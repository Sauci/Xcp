import hashlib
import os
import sys
import random
import traceback

import pytest
from bsw_code_gen import BSWCodeGen
from cffi import FFI
from importlib import import_module
from io import StringIO
from re import sub
from unittest.mock import MagicMock
from glob import glob

from pycparser.c_ast import FuncDecl, NodeVisitor
from pycparser.c_generator import CGenerator as Generator
from pycparser.c_parser import CParser
from pcpp.preprocessor import Preprocessor as Pp


def pytest_addoption(parser):
    parser.addoption('--build_directory', action='store')
    parser.addoption('--script_directory', action='store')
    parser.addoption('--header', action='store')
    parser.addoption('--source', action='store')
    parser.addoption('--compile_definitions', action='store')
    parser.addoption('--include_directories', action='store')


def pytest_configure(config):
    print(config)
    os.environ['build_directory'] = config.getoption('build_directory')
    os.environ['script_directory'] = config.getoption('script_directory')
    os.environ['header'] = config.getoption('header')
    os.environ['source'] = config.getoption('source')
    os.environ['compile_definitions'] = config.getoption('compile_definitions')
    os.environ['include_directories'] = config.getoption('include_directories')


@pytest.fixture
def seed(request) -> [int]:
    return [random.getrandbits(8, ) for _ in range(request.param)]


@pytest.fixture
def seed_array(request) -> [[int]]:
    seed_size, number_of_seeds = request.param
    return [[random.getrandbits(8, ) for _ in range(seed_size)] for _ in range(number_of_seeds)]


def _asan_flags():
    """Debug aid: set XCP_ASAN=1 to build the module under test with AddressSanitizer.

    Requires a glibc toolchain and running python with libasan LD_PRELOADed. Off by default,
    so the normal build is unaffected.
    """
    return ('-fsanitize=address', '-fno-omit-frame-pointer') if os.getenv('XCP_ASAN') else tuple()


def convert(name):
    s1 = sub('(.)([A-Z][a-z][_]+)', r'\1_\2', name)
    return sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class FunctionDecl(NodeVisitor):
    def __init__(self, source_string):
        self.static = set()
        self.extern = set()
        self.locals = set()
        self.visit(CParser().parse(source_string))

    def visit_Decl(self, node):
        if isinstance(node.type, FuncDecl):
            if 'static' in node.storage:
                self.static.add(node)
            elif 'extern' in node.storage:
                self.extern.add(node)
            else:
                self.locals.add(node)


class CFFIHeader(Generator):
    def __init__(self, interface, local, extern):
        super(CFFIHeader, self).__init__()
        self.locals = set(e.name for e in local)
        self.extern = set(e.name for e in extern)
        self.mocked = set()
        self.string = self.visit(CParser().parse(interface))

    def __str__(self):
        return self.string

    def visit_Decl(self, n, no_type=False):
        if isinstance(n.type, FuncDecl):
            if n.name in self.extern:
                self.mocked.add(n.name)
                n.storage.remove('extern')
                n.storage.append('extern "Python+C"')
        return Generator.visit_Decl(self, n)


class Preprocessor(Pp):
    def __init__(self):
        super(Preprocessor, self).__init__()
        self.defines = dict()

    @staticmethod
    def _token_to_int(token_value):
        value = token_value.rstrip('UuLl')
        try:
            return int(value, 10)
        except ValueError:
            return int(value, 16)

    def on_directive_handle(self, directive, tokens, if_pass_thru, preceding_tokens):
        if directive.value == 'define':
            name = [t.value for t in tokens if t.type == 'CPP_ID']
            value = [t.value for t in tokens if t.type in 'CPP_INTEGER']
            if len(name) and len(value):
                self.defines[name[0]] = self._token_to_int(value[0])
        return super(Preprocessor, self).on_directive_handle(directive, tokens, if_pass_thru, preceding_tokens)

    def resolve_effective_defines(self):
        """pcpp calls on_directive_handle for every #define its scanner walks past while it
        determines nesting -- including one sitting in a false #ifndef/#if branch -- and does not
        tell the hook whether that branch was actually taken (`if_pass_thru` is a different, and
        for our purposes unrelated, pcpp concept). So a header guarded as
        `#ifndef X / #define X (fallback) / #endif`, where X was already defined to something else
        via a compile definition, leaves self.defines holding the unused fallback rather than the
        value actually in effect. self.macros is pcpp's own macro table, updated only for branches
        it actually took, so once parsing has finished it is authoritative for any name still
        defined; call this after parse()/write() to correct self.defines from it.
        """
        for name in list(self.defines):
            macro = self.macros.get(name)
            if macro is None:
                continue
            value = [t.value for t in macro.value if t.type in 'CPP_INTEGER']
            if value:
                try:
                    self.defines[name] = self._token_to_int(value[0])
                except ValueError:
                    pass


class MockGen(FFI):
    _pp = dict()
    _ffi_header = dict()
    _parse_cache = dict()

    def __init__(self,
                 name,
                 source,
                 header,
                 include_dirs=tuple(),
                 define_macros=tuple(),
                 compile_flags=tuple(),
                 link_flags=tuple(),
                 link_libraries=tuple(),
                 sources=tuple(),
                 build_dir=''):
        super(MockGen, self).__init__()
        self._name = name
        if self.name in sys.modules:
            self.ffi_module = sys.modules[self.name]
        else:
            # The generated Xcp_Cfg.h and Xcp_Rt.h depend only on the number of configurations,
            # so every test configuration yields byte-identical header text. Parsing is keyed on
            # that text (plus the macros pcpp expands with) rather than on the module name, so
            # the preprocess and the two pycparser passes run once per distinct header instead
            # of once per module. Without this a full run performed several hundred redundant
            # parses through pcpp, pycparser and PLY, all of which hold global mutable state.
            parse_key = hashlib.sha1(
                (header + repr(sorted(define_macros)) + repr(sorted(include_dirs))).encode('utf-8')).hexdigest()
            if parse_key not in self._parse_cache:
                pre_processor = Preprocessor()
                for include_directory in include_dirs:
                    pre_processor.add_path(include_directory)
                for compile_definition in (' '.join(d.split('=')) for d in define_macros):
                    pre_processor.define(compile_definition)
                pre_processor.parse(header)
                handle = StringIO()
                pre_processor.write(handle)
                expanded = handle.getvalue()
                pre_processor.resolve_effective_defines()
                func_decl = FunctionDecl(expanded)
                # Built once: the original code constructed CFFIHeader twice per module, once to
                # store and once to feed cdef.
                self._parse_cache[parse_key] = (pre_processor,
                                                CFFIHeader(expanded, func_decl.locals, func_decl.extern))
            pre_processor, cffi_header = self._parse_cache[parse_key]
            self._pp[self.name] = pre_processor
            self._ffi_header[self.name] = cffi_header
            # cffi caches one pycparser.CParser in cffi.cparser._parser_cache and reuses it for
            # every cdef(), so a parse that raises leaves the shared PLY parser's symstack and
            # statestack dirty and later parses return nonsense. Resetting that cache per module
            # was tried and measured WORSE -- it forced 184 CParser constructions and the suite
            # completed less often -- so it was reverted in 9e880ba. Left here as a warning: the
            # residual flake looks like this, and this is not the fix.
            self.cdef(str(cffi_header))
            self.set_source(self.name, source,
                            include_dirs=include_dirs,
                            define_macros=list(tuple(d.split('=')) for d in define_macros),
                            extra_compile_args=list(compile_flags),
                            libraries=list(link_libraries),
                            library_dirs=(build_dir,),
                            sources=list(sources),
                            extra_link_args=list(link_flags))
            # distutils places each source's object at <tmpdir>/<abs-path-without-leading-/>,
            # ignoring the extension name entirely. That's fine for cffi's own generated glue
            # file (named after this extension, so already unique) but not for an extra source
            # given by absolute path: every rt_key's MockGen compiles the same Xcp.c path, and
            # each recompile overwrites the previous one's .o/.gcno at that identical spot. The
            # resulting .gcda then carries a stamp tied to whichever compile happened last, so
            # gcov refuses to associate it with data flushed by any other rt_key's copy at exit
            # (all of them share this one process), and coverage for Xcp.c collapses to zero.
            # Compiling extra sources into a subdirectory namespaced by this module's own name
            # keeps every rt_key's copy at its own path, so each stays internally consistent.
            lib_path = self.compile(tmpdir=os.path.join(build_dir, self.name) if sources else build_dir)
            sys.path.append(os.path.dirname(lib_path))
            self.ffi_module = import_module(self.name)

    @property
    def name(self):
        return self._name

    @property
    def pp(self):
        return self._pp[self.name]

    @property
    def ffi_header(self):
        return self._ffi_header[self.name]

    @property
    def mocked(self):
        return self.ffi_header.mocked

    @property
    def ffi(self):
        return self.ffi_module.ffi

    @property
    def lib(self):
        return self.ffi_module.lib


class _GeneratedSources(object):
    """Snapshot of a BSWCodeGen's outputs, so the generator need not be re-run per test."""

    def __init__(self, code_gen):
        self.header_cfg = code_gen.header_cfg
        self.source_cfg = code_gen.source_cfg
        self.header_rt = code_gen.header_rt
        self.source_rt = code_gen.source_rt


class XcpTest(object):
    _code_gen_cache = dict()
    # Every live instance, so the _callback_invariants autouse fixture below can sweep
    # dto_queue_area_violations and callback_exceptions after each test, without each test
    # remembering to check them itself.
    _instances = list()

    def __init__(self,
                 config,
                 initialize=True,
                 rx_buffer_size=0x0FFF,
                 configuration_index=0):
        # Which of the generated file's configurations Xcp_Init runs against, i.e. which element
        # of `const Xcp_Type Xcp[]` becomes Xcp_Ptr. Only ever other than 0 for a MultiConfig
        # (test/parameter.py): with one configuration there is nothing to choose, and a
        # build-wide macro and the active configuration's own fields can never disagree.
        self.configuration_index = configuration_index
        self.available_rx_buffer = rx_buffer_size
        # DD14/fix round 1: SchM_Enter_Xcp_DtoQueue and SchM_Exit_Xcp_DtoQueue below are given
        # side effects that model the exclusive area as a single boolean, so nesting,
        # ordering and imbalance are all observable instead of only being counted. dto_queue_area_held
        # is readable directly by a test that wants to confirm a read happens outside the area;
        # dto_queue_area_violations is swept by the autouse fixture below.
        self.dto_queue_area_held = False
        self.dto_queue_area_violations = list()
        # CFFI swallows any exception raised inside an `extern "Python+C"` callback: it prints the
        # traceback to stderr and returns 0 to the C caller. E_OK is 0x00u, so a raising mock
        # reports SUCCESS to the module under test and a test can pass on an assertion that never
        # ran. Every callback is wrapped by _guarded_callback below so the exception lands here and
        # the _callback_invariants autouse fixture fails the test once control is back in Python.
        self.callback_exceptions = list()
        XcpTest._instances.append(self)
        # Owns every buffer handed to the C module, so none is freed while C still points at it.
        self._pdu_info_keepalive = list()
        self.can_if_tx_data = list()
        self.can_tp_rx_data = list()
        # BSWCodeGen builds a fresh jinja2 Environment and recompiles every template on each
        # construction, and XcpTest constructs one per test. A file such as upload_test.py runs
        # thousands of tests over a handful of distinct configurations, so this ran tens of
        # thousands of template compilations to produce a handful of distinct outputs, and
        # jinja2 eventually emitted malformed Python for a template. Generated sources depend
        # only on the configuration, so cache them by configuration id.
        code_gen = self._code_gen_cache.get(config.get_id)
        if code_gen is None:
            code_gen = _GeneratedSources(BSWCodeGen(config, self.script_directory))
            self._code_gen_cache[config.get_id] = code_gen
        with open(os.path.join(self.build_directory, 'Xcp_Cfg.h'), 'w') as fp:
            fp.write(code_gen.header_cfg)
        with open(os.path.join(self.build_directory, 'Xcp_Cfg.c'), 'w') as fp:
            fp.write(code_gen.source_cfg)
        with open(os.path.join(self.build_directory, 'Xcp_Rt.h'), 'w') as fp:
            fp.write(code_gen.header_rt)
        with open(os.path.join(self.build_directory, 'Xcp_Rt.c'), 'w') as fp:
            fp.write(code_gen.source_rt)
        with open(self.header, 'r') as fp:
            header = fp.read()
        os.environ['DYLD_LIBRARY_PATH'] = '{}'.format(self.build_directory)
        os.environ['LD_LIBRARY_PATH'] = '{}'.format(self.build_directory)
        # XCP_PAGING_SUPPORTED is emitted into the generated Xcp_Cfg.h for integrators, but the
        # module under test never includes Xcp_Cfg.h: doing so would pull
        # `extern const Xcp_Type Xcp[...]` into its cdef, and that symbol is only ever defined in
        # the separate configuration module it is not linked against (undefined symbol at import
        # time). Thread the same value through as a compile definition instead, derived from the
        # same configuration.segments the generated header keys off, and give it to every module:
        # self.compile_definitions carries whatever the CMake build derived, which is not
        # necessarily what this configuration needs, and it would otherwise suppress the generated
        # header's own definition. A later -D wins, so appending the derived value corrects it.
        paging_define = ('XCP_PAGING_SUPPORTED={}'.format(
                'STD_ON' if any(c.get('segments') for c in config['configurations']) else 'STD_OFF'),)
        # XCP_MAX_DTO sizes the DTO frame buffers in Xcp_Types.h, which every module includes, so
        # all three compiled modules must agree on it or the ring in the runtime module and the
        # code that indexes it disagree on the element stride. Same reasoning as paging_define
        # above: the generated Xcp_Cfg.h is not visible to the module under test.
        max_dto_define = ('XCP_MAX_DTO=0x{:02X}'.format(
                max(c['protocol_layer']['max_dto'] for c in config['configurations'])),)
        # XCP_DAQ_TIMESTAMP_SUPPORTED/_SIZE gate Xcp_GetDaqTimestamp's declaration (once a later
        # task wires it into Xcp.h) and describe the timestamp field width to code compiled
        # against Xcp_Types.h. Same reasoning as paging_define/max_dto_define above: the generated
        # Xcp_Cfg.h is not visible to the module under test, so these are derived here from the
        # configuration dict directly and given to every module. One macro is on when ANY
        # configuration declares a timestamp block, and the other is the largest configured wire
        # size, mirroring header_cfg.h.jinja2's own aggregation over every configuration.
        # Unlike paging_define, this is given as a bare 0/1 rather than STD_OFF/STD_ON: identical
        # once the preprocessor expands STD_ON/STD_OFF for the actual `#if` compilation, but
        # test.conftest.Preprocessor.on_directive_handle/resolve_effective_defines (above) only
        # ever records a #define's value when it tokenizes as a literal integer, so a symbolic
        # right-hand side would leave handle.define('XCP_DAQ_TIMESTAMP_SUPPORTED') KeyError-ing
        # regardless of the override reaching the compiler correctly.
        daq_timestamp_supported_define = ('XCP_DAQ_TIMESTAMP_SUPPORTED={}'.format(
                1 if any(c['protocol_layer'].get('timestamp')
                         for c in config['configurations']) else 0),)
        daq_timestamp_wire_size = {'BYTE': 1, 'WORD': 2, 'DWORD': 4}
        daq_timestamp_size_define = ('XCP_DAQ_TIMESTAMP_SIZE={}'.format(
                max((daq_timestamp_wire_size[c['protocol_layer']['timestamp']['size']]
                     for c in config['configurations'] if c['protocol_layer'].get('timestamp')),
                    default=0)),)
        # The module under test is only coupled to a configuration through the generated
        # runtime it links against, so key both on a digest of that generated source rather
        # than on the whole configuration. Configurations producing identical runtime source
        # then share one compiled pair, which collapses hundreds of compiled and dlopened
        # modules down to a handful, while any change to the generated runtime automatically
        # produces a new key. Keying on the whole configuration compiled a fresh copy per
        # parametrisation; keying by hand on event_queue_size would silently break the first
        # time the runtime template gained another dependency. paging_define is discriminated by
        # the same digest, because it is a function of the segment count and the generated runtime
        # sizes Xcp_SegmentRt00 by that same count. max_dto_define has no such relationship to
        # source_rt -- nothing in the runtime template reads protocol_layer.max_dto -- so two
        # configurations that differ only by max_dto would otherwise hash identically here and
        # MockGen's `if self.name in sys.modules` cache hit would silently keep serving whichever
        # one compiled first, including its baked-in XCP_MAX_DTO. Folding max_dto_define into the
        # digest directly keeps it, rather than incidental correlation, responsible for the key.
        # self.code below is keyed on this same rt_key (not a key of its own), so this digest is
        # what protects it against staleness too. daq_timestamp_supported_define/size_define are
        # in exactly max_dto_define's position -- nothing in source_rt reads protocol_layer
        # .timestamp either -- so two configurations differing only by timestamp size would
        # otherwise collide here and hand the second one the first one's baked-in
        # XCP_DAQ_TIMESTAMP_SIZE. Confirmed by running the parametrized BYTE/WORD/DWORD cases of
        # test_configured_timestamp_reaches_the_generated_configuration without this fold: the
        # second case failed with the first case's wire size still in effect.
        rt_key = hashlib.sha1((code_gen.source_rt + max_dto_define[0] + daq_timestamp_supported_define[0] +
                              daq_timestamp_size_define[0]).encode('utf-8')).hexdigest()[0:8]
        self.rt = MockGen('libcffi_xcp_rt_{}'.format(rt_key),
                          code_gen.source_rt,
                          code_gen.header_rt,
                          define_macros=tuple(self.compile_definitions) +
                                        ('XCP_EVENT_QUEUE_SIZE=0x{:04X}'.format(config.event_queue_size),) +
                                        paging_define +
                                        max_dto_define +
                                        daq_timestamp_supported_define +
                                        daq_timestamp_size_define,
                          include_dirs=tuple(self.include_directories + [self.build_directory]),
                          compile_flags=_asan_flags(),
                          link_flags=_asan_flags(),
                          build_dir=self.build_directory)
        self.config = MockGen('_cffi_xcp_cfg_{}'.format(config.get_id),
                              code_gen.source_cfg,
                              code_gen.header_cfg,
                              define_macros=tuple(self.compile_definitions) +
                                            ('XCP_PDU_ID_CTO_RX=0x{:04X}'.format(config.channel_rx_pdu),) +
                                            ('XCP_PDU_ID_CTO_TX=0x{:04X}'.format(config.channel_tx_pdu),) +
                                            ('XCP_PDU_ID_TRANSMIT=0x{:04X}'.format(
                                                    config.default_daq_dto_pdu_mapping),) +
                                            paging_define +
                                            max_dto_define +
                                            daq_timestamp_supported_define +
                                            daq_timestamp_size_define,
                              include_dirs=tuple(self.include_directories + [self.build_directory]),
                              compile_flags=_asan_flags(),
                              link_flags=_asan_flags(),
                              build_dir=self.build_directory)
        f = glob(os.path.join(self.build_directory, 'libcffi_xcp_rt_{}*.so'.format(rt_key)))[0]
        # The module under test is compiled with XCP_EVENT_QUEUE_SIZE and linked against one
        # libcffi_xcp_rt_*.so whose Xcp_Event00 array is sized at compile time. Sharing a single
        # '_cffi_xcp' across configurations let Xcp_Init run with one configuration's
        # eventQueueSize against another's array, overflowing it (ASan: global-buffer-overflow
        # in Xcp_EventQueueInit). Keying on the same rt_key keeps the compiled bound and the
        # linked array in the same generated pair.
        self.code = MockGen('_cffi_xcp_{}'.format(rt_key),
                            '#include "Xcp.h"',
                            header,
                            define_macros=tuple(self.compile_definitions) +
                                          ('XCP_EVENT_QUEUE_SIZE=0x{:04X}'.format(config.event_queue_size),) +
                                          paging_define +
                                          max_dto_define +
                                          daq_timestamp_supported_define +
                                          daq_timestamp_size_define,
                            include_dirs=tuple(self.include_directories + [self.build_directory]),
                            compile_flags=('-g', '-O0', '-fprofile-arcs', '-ftest-coverage') + _asan_flags(),
                            link_flags=('-g', '-O0', '-fprofile-arcs', '-ftest-coverage',) + _asan_flags(),
                            link_libraries=(os.path.basename(f).lstrip('lib').rstrip('.so'),),
                            sources=tuple(self.sources),
                            build_dir=self.build_directory)
        self.can_if_transmit = MagicMock()
        self.det_report_error = MagicMock()
        self.det_report_runtime_error = MagicMock()
        self.det_report_transient_fault = MagicMock()
        self.xcp_get_seed = MagicMock()
        self.xcp_calc_key = MagicMock()
        self.xcp_set_cal_page = MagicMock()
        self.xcp_get_cal_page = MagicMock()
        self.xcp_copy_cal_page = MagicMock()
        self.xcp_read_slave_memory_u8 = MagicMock()
        self.xcp_read_slave_memory_u16 = MagicMock()
        self.xcp_read_slave_memory_u32 = MagicMock()
        self.xcp_write_slave_memory_u8 = MagicMock()
        self.xcp_write_slave_memory_u16 = MagicMock()
        self.xcp_write_slave_memory_u32 = MagicMock()
        self.xcp_store_calibration_data_to_non_volatile_memory = MagicMock()
        # Xcp_GetDaqTimestamp reaches self.code.mocked on its own once Xcp_DaqTimestamp.h is
        # pulled in under XCP_DAQ_TIMESTAMP_SUPPORTED -- pcpp discovers any `extern`-declared
        # function reachable from interface/Xcp.h without help. What it does not do is invent this
        # attribute: the loop below is a plain getattr(self, convert(func)), so a configuration
        # that enables the timestamp without this assignment existing fails inside this
        # constructor with AttributeError, not inside whichever test happened to ask for it.
        self.xcp_get_daq_timestamp = MagicMock()
        self.sch_m_enter_xcp_dto_queue = MagicMock()
        self.sch_m_exit_xcp_dto_queue = MagicMock()
        self.xcp_user_cmd_function = MagicMock()
        self.config.ffi.def_extern('Xcp_UserCmdFunction')(
                self._guarded_callback('Xcp_UserCmdFunction', self.xcp_user_cmd_function))
        self.xcp_user_cmd_function.return_value = self.define('E_OK')
        self.xcp_user_defined_checksum_function = MagicMock()
        self.config.ffi.def_extern('Xcp_UserDefinedChecksumFunction')(
                self._guarded_callback('Xcp_UserDefinedChecksumFunction',
                                       self.xcp_user_defined_checksum_function))
        self.xcp_user_defined_checksum_function.return_value = 0
        for func in self.code.mocked:
            self.ffi.def_extern(func)(self._guarded_callback(func, getattr(self, convert(func))))
        self.can_if_transmit.return_value = self.define('E_OK')
        self.det_report_error.return_value = self.define('E_OK')
        self.det_report_runtime_error.return_value = self.define('E_OK')
        self.det_report_transient_fault.return_value = self.define('E_OK')
        self.xcp_get_seed.return_value = self.define('E_OK')
        self.xcp_calc_key.return_value = self.define('E_OK')
        self.xcp_set_cal_page.return_value = self.define('E_OK')
        self.xcp_get_cal_page.return_value = self.define('E_OK')
        self.xcp_copy_cal_page.return_value = self.define('E_OK')
        self.xcp_read_slave_memory_u8.return_value = None
        self.xcp_read_slave_memory_u16.return_value = None
        self.xcp_read_slave_memory_u32.return_value = None
        self.xcp_write_slave_memory_u8.return_value = None
        self.xcp_write_slave_memory_u16.return_value = None
        self.xcp_write_slave_memory_u32.return_value = None
        self.xcp_store_calibration_data_to_non_volatile_memory.return_value = self.define('E_OK')
        # Fix round 1: MagicMock pre-configures __int__/__index__ to return 1, so a call reaching
        # this mock through the real CFFI boundary (extern "Python+C", uint32 return) coerces
        # successfully to 1 instead of raising -- _guarded_callback only records an exception the
        # mock itself raises, and return-type coercion happens after mock() has already returned,
        # outside that try/except. Left unset, a test that forgets to configure this callback would
        # not fail loudly; it would silently bake a wrong-but-plausible-looking timestamp into a
        # DTO. 0xFFFFFFFF rather than the more obvious 0: a free-running counter reading 0 is a
        # plausible real sample (e.g. right after reset), so it would not stand out in a failing
        # assertion the way this maximum-value sentinel does. Matches the precedent e150861 set for
        # xcp_set_cal_page/xcp_get_cal_page/xcp_copy_cal_page: defaulted in the same commit that
        # added the mock, before any real call site existed anywhere in source/*.c.
        self.xcp_get_daq_timestamp.return_value = 0xFFFFFFFF
        def enter_dto_queue_area():
            if self.dto_queue_area_held:
                self.dto_queue_area_violations.append(
                        'SchM_Enter_Xcp_DtoQueue called while already held (nested or double enter)')
            self.dto_queue_area_held = True

        def exit_dto_queue_area():
            if not self.dto_queue_area_held:
                self.dto_queue_area_violations.append(
                        'SchM_Exit_Xcp_DtoQueue called while not held (exit without a matching enter)')
            self.dto_queue_area_held = False

        self.sch_m_enter_xcp_dto_queue.side_effect = enter_dto_queue_area
        self.sch_m_exit_xcp_dto_queue.side_effect = exit_dto_queue_area

        self.code.lib.Xcp_State = self.code.lib.XCP_UNINITIALIZED
        if initialize:
            # addressof(array, index) rather than a plain cast of the array, so a
            # configuration_index other than 0 selects that element of Xcp[] the way an
            # integrator's own Xcp_Init(&Xcp[n]) call would. Index 0 is byte-for-byte the cast
            # this replaced.
            self.code.lib.Xcp_Init(self.code.ffi.cast(
                    'const Xcp_Type *',
                    self.config.ffi.addressof(self.config.lib.Xcp, configuration_index)))

    def _guarded_callback(self, name, mock):
        """Wraps a mock so an exception it raises is recorded rather than only printed.

        The exception is re-raised so CFFI's own handling is unchanged -- it still prints the
        traceback and returns 0 to C, exactly as before -- and the mock itself is still the object
        the test asserts `call_args` and `call_count` on. All this adds is a record the
        _callback_invariants fixture can fail on, which is the difference between a test that
        passes because the code is right and one that passes because its assertion never ran.
        """
        def call(*args):
            try:
                return mock(*args)
            except BaseException:
                self.callback_exceptions.append((name, traceback.format_exc()))
                raise

        return call

    def get_pdu_info(self, payload, null_payload=False, overridden_size=None, meta_data=None):
        if isinstance(payload, str):
            payload = [ord(c) for c in payload]
        sdu_data = self.code.ffi.new('uint8 []', list(payload))
        if overridden_size is not None:
            sdu_length = overridden_size
        else:
            sdu_length = len(payload)
        if null_payload:
            sdu_data = self.code.ffi.NULL
        pdu_info = self.code.ffi.new('PduInfoType *')
        pdu_info.SduDataPtr = sdu_data
        pdu_info.SduLength = sdu_length
        if meta_data is not None:
            sdu_meta_data = self.code.ffi.new('uint8 []', list(meta_data))
            pdu_info.MetaDataPtr = sdu_meta_data
        else:
            sdu_meta_data = None
            pdu_info.MetaDataPtr = self.code.ffi.NULL
        # Assigning a buffer's address into a cdata field does NOT keep that buffer alive:
        # cffi frees the memory owned by ffi.new() as soon as the returned object goes out of
        # scope. Without this, SduDataPtr and MetaDataPtr would dangle into memory CPython has
        # already reused, and the C under test would read (and act on) live Python objects.
        self._pdu_info_keepalive.append((pdu_info, sdu_data, sdu_meta_data))
        return pdu_info

    def define(self, name):
        return self.code.pp.defines[name]

    @property
    def lib(self):
        return self.code.lib

    @property
    def ffi(self):
        return self.code.ffi

    @property
    def build_directory(self):
        return os.getenv('build_directory')

    @property
    def script_directory(self):
        return os.getenv('script_directory')

    @property
    def header(self):
        return os.getenv('header')

    @property
    def sources(self):
        return os.getenv('source').split(';')

    @property
    def compile_definitions(self):
        return os.getenv('compile_definitions').split(';') + ['CFFI_ENABLE=STD_ON']

    @property
    def include_directories(self):
        return os.getenv('include_directories').split(';')


@pytest.fixture(autouse=True)
def _callback_invariants():
    """Checks, after every test, the two things the C/Python boundary cannot report on its own: an
    exception raised inside a CFFI callback, and an imbalance in the DTO-queue exclusive area.

    Both exist for one reason. A callback registered with `extern "Python+C"` that raises has its
    traceback printed to stderr and swallowed at the boundary; the C caller is handed 0, which is
    E_OK. So neither an assertion inside a mock nor a raise from the SchM_Enter/Exit side effects
    can fail the test that is still executing C code several frames up. Recording both without
    raising, then asserting here once control is back in pure Python, sidesteps that entirely.

    SchM_Enter/Exit_Xcp_DtoQueue's side effects (XcpTest.__init__ above) model the exclusive area as
    a boolean, so a violation means a real nesting, ordering, or enter/exit imbalance was exercised
    by the test that just ran -- not merely that the mocks were called an unexpected number of
    times. A test that leaves the area HELD at teardown is caught too: an Enter with no matching
    Exit is a leaked lock, which in a real integration means interrupts stay masked.

    Every test gets all of this for free -- the fixture is autouse and every XcpTest registers
    itself in XcpTest._instances.
    """
    XcpTest._instances = list()

    yield

    violations = [(instance, violation)
                  for instance in XcpTest._instances
                  for violation in instance.dto_queue_area_violations]
    leaked = [instance for instance in XcpTest._instances if instance.dto_queue_area_held]
    raised = [entry
              for instance in XcpTest._instances
              for entry in instance.callback_exceptions]
    XcpTest._instances = list()

    assert raised == [], \
        'an exception was raised inside a CFFI callback, where it would otherwise be swallowed and '\
        'reported to the module under test as E_OK:\n{}'.format(
                '\n'.join('{}:\n{}'.format(name, tb) for name, tb in raised))

    assert violations == [], \
        'SchM_Enter_Xcp_DtoQueue/SchM_Exit_Xcp_DtoQueue nesting or imbalance: {}'.format(
                [v for _, v in violations])
    assert leaked == [], \
        'SchM_Enter_Xcp_DtoQueue left the area held at teardown -- a leaked lock -- in {} instance(s)'.format(
                len(leaked))

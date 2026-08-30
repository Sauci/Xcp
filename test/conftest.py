import hashlib
import os
import sys
import random

import pytest
from bsw_code_gen import BSWCodeGen
from cffi import FFI
from cffi import cparser as cffi_cparser
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

    def on_directive_handle(self, directive, tokens, if_pass_thru, preceding_tokens):
        if directive.value == 'define':
            name = [t.value for t in tokens if t.type == 'CPP_ID']
            value = [t.value for t in tokens if t.type in 'CPP_INTEGER']
            if len(name) and len(value):
                name = name[0]
                value = value[0].rstrip('UuLl')
                try:
                    value = int(value, 10)
                except ValueError:
                    try:
                        value = int(value, 16)
                    except ValueError as e:
                        raise e
                self.defines[name] = value
        return super(Preprocessor, self).on_directive_handle(directive, tokens, if_pass_thru, preceding_tokens)


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
                func_decl = FunctionDecl(expanded)
                # Built once: the original code constructed CFFIHeader twice per module, once to
                # store and once to feed cdef.
                self._parse_cache[parse_key] = (pre_processor,
                                                CFFIHeader(expanded, func_decl.locals, func_decl.extern))
            pre_processor, cffi_header = self._parse_cache[parse_key]
            self._pp[self.name] = pre_processor
            self._ffi_header[self.name] = cffi_header
            # cffi caches a single pycparser.CParser in cffi.cparser._parser_cache and reuses
            # it for every cdef(). pycparser resets its own scope stack per parse, but the
            # underlying PLY parser object is shared, so once any parse raises, PLY's symstack
            # and statestack stay dirty and every later parse returns nonsense (AST nodes where
            # dicts are expected, 'list' object is not callable, and so on). Force a fresh
            # parser per module so one bad parse cannot poison the rest of the session.
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

    def __init__(self,
                 config,
                 initialize=True,
                 rx_buffer_size=0x0FFF):
        self.available_rx_buffer = rx_buffer_size
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
        # The module under test is only coupled to a configuration through the generated
        # runtime it links against, so key both on a digest of that generated source rather
        # than on the whole configuration. Configurations producing identical runtime source
        # then share one compiled pair, which collapses hundreds of compiled and dlopened
        # modules down to a handful, while any change to the generated runtime automatically
        # produces a new key. Keying on the whole configuration compiled a fresh copy per
        # parametrisation; keying by hand on event_queue_size would silently break the first
        # time the runtime template gained another dependency.
        rt_key = hashlib.sha1(code_gen.source_rt.encode('utf-8')).hexdigest()[0:8]
        self.rt = MockGen('libcffi_xcp_rt_{}'.format(rt_key),
                          code_gen.source_rt,
                          code_gen.header_rt,
                          define_macros=tuple(self.compile_definitions) +
                                        ('XCP_EVENT_QUEUE_SIZE=0x{:04X}'.format(config.event_queue_size),),
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
                                                    config.default_daq_dto_pdu_mapping),),
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
                                          ('XCP_EVENT_QUEUE_SIZE=0x{:04X}'.format(config.event_queue_size),),
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
        self.xcp_user_cmd_function = MagicMock()
        self.config.ffi.def_extern('Xcp_UserCmdFunction')(self.xcp_user_cmd_function)
        self.xcp_user_cmd_function.return_value = self.define('E_OK')
        self.xcp_user_defined_checksum_function = MagicMock()
        self.config.ffi.def_extern('Xcp_UserDefinedChecksumFunction')(self.xcp_user_defined_checksum_function)
        self.xcp_user_defined_checksum_function.return_value = 0
        for func in self.code.mocked:
            self.ffi.def_extern(func)(getattr(self, convert(func)))
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

        self.code.lib.Xcp_State = self.code.lib.XCP_UNINITIALIZED
        if initialize:
            self.code.lib.Xcp_Init(self.code.ffi.cast('const Xcp_Type *', self.config.lib.Xcp))

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

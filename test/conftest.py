import os
import sys

from bsw_code_gen import BSWCodeGen
from cffi import FFI
from importlib import import_module
from io import StringIO
from re import sub
from unittest.mock import MagicMock

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
    def __init__(self,
                 name,
                 source,
                 header,
                 include_dirs=tuple(),
                 define_macros=tuple(),
                 compile_flags=tuple(),
                 link_flags=tuple(),
                 build_dir=''):
        super(MockGen, self).__init__()
        self.pp = Preprocessor()
        for include_directory in include_dirs:
            self.pp.add_path(include_directory)
        for compile_definition in (' '.join(d.split('=')) for d in define_macros):
            self.pp.define(compile_definition)
        self.pp.parse(header)
        handle = StringIO()
        self.pp.write(handle)
        self.header = handle.getvalue()
        func_decl = FunctionDecl(self.header)
        self.ffi_header = CFFIHeader(self.header, func_decl.locals, func_decl.extern)
        if name in sys.modules:
            self.ffi_module = sys.modules[name]
        else:
            self.cdef(str(CFFIHeader(self.header, func_decl.locals, func_decl.extern)))
            self.set_source(name, source,
                            include_dirs=include_dirs,
                            define_macros=list(tuple(d.split('=')) for d in define_macros),
                            extra_compile_args=list(compile_flags),
                            extra_link_args=list(link_flags))
            lib_path = self.compile(tmpdir=build_dir)
            sys.path.append(os.path.dirname(lib_path))
            self.ffi_module = import_module(name)

    @property
    def mocked(self):
        return self.ffi_header.mocked

    @property
    def ffi(self):
        return self.ffi_module.ffi

    @property
    def lib(self):
        return self.ffi_module.lib


class XcpTest(object):
    def __init__(self,
                 config,
                 initialize=True,
                 rx_buffer_size=0x0FFF):
        self.available_rx_buffer = rx_buffer_size
        self.can_if_tx_data = list()
        self.can_tp_rx_data = list()
        code_gen = BSWCodeGen(config, self.script_directory)
        with open(os.path.join(self.build_directory, 'Xcp_Cfg.h'), 'w') as fp:
            fp.write(code_gen.header)
        with open(os.path.join(self.build_directory, 'Xcp_Cfg.c'), 'w') as fp:
            fp.write(code_gen.source)
        with open(self.header, 'r') as fp:
            header = fp.read()
        self.config = MockGen('_cffi_xcp_cfg_{}'.format(config.get_id),
                              code_gen.source,
                              code_gen.header,
                              define_macros=tuple(self.compile_definitions) +
                                            ('XCP_PDU_ID_CTO_RX=0x{:04X}'.format(config.channel_rx_pdu_ref),) +
                                            ('XCP_PDU_ID_CTO_TX=0x{:04X}'.format(config.channel_tx_pdu_ref),) +
                                            ('XCP_PDU_ID_TRANSMIT=0x{:04X}'.format(config.default_daq_dto_pdu_mapping),),
                              include_dirs=tuple(self.include_directories + [self.build_directory]),
                              build_dir=self.build_directory)
        self.code = MockGen('_cffi_xcp',
                            '#include "{}"'.format(self.source),
                            header,
                            define_macros=tuple(self.compile_definitions),
                            include_dirs=tuple(self.include_directories + [self.build_directory]),
                            compile_flags=('-g', '-O0', '-fprofile-arcs', '-ftest-coverage'),
                            link_flags=('-g', '-O0', '-fprofile-arcs', '-ftest-coverage'),
                            build_dir=self.build_directory)
        self.code.lib.Xcp_State = self.code.lib.XCP_UNINITIALIZED
        if initialize:
            self.code.lib.Xcp_Init(self.code.ffi.cast('const Xcp_Type *', self.config.lib.Xcp))
            if self.code.lib.Xcp_State != self.code.lib.XCP_INITIALIZED:
                raise ValueError('Xcp module not initialized correctly...')

        self.can_if_transmit = MagicMock()
        self.det_report_error = MagicMock()
        self.det_report_runtime_error = MagicMock()
        self.det_report_transient_fault = MagicMock()
        for func in self.code.mocked:
            self.ffi.def_extern(func)(getattr(self, convert(func)))
        self.can_if_transmit.return_value = self.define('E_OK')
        self.det_report_error.return_value = self.define('E_OK')
        self.det_report_runtime_error.return_value = self.define('E_OK')
        self.det_report_transient_fault.return_value = self.define('E_OK')

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
            pdu_info.MetaDataPtr = self.code.ffi.NULL
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
    def source(self):
        return os.getenv('source')

    @property
    def compile_definitions(self):
        return os.getenv('compile_definitions').split(';') + ['CFFI_ENABLE=STD_ON']

    @property
    def include_directories(self):
        return os.getenv('include_directories').split(';')

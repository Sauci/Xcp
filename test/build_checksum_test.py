#!/usr/bin/env python
# -*- coding: utf-8 -*-

# see http://www.sunshine2k.de/coding/javascript/crc/crc_js.html

import crcmod
import crcmod.predefined

from jinja2.exceptions import UndefinedError

from .parameter import *
from .conftest import XcpTest

from unittest.mock import ANY


def checksum_add_u8_into_u8(data: [int], _byte_order) -> int:
    result = 0
    for b in data:
        result = ((result & 0xFF) + b) & 0xFF
    return result


def checksum_add_u8_into_u16(data: [int], _byte_order) -> int:
    result = 0
    for b in data:
        result = ((result & 0xFFFF) + b) & 0xFFFF
    return result


def checksum_add_u8_into_u32(data: [int], _byte_order) -> int:
    result = 0
    for b in data:
        result = ((result & 0xFFFFFFFF) + b) & 0xFFFFFFFF
    return result


def checksum_add_u16_into_u16(data: [int], _byte_order) -> int:
    result = 0
    for b in data:
        result = ((result & 0xFFFF) + b) & 0xFFFF
    return result


def checksum_add_u16_into_u32(data: [int], _byte_order) -> int:
    result = 0
    for b in data:
        result = ((result & 0xFFFFFFFF) + b) & 0xFFFFFFFF
    return result


def checksum_add_u32_into_u32(data: [int], _byte_order) -> int:
    result = 0
    for b in data:
        result = ((result & 0xFFFFFFFF) + b) & 0xFFFFFFFF
    return result


def checksum_crc16(data: [int], _byte_order) -> int:
    f = crcmod.predefined.mkPredefinedCrcFun('crc-16')
    return f(bytearray(data))


def checksum_crc16_citt(data: [int], _byte_order) -> int:
    f = crcmod.predefined.mkPredefinedCrcFun('crc-ccitt-false')
    return f(bytearray(data))


def checksum_crc32(data: [int], _byte_order) -> int:
    f = crcmod.predefined.mkPredefinedCrcFun('crc-32')
    return f(bytearray(data))


@pytest.mark.parametrize('ag, checksum_type, checksum_type_int, function', [
    pytest.param('BYTE', 'XCP_ADD_11', 0x01, checksum_add_u8_into_u8, id='XCP_ADD_11'),
    pytest.param('BYTE', 'XCP_ADD_12', 0x02, checksum_add_u8_into_u16, id='XCP_ADD_12'),
    pytest.param('BYTE', 'XCP_ADD_14', 0x03, checksum_add_u8_into_u32, id='XCP_ADD_14'),
    pytest.param('WORD', 'XCP_ADD_22', 0x04, checksum_add_u16_into_u16, id='XCP_ADD_22'),
    pytest.param('WORD', 'XCP_ADD_24', 0x05, checksum_add_u16_into_u32, id='XCP_ADD_24'),
    pytest.param('DWORD', 'XCP_ADD_44', 0x06, checksum_add_u32_into_u32, id='XCP_ADD_44'),
    pytest.param('BYTE', 'XCP_CRC_16', 0x07, checksum_crc16, id='XCP_CRC_16'),
    pytest.param('BYTE', 'XCP_CRC_16_CITT', 0x08, checksum_crc16_citt, id='XCP_CRC_16_CITT'),
    pytest.param('BYTE', 'XCP_CRC_32', 0x09, checksum_crc32, id='XCP_CRC_32')
])
@pytest.mark.parametrize('block_size', [pytest.param(v, id='block_size = {:04}d'.format(v)) for v in [1, 2, 3, 1000]])
@pytest.mark.parametrize('mta', mtas)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_returns_expected_checksum_on_a_single_block(ag,
                                                                    checksum_type,
                                                                    checksum_type_int,
                                                                    function,
                                                                    block_size,
                                                                    mta,
                                                                    byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   byte_order=byte_order,
                                   checksum_type=checksum_type))

    element_size = element_size_from_address_granularity(ag)
    expected_block = generate_random_block_content(block_size, element_size, mta)
    expected_block_generator = (v for v in expected_block)

    def read_slave_memory(p_address, _extension, p_buffer):
        expected_address, expected_value = next(expected_block_generator)
        assert int(handle.ffi.cast('uint32_t', p_address)) == expected_address
        raw = expected_value.to_bytes(element_size, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order],
                                      signed=False)
        for i, b in enumerate(raw):
            p_buffer[i] = int(b)
        return None

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_MTA
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                  0x00,
                                                                  0x00,
                                                                  0x00,
                                                                  *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                  0x00,
                                                                  0x00,
                                                                  0x00,
                                                                  *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check checksum type.
    assert raw_data[1] == checksum_type_int

    # check reserved bytes.
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00

    # check checksum value.
    actual_checksum = u32_from_array(bytearray(raw_data[4:8]), byte_order)
    expected_checksum = function([v[1] for v in expected_block], byte_order)
    assert actual_checksum == expected_checksum


@pytest.mark.parametrize('ag', [pytest.param('BYTE', id='XCP_USER_DEFINED')])
@pytest.mark.parametrize('block_size', [pytest.param(v, id='block_size = {:04}d'.format(v)) for v in [1, 2, 3, 1000]])
@pytest.mark.parametrize('mta', mtas)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_user_defined_returns_expected_checksum_on_a_single_block(ag,
                                                                                 block_size,
                                                                                 mta,
                                                                                 byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   byte_order=byte_order,
                                   checksum_type='XCP_USER_DEFINED',
                                   user_defined_checksum_function='Xcp_UserDefinedChecksumFunction'))

    element_size = element_size_from_address_granularity(ag)

    def xcp_user_defined_checksum_function(_p_lower_address, p_upper_address, p_checksum):
        p_checksum[0] = int.from_bytes(bytearray((1, 2, 3, 4)),
                                       dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order],
                                       signed=False)
        return p_upper_address

    handle.xcp_user_defined_checksum_function.side_effect = xcp_user_defined_checksum_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_MTA
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                  0x00,
                                                                  0x00,
                                                                  0x00,
                                                                  *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                  0x00,
                                                                  0x00,
                                                                  0x00,
                                                                  *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check checksum type.
    assert raw_data[1] == 0xFF

    # check reserved bytes.
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00

    # check checksum.
    expected_checksum = u32_from_array(bytearray((1, 2, 3, 4)), byte_order)
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == expected_checksum

    # check checksum value.
    handle.xcp_user_defined_checksum_function.assert_called_once_with(handle.ffi.cast('void *', mta),
                                                                      handle.ffi.cast('void *', mta + element_size * block_size),
                                                                      ANY)


def test_build_checksum_calls_the_det_with_err_param_pointer_if_checksum_function_is_null():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_USER_DEFINED',
                                   user_defined_checksum_function=None))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))

    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_PARAM_POINTER'))


def test_build_checksum_returns_err_cmd_unknown_if_checksum_function_is_null():
    """XCP part 2 - Protocol Layer Specification 1.1/1.7.3.1 defines ERR_OUT_OF_RANGE as "command
    syntax valid but command parameter(s) out of range". Here the master's parameters are valid and
    the SLAVE is misconfigured, so 0x22 misattributes the fault and its matrix action, "retry other
    parameter", points the master at a fix that cannot exist.

    ERR_CMD_UNKNOWN is "unknown command or not implemented optional command", action "display
    error" -- terminal rather than futile, already in this command's 1.1/1.7.3.2.1 row so no
    deviation is recorded, and already this module's answer for an unavailable BUILD_CHECKSUM (see
    asam_error_matrix_test.py's TestBuildChecksumErrorHandling::test_returns_err_cmd_unknown, which
    builds with xcp_build_checksum_api_enable=False and asserts exactly this). A configured-but-
    unusable checksum function is that same unavailability, found at run time. DD118.

    SduLength is asserted because 0x20 carries no payload: 1.1/1.1.3.3 attaches additional
    information to 0x22 and 0x31 only.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_USER_DEFINED',
                                   user_defined_checksum_function=None))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = handle.can_if_transmit.call_args[0][1]

    assert tuple(response.SduDataPtr[0:2]) == (0xFE, 0x20)
    assert response.SduLength == 2


def test_build_checksum_returns_err_cmd_unknown_if_checksum_type_is_out_of_range():
    """The sibling condition: a configured checksum type that maps to no ASAM wire value reaches
    Xcp_DTOCmdStdBuildChecksum's `default:` case and its 0x0A sentinel. Same reasoning as above --
    the master's request is well formed and the slave cannot serve it. DD118.

    checksum_type is passed as an int rather than one of the schema's enum strings, which is how
    this test reaches that default case at all.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, checksum_type=0xFF, user_defined_checksum_function=None))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = handle.can_if_transmit.call_args[0][1]

    assert tuple(response.SduDataPtr[0:2]) == (0xFE, 0x20)
    assert response.SduLength == 2


# XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9 publishes a 32-byte test pattern and the
# result each algorithm must produce over it. 1.0 carries no such table at all -- these values exist
# only in 1.1. The tests above compare the module against the checksum_* helpers at the top of this
# file, which verifies that two implementations agree; it cannot catch a misunderstanding they
# share. These are external reference values, so they can. Design doc DD120.
#
# The 1.1 PDF is a scanned OCR dump and this table is damaged in it ("Ay10", "CHIT", "OxC/76A"), so
# every value below was recomputed from the pattern and the specification's own CRC parameters
# (poly, init, refin, refout, xorout) and kept only where the recomputation and the reading agreed.
# All nine agreed, on both byte orders.
SPEC_TEST_PATTERN = tuple(range(0x01, 0x11)) + tuple(range(0xF1, 0x100)) + (0x00,)

# The result is always a DWORD regardless of algorithm (1.1/1.6.1.2.9), so the narrower sums are
# written here zero-extended to 32 bits -- that is what Xcp_BuildChecksum*'s `*pResult = (uint32)crc`
# produces and what the response carries in bytes 4..7.
SPEC_VECTORS = (
    # address_granularity, checksum_type,     wire type, LITTLE_ENDIAN (Intel), BIG_ENDIAN (Motorola)
    pytest.param('BYTE', 'XCP_ADD_11', 0x01, 0x00000010, 0x00000010, id='XCP_ADD_11'),
    pytest.param('BYTE', 'XCP_ADD_12', 0x02, 0x00000F10, 0x00000F10, id='XCP_ADD_12'),
    pytest.param('BYTE', 'XCP_ADD_14', 0x03, 0x00000F10, 0x00000F10, id='XCP_ADD_14'),
    pytest.param('WORD', 'XCP_ADD_22', 0x04, 0x00001800, 0x00000710, id='XCP_ADD_22'),
    pytest.param('WORD', 'XCP_ADD_24', 0x05, 0x00071800, 0x00080710, id='XCP_ADD_24'),
    pytest.param('DWORD', 'XCP_ADD_44', 0x06, 0x140C03F8, 0xFC040B10, id='XCP_ADD_44'),
    pytest.param('BYTE', 'XCP_CRC_16', 0x07, 0x0000C76A, 0x0000C76A, id='XCP_CRC_16'),
    pytest.param('BYTE', 'XCP_CRC_16_CITT', 0x08, 0x00009D50, 0x00009D50, id='XCP_CRC_16_CITT'),
    pytest.param('BYTE', 'XCP_CRC_32', 0x09, 0x89CD97CE, 0x89CD97CE, id='XCP_CRC_32'),
)


@pytest.mark.parametrize('ag, checksum_type, checksum_type_int, expected_little, expected_big',
                         SPEC_VECTORS)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_matches_the_specification_reference_vectors(ag,
                                                                    checksum_type,
                                                                    checksum_type_int,
                                                                    expected_little,
                                                                    expected_big,
                                                                    byte_order):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9's own validation tables.

    The pattern is a BYTE STREAM, not a list of element values: the mock places those 32 bytes in
    memory verbatim and lets the configured granularity and byte order decide what elements they
    form. That is exactly what makes XCP_ADD_22, XCP_ADD_24 and XCP_ADD_44 differ between the
    Intel and Motorola columns, and why the other six do not.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   byte_order=byte_order,
                                   checksum_type=checksum_type))

    mta = 0xDEADBEEF
    element_size = element_size_from_address_granularity(ag)
    block_size = len(SPEC_TEST_PATTERN) // element_size
    expected = expected_little if byte_order == 'LITTLE_ENDIAN' else expected_big

    def read_slave_memory(p_address, _extension, p_buffer):
        offset = int(handle.ffi.cast('uint32_t', p_address)) - mta
        for i in range(element_size):
            p_buffer[i] = SPEC_TEST_PATTERN[offset + i]
        return None

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_MTA
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    assert raw_data[0] == 0xFF
    assert raw_data[1] == checksum_type_int
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == expected


def _connect_and_set_mta(handle, mta, byte_order):
    """CONNECT then SET_MTA, the preamble every BUILD_CHECKSUM test needs."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


@pytest.mark.parametrize('block_size', [pytest.param(0, id='block_size = 0'),
                                        pytest.param(1001, id='block_size = max + 1')])
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_out_of_range_carries_the_maximum_block_size(block_size, byte_order):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9's negative response: byte 0 0xFE,
    byte 1 the error code, bytes 2,3 a reserved WORD, bytes 4..7 the maximum block size as a DWORD.
    1.1/1.1.3.3 conditions that payload on the pair (BUILD_CHECKSUM, 0x22) and names no trigger, so
    both out-of-range conditions carry it, not only the one 1.6.1.2.9's prose names (DD117).

    SduLength is asserted because this suite's pervasive SduDataPtr[0:2] idiom cannot see a payload
    at all: without it this test would pass whether or not the DWORD is ever written.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   checksum_max_block_size=1000))

    _connect_and_set_mta(handle, 0xDEADBEEF, byte_order)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()

    response = handle.can_if_transmit.call_args[0][1]
    raw_data = tuple(response.SduDataPtr[0:8])

    assert raw_data[0:2] == (0xFE, 0x22)
    assert response.SduLength == 8
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == 1000


@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_accepts_a_block_size_equal_to_the_maximum(byte_order):
    """The off-by-one guard: the bound is inclusive, so max itself must still be answered."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   checksum_max_block_size=4))

    handle.xcp_read_slave_memory_u8.side_effect = lambda _a, _e, p_buffer: p_buffer.__setitem__(0, 0x01)

    _connect_and_set_mta(handle, 0xDEADBEEF, byte_order)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(4, byte_order))))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_does_not_advance_the_mta_when_it_refuses(byte_order):
    """1.1/1.6.1.2.9 post-increments the MTA by the block size, and only a successful checksum may
    do so. A rejected request that advanced it would silently desynchronise the master: the next
    command would read from somewhere the master never asked for."""
    mta = 0xDEADBEEF
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   checksum_max_block_size=1000))

    handle.xcp_read_slave_memory_u8.side_effect = lambda _a, _e, p_buffer: p_buffer.__setitem__(0, 0x01)

    _connect_and_set_mta(handle, mta, byte_order)

    # refused: over the bound
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(1001, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.xcp_read_slave_memory_u8.reset_mock()

    # accepted: the first address it reads is where the MTA still is
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(1, byte_order))))
    handle.lib.Xcp_MainFunction()

    first_address = handle.xcp_read_slave_memory_u8.call_args_list[0][0][0]
    assert int(handle.ffi.cast('uint32_t', first_address)) == mta


def test_generation_refuses_a_checksum_max_block_size_that_would_overflow():
    """script/source_cfg.c.jinja2 refuses a bound whose product with the address granularity would
    not fit a uint32. The runtime check in Xcp_DTOCmdStdBuildChecksum guarantees
    block_size <= checksumMaxBlockSize; this guarantees checksumMaxBlockSize * element_size fits,
    and together they make element_size * block_size unable to overflow. DD119.

    A constraint between two configuration fields, which is why it lives here and not in
    config/xcp.schema.json: JSON Schema cannot express it.

    Ungated on xcp_build_checksum_api_enable, following the rule the sector Length mod AG guard's
    own comment states -- a check on whether the CONFIGURATION means anything, not a decision about
    what to emit. Gating it would let a broken configuration ship silently and fail only for
    whoever enabled the command later.
    """
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                              address_granularity='DWORD',
                              checksum_max_block_size=0x40000000))


def test_generation_accepts_the_largest_checksum_max_block_size_that_fits():
    """The companion the rejection above needs to mean anything. `raise` is a deliberately-undefined
    Jinja global, so EVERY guard in that template surfaces the identical "'raise' is undefined" --
    pytest.raises(UndefinedError) alone cannot show which guard fired, or that the configuration was
    not refused for some unrelated reason. 0x3FFFFFFF * 4 is 0xFFFFFFFC, the largest product that
    still fits, and the same configuration generates cleanly."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                          address_granularity='DWORD',
                          checksum_max_block_size=0x3FFFFFFF))

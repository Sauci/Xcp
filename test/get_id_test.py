#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('mode, actual_identification, expected_identification', [
    (0x00, '/path/to/database.a2l', '/path/to/database.a2l')])
def test_get_id_returns_identification_through_mta_when_mode_is_0(byte_order,
                                                                  mode,
                                                                  actual_identification,
                                                                  expected_identification):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   byte_order=byte_order,
                                   identification=actual_identification))

    memory_identification = []

    def read_slave_memory(p_address, _extension, _p_buffer):
        memory_identification.append(handle.ffi.cast('uint8_t*', p_address)[0])

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_ID
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, mode)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check the response Mode bit mask. XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2
    # makes this byte a bit mask -- TRANSFER_MODE at bit 0, COMPRESSED_ENCRYPTED at bit 1, bits 2-7
    # don't-care. 1.0/1.6.1.2.2 has the same byte and leaves it unnamed, which is why this was
    # previously read as an echo of the request's Requested Identification Type. It is not one:
    # request byte 1 and response byte 1 are different fields that both happen to be 0 here. The
    # old `assert raw_data[1] == mode` pinned the right value only because this test's parametrize
    # list has one row at zero; it would demand a wrong thing -- that the response echo the
    # request -- as soon as a second identification type is covered.
    # Both bits clear: the slave transfers through the MTA and does not compress (DD111).
    assert raw_data[1] & 0x01 == 0x00, 'TRANSFER_MODE must be clear: this slave points the MTA'
    assert raw_data[1] & 0x02 == 0x00, 'COMPRESSED_ENCRYPTED must be clear: nothing is compressed'
    assert raw_data[1] == 0x00, 'no reserved bit of the Mode mask may be set'

    # check reserved bytes.
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00

    # check Length.
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == len(expected_identification)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, len(expected_identification))))
    for _ in range(int(math.ceil(len(expected_identification) / 7))):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # check Identification.
    assert ''.join(chr(c) for c in memory_identification) == expected_identification


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_id_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, 0x00)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x08))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0x08:max_cto]) == remaining_zeros


def _connect(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def _get_id(handle, identification_type):
    """Issue GET_ID and return the response bytes, read immediately after the transmit call."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, identification_type)))
    handle.lib.Xcp_MainFunction()
    raw = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return raw


@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('identification_type', (0x01, 0x02, 0x03, 0x04, 0x80, 0xFF))
def test_get_id_reports_length_zero_for_a_defined_type_it_does_not_serve(byte_order,
                                                                        identification_type):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 (1.0/1.6.1.2.2, identical wording):
    "If length is 0, the requested identification type is not available." That is GET_ID's own
    in-band way of declining, and it exists so a master can enumerate what a slave supports without
    provoking errors. Types 1-4 and 128-255 are all types 1.1 defines as requestable, so naming one
    is a valid parameter even on a slave with nothing to return for it -- DD110.

    Type 255 is covered here deliberately: the ERR_OUT_OF_RANGE test this replaces ranged over
    range(0x01, 0xFF), which stops at 254, so the top of the user-defined range was never exercised.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, byte_order=byte_order))
    _connect(handle)

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0] == 0xFF, 'a declined type is still a positive response, not an error packet'
    assert raw_data[1] == 0x00, 'Mode: TRANSFER_MODE and COMPRESSED_ENCRYPTED both clear'
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == 0, 'Length must be 0'


@pytest.mark.parametrize('identification_type', (0x05, 0x40, 0x7F))
def test_get_id_rejects_a_type_the_specification_does_not_define(identification_type):
    """1.1/1.6.1.2.2 lists exactly 0, 1, 2, 3, 4 and 128..255 as the types that "may be requested".
    5..127 name no identification type at all, so a master sending one has supplied an out-of-range
    parameter -- which is what keeps 1.1/1.7.3.2.1's GET_ID ERR_OUT_OF_RANGE row reachable, given
    that the identification type is GET_ID's only parameter. DD110."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    _connect(handle)

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0:2] == (0xFE, 0x22), 'expected ERR_OUT_OF_RANGE'


def _set_mta(handle, address_bytes, extension=0x00):
    """SET_MTA. Copy the exact framing from test/session_teardown_test.py, which already issues a
    SET_MTA(0xDEADBEEF) for the neighbouring DD75 case -- do not reconstruct the byte order here."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
        (0xF6, 0x00, 0x00, extension) + address_bytes))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def _upload_addresses(handle, element_count):
    """Issue UPLOAD and return the raw pointers Xcp_ReadSlaveMemory was asked to read.

    Returns cdata pointers, not integers: the harness idiom for "is this pointer null" is a direct
    comparison against handle.ffi.NULL (test/clear_daq_list_test.py:40), which needs no cast to an
    integer type the cdef may not carry.
    """
    addresses = []
    handle.xcp_read_slave_memory_u8.side_effect = \
        lambda p_address, _extension, _p_buffer: addresses.append(p_address)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, element_count)))
    handle.lib.Xcp_MainFunction()
    return addresses


def test_a_length_zero_get_id_does_not_leave_an_earlier_set_mta_standing():
    """DD113. A declined GET_ID must not leave an earlier SET_MTA's pointer in place: a master that
    ignores Length = 0 and uploads anyway would then read through a pointer the slave never set for
    this purpose -- the defect DD75 fixed for the extension half of the same pair, arriving the
    other way round.

    Paired with its own positive control below. "This address was never read" is vacuous alone: such
    a test passes just as happily if UPLOAD read nothing at all, or if SET_MTA never worked. The
    control shows the same SET_MTA address IS reached when no GET_ID intervenes, so the difference
    here is caused by GET_ID and by nothing else. test/session_teardown_test.py uses the same
    pairing for the neighbouring DD75 case.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    _connect(handle)
    _set_mta(handle, (0xEF, 0xBE, 0xAD, 0xDE))

    _get_id(handle, 0x03)   # a type 1.1/1.6.1.2.2 defines but this slave does not serve

    addresses = _upload_addresses(handle, 0x01)

    assert addresses, 'UPLOAD read no memory at all -- see the note below before changing this'
    assert addresses[0] == handle.ffi.NULL, \
        'a Length = 0 GET_ID left the earlier SET_MTA standing for the following UPLOAD'


def test_an_upload_with_no_intervening_get_id_still_reads_the_set_mta_address():
    """The positive control for the test above: same SET_MTA, same UPLOAD, no GET_ID between them.
    If this ever fails, the absence the test above asserts proves nothing."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    _connect(handle)
    _set_mta(handle, (0xEF, 0xBE, 0xAD, 0xDE))

    addresses = _upload_addresses(handle, 0x01)

    assert addresses, 'setup: UPLOAD must read memory'
    assert addresses[0] != handle.ffi.NULL, \
        'setup: UPLOAD must reach the address SET_MTA just set, or the paired test is vacuous'

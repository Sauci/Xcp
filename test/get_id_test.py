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

    # check Mode.
    assert raw_data[1] == mode

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

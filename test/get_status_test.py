#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('current_session_status_byte, current_session_status', ((0b00000000, 0b00000000),
                                                                                 (0b00000001, 0b00000001),
                                                                                 (0b00000100, 0b00000100),
                                                                                 (0b00001000, 0b00001000),
                                                                                 (0b00001000, 0b00001010),
                                                                                 (0b00001000, 0b00011000),
                                                                                 (0b00001000, 0b00101000),
                                                                                 (0b00001000, 0b01001000),
                                                                                 (0b00001000, 0b10001000),))
def test_get_status_sets_the_current_session_status_byte_to_active_session_status(current_session_status_byte,
                                                                                  current_session_status):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, current_session_status, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] == current_session_status_byte


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_status_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x06))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[6:max_cto]) == remaining_zeros

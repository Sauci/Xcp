#!/usr/bin/env python
# -*- coding: utf-8 -*-


from .parameter import *
from .conftest import XcpTest


def test_command_disconnect_sets_the_packet_id_byte_to_pid_response_on_positive_response():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_disconnect_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x01))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[1:max_cto]) == remaining_zeros

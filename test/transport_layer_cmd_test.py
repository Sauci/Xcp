#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('rx_pdu_ref, tx_pdu_ref', [(0x0001, 0x0002), (0xFFFE, 0xFFFF)])
@pytest.mark.parametrize('mode, xcp_tag', [pytest.param(0, [0x58, 0x43, 0x50], id='mode=echo'),
                                           pytest.param(1, [0xA7, 0xBC, 0xAF], id='mode=inversed echo')])
@pytest.mark.parametrize('byte_order', byte_orders)
def test_transport_layer_cmd_sub_command_get_slave_can_identifier_returns_expected_data(rx_pdu_ref, tx_pdu_ref,
                                                                                        mode,
                                                                                        xcp_tag,
                                                                                        byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=rx_pdu_ref,
                                   channel_tx_pdu_ref=tx_pdu_ref,
                                   byte_order=byte_order))
    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(rx_pdu_ref, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(rx_pdu_ref, handle.define('E_OK'))

    # TRANSPORT_LAYER_CMD
    handle.lib.Xcp_CanIfRxIndication(rx_pdu_ref, handle.get_pdu_info((0xF2, 0xFF, 0x58, 0x43, 0x50, mode)))
    handle.lib.Xcp_MainFunction()

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check XCP tag.
    assert list(raw_data[1:4]) == xcp_tag

    # check CAN identifier for CMD/STIM.
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == rx_pdu_ref


@pytest.mark.parametrize('daq_list_number, daq_pdu_ref', [(0x0000, 0x0001), (0x0000, 0x0003)])
@pytest.mark.parametrize('byte_order', byte_orders[0:1])
def test_transport_layer_cmd_sub_command_get_daq_list_can_identifier_returns_expected_data(daq_list_number,
                                                                                           daq_pdu_ref,
                                                                                           byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   daqs=(dict(name='DAQ1',
                                              type='DAQ',
                                              max_odt=1,
                                              max_odt_entries=1,
                                              pdu_mapping=daq_pdu_ref,
                                              dtos=[dict(pid=0)]),)))
    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # TRANSPORT_LAYER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
        (0xF2, 0xFE) + tuple(u16_to_array(daq_list_number, byte_order))))
    handle.lib.Xcp_MainFunction()

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check CAN ID fixed.
    assert raw_data[1] == 0x01

    # check reserved bytes.
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00

    # check DAQ CAN identifier of DTO dedicated to list number.
    print(u32_from_array(bytearray(raw_data[4:8]), byte_order))
    print(daq_pdu_ref)
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == daq_pdu_ref


def test_transport_layer_cmd_sub_cmd_set_daq_list_can_identifier_returns_err_cmd_unknown():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # TRANSPORT_LAYER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF2, 0xFD, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

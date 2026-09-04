#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def exchange(handle, request, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


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


def test_get_daq_id_answers_each_allocated_dynamic_list_by_its_own_number():
    """GET_DAQ_ID scans daqList[..].number for a match (source/Xcp_Std.c), so every DAQ list has to
    carry its own index -- including a dynamically allocated one.

    The dynamic pool used to be generated with number == 0 in every slot, under a comment claiming
    ALLOC_DAQ assigned it. Nothing did. The scan therefore matched slot 0 for daq_list_number 0 and
    nothing at all for any other, so a master that had allocated four lists was told
    ERR_OUT_OF_RANGE for three of them. 0xF2 is hard-enabled and unprotected, so no configuration
    gated the failure.

    List 0 alone would not have noticed: it answers correctly under both the broken and the fixed
    generator. Every list of the pool is swept for that reason, and the out-of-pool number after it
    pins that the scan is still bounded by daqListCount rather than answering anything at all."""
    config = dynamic_config(daq_count=4, odt_count=2, odt_entries_count=2)
    handle = XcpTest(config)
    connect(handle)

    assert exchange(handle, (0xD5, 0x00, 0x04, 0x00))[0] == 0xFF, 'ALLOC_DAQ(4) was refused'

    for daq_list_number in range(4):
        answer = exchange(handle, (0xF2, 0xFE) + tuple(u16_to_array(daq_list_number, 'LITTLE_ENDIAN')))

        assert answer[0] == 0xFF, \
            'GET_DAQ_ID refused allocated DAQ list {}'.format(daq_list_number)
        # Every list of one dynamic pool shares the single pdu_mapping the daq_dynamic block names,
        # so the identifier is the same for all four -- what differs between them is only whether
        # the list is found at all.
        assert u32_from_array(bytearray(answer[4:8]), 'LITTLE_ENDIAN') == \
            config.default_daq_dto_pdu_mapping

    assert exchange(handle, (0xF2, 0xFE) + tuple(u16_to_array(0x0004, 'LITTLE_ENDIAN')))[0:2] == \
        (0xFE, 0x22), 'a list number past the pool was answered rather than refused'


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

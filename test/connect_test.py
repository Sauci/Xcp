#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pytest

from .parameter import *
from .conftest import XcpTest


def test_command_connect_sets_the_packet_id_byte_to_pid_response_on_positive_response():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('resource_cal_pag_bit, api_enable', ((0, (False, False, False, False, False)),
                                                              (0, (True, False, False, False, False)),
                                                              (0, (True, True, False, False, False)),
                                                              (0, (True, True, True, False, False)),
                                                              (0, (True, True, True, True, False)),
                                                              (1, (True, True, True, True, True))))
def test_connect_sets_the_resource_cal_pag_bit_according_to_enabled_apis(resource_cal_pag_bit, api_enable):
    # XCP part 2 - Protocol Layer Specification 1.0/1.4: if SET_CAL_PAGE is implemented,
    # GET_CAL_PAGE is required. The walk below enables one more API at each step, so
    # GET_CAL_PAGE (api_enable[3]) must come on no later than SET_CAL_PAGE (api_enable[4]) --
    # the reverse order would ask Xcp_Init for an invalid configuration, which it rightly
    # refuses to initialize (leaving Xcp_State XCP_UNINITIALIZED, and CONNECT unanswered).
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   xcp_download_api_enable=api_enable[0],
                                   xcp_download_max_api_enable=api_enable[1],
                                   xcp_short_download_api_enable=api_enable[2],
                                   xcp_get_cal_page_api_enable=api_enable[3],
                                   xcp_set_cal_page_api_enable=api_enable[4]))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & 0x01 == resource_cal_pag_bit


@pytest.mark.parametrize('resource_daq_bit, api_enable', (
        (1, (True, True, True, True, True, True)),
        (0, (False, True, True, True, True, True)),
        (0, (True, False, True, True, True, True)),
        (0, (True, True, False, True, True, True)),
        (0, (True, True, True, False, True, True)),
        (0, (True, True, True, True, False, True)),
        (0, (True, True, True, True, True, False))))
def test_connect_sets_the_resource_daq_bit_according_to_enabled_apis(resource_daq_bit, api_enable):
    """D14. 1.1/1.6.1.1.1 defines the bit as a property of the DAQ list group: CLEAR_DAQ_LIST,
    SET_DAQ_PTR, WRITE_DAQ, SET_DAQ_LIST_MODE, START_STOP_DAQ_LIST and START_STOP_SYNCH are the
    six commands an available DAQ list actually needs, so disabling any one of them individually
    (the other five, and every optional DAQ command, left at their enabled default) clears the
    bit. The eleven other DAQ commands are optional per 1.1 and do not gate it -- see
    test_the_daq_resource_bit_survives_disabling_an_optional_daq_command below, which holds all
    six of these on while disabling every optional one at once."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   xcp_clear_daq_list_api_enable=api_enable[0],
                                   xcp_set_daq_ptr_api_enable=api_enable[1],
                                   xcp_write_daq_api_enable=api_enable[2],
                                   xcp_set_daq_list_mode_api_enable=api_enable[3],
                                   xcp_start_stop_daq_list_api_enable=api_enable[4],
                                   xcp_start_stop_synch_api_enable=api_enable[5]))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & (0x01 << 0x02)) >> 0x02) == resource_daq_bit


def resource(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return handle.can_if_transmit.call_args[0][1].SduDataPtr[1]


def test_the_daq_resource_bit_survives_disabling_an_optional_daq_command():
    """D14. 1.1/1.6.1.1.1 defines the bit as "DAQ lists available", a group property. Requiring
    every optional command made an integrator's configuration switch DAQ off entirely."""
    handle = XcpTest(DefaultConfig(xcp_get_daq_clock_api_enable=False,
                                   xcp_read_daq_api_enable=False,
                                   xcp_get_daq_list_info_api_enable=False,
                                   xcp_get_daq_event_info_api_enable=False,
                                   xcp_free_daq_api_enable=False,
                                   xcp_alloc_daq_api_enable=False,
                                   xcp_alloc_odt_api_enable=False,
                                   xcp_alloc_odt_entry_api_enable=False))

    assert resource(handle) & 0x04 != 0


def test_the_daq_resource_bit_clears_without_a_mandatory_daq_command():
    handle = XcpTest(DefaultConfig(xcp_set_daq_ptr_api_enable=False))

    assert resource(handle) & 0x04 == 0


@pytest.mark.parametrize('resource_stim_bit, daq_type', ((0, "DAQ"), (1, "STIM"), (1, "DAQ_STIM")))
def test_connect_sets_the_resource_stim_bit_according_to_enabled_apis(resource_stim_bit, daq_type):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, daqs=(dict(name='DAQ1',
                                                                         type=daq_type,
                                                                         max_odt=1,
                                                                         max_odt_entries=1,
                                                                         pdu_mapping='XCP_PDU_ID_TRANSMIT',
                                                                         dtos=[dict(pid=0)]),)))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & (0x01 << 0x03)) >> 0x03) == resource_stim_bit


@pytest.mark.parametrize('resource_pgm_bit, api_enable', ((0, (False, False, False)),
                                                          (0, (True, False, False)),
                                                          (0, (True, True, False)),
                                                          (1, (True, True, True))))
def test_connect_sets_the_resource_pgm_bit_according_to_enabled_apis(resource_pgm_bit, api_enable):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   xcp_program_clear_api_enable=api_enable[0],
                                   xcp_program_api_enable=api_enable[1],
                                   xcp_program_max_api_enable=api_enable[2]))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & (0x01 << 0x04)) >> 0x04) == resource_pgm_bit


@pytest.mark.parametrize('byte_order_bit, byte_order', ((0, "LITTLE_ENDIAN"), (1, "BIG_ENDIAN")))
def test_connect_sets_the_byte_order_bit_according_to_the_configured_value(byte_order_bit, byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, byte_order=byte_order))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[2] & 0x01 == byte_order_bit


@pytest.mark.parametrize('address_granularity_bits, address_granularity', ((0, 'BYTE'), (1, 'WORD'), (2, 'DWORD')))
def test_connect_sets_the_address_granularity_bits_according_to_the_configured_value(address_granularity_bits,
                                                                                     address_granularity):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity=address_granularity))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[2] & 0x06) >> 0x01) == address_granularity_bits


@pytest.mark.parametrize('slave_block_mode_bit, slave_block_mode', ((0, False), (1, True)))
def test_connect_sets_the_slave_block_mode_bit_according_to_the_configured_value(slave_block_mode_bit,
                                                                                 slave_block_mode):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, slave_block_mode=slave_block_mode))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[2] & (0x01 << 0x06)) >> 0x06) == slave_block_mode_bit


@pytest.mark.parametrize('optional_bit, api_enable', ((0, False), (1, True)))
def test_connect_sets_the_optional_bit_according_to_enabled_apis(optional_bit, api_enable):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_get_comm_mode_info_api_enable=api_enable))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[2] & (0x01 << 0x07)) >> 0x07) == optional_bit


@pytest.mark.parametrize('max_cto_byte, max_cto', ((8, 8), (16, 16), (32, 32)))
def test_connect_sets_the_max_cto_byte_according_to_the_configured_value(max_cto_byte, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[3] == max_cto_byte


@pytest.mark.parametrize('max_dto_bytes, max_dto, byte_order', (((8, 0), 8, 'LITTLE_ENDIAN'),
                                                                ((16, 0), 16, 'LITTLE_ENDIAN'),
                                                                ((32, 0), 32, 'LITTLE_ENDIAN'),
                                                                ((0, 8), 8, 'BIG_ENDIAN'),
                                                                ((0, 16), 16, 'BIG_ENDIAN'),
                                                                ((0, 32), 32, 'BIG_ENDIAN')))
def test_connect_sets_the_max_dto_byte_according_to_the_configured_value(max_dto_bytes, max_dto, byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_dto=max_dto, byte_order=byte_order))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[4:6]) == max_dto_bytes


def test_connect_sets_the_protocol_layer_version_number_byte_according_to_the_implementation():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[6] == 0x01


def test_connect_sets_the_transport_layer_version_number_byte_according_to_the_implementation():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[7] == 0x01


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_connect_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x08))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[8:max_cto]) == remaining_zeros

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('payload', ((0xFF,),))
def test_command_connect_raises_e_asam_invalid_cto_packet_if_payload_size_is_too_short(payload):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_ASAM_CMD_SYNTAX'))


@pytest.mark.parametrize('mode', range(0x02, 0xFF))
def test_command_connect_raises_e_asam_invalid_cto_parameter_if_a_parameter_is_not_in_allowed_range(mode):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, mode)))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_ASAM_OUT_OF_RANGE'))


@pytest.mark.parametrize('resource_cal_pag_bit, api_enable', ((0, (False, False, False, False, False)),
                                                              (0, (True, False, False, False, False)),
                                                              (0, (True, True, False, False, False)),
                                                              (0, (True, True, True, False, False)),
                                                              (0, (True, True, True, True, False)),
                                                              (1, (True, True, True, True, True))))
def test_command_connect_sets_the_resource_cal_pag_bit_according_to_enabled_apis(resource_cal_pag_bit, api_enable):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   xcp_download_api_enable=api_enable[0],
                                   xcp_download_max_api_enable=api_enable[1],
                                   xcp_short_download_api_enable=api_enable[2],
                                   xcp_set_cal_page_api_enable=api_enable[3],
                                   xcp_get_cal_page_api_enable=api_enable[4]))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.can_if_transmit.assert_called_once()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & 0x01 == resource_cal_pag_bit


@pytest.mark.parametrize('resource_daq_bit, api_enable', (
        (0, (
                False, False, False, False, False, False, False, False, False, False, False, False, False, False, False,
                False,
                False)),
        (0, (
                True, False, False, False, False, False, False, False, False, False, False, False, False, False, False,
                False,
                False)),
        (0, (
                True, True, False, False, False, False, False, False, False, False, False, False, False, False, False,
                False,
                False)),
        (0, (
                True, True, True, False, False, False, False, False, False, False, False, False, False, False, False,
                False,
                False)),
        (0, (True, True, True, True, False, False, False, False, False, False, False, False, False, False, False, False,
             False)),
        (0, (True, True, True, True, True, False, False, False, False, False, False, False, False, False, False, False,
             False)),
        (0, (True, True, True, True, True, True, False, False, False, False, False, False, False, False, False, False,
             False)),
        (0, (True, True, True, True, True, True, True, False, False, False, False, False, False, False, False, False,
             False)),
        (0, (
                True, True, True, True, True, True, True, True, False, False, False, False, False, False, False, False,
                False)),
        (0, (
                True, True, True, True, True, True, True, True, True, False, False, False, False, False, False, False,
                False)),
        (0,
         (True, True, True, True, True, True, True, True, True, True, False, False, False, False, False, False, False)),
        (0,
         (True, True, True, True, True, True, True, True, True, True, True, False, False, False, False, False, False)),
        (
                0, (True, True, True, True, True, True, True, True, True, True, True, True, False, False, False, False,
                    False)),
        (0, (True, True, True, True, True, True, True, True, True, True, True, True, True, False, False, False, False)),
        (0, (True, True, True, True, True, True, True, True, True, True, True, True, True, True, False, False, False)),
        (0, (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, False, False)),
        (0, (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, False)),
        (1, (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, True))))
def test_command_connect_sets_the_resource_daq_bit_according_to_enabled_apis(resource_daq_bit, api_enable):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   xcp_clear_daq_list_api_enable=api_enable[0],
                                   xcp_set_daq_ptr_api_enable=api_enable[1],
                                   xcp_write_daq_api_enable=api_enable[2],
                                   xcp_set_daq_list_mode_api_enable=api_enable[3],
                                   xcp_get_daq_list_mode_api_enable=api_enable[4],
                                   xcp_start_stop_daq_list_api_enable=api_enable[5],
                                   xcp_start_stop_synch_api_enable=api_enable[6],
                                   xcp_get_daq_clock_api_enable=api_enable[7],
                                   xcp_read_daq_api_enable=api_enable[8],
                                   xcp_get_daq_processor_info_api_enable=api_enable[9],
                                   xcp_get_daq_resolution_info_api_enable=api_enable[10],
                                   xcp_get_daq_list_info_api_enable=api_enable[11],
                                   xcp_get_daq_event_info_api_enable=api_enable[12],
                                   xcp_free_daq_api_enable=api_enable[13],
                                   xcp_alloc_daq_api_enable=api_enable[14],
                                   xcp_alloc_odt_api_enable=api_enable[15],
                                   xcp_alloc_odt_entry_api_enable=api_enable[16]))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.can_if_transmit.assert_called_once()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & (0x01 << 0x02)) >> 0x02) == resource_daq_bit


@pytest.mark.parametrize('resource_stim_bit, daq_type', ((0, "DAQ"), (1, "STIM"), (1, "DAQ_STIM")))
def test_command_connect_sets_the_resource_stim_bit_according_to_enabled_apis(resource_stim_bit, daq_type):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, daq_type=daq_type))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.can_if_transmit.assert_called_once()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & (0x01 << 0x03)) >> 0x03) == resource_stim_bit


@pytest.mark.parametrize('resource_pgm_bit, api_enable', ((0, (False, False, False)),
                                                          (0, (True, False, False)),
                                                          (0, (True, True, False)),
                                                          (1, (True, True, True))))
def test_command_connect_sets_the_resource_cal_pag_bit_according_to_enabled_apis(resource_pgm_bit, api_enable):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   xcp_program_clear_api_enable=api_enable[0],
                                   xcp_program_api_enable=api_enable[1],
                                   xcp_program_max_api_enable=api_enable[2]))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.can_if_transmit.assert_called_once()
    assert ((handle.can_if_transmit.call_args[0][1].SduDataPtr[1] & (0x01 << 0x04)) >> 0x04) == resource_pgm_bit

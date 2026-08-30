#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('pid', tuple(range(0xC0, 0xD3)))
def test_unimplemented_commands_return_err_cmd_unknown(pid):
    """XCP part 2 - Protocol Layer Specification 1.0/1.4: an attempt to execute a not implemented
    optional command will return ERR_CMD_UNKNOWN and does not have any effect.
    XCP part 2 - Protocol Layer Specification 1.0/1.1.5.1: 0xC0..0xFF are all CMD identifiers;
    there is no DAQ identifier range from master to slave."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)


@pytest.mark.parametrize('pid, flag', ((0xEF, 'xcp_download_next_api_enable'),
                                       (0xEC, 'xcp_modify_bits_api_enable'),
                                       (0xE9, 'xcp_get_pag_processor_info_api_enable'),
                                       (0xE8, 'xcp_get_segment_info_api_enable'),
                                       (0xE7, 'xcp_get_page_info_api_enable'),
                                       (0xE6, 'xcp_set_segment_mode_api_enable'),
                                       (0xE5, 'xcp_get_segment_mode_api_enable'),
                                       (0xE4, 'xcp_copy_cal_page_api_enable')))
def test_disabled_optional_commands_return_err_cmd_unknown(pid, flag):
    """XCP part 2 - Protocol Layer Specification 1.0/1.4"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=8,
                                   segments=[segment(pages=[page()])],
                                   **{flag: False}))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

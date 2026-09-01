#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('pid', tuple(pid for pid in range(0xC0, 0xE4) if pid not in (0xDA, 0xDD, 0xDE, 0xDF, 0xE0, 0xE1, 0xE2, 0xE3)))
def test_unimplemented_commands_return_err_cmd_unknown(pid):
    """XCP part 2 - Protocol Layer Specification 1.0/1.4: an attempt to execute a not implemented
    optional command will return ERR_CMD_UNKNOWN and does not have any effect.
    XCP part 2 - Protocol Layer Specification 1.0/1.1.5.1: 0xC0..0xFF are all CMD identifiers;
    there is no DAQ identifier range from master to slave.

    Covers 0xC0..0xE3: the reserved range, the PGM group and the DAQ group, none of which this
    module implements. The DAQ half used to stop at 0xD2, so the seventeen DAQ PIDs went
    untested while their handlers returned E_OK without ever filling the response buffer -- the
    slave transmitted whatever the previous command had left in it.

    0xDA (GET_DAQ_PROCESSOR_INFO), 0xDD (START_STOP_SYNCH), 0xDE (START_STOP_DAQ_LIST), 0xDF
    (GET_DAQ_LIST_MODE), 0xE0 (SET_DAQ_LIST_MODE), 0xE1 (WRITE_DAQ), 0xE2 (SET_DAQ_PTR) and 0xE3
    (CLEAR_DAQ_LIST) are excluded: all eight are implemented now, and
    get_daq_processor_info_test.py, start_stop_synch_test.py, start_stop_daq_list_test.py,
    get_daq_list_mode_test.py, set_daq_list_mode_test.py, write_daq_test.py, set_daq_ptr_test.py
    and clear_daq_list_test.py cover them."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
    connect(handle)

    # call_args holds the live pointer into the response buffer, not a snapshot, so a slave that
    # filled the error packet but never transmitted it would still satisfy the byte assertion.
    # Reset first and count the call, as the sibling command tests do.
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
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

    # call_args holds the live pointer into the response buffer, not a snapshot, so a slave that
    # filled the error packet but never transmitted it would still satisfy the byte assertion.
    # Reset first and count the call, as the sibling command tests do.
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)


@pytest.mark.parametrize('stim_pid', (0x00, 0x01, 0x7F, 0xBF))
def test_identifiers_below_the_command_range_are_answered_with_silence(stim_pid):
    """XCP part 2 - Protocol Layer Specification 1.0/1.1.5.1: master to slave, 0x00..0xBF is an
    absolute or relative ODT number for STIM, not a command.

    The companion of the two tests above. Those PIDs carry the is-CTO bit clear, so they reach
    the DTO branch, which transmits nothing. That branch sits immediately beside the one that
    answers a disabled command, and the two are one `else` apart: a fix to either that is
    written a scope too high would make the slave answer STIM frames. Nothing else in the suite
    pins this.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
    connect(handle)

    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((stim_pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 0

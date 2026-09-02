#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=2),
                                         daq(name='DAQ2', max_odt=1, max_odt_entries=2)),
                                   **kwargs))
    connect(handle)
    return handle


def exchange(handle, request, length=2):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def configure(handle, daq_list):
    exchange(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) + (0x00, 0x00))
    exchange(handle, (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))


def select(handle, daq_list):
    exchange(handle, (0xDE, 0x02) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')))


def mode_of(handle, daq_list):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[daq_list].mode


def test_start_selected_starts_only_the_selected_lists():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.5"""
    handle = daq_handle()
    configure(handle, 0)
    configure(handle, 1)
    select(handle, 1)

    assert exchange(handle, (0xDD, 0x01))[0] == 0xFF

    assert mode_of(handle, 0) & 0x40 == 0  # XCP_DAQ_LIST_MODE_RUNNING
    assert mode_of(handle, 1) & 0x40 != 0  # XCP_DAQ_LIST_MODE_RUNNING


def test_start_selected_clears_the_selected_flag():
    """1.1/1.6.4.1.1.5: "The slave device software has to reset the mode SELECTED of a DAQ list
    after successful execution of a START_STOP_SYNCH"."""
    handle = daq_handle()
    configure(handle, 0)
    select(handle, 0)

    exchange(handle, (0xDD, 0x01))

    assert mode_of(handle, 0) & 0x01 == 0  # XCP_DAQ_LIST_MODE_SELECTED


def test_stop_all_stops_every_list_selected_or_not():
    handle = daq_handle()
    configure(handle, 0)
    configure(handle, 1)
    exchange(handle, (0xDE, 0x01, 0x00, 0x00))
    exchange(handle, (0xDE, 0x01, 0x01, 0x00))

    assert exchange(handle, (0xDD, 0x00))[0] == 0xFF

    assert mode_of(handle, 0) & 0x40 == 0  # XCP_DAQ_LIST_MODE_RUNNING
    assert mode_of(handle, 1) & 0x40 == 0  # XCP_DAQ_LIST_MODE_RUNNING


def test_stop_all_clears_the_selected_flag_too():
    """1.1/1.6.4.1.1.5's SELECTED reset is not special-cased to START_SELECTED: "The slave device
    software has to reset the mode SELECTED of a DAQ list after successful execution of a
    START_STOP_SYNCH" -- stop-all is such an execution too, even for a list that was selected but
    whose selection stop-all otherwise ignores (it stops every list, not only selected ones)."""
    handle = daq_handle()
    configure(handle, 0)
    select(handle, 0)

    exchange(handle, (0xDD, 0x00))

    assert mode_of(handle, 0) & 0x01 == 0  # XCP_DAQ_LIST_MODE_SELECTED


def test_stop_selected_leaves_unselected_lists_running():
    handle = daq_handle()
    configure(handle, 0)
    configure(handle, 1)
    exchange(handle, (0xDE, 0x01, 0x00, 0x00))
    exchange(handle, (0xDE, 0x01, 0x01, 0x00))
    select(handle, 1)

    exchange(handle, (0xDD, 0x02))

    assert mode_of(handle, 0) & 0x40 != 0  # XCP_DAQ_LIST_MODE_RUNNING
    assert mode_of(handle, 1) & 0x40 == 0  # XCP_DAQ_LIST_MODE_RUNNING


def test_stop_selected_clears_the_selected_flag():
    """Same rule as test_start_selected_clears_the_selected_flag and
    test_stop_all_clears_the_selected_flag_too, pinned for the third and last mode so all three
    branches of the mode dispatch are shown to reach the shared SELECTED reset."""
    handle = daq_handle()
    configure(handle, 0)
    select(handle, 0)

    exchange(handle, (0xDD, 0x02))

    assert mode_of(handle, 0) & 0x01 == 0  # XCP_DAQ_LIST_MODE_SELECTED


def test_start_selected_with_nothing_selected_is_rejected():
    handle = daq_handle()
    configure(handle, 0)

    assert exchange(handle, (0xDD, 0x01)) == (0xFE, 0x2A)


@pytest.mark.parametrize('mode', (0x03, 0x10, 0xFF))
def test_an_unknown_mode_is_rejected(mode):
    handle = daq_handle()

    assert exchange(handle, (0xDD, mode)) == (0xFE, 0x27)


def test_stop_all_updates_the_session_status():
    handle = daq_handle()
    configure(handle, 0)
    exchange(handle, (0xDE, 0x01, 0x00, 0x00))

    assert exchange(handle, (0xFD,))[1] & 0x40 != 0

    exchange(handle, (0xDD, 0x00))

    assert exchange(handle, (0xFD,))[1] & 0x40 == 0

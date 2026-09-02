#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=2),
                                         daq(name='DAQ2', max_odt=5, max_odt_entries=2)),
                                   **kwargs))
    connect(handle)
    return handle


def exchange(handle, request, length=2):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def configure(handle, daq_list=0):
    """One written ODT entry, so the list is startable."""
    exchange(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) + (0x00, 0x00))
    exchange(handle, (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))


def start_stop(handle, mode, daq_list=0, byte_order='LITTLE_ENDIAN'):
    return exchange(handle, (0xDE, mode) + tuple(u16_to_array(daq_list, byte_order)))


def mode_of(handle, daq_list=0):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[daq_list].mode


def test_start_sets_running_and_answers_with_first_pid():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4"""
    handle = daq_handle()
    configure(handle, daq_list=1)

    assert start_stop(handle, 0x01, daq_list=1) == (0xFF, 3), 'FIRST_PID of DAQ2 is 3'
    assert mode_of(handle, 1) & 0x40 != 0  # XCP_DAQ_LIST_MODE_RUNNING


def test_stop_clears_running():
    handle = daq_handle()
    configure(handle)
    start_stop(handle, 0x01)

    assert start_stop(handle, 0x00)[0] == 0xFF
    assert mode_of(handle) & 0x40 == 0  # XCP_DAQ_LIST_MODE_RUNNING


def test_select_marks_the_list_without_starting_it():
    """1.1/1.6.4.1.1.4: select "configures the DAQ list with the provided parameters but does
    not start the data transmission"."""
    handle = daq_handle()
    configure(handle)

    assert start_stop(handle, 0x02)[0] == 0xFF
    assert mode_of(handle) & 0x01 != 0  # XCP_DAQ_LIST_MODE_SELECTED
    assert mode_of(handle) & 0x40 == 0  # XCP_DAQ_LIST_MODE_RUNNING


def test_stop_is_accepted_for_a_list_that_was_never_started():
    handle = daq_handle()
    configure(handle)

    assert start_stop(handle, 0x00)[0] == 0xFF


@pytest.mark.parametrize('mode', (0x03, 0x10, 0xFF))
def test_an_unknown_mode_is_rejected(mode):
    handle = daq_handle()
    configure(handle)

    assert start_stop(handle, mode) == (0xFE, 0x27)


def test_starting_an_empty_list_is_rejected():
    """Nothing is configured to sample, so the list cannot enter data transfer mode."""
    handle = daq_handle()

    assert start_stop(handle, 0x01) == (0xFE, 0x2A)
    assert start_stop(handle, 0x02) == (0xFE, 0x2A)


def test_stopping_an_empty_list_is_still_accepted():
    handle = daq_handle()

    assert start_stop(handle, 0x00)[0] == 0xFF


def test_an_unknown_list_is_rejected():
    handle = daq_handle()

    assert start_stop(handle, 0x01, daq_list=2) == (0xFE, 0x22)


def test_the_session_status_reports_daq_running():
    """1.1/1.6.1.1.3: "If at least one DAQ list has been started, the slave device is in data
    transfer mode. The GET_STATUS command will return the DAQ_RUNNING status bit set."."""
    handle = daq_handle()
    configure(handle)
    start_stop(handle, 0x01)

    assert exchange(handle, (0xFD,), length=2)[1] & 0x40 != 0

    start_stop(handle, 0x00)

    assert exchange(handle, (0xFD,), length=2)[1] & 0x40 == 0


def test_daq_running_survives_stopping_one_of_two_running_lists():
    """1.1/1.6.1.1.3 defines DAQ_RUNNING as "at least one DAQ list has been started and is in
    data transfer mode" -- a property of every list together, not of the one just stopped. This
    is why Xcp_DaqSessionStatusUpdate rescans every list on every start/stop instead of tracking
    a count or toggling a flag: with two lists running, stopping one must leave the bit set,
    because the other is still transmitting. Do not "simplify" the rescan away."""
    handle = daq_handle()
    configure(handle, daq_list=0)
    configure(handle, daq_list=1)
    start_stop(handle, 0x01, daq_list=0)
    start_stop(handle, 0x01, daq_list=1)

    assert exchange(handle, (0xFD,), length=2)[1] & 0x40 != 0

    start_stop(handle, 0x00, daq_list=0)

    assert exchange(handle, (0xFD,), length=2)[1] & 0x40 != 0, 'DAQ2 is still running'

    start_stop(handle, 0x00, daq_list=1)

    assert exchange(handle, (0xFD,), length=2)[1] & 0x40 == 0

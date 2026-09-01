#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=2),
                                         daq(name='DAQ2', max_odt=1, max_odt_entries=1)),
                                   **kwargs))
    connect(handle)
    return handle


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def fill(handle, daq_list=0):
    """SET_DAQ_PTR then WRITE_DAQ, so the list has something to clear."""
    response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) + (0x00, 0x00))
    response(handle, (0xE1, 0xFF, 0x01, 0x02) + tuple(u32_to_array(0xDEADBEEF, 'LITTLE_ENDIAN')))


def test_clear_daq_list_resets_every_odt_entry():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.1.1"""
    handle = daq_handle()
    fill(handle)

    assert response(handle, (0xE3, 0x00, 0x00, 0x00))[0] == 0xFF

    entry = handle.lib.Xcp_Ptr.config.daqList[0].odt[0].odtEntry[0]
    assert entry.address == handle.ffi.NULL
    assert entry.addressExtension == 0
    assert entry.length == 0
    assert entry.bitOffset == 0xFF


def test_clear_daq_list_stops_a_running_list_rather_than_refusing():
    """1.1/1.6.4.2.1.1: "the running Data Transmission on this list will be stopped". D10."""
    handle = daq_handle()
    rt = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]
    rt.daqList[0].mode = 0x40  # XCP_DAQ_LIST_MODE_RUNNING

    assert response(handle, (0xE3, 0x00, 0x00, 0x00))[0] == 0xFF
    assert rt.daqList[0].mode == 0


def test_clear_daq_list_resets_the_list_state():
    handle = daq_handle()
    rt = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]
    rt.daqList[0].eventChannelNumber = 3
    rt.daqList[0].prescaler = 5
    rt.daqList[0].prescalerCounter = 2
    rt.daqList[0].priority = 0

    response(handle, (0xE3, 0x00, 0x00, 0x00))

    assert rt.daqList[0].eventChannelNumber == 0
    assert rt.daqList[0].prescaler == 1
    assert rt.daqList[0].prescalerCounter == 0


def test_clear_daq_list_leaves_other_lists_alone():
    handle = daq_handle()
    fill(handle, daq_list=1)

    response(handle, (0xE3, 0x00, 0x00, 0x00))

    assert handle.lib.Xcp_Ptr.config.daqList[1].odt[0].odtEntry[0].length == 1


def test_clear_daq_list_invalidates_a_pointer_aimed_at_it():
    """1.1/1.6.4.2.1.1 leaves a pointer aimed at a just-cleared list naming nothing meaningful.

    Xcp_Internal is not reachable from this CFFI harness (interface/Xcp.h does not include
    Xcp_Internal.h), so invalidation is observed through its consequence instead, the same way
    write_daq_test.py's test_write_daq_without_a_pointer_is_refused does: with the pointer gone,
    a WRITE_DAQ finds nothing valid to write through and answers ERR_OUT_OF_RANGE."""
    handle = daq_handle()
    response(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))

    response(handle, (0xE3, 0x00, 0x00, 0x00))

    assert response(handle, (0xE1, 0xFF, 0x01, 0x02) +
                    tuple(u32_to_array(0xDEADBEEF, 'LITTLE_ENDIAN'))) == (0xFE, 0x22)


def test_clear_daq_list_rejects_an_unknown_list():
    handle = daq_handle()

    assert response(handle, (0xE3, 0x00, 0x02, 0x00)) == (0xFE, 0x22)


def test_clear_daq_list_updates_the_daq_running_session_status():
    """1.1/1.6.1.1.3: "If at least one DAQ list has been started, the slave device is in data
    transfer mode. The GET_STATUS command will return the DAQ_RUNNING status bit set." That bit
    is a property of every list together (Xcp_DaqSessionStatusUpdate), not just the one being
    cleared: CLEAR_DAQ_LIST resets the cleared list's own mode directly, so without also calling
    that helper, clearing the only running list would leave DAQ_RUNNING set in session_status."""
    handle = daq_handle()
    fill(handle)
    response(handle, (0xDE, 0x01, 0x00, 0x00))  # START_STOP_DAQ_LIST, start, DAQ_LIST_NUMBER=0

    assert response(handle, (0xFD,))[1] & 0x40 != 0

    response(handle, (0xE3, 0x00, 0x00, 0x00))

    assert response(handle, (0xFD,))[1] & 0x40 == 0


def test_xcp_init_clears_odt_entries_left_by_a_previous_session():
    """The generated ODT entry arrays are module-level mutable statics (script/source_cfg.c.jinja2
    emits them `static`) that Xcp_Init did not used to reset. Two consequences: a re-initialised
    module inherited a previous session's DAQ configuration, and, in this test harness,
    XcpTest/MockGen caches compiled modules by configuration hash, so a test sharing a compiled
    configuration with an earlier one silently inherited whatever that earlier test had written
    (write_daq_test.py's fix-round-1 test worked around exactly this from the Python side).

    Companion of daq_runtime_test.py's
    test_initialisation_clears_runtime_state_left_by_a_previous_session, which covers Xcp_Rt the
    same way. bit_offset is deliberately not the 0xFF "ignore" sentinel here (unlike fill()'s
    WRITE_DAQ), so the post-reinit bitOffset==0xFF assertion is actually evidence of a reset
    rather than trivially true of the value written in the first place."""
    handle = daq_handle()
    response(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))
    response(handle, (0xE1, 0x07, 0x01, 0x00) + tuple(u32_to_array(0xDEADBEEF, 'LITTLE_ENDIAN')))

    entry = handle.lib.Xcp_Ptr.config.daqList[0].odt[0].odtEntry[0]
    assert entry.length == 1
    assert entry.bitOffset == 0x07

    handle.lib.Xcp_Init(handle.ffi.cast('const Xcp_Type *', handle.config.lib.Xcp))

    assert entry.length == 0
    assert entry.bitOffset == 0xFF

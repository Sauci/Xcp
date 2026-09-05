#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'), daq(name='DAQ2')), **kwargs))
    connect(handle)
    return handle


def exchange(handle, request, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def get_mode(handle, daq_list=0, byte_order='LITTLE_ENDIAN'):
    return exchange(handle, (0xDF, 0x00) + tuple(u16_to_array(daq_list, byte_order)))


def test_get_daq_list_mode_reports_a_freshly_initialised_list():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.6"""
    handle = daq_handle()

    assert get_mode(handle) == (0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)


def test_get_daq_list_mode_reports_what_set_daq_list_mode_stored():
    """Channel 0 is the untouched power-up default (source/Xcp.c's Xcp_Init), so asserting it
    back would pass even if SET_DAQ_LIST_MODE's store were deleted. SET_DAQ_LIST_MODE rejects any
    channel at or above maxEventChannel (source/Xcp_Daq.c), and the default configuration
    declares only one channel, so a second channel has to be configured before channel 1 can be
    set and read back as a real round trip."""
    handle = daq_handle(events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),
                                event(name='EVT2', triggered_daq_list_ref=['DAQ1'])))
    exchange(handle, (0xE0, 0x00, 0x01, 0x00, 0x01, 0x00, 0x03, 0x00), length=1)

    assert get_mode(handle, daq_list=1)[6] == 3, 'prescaler'
    assert get_mode(handle, daq_list=1)[4:6] == (0x01, 0x00), 'event channel, little endian'


def test_get_daq_list_mode_reports_direction_for_a_receiving_list():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.6, the GET-side half of SP3's Task
    4: SET_DAQ_LIST_MODE stores DIRECTION (bit 1) in the same layout GET_DAQ_LIST_MODE reads back,
    so a stimulation-capable list that accepted DIRECTION = STIM must report it set here -- the
    same round trip test_get_daq_list_mode_reports_what_set_daq_list_mode_stored above performs
    for the event channel and prescaler. set_daq_list_mode_test.py's
    test_set_daq_list_mode_accepts_stim_on_a_receiving_list drives the same round trip already, to
    show SET accepted the request; this test gives GET_DAQ_LIST_MODE's own reporting contract a
    home in the file that owns it, matching every other bit this file pins by name."""
    handle = XcpTest(stim_config(daq_count=1, odt_count=1, odt_entries_count=1))
    connect(handle)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xE0, 0x02, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))

    assert (get_mode(handle)[1] & 0x02) != 0x00


def test_get_daq_list_mode_reports_running_and_selected():
    handle = daq_handle()
    rt = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]
    # handle.define() resolves macros visible to interface/Xcp.h's preprocess; these live in
    # source/Xcp_Internal.h only, so they are spelled out literally here, as in
    # set_daq_list_mode_test.py.
    rt.daqList[0].mode = (0x40 |  # XCP_DAQ_LIST_MODE_RUNNING
                          0x01)  # XCP_DAQ_LIST_MODE_SELECTED

    assert get_mode(handle)[1] == 0x41


def test_get_daq_list_mode_writes_the_event_channel_in_the_configured_byte_order():
    handle = daq_handle(byte_order='BIG_ENDIAN')
    # 0x0001's two bytes differ, so a byte-swapped reading (0x01, 0x00) is distinguishable from
    # the correctly-ordered one (0x00, 0x01) asserted below; 0x0000 would pass under either order
    # and prove nothing.
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].eventChannelNumber = 0x0001

    assert get_mode(handle, byte_order='BIG_ENDIAN')[4:6] == (0x00, 0x01)


def test_get_daq_list_mode_reports_priority():
    """SET_DAQ_LIST_MODE refuses any nonzero priority by specification (1.1/1.6.4.1.1.3: "If the
    ECU doesn't support the prioritization of DAQ lists, a DAQ list priority > 0 is not allowed
    and will be indicated by returning ERR_OUT_OF_RANGE"), so a round trip through the command
    cannot exercise the priority byte -- the runtime state is poked directly instead, as tests
    above already do for mode and for the event channel's byte order. Do not "fix" this by
    routing it through SET_DAQ_LIST_MODE: that command's own restriction means it would quietly
    delete the only coverage of this byte."""
    handle = daq_handle()
    # 0x7F has bits set in both nibbles, so a truncation or a wrong-field read would be visible.
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].priority = 0x7F

    assert get_mode(handle)[7] == 0x7F


def test_get_daq_list_mode_rejects_an_unknown_list():
    handle = daq_handle()

    assert get_mode(handle, daq_list=2)[0:2] == (0xFE, 0x22)

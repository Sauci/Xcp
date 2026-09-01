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
    handle = daq_handle()
    exchange(handle, (0xE0, 0x00, 0x01, 0x00, 0x00, 0x00, 0x03, 0x00), length=1)

    assert get_mode(handle, daq_list=1)[6] == 3, 'prescaler'
    assert get_mode(handle, daq_list=1)[4:6] == (0x00, 0x00), 'event channel, little endian'


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


def test_get_daq_list_mode_rejects_an_unknown_list():
    handle = daq_handle()

    assert get_mode(handle, daq_list=2)[0:2] == (0xFE, 0x22)

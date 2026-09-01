#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def rt(handle):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]


def exchange(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def test_daq_list_runtime_starts_stopped_with_a_prescaler_of_one():
    """A prescaler of 0 would divide a raster to nothing; 1.1/1.6.4.1.1.3 makes 1 the neutral
    value, so that is what a list must hold before the master ever sets a mode."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'), daq(name='DAQ2'))))

    for index in range(2):
        assert rt(handle).daqList[index].mode == 0
        assert rt(handle).daqList[index].prescaler == 1
        assert rt(handle).daqList[index].prescalerCounter == 0
        assert rt(handle).daqList[index].priority == 0
        assert rt(handle).daqList[index].eventChannelNumber == 0


def test_dto_queue_starts_empty_at_the_configured_depth():
    handle = XcpTest(DefaultConfig(daq_queue_size=8))

    assert rt(handle).dtoQueue.depth == 8
    assert rt(handle).dtoQueue.count == 0
    assert rt(handle).dtoQueue.read == 0
    assert rt(handle).dtoQueue.write == 0


def test_initialisation_clears_runtime_state_left_by_a_previous_session():
    handle = XcpTest(DefaultConfig())

    rt(handle).daqList[0].mode = 0x40  # RUNNING
    rt(handle).daqList[0].prescaler = 7
    rt(handle).dtoQueue.count = 3

    handle.lib.Xcp_Init(handle.ffi.cast('const Xcp_Type *', handle.config.lib.Xcp))

    assert rt(handle).daqList[0].mode == 0
    assert rt(handle).daqList[0].prescaler == 1
    assert rt(handle).dtoQueue.count == 0


def test_trigger_rejects_an_unknown_event_channel():
    """DD15. The API is a vendor extension, so it reports a development error rather than an
    XCP error packet: no master asked for anything."""
    handle = XcpTest(DefaultConfig())

    handle.lib.Xcp_TriggerEventChannel(1)

    handle.det_report_error.assert_called_once_with(ANY, ANY,
                                                   handle.define('XCP_TRIGGER_EVENT_CHANNEL_API_ID'),
                                                   handle.define('XCP_E_INVALID_EVENT_CHANNEL'))


def test_trigger_before_initialisation_reports_uninit():
    handle = XcpTest(DefaultConfig(), initialize=False)

    handle.lib.Xcp_TriggerEventChannel(0)

    handle.det_report_error.assert_called_once_with(ANY, ANY,
                                                   handle.define('XCP_TRIGGER_EVENT_CHANNEL_API_ID'),
                                                   handle.define('XCP_E_UNINIT'))


def test_a_stopped_list_samples_nothing():
    handle = XcpTest(DefaultConfig())
    connect(handle)
    handle.xcp_read_slave_memory_u8.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    handle.xcp_read_slave_memory_u8.assert_not_called()


def test_a_full_ring_drops_the_frame_instead_of_growing():
    """A full ring in this task simply drops the frame; nothing counts the drop or reports
    EV_DAQ_OVERLOAD yet -- that arrives once the arbitration that lets the ring drain does too.
    This only guarantees the ring itself never grows past its configured depth."""
    handle = XcpTest(DefaultConfig(daq_queue_size=2,
                                   daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=1),)))
    connect(handle)

    for odt in range(3):
        exchange(handle, (0xE2, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (odt, 0x00))
        exchange(handle, (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000 + odt, 'LITTLE_ENDIAN')))
    exchange(handle, (0xE0, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) +
             tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x01, 0x00))
    exchange(handle, (0xDE, 0x01) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))

    handle.lib.Xcp_TriggerEventChannel(0)

    assert rt(handle).dtoQueue.count == 2, 'three ODTs were sampled but only two ring slots exist'
    # A ring that started empty (read == write == 0) and took exactly `depth` successful pushes
    # and no pops is, by construction, full: write has wrapped all the way back to meet read. If
    # the third (dropped) push had advanced write anyway -- the mutation the count assertion above
    # cannot see, since write and count are updated independently -- write would have moved past
    # read instead.
    assert rt(handle).dtoQueue.write == rt(handle).dtoQueue.read, \
        'the write index only advances for frames actually stored'

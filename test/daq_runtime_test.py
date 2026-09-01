#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest


def rt(handle):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]


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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def test_get_daq_clock_returns_the_value_captured_at_reception():
    """1.1/1.6.4.1.2.3: the response 'contains the current value of the data acquisition clock,
    when the GET_DAQ_CLOCK command packet has been received'. Xcp_CanIfRxIndication dispatches
    Xcp_DTOCmdDaqGetDaqClock synchronously, in the same call that receives the command, so that
    handler's own Xcp_GetDaqTimestamp() call already happens at reception -- there is no later,
    differently-scheduled point this could be deferred to (Xcp_MainFunction never assembles CTO
    responses; see the Task 8 report). What the wire value alone cannot prove is that the clock was
    read only once: a second, redundant read whose result is discarded would leave the same bytes
    on the wire and be invisible below, so call_count is asserted directly instead."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp()))
    connect(handle)
    handle.xcp_get_daq_timestamp.side_effect = (v for v in (0x11111111, 0x22222222, 0x33333333))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDC,)))
    handle.lib.Xcp_MainFunction()

    assert handle.xcp_get_daq_timestamp.call_count == 1

    frame = handle.can_if_transmit.call_args[0][1].SduDataPtr
    assert frame[0] == 0xFF
    assert tuple(frame[1:4]) == (0x00, 0x00, 0x00), 'three reserved bytes'
    assert payload_to_array(bytearray(frame[4:8]), 1, 4, 'LITTLE_ENDIAN')[0] == 0x11111111


def test_get_daq_clock_is_unknown_without_a_configured_clock():
    handle = XcpTest(DefaultConfig())
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDC,)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN'))

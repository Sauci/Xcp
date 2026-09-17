#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""EV_TIME_SYNC: reporting a timestamp captured on an external sync line (1.1/§1.8.8).

    0    BYTE    Event = 0xFD
    1    BYTE    Event Code = 0x08
    2    BYTE    reserved
    3    BYTE    reserved
    4..7 DWORD   Timestamp

§1.8.8 contradicts itself about that width -- the table says DWORD, the prose says the format is
GET_DAQ_RESOLUTION_INFO's, and that command encodes a size of 1, 2 or 4 bytes. DD154 takes the
table. The test below under a ONE_BYTE configuration is what would fail if someone later "fixed"
the width to follow the prose.
"""

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect

SYNC_TIMESTAMP = 0x89ABCDEF


def time_sync_config(size='DWORD', **kwargs):
    return DefaultConfig(channel_rx_pdu_ref=0x0001, timestamp=timestamp(size=size), **kwargs)


def raise_and_drain(handle, value=SYNC_TIMESTAMP):
    """Raise the event and read the frame immediately after the Xcp_MainFunction that sends it --
    not from call_args_list, which records a pointer into the one reused event buffer."""
    result = handle.lib.Xcp_RaiseTimeSyncEvent(value)
    before = handle.can_if_transmit.call_count
    handle.lib.Xcp_MainFunction()

    if handle.can_if_transmit.call_count == before:
        return result, None

    frame = handle.can_if_transmit.call_args[0][1]
    captured = (tuple(frame.SduDataPtr[0:8]), frame.SduLength)
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return result, captured


@pytest.mark.parametrize('byte_order', ('LITTLE_ENDIAN', 'BIG_ENDIAN'))
def test_the_event_carries_the_timestamp_in_1_8_8s_layout(byte_order):
    handle = XcpTest(time_sync_config(byte_order=byte_order))
    connect(handle)

    result, reported = raise_and_drain(handle)

    assert result == handle.define('E_OK')
    assert reported is not None
    frame, length = reported

    assert frame[0:2] == (0xFD, 0x08), 'EV_TIME_SYNC'
    assert frame[2:4] == (0x00, 0x00), '1.8.8 names positions 2 and 3 reserved; a defined byte ' \
                                       'beats whatever the queue entry last held'
    assert u32_from_array(bytearray(frame[4:8]), byte_order) == SYNC_TIMESTAMP
    assert length == 0x08


def test_the_integrators_value_is_transmitted_and_the_clock_is_not_read():
    """DD155's whole point. A test asserting only that the bytes looked plausible would pass if the
    module re-read Xcp_GetDaqTimestamp() instead of using what it was given -- which would discard
    the edge-accurate capture that is the reason 1.8.8 exists."""
    handle = XcpTest(time_sync_config())
    connect(handle)

    handle.xcp_get_daq_timestamp.reset_mock()

    _, reported = raise_and_drain(handle, 0x0BADF00D)

    assert reported is not None
    frame, _ = reported
    assert u32_from_array(bytearray(frame[4:8]), 'LITTLE_ENDIAN') == 0x0BADF00D
    handle.xcp_get_daq_timestamp.assert_not_called()


@pytest.mark.parametrize('size', ('BYTE', 'WORD', 'DWORD'))
def test_the_full_32_bits_are_sent_whatever_the_daq_timestamp_size(size):
    """DD154's consequence, stated as a test so it cannot be "fixed" by accident: a configuration
    truncating DAQ timestamps to one or two bytes still sends all four here. Truncating the one
    packet whose stated purpose is highly accurate time synchronisation would defeat it."""
    handle = XcpTest(time_sync_config(size=size))
    connect(handle)

    _, reported = raise_and_drain(handle)

    assert reported is not None
    frame, length = reported
    assert u32_from_array(bytearray(frame[4:8]), 'LITTLE_ENDIAN') == SYNC_TIMESTAMP
    assert length == 0x08, 'the packet is 8 bytes regardless of the configured timestamp width'


def test_a_full_event_queue_is_reported_to_det():
    """The branch nothing reaches by accident. Filled through Xcp_RaiseUserEvent, the entry point
    added for §1.2's carriers."""
    handle = XcpTest(time_sync_config(event_queue_size=2))
    connect(handle)

    filler = (0x41, 0x42)
    while handle.lib.Xcp_RaiseUserEvent(filler, len(filler)) == handle.define('E_OK'):
        pass

    handle.det_report_error.reset_mock()

    assert handle.lib.Xcp_RaiseTimeSyncEvent(SYNC_TIMESTAMP) == handle.define('E_NOT_OK')
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY,
                                                    handle.define('XCP_E_EVENT_QUEUE_FULL'))

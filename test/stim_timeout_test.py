#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""EV_STIM_TIMEOUT: noticing that a STIM DAQ list went unstimulated across consecutive events.

XCP part 2 - Protocol Layer Specification 1.1/1.8.9 defines the packet and none of the policy. What
is asserted here is this module's policy, recorded as DD149-DD153 in
docs/superpowers/specs/2026-09-17-xcp-stim-timeout-design.md: consecutive MISSED EVENTS rather than
elapsed time, a list stale only when NONE of its slots were refreshed, the channel reported when
every list on it is stale and the list reported otherwise, and one report per staleness episode.

1.1/1.8.9's own layout, which the OCR sidecar renders with its Info Type 1 row missing entirely:

    0    BYTE   Event = 0xFD
    1    BYTE   Event Code = 0x09
    2    BYTE   Info Type: 0 = Event channel number, 1 = DAQ list number
    3    BYTE   reserved
    4..5 WORD   Event channel number or DAQ list number, depending on Info Type
"""

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect
from .stim_reception_test import deliver, running_stim_list

STIM_FRAME = (0x00, 0x11, 0x22, 0x33, 0x44)  # absolute PID 0, then payload


def stim_timeout_config(threshold=None, lists=1, **kwargs):
    """`lists` DAQ_STIM lists on one event channel, the channel declaring `threshold` missed events
    -- or declaring nothing at all when threshold is None, which is DD152's opt-out.

    One list is the ordinary case and always reports Info Type 0: DD151 reports the CHANNEL when
    every STIM list on it is stale, and with a single list that is the only way it can be stale at
    all. Info Type 1 needs two lists of which only one goes quiet, which is what lists=2 is for."""
    names = ['DAQ%d' % (n + 1) for n in range(lists)]
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         daqs=tuple(daq(name=n, type='DAQ_STIM', max_odt=1, max_odt_entries=1)
                                    for n in names),
                         events=(event(name='EVENT0', triggered_daq_list_ref=names,
                                       stim_timeout_events=threshold),),
                         **kwargs)


def armed(handle, config):
    """A connected slave with a running STIM list, one fresh frame already delivered."""
    connect(handle)
    running_stim_list(handle)
    deliver(handle, STIM_FRAME, config.default_daq_dto_pdu_mapping)


def trigger(handle):
    """One stimulation event, then the frame it transmitted -- read immediately, NOT from
    call_args_list afterwards: the mock records a pointer into the one reused event buffer."""
    before = handle.can_if_transmit.call_count
    handle.lib.Xcp_TriggerEventChannel(0x0000)
    handle.lib.Xcp_MainFunction()

    if handle.can_if_transmit.call_count == before:
        return None

    frame = handle.can_if_transmit.call_args[0][1]
    captured = (tuple(frame.SduDataPtr[0:6]), frame.SduLength)
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return captured


def test_a_stale_list_reports_once_at_exactly_the_threshold():
    """DD153. The first trigger consumes the delivered frame, so staleness starts after it. The
    report fires when the counter EQUALS the threshold -- not before, and not again while the list
    stays stale, because one episode must not flood a queue that drops when full."""
    config = stim_timeout_config(threshold=3)
    handle = XcpTest(config)
    armed(handle, config)

    assert trigger(handle) is None, 'the delivered frame is applied; nothing is stale yet'

    assert trigger(handle) is None, 'stale 1 of 3'
    assert trigger(handle) is None, 'stale 2 of 3'

    reported = trigger(handle)
    assert reported is not None, 'stale 3 of 3 must report'
    frame, length = reported
    assert frame[0:4] == (0xFD, 0x09, 0x00, 0x00), \
        'EV_STIM_TIMEOUT, Info Type 0 (channel), reserved 0 -- the only STIM list on this channel ' \
        'is stale, so DD151 reports the channel rather than the list'
    assert u16_from_array(bytearray(frame[4:6]), 'LITTLE_ENDIAN') == 0x0000, 'event channel 0'
    assert length == 0x06

    assert trigger(handle) is None, 'stale 4 of 3 must not report again'
    assert trigger(handle) is None, 'nor 5'


def test_fresh_data_resets_the_counter_and_a_second_episode_reports_again():
    config = stim_timeout_config(threshold=2)
    handle = XcpTest(config)
    armed(handle, config)

    assert trigger(handle) is None
    assert trigger(handle) is None, 'stale 1 of 2'

    deliver(handle, STIM_FRAME, config.default_daq_dto_pdu_mapping)
    assert trigger(handle) is None, 'fresh again: the counter resets'
    assert trigger(handle) is None, 'stale 1 of 2 once more'

    assert trigger(handle) is not None, 'the second episode reports on its own merits'


def test_a_channel_with_no_threshold_never_reports():
    """DD152's opt-out, and the invariant every configuration written before this feature relies
    on: absent means off, however long the list stays stale."""
    config = stim_timeout_config(threshold=None)
    handle = XcpTest(config)
    armed(handle, config)

    for _ in range(12):
        assert trigger(handle) is None

    handle.det_report_error.assert_not_called()


def test_a_stale_list_still_applies_its_latched_values():
    """DD35 is untouched: this design observes, it does not change what is applied. SP3 recorded
    that a later EV_STIM_TIMEOUT 'can report that data went stale without changing what is
    applied', and that is what this pins."""
    config = stim_timeout_config(threshold=2)
    handle = XcpTest(config)
    armed(handle, config)

    trigger(handle)
    writes_after_first = handle.xcp_write_slave_memory_u8.call_count

    trigger(handle)

    assert handle.xcp_write_slave_memory_u8.call_count > writes_after_first, \
        'a stale list keeps applying the values it last received'


def two_list_channel(threshold):
    """Two DAQ_STIM lists on one event channel. Under ABSOLUTE identification list 0's ODT 0 is
    absolute PID 0 and list 1's is PID 1, so the two are stimulated by frames that differ only in
    their first byte."""
    config = stim_timeout_config(threshold=threshold, lists=2)
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, daq_list=0)
    running_stim_list(handle, daq_list=1)
    return handle, config


def test_one_stale_list_of_two_reports_that_list_by_number():
    """DD151's other arm, and the only way Info Type 1 is ever sent: some lists on the channel are
    stale and some are not, so naming the channel would say less than naming the list. List 1 is
    kept fresh throughout; list 0 is not."""
    handle, config = two_list_channel(threshold=2)
    pdu = config.default_daq_dto_pdu_mapping

    deliver(handle, (0x00,) + STIM_FRAME[1:], pdu)
    deliver(handle, (0x01,) + STIM_FRAME[1:], pdu)
    assert trigger(handle) is None, 'both fresh'

    deliver(handle, (0x01,) + STIM_FRAME[1:], pdu)
    assert trigger(handle) is None, 'list 0 stale 1 of 2, list 1 fresh'

    deliver(handle, (0x01,) + STIM_FRAME[1:], pdu)
    reported = trigger(handle)

    assert reported is not None, 'list 0 stale 2 of 2 must report'
    frame, length = reported
    assert frame[0:4] == (0xFD, 0x09, 0x01, 0x00), 'Info Type 1 (DAQ list), reserved 0'
    assert u16_from_array(bytearray(frame[4:6]), 'LITTLE_ENDIAN') == 0x0000, 'DAQ list 0, the stale one'
    assert length == 0x06


def test_both_lists_stale_reports_the_channel_once():
    """DD151's first arm on a channel where it is not trivially true: two lists, both stale, one
    report naming the channel rather than two naming the lists."""
    handle, config = two_list_channel(threshold=2)
    pdu = config.default_daq_dto_pdu_mapping

    deliver(handle, (0x00,) + STIM_FRAME[1:], pdu)
    deliver(handle, (0x01,) + STIM_FRAME[1:], pdu)
    assert trigger(handle) is None, 'both fresh'

    assert trigger(handle) is None, 'both stale 1 of 2'

    reported = trigger(handle)
    assert reported is not None
    frame, _ = reported
    assert frame[0:4] == (0xFD, 0x09, 0x00, 0x00), 'Info Type 0 (event channel)'
    assert u16_from_array(bytearray(frame[4:6]), 'LITTLE_ENDIAN') == 0x0000, 'event channel 0'

    assert trigger(handle) is None, 'and only once for the episode'


@pytest.mark.parametrize('byte_order', ('LITTLE_ENDIAN', 'BIG_ENDIAN'))
def test_the_number_is_written_in_the_configured_byte_order(byte_order):
    """1.1/1.8.9's position 4 is a WORD, so it follows the configured order like every other
    multi-byte field. A single-byte channel number would make the two orders indistinguishable, so
    this asserts the raw bytes rather than the decoded value."""
    config = stim_timeout_config(threshold=1, byte_order=byte_order)
    handle = XcpTest(config)
    armed(handle, config)

    trigger(handle)
    reported = trigger(handle)

    assert reported is not None
    frame, _ = reported
    assert u16_from_array(bytearray(frame[4:6]), byte_order) == 0x0000


def test_a_full_event_queue_is_reported_to_det():
    """The queue-full branch, which no other test reaches by accident -- the shape that shipped
    uncovered twice before. The queue is filled with EV_USER first, using the entry point added for
    1.1/1.2's carriers, so the timeout event has nowhere to go."""
    config = stim_timeout_config(threshold=1, event_queue_size=2)
    handle = XcpTest(config)
    armed(handle, config)

    trigger(handle)

    filler = (0x41, 0x42)
    while handle.lib.Xcp_RaiseUserEvent(filler, len(filler)) == handle.define('E_OK'):
        pass

    handle.det_report_error.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0x0000)

    handle.det_report_error.assert_called_with(ANY, ANY, ANY,
                                               handle.define('XCP_E_EVENT_QUEUE_FULL'))

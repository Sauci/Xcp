#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The three event codes XCP part 2 - Protocol Layer Specification 1.1/1.2 defines that this module
can reach without a new subsystem: EV_USER (0xFE) and EV_TRANSPORT (0xFF), the two carriers of
optional event information data, and EV_SESSION_TERMINATED (0x07).

The carriers became implementable when DD138 taught the event queue's transmit branch to lay
userData out at 2..MAX_CTO-1, which it did for SERV_TEXT; 1.1/1.1.3.4 puts an EV packet's optional
information data in exactly that range. The design that built it scoped them out for having no
caller, not for lacking machinery."""

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


def connected(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def drain_one(handle):
    """The next frame, read immediately after the Xcp_MainFunction that sends it. NOT from
    call_args_list afterwards: the mock records the PduInfoType pointer and every event is
    transmitted out of the one Xcp_Internal.event.pdu_info buffer, so a later read shows whatever
    that buffer holds last, identically for every recorded call."""
    handle.lib.Xcp_MainFunction()
    frame = handle.can_if_transmit.call_args[0][1]
    captured = (tuple(frame.SduDataPtr[0:8]), frame.SduLength)
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return captured


@pytest.mark.parametrize('raise_name, event_code', (('Xcp_RaiseUserEvent', 0xFE),
                                                    ('Xcp_RaiseTransportEvent', 0xFF)))
def test_a_carrier_event_transmits_its_information_data(raise_name, event_code):
    """1.1/1.1.3.4: the PID at 0, the event code at 1, optional event information over
    2..MAX_CTO-1."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connected(handle)

    data = (0xDE, 0xAD, 0xBE, 0xEF)
    assert getattr(handle.lib, raise_name)(data, len(data)) == handle.define('E_OK')

    frame, length = drain_one(handle)

    assert frame[0:2] == (0xFD, event_code)
    assert frame[2:6] == data
    assert length == 0x06


@pytest.mark.parametrize('raise_name, event_code', (('Xcp_RaiseUserEvent', 0xFE),
                                                    ('Xcp_RaiseTransportEvent', 0xFF)))
def test_a_carrier_event_may_carry_no_information_data(raise_name, event_code):
    """1.1/1.1.3.4 makes the information data optional, so a bare two-byte event is legal and a
    length of 0 is not a fault. This is where a bound copied from SERV_TEXT without thinking would
    show: 1.1/1.3 requires that payload to be non-empty and null-terminated, and 1.1/1.2 requires
    neither of an event."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connected(handle)

    assert getattr(handle.lib, raise_name)(handle.ffi.NULL, 0) == handle.define('E_OK')

    frame, length = drain_one(handle)

    assert frame[0:2] == (0xFD, event_code)
    assert length == 0x02
    handle.det_report_error.assert_not_called()


@pytest.mark.parametrize('raise_name', ('Xcp_RaiseUserEvent', 'Xcp_RaiseTransportEvent'))
def test_a_carrier_event_refuses_a_null_pointer_with_a_non_zero_length(raise_name):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connected(handle)

    transmit_calls = handle.can_if_transmit.call_count

    assert getattr(handle.lib, raise_name)(handle.ffi.NULL, 4) == handle.define('E_NOT_OK')

    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == transmit_calls, 'nothing may reach the transport'
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY,
                                                    handle.define('XCP_E_PARAM_POINTER'))


@pytest.mark.parametrize('raise_name', ('Xcp_RaiseUserEvent', 'Xcp_RaiseTransportEvent'))
def test_a_carrier_event_refuses_data_longer_than_max_cto_allows(raise_name):
    """MAX_CTO 8 leaves 6 bytes for information data; 7 is one over."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
    connected(handle)

    transmit_calls = handle.can_if_transmit.call_count
    data = tuple([0x41] * 7)

    assert getattr(handle.lib, raise_name)(data, len(data)) == handle.define('E_NOT_OK')

    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == transmit_calls
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY,
                                                    handle.define('XCP_E_EVENT_DATA_INVALID'))


@pytest.mark.parametrize('raise_name', ('Xcp_RaiseUserEvent', 'Xcp_RaiseTransportEvent'))
def test_a_carrier_event_refuses_data_longer_than_the_queue_entry_holds(raise_name):
    """The second, independent bound: XCP_EVENT_USER_DATA_SIZE is 16 by default while MAX_CTO here
    is 128, so this data fits the frame and not the queue entry."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=128))
    connected(handle)

    transmit_calls = handle.can_if_transmit.call_count
    data = tuple([0x41] * 17)

    assert getattr(handle.lib, raise_name)(data, len(data)) == handle.define('E_NOT_OK')

    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == transmit_calls
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY,
                                                    handle.define('XCP_E_EVENT_DATA_INVALID'))


def test_terminate_session_announces_the_termination():
    """1.1/1.2: "the slave indicates to the master that it autonomously decided to disconnect the
    current XCP session" -- the event announces a decision already taken, which is why this is one
    call and not two."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connected(handle)

    assert handle.lib.Xcp_TerminateSession() == handle.define('E_OK')

    frame, length = drain_one(handle)

    assert frame[0:2] == (0xFD, 0x07), 'EV_SESSION_TERMINATED'
    assert length == 0x02, '1.1/1.2 defines no information data for this code'


def test_terminate_session_actually_disconnects():
    """The half that makes the event true. Xcp_DisconnectSession is internal, so an event-only API
    would let an integrator announce a termination it had no way to perform. GET_STATUS is the
    probe: 1.1/1.6.1.1.3 makes it reachable only while connected, so a refusal proves the session
    ended."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connected(handle)

    assert handle.lib.Xcp_TerminateSession() == handle.define('E_OK')

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    transmit_calls = handle.can_if_transmit.call_count

    # GET_STATUS, which a disconnected slave must not answer.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == transmit_calls, \
        'a disconnected slave answers nothing but CONNECT'


@pytest.mark.parametrize('raise_name', ('Xcp_RaiseUserEvent', 'Xcp_RaiseTransportEvent'))
def test_a_carrier_event_refuses_a_full_queue(raise_name):
    """A queue-full branch is reached by no other test by accident, which is precisely how the SERV
    work shipped one uncovered and needed a codecov report to notice."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, event_queue_size=2))
    connected(handle)

    data = (0x41, 0x42)
    results = [getattr(handle.lib, raise_name)(data, len(data)) for _ in range(4)]

    assert handle.define('E_NOT_OK') in results, 'a queue of capacity 1 must fill'
    handle.det_report_error.assert_called_with(ANY, ANY, ANY,
                                               handle.define('XCP_E_EVENT_QUEUE_FULL'))


def test_terminate_session_disconnects_even_when_the_event_cannot_be_queued():
    """The session ends whatever the queue says. 1.1/1.2 makes EV_SESSION_TERMINATED the
    announcement of a decision already taken, so a full queue must not leave the session running --
    that would make the return value describe the announcement while the caller reads it as the
    termination. E_NOT_OK here means 'the master was not told', not 'nothing happened'."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, event_queue_size=2))
    connected(handle)

    # Fill the queue with something else first, so the termination event has nowhere to go.
    filler = (0x41, 0x42)
    while handle.lib.Xcp_RaiseUserEvent(filler, len(filler)) == handle.define('E_OK'):
        pass

    handle.det_report_error.reset_mock()

    assert handle.lib.Xcp_TerminateSession() == handle.define('E_NOT_OK')
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY,
                                                    handle.define('XCP_E_EVENT_QUEUE_FULL'))

    # Drain the filler events first. Without this the probe below measures the queue draining
    # rather than the command being answered -- a transmit count says something went out, not what.
    for _ in range(8):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    transmit_calls = handle.can_if_transmit.call_count

    # GET_STATUS, which a disconnected slave must not answer -- the session ended regardless.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == transmit_calls, \
        'the termination happened even though the announcement did not'

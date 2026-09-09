#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-NV Task 1: SET_REQUEST's STORE_DAQ_REQ and CLEAR_DAQ_REQ, and their polled integrator
callbacks Xcp_StoreDaqConfiguration / Xcp_ClearDaqConfiguration (interface/Xcp.h).

Task 2 extends this file: the session configuration id SET_REQUEST carries in bytes 2,3, held in
Xcp_Internal.session_configuration_id and reported by GET_STATUS bytes 4,5 (DD98/DD99).

Task 4 extends this file again: Xcp_ReadStoredSessionConfigurationId (interface/Xcp.h), the polled
start-up read that adopts session_configuration_id from non-volatile storage, and
XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE (0xFE, 0x33), what GET_STATUS answers while that read
is still outstanding (DD100/DD101). The Final verification section at the end also covers DD102:
RESUME_SUPPORTED stays clear, SET_DAQ_LIST_MODE is unaffected, and no DAQ list is restored.

The final review's fix wave adds one more section at the very end: F1, a live state bug in the
interaction between the store/clear blocks above and Task 4's read, reachable only once all three
API flags are on together -- a configuration none of the sections above build.

Design doc: docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md (DD94-DD102).

DD95 is the hazard this whole task exists around: the ERR_PGM_ACTIVE gate in Xcp_CanIfRxIndication
refuses every command whose Xcp_CTOErrorMatrix row carries that bit -- 42 rows in the default build,
38 with flash programming enabled (four rows carry the bit only with that gate off; counted from the
matrix's own initializer entries per preprocessor branch, not by grepping the macro name, which also
matches the dispatch gate's own uses) -- DISCONNECT among them, for as long as any of the three
session-status request bits is set. A request bit that never clears is therefore a permanent,
reconnect-only denial of service. The rule that avoids it,
copied from STORE_CAL_REQ's own pre-existing block in Xcp_MainFunction (source/Xcp.c): E_OK means
finished, whatever the status code says, so only E_NOT_OK holds the bit.
"""

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def exchange(handle, request, tx_pdu_ref=0x0001, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(tx_pdu_ref, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def test_set_request_accepts_store_daq_req_and_polls_the_store_callback():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)
    # E_NOT_OK: not yet finished. Keeps this test to its one job -- accepted, and the callback
    # reached -- without also queuing the completion event, which test_completion_clears_the_bit_
    # and_raises_the_matching_event_carrying_the_status_byte below owns.
    handle.xcp_store_daq_configuration.return_value = handle.define('E_NOT_OK')

    assert exchange(handle, (0xF9, 0b00000100, 0x00, 0x00))[0] == 0xFF

    assert handle.xcp_store_daq_configuration.called


def test_set_request_accepts_clear_daq_req_and_polls_the_clear_callback():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_clear_daq_configuration_api_enable=True))
    connect(handle)
    handle.xcp_clear_daq_configuration.return_value = handle.define('E_NOT_OK')

    assert exchange(handle, (0xF9, 0b00001000, 0x00, 0x00))[0] == 0xFF

    assert handle.xcp_clear_daq_configuration.called


@pytest.mark.parametrize('mode, mock_attr, api_enable_kwarg', (
        (0b00000100, 'xcp_store_daq_configuration', 'xcp_store_daq_configuration_api_enable'),
        (0b00001000, 'xcp_clear_daq_configuration', 'xcp_clear_daq_configuration_api_enable'),
))
def test_the_request_bit_stays_set_while_the_callback_has_not_finished(mode, mock_attr, api_enable_kwarg):
    """A callback returning E_NOT_OK is polled again on the next Xcp_MainFunction and the request
    bit stays set. Xcp_Internal is not reachable from the CFFI harness (global constraint 4), so
    this is observed through GET_STATUS byte 1 rather than the field itself."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **{api_enable_kwarg: True}))
    connect(handle)

    mock = getattr(handle, mock_attr)
    mock.return_value = handle.define('E_NOT_OK')

    exchange(handle, (0xF9, mode, 0x00, 0x00))  # poll #1: not yet finished
    handle.lib.Xcp_MainFunction()               # poll #2: still not finished

    assert mock.call_count == 2

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[1] & mode == mode


@pytest.mark.parametrize('mode, mock_attr, event_pid', (
        (0b00000100, 'xcp_store_daq_configuration', 0x02),  # EV_STORE_DAQ
        (0b00001000, 'xcp_clear_daq_configuration', 0x01),  # EV_CLEAR_DAQ
))
def test_completion_clears_the_bit_and_raises_the_matching_event_carrying_the_status_byte(mode, mock_attr, event_pid):
    """EV_STORE_DAQ is 0x02 and EV_CLEAR_DAQ is 0x01 -- counter-intuitive (the reverse of mode-bit
    order), so checked explicitly here rather than assumed; swapped, this is exactly what mutation
    3 (task-1-report.md) verifies. Each event carries the status byte as its one-byte payload,
    exactly as EV_STORE_CAL does (set_request_test.py)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True,
                                    xcp_clear_daq_configuration_api_enable=True))
    connect(handle)

    def finish_successfully(*args):
        args[-1][0] = 0x00  # zero status: a clean completion
        return handle.define('E_OK')

    getattr(handle, mock_attr).side_effect = finish_successfully

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    event_frames = [call for call in handle.can_if_transmit.call_args_list
                    if tuple(call[0][1].SduDataPtr[0:3]) == (0xFD, event_pid, 0x00)]
    assert len(event_frames) > 0

    # Drains the event this completion queued and chained onto the confirmation above (D16,
    # set_request_test.py), so the GET_STATUS exchange below is not racing a still-unconfirmed
    # frame. A no-op if nothing was actually left in flight (ONGOING_TRANSMIT_TYPE_NONE,
    # Xcp_CanIfTxConfirmation, source/Xcp.c).
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[1] & mode == 0x00


def test_a_completed_but_failed_store_daq_req_clears_the_bit_so_disconnect_is_not_refused():
    """DD95, the denial-of-service hazard this task exists to avoid, and the reason this test is
    the acceptance bar rather than a nicety: found live for STORE_CAL_REQ on an earlier branch
    (DD77/R1). The ERR_PGM_ACTIVE gate in Xcp_CanIfRxIndication refuses every command whose
    Xcp_CTOErrorMatrix row carries that bit -- 42 rows in the default build, 38 with flash
    programming enabled (four rows carry the bit only with that gate off) -- DISCONNECT among them,
    while any of the three request bits is set. E_OK means finished, whatever the status code says:
    a callback that completes but reports failure must still clear its bit, or the module wedges
    until the next CONNECT."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)

    def store_daq_configuration(session_configuration_id, p_status_code):
        p_status_code[0] = 0x01  # non-zero: failed, but E_OK still means "finished"
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000100, 0x00, 0x00))
    # Drains the queued EV_STORE_DAQ (see the comment in the completion test above) so DISCONNECT
    # below is not racing a still-unconfirmed frame.
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFE,))[0] == 0xFF


def test_a_completed_but_failed_clear_daq_req_clears_the_bit_so_disconnect_is_not_refused():
    """Same hazard as test_a_completed_but_failed_store_daq_req_clears_the_bit_so_disconnect_is_not_
    refused above, for CLEAR_DAQ_REQ."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_clear_daq_configuration_api_enable=True))
    connect(handle)

    def clear_daq_configuration(p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_clear_daq_configuration.side_effect = clear_daq_configuration

    exchange(handle, (0xF9, 0b00001000, 0x00, 0x00))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFE,))[0] == 0xFF


def test_a_completed_but_failed_store_cal_req_clears_the_bit_so_disconnect_is_not_refused():
    """DD96 regression pin, not a fix. This rule already holds for STORE_CAL_REQ (Xcp_MainFunction,
    source/Xcp.c -- 'E_OK means finished, whatever the status code says') but nothing tested it
    before this task: a later change narrowing the clear to a zero status code would pass every
    existing test silently. STORE_CAL_REQ's own store path is unchanged by this task."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    def store_calibration_data_to_non_volatile_memory(p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = \
        store_calibration_data_to_non_volatile_memory

    exchange(handle, (0xF9, 0b00000001, 0x00, 0x00))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFE,))[0] == 0xFF


@pytest.mark.parametrize('mode, name', ((0b00000100, 'STORE_DAQ_REQ'),
                                        (0b00001000, 'CLEAR_DAQ_REQ')))
def test_set_request_refuses_the_daq_modes_when_their_api_flags_are_disabled(mode, name):
    """Widening SET_REQUEST's accepted mask (source/Xcp_Std.c) is conditional on the matching
    xcp_store_daq_configuration_api_enable / xcp_clear_daq_configuration_api_enable flag, so an
    unconfigured build answers exactly as it always has: ERR_OUT_OF_RANGE (XCP part 2 - Protocol
    Layer Specification 1.0/1.6.1.2.3). DefaultConfig() itself defaults both flags off
    (test/parameter.py) -- which is what keeps test/set_request_test.py's own
    test_set_request_refuses_the_non_volatile_daq_modes_it_cannot_fulfil and
    test/get_status_test.py's test_get_status_never_reports_a_request_no_code_can_fulfil passing
    unchanged."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    assert exchange(handle, (0xF9, mode, 0x00, 0x00))[0:2] == (0xFE, 0x22)


@pytest.mark.parametrize('mode, mock_attr, api_enable_kwarg', (
        (0b00000100, 'xcp_store_daq_configuration', 'xcp_store_daq_configuration_api_enable'),
        (0b00001000, 'xcp_clear_daq_configuration', 'xcp_clear_daq_configuration_api_enable'),
))
def test_an_unconfirmed_event_still_occupies_its_slot_so_a_new_push_can_fail(mode, mock_attr, api_enable_kwarg):
    """The STORE_DAQ_REQ/CLEAR_DAQ_REQ twin of set_request_test.py's own test of the same name,
    which covers the identical XCP_E_EVENT_QUEUE_FULL line for STORE_CAL_REQ -- source/Xcp.c:1643
    (STORE_DAQ_REQ) and :1691 (CLEAR_DAQ_REQ) push into the same event queue, through the same
    ring, on the same mechanism that test already pins: Xcp_EventQueueGet peeks -- it does not
    advance `read` -- so an event selected for transmission stays counted as occupying its ring
    slot until Xcp_EventQueuePop runs in the confirmation, and the ring keeps one slot always empty
    to tell full from empty. At event_queue_size=2 the usable capacity for a *new* push while one
    event is in flight, unconfirmed, is eventQueueSize - 2 == 0: the second SET_REQUEST's push
    fails outright and Xcp_ReportError(..., XCP_E_EVENT_QUEUE_FULL) fires. Exactly one such DET
    call is asserted, as the precedent does, not merely more than zero, so a handler that reported
    it on every iteration would not pass by accident. Lives here rather than in
    set_request_test.py because STORE_DAQ_REQ/CLEAR_DAQ_REQ are this file's own feature -- the
    completion/event-push behaviour they share is already pinned together in this file's own
    test_completion_clears_the_bit_and_raises_the_matching_event_carrying_the_status_byte above,
    and this needs nothing set_request_test.py's STORE_CAL_REQ-only tests already provide."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, event_queue_size=2, **{api_enable_kwarg: True}))

    def finish_successfully(*args):
        args[-1][0] = 0x00  # zero status: a clean completion
        return handle.define('E_OK')

    getattr(handle, mock_attr).side_effect = finish_successfully

    connect(handle)

    for _ in range(2):
        # SET_REQUEST
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert len([c for c in handle.det_report_error.call_args_list
                if c[0][3] == handle.define('XCP_E_EVENT_QUEUE_FULL')]) == 1


@pytest.mark.parametrize('byte_order', byte_orders)
def test_set_request_passes_the_session_configuration_id_to_the_store_callback(byte_order):
    """Task 2, brief test 1. XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3: SET_REQUEST's
    WORD session_configuration_id sits at bytes 2,3 and must reach Xcp_StoreDaqConfiguration's own
    first parameter -- asserted on the callback's actual argument, not merely that it was called,
    which would also pass with Task 1's own 0x0000 placeholder. Parametrized over byte order because
    asserting the decoded value at a non-default byte order is what makes a hardcoded endianness
    observable -- a round-trip through both Xcp_CopyToU16WithOrder and Xcp_CopyFromU16WithOrder
    cannot distinguish it."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, byte_order=byte_order,
                                    xcp_store_daq_configuration_api_enable=True))
    connect(handle)
    handle.xcp_store_daq_configuration.return_value = handle.define('E_NOT_OK')

    exchange(handle, (0xF9, 0b00000100) + tuple(u16_to_array(0x1234, byte_order)))

    assert handle.xcp_store_daq_configuration.call_args[0][0] == 0x1234


@pytest.mark.parametrize('byte_order', byte_orders)
def test_get_status_reports_the_session_configuration_id_after_a_successful_store(byte_order):
    """Task 2, brief test 2. XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3, bytes 4,5, in
    the configured byte order -- DD99's second row: STORE_DAQ_REQ completing with a zero status
    adopts the id SET_REQUEST carried into Xcp_Internal.session_configuration_id. Parametrized over
    byte order because this assertion exercises both the read side (SET_REQUEST,
    Xcp_CopyToU16WithOrder) and the write side (GET_STATUS, Xcp_CopyFromU16WithOrder) together --
    a byte-order defect on either side alone would show up here. The symmetric case, where the same
    wrong order is hardcoded in both conversions, is caught by the read-side test above, which
    asserts the decoded value at a non-default byte order."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, byte_order=byte_order,
                                    xcp_store_daq_configuration_api_enable=True))
    connect(handle)

    def store_daq_configuration(session_configuration_id, p_status_code):
        p_status_code[0] = 0x00  # zero status: a clean completion
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000100) + tuple(u16_to_array(0x1234, byte_order)))
    # Drains the queued EV_STORE_DAQ (see test_completion_clears_the_bit_and_raises_the_matching_
    # event_carrying_the_status_byte above) so GET_STATUS below is not racing a still-unconfirmed
    # frame.
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == tuple(u16_to_array(0x1234, byte_order))


def test_a_failed_store_leaves_the_previously_reported_id_unchanged():
    """Task 2, brief test 3. DD99's fourth row: a store that completes but fails (E_OK, non-zero
    status) leaves Xcp_Internal.session_configuration_id unchanged. A prior successful store gives
    it something to leave unchanged -- without one, an implementation that always adopts the id
    (ignoring the status) and one that never does would be indistinguishable from a fresh 0."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)

    def store_daq_configuration_ok(session_configuration_id, p_status_code):
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration_ok

    exchange(handle, (0xF9, 0b00000100, 0x34, 0x12))  # id = 0x1234, completes successfully
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_STORE_DAQ

    def store_daq_configuration_failed(session_configuration_id, p_status_code):
        p_status_code[0] = 0x01  # non-zero: failed, but E_OK still means "finished" (DD95/DD96)
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration_failed

    exchange(handle, (0xF9, 0b00000100, 0x78, 0x56))  # id = 0x5678, but this store fails
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_STORE_DAQ

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x34, 0x12)


def test_a_successful_clear_resets_the_reported_id_to_zero():
    """Task 2, brief test 4. DD98: XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3's
    CLEAR_DAQ_REQ postcondition resets the session configuration id to 0 -- stated here as an
    observable outcome, since this module never sees the integrator's non-volatile memory."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True,
                                    xcp_clear_daq_configuration_api_enable=True))
    connect(handle)

    def store_daq_configuration(session_configuration_id, p_status_code):
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000100, 0x34, 0x12))  # id = 0x1234, completes successfully
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_STORE_DAQ

    def clear_daq_configuration(p_status_code):
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_clear_daq_configuration.side_effect = clear_daq_configuration

    exchange(handle, (0xF9, 0b00001000, 0x00, 0x00))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_CLEAR_DAQ

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x00, 0x00)


def test_connect_does_not_reset_the_session_configuration_id():
    """Task 2, brief test 5 -- the assertion this task cares most about. DD99: CONNECT clears the
    three session-status REQUEST bits (DD77/R1, Xcp_CTOCmdStdConnect's own final review R1 comment,
    source/Xcp_Std.c) but must leave the id standing -- it reflects what non-volatile memory holds,
    which a reconnect does not alter. Clearing it would make GET_STATUS report 0 while storage still
    holds a configuration. This is the assertion most likely to be broken later, because the
    instinct is to reset everything at the session boundary."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)

    def store_daq_configuration(session_configuration_id, p_status_code):
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000100, 0x34, 0x12))  # id = 0x1234, completes successfully
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_STORE_DAQ

    connect(handle)  # reconnect: must clear the request bits, must not touch the id

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x34, 0x12)


# ---------------------------------------------------------------------------------------------
# Task 4: the start-up read, and the error it reports while outstanding (DD100/DD101).
#
# Unlike STORE_DAQ_REQ/CLEAR_DAQ_REQ above, nothing in SET_REQUEST arms this read -- Xcp_Init
# arms it directly from xcp_read_stored_session_configuration_id_api_enable, so every test below
# that wants the read outstanding configures
# Xcp_ReadStoredSessionConfigurationId's mock BEFORE the first Xcp_MainFunction call, including
# the one connect() itself makes: XcpTest's own constructor already calls Xcp_Init (test/
# conftest.py), so the state is armed by the time DefaultConfig() returns, and connect()'s own
# Xcp_MainFunction is this module's first poll of it.
# ---------------------------------------------------------------------------------------------

def test_the_stored_session_configuration_id_read_is_retried_while_not_yet_readable():
    """Task 4, brief test 1. DD100: Xcp_ReadStoredSessionConfigurationId is polled from
    Xcp_MainFunction on the identical contract Xcp_StoreDaqConfiguration/
    Xcp_ClearDaqConfiguration already use -- E_NOT_OK means "not yet readable, ask again". Two
    E_NOT_OK answers and then E_OK with 0x4321 pins the RETRY, not merely the adoption: a one-shot
    read that gave up after its first E_NOT_OK would never reach the third, successful call, and
    this would still read back as 0x0000."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_read_stored_session_configuration_id_api_enable=True))

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        if handle.xcp_read_stored_session_configuration_id.call_count < 3:
            return handle.define('E_NOT_OK')
        p_session_configuration_id[0] = 0x4321
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    connect(handle)                # poll #1: E_NOT_OK
    handle.lib.Xcp_MainFunction()  # poll #2: E_NOT_OK
    handle.lib.Xcp_MainFunction()  # poll #3: E_OK, 0x4321

    assert handle.xcp_read_stored_session_configuration_id.call_count == 3

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x21, 0x43)


def test_get_status_answers_resource_temporary_not_accessible_while_the_read_is_outstanding():
    """Task 4, brief test 2, and design doc DD101. GET_STATUS is reachable only once CONNECTed --
    XCP part 1 - Overview 1.0/2.3: "In 'DISCONNECTED' state, the slave processes no XCP commands
    except for CONNECT" (Xcp_CanIfRxIndication's own dispatch gate, source/Xcp.c, quotes this
    verbatim) -- so this test connects FIRST, while the read is still outstanding --
    connecting only after the read has already completed would pin nothing about the window at
    all. Both halves -- refused during the window, answered normally once it closes -- are
    asserted in the one test so the TRANSITION is what is pinned, not two facts that could each
    pass independently for the wrong reason."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_read_stored_session_configuration_id_api_enable=True))
    handle.xcp_read_stored_session_configuration_id.return_value = handle.define('E_NOT_OK')

    connect(handle)  # poll #1: E_NOT_OK -- the read is still outstanding once CONNECT returns

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x33)

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        p_session_configuration_id[0] = 0x0000
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    handle.lib.Xcp_MainFunction()  # poll #2: E_OK -- the read completes

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[0] == 0xFF


def test_a_read_completing_with_nothing_stored_leaves_the_id_at_zero():
    """Task 4, brief test 3. DD100: E_OK with a non-zero status code means non-volatile memory
    holds no valid configuration -- the same "E_OK means finished, the status code carries the
    outcome" contract STORE_DAQ_REQ/CLEAR_DAQ_REQ already use (DD95/DD96). The mock reports a
    non-zero id here specifically so adopting it regardless of the status code would be caught:
    Xcp_Init already leaves session_configuration_id at 0x0000u, so a handler that copied the id
    unconditionally would still pass this test if it always reported 0."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_read_stored_session_configuration_id_api_enable=True))

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        p_session_configuration_id[0] = 0xBEEF  # must NOT be adopted: the status below says invalid
        p_status_code[0] = 0x01  # non-zero: nothing stored
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    connect(handle)  # poll #1: E_OK, but "nothing stored"

    response = exchange(handle, (0xFD, 0x00, 0x00, 0x00))
    assert response[0] == 0xFF
    assert response[4:6] == (0x00, 0x00)


def test_the_read_is_not_repeated_once_it_has_completed():
    """Task 4, brief test 4. Xcp_Internal.session_configuration_id_read_state (source/
    Xcp_Internal.h) moves to COMPLETE the moment Xcp_ReadStoredSessionConfigurationId first
    reports E_OK, and Xcp_MainFunction's own poll site never calls it again for the rest of the
    session. Checked directly on the mock's call_count rather than only inferred from GET_STATUS,
    since a handler that kept polling but discarded a later answer could still leave GET_STATUS
    looking right."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_read_stored_session_configuration_id_api_enable=True))

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        p_session_configuration_id[0] = 0x0001
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    connect(handle)  # poll #1: completes the read

    assert handle.xcp_read_stored_session_configuration_id.call_count == 1

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_MainFunction()

    assert handle.xcp_read_stored_session_configuration_id.call_count == 1


def test_with_the_api_flag_disabled_there_is_no_read_and_get_status_answers_normally():
    """Task 4, brief test 5. xcp_read_stored_session_configuration_id_api_enable gates whether
    Xcp_Init arms the read at all (Xcp_Init, source/Xcp.c) and so whether Xcp_MainFunction ever
    polls Xcp_ReadStoredSessionConfigurationId, which is what DD101's GET_STATUS window depends
    on -- an unconfigured build has nowhere to read a stored configuration from and so nothing to
    poll. DefaultConfig() itself defaults the flag off (test/parameter.py), which is what keeps
    every other test in this suite, none of which mentions this flag, unaffected by this task."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    assert handle.xcp_read_stored_session_configuration_id.called is False

    response = exchange(handle, (0xFD, 0x00, 0x00, 0x00))
    assert response[0] == 0xFF
    assert response[4:6] == (0x00, 0x00)


# ---------------------------------------------------------------------------------------------
# Final verification (docs/superpowers/plans/2026-09-09-xcp-daq-nv-storage.md). DD102: this plan
# builds persistence, not RESUME, and the two tests below exist so a reviewer sees that checked
# rather than assumed, since nothing else in this plan touches GET_DAQ_PROCESSOR_INFO or
# SET_DAQ_LIST_MODE at all.
# ---------------------------------------------------------------------------------------------

def test_resume_stays_unadvertised_and_unhonoured_after_this_task():
    """Final verification, DD102. RESUME_SUPPORTED (DAQ_PROPERTIES bit 2, GET_DAQ_PROCESSOR_INFO,
    1.1/1.6.4.1.2.4) is checked directly here, not only cross-referenced, so this task's own
    verification shows it was looked at rather than assumed from test/get_daq_processor_info_
    test.py's own (unrelated) coverage.

    SET_DAQ_LIST_MODE's own bit 7 is checked too, worded carefully. This plan's design doc and its
    own Final Verification checklist both say SET_DAQ_LIST_MODE "still refuses the RESUME bit" --
    that does not match current code, and predates this task: 1.1's own SET_DAQ_LIST_MODE mode-
    byte table (source/Xcp_Internal.h) marks bits 2, 3, 6 and 7 don't-care ("a master may set them
    to anything and the slave ignores them"), and test/set_daq_list_mode_test.py's own
    test_set_daq_list_mode_tolerates_the_bits_the_specification_marks_dont_care[0x80] already pins
    exactly that -- bit 7 is ACCEPTED (0xFF), not refused with an error. Commit 13f59c2 deliberately
    stopped refusing bits 6/7, as over-strict, before this plan existed; asserting a refusal here
    would either fail honestly or force a mischaracterisation of passing, spec-correct behaviour,
    neither of which this task should do quietly. What DD102 actually needs -- and what this
    checks -- is the part that IS still true: the bit is not HONOURED. Xcp_DTOCmdDaqSetDaqListMode
    never writes XCP_DAQ_LIST_MODE_RESUME into the list's own stored mode, so GET_DAQ_LIST_MODE
    never reports it set, whatever SET_DAQ_LIST_MODE's request carried."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    daq_processor_info = exchange(handle, (0xDA,))
    assert daq_processor_info[0] == 0xFF  # an error response would also satisfy the bit check below
    assert daq_processor_info[1] & 0b00000100 == 0x00  # RESUME_SUPPORTED, bit 2

    # SET_DAQ_LIST_MODE(RESUME=1, daq_list=0, channel=0, prescaler=1, priority=0): accepted, not
    # refused -- see the docstring above for why "accepted" is the correct, current behaviour.
    assert exchange(handle, (0xE0, 0b10000000, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF

    daq_list_mode = exchange(handle, (0xDF, 0x00, 0x00, 0x00))
    assert daq_list_mode[0] == 0xFF  # an error response would also satisfy the bit check below
    assert daq_list_mode[1] & 0b10000000 == 0x00  # RESUME, bit 7


def test_the_read_does_not_restore_any_daq_list():
    """Final verification, DD102. The start-up read adopts the session configuration id and
    nothing else -- restoring DAQ lists is RESUME's job, and RESUME is a later phase. Configures
    a non-zero id, the shape a resumed session would need if one were ever restored, and confirms
    DAQ list 0 comes up exactly as Xcp_Init always leaves it: not selected, not running."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_read_stored_session_configuration_id_api_enable=True))

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        p_session_configuration_id[0] = 0x1234
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    connect(handle)  # poll #1: completes the read, adopts 0x1234

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x34, 0x12)  # the id WAS adopted

    daq_list_mode = exchange(handle, (0xDF, 0x00, 0x00, 0x00))
    assert daq_list_mode[0] == 0xFF  # an error response would also satisfy the two bit checks below
    mode = daq_list_mode[1]
    assert mode & 0b00000001 == 0x00  # SELECTED
    assert mode & 0b01000000 == 0x00  # RUNNING


# ---------------------------------------------------------------------------------------------
# Final review fix wave, F1: a live state bug the branch's own tests never built the
# configuration to reach. Task 4's tests above pass only the read flag; Tasks 1-2's only the
# store/clear flags -- the three-flag configuration below, the shape an integrator running all of
# DD94-DD102 in production would build, was never exercised by any existing test, and the bug is
# invisible without it.
# ---------------------------------------------------------------------------------------------

def test_a_completed_store_retires_a_still_outstanding_start_up_read():
    """Final review fix wave, F1. Within one Xcp_MainFunction, the STORE_DAQ_REQ block runs
    before the start-up read's own poll, and both write Xcp_Internal.session_configuration_id --
    the read had no guard against a store having already completed. Sequence: the read is armed
    OUTSTANDING and still not-yet-readable (E_NOT_OK) when STORE_DAQ_REQ(id=0x1234) completes
    successfully and adopts it; the read is then made to complete too, E_OK with status 0 and
    0x0000 -- "whatever storage held when ITS OWN job started", i.e. before the master's store
    reached it. Without the fix, that later completion overwrites session_configuration_id with
    the stale 0x0000, and GET_STATUS reports it instead of the id the master just committed --
    design doc DD99's own words: "Clearing it would make GET_STATUS report 0 while storage still
    holds a configuration." The fix retires the read the moment a store or clear completes with a
    zero status, so it is never polled again afterwards; the call_count assertion below pins that
    directly, not only the GET_STATUS symptom -- one call here, where the unfixed code reaches
    three (armed by connect(), polled again alongside the store's own completion since nothing
    yet retires it, and finally completed with the stale value)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True,
                                    xcp_clear_daq_configuration_api_enable=True,
                                    xcp_read_stored_session_configuration_id_api_enable=True))
    handle.xcp_read_stored_session_configuration_id.return_value = handle.define('E_NOT_OK')

    connect(handle)  # poll #1 (connect's own Xcp_MainFunction call): read polled, still E_NOT_OK

    def store_daq_configuration(session_configuration_id, p_status_code):
        p_status_code[0] = 0x00  # zero status: a clean completion
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    # poll #2 (exchange's own Xcp_MainFunction call): STORE_DAQ_REQ completes and adopts 0x1234.
    exchange(handle, (0xF9, 0b00000100, 0x34, 0x12))  # id = 0x1234
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_STORE_DAQ

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        p_session_configuration_id[0] = 0x0000  # whatever storage held when THIS job started
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    handle.lib.Xcp_MainFunction()  # poll #3: the read would complete here, if still polled

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x34, 0x12)  # poll #4
    assert handle.xcp_read_stored_session_configuration_id.call_count == 1


def test_a_completed_clear_retires_a_still_outstanding_start_up_read():
    """Final review fix wave, F1 -- the clear-side twin of
    test_a_completed_store_retires_a_still_outstanding_start_up_read above. source/Xcp.c:1671 is
    the CLEAR_DAQ_REQ block's own copy of the guard, reviewed alongside the STORE_DAQ_REQ one but,
    before this test, never actually executed -- the store-side test above is the only one that
    builds all three API flags together, and it only ever drives the store path. Same live state
    bug, same fix, same mechanism: within one Xcp_MainFunction, the CLEAR_DAQ_REQ block runs before
    the start-up read's own poll, and both write Xcp_Internal.session_configuration_id. Sequence:
    the read is armed OUTSTANDING and still not-yet-readable (E_NOT_OK) when CLEAR_DAQ_REQ
    completes successfully and resets the id to 0x0000u; the read is then made to complete too,
    E_OK with status 0 and a NON-ZERO id, 0x4321 -- deliberately not 0x0000, because both Xcp_Init
    and a successful clear already leave the id at 0x0000u, so a read that also reported 0x0000
    would pass this test whether or not the guard exists. Without the fix, that later completion
    overwrites session_configuration_id with 0x4321, and GET_STATUS reports it instead of the
    0x0000 the clear just committed -- the same clobber the store-side test above catches, seen
    from the clear side. The fix retires the read the moment a store or clear completes with a
    zero status, so it is never polled again afterwards; the call_count assertion below pins that
    directly, not only the GET_STATUS symptom -- one call here, where the unfixed code would reach
    three (armed by connect(), polled again alongside the clear's own completion since nothing yet
    retires it, and finally completed with the non-zero value)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True,
                                    xcp_clear_daq_configuration_api_enable=True,
                                    xcp_read_stored_session_configuration_id_api_enable=True))
    handle.xcp_read_stored_session_configuration_id.return_value = handle.define('E_NOT_OK')

    connect(handle)  # poll #1 (connect's own Xcp_MainFunction call): read polled, still E_NOT_OK

    def clear_daq_configuration(p_status_code):
        p_status_code[0] = 0x00  # zero status: a clean completion
        return handle.define('E_OK')

    handle.xcp_clear_daq_configuration.side_effect = clear_daq_configuration

    # poll #2 (exchange's own Xcp_MainFunction call): CLEAR_DAQ_REQ completes and resets to 0x0000.
    exchange(handle, (0xF9, 0b00001000, 0x00, 0x00))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))  # drains EV_CLEAR_DAQ

    def read_stored_session_configuration_id(p_session_configuration_id, p_status_code):
        p_session_configuration_id[0] = 0x4321  # non-zero: must NOT be adopted if the guard holds
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_read_stored_session_configuration_id.side_effect = read_stored_session_configuration_id

    handle.lib.Xcp_MainFunction()  # poll #3: the read would complete here, if still polled

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[4:6] == (0x00, 0x00)  # poll #4
    assert handle.xcp_read_stored_session_configuration_id.call_count == 1

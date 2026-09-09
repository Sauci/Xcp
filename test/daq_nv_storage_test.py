#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-NV Task 1: SET_REQUEST's STORE_DAQ_REQ and CLEAR_DAQ_REQ, and their polled integrator
callbacks Xcp_StoreDaqConfiguration / Xcp_ClearDaqConfiguration (interface/Xcp.h).

Task 2 extends this file: the session configuration id SET_REQUEST carries in bytes 2,3, held in
Xcp_Internal.session_configuration_id and reported by GET_STATUS bytes 4,5 (DD98/DD99).

Design doc: docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md (DD94-DD99).

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


def test_set_request_passes_the_session_configuration_id_to_the_store_callback():
    """Task 2, brief test 1. XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.3: SET_REQUEST's
    WORD session_configuration_id sits at bytes 2,3 and must reach Xcp_StoreDaqConfiguration's own
    first parameter -- asserted on the callback's actual argument, not merely that it was called,
    which would also pass with Task 1's own 0x0000 placeholder."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)
    handle.xcp_store_daq_configuration.return_value = handle.define('E_NOT_OK')

    exchange(handle, (0xF9, 0b00000100, 0x34, 0x12))  # id = 0x1234, LITTLE_ENDIAN (DefaultConfig's own default)

    assert handle.xcp_store_daq_configuration.call_args[0][0] == 0x1234


@pytest.mark.parametrize('byte_order', byte_orders)
def test_get_status_reports_the_session_configuration_id_after_a_successful_store(byte_order):
    """Task 2, brief test 2. XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3, bytes 4,5, in
    the configured byte order -- DD99's second row: STORE_DAQ_REQ completing with a zero status
    adopts the id SET_REQUEST carried into Xcp_Internal.session_configuration_id. Parametrized over
    byte order (unlike test 1 above) because this is the one assertion that exercises both the read
    side (SET_REQUEST, Xcp_CopyToU16WithOrder) and the write side (GET_STATUS,
    Xcp_CopyFromU16WithOrder) together -- a byte-order defect in either would show up here even if
    the other side were correct."""
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

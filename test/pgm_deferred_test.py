#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def pgm_handle(**kwargs):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, programming_enabled=True, **kwargs))
    connect(handle)
    return handle


def program_start(handle):
    """PROGRAM_START, without pumping Xcp_MainFunction -- the point of most tests here is what
    happens across SUBSEQUENT main-function calls, so the request and the polling are separate.

    Xcp_CanIfRxIndication only fills a buffer and sets a pending flag; every helper elsewhere in
    this suite (download_test.connect, clear_daq_list_test.response, pgm_configuration_test.exchange)
    calls Xcp_MainFunction afterward for exactly that reason, and this helper deliberately does not,
    so that a test can pump Xcp_MainFunction itself and count exactly how many polls have happened."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD2,)))


def transmitted(handle):
    """The last frame handed to CanIf, or None if CanIf_Transmit has not been called since the
    marker was placed. Reading call_args directly would return the CONNECT response for a command
    that transmitted nothing, which is exactly the case these tests must distinguish."""
    if handle.can_if_transmit.call_args is None:
        return None
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])


def busy_then(handle, status_code, busy_calls):
    """Xcp_ProgramStart returns E_NOT_OK `busy_calls` times, then E_OK with `status_code`.

    Writes 0xEE into pStatusCode on every BUSY call. DD54 says the module must not read that
    parameter while the callback is unfinished, and a poison value is how a test can see a module
    that does -- 0xEE would reach the wire as a bogus ERR_GENERIC."""
    state = dict(calls=0)

    def side_effect(p_status):
        state['calls'] += 1
        if state['calls'] <= busy_calls:
            p_status[0] = 0xEE
            return handle.define('E_NOT_OK')
        p_status[0] = status_code
        return handle.define('E_OK')

    handle.xcp_program_start.side_effect = side_effect
    return state


def test_program_start_transmits_nothing_while_the_integrator_is_busy():
    """DD53. The response is withheld with *responseExpected = FALSE, the mechanism
    Xcp_DTOCmdCalDownload already uses mid-block-transfer.

    Asserted as 'no CanIf_Transmit call at all' rather than 'not a positive response': a module
    that answered ERR_GENERIC immediately would satisfy the weaker assertion while being exactly
    the bug this test exists to catch."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=3)
    handle.can_if_transmit.reset_mock()

    program_start(handle)

    assert transmitted(handle) is None, 'no response may go out while the callback is unfinished'


def test_the_response_appears_on_the_main_function_where_the_callback_completes():
    """The other half: the response is not merely delayed, it arrives, and on the right cycle.
    Pumping one main function at a time and asserting the transition is what distinguishes a
    working deferral from a module that answers on the next command instead.

    A TxConfirmation for the still-busy poll's EV_CMD_PENDING sits between the two
    Xcp_MainFunction calls: the transmit pipeline carries one frame at a time (SWS_Xcp_00859), so
    without confirming that event first, the eventual positive response would be built correctly
    but stay queued behind it forever, never reaching CanIf_Transmit at all -- a false failure
    that would have nothing to do with the deferral logic under test."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=2)
    handle.can_if_transmit.reset_mock()
    program_start(handle)

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] != 0xFF, 'still busy on the second poll'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the positive response arrives when the callback does'


def test_the_positive_response_reports_the_live_communication_parameters():
    """DD56. MAX_CTO_PGM, MAX_BS_PGM, MIN_ST_PGM and QUEUE_SIZE_PGM are the module's ordinary
    values, because this module does not change them in programming mode.

    Pinned against the configuration rather than against literals: 1.1/1.6.5.1.3 makes MAX_BS_PGM
    and MIN_ST_PGM the bound on SP4b's PROGRAM_NEXT block transfer, so a wrong value here becomes
    a wire-visible defect there.

    The Xcp_MainFunction call is the ordinary flush every command needs (Xcp_CanIfRxIndication
    only fills a buffer and never transmits), not a busy poll: busy_calls=0 means the handler
    already built this response synchronously, before Xcp_MainFunction ever runs. Without it, and
    without the reset_mock() before program_start, this test passed anyway by reading connect()'s
    own response back out of the mock -- CONNECT's byte 3 is also maxCto (Xcp_CTOCmdStdConnect,
    Xcp_Std.c), so frame[0] and frame[3] matched a response this exchange never sent."""
    handle = pgm_handle(max_bs=5, min_st=3, cto_queue_size=2)
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    frame = transmitted(handle)

    assert frame[0] == 0xFF
    assert frame[3] == handle.lib.Xcp_Ptr.general.maxCto, 'MAX_CTO_PGM'
    assert frame[4] == 5, 'MAX_BS_PGM'
    assert frame[5] == 3, 'MIN_ST_PGM'
    assert frame[6] == 2, 'QUEUE_SIZE_PGM'


@pytest.mark.parametrize('master_block_mode, interleaved_mode, slave_block_mode, expected', (
    (True, False, False, 0x01),
    (False, True, False, 0x02),
    (False, False, True, 0x40),
    (True, True, True, 0x43),
))
def test_the_positive_response_reports_comm_mode_pgm(master_block_mode, interleaved_mode,
                                                      slave_block_mode, expected):
    """DD56. COMM_MODE_PGM is built from the same three flags GET_COMM_MODE_INFO's
    COMM_MODE_OPTIONAL reads (Xcp_DTOCmdStdGetCommModeInfo, Xcp_Std.c), at this response's own bit
    positions: masterBlockModeSupported (bit 0), interleavedModeSupported (bit 1) and
    slaveBlockModeSupported (bit 6) -- the third of which COMM_MODE_OPTIONAL has no bit for at all.

    Not asserted by test_the_positive_response_reports_the_live_communication_parameters, which
    pins MAX_CTO_PGM/MAX_BS_PGM/MIN_ST_PGM/QUEUE_SIZE_PGM but never reads byte 2. Swept one flag at
    a time, plus all three together, so each bit is pinned to its own flag rather than to a fixed
    configuration's coincidental combination."""
    handle = pgm_handle(master_block_mode=master_block_mode, interleaved_mode=interleaved_mode,
                        slave_block_mode=slave_block_mode)
    busy_then(handle, 0x00, busy_calls=0)
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[2] == expected, 'COMM_MODE_PGM'


def test_a_failing_integrator_yields_err_generic_and_leaves_the_session_closed():
    """1.1/1.6.5.1.1 names ERR_GENERIC for a slave 'not in a state which permits programming'.

    pgm_state is not reachable from this CFFI harness: test/conftest.py builds its cdef from
    interface/Xcp.h alone, which does not include Xcp_Internal.h. test/clear_daq_list_test.py:80-92
    documents the same limitation and the same workaround. So the claim that matters -- a module
    that answered correctly but stayed in XCP_PGM_STARTING would refuse every later PROGRAM_START
    with ERR_SEQUENCE, and no wire assertion on THIS exchange alone would notice -- is checked by
    actually sending that later PROGRAM_START and requiring it to be accepted rather than answered
    ERR_SEQUENCE (0x29)."""
    handle = pgm_handle()
    busy_then(handle, 0x01, busy_calls=1)
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'

    # Confirms the ERR_GENERIC response before trying again: the transmit pipeline carries one
    # frame at a time (SWS_Xcp_00859), and an unconfirmed CTO response would leave the second
    # PROGRAM_START's own answer queued behind it forever, never reaching CanIf_Transmit -- a
    # false failure unrelated to whether pgm_state is really back at XCP_PGM_IDLE.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    busy_then(handle, 0x00, busy_calls=0)
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, \
        'pgm_state must be back at XCP_PGM_IDLE, or this second PROGRAM_START would be refused ' \
        'with ERR_SEQUENCE instead of accepted'


def test_the_status_code_is_not_read_while_the_callback_is_busy():
    """DD54 and §4: pStatusCode is defined only for the E_OK case. The stub poisons it with 0xEE
    on every busy call, so a module that read it early would answer ERR_GENERIC-with-0xEE instead
    of completing successfully.

    Each poll's EV_CMD_PENDING is confirmed before the next: the transmit pipeline carries one
    frame at a time (SWS_Xcp_00859), so leaving a busy poll's event unconfirmed would leave the
    eventual completion response queued behind it forever, never reaching CanIf_Transmit -- the
    same reason test_the_response_appears_on_the_main_function_where_the_callback_completes
    confirms before its own final poll."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=4)
    program_start(handle)
    for _ in range(5):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert transmitted(handle)[0] == 0xFF, 'the poison value must not have been read'


def test_an_instantaneous_integrator_is_answered_without_deferring():
    """Spec §4. The first call to Xcp_ProgramStart happens in the handler, so an integrator that
    finishes immediately is answered on the very first ordinary flush -- no pending slot, no
    busy-poll cycle, and no EV_CMD_PENDING for an operation that never waited. One
    Xcp_MainFunction call is still needed to reach CanIf_Transmit at all, exactly as it is for
    every other command in this suite (download_test.connect, clear_daq_list_test.response): what
    this test pins is that ONE ordinary flush is enough, never the busy-poll cycle a deferred
    PROGRAM_START needs several of before its response appears.

    Without this test the handler could defer unconditionally and every other test here would
    still pass, since they all pump Xcp_MainFunction anyway. What it pins is the absence of an
    event: a module that always defers would emit one before answering.

    'nothing was left pending' cannot be read off pending_command.active directly, for the same
    CFFI-visibility reason as the ERR_GENERIC test above (test/clear_daq_list_test.py:80-92). Its
    only consumer in this task is Xcp_MainFunction's own poll, which runs the integrator callback
    again while a command is still marked pending -- so a stuck slot would replay
    Xcp_ProgramStart's already-configured success and transmit a second, unsolicited positive
    response on the next main-function call. Task 3 adds an ERR_CMD_BUSY gate on incoming commands
    that would give this a second, independent observable; Task 2 has only this one."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD2,)))
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'answered on the first ordinary flush'

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]
    assert events == [], 'an operation that never waited must not ask the master to wait'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args is None, \
        'nothing was left pending to complete a second time'


def test_at_most_one_ev_cmd_pending_is_outstanding():
    """DD54. Xcp_MainFunction is aperiodic -- cyclic per SWS_Xcp_00824, but the module may never
    depend on its period -- so EV_CMD_PENDING cannot be timed. Bounding it to one in flight makes
    the rate follow TxConfirmation instead, which SWS_Xcp_00859 already forces the module to wait
    for.

    Ten busy polls with no confirmation in between must produce exactly one event. A module that
    pushed one per poll would emit ten, which is the defect: on a fast bus that is a flood, and on
    any bus it is a rate derived from a period the module is not allowed to assume.

    The second half below is the part that actually pins a missing event_outstanding guard: the
    transmit pipeline carries one frame at a time (SWS_Xcp_00859), so a module that pushed on every
    busy poll would still show only one CanIf_Transmit call here -- the other nine would sit queued
    behind the first, unconfirmed, invisible to CanIf_Transmit until something frees the pipeline.
    Confirming the one outstanding event does exactly that, so it is where a queued flood would
    actually surface."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=20)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    for _ in range(10):
        handle.lib.Xcp_MainFunction()

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]

    assert len(events) == 1, 'exactly one EV_CMD_PENDING may be outstanding at a time'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]
    assert events == [], 'confirming the one outstanding event must not release a queued flood'


def test_a_second_ev_cmd_pending_follows_the_first_confirmation():
    """The complement of the test above, and the one that stops 'bounded to one' from degenerating
    into 'exactly one, ever'. After the first event is confirmed the slave may ask again, which is
    what keeps a master's timer alive across a long erase (1.1/1.7.2.4.2, Diagram 28)."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=20)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_MainFunction()

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]

    assert len(events) == 2

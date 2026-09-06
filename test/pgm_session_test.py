#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .pgm_deferred_test import pgm_handle, program_start, program_reset, transmitted, busy_then
from .download_test import connect
from .free_daq_test import dynamic_handle, allocate_directly
from .parameter import u16_to_array, u32_to_array


def send(handle, request):
    """A request, one main function, and the frame it produced (or None)."""
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    return transmitted(handle)


def program_prepare(handle, code_size):
    """PROGRAM_PREPARE (Task 5), without pumping Xcp_MainFunction -- mirrors program_start/
    program_reset in pgm_deferred_test.py and for the same reason: a test needs to pump
    Xcp_MainFunction and confirm transmissions itself, at its own pace. Byte 1 is the request's
    unused byte (1.1/1.6.5.2.3); Codesize is the WORD at bytes 2-3, in this suite's default
    byte order (LITTLE_ENDIAN, test/parameter.py's DefaultConfig)."""
    handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xCC, 0x00) + tuple(u16_to_array(code_size, 'LITTLE_ENDIAN'))))


def test_a_command_arriving_mid_operation_is_answered_err_cmd_busy():
    """DD55. The pre-existing ERR_CMD_BUSY gate tests
    cto_response.successful_transmission_pending, which DD53 leaves FALSE for the whole duration of
    a deferred operation -- precisely so that nothing is transmitted. That gate therefore does NOT
    cover this case, and without the new term the command would be dispatched, its handler would
    write cto_response.pdu_info, and Xcp_MainFunction would then overwrite the same buffer with the
    pending command's answer: one response lost, the other malformed.

    GET_STATUS is the interloper because it is unconditionally available and has no side effects,
    so a failure here is about the busy gate and nothing else. It is also a command whose own
    Xcp_CTOErrorMatrix entry carries no XCP_INTERNAL_ERR_CMD_BUSY bit at all (0x00u, source/Xcp.c),
    so the pre-existing gate would wave it through unconditionally -- this interloper is precisely
    the case the pre-existing gate was never asked to cover."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=20)
    program_start(handle)

    assert send(handle, (0xFD,))[0:2] == (0xFE, 0x10), 'ERR_CMD_BUSY'


def test_the_pending_response_still_arrives_after_an_err_cmd_busy():
    """The assertion that makes the test above mean something. ERR_CMD_BUSY alone would also be
    produced by a module that discarded the pending command on any interruption -- a worse bug than
    the one being fixed, and invisible to a test that only reads the busy answer.

    Fix round 1, finding 3 changed the timing here: Xcp_MainFunction now withholds the WHOLE
    pending-command block (poll included, not only the completion publish) while
    cto_response.successful_transmission_pending is TRUE, so send()'s own Xcp_MainFunction call
    does not poll at all this cycle -- the busy response it just built for GET_STATUS is still
    unconfirmed, occupying the one buffer both answers would otherwise share. Only one poll (the
    integrator's own busy answer, still counted by busy_calls=2) happens once that response is
    confirmed and the pipeline is genuinely free again."""
    handle = pgm_handle()
    state = busy_then(handle, 0x00, busy_calls=2)
    program_start(handle)
    send(handle, (0xFD,))

    # Frees the transmit pipeline: SWS_Xcp_00859 carries one frame at a time, and send() above
    # leaves its own ERR_CMD_BUSY response unconfirmed. Nothing was queued behind it -- the
    # withheld poll (finding 3) never ran while it was in flight -- so one confirmation, not two,
    # fully drains the pipeline here.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # The poll now allowed to run (still busy, busy_calls=2): pushes and transmits its own
    # EV_CMD_PENDING (DD54), confirmed in turn so the pipeline is settled again before the
    # completing poll.
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM_START response still arrives'
    assert state['calls'] >= 3, 'and the integrator was polled through the interruption'


def test_synch_is_exempt_and_abandons_without_clearing_the_slot():
    """1.1/1.7.1.1 makes SYNCH the master's means of resynchronising; a SYNCH that cannot get
    through leaves a confused master with no way out, so it is answered ERR_CMD_SYNCH.

    It must NOT clear the slot. Xcp_MainFunction polls only while pending_command.active, so
    clearing it would stop the polling and strand the integrator mid-erase: its callback never
    called again, never reporting completion, and a later PROGRAM_START starting a second operation
    on top of a first still running.

    Two assertions, and the second is the one that catches the tempting wrong fix: the poll count
    keeps rising after the SYNCH, and no response goes out when it finally completes.

    Fix round 1, finding 3 changed the timing here too: send(SYNCH)'s own Xcp_MainFunction call
    withholds the whole pending-command block while its ERR_CMD_SYNCH response is unconfirmed and
    in flight (the same buffer PROGRAM_START's own eventual answer would need), so it neither polls
    nor pushes an EV_CMD_PENDING that cycle. busy_calls=2 leaves exactly one more busy poll after
    that response is confirmed, before completion -- chosen precisely, and pinned by the
    calls_at_synch/state['calls'] arithmetic below, rather than left to a generous margin: this
    test needs to know exactly which Xcp_MainFunction call completes the operation, so that the
    mock can be reset immediately before it and 'nothing transmitted' means what it says instead of
    merely restating an earlier, unrelated, correctly transmitted EV_CMD_PENDING (DD54) that a
    looser count would leave sitting in call_args."""
    handle = pgm_handle()
    state = busy_then(handle, 0x00, busy_calls=2)
    program_start(handle)

    assert send(handle, (0xFC,))[0:2] == (0xFE, 0x00), 'ERR_CMD_SYNCH'

    # Confirms send()'s own ERR_CMD_SYNCH response. Nothing is queued behind it -- finding 3's
    # guard withheld the poll (and any EV_CMD_PENDING push) entirely while it was unconfirmed and
    # in flight -- so this one confirmation fully drains the pipeline.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # One busy poll now allowed to run: pushes and transmits its own EV_CMD_PENDING, confirmed in
    # turn, leaving the pipeline settled again immediately before the completing poll.
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    calls_at_synch = state['calls']
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # the completing poll: E_OK, but the command was abandoned

    assert state['calls'] > calls_at_synch, \
        'the integrator must be polled to completion; abandoning is not cancelling'
    assert transmitted(handle) is None, \
        'an abandoned command answers nobody -- the master has moved on'


def test_a_pgm_command_is_still_refused_while_an_abandoned_operation_finishes():
    """The state DD55 creates, which has no name on the wire: the operation is over as far as the
    master is concerned (Xcp_PgmAbandonPendingCommand returns pgm_state to XCP_PGM_IDLE) and not
    over as far as the flash is concerned (pending_command.active stays TRUE). Both facts are real
    and they are different, which is why one flag cannot carry them.

    That first fact is not independently asserted by reading state -- Xcp_Internal is not
    reachable from this CFFI harness (interface/Xcp.h does not include Xcp_Internal.h --
    test/clear_daq_list_test.py:80-92) -- but IS wire-observable once the abandoned operation
    actually finishes and releases the slot: Fix round 1, finding 1 found that the window this
    test used to stop at (still busy, active TRUE) never reaches PROGRAM_START's own sequence
    check (source/Xcp_Pgm.c:40, `if (pgm_state != XCP_PGM_IDLE)`) at all, so deleting the
    Xcp_PgmAbandonPendingCommand line that resets pgm_state passed every test in this file
    unnoticed -- the reset is invisible exactly as long as ERR_CMD_BUSY keeps refusing new
    commands, and becomes wire-visible the moment it stops. This test now covers both halves: busy
    while active, sequence-clean once it is not.

    While busy (PROGRAM_START as interloper, not GET_STATUS): a busy gate mistakenly written
    against pgm_state instead of pending_command.active would still pass
    test_a_command_arriving_mid_operation_is_answered_err_cmd_busy unchanged, because that test's
    whole window sits before any SYNCH, while pgm_state is still XCP_PGM_STARTING (not
    XCP_PGM_IDLE) either way -- a pgm_state-based gate and an active-based gate agree there. Only
    here, after SYNCH has put pgm_state back at XCP_PGM_IDLE while active stays TRUE, would such a
    mutant wrongly admit this second PROGRAM_START -- reaching the handler's own sequence check,
    finding pgm_state == XCP_PGM_IDLE, and starting a second flash operation on top of the first,
    still-running one.

    After completion: if Xcp_PgmAbandonPendingCommand never reset pgm_state, it would still read
    XCP_PGM_STARTING once active finally goes FALSE, and a fresh PROGRAM_START would be refused
    ERR_SEQUENCE (0xFE, 0x29) instead of accepted -- permanently, since nothing else ever writes
    pgm_state back to IDLE on an abandoned path (Xcp_PgmCompleteProgramStart, the only other
    writer, is skipped precisely because the command was abandoned)."""
    handle = pgm_handle()
    state = busy_then(handle, 0x00, busy_calls=2)
    program_start(handle)
    send(handle, (0xFC,))

    # Frees the transmit pipeline: SWS_Xcp_00859 carries one frame at a time, and the SYNCH
    # response above is still unconfirmed and in flight. Nothing is queued behind it (finding 3
    # withheld the poll this cycle too), so one confirmation fully drains it.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD2,))[0:2] == (0xFE, 0x10), \
        'a second flash operation must not start on top of one still running'

    # Drains this second exchange's own ERR_CMD_BUSY response the same way, then lets the FIRST
    # (abandoned) PROGRAM_START's polling run to actual completion: one more busy poll
    # (busy_calls=2), confirmed, then the completing poll.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # the completing poll: E_OK, but abandoned -- answers nobody

    assert transmitted(handle) is None, 'the abandoned operation still answers nobody on completion'

    # Now genuinely idle on both counts (active FALSE, pgm_state reset). A fresh PROGRAM_START
    # against an instantaneous integrator must be accepted, not refused ERR_SEQUENCE.
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, \
        'pgm_state must have been reset to XCP_PGM_IDLE by the abandoned operation, or this ' \
        'PROGRAM_START is refused ERR_SEQUENCE instead of accepted -- permanently, since nothing ' \
        'else would ever write it back'


def test_a_completing_poll_does_not_clobber_an_unconfirmed_err_cmd_busy():
    """Fix round 1, finding 3. cto_response.pdu_info is the one buffer every CTO response shares,
    including the ERR_CMD_BUSY packet DD55's own gate writes for an interloper. That gate stops
    the interloper's own HANDLER from touching the buffer, but says nothing about
    Xcp_MainFunction's own completion of the PENDING command doing so an instant later: if the
    integrator finishes while that ERR_CMD_BUSY response is still unconfirmed, an unguarded
    pending-command poll would let Xcp_PgmCompleteProgramStart overwrite it in place, in the exact
    frame CanIf is still holding for the master. Xcp_MainFunction now withholds the whole
    pending-command block (not merely the completion) while cto_response.successful_transmission_
    pending is TRUE, so the integrator is not even polled until the busy response is confirmed.

    busy_calls=1 means the integrator is ready to finish on the very poll that would otherwise run
    inside the SAME Xcp_MainFunction call that transmits the interloper's ERR_CMD_BUSY response
    for the first time (send() below is exactly that: one Xcp_CanIfRxIndication and one
    Xcp_MainFunction). Unguarded, that call completes the pending command before the BUSY bytes it
    just built ever reach CanIf_Transmit, so send() itself is where the corruption first surfaces
    -- the assertion below is not merely 'a frame that used to be ERR_CMD_BUSY got overwritten
    later', it is 'ERR_CMD_BUSY must be what is transmitted at all'. state['calls'] staying at 1 is
    the second, independent witness: the integrator must not be asked at all while unconfirmed."""
    handle = pgm_handle()
    state = busy_then(handle, 0x00, busy_calls=1)
    program_start(handle)  # call 1, the fast path inside the handler: E_NOT_OK -> deferred

    assert send(handle, (0xFD,))[0:2] == (0xFE, 0x10), 'ERR_CMD_BUSY, GET_STATUS as interloper'
    assert state['calls'] == 1, 'the integrator must not be polled while BUSY is still unconfirmed'

    # Confirming it frees the pipeline; the withheld poll now runs and completes for real.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_MainFunction()

    assert state['calls'] == 2, 'the integrator is polled once the pipeline is actually free'
    assert transmitted(handle)[0] == 0xFF, 'the PROGRAM_START response arrives only afterwards'


def probe_still_connected(handle):
    """GET_SEED (0xF8), used across the PROGRAM_RESET tests below as a direct, wire-independent
    witness of whether the module still considers itself connected.

    Chosen over reading the transmitted frame because GET_SEED reaches a mock
    (handle.xcp_get_seed) that is called if and only if Xcp_CanIfRxIndication actually dispatches
    it: source/Xcp.c's disconnected-state gate (~line 1493, 'the slave processes no XCP commands
    except for CONNECT') drops a non-CONNECT CTO before it ever reaches Xcp_PIDTable -- no
    response, no dispatch, no Det report -- so a module that (wrongly) already believes itself
    disconnected leaves this mock uncalled. Reading transmitted() instead would not work here:
    cto_response.pdu_info is one buffer shared by every CTO response (standing hazard 3), and the
    single-frame transmit pipeline (SWS_Xcp_00859) means GET_SEED's own answer, even if dispatched,
    would not reach CanIf_Transmit until whatever is already in flight is confirmed -- entangling
    the assertion with pipeline timing that has nothing to do with connection state."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))
    return handle.xcp_get_seed.call_count


def test_program_reset_is_accepted_from_xcp_pgm_idle():
    """Task 4, requirement 1. 1.1/1.6.5.1.4: 'This command may be used to force a slave device
    reset for other purposes.' DD57 makes PROGRAM_RESET the one PGM command in this sub-project not
    gated on a programming session: every other one requires a successful PROGRAM_START first, but
    this one is legal even when Xcp_Internal.pgm_state has never left XCP_PGM_IDLE.

    pgm_handle() connects but never sends PROGRAM_START, so pgm_state is XCP_PGM_IDLE here by
    construction. Mutation: gating the handler on XCP_PGM_ACTIVE (the mirror image of
    PROGRAM_START's own `if (pgm_state != XCP_PGM_IDLE)` check in source/Xcp_Pgm.c) answers
    ERR_SEQUENCE instead of 0xFF, which this test catches directly."""
    handle = pgm_handle()
    handle.can_if_transmit.reset_mock()

    program_reset(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_RESET must be accepted from XCP_PGM_IDLE'


def test_program_reset_is_also_accepted_from_xcp_pgm_active():
    """The complement of the test above, guarding the other direction DD57 requires: PROGRAM_RESET
    is not merely tolerated from IDLE, it must keep working from XCP_PGM_ACTIVE too, since ending an
    active session is this command's entire purpose. Mutation: copying PROGRAM_START's own
    `if (pgm_state != XCP_PGM_IDLE) ERR_SEQUENCE` gate into Xcp_DTOCmdPgmProgramReset -- the natural
    mistake a reviewer reaching for that handler as a template could make -- answers ERR_SEQUENCE
    (0xFE, 0x29) here instead of 0xFF, while leaving test_program_reset_is_accepted_from_xcp_pgm_idle
    passing (pgm_state IS XCP_PGM_IDLE there); verified by hand (see the task report).

    Xcp_CTOErrorMatrix[0xCF] (source/Xcp.c) also carries no XCP_INTERNAL_ERR_PGM_ACTIVE, for the
    same reason. That specific bit is NOT independently mutation-verifiable today: DD51's fourth
    disjunct (gating 42 commands on Xcp_Internal.pgm_state == XCP_PGM_ACTIVE, alongside the three
    session_status bits the generic ERR_PGM_ACTIVE gate already tests) has not been implemented by
    any task yet -- confirmed by reading source/Xcp.c's gate directly, and by hand: reinstating the
    bit here changes nothing today. It is set correctly regardless, because leaving it out is what
    DD57 requires and what stops the coming task from silently locking PROGRAM_RESET out of the one
    state it exists to leave -- see the task report.

    A real, completed PROGRAM_START is used to reach XCP_PGM_ACTIVE -- not merely asserted, since
    Xcp_Internal is not reachable from this CFFI harness (test/clear_daq_list_test.py:80-92)."""
    handle = pgm_handle()
    handle.can_if_transmit.reset_mock()  # fix round 1, finding 5: without this, a PROGRAM_START
    # that transmitted nothing would still read the setup guard's 0xFF off pgm_handle()'s own
    # stale CONNECT response (transmitted()'s docstring, test/pgm_deferred_test.py, names this
    # exact hazard), and this test would then assert about XCP_PGM_ACTIVE from a session that
    # never actually entered it.
    busy_then(handle, 0x00, busy_calls=0)
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_START must succeed to reach ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    busy_then(handle, 0x00, busy_calls=0, mock=handle.xcp_program_reset)
    handle.can_if_transmit.reset_mock()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_RESET must also be accepted from XCP_PGM_ACTIVE'


def test_program_reset_answers_before_disconnecting():
    """Task 4, requirement 2 -- rewritten in fix round 1. The first version of this test asserted
    only that PROGRAM_RESET's own response arrives, reasoning (correctly, but not far enough) that
    no ordering swap between building the response and flipping connection_status is visible
    through the transmit path alone (Xcp_FinalizeResPacket/Xcp_StartNextTransmission/
    Xcp_TransmitOneFrame never read it). That was true of the deferred, on-confirmation form fix
    round 0 shipped, and review measured what it actually cost: cto_response.pdu_info is one shared
    buffer and Xcp_CanIfRxIndication never transmits, so ANY command arriving before the next
    Xcp_MainFunction -- an unbounded window, Xcp_MainFunction being aperiodic -- silently replaced
    PROGRAM_RESET's own response in that buffer, and the slave then disconnected on THAT frame's
    confirmation instead: a following SYNCH left the master with ERR_CMD_SYNCH, a GET_STATUS with
    the GET_STATUS answer, and a second PROGRAM_RESET (the t7 retry 1.1/1.7.3.2.4 mandates) with
    ERR_CMD_BUSY -- in every case no answer to PROGRAM_RESET at all, and the master retrying into a
    slave that had already hung up. That divergence is requirement 2's actual substance, and this
    test now exercises exactly the race that exposed it.

    DD57 (fix round 1) answers it by disconnecting in the completion, immediately after the
    response is built, sharing Xcp_CTOCmdStdDisconnect's own unwind (Xcp_DisconnectSession,
    Xcp_Std.c). That form is immune for the same reason a genuine DISCONNECT's own answer already
    is: by the time Xcp_DTOCmdPgmProgramReset returns, Xcp_Internal.connection_status is already
    XCP_CONNECTION_STATE_DISCONNECTED, so SYNCH, sent next and before Xcp_MainFunction ever runs,
    is dropped by the disconnected-state gate inside Xcp_CanIfRxIndication (source/Xcp.c) before it
    can touch cto_response.pdu_info -- PROGRAM_RESET's own bytes, already sitting there, are what
    Xcp_MainFunction transmits.

    Mutation: reinstating fix round 0's deferred form (Xcp_PgmCompleteProgramReset setting a flag
    for Xcp_CanIfTxConfirmation to act on later, instead of disconnecting itself) makes the
    transmitted frame SYNCH's own ERR_CMD_SYNCH instead of PROGRAM_RESET's 0xFF -- verified by hand
    against that implementation directly (see the task report).

    The second assertion is carried over from fix round 0 unchanged: it is not vacuous (a handler
    that shortcuts straight to a Disconnect-shaped answer without calling the integrator would
    still pass the first assertion) but pins a different, narrower claim than requirement 2 itself,
    which review noted needed its own coverage rather than standing in for it."""
    handle = pgm_handle()
    handle.can_if_transmit.reset_mock()
    program_reset(handle)

    # Sent before Xcp_MainFunction ever runs, so nothing has flushed PROGRAM_RESET's own response
    # to CanIf yet. 1.1/1.7.1.1 exempts SYNCH from every busy gate this module has, precisely so it
    # always gets through when the module is still connected -- the disconnected-state gate is a
    # different, earlier check, and is the one this frame is actually testing.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFC,)))

    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, \
        "PROGRAM_RESET's own response must still reach the master, not SYNCH's ERR_CMD_SYNCH"
    assert handle.xcp_program_reset.call_count == 1, \
        'the response must come from actually calling Xcp_ProgramReset, not from a handler that ' \
        'shortcuts straight to a Disconnect-shaped answer'


def test_program_reset_disconnects_once_the_response_is_confirmed():
    """Task 4, requirement 3. The other half of DD57: PROGRAM_RESET must actually disconnect, and
    stay disconnected. Fix round 1 moved WHEN that happens -- Xcp_PgmCompleteProgramReset
    (Xcp_Pgm.c) now calls Xcp_DisconnectSession (Xcp_Std.c) itself, in the completion, before this
    response is ever confirmed, rather than deferring to Xcp_CanIfTxConfirmation -- but the
    end state this test checks is unchanged: by the time the exchange has fully settled
    (Xcp_MainFunction, then this response's own confirmation), the connection must be down.
    source/Xcp.c's disconnected-state gate inside Xcp_CanIfRxIndication is where this becomes
    observable at all -- 'the slave processes no XCP commands except for CONNECT' once
    Xcp_Internal.connection_status is XCP_CONNECTION_STATE_DISCONNECTED, silently dropping a
    non-CONNECT CTO with no dispatch, no response and no Det report.

    Mutation: a module that never disconnects at all (Xcp_PgmCompleteProgramReset's success branch
    never calling Xcp_DisconnectSession) leaves probe_still_connected's call_count at 1 here
    instead of 0."""
    handle = pgm_handle()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert probe_still_connected(handle) == 0, \
        'the connection must be down once PROGRAM_RESET\'s own response has been confirmed'


def test_program_reset_calls_no_reset_api_and_exposes_none():
    """Task 4, requirement 4. SWS_Xcp_00856 / DD50: unlike ASAM's own suggestion ('usually a
    hardware reset of the slave device is executed'), this module performs no device reset itself.
    An integrator wanting one performs it from within its own Xcp_ProgramReset implementation --
    the only hook this sub-project gives it for ending a programming sequence at all.

    There is no reset API in this module for a test to mock a call to and assert against, so the
    honest check is structural: handle.code.mocked is the exact set of extern functions
    interface/Xcp.h declares, built by the same cdef parse (interface/Xcp.h alone) this whole
    harness relies on -- not Xcp_Internal, and not a guess about the module's insides. The only
    name in that set with 'reset' in it may be Xcp_ProgramReset itself, which is the integrator's
    OWN polled hook (the module calling out to ASK whether the integrator is done, never a command
    FROM the module telling anything to reset) -- there is no second, separate trigger.

    Mutation-verified by hand (see the task report): temporarily adding a second declaration,
    `extern void Xcp_ResetDevice(void);`, under interface/Xcp.h's XCP_FLASH_PROGRAMMING_ENABLED
    guard makes this fail, since handle.code.mocked would then carry two reset-shaped names."""
    handle = pgm_handle()

    reset_like = {name for name in handle.code.mocked if 'reset' in name.lower()}

    assert reset_like == {'Xcp_ProgramReset'}, \
        'PROGRAM_RESET must not declare or expose any further, separate device-reset trigger'


def test_program_reset_leaves_pgm_state_ready_for_a_new_session():
    """Not one of the five requirements handed down for this task, but a direct consequence of
    them: Xcp_PgmCompleteProgramReset's success branch (Xcp_Pgm.c) resets Xcp_Internal.pgm_state to
    XCP_PGM_IDLE itself, before calling Xcp_DisconnectSession (Xcp_Std.c, shared with plain
    DISCONNECT) -- that shared function does not and must not touch pgm_state, since plain
    DISCONNECT has no programming session to end. Nothing else ever resets pgm_state once a session
    reaches XCP_PGM_ACTIVE -- Xcp_CTOCmdStdConnect and Xcp_CTOCmdStdDisconnect (Xcp_Std.c) do not
    touch it, and it is otherwise reset only by Xcp_Init. Without PROGRAM_RESET's own reset, a
    session that reached XCP_PGM_ACTIVE and was properly ended would leave pgm_state stuck at
    XCP_PGM_ACTIVE forever, silently, since disconnecting says nothing on the wire about it.

    The wire-observable consequence, since Xcp_Internal is not reachable from this CFFI harness
    (test/clear_daq_list_test.py:80-92): a master that reconnects after a completed PROGRAM_RESET
    and starts an entirely new session must be accepted, not refused ERR_SEQUENCE (0xFE, 0x29) by
    PROGRAM_START's own `if (pgm_state != XCP_PGM_IDLE)` check (source/Xcp_Pgm.c) -- which is
    exactly what a module that leaked the old ACTIVE state into the new session would do.

    Mutation: deleting `Xcp_Internal.pgm_state = XCP_PGM_IDLE;` from
    Xcp_PgmCompleteProgramReset's success branch (Xcp_Pgm.c) leaves this second PROGRAM_START
    refused ERR_SEQUENCE instead of accepted -- verified by hand (see the task report)."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    busy_then(handle, 0x00, busy_calls=0, mock=handle.xcp_program_reset)
    program_reset(handle)  # disconnects here, in the completion (DD57, fix round 1)
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    connect(handle)  # a fresh master, or the same one, starting an entirely new session

    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, \
        'pgm_state must have been reset to XCP_PGM_IDLE by PROGRAM_RESET, or this new session\'s ' \
        'own PROGRAM_START is refused ERR_SEQUENCE instead of accepted'


def test_program_reset_frees_a_dynamic_allocation_so_the_next_session_does_not_inherit_it():
    """Fix round 1, finding 2 -- the spec-compliance FAIL. Xcp_CTOCmdStdDisconnect's own unwind
    (Xcp_DisconnectSession, source/Xcp_Std.c) calls Xcp_DaqFreeAll under DAQ_DYNAMIC specifically so
    an allocation the disconnecting master never freed cannot leak into the next session.
    test_disconnect_frees_the_allocation_so_the_next_session_does_not_inherit_it
    (test/free_daq_test.py) is the precedent this test mirrors exactly, substituting PROGRAM_RESET
    for DISCONNECT and reusing its own helpers (dynamic_handle, allocate_directly).

    Fix round 0's Xcp_PgmDisconnectIfPending set only connection_status and pgm_state, skipping
    that unwind entirely -- a second door to XCP_CONNECTION_STATE_DISCONNECTED that released
    nothing, breaking the invariant source/Xcp_Std.c itself states ('released on Xcp_Init always,
    on FREE_DAQ always, and on DISCONNECT only under DAQ_DYNAMIC') by adding a fourth door. Review
    measured, on that tree: first session allocates 2 ODTs, PROGRAM_RESET, second session allocates
    1 -> maxOdt == 3 and odt[1].entryCount == 1, i.e. the new master silently inherits the previous
    session's lists and ODT entries.

    Fixed by sharing Xcp_DisconnectSession between Xcp_CTOCmdStdDisconnect and
    Xcp_PgmCompleteProgramReset (Xcp_Pgm.c), so the two doors cannot diverge again -- which this
    test pins directly rather than trusting the sharing to hold by inspection alone. Mutation:
    reverting Xcp_PgmCompleteProgramReset to set connection_status/pgm_state directly instead of
    calling Xcp_DisconnectSession reproduces the review's own measurement here (maxOdt == 3,
    odt[1].entryCount == 1) -- verified by hand (see the task report)."""
    handle = dynamic_handle(programming_enabled=True, daq_count=2, odt_count=4, odt_entries_count=2)
    allocate_directly(handle, odt_count=2, address=0x1000)

    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 2, 'the setup itself did not allocate'

    program_reset(handle)  # PROGRAM_RESET, answered and disconnected synchronously (DD57)

    connect(handle)  # the next master
    allocate_directly(handle, odt_count=1, address=0x2000)

    descriptor = handle.lib.Xcp_Ptr.config.daqList[0]

    assert descriptor.maxOdt == 1
    assert descriptor.odt[1].entryCount == 0
    assert descriptor.odt[1].odtEntry[0].address == handle.ffi.NULL
    assert descriptor.odt[1].odtEntry[0].length == 0


def test_program_prepare_passes_the_current_mta_and_codesize_to_the_integrator():
    """Task 5, requirement 1. 1.1/1.6.5.2.3: 'The MTA points to the begin of the volatile memory
    location where the code will be stored. The parameter Codesize specifies the size of the code
    that will be downloaded.' Design §4: 'Xcp_ProgramPrepare receives the current MTA and the
    Codesize from the request, rather than reading module state itself.'

    SET_MTA first establishes a known, non-zero MTA (0x12345678) -- reusing the harness's own
    address-setting command rather than reaching into Xcp_Internal, which is not reachable from
    this CFFI harness (test/clear_daq_list_test.py:80-92). Its own response is confirmed before
    PROGRAM_PREPARE is sent: PROGRAM_PREPARE's own Xcp_CTOErrorMatrix entry (source/Xcp.c) carries
    XCP_INTERNAL_ERR_CMD_BUSY, so an unconfirmed SET_MTA response left occupying the one-frame
    transmit pipeline (SWS_Xcp_00859) would answer ERR_CMD_BUSY instead of ever calling
    Xcp_ProgramPrepare at all.

    Both halves are checked against the SAME call, so a module that passed a stale or zero
    address, or the wrong Codesize, is caught either way."""
    handle = pgm_handle()
    handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00) +
                                        tuple(u32_to_array(0x12345678, 'LITTLE_ENDIAN'))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    program_prepare(handle, code_size=0x1234)

    address, code_size, _p_status_code = handle.xcp_program_prepare.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x12345678, 'the current MTA'
    assert code_size == 0x1234, "the request's own Codesize"


def test_program_prepare_answers_err_generic_on_a_non_zero_status_code():
    """Task 5, requirement 1's other half. 1.1/1.6.5.2.3: 'The slave device has to make sure that
    the target memory area is available and it is in a operational state which permits the
    download of code. If not, a ERR_GENERIC will be returned.'"""
    handle = pgm_handle()

    def target_area_unavailable(_address, _code_size, p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_program_prepare.side_effect = target_area_unavailable
    handle.can_if_transmit.reset_mock()

    program_prepare(handle, code_size=0x0010)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'


def test_program_prepare_defers_through_the_pending_slot_and_keeps_passing_codesize():
    """Not one of the four requirements handed down for this task, but the direct consequence of
    giving Xcp_ProgramPrepare a callback signature the existing deferred machinery was not built
    for: Xcp_PgmPollPendingCommand and Xcp_PgmCompletePendingCommand (source/Xcp_Pgm.c) switch on
    pending_command.pid, which carries nothing beyond the PID itself, active/abandoned/
    event_outstanding flags -- exactly enough for PROGRAM_START and PROGRAM_RESET, whose polled
    contract is pStatusCode alone. Xcp_ProgramPrepare's own contract additionally takes address
    and codeSize on EVERY call, not only the first (design §4), and the switch-based poll has no
    way back to the original request once the handler that parsed it has returned -- which is why
    Task 5 adds pending_command.program_prepare_code_size (source/Xcp_Internal.h) to carry it. The
    MTA needs no equivalent: Xcp_Internal.memory_transfer.address is already standing state the
    poll re-reads directly, stable for the duration because DD55's ERR_CMD_BUSY gate refuses any
    interloping SET_MTA.

    A module that never persisted Codesize (leaving it at 0, or at whatever the slot's memory
    happened to hold) would still pass every existing PROGRAM_START/PROGRAM_RESET test in this
    suite -- neither needs anything beyond pStatusCode -- so this is what actually exercises the
    difference. Isomorphic to
    test_the_response_appears_on_the_main_function_where_the_callback_completes
    (pgm_deferred_test.py), substituting Xcp_ProgramPrepare for Xcp_ProgramStart."""
    handle = pgm_handle()
    state = dict(calls=0)

    def busy_then_complete(_address, _code_size, p_status_code):
        # Mirrors pgm_deferred_test.py's own busy_then(..., busy_calls=2): call 1 is the fast
        # path inside the handler itself (program_prepare below), call 2 is the first
        # Xcp_MainFunction poll, and only call 3, the second poll, completes.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_prepare.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program_prepare(handle, code_size=0x2345)

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] != 0xFF, 'still busy on the second poll'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM_PREPARE response arrives'

    _address, code_size, _p_status_code = handle.xcp_program_prepare.call_args_list[-1][0]
    assert code_size == 0x2345, "Codesize must still be the request's own value on the completing poll"


def test_program_prepare_is_accepted_from_xcp_pgm_idle():
    """Task 5, requirement 2. 1.1/1.6.5.2.3 makes PROGRAM_PREPARE a precondition FOR programming,
    not a step within a session -- the master downloads code to volatile memory before
    PROGRAM_START -- so it is legal before PROGRAM_START has ever been sent. pgm_handle() connects
    but never sends PROGRAM_START, so pgm_state is XCP_PGM_IDLE here by construction.

    Mutation: copying PROGRAM_START's own `if (pgm_state != XCP_PGM_IDLE)` gate into
    Xcp_DTOCmdPgmProgramPrepare would not even fire here (pgm_state IS XCP_PGM_IDLE already) -- the
    mutant is only caught by test_program_prepare_is_also_accepted_from_xcp_pgm_active below, this
    test's complement."""
    handle = pgm_handle()
    handle.can_if_transmit.reset_mock()

    program_prepare(handle, code_size=0x0010)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_PREPARE must be accepted from XCP_PGM_IDLE'


def test_program_prepare_is_also_accepted_from_xcp_pgm_active():
    """Task 5, requirement 2's other direction. PROGRAM_PREPARE must keep working once a session
    is already open, not merely before one starts -- nothing in 1.1/1.6.5.2.3 or design §4 closes
    it off once XCP_PGM_ACTIVE, and an integrator downloading a second block of code mid-session
    still needs it. Mutation: gating the handler on `pgm_state != XCP_PGM_IDLE` (PROGRAM_START's
    own check, the natural mistake a reviewer reusing that handler as a template could make)
    answers ERR_SEQUENCE (0xFE, 0x29) here instead of 0xFF, while leaving
    test_program_prepare_is_accepted_from_xcp_pgm_idle passing (pgm_state IS XCP_PGM_IDLE there).

    A real, completed PROGRAM_START reaches XCP_PGM_ACTIVE -- not merely asserted, since
    Xcp_Internal is not reachable from this CFFI harness (test/clear_daq_list_test.py:80-92)."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_START must succeed to reach ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program_prepare(handle, code_size=0x0010)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_PREPARE must also be accepted from XCP_PGM_ACTIVE'


@pytest.mark.parametrize('payload', ((0xCC,), (0xCC, 0x00), (0xCC, 0x00, 0x00)))
def test_program_prepare_below_four_bytes_answers_err_cmd_syntax(payload):
    """Task 5, requirement 3. 1.1/1.6.5.2.3's request is command code, one unused byte, then a
    WORD Codesize: four bytes. Enforced by the generic ERR_CMD_SYNTAX gate already in
    Xcp_CanIfRxIndication, against Xcp_Ptr->general->ctoInfo[0xCC]'s own minimum request size
    (script/source_cfg.c.jinja2: 4 for PROGRAM_PREPARE) -- nothing PROGRAM_PREPARE-specific was
    written for this, so this test is what actually confirms the generated minimum is 4 and not
    something smaller that would let a truncated request reach Xcp_ProgramPrepare."""
    handle = pgm_handle()

    assert send(handle, payload)[0:2] == (0xFE, 0x21), 'ERR_CMD_SYNTAX'


def test_an_active_programming_session_makes_the_pgm_active_gate_fire():
    """DD51. The ERR_PGM_ACTIVE machinery has existed since before SP1 and has never had a
    programming session to trigger it. Reached through Xcp_Internal.pgm_state as a fourth
    disjunct beside the three session-status bits Xcp_CanIfRxIndication's gate already tests, NOT
    by adding a fourth bit to the session status byte: 1.1/1.6.1.2.3 is a wire format that
    GET_STATUS reports, and a programming session is module state, not one of its bits.

    GET_SEED (0xF8) is the probe: its own Xcp_CTOErrorMatrix entry (source/Xcp.c) carries
    XCP_INTERNAL_ERR_PGM_ACTIVE, the same bit the pre-existing session_status-driven trigger
    already exercises for this exact command (asam_error_matrix_test.py,
    TestGetSeedErrorHandling::test_returns_err_pgm_active) -- so a refusal here pins the new
    pgm_state-driven trigger alongside a form of the gate that already has coverage, rather than
    inventing an unrelated observable.

    A real, completed PROGRAM_START reaches XCP_PGM_ACTIVE -- not merely asserted, since
    Xcp_Internal is not reachable from this CFFI harness (test/clear_daq_list_test.py:80-92)."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_START must succeed to reach ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xF8, 0x00, 0x01))[0:2] == (0xFE, 0x12), 'ERR_PGM_ACTIVE'


@pytest.mark.parametrize('pid, name, payload', (
    (0xF6, 'SET_MTA', (0xF6, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    (0xD1, 'PROGRAM_CLEAR', (0xD1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    (0xD0, 'PROGRAM', (0xD0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    (0xC9, 'PROGRAM_MAX', (0xC9, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    (0xCA, 'PROGRAM_NEXT', (0xCA, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    (0xF5, 'UPLOAD', (0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    (0xF3, 'BUILD_CHECKSUM', (0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)),
))
def test_the_commands_required_during_programming_are_not_pgm_active_gated(pid, name, payload):
    """1.1/1.6.5.1.1 lists the commands that 'must always be available during a memory programming
    sequence' -- SET_MTA, PROGRAM_CLEAR, PROGRAM, PROGRAM_MAX or PROGRAM_NEXT, optionally UPLOAD
    and BUILD_CHECKSUM. Gating any of them behind ERR_PGM_ACTIVE would make a programming session
    impossible to conduct.

    Xcp_CTOErrorMatrix (source/Xcp.c) is declared `static` and reaches no header interface/Xcp.h
    includes, so it is not visible to this CFFI harness (test/conftest.py builds its cdef from
    interface/Xcp.h alone) -- an earlier draft of this test read it directly and could not have
    run. Asserted instead by actually sending each command during an active session and checking
    the answer is not ERR_PGM_ACTIVE (0xFE, 0x12): four of these seven (PROGRAM_CLEAR, PROGRAM,
    PROGRAM_MAX, PROGRAM_NEXT) are unimplemented until SP4b and answer ERR_CMD_UNKNOWN
    (0xFE, 0x20) today, which is not ERR_PGM_ACTIVE either and keeps this assertion honest and
    future-proof once SP4b implements them for real.

    Each payload is padded to 8 bytes (this suite's default MAX_CTO) and at or above every one of
    these seven's own minimum request size (script/source_cfg.c.jinja2: 2 to 8 bytes) -- anything
    short enough to trip ERR_CMD_SYNTAX first would make the assertion vacuous, since that gate is
    checked in Xcp_CanIfRxIndication before ERR_PGM_ACTIVE and would refuse the command for an
    unrelated reason without ever reaching the gate this test exists to check."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_START must succeed to reach ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, payload)[0:2] != (0xFE, 0x12), \
        '%s must stay available during a programming sequence' % name

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .pgm_deferred_test import pgm_handle, program_start, transmitted, busy_then


def send(handle, request):
    """A request, one main function, and the frame it produced (or None)."""
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    return transmitted(handle)


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

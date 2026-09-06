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
    the one being fixed, and invisible to a test that only reads the busy answer."""
    handle = pgm_handle()
    state = busy_then(handle, 0x00, busy_calls=2)
    program_start(handle)
    send(handle, (0xFD,))

    # Frees the transmit pipeline before pumping the completion: SWS_Xcp_00859 carries one frame
    # at a time, and send() above leaves its own ERR_CMD_BUSY response unconfirmed. Confirming it
    # reveals the EV_CMD_PENDING (DD54) that the same Xcp_MainFunction call queued behind it, which
    # is ALSO still unconfirmed and so ALSO occupies the pipeline -- two confirms, not one, or the
    # eventual positive response would be built correctly but stay queued forever, never reaching
    # CanIf_Transmit: a false failure with nothing to do with the busy gate this test is actually
    # about (pgm_deferred_test.py's
    # test_the_response_appears_on_the_main_function_where_the_callback_completes documents the
    # same pipeline rule for the same reason, with one fewer frame ahead of the response).
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
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

    busy_calls=3 leaves exactly one more busy poll (call 3) after the one send(SYNCH) itself
    causes (call 2, following program_start's own fast-path call 1) before completion (call 4) --
    chosen precisely, and pinned by the calls_at_synch/state['calls'] arithmetic below, rather than
    left to a generous margin: this test needs to know exactly which Xcp_MainFunction call
    completes the operation, so that the mock can be reset immediately before it and 'nothing
    transmitted' means what it says instead of merely restating an earlier, unrelated, correctly
    transmitted EV_CMD_PENDING (DD54) that a looser count would leave sitting in call_args."""
    handle = pgm_handle()
    state = busy_then(handle, 0x00, busy_calls=3)
    program_start(handle)

    assert send(handle, (0xFC,))[0:2] == (0xFE, 0x00), 'ERR_CMD_SYNCH'

    # Drains everything already in flight from the SYNCH exchange above -- SWS_Xcp_00859 carries
    # one frame at a time. Confirming send()'s own ERR_CMD_SYNCH response reveals the EV_CMD_PENDING
    # (DD54) that the same Xcp_MainFunction call queued behind it (poll 2, still busy); confirming
    # THAT is the module's own event, so it correctly clears pending_command.event_outstanding.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # One further busy poll (call 3 of 3): pushes and transmits, then confirms, its own
    # EV_CMD_PENDING, leaving the pipeline settled again immediately before the completing poll.
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    calls_at_synch = state['calls']
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # call 4: E_OK, but the command was abandoned

    assert state['calls'] > calls_at_synch, \
        'the integrator must be polled to completion; abandoning is not cancelling'
    assert transmitted(handle) is None, \
        'an abandoned command answers nobody -- the master has moved on'


def test_a_pgm_command_is_still_refused_while_an_abandoned_operation_finishes():
    """The state DD55 creates, which has no name on the wire: the operation is over as far as the
    master is concerned (Xcp_PgmAbandonPendingCommand returns pgm_state to XCP_PGM_IDLE) and not
    over as far as the flash is concerned (pending_command.active stays TRUE). Both facts are real
    and they are different, which is why one flag cannot carry them.

    That first fact is not independently asserted here. Xcp_Internal is not reachable from this
    CFFI harness (interface/Xcp.h does not include Xcp_Internal.h --
    test/clear_daq_list_test.py:80-92), and by DD55's own construction pgm_state cannot be
    observed on the wire either while active stays TRUE: every command but SYNCH is answered
    ERR_CMD_BUSY straight from pending_command.active, before dispatch ever reaches
    PROGRAM_START's handler, where pgm_state would otherwise be consulted. That is not a gap in
    this test; it is the state DD55's docstring calls having 'no name on the wire'.

    What IS observable, and the reason PROGRAM_START rather than GET_STATUS is the interloper
    here: a busy gate mistakenly written against pgm_state instead of pending_command.active would
    still pass test_a_command_arriving_mid_operation_is_answered_err_cmd_busy unchanged, because
    that test's whole window sits before any SYNCH, while pgm_state is still XCP_PGM_STARTING (not
    XCP_PGM_IDLE) either way -- a pgm_state-based gate and an active-based gate agree there. Only
    here, after SYNCH has put pgm_state back at XCP_PGM_IDLE while active stays TRUE, would such a
    mutant wrongly admit this second PROGRAM_START -- reaching the handler's own sequence check,
    finding pgm_state == XCP_PGM_IDLE, and starting a second flash operation on top of the first,
    still-running one."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=20)
    program_start(handle)
    send(handle, (0xFC,))

    # Frees the transmit pipeline: SWS_Xcp_00859 carries one frame at a time, and the SYNCH
    # response above (and the EV_CMD_PENDING it leaves queued behind it, DD54) are both still
    # unconfirmed. Without this the second send() below could transmit nothing at all, for a
    # reason that has nothing to do with the busy gate under test here.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD2,))[0:2] == (0xFE, 0x10), \
        'a second flash operation must not start on top of one still running'

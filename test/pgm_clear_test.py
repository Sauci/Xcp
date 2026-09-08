#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import DefaultConfig, u32_to_array
from .conftest import XcpTest
from .download_test import connect
from .pgm_deferred_test import program_start, transmitted
from .pgm_session_test import send


def pgm_clear_handle(**kwargs):
    """A connected slave with the flash-programming gate on and PROGRAM_CLEAR enabled.

    Cannot reuse pgm_deferred_test.pgm_handle(): that helper forces
    xcp_program_clear_api_enable=False as a literal keyword, which is what SP4a's generation guard
    (DD69) required of every gate-on configuration before this task existed to answer PROGRAM_CLEAR
    for real -- and passing xcp_program_clear_api_enable again through **kwargs to override it would
    collide with that literal (TypeError: got multiple values for keyword argument), not shadow it.

    pgm_handle() itself is left exactly as SP4a wrote it. test/pgm_session_test.py's
    test_the_commands_required_during_programming_are_not_pgm_active_gated and
    test/pgm_configuration_test.py's GATE_ON-based tests assert against it and were deliberately
    written to tolerate PROGRAM_CLEAR staying unimplemented there (their own docstrings say so), so
    changing its default would be an unreviewed, blast-radius change to files outside this task for
    no benefit this suite needs.

    xcp_program_api_enable and xcp_program_max_api_enable stay forced False here: PROGRAM and
    PROGRAM_MAX remain unimplemented until later tasks, and DD69's guard still refuses them
    alongside programming.enabled."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   programming_enabled=True,
                                   xcp_program_clear_api_enable=True,
                                   xcp_program_api_enable=False,
                                   xcp_program_max_api_enable=False,
                                   **kwargs))
    connect(handle)
    return handle


def program_clear(handle, mode, clear_range):
    """PROGRAM_CLEAR (Task 2), without pumping Xcp_MainFunction -- mirrors pgm_session_test.py's
    own program_prepare() and for the same reason: a test needs to pump Xcp_MainFunction and confirm
    transmissions itself, at its own pace. Byte 1 is the mode; bytes 2-3 are the request's reserved
    WORD; the clear range is the DWORD at bytes 4-7 (1.1/1.6.5.1.2), in this suite's default byte
    order (LITTLE_ENDIAN, test/parameter.py's DefaultConfig)."""
    handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xD1, mode, 0x00, 0x00) +
                                        tuple(u32_to_array(clear_range, 'LITTLE_ENDIAN'))))


def _active_session_with_mta(handle, address=0x12345678):
    """Opens a programming session and points the MTA at `address`, confirming both responses so
    the one-frame transmit pipeline (SWS_Xcp_00859) is free before the PROGRAM_CLEAR request under
    test -- PROGRAM_CLEAR's own Xcp_CTOErrorMatrix entry (source/Xcp.c) carries
    XCP_INTERNAL_ERR_CMD_BUSY, so an unconfirmed response left occupying that one slot would answer
    ERR_CMD_BUSY instead of ever reaching Xcp_ProgramClear.

    Mirrors pgm_session_test.py's own PROGRAM_PREPARE setup
    (test_program_prepare_passes_the_current_mta_and_codesize_to_the_integrator and
    test_program_prepare_is_also_accepted_from_xcp_pgm_active), extended with the PROGRAM_START
    PROGRAM_CLEAR needs and PROGRAM_PREPARE does not (DD67's session gate, 1.1/1.6.5.1.1).
    xcp_program_start's mock needs no configuration here: conftest.py's own default return_value
    (E_OK) already completes it synchronously, on the very first call, with the status code its
    handler locally initialises to zero and the mock's return value alone never touches."""
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_START must succeed to reach ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00) +
                                        tuple(u32_to_array(address, 'LITTLE_ENDIAN'))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def test_program_clear_is_refused_err_sequence_before_program_start_succeeds():
    """1.1/1.6.5.1.1 requires PROGRAM_CLEAR, PROGRAM, PROGRAM_NEXT and PROGRAM_MAX refused until
    PROGRAM_START has succeeded. SP4a implemented Xcp_Internal.pgm_state for exactly this gate and
    had no command to test it against (design doc Section 2: 'SP4a implemented that gate with no
    users; SP4b is its first user') -- this is that first real user, against a real handler.

    pgm_clear_handle() connects but never sends PROGRAM_START, so pgm_state is XCP_PGM_IDLE here by
    construction -- the same setup test_program_prepare_is_accepted_from_xcp_pgm_idle
    (pgm_session_test.py) uses to prove the OPPOSITE command's absence of this gate.

    Mutation: deleting the `pgm_state != XCP_PGM_ACTIVE` check (or inverting it) in
    Xcp_DTOCmdPgmProgramClear makes the handler fall through to the mode check and then to
    Xcp_ProgramClear, whose mock defaults to E_OK with a zero status code (conftest.py) -- the
    response becomes (0xFF,), not (0xFE, 0x29), and the call_count assertion below also catches it
    directly."""
    handle = pgm_clear_handle()

    assert send(handle, (0xD1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x29), \
        'ERR_SEQUENCE'
    assert handle.xcp_program_clear.call_count == 0, 'the integrator must not be reached either'


def test_program_clear_passes_the_current_mta_and_clear_range_to_the_integrator():
    """1.1/1.6.5.1.2, absolute access mode: 'The MTA points to the start of a memory sector... The
    Clear Range indicates the length of the memory part to be cleared.' Design Section 4 copies
    Xcp_ProgramPrepare's own polled contract, which likewise takes its arguments from the request
    and from Xcp_Internal.memory_transfer.address rather than reading module state itself.

    Both halves are checked against the SAME call, so a module that passed a stale or zero address,
    or the wrong clear range -- e.g. reading the reserved WORD at bytes 2-3 instead of the DWORD at
    4-7 -- is caught either way. Mirrors
    test_program_prepare_passes_the_current_mta_and_codesize_to_the_integrator
    (pgm_session_test.py)."""
    handle = pgm_clear_handle()
    _active_session_with_mta(handle, address=0x12345678)

    program_clear(handle, mode=0x00, clear_range=0xABCD1234)

    address, clear_range, _p_status_code = handle.xcp_program_clear.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x12345678, 'the current MTA'
    assert clear_range == 0xABCD1234, "the request's own clear range"


def test_program_clear_defers_through_the_pending_slot_and_keeps_passing_the_clear_range():
    """Xcp_ProgramClear's contract takes address and clearRange on EVERY call, not only the first
    (design Section 4) -- the same shape Xcp_ProgramPrepare's own equivalent test pins
    (test_program_prepare_defers_through_the_pending_slot_and_keeps_passing_codesize,
    pgm_session_test.py). Xcp_PgmPollPendingCommand (Xcp_Pgm.c) has no way back to the original
    request once the handler that parsed it has returned, which is why the clear range has to live
    in pending_command's union (source/Xcp_Internal.h, Task 2) across poll cycles.

    A module that never persisted the clear range -- leaving it 0, or aliased onto
    program_prepare_code_size's storage in a union that was keyed wrong -- would still pass every
    PROGRAM_START/PROGRAM_RESET test and even the synchronous args test above, neither of which
    needs more than one call. This is what actually exercises the difference: the mutation is
    reading Xcp_Internal.pending_command.args.program_prepare_code_size (the WRONG union member) in
    Xcp_PgmPollPendingCommand's PROGRAM_CLEAR case instead of .program_clear_range, which this test
    catches on the completing poll's own call_args_list[-1] even though the FIRST call (inside the
    handler, before anything is stored in the union) still carries the right value and would pass a
    weaker assertion checking only that one."""
    handle = pgm_clear_handle()
    _active_session_with_mta(handle, address=0x12345678)

    state = dict(calls=0)

    def busy_then_complete(_address, _clear_range, p_status_code):
        # call 1: the fast path inside the handler itself (program_clear below); call 2: the first
        # Xcp_MainFunction poll; only call 3, the second poll, completes -- mirrors
        # test_program_prepare_defers_through_the_pending_slot_and_keeps_passing_codesize.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_clear.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program_clear(handle, mode=0x00, clear_range=0x89ABCDEF)

    handle.lib.Xcp_MainFunction()
    # Fix round 2: != 0xFF also passes on an ERROR response, not only on the intended 'still busy,
    # no response yet, only DD54's own EV_CMD_PENDING went out'. == 0xFD asserts what this line
    # actually means; a missing frame still TypeErrors rather than passing vacuously either way.
    assert transmitted(handle)[0] == 0xFD, 'still busy on the second poll: only EV_CMD_PENDING (DD54)'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM_CLEAR response arrives'

    address, clear_range, _p_status_code = handle.xcp_program_clear.call_args_list[-1][0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x12345678, \
        'the MTA must still be the current one on the completing poll'
    assert clear_range == 0x89ABCDEF, \
        "the clear range must still be the request's own value on the completing poll"


@pytest.mark.parametrize('mode', (0x02, 0x80, 0xFF))
def test_program_clear_unrecognised_mode_is_refused_err_out_of_range_without_calling_the_integrator(mode):
    """Fix round 2, task-2-review.md finding 1. 1.6.5.1.2's mode-byte table has exactly two rows,
    0x00 and 0x01 -- an enumeration of the values this command recognises, not a bit field with
    reserved-but-harmless positions. Every value other than those two is therefore unrecognised: a
    master that sets a vendor extension, a future ASAM revision's mode bit, or simply a mis-encoded
    frame is asking for a mode this slave cannot honour, and a handler that fell through to absolute
    mode for anything it did not specifically refuse would erase `clearRange` bytes at the MTA on
    that master's behalf and report success -- confirmed against a build carrying exactly that bug
    (task-2-review.md): modes 0x02, 0x03, 0x80 and 0xFF each reached Xcp_ProgramClear once and were
    answered (0xFF,).

    Answered ERR_OUT_OF_RANGE, whose own 1.7.3.2.5 row lists the action 'retry other parameter' --
    correct for any mode byte this slave does not recognise. call_count == 0 is the assertion that
    actually matters: a handler that erased first and refused afterwards would still pass a
    wire-only assertion on the response code alone.

    SP4c Task 5 narrows this parametrisation: 0x01 (functional access mode, DD84/DD93) used to be
    included here alongside 0x02/0x80/0xFF, pinning SP4b's own DD67 refusal of every non-zero mode
    byte with no exception. That task implements the 0x01 branch this file's own
    test/pgm_functional_test.py now covers in full -- including the still-refused case, when
    xcp_program_clear_functional_api_enable is False -- so 0x01 is removed from here rather than
    left asserting a refusal this build may no longer produce. 0x02/0x80/0xFF are untouched by that
    task and stay refused unconditionally, which is exactly what this narrowed parametrisation still
    checks.

    Mutation: SP4c Task 5 inserts its own `mode == 0x01u` branch ahead of this catch-all, so 0x01 is
    intercepted by ORDER rather than by an explicit exclusion written into this line -- this
    catch-all still reads the same `!= 0x00u` it always has. Disabling that new, earlier branch
    (making it permanently false) leaves 0x01 falling into THIS catch-all too, and this
    parametrisation would need a fourth case to notice; that specific regression is what
    test/pgm_functional_test.py's own test 1 catches instead, in isolation, since call_count there
    names the callback actually reached. What this catch-all's own mutation still covers is
    unchanged: reverting `!= 0x00u` to admit any of 0x02/0x80/0xFF as absolute mode reaches
    Xcp_ProgramClear and answers (0xFF,), not (0xFE, 0x22), with call_count == 1, not 0, for each of
    these three cases."""
    handle = pgm_clear_handle()
    _active_session_with_mta(handle)

    assert send(handle, (0xD1, mode, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22), \
        'ERR_OUT_OF_RANGE'
    assert handle.xcp_program_clear.call_count == 0, \
        'an unrecognised mode must never reach the integrator'


def test_program_clear_answers_err_access_denied_on_a_non_zero_status_code():
    """Xcp_ProgramClear's own polled contract (design Section 4, copied from
    Xcp_StoreCalibrationDataToNonVolatileMemory): E_OK with a non-zero status code means the erase
    finished, but failed. Fix round 1: 1.1/1.6.5.1.2 names no error at all for this case -- it
    describes the modes and parameters and stops -- so 1.7.3.2.5's own PROGRAM_CLEAR row is the
    only guide, and this module answers a code that row actually lists (ERR_CMD_BUSY,
    ERR_CMD_SYNTAX, ERR_OUT_OF_RANGE, ERR_ACCESS_DENIED, ERR_ACCESS_LOCKED, ERR_SEQUENCE): no
    deviation, unlike PROGRAM_RESET's DD57. ERR_ACCESS_DENIED specifically, not merely because it
    is one of the six: the 1.0 error-code table defines it as "The memory location is not
    accessible", the precise statement of an integrator that could not erase the sector the master
    asked for -- where PROGRAM_START's and PROGRAM_PREPARE's own ERR_GENERIC above answers a
    different question (1.6.5.1.1 names it for a slave "not in a state which permits
    programming", a statement about the slave, not the memory).

    Mutation: an Xcp_PgmCompleteProgramClear that ignores statusCode and always builds the positive
    response makes this answer (0xFF,) instead of (0xFE, 0x24)."""
    handle = pgm_clear_handle()
    _active_session_with_mta(handle)

    def erase_failed(_address, _clear_range, p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_program_clear.side_effect = erase_failed

    assert send(handle, (0xD1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x24), \
        'ERR_ACCESS_DENIED'


@pytest.mark.parametrize('payload', tuple((0xD1,) + (0x00,) * n for n in range(7)))
def test_program_clear_below_eight_bytes_answers_err_cmd_syntax(payload):
    """1.1/1.6.5.1.2's request is command code, mode, a reserved WORD, then a DWORD clear range:
    eight bytes. Enforced by the generic ERR_CMD_SYNTAX gate already in Xcp_CanIfRxIndication,
    against Xcp_Ptr->general->ctoInfo[0xD1]'s own minimum request size (script/source_cfg.c.jinja2:
    8 for PROGRAM_CLEAR) -- nothing PROGRAM_CLEAR-specific was written for this, so this test is what
    actually confirms the generated minimum is 8 and not something smaller that would let a
    truncated request reach Xcp_ProgramClear. Mirrors
    test_program_prepare_below_four_bytes_answers_err_cmd_syntax (pgm_session_test.py).

    No session is opened first: the syntax gate runs in Xcp_CanIfRxIndication before Xcp_PIDTable is
    even consulted (source/Xcp.c), so it fires regardless of pgm_state -- covered directly by
    parametrising down to a single-byte request, which a pgm_state check alone could never explain
    an ERR_CMD_SYNTAX answer for.

    Mutation: script/source_cfg.c.jinja2's PROGRAM_CLEAR ctoInfo row generating a minimum smaller
    than 8 (e.g. the trailing `0x08u` changed to `0x01u`) lets a short request past the syntax gate
    and into Xcp_DTOCmdPgmProgramClear instead of being refused before dispatch -- verified by hand
    for this report by making exactly that edit: with no session open (as here), the one-byte
    `payload0` case then answers (0xFE, 0x29) ERR_SEQUENCE, reading pgm_state before it ever reaches
    the mode byte one byte past what the request actually carried; a variant of this test that
    opened a session first would instead reach that out-of-bounds read. Either way the answer is no
    longer (0xFE, 0x21), which is what this assertion actually checks."""
    handle = pgm_clear_handle()

    assert send(handle, payload)[0:2] == (0xFE, 0x21), 'ERR_CMD_SYNTAX'

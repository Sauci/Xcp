#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Originally SP4a Task 6, deliverable (a): design doc Section 9
(docs/superpowers/specs/2026-09-06-xcp-pgm-sp4a-design.md), acceptance criteria 2, 3, 5 and 7,
exercised together rather than one at a time. Extended by SP4b Task 6, deliverable (a): design doc
Section 9 (docs/superpowers/specs/2026-09-07-xcp-pgm-sp4b-design.md), acceptance criteria 2
(PROGRAM_CLEAR/PROGRAM conjuncts), 3, 5 and 6 -- see the second half of this docstring, below the
resource-protection finding, for what SP4b actually added and why it extends the walk rather than
replacing it.

Every other file in either sub-project's test suite proves ONE command, or one pair of them, in
isolation: pgm_deferred_test.py the deferred machinery underneath PROGRAM_START alone,
pgm_session_test.py the busy/SYNCH/active/reset gates one at a time, pgm_clear_test.py and
pgm_program_test.py PROGRAM_CLEAR and PROGRAM/PROGRAM_NEXT each against a handle built fresh for
that one exchange. None of them shows the sequence COMPOSES -- that a master walking CONNECT
through an erase, a program, and PROGRAM_RESET, against an integrator that is genuinely slow, gets
one coherent conversation out the other end rather than several correct answers to several
separate questions. That is what test_a_real_masters_full_programming_sequence_composes_end_to_end
below is for, and it is why it is one long test rather than several short ones: the whole point is
that nothing resets the module in between.

**A resource-protection finding, now historical -- read this before wondering why the test below
still does not set resource_protection_programming.** The original SP4a task brief asked for the
PGM resource to be configured protected so GET_SEED/UNLOCK would be 'real rather than decorative'.
At the time this docstring was first written, that configuration could not be generated at all:
script/source_cfg.c.jinja2 refused `resource_protection.programming` outright in any build with
`programming.enabled` set (final-review finding 2), for the reason described next.

The wall, now dissolved (DD83): this module's README ('Key lifetime') used to document that an
UNLOCK's effect 'is discarded after the command FOLLOWING the UNLOCK sequence has been executed',
which source/Xcp.c implemented as Xcp_ClearProtectionStatus() running after every dispatched
command except UNLOCK itself -- so one GET_SEED/UNLOCK round unlocked exactly the ONE command sent
right after it, never more. PROGRAM_START was that one command, and dispatching it (immediately, in
the handler, before it ever defers) is what spent it. By the time the session reached
XCP_PGM_ACTIVE and PROGRAM_RESET was due, PGM was locked again, and there was no way to re-unlock
it: GET_SEED and UNLOCK both carried XCP_INTERNAL_ERR_PGM_ACTIVE in their own Xcp_CTOErrorMatrix
rows (source/Xcp.c) -- pre-existing, not touched by SP4a -- so DD51's own ACTIVE-session trigger
refused both of them right back. Measured directly at the time (see task-6-report.md): a
PROGRAM_RESET sent in this state answered (0xFE, 0x25), ERR_ACCESS_LOCKED, not the positive
response DD57 promises.

That was a genuine interaction between two mechanisms that each predated SP4a and were each correct
on their own -- resource protection's one-shot lifetime, and the pre-existing ERR_PGM_ACTIVE bit on
GET_SEED/UNLOCK -- so fixing it meant changing the unlock lifetime for every resource group, not
something a test could repair by itself. DD79 is that fix: a granted resource now lasts the whole
session instead of the single command following the unlock, so the GET_SEED/UNLOCK round that
admits PROGRAM_START is still in effect when PROGRAM_RESET needs it, and the dead end above no
longer forms.
test/pgm_protected_acceptance_test.py::test_a_protected_pgm_resource_conducts_a_full_programming_sequence_end_to_end
now proves exactly that: CONNECT, PROGRAM_START refused before any unlock (protection proven live),
GET_SEED/UNLOCK, PROGRAM_START, PROGRAM_CLEAR, PROGRAM and PROGRAM_RESET, every step answering
positively.

What this file still does, and why it still does not set resource_protection_programming: the test
below is about the RICH sequence composing -- GET_PGM_PROCESSOR_INFO, a genuinely interrupted and
polled PROGRAM_START, a slow PROGRAM_CLEAR, a real multi-frame PROGRAM/PROGRAM_NEXT block, a
zero-element PROGRAM, PROGRAM_RESET and the disconnect it triggers -- not whether protection
survives across it. Layering resource_protection_programming onto this test would conflate two
concerns this suite now keeps apart on purpose: this file proves the rich command sequence
composes; pgm_protected_acceptance_test.py proves protection survives a deliberately minimal one,
including the exact fact this paragraph used to say nothing could prove -- GET_SEED/UNLOCK actually
GATING a PGM command (PROGRAM_START answers ERR_ACCESS_LOCKED there before the unlock). The test
below still sends a real, wire-correct GET_SEED/UNLOCK exchange for the PGM resource where the
original brief places it (CONNECT, then this, then SET_MTA), proving the handshake itself is
correct -- but, as before, on a build where nothing gates on it.

Every exchange below follows the standing rule this sub-project's five prior tasks paid for the
hard way (task reports in .superpowers/sdd/2026-09-06-xcp-pgm-sp4a/): reset can_if_transmit
immediately before the exchange under test, read transmitted()'s single most recent frame rather
than scanning call_args_list, confirm every response before the next request (the transmit
pipeline carries one frame at a time, SWS_Xcp_00859), and pump Xcp_MainFunction wherever a
transmission must have happened, since Xcp_CanIfRxIndication itself never transmits.

**SP4b, Task 6 (docs/superpowers/specs/2026-09-07-xcp-pgm-sp4b-design.md, Section 9), extends the
walk above through a real erase and program rather than replacing it.** Everything the paragraphs
above describe -- the resource-protection wall, the GET_SEED/UNLOCK handshake sent regardless of
it, the five SP4a-era mutations, the six stale-frame traps -- is unchanged and still lives in
test_a_real_masters_full_programming_sequence_composes_end_to_end below, which is now longer, not
different: the same one continuous handle now also carries GET_PGM_PROCESSOR_INFO right after
CONNECT, and, once PROGRAM_START has opened the session, a genuine SET_MTA -> PROGRAM_CLEAR ->
SET_MTA -> PROGRAM + PROGRAM_NEXT (a real multi-frame block) -> PROGRAM with zero elements cycle
before the existing PROGRAM_RESET/disconnect ending. This is what no per-task test in either
sub-project proves: pgm_clear_test.py and pgm_program_test.py each verify PROGRAM_CLEAR or
PROGRAM/PROGRAM_NEXT in isolation, against a handle built fresh for that one exchange; none shows
an ERASE and a PROGRAM sharing the SAME ACTIVE session a busy, interrupted PROGRAM_START already
opened, at MTAs the session itself set moments earlier.

PROGRAM_CLEAR is deliberately ALSO run against a slow, deferring integrator (busy_calls=2, its own
EV_CMD_PENDING asserted) -- not merely completed synchronously the way PROGRAM/PROGRAM_NEXT are
below -- because DD67 calls erase "the slowest operation in the protocol", and because a module
that special-cased PROGRAM_START's own PID inside Xcp_PgmPollPendingCommand/
Xcp_PgmCompletePendingCommand's shared switches (source/Xcp_Pgm.c), rather than genuinely sharing
them across every pending command, would still pass every assertion PROGRAM_START's own busy
sequence makes and only fail here. PROGRAM/PROGRAM_NEXT complete synchronously: their own deferral
is already exhaustively pinned in isolation
(pgm_program_test.py's test_program_defers_through_the_pending_slot_and_keeps_passing_the_same_bytes
and test_program_next_defers_through_the_pending_slot_and_keeps_passing_the_whole_block), and this
test's own job is composition, not re-deriving a property a per-task test already owns -- the same
restraint SP4a's own Task 6 report exercised for PROGRAM_PREPARE's and PROGRAM_RESET's own branch
coverage.

Five further mutations, one per SP4b task (1 through 5; SP4b's own Task 6 is this task, and has
nothing of its own to mutate), are recorded on the test function's own docstring below, alongside
the five SP4a-era ones. task-6-report.md
(.superpowers/sdd/2026-09-07-xcp-pgm-sp4b/task-6-report.md) carries the full list and each one's
measured result.

**Criteria this extension newly discharges (design doc Section 9):** 3 (a multi-frame block reaches
the integrator as one contiguous write of the right length at the right address), 5 (PROGRAM_START
reports programming.max_block_size as MAX_BS_PGM, checked against a configuration where that value
and the live max_bs deliberately differ), and 6 (GET_PGM_PROCESSOR_INFO reports absolute mode only
and MAX_SECTOR 0). Criterion 2's PROGRAM_CLEAR and PROGRAM conjuncts are exercised for real here
too, though PROGRAM_MAX -- also part of criterion 2, and not named in the brief's own sequence -- is
not: it is exhaustively covered in isolation (pgm_program_test.py) instead. Criterion 4 (a failed
write leaves the MTA where the master left it) is deliberately NOT re-derived here either: every
write in this sequence succeeds, on purpose, since this test's own point is a real master's
SUCCESSFUL sequence composing end to end, and DD66's failure path already has its own dedicated,
mutation-verified test (pgm_program_test.py's own
test_a_failed_program_write_leaves_the_mta_unmoved). Criteria 1 and 7 are generation-level claims no
wire-level test, this one included, can discharge or refute; see task-6-report.md for how each was
actually checked.
"""

from .pgm_deferred_test import program_start, program_reset, transmitted, busy_then
from .pgm_session_test import send, program_prepare, probe_still_connected
from .pgm_program_test import pgm_program_handle, program, program_next
from .pgm_clear_test import program_clear
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .parameter import u32_to_array


PGM_RESOURCE = 0x10  # XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, source/Xcp_Internal.h: 0x01u << 4.


def unlock_pgm(handle, seed=(0x42,)):
    """One full, confirmed GET_SEED/UNLOCK round for the PGM resource. Mechanically correct on any
    handle -- the response reflects the resource the request named regardless of whether that
    resource is actually configured as protected (seed_key_test.py's own
    test_unlock_unlocks_the_requested_resource_if_the_key_is_valid runs with every
    resource_protection_* flag at its False default and still gets back (0xFF, resource)) -- which
    is what lets the sequence below carry a real exchange on a build where, by the module
    docstring's finding, no build may configure the PGM resource as protected at all."""
    seed = list(seed)
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, seed)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, PGM_RESOURCE)))
    handle.lib.Xcp_MainFunction()
    frame = transmitted(handle)
    # Byte 1 is the REMAINING length as of this response, seed_key_test.py's own
    # test_get_seed_returns_the_expected_responses pins it: a fresh, one-byte seed reports 1 here,
    # not 0 -- 0 would mean nothing was left BEFORE this frame, which is never true of the first.
    assert frame[0:3] == (0xFF, len(seed), seed[0]), 'GET_SEED must return the PGM seed'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, len(seed)) + tuple(seed)))
    handle.lib.Xcp_MainFunction()
    frame = transmitted(handle)
    assert frame[0:2] == (0xFF, PGM_RESOURCE), 'UNLOCK must succeed and report PGM unlocked'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def test_a_real_masters_full_programming_sequence_composes_end_to_end():
    """CONNECT -> GET_PGM_PROCESSOR_INFO -> GET_SEED/UNLOCK -> SET_MTA -> PROGRAM_PREPARE ->
    PROGRAM_START (deferred, against a deliberately slow integrator, interrupted mid-operation) ->
    the resulting ACTIVE session -> SET_MTA -> PROGRAM_CLEAR (also deferred, against its own slow
    integrator) -> SET_MTA -> PROGRAM + PROGRAM_NEXT x2 (a genuine multi-frame block) -> PROGRAM
    with zero elements -> PROGRAM_RESET -> disconnected. Every step is answered and confirmed
    before the next request, so a module that silently dropped or malformed any one exchange would
    desynchronise every assertion after it, not merely the one closest to the defect. See the
    module docstring for why the PGM resource is not configured as protected here, and for what
    SP4b's own extension (everything from the second SET_MTA onward) adds to what SP4a's Task 6
    already proved.

    Ten mutations in total were run against this test (task-6-report.md carries the full list and
    each one's measured result). Five are SP4a-era, unchanged since Task 6 of that sub-project and
    still caught by the SAME assertions, now earlier in a longer test rather than at its end:
    disabling the EV_CMD_PENDING push (SP4a Task 2/DD54), inverting the ERR_CMD_BUSY gate's
    pending_command.active test (SP4a Task 3/DD55), dropping PROGRAM_RESET's
    Xcp_DisconnectSession call (SP4a Task 4/DD57), and two forms of DD51's ERR_PGM_ACTIVE gate
    (SP4a Task 5): removing the pgm_state disjunct entirely, and reinstating
    XCP_INTERNAL_ERR_PGM_ACTIVE on SET_MTA's own matrix row -- the fix SP4a's own Task 5 report
    calls 'the most consequential defect of the sub-project'.

    Five more are this sub-project's own, one per SP4b task, each caught by an assertion this
    extension adds: reverting PROGRAM_START's byte 4 from XCP_PGM_MAX_BLOCK_SIZE back to the live
    Xcp_Ptr->general->maxBS (Task 1/DD62); Xcp_PgmPollPendingCommand's PROGRAM_CLEAR case reading
    pending_command.args.program_prepare_code_size instead of .program_clear_range on the
    completing poll (Task 2, the same union-member mistake pgm_clear_test.py's own equivalent test
    mutates); deleting Xcp_DTOCmdPgmProgram's zero-element special case, DD64 (Task 3); starting
    Xcp_DTOCmdPgmProgramNext's copy at index 0 instead of Xcp_Internal.pgm_block.length, so each
    frame overwrites the block instead of appending to it, DD63 (Task 4); and OR-ing
    XCP_PGM_PROPERTIES_FUNCTIONAL_MODE into PGM_PROPERTIES alongside ABSOLUTE_MODE, DD68 (Task 5).
    All ten made this test fail; none is left in the tree."""
    handle = pgm_program_handle(max_bs=5, programming_max_block_size=12)

    # GET_PGM_PROCESSOR_INFO, right after CONNECT: DD68's advertisement, checked here as part of
    # the composed sequence a real master would actually query it in, not only in isolation
    # (pgm_processor_info_test.py). Answered identically from XCP_PGM_IDLE and XCP_PGM_ACTIVE
    # (pgm_processor_info_test.py's own
    # test_get_pgm_processor_info_is_answered_identically_from_xcp_pgm_idle_and_xcp_pgm_active
    # already pins that independently), so nothing about asking before PROGRAM_START, as a real
    # master would, is special-cased here.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xCE,)))
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0:3] == (0xFF, 0x01, 0x00), \
        'GET_PGM_PROCESSOR_INFO must advertise absolute-mode-only programming and MAX_SECTOR 0'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # GET_SEED/UNLOCK for the PGM resource, exactly where the brief places it: a real master
    # requests and answers a seed before touching PGM commands regardless of whether THIS slave's
    # configuration happens to enforce it (see the module docstring for why this build does not).
    unlock_pgm(handle)

    # SET_MTA, establishing the download address PROGRAM_PREPARE reads next.
    assert send(handle, (0xF6, 0x00, 0x00, 0x00) + tuple(u32_to_array(0xCAFEF00D, 'LITTLE_ENDIAN')))[0] == 0xFF, \
        'SET_MTA establishes the download address'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program_prepare(handle, code_size=0x2000)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_PREPARE is accepted'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # PROGRAM_START, against a deliberately slow integrator (busy_calls=3: two full busy polls
    # after the handler's own first call, so the deferral, EV_CMD_PENDING and an interruption are
    # all genuinely exercised rather than the operation completing on the first, synchronous call
    # the way pgm_deferred_test.py's own test_an_instantaneous_integrator_is_answered_without_
    # deferring shows an immediate integrator would).
    state = busy_then(handle, 0x00, busy_calls=3)
    handle.can_if_transmit.reset_mock()
    program_start(handle)  # call 1, inside the handler itself (DD53): busy, so it defers.

    handle.lib.Xcp_MainFunction()  # call 2: still busy.
    assert transmitted(handle)[0:2] == (0xFD, 0x05), \
        'EV_CMD_PENDING (DD54) must keep the master informed while PROGRAM_START is still pending'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # A command arriving mid-operation is answered ERR_CMD_BUSY (DD55, Task 3) instead of being
    # dispatched. GET_STATUS is the interloper: unconditionally available, no side effects of its
    # own, and (per pgm_session_test.py's own choice of the same probe) not itself carrying
    # XCP_INTERNAL_ERR_CMD_BUSY in its matrix entry, so a stale busy check reading the wrong flag
    # could not wave it through by accident.
    assert send(handle, (0xFD,))[0:2] == (0xFE, 0x10), \
        'a command arriving mid-operation must be answered ERR_CMD_BUSY'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # call 3: still busy -- the operation survives the interruption.
    assert transmitted(handle)[0:2] == (0xFD, 0x05), \
        'EV_CMD_PENDING must resume once the interloper is drained: the operation is still alive'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # call 4: the slow integrator finally reports E_OK.
    frame = transmitted(handle)
    assert frame[0] == 0xFF, \
        'the pending PROGRAM_START response must still arrive once the integrator finishes'
    assert frame[4] == 12, \
        "MAX_BS_PGM (DD62) must be this handle's configured programming.max_block_size (12), not " \
        'its deliberately different max_bs (5) -- pgm_deferred_test.py pins this fact in ' \
        'isolation; this is the same fact, checked in the very session the PROGRAM_CLEAR/PROGRAM ' \
        'block below actually uses'
    assert state['calls'] == 4, \
        'the integrator must actually have been polled through both the wait and the interruption'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # The session is now ACTIVE (Xcp_PgmCompleteProgramStart, source/Xcp_Pgm.c). DD51's fourth
    # disjunct (Xcp_Internal.pgm_state == XCP_PGM_ACTIVE, beside the three pre-existing
    # session_status bits) makes a gated command answer ERR_PGM_ACTIVE. GET_SEED is the probe,
    # exactly as in pgm_session_test.py's own
    # test_an_active_programming_session_makes_the_pgm_active_gate_fire: its own Xcp_CTOErrorMatrix
    # entry carries XCP_INTERNAL_ERR_PGM_ACTIVE, regardless of resource protection.
    assert send(handle, (0xF8, 0x00, 0x01))[0:2] == (0xFE, 0x12), \
        'an active programming session must gate GET_SEED with ERR_PGM_ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # But SET_MTA -- one of the seven commands 1.1/1.6.5.1.1 requires to stay available throughout
    # a programming sequence -- is NOT refused. Task 5's own report names the alternative outcome
    # "the most consequential defect of the sub-project": SET_MTA, UPLOAD and BUILD_CHECKSUM
    # originally still carried XCP_INTERNAL_ERR_PGM_ACTIVE, which would have made a programming
    # sequence unable to reposition the MTA -- impossible to conduct at all -- and the gate had no
    # trigger before this sub-project, so nothing had ever caught it on the wire.
    frame = send(handle, (0xF6, 0x00, 0x00, 0x00) + tuple(u32_to_array(0x87654321, 'LITTLE_ENDIAN')))
    assert frame[0:2] != (0xFE, 0x12), 'SET_MTA must stay available during a programming sequence'
    assert frame[0] == 0xFF, 'and must be genuinely answered, not merely refused for some OTHER reason'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # ---------------------------------------------------------------------------------------------
    # SP4b's own extension: a genuine erase, then a genuine multi-frame program, in the SAME ACTIVE
    # session PROGRAM_START opened above -- see the module docstring for why this is what no
    # per-task test in either sub-project proves.
    # ---------------------------------------------------------------------------------------------

    # SET_MTA -> PROGRAM_CLEAR: erase, against its own deliberately slow integrator (DD67 calls
    # erase "the slowest operation in the protocol"), so EV_CMD_PENDING is genuinely exercised a
    # SECOND time, through Xcp_PgmPollPendingCommand/Xcp_PgmCompletePendingCommand's shared
    # switches (source/Xcp_Pgm.c) rather than PROGRAM_START's own busy sequence replayed. busy_then
    # (pgm_deferred_test.py) cannot be reused here: its own side_effect takes pStatusCode alone,
    # where Xcp_ProgramClear's contract also takes address and clearRange on every call.
    ERASE_ADDRESS = 0x00080000
    # Deliberately > 0xFFFF: pending_command.args is a union of program_prepare_code_size (uint16)
    # and program_clear_range (uint32) at the same offset (source/Xcp_Internal.h). A clear range
    # that fits in 16 bits would let a completing poll that read the WRONG union member (Task 2's
    # own mutation, see this test's own docstring) reproduce the same low 16 bits by coincidence
    # and pass anyway -- exactly the trap this value avoids.
    ERASE_RANGE = 0x00123000

    handle.can_if_transmit.reset_mock()
    assert send(handle, (0xF6, 0x00, 0x00, 0x00) +
                tuple(u32_to_array(ERASE_ADDRESS, 'LITTLE_ENDIAN')))[0] == 0xFF, \
        'SET_MTA establishes the erase target'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    erase_state = dict(calls=0)

    def erase_busy_then_complete(_address, _clear_range, p_status_code):
        # call 1: the fast path inside the handler itself (program_clear below); call 2: the first
        # Xcp_MainFunction poll -- both busy; call 3, the second poll, completes. Mirrors
        # pgm_clear_test.py's own
        # test_program_clear_defers_through_the_pending_slot_and_keeps_passing_the_clear_range.
        erase_state['calls'] += 1
        if erase_state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_clear.side_effect = erase_busy_then_complete
    handle.can_if_transmit.reset_mock()

    program_clear(handle, mode=0x00, clear_range=ERASE_RANGE)  # call 1, in the handler: busy, defers

    handle.lib.Xcp_MainFunction()  # call 2: still busy
    assert transmitted(handle)[0:2] == (0xFD, 0x05), \
        'EV_CMD_PENDING must fire for PROGRAM_CLEAR too, not only for PROGRAM_START above'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # call 3: the slow integrator finally reports E_OK

    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_CLEAR must answer once the erase completes'
    address, clear_range, _p_status_code = handle.xcp_program_clear.call_args_list[-1][0]
    assert int(handle.ffi.cast('uintptr_t', address)) == ERASE_ADDRESS, \
        'the integrator must have been handed the address this session just set'
    assert clear_range == ERASE_RANGE, "the integrator must have been handed the request's own clear range"
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # SET_MTA -> PROGRAM + PROGRAM_NEXT x2: a genuine multi-frame block (14 bytes over 3 frames at
    # this suite's default MAX_CTO=8, 6 data bytes per frame), immediately after the erase, at a
    # DIFFERENT address from ERASE_ADDRESS -- a module that quietly kept programming at the erase
    # target instead of re-reading the freshly-set MTA cannot pass this by coincidence. Both writes
    # complete synchronously (the default mock behaviour): PROGRAM's and PROGRAM_NEXT's own
    # deferral is already exhaustively pinned in isolation (pgm_program_test.py), and composing is
    # this test's own job, not re-deriving it a third time.
    PROGRAM_ADDRESS = 0x00080100
    payload = tuple(range(0x01, 0x0F))  # 14 recognisable, distinct bytes: 0x01..0x0E

    handle.can_if_transmit.reset_mock()
    assert send(handle, (0xF6, 0x00, 0x00, 0x00) +
                tuple(u32_to_array(PROGRAM_ADDRESS, 'LITTLE_ENDIAN')))[0] == 0xFF, \
        'SET_MTA establishes the program target, distinct from the erase target above'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program(handle, 0x0E, data=payload[0:6])           # frame 1 (PROGRAM): 6 of 14, 8 remaining
    program_next(handle, 0x08, data=payload[6:12])      # frame 2 (PROGRAM_NEXT): 6 of 8, 2 remaining
    program_next(handle, 0x02, data=payload[12:14])     # frame 3 (PROGRAM_NEXT): the last 2, completes

    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the completing PROGRAM_NEXT frame answers'
    assert handle.xcp_program_write.call_count == 1, \
        'once per BLOCK across all three frames, not once per frame'
    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == PROGRAM_ADDRESS, \
        'the block must land at the MTA this session just set, not the earlier erase target'
    assert length == 0x0E, 'the true total length of the whole block'
    assert bytes(p_data[0:length]) == bytes(payload), \
        'the exact concatenation of all three frames, in order -- not merely the right length'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # PROGRAM with zero elements: DD64 ends the segment with a positive response and never reaches
    # the integrator again -- distinct from programming zero bytes, and distinct from ending the
    # whole programming SEQUENCE, which 1.6.5.1.3 leaves to PROGRAM_RESET below.
    handle.can_if_transmit.reset_mock()
    assert send(handle, (0xD0, 0x00))[0] == 0xFF, \
        'a zero-element PROGRAM must end the segment with a positive response'
    assert handle.xcp_program_write.call_count == 1, \
        'still exactly one call -- the zero-element PROGRAM must not have reached the integrator again'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # PROGRAM_RESET: answers, then disconnects (DD57).
    handle.can_if_transmit.reset_mock()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_RESET must answer'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # DD57: the disconnect happens in the completion, sharing Xcp_CTOCmdStdDisconnect's own unwind
    # (Xcp_DisconnectSession, source/Xcp_Std.c), so by the time that response has been confirmed
    # the module must already refuse to dispatch anything but CONNECT. probe_still_connected (from
    # pgm_session_test.py, used there for exactly this) sends a bare GET_SEED and reports whether
    # source/Xcp.c's disconnected-state gate let it reach Xcp_GetSeed at all. Reset first: the
    # unlock_pgm round at the top of this test already called xcp_get_seed once, and this probe's
    # own contract (like pgm_session_test.py's own uses of it) is a call count starting at zero.
    handle.xcp_get_seed.reset_mock()
    assert probe_still_connected(handle) == 0, \
        'the slave must be disconnected once PROGRAM_RESET\'s own response has been confirmed'

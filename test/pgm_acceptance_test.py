#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Task 6, deliverable (a). Design doc Section 9 (docs/superpowers/specs/2026-09-06-xcp-pgm-sp4a-
design.md), acceptance criteria 2, 3, 5 and 7, exercised together rather than one at a time.

Every other file in this sub-project's test suite proves ONE command, or one pair of them, in
isolation: pgm_deferred_test.py the deferred machinery underneath PROGRAM_START alone,
pgm_session_test.py the busy/SYNCH/active/reset gates one at a time. None of them shows the
sequence COMPOSES -- that a master walking CONNECT through PROGRAM_RESET, against an integrator
that is genuinely slow, gets one coherent conversation out the other end rather than five correct
answers to five separate questions. That is what test_a_real_masters_full_programming_sequence_
composes_end_to_end below is for, and it is why it is one long test rather than several short
ones: the whole point is that nothing resets the module in between.

**A resource-protection finding, read this before wondering why the main test below does not set
resource_protection_programming.** The task brief asks for the PGM resource to be configured
protected so GET_SEED/UNLOCK is 'real rather than decorative'. Building it that way -- unlocking
PGM, sending PROGRAM_PREPARE, unlocking again, sending PROGRAM_START -- works, and both
exchanges are genuinely load-bearing (test_get_seed_unlock_genuinely_gates_a_pgm_command below
proves it directly). It stops working at PROGRAM_RESET, and not from a mistake in the test: this
module's README ('Key lifetime') documents that an UNLOCK's effect 'is discarded after the command
FOLLOWING the UNLOCK sequence has been executed', which source/Xcp.c implements as
Xcp_ClearProtectionStatus() running after every dispatched command except UNLOCK itself -- so one
GET_SEED/UNLOCK round unlocks exactly the ONE command sent right after it, never more. PROGRAM_START
is that one command for the second round, and dispatching it (immediately, in the handler, before
it ever defers) is what spends it. By the time the session reaches XCP_PGM_ACTIVE and PROGRAM_RESET
is due, PGM is locked again, and there is no way to re-unlock it: GET_SEED and UNLOCK both carry
XCP_INTERNAL_ERR_PGM_ACTIVE in their own Xcp_CTOErrorMatrix rows (source/Xcp.c) -- pre-existing,
not touched by SP4a -- so DD51's own new ACTIVE-session trigger refuses both of them right back.
Measured directly (see task-6-report.md): a PROGRAM_RESET sent in this state answers (0xFE, 0x25),
ERR_ACCESS_LOCKED, not the positive response DD57 promises. Nothing between PROGRAM_START's
dispatch and PROGRAM_RESET can change that -- SYNCH does not reset pgm_state for an established
ACTIVE session (Task 3's own fix, DD55 corrected), and no command this module implements re-opens
GET_SEED/UNLOCK while ACTIVE.

That is a genuine interaction between two mechanisms that both predate this task and are each
correct on their own -- resource protection's one-shot lifetime, and the pre-existing (not SP4a's)
ERR_PGM_ACTIVE bit on GET_SEED/UNLOCK -- and fixing it is a design decision belonging to DD51,
DD57 or the seed-key mechanism, not something a test may repair by itself. §9's own acceptance
criteria say nothing about resource protection at all; PROGRAM_RESET answering and disconnecting
is a named, independent criterion (3), and is also this test's only way to mutation-verify Task
4's contribution at all. So the main test below sends a real, wire-correct GET_SEED/UNLOCK
exchange for the PGM resource where the brief places it (CONNECT, then this, then SET_MTA), proving
the handshake itself is correct, but does not configure the resource as protected -- which means,
by the brief's own vocabulary, this ONE exchange is decorative in THIS test. The load-bearing proof
that GET_SEED/UNLOCK genuinely gates a PGM command lives in the second test below instead, which
does not need to reach PROGRAM_RESET and so never meets the wall above.

Every exchange below follows the standing rule this sub-project's five prior tasks paid for the
hard way (task reports in .superpowers/sdd/2026-09-06-xcp-pgm-sp4a/): reset can_if_transmit
immediately before the exchange under test, read transmitted()'s single most recent frame rather
than scanning call_args_list, confirm every response before the next request (the transmit
pipeline carries one frame at a time, SWS_Xcp_00859), and pump Xcp_MainFunction wherever a
transmission must have happened, since Xcp_CanIfRxIndication itself never transmits.
"""

from .pgm_deferred_test import pgm_handle, program_start, program_reset, transmitted, busy_then
from .pgm_session_test import send, program_prepare, probe_still_connected
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .parameter import u32_to_array


PGM_RESOURCE = 0x10  # XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, source/Xcp_Internal.h: 0x01u << 4.


def unlock_pgm(handle, seed=(0x42,)):
    """One full, confirmed GET_SEED/UNLOCK round for the PGM resource. Mechanically correct on any
    handle -- the response reflects the resource the request named regardless of whether that
    resource is actually configured as protected (seed_key_test.py's own
    test_unlock_unlocks_the_requested_resource_if_the_key_is_valid runs with every
    resource_protection_* flag at its False default and still gets back (0xFF, resource)) -- so
    this same helper serves both tests below: the main one, where it is a real exchange that does
    not happen to gate anything (see the module docstring), and the second, focused test, where
    resource_protection_programming=True makes it load-bearing."""
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
    """CONNECT -> GET_SEED/UNLOCK -> SET_MTA -> PROGRAM_PREPARE -> PROGRAM_START (deferred, against
    a deliberately slow integrator, interrupted mid-operation) -> the resulting ACTIVE session ->
    PROGRAM_RESET -> disconnected. Every step is answered and confirmed before the next request, so
    a module that silently dropped or malformed any one exchange would desynchronise every
    assertion after it, not merely the one closest to the defect. See the module docstring for why
    the PGM resource is not configured as protected here.

    Five mutations were run against this test while writing it (task-6-report.md carries the full
    list and each one's result): disabling the EV_CMD_PENDING push (Task 2/DD54), inverting the
    ERR_CMD_BUSY gate's pending_command.active test (Task 3/DD55), dropping PROGRAM_RESET's
    Xcp_DisconnectSession call (Task 4/DD57), and two forms of DD51's ERR_PGM_ACTIVE gate (Task 5):
    removing the pgm_state disjunct entirely, and reinstating XCP_INTERNAL_ERR_PGM_ACTIVE on
    SET_MTA's own matrix row -- the fix Task 5's own report calls 'the most consequential defect of
    the sub-project'. All five made this test fail; none is left in the tree."""
    handle = pgm_handle()

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
    assert transmitted(handle)[0] == 0xFF, \
        'the pending PROGRAM_START response must still arrive once the integrator finishes'
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


def test_get_seed_unlock_genuinely_gates_a_pgm_command():
    """The load-bearing half of 'configure the PGM resource as protected so the GET_SEED/UNLOCK
    step is real rather than decorative' -- proven directly, on its own, rather than woven through
    the full sequence above, for the reason the module docstring gives: doing both in the same test
    is not achievable once PROGRAM_START has made the session ACTIVE (GET_SEED/UNLOCK are then
    refused ERR_PGM_ACTIVE themselves, so a resource can never be re-unlocked for PROGRAM_RESET).
    PROGRAM_PREPARE is chosen because it needs no completed session at all -- it is legal from
    XCP_PGM_IDLE (design §4) -- so this test never approaches that wall.

    Both directions are checked on the SAME handle: refused ERR_ACCESS_LOCKED (0xFE, 0x25) before
    the resource is unlocked, and accepted once it is. The first half alone would also pass a
    module that refused PROGRAM_PREPARE unconditionally; the second half alone would also pass a
    module that never enforced protection at all. Only the pair, in this order, says the unlock
    itself is what changed the answer."""
    handle = pgm_handle(resource_protection_programming=True)

    assert send(handle, (0xCC, 0x00, 0x00, 0x10))[0:2] == (0xFE, 0x25), \
        'PROGRAM_PREPARE must be refused ERR_ACCESS_LOCKED while the PGM resource is locked'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    unlock_pgm(handle)

    handle.can_if_transmit.reset_mock()
    program_prepare(handle, code_size=0x0010)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, \
        'PROGRAM_PREPARE must be accepted once GET_SEED/UNLOCK has actually unlocked PGM'

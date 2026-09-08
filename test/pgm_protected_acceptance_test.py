#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD83 -- the configuration this proves buildable could not be generated at all before this task.

script/source_cfg.c.jinja2 raised on `resource_protection.programming: true` with
`programming.enabled: true`, because an unlock was spent by the single command that followed it:
PROGRAM_START consumed the grant, the session became XCP_PGM_ACTIVE, PROGRAM_RESET -- the only
command that ends it -- was locked again, and GET_SEED and UNLOCK were themselves refused
ERR_PGM_ACTIVE. The slave could never leave the programming session.

Every link in that chain depended on the grant being spent, so DD79 dissolves it. This test walks
the whole sequence rather than arguing it: an argument that a dead end no longer exists is worth
much less than a run that goes through where the dead end was."""

from .pgm_deferred_test import program_start, program_reset, transmitted, busy_then
from .pgm_program_test import pgm_program_handle, program
from .pgm_clear_test import program_clear
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .seed_key_defects_test import exchange


PGM_RESOURCE = 0x10  # XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM, source/Xcp_Internal.h: 0x01u << 4.


def test_a_protected_pgm_resource_conducts_a_full_programming_sequence_end_to_end():
    """CONNECT -> PROGRAM_START refused (protection is live) -> GET_SEED/UNLOCK for the PGM
    resource -> PROGRAM_START (deferred, genuinely polled) -> PROGRAM_CLEAR -> PROGRAM ->
    PROGRAM_RESET, every step confirmed before the next request (SWS_Xcp_00859: the transmit
    pipeline carries one frame at a time).

    The refusal this replaces argued the sequence below is impossible: PROGRAM_START spends the
    single-command grant GET_SEED/UNLOCK produced, the session becomes XCP_PGM_ACTIVE,
    PROGRAM_RESET -- the only command that ends it, and itself PGM-group-protected
    (Xcp_PIDToCmdGroupTable, source/Xcp.c) -- is locked again, and GET_SEED/UNLOCK cannot be
    replayed to re-open it because DD51's ERR_PGM_ACTIVE gate refuses both while ACTIVE. This test
    performs exactly ONE GET_SEED/UNLOCK round, before PROGRAM_START, and never touches GET_SEED or
    UNLOCK again -- so if the grant does not survive PROGRAM_START, PROGRAM_CLEAR, PROGRAM and
    PROGRAM_RESET all the way to the end, one of those four answers ERR_ACCESS_LOCKED (0xFE, 0x25)
    instead of the positive response asserted here. DD79 (Task 1) is what makes the grant last the
    whole session instead of the one command following the unlock; DD81 (Task 2) is what makes the
    one GET_SEED/UNLOCK round itself genuine (UNLOCK answers ERR_SEQUENCE without a held seed).

    PROGRAM_START alone is pumped through a genuine busy cycle (Xcp_ProgramStart returns E_NOT_OK
    once before reporting E_OK, and DD54's own poison-value convention -- 0xEE, only ever read on a
    premature answer -- makes a module that read the status code early answer ERR_GENERIC-with-0xEE
    on the wire): the point being proven here is resource protection surviving PROGRAM_START's own
    deferral, not deferral itself, which pgm_deferred_test.py and pgm_acceptance_test.py already
    prove exhaustively. PROGRAM_CLEAR, PROGRAM and PROGRAM_RESET are each left at the suite's
    default synchronous integrator (conftest.py: E_OK, status code 0) -- the same default
    pgm_clear_test.py's and pgm_program_test.py's own basic success tests, and this module's own
    PROGRAM_RESET step, rely on -- since re-deriving their own deferred-polling correctness a
    second time is not this test's job."""
    handle = pgm_program_handle(resource_protection_programming=True)

    # Proven live, not merely advertised: PROGRAM_START is refused before any resource is unlocked.
    assert exchange(handle, (0xD2,))[0:2] == (0xFE, 0x25), \
        'PROGRAM_START must be refused ERR_ACCESS_LOCKED before the PGM resource is unlocked'

    # One GET_SEED/UNLOCK round for the PGM resource -- the only one this test ever sends. Task 2's
    # held-seed admission gate makes this a genuine sequence: UNLOCK reads the seed GET_SEED just
    # produced, not merely last_pid's own set-membership.
    seed = [0x42]
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, seed)

    frame = exchange(handle, (0xF8, 0x00, PGM_RESOURCE), length=3)
    assert frame[0:3] == (0xFF, len(seed), seed[0]), 'GET_SEED must return the PGM seed'

    frame = exchange(handle, (0xF7, len(seed)) + tuple(seed), length=2)
    assert frame[0:2] == (0xFF, PGM_RESOURCE), 'UNLOCK must succeed and report PGM unlocked'

    # PROGRAM_START: polled, not immediate. Xcp_ProgramStart returns E_NOT_OK once (the status code
    # must not be read on that call -- DD54's poison value would surface as ERR_GENERIC-with-0xEE if
    # it were), so the answer does not arrive on the first Xcp_MainFunction; pump and confirm rather
    # than assume it does.
    busy_then(handle, 0x00, busy_calls=2)
    handle.can_if_transmit.reset_mock()
    program_start(handle)  # call 1, inside the handler itself (DD53): still busy, so it defers.

    handle.lib.Xcp_MainFunction()  # call 2: still busy.
    assert transmitted(handle)[0:2] == (0xFD, 0x05), \
        'EV_CMD_PENDING must keep the master informed while PROGRAM_START is still pending'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # call 3: the integrator finally reports E_OK.
    assert transmitted(handle)[0] == 0xFF, \
        'PROGRAM_START must succeed once the PGM resource is unlocked'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # The session is now XCP_PGM_ACTIVE. Before DD79, the grant that admitted PROGRAM_START would
    # already be gone (spent by PROGRAM_START itself) and every command below, PGM-group-protected
    # like PROGRAM_START, would answer ERR_ACCESS_LOCKED instead of what is asserted here.

    # PROGRAM_CLEAR: default synchronous integrator (conftest.py), same single-poll pattern
    # pgm_clear_test.py's own basic success tests use.
    handle.can_if_transmit.reset_mock()
    program_clear(handle, mode=0x00, clear_range=0x00001000)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_CLEAR must succeed with the grant still held'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # PROGRAM: two recognisable bytes, well under any block-mode threshold at this suite's default
    # MAX_CTO -- a single frame, synchronously written.
    handle.can_if_transmit.reset_mock()
    program(handle, 0x02, data=(0xAA, 0xBB))
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM must succeed with the grant still held'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # PROGRAM_RESET: the only command that ends the session, and itself PGM-group-protected -- the
    # exact command the refused configuration could never legitimately reach.
    handle.can_if_transmit.reset_mock()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_RESET must succeed and end the session'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

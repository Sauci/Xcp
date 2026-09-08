#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD79 (docs/superpowers/specs/2026-09-08-xcp-seed-key-hardening-design.md) -- a pre-existing
defect in shipped code: a successful UNLOCK grants a resource for exactly ONE following command.

source/Xcp.c cleared the whole granted set after every dispatched command except UNLOCK itself, so
an unrelated GET_STATUS spent the grant just as a CAL command did. XCP part 2 - Protocol Layer
Specification 1.0/1.6.1.2.5 says the opposite: "a repetition of an UNLOCK sequence with a correct
key will have a positive response and no other effect", which presumes the grant is still standing.

DOWNLOAD (0xF0) is the protected observable throughout this file: Xcp_PIDToCmdGroupTable
(source/Xcp.c) maps it to MASK_CAL_PAG, while SET_MTA (0xF6) and GET_STATUS (0xFD) map to
MASK_NONE, so the setup and the interloper both stay reachable while CAL_PAG is locked."""

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .seed_key_defects_test import exchange

GET_STATUS = (0xFD,)
DOWNLOAD = (0xF0, 0x03, 0x11, 0x22, 0x33)
SEED = [0x11, 0x22]
KEY = [0x33, 0x44]


def cal_protected_handle(**kwargs):
    """A slave whose CALibration/Paging group is protected, connected and with a valid MTA.

    The MTA is set BEFORE any unlock deliberately: SET_MTA is MASK_NONE, so it must succeed while
    CAL_PAG is still locked, and doing it here keeps every DOWNLOAD below a test of the protection
    gate rather than of address setup."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   resource_protection_calibration_paging=True,
                                   **kwargs))
    connect(handle)
    set_mta(handle, 0x1000)
    return handle


def unlock_cal_pag(handle):
    """A complete GET_SEED/UNLOCK sequence for CAL_PAG, asserting each half so a failure here is
    never mistaken for the behaviour under test."""
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF, 'GET_SEED(mode=0, CAL_PAG)'
    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0] == 0xFF, 'UNLOCK'


def test_a_protected_command_is_refused_before_any_unlock():
    """The precondition every other test in this file rests on. Without it, a DOWNLOAD that
    succeeds proves nothing -- it would succeed identically if the resource were never protected,
    which is exactly the configuration the rest of the suite runs in."""
    handle = cal_protected_handle()

    assert exchange(handle, DOWNLOAD)[0:2] == (0xFE, 0x25), 'ERR_ACCESS_LOCKED'


def test_an_unlock_survives_an_unrelated_command():
    """DD79, the defect itself. GET_STATUS is MASK_NONE and has no side effects, so the only thing
    it can do to the DOWNLOAD that follows is spend its grant -- which is what it used to do."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)

    assert exchange(handle, DOWNLOAD)[0] == 0xFF, 'the first protected command after UNLOCK'
    assert exchange(handle, GET_STATUS)[0] == 0xFF
    assert exchange(handle, DOWNLOAD)[0] == 0xFF, \
        'the grant was spent by an unrelated GET_STATUS'


def test_an_unlock_survives_repeated_use_of_the_protected_resource():
    """The grant must not be consumed by the protected command either -- a variant the
    single-command lifetime also broke, and one a master doing a real calibration session hits
    immediately."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)

    for attempt in range(5):
        assert exchange(handle, DOWNLOAD)[0] == 0xFF, \
            'DOWNLOAD number {} was refused'.format(attempt + 1)


def test_an_unlock_does_not_survive_a_reconnect():
    """The other half of DD79: the grant lasts the SESSION, not forever. This is the same session
    boundary DD77 established, and the reset joins that block."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)
    assert exchange(handle, DOWNLOAD)[0] == 0xFF

    connect(handle)
    set_mta(handle, 0x1000)

    assert exchange(handle, DOWNLOAD)[0:2] == (0xFE, 0x25), \
        'the grant outlived the session that earned it'


def test_unlock_with_no_preceding_get_seed_is_refused():
    """DD81, and the defect section 3b of the previous branch recorded and deliberately left
    unfixed. XCP part 2 1.0/1.6.1.2.5: "The master only can send an UNLOCK sequence if previously
    there was a GET_SEED sequence... If the master does not respect this sequence, the slave
    returns an ERR_SEQUENCE."

    ERR_SEQUENCE needs no deviation: it is in UNLOCK's own 1.7.3.2.1 row, and that row's prescribed
    pre-action for it is literally GET_SEED, so the refusal tells the master exactly what to do."""
    handle = cal_protected_handle()
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'
    assert exchange(handle, DOWNLOAD)[0:2] == (0xFE, 0x25), \
        'the resource was granted by an UNLOCK against a seed that was never issued'


def test_a_second_unlock_without_a_fresh_seed_is_refused():
    """The seed is spent by the UNLOCK that consumes it -- Xcp_DTOCmdStdUnlock already zeroes
    seed.total_length on a complete key, under a comment saying it "enforces a new seed to be
    requested prior to unlock a next resource". Nothing ever checked it. This is that check."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)

    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'


def test_a_legitimate_multi_frame_key_is_still_admitted():
    """The guard must not break a key too long for one frame. At MAX_CTO=8 a frame carries at most
    MAX_CTO-2 = 6 key bytes, so a 10-byte key needs two UNLOCK frames; seed.total_length stays
    non-zero across the whole sequence and is zeroed only on completion, so every frame is
    admitted. Without this test the guard could be written to admit only the FIRST frame and both
    tests above would still pass."""
    handle = cal_protected_handle()
    long_key = [0xA0 + i for i in range(10)]

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, long_key)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF
    assert exchange(handle, (0xF7, 10) + tuple(long_key[0:6]))[0] == 0xFF, 'first UNLOCK frame'
    assert exchange(handle, (0xF7, 4) + tuple(long_key[6:10]))[0] == 0xFF, 'second UNLOCK frame'

    assert exchange(handle, DOWNLOAD)[0] == 0xFF, 'a legitimate multi-frame unlock was refused'


def test_an_unlock_after_get_status_is_refused_despite_a_held_seed():
    """Isolates the last_pid conjunct alone -- coordinator ruling on task-2-report.md's mutation 2,
    which found that conjunct unpinned by every scenario in this file: dropping it left all seven
    tests above passing regardless. In six of them the two conjuncts simply agree, so
    seed.total_length alone decides exactly what last_pid alone would have decided. In the seventh,
    test_a_second_unlock_without_a_fresh_seed_is_refused, they disagree -- last_pid is still
    UNLOCK's own pid and so admits, while the seed was discarded by the UNLOCK that consumed it --
    but the AND is false there only because the seed conjunct dominates, which is again a refusal
    seed.total_length produces on its own.

    GET_STATUS is MASK_NONE (always reachable, this file's own module docstring) and
    Xcp_CTOCmdStdGetStatus (source/Xcp_Std.c) never reads or writes Xcp_Internal.seed -- so it
    leaves a just-issued seed exactly as GET_SEED left it. But it is a dispatch like any other, and
    always answers positively, so Xcp_CanIfRxIndication's DD72 gate (source/Xcp.c), which advances
    last_pid past any dispatch whose own response byte 0 is not XCP_PID_ERROR, advances it to
    GET_STATUS's own pid (0xFD). The UNLOCK that follows therefore satisfies the seed.total_length
    conjunct (a seed is genuinely held, untouched) and fails only the last_pid conjunct (0xFD is
    outside {GET_SEED, UNLOCK}) -- the one scenario in this file where they disagree in THIS
    direction, last_pid refusing what the seed conjunct would have admitted, so only a gate that
    checks both refuses it. Confirmed empirically, not just by trace: with
    task-2-report.md's mutation 2 reapplied (last_pid terms dropped, only seed.total_length !=
    0x00u kept), this test fails -- see the report's update for that run.

    xcp_calc_key is armed to succeed with a matching key, not left unconfigured: if the last_pid
    conjunct were ever dropped, this UNLOCK would be admitted, reach Xcp_CalcKey and match,
    answering a clean (0xFF, ...) -- an unambiguous positive, not an artifact of an unconfigured
    mock -- so a broken gate cannot pass this test by accident."""
    handle = cal_protected_handle()
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF, 'GET_SEED(mode=0, CAL_PAG)'
    assert exchange(handle, GET_STATUS)[0] == 0xFF, 'GET_STATUS'

    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'


def test_get_status_reports_which_resources_are_still_protected():
    """DD82. XCP part 2 1.0/1.6.1.1.3 defines the Current Resource Protection Status as a mask
    where 1 = the group IS protected, and 1.6.1.2.5 makes UNLOCK's positive response carry that
    same mask. The module reported the UNLOCKED set instead -- so after unlocking CAL_PAG it said
    CAL_PAG was protected, at the moment it stopped being."""
    handle = cal_protected_handle()

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x01, \
        'CAL_PAG is configured protected and nothing has been unlocked'

    unlock_cal_pag(handle)

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x00, \
        'CAL_PAG was reported protected after being unlocked'


def test_get_status_reports_nothing_protected_when_nothing_is_configured_protected():
    """The domain half of the defect, not just the direction. In a build where no resource is
    protected -- test/parameter.py's DefaultConfig, which is what almost the whole suite runs --
    unlocking PGM used to make this byte report 0x10, claiming a protection the build does not
    have.

    The GET_SEED/UNLOCK round below is what makes this test the domain half rather than a restated
    initial condition: byte 2 reads 0x00 before any unlock on the defective code too, so the first
    assertion alone passes either way. It is kept as a precondition -- an UNLOCK that is refused
    would leave 0x00 standing for the wrong reason -- and the second assertion is the one that
    measures the defect. UNLOCK's own answer is asserted positive for the same reason.

    That precondition checks TWO bytes, not just the PID. On a DD76-shaped regression -- UNLOCK's
    handler writing nothing into the shared cto_response buffer while responseExpected stays TRUE
    (source/Xcp_Std.c; the exact defect test/seed_key_defects_test.py's
    test_an_unlock_whose_calc_key_fails_answers_an_error_instead_of_a_stale_positive_response
    exists for) -- the frame transmitted here is the PREVIOUS command's, i.e. GET_SEED's own
    (0xFF, 0x02, 0x11, 0x22, ...). Its byte 0 is 0xFF too, so a PID-only guard admits it, the
    UNLOCK never ran, and the closing assertion below would then pass vacuously: on this build
    byte 2 is 0x00 whether anything was granted or not, which is precisely the state this test is
    supposed to be measuring against. exchange()'s own reset_mock cannot catch that -- the
    staleness is in the C-side buffer, not the Python mock. UNLOCK's byte 1 is the remaining
    protection mask, 0x00 on a build that protects nothing, while GET_SEED's byte 1 is len(SEED)
    == 2, so the pair tells the two frames apart."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x00

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x10))[0:2] == (0xFF, len(SEED)), 'GET_SEED(mode=0, PGM)'
    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFF, 0x00), 'UNLOCK(PGM)'

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x00, \
        'PGM was reported protected on a build that does not protect it'


def test_unlock_answers_the_remaining_protection_mask():
    """1.6.1.2.5: "The answer upon UNLOCK contains the Current Resource Protection Mask as
    described at GET_STATUS." Byte 1 of UNLOCK's positive response, same polarity as above."""
    handle = cal_protected_handle()
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF
    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFF, 0x00), \
        'UNLOCK reported the granted resource instead of what remains protected'


def test_unlocking_a_second_resource_keeps_the_first_one_granted():
    """The mask ACCUMULATES grants: unlocking DAQ must clear only DAQ's own bit, leaving CAL_PAG's
    grant standing. The inverted field's own writer was `|=` for exactly this reason (DD79); the
    inversion turns that into `&= ~mask` (Xcp_UnlockResources, source/Xcp.c), and an implementation
    that assigned instead would re-lock CAL_PAG here while still answering every single-resource
    test in this file identically.

    Both halves of "still granted" are checked, because they are two different readers of the same
    mask and either could regress alone: the dispatch gate (a MASK_CAL_PAG command, DOWNLOAD, must
    still be admitted) and GET_STATUS byte 2, which must read 0x00 -- nothing left protected -- and
    not 0x01, CAL_PAG protected again.

    Two full GET_SEED/UNLOCK rounds, not one seed stretched over two UNLOCKs: DD81 discards the
    seed on every completed key, so the second unlock needs a seed of its own or it is refused
    ERR_SEQUENCE before it ever reaches Xcp_CalcKey."""
    handle = cal_protected_handle(resource_protection_data_acquisition=True)

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x05, \
        'CAL_PAG (0x01) and DAQ (0x04) are both configured protected and nothing is unlocked yet'

    unlock_cal_pag(handle)

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x04, \
        'CAL_PAG was unlocked, so only DAQ must remain protected'

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x04))[0] == 0xFF, 'GET_SEED(mode=0, DAQ)'
    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFF, 0x00), \
        'UNLOCK(DAQ) must answer an empty remaining-protection mask, both groups now granted'

    assert exchange(handle, DOWNLOAD)[0] == 0xFF, \
        'the CAL_PAG grant was dropped by the DAQ unlock that followed it'
    assert exchange(handle, GET_STATUS, length=3)[2] == 0x00, \
        'GET_STATUS reported CAL_PAG protected again after DAQ was unlocked'

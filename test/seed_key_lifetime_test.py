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
    tests above passing regardless, because each one's seed.total_length happens to already agree
    with what last_pid alone would have decided.

    GET_STATUS is MASK_NONE (always reachable, this file's own module docstring) and
    Xcp_CTOCmdStdGetStatus (source/Xcp_Std.c) never reads or writes Xcp_Internal.seed -- so it
    leaves a just-issued seed exactly as GET_SEED left it. But it is a dispatch like any other, and
    always answers positively, so Xcp_CanIfRxIndication's DD72 gate (source/Xcp.c), which advances
    last_pid past any dispatch whose own response byte 0 is not XCP_PID_ERROR, advances it to
    GET_STATUS's own pid (0xFD). The UNLOCK that follows therefore satisfies the seed.total_length
    conjunct (a seed is genuinely held, untouched) and fails only the last_pid conjunct (0xFD is
    outside {GET_SEED, UNLOCK}) -- the one scenario in this file where the two conjuncts disagree,
    so only a gate that checks both refuses it. Confirmed empirically, not just by trace: with
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

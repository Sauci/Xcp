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

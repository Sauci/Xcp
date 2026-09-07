#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD72 (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md) -- a pre-existing
authentication bypass in shipped seed-and-key code, independent of any feature branch this
repository carries. Measured on the unfixed code: GET_SEED for the PGM resource, made to fail,
answered (0xFE, 0x22); UNLOCK then answered (0xFF, 0x10); GET_STATUS then reported
protection_status = 0x10. The PGM resource was unlocked with no seed ever produced.

Two independent legs, both fixed here:
- Xcp_DTOCmdStdGetSeed (source/Xcp_Std.c) used to commit requested_protected_resource before
  Xcp_GetSeed ran and never rolled it back on failure, so Xcp_SetProtectionStatus (source/Xcp.c)
  could later copy a resource whose own seed request had been refused straight into
  protection_status.
- The CTO dispatch in Xcp_CanIfRxIndication (source/Xcp.c) used to write last_pid for every
  dispatched command unconditionally, including one whose own handler refused it, so
  Xcp_DTOCmdStdUnlock's "last_pid == GET_SEED" admission check (source/Xcp_Std.c) could not tell a
  successful GET_SEED from a refused one.

test_a_failed_get_seed_leaves_the_resource_locked below is the direct reproduction of the measured
scenario and is sensitive to the last_pid leg; test_a_failed_get_seed_does_not_let_a_stale_
admission_grant_the_resource_it_requested isolates the requested_protected_resource leg, which the
first test cannot -- see its own docstring. Both are mutation-verified in task-2-report.md.

Xcp_Internal is not reachable from this CFFI harness (interface/Xcp.h does not include
Xcp_Internal.h), so every assertion below observes through GET_SEED/UNLOCK/GET_STATUS's own wire
responses -- never through Xcp_Internal directly -- following test/clear_daq_list_test.py's own
precedent (test_clear_daq_list_invalidates_a_pointer_aimed_at_it)."""

from .parameter import *
from .conftest import XcpTest
from .download_test import connect
from .seed_key_test import get_seed_key_slices, get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok

CAL_PAG = 0x01
PGM = 0x10

GET_STATUS = (0xFD,)


def get_seed_side_effect_fail(handle):
    """Models an integrator's Xcp_GetSeed that cannot produce a seed for the requested resource:
    E_NOT_OK, and -- since it never touches pSeedLength -- Xcp_Internal.seed.total_length stays at
    the 0 Xcp_DTOCmdStdGetSeed itself resets it to just before this call. Either alone already
    makes Xcp_DTOCmdStdGetSeed's own two checks refuse the request with ERR_OUT_OF_RANGE; both are
    true here for one realistic cause, not to double up on the trigger."""
    def wrapper(_p_seed_buffer, _max_seed_length, _p_seed_length):
        return handle.define('E_NOT_OK')
    return wrapper


def exchange(handle, request):
    """Sends one CTO request and returns the first three response bytes -- enough for every
    assertion in this file: byte 0 is always the PID (0xFF/0xFE), byte 1 is the error code
    (GET_SEED/UNLOCK error responses) or session_status (GET_STATUS), byte 2 is protection_status
    (GET_STATUS only; unused trailing_value padding elsewhere).

    Resets the transmit mock before sending, so a prior exchange's still-buffered response can
    never be misread as this one's, and asserts exactly one transmission happened -- catching a
    handler that silently stopped responding, which a bare call_args read after only
    Xcp_CanIfRxIndication would miss entirely, since Xcp_CanIfRxIndication itself never transmits
    (the response goes out through Xcp_MainFunction). Confirms the transmission before returning,
    matching every existing helper of this shape (download_test.connect,
    clear_daq_list_test.response) -- the convention the rest of this suite always follows before
    issuing a further command."""
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 1, 'no response was transmitted for {}'.format(request)
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return response


def test_a_failed_get_seed_leaves_the_resource_locked():
    """DD72's own measured scenario. GET_SEED(PGM) is made to fail, then UNLOCK offers a key that
    Xcp_CalcKey's own mock is configured to accept regardless of what the (never-produced) seed
    held -- modelling an attacker who already knows what key an empty/absent seed yields, exactly
    the concern DD73 separately names for a real Xcp_CalcKey that ignores its length argument.
    UNLOCK must still be refused, and GET_STATUS must still report the resource locked.

    Before the fix: GET_SEED -> (0xFE, 0x22) [XCP_E_ASAM_OUT_OF_RANGE], UNLOCK -> (0xFF, 0x10)
    [granted], GET_STATUS -> protection_status 0x10. Recorded in task-2-report.md."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.xcp_get_seed.side_effect = get_seed_side_effect_fail(handle)

    get_seed_response = exchange(handle, (0xF8, 0x00, PGM))
    assert get_seed_response[0:2] == (0xFE, 0x22)

    key = [0x99]
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, key)

    unlock_response = exchange(handle, (0xF7, len(key), *key))
    assert unlock_response[0] == 0xFE, (
        'UNLOCK was admitted ({}) even though its own GET_SEED answered ERR_OUT_OF_RANGE'.format(
                unlock_response))
    assert unlock_response[0:2] == (0xFE, 0x29)  # XCP_E_ASAM_SEQUENCE

    status_response = exchange(handle, GET_STATUS)
    assert status_response[2] == 0x00, (
        'protection_status=0x{:02X} after a failed GET_SEED and a should-be-refused UNLOCK '
        '(GET_SEED: {}, UNLOCK: {})'.format(status_response[2], get_seed_response, unlock_response))


def test_a_failed_get_seed_does_not_let_a_stale_admission_grant_the_resource_it_requested():
    """Isolates the requested_protected_resource leg. A GET_SEED/UNLOCK exchange for CAL_PAG
    completes legitimately first, which -- 1.1/1.6.1.1.7's own multi-frame KEY continuation
    support, admitting a further UNLOCK whenever last_pid is already UNLOCK's own pid -- leaves
    last_pid sitting on a value Xcp_DTOCmdStdUnlock accepts. A second GET_SEED, for PGM this time,
    is then made to fail: with only the last_pid leg fixed, that failure does not touch last_pid,
    so it is still left at UNLOCK's pid from the CAL_PAG exchange above rather than CONNECT's --
    and an immediately following UNLOCK is admitted through that carryover regardless of the
    last_pid leg's own state. What must not happen is that admission granting PGM: whether it
    grants CAL_PAG again (a harmless re-grant of what was already legitimately obtained) or PGM
    (the bypass) turns entirely on requested_protected_resource, which is this test's own target.

    test_a_failed_get_seed_leaves_the_resource_locked above cannot show this: immediately after
    CONNECT, last_pid is CONNECT's own pid, already outside {GET_SEED, UNLOCK}, so the last_pid leg
    alone already refuses that test's UNLOCK regardless of what requested_protected_resource holds.
    Mutation-verified in task-2-report.md."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    legitimate_seed = [0x11, 0x22]
    # Xcp_CheckMasterSlaveKeyMatch only compares against whatever Xcp_CalcKey's own mock below
    # returns, not against the seed itself -- binding the two together for real is DD73's own,
    # separate concern -- so this need not (and deliberately does not) look like a function of
    # legitimate_seed.
    legitimate_key = [0xAA, 0xBB]
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, legitimate_seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, legitimate_key)

    get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG))
    assert get_seed_response[0:2] == (0xFF, len(legitimate_seed))

    unlock_response = exchange(handle, (0xF7, len(legitimate_key), *legitimate_key))
    assert unlock_response[0:2] == (0xFF, CAL_PAG)

    handle.xcp_get_seed.side_effect = get_seed_side_effect_fail(handle)

    failed_get_seed_response = exchange(handle, (0xF8, 0x00, PGM))
    assert failed_get_seed_response[0:2] == (0xFE, 0x22)

    second_unlock_response = exchange(handle, (0xF7, len(legitimate_key), *legitimate_key))

    status_response = exchange(handle, GET_STATUS)
    assert status_response[2] == CAL_PAG, (
        'protection_status=0x{:02X} after PGM\'s own GET_SEED answered ERR_OUT_OF_RANGE -- '
        'expected CAL_PAG (0x{:02X}, already legitimately granted) or, if PGM leaked through, '
        '0x{:02X} (first UNLOCK: {}, failed GET_SEED: {}, second UNLOCK: {})'.format(
                status_response[2], CAL_PAG, PGM, unlock_response, failed_get_seed_response,
                second_unlock_response))


@pytest.mark.parametrize('resource', resources)
def test_a_legitimate_multi_frame_get_seed_and_unlock_sequence_still_unlocks_the_resource(resource):
    """The neighbour this task's fix most endangers (task-2-brief.md step 4): both legs tighten an
    admission test -- Xcp_DTOCmdStdUnlock's own last_pid gate, and what Xcp_DTOCmdStdGetSeed
    commits into requested_protected_resource -- and tightening one is exactly how a legitimate
    sequence gets broken. max_cto=8 with a 10-byte seed forces both GET_SEED and UNLOCK across two
    frames each (6 + 4), so this exercises the mode=1 seed continuation and the split-key
    continuation together, then checks the grant took effect through GET_STATUS rather than
    trusting UNLOCK's own final response alone."""
    max_cto = 8
    seed = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA]
    key = seed

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto))
    connect(handle)

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, key)

    seed_slices = get_seed_key_slices(seed, max_cto=max_cto)
    key_slices = get_seed_key_slices(key, max_cto=max_cto)
    # Both must actually span more than one frame, or this would not be the scenario this test's
    # own name and docstring claim.
    assert len(seed_slices) > 1
    assert len(key_slices) > 1

    for mode, _ in zip([0] + [1] * (len(seed_slices) - 1), seed_slices):
        response = exchange(handle, (0xF8, mode, resource))
        assert response[0] == 0xFF

    remaining_key_length = len(key)
    for key_slice in key_slices:
        response = exchange(handle, (0xF7, remaining_key_length, *key_slice))
        assert response[0] == 0xFF
        remaining_key_length -= len(key_slice)

    status_response = exchange(handle, GET_STATUS)
    assert status_response[2] == resource, (
        'GET_STATUS reported protection_status=0x{:02X}, expected the requested resource 0x{:02X} '
        'to be granted'.format(status_response[2], resource))

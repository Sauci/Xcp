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

DD73 -- a second, independent pre-existing defect in the same shipped seed-and-key code: the key
calculation must receive the seed's actual length, not the "bytes left to send" bookkeeping
Xcp_DTOCmdStdGetSeed (source/Xcp_Std.c) used to leave behind once GET_SEED's own final chunk had
gone out. Xcp_DTOCmdStdUnlock (source/Xcp_Std.c) reads that same total_length field as the seed
LENGTH it passes to Xcp_CalcKey -- so on unfixed code Xcp_CalcKey was called with seedLength=0 for
every seed, every session, and an integrator honouring that parameter (test/stub/Xcp_SeedKey.h)
computed its key from a zero-length seed: the key was not bound to the challenge, which XCP part 2
- Protocol Layer Specification 1.1/1.6.1.2.4 and 1.1/1.6.1.2.5 both require it to be (the same key
would then be valid in every session). Nothing caught this because calc_key_side_effect_copy_ok
(test/seed_key_test.py), the only double UNLOCK's key check ever went through, ignores the
seedLength argument -- a double that cannot observe the value under test cannot fail when that
value is wrong. test_unlock_computes_the_key_from_the_seeds_actual_length below uses
calc_key_side_effect_recording_seed_length instead, defined in this file, which records what it
actually receives. Mutation-verified in task-3-report.md.

Task 7 (.superpowers/sdd/2026-09-07-xcp-shared-state-defects/task-7-report.md) -- a third,
independent pre-existing defect in the same shipped seed-and-key code, found by the acceptance
pass over DD70-DD75 (task-6-report.md's own "SEVENTH DEFECT FOUND... route C") rather than by the
original design document. Xcp_DTOCmdStdUnlock's `if (Xcp_CalcKey(...) == E_OK)` (source/Xcp_Std.c)
had no `else`: when the integrator's own key-derivation callback fails outright -- not a key
MISMATCH, DD72's own concern above, but Xcp_CalcKey itself returning E_NOT_OK -- responseExpected
stays TRUE regardless and nothing overwrote the shared response buffer, so the previous command's
own answer (typically GET_SEED's) was retransmitted as this UNLOCK's. This also fed a stale
non-error byte 0 to the last_pid gate DD72 added (source/Xcp.c), so a failed UNLOCK could record a
success there too, though Xcp_DTOCmdStdUnlock's own admission test cannot tell last_pid's two
admitted values apart, which bounds what that second consequence can be observed to do -- see
test_a_failed_unlock_does_not_leave_a_stale_answer_for_whatever_reads_it_next's own docstring.
Fixed by filling XCP_E_ASAM_GENERIC (0x31), a recorded deviation -- 1.7.3.2.1's own UNLOCK row
lists no code for an integrator callback failing outright -- matching the identical deviation
source/Xcp_Pgm.c's DD57 already recorded for PROGRAM_RESET's own integrator-callback completion.
test_an_unlock_whose_calc_key_fails_answers_an_error_instead_of_a_stale_positive_response below is
the direct reproduction; test_a_key_mismatch_still_answers_access_locked_not_the_calc_key_failure_
code is the neighbour DD72's own sibling `else` (ERR_ACCESS_LOCKED, a key MISMATCH) must not be
confused with. Mutation-verified in task-7-report.md.

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


def calc_key_side_effect_recording_seed_length(handle, key, received_seed_lengths):
    """DD73's own double. calc_key_side_effect_copy_ok (test/seed_key_test.py) -- the only
    Xcp_CalcKey double used anywhere else in this suite -- names its seedLength parameter
    `_seed_length`, the underscore marking it deliberately unread: it is why DD73 shipped, since a
    double that never looks at the parameter under test cannot fail when the module gets it wrong.
    This wrapper is otherwise identical (same unconditional E_OK, same unconditional copy of `key`
    into the slave key buffer, so it isolates DD73 from the master/slave key comparison exactly as
    calc_key_side_effect_copy_ok does) except that it appends the seedLength it actually received
    to received_seed_lengths, letting the calling test assert on it directly rather than reaching
    into handle.xcp_calc_key's own MagicMock call history."""
    def wrapper(_p_seed_buffer, seed_length, p_key_buffer, _max_key_length, p_key_length):
        received_seed_lengths.append(seed_length)
        for i, b in enumerate(key):
            p_key_buffer[i] = b
        p_key_length[0] = len(key)
        return handle.define('E_OK')
    return wrapper


def calc_key_side_effect_fail(handle):
    """Models an integrator's Xcp_CalcKey that cannot derive a key from the seed it was given at
    all -- E_NOT_OK, touching neither pKeyBuffer nor pKeyLength -- as distinct from
    calc_key_side_effect_copy_ok's E_OK-but-wrong-key and Xcp_CheckMasterSlaveKeyMatch's own
    mismatch: here the slave never produces a key to compare in the first place. This is task 7's
    own double (.superpowers/sdd/2026-09-07-xcp-shared-state-defects/task-7-report.md): the
    condition behind Xcp_DTOCmdStdUnlock's missing `else` (source/Xcp_Std.c, the `if
    (Xcp_CalcKey(...) == E_OK)` opened at the time of writing around line 806)."""
    def wrapper(_p_seed_buffer, _seed_length, _p_key_buffer, _max_key_length, _p_key_length):
        return handle.define('E_NOT_OK')
    return wrapper


def exchange(handle, request, length=3):
    """Sends one CTO request and returns the first `length` response bytes -- 3 is enough for
    every status-code assertion in this file: byte 0 is always the PID (0xFF/0xFE), byte 1 is the
    error code (GET_SEED/UNLOCK error responses) or session_status (GET_STATUS), byte 2 is
    protection_status (GET_STATUS only; unused trailing_value padding elsewhere). A caller that
    needs to check the transmitted DATA too -- GET_SEED's own seed bytes, task-3-brief.md step 4 --
    passes a larger length; SduDataPtr always holds a full MAX_CTO-sized frame, so any length up to
    MAX_CTO is safe to read regardless of how many of those bytes this particular response filled.

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
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])
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
    completes legitimately first, which -- 1.1/1.6.1.2.5's own multi-frame KEY continuation
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


def test_unlock_computes_the_key_from_the_seeds_actual_length():
    """DD73's own measured scenario, single-frame: the seed 0x11 0x22 0x33 0x44 is the design
    doc's own example, and both it and the one-byte key fit in one CTO at the default MAX_CTO=8.
    A legitimate GET_SEED/UNLOCK exchange -- checking not UNLOCK's own response, which does not
    depend on seedLength at all here (calc_key_side_effect_recording_seed_length below returns
    E_OK and a fixed key unconditionally, whatever it is told the seed's length is) -- but what
    Xcp_CalcKey was actually called with.

    On unfixed code, Xcp_DTOCmdStdGetSeed (source/Xcp_Std.c) reset Xcp_Internal.seed.total_length
    to 0x00u once this single frame had carried the whole seed, and Xcp_DTOCmdStdUnlock
    (source/Xcp_Std.c) then read that same field as the seed length passed to Xcp_CalcKey:
    received_seed_lengths == [0], for every seed -- matching the design doc's own measurement
    exactly. test_a_legitimate_multi_frame_get_seed_and_unlock_sequence_still_unlocks_the_resource
    below makes the same assertion for a seed spanning more than one frame -- task-3-brief.md's
    own neighbour (step 4), since total_length's pacing role is exactly what the fix changes."""
    seed = [0x11, 0x22, 0x33, 0x44]
    key = [0x99]

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    received_seed_lengths = []
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_recording_seed_length(
            handle, key, received_seed_lengths)

    get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG), length=2 + len(seed))
    assert get_seed_response[0:2] == (0xFF, len(seed))
    assert list(get_seed_response[2:2 + len(seed)]) == seed, (
        'GET_SEED transmitted {}, expected the configured seed {}'.format(
                list(get_seed_response[2:2 + len(seed)]), seed))

    unlock_response = exchange(handle, (0xF7, len(key), *key))
    assert unlock_response[0:2] == (0xFF, CAL_PAG), (
        'UNLOCK was not admitted ({}) for a legitimate single-frame seed/key exchange'.format(
                unlock_response))

    assert received_seed_lengths == [len(seed)], (
        'Xcp_CalcKey received seedLength={} for a {}-byte seed {} -- the key was not computed '
        'from the seed actually transmitted on the wire'.format(
                received_seed_lengths, len(seed), seed))


@pytest.mark.parametrize('resource', resources)
def test_a_legitimate_multi_frame_get_seed_and_unlock_sequence_still_unlocks_the_resource(resource):
    """The neighbour this task's fix most endangers (task-2-brief.md step 4): both legs tighten an
    admission test -- Xcp_DTOCmdStdUnlock's own last_pid gate, and what Xcp_DTOCmdStdGetSeed
    commits into requested_protected_resource -- and tightening one is exactly how a legitimate
    sequence gets broken. max_cto=8 with a 10-byte seed forces both GET_SEED and UNLOCK across two
    frames each (6 + 4), so this exercises the mode=1 seed continuation and the split-key
    continuation together, then checks the grant took effect through GET_STATUS rather than
    trusting UNLOCK's own final response alone.

    Also DD73's own neighbour (task-3-brief.md step 4): Xcp_Internal.seed.total_length is what
    paces this multi-frame GET_SEED transmission -- the response byte reporting how much is left,
    and the boundary between "the rest fits in this frame" and "one more frame is needed" both
    read it -- which is exactly the field DD73's fix stops resetting mid-sequence. So this
    reconstructs the seed from every GET_SEED frame's own transmitted bytes, not merely each
    frame's reported length or the frame count (either of which the fix could satisfy by
    accident), and confirms Xcp_CalcKey's own double received seedLength == len(seed) -- the value
    the pre-fix code zeroed out -- here in the multi-frame case, complementing
    test_unlock_computes_the_key_from_the_seeds_actual_length's single-frame one above."""
    max_cto = 8
    seed = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA]
    key = seed

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto))
    connect(handle)

    received_seed_lengths = []
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_recording_seed_length(
            handle, key, received_seed_lengths)

    seed_slices = get_seed_key_slices(seed, max_cto=max_cto)
    key_slices = get_seed_key_slices(key, max_cto=max_cto)
    # Both must actually span more than one frame, or this would not be the scenario this test's
    # own name and docstring claim.
    assert len(seed_slices) > 1
    assert len(key_slices) > 1

    actual_seed = []
    remaining_seed_length = len(seed)
    for mode, seed_slice in zip([0] + [1] * (len(seed_slices) - 1), seed_slices):
        response = exchange(handle, (0xF8, mode, resource), length=max_cto)
        assert response[0:2] == (0xFF, remaining_seed_length)
        actual_seed += list(response[2:2 + len(seed_slice)])
        remaining_seed_length -= len(seed_slice)

    assert actual_seed == seed, (
        'GET_SEED transmitted {} across {} frames, expected the configured seed {}'.format(
                actual_seed, len(seed_slices), seed))

    remaining_key_length = len(key)
    for key_slice in key_slices:
        response = exchange(handle, (0xF7, remaining_key_length, *key_slice))
        assert response[0] == 0xFF
        remaining_key_length -= len(key_slice)

    assert received_seed_lengths == [len(seed)], (
        'Xcp_CalcKey received seedLength={} for a {}-byte seed {} transmitted across {} frames -- '
        'the key was not computed from the seed actually transmitted on the wire'.format(
                received_seed_lengths, len(seed), seed, len(seed_slices)))

    status_response = exchange(handle, GET_STATUS)
    assert status_response[2] == resource, (
        'GET_STATUS reported protection_status=0x{:02X}, expected the requested resource 0x{:02X} '
        'to be granted'.format(status_response[2], resource))


def test_an_unlock_whose_calc_key_fails_answers_an_error_instead_of_a_stale_positive_response():
    """Task 7 (.superpowers/sdd/2026-09-07-xcp-shared-state-defects/task-7-report.md) -- a
    pre-existing defect, found by the acceptance pass over this branch's own six shared-state
    fixes (DD70-DD75) and unchanged by any of them, though the last_pid leg of DD72 (source/Xcp.c)
    now depends on the field this defect corrupts. See
    test_a_failed_unlock_does_not_leave_a_stale_answer_for_whatever_reads_it_next below for that
    second consequence.

    Xcp_DTOCmdStdUnlock's `if (Xcp_CalcKey(...) == E_OK)` (source/Xcp_Std.c) used to have no
    `else`. calc_key_side_effect_fail models an integrator whose key-derivation callback itself
    fails outright -- E_NOT_OK, touching neither output parameter -- which is a different
    condition from a KEY MISMATCH (Xcp_CheckMasterSlaveKeyMatch failing after Xcp_CalcKey
    successfully produces a key that just does not match the master's own -- see
    test_a_key_mismatch_still_answers_access_locked_not_the_calc_key_failure_code below, the
    sibling branch this one must not be confused with). responseExpected stays TRUE regardless
    (set at this function's own entry), so with no else nothing overwrote
    cto_response.pdu_info: the previous command's own response was retransmitted as this UNLOCK's
    answer instead.

    Measured on the unfixed code, this exact scenario: GET_SEED answered
    (0xFF, 0x04, 0x11, 0x22, 0x33, 0x44) -- a genuine, successful seed. UNLOCK, whose Xcp_CalcKey
    then failed, answered (0xFF, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00): PID 0xFF (RESPONSE,
    not ERR), byte 1 the number 0x04 -- not a protection status this UNLOCK ever computed, but
    GET_SEED's own remaining-length byte, left over in the shared buffer -- and bytes 2.. zeroed by
    this UNLOCK's own Xcp_FinalizeResPacket(2) call (source/Xcp.c; it pads from index 2 onward and
    never touches byte 0 or byte 1, which is exactly why they were still GET_SEED's). GET_STATUS
    afterwards still reported protection_status=0x00 -- nothing was actually granted -- so the
    defect is the master being told a false positive, not (by itself) a privilege grant.

    After the fix: UNLOCK answers (0xFE, 0x31) -- ERR_GENERIC. See source/Xcp_Std.c's own comment
    at the XCP_E_ASAM_GENERIC call for why none of XCP part 2 - Protocol Layer Specification
    1.0/1.7.3.2.1's seven listed UNLOCK error codes (verified against the 1.0 PDF, which
    pdftotext -layout extracts cleanly) fits an integrator callback failing outright, and why
    ERR_GENERIC is the same recorded deviation DD57 already uses for PROGRAM_RESET's identical
    shape of problem (source/Xcp_Pgm.c)."""
    seed = [0x11, 0x22, 0x33, 0x44]
    key = [0x99]

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_fail(handle)

    get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG), length=2 + len(seed))
    assert get_seed_response[0:2] == (0xFF, len(seed))

    unlock_response = exchange(handle, (0xF7, len(key), *key), length=8)
    assert unlock_response[0] != 0xFF, (
        'UNLOCK answered a positive PID (0xFF) although its own Xcp_CalcKey returned E_NOT_OK -- '
        'the previous command\'s (GET_SEED\'s) response is still sitting in the shared buffer and '
        'was retransmitted as this UNLOCK\'s own answer: {}'.format(unlock_response))
    assert unlock_response[0:2] == (0xFE, 0x31), (
        'UNLOCK answered {} for a failed Xcp_CalcKey, expected (0xFE, 0x31) [ERR_GENERIC]'.format(
                unlock_response))

    status_response = exchange(handle, GET_STATUS)
    assert status_response[2] == 0x00, (
        'protection_status=0x{:02X} after a GET_SEED/UNLOCK exchange whose Xcp_CalcKey failed -- '
        'nothing should have been granted'.format(status_response[2]))


def test_a_failed_unlock_does_not_leave_a_stale_answer_for_whatever_reads_it_next():
    """Task 7's second consequence. Xcp_CanIfRxIndication's last_pid gate (source/Xcp.c, DD72)
    only advances Xcp_Internal.last_pid past a dispatch whose own response byte 0 is NOT
    XCP_PID_ERROR -- so a failed UNLOCK that (pre-fix) left a stale, non-error byte 0 behind was
    indistinguishable from a successful one, and last_pid recorded a success this dispatch never
    earned. Xcp_Internal is not reachable from this CFFI harness (interface/Xcp.h does not include
    Xcp_Internal.h -- see this file's own module docstring), so last_pid's value cannot be read
    directly; this observes the fix's effect through consequences instead.

    What last_pid actually gates in Xcp_DTOCmdStdUnlock is membership in
    {GET_SEED, UNLOCK} (source/Xcp_Std.c's own `if ((last_pid == GET_SEED) || (last_pid ==
    UNLOCK))`), by design admitting a FURTHER unlock attempt whenever last_pid is already UNLOCK's
    own pid -- 1.0/1.6.1.2.5's own multi-frame key continuation, and the same mechanism
    test_a_failed_get_seed_does_not_let_a_stale_admission_grant_the_resource_it_requested above
    already exercises. Reaching Xcp_DTOCmdStdUnlock's own Xcp_CalcKey call at all -- pre-fix or
    post-fix -- already requires last_pid to be GET_SEED or UNLOCK, and whichever of those two
    member values it ends up as afterwards, a following UNLOCK is equally admitted through that
    same membership test either way: last_pid landing on the WRONG one of its two admitted values
    is not something Xcp_DTOCmdStdUnlock's own gate can ever tell apart (confirmed by direct trace
    and empirically, both ways, while investigating this task -- see task-7-report.md). So a bare
    "does a following UNLOCK get admitted" probe cannot isolate this leg the way
    DD72's own two tests isolate its two legs -- unlike GET_SEED failing, which (immediately after
    CONNECT) can flip last_pid from OUTSIDE that set to inside it, UNLOCK failing never can, since
    reaching its own failure path already means last_pid was inside the set to begin with.

    What the fix actually guarantees, and what this test pins instead: every dispatch that reads
    byte 0 next -- including DD72's own gate, and including the following UNLOCK's own answer --
    now sees the truth. A chain of failing UNLOCK attempts (fresh key bytes each time, no new
    GET_SEED reissued in between -- Xcp_DTOCmdStdUnlock discards the seed once a full key has been
    received, success or failure, so none would even be honoured) never again shows the stale
    positive response the defect used to produce, on the first attempt or any later one, and
    GET_STATUS confirms nothing is ever granted across the whole chain."""
    seed = [0x11, 0x22, 0x33, 0x44]

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_fail(handle)

    get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG), length=2 + len(seed))
    assert get_seed_response[0:2] == (0xFF, len(seed))

    for attempt, key in enumerate(([0x99], [0x55], [0x11, 0x22])):
        unlock_response = exchange(handle, (0xF7, len(key), *key), length=8)
        assert unlock_response[0:2] == (0xFE, 0x31), (
            'UNLOCK attempt #{} (key={}) answered {}, expected (0xFE, 0x31) [ERR_GENERIC] again -- '
            'a stale answer from an earlier exchange would show up here as something else, most '
            'likely a positive (0xFF, ...) reply nobody computed'.format(attempt, key, unlock_response))

    status_response = exchange(handle, GET_STATUS)
    assert status_response[2] == 0x00, (
        'protection_status=0x{:02X} after a chain of UNLOCK attempts whose Xcp_CalcKey always '
        'failed -- nothing should ever have been granted'.format(status_response[2]))


def test_a_key_mismatch_still_answers_access_locked_not_the_calc_key_failure_code():
    """Task 7's own neighbour: Xcp_CalcKey failing outright (this file's own
    calc_key_side_effect_fail, task 7's own condition, answered ERR_GENERIC -- see
    test_an_unlock_whose_calc_key_fails_answers_an_error_instead_of_a_stale_positive_response
    above) is a different condition from Xcp_CalcKey SUCCEEDING with a key that then does not
    match the master's own (Xcp_CheckMasterSlaveKeyMatch failing, source/Xcp_Std.c's sibling
    `else` immediately above task 7's own new branch), which XCP part 2 - Protocol Layer
    Specification 1.0/1.6.1.2.5 answers ERR_ACCESS_LOCKED and disconnects for. The two must not be
    conflated -- easy to do by accident, since both are reached from the exact same `if
    (Xcp_CalcKey(...) == E_OK)` this task edited. test_unlock_disconnects_the_master_if_key_is_
    invalid (test/seed_key_test.py) already covers this scenario but pins it weakly (only
    call_count, never UNLOCK's own response bytes); this is the same scenario with the same
    exchange()-based rigor (reset_mock, exactly one transmission) the rest of this file already
    uses, kept here rather than in that file because it exists specifically to guard task 7's own
    new branch."""
    seed = [0x11]

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    def calc_key_side_effect_mismatch(_p_seed_buffer, _seed_length, p_key_buffer, _max_key_length, p_key_length):
        for i, b in enumerate(seed):
            p_key_buffer[i] = (~b) & 0xFF
        p_key_length[0] = len(seed)
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_mismatch

    get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG), length=2 + len(seed))
    assert get_seed_response[0:2] == (0xFF, len(seed))

    unlock_response = exchange(handle, (0xF7, len(seed), *seed), length=8)
    assert unlock_response[0:2] == (0xFE, 0x25), (
        'UNLOCK answered {} for a KEY MISMATCH (Xcp_CalcKey succeeded), expected (0xFE, 0x25) '
        '[ERR_ACCESS_LOCKED] -- not task 7\'s own (0xFE, 0x31) [ERR_GENERIC], which is for '
        'Xcp_CalcKey failing outright, a different condition'.format(unlock_response))

    # 1.0/1.6.1.2.5: "the slave device will then go to disconnected state" -- unlike task 7's own
    # ERR_GENERIC branch, which does not disconnect (see source/Xcp_Std.c's own comment on why
    # not). GET_STATUS must therefore go entirely unanswered here.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(GET_STATUS))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 0, (
        'GET_STATUS was answered after a key-mismatch UNLOCK, but 1.0/1.6.1.2.5 disconnects the '
        'session on a rejected key -- a disconnected slave processes nothing but CONNECT')


def test_get_seed_mode_1_after_the_whole_seed_was_sent_answers_zero_remaining():
    """Final review, F3. DD73 stopped Xcp_DTOCmdStdGetSeed (source/Xcp_Std.c) zeroing
    seed.total_length once the final chunk goes out -- that zeroing was the DD73 defect, because
    Xcp_DTOCmdStdUnlock reads the same field as the seed LENGTH it hands Xcp_CalcKey.

    Removing it changed one behaviour nobody asked about and no test covered. The `mode == 1` gate
    at source/Xcp_Std.c:990 is `total_length != 0`, so on the old code a mode=1 request made after
    the seed had been fully transmitted found total_length == 0 and answered ERR_SEQUENCE; now the
    gate passes, 0 bytes remain, and the slave answers (0xFF, 0x00).

    The new answer is the defensible one -- 1.1/1.6.1.2.4's ERR_SEQUENCE rule is about a mode=1
    with no preceding mode=0 request at all, which is a different thing from "you have already
    been sent everything" -- but it was an accident of the DD73 fix rather than a decision, so it
    is pinned here and recorded in the DD73 entry.

    The existing coverage cannot reach this state: seed_key_test.py's only mode=1 test
    parametrises 7..12-byte seeds at MAX_CTO=8, so a remainder always survives the first frame.
    This test uses a 4-byte seed, which fits entirely in the first frame's 6 payload bytes."""
    seed = [0xDE, 0xAD, 0xBE, 0xEF]
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))

    def get_seed_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed):
            p_seed_buffer[i] = b
        p_seed_length[0] = len(seed)
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_side_effect

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED mode=0: the whole 4-byte seed leaves in this one frame, so nothing remains.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 1
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, len(seed))
    assert list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:2 + len(seed)]) == seed
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # Reset before the request under test. The mode=0 answer above is (0xFF, 0x04) and the one
    # checked below is (0xFF, 0x00), so they differ in byte 1 -- but call_args is a live view into
    # the single shared cto_response buffer, not a snapshot, so the count check is what actually
    # distinguishes "mode=1 was answered" from "nothing was dispatched".
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, 0x00)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP4c Task 1: PROGRAM_VERIFY (0xC8), the thinnest of the three commands this sub-project adds and
the one that establishes its schema/generation/dispatch plumbing (design doc
docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md, DD91). Unlike every PGM command
pgm_clear_test.py/pgm_program_test.py/pgm_session_test.py exercise, PROGRAM_VERIFY carries no
Xcp_Internal.pgm_state gate and touches no MTA (design doc Section 1, this task's own 'Consumes:
nothing') -- so pgm_handle() alone, with no PROGRAM_START/PROGRAM_PREPARE dance first, is already a
sufficient starting point for every test below."""

import pytest

from .parameter import u16_to_array, u32_to_array
from .pgm_deferred_test import pgm_handle, transmitted
from .pgm_session_test import send


def pgm_verify_handle(**kwargs):
    """A connected slave with the flash-programming gate on and PROGRAM_VERIFY enabled.

    Unlike pgm_clear_test.py's own pgm_clear_handle(), this can simply forward to
    pgm_deferred_test.pgm_handle(): xcp_program_verify_api_enable is not one of the three keys
    pgm_handle() forces False (xcp_program_clear_api_enable, xcp_program_api_enable,
    xcp_program_max_api_enable -- the three CONNECT's own flash-programming resource bit is defined
    by; none of that is this file's concern), and test/parameter.py's own DefaultConfig gives the
    new key the same default every other xcp_program_*_api_enable key already has (True) -- so a
    plain pgm_handle() call already answers PROGRAM_VERIFY for real. This wrapper exists only so
    this file follows the same one-helper-per-command convention pgm_clear_test.py and
    pgm_program_test.py both use, and so a kwarg override (e.g. xcp_program_verify_api_enable=False,
    test 5 below) has one obvious place to go."""
    return pgm_handle(**kwargs)


def test_program_verify_passes_mode_type_and_value_exactly_as_transmitted_and_answers_ff_on_success():
    """Brief test 1. Asserted on handle.xcp_program_verify.call_args -- the actual arguments the
    mock recorded -- rather than on call_count alone: a double that is only checked for call_count
    would still pass a handler that forwarded the wrong byte, swapped mode and type, or read the
    DWORD at the wrong offset, which is the repeated trap this task's own brief warns about by
    name. mode (0x3C) and value (0x89ABCDEF) are both distinctive -- neither 0 nor producible by
    misreading a neighbouring field -- and verification_type is 0x0002 (code areas, the brief's own
    example), a genuinely defined, non-reserved value so this exchange does not double as test 2's
    own reserved-bit refusal below.

    frame[0] == 0xFF relies on conftest.py's own default mock behaviour (return_value=E_OK, no
    side_effect configured here), which leaves the handler's own locally-initialised status_code at
    0 -- the same default every other PGM polled-callback test in this suite relies on for its own
    'answers positively with no explicit side_effect' cases (e.g.
    pgm_clear_test.py's test_program_clear_passes_the_current_mta_and_clear_range_to_the_integrator).

    Mutation: dropping the argument forwarding (Xcp_DTOCmdPgmProgramVerify calling
    Xcp_ProgramVerify with constants, or with the wrong local, instead of the parsed request
    fields) leaves frame[0] == 0xFF unchanged -- call_count alone could never catch it -- but fails
    the call_args assertions below."""
    handle = pgm_verify_handle()

    frame = send(handle, (0xC8, 0x3C, 0x02, 0x00) + tuple(u32_to_array(0x89ABCDEF, 'LITTLE_ENDIAN')))

    assert frame[0] == 0xFF, 'the callback reports success by default (conftest.py)'
    mode, verification_type, value, _p_status_code = handle.xcp_program_verify.call_args[0]
    assert mode == 0x3C, 'verificationMode must be the request byte exactly as transmitted'
    assert verification_type == 0x0002, \
        'verificationType must be the request WORD exactly as transmitted (code areas)'
    assert value == 0x89ABCDEF, 'verificationValue must be the request DWORD exactly as transmitted'


@pytest.mark.parametrize('reserved_bit', (0x0008, 0x0010, 0x0020, 0x0040, 0x0080))
def test_program_verify_refuses_each_reserved_verification_type_bit_without_calling_the_integrator(reserved_bit):
    """Brief test 2. XCP part 2 - Protocol Layer Specification 1.6.5.2.7 marks 0x0008..0x0080
    reserved (design doc DD91) -- five individual bits, not one combined range -- so this is
    parametrised over each bit on its own rather than over one value that ORs them together
    (0x00F8): a handler that checked only `== 0x0008` explicitly, or masked with the wrong
    constant, would still refuse a combined 0x00F8 (some bit in it always matches) while silently
    admitting several of the individual bits this parametrisation catches one at a time.

    call_count == 0 is the assertion that actually matters, not merely the wire response: a
    handler that called Xcp_ProgramVerify first and refused afterwards would still answer (0xFE,
    0x22) here, the same trap pgm_clear_test.py's own mode-byte tests already document for
    PROGRAM_CLEAR.

    Mutation: inverting the reserved-bit check (refuse -> accept) makes every one of these five
    cases reach the integrator and answer (0xFF,) instead, with call_count == 1, not 0."""
    handle = pgm_verify_handle()

    frame = send(handle, (0xC8, 0x00) + tuple(u16_to_array(reserved_bit, 'LITTLE_ENDIAN')) +
                          tuple(u32_to_array(0x00000000, 'LITTLE_ENDIAN')))

    assert frame[0:2] == (0xFE, 0x22), \
        'ERR_OUT_OF_RANGE for a reserved verification_type bit (0x%04X)' % reserved_bit
    assert handle.xcp_program_verify.call_count == 0, \
        'a reserved verification-type bit must never reach the integrator'


@pytest.mark.parametrize('verification_type', (0x0004, 0x0100))
def test_program_verify_accepts_and_forwards_the_values_immediately_outside_the_reserved_span(verification_type):
    """Task 1 review, fix round 1, Important finding: the reserved span's own boundaries were
    unverified. test_program_verify_refuses_each_reserved_verification_type_bit_... below pins the
    five reserved bits themselves (0x0008..0x0080), and every positive-path test elsewhere in this
    file uses 0x0002 -- so nothing distinguished the correct mask (0x00F8u, exactly 0x0008..0x0080)
    from an off-by-one neighbour that also swallows an adjacent, legal bit. 0x0004 is 'complete
    flash', the highest DEFINED bit (1.6.5.2.7), immediately below the reserved span's own 0x0008
    floor; 0x0100 is the lowest USER DEFINED bit, immediately above the reserved span's own 0x0080
    ceiling. Neither is reserved, so both must reach the integrator, with the exact value intact --
    not merely 'not refused', which a wire-only assertion could satisfy by accident if the module
    answered positively without ever calling Xcp_ProgramVerify at all.

    Mutation (measured for the review, task-1-report.md fix round 1): masking with 0x00FCu (0x00F8u
    | 0x0004u) makes the 0x0004 case fail -- refused (0xFE, 0x22) instead of reaching the
    integrator. Masking with 0x01F8u (0x00F8u | 0x0100u) makes the 0x0100 case fail the identical
    way. Each mutation fails only its own case; the other passes unaffected, since 0x00FCu still
    leaves 0x0100 alone and 0x01F8u still leaves 0x0004 alone -- confirming each boundary needs its
    own case, not one shared value that fails to catch a defect in the OTHER direction."""
    handle = pgm_verify_handle()

    frame = send(handle, (0xC8, 0x00) + tuple(u16_to_array(verification_type, 'LITTLE_ENDIAN')) +
                          tuple(u32_to_array(0x11223344, 'LITTLE_ENDIAN')))

    assert frame[0] == 0xFF, \
        'a value immediately outside the reserved span (0x%04X) must reach the integrator and ' \
        'succeed, not be refused as if it were reserved' % verification_type
    mode, actual_type, value, _p_status_code = handle.xcp_program_verify.call_args[0]
    assert actual_type == verification_type, \
        'the exact boundary value must reach the integrator, not a neighbouring one'
    assert value == 0x11223344, 'verificationValue must still be forwarded exactly alongside it'


def test_program_verify_refuses_a_reserved_bit_even_when_combined_with_a_defined_one():
    """Task 1 review, fix round 1, Important finding's second half: 'consider also whether a
    reserved bit combined with a defined one should be refused'. 0x0081 = 0x0080 (reserved) | 0x0001
    (calibration areas, defined) -- chosen over the review's own suggested 0x0088, which on
    inspection is 0x0080 | 0x0008, two RESERVED bits combined, not a reserved bit combined with a
    defined one; it would not have exercised the case this test is actually for.

    Closes a hole neither existing test can:
    test_program_verify_refuses_each_reserved_verification_type_bit_... sends each reserved bit
    ALONE, so a handler that checked verification_type against each reserved constant with `==`
    (equality against a single value, mirroring the exact defect
    test_program_clear_unrecognised_mode_is_refused_err_out_of_range_without_calling_the_integrator
    in pgm_clear_test.py documents for PROGRAM_CLEAR's own mode byte) would still pass every one of
    those five cases -- 0x0081 matches none of them by equality -- while wrongly admitting a
    reserved bit that happens to arrive alongside a legal one. The bitmask check
    (verification_type & 0x00F8u) catches this by construction; this test is what actually confirms
    it does, on the wire."""
    handle = pgm_verify_handle()

    frame = send(handle, (0xC8, 0x00) + tuple(u16_to_array(0x0081, 'LITTLE_ENDIAN')) +
                          tuple(u32_to_array(0x00000000, 'LITTLE_ENDIAN')))

    assert frame[0:2] == (0xFE, 0x22), \
        'ERR_OUT_OF_RANGE, even though 0x0001 (calibration areas) alone would be legal'
    assert handle.xcp_program_verify.call_count == 0, \
        'a reserved bit combined with a defined one must still never reach the integrator'


def test_program_verify_answers_err_verify_on_a_failing_callback():
    """Brief test 3. Design doc DD91: 'ERR_VERIFY, also in the row, is answered when the
    integrator reports failure' -- the polled contract's ordinary E_OK-with-non-zero-statusCode
    shape, copied from Xcp_ProgramClear/Xcp_ProgramWrite. verification_type is 0x0002 (code areas,
    non-reserved) so this exchange reaches the integrator rather than being refused by test 2's own
    check above."""
    handle = pgm_verify_handle()

    def verification_failed(_mode, _verification_type, _value, p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_program_verify.side_effect = verification_failed

    frame = send(handle, (0xC8, 0x00, 0x02, 0x00) + tuple(u32_to_array(0x00000000, 'LITTLE_ENDIAN')))

    assert frame[0:2] == (0xFE, 0x32), 'ERR_VERIFY'


def test_program_verify_defers_through_the_pending_slot_and_keeps_passing_mode_type_and_value():
    """Brief test 4, mirroring test/pgm_acceptance_test.py's own busy-then-complete pumping for
    PROGRAM_CLEAR's erase (two busy calls, EV_CMD_PENDING asserted on the second, completing only
    on the third) and pgm_clear_test.py's own
    test_program_clear_defers_through_the_pending_slot_and_keeps_passing_the_clear_range: mode,
    verification_type and verification_value are asserted again on the COMPLETING poll, not only on
    the first (in-handler) call, because Xcp_ProgramVerify's own contract takes all three on EVERY
    call (design doc DD91, copying Xcp_ProgramClear's identical per-call shape) and
    Xcp_PgmPollPendingCommand (source/Xcp_Pgm.c) has no way back to the original request once the
    handler that parsed it has returned -- the three fields have to survive in
    Xcp_Internal.pending_command.args' own union across poll cycles (source/Xcp_Internal.h, this
    task's new member). A handler that never persisted them, or aliased them onto
    program_clear_range's own storage in a union keyed wrong, would still pass every test above
    (none needs more than the first call) and fail only here.

    No session or MTA setup first, unlike PROGRAM_CLEAR's own equivalent test: PROGRAM_VERIFY
    carries no pgm_state gate and touches no address (module docstring above) -- pgm_verify_handle()
    alone is a sufficient starting point.

    Mutation: reading the wrong union member (or none) on the completing poll leaves frame[0] ==
    0xFF unchanged -- the response itself does not distinguish it -- but fails state['last']."""
    handle = pgm_verify_handle()

    state = dict(calls=0)

    def busy_then_complete(mode, verification_type, value, p_status_code):
        # call 1: the fast path inside the handler itself (the RxIndication below); call 2: the
        # first Xcp_MainFunction poll; only call 3, the second poll, completes -- mirrors
        # pgm_clear_test.py's own identically-shaped busy_then_complete.
        state['calls'] += 1
        state['last'] = (mode, verification_type, value)
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_verify.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xC8, 0x11, 0x02, 0x00) +
                                        tuple(u32_to_array(0x76543210, 'LITTLE_ENDIAN'))))
    # call 1, in the handler: busy, defers. Xcp_CanIfRxIndication itself never transmits, so there
    # is nothing to assert about the wire yet (pgm_deferred_test.py's own fix round 1 documents why
    # asserting "nothing transmitted" at exactly this point would be vacuous: true regardless of
    # handler correctness).

    handle.lib.Xcp_MainFunction()  # call 2: still busy
    assert transmitted(handle)[0:2] == (0xFD, 0x05), \
        'still busy on the second poll: only EV_CMD_PENDING (DD54) may go out'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # call 3: the integrator finally reports E_OK

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM_VERIFY response arrives'
    assert state['last'] == (0x11, 0x0002, 0x76543210), \
        "mode, type and value must still be the request's own values on the completing poll"


def test_program_verify_answers_err_cmd_unknown_when_its_own_api_key_is_disabled():
    """Brief test 5. Mirrors pgm_configuration_test.py's own
    test_the_three_pgm_advertised_commands_answer_err_cmd_unknown_when_their_own_keys_are_disabled:
    with xcp_program_verify_api_enable False, ctoInfo[0xC8]'s own enable bit is 0
    (script/source_cfg.c.jinja2), so Xcp_CanIfRxIndication refuses the command before
    Xcp_PIDTable is ever consulted -- the same wire answer a genuinely unimplemented command gets,
    and call_count == 0 confirms dispatch never reaches the (real, existing) handler at all."""
    handle = pgm_verify_handle(xcp_program_verify_api_enable=False)

    frame = send(handle, (0xC8, 0x00, 0x02, 0x00) + tuple(u32_to_array(0x00000000, 'LITTLE_ENDIAN')))

    assert frame[0:2] == (0xFE, 0x20), 'ERR_CMD_UNKNOWN'
    assert handle.xcp_program_verify.call_count == 0, 'a disabled command must never reach the integrator'

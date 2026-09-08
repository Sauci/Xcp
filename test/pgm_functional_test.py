#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP4c Task 5: functional access mode for PROGRAM_CLEAR (0xD1, mode=0x01) -- clearing flash by AREA
rather than by address (design doc docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md, DD84,
DD93).

1.6.5.1.2 (both revisions) gives PROGRAM_CLEAR's mode byte two different readings of the same two
request fields: absolute mode (0x00, default, already shipped by SP4b) has the MTA point at a memory
sector and clear_range is a length; functional mode (0x01, this task) has "the MTA has no influence
on the clearing functionality" at all, and clear_range becomes a bit mask of memory areas instead --
0x00000001 all calibration data areas, 0x00000002 all code areas (the boot area is not covered),
0x00000004 NVRAM areas, 0x00000008..0x00000080 reserved, 0x00000100..0xFFFFFF00 user defined.
Xcp_ProgramClear and Xcp_ProgramClearFunctional are therefore two separate callbacks (DD84), not one
callback taking an extra mode parameter: the latter has no address parameter to pass at all, so
handing an address to a callback whose own request carries none is unrepresentable rather than merely
discouraged.

DD93: this mode byte is independent of PROGRAM_FORMAT's own access method
(Xcp_Internal.pgm_format.access_method, SP4c Task 3) -- 1.6.5.2.4 states outright that "it is
possible to use different access modes for clearing and programming". Xcp_DTOCmdPgmProgramClear
therefore reads this request's own mode byte directly and never consults pgm_format at all -- a
master may clear functionally and program absolutely, or the reverse. DD93 does NOT decouple this
mode byte from PGM_PROPERTIES' own advertisement, and this file's own fixture takes care not to
read it that way -- see xcp_program_clear_functional_api_enable's own default below.

**xcp_program_clear_functional_api_enable defaults False, unlike every sibling
xcp_program_*_api_enable flag (all True).** Corrected after this task's own first full-suite run:
defaulting it True (matching sibling flags) made every existing configuration, including this
file's own base fixture, silently accept mode 0x01 while GET_PGM_PROCESSOR_INFO's own PGM_PROPERTIES
byte still advertised ABSOLUTE_MODE only (DD92's FUNCTIONAL_MODE bit stays 0 until Task 6 -- it
requires BOTH this task's own callback and Task 6's Xcp_ProgramWriteFunctional, one combined
capability, not two independent ones). test/pgm_processor_info_test.py's own
test_get_pgm_processor_info_advertised_absolute_only_mode_matches_program_clear_refusing_functional_
mode caught exactly that: a slave implementing a mode it does not advertise is D10's own defect
class, inverted. Every test below that needs the functional path working passes
xcp_program_clear_functional_api_enable=True explicitly (pgm_clear_functional_handle's own default
kwarg, below) rather than relying on a module-wide default that would silently change what every
OTHER test file's own default configuration advertises.

SP4b already implemented this mode byte and refused everything but 0x00 -- deliberately, with
test/pgm_clear_test.py's own test_program_clear_unrecognised_mode_is_refused_err_out_of_range_
without_calling_the_integrator pinning it across 0x01, 0x02, 0x80 and 0xFF together. This task makes
0x01 valid (when configured), which is why that test is narrowed to (0x02, 0x80, 0xFF) rather than
deleted -- see its own updated docstring for the "other modes still refused" half this task must not
disturb.
test_program_clear_functional_mode_is_refused_err_out_of_range_without_calling_the_integrator, the
companion test that existed only to name 0x01 specifically (DD67's own reasoning, now superseded by
DD93), is removed rather than narrowed: its one case's premise -- that this slave can never offer
functional access -- is exactly what this task makes false, and its only surviving narrower claim
("refused when this build does not configure it") is test 4 below, in full, so nothing is lost."""

import pytest

from .parameter import u32_to_array
from .pgm_clear_test import pgm_clear_handle, program_clear
from .pgm_deferred_test import program_start, transmitted
from .pgm_session_test import send


def pgm_clear_functional_handle(**kwargs):
    """A connected slave with the flash-programming gate on, PROGRAM_CLEAR enabled, and -- unlike
    every sibling xcp_program_*_api_enable flag -- xcp_program_clear_functional_api_enable turned ON
    explicitly rather than inherited from test/parameter.py's own DefaultConfig default, which is
    False (see this module's own docstring: PGM_PROPERTIES' FUNCTIONAL_MODE bit is one combined
    capability this task alone cannot honestly advertise, so the default must not silently grant
    it). setdefault(), not a positional/literal kwarg the way pgm_clear_handle() itself forces
    xcp_program_clear_api_enable=True: a literal would collide (TypeError: got multiple values for
    keyword argument) the moment a caller -- test 4 below -- passes
    xcp_program_clear_functional_api_enable=False of its own to get the negative case;
    setdefault() lets that override through untouched while still defaulting every other caller in
    this file to the positive, functional-capable configuration its own tests need."""
    kwargs.setdefault('xcp_program_clear_functional_api_enable', True)
    return pgm_clear_handle(**kwargs)


def _active_session_with_mta(handle, address=0x12345678):
    """Opens a programming session and points the MTA at `address`, confirming both responses so the
    one-frame transmit pipeline (SWS_Xcp_00859) is free before the request under test. This file's
    own copy of pgm_clear_test.py's and pgm_format_test.py's identically-named, identically-shaped
    helper, following the same one-helper-per-file convention rather than importing a
    leading-underscore name from a sibling module.

    The MTA set here is deliberately never read by a functional PROGRAM_CLEAR --
    Xcp_ProgramClearFunctional's own signature (interface/Xcp.h) carries no address parameter at
    all, DD84's own "the wrong thing becomes unrepresentable" -- so this only exercises the
    session-open half of what this helper does; a real master would ordinarily still have pointed
    the MTA somewhere before PROGRAM_START in any actual sequence."""
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


def test_program_clear_functional_reaches_the_integrator_and_never_calls_the_absolute_callback():
    """Brief test 1. mode=0x01, clear_range=0x02 (the request's own area bitmask -- "all code
    areas", 1.6.5.1.2) must reach Xcp_ProgramClearFunctional with that exact value, and -- the half
    that actually distinguishes a real functional implementation from one that silently fell back to
    the absolute path -- Xcp_ProgramClear must never be called. A test asserting only the first half
    would still pass against a handler that ignored the mode byte, read clear_range as a length, and
    called Xcp_ProgramClear(MTA, 0x02, ...) instead: this suite's own default mock answers E_OK
    regardless of which callback receives the call, so only the call_count assertion below actually
    catches that ordering bug.

    Mutation (Step 5, measured below): making the 0x01 branch fall through to the absolute path
    makes this test fail specifically on the call_count assertion (Xcp_ProgramClear reached instead
    of Xcp_ProgramClearFunctional)."""
    handle = pgm_clear_functional_handle()
    _active_session_with_mta(handle)

    frame = send(handle, (0xD1, 0x01, 0x00, 0x00) + tuple(u32_to_array(0x00000002, 'LITTLE_ENDIAN')))

    assert frame[0] == 0xFF, 'the request must succeed'
    # Checked before unpacking xcp_program_clear_functional's own call_args below, deliberately:
    # a handler that silently fell back to the absolute path leaves call_args as None (never
    # called), which would otherwise fail this test on an unrelated TypeError instead of on this
    # assertion -- the one that actually names the defect (Step 5's own mutation, measured below).
    assert handle.xcp_program_clear.call_count == 0, \
        'a functional request must never reach the absolute-mode callback'
    clear_range, _p_status_code = handle.xcp_program_clear_functional.call_args[0]
    assert clear_range == 0x00000002, "the request's own area bitmask, forwarded exactly"


@pytest.mark.parametrize('reserved_bit', (0x00000008, 0x00000010, 0x00000020, 0x00000040, 0x00000080))
def test_program_clear_functional_refuses_each_reserved_area_bit_without_calling_the_integrator(reserved_bit):
    """Brief test 2. 1.6.5.1.2 (both revisions) reserves 0x00000008..0x00000080 of the area bitmask
    -- five individual bits, not one combined range -- so this is parametrised over each bit on its
    own rather than over one ORed value (0x000000F8): a handler checking only `== 0x00000008`
    explicitly, or masking with the wrong constant, could still refuse a combined 0x000000F8 (some
    bit in it always matches) while silently admitting several of the individual bits this
    parametrisation catches one at a time. Mirrors pgm_verify_test.py's own identically-shaped
    reserved-bit test for PROGRAM_VERIFY's own verificationType.

    call_count == 0 is the assertion that actually matters, not merely the wire response: a handler
    that called Xcp_ProgramClearFunctional first and refused afterwards would still answer (0xFE,
    0x22) here.

    Mutation (Step 5, measured below): inverting the reserved-bit check makes every one of these
    five cases reach the integrator and answer (0xFF,) instead, with call_count == 1, not 0."""
    handle = pgm_clear_functional_handle()
    _active_session_with_mta(handle)

    frame = send(handle, (0xD1, 0x01, 0x00, 0x00) + tuple(u32_to_array(reserved_bit, 'LITTLE_ENDIAN')))

    assert frame[0:2] == (0xFE, 0x22), \
        'ERR_OUT_OF_RANGE for a reserved area bit (0x%08X)' % reserved_bit
    assert handle.xcp_program_clear_functional.call_count == 0, \
        'a reserved area bit must never reach the integrator'


@pytest.mark.parametrize('clear_range', (0x00000004, 0x00000100))
def test_program_clear_functional_accepts_and_forwards_the_values_immediately_outside_the_reserved_span(clear_range):
    """Brief test 3, plus the boundary check the controller's own resolution asks for by name:
    SP4c's plan Task 1 (test/pgm_verify_test.py) shipped a correct reserved-bit mask that no test
    distinguished from an off-by-one neighbour, because every positive-path test used the same
    interior value and the reserved-bit test above only exercises the reserved span itself
    (0x08..0x80) -- nothing there would fail against a mask of 0x000000FC (swallowing 0x04) or
    0x000001F8 (swallowing 0x0100) instead of the correct 0x000000F8. 0x00000004 is "NVRAM areas",
    the highest DEFINED bit (1.6.5.1.2), immediately below the reserved span's own 0x00000008 floor;
    0x00000100 is the lowest USER DEFINED bit, immediately above the reserved span's own 0x00000080
    ceiling -- the brief's own test 3 example. Neither is reserved, so both must reach the
    integrator with the exact value intact, not merely "not refused", which a wire-only assertion
    could satisfy by accident if the module answered positively without ever calling
    Xcp_ProgramClearFunctional at all.

    Mutation (measured below, not one of Step 5's own two named mutations but the same class of
    off-by-one risk this plan has already shipped once): masking with 0x000000FCu (0x000000F8u |
    0x00000004u) makes the 0x00000004 case fail; masking with 0x000001F8u (0x000000F8u |
    0x00000100u) makes the 0x00000100 case fail the identical way; each mutation leaves the OTHER
    case unaffected, confirming each boundary needs its own case, not one shared value that fails to
    catch a defect in the other direction."""
    handle = pgm_clear_functional_handle()
    _active_session_with_mta(handle)

    frame = send(handle, (0xD1, 0x01, 0x00, 0x00) + tuple(u32_to_array(clear_range, 'LITTLE_ENDIAN')))

    assert frame[0] == 0xFF, \
        'a value immediately outside the reserved span (0x%08X) must reach the integrator and ' \
        'succeed, not be refused as if it were reserved' % clear_range
    forwarded_clear_range, _p_status_code = handle.xcp_program_clear_functional.call_args[0]
    assert forwarded_clear_range == clear_range, \
        'the exact boundary value must reach the integrator, not a neighbouring one'
    assert handle.xcp_program_clear.call_count == 0, \
        'a functional request must never reach the absolute-mode callback'


def test_program_clear_functional_is_refused_when_not_configured():
    """Brief test 4. xcp_program_clear_functional_api_enable=False -- an integrator's build that has
    not implemented Xcp_ProgramClearFunctional -- must refuse mode=0x01 the same way an unrecognised
    reserved bit is refused: (0xFE, 0x22) ERR_OUT_OF_RANGE, integrator never reached. clear_range is
    0x00000002 here, the same defined, non-reserved value test 1 above uses, deliberately: it
    isolates this refusal from the reserved-bit refusal above -- a request combining a reserved bit
    with an unconfigured build would still answer (0xFE, 0x22) either way and would not tell the two
    checks apart.

    Mutation: deleting this capability check (or inverting it) makes this test fail -- the request
    is answered 0xFF and Xcp_ProgramClearFunctional is called once, instead of being refused with
    call_count == 0."""
    handle = pgm_clear_functional_handle(xcp_program_clear_functional_api_enable=False)
    _active_session_with_mta(handle)

    frame = send(handle, (0xD1, 0x01, 0x00, 0x00) + tuple(u32_to_array(0x00000002, 'LITTLE_ENDIAN')))

    assert frame[0:2] == (0xFE, 0x22), 'ERR_OUT_OF_RANGE: functional clear is not configured'
    assert handle.xcp_program_clear_functional.call_count == 0, \
        'an unconfigured functional callback must never be reached'


def test_program_clear_functional_defers_through_the_pending_slot_and_keeps_passing_the_clear_range():
    """Not one of the brief's own five items -- added because Xcp_PgmPollPendingCommand's
    XCP_PID_CMD_PROGRAM_CLEAR case now branches on Xcp_Internal.pending_command.program_clear_
    functional to choose which callback to re-invoke on a later poll, and every test above completes
    on the very first, synchronous call (this suite's own default mock returns E_OK immediately) --
    none of them ever reaches that branch. A bug there (the flag read backwards, or the continuation
    hard-coded to call Xcp_ProgramClear regardless of which mode deferred) would ship with all five
    of the brief's own tests green. Mirrors pgm_clear_test.py's own
    test_program_clear_defers_through_the_pending_slot_and_keeps_passing_the_clear_range exactly,
    adapted to the functional callback's own two-argument signature (no address).

    Mutation: hard-coding Xcp_PgmPollPendingCommand's PROGRAM_CLEAR case to always call
    Xcp_ProgramClear, regardless of program_clear_functional, makes this test fail on the
    call_args_list unpack below (Xcp_ProgramClear does not share Xcp_ProgramClearFunctional's own
    two-argument shape, so a poll that reached the wrong mock would either raise or leave
    xcp_program_clear_functional.call_args_list empty)."""
    handle = pgm_clear_functional_handle()
    _active_session_with_mta(handle)

    state = dict(calls=0)

    def busy_then_complete(_clear_range, p_status_code):
        # call 1: the fast path inside the handler itself (program_clear below); call 2: the first
        # Xcp_MainFunction poll; only call 3, the second poll, completes -- mirrors
        # pgm_clear_test.py's own test_program_clear_defers_through_the_pending_slot_and_keeps_
        # passing_the_clear_range.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_clear_functional.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program_clear(handle, mode=0x01, clear_range=0x00000002)

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFD, 'still busy on the second poll: only EV_CMD_PENDING (DD54)'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the deferred functional PROGRAM_CLEAR response arrives'

    clear_range, _p_status_code = handle.xcp_program_clear_functional.call_args_list[-1][0]
    assert clear_range == 0x00000002, \
        "the area bitmask must still be the request's own value on the completing poll"
    assert handle.xcp_program_clear.call_count == 0, \
        'the absolute-mode callback must never be reached for a functional-mode request'

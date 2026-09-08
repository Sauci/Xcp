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
("refused when this build does not configure it") is test 4 below, in full, so nothing is lost.

**SP4c Task 6 extends this file with the other half of functional access: PROGRAM itself
(Xcp_ProgramWriteFunctional), the Block Sequence Counter it carries (DD86), and the advertisement
that finally becomes true (DD92).** Everything above this paragraph is Task 5's and is unchanged in
substance; the two additions Task 6 makes to it are named where they occur
(pgm_clear_functional_handle's second setdefault, and test 4's second False).

What Task 6 adds below, in order: PROGRAM_FORMAT's own functional-access ACCEPTANCE half, which
Task 3 could implement but not test (its module docstring says so, and predicted -- correctly, as
this file now demonstrates -- that no change to Xcp_DTOCmdPgmProgramFormat would be needed once
FUNCTIONAL_MODE could be advertised at all); PROGRAM reaching Xcp_ProgramWriteFunctional instead of
Xcp_ProgramWrite; DD86's Block Sequence Counter, each of its three specified behaviours pinned by
its own test; DD92's advertisement in both directions, plus the generation guard that keeps the two
halves of the one capability from being configured separately; and two end-to-end runs -- one purely
functional, one deliberately MIXED (functional clear, absolute programming), which 1.6.5.2.4 permits
outright ("it is possible to use different access modes for clearing and programming", DD93) and
which nothing else in this suite would catch being wrongly coupled."""

import pytest

from jinja2.exceptions import UndefinedError

from .parameter import u32_to_array
from .pgm_clear_test import pgm_clear_handle, program_clear
from .pgm_deferred_test import program_start, program_reset, transmitted
from .pgm_program_test import pgm_program_handle, program, program_max, program_next
from .pgm_processor_info_test import get_pgm_processor_info
from .pgm_session_test import send
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok


#: XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM (source/Xcp_Internal.h: 0x01u << 4), spelled the same
#: way pgm_protected_acceptance_test.py and pgm_acceptance_test.py already spell it.
PGM_RESOURCE = 0x10

#: XCP_PGM_PROPERTIES_ABSOLUTE_MODE | XCP_PGM_PROPERTIES_FUNCTIONAL_MODE (source/Xcp_Internal.h,
#: bits 0 and 1 of GET_PGM_PROCESSOR_INFO's own PGM_PROPERTIES byte, 1.1/1.6.5.2.1).
ABSOLUTE_MODE = 0x01
FUNCTIONAL_MODE = 0x02


def pgm_clear_functional_handle(**kwargs):
    """A connected slave with the flash-programming gate on, PROGRAM_CLEAR enabled, and -- unlike
    every sibling xcp_program_*_api_enable flag -- both functional flags turned ON explicitly rather
    than inherited from test/parameter.py's own DefaultConfig defaults, which are False (see this
    module's own docstring: PGM_PROPERTIES' FUNCTIONAL_MODE bit is one combined capability, so
    neither flag alone may grant it). setdefault(), not positional/literal kwargs the way
    pgm_clear_handle() itself forces xcp_program_clear_api_enable=True: a literal would collide
    (TypeError: got multiple values for keyword argument) the moment a caller -- test 4 below --
    passes either flag of its own to get the negative case; setdefault() lets that override through
    untouched while still defaulting every other caller in this file to the positive,
    functional-capable configuration its own tests need.

    xcp_program_write_functional_api_enable joins the setdefault list in Task 6, and not merely for
    symmetry: script/source_cfg.c.jinja2 now REFUSES to generate a configuration that enables one
    functional flag without the other (DD92 -- see
    test_generation_refuses_functional_mode_configured_by_halves below), so a handle enabling the
    clear half alone would no longer build at all."""
    kwargs.setdefault('xcp_program_clear_functional_api_enable', True)
    kwargs.setdefault('xcp_program_write_functional_api_enable', True)
    return pgm_clear_handle(**kwargs)


def pgm_functional_handle(**kwargs):
    """Task 6's own base fixture: pgm_program_test.py's pgm_program_handle() -- PROGRAM_CLEAR,
    PROGRAM and PROGRAM_MAX all enabled -- with both functional flags on.

    pgm_clear_functional_handle() above cannot serve Task 6's tests: it forwards to
    pgm_clear_handle(), which forces xcp_program_api_enable=False and xcp_program_max_api_enable=
    False as literal kwargs (its own docstring explains why), and every test below needs a real
    PROGRAM to reach Xcp_ProgramWriteFunctional with."""
    kwargs.setdefault('xcp_program_clear_functional_api_enable', True)
    kwargs.setdefault('xcp_program_write_functional_api_enable', True)
    return pgm_program_handle(**kwargs)


def program_format(handle, compression=0x00, encryption=0x00, programming_method=0x00, access=0x00):
    """PROGRAM_FORMAT (0xCB, Task 3), sent and answered in one exchange -- the command is
    synchronous by contract (DD91), so unlike program()/program_clear() there is no deferral for a
    caller to pump at its own pace and send()'s single Xcp_MainFunction is always enough. Mirrors
    pgm_format_test.py's own request layout (1.1/1.6.5.2.4: compression, encryption, programming
    method, access method at bytes 1..4)."""
    return send(handle, (0xCB, compression, encryption, programming_method, access))


def _functional_session(handle, address=0x12345678):
    """An ACTIVE programming session that has been told, by an accepted PROGRAM_FORMAT, that the
    data to follow uses FUNCTIONAL access mode (access method 0x01, 1.1/1.6.5.2.4).

    PROGRAM_FORMAT is sent AFTER _active_session_with_mta's own SET_MTA, deliberately and not
    incidentally: SET_MTA resets pgm_format back to its all-absolute defaults (DD85,
    pgm_format_test.py's own test_set_mta_resets_the_program_format_state_to_defaults), so a helper
    that formatted first and set the MTA afterwards would hand every test below an ABSOLUTE session
    while claiming otherwise -- and, since the absolute callback answers E_OK just as readily, the
    tests would fail on their call_count assertions with no hint of the real cause.

    The MTA is set at all only because _active_session_with_mta is this file's own shared
    session-opening helper; nothing on the functional path ever reads it (1.6.5.1.3: "the ECU
    software knows the start address for the new flash content automatically"), which is exactly
    what test_a_functional_write_never_moves_the_mta below pins."""
    _active_session_with_mta(handle, address=address)

    frame = program_format(handle, access=0x01)
    assert frame[0] == 0xFF, 'setup: PROGRAM_FORMAT(access=0x01) must be accepted'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def _write_functional_call(handle, index=-1):
    """The (blockSequenceCounter, pData, length) triple of one Xcp_ProgramWriteFunctional call,
    `index` counted over call_args_list (default: the most recent). Unpacks the four-argument
    signature in one place so no test below repeats it, and reads pData eagerly into a bytes
    object: the pointer is only guaranteed valid for the duration of the call (interface/Xcp.h),
    though in practice it points into Xcp_Internal.pgm_block, which outlives it."""
    counter, p_data, length, _p_status_code = handle.xcp_program_write_functional.call_args_list[index][0]
    return counter, bytes(p_data[0:length]), length


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
    call_count == 0.

    BOTH functional flags are passed False since Task 6, not only the clear half this test is about:
    DD92's generation guard refuses a configuration that offers one without the other
    (test_generation_refuses_functional_mode_configured_by_halves below), so this build has to turn
    functional access off as the one combined capability it is. That does not weaken the test -- what
    it pins is a build whose integrator did not implement Xcp_ProgramClearFunctional, which is
    exactly what this configuration now describes."""
    handle = pgm_clear_functional_handle(xcp_program_clear_functional_api_enable=False,
                                         xcp_program_write_functional_api_enable=False)
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


# ------------------------------------------------------------------------------------------------
# SP4c Task 6: functional access mode for PROGRAM, the Block Sequence Counter, and the DD92
# advertisement. Everything above is Task 5's (PROGRAM_CLEAR, mode 0x01).
# ------------------------------------------------------------------------------------------------


def test_program_format_functional_access_is_accepted_and_forwarded_once_it_is_advertised():
    """The half Task 3 implemented but could not test, closed here rather than left standing.

    pgm_format_test.py's own test_program_format_refuses_functional_access_when_not_advertised pins
    the REFUSAL half of DD89's fourth term; its module docstring records that the acceptance half was
    unreachable in Task 3 (no configuration could set PGM_PROPERTIES' FUNCTIONAL_MODE bit yet) and
    predicts that Task 6 would activate it "by adding one more generation term to that shared byte --
    no further change to Xcp_DTOCmdPgmProgramFormat itself". This test is what makes that prediction
    falsifiable: the identical request (0xCB, 0x00, 0x00, 0x00, 0x01) that is refused there is
    accepted here, on a build that advertises FUNCTIONAL_MODE, with the access byte forwarded to the
    integrator intact.

    'Not refused' would be too weak, exactly as it is for pgm_format_test.py's own accepted halves:
    call_args is unpacked, so a handler answering positively without ever calling Xcp_ProgramFormat
    would raise on the unpack rather than pass quietly.

    Mutation: forcing the FUNCTIONAL_MODE term out of pgmProperties' generation
    (script/source_cfg.c.jinja2) makes this test fail with (0xFE, 0x22) -- and the refusal test in
    pgm_format_test.py keeps passing, which is the pair this task's own advertise/accept invariant
    rests on."""
    handle = pgm_functional_handle()
    _active_session_with_mta(handle)

    frame = program_format(handle, access=0x01)

    assert frame[0] == 0xFF, \
        'functional access must be accepted once PGM_PROPERTIES advertises FUNCTIONAL_MODE'
    _compression, _encryption, _programming_method, access, _p_status = \
        handle.xcp_program_format.call_args[0]
    assert access == 0x01, "the request's own access method must reach the integrator intact"


def test_program_reaches_the_functional_write_callback_with_the_payload_and_never_the_absolute_one():
    """Brief test 1. Under an accepted PROGRAM_FORMAT(access=0x01), a PROGRAM must reach
    Xcp_ProgramWriteFunctional with the payload it carried -- and Xcp_ProgramWrite must never be
    called at all.

    The negative half is what distinguishes a working implementation from one that silently fell
    back: this suite's default mocks answer E_OK from either callback, so a handler that ignored
    pgm_format.access_method entirely and called Xcp_ProgramWrite(MTA, ...) would still answer 0xFF
    here and still pass every wire-level assertion. Only the call_count assertion catches it.

    Mutation (Step 5, measured in the task report): making the functional branch call
    Xcp_ProgramWrite makes this test fail on the call_count assertion below, naming the defect
    directly."""
    handle = pgm_functional_handle()
    _functional_session(handle)

    frame = send(handle, (0xD0, 0x02, 0xAA, 0xBB))

    assert frame[0] == 0xFF, 'a functional PROGRAM must succeed'
    assert handle.xcp_program_write.call_count == 0, \
        'a functional PROGRAM must never reach the absolute-mode write callback'
    assert handle.xcp_program_write_functional.call_count == 1, \
        'it must reach the functional write callback exactly once'
    _counter, data, length = _write_functional_call(handle)
    assert (length, data) == (0x02, bytes((0xAA, 0xBB))), \
        "the request's own payload must reach the integrator exactly as transmitted"


def test_the_first_program_after_program_format_carries_block_sequence_counter_one():
    """DD86's first specified behaviour, on its own. 1.6.5.1.3 (both revisions): "The Block Sequence
    Counter of the server shall be initialized to one (1) when receiving a PROGRAM_FORMAT request
    message. This means that the first PROGRAM request message following the PROGRAM_FORMAT request
    message starts with a Block Sequence Counter of one (1)."

    Deliberately separate from the increment test below, which the design doc's own test strategy
    and this task's brief both insist on: a test asserting only this one would pass against a counter
    that never increments at all, and a test asserting only the increment would pass against one
    that started at 7.

    Mutation: initialising the counter to anything but the value that makes the first request read 1
    (Xcp_DTOCmdPgmProgramFormat, source/Xcp_Pgm.c) fails here and nowhere else."""
    handle = pgm_functional_handle()
    _functional_session(handle)

    send(handle, (0xD0, 0x02, 0xAA, 0xBB))

    counter, _data, _length = _write_functional_call(handle)
    assert counter == 1, 'the first data transfer after PROGRAM_FORMAT carries counter 1'


def test_each_data_transfer_request_increments_the_block_sequence_counter():
    """DD86's second specified behaviour, on its own: "Its value is incremented by 1 for each
    subsequent data transfer request" (1.6.5.1.3). Three transfers in one formatted session must
    carry 1, 2 and 3 -- the whole sequence asserted, not merely the last, so a counter that jumped
    or repeated is caught at the exact transfer where it did.

    The middle transfer is a PROGRAM_MAX, not a third PROGRAM: DD86 names PROGRAM, PROGRAM_NEXT and
    PROGRAM_MAX together as the data transfer requests that count, and a counter advanced only from
    PROGRAM's own handler would pass a test that sent nothing else. PROGRAM_MAX carries a fixed
    MAX_CTO-1 (7 at this suite's default) bytes with no element count of its own (1.6.5.2.6).

    Mutation (Step 5, measured in the task report): freezing the counter -- deleting the increment --
    leaves every call reading 1, failing this test's second assertion while
    test_the_first_program_after_program_format_carries_block_sequence_counter_one above still
    passes."""
    handle = pgm_functional_handle()
    _functional_session(handle)

    assert send(handle, (0xD0, 0x02, 0xAA, 0xBB))[0] == 0xFF, 'first transfer: PROGRAM'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program_max(handle, data=tuple(range(0x10, 0x17)))
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'second transfer: PROGRAM_MAX'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD0, 0x02, 0xCC, 0xDD))[0] == 0xFF, 'third transfer: PROGRAM again'

    counters = [call[0][0] for call in handle.xcp_program_write_functional.call_args_list]
    assert counters == [1, 2, 3], \
        'each data transfer request advances the counter by exactly one: %r' % (counters,)
    assert handle.xcp_program_write.call_count == 0, \
        'PROGRAM_MAX must take the functional path too, not only PROGRAM'


def test_a_fresh_program_format_reinitialises_the_block_sequence_counter():
    """DD86's third reset point, and the one 1.6.5.1.3 states outright: a PROGRAM_FORMAT
    re-initialises the counter, so the first transfer after it reads 1 again rather than continuing
    from where the previous stream left off.

    Two transfers precede it, not one, deliberately: after a single transfer the counter would read
    1 either way -- whether it was re-initialised or merely never advanced -- and this test would
    prove nothing. After two, a counter that was NOT reset reads 3 here.

    Mutation: deleting the counter's initialisation from Xcp_DTOCmdPgmProgramFormat leaves this
    third transfer reading 3."""
    handle = pgm_functional_handle()
    _functional_session(handle)

    assert send(handle, (0xD0, 0x02, 0xAA, 0xBB))[0] == 0xFF, 'first transfer of the first stream'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert send(handle, (0xD0, 0x02, 0xCC, 0xDD))[0] == 0xFF, 'second transfer of the first stream'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert [call[0][0] for call in handle.xcp_program_write_functional.call_args_list] == [1, 2], \
        'setup: the first stream must have counted 1 then 2 before the re-format below'

    frame = program_format(handle, access=0x01)
    assert frame[0] == 0xFF, 'a second PROGRAM_FORMAT is accepted mid-session'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD0, 0x02, 0xEE, 0xFF))[0] == 0xFF, 'first transfer of the second stream'

    counter, _data, _length = _write_functional_call(handle)
    assert counter == 1, \
        'a fresh PROGRAM_FORMAT restarts the count at 1, it does not continue the previous stream'


def test_a_refused_program_format_leaves_the_block_sequence_counter_untouched():
    """Not one of the brief's own items: it pins the one judgment call the counter's initialisation
    needed. 1.6.5.1.3 says the counter is initialised "when receiving a PROGRAM_FORMAT request
    message", which taken to the letter would re-base it even for a request this slave then REFUSES.
    This module initialises it on the same acceptance branch that stores the format itself, for the
    reason DD85 already gives for that state: a refused PROGRAM_FORMAT leaves pgm_format exactly as
    it was, and a master told ERR_OUT_OF_RANGE has no reason to restart its own count either -- so
    re-basing the slave's counter alone would create precisely the divergence the counter exists to
    detect.

    The refused request here sets a non-default compression method on a build that does not
    advertise COMPRESSION_SUPPORTED -- DD89's first term, pinned in isolation by
    pgm_format_test.py's own advertise/accept test -- so the refusal is unambiguous and has nothing
    to do with the access method the session is already using.

    Mutation: initialising the counter before the DD89 structural check (or in an unconditional
    prologue) makes the transfer below read 1 instead of 3."""
    handle = pgm_functional_handle()
    _functional_session(handle)

    assert send(handle, (0xD0, 0x02, 0xAA, 0xBB))[0] == 0xFF, 'first transfer'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert send(handle, (0xD0, 0x02, 0xCC, 0xDD))[0] == 0xFF, 'second transfer'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    frame = program_format(handle, compression=0x01, access=0x01)
    assert frame[0:2] == (0xFE, 0x22), \
        'setup: an unadvertised compression method must be refused ERR_OUT_OF_RANGE (DD89)'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD0, 0x02, 0xEE, 0xFF))[0] == 0xFF, 'the stream continues after the refusal'

    counter, _data, _length = _write_functional_call(handle)
    assert counter == 3, \
        'a REFUSED PROGRAM_FORMAT must not re-base the counter: the stream continues at 3'


def test_every_frame_of_a_master_block_counts_as_its_own_data_transfer_request():
    """DD86 names PROGRAM_NEXT among the three commands that advance the counter, so a master block
    mode block of three frames advances it three times even though it produces exactly ONE call to
    the integrator (1.6.5.1.3: "The slave device will acknowledge only the last PROGRAM_NEXT command
    packet", DD63). The completing frame's own counter is therefore 3, not 1.

    Recorded as a deliberate reading rather than an obvious one, because the alternative is
    defensible: 1.6.5.1.3 also says the MTA IS the counter under this mode, and this module advances
    the MTA once per completed BLOCK (DD66), not once per frame. DD86's own table settles it the
    other way -- "each data transfer request (PROGRAM, PROGRAM_NEXT, PROGRAM_MAX): incremented by
    1" -- and so does the rollover sentence immediately after it in the specification, which is
    phrased against the arrival of a request message ("rolls over and starts at 0x00 with the next
    data transfer request message"), not against a write completing. This test is what makes that
    reading visible instead of leaving it implicit in the source.

    14 bytes over three frames at this suite's default MAX_CTO of 8 (6 + 6 + 2), mirroring
    pgm_acceptance_test.py's own multi-frame block exactly."""
    handle = pgm_functional_handle()
    _functional_session(handle)
    payload = tuple(range(0x01, 0x0F))

    handle.can_if_transmit.reset_mock()
    program(handle, 0x0E, data=payload[0:6])
    program_next(handle, 0x08, data=payload[6:12])
    program_next(handle, 0x02, data=payload[12:14])
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the completing PROGRAM_NEXT frame answers'
    assert handle.xcp_program_write_functional.call_count == 1, \
        'once per BLOCK across all three frames, not once per frame'
    counter, data, length = _write_functional_call(handle)
    assert (length, data) == (0x0E, bytes(payload)), \
        'the whole block reaches the functional callback, in order, exactly as absolute mode does'
    assert counter == 3, \
        'all three frames are data transfer requests, so the completing frame carries counter 3'


def test_a_functional_write_defers_through_the_pending_slot_and_keeps_passing_the_same_counter():
    """Not one of the brief's own items, and the same gap Task 5 closed for PROGRAM_CLEAR: every
    test above completes on the callback's first, synchronous call, so none of them ever reaches
    Xcp_PgmPollPendingCommand's own PROGRAM/PROGRAM_MAX/PROGRAM_NEXT case. A poll that re-invoked
    the ABSOLUTE callback, or that re-read a counter already advanced past this transfer's own
    value, would ship with every other test in this file green.

    Both claims are asserted on the completing poll: the same counter as the handler's own first
    call (1, not 2 -- the counter must not advance while one transfer is still being polled), and
    the absolute callback never reached."""
    handle = pgm_functional_handle()
    _functional_session(handle)

    state = dict(calls=0)

    def busy_then_complete(_counter, _p_data, _length, p_status_code):
        # call 1: the fast path inside the handler itself; call 2: the first Xcp_MainFunction poll;
        # only call 3, the second poll, completes -- mirrors pgm_program_test.py's own
        # test_program_defers_through_the_pending_slot_and_keeps_passing_the_same_bytes.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_write_functional.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program(handle, 0x02, data=(0xAA, 0xBB))

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFD, 'still busy on the second call: only EV_CMD_PENDING (DD54)'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'the deferred functional PROGRAM response arrives'

    assert state['calls'] == 3, 'the integrator must genuinely have been polled, not called once'
    counters = [call[0][0] for call in handle.xcp_program_write_functional.call_args_list]
    assert counters == [1, 1, 1], \
        'every poll of ONE transfer must carry that transfer\'s own counter: %r' % (counters,)
    assert handle.xcp_program_write.call_count == 0, \
        'a deferred functional write must never continue through the absolute-mode callback'


def test_a_functional_write_never_moves_the_mta():
    """1.6.5.1.3 puts "The MTA will be post-incremented by the number of data bytes" under *Absolute
    Access mode* alone; under *Functional Access mode* the same paragraph says the ECU knows the
    start address by itself and the MTA works as the Block Sequence Counter instead. So a functional
    write must leave Xcp_Internal.memory_transfer.address exactly where SET_MTA left it -- otherwise
    a master that programmed functionally and then switched to absolute access without re-sending
    SET_MTA would find its own image written one block further on than it asked.

    Observed the only way the harness can observe the MTA: through a following ABSOLUTE write's own
    address argument. The intervening PROGRAM_FORMAT carries all-default fields, which 1.6.5.2.4
    makes equivalent to the command never having been sent (absolute access, unmodified data), and
    -- unlike SET_MTA, the other way back to absolute mode -- it does not itself write the MTA, so
    the address asserted below can only be the one the functional write did or did not move.

    Mutation: advancing the MTA on the functional path as well (sharing DD66's post-increment
    unconditionally) makes the address below read 0x1234567A instead of 0x12345678."""
    handle = pgm_functional_handle()
    _functional_session(handle, address=0x12345678)

    assert send(handle, (0xD0, 0x02, 0xAA, 0xBB))[0] == 0xFF, 'the functional write succeeds'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    frame = program_format(handle)
    assert frame[0] == 0xFF, 'setup: an all-defaults PROGRAM_FORMAT returns the session to absolute'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD0, 0x02, 0xCC, 0xDD))[0] == 0xFF, 'the following absolute write succeeds'

    address, _p_data, _length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x12345678, \
        'the MTA must be exactly where SET_MTA left it: a functional write does not advance it'


@pytest.mark.parametrize('functional_configured', (True, False), ids=('configured', 'not_configured'))
def test_get_pgm_processor_info_advertises_functional_mode_exactly_when_it_is_available(functional_configured):
    """DD92, both directions, on the whole PGM_PROPERTIES byte rather than on bit 1 alone: "The
    FUNCTIONAL_MODE bit is set if and only if DD84's callbacks are configured. Both directions are
    defects: advertising an unimplemented mode is D10's class, and implementing an unadvertised one
    is its inverse -- a master reads PGM_PROPERTIES to decide what to use, so an unadvertised
    capability is an unreachable one."

    Asserted as == ABSOLUTE_MODE | FUNCTIONAL_MODE and == ABSOLUTE_MODE, not as a bit test, for the
    reason pgm_processor_info_test.py's own byte-level test gives: a build that also claimed
    COMPRESSION_SUPPORTED or any other bit it does not implement would pass a bit-1 test and still
    be lying about the rest of the byte.

    The paired behaviour is what the two end-to-end runs below assert, and the advertise/accept
    invariant they hold together is what the generation guard in the next test enforces for every
    configuration the suite can generate.

    Mutation (Step 5, measured in the task report): ORing FUNCTIONAL_MODE in unconditionally makes
    the not_configured case fail, exactly as it should -- and, tellingly, leaves the configured case
    passing."""
    handle = pgm_functional_handle() if functional_configured else pgm_program_handle()

    frame = get_pgm_processor_info(handle)

    expected = ABSOLUTE_MODE | FUNCTIONAL_MODE if functional_configured else ABSOLUTE_MODE
    assert frame[0:2] == (0xFF, expected), \
        'PGM_PROPERTIES must advertise functional mode exactly when this build offers it: %r' % (frame,)


@pytest.mark.parametrize('clear_enabled,write_enabled', ((True, False), (False, True)),
                         ids=('clear_without_write', 'write_without_clear'))
def test_generation_refuses_functional_mode_configured_by_halves(clear_enabled, write_enabled):
    """DD92: "Generation refuses functional mode enabled without the callbacks, matching how this
    module already prevents unbuildable configurations." PGM_PROPERTIES carries ONE FUNCTIONAL_MODE
    bit for both halves, so a build offering one callback without the other cannot be advertised
    honestly in either direction:

    - clear without write: PROGRAM_CLEAR would accept mode 0x01 (its own gate is
      pgmClearFunctionalSupported, independent of PGM_PROPERTIES by DD93) while PGM_PROPERTIES
      advertised no functional mode at all -- the exact defect that made Task 5's own default flip
      to False, caught then by pgm_processor_info_test.py.
    - write without clear: nothing would be advertised and nothing would be accepted, so the flag
      would silently go nowhere -- the shape script/source_cfg.c.jinja2 already refuses for a
      `daq_dynamic` pool under a STATIC configuration, in those same words.

    Refused at generation rather than at runtime for the reason every other guard in that template
    is: a configuration that cannot mean anything should not produce a slave. `raise(...)` is not a
    registered Jinja global anywhere in that file, so this surfaces as jinja2.exceptions.
    UndefinedError with no message to match on -- see pgm_sector_test.py's own generation test for
    the same note.

    Mutation: dropping the guard lets both halves generate; the clear_without_write case then
    produces exactly the advertise/accept mismatch DD92 forbids, and no other test in this suite
    would report it."""
    with pytest.raises(UndefinedError):
        pgm_functional_handle(xcp_program_clear_functional_api_enable=clear_enabled,
                              xcp_program_write_functional_api_enable=write_enabled)


def test_a_pure_functional_programming_sequence_composes_end_to_end():
    """Acceptance run A: CONNECT -> GET_SEED/UNLOCK -> PROGRAM_START -> PROGRAM_FORMAT(access=0x01)
    -> PROGRAM_CLEAR(mode=0x01) -> PROGRAM -> PROGRAM_RESET, every step answering positively, on a
    build where the PGM resource is genuinely protected (so the unlock is real, not decorative --
    pgm_protected_acceptance_test.py's own reasoning, reused here rather than re-argued).

    No SET_MTA anywhere in this sequence, and that is the point rather than an omission: under
    functional access neither the clear (1.6.5.1.2: "the MTA has no influence on the clearing
    functionality") nor the write (1.6.5.1.3: "the ECU software knows the start address for the new
    flash content automatically") reads an address at all. A module that still depended on one would
    program at whatever the MTA happened to hold -- zero here, since nothing ever set it.

    The negative half carries as much weight as the positive one: NEITHER absolute callback may be
    called anywhere in this run. Without it, a module that silently fell back to absolute access for
    both operations would answer 0xFF at every step and pass every other assertion here."""
    handle = pgm_functional_handle(resource_protection_programming=True)

    assert send(handle, (0xD2,))[0:2] == (0xFE, 0x25), \
        'PROGRAM_START must be refused ERR_ACCESS_LOCKED before the PGM resource is unlocked'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    seed = [0x42]
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, seed)

    frame = send(handle, (0xF8, 0x00, PGM_RESOURCE))
    assert frame[0:3] == (0xFF, len(seed), seed[0]), 'GET_SEED must return the PGM seed'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    frame = send(handle, (0xF7, len(seed)) + tuple(seed))
    assert frame[0:2] == (0xFF, 0x00), 'UNLOCK must grant the PGM resource for the whole session'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_START opens the session'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert program_format(handle, access=0x01)[0] == 0xFF, \
        'PROGRAM_FORMAT announces functional access for everything that follows'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # PROGRAM_CLEAR, functional: clear_range is an AREA bitmask here (0x00000002, all code areas),
    # not a length -- and PROGRAM_CLEAR's own mode byte says so, independently of the PROGRAM_FORMAT
    # above (DD93). Run B below is the same sequence with the two decoupled the other way.
    handle.can_if_transmit.reset_mock()
    program_clear(handle, mode=0x01, clear_range=0x00000002)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_CLEAR must erase by area'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD0, 0x04, 0xDE, 0xAD, 0xBE, 0xEF))[0] == 0xFF, \
        'PROGRAM must write through the functional callback'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'PROGRAM_RESET ends the sequence'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert handle.xcp_program_clear_functional.call_count == 1, 'the erase went to the area callback'
    clear_range, _p_status_code = handle.xcp_program_clear_functional.call_args[0]
    assert clear_range == 0x00000002, "the erase carried the request's own area bitmask"

    assert handle.xcp_program_write_functional.call_count == 1, 'the write went to the block callback'
    counter, data, length = _write_functional_call(handle)
    assert (counter, length, data) == (1, 0x04, bytes((0xDE, 0xAD, 0xBE, 0xEF))), \
        'the first transfer of the stream, its payload intact and its counter at 1'

    assert handle.xcp_program_clear.call_count == 0, \
        'no part of a purely functional sequence may reach the absolute-mode clear callback'
    assert handle.xcp_program_write.call_count == 0, \
        'no part of a purely functional sequence may reach the absolute-mode write callback'


def test_a_functional_clear_and_an_absolute_program_compose_in_one_session():
    """Acceptance run B: the MIXED sequence 1.6.5.2.4 permits outright -- "It is possible to use
    different access modes for clearing and programming" (DD93) -- clearing by AREA while
    programming by ADDRESS, in one session.

    Nothing else in this suite would catch the two paths being wrongly coupled. A module that
    derived PROGRAM_CLEAR's mode from pgm_format.access_method, or PROGRAM's callback choice from
    the last clear's mode, passes every test above (where the two agree) and fails only here.

    Both halves are asserted positively, not merely "not refused": Xcp_ProgramClearFunctional
    receives the area bitmask, and Xcp_ProgramWrite receives the MTA this session set -- while their
    opposite numbers (Xcp_ProgramClear and Xcp_ProgramWriteFunctional) are never called at all.

    The session is deliberately left at its all-defaults format: PROGRAM_FORMAT is never sent, which
    1.6.5.2.4 makes equivalent to absolute access with unmodified data, so the functional clear below
    is chosen purely by PROGRAM_CLEAR's own mode byte."""
    handle = pgm_functional_handle()
    _active_session_with_mta(handle, address=0x00080000)

    handle.can_if_transmit.reset_mock()
    program_clear(handle, mode=0x01, clear_range=0x00000001)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'the functional clear succeeds with no PROGRAM_FORMAT'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xD0, 0x02, 0x11, 0x22))[0] == 0xFF, \
        'and an ABSOLUTE program succeeds in the very same session'

    assert handle.xcp_program_clear_functional.call_count == 1, 'the erase went to the area callback'
    clear_range, _p_status_code = handle.xcp_program_clear_functional.call_args[0]
    assert clear_range == 0x00000001, "the erase carried the request's own area bitmask"
    assert handle.xcp_program_clear.call_count == 0, \
        'a functional clear must not also reach the absolute-mode clear callback'

    assert handle.xcp_program_write.call_count == 1, 'the write went to the absolute callback'
    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x00080000, \
        'the absolute write must land at the MTA this session set, unaffected by the functional erase'
    assert (length, bytes(p_data[0:length])) == (0x02, bytes((0x11, 0x22))), \
        "the absolute write must carry the request's own payload"
    assert handle.xcp_program_write_functional.call_count == 0, \
        'an absolute program must never reach the functional write callback, whatever the clear did'

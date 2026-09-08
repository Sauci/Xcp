#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP4c Task 3: PROGRAM_FORMAT (0xCB), the format state it sets (Xcp_Internal.pgm_format, DD85),
and the advertise/accept rule (DD89): PROGRAM_FORMAT accepts a non-default compression, encryption
or programming method only if GET_PGM_PROCESSOR_INFO's own PGM_PROPERTIES byte advertises the
matching SUPPORTED bit -- the same byte, read at the point of use
(Xcp_Ptr->general->pgmProperties), so the two commands cannot drift apart by construction rather
than by discipline (design doc docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md).

Functional access mode (access_method = 0x01) is the fourth term of that same compound condition,
gated on PGM_PROPERTIES' FUNCTIONAL_MODE bit -- but that bit is set only once DD84's two functional
callbacks exist (DD92), and neither is added until Tasks 5 and 6. This task therefore pins only the
refusal half of that fourth term for real (test_program_format_refuses_functional_access_...
below): no configuration this task's own schema exposes can ever advertise FUNCTIONAL_MODE, so the
'accepted when configured' half the design doc's test strategy calls for is not yet reachable, the
same honest limitation Task 4's own Block Sequence Counter tests record for the identical reason
(counter has no reader until Task 6). The structural check itself already reads the same
Xcp_Ptr->general->pgmProperties field GET_PGM_PROCESSOR_INFO reports, so Task 6 activates the
acceptance path by adding one more generation term to that shared byte -- no further change to
Xcp_DTOCmdPgmProgramFormat itself.

pgm_program_handle() (test/pgm_program_test.py), not pgm_deferred_test.py's own pgm_handle(), is
this file's base fixture throughout: DD90 (test 4 below) needs a real PROGRAM to refuse, and
pgm_handle() forces PROGRAM off. PROGRAM_FORMAT plays no part in CONNECT's own RESOURCE bit (like
PROGRAM_VERIFY before it -- Xcp_CTOCmdStdConnect reads exactly PROGRAM_CLEAR/PROGRAM/PROGRAM_MAX),
so nothing about this file's own fixture needs to force it off the way pgm_clear_handle() forces
the other three."""

import pytest

from .parameter import u32_to_array
from .pgm_deferred_test import program_start, program_reset, transmitted
from .pgm_session_test import send
from .pgm_program_test import pgm_program_handle, program
from .download_test import connect, set_mta


def pgm_format_handle(**kwargs):
    """A connected slave with the flash-programming gate on and PROGRAM_CLEAR, PROGRAM, PROGRAM_MAX
    and PROGRAM_FORMAT all enabled -- forwards to pgm_program_test.py's own pgm_program_handle()
    for the reason the module docstring above gives. xcp_program_format_api_enable is not one of
    the keys pgm_program_handle() forces, and test/parameter.py's own DefaultConfig gives the new
    key the same True default every other xcp_program_*_api_enable key already has, so a plain
    pgm_program_handle() call already answers PROGRAM_FORMAT for real -- mirrors
    pgm_verify_test.py's own identically-shaped pgm_verify_handle()."""
    return pgm_program_handle(**kwargs)


def _active_session_with_mta(handle, address=0x12345678):
    """Opens a programming session and points the MTA at `address`, confirming both responses so
    the one-frame transmit pipeline (SWS_Xcp_00859) is free before the request under test. Mirrors
    pgm_clear_test.py's and pgm_program_test.py's own identically-named, identically-shaped
    helper -- this file's own copy, following the same one-helper-per-file convention rather than
    importing a leading-underscore name from a sibling module."""
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


def test_program_format_with_all_defaults_is_accepted_and_forwarded_as_all_zeros():
    """Brief test 1. (0xCB, 0x00, 0x00, 0x00, 0x00) -- every field at its spec-default (uncompressed,
    unencrypted, sequential, absolute) -- needs no advertised capability at all (DD89's rule is
    about NON-default values only) and must reach Xcp_ProgramFormat with all four bytes intact.

    frame[0] == 0xFF relies on conftest.py's own default mock behaviour (return_value=E_OK, no
    side_effect configured here), which leaves the handler's own locally-initialised status_code at
    0 -- the same default every other PGM synchronous/polled-callback test in this suite relies on,
    e.g. pgm_verify_test.py's own identically-shaped first test.

    Mutation: dropping the argument forwarding (calling Xcp_ProgramFormat with constants instead of
    the parsed request fields) leaves frame[0] == 0xFF unchanged -- call_count alone could never
    catch it -- but fails the call_args assertion below."""
    handle = pgm_format_handle()

    frame = send(handle, (0xCB, 0x00, 0x00, 0x00, 0x00))

    assert frame[0] == 0xFF, 'all-defaults PROGRAM_FORMAT must be accepted'
    compression, encryption, programming_method, access, _p_status = handle.xcp_program_format.call_args[0]
    assert (compression, encryption, programming_method, access) == (0x00, 0x00, 0x00, 0x00), \
        'all four fields must reach the integrator exactly as transmitted (all zero)'


@pytest.mark.parametrize('field_index,supported_kwarg', (
    (0x01, 'programming_compression_supported'),
    (0x02, 'programming_encryption_supported'),
    (0x03, 'programming_non_sequential_supported'),
), ids=('compression', 'encryption', 'non_sequential'))
def test_program_format_accepts_exactly_what_get_pgm_processor_info_advertises(field_index, supported_kwarg):
    """Brief test 2, DD89's advertise/accept rule, both directions, parametrised over the three
    capability pairs rather than duplicated per capability (compression byte 1/COMPRESSION_SUPPORTED,
    encryption byte 2/ENCRYPTION_SUPPORTED, programming method byte 3/NON_SEQ_PGM_SUPPORTED -- 1.1/
    1.6.5.2.4's own request layout).

    Refused half: the matching *_supported flag is left at DefaultConfig's own False default, so
    PGM_PROPERTIES does not advertise it -- ERR_OUT_OF_RANGE, and the integrator must never be
    reached (a handler that refused only AFTER calling out would still answer (0xFE, 0x22) here, the
    trap pgm_clear_test.py's own mode-byte tests already document for PROGRAM_CLEAR).

    Accepted half: the SAME non-zero byte, now with the matching capability configured True. 'Not
    refused' is weaker than 'forwarded intact' (task brief) -- call_args is unpacked and the exact
    field asserted, so a handler answering positive without ever calling Xcp_ProgramFormat would
    raise on the unpack rather than silently pass.

    Mutation (Step 6): inverting or deleting this ONE field's own SUPPORTED check must fail only
    this parametrisation's own refused-half case, not the other two capabilities'."""
    request = [0xCB, 0x00, 0x00, 0x00, 0x00]
    request[field_index] = 0x01

    refused_handle = pgm_format_handle()
    refused_frame = send(refused_handle, tuple(request))
    assert refused_frame[0:2] == (0xFE, 0x22), \
        'ERR_OUT_OF_RANGE: byte %d set without the matching capability advertised' % field_index
    assert refused_handle.xcp_program_format.call_count == 0, \
        'an unadvertised non-default value must never reach the integrator'

    accepted_handle = pgm_format_handle(**{supported_kwarg: True})
    accepted_frame = send(accepted_handle, tuple(request))
    assert accepted_frame[0] == 0xFF, \
        'the identical request must be accepted once %s is configured' % supported_kwarg
    forwarded = accepted_handle.xcp_program_format.call_args[0]
    assert forwarded[field_index - 1] == 0x01, \
        'the advertised, non-default byte must reach the integrator exactly as transmitted'


def test_program_format_refuses_functional_access_when_not_advertised():
    """Brief test 3, refusal half only -- see the module docstring above for why the acceptance half
    is not reachable within this task: PGM_PROPERTIES' FUNCTIONAL_MODE bit is set only once DD84's
    two functional callbacks are configured (DD92), and neither exists before Tasks 5/6.

    access_method = 0x01 is DD89's fourth term, checked against the same
    Xcp_Ptr->general->pgmProperties byte the other three use -- FUNCTIONAL_MODE is never set by
    this task's own generation (no schema flag this task adds can turn it on), so this refusal is
    unconditional today and the mutation below is what actually proves the check exists rather than
    the bit simply never being reachable.

    Mutation (Step 6): deleting this fourth term (or the whole access_method check) makes this test
    fail -- the request is answered 0xFF and Xcp_ProgramFormat is called, instead of ERR_OUT_OF_RANGE
    with no call at all."""
    handle = pgm_format_handle()

    frame = send(handle, (0xCB, 0x00, 0x00, 0x00, 0x01))

    assert frame[0:2] == (0xFE, 0x22), \
        'ERR_OUT_OF_RANGE: FUNCTIONAL_MODE is not, and today cannot be, advertised'
    assert handle.xcp_program_format.call_count == 0, \
        'functional access must never reach the integrator while unadvertised'


@pytest.mark.parametrize('required_kwarg', (
    'programming_compression_required',
    'programming_encryption_required',
    'programming_non_sequential_required',
), ids=('compression_required', 'encryption_required', 'non_sequential_required'))
def test_program_is_refused_err_sequence_without_a_preceding_program_format_when_required(required_kwarg):
    """Brief test 4, DD90: 'If modified data transmission is expected by the slave and no
    PROGRAM_FORMAT command is transmitted, the slave responds with ERR_SEQUENCE' (1.6.5.2.4).
    Parametrised over the three REQUIRED bits individually, mirroring test 2's own per-capability
    shape: a PROGRAM (0xD0) sent against an ACTIVE session that never received a PROGRAM_FORMAT is
    refused (0xFE, 0x29) whenever ANY of the three is configured.

    A real, active session (PROGRAM_START + SET_MTA) is required first, so the refusal below is
    unambiguously DD90's own gate rather than the pre-existing pgm_state != XCP_PGM_ACTIVE one
    (pgm_program_test.py's own test_program_is_refused_err_sequence_before_program_start_succeeds
    already pins that separate gate).

    Mutation (per term, Step 6): deleting or inverting only THIS required flag's own check in the
    shared static helper must fail only this parametrisation's own case, not the other two."""
    handle = pgm_format_handle(**{required_kwarg: True})
    _active_session_with_mta(handle)

    frame = send(handle, (0xD0, 0x01, 0xAA))

    assert frame[0:2] == (0xFE, 0x29), \
        'ERR_SEQUENCE: %s is configured but no PROGRAM_FORMAT preceded this PROGRAM' % required_kwarg
    assert handle.xcp_program_write.call_count == 0, \
        'a PROGRAM refused by DD90 must never reach Xcp_ProgramWrite'


def test_program_succeeds_without_a_preceding_program_format_when_nothing_is_required():
    """Brief test 4, the other half: with no REQUIRED bit configured (DefaultConfig's own default
    for all three), the identical PROGRAM with no preceding PROGRAM_FORMAT succeeds -- 1.6.5.2.4's
    own 'unmodified data and absolute address access method is supposed' when the command is not
    sent at all, which this build already offers by default."""
    handle = pgm_format_handle()
    _active_session_with_mta(handle)

    frame = send(handle, (0xD0, 0x01, 0xAA))

    assert frame[0] == 0xFF, 'no REQUIRED capability is configured, so PROGRAM must succeed'


def _formatted_session(handle):
    """An active, MTA-pointed session that has ALSO been told a non-default compression method via
    PROGRAM_FORMAT, so test_program_is_refused_err_sequence_without_a_preceding_program_format_when_
    required's own REQUIRED gate is satisfied and a following PROGRAM can succeed -- the baseline
    every test 5 helper below builds on before checking whether some OTHER command resets it back to
    ERR_SEQUENCE.

    Every exchange below is confirmed before the next is sent (Xcp_CanIfTxConfirmation), including
    the very last one, so this helper leaves the one-frame transmit pipeline (SWS_Xcp_00859) free
    for whatever the caller sends next -- mirroring _active_session_with_mta's own two confirmed
    steps. Without it, PROGRAM's own Xcp_CTOErrorMatrix entry (XCP_INTERNAL_ERR_CMD_BUSY) would
    refuse -- or, measured directly, simply transmit nothing for -- the caller's own following
    request."""
    _active_session_with_mta(handle)
    format_frame = send(handle, (0xCB, 0x01, 0x00, 0x00, 0x00))
    assert format_frame[0] == 0xFF, 'setup: PROGRAM_FORMAT must be accepted (compression supported)'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    program_frame = send(handle, (0xD0, 0x01, 0xAA))
    assert program_frame[0] == 0xFF, \
        'setup: PROGRAM must now succeed -- PROGRAM_FORMAT was just honoured'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def test_set_mta_resets_the_program_format_state_to_defaults():
    """Brief test 5, DD85's lifetime, the clean case the brief itself points at: 'observable via
    test 4's REQUIRED behaviour returning to ERR_SEQUENCE'. SET_MTA touches no pgm_state of its own
    (DD86), so the session stays XCP_PGM_ACTIVE throughout -- a PROGRAM refused after SET_MTA here
    can only be DD90's own REQUIRED gate reopening, not the unrelated pgm_state gate.

    Mutation (Step 6): deleting the SET_MTA reset (Xcp_PgmFormatReset(), called from
    Xcp_DTOCmdStdSetMta) leaves pgm_format.compression_method at 0x01 from the setup PROGRAM_FORMAT
    above, so DD90's gate stays satisfied and the PROGRAM below wrongly succeeds instead of being
    refused."""
    handle = pgm_format_handle(programming_compression_supported=True,
                               programming_compression_required=True)
    _formatted_session(handle)

    set_mta(handle, 0x12345678)

    frame = send(handle, (0xD0, 0x01, 0xAA))
    assert frame[0:2] == (0xFE, 0x29), \
        'ERR_SEQUENCE: SET_MTA must reset pgm_format back to defaults (DD85)'


def test_connect_resets_the_program_format_state_to_defaults():
    """Brief test 5, DD85's lifetime: CONNECT (1.1/1.6.1.1.1's own session start) resets pgm_format
    alongside every other piece of session state this module already tears down there.

    CONNECT also drops pgm_state back to XCP_PGM_IDLE, so the session is deliberately re-opened
    (PROGRAM_START + SET_MTA again) before the probing PROGRAM below -- otherwise a refusal would be
    ambiguous between the pre-existing pgm_state gate and this task's own pgm_format one, and would
    prove nothing about DD85 specifically."""
    handle = pgm_format_handle(programming_compression_supported=True,
                               programming_compression_required=True)
    _formatted_session(handle)

    connect(handle)
    _active_session_with_mta(handle)

    frame = send(handle, (0xD0, 0x01, 0xAA))
    assert frame[0:2] == (0xFE, 0x29), \
        'ERR_SEQUENCE: CONNECT must reset pgm_format back to defaults (DD85), not merely pgm_state'


def test_program_reset_resets_the_program_format_state_to_defaults():
    """Brief test 5, DD85's lifetime: PROGRAM_RESET (1.1/1.6.5.1.4, ending the sequence) resets
    pgm_format alongside pgm_state and pgm_block, which Xcp_PgmCompleteProgramReset already clears.

    Mirrors test_connect_resets_the_program_format_state_to_defaults immediately above: PROGRAM_RESET
    also disconnects (DD57), dropping pgm_state to XCP_PGM_IDLE, so the session is reopened before
    the probing PROGRAM for the identical reason -- CONNECT is the only door back from the
    disconnected state, and is what test_connect_... above already proves resets pgm_format on its
    own, so reconnecting here does not itself explain a renewed refusal."""
    handle = pgm_format_handle(programming_compression_supported=True,
                               programming_compression_required=True)
    _formatted_session(handle)

    handle.can_if_transmit.reset_mock()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_RESET must succeed'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    connect(handle)
    _active_session_with_mta(handle)

    frame = send(handle, (0xD0, 0x01, 0xAA))
    assert frame[0:2] == (0xFE, 0x29), \
        'ERR_SEQUENCE: PROGRAM_RESET must reset pgm_format back to defaults (DD85)'


def test_get_status_does_not_reset_the_program_format_state():
    """Brief test 5, the negative control: an unrelated command must NOT reset pgm_format. Without
    this, a change that resets the format on every command (or on none, vacuously passing the three
    tests above by coincidence) would not be caught by them alone."""
    handle = pgm_format_handle(programming_compression_supported=True,
                               programming_compression_required=True)
    _formatted_session(handle)

    status_frame = send(handle, (0xFD,))
    assert status_frame[0] == 0xFF, 'setup: GET_STATUS itself must succeed'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    frame = send(handle, (0xD0, 0x01, 0xAA))
    assert frame[0] == 0xFF, \
        'GET_STATUS must not reset pgm_format -- PROGRAM must still succeed'

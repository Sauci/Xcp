#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .pgm_clear_test import pgm_clear_handle, _active_session_with_mta
from .pgm_deferred_test import pgm_handle, program_start, transmitted
from .pgm_session_test import send


def get_pgm_processor_info(handle):
    """GET_PGM_PROCESSOR_INFO (0xCE, Task 5), through send() (pgm_session_test.py): resets the
    mock, sends the request, pumps one Xcp_MainFunction, and returns the frame it produced (or
    None). This command never defers (Xcp_DTOCmdPgmGetPgmProcessorInfo's own @details,
    source/Xcp_Internal.h) -- unlike program_start/program_reset in pgm_deferred_test.py, which
    deliberately withhold the pump so a test can count polls, there is nothing here to count, so
    one main-function call is always enough to see the answer."""
    return send(handle, (0xCE,))


def test_get_pgm_processor_info_reports_pgm_properties_absolute_mode_only():
    """DD68. 1.0/1.6.5.2.1's mode-bit table reads FUNCTIONAL_MODE:ABSOLUTE_MODE = "0 1" as "Only
    Absolute mode supported" -- the one mode this module offers (SP4b: PROGRAM_CLEAR, PROGRAM,
    PROGRAM_MAX, PROGRAM_NEXT). Checked as the WHOLE byte, not merely bit 0: a module that also
    claimed COMPRESSION_SUPPORTED, ENCRYPTION_SUPPORTED or NON_SEQ_PGM_SUPPORTED -- none of which
    is implemented -- would still pass a bit-0-only assertion. 0x01 is the only value that is both
    ABSOLUTE_MODE set and every other bit clear.

    Mutation: setting XCP_PGM_PROPERTIES_FUNCTIONAL_MODE instead of (or alongside)
    XCP_PGM_PROPERTIES_ABSOLUTE_MODE, or OR-ing in any of the COMPRESSION_x/ENCRYPTION_x/
    NON_SEQ_PGM_x bits (source/Xcp_Internal.h), changes this byte and fails here."""
    handle = pgm_handle()

    response = get_pgm_processor_info(handle)

    assert response[0:2] == (0xFF, 0x01), \
        'PGM_PROPERTIES must read exactly ABSOLUTE_MODE set, every other bit clear: %r' % (response,)


def test_get_pgm_processor_info_reports_max_sector_zero():
    """DD68's original claim, still truthful for a slave with no sector description: GET_SECTOR_INFO
    answers ERR_SEGMENT_NOT_VALID for a sector that is not available, and every sector number is out
    of range when MAX_SECTOR is 0.

    Final review F10: this docstring used to say GET_SECTOR_INFO was "still unimplemented, SP4c" and
    answered ERR_OUT_OF_RANGE, and it was wrong twice over. SP4c Task 2 implements the command
    (Xcp_DTOCmdPgmGetSectorInfo, source/Xcp_Pgm.c), and DD88 settles the code against 1.6.5.2.2's own
    self-contradiction: the section's PROSE says ERR_OUT_OF_RANGE, but §1.7.3.2.5's row for that same
    command lists ERR_CMD_BUSY, ERR_CMD_UNKNOWN, ERR_CMD_SYNTAX, ERR_MODE_NOT_VALID and
    ERR_SEGMENT_NOT_VALID and no ERR_OUT_OF_RANGE at all -- so the listed code that fits is used and
    no deviation is taken (DD65's rule from SP4b). This was the last surviving copy of the prediction
    DD88 falsified; test/pgm_sector_test.py asserts the actual code, and MAX_SECTOR's own agreement
    with a GET_SECTOR_INFO walk is pinned there too.

    Still MAX_SECTOR zero here, and by configuration rather than by the hardcoding DD68 described:
    `sectors` defaults empty (test/parameter.py), MAX_SECTOR is that array's length (DD87), and this
    test's own handle declares no sector.

    The PID is checked too, and deliberately not left implicit: this suite's own default
    trailing_value is 0 (test/parameter.py), and Xcp_FillErrorPacket's own 2-byte error shape
    (source/Xcp.c) pads from index 2 onward with that same value -- so an ERR_SEQUENCE response
    (0xFE, 0x29, 0x00, ...), byte 2 included, would satisfy a response[2] == 0x00 assertion alone
    just as well as the true positive response does. Measured directly: a `pgm_state != ACTIVE`
    guard mistakenly added to the handler answers ERR_SEQUENCE from XCP_PGM_IDLE and left an
    earlier revision of this test (checking only response[2]) passing regardless. response[0]
    closes that gap.

    Mutation: reporting any non-zero MAX_SECTOR fails here directly; so does refusing the command
    entirely, now that the PID is checked alongside it."""
    handle = pgm_handle()

    response = get_pgm_processor_info(handle)

    assert response[0] == 0xFF, 'setup: must be the positive response, not an error: %r' % (response,)
    assert response[2] == 0x00, 'MAX_SECTOR must read 0: %r' % (response,)


def test_get_pgm_processor_info_response_is_exactly_three_bytes():
    """Closes a gap the two tests above cannot reach on their own: this suite's own default
    trailing_value is 0 (test/parameter.py), the same value MAX_SECTOR itself correctly reports, so
    Xcp_FinalizeResPacket's own startIndex argument (source/Xcp.c) mutated from 0x03u down to 0x02u
    would let that function's own trailing-fill loop overwrite SduDataPtr[2] with the pad byte
    instead of leaving the MAX_SECTOR Xcp_DTOCmdPgmGetPgmProcessorInfo already wrote there -- and the
    wire byte would still read 0x00 either way, indistinguishable from
    test_get_pgm_processor_info_reports_max_sector_zero's own assertion. Reading SduLength directly
    is the only way to pin the argument itself rather than a value it happens to alias with the
    correct one.

    Mutation: 0x03u -> 0x02u fails here (SduLength reads 2 instead of 3). 0x03u -> 0x01u or 0x00u is
    already caught by test_get_pgm_processor_info_reports_pgm_properties_absolute_mode_only above,
    since the same fill loop would then also overwrite SduDataPtr[1] -- 0x01, PGM_PROPERTIES' own
    correct value, is not this suite's trailing_value, so that byte would visibly change too."""
    handle = pgm_handle()

    response = get_pgm_processor_info(handle)
    assert response[0] == 0xFF, 'setup: must be the positive response, not an error: %r' % (response,)

    length = handle.can_if_transmit.call_args[0][1].SduLength
    assert length == 0x03, \
        'GET_PGM_PROCESSOR_INFO answers exactly PID + PGM_PROPERTIES + MAX_SECTOR, 3 bytes: %r' \
        % (length,)


def test_get_pgm_processor_info_is_answered_identically_from_xcp_pgm_idle_and_xcp_pgm_active():
    """Decides, and pins, the one question the task brief leaves open: whether this command is
    refused before PROGRAM_START the way PROGRAM_CLEAR, PROGRAM, PROGRAM_MAX and PROGRAM_NEXT are.
    It is not. 1.0/1.6.5.1.1's "not allowed until PROGRAM_START" list names exactly those four
    commands, not this one, and Xcp_CTOErrorMatrix[0xCE] (source/Xcp.c) already agreed before this
    task touched it: ERR_CMD_BUSY, ERR_CMD_UNKNOWN and ERR_CMD_SYNTAX only, matching §1.7.3.2.5's
    own row for GET_PGM_PROCESSOR_INFO exactly -- no ERR_SEQUENCE (the code every one of the four
    gated commands answers from XCP_PGM_IDLE) and no ERR_PGM_ACTIVE (DD51's gate). This module's own
    handler therefore carries no Xcp_Internal.pgm_state check of any kind, and this test is what
    would fail if a future change added one in either direction.

    Each exchange is confirmed before the next is sent (Xcp_CanIfTxConfirmation), freeing the
    one-frame transmit pipeline SWS_Xcp_00859 requires -- both this command's own row and
    PROGRAM_START's carry XCP_INTERNAL_ERR_CMD_BUSY, so an unconfirmed response left occupying that
    slot would answer ERR_CMD_BUSY instead of what this test means to observe, the same reasoning
    pgm_clear_test.py's own _active_session_with_mta documents.

    Mutation: gating the handler on `pgm_state != XCP_PGM_ACTIVE` (mirroring PROGRAM_CLEAR's own
    guard) answers ERR_SEQUENCE for the first exchange below instead of the positive response;
    gating it the other way (`== XCP_PGM_ACTIVE`, refusing an open session) answers ERR_SEQUENCE for
    the second."""
    handle = pgm_handle()

    idle_response = get_pgm_processor_info(handle)
    assert idle_response[0:3] == (0xFF, 0x01, 0x00), \
        'must answer normally from XCP_PGM_IDLE (no PROGRAM_START has been sent): %r' % (idle_response,)
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    # reset_mock() before the exchange this guard reads, not after: the idle response above is also
    # 0xFF-led, so without it the assertion is satisfied by stale data and a PROGRAM_START that
    # silently stopped transmitting would leave this test re-exercising XCP_PGM_IDLE while claiming
    # XCP_PGM_ACTIVE. test/pgm_clear_test.py's _active_session_with_mta, which this mirrors, resets
    # for the same reason.
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: PROGRAM_START must succeed to reach XCP_PGM_ACTIVE'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    active_response = get_pgm_processor_info(handle)
    assert active_response[0:3] == (0xFF, 0x01, 0x00), \
        'must answer identically from XCP_PGM_ACTIVE: %r' % (active_response,)


def test_get_pgm_processor_info_advertised_absolute_only_mode_matches_program_clear_refusing_functional_mode():
    """The test this sub-project's own history most demands (task brief): that the claim
    GET_PGM_PROCESSOR_INFO makes on the wire and the behaviour PROGRAM_CLEAR actually delivers are
    the SAME fact, checked together in one test, rather than trusted to stay in step because two
    separate test files each happen to assert their own half forever. DD68 is the advertisement --
    ABSOLUTE_MODE only; DD67 is the enforcement -- PROGRAM_CLEAR mode 0x01 (functional) refused
    ERR_OUT_OF_RANGE. What only THIS test pins is the two facts drifting apart, which asserting each
    alone in its own file cannot catch.

    Final review F11: the sentence removed here cited
    test_program_clear_functional_mode_is_refused_err_out_of_range_without_calling_the_integrator as
    the test that "already pins DD67 in isolation". SP4c Task 5 deleted that test, because DD93
    falsifies its whole premise -- this slave CAN offer functional clear, and does when configured.
    The isolated half now lives in test/pgm_functional_test.py's own
    test_program_clear_functional_is_refused_when_not_configured. This test's own claim is unchanged
    and still worth making: it is the pairing, on a build that configures no functional access, that
    nothing else asserts in one place."""
    handle = pgm_clear_handle()

    info_response = get_pgm_processor_info(handle)
    assert info_response[0:2] == (0xFF, 0x01), \
        'setup: GET_PGM_PROCESSOR_INFO must advertise ABSOLUTE_MODE only before this test can check ' \
        'PROGRAM_CLEAR keeps that promise: %r' % (info_response,)
    # Confirmed before the next exchange: the one-frame transmit pipeline (SWS_Xcp_00859) must be
    # free before _active_session_with_mta's own PROGRAM_START, the same reasoning its docstring
    # and this file's own idle/active test above both already document.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    _active_session_with_mta(handle)

    clear_response = send(handle, (0xD1, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00))
    assert clear_response[0:2] == (0xFE, 0x22), \
        'PROGRAM_CLEAR mode 0x01 (functional) must be refused ERR_OUT_OF_RANGE -- exactly what ' \
        'FUNCTIONAL_MODE clear in PGM_PROPERTIES above promised: %r' % (clear_response,)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import DefaultConfig, u32_to_array
from .conftest import XcpTest
from .download_test import connect
from .pgm_deferred_test import program_start, transmitted
from .pgm_session_test import send


def pgm_program_handle(**kwargs):
    """A connected slave with the flash-programming gate on and PROGRAM_CLEAR, PROGRAM and
    PROGRAM_MAX all enabled. Unlike pgm_deferred_test.py's own pgm_handle() and
    pgm_clear_test.py's pgm_clear_handle(), nothing needs forcing here beyond programming.enabled
    itself: DefaultConfig's own baseline already has xcp_program_clear_api_enable,
    xcp_program_api_enable and xcp_program_max_api_enable all True (test/parameter.py) -- Task 3
    deletes the last two terms of SP4a's generation guard (DD69), so this is the first task for
    which that default combination actually generates at all."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   programming_enabled=True,
                                   **kwargs))
    connect(handle)
    return handle


def _active_session_with_mta(handle, address=0x12345678):
    """Opens a programming session and points the MTA at `address`, confirming both responses so
    the one-frame transmit pipeline (SWS_Xcp_00859) is free before the PROGRAM/PROGRAM_MAX request
    under test. Mirrors pgm_clear_test.py's own identically-named, identically-shaped helper."""
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


def program(handle, elements, data=()):
    """PROGRAM (0xD0, Task 3), without pumping Xcp_MainFunction -- mirrors pgm_clear_test.py's own
    program_clear() and for the same reason: a test needs to pump Xcp_MainFunction and confirm
    transmissions itself, at its own pace. Byte 1 is the element count; AG=1 (BYTE, this suite's
    default) means no alignment byte, so the data begins immediately at byte 2 (1.1/1.6.5.1.3)."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD0, elements) + tuple(data)))


def program_max(handle, data):
    """PROGRAM_MAX (0xC9, Task 3), without pumping Xcp_MainFunction -- mirrors program() above.
    AG=1 means no alignment byte, so the data begins immediately at byte 1 (1.1/1.6.5.2.6); `data`
    is normally exactly MAX_CTO-1 bytes, the fixed size being the point of this command."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xC9,) + tuple(data)))


def test_program_is_refused_err_sequence_before_program_start_succeeds():
    """1.1/1.6.5.1.1 requires PROGRAM refused until PROGRAM_START has succeeded -- the same gate
    Xcp_DTOCmdPgmProgramClear's own handler carries (Task 2, DD67), and this is that gate's second
    real user. pgm_program_handle() connects but never sends PROGRAM_START, so pgm_state is
    XCP_PGM_IDLE here by construction.

    Mutation: deleting the `pgm_state != XCP_PGM_ACTIVE` check (or inverting it) falls through to
    the element-count parsing and then to Xcp_ProgramWrite, whose mock defaults to E_OK with a zero
    status code (conftest.py) -- the response becomes (0xFF,), not (0xFE, 0x29), and the call_count
    assertion below also catches it directly."""
    handle = pgm_program_handle()

    assert send(handle, (0xD0, 0x01, 0xAA))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'
    assert handle.xcp_program_write.call_count == 0, 'the integrator must not be reached either'


def test_program_max_is_refused_err_sequence_before_program_start_succeeds():
    """The same gate's third real user, against PROGRAM_MAX. Padded to MAX_CTO (8) bytes -- this
    suite's default -- so a truncated-frame answer could not be confused with the session gate this
    test actually means to pin."""
    handle = pgm_program_handle()

    assert send(handle, (0xC9,) + tuple(range(7)))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'
    assert handle.xcp_program_write.call_count == 0, 'the integrator must not be reached either'


def test_program_hands_the_single_frame_payload_to_the_integrator_at_the_mta():
    """1.1/1.6.5.1.3: 'The data block of the specified length ... contained in the CMD will be
    copied into memory, starting at the MTA.' Asserted on the bytes the integrator actually
    received, not on the response -- a handler that answered correctly while handing the integrator
    a stale, zero, or wrongly-offset buffer would still pass a response-only assertion."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x12345678)

    program(handle, 0x03, data=(0x11, 0x22, 0x33))

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x12345678, 'the current MTA'
    assert length == 0x03, "the request's own element count"
    assert bytes(p_data[0:length]) == bytes((0x11, 0x22, 0x33)), 'exactly the request payload'


def test_program_mta_post_increments_by_the_bytes_written_on_success():
    """DD66, the success path. 1.1/1.6.5.1.3: 'The MTA will be post-incremented by the number of
    data bytes.' Asserted through a FOLLOWING PROGRAM landing at the next address, since
    Xcp_Internal is not reachable from this CFFI harness (test/clear_daq_list_test.py:80-92)."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x1000)

    # Fix round 1, finding 3. Without this, transmitted() reads _active_session_with_mta's own
    # leftover SET_MTA response (also PID 0xFF, XCP_PID_RESPONSE, on any successful command) rather
    # than PROGRAM's own -- the setup assertion below would then pass whether or not this PROGRAM
    # transmitted anything at all, which review's own probe proved directly: the identical assertion
    # passes with no PROGRAM sent and no Xcp_MainFunction call in between.
    handle.can_if_transmit.reset_mock()

    program(handle, 0x03, data=(0x11, 0x22, 0x33))
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFF, 'setup: the first PROGRAM must succeed'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.xcp_program_write.reset_mock()

    program(handle, 0x02, data=(0x44, 0x55))

    address, _p_data, _length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x1003, \
        'the MTA must have advanced by the 3 bytes the first PROGRAM wrote'


def test_a_failed_program_write_leaves_the_mta_unmoved():
    """DD66, the failure path -- 'the term most likely to be missing, because the happy path passes
    without it' (task brief). 1.7.3.2.5 gives PROGRAM the pre-action SYNCH+SET_MTA, so a master
    recovering from a failure re-points the MTA itself; a slave that had already advanced it would
    have moved a pointer the master believes it still controls. Same construction as the
    success-path test above, except the first write reports failure: the SECOND PROGRAM must land
    at the SAME address, not one 3 bytes on.

    Mutation: an Xcp_PgmCompleteProgramWrite that advances Xcp_Internal.memory_transfer.address
    unconditionally, rather than only in the statusCode == 0 branch, makes the second PROGRAM's own
    address 0x1003 instead of 0x1000, which the final assertion catches directly."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x1000)

    def write_failed(_address, _p_data, _length, p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_program_write.side_effect = write_failed

    program(handle, 0x03, data=(0x11, 0x22, 0x33))
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0:2] == (0xFE, 0x24), 'setup: ERR_ACCESS_DENIED'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.xcp_program_write.side_effect = None  # the second PROGRAM succeeds; only its own
    handle.xcp_program_write.reset_mock()         # address matters to this test

    program(handle, 0x02, data=(0x44, 0x55))

    address, _p_data, _length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x1000, \
        'a failed write must not have advanced the MTA -- the second PROGRAM must land at the ' \
        'SAME address the first one was handed'


def test_program_with_zero_elements_ends_the_segment_without_calling_the_integrator():
    """DD64. 1.1/1.6.5.1.3: 'The end of the memory segment is indicated, when the number of data
    elements is 0.' Distinct from programming zero bytes: it answers positively without ever
    reaching Xcp_ProgramWrite, and does not end the programming sequence -- 1.6.5.1.3 gives that to
    PROGRAM_RESET, which SP4a implements.

    call_count == 0 is what actually distinguishes this from a handler that happened to answer 0xFF
    for an unrelated reason: the default mock (E_OK, zero status) would also answer 0xFF if the
    zero-count branch were deleted and fell through to an ordinary (zero-length) write."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    assert send(handle, (0xD0, 0x00))[0] == 0xFF, 'a positive response, with no integrator call'
    assert handle.xcp_program_write.call_count == 0


def test_program_declaring_more_elements_than_fit_a_single_frame_is_refused_err_out_of_range():
    """Task 3 does not implement master block mode for PROGRAM (design doc title: 'PROGRAM without
    block mode') -- PROGRAM_NEXT, which Task 4 adds, is what a genuine multi-frame block needs. A
    declared count larger than one CTO frame can carry is therefore refused outright, mirroring
    Xcp_DTOCmdCalDownload's own identical choice when ITS OWN masterBlockModeSupported is FALSE
    (Xcp_DataTransferInitialize, source/Xcp.c) --
    test_download_returns_err_out_of_range_when_the_count_exceeds_a_single_packet
    (test/download_test.py) pins the identical condition for that sibling command. At MAX_CTO=8,
    AG=BYTE, a single frame carries at most 6 data bytes (2 header bytes reserved); 7 is one past
    that.

    call_count == 0 is the assertion that matters: a handler that copied the 6 bytes it COULD hold
    and called Xcp_ProgramWrite anyway would silently discard the master's 7th byte and report
    success for less than what was asked -- exactly the silent-partial-write class of bug the
    call-count assertion, not the wire code alone, is what catches."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    assert send(handle, (0xD0, 0x07) + tuple(range(7)))[0:2] == (0xFE, 0x22), 'ERR_OUT_OF_RANGE'
    assert handle.xcp_program_write.call_count == 0


def test_program_declaring_more_bytes_than_the_frame_actually_carries_answers_err_cmd_syntax():
    """Mirrors Xcp_DTOCmdCalDownload's own guard against a frame shorter than the payload it
    announces (source/Xcp_Cal.c) -- without this the handler would copy whatever memory follows the
    received PDU into pgm_block, and from there into flash. 3 elements declared, only 1 actually
    sent -- well within a single frame's own 6-byte capacity at MAX_CTO=8, AG=BYTE, so this is not
    the oversized-count case above."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    assert send(handle, (0xD0, 0x03, 0x11))[0:2] == (0xFE, 0x21), 'ERR_CMD_SYNTAX'
    assert handle.xcp_program_write.call_count == 0


def test_program_below_two_bytes_answers_err_cmd_syntax():
    """1.1/1.6.5.1.3's request is command code then a BYTE element count: two bytes at minimum,
    since DD64 makes zero a legitimate count needing no further bytes at all -- unlike DOWNLOAD's
    own minimum (script/source_cfg.c.jinja2: 3 for DOWNLOAD 0xF0), whose own count must be >= 1
    (1.0/1.6.2.1.1's table: '[1..(MAX_CTO-2)/AG] Standard mode'). PROGRAM's own generated minimum
    is 2 (Task 3), not SP4a's placeholder 4: this test is what confirms that generated value.

    No session is opened first: the generic syntax gate runs in Xcp_CanIfRxIndication before
    Xcp_PIDTable is even consulted, so it fires regardless of pgm_state -- covered directly by a
    single-byte request, which a pgm_state check alone could never explain an ERR_CMD_SYNTAX answer
    for.

    Mutation: script/source_cfg.c.jinja2's PROGRAM ctoInfo row generating a minimum other than 2
    (e.g. reverted to 4) either lets this one-byte request past the syntax gate and into
    Xcp_DTOCmdPgmProgram with no session open (answering ERR_SEQUENCE instead of ERR_CMD_SYNTAX,
    caught here), or -- if raised further -- would also start refusing the legitimate 2-byte
    zero-count request test_program_with_zero_elements_ends_the_segment_without_calling_the_integrator
    sends, caught there instead."""
    handle = pgm_program_handle()

    assert send(handle, (0xD0,))[0:2] == (0xFE, 0x21), 'ERR_CMD_SYNTAX'


def test_program_defers_through_the_pending_slot_and_keeps_passing_the_same_bytes():
    """Xcp_ProgramWrite's contract presents pData on EVERY call, not only the first (design Section
    4) -- Xcp_Internal.pgm_block is what makes that possible across poll cycles: standing state the
    poll re-reads directly, the same shape Xcp_Internal.memory_transfer.address already has for the
    MTA, and PROGRAM_CLEAR's own clear range has in pending_command.args (Task 2) -- except here it
    is the block buffer itself doing that job, not a union member.

    A module that copied the bytes into some OTHER, transient buffer the handler alone owned would
    still pass every synchronous test above (none of them poll more than once) and only fail here,
    on the LAST call -- mirrors
    pgm_clear_test.test_program_clear_defers_through_the_pending_slot_and_keeps_passing_the_clear_range."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x3000)

    state = dict(calls=0)

    def busy_then_complete(_address, _p_data, _length, p_status_code):
        # call 1: the fast path inside the handler itself (program() below); call 2: the first
        # Xcp_MainFunction poll; only call 3, the second poll, completes.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_write.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program(handle, 0x03, data=(0xAA, 0xBB, 0xCC))

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFD, 'still busy on the second poll: only EV_CMD_PENDING (DD54)'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM response arrives'

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args_list[-1][0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x3000, \
        'the MTA must still be the current one on the completing poll'
    assert bytes(p_data[0:length]) == bytes((0xAA, 0xBB, 0xCC)), \
        'the same bytes must still be presented on the completing poll'


def test_program_max_programs_max_cto_minus_one_elements_from_the_mta():
    """1.1/1.6.5.2.6: 'The data block with the fixed length of MAX_CTO-1 elements contained in the
    CTO will be programmed into non-volatile memory, starting at the MTA.' At AG=BYTE (this suite's
    default) an element is one byte, so MAX_CTO-1 elements is MAX_CTO-1 bytes: 7, at this suite's
    default MAX_CTO of 8. No count byte in the request -- the fixed size is the point of this
    command -- so the data begins right after the command code."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2000)

    # Fix round 1, finding 3 -- same hazard and same fix as
    # test_program_mta_post_increments_by_the_bytes_written_on_success above: without this,
    # transmitted()'s own final assertion below reads _active_session_with_mta's leftover SET_MTA
    # response (also 0xFF) rather than PROGRAM_MAX's, and would pass whether or not PROGRAM_MAX
    # transmitted anything.
    handle.can_if_transmit.reset_mock()

    data = tuple(range(0x01, 0x08))  # 7 bytes = MAX_CTO(8) - 1
    program_max(handle, data)
    handle.lib.Xcp_MainFunction()

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x2000
    assert length == 0x07
    assert bytes(p_data[0:length]) == bytes(data)
    assert transmitted(handle)[0] == 0xFF


def test_program_max_short_frame_answers_err_cmd_syntax_without_calling_the_integrator():
    """PROGRAM_MAX's own 1.7.3.2.5 row carries no ERR_CMD_SYNTAX bit at all -- unlike DOWNLOAD_MAX's
    row, which does -- so the generic pre-dispatch length gate (Xcp_CanIfRxIndication, source/Xcp.c)
    never even consults this command's ctoInfo minimum: it always dispatches, however short the
    frame. This handler's own explicit MAX_CTO check is therefore the ONLY protection against
    reading past a short received PDU, not merely a stylistic mirror of
    Xcp_DTOCmdCalDownloadMax's identical-looking one. A single byte (the command code alone) is as
    short as a frame can be."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    assert send(handle, (0xC9,))[0:2] == (0xFE, 0x21), 'ERR_CMD_SYNTAX'
    assert handle.xcp_program_write.call_count == 0


def test_program_max_succeeds_at_the_minimum_schema_legal_block_size():
    """Task 3 review, fix round 1, finding 1. Before this fix round,
    Xcp_Internal.pgm_block.data was sized from XCP_PGM_MAX_BLOCK_SIZE*(MAX_CTO-2) alone -- a
    PROGRAM frame's own unit -- and PROGRAM_MAX's fixed transfer (MAX_CTO-1 bytes at AG=BYTE, since
    it carries no element-count byte of its own reserving a position) is one byte longer than that,
    so programming.max_block_size=1 (then schema-legal) overflowed the buffer on EVERY PROGRAM_MAX
    request: CONNECT advertised the command while it answered ERR_MEMORY_OVERFLOW unconditionally --
    the D10 shape this sub-project exists to close, reachable from a schema-legal configuration.
    This test replaces the one that used to pin that (now corrected) permanent refusal.

    The buffer is now sized as the LARGER of that same PROGRAM-frame unit and MAX_CTO-1
    (source/Xcp_Internal.h), so at max_block_size=1 -- also now the schema's own raised minimum, 0
    no longer being legal -- it is exactly MAX_CTO-1 (8-1=7) bytes: precisely what this command
    needs, with nothing to spare. Asserted the same way
    test_program_max_programs_max_cto_minus_one_elements_from_the_mta above is: the integrator
    receives the full 7-byte payload at the current MTA, and the wire answers 0xFF, not
    ERR_MEMORY_OVERFLOW."""
    handle = pgm_program_handle(programming_max_block_size=1, max_cto=8)
    _active_session_with_mta(handle, address=0x5000)
    handle.can_if_transmit.reset_mock()  # fix round 1, finding 3's own hazard: without this,
    # transmitted() below could read _active_session_with_mta's leftover SET_MTA response instead
    # of PROGRAM_MAX's own.

    data = tuple(range(0x01, 0x08))  # 7 bytes = MAX_CTO(8) - 1
    program_max(handle, data)
    handle.lib.Xcp_MainFunction()

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x5000
    assert length == 0x07
    assert bytes(p_data[0:length]) == bytes(data)
    assert transmitted(handle)[0] == 0xFF, \
        'PROGRAM_MAX must succeed at the minimum legal block size, not answer ERR_MEMORY_OVERFLOW'


def test_program_max_defers_through_the_pending_slot():
    """The same deferral mechanism PROGRAM's own test above pins, exercised through PROGRAM_MAX
    instead: a module that answered synchronously regardless of what Xcp_ProgramWrite's first call
    reports would transmit before the busy integrator ever completes, which the withheld-response
    assertion below catches directly."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    state = dict(calls=0)

    def busy_then_complete(_address, _p_data, _length, p_status_code):
        state['calls'] += 1
        if state['calls'] <= 1:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_write.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program_max(handle, tuple(range(7)))
    assert transmitted(handle) is None, 'withheld while the integrator is still busy (DD53)'

    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM_MAX response arrives'


def test_program_max_also_leaves_the_mta_unmoved_on_a_failed_write():
    """DD66 shares Xcp_PgmCompleteProgramWrite between PROGRAM and PROGRAM_MAX (Task 3) -- pinned
    thoroughly for PROGRAM above; this is the narrow, PROGRAM_MAX-specific slice: that its own
    handler reaches the SAME shared completion rather than some divergent copy that forgot the
    guard. A following PROGRAM (not PROGRAM_MAX, so the assertion is unambiguous about which
    command's own argument is being read) must land at the SAME address a failed PROGRAM_MAX left
    the MTA at."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x4000)

    def write_failed(_address, _p_data, _length, p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_program_write.side_effect = write_failed

    program_max(handle, tuple(range(7)))
    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0:2] == (0xFE, 0x24), 'setup: ERR_ACCESS_DENIED'
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.xcp_program_write.side_effect = None
    handle.xcp_program_write.reset_mock()

    program(handle, 0x01, data=(0xAB,))

    address, _p_data, _length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x4000, \
        'a failed PROGRAM_MAX write must not have advanced the MTA either'

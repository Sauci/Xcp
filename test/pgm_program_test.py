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


def program_next(handle, elements, data=()):
    """PROGRAM_NEXT (0xCA, Task 4), without pumping Xcp_MainFunction -- mirrors program() above.
    Byte 1 is the remaining element count the master believes the slave still expects (1.1/
    1.6.5.2.5); AG=1 means no alignment byte, so the data begins immediately at byte 2, exactly as
    program() above has it."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xCA, elements) + tuple(data)))


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


def test_program_declaring_more_elements_than_fit_a_single_frame_is_refused_err_out_of_range_without_master_block_mode():
    """Task 3 did not implement master block mode for PROGRAM (design doc title: 'PROGRAM without
    block mode') -- PROGRAM_NEXT, which Task 4 adds, is what a genuine multi-frame block needs.
    Task 4 wires Xcp_Ptr->general->masterBlockModeSupported into this decision (DD63): a declared
    count larger than one CTO frame can carry is refused outright ONLY when master block mode is
    unsupported, mirroring Xcp_DTOCmdCalDownload's own identical choice when ITS OWN
    masterBlockModeSupported is FALSE (Xcp_DataTransferInitialize, source/Xcp.c) --
    test_download_returns_err_out_of_range_when_the_count_exceeds_a_single_packet
    (test/download_test.py) pins the identical condition for that sibling command. At MAX_CTO=8,
    AG=BYTE, a single frame carries at most 6 data bytes (2 header bytes reserved); 7 is one past
    that.

    master_block_mode=False is passed explicitly, unlike Task 3's own version of this test:
    DefaultConfig's own default is True (test/parameter.py), which after Task 4 opens a block
    instead of refusing -- test_program_next_accumulates_a_multi_frame_block_into_one_contiguous_write
    below is what pins THAT behaviour. Without forcing the flag off here, this test would be
    exercising block mode by accident and its own name would no longer describe what it asserts.

    call_count == 0 is the assertion that matters: a handler that copied the 6 bytes it COULD hold
    and called Xcp_ProgramWrite anyway would silently discard the master's 7th byte and report
    success for less than what was asked -- exactly the silent-partial-write class of bug the
    call-count assertion, not the wire code alone, is what catches."""
    handle = pgm_program_handle(master_block_mode=False)
    _active_session_with_mta(handle)

    assert send(handle, (0xD0, 0x07) + tuple(range(7)))[0:2] == (0xFE, 0x22), 'ERR_OUT_OF_RANGE'
    assert handle.xcp_program_write.call_count == 0


def test_program_with_master_block_mode_off_still_succeeds_when_the_count_fits_a_single_frame():
    """Closes a mutation gap in Xcp_DTOCmdPgmProgram's own block-mode-off refusal, whose condition
    is `(frame_elements != number_of_data_elements) && (masterBlockModeSupported == FALSE)`: every
    OTHER test in this suite passing master_block_mode=False also happens to send an OVERSIZED
    count, so deleting the `frame_elements != number_of_data_elements` term (leaving the refusal
    keyed on masterBlockModeSupported alone) would refuse every single PROGRAM whenever block mode
    is off, fitting or not -- and nothing above would notice, since the term's own deletion changes
    nothing for an already-oversized count. A 3-element count, well under the 6-byte single-frame
    capacity at this suite's default MAX_CTO=8, must still succeed with block mode off."""
    handle = pgm_program_handle(master_block_mode=False)
    _active_session_with_mta(handle, address=0x2800)

    program(handle, 0x03, data=(0x11, 0x22, 0x33))
    handle.lib.Xcp_MainFunction()

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x2800
    assert length == 0x03
    assert bytes(p_data[0:length]) == bytes((0x11, 0x22, 0x33))
    assert transmitted(handle)[0] == 0xFF


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
    reports would transmit before the busy integrator ever completes.

    Review, fix round 1, finding 4: an earlier version of this test asserted
    `transmitted(handle) is None` immediately after program_max(), before any Xcp_MainFunction()
    call -- true unconditionally, since Xcp_CanIfRxIndication never transmits regardless of what
    the module did, the exact vacuous shape test_program_next_intermediate_frame_transmits_nothing
    documents avoiding. busy_calls is now 2 (the synchronous attempt inside the handler itself, plus
    one further poll that is STILL busy), so Xcp_MainFunction() actually runs once with a real
    chance to transmit and the EV_CMD_PENDING frame it answers with (DD54) is what proves nothing
    else did -- mirrors test_program_defers_through_the_pending_slot_and_keeps_passing_the_same_bytes
    above exactly."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    state = dict(calls=0)

    def busy_then_complete(_address, _p_data, _length, p_status_code):
        # call 1: the fast path inside the handler itself (program_max() below); call 2: the first
        # Xcp_MainFunction poll; only call 3, the second poll, completes.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_write.side_effect = busy_then_complete
    handle.can_if_transmit.reset_mock()

    program_max(handle, tuple(range(7)))

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFD, 'still busy on the second poll: only EV_CMD_PENDING (DD54)'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
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


# ---------------------------------------------------------------------------------------------
# Task 4: PROGRAM_NEXT and master block mode (DD63).
# ---------------------------------------------------------------------------------------------


def test_program_next_is_refused_err_sequence_before_program_start_succeeds():
    """1.1/1.6.5.1.1 lists PROGRAM_NEXT as the fourth of the four commands refused until
    PROGRAM_START has succeeded, beside PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX above -- this is
    that gate's fourth real user. pgm_program_handle() connects but never sends PROGRAM_START, so
    pgm_state is XCP_PGM_IDLE here by construction, and no block can possibly be open either."""
    handle = pgm_program_handle()

    assert send(handle, (0xCA, 0x01, 0xAA))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'
    assert handle.xcp_program_write.call_count == 0, 'the integrator must not be reached either'


def test_program_next_without_an_open_block_is_refused_err_sequence_expecting_zero():
    """1.1/1.6.5.2.5: PROGRAM_NEXT is only legal following a PROGRAM (or a preceding PROGRAM_NEXT)
    that left a block open. No PROGRAM has been sent here, so Xcp_PgmBlockIsActive() is FALSE
    (Xcp_Internal.pgm_block's own flag, not Xcp_BlockTransferIsActive()/block_transfer -- review,
    fix round 1, finding 1) -- 1.7.3.2.5's own PROGRAM_NEXT row lists ERR_SEQUENCE for this, the
    same code the session gate above answers, and PROGRAM_NEXT's negative response always carries
    the number of elements the slave expects (1.1/1.6.5.2.5) -- 0 here, since no block was ever
    requested at all. Distinguished from the session-gate test above by pgm_state: the session IS
    active here (_active_session_with_mta), so this pins Xcp_DTOCmdPgmProgramNext's OWN
    Xcp_PgmBlockIsActive() check, not the outer pgm_state gate it shares with the other three
    commands."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle)

    assert send(handle, (0xCA, 0x01, 0xAA))[0:3] == (0xFE, 0x29, 0x00), \
        'ERR_SEQUENCE, expecting 0 elements'
    assert handle.xcp_program_write.call_count == 0


def test_program_next_accumulates_a_multi_frame_block_into_one_contiguous_write():
    """DD63: 'PROGRAM opens a block and its payload is copied into Xcp_Internal.pgm_block. Each
    PROGRAM_NEXT appends.' Three frames (6, 6 and 2 elements, at MAX_CTO=8's own 6-byte-per-frame
    ceiling) must reach Xcp_ProgramWrite as ONE call carrying all 14 bytes concatenated in order,
    at the MTA the block opened at -- not the address of whichever frame happened to arrive last.

    Asserts the concatenation itself, not merely a byte count or the final response: a handler
    that let a later frame overwrite earlier ones (keeping only the tail of the block) would still
    answer 0xFF with call_count 1 and even the right LENGTH, and only the actual bytes would catch
    it.

    Mutation (fix round verification): making the copy in Xcp_DTOCmdPgmProgramNext start at index
    0 instead of Xcp_Internal.pgm_block.length -- i.e. each frame overwriting the buffer instead of
    appending to it -- makes the final bytes equal the LAST frame's own 2 bytes rather than all 14,
    which the equality assertion below catches directly."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2000)

    payload = tuple(range(0x01, 0x0F))  # 14 recognisable, distinct bytes: 0x01..0x0E
    handle.can_if_transmit.reset_mock()

    program(handle, 0x0E, data=payload[0:6])           # frame 1 (PROGRAM): 6 of 14, 8 remaining
    program_next(handle, 0x08, data=payload[6:12])      # frame 2 (PROGRAM_NEXT): 6 of 8, 2 remaining
    program_next(handle, 0x02, data=payload[12:14])     # frame 3 (PROGRAM_NEXT): the last 2, completes

    handle.lib.Xcp_MainFunction()

    assert handle.xcp_program_write.call_count == 1, 'once per BLOCK, not once per frame'
    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x2000, 'the MTA the block opened at'
    assert length == 0x0E, 'the true total length of the whole block'
    assert bytes(p_data[0:length]) == bytes(payload), 'the exact concatenation, in order'
    assert transmitted(handle)[0] == 0xFF


def test_program_next_intermediate_frame_transmits_nothing():
    """DD63: 'Intermediate frames answer nothing and complete entirely in receive context ... They
    set *responseExpected = FALSE, copy their bytes, and return -- no callback, no polling, no
    pending slot.' 1.1/1.6.5.1.3: 'The slave device will acknowledge only the last PROGRAM_NEXT
    command packet.'

    Deliberately NOT asserted by transmitted(handle) is None alone right after the frame arrives --
    that is true whatever the module did with the bytes, since Xcp_CanIfRxIndication itself never
    transmits (task brief's own trap). Xcp_MainFunction is pumped twice after the intermediate
    frame and CanIf_Transmit's own call_count is asserted to still be zero, which is what actually
    distinguishes 'correctly withheld' from 'not attempted yet'. Xcp_ProgramWrite's own call_count
    is asserted alongside it: the block is not yet complete (2 of 14 bytes still outstanding), so
    the integrator must not have been reached either. Completing the block afterwards, and getting
    a real response then, is the contrast that proves the module is not simply broken."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2100)

    program(handle, 0x0E, data=tuple(range(0x01, 0x07)))       # frame 1: 6 of 14, 8 remaining
    handle.can_if_transmit.reset_mock()
    handle.xcp_program_write.reset_mock()

    program_next(handle, 0x08, data=tuple(range(0x07, 0x0D)))  # frame 2: 6 of 8, 2 remaining -- NOT last

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 0, \
        'an intermediate PROGRAM_NEXT must transmit nothing, even after Xcp_MainFunction runs'
    assert handle.xcp_program_write.call_count == 0, \
        'the integrator must not be reached until the block completes'

    program_next(handle, 0x02, data=(0x0D, 0x0E))               # frame 3: the last 2, completes
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the completing frame DOES answer, unlike the ones before it'


def test_program_next_short_final_frame_completes_the_block_and_writes_the_true_length():
    """A final PROGRAM_NEXT frame carrying fewer bytes than a full frame's own capacity (1 of a
    possible 6, at MAX_CTO=8) must still complete the block and report the TRUE accumulated
    length (7), not the frame's own physical capacity and not merely the first frame's 6."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2200)

    program(handle, 0x07, data=tuple(range(0x01, 0x07)))  # frame 1: 6 of 7, 1 remaining
    handle.can_if_transmit.reset_mock()

    program_next(handle, 0x01, data=(0x07,))               # short final frame: 1 byte, not 6

    handle.lib.Xcp_MainFunction()

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x2200
    assert length == 0x07, 'the true total length, not the last frames own capacity'
    assert bytes(p_data[0:length]) == bytes(range(0x01, 0x08))
    assert transmitted(handle)[0] == 0xFF


def test_program_next_wrong_element_count_answers_err_sequence_with_the_expected_count():
    """1.1/1.6.5.2.5: 'It contains the remaining number of data elements to transmit. The slave
    device will use this information to detect lost packets. If a sequence error has been
    detected, the error code ERR_SEQUENCE will be returned. The negative response will contain the
    expected number of data elements.' 4 elements remain (10 declared, 6 sent by the opening
    PROGRAM); this PROGRAM_NEXT declares 3 instead. Xcp_FillErrorPacketWithData is the same
    mechanism Xcp_DTOCmdCalDownloadNext already uses for the identical shape of response
    (source/Xcp_Cal.c).

    Asserted on byte 2 itself, not merely on the ERR_SEQUENCE code: a handler that answered
    ERR_SEQUENCE with the WRONG count (the just-received 3, say, instead of the still-expected 4)
    would still pass an assertion that stopped at byte 1."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2300)

    program(handle, 0x0A, data=tuple(range(0x01, 0x07)))  # frame 1: 6 of 10, 4 remaining
    handle.can_if_transmit.reset_mock()

    response = send(handle, (0xCA, 0x03, 0xAA, 0xBB, 0xCC))  # declares 3; 4 are actually expected

    assert response[0:3] == (0xFE, 0x29, 0x04), 'ERR_SEQUENCE, carrying the expected count (4)'
    assert handle.xcp_program_write.call_count == 0, 'a rejected frame must not reach the integrator'


def test_program_next_wrong_element_count_discards_the_block_rather_than_resuming_it():
    """DD63: a block that goes wrong is discarded, not resumed -- 1.7.3.2.5 gives PROGRAM_NEXT the
    pre-action SYNCH+PROGRAM, so the master restarts from its own PROGRAM rather than retrying the
    failed PROGRAM_NEXT. Pinned here by sending a well-formed PROGRAM_NEXT (matching the count the
    aborted block was still expecting) right after the sequence error: were the block still
    considered open, this would look like a valid continuation and be accepted; discarded, it is
    instead just another PROGRAM_NEXT with no block open at all, refused ERR_SEQUENCE expecting 0."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2350)

    program(handle, 0x0A, data=tuple(range(0x01, 0x07)))  # frame 1: 6 of 10, 4 remaining
    assert send(handle, (0xCA, 0x03, 0xAA, 0xBB, 0xCC))[0:2] == (0xFE, 0x29), \
        'setup: wrong count -- aborts the block'
    # PROGRAM_NEXT's own Xcp_CTOErrorMatrix entry carries XCP_INTERNAL_ERR_CMD_BUSY, so this
    # response must be confirmed before the exchange under test, exactly as _active_session_with_mta
    # confirms PROGRAM_START's and SET_MTA's own responses -- otherwise the SECOND PROGRAM_NEXT
    # below is answered ERR_CMD_BUSY (or, before the pending one is even inspected, transmits
    # nothing at all this cycle), not the ERR_SEQUENCE this test means to pin.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert send(handle, (0xCA, 0x04, 0x01, 0x02, 0x03, 0x04))[0:3] == (0xFE, 0x29, 0x00), \
        'the block is gone, not merely paused: this now-well-formed continuation finds nothing open'
    assert handle.xcp_program_write.call_count == 0


def test_program_next_declaring_more_bytes_than_the_frame_actually_carries_answers_err_cmd_syntax():
    """Mirrors PROGRAM's own
    test_program_declaring_more_bytes_than_the_frame_actually_carries_answers_err_cmd_syntax,
    exercised against Xcp_DTOCmdPgmProgramNext's own identical guard (source/Xcp_Pgm.c): without
    it, the handler would copy whatever follows the received PDU into pgm_block, and from there
    into flash. 4 elements remain (10 declared, 6 already sent by the opening PROGRAM); this
    PROGRAM_NEXT correctly DECLARES 4 (matching what is actually expected, so the wrong-count
    branch above is not what answers this) but only actually sends 1 data byte."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2900)

    program(handle, 0x0A, data=tuple(range(0x01, 0x07)))  # frame 1: 6 of 10, 4 remaining
    handle.can_if_transmit.reset_mock()

    assert send(handle, (0xCA, 0x04, 0x11))[0:2] == (0xFE, 0x21), 'ERR_CMD_SYNTAX'
    assert handle.xcp_program_write.call_count == 0

    # DD63: this failed frame discards the block too, exactly as the wrong-count case does above --
    # confirmed the same way, by a well-formed follow-up PROGRAM_NEXT finding nothing open.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert send(handle, (0xCA, 0x04, 0x01, 0x02, 0x03, 0x04))[0:3] == (0xFE, 0x29, 0x00)


def test_program_declaring_a_block_longer_than_the_buffer_answers_err_memory_overflow():
    """DD63: 'A block whose declared length exceeds MAX_BS_PGM x (MAX_CTO - 2) is refused
    ERR_MEMORY_OVERFLOW, which Section 1.7.3.2.5 lists for PROGRAM.' programming_max_block_size=1
    sizes the buffer to MAX(1*(8-2), 8-1) = 7 bytes (source/Xcp_Internal.h); 10 declared elements
    is 3 more than that, so the block must be refused up front, on the OPENING PROGRAM itself,
    before a single PROGRAM_NEXT is ever needed.

    call_count == 0 is what distinguishes this from a handler that accepted the first 6 bytes
    anyway and only discovered the overflow on a later PROGRAM_NEXT -- DD63 requires the refusal
    on the declared total, checked before anything is copied."""
    handle = pgm_program_handle(programming_max_block_size=1, max_cto=8)
    _active_session_with_mta(handle, address=0x2400)

    assert send(handle, (0xD0, 0x0A) + tuple(range(6)))[0:2] == (0xFE, 0x30), 'ERR_MEMORY_OVERFLOW'
    assert handle.xcp_program_write.call_count == 0, 'nothing written'


def test_program_max_inside_an_open_block_is_refused_err_sequence():
    """DD65 (H1): 1.6.5.2.6, 'This command does not support block transfer and it may not be used
    within a block transfer sequence.' Xcp_DTOCmdPgmProgramMax's own Xcp_PgmBlockIsActive() guard
    (source/Xcp_Pgm.c; Xcp_BlockTransferIsActive() before fix round 1, finding 1 -- see the test
    below) existed since Task 3 but had no PROGRAM in the build that could ever leave it TRUE --
    Task 4's own PROGRAM_NEXT is what finally drives it. A block is opened (10 declared, 6 sent, 4
    still outstanding) and PROGRAM_MAX is sent into the middle of it.

    Mutation: deleting (or inverting) the `Xcp_PgmBlockIsActive() == TRUE` branch in
    Xcp_DTOCmdPgmProgramMax falls through to its own length/copy logic and answers 0xFF instead of
    (0xFE, 0x29) -- caught directly below, and confirmed by actually performing this deletion
    (task report)."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2500)

    program(handle, 0x0A, data=tuple(range(0x01, 0x07)))  # opens a block, 4 elements still outstanding
    handle.can_if_transmit.reset_mock()
    handle.xcp_program_write.reset_mock()

    assert send(handle, (0xC9,) + tuple(range(7)))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'
    assert handle.xcp_program_write.call_count == 0, 'the integrator must not be reached either'


def test_confirming_a_response_while_a_program_block_is_open_does_not_leak_slave_memory():
    """Review, fix round 1, finding 1 (critical). Xcp_CanIfTxConfirmation (source/Xcp.c,
    ONGOING_TRANSMIT_TYPE_CTO) treats ANY active Xcp_Internal.block_transfer as a slave block mode
    UPLOAD continuation still owed to the master: once a confirmed response's own
    Xcp_BlockTransferIsActive() reads TRUE, it reads MAX_CTO-1 bytes at the current MTA through
    Xcp_ReadSlaveMemoryU8, transmits them as an unrequested 0xFF frame, advances the MTA by that
    many bytes, and repeats on the next confirmation too.

    The first version of this task populated exactly that shared state for PGM's own, unrelated
    block bookkeeping, on DD63's own advice to reuse it and because Xcp_DTOCmdPgmProgramMax's own
    DD65 guard already read it. Neither reasoning noticed Xcp_CanIfTxConfirmation's own, different
    reader: since a PGM block can stay open across several unrelated command/response exchanges --
    this test's own PROGRAM_MAX, refused mid-block by the test immediately above, or a SET_MTA,
    both of which 1.1/1.6.5.1.1 requires to stay available during a programming sequence --
    confirming THEIR ordinary response also triggered the identical unsolicited-UPLOAD path:
    slave memory disclosed on the wire, the MTA silently moved (breaching DD66), and the session
    left wedged. Reproduced on the branch before this fix (task-4-report.md, 'Fix round 1',
    finding 1).

    Fixed by giving PGM its own, separate pair (Xcp_Internal.pgm_block.requested_elements/
    frame_elements, source/Xcp_Internal.h) that Xcp_CanIfTxConfirmation never reads and
    Xcp_Internal.block_transfer never touches again from this module -- so a PGM block being open
    is now structurally invisible to the confirmation path, the same way it was before this
    sub-project existed.

    Exercises exactly the reproduction above: a block is opened (10 declared, 6 sent, 4 still
    outstanding), PROGRAM_MAX is refused into the middle of it (an ordinary, unrelated response),
    and THAT response is confirmed. No slave memory read, no further transmission, and the MTA
    unmoved -- the last checked by completing the still-open block afterward with the correct
    remaining count and confirming it still lands at the block's own original MTA, proof the
    confirmation above did not silently advance it."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x3000)

    program(handle, 0x0A, data=tuple(range(0x01, 0x07)))  # opens a block, 4 elements still outstanding

    handle.can_if_transmit.reset_mock()
    assert send(handle, (0xC9,) + tuple(range(7)))[0:2] == (0xFE, 0x29), 'setup: PROGRAM_MAX refused'

    handle.can_if_transmit.reset_mock()
    handle.xcp_read_slave_memory_u8.reset_mock()

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert handle.xcp_read_slave_memory_u8.call_count == 0, \
        'confirming an ordinary response must never read slave memory for an unsolicited UPLOAD'
    assert handle.can_if_transmit.call_count == 0, \
        'confirming an ordinary response must not trigger any further, unsolicited transmission'

    # the block itself must still be exactly as it was: completed with the correct remaining count,
    # it must write at the ORIGINAL MTA -- proof the confirmation above did not silently advance it.
    program_next(handle, 0x04, data=(0x07, 0x08, 0x09, 0x0A))
    handle.lib.Xcp_MainFunction()

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x3000, 'the MTA must not have moved'
    assert length == 0x0A
    assert bytes(p_data[0:length]) == bytes(range(0x01, 0x0B))
    assert transmitted(handle)[0] == 0xFF


def test_program_block_of_max_bs_pgm_frames_succeeds():
    """H3: PROGRAM_START's own response advertises programming.max_block_size (8, this suite's
    default) as MAX_BS_PGM, and 1.1/1.6.5.1.3 makes that value, together with MIN_ST_PGM, the bound
    on how many packets a master block mode PROGRAM sequence may contain. At this suite's default
    MAX_CTO=8, AG=BYTE, a single frame carries at most 6 elements, so a block declaring the
    advertised maximum of MAX_BS_PGM(8) frames' worth -- 48 elements -- needs exactly 1 PROGRAM
    plus 7 PROGRAM_NEXT frames, and this is the first test in the suite that sends that many and
    confirms the advertised number is actually achievable end to end, not merely reported."""
    handle = pgm_program_handle()  # defaults: programming_max_block_size=8, max_cto=8
    _active_session_with_mta(handle, address=0x2600)

    total = 8 * (8 - 2)  # MAX_BS_PGM * (MAX_CTO - 2) == 48, exactly 8 frames of 6 bytes each
    payload = tuple(range(total))
    handle.can_if_transmit.reset_mock()

    program(handle, total, data=payload[0:6])
    remaining, offset, frame_count = total - 6, 6, 1
    while remaining > 0:
        chunk = payload[offset:offset + 6]
        program_next(handle, remaining, data=chunk)
        remaining -= len(chunk)
        offset += len(chunk)
        frame_count += 1

    assert frame_count == 8, 'setup: exactly MAX_BS_PGM frames must have been sent'

    handle.lib.Xcp_MainFunction()

    assert handle.xcp_program_write.call_count == 1
    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x2600
    assert length == total
    assert bytes(p_data[0:length]) == bytes(payload)
    assert transmitted(handle)[0] == 0xFF, \
        'a block of exactly the advertised MAX_BS_PGM frames must succeed, not overflow'


def test_program_next_defers_through_the_pending_slot_and_keeps_passing_the_whole_block():
    """The completing PROGRAM_NEXT frame defers through the identical pending-command machinery
    PROGRAM's own test_program_defers_through_the_pending_slot_and_keeps_passing_the_same_bytes
    pins, exercised through the command that adds a NEW case to Xcp_PgmPollPendingCommand's and
    Xcp_PgmCompletePendingCommand's own switches (source/Xcp_Pgm.c). A module that stored the wrong
    PID in Xcp_Internal.pending_command, or that failed to add PROGRAM_NEXT's own case to either
    switch, would either dispatch to the wrong completion function on the next poll or fall into
    the `default` branch, which returns E_OK immediately without ever presenting the accumulated
    bytes again -- caught here by asserting the FULL 14-byte block is still what the LAST poll
    presents to the integrator, not just that a response eventually arrives.

    Review, fix round 1, finding 4: an earlier version of this test asserted
    `transmitted(handle) is None` immediately after the completing program_next(), before any
    Xcp_MainFunction() call -- true unconditionally, since Xcp_CanIfRxIndication never transmits
    regardless of what the module did, the exact vacuous shape
    test_program_next_intermediate_frame_transmits_nothing (230 lines above at the time of review)
    documents avoiding. busy_calls is now 2, so the first Xcp_MainFunction() poll is still busy and
    answers a real, checkable frame (EV_CMD_PENDING, DD54) instead of nothing at all -- mirrors
    test_program_max_defers_through_the_pending_slot's own identical fix above."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x2700)

    state = dict(calls=0)

    def busy_then_complete(_address, _p_data, _length, p_status_code):
        # call 1: the fast path inside the handler itself (the completing program_next() below);
        # call 2: the first Xcp_MainFunction poll; only call 3, the second poll, completes.
        state['calls'] += 1
        if state['calls'] <= 2:
            return handle.define('E_NOT_OK')
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_program_write.side_effect = busy_then_complete

    payload = tuple(range(0x01, 0x0F))
    program(handle, 0x0E, data=payload[0:6])
    program_next(handle, 0x08, data=payload[6:12])
    handle.can_if_transmit.reset_mock()

    program_next(handle, 0x02, data=payload[12:14])  # completes; first Xcp_ProgramWrite call is busy

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] == 0xFD, 'still busy on the second poll: only EV_CMD_PENDING (DD54)'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # third call completes

    assert transmitted(handle)[0] == 0xFF, 'the deferred PROGRAM_NEXT response arrives'

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args_list[-1][0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x2700
    assert length == 0x0E
    assert bytes(p_data[0:length]) == bytes(payload), \
        'the same, complete, concatenated block must still be presented on the completing poll'


def test_program_a_second_block_does_not_accumulate_onto_the_first():
    """Companion to
    test_a_fresh_block_works_end_to_end_after_reinit_even_though_the_previous_one_was_left_half_open
    below, and the test that actually catches the mutation that one's own docstring first claimed
    to (task report corrects that claim; this test is the fix). Two ordinary, independent
    single-frame PROGRAM commands, 3 bytes then 2, in the SAME session -- no Xcp_Init between them.
    Xcp_DTOCmdPgmProgram's opening frame sets Xcp_Internal.pgm_block.length by direct assignment,
    not by accumulating onto whatever it already held (source/Xcp_Pgm.c), so the second block's own
    write must present length 2, not 5.

    Mutation: changing that assignment from `pgm_block.length = frame_length` to
    `pgm_block.length += frame_length` makes the second call's own length 3+2=5 instead of 2,
    caught directly below -- confirmed by actually performing this mutation (task report). The SAME
    mutation does NOT make the test below fail: an Xcp_Init sits between that test's two PROGRAM
    calls, and its OWN (unmutated) `pgm_block.length = 0x0000u` already re-zeroes the field before
    the mutated line ever runs again, masking it completely. This test has no Xcp_Init in the way,
    so it is the one that actually exercises PROGRAM's own opening-frame assignment twice in a
    row."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x1500)

    program(handle, 0x03, data=(0x11, 0x22, 0x33))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.xcp_program_write.reset_mock()

    program(handle, 0x02, data=(0x44, 0x55))
    handle.lib.Xcp_MainFunction()

    _address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert length == 0x02, 'must not have accumulated the first blocks own 3 bytes on top'
    assert bytes(p_data[0:length]) == bytes((0x44, 0x55))


def test_a_fresh_block_works_end_to_end_after_reinit_even_though_the_previous_one_was_left_half_open():
    """H2, renamed from test_xcp_init_clears_a_half_open_program_block (review, fix round 1,
    finding 3): the old name claimed this test pins Xcp_Init's own clearing of
    Xcp_Internal.pgm_block.length, and it cannot -- a future reader deleting that line would still
    see this test green and mistake it for coverage. What it actually pins, honestly: a fresh
    session's first block still works correctly end to end, after a reinit that happened to catch a
    PREVIOUS block half-open. Task 1 added pgm_block.length's own clearing to Xcp_Init and
    disclosed that nothing exercised it, because nothing read the field across sessions before
    block mode existed to make PROGRAM_NEXT's own append depend on where a previous block left off.

    A block is opened and left half-open (7 declared, only the first 6 sent -- 1 element still
    outstanding, no completing PROGRAM_NEXT ever sent). Xcp_Init runs, the module reconnects and
    opens a brand new session, and a FRESH single-frame block is programmed. The integrator must
    receive exactly that fresh block's own 2 bytes at its own new MTA -- not the earlier session's
    address, length, or leftover bytes.

    Measured, not assumed (task report, confirmed independently by review): this test passes
    whether or not Xcp_Init's own clearing of pgm_block.length actually runs, and stays passing
    even with that line deleted outright. Xcp_DTOCmdPgmProgram's opening frame sets
    Xcp_Internal.pgm_block.length by direct assignment rather than by accumulating onto whatever it
    already held, so a fresh PROGRAM always re-establishes the block from index 0 itself regardless
    of what Xcp_Init did or did not clear first -- Xcp_Init's own clearing is therefore not
    independently load-bearing THROUGH this particular path, and this test does not prove it is.
    What IS still real, and still caught by a test, is the underlying property Xcp_Init's clear
    defends alongside PROGRAM's own assignment: test_program_a_second_block_does_not_accumulate_onto_the_first
    above pins the identical 'a fresh block must not inherit an earlier one's bytes' invariant with
    no Xcp_Init in the way, and IS killed by mutating PROGRAM's own opening-frame assignment from
    `=` to `+=` -- see its own docstring. Xcp_Init's clear is kept regardless, as the same kind of
    documented, currently-unreachable defence in depth Xcp_Internal.h already keeps for the
    buffer-overflow guards below Task 3's own PROGRAM_MAX: a second, independent line protecting
    the same invariant is not dead code merely because one test cannot distinguish its presence
    from its absence."""
    handle = pgm_program_handle()
    _active_session_with_mta(handle, address=0x7000)

    program(handle, 0x07, data=(0x11, 0x22, 0x33, 0x44, 0x55, 0x66))  # half-open: 1 element outstanding

    handle.lib.Xcp_Init(handle.ffi.cast('const Xcp_Type *', handle.config.lib.Xcp))

    connect(handle)
    _active_session_with_mta(handle, address=0x9000)
    handle.xcp_program_write.reset_mock()
    handle.can_if_transmit.reset_mock()

    program(handle, 0x02, data=(0xAA, 0xBB))
    handle.lib.Xcp_MainFunction()

    address, p_data, length, _p_status_code = handle.xcp_program_write.call_args[0]
    assert int(handle.ffi.cast('uintptr_t', address)) == 0x9000
    assert length == 0x02, 'must not have inherited the half-open blocks own declared/remaining length'
    assert bytes(p_data[0:length]) == bytes((0xAA, 0xBB)), 'must not have inherited its leftover bytes'
    assert transmitted(handle)[0] == 0xFF

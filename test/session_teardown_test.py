#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD74 (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md) -- a pre-existing
defect in shipped code, independent of any feature branch this repository carries: CONNECT does
not tear down the whole session. XCP part 2 - Protocol Layer Specification 1.1/1.6.1.1.1 makes
CONNECT the start of a session, and Xcp_CTOCmdStdConnect's own comment (source/Xcp_Std.c) already
argues that no state of the previous session may survive into the next -- it was written when an
earlier task made CONNECT clear pgm_state for exactly this reason. Until this task's own fix,
CONNECT cleared pgm_state and called Xcp_PgmBlockAbort(), and nothing else. Four more pieces of
session state survived a reconnect:

- An open block transfer (Xcp_Internal.block_transfer): a slave block mode (UPLOAD) transfer left
  mid-flight answers a later, unrelated transmission confirmation by continuing to read and
  transmit the PREVIOUS session's memory into the new one.
- A partial key (Xcp_Internal.key_master/key_slave): an UNLOCK that announces N bytes and delivers
  fewer, left standing, lets a new session's UNLOCK complete it with only the still-missing bytes.
- The MTA (Xcp_Internal.memory_transfer): a DOWNLOAD with no SET_MTA in the new session writes at
  the previous session's address.
- A half-fetched seed (Xcp_Internal.seed): a GET_SEED(mode=0) whose continuation frames were never
  requested lets a new session's very first GET_SEED(mode=1) collect the tail of the previous
  session's seed. Not among DD74's own three measured consequences -- the fix resets the seed
  anyway, and the reset turns out to be load-bearing; see below.

test_an_open_block_transfer_does_not_survive_a_reconnect, test_a_partial_key_does_not_survive_a_
reconnect, test_the_mta_does_not_survive_a_reconnect and
test_a_partially_transmitted_seed_does_not_survive_a_reconnect below are the direct reproductions,
one per item, each across a real DISCONNECT/CONNECT. test_a_normal_session_still_works_end_to_end_
after_a_reconnect is the neighbour every one of the four resets endangers: a teardown that clears
too much breaks exactly the ordinary session it exists to protect.

The seed item is the one DD74's own task reported as untestable -- "the seed reset has no dedicated
test, traced by mutation to nothing depending on it, because every legitimate GET_SEED(mode=0)
overwrites the field unconditionally" (task-4-report.md). True of mode=0; GET_SEED(mode=1) is the
other reader and overwrites nothing. Added by the acceptance pass that re-derived it rather than
accepting the disclosure (task-6-report.md).

Two upstream tasks change what "surviving" actually looks like on this branch, and both are
accounted for rather than assumed:

- The block transfer test is deliberately NOT the design doc's own pre-measurement scenario. An
  earlier task narrowed Xcp_CanIfTxConfirmation's own confirmation predicate (source/Xcp.c) from
  "any open block" to "an open SLAVE block mode transfer specifically" (Xcp_SlaveBlockTransferIsActive,
  fixing a memory disclosure of its own) -- so a left-open DOWNLOAD (master block mode) no longer
  reproduces anything here, and this test uses UPLOAD (slave block mode) instead, matching what the
  narrowed predicate still lets through today.
- The key and MTA tests, and the fix's own seed reset, are written against total_length's CURRENT
  meaning: an earlier task corrected Xcp_Internal.seed.total_length to mean the seed's own length
  (previously it meant "bytes still to send" and was zeroed the instant the last chunk went out,
  which is also why Xcp_CalcKey used to be called with seedLength=0 for every seed -- a separate,
  already-fixed defect). Nothing below depends on the pre-fix meaning.

Xcp_Internal is not reachable from this CFFI harness (interface/Xcp.h does not include
Xcp_Internal.h), so every assertion below observes through the wire -- a transmitted response, a
recorded slave-memory read, or a captured slave-memory write -- never through Xcp_Internal
directly, following test/clear_daq_list_test.py's own precedent
(test_clear_daq_list_invalidates_a_pointer_aimed_at_it, lines 80-92).

Citation note: the brief describes the MTA as left "undefined" by XCP part 2 1.1/1.6.2 until
SET_MTA. Checked against both the local 1.1 PDF's own OCR text and the 1.0 PDF (pdftotext
-layout, per this task's own instructions -- the local 1.1 PDF extracts as scrambled text
directly): neither document uses the word "undefined" anywhere in connection with the MTA. The
only "undefined" in either document describes the DAQ pointer (1.1/1.6.4.1.1.2), a different
field. What IS verifiable: SET_MTA's own entry (1.1/1.6.1.2.6) is listed "Category: Standard,
optional", and neither it nor DOWNLOAD's entry (1.1/1.6.2.1.1) states what the MTA holds before
the first SET_MTA of a session. The fix's own comment in source/Xcp_Std.c states this precisely
rather than repeating the brief's "undefined" wording as a verified quote."""

import math

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes
from .block_transfer_disclosure_test import poison_reads
from .seed_key_test import get_seed_key_slices, get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .seed_key_defects_test import exchange

CAL_PAG = 0x01
PGM = 0x10
GET_STATUS = (0xFD,)


def disconnect(handle):
    """A real DISCONNECT, expected to succeed cleanly (nothing outstanding). Mirrors exchange()'s
    own shape (reset, send, confirm exactly one transmission, return it, confirm) -- deliberately
    NOT reused from seed_key_defects_test.py, since this file's own item 1 needs a DISCONNECT that
    is refused instead, and a shared helper that always asserts success would not fit both."""
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 1, 'DISCONNECT must be answered when nothing is outstanding'
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return response


def set_mta_with_extension(handle, address, extension, byte_order='LITTLE_ENDIAN'):
    """download_test.set_mta always sends address extension 0 -- fine for every test that only
    cares about the address half of the MTA, but DD75 (this file's own last three tests below) is
    specifically about the extension half, so this needs its own SET_MTA that can set a non-zero
    one. Mirrors disconnect()'s own shape (reset, send, confirm exactly one transmission, return
    it, confirm) rather than download_test.set_mta's, since that one does not return a response at
    all and every caller below needs to pin that SET_MTA itself actually succeeded."""
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, extension) + tuple(u32_to_array(address, byte_order))))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 1, 'SET_MTA must be answered when nothing is outstanding'
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:1])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return response


def capture_extensions(handle):
    """Records the (address, extension) pair of every AG=BYTE slave-memory read as plain
    integers -- address is cast, never dereferenced, because this double is also used where the
    MTA is a fabricated address (SET_MTA(0xDEADBEEF) with no GET_ID) that this process has no real
    memory backing for; dereferencing it the way test/get_id_test.py's own double does would
    segfault. Matches poison_reads' own address-as-integer convention
    (block_transfer_disclosure_test.py), extended with the extension parameter every existing
    read_slave_memory double in this suite names `_extension` and drops -- Trap 11, and this
    defect's own history (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md,
    DD75: 'Nothing caught it because the existing test doubles ignore the parameter', said there of
    DD73 but equally true here -- this is the one double in the suite that actually looks at it)."""
    reads = list()

    def read_slave_memory(p_address, extension, p_buffer):
        reads.append((int(handle.ffi.cast('uint32_t', p_address)), extension))
        p_buffer[0] = 0x00

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    return reads


def test_an_open_block_transfer_does_not_survive_a_reconnect():
    """DD74, item 1. UPLOAD(10) at MAX_CTO=8/AG=BYTE (capacity (8-1)/1 = 7 elements/frame) opens a
    slave block mode transfer and immediately sends its first frame (7 elements) as the UPLOAD
    response itself -- 3 elements still outstanding. The master that sent this vanishes: it never
    confirms that frame, which is what leaves the transfer genuinely open rather than merely
    started (Xcp_Internal.block_transfer.requested_elements stays nonzero only for as long as a
    frame remains unconfirmed or unfinished; once acknowledged, either more is queued and sent
    immediately -- source/Xcp.c's own "confirmations chain" behaviour, block_transfer_disclosure_
    test.py -- or the transfer is simply over, so there is no quiescent-yet-open state for this
    module's own UPLOAD to be caught in other than exactly this one).

    Both DISCONNECT and CONNECT are dispatched (real commands, real state transitions) while that
    one frame is still outstanding, and neither response reaches the wire for the identical reason
    -- confirmed directly below rather than assumed, since a wrong mental model of this mechanism
    would otherwise surface three steps later as a confusing, hard-to-place failure instead of
    here. DISCONNECT's own Xcp_CTOErrorMatrix entry (source/Xcp.c) carries
    XCP_INTERNAL_ERR_CMD_BUSY, so it is refused outright; CONNECT's is 0x00u (no gate at all,
    Xcp_Std.c's own comment: "its Xcp_CTOErrorMatrix row is 0x00u"), so it dispatches and
    overwrites the shared response buffer with the CONNECT response -- but
    Xcp_Internal.ongoing_transmit_type (source/Xcp.c) still names the original, unconfirmed UPLOAD
    frame as in flight, so Xcp_StartNextTransmission hands neither the refusal nor the CONNECT
    response to CanIf_Transmit. This is this task's own brief, almost verbatim: "the CONNECT
    response is overwritten and never transmitted."

    Only then does the CAN driver confirm the one transmission it actually has outstanding -- the
    ORIGINAL, session 1 UPLOAD frame. On unfixed code nothing between the two commands above
    touched the block, so the module still believes it owes the master the rest of session 1's
    transfer, and continues it: Xcp_SlaveBlockTransferIsActive() (source/Xcp.c) reads
    block_transfer.requested_elements and .slave_block_mode exactly as session 1 left them, reads
    3 more bytes of session 1's memory at session 1's own MTA, and transmits them into session 2,
    unsolicited -- DD70's disclosure, reopened across a reconnect, streaming the previous session's
    memory into the new one exactly as this task's own brief names.

    Measured against unfixed code (task-4-report.md): 3 reads, 1 unsolicited transmission."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   slave_block_mode=True,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x1000)
    reads = poison_reads(handle)

    # Session 1: UPLOAD(10) opens the block and sends its first (7-element) frame as the UPLOAD
    # response. Never confirmed -- the master vanishes here, mid-transfer.
    handle.can_if_transmit.reset_mock()
    reads.clear()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 10)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1, 'the first frame of the UPLOAD must be sent'
    assert len(reads) == 7, 'the first frame must carry all 7 elements that fit at MAX_CTO=8/AG=BYTE'

    # A real master tries the polite way out first.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 0, (
        'setup: a transmission must still be outstanding here for DISCONNECT to be refused '
        'ERR_CMD_BUSY and, in turn, for its own refusal to also not reach the wire -- if this '
        'fails, the scenario below is not the one this test claims to build')

    # ...and, getting nothing back, reconnects instead.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 0, (
        'setup: CONNECT\'s own response must likewise still be sitting unsent behind the '
        'original outstanding frame -- this task\'s own brief names exactly this')

    # The CAN driver finally confirms the one transmission that was ever actually handed to it.
    reads.clear()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert reads == [], (
        'CONNECT must end the block transfer left open by the previous session -- confirming its '
        'last outstanding frame read {} more byte(s) of session 1\'s memory ({}) into session 2'.format(
                len(reads), reads))
    assert handle.can_if_transmit.call_count == 0, (
        'CONNECT must end the block transfer left open by the previous session -- confirming its '
        'last outstanding frame transmitted {} further, unsolicited frame(s) into session 2'.format(
                handle.can_if_transmit.call_count))

    # And the module must still be alive and answering normally afterward, not merely silent
    # because something upstream is wedged.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(GET_STATUS))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_a_partial_key_does_not_survive_a_reconnect():
    """DD74, item 2. Session 1 requests a seed for CAL_PAG and announces an 8-byte key, but its
    own UNLOCK frame -- at the default MAX_CTO=8, at most 6 key bytes fit in one frame -- can only
    ever deliver 6 of them; the master vanishes there, 2 bytes short.

    Xcp_DTOCmdStdUnlock (source/Xcp_Std.c) reads key_master.total_length == 0 as "no transfer in
    progress, this frame's own length byte starts a new one" -- so if CONNECT leaves the stale 8
    standing, session 2's own 2-byte UNLOCK is read as the CONTINUATION of session 1's transfer
    (2 <= 8 - 6) rather than as a new, too-short one, and completes it using 6 bytes session 2
    never supplied.

    The key configured for this test (Xcp_CalcKey's own double below) is 8 bytes, matching what
    session 1 announced -- deliberately, not an arbitrary choice: it is what makes the two
    interpretations diverge observably. Xcp_CheckMasterSlaveKeyMatch (source/Xcp_Std.c) refuses
    outright on a length mismatch before ever comparing content
    (`if (slaveKeyLength == masterKeyLength) {...} else { result = E_NOT_OK; }`), so a correctly
    reset session 2 -- reading the 2-byte request as announcing a fresh, 2-byte key -- can never
    match an 8-byte configured key no matter its content, and must refuse; only the stale-total-
    length reading can complete an 8-byte comparison at all, and this test's key content (all
    0xAA, both session's real bytes) is chosen so that reading succeeds whenever it is reached, to
    isolate the length/indexing defect this item actually is from any question of byte content.

    Measured against unfixed code (task-4-report.md): the final UNLOCK grants CAL_PAG, matching
    this task's own brief ("grants CAL_PAG") almost verbatim."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
    connect(handle)

    key = [0xAA] * 8
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, key)

    # Session 1: GET_SEED, then an UNLOCK announcing all 8 bytes of the key but delivering only
    # the 6 that fit in one frame at MAX_CTO=8. The master vanishes here.
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, [0x11, 0x22])
    first_get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG))
    assert first_get_seed_response[0:2] == (0xFF, 0x02)

    partial_unlock_response = exchange(handle, (0xF7, len(key)) + tuple(key[0:6]))
    assert partial_unlock_response[0:2] == (0xFF, 0x00), (
        'setup: the first, partial UNLOCK frame must itself be accepted as "more expected" -- '
        '{} -- or the scenario below is not the one this test claims to build'.format(
                partial_unlock_response))

    disconnect(handle)
    connect(handle)

    # Session 2's own GET_SEED -- required both to satisfy Xcp_DTOCmdStdUnlock's own
    # last_pid-in-{GET_SEED,UNLOCK} admission gate (source/Xcp_Std.c) and to match this task's own
    # brief's sequence ("After DISCONNECT, CONNECT and GET_SEED, an UNLOCK carrying 2 bytes...").
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, [0x33, 0x44])
    second_get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG))
    assert second_get_seed_response[0:2] == (0xFF, 0x02)

    # Session 2 supplies only the 2 bytes a FRESH, from-scratch key of length 2 would need -- not
    # the 8 session 1's still-open transfer actually announced, and not the 6 bytes session 1
    # already delivered, which session 2 never saw.
    final_unlock_response = exchange(handle, (0xF7, 0x02) + tuple(key[6:8]))

    assert final_unlock_response[0:2] == (0xFE, 0x25), (
        'final UNLOCK answered {} -- expected (0xFE, 0x25) ERR_ACCESS_LOCKED: a fresh 2-byte key '
        'can never match the 8-byte key this test configures (Xcp_CheckMasterSlaveKeyMatch '
        'refuses on length alone), so a match here means session 2\'s 2 bytes completed session '
        '1\'s still-open 8-byte transfer instead of starting a new one of their own -- the '
        'previous session\'s partial key survived the reconnect (GET_SEED: {}, UNLOCK: {})'.format(
                final_unlock_response, second_get_seed_response, final_unlock_response))


def test_the_mta_does_not_survive_a_reconnect():
    """DD74, item 3. Session 1 points the MTA at 0xDEADBEEF and never sends another SET_MTA. If
    CONNECT leaves that address standing, a DOWNLOAD in the new session -- with no SET_MTA of its
    own -- writes through it, at an address that address belongs to the previous session, not
    this one.

    Measured against unfixed code (task-4-report.md): the DOWNLOAD below writes at 0xDEADBEEF."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=False))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)
    written = capture_writes(handle, 1)

    assert disconnect(handle)[0] == 0xFF, 'setup: DISCONNECT must succeed cleanly here'
    connect(handle)

    # Session 2, no SET_MTA at all.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x01, 0x11)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF, (
        'setup: DOWNLOAD must still be dispatched even with no SET_MTA in this session -- '
        '1.1/1.6.1.2.6 lists SET_MTA "Standard, optional", so a master that omits it is not '
        'refused by this module for that reason alone')
    assert written == [(0x00000000, 0x11)], (
        'DOWNLOAD with no SET_MTA in the new session wrote {} -- expected a write at address 0 '
        '(this module\'s own reset MTA), not at session 1\'s own address 0x{:08X}'.format(
                written, 0xDEADBEEF))


def test_a_partially_transmitted_seed_does_not_survive_a_reconnect():
    """DD74's fourth reset -- the seed -- which the task that made it reported as having no
    dedicated test, "traced by mutation to nothing depending on it, because every legitimate
    GET_SEED(mode=0) overwrites the field unconditionally" (task-4-report.md). That reasoning
    holds only for mode=0, which does indeed reset seed.total_length/current_index before doing
    anything else. GET_SEED(mode=1) is the OTHER reader, and it does not overwrite either
    field: it reads them. So the reset IS observable, and this is the test.

    XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.4 splits a seed too long for one frame
    across a GET_SEED(mode=0) followed by GET_SEED(mode=1) continuations, and makes a mode=1
    arriving without a preceding mode=0 an ERR_SEQUENCE. Xcp_DTOCmdStdGetSeed (source/Xcp_Std.c)
    implements that gate as `if (Xcp_Internal.seed.total_length != 0x00u)` -- "is a seed currently
    held". Session 1 here asks for a 10-byte seed at MAX_CTO=8, receives the 6 bytes that fit in
    one frame, and vanishes without ever asking for the remaining 4. Without CONNECT's own reset
    of that field, session 2's very first command can be a GET_SEED(mode=1) that satisfies the
    gate on session 1's leftovers and is answered with the tail of the PREVIOUS session's seed.

    Measured on this branch with only the two `Xcp_Internal.seed.*` lines of
    Xcp_CTOCmdStdConnect's DD74 block removed, everything else fixed: the continuation below is
    answered (0xFF, 0x04, 0x77, 0x88, 0x99, 0xAA) -- session 1's remaining seed bytes, in
    session 2. With the reset in place it is (0xFE, 0x29) ERR_SEQUENCE, as it is for any other
    master that never asked for a seed at all.

    DD73 did not open this route. That task stopped total_length being zeroed once GET_SEED's
    final chunk goes out -- but this seed's final chunk is exactly what never goes out, so the
    field was already left non-zero here on pre-DD73 code too. The route is pre-existing, like
    every other item in this file."""
    max_cto = 8
    seed = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA]

    slices = get_seed_key_slices(seed, max_cto=max_cto)
    # The whole scenario is "a seed that one frame cannot carry, left half-fetched", so a
    # single-frame seed would make this test pin nothing at all.
    assert len(slices) > 1, 'setup: this seed must not fit in one GET_SEED frame'
    withheld = seed[len(slices[0]):]

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto))
    connect(handle)
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)

    first_frame = exchange(handle, (0xF8, 0x00, CAL_PAG), length=max_cto)
    assert first_frame[0:2] == (0xFF, len(seed)), (
        'setup: GET_SEED(mode=0) answered {}, expected (0xFF, {}) -- the whole seed still to '
        'come'.format(first_frame, len(seed)))
    assert list(first_frame[2:2 + len(slices[0])]) == slices[0], (
        'setup: GET_SEED(mode=0) carried {}, expected the seed\'s first {} bytes {} -- without '
        'this the "half-fetched" state below is not the one this test claims to build'.format(
                list(first_frame[2:2 + len(slices[0])]), len(slices[0]), slices[0]))

    # Session 1 ends here, with `withheld` never requested and never transmitted.
    assert disconnect(handle)[0] == 0xFF, 'setup: DISCONNECT must succeed cleanly here'
    connect(handle)

    continuation = exchange(handle, (0xF8, 0x01, CAL_PAG), length=max_cto)

    assert continuation[0:2] == (0xFE, 0x29), (
        'GET_SEED(mode=1) as session 2\'s first command answered {} -- expected (0xFE, 0x29) '
        'ERR_SEQUENCE, since session 2 has never sent a GET_SEED(mode=0) of its own. Session 1 '
        'withheld {}, and a positive answer here means CONNECT left seed.total_length standing '
        'for this new session to continue against'.format(continuation, withheld))


def test_a_normal_session_still_works_end_to_end_after_a_reconnect():
    """The neighbour every one of the four resets above endangers, and DD74's own brief names as
    the most likely way to get this task wrong: a teardown that clears too much breaks exactly the
    ordinary session it exists to protect. CONNECT, SET_MTA, DOWNLOAD, GET_SEED, UNLOCK -- a
    complete, legitimate sequence, run entirely in the SECOND of two sessions so that every one of
    this task's own resets has already run at least once before any of these commands does.

    DD78 configures PGM as protected and points the GET_SEED/UNLOCK round at PGM, so that UNLOCK's
    own byte 1 -- the Current Resource Protection Mask of 1.0/1.6.1.1.3, 1 = still protected --
    measures the grant rather than reading 0x00 on a build with nothing to protect. PGM rather than
    CAL_PAG because DOWNLOAD above is MASK_CAL_PAG (Xcp_PIDToCmdGroupTable, source/Xcp.c) and is
    deliberately sent BEFORE the unlock: protecting CAL_PAG would make it answer ERR_ACCESS_LOCKED
    and turn this test into a protection test instead of the end-to-end session it is. No
    PGM-group command is sent here, so the flag is inert apart from the mask -- which is the point.

    What the mask here does NOT show is that Xcp_CTOCmdStdConnect's own re-seed of it
    (source/Xcp_Std.c) ran: the first session unlocks nothing, so locked_resource holds PGM's bit
    from Xcp_Init onward and every assertion below reads the same with that re-seed deleted. The
    re-seed is pinned elsewhere, by
    test/seed_key_lifetime_test.py::test_an_unlock_does_not_survive_a_reconnect, which unlocks in
    the first session and requires the second to refuse the protected command again."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8,
                                   resource_protection_programming=True))
    connect(handle)
    disconnect(handle)
    connect(handle)

    set_mta(handle, 0xC0FFEE)
    written = capture_writes(handle, 1)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x02, 0x11, 0x22)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF, 'DOWNLOAD must still succeed'
    assert written == [(0xC0FFEE, 0x11), (0xC0FFEF, 0x22)], (
        'DOWNLOAD must still write the payload it was just sent, at the address this session\'s '
        'own SET_MTA just set -- got {}'.format(written))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    key = [0x77, 0x88]
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, key)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, key)

    get_seed_response = exchange(handle, (0xF8, 0x00, PGM))
    assert get_seed_response[0:2] == (0xFF, len(key)), 'GET_SEED must still succeed'

    unlock_response = exchange(handle, (0xF7, len(key), *key))
    assert unlock_response[0:2] == (0xFF, 0x00), (
        'a legitimate GET_SEED/UNLOCK sequence must still grant the resource it requested after '
        'a reconnect -- PGM is this build\'s only protected group, so an empty protection mask is '
        'what a grant looks like; got {}'.format(unlock_response))


def test_get_id_does_not_leak_the_previous_commands_address_extension():
    """DD75 (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md) -- a
    pre-existing defect in shipped code, independent of any feature branch this repository
    carries, and independent of DD74 above despite sharing this file: DD74 is CONNECT leaving
    session state standing across a reconnect; this is GET_ID leaving part of the MTA standing
    across the very next command, in the SAME session, no CONNECT involved anywhere in this test.

    Xcp_DTOCmdStdGetId (source/Xcp_Std.c) writes memory_transfer.address to point the MTA at the
    identification string it is about to publish, but leaves .extension untouched -- so a
    following UPLOAD (Xcp_BlockTransferReadSlaveMemory, source/Xcp.c) reads that string through
    whatever extension the PREVIOUS command last set, not through the identification's own.

    XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 (1.0/1.6.1.2.2, identical wording,
    verified against both the local 1.1 PDF's own OCR text and the 1.0 PDF via `pdftotext
    -layout`) has GET_ID, mode 0, "set the Memory Transfer Address (MTA) to the location from
    which the master device may upload the requested identification" -- and 1.1/1.6.1.2.6
    (1.0/1.6.1.2.6, same wording) defines the MTA itself as one complete pointer, "32Bit address +
    8Bit extension", not an address alone. Xcp_DTOCmdDaqGetDaqEventInfo
    (source/Xcp_Daq.c:1424-1425) shows the intended contract: it sets both members when it points
    the MTA at its own plain, module-owned string (an event channel's name) for a following
    UPLOAD.

    SET_MTA(extension=7) first, matching this defect's own measured reproduction, and deliberately
    NOT the fixed value: 7 is the top of this suite's own address_extensions range
    (test/parameter.py, range(8)) and the identification's own correct extension is this task's
    own fix, 0x00u, the bottom of it -- so a test that failed to observe the swap would still show
    7 leaking through rather than 0 by some unrelated coincidence.

    Measured against unfixed code (task-5-report.md): UPLOAD(3) reads the identification through
    extension 7 -- SET_MTA's own leftover -- for all three elements, not through 0."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)

    assert set_mta_with_extension(handle, 0xDEADBEEF, 0x07)[0] == 0xFF, (
        'setup: SET_MTA must succeed here, or the leftover extension this test measures was '
        'never actually set in the first place')

    get_id_response = exchange(handle, (0xFA, 0x00), length=2)
    assert get_id_response == (0xFF, 0x00), (
        'setup: GET_ID must answer (PID, Mode) = (0xFF, 0x00) -- got {} -- meaning "the '
        'identification is available via the MTA", or the UPLOAD below would not be reading '
        'through the pointer GET_ID is supposed to have just set'.format(get_id_response))

    reads = capture_extensions(handle)
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x03)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 1, 'UPLOAD must be answered'
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    observed_extensions = [extension for _address, extension in reads]
    assert observed_extensions == [0x00, 0x00, 0x00], (
        'UPLOAD read the identification through extension(s) {} -- expected [0, 0, 0] (this '
        "module's own convention for a plain, non-segmented descriptive pointer -- see this "
        "task's own fix comment at Xcp_DTOCmdStdGetId, source/Xcp_Std.c). Getting 7 back means "
        "GET_ID left memory_transfer.extension holding SET_MTA's own leftover value instead of "
        'setting it alongside the address it does write -- exactly DD75'.format(observed_extensions))


def test_get_id_followed_by_upload_still_returns_the_correct_identification_content():
    """DD75's own neighbour, named explicitly by this task's own brief: GET_ID followed by UPLOAD
    must still return the identification string itself correctly. The fix adds an extension
    assignment immediately beside the address assignment Xcp_DTOCmdStdGetId already had (source/
    Xcp_Std.c) -- close enough in the source that a slip (writing to the wrong member, or
    clobbering the address while adding the extension) would land right there and would not be
    caught by test_get_id_does_not_leak_the_previous_commands_address_extension above, which never
    looks at what UPLOAD actually returns.

    SET_MTA(extension=7) first, matching the scenario above rather than a session whose MTA was
    never touched, so this exercises the identical control flow the fix touches.

    identification is deliberately a string this test chooses itself, not DefaultConfig's own
    default (test/parameter.py) -- decoupled from that default so a future change to it could not
    make this test pass by coincidence.

    Content is read back the same way test/get_id_test.py's own
    test_get_id_returns_identification_through_mta_when_mode_is_0 does: by dereferencing the real
    address each read names, which is safe here specifically because GET_ID has just pointed the
    MTA at Xcp_Ptr->general->identification, real backing memory in this process -- unlike
    capture_extensions above, which must never do this because it is also used where the MTA
    names a fabricated address."""
    identification = 'DD75/get_id/content.a2l'
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE',
                                   max_cto=8, identification=identification))
    connect(handle)

    assert set_mta_with_extension(handle, 0xDEADBEEF, 0x07)[0] == 0xFF, (
        'setup: SET_MTA must succeed here')

    get_id_response = exchange(handle, (0xFA, 0x00), length=2)
    assert get_id_response == (0xFF, 0x00), (
        'setup: GET_ID must answer (PID, Mode) = (0xFF, 0x00) -- got {}'.format(get_id_response))

    reads = list()

    def read_slave_memory(p_address, extension, p_buffer):
        p_buffer[0] = handle.ffi.cast('uint8_t*', p_address)[0]
        reads.append((extension, int(p_buffer[0])))

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, len(identification))))
    for _ in range(math.ceil(len(identification) / 7)):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert len(reads) == len(identification), (
        'UPLOAD triggered {} slave-memory read(s), expected exactly the {} bytes of the '
        'identification string'.format(len(reads), len(identification)))
    assert ''.join(chr(byte) for _extension, byte in reads) == identification, (
        'the identification content UPLOAD returned does not match what GET_ID pointed the MTA '
        'at -- the extension fix must have disturbed the address assignment beside it')
    assert [extension for extension, _byte in reads] == [0x00] * len(identification), (
        'expected extension 0x00 throughout -- this identification is not part of any configured '
        'SEGMENT for a non-zero extension to name')


def test_set_mta_followed_by_upload_without_get_id_is_unaffected_by_the_get_id_fix():
    """DD75's other neighbour, named explicitly by this task's own brief: a SET_MTA followed by an
    ordinary UPLOAD, with no GET_ID in between, must be unaffected. Xcp_DTOCmdStdGetId's own fix
    is scoped to its own handler (a local assignment, not, say, a helper that zeroes the extension
    somewhere every command passes through), so a session that never calls GET_ID at all must see
    exactly the extension its own SET_MTA set, undisturbed.

    extension=3 here, not 7 or 0 -- distinct from the leaked value the test above pins and from
    this task's own fixed value for GET_ID, so a pass here cannot be mistaken for either of those
    by coincidence."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)

    assert set_mta_with_extension(handle, 0xDEADBEEF, 0x03)[0] == 0xFF, (
        'setup: SET_MTA must succeed here')

    reads = capture_extensions(handle)
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x03)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 1, 'UPLOAD must be answered'
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    observed_extensions = [extension for _address, extension in reads]
    assert observed_extensions == [0x03, 0x03, 0x03], (
        'UPLOAD with no intervening GET_ID read memory through extension(s) {} -- expected '
        "[3, 3, 3], SET_MTA's own value, unaffected by DD75's fix to a wholly different command's "
        'handler'.format(observed_extensions))


def test_a_stuck_store_cal_request_does_not_survive_a_reconnect():
    """Final review, R1. The audit recorded session_status sound because "SET_REQUEST refuses
    every bit but STORE_CAL_REQ, so the ERR_PGM_ACTIVE gate cannot be wedged". The one accepted
    bit is enough.

    STORE_CAL_REQ is cleared in exactly one place -- Xcp_MainFunction (source/Xcp.c) -- and only
    when Xcp_StoreCalibrationDataToNonVolatileMemory returns E_OK. An integrator whose NVM write
    never succeeds returns E_NOT_OK forever, so the bit never clears, and the ERR_PGM_ACTIVE gate
    then refuses every command whose Xcp_CTOErrorMatrix row carries the bit -- 42 rows in the
    default build, 38 with flash programming enabled (four rows carry the bit only with that gate
    off; counted from the matrix's own initializer entries per preprocessor branch, not by grepping
    the macro name, which also matches the dispatch gate's own uses), DISCONNECT among them.
    CONNECT is itself ungated (row 0x00u), so before the fix a master could reconnect and recover
    nothing: only Xcp_Init, a power cycle, cleared it.

    The two halves matter separately. The DISCONNECT refusal below is the PRECONDITION -- it
    proves the wedge is real and that this test is exercising it, not a slave that was fine all
    along. The refusal is expected and correct while the request is outstanding; what was wrong is
    that it outlived the session."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')

    connect(handle)

    assert exchange(handle, (0xF9, 0x01, 0x00, 0x00))[0] == 0xFF, 'SET_REQUEST(STORE_CAL_REQ)'

    # Poll once: the integrator refuses, so the bit stays set. Without this the bit would be set
    # but never yet offered to the integrator, and the test would not be pinning the stuck case.
    handle.lib.Xcp_MainFunction()
    assert handle.xcp_store_calibration_data_to_non_volatile_memory.call_count > 0, \
        'the store was never attempted, so nothing is stuck and this test proves nothing'

    # Precondition: the wedge is real. DISCONNECT is refused while the request is outstanding.
    assert exchange(handle, (0xFE,))[0:2] == (0xFE, 0x12), 'ERR_PGM_ACTIVE'

    connect(handle)

    # The fix: the new session does not inherit the previous one's stuck request.
    assert exchange(handle, (0xFE,))[0] == 0xFF, \
        'DISCONNECT still refused after a reconnect: the wedge outlived the session'


def test_the_daq_pointer_does_not_survive_a_reconnect():
    """Final review, R2. daq_pointer is a per-session cursor exactly as the MTA is
    (test_the_mta_does_not_survive_a_reconnect above), and survived CONNECT for the same reason --
    nothing reset it. Xcp_DaqFreeAll (source/Xcp_Daq.c) does clear it but runs only from
    DISCONNECT and only under a DYNAMIC configuration, so a master that vanishes without
    DISCONNECT -- this file's whole threat model -- never reached it.

    Before the fix, session 2's WRITE_DAQ with no SET_DAQ_PTR of its own wrote session 1's ODT
    entry. After it, the pointer is invalid and WRITE_DAQ answers ERR_OUT_OF_RANGE, which
    1.1/1.6.4.1.1.2 makes the correct answer for an undefined pointer: repositioning it is the
    master's responsibility.

    The last two lines are what stop this passing for the wrong reason. ERR_OUT_OF_RANGE would
    equally be the answer if the reconnect had freed the DAQ pool outright, which is a different
    behaviour and one this fix deliberately does not implement (the DD25/SP2d question). Setting
    the pointer again and completing the write proves the lists are still allocated, so the
    refusal above was the invalid pointer and nothing else."""
    handle = XcpTest(dynamic_config(daq_count=1, odt_count=1, odt_entries_count=1,
                                    channel_rx_pdu_ref=0x0001))
    write_daq = (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN'))

    connect(handle)
    assert exchange(handle, (0xD6,))[0] == 0xFF                              # FREE_DAQ
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF             # ALLOC_DAQ(1)
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF       # ALLOC_ODT(list 0, 1)
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF  # ALLOC_ODT_ENTRY
    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0] == 0xFF  # SET_DAQ_PTR(0,0,0)

    connect(handle)

    assert exchange(handle, write_daq)[0:2] == (0xFE, 0x22), \
        'WRITE_DAQ used the previous session\'s DAQ pointer'

    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0] == 0xFF
    assert exchange(handle, write_daq)[0] == 0xFF, \
        'the reconnect freed the DAQ pool, so the refusal above was not about the pointer'

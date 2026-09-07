#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD74 (docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md) -- a pre-existing
defect in shipped code, independent of any feature branch this repository carries: CONNECT does
not tear down the whole session. XCP part 2 - Protocol Layer Specification 1.1/1.6.1.1.1 makes
CONNECT the start of a session, and Xcp_CTOCmdStdConnect's own comment (source/Xcp_Std.c) already
argues that no state of the previous session may survive into the next -- it was written when an
earlier task made CONNECT clear pgm_state for exactly this reason. Until this task's own fix,
CONNECT cleared pgm_state and called Xcp_PgmBlockAbort(), and nothing else. Three more pieces of
session state survived a reconnect:

- An open block transfer (Xcp_Internal.block_transfer): a slave block mode (UPLOAD) transfer left
  mid-flight answers a later, unrelated transmission confirmation by continuing to read and
  transmit the PREVIOUS session's memory into the new one.
- A partial key (Xcp_Internal.key_master/key_slave): an UNLOCK that announces N bytes and delivers
  fewer, left standing, lets a new session's UNLOCK complete it with only the still-missing bytes.
- The MTA (Xcp_Internal.memory_transfer): a DOWNLOAD with no SET_MTA in the new session writes at
  the previous session's address.

test_an_open_block_transfer_does_not_survive_a_reconnect, test_a_partial_key_does_not_survive_a_
reconnect and test_the_mta_does_not_survive_a_reconnect below are the direct reproductions, one
per item, each across a real DISCONNECT/CONNECT. test_a_normal_session_still_works_end_to_end_
after_a_reconnect is the neighbour every one of the three resets endangers: a teardown that clears
too much breaks exactly the ordinary session it exists to protect.

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

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes
from .block_transfer_disclosure_test import poison_reads
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .seed_key_defects_test import exchange

CAL_PAG = 0x01
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


def test_a_normal_session_still_works_end_to_end_after_a_reconnect():
    """The neighbour every one of the three resets above endangers, and DD74's own brief names as
    the most likely way to get this task wrong: a teardown that clears too much breaks exactly the
    ordinary session it exists to protect. CONNECT, SET_MTA, DOWNLOAD, GET_SEED, UNLOCK -- a
    complete, legitimate sequence, run entirely in the SECOND of two sessions so that every one of
    this task's own resets has already run at least once before any of these commands does."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
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

    get_seed_response = exchange(handle, (0xF8, 0x00, CAL_PAG))
    assert get_seed_response[0:2] == (0xFF, len(key)), 'GET_SEED must still succeed'

    unlock_response = exchange(handle, (0xF7, len(key), *key))
    assert unlock_response[0:2] == (0xFF, CAL_PAG), (
        'a legitimate GET_SEED/UNLOCK sequence must still grant the resource it requested after '
        'a reconnect -- got {}'.format(unlock_response))

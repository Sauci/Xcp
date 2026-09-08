#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta

GET_STATUS = (0xFD,)

# With MAX_CTO=8 at AG=BYTE, a single DOWNLOAD frame can carry at most (MAX_CTO - 2) / 1 = 6
# elements (Xcp_BlockTransferFrameElements), so any declared count above 6 opens a block, writes
# these same 6 bytes as its first (and only, for now) frame, and leaves the MTA at
# mta + 6 -- 0x1006 when mta=0x1000, the design doc's own measured address.
BLOCK_FIRST_FRAME_PAYLOAD = (0x11, 0x22, 0x33, 0x44, 0x55, 0x66)


def handle_with_open_download_block(declared_elements, mta=0x1000):
    """CONNECT, SET_MTA(mta), then a DOWNLOAD declaring declared_elements and carrying 6 -- opens
    a master-block-mode block and leaves its own response suppressed (XCP part 2 1.1/1.6.2.1.1:
    "The slave device will acknowledge only the last DOWNLOAD_NEXT command packet"), so nothing
    is transmitted yet and nothing is pending confirmation. declared_elements - 6 is then left
    outstanding, and 6 (this write's own frame_elements) stale.

    The tests below pick declared_elements for different reasons. The wrap-runaway test uses the
    design doc's own 10 -- outstanding (4) < stale (6), so the subtraction its own confirmation
    drives underflows, exactly as measured. The other two deliberately do not: with a guarded
    subtraction in place, 10 would make either pass even if the fix each one exists to check were
    reverted, because the guard alone (outstanding < stale, so it clamps to zero) already stops
    that scenario cold -- a passing test proving nothing about the fix it is meant to pin.
    Declaring enough that outstanding stays >= stale keeps every check independent of the guard's
    own state, matching the "confirm ... others do not" half of this task's mutation-verification
    requirement -- this is what fix round 1's F3 finding measured DD70's own predicate fix being
    unprotected by, on a second trigger command, and is why that test also declares 20."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, mta)

    # Reset both mocks so the premise assertions below see ONLY the DOWNLOAD's own effects --
    # connect() and set_mta() each transmit a response of their own.
    handle.can_if_transmit.reset_mock()
    handle.xcp_write_slave_memory_u8.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xF0, declared_elements) + BLOCK_FIRST_FRAME_PAYLOAD))
    handle.lib.Xcp_MainFunction()

    # The premise this helper exists to establish, asserted rather than assumed. Without these two
    # checks every test in this file passes vacuously: if the DOWNLOAD were refused or never
    # dispatched, "no block is open" and "the fix works" produce IDENTICAL evidence -- zero reads
    # and zero transmits -- so all three tests would stay green while pinning nothing. Final
    # review, F6.
    #
    # The pair is a complete discriminator for the ways this setup can silently fail:
    #   * refused (ERR_OUT_OF_RANGE, ERR_CMD_SYNTAX, ...) -> transmits an error frame
    #   * never dispatched                               -> writes nothing
    #   * completed as a single non-block frame          -> transmits a positive response
    # Only a genuinely open block both consumes the payload and stays silent, because
    # 1.1/1.6.2.1.1 has the slave acknowledge only the LAST frame of a block.
    assert handle.xcp_write_slave_memory_u8.call_count > 0, \
        'the DOWNLOAD never reached slave memory: no block was opened and this file tests nothing'
    assert handle.can_if_transmit.call_count == 0, \
        'the DOWNLOAD answered instead of opening a block: this file tests nothing'

    return handle


def poison_reads(handle):
    """Fills every AG=BYTE slave-memory read with a recognizable non-zero pattern and records
    each address read into a plain list the test clears and re-checks itself, independently of
    the mock's own call_count. Pinning both a read count of zero AND a transmit count of zero is
    deliberate: a fix that stopped the read but still transmitted a stale buffer, or that stopped
    the transmit but left the read running, would each satisfy only one of the two checks below."""
    reads = list()

    def read_slave_memory(p_address, _extension, p_buffer):
        reads.append(int(handle.ffi.cast('uint32_t', p_address)))
        p_buffer[0] = 0x5A

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    return reads


def test_confirming_a_response_during_a_download_block_does_not_disclose_slave_memory():
    """DD70. Xcp_CanIfTxConfirmation asks Xcp_BlockTransferIsActive() and, if true, continues the
    transfer by reading slave memory and transmitting it -- correct only for slave block mode, an
    UPLOAD, where the slave sends the frames. Xcp_DataTransferInitialize is shared with DOWNLOAD
    and records no direction, so an open master-block-mode DOWNLOAD satisfies the same predicate.

    Measured before the fix: seven slave-memory reads at 0x1006..0x100C and an unsolicited
    (0xFF, 0x5A x7) frame -- seven bytes of slave memory to a master that asked for nothing.

    GET_STATUS is the interloper because it is unconditionally available and has no side effects,
    so a failure here is about the confirmation path and nothing else. 20 declared, not the
    design doc's 10, so this is independent of DD71's own guard -- see
    handle_with_open_download_block's docstring; the addresses and read count this produces are
    identical to the 10-element scenario's either way, since both leave the same 6-byte first
    frame at the same MTA."""
    handle = handle_with_open_download_block(20, mta=0x1000)
    reads = poison_reads(handle)

    # Reset before GET_STATUS is even sent, not just before the confirmation: fix round 1's F1
    # finding is that SET_MTA's own last response, still sitting in the single shared
    # cto_response buffer from handle_with_open_download_block's own setup, is
    # (0xFF, 0x00) -- PID plus a zero trailing byte, DefaultConfig's own default -- byte-identical
    # to what GET_STATUS's response is checked against below. call_args is a live view into that
    # one buffer, not a snapshot, so reading it without resetting first would pass this "GET_STATUS
    # answered normally" guard even if GET_STATUS were never dispatched at all.
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(GET_STATUS))
    handle.lib.Xcp_MainFunction()

    # GET_STATUS answers normally, exactly as the design doc's own measurement describes -- this
    # failure is about what its CONFIRMATION does, not about GET_STATUS itself. call_count == 1 is
    # the half of this guard that actually distinguishes "GET_STATUS responded" from "nothing
    # happened and the buffer still holds an old response"; the content check alone cannot.
    assert handle.can_if_transmit.call_count == 1
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, 0x00)

    # Reset again right before the confirmation under test, for the same reason.
    handle.can_if_transmit.reset_mock()
    reads.clear()

    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert reads == []
    assert handle.can_if_transmit.call_count == 0


def test_a_refused_upload_during_an_open_download_block_does_not_relabel_it():
    """Fix round 1, F3 (task-1-review.md). Xcp_DataTransferInitialize records
    block_transfer.slave_block_mode only inside its own `if (result == E_OK)` block, the same
    guard that already protects requested_elements/frame_elements from a refused request's
    leftovers -- but that placement is independently load-bearing, not merely mirroring the two
    pre-existing fields, and shipped with no test of its own.

    An UPLOAD carrying 0 elements is refused, ERR_OUT_OF_RANGE (XCP part 2 1.0/1.6.1.2.7),
    because Xcp_DataTransferInitialize's own numberOfDataElements != 0 check fails -- and it
    reaches that check, so it would reach an unguarded direction write too, even while an
    unrelated DOWNLOAD block sits open: that block's own response is suppressed
    (1.1/1.6.2.1.1), so nothing is pending and the refused UPLOAD dispatches normally rather than
    being refused ERR_CMD_BUSY.

    Moving the direction write above the `if (result == E_OK)` gate (mutation-verified, see
    task-1-report.md) relabels the still-open DOWNLOAD block as slave-direction using the refused
    UPLOAD's own TRUE, without touching requested_elements/frame_elements at all -- so confirming
    the refused UPLOAD's own (0xFE, 0x22) response reopens DD70's exact disclosure (the same seven
    reads at 0x1006..0x100C) through this second trigger command, with every other test in this
    file still green."""
    handle = handle_with_open_download_block(20, mta=0x1000)
    reads = poison_reads(handle)

    handle.can_if_transmit.reset_mock()

    # UPLOAD carrying 0 elements: always refused regardless of slave_block_mode configuration
    # (Xcp_DataTransferInitialize's numberOfDataElements != 0 check fails first), and -- the
    # premise this test exists to pin -- still dispatched despite the DOWNLOAD block remaining
    # open, because that block's own suppressed response leaves nothing pending.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    handle.can_if_transmit.reset_mock()
    reads.clear()

    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert reads == []
    assert handle.can_if_transmit.call_count == 0


def test_repeatedly_confirming_a_response_during_a_download_block_never_runs_away():
    """DD71's own measured consequence, used as a second regression signal for the DD70 predicate
    fix above -- not, despite this test's original name, an independent pin on the guard itself.
    Xcp_BlockTransferAcknowledgeFrame (source/Xcp.c) computes
    requested_elements -= frame_elements on a uint8 with no bound check. In this scenario the
    DOWNLOAD write left requested_elements=4 outstanding with frame_elements=6 stale from that
    same write; before the fix, confirming GET_STATUS's unrelated response reached this
    subtraction with both operands unchanged, 4 - 6, which wrapped to 254 instead of the fix's own
    clamp to zero.

    Renamed and given a setup guard in fix round 1 (task-1-review.md F2). Mutation-verified (see
    task-1-report.md) that reverting ONLY the guard in Xcp_BlockTransferAcknowledgeFrame, with
    DD70's predicate fix left in place, leaves this test green: nothing reachable through the
    public command interface still calls that function with a mismatched pair once the predicate
    gates entry (traced by hand: the subtraction's only other caller,
    Xcp_BlockTransferWriteSlaveMemory, computes frame_elements from requested_elements immediately
    beforehand and so can never itself trigger the mismatch). The guard stays as defense-in-depth
    on the design doc's own basis ("a future caller could reach it another way"); reverting the
    guard together with the predicate reproduces the original 37-frame runaway below, which is
    what this test's own name now claims and nothing stronger: that the predicate fix holds up
    over a sustained drain, not only the single confirmation the test above checks.

    Xcp_Internal is not reachable from this CFFI harness (interface/Xcp.h does not include
    Xcp_Internal.h), the same reason test/clear_daq_list_test.py's own pointer-invalidation test
    gives, so the (pre-fix) wrap was observed through what it drove instead: each further
    confirmation paid out one more frame of the wrapped count, so a wrapped 254 kept the chain
    running for roughly 37 frames (36 of 7 elements plus a final 2, MAX_CTO=8 at AG=BYTE:
    36*7+2=254) before the count finally walked back down through zero on its own."""
    handle = handle_with_open_download_block(10, mta=0x1000)
    poison_reads(handle)

    # Setup guard, added in fix round 1 (F2): without it, this test would pass just as easily if
    # GET_STATUS silently stopped responding at all, since the loop below would then never see
    # ongoing_transmit_type become CTO in the first place and call_count would stay 0 regardless
    # of whether anything about DD70/DD71's own fix is even still correct.
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(GET_STATUS))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, 0x00)

    handle.can_if_transmit.reset_mock()

    # Confirmations chain: Xcp_CanIfTxConfirmation ends with Xcp_StartNextTransmission, which
    # transmits again immediately as long as the module still believes it owes the master more
    # data (source/Xcp.c, "D16" comment above that call). Calling this once only shows the first
    # frame of a runaway, not its size, so "observe through consequences" here means draining it:
    # 45 is comfortably above the ~37 frames the wrap produces -- a bound derived from the
    # arithmetic (254 elements at 7 per frame cannot take more than ceil(254/7) = 37 frames to
    # drain, even in the worst case), not tuned against one run -- so a guarded implementation is
    # done long before the loop ends and an unguarded one is still caught mid-runaway.
    for _ in range(45):
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.can_if_transmit.call_count == 0


def test_upload_slave_block_transfer_still_chains_across_confirmations_after_the_narrower_predicate():
    """The neighbour DD70's fix most endangers: UPLOAD's own slave block mode legitimately relies
    on Xcp_CanIfTxConfirmation reading Xcp_Internal.block_transfer to keep sending frames until
    the master has everything it asked for. A predicate narrowed to "not a DOWNLOAD" in some
    accidental way (rather than "is a slave-direction transfer") could easily also start refusing
    this. 20 elements at MAX_CTO=8/AG=BYTE (capacity (MAX_CTO-1)/1 = 7 per frame, one byte less
    than DOWNLOAD's because UPLOAD's response carries no count byte) needs three frames -- 7, 7,
    then the remaining 6 -- so this is the existing suite's own
    test_upload_block_transfer_completes_without_further_main_function_calls (upload_test.py)
    scenario, extended one confirmation further to also pin that the chain then stops cleanly
    rather than continuing to run (the DD71 side of this same neighbour: a legitimate transfer's
    own final confirmation must not misbehave either)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   slave_block_mode=True,
                                   max_cto=8))
    connect(handle)
    reads = poison_reads(handle)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 20)))
    handle.lib.Xcp_MainFunction()

    for _ in range(2):
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # Three frames -- 7 + 7 + 6 -- carrying all 20 requested elements between them.
    assert handle.can_if_transmit.call_count == 3
    assert len(reads) == 20

    # One more confirmation, of the third (final) frame: the block is now fully acknowledged
    # (requested_elements reaches exactly 0), so this must close the transfer -- no further read,
    # no further frame -- rather than either wedging open or, DD71's own failure mode, wrapping
    # past zero and running away.
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.can_if_transmit.call_count == 3
    assert len(reads) == 20

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes


@pytest.mark.parametrize('byte_order', byte_orders)
def test_short_download_writes_at_its_own_address(byte_order):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   byte_order=byte_order,
                                   max_cto=16))
    connect(handle)
    written = capture_writes(handle, 1, byte_order)

    payload = (0xED, 0x03, 0x00, 0x02) + tuple(u32_to_array(0x00003000, byte_order)) + (0xAA, 0xBB, 0xCC)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert written == [(0x00003000, 0xAA), (0x00003001, 0xBB), (0x00003002, 0xCC)]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_short_download_leaves_the_mta_behind_the_written_block():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: MTA is set behind the block."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=16))
    connect(handle)
    written = capture_writes(handle, 1)

    payload = (0xED, 0x03, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN')) + (0xAA, 0xBB, 0xCC)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # A following DOWNLOAD must continue at 0x3003.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x01, 0xDD)))
    handle.lib.Xcp_MainFunction()

    assert written[-1] == (0x00003003, 0xDD)


def test_short_download_returns_err_out_of_range_when_the_count_exceeds_capacity():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: n is in [0..(MAX_CTO-8)/AG]."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=16))
    connect(handle)

    payload = (0xED, 0x09, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN')) + tuple([0] * 8)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


def test_short_download_carries_no_data_when_max_cto_is_eight():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: no effect if MAX_CTO = 8."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    written = capture_writes(handle, 1)

    payload = (0xED, 0x00, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert written == []
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_short_download_inside_a_block_transfer_returns_err_sequence_and_aborts_the_transfer():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3 forbids use within a block sequence.

    Beyond the error code, the pending transfer must actually be aborted rather than merely
    reported on. That is checked by following up with a DOWNLOAD_NEXT: XCP part 2 - Protocol
    Layer Specification 1.0/1.6.2.2.1 has it report the expected count in its ERR_SEQUENCE
    response, so if the abort had not happened the transfer would still be active and it would
    report the 2 elements still outstanding instead of 0x00.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=16))
    connect(handle)
    set_mta(handle, 0x00001000)
    capture_writes(handle, 1)

    # DOWNLOAD announces 16 elements; a MAX_CTO=16 frame only carries 14 (MAX_CTO-2), so this
    # arms a block transfer with 2 elements still outstanding.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x10) + tuple(range(14))))
    handle.lib.Xcp_MainFunction()

    # A well-formed, in-capacity SHORT_DOWNLOAD -- the block-transfer check must pre-empt it
    # regardless of the address, extension or data it carries.
    payload = (0xED, 0x03, 0x00, 0x00) + tuple(u32_to_array(0x00004000, 'LITTLE_ENDIAN')) + (0xAA, 0xBB, 0xCC)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x29)
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 0x11, 0x22)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFE, 0x29, 0x00)

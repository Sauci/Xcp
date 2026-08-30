#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes


def test_download_next_completes_a_block_transfer_and_acknowledges_only_the_last_packet():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1, diagram 23."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00001000)
    written = capture_writes(handle, 1)

    handle.can_if_transmit.reset_mock()

    # DOWNLOAD(0x0E, d0..d5) - 14 elements announced, 6 carried.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0E, 0, 1, 2, 3, 4, 5)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 0, 'intermediate packets must not be acknowledged'

    # DOWNLOAD_NEXT(0x08, d6..d11)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x08, 6, 7, 8, 9, 10, 11)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 0, 'intermediate packets must not be acknowledged'

    # DOWNLOAD_NEXT(0x02, d12 d13)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 12, 13)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
    assert written == [(0x00001000 + i, i) for i in range(14)]


def test_download_next_returns_err_sequence_with_the_expected_count_on_mismatch():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1 negative response."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00001000)
    capture_writes(handle, 1)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0E, 0, 1, 2, 3, 4, 5)))
    handle.lib.Xcp_MainFunction()

    # 8 elements remain; announce 7 instead.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x07, 6, 7, 8, 9, 10, 11)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFE, 0x29, 0x08)


def test_download_next_without_an_active_block_transfer_returns_err_sequence():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00001000)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 0x11, 0x22)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFE, 0x29, 0x00)

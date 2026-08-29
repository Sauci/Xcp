#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest


def connect(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def set_mta(handle, mta, byte_order='LITTLE_ENDIAN'):
    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00) + tuple(u32_to_array(mta, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def capture_writes(handle, element_size, byte_order='LITTLE_ENDIAN'):
    written = list()

    def write_slave_memory(p_address, p_buffer):
        value = bytes(p_buffer[0:element_size])
        written.append((int(handle.ffi.cast('uint32_t', p_address)),
                        int.from_bytes(value, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order])))

    handle.xcp_write_slave_memory_u8.side_effect = write_slave_memory
    handle.xcp_write_slave_memory_u16.side_effect = write_slave_memory
    handle.xcp_write_slave_memory_u32.side_effect = write_slave_memory
    return written


def test_download_writes_the_payload_to_the_mta_and_acknowledges():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=False,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)
    written = capture_writes(handle, 1)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x03, 0x11, 0x22, 0x33)))
    handle.lib.Xcp_MainFunction()

    assert written == [(0xDEADBEEF, 0x11), (0xDEADBEF0, 0x22), (0xDEADBEF1, 0x33)]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_download_returns_err_out_of_range_when_the_count_exceeds_a_single_packet():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=False,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x07, 0x11, 0x22, 0x33)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


@pytest.mark.parametrize('master_block_mode, slave_block_mode, expect_accepted', ((False, False, False),
                                                                                  (False, True, False),
                                                                                  (True, False, True),
                                                                                  (True, True, True)))
def test_download_block_mode_follows_the_master_block_mode_flag(master_block_mode,
                                                                slave_block_mode,
                                                                expect_accepted):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.1: MAX_BS belongs to master block mode."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=master_block_mode,
                                   slave_block_mode=slave_block_mode,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)
    capture_writes(handle, 1)

    # 10 elements needs more than one packet, so it is only legal in master block mode.
    # Block mode suppresses the response until the final DOWNLOAD_NEXT, so the earlier
    # SET_MTA response must be cleared first or an accepted case would be indistinguishable
    # from one that silently did nothing.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66)))
    handle.lib.Xcp_MainFunction()

    if expect_accepted:
        assert handle.can_if_transmit.call_count == 0
    else:
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

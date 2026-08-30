#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes


@pytest.mark.parametrize('ag, max_cto, expected_count', (('BYTE', 8, 7),
                                                         ('WORD', 8, 3),
                                                         ('DWORD', 8, 1)))
def test_download_max_writes_a_fixed_number_of_elements(ag, max_cto, expected_count):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2: MAX_CTO/AG-1 elements."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   max_cto=max_cto))
    connect(handle)
    set_mta(handle, 0x00002000)
    element_size = element_size_from_address_granularity(ag)
    written = capture_writes(handle, element_size)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple([0xEE] + [0x00] * (max_cto - 1))))
    handle.lib.Xcp_MainFunction()

    assert len(written) == expected_count
    assert [a for a, _ in written] == [0x00002000 + (i * element_size) for i in range(expected_count)]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_download_max_returns_err_cmd_syntax_when_the_packet_is_short():
    """The minimum request size is MAX_CTO, which ctoInfo's 4-bit field cannot express."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00002000)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEE, 0x11, 0x22)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)


def test_download_max_inside_a_block_transfer_returns_err_sequence():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2 forbids use within a block sequence."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00002000)
    capture_writes(handle, 1)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0E, 0, 1, 2, 3, 4, 5)))
    handle.lib.Xcp_MainFunction()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple([0xEE] + [0x00] * 7)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x29)

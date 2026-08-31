#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A write command must not read past the PDU it was given.

The element count is taken from the request, but the number of bytes a handler reads was bounded
only by MAX_CTO, never by the length actually received. The dispatcher's generic length gate
enforces each command's minimum request size, which covers the header alone, so a frame
announcing more elements than it carries passed straight through: the handler read whatever
followed the frame in memory, wrote it into calibration memory through the integrator callback,
and acknowledged success.

DOWNLOAD_MAX was the only one of the four write commands that checked.
"""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta


def write_handle(max_cto=8, ag='BYTE', master_block_mode=False):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   master_block_mode=master_block_mode,
                                   max_cto=max_cto))
    connect(handle)
    set_mta(handle, 0x00000000)
    handle.xcp_write_slave_memory_u8.reset_mock()
    handle.xcp_write_slave_memory_u16.reset_mock()
    handle.xcp_write_slave_memory_u32.reset_mock()
    handle.can_if_transmit.reset_mock()

    return handle


def writes(handle):
    return (handle.xcp_write_slave_memory_u8.call_count +
            handle.xcp_write_slave_memory_u16.call_count +
            handle.xcp_write_slave_memory_u32.call_count)


@pytest.mark.parametrize('announced, carried', ((0x06, 1), (0x06, 0), (0x02, 1)))
def test_download_rejects_a_frame_shorter_than_the_payload_it_announces(announced, carried):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2: ERR_CMD_SYNTAX."""
    handle = write_handle()

    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xF0, announced) + tuple(0xAA for _ in range(carried))))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)
    assert writes(handle) == 0, 'nothing may be written from a frame that was never received'


@pytest.mark.parametrize('max_cto, announced, carried', ((128, 100, 0), (128, 100, 99), (16, 8, 7)))
def test_short_download_rejects_a_frame_shorter_than_the_payload_it_announces(max_cto, announced, carried):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2: ERR_CMD_SYNTAX."""
    handle = write_handle(max_cto=max_cto)

    header = (0xED, announced, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)
    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info(header + tuple(0xAA for _ in range(carried))))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)
    assert writes(handle) == 0


def test_download_next_rejects_a_frame_shorter_than_the_payload_it_announces():
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2: ERR_CMD_SYNTAX."""
    handle = write_handle(max_cto=8, master_block_mode=True)

    # Open a block transfer of 12 elements: the first frame carries its full six.
    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xF0, 0x0C, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06)))
    handle.lib.Xcp_MainFunction()
    handle.can_if_transmit.reset_mock()
    handle.xcp_write_slave_memory_u8.reset_mock()

    # The continuation announces the remaining six but carries one.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x06, 0x07)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)
    assert writes(handle) == 0


@pytest.mark.parametrize('ag, element_size', (('BYTE', 1), ('WORD', 2), ('DWORD', 4)))
def test_a_frame_carrying_exactly_what_it_announces_is_still_accepted(ag, element_size):
    """The guard must not reject well formed requests at any address granularity."""
    handle = write_handle(ag=ag)

    # Data starts after (MAX_CTO - 2) mod AG alignment bytes, so a well formed frame carries
    # those too. Getting this wrong is what a bounds check should catch, and did.
    alignment = (8 - 2) % element_size
    count = (8 - 2) // element_size
    payload = tuple(0x00 for _ in range(alignment)) + tuple(0xAA for _ in range(count * element_size))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, count) + payload))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
    assert writes(handle) == count

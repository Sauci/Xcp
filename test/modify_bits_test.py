#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta


def run_modify_bits(handle, initial, shift, and_mask, xor_mask, byte_order='LITTLE_ENDIAN'):
    result = dict()

    def read_slave_memory(_p_address, _extension, p_buffer):
        for i, b in enumerate(u32_to_array(initial, byte_order)):
            p_buffer[i] = b

    def write_slave_memory(p_address, p_buffer):
        result['address'] = int(handle.ffi.cast('uint32_t', p_address))
        result['value'] = u32_from_array(bytes(p_buffer[0:4]), byte_order)

    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory
    handle.xcp_write_slave_memory_u32.side_effect = write_slave_memory

    payload = (0xEC, shift) + tuple(u16_to_array(and_mask, byte_order)) + tuple(u16_to_array(xor_mask, byte_order))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()
    return result


@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_modify_bits_matches_the_specification_example(max_cto, byte_order):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4 worked example.

    Byte order only changes how the masks and the memory value are marshalled to and from
    the wire; the arithmetic result must be identical under BIG_ENDIAN and LITTLE_ENDIAN.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   byte_order=byte_order,
                                   max_cto=max_cto))
    connect(handle)
    set_mta(handle, 0x00004000, byte_order)

    result = run_modify_bits(handle, 0xFFF0FFFF, 16, 0xBFFE, 0x0001, byte_order)

    assert result['value'] == 0xBFF1FFFF
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('shift, and_mask, xor_mask, initial, expected', ((0, 0xFFFE, 0x0000, 0xFFFFFFFF, 0xFFFFFFFE),
                                                                          (0, 0xFFFE, 0x0001, 0xFFFFFFFE, 0xFFFFFFFF),
                                                                          (8, 0xFFFF, 0x00FF, 0x00000000, 0x0000FF00),
                                                                          (16, 0xFFFF, 0xFFFF, 0x00000000, 0xFFFF0000),
                                                                          (31, 0xFFFF, 0x0001, 0x00000000, 0x80000000)))
def test_modify_bits_applies_the_mask_formula(shift, and_mask, xor_mask, initial, expected):
    """The masks must be widened to 32 bits before shifting."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    assert run_modify_bits(handle, initial, shift, and_mask, xor_mask)['value'] == expected


def test_modify_bits_does_not_move_the_mta():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4: The MTA will not be affected."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    first = run_modify_bits(handle, 0x00000000, 0, 0xFFFF, 0x0001)
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    second = run_modify_bits(handle, 0x00000000, 0, 0xFFFF, 0x0001)

    assert first['address'] == second['address'] == 0x00004000


def test_modify_bits_returns_err_out_of_range_for_a_shift_above_31():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEC, 0x20, 0xFF, 0xFF, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

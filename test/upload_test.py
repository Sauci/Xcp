#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
import random
import struct

from math import floor

from .parameter import *
from .conftest import XcpTest


# TODO: use max_cto parameter here instead of hard-coded 8 byte value...

def generate_random_block_content(n, element_size, base_address) -> [int]:
    return list((base_address + (i * 8 * element_size), random.getrandbits(8 * element_size, )) for i in range(n))


def address_to_array(address: int, byte_size: int, endianness: str) -> [int]:
    return [int(b) for b in address.to_bytes(byte_size,
                                             dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[endianness],
                                             signed=False)]


def get_block_slices_for_max_cto(block, element_size, max_cto=8):
    n = floor((max_cto - 1) / element_size)
    return [block[i * n:(i + 1) * n] for i in range(len(block)) if len(block[i * n:(i + 1) * n]) != 0]


@pytest.mark.parametrize('ag, element_size', (('BYTE', 1), ('WORD', 2), ('DWORD', 4)))
@pytest.mark.parametrize('number_of_data_elements', range(1, 255))
@pytest.mark.parametrize('byte_order', ('BIG_ENDIAN', 'LITTLE_ENDIAN'))
@pytest.mark.parametrize('mta', [0x00000000])
def test_upload_uploads_elements_according_to_provided_mta_with_address_granularity_byte(ag,
                                                                                         element_size,
                                                                                         number_of_data_elements,
                                                                                         mta,
                                                                                         byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity=ag, byte_order=byte_order))

    expected_block = generate_random_block_content(number_of_data_elements, element_size, mta)
    expected_block_generator = (v for v in expected_block)
    actual_block = list()
    block_slices = get_block_slices_for_max_cto(expected_block, element_size)

    def read_slave_memory(address, _extension, p_buffer):
        expected_address, expected_value = next(expected_block_generator)
        expected_value_buffer = expected_value.to_bytes(element_size,
                                                        dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order],
                                                        signed=False)
        for i, b in enumerate(expected_value_buffer):
            p_buffer[i] = int(b)
        actual_block.append((int(address), expected_value))

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_MTA
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                  0x00,
                                                                  0x00,
                                                                  0x00,
                                                                  *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UPLOAD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, number_of_data_elements)))
    for s in block_slices:
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
        raw_values = bytearray(
            handle.can_if_transmit.call_args[0][1].SduDataPtr[element_size:element_size + (element_size * len(s))])
        actual_values = tuple(struct.unpack('{}{}'.format('>' if byte_order == 'BIG_ENDIAN' else '<',
                                                          {1: 'B', 2: 'H', 4: 'I'}[element_size] * len(s)), raw_values))
        assert actual_values == tuple(v[1] for v in s)

        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # Call Xcp_MainFunction one more time to make sure no more data are sent.
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == len(block_slices) + 2
    assert actual_block == expected_block

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import crcmod
import crcmod.predefined

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('checksum_type, poly, init, reverse, xor_out', [
    pytest.param(0x09, 0x104C11DB7, 0xFFFFFFFF, True, 0xFFFFFFFF, id='XCP_CRC_32')
])
@pytest.mark.parametrize('ag', address_granularities)
@pytest.mark.parametrize('block_size', [pytest.param(v, id='block_size = {:04}d'.format(v)) for v in [1,
                                                                                                      2,
                                                                                                      3,
                                                                                                      8,
                                                                                                      64,
                                                                                                      256,
                                                                                                      1000]])
@pytest.mark.parametrize('mta', mtas)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_returns_expected_checksum_on_a_single_block(checksum_type,
                                                                    poly,
                                                                    init,
                                                                    reverse,
                                                                    xor_out,
                                                                    ag,
                                                                    block_size,
                                                                    mta,
                                                                    byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity=ag, byte_order=byte_order))

    element_size = element_size_from_address_granularity(ag)
    expected_block = generate_random_block_content(block_size * element_size, 1, mta)
    expected_block_generator = (v for v in expected_block)

    def read_slave_memory(address, _extension, p_buffer):
        expected_address, expected_value = next(expected_block_generator)
        assert address == expected_address
        p_buffer[0] = int(expected_value)

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory

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

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                  0x00,
                                                                  0x00,
                                                                  0x00,
                                                                  *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # check packet ID.
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    # check checksum type.
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] == checksum_type

    # check reserved bytes.
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[2] == 0x00
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[3] == 0x00

    # check checksum value.
    actual_checksum = u32_from_array(bytearray(handle.can_if_transmit.call_args[0][1].SduDataPtr[4:8]), byte_order)
    expected_checksum = crcmod.mkCrcFun(poly=poly, rev=reverse, initCrc=init, xorOut=xor_out)(bytearray(v[1] for v in expected_block))
    assert actual_checksum == expected_checksum

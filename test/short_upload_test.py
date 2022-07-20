#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest_cases

from .parameter import *
from .conftest import XcpTest


@pytest_cases.fixture()
@pytest.mark.parametrize('ag', address_granularities)
@pytest.mark.parametrize('max_cto', max_ctos)
def short_upload_payload_properties(ag, max_cto):
    element_size = element_size_from_address_granularity(ag)
    num_of_data_elements = floor((max_cto - 1) / element_size)
    alignment = max_cto - 1 - num_of_data_elements * element_size
    return ag, max_cto, alignment, num_of_data_elements


@pytest_cases.parametrize('ag, max_cto, alignment, number_of_data_elements',
                          [pytest_cases.fixture_ref(short_upload_payload_properties)])
@pytest.mark.parametrize('address_extension', address_extensions)
@pytest.mark.parametrize('mta', mtas)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_short_upload_uploads_elements_according_to_provided_mta_with_address_granularity_byte(ag,
                                                                                               max_cto,
                                                                                               alignment,
                                                                                               number_of_data_elements,
                                                                                               address_extension,
                                                                                               mta,
                                                                                               byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   byte_order=byte_order,
                                   max_cto=max_cto))

    element_size = element_size_from_address_granularity(ag)
    expected_block = generate_random_block_content(number_of_data_elements, element_size, mta)
    expected_block_generator = (v for v in expected_block)
    actual_block = list()
    block_slices = get_block_slices_for_max_cto(expected_block, element_size, max_cto=max_cto)

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

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SHORT_UPLOAD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF4,
                                                                  number_of_data_elements,
                                                                  0x00,
                                                                  address_extension,
                                                                  *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[1:1 + alignment]) == tuple([0] * alignment)
    raw_values = bytearray(handle.can_if_transmit.call_args[0][1].SduDataPtr[element_size:max_cto])
    actual_values = tuple(payload_to_array(raw_values, number_of_data_elements, element_size, byte_order))
    assert actual_values == tuple(v[1] for v in block_slices[0])

    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # Call Xcp_MainFunction one more time to make sure no more data are sent.
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 2
    assert actual_block == expected_block

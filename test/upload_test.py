#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
import pytest_cases

from .parameter import *
from .conftest import XcpTest


@pytest_cases.fixture()
@pytest.mark.parametrize('ag', address_granularities)
@pytest.mark.parametrize('max_cto', max_ctos)
def upload_payload_properties(ag, max_cto):
    element_size = element_size_from_address_granularity(ag)
    num_of_data_elements = floor((max_cto - 1) / element_size)
    alignment = max_cto - 1 - num_of_data_elements * element_size
    return ag, max_cto, alignment


@pytest_cases.parametrize('ag, max_cto, alignment', [pytest_cases.fixture_ref(upload_payload_properties)])
@pytest.mark.parametrize('number_of_data_elements', range(1, 256))
@pytest.mark.parametrize('mta', mtas)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_upload_uploads_elements_according_to_provided_mta_with_address_granularity_byte(ag,
                                                                                         max_cto,
                                                                                         alignment,
                                                                                         number_of_data_elements,
                                                                                         mta,
                                                                                         byte_order):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   byte_order=byte_order,
                                   slave_block_mode=True,
                                   max_cto=max_cto))

    element_size = element_size_from_address_granularity(ag)
    expected_block = generate_random_block_content(number_of_data_elements, element_size, mta)
    expected_block_generator = (v for v in expected_block)
    actual_block = list()
    block_slices = get_block_slices_for_max_cto(expected_block, element_size, max_cto=max_cto)

    def read_slave_memory(p_address, _extension, p_buffer):
        expected_address, expected_value = next(expected_block_generator)
        expected_value_buffer = expected_value.to_bytes(element_size,
                                                        dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order],
                                                        signed=False)
        for i, b in enumerate(expected_value_buffer):
            p_buffer[i] = int(b)
        actual_block.append((int(handle.ffi.cast('uint32_t', p_address)), expected_value))

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
    for i, s in enumerate(block_slices):
        handle.lib.Xcp_MainFunction()

        # check packet ID.
        assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

        # check alignment byte(s) if any.
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[1:1 + alignment]) == tuple([0] * alignment)

        # check uploaded values.
        raw_payload = bytearray(handle.can_if_transmit.call_args[0][1].SduDataPtr[element_size:max_cto])
        expected = [v[1] for v in s]
        actual = payload_to_array(raw_payload[:len(s) * element_size], len(s), element_size, byte_order)
        assert tuple(actual) == tuple(expected)

        # check trailing zeros (if any).
        expected = [0] * (max_cto - (len(s) * element_size) - alignment - 1)
        actual = handle.can_if_transmit.call_args[0][1].SduDataPtr[max_cto - len(expected):max_cto]
        assert tuple(actual) == tuple(expected)

        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # Call Xcp_MainFunction one more time to make sure no more data are sent.
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == len(block_slices) + 2
    assert actual_block == expected_block


@pytest.mark.parametrize('ag,max_cto,data_elements', [
    ('BYTE', 0x08, 0x08),
    ('WORD', 0x08, 0x04),
    ('DWORD', 0x08, 0x02)])
def test_upload_returns_err_out_of_range_if_slave_block_mode_is_disabled_and_payload_exceeds_range(ag,
                                                                                                   max_cto,
                                                                                                   data_elements):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   slave_block_mode=False,
                                   max_cto=max_cto))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UPLOAD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, data_elements)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


def test_upload_returns_err_out_of_range_if_slave_block_mode_is_enabled_and_payload_exceeds_range():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   slave_block_mode=True))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UPLOAD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)
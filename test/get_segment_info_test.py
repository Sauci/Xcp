#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def info_handle(byte_order='LITTLE_ENDIAN', max_cto=8):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   max_cto=max_cto,
                                   segments=[segment(name='S0',
                                                     address=0x00400000,
                                                     length=0x1000,
                                                     address_extension=0x02,
                                                     compression_method=0x03,
                                                     encryption_method=0x04,
                                                     pages=[page(), page(), page()],
                                                     address_mappings=[
                                                         address_mapping(0x11111111, 0x22222222, 0x33333333),
                                                         address_mapping(0x44444444, 0x55555555, 0x66666666)])]))
    connect(handle)
    return handle


@pytest.mark.parametrize('segment_info, expected', ((0x00, 0x00400000), (0x01, 0x00001000)))
@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_segment_info_mode_0_returns_address_and_length(max_cto, segment_info, expected, byte_order):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 0."""
    handle = info_handle(byte_order, max_cto=max_cto)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x00, 0x00, segment_info, 0x00)))
    handle.lib.Xcp_MainFunction()

    response = handle.can_if_transmit.call_args[0][1].SduDataPtr
    assert response[0] == 0xFF
    assert u32_from_array(bytes(response[4:8]), byte_order) == expected


def test_get_segment_info_mode_1_returns_standard_information():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 1."""
    handle = info_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x01, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:6]) == (0xFF, 0x03, 0x02, 0x02, 0x03, 0x04)


@pytest.mark.parametrize('mapping_index, segment_info, expected', ((0x00, 0x00, 0x11111111),
                                                                   (0x00, 0x01, 0x22222222),
                                                                   (0x00, 0x02, 0x33333333),
                                                                   (0x01, 0x00, 0x44444444),
                                                                   (0x01, 0x02, 0x66666666)))
def test_get_segment_info_mode_2_returns_mapping_information(mapping_index, segment_info, expected):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 2."""
    handle = info_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x02, 0x00, segment_info, mapping_index)))
    handle.lib.Xcp_MainFunction()

    response = handle.can_if_transmit.call_args[0][1].SduDataPtr
    assert response[0] == 0xFF
    assert u32_from_array(bytes(response[4:8]), 'LITTLE_ENDIAN') == expected


@pytest.mark.parametrize('mode, segment, segment_info, mapping_index, expected_error',
                         ((0x00, 0x05, 0x00, 0x00, 0x28),
                          (0x03, 0x00, 0x00, 0x00, 0x22),
                          (0x00, 0x00, 0x02, 0x00, 0x22),
                          (0x02, 0x00, 0x03, 0x00, 0x22),
                          (0x02, 0x00, 0x00, 0x02, 0x22)))
def test_get_segment_info_rejects_invalid_parameters(mode, segment, segment_info, mapping_index, expected_error):
    handle = info_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001,
                                     handle.get_pdu_info((0xE8, mode, segment, segment_info, mapping_index)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)


@pytest.mark.parametrize('mapping_index', (0x00, 0x01, 0xFF))
def test_get_segment_info_mode_2_rejects_every_index_when_the_segment_has_no_mappings(mapping_index):
    """A segment may declare no address mappings at all, which is the configuration default.

    MAPPING_INDEX is unsigned, so `mapping_index >= maxMapping` rejects every possible wire
    value when maxMapping is zero and the array is never indexed. This pins that, because the
    generator still emits a sentinel row for such a segment: were the bound ever dropped, the
    read would succeed against the sentinel instead of faulting, and the defect would be silent.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=8,
                                   segments=[segment(name='S0', address_mappings=[])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001,
                                     handle.get_pdu_info((0xE8, 0x02, 0x00, 0x00, mapping_index)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

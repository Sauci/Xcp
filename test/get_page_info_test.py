#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('ecu, xcp_read, xcp_write, expected', (
        ('NOT_ALLOWED', 'NOT_ALLOWED', 'NOT_ALLOWED', 0x00),
        ('DONT_CARE', 'NOT_ALLOWED', 'NOT_ALLOWED', 0x03),
        ('NOT_ALLOWED', 'DONT_CARE', 'NOT_ALLOWED', 0x0C),
        ('NOT_ALLOWED', 'NOT_ALLOWED', 'DONT_CARE', 0x30),
        ('WITHOUT_OTHER', 'WITH_OTHER', 'WITHOUT_OTHER', 0x19),
        ('DONT_CARE', 'DONT_CARE', 'DONT_CARE', 0x3F)))
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_page_info_packs_the_page_properties(max_cto, ecu, xcp_read, xcp_write, expected):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.3: bits 1:0, 3:2 and 5:4."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=max_cto,
                                   segments=[segment(pages=[page(init_segment=0x07,
                                                                 ecu_access=ecu,
                                                                 xcp_read_access=xcp_read,
                                                                 xcp_write_access=xcp_write)])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE7, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFF, expected, 0x07)


@pytest.mark.parametrize('segment_number, page_number, expected_error', ((0x05, 0x00, 0x28),
                                                                         (0x00, 0x09, 0x26)))
def test_get_page_info_rejects_invalid_parameters(segment_number, page_number, expected_error):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3 lists ERR_SEGMENT_NOT_VALID
    and ERR_PAGE_NOT_VALID for this command, not ERR_OUT_OF_RANGE."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   segments=[segment(pages=[page(), page()])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE7, 0x00, segment_number, page_number)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)

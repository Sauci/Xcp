#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def paging_handle(segment_count=2, page_count=2, max_cto=8):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=max_cto,
                                   segments=[segment(name='S{}'.format(i),
                                                     pages=[page() for _ in range(page_count)])
                                             for i in range(segment_count)]))
    connect(handle)
    return handle


@pytest.mark.parametrize('max_cto', max_ctos)
def test_set_cal_page_delegates_to_the_integrator_and_acknowledges(max_cto):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1"""
    handle = paging_handle(max_cto=max_cto)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x03, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert handle.xcp_set_cal_page.call_args[0][0:3] == (0x01, 0x01, 0x03)
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_set_cal_page_with_the_all_bit_applies_to_every_segment():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1: ALL ignores the segment number."""
    handle = paging_handle(segment_count=3)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x81, 0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert [c[0][0] for c in handle.xcp_set_cal_page.call_args_list] == [0, 1, 2]
    # The ALL flag selects the segments and is consumed here, so the integrator sees only the
    # access bits it can act on -- 0x81 requests ECU access for every segment, not access 0x81.
    assert [c[0][2] for c in handle.xcp_set_cal_page.call_args_list] == [0x01, 0x01, 0x01]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('mode, segment, page, expected_error', ((0x01, 0x05, 0x00, 0x28),
                                                                 (0x01, 0x00, 0x07, 0x26),
                                                                 (0x00, 0x00, 0x00, 0x27),
                                                                 (0x80, 0x00, 0x00, 0x27)))
def test_set_cal_page_rejects_invalid_parameters(mode, segment, page, expected_error):
    """ERR_SEGMENT_NOT_VALID 0x28, ERR_PAGE_NOT_VALID 0x26, ERR_MODE_NOT_VALID 0x27."""
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, mode, segment, page)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)


def test_set_cal_page_returns_err_mode_not_valid_when_the_callback_fails():
    handle = paging_handle()
    handle.xcp_set_cal_page.return_value = handle.define('E_NOT_OK')

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)

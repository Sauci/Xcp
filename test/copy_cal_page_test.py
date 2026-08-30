#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .set_cal_page_test import paging_handle


def test_copy_cal_page_delegates_to_the_integrator_and_acknowledges():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.6"""
    handle = paging_handle(segment_count=4, page_count=4)
    # can_if_transmit is reused across commands and never cleared between them, and CONNECT's
    # own positive-response PID is also 0xFF: without resetting the mock here, a broken dispatch
    # that never calls CanIf_Transmit for this request would still show the CONNECT ack that
    # paging_handle() already triggered, and a bare SduDataPtr[0] == 0xFF check would pass
    # spuriously.
    handle.can_if_transmit.reset_mock()

    # Four pairwise-distinct values, so that a transposed source/destination pair (or a
    # segment/page mix-up within one side) shows up as a mismatched tuple instead of silently
    # matching thanks to repeated values.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x01, 0x02, 0x03)))
    handle.lib.Xcp_MainFunction()

    assert handle.xcp_copy_cal_page.call_args[0][0:4] == (0x00, 0x01, 0x02, 0x03)
    assert handle.can_if_transmit.call_count == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_copy_cal_page_returns_err_write_protected_when_the_callback_fails():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.6: e.g. the destination is flash."""
    handle = paging_handle()
    handle.xcp_copy_cal_page.return_value = handle.define('E_NOT_OK')
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x23)


@pytest.mark.parametrize('src_segment, src_page, dst_segment, dst_page, expected_error',
                         ((0x05, 0x00, 0x00, 0x00, 0x28),
                          (0x00, 0x00, 0x05, 0x00, 0x28),
                          (0x00, 0x09, 0x00, 0x00, 0x26),
                          (0x00, 0x00, 0x00, 0x09, 0x26)))
def test_copy_cal_page_rejects_invalid_parameters(src_segment, src_page, dst_segment, dst_page, expected_error):
    """ERR_SEGMENT_NOT_VALID 0x28, ERR_PAGE_NOT_VALID 0x26."""
    handle = paging_handle()
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xE4, src_segment, src_page, dst_segment, dst_page)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)
    assert handle.xcp_copy_cal_page.call_count == 0

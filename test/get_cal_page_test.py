#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest
from .set_cal_page_test import paging_handle


@pytest.mark.parametrize('mode', (0x01, 0x02))
def test_get_cal_page_returns_the_page_reported_by_the_integrator(mode):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2"""
    handle = paging_handle()

    def get_cal_page(_segment, _mode, p_page):
        p_page[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_get_cal_page.side_effect = get_cal_page

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, mode, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4]) == (0xFF, 0x00, 0x00, 0x01)


@pytest.mark.parametrize('mode', (0x00, 0x03, 0x04, 0xFF))
def test_get_cal_page_rejects_any_mode_other_than_ecu_or_xcp(mode):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2: all other values are invalid."""
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, mode, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)


def test_get_cal_page_rejects_an_unknown_segment():
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, 0x01, 0x05)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)


def test_xcp_init_fails_when_set_cal_page_is_enabled_without_get_cal_page():
    """XCP part 2 - Protocol Layer Specification 1.0/1.4: SET_CAL_PAGE requires GET_CAL_PAGE."""
    handle = XcpTest(DefaultConfig(xcp_set_cal_page_api_enable=True,
                                   xcp_get_cal_page_api_enable=False,
                                   segments=[segment(pages=[page()])]))
    handle.det_report_error.assert_called_once_with(ANY, ANY,
                                                    handle.define('XCP_INIT_API_ID'),
                                                    handle.define('XCP_E_INIT_FAILED'))


def test_xcp_init_fails_when_get_seed_is_enabled_without_unlock():
    """XCP part 2 - Protocol Layer Specification 1.0/1.4: GET_SEED requires UNLOCK."""
    handle = XcpTest(DefaultConfig(xcp_get_seed_api_enable=True,
                                   xcp_unlock_api_enable=False))
    handle.det_report_error.assert_called_once_with(ANY, ANY,
                                                    handle.define('XCP_INIT_API_ID'),
                                                    handle.define('XCP_E_INIT_FAILED'))

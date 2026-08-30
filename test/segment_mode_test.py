#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def freeze_handle(freeze_supported=True, segment_count=2):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   freeze_supported=freeze_supported,
                                   segments=[segment(name='S{}'.format(i), pages=[page()])
                                             for i in range(segment_count)]))
    connect(handle)
    return handle


def test_segment_mode_defaults_to_freeze_disabled():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.5"""
    handle = freeze_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE5, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFF, 0x00, 0x00)


def test_set_segment_mode_freeze_is_reported_back_by_get_segment_mode():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.4 and 1.6.3.2.5"""
    handle = freeze_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE6, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE5, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFF, 0x00, 0x01)


def test_set_segment_mode_freeze_is_visible_through_the_public_accessor():
    """The FREEZE flag selects the SEGMENT for freezing through STORE_CAL_REQ."""
    handle = freeze_handle()

    assert handle.lib.Xcp_GetSegmentFreezeState(0x01) == 0

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE6, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert handle.lib.Xcp_GetSegmentFreezeState(0x01) == 1
    assert handle.lib.Xcp_GetSegmentFreezeState(0x00) == 0
    assert handle.lib.Xcp_GetSegmentFreezeState(0x05) == 0, 'out-of-range segments report FALSE'


def test_set_segment_mode_rejects_freeze_when_it_is_not_supported():
    handle = freeze_handle(freeze_supported=False)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE6, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)


@pytest.mark.parametrize('pid', (0xE5, 0xE6))
def test_segment_mode_commands_reject_an_unknown_segment(pid):
    handle = freeze_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x05)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('segment_count', (1, 2, 5))
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_pag_processor_info_reports_the_configured_segment_count(max_cto, segment_count):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1: MAX_SEGMENT."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=max_cto,
                                   segments=[segment(name='S{}'.format(i), pages=[page()])
                                             for i in range(segment_count)]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE9,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] == segment_count


@pytest.mark.parametrize('freeze_supported, expected', ((False, 0x00), (True, 0x01)))
def test_get_pag_processor_info_reports_freeze_supported(freeze_supported, expected):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1: PAG_PROPERTIES bit 0."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   freeze_supported=freeze_supported,
                                   segments=[segment(pages=[page()])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE9,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[2] == expected

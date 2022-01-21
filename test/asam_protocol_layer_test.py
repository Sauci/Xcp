#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('payload', ((0xFF,),))
def test_command_connect_raises_e_asam_invalid_cto_packet_if_payload_size_is_too_short(payload):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_ASAM_INVALID_CTO_PACKET'))


@pytest.mark.parametrize('mode', range(0x02, 0xFF))
def test_command_connect_raises_e_asam_invalid_cto_parameter_if_a_parameter_is_not_in_allowed_range(mode):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, mode)))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_ASAM_INVALID_CTO_PARAMETER'))

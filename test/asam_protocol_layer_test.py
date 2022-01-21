#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('payload', ((0xFF,),))
def test_connect_command_raises_e_asam_invalid_cto_packet_if_payload_size_is_too_short(payload):
    handle = XcpTest(DefaultConfig())
    handle.lib.Xcp_CanIfRxIndication(0, handle.get_pdu_info(payload))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_ASAM_INVALID_CTO_PACKET'))

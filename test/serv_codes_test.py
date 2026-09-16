#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


def test_service_reset_reaches_the_master_as_a_serv_packet():
    """XCP part 2 - Protocol Layer Specification 1.1/1.3's SERV_RESET (0x00), "Slave requesting to
    be reset", carried by 1.1/1.1.3.5's SERV packet: PID 0xFC at position 0, the service request
    code at position 1. Two bytes, no data.

    It requests a reset OF the slave BY the master, so this changes no module state -- a slave
    acting on its own request would be answering a question nobody asked it (DD140)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_RequestServiceReset() == handle.define('E_OK')

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frame = handle.can_if_transmit.call_args[0][1]
    assert tuple(frame.SduDataPtr[0:2]) == (0xFC, 0x00), 'SERV_RESET'
    assert frame.SduLength == 0x02
    handle.det_report_error.assert_not_called()

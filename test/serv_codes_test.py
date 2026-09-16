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


def test_service_text_reaches_the_master_with_its_terminator():
    """1.1/1.3's SERV_TEXT (0x01): "The remaining data bytes of the packet contain plain ASCII text
    ... The text must be null terminated to indicate the end of the overall packet." The terminator
    is part of the payload, so "Hey\\0" is four bytes and the frame is 2 + 4."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    text = (0x48, 0x65, 0x79, 0x00)  # "Hey\0"
    assert handle.lib.Xcp_SendServiceText(text, len(text)) == handle.define('E_OK')

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frame = handle.can_if_transmit.call_args[0][1]
    assert tuple(frame.SduDataPtr[0:6]) == (0xFC, 0x01) + text
    assert frame.SduLength == 0x06
    handle.det_report_error.assert_not_called()


@pytest.mark.parametrize('text, expected_det', (
    (None, 'XCP_E_PARAM_POINTER'),
    ((), 'XCP_E_SERVICE_TEXT_INVALID'),
    ((0x48, 0x65), 'XCP_E_SERVICE_TEXT_INVALID'),
    ((0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x00), 'XCP_E_SERVICE_TEXT_INVALID'),
), ids=('null pointer', 'zero length', 'no terminator', 'longer than MAX_CTO'))
def test_service_text_refuses_what_it_cannot_transmit(text, expected_det):
    """Each rejection asserts three things: E_NOT_OK returned, the right Det id reported, and that
    NOTHING was transmitted. The third is the one this codebase keeps having to learn -- D18's
    Finding 4, GET_SEED, SHORT_UPLOAD and the event frame length all survived because tests
    asserted payload bytes or Det without asserting what reached the transport.

    MAX_CTO is 8 here, so a SERV_TEXT payload has 6 bytes to occupy: the 8-byte case is one over."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    transmit_calls = handle.can_if_transmit.call_count

    if text is None:
        result = handle.lib.Xcp_SendServiceText(handle.ffi.NULL, 4)
    else:
        result = handle.lib.Xcp_SendServiceText(text, len(text))

    handle.lib.Xcp_MainFunction()

    assert result == handle.define('E_NOT_OK')
    assert handle.can_if_transmit.call_count == transmit_calls, 'nothing may reach the transport'
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY, handle.define(expected_det))


def test_service_text_refuses_more_than_the_queue_entry_holds():
    """The second bound, which the MAX_CTO one does not imply: XCP_EVENT_USER_DATA_SIZE is 16 by
    default while MAX_CTO here is 128, so this text fits the frame and not the queue entry."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=128))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    transmit_calls = handle.can_if_transmit.call_count
    text = tuple([0x41] * 16) + (0x00,)  # 17 bytes: fits MAX_CTO 128, exceeds the 16-byte entry

    assert handle.lib.Xcp_SendServiceText(text, len(text)) == handle.define('E_NOT_OK')

    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == transmit_calls
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY,
                                                    handle.define('XCP_E_SERVICE_TEXT_INVALID'))

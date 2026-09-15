#!/usr/bin/env python
# -*- coding: utf-8 -*-

# see http://www.sunshine2k.de/coding/javascript/crc/crc_js.html

import ctypes

import crcmod
import zlib
import crcmod.predefined
import pytest

from .parameter import *
from .conftest import XcpTest

from unittest.mock import ANY


@pytest.mark.parametrize('sdu_length, sdu_data', [(0x03, (0xF1, 0x01, 0x02)),
                                                  (0x04, (0xF1, 0x01, 0x02, 0x03)),
                                                  (0x05, (0xF1, 0x01, 0x02, 0x03, 0x04)),
                                                  (0x06, (0xF1, 0x01, 0x02, 0x03, 0x04, 0x05)),
                                                  (0x07, (0xF1, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06)),
                                                  (0x08, (0xF1, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07))])
def test_user_cmd_function_is_called_with_received_pdu_info(sdu_length, sdu_data):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(sdu_data))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.xcp_user_cmd_function.call_args[0][0].SduLength == sdu_length
    assert tuple(handle.xcp_user_cmd_function.call_args[0][0].SduDataPtr[0:sdu_length]) == sdu_data


@pytest.mark.parametrize('sdu_length, sdu_data', [(0x01, (0x01,)),
                                                  (0x02, (0x01, 0x02)),
                                                  (0x03, (0x01, 0x02, 0x03)),
                                                  (0x04, (0x01, 0x02, 0x03, 0x04)),
                                                  (0x05, (0x01, 0x02, 0x03, 0x04, 0x05)),
                                                  (0x06, (0x01, 0x02, 0x03, 0x04, 0x05, 0x06)),
                                                  (0x07, (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07)),
                                                  (0x08, (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08))
                                                  ])
def test_user_cmd_function_returns_the_user_defined_buffer(sdu_length, sdu_data):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = sdu_length
        for i in range(len(sdu_data)):
            p_res_err_pdu_info[0].SduDataPtr[i] = sdu_data[i]
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.can_if_transmit.call_args[0][1].SduLength == sdu_length
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:sdu_length]) == sdu_data


def test_user_cmd_function_calls_det_with_err_invalid_pointer_if_no_user_cmd_function_is_defined():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function=None))

    def xcp_user_cmd_function(_p_cmd_pdu_info, _p_res_err_pdu_info):
        return 0

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_PARAM_POINTER'))


def test_user_cmd_refuses_a_response_longer_than_max_cto():
    """The integrator's callback is the only place a response length reaches this module from
    outside, and nothing checked it: Xcp_DTOCmdStdUserCmd finalized whatever SduLength came back, so
    a frame longer than the 2..MAX_CTO-1 layout of XCP part 2 - Protocol Layer Specification
    1.1/1.1.3.3 reached CanIf. Refused rather than truncated (DD129): a user-defined payload carries
    no length field, so a clamped response is indistinguishable from a complete one."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = 0x09
        for i in range(0x09):
            p_res_err_pdu_info[0].SduDataPtr[i] = 0xAA
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4])

    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    # The length is asserted at the mock because SduDataPtr always holds a full MAX_CTO frame padded
    # with trailingValue, so bytes 2-3 are readable whether or not the module wrote them.
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0006, \
        'expected XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG'
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_USER_CMD_RESPONSE_TOO_LONG'))


def test_user_cmd_transmits_a_response_exactly_at_max_cto():
    """The boundary the refusal above must not swallow. MAX_CTO itself is a legal length -- XCP part
    2 - Protocol Layer Specification 1.1/1.1.3.3 ends the payload area at MAX_CTO-1, so a packet
    whose SduLength equals MAX_CTO occupies positions 0..MAX_CTO-1 exactly. An off-by-one in the
    comparison shows here and nowhere else."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = 0x08
        for i in range(0x08):
            p_res_err_pdu_info[0].SduDataPtr[i] = i
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.can_if_transmit.call_args[0][1].SduLength == 0x08
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8]) == (0, 1, 2, 3, 4, 5, 6, 7)
    handle.det_report_error.assert_not_called()

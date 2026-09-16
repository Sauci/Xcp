#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest


def test_a_zero_length_user_cmd_response_is_refused_rather_than_transmitted():
    """DD136. Xcp_DTOCmdStdUserCmd finalizes at whatever length the integrator's callback set, and
    DD129 bounded that only from above. A callback returning E_OK with SduLength 0 therefore reached
    Xcp_FinalizeResPacket(0, ...) and was transmitted as a frame with no readable PID.

    This is also the live path that makes the invariant guard a reachable branch rather than the
    kind of unenterable guard DD126 records this project deleting twice: it needs no handler defect,
    only an integrator mistake."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = 0x00
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT -- loads the shared buffer with an 8-byte positive answer.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD, whose callback writes nothing and claims length 0.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4])

    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0007, \
        'expected XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN'
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_RESPONSE_NOT_WRITTEN'))

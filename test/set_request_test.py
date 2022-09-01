#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


def test_set_request_activates_the_callback_function_call_until_finished():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    return_values = (r for r in [handle.define('E_NOT_OK'), handle.define('E_NOT_OK'), handle.define('E_OK')])

    def store_calibration_data_to_non_volatile_memory(p_success):
        p_success[0] = handle.define('E_OK')
        return next(return_values)

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = store_calibration_data_to_non_volatile_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_REQUEST
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFD, 0x03)

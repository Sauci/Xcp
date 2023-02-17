#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from unittest.mock import ANY


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


@pytest.mark.parametrize('event_queue_size', [2, 4, 8, 16, 32])
def test_set_request_calls_det_with_err_event_queue_full_if_no_event_is_sent(event_queue_size):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, event_queue_size=event_queue_size))

    def store_calibration_data_to_non_volatile_memory(p_success):
        p_success[0] = handle.define('E_OK')
        return handle.define('E_OK')

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = store_calibration_data_to_non_volatile_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    for _ in range(event_queue_size):
        # SET_REQUEST
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_MAIN_FUNCTION_API_ID'),
                                                    handle.define('XCP_E_EVENT_QUEUE_FULL'))


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_set_request_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x08))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0x08:max_cto]) == remaining_zeros

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


@pytest.mark.parametrize('event_queue_size', [4, 8, 16, 32])
# event_queue_size=2 (capacity 1) is deliberately excluded: the drained-but-still-momentarily-
# unconfirmed chain can transiently hold two events at once (the previous one, not yet popped,
# and the one this iteration just pushed) before settling back down. A capacity of 1 cannot
# absorb that transient peak and still, correctly, reports XCP_E_EVENT_QUEUE_FULL for it -- that
# is a fact about a razor-thin capacity, not about events accumulating without bound, which is
# what this test is about. Verified empirically: [4, 8, 16, 32] never report it; [2] does.
def test_set_request_events_are_drained_by_the_confirmation_and_never_fill_the_queue(event_queue_size):
    """D16. Before the confirmation chained the next transmission, a queued EV_STORE_CAL event
    only left once a *later*, separate Xcp_MainFunction call found the module idle -- so
    SET_REQUEST issued faster than that filled the event queue and Det reported
    XCP_E_EVENT_QUEUE_FULL. That laziness was the defect this task fixes. Now the confirmation
    itself starts the next transmission, so the moment the CTO response ahead of it in the single
    in-flight slot is confirmed, the queued event is drained through that same slot -- it no
    longer waits for a separate idle Xcp_MainFunction call, and repeated SET_REQUESTs no longer
    fill the queue, regardless of event_queue_size. Coverage for XCP_E_EVENT_QUEUE_FULL moves to
    Task 16, whose DAQ overload path is not gated on CTO busy and can still genuinely fill it."""
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

    # (0xFD, 0x03) = XCP_PID_EVENT, XCP_EVENT_STORE_CAL (Xcp_Internal.h -- not reachable via
    # handle.define, per this task's ruling 3, so the literals are used with this comment).
    event_frames = [call for call in handle.can_if_transmit.call_args_list
                    if tuple(call[0][1].SduDataPtr[0:2]) == (0xFD, 0x03)]
    assert len(event_frames) > 0, 'EV_STORE_CAL must actually reach CanIf_Transmit'

    queue_full_errors = [call for call in handle.det_report_error.call_args_list
                         if call[0][3] == handle.define('XCP_E_EVENT_QUEUE_FULL')]
    assert queue_full_errors == [], 'the confirmation chain must keep the event queue drained'


def test_an_unconfirmed_event_still_occupies_its_slot_so_a_new_push_can_fail():
    """Xcp_EventQueueGet peeks -- it does not advance `read`. An event selected for transmission
    stays counted as occupying its ring slot until Xcp_EventQueuePop runs in the confirmation.
    Combined with the ring's own full test (one slot always kept empty to tell full from empty),
    the usable capacity for a *new* push while one event is in flight, unconfirmed, is
    eventQueueSize - 2. At eventQueueSize == 2 that is zero: the second SET_REQUEST's push fails
    outright and Xcp_ReportError(..., XCP_E_EVENT_QUEUE_FULL) fires. This is unrelated to
    accumulation over many iterations -- it is a single push failing against a slot the ring has
    not yet been told is free -- and it survives Task 16, whose DAQ overload path pushes into the
    same ring."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, event_queue_size=2))

    def store_calibration_data_to_non_volatile_memory(p_success):
        p_success[0] = handle.define('E_OK')
        return handle.define('E_OK')

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = store_calibration_data_to_non_volatile_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    for _ in range(2):
        # SET_REQUEST
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert len([c for c in handle.det_report_error.call_args_list
                if c[0][3] == handle.define('XCP_E_EVENT_QUEUE_FULL')]) == 1


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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def test_the_confirmation_starts_the_next_transmission():
    """D16: a queued frame must not wait for the next Xcp_MainFunction."""
    handle = XcpTest(DefaultConfig(max_cto=8, slave_block_mode=True))
    connect(handle)

    handle.can_if_transmit.reset_mock()

    # UPLOAD of 20 elements at MAX_CTO 8 needs three frames.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 20)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1, 'the main function starts the first frame'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert handle.can_if_transmit.call_count == 2, 'the confirmation starts the second, unaided'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert handle.can_if_transmit.call_count == 3, 'and the third'


def test_a_refused_transmission_is_retried_by_the_main_function():
    handle = XcpTest(DefaultConfig())
    connect(handle)

    handle.can_if_transmit.reset_mock()
    handle.can_if_transmit.return_value = handle.define('E_NOT_OK')

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1

    handle.can_if_transmit.return_value = handle.define('E_OK')
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 2, 'nothing was stranded by the refusal'


def test_every_path_leaves_the_exclusive_area_it_entered():
    handle = XcpTest(DefaultConfig())
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert handle.sch_m_enter_xcp_dto_queue.call_count == handle.sch_m_exit_xcp_dto_queue.call_count
    assert handle.sch_m_enter_xcp_dto_queue.call_count > 0, 'the transmit path really did take the area'


def test_a_synchronous_confirmation_does_not_recurse_into_can_if_transmit():
    """DD13. A CanIf that confirms from inside CanIf_Transmit would otherwise recurse once per
    queued frame, and would re-enter CanIf_Transmit for the same PduId, which SWS_CANIF_00005
    forbids."""
    handle = XcpTest(DefaultConfig(max_cto=8, slave_block_mode=True))
    connect(handle)

    # connect() itself makes one un-instrumented can_if_transmit call for the CONNECT response,
    # before the synchronous side_effect below is installed; without this, that call inflates
    # call_count by one and the assertion below is checking the wrong thing.
    handle.can_if_transmit.reset_mock()

    depth = {'current': 0, 'max': 0}

    def confirming_transmit(pdu_id, pdu_info):
        depth['current'] += 1
        depth['max'] = max(depth['max'], depth['current'])
        handle.lib.Xcp_CanIfTxConfirmation(pdu_id, handle.define('E_OK'))
        depth['current'] -= 1
        return handle.define('E_OK')

    handle.can_if_transmit.side_effect = confirming_transmit

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 20)))
    handle.lib.Xcp_MainFunction()

    assert depth['max'] == 1, 'CanIf_Transmit was never entered from inside itself'
    assert handle.can_if_transmit.call_count == 3, 'all three frames still went out'
    assert handle.sch_m_enter_xcp_dto_queue.call_count == handle.sch_m_exit_xcp_dto_queue.call_count


def running_daq(handle, entries=1, daq_list=0, odts=1):
    """Writes `entries` entries into each of the first `odts` ODTs of `daq_list`, then starts it.

    SET_DAQ_PTR and WRITE_DAQ both answer ERR_DAQ_ACTIVE once the list is RUNNING
    (source/Xcp_Daq.c: Xcp_DTOCmdDaqSetDaqPtr, Xcp_DTOCmdDaqWriteDaq), so every ODT this helper is
    asked for must be configured before the one START_STOP_DAQ_LIST at the end -- calling this
    helper, or SET_DAQ_PTR, a second time afterwards cannot reach a second ODT. That is why odts
    is a loop inside one call rather than something the caller drives by calling this repeatedly.
    """
    def exchange(request):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    for odt in range(odts):
        exchange((0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) + (odt, 0x00))
        for index in range(entries):
            exchange((0xE1, 0xFF, 0x01, 0x00) +
                     tuple(u32_to_array(0x1000 + (odt * entries) + index, 'LITTLE_ENDIAN')))
    exchange((0xE0, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) +
             tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x01, 0x00))
    exchange((0xDE, 0x01) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')))


def test_a_burst_is_transmitted_in_full_without_the_main_function():
    """DD3 and the acceptance criterion it exists for: an aperiodic Xcp_MainFunction must not
    be able to stall measurement. All three ODTs are populated before the list starts (see
    running_daq's docstring for why that ordering matters), so one trigger queues a genuine
    three-frame burst."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=1),)))
    connect(handle)
    running_daq(handle, odts=3)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_count == 1, 'the trigger starts the chain itself'

    handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_OK'))
    handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_OK'))

    assert handle.can_if_transmit.call_count == 3, 'confirmations carried the rest, unaided'


def test_daq_frames_go_out_on_the_configured_pdu():
    handle = XcpTest(DefaultConfig(default_daq_dto_pdu_mapping=0x0009))
    connect(handle)
    running_daq(handle)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][0] == 0x0009


def test_a_daq_frames_failed_confirmation_leaves_it_at_the_head_of_the_ring_for_retry():
    """CanIf_Transmit is asynchronous, so a refusal reported through the confirmation --
    as opposed to through CanIf_Transmit's own synchronous return value, which
    test_a_refused_transmission_is_retried_by_the_main_function above already covers for the CTO
    arm -- must leave the frame at the head of the ring rather than drop it: Xcp_DaqQueuePop only
    runs on a successful confirmation. D16 means the very same confirmation call re-arms
    transmission, so the retried frame reaches CanIf again immediately, with identical content,
    with no separate Xcp_MainFunction call needed."""
    handle = XcpTest(DefaultConfig())
    connect(handle)
    running_daq(handle)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_count == 1
    first_call_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_NOT_OK'))

    assert handle.can_if_transmit.call_count == 2, \
        'the same confirmation call re-armed transmission and retried the frame, unaided'
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == first_call_data, \
        'the retried frame is byte-identical to the one that was refused -- nothing was dropped'


def test_a_command_response_overtakes_queued_measurement_data():
    """The master's time-out is running against the response; measurement traffic must not
    delay it."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=1),)))
    connect(handle)
    running_daq(handle)

    handle.can_if_transmit.return_value = handle.define('E_NOT_OK')
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.can_if_transmit.return_value = handle.define('E_OK')

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
    assert handle.can_if_transmit.call_args[0][0] == 0x0002, 'on the CTO PDU, not the DAQ one'


def test_a_full_ring_drops_the_frame_and_reports_one_overload_event():
    """DD6 and 1.1/1.8.6: the slave "must take care not to overload another cycle with this
    additional packet". Five ODTs sampled into a two-slot ring: two frames survive, three are
    dropped by one single trigger, and exactly one EV_DAQ_OVERLOAD -- not three -- must cover
    them."""
    handle = XcpTest(DefaultConfig(daq_queue_size=2,
                                   daqs=(daq(name='DAQ1', max_odt=5, max_odt_entries=1),),
                                   overload_indication='EVENT'))
    connect(handle)
    running_daq(handle, odts=5)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_count == 1, 'the trigger starts the chain itself'

    # Drain everything this one trigger queued -- the two surviving DAQ frames plus the one
    # overload event -- confirming each in turn, and record what CanIf actually saw for each.
    transmitted = []
    for _ in range(3):
        transmitted.append(tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]))
        handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_OK'))

    assert transmitted[0] == (0xFD, 0x06), \
        'the event arm outranks the DAQ arm: the overload event goes out before either ' \
        'surviving DAQ frame, not after'

    events = [frame for frame in transmitted if frame[0] == 0xFD]
    assert events == [(0xFD, 0x06)], 'exactly one EV_DAQ_OVERLOAD must cover all three drops'


def test_no_overload_event_when_indication_is_off():
    handle = XcpTest(DefaultConfig(daq_queue_size=1,
                                   daqs=(daq(name='DAQ1', max_odt=5, max_odt_entries=1),),
                                   overload_indication='NONE'))
    connect(handle)
    running_daq(handle, odts=5)

    handle.can_if_transmit.return_value = handle.define('E_NOT_OK')
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.can_if_transmit.return_value = handle.define('E_OK')
    handle.can_if_transmit.reset_mock()

    for _ in range(4):
        handle.lib.Xcp_MainFunction()
        if handle.can_if_transmit.call_args is not None:
            handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_OK'))

    assert all(call[0][1].SduDataPtr[0] != 0xFD for call in handle.can_if_transmit.call_args_list)


def test_a_full_event_queue_reports_full_from_the_daq_overload_path():
    """Coverage carried from Task 5 (test/set_request_test.py): XCP_E_EVENT_QUEUE_FULL was
    reachable only through SET_REQUEST, at a razor-thin event_queue_size=2, because the
    confirmation chain keeps that path's own queue drained (D16). Xcp_TriggerEventChannel is not
    gated on CTO busy or on any confirmation at all -- it is a vendor-extension API the
    integrator calls freely -- so calling it repeatedly against a one-slot DTO ring that nothing
    ever confirms (so it never drains) fills the event queue with EV_DAQ_OVERLOAD reports the
    same way SET_REQUEST used to fill it with EV_STORE_CAL."""
    handle = XcpTest(DefaultConfig(daq_queue_size=1, event_queue_size=2))
    connect(handle)
    running_daq(handle)

    for _ in range(10):
        handle.lib.Xcp_TriggerEventChannel(0)
        if handle.det_report_error.call_count > 0:
            break

    handle.det_report_error.assert_called_once_with(ANY, ANY,
                                                   handle.define('XCP_TRIGGER_EVENT_CHANNEL_API_ID'),
                                                   handle.define('XCP_E_EVENT_QUEUE_FULL'))

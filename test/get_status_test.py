#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


# Only STORE_CAL_REQ survives here. The cases that once drove STORE_DAQ_REQ (0b100) and
# CLEAR_DAQ_REQ (0b1000) through SET_REQUEST and asserted they appeared in the session status were
# asserting the defect: neither mode is fulfilled by any code, so the bit latched forever and, via
# the ERR_PGM_ACTIVE gate in Xcp_CanIfRxIndication, disabled most of the command set for the rest
# of the session. SET_REQUEST now refuses both; the tests below cover that.
@pytest.mark.parametrize('current_session_status_byte, set_request_mode_byte', ((0b00000000, 0b00000000),
                                                                                (0b00000001, 0b00000001)))
def test_get_status_returns_the_current_session_status_for_bytes_0_2_3(current_session_status_byte,
                                                                       set_request_mode_byte):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    def store_calibration_data_to_non_volatile_memory(p_success):
        p_success[0] = handle.define('E_NOT_OK')
        return handle.define('E_NOT_OK')

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = store_calibration_data_to_non_volatile_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_REQUEST
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, set_request_mode_byte, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_STATUS
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] == current_session_status_byte


def test_get_status_reports_a_session_configuration_id_of_zero_rather_than_a_placeholder():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3, bytes 4,5.

    This replaces a skipped placeholder that had stood as defect D9's marker (and misnamed the
    offsets as bytes 6,7). The id is written by SET_REQUEST with STORE_DAQ_REQ and held in
    non-volatile memory beside the stored DAQ lists; this module refuses STORE_DAQ_REQ and reports
    RESUME unsupported, so nothing is ever stored and 0 -- what the specification itself resets the
    id to on CLEAR_DAQ_REQ -- is the honest answer. It reported the fabricated constant 0xABCD
    until D9 was closed, which a master could not distinguish from a real stored id."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0x04:0x06]) == (0x00, 0x00)


@pytest.mark.parametrize('mode, name', ((0b00000100, 'STORE_DAQ_REQ'),
                                        (0b00001000, 'CLEAR_DAQ_REQ')))
def test_get_status_never_reports_a_request_no_code_can_fulfil(mode, name):
    """A request bit is cleared by the slave once the request is fulfilled (1.0/1.6.1.1.3). Nothing
    in this module fulfils the two non-volatile DAQ requests, so a bit that reached the session
    status would stay set for the rest of the session and GET_STATUS would report a store that was
    never going to complete. SET_REQUEST refuses them instead, which is what keeps this clear."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] == 0x00


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_status_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x06))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[6:max_cto]) == remaining_zeros


def test_daq_running_is_reported_while_a_list_is_started():
    """D15. 1.1/1.6.1.1.3: "at least one DAQ list has been started and is in data transfer mode".

    Pins the behaviour where GET_STATUS itself lives: start_stop_daq_list_test.py's
    test_the_session_status_reports_daq_running and clear_daq_list_test.py's
    test_clear_daq_list_updates_the_daq_running_session_status already cover the bit's
    transitions from each command that maintains it, but neither checks that a fresh session
    reports DAQ_RUNNING clear through GET_STATUS before any DAQ list exists -- the assertion the
    "Test quality" note calls out as proving nothing on its own unless paired with the
    set-after-start transition in the same test, which this does."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    def exchange(request):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
        return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert exchange((0xFD,))[1] & 0x40 == 0  # DAQ_RUNNING

    exchange((0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))  # SET_DAQ_PTR: DAQ list 0, ODT 0, entry 0
    exchange((0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))  # WRITE_DAQ
    exchange((0xDE, 0x01, 0x00, 0x00))  # START_STOP_DAQ_LIST: start, DAQ list 0

    assert exchange((0xFD,))[1] & 0x40 != 0  # DAQ_RUNNING

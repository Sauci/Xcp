#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-NV Task 1: SET_REQUEST's STORE_DAQ_REQ and CLEAR_DAQ_REQ, and their polled integrator
callbacks Xcp_StoreDaqConfiguration / Xcp_ClearDaqConfiguration (interface/Xcp.h).

Design doc: docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md (DD94-DD97).

DD95 is the hazard this whole task exists around: the ERR_PGM_ACTIVE gate in Xcp_CanIfRxIndication
refuses every command whose Xcp_CTOErrorMatrix row carries that bit -- 45 rows, DISCONNECT among
them -- for as long as any of the three session-status request bits is set. A request bit that
never clears is therefore a permanent, reconnect-only denial of service. The rule that avoids it,
copied from STORE_CAL_REQ's own pre-existing block in Xcp_MainFunction (source/Xcp.c): E_OK means
finished, whatever the status code says, so only E_NOT_OK holds the bit.
"""

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def exchange(handle, request, tx_pdu_ref=0x0001, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(tx_pdu_ref, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def test_set_request_accepts_store_daq_req_and_polls_the_store_callback():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)
    # E_NOT_OK: not yet finished. Keeps this test to its one job -- accepted, and the callback
    # reached -- without also queuing the completion event, which test_completion_clears_the_bit_
    # and_raises_the_matching_event_carrying_the_status_byte below owns.
    handle.xcp_store_daq_configuration.return_value = handle.define('E_NOT_OK')

    assert exchange(handle, (0xF9, 0b00000100, 0x00, 0x00))[0] == 0xFF

    assert handle.xcp_store_daq_configuration.called


def test_set_request_accepts_clear_daq_req_and_polls_the_clear_callback():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_clear_daq_configuration_api_enable=True))
    connect(handle)
    handle.xcp_clear_daq_configuration.return_value = handle.define('E_NOT_OK')

    assert exchange(handle, (0xF9, 0b00001000, 0x00, 0x00))[0] == 0xFF

    assert handle.xcp_clear_daq_configuration.called


@pytest.mark.parametrize('mode, mock_attr, api_enable_kwarg', (
        (0b00000100, 'xcp_store_daq_configuration', 'xcp_store_daq_configuration_api_enable'),
        (0b00001000, 'xcp_clear_daq_configuration', 'xcp_clear_daq_configuration_api_enable'),
))
def test_the_request_bit_stays_set_while_the_callback_has_not_finished(mode, mock_attr, api_enable_kwarg):
    """A callback returning E_NOT_OK is polled again on the next Xcp_MainFunction and the request
    bit stays set. Xcp_Internal is not reachable from the CFFI harness (global constraint 4), so
    this is observed through GET_STATUS byte 1 rather than the field itself."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **{api_enable_kwarg: True}))
    connect(handle)

    mock = getattr(handle, mock_attr)
    mock.return_value = handle.define('E_NOT_OK')

    exchange(handle, (0xF9, mode, 0x00, 0x00))  # poll #1: not yet finished
    handle.lib.Xcp_MainFunction()               # poll #2: still not finished

    assert mock.call_count == 2

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[1] & mode == mode


@pytest.mark.parametrize('mode, mock_attr, event_pid', (
        (0b00000100, 'xcp_store_daq_configuration', 0x02),  # EV_STORE_DAQ
        (0b00001000, 'xcp_clear_daq_configuration', 0x01),  # EV_CLEAR_DAQ
))
def test_completion_clears_the_bit_and_raises_the_matching_event_carrying_the_status_byte(mode, mock_attr, event_pid):
    """EV_STORE_DAQ is 0x02 and EV_CLEAR_DAQ is 0x01 -- counter-intuitive (the reverse of mode-bit
    order), so checked explicitly here rather than assumed; swapped, this is exactly what mutation
    3 (task-1-report.md) verifies. Each event carries the status byte as its one-byte payload,
    exactly as EV_STORE_CAL does (set_request_test.py)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True,
                                    xcp_clear_daq_configuration_api_enable=True))
    connect(handle)

    def finish_successfully(*args):
        args[-1][0] = 0x00  # zero status: a clean completion
        return handle.define('E_OK')

    getattr(handle, mock_attr).side_effect = finish_successfully

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    event_frames = [call for call in handle.can_if_transmit.call_args_list
                    if tuple(call[0][1].SduDataPtr[0:3]) == (0xFD, event_pid, 0x00)]
    assert len(event_frames) > 0

    # Drains the event this completion queued and chained onto the confirmation above (D16,
    # set_request_test.py), so the GET_STATUS exchange below is not racing a still-unconfirmed
    # frame. A no-op if nothing was actually left in flight (ONGOING_TRANSMIT_TYPE_NONE,
    # Xcp_CanIfTxConfirmation, source/Xcp.c).
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFD, 0x00, 0x00, 0x00))[1] & mode == 0x00


def test_a_completed_but_failed_store_daq_req_clears_the_bit_so_disconnect_is_not_refused():
    """DD95, the denial-of-service hazard this task exists to avoid, and the reason this test is
    the acceptance bar rather than a nicety: found live for STORE_CAL_REQ on an earlier branch
    (DD77/R1). The ERR_PGM_ACTIVE gate in Xcp_CanIfRxIndication refuses every command whose
    Xcp_CTOErrorMatrix row carries that bit -- 45 rows, DISCONNECT among them -- while any of the
    three request bits is set. E_OK means finished, whatever the status code says: a callback that
    completes but reports failure must still clear its bit, or the module wedges until the next
    CONNECT."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_store_daq_configuration_api_enable=True))
    connect(handle)

    def store_daq_configuration(session_configuration_id, p_status_code):
        p_status_code[0] = 0x01  # non-zero: failed, but E_OK still means "finished"
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000100, 0x00, 0x00))
    # Drains the queued EV_STORE_DAQ (see the comment in the completion test above) so DISCONNECT
    # below is not racing a still-unconfirmed frame.
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFE,))[0] == 0xFF


def test_a_completed_but_failed_clear_daq_req_clears_the_bit_so_disconnect_is_not_refused():
    """Same hazard as test_a_completed_but_failed_store_daq_req_clears_the_bit_so_disconnect_is_not_
    refused above, for CLEAR_DAQ_REQ."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_clear_daq_configuration_api_enable=True))
    connect(handle)

    def clear_daq_configuration(p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_clear_daq_configuration.side_effect = clear_daq_configuration

    exchange(handle, (0xF9, 0b00001000, 0x00, 0x00))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFE,))[0] == 0xFF


def test_a_completed_but_failed_store_cal_req_clears_the_bit_so_disconnect_is_not_refused():
    """DD96 regression pin, not a fix. This rule already holds for STORE_CAL_REQ (Xcp_MainFunction,
    source/Xcp.c -- 'E_OK means finished, whatever the status code says') but nothing tested it
    before this task: a later change narrowing the clear to a zero status code would pass every
    existing test silently. STORE_CAL_REQ's own store path is unchanged by this task."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    def store_calibration_data_to_non_volatile_memory(p_status_code):
        p_status_code[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = \
        store_calibration_data_to_non_volatile_memory

    exchange(handle, (0xF9, 0b00000001, 0x00, 0x00))
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert exchange(handle, (0xFE,))[0] == 0xFF


@pytest.mark.parametrize('mode, name', ((0b00000100, 'STORE_DAQ_REQ'),
                                        (0b00001000, 'CLEAR_DAQ_REQ')))
def test_set_request_refuses_the_daq_modes_when_their_api_flags_are_disabled(mode, name):
    """Widening SET_REQUEST's accepted mask (source/Xcp_Std.c) is conditional on the matching
    xcp_store_daq_configuration_api_enable / xcp_clear_daq_configuration_api_enable flag, so an
    unconfigured build answers exactly as it always has: ERR_OUT_OF_RANGE (XCP part 2 - Protocol
    Layer Specification 1.0/1.6.1.2.3). DefaultConfig() itself defaults both flags off
    (test/parameter.py) -- which is what keeps test/set_request_test.py's own
    test_set_request_refuses_the_non_volatile_daq_modes_it_cannot_fulfil and
    test/get_status_test.py's test_get_status_never_reports_a_request_no_code_can_fulfil passing
    unchanged."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    assert exchange(handle, (0xF9, mode, 0x00, 0x00))[0:2] == (0xFE, 0x22)

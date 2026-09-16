#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


def test_an_event_packet_is_transmitted_with_its_own_length():
    """Xcp_Internal.event.pdu_info.SduLength was assigned exactly once in the module -- to 0, at
    Xcp_Init. Xcp_TransmitOneFrame's event branch wrote SduDataPtr[0] and [1] and handed the PduInfo
    to CanIf without ever setting the length, so every EV_* packet went out as a zero-length frame
    and the event code never reached the bus. Measured before the fix: the buffer held (0xFD, 0x03)
    and SduLength was 0.

    That is every event this module has: EV_STORE_CAL, EV_CLEAR_DAQ, EV_STORE_DAQ, EV_DAQ_OVERLOAD,
    EV_RESUME_MODE and EV_CMD_PENDING -- the last built by SP4 precisely so a master restarts its
    time-out during deferred programming, which it cannot do from an empty frame.

    The whole suite was green because every event assertion reads SduDataPtr and none read
    SduLength. That is the same blind spot behind D18's Finding 4, GET_SEED and SHORT_UPLOAD; the
    assertions added to the event tests alongside this one are what close it rather than move it.

    XCP part 2 - Protocol Layer Specification 1.1/1.1.3.4 lays the EV packet out as the PID at 0,
    the event code at 1 and optional event information over 2..MAX_CTO-1. This module sends no
    information data, so its events are two bytes long."""
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

    # SET_REQUEST, whose deferred completion raises EV_STORE_CAL.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frame = handle.can_if_transmit.call_args[0][1]

    assert tuple(frame.SduDataPtr[0:2]) == (0xFD, 0x03), 'EV_STORE_CAL'
    assert frame.SduLength == 0x02, 'the event code must actually reach the bus'

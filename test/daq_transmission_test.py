#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

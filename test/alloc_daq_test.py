#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def dynamic_handle(**kwargs):
    handle = XcpTest(dynamic_config(**kwargs))
    connect(handle)
    return handle


def exchange(handle, request, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def test_alloc_daq_makes_lists_available():
    handle = dynamic_handle(daq_count=4)
    assert exchange(handle, (0xD5, 0x00, 0x02, 0x00))[0] == 0xFF
    assert exchange(handle, (0xE3, 0x00, 0x01, 0x00))[0] == 0xFF          # list 1 available
    assert exchange(handle, (0xE3, 0x00, 0x02, 0x00))[0:2] == (0xFE, 0x22)  # list 2 is not


def test_alloc_daq_accumulates_across_repeated_calls():
    """DD28. The specification forbids ALLOC_DAQ only after ALLOC_ODT and ALLOC_ODT_ENTRY, so a
    repeat from FREE or DAQ is permitted -- and each call therefore adds to what is allocated.
    Treating a repeat as a replacement would make the permitted repeat meaningless."""
    handle = dynamic_handle(daq_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    assert exchange(handle, (0xE3, 0x00, 0x02, 0x00))[0] == 0xFF          # three allocated
    assert exchange(handle, (0xE3, 0x00, 0x03, 0x00))[0:2] == (0xFE, 0x22)


def test_alloc_daq_refuses_more_lists_than_the_pool_holds():
    handle = dynamic_handle(daq_count=4)
    assert exchange(handle, (0xD5, 0x00, 0x05, 0x00))[0:2] == (0xFE, 0x30)
    # The rejected request left nothing allocated.
    assert exchange(handle, (0xE3, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22)

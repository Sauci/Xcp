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


def test_a_dynamic_build_has_no_valid_daq_lists_until_alloc_daq():
    """DD32. The spec's ALLOC_ODT range [MIN_DAQ, MIN_DAQ+DAQ_COUNT-1] is over what ALLOC_DAQ
    allocated, not over the configured pool, so a list inside the pool but not yet allocated is
    "not available" and answers ERR_OUT_OF_RANGE. One runtime count gives both models the right
    answer: it starts at daqCount under STATIC and at zero under DYNAMIC."""
    handle = dynamic_handle(daq_count=4)
    # CLEAR_DAQ_LIST on list 0, which the pool has room for but nothing has allocated.
    assert exchange(handle, (0xE3, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22)

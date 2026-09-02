#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(daqs=None, **kwargs):
    handle = XcpTest(DefaultConfig(daqs=daqs if daqs is not None
                                   else (daq(name='DAQ1', max_odt=2, max_odt_entries=3),),
                                   **kwargs))
    connect(handle)
    return handle


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def test_set_daq_ptr_accepts_a_valid_target():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.1"""
    handle = daq_handle()

    assert response(handle, (0xE2, 0x00, 0x00, 0x00, 0x01, 0x02))[0] == 0xFF


def test_set_daq_ptr_rejects_an_unknown_daq_list():
    handle = daq_handle()

    assert response(handle, (0xE2, 0x00, 0x01, 0x00, 0x00, 0x00)) == (0xFE, 0x22)


def test_set_daq_ptr_rejects_an_odt_beyond_the_list():
    handle = daq_handle()

    assert response(handle, (0xE2, 0x00, 0x00, 0x00, 0x02, 0x00)) == (0xFE, 0x22)


def test_set_daq_ptr_rejects_an_entry_beyond_the_odt():
    handle = daq_handle()

    assert response(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x03)) == (0xFE, 0x22)


def test_set_daq_ptr_reads_the_list_number_in_the_configured_byte_order():
    """3 DAQ lists are configured (valid indices 0..2). The request spells list 2 as
    (0x00, 0x02) in BIG_ENDIAN. Misreading those two bytes as LITTLE_ENDIAN would produce
    0x0200 (512), which is out of range for daqCount=3, so a byte-order bug turns the expected
    0xFF into (0xFE, 0x22) instead -- the response alone is a real check of which order was
    used."""
    handle = daq_handle(daqs=tuple(daq(name='DAQ{}'.format(i), max_odt=1, max_odt_entries=1)
                                   for i in range(1, 4)),
                        byte_order='BIG_ENDIAN')

    assert response(handle, (0xE2, 0x00, 0x00, 0x02, 0x00, 0x00))[0] == 0xFF


def test_set_daq_ptr_is_refused_while_the_list_is_running():
    """XCP part 2 - Protocol Layer Specification 1.1/1.7.3.2.4 lists ERR_DAQ_ACTIVE."""
    handle = daq_handle()
    rt = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]
    rt.daqList[0].mode = 0x40  # XCP_DAQ_LIST_MODE_RUNNING

    assert response(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00)) == (0xFE, 0x11)

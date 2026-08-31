#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Exercise the CAL and PAG commands at MAX_CTO values larger than 8.

The per-command test files all fix MAX_CTO at 8, the XCP-on-CAN value, while the commands that
predate them are parametrised over 8, 128 and 256. Two reasons that gap is worth closing rather
than leaving to inspection:

- `Xcp_FinalizeResPacket` pads every response with the trailing value up to MAX_CTO, so the
  response path of every command depends on MAX_CTO even when its own fields are fixed-size.
- `SHORT_DOWNLOAD` can carry `(MAX_CTO - 8) / AG` elements, which is exactly zero at MAX_CTO = 8.
  Every existing case therefore exercises only the degenerate configuration in which the command
  can move no data at all.
"""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect

large_max_ctos = [pytest.param(v, id='MAX_CTO = {:04X}h'.format(v)) for v in (128, 256)]


def exchange(handle, payload):
    """Send one command and return its response, leaving no transmission pending."""
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple(payload)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1

    response = handle.can_if_transmit.call_args[0][1].SduDataPtr
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    return response


def paging_handle(max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=max_cto,
                                   freeze_supported=True,
                                   segments=[segment(name='S0',
                                                     address=0x00400000,
                                                     length=0x1000,
                                                     pages=[page(), page()],
                                                     address_mappings=[
                                                         address_mapping(0x11111111, 0x22222222, 0x33333333)]),
                                             segment(name='S1', pages=[page(), page()])]))
    connect(handle)

    return handle


@pytest.mark.parametrize('max_cto', large_max_ctos)
def test_every_pag_command_answers_at_a_large_max_cto(max_cto):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3"""
    handle = paging_handle(max_cto)

    assert exchange(handle, (0xEB, 0x01, 0x00, 0x01))[0] == 0xFF, 'SET_CAL_PAGE'
    assert exchange(handle, (0xEA, 0x01, 0x00))[0] == 0xFF, 'GET_CAL_PAGE'

    response = exchange(handle, (0xE9,))
    assert tuple(response[0:3]) == (0xFF, 0x02, 0x01), 'GET_PAG_PROCESSOR_INFO'

    response = exchange(handle, (0xE8, 0x00, 0x00, 0x00, 0x00))
    assert response[0] == 0xFF, 'GET_SEGMENT_INFO'
    assert u32_from_array(bytes(response[4:8]), 'LITTLE_ENDIAN') == 0x00400000

    assert exchange(handle, (0xE7, 0x00, 0x00, 0x00))[0] == 0xFF, 'GET_PAGE_INFO'
    assert exchange(handle, (0xE6, 0x01, 0x00))[0] == 0xFF, 'SET_SEGMENT_MODE'

    response = exchange(handle, (0xE5, 0x00, 0x00))
    assert tuple((response[0], response[2])) == (0xFF, 0x01), 'GET_SEGMENT_MODE reports that FREEZE'

    assert exchange(handle, (0xE4, 0x00, 0x00, 0x01, 0x01))[0] == 0xFF, 'COPY_CAL_PAGE'


@pytest.mark.parametrize('max_cto', large_max_ctos)
def test_pag_errors_are_reported_at_a_large_max_cto(max_cto):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3"""
    handle = paging_handle(max_cto)

    response = exchange(handle, (0xEB, 0x01, 0x09, 0x00))
    assert tuple(response[0:2]) == (0xFE, 0x28), 'SET_CAL_PAGE, unknown segment'

    response = exchange(handle, (0xE8, 0x02, 0x00, 0x00, 0x09))
    assert tuple(response[0:2]) == (0xFE, 0x22), 'GET_SEGMENT_INFO, mapping index out of range'


@pytest.mark.parametrize('max_cto', large_max_ctos)
@pytest.mark.parametrize('ag', ('BYTE', 'WORD', 'DWORD'))
def test_every_cal_command_answers_at_a_large_max_cto(ag, max_cto):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2"""
    element_size = {'BYTE': 1, 'WORD': 2, 'DWORD': 4}[ag]
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=max_cto,
                                   address_granularity=ag,
                                   master_block_mode=True))
    connect(handle)

    exchange(handle, (0xF6, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))

    assert exchange(handle, [0xF0, 0x01] + [0x00] * (max_cto - 2))[0] == 0xFF, 'DOWNLOAD'
    assert exchange(handle, [0xEE] + [0x00] * (max_cto - 1))[0] == 0xFF, 'DOWNLOAD_MAX'

    # (MAX_CTO - 8) / AG elements, the first configuration in which SHORT_DOWNLOAD can carry any.
    capacity = (max_cto - 8) // element_size
    request = [0xED, capacity, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    assert exchange(handle, request + [0x00] * (capacity * element_size))[0] == 0xFF, 'SHORT_DOWNLOAD'

    request[1] = capacity + 1
    response = exchange(handle, request + [0x00] * ((capacity + 1) * element_size))
    assert tuple(response[0:2]) == (0xFE, 0x22), 'SHORT_DOWNLOAD one element over capacity'

    assert exchange(handle, [0xEC, 0x00, 0xFF, 0xFF, 0x00, 0x00] + [0x00] * (max_cto - 6))[0] == 0xFF, 'MODIFY_BITS'

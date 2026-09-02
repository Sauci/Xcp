#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1000, byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_PTR to (daq_list, odt, entry 0), then WRITE_DAQ one entry of `size` bytes. Asserts
    both steps were accepted -- a caller relying on a configured entry must not pass because the
    write silently failed."""
    assert response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) +
                    (odt, 0x00))[0] == 0xFF
    assert response(handle, (0xE1, 0xFF, size, 0x00) +
                    tuple(u32_to_array(address, byte_order)))[0] == 0xFF


def start_daq_list(handle, daq_list=0, mode=0x00, channel=0, prescaler=1, priority=0,
                   byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_LIST_MODE with `mode`, then START_STOP_DAQ_LIST(START). Asserts both steps were
    accepted."""
    assert response(handle, (0xE0, mode) + tuple(u16_to_array(daq_list, byte_order)) +
                    tuple(u16_to_array(channel, byte_order)) + (prescaler, priority))[0] == 0xFF
    assert response(handle, (0xDE, 0x01) + tuple(u16_to_array(daq_list, byte_order)))[0] == 0xFF


def test_pid_off_is_accepted_for_an_absolute_single_odt_list():
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('identification', ('RELATIVE_BYTE', 'RELATIVE_WORD', 'RELATIVE_WORD_ALIGNED'))
def test_pid_off_is_refused_unless_identification_is_absolute(identification):
    """1.1/1.1.2.1: 'Turning off the transmission of the Identification Field is only allowed if
    the Identification Field Type is absolute ODT number.'"""
    handle = XcpTest(DefaultConfig(identification_field_type=identification,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID'))


def test_pid_off_is_refused_for_a_multi_odt_list():
    """Without an identification field the transport layer must disambiguate, which 1.1.2.1 says
    requires 'only one ODT for each DAQ list'. This module gives a DAQ list exactly one TX PDU, so
    a second ODT would be indistinguishable from the first on the bus."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=1),)))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID'))


def test_a_pid_off_dto_carries_no_identification_field():
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1234)
    start_daq_list(handle, daq_list=0, mode=0x20)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][1].SduLength == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xA5


def test_pid_off_with_a_timestamp_puts_the_timestamp_at_offset_zero():
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE', timestamp=timestamp(size='WORD'),
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    handle.xcp_get_daq_timestamp.return_value = 0xBEEF
    configure_one_entry(handle, daq_list=0, odt=0, size=1)
    start_daq_list(handle, daq_list=0, mode=0x30)

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = handle.can_if_transmit.call_args[0][1].SduDataPtr
    assert tuple(frame[0:2]) == (0xEF, 0xBE)


@pytest.mark.parametrize('identification, expected', (('ABSOLUTE', 0x20),
                                                      ('RELATIVE_BYTE', 0x00),
                                                      ('RELATIVE_WORD', 0x00),
                                                      ('RELATIVE_WORD_ALIGNED', 0x00)))
def test_pid_off_supported_is_advertised_only_for_absolute_identification(identification, expected):
    handle = XcpTest(DefaultConfig(identification_field_type=identification))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDA,)))
    handle.lib.Xcp_MainFunction()

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x20) == expected

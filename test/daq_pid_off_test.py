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


def stop_daq_list(handle, daq_list=0, byte_order='LITTLE_ENDIAN'):
    """START_STOP_DAQ_LIST(STOP). SET_DAQ_LIST_MODE answers ERR_DAQ_ACTIVE for a running list, so
    a mode change after a start has to come through here first."""
    assert response(handle, (0xDE, 0x00) + tuple(u16_to_array(daq_list, byte_order)))[0] == 0xFF


def daq_list_mode(handle, daq_list=0):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[daq_list].mode


def test_pid_off_is_accepted_for_an_absolute_single_odt_list():
    """The response byte alone is not evidence here: connect() left 0xFF in that same buffer, so a
    handler that returned without assembling a response at all would leave it reading 0xFF. What
    makes this the acceptance half of DD20 is the second assertion -- PID_OFF actually reached the
    stored runtime mode, which is the only place Xcp_DaqSampleOdt consults when it decides whether
    to emit an identification field. Its sibling in set_daq_list_mode_test.py
    (test_set_daq_list_mode_accepts_timestamp_when_a_clock_is_configured) pairs the same two
    assertions for the TIMESTAMP bit, for the same reason."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    assert response(handle, (0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF
    assert (daq_list_mode(handle) & 0x20) != 0x00, 'PID_OFF reached the stored mode'


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
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1234)
    start_daq_list(handle, daq_list=0, mode=0x20)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][1].SduLength == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xA5


def test_pid_off_with_a_timestamp_puts_the_timestamp_at_offset_zero():
    """1.1/1.1.2.2 puts the timestamp directly after the identification field, so with no
    identification field it starts at offset 0. SduLength is asserted too: the two timestamp bytes
    at 0..1 do not by themselves say that nothing preceded them -- a frame that still carried the
    identification field and merely happened to hold 0xEF, 0xBE at the front would satisfy the byte
    assertion alone. Three bytes total, one entry of one byte plus the WORD timestamp, is what
    says the identification field is absent."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE', timestamp=timestamp(size='WORD'),
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    handle.xcp_get_daq_timestamp.return_value = 0xBEEF
    configure_one_entry(handle, daq_list=0, odt=0, size=1)
    start_daq_list(handle, daq_list=0, mode=0x30)

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = handle.can_if_transmit.call_args[0][1]
    assert frame.SduLength == 3, 'a WORD timestamp and one one-byte entry, and nothing before them'
    assert tuple(frame.SduDataPtr[0:2]) == (0xEF, 0xBE)


def test_clearing_pid_off_makes_the_identification_field_reappear():
    """The other direction of DD20, which nothing covered: every other test here either sets
    PID_OFF or is refused it, so a handler that latched the bit on and never cleared it -- or a
    sampler that dropped the identification field for every list once any list had asked -- would
    have gone unnoticed. The list is stopped in between because SET_DAQ_LIST_MODE answers
    ERR_DAQ_ACTIVE while it runs.

    FIRST_PID is read from the configuration rather than assumed to be 0: it is assigned by the
    slave at generation time (1.1/1.6.4.1.1.4), and hard-coding it here would pin an implementation
    detail this test is not about."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1234)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    start_daq_list(handle, daq_list=0, mode=0x20)
    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][1].SduLength == 1, 'no identification field'
    handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_OK'))

    stop_daq_list(handle, daq_list=0)
    start_daq_list(handle, daq_list=0, mode=0x00)
    assert (daq_list_mode(handle) & 0x20) == 0x00, 'PID_OFF cleared from the stored mode'

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = handle.can_if_transmit.call_args[0][1]
    assert frame.SduLength == 2, 'the absolute ODT number is back in front of the data'
    assert frame.SduDataPtr[0] == handle.lib.Xcp_Ptr.config.daqList[0].firstPid
    assert frame.SduDataPtr[1] == 0xA5


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

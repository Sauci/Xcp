#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'), daq(name='DAQ2')), **kwargs))
    connect(handle)
    return handle


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def set_mode(handle, mode=0x00, daq_list=0, channel=0, prescaler=1, priority=0,
             byte_order='LITTLE_ENDIAN'):
    return response(handle, (0xE0, mode) + tuple(u16_to_array(daq_list, byte_order)) +
                    tuple(u16_to_array(channel, byte_order)) + (prescaler, priority))


def fill_odt_zero_to_capacity(handle, daq_list=0, byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_PTR to ODT 0 entry 0, then WRITE_DAQ one byte at a time -- relying on the pointer's
    auto post-increment within the ODT (1.1/1.6.4.1.1.2) -- until the ODT holds odtEntrySizeDaq
    bytes, the same MAX_ODT_ENTRY_SIZE_DAQ GET_DAQ_RESOLUTION_INFO reports. Asserts capacity was
    actually reached: a helper that silently filled less would make a caller relying on a full
    ODT 0 pass for the wrong reason."""
    capacity = handle.lib.Xcp_Ptr.general.odtEntrySizeDaq

    assert response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) +
                    (0x00, 0x00))[0] == 0xFF

    for _ in range(capacity):
        assert response(handle, (0xE1, 0xFF, 0x01, 0x00) +
                        tuple(u32_to_array(0xDEADBEEF, byte_order)))[0] == 0xFF

    used = sum(handle.lib.Xcp_Ptr.config.daqList[daq_list].odt[0].odtEntry[idx].length
              for idx in range(handle.lib.Xcp_Ptr.config.daqList[daq_list].maxOdtEntries))
    assert used == capacity, 'fill_odt_zero_to_capacity only reached {} of {} bytes'.format(used, capacity)


def test_set_daq_list_mode_stores_channel_prescaler_and_priority():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.3"""
    handle = daq_handle()

    assert set_mode(handle, daq_list=1, channel=0, prescaler=4, priority=0)[0] == 0xFF

    rt = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]
    assert rt.daqList[1].eventChannelNumber == 0
    assert rt.daqList[1].prescaler == 4
    assert rt.daqList[1].priority == 0
    assert rt.daqList[1].prescalerCounter == 0, 'a mode change restarts the division'


@pytest.mark.parametrize('mode, name', ((0x01, 'DIRECTION = STIM'),
                                        (0x10, 'TIMESTAMP'),
                                        (0x20, 'PID_OFF'),
                                        (0x40, 'bit 6, ALTERNATING in 1.1'),
                                        (0x80, 'bit 7')))
def test_set_daq_list_mode_rejects_every_unimplemented_mode_bit(mode, name):
    """DD9: 1.7.3.2.4 lists ERR_MODE_NOT_VALID for this command and that is what these are."""
    handle = daq_handle()

    assert set_mode(handle, mode=mode) == (0xFE, 0x27), name


@pytest.mark.parametrize('mode', (0x02, 0x04, 0x08))
def test_set_daq_list_mode_tolerates_the_bits_1_0_marks_dont_care(mode):
    handle = daq_handle()

    assert set_mode(handle, mode=mode)[0] == 0xFF


def test_set_daq_list_mode_rejects_an_unknown_daq_list():
    handle = daq_handle()

    assert set_mode(handle, daq_list=2) == (0xFE, 0x22)


def test_set_daq_list_mode_rejects_an_unknown_event_channel():
    handle = daq_handle()

    assert set_mode(handle, channel=1) == (0xFE, 0x22)


def test_set_daq_list_mode_is_refused_while_the_list_is_running():
    handle = daq_handle()
    # handle.define() resolves macros visible to interface/Xcp.h's preprocess; this one lives in
    # source/Xcp_Internal.h only, so it is spelled out literally here.
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode = 0x40  # XCP_DAQ_LIST_MODE_RUNNING

    assert set_mode(handle) == (0xFE, 0x11)


def test_set_daq_list_mode_rejects_a_zero_prescaler():
    """1.1/1.6.4.1.1.3: "Without reduction, the prescaler value must equal 1"; 0 divides a
    raster to nothing."""
    handle = daq_handle()

    assert set_mode(handle, prescaler=0) == (0xFE, 0x22)


def test_set_daq_list_mode_rejects_a_prescaler_above_one_when_unsupported():
    handle = daq_handle(prescaler_supported=False)

    assert set_mode(handle, prescaler=1)[0] == 0xFF
    assert set_mode(handle, prescaler=2) == (0xFE, 0x22)


def test_set_daq_list_mode_rejects_a_priority_above_zero():
    """1.1/1.6.4.1.1.3: "If the ECU doesn't support the prioritization of DAQ lists, a DAQ list
    priority > 0 is not allowed and will be indicated by returning ERR_OUT_OF_RANGE"."""
    handle = daq_handle()

    assert set_mode(handle, priority=1) == (0xFE, 0x22)
    assert set_mode(handle, priority=0xFF) == (0xFE, 0x22)


def test_set_daq_list_mode_reads_words_in_the_configured_byte_order():
    handle = daq_handle(byte_order='BIG_ENDIAN')

    assert set_mode(handle, daq_list=1, byte_order='BIG_ENDIAN')[0] == 0xFF
    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[1].prescaler == 1


def test_set_daq_list_mode_accepts_timestamp_when_a_clock_is_configured():
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size='WORD')))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x10, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
    # XCP_DAQ_LIST_MODE_TIMESTAMP (GET_DAQ_LIST_MODE layout, 1.1/1.6.4.1.2.6): accepting the
    # request is not enough on its own -- Task 5 reads this stored bit to decide whether to
    # timestamp the DTO, so the request must actually reach the runtime mode.
    assert (handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode & 0x10) != 0x00


def test_set_daq_list_mode_refuses_timestamp_without_a_clock():
    """ERR_MODE_NOT_VALID, not ERR_OUT_OF_RANGE: the mode is unsupported by this build, which is
    exactly what 1.7.3.2.4 lists the code for (DD9)."""
    handle = XcpTest(DefaultConfig())
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x10, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID'))


def test_enabling_timestamp_is_refused_when_odt_zero_is_already_full():
    """The master may write entries before setting the mode. MAX_ODT_ENTRY_SIZE_DAQ, which
    GET_DAQ_RESOLUTION_INFO reports, does not change; the timestamp reduces ODT 0's budget, so an
    ODT 0 already filled to that reported maximum can no longer carry a timestamp.
    ERR_OUT_OF_RANGE, whose prescribed master action -- retry other parameter -- is exactly the
    recovery available: drop an entry, or leave the timestamp off."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size='DWORD'),
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=8),)))
    connect(handle)
    fill_odt_zero_to_capacity(handle, daq_list=0)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x10, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))

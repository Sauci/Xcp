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


# TIMESTAMP (0x10) and PID_OFF (0x20) used to be in this list and are not any more: neither is
# unconditionally refused any longer. TIMESTAMP is refused only by daq_handle()'s no-clock fixture
# -- test_set_daq_list_mode_refuses_timestamp_without_a_clock (below) covers exactly that. PID_OFF
# is refused only for a non-ABSOLUTE identification field type, a multi-ODT list, or a TX PDU some
# other list shares. daq_handle() builds two lists that do share one, so PID_OFF is in fact refused
# under this fixture -- but for a reason this file does not name, which is worse than not testing
# it here at all; test/daq_pid_off_test.py's
# test_pid_off_is_refused_unless_identification_is_absolute,
# test_pid_off_is_refused_for_a_multi_odt_list and
# test_pid_off_is_refused_when_another_list_shares_this_list_s_tx_pdu cover the three refusal paths
# precisely and by name. Keeping a same-outcome entry here would only assert the same thing twice
# for three different reasons.
@pytest.mark.parametrize('mode, name', ((0x02, 'DIRECTION = STIM, bit 1'),
                                        (0x01, 'ALTERNATING, bit 0 in 1.1')))
def test_set_daq_list_mode_rejects_every_unimplemented_mode_bit(mode, name):
    """DD9: 1.7.3.2.4 lists ERR_MODE_NOT_VALID for this command and that is what these are."""
    handle = daq_handle()

    assert set_mode(handle, mode=mode) == (0xFE, 0x27), name


@pytest.mark.parametrize('mode', (0x04, 0x08, 0x40, 0x80))
def test_set_daq_list_mode_tolerates_the_bits_the_specification_marks_dont_care(mode):
    """Bits 2, 3, 6 and 7 carry an 'x' in the mode bit table of both 1.0 and 1.1, so a master may
    set them to anything and the slave ignores them. Bits 6 and 7 were previously refused, on the
    belief that 1.1 placed ALTERNATING in them -- it places it at bit 0."""
    handle = daq_handle()

    assert set_mode(handle, mode=mode)[0] == 0xFF


def test_set_daq_list_mode_refuses_a_stimulation_direction_rather_than_ignoring_it():
    """Regression. DIRECTION is bit 1 in both 1.0 and 1.1, but this module declared it at bit 0
    until the mode-bit positions were corrected. Bit 1 was covered by nothing, and the mask's own
    comment called bits 1-3 tolerated don't-cares -- so a master asking for STIM got a positive
    response, believed it had configured stimulation, and the slave went on sampling in the DAQ
    direction with no error anywhere. Silence was the whole defect, so this test asserts the error
    code rather than merely that the request did not succeed."""
    handle = daq_handle()

    assert set_mode(handle, mode=0x02) == (0xFE, 0x27)


def test_set_daq_list_mode_refuses_alternating_at_the_bit_the_specification_gives_it():
    """ALTERNATING is bit 0, read off 1.1's own bit table. It is refused rather than implemented:
    the capability is declared through DAQ_ALTERNATING_SUPPORTED in the A2L file, which this module
    does not emit, it pairs the list with a display event channel the protocol layer never gives
    slave-side semantics for, and 1.1 forbids combining it with TIMESTAMP."""
    handle = daq_handle()

    assert set_mode(handle, mode=0x01) == (0xFE, 0x27)


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


def test_set_daq_list_mode_clears_timestamp_when_a_later_request_omits_it():
    """The bit is fully re-specified on every request, not only ever settable: a master that turns
    TIMESTAMP back off must see it actually cleared from the stored mode. Every other test that
    reaches the clearing arm starts from mode 0, where clearing an already-clear bit proves
    nothing; this one starts from the bit set, so it is the only test that would fail if that arm
    were deleted, or its `&=` mistyped as `|=`."""
    handle = daq_handle(timestamp=timestamp(size='WORD'))

    assert set_mode(handle, mode=0x10)[0] == 0xFF
    assert (handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode & 0x10) != 0x00

    assert set_mode(handle, mode=0x00)[0] == 0xFF
    assert (handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode & 0x10) == 0x00


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


@pytest.mark.parametrize('max_odt_entries', (0, 4))
def test_enabling_timestamp_is_refused_for_a_list_with_no_odt(max_odt_entries):
    """`max_odt: 0` is a configuration config/xcp.schema.json accepts (`"minimum": 0`) and
    script/source_cfg.c.jinja2 emits as a zero-length `Xcp_OdtType` array, which GCC takes without
    complaint. Every other `odt[` access in source/Xcp_Daq.c is bounded by `maxOdt` or by
    SET_DAQ_PTR's own validation; the ODT-0 capacity check reached from here was the one that was
    not.

    The two parameters are not the same test twice, and only one of them discriminates without
    AddressSanitizer:

    - `max_odt_entries=0` is the deterministic half. Xcp_OdtUsedBytes' loop runs zero times, so it
      reads nothing out of bounds and returns a well-defined 0 -- which is below any budget, so
      before the maxOdt guard this request was *accepted*, arming a timestamp on a list with no
      ODT to carry it. Removing the guard turns this case from 0xFE into 0xFF.
    - `max_odt_entries=4` is the out-of-bounds read itself: Xcp_OdtUsedBytes dereferences
      `daqList[n].odt[0]` past the end of a zero-length array and walks whatever `odtEntry` pointer
      it finds there. Its answer is whatever memory follows, so this case cannot fail on the
      response byte alone; it needs `XCP_ASAN=1` (test/conftest.py's `_asan_flags`, off by default)
      to fail rather than quietly return one. It is kept because that is the case an ASAN run --
      or a different link order -- has to be able to reach by name.

    ERR_OUT_OF_RANGE, the same code the capacity check itself answers: a list with no ODT 0 has
    nowhere to put a timestamp, which is the capacity question with the answer "none"."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size='DWORD'),
                                   daqs=(daq(name='DAQ1', max_odt=0, max_odt_entries=max_odt_entries),)))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x10, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))

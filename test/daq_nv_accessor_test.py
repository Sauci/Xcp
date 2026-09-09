#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-NV Task 3 (design doc DD94, docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md):
the four read-only accessors an integrator implementing Xcp_StoreDaqConfiguration calls to learn
what to store. Built under DAQ_DYNAMIC and configured at runtime, mirroring
test/daq_dynamic_acceptance_test.py's own allocation sequence -- under DAQ_STATIC the accessors
would report generator constants and a broken handler could still look right."""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def dynamic_handle(**kwargs):
    kwargs.setdefault('xcp_daq_nv_accessors_api_enable', True)
    handle = XcpTest(dynamic_config(**kwargs))
    connect(handle)
    return handle


def exchange(handle, request, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def test_daq_list_selected_state_follows_start_stop_daq_list_select():
    """Selection is XCP_DAQ_LIST_MODE_SELECTED in the list's runtime mode byte
    (source/Xcp_Internal.h), set by START_STOP_DAQ_LIST's SELECT sub-mode (0x02,
    XCP_DAQ_START_STOP_MODE_SELECT) and left set until a START_STOP_SYNCH resets it, so it is
    still readable straight after the exchange below with no SYNCH in between. Two lists are
    allocated; list 1 is never selected, so a handler that reports TRUE for any valid list
    regardless of its own selection would still be caught by the assertions on it."""
    handle = dynamic_handle(daq_count=2, odt_count=1, odt_entries_count=1)
    exchange(handle, (0xD6,))                                   # FREE_DAQ
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))                   # ALLOC_DAQ(2)
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))             # ALLOC_ODT(list 0, 1)
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))       # ALLOC_ODT_ENTRY(list 0, odt 0, 1)
    exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))       # SET_DAQ_PTR(list 0, odt 0, entry 0)
    # WRITE_DAQ(bit_offset=0xFF/none, size=1, extension=0, address=0x1000): list 0 must hold at
    # least one written entry, or START_STOP_DAQ_LIST(Select) below answers ERR_DAQ_CONFIG.
    assert exchange(handle, (0xE1, 0xFF, 0x01, 0x00, 0x00, 0x10, 0x00, 0x00))[0] == 0xFF

    assert handle.lib.Xcp_GetDaqListSelectedState(0) == 0, 'unselected before START_STOP_DAQ_LIST(Select)'
    assert handle.lib.Xcp_GetDaqListSelectedState(1) == 0, 'a list allocated but never selected'

    assert exchange(handle, (0xDE, 0x02, 0x00, 0x00))[0] == 0xFF  # START_STOP_DAQ_LIST(Select, list 0)

    assert handle.lib.Xcp_GetDaqListSelectedState(0) == 1, 'selected after START_STOP_DAQ_LIST(Select)'
    assert handle.lib.Xcp_GetDaqListSelectedState(1) == 0, 'list 1 was never selected'


def test_daq_list_odt_count_reports_what_alloc_odt_allocated():
    handle = dynamic_handle(daq_count=1, odt_count=4, odt_entries_count=1)
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x03))[0] == 0xFF  # ALLOC_ODT(list 0, 3)

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 3


def test_odt_entry_count_is_reported_per_odt_not_shared_across_the_list():
    """Two ODTs with different counts, so a handler that always answers one ODT's count --
    ODT 0's, or any other single shared count -- fails at least one of the two assertions below."""
    handle = dynamic_handle(daq_count=1, odt_count=2, odt_entries_count=5)
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x02))                        # ALLOC_ODT(list 0, 2)
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x02))[0] == 0xFF  # ALLOC_ODT_ENTRY(list 0, odt 0, 2)
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x01, 0x05))[0] == 0xFF  # ALLOC_ODT_ENTRY(list 0, odt 1, 5)

    assert handle.lib.Xcp_GetOdtEntryCount(0, 0) == 2
    assert handle.lib.Xcp_GetOdtEntryCount(0, 1) == 5


def test_get_odt_entry_reports_what_write_daq_configured():
    """address=0, extension=0, length=0 and (if valid) bit_offset=0xFF are every ODT entry's
    power-up default (XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.1.1). The WRITE_DAQ
    below picks a value differing from all four defaults at once, so an accessor that left any one
    field un-copied -- including bitOffset, easy to miss since it alone is not a WRITE_DAQ
    parameter's most obvious use -- would still be caught."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))
    # WRITE_DAQ: bit_offset=3, size=1 (the BYTE granularity address_granularity=default requires
    # whenever bit_offset is not 0xFF), extension=2, address=0x12345678.
    assert exchange(handle, (0xE1, 0x03, 0x01, 0x02, 0x78, 0x56, 0x34, 0x12))[0] == 0xFF

    entry = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetOdtEntry(0, 0, 0, entry) == handle.define('E_OK')
    assert int(handle.ffi.cast('uintptr_t', entry.address)) == 0x12345678
    assert entry.bitOffset == 0x03
    assert entry.addressExtension == 0x02
    assert entry.length == 0x01


def test_accessors_refuse_a_list_number_at_or_past_the_allocated_count():
    """DD32's own rule: valid means allocated, not merely inside the configured pool. List 1 sits
    inside daq_count's pool but ALLOC_DAQ below hands out only list 0."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    exchange(handle, (0xD6,))
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF  # ALLOC_DAQ(1): only list 0 exists

    entry = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetDaqListSelectedState(1) == 0
    assert handle.lib.Xcp_GetDaqListOdtCount(1) == 0
    assert handle.lib.Xcp_GetOdtEntryCount(1, 0) == 0
    assert handle.lib.Xcp_GetOdtEntry(1, 0, 0, entry) == handle.define('E_NOT_OK')


def test_accessors_refuse_an_odt_number_past_the_list_own_count():
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF  # ALLOC_ODT(list 0, 1): only odt 0

    entry = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetOdtEntryCount(0, 1) == 0
    assert handle.lib.Xcp_GetOdtEntry(0, 1, 0, entry) == handle.define('E_NOT_OK')


def test_get_odt_entry_refuses_an_entry_number_past_the_odt_own_count():
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    # ALLOC_ODT_ENTRY(list 0, odt 0, 1): only entry 0 exists.
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF

    entry = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetOdtEntry(0, 0, 1, entry) == handle.define('E_NOT_OK')


def test_accessors_report_their_out_of_range_defaults_when_the_flag_is_disabled():
    """xcp_daq_nv_accessors_api_enable gates all four together (task brief step 3): a fully
    configured, selected list must still read back as though it does not exist when the flag is
    off, exactly as it does for a genuinely out-of-range argument above -- the flag exists
    precisely so an integrator who never implements Xcp_StoreDaqConfiguration pays nothing for it,
    and "pays nothing" must include "these four report nothing", not just "compiles smaller"."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1,
                            xcp_daq_nv_accessors_api_enable=False)
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))
    exchange(handle, (0xE1, 0x03, 0x01, 0x02, 0x78, 0x56, 0x34, 0x12))
    assert exchange(handle, (0xDE, 0x02, 0x00, 0x00))[0] == 0xFF  # START_STOP_DAQ_LIST(Select, list 0)

    entry = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetDaqListSelectedState(0) == 0
    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 0
    assert handle.lib.Xcp_GetOdtEntryCount(0, 0) == 0
    assert handle.lib.Xcp_GetOdtEntry(0, 0, 0, entry) == handle.define('E_NOT_OK')

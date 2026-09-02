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


def set_daq_ptr(handle, daq_list=0, odt=0, entry=0, byte_order='LITTLE_ENDIAN'):
    return response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) + (odt, entry))


def write_daq(handle, size=1, extension=0, address=0xDEADBEEF, bit_offset=0xFF,
              byte_order='LITTLE_ENDIAN'):
    return response(handle, (0xE1, bit_offset, size, extension) +
                    tuple(u32_to_array(address, byte_order)))


def write_daq_multiple(handle, entries, byte_order='LITTLE_ENDIAN'):
    """entries is a list of dicts with the same keys write_daq's kwargs use (bit_offset, size,
    extension, address) -- one BAD_ENTRIES value shared verbatim between write_daq and this
    function is what lets the parity test below issue "the same" bad element to both commands."""
    request = [0xC7, len(entries)]

    for one_entry in entries:
        request += [one_entry['bit_offset'], one_entry['size']]
        request += list(u32_to_array(one_entry['address'], byte_order))
        request += [one_entry['extension'], 0x00]

    return response(handle, tuple(request))


def read_back_entry(handle, daq_list=0, odt=0, entry=0):
    odt_entry = handle.lib.Xcp_Ptr.config.daqList[daq_list].odt[odt].odtEntry[entry]

    return {'address': int(handle.ffi.cast('uintptr_t', odt_entry.address)),
            'address_extension': odt_entry.addressExtension,
            'bit_offset': odt_entry.bitOffset,
            'size': odt_entry.length}


def _bad_entry(bit_offset=0xFF, size=1, extension=0, address=0):
    return {'bit_offset': bit_offset, 'size': size, 'extension': extension, 'address': address}


def _setup_pointer(handle):
    connect(handle)
    set_daq_ptr(handle, daq_list=0, odt=0, entry=0)


def _setup_pointer_after_a_filled_entry(handle):
    """odtEntrySizeDaq is MAX_DTO(8) - 1 for the default ABSOLUTE identification field, so 7
    bytes total. Filling entry 0 with 6 of those and then pointing at entry 1 leaves only 1 byte
    of budget for whatever comes next, so a 2-byte entry there overflows the ODT rather than any
    single-entry size limit."""
    connect(handle)
    set_daq_ptr(handle, daq_list=0, odt=0, entry=0)
    assert write_daq(handle, size=6)[0] == 0xFF
    set_daq_ptr(handle, daq_list=0, odt=0, entry=1)


# Three distinct branches of the shared Xcp_DaqApplyOdtEntry helper, each reached only once the
# DAQ pointer is valid (unlike an unconnected/unpositioned handle, which would trip the pointer
# check identically for every case here and never reach the branch each case names):
# - size_too_large: size (8) exceeds odtEntrySizeDaq (7).
# - bad_granularity: a real bit offset (0) demands size == granularity (1 for BYTE); 3 does not.
# - odt_would_overflow: the entry is individually legal, but 6 + 2 exceeds the 7-byte ODT budget.
BAD_ENTRIES = {
    'size_too_large': (_setup_pointer, _bad_entry(size=8)),
    'bad_granularity': (_setup_pointer, _bad_entry(bit_offset=0x00, size=3)),
    'odt_would_overflow': (_setup_pointer_after_a_filled_entry, _bad_entry(size=2)),
}


def test_write_daq_multiple_writes_every_element():
    handle = XcpTest(DefaultConfig(max_cto=0x40, xcp_write_daq_multiple_api_enable=True,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=4),)))
    connect(handle)
    set_daq_ptr(handle, daq_list=0, odt=0, entry=0)

    # Extensions are distinct, non-zero, and different from the trailing dummy (always 0x00) so
    # that reading the wrong byte of an element -- e.g. offset 7 (dummy) instead of offset 6
    # (address extension) -- shows up as a wrong address_extension rather than passing unnoticed.
    request = [0xC7, 0x02]
    request += [0xFF, 0x01, 0x11, 0x22, 0x33, 0x44, 0x03, 0x00]
    request += [0xFF, 0x01, 0x55, 0x66, 0x77, 0x88, 0x07, 0x00]
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple(request)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    entry0 = read_back_entry(handle, daq_list=0, odt=0, entry=0)
    assert entry0['address'] == 0x44332211
    assert entry0['address_extension'] == 0x03
    assert entry0['bit_offset'] == 0xFF
    assert entry0['size'] == 0x01

    entry1 = read_back_entry(handle, daq_list=0, odt=0, entry=1)
    assert entry1['address'] == 0x88776655
    assert entry1['address_extension'] == 0x07
    assert entry1['bit_offset'] == 0xFF
    assert entry1['size'] == 0x01


@pytest.mark.parametrize('bad', ('size_too_large', 'bad_granularity', 'odt_would_overflow'))
def test_write_daq_multiple_rejects_exactly_what_write_daq_rejects(bad):
    """1.6.4.1.2.1: 'In general WRITE_DAQ_MULTIPLE has the same restrictions as the WRITE_DAQ
    command.' Both commands run the same helper, and this test is what keeps that true: it asserts
    the two answer the same error code for the same offending entry, for three different branches
    of that shared helper (BAD_ENTRIES above) -- so a future change that re-implements one check for
    one command but not the other has three independent chances to be caught here, not one that
    happens to pass by both commands failing the same *earlier* check (e.g. an invalid pointer)
    regardless of which branch this test intended to exercise.

    single and multi are built from configurations that differ only in apis
    (xcp_write_daq_multiple_api_enable plays no part in source_rt), so XcpTest's rt_key cache
    (conftest.py: "keyed on ... a digest of
    [source_rt]") hands them the same compiled module -- constructing one rebinds that module's
    def_extern callbacks and Xcp_Ptr to itself. single is therefore fully used, single_error included,
    before multi is even constructed: interleaving the two (or constructing both up front) would have
    multi's construction steal single's callback registration out from under it, and
    single.can_if_transmit would never see the call at all."""
    setup, bad_entry = BAD_ENTRIES[bad]

    single = XcpTest(DefaultConfig(max_cto=0x40, daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=4),)))
    setup(single)
    single_error = write_daq(single, bit_offset=bad_entry['bit_offset'], size=bad_entry['size'],
                             extension=bad_entry['extension'], address=bad_entry['address'])

    multi = XcpTest(DefaultConfig(max_cto=0x40, xcp_write_daq_multiple_api_enable=True,
                                  daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=4),)))
    setup(multi)
    multi_error = write_daq_multiple(multi, [bad_entry])

    assert single_error == multi_error


def test_write_daq_multiple_refuses_to_cross_an_odt_border():
    """1.6.4.1.2.1: 'All DAQ entries within one WRITE_DAQ_MULTIPLE must be written into one ODT.
    WRITE_DAQ_MULTIPLE must not be used to write over ODT borders.'"""
    handle = XcpTest(DefaultConfig(max_cto=0x40, xcp_write_daq_multiple_api_enable=True,
                                   daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=2),)))
    connect(handle)
    set_daq_ptr(handle, daq_list=0, odt=0, entry=1)

    request = [0xC7, 0x02] + [0xFF, 0x01, 0, 0, 0, 0, 0, 0] * 2
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple(request)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))


def test_write_daq_multiple_rejects_a_length_that_disagrees_with_n():
    handle = XcpTest(DefaultConfig(max_cto=0x40, xcp_write_daq_multiple_api_enable=True,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=4),)))
    connect(handle)
    set_daq_ptr(handle, daq_list=0, odt=0, entry=0)

    request = [0xC7, 0x03] + [0xFF, 0x01, 0, 0, 0, 0, 0, 0]
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple(request)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_SYNTAX'))


def test_write_daq_multiple_is_refused_when_disabled():
    """xcp_write_daq_multiple_api_enable defaults to False in this test harness (see parameter.py
    for why); this pins that a disabled command answers ERR_CMD_UNKNOWN through the same generic
    ctoInfo-enable path every other optional command uses, not a bespoke one."""
    handle = XcpTest(DefaultConfig(max_cto=0x40, daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=4),)))
    connect(handle)

    assert write_daq_multiple(handle, []) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN'))

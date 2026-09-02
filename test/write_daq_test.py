#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_handle(max_odt=1, max_odt_entries=4, **kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=max_odt,
                                             max_odt_entries=max_odt_entries),),
                                   **kwargs))
    connect(handle)
    return handle


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


def entry(handle, odt=0, index=0):
    return handle.lib.Xcp_Ptr.config.daqList[0].odt[odt].odtEntry[index]


def test_write_daq_fills_the_entry_the_pointer_names():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2"""
    handle = daq_handle()
    set_daq_ptr(handle, entry=1)

    assert write_daq(handle, size=1, extension=3, address=0xDEADBEEF)[0] == 0xFF

    assert entry(handle, index=1).length == 1
    assert entry(handle, index=1).addressExtension == 3
    assert entry(handle, index=1).bitOffset == 0xFF
    assert int(handle.ffi.cast('uintptr_t', entry(handle, index=1).address)) == 0xDEADBEEF


def test_write_daq_post_increments_the_pointer_within_the_odt():
    """1.1/1.6.4.1.1.2: "auto post incremented to the next ODT entry within one and the same ODT".

    Xcp_Internal is not reachable from this CFFI harness (interface/Xcp.h does not include
    Xcp_Internal.h), so the post-increment is observed through its consequence instead: two
    distinct addresses landing in entries 0 and 1 is only possible if the pointer moved between
    the two calls."""
    handle = daq_handle()
    set_daq_ptr(handle)

    write_daq(handle, address=0x1000)
    write_daq(handle, address=0x2000)

    assert int(handle.ffi.cast('uintptr_t', entry(handle, index=0).address)) == 0x1000
    assert int(handle.ffi.cast('uintptr_t', entry(handle, index=1).address)) == 0x2000


def test_the_pointer_goes_invalid_past_the_last_entry_of_an_odt():
    """1.1/1.6.4.1.1.2 leaves it undefined there; DD10 makes that observable as an error.

    Xcp_Internal is not reachable from this CFFI harness, so invalidation is observed through
    its consequence: a third WRITE_DAQ against a two-entry ODT answers ERR_OUT_OF_RANGE."""
    handle = daq_handle(max_odt_entries=2)
    set_daq_ptr(handle)

    write_daq(handle)
    write_daq(handle)

    assert write_daq(handle) == (0xFE, 0x22)


def test_write_daq_without_a_pointer_is_refused():
    handle = daq_handle()

    assert write_daq(handle) == (0xFE, 0x22)


def test_write_daq_is_refused_while_the_list_is_running():
    """XCP part 2 - Protocol Layer Specification 1.1/1.7.3.2.4 lists ERR_DAQ_ACTIVE.

    XCP_DAQ_LIST_MODE_RUNNING lives in Xcp_Internal.h, which handle.define() cannot resolve
    (its cdef only reaches macros included from interface/Xcp.h), so the bit is spelled out
    literally here, the same way set_daq_ptr_test.py does it."""
    handle = daq_handle()
    set_daq_ptr(handle)
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode = 0x40  # XCP_DAQ_LIST_MODE_RUNNING

    assert write_daq(handle) == (0xFE, 0x11)


@pytest.mark.parametrize('size', (0, 8))
def test_write_daq_rejects_a_size_outside_the_odt_entry_limits(size):
    """MAX_ODT_ENTRY_SIZE_DAQ is MAX_DTO - 1 = 7 for ABSOLUTE at MAX_DTO 8."""
    handle = daq_handle()
    set_daq_ptr(handle)

    assert write_daq(handle, size=size) == (0xFE, 0x22)


@pytest.mark.parametrize('address_granularity, bad_size', (('WORD', 3), ('DWORD', 6)))
def test_write_daq_rejects_a_size_that_is_not_a_multiple_of_the_granularity(address_granularity,
                                                                           bad_size):
    """1.1/1.6.4.1.2.5: SizeOf(element) mod GRANULARITY_ODT_ENTRY_SIZE_DAQ = 0."""
    handle = daq_handle(address_granularity=address_granularity)
    set_daq_ptr(handle)

    assert write_daq(handle, size=bad_size) == (0xFE, 0x22)


def test_write_daq_stores_a_bit_offset_and_requires_the_granularity_size():
    """DD8: the slave validates BIT_OFFSET and stores it, but transmits the element unmasked."""
    handle = daq_handle()
    set_daq_ptr(handle)

    assert write_daq(handle, bit_offset=0x07, size=1)[0] == 0xFF
    assert entry(handle).bitOffset == 0x07


@pytest.mark.parametrize('bit_offset', (0x20, 0x7F, 0xFE))
def test_write_daq_rejects_an_undefined_bit_offset(bit_offset):
    handle = daq_handle()
    set_daq_ptr(handle)

    assert write_daq(handle, bit_offset=bit_offset) == (0xFE, 0x22)


def test_write_daq_rejects_a_bit_offset_whose_size_is_not_the_granularity():
    handle = daq_handle(address_granularity='WORD')
    set_daq_ptr(handle)

    assert write_daq(handle, bit_offset=0x03, size=4) == (0xFE, 0x22)


def test_write_daq_refuses_to_overfill_an_odt():
    """DD8. Four entries of two bytes need eight, but ABSOLUTE at MAX_DTO 8 leaves seven."""
    handle = daq_handle(max_odt_entries=4)
    set_daq_ptr(handle)

    assert write_daq(handle, size=2)[0] == 0xFF
    assert write_daq(handle, size=2)[0] == 0xFF
    assert write_daq(handle, size=2)[0] == 0xFF
    assert write_daq(handle, size=2) == (0xFE, 0x2A)


def test_write_daq_excludes_the_targeted_entrys_own_stale_length_from_the_capacity_check():
    """DD8: Xcp_OdtUsedBytes excludes the entry being (re)written from its own sum, so
    repositioning to an already-written entry and rewriting it with a different size weighs the
    new size against the OTHER entries only -- not against the entry's own stale length.

    At MAX_DTO 8 / ABSOLUTE, MAX_ODT_ENTRY_SIZE_DAQ is 7. Entry 0 first takes 5 bytes and entry 1
    takes 1 (6 of 7 used). Repositioning back to entry 0 and rewriting it with size 3:
    - Correct (excludes entry 0's own stale length): 1 (entry 1) + 3 = 4 <= 7, accepted.
    - Inverted condition (sums ONLY entry 0's own stale length, `==` instead of `!=`):
      5 (entry 0's stale 5, not the 1 entry 1 actually holds) + 3 = 8 > 7, wrongly rejected.
    - Exclusion dropped entirely (sums every entry unconditionally): 5 (entry 0's stale length,
      still uncounted-out) + 1 (entry 1) + 3 = 9 > 7, wrongly rejected.
    All three readings diverge on this data (5, 1, 3 was chosen so they would), so accepting here
    is evidence the exclusion is both present and correctly directed, not a coincidence of small
    numbers all fitting comfortably either way.

    This configuration (max_odt=1, max_odt_entries=4, otherwise every DefaultConfig default) is
    byte-identical to several sibling tests' in this file, e.g.
    test_write_daq_refuses_to_overfill_an_odt, and XcpTest/MockGen caches compiled modules by
    configuration hash: Xcp_Init resets Xcp_Rt and Xcp_Internal but never the config module's own
    ODT entry fields, so a sibling test's leftover entry lengths persist into this one. This
    test's margin is exact (7 vs 8) where its siblings' are not, so it is the first one actually
    sensitive to that leftover state -- entries 0 and 1 are about to be overwritten by the
    sequence below anyway, but entries 2 and 3 are not, so they are cleared explicitly first to
    make the sequence deterministic regardless of what ran before it."""
    handle = daq_handle(max_odt_entries=4)
    for index in range(4):
        entry(handle, index=index).length = 0

    set_daq_ptr(handle)

    assert write_daq(handle, size=5)[0] == 0xFF
    assert write_daq(handle, size=1)[0] == 0xFF

    set_daq_ptr(handle, entry=0)

    assert write_daq(handle, size=3)[0] == 0xFF
    assert entry(handle, index=0).length == 3

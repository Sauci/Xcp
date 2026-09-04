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


def test_alloc_odt_entry_gives_each_odt_its_own_count():
    """DD34. This is what the per-ODT entryCount exists for: the per-list maxOdtEntries cannot
    express one ODT holding four entries and another two."""
    handle = dynamic_handle(daq_count=1, odt_count=2, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x02))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x04))[0] == 0xFF
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x01, 0x02))[0] == 0xFF
    daq_list = handle.lib.Xcp_Ptr.config.daqList[0]
    assert (daq_list.odt[0].entryCount, daq_list.odt[1].entryCount) == (4, 2)


def test_alloc_odt_entry_accumulates_across_repeated_calls_to_the_same_odt():
    """DD28. The specification forbids ALLOC_ODT_ENTRY only after FREE and DAQ, so a repeat from
    ODT or ODT_ENTRY naming the same ODT is permitted -- and each call therefore adds to what is
    allocated, the same as ALLOC_DAQ and ALLOC_ODT. Distinct from
    test_alloc_odt_entry_gives_each_odt_its_own_count: that test names two different ODTs, both
    starting from zero, so it cannot tell an accumulate from a replace -- only a second call
    naming the same ODT can. Treating a repeat as a replacement would make the permitted repeat
    meaningless."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=8)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x03))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x02))[0] == 0xFF
    assert handle.lib.Xcp_Ptr.config.daqList[0].odt[0].entryCount == 5


def test_alloc_odt_entry_refuses_an_odt_the_list_does_not_have():
    handle = dynamic_handle(daq_count=1, odt_count=4, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x02))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x02, 0x01))[0:2] == (0xFE, 0x22)


def test_alloc_odt_entry_refuses_more_entries_than_one_odt_may_hold():
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x05))[0:2] == (0xFE, 0x30)


def test_alloc_odt_entry_refuses_a_list_that_was_never_allocated():
    """The DD32 rule ALLOC_ODT and ALLOC_DAQ already answer to: valid means allocated, not merely
    inside the configured pool. List 1 is inside the pool but ALLOC_DAQ only handed out list 0."""
    handle = dynamic_handle(daq_count=4, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    assert exchange(handle, (0xD3, 0x00, 0x01, 0x00, 0x00, 0x01))[0:2] == (0xFE, 0x22)


def test_alloc_odt_entry_before_any_alloc_odt_is_a_sequence_error():
    """Unlike ALLOC_ODT, which accepts a bare ALLOC_DAQ, ALLOC_ODT_ENTRY is accepted only from
    XCP_DAQ_ALLOC_ODT or XCP_DAQ_ALLOC_ODT_ENTRY (1.1/1.6.4.3.1.4) -- so both FREE and DAQ answer
    ERR_SEQUENCE."""
    handle = dynamic_handle(daq_count=1, odt_count=1)
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0:2] == (0xFE, 0x29)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0:2] == (0xFE, 0x29)


def test_alloc_odt_entry_blocks_alloc_odt_once_reached():
    """The closing step of the running-list FIRST_PID safety argument: once the state has reached
    XCP_DAQ_ALLOC_ODT_ENTRY, ALLOC_ODT answers ERR_SEQUENCE, and FREE_DAQ is the only way back --
    so no master can grow a list's maxOdt, and with it its FIRST_PID prefix sum, once that list
    has an ODT entry."""
    handle = dynamic_handle(daq_count=1, odt_count=2, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0:2] == (0xFE, 0x29)
    # FREE_DAQ is the only way back.
    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF


def test_alloc_odt_entry_refusal_leaves_the_allocation_state_unadvanced():
    """Nothing otherwise pins that a refused request leaves the allocation state where it found
    it -- a mutant that hoists the state assignment above the error chain survives the rest of the
    suite. Observed indirectly through ALLOC_ODT (0xD4), which is accepted from
    XCP_DAQ_ALLOC_ODT but answers ERR_SEQUENCE from XCP_DAQ_ALLOC_ODT_ENTRY: if the
    ERR_OUT_OF_RANGE refusal below had actually advanced the state, the ALLOC_ODT after it would
    answer ERR_SEQUENCE instead of succeeding. odt_count leaves room for two ODTs, not one, so
    that follow-up ALLOC_ODT succeeding turns on the state alone, not on any pool capacity left."""
    handle = dynamic_handle(daq_count=1, odt_count=2, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x01, 0x01))[0:2] == (0xFE, 0x22)
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF


def test_alloc_odt_entry_refused_memory_overflow_leaves_entrycount_unchanged():
    """The sibling of test_alloc_odt_entry_refusal_leaves_the_allocation_state_unadvanced, for
    entryCount rather than daq_alloc_state: a refused request must leave entryCount exactly where
    it found it, not just the response bytes ERR_MEMORY_OVERFLOW already pins. This is the case
    that matters most for entryCount specifically -- MEMORY_OVERFLOW is the one check whose entire
    purpose is to keep entryCount from exceeding odt_entries_count, the actual width of that ODT's
    slice of the generated entry pool (script/source_cfg.c.jinja2). A write hoisted above the
    error chain would still run here: 2 (already granted by the first call below) + 3 (requested
    by the refused second call) = 5, which already exceeds the odt_entries_count = 4 cap this
    refusal exists to enforce -- precisely the out-of-bounds shape DD14/DD30 prevent elsewhere in
    this design."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x02))
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x03))[0:2] == (0xFE, 0x30)
    assert handle.lib.Xcp_Ptr.config.daqList[0].odt[0].entryCount == 2

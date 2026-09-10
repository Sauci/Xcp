#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-RESUME (design doc DD103-DD107, docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md).

The Xcp_Restore* setters are the mirror of SP5-NV's four accessors: the integrator pushes back what
it stored, and Xcp_ResumeComplete is the only thing that makes any of it live (DD105)."""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def restoring_handle(**kwargs):
    """A dynamic build with nothing configured. No CONNECT: restoration is a start-up activity and
    must work before any master exists, which is the whole point of the feature."""
    return XcpTest(dynamic_config(daq_count=2, odt_count=2, odt_entries_count=2, **kwargs))


def entry(handle, address=0x1000, length=1, extension=0, bit_offset=0xFF):
    p = handle.ffi.new('Xcp_OdtEntryType *')
    p.address = handle.ffi.cast('uint32 *', address)
    p.length = length
    p.addressExtension = extension
    p.bitOffset = bit_offset
    return p


def test_the_setters_rebuild_a_list_the_accessors_then_report():
    """Round trip through the two halves of DD94/DD103: what Xcp_Restore* writes is what the SP5-NV
    accessors read back. Asserted through the accessors rather than internal state, which the CFFI
    harness cannot reach. Every field differs from its default so a partially-applied setter fails."""
    handle = restoring_handle()

    assert handle.lib.Xcp_RestoreDaqListCount(2) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtCount(0, 2) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntryCount(0, 1, 2) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntry(0, 1, 0, entry(handle, address=0x12345678, length=1,
                                                          extension=2, bit_offset=3)) == handle.define('E_OK')

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 2
    assert handle.lib.Xcp_GetOdtEntryCount(0, 1) == 2

    read_back = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetOdtEntry(0, 1, 0, read_back) == handle.define('E_OK')
    assert int(handle.ffi.cast('uint32', read_back.address)) == 0x12345678
    assert (read_back.length, read_back.addressExtension, read_back.bitOffset) == (1, 2, 3)


def test_the_setters_refuse_out_of_range_arguments():
    """Mirrors the accessors' own bounds (SP5-NV Task 3): a list at or past the restored count, an
    ODT past that list's count, an entry past that ODT's count. Each argument is at the boundary,
    which is the sharpest case for a >=-vs-> error."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(2)
    handle.lib.Xcp_RestoreOdtCount(0, 2)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 1, 2)

    assert handle.lib.Xcp_RestoreOdtCount(2, 1) == handle.define('E_NOT_OK'), 'list == count'
    assert handle.lib.Xcp_RestoreOdtEntryCount(0, 2, 1) == handle.define('E_NOT_OK'), 'odt == count'
    assert handle.lib.Xcp_RestoreOdtEntry(0, 1, 2, entry(handle)) == handle.define('E_NOT_OK'), 'entry == count'


def test_nothing_runs_until_resume_complete():
    """DD105. A restore that stops halfway must leave a slave that resumed nothing, not one
    transmitting a half-built configuration. Asserted on CanIf_Transmit, which is where a running
    list would show up, after triggering the event channel the list is bound to.

    The negative half alone would pass for any reason the trigger fails to reach transmission -- a
    mis-bound list, an empty ODT, a prescaler -- not only for the reason this test names, so it
    would pass against a build whose commit gate does nothing at all. The positive half after
    Xcp_ResumeComplete is the control that rules that out: the same list, the same event channel,
    now transmitting, proves the first assertion was actually about the commit gate."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert not handle.can_if_transmit.called, 'no Xcp_ResumeComplete, so nothing is live'

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.called, 'the same list, committed, transmits on the same trigger'


def test_the_setters_are_refused_once_a_master_has_connected():
    """DD107. Restoration is a start-up activity. A live session configures DAQ through the
    protocol, and a setter that still worked mid-session would be an unpoliced path into DAQ state
    that no ERR_ code describes.

    Refused after CONNECT specifically, not only after Xcp_ResumeComplete: an integrator that never
    commits must not be left holding a working back door for the rest of the session."""
    handle = restoring_handle()
    assert handle.lib.Xcp_RestoreDaqListCount(1) == handle.define('E_OK'), 'accepted before CONNECT'

    connect(handle)

    assert handle.lib.Xcp_RestoreDaqListCount(1) == handle.define('E_NOT_OK')
    assert handle.lib.Xcp_RestoreOdtCount(0, 1) == handle.define('E_NOT_OK')


def test_resume_complete_refuses_a_list_the_front_door_would_refuse_to_start():
    """DD105's second half. START_STOP_DAQ_LIST answers ERR_DAQ_CONFIG for a list with no written
    ODT entry, so resuming must not create by the back door a state the front door rejects. The ODT
    entry count is restored but no entry is written."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_NOT_OK')

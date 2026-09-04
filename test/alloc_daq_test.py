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


def test_alloc_daq_makes_lists_available():
    handle = dynamic_handle(daq_count=4)
    assert exchange(handle, (0xD5, 0x00, 0x02, 0x00))[0] == 0xFF
    assert exchange(handle, (0xE3, 0x00, 0x01, 0x00))[0] == 0xFF          # list 1 available
    assert exchange(handle, (0xE3, 0x00, 0x02, 0x00))[0:2] == (0xFE, 0x22)  # list 2 is not


def test_alloc_daq_accumulates_across_repeated_calls():
    """DD28. The specification forbids ALLOC_DAQ only after ALLOC_ODT and ALLOC_ODT_ENTRY, so a
    repeat from FREE or DAQ is permitted -- and each call therefore adds to what is allocated.
    Treating a repeat as a replacement would make the permitted repeat meaningless."""
    handle = dynamic_handle(daq_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    assert exchange(handle, (0xE3, 0x00, 0x02, 0x00))[0] == 0xFF          # three allocated
    assert exchange(handle, (0xE3, 0x00, 0x03, 0x00))[0:2] == (0xFE, 0x22)


def test_alloc_daq_refuses_more_lists_than_the_pool_holds():
    handle = dynamic_handle(daq_count=4)
    assert exchange(handle, (0xD5, 0x00, 0x05, 0x00))[0:2] == (0xFE, 0x30)
    # The rejected request left nothing allocated.
    assert exchange(handle, (0xE3, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22)


def test_alloc_daq_refusal_leaves_the_allocation_state_unadvanced():
    """The sibling of test_alloc_odt_entry_refusal_leaves_the_allocation_state_unadvanced, for
    0xD5. Nothing else pins that a refused ALLOC_DAQ leaves daq_alloc_state where it found it: a
    mutant that moves the `Xcp_Internal.daq_alloc_state = XCP_DAQ_ALLOC_DAQ` assignment out of the
    else and after the if/else chain survives the whole rest of the suite -- the refusal above
    already asserts nothing was allocated, but says nothing about the state.

    Observed through ALLOC_ODT's *error code*, not through acceptance, because both states this
    has to tell apart refuse the command. ALLOC_ODT checks its refusals in the error matrix's own
    precedence -- SEQUENCE, then OUT_OF_RANGE (source/Xcp_Daq.c) -- so from XCP_DAQ_ALLOC_FREE,
    where the state must still be, it answers ERR_SEQUENCE; from XCP_DAQ_ALLOC_DAQ, where the
    mutant would have put it, the sequence check passes and it falls through to ERR_OUT_OF_RANGE
    for a list ALLOC_DAQ never handed out. The two codes are what separates the correct module
    from the mutant."""
    handle = dynamic_handle(daq_count=4)

    assert exchange(handle, (0xD5, 0x00, 0x05, 0x00))[0:2] == (0xFE, 0x30)
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0:2] == (0xFE, 0x29), \
        'the refused ALLOC_DAQ advanced the state out of XCP_DAQ_ALLOC_FREE'

    # And the state really is still the one ALLOC_DAQ is accepted from, rather than some third
    # thing: a well-formed request from here still succeeds.
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF

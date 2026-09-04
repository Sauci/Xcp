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


def test_alloc_odt_assigns_contiguous_first_pids_whatever_the_allocation_order():
    """DD31. Assigning PIDs in call order breaks under DD28's accumulate rule: ALLOC_ODT(0, 2),
    ALLOC_ODT(1, 3), ALLOC_ODT(0, 1) leaves list 0 needing three contiguous PIDs when list 1
    already owns 2..4. The absolute ODT number is firstPid + relative, so contiguity is required.
    firstPid is therefore a prefix sum over list index, recomputed whenever an ODT count changes --
    the same rule the generator applies to static lists."""
    handle = dynamic_handle(daq_count=2, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x02))   # list 0 gets 2 ODTs
    exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0x03))   # list 1 gets 3
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))   # list 0 gets 1 more, now 3
    assert handle.lib.Xcp_Ptr.config.daqList[0].firstPid == 0
    assert handle.lib.Xcp_Ptr.config.daqList[1].firstPid == 3   # not 2


def test_alloc_odt_first_pid_blocks_never_overlap_read_back_through_the_protocol():
    """DD31, the regression that rules out call-order assignment. ODTs are allocated to list 1
    before list 0, and list 0 is then extended, so every call-order scheme -- handing out PIDs as
    the requests arrive, or appending only the increment -- puts list 0's third ODT on top of a PID
    list 1 already owns. START_STOP_DAQ_LIST is how a master reads FIRST_PID back
    (1.1/1.6.4.1.1.4), so the assertion is made there rather than against the descriptor: mode STOP
    reports it without requiring the list to be configured. List 2 is allocated but empty, and its
    FIRST_PID is still the prefix sum -- it names where its first ODT would begin."""
    handle = dynamic_handle(daq_count=3, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x03, 0x00))
    exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0x03))   # list 1 first, 3 ODTs
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x02))   # then list 0, 2 ODTs
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))   # then list 0 again, now 3

    first_pids = [exchange(handle, (0xDE, 0x00, daq, 0x00))[0:2] for daq in range(3)]

    assert first_pids == [(0xFF, 0), (0xFF, 3), (0xFF, 6)]

    # Spelt out as the property the numbers above stand for: each list's block of absolute ODT
    # numbers is firstPid .. firstPid + maxOdt - 1, and no two blocks may share a number.
    blocks = [set(range(pid, pid + odt_count))
              for (_, pid), odt_count in zip(first_pids, (3, 3, 0))]
    assert blocks[0] == {0, 1, 2}
    assert blocks[1] == {3, 4, 5}
    assert (blocks[0] & blocks[1]) == set()
    assert blocks[2] == set()


def test_alloc_odt_refuses_a_list_that_was_never_allocated():
    handle = dynamic_handle(daq_count=4, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0x01))[0:2] == (0xFE, 0x22)


def test_alloc_odt_refuses_more_odts_than_one_list_may_hold():
    handle = dynamic_handle(daq_count=1, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x05))[0:2] == (0xFE, 0x30)


def test_alloc_odt_refuses_to_exhaust_the_pid_space():
    """DD31. Slave-to-master PIDs 0xFC..0xFF are SERV, EV, ERR and RES, leaving 0x00..0xFB -- 252
    absolute ODT numbers. Checked at runtime rather than at generation: guarding
    daq_count * odt_count <= 252 in the template would reject configurations a master can use
    perfectly well, since it rarely allocates the whole rectangle."""
    handle = dynamic_handle(daq_count=2, odt_count=252)
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0xFC))[0] == 0xFF     # 252 exactly
    assert exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0x01))[0:2] == (0xFE, 0x30)
    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 252               # unchanged


def test_alloc_odt_ceiling_holds_where_a_uint8_total_would_wrap():
    """DD31, and why the running total is accumulated in a uint16 rather than in the uint8 the ODT
    counts themselves live in. With 252 ODTs already out, a second request for 252 clears the
    per-list check -- odtCount is 252, and this list holds none yet -- and totals 504, which is 248
    in a uint8: comfortably under the very ceiling it is being compared against. The request would
    be admitted and the absolute ODT numbers it hands out would run through SERV, EV, ERR and RES.
    The per-list check cannot stand in for this one; it is what makes the wrap reachable."""
    handle = dynamic_handle(daq_count=2, odt_count=252)
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0xFC))[0] == 0xFF
    assert exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0xFC))[0:2] == (0xFE, 0x30)
    assert handle.lib.Xcp_Ptr.config.daqList[1].maxOdt == 0


def test_alloc_odt_before_any_alloc_daq_is_a_sequence_error():
    """DD28. ALLOC_ODT is accepted only from XCP_DAQ_ALLOC_DAQ or XCP_DAQ_ALLOC_ODT
    (1.1/1.6.4.3.1.3). Nothing is allocated in the FREE state either, so ERR_OUT_OF_RANGE would
    also be true of this request -- ERR_SEQUENCE wins because it is a statement about the command
    stream rather than about this command's parameters."""
    handle = dynamic_handle(daq_count=4, odt_count=4)
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0:2] == (0xFE, 0x29)


def test_alloc_daq_after_alloc_odt_is_a_sequence_error():
    """DD28, and the half of Xcp_DTOCmdDaqAllocDaq's ERR_SEQUENCE branch nothing could reach until
    ALLOC_ODT existed: XCP_DAQ_ALLOC_ODT is the first non-FREE, non-DAQ state the module can be
    driven into. 1.1/1.6.4.3.1.2 lists an ALLOC_DAQ after an ALLOC_ODT among its ERR_SEQUENCE
    cases; the master has to send FREE_DAQ before starting over."""
    handle = dynamic_handle(daq_count=4, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0:2] == (0xFE, 0x29)
    # FREE_DAQ returns the state machine to FREE, so ALLOC_DAQ is accepted again.
    exchange(handle, (0xD6,))
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF


def test_alloc_odt_restarts_the_prefix_sum_after_free_daq():
    """FREE_DAQ zeroes maxOdt and firstPid across the pool (1.1/1.6.4.3.1.1), so a master that
    starts over gets PIDs from 0 again rather than continuing the previous session's prefix sum.
    A prefix sum recomputed from the descriptor is what makes that come out right without
    FREE_DAQ having to know anything about PIDs."""
    handle = dynamic_handle(daq_count=2, odt_count=4)
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x02))
    exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0x02))
    assert handle.lib.Xcp_Ptr.config.daqList[1].firstPid == 2, 'the first session did not allocate'

    exchange(handle, (0xD6,))
    exchange(handle, (0xD5, 0x00, 0x02, 0x00))
    exchange(handle, (0xD4, 0x00, 0x01, 0x00, 0x01))
    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 0
    assert handle.lib.Xcp_Ptr.config.daqList[0].firstPid == 0
    assert handle.lib.Xcp_Ptr.config.daqList[1].maxOdt == 1
    assert handle.lib.Xcp_Ptr.config.daqList[1].firstPid == 0

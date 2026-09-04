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


def queued_frames(handle):
    """Every frame currently in the ring, oldest first, as bytes. See
    test/daq_identification_field_test.py and test/daq_concurrency_test.py for why reading
    Xcp_Rt[...].dtoQueue directly needs no test-only surface in the module under test."""
    queue = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].dtoQueue
    frames = list()
    index = queue.read
    for _ in range(queue.count):
        frame = queue.frame[index]
        frames.append(bytes(frame.data[0:frame.length]))
        index = (index + 1) % queue.depth
    return frames


#: One canonical request per allocation command, reused by both the state-reaching helper below
#: and the sweep it feeds. Each names list 0 (and, for ALLOC_ODT_ENTRY, ODT 0) and asks for
#: exactly one more unit than it already holds, so the same literal works whether it is the request
#: that reaches a state or the request the sweep fires from it -- accumulating by one is what DD28
#: permits from every state a command is accepted from.
_ALLOC_REQUEST = {
    'FREE_DAQ': (0xD6,),
    'ALLOC_DAQ': (0xD5, 0x00, 0x01, 0x00),
    'ALLOC_ODT': (0xD4, 0x00, 0x00, 0x00, 0x01),
    'ALLOC_ODT_ENTRY': (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01),
}


def reach_state(handle, state):
    """Drives the allocation state machine to `state` through the protocol alone, exactly as a
    real master would: FREE is FREE_DAQ; DAQ is FREE then ALLOC_DAQ; ODT is DAQ then ALLOC_ODT;
    ODT_ENTRY is ODT then ALLOC_ODT_ENTRY. Xcp_Internal.daq_alloc_state itself has no test-reachable
    surface -- Xcp_Internal is declared in source/Xcp_Internal.h, which interface/Xcp.h does not
    include (see test/free_daq_test.py's allocate_directly for the same limitation) -- so walking
    the commands is the only way to reach a given cell of the sweep below.

    Each step asserts its own success rather than trusting the next command's response to reveal a
    broken setup indirectly: a transition that silently failed here would otherwise misreport as a
    failure of a *different*, unrelated cell three states later."""
    assert exchange(handle, _ALLOC_REQUEST['FREE_DAQ'])[0] == 0xFF
    if state == 'FREE':
        return
    assert exchange(handle, _ALLOC_REQUEST['ALLOC_DAQ'])[0] == 0xFF
    if state == 'DAQ':
        return
    assert exchange(handle, _ALLOC_REQUEST['ALLOC_ODT'])[0] == 0xFF
    if state == 'ODT':
        return
    assert exchange(handle, _ALLOC_REQUEST['ALLOC_ODT_ENTRY'])[0] == 0xFF
    assert state == 'ODT_ENTRY', 'unknown state {!r}'.format(state)


def test_a_dynamic_build_has_no_valid_daq_lists_until_alloc_daq():
    """DD32. The spec's ALLOC_ODT range [MIN_DAQ, MIN_DAQ+DAQ_COUNT-1] is over what ALLOC_DAQ
    allocated, not over the configured pool, so a list inside the pool but not yet allocated is
    "not available" and answers ERR_OUT_OF_RANGE. One runtime count gives both models the right
    answer: it starts at daqCount under STATIC and at zero under DYNAMIC."""
    handle = dynamic_handle(daq_count=4)
    # CLEAR_DAQ_LIST on list 0, which the pool has room for but nothing has allocated.
    assert exchange(handle, (0xE3, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22)


# Four states (FREE, DAQ, ODT, ODT_ENTRY) times four commands (FREE_DAQ, ALLOC_DAQ, ALLOC_ODT,
# ALLOC_ODT_ENTRY). Ten cells are accepted (0xFF); the six the specification enumerates as
# ERR_SEQUENCE answer 0x29 (XCP_E_ASAM_SEQUENCE) -- no more, no fewer. `ids=lambda v: str(v)`
# stringifies state, command and expected individually and joins them, so a failing case names
# itself as e.g. "ODT-ALLOC_DAQ-41" rather than a bare parametrize index.
@pytest.mark.parametrize('state, command, expected', (
    ('FREE',      'FREE_DAQ',        0xFF), ('FREE',      'ALLOC_DAQ',       0xFF),
    ('FREE',      'ALLOC_ODT',       0x29), ('FREE',      'ALLOC_ODT_ENTRY', 0x29),
    ('DAQ',       'FREE_DAQ',        0xFF), ('DAQ',       'ALLOC_DAQ',       0xFF),
    ('DAQ',       'ALLOC_ODT',       0xFF), ('DAQ',       'ALLOC_ODT_ENTRY', 0x29),
    ('ODT',       'FREE_DAQ',        0xFF), ('ODT',       'ALLOC_DAQ',       0x29),
    ('ODT',       'ALLOC_ODT',       0xFF), ('ODT',       'ALLOC_ODT_ENTRY', 0xFF),
    ('ODT_ENTRY', 'FREE_DAQ',        0xFF), ('ODT_ENTRY', 'ALLOC_DAQ',       0x29),
    ('ODT_ENTRY', 'ALLOC_ODT',       0x29), ('ODT_ENTRY', 'ALLOC_ODT_ENTRY', 0xFF),
), ids=lambda v: str(v))
def test_the_allocation_sequence_refuses_exactly_what_the_specification_enumerates(state, command,
                                                                                   expected):
    """DD28. 1.1/1.6.4.3.1 enumerates six ERR_SEQUENCE cases and no others. The initial state is
    FREE: §1.6.4.3.1.1 requires the master to send FREE_DAQ first, but that is a requirement on
    the master, and a refusal absent from the enumerated list is not the slave's to invent.

    The pool (4 DAQ lists, 4 ODTs, 4 ODT entries) is sized generously above what any single cell
    needs: reach_state grants at most one DAQ list, one ODT and one ODT entry, and the most any
    accepted command adds on top of that is one more of the same -- so every accepted cell here
    genuinely succeeds (asserted as response[0] == 0xFF, not merely as "not ERR_SEQUENCE"; an
    accepted cell that actually hit ERR_MEMORY_OVERFLOW because the pool ran out would still be a
    broken test even though 0x30 != 0x29)."""
    handle = dynamic_handle(daq_count=4, odt_count=4, odt_entries_count=4)
    reach_state(handle, state)

    response = exchange(handle, _ALLOC_REQUEST[command])

    if expected == 0xFF:
        assert response[0] == 0xFF
    else:
        assert response[0:2] == (0xFE, expected)


def test_the_allocation_sequence_end_to_end_reaches_a_sampled_frame():
    """The round trip a real master relies on, and what no other test proves: alloc_daq_test.py,
    alloc_odt_test.py and alloc_odt_entry_test.py each prove their own command in isolation, but
    none of them shows the pool they allocate out of is actually usable end to end. FREE_DAQ,
    ALLOC_DAQ, ALLOC_ODT and ALLOC_ODT_ENTRY build one list with one ODT and one entry; SET_DAQ_PTR
    and WRITE_DAQ configure that entry; SET_DAQ_LIST_MODE and START_STOP_DAQ_LIST bring the list
    into data transfer mode; a trigger samples it. If any one of those steps did not genuinely work
    the way its own dedicated test says it does, this is the test that would notice."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    assert exchange(handle, (0xD6,))[0] == 0xFF                             # FREE_DAQ
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF            # ALLOC_DAQ(1)
    assert exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF      # ALLOC_ODT(list 0, 1)
    assert exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF  # ALLOC_ODT_ENTRY(list 0, odt 0, 1)
    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0] == 0xFF  # SET_DAQ_PTR(list 0, odt 0, entry 0)
    assert exchange(handle, (0xE1, 0xFF, 0x01, 0x00) +
                    tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))[0] == 0xFF  # WRITE_DAQ(1 byte)
    # SET_DAQ_LIST_MODE(list 0, event channel 0, prescaler 1, priority 0).
    assert exchange(handle, (0xE0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF
    assert exchange(handle, (0xDE, 0x01, 0x00, 0x00))[0] == 0xFF            # START_STOP_DAQ_LIST(START, list 0)

    handle.lib.Xcp_TriggerEventChannel(0)

    frames = queued_frames(handle)
    assert len(frames) == 1, 'one non-empty ODT samples to exactly one frame'
    # 0, not the descriptor's firstPid: the sampler computes this byte from that very field, so
    # comparing the two could not tell a correct FIRST_PID from a wrong one. The literal is what
    # pins the prefix sum -- the first and only allocated list starts the PID space at 0, and its
    # relative ODT 0 is therefore absolute ODT 0.
    assert frames[0][0] == 0x00, 'absolute ODT number: FIRST_PID + relative ODT 0'
    assert frames[0][1] == 0xA5, 'the sampled payload'

    assert exchange(handle, (0xDE, 0x00, 0x00, 0x00))[0] == 0xFF            # START_STOP_DAQ_LIST(STOP, list 0)


def test_clear_daq_list_clears_entries_without_releasing_the_allocation():
    """Spec §6: CLEAR_DAQ_LIST and FREE_DAQ stay distinct. CLEAR_DAQ_LIST clears one list's
    entries and keeps its allocation; only FREE_DAQ releases it. Both call Xcp_DaqListReset, so
    this is what stops that shared helper from being given FREE_DAQ's deallocation as well.

    An entry is actually written before the clear, and its power-up-reset is asserted alongside
    the surviving allocation: the docstring's own name promises both halves ("clears entries"
    *and* "without releasing the allocation"), and a version that only checked the second half
    would not notice CLEAR_DAQ_LIST silently stopping short of Xcp_DaqListClearEntries."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))
    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0] == 0xFF
    assert exchange(handle, (0xE1, 0xFF, 0x01, 0x00) +
                    tuple(u32_to_array(0xDEADBEEF, 'LITTLE_ENDIAN')))[0] == 0xFF

    assert exchange(handle, (0xE3, 0x00, 0x00, 0x00))[0] == 0xFF

    # The entry is back to its power-up state ...
    entry = handle.lib.Xcp_Ptr.config.daqList[0].odt[0].odtEntry[0]
    assert entry.address == handle.ffi.NULL
    assert entry.length == 0
    # ... but the allocation itself -- the list is still valid and still has its ODT and entry
    # slot -- survived. A repeat of the CLEAR_DAQ_LIST above used to close this test; it was
    # byte-identical to that line and implied by the two assertions here, so it is gone.
    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 1
    assert handle.lib.Xcp_Ptr.config.daqList[0].odt[0].entryCount == 1


def test_set_daq_ptr_is_refused_on_a_list_the_master_never_allocated():
    """Spec §6 and DD32: no new bounds check was added for this. SET_DAQ_PTR is refused before any
    ALLOC_DAQ and again after ALLOC_DAQ but before ALLOC_ODT, and both are asserted below.

    The first is the case this test is named for, and an earlier version did not reach it: it sent
    ALLOC_DAQ before the request, so the only thing it ever exercised was the second case.

    What the wire says and does not say. Both cases answer ERR_OUT_OF_RANGE (1.1/1.6.4.1.1.1, "If
    the specified list is not available") and SET_DAQ_PTR has two checks that produce it -- the
    Xcp_DaqListIsValid gate and `odt_number >= maxOdt` three branches later -- so the response does
    not identify which one fired, and this test does not claim to. It claims the outcome: neither
    an unallocated list nor an allocated list with no ODTs may be pointed at. Which branch answers
    the first case is pinned separately, by
    test_a_dynamic_build_has_no_valid_daq_lists_until_alloc_daq above, through CLEAR_DAQ_LIST --
    a command that has the validity gate and no maxOdt bound behind it."""
    handle = dynamic_handle(daq_count=2, odt_count=2, odt_entries_count=2)

    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22), \
        'a list the master never allocated was pointed at'

    exchange(handle, (0xD5, 0x00, 0x01, 0x00))

    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0:2] == (0xFE, 0x22), \
        'a list allocated but holding no ODTs was pointed at'


def test_get_daq_list_info_reports_the_allocated_shape_not_the_configured_one():
    """Spec §6: GET_DAQ_LIST_INFO reads the descriptor, so it reports runtime MAX_ODT with no
    change. Before ALLOC_ODT the list holds no ODTs, and that is what it must say."""
    handle = dynamic_handle(daq_count=1, odt_count=8, odt_entries_count=4)
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    assert exchange(handle, (0xD8, 0x00, 0x00, 0x00))[2] == 0x00
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x03))
    assert exchange(handle, (0xD8, 0x00, 0x00, 0x00))[2] == 0x03


@pytest.mark.parametrize('daq_count, accepted', ((1, True), (2, False)))
def test_pid_off_under_dynamic_follows_the_shared_tx_pdu_rule(daq_count, accepted):
    """Spec §6. script/source_cfg.c.jinja2 gives an entire dynamic pool exactly one DTO/PDU
    mapping ("One DTO for the whole dynamic pool, not one per list ... every list in the pool
    shares this element"), so SP2b's rule, Xcp_DaqListTxPduIsExclusive, applies unchanged but its
    loop walks the *configured* pool (Xcp_Ptr->general->daqCount) rather than the allocated count
    -- every pool slot, allocated or not, already carries the one shared mapping. The
    discriminator this test sweeps is therefore the pool's own size, not how many lists ALLOC_DAQ
    has handed out: a lone list in a one-list pool is exclusive by construction, while a second,
    even unallocated, slot in a two-list pool already shares the PDU. With one CAN-ID and several
    lists, §1.1.2.1 identification genuinely cannot be recovered without a PID, so refusing it is
    honest rather than restrictive."""
    handle = dynamic_handle(daq_count=daq_count, odt_count=1, odt_entries_count=1,
                            identification_field_type='ABSOLUTE')
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))
    # SET_DAQ_LIST_MODE with PID_OFF (bit 5) on list 0, event channel 0, prescaler 1, priority 0.
    result = exchange(handle, (0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))
    # The refused case pins ERR_MODE_NOT_VALID specifically rather than "some error": SET_DAQ_LIST_
    # MODE has four other refusals (OUT_OF_RANGE for the list, the event channel and the prescaler,
    # SEQUENCE for a running list), so `result[0] == 0xFF` being False would be satisfied by the
    # refusal migrating to any of them -- including ones that would refuse this request whether or
    # not the shared-TX-PDU rule existed at all.
    if accepted:
        assert result[0] == 0xFF
    else:
        assert result[0:2] == (0xFE, 0x27)

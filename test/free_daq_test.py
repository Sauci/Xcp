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


def rt(handle):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]


def queued_frames(handle):
    """Every frame currently in the ring, oldest first, as bytes. See
    test/daq_identification_field_test.py for why reading Xcp_Rt[...].dtoQueue directly needs no
    test-only surface in the module under test."""
    queue = rt(handle).dtoQueue
    frames = list()
    index = queue.read
    for _ in range(queue.count):
        frame = queue.frame[index]
        frames.append(bytes(frame.data[0:frame.length]))
        index = (index + 1) % queue.depth
    return frames


def allocate_directly(handle, daq_list_count=1, odt_count=1, entry_count=1, address=0x1000):
    """What ALLOC_ODT, ALLOC_ODT_ENTRY and WRITE_DAQ will leave behind, written into the descriptor
    from the test instead of driven through the protocol.

    ALLOC_DAQ (0xD5), ALLOC_ODT (0xD4) and ALLOC_ODT_ENTRY (0xD3) are not implemented yet -- they
    still answer ERR_CMD_UNKNOWN -- so there is no protocol route to an allocated dynamic DAQ list
    at the point FREE_DAQ is being written. Writing the descriptor directly is the house's existing
    way of reaching module state a command cannot yet produce (test/daq_concurrency_test.py and
    test/daq_identification_field_test.py both reach Xcp_Rt[...].dtoQueue the same way), and the
    descriptor is exactly what the allocator will write: ALLOC_ODT raises maxOdt and recomputes
    firstPid as a prefix sum (DD31), ALLOC_ODT_ENTRY raises the addressed ODT's entryCount (DD34),
    and WRITE_DAQ fills the entries.

    maxOdt is raised rather than assigned, because DD28 makes repeated ALLOC_ODT accumulate; a
    caller that allocates twice therefore models two ALLOC_ODT requests, not one.

    Nothing resets the descriptor before this runs, and nothing needs to: the generated descriptor
    arrays are module-level statics shared by every XcpTest compiling the same configuration
    (test/conftest.py caches by configuration id), but Xcp_Init -- which XcpTest runs on
    construction -- calls Xcp_DaqFreeAll, so each test starts from a genuinely unallocated pool.
    test_initialisation_releases_an_allocation_left_by_a_previous_session pins that directly; if it
    ever regresses, the accumulation below walks past the pool's generated ODT array rather than
    failing cleanly, so that test failing first is not a coincidence worth ignoring.

    One thing this cannot reach: Xcp_Internal.allocated_daq_count, which ALLOC_DAQ raises.
    Xcp_Internal is declared in source/Xcp_Internal.h, which interface/Xcp.h does not include, so
    it is absent from the CFFI harness's cdef and unreachable from a test at all (the same
    limitation write_daq_test.py and clear_daq_list_test.py record for the DAQ pointer). Every
    assertion below is therefore over the descriptor, Xcp_DaqListRt and the wire, never over that
    counter -- and the tests it makes vacuous are named where that is the case.
    """
    for daq_idx in range(daq_list_count):
        descriptor = handle.lib.Xcp_Ptr.config.daqList[daq_idx]
        first_odt = descriptor.maxOdt
        descriptor.maxOdt = first_odt + odt_count

        for odt_idx in range(first_odt, first_odt + odt_count):
            descriptor.odt[odt_idx].entryCount = entry_count

            for entry_idx in range(entry_count):
                entry = descriptor.odt[odt_idx].odtEntry[entry_idx]
                entry.address = handle.ffi.cast('uint32 *', address)
                entry.addressExtension = 0x00
                entry.length = 0x01
                entry.bitOffset = 0xFF

    # DD31: firstPid is a prefix sum over the lists' ODT counts, recomputed across the whole pool
    # whenever any list's count changes -- not assigned in call order.
    first_pid = 0
    for daq_idx in range(handle.lib.Xcp_Ptr.general.daqCount):
        handle.lib.Xcp_Ptr.config.daqList[daq_idx].firstPid = first_pid
        first_pid += handle.lib.Xcp_Ptr.config.daqList[daq_idx].maxOdt


def start_through_start_stop_synch(handle):
    """Puts list 0 into data transfer mode, and DAQ_RUNNING into the session status with it.

    START_STOP_DAQ_LIST is gated by Xcp_DaqListIsValid, which bounds against the allocated count
    allocate_directly cannot raise, so it refuses every list of a dynamic build until ALLOC_DAQ
    exists. START_STOP_SYNCH is not gated that way: it walks the configured pool and starts
    whichever lists carry SELECTED. Planting SELECTED and sending it leaves the module itself to
    set both the list's RUNNING bit and the session status' DAQ_RUNNING bit, so the pre-condition
    the tests below assert against is the module's own, not the test's."""
    rt(handle).daqList[0].mode = 0x01  # XCP_DAQ_LIST_MODE_SELECTED, source/Xcp_Internal.h
    assert exchange(handle, (0xDD, 0x01))[0] == 0xFF, 'START_STOP_SYNCH start selected refused'
    assert exchange(handle, (0xFD,))[1] & 0x40 == 0x40, 'the list did not actually start'


def test_free_daq_answers_a_positive_response():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.1. The request is one byte and
    carries nothing to validate, so the only negative answers 0xD6 has are the dispatcher's own
    (Xcp_CTOErrorMatrix gives it CMD_BUSY, PGM_ACTIVE, CMD_UNKNOWN and CMD_SYNTAX); the handler
    itself never refuses."""
    handle = dynamic_handle(daq_count=2, odt_count=2, odt_entries_count=2)

    assert exchange(handle, (0xD6,))[0:1] == (0xFF,)


def test_free_daq_releases_every_allocation():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.3.1.1: "This command clears all DAQ
    lists and frees all dynamically allocated DAQ lists, ODTs and ODT entries." Every list, not
    the one a pointer happens to name -- so both lists below are checked, and the ODT entries with
    them: an ODT count returned to zero while the entries it described are still populated would
    leave a reallocated list holding the previous allocation's addresses."""
    handle = dynamic_handle(daq_count=2, odt_count=2, odt_entries_count=2)
    allocate_directly(handle, daq_list_count=2, odt_count=2, entry_count=2)

    assert handle.lib.Xcp_Ptr.config.daqList[1].firstPid == 2, 'the setup itself did not allocate'

    assert exchange(handle, (0xD6,))[0] == 0xFF

    for daq_idx in range(2):
        descriptor = handle.lib.Xcp_Ptr.config.daqList[daq_idx]

        assert descriptor.maxOdt == 0
        assert descriptor.firstPid == 0

        for odt_idx in range(2):
            assert descriptor.odt[odt_idx].entryCount == 0

            for entry_idx in range(2):
                entry = descriptor.odt[odt_idx].odtEntry[entry_idx]

                assert entry.address == handle.ffi.NULL
                assert entry.addressExtension == 0
                assert entry.length == 0
                # 1.1/1.6.4.2.1.1: "(if valid : bit_offset = 0xFF)".
                assert entry.bitOffset == 0xFF


def test_free_daq_stops_a_running_daq_rather_than_refusing_it():
    """DD29. Xcp_CTOErrorMatrix gives 0xD6 only CMD_BUSY, PGM_ACTIVE, CMD_UNKNOWN and CMD_SYNTAX;
    ERR_DAQ_ACTIVE is absent, so refusing a running slave is not authorised. FREE_DAQ therefore
    stops every running list and clears DAQ_RUNNING."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    allocate_directly(handle)
    start_through_start_stop_synch(handle)

    assert exchange(handle, (0xD6,))[0] == 0xFF
    # GET_STATUS: DAQ_RUNNING (XCP_SESSION_STATUS_MASK_DAQ_RUNNING) clear.
    assert exchange(handle, (0xFD,))[1] & 0x40 == 0x00
    assert rt(handle).daqList[0].mode == 0x00
    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 0


def test_free_daq_clears_the_runtime_state_not_only_the_descriptor():
    """DD30. Mode, prescaler, prescalerCounter, priority and eventChannelNumber live in
    Xcp_DaqListRt, a separate array from the descriptor. A freed-then-reallocated list that
    inherited them would start with a binding the master never set for it.

    The prescaler returns to 1, not 0: 1.1/1.6.4.1.1.3 makes 1 the neutral value, and
    Xcp_TriggerEventChannel elapses a cycle on `prescalerCounter >= prescaler`, so a zero
    prescaler would mean every trigger elapses rather than none."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    allocate_directly(handle)

    rt(handle).daqList[0].mode = 0x10  # XCP_DAQ_LIST_MODE_TIMESTAMP
    rt(handle).daqList[0].eventChannelNumber = 0x0001
    rt(handle).daqList[0].prescaler = 0x07
    rt(handle).daqList[0].prescalerCounter = 0x03
    rt(handle).daqList[0].priority = 0x05

    assert exchange(handle, (0xD6,))[0] == 0xFF

    entry = rt(handle).daqList[0]
    assert (entry.mode, entry.eventChannelNumber, entry.prescaler,
            entry.prescalerCounter, entry.priority) == (0x00, 0x0000, 0x01, 0x00, 0x00)


def test_a_configured_running_list_samples_when_free_daq_does_not_run():
    """The control for the post-condition test below: without it, a trigger that samples nothing
    after FREE_DAQ proves nothing, because a setup that never sampled in the first place would
    satisfy the same assertion."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    allocate_directly(handle)
    start_through_start_stop_synch(handle)
    handle.xcp_read_slave_memory_u8.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.xcp_read_slave_memory_u8.call_count == 1
    assert len(queued_frames(handle)) == 1


def test_a_trigger_after_free_daq_samples_nothing_and_queues_no_frame():
    """DD30's outcome, stated as a post-condition rather than as an interleaving.

    Xcp_TriggerEventChannel runs in interrupt context and reaches entry storage by walking maxOdt
    and then each ODT's entryCount, so the failure this guards against is a count outliving the
    storage it describes -- a trigger that samples through a released ODT entry. The test that
    would exercise the race itself, driving a trigger from inside the exclusive area FREE_DAQ is
    holding, is not written: see the Task 4 report and design §10 for why the harness cannot
    express it. What is checked here is the outcome the race is about -- once FREE_DAQ has
    returned, the sampler reaches nothing at all -- for the same list that
    test_a_configured_running_list_samples_when_free_daq_does_not_run has just shown does sample
    without it."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    allocate_directly(handle)
    start_through_start_stop_synch(handle)

    assert exchange(handle, (0xD6,))[0] == 0xFF

    queued_before = rt(handle).dtoQueue.count
    handle.xcp_read_slave_memory_u8.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    handle.xcp_read_slave_memory_u8.assert_not_called()
    assert rt(handle).dtoQueue.count == queued_before


#: How many times Xcp_DaqFreeAll releases the DAQ exclusive area for one list holding one ODT:
#: once at the end of Xcp_DaqListClearEntries' per-ODT critical section, and once at the end of
#: the per-list critical section around the descriptor-count writes. Pinned by
#: test_free_daq_holds_the_exclusive_area_exactly_once_per_odt_and_once_per_list below, so a new
#: critical section fails that test loudly instead of silently leaving the sweep below short.
FREE_DAQ_AREA_RELEASES = 2


@pytest.mark.parametrize('release_index', range(FREE_DAQ_AREA_RELEASES))
def test_a_trigger_preempting_free_daq_at_any_area_release_samples_nothing(release_index):
    """DD30, exercised as an interleaving rather than only as a post-condition.

    Xcp_TriggerEventChannel is documented to run in an interrupt, and FREE_DAQ runs in CanIf's
    receive context, so the sampler can preempt the unwind. It cannot preempt it *anywhere*: the
    DAQ exclusive area exists precisely to suppress that interrupt, so the points at which a
    trigger can actually land are the points at which the area is not held. Firing the trigger
    from SchM_Exit_Xcp_DtoQueue's side effect puts it at exactly those points, one at a time, and
    is a legitimate preemption -- unlike firing it from SchM_Enter's, which injects a trigger into
    a window the lock forbids and which the harness's own invariant correctly reports as a
    double-enter (see the Task 4 report).

    At every one of those points the sampler must come away with nothing: either the entries of
    the ODT it walks have already been cleared while the counts still describe them (release 0),
    or the counts are already zero (release 1). What it must never do is read through an entry the
    unwind has released -- the DD14 failure class -- so the assertion is on the memory reads
    themselves, not just on the ring."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=2)
    allocate_directly(handle, odt_count=1, entry_count=2)
    start_through_start_stop_synch(handle)

    original_exit = handle.sch_m_exit_xcp_dto_queue.side_effect
    state = {'releases': 0, 'fired': False, 'reads': None}

    def exit_and_preempt():
        original_exit()
        if (state['releases'] == release_index) and (state['fired'] is False):
            state['fired'] = True
            handle.xcp_read_slave_memory_u8.reset_mock()
            handle.lib.Xcp_TriggerEventChannel(0)
            state['reads'] = handle.xcp_read_slave_memory_u8.call_count
        state['releases'] += 1

    handle.sch_m_exit_xcp_dto_queue.side_effect = exit_and_preempt

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD6,)))

    handle.sch_m_exit_xcp_dto_queue.side_effect = original_exit

    assert state['fired'] is True, \
        'release {} was never reached, so nothing was interleaved'.format(release_index)
    assert state['reads'] == 0, 'the preempting trigger read slave memory through a freed entry'
    assert len(queued_frames(handle)) == 0
    # The injected trigger takes the area itself; that it did so without nesting is what says the
    # release point really was outside the area rather than inside it.
    assert handle.dto_queue_area_violations == []


def test_free_daq_holds_the_exclusive_area_exactly_once_per_odt_and_once_per_list():
    """Guards FREE_DAQ_AREA_RELEASES, and so the sweep above: a critical section added to the
    unwind without extending the sweep would leave an interleaving point untested, which is the
    one thing a sweep parametrised by a literal cannot notice by itself."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=2)
    allocate_directly(handle, odt_count=1, entry_count=2)
    enter_count_before = handle.sch_m_enter_xcp_dto_queue.call_count

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD6,)))

    assert handle.sch_m_enter_xcp_dto_queue.call_count - enter_count_before == FREE_DAQ_AREA_RELEASES


def test_free_daq_takes_the_exclusive_area_around_the_descriptor_writes():
    """DD30/DD14. maxOdt and entryCount are read by Xcp_TriggerEventChannel and Xcp_DaqSampleOdt,
    which may run in an interrupt that preempts this command in CanIf's receive context, so
    FREE_DAQ's writes to them are taken under the same exclusive area the sampler takes -- the
    one-sided-lock bug test/daq_concurrency_test.py::test_clear_daq_list_takes_the_exclusive_area
    catches for CLEAR_DAQ_LIST.

    Exactly one entry is expected, and the count is taken around Xcp_CanIfRxIndication alone (the
    handler runs synchronously inside it) rather than around a full exchange, whose
    Xcp_MainFunction takes the same area to read the DTO ring. Nothing is allocated here on
    purpose: with maxOdt at zero, Xcp_DaqListClearEntries' per-ODT loop -- which takes the area
    once per ODT -- does not execute at all, so the single entry counted below can only be the one
    around the descriptor-count writes."""
    handle = dynamic_handle(daq_count=1, odt_count=1, odt_entries_count=1)
    enter_count_before = handle.sch_m_enter_xcp_dto_queue.call_count

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD6,)))

    assert handle.sch_m_enter_xcp_dto_queue.call_count - enter_count_before == 1


def test_initialisation_releases_an_allocation_left_by_a_previous_session():
    """Xcp_Init must establish the same invariant FREE_DAQ does, so it runs the same unwind.

    It used to reset Xcp_Internal and every Xcp_DaqListRt and clear the ODT entries, but left the
    descriptor's own maxOdt, firstPid and per-ODT entryCount standing -- and under DYNAMIC those
    three ARE the allocation. A re-initialised module therefore set allocated_daq_count to 0 and
    daq_alloc_state to FREE, reporting nothing allocated, while the descriptor still described the
    previous session's lists: the two halves of the allocation state disagreed. The clear missed
    the entries too, because Xcp_DaqListClearEntries is bounded by exactly the counts being left
    behind -- which is Task 2's carried note ("Xcp_Init never clears the pool's ODT entries") seen
    from one level up.

    The generated descriptor arrays are module-level mutable statics with no initialisation of
    their own, so this is the only thing standing between one session's allocation and the next
    one's."""
    handle = dynamic_handle(daq_count=2, odt_count=2, odt_entries_count=2)
    allocate_directly(handle, daq_list_count=2, odt_count=2, entry_count=2)

    assert handle.lib.Xcp_Ptr.config.daqList[1].firstPid == 2, 'the setup itself did not allocate'

    handle.lib.Xcp_Init(handle.ffi.cast('const Xcp_Type *', handle.config.lib.Xcp))

    for daq_idx in range(2):
        descriptor = handle.lib.Xcp_Ptr.config.daqList[daq_idx]

        assert descriptor.maxOdt == 0
        assert descriptor.firstPid == 0

        for odt_idx in range(2):
            assert descriptor.odt[odt_idx].entryCount == 0

            for entry_idx in range(2):
                entry = descriptor.odt[odt_idx].odtEntry[entry_idx]

                assert entry.address == handle.ffi.NULL
                assert entry.length == 0


def test_disconnect_frees_the_allocation_so_the_next_session_does_not_inherit_it():
    """XCP part 1 - Overview 1.0/2.3: in "DISCONNECTED" state "the session status, all DAQ lists
    and the protection status bits are reset". Nothing performed that reset -- Xcp_CTOCmdStdDisconnect
    cleared only connection_status, CONNECT cleared nothing, and Xcp_Init was the module's only
    session-state reset path.

    Under DYNAMIC that is not merely untidy. The allocation state machine starts in FREE and
    accepts ALLOC_DAQ with no preceding FREE_DAQ (DD28), and repeats accumulate, so a master that
    allocated and then disconnected without sending FREE_DAQ left its allocation standing for the
    next master to add to. Here the first session takes two ODTs and the second takes one: with
    the allocation released at DISCONNECT the second session holds exactly the one ODT it asked
    for, and ODT 1 -- the first session's -- is back to being unallocated and empty. Without it,
    maxOdt would read three and ODT 1 would still carry the first session's entry."""
    handle = dynamic_handle(daq_count=2, odt_count=4, odt_entries_count=2)
    allocate_directly(handle, odt_count=2, address=0x1000)

    assert exchange(handle, (0xFE,))[0] == 0xFF  # DISCONNECT

    connect(handle)  # the next master
    allocate_directly(handle, odt_count=1, address=0x2000)

    descriptor = handle.lib.Xcp_Ptr.config.daqList[0]

    assert descriptor.maxOdt == 1
    assert descriptor.odt[1].entryCount == 0
    assert descriptor.odt[1].odtEntry[0].address == handle.ffi.NULL
    assert descriptor.odt[1].odtEntry[0].length == 0


def test_disconnect_leaves_a_static_configurations_daq_entries_alone():
    """The counterpart of the test above, and the boundary on it: the DISCONNECT unwind is gated on
    DAQ_DYNAMIC, so a STATIC build's configured DAQ entries survive a disconnect untouched.

    A STATIC configuration has no allocation to leak -- its lists are generated, not allocated --
    so the gap the DYNAMIC gate closes does not exist here, and clearing a master's written entries
    on disconnect would be a behaviour change to the static model that SP2d is required not to make
    (DD25). Pinned rather than left implicit, because Xcp_DaqFreeAll is one unguarded call away
    from doing it.

    Whether XCP part 1 - Overview 2.3 nevertheless requires a disconnecting slave to reset its DAQ
    lists in both models is a separate question, deliberately not settled here: that document is
    not in docs/external/, so the claim cannot be checked against a source. It is recorded as a
    follow-up in the Task 4 report rather than implemented against an unverifiable citation."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))  # SET_DAQ_PTR list 0, odt 0, entry 0
    exchange(handle, (0xE1, 0xFF, 0x01, 0x00, 0x00, 0x10, 0x00, 0x00))  # WRITE_DAQ address 0x1000

    assert exchange(handle, (0xFE,))[0] == 0xFF  # DISCONNECT

    connect(handle)

    entry = handle.lib.Xcp_Ptr.config.daqList[0].odt[0].odtEntry[0]

    assert entry.address != handle.ffi.NULL, 'DISCONNECT cleared a static build\'s ODT entry'
    assert int(handle.ffi.cast('uint32_t', entry.address)) == 0x1000
    assert entry.length == 1
    # The list is still there to be cleared, as it was before: a static list's ODTs are generated,
    # not allocated, so CLEAR_DAQ_LIST on list 0 is answered rather than refused as out of range.
    assert exchange(handle, (0xE3, 0x00, 0x00, 0x00))[0] == 0xFF

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Applying buffered stimulation data to ECU memory at the event trigger (SP3 Task 8,
DD35/DD37/DD40/DD45).

This is the half of stimulation that writes. Everything up to here failed loudly when it was wrong
-- a frame was refused, a command answered with an error code, a slot stayed empty. From here on a
mistake is a value landing at an address the slave chose badly, which nothing on the bus reports
and which the design document names as this sub-project's principal risk (spec section 7).

**So every test in this file asserts the (address, value) pairs the module handed to
Xcp_WriteSlaveMemoryTable, not that a frame was accepted or that the apply ran.** A test that
checked only "the trigger stimulated something" would pass under exactly the defect that matters:
the master's bytes written to the right entry at the wrong offset, or to the wrong entry entirely.

The apply is the mirror of Xcp_DaqSampleOdt (source/Xcp_DaqRuntime.c): the same entry walk, the
same cumulative offset, in the other direction. Where the two could disagree -- the offset
arithmetic, which entries are consumed, what an empty entry costs -- the tests below pin the apply
against a payload whose every byte is distinct, so an offset off by one is a different assertion
failure rather than a silently equal one.
"""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect
from .stim_reception_test import (configure_one_entry, deliver, response, set_daq_list_mode, slot,
                                  start_daq_list)

# The bytes a master stimulates with. Every one distinct, and none of them 0x00: the tests below
# assert WHICH payload byte reached WHICH address, so two equal bytes would make an offset error
# of one invisible wherever the two happened to line up.
PAYLOAD = (0x11, 0x22, 0x33, 0x44, 0x55)

# A second, wholly different payload, for the tests that replace what a slot holds.
SECOND_PAYLOAD = (0x66, 0x77, 0x88, 0x99, 0xAA)

# The two addresses the split-entry tests point their entries at. Far apart on purpose: an
# implementation that wrote the second entry's slice through the FIRST entry's address, advanced by
# the running offset, would land at 0x1002 -- which has to be distinguishable from 0x2000 rather
# than merely "some address".
FIRST_ADDRESS = 0x1000
SECOND_ADDRESS = 0x2000


def stimulation_config(max_odt=1, max_odt_entries=2, **kwargs):
    """One DAQ_STIM list under ABSOLUTE identification, so ODT n of the single list is absolute PID
    n and every frame below is one PID byte followed by its payload."""
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=max_odt,
                                   max_odt_entries=max_odt_entries),),
                         **kwargs)


def write_daq(handle, size, address, extension=0x00):
    """One WRITE_DAQ at the DAQ pointer's current position, which the command post-increments -- so
    consecutive calls after one SET_DAQ_PTR fill consecutive entries of the same ODT. Asserted,
    because an entry that was silently not written contributes nothing to the payload the apply
    consumes, and every offset assertion below would then be about a different layout."""
    assert response(handle, (0xE1, 0xFF, size, extension) +
                    tuple(u32_to_array(address, 'LITTLE_ENDIAN')))[0] == 0xFF, 'WRITE_DAQ was refused'


def set_daq_ptr(handle, daq_list=0, odt=0, entry=0):
    assert response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) +
                    (odt, entry))[0] == 0xFF, 'SET_DAQ_PTR was refused'


def configure_entries(handle, entries, daq_list=0, odt=0):
    """SET_DAQ_PTR to (daq_list, odt, entry 0), then one WRITE_DAQ per (size, address, extension)."""
    set_daq_ptr(handle, daq_list=daq_list, odt=odt)
    for size, address, extension in entries:
        write_daq(handle, size, address, extension=extension)


def running_stim_list(handle, entries, daq_list=0, odt=0, mode=0x02):
    """The state a trigger applies in: the ODT's entries written, DIRECTION = STIM, RUNNING."""
    configure_entries(handle, entries, daq_list=daq_list, odt=odt)
    set_daq_list_mode(handle, daq_list=daq_list, mode=mode)
    start_daq_list(handle, daq_list=daq_list)


def capture_writes(handle):
    """Every (address, value) pair the apply hands to Xcp_WriteSlaveMemoryTable, in order.

    The list IS the memory model: the write table is the module's only route to ECU memory, so what
    it was asked to write, and where, is the whole of what the apply did. Every test that uses this
    helper runs at BYTE granularity (DefaultConfig's own default), so one call is one byte and the
    sequence reads as the memory image the master asked for; the granularity sweep below installs
    its own capture across all three tables, since there one call is one element.
    """
    written = list()

    def write_slave_memory(p_address, p_buffer):
        written.append((int(handle.ffi.cast('uint32_t', p_address)), p_buffer[0]))

    handle.xcp_write_slave_memory_u8.side_effect = write_slave_memory
    return written


def not_applied(handle):
    """The Det reports Xcp_DaqApplyStim raised for what it could not stimulate, filtered out of
    whatever else the setup commands reported."""
    return [call for call in handle.det_report_error.call_args_list
            if call[0][3] == handle.define('XCP_E_STIM_NOT_APPLIED')]


def expected(address, payload):
    return [(address + index, byte) for index, byte in enumerate(payload)]


def test_the_event_writes_the_masters_bytes_at_the_entrys_address():
    """The whole feature, in the smallest configuration that shows it: one ODT entry, one frame,
    one trigger, and the master's four bytes in ECU memory at the address WRITE_DAQ named.

    Asserted as the exact ordered sequence of (address, value) pairs, not as a set and not as a
    count. The order is the memory image: an apply that wrote the right bytes to the right block in
    the wrong order would have got the entry's internal layout wrong, which for a multi-byte
    variable is as destructive as writing the wrong address.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[:4])


def test_each_entry_takes_its_own_slice_of_the_payload_at_the_running_offset():
    """The offset arithmetic, which is the one thing here that fails silently.

    Two entries of DIFFERENT widths -- two bytes then three -- at two addresses far apart. The
    payload is one flat block on the wire (1.1/1.1.4.1), and which of its bytes belong to which
    entry is decided entirely by the running offset the apply keeps as it walks the entries. That
    offset is the mirror of Xcp_DaqSampleOdt's own, which fills the frame in the other direction
    from the same entry list; the two must agree, or a master's round trip through this slave
    returns bytes to different variables than it sent.

    Unequal widths on purpose: with two entries of the same size, an implementation that advanced
    the offset by a constant instead of by each entry's own length would still be right here.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((2, FIRST_ADDRESS, 0x00), (3, SECOND_ADDRESS, 0x00)))
    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[0:2]) + expected(SECOND_ADDRESS, PAYLOAD[2:5])


@pytest.mark.parametrize('address_granularity', address_granularities)
def test_an_entry_is_applied_one_element_at_a_time_at_the_configured_granularity(address_granularity):
    """1.1/1.1.4.1: an ODT entry of n bytes is n/AG elements, and the write table is indexed by the
    granularity -- Xcp_WriteSlaveMemoryU8, U16 or U32, one call per element, the address advancing
    by one element each time. The DAQ direction has this swept in daq_acceptance_test.py; the
    stimulation direction consumes the same layout backwards and gets its own sweep here, because
    a BYTE-only test cannot tell an implementation that walks elements from one that walks bytes.

    Two elements per entry, so the per-element address advance is exercised rather than only the
    entry's base address. MAX_DTO is raised to 16 for that: at 8 the ODT budget is 7 bytes and two
    DWORD elements do not fit.

    Asserted as raw payload BYTES per element, not as decoded integers, and that is the point
    rather than a convenience -- stimulation data is pass-through. byteOrder governs the protocol's
    own multi-byte fields (a DAQ list number, an MTA), never the measured or stimulated value,
    which is the sentence Xcp_DaqWriteIdentificationField already makes for the other direction.
    """
    element_size = element_size_from_address_granularity(address_granularity)
    config = stimulation_config(max_dto=16, address_granularity=address_granularity)
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((2 * element_size, FIRST_ADDRESS, 0x00),))
    payload = tuple(range(0xA0, 0xA0 + (2 * element_size)))
    deliver(handle, (0x00,) + payload, config.default_daq_dto_pdu_mapping)
    written = list()

    def write_slave_memory(p_address, p_buffer):
        written.append((int(handle.ffi.cast('uint32_t', p_address)),
                        tuple(p_buffer[0:element_size])))

    handle.xcp_write_slave_memory_u8.side_effect = write_slave_memory
    handle.xcp_write_slave_memory_u16.side_effect = write_slave_memory
    handle.xcp_write_slave_memory_u32.side_effect = write_slave_memory

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [(FIRST_ADDRESS, payload[0:element_size]),
                       (FIRST_ADDRESS + element_size, payload[element_size:])]


def test_a_slot_is_latched_and_applied_at_every_event():
    """DD35, and the test the decision stands or falls on: ONE frame, TWO triggers, the variable
    written both times.

    Under one-shot semantics -- apply the payload and clear the slot -- the first trigger passes
    every other test in this file and the second writes nothing at all, so this is the only
    assertion that separates the two policies. It is a discriminator, not a formality.

    The two rounds are asserted as one concatenated sequence rather than by counting calls: a
    second round that wrote different bytes, or the same bytes to a different address, is a
    different defect from a second round that did not happen, and both must fail here.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[:4]) * 2, \
        'the master sent once; the slot is latched, so both events apply it'


def test_a_new_frame_replaces_what_the_latched_slot_applies():
    """The other half of DD35, and what keeps "latched" from meaning "frozen": once a second frame
    arrives, every subsequent event applies the NEW payload and never the old one.

    Both rounds are asserted together, so an implementation that applied the first payload twice
    and an implementation that applied the second payload twice are both visible -- the second
    would pass an assertion that looked only at the final state of memory."""
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)
    deliver(handle, (0x00,) + SECOND_PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[:4]) + \
           expected(FIRST_ADDRESS, SECOND_PAYLOAD[:4])


def test_a_slot_no_frame_ever_filled_writes_nothing_and_reports_nothing():
    """DD35's third state, beside "holds the last frame" and "holds a new one": holds nothing.

    A list that is RUNNING and directed at stimulation before its master has sent anything must
    apply nothing -- writing a slot of zeros into ECU memory would be a write no master asked for.
    And it must stay SILENT while it does: this is the steady state of a freshly started list, so a
    Det report here would fire on every event of every cycle until the first frame arrives.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    assert slot(handle).length == 0, 'no frame was delivered, so the slot holds nothing'
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [], 'an empty slot is skipped, not applied as zeros'
    assert not_applied(handle) == [], 'and skipped silently -- this is a started list, not a fault'


def test_an_entry_naming_a_non_zero_address_extension_is_skipped_while_its_siblings_apply():
    """DD45. Xcp_WriteSlaveMemoryTable takes (address, buffer) and has no parameter for an address
    extension, while Xcp_ReadSlaveMemoryTable takes one -- so an entry naming segment 1 can be
    sampled but cannot be stimulated at the place it names. Writing it anyway puts the master's
    bytes at the right offset in the WRONG segment, with nothing to report it.

    Two assertions, and the second is the one that is easy to get wrong:

    - the skipped entry writes nothing, and its sibling writes everything it should;
    - the sibling still takes ITS OWN slice of the payload, PAYLOAD[2:5], not the payload's first
      three bytes. The master laid the frame out from the whole ODT -- Xcp_DaqStimOdtPayloadLength
      (source/Xcp_DaqRuntime.c) is what reception measured it against, and that sums every entry --
      so a skipped entry's bytes are on the wire and the running offset has to consume them. An
      apply that skipped the offset advance along with the write would silently shift every
      following entry by the width of the one it refused.

    The Det report is asserted exactly once, with this API's own id: the trigger is what raised it,
    not the receive callback, and XCP_E_STIM_FRAME_REJECTED belongs to the other one.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((2, FIRST_ADDRESS, 0x01), (3, SECOND_ADDRESS, 0x00)))
    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(SECOND_ADDRESS, PAYLOAD[2:5]), \
        'the extension-0 sibling applies, and keeps the slice the master gave it'
    assert len(not_applied(handle)) == 1
    assert not_applied(handle)[0][0][2] == handle.define('XCP_TRIGGER_EVENT_CHANNEL_API_ID'), \
        'the trigger raised it, not the receive callback'


def test_an_entry_widened_after_its_frame_arrived_applies_nothing_it_did_not_receive():
    """The slot is bytes plus a length, and the ODT it belongs to can be reconfigured after those
    bytes arrived. DD39 checks the payload against the ODT's entries at RECEPTION, which is the
    right place for it -- but the check is not a property that survives:

        START -> deliver a one-byte frame -> STOP -> WRITE_DAQ widening the entry to four bytes
        -> START -> trigger

    Six commands, every one of them legal (WRITE_DAQ needs only that the list be stopped), and the
    slot now holds one byte against an entry that wants four. An apply that trusted the entry and
    ignored the slot's own length would read three bytes past what the master sent -- uninitialised
    stack, in this build -- and write them into ECU memory.

    So the entry is refused whole rather than applied in part: partial application is precisely
    what DD39's reception check exists to keep the apply path from ever reasoning about, and half
    of a multi-byte variable is not a value the master asked for. It is reported, unlike the empty
    slot above, because this state is a real disagreement rather than a list waiting for its first
    frame.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((1, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00, PAYLOAD[0]), config.default_daq_dto_pdu_mapping)
    assert slot(handle).length == 1, 'the one-byte frame is what the slot holds'
    assert response(handle, (0xDE, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))[0] == 0xFF, 'STOP'
    configure_entries(handle, ((4, FIRST_ADDRESS, 0x00),))
    start_daq_list(handle)
    assert slot(handle).length == 1, 'and STOP did not clear it'
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [], 'four bytes were wanted and one was received, so none are applied'
    assert len(not_applied(handle)) == 1


def test_a_slot_length_larger_than_its_buffer_cannot_read_past_it():
    """The apply copies `length` bytes out of the slot into a stack buffer of XCP_MAX_DTO, and
    `length` cannot exceed that -- Xcp_DaqStoreStim refuses a frame longer than the running
    configuration's MAX_DTO, itself no larger than XCP_MAX_DTO. That invariant lives in a different
    function, so the copy is clamped against its own sizeof as well, and this is what makes the
    clamp a checked line rather than an unreachable one.

    The length is corrupted directly, past anything the command set or the wire can produce, and
    ASan is the oracle: without the clamp the copy loop runs 255 times into an eight-byte stack
    array and reads as far past the end of the slot, which is a stack-buffer-overflow the harness
    fails on rather than a wrong value it might not notice. The applied bytes are asserted too, so
    a clamp that fired but also broke the ordinary case is visible.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    slot(handle).length = 0xFF
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[:4]), \
        'the entry still applies, and nothing was read past the slot to do it'


def test_a_list_the_master_has_turned_back_to_measurement_applies_nothing():
    """DIRECTION is checked when the frame arrives (DD39) and again here, and the second check is
    not a duplicate of the first: DD35 latches the slot, so an arbitrary amount of time and an
    arbitrary number of commands separate the two.

        START(DIRECTION = STIM) -> deliver -> STOP -> SET_DAQ_LIST_MODE(DIRECTION clear) -> START

    SET_DAQ_LIST_MODE answers ERR_DAQ_ACTIVE on a running list, so the master has to stop it first
    -- and neither the stop nor the mode change touches the slot, which is the invariant
    stim_reception_test.py's own disconnect test records. The list is then RUNNING and measuring,
    with a stimulation payload still latched behind it. Applying that payload would write memory
    the master has explicitly said it only wants to read, which is the same sentence
    test_a_frame_for_a_list_whose_direction_is_daq_is_dropped makes about the receive side.

    The slot is asserted to still hold its payload, so this test is about the apply refusing rather
    than about something having quietly emptied the slot.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    assert response(handle, (0xDE, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))[0] == 0xFF, 'STOP'
    set_daq_list_mode(handle, mode=0x00)
    start_daq_list(handle)
    assert (handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode & 0x42) == 0x40, \
        'RUNNING with DIRECTION clear is the premise'
    assert slot(handle).length == 4, 'and the payload is still latched behind it'
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [], 'a measuring list must not have memory written under it'


def test_a_daq_only_build_applies_nothing_and_takes_no_stimulation_area():
    """The guard that keeps a list which cannot receive away from the slot array at all.

    A DAQ-typed list has no slot: the generator reserves one only for lists that can receive, so
    stimSlotBase is 0 and stimSlot itself is NULL_PTR for a build whose every list is DAQ
    (interface/Xcp_Types.h). An apply that walked every running list on the channel without asking
    what the list's TYPE is would dereference that null pointer here -- and in a build that does
    have a pool, would read the FIRST receiving list's slot and stimulate through a DAQ list's
    addresses.

    Counted as well as asserted empty, for the reason stim_reception_test.py's own DAQ-only test
    gives: the harness's bookkeeping would catch an unbalanced area but not a balanced one taken
    for a pool that does not exist, and "a DAQ-only build pays nothing for stimulation" is a stated
    constraint of this sub-project.
    """
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ', max_odt=1, max_odt_entries=1),)))
    connect(handle)
    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 0, 'the premise'
    configure_one_entry(handle)
    set_daq_list_mode(handle, mode=0x00)
    start_daq_list(handle)
    written = capture_writes(handle)
    handle.sch_m_enter_xcp_stim_buffer.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [], 'a DAQ list measures; nothing is written through its entries'
    assert handle.sch_m_enter_xcp_stim_buffer.call_count == 0, \
        'and no stimulation area is taken for a pool that was never reserved'


def test_a_daq_only_lists_forced_direction_still_reaches_no_slot():
    """The type guard, exercised on its own -- which the test above cannot do.

    Xcp_DaqApplyStim asks two things of a list before it touches the slot array: that its
    configured type can receive, and that DIRECTION is set. The command set cannot produce a DAQ
    list with DIRECTION set at all -- Xcp_DTOCmdDaqSetDaqListMode (source/Xcp_Daq.c) answers
    ERR_MODE_NOT_VALID for exactly that -- so on every configuration a master can reach, the
    DIRECTION half alone gives the right answer and a missing type check is invisible. Verified:
    with the type conjunct deleted, the whole suite stays green.

    So the state is constructed directly, the same way
    stim_reception_test.py::test_a_frame_for_a_list_that_cannot_receive_is_dropped constructs its
    own, and for the same reason: the refusal in the command set is precisely why this is a second,
    independent guard rather than a duplicate, and a guard nothing can reach is a guard nothing can
    check.

    In a DAQ-only build Xcp_Rt[...].stimSlot is NULL_PTR outright (interface/Xcp_Types.h), so an
    apply that reached the slot array here would dereference it. This test therefore fails by
    crashing rather than by asserting, which is itself the point: there is no slot to read, at any
    index, and the type is the only thing that says so.
    """
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ', max_odt=1, max_odt_entries=1),)))
    connect(handle)
    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 0, \
        'a DAQ-only build reserves no slots, so stimSlot is the null pointer'
    configure_one_entry(handle)
    # 0x42: RUNNING (bit 6) and DIRECTION (bit 1), written straight to the runtime state because
    # SET_DAQ_LIST_MODE refuses DIRECTION on a DAQ list and no command sequence can reach this.
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode = 0x42
    written = capture_writes(handle)
    handle.sch_m_enter_xcp_stim_buffer.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [], 'a list that cannot receive stimulates nothing, whatever its mode says'
    assert handle.sch_m_enter_xcp_stim_buffer.call_count == 0


def test_a_list_that_cannot_receive_never_reaches_another_lists_slot():
    """The same guard where the failure would be silent instead of fatal.

    stimSlotBase is 0 for a list the generator reserved nothing for (DD43), and 0 is also the base
    of the FIRST list that CAN receive. So in a build that has a pool, an apply that skipped the
    type check would not crash: it would read the receiving list's slot and write that master's
    payload through THIS list's entry addresses -- a variable stimulated that no master ever named,
    in a list the master asked only to measure.

    DAQ1 receives and is stimulated normally; DAQ2 is DAQ-typed, points at a different address, and
    has its mode forced exactly as above. The assertion is the whole write sequence, so DAQ2's
    address appearing at all fails it -- there is no threshold or count that would let it through.
    """
    config = DefaultConfig(identification_field_type='ABSOLUTE',
                           daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=1, max_odt_entries=1),
                                 daq(name='DAQ2', type='DAQ', max_odt=1, max_odt_entries=1)),
                           events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),))
    handle = XcpTest(config)
    connect(handle)
    assert handle.lib.Xcp_Ptr.config.daqList[1].stimSlotBase == 0, \
        'the non-receiving list shares the first receiving list\'s base, which is what makes this'
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),), daq_list=0)
    configure_entries(handle, ((4, SECOND_ADDRESS, 0x00),), daq_list=1)
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[1].mode = 0x42
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[:4]), \
        'only the list the master stimulated was written; DAQ2 read no slot at all'


def test_the_payload_is_copied_under_the_area_and_memory_written_outside_it():
    """DD37, in both of its halves.

    **Held per slot, not around the loop.** Two ODTs, each with a frame of its own, so a correct
    apply enters the area exactly twice in one trigger. An implementation that wrapped the whole
    apply in one section would enter once, which is what this counts.

    **Released before any memory is written.** SchM_Enter_Xcp_StimBuffer suspends the context the
    receive callback runs in; Xcp_WriteSlaveMemoryTable calls out to integrator code of unbounded
    duration, and holding an interrupt lock across it is the mistake Xcp_DaqSampleOdt avoids in the
    other direction (it copies its entries under the area and reads memory outside it) and that
    test/stub/SchM_Xcp.h's own contract warns about for CanIf_Transmit. Every write is therefore
    observed with the harness's own "area held" flag, and every one of them must see it clear.

    The harness asserts globally, after every test, that neither area was nested, unbalanced or
    leaked -- so neither of these two properties is covered by that bookkeeping, which is why they
    are asserted here.
    """
    config = stimulation_config(max_odt=2, max_odt_entries=1)
    handle = XcpTest(config)
    connect(handle)
    for odt in range(2):
        configure_entries(handle, ((4, FIRST_ADDRESS + (0x100 * odt), 0x00),), odt=odt)
    set_daq_list_mode(handle, mode=0x02)
    start_daq_list(handle)
    for odt, payload in enumerate((PAYLOAD, SECOND_PAYLOAD)):
        deliver(handle, (odt,) + payload[:4], config.default_daq_dto_pdu_mapping)
    held = list()

    def write_slave_memory(_p_address, _p_buffer):
        held.append(handle.stim_buffer_area_held)

    handle.xcp_write_slave_memory_u8.side_effect = write_slave_memory
    handle.sch_m_enter_xcp_stim_buffer.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    assert len(held) == 8, 'both ODTs applied, or this proves nothing about either'
    assert held == [False] * 8, 'memory is written with the stimulation area released'
    assert handle.sch_m_enter_xcp_stim_buffer.call_count == 2, \
        'the area is taken once per slot, not once around the whole apply'


def test_a_clear_arriving_between_two_entry_writes_does_not_redirect_the_second():
    """DD14, on the writing side, and it is the reason the apply snapshots the ODT's entries under
    SchM_Enter_Xcp_DtoQueue before it writes anything through them.

    CLEAR_DAQ_LIST is legal against a RUNNING list -- 1.1/1.6.4.2.1.1 says the running transmission
    "will be stopped" as part of executing it, not that the command is refused -- and it arrives in
    CanIf's receive context, which can preempt the trigger. Xcp_DaqListClearEntries
    (source/Xcp_Daq.c) resets each entry's address to NULL_PTR and its length to 0 as separate
    writes under that same area. An apply reading the LIVE entries as it walked them would, from
    the second entry on, either write to address 0 or find a zero length and write nothing.

    This is the exact shape of daq_concurrency_test.py::
    test_a_clear_arriving_between_two_entry_reads_does_not_corrupt_the_frame, on the other
    direction: the clear is injected from inside the FIRST memory callback, so it lands after the
    snapshot was taken and before the second entry is written -- precisely the window the snapshot
    exists to close. Xcp_CanIfRxIndication runs the handler synchronously, so no Xcp_MainFunction
    is needed to observe its effect.

    Injected from a memory callback rather than from SchM_Enter_Xcp_DtoQueue: this models a
    preemption that is legitimate, one arriving while the apply holds no area at all, which is what
    makes an unguarded implementation genuinely wrong rather than merely unlucky.
    """
    config = stimulation_config()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((1, FIRST_ADDRESS, 0x00), (1, SECOND_ADDRESS, 0x00)))
    deliver(handle, (0x00,) + PAYLOAD[:2], config.default_daq_dto_pdu_mapping)
    written = list()

    def write_slave_memory(p_address, p_buffer):
        written.append((int(handle.ffi.cast('uint32_t', p_address)), p_buffer[0]))
        if len(written) == 1:
            handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
                    (0xE3, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN'))))

    handle.xcp_write_slave_memory_u8.side_effect = write_slave_memory

    handle.lib.Xcp_TriggerEventChannel(0)

    assert written == [(FIRST_ADDRESS, PAYLOAD[0]), (SECOND_ADDRESS, PAYLOAD[1])], \
        'both entries were written through the snapshot the clear arrived too late to reach'
    assert 0 not in [address for address, _ in written], \
        'and no write was ever handed the cleared address 0'


def test_the_apply_precedes_the_sampling_loop():
    """DD40, and it is load-bearing rather than stylistic.

    A DAQ_STIM list applies and samples on the same event. Applying first is what makes a list that
    stimulates and measures the same variable report the value that was actually in effect, rather
    than the one the stimulus was about to overwrite -- and it is what keeps every StimBuffer
    section closed before the sampler's first DtoQueue section opens, so the two areas can never
    nest.

    Observed as the ORDER of the two memory callbacks within one trigger: the apply writes through
    Xcp_WriteSlaveMemoryTable, the sampler reads through Xcp_ReadSlaveMemoryTable, and every write
    of the cycle must precede every read of it. Ordering is asserted directly rather than through
    the sampled DTO's contents, because the harness's read callback does not model memory -- the
    end-to-end version, where the sampled frame carries the stimulated value, is Task 9's.
    """
    config = stimulation_config(max_odt_entries=1)
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, ((4, FIRST_ADDRESS, 0x00),))
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    order = list()

    handle.xcp_write_slave_memory_u8.side_effect = lambda _a, _b: order.append('apply')
    handle.xcp_read_slave_memory_u8.side_effect = lambda _a, _e, _b: order.append('sample')

    handle.lib.Xcp_TriggerEventChannel(0)

    assert order == ['apply'] * 4 + ['sample'] * 4, \
        'the whole apply completes before the sampling loop reads anything'


def test_the_prescaler_divides_the_apply_rate_as_it_divides_the_sample_rate():
    """The apply belongs to the DAQ list's cycle, not to the raw event raster. 1.1/1.6.4.1.1.3
    makes the prescaler a reduction of the event channel's rate FOR THAT LIST, and a list that
    stimulated on every trigger while sampling every third would run its two directions at
    different rates -- which is exactly what DD40's ordering guarantee is about not doing.

    Nine triggers at prescaler 3 therefore give three applied rounds, the same three rounds
    daq_runtime_test.py::test_the_prescaler_divides_the_trigger_rate counts on the sampling side.
    """
    config = stimulation_config(max_odt_entries=1)
    handle = XcpTest(config)
    connect(handle)
    configure_entries(handle, ((4, FIRST_ADDRESS, 0x00),))
    assert response(handle, (0xE0, 0x02) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) +
                    (0x00, 0x00, 0x03, 0x00))[0] == 0xFF, 'SET_DAQ_LIST_MODE at prescaler 3'
    start_daq_list(handle)
    deliver(handle, (0x00,) + PAYLOAD[:4], config.default_daq_dto_pdu_mapping)
    written = capture_writes(handle)

    for _ in range(9):
        handle.lib.Xcp_TriggerEventChannel(0)

    assert written == expected(FIRST_ADDRESS, PAYLOAD[:4]) * 3, \
        'nine triggers at prescaler 3 apply three times, not nine'

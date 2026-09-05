#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A master stimulating a variable end to end, through the protocol (SP3 Task 9).

Every other file in this sub-project takes one layer apart. stim_decode_test.py pins the
identification field, stim_reception_test.py pins what reaches the slot, stim_apply_test.py pins
what the apply hands to Xcp_WriteSlaveMemoryTable. Each of them reaches into the module to set up
the layer below it: they write the ODT entries through the protocol but assert against the write
table, or construct a runtime mode byte the command set refuses to produce.

**This file does none of that.** Every configuration step is a command a real master sends, every
stimulation frame arrives through Xcp_CanIfRxIndication, and the assertions are on a MODEL OF ECU
MEMORY that the module's own read and write callbacks are wired into. Nothing here inspects the
slot, the ODT entries or the mode field to decide whether stimulation worked; the question is only
ever "does the variable hold the master's bytes", which is the question the whole sub-project
exists to answer and the one no individual layer's test asks.

That memory model is what makes the ordering test at the bottom possible at all. stim_apply_test's
own DD40 test observes the ORDER of the two memory callbacks, because the harness's read callback
returns nothing by default; here the acquiring list genuinely reads back what the stimulating list
just wrote, and the sampled DTO carries it. That is the guarantee DD40 exists for, stated as the
master would see it.
"""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect

# The bytes a master stimulates with: four distinct values, none of them 0x00 and none equal to
# SENTINEL below. Distinctness is load-bearing everywhere in this file -- an applied payload that
# is one byte off must produce a different assertion failure rather than a silently equal one.
PAYLOAD = (0x11, 0x22, 0x33, 0x44)

# A second, wholly different payload, for the preemption test's two rounds.
SECOND_PAYLOAD = (0x66, 0x77, 0x88, 0x99)

# What memory holds before anything stimulates it. Every byte differs from PAYLOAD's and from
# SECOND_PAYLOAD's, so "the apply never ran" and "the apply ran and wrote the right thing" are
# never the same tuple. 0x00 would not do: an unwritten address in the model reads as 0x00 anyway.
SENTINEL = (0xE1, 0xE2, 0xE3, 0xE4)

# The address of the variable the master stimulates, and of the guard byte immediately past it. The
# guard is seeded and asserted unchanged wherever a four-byte entry is applied, so an apply that
# wrote one byte too many is a failure rather than a value nobody looks at.
VARIABLE = 0x1000
GUARD = VARIABLE + 4

# A second variable, far enough from the first that an entry written through the WRONG base address
# and advanced by the running offset lands at 0x1004 -- distinguishable from 0x2000 rather than
# merely "some other address".
SECOND_VARIABLE = 0x2000


class SlaveMemory(object):
    """A byte-addressed model of the ECU memory behind Xcp_ReadSlaveMemoryTable and
    Xcp_WriteSlaveMemoryTable, so a value stimulated through one can be read back through the
    other.

    The module's only route to slave memory is those two tables (the integrator supplies them), so
    modelling them IS modelling memory as far as this module is concerned. The harness leaves both
    returning nothing by default, which is right for tests that assert on calls; it is not enough
    here, where the point is that the stimulated value is genuinely there afterwards -- for the
    acquiring list of the ordering test to sample, and for these assertions to read.

    BYTE granularity only, which every configuration in this file uses (DefaultConfig's own
    default): one callback is then one byte and the model needs no element arithmetic. The
    per-element address advance at WORD and DWORD granularity is swept by
    stim_apply_test.py::test_an_entry_is_applied_one_element_at_a_time_at_the_configured_granularity;
    wiring only the u8 pair here means a configuration that reached the u16 or u32 table would
    write nothing this model could see, and the assertions would fail rather than quietly pass.
    """

    def __init__(self, handle):
        self._handle = handle
        self._bytes = dict()
        handle.xcp_write_slave_memory_u8.side_effect = self._write
        handle.xcp_read_slave_memory_u8.side_effect = self._read

    def _address_of(self, p_address):
        return int(self._handle.ffi.cast('uint32_t', p_address))

    def _write(self, p_address, p_buffer):
        self._bytes[self._address_of(p_address)] = p_buffer[0]

    def _read(self, p_address, _extension, p_buffer):
        p_buffer[0] = self._bytes.get(self._address_of(p_address), 0x00)

    def seed(self, address, values):
        """Puts `values` at `address` without going through the module, as whatever wrote that
        variable before the master ever connected would have."""
        for index, value in enumerate(values):
            self._bytes[address + index] = value

    def read(self, address, length):
        return tuple(self._bytes.get(address + index, 0x00) for index in range(length))


def exchange(handle, request, length=8):
    """One CTO exchange, returning the first `length` response bytes."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def command(handle, request, what):
    """One command, asserted accepted. Every configuration step in this file goes through here: a
    step that was silently refused would leave the list in a state that makes the final memory
    assertion fail for a reason that has nothing to do with stimulation."""
    assert exchange(handle, request)[0] == 0xFF, '{} was refused'.format(what)


def deliver(handle, frame, rx_pdu_id):
    """One stimulation frame on the DAQ list's own RX PDU, followed by the main function -- so a
    handler that wrongly assembled a response is caught transmitting it (DD46)."""
    handle.lib.Xcp_CanIfRxIndication(rx_pdu_id, handle.get_pdu_info(frame))
    handle.lib.Xcp_MainFunction()


def set_daq_ptr(handle, daq_list=0, odt=0, entry=0):
    command(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) + (odt, entry),
            'SET_DAQ_PTR')


def write_daq(handle, size, address):
    command(handle, (0xE1, 0xFF, size, 0x00) + tuple(u32_to_array(address, 'LITTLE_ENDIAN')),
            'WRITE_DAQ')


def set_daq_list_mode(handle, daq_list=0, mode=0x02, event_channel=0):
    command(handle, (0xE0, mode) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) +
            tuple(u16_to_array(event_channel, 'LITTLE_ENDIAN')) + (0x01, 0x00),
            'SET_DAQ_LIST_MODE')


def start_daq_list(handle, daq_list=0):
    command(handle, (0xDE, 0x01) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')),
            'START_STOP_DAQ_LIST(START)')


def stop_daq_list(handle, daq_list=0):
    command(handle, (0xDE, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')),
            'START_STOP_DAQ_LIST(STOP)')


def configure_entry(handle, address, size=len(PAYLOAD), daq_list=0, odt=0):
    set_daq_ptr(handle, daq_list=daq_list, odt=odt)
    write_daq(handle, size, address)


def queued_frames(handle):
    """Every frame currently in the DTO ring, oldest first. Same reader as
    test/daq_dynamic_acceptance_test.py's."""
    queue = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].dtoQueue
    frames = list()
    index = queue.read
    for _ in range(queue.count):
        frame = queue.frame[index]
        frames.append(tuple(frame.data[0:frame.length]))
        index = (index + 1) % queue.depth
    return frames


#: (identification field type, the SET_DAQ_LIST_MODE byte, the header a frame for list 0 / ODT 0
#: carries in front of its payload). One case per row of the design document's own offset table,
#: plus PID_OFF -- which is a runtime mode bit rather than a configured type (1.1/1.1.2.1 removes
#: the identification field entirely), so it configures ABSOLUTE and asks for bit 5 on top of
#: DIRECTION.
#:
#: The RELATIVE_WORD_ALIGNED case fills its dummy byte with 0xFF rather than 0x00: 1.1/1.1.2.1
#: gives that byte no defined value, so a decoder that read it would be reading noise, and a
#: master is free to send anything there. 0x00 would let a decoder that mistook the FILL byte for
#: part of the DAQ list number still arrive at list 0.
IDENTIFICATION_CASES = (
    pytest.param('ABSOLUTE', 0x02, (0x00,), id='ABSOLUTE'),
    pytest.param('RELATIVE_BYTE', 0x02, (0x00, 0x00), id='RELATIVE_BYTE'),
    pytest.param('RELATIVE_WORD', 0x02, (0x00, 0x00, 0x00), id='RELATIVE_WORD'),
    pytest.param('RELATIVE_WORD_ALIGNED', 0x02, (0x00, 0xFF, 0x00, 0x00),
                 id='RELATIVE_WORD_ALIGNED'),
    pytest.param('ABSOLUTE', 0x22, (), id='PID_OFF'),
)


@pytest.mark.parametrize('identification_field_type, mode, header', IDENTIFICATION_CASES)
def test_a_master_stimulates_a_variable_end_to_end_through_the_protocol(identification_field_type,
                                                                       mode, header):
    """The whole sub-project in one test, and the acceptance criterion §9 states first: a master
    allocates a DAQ list out of a dynamic pool, points an ODT entry at a variable, puts the list
    into stimulation mode, starts it, sends one frame, and the variable holds its bytes.

        FREE_DAQ -> ALLOC_DAQ -> ALLOC_ODT -> ALLOC_ODT_ENTRY -> SET_DAQ_PTR -> WRITE_DAQ ->
        SET_DAQ_LIST_MODE(DIRECTION = STIM) -> START_STOP_DAQ_LIST -> a frame -> a trigger -> STOP

    Every one of those is a real command on the wire, and every one is asserted accepted. It is
    the inverse of daq_dynamic_acceptance_test.py::
    test_the_allocation_sequence_end_to_end_reaches_a_sampled_frame, which walks the same
    allocation sequence in the acquisition direction -- and it is the test that would notice if any
    single step did not in fact work the way its own dedicated test says it does.

    **Swept over all four identification field types and PID_OFF**, which §9 asks for in those
    words. Each one puts the payload at a different offset in the frame, and each offset is already
    pinned inside the decoder by stim_decode_test.py -- but pinned there as a returned number, not
    as bytes arriving in a variable. Composing the decode with the apply is what this sweep adds,
    and it is the same argument the timestamped case below rests on: an offset that is right in
    isolation and wrong in composition writes the master's data to the wrong addresses with nothing
    on the bus to report it.

    Three assertions, in the order the failures they catch would occur:

    - **before the trigger, the variable still holds what it held.** DD36 puts the write in the
      trigger's context and never in the receive callback's; a slave that applied on arrival would
      write memory from CanIf's context, and would pass the final assertion below while doing it.
    - **after the trigger, the variable holds the master's four bytes.** The feature.
    - **the byte past the variable is untouched.** The entry is four bytes wide, so a fifth write
      is an overrun into whatever the integrator put next to that variable -- silent, and exactly
      the class of failure the design document's §7 names as this sub-project's principal risk.

    STOP is sent last and asserted, because it is part of the round trip a master performs and
    nothing else here would notice a list that could be started but not stopped.

    The pool is one list of one ODT for every case, which PID_OFF requires and the others do not
    mind: SP2b's Xcp_DaqListTxPduIsExclusive rule has its receive-side twin here, and a dynamic
    pool shares one PDU across every list it holds (script/source_cfg.c.jinja2), so PID_OFF is
    grantable only to a pool of one.
    """
    config = stim_config(daq_count=1, odt_count=1, odt_entries_count=1,
                         identification_field_type=identification_field_type)
    handle = XcpTest(config)
    connect(handle)
    memory = SlaveMemory(handle)
    memory.seed(VARIABLE, SENTINEL)
    memory.seed(GUARD, (0xA5,))

    command(handle, (0xD6,), 'FREE_DAQ')
    command(handle, (0xD5, 0x00, 0x01, 0x00), 'ALLOC_DAQ(1 list)')
    command(handle, (0xD4, 0x00, 0x00, 0x00, 0x01), 'ALLOC_ODT(list 0, 1 ODT)')
    command(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01), 'ALLOC_ODT_ENTRY(list 0, ODT 0, 1 entry)')
    configure_entry(handle, VARIABLE)
    set_daq_list_mode(handle, mode=mode)
    start_daq_list(handle)

    deliver(handle, header + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert memory.read(VARIABLE, 4) == SENTINEL, \
        'the frame arrived, but DD36 applies it at the trigger and not in the receive callback'

    handle.lib.Xcp_TriggerEventChannel(0)

    assert memory.read(VARIABLE, 4) == PAYLOAD, \
        'the master stimulated the variable; it must hold exactly the bytes it sent'
    assert memory.read(GUARD, 1) == (0xA5,), 'and nothing past the four bytes the entry describes'

    stop_daq_list(handle)


def timestamped_config(size):
    """One DAQ_STIM list of two ODTs, ABSOLUTE identification, and a clock of `size`.

    MAX_DTO is 16 rather than the default 8 so ODT 0's frame -- one PID byte, up to four timestamp
    bytes and a four-byte payload -- fits inside what Xcp_DaqStoreStim accepts (1.1/1.1.4.2 bounds
    a DTO at MAX_DTO, and the slave refuses a longer frame outright).
    """
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         max_dto=16,
                         timestamp=timestamp(size=size),
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=2, max_odt_entries=1),))


# Four bytes that look like nothing else in this file, truncated to the configured wire size. What
# the master puts in a STIM timestamp is the slave's own clock echoed back (1.0/1.1.2.2), so any
# value is well-formed; these are chosen only to be unmistakable in a failing assertion. None of
# them appears in PAYLOAD, so a payload read one byte short applies a timestamp byte to the
# variable and fails on the value, not merely on a length.
TIMESTAMP_BYTES = (0xDE, 0xAD, 0xBE, 0xEF)


@pytest.mark.parametrize('size', timestamp_sizes)
def test_a_timestamped_list_applies_odt_0_past_its_timestamp_and_odt_1_without_one(size):
    """DD44, composed end to end -- and §7 calls this the highest-consequence detail in the
    sub-project.

    A STIM DTO carries a timestamp when the list is in timestamped mode (1.1/1.1.2.2: "The
    TIMESTAMP flag can be used as well for DIRECTION = DAQ as for DIRECTION = STIM"), on ODT 0 of
    the cycle and no other (1.1/1.1.2.2 Diagram 10, "TS only in first DTO Packet of sample"). So
    the payload starts at a different offset in ODT 0's frame than in ODT 1's, in the same list, at
    the same moment -- and the slave gets the width from its own configuration, because the master
    is obliged to use the Type of Timestamp Field the slave published.

    The pieces of that offset are each pinned already: stim_decode_test.py pins what the decoder
    returns, stim_reception_test.py pins what lands in the slot, stim_apply_test.py pins what the
    apply writes. **None of them composes the three.** A payload read one, two or four bytes off
    writes the master's data to the wrong addresses and nothing in the protocol reports it, so the
    assertion here is on the applied VALUES of both ODTs, at both addresses, for every timestamp
    width the slave can be configured with.

    Both ODTs, in one trigger, is what makes this a discriminator rather than a demonstration:

    - if the timestamp were not skipped at all, ODT 0's variable would hold the timestamp's own
      bytes and ODT 1's would still be right;
    - if it were skipped on every ODT rather than only on ODT 0, ODT 1's frame would be short of
      what its entry needs, DD39 would drop it at reception, and ODT 1's variable would still hold
      the sentinel while ODT 0's was right;
    - if the width were the compile-time XCP_DAQ_TIMESTAMP_SIZE rather than the running
      configuration's own, the BYTE and WORD cases would apply from the wrong offset while the
      DWORD case passed.

    Only an implementation that adds exactly Xcp_TimestampWireSize(timestampType), exactly on ODT
    0, passes all three of those at once.
    """
    config = timestamped_config(size)
    wire_size = timestamp_wire_size[size]
    handle = XcpTest(config)
    connect(handle)
    memory = SlaveMemory(handle)
    memory.seed(VARIABLE, SENTINEL)
    memory.seed(SECOND_VARIABLE, SENTINEL)

    configure_entry(handle, VARIABLE, odt=0)
    configure_entry(handle, SECOND_VARIABLE, odt=1)
    # 0x12: TIMESTAMP (bit 4) and DIRECTION (bit 1). The stored TIMESTAMP bit is what reception
    # reads to decide whether ODT 0's frame carries the field at all, so a refused request here
    # would silently turn this into the untimestamped case.
    set_daq_list_mode(handle, mode=0x12)
    start_daq_list(handle)

    # ODT 0 carries the timestamp between its identification field and its payload; ODT 1 does not.
    deliver(handle, (0x00,) + TIMESTAMP_BYTES[0:wire_size] + PAYLOAD,
            config.default_daq_dto_pdu_mapping)
    deliver(handle, (0x01,) + SECOND_PAYLOAD, config.default_daq_dto_pdu_mapping)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert memory.read(VARIABLE, 4) == PAYLOAD, \
        'ODT 0 applies from past its {}-byte timestamp'.format(wire_size)
    assert memory.read(SECOND_VARIABLE, 4) == SECOND_PAYLOAD, \
        'and ODT 1, which carries no timestamp, applies from directly past its PID'


def stimulated_and_measured_config():
    """Two lists on one event channel, both pointed at the SAME variable: DAQ1 (index 0) measures
    it, DAQ2 (index 1) stimulates it.

    The stimulating list holds the HIGHER index deliberately, exactly as
    stim_apply_test.py::one_acquiring_and_one_stimulating_list does. DD40 requires every
    stimulating list to apply before ANY acquiring list samples; a single interleaved pass over the
    lists would satisfy that only when the stimulating list happened to come first, so putting it
    second is what turns an accident of configuration order into an assertion.

    ABSOLUTE identification, so DAQ1 owns absolute PID 0 and DAQ2 owns absolute PID 1 -- which is
    both the byte a stimulation frame for DAQ2 carries and the byte DAQ1's sampled frame leads
    with.
    """
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         daqs=(daq(name='DAQ1', type='DAQ', max_odt=1, max_odt_entries=1),
                               daq(name='DAQ2', type='DAQ_STIM', max_odt=1, max_odt_entries=1)),
                         events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),))


def test_a_list_measuring_a_stimulated_variable_reports_the_stimulated_value():
    """DD40, as the master sees it, and the reason the ordering is not a free choice.

    One event channel carries two lists. DAQ2 stimulates a variable; DAQ1 measures that same
    variable. Applying every stimulating list before sampling any acquiring list is what makes the
    measurement report the value that was ACTUALLY IN EFFECT during the cycle, rather than the one
    the stimulus was about to replace -- which is the whole point of a bypassing setup, where the
    master stimulates an input and measures the ECU's response to it in the same cycle.

    stim_apply_test.py::test_the_apply_precedes_the_sampling_loop pins the same ordering by
    observing which memory callback fired first, and says in its own docstring that the end-to-end
    version -- where the sampled frame carries the stimulated value -- is this one. The difference
    is that this one cannot pass for a reason unrelated to the order: memory is modelled here, so
    the sampled DTO's payload IS whatever was in the variable when DAQ1 read it.

    Seeded with SENTINEL first, which is what makes the failure legible rather than merely present:
    against a slave that sampled before it applied, the queued frame carries 0xE1 rather than 0x11,
    and the assertion says which of the two values the measurement caught.

    The frame is asserted whole, PID included. DAQ1 is the lower-numbered list, so its absolute PID
    is 0 and DAQ2's is 1; a frame arriving with PID 1 would mean the stimulating list had sampled
    as well, which the corrected DD40 says it must not (1.1/1.6.4.1.1.3 -- DIRECTION selects
    acquisition **or** stimulation).
    """
    config = stimulated_and_measured_config()
    handle = XcpTest(config)
    connect(handle)
    memory = SlaveMemory(handle)
    memory.seed(VARIABLE, SENTINEL)

    configure_entry(handle, VARIABLE, daq_list=0)
    set_daq_list_mode(handle, daq_list=0, mode=0x00)
    start_daq_list(handle, daq_list=0)
    configure_entry(handle, VARIABLE, daq_list=1)
    set_daq_list_mode(handle, daq_list=1, mode=0x02)
    start_daq_list(handle, daq_list=1)
    deliver(handle, (0x01,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert memory.read(VARIABLE, 4) == PAYLOAD, 'the stimulus reached the variable'
    assert queued_frames(handle) == [(0x00,) + PAYLOAD], \
        'DAQ1 measured the variable after DAQ2 stimulated it, though DAQ1 is the lower-numbered ' \
        'list -- a frame carrying {} would mean it sampled first'.format(SENTINEL)


def test_a_frame_arriving_while_the_trigger_holds_no_area_applies_to_the_next_cycle():
    """DD37's exclusive area, exercised as an interleaving rather than as a call count.

    Xcp_DaqStoreStim runs in CanIf's receive context and Xcp_TriggerEventChannel is documented
    callable from an interrupt, so a stimulation frame really can arrive part-way through an apply.
    It cannot arrive *anywhere*: SchM_Enter_Xcp_StimBuffer exists to suspend that context, so the
    points where a frame can genuinely land are the points at which the area is not held.

    **This test injects at the area's EXIT, which is the legitimate preemption** -- the same
    distinction SP2d drew for FREE_DAQ (test/free_daq_test.py::
    test_a_trigger_preempting_free_daq_at_any_area_release_samples_nothing). Injecting at the
    *enter* would model a preemption the area exists to forbid, and the harness's own bookkeeping
    correctly reports it as a double-enter rather than as a finding about the module.

    The exit of Xcp_DaqApplyStimOdt's first section is the one interleaving point that matters:
    the payload and its length have just been copied out of the slot, and no memory has been
    written yet. So the new frame lands squarely inside the window the copy exists to close, and
    two things must hold:

    - **this cycle applies the OLD payload, whole.** Both entries, from one frame, with no byte of
      the new one mixed in. An apply that read the slot live as it walked the entries would write
      the NEW payload here, and an apply that read `length` under the area but the bytes outside it
      would write a mixture -- both are the DD14 failure class, and both fail this assertion.
    - **the NEXT cycle applies the new payload.** The frame was accepted, not merely survived: a
      slave that dropped a frame arriving mid-apply would pass the first assertion and lose the
      master's data silently.

    Two entries at two addresses, so "coherent" is a statement about a payload split across
    entries rather than about a single copy. The area bookkeeping is asserted directly as well:
    the injected reception takes the area itself, and that it did so without nesting is what says
    the release point really was outside it.

    **This test is the only thing in the tree that holds the snapshot, and it is not "just a
    concurrency test".** Verified by mutation, and confirmed independently by Task 9's reviewer
    against every candidate injection point: an apply that wrote from `p_slot->data` directly --
    reading the slot live as it walks the entries, instead of the copy it took under the area --
    passes every test in stim_apply_test.py, stim_reception_test.py and stim_decode_test.py.
    stim_apply_test.py::test_the_payload_is_copied_under_the_area_and_memory_written_outside_it
    comes closest and still does not catch it: it counts the area's entries and asserts memory is
    written with it released, but never that the copy's CONTENTS are what get written. Do not trim
    this test on the strength of a green run.
    """
    config = DefaultConfig(identification_field_type='ABSOLUTE',
                           daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=1, max_odt_entries=2),))
    handle = XcpTest(config)
    connect(handle)
    memory = SlaveMemory(handle)
    memory.seed(VARIABLE, SENTINEL)
    memory.seed(SECOND_VARIABLE, SENTINEL)

    set_daq_ptr(handle)
    write_daq(handle, 2, VARIABLE)
    write_daq(handle, 2, SECOND_VARIABLE)
    set_daq_list_mode(handle, mode=0x02)
    start_daq_list(handle)
    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    original_exit = handle.sch_m_exit_xcp_stim_buffer.side_effect
    state = {'fired': False}

    def exit_and_preempt():
        original_exit()
        # `fired` also guards against recursion: the injected reception takes and releases this
        # very area, which re-enters this side effect.
        if state['fired'] is False:
            state['fired'] = True
            handle.lib.Xcp_CanIfRxIndication(
                    config.default_daq_dto_pdu_mapping,
                    handle.get_pdu_info((0x00,) + SECOND_PAYLOAD))

    handle.sch_m_exit_xcp_stim_buffer.side_effect = exit_and_preempt

    handle.lib.Xcp_TriggerEventChannel(0)

    handle.sch_m_exit_xcp_stim_buffer.side_effect = original_exit

    assert state['fired'] is True, 'the apply never released the area, so nothing was interleaved'
    assert (memory.read(VARIABLE, 2), memory.read(SECOND_VARIABLE, 2)) == \
           (PAYLOAD[0:2], PAYLOAD[2:4]), \
        'the cycle applies the payload it copied out before the preemption, whole'
    assert handle.stim_buffer_area_violations == []

    handle.lib.Xcp_TriggerEventChannel(0)

    assert (memory.read(VARIABLE, 2), memory.read(SECOND_VARIABLE, 2)) == \
           (SECOND_PAYLOAD[0:2], SECOND_PAYLOAD[2:4]), \
        'and the frame that preempted it was stored, not dropped: the next cycle applies it'

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Receiving a stimulation frame and buffering it in its ODT's slot (SP3 Task 7, DD36/DD37/DD39).

Xcp_DaqStoreStim is the whole of what a STIM DTO does in the receive callback: it decodes the
identification field (Task 6), checks DD39's conditions, and copies the payload and its length into
one Xcp_StimSlotType under SchM_Enter_Xcp_StimBuffer. Nothing else. DD36's argument that a
stimulation PDU may preempt a CTO mid-dispatch without corrupting anything rests on exactly that:
the handler touches its own slot and nothing the CTO path owns.

**Every rejection here asserts the slot is UNCHANGED, not merely that the frame was refused.** A
DTO is not a command and no master is waiting on one, so there is no response to inspect: a
stimulation frame that is silently stored when it should have been dropped is invisible from the
bus, and would surface a cycle later as memory written from data the slave should never have kept.
The slot is therefore the only evidence, and `Det` the only channel a rejection has (DD39).
"""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect

# The bytes a master stimulates with. Four distinct values, none of them 0x00: a slot left
# untouched reads as zeros, so a payload of zeros would make "stored" and "not stored"
# indistinguishable in every rejection test below.
PAYLOAD = (0x11, 0x22, 0x33, 0x44)

# The width of the single ODT entry every list in this file is configured with, and therefore the
# payload length DD39 requires of a frame addressing it.
ENTRY_SIZE = len(PAYLOAD)


def response(handle, request):
    """One CTO exchange, returning the first two response bytes."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def configure_one_entry(handle, daq_list=0, size=ENTRY_SIZE, address=0x1000):
    """SET_DAQ_PTR to (daq_list, ODT 0, entry 0), then WRITE_DAQ one entry of `size` bytes. Both
    steps are asserted: a list whose entries were silently not written has a required payload
    length of zero, which would make the short-payload rejection below unreachable."""
    assert response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) +
                    (0x00, 0x00))[0] == 0xFF, 'SET_DAQ_PTR was refused'
    assert response(handle, (0xE1, 0xFF, size, 0x00) +
                    tuple(u32_to_array(address, 'LITTLE_ENDIAN')))[0] == 0xFF, 'WRITE_DAQ was refused'


def set_daq_list_mode(handle, daq_list=0, mode=0x02):
    """SET_DAQ_LIST_MODE, asserting the slave accepted it. DIRECTION is bit 1 in the request byte
    and in the stored mode alike; the stored bit is what Xcp_DaqStoreStim reads, so a refused
    request must not be mistaken for a configured one."""
    assert response(handle, (0xE0, mode) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')) +
                    (0x00, 0x00, 0x01, 0x00))[0] == 0xFF, 'SET_DAQ_LIST_MODE was refused'


def start_daq_list(handle, daq_list=0):
    assert response(handle, (0xDE, 0x01) + tuple(u16_to_array(daq_list, 'LITTLE_ENDIAN')))[0] == 0xFF, \
        'START_STOP_DAQ_LIST was refused'


def running_stim_list(handle, daq_list=0, mode=0x02, size=ENTRY_SIZE):
    """The state DD39 accepts a frame in: one entry written, DIRECTION = STIM, RUNNING."""
    configure_one_entry(handle, daq_list=daq_list, size=size)
    set_daq_list_mode(handle, daq_list=daq_list, mode=mode)
    start_daq_list(handle, daq_list=daq_list)


def slot(handle, daq_list=0, odt=0):
    """The Xcp_StimSlotType this (list, ODT) addresses -- stimSlot[stimSlotBase + odt], which is
    the whole of the addressing rule in both configuration models (DD43)."""
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlot[
        handle.lib.Xcp_Ptr.config.daqList[daq_list].stimSlotBase + odt]


def slot_state(handle, daq_list=0, odt=0):
    """(length, every byte of the slot's buffer). The whole buffer, not the first `length` bytes:
    a rejection that wrote the payload but left `length` at zero must be visible as a change, and
    slicing by `length` would hide exactly that."""
    one = slot(handle, daq_list, odt)
    return one.length, tuple(one.data)


def rejections(handle):
    """The Det reports Xcp_DaqStoreStim raised for dropped frames, filtered out of whatever else
    the setup commands reported."""
    return [call for call in handle.det_report_error.call_args_list
            if call[0][3] == handle.define('XCP_E_STIM_FRAME_REJECTED')]


def deliver(handle, frame, rx_pdu_id):
    """One stimulation frame on `rx_pdu_id`, followed by the main function -- so that a handler
    which wrongly assembled a response would be caught transmitting it, not merely filling a
    buffer nobody sends."""
    handle.lib.Xcp_CanIfRxIndication(rx_pdu_id, handle.get_pdu_info(frame))
    handle.lib.Xcp_MainFunction()


def one_stimulation_list(**kwargs):
    """A single DAQ_STIM list of one ODT. ABSOLUTE identification, so its ODT 0 is absolute PID 0
    and the frames below are one PID byte followed by their payload."""
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=1, max_odt_entries=1),),
                         **kwargs)


def test_a_received_frame_is_stored_in_its_odts_slot():
    """DD36/DD39's accepting case: the payload the master sent, and its length, land in the slot
    that ODT addresses.

    The length is asserted as well as the bytes because the two are what Xcp_DaqApplyStim reads
    back as a pair -- a slot holding the right bytes under a length of zero applies nothing, and a
    slot holding a length longer than what arrived applies whatever the previous frame left behind.

    Nothing is transmitted in answer: 1.1/1.1.4.2's DTO is not a command, so there is no response
    to assemble and no master waiting on one (DD39). A handler that filled the CTO response buffer
    -- the one thing DD36 says a receive-context handler must never touch -- would be caught here.
    """
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)
    handle.can_if_transmit.reset_mock()

    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert (slot(handle).length, tuple(slot(handle).data[0:ENTRY_SIZE])) == (ENTRY_SIZE, PAYLOAD)
    assert handle.can_if_transmit.call_count == 0, 'a DTO is not a command; nothing answers one'
    assert rejections(handle) == [], 'the frame was accepted, so nothing is reported'


def test_the_payload_and_its_length_are_written_inside_the_exclusive_area():
    """DD37, and the half of it the harness's own bookkeeping cannot see. test/conftest.py asserts
    globally, after every test, that neither exclusive area was nested, unbalanced or leaked -- so
    a slot written OUTSIDE a correctly entered and exited area passes all of that silently.

    This observes the slot from inside the area instead: once on entry, where it must still be
    empty, and once on exit, where it must already hold the whole frame. Both the payload and the
    length are checked at both points, because `length` paired with the buffer it describes is the
    DD14 failure class -- writing one inside the area and the other outside it is exactly the
    torn pair DD37 exists to prevent, and it would satisfy an assertion that looked only at the
    bytes.
    """
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)
    before = slot_state(handle)
    observed = list()
    enter_bookkeeping = handle.sch_m_enter_xcp_stim_buffer.side_effect
    exit_bookkeeping = handle.sch_m_exit_xcp_stim_buffer.side_effect

    def on_enter():
        enter_bookkeeping()
        observed.append(('enter', slot_state(handle)))

    def on_exit():
        observed.append(('exit', slot_state(handle)))
        exit_bookkeeping()

    handle.sch_m_enter_xcp_stim_buffer.side_effect = on_enter
    handle.sch_m_exit_xcp_stim_buffer.side_effect = on_exit

    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    stored = (ENTRY_SIZE, PAYLOAD + before[1][ENTRY_SIZE:])
    assert observed == [('enter', before), ('exit', stored)], \
        'the slot must go from untouched to complete strictly between the enter and the exit'


def test_a_frame_for_a_list_that_cannot_receive_is_dropped():
    """DD39's first condition. A list whose configured type is DAQ has no stimulation slot at all:
    the generator reserves one only for lists that can receive, so its stimSlotBase is 0 and is
    never read (DD43). A handler that skipped the type check would address
    stimSlot[0 + 0] -- the FIRST RECEIVING list's slot -- and apply this frame's bytes to a
    completely unrelated list's addresses.

    The runtime mode is written directly rather than through SET_DAQ_LIST_MODE because the command
    set cannot reach this state: Xcp_DTOCmdDaqSetDaqListMode refuses DIRECTION on a list whose type
    is neither STIM nor DAQ_STIM. That refusal is exactly why the type check here is a SECOND,
    independent guard rather than a duplicate -- and constructing the state directly is what makes
    it independently observable. RUNNING and DIRECTION are both set, and the DAQ list has no
    entries written, so its required payload length is zero: the type check is the only thing left
    that can refuse this frame.
    """
    config = DefaultConfig(identification_field_type='ABSOLUTE',
                           daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=1, max_odt_entries=1),
                                 daq(name='DAQ2', type='DAQ', max_odt=1, max_odt_entries=1)),
                           events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),))
    handle = XcpTest(config)
    connect(handle)
    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 1, \
        'only the receiving list reserves a slot, so any write at all lands in DAQ1\'s'
    handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[1].mode = 0x42
    before = slot_state(handle, daq_list=0)

    deliver(handle, (0x01,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert slot_state(handle, daq_list=0) == before, 'the receiving list\'s slot must be untouched'
    assert len(rejections(handle)) == 1, 'the drop is reported through Det, the only channel there is'


def test_a_frame_for_a_list_that_is_not_running_is_dropped():
    """DD39's second condition. DIRECTION is set and the entries are written, but
    START_STOP_DAQ_LIST never ran -- 1.1/1.6.4.1.1.4 makes RUNNING what says a list is live, and a
    stopped list's slot must not be filled with data the next START would then apply."""
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    configure_one_entry(handle)
    set_daq_list_mode(handle, mode=0x02)
    before = slot_state(handle)

    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert slot_state(handle) == before
    assert len(rejections(handle)) == 1


def test_a_frame_for_a_list_whose_direction_is_daq_is_dropped():
    """DD39's third condition, and the one that separates a list which CAN receive from one that
    currently is. The list is DAQ_STIM and RUNNING, so both other conditions hold; only the stored
    DIRECTION bit is clear, which 1.1/1.6.4.1.1.3 makes the master's own statement that this list
    measures rather than stimulates. Applying a frame to it would write memory the master asked
    only to read."""
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle, mode=0x00)
    assert (handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[0].mode & 0x42) == 0x40, \
        'RUNNING without DIRECTION is the premise'
    before = slot_state(handle)

    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert slot_state(handle) == before
    assert len(rejections(handle)) == 1


def test_a_payload_shorter_than_the_odts_entries_is_dropped():
    """DD39's fourth condition. The ODT's one entry is four bytes wide, and the frame carries
    three. Rejecting it here rather than at the event is what keeps the apply path from ever
    reasoning about partial data, and attributes the failure to the frame that caused it instead
    of to a cycle that runs later.

    A stored short payload would not be harmless: Xcp_DaqApplyStim walks the ODT's entries and
    writes what each one's length says, so a slot three bytes long against a four-byte entry either
    writes a byte the master never sent or has to invent a rule for the shortfall."""
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)
    before = slot_state(handle)

    deliver(handle, (0x00,) + PAYLOAD[:ENTRY_SIZE - 1], config.default_daq_dto_pdu_mapping)

    assert slot_state(handle) == before
    assert len(rejections(handle)) == 1


def test_a_payload_exactly_as_long_as_the_odts_entries_is_stored():
    """The boundary the test above sits one byte below, on the identical configuration: equality
    is acceptance. Without this, an implementation comparing with `<=` instead of `<` would reject
    every well-formed frame and no test would notice, because every other accepting case in this
    file also carries exactly the required length."""
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)

    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert slot(handle).length == ENTRY_SIZE
    assert rejections(handle) == []


def test_a_frame_longer_than_max_dto_is_dropped():
    """1.1/1.1.4.2 bounds a DTO packet at MAX_DTO, which the slave publishes in its CONNECT
    response, so a longer frame is one the master was told not to send. It is refused rather than
    truncated: Xcp_StimSlotType's buffer is XCP_MAX_DTO bytes, and a payload past that end has
    nowhere to go that is not somebody else's slot.

    MAX_DTO here is the running configuration's, not the build-wide XCP_MAX_DTO macro -- the two
    are equal in a single-configuration harness, and the check is written against the former for
    the same reason the timestamp width is (Xcp_DaqSampleOdt's own note).
    """
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)
    max_dto = handle.lib.Xcp_Ptr.general.maxDto
    before = slot_state(handle)

    deliver(handle, tuple([0x00] + [0x5A] * max_dto), config.default_daq_dto_pdu_mapping)

    assert slot_state(handle) == before, 'a frame of MAX_DTO + 1 bytes is refused whole'
    assert len(rejections(handle)) == 1


def test_a_frame_the_decoder_cannot_resolve_is_dropped():
    """Xcp_DaqReadIdentificationField answering E_NOT_OK is a rejection like any other, and gets
    the same Det report: absolute PID 0x01 belongs to no list in a configuration whose single list
    owns absolute ODT number 0 alone."""
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)
    before = slot_state(handle)

    deliver(handle, (0x01,) + PAYLOAD, config.default_daq_dto_pdu_mapping)

    assert slot_state(handle) == before
    assert len(rejections(handle)) == 1


def two_receiving_lists_on_separate_pdus():
    """Two single-ODT DAQ_STIM lists that do NOT share a receiving PDU.

    Every list in this harness maps to XCP_PDU_ID_TRANSMIT by default, so until this configuration
    existed a handler that ignored rxPduId entirely would have behaved identically to one that
    honoured it. DAQ2's XCP_PDU_ID_STIM_B is left undefined by the harness, so
    script/source_cfg.c.jinja2's own #ifndef fallback assigns it the next free id -- the numbers are
    read back off the configuration below rather than assumed, since a fallback that happened to
    collide would make these tests pass for the wrong reason.

    Distinct PDUs are also what lets BOTH lists hold PID_OFF: Xcp_DaqListTxPduIsExclusive
    (source/Xcp_Daq.c) refuses the bit to a list another list shares a PDU with.
    """
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=1, max_odt_entries=1,
                                   pdu_mapping='XCP_PDU_ID_TRANSMIT'),
                               daq(name='DAQ2', type='DAQ_STIM', max_odt=1, max_odt_entries=1,
                                   pdu_mapping='XCP_PDU_ID_STIM_B')),
                         events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),))


def receiving_pdu(handle, daq_list):
    return handle.lib.Xcp_Ptr.config.daqList[daq_list].dto[0].dto2PduMapping.rxPdu.id


@pytest.mark.parametrize('addressed', (0, 1))
def test_a_pid_off_frame_lands_only_in_the_list_whose_pdu_it_arrived_on(addressed):
    """1.1/1.1.2.1: with the identification field turned off 'the unambiguous identification has to
    be done on the level of the Transport Layer' -- for this module, the PDU the frame arrived on.
    Under PID_OFF the receiving PduId is the ONLY thing that identifies the list, so this is where
    ignoring it is fatal rather than merely wrong.

    Both directions are exercised, on one configuration: a handler that always answered the first
    PID_OFF list passes the `addressed == 0` case by luck and fails `addressed == 1`, and one that
    always answered the last does the reverse. The untouched list is asserted as well as the
    addressed one -- storing into both would satisfy an assertion that only looked at the
    destination, and would stimulate a list the master never addressed.
    """
    handle = XcpTest(two_receiving_lists_on_separate_pdus())
    connect(handle)
    assert receiving_pdu(handle, 0) != receiving_pdu(handle, 1), \
        'the two lists must really receive on different PDUs, or this proves nothing'
    for daq_list in (0, 1):
        # 0x22: PID_OFF (bit 5) and DIRECTION (bit 1). PID_OFF needs ABSOLUTE identification, a
        # single ODT and an unshared PDU, which this configuration gives both lists.
        running_stim_list(handle, daq_list=daq_list, mode=0x22, size=1)
    untouched = 1 - addressed
    before = slot_state(handle, daq_list=untouched)

    deliver(handle, (PAYLOAD[0],), receiving_pdu(handle, addressed))

    assert slot(handle, daq_list=addressed).length == 1
    assert slot(handle, daq_list=addressed).data[0] == PAYLOAD[0]
    assert slot_state(handle, daq_list=untouched) == before, \
        'the list the frame did not address must be untouched'


# --------------------------------------------------------------------------------------------
# Releasing a slot with the DAQ lists it belongs to.
#
# Xcp_DaqFreeAll (source/Xcp_Daq.c) is the single unwind all three paths share -- FREE_DAQ,
# Xcp_Init, and DISCONNECT under DAQ_DYNAMIC -- so the invariant is established once and the three
# tests below check the three doors into it rather than three implementations.
#
# It matters because DD35 makes a slot LATCHED: Xcp_DaqApplyStim re-applies the last payload
# received on EVERY event until a new frame replaces it. A slot that outlived its session would
# therefore not merely hold stale bytes, it would write them into an ECU variable at the first
# trigger of the next session with no master having sent anything -- a write no command asked for
# and no response reports. That is why each test below stores a payload first and asserts it was
# really there: a test that only checked `length == 0` afterwards would pass against a slot that
# had never been written at all.
# --------------------------------------------------------------------------------------------


def assert_payload_is_stored(handle, daq_list=0):
    """Asserts the delivered payload really reached the slot, so the release assertion that
    follows is about something that was demonstrably there rather than about a slot no frame ever
    filled."""
    assert slot(handle, daq_list=daq_list).length == ENTRY_SIZE, \
        'the payload has to be in the slot before a release can be shown to remove it'


def dynamic_stimulation_handle():
    """A DAQ_DYNAMIC pool that can receive, with one list of one ODT of one entry allocated.

    DYNAMIC rather than STATIC because FREE_DAQ and DISCONNECT's unwind are both reachable only
    there: script/source_cfg.c.jinja2 refuses a STATIC configuration that enables any of the four
    allocation APIs, and Xcp_CTOCmdStdDisconnect (source/Xcp_Std.c) gates its Xcp_DaqFreeAll call
    on DAQ_DYNAMIC. The re-initialisation test below covers the static pool, which these two
    cannot reach.
    """
    config = stim_config(daq_count=1, odt_count=1, odt_entries_count=1)
    handle = XcpTest(config)
    connect(handle)
    assert response(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF, 'ALLOC_DAQ one list'
    assert response(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF, 'ALLOC_ODT one ODT'
    assert response(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF, 'ALLOC_ODT_ENTRY one entry'
    running_stim_list(handle)
    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)
    assert_payload_is_stored(handle)
    return handle


def test_free_daq_clears_a_stored_stimulation_payload():
    """1.1/1.6.4.3.1.1: FREE_DAQ 'clears all DAQ lists and frees all dynamically allocated DAQ
    lists, ODTs and ODT entries'. A stimulation slot belongs to the ODT it was allocated for, so it
    is one of the things being freed -- and leaving it behind is worse than leaving a descriptor
    behind, because the next session's first trigger writes it into memory rather than merely
    disagreeing with itself about what is allocated.

    maxOdt is asserted too, so a FREE_DAQ that silently did nothing at all would fail on the half
    that was already working rather than passing this test for the wrong reason."""
    handle = dynamic_stimulation_handle()

    assert response(handle, (0xD6,))[0] == 0xFF, 'FREE_DAQ'

    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 0, 'FREE_DAQ released the lists'
    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlot[0].length == 0, \
        'and the stimulation slot that was allocated with them'


def test_disconnect_clears_a_stored_stimulation_payload():
    """XCP part 1 - Overview 1.0/2.3: in DISCONNECTED state 'all DAQ lists ... are reset'.
    Xcp_CTOCmdStdDisconnect (source/Xcp_Std.c) reaches that through the same Xcp_DaqFreeAll, so a
    master that simply stops talking -- rather than politely running FREE_DAQ first -- must not
    leave a payload behind for whoever connects next."""
    handle = dynamic_stimulation_handle()

    assert response(handle, (0xFE,))[0] == 0xFF, 'DISCONNECT'

    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlot[0].length == 0


def test_re_initialising_the_module_clears_a_stored_stimulation_payload():
    """The third door into the same unwind, and the only one that reaches a STATIC pool: Xcp_Init
    calls Xcp_DaqFreeAll to establish the start-up invariant, exactly as it resets the DTO ring's
    indices two lines later.

    The pool is a generated static with no initialiser of its own, so it is zero at load and this
    is the ONLY thing standing between one session's stimulation data and the next one's -- the
    same sentence free_daq_test.py's own re-initialisation test makes about the descriptor arrays.
    A STATIC configuration cannot enable FREE_DAQ and its DISCONNECT does not unwind, so without
    this test the static half of the fix would be unexercised."""
    config = one_stimulation_list()
    handle = XcpTest(config)
    connect(handle)
    running_stim_list(handle)
    deliver(handle, (0x00,) + PAYLOAD, config.default_daq_dto_pdu_mapping)
    assert_payload_is_stored(handle)

    handle.lib.Xcp_Init(handle.ffi.cast('const Xcp_Type *', handle.config.lib.Xcp))

    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlot[0].length == 0


def test_a_daq_only_build_takes_no_exclusive_area_to_release_slots_it_never_reserved():
    """The guard half of the fix. stimSlotCount is 0 exactly when stimSlot is NULL_PTR
    (interface/Xcp_Types.h), so the release loop must run zero times rather than dereference the
    null pointer or take an area for a pool that does not exist.

    Counted rather than merely 'did not crash': the harness's exclusive-area bookkeeping would
    catch an unbalanced area but not a balanced one taken pointlessly, and 'a DAQ-only build pays
    nothing for stimulation' is a stated constraint of this sub-project, not just a nicety.
    Xcp_Init has already run one full Xcp_DaqFreeAll by the time the mock is inspected."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ', max_odt=2, max_odt_entries=2),)))

    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 0, 'the premise'
    assert handle.sch_m_enter_xcp_stim_buffer.call_count == 0, \
        'a build with no stimulation pool must not enter the stimulation area at all'

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


def resumed_handle():
    """One list restored, committed, and running -- the state every test below starts from."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    # Xcp_ResumeComplete queues EV_RESUME_MODE (source/Xcp_Daq.c) but drives no transmission of
    # its own -- ongoing_transmit_type is still NONE here, exactly as it is after Xcp_MainFunction's
    # own EV_STORE_DAQ push, whose shape it copies. Left queued, a later connect()'s single
    # confirmation would chain Xcp_StartNextTransmission onto it (the D16 pattern test/
    # set_request_test.py's own EV_STORE_CAL case documents and explicitly drains), transmitting it
    # unconfirmed and leaving every CTO response after it stuck behind it -- not lost, since
    # Xcp_CanIfRxIndication still fills cto_response.pdu_info, but never handed to CanIf_Transmit,
    # so a test reading can_if_transmit.call_args would see this stale event's own buffer, or
    # coincidentally alias into whatever later overwrote it. Draining it once, here, is what "the
    # state every test below starts from" (this function's own docstring) has to mean: no test
    # below is about this event, or expects it still in flight when a CONNECT arrives.
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    return handle


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


def test_the_setters_are_refused_once_resume_complete_has_run():
    """DD107's other half. Every setter carries two independent guards --
    `resume_state != XCP_RESUME_ACTIVE` and `connection_status == DISCONNECTED` --
    and test_the_setters_are_refused_once_a_master_has_connected above pins the second by calling
    CONNECT. No CONNECT appears anywhere in this test: connection_status stays DISCONNECTED
    throughout, so a refusal here cannot come from that guard and can only come from resume_state,
    which Xcp_ResumeComplete alone ever advances to XCP_RESUME_ACTIVE. Without this test, deleting
    the resume_state clause from every setter would leave the whole suite green, since every other
    refusal test reaches XCP_RESUME_ACTIVE only via a path that also satisfies the connection
    guard or never reaches it at all."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

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


def test_resuming_two_lists_does_not_collide_their_absolute_odt_numbers():
    """Task 1 review finding, fixed before this task's review: Xcp_RestoreOdtCount raised maxOdt
    without recomputing FIRST_PID the way ALLOC_ODT does (Xcp_DaqRecomputeFirstPids, source/
    Xcp_Daq.c). Under the default ABSOLUTE identification field type (1.1/1.1.2.1), FIRST_PID is
    the prefix sum of every list's own ODT count, so restoring two lists that each get an ODT --
    with nothing recomputing that sum -- leaves both lists' FIRST_PID at the 0 Xcp_Init/
    Xcp_DaqFreeAll set it to, and both lists' ODT 0 transmit identified as absolute ODT number 0:
    a real collision on the wire, not a stale reported value. Every earlier test in this file
    restores exactly one list, which is why none of them caught it.

    Asserted on the two transmitted frames' own identification byte -- where the collision would
    actually show up -- rather than on firstPid directly, which Xcp_Internal and the generated DAQ
    list array are not reachable from the CFFI harness (test/conftest.py builds its cdef from
    interface/Xcp.h alone)."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(2)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtCount(1, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(1, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreOdtEntry(1, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    handle.lib.Xcp_RestoreDaqListMode(1, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 1, 'the trigger starts the chain itself'

    # Every DAQ transmission is handed the same static PduInfoType (Xcp_DaqTxPduInfo, source/
    # Xcp_DaqRuntime.c's Xcp_DaqQueuePeek), so each frame's content has to be read out before the
    # confirmation that arms the next one overwrites it -- the same pattern test/
    # daq_transmission_test.py's own test_a_full_ring_drops_the_frame_and_reports_one_overload_
    # event uses. The DAQ queue transmits one frame at a time (SWS_Xcp_00859); confirming one is
    # what lets Xcp_StartNextTransmission (source/Xcp.c) pick up the next, unaided.
    pids = []
    for _ in range(2):
        pids.append(tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:1]))
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert pids[0] != pids[1], 'two lists, each with one ODT, must not share an absolute ODT number'


def test_a_resumed_lists_odt_survives_a_disconnect():
    """DD106 (docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md): Xcp_DisconnectSession
    frees every dynamic list under DAQ_DYNAMIC, which would let a master's mere DISCONNECT kill a
    measurement Xcp_ResumeComplete restored from non-volatile memory before that master ever
    connected.

    This is the positive half only, deliberately. A fixture that also tries to prove the session's
    own lists ARE freed -- list 0 resumed, list 1 ALLOC_DAQ'd by the connecting master -- cannot show
    that through Xcp_GetDaqListOdtCount(1) unless something gives list 1 an ODT first: without one,
    that count reads 0 before the disconnect as well as after, and the assertion cannot tell "freed"
    from "never had one". Giving list 1 an ODT through the protocol runs into ALLOC_ODT's own
    sequencing (it wants a FREE_DAQ before a second allocation round), and FREE_DAQ frees the
    resumed list right along with it (Xcp_DTOCmdDaqFreeDaq, source/Xcp_Daq.c, frees unconditionally
    by design -- see that function's own comment). So this test asserts survival alone, on a count
    that is non-zero before the disconnect too, which is what gives the assertion something to lose.

    The discriminating negative -- that DISCONNECT still frees a list belonging to the session that
    is ending -- already exists in the suite:
    test/free_daq_test.py::test_disconnect_frees_the_allocation_so_the_next_session_does_not_inherit_it
    allocates real ODTs directly into the descriptor, with no resumed list anywhere in its fixture,
    and asserts they are gone after DISCONNECT. An implementation that spared every list, resumed or
    not, would pass this test and fail that one."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 1, 'non-zero before the disconnect too'

    connect(handle)

    # DISCONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 1, 'the resumed list survives the disconnect'


def test_free_daq_clears_resume_state_so_a_setter_is_accepted_again():
    """FREE_DAQ's own counterpart to DD106
    (docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md), which is about DISCONNECT alone.
    Xcp_DTOCmdDaqFreeDaq (source/Xcp_Daq.c) keeps calling Xcp_DaqFreeAll unconditionally -- an
    explicit FREE_DAQ frees a resumed list along with every other one, unlike DISCONNECT's implicit,
    resume-sparing teardown above, and correctly so: a master that explicitly asks to free
    everything is owed exactly that.

    But that leaves Xcp_Internal.resume_state at XCP_RESUME_ACTIVE with no resumed configuration
    left for it to describe, and DD107 refuses every Xcp_Restore* setter for as long as it stays
    there -- a slave that just freed its resumed pool would go on refusing to have a new one
    restored into it. resume_state is not reachable from the CFFI harness (source/Xcp_Internal.h is
    outside interface/Xcp.h's cdef, test/conftest.py), so this is observed the only way DD107 itself
    is observable: through a setter, refused while resume_state == XCP_RESUME_ACTIVE and accepted
    again once it is not. The DISCONNECT after FREE_DAQ clears the setters' other, independent guard
    -- connection_status == DISCONNECTED -- so a refusal here cannot be attributed to that one."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    # Drains the EV_RESUME_MODE that commit just queued, exactly as resumed_handle() above does
    # and for the same reason: left queued, connect()'s own confirmation chains a transmission for
    # it that nothing here would confirm, and FREE_DAQ's response ends up the one stuck unconfirmed
    # behind it -- which busy-gates DISCONNECT below (DD29: 0xD6 carries CMD_BUSY) before its
    # handler ever runs, so connection_status never reaches DISCONNECTED and the setter at the
    # bottom fails on that guard instead of the one this test is about.
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    connect(handle)

    # FREE_DAQ
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD6,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # DISCONNECT, so only the resume_state guard stands between the setter and E_OK.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_RestoreDaqListCount(1) == handle.define('E_OK'), \
        'resume_state must not still be XCP_RESUME_ACTIVE here'


def test_a_resumed_slave_transmits_with_no_connect_ever_sent():
    """The acceptance bar. 1.1/1.6.4.1.1.4: "the slave being in RESUME mode started the DAQ list
    automatically". Autonomous transmission IS the feature; no other test in this repository
    transmits without a session, so this one cannot pass by inheriting a fixture's habits."""
    handle = resumed_handle()
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.called, 'a resumed list transmits with no master session'


def test_resume_complete_raises_ev_resume_mode():
    """1.1/1.8.1: "With EV_RESUME_MODE the slave indicates that it is starting in RESUME mode."
    Code 0x00 (Xcp_Internal.h, not reachable via handle.define -- the literal is used with this
    comment, as test/set_request_test.py does for its own event codes)."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    handle.can_if_transmit.reset_mock()

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')
    handle.lib.Xcp_MainFunction()

    frames = [c for c in handle.can_if_transmit.call_args_list
              if tuple(c[0][1].SduDataPtr[0:2]) == (0xFD, 0x00)]  # XCP_PID_EVENT, EV_RESUME_MODE
    assert len(frames) == 1, 'exactly one EV_RESUME_MODE'


def test_resume_complete_reports_a_full_event_queue():
    """The failure branch EV_RESUME_MODE's own push takes (Xcp_ResumeComplete, source/Xcp_Daq.c)
    matches Xcp_MainFunction's own EV_STORE_DAQ push (source/Xcp.c), not EV_CMD_PENDING's
    (source/Xcp_Pgm.c): EV_RESUME_MODE is one-shot, with no later retry to fall back on the way
    EV_CMD_PENDING's own busy poll does, so a dropped push is worth a diagnostic rather than a
    silent loss.

    test/set_request_test.py::test_an_unconfirmed_event_still_occupies_its_slot_so_a_new_push_can_fail
    spells out the mechanism this reuses: the ring keeps one slot empty to tell full from empty, so
    an event_queue_size of 2 leaves exactly one usable slot, and a push that finds it already
    occupied fails outright, with no need for any transmission or confirmation to be involved at
    all -- occupancy is set the moment a push succeeds (Xcp_EventQueuePush's own write index moves)
    and only released by Xcp_EventQueuePop in a confirmation, neither of which this test ever
    triggers. Xcp_ResumeComplete carries no guard against being called twice -- nothing in this
    task asks for one -- so the second call's own DAQ list re-validation succeeds identically to
    the first (nothing about the restored list changed), and only its own EV_RESUME_MODE push finds
    the queue full."""
    handle = restoring_handle(event_queue_size=2)
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK'), \
        'the DAQ list itself is still configured, so the second call succeeds too'

    full_errors = [c for c in handle.det_report_error.call_args_list
                   if c[0][3] == handle.define('XCP_E_EVENT_QUEUE_FULL')]
    assert len(full_errors) == 1


def test_get_status_reports_resume_and_the_restored_id():
    """1.1/1.6.1.1.3: session status bit 7 RESUME, "1 = Slave is in RESUME mode", and bit 6
    DAQ_RUNNING, which follows from the restored list actually running. The id comes from
    Xcp_ResumeComplete, so 0x1234 rather than the 0x0000 Xcp_Init leaves -- a value that cannot
    coincide with the default."""
    handle = resumed_handle()
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:6])

    assert response[0] == 0xFF
    assert response[1] & 0b10000000 != 0x00, 'session status RESUME, bit 7'
    assert response[1] & 0b01000000 != 0x00, 'session status DAQ_RUNNING, bit 6'
    assert response[4:6] == (0x34, 0x12), 'the restored session configuration id'


def test_get_status_after_a_second_connect_still_reports_resume():
    """DD77's own reasoning, extended to bit 7: Xcp_CTOCmdStdConnect (source/Xcp_Std.c) clears
    STORE_CAL_REQ/STORE_DAQ_REQ/CLEAR_DAQ_REQ with an explicit mask rather than zeroing
    session_status, precisely so DAQ_RUNNING survives a reconnect. XCP_SESSION_STATUS_MASK_RESUME
    stays out of that mask for the identical reason -- a master reconnecting to a resumed slave is
    still talking to a resumed slave -- and this is the test that would fail if a future edit
    folded RESUME into the mask alongside the three request bits."""
    handle = resumed_handle()
    connect(handle)

    connect(handle)  # a second CONNECT; nothing about DD77's mask is specific to the first one.

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert response[0] == 0xFF
    assert response[1] & 0b10000000 != 0x00, 'session status RESUME must survive a second CONNECT'


def test_get_daq_list_mode_reports_resume_and_running_for_a_restored_list():
    """1.1/1.6.4.1.1.4: mode bit 7 RESUME, "this DAQ list is part of a configuration used in RESUME
    mode", and bit 6 RUNNING. Both in the GET_DAQ_LIST_MODE response layout, which is the layout
    Xcp_DaqListRtType::mode already stores."""
    handle = resumed_handle()
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDF, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert response[0] == 0xFF, 'an error response would satisfy the bit tests below'
    assert response[1] & 0b10000000 != 0x00, 'RESUME, bit 7'
    assert response[1] & 0b01000000 != 0x00, 'RUNNING, bit 6'

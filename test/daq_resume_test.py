#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-RESUME (design doc DD103-DD107, docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md).

The Xcp_Restore* setters are the mirror of SP5-NV's four accessors: the integrator pushes back what
it stored, and Xcp_ResumeComplete is the only thing that makes any of it live (DD105).

Task 4 extends this file: Xcp_GetResumeArmedState (DD104), the fifth accessor, queried during a
live SET_REQUEST-driven store rather than during restoration, so its own tests connect a master
instead of building a restoring_handle(); and the final-verification check that a CONNECT during
RESUME does not stop the lists, folded into
test_get_status_after_a_second_connect_still_reports_resume below rather than added as a separate
test, since that test already connects twice for an unrelated reason and the two checks share one
fixture. RESUME_SUPPORTED going from clear to set in GET_DAQ_PROCESSOR_INFO (1.1/1.6.4.1.2.4) is
Task 4's other half; test/daq_nv_storage_test.py and test/get_daq_processor_info_test.py carry that
side, not this file, since it is not a Xcp_Restore*/Xcp_ResumeComplete behaviour."""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect
from .daq_nv_storage_test import exchange


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
    """The acceptance bar. 1.1/1.6.4.1.2.6: "the slave being in RESUME mode started the DAQ list
    automatically". Autonomous transmission IS the feature; no other test in this repository
    transmits without a session, so this one cannot pass by inheriting a fixture's habits."""
    handle = resumed_handle()
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.called, 'a resumed list transmits with no master session'


def test_a_resumed_slave_refuses_commands_with_no_connect_ever_sent():
    """DD105's correction (docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md,
    .superpowers/sdd/2026-09-10-xcp-daq-resume/task-6-brief.md): Xcp_ResumeComplete used to enter
    XCP_CONNECTION_STATE_RESUME, and both connection gates (source/Xcp.c) test
    != XCP_CONNECTION_STATE_DISCONNECTED rather than == XCP_CONNECTION_STATE_CONNECTED -- so that
    one write alone admitted the entire command set, DOWNLOAD/SET_MTA/FREE_DAQ/the programming
    commands included, to any node on the bus with no CONNECT ever received. The write is gone;
    this pins the property it was hiding, not just the absence of the line -- a command must still
    be refused after a resume with no CONNECT anywhere in the test.

    GET_STATUS: harmless and unambiguous. Read-only, no side effect if wrongly accepted, and
    test_get_status_reports_resume_and_the_restored_id above proves this exact fixture answers it
    once CONNECT precedes it -- so a silent CanIf_Transmit here can only be the connection gate,
    not the command being disabled or out of range. Asserted on CanIf_Transmit, not on
    connection_status, which the CFFI harness cannot reach (test/conftest.py builds its cdef from
    interface/Xcp.h alone): a refused command produces no response at all, so there is nothing
    else to read the refusal off of."""
    handle = resumed_handle()
    handle.can_if_transmit.reset_mock()

    # GET_STATUS. No CONNECT anywhere in this test.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()

    assert not handle.can_if_transmit.called, 'no CONNECT was ever sent; GET_STATUS must be refused'


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

    Final review F2 finding: this test used to reach a full queue by calling Xcp_ResumeComplete
    TWICE with event_queue_size=2, relying on the docstring's own now-false premise that "nothing
    in this task asks for" a guard against a second call -- F2 added exactly that guard (DD107's
    two-clause gate, the same one every Xcp_Restore* setter already carried), so a second call is
    now refused outright before it would ever reach its own push, on a state this test cannot
    manufacture without one (only a successful Xcp_ResumeComplete ever reaches
    XCP_RESUME_ACTIVE). event_queue_size=1 reaches the same push failure on the FIRST and ONLY
    call instead: Xcp_EventQueuePush's ring keeps one slot empty to tell full from empty
    (test/set_request_test.py::test_an_unconfirmed_event_still_occupies_its_slot_so_a_new_push_can_
    fail spells out the same rule against a queue with something already in flight), so a size of 1
    leaves zero usable slots and even a completely fresh queue's first push fails outright."""
    handle = restoring_handle(event_queue_size=1)
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK'), \
        'the DAQ commit itself is unaffected by a queue that cannot also hold the event'

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
    folded RESUME into the mask alongside the three request bits.

    Final verification (task-4-brief.md): "a CONNECT during RESUME does not stop the lists" --
    asserted here, not assumed, because nothing in Tasks 1-4 touches CONNECT at all (design doc
    Section 3, docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md: "CONNECT. It does not
    touch DAQ state today and does not need to."). The session-status bit above proves the slave
    still REPORTS resumed; it does not by itself prove the list is still RUNNING, since that report
    and the list's own mode byte are different storage (source/Xcp_Daq.c's
    Xcp_DaqSessionStatusUpdate recomputes DAQ_RUNNING from list state, but nothing recomputes
    RESUME the same way). So the block below drives an actual transmission through two CONNECTs,
    the same check test_a_resumed_slave_transmits_with_no_connect_ever_sent makes with zero
    CONNECTs -- together the two prove CONNECT is simply irrelevant to whether a resumed list
    transmits, rather than merely untested."""
    handle = resumed_handle()
    connect(handle)

    connect(handle)  # a second CONNECT; nothing about DD77's mask is specific to the first one.

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert response[0] == 0xFF
    assert response[1] & 0b10000000 != 0x00, 'session status RESUME must survive a second CONNECT'

    # Confirm GET_STATUS's own response first: Xcp_CanIfTxConfirmation unconditionally chains
    # Xcp_StartNextTransmission (test/set_request_test.py's own EV_STORE_CAL case documents this),
    # so leaving it unconfirmed would hold the transmission slot and make the trigger below look
    # like it did nothing -- for a reason that has nothing to do with CONNECT.
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.called, 'the resumed list is still running, and transmits, after two CONNECTs'


def test_get_daq_list_mode_reports_resume_and_running_for_a_restored_list():
    """1.1/1.6.4.1.2.6: mode bit 7 RESUME, "this DAQ list is part of a configuration used in RESUME
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


def test_the_armed_state_follows_the_store_mode_bit_that_asked_for_it():
    """DD104. 1.1/1.6.1.2.3: STORE_DAQ_REQ_RESUME (mode bit 2) "implicitly sets the slave into
    RESUME mode", STORE_DAQ_REQ_NO_RESUME (bit 1) "does not". The module keeps no non-volatile
    memory, so the integrator queries this during Xcp_StoreDaqConfiguration and persists it.

    Both bits are exercised in one test so the accessor cannot pass by returning a constant. This
    is the one test in this file that connects a master and drives SET_REQUEST rather than calling
    Xcp_Restore*/Xcp_ResumeComplete directly: the armed flag belongs to the STORE side DD94 already
    built, not to the restore side this file otherwise covers (see this file's own module
    docstring)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True))
    connect(handle)
    seen = []

    def store_daq_configuration(session_configuration_id, p_status_code):
        seen.append(handle.lib.Xcp_GetResumeArmedState())
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000010, 0x00, 0x00))   # NO_RESUME
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    exchange(handle, (0xF9, 0b00000100, 0x00, 0x00))   # RESUME
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert seen == [0, 1], 'FALSE for the NO_RESUME store, TRUE for the RESUME store'


def test_resume_supported_is_advertised():
    """1.1/1.6.4.1.2.4, DAQ_PROPERTIES bit 2: "1 = DAQ lists can be set to RESUME mode." Now true,
    and this is the assertion that keeps the SET_REQUEST bit 2 acceptance
    (test_the_armed_state_follows_the_store_mode_bit_that_asked_for_it above, and
    Xcp_DTOCmdStdSetRequest's own accepted_request_mask, source/Xcp_Std.c) honest -- a master could
    otherwise be told a store armed a mode GET_DAQ_PROCESSOR_INFO denies the slave offers."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDA,)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert response[0] == 0xFF
    assert response[1] & 0b00000100 != 0x00, 'DAQ_PROPERTIES RESUME_SUPPORTED, bit 2'


# Final whole-branch review, F1 (Critical): Xcp_RestoreOdtEntry copied address/bitOffset/
# addressExtension/length verbatim, applying none of the four rules WRITE_DAQ enforces through
# Xcp_DaqApplyOdtEntry (source/Xcp_Daq.c) -- size != 0, size <= odtEntrySizeDaq, size a multiple of
# the address granularity, and the per-ODT budget. Xcp_DaqSampleOdt (source/Xcp_DaqRuntime.c)
# trusts that invariant absolutely: it writes pFrame->data[offset] with no bound of its own, and
# pFrame is an 8-byte (default MAX_DTO) stack local in a function documented callable from an
# interrupt. The two tests below pin the fix at both sites the review asked for -- the setter's own
# per-call check, and Xcp_ResumeComplete's whole-of-restoration re-check -- because the second is
# the one the setter alone cannot catch.

def test_restore_odt_entry_refuses_what_write_daq_would_refuse():
    """F1, the setter's own site. MAX_ODT_ENTRY_SIZE_DAQ is MAX_DTO - 1 = 7 for the default
    ABSOLUTE/MAX_DTO=8 build write_daq_test.py's own test_write_daq_rejects_a_size_outside_the_odt_
    entry_limits pins for WRITE_DAQ. The boundary is checked both sides, the sharpest case for a
    </<= mistake: 7 must stay accepted (a fix that refused it would make an honest configuration
    unrestorable) and 8 -- the length the review's own failure scenario names, extended to a value
    that still fits inside a uint8 -- must not."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)

    assert handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle, length=7)) == handle.define('E_OK'), \
        'MAX_ODT_ENTRY_SIZE_DAQ itself must stay legal'
    assert handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle, length=8)) == handle.define('E_NOT_OK'), \
        'one byte past MAX_ODT_ENTRY_SIZE_DAQ -- WRITE_DAQ answers ERR_OUT_OF_RANGE for this size'


def test_restore_odt_entry_accepts_length_zero_as_the_unwritten_marker():
    """F1's own carve-out. Xcp_GetOdtEntry reports an unwritten entry with length 0 (and bitOffset
    XCP_ODT_ENTRY_BIT_OFFSET_NONE, the entry() helper's own default), and the restore-side mirror
    must accept exactly what the accessor gave it -- folding length into the same size != 0 rule
    WRITE_DAQ applies to a master's own request would make a faithful round trip of an unwritten
    entry impossible."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)

    assert handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle, length=0)) == handle.define('E_OK')


def test_resume_complete_refuses_an_odts_total_exceeding_its_budget():
    """F1, the site the setter alone cannot catch, and the single most important test in this
    wave. Both entries below are individually legal against ODT 0's FULL budget (7 bytes) at the
    moment Xcp_RestoreOdtEntry accepts them -- TIMESTAMP is not yet on the list, so
    Xcp_DaqOdtEntryBudget has not shrunk it. Only once Xcp_RestoreDaqListMode restores TIMESTAMP
    afterwards does the budget fall to 3 (7 minus the DWORD timestamp's 4 bytes, XCP part 2 -
    Protocol Layer Specification 1.1/1.1.2.2 Diagram 10), leaving the ODT's already-restored total
    of 4 bytes over it. Xcp_RestoreOdtEntry cannot revisit a decision it already made;
    Xcp_ResumeComplete is the one place that re-derives the budget from the list's FINAL mode,
    order-independently, immediately before anything becomes live (DD105)."""
    handle = restoring_handle(timestamp=timestamp(size='DWORD'))
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 2)
    assert handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle, length=2)) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntry(0, 0, 1, entry(handle, length=2)) == handle.define('E_OK')
    # XCP_DAQ_LIST_MODE_TIMESTAMP, GET_DAQ_LIST_MODE layout (1.1/1.6.4.1.2.6), bit 4 -- accepted on
    # its own terms (F4's clock check below asks only that a clock be configured, which it is).
    assert handle.lib.Xcp_RestoreDaqListMode(0, 0x10, 0, 1, 0) == handle.define('E_OK')

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_NOT_OK')


# Final whole-branch review, F2 (Important): Xcp_ResumeComplete carried neither of DD107's two
# guards, though every Xcp_Restore* setter above carries both (test_the_setters_are_refused_once_a_
# master_has_connected and test_the_setters_are_refused_once_resume_complete_has_run pin them for
# the setters). Tested separately here for the identical reason those two tests are separate: one
# guard can mask the other.

def test_resume_complete_refuses_once_a_master_has_connected():
    """F2, the connection_status half. resume_state is still XCP_RESUME_RESTORING here, not
    XCP_RESUME_ACTIVE -- only a prior SUCCESSFUL Xcp_ResumeComplete ever advances it, and this is
    the first call -- so a refusal below can only come from connection_status, isolating this
    clause from its sibling."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)

    connect(handle)

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_NOT_OK')


def test_resume_complete_refuses_once_it_has_already_run():
    """F2's other half. DISCONNECT genuinely returns connection_status to DISCONNECTED, while
    resume_state stays XCP_RESUME_ACTIVE throughout -- Xcp_DaqFreeSessionAllocated spares a
    RESUME-marked list from the teardown itself (DD106,
    test_a_resumed_lists_odt_survives_a_disconnect above), and only Xcp_DTOCmdDaqFreeDaq ever
    clears resume_state, which this test never sends. So a second Xcp_ResumeComplete call below is
    refused for connection_status being genuinely DISCONNECTED again -- a refusal here can only
    come from resume_state, isolating it from its sibling the same way test_the_setters_are_
    refused_once_resume_complete_has_run does for the setters."""
    handle = resumed_handle()
    connect(handle)

    # DISCONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_ResumeComplete(0x5678) == handle.define('E_NOT_OK')


def test_resume_complete_refuses_an_empty_commit():
    """F3 (Important). With allocated_daq_count == 0 the validation loop never runs, so this used
    to return E_OK unconditionally -- entering RESUME mode, refusing every future Xcp_Restore*
    (DD107, once resume_state reaches XCP_RESUME_ACTIVE), and opening the CTO dispatch with no
    CONNECT ever received, all for a slave transmitting nothing. DD105 already answers this the
    way START_STOP_SYNCH answers ERR_DAQ_CONFIG for starting an empty selection: refuse it. No
    Xcp_Restore* call of any kind precedes this call -- allocated_daq_count is 0 from Xcp_Init
    alone."""
    handle = restoring_handle()

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_NOT_OK')


# Final whole-branch review, F4 (Important): Xcp_RestoreDaqListMode applied none of SET_DAQ_LIST_
# MODE's own validation (Xcp_DTOCmdDaqSetDaqListMode, source/Xcp_Daq.c), so the back door could
# grant a mode the front door never would -- DD105's principle applied to the mode rather than the
# entries. Two of the three silent consequences the review named are pinned below; a list restored
# with the third (PID_OFF shared between two lists on one RX PDU) needs a stim-capable pool this
# file's DAQ-only restoring_handle() does not build, so it is left to this fix's code review rather
# than a dedicated test here.

def test_restore_daq_list_mode_refuses_an_out_of_range_event_channel():
    """F4. Xcp_DTOCmdDaqSetDaqListMode answers ERR_OUT_OF_RANGE for eventChannelNumber >=
    maxEventChannel (1.1/1.6.4.1.1.3); granted here instead, the list would be bound to a channel
    that can never elapse, reported RUNNING|RESUME by Xcp_ResumeComplete while transmitting
    nothing, forever. dynamic_config's single default event (EVT1) leaves maxEventChannel at 1, so
    channel 1 is the first invalid one and channel 0 the boundary a fix must not also refuse."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)

    assert handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 1, 1, 0) == handle.define('E_NOT_OK')
    assert handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0) == handle.define('E_OK'), \
        'channel 0 is the boundary this refusal must not also catch'


def test_restore_daq_list_mode_refuses_direction_on_a_daq_only_list():
    """F4's most concrete named consequence. Xcp_DTOCmdDaqSetDaqListMode refuses DIRECTION
    (stimulation) on a list whose configured type cannot receive (1.1/1.6.4.1.1.3); granted here
    instead, both of Xcp_TriggerEventChannel's passes skip the list on its type test
    (source/Xcp_DaqRuntime.c), so it would report RUNNING|RESUME and transmit nothing, forever.
    restoring_handle's pool is type DAQ throughout (dynamic_config's own default), so DIRECTION
    (bit 1, GET_DAQ_LIST_MODE layout) is never grantable here."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)

    assert handle.lib.Xcp_RestoreDaqListMode(0, 0x02, 0, 1, 0) == handle.define('E_NOT_OK')


# Task 5 (.superpowers/sdd/2026-09-10-xcp-daq-resume/task-5-brief.md), added after the final
# whole-branch review: the read side DD103 promised and never delivered. Xcp_RestoreDaqListMode's
# own doc comment (interface/Xcp.h) used to say so outright -- mode, event channel, prescaler and
# priority had no accessor, so an integrator's Xcp_StoreDaqConfiguration could query a list's
# selection, ODT count, entry counts and entries, but not the one field (the event channel) that
# decides whether a restored list ever fires. Xcp_GetDaqListMode (source/Xcp_Daq.c) closes the gap;
# the three tests below are its coverage, in the shape the brief itself lays out.

def test_get_daq_list_mode_reports_what_set_daq_list_mode_wrote():
    """Task 5, test 1: the round trip through the real command. The list is bound with
    SET_DAQ_LIST_MODE, not by calling Xcp_RestoreDaqListMode -- seeding the state a broken
    Xcp_GetDaqListMode reads back through the restore setter would let a broken accessor agree
    with a broken setter. mode=2 (DIRECTION), channel=1, prescaler=5 and priority=0 are four
    pairwise distinct numbers, and three of the four differ from their own power-up default
    (0, 0, 1): the fourth, priority, cannot -- SET_DAQ_LIST_MODE refuses any nonzero priority by
    specification (1.1/1.6.4.1.1.3), exactly as test/get_daq_list_mode_test.py's own
    test_get_daq_list_mode_reports_priority notes for GET_DAQ_LIST_MODE itself, so a round trip
    through the real command cannot exercise that byte either. DIRECTION needs a
    stimulation-capable list, hence stim_config rather than dynamic_config; a second event channel
    exists so channel 1 -- the field DD103's own gap was about -- is reachable at all."""
    handle = XcpTest(stim_config(daq_count=1, odt_count=1, odt_entries_count=1,
                                  events=(event(name='EVT1'), event(name='EVT2'))))
    connect(handle)
    exchange(handle, (0xD6,))                                   # FREE_DAQ
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))                  # ALLOC_DAQ(1)
    # SET_DAQ_LIST_MODE(DIRECTION, list 0, channel 1, prescaler 5, priority 0).
    assert exchange(handle, (0xE0, 0x02, 0x00, 0x00, 0x01, 0x00, 0x05, 0x00))[0] == 0xFF

    # Seeded with values SET_DAQ_LIST_MODE can never produce here (test/stim_decode_test.py's own
    # idiom for an out parameter a broken callee might leave untouched), so a Xcp_GetDaqListMode
    # that forgets to write one of these fails on the stale seed rather than coincidentally
    # reading back a value that happens to already be correct.
    p_mode = handle.ffi.new('uint8 *', 0xFF)
    p_event_channel_number = handle.ffi.new('uint16 *', 0xFFFF)
    p_prescaler = handle.ffi.new('uint8 *', 0xFF)
    p_priority = handle.ffi.new('uint8 *', 0xFF)
    assert handle.lib.Xcp_GetDaqListMode(0, p_mode, p_event_channel_number, p_prescaler,
                                         p_priority) == handle.define('E_OK')

    assert p_mode[0] == 0x02, 'DIRECTION, the bit the power-up default (0x00) lacks'
    assert p_event_channel_number[0] == 1, 'the non-zero channel SET_DAQ_LIST_MODE bound'
    assert p_prescaler[0] == 5, 'the prescaler above 1'
    assert p_priority[0] == 0, 'the only priority SET_DAQ_LIST_MODE ever grants'


def test_get_daq_list_mode_refuses_a_list_number_at_the_allocated_count():
    """Task 5, test 2: the out-of-range refusal, mirroring Xcp_GetOdtEntry's own bound
    (test/daq_nv_accessor_test.py::test_accessors_refuse_a_list_number_at_or_past_the_allocated_
    count) through the same Xcp_DaqListIsValid, reused rather than re-derived. List 1 is the
    boundary itself -- the allocated count -- not a value far past it, the sharpest case for a
    >=-vs-> mistake."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)

    p_mode = handle.ffi.new('uint8 *')
    p_event_channel_number = handle.ffi.new('uint16 *')
    p_prescaler = handle.ffi.new('uint8 *')
    p_priority = handle.ffi.new('uint8 *')
    assert handle.lib.Xcp_GetDaqListMode(1, p_mode, p_event_channel_number, p_prescaler,
                                         p_priority) == handle.define('E_NOT_OK')


def test_a_list_restored_purely_from_the_accessors_capture_fires_on_the_bound_channel_only():
    """Task 5, test 3: the end-to-end proof, and the one that matters. A test that only triggered
    the channel it originally bound would pass even if Xcp_GetDaqListMode returned a constant,
    because the restore would then bind to the same wrong value the capture returned -- so no
    literal value is asserted on the captured tuple anywhere below (that belongs to
    test_get_daq_list_mode_reports_what_set_daq_list_mode_wrote above). This test instead triggers
    BOTH event channels and lets actual transmission settle it: the non-default channel (1, what
    SET_DAQ_LIST_MODE actually bound) must fire, and the default channel (0, what a
    constant-returning accessor would produce instead) must stay silent.

    The teardown in the middle is deliberate, not decorative: without it, the list the triggers
    below find could coincidentally still be the very list SET_DAQ_LIST_MODE bound moments earlier,
    and the assertions would hold no matter what Xcp_RestoreDaqListMode did with its arguments.
    DISCONNECT frees this session's own dynamic list first (DD106, Xcp_DaqFreeSessionAllocated), so
    the list the triggers later find exists only because Xcp_RestoreDaqListMode and
    Xcp_ResumeComplete rebuilt it from the captured values alone."""
    handle = XcpTest(dynamic_config(daq_count=1, odt_count=1, odt_entries_count=1,
                                     events=(event(name='EVT1'), event(name='EVT2'))))
    connect(handle)

    # Bind list 0 to the NON-DEFAULT channel (1) through the real command -- not through
    # Xcp_RestoreDaqListMode, which would let a broken accessor agree with a broken setter.
    exchange(handle, (0xD6,))                                          # FREE_DAQ
    exchange(handle, (0xD5, 0x00, 0x01, 0x00))                         # ALLOC_DAQ(1)
    exchange(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))                   # ALLOC_ODT(list 0, 1)
    exchange(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))             # ALLOC_ODT_ENTRY(list 0, odt 0, 1)
    exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))             # SET_DAQ_PTR(list 0, odt 0, entry 0)
    assert exchange(handle, (0xE1, 0xFF, 0x01, 0x00) +
                    tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))[0] == 0xFF  # WRITE_DAQ(1 byte)
    # SET_DAQ_LIST_MODE(list 0, event channel 1, prescaler 1, priority 0).
    assert exchange(handle, (0xE0, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00))[0] == 0xFF

    p_mode = handle.ffi.new('uint8 *')
    p_event_channel_number = handle.ffi.new('uint16 *')
    p_prescaler = handle.ffi.new('uint8 *')
    p_priority = handle.ffi.new('uint8 *')
    assert handle.lib.Xcp_GetDaqListMode(0, p_mode, p_event_channel_number, p_prescaler,
                                         p_priority) == handle.define('E_OK')
    captured = (p_mode[0], p_event_channel_number[0], p_prescaler[0], p_priority[0])

    # Tear the configuration down. DISCONNECT frees this session's own (non-RESUME) dynamic list
    # (DD106, Xcp_DaqFreeSessionAllocated), so nothing survives below for the restore to coast on.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 0, 'the session list is gone, not merely stopped'

    # Restore using ONLY the captured values -- nothing below spells out "channel 1" anywhere.
    assert handle.lib.Xcp_RestoreDaqListCount(1) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtCount(0, 1) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle)) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreDaqListMode(0, *captured) == handle.define('E_OK')
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    # Drains the EV_RESUME_MODE the commit just queued, exactly as resumed_handle() above does and
    # for the same reason: left queued, the next confirmation chains a transmission for it that
    # neither trigger below confirms, and it would otherwise sit in can_if_transmit's history and
    # confuse the two reset_mock()/called checks that follow.
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(1)
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.called, \
        'restored from the actual capture: channel 1, what SET_DAQ_LIST_MODE really bound, fires'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()
    assert not handle.can_if_transmit.called, \
        'channel 0 is what a constant-returning accessor would have produced instead, and must stay silent'

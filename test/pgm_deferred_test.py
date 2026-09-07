#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def pgm_handle(**kwargs):
    """A connected slave with the flash-programming gate on.

    The three keys forced False below are PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX -- the three
    Xcp_CTOCmdStdConnect reads for CONNECT's RESOURCE bit 4, none of them implemented before SP4b.
    script/source_cfg.c.jinja2 refuses their combination with `programming.enabled` outright
    (final-review finding 3: the advertisement would be D10 again, one flag away), so this is not a
    preference but the only gate-on configuration that generates at all. Passing them here rather
    than changing DefaultConfig's own defaults keeps the gate-OFF tests -- which still exercise
    those keys, and for which they are harmless -- reading exactly as they did.

    They are also spelled out rather than left to the schema so that SP4b, which will enable them
    for real, finds one place to change."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   programming_enabled=True,
                                   xcp_program_clear_api_enable=False,
                                   xcp_program_api_enable=False,
                                   xcp_program_max_api_enable=False,
                                   **kwargs))
    connect(handle)
    return handle


def program_start(handle):
    """PROGRAM_START, without pumping Xcp_MainFunction -- the point of most tests here is what
    happens across SUBSEQUENT main-function calls, so the request and the polling are separate.

    Xcp_CanIfRxIndication only fills a buffer and sets a pending flag; every helper elsewhere in
    this suite (download_test.connect, clear_daq_list_test.response, pgm_configuration_test.exchange)
    calls Xcp_MainFunction afterward for exactly that reason, and this helper deliberately does not,
    so that a test can pump Xcp_MainFunction itself and count exactly how many polls have happened."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD2,)))


def program_reset(handle):
    """PROGRAM_RESET (Task 4), without pumping Xcp_MainFunction -- mirrors program_start above and
    for the same reason: a test needs to pump Xcp_MainFunction and confirm transmissions itself,
    at its own pace, rather than have this helper do it once and hide how many cycles it took."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xCF,)))


def transmitted(handle):
    """The last frame handed to CanIf, or None if CanIf_Transmit has not been called since the
    marker was placed. Reading call_args directly would return the CONNECT response for a command
    that transmitted nothing, which is exactly the case these tests must distinguish."""
    if handle.can_if_transmit.call_args is None:
        return None
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])


def busy_then(handle, status_code, busy_calls, mock=None):
    """Xcp_ProgramStart returns E_NOT_OK `busy_calls` times, then E_OK with `status_code`.

    Writes 0xEE into pStatusCode on every BUSY call. DD54 says the module must not read that
    parameter while the callback is unfinished, and a poison value is how a test can see a module
    that does -- 0xEE would reach the wire as a bogus ERR_GENERIC.

    `mock` defaults to handle.xcp_program_start; Task 4's own tests pass handle.xcp_program_reset
    instead, since Xcp_ProgramReset(uint8 *pStatusCode) copies the exact same polled contract (spec
    Section 4) and every test below would otherwise have to reimplement this side effect."""
    if mock is None:
        mock = handle.xcp_program_start
    state = dict(calls=0)

    def side_effect(p_status):
        state['calls'] += 1
        if state['calls'] <= busy_calls:
            p_status[0] = 0xEE
            return handle.define('E_NOT_OK')
        p_status[0] = status_code
        return handle.define('E_OK')

    mock.side_effect = side_effect
    return state


def test_program_start_transmits_nothing_while_the_integrator_is_busy():
    """DD53. The response is withheld with *responseExpected = FALSE, the mechanism
    Xcp_DTOCmdCalDownload already uses mid-block-transfer.

    Review fix round 1, finding 1. The previous form of this test asserted
    `transmitted(handle) is None` after `program_start` alone, with no Xcp_MainFunction call --
    but Xcp_CanIfRxIndication never transmits (the only Xcp_StartNextTransmission call sites are
    Xcp_MainFunction's own tail and Xcp_CanIfTxConfirmation's), so that assertion held
    unconditionally, for any handler behaviour whatsoever, and mutation 3 in the report documents
    catching this without repairing it. Pumping one Xcp_MainFunction is what actually exercises
    DD53: the poll is still busy, so no *response* may go out, but DD54's EV_CMD_PENDING on that
    same poll is expected and must be let through -- asserted as 'no CTO frame', PID 0xFF or 0xFE,
    rather than 'no CanIf_Transmit call at all'. A module with *responseExpected = TRUE on the
    deferral branch writes nothing new into cto_response.pdu_info and this handler's caller
    publishes it anyway, so the stale CONNECT response already sitting there (every one of these
    tests calls connect() first) would be transmitted as PROGRAM_START's answer -- exactly what
    this form catches and the previous one could not."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=3)
    handle.can_if_transmit.reset_mock()

    program_start(handle)
    handle.lib.Xcp_MainFunction()

    responses = [call for call in handle.can_if_transmit.call_args_list
                 if call[0][1].SduDataPtr[0] in (0xFF, 0xFE)]
    assert responses == [], 'no response may go out while the callback is unfinished'


def test_the_response_appears_on_the_main_function_where_the_callback_completes():
    """The other half: the response is not merely delayed, it arrives, and on the right cycle.
    Pumping one main function at a time and asserting the transition is what distinguishes a
    working deferral from a module that answers on the next command instead.

    A TxConfirmation for the still-busy poll's EV_CMD_PENDING sits between the two
    Xcp_MainFunction calls: the transmit pipeline carries one frame at a time (SWS_Xcp_00859), so
    without confirming that event first, the eventual positive response would be built correctly
    but stay queued behind it forever, never reaching CanIf_Transmit at all -- a false failure
    that would have nothing to do with the deferral logic under test."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=2)
    handle.can_if_transmit.reset_mock()
    program_start(handle)

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] != 0xFF, 'still busy on the second poll'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the positive response arrives when the callback does'


def test_the_positive_response_reports_the_live_communication_parameters():
    """DD56, as narrowed by DD62. MAX_CTO_PGM, MIN_ST_PGM and QUEUE_SIZE_PGM are still the
    module's ordinary, live values, because this module does not change them in programming mode.

    MAX_BS_PGM (byte 4) is deliberately NOT asserted here any more: DD62 revises DD56 for that one
    field alone, and it is no longer "live" in the sense this test's name means -- it is covered by
    test_max_bs_pgm_reports_the_configured_block_size_not_the_live_max_bs below, which needs a
    configuration where max_bs and max_block_size actually differ to mean anything.

    Pinned against the configuration rather than against literals: 1.1/1.6.5.1.3 makes MAX_BS_PGM
    and MIN_ST_PGM the bound on SP4b's PROGRAM_NEXT block transfer, so a wrong value here becomes
    a wire-visible defect there.

    The Xcp_MainFunction call is the ordinary flush every command needs (Xcp_CanIfRxIndication
    only fills a buffer and never transmits), not a busy poll: busy_calls=0 means the handler
    already built this response synchronously, before Xcp_MainFunction ever runs. Without it, and
    without the reset_mock() before program_start, this test passed anyway by reading connect()'s
    own response back out of the mock -- CONNECT's byte 3 is also maxCto (Xcp_CTOCmdStdConnect,
    Xcp_Std.c), so frame[0] and frame[3] matched a response this exchange never sent."""
    handle = pgm_handle(min_st=3, cto_queue_size=2)
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    frame = transmitted(handle)

    assert frame[0] == 0xFF
    assert frame[3] == handle.lib.Xcp_Ptr.general.maxCto, 'MAX_CTO_PGM'
    assert frame[5] == 3, 'MIN_ST_PGM'
    assert frame[6] == 2, 'QUEUE_SIZE_PGM'


def test_max_bs_pgm_reports_the_configured_block_size_not_the_live_max_bs():
    """DD62, revising DD56. MAX_BS_PGM (byte 4) is programming.max_block_size, read at runtime from
    Xcp_Ptr->general->maxBsPgm (script/source_cfg.c.jinja2) -- not the ordinary protocol_layer.max_bs
    this module reported here before SP4b needed a buffer to size (DD56, as SP4a left it).

    max_bs and max_block_size are configured to DIFFERENT values on purpose: 5 and 12. Equal
    values would pass whether the module answered with the old field or the new one, pinning
    nothing -- exactly the plan's failure mode 5 ('a deferral test discarding the very value it
    meant to check'), one of six ways a test in this sub-project has already passed while proving
    nothing. Asserting 12 and NOT 5 is what actually distinguishes DD62's field from DD56's.

    Does NOT distinguish Xcp_Ptr->general->maxBsPgm (this configuration's own live value) from
    XCP_PGM_MAX_BLOCK_SIZE (the compile-time macro Xcp_Internal.pgm_block is sized from, the
    largest max_block_size across every configuration in the BUILD): with a single configuration
    the two are always numerically equal, which is exactly the trap final-review finding F4 caught
    -- MAX_BS_PGM read the macro here until that fix, and this test could not have told the
    difference either way. test_max_bs_pgm_reports_the_active_configurations_own_value_not_the_
    build_wide_maximum below, the one that needs two configurations, is what actually pins F4."""
    handle = pgm_handle(max_bs=5, programming_max_block_size=12)
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    frame = transmitted(handle)

    assert frame[0] == 0xFF
    assert frame[4] == 12, 'MAX_BS_PGM must be programming.max_block_size (12), not max_bs (5)'


def test_max_bs_pgm_reports_the_active_configurations_own_value_not_the_build_wide_maximum():
    """Final review F4. Xcp_Internal.pgm_block is sized once for a module compiled once for every
    configuration in the build, so XCP_PGM_MAX_BLOCK_SIZE (script/header_cfg.h.jinja2) is
    deliberately the LARGEST programming.max_block_size across all of them -- but DD62, design
    Section 9 criterion 5, and this sub-project's own ledger ruling on the identical
    macro-versus-runtime-field question for maxCto all say MAX_BS_PGM is the value THIS
    configuration declares, not the build-wide bound. Before this fix, PROGRAM_START read the
    compile-time macro directly (source/Xcp_Pgm.c), so a configuration declaring the SMALLER of two
    values in one build advertised the LARGER one instead -- a promise about a block size this
    configuration's own master was never told to expect.

    Two configurations in one generated file, 5 and 200 apart on purpose (matching the file-wide
    convention every other DD62 test here already follows: equal values would pass whether the
    module reported the per-configuration field or the build-wide macro, pinning nothing).
    Configuration 0 (5) is run first: if MAX_BS_PGM still read the macro, this assertion would see
    200, not 5 -- the direction the measured defect actually took, and the one a test that only
    ever ran the build's OWN largest configuration could never catch."""
    handle = XcpTest(MultiConfig(DefaultConfig(programming_enabled=True, programming_max_block_size=5),
                                 DefaultConfig(programming_enabled=True, programming_max_block_size=200)),
                     configuration_index=0)
    connect(handle)
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    frame = transmitted(handle)

    assert frame[0] == 0xFF
    assert frame[4] == 5, \
        "MAX_BS_PGM must be THIS configuration's own max_block_size (5), not the build-wide " \
        'maximum across every configuration (200)'


@pytest.mark.parametrize('master_block_mode, interleaved_mode, slave_block_mode, expected', (
    (True, False, False, 0x01),
    (False, True, False, 0x02),
    (False, False, True, 0x40),
    (True, True, True, 0x43),
))
def test_the_positive_response_reports_comm_mode_pgm(master_block_mode, interleaved_mode,
                                                      slave_block_mode, expected):
    """DD56. COMM_MODE_PGM is built from the same three flags GET_COMM_MODE_INFO's
    COMM_MODE_OPTIONAL reads (Xcp_DTOCmdStdGetCommModeInfo, Xcp_Std.c), at this response's own bit
    positions: masterBlockModeSupported (bit 0), interleavedModeSupported (bit 1) and
    slaveBlockModeSupported (bit 6) -- the third of which COMM_MODE_OPTIONAL has no bit for at all.

    Not asserted by test_the_positive_response_reports_the_live_communication_parameters, which
    pins MAX_CTO_PGM/MAX_BS_PGM/MIN_ST_PGM/QUEUE_SIZE_PGM but never reads byte 2. Swept one flag at
    a time, plus all three together, so each bit is pinned to its own flag rather than to a fixed
    configuration's coincidental combination."""
    handle = pgm_handle(master_block_mode=master_block_mode, interleaved_mode=interleaved_mode,
                        slave_block_mode=slave_block_mode)
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[2] == expected, 'COMM_MODE_PGM'


def test_a_failing_integrator_yields_err_generic_and_leaves_the_session_closed():
    """1.1/1.6.5.1.1 names ERR_GENERIC for a slave 'not in a state which permits programming'.

    pgm_state is not reachable from this CFFI harness: test/conftest.py builds its cdef from
    interface/Xcp.h alone, which does not include Xcp_Internal.h. test/clear_daq_list_test.py:80-92
    documents the same limitation and the same workaround. So the claim that matters -- a module
    that answered correctly but left pgm_state at XCP_PGM_ACTIVE would refuse every later
    PROGRAM_START with ERR_GENERIC, and no wire assertion on THIS exchange alone would notice -- is
    checked by actually sending that later PROGRAM_START and requiring it to be accepted rather
    than answered ERR_GENERIC (0x31)."""
    handle = pgm_handle()
    busy_then(handle, 0x01, busy_calls=1)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'

    # Confirms the ERR_GENERIC response before trying again: the transmit pipeline carries one
    # frame at a time (SWS_Xcp_00859), and an unconfirmed CTO response would leave the second
    # PROGRAM_START's own answer queued behind it forever, never reaching CanIf_Transmit -- a
    # false failure unrelated to whether pgm_state is really back at XCP_PGM_IDLE.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    busy_then(handle, 0x00, busy_calls=0)
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, \
        'pgm_state must be back at XCP_PGM_IDLE, or this second PROGRAM_START would be refused ' \
        'with ERR_GENERIC instead of accepted'


def test_the_status_code_is_not_read_while_the_callback_is_busy():
    """DD54 and §4: pStatusCode is defined only for the E_OK case. The stub poisons it with 0xEE
    on every busy call, so a module that read it early would answer ERR_GENERIC-with-0xEE instead
    of completing successfully.

    Each poll's EV_CMD_PENDING is confirmed before the next: the transmit pipeline carries one
    frame at a time (SWS_Xcp_00859), so leaving a busy poll's event unconfirmed would leave the
    eventual completion response queued behind it forever, never reaching CanIf_Transmit -- the
    same reason test_the_response_appears_on_the_main_function_where_the_callback_completes
    confirms before its own final poll."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=4)
    program_start(handle)
    for _ in range(5):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    assert transmitted(handle)[0] == 0xFF, 'the poison value must not have been read'


def test_an_instantaneous_integrator_is_answered_without_deferring():
    """Spec §4. The first call to Xcp_ProgramStart happens in the handler, so an integrator that
    finishes immediately is answered on the very first ordinary flush -- no pending slot, no
    busy-poll cycle, and no EV_CMD_PENDING for an operation that never waited. One
    Xcp_MainFunction call is still needed to reach CanIf_Transmit at all, exactly as it is for
    every other command in this suite (download_test.connect, clear_daq_list_test.response): what
    this test pins is that ONE ordinary flush is enough, never the busy-poll cycle a deferred
    PROGRAM_START needs several of before its response appears.

    Review fix round 1, finding 3. The wire-level assertions below (0xFF on the first flush, no
    EV_CMD_PENDING, nothing left pending) all still pass for a handler mutated to defer
    unconditionally -- set pending_command, *responseExpected = FALSE, no fast path -- because
    with busy_calls=0 the very first Xcp_MainFunction poll immediately calls back into
    Xcp_ProgramStart, which returns E_OK on ITS first call too, so the response still arrives on
    the first Xcp_MainFunction and the slot still gets released. None of that distinguishes
    'answered in the handler' from 'deferred once, resolved on the very next poll'. What does is a
    count on the mock itself, which needs no Xcp_Internal reachability: the handler call and the
    completing poll are the same call if and only if the fast path ran."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD2,)))
    assert handle.xcp_program_start.call_count == 1, 'the first call happens in the handler'

    handle.lib.Xcp_MainFunction()
    assert handle.xcp_program_start.call_count == 1, 'and the completed command is not polled again'

    assert transmitted(handle)[0] == 0xFF, 'answered on the first ordinary flush'

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]
    assert events == [], 'an operation that never waited must not ask the master to wait'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args is None, \
        'nothing was left pending to complete a second time'


def test_at_most_one_ev_cmd_pending_is_outstanding():
    """DD54. Xcp_MainFunction is aperiodic -- cyclic per SWS_Xcp_00824, but the module may never
    depend on its period -- so EV_CMD_PENDING cannot be timed. Bounding it to one in flight makes
    the rate follow TxConfirmation instead, which SWS_Xcp_00859 already forces the module to wait
    for.

    Ten busy polls with no confirmation in between must produce exactly one event. A module that
    pushed one per poll would emit ten, which is the defect: on a fast bus that is a flood, and on
    any bus it is a rate derived from a period the module is not allowed to assume.

    The second half below is the part that actually pins a missing event_outstanding guard: the
    transmit pipeline carries one frame at a time (SWS_Xcp_00859), so a module that pushed on every
    busy poll would still show only one CanIf_Transmit call here -- the other nine would sit queued
    behind the first, unconfirmed, invisible to CanIf_Transmit until something frees the pipeline.
    Confirming the one outstanding event does exactly that, so it is where a queued flood would
    actually surface."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=20)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    for _ in range(10):
        handle.lib.Xcp_MainFunction()

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]

    assert len(events) == 1, 'exactly one EV_CMD_PENDING may be outstanding at a time'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]
    assert events == [], 'confirming the one outstanding event must not release a queued flood'


def test_a_second_ev_cmd_pending_follows_the_first_confirmation():
    """The complement of the test above, and the one that stops 'bounded to one' from degenerating
    into 'exactly one, ever'. After the first event is confirmed the slave may ask again, which is
    what keeps a master's timer alive across a long erase (1.1/1.7.2.4.2, Diagram 28)."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=20)
    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_MainFunction()

    events = [call for call in handle.can_if_transmit.call_args_list
              if call[0][1].SduDataPtr[0] == 0xFD and call[0][1].SduDataPtr[1] == 0x05]

    assert len(events) == 2


def test_a_foreign_events_confirmation_does_not_release_the_bound():
    """Review fix round 1, finding 2. DD54's bound is 'no EV_CMD_PENDING FROM THIS PENDING
    COMMAND still outstanding', not 'no event of any kind'. The event queue is shared with
    EV_STORE_CAL (Xcp_MainFunction's own STORE_CAL_REQ block) and EV_DAQ_OVERLOAD
    (Xcp_TriggerEventChannel, Xcp_DaqRuntime.c).

    Task 3 retired this test's original second producer. SET_REQUEST used to be sent after
    program_start deferred, which was the simplest way to put a second, independent producer on
    the queue without a full DAQ configuration -- but DD55 (source/Xcp.c's ERR_CMD_BUSY gate)
    now answers ANY command arriving while pending_command.active is TRUE with ERR_CMD_BUSY,
    SYNCH alone excepted, and does not dispatch it. A SET_REQUEST sent in that window never
    reaches Xcp_DTOCmdStdSetRequest, session_status never gains STORE_CAL_REQ, and
    Xcp_MainFunction's STORE_CAL_REQ block never fires -- the scenario this test needs no longer
    exists on that path. EV_DAQ_OVERLOAD is the surviving second producer, because
    Xcp_TriggerEventChannel is called directly rather than through Xcp_CanIfRxIndication: DD55
    gates the CTO receive path, not this call, which is exactly the property this substitution
    needs.

    max_odt=2 against daq_queue_size=1 (one usable ring slot, matching
    daq_runtime_test.py's own test_an_overloaded_trigger_queues_exactly_one_overload_event
    construction) makes a single trigger sample one ODT successfully and drop the other, raising
    exactly one EV_DAQ_OVERLOAD (1.1/1.8.6). The one successful ODT's own DTO frame is an
    unavoidable side effect of that construction: Xcp_TransmitOneFrame ranks DAQ below both CTO
    and the event queue, so that frame only gets a turn once this test's event traffic finally
    stops -- which is why the last step below checks for the ABSENCE of an EV_CMD_PENDING shape
    rather than for no transmission at all, unlike every earlier step here.

    No other test in this file has two event sources, which is exactly why the leak this pins was
    invisible before: with one producer, 'clear on any confirmation' and 'clear on this command's
    own confirmation' are indistinguishable.

    Sequence (event_queue_size=4 so both events comfortably coexist in the ring at once). Checked
    one step at a time, resetting the mock before each: Xcp_Internal.event.pdu_info is one buffer
    reused for every event, whichever type, so a *retrospective* scan of call_args_list is not
    reliable evidence of what an earlier call actually sent -- an old entry's SduDataPtr reflects
    whatever the *next* event transmission later wrote into that same memory. Only the single most
    recent call (this file's transmitted() helper) is ever a trustworthy snapshot, which is why
    every other test in this file already reads transmitted() rather than filtering
    call_args_list -- except the two DD54 tests just above, which get away with a retrospective
    scan only because EV_CMD_PENDING is the sole event type they ever produce.

    1. A busy poll pushes and transmits EV_CMD_PENDING #1.
    2. Xcp_TriggerEventChannel fires DAQ1's bound event directly: one ODT samples into the DAQ
       queue's only slot, the other is dropped, and EV_DAQ_OVERLOAD is pushed behind #1 -- #1 is
       still in flight, unconfirmed, so nothing new is transmitted this step.
    3. Confirming #1 correctly clears the bound (it IS the module's own event) and reveals
       EV_DAQ_OVERLOAD, which is selected and transmitted next -- nothing else competes ahead of
       it, since this producer has no CTO response of its own the way SET_REQUEST used to.
    4. A further busy poll finds the bound correctly clear and pushes EV_CMD_PENDING #2, which
       only queues behind the still-in-flight EV_DAQ_OVERLOAD -- nothing new transmitted this step.
    5. Confirming EV_DAQ_OVERLOAD -- not a CMD_PENDING event -- drains the queue in turn, so #2 is
       selected and transmitted. This is the moment a module that clears the bound unconditionally
       would also (wrongly) clear it, since #2 is the one now in flight and NOT yet confirmed.
    6. One more busy poll: a leaking module pushes EV_CMD_PENDING #3 here, behind #2, which is
       still outstanding. Nothing transmits this step either way -- the pipeline is still occupied
       by #2 -- so this step cannot by itself distinguish the fix from the leak.
    7. Confirming #2 is where the two diverge: fixed, the bound was held at step 5, so step 6
       pushed nothing, and the freed pipeline goes to the waiting DTO frame instead -- the DAQ
       queue outranks nothing else once CTO and the event queue are both actually empty. Leaking,
       step 6's #3 is sitting queued ahead of that DTO frame, and transmits now instead -- a THIRD
       EV_CMD_PENDING that never got a TxConfirmation-driven release.
    """
    handle = pgm_handle(event_queue_size=4, daq_queue_size=1,
                        daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=1),))
    busy_then(handle, 0x00, busy_calls=20)

    def daq_setup_exchange(request):
        """RxIndication + MainFunction + TxConfirmation, confirmed as it goes: plain sequential
        setup, run entirely before program_start below, so pending_command.active is FALSE
        throughout and none of these CTOs can ever meet DD55's busy gate."""
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    for odt in range(2):
        daq_setup_exchange((0xE2, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (odt, 0x00))
        daq_setup_exchange((0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000 + odt, 'LITTLE_ENDIAN')))
    daq_setup_exchange((0xE0, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) +
                       tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x01, 0x00))
    daq_setup_exchange((0xDE, 0x01) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))

    handle.can_if_transmit.reset_mock()

    program_start(handle)
    handle.lib.Xcp_MainFunction()  # 1
    assert transmitted(handle)[0:2] == (0xFD, 0x05), 'EV_CMD_PENDING #1'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)  # 2
    assert transmitted(handle) is None, 'the pipeline is still occupied by #1, unconfirmed'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))  # 3
    assert transmitted(handle)[0:2] == (0xFD, 0x06), 'EV_DAQ_OVERLOAD, revealed once #1 is gone'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # 4
    assert transmitted(handle) is None, 'the pipeline is still occupied by EV_DAQ_OVERLOAD, unconfirmed'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))  # 5
    assert transmitted(handle)[0:2] == (0xFD, 0x05), '#2, queued behind EV_DAQ_OVERLOAD until now'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # 6
    assert transmitted(handle) is None, \
        'the pipeline is still occupied by #2 -- this step alone cannot show the leak'

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))  # 7

    assert transmitted(handle)[0:2] != (0xFD, 0x05), \
        'confirming EV_DAQ_OVERLOAD at step 5 must not have released the bound on #2 -- a module ' \
        'that cleared it there would have let step 6 push a third EV_CMD_PENDING, which would ' \
        'transmit here as soon as #2 itself is confirmed, ahead of the DTO frame this correctly ' \
        'empty event queue now finally lets through instead'


def test_a_failed_push_leaves_the_bound_clear_so_a_later_poll_retries():
    """Review fix round 1, finding 5. Xcp_EventQueuePush can fail (queue full); the retry
    contract is that event_outstanding stays FALSE whenever nothing was actually queued, so the
    very next busy poll tries again. Marking one outstanding unconditionally would starve every
    later poll of a retry for the rest of the operation, permanently, since only a successful pop
    of an actual queued event ever clears the flag.

    Reuses set_request_test.py's proven technique for forcing Xcp_EventQueuePush to fail: at
    event_queue_size=2 an event already selected for transmission, unconfirmed, still occupies its
    ring slot (Xcp_EventQueueGet peeks without advancing `read`), so the ring's one usable slot
    (capacity eventQueueSize - 1) is unavailable to a second push until that first event is
    confirmed. EV_STORE_CAL (via SET_REQUEST) is put in that unconfirmed, in-flight state first,
    which forces the PGM busy poll's own push to fail outright -- no DAQ configuration needed.

    Checked one step at a time with transmitted(), resetting the mock before each, rather than by
    scanning call_args_list once at the end: Xcp_Internal.event.pdu_info is one buffer reused for
    every event, so an old entry's SduDataPtr silently takes on whatever a *later* event
    transmission writes into that same memory -- see
    test_a_foreign_events_confirmation_does_not_release_the_bound, just above, for the full
    explanation and the test this file used to get that wrong."""
    handle = pgm_handle(event_queue_size=2)

    def store_calibration_completes(p_success):
        p_success[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = store_calibration_completes
    busy_then(handle, 0x00, busy_calls=20)

    # SET_REQUEST(STORE_CAL_REQ), driven to the point where EV_STORE_CAL is selected and
    # transmitted but not yet confirmed -- occupying the ring's only usable slot.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))  # confirms SET_REQUEST's own
    # CTO response; EV_STORE_CAL is selected and transmitted next, and stays unconfirmed

    handle.can_if_transmit.reset_mock()

    program_start(handle)
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # busy poll's own push fails outright: the ring is full

    assert transmitted(handle) is None, 'nothing was queued, so nothing may be transmitted'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))  # confirms EV_STORE_CAL,
    # freeing the ring; nothing is queued yet, so nothing transmits from this call either
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()  # a module that marked the bound set on the failed push above
    # would skip this retry forever; one that left it clear pushes and transmits now

    assert transmitted(handle)[0:2] == (0xFD, 0x05), \
        'a failed push must not block every later retry once the queue has room again'


def test_program_reset_defers_like_program_start():
    """Task 4, requirement 5. Xcp_DTOCmdPgmProgramReset must go through the exact same
    pending-command machinery PROGRAM_START uses -- Xcp_PgmPollPendingCommand and
    Xcp_PgmCompletePendingCommand switch on pending_command.pid precisely so a second command can
    join them -- rather than answering synchronously regardless of what Xcp_ProgramReset reports.

    Isomorphic to test_the_response_appears_on_the_main_function_where_the_callback_completes
    above, substituting Xcp_ProgramReset for Xcp_ProgramStart: still busy on the second poll (only
    EV_CMD_PENDING may go out), and the positive response arrives only once the callback actually
    reports E_OK. Mutation: a handler that answers immediately regardless of Xcp_ProgramReset's
    first return value would transmit 0xFF right after program_reset(handle), before either
    Xcp_MainFunction call below, which the first assertion catches."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=2, mock=handle.xcp_program_reset)
    handle.can_if_transmit.reset_mock()
    program_reset(handle)

    handle.lib.Xcp_MainFunction()
    assert transmitted(handle)[0] != 0xFF, 'still busy on the second poll'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0] == 0xFF, 'the positive response arrives once Xcp_ProgramReset does'


def test_a_failing_program_reset_yields_err_generic_and_does_not_disconnect():
    """Xcp_ProgramReset copies Xcp_StoreCalibrationDataToNonVolatileMemory's contract (design
    Section 4): pStatusCode non-zero means the operation finished, but unsuccessfully. Mirrors
    test_a_failing_integrator_yields_err_generic_and_leaves_the_session_closed above, PROGRAM_START's
    own equivalent.

    The disconnect must NOT happen on this path -- DD57 has PROGRAM_RESET disconnect only in the
    success branch of its completion, immediately after building a positive response, and there is
    no positive response here to hang a disconnect off of. xcp_get_seed's call_count is the
    witness, exactly as in
    pgm_session_test.test_program_reset_disconnects_once_the_response_is_confirmed: a module that
    already believes itself disconnected drops a non-CONNECT CTO with no dispatch at all
    (source/Xcp.c's disconnected-state gate), so a module that wrongly disconnects even on FAILURE
    would leave xcp_get_seed uncalled here."""
    handle = pgm_handle()
    busy_then(handle, 0x01, busy_calls=0, mock=handle.xcp_program_reset)
    handle.can_if_transmit.reset_mock()
    program_reset(handle)
    handle.lib.Xcp_MainFunction()

    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'

    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))

    assert handle.xcp_get_seed.call_count == 1, 'a failed PROGRAM_RESET must not disconnect'

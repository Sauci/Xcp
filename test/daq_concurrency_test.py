#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def test_exclusive_area_stub_is_linked_and_reaches_the_integrator_callback():
    """The DD5 exclusive area stub (SchM_Enter_Xcp_DtoQueue / SchM_Exit_Xcp_DtoQueue) must be
    declared in the integrator-facing header, reachable from the sixth translation unit, and
    wired through the CFFI harness to its mock -- exactly like any other integrator callback.
    Xcp_Init itself now calls it once per configured ODT while clearing DAQ entries on start-up
    (DD14, Task 15 fix round 1: Xcp_DaqListClearEntries takes the area so a concurrent sampler
    cannot observe a torn entry), so the mocks are reset once construction is done to isolate
    this test's own direct calls from that."""
    handle = XcpTest(DefaultConfig())
    handle.sch_m_enter_xcp_dto_queue.reset_mock()
    handle.sch_m_exit_xcp_dto_queue.reset_mock()

    handle.lib.SchM_Enter_Xcp_DtoQueue()
    handle.sch_m_enter_xcp_dto_queue.assert_called_once_with()

    handle.lib.SchM_Exit_Xcp_DtoQueue()
    handle.sch_m_exit_xcp_dto_queue.assert_called_once_with()


def exchange(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def queued_frames(handle):
    """Every frame currently in the ring, oldest first, as bytes. See
    test/daq_identification_field_test.py for why reading Xcp_Rt[...].dtoQueue directly needs no
    test-only surface in the module under test."""
    queue = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].dtoQueue
    frames = list()
    index = queue.read
    for _ in range(queue.count):
        frame = queue.frame[index]
        frames.append(bytes(frame.data[0:frame.length]))
        index = (index + 1) % queue.depth
    return frames


def test_clear_daq_list_takes_the_exclusive_area():
    """Fix round 1, finding 1 / finding B. A one-sided area -- the sampler taking it while
    Xcp_DaqListClearEntries does not -- is exactly the bug this catches directly, with no
    threading needed: a clear that never enters the area leaves this count unchanged. This is a
    genuine mutation proof, not just a design argument: verified to FAIL against the pre-fix
    Xcp_DaqListClearEntries (no SchM_Enter/Exit at all) and PASS against the fixed one; both runs
    are recorded in the Task 15 report, "Fix round 1"."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    enter_count_before = handle.sch_m_enter_xcp_dto_queue.call_count

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
            (0xE3, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN'))))

    assert handle.sch_m_enter_xcp_dto_queue.call_count > enter_count_before, \
        'CLEAR_DAQ_LIST never entered the exclusive area'


def test_a_clear_arriving_between_two_entry_reads_does_not_corrupt_the_frame():
    """Fix round 1, finding C: DD14's actual guarantee, exercised end to end rather than by
    mechanism. Xcp_ReadSlaveMemoryU8 is called from OUTSIDE the exclusive area, reading through
    Xcp_DaqSampleOdt's local copies -- precisely the window a concurrent CLEAR_DAQ_LIST could
    otherwise corrupt. The first read's side effect injects a CLEAR_DAQ_LIST for the very list
    being sampled, simulating the command arriving mid-sample (Xcp_CanIfRxIndication runs the
    handler, including Xcp_DaqListClearEntries, synchronously -- no Xcp_MainFunction needed to
    observe its effect). If the sampler read the live entries instead of its copies, the second
    entry's address would already be cleared to 0 by the time its own read fired."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=2),)))
    connect(handle)

    exchange(handle, (0xE2, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x00, 0x00))
    exchange(handle, (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))
    exchange(handle, (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x2000, 'LITTLE_ENDIAN')))
    exchange(handle, (0xE0, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) +
             tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x01, 0x00))
    exchange(handle, (0xDE, 0x01) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))

    addresses_read = list()
    values = {0x1000: 0xAA, 0x2000: 0xBB}
    call_count = [0]

    def read_slave_memory(p_address, _extension, p_buffer):
        address = int(handle.ffi.cast('uint32_t', p_address))
        addresses_read.append(address)
        call_count[0] += 1
        if call_count[0] == 1:
            handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
                    (0xE3, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN'))))
        p_buffer[0] = values.get(address, 0xFF)

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory

    handle.lib.Xcp_TriggerEventChannel(0)

    frames = queued_frames(handle)
    assert len(frames) == 1, 'the ODT still produced its frame despite the injected clear'
    assert frames[0][-2:] == bytes((0xAA, 0xBB)), \
        'both entries -- sampled from copies made before the clear reached the live array -- ' \
        'survived it intact'
    assert 0 not in addresses_read, 'no read was ever handed the cleared address 0'

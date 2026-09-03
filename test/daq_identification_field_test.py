#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def queued_frames(handle):
    """Every frame currently in the ring, oldest (earliest pushed) first, as bytes.

    Reads Xcp_Rt[...].dtoQueue directly -- Xcp_Rt is exposed under CFFI_ENABLE and
    Xcp_DtoQueueType/Xcp_DtoFrameType are both public in interface/Xcp_Types.h, so this needs no
    test-only surface in the module under test.
    """
    queue = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].dtoQueue
    frames = list()
    index = queue.read
    for _ in range(queue.count):
        frame = queue.frame[index]
        frames.append(bytes(frame.data[0:frame.length]))
        index = (index + 1) % queue.depth
    return frames


def configure_and_start(handle, values, daq_list=0, odt=0, size=1, byte_order='LITTLE_ENDIAN'):
    """Writes one ODT entry per value, then starts the list."""
    def exchange(request):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    exchange((0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) + (odt, 0x00))
    for index, _ in enumerate(values):
        exchange((0xE1, 0xFF, size, 0x00) +
                 tuple(u32_to_array(0x1000 + (index * size), byte_order)))
    exchange((0xE0, 0x00) + tuple(u16_to_array(daq_list, byte_order)) +
             tuple(u16_to_array(0, byte_order)) + (0x01, 0x00))
    exchange((0xDE, 0x01) + tuple(u16_to_array(daq_list, byte_order)))


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1000, byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_PTR to (daq_list, odt, entry 0), then WRITE_DAQ one entry of `size` bytes. Asserts
    both steps were accepted -- a caller relying on a configured entry must not pass because the
    write silently failed."""
    assert response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) +
                    (odt, 0x00))[0] == 0xFF
    assert response(handle, (0xE1, 0xFF, size, 0x00) +
                    tuple(u32_to_array(address, byte_order)))[0] == 0xFF


def start_daq_list(handle, daq_list=0, mode=0x00, channel=0, prescaler=1, priority=0,
                   byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_LIST_MODE with `mode`, then START_STOP_DAQ_LIST(START). Asserts both steps were
    accepted."""
    assert response(handle, (0xE0, mode) + tuple(u16_to_array(daq_list, byte_order)) +
                    tuple(u16_to_array(channel, byte_order)) + (prescaler, priority))[0] == 0xFF
    assert response(handle, (0xDE, 0x01) + tuple(u16_to_array(daq_list, byte_order)))[0] == 0xFF


def install_memory(handle, values, element_size=1, byte_order='LITTLE_ENDIAN'):
    """Each read returns the next value, so frame contents are predictable."""
    def read_slave_memory(_address, _extension, p_buffer):
        value = next(source)
        for i, b in enumerate(value.to_bytes(element_size,
                                             dict(BIG_ENDIAN='big',
                                                  LITTLE_ENDIAN='little')[byte_order],
                                             signed=False)):
            p_buffer[i] = int(b)

    source = (v for v in values * 100)
    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory


@pytest.mark.parametrize('ident, header', (
        ('ABSOLUTE', lambda first_pid, odt, daq: (first_pid + odt,)),
        ('RELATIVE_BYTE', lambda first_pid, odt, daq: (odt, daq)),
        ('RELATIVE_WORD', lambda first_pid, odt, daq: (odt,) + tuple(u16_to_array(daq, 'LITTLE_ENDIAN'))),
        ('RELATIVE_WORD_ALIGNED', lambda first_pid, odt, daq: (odt, 0x00) + tuple(u16_to_array(daq, 'LITTLE_ENDIAN')))))
def test_the_identification_field_matches_its_type(ident, header):
    """XCP part 2 - Protocol Layer Specification 1.1/1.1.2.1"""
    handle = XcpTest(DefaultConfig(identification_field_type=ident,
                                   daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=2),
                                         daq(name='DAQ2', max_odt=2, max_odt_entries=2))))
    connect(handle)
    install_memory(handle, [0xAA, 0xBB])
    configure_and_start(handle, [0xAA], daq_list=1, odt=0)

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = queued_frames(handle)[0]
    assert tuple(frame[0:len(header(2, 0, 1))]) == header(2, 0, 1), \
        'DAQ2 has FIRST_PID 2, relative ODT 0, absolute DAQ list number 1'
    assert frame[len(header(2, 0, 1))] == 0xAA, 'the data follows the identification field'


def test_the_word_identification_field_follows_the_configured_byte_order():
    handle = XcpTest(DefaultConfig(identification_field_type='RELATIVE_WORD',
                                   byte_order='BIG_ENDIAN',
                                   daqs=tuple(daq(name='DAQ{}'.format(i + 1), max_odt=1,
                                                  max_odt_entries=1) for i in range(4))))
    connect(handle)
    install_memory(handle, [0x5A], byte_order='BIG_ENDIAN')
    configure_and_start(handle, [0x5A], daq_list=3, byte_order='BIG_ENDIAN')

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = queued_frames(handle)[0]
    assert tuple(frame[0:3]) == (0x00, 0x00, 0x03), 'relative ODT 0, then DAQ list 3 as a WORD'


def test_absolute_odt_numbers_are_first_pid_plus_the_relative_number():
    """1.1/1.1.2.1: absolute_ODT_NUMBER = FIRST_PID(list) + relative ODT_NUMBER.

    Every ODT is configured before the list is started, not interleaved with starting it: WRITE_DAQ
    and SET_DAQ_PTR both answer ERR_DAQ_ACTIVE once the list is running (1.1/1.6.4.1.1.1/.2), so a
    per-ODT configure-then-start loop would silently leave every ODT past the first unwritten.
    """
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=1),)))
    connect(handle)
    install_memory(handle, [0x11, 0x22, 0x33])

    def exchange(request):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    for odt in range(3):
        exchange((0xE2, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (odt, 0x00))
        exchange((0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000 + odt, 'LITTLE_ENDIAN')))
    exchange((0xE0, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) +
             tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x01, 0x00))
    exchange((0xDE, 0x01) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))

    handle.lib.Xcp_TriggerEventChannel(0)

    frames = queued_frames(handle)
    assert [frame[0] for frame in frames] == [0, 1, 2]
    assert [frame[1] for frame in frames] == [0x11, 0x22, 0x33], \
        'each ODT sampled its own entry, in ODT order'


def test_an_entry_written_at_a_non_zero_slot_is_still_sampled():
    """Entry 0 of the ODT is left unwritten (length 0); entry 1 is the one WRITE_DAQ fills, via
    SET_DAQ_PTR positioned directly at it. DD14's per-ODT copy buffer is compacted -- it holds
    only the entries that turned out non-empty, indexed by copy order rather than by their
    original slot -- so this is the case that distinguishes compaction from a buggy copy that
    stored entries at their scan index instead: that variant would read back slot 0's
    never-written (uninitialised) copy rather than slot 1's real one."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=2),)))
    connect(handle)
    install_memory(handle, [0x7E])

    def exchange(request):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    exchange((0xE2, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x00, 0x01))
    exchange((0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x2000, 'LITTLE_ENDIAN')))
    exchange((0xE0, 0x00) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')) +
             tuple(u16_to_array(0, 'LITTLE_ENDIAN')) + (0x01, 0x00))
    exchange((0xDE, 0x01) + tuple(u16_to_array(0, 'LITTLE_ENDIAN')))

    handle.lib.Xcp_TriggerEventChannel(0)

    frames = queued_frames(handle)
    assert len(frames) == 1, 'the ODT had exactly one written entry, so it produced one frame'
    assert frames[0][-1] == 0x7E, 'the entry at slot 1 is what got sampled, not slot 0'


_timestamp_offset_identifications = (('ABSOLUTE', 1), ('RELATIVE_BYTE', 2), ('RELATIVE_WORD', 3),
                                     ('RELATIVE_WORD_ALIGNED', 4))
_timestamp_offset_sizes = tuple((size, wire) for size, wire in timestamp_wire_size.items() if size is not None)

# Every identification_field_type x every timestamp width, but the byte-order axis is trimmed to
# LITTLE_ENDIAN alone for the three identification widths added on top of the original ABSOLUTE
# cases: byte order governs how the timestamp's own bytes are encoded, already proven independent
# of the identification field's width by the ABSOLUTE cases below, so crossing it with every width
# again would only multiply 4 x 3 x 2 = 24 cases for no additional discriminating power.
_timestamp_offset_cases = [
    pytest.param(ident, id_size, size, width, byte_order,
                 id='{}-{}-{}'.format(ident, size, byte_order))
    for ident, id_size in _timestamp_offset_identifications
    for size, width in _timestamp_offset_sizes
    for byte_order in (('LITTLE_ENDIAN', 'BIG_ENDIAN') if ident == 'ABSOLUTE' else ('LITTLE_ENDIAN',))
]


@pytest.mark.parametrize('ident, id_size, size, width, byte_order', _timestamp_offset_cases)
def test_the_timestamp_follows_the_identification_field_in_the_first_odt(ident, id_size, size, width,
                                                                          byte_order):
    """1.1/1.1.2.2: 'DTO Packets directly after the Identification Field might have a Timestamp
    Field'. Parametrised over every identification_field_type, not just the default ABSOLUTE, and
    asserting at frame[id_size:id_size + width] rather than a hardcoded frame[1:1 + width]: an
    implementation that stored the timestamp at a fixed offset 1 instead of genuinely reading it
    off Xcp_DaqWriteIdentificationField's return value would only be caught here, at the three
    wider identification fields -- ABSOLUTE's own 1-byte field makes offset 1 and "after the
    identification field" indistinguishable.

    max_dto=9: the tightest combination this matrix reaches is a 4-byte RELATIVE_WORD_ALIGNED
    identification field plus a 4-byte DWORD timestamp plus the one configured data byte, exactly
    9 -- the default max_dto=8 would leave RELATIVE_WORD_ALIGNED/DWORD no room for that data byte
    and SET_DAQ_LIST_MODE would refuse to enable TIMESTAMP at all, which start_daq_list asserts
    against."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size=size), byte_order=byte_order,
                                   identification_field_type=ident, max_dto=9,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    handle.xcp_get_daq_timestamp.return_value = 0x89ABCDEF
    configure_one_entry(handle, daq_list=0, odt=0, size=1)
    start_daq_list(handle, daq_list=0, mode=0x10)

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = handle.can_if_transmit.call_args[0][1].SduDataPtr
    expected = (0x89ABCDEF & ((1 << (8 * width)) - 1)).to_bytes(
            width, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order])
    assert tuple(frame[id_size:id_size + width]) == tuple(expected)


def test_only_the_first_odt_of_a_cycle_carries_a_timestamp():
    """1.1/1.1.2.2 Diagram 10. A timestamp in every ODT would both waste bus bandwidth and
    misreport the sample instant of the later ODTs."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size='DWORD'),
                                   daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    handle.xcp_get_daq_timestamp.return_value = 0x11223344
    configure_one_entry(handle, daq_list=0, odt=0, size=1)
    configure_one_entry(handle, daq_list=0, odt=1, size=1)
    start_daq_list(handle, daq_list=0, mode=0x10)

    handle.lib.Xcp_TriggerEventChannel(0)
    frames = queued_frames(handle)

    assert len(frames[0]) == 1 + 4 + 1, 'ODT 0: PID + timestamp + one byte'
    assert len(frames[1]) == 1 + 1, 'ODT 1: PID + one byte, no timestamp'


def test_the_clock_is_read_once_per_cycle_not_once_per_odt():
    """A per-ODT read would give ODTs of one cycle different timestamps, contradicting the
    'first ODT of a DAQ cycle' model, and would call into integrator code more often than needed."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size='DWORD'),
                                   daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    for odt in range(3):
        configure_one_entry(handle, daq_list=0, odt=odt, size=1)
    start_daq_list(handle, daq_list=0, mode=0x10)
    handle.xcp_get_daq_timestamp.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.xcp_get_daq_timestamp.call_count == 1


def test_no_timestamp_is_transmitted_when_the_mode_is_off():
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size='DWORD'),
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    configure_one_entry(handle, daq_list=0, odt=0, size=1)
    start_daq_list(handle, daq_list=0, mode=0x00)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][1].SduLength == 2
    assert handle.xcp_get_daq_timestamp.call_count == 0

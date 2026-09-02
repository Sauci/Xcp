#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def value_for_address(address, element_size):
    """The byte pattern a correctly-addressed read of `element_size` bytes must return: the low
    byte of the address, then consecutive bytes from there. install_memory's mock computes exactly
    this from the address argument it actually receives, so a frame's contents encode *where* each
    element was read from. A test that wants to know what a read SHOULD have returned -- as
    opposed to merely what the mock WAS called with -- calls this directly against an
    independently-computed expected address (see expected_addresses), so a wrong per-element
    address advance produces the wrong bytes at a known offset instead of merely a
    differently-ordered but still-distinct sequence."""
    base = address & 0xFF
    return bytes(((base + i) & 0xFF) for i in range(element_size))


def expected_addresses(odt, sizes, element_size):
    """Replicates DaqSession.write_odt's own address arithmetic, so a test can independently
    predict, for every element write_odt configured, the exact address Xcp_DaqSampleOdt must read
    it from -- in the same order the ODT is sampled (entry order, then element order within an
    entry).

    Only valid for the entry shapes write_odt is actually given in this file: every entry but the
    last sized exactly `element_size` (one element), the last sized up to `2 * element_size` --
    exactly what plan_odt_entries produces, and what every single-entry `sizes` list trivially
    satisfies. write_odt addresses entry `index` at `base + index * element_size`, which only
    matches this generator's own `base + element * element_size` per-element addressing when
    entries before the last never span more than one element; a `sizes` list with more than one
    multi-element entry would need a running byte offset instead, which write_odt does not
    compute."""
    for index, size in enumerate(sizes):
        base = 0x00010000 + (odt * 0x100) + (index * element_size)
        for element in range(size // element_size):
            yield base + (element * element_size)


class DaqSession(object):
    """Drives one configured, running DAQ list and records exactly what reached CanIf."""

    def __init__(self, handle, byte_order):
        self.handle = handle
        self.byte_order = byte_order
        self.reads = []

    def exchange(self, request):
        self.handle.can_if_transmit.reset_mock()
        self.handle.lib.Xcp_CanIfRxIndication(0x0001, self.handle.get_pdu_info(request))
        self.handle.lib.Xcp_MainFunction()
        self.handle.lib.Xcp_CanIfTxConfirmation(0x0002, self.handle.define('E_OK'))
        return tuple(self.handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    def install_memory(self, element_size):
        """Every read's returned bytes are a deterministic function of the address argument alone
        (value_for_address), never of call order: a wrong per-element address advance -- e.g.
        re-reading an entry's base address for every element instead of stepping by element_size
        -- then produces the wrong bytes at a known offset, rather than merely a
        differently-ordered but still-distinct sequence that a call-order-keyed pattern could not
        tell apart from correct."""
        def read(address, _extension, p_buffer):
            value = value_for_address(int(self.handle.ffi.cast('uint32_t', address)), element_size)
            for i, b in enumerate(value):
                p_buffer[i] = int(b)
            self.reads.append(value)

        self.handle.xcp_read_slave_memory_u8.side_effect = read
        self.handle.xcp_read_slave_memory_u16.side_effect = read
        self.handle.xcp_read_slave_memory_u32.side_effect = read

    def write_odt(self, daq_list, odt, sizes, element_size):
        self.exchange((0xE2, 0x00) + tuple(u16_to_array(daq_list, self.byte_order)) + (odt, 0x00))
        for index, size in enumerate(sizes):
            address = 0x00010000 + (odt * 0x100) + (index * element_size)
            self.exchange((0xE1, 0xFF, size, 0x00) +
                          tuple(u32_to_array(address, self.byte_order)))

    def start(self, daq_list, channel=0):
        self.exchange((0xE0, 0x00) + tuple(u16_to_array(daq_list, self.byte_order)) +
                      tuple(u16_to_array(channel, self.byte_order)) + (0x01, 0x00))
        return self.exchange((0xDE, 0x01) + tuple(u16_to_array(daq_list, self.byte_order)))

    def trigger(self, channel=0):
        """Fires the channel and drains every queued frame, returning them in order."""
        self.handle.can_if_transmit.reset_mock()
        self.handle.lib.Xcp_TriggerEventChannel(channel)

        frames = []
        while True:
            call = self.handle.can_if_transmit.call_args
            if call is None:
                break
            frames.append((call[0][0], bytes(call[0][1].SduDataPtr[0:call[0][1].SduLength])))
            self.handle.can_if_transmit.reset_mock()
            self.handle.lib.Xcp_CanIfTxConfirmation(call[0][0], self.handle.define('E_OK'))
        return frames


@pytest.mark.parametrize('ag', address_granularities)
@pytest.mark.parametrize('ident', identification_field_types)
@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('max_dto', max_dtos)
def test_every_dto_byte_lands_where_the_specification_puts_it(ag, ident, byte_order, max_dto):
    """XCP part 2 - Protocol Layer Specification 1.1/1.1.4.1: identification field, then data.

    Two DAQ lists so the absolute DAQ list number in the relative identification field types is
    non-zero, and three ODTs so absolute ODT numbering is exercised past FIRST_PID."""
    element_size = element_size_from_address_granularity(ag)
    capacity = max_dto - identification_field_size[ident]
    sizes = plan_odt_entries(capacity, element_size, wanted=3)

    if not sizes:
        pytest.skip('{} leaves no room for a {}-byte element'.format(ident, element_size))

    handle = XcpTest(DefaultConfig(address_granularity=ag,
                                   identification_field_type=ident,
                                   byte_order=byte_order,
                                   max_dto=max_dto,
                                   daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=4),
                                         daq(name='DAQ2', max_odt=3, max_odt_entries=4))))
    connect(handle)

    session = DaqSession(handle, byte_order)
    session.install_memory(element_size)
    for odt in range(3):
        session.write_odt(daq_list=1, odt=odt, sizes=sizes, element_size=element_size)
    first_pid = session.start(daq_list=1)[1]

    assert first_pid == 2, 'DAQ2 follows DAQ1, which owns two ODTs'

    frames = session.trigger()

    assert len(frames) == 3, 'one frame per non-empty ODT'

    for odt, (pdu_id, frame) in enumerate(frames):
        header = expected_identification_field(ident, first_pid, odt, 1, byte_order)

        assert tuple(frame[0:len(header)]) == header, 'ODT {} identification field'.format(odt)
        assert len(frame) == len(header) + sum(sizes), 'ODT {} length'.format(odt)

        offset = len(header)
        for address in expected_addresses(odt, sizes, element_size):
            expected = value_for_address(address, element_size)
            assert bytes(frame[offset:offset + element_size]) == expected, \
                'ODT {} element at offset {} (address 0x{:08X})'.format(odt, offset, address)
            offset += element_size


@pytest.mark.parametrize('max_dto', max_dtos)
@pytest.mark.parametrize('ag', address_granularities)
def test_a_dto_filled_to_capacity_has_every_byte_in_place(ag, max_dto):
    """The matrix above caps every ODT at 3 entries (plan_odt_entries(wanted=3)), so it never
    frames anywhere near a DTO's real capacity -- at BYTE granularity MAX_DTO 8, 16 and 64 all
    produce the identical entry plan [1, 1, 2], so those three configurations emit byte-identical
    frames and MAX_DTO's positional effect was pinned only by the number GET_DAQ_RESOLUTION_INFO
    reports, never by an actual frame's length or content.

    RELATIVE_WORD_ALIGNED is used throughout because it is the only identification field type
    whose MAX_ODT_ENTRY_SIZE_DAQ (= MAX_DTO - 4) stays a multiple of every address granularity's
    element size for all three MAX_DTO values in this matrix (8, 16 and 64 are all multiples of
    4) -- so a single WRITE_DAQ entry can legally claim the *entire* reported capacity in one
    write, filling the DTO to the exact byte rather than just close to it."""
    element_size = element_size_from_address_granularity(ag)
    capacity = max_dto - identification_field_size['RELATIVE_WORD_ALIGNED']

    handle = XcpTest(DefaultConfig(address_granularity=ag,
                                   identification_field_type='RELATIVE_WORD_ALIGNED',
                                   max_dto=max_dto,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)
    session = DaqSession(handle, 'LITTLE_ENDIAN')
    session.install_memory(element_size)
    session.write_odt(daq_list=0, odt=0, sizes=[capacity], element_size=element_size)
    session.start(daq_list=0)

    frames = session.trigger()

    assert len(frames) == 1
    header = expected_identification_field('RELATIVE_WORD_ALIGNED', 0, 0, 0, 'LITTLE_ENDIAN')
    frame = frames[0][1]

    assert len(frame) == len(header) + capacity == max_dto, \
        'the DTO is exactly full: identification field plus every capacity byte, nothing more'

    offset = len(header)
    for address in expected_addresses(0, [capacity], element_size):
        expected = value_for_address(address, element_size)
        assert bytes(frame[offset:offset + element_size]) == expected, \
            'byte at offset {} (address 0x{:08X})'.format(offset, address)
        offset += element_size


@pytest.mark.parametrize('ag', address_granularities)
@pytest.mark.parametrize('ident', identification_field_types)
@pytest.mark.parametrize('max_dto', max_dtos)
def test_write_daq_accepts_exactly_what_get_daq_resolution_info_promises(ag, ident, max_dto):
    """The two commands must agree, or a master that trusts the reported limit gets rejected."""
    element_size = element_size_from_address_granularity(ag)
    handle = XcpTest(DefaultConfig(address_granularity=ag,
                                   identification_field_type=ident,
                                   max_dto=max_dto,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=8),)))
    connect(handle)
    session = DaqSession(handle, 'LITTLE_ENDIAN')

    resolution = session.exchange((0xD9,))
    granularity, max_entry_size = resolution[1], resolution[2]

    assert granularity == element_size
    assert max_entry_size == max_dto - identification_field_size[ident]

    largest = max_entry_size - (max_entry_size % element_size)
    if largest == 0:
        pytest.skip('no element fits')

    session.exchange((0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))
    assert session.exchange((0xE1, 0xFF, largest, 0x00) +
                            tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))[0] == 0xFF, \
        'the largest promised entry is accepted'

    session.exchange((0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))
    # The tightest granularity-valid size that must still be refused: max_entry_size + 1 can
    # overshoot by more than one granularity step (e.g. DWORD/RELATIVE_BYTE/MAX_DTO=8 has
    # max_entry_size=6, largest=4, so +1 gives 7 -- itself not a multiple of 4, so refusing it
    # would be indistinguishable from the misalignment check write_daq_test.py already covers,
    # leaving sizes 5, 6 and 7 untested). largest + element_size is always a multiple of the
    # granularity and always exceeds max_entry_size by construction (largest is the greatest such
    # multiple not exceeding it), so refusing it isolates the size-vs-ceiling comparison alone.
    refused_size = largest + element_size
    assert session.exchange((0xE1, 0xFF, refused_size, 0x00) +
                            tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))[0:2] == (0xFE, 0x22), \
        'the next granularity-valid size past the largest accepted one is refused'


def test_a_list_configured_only_past_odt_0_is_still_recognised_as_configured():
    """Regression for the gap Task 11's review left open (progress.md, Task 11 "minor (deferred)":
    "Xcp_DaqListIsConfigured is only ever exercised with ODT 0 / entry 0 written, so reducing its
    loops to check just [0][0] would fail no test. CARRY INTO TASK 19: the acceptance matrix must
    configure a list whose only written entry is NOT in ODT 0, or this stays uncovered.").

    None of this file's other tests close that gap either -- every one of them writes relative
    ODT 0 of whichever list it starts, alongside any later ODT. Here DAQ2's relative ODT 0
    (absolute ODT 1) is never addressed at all -- its one entry keeps its power-up length of 0 --
    while relative ODT 1 (absolute ODT 2) gets the only written entry. Starting the list can only
    succeed if Xcp_DaqListIsConfigured's nested loop actually reaches past odt_idx 0 to find it;
    a stub that only checked [0][0] would see a never-written entry there and answer
    ERR_DAQ_CONFIG instead of starting the list."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),
                                         daq(name='DAQ2', max_odt=2, max_odt_entries=1))))
    connect(handle)
    session = DaqSession(handle, 'LITTLE_ENDIAN')
    session.install_memory(1)

    session.write_odt(daq_list=1, odt=1, sizes=[1], element_size=1)

    response = session.start(daq_list=1)

    assert response[0] == 0xFF, \
        'ERR_DAQ_CONFIG here would mean Xcp_DaqListIsConfigured missed the entry at ODT 1'
    assert response[1] == 1, 'FIRST_PID of DAQ2: DAQ1 owns the one ODT ahead of it'

    frames = session.trigger()

    assert len(frames) == 1, 'ODT 0 has no written entry and samples to nothing; only ODT 1 fires'
    assert frames[0][1][0] == response[1] + 1, 'absolute ODT number: FIRST_PID + relative ODT 1'


@pytest.mark.parametrize('max_cto', max_ctos)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_the_command_path_is_unaffected_by_max_cto(max_cto, byte_order):
    """DAQ commands are all eight bytes or fewer, so every MAX_CTO must carry them identically."""
    handle = XcpTest(DefaultConfig(max_cto=max_cto,
                                   byte_order=byte_order,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),
                                         daq(name='DAQ2', max_odt=1, max_odt_entries=1))))
    connect(handle)
    session = DaqSession(handle, byte_order)

    assert session.exchange((0xDA,))[2:4] == tuple(u16_to_array(2, byte_order)), 'MAX_DAQ'

    session.write_odt(daq_list=1, odt=0, sizes=[1], element_size=1)

    assert session.start(daq_list=1)[1] == 1, 'FIRST_PID of the second list'

    mode = session.exchange((0xDF, 0x00) + tuple(u16_to_array(1, byte_order)))
    assert mode[1] & 0x40 != 0, 'RUNNING'
    assert mode[4:6] == tuple(u16_to_array(0, byte_order)), 'event channel'


@pytest.mark.parametrize('ag', address_granularities)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_measured_data_is_passed_through_untouched_by_byte_order(ag, byte_order):
    """The module reorders protocol words, never measured data -- same rule UPLOAD follows."""
    element_size = element_size_from_address_granularity(ag)
    handle = XcpTest(DefaultConfig(address_granularity=ag,
                                   byte_order=byte_order,
                                   identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    marker = bytes(range(0xA0, 0xA0 + element_size))

    def read(_address, _extension, p_buffer):
        for i, b in enumerate(marker):
            p_buffer[i] = int(b)

    handle.xcp_read_slave_memory_u8.side_effect = read
    handle.xcp_read_slave_memory_u16.side_effect = read
    handle.xcp_read_slave_memory_u32.side_effect = read

    session = DaqSession(handle, byte_order)
    session.write_odt(daq_list=0, odt=0, sizes=[element_size], element_size=element_size)
    session.start(daq_list=0)

    frames = session.trigger()

    assert frames[0][1][1:1 + element_size] == marker, 'in the order the integrator wrote it'


@pytest.mark.parametrize('ident', identification_field_types)
def test_two_lists_on_one_channel_are_both_sampled_with_distinct_identification(ident):
    handle = XcpTest(DefaultConfig(identification_field_type=ident,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),
                                         daq(name='DAQ2', max_odt=1, max_odt_entries=1)),
                                   events=(event(triggered_daq_list_ref=['DAQ1', 'DAQ2']),)))
    connect(handle)

    session = DaqSession(handle, 'LITTLE_ENDIAN')
    session.install_memory(1)
    for daq_list in (0, 1):
        session.write_odt(daq_list=daq_list, odt=0, sizes=[1], element_size=1)
        session.start(daq_list=daq_list)

    frames = session.trigger()

    assert len(frames) == 2
    headers = [tuple(frame[0:identification_field_size[ident]]) for _, frame in frames]
    assert headers[0] != headers[1], 'each list is identifiable in its own frames'
    assert headers[0] == expected_identification_field(ident, 0, 0, 0, 'LITTLE_ENDIAN')
    assert headers[1] == expected_identification_field(ident, 1, 0, 1, 'LITTLE_ENDIAN')


@pytest.mark.parametrize('trailing_value', trailing_values)
def test_the_relative_word_aligned_fill_byte_carries_the_configured_trailing_value(trailing_value):
    """1.1/1.1.2.1 gives the RELATIVE_WORD_ALIGNED FILL byte no defined value;
    source/Xcp_DaqRuntime.c fills it with the same trailing value Xcp_FinalizeResPacket pads
    responses with. Asserting only the default (0) proves nothing: DefaultConfig's own default
    trailing_value is 0, so a deleted FILL-byte write and a correct one are indistinguishable at
    that value. Swept over both ends of `trailing_values` -- already defined in parameter.py but,
    until now, never exercised by any DAQ test -- so the non-zero case is the one that actually
    distinguishes a real write from an incidental zero."""
    handle = XcpTest(DefaultConfig(identification_field_type='RELATIVE_WORD_ALIGNED',
                                   trailing_value=trailing_value,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)
    session = DaqSession(handle, 'LITTLE_ENDIAN')
    session.install_memory(1)
    session.write_odt(daq_list=0, odt=0, sizes=[1], element_size=1)
    session.start(daq_list=0)

    frames = session.trigger()

    assert frames[0][1][1] == trailing_value, 'FILL byte carries the configured trailing value'


@pytest.mark.parametrize('prescaler', (1, 2, 5))
def test_the_prescaler_divides_the_raster(prescaler):
    """1.1/1.6.4.1.1.3: a prescaler above 1 reduces the transmission rate."""
    handle = XcpTest(DefaultConfig(prescaler_supported=True,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)
    session = DaqSession(handle, 'LITTLE_ENDIAN')
    session.install_memory(1)
    session.write_odt(daq_list=0, odt=0, sizes=[1], element_size=1)
    session.exchange((0xE0, 0x00, 0x00, 0x00, 0x00, 0x00, prescaler, 0x00))
    session.exchange((0xDE, 0x01, 0x00, 0x00))

    frames = []
    for _ in range(prescaler * 3):
        frames.extend(session.trigger())

    assert len(frames) == 3, 'three transmissions out of {} triggers'.format(prescaler * 3)

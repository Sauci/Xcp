#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools
import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


class DaqSession(object):
    """Drives one configured, running DAQ list and records exactly what reached CanIf."""

    def __init__(self, handle, byte_order):
        self.handle = handle
        self.byte_order = byte_order
        self.reads = []

    def exchange(self, request):
        self.handle.lib.Xcp_CanIfRxIndication(0x0001, self.handle.get_pdu_info(request))
        self.handle.lib.Xcp_MainFunction()
        self.handle.lib.Xcp_CanIfTxConfirmation(0x0002, self.handle.define('E_OK'))
        return tuple(self.handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    def install_memory(self, element_size):
        """Every read yields a distinct, position-revealing byte pattern."""
        counter = itertools.count(1)

        def read(_address, _extension, p_buffer):
            base = next(counter) & 0xFF
            value = bytes(((base + i) & 0xFF) for i in range(element_size))
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

    session.reads.clear()
    frames = session.trigger()

    assert len(frames) == 3, 'one frame per non-empty ODT'

    read_index = 0
    for odt, (pdu_id, frame) in enumerate(frames):
        header = expected_identification_field(ident, first_pid, odt, 1, byte_order)

        assert tuple(frame[0:len(header)]) == header, 'ODT {} identification field'.format(odt)
        assert len(frame) == len(header) + sum(sizes), 'ODT {} length'.format(odt)

        offset = len(header)
        for size in sizes:
            for _ in range(size // element_size):
                assert bytes(frame[offset:offset + element_size]) == session.reads[read_index], \
                    'ODT {} element at offset {}'.format(odt, offset)
                offset += element_size
                read_index += 1


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
    assert session.exchange((0xE1, 0xFF, max_entry_size + 1, 0x00) +
                            tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))[0:2] == (0xFE, 0x22), \
        'one byte past it is refused'


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

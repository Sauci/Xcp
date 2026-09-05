#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Decoding the identification field of a received stimulation frame (SP3 Task 6, DD44).

Xcp_DaqReadIdentificationField is the exact inverse of Xcp_DaqWriteIdentificationField
(source/Xcp_DaqRuntime.c): given the frame a master sent, it answers which DAQ list and which ODT
that frame addresses, and at which byte its payload begins.

Every case below asserts the decoded *offset*, not only the decoded list and ODT numbers, and that
is the whole point of this file. A payload offset wrong by one, two or four bytes fails nowhere in
the protocol -- it applies the master's data to the wrong addresses, silently. A test that checked
only the list and the ODT would pass under exactly that defect, so each frame here carries a
sentinel byte at the first payload position with different bytes on either side of it: both
`offset == <number>` and `frame[offset] == PAYLOAD` have to hold, and the second fails for
offset +/- 1 as well.

The offsets themselves come from 1.1/1.1.2.1 (identification field) and 1.1/1.1.2.2 (timestamp
field), and are the ones Xcp_DaqWriteIdentificationField already writes on the transmit side.
"""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect

# The first payload byte of every frame in this file, and its neighbours. All three differ, and
# none of them ever appears in an identification or timestamp field built below, so an offset off
# by one lands on a byte that is not PAYLOAD.
PAYLOAD = 0x5A
TRAILER = 0xA5
FILLER = 0xEE


def decode(handle, frame, rx_pdu_id):
    """Calls Xcp_DaqReadIdentificationField on `frame` and returns (result, daq, odt, offset).

    The three out-parameters are seeded with values no configuration here can produce, so a
    decoder that returns E_OK without writing one of them fails on the value rather than passing
    on whatever the stack happened to hold.
    """
    daq_list_number = handle.ffi.new('uint16 *', 0xFFFF)
    odt_number = handle.ffi.new('uint8 *', 0xFF)
    offset = handle.ffi.new('uint8 *', 0xFF)
    result = handle.lib.Xcp_DaqReadIdentificationField(handle.get_pdu_info(frame), rx_pdu_id,
                                                       daq_list_number, odt_number, offset)
    return result, daq_list_number[0], odt_number[0], offset[0]


def set_daq_list_mode(handle, daq_list=0, mode=0x00, channel=0, prescaler=1, priority=0,
                      byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_LIST_MODE, asserting the slave accepted it. The stored mode bits are what the
    decoder reads for PID_OFF and TIMESTAMP, so a refused request must not be mistaken for a
    configured one."""
    handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xE0, mode) + tuple(u16_to_array(daq_list, byte_order)) +
                                        tuple(u16_to_array(channel, byte_order)) +
                                        (prescaler, priority)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0x00] == 0xFF, \
        'SET_DAQ_LIST_MODE was refused, so the stored mode is not what this test assumes'


def two_stimulation_lists(identification_field_type='ABSOLUTE'):
    """Two 2-ODT stimulation lists, so DAQ2's FIRST_PID is 2 and the ABSOLUTE reverse lookup has to
    discriminate between them rather than always answering list 0."""
    return DefaultConfig(identification_field_type=identification_field_type,
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=2, max_odt_entries=2),
                               daq(name='DAQ2', type='DAQ_STIM', max_odt=2, max_odt_entries=2)))


# The identification field addressing DAQ list 1, ODT 1, under each of the four types, and the
# payload offset that follows from it. Exactly the four layouts Xcp_DaqWriteIdentificationField
# writes: [absolute PID], [odt, daq(u8)], [odt, daq(u16)], [odt, fill, daq(u16)]. DAQ2 has
# FIRST_PID 2, so its ODT 1 is absolute PID 3.
_identification_cases = (
    ('ABSOLUTE', (0x03,), 1),
    ('RELATIVE_BYTE', (0x01, 0x01), 2),
    ('RELATIVE_WORD', (0x01, 0x01, 0x00), 3),
    ('RELATIVE_WORD_ALIGNED', (0x01, FILLER, 0x01, 0x00), 4),
)


@pytest.mark.parametrize('identification, field, expected_offset', _identification_cases)
def test_the_payload_begins_after_the_identification_field(identification, field, expected_offset):
    """1.1/1.1.2.1, and the inverse of Xcp_DaqWriteIdentificationField's four arms.

    The FILL byte of RELATIVE_WORD_ALIGNED is given a value here that is neither the list number
    nor the ODT number nor the payload: 1.1.2.1 gives it no defined value, so a decoder that read
    the DAQ list number from the wrong side of it would decode list 0xEE rather than accidentally
    still decoding 1.
    """
    config = two_stimulation_lists(identification)
    handle = XcpTest(config)
    connect(handle)
    frame = field + (PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number) == (1, 1)
    assert offset == expected_offset
    assert frame[offset] == PAYLOAD, 'the offset is where the payload actually starts'


@pytest.mark.parametrize('pid, expected', ((0x00, (0, 0)), (0x01, (0, 1)),
                                           (0x02, (1, 0)), (0x03, (1, 1))))
def test_an_absolute_pid_resolves_to_the_list_holding_it(pid, expected):
    """1.1/1.6.4.1.1.4: absolute_ODT_NUMBER = FIRST_PID(list) + relative ODT_NUMBER, so the reverse
    is a scan for the list whose [FIRST_PID, FIRST_PID + maxOdt) range contains the PID.

    Exhaustive over both lists rather than one case each: a decoder that always answered the first
    allocated list passes the (1, 1) case's siblings above only by luck, and one that always
    answered the last would pass that case and fail here.
    """
    config = two_stimulation_lists()
    handle = XcpTest(config)
    connect(handle)

    result, daq_list_number, odt_number, offset = decode(handle, (pid, PAYLOAD, TRAILER),
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number) == expected
    assert offset == 1


def test_an_absolute_pid_past_every_allocated_list_is_refused():
    """Two 2-ODT lists number absolute ODTs 0..3; 4 belongs to no list, and a decoder that clamped
    or wrapped would hand the caller a list it must not stimulate."""
    config = two_stimulation_lists()
    handle = XcpTest(config)
    connect(handle)

    result, _, _, _ = decode(handle, (0x04, PAYLOAD, TRAILER),
                             config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_NOT_OK')


@pytest.mark.parametrize('identification, field', (
        ('RELATIVE_BYTE', (0x00, 0x02)),
        ('RELATIVE_WORD', (0x00, 0x02, 0x00)),
        ('RELATIVE_WORD_ALIGNED', (0x00, FILLER, 0x02, 0x00))))
def test_a_relative_field_naming_an_unallocated_list_is_refused(identification, field):
    """The explicit list number needs the same bound the ABSOLUTE scan applies implicitly: list 2
    does not exist in a two-list configuration."""
    config = two_stimulation_lists(identification)
    handle = XcpTest(config)
    connect(handle)

    result, _, _, _ = decode(handle, field + (PAYLOAD, TRAILER),
                             config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_NOT_OK')


@pytest.mark.parametrize('identification, field', (
        ('RELATIVE_BYTE', (0x02, 0x01)),
        ('RELATIVE_WORD', (0x02, 0x01, 0x00)),
        ('RELATIVE_WORD_ALIGNED', (0x02, FILLER, 0x01, 0x00))))
def test_a_relative_field_naming_an_odt_the_list_does_not_have_is_refused(identification, field):
    """A 2-ODT list has ODTs 0 and 1. ODT 2 addresses storage that does not exist, and the caller
    would index the ODT array with it."""
    config = two_stimulation_lists(identification)
    handle = XcpTest(config)
    connect(handle)

    result, _, _, _ = decode(handle, field + (PAYLOAD, TRAILER),
                             config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_NOT_OK')


def test_the_word_list_number_follows_the_configured_byte_order():
    """byteOrder governs the protocol's own multi-byte fields, and the DAQ list number of the two
    WORD forms is one -- Xcp_DaqWriteIdentificationField encodes it with
    Xcp_CopyFromU16WithOrder, so reading it back with a fixed-endian copy decodes list 0x0100
    rather than list 1 under BIG_ENDIAN."""
    config = DefaultConfig(identification_field_type='RELATIVE_WORD', byte_order='BIG_ENDIAN',
                           daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=2, max_odt_entries=2),
                                 daq(name='DAQ2', type='DAQ_STIM', max_odt=2, max_odt_entries=2)))
    handle = XcpTest(config)
    connect(handle)
    frame = (0x01, 0x00, 0x01, PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number) == (1, 1)
    assert offset == 3
    assert frame[offset] == PAYLOAD


def pid_off_config():
    """A single stimulation list. PID_OFF needs an ABSOLUTE identification type, exactly one ODT
    and a PDU no other list shares (Xcp_DaqListTxPduIsExclusive, source/Xcp_Daq.c) -- every list in
    this harness maps to XCP_PDU_ID_TRANSMIT, so a second list would make SET_DAQ_LIST_MODE refuse
    the bit."""
    return DefaultConfig(identification_field_type='ABSOLUTE',
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=1, max_odt_entries=1),))


def test_pid_off_takes_the_list_from_the_receiving_pdu_and_starts_the_payload_at_zero():
    """1.1/1.1.2.1: with the identification field turned off 'the unambiguous identification has to
    be done on the level of the Transport Layer', which for this module is the PDU the frame
    arrived on. There is no field to skip, so the payload starts at byte 0."""
    config = pid_off_config()
    handle = XcpTest(config)
    connect(handle)
    set_daq_list_mode(handle, mode=0x20)
    frame = (PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number, offset) == (0, 0, 0)
    assert frame[offset] == PAYLOAD


def test_the_same_frame_without_pid_off_is_read_as_an_identification_field():
    """The negative half of the case above, and what makes it about PID_OFF rather than about the
    decoder ignoring the identification field unconditionally: the identical frame, on the
    identical PDU, against the identical configuration with only the stored mode bit cleared, has
    its first byte read as an absolute PID -- and 0x5A names no ODT of a one-ODT list."""
    config = pid_off_config()
    handle = XcpTest(config)
    connect(handle)

    result, _, _, _ = decode(handle, (PAYLOAD, TRAILER), config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_NOT_OK')


def timestamped_config(size, identification_field_type='ABSOLUTE'):
    return DefaultConfig(timestamp=timestamp(size=size),
                         identification_field_type=identification_field_type,
                         daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=2, max_odt_entries=1),))


# DD44. 1.1/1.1.2.2: 'The TIMESTAMP flag can be used as well for DIRECTION = DAQ as for
# DIRECTION = STIM', and for stimulation the master echoes back the slave's own clock value 'in
# the DTO Packet for the first ODT of the DAQ cycle' -- so the field is present on ODT 0 and on no
# other ODT, exactly as Diagram 10 shows for the acquisition direction.
#
# The two tests below are a pair, on one configuration, and it is the pair that pins DD44: ODT 0
# carrying a timestamp and ODT 1 not carrying one. Either alone is satisfied by an implementation
# that adds the width unconditionally, or by one that never adds it at all. They are two tests
# rather than one so that a decoder failing only one half says which half.
#
# Both are parametrised over all three widths, so a decoder that hardcoded one of them fails. That
# does not by itself separate Xcp_TimestampWireSize(timestampType) from the XCP_DAQ_TIMESTAMP_SIZE
# macro -- with a single configuration the two are equal by construction -- which is what the
# MultiConfig test further down is for.
_timestamp_widths = tuple((size, wire) for size, wire in timestamp_wire_size.items()
                          if size is not None)


@pytest.mark.parametrize('size, width', _timestamp_widths)
def test_the_timestamp_of_odt_zero_is_counted_into_the_payload_offset(size, width):
    """DD44, first half: on ODT 0 of a timestamped list the payload starts after the identification
    field AND the timestamp."""
    config = timestamped_config(size)
    handle = XcpTest(config)
    connect(handle)
    set_daq_list_mode(handle, mode=0x10)
    frame = (0x00,) + (FILLER,) * width + (PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number, offset) == (0, 0, 1 + width)
    assert frame[offset] == PAYLOAD, 'ODT 0 skips the identification field and the timestamp'


@pytest.mark.parametrize('size, width', _timestamp_widths)
def test_no_timestamp_is_counted_into_a_later_odts_payload_offset(size, width):
    """DD44, second half: the same list, in the same timestamped mode, carries no timestamp on
    ODT 1, so its payload starts directly after the identification field. `width` is unused in the
    assertion on purpose -- that is the point -- and is kept in the parametrisation so this runs
    against exactly the configurations its ODT-0 sibling does."""
    config = timestamped_config(size)
    handle = XcpTest(config)
    connect(handle)
    set_daq_list_mode(handle, mode=0x10)
    frame = (0x01, PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number, offset) == (0, 1, 1)
    assert frame[offset] == PAYLOAD, 'ODT 1 skips the identification field only'


def test_no_timestamp_is_skipped_when_the_mode_bit_is_off():
    """The list is configured with a clock but SET_DAQ_LIST_MODE never enables TIMESTAMP, so its
    ODT 0 carries no timestamp field either. A decoder keyed on the build's configuration rather
    than on the list's stored mode would skip four bytes of payload here."""
    config = timestamped_config('DWORD')
    handle = XcpTest(config)
    connect(handle)
    frame = (0x00, PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number, offset) == (0, 0, 1)
    assert frame[offset] == PAYLOAD


def test_the_timestamp_width_is_the_running_configurations_not_the_builds_maximum():
    """1.1/1.1.2.2: 'The master has to use the same Type of Timestamp Field when transferring STIM
    Packets to the slave' as the slave publishes through GET_DAQ_RESOLUTION_INFO -- which is the
    running configuration's timestampType, not a build-wide maximum.

    XCP_DAQ_TIMESTAMP_SIZE folds every configuration in the generated file to the largest, so here
    it is 4 while configuration 0's own wire size is 1. That is the one shape that tells
    Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType) from the macro, and it is the same
    distinction Xcp_DaqSampleOdt's own comment records on the transmit side.
    """
    config = MultiConfig(timestamped_config('BYTE'), DefaultConfig(timestamp=timestamp(size='DWORD')))
    handle = XcpTest(config, configuration_index=0)
    connect(handle)
    assert handle.define('XCP_DAQ_TIMESTAMP_SIZE') == 4, \
        'the build-wide maximum has to differ from configuration 0, or this proves nothing'
    set_daq_list_mode(handle, mode=0x10)
    frame = (0x00, FILLER, PAYLOAD, TRAILER)

    result, daq_list_number, odt_number, offset = decode(handle, frame,
                                                         config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number, offset) == (0, 0, 2)
    assert frame[offset] == PAYLOAD


@pytest.mark.parametrize('identification, frame', (
        ('RELATIVE_BYTE', (0x01,)),
        ('RELATIVE_WORD', (0x01, 0x01)),
        ('RELATIVE_WORD_ALIGNED', (0x01, FILLER, 0x01))))
def test_a_frame_too_short_to_hold_its_identification_field_is_refused(identification, frame):
    """One byte short of the field the configured type says is there. The decoder must not read
    past SduLength to find a list number, and the caller must not be handed an offset larger than
    the frame it would then subtract from."""
    config = two_stimulation_lists(identification)
    handle = XcpTest(config)
    connect(handle)

    result, _, _, _ = decode(handle, frame, config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_NOT_OK')


def test_a_frame_too_short_to_hold_its_timestamp_is_refused():
    """The identification field fits, the timestamp ODT 0 must carry does not. The offset would
    otherwise point past the end of the frame, and the payload length the caller computes from it
    would underflow."""
    config = timestamped_config('DWORD')
    handle = XcpTest(config)
    connect(handle)
    set_daq_list_mode(handle, mode=0x10)

    result, _, _, _ = decode(handle, (0x00, FILLER, FILLER, FILLER),
                             config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_NOT_OK')


def test_a_frame_holding_its_fields_and_no_payload_is_accepted():
    """The boundary the test above sits one byte below: a frame that is exactly its identification
    field and its timestamp names a list and an ODT, and carries an empty payload. Rejecting a
    payload too short for the ODT's entries is DD39's, on the caller's side, not this decoder's."""
    config = timestamped_config('DWORD')
    handle = XcpTest(config)
    connect(handle)
    set_daq_list_mode(handle, mode=0x10)

    result, daq_list_number, odt_number, offset = decode(
            handle, (0x00, FILLER, FILLER, FILLER, FILLER), config.default_daq_dto_pdu_mapping)

    assert result == handle.define('E_OK')
    assert (daq_list_number, odt_number, offset) == (0, 0, 5)

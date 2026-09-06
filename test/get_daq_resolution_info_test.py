#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def info(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD9,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(**kwargs))
    connect(handle)
    return handle


def exchange(handle, request, length=2):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def write_daq(handle, size, address=0x1000):
    """SET_DAQ_PTR to (list 0, ODT 0, entry 0) and one WRITE_DAQ of `size` bytes, returning the
    response's first two bytes.

    The pointer is repositioned before every attempt rather than once for the sequence: WRITE_DAQ
    post-increments it on success and the list has one entry, so a later attempt without a fresh
    SET_DAQ_PTR would be refused for pointer validity -- with the same ERR_OUT_OF_RANGE the size
    checks answer, and for a reason that has nothing to do with the size under test."""
    assert exchange(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0] == 0xFF, \
        'SET_DAQ_PTR was refused'
    return exchange(handle, (0xE1, 0xFF, size, 0x00) +
                    tuple(u32_to_array(address, 'LITTLE_ENDIAN')))


@pytest.mark.parametrize('ag', address_granularities)
def test_granularity_is_the_address_granularity_element_size(ag):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5: the possible values for
    GRANULARITY_ODT_ENTRY_SIZE_x are {1,2,4,8}. Exhaustive over all three address granularities
    this slave can be configured with, so a wrong or hard-coded granularity surfaces here."""
    handle = daq_handle(address_granularity=ag)

    assert info(handle)[1] == element_size_from_address_granularity(ag)
    assert info(handle)[1] in (1, 2, 4, 8)


@pytest.mark.parametrize('max_dto, ident, expected', ((8, 'ABSOLUTE', 7),
                                                      (8, 'RELATIVE_BYTE', 6),
                                                      (8, 'RELATIVE_WORD', 5),
                                                      (8, 'RELATIVE_WORD_ALIGNED', 4),
                                                      (64, 'ABSOLUTE', 63),
                                                      (256, 'ABSOLUTE', 255)))
def test_max_odt_entry_size_is_what_a_dto_leaves_after_the_identification_field(max_dto, ident,
                                                                               expected):
    """MAX_ODT_ENTRY_SIZE_DAQ is Xcp_Ptr->general->odtEntrySizeDaq -- the exact same derived value
    WRITE_DAQ (Task 7) checks a new ODT entry's size against
    (source/Xcp_Daq.c:Xcp_DTOCmdDaqWriteDaq, "size > Xcp_Ptr->general->odtEntrySizeDaq"). Reading
    the same field both places is what keeps the two commands in agreement: whatever this command
    advertises as the ceiling is exactly what WRITE_DAQ enforces as the ceiling, across every
    MAX_DTO / identification field type combination (Task 19's acceptance matrix exercises this
    pairing directly). Varied here across both axes so the reported byte is distinctive rather
    than incidentally correct."""
    handle = daq_handle(max_dto=max_dto, identification_field_type=ident)

    assert info(handle)[2] == expected


def test_stim_fields_are_zero_for_a_build_that_cannot_receive_stimulation():
    """GRANULARITY_ODT_ENTRY_SIZE_STIM (byte 3) and MAX_ODT_ENTRY_SIZE_STIM (byte 4) are both zero
    for a DAQ-only configuration. Not "not implemented yet" -- SP3 implements stimulation, and the
    sibling test below is what this slave reports once a configuration can receive. Zero is what a
    slave that stimulates nothing has to say about the size and granularity of a stimulation ODT
    entry it will never accept, and it is what the ASAP2 grammar says by making its "STIM" block
    optional (1.1/1.6.4.1.2.5, whose GRANULARITY_ODT_ENTRY_SIZE_x enumeration is {1,2,4,8}).

    Not vacuous zero checks: connect(), called by daq_handle() immediately before info(), leaves
    nonzero bytes at both of these exact buffer offsets in Xcp_CTOCmdStdConnect's own response
    (source/Xcp_Std.c) -- MAX_CTO (0x08 by default) at byte 3, and MAX_DTO's low byte (0x08 by
    default, little endian) at byte 4. Since Xcp_FinalizeResPacket only fills bytes from its start
    index onward, a deleted assignment on either byte would leave that 0x08 rather than 0x00, so
    both assertions are load-bearing under the default configuration this test uses. Confirmed by
    mutation -- see task-14-report.md.

    It is load-bearing a second way now, which the paragraph above does not cover: byte 3 is no
    longer a constant, so a granularity reported unconditionally -- without asking whether this
    configuration can receive at all -- would answer 1 here rather than 0. Also confirmed by
    mutation; see task-9-report.md."""
    handle = daq_handle()

    assert info(handle)[3] == 0
    assert info(handle)[4] == 0


@pytest.mark.parametrize('ag', address_granularities)
def test_stim_fields_report_the_same_limits_write_daq_enforces_on_a_stim_entry(ag):
    """The DIRECTION = STIM half of the two tests above, on a configuration that can receive.

    1.1/1.6.4.1.2.5 reports the two directions as four separate bytes because it allows a slave
    whose directions differ. This one's do not, and the reason is structural rather than a
    coincidence worth reporting twice (DD47): WRITE_DAQ and WRITE_DAQ_MULTIPLE share one
    entry-application routine, Xcp_DaqApplyOdtEntry (source/Xcp_Daq.c), and it refuses an entry
    whose size is not a multiple of the address granularity or is larger than odtEntrySizeDaq
    without consulting the list's direction at all -- an entry does not know, when it is written,
    which direction SET_DAQ_LIST_MODE will later put its list into.

    **The last two assertions are what make that demonstrated rather than inferred.** The first
    three compare byte 3 against byte 1 and byte 4 against byte 2, which says the two directions
    agree but leans on the DAQ half being pinned by a test that runs on a DAQ-only list -- sound,
    since the routine takes no direction, but a transitive argument. So this list, which is
    DAQ_STIM, is offered the two entry sizes its own reported bytes forbid and the one they permit:

    - a size one past the reported granularity is refused, **at the two granularities where that
      constraint has content**. At BYTE there is no such size -- every integer is a multiple of 1
      -- so the refusal is asserted for WORD and DWORD, and the acceptance below covers all three.
      Both refused sizes stay well under MAX_ODT_ENTRY_SIZE_STIM (3 and 5, against 7), so the
      granularity check is unambiguously what answers them.
    - a size one past the reported maximum is refused at every granularity: 8 is a multiple of 1,
      2 and 4 alike, so only the size check can be refusing it.
    - a size of exactly the reported granularity is accepted, which keeps the two refusals from
      being satisfied by a slave that had simply stopped accepting entries.

    ERR_OUT_OF_RANGE (0x22) is pinned rather than "some error": 1.7.3.2.4 gives its prescribed
    master action as "retry other parameter", which is the honest answer to a size this slave
    cannot take, and the neighbouring refusals in this routine answer ERR_DAQ_ACTIVE,
    ERR_WRITE_PROTECTED and ERR_DAQ_CONFIG instead.

    daq_acceptance_test.py::test_write_daq_accepts_exactly_what_get_daq_resolution_info_promises is
    the DAQ direction's version of these three, sweeping MAX_DTO and the identification field type
    as well. This is deliberately the narrower twin rather than a second sweep: what is new here is
    that the list is DAQ_STIM and the bytes being honoured are 3 and 4, not that the routine's
    arithmetic works -- which that test already establishes across a far wider space than a STIM
    list adds anything to.

    Asserted against the DAQ bytes of the same response rather than against fresh literals: the
    claim is that the two directions agree, and two independently written literals would still
    agree if the module had stopped deriving one from the other. The non-zero assertions are what
    keep that from being satisfied by a slave that reported 0 for all four.

    Swept over the address granularity for byte 3, exactly as the DAQ granularity test above is:
    a hard-coded 1 would pass at BYTE and nowhere else.
    """
    handle = XcpTest(DefaultConfig(address_granularity=ag,
                                   daqs=(daq(name='DAQ1', type='DAQ_STIM'),)))
    connect(handle)

    response = info(handle)

    assert response[3] == element_size_from_address_granularity(ag)
    assert response[3] == response[1], \
        'one entry-application routine, one granularity, both directions'
    assert response[4] == response[2], 'and one MAX_ODT_ENTRY_SIZE, for the same reason'
    assert response[3] != 0 and response[4] != 0, \
        'a configuration that can receive must not report a DAQ-only build\'s zeros'

    if response[3] > 1:
        assert write_daq(handle, response[3] + 1) == (0xFE, 0x22), \
            'a STIM entry whose size is not a multiple of the reported granularity is refused'
    assert write_daq(handle, response[4] + 1) == (0xFE, 0x22), \
        'a STIM entry larger than the reported MAX_ODT_ENTRY_SIZE_STIM is refused'
    assert write_daq(handle, response[3])[0] == 0xFF, \
        'and one of exactly the reported granularity is accepted'


def test_timestamp_fields_are_invalid_because_timestamps_are_unsupported():
    """1.1/1.6.4.1.2.5: "If the slave doesn't support a time stamped mode, the parameters
    TIMESTAMP_MODE and TIMESTAMP_TICKS are invalid". TIMESTAMP_SUPPORTED (DAQ_PROPERTIES bit 4,
    GET_DAQ_PROCESSOR_INFO) is clear, so 0/0x0000 here is the specification-mandated way to say
    "invalid", not a placeholder for unimplemented work.

    TIMESTAMP_TICKS (bytes 6:8) is load-bearing under this default LITTLE_ENDIAN configuration:
    connect() leaves XCP_PROTOCOL_LAYER_VERSION and XCP_TRANSPORT_LAYER_VERSION (both 0x01,
    source/Xcp_Std.c) at bytes 6 and 7 of the same buffer, so a deleted
    Xcp_CopyFromU16WithOrder call would leave (0x01, 0x01) instead of (0x00, 0x00).

    TIMESTAMP_MODE (byte 5) is NOT load-bearing here: connect()'s own response leaves MAX_DTO's
    high byte at byte 5, which is 0x00 under little-endian MAX_DTO=8 (this test's configuration)
    before GET_DAQ_RESOLUTION_INFO ever runs -- a deleted TIMESTAMP_MODE assignment would coincide
    with the expected 0x00 and this assertion would not catch it. See the byte-order-agnostic
    sibling test below for the assertion that actually is load-bearing on byte 5. Confirmed by
    mutation -- see task-14-report.md."""
    handle = daq_handle()

    assert info(handle)[5] == 0
    assert info(handle)[6:8] == (0x00, 0x00)


def test_timestamp_mode_is_invalid_regardless_of_byte_order():
    """The load-bearing counterpart to TIMESTAMP_MODE's check above. Xcp_CopyFromU16WithOrder
    (source/Xcp.c) places MAX_DTO's low byte at byte 5 under BIG_ENDIAN instead of the high byte,
    so connect()'s leftover there becomes MAX_DTO's low byte -- 0x08 under this test's default
    MAX_DTO=8, nonzero. A deleted TIMESTAMP_MODE assignment would leave that 0x08 rather than the
    expected 0x00, so this variant is the one that actually proves the assignment exists.
    Confirmed by mutation -- see task-14-report.md."""
    handle = daq_handle(byte_order='BIG_ENDIAN')

    assert info(handle)[5] == 0


@pytest.mark.parametrize('size', timestamp_sizes)
def test_timestamp_mode_encodes_the_configured_size_on_the_wire(size):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5: TIMESTAMP_MODE bits 2:0 carry the
    size as 0, 1, 2 or 4 -- 3 is "Not allowed". Xcp_TimestampTypeType's enumerators are implicit, so
    FOUR_BYTE is 3; writing the enumerator into these bits would emit exactly the forbidden value.
    This test is the reason the Xcp_TimestampWireSize mapping exists.

    The expected wire size comes from parameter.py's timestamp_wire_size table rather than a fresh
    literal tuple. Task 1 added that table (and timestamp_sizes) already anticipating this test,
    but nothing used it until now -- using it here is the first consumer, and avoids adding a
    sixth independent copy of the BYTE/WORD/DWORD -> 1/2/4 map that already exists five times over
    (CMakeLists.txt, script/header_cfg.h.jinja2, script/source_cfg.c.jinja2, test/conftest.py, and
    a literal tuple in test/daq_configuration_test.py)."""
    handle = daq_handle(timestamp=timestamp(size=size, unit='TIMESTAMP_UNIT_10US', ticks=250))

    response = info(handle)

    mode = response[5]
    assert (mode & 0x07) == timestamp_wire_size[size]
    assert (mode & 0x08) == 0x00, 'TIMESTAMP_FIXED must be clear: the master may switch the timestamp off'
    assert ((mode >> 4) & 0x0F) == handle.lib.TIMESTAMP_UNIT_10US

    ticks = payload_to_array(bytearray(response[6:8]), 1, 2, 'LITTLE_ENDIAN')[0]
    assert ticks == 250

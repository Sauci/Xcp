#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Per-segment checksum configuration: XCP part 2 - Protocol Layer Specification 1.1/2.1's AML
declares a CHECKSUM block inside each SEGMENT, and this module now honours one for a BUILD_CHECKSUM
whose MTA falls inside that segment.

Resolution is observable from the wire alone: 1.1/1.6.1.2.9's positive response carries the checksum
type in byte 1, so a segment declaring XCP_CRC_16 against a global XCP_ADD_11 answers 0x07 when the
MTA is inside it and 0x01 when it is not. No test here reaches into the module."""

from .parameter import *
from .conftest import XcpTest

SEGMENT_ADDRESS = 0x00400000
SEGMENT_LENGTH = 0x1000
OUTSIDE_ADDRESS = 0x00500000

XCP_ADD_11_ON_THE_WIRE = 0x01
XCP_CRC_16_ON_THE_WIRE = 0x07


def build_checksum(handle, mta, block_size, byte_order='LITTLE_ENDIAN'):
    """CONNECT, SET_MTA, BUILD_CHECKSUM -- returns the eight response bytes."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
        (0xF6, 0x00, 0x00, 0x00, *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
        (0xF3, 0x00, 0x00, 0x00, *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])


def reading_zeros(handle):
    """Content is irrelevant to every test in this file -- what is asserted is which CONFIGURATION
    produced the answer, which the response's type byte reports directly."""
    def read_slave_memory(_p_address, _extension, p_buffer):
        p_buffer[0] = 0x00
        return None

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory


def test_a_segment_checksum_type_overrides_the_global_one():
    """The MTA is inside a segment declaring XCP_CRC_16, while protocol_layer declares XCP_ADD_11."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum('XCP_CRC_16'))]))
    reading_zeros(handle)

    response = build_checksum(handle, SEGMENT_ADDRESS, 0x04)

    assert response[0] == 0xFF
    assert response[1] == XCP_CRC_16_ON_THE_WIRE, "the segment's type, not protocol_layer's"


def test_an_mta_in_no_segment_uses_the_global_checksum_type():
    """DD143's invariant, from the other side: an address outside every configured segment behaves
    exactly as it did before per-segment configuration existed. This is also the answer to 'the MTA
    is in no configured segment', which neither 1.0 nor 1.1 defines and which DD115 deferred this
    whole feature over -- keeping the global makes the question answer itself."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum('XCP_CRC_16'))]))
    reading_zeros(handle)

    response = build_checksum(handle, OUTSIDE_ADDRESS, 0x04)

    assert response[1] == XCP_ADD_11_ON_THE_WIRE, 'outside every segment, the global applies'


def test_a_segment_declaring_no_checksum_uses_the_global_one():
    """The other half of the invariant: a configured segment that declares no CHECKSUM block at all
    changes nothing, which is every segment in every configuration written before today."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH)]))
    reading_zeros(handle)

    response = build_checksum(handle, SEGMENT_ADDRESS, 0x04)

    assert response[1] == XCP_ADD_11_ON_THE_WIRE


def test_a_segment_declaring_only_a_type_takes_its_bound_from_the_global():
    """The partial override, and the case that would catch the three fields being read as a unit
    rather than independently. The segment declares a type and no bound; a block size above nothing
    in particular but within the global bound must therefore succeed, carrying the segment's type."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   checksum_max_block_size=0x40,
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum('XCP_CRC_16'))]))
    reading_zeros(handle)

    response = build_checksum(handle, SEGMENT_ADDRESS, 0x20)

    assert response[0] == 0xFF, 'the global bound of 0x40 admits a block of 0x20'
    assert response[1] == XCP_CRC_16_ON_THE_WIRE, "and the segment's type still applies"


def test_an_out_of_range_refusal_reports_the_bound_that_applied():
    """DD147. 1.1/1.1.3.3 requires BUILD_CHECKSUM's ERR_OUT_OF_RANGE to carry the maximum allowed
    block size, which D6 added. With per-segment bounds it must be the bound that actually applied:
    a slave that refuses against a segment's bound and then names the global one tells the master a
    limit that does not apply to the address it asked about -- worse than carrying no payload at
    all, because it is confidently wrong and nothing on the wire reveals it.

    The segment's bound here is deliberately SMALLER than the global, so the two values differ and
    the wrong one is visible. A test asserting only the error code would pass either way."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   checksum_max_block_size=0x1000,
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum(
                                                         'XCP_CRC_16',
                                                         checksum_max_block_size=0x10))]))
    reading_zeros(handle)

    response = build_checksum(handle, SEGMENT_ADDRESS, 0x20)

    assert response[0:2] == (0xFE, 0x22), 'ERR_OUT_OF_RANGE'
    assert u32_from_array(bytearray(response[4:8]), 'LITTLE_ENDIAN') == 0x10, \
        "the segment's bound, not the global 0x1000"


def test_a_segment_bound_does_not_leak_to_an_address_outside_it():
    """The mirror of the test above, and the one that would catch the resolved bound being cached or
    applied globally: the same request that the segment refuses must succeed outside it, where the
    larger global bound is in force."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   checksum_max_block_size=0x1000,
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum(
                                                         'XCP_CRC_16',
                                                         checksum_max_block_size=0x10))]))
    reading_zeros(handle)

    response = build_checksum(handle, OUTSIDE_ADDRESS, 0x20)

    assert response[0] == 0xFF, 'outside the segment the global bound of 0x1000 admits 0x20'
    assert response[1] == XCP_ADD_11_ON_THE_WIRE

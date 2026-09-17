#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Per-segment checksum configuration: XCP part 2 - Protocol Layer Specification 1.1/2.1's AML
declares a CHECKSUM block inside each SEGMENT, and this module now honours one for a BUILD_CHECKSUM
whose MTA falls inside that segment.

Resolution is observable from the wire alone: 1.1/1.6.1.2.9's positive response carries the checksum
type in byte 1, so a segment declaring XCP_CRC_16 against a global XCP_ADD_11 answers 0x07 when the
MTA is inside it and 0x01 when it is not. No test here reaches into the module."""

import pytest

from jinja2.exceptions import UndefinedError

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


def test_a_block_spanning_out_of_its_segment_uses_that_segment_configuration():
    """DD145. The block starts inside the segment and runs past its end. The segment containing the
    START decides for the whole of it -- 1.1/1.6.1.2.9 calls it "the memory block that is defined by
    the MTA and Block size", and the MTA is what locates it. Pinned so the decision cannot drift
    silently: the alternative reading, refusing a spanning block, would change behaviour in builds
    with no per-segment overrides at all."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   checksum_max_block_size=0x10000,
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=0x10,
                                                     checksum=segment_checksum('XCP_CRC_16'))]))
    reading_zeros(handle)

    # 0x40 elements from the segment's base, against a segment only 0x10 long.
    response = build_checksum(handle, SEGMENT_ADDRESS, 0x40)

    assert response[0] == 0xFF
    assert response[1] == XCP_CRC_16_ON_THE_WIRE, "the starting segment's type covers the whole block"


def test_overlapping_segments_resolve_to_the_first_declared():
    """DD144. config/xcp.schema.json does not forbid overlap, and declaration order is the only
    ordering an integrator controls, so first match is the rule and this is what makes it a promise
    rather than an artefact of loop direction."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   segments=[segment(name='FIRST',
                                                     address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum('XCP_CRC_16')),
                                             segment(name='SECOND',
                                                     address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum('XCP_ADD_11'))]))
    reading_zeros(handle)

    response = build_checksum(handle, SEGMENT_ADDRESS, 0x04)

    assert response[1] == XCP_CRC_16_ON_THE_WIRE, "FIRST is declared first, so FIRST wins"


def test_a_segment_callback_is_used_in_place_of_the_global_one():
    """A segment declaring XCP_USER_DEFINED with its own callback must invoke THAT callback. Asserted
    on which mock was called rather than on the resulting checksum, since both callbacks could
    return the same value and the test would then prove nothing."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_ADD_11',
                                   user_defined_checksum_function='Xcp_UserDefinedChecksumFunction',
                                   segments=[segment(address=SEGMENT_ADDRESS,
                                                     length=SEGMENT_LENGTH,
                                                     checksum=segment_checksum('XCP_USER_DEFINED'))]))
    reading_zeros(handle)

    def xcp_user_defined_checksum_function(_p_lower_address, p_upper_address, p_checksum):
        p_checksum[0] = 0x12345678
        return p_upper_address

    handle.xcp_user_defined_checksum_function.side_effect = xcp_user_defined_checksum_function

    response = build_checksum(handle, SEGMENT_ADDRESS, 0x04)

    assert response[1] == 0xFF, 'XCP_USER_DEFINED reports 0xFF on the wire'
    handle.xcp_user_defined_checksum_function.assert_called_once()


def test_generation_refuses_a_segment_user_defined_checksum_with_no_callback_anywhere():
    """DD148. The segment declares XCP_USER_DEFINED and there is no callback on it or globally, so
    Xcp_DTOCmdStdBuildChecksum would call NULL_PTR for any MTA inside it."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                              user_defined_checksum_function=None,
                              segments=[segment(address=SEGMENT_ADDRESS,
                                                checksum=segment_checksum('XCP_USER_DEFINED'))]))


def test_generation_accepts_a_segment_user_defined_checksum_falling_back_to_the_global_callback():
    """The companion the refusal needs. The guard is a conjunction over the fallback, not a check on
    the segment alone: a segment declaring the type and leaving the callback global is legitimate,
    and every guard in that template raises the identical "'raise' is undefined", so only the pair
    identifies which one fired."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                          user_defined_checksum_function='Xcp_UserDefinedChecksumFunction',
                          segments=[segment(address=SEGMENT_ADDRESS,
                                            checksum=segment_checksum('XCP_USER_DEFINED'))]))


def test_generation_refuses_a_segment_block_size_whose_product_with_granularity_overflows():
    """DD148, the second guard: the bound DD119 applies to protocol_layer.checksum_max_block_size
    must not be escapable by a per-segment override. DWORD granularity, so 0x40000000 * 4 is the
    first product exceeding uint32."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                              address_granularity='DWORD',
                              segments=[segment(address=SEGMENT_ADDRESS,
                                                checksum=segment_checksum(
                                                    'XCP_CRC_16',
                                                    checksum_max_block_size=0x40000000))]))


def test_generation_accepts_the_largest_segment_block_size_that_fits():
    """The boundary an off-by-one would show at: 0x3FFFFFFF * 4 is the largest product within
    uint32."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                          address_granularity='DWORD',
                          segments=[segment(address=SEGMENT_ADDRESS,
                                            checksum=segment_checksum(
                                                'XCP_CRC_16',
                                                checksum_max_block_size=0x3FFFFFFF))]))

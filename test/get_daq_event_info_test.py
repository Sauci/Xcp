#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from jinja2.exceptions import UndefinedError

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta


def daq_event_info(handle, event_channel_number=0, byte_order='LITTLE_ENDIAN'):
    request = (0xD7, 0x00) + tuple(u16_to_array(event_channel_number, byte_order))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    return handle.can_if_transmit.call_args[0][1].SduDataPtr


def read_through_to_real_memory(handle):
    """A mock side_effect that genuinely dereferences the address the slave hands it, rather than
    fabricating a value the way the block-transfer tests elsewhere in this suite do (they only
    need to prove the *address* the slave requested was correct, not the wire bytes -- see e.g.
    get_id_test.py's own read_slave_memory, which never writes p_buffer at all). This is what lets
    test_the_event_channel_name_is_uploadable_from_the_mta_it_sets assert on the actual
    transmitted bytes: the MTA GET_DAQ_EVENT_INFO sets really does point at the compiled name
    array, so a mock that reads through it round-trips the real configured name."""
    def read_slave_memory(p_address, _extension, p_buffer):
        p_buffer[0] = handle.ffi.cast('uint8_t*', p_address)[0]
    return read_slave_memory


def test_get_daq_event_info_reports_the_configured_channel():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.7. All six response fields are
    configured pairwise distinct, non-zero, AND away from event()'s own defaults
    (consistency='ODT', time_cycle=10, time_unit='TIMESTAMP_UNIT_1MS', triggered_daq_list_ref=
    ['DAQ1']) -- pairwise distinctness alone catches a transposition, but a hardcoded handler
    (source/Xcp_Daq.c's SduDataPtr[0x02u..0x06u] assignments replaced by the literals
    0x04u, 0x01u, 0x0Au, 0x06u) would still pass a test that only moves priority away from its
    default, since every other field would then equal the default the helper already supplies.
    Task 10 shipped a test that would have passed with two request fields transposed because
    every value was zero; Task 12 shipped a response field with no assertion at all.

    Two channels, and channel 1 (not 0) is the one requested: nothing in a single-channel test
    distinguishes eventChannel[event_channel_number] from a hardcoded eventChannel[0]. Channel 0
    is configured with different values throughout, so indexing the wrong channel fails loudly
    rather than coincidentally matching.

    consistency='EVENT' here also exercises Xcp_EventConsistencyBits' only non-trivial branch
    (DAQ_EVENT_PROPERTIES' CONSISTENCY_EVENT bit, 0x80) -- the bit position that most needed a
    real check, since the bit table came from reading the spec's page image directly (the OCR
    text mangles it) rather than from anything the brief stated as a literal."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1), daq(name='DAQ2', max_odt=1)),
                                   events=(event(name='EVT_OTHER', priority=1, time_cycle=1,
                                                triggered_daq_list_ref=['DAQ1']),
                                           event(name='EVT_100MS', consistency='EVENT', priority=50,
                                                time_cycle=100, time_unit='TIMESTAMP_UNIT_10MS',
                                                triggered_daq_list_ref=['DAQ1', 'DAQ2']))))
    connect(handle)

    frame = daq_event_info(handle, event_channel_number=1)

    assert frame[0] == 0xFF
    assert frame[1] == 0x84, 'DAQ_EVENT_PROPERTIES -- DAQ bit (type=DAQ) | CONSISTENCY_EVENT bit'
    assert frame[2] == 2, 'MAX_DAQ_LIST -- the length of triggered_daq_list_ref'
    assert frame[3] == len('EVT_100MS'), 'EVENT_CHANNEL_NAME_LENGTH'
    assert frame[4] == 100, 'TIME_CYCLE'
    assert frame[5] == handle.lib.TIMESTAMP_UNIT_10MS
    assert frame[6] == 50, 'PRIORITY'


def test_get_daq_event_info_honours_byte_order_when_decoding_the_channel_number():
    """The EVENT_CHANNEL_NUMBER decode (Xcp_CopyToU16WithOrder, source/Xcp_Daq.c) is otherwise
    transposition-immune in this file's other tests: channel 0 is 0x0000 under either byte order,
    and an out-of-range request like 9 reads as 0x0009 or 0x0900 either way -- still out of range
    regardless of whether byte order was even applied. Requesting channel 1 of a two-channel
    config under BIG_ENDIAN is the case that actually depends on correct decoding: swapped,
    channel 1 (wire bytes 0x00, 0x01) would read as 0x0100 = 256, which IS out of range for two
    channels, so a byte-order bug here answers ERR_OUT_OF_RANGE instead of channel 1's real data."""
    handle = XcpTest(DefaultConfig(byte_order='BIG_ENDIAN',
                                   daqs=(daq(name='DAQ1'), daq(name='DAQ2')),
                                   events=(event(name='EVT0', priority=1, triggered_daq_list_ref=['DAQ1']),
                                           event(name='EVT1', priority=42, triggered_daq_list_ref=['DAQ2']))))
    connect(handle)

    frame = daq_event_info(handle, event_channel_number=1, byte_order='BIG_ENDIAN')

    assert frame[0] == 0xFF, 'a byte-order decoding bug would misread channel 1 as out of range'
    assert frame[6] == 42, "PRIORITY -- proves this is channel 1's data, not channel 0's"


def test_daq_event_properties_stim_bit_stays_clear_for_a_daq_stim_channel():
    """DAQ_EVENT_PROPERTIES' STIM bit (0x08) stays clear even for a DAQ_STIM channel, the same
    policy Xcp_DTOCmdDaqGetDaqListInfo's own DAQ_LIST_PROPERTIES applies for the identical reason
    (get_daq_list_info_test.py, test_daq_list_properties_daq_bit_follows_the_configured_type):
    data stimulation arrives in SP3. Nothing pinned this in this file until now -- the DAQ bit
    (0x04, set because DAQ_STIM is DAQ-capable) was the only properties bit any test here observed."""
    handle = XcpTest(DefaultConfig(events=(event(name='EVT', type='DAQ_STIM',
                                                 triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)

    frame = daq_event_info(handle)

    assert frame[1] == 0x04, 'DAQ_EVENT_PROPERTIES -- DAQ set, STIM (0x08) stays clear until SP3'


def test_the_event_channel_name_is_uploadable_from_the_mta_it_sets():
    """1.6.4.1.2.7: the command 'automatically sets the Memory Transfer Address (MTA) to the
    location from which the master device may upload the event channel name as ASCII text, using
    one or more UPLOAD commands'. No NUL terminator on the wire.

    max_cto=16: default max_cto is 8, leaving only 7 payload bytes per CTO frame (max_cto - 1) --
    one short of this 8-byte name. A single-frame UPLOAD is what lets this test prove the MTA is
    right by construction, not a multi-frame block transfer (get_id_test.py's own MTA/UPLOAD round
    trip already covers that, with a name long enough to require one), so max_cto is raised
    instead of the name shortened -- a shorter name would stop pinning "no NUL terminator" (there
    would be no embedded NUL in EVT_10MS to accidentally match anyway, but a name is not evidence
    of that until it is transmitted whole)."""
    handle = XcpTest(DefaultConfig(max_cto=16,
                                   events=(event(name='EVT_10MS', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    handle.xcp_read_slave_memory_u8.side_effect = read_through_to_real_memory(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD7, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, len('EVT_10MS'))))
    handle.lib.Xcp_MainFunction()

    uploaded = bytes(handle.can_if_transmit.call_args[0][1].SduDataPtr[1:1 + len('EVT_10MS')])
    assert uploaded == b'EVT_10MS'


def test_no_name_is_published_when_publish_names_is_false():
    """1.6.4.1.2.7 defines EVENT_CHANNEL_NAME_LENGTH 0 as 'if not available', so this is
    conformant, not a degraded mode.

    Also pins the companion rule: the MTA is left alone. Moving it to NULL_PTR when there is
    nothing to publish would silently invalidate whatever the master had already set with
    SET_MTA -- so a SET_MTA immediately before GET_DAQ_EVENT_INFO here must still be the address
    an UPLOAD right after reads from, proving the command did not touch it."""
    handle = XcpTest(DefaultConfig(publish_names=False,
                                   events=(event(name='EVT_10MS', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD7, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[3] == 0

    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    addresses_read = []
    handle.xcp_read_slave_memory_u8.side_effect = \
        lambda p_address, _e, _b: addresses_read.append(int(handle.ffi.cast('uint32_t', p_address)))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert addresses_read == [0xDEADBEEF]


@pytest.mark.parametrize('consistency, expected', (('ODT', 0x00),
                                                   ('DAQ', 0x40),
                                                   ('EVENT', 0x80)))
def test_consistency_reaches_the_right_daq_event_properties_bits(consistency, expected):
    """1.6.4.1.2.7 encodes consistency in DAQ_EVENT_PROPERTIES bits 7:6 -- 00 ODT, 01
    CONSISTENCY_DAQ, 10 CONSISTENCY_EVENT. config/xcp.schema.json has always permitted all three,
    but "DAQ" reached the generator as a bare identifier and resolved to
    Xcp_EventChannelTypeType::DAQ, a different enumeration whose DAQ is 0x00u -- numerically this
    enumeration's ODT. So a channel configured for DAQ-list consistency compiled, ran, and
    reported ODT consistency, and bit 6 was set by nothing anywhere in the module. All three
    values are swept here rather than only the newly-mapped one, so the mapping is pinned as a
    whole and ODT stays distinguishable from a DAQ that silently collapsed onto it."""
    handle = XcpTest(DefaultConfig(events=(event(name='EVT', consistency=consistency,
                                                 triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)

    frame = daq_event_info(handle)

    assert frame[1] == (0x04 | expected), 'DAQ bit (type=DAQ) plus the consistency bits'


def test_the_event_channel_consistency_enumerators_keep_their_numeric_values():
    """Xcp_EventChannelConsistencyType is transmitted only indirectly, through
    Xcp_EventConsistencyBits, so nothing above pins the enumerators themselves -- but their values
    are ABI for any integrator holding an already-compiled Xcp_Cfg.o. The commented-out //DAQ sat
    between ODT and EVENT, so the obvious way to enable DAQ-list consistency was to uncomment it,
    which silently renumbers EVENT from 1 to 2. DAQ_LIST is appended with an explicit value
    instead, and this test is what refuses the tempting edit.

    Xcp_EventChannelTypeType::DAQ is asserted alongside because it is the collision that made the
    bug possible: a bare DAQ in this position is 0x00u, indistinguishable from ODT."""
    handle = XcpTest(DefaultConfig())

    assert handle.lib.ODT == 0x00
    assert handle.lib.EVENT == 0x01, 'inserting an enumerator before this one is an ABI break'
    assert handle.lib.DAQ_LIST == 0x02
    assert handle.lib.DAQ == 0x00, 'Xcp_EventChannelTypeType::DAQ, which a bare "DAQ" resolves to'


def test_max_daq_list_reports_the_full_reference_count_at_the_byte_boundary():
    """MAX_DAQ_LIST is one byte (1.6.4.1.2.7), and 255 references is the most it can carry. This
    asserts that boundary: a channel referencing exactly 255 lists reports 255, and the count that
    will not fit fails generation instead (the test below).

    What this does NOT assert, despite an earlier docstring here claiming it did, is that the byte
    is read from maxDaqList rather than from (uint8)triggeredDaqListRefCount. Reverting
    source/Xcp_Daq.c to the old cast passes all thirteen tests in this file, and no test can
    separate them: script/source_cfg.c.jinja2 emits both fields from the same
    `triggered_daq_list_ref|length`, so they differ only above 255, which the generation guard
    makes unreachable. A test that poked maxDaqList through the handle would discriminate on paper
    while asserting a state the module never produces, which is worse than admitting the gap.

    The change to maxDaqList is still worth having -- it is the uint8 field whose doxygen quotes
    1.6.4.1.2.7's own definition of MAX_DAQ_LIST, against a uint32 that a cast would truncate --
    but it is a change the generation guard, not this test, is what makes safe."""
    handle = XcpTest(DefaultConfig(events=(event(name='EVT', triggered_daq_list_ref=['DAQ1'] * 255),)))
    connect(handle)

    frame = daq_event_info(handle)

    assert frame[2] == 255
    assert handle.lib.Xcp_Ptr.config.eventChannel[0].maxDaqList == 255


def test_generation_fails_when_an_event_channel_references_more_lists_than_one_byte_can_report():
    """The guard that makes reading the uint8 maxDaqList safe: a count that field cannot hold is
    refused at generation, beside the existing odtCount / odtEntriesCount guard, rather than
    emitted as a literal the compiler truncates."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(events=(event(name='EVT', triggered_daq_list_ref=['DAQ1'] * 256),)))


def test_get_daq_event_info_answers_out_of_range_for_an_unknown_channel():
    handle = XcpTest(DefaultConfig(events=(event(name='EVT', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)

    frame = daq_event_info(handle, event_channel_number=9)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))


def test_get_daq_event_info_is_refused_when_disabled():
    """xcp_get_daq_event_info_api_enable defaults to True (config/xcp.json and parameter.py both
    already ship it enabled); this pins that turning it off still answers ERR_CMD_UNKNOWN through
    the same generic ctoInfo-enable path every other optional command uses.
    Xcp_PIDTable[0xD7] points unconditionally at Xcp_DTOCmdDaqGetDaqEventInfo -- there is no
    compile-time fallback to Xcp_CmdNotImplemented -- so this is the test that would fail if the
    runtime gate were ever bypassed."""
    handle = XcpTest(DefaultConfig(xcp_get_daq_event_info_api_enable=False))
    connect(handle)

    frame = daq_event_info(handle)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN'))

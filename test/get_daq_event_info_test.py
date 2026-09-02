#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
    configured pairwise distinct and non-zero -- MAX_DAQ_LIST=1, DAQ_EVENT_PROPERTIES=4 (DAQ bit
    only: type and consistency both default), EVENT_CHANNEL_NAME_LENGTH=8, TIME_CYCLE=10,
    TIME_UNIT=6, PRIORITY=7 -- so no two of them could be transposed and still pass. Task 10
    shipped a test that would have passed with two request fields transposed because every value
    was zero; Task 12 shipped a response field with no assertion at all."""
    handle = XcpTest(DefaultConfig(events=(event(name='EVT_10MS', priority=7, time_cycle=10,
                                                 time_unit='TIMESTAMP_UNIT_1MS',
                                                 triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)

    frame = daq_event_info(handle)

    assert frame[0] == 0xFF
    assert frame[1] == 0x04, 'DAQ_EVENT_PROPERTIES -- DAQ bit only, type and consistency default'
    assert frame[2] == 1, 'MAX_DAQ_LIST -- the length of triggered_daq_list_ref'
    assert frame[3] == len('EVT_10MS'), 'EVENT_CHANNEL_NAME_LENGTH'
    assert frame[4] == 10, 'TIME_CYCLE'
    assert frame[5] == handle.lib.TIMESTAMP_UNIT_1MS
    assert frame[6] == 7, 'PRIORITY'


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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def response(handle, request):
    """One command, confirmed, so the next one in the same test can be sent -- the same
    Rx/MainFunction/TxConfirmation triple daq_pid_off_test.py and write_daq_multiple_test.py use.
    Returns the whole response frame rather than its first two bytes, because every caller here
    asserts on a field further in."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    frame = handle.can_if_transmit.call_args[0][1].SduDataPtr
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return frame


def get_daq_clock(handle):
    return response(handle, (0xDC,))


def clockless_and_clocked():
    """One generated file holding two configurations: index 0 declares no
    protocol_layer.timestamp, index 1 declares a DWORD one.

    This is the shape every macro in script/header_cfg.h.jinja2 is folded for and that no test
    could build until MultiConfig existed. XCP_DAQ_TIMESTAMP_SUPPORTED is ANY across
    configurations, so it is STD_ON for this whole build -- Xcp_DTOCmdDaqGetDaqClock is compiled
    in and Xcp_PIDTable[0xDC] points at it rather than at Xcp_CmdNotImplemented -- while
    configuration 0 still has no clock. Any test using this fixture on index 0 must assert
    XCP_DAQ_TIMESTAMP_SUPPORTED is STD_ON, or it cannot tell the runtime gate's ERR_CMD_UNKNOWN
    from the compile-time fallback's identical one."""
    return MultiConfig(DefaultConfig(),
                       DefaultConfig(timestamp=timestamp(size='DWORD')))


@pytest.mark.parametrize('byte_order', byte_orders)
def test_get_daq_clock_returns_the_value_captured_at_reception(byte_order):
    """1.1/1.6.4.1.2.3: the response 'contains the current value of the data acquisition clock,
    when the GET_DAQ_CLOCK command packet has been received'. Xcp_CanIfRxIndication dispatches
    Xcp_DTOCmdDaqGetDaqClock synchronously, in the same call that receives the command, so that
    handler's own Xcp_GetDaqTimestamp() call already happens at reception -- there is no later,
    differently-scheduled point this could be deferred to (Xcp_MainFunction never assembles CTO
    responses; see the Task 8 report). What the wire value alone cannot prove is that the clock was
    read only once: a second, redundant read whose result is discarded would leave the same bytes
    on the wire and be invisible below, so call_count is asserted directly instead.

    The DWORD is the command's only multi-byte field, and it is asserted byte by byte against
    u32_to_array under both byte orders. The three mock values are non-palindromic for the same
    reason get_daq_processor_info_test.py's are: 0x11111111 and friends read identically in either
    direction, so replacing Xcp_CopyFromU32WithOrder with a fixed-endian copy would have left every
    assertion here passing."""
    handle = XcpTest(DefaultConfig(byte_order=byte_order, timestamp=timestamp()))
    connect(handle)
    handle.xcp_get_daq_timestamp.side_effect = (v for v in (0x12345678, 0x9ABCDEF0, 0x0BADF00D))

    frame = get_daq_clock(handle)

    assert handle.xcp_get_daq_timestamp.call_count == 1

    assert frame[0] == 0xFF
    assert tuple(frame[1:4]) == (0x00, 0x00, 0x00), 'three reserved bytes'
    assert tuple(frame[4:8]) == tuple(u32_to_array(0x12345678, byte_order))


def test_get_daq_clock_is_unknown_without_a_configured_clock():
    handle = XcpTest(DefaultConfig())
    connect(handle)

    assert tuple(get_daq_clock(handle)[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN'))


def test_every_clock_command_agrees_a_clockless_configuration_has_no_clock():
    """The build-wide macro says SOME configuration has a clock; Xcp_Ptr->general->timestampType
    says whether the ACTIVE one does. GET_DAQ_PROCESSOR_INFO, GET_DAQ_RESOLUTION_INFO and
    SET_DAQ_LIST_MODE have always asked the second question. GET_DAQ_CLOCK asked only the first,
    so in exactly this build -- two configurations, only the second with a clock, running as the
    first -- it answered with a value while its three siblings correctly reported no clock, and it
    called Xcp_GetDaqTimestamp on behalf of a configuration that never contracted for one.

    All four are asserted together rather than in four tests because the defect was never that any
    one of them was wrong on its own; it was that they disagreed."""
    handle = XcpTest(clockless_and_clocked(), configuration_index=0)
    connect(handle)

    assert handle.define('XCP_DAQ_TIMESTAMP_SUPPORTED') == handle.define('STD_ON'), \
        'otherwise Xcp_PIDTable[0xDC] is Xcp_CmdNotImplemented and this test proves nothing'
    assert handle.lib.Xcp_Ptr.general.timestampType == handle.lib.NO_TIME_STAMP

    assert (response(handle, (0xDA,))[0x01] & 0x10) == 0x00, \
        'GET_DAQ_PROCESSOR_INFO: TIMESTAMP_SUPPORTED clear'

    assert tuple(response(handle, (0xD9,))[5:8]) == (0x00, 0x00, 0x00), \
        'GET_DAQ_RESOLUTION_INFO: TIMESTAMP_MODE and TIMESTAMP_TICKS invalid'

    assert tuple(response(handle, (0xE0, 0x10, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0:2]) == \
        (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID')), \
        'SET_DAQ_LIST_MODE: TIMESTAMP refused'

    assert tuple(get_daq_clock(handle)[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN')), \
        'GET_DAQ_CLOCK: the same answer its three siblings give'
    assert handle.xcp_get_daq_timestamp.call_count == 0, \
        'a configuration with no clock must not have its integrator asked for one'


def test_get_daq_clock_still_answers_for_the_clocked_configuration_of_the_same_build():
    """The other half of the test above, and what keeps its fix from being "compile the command
    out": the very same generated file, run as configuration 1, must still answer. A gate that
    refused on the build-wide macro, or an over-eager fix that dropped the handler, fails here."""
    handle = XcpTest(clockless_and_clocked(), configuration_index=1)
    connect(handle)
    handle.xcp_get_daq_timestamp.return_value = 0x12345678

    frame = get_daq_clock(handle)

    assert frame[0] == 0xFF
    assert tuple(frame[4:8]) == tuple(u32_to_array(0x12345678, 'LITTLE_ENDIAN'))

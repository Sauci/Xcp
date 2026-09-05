#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def daq_list_info(handle, daq_list_number=0, byte_order='LITTLE_ENDIAN'):
    request = (0xD8, 0x00) + tuple(u16_to_array(daq_list_number, byte_order))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    return handle.can_if_transmit.call_args[0][1].SduDataPtr


def exchange(handle, request, length=8):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def test_get_daq_list_info_reports_the_configured_shape():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.2.1: MAX_ODT and MAX_ODT_ENTRIES echo
    this list's own configuration. Configured distinct from each other and both non-default --
    Task 10's review caught a test that would have passed with two response fields transposed,
    because every value in it was zero.

    FIXED_EVENT (bytes 4:6) is checked here too, and is load-bearing under this default
    LITTLE_ENDIAN, MAX_DTO=8 configuration: connect(), called immediately before daq_list_info(),
    leaves MAX_DTO's own WORD in that exact buffer region (Xcp_CTOCmdStdConnect, source/Xcp_Std.c,
    "Xcp_CopyFromU16WithOrder(Xcp_Ptr->general->maxDto, &SduDataPtr[0x04u], ...)") -- byte 4 = 0x08
    (MAX_DTO's low byte under little endian), byte 5 = 0x00. A deleted or mis-offset
    Xcp_CopyFromU16WithOrder call in Xcp_DTOCmdDaqGetDaqListInfo would leave that 0x08 at byte 4
    rather than the expected 0x00, so this assertion is not a check against an already-zero
    buffer. Byte 5's own leftover here is coincidentally already zero (MAX_DTO=8 has no high
    byte); see test_fixed_event_is_zeroed_regardless_of_byte_order below for the counterpart that
    makes byte 5 load-bearing too."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=7),)))
    connect(handle)

    frame = daq_list_info(handle)

    assert frame[0] == 0xFF
    assert frame[2] == 3, 'MAX_ODT'
    assert frame[3] == 7, 'MAX_ODT_ENTRIES'
    assert tuple(frame[4:6]) == (0, 0), 'FIXED_EVENT'


def test_fixed_event_is_zeroed_regardless_of_byte_order():
    """The load-bearing counterpart to FIXED_EVENT's check above. Xcp_CopyFromU16WithOrder
    (source/Xcp.c) places MAX_DTO's low byte at buffer offset 5 under BIG_ENDIAN instead of
    offset 4, so connect()'s leftover there (Xcp_CTOCmdStdConnect) becomes MAX_DTO's low byte --
    0x08 under this test's default MAX_DTO=8, nonzero -- while offset 4 becomes MAX_DTO's high
    byte, 0x00. A deleted or mis-offset Xcp_CopyFromU16WithOrder call in
    Xcp_DTOCmdDaqGetDaqListInfo would leave that 0x08 at byte 5 rather than the expected 0x00, so
    this variant is the one that actually proves FIXED_EVENT's own write reaches byte 5, the half
    the default LITTLE_ENDIAN test above cannot distinguish."""
    handle = XcpTest(DefaultConfig(byte_order='BIG_ENDIAN', daqs=(daq(name='DAQ1'),)))
    connect(handle)

    frame = daq_list_info(handle, byte_order='BIG_ENDIAN')

    assert tuple(frame[4:6]) == (0, 0), 'FIXED_EVENT'


def test_daq_list_properties_report_a_configurable_list_on_a_movable_event():
    """PREDEFINED clear: the master writes the entries. EVENT_FIXED clear (DD23): the sampler
    honours the binding SET_DAQ_LIST_MODE wrote at runtime, not the configured one, so the master
    may move a list between channels -- which also makes FIXED_EVENT don't-care."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ'),)))
    connect(handle)

    properties = daq_list_info(handle)[1]

    assert (properties & 0x01) == 0x00, 'PREDEFINED'
    assert (properties & 0x02) == 0x00, 'EVENT_FIXED'
    assert (properties & 0x04) == 0x04, 'DAQ'
    assert (properties & 0x08) == 0x00, 'STIM arrives in SP3'


@pytest.mark.parametrize('daq_type', ('DAQ', 'DAQ_STIM'))
def test_daq_list_properties_daq_bit_is_set_for_every_type_that_can_be_configured(daq_type):
    """The DAQ bit (0x04) is set for both DAQ and DAQ_STIM lists -- the same two types
    Xcp_CanIfRxIndication (source/Xcp.c) already treats as DAQ-capable when routing a stimulation
    PDU. STIM (0x08) stays clear for both: stimulation support arrives in SP3, matching the STIM
    granularity of 0 GET_DAQ_RESOLUTION_INFO already reports for the same reason
    (test_stim_fields_are_zero_while_stimulation_is_out_of_scope,
    get_daq_resolution_info_test.py).

    This used to carry a third case, `('STIM', False)`, and claimed to pin the OR in
    Xcp_DTOCmdDaqGetDaqListInfo against a coincidence. It no longer can, and says so rather than
    pretending: a pure STIM list is now refused at generation
    (test_generation_fails_when_a_daq_list_is_configured_as_stim, daq_configuration_test.py),
    because DAQ_LIST_PROPERTIES for one would have both type bits clear, an encoding
    1.1/1.6.4.2.2.1's DAQ_LIST_TYPE table marks "Not allowed". Every type that can reach this
    handler is DAQ-capable, so the OR's false arm is unreachable until SP3 implements the
    direction and lifts the guard. What is left here is still worth asserting -- DAQ_STIM reaches
    the same bit as DAQ, and neither sets STIM -- it is just not a test of the OR."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type=daq_type),)))
    connect(handle)

    properties = daq_list_info(handle)[1]

    assert (properties & 0x04) == 0x04, 'DAQ'
    assert (properties & 0x08) == 0x00, 'STIM arrives in SP3'


def test_get_daq_list_info_reports_stim_for_a_receiving_list():
    """§4. The generator refuses a pure STIM list today, and its comment states its own expiry:
    GET_DAQ_LIST_INFO would report both type bits clear, which 1.1/1.6.4.2.2.1's DAQ_LIST_TYPE
    table marks "Not allowed", because stimulation was unimplemented. It is implemented now.

    DAQ_LIST_PROPERTIES bit 2 is DAQ, bit 3 is STIM."""
    handle = XcpTest(stim_config(daq_count=1, odt_count=1, odt_entries_count=1))
    connect(handle)
    assert exchange(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF

    properties = exchange(handle, (0xD8, 0x00, 0x00, 0x00))[1]

    assert (properties & 0b00001000) != 0, 'DAQ_LIST_PROPERTIES must report STIM'
    assert (properties & 0b00000100) != 0, 'a DAQ_STIM pool is DAQ-capable too'


def test_get_daq_list_info_answers_out_of_range_for_an_unknown_list():
    """1.1/1.6.4.2.2.1: "If the specified list is not available, ERR_OUT_OF_RANGE will be
    returned." Unlike the DAQ pointer's own predicate-free check (Task 9), the DAQ list has a real
    one, Xcp_DaqListIsValid -- DefaultConfig()'s single configured list makes list 5 exactly the
    kind of list it rejects."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'),)))
    connect(handle)

    frame = daq_list_info(handle, daq_list_number=5)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))


def test_get_daq_list_info_is_refused_when_disabled():
    """xcp_get_daq_list_info_api_enable defaults to True (config/xcp.json and parameter.py both
    already ship it enabled); this pins that turning it off still answers ERR_CMD_UNKNOWN through
    the same generic ctoInfo-enable path every other optional command uses.
    Xcp_PIDTable[0xD8] points unconditionally at Xcp_DTOCmdDaqGetDaqListInfo -- there is no
    compile-time fallback to Xcp_CmdNotImplemented -- so this is the test that would fail if the
    runtime gate were ever bypassed."""
    handle = XcpTest(DefaultConfig(xcp_get_daq_list_info_api_enable=False))
    connect(handle)

    frame = daq_list_info(handle)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN'))

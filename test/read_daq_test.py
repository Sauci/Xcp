#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def set_daq_ptr(handle, daq_list=0, odt=0, entry=0, byte_order='LITTLE_ENDIAN'):
    return response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) + (odt, entry))


def write_daq(handle, size=1, extension=0, address=0xDEADBEEF, bit_offset=0xFF,
              byte_order='LITTLE_ENDIAN'):
    return response(handle, (0xE1, bit_offset, size, extension) +
                    tuple(u32_to_array(address, byte_order)))


def read_daq(handle):
    """Unlike response() above, this does not confirm the transmission itself: the returned frame
    is a live CFFI pointer into the module's own response buffer, and every test below needs to
    assert against it before confirming -- confirming first risks the assertions reading a buffer
    Xcp_StartNextTransmission has already reused for a later frame. See confirm()."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDB,)))
    handle.lib.Xcp_MainFunction()
    return handle.can_if_transmit.call_args[0][1].SduDataPtr


def confirm(handle):
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


# (bit_offset, size, extension, address). Chosen so that within each entry, and across entries,
# no two asserted fields ever share a value -- a transposed offset (BIT_OFFSET and size swapped,
# or the address extension read from the wrong response byte) then shows up as a wrong assertion
# rather than passing by coincidence, the lesson Task 10's review drew from a test where every
# field was zero. Entries 0 and 1 are bit-addressed (BIT_OFFSET 0x00/0x08, both real -- 0x00..
# 0x1F), which 1.1/1.6.4.1.1.2 requires to carry size == GRANULARITY_ODT_ENTRY_SIZE (1, for the
# default BYTE granularity): that is why they share size 0x01, not an oversight -- the
# granularity does not allow anything else there. Entry 2 is byte-addressed (BIT_OFFSET 0xFF,
# "ignore the field"), which the granularity does allow a different size for, so it is given one
# (0x03) rather than matching the other two.
ENTRIES = ((0x00, 0x01, 0x05, 0x11223344),
          (0x08, 0x01, 0x06, 0x55667788),
          (0xFF, 0x03, 0x07, 0x99AABBCC))


@pytest.mark.parametrize('byte_order', ('LITTLE_ENDIAN', 'BIG_ENDIAN'))
def test_read_daq_returns_what_write_daq_stored(byte_order):
    """A round trip tests both commands' view of the pointer at once: if either advances
    differently, the values come back against the wrong entries."""
    handle = XcpTest(DefaultConfig(byte_order=byte_order,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=3),)))
    connect(handle)

    set_daq_ptr(handle, daq_list=0, odt=0, entry=0, byte_order=byte_order)
    for bit_offset, size, extension, address in ENTRIES:
        assert write_daq(handle, bit_offset=bit_offset, size=size, extension=extension,
                         address=address, byte_order=byte_order)[0] == 0xFF

    set_daq_ptr(handle, daq_list=0, odt=0, entry=0, byte_order=byte_order)
    for bit_offset, size, extension, address in ENTRIES:
        frame = read_daq(handle)

        assert frame[0] == 0xFF
        assert frame[1] == bit_offset
        assert frame[2] == size
        assert frame[3] == extension
        assert payload_to_array(bytearray(frame[4:8]), 1, 4, byte_order)[0] == address

        confirm(handle)


def test_read_daq_answers_out_of_range_without_a_valid_pointer():
    """DD10 (SP2a): the pointer is undefined past the last entry of an ODT and repositioning it
    is the master's responsibility. ERR_OUT_OF_RANGE's prescribed action, "retry other
    parameter", means exactly that -- reposition with SET_DAQ_PTR. A freshly connected slave has
    never had a SET_DAQ_PTR at all, so the pointer starts out invalid the same way.

    This code is a deliberate deviation, recorded in design section 7.2: 1.7.3.2.4's READ_DAQ row
    does not list ERR_OUT_OF_RANGE, unlike every other command SP2b touches. The only listed
    alternative is ERR_CMD_SYNTAX, whose prescribed action -- "retry other syntax" -- cannot
    reposition a pointer, so it would send the master somewhere with nothing to find."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    frame = read_daq(handle)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))


def test_read_daq_stops_at_the_odt_border_like_write_daq_does():
    """1.1/1.6.4.1.2.2: "The DAQ list pointer is auto post incremented within one and the same
    ODT (See WRITE_DAQ)." Xcp_DaqPointerAdvance stops (invalidates) rather than wrapping into the
    next ODT (Task 9), so READ_DAQ finding the pointer past the last entry of a two-entry ODT
    must answer ERR_OUT_OF_RANGE exactly like a third WRITE_DAQ does today
    (test_the_pointer_goes_invalid_past_the_last_entry_of_an_odt, write_daq_test.py) -- two
    writes already leave the pointer invalid, the same way they do there."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=2),)))
    connect(handle)
    set_daq_ptr(handle, daq_list=0, odt=0, entry=0)

    assert write_daq(handle, size=1)[0] == 0xFF
    assert write_daq(handle, size=1)[0] == 0xFF

    frame = read_daq(handle)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_OUT_OF_RANGE'))


def test_read_daq_is_refused_when_disabled():
    """xcp_read_daq_api_enable defaults to True (config/xcp.json and parameter.py both already
    ship it enabled); this pins that turning it off still answers ERR_CMD_UNKNOWN through the
    same generic ctoInfo-enable path every other optional command uses. Xcp_PIDTable[0xDB] points
    unconditionally at Xcp_DTOCmdDaqReadDaq -- there is no compile-time fallback to
    Xcp_CmdNotImplemented -- so this is the test that would fail if the runtime gate were ever
    bypassed."""
    handle = XcpTest(DefaultConfig(xcp_read_daq_api_enable=False))
    connect(handle)

    frame = read_daq(handle)

    assert tuple(frame[0:2]) == (0xFE, handle.define('XCP_E_ASAM_CMD_UNKNOWN'))

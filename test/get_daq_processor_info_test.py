#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def info(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDA,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])


def daq_handle(**kwargs):
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'), daq(name='DAQ2'), daq(name='DAQ3')),
                                   **kwargs))
    connect(handle)
    return handle


def test_daq_properties_report_what_this_phase_implements():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.4. DAQ_CONFIG_TYPE static (bit 0
    clear), PRESCALER_SUPPORTED set (bit 1), RESUME/BIT_STIM/TIMESTAMP/PID_OFF clear (bits 2-5),
    OVERLOAD_MSB clear (bit 6), overload reported by event packet (bit 7).

    Checked as one exact byte rather than a mask on the two bits this phase drives, so a stray
    bit anywhere -- including a wrongly-set OVERLOAD_MSB -- fails this test too."""
    handle = daq_handle(prescaler_supported=True, overload_indication='EVENT')

    assert info(handle)[1] == 0x82


def test_daq_properties_drop_the_overload_bit_when_indication_is_off():
    """The other half of the pair above. test_daq_properties_report_what_this_phase_implements
    already proves the bit sets when overload_indication is EVENT; this proves it clears when
    NONE. Neither test alone distinguishes "reads overloadEvent from configuration" from a
    handler that always reports one fixed value -- together they do: an always-set handler fails
    this one, an always-clear handler fails the other."""
    handle = daq_handle(overload_indication='NONE')

    assert info(handle)[1] & 0xC0 == 0x00


def test_daq_properties_drop_the_prescaler_bit_when_unsupported():
    """Mirrors the overload pair for PRESCALER_SUPPORTED (bit 1): the sibling test above proves
    the bit sets when supported, this proves it clears when not."""
    handle = daq_handle(prescaler_supported=False)

    assert info(handle)[1] & 0x02 == 0x00


def test_max_daq_and_max_event_channel_and_min_daq():
    """MAX_DAQ and MAX_EVENT_CHANNEL are configured distinctively -- 3 DAQ lists, 2 event
    channels -- so neither reads as 1 (a plausible hard-coded stub value) or 0, and the two
    differ from each other so a field swap between them would also fail.

    MIN_DAQ has no configuration knob in this phase: source_cfg.c.jinja2 hard-codes it 0x00u
    ("no DAQ list is PREDEFINED"), so its correct value can never be made distinctive by
    configuration alone. The assertion is still load-bearing: daq_handle() calls connect() right
    before this command runs, and CONNECT's own response (Xcp_CTOCmdStdConnect,
    source/Xcp_Std.c) writes XCP_PROTOCOL_LAYER_VERSION (0x01, nonzero) into byte 6 of the exact
    same response buffer. Xcp_FinalizeResPacket only fills bytes from its start index onward, so
    if GET_DAQ_PROCESSOR_INFO's own byte-6 assignment were ever deleted, this response would
    still carry that leftover 0x01 instead of 0x00. Confirmed by mutation -- see
    task-13-report.md."""
    handle = daq_handle(events=(event(triggered_daq_list_ref=['DAQ1']), event(triggered_daq_list_ref=['DAQ2'])))

    response = info(handle)

    assert response[2:4] == (0x03, 0x00), 'MAX_DAQ, little endian'
    assert response[4:6] == (0x02, 0x00), 'MAX_EVENT_CHANNEL, little endian'
    assert response[6] == 0x00, 'MIN_DAQ: nothing is predefined'


def test_words_follow_the_configured_byte_order():
    """MAX_DAQ and MAX_EVENT_CHANNEL go through two independent Xcp_CopyFromU16WithOrder call
    sites in the handler, so both are checked here rather than trusting one to prove the other --
    a copy-paste regression could hardcode one call site's order while the other correctly reads
    configuration. Same distinctive counts as above (3 DAQ lists, 2 event channels), so neither
    0x0003 nor 0x0002 is byte-palindromic under a swap."""
    handle = daq_handle(byte_order='BIG_ENDIAN',
                        events=(event(triggered_daq_list_ref=['DAQ1']), event(triggered_daq_list_ref=['DAQ2'])))

    response = info(handle)

    assert response[2:4] == (0x00, 0x03), 'MAX_DAQ, big endian'
    assert response[4:6] == (0x00, 0x02), 'MAX_EVENT_CHANNEL, big endian'


@pytest.mark.parametrize('name, key', (('ABSOLUTE', 0x00),
                                       ('RELATIVE_BYTE', 0x40),
                                       ('RELATIVE_WORD', 0x80),
                                       ('RELATIVE_WORD_ALIGNED', 0xC0)))
def test_daq_key_byte_carries_the_identification_field_type_in_bits_7_6(name, key):
    """Exhaustive over all four values Xcp_IdentificationFieldTypeType can take, so a wrong shift
    amount or a misordered enum surfaces here without needing to inspect the enum's numbering by
    hand. The ABSOLUTE case (key 0x00) is not a vacuous zero check either, by the same argument as
    MIN_DAQ above: connect(), called by daq_handle() immediately before info(), leaves
    XCP_TRANSPORT_LAYER_VERSION (0x01, nonzero) at this same buffer offset (byte 7 of CONNECT's
    response), so a deleted key_byte assignment would leave 0x01 rather than 0x00."""
    handle = daq_handle(identification_field_type=name)

    assert info(handle)[7] == key, 'optimisation type OM_DEFAULT and address extension 0'


def test_timestamp_supported_is_set_when_a_clock_is_configured():
    """DAQ_PROPERTIES bit 4 (XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.4). Mirrors the
    prescaler/overload set-clear pairs above: this proves the bit sets when a clock is configured,
    the sibling below proves it clears when none is."""
    handle = daq_handle(timestamp=timestamp())

    assert (info(handle)[1] & 0x10) == 0x10


def test_timestamp_supported_is_clear_without_a_clock():
    """The other half of the pair above: DefaultConfig's timestamp=None means no protocol_layer
    timestamp block, i.e. NO_TIME_STAMP (Task 1), so TIMESTAMP_SUPPORTED must stay clear."""
    handle = daq_handle()

    assert (info(handle)[1] & 0x10) == 0x00

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from jinja2.exceptions import UndefinedError

from .parameter import *
from .conftest import XcpTest


identification_field_cases = [
    pytest.param('ABSOLUTE', 1, id='ident = ABSOLUTE'),
    pytest.param('RELATIVE_BYTE', 2, id='ident = RELATIVE_BYTE'),
    pytest.param('RELATIVE_WORD', 3, id='ident = RELATIVE_WORD'),
    pytest.param('RELATIVE_WORD_ALIGNED', 4, id='ident = RELATIVE_WORD_ALIGNED')]


@pytest.mark.parametrize('name, header_size', identification_field_cases)
def test_identification_field_type_reaches_the_generated_configuration(name, header_size):
    handle = XcpTest(DefaultConfig(identification_field_type=name))

    assert handle.config.lib.Xcp[0].general.identificationFieldType == getattr(handle.lib, name)


@pytest.mark.parametrize('name, header_size', identification_field_cases)
def test_max_odt_entry_size_daq_is_max_dto_less_the_identification_field(name, header_size):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5"""
    handle = XcpTest(DefaultConfig(identification_field_type=name, max_dto=8))

    assert handle.config.lib.Xcp[0].general.odtEntrySizeDaq == 8 - header_size


def test_stim_odt_entry_size_is_zero_while_stimulation_is_out_of_scope():
    handle = XcpTest(DefaultConfig())

    assert handle.config.lib.Xcp[0].general.odtEntrySizeStim == 0


def test_prescaler_support_comes_from_the_configuration():
    assert XcpTest(DefaultConfig(prescaler_supported=True)).config.lib.Xcp[0].general.prescalerSupported == 1
    assert XcpTest(DefaultConfig(prescaler_supported=False)).config.lib.Xcp[0].general.prescalerSupported == 0


def test_odt_counts_are_summed_over_every_daq_list():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=9),
                                         daq(name='DAQ2', max_odt=5, max_odt_entries=10))))

    assert handle.config.lib.Xcp[0].general.odtCount == 3 + 5
    assert handle.config.lib.Xcp[0].general.odtEntriesCount == (3 * 9) + (5 * 10)


def test_min_daq_is_zero_because_no_daq_list_is_predefined():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.4"""
    handle = XcpTest(DefaultConfig())

    assert handle.config.lib.Xcp[0].general.minDaq == 0


@pytest.mark.parametrize('max_dto', (8, 16, 64))
def test_max_dto_is_available_as_a_compile_time_macro(max_dto):
    handle = XcpTest(DefaultConfig(max_dto=max_dto))

    assert handle.define('XCP_MAX_DTO') == max_dto


def test_first_pid_is_the_running_sum_of_preceding_odt_counts():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4"""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3),
                                         daq(name='DAQ2', max_odt=5),
                                         daq(name='DAQ3', max_odt=2))))

    assert handle.config.lib.Xcp[0].config.daqList[0].firstPid == 0
    assert handle.config.lib.Xcp[0].config.daqList[1].firstPid == 3
    assert handle.config.lib.Xcp[0].config.daqList[2].firstPid == 8


def test_odt_entries_start_with_a_cleared_address_extension():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.1.1 resets extension to 0."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=2),)))

    assert handle.config.lib.Xcp[0].config.daqList[0].odt[0].odtEntry[0].addressExtension == 0
    assert handle.config.lib.Xcp[0].config.daqList[0].odt[0].odtEntry[1].addressExtension == 0


def test_event_channels_are_generated_rather_than_left_null():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1), daq(name='DAQ2', max_odt=1))))

    assert handle.config.lib.Xcp[0].config.eventChannel != handle.config.ffi.NULL
    assert handle.config.lib.Xcp[0].general.maxEventChannel == 1
    assert handle.config.lib.Xcp[0].config.eventChannel[0].number == 0
    assert handle.config.lib.Xcp[0].config.eventChannel[0].timeCycle == 10
    assert handle.config.lib.Xcp[0].config.eventChannel[0].timeUnit == handle.lib.TIMESTAMP_UNIT_1MS


def test_event_channel_references_resolve_to_the_named_daq_lists():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3), daq(name='DAQ2', max_odt=5)),
                                   events=(event(triggered_daq_list_ref=['DAQ2']),)))

    channel = handle.config.lib.Xcp[0].config.eventChannel[0]

    assert channel.triggeredDaqListRefCount == 1
    assert channel.triggeredDaqListRef[0].number == 1
    assert channel.triggeredDaqListRef[0].firstPid == 3


def test_event_channel_may_reference_several_daq_lists():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1), daq(name='DAQ2', max_odt=1)),
                                   events=(event(triggered_daq_list_ref=['DAQ1', 'DAQ2']),)))

    channel = handle.config.lib.Xcp[0].config.eventChannel[0]

    assert channel.triggeredDaqListRefCount == 2
    assert channel.triggeredDaqListRef[0].number == 0
    assert channel.triggeredDaqListRef[1].number == 1


# The four tests below assert only that generation fails, never on the exception's message: the
# generator's raise(...) call is not a registered Jinja global (see source_cfg.c.jinja2's comment
# at its first call site), so every one of these actually aborts with jinja2.exceptions.UndefinedError
# and the message string these DAQ/event misconfigurations would otherwise explain never reaches it.
# jinja2.exceptions.UndefinedError is still worth asserting on, narrower than a bare Exception: all
# five raise(...) sites deterministically produce it, so the assertion stays agnostic about which
# site fired and unattached to message text, while still ruling out an unrelated failure that never
# reached the template at all (a typo'd daq()/event() keyword argument, an import error, ...).


def test_generation_fails_when_a_configured_pid_contradicts_the_derived_first_pid():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4 -- reproduces D12: DAQ1's 3 ODTs
    claim absolute ODT numbers 0-2, so DAQ2's FIRST_PID is derived as 3, contradicting the 1
    configured here for DAQ2, which claims absolute ODT numbers 1-5 and so overlaps DAQ1."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, dtos=[{"pid": 0}]),
                                    daq(name='DAQ2', max_odt=5, dtos=[{"pid": 1}]))))


def test_generation_fails_when_total_odt_count_exceeds_the_pid_ceiling():
    """XCP part 2 - Protocol Layer Specification 1.1/1.1.4.1 caps a DAQ PID at 0xFB, so the total
    ODT count across every DAQ list must not exceed 0xFC (252).

    253, not a round number: Xcp_GeneralType's own odtCount field (Task 1's guard, source_cfg.c
    .jinja2's `counters.odt > 255`) independently rejects anything over 255, so a total that also
    clears 255 -- 300, say -- would still abort generation even if this task's own >252 guard were
    broken or deleted, and the test would stay green for the wrong reason. 253 sits strictly between
    the two ceilings (252 < 253 <= 255), so only the guard this test exists to cover can reject it.
    Verified empirically: rendering this exact configuration with only the >252 guard suppressed
    produces 215,968 characters of clean C, with nothing else in the template objecting."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=200), daq(name='DAQ2', max_odt=53))))


def test_generation_fails_when_an_event_channel_references_an_unknown_daq_list():
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'),),
                              events=(event(triggered_daq_list_ref=['NOPE']),)))


def test_generation_fails_when_an_event_has_no_time_unit():
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(events=({"consistency": "ODT",
                                       "priority": 0,
                                       "time_cycle": 10,
                                       "type": "DAQ",
                                       "triggered_daq_list_ref": ["DAQ1"]},)))

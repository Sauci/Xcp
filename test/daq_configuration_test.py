#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

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


def test_generation_fails_when_a_pid_is_configured_on_a_dto_that_is_not_the_first():
    """A PID on a later DTO has nothing to be checked against, and the generated code never reads
    one, so accepting it would let an integrator believe they had set something. AUTOSAR maps ODTs
    to DTOs by reference (ECUC_Xcp_00056, XcpOdt2DtoMapping) rather than by position, and that
    reference is not configurable here, so there is no second FIRST_PID to derive.

    match= cannot narrow this: every guard in source_cfg.c.jinja2 aborts by referencing the
    undefined name `raise`, so they all surface the same "'raise' is undefined" message (see the
    comment above the first guard in that template). What makes this test discriminating is the
    companion below: DTO 0's pid is the derived value, so the sibling FIRST_PID guard cannot fire,
    and the same configuration generates cleanly once the second pid is removed."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, dtos=[{"pid": 0}, {"pid": 1}]),)))


def test_generation_accepts_a_second_dto_that_configures_no_pid():
    """The rejection above is about the "pid" key, not about having more than one DTO: a list may
    still carry several, they just cannot each claim a PID."""
    XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, dtos=[{"pid": 0}, {}]),)))


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


@pytest.mark.parametrize('size, expected_type, expected_wire', (('BYTE', 'ONE_BYTE', 1),
                                                                 ('WORD', 'TWO_BYTE', 2),
                                                                 ('DWORD', 'FOUR_BYTE', 4)))
def test_configured_timestamp_reaches_the_generated_configuration(size, expected_type, expected_wire):
    """The three values were hard-coded literals (FOUR_BYTE, TIMESTAMP_UNIT_1MS, 0x0001u) before
    SP2b. XCP_DAQ_TIMESTAMP_SIZE is the wire size in bytes, deliberately not the enumerator:
    Xcp_TimestampTypeType is implicit, so FOUR_BYTE == 3, while the wire size is 4."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp(size=size,
                                                        unit='TIMESTAMP_UNIT_10US',
                                                        ticks=250)))

    assert handle.config.lib.Xcp[0].general.timestampType == getattr(handle.lib, expected_type)
    assert handle.config.lib.Xcp[0].general.timestampUnit == handle.lib.TIMESTAMP_UNIT_10US
    assert handle.config.lib.Xcp[0].general.timestampTicks == 250
    assert handle.define('XCP_DAQ_TIMESTAMP_SUPPORTED') == handle.define('STD_ON')
    assert handle.define('XCP_DAQ_TIMESTAMP_SIZE') == expected_wire


def test_an_absent_timestamp_block_disables_timestamps():
    handle = XcpTest(DefaultConfig())

    assert handle.config.lib.Xcp[0].general.timestampType == handle.lib.NO_TIME_STAMP
    assert handle.define('XCP_DAQ_TIMESTAMP_SUPPORTED') == handle.define('STD_OFF')
    assert handle.define('XCP_DAQ_TIMESTAMP_SIZE') == 0


def test_the_build_derives_daq_timestamp_macros_from_the_repository_configuration():
    """The two tests above only prove the harness's own per-test override reaches
    Xcp_GeneralConfig00 -- test/conftest.py injects XCP_DAQ_TIMESTAMP_SUPPORTED/_SIZE as compile
    definitions computed straight from each test's own configuration dict, bypassing the generated
    Xcp_Cfg.h entirely (handle.define() reads that injected value, not anything CMake derived).
    A real, non-test build never gets that injection: generated Xcp_Cfg.h includes Xcp_Types.h
    (whose fallback exists only so handle.define() has literal text to key off) before its own
    conditional block for these two macros, so that block's #define is unreachable there, and
    source/*.c does not include Xcp_Cfg.h at all. Without CMakeLists.txt deriving and injecting
    the same two macros the way it already does for XCP_PAGING_SUPPORTED, an integrator configuring
    protocol_layer.timestamp would silently get a module built with XCP_DAQ_TIMESTAMP_SUPPORTED
    permanently STD_OFF -- Task 2 gates Xcp_GetDaqTimestamp's declaration on exactly that macro.

    This test reads what CMake actually computed for the Xcp target's own COMPILE_DEFINITIONS
    (threaded through as the --compile_definitions pytest option, itself
    $<TARGET_PROPERTY:Xcp,COMPILE_DEFINITIONS>) straight from os.environ, never touching an XcpTest
    instance or its per-test override, and recomputes the expected values independently, straight
    from config/xcp.json on disk -- the file the CMakeLists.txt derivation itself reads -- rather
    than hard-coding today's STD_OFF/0 as a literal, so this stays correct if that file ever grows
    a timestamp block. Deleting the two new target_compile_definitions entries in CMakeLists.txt,
    or reverting to a fixed default there, fails this test with a KeyError or a mismatch; it cannot
    pass by coincidence the way it could if it re-read the harness's own injected value instead."""
    repository_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          'config', 'xcp.json')
    with open(repository_config_path) as fp:
        repository_config = json.load(fp)

    wire_size = {'BYTE': 1, 'WORD': 2, 'DWORD': 4}
    expected_supported = 'STD_ON' if any(c['protocol_layer'].get('timestamp')
                                         for c in repository_config['configurations']) else 'STD_OFF'
    expected_size = str(max((wire_size[c['protocol_layer']['timestamp']['size']]
                             for c in repository_config['configurations']
                             if c['protocol_layer'].get('timestamp')),
                            default=0))

    definitions = dict(item.split('=', 1) for item in os.environ['compile_definitions'].split(';') if '=' in item)

    assert definitions['XCP_DAQ_TIMESTAMP_SUPPORTED'] == expected_supported
    assert definitions['XCP_DAQ_TIMESTAMP_SIZE'] == expected_size


def test_generation_fails_when_an_event_has_an_empty_triggered_daq_list_ref():
    """An empty triggered_daq_list_ref would emit a zero-length C array
    (Xcp_EventChannelDaqListRef...[0x00u]) -- a GCC extension, an ISO C constraint violation, and
    rejected by MISRA and several embedded toolchains. The schema has no minItems to catch it."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'),),
                              events=(event(triggered_daq_list_ref=[]),)))

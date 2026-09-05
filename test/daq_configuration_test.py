#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

import pytest

from io import StringIO

from bsw_code_gen import BSWCodeGen
from jinja2.exceptions import UndefinedError

from .parameter import *
from .conftest import Preprocessor, XcpTest
from .download_test import connect


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


def test_a_dynamic_configuration_reports_its_pool_through_the_autosar_parameters():
    """DD26. XcpDaqCount (ECUC_Xcp_00012) is the number of allocatable lists, XcpOdtCount
    (ECUC_Xcp_00054) the ODTs of a DAQ list, XcpOdtEntriesCount (ECUC_Xcp_00059) the entries into
    an ODT. All three are defined only for DAQ_DYNAMIC."""
    handle = XcpTest(dynamic_config(daq_count=4, odt_count=8, odt_entries_count=16))
    general = handle.config.lib.Xcp[0].general

    # handle.lib, not handle.define: DAQ_DYNAMIC and DAQ_STATIC are Xcp_DaqConfigTypeType
    # enumerators (interface/Xcp_Types.h), not preprocessor names, and handle.define only ever
    # sees literal `#define`s -- see test.conftest.Preprocessor.on_directive_handle.
    assert general.daqConfigType == handle.lib.DAQ_DYNAMIC
    assert general.daqCount == 4
    assert general.odtCount == 8
    assert general.odtEntriesCount == 16


def test_a_static_configuration_leaves_the_dynamic_only_parameters_at_zero():
    """AUTOSAR defines XcpOdtCount and XcpOdtEntriesCount only for DAQ_DYNAMIC. The generator
    previously emitted aggregate sums here -- the total ODTs across all lists, and the grand total
    of entries -- which is neither field's meaning. No .c file read either one, so this corrects a
    latent wrong value rather than changing behaviour."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=9),)))
    general = handle.config.lib.Xcp[0].general

    assert general.daqConfigType == handle.lib.DAQ_STATIC
    assert general.daqCount == 1
    assert general.odtCount == 0
    assert general.odtEntriesCount == 0


def test_min_daq_is_zero_because_no_daq_list_is_predefined():
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.4"""
    handle = XcpTest(DefaultConfig())

    assert handle.config.lib.Xcp[0].general.minDaq == 0


@pytest.mark.parametrize('max_dto', (8, 16, 64))
def test_max_dto_is_available_as_a_compile_time_macro(max_dto):
    handle = XcpTest(DefaultConfig(max_dto=max_dto))

    assert handle.define('XCP_MAX_DTO') == max_dto


def test_a_multi_configuration_build_with_differing_max_dto_compiles_and_behaves():
    """script/source_rt.c.jinja2's Xcp_DtoFrameStrideCheck asserted XCP_MAX_DTO == this
    configuration's own max_dto, inside the per-configuration loop that emits one check per
    configuration in the generated file. XCP_MAX_DTO is a max() fold over every configuration in
    that file (script/header_cfg.h.jinja2), sizing Xcp_DtoFrameType.data[] once for the whole
    module, so any configuration whose own max_dto is smaller than another's in the same file
    failed to compile under ==, even though the shared, larger buffer already had room for it. >=
    is the correct relation: it demands the buffer be at least as large as this configuration
    needs, which a max() fold guarantees by construction.

    Constructing each XcpTest instance below is itself the compile-time half of this test --
    MockGen raises if the generated runtime fails to build, and before this fix it did, for
    configuration 0, the smaller of the two, the moment its own max_dto (8) disagreed with the
    fold's 64.

    The behavioural half follows, so a fix that merely compiles by coercing every configuration to
    the larger value cannot pass here. CONNECT's MAX_DTO field (source/Xcp_Std.c) reads
    Xcp_Ptr->general->maxDto, a per-configuration runtime field distinct from the compile-time
    macro above, so each configuration must still report its own. And Xcp_DtoFrameType.data[]
    itself -- shared, and sized to the larger configuration's 64 by the very fold this fix must
    not break -- must still produce a correctly bounded frame when a DAQ list running under the
    smaller configuration is triggered: one written byte plus its PID is a 2-byte frame in an
    8-byte MAX_DTO configuration exactly as it would be in a single-configuration build, not a
    64-byte one.

    Configuration 0 is built, used, and finished with before configuration 1 is ever constructed,
    rather than interleaved: MockGen caches the compiled module by rt_key, which folds in every
    configuration's max_dto (not just the active one), so both configurations here share one
    compiled module, including its def_extern callback registrations. A second XcpTest against
    the same rt_key re-registers those callbacks against its own mocks, so a live handle_small
    call made after handle_large exists would silently land on handle_large's mocks instead."""
    def exchange(handle, request):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    multi = MultiConfig(DefaultConfig(max_dto=8), DefaultConfig(max_dto=64))

    handle_small = XcpTest(multi, configuration_index=0)

    assert handle_small.define('XCP_MAX_DTO') == 64, \
        'one compiled stride, shared by both configurations -- the fold this fix must not break'

    connect(handle_small)
    small_connect = tuple(handle_small.can_if_transmit.call_args[0][1].SduDataPtr[0:8])
    assert (small_connect[4] | (small_connect[5] << 8)) == 8, \
        "CONNECT must report configuration 0's own MAX_DTO, not the shared compiled stride"

    exchange(handle_small, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))  # SET_DAQ_PTR: list 0, odt 0, entry 0
    exchange(handle_small, (0xE1, 0xFF, 0x01, 0x00) + tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))  # WRITE_DAQ
    exchange(handle_small, (0xE0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))  # SET_DAQ_LIST_MODE: channel 0
    exchange(handle_small, (0xDE, 0x01, 0x00, 0x00))  # START_STOP_DAQ_LIST: start list 0

    handle_small.can_if_transmit.reset_mock()
    handle_small.lib.Xcp_TriggerEventChannel(0)

    assert handle_small.can_if_transmit.call_count == 1
    frame = handle_small.can_if_transmit.call_args[0][1]
    assert frame.SduLength == 2, 'FIRST_PID plus the one written byte -- not the 64-byte stride'
    assert frame.SduDataPtr[0] == 0x00, 'FIRST_PID of the sole DAQ list/ODT'

    # Configuration 1, the larger of the two, in the same generated file -- built only now that
    # handle_small is done with (see the docstring for why).
    handle_large = XcpTest(multi, configuration_index=1)

    assert handle_large.define('XCP_MAX_DTO') == 64

    connect(handle_large)
    large_connect = tuple(handle_large.can_if_transmit.call_args[0][1].SduDataPtr[0:8])
    assert (large_connect[4] | (large_connect[5] << 8)) == 64


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


def test_each_odt_carries_its_own_entry_count_seeded_from_the_list_cap():
    """DD34. ALLOC_ODT_ENTRY assigns entries to one ODT, so a per-ODT count is needed; the
    per-list maxOdtEntries cannot express one ODT holding four entries and another two. Under
    STATIC every ODT is seeded with the list's max_odt_entries, which is what keeps the six
    relocated bound checks comparing against the value they compared against before."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3, max_odt_entries=9),)))
    daq_list = handle.config.lib.Xcp[0].config.daqList[0]
    assert daq_list.maxOdtEntries == 9
    for odt in range(3):
        assert daq_list.odt[odt].entryCount == 9


def test_a_dynamic_pool_is_reserved_empty_and_sliced_per_list_and_per_odt():
    """DD26. The rectangle -- daq_count x odt_count x odt_entries_count -- is reserved in full at
    build time and handed out by the allocator, so every descriptor starts empty while the slices
    ALLOC_ODT and ALLOC_ODT_ENTRY will fill are already wired: list i owns the ODTs
    [i*odt_count, (i+1)*odt_count) of one flat array, and ODT k owns the entries
    [k*odt_entries_count, (k+1)*odt_entries_count) of another.

    maxOdt is 0, not odt_count: an unallocated list must fail the bounds checks that already
    exist, which is what lets SP2d add none of its own (see the plan's global constraints).
    maxOdtEntries is the rectangle's width because that is the per-list cap the allocator may
    never exceed, and nothing raises it at runtime.

    `number` is the exception to "starts empty": it is slot i's own index, seeded at build time
    exactly as a static list's is, because ALLOC_DAQ hands out the first N slots of this pool in
    order and so slot i is list number i whether or not it has been handed out. It used to be
    zero here, which made every slot claim to be list 0 and broke GET_DAQ_ID's scan over this
    field -- see
    test/transport_layer_cmd_test.py::test_get_daq_id_answers_each_allocated_dynamic_list_by_its_own_number."""
    handle = XcpTest(dynamic_config(daq_count=3, odt_count=2, odt_entries_count=4))
    config = handle.config.lib.Xcp[0].config
    first_odt = config.daqList[0].odt
    first_entry = config.daqList[0].odt[0].odtEntry

    assert config.daqListCount == 3
    for i in range(3):
        daq_list = config.daqList[i]
        assert daq_list.number == i
        assert daq_list.firstPid == 0
        assert daq_list.maxOdt == 0
        assert daq_list.maxOdtEntries == 4
        assert daq_list.type == handle.lib.DAQ
        assert daq_list.odt == first_odt + (i * 2)
        for j in range(2):
            odt = daq_list.odt[j]
            assert odt.odtNumber == 0
            assert odt.entryCount == 0
            # max_dto 8 less the 1-byte ABSOLUTE identification field, DefaultConfig's own defaults.
            assert odt.odtEntryMaxSize == 7
            assert odt.odtEntry == first_entry + ((((i * 2) + j) * 4))


def test_a_dynamic_pool_shares_one_dto_across_every_list_in_it():
    """Every list in the pool transmits on the one pdu_mapping the daq_dynamic block names -- the
    master picks which lists it allocates, not which PDU they leave on -- so one Xcp_DtoType
    serves them all. dtoCount stays 1 rather than 0 because Xcp_Std.c guards its read of dto[0]
    with `dtoCount > 0` and Xcp_DaqRuntime.c reads dto[0] to address the frame."""
    handle = XcpTest(dynamic_config(daq_count=3))
    config = handle.config.lib.Xcp[0].config

    for i in range(3):
        assert config.daqList[i].dtoCount == 1
        assert config.daqList[i].dto == config.daqList[0].dto


def _generated_source(config):
    """The Xcp_Cfg.c `config` generates, as text. Which MemMap section a declaration sits in is
    invisible to the compiled harness -- Xcp_MemMap.h expands to nothing here -- so the generated
    source is the only place it can be observed."""
    return BSWCodeGen(config, os.environ['script_directory']).source_cfg


def _generated_runtime(config):
    """The Xcp_Rt.c `config` generates, as text."""
    return BSWCodeGen(config, os.environ['script_directory']).source_rt


def _memmap_section_of(source, declaration):
    """The Xcp_START_SEC_... section `declaration` is emitted inside, or None if it is absent."""
    section = None
    for line in source.splitlines():
        if line.startswith('#define Xcp_START_SEC_'):
            section = line.split()[1]
        elif declaration in line:
            return section
    return None


def test_a_dynamic_pool_is_emitted_into_a_writable_memmap_section():
    """ALLOC_DAQ, ALLOC_ODT and ALLOC_ODT_ENTRY write the Xcp_DaqListType and Xcp_OdtType arrays
    at runtime, so under DAQ_DYNAMIC they cannot sit in Xcp_START_SEC_CONST_UNSPECIFIED -- that is
    the section that puts them in flash on a target, and the `const` keyword the arrays lack is
    not what places them (see the note above Xcp_DaqListType in interface/Xcp_Types.h)."""
    source = _generated_source(dynamic_config())

    assert _memmap_section_of(source, 'static Xcp_DaqListType Xcp_DaqListConfig00[') == \
        'Xcp_START_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED'
    assert _memmap_section_of(source, 'static Xcp_OdtType Xcp_OdtConfig00[') == \
        'Xcp_START_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED'


@pytest.mark.parametrize('config, expected', (
    pytest.param(lambda: dynamic_config(daq_count=7), 'Xcp_DaqListRt00[0x07u];', id='DYNAMIC pool of 7'),
    pytest.param(lambda: DefaultConfig(daqs=(daq(name='DAQ1'), daq(name='DAQ2'))),
                 'Xcp_DaqListRt00[0x02u];', id='STATIC, two lists'),
))
def test_the_runtime_daq_list_array_is_sized_for_every_list_the_configuration_can_present(config,
                                                                                          expected):
    """Xcp_Init and Xcp_TriggerEventChannel both index Xcp_Rt[...].daqList by daqCount
    (source/Xcp.c, source/Xcp_DaqRuntime.c), which under DAQ_DYNAMIC is the pool size and not the
    number of lists declared under `daqs` -- of which a dynamic configuration has none. An array
    sized from `daqs` is therefore written past its end by Xcp_Init before the master has
    allocated anything.

    Asserted against the generated text rather than through a running module because the array is
    a file-scope static: nothing in the harness can reach it to bound-check it, and the
    out-of-bounds write it would take to expose the bug is silent unless the suite is run under
    XCP_ASAN=1, which it is not by default (test/conftest.py's _asan_flags)."""
    assert expected in _generated_runtime(config())


def test_a_static_configuration_keeps_its_descriptors_in_the_const_section():
    """The other half of the test above: nothing writes a STATIC configuration's descriptors, so
    they must stay in flash exactly as they are today."""
    source = _generated_source(DefaultConfig())

    assert _memmap_section_of(source, 'static Xcp_DaqListType Xcp_DaqListConfig00[') == \
        'Xcp_START_SEC_CONST_UNSPECIFIED'
    assert _memmap_section_of(source, 'static Xcp_OdtType Xcp_OdtConfig00Daq00[') == \
        'Xcp_START_SEC_CONST_UNSPECIFIED'


def test_event_channels_are_generated_rather_than_left_null():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1), daq(name='DAQ2', max_odt=1))))

    assert handle.config.lib.Xcp[0].config.eventChannel != handle.config.ffi.NULL
    assert handle.config.lib.Xcp[0].general.maxEventChannel == 1
    assert handle.config.lib.Xcp[0].config.eventChannel[0].number == 0
    assert handle.config.lib.Xcp[0].config.eventChannel[0].timeCycle == 10
    assert handle.config.lib.Xcp[0].config.eventChannel[0].timeUnit == handle.lib.TIMESTAMP_UNIT_1MS


def test_event_channel_references_resolve_to_the_named_daq_lists():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=3), daq(name='DAQ2', max_odt=5)),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ2']),)))

    channel = handle.config.lib.Xcp[0].config.eventChannel[0]

    assert channel.triggeredDaqListRefCount == 1
    assert channel.triggeredDaqListRef[0].number == 1
    assert channel.triggeredDaqListRef[0].firstPid == 3


def test_event_channel_may_reference_several_daq_lists():
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=1), daq(name='DAQ2', max_odt=1)),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1', 'DAQ2']),)))

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

    253 is chosen for a different reason than this docstring used to give. It claimed
    source_cfg.c.jinja2's `counters.odt > 255` was an *independent* second ceiling that a rounder
    300 would also trip, so 253 was needed to isolate this one. That was wrong in both directions:
    `counters.odt` and `pid.next` are the same sum, and the PID guard runs in an earlier template
    loop, so the uint8 condition could never fire at all -- 253 and 300 alike aborted here, and
    nothing about 253 isolated anything. The dead half has since been removed; XcpOdtCount's uint8
    field is protected by this stricter 252 ceiling rather than by a guard of its own.

    253 is kept because it is the smallest total that violates the ceiling, which is the value a
    boundary test should use. Verified empirically: rendering this exact configuration with only
    the >252 guard suppressed produces 215,968 characters of clean C, with nothing else in the
    template objecting."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', max_odt=200), daq(name='DAQ2', max_odt=53))))


def test_generation_fails_when_a_stim_capable_list_exceeds_the_stim_pid_ceiling():
    """DD42. XCP part 2 - Protocol Layer Specification 1.1/1.1.5.1 caps a STIM PID at 0xBF, tighter
    than the 0xFB ceiling test_generation_fails_when_total_odt_count_exceeds_the_pid_ceiling above
    checks: a list that can receive is addressed in that direction too, so its absolute ODT numbers
    -- FIRST_PID is fixed at generation for a STATIC list -- must not reach 0xC0.

    193 is the smallest total that violates it, the same reasoning the 252/253 pair above uses for
    the wider ceiling. A DAQ list of the same size is untouched by this guard (it keeps the 0xFB
    range), which is the generation-time half of proving the two ceilings are distinguished rather
    than both clamped low -- test/alloc_odt_test.py proves the runtime half."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='STIM', max_odt=193),)))


def test_generation_accepts_a_daq_list_past_the_stim_ceiling_when_it_cannot_receive():
    """DD42, the STATIC sibling of test_alloc_odt_keeps_the_full_daq_ceiling_for_a_daq_only_pool:
    script/source_cfg.c.jinja2's `daq.type != 'DAQ'` filter is what lets a DAQ list keep the wider
    0xFB range while a list that can receive is held to 0xC0, and nothing above exercises the
    DAQ-only half of that filter. test_generation_fails_when_total_odt_count_exceeds_the_pid_ceiling
    cannot: its two DAQ lists total 253, which trips the pre-existing `pid.next > 252` guard before
    the 0xC0 loop is ever reached, so its `pytest.raises(UndefinedError)` cannot tell a correctly
    scoped 0xC0 guard from one that also caught DAQ lists -- dropping `!= 'DAQ'` entirely (or
    inverting it) would pass every test above just as well as the real filter does.

    DAQ2 here sits in the one window that discriminates the two: its absolute ODT numbers run
    100..249 -- past 192 (0xC0), so an over-broad guard refuses it, but at or under 252 (0xFB + 1),
    so it is clear of the `pid.next` guard and only the type filter decides the outcome. DAQ1 is
    DAQ_STIM and stays under its own 192 ceiling (0..99), so this one configuration exercises both
    guards without either tripping incorrectly."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ_STIM', max_odt=100),
                                          daq(name='DAQ2', type='DAQ', max_odt=150))))

    assert handle.config.lib.Xcp[0].config.daqList[1].type == handle.lib.DAQ
    assert handle.config.lib.Xcp[0].config.daqList[1].firstPid == 100
    assert handle.config.lib.Xcp[0].config.daqList[1].maxOdt == 150


def test_generation_fails_when_odt_entry_size_daq_exceeds_the_uint8_field():
    """odtEntrySizeDaq is emitted as one byte into Xcp_GeneralType's uint8 XcpOdtEntrySizeDaq, but
    it is derived from max_dto, whose schema maximum is 65535. It sat two lines below the
    odtCount/odtEntriesCount guard with no bound of its own, so `max_dto: 1000` emitted 0x3E7u and
    the compiler truncated it to 231: GET_DAQ_RESOLUTION_INFO reported MAX_ODT_ENTRY_SIZE_DAQ 231
    for a 999-byte ODT, and every ODT-0 budget computation in source/Xcp_Daq.c ran on the truncated
    value. -Woverflow warned about it; nothing failed.

    257, not 1000: with the default ABSOLUTE identification field it is the smallest max_dto whose
    remainder (256) will not fit, and the companion below shows that 256 -- one less, remainder 255
    -- still generates. Nothing else in the template objects to either, so the pair discriminates
    this guard from the nine others that abort with the same "'raise' is undefined"."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(identification_field_type='ABSOLUTE', max_dto=257))


def test_generation_accepts_a_pure_stim_list():
    """A pure STIM list used to be refused at generation: Xcp_DTOCmdDaqGetDaqListInfo would have
    answered DAQ_LIST_PROPERTIES with both type bits clear -- DAQ clear because the list is not
    DAQ-capable, STIM clear because the direction was unimplemented -- and XCP part 2
    1.1/1.6.4.2.2.1's DAQ_LIST_TYPE table marks that encoding "Not allowed". SP3 implemented data
    stimulation and lifted the guard: Xcp_DTOCmdDaqGetDaqListInfo now sets the STIM bit for such a
    list instead of leaving both clear, which is the encoding the table marks "Not allowed"'s
    counterpart. This pins that the static list itself generates with the right type;
    get_daq_list_info_test.py's test_get_daq_list_info_reports_stim_for_a_pure_stim_list pins the
    resulting DAQ_LIST_PROPERTIES bits over a real GET_DAQ_LIST_INFO exchange.
    test_get_daq_list_info_reports_stim_for_a_receiving_list in that file is not this list's
    equivalent -- it configures a DAQ_STIM pool, not a pure STIM list."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='STIM'),)))

    assert handle.config.lib.Xcp[0].config.daqList[0].type == handle.lib.STIM


def test_generation_accepts_a_daq_stim_list():
    """DAQ_STIM generates too, and stays distinguishable from the pure STIM list above: DAQ_STIM
    is DAQ-capable as well as STIM-capable, where a pure STIM list is STIM-capable only."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ_STIM'),)))

    assert handle.config.lib.Xcp[0].config.daqList[0].type == handle.lib.DAQ_STIM


def test_generation_accepts_the_largest_odt_entry_size_the_uint8_field_can_hold():
    """The boundary the guard above is placed at, from the accepting side: 255 is representable and
    must stay accepted, so the guard is `> 255` and not `>= 255` or a rounder cut."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE', max_dto=256))

    assert handle.config.lib.Xcp[0].general.odtEntrySizeDaq == 255


def test_generation_fails_when_an_event_channel_references_an_unknown_daq_list():
    """name='EVT1': without it, this configuration would also trip the newer publish_names guard
    (script/source_cfg.c.jinja2 checks the DAQ-list reference before the name), so this test would
    keep passing -- for the wrong reason -- even if the reference-validity guard it names were
    reordered after the name guard or deleted outright."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'),),
                              events=(event(name='EVT1', triggered_daq_list_ref=['NOPE']),)))


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


def _preprocess_against_the_generated_header(config, probe_body):
    """Writes the Xcp_Cfg.h `config` generates into the build directory and preprocesses
    `probe_body` against it with NO compile definitions at all -- the position an integrator is in
    when they compile a translation unit that includes the generated header without replicating
    this project's target_compile_definitions. Returns the expanded text, whitespace-normalised."""
    probe_header = 'Xcp_Cfg_ordering_probe.h'
    build_directory = os.environ['build_directory']
    with open(os.path.join(build_directory, probe_header), 'w') as fp:
        fp.write(BSWCodeGen(config, os.environ['script_directory']).header_cfg)

    pre_processor = Preprocessor()
    for include_directory in os.environ['include_directories'].split(';') + [build_directory]:
        pre_processor.add_path(include_directory)
    pre_processor.parse('#include "{}"\n{}'.format(probe_header, probe_body))
    handle = StringIO()
    pre_processor.write(handle)
    return ' '.join(handle.getvalue().split())


ORDERING_PROBE = """
#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)
PROBE_TIMESTAMP_IS_ON
#else
PROBE_TIMESTAMP_IS_OFF
#endif
PROBE_TIMESTAMP_WIDTH XCP_DAQ_TIMESTAMP_SIZE
PROBE_MAX_DTO XCP_MAX_DTO
"""


def test_the_generated_header_is_authoritative_for_the_macros_it_derives():
    """interface/Xcp_Types.h carries `#ifndef X / #define X <fallback> / #endif` for XCP_MAX_DTO,
    XCP_DAQ_TIMESTAMP_SUPPORTED and XCP_DAQ_TIMESTAMP_SIZE, so that the harness's handle.define()
    has literal #define text to key off. The generated Xcp_Cfg.h used to include Xcp_Types.h before
    its own conditional blocks for the same three names, which meant those fallbacks always won and
    every one of the generated blocks was unreachable -- both halves were added by the same task
    and cancelled each other out. A configuration declaring a DWORD timestamp generated a header
    saying XCP_DAQ_TIMESTAMP_SUPPORTED (STD_OFF) and XCP_DAQ_TIMESTAMP_SIZE (0u), while its
    Xcp_Cfg.c set timestampType = FOUR_BYTE regardless.

    Preprocessed with no compile definitions whatsoever, deliberately: what this pins is that the
    header stands on its own, not that CMakeLists.txt threads the right -D through (its sibling
    below covers that, and it is a separate obligation -- source/*.c never includes Xcp_Cfg.h, so
    the -D is still what reaches the library sources)."""
    expanded = _preprocess_against_the_generated_header(
            DefaultConfig(timestamp=timestamp(size='DWORD'), max_dto=64), ORDERING_PROBE)

    assert 'PROBE_TIMESTAMP_IS_ON' in expanded
    assert 'PROBE_TIMESTAMP_WIDTH (4u)' in expanded
    assert 'PROBE_MAX_DTO (0x40u)' in expanded


def test_the_generated_header_still_reports_no_clock_when_none_is_configured():
    """The other direction of the test above: making the blocks reachable must not make them
    unconditional."""
    expanded = _preprocess_against_the_generated_header(DefaultConfig(), ORDERING_PROBE)

    assert 'PROBE_TIMESTAMP_IS_OFF' in expanded
    assert 'PROBE_TIMESTAMP_WIDTH (0u)' in expanded


def test_the_build_derives_daq_timestamp_macros_from_the_repository_configuration():
    """The two tests above only prove the harness's own per-test override reaches
    Xcp_GeneralConfig00 -- test/conftest.py injects XCP_DAQ_TIMESTAMP_SUPPORTED/_SIZE as compile
    definitions computed straight from each test's own configuration dict, bypassing the generated
    Xcp_Cfg.h entirely (handle.define() reads that injected value, not anything CMake derived).
    A real, non-test build never gets that injection, and the generated Xcp_Cfg.h cannot stand in
    for it: source/*.c includes Xcp.h and never Xcp_Cfg.h, so what that header defines does not
    reach the library sources at all. (It does now define these two correctly for whoever *does*
    include it -- script/header_cfg.h.jinja2 defines every derived macro ahead of its first
    #include, so Xcp_Types.h's fallback, which exists only so handle.define() has literal text to
    key off, no longer pre-empts it. That is a separate hole, closed separately.) Without
    CMakeLists.txt deriving and injecting the same two macros the way it already does for
    XCP_PAGING_SUPPORTED, an integrator configuring protocol_layer.timestamp would silently get a
    module built with XCP_DAQ_TIMESTAMP_SUPPORTED permanently STD_OFF -- Task 2 gates
    Xcp_GetDaqTimestamp's declaration on exactly that macro.

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

    expected_supported = 'STD_ON' if any(c['protocol_layer'].get('timestamp')
                                         for c in repository_config['configurations']) else 'STD_OFF'
    expected_size = str(max((timestamp_wire_size[c['protocol_layer']['timestamp']['size']]
                             for c in repository_config['configurations']
                             if c['protocol_layer'].get('timestamp')),
                            default=0))

    definitions = dict(item.split('=', 1) for item in os.environ['compile_definitions'].split(';') if '=' in item)

    assert definitions['XCP_DAQ_TIMESTAMP_SUPPORTED'] == expected_supported
    assert definitions['XCP_DAQ_TIMESTAMP_SIZE'] == expected_size


def test_generation_fails_when_the_timestamp_does_not_fit_the_odt_zero_budget():
    """MAX_DTO 7 with a 4-byte RELATIVE_WORD_ALIGNED identification field leaves
    odt_entry_size_daq = 3, less than the 4-byte DWORD timestamp XCP part 2 1.1/1.1.2.2 puts in
    ODT 0 alongside the identification field. Left ungenerated, source/Xcp_Daq.c's ODT-0 budget
    arithmetic (odtEntrySizeDaq minus the timestamp's wire size, both uint8/uint16) would underflow
    instead: Xcp_DTOCmdDaqSetDaqListMode's capacity guard becomes a comparison against a wrapped
    ~65535 that can never trip, and Xcp_DaqOdtEntryBudget saturates to 255, so WRITE_DAQ would
    accept far more than the 7-byte frame buffer holds -- an out-of-bounds write once
    Xcp_DaqSampleOdt (source/Xcp_DaqRuntime.c) actually stores the timestamp there. The schema's
    max_dto minimum of 8 keeps a real, schema-validated build from reaching this configuration, but
    this harness deliberately bypasses the schema, the same way every other test in this file's
    UndefinedError cluster does."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(max_dto=7, identification_field_type='RELATIVE_WORD_ALIGNED',
                              timestamp=timestamp(size='DWORD')))


def test_generation_fails_when_an_event_has_an_empty_triggered_daq_list_ref():
    """An empty triggered_daq_list_ref would emit a zero-length C array
    (Xcp_EventChannelDaqListRef...[0x00u]) -- a GCC extension, an ISO C constraint violation, and
    rejected by MISRA and several embedded toolchains. The schema has no minItems to catch it.

    name='EVT1': without it, this configuration would also trip the newer publish_names guard,
    which source_cfg.c.jinja2 currently checks after the empty-ref guard -- so this test would
    keep passing, for the wrong reason, if that ordering were ever reversed or the empty-ref
    guard itself were deleted."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(daqs=(daq(name='DAQ1'),),
                              events=(event(name='EVT1', triggered_daq_list_ref=[]),)))


def test_generation_fails_when_a_dynamic_pool_holds_no_daq_lists():
    """The DAQ_DYNAMIC half of the guard above, which is one guard on daq_list_ref_count rather
    than two. daq_count's schema minimum is 0 and every event channel references the whole pool,
    so daq_count 0 emits the same zero-length Xcp_EventChannelDaqListRef0000[0x00u] that an empty
    triggered_daq_list_ref does under DAQ_STATIC.

    Not about the ODT and ODT-entry arrays, which daq_count 0 also makes zero-length: `max_odt: 0`
    has always been allowed to do that, and source/Xcp_Daq.c documents it above Xcp_OdtUsedBytes
    as tolerated. This asserts only the event-channel array, which the static configuration has
    always been refused for."""
    with pytest.raises(UndefinedError):
        XcpTest(dynamic_config(daq_count=0))


def test_generation_fails_when_write_daq_multiple_is_enabled_with_max_cto_below_ten():
    """1.6.4.1.2.1: 'If the optional command WRITE_DAQ_MULTIPLE is used, the requirement
    MAX_CTO >= 10 has to be fulfilled.' A single element is 8 bytes after a 2-byte header, so a
    smaller MAX_CTO cannot carry even one."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(max_cto=9, xcp_write_daq_multiple_api_enable=True))


def test_generation_fails_when_publish_names_is_set_but_an_event_has_no_name():
    """publish_names defaults to True (test/parameter.py, matching protocol_layer.publish_names'
    own schema default), and event()'s own default omits "name" entirely -- see its comment --
    so this is what actually fires script/source_cfg.c.jinja2's guard rather than the helper
    inventing a name that would paper over a real integrator misconfiguration."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(publish_names=True, events=(event(triggered_daq_list_ref=['DAQ1']),)))


@pytest.mark.parametrize('config, why', (
    pytest.param(lambda: dynamic_config(daq_count=256, odt_count=1, odt_entries_count=1),
                 'daq_count above the uint8 MAX_DAQ_LIST field',
                 id='daq_count = 256'),
    pytest.param(lambda: DefaultConfig(xcp_free_daq_api_enable=True),
                 'FREE_DAQ enabled under a STATIC configuration',
                 id='FREE_DAQ under STATIC'),
    pytest.param(lambda: DefaultConfig(daq_config_type='DYNAMIC',
                                       xcp_free_daq_api_enable=True,
                                       xcp_alloc_daq_api_enable=False,
                                       xcp_alloc_odt_api_enable=True,
                                       xcp_alloc_odt_entry_api_enable=True),
                 'ALLOC_DAQ disabled under DYNAMIC',
                 id='ALLOC_DAQ disabled under DYNAMIC'),
))
def test_generation_refuses_incoherent_dynamic_configurations(config, why):
    """The guard messages are documentation, not output: raise() is not a registered Jinja global
    in bsw_code_gen, so referencing it aborts rendering with UndefinedError and the string never
    reaches the caller. These assert that generation fails, never that a message matches -- the
    same reasoning as the cluster of guard tests above, whose comment explains why UndefinedError
    is still worth naming instead of a bare Exception.

    The first row goes through dynamic_config so that daq_count is the *only* thing wrong with it:
    built from a bare DefaultConfig it would trip the ALLOC-APIs-disabled guard as well, and pass
    for a reason that has nothing to do with the ceiling it is named after. The other two rows are
    the opposite case -- what is wrong with them is which API flags are set, so they have to set
    those flags themselves rather than let the helper supply a coherent set."""
    with pytest.raises(UndefinedError):
        XcpTest(config())


def test_generation_accepts_the_largest_dynamic_pool_the_uint8_max_daq_list_field_can_hold():
    """The boundary above, from the accepting side: 255 lists are representable in the uint8
    MAX_DAQ_LIST byte GET_DAQ_EVENT_INFO transmits, so the guard is `> 255` and not `>= 255`."""
    handle = XcpTest(dynamic_config(daq_count=255, odt_count=1, odt_entries_count=1))

    assert handle.config.lib.Xcp[0].general.daqCount == 255
    assert handle.config.lib.Xcp[0].config.daqListCount == 255
    assert handle.config.lib.Xcp[0].config.eventChannel[0].maxDaqList == 255


@pytest.mark.parametrize('count', (8, 16))
def test_the_daq_list_count_is_emitted_as_a_hexadecimal_literal(count):
    """script/source_cfg.c.jinja2 emitted daqListCount as '%04Xu' -- with no 0x -- which makes a
    leading-zero literal OCTAL. One and two DAQ lists are the same number in octal as in hex, and
    no configuration in the suite had ever declared more, so nothing showed it: 8 is not a valid
    octal constant at all (the build fails), and 16 emits 0010u, which is octal 8 -- a module that
    silently reports half its DAQ lists to the GET_DAQ_ID scan in source/Xcp_Std.c, the one place
    that reads this field. A 255-list dynamic pool emitted 00FFu and would not compile, which is
    what found it; both counts here are pinned because the two failure modes are different."""
    handle = XcpTest(DefaultConfig(daqs=tuple(daq(name='DAQ{}'.format(i)) for i in range(count)),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ0']),)))

    assert handle.config.lib.Xcp[0].config.daqListCount == count


def test_generation_refuses_daq_lists_declared_alongside_a_dynamic_pool():
    """A DAQ_DYNAMIC configuration declares no lists -- the master allocates them out of the pool
    -- so a `daqs` entry is an integrator saying two incompatible things at once. Silently
    ignoring it would leave them believing they had configured a list that will never exist."""
    config = dynamic_config()
    config['configurations'][0]['daqs'] = [daq(name='DAQ1')]

    with pytest.raises(UndefinedError):
        XcpTest(config)


def test_generation_refuses_a_dynamic_pool_declared_under_a_static_configuration():
    """The mirror of the test above. A `daq_dynamic` block under DAQ_STATIC configures a pool
    nothing will ever allocate from, and its dimensions would silently go nowhere."""
    config = DefaultConfig()
    config['configurations'][0]['daq_dynamic'] = {"daq_count": 4,
                                                  "odt_count": 8,
                                                  "odt_entries_count": 16,
                                                  "pdu_mapping": "XCP_PDU_ID_TRANSMIT"}

    with pytest.raises(UndefinedError):
        XcpTest(config)


def test_a_stim_capable_pool_reserves_a_slot_for_every_odt():
    """DD43. A STIM buffer must exist for any list that might receive, and under a dynamic pool
    there is no per-list type -- SET_DAQ_LIST_MODE sets direction at runtime. The pool therefore
    declares its own direction, mirroring daqs[].type for a static list.

    A DAQ-typed pool generates no slots at all, which is what keeps a DAQ-only build paying
    nothing for stimulation it never uses.

    Reads Xcp_Rt[...] the way every other test in the suite does -- handle.lib, the module under
    test linked against the generated runtime, not handle.config.lib, which is the generated
    CONFIGURATION module and carries no Xcp_Rt at all."""
    handle = XcpTest(stim_config(daq_count=2, odt_count=3, odt_entries_count=2))
    rt = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef]

    assert rt.stimSlotCount == 2 * 3

    for daq_idx in range(2):
        # The pool is rectangular and every list in it can receive, so the prefix sum
        # stimSlotBase carries collapses to daq_idx * odt_count here. Asserted rather than
        # assumed, because it is the closed form that does NOT survive the static model --
        # see test_a_static_list_that_can_receive_starts_where_its_own_slots_do.
        assert handle.lib.Xcp_Ptr.config.daqList[daq_idx].stimSlotBase == daq_idx * 3

        for odt_idx in range(3):
            slot = rt.stimSlot[handle.lib.Xcp_Ptr.config.daqList[daq_idx].stimSlotBase + odt_idx]
            assert slot.length == 0, 'a freshly generated slot holds nothing'


def test_a_daq_only_pool_reserves_no_stim_slots():
    """The other half of DD43: declaring `DAQ` must cost nothing.

    The second half of this test drops the key entirely, because `type` is deliberately absent
    from the schema's required list for daq_dynamic -- the default is what keeps every dynamic
    configuration written before stimulation existed valid, and DAQ-only. Without this, both
    templates' `| default('DAQ')` would be reached by no test at all."""
    handle = XcpTest(dynamic_config(daq_count=2, odt_count=3, odt_entries_count=2))

    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 0

    config = dynamic_config(daq_count=2, odt_count=3, odt_entries_count=2)
    del config['configurations'][0]['daq_dynamic']['type']
    handle = XcpTest(config)

    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 0


def test_a_dynamic_pool_generates_lists_of_its_declared_type():
    """script/source_cfg.c.jinja2's DYNAMIC branch hard-coded XcpDaqListType to DAQ for every pool
    slot regardless of daq_dynamic.type, predating pools having a type at all. source/Xcp.c's
    Xcp_CanIfRxIndication accepts a received PDU on a DAQ list only when its type is STIM or
    DAQ_STIM, so with every slot typed DAQ no dynamically allocated list could ever accept a
    stimulation frame no matter what the pool declared -- valid_pdu_id stayed FALSE and reception
    was dead for every dynamic STIM pool, a path no other test exercises. Two slots, both checked:
    the bug was per-slot, the same hard-coded literal emitted on every iteration of the loop."""
    handle = XcpTest(stim_config(daq_count=2, odt_count=1, odt_entries_count=1))

    for i in range(2):
        assert handle.lib.Xcp_Ptr.config.daqList[i].type == handle.lib.DAQ_STIM


def test_a_static_list_that_can_receive_starts_where_its_own_slots_do():
    """DD43. The case with no closed form, and the reason Xcp_DaqListType carries stimSlotBase at
    all rather than the addressing being computed from the list number.

    A static configuration reserves slots for its RECEIVING lists only, so a DAQ list advances the
    base by nothing however many ODTs it owns. Here list 0 is a DAQ list with two ODTs, and the two
    receiving lists that follow it start at 0 and 3 -- not at 2 and 5, which is where summing over
    every list would put them, and not at 1 * odt_count and 2 * odt_count, which is where the
    rectangular rule a dynamic pool obeys would. Both wrong answers are indistinguishable from the
    right one under a dynamic pool, which is why this case is pinned separately.

    A DAQ list's own base is 0 and is never read: nothing addresses a stimulation slot for a list
    whose direction excludes STIM."""
    handle = XcpTest(DefaultConfig(daqs=(daq(name='DAQ1', type='DAQ', max_odt=2),
                                         daq(name='DAQ2', type='DAQ_STIM', max_odt=3),
                                         daq(name='DAQ3', type='DAQ_STIM', max_odt=4)),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    daq_list = handle.lib.Xcp_Ptr.config.daqList

    assert daq_list[0].stimSlotBase == 0, 'a DAQ list reserves nothing, so it starts nowhere'
    assert daq_list[1].stimSlotBase == 0, 'the first receiving list starts at the front'
    assert daq_list[2].stimSlotBase == 3, "after the first receiving list's three ODTs"

    assert handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount == 3 + 4

    # The last slot the last list addresses is the last slot reserved: base plus its own ODTs
    # accounts for the array exactly, with nothing over-run and nothing stranded.
    assert daq_list[2].stimSlotBase + daq_list[2].maxOdt == \
        handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].stimSlotCount


def test_odt_entry_size_stim_is_reported_for_a_stim_capable_build():
    """DD44/§4. XcpOdtEntrySizeStim derives exactly as XcpOdtEntrySizeDaq does -- MAX_DTO less the
    identification field -- and was hard-coded 0x00u with the comment "STIM arrives in SP3"."""
    handle = XcpTest(stim_config(daq_count=1, odt_count=1, odt_entries_count=1, max_dto=8))

    assert handle.config.lib.Xcp[0].general.odtEntrySizeStim == \
        handle.config.lib.Xcp[0].general.odtEntrySizeDaq
    assert handle.config.lib.Xcp[0].general.odtEntrySizeStim != 0

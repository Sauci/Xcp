#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP4c Task 2: GET_SECTOR_INFO (0xCD) and the flash sector configuration model it reports from
(design doc docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md, DD87/DD88). Unlike
PROGRAM_VERIFY (pgm_verify_test.py, Task 1), this command calls no integrator callback at all --
it is read-only reporting over Xcp_SectorType (interface/Xcp_Types.h), a configuration array with
no runtime state of its own, so every test below asserts on wire bytes and on the configured
sector() fixtures directly, with no mock to inspect."""

import pytest

from jinja2.exceptions import UndefinedError

from .parameter import DefaultConfig, sector, u32_to_array
from .conftest import XcpTest
from .pgm_deferred_test import pgm_handle
from .pgm_session_test import send


#: Three sectors with all five reported fields distinct per sector, and clear/program sequence
#: numbers taken directly from 1.6.5.2.2's own worked example: cleared in order 0, 1, 2 while
#: programmed in order 5, 4, 3 -- an order that differs from sector order AND from each other, so
#: a handler that assumes the two sequences move together, or match sector order, is caught by
#: test_sequence_numbers_are_reported_verbatim_using_the_specifications_own_example below.
THREE_SECTORS = (
    sector(start_address=0x00001000, length=0x00000010,
          clear_sequence_number=0x00, program_sequence_number=0x05, programming_method=0x01),
    sector(start_address=0x00002000, length=0x00000020,
          clear_sequence_number=0x01, program_sequence_number=0x04, programming_method=0x02),
    sector(start_address=0x00003000, length=0x00000030,
          clear_sequence_number=0x02, program_sequence_number=0x03, programming_method=0x03),
)


def get_sector_info(handle, mode, sector_number):
    """GET_SECTOR_INFO (0xCD), through send() (pgm_session_test.py): resets the mock, sends the
    request, pumps one Xcp_MainFunction, and returns the frame it produced (or None). Like
    GET_PGM_PROCESSOR_INFO (pgm_processor_info_test.py), this command never defers -- it calls no
    integrator callback and reports only this build's own fixed configuration -- so one
    main-function call is always enough to see the answer."""
    return send(handle, (0xCD, mode, sector_number))


@pytest.mark.parametrize('sector_number', (0, 1, 2))
def test_mode_0_returns_the_configured_start_address_and_sequence_numbers_and_method(sector_number):
    """Brief test 1. THREE_SECTORS gives every reported field a distinct value per sector, so a
    handler that returns the wrong sector's data -- always sector 0, an off-by-one index, the
    sectors read in reverse -- fails this for at least one of the three parametrised indices, not
    only for a single hard-coded one.

    Mutation: indexing Xcp_Ptr->config->sector[] with a fixed 0 passes only sector_number=0 and
    fails the other two; indexing with sector_number +/- 1 (off by one) fails all three, since each
    would then read its NEIGHBOUR's values instead of its own."""
    handle = pgm_handle(sectors=THREE_SECTORS)
    expected = THREE_SECTORS[sector_number]

    response = get_sector_info(handle, 0x00, sector_number)

    assert response[0] == 0xFF, 'setup: must be the positive response, not an error: %r' % (response,)
    assert response[1] == expected['clear_sequence_number'], \
        'byte 1 must be sector %d\'s own clear_sequence_number: %r' % (sector_number, response)
    assert response[2] == expected['program_sequence_number'], \
        'byte 2 must be sector %d\'s own program_sequence_number: %r' % (sector_number, response)
    assert response[3] == expected['programming_method'], \
        'byte 3 must be sector %d\'s own programming_method: %r' % (sector_number, response)
    assert response[4:8] == tuple(u32_to_array(expected['start_address'], 'LITTLE_ENDIAN')), \
        'bytes 4-7 (mode 0 SECTOR_INFO) must be sector %d\'s own start address: %r' \
        % (sector_number, response)


def test_mode_1_returns_the_length_in_bytes_at_an_address_granularity_wider_than_byte():
    """Brief test 2, DD87. address_granularity is WORD here (2 bytes), not this suite's own BYTE
    default: 1.0 reads mode 1's SECTOR_INFO in AG units, 1.1 reads it in bytes, and the two
    readings are numerically identical whenever AG is BYTE, so a test that never left AG=BYTE would
    pass against either interpretation and prove nothing about which one actually shipped.

    0x00001000 (4096 bytes) is a multiple of 2 (satisfying generation's own DD87 mod-AG check,
    exercised directly by test_generation_refuses_a_sector_length_that_is_not_a_multiple_of_the_
    address_granularity below) and, divided by the AG element size, reads back as 0x00000800 -- a
    different, smaller value a handler that wrongly converted to AG units before reporting would
    produce instead of the correct 0x00001000.

    Mutation: dividing sector_info by the AG element size before reporting it (the 1.0 reading,
    not this design's own 1.1 one) reports 0x00000800 here instead of 0x00001000 and fails this
    test, while leaving every AG=BYTE test elsewhere in this suite passing regardless -- which is
    exactly why DD87 requires this test to run at a wider AG."""
    handle = pgm_handle(address_granularity='WORD',
                        sectors=(sector(start_address=0x00004000, length=0x00001000,
                                       clear_sequence_number=0x07, program_sequence_number=0x09,
                                       programming_method=0x0A),))

    response = get_sector_info(handle, 0x01, 0x00)

    assert response[0] == 0xFF, 'setup: must be the positive response, not an error: %r' % (response,)
    assert response[4:8] == tuple(u32_to_array(0x00001000, 'LITTLE_ENDIAN')), \
        'bytes 4-7 (mode 1 SECTOR_INFO) must be the configured length in BYTES, not AG units: %r' \
        % (response,)


def test_a_sector_number_equal_to_max_sector_is_refused_err_segment_not_valid():
    """Brief test 3, DD88. MAX_SECTOR is len(THREE_SECTORS) == 3, so sector_number 3 is the first
    invalid index -- one past the last configured sector, [0, MAX_SECTOR) per 1.6.5.2.2. Answered
    ERR_SEGMENT_NOT_VALID (0x28), not the specification prose's own ERR_OUT_OF_RANGE (0x22): the
    specification contradicts itself here (1.6.5.2.2's prose vs. 1.7.3.2.5's own error row for this
    command), and DD88 resolves it in the listed code's favour, the same rule DD65 already
    established for PROGRAM_MAX's own self-contradictory length in SP4b.

    Mutation (this task's Step 6): answering ERR_OUT_OF_RANGE (0x22) instead of
    ERR_SEGMENT_NOT_VALID fails this test directly -- recorded in task-2-report.md."""
    handle = pgm_handle(sectors=THREE_SECTORS)

    response = get_sector_info(handle, 0x00, len(THREE_SECTORS))

    assert response[0:2] == (0xFE, 0x28), \
        'ERR_SEGMENT_NOT_VALID for SECTOR_NUMBER == MAX_SECTOR: %r' % (response,)


@pytest.mark.parametrize('mode', (0x02, 0xFF))
def test_a_mode_byte_other_than_0_or_1_is_refused_err_mode_not_valid(mode):
    """Brief test 4. 0x02 is the first value past the two defined modes; 0xFF is the opposite end
    of the byte range -- together they rule out an off-by-one range check (e.g. `mode > 0x02`, or a
    check that only catches values near one end) passing one boundary while missing the other.
    sector_number is 0, a valid index in THREE_SECTORS, so this exchange isolates the mode check
    from SECTOR_NUMBER validity -- test_a_sector_number_equal_to_max_sector_is_refused_err_segment_
    not_valid above is what isolates the reverse.

    Mutation: checking only `mode != 0x00` (silently treating every non-zero mode as mode 1, the
    same trap PROGRAM_CLEAR's own mode byte documents in pgm_clear_test.py) fails both parametrised
    cases here, since neither reaches ERR_MODE_NOT_VALID; a one-sided range check
    (e.g. `mode > 0x01` alone, dropping the lower bound) still fails both, since both values here
    are already above 0x01."""
    handle = pgm_handle(sectors=THREE_SECTORS)

    response = get_sector_info(handle, mode, 0x00)

    assert response[0:2] == (0xFE, 0x27), \
        'ERR_MODE_NOT_VALID for mode 0x%02X: %r' % (mode, response)


def test_max_sector_agrees_between_get_pgm_processor_info_and_a_get_sector_info_walk():
    """Brief test 5, the cross-command invariant design doc Section 4 calls out as "where this
    phase can go quietly wrong": GET_PGM_PROCESSOR_INFO's own MAX_SECTOR byte and the range
    GET_SECTOR_INFO actually accepts must agree, or a master enumerating sectors by
    GET_PGM_PROCESSOR_INFO's own count either walks off the end or stops short of a real one.

    Both halves are asserted in this one test, deliberately: a test checking only the byte, or only
    the walk, would not notice the two drifting apart -- one derived correctly and the other left
    stale, or the reverse. Mirrors pgm_processor_info_test.py's own
    test_get_pgm_processor_info_advertised_absolute_only_mode_matches_program_clear_refusing_
    functional_mode, which pins an analogous advertised-vs-enforced pair for PGM_PROPERTIES/
    PROGRAM_CLEAR instead of MAX_SECTOR/GET_SECTOR_INFO.

    Mutation (this task's Step 6): reverting GET_PGM_PROCESSOR_INFO's MAX_SECTOR byte to a
    hard-coded 0 fails the byte assertion directly (0 != 3) while every GET_SECTOR_INFO walk
    assertion below it still passes on its own -- recorded in task-2-report.md."""
    handle = pgm_handle(sectors=THREE_SECTORS)

    processor_info = send(handle, (0xCE,))
    assert processor_info[0] == 0xFF, \
        'setup: GET_PGM_PROCESSOR_INFO must succeed: %r' % (processor_info,)
    assert processor_info[2] == len(THREE_SECTORS), \
        'GET_PGM_PROCESSOR_INFO MAX_SECTOR must equal the configured sector count: %r' \
        % (processor_info,)
    # Confirmed before the next exchange, the same way pgm_processor_info_test.py's own
    # test_get_pgm_processor_info_is_answered_identically_from_xcp_pgm_idle_and_xcp_pgm_active
    # confirms between its own two exchanges: both this row and GET_SECTOR_INFO's own carry
    # XCP_INTERNAL_ERR_CMD_BUSY (source/Xcp.c), so an unconfirmed response left occupying
    # cto_response would leave the walk below with nothing transmitted at all, not merely a wrong
    # answer -- SWS_Xcp_00859's one-frame transmit pipeline, not a defect in the walk itself.
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    for sector_number in range(len(THREE_SECTORS)):
        response = get_sector_info(handle, 0x00, sector_number)
        assert response[0] == 0xFF, \
            'sector %d, inside [0, MAX_SECTOR), must succeed: %r' % (sector_number, response)
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    walked_off_the_end = get_sector_info(handle, 0x00, len(THREE_SECTORS))
    assert walked_off_the_end[0:2] == (0xFE, 0x28), \
        'sector_number == MAX_SECTOR must still be refused, even after the walk above: %r' \
        % (walked_off_the_end,)


def test_sequence_numbers_are_reported_verbatim_using_the_specifications_own_example():
    """Brief test 6. 1.6.5.2.2's own worked example clears three sectors in order 0, 1, 2 while
    programming them in order 5, 4, 3 -- an order that differs from sector order and from the clear
    order, ruling out a handler that assumes the two sequences move together or match sector order.
    THREE_SECTORS is built with exactly this example's own numbers (module docstring above), so
    this test both exercises that data directly and pins the example itself, in case a future edit
    to the shared fixture drifts away from it without anyone noticing."""
    handle = pgm_handle(sectors=THREE_SECTORS)

    assert tuple(s['clear_sequence_number'] for s in THREE_SECTORS) == (0x00, 0x01, 0x02), \
        'setup: THREE_SECTORS must still carry 1.6.5.2.2\'s own clear order'
    assert tuple(s['program_sequence_number'] for s in THREE_SECTORS) == (0x05, 0x04, 0x03), \
        'setup: THREE_SECTORS must still carry 1.6.5.2.2\'s own program order'

    for sector_number, expected in enumerate(THREE_SECTORS):
        response = get_sector_info(handle, 0x00, sector_number)
        assert response[1] == expected['clear_sequence_number'], \
            'sector %d clear_sequence_number, reported verbatim: %r' % (sector_number, response)
        assert response[2] == expected['program_sequence_number'], \
            'sector %d program_sequence_number, reported verbatim: %r' % (sector_number, response)
        # Confirmed before the next sector's own exchange -- see
        # test_max_sector_agrees_between_get_pgm_processor_info_and_a_get_sector_info_walk's
        # identical comment above for why an unconfirmed response blocks the next one entirely.
        handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))


def test_generation_refuses_a_sector_length_that_is_not_a_multiple_of_the_address_granularity():
    """DD87's build-time rule, not one of the six tests the brief enumerates but added for the same
    reason test/daq_configuration_test.py pins its own generation-time guards (module docstring
    there): a `raise(...)` with nothing asserting it ever fires is a comment with extra steps.
    1.1/1.6.5.2.2 requires "Length mod AG = 0" for the length GET_SECTOR_INFO's mode 1 reports in
    bytes (design doc DD87), and script/source_cfg.c.jinja2 turns that into a generation refusal
    rather than leaving it as a comment for GET_SECTOR_INFO's own handler to trust.

    address_granularity WORD (2 bytes) and a configured length of 3 -- odd, not a multiple of 2 --
    trips it. `raise(...)` is not a registered Jinja global anywhere in that template (see its own
    comment at the FIRST_PID guard, or daq_configuration_test.py's identical note above its own
    four raise-based tests), so this -- like every other generation guard in the file -- surfaces as
    jinja2.exceptions.UndefinedError, not as a message-carrying exception; match= cannot narrow it
    for the same reason it cannot narrow those tests either.

    Mutation: deleting this guard (or checking `length % AG` against the wrong operand, e.g.
    `address_granularity_bytes % sector.length`) lets DefaultConfig() with this exact sectors=
    argument generate cleanly instead of raising, failing this test."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(programming_enabled=True,
                              address_granularity='WORD',
                              sectors=(sector(start_address=0x00001000, length=3,
                                             clear_sequence_number=0x00,
                                             program_sequence_number=0x00,
                                             programming_method=0x00),)))

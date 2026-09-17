#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Xcp_CTOErrorMatrix against XCP part 2 - Protocol Layer Specification 1.1/1.7.3.2.1.

**Why this test parses C source instead of exercising behaviour.** The matrix is read in exactly
three places, all in Xcp_CanIfRxIndication, and only for three of its bits:

    Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_CMD_BUSY
    Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_CMD_SYNTAX
    Xcp_CTOErrorMatrix[pid] & XCP_INTERNAL_ERR_PGM_ACTIVE

Every other bit is written and never read, so no behavioural test can observe it. The table is
documentation encoded as data, and until this test it was verified by nothing at all -- which is how
it stayed 1.0-era for months, and how four STD rows were still wrong after a change that set out to
correct exactly them (conformance review finding R1,
docs/superpowers/specs/2026-09-17-xcp-1-1-conformance-review.md).

The reference below is 1.1/1.7.3.2.1 read from the PDF's own glyph-enciphered text layer, not the
OCR sidecar, which has been wrong about three separate tables including this one. Where the module
deliberately carries a code 1.1 does not list, or omits one it does, the deviation must be declared
in DECLARED_DEVIATIONS with its reason -- an undeclared difference fails."""

import os
import re

SOURCE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'source', 'Xcp.c')

# 1.1/1.7.3.2.1, one entry per standard command. Timeouts are not codes and are omitted.
# CONNECT's row is CONNECT(NORMAL)'s: 1.1 splits the two modes, and this table has one row per PID.
SPEC_STD = {
    '0xFF': ('CONNECT', {'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xFE': ('DISCONNECT', {'CMD_BUSY', 'PGM_ACTIVE'}),
    '0xFD': ('GET_STATUS', {'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xFC': ('SYNCH', {'CMD_SYNCH', 'CMD_UNKNOWN', 'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xFB': ('GET_COMM_MODE_INFO', {'CMD_BUSY', 'CMD_SYNTAX', 'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xFA': ('GET_ID', {'CMD_BUSY', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF9': ('SET_REQUEST', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                             'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF8': ('GET_SEED', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                          'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF7': ('UNLOCK', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                        'ACCESS_LOCKED', 'SEQUENCE', 'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF6': ('SET_MTA', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                         'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF5': ('UPLOAD', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                        'ACCESS_DENIED', 'ACCESS_LOCKED', 'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF4': ('SHORT_UPLOAD', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                              'ACCESS_DENIED', 'ACCESS_LOCKED', 'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF3': ('BUILD_CHECKSUM', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_UNKNOWN', 'CMD_SYNTAX',
                                'OUT_OF_RANGE', 'ACCESS_DENIED', 'ACCESS_LOCKED',
                                'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF2': ('TRANSPORT_LAYER_CMD', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                                     'RES_TEMP_NOT_ACCESSIBLE'}),
    '0xF1': ('USER_CMD', {'CMD_BUSY', 'PGM_ACTIVE', 'CMD_SYNTAX', 'OUT_OF_RANGE',
                          'RES_TEMP_NOT_ACCESSIBLE'}),
}

# Every place the module knowingly differs from the table above, with the reason. Keyed by
# (pid, arm) where arm is 'ungated' or 'MACRO=ON'/'MACRO=OFF'.
DECLARED_DEVIATIONS = {
    ('0xF7', 'ungated'): (
        {'GENERIC'}, set(),
        "DD76: UNLOCK answers ERR_GENERIC when the integrator's Xcp_CalcKey cannot compute a key at "
        "all. None of the seven codes 1.1 lists fits that -- ERR_ACCESS_LOCKED, which the sibling "
        "branch answers, means the key was WRONG. 1.1/1.7.3 provides for off-row codes (DD132)."),
    ('0xF1', 'ungated'): (
        {'GENERIC'}, set(),
        "DD130: USER_CMD answers ERR_GENERIC with a detail WORD when the integrator's callback "
        "overruns MAX_CTO. Every code 1.1 lists for this row blames the master's request for what "
        "the slave's own extension did."),
    ('0xFA', 'ungated'): (
        {'OUT_OF_RANGE'}, set(),
        "DD110, and conformance review finding R2: GET_ID answers ERR_OUT_OF_RANGE for an "
        "identification type in 5..127, which names no type at all. 1.1/1.7.3.2.1's GET_ID row does "
        "NOT list it -- Xcp_Std.c claimed it did until R2 -- so this is an off-row answer under "
        "1.1/1.7.3, not compliance."),
    ('0xF6', 'XCP_FLASH_PROGRAMMING_ENABLED=ON'): (
        set(), {'PGM_ACTIVE'},
        "DD51: 1.1/1.6.5.1.1 requires SET_MTA to stay available DURING a programming sequence, and "
        "one matrix bit governs all four ERR_PGM_ACTIVE triggers, so carrying it would make the "
        "gate refuse the command the specification requires to remain reachable."),
    ('0xF5', 'XCP_FLASH_PROGRAMMING_ENABLED=ON'): (
        set(), {'PGM_ACTIVE'}, "DD51, as for SET_MTA above: UPLOAD is one of the seven commands "
                               "1.1/1.6.5.1.1 requires during a programming sequence."),
    ('0xF3', 'XCP_FLASH_PROGRAMMING_ENABLED=ON'): (
        set(), {'PGM_ACTIVE'}, "DD51, as for SET_MTA above: BUILD_CHECKSUM is one of the seven "
                               "commands 1.1/1.6.5.1.1 requires during a programming sequence."),
}


def parse_matrix():
    """Every Xcp_CTOErrorMatrix row, as {pid: {arm: {code, ...}}}.

    The #if/#else arms are tracked separately and deliberately. A parser that collapses them keeps
    whichever appears last in the file, which for the PID table reports nineteen commands as
    unimplemented and for this table hides a difference between the two builds -- both mistakes this
    review made before writing them down."""
    with open(SOURCE) as fp:
        src = fp.read()

    start = src.index('static const uint32_least Xcp_CTOErrorMatrix[0x100u]')
    body = src[start:src.index('};', start)]

    rows, gate = {}, []
    for line in body.split('\n'):
        stripped = line.strip()
        if stripped.startswith('#if'):
            macro = re.search(r'(XCP_\w+)', stripped)
            gate.append([macro.group(1) if macro else '?', False])
            continue
        if stripped.startswith('#else'):
            if gate:
                gate[-1][1] = True
            continue
        if stripped.startswith('#endif'):
            if gate:
                gate.pop()
            continue

        marker = re.search(r'/\* ([A-Z_0-9]+) ?(0x[0-9A-F]{2})', stripped)
        if marker and stripped.startswith(('XCP_INTERNAL', '0x00u')):
            arm = 'ungated' if not gate else '%s=%s' % (gate[-1][0], 'OFF' if gate[-1][1] else 'ON')
            codes = set(re.findall(r'XCP_INTERNAL_ERR_([A-Z_]+)', stripped))
            rows.setdefault(marker.group(2), {})[arm] = codes
    return rows


def test_every_standard_command_row_matches_1_1():
    """Each STD row must hold exactly what 1.1/1.7.3.2.1 lists, plus or minus only what
    DECLARED_DEVIATIONS accounts for with a reason."""
    rows = parse_matrix()
    problems = []

    for pid, (name, expected) in sorted(SPEC_STD.items(), reverse=True):
        arms = rows.get(pid)
        if not arms:
            problems.append('%s %s: no row found in Xcp_CTOErrorMatrix' % (pid, name))
            continue

        for arm, actual in sorted(arms.items()):
            extra_ok, missing_ok, _ = DECLARED_DEVIATIONS.get((pid, arm), (set(), set(), ''))

            unlisted = actual - expected - extra_ok
            absent = expected - actual - missing_ok

            if unlisted:
                problems.append(
                    '%s %s [%s] carries %s, which 1.1/1.7.3.2.1 does not list for it and no entry '
                    'in DECLARED_DEVIATIONS accounts for'
                    % (pid, name, arm, ', '.join('ERR_' + c for c in sorted(unlisted))))
            if absent:
                problems.append(
                    '%s %s [%s] is missing %s, which 1.1/1.7.3.2.1 lists for it'
                    % (pid, name, arm, ', '.join('ERR_' + c for c in sorted(absent))))

    assert not problems, 'Xcp_CTOErrorMatrix disagrees with 1.1/1.7.3.2.1:\n  ' + '\n  '.join(problems)


def test_the_parser_sees_both_arms_of_a_gated_row():
    """A guard on the check above rather than on the module. If parse_matrix silently collapsed the
    preprocessor arms, test_every_standard_command_row_matches_1_1 would still pass while checking
    only half of what ships -- the same way a naive parse of Xcp_PIDTable reports nineteen commands
    as unimplemented. SET_MTA is gated and its two arms differ, so it proves the arms are kept
    apart."""
    arms = parse_matrix()['0xF6']

    assert set(arms) == {'XCP_FLASH_PROGRAMMING_ENABLED=ON', 'XCP_FLASH_PROGRAMMING_ENABLED=OFF'}, \
        'SET_MTA is gated by XCP_FLASH_PROGRAMMING_ENABLED and both arms must be parsed, got %r' % (
            sorted(arms),)
    assert arms['XCP_FLASH_PROGRAMMING_ENABLED=ON'] != arms['XCP_FLASH_PROGRAMMING_ENABLED=OFF'], \
        'the two arms differ by ERR_PGM_ACTIVE (DD51); identical sets mean they were collapsed'

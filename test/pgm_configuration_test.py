#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from bsw_code_gen import BSWCodeGen

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


PGM_PIDS = ((0xD2, 'PROGRAM_START'), (0xD1, 'PROGRAM_CLEAR'), (0xD0, 'PROGRAM'),
            (0xCF, 'PROGRAM_RESET'), (0xCE, 'GET_PGM_PROCESSOR_INFO'), (0xCD, 'GET_SECTOR_INFO'),
            (0xCC, 'PROGRAM_PREPARE'), (0xCB, 'PROGRAM_FORMAT'), (0xCA, 'PROGRAM_NEXT'),
            (0xC9, 'PROGRAM_MAX'), (0xC8, 'PROGRAM_VERIFY'))

#: A gate-on shape with PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX all off, so every PGM test sharing
#: this dict reads the same way regardless of which of those three commands' own test file
#: (pgm_clear_test.py, pgm_program_test.py) exercises it with its own handle instead. Mirrors
#: pgm_deferred_test.py's own pgm_handle() and exists for the same reason: since SP4b Task 3
#: deleted DD69's generation guard entirely (all three commands now exist), this is no longer the
#: only gate-on shape that generates -- xcp_program_clear_api_enable, xcp_program_api_enable and
#: xcp_program_max_api_enable all True now generate cleanly too (config/xcp.json's own default,
#: test/parameter.py) -- but it is still the shape every test below wants, isolating PGM's
#: generated ctoInfo rows and CONNECT's own resource bit from the three commands' own behaviour.
GATE_ON = dict(programming_enabled=True,
               xcp_program_clear_api_enable=False,
               xcp_program_api_enable=False,
               xcp_program_max_api_enable=False)


def exchange(handle, request, length=8):
    # reset_mock() first, and this is the sixth place in this sub-project that needed it (the
    # final review's finding 8). handle.can_if_transmit.call_args is the LAST call, not this
    # exchange's: safe for the first PID in a sweep, because connect() leaves a 0xFF frame behind
    # that no (0xFE, 0x20) assertion could match, and unsafe from the second on -- ten of the
    # eleven assertions in the sweep below expect the same (0xFE, 0x20) from every PID, so a module
    # that silently transmitted nothing for one of them would be handed the previous PID's answer
    # and pass. Resetting here makes each assertion a statement about the frame ITS OWN request
    # produced.
    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:length])


def test_the_default_configuration_does_not_advertise_flash_programming():
    """D10. The shipped config/xcp.json set CONNECT's PGM bit (resource byte 0x15) while every one
    of the eleven PGM PIDs answered ERR_CMD_UNKNOWN -- an advertisement with nothing behind it,
    the same class as SP3's advertised-but-ungated STIM resource.

    Both halves are asserted on ONE handle. The bit alone would also read 0 on a build that had
    simply disabled the commands by hand, and the ERR_CMD_UNKNOWN sweep alone would pass on a
    build that advertised nothing at all -- it is the pair, from a default configuration, that
    says the advertisement matches the implementation."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    resource = handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01]

    assert (resource & 0x10) == 0x00, \
        'CONNECT must not advertise flash programming in a build that implements none'
    for pid, name in PGM_PIDS:
        assert exchange(handle, (pid,) + (0x00,) * 7)[0:2] == (0xFE, 0x20), \
            '%s answers ERR_CMD_UNKNOWN with the gate off' % name


def test_the_gate_on_build_still_does_not_advertise_flash_programming():
    """GATE_ON's own self-consistency check. Final-review finding 3's generation guard (DD69) is
    gone as of this task -- deleted term by term as SP4b implemented PROGRAM_CLEAR (Task 2), then
    PROGRAM and PROGRAM_MAX (Task 3) -- so this no longer states a ceiling on what any build can
    advertise (test/connect_test.py's restored
    test_connect_sets_the_resource_pgm_bit_according_to_enabled_apis, DD60, proves the bit reads
    TRUE for a build that enables all three). What this still asserts is narrower and remains true:
    GATE_ON itself -- the fixture nearly every other test in this file builds on, deliberately
    holding all three commands off so it can isolate PGM's OTHER generated rows and CONNECT's
    resource bit from those three commands' own behaviour -- does what its own name promises."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **GATE_ON))
    connect(handle)

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x10) == 0x00, \
        'GATE_ON must not advertise flash programming, since it holds all three commands off'


def test_the_three_pgm_advertised_commands_answer_err_cmd_unknown_when_their_own_keys_are_disabled():
    """The other half of the pair above, and the half that says the advertisement matches the
    implementation rather than merely that both are absent.

    test_the_default_configuration_does_not_advertise_flash_programming makes this claim for the
    gate-OFF build, where every PGM command is unimplemented. Here the gate is ON and seven of the
    eleven commands really do exist -- PROGRAM_START, PROGRAM_RESET, PROGRAM_PREPARE, and as of
    SP4b, PROGRAM_CLEAR (Task 2), PROGRAM and PROGRAM_MAX (Task 3) -- exercised at length in
    pgm_deferred_test.py, pgm_session_test.py, pgm_clear_test.py and pgm_program_test.py. GATE_ON
    still holds all three of CONNECT's own reads disabled by their own keys, though, so the sweep
    below is over those three: they must still answer ERR_CMD_UNKNOWN, which is what makes the
    withheld advertisement above the truth about THIS build and not an accident of it. All three
    answer it for the identical reason now, unlike before Task 3: GATE_ON leaves their own
    xcp_..._api_enable keys False, so each ctoInfo entry is disabled and dispatch never reaches
    its (real, existing) handler at all -- the same wire answer a genuinely unimplemented command
    gets, which is the property test_every_pgm_ctoinfo_entry_generates_disabled_with_the_gate_off's
    own docstring names directly. pgm_clear_test.py and pgm_program_test.py are where the three
    handlers are actually exercised, on handles that enable them."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **GATE_ON))
    connect(handle)

    for pid, name in ((0xD1, 'PROGRAM_CLEAR'), (0xD0, 'PROGRAM'), (0xC9, 'PROGRAM_MAX')):
        assert exchange(handle, (pid,) + (0x00,) * 7)[0:2] == (0xFE, 0x20), \
            '%s must answer ERR_CMD_UNKNOWN while its own api_enable key is disabled' % name


def test_the_gate_overrides_the_api_keys():
    """DD59's second conjunct. A command whose handler is not compiled must not be advertised as
    enabled, however its own key is set -- D10 restated per command. Without this term, an
    integrator who enabled the three API keys without enabling the feature would get the
    advertisement back and nothing behind it.

    A gate-off build has no PGM handler for the advertisement to be wrong about, so the same three
    keys generate cleanly here -- and a guard mistakenly written as "refuse these keys", full stop,
    rather than the conjunction with programming.enabled, would fail this test."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   programming_enabled=False,
                                   xcp_program_clear_api_enable=True,
                                   xcp_program_api_enable=True,
                                   xcp_program_max_api_enable=True))
    connect(handle)

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x10) == 0x00


def _generated_source(config):
    """The Xcp_Cfg.c `config` generates, as text -- mirrors daq_configuration_test.py's own
    _generated_source helper (same name, same one-line body), needed here for the identical
    reason: some claims are about the GENERATED CONSTANT, not about anything a compiled, running
    module can be made to reveal on the wire."""
    return BSWCodeGen(config, os.environ['script_directory']).source_cfg


def test_every_pgm_ctoinfo_entry_generates_disabled_with_the_gate_off():
    """Design doc §9, acceptance criterion 1: 'A default build...is byte-for-byte identical to
    today's.' Task 6's own gate-off comparison (task-6-report.md) needs this at the level the wire
    cannot reach: D10 was a defect where the WIRE behaviour (ERR_CMD_UNKNOWN) was already correct,
    for the wrong reason. source/Xcp.c's own dispatcher treats 'ctoInfo disabled' and 'ctoInfo
    enabled but Xcp_PIDTable points at Xcp_CmdNotImplemented' identically -- both answer
    ERR_CMD_UNKNOWN (the commit titled 'fix: return ERR_CMD_UNKNOWN for unimplemented and disabled
    commands' made that unification deliberate) -- so test_the_default_configuration_does_not_
    advertise_flash_programming above, however many PIDs it sweeps, cannot tell a disabled entry
    apart from an enabled-but-unimplemented one. Reading the generated constant directly is the
    only way to pin which of the two this actually is.

    Confirmed against history rather than merely asserted (task-6-report.md carries the full
    diff): extracting script/source_cfg.c.jinja2, config/xcp.schema.json and config/xcp.json as
    they stood at 018116556c282df9fb0df7ef6691c3856f071398 -- the commit immediately before Task
    1's generator fix, 83cb11d967feffda21ebefc8b05fc7e51075b554 -- and running them through the
    same generator shows all ten of these bits (every PGM PID except PROGRAM_MAX, D11's one live
    term) read enabled (0x01u) unconditionally there, regardless of configuration. This test is
    what a regression back to that state would fail."""
    source = _generated_source(DefaultConfig())

    for pid, name in PGM_PIDS:
        marker = '%s 0x%02X' % (name, pid)
        matches = [line for line in source.splitlines() if marker in line]
        assert len(matches) == 1, \
            '%s must appear exactly once in the generated ctoInfo table' % marker
        assert '(0x00u << 0x07u) /* enable */' in matches[0], \
            '%s must generate disabled with the gate off: %r' % (marker, matches[0])


def test_program_ctoinfo_minimum_nibble_is_unchanged_with_the_gate_off():
    """Task 3 review, fix round 1, finding 4. Design doc Section 9, acceptance criterion 1's
    byte-for-byte claim is about the whole generated file, not merely the enable bit the test
    above and test_the_gate_touches_only_pgm_ctoinfo_rows below both check -- neither would have
    caught PROGRAM's own ctoInfo minimum-request nibble (the trailing 4 bits of the row) being
    emitted unconditionally at Task 3's new value (2), outside the programming.enabled
    conditional that already gates the enable and protected bits on the same line, so a gate-off
    build's generated Xcp_Cfg.c differed from a pre-Task-3 tree by that one byte even though the
    row stayed disabled and unread either way (source/Xcp.c tests the enable bit before ever
    reading this nibble). Fixed by keying the nibble on the identical conjunction the enable bit
    already tests, so a gate-off build (this test) and GATE_ON with PROGRAM's own key left False
    (test_the_gate_touches_only_pgm_ctoinfo_rows's own `unchanged` set) both keep the pre-Task-3
    value, 4 -- and only a build where PROGRAM is truly reachable renders the corrected value, 2.

    Checked directly against the generated line's own trailing token, which neither of this
    file's two other generator tests reads at all."""
    source = _generated_source(DefaultConfig())

    matches = [line for line in source.splitlines() if 'PROGRAM 0xD0' in line]
    assert len(matches) == 1, 'PROGRAM 0xD0 must appear exactly once in the generated ctoInfo table'
    assert '0x04u, /* PROGRAM 0xD0' in matches[0], \
        'the gate-off minimum nibble must stay the pre-Task-3 value (4), not become 2 merely ' \
        'because the row is unreachable either way: %r' % matches[0]


def test_program_next_ctoinfo_minimum_nibble_is_unchanged_with_the_gate_off():
    """Task 4 review, fix round 1, finding 2. The exact mistake
    test_program_ctoinfo_minimum_nibble_is_unchanged_with_the_gate_off above exists to catch,
    reintroduced for a different row: PROGRAM_NEXT's own ctoInfo minimum-request nibble was
    corrected from the SP4a-era placeholder 4 to the true value 3 (task-4-report.md), but emitted
    unconditionally, outside the `programming.enabled` conditional that already gates this row's
    own enable bit on the same line -- so a gate-off build's generated Xcp_Cfg.c differed from
    SP4a's by this one byte even though the row stayed disabled and unread either way (source/Xcp.c
    tests the enable bit before ever reading this nibble). Unlike PROGRAM 0xD0's own key, this row
    has no per-command api_enable term to conjoin (DD69/design Section 4: PROGRAM_NEXT adds no new
    callback), so the correct key is `programming.enabled` alone -- the identical condition its own
    enable bit already tests, one column to its own left.

    Fixed by keying the nibble on that same condition, so a gate-off build (this test) keeps the
    pre-Task-4 value, 4, and only a build where `programming.enabled` is true renders the corrected
    value, 3 (test_generation_accepts_the_pgm_resource_on_a_build_that_cannot_program and friends
    below exercise that side indirectly; the value itself, 3, is not in question here -- only its
    conditional placement is)."""
    source = _generated_source(DefaultConfig())

    matches = [line for line in source.splitlines() if 'PROGRAM_NEXT 0xCA' in line]
    assert len(matches) == 1, 'PROGRAM_NEXT 0xCA must appear exactly once in the generated ctoInfo table'
    assert '0x04u, /* PROGRAM_NEXT 0xCA' in matches[0], \
        'the gate-off minimum nibble must stay the pre-Task-4 value (4), not become 3 merely ' \
        'because the row is unreachable either way: %r' % matches[0]


def test_gate_off_output_does_not_depend_on_any_other_programming_setting():
    """Task 4 review, fix round 2. The two tests immediately above are hand-written siblings, one
    per row (PROGRAM 0xD0 from Task 3's own review, PROGRAM_NEXT 0xCA from this task's own fix
    round 1) -- each pins that ONE row's own minimum nibble against ONE way it could leak past the
    gate. The review checked directly whether that generalises, by keying a THIRD row's own
    minimum nibble (GET_SECTOR_INFO 0xCD) on something other than `programming.enabled` while the
    gate stayed off: every one of the 108 tests in this file still passed, because
    test_every_pgm_ctoinfo_entry_generates_disabled_with_the_gate_off only reads the enable bit and
    test_the_gate_touches_only_pgm_ctoinfo_rows only compares which LINES differ between gate-on
    and gate-off -- neither reads a value that stays constant across THAT comparison while still
    depending on something it should not. Two more hand-written siblings would only have moved the
    same gap to a fourth and fifth row; GET_SECTOR_INFO and GET_PGM_PROCESSOR_INFO both still have
    no sibling of their own after this test is added, and neither needs one.

    The property that actually closes the class, not merely one instance of it: with
    `programming.enabled` FALSE, source/Xcp.c's own dispatcher never reads a PGM row's ctoInfo
    fields beyond the enable bit it already tested false, so NOTHING else about a PGM row -- not
    its minimum nibble, not any other field this sub-project or a later one adds -- may depend on
    ANY other configuration value while the gate stays off. A baseline gate-off build is compared,
    byte for byte, against one variant per OTHER setting this command group's own implementation
    status could plausibly leak through -- `programming.max_block_size` moved to each of its two
    extremes, each of the TEN `xcp_program_*_api_enable` keys flipped away from its own default,
    each of the six `programming.*` PGM_PROPERTIES capability flags turned on, and a declared
    `programming.sectors` entry -- all with the gate itself left off throughout. Comparing the WHOLE
    generated file, not only the ctoInfo table, matches acceptance criterion 1's own scope (design
    doc Section 9): a leak could in principle land anywhere the generator touches, not only in the
    block this sub-project's own two siblings happen to read.

    **Final review F6: SP4c added eleven settings and extended this sweep by none, and that -- not
    correct gating -- is the only reason it kept passing.** Seven of the eleven were measured
    changing gate-off output when the sweep was finally extended: `pgmProperties` bits 2-7 carried no
    `programming.enabled` conjunct while bit 1 and `pgmClearFunctionalSupported` on the adjacent
    lines did (F4), and `maxSector` with the `Xcp_SectorConfig` array were ungated the same way (F5).
    The eleven axes are named individually below rather than folded into a loop over
    test/parameter.py's own keyword list, so that adding a twelfth setting without adding a variant
    is a visible omission in this dict rather than an invisible one in a helper.

    Two shapes of variant, and the difference matters: a flag whose DefaultConfig value is True is
    flipped False, and one whose default is False is flipped True. Flipping a False default "off"
    would compare the baseline against itself and pass unconditionally -- which is exactly how a
    sweep silently stops testing anything. `xcp_program_clear_functional_api_enable` and
    `xcp_program_write_functional_api_enable` are the two that default False, and they are varied
    INDIVIDUALLY here even though script/source_cfg.c.jinja2 refuses to generate one without the
    other: that DD92 guard is itself conjoined with `programming.enabled`, so with the gate off each
    flag alone generates cleanly, and one at a time is the stricter test. The both-on case is swept
    too, since that is the combination that actually sets a bit once the gate is on.

    `resource_protection_programming` is deliberately NOT one of the variants, and finding out why
    the hard way is exactly what building this test caught: it changes `protectedResource`'s own
    PGM bit (source/Xcp_Cfg.c) whether or not `programming.enabled` is true, by design -- a slave
    declares which resources need unlocking as a policy independent of whether the commands behind
    them exist yet, the same way GET_SEED/UNLOCK already read that bit for resources a given build
    does not implement at all. Including it as a variant made this test fail against CORRECT
    output on the very first run, which is worth recording so the same false lead is not
    rediscovered: resource protection is a different axis from command-implementation gating, and
    this property is about the latter only.

    Mutation-verified against two independent, unrelated leaks (task report), proving this is not
    a sibling of the two tests above with extra steps: keying GET_SECTOR_INFO 0xCD's own minimum
    nibble on `programming.max_block_size`, ungated on `programming.enabled` -- mirroring this
    task's own fix round 1 mistake, on a row and a setting neither hand-written sibling above ever
    names -- makes the `max_block_size` variant below fail; keying PROGRAM_FORMAT 0xCB's own
    minimum nibble on `xcp_program_prepare_api_enable` the same, ungated, way makes the
    corresponding api_enable variant fail instead. Both were reverted after."""
    baseline = _generated_source(DefaultConfig())

    variants = {
        'programming_max_block_size=1': DefaultConfig(programming_max_block_size=1),
        'programming_max_block_size=255': DefaultConfig(programming_max_block_size=255),
        # The six api keys this sweep has carried since Task 4, all of them True by default.
        'xcp_program_clear_api_enable=False': DefaultConfig(xcp_program_clear_api_enable=False),
        'xcp_program_api_enable=False': DefaultConfig(xcp_program_api_enable=False),
        'xcp_program_max_api_enable=False': DefaultConfig(xcp_program_max_api_enable=False),
        'xcp_program_start_api_enable=False': DefaultConfig(xcp_program_start_api_enable=False),
        'xcp_program_reset_api_enable=False': DefaultConfig(xcp_program_reset_api_enable=False),
        'xcp_program_prepare_api_enable=False': DefaultConfig(xcp_program_prepare_api_enable=False),
        # F6, axis 1-2 of eleven: SP4c's two new api keys that default True, so flipped False.
        'xcp_program_verify_api_enable=False': DefaultConfig(xcp_program_verify_api_enable=False),
        'xcp_program_format_api_enable=False': DefaultConfig(xcp_program_format_api_enable=False),
        # F6, axis 3-5: SP4c's two api keys that default False, so flipped TRUE -- individually
        # (legal with the gate off, see the docstring) and together.
        'xcp_program_clear_functional_api_enable=True':
            DefaultConfig(xcp_program_clear_functional_api_enable=True),
        'xcp_program_write_functional_api_enable=True':
            DefaultConfig(xcp_program_write_functional_api_enable=True),
        'both functional api keys=True':
            DefaultConfig(xcp_program_clear_functional_api_enable=True,
                          xcp_program_write_functional_api_enable=True),
        # F6, axis 6-11: the six PGM_PROPERTIES capability flags (DD89/DD90), all False by default.
        # Every one of these six was measured changing gate-off output before F4 gated
        # pgmProperties' bits 2-7 (script/source_cfg.c.jinja2).
        'programming_compression_supported=True':
            DefaultConfig(programming_compression_supported=True),
        'programming_compression_required=True':
            DefaultConfig(programming_compression_required=True),
        'programming_encryption_supported=True':
            DefaultConfig(programming_encryption_supported=True),
        'programming_encryption_required=True':
            DefaultConfig(programming_encryption_required=True),
        'programming_non_sequential_supported=True':
            DefaultConfig(programming_non_sequential_supported=True),
        'programming_non_sequential_required=True':
            DefaultConfig(programming_non_sequential_required=True),
        # F6, the eleventh axis: a declared sector. Measured before F5 gated maxSector and the
        # Xcp_SectorConfig array, this one variant moved SEVEN lines of gate-off output --
        # Xcp_SectorConfig00[0x01u] to [0x02u], five initialiser lines, and maxSector 0x00u to
        # 0x01u. `length` is a multiple of the default AG (BYTE) so DD87's own "Length mod AG = 0"
        # generation guard, which is deliberately NOT gated on programming.enabled, stays quiet.
        'sectors=[one sector]': DefaultConfig(sectors=(sector(start_address=0x08000000,
                                                             length=0x1000,
                                                             clear_sequence_number=1,
                                                             program_sequence_number=2,
                                                             programming_method=3),)),
    }

    # A guard on the sweep itself, not on the generator: a variant that does not actually differ from
    # the baseline CONFIGURATION would compare the baseline against itself and pass no matter what
    # the template did. Cheap to state, and it is the failure mode that let F4 and F5 through.
    for label, config in variants.items():
        assert config != DefaultConfig(), \
            '%s does not differ from DefaultConfig(), so it tests nothing' % label

    for label, config in variants.items():
        assert _generated_source(config) == baseline, \
            'programming.enabled is FALSE in both the baseline and this variant, so %s alone must ' \
            'not change a single byte of the generated output -- something programming-related ' \
            'reached Xcp_Cfg.c without the enable check source/Xcp.c relies on' % label


def test_the_gate_touches_only_pgm_ctoinfo_rows():
    """The other half of acceptance criterion 1: not merely that the disabled state above is
    correct, but that turning the gate on touches NOTHING else. A generator defect that shifted
    some unrelated byte whenever 'programming.enabled' flipped would pass every wire-level test in
    this suite -- all of it runs with the gate off -- and still violate 'byte-for-byte identical',
    which is a claim about the whole file, not about the eleven rows this sub-project added.

    Named for eleven rows until final-review finding 3; eight of them here, since this comparison's
    `on` config is GATE_ON, which forces PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX off deliberately --
    by GATE_ON's own choice now, not because the generator refuses any combination of them: DD69's
    guard is gone entirely as of SP4b Task 3, term by term as PROGRAM_CLEAR (Task 2), then PROGRAM
    and PROGRAM_MAX (Task 3) were implemented. GATE_ON keeps holding all three off regardless,
    because isolating the OTHER eight rows from these three commands' own behaviour is what this
    particular comparison needs, not because generation would refuse the alternative. The claim
    itself is unchanged -- nothing outside the PGM block may move when the gate flips -- and is
    asserted below as the exact set rather than as a number.

    Diffs the current generator's own output for the gate on vs off, rather than reaching back into
    git history for the comparison. The two questions are the same one as long as the template's
    non-PGM rows do not move, and this form does not ask every future test run to depend on git
    history being present and unrewritten -- something no other test in this suite does. The
    historical comparison was run by hand instead, twice: task-6-report.md carries Task 1's, and
    final-fix-report.md carries this round's, where the default build's generated Xcp_Cfg.c,
    Xcp_Cfg.h, Xcp_Rt.c and Xcp_Rt.h were confirmed byte-identical to 35c4877's despite
    config/xcp.json's PGM defaults changing and two guards being added to the template.

    Nine differing lines, not eight, since final review F4: Xcp_GeneralType's own maxBsPgm row
    (script/source_cfg.c.jinja2) is a second, genuine gate-on/gate-off difference outside the
    ctoInfo table entirely -- MAX_BS_PGM's per-configuration value, 0 whenever programming.enabled
    is false (F4's own gate-off invariant, guarded separately by
    test_gate_off_output_does_not_depend_on_any_other_programming_setting) and the real configured
    value once it is true. Caught here the moment F4's own fix landed: keying this row on
    programming.enabled alone (matching the ctoInfo rows) still left it differing between GATE_ON
    and gate-off, since GATE_ON's own programming.enabled IS true -- a real, correctly-gated
    difference this test's own pre-F4 assertion (`== len(PGM_PIDS) - len(unchanged)`, silently
    assuming every differing line is a ctoInfo row) was not yet written to expect."""
    off = _generated_source(DefaultConfig())
    on = _generated_source(DefaultConfig(xcp_program_start_api_enable=True,
                                         xcp_program_reset_api_enable=True,
                                         xcp_program_prepare_api_enable=True,
                                         **GATE_ON))

    off_lines = off.splitlines()
    on_lines = on.splitlines()
    assert len(off_lines) == len(on_lines), 'the gate must not add or remove any generated line'

    # Eight, not eleven, since final-review finding 3: this comparison's `on` config is GATE_ON,
    # which forces PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX off deliberately, so their rows are
    # identical on both sides and the ceiling on what the gate may touch drops to the other eight.
    # Asserting the exact set rather than a count keeps the claim from weakening as that number
    # moves: DD69's generator refusal is gone for all three now (Task 2 lifted PROGRAM_CLEAR's own
    # term, Task 3 the other two), and only GATE_ON's own choice to still pass all three keys False
    # keeps their rows in this particular set.
    unchanged = {'PROGRAM_CLEAR 0xD1', 'PROGRAM 0xD0', 'PROGRAM_MAX 0xC9'}
    pgm_markers = ['%s 0x%02X' % (name, pid) for pid, name in PGM_PIDS]
    # Final review F4: the one non-ctoInfo row this gate is now also allowed to touch, named
    # explicitly (not folded into pgm_markers, which greps for a PID name/hex pair this row does
    # not carry) so the loop below can tell "an expected second kind of difference" apart from "an
    # unrelated byte the gate should never move".
    other_expected_markers = ['maxBsPgm']
    differing = [i for i, (o, n) in enumerate(zip(off_lines, on_lines)) if o != n]

    assert len(differing) == len(PGM_PIDS) - len(unchanged) + len(other_expected_markers), \
        'the gate must change exactly the eight enableable PGM ctoInfo rows plus maxBsPgm, no ' \
        'more and no fewer'
    for i in differing:
        assert any(marker in off_lines[i] for marker in pgm_markers + other_expected_markers), \
            'line %d differs but names no PGM PID: %r' % (i, off_lines[i])
        assert not any(marker in off_lines[i] for marker in unchanged), \
            'line %d is one of the three commands SP4a cannot enable, yet the gate changed it: %r' \
            % (i, off_lines[i])


def test_generation_accepts_the_pgm_resource_on_a_build_that_can_program():
    """DD83. This test used to be the guard itself -- named for the refusal rather than the
    acceptance this rename now reflects -- and it made generation fail outright whenever
    `resource_protection.programming: true` was combined with `programming.enabled: true`,
    because an UNLOCK was spent by the single command that followed it (source/Xcp.c, and
    README.md's *Key lifetime* section as it read before DD79 rewrote it) -- PROGRAM_START consumed
    the grant that admitted it, the session
    became XCP_PGM_ACTIVE, PROGRAM_RESET (the only command that ends it, and itself
    PGM-group-protected) was locked again, and GET_SEED/UNLOCK could not re-open it because DD51's
    ERR_PGM_ACTIVE gate refuses both while ACTIVE. A programming session, once opened, could never
    legitimately be left, so the configuration was refused at generation rather than shipped.

    DD79 makes a granted resource last the whole session instead of the single command following
    the unlock that grants it, so the GET_SEED/UNLOCK round that admits PROGRAM_START is still in
    effect when PROGRAM_RESET needs it, and the dead end above no longer forms. This test only
    proves the CONFIGURATION generates and advertises the resource correctly -- the same content
    check test_generation_accepts_the_pgm_resource_on_a_build_that_cannot_program below makes, on
    the build that test's own name says cannot exist. The sequence itself -- GET_SEED, UNLOCK,
    PROGRAM_START, PROGRAM_CLEAR, PROGRAM, PROGRAM_RESET, every step confirmed positive, and
    PROGRAM_START proven refused before the unlock so the protection is live rather than absent --
    is walked end to end by
    test/pgm_protected_acceptance_test.py::test_a_protected_pgm_resource_conducts_a_full_programming_sequence_end_to_end,
    which is what actually discharges the claim this generation-level check only advertises.

    Kept, renamed and inverted rather than deleted: this stays the only GENERATION-level guard on
    this configuration. If a refusal is ever reintroduced here -- for this reason or another -- it
    fails this one test in a single line; a regression in the session-lifetime mechanism itself
    would instead surface as a much noisier failure partway through the acceptance test's own
    nine-step sequence."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   resource_protection_programming=True,
                                   **GATE_ON))

    # Bit 4, PGM, in the resource layout of XCP part 2 1.1/1.5 -- written as the shift
    # script/source_cfg.c.jinja2 emits rather than as a name, because
    # XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM lives in source/Xcp_Internal.h, which the harness does
    # not parse for defines. The same assertion
    # test_generation_accepts_the_pgm_resource_on_a_build_that_cannot_program makes below, now also
    # true of a build that CAN program.
    assert handle.config.lib.Xcp[0].general.protectedResource == (0x01 << 0x04)


def test_generation_accepts_the_pgm_resource_on_a_build_that_cannot_program():
    """The other half of the guard's condition, and what makes it a statement about the DEAD END
    rather than about the flag -- DD48's own test_generation_accepts_the_stim_resource_on_a_
    configuration_that_cannot_stimulate, applied to PGM.

    With the feature gated off there is no PROGRAM_START to open a session, so nothing can reach
    the state the guard exists to keep a master out of: the flag is inert, exactly as it was for
    every configuration before this sub-project, and the configuration still generates with bit 4
    of protectedResource set. A guard written as "refuse resource_protection.programming", full
    stop, would refuse a configuration that cannot go wrong."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   programming_enabled=False,
                                   resource_protection_programming=True))

    # Bit 4, PGM, in the resource layout of XCP part 2 1.1/1.5 -- written as the shift
    # script/source_cfg.c.jinja2 emits rather than as a name, because
    # XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM lives in source/Xcp_Internal.h, which the harness does
    # not parse for defines. daq_configuration_test.py reads the STIM bit the same way.
    assert handle.config.lib.Xcp[0].general.protectedResource == (0x01 << 0x04)


def test_generation_accepts_a_programming_build_that_does_not_claim_the_pgm_resource():
    """The second discriminator: it is the CONJUNCTION that is refused. A gate-on build that leaves
    `resource_protection.programming` clear promises the master nothing about protecting the PGM
    group, so there is nothing for it to be wrong about -- and this is the configuration every
    other PGM test in this suite runs on (pgm_deferred_test.py's pgm_handle), so a guard written as
    "refuse programming.enabled with any protection at all" would take the whole sub-project's test
    suite down with it."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   resource_protection_data_acquisition=True,
                                   **GATE_ON))

    # Bit 2, DAQ, in the same 1.1/1.5 layout. A protected resource is still set, so this cannot
    # pass by the configuration simply protecting nothing.
    assert handle.config.lib.Xcp[0].general.protectedResource == (0x01 << 0x02)

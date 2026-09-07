#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import pytest

from bsw_code_gen import BSWCodeGen
from jinja2.exceptions import UndefinedError

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


PGM_PIDS = ((0xD2, 'PROGRAM_START'), (0xD1, 'PROGRAM_CLEAR'), (0xD0, 'PROGRAM'),
            (0xCF, 'PROGRAM_RESET'), (0xCE, 'GET_PGM_PROCESSOR_INFO'), (0xCD, 'GET_SECTOR_INFO'),
            (0xCC, 'PROGRAM_PREPARE'), (0xCB, 'PROGRAM_FORMAT'), (0xCA, 'PROGRAM_NEXT'),
            (0xC9, 'PROGRAM_MAX'), (0xC8, 'PROGRAM_VERIFY'))

#: The three PGM commands CONNECT's RESOURCE bit 4 is defined by (1.0/1.6.1.1.1), none of them
#: implemented before SP4b, and therefore the three keys script/source_cfg.c.jinja2 refuses to see
#: enabled alongside `programming.enabled` (final-review finding 3).
CONNECT_ADVERTISED_KEYS = ('xcp_program_clear_api_enable',
                           'xcp_program_api_enable',
                           'xcp_program_max_api_enable')

#: The only gate-on shape that generates: the feature on, the three unimplemented commands off.
#: Mirrors pgm_deferred_test.py's own pgm_handle() and exists for the same reason.
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


@pytest.mark.parametrize('key', CONNECT_ADVERTISED_KEYS)
def test_generation_refuses_each_unimplemented_pgm_key_on_its_own(key):
    """Final-review finding 3, and D11's successor.

    Until this guard, `programming.enabled: true` generated eight of the eleven PGM ctoInfo rows
    ENABLED with Xcp_PIDTable routing them to Xcp_CmdNotImplemented -- and three of the eight are
    exactly the three Xcp_CTOCmdStdConnect reads for RESOURCE bit 4 (1.0/1.6.1.1.1 defines the bit
    by naming PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX). So CONNECT advertised "Flash programming
    available" while all three answered ERR_CMD_UNKNOWN: defect D10 verbatim, one configuration
    flag away from the branch that exists to close it, and this file previously asserted it as
    correct.

    Parametrised over the key that is the SOLE one enabled, so each of the three terms in the
    generator's condition is the only possible cause of the refusal in exactly one case. A guard
    written against `xcp_program_max_api_enable` alone -- D11's original defect, in which that was
    the only key the generator read -- would fail two of these three cases.

    Asserts only that generation fails, never on the message: raise(...) is not a registered Jinja
    global, so every guard in source_cfg.c.jinja2 aborts with the same "'raise' is undefined"
    UndefinedError (daq_configuration_test.py carries the full explanation above its own four).
    What makes this test discriminating is not the message but its companions below: the same
    keys generate cleanly with the gate off, and the gate generates cleanly with the keys off."""
    handle_kwargs = {name: (name == key) for name in CONNECT_ADVERTISED_KEYS}

    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, programming_enabled=True, **handle_kwargs))


def test_the_gate_on_build_still_does_not_advertise_flash_programming():
    """The positive-shaped half of the guard above, and what keeps D10 closed in the only gate-on
    configuration that generates at all.

    This replaces test_all_three_pgm_api_keys_enabled_advertises_flash_programming, which asserted
    the OPPOSITE -- that a gate-on build with the three keys enabled sets the bit -- and was the
    branch's own written endorsement of the defect. That test belongs to SP4b: once PROGRAM_CLEAR,
    PROGRAM and PROGRAM_MAX exist, the guard above loses its terms one by one, the keys become
    settable again, and the bit becomes legitimately true for the first time (design §8 says so).
    Until then no buildable configuration sets it, which is the honest state of affairs and is
    exactly what this asserts.

    The consequence worth stating out loud for whoever writes SP4b: `resource |= (0x01u << 0x04u)`
    in Xcp_CTOCmdStdConnect (source/Xcp_Std.c) is unreachable in every configuration this release
    can build, so no test in this suite can currently prove that line works. Restoring that proof
    is SP4b's, not something to be simulated here by re-admitting the lie."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **GATE_ON))
    connect(handle)

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x10) == 0x00, \
        'no configuration SP4a can build may advertise flash programming'


def test_the_three_unimplemented_commands_answer_err_cmd_unknown_with_the_gate_on():
    """The other half of the pair above, and the half that says the advertisement matches the
    implementation rather than merely that both are absent.

    test_the_default_configuration_does_not_advertise_flash_programming makes this claim for the
    gate-OFF build, where every PGM command is unimplemented. Here the gate is ON and three of the
    eleven commands really do exist -- PROGRAM_START, PROGRAM_RESET and PROGRAM_PREPARE, exercised
    at length in pgm_deferred_test.py and pgm_session_test.py -- so the sweep is over the three
    CONNECT reads instead: they must answer ERR_CMD_UNKNOWN, which is what makes the withheld
    advertisement above the truth about this build and not an accident of it."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **GATE_ON))
    connect(handle)

    for pid, name in ((0xD1, 'PROGRAM_CLEAR'), (0xD0, 'PROGRAM'), (0xC9, 'PROGRAM_MAX')):
        assert exchange(handle, (pid,) + (0x00,) * 7)[0:2] == (0xFE, 0x20), \
            '%s must answer ERR_CMD_UNKNOWN until SP4b implements it' % name


def test_the_gate_overrides_the_api_keys():
    """DD59's second conjunct. A command whose handler is not compiled must not be advertised as
    enabled, however its own key is set -- D10 restated per command. Without this term, an
    integrator who enabled the three API keys without enabling the feature would get the
    advertisement back and nothing behind it.

    This is also the accepting discriminator for the guard in
    test_generation_refuses_each_unimplemented_pgm_key_on_its_own above: it is the CONJUNCTION that
    is refused, not the keys. A gate-off build has no PGM handler for the advertisement to be wrong
    about, so the same three keys generate cleanly here -- and a guard mistakenly written as "refuse
    these keys", full stop, would fail this test."""
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


def test_the_gate_touches_only_pgm_ctoinfo_rows():
    """The other half of acceptance criterion 1: not merely that the disabled state above is
    correct, but that turning the gate on touches NOTHING else. A generator defect that shifted
    some unrelated byte whenever 'programming.enabled' flipped would pass every wire-level test in
    this suite -- all of it runs with the gate off -- and still violate 'byte-for-byte identical',
    which is a claim about the whole file, not about the eleven rows this sub-project added.

    Named for eleven rows until final-review finding 3; eight of them now, since PROGRAM_CLEAR,
    PROGRAM and PROGRAM_MAX cannot be enabled in a gate-on build at all. The claim is unchanged --
    nothing outside the PGM block may move when the gate flips -- and is asserted below as the
    exact set rather than as a number.

    Diffs the current generator's own output for the gate on vs off, rather than reaching back into
    git history for the comparison. The two questions are the same one as long as the template's
    non-PGM rows do not move, and this form does not ask every future test run to depend on git
    history being present and unrewritten -- something no other test in this suite does. The
    historical comparison was run by hand instead, twice: task-6-report.md carries Task 1's, and
    final-fix-report.md carries this round's, where the default build's generated Xcp_Cfg.c,
    Xcp_Cfg.h, Xcp_Rt.c and Xcp_Rt.h were confirmed byte-identical to 35c4877's despite
    config/xcp.json's PGM defaults changing and two guards being added to the template."""
    off = _generated_source(DefaultConfig())
    on = _generated_source(DefaultConfig(xcp_program_start_api_enable=True,
                                         xcp_program_reset_api_enable=True,
                                         xcp_program_prepare_api_enable=True,
                                         **GATE_ON))

    off_lines = off.splitlines()
    on_lines = on.splitlines()
    assert len(off_lines) == len(on_lines), 'the gate must not add or remove any generated line'

    # Eight, not eleven, since final-review finding 3: PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX
    # cannot be enabled in a gate-on build at all, so their rows are identical on both sides and
    # the ceiling on what the gate may touch drops to the other eight. Asserting the exact set
    # rather than a count keeps the claim from weakening as that number moves: SP4b puts each of
    # the three back as it implements it, and this list is where that shows up.
    unchanged = {'PROGRAM_CLEAR 0xD1', 'PROGRAM 0xD0', 'PROGRAM_MAX 0xC9'}
    pgm_markers = ['%s 0x%02X' % (name, pid) for pid, name in PGM_PIDS]
    differing = [i for i, (o, n) in enumerate(zip(off_lines, on_lines)) if o != n]

    assert len(differing) == len(PGM_PIDS) - len(unchanged), \
        'the gate must change exactly the eight enableable PGM ctoInfo rows, no more and no fewer'
    for i in differing:
        assert any(marker in off_lines[i] for marker in pgm_markers), \
            'line %d differs but names no PGM PID: %r' % (i, off_lines[i])
        assert not any(marker in off_lines[i] for marker in unchanged), \
            'line %d is one of the three commands SP4a cannot enable, yet the gate changed it: %r' \
            % (i, off_lines[i])


def test_generation_refuses_the_pgm_resource_on_a_build_that_can_program():
    """Final-review finding 2, and the exact analogue of DD48's STIM refusal
    (daq_configuration_test.py's test_generation_refuses_the_stim_resource_on_a_configuration_that_
    can_stimulate). The difference between the two is instructive: DD48 refuses a protection the
    module does NOT enforce, this refuses one it enforces too well.

    Measured on this branch before the guard existed, not reasoned. An UNLOCK is spent by the one
    command that follows it -- Xcp_ClearProtectionStatus runs after every dispatched PID but UNLOCK
    (source/Xcp.c), README.md's *Key lifetime* documents it, and even an unprotected interposed
    GET_STATUS spends it -- so PROGRAM_START consumes the unlock that admitted it. The session is
    then XCP_PGM_ACTIVE, and:

        PROGRAM_RESET   -> (0xFE, 0x25) ERR_ACCESS_LOCKED, the unlock having been spent
        GET_SEED        -> (0xFE, 0x12) ERR_PGM_ACTIVE
        UNLOCK          -> (0xFE, 0x12)
        DISCONNECT      -> (0xFE, 0x12)

    Every one of those refusals is individually conformant -- 1.1/1.7.3.2.1 and 1.7.3.2.5 list
    ERR_PGM_ACTIVE for GET_SEED, UNLOCK and DISCONNECT with the action "wait t7, repeat infinitely
    times" -- and the composition is a slave that cannot leave a programming session at all: the
    only door out is PROGRAM_RESET, PROGRAM_RESET is in the locked group, and the only way to
    unlock the group is refused because the session is open.

    Refused at generation rather than repaired here because repairing it means changing the unlock
    LIFETIME, which is one mechanism shared by CAL_PAG, DAQ and PGM alike and needs its own design.
    Asserts only that generation fails, never on the message, for the reason
    test_generation_refuses_each_unimplemented_pgm_key_on_its_own above gives."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                              resource_protection_programming=True,
                              **GATE_ON))


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

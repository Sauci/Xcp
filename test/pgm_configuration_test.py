#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import pytest

from bsw_code_gen import BSWCodeGen

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


PGM_PIDS = ((0xD2, 'PROGRAM_START'), (0xD1, 'PROGRAM_CLEAR'), (0xD0, 'PROGRAM'),
            (0xCF, 'PROGRAM_RESET'), (0xCE, 'GET_PGM_PROCESSOR_INFO'), (0xCD, 'GET_SECTOR_INFO'),
            (0xCC, 'PROGRAM_PREPARE'), (0xCB, 'PROGRAM_FORMAT'), (0xCA, 'PROGRAM_NEXT'),
            (0xC9, 'PROGRAM_MAX'), (0xC8, 'PROGRAM_VERIFY'))


def exchange(handle, request, length=8):
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


@pytest.mark.parametrize('key', ('xcp_program_clear_api_enable',
                                 'xcp_program_api_enable',
                                 'xcp_program_max_api_enable'))
def test_each_pgm_api_key_alone_withdraws_the_connect_advertisement(key):
    """D11. script/source_cfg.c.jinja2 hard-coded the ctoInfo enable bit for the whole PGM block
    except PROGRAM_MAX, so xcp_program_api_enable and xcp_program_clear_api_enable were accepted
    and ignored. Xcp_CTOCmdStdConnect tests all three, so its three-term conjunction was one term.

    Parametrised over the key that is DISABLED, with the other two enabled, so each conjunct is
    the sole cause of the 0 in exactly one case. The pre-existing sweep in connect_test.py varied
    all three together and passed every case on xcp_program_max_api_enable alone -- it would have
    passed unchanged had the other two keys been deleted from the schema outright."""
    enabled = {'xcp_program_clear_api_enable': True,
               'xcp_program_api_enable': True,
               'xcp_program_max_api_enable': True,
               'programming_enabled': True}
    enabled[key] = False
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, **enabled))
    connect(handle)

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x10) == 0x00, \
        'disabling %s alone must withdraw the PGM advertisement' % key


def test_all_three_pgm_api_keys_enabled_advertises_flash_programming():
    """The positive half of the sweep above: with the gate on and all three commands enabled, the
    bit is set. Without this, every case would be a zero and a module that never set the bit at
    all would pass the whole parametrisation."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   programming_enabled=True,
                                   xcp_program_clear_api_enable=True,
                                   xcp_program_api_enable=True,
                                   xcp_program_max_api_enable=True))
    connect(handle)

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x10) == 0x10


def test_the_gate_overrides_the_api_keys():
    """DD59's second conjunct. A command whose handler is not compiled must not be advertised as
    enabled, however its own key is set -- D10 restated per command. Without this term, an
    integrator who enabled the three API keys without enabling the feature would get the
    advertisement back and nothing behind it."""
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


def test_the_gate_touches_only_the_eleven_pgm_ctoinfo_rows():
    """The other half of acceptance criterion 1: not merely that the disabled state above is
    correct, but that turning the gate on touches NOTHING else. A generator defect that shifted
    some unrelated byte whenever 'programming.enabled' flipped would pass every wire-level test in
    this suite -- all of it runs with the gate off -- and still violate 'byte-for-byte identical',
    which is a claim about the whole file, not about the eleven rows this sub-project added.

    Diffs the current generator's own output for the gate on vs off, rather than reaching back
    into git history for the comparison: script/source_cfg.c.jinja2 has not changed since Task 1
    (confirmed by inspection -- git log shows exactly one commit touching it on this branch,
    83cb11d967feffda21ebefc8b05fc7e51075b554), so this in-tree, git-independent diff already
    answers the same question a historical one would, without asking every future test run to
    depend on git history being present and unrewritten -- something no other test in this suite
    does. task-6-report.md also carries the historical diff directly, run by hand once, for the
    record."""
    off = _generated_source(DefaultConfig())
    on = _generated_source(DefaultConfig(programming_enabled=True,
                                         xcp_program_clear_api_enable=True,
                                         xcp_program_api_enable=True,
                                         xcp_program_max_api_enable=True,
                                         xcp_program_start_api_enable=True,
                                         xcp_program_reset_api_enable=True,
                                         xcp_program_prepare_api_enable=True))

    off_lines = off.splitlines()
    on_lines = on.splitlines()
    assert len(off_lines) == len(on_lines), 'the gate must not add or remove any generated line'

    pgm_markers = ['%s 0x%02X' % (name, pid) for pid, name in PGM_PIDS]
    differing = [i for i, (o, n) in enumerate(zip(off_lines, on_lines)) if o != n]

    assert len(differing) == len(PGM_PIDS), \
        'the gate must change exactly the eleven PGM ctoInfo rows, nothing more and nothing fewer'
    for i in differing:
        assert any(marker in off_lines[i] for marker in pgm_markers), \
            'line %d differs but names no PGM PID: %r' % (i, off_lines[i])

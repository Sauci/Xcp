#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


def get_seed_key_slices(seed, max_cto=8):
    n = max_cto - 2
    return [seed[i * n:(i + 1) * n] for i in range(len(seed)) if len(seed[i * n:(i + 1) * n]) != 0]


def get_seed_side_effect_copy_ok(handle, seed):
    def wrapper(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed):
            p_seed_buffer[i] = b
        p_seed_length[0] = len(seed)
        return handle.define('E_OK')
    return wrapper


def calc_key_side_effect_copy_ok(handle, key):
    def wrapper(_p_seed_buffer, _seed_length, p_key_buffer, _max_key_length, p_key_length):
        for i, b in enumerate(key):
            p_key_buffer[i] = b
        p_key_length[0] = len(key)
        return handle.define('E_OK')
    return wrapper


# DD78. The resource_protection_* flag that makes each member of `resources` (test/parameter.py)
# genuinely protected, so that a test parametrised over a resource can also configure that resource
# -- what GET_STATUS byte 2 and UNLOCK response byte 1 report is the Current Resource Protection
# Mask of XCP part 2 1.0/1.6.1.1.3 (1 = still protected), which says nothing about a group the build
# never protected.
#
# All four are buildable on DefaultConfig, STIM included: script/source_cfg.c.jinja2 refuses
# resource_protection.data_stimulation only when the build is `stim.capable`, which for a STATIC
# configuration means at least one entry of `daqs` with a type other than 'DAQ'. DefaultConfig's own
# single list is a plain DAQ list, so the refusal (DD41/DD48) does not fire here.
RESOURCE_PROTECTION_FLAG = {0x01: 'resource_protection_calibration_paging',
                            0x04: 'resource_protection_data_acquisition',
                            0x08: 'resource_protection_data_stimulation',
                            0x10: 'resource_protection_programming'}


@pytest.mark.parametrize('resource', resources)
@pytest.mark.parametrize('max_cto', max_ctos)
@pytest.mark.parametrize('seed', seeds, indirect=True)
def test_get_seed_returns_the_expected_responses(resource, max_cto, seed):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto))

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED
    actual_seed = list()
    remaining_seed_length = len(seed)
    for mode, seed_slice in zip([0] + [1] * (len(get_seed_key_slices(seed, max_cto)) - 1),
                                get_seed_key_slices(seed, max_cto)):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, mode, resource)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, remaining_seed_length)
        actual_seed += list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:2 + min(remaining_seed_length, max_cto - 2)])
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        remaining_seed_length -= len(seed_slice)

    assert actual_seed == seed


@pytest.mark.parametrize('seed_array', ((s, 2) for s in range(0x07, 0x0D)), indirect=True)
def test_get_seed_does_not_return_an_error_pid_if_the_first_part_of_the_seed_is_requested_twice(seed_array):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    def get_seed_1_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed_array[0]):
            p_seed_buffer[i] = b
        p_seed_length[0] = len(seed_array[0])
        return handle.define('E_OK')

    def get_seed_2_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed_array[1]):
            p_seed_buffer[i] = b
        p_seed_length[0] = len(seed_array[1])
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_1_side_effect

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED #1
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, len(seed_array[0]))
    assert seed_array[0][0:6] == list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:8])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.xcp_get_seed.side_effect = get_seed_2_side_effect

    # GET_SEED #1
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, len(seed_array[1]))
    second_seed = list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:8])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED #2
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, len(seed_array[1]) - 0x06)
    second_seed += list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:2 + len(seed_array[1]) - 0x06])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert second_seed == seed_array[1]


@pytest.mark.parametrize('resource', resources)
@pytest.mark.parametrize('max_cto', max_ctos)
@pytest.mark.parametrize('seed', seeds, indirect=True)
def test_unlock_unlocks_the_requested_resource_if_the_key_is_valid(resource, max_cto, seed):
    """DD78. The resource under test is configured protected, and the two assertions below read the
    Current Resource Protection Mask of XCP part 2 1.0/1.6.1.1.3 -- 1 = the group IS protected --
    which 1.6.1.2.5 makes UNLOCK's positive response carry as well.

    Both inverted with the field they read, and the pair still discriminates a partial key from a
    complete one, in the opposite direction: while frames are still outstanding the resource is
    reported STILL LOCKED (0xFF, resource), and only the frame that completes the key reports
    (0xFF, 0x00) -- nothing left protected. Protecting the resource is what makes either byte mean
    anything: on a build that protects nothing this mask is 0x00 from CONNECT onwards, so both
    assertions would read 0x00 and neither would tell a granted resource from a refused one, nor a
    partial frame from the final one.

    That the byte reaches 0x00 also proves the RIGHT resource was released: `resource` is the only
    bit in the mask, so any other group being cleared instead would leave it standing."""
    key = seed

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto,
                                   **{RESOURCE_PROTECTION_FLAG[resource]: True}))

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, key)

    seed_slices = get_seed_key_slices(seed, max_cto=max_cto)
    key_slices = get_seed_key_slices(key, max_cto=max_cto)

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED
    for mode, _ in zip([0] + [1] * (len(seed_slices) - 1), seed_slices):
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, mode, resource)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UNLOCK
    remaining_key_length = len(key)
    for key_slice in key_slices:
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, remaining_key_length, *key_slice)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        remaining_key_length -= len(key_slice)

        if remaining_key_length != 0:
            assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, resource), (
                'an UNLOCK frame with {} key bytes still outstanding must report resource 0x{:02X} '
                'STILL protected -- nothing is granted until the key is complete'.format(
                        remaining_key_length, resource))

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, 0x00), (
        'the UNLOCK completing the key must report an empty protection mask -- resource 0x{:02X} '
        'was the only protected group on this build and has just been granted'.format(resource))


@pytest.mark.parametrize('resource', resources)
@pytest.mark.parametrize('seed', [pytest.param(1, id='seed length = {:03}d'.format(1))], indirect=True)
def test_unlock_disconnects_the_master_if_key_is_invalid(resource, seed):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    def calc_key_side_effect(_p_seed_buffer, _seed_length, p_key_buffer, _max_key_length, p_key_length):
        for i, b in enumerate(seed):
            p_key_buffer[i] = (~b) & 0xFF
        p_key_length[0] = len(seed)
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, seed)
    handle.xcp_calc_key.side_effect = calc_key_side_effect

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, resource)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UNLOCK
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, len(seed), *seed)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_STATUS
    # If we are disconnected, no commands except the CONNECT command is processed. Here, we send a GET_STATUS command to
    # check if the CanIf underlying function is called or not (we expect that it is not called, as we should be
    # disconnected).
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_count == 3

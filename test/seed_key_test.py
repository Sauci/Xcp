#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest


# TODO: handle seed size according to MAX_CTO definition instead of hard-coded 8 byte MAX_CTO value (e.g. XCP on
#  ethernet)


def get_seed_key_slices_for_max_cto(seed, max_cto=8):
    n = max_cto - 2
    return [seed[i * n:(i + 1) * n] for i in range(len(seed)) if len(seed[i * n:(i + 1) * n]) != 0]


@pytest.mark.parametrize('seed', range(0x01, 0xFF), indirect=True)
def test_get_seed_returns_the_expected_responses(seed):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    def get_seed_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed):
            p_seed_buffer[i] = seed[i]
        p_seed_length[0] = len(seed)
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_side_effect

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED 1
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, len(seed))

    actual_seed = list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:2 + min(len(seed), 6)])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED 2..n
    remaining_seed_length = len(seed) - 6
    for seed_slice in get_seed_key_slices_for_max_cto(seed)[1:]:
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, 0x01)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, remaining_seed_length)

        actual_seed += list(handle.can_if_transmit.call_args[0][1].SduDataPtr[2:2 + min(remaining_seed_length, 6)])
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        remaining_seed_length -= len(seed_slice)

    assert actual_seed == seed


@pytest.mark.parametrize('seed_array', ((s, 2) for s in range(0x07, 0x0D)), indirect=True)
def test_get_seed_does_not_return_an_error_pid_if_the_first_part_of_the_seed_is_requested_twice(seed_array: [[int]]):
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


@pytest.mark.parametrize('resource', (0b00000001, 0b00000100, 0b00001000, 0b00010000))
@pytest.mark.parametrize('seed', list(range(0x07, 0xFF)), indirect=True)
def test_unlock_unlocks_the_requested_resource_if_the_key_is_valid(seed, resource):
    key = seed

    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    def get_seed_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed):
            p_seed_buffer[i] = b
        p_seed_length[0] = len(seed)
        return handle.define('E_OK')

    def calc_key_side_effect(_p_seed_buffer, _seed_length, p_key_buffer, _max_key_length, p_key_length):
        # The key is calculated with the seed transmitted to the master in the slave as well. Then, the key of the slave
        # is compared against the key from the master. If we have a key match, then the key is valid. Thus, here we
        # simply copy the seed.
        for i, b in enumerate(key):
            p_key_buffer[i] = b
        p_key_length[0] = len(key)
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_side_effect
    handle.xcp_calc_key.side_effect = calc_key_side_effect

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED 1
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, resource)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_SEED 2..n
    for _ in get_seed_key_slices_for_max_cto(seed)[1:]:
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, resource)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UNLOCK 1
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, len(key), *key[0:6])))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, 0x00)

    # UNLOCK 2..n
    remaining_key_length = len(key) - 6
    for key_slice in get_seed_key_slices_for_max_cto(key)[1:]:
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, remaining_key_length, *key_slice)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        remaining_key_length -= len(key_slice)

        if remaining_key_length != 0:
            assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, 0x00)

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFF, resource)


@pytest.mark.parametrize('resource', (0b00000001, 0b00000100, 0b00001000, 0b00010000))
@pytest.mark.parametrize('seed', [1], indirect=True)
def test_unlock_disconnects_the_master_if_key_is_invalid(resource, seed):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    def get_seed_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
        for i, b in enumerate(seed):
            p_seed_buffer[i] = seed[i]
        p_seed_length[0] = len(seed)
        return handle.define('E_OK')

    def calc_key_side_effect(_p_seed_buffer, _seed_length, p_key_buffer, _max_key_length, p_key_length):
        for i, b in enumerate(seed):
            p_key_buffer[i] = (~b) & 0xFF
        p_key_length[0] = len(seed)
        return handle.define('E_OK')

    handle.xcp_get_seed.side_effect = get_seed_side_effect
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest


class TestConnectErrorHandling:
    """
    Command               Error             Pre-Action Action
    CONNECT(NORMAL)       timeout t1        -          repeat ∞ times
    CONNECT(USER_DEFINED) timeout t6        wait t7    repeat ∞ times
    """

    # @pytest.mark.parametrize('payload', ((0xFF,),))
    # def test_connect_normal_mode_timeout_t1(self, payload):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    # @pytest.mark.parametrize('mode', range(0x02, 0x0F))
    # def test_connect_user_defined_mode_timeout_t6(self, mode):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, mode)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


class TestDisconnectErrorHandling:
    """
    Command               Error             Pre-Action      Action
    DISCONNECT            timeout t1        SYNCH           repeat 2 times
    DISCONNECT            ERR_CMD_BUSY      wait t7         repeat ∞ times
    DISCONNECT            ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    """

    # def test_disconnect_timeout_t1(self):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    def test_disconnect_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_disconnect_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)


class TestGetStatusErrorHandling:
    """
    Command               Error             Pre-Action      Action
    GET_STATUS            timeout t1        SYNCH           repeat 2 times
    """

    # @pytest.mark.parametrize('payload', ((0xFF,),))
    # def test_get_status_normal_mode_timeout_t1(self, payload):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


class TestSynchErrorHandling:
    """
    Command               Error             Pre-Action      Action
    SYNCH                 timeout t1        SYNCH           repeat 2 times
    SYNCH                 ERR_CMD_SYNCH     -               -
    SYNCH                 ERR_CMD_UNKNOWN   -               restart session
    """

    # def test_synch_timeout_t1(self):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFC,)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    def test_synch_err_cmd_synch(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFC,)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x00)

    @pytest.mark.skip(reason='SYNCH command is not optional and won\'t fail...')
    def test_synch_err_cmd_unknown(self):
        pass


class TestGetCommModInfoErrorHandling:
    """
    Command               Error             Pre-Action      Action
    GET_COMM_MODE_INFO    timeout t1        SYNCH           repeat 2 times
    GET_COMM_MODE_INFO    ERR_CMD_BUSY      wait t7         repeat ∞ times
    GET_COMM_MODE_INFO    ERR_CMD_SYNTAX    -               retry other syntax
    """

    def test_get_comm_mode_info_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFB,)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.skip(reason='GET_COMM_MOD_INFO take a single packet ID and is, by design, not able to fail on syntax')
    def test_get_comm_mode_info_err_cmd_syntax(self, mode_bit):
        pass


class TestGetIdErrorHandling:
    """
    Command               Error             Pre-Action      Action
    GET_ID                timeout t1        SYNCH           repeat 2 times
    GET_ID                ERR_CMD_BUSY      wait t7         repeat ∞ times
    GET_ID                ERR_CMD_UNKNOWN   -               display error
    GET_ID                ERR_CMD_SYNTAX    -               retry other syntax
    GET_ID                ERR_OUT_OF_RANGE  -               retry other parameter
    """

    def test_get_id_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    def test_get_id_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_get_id_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xFA,),))
    def test_get_id_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('requested_identification_type', range(0x01, 0xFF))
    def test_get_id_err_out_of_range(self, requested_identification_type):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, requested_identification_type)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


class TestSetRequestErrorHandling:
    """
    Command               Error             Pre-Action      Action
    SET_REQUEST           timeout t1        SYNCH           repeat 2 times
    SET_REQUEST           ERR_CMD_BUSY      wait t7         repeat ∞ times
    SET_REQUEST           ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    SET_REQUEST           ERR_CMD_UNKNOWN   -               display error
    SET_REQUEST           ERR_CMD_SYNTAX    -               retry other syntax
    SET_REQUEST           ERR_OUT_OF_RANGE  -               retry other parameter
    """

    # def test_set_request_timeout_t1(self):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x00, 0x00, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    def test_set_request_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_set_request_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_set_request_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_set_request_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF9,), (0xF9, 0x00), (0xF9, 0x00, 0x00)))
    def test_set_request_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('mode', (0b10000000, 0b01000000, 0b00100000, 0b00010000, 0b00000010))
    @pytest.mark.parametrize('session_configuration_id', (0x0001, 0x00FF, 0xFF00, 0x0100, 0xFFFF))
    def test_set_request_err_out_of_range(self, mode, session_configuration_id):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9,
                                                                      mode,
                                                                      session_configuration_id >> 8,
                                                                      session_configuration_id & 0xFF)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


class TestGetSeedErrorHandling:
    """
    Command               Error             Pre-Action      Action
    GET_SEED              timeout t1        SYNCH           repeat 2 times
    GET_SEED              ERR_CMD_BUSY      wait t7         repeat ∞ times
    GET_SEED              ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    GET_SEED              ERR_CMD_UNKNOWN   -               display error
    GET_SEED              ERR_CMD_SYNTAX    -               retry other syntax
    GET_SEED              ERR_OUT_OF_RANGE  -               retry other parameter
    GET_SEED              ERR_SEQUENCE      GET_SEED        repeat 2 times (not in the matrix)
    """

    # def test_set_request_timeout_t1(self):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x00, 0x00, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    def test_get_seed_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_get_seed_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_get_seed_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_get_seed_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF8,), (0xF8, 0x00)))
    def test_get_seed_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('mode', range(0x02, 0x0F))
    @pytest.mark.parametrize('resource', [0x00] + list(range(0x02, 0x0F)))
    def test_get_seed_err_out_of_range_from_parameter(self, mode, resource):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, mode, resource)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.parametrize('resource', (0x01, 0x01 << 0x02, 0x01 << 0x03, 0x01 << 0x04))
    def test_get_seed_err_out_of_range_from_seed_function(self, resource):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

        def get_seed_side_effect(_p_seed_buffer, _max_seed_length, p_seed_length):
            p_seed_length[0] = 1
            return handle.define('E_NOT_OK')

        handle.xcp_get_seed.side_effect = get_seed_side_effect

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, resource)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.parametrize('resource', (0x01, 0x01 << 0x02, 0x01 << 0x03, 0x01 << 0x04))
    @pytest.mark.parametrize('seed_length', [0x00])
    def test_get_seed_err_out_of_range_from_seed_length(self, resource, seed_length):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

        def get_seed_side_effect(_p_seed_buffer, _max_seed_length, p_seed_length):
            p_seed_length[0] = seed_length
            return handle.define('E_OK')

        handle.xcp_get_seed.side_effect = get_seed_side_effect
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, resource)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.parametrize('initial_resource, consecutive_resource', ((0x01 << 0x00, 0x01 << 0x02),
                                                                        (0x01 << 0x02, 0x01 << 0x03),
                                                                        (0x01 << 0x03, 0x01 << 0x04),
                                                                        (0x01 << 0x04, 0x01 << 0x00)))
    def test_get_seed_err_out_of_range_from_resource(self, initial_resource, consecutive_resource):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

        def get_seed_side_effect(_p_seed_buffer, _max_seed_length, p_seed_length):
            p_seed_length[0] = 8
            return handle.define('E_OK')

        handle.xcp_get_seed.side_effect = get_seed_side_effect
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, initial_resource)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, consecutive_resource)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    def test_get_seed_err_sequence(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, 0x01, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x29)


class TestUnlockErrorHandling:
    """
    Command               Error             Pre-Action      Action
    UNLOCK                timeout t1        SYNCH           repeat 2 times
    UNLOCK                ERR_CMD_BUSY      wait t7         repeat ∞ times
    UNLOCK                ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    UNLOCK                ERR_CMD_UNKNOWN   -               display error
    UNLOCK                ERR_CMD_SYNTAX    -               retry other syntax
    UNLOCK                ERR_OUT_OF_RANGE  -               retry other parameter
    UNLOCK                ERR_ACCESS_LOCKED -               restart session
    UNLOCK                ERR_SEQUENCE      GET_SEED        repeat 2 times
    """

    # def test_set_request_timeout_t1(self):
    #     handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    #     handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x00, 0x00, 0x00)))
    #     handle.lib.Xcp_MainFunction()
    #     assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

    def test_unlock_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_unlock_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_unlock_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_unlock_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF7,), (0xF7, 0x00)))
    def test_unlock_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('seed', [1], indirect=True)
    @pytest.mark.parametrize('key_length', [0x00])
    def test_unlock_err_out_of_range(self, seed, key_length):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

        def get_seed_side_effect(p_seed_buffer, _max_seed_length, p_seed_length):
            for i, b in enumerate(seed):
                p_seed_buffer[i] = seed[i]
            p_seed_length[0] = len(seed)
            return handle.define('E_OK')

        handle.xcp_get_seed.side_effect = get_seed_side_effect

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, 0x01)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7,
                                                                      key_length,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.parametrize('resource', (0b00000001, 0b00000100, 0b00001000, 0b00010000))
    @pytest.mark.parametrize('seed', [1], indirect=True)
    def test_unlock_err_access_locked(self, resource, seed):
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

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x00, resource)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, len(seed), *seed)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x25)

    def test_unlock_err_sequence_from_seed_request(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, 0x01, 0x01)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x29)

    def test_unlock_err_sequence_from_key_length(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

        def get_seed_side_effect(_p_seed_buffer, _max_seed_length, p_seed_length):
            p_seed_length[0] = 1
            return handle.define('E_OK')

        handle.xcp_get_seed.side_effect = get_seed_side_effect

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, 0x01, 0x01)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF7, 0x03, 0x07, 0x08, 0x09)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x29)


class TestSetMtaErrorHandling:
    """
    Command               Error             Pre-Action      Action
    SET_MTA               timeout t1        SYNCH           repeat 2 times
    SET_MTA               ERR_CMD_BUSY      wait t7         repeat ∞ times
    SET_MTA               ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    SET_MTA               ERR_CMD_UNKNOWN   -               display error
    SET_MTA               ERR_CMD_SYNTAX    -               retry other syntax
    SET_MTA               ERR_OUT_OF_RANGE  -               retry other parameter
    """

    def test_set_mta_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_set_mta_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_set_mta_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_set_mta_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF6,),
                                         (0xF6, 0x00),
                                         (0xF6, 0x00, 0x00),
                                         (0xF6, 0x00, 0x00, 0x00),
                                         (0xF6, 0x00, 0x00, 0x00, 0x00),
                                         (0xF6, 0x00, 0x00, 0x00, 0x00, 0x00),
                                         (0xF6, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    def test_set_mta_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_set_mta_err_out_of_range(self):
        pass


class TestUploadErrorHandling:
    """
    Command               Error             Pre-Action      Action
    UPLOAD                timeout t1        SYNCH + SET_MTA repeat 2 times
    UPLOAD                ERR_CMD_BUSY      wait t7         repeat ∞ times
    UPLOAD                ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    UPLOAD                ERR_CMD_UNKNOWN   -               display error
    UPLOAD                ERR_CMD_SYNTAX    -               retry other syntax
    UPLOAD                ERR_OUT_OF_RANGE  -               retry other parameter
    """

    def test_upload_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_upload_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_upload_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_upload_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF5,),))
    def test_upload_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('number_of_elements', (0,))
    def test_upload_err_out_of_range(self, number_of_elements):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, number_of_elements)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_upload_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='XCP protocol layer specification 1.0 - 1.6.1.1.3: standard commands are never protected')
    def test_upload_err_access_locked(self):
        pass


class TestShortUploadErrorHandling:
    """
    Command               Error             Pre-Action      Action
    SHORT_UPLOAD          timeout t1        SYNCH + SET_MTA repeat 2 times
    SHORT_UPLOAD          ERR_CMD_BUSY      wait t7         repeat ∞ times
    SHORT_UPLOAD          ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    SHORT_UPLOAD          ERR_CMD_UNKNOWN   -               display error
    SHORT_UPLOAD          ERR_CMD_SYNTAX    -               retry other syntax
    SHORT_UPLOAD          ERR_OUT_OF_RANGE  -               retry other parameter
    BUILD_CHECKSUM        ERR_ACCESS_DENIED -               display error
    BUILD_CHECKSUM        ERR_ACCESS_LOCKED unlock slave    repeat 2 times
    """

    def test_short_upload_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF4, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_short_upload_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF4, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_short_upload_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_short_upload_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF4, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF4,),))
    def test_short_upload_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('number_of_elements, ag', ((0, 'BYTE'),
                                                        (0, 'WORD'),
                                                        (0, 'DWORD'),
                                                        (8, 'BYTE'),
                                                        (4, 'WORD'),
                                                        (2, 'DWORD')))
    def test_short_upload_err_out_of_range(self, number_of_elements, ag):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity=ag))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF4,
                                                                      number_of_elements,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_short_upload_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='XCP protocol layer specification 1.0 - 1.6.1.1.3: standard commands are never protected')
    def test_short_upload_err_access_locked(self):
        pass


class TestBuildChecksumErrorHandling:
    """
    Command               Error             Pre-Action      Action
    BUILD_CHECKSUM        timeout t2        SYNCH + SET_MTA repeat 2 times
    BUILD_CHECKSUM        ERR_CMD_BUSY      wait t7         repeat ∞ times
    BUILD_CHECKSUM        ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    BUILD_CHECKSUM        ERR_CMD_UNKNOWN   -               display error
    BUILD_CHECKSUM        ERR_CMD_SYNTAX    -               retry other syntax
    BUILD_CHECKSUM        ERR_OUT_OF_RANGE  -               retry other parameter
    BUILD_CHECKSUM        ERR_ACCESS_DENIED -               display error
    BUILD_CHECKSUM        ERR_ACCESS_LOCKED unlock slave    repeat 2 times
    """

    def test_build_checksum_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_build_checksum_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    def test_build_checksum_err_cmd_unknown(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_build_checksum_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.parametrize('payload', ((0xF3,),
                                         (0xF3, 0x00),
                                         (0xF3, 0x00, 0x00),
                                         (0xF3, 0x00, 0x00, 0x00),
                                         (0xF3, 0x00, 0x00, 0x00, 0x00),
                                         (0xF3, 0x00, 0x00, 0x00, 0x00, 0x00),
                                         (0xF3, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),))
    def test_build_checksum_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    def test_build_checksum_err_out_of_range(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00,
                                                                      0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_build_checksum_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='XCP protocol layer specification 1.0 - 1.6.1.1.3: standard commands are never protected')
    def test_build_checksum_err_access_locked(self):
        pass


class TestTransportLayerCmdErrorHandling:
    """
    Command               Error             Pre-Action      Action
    TRANSPORT_LAYER_CMD   timeout t1        SYNCH           repeat 2 times
    TRANSPORT_LAYER_CMD   ERR_CMD_BUSY      wait t7         repeat ∞ times
    TRANSPORT_LAYER_CMD   ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    TRANSPORT_LAYER_CMD   ERR_CMD_SYNTAX    -               retry other syntax
    TRANSPORT_LAYER_CMD   ERR_OUT_OF_RANGE  -               retry other parameter
    """

    def test_transport_layer_cmd_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF2, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_transport_layer_cmd_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF2, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    @pytest.mark.parametrize('payload', ((0xF2,),
                                         (0xF2, 0xFF),
                                         (0xF2, 0xFF, 0x00),
                                         (0xF2, 0xFF, 0x00, 0x00),
                                         (0xF2, 0xFE),
                                         (0xF2, 0xFE, 0x00),
                                         (0xF2, 0xFD),
                                         (0xF2, 0xFD, 0x00),
                                         (0xF2, 0xFD, 0x00, 0x00),
                                         (0xF2, 0xFD, 0x00, 0x00, 0x00),
                                         (0xF2, 0xFD, 0x00, 0x00, 0x00, 0x00),
                                         (0xF2, 0xFD, 0x00, 0x00, 0x00, 0x00, 0x00),))
    def test_transport_layer_cmd_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('payload', ((0xF2, 0xFC, 0x00, 0x00, 0x00, 0x00),
                                         (0xF2, 0xFF, 0x59, 0x43, 0x50, 0x00),
                                         (0xF2, 0xFF, 0x58, 0x44, 0x50, 0x00),
                                         (0xF2, 0xFF, 0x58, 0x43, 0x51, 0x00),
                                         (0xF2, 0xFF, 0x58, 0x43, 0x50, 0x02),
                                         (0xF2, 0xFE, 0xFF, 0xFF, 0x00, 0x00),))
    def test_transport_layer_cmd_err_out_of_range(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


class TestUserCmdErrorHandling:
    """
    Command               Error             Pre-Action      Action
    USER_CMD              timeout t1        SYNCH           repeat 2 times
    USER_CMD              ERR_CMD_BUSY      wait t7         repeat ∞ times
    USER_CMD              ERR_PGM_ACTIVE    wait t7         repeat ∞ times
    USER_CMD              ERR_CMD_SYNTAX    -               retry other syntax
    USER_CMD              ERR_OUT_OF_RANGE  -               retry other parameter
    """

    def test_user_cmd_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_user_cmd_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    @pytest.mark.parametrize('payload', ((0xF1,), (0xF1, 0xFF)))
    def test_user_cmd_err_cmd_syntax(self, payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.parametrize('response_payload', ((0xFE, 0x22),))
    def test_user_cmd_err_out_of_range(self, response_payload):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

        def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
            p_res_err_pdu_info[0].SduLength = 2
            for i in range(len(response_payload)):
                p_res_err_pdu_info[0].SduDataPtr[i] = response_payload[i]
            return handle.define('E_OK')

        handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

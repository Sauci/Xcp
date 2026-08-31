#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest


class TestConnectErrorHandling:
    """
    Command               Error               Pre-Action Action
    CONNECT(NORMAL)       timeout t1          -          repeat ∞ times
    CONNECT(USER_DEFINED) timeout t6          wait t7    repeat ∞ times
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
    Command               Error               Pre-Action      Action
    DISCONNECT            timeout t1          SYNCH           repeat 2 times
    DISCONNECT            ERR_CMD_BUSY        wait t7         repeat ∞ times
    DISCONNECT            ERR_PGM_ACTIVE      wait t7         repeat ∞ times
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
    Command               Error               Pre-Action      Action
    GET_STATUS            timeout t1          SYNCH           repeat 2 times
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
    Command               Error               Pre-Action      Action
    SYNCH                 timeout t1          SYNCH           repeat 2 times
    SYNCH                 ERR_CMD_SYNCH       -               -
    SYNCH                 ERR_CMD_UNKNOWN     -               restart session
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
    Command               Error               Pre-Action      Action
    GET_COMM_MODE_INFO    timeout t1          SYNCH           repeat 2 times
    GET_COMM_MODE_INFO    ERR_CMD_BUSY        wait t7         repeat ∞ times
    GET_COMM_MODE_INFO    ERR_CMD_SYNTAX      -               retry other syntax
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
    Command               Error               Pre-Action      Action
    GET_ID                timeout t1          SYNCH           repeat 2 times
    GET_ID                ERR_CMD_BUSY        wait t7         repeat ∞ times
    GET_ID                ERR_CMD_UNKNOWN     -               display error
    GET_ID                ERR_CMD_SYNTAX      -               retry other syntax
    GET_ID                ERR_OUT_OF_RANGE    -               retry other parameter
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
    Command               Error               Pre-Action      Action
    SET_REQUEST           timeout t1          SYNCH           repeat 2 times
    SET_REQUEST           ERR_CMD_BUSY        wait t7         repeat ∞ times
    SET_REQUEST           ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    SET_REQUEST           ERR_CMD_UNKNOWN     -               display error
    SET_REQUEST           ERR_CMD_SYNTAX      -               retry other syntax
    SET_REQUEST           ERR_OUT_OF_RANGE    -               retry other parameter
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
    Command               Error               Pre-Action      Action
    GET_SEED              timeout t1          SYNCH           repeat 2 times
    GET_SEED              ERR_CMD_BUSY        wait t7         repeat ∞ times
    GET_SEED              ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    GET_SEED              ERR_CMD_UNKNOWN     -               display error
    GET_SEED              ERR_CMD_SYNTAX      -               retry other syntax
    GET_SEED              ERR_OUT_OF_RANGE    -               retry other parameter
    GET_SEED              ERR_SEQUENCE        GET_SEED        repeat 2 times (not in the matrix)
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
    Command               Error               Pre-Action      Action
    UNLOCK                timeout t1          SYNCH           repeat 2 times
    UNLOCK                ERR_CMD_BUSY        wait t7         repeat ∞ times
    UNLOCK                ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    UNLOCK                ERR_CMD_UNKNOWN     -               display error
    UNLOCK                ERR_CMD_SYNTAX      -               retry other syntax
    UNLOCK                ERR_OUT_OF_RANGE    -               retry other parameter
    UNLOCK                ERR_ACCESS_LOCKED   -               restart session
    UNLOCK                ERR_SEQUENCE        GET_SEED        repeat 2 times
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
        # GET_SEED is disabled along with UNLOCK: XCP part 2 - Protocol Layer Specification
        # 1.0/1.4 requires UNLOCK whenever GET_SEED is implemented, so leaving GET_SEED enabled
        # here would make Xcp_Init reject the configuration before this command is ever sent.
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       xcp_get_seed_api_enable=False,
                                       xcp_unlock_api_enable=False))
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
    Command               Error               Pre-Action      Action
    SET_MTA               timeout t1          SYNCH           repeat 2 times
    SET_MTA               ERR_CMD_BUSY        wait t7         repeat ∞ times
    SET_MTA               ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    SET_MTA               ERR_CMD_UNKNOWN     -               display error
    SET_MTA               ERR_CMD_SYNTAX      -               retry other syntax
    SET_MTA               ERR_OUT_OF_RANGE    -               retry other parameter
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
    Command               Error               Pre-Action      Action
    UPLOAD                timeout t1          SYNCH + SET_MTA repeat 2 times
    UPLOAD                ERR_CMD_BUSY        wait t7         repeat ∞ times
    UPLOAD                ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    UPLOAD                ERR_CMD_UNKNOWN     -               display error
    UPLOAD                ERR_CMD_SYNTAX      -               retry other syntax
    UPLOAD                ERR_OUT_OF_RANGE    -               retry other parameter
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
    Command               Error               Pre-Action      Action
    SHORT_UPLOAD          timeout t1          SYNCH + SET_MTA repeat 2 times
    SHORT_UPLOAD          ERR_CMD_BUSY        wait t7         repeat ∞ times
    SHORT_UPLOAD          ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    SHORT_UPLOAD          ERR_CMD_UNKNOWN     -               display error
    SHORT_UPLOAD          ERR_CMD_SYNTAX      -               retry other syntax
    SHORT_UPLOAD          ERR_OUT_OF_RANGE    -               retry other parameter
    SHORT_UPLOAD          ERR_ACCESS_DENIED   -               display error
    SHORT_UPLOAD          ERR_ACCESS_LOCKED   unlock slave    repeat 2 times
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
    Command               Error               Pre-Action      Action
    BUILD_CHECKSUM        timeout t2          SYNCH + SET_MTA repeat 2 times
    BUILD_CHECKSUM        ERR_CMD_BUSY        wait t7         repeat ∞ times
    BUILD_CHECKSUM        ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    BUILD_CHECKSUM        ERR_CMD_UNKNOWN     -               display error
    BUILD_CHECKSUM        ERR_CMD_SYNTAX      -               retry other syntax
    BUILD_CHECKSUM        ERR_OUT_OF_RANGE    -               retry other parameter
    BUILD_CHECKSUM        ERR_ACCESS_DENIED   -               display error
    BUILD_CHECKSUM        ERR_ACCESS_LOCKED   unlock slave    repeat 2 times
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
    Command               Error               Pre-Action      Action
    TRANSPORT_LAYER_CMD   timeout t1          SYNCH           repeat 2 times
    TRANSPORT_LAYER_CMD   ERR_CMD_BUSY        wait t7         repeat ∞ times
    TRANSPORT_LAYER_CMD   ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    TRANSPORT_LAYER_CMD   ERR_CMD_SYNTAX      -               retry other syntax
    TRANSPORT_LAYER_CMD   ERR_OUT_OF_RANGE    -               retry other parameter
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
    Command               Error               Pre-Action      Action
    USER_CMD              timeout t1          SYNCH           repeat 2 times
    USER_CMD              ERR_CMD_BUSY        wait t7         repeat ∞ times
    USER_CMD              ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    USER_CMD              ERR_CMD_SYNTAX      -               retry other syntax
    USER_CMD              ERR_OUT_OF_RANGE    -               retry other parameter
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


class TestDownloadErrorHandling:
    """
    Command               Error               Pre-Action      Action
    DOWNLOAD              timeout t1          SYNCH + SET_MTA repeat 2 times
    DOWNLOAD              ERR_CMD_BUSY        wait t7         repeat ∞ times
    DOWNLOAD              ERR_PGM_ACTIVE      wait t7         repeat ∞ times
    DOWNLOAD              ERR_OUT_OF_RANGE    -               retry other parameter
    DOWNLOAD              ERR_ACCESS_DENIED   -               display error
    DOWNLOAD              ERR_ACCESS_LOCKED   unlock slave    repeat 2 times
    DOWNLOAD              ERR_WRITE_PROTECTED -               display error
    DOWNLOAD              ERR_MEMORY_OVERFLOW -               display error
    """

    def test_download_err_cmd_busy(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x10)

    @pytest.mark.parametrize('mode_bit', (0b00000001, 0b00000100, 0b00001000))
    def test_download_err_pgm_active(self, mode_bit):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.xcp_store_calibration_data_to_non_volatile_memory.return_value = handle.define('E_NOT_OK')
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, mode_bit, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x12)

    @pytest.mark.parametrize('number_of_elements, ag, max_bs, master_block_mode', ((0, 'BYTE', 255, True),
                                                                                   (0, 'WORD', 255, True),
                                                                                   (0, 'DWORD', 255, True),
                                                                                   (7, 'BYTE', 1, True),
                                                                                   (4, 'WORD', 1, True),
                                                                                   (2, 'DWORD', 1, True),
                                                                                   (0, 'BYTE', 255, False),
                                                                                   (0, 'WORD', 255, False),
                                                                                   (0, 'DWORD', 255, False),
                                                                                   (7, 'BYTE', 1, False),
                                                                                   (4, 'WORD', 1, False),
                                                                                   (2, 'DWORD', 1, False)))
    def test_download_err_out_of_range(self, number_of_elements, ag, max_bs, master_block_mode):
        """XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7: without block transfer mode,
        the number of data elements parameter has to be in the range [1..MAX_CTO-1]; an
        ERR_OUT_OF_RANGE is returned otherwise. 0 elements is out of range under every AG and
        block-mode setting, and so is a count that exceeds what a single frame (or, in block
        mode, MAX_BS consecutive frames) could carry.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       address_granularity=ag,
                                       master_block_mode=master_block_mode,
                                       max_bs=max_bs,
                                       max_cto=8))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(
            0x0001, handle.get_pdu_info((0xF0, number_of_elements, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_download_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='XCP protocol layer specification 1.0 - 1.6.1.1.3: standard commands are never protected')
    def test_download_err_access_locked(self):
        pass

    def test_download_err_cmd_unknown(self):
        """Exercises the test harness's config-time disable knob. XCP part 2 - Protocol Layer
        Specification 1.0/1.6.2.1 lists DOWNLOAD as mandatory, so a conformant integration can
        never disable it and this scenario is not part of DOWNLOAD's own matrix row; but the
        generic dispatcher (XCP part 2 - Protocol Layer Specification 1.0/1.4: an attempt to
        execute a not implemented optional command will return ERR_CMD_UNKNOWN) does not know
        that, and answers ERR_CMD_UNKNOWN regardless of which command was switched off.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_download_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_download_err_write_protected(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_download_err_memory_overflow(self, payload):
        pass


class TestDownloadNextErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_download_next_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 0x11, 0x22)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 0x11)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.skip(reason='Xcp_DTOCmdStdDownloadNext only ever compares the announced count '
                             'against the active block transfer and reports ERR_SEQUENCE on a '
                             'mismatch; it has no path that produces ERR_OUT_OF_RANGE')
    def test_returns_err_out_of_range(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_locked(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_write_protected(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_memory_overflow(self):
        pass

    def test_returns_err_sequence_without_an_active_block_transfer(self):
        """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1: If the number of data
        elements does not match the expected value, the error code ERR_SEQUENCE will be
        returned. Outside of a block transfer there is nothing to match against, so the
        expected count is reported as 0.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 0x11, 0x22)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFE, 0x29, 0x00)


class TestDownloadMaxErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8, xcp_download_max_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEE, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2: the minimum request size of
        this command is MAX_CTO, one short of which must still be rejected.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEE, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.skip(reason='Xcp_DTOCmdStdDownloadMax always writes a fixed MAX_CTO/AG-1 '
                             'elements with no user-supplied count to range-check; it has no '
                             'path that produces ERR_OUT_OF_RANGE')
    def test_returns_err_out_of_range(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_locked(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_write_protected(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_memory_overflow(self):
        pass


class TestShortDownloadErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_short_download_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xED, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xED, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    def test_returns_err_out_of_range_when_the_count_exceeds_capacity(self):
        """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: If the number of elements
        exceeds (MAX_CTO-8)/AG, the error code ERR_OUT_OF_RANGE will be returned.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=16))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        payload = (0xED, 0x09, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN')) + tuple([0x00] * 8)
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_locked(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_write_protected(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_memory_overflow(self):
        pass


class TestModifyBitsErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.2"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, xcp_modify_bits_api_enable=False))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEC, 0x00, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEC, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    def test_returns_err_out_of_range_for_a_shift_above_31(self):
        """A shift of 32 or more is undefined behaviour on a 32 bit value; the specification
        puts no bound on S, so the request is rejected rather than evaluated.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEC, 0x20, 0xFF, 0xFF, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_denied(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_access_locked(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_write_protected(self):
        pass

    @pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')
    def test_returns_err_memory_overflow(self):
        pass


class TestSetCalPageErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3

    SET_CAL_PAGE is a mandatory command once paging is used, so it has no ERR_CMD_UNKNOWN row.
    """

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x01, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    def test_returns_err_page_not_valid_for_an_unknown_page(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x01, 0x00, 0x01)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x26)

    def test_returns_err_mode_not_valid_when_neither_ecu_nor_xcp_is_requested(self):
        """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1: both flags ECU and XCP may be
        set simultaneously or separately. A request selecting neither asks for nothing and is
        rejected.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)

    def test_returns_err_segment_not_valid_for_an_unknown_segment(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x01, 0x01, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)

    def test_returns_err_mode_not_valid_rather_than_err_segment_not_valid_when_both_apply(self):
        """Coverage gap from the Task 15 review, generalised to SET_CAL_PAGE: a mode selecting
        neither ECU nor XCP and an unknown segment can each individually justify a different
        error. Xcp_DTOCmdStdSetCalPage checks the mode bits before it ever looks at the segment,
        so ERR_MODE_NOT_VALID wins; swapping the two checks would still satisfy every other test
        in this file.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        # mode 0x00 selects neither ECU nor XCP, and segment 0x01 does not exist (only segment
        # 0 is configured): both ERR_MODE_NOT_VALID and ERR_SEGMENT_NOT_VALID are individually
        # justified by this single request.
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x00, 0x01, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)

    def test_returns_err_segment_not_valid_rather_than_err_page_not_valid_when_both_apply(self):
        """Same gap as above, one check further down: an unknown segment and an unknown page can
        each individually justify a different error. Xcp_DTOCmdStdSetCalPage validates every
        affected segment before it ever looks at the page, so ERR_SEGMENT_NOT_VALID wins.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        # segment 0x01 does not exist and page 0x01 does not exist either (only page 0 is
        # configured on segment 0): both ERR_SEGMENT_NOT_VALID and ERR_PAGE_NOT_VALID are
        # individually justified by this single request.
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x01, 0x01, 0x01)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)


class TestGetCalPageErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3

    GET_CAL_PAGE is a mandatory command once paging is used, so it has no ERR_CMD_UNKNOWN row.
    """

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, 0x01)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    @pytest.mark.skip(reason='GET_CAL_PAGE has no page parameter to validate: the request only '
                             'carries mode and segment. Xcp_DTOCmdStdGetCalPage never produces '
                             'ERR_PAGE_NOT_VALID even though 1.7.3.2.3 lists it for this command')
    def test_returns_err_page_not_valid(self):
        pass

    def test_returns_err_mode_not_valid_for_any_mode_other_than_ecu_or_xcp(self):
        """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2: mode may be 0x01 (ECU access)
        or 0x02 (XCP access). All other values are invalid.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)

    def test_returns_err_segment_not_valid_for_an_unknown_segment(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, 0x01, 0x01)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)

    def test_returns_err_mode_not_valid_rather_than_err_segment_not_valid_when_both_apply(self):
        """Same gap as SET_CAL_PAGE: an invalid mode and an unknown segment can each
        individually justify a different error. Xcp_DTOCmdStdGetCalPage checks the mode before
        the segment, so ERR_MODE_NOT_VALID wins.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, 0x00, 0x01)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)


class TestGetPagProcessorInfoErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       xcp_get_pag_processor_info_api_enable=False,
                                       segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE9,)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    @pytest.mark.skip(reason='GET_PAG_PROCESSOR_INFO takes a single packet ID and is, by design, '
                             'not able to fail on syntax')
    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        pass


class TestGetSegmentInfoErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       xcp_get_segment_info_api_enable=False,
                                       segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    def test_returns_err_out_of_range_for_an_invalid_mode(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x03, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)

    def test_returns_err_segment_not_valid_for_an_unknown_segment(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x00, 0x01, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)

    def test_returns_err_segment_not_valid_rather_than_err_out_of_range_when_both_apply(self):
        """An unknown segment and an invalid mode can each individually justify a different
        error. Xcp_DTOCmdStdGetSegmentInfo checks the segment before it ever looks at mode, so
        ERR_SEGMENT_NOT_VALID wins; swapping the two checks would still satisfy every other test
        in this file.
        """
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.can_if_transmit.reset_mock()

        # mode 0x03 is invalid (only 0, 1 and 2 are defined) and segment 0x01 does not exist:
        # both ERR_OUT_OF_RANGE and ERR_SEGMENT_NOT_VALID are individually justified by this
        # single request.
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x03, 0x01, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()

        assert handle.can_if_transmit.call_count == 1
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)


@pytest.mark.parametrize('name, code', (('XCP_E_ASAM_CMD_SYNCH', 0x00),
                                        ('XCP_E_ASAM_CMD_BUSY', 0x10),
                                        ('XCP_E_ASAM_DAQ_ACTIVE', 0x11),
                                        ('XCP_E_ASAM_PGM_ACTIVE', 0x12),
                                        ('XCP_E_ASAM_CMD_UNKNOWN', 0x20),
                                        ('XCP_E_ASAM_CMD_SYNTAX', 0x21),
                                        ('XCP_E_ASAM_OUT_OF_RANGE', 0x22),
                                        ('XCP_E_ASAM_WRITE_PROTECTED', 0x23),
                                        ('XCP_E_ASAM_ACCESS_DENIED', 0x24),
                                        ('XCP_E_ASAM_ACCESS_LOCKED', 0x25),
                                        ('XCP_E_ASAM_PAGE_NOT_VALID', 0x26),
                                        ('XCP_E_ASAM_MODE_NOT_VALID', 0x27),
                                        ('XCP_E_ASAM_SEGMENT_NOT_VALID', 0x28),
                                        ('XCP_E_ASAM_SEQUENCE', 0x29),
                                        ('XCP_E_ASAM_DAQ_CONFIG', 0x2A),
                                        ('XCP_E_ASAM_MEMORY_OVERFLOW', 0x30),
                                        ('XCP_E_ASAM_GENERIC', 0x31),
                                        ('XCP_E_ASAM_VERIFY', 0x32)))
def test_asam_error_codes_match_the_specification(name, code):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.1"""
    handle = XcpTest(DefaultConfig())
    assert handle.define(name) == code

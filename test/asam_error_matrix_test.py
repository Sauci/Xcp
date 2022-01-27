#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


class TestConnectErrorHandling:
    """
    Command               Error            Pre-Action Action
    CONNECT(NORMAL)       timeout t1       -          repeat ∞ times
    CONNECT(USER_DEFINED) timeout t6       wait t7    repeat ∞ times
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
    Command               Error            Pre-Action Action
    DISCONNECT            timeout t1       SYNCH      repeat 2 times
    DISCONNECT            ERR_CMD_BUSY     wait t7    repeat ∞ times
    DISCONNECT            ERR_PGM_ACTIVE   wait t7    repeat ∞ times
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
    Command               Error            Pre-Action Action
    GET_STATUS            timeout t1       SYNCH      repeat 2 times
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
    Command               Error            Pre-Action Action
    SYNCH                 timeout t1       SYNCH      repeat 2 times
    SYNCH                 ERR_CMD_SYNCH    -          -
    SYNCH                 ERR_CMD_UNKNOWN  -          restart session
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
    Command               Error            Pre-Action Action
    GET_COMM_MODE_INFO    timeout t1       SYNCH      repeat 2 times
    GET_COMM_MODE_INFO    ERR_CMD_BUSY     wait t7    repeat ∞ times
    GET_COMM_MODE_INFO    ERR_CMD_SYNTAX   -          retry other syntax
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
    Command               Error            Pre-Action Action
    GET_ID                timeout t1       SYNCH      repeat 2 times
    GET_ID                ERR_CMD_BUSY     wait t7    repeat ∞ times
    GET_ID                ERR_CMD_UNKNOWN  -          display error
    GET_ID                ERR_CMD_SYNTAX   -          retry other syntax
    GET_ID                ERR_OUT_OF_RANGE -          retry other parameter
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

    @pytest.mark.parametrize('requested_identification_type', range(0x05, 0xFF))
    def test_set_request_err_out_of_range(self, requested_identification_type):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, requested_identification_type)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


class TestSetRequestErrorHandling:
    """
    Command               Error            Pre-Action Action
    SET_REQUEST           timeout t1       SYNCH      repeat 2 times
    SET_REQUEST           ERR_CMD_BUSY     wait t7    repeat ∞ times
    SET_REQUEST           ERR_PGM_ACTIVE   wait t7    repeat ∞ times
    SET_REQUEST           ERR_CMD_UNKNOWN  -          display error
    SET_REQUEST           ERR_CMD_SYNTAX   -          retry other syntax
    SET_REQUEST           ERR_OUT_OF_RANGE -          retry other parameter
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

    @pytest.mark.parametrize('session_configuration_id', (0x0001, 0x00FF, 0xFF00, 0x0100, 0xFFFF))
    def test_set_request_err_out_of_range(self, session_configuration_id):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9,
                                                                      0x00,
                                                                      session_configuration_id >> 8,
                                                                      session_configuration_id & 0xFF)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


class TestGetSeedErrorHandling:
    """
    Command               Error            Pre-Action Action
    GET_SEED              timeout t1       SYNCH      repeat 2 times
    GET_SEED              ERR_CMD_BUSY     wait t7    repeat ∞ times
    GET_SEED              ERR_PGM_ACTIVE   wait t7    repeat ∞ times
    GET_SEED              ERR_CMD_UNKNOWN  -          display error
    GET_SEED              ERR_CMD_SYNTAX   -          retry other syntax
    GET_SEED              ERR_OUT_OF_RANGE -          retry other parameter
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
    @pytest.mark.parametrize('mode_type', range(0x02, 0x0F))
    def test_get_seed_err_out_of_range(self, mode, mode_type):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF8, mode, mode_type)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)
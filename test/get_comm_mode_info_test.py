#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('queue_size', queue_sizes)
@pytest.mark.parametrize('max_bs', max_bss)
@pytest.mark.parametrize('min_st', min_sts)
@pytest.mark.parametrize('comm_mode_optional, master_block_mode, interleaved_mode', [
    (0x00, False, False),
    (0x01, True, False),
    (0x02, False, True),
    (0x03, True, True)])
def test_get_comm_mode_info_returns_expected_values(queue_size,
                                                    max_bs,
                                                    min_st,
                                                    comm_mode_optional,
                                                    master_block_mode,
                                                    interleaved_mode):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   master_block_mode=master_block_mode,
                                   interleaved_mode=interleaved_mode,
                                   max_bs=max_bs,
                                   min_st=min_st,
                                   queue_size=queue_size))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_COMM_MODE_INFO
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFB,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check reserved byte.
    assert raw_data[1] == 0x00

    # check COMM_MODE_OPTIONAL.
    assert raw_data[2] == comm_mode_optional

    # check reserved byte.
    assert raw_data[3] == 0x00

    # check MAX_BS.
    assert raw_data[4] == max_bs

    # check MIN_ST.
    assert raw_data[5] == min_st

    # check QUEUE_SIZE.
    assert raw_data[6] == queue_size

    # check XCP driver version number.
    assert raw_data[7] == ((handle.define('XCP_SW_MAJOR_VERSION') & 0x0F) << 4) | \
           (handle.define('XCP_SW_MINOR_VERSION') & 0x0F)


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_comm_mode_info_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFB,)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x08))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[8:max_cto]) == remaining_zeros

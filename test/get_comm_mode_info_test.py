#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('max_bs', max_bss)
@pytest.mark.parametrize('min_st', min_sts)
@pytest.mark.parametrize('comm_mode_optional, master_block_mode', [
    (0x00, False),
    (0x01, True)])
def test_get_comm_mode_info_returns_expected_values(max_bs,
                                                    min_st,
                                                    comm_mode_optional,
                                                    master_block_mode):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   master_block_mode=master_block_mode,
                                   max_bs=max_bs,
                                   min_st=min_st))

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

    # check QUEUE_SIZE. Zero unconditionally: 1.0/1.6.1.1.3 gives this byte meaning only "if
    # interleaved mode is available", and this module implements no receipt queue, so
    # COMM_MODE_OPTIONAL bit 1 is never set and a non-zero size here would describe a queue that
    # does not exist.
    assert raw_data[6] == 0x00

    # check XCP driver version number.
    assert raw_data[7] == ((handle.define('XCP_SW_MAJOR_VERSION') & 0x0F) << 4) | \
           (handle.define('XCP_SW_MINOR_VERSION') & 0x0F)


def test_interleaved_mode_is_never_advertised_and_carries_no_queue_size():
    """1.0/1.6.1.1.3: INTERLEAVED_MODE says the interleaved mode is available, and "if interleaved
    mode is available, QUEUE_SIZE indicates the maximum number of consecutive command packets the
    master can send to the receipt queue of the slave".

    This module has no receipt queue. A second request arriving while a response is still
    unconfirmed is refused ERR_CMD_BUSY (Xcp_CanIfRxIndication, source/Xcp.c), which is the
    opposite of what the flag promises -- so the bit is hardcoded clear rather than configurable,
    and QUEUE_SIZE reports 0. Advertising a queue depth the slave will not honour is the
    advertise-what-you-cannot-accept defect this project has fixed repeatedly.

    Both bytes are asserted here rather than left to the parametrized test above, because that one
    sweeps the flags the module DOES implement; this one pins the absence, which no sweep over
    supported flags can express."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, master_block_mode=True,
                                   slave_block_mode=True))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_COMM_MODE_INFO
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFB,)))
    handle.lib.Xcp_MainFunction()

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    assert raw_data[2] & 0x02 == 0x00, 'COMM_MODE_OPTIONAL INTERLEAVED_MODE, bit 1'
    assert raw_data[6] == 0x00, 'QUEUE_SIZE'


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

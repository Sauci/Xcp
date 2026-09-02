#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('max_cto, address_granularity', ((1, 'WORD'),
                                                          (3, 'WORD'),
                                                          (1, 'DWORD'),
                                                          (3, 'DWORD')))
def test_xcp_init_raises_e_init_failed_if_max_cto_parameter_does_not_fit_with_address_granularity(max_cto,
                                                                                                  address_granularity):
    handle = XcpTest(DefaultConfig(max_cto=max_cto, address_granularity=address_granularity))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_INIT_API_ID'),
                                                    handle.define('XCP_E_INIT_FAILED'))


# 1 would also fail the modulo check below, but it also leaves zero bytes of ODT capacity under
# the default ABSOLUTE identification field (max_dto - 1 == 0), which the generator now rejects at
# code-generation time (source_cfg.c.jinja2's odt_entry_size_daq guard) before Xcp_Init ever runs.
# 5 keeps this test's own point -- MAX_DTO not dividing the address granularity's element size --
# isolated from that unrelated guard: 5 % 2 == 1 and 5 % 4 == 1, so Xcp_Init still rejects it, and
# 5 - 1 == 4 bytes of capacity, so code generation does not. Do not simplify this back to 1.
@pytest.mark.parametrize('max_dto, address_granularity', ((5, 'WORD'),
                                                          (3, 'WORD'),
                                                          (5, 'DWORD'),
                                                          (3, 'DWORD')))
def test_xcp_init_raises_e_init_failed_if_max_dto_parameter_does_not_fit_with_address_granularity(max_dto,
                                                                                                  address_granularity):
    handle = XcpTest(DefaultConfig(max_dto=max_dto, address_granularity=address_granularity))
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_INIT_API_ID'),
                                                    handle.define('XCP_E_INIT_FAILED'))


def test_command_get_status_sets_the_packet_id_byte_to_pid_response_on_positive_response():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF

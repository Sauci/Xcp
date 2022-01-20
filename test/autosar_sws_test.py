#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

import pytest

from .parameter import *
from .conftest import XcpTest


def test_sws_00802():
    """
    The function Xcp_Init shall internally store the configuration address to enable subsequent API calls to access the
    configuration.
    """

    handle = XcpTest(DefaultConfig())
    assert handle.config.lib.Xcp == handle.lib.Xcp_Ptr


class TestSWS00825:
    """
    If development error detection for the Xcp module is enabled, then the function Xcp_GetVersionInfo shall check
    whether the parameter VersioninfoPtr is a NULL pointer (NULL_PTR). If VersioninfoPtr is a NULL pointer, then the
    function Xcp_GetVersionInfo shall raise the development error XCP_E_PARAM_POINTER and return.
    """

    def test_null_parameter(self):
        handle = XcpTest(DefaultConfig())
        handle.lib.Xcp_GetVersionInfo(handle.ffi.NULL)
        handle.det_report_error.assert_called_once_with(ANY, ANY, ANY, handle.define('XCP_E_PARAM_POINTER'))

    def test_non_null_parameter(self):
        handle = XcpTest(DefaultConfig())
        version_info = handle.ffi.new('Std_VersionInfoType *')
        handle.lib.Xcp_GetVersionInfo(version_info)
        handle.det_report_error.assert_not_called()


def test_sws_00840():
    """
    If development error detection for the XCP module is enabled: if the function Xcp_<Lo>TxConfirmation is called
    before the XCP was initialized successfully, the function Xcp_<Lo>TxConfirmation shall raise the development error
    XCP_E_UNINIT and return.
    """

    handle = XcpTest(DefaultConfig(), initialize=False)
    handle.lib.Xcp_CanIfTxConfirmation(0, handle.define('E_OK'))
    handle.det_report_error.assert_called_once_with(ANY, ANY, handle.define('XCP_CAN_IF_TX_CONFIRMATION_API_ID'), handle.define('XCP_E_UNINIT'))


def test_sws_00842():
    """
    If development error detection for the XCP module is enabled: if the function Xcp_<Lo>TriggerTransmit is called
    before the XCP was initialized successfully, the function Xcp_<Lo>TriggerTransmit shall raise the development error
    XCP_E_UNINIT and return E_NOT_OK.
    """

    handle = XcpTest(DefaultConfig(), initialize=False)
    assert handle.lib.Xcp_CanIfTriggerTransmit(0, handle.ffi.NULL) == handle.define('E_NOT_OK')
    handle.det_report_error.assert_called_once_with(ANY, ANY, handle.define('XCP_CAN_IF_TRIGGER_TRANSMIT_API_ID'), handle.define('XCP_E_UNINIT'))


@pytest.mark.parametrize('enumeration, value', (('XCP_TX_OFF', 0), ('XCP_TX_ON', 1)))
def test_sws_00846(enumeration, value):
    handle = XcpTest(DefaultConfig())
    assert getattr(handle.lib, enumeration) == value


class TestSWS00847:
    """
    The callback function Xcp_<Lo>RxIndication shall inform the DET, if development error detection is enabled
    (XCP_DEV_ERROR_DETECT is set to TRUE) and if function call has failed because of the following reasons:
    - Xcp was not initialized (XCP_E_UNINIT)
    - PduInfoPtr equals NULL_PTR (XCP_E_PARAM_POINTER)
    - Invalid PDUID (XCP_E_INVALID_PDUID)
    """

    def test_not_initialized_error(self):
        handle = XcpTest(DefaultConfig(), initialize=False)
        handle.lib.Xcp_CanIfRxIndication(0, handle.get_pdu_info((dummy_byte,)))
        handle.det_report_error.assert_called_once_with(ANY, ANY, handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'), handle.define('XCP_E_UNINIT'))

    def test_null_pdu_info_pointer_error(self):
        handle = XcpTest(DefaultConfig())
        handle.lib.Xcp_CanIfRxIndication(0, handle.ffi.NULL)
        handle.det_report_error.assert_called_once_with(ANY, ANY, handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'), handle.define('XCP_E_PARAM_POINTER'))

    @pytest.mark.parametrize('pdu_id', range(1, 10))
    def test_invalid_pdu_id_error(self, pdu_id):
        handle = XcpTest(DefaultConfig())
        handle.lib.Xcp_CanIfRxIndication(pdu_id, handle.get_pdu_info((dummy_byte,)))
        handle.det_report_error.assert_called_with(ANY, ANY, handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'), handle.define('XCP_E_INVALID_PDUID'))

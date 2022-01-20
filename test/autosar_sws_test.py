#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest


def test_sws_00825():
    """
    If development error detection for the Xcp module is enabled, then the function Xcp_GetVersionInfo shall check
    whether the parameter VersioninfoPtr is a NULL pointer (NULL_PTR). If VersioninfoPtr is a NULL pointer, then the
    function Xcp_GetVersionInfo shall raise the development error XCP_E_PARAM_POINTER and return.
    """
    handle = XcpTest(DefaultConfig())
    handle.lib.Xcp_GetVersionInfo(handle.ffi.NULL)
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY, handle.define('XCP_E_PARAM_POINTER'))



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
        handle.det_report_error.assert_called_once_with(ANY, ANY, ANY, handle.define('XCP_E_UNINIT'))

    def test_null_pdu_info_pointer_error(self):
        handle = XcpTest(DefaultConfig())
        handle.lib.Xcp_CanIfRxIndication(0, handle.ffi.NULL)
        handle.det_report_error.assert_called_once_with(ANY, ANY, ANY, handle.define('XCP_E_PARAM_POINTER'))

    @pytest.mark.parametrize('pdu_id', range(1, 10))
    def test_invalid_pdu_id_error(self, pdu_id):
        handle = XcpTest(DefaultConfig())
        handle.lib.Xcp_CanIfRxIndication(pdu_id, handle.get_pdu_info((dummy_byte,)))
        handle.det_report_error.assert_called_with(ANY, ANY, ANY, handle.define('XCP_E_INVALID_PDUID'))

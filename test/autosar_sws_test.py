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

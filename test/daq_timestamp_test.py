#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


def test_the_clock_callback_is_available_when_timestamps_are_configured():
    """Xcp_GetDaqTimestamp is declared in a header Xcp.h includes, so pcpp's parse of Xcp.h puts
    it in conftest's code.mocked set on its own. That set only decides which names get wired into
    CFFI, though -- the wiring loop is a plain getattr(self, convert(func)), so conftest.py must
    still assign self.xcp_get_daq_timestamp itself, exactly as it does for every other callback in
    that set. This test exists to prove that wiring before anything depends on it."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp()))

    assert handle.xcp_get_daq_timestamp is not None
    handle.xcp_get_daq_timestamp.return_value = 0xDEADBEEF
    assert handle.xcp_get_daq_timestamp() == 0xDEADBEEF

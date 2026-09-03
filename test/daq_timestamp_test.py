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


def test_an_unconfigured_clock_reads_as_a_sentinel_rather_than_a_plausible_value():
    """A test that forgets to set xcp_get_daq_timestamp.return_value must not get back something
    that looks like real data. MagicMock pre-configures __int__/__index__ to return 1, and CFFI's
    extern "Python+C" return-type coercion happens after mock() has already returned -- outside
    _guarded_callback's try/except -- so an unset mock would otherwise hand a real C caller a
    silently wrong-but-plausible 1, not an exception _callback_invariants could catch. Calling
    straight through the CFFI boundary (handle.lib, not the Python mock) exercises that actual
    coercion path rather than only the Python-level attribute conftest.py's constructor sets."""
    handle = XcpTest(DefaultConfig(timestamp=timestamp()))

    assert handle.lib.Xcp_GetDaqTimestamp() == 0xFFFFFFFF

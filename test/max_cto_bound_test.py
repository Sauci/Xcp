#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jinja2.exceptions import UndefinedError

import pytest

from .parameter import *
from .conftest import XcpTest


def test_generation_refuses_a_max_cto_below_the_error_payload_floor():
    """XCP part 2 - Protocol Layer Specification 1.1/1.1.3.3 puts an error packet's optional data at
    positions 2..MAX_CTO-1, and 1.1/1.6.1.2.9 puts BUILD_CHECKSUM's maximum block size at 4..7, so
    the largest error packet this module builds is 8 bytes. Nothing in source/ checks it:
    Xcp_FillErrorPacketWithData (source/Xcp.c) copies its payload with no comparison against
    maxCto, and Xcp_FinalizeResPacket cannot catch an over-long packet afterwards because its own
    padding loop simply does not execute. That is D18. The check therefore lives at generation,
    where the payload sizes are known constants (DD126).

    A constraint between a configuration field and the module's own constants, which is why it is
    not in config/xcp.schema.json: test/conftest.py bypasses the schema and would not see it.
    """
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=7))


def test_generation_accepts_the_smallest_max_cto_that_holds_every_error_payload():
    """The companion the rejection above needs to mean anything. `raise` is a deliberately-undefined
    Jinja global, so every guard in that template surfaces the identical "'raise' is undefined" and
    pytest.raises(UndefinedError) alone cannot show which one fired, or that the configuration was
    not refused for an unrelated reason. 8 is the floor exactly, so this pair brackets it."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))

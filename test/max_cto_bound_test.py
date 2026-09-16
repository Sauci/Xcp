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


def test_generation_refuses_a_max_cto_above_the_ceiling():
    """D18 Finding 5: the floor above had no matching ceiling, and nothing under script/*.jinja2
    refused a max_cto above any value. config/xcp.schema.json allowed 256 while its own description
    two lines up said AUTOSAR's upper limit is 255, source/Xcp_Internal.h's two buffer comments said
    "8 to 255", and CONNECT reports MAX_CTO in ONE byte -- so 256 would have gone out as 0, telling
    the master no CTO fits at all. The schema now says 255 and this guard refuses above it, for the
    reason DD126 gives for the floor: the schema bounds one input format, the template is what every
    configuration passes through."""
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=256))


def test_generation_accepts_the_largest_max_cto_that_connect_can_report():
    """The companion the refusal above needs, and the boundary an off-by-one would show at. 255 is a
    legal MAX_CTO and must build. It is not in the shared max_ctos list because that list crosses
    address_granularity and 255 is divisible by neither 2 nor 4, which Xcp_Init refuses
    (1.1/1.6.1.1.1, MAX_CTO mod AG = 0) -- the default granularity is BYTE, so it builds here."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=255))

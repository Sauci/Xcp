#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest


def test_exclusive_area_stub_is_linked_and_reaches_the_integrator_callback():
    """The DD5 exclusive area stub (SchM_Enter_Xcp_DtoQueue / SchM_Exit_Xcp_DtoQueue) must be
    declared in the integrator-facing header, reachable from the sixth translation unit, and
    wired through the CFFI harness to its mock -- exactly like any other integrator callback.
    Nothing in production code calls the area yet, so this only proves the plumbing; Task 5
    introduces the first real caller and asserts enter/exit balance from there."""
    handle = XcpTest(DefaultConfig())

    handle.lib.SchM_Enter_Xcp_DtoQueue()
    handle.sch_m_enter_xcp_dto_queue.assert_called_once_with()

    handle.lib.SchM_Exit_Xcp_DtoQueue()
    handle.sch_m_exit_xcp_dto_queue.assert_called_once_with()

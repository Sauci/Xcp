#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def response(handle, request):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(request))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))
    return tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])


def configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1000, byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_PTR to (daq_list, odt, entry 0), then WRITE_DAQ one entry of `size` bytes. Asserts
    both steps were accepted -- a caller relying on a configured entry must not pass because the
    write silently failed."""
    assert response(handle, (0xE2, 0x00) + tuple(u16_to_array(daq_list, byte_order)) +
                    (odt, 0x00))[0] == 0xFF
    assert response(handle, (0xE1, 0xFF, size, 0x00) +
                    tuple(u32_to_array(address, byte_order)))[0] == 0xFF


def start_daq_list(handle, daq_list=0, mode=0x00, channel=0, prescaler=1, priority=0,
                   byte_order='LITTLE_ENDIAN'):
    """SET_DAQ_LIST_MODE with `mode`, then START_STOP_DAQ_LIST(START). Asserts both steps were
    accepted."""
    assert response(handle, (0xE0, mode) + tuple(u16_to_array(daq_list, byte_order)) +
                    tuple(u16_to_array(channel, byte_order)) + (prescaler, priority))[0] == 0xFF
    assert response(handle, (0xDE, 0x01) + tuple(u16_to_array(daq_list, byte_order)))[0] == 0xFF


def stop_daq_list(handle, daq_list=0, byte_order='LITTLE_ENDIAN'):
    """START_STOP_DAQ_LIST(STOP). SET_DAQ_LIST_MODE answers ERR_DAQ_ACTIVE for a running list, so
    a mode change after a start has to come through here first."""
    assert response(handle, (0xDE, 0x00) + tuple(u16_to_array(daq_list, byte_order)))[0] == 0xFF


def daq_list_mode(handle, daq_list=0):
    return handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].daqList[daq_list].mode


def test_pid_off_is_accepted_for_an_absolute_single_odt_list():
    """The response byte alone is not evidence here: connect() left 0xFF in that same buffer, so a
    handler that returned without assembling a response at all would leave it reading 0xFF. What
    makes this the acceptance half of DD20 is the second assertion -- PID_OFF actually reached the
    stored runtime mode, which is the only place Xcp_DaqSampleOdt consults when it decides whether
    to emit an identification field. Its sibling in set_daq_list_mode_test.py
    (test_set_daq_list_mode_accepts_timestamp_when_a_clock_is_configured) pairs the same two
    assertions for the TIMESTAMP bit, for the same reason."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    assert response(handle, (0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF
    assert (daq_list_mode(handle) & 0x20) != 0x00, 'PID_OFF reached the stored mode'


@pytest.mark.parametrize('identification', ('RELATIVE_BYTE', 'RELATIVE_WORD', 'RELATIVE_WORD_ALIGNED'))
def test_pid_off_is_refused_unless_identification_is_absolute(identification):
    """1.1/1.1.2.1: 'Turning off the transmission of the Identification Field is only allowed if
    the Identification Field Type is absolute ODT number.'"""
    handle = XcpTest(DefaultConfig(identification_field_type=identification,
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),)))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID'))


def test_pid_off_is_refused_for_a_multi_odt_list():
    """Without an identification field the transport layer must disambiguate, which 1.1.2.1 says
    requires 'only one ODT for each DAQ list'. This module gives a DAQ list exactly one TX PDU, so
    a second ODT would be indistinguishable from the first on the bus."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=2, max_odt_entries=1),)))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID'))


def test_pid_off_is_refused_when_another_list_shares_this_list_s_tx_pdu():
    """The half of 1.1.2.1 that DD20 originally waved away. "Separate CAN-Ids for each DAQ list"
    is a claim about *distinctness*, and giving every list exactly one TX PDU does not establish
    it: config/xcp.schema.json puts no uniqueItems on pdu_mapping, and config/xcp.json itself maps
    both of its DAQ lists to XCP_PDU_ID_TRANSMIT. Two single-ODT lists on one CAN-Id, both with
    PID_OFF, put two DTOs on that Id with nothing to say which list produced either.

    Both lists are max_odt=1 and identification is ABSOLUTE, so the two conditions that were
    already checked are both satisfied: the shared PDU is the only thing left that can refuse
    this, which is what makes it the discriminating half of its pair with the test below."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1,
                                             pdu_mapping='XCP_PDU_ID_TRANSMIT'),
                                         daq(name='DAQ2', max_odt=1, max_odt_entries=1,
                                             pdu_mapping='XCP_PDU_ID_TRANSMIT'))))
    connect(handle)
    assert (handle.lib.Xcp_Ptr.config.daqList[0].dto[0].dto2PduMapping.txPdu.id ==
            handle.lib.Xcp_Ptr.config.daqList[1].dto[0].dto2PduMapping.txPdu.id), 'the premise'

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, handle.define('XCP_E_ASAM_MODE_NOT_VALID'))


def test_pid_off_is_accepted_when_no_other_list_shares_this_list_s_tx_pdu():
    """The other direction of the same rule, and the reason the refusal above is not simply "more
    than one DAQ list". Two lists again, differing only in which TX PDU they name: DAQ2's
    XCP_PDU_ID_TRANSMIT_B is left undefined by the harness, so script/source_cfg.c.jinja2's own
    #ifndef fallback assigns it the next free id -- which is what the first assertion checks,
    since a fallback that happened to collide would make this test pass for the wrong reason.

    As in test_pid_off_is_accepted_for_an_absolute_single_odt_list, the 0xFF is not the evidence:
    the stored runtime mode is, because that is the only thing Xcp_DaqSampleOdt consults."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1,
                                             pdu_mapping='XCP_PDU_ID_TRANSMIT'),
                                         daq(name='DAQ2', max_odt=1, max_odt_entries=1,
                                             pdu_mapping='XCP_PDU_ID_TRANSMIT_B'))))
    connect(handle)
    assert (handle.lib.Xcp_Ptr.config.daqList[0].dto[0].dto2PduMapping.txPdu.id !=
            handle.lib.Xcp_Ptr.config.daqList[1].dto[0].dto2PduMapping.txPdu.id), 'the premise'

    assert response(handle, (0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF
    assert (daq_list_mode(handle) & 0x20) != 0x00, 'PID_OFF reached the stored mode'


def test_a_pid_off_dto_carries_no_identification_field():
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1234)
    start_daq_list(handle, daq_list=0, mode=0x20)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][1].SduLength == 1
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xA5


def test_pid_off_with_a_timestamp_puts_the_timestamp_at_offset_zero():
    """1.1/1.1.2.2 puts the timestamp directly after the identification field, so with no
    identification field it starts at offset 0. SduLength is asserted too: the two timestamp bytes
    at 0..1 do not by themselves say that nothing preceded them -- a frame that still carried the
    identification field and merely happened to hold 0xEF, 0xBE at the front would satisfy the byte
    assertion alone. Three bytes total, one entry of one byte plus the WORD timestamp, is what
    says the identification field is absent."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE', timestamp=timestamp(size='WORD'),
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    handle.xcp_get_daq_timestamp.return_value = 0xBEEF
    configure_one_entry(handle, daq_list=0, odt=0, size=1)
    start_daq_list(handle, daq_list=0, mode=0x30)

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = handle.can_if_transmit.call_args[0][1]
    assert frame.SduLength == 3, 'a WORD timestamp and one one-byte entry, and nothing before them'
    assert tuple(frame.SduDataPtr[0:2]) == (0xEF, 0xBE)


def test_clearing_pid_off_makes_the_identification_field_reappear():
    """The other direction of DD20, which nothing covered: every other test here either sets
    PID_OFF or is refused it, so a handler that latched the bit on and never cleared it -- or a
    sampler that dropped the identification field for every list once any list had asked -- would
    have gone unnoticed. The list is stopped in between because SET_DAQ_LIST_MODE answers
    ERR_DAQ_ACTIVE while it runs.

    FIRST_PID is read from the configuration rather than assumed to be 0: it is assigned by the
    slave at generation time (1.1/1.6.4.1.1.4), and hard-coding it here would pin an implementation
    detail this test is not about."""
    handle = XcpTest(DefaultConfig(identification_field_type='ABSOLUTE',
                                   daqs=(daq(name='DAQ1', max_odt=1, max_odt_entries=1),),
                                   events=(event(name='EVT1', triggered_daq_list_ref=['DAQ1']),)))
    connect(handle)
    configure_one_entry(handle, daq_list=0, odt=0, size=1, address=0x1234)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    start_daq_list(handle, daq_list=0, mode=0x20)
    handle.lib.Xcp_TriggerEventChannel(0)

    assert handle.can_if_transmit.call_args[0][1].SduLength == 1, 'no identification field'
    handle.lib.Xcp_CanIfTxConfirmation(0x0003, handle.define('E_OK'))

    stop_daq_list(handle, daq_list=0)
    start_daq_list(handle, daq_list=0, mode=0x00)
    assert (daq_list_mode(handle) & 0x20) == 0x00, 'PID_OFF cleared from the stored mode'

    handle.lib.Xcp_TriggerEventChannel(0)

    frame = handle.can_if_transmit.call_args[0][1]
    assert frame.SduLength == 2, 'the absolute ODT number is back in front of the data'
    assert frame.SduDataPtr[0] == handle.lib.Xcp_Ptr.config.daqList[0].firstPid
    assert frame.SduDataPtr[1] == 0xA5


@pytest.mark.parametrize('identification, expected', (('ABSOLUTE', 0x20),
                                                      ('RELATIVE_BYTE', 0x00),
                                                      ('RELATIVE_WORD', 0x00),
                                                      ('RELATIVE_WORD_ALIGNED', 0x00)))
def test_pid_off_supported_is_advertised_only_for_absolute_identification(identification, expected):
    handle = XcpTest(DefaultConfig(identification_field_type=identification))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDA,)))
    handle.lib.Xcp_MainFunction()

    assert (handle.can_if_transmit.call_args[0][1].SduDataPtr[0x01] & 0x20) == expected


def queued_frames(handle):
    """Every frame currently in the ring, oldest first, as bytes. Read directly out of
    Xcp_Rt[...].dtoQueue, as test/daq_dynamic_acceptance_test.py and four other files do; the
    transmit path is asserted here rather than through can_if_transmit because a list that must
    not be sampled produces NO call, and `call_args` on a mock that was never called after the
    setup commands still holds whatever the last setup response left there."""
    queue = handle.lib.Xcp_Rt[handle.lib.Xcp_Ptr.xcpRtRef].dtoQueue
    frames = list()
    index = queue.read
    for _ in range(queue.count):
        frame = queue.frame[index]
        frames.append(bytes(frame.data[0:frame.length]))
        index = (index + 1) % queue.depth
    return frames


def not_identifiable(handle):
    """The Det reports Xcp_TriggerEventChannel raised for lists it would not sample, filtered out
    of whatever else the setup commands reported."""
    return [call for call in handle.det_report_error.call_args_list
            if call[0][3] == handle.define('XCP_E_DAQ_LIST_NOT_IDENTIFIABLE')]


def drifted_handle(mode=0x20, entries=True):
    """A dynamic pool of one list, granted `mode` while it held a single ODT and then grown to two.

    daq_count=1 is required, not incidental: Xcp_DaqListTxPduIsExclusive walks the CONFIGURED pool,
    so a second slot -- even unallocated -- would make SET_DAQ_LIST_MODE refuse PID_OFF outright
    (test_pid_off_under_dynamic_follows_the_shared_tx_pdu_rule) and the drift could never be set up.

    The allocations all precede the ODT entries because 1.1/1.6.4.2.1.3 answers ERR_SEQUENCE to an
    ALLOC_ODT that follows an ALLOC_ODT_ENTRY; the second ALLOC_ODT is legal exactly where it sits,
    after another ALLOC_ODT and after SET_DAQ_LIST_MODE, neither of which is an enumerated case."""
    handle = XcpTest(dynamic_config(daq_count=1, odt_count=2, odt_entries_count=1,
                                    identification_field_type='ABSOLUTE'))
    connect(handle)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)

    assert response(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF, 'ALLOC_DAQ(1)'
    assert response(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF, 'ALLOC_ODT(list 0, 1)'
    assert response(handle, (0xE0, mode, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF, \
        'SET_DAQ_LIST_MODE is granted while the list still holds exactly one ODT'
    assert response(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF, 'ALLOC_ODT accumulates'
    assert handle.lib.Xcp_Ptr.config.daqList[0].maxOdt == 2, 'the list now has two ODTs'
    assert (daq_list_mode(handle) & mode) == mode, 'and the granted mode is still set on it'

    if entries:
        for odt in (0x00, 0x01):
            assert response(handle, (0xD3, 0x00, 0x00, 0x00, odt, 0x01))[0] == 0xFF
            assert response(handle, (0xE2, 0x00, 0x00, 0x00, odt, 0x00))[0] == 0xFF
            assert response(handle, (0xE1, 0xFF, 0x01, 0x00) +
                            tuple(u32_to_array(0x1000 + odt, 'LITTLE_ENDIAN')))[0] == 0xFF
        # Last, and only once the entries are in place: SET_DAQ_LIST_MODE answers ERR_DAQ_ACTIVE
        # for a running list, so nothing above could follow a START. A list left stopped would make
        # every caller below pass by sampling nothing at all, for a reason that has nothing to do
        # with PID_OFF.
        assert response(handle, (0xDE, 0x01, 0x00, 0x00))[0] == 0xFF, 'START_STOP_DAQ_LIST(START)'
    return handle


def test_a_pid_off_list_grown_past_one_odt_is_not_sampled():
    """The transmit-side twin of stim_decode_test.py's
    test_pid_off_is_refused_once_alloc_odt_has_grown_the_list_past_one_odt. Both directions face the
    same drifted list; the receive side cannot attribute an arriving frame to an ODT and drops it,
    and this side must not create the frames that would be unattributable.

    Sampling this list would queue two DTOs, each with no identification field, onto the one PDU the
    pool shares -- and 1.1/1.1.2.1 leaves the master nothing else to tell them apart with, since
    every ODT of a list goes out on the same CAN-Id. Asserting the ring is empty rather than
    asserting one frame is deliberate: emitting ODT 0 alone would still be wrong, because the master
    was promised the list's whole cycle and would silently receive half of it.

    The Det report is asserted as well as the silence. Without it this test would pass just as well
    against a module that skipped the list for some unrelated reason -- a broken elapsed check, a
    list that never actually started -- and drifted lists would vanish with no trace an integrator
    could see."""
    handle = drifted_handle()

    handle.lib.Xcp_TriggerEventChannel(0)

    assert queued_frames(handle) == [], \
        'a PID_OFF list with two ODTs cannot be identified on the wire, so it must not be sampled'
    assert len(not_identifiable(handle)) == 1, 'and the skip is reported once for the list'
    assert not_identifiable(handle)[0][0][2] == \
        handle.define('XCP_TRIGGER_EVENT_CHANNEL_API_ID')


def test_the_same_list_transmits_both_odts_once_pid_off_is_cleared():
    """The PID_OFF term of the skip condition, isolated. Same pool, same two ALLOC_ODTs, same
    entries -- only the granted mode differs -- so a guard that had been written against maxOdt
    alone, or against dynamic allocation, would fail here by refusing a perfectly ordinary two-ODT
    list. Two frames, not merely 'some', because a guard that skipped ODT 1 while emitting ODT 0
    would satisfy a weaker assertion.

    The absolute ODT numbers are pinned as well: with the identification field back, the two frames
    must be distinguishable, which is the property whose absence justifies the skip in the first
    test."""
    handle = drifted_handle(mode=0x00)

    handle.lib.Xcp_TriggerEventChannel(0)

    frames = queued_frames(handle)
    assert len(frames) == 2, 'two ODTs, each with one entry, sample to two frames'
    first_pid = handle.lib.Xcp_Ptr.config.daqList[0].firstPid
    assert [frame[0] for frame in frames] == [first_pid, first_pid + 1], \
        'and each carries its own absolute ODT number'
    assert not_identifiable(handle) == [], 'nothing was skipped, so nothing was reported'


def test_a_single_odt_pid_off_list_still_transmits():
    """The maxOdt term of the skip condition, isolated. The identical dynamic pool and the identical
    PID_OFF grant, without the second ALLOC_ODT: a guard that keyed on PID_OFF alone would silence
    this list too, and PID_OFF would become a bit that turns transmission off rather than the
    identification field.

    SduLength is asserted because the payload byte alone does not say the identification field is
    absent -- one byte total is what says it."""
    handle = XcpTest(dynamic_config(daq_count=1, odt_count=2, odt_entries_count=1,
                                    identification_field_type='ABSOLUTE'))
    connect(handle)
    handle.xcp_read_slave_memory_u8.side_effect = lambda a, e, b: b.__setitem__(0, 0xA5)
    assert response(handle, (0xD5, 0x00, 0x01, 0x00))[0] == 0xFF
    assert response(handle, (0xD4, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF
    assert response(handle, (0xE0, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00))[0] == 0xFF
    assert response(handle, (0xD3, 0x00, 0x00, 0x00, 0x00, 0x01))[0] == 0xFF
    assert response(handle, (0xE2, 0x00, 0x00, 0x00, 0x00, 0x00))[0] == 0xFF
    assert response(handle, (0xE1, 0xFF, 0x01, 0x00) +
                    tuple(u32_to_array(0x1000, 'LITTLE_ENDIAN')))[0] == 0xFF
    assert response(handle, (0xDE, 0x01, 0x00, 0x00))[0] == 0xFF

    handle.lib.Xcp_TriggerEventChannel(0)

    assert queued_frames(handle) == [bytes((0xA5,))], \
        'one ODT, one entry, and no identification field in front of it'
    assert not_identifiable(handle) == []

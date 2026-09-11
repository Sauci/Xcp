#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math
from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest


@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('mode, actual_identification, expected_identification', [
    (0x00, '/path/to/database.a2l', '/path/to/database.a2l')])
def test_get_id_returns_identification_through_mta_when_mode_is_0(byte_order,
                                                                  mode,
                                                                  actual_identification,
                                                                  expected_identification):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   byte_order=byte_order,
                                   identification=actual_identification))

    memory_identification = []

    def read_slave_memory(p_address, _extension, _p_buffer):
        memory_identification.append(handle.ffi.cast('uint8_t*', p_address)[0])

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # GET_ID
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, mode)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    # check packet ID.
    assert raw_data[0] == 0xFF

    # check the response Mode bit mask. XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2
    # makes this byte a bit mask -- TRANSFER_MODE at bit 0, COMPRESSED_ENCRYPTED at bit 1, bits 2-7
    # don't-care. 1.0/1.6.1.2.2 has the same byte and leaves it unnamed, which is why this was
    # previously read as an echo of the request's Requested Identification Type. It is not one:
    # request byte 1 and response byte 1 are different fields that both happen to be 0 here. The
    # old `assert raw_data[1] == mode` pinned the right value only because this test's parametrize
    # list has one row at zero; it would demand a wrong thing -- that the response echo the
    # request -- as soon as a second identification type is covered.
    # Both bits clear: the slave transfers through the MTA and does not compress (DD111).
    assert raw_data[1] & 0x01 == 0x00, 'TRANSFER_MODE must be clear: this slave points the MTA'
    assert raw_data[1] & 0x02 == 0x00, 'COMPRESSED_ENCRYPTED must be clear: nothing is compressed'
    assert raw_data[1] == 0x00, 'no reserved bit of the Mode mask may be set'

    # check reserved bytes.
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00

    # check Length.
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == len(expected_identification)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, len(expected_identification))))
    for _ in range(int(math.ceil(len(expected_identification) / 7))):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # check Identification.
    assert ''.join(chr(c) for c in memory_identification) == expected_identification


@pytest.mark.parametrize('trailing_value', trailing_values)
@pytest.mark.parametrize('max_cto', max_ctos)
def test_get_id_sets_all_remaining_bytes_to_trailing_value(trailing_value, max_cto):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=max_cto, trailing_value=trailing_value))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, 0x00)))
    handle.lib.Xcp_MainFunction()
    remaining_zeros = tuple(trailing_value for _ in range(max_cto - 0x08))
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0x08:max_cto]) == remaining_zeros


def _connect(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def _get_id(handle, identification_type):
    """Issue GET_ID and return the response bytes, read immediately after the transmit call."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, identification_type)))
    handle.lib.Xcp_MainFunction()
    raw = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    return raw


@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('identification_type', (0x01, 0x02, 0x03, 0x04, 0x80, 0xFF))
def test_get_id_reports_length_zero_for_a_defined_type_it_does_not_serve(byte_order,
                                                                        identification_type):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 (1.0/1.6.1.2.2, identical wording):
    "If length is 0, the requested identification type is not available." That is GET_ID's own
    in-band way of declining, and it exists so a master can enumerate what a slave supports without
    provoking errors. Types 1-4 and 128-255 are all types 1.1 defines as requestable, so naming one
    is a valid parameter even on a slave with nothing to return for it -- DD110.

    Type 255 is covered here deliberately: the ERR_OUT_OF_RANGE test this replaces ranged over
    range(0x01, 0xFF), which stops at 254, so the top of the user-defined range was never exercised.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, byte_order=byte_order))
    _connect(handle)

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0] == 0xFF, 'a declined type is still a positive response, not an error packet'
    assert raw_data[1] == 0x00, 'Mode: TRANSFER_MODE and COMPRESSED_ENCRYPTED both clear'
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == 0, 'Length must be 0'


@pytest.mark.parametrize('identification_type', (0x05, 0x40, 0x7F))
def test_get_id_rejects_a_type_the_specification_does_not_define(identification_type):
    """1.1/1.6.1.2.2 lists exactly 0, 1, 2, 3, 4 and 128..255 as the types that "may be requested".
    5..127 name no identification type at all, so a master sending one has supplied an out-of-range
    parameter -- which is what keeps 1.1/1.7.3.2.1's GET_ID ERR_OUT_OF_RANGE row reachable, given
    that the identification type is GET_ID's only parameter. DD110."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    _connect(handle)

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0:2] == (0xFE, 0x22), 'expected ERR_OUT_OF_RANGE'


def _set_mta(handle, address_bytes, extension=0x00):
    """SET_MTA. Copy the exact framing from test/session_teardown_test.py, which already issues a
    SET_MTA(0xDEADBEEF) for the neighbouring DD75 case -- do not reconstruct the byte order here."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(
        (0xF6, 0x00, 0x00, extension) + address_bytes))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def _upload_addresses(handle, element_count):
    """Issue UPLOAD and return the MTA pairs Xcp_ReadSlaveMemory* was asked to read through, as
    (address, extension) integers.

    A pair, not an address alone: 1.1/1.6.1.2.6 defines the MTA as "32Bit address + 8Bit
    extension", and an address can be right while its extension is stale -- DD75's defect. The
    address is cast to uintptr_t, as test_get_id_points_the_mta_at_the_callbacks_address_and_
    extension does, and never dereferenced: callers here point the MTA at SET_MTA's fabricated
    0xDEADBEEF, or expect NULL. All three widths are hooked because UPLOAD reads through
    Xcp_ReadSlaveMemoryTable[addressGranularity] (source/Xcp.c), so a WORD or DWORD configuration
    never reaches the u8 double.
    """
    reads = []

    def read_slave_memory(p_address, extension, _p_buffer):
        reads.append((int(handle.ffi.cast('uintptr_t', p_address)), extension))

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, element_count)))
    handle.lib.Xcp_MainFunction()
    return reads


_CALLBACK_CONFIG = dict(channel_rx_pdu_ref=0x0001,
                        get_id_function='Xcp_GetIdentificationFunction')

# Distinct from the extension every SET_MTA below sets (7), so a pair that leaks names its source.
_CALLBACK_EXTENSION = 0x05


def _no_callback(_handle):
    pass


def _declines_after_writing(handle):
    _serve(handle, b'abcd', extension=_CALLBACK_EXTENSION, result='E_NOT_OK')


def _serves_a_length_the_granularity_refuses(handle):
    _serve(handle, b'abc', extension=_CALLBACK_EXTENSION)   # 3 is not a multiple of WORD's 2


def _serves_length_zero(handle):
    _serve(handle, b'', extension=_CALLBACK_EXTENSION)


# Every route by which GET_ID answers Length = 0 -- (configuration, callback behaviour, type).
_LENGTH_ZERO_ROUTES = (
    pytest.param(dict(channel_rx_pdu_ref=0x0001), _no_callback, 0x03,
                 id='(i) no callback, a defined type it does not serve'),
    pytest.param(_CALLBACK_CONFIG, _declines_after_writing, 0x01,
                 id='(ii) callback writes its out-parameters, then E_NOT_OK'),
    pytest.param(dict(address_granularity='WORD', **_CALLBACK_CONFIG),
                 _serves_a_length_the_granularity_refuses, 0x01,
                 id='(iii) callback length 3 under WORD'),
    pytest.param(_CALLBACK_CONFIG, _serves_length_zero, 0x01,
                 id='(iv) callback answers E_OK with length 0'),
    pytest.param(dict(channel_rx_pdu_ref=0x0001, identification=''), _no_callback, 0x00,
                 id='(v) empty configured identification, type 0'),
)


@pytest.mark.parametrize('config, callback_behaviour, identification_type', _LENGTH_ZERO_ROUTES)
def test_a_length_zero_get_id_does_not_leave_an_earlier_set_mta_standing(config,
                                                                        callback_behaviour,
                                                                        identification_type):
    """DD113. Every GET_ID that answers Length = 0 points the MTA at (NULL_PTR, 0x00u). A master
    that ignores Length = 0 and uploads anyway then reads through a pointer the slave deliberately
    nulled -- not an earlier SET_MTA's, which is the defect DD75 fixed for the extension half of
    the same pair, arriving the other way round, and not whatever the route itself was holding.

    One row per route to Length = 0, because they reach it differently: (i) nothing serves a
    defined type, so nothing is assigned; (ii) the callback writes all three out-parameters and
    then declines; (iii) the callback's length is refused as not a multiple of the granularity;
    (iv) the callback answers E_OK with a length of 0; (v) the configured string is empty. Routes
    (ii) to (v) all reach Length = 0 holding a live address -- the callback's own, or the empty
    string's -- which is what (i), the only route this test used to take, could never show.

    SET_MTA sets extension 7 first, and the callback writes extension 5, so a pair that leaks names
    its source. Paired with a positive control per route below: "UPLOAD read (NULL, 0)" is vacuous
    alone, because CONNECT itself leaves the MTA at exactly that pair, so a SET_MTA that silently
    failed would pass every row. test/session_teardown_test.py uses the same pairing for the
    neighbouring DD75 case.
    """
    handle = XcpTest(DefaultConfig(**config))
    _connect(handle)
    callback_behaviour(handle)
    _set_mta(handle, (0xEF, 0xBE, 0xAD, 0xDE), extension=0x07)

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0] == 0xFF, 'a Length = 0 answer is still a positive response'
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == 0, \
        'every row here is a route to Length = 0'

    reads = _upload_addresses(handle, 0x01)

    assert reads, 'UPLOAD read no memory at all -- see the docstring before changing this'
    assert reads[0] == (0, 0x00), \
        'UPLOAD read through (0x{:X}, {}) after a Length = 0 GET_ID -- expected (NULL, 0)'.format(
            *reads[0])


@pytest.mark.parametrize('config', [pytest.param(route.values[0], id=route.id)
                                    for route in _LENGTH_ZERO_ROUTES])
def test_an_upload_with_no_intervening_get_id_still_reads_the_set_mta_address(config):
    """The positive control for the test above, one row per route's configuration: the same SET_MTA
    and the same UPLOAD, with no GET_ID between them. If a row here fails, the (NULL, 0) its route
    asserts above proves nothing. Per route rather than once, because the configurations differ
    where it matters: route (iii)'s WORD granularity reads through a different
    Xcp_ReadSlaveMemory* function than the others."""
    handle = XcpTest(DefaultConfig(**config))
    _connect(handle)
    _set_mta(handle, (0xEF, 0xBE, 0xAD, 0xDE), extension=0x07)

    reads = _upload_addresses(handle, 0x01)

    assert reads, 'setup: UPLOAD must read memory'
    assert reads[0][0] != 0, \
        'setup: UPLOAD must reach the address SET_MTA just set, or the paired test is vacuous'


def _serve(handle, payload, extension=0x00, result='E_OK'):
    """Make the configured callback answer `payload` for every type, and keep the buffer alive.

    `result` is what the callback returns after writing all three out-parameters. E_NOT_OK after
    writing them is how a test shows the module takes nothing from a declined call.

    Allocated and cast through handle.config.ffi, not the bare handle.ffi (== handle.code.ffi):
    Xcp_GetIdentificationFunction's own extern is declared and registered on handle.config.ffi
    (Xcp_Cfg.c is what takes &Xcp_GetIdentificationFunction, the same reason
    Xcp_UserCmdFunction/Xcp_UserDefinedChecksumFunction are registered there rather than through
    the generic self.code.mocked loop), so the pointer and cast that flow through its
    const void ** out-parameter are kept on that same ffi rather than relying on code.ffi and
    config.ffi's independently-registered types happening to agree.
    """
    buffer = handle.config.ffi.new('char[]', payload)
    handle._pdu_info_keepalive.append(buffer)

    def get_identification(_type, p_identification, p_extension, p_length):
        p_identification[0] = handle.config.ffi.cast('void *', buffer)
        p_extension[0] = extension
        p_length[0] = len(payload)
        return handle.define(result)

    handle.xcp_get_identification_function.side_effect = get_identification
    return buffer


@pytest.mark.parametrize('byte_order', byte_orders)
@pytest.mark.parametrize('identification_type', (0x00, 0x01, 0x02, 0x03, 0x04, 0x80, 0xFF))
def test_get_id_serves_every_defined_type_from_the_callback(byte_order, identification_type):
    """DD108. Types 1-3 are strings an integrator could put in xcp.json, but type 4 is
    "ASAM-MC2 file to upload" (1.1/1.6.1.2.2) -- a whole A2L file whose contents are not known when
    the configuration is generated -- and 128..255 is an open user-defined range a fixed table
    cannot enumerate. So identification data comes from a callback."""
    handle = XcpTest(DefaultConfig(byte_order=byte_order, **_CALLBACK_CONFIG))
    _connect(handle)
    _serve(handle, b'abcd')

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0] == 0xFF
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == 4
    assert handle.xcp_get_identification_function.call_args[0][0] == identification_type, \
        'the callback must be told which type was requested'


def test_get_id_points_the_mta_at_the_callbacks_address_and_extension():
    """DD109. DD75 fixed extension = 0 for the *static* identification, on the ground that it is
    "plain, slave-owned descriptive data that lives entirely outside the page-switching model" --
    an argument about Xcp_Ptr->general->identification that does not transfer to arbitrary
    integrator data. Type 4 is the case that breaks it: an A2L file plausibly lives in memory the
    integrator's Xcp_ReadSlaveMemory* reaches through a non-zero extension. Fixing the extension at
    0 would advertise type 4 while only being able to serve it from extension-0 memory."""
    handle = XcpTest(DefaultConfig(**_CALLBACK_CONFIG))
    _connect(handle)
    buffer = _serve(handle, b'wxyz', extension=0x07)

    _get_id(handle, 0x04)

    reads = []
    handle.xcp_read_slave_memory_u8.side_effect = lambda p_address, extension, _p_buffer: \
        reads.append((int(handle.ffi.cast('uintptr_t', p_address)), extension))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, 0x04)))
    handle.lib.Xcp_MainFunction()

    assert reads, 'UPLOAD did not read any memory'
    assert reads[0] == (int(handle.ffi.cast('uintptr_t', buffer)), 0x07), \
        'UPLOAD read {} -- expected the callback\'s own address and extension 7'.format(reads[0])


def test_get_id_falls_back_to_the_static_identification_when_the_callback_declines_type_zero():
    """DD110. The callback is consulted for every defined type including 0, and E_NOT_OK means
    "I do not serve that type" rather than an error. For type 0 the configured string is the
    fallback, so an integrator who only wants types 1-4 returns E_NOT_OK for 0 and still gets the
    behaviour that shipped before this phase."""
    handle = XcpTest(DefaultConfig(identification='/path/to/xcp.a2l', **_CALLBACK_CONFIG))
    _connect(handle)
    handle.xcp_get_identification_function.side_effect = None
    handle.xcp_get_identification_function.return_value = handle.define('E_NOT_OK')

    raw_data = _get_id(handle, 0x00)

    assert raw_data[0] == 0xFF
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == len('/path/to/xcp.a2l')


def test_get_id_takes_nothing_a_declining_callback_wrote_into_the_static_fallback():
    """DD110 and DD75 together. E_NOT_OK promises nothing about the out-parameters, and this
    callback writes all three before declining type 0 -- its own buffer, extension 5 and length 4.
    The configured string is the fallback, and the response and the MTA must both be entirely its
    own: its length, its address, and extension 0, DD75's value for plain slave-owned descriptive
    data. Nothing the declining callback wrote may survive into either.

    The decline path resets only the length (DD113), so for type 0 the fallback's own assignments
    are all that stand between the callback's pair and the MTA. The address and the length are
    assigned there unconditionally; this is the test that notices if the extension assignment goes.
    SET_MTA sets extension 7 first, so a leak names its source: 5 is the callback's, 7 the earlier
    SET_MTA's.
    """
    handle = XcpTest(DefaultConfig(**_CALLBACK_CONFIG))
    _connect(handle)
    _serve(handle, b'abcd', extension=_CALLBACK_EXTENSION, result='E_NOT_OK')
    _set_mta(handle, (0xEF, 0xBE, 0xAD, 0xDE), extension=0x07)

    raw_data = _get_id(handle, 0x00)

    assert raw_data[0] == 0xFF
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == len('/path/to/xcp.a2l'), \
        "the configured string's length, not the 4 the declining callback wrote"

    reads = _upload_addresses(handle, 0x01)

    identification = int(handle.ffi.cast('uintptr_t',
                                         handle.config.lib.Xcp[0].general.identification))
    assert reads, 'UPLOAD read no memory at all'
    assert reads[0] == (identification, 0x00), \
        'UPLOAD read through (0x{:X}, {}) -- expected the configured string at 0x{:X}, ' \
        'extension 0'.format(reads[0][0], reads[0][1], identification)


@pytest.mark.parametrize('identification_type', (0x01, 0x04, 0x80, 0xFF))
def test_get_id_reports_length_zero_when_the_callback_declines_a_non_ascii_type(
        identification_type):
    """The other half of the fallback: only type 0 has a static string behind it, so a declined
    type 1-4 or 128-255 is simply not available -- Length = 0, per 1.1/1.6.1.2.2. DD110."""
    handle = XcpTest(DefaultConfig(**_CALLBACK_CONFIG))
    _connect(handle)
    handle.xcp_get_identification_function.side_effect = None
    handle.xcp_get_identification_function.return_value = handle.define('E_NOT_OK')

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0] == 0xFF
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == 0


@pytest.mark.parametrize('identification_type', (0x05, 0x7F))
def test_get_id_does_not_consult_the_callback_for_an_undefined_type(identification_type):
    """5..127 are refused before the callback is reached: they name no identification type at all,
    so there is nothing for an integrator to be asked about. DD110."""
    handle = XcpTest(DefaultConfig(**_CALLBACK_CONFIG))
    _connect(handle)
    _serve(handle, b'abcd')

    raw_data = _get_id(handle, identification_type)

    assert raw_data[0:2] == (0xFE, 0x22)
    handle.xcp_get_identification_function.assert_not_called()


@pytest.mark.parametrize('address_granularity, length', (('WORD', 3), ('DWORD', 5), ('DWORD', 7)))
def test_get_id_refuses_a_callback_length_that_is_not_a_multiple_of_the_granularity(
        address_granularity, length):
    """DD112's runtime half. XCP part 2 1.1/1.6.1.2.2's "Length mod AG = 0" protects the UPLOAD that
    follows, whose element count 1.1 defines as (Length GET_ID [BYTE]) / AG. The configured string
    is checked at generation time; a callback's length is not knowable then.

    The module cannot emit a non-conforming Length, and reporting the type unavailable is the honest
    alternative to truncating the data or padding it with the NULs 1.1 explicitly says the string
    does not carry. The integrator hears about it through DET, which is the only channel available:
    the master is simply told the type is not there.
    """
    handle = XcpTest(DefaultConfig(address_granularity=address_granularity, **_CALLBACK_CONFIG))
    _connect(handle)
    _serve(handle, b'x' * length)
    # Everything asserted below is about GET_ID alone. Without this, a DET raised by CONNECT or by
    # construction would be the call assert_called_once_with inspects, and the test would report on
    # the wrong one -- passing or failing for a reason that has nothing to do with GET_ID.
    handle.det_report_error.reset_mock()

    # Delivered inline, not through _get_id: the command table's one dispatch site
    # (source/Xcp.c:2161, `Xcp_PIDTable[pid](...)`) is reached only from Xcp_CanIfRxIndication, so
    # Xcp_DTOCmdStdGetId -- and the DET it raises -- runs during this call, never during
    # Xcp_MainFunction. Asserting that here, before Xcp_MainFunction runs at all, grounds the
    # expected API id in the test's own action instead of in a constant copied from the
    # implementation: the error fires during the call just made, so it must name that call. This is
    # what lets this assertion catch a wrong API id, which asserting only after Xcp_MainFunction (as
    # before) never could.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, 0x01)))
    handle.det_report_error.assert_called_once_with(
        ANY, ANY,
        handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
        handle.define('XCP_E_IDENTIFICATION_NOT_GRANULAR'))

    handle.lib.Xcp_MainFunction()
    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert raw_data[0] == 0xFF, 'still a positive response'
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == 0, \
        'a non-conforming length must be reported as unavailable, not emitted'


@pytest.mark.parametrize('address_granularity, length', (('BYTE', 3), ('WORD', 4), ('DWORD', 8)))
def test_get_id_accepts_a_callback_length_that_is_a_multiple_of_the_granularity(
        address_granularity, length):
    """The boundary above from the accepting side, including BYTE, where the rule is vacuous:
    every length is a multiple of 1, so no conforming configuration is ever refused by it."""
    handle = XcpTest(DefaultConfig(address_granularity=address_granularity, **_CALLBACK_CONFIG))
    _connect(handle)
    _serve(handle, b'x' * length)
    handle.det_report_error.reset_mock()   # same reason as the test above

    raw_data = _get_id(handle, 0x01)

    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == length
    handle.det_report_error.assert_not_called()


def test_get_id_does_not_fall_back_to_the_static_identification_when_type_zeros_callback_length_is_not_granular():
    """A type-0 callback that answered E_OK has claimed the type, so when its length is refused the
    response is Length = 0 -- never the configured string. The hazard this pins is ordering and
    state together: `served` is TRUE for such a callback, and served == FALSE together with
    identification_type == XCP_GET_ID_TYPE_ASCII is exactly the static fallback's condition. A
    granularity check that marked the refused request unserved and ran before the fallback block
    would hand type 0 to the configured string, and the response would silently carry its
    conforming, non-zero length instead of the Length = 0 DET just reported -- hiding the very
    defect DET is reporting.

    The default configured string ('/path/to/xcp.a2l', 16 bytes) is itself WORD/DWORD-conforming,
    so if this test ever starts observing that length instead of 0, the cause is the fallback firing,
    not a coincidental failure of the static string's own generation-time check. DD112.
    """
    handle = XcpTest(DefaultConfig(address_granularity='WORD', **_CALLBACK_CONFIG))
    _connect(handle)
    _serve(handle, b'x' * 3)   # 3 is not a multiple of WORD's 2-byte element size
    handle.det_report_error.reset_mock()

    # Same ordering argument as the refusing-a-non-granular-length test above: Xcp_DTOCmdStdGetId,
    # and the DET it raises, run inside Xcp_CanIfRxIndication, never inside Xcp_MainFunction, so
    # this is checked before Xcp_MainFunction runs -- grounding the expected API id in this test's
    # own action rather than in a constant copied from the plan.
    # XCP_GET_ID_TYPE_ASCII -- the only type with a static fallback.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFA, 0x00)))
    handle.det_report_error.assert_called_once_with(
        ANY, ANY,
        handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
        handle.define('XCP_E_IDENTIFICATION_NOT_GRANULAR'))

    handle.lib.Xcp_MainFunction()
    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert raw_data[0] == 0xFF
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == 0, \
        'a callback that claimed type 0 with a bad length must not fall back to the configured string'


@pytest.mark.parametrize('identification', (
    pytest.param('D:\\temp\\new1.a2l', id='backslashes C reads as escapes'),   # 16 characters
    pytest.param('c:\\database\\test.a2l', id='1.1 example 2'),               # 20 characters
    pytest.param('/path/to/"x".a2l', id='double quotes'),                      # 16 characters
))
def test_get_id_reports_a_configured_identification_needing_c_escapes_at_its_own_length(
        identification):
    """DD112's generation half counts the configured string's characters; GET_ID reports the
    compiled C string's bytes. This is where the two are shown to agree. The generator pastes the
    identification into a C string literal, so a backslash or double quote in it must be escaped
    there. Unescaped, C reads D:\\temp\\new1.a2l's \\t and \\n as a tab and a line feed and
    compiles its 16 characters to 14 bytes -- a Length that violates the Length mod AG = 0 the
    generator had just accepted, with no DET, because the run-time check covers only callback
    lengths. c:\\database\\test.a2l is XCP part 2 1.1/1.6.1.2.2's own second example.

    DWORD, the strictest granularity: every row is a multiple of 4 characters, so the generator
    accepts each one, and the Length on the wire must be that same number. The generated string's
    content is checked as well, so an escape that doubled a character instead of preserving it
    fails here too.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='DWORD',
                                   identification=identification))
    _connect(handle)

    raw_data = _get_id(handle, 0x00)

    assert raw_data[0] == 0xFF
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == len(identification), \
        'GET_ID must report the configured identification at the length the generator checked'
    assert handle.ffi.string(handle.config.lib.Xcp[0].general.identification) == \
        identification.encode('ascii'), 'the generated C literal must compile to the configured string'

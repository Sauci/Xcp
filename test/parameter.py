import hashlib
import json
import pytest
import random
import struct

from math import floor

dummy_byte = 0xFF

address_extensions = [pytest.param(v, id='address extension = {:02}d'.format(v)) for v in range(8)]
address_granularities = [pytest.param('BYTE', id='AG = BYTE'),
                         pytest.param('WORD', id='AG = WORD'),
                         pytest.param('DWORD', id='AG = DWORD')]
byte_orders = [pytest.param('BIG_ENDIAN', id='byte_order = BIG_ENDIAN'),
               pytest.param('LITTLE_ENDIAN', id='byte_order = LITTLE_ENDIAN')]
max_ctos = [pytest.param(v, id='MAX_CTO = {:04X}h'.format(v)) for v in (8, 128, 256)]
mtas = [pytest.param(v, id='MTA = {:08X}h'.format(v)) for v in (0xDEADBEEF,)]
resources = [pytest.param(1, id='RESOURCE = CAL/PAG'),
             pytest.param(4, id='RESOURCE = DAQ'),
             pytest.param(8, id='RESOURCE = STIM'),
             pytest.param(16, id='RESOURCE = PGM')]
seeds = [pytest.param(v, id='seed length = {:03}d'.format(v)) for v in range(0x01, 0x100)]
trailing_values = [pytest.param(v, id='trailing value = {:02X}h'.format(v)) for v in (0, 255)]
cto_queue_sizes = [pytest.param(v, id='CTO_QUEUE_SIZE = {:02}d'.format(v)) for v in (0, 1, 255)]
max_bss = [pytest.param(v, id='MAX_BS = {:02}d'.format(v)) for v in (0, 1, 255)]
min_sts = [pytest.param(v, id='MIN_ST = {:02}d'.format(v)) for v in (0, 1, 255)]
max_dtos = [pytest.param(v, id='MAX_DTO = {:03}d'.format(v)) for v in (8, 16, 64)]
identification_field_types = [pytest.param(v, id='ident = {}'.format(v))
                              for v in ('ABSOLUTE', 'RELATIVE_BYTE', 'RELATIVE_WORD',
                                        'RELATIVE_WORD_ALIGNED')]

identification_field_size = {'ABSOLUTE': 1,
                             'RELATIVE_BYTE': 2,
                             'RELATIVE_WORD': 3,
                             'RELATIVE_WORD_ALIGNED': 4}


def expected_identification_field(ident, first_pid, relative_odt, daq_list_number, byte_order,
                                  fill=0):
    """The bytes a DTO must start with, per XCP part 2 1.1/1.1.2.1."""
    if ident == 'ABSOLUTE':
        return (first_pid + relative_odt,)
    if ident == 'RELATIVE_BYTE':
        return (relative_odt, daq_list_number & 0xFF)
    if ident == 'RELATIVE_WORD':
        return (relative_odt,) + tuple(u16_to_array(daq_list_number, byte_order))
    return (relative_odt, fill) + tuple(u16_to_array(daq_list_number, byte_order))


def plan_odt_entries(capacity, element_size, wanted):
    """Entry sizes that fit one ODT: each a multiple of the granularity, summing within
    capacity. Returns fewer than `wanted` when the capacity cannot hold that many."""
    sizes = []
    remaining = capacity - (capacity % element_size)
    while len(sizes) < wanted and remaining >= element_size:
        size = element_size if (len(sizes) + 1) < wanted else min(remaining, element_size * 2)
        size = size - (size % element_size)
        if size == 0 or size > remaining:
            break
        sizes.append(size)
        remaining -= size
    return sizes


def element_size_from_address_granularity(address_granularity):
    return dict(BYTE=1, WORD=2, DWORD=4)[address_granularity]


def generate_random_block_content(n, element_size, base_address) -> [(int, int)]:
    return list((base_address + (i * element_size), random.getrandbits(8 * element_size, )) for i in range(n))


def get_block_slices_for_max_cto(block, element_size, max_cto=8):
    n = floor((max_cto - 1) / element_size)
    return [block[i * n:(i + 1) * n] for i in range(len(block)) if len(block[i * n:(i + 1) * n]) != 0]


def address_to_array(address: int, byte_size: int, endianness: str) -> [int]:
    return [int(b) for b in address.to_bytes(byte_size,
                                             dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[endianness],
                                             signed=False)]


def u16_to_array(value: int, endianness: str) -> [int]:
    return [int(b) for b in value.to_bytes(2, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[endianness], signed=False)]


def u32_to_array(value: int, endianness: str) -> [int]:
    return [int(b) for b in value.to_bytes(4, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[endianness], signed=False)]


def u32_from_array(data: bytearray, endianness: str):
    return int.from_bytes(data, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[endianness], signed=False)


def payload_to_array(payload, number_of_data_elements, element_size, byte_order):
    return struct.unpack('{}{}'.format('>' if byte_order == 'BIG_ENDIAN' else '<',
                                       {1: 'B', 2: 'H', 4: 'I'}[element_size] *
                                       number_of_data_elements), payload)


def page(init_segment=0,
         ecu_access='DONT_CARE',
         xcp_read_access='DONT_CARE',
         xcp_write_access='DONT_CARE'):
    return {"init_segment": init_segment,
            "ecu_access": ecu_access,
            "xcp_read_access": xcp_read_access,
            "xcp_write_access": xcp_write_access}


def address_mapping(source_address=0, destination_address=0, length=0):
    return {"source_address": source_address,
            "destination_address": destination_address,
            "length": length}


def segment(name='CAL_SEG',
            address=0x00400000,
            length=0x1000,
            address_extension=0,
            compression_method=0,
            encryption_method=0,
            pages=None,
            address_mappings=None):
    return {"name": name,
            "address": address,
            "length": length,
            "address_extension": address_extension,
            "compression_method": compression_method,
            "encryption_method": encryption_method,
            "pages": list(pages) if pages is not None else [page()],
            "address_mappings": list(address_mappings) if address_mappings is not None else []}


def daq(name='DAQ1',
        type='DAQ',
        max_odt=1,
        max_odt_entries=1,
        pdu_mapping='XCP_PDU_ID_TRANSMIT',
        dtos=None):
    # No "pid" here when the caller does not pass dtos: FIRST_PID is derived and assigned by the
    # slave (XCP part 2 1.1/1.6.4.1.1.4), so a caller with no opinion on it should not assert one.
    # The generator's `dto.pid | default(0)` fallback keeps Xcp_DtoConfig buildable, and leaving
    # "pid" undefined keeps source_cfg.c.jinja2's FIRST_PID validation from firing on a value this
    # helper made up rather than one the caller actually configured.
    return {"name": name,
            "type": type,
            "max_odt": max_odt,
            "max_odt_entries": max_odt_entries,
            "pdu_mapping": pdu_mapping,
            "dtos": list(dtos) if dtos is not None else [{}]}


timestamp_sizes = [pytest.param(v, id='TS = {}'.format(v)) for v in ('BYTE', 'WORD', 'DWORD')]

# The wire encoding of the TIMESTAMP_MODE size field, XCP part 2 - Protocol Layer Specification
# 1.1/1.6.4.1.2.5. Deliberately not Xcp_TimestampTypeType's enumerator values: that enum is
# implicit, so FOUR_BYTE == 3, and 3 is the one size the specification marks "Not allowed".
timestamp_wire_size = {'BYTE': 1, 'WORD': 2, 'DWORD': 4, None: 0}


def timestamp(size='DWORD', unit='TIMESTAMP_UNIT_1MS', ticks=1):
    return {"size": size, "unit": unit, "ticks": ticks}


def event(consistency='ODT',
          priority=0,
          time_cycle=10,
          time_unit='TIMESTAMP_UNIT_1MS',
          type='DAQ',
          triggered_daq_list_ref=None,
          name=None):
    # name=None omits the key entirely rather than inventing one: protocol_layer.publish_names
    # defaults to True (DefaultConfig below), and script/source_cfg.c.jinja2 rejects a published
    # event channel with no name, so a caller testing that guard must see it fire, not see this
    # helper paper over the missing name.
    result = {"consistency": consistency,
              "priority": priority,
              "time_cycle": time_cycle,
              "time_unit": time_unit,
              "type": type,
              "triggered_daq_list_ref": list(triggered_daq_list_ref)
              if triggered_daq_list_ref is not None else ['DAQ1']}
    if name is not None:
        result["name"] = name
    return result


class DefaultConfig(dict):
    def __init__(self,
                 channel_rx_pdu_ref=0x0001,
                 channel_tx_pdu_ref=0x0002,
                 default_daq_dto_pdu_mapping=0x0003,
                 events=None,
                 daqs=({
                     "name": "DAQ1",
                     "type": "DAQ",
                     "max_odt": 1,
                     "max_odt_entries": 1,
                     "pdu_mapping": "XCP_PDU_ID_TRANSMIT",
                     "dtos": [
                         {
                             "pid": 0
                         }
                     ]
                 },),
                 daq_config_type='STATIC',
                 # Read only when daq_config_type is 'DYNAMIC'. A STATIC configuration emits no
                 # daq_dynamic block at all -- the generator refuses one, since a pool nothing can
                 # ever allocate from is an integrator saying two incompatible things at once.
                 daq_count=4,
                 odt_count=8,
                 odt_entries_count=16,
                 # Direction the pool supports, mirroring daqs[].type for a static list. Read only
                 # when daq_config_type is 'DYNAMIC', for the same reason as the three dimensions
                 # above. 'DAQ' is both this default and the schema's, so a dynamic configuration
                 # that says nothing reserves no stimulation storage at all.
                 daq_dynamic_type='DAQ',
                 segments=(),
                 freeze_supported=False,
                 xcp_set_request_api_enable=True,
                 xcp_get_id_api_enable=True,
                 xcp_get_seed_api_enable=True,
                 xcp_unlock_api_enable=True,
                 xcp_set_mta_api_enable=True,
                 xcp_upload_api_enable=True,
                 xcp_short_upload_api_enable=True,
                 xcp_build_checksum_api_enable=True,
                 xcp_download_api_enable=True,
                 xcp_download_max_api_enable=True,
                 xcp_short_download_api_enable=True,
                 xcp_set_cal_page_api_enable=True,
                 xcp_get_cal_page_api_enable=True,
                 xcp_clear_daq_list_api_enable=True,
                 xcp_set_daq_ptr_api_enable=True,
                 xcp_write_daq_api_enable=True,
                 # Unlike every other *_api_enable default above, this one defaults to False, not
                 # True: WRITE_DAQ_MULTIPLE's own generation guard (script/source_cfg.c.jinja2)
                 # rejects MAX_CTO < 10, and this class's own max_cto default is 8. Defaulting this
                 # flag to True would make DefaultConfig() itself fail to generate, breaking every
                 # test in the suite that does not care about WRITE_DAQ_MULTIPLE at all. Tests that
                 # exercise the command pass both xcp_write_daq_multiple_api_enable=True and a
                 # max_cto >= 10 explicitly.
                 xcp_write_daq_multiple_api_enable=False,
                 xcp_set_daq_list_mode_api_enable=True,
                 xcp_get_daq_list_mode_api_enable=True,
                 xcp_start_stop_daq_list_api_enable=True,
                 xcp_start_stop_synch_api_enable=True,
                 xcp_get_daq_clock_api_enable=True,
                 xcp_read_daq_api_enable=True,
                 xcp_get_daq_processor_info_api_enable=True,
                 xcp_get_daq_resolution_info_api_enable=True,
                 xcp_get_daq_list_info_api_enable=True,
                 xcp_get_daq_event_info_api_enable=True,
                 # False, not True, for the same reason as xcp_write_daq_multiple_api_enable
                 # above: the generation guard added with SP2d rejects these four being enabled
                 # under a STATIC configuration, and this class's own daq_config_type default is
                 # STATIC. Defaulting them True would make DefaultConfig() itself fail to
                 # generate. A DYNAMIC configuration must enable all four, and the guard rejects
                 # that direction too -- dynamic_config() below is what supplies the coherent set.
                 xcp_free_daq_api_enable=False,
                 xcp_alloc_daq_api_enable=False,
                 xcp_alloc_odt_api_enable=False,
                 xcp_alloc_odt_entry_api_enable=False,
                 xcp_program_clear_api_enable=True,
                 xcp_program_api_enable=True,
                 xcp_program_max_api_enable=True,
                 xcp_get_comm_mode_info_api_enable=True,
                 xcp_download_next_api_enable=True,
                 xcp_modify_bits_api_enable=True,
                 xcp_get_pag_processor_info_api_enable=True,
                 xcp_get_segment_info_api_enable=True,
                 xcp_get_page_info_api_enable=True,
                 xcp_set_segment_mode_api_enable=True,
                 xcp_get_segment_mode_api_enable=True,
                 xcp_copy_cal_page_api_enable=True,
                 resource_protection_calibration_paging=False,
                 resource_protection_data_acquisition=False,
                 resource_protection_data_stimulation=False,
                 resource_protection_programming=False,
                 byte_order='LITTLE_ENDIAN',
                 address_granularity='BYTE',
                 master_block_mode=True,
                 slave_block_mode=True,
                 interleaved_mode=False,
                 max_bs=255,
                 min_st=255,
                 cto_queue_size=16,
                 event_queue_size=16,
                 max_cto=8,
                 max_dto=8,
                 identification_field_type='ABSOLUTE',
                 daq_queue_size=16,
                 prescaler_supported=True,
                 publish_names=True,
                 overload_indication='EVENT',
                 checksum_type='XCP_CRC_32',
                 user_defined_checksum_function='Xcp_UserDefinedChecksumFunction',
                 user_cmd_function='Xcp_UserCmdFunction',
                 trailing_value=0,
                 identification='/path/to/database.a2l',
                 timestamp=None):
        self._channel_rx_pdu = channel_rx_pdu_ref
        self._channel_tx_pdu = channel_tx_pdu_ref
        self._default_daq_dto_pdu_mapping = default_daq_dto_pdu_mapping
        self._event_queue_size = event_queue_size
        self._daq_queue_size = daq_queue_size
        protocol_layer = {
            "byte_order": byte_order,
            "address_granularity": address_granularity,
            "master_block_mode": master_block_mode,
            "slave_block_mode": slave_block_mode,
            "interleaved_mode": interleaved_mode,
            "max_bs": max_bs,
            "min_st": min_st,
            "cto_queue_size": cto_queue_size,
            "event_queue_size": event_queue_size,
            "max_cto": max_cto,
            "max_dto": max_dto,
            "identification_field_type": identification_field_type,
            "daq_queue_size": daq_queue_size,
            "prescaler_supported": prescaler_supported,
            "publish_names": publish_names,
            "overload_indication": overload_indication,
            "checksum_type": checksum_type,
            "user_defined_checksum_function": user_defined_checksum_function,
            "user_cmd_function": user_cmd_function,
            "trailing_value": trailing_value,
            'identification': identification,
            "daq_config_type": daq_config_type
        }
        if timestamp is not None:
            protocol_layer["timestamp"] = timestamp
        # A DAQ_DYNAMIC configuration declares no DAQ lists -- the master allocates them out of
        # the pool -- so "daqs" is dropped entirely rather than left empty, and with no list to
        # name, every event's triggered_daq_list_ref goes with it. Both are what the generator's
        # own coherence guards demand; leaving either in place makes generation fail.
        events = list(events) if events is not None else [event(name='EVT1')]
        if daq_config_type == 'DYNAMIC':
            events = [{key: value for key, value in one.items()
                       if key != 'triggered_daq_list_ref'} for one in events]
        super(DefaultConfig, self).__init__(configurations=[
            {
                "communication": {
                    "channel_rx_pdu_ref": "XCP_PDU_ID_CTO_RX",
                    "channel_tx_pdu_ref": "XCP_PDU_ID_CTO_TX"
                },
                "daqs": list(daqs),
                "segments": list(segments),
                "paging": {"freeze_supported": freeze_supported},
                # event()'s own bare default omits "name" (see its docstring comment), and
                # publish_names defaults to True two lines above -- so DefaultConfig's own
                # fallback event needs a name of its own, or every test that builds DefaultConfig()
                # without an explicit events= would trip script/source_cfg.c.jinja2's publish_names
                # guard by accident. That fallback is applied where `events` is normalised above,
                # so that the DAQ_DYNAMIC branch there sees it too.
                "events": events,
                "apis": {
                    "xcp_set_request_api_enable": {"enabled": xcp_set_request_api_enable, "protected": False},
                    "xcp_get_id_api_enable": {"enabled": xcp_get_id_api_enable, "protected": False},
                    "xcp_get_seed_api_enable": {"enabled": xcp_get_seed_api_enable, "protected": False},
                    "xcp_unlock_api_enable": {"enabled": xcp_unlock_api_enable, "protected": False},
                    "xcp_set_mta_api_enable": {"enabled": xcp_set_mta_api_enable, "protected": False},
                    "xcp_upload_api_enable": {"enabled": xcp_upload_api_enable, "protected": False},
                    "xcp_short_upload_api_enable": {"enabled": xcp_short_upload_api_enable, "protected": False},
                    "xcp_build_checksum_api_enable": {"enabled": xcp_build_checksum_api_enable, "protected": False},
                    "xcp_download_api_enable": {"enabled": xcp_download_api_enable, "protected": False},
                    "xcp_download_max_api_enable": {"enabled": xcp_download_max_api_enable, "protected": False},
                    "xcp_short_download_api_enable": {"enabled": xcp_short_download_api_enable, "protected": False},
                    "xcp_set_cal_page_api_enable": {"enabled": xcp_set_cal_page_api_enable, "protected": False},
                    "xcp_get_cal_page_api_enable": {"enabled": xcp_get_cal_page_api_enable, "protected": False},
                    "xcp_clear_daq_list_api_enable": {"enabled": xcp_clear_daq_list_api_enable, "protected": False},
                    "xcp_set_daq_ptr_api_enable": {"enabled": xcp_set_daq_ptr_api_enable, "protected": False},
                    "xcp_write_daq_api_enable": {"enabled": xcp_write_daq_api_enable, "protected": False},
                    "xcp_write_daq_multiple_api_enable": {"enabled": xcp_write_daq_multiple_api_enable,
                                                          "protected": False},
                    "xcp_set_daq_list_mode_api_enable": {"enabled": xcp_set_daq_list_mode_api_enable,
                                                         "protected": False},
                    "xcp_get_daq_list_mode_api_enable": {"enabled": xcp_get_daq_list_mode_api_enable,
                                                         "protected": False},
                    "xcp_start_stop_daq_list_api_enable": {"enabled": xcp_start_stop_daq_list_api_enable,
                                                           "protected": False},
                    "xcp_start_stop_synch_api_enable": {"enabled": xcp_start_stop_synch_api_enable, "protected": False},
                    "xcp_get_daq_clock_api_enable": {"enabled": xcp_get_daq_clock_api_enable, "protected": False},
                    "xcp_read_daq_api_enable": {"enabled": xcp_read_daq_api_enable, "protected": False},
                    "xcp_get_daq_processor_info_api_enable": {"enabled": xcp_get_daq_processor_info_api_enable,
                                                              "protected": False},
                    "xcp_get_daq_resolution_info_api_enable": {"enabled": xcp_get_daq_resolution_info_api_enable,
                                                               "protected": False},
                    "xcp_get_daq_list_info_api_enable": {"enabled": xcp_get_daq_list_info_api_enable,
                                                         "protected": False},
                    "xcp_get_daq_event_info_api_enable": {"enabled": xcp_get_daq_event_info_api_enable,
                                                          "protected": False},
                    "xcp_free_daq_api_enable": {"enabled": xcp_free_daq_api_enable, "protected": False},
                    "xcp_alloc_daq_api_enable": {"enabled": xcp_alloc_daq_api_enable, "protected": False},
                    "xcp_alloc_odt_api_enable": {"enabled": xcp_alloc_odt_api_enable, "protected": False},
                    "xcp_alloc_odt_entry_api_enable": {"enabled": xcp_alloc_odt_entry_api_enable, "protected": False},
                    "xcp_program_clear_api_enable": {"enabled": xcp_program_clear_api_enable, "protected": False},
                    "xcp_program_api_enable": {"enabled": xcp_program_api_enable, "protected": False},
                    "xcp_program_max_api_enable": {"enabled": xcp_program_max_api_enable, "protected": False},
                    "xcp_get_comm_mode_info_api_enable": {"enabled": xcp_get_comm_mode_info_api_enable,
                                                          "protected": False},
                    "xcp_download_next_api_enable": {"enabled": xcp_download_next_api_enable, "protected": False},
                    "xcp_modify_bits_api_enable": {"enabled": xcp_modify_bits_api_enable, "protected": False},
                    "xcp_get_pag_processor_info_api_enable": {"enabled": xcp_get_pag_processor_info_api_enable,
                                                              "protected": False},
                    "xcp_get_segment_info_api_enable": {"enabled": xcp_get_segment_info_api_enable,
                                                        "protected": False},
                    "xcp_get_page_info_api_enable": {"enabled": xcp_get_page_info_api_enable, "protected": False},
                    "xcp_set_segment_mode_api_enable": {"enabled": xcp_set_segment_mode_api_enable,
                                                        "protected": False},
                    "xcp_get_segment_mode_api_enable": {"enabled": xcp_get_segment_mode_api_enable,
                                                        "protected": False},
                    "xcp_copy_cal_page_api_enable": {"enabled": xcp_copy_cal_page_api_enable, "protected": False},
                    "resource_protection": {
                        "calibration_paging": resource_protection_calibration_paging,
                        "data_acquisition": resource_protection_data_acquisition,
                        "data_stimulation": resource_protection_data_stimulation,
                        "programming": resource_protection_programming
                    }
                },
                "protocol_layer": protocol_layer
            }
        ])
        if daq_config_type == 'DYNAMIC':
            configuration = self['configurations'][0]
            del configuration["daqs"]
            # pdu_mapping is not a keyword argument of its own: every list the master allocates
            # out of one pool transmits on the same PDU, and XCP_PDU_ID_TRANSMIT is the name
            # test/conftest.py compiles a value for -- the same one daq() and the daqs default
            # above already use.
            configuration["daq_dynamic"] = {"daq_count": daq_count,
                                            "odt_count": odt_count,
                                            "odt_entries_count": odt_entries_count,
                                            "pdu_mapping": "XCP_PDU_ID_TRANSMIT",
                                            "type": daq_dynamic_type}

    @property
    def get_id(self):
        tmp = self.copy()
        tmp.update(dict(_channel_rx_pdu=self.channel_rx_pdu,
                        _channel_tx_pdu=self.channel_tx_pdu,
                        _default_daq_dto_pdu_mapping=self.default_daq_dto_pdu_mapping))
        return hashlib.sha224(json.dumps(tmp, sort_keys=True, indent=0).encode('utf-8')).hexdigest()[0:8]

    @property
    def channel_rx_pdu(self):
        return self._channel_rx_pdu

    @property
    def channel_tx_pdu(self):
        return self._channel_tx_pdu

    @property
    def default_daq_dto_pdu_mapping(self):
        return self._default_daq_dto_pdu_mapping

    @property
    def event_queue_size(self):
        return self._event_queue_size

    @property
    def daq_queue_size(self):
        return self._daq_queue_size


def dynamic_config(daq_count=4, odt_count=8, odt_entries_count=16, **kwargs):
    """A DefaultConfig with a dynamic DAQ pool. The four ALLOC APIs must all be enabled: the
    generator refuses a DAQ_DYNAMIC configuration with any of them disabled, since that is a
    dynamic build with no way to allocate. `daqs` is left empty because a dynamic configuration
    declares no lists -- the master allocates them."""
    return DefaultConfig(daq_config_type='DYNAMIC',
                         daq_count=daq_count,
                         odt_count=odt_count,
                         odt_entries_count=odt_entries_count,
                         daqs=(),
                         xcp_free_daq_api_enable=True,
                         xcp_alloc_daq_api_enable=True,
                         xcp_alloc_odt_api_enable=True,
                         xcp_alloc_odt_entry_api_enable=True,
                         **kwargs)


def stim_config(daq_count=2, odt_count=2, odt_entries_count=2, pool_type='DAQ_STIM', **kwargs):
    """A dynamic pool that can receive stimulation. Mirrors dynamic_config, which builds a
    DAQ-only pool; both enable the four ALLOC APIs, which a DAQ_DYNAMIC configuration must."""
    return dynamic_config(daq_count=daq_count, odt_count=odt_count,
                          odt_entries_count=odt_entries_count, daq_dynamic_type=pool_type, **kwargs)


class MultiConfig(dict):
    """A configuration file carrying more than one configuration.

    DefaultConfig always emits exactly one, so until this existed every aggregation over
    `configurations` was unexercised: the `any`/`max` folds in script/header_cfg.h.jinja2, the
    matching ones in test/conftest.py's own compile definitions, and CMakeLists.txt's derivation
    of the same macros. So was the distinction those aggregations exist to preserve -- a
    build-wide macro says what SOME configuration needs, and a command must still gate on what
    *the active* configuration declares (Xcp_Ptr->general->...). A single-configuration harness
    cannot tell the two apart, because there the build-wide answer and the per-configuration
    answer are always the same.

    Composed from already-built DefaultConfig instances rather than from a second parallel set of
    keyword arguments, so each configuration is still described exactly the way every other test
    in the suite describes one. Select which one Xcp_Init runs against with XcpTest's
    configuration_index.
    """

    def __init__(self, *configs):
        if len(configs) < 2:
            raise ValueError('MultiConfig exists to hold more than one configuration; '
                             'use DefaultConfig directly for one')
        # Every configuration in one generated file shares the PDU reference *names*
        # (XCP_PDU_ID_CTO_RX and friends are literals in DefaultConfig's communication/daqs
        # blocks), and test/conftest.py passes each name to the compiler exactly once. Two
        # configurations asking for different numeric values for one name is therefore not
        # something the generated file could express; refuse it here rather than silently
        # applying the first one's value to both.
        for attribute in ('channel_rx_pdu', 'channel_tx_pdu', 'default_daq_dto_pdu_mapping'):
            values = set(getattr(config, attribute) for config in configs)
            if len(values) != 1:
                raise ValueError('{} differs between configurations ({}), but every configuration '
                                 'in one generated file shares that PDU reference name'.format(
                                         attribute, sorted(values)))
        self._channel_rx_pdu = configs[0].channel_rx_pdu
        self._channel_tx_pdu = configs[0].channel_tx_pdu
        self._default_daq_dto_pdu_mapping = configs[0].default_daq_dto_pdu_mapping
        # XCP_EVENT_QUEUE_SIZE is one compile definition for the whole module, so it takes the
        # largest any configuration asks for -- the same fold header_cfg.h.jinja2 applies to
        # XCP_MAX_DTO.
        self._event_queue_size = max(config.event_queue_size for config in configs)
        self._daq_queue_size = max(config.daq_queue_size for config in configs)
        super(MultiConfig, self).__init__(
                configurations=[configuration
                                for config in configs
                                for configuration in config['configurations']])

    get_id = DefaultConfig.get_id
    channel_rx_pdu = DefaultConfig.channel_rx_pdu
    channel_tx_pdu = DefaultConfig.channel_tx_pdu
    default_daq_dto_pdu_mapping = DefaultConfig.default_daq_dto_pdu_mapping
    event_queue_size = DefaultConfig.event_queue_size
    daq_queue_size = DefaultConfig.daq_queue_size


if __name__ == '__main__':
    a = DefaultConfig()
    print(a.get_id)

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
queue_sizes = [pytest.param(v, id='QUEUE_SIZE = {:02}d'.format(v)) for v in (0, 1, 255)]
max_bss = [pytest.param(v, id='MAX_BS = {:02}d'.format(v)) for v in (0, 1, 255)]
min_sts = [pytest.param(v, id='MIN_ST = {:02}d'.format(v)) for v in (0, 1, 255)]


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


class DAQ(object):
    def __init__(self, name, type, max_odt, max_odt_entries, dtos):
        self._name = name
        self._type = type
        self._max_odt = max_odt
        self._max_odt_entries = max_odt_entries
        self._dtos = dtos


class DefaultConfig(dict):
    def __init__(self,
                 channel_rx_pdu_ref=0x0001,
                 channel_tx_pdu_ref=0x0002,
                 default_daq_dto_pdu_mapping=0x0003,
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
                 xcp_free_daq_api_enable=True,
                 xcp_alloc_daq_api_enable=True,
                 xcp_alloc_odt_api_enable=True,
                 xcp_alloc_odt_entry_api_enable=True,
                 xcp_program_clear_api_enable=True,
                 xcp_program_api_enable=True,
                 xcp_program_max_api_enable=True,
                 xcp_get_comm_mode_info_api_enable=True,
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
                 checksum_type='XCP_CRC_32',
                 user_defined_checksum_function='Xcp_UserDefinedChecksumFunction',
                 user_cmd_function='Xcp_UserCmdFunction',
                 trailing_value=0,
                 identification='/path/to/database.a2l'):
        self._channel_rx_pdu = channel_rx_pdu_ref
        self._channel_tx_pdu = channel_tx_pdu_ref
        self._default_daq_dto_pdu_mapping = default_daq_dto_pdu_mapping
        self._event_queue_size = event_queue_size
        super(DefaultConfig, self).__init__(configurations=[
            {
                "communication": {
                    "channel_rx_pdu_ref": "XCP_PDU_ID_CTO_RX",
                    "channel_tx_pdu_ref": "XCP_PDU_ID_CTO_TX"
                },
                "daqs": list(daqs),
                "events": [
                    {
                        "consistency": "ODT",
                        "priority": 0,
                        "time_cycle": 10,
                        "time_unit": "TIMESTAMP_UNIT_1MS",
                        "triggered_daq_list_ref": [
                            "DAQ1"
                        ]
                    }
                ],
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
                    "resource_protection": {
                        "calibration_paging": resource_protection_calibration_paging,
                        "data_acquisition": resource_protection_data_acquisition,
                        "data_stimulation": resource_protection_data_stimulation,
                        "programming": resource_protection_programming
                    }
                },
                "protocol_layer": {
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
                    "checksum_type": checksum_type,
                    "user_defined_checksum_function": user_defined_checksum_function,
                    "user_cmd_function": user_cmd_function,
                    "trailing_value": trailing_value,
                    'identification': identification
                }
            }
        ])

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


if __name__ == '__main__':
    a = DefaultConfig()
    print(a.get_id)

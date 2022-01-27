import hashlib
import json

dummy_byte = 0xFF


class Config(dict):
    def __init__(self, *args, **kwargs):
        super(Config, self).__init__(*args, **kwargs)
        self._channel_rx_pdu_ref = 0x0001
        self._channel_tx_pdu_ref = 0x0002
        self._default_daq_dto_pdu_mapping = 0x0003

    @property
    def get_id(self):
        return hashlib.sha224(json.dumps(self, sort_keys=True, indent=0).encode('utf-8')).hexdigest()[0:8]

    @property
    def channel_rx_pdu_ref(self) -> int:
        return self._channel_rx_pdu_ref

    @property
    def channel_tx_pdu_ref(self) -> int:
        return self._channel_tx_pdu_ref

    @property
    def default_daq_dto_pdu_mapping(self) -> int:
        return self._default_daq_dto_pdu_mapping


class DefaultConfig(Config):
    def __init__(self,
                 channel_rx_pdu_ref=0x0001,
                 channel_tx_pdu_ref=0x0002,
                 default_daq_dto_pdu_mapping=0x0003,
                 daq_type="DAQ",
                 xcp_set_request_api_enable=True,
                 xcp_get_id_api_enable=True,
                 xcp_get_seed_api_enable=True,
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
                 byte_order='LITTLE_ENDIAN',
                 address_granularity='DWORD',
                 slave_block_mode=True,
                 max_cto=8,
                 max_dto=8):
        super(DefaultConfig, self).__init__({
            "configurations": [
                {
                    "communication": {
                        "channel_rx_pdu_ref": "XCP_PDU_ID_CTO_RX",
                        "channel_tx_pdu_ref": "XCP_PDU_ID_CTO_TX"
                    },
                    "daqs": [
                        {
                            "name": "DAQ1",
                            "type": daq_type,
                            "max_odt": 1,
                            "max_odt_entries": 1,
                            "dtos": [
                                {
                                    "pid": 0,
                                    "pdu_mapping": "XCP_PDU_ID_TRANSMIT"
                                }
                            ]
                        }
                    ],
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
                        "xcp_set_request_api_enable": xcp_set_request_api_enable,
                        "xcp_get_id_api_enable": xcp_get_id_api_enable,
                        "xcp_get_seed_api_enable": xcp_get_seed_api_enable,
                        "xcp_download_api_enable": xcp_download_api_enable,
                        "xcp_download_max_api_enable": xcp_download_max_api_enable,
                        "xcp_short_download_api_enable": xcp_short_download_api_enable,
                        "xcp_set_cal_page_api_enable": xcp_set_cal_page_api_enable,
                        "xcp_get_cal_page_api_enable": xcp_get_cal_page_api_enable,
                        "xcp_clear_daq_list_api_enable": xcp_clear_daq_list_api_enable,
                        "xcp_set_daq_ptr_api_enable": xcp_set_daq_ptr_api_enable,
                        "xcp_write_daq_api_enable": xcp_write_daq_api_enable,
                        "xcp_set_daq_list_mode_api_enable": xcp_set_daq_list_mode_api_enable,
                        "xcp_get_daq_list_mode_api_enable": xcp_get_daq_list_mode_api_enable,
                        "xcp_start_stop_daq_list_api_enable": xcp_start_stop_daq_list_api_enable,
                        "xcp_start_stop_synch_api_enable": xcp_start_stop_synch_api_enable,
                        "xcp_get_daq_clock_api_enable": xcp_get_daq_clock_api_enable,
                        "xcp_read_daq_api_enable": xcp_read_daq_api_enable,
                        "xcp_get_daq_processor_info_api_enable": xcp_get_daq_processor_info_api_enable,
                        "xcp_get_daq_resolution_info_api_enable": xcp_get_daq_resolution_info_api_enable,
                        "xcp_get_daq_list_info_api_enable": xcp_get_daq_list_info_api_enable,
                        "xcp_get_daq_event_info_api_enable": xcp_get_daq_event_info_api_enable,
                        "xcp_free_daq_api_enable": xcp_free_daq_api_enable,
                        "xcp_alloc_daq_api_enable": xcp_alloc_daq_api_enable,
                        "xcp_alloc_odt_api_enable": xcp_alloc_odt_api_enable,
                        "xcp_alloc_odt_entry_api_enable": xcp_alloc_odt_entry_api_enable,
                        "xcp_program_clear_api_enable": xcp_program_clear_api_enable,
                        "xcp_program_api_enable": xcp_program_api_enable,
                        "xcp_program_max_api_enable": xcp_program_max_api_enable,
                        "xcp_get_comm_mode_info_api_enable": xcp_get_comm_mode_info_api_enable
                    },
                    "protocol_layer": {
                        "byte_order": byte_order,
                        "address_granularity": address_granularity,
                        "slave_block_mode": slave_block_mode,
                        "max_cto": max_cto,
                        "max_dto": max_dto
                    }
                }
            ]
        })
        self._channel_rx_pdu_ref = channel_rx_pdu_ref
        self._channel_tx_pdu_ref = channel_tx_pdu_ref
        self._default_daq_dto_pdu_mapping = default_daq_dto_pdu_mapping

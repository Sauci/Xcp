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
    def channel_rx_pdu_ref(self) -> (str, int):
        return self._channel_rx_pdu_ref

    @property
    def channel_tx_pdu_ref(self) -> (str, int):
        return self._channel_tx_pdu_ref

    @property
    def default_daq_dto_pdu_mapping(self) -> (str, int):
        return self._default_daq_dto_pdu_mapping


class DefaultConfig(Config):
    def __init__(self, channel_rx_pdu_ref=0x0001, channel_tx_pdu_ref=0x0002, default_daq_dto_pdu_mapping=0x0003):
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
                            "type": "DAQ",
                            "max_odt": 3,
                            "max_odt_entries": 9,
                            "dtos": [
                                {
                                    "pid": 0,
                                    "pdu_mapping": "XCP_PDU_ID_TRANSMIT"
                                }
                            ]
                        },
                        {
                            "name": "DAQ2",
                            "type": "DAQ",
                            "max_odt": 5,
                            "max_odt_entries": 10,
                            "dtos": [
                                {
                                    "pid": 1,
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
                    ]
                }
            ]
        })
        self._channel_rx_pdu_ref = channel_rx_pdu_ref
        self._channel_tx_pdu_ref = channel_tx_pdu_ref
        self._default_daq_dto_pdu_mapping = default_daq_dto_pdu_mapping

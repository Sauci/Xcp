import hashlib
import json
import pytest


class Config(dict):

    @property
    def get_id(self):
        return hashlib.sha224(json.dumps(self, sort_keys=True, indent=0).encode('utf-8')).hexdigest()[0:8]


class DefaultConfig(Config):
    def __init__(self):
        super(DefaultConfig, self).__init__({
            "configurations": [
                {
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

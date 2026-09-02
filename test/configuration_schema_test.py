#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Checks the harness' own configurations against config/xcp.schema.json.

generated/CMakeLists.txt passes -schema, so an integrator building through CMake gets their
configuration validated before anything is generated. The harness does not take that path: it drives
BSWCodeGen through its Python API, so nothing here validated against the schema and the two drifted
apart unnoticed -- the schema still demanded a "pid" per DTO long after FIRST_PID became a value the
slave derives (XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4) and the generator stopped
needing one. These tests tie the two back together: a configuration this harness treats as ordinary
must be one the schema accepts.

Configurations the harness builds deliberately out of range -- max_cto=1, max_dto=5 in
asam_protocol_layer_test.py, which exist to exercise Xcp_Init's own runtime checks -- are not
covered here, and should not be: they are invalid by design.
"""

import json
import os

import jsonschema
import pytest

from .parameter import *

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'config',
                           'xcp.schema.json')


@pytest.fixture(scope='module')
def schema():
    with open(SCHEMA_PATH) as fp:
        return json.load(fp)


def validate(configuration, schema):
    # json round-trip first: the harness passes plain dicts, but the schema is what a JSON file on
    # disk is checked against, so anything that does not survive serialisation is a finding too.
    jsonschema.validate(json.loads(json.dumps(configuration)), schema)


def test_the_default_configuration_is_valid(schema):
    validate(DefaultConfig(), schema)


def test_a_daq_list_built_by_the_daq_helper_is_valid(schema):
    """The daq() helper omits "pid" -- FIRST_PID is derived, so a caller with no opinion on the
    numbering should not have to invent one. The schema used to require it."""
    validate(DefaultConfig(daqs=(daq(),)), schema)


def test_an_event_built_by_the_event_helper_is_valid(schema):
    validate(DefaultConfig(daqs=(daq(),), events=(event(),)), schema)


def test_a_segment_built_by_the_segment_helper_is_valid(schema):
    validate(DefaultConfig(segments=(segment(pages=(page(), page())),)), schema)


@pytest.mark.parametrize('address_granularity', address_granularities)
def test_every_address_granularity_is_valid(schema, address_granularity):
    validate(DefaultConfig(address_granularity=address_granularity), schema)


@pytest.mark.parametrize('identification_field_type', identification_field_types)
def test_every_identification_field_type_is_valid(schema, identification_field_type):
    validate(DefaultConfig(identification=identification_field_type), schema)


def test_the_repository_configuration_is_valid(schema):
    """config/xcp.json is what generated/CMakeLists.txt actually validates; a failure here is a
    broken integrator build, not just a harness inconsistency."""
    with open(os.path.join(os.path.dirname(SCHEMA_PATH), 'xcp.json')) as fp:
        validate(json.load(fp), schema)


def test_a_dto_without_a_pid_is_accepted(schema):
    """Pins the rule the other tests depend on, so a future tightening of the schema fails here with
    a reason rather than in a dozen unrelated places."""
    validate(DefaultConfig(daqs=(daq(dtos=[{}]),)), schema)


def test_a_dto_pid_above_the_odt_ceiling_is_still_rejected(schema):
    """Dropping "pid" from the required list must not have made the field unchecked when present."""
    with pytest.raises(jsonschema.ValidationError):
        validate(DefaultConfig(daqs=(daq(dtos=[{'pid': 252}]),)), schema)


def test_an_event_name_containing_a_quote_is_rejected(schema):
    """script/source_cfg.c.jinja2 interpolates events[].name raw into a generated C string
    literal (static const uint8 ...[] = "{{event.name}}";). A '"' in the name would close that
    literal early -- breaking generation at best, injecting arbitrary text into the generated
    source at worst -- so the schema has to refuse it before generation ever sees it."""
    with pytest.raises(jsonschema.ValidationError):
        validate(DefaultConfig(events=(event(name='EVT"10MS', triggered_daq_list_ref=['DAQ1']),)), schema)

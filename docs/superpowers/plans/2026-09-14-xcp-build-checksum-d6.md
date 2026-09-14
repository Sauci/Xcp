# BUILD_CHECKSUM D6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close roadmap defect D6 — give `BUILD_CHECKSUM` a configured maximum block size, enforce it, and return it in the extended `ERR_OUT_OF_RANGE` payload the specification defines.

**Architecture:** A new required configuration field `protocol_layer.checksum_max_block_size` reaches C as `Xcp_GeneralType.checksumMaxBlockSize`. `Xcp_DTOCmdStdBuildChecksum` gains a bound check beside its existing zero check, and its single remaining `ERR_OUT_OF_RANGE` path answers through `Xcp_FillErrorPacketWithData` with a six-byte payload. The two *configuration* faults (unmappable type, NULL user function) move to `ERR_CMD_UNKNOWN`. A generation-time guard refuses a bound that would overflow a `uint32` when multiplied by the address granularity.

**Tech Stack:** C (GCC 8.3.0, no `-std` flag, so gnu17), Jinja2 2.11.3 templates, Python 3.7 + pytest 7.4.4 + cffi 1.15.0 test harness, CMake, jsonschema.

**Spec:** `docs/superpowers/specs/2026-09-14-xcp-build-checksum-d6-design.md` (decisions DD115–DD120). Read it alongside this plan; every task below argues from it.

## Global Constraints

- **Reference revision is 1.1.** Every specification citation carries a revision prefix, e.g. `1.1/1.6.1.2.9`, never a bare section number.
- **Tests run in Docker only.** Never run `./test.sh` on the host — it fails in a way that looks like a pass. The exact invocation, from the repository root:
  ```bash
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local ./test.sh
  ```
  The `--user` flag is load-bearing: without it the run leaves root-owned files under `build/` that you cannot delete.
- **A run that stops short with a pycparser, PLY, Jinja2 or CFFI error is not a result — re-run it.** The suite fails this way roughly one run in four for reasons unrelated to any change. `test.sh`'s header records what has been ruled out.
- **Never `rm -rf generated/*`** — it holds a tracked `generated/CMakeLists.txt`. Clearing `build/` is safe.
- **`XCP_PYTEST_ARGS` is a CMake cache variable** (`CMakeLists.txt:17`), consumed only as pytest arguments at `CMakeLists.txt:307`. Seeding it scopes **every later run** until cleared. To run one file quickly, from inside the container:
  ```bash
  cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;build_checksum" && cd ..
  ```
  and **always clear it before the next task**:
  ```bash
  cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd ..
  ```
  Each task's final verification must be a full unscoped `./test.sh`.
- **Commit trailer**, on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  ```
- **Branch:** `docs/xcp-build-checksum-d6-design`, already created from `develop`. Everything lands as one PR against `develop`; CI is the authoritative verification.
- **Match local style.** `source/Xcp_Std.c` uses Allman braces at function and `if`/`else` level, *except* inside `Xcp_DTOCmdStdBuildChecksum`'s inner error block (lines 625–643) which is K&R. Preserve whatever is already there; do not reformat neighbouring lines.

---

## File Structure

| File | Responsibility | Change |
|:--|:--|:--|
| `config/xcp.schema.json` | integrator-facing configuration contract | add `checksum_max_block_size` property + `required` entry |
| `config/xcp.json` | the module's own default configuration | add the value |
| `test/parameter.py` | harness configuration builder | add kwarg + dict entry |
| `interface/Xcp_Types.h` | generated-config C types | add `checksumMaxBlockSize` field |
| `script/source_cfg.c.jinja2` | emits `Xcp_Cfg.c` | add initialiser line **at the same index** + overflow guard |
| `source/Xcp_Std.c` | `BUILD_CHECKSUM` handler | bound check, payload helper, two error-code changes |
| `test/build_checksum_test.py` | command behaviour | known-answer vectors, bound tests, rewritten error tests |
| `test/configuration_schema_test.py` | schema contract | required + minimum tests |
| `test/daq_configuration_test.py` | generation refusals | *not touched* — new guard tests go in `build_checksum_test.py` |
| `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` | defect register | four edits |

**The positional-initialiser hazard.** `Xcp_GeneralType` is initialised **positionally** by `script/source_cfg.c.jinja2`. Task 2 adds a field to the struct and a line to the template; if only one lands, neighbouring configuration is silently mis-assigned. A `uint32` written where a function pointer belongs will fail to compile, but nothing catches a swap between two same-typed neighbours. **Both edits belong to the same commit.**

---

### Task 1: Known-answer checksum vectors from 1.1/1.6.1.2.9

Pure test addition, no production change. It runs first deliberately: it validates the nine existing checksum implementations against the standard *before* anything is modified, so any later failure is attributable to this work.

**Files:**
- Test: `test/build_checksum_test.py` (append after the existing `test_build_checksum_user_defined_returns_expected_checksum_on_a_single_block`, which ends near line 222)

**Interfaces:**
- Consumes: `XcpTest`, `DefaultConfig`, `byte_orders`, `mtas`, `element_size_from_address_granularity`, `address_to_array`, `u32_to_array`, `u32_from_array` — all already imported by that file via `from .parameter import *`.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing test**

Append to `test/build_checksum_test.py`:

```python
# XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9 publishes a 32-byte test pattern and the
# result each algorithm must produce over it. 1.0 carries no such table at all -- these values exist
# only in 1.1. The tests above compare the module against the checksum_* helpers at the top of this
# file, which verifies that two implementations agree; it cannot catch a misunderstanding they
# share. These are external reference values, so they can. Design doc DD120.
#
# The 1.1 PDF is a scanned OCR dump and this table is damaged in it ("Ay10", "CHIT", "OxC/76A"), so
# every value below was recomputed from the pattern and the specification's own CRC parameters
# (poly, init, refin, refout, xorout) and kept only where the recomputation and the reading agreed.
# All nine agreed, on both byte orders.
SPEC_TEST_PATTERN = tuple(range(0x01, 0x11)) + tuple(range(0xF1, 0x100)) + (0x00,)

# The result is always a DWORD regardless of algorithm (1.1/1.6.1.2.9), so the narrower sums are
# written here zero-extended to 32 bits -- that is what Xcp_BuildChecksum*'s `*pResult = (uint32)crc`
# produces and what the response carries in bytes 4..7.
SPEC_VECTORS = (
    # address_granularity, checksum_type,     wire type, LITTLE_ENDIAN (Intel), BIG_ENDIAN (Motorola)
    pytest.param('BYTE', 'XCP_ADD_11', 0x01, 0x00000010, 0x00000010, id='XCP_ADD_11'),
    pytest.param('BYTE', 'XCP_ADD_12', 0x02, 0x00000F10, 0x00000F10, id='XCP_ADD_12'),
    pytest.param('BYTE', 'XCP_ADD_14', 0x03, 0x00000F10, 0x00000F10, id='XCP_ADD_14'),
    pytest.param('WORD', 'XCP_ADD_22', 0x04, 0x00001800, 0x00000710, id='XCP_ADD_22'),
    pytest.param('WORD', 'XCP_ADD_24', 0x05, 0x00071800, 0x00080710, id='XCP_ADD_24'),
    pytest.param('DWORD', 'XCP_ADD_44', 0x06, 0x140C03F8, 0xFC040B10, id='XCP_ADD_44'),
    pytest.param('BYTE', 'XCP_CRC_16', 0x07, 0x0000C76A, 0x0000C76A, id='XCP_CRC_16'),
    pytest.param('BYTE', 'XCP_CRC_16_CITT', 0x08, 0x00009D50, 0x00009D50, id='XCP_CRC_16_CITT'),
    pytest.param('BYTE', 'XCP_CRC_32', 0x09, 0x89CD97CE, 0x89CD97CE, id='XCP_CRC_32'),
)


@pytest.mark.parametrize('ag, checksum_type, checksum_type_int, expected_little, expected_big',
                         SPEC_VECTORS)
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_matches_the_specification_reference_vectors(ag,
                                                                    checksum_type,
                                                                    checksum_type_int,
                                                                    expected_little,
                                                                    expected_big,
                                                                    byte_order):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9's own validation tables.

    The pattern is a BYTE STREAM, not a list of element values: the mock places those 32 bytes in
    memory verbatim and lets the configured granularity and byte order decide what elements they
    form. That is exactly what makes XCP_ADD_22, XCP_ADD_24 and XCP_ADD_44 differ between the
    Intel and Motorola columns, and why the other six do not.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   byte_order=byte_order,
                                   checksum_type=checksum_type))

    mta = 0xDEADBEEF
    element_size = element_size_from_address_granularity(ag)
    block_size = len(SPEC_TEST_PATTERN) // element_size
    expected = expected_little if byte_order == 'LITTLE_ENDIAN' else expected_big

    def read_slave_memory(p_address, _extension, p_buffer):
        offset = int(handle.ffi.cast('uint32_t', p_address)) - mta
        for i in range(element_size):
            p_buffer[i] = SPEC_TEST_PATTERN[offset + i]
        return None

    handle.xcp_read_slave_memory_u8.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u16.side_effect = read_slave_memory
    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # SET_MTA
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    raw_data = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8])

    assert raw_data[0] == 0xFF
    assert raw_data[1] == checksum_type_int
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == expected
```

- [ ] **Step 2: Run it and see what happens**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;reference_vectors" && cd .. && ./test.sh'
```

Expected: **PASS**, 18 tests (9 algorithms × 2 byte orders).

This is the one task in the plan whose test is expected to pass immediately — it is a characterisation test over code that already exists, and its value is the evidence it produces. **If any vector fails, stop and report it before writing another line**: that means a shipped checksum algorithm disagrees with the specification, which is a defect larger than D6 and needs its own decision.

- [ ] **Step 3: Clear the scoped cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS=""'
```

- [ ] **Step 4: Commit**

```bash
git add test/build_checksum_test.py
git commit -m "$(cat <<'EOF'
test: check the checksum algorithms against 1.1's own reference vectors

XCP part 2 1.1/1.6.1.2.9 publishes a 32-byte pattern and the result each
algorithm must produce over it; 1.0 has no such table. The existing tests
compare the module against checksum_* helpers in the same file, so they
verify that two implementations agree and cannot catch a misunderstanding
they share.

The 1.1 PDF is a scanned OCR dump and the table is damaged in it, so every
value was recomputed from the pattern and the specification's own CRC
parameters and kept only where recomputation and reading agreed. All nine
agreed, on both byte orders.

ADD_22, ADD_24 and ADD_44 differ between the Intel and Motorola columns, so
these also test byte order against the standard rather than against the
harness's own assumption.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add `checksum_max_block_size` to the configuration surface

The field exists end-to-end and reaches C. Nothing reads it yet — Task 3 does.

**Files:**
- Modify: `test/parameter.py:391` (kwarg) and `test/parameter.py:419` (dict entry)
- Modify: `config/xcp.schema.json:590` (property, after `user_defined_checksum_function`'s block) and `config/xcp.schema.json:668` (`required` array)
- Modify: `config/xcp.json:305`
- Modify: `interface/Xcp_Types.h:629`
- Modify: `script/source_cfg.c.jinja2:1264`
- Test: `test/configuration_schema_test.py`

**Interfaces:**
- Produces, for Task 3: `Xcp_Ptr->general->checksumMaxBlockSize`, type `const uint32`, in AG units.
- Produces, for Tasks 3–5: `DefaultConfig(checksum_max_block_size=<int>)` keyword, default `65536`.
- Note: `protocol_layer` does **not** declare `additionalProperties: false`, so adding the key to `parameter.py` before the schema knows about it validates cleanly. That is why Step 1 adds it to `parameter.py` first — it makes the `required` test a genuine red.

- [ ] **Step 1: Add the field to the harness only**

In `test/parameter.py`, after the kwarg `user_defined_checksum_function='Xcp_UserDefinedChecksumFunction',`:

```python
                 checksum_max_block_size=65536,
```

and in the `protocol_layer` dict, after `"user_defined_checksum_function": user_defined_checksum_function,`:

```python
            "checksum_max_block_size": checksum_max_block_size,
```

- [ ] **Step 2: Write the failing tests**

Append to `test/configuration_schema_test.py`:

```python
def test_a_configuration_without_checksum_max_block_size_is_rejected(schema):
    """BUILD_CHECKSUM's bound is required, not defaulted (design doc DD116,
    docs/superpowers/specs/2026-09-14-xcp-build-checksum-d6-design.md): a default would leave both
    the 1.1/1.1.3.3 conformance gap and the unbounded element_size * block_size multiplication in
    source/Xcp_Std.c reachable in every build that did not opt in."""
    configuration = DefaultConfig()
    del configuration['configurations'][0]['protocol_layer']['checksum_max_block_size']
    with pytest.raises(jsonschema.ValidationError):
        validate(configuration, schema)


def test_a_checksum_max_block_size_of_zero_is_rejected(schema):
    """0 is not a block size -- the same reasoning programming.max_block_size's own minimum
    records. A maximum of 0 would also reject every request, since block_size == 0 already fails."""
    with pytest.raises(jsonschema.ValidationError):
        validate(DefaultConfig(checksum_max_block_size=0), schema)


def test_the_default_checksum_max_block_size_is_valid(schema):
    """The companion to both rejections above: the value the harness and config/xcp.json actually
    carry must be one the schema accepts, or the two rejections prove nothing."""
    validate(DefaultConfig(), schema)
```

- [ ] **Step 3: Run them and verify both rejections fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;checksum_max_block_size" && cd .. && ./test.sh'
```

Expected: `test_a_configuration_without_checksum_max_block_size_is_rejected` **FAILS** with `DID NOT RAISE jsonschema.exceptions.ValidationError`, and `test_a_checksum_max_block_size_of_zero_is_rejected` **FAILS** the same way. `test_the_default_checksum_max_block_size_is_valid` passes.

- [ ] **Step 4: Add the schema property and required entry**

In `config/xcp.schema.json`, after the `"user_defined_checksum_function"` block's closing `},` and before `"user_cmd_function": {`:

```json
              "checksum_max_block_size": {
                "description": "Maximum Block size BUILD_CHECKSUM accepts, in address granularity units, matching the Block size [AG] its request carries (XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9). It is also the DWORD the negative response returns in bytes 4..7: 1.1/1.1.3.3 requires that every ERR_OUT_OF_RANGE from this command carry the maximum allowed block size. Required rather than defaulted (design doc DD116, docs/superpowers/specs/2026-09-14-xcp-build-checksum-d6-design.md), so that every build carries a real bound rather than only those that opt in. Minimum 1, not 0, for the reason programming.max_block_size's own minimum records: 0 is not a block size, and a maximum of 0 would reject every request because block_size == 0 already fails. script/source_cfg.c.jinja2 additionally refuses a value whose product with address_granularity would exceed a uint32, which this schema cannot express because it is a constraint between two fields (DD119).",
                "type": "integer",
                "minimum": 1,
                "maximum": 4294967295
              },
```

and in the `protocol_layer` `required` array, after `"user_defined_checksum_function",`:

```json
              "checksum_max_block_size",
```

- [ ] **Step 5: Run the schema tests again**

Same command as Step 3. Expected: **PASS**, all three.

- [ ] **Step 6: Add the value to the module's own configuration**

In `config/xcp.json`, after `"user_defined_checksum_function": null,`:

```json
        "checksum_max_block_size": 65536,
```

- [ ] **Step 7: Add the C field and its initialiser — together**

In `interface/Xcp_Types.h`, immediately after the `userDefinedChecksumFunction` member:

```c
    const uint32 checksumMaxBlockSize; /* not part of the specification... */
```

In `script/source_cfg.c.jinja2`, immediately after the `userDefinedChecksumFunction` initialiser line:

```jinja
    {{'0x%08Xu' % configuration.protocol_layer.checksum_max_block_size}}, /* checksumMaxBlockSize */
```

**Both edits, or neither.** The initialiser is positional; a field added to only one of these two files mis-assigns `userCmdFunction` and everything after it.

- [ ] **Step 8: Full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`. A compile error naming `userCmdFunction` or `trailingValue` means Step 7 landed in only one file.

- [ ] **Step 9: Commit**

```bash
git add test/parameter.py test/configuration_schema_test.py config/xcp.schema.json config/xcp.json interface/Xcp_Types.h script/source_cfg.c.jinja2
git commit -m "$(cat <<'EOF'
feat: configure BUILD_CHECKSUM's maximum block size

Adds a required protocol_layer.checksum_max_block_size, in address
granularity units, and carries it through to Xcp_GeneralType as
checksumMaxBlockSize. Nothing reads it yet.

Required rather than defaulted (DD116): a default would leave both the
1.1/1.1.3.3 conformance gap and the unbounded element_size * block_size
multiplication reachable in every build that did not opt in.

The struct field and the generator's initialiser line are in one commit
deliberately -- Xcp_GeneralType is initialised positionally, so a field
added to only one of them silently mis-assigns its neighbours.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Enforce the bound and return the extended payload

**Files:**
- Modify: `source/Xcp_Std.c` — forward declaration near the existing `Xcp_BuildChecksum*` statics (lines 19–83), a new static helper, and the gate at line 539 / the outer `else` at lines 645–648
- Test: `test/build_checksum_test.py`

**Interfaces:**
- Consumes: `Xcp_Ptr->general->checksumMaxBlockSize` (`const uint32`, Task 2); `Xcp_FillErrorPacketWithData(const uint8 errorCode, const uint8 *pData, const uint8 dataLength, PduInfoType *pPduInfo)` (`source/Xcp.c:2685`), which writes `pData` flat from byte 2 and finalises at `2 + dataLength`; `Xcp_CopyFromU32WithOrder(uint32 value, uint8 *pDestination, Xcp_ByteOrderType order)`.
- Produces, for Task 4: the file-local helper `static void Xcp_BuildChecksumFillMaxBlockSize(void);`.

- [ ] **Step 1: Write the failing tests**

Append to `test/build_checksum_test.py`:

```python
def _connect_and_set_mta(handle, mta, byte_order):
    """CONNECT then SET_MTA, the preamble every BUILD_CHECKSUM test needs."""
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF6,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *address_to_array(mta, 4, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


@pytest.mark.parametrize('block_size', [pytest.param(0, id='block_size = 0'),
                                        pytest.param(1001, id='block_size = max + 1')])
@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_out_of_range_carries_the_maximum_block_size(block_size, byte_order):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9's negative response: byte 0 0xFE,
    byte 1 the error code, bytes 2,3 a reserved WORD, bytes 4..7 the maximum block size as a DWORD.
    1.1/1.1.3.3 conditions that payload on the pair (BUILD_CHECKSUM, 0x22) and names no trigger, so
    both out-of-range conditions carry it, not only the one 1.6.1.2.9's prose names (DD117).

    SduLength is asserted because this suite's pervasive SduDataPtr[0:2] idiom cannot see a payload
    at all: without it this test would pass whether or not the DWORD is ever written.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   checksum_max_block_size=1000))

    _connect_and_set_mta(handle, 0xDEADBEEF, byte_order)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(block_size, byte_order))))
    handle.lib.Xcp_MainFunction()

    response = handle.can_if_transmit.call_args[0][1]
    raw_data = tuple(response.SduDataPtr[0:8])

    assert raw_data[0:2] == (0xFE, 0x22)
    assert response.SduLength == 8
    assert raw_data[2] == 0x00
    assert raw_data[3] == 0x00
    assert u32_from_array(bytearray(raw_data[4:8]), byte_order) == 1000


@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_accepts_a_block_size_equal_to_the_maximum(byte_order):
    """The off-by-one guard: the bound is inclusive, so max itself must still be answered."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   checksum_max_block_size=4))

    handle.xcp_read_slave_memory_u8.side_effect = lambda _a, _e, p_buffer: p_buffer.__setitem__(0, 0x01)

    _connect_and_set_mta(handle, 0xDEADBEEF, byte_order)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(4, byte_order))))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('byte_order', byte_orders)
def test_build_checksum_does_not_advance_the_mta_when_it_refuses(byte_order):
    """1.1/1.6.1.2.9 post-increments the MTA by the block size, and only a successful checksum may
    do so. A rejected request that advanced it would silently desynchronise the master: the next
    command would read from somewhere the master never asked for."""
    mta = 0xDEADBEEF
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   checksum_max_block_size=1000))

    handle.xcp_read_slave_memory_u8.side_effect = lambda _a, _e, p_buffer: p_buffer.__setitem__(0, 0x01)

    _connect_and_set_mta(handle, mta, byte_order)

    # refused: over the bound
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(1001, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.xcp_read_slave_memory_u8.reset_mock()

    # accepted: the first address it reads is where the MTA still is
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3,
                                                                 0x00,
                                                                 0x00,
                                                                 0x00,
                                                                 *u32_to_array(1, byte_order))))
    handle.lib.Xcp_MainFunction()

    first_address = handle.xcp_read_slave_memory_u8.call_args_list[0][0][0]
    assert int(handle.ffi.cast('uint32_t', first_address)) == mta
```

- [ ] **Step 2: Run and verify they fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;maximum_block_size or equal_to_the_maximum or does_not_advance" && cd .. && ./test.sh'
```

Expected: `test_build_checksum_out_of_range_carries_the_maximum_block_size` **FAILS** — `assert 2 == 8` on `SduLength`, because the handler still answers a bare two-byte error. The other two pass already (no bound exists, so `block_size = 4` succeeds and a refused request already leaves the MTA alone); they are regression cover for Step 3, not new red.

- [ ] **Step 3: Implement the bound and the payload**

In `source/Xcp_Std.c`, add beside the other file-local declarations (near lines 19–83):

```c
static void Xcp_BuildChecksumFillMaxBlockSize(void);
```

Add the helper immediately above `Xcp_DTOCmdStdBuildChecksum`:

```c
/* XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9 gives BUILD_CHECKSUM a negative response
 * of its own: bytes 2,3 a reserved WORD, bytes 4..7 the maximum block size as a DWORD. 1.1/1.1.3.3
 * states the same requirement conditioned on the pair (BUILD_CHECKSUM, 0x22) with no trigger named,
 * which is why every ERR_OUT_OF_RANGE this handler answers comes through here (DD117).
 *
 * Xcp_FillErrorPacketWithData (source/Xcp.c) writes pData flat from byte 2 and finalizes at
 * 2 + dataLength, so the two reserved bytes are part of the payload rather than something it
 * writes itself. */
static void Xcp_BuildChecksumFillMaxBlockSize(void)
{
    uint8 data[0x06u];

    data[0x00u] = 0x00u;
    data[0x01u] = 0x00u;

    Xcp_CopyFromU32WithOrder(Xcp_Ptr->general->checksumMaxBlockSize,
                             &data[0x02u],
                             Xcp_Ptr->general->byteOrder);

    Xcp_FillErrorPacketWithData(XCP_E_ASAM_OUT_OF_RANGE,
                                data,
                                0x06u,
                                &Xcp_Internal.cto_response.pdu_info);
}
```

Change the gate at line 539 from:

```c
    if (block_size > 0x00u)
```

to:

```c
    /* Both conditions are request validation and belong together, ahead of any configuration
     * resolution: a misconfigured slave receiving an oversized request answers ERR_OUT_OF_RANGE,
     * not the ERR_CMD_UNKNOWN the configuration faults below answer. The upper bound is also what
     * keeps element_size * block_size below -- element_size is up to 4 and block_size arrives from
     * four wire bytes -- from overflowing; script/source_cfg.c.jinja2 refuses a configured maximum
     * whose product with the address granularity would not fit (DD119). */
    if ((block_size > 0x00u) && (block_size <= Xcp_Ptr->general->checksumMaxBlockSize))
```

and the outer `else` at lines 645–648 from:

```c
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
```

to:

```c
    else
    {
        Xcp_BuildChecksumFillMaxBlockSize();
    }
```

- [ ] **Step 4: Run the tests again**

Same command as Step 2. Expected: **PASS**, all six (2 conditions × 2 byte orders, plus the two singles × 2 byte orders).

- [ ] **Step 5: Full suite, then clear the cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`.

- [ ] **Step 6: Commit**

```bash
git add source/Xcp_Std.c test/build_checksum_test.py
git commit -m "$(cat <<'EOF'
fix: bound BUILD_CHECKSUM's block size and return the maximum on refusal

Closes the half of D6 the roadmap entry describes, and the half it does
not. 1.1/1.6.1.2.9 and 1.1/1.1.3.3 both require ERR_OUT_OF_RANGE from this
command to carry the maximum block size as a DWORD in bytes 4..7; the
handler answered a bare error code. There was also no maximum at all, so
block_size arrived from four wire bytes and was used unchecked in
element_size * block_size with element_size up to 4.

Both out-of-range conditions carry the payload, not only the one
1.6.1.2.9's prose names: 1.1.3.3 conditions it on the command and the error
code and names no trigger (DD117).

The bound sits with the existing zero check, ahead of configuration
resolution, so an oversized request from a misconfigured slave answers
ERR_OUT_OF_RANGE rather than the ERR_CMD_UNKNOWN the configuration faults
answer.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Answer `ERR_CMD_UNKNOWN` for the two configuration faults

**Files:**
- Modify: `source/Xcp_Std.c:639` and `source/Xcp_Std.c:642` (line numbers before Task 3; after it they will have shifted by the helper's length — find them by content)
- Modify: `test/build_checksum_test.py` — the two existing tests at lines 244 and 262

**Interfaces:**
- Consumes: `XCP_E_ASAM_CMD_UNKNOWN` from `interface/Xcp_Errors.h` (value `0x20u`).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Rewrite the two existing tests**

In `test/build_checksum_test.py`, replace `test_build_checksum_returns_err_out_of_range_if_checksum_function_is_null` and `test_build_checksum_returns_err_out_of_range_if_checksum_type_is_out_of_range` with:

```python
def test_build_checksum_returns_err_cmd_unknown_if_checksum_function_is_null():
    """XCP part 2 - Protocol Layer Specification 1.1/1.7.3.1 defines ERR_OUT_OF_RANGE as "command
    syntax valid but command parameter(s) out of range". Here the master's parameters are valid and
    the SLAVE is misconfigured, so 0x22 misattributes the fault and its matrix action, "retry other
    parameter", points the master at a fix that cannot exist.

    ERR_CMD_UNKNOWN is "unknown command or not implemented optional command", action "display
    error" -- terminal rather than futile, already in this command's 1.1/1.7.3.2.1 row so no
    deviation is recorded, and already this module's answer for an unavailable BUILD_CHECKSUM (see
    asam_error_matrix_test.py's TestBuildChecksumErrorHandling::test_returns_err_cmd_unknown, which
    builds with xcp_build_checksum_api_enable=False and asserts exactly this). A configured-but-
    unusable checksum function is that same unavailability, found at run time. DD118.

    SduLength is asserted because 0x20 carries no payload: 1.1/1.1.3.3 attaches additional
    information to 0x22 and 0x31 only.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   checksum_type='XCP_USER_DEFINED',
                                   user_defined_checksum_function=None))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = handle.can_if_transmit.call_args[0][1]

    assert tuple(response.SduDataPtr[0:2]) == (0xFE, 0x20)
    assert response.SduLength == 2


def test_build_checksum_returns_err_cmd_unknown_if_checksum_type_is_out_of_range():
    """The sibling condition: a configured checksum type that maps to no ASAM wire value reaches
    Xcp_DTOCmdStdBuildChecksum's `default:` case and its 0x0A sentinel. Same reasoning as above --
    the master's request is well formed and the slave cannot serve it. DD118.

    checksum_type is passed as an int rather than one of the schema's enum strings, which is how
    this test reaches that default case at all.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, checksum_type=0xFF, user_defined_checksum_function=None))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # BUILD_CHECKSUM
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF3, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = handle.can_if_transmit.call_args[0][1]

    assert tuple(response.SduDataPtr[0:2]) == (0xFE, 0x20)
    assert response.SduLength == 2
```

Leave `test_build_checksum_calls_the_det_with_err_param_pointer_if_checksum_function_is_null` unchanged — DD118 keeps the DET report.

- [ ] **Step 2: Run and verify they fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;err_cmd_unknown_if_checksum" && cd .. && ./test.sh'
```

Expected: both **FAIL** with `assert (254, 34) == (254, 32)` — the handler still answers 0x22.

- [ ] **Step 3: Change the two error codes**

In `source/Xcp_Std.c`, inside `Xcp_DTOCmdStdBuildChecksum`, change the NULL-function branch:

```c
            } else {
                Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, XCP_E_PARAM_POINTER);
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);
            }
        } else {
            Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);
        }
```

Both were `XCP_E_ASAM_OUT_OF_RANGE`. Keep the K&R braces already on those lines.

- [ ] **Step 4: Run the tests again**

Same command as Step 2. Expected: **PASS**, both.

- [ ] **Step 5: Full suite, then clear the cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`. `Xcp_CTOErrorMatrix` needs no change — `ERR_CMD_UNKNOWN` is already in BUILD_CHECKSUM's row at `source/Xcp.c:1018` and `:1028`.

- [ ] **Step 6: Commit**

```bash
git add source/Xcp_Std.c test/build_checksum_test.py
git commit -m "$(cat <<'EOF'
fix: answer ERR_CMD_UNKNOWN for BUILD_CHECKSUM's configuration faults

An unmappable checksum type and a XCP_USER_DEFINED selection with no
function configured both answered ERR_OUT_OF_RANGE. 1.1/1.7.3.1 defines
that code as "command syntax valid but command parameter(s) out of range",
but in both cases the master's parameters are valid and the slave is
misconfigured -- so 0x22 misattributes the fault, and its matrix action
"retry other parameter" names a fix the master cannot perform.

ERR_CMD_UNKNOWN is already in this command's 1.1/1.7.3.2.1 row, so no
deviation is recorded, and it is already the module's answer for an
unavailable BUILD_CHECKSUM: asam_error_matrix_test.py builds with
xcp_build_checksum_api_enable=False and asserts exactly this. A
configured-but-unusable checksum function is the same unavailability found
at run time rather than build time. DD118.

ERR_GENERIC was rejected because every 1.7.3.2 row carrying it prescribes
"restart session" against a fault that never clears, and
ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE because 1.1/1.7.3.1 defines it as
temporary while these faults are permanent.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Refuse an overflowing bound at generation

**Files:**
- Modify: `script/source_cfg.c.jinja2` — insert after the identification `Length mod AG = 0` guard's `{%- endif %}` (near line 785) and before `{%- set ts = configuration.protocol_layer.timestamp %}`
- Test: `test/build_checksum_test.py`

**Interfaces:**
- Consumes: `raise(...)`, the deliberately-undefined Jinja global this template already uses for every guard; `configuration.protocol_layer.checksum_max_block_size` (Task 2).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing test and its companion**

Append to `test/build_checksum_test.py`. Its current imports are `crcmod`, `crcmod.predefined`, `from .parameter import *`, `from .conftest import XcpTest` and `from unittest.mock import ANY` — none of which provides `UndefinedError`, so add it, spelled as `test/daq_configuration_test.py:12` spells it:

```python
from jinja2.exceptions import UndefinedError
```

(`pytest` itself needs no import here: it already arrives through `from .parameter import *`, which is why the existing `@pytest.mark.parametrize` decorators in this file work.)

```python
def test_generation_refuses_a_checksum_max_block_size_that_would_overflow():
    """script/source_cfg.c.jinja2 refuses a bound whose product with the address granularity would
    not fit a uint32. The runtime check in Xcp_DTOCmdStdBuildChecksum guarantees
    block_size <= checksumMaxBlockSize; this guarantees checksumMaxBlockSize * element_size fits,
    and together they make element_size * block_size unable to overflow. DD119.

    A constraint between two configuration fields, which is why it lives here and not in
    config/xcp.schema.json: JSON Schema cannot express it.

    Ungated on xcp_build_checksum_api_enable, following the rule the sector Length mod AG guard's
    own comment states -- a check on whether the CONFIGURATION means anything, not a decision about
    what to emit. Gating it would let a broken configuration ship silently and fail only for
    whoever enabled the command later.
    """
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                              address_granularity='DWORD',
                              checksum_max_block_size=0x40000000))


def test_generation_accepts_the_largest_checksum_max_block_size_that_fits():
    """The companion the rejection above needs to mean anything. `raise` is a deliberately-undefined
    Jinja global, so EVERY guard in that template surfaces the identical "'raise' is undefined" --
    pytest.raises(UndefinedError) alone cannot show which guard fired, or that the configuration was
    not refused for some unrelated reason. 0x3FFFFFFF * 4 is 0xFFFFFFFC, the largest product that
    still fits, and the same configuration generates cleanly."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                          address_granularity='DWORD',
                          checksum_max_block_size=0x3FFFFFFF))
```

- [ ] **Step 2: Run and verify the first fails**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;overflow or largest_checksum_max" && cd .. && ./test.sh'
```

Expected: `test_generation_refuses_a_checksum_max_block_size_that_would_overflow` **FAILS** with `DID NOT RAISE jinja2.exceptions.UndefinedError`; the companion passes.

- [ ] **Step 3: Add the guard**

In `script/source_cfg.c.jinja2`, after the identification guard's `{%- endif %}`:

```jinja
{%- set checksum_ag_size = {'BYTE': 1, 'WORD': 2, 'DWORD': 4}[configuration.protocol_layer.address_granularity] %}
{%- if (configuration.protocol_layer.checksum_max_block_size * checksum_ag_size) > 4294967295 %}
    {#- XCP part 2 1.1/1.6.1.2.9 gives BUILD_CHECKSUM's Block size in address granularity units, and
        Xcp_DTOCmdStdBuildChecksum (source/Xcp_Std.c) turns it into an address with
        element_size * block_size. Its runtime check guarantees block_size <= checksumMaxBlockSize;
        this guarantees the product of that maximum and the granularity fits a uint32, so the
        multiplication cannot overflow for any request the handler accepts. A constraint between two
        configuration fields, which config/xcp.schema.json cannot express -- hence here. DD119.

        Deliberately NOT gated on apis.xcp_build_checksum_api_enable, the same asymmetry the sector
        "Length mod AG = 0" guard above records: this asks whether the CONFIGURATION means anything,
        not what to emit. A bound that cannot be honoured is meaningless whether or not this build
        currently serves the command, and gating it would let it ship silently and fail for whoever
        enables the command later. A raise is not generated output, so no byte-for-byte invariance
        property is disturbed by it. #}
{{ raise('checksum_max_block_size {} is in {} address granularity units, and {} * {} exceeds the uint32 that source/Xcp_Std.c computes element_size * block_size in; the largest value that fits this granularity is {} (XCP part 2 1.1/1.6.1.2.9; DD119 in docs/superpowers/specs/2026-09-14-xcp-build-checksum-d6-design.md)'.format(configuration.protocol_layer.checksum_max_block_size, configuration.protocol_layer.address_granularity, configuration.protocol_layer.checksum_max_block_size, checksum_ag_size, 4294967295 // checksum_ag_size)) }}
{%- endif %}
```

- [ ] **Step 4: Run the tests again**

Same command as Step 2. Expected: **PASS**, both.

- [ ] **Step 5: Full suite, then clear the cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`.

- [ ] **Step 6: Commit**

```bash
git add script/source_cfg.c.jinja2 test/build_checksum_test.py
git commit -m "$(cat <<'EOF'
feat: refuse a checksum_max_block_size that would overflow at generation

The runtime bound guarantees block_size <= checksumMaxBlockSize; this
guarantees checksumMaxBlockSize * element_size fits a uint32. Together they
make element_size * block_size in Xcp_DTOCmdStdBuildChecksum unable to
overflow for any request the handler accepts.

A constraint between two configuration fields, which config/xcp.schema.json
cannot express, so it is a generation-time raise like the identification and
sector guards beside it.

Ungated on xcp_build_checksum_api_enable, following the rule the sector
Length mod AG guard records: this asks whether the configuration means
anything rather than what to emit, and gating it would let a broken bound
ship silently and fail only for whoever enabled the command later. DD119.

The rejection ships with a companion test that generates the same
configuration at a legal value, because `raise` is a deliberately-undefined
Jinja global -- every guard in that template surfaces the identical
"'raise' is undefined", so the rejection alone is not discriminating.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Roadmap edits

Documentation only, no test cycle. Four edits, all in `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`.

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` lines 209, 211–215, 224–225, 283–296, and the end of §3 (before the `---` preceding `## 4. Decomposition` at line 362)

**Interfaces:** none.

- [ ] **Step 1: Close the D6 entry**

Replace the `> **Open.** Belongs with the per-segment checksum reconciliation described at the end of §2.6.` blockquote under D6 with:

```markdown
> **Fixed.** `protocol_layer.checksum_max_block_size` is a required configuration field,
> `Xcp_DTOCmdStdBuildChecksum` enforces it, and every `ERR_OUT_OF_RANGE` it answers carries the
> maximum as the DWORD 1.1/1.6.1.2.9 and 1.1/1.1.3.3 require. Design:
> `2026-09-14-xcp-build-checksum-d6-design.md` (DD115–DD120).
>
> The entry understated the defect: there was no maximum block size anywhere, in configuration or
> as a check, so `block_size` arrived from four wire bytes and was used unchecked in
> `element_size * block_size`. Two paths that answered `ERR_OUT_OF_RANGE` for *configuration*
> faults now answer `ERR_CMD_UNKNOWN` (DD118).
>
> Closed **without** the per-segment reconciliation this section previously bound it to — see
> DD115. The two are separable: the payload and the missing bound are a conformance defect in one
> handler, reachable today; the AML reconciliation is a change to the configuration model needing
> its own design.
```

Also correct the stale citation in the parenthetical immediately below it — `source/Xcp.c:2639` is now inside `Xcp_TransmitOneFrame`'s CanIf re-entrancy handling; the checksum-type mapping lives in `source/Xcp_Std.c`:

```markdown
(The checksum *type* mapping is correct: `Xcp_ChecksumType` is a zero-based internal enum,
but `Xcp_DTOCmdStdBuildChecksum` translates it explicitly to the ASAM wire values 0x01..0x09
and 0xFF at `source/Xcp_Std.c` before transmitting.)
```

- [ ] **Step 2: Update §2.6's "Extended error payloads" row**

Replace the row's status cell — currently beginning `**partial.**` — with:

```markdown
| Extended error payloads | §1.1.3.3 | **done.** `Xcp_FillErrorPacketWithData` (`source/Xcp.c`) is the mechanism: `DOWNLOAD_NEXT` and `PROGRAM_NEXT` attach the expected element count to their `ERR_SEQUENCE` response (`source/Xcp_Cal.c`, `source/Xcp_Pgm.c`), and `BUILD_CHECKSUM` attaches the maximum block size to its `ERR_OUT_OF_RANGE` (`source/Xcp_Std.c`, D6). One gap remains and is tracked as D17: `ERR_GENERIC`'s own implementation-specific WORD is never attached at any of its five call sites. This row previously read a blanket "absent", which overstated the gap, then "partial" while D6 was open |
```

- [ ] **Step 3: Rewrite the per-segment observation so it stands alone**

Replace the paragraph at lines 211–215 (`One structural observation for later work: …it belongs with D6.`) with:

```markdown
**Open: per-segment checksum configuration.** The AML in §2.1 declares checksum configuration
**per segment** — a `CHECKSUM` block carrying type, `MAX_BLOCK_SIZE` and `EXTERNAL_FUNCTION`
inside each `Segment`. `config/xcp.json` declares all three once globally under `protocol_layer`,
and D6 deliberately kept it that way (DD115). Reconciling them needs a resolution from the MTA —
an arbitrary address — to a segment, which this module has never had: segments are reached only
by an index the master supplies, and `Xcp_SegmentType`'s `address`/`length` are read today only to
report `GET_SEGMENT_INFO`. It also needs an answer to "the MTA is in no configured segment", which
neither 1.0 nor 1.1 defines. That is a change to the configuration model and wants its own design.
```

and in §3's status paragraph, replace `D6 remains open and travels with the per-segment checksum reconciliation noted at the end of §2.6.` with:

```markdown
D6 is fixed (2026-09-14) without the per-segment checksum reconciliation it was once bound to;
that reconciliation is now tracked on its own at the end of §2.6.
```

- [ ] **Step 4: Add the D17 entry**

At the end of §3 — after D7's `> **Fixed.**` blockquote and before the `---` that precedes `## 4. Decomposition` — add:

```markdown
**D17 — `ERR_GENERIC` never carries its extended payload.** 1.1/§1.1.3.3 defines two
payload-bearing error codes. `BUILD_CHECKSUM`'s `ERR_OUT_OF_RANGE` DWORD is the one D6 closed; the
other is `ERR_GENERIC` (0x31), which "contains an implementation specific slave device error code
as WORD as additional information". All five sites that answer it — one in `source/Xcp_Std.c`
(`UNLOCK`, DD76) and four in `source/Xcp_Pgm.c` — call plain `Xcp_FillErrorPacket`, so no WORD is
ever attached. The `UNLOCK` branch's own comment cites §1.1.3.3's wording as its justification for
*choosing* that code, then omits the payload that same sentence describes.

Not folded into D6: it touches `UNLOCK` and the PGM group rather than the checksum command, and
deciding what the WORD should contain is a design question of its own — the specification leaves
the value implementation-specific, so this module would be defining a private error vocabulary.

> **Open.** Found while designing D6 (`2026-09-14-xcp-build-checksum-d6-design.md` §6).
```

- [ ] **Step 5: Verify the document still renders and nothing else moved**

```bash
git diff --stat docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
grep -n 'D6 remains open\|partial\.\*\* `Xcp_FillErrorPacketWithData`\|belongs with D6' docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
```

Expected: the `grep` prints **nothing** — all three superseded phrasings are gone.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
git commit -m "$(cat <<'EOF'
docs: close D6 in the roadmap, and record D17

Four edits. D6 is marked fixed with the decisions that closed it, and its
stale source/Xcp.c:2639 citation is corrected -- that line is now inside
Xcp_TransmitOneFrame's CanIf re-entrancy handling, and the checksum-type
mapping lives in source/Xcp_Std.c.

2.6's extended-error-payloads row moves from partial to done, and its
closing per-segment observation is rewritten to stand on its own rather
than hang off a defect that is now closed -- as does the sentence in 3
binding D6 to it. D6 was deliberately closed without that reconciliation
(DD115) and the roadmap should say so where a reader will meet it.

D17 records the remaining extended-payload gap: ERR_GENERIC's own
implementation-specific WORD is never attached at any of its five call
sites, while the UNLOCK branch cites the very sentence defining it as its
reason for choosing the code.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Push and open the PR**

```bash
git push -u origin docs/xcp-build-checksum-d6-design
gh pr create --base develop --head docs/xcp-build-checksum-d6-design --title "fix: close D6 -- BUILD_CHECKSUM's maximum block size and extended error payload"
```

- [ ] **Wait for CI and read its verdict**

```bash
gh pr checks <N>
```

CI runs the full suite on the same Alpine image and is the authoritative verification. It has been green on 40 of its last 40 runs, so a red run here is a real finding, not the local flake.

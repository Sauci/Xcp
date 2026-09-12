# GET_ID Identification Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `GET_ID` from identification type 0 (ASCII) alone to types 1–4 and the 128–255 user-defined range, served through an integrator callback.

**Architecture:** `Xcp_DTOCmdStdGetId` keeps answering through the MTA (`TRANSFER_MODE = 0`). An optional `getIdentificationFunction` on `Xcp_GeneralType` supplies address, MTA extension and length for any type; the configured static `identification` string remains type 0's fallback. Types the specification does not define (5–127) answer `ERR_OUT_OF_RANGE`; defined types the slave does not serve answer a positive response with `Length = 0`.

**Tech Stack:** C (AUTOSAR BSW module), Jinja2 code generation (`script/source_cfg.c.jinja2`), CFFI + pytest harness, CMake/ctest, Docker.

**Spec:** `docs/superpowers/specs/2026-09-11-xcp-get-id-types-design.md` (DD108–DD114)

## Global Constraints

- **Reference revision is 1.1.** Every specification citation carries its revision prefix: `1.1/§1.6.1.2.2`, never a bare section number. Cite 1.0 only where it differs or is the readable copy.
- **`GET_ID` is §1.6.1.2.2 in both revisions.** The error matrix is §1.7.3.2.1 in both.
- **`TRANSFER_MODE` is bit 0, `COMPRESSED_ENCRYPTED` is bit 1** of the response Mode byte (1.1/§1.6.1.2.2). Both stay clear — DD111.
- **Run the suite in Docker only.** `./test.sh` on the host dies at `cmake: not found`:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 \
    --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
  ```
  `--user` is load-bearing — a root run leaves root-owned files under `build/` that later runs cannot delete. A full run is ~7 minutes.
- **`XCP_PYTEST_ARGS` is a CMake cache variable.** Seeding it scopes every later run until cleared to `""`.
- **Never `rm -rf generated/*`** — it holds a tracked `generated/CMakeLists.txt`. Clearing `build/` is safe.
- **`Xcp_GeneralType` is initialised positionally** by `script/source_cfg.c.jinja2`. New fields go strictly at the **tail** of both the struct and the initialiser, or every later field silently shifts.
- **`Xcp_Internal` and file-`static` tables are unreachable** from the CFFI harness — `test/conftest.py` builds its cdef from `interface/Xcp.h` alone. Assert on transmitted bytes, callback arguments, DET calls, or exported return values.
- **`Xcp_DaqQueuePeek` hands every transmission the same static `PduInfoType`.** Read each frame immediately after its own `CanIf_Transmit` call, never from `call_args_list` afterwards.
- **`raise()` is not a registered Jinja global.** `{{ raise('...') }}` aborts rendering with `jinja2.exceptions.UndefinedError`; the message is documentation, never output. Guard tests assert `pytest.raises(UndefinedError)`, never a message match.
- **Mutation-verify every behavioural claim:** change the code so the test *should* fail, confirm it does, and name the test. A passing suite is not evidence that a test pins anything.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Branch:** `feature/xcp-get-id-types`, already created, design doc already committed. Push as work progresses.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `source/Xcp_Internal.h` | `XCP_GET_ID_MODE_*` masks, `XCP_GET_ID_TYPE_*` bounds | 1, 2 |
| `source/Xcp_Std.c` | `Xcp_DTOCmdStdGetId` — the whole command | 1, 2, 4, 5 |
| `interface/Xcp.h` | `XCP_E_IDENTIFICATION_NOT_GRANULAR` DET code | 5 |
| `interface/Xcp_Types.h` | `getIdentificationFunction` at the tail of `Xcp_GeneralType` | 4 |
| `config/xcp.schema.json` | `get_id_function` property; `identification` default | 3, 4 |
| `config/xcp.json` | shipped default configuration | 3, 4 |
| `script/source_cfg.c.jinja2` | AG guard; initialiser entry at the tail | 3, 4 |
| `test/parameter.py` | `DefaultConfig` defaults for both new knobs | 3, 4 |
| `test/conftest.py` | `Xcp_GetIdentificationFunction` extern registration | 4 |
| `test/get_id_test.py` | Mode byte, `Length = 0`, callback behaviour | 1, 2, 4, 5 |
| `test/asam_error_matrix_test.py` | narrowed `ERR_OUT_OF_RANGE` range | 2 |
| `test/daq_configuration_test.py` | generator guard test | 3 |
| `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` | conformance rows | 6 |

---

### Task 1: Name the Mode bits and repair the assertion that pinned an echo, not a bit mask

**Correction, made after Task 1's implementer disproved it empirically**
(commit `afa5c8e`): this title originally read
"repair the assertion that cannot fail." The old assertion could fail — with this test's `mode`
pinned at 0, mutating the response byte away from 0 broke the old assertion exactly as it broke the
new one, for the unrelated reason that the two sides then read different numbers. Its real weakness
was that it could not tell a correct bit-mask implementation from an incorrect echo of the request
at mode 0, not that it was immune to a wrong byte on the wire. Retitled here rather than left
standing; see the two corrections below for how the same overstatement reached this task's own step
text and commit message.

Lands first and changes no behaviour. The existing test asserts `raw_data[1] == mode`, comparing the response's Mode bit mask against the request's Requested Identification Type — two different fields coinciding at zero against a hardcoded `0x00`. Until that is fixed, nothing later in this plan is pinned by it.

**Files:**
- Modify: `source/Xcp_Internal.h` (near `XCP_PID_CMD_GET_ID`, line 107)
- Modify: `source/Xcp_Std.c:1264-1335` (`Xcp_DTOCmdStdGetId`)
- Test: `test/get_id_test.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `XCP_GET_ID_MODE_TRANSFER_MODE`, `XCP_GET_ID_MODE_COMPRESSED_ENCRYPTED` — `uint8` masks used by Tasks 2, 4, 5.

- [ ] **Step 1: Write the failing test**

Replace the two assertions on `raw_data[1]` in `test_get_id_returns_identification_through_mta_when_mode_is_0` in `test/get_id_test.py`. Delete `# check Mode.` and `assert raw_data[1] == mode`, and put this in their place:

```python
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
```

- [ ] **Step 2: Run it and confirm it passes against unchanged code, then mutation-verify**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```

The new assertions pass against today's hardcoded `0x00`. That is expected — this step is not what proves them. **Mutation-verify now:** change `source/Xcp_Std.c` line 1323 from `SduDataPtr[0x01u] = 0x00u;` to `= 0x01u;` and re-run only this test. It must fail on the `TRANSFER_MODE` assertion. Then set `= 0x02u` and confirm it fails on `COMPRESSED_ENCRYPTED`. Revert both.

**Correction, made after Task 1's implementer disproved it empirically** (commit `afa5c8e`): this step originally ended "Record in the commit message that the old assertion survived both mutations and the new one does not." It does not survive either mutation — this test's `mode` is pinned at 0, so a mutated response byte breaks `raw_data[1] == mode` too, for the same coincidental reason it used to pass. Commit `1a6144c` carries that since-disproven wording verbatim, because it was written before the mutation-verify step above was actually run against it; the fix landed in a follow-up commit rather than rewriting the pushed one. See the design doc's DD-adjacent correction in `2026-09-11-xcp-get-id-types-design.md` §1 for the accurate characterisation.

- [ ] **Step 3: Add the named masks**

In `source/Xcp_Internal.h`, immediately after `#define XCP_PID_CMD_GET_ID (0xFAu)`:

```c
/**
 * @brief GET_ID positive response Mode bit mask.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2. 1.0/1.6.1.2.2 carries the same
 * byte but leaves it an unnamed "Mode"; 1.1 makes it a bit mask and adds COMPRESSED_ENCRYPTED.
 * @details Bit positions are asserted from the 1.1 PDF's own text layer, not from its OCR sidecar,
 * which misaligns table columns. The glyph substitution was recovered from known-plaintext pairs
 * and the prose decode agrees independently with the table's column geometry; the method is
 * recorded in docs/superpowers/specs/2026-09-11-xcp-get-id-types-design.md section 0.
 *
 * Both bits are always clear in this module (DD111). TRANSFER_MODE stays 0 because the request
 * packet is two bytes -- command code and Requested Identification Type -- so the master has no
 * field in which to ask for inline transfer; the slave chooses and merely reports which mode it
 * used, and 1.1/1.6.1.2.2 describes mode 0 as a complete answer. COMPRESSED_ENCRYPTED stays 0
 * because its algorithm interface lives in XCP Part 4, which is not in docs/external/ -- and
 * because the cleared state is always legal.
 */
#define XCP_GET_ID_MODE_TRANSFER_MODE (0x01u << 0x00u)
#define XCP_GET_ID_MODE_COMPRESSED_ENCRYPTED (0x01u << 0x01u)
```

- [ ] **Step 4: Cite them at the build site**

In `source/Xcp_Std.c`, replace the bare `Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u;` with:

```c
        /* Mode (1.1/1.6.1.2.2): TRANSFER_MODE and COMPRESSED_ENCRYPTED both clear. See DD111 and
         * the masks' own note in source/Xcp_Internal.h for why neither is ever set here. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u;
```

Do not write the value as an expression over the two masks. `0x00u` is what goes on the wire and the comment is what explains it; an expression contrived to evaluate to zero while mentioning both names is harder to read than either. The masks earn their place by being referenced from the tests and from the header's own documentation, not by appearing here.

**Correction, made in the final review's fix wave**
(commit `efafeaf`): the last sentence above
describes something impossible. The tests cannot reference the masks at all: they live in
`source/Xcp_Internal.h`, and the harness builds its cdef, and every `handle.define(...)` lookup,
from `interface/Xcp.h` and the generated configuration headers, none of which includes
`source/Xcp_Internal.h` — `interface/Xcp.h`'s own note on internal declarations says the same of
functions declared only there. As shipped, the masks were referenced nowhere: not from the tests,
and not at the build site either, whose comment named the two bits only in prose. That comment now
names both macro identifiers. In code the masks remain unreferenced, a deliberate MISRA C:2012
Rule 2.5 (advisory) deviation recorded in the design doc's DD111 correction.

- [ ] **Step 5: Run the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: 12962 passed, 29 skipped (baseline), both ctest targets green.

- [ ] **Step 6: Commit and push**

```bash
git add source/Xcp_Internal.h source/Xcp_Std.c test/get_id_test.py
git commit -m "test: pin GET_ID's response Mode byte as the bit mask 1.1 defines

test_get_id_returns_identification_through_mta_when_mode_is_0 asserted
raw_data[1] == mode, comparing the response's Mode bit mask against the
request's Requested Identification Type. Two different fields that both
happen to be 0, checked against a hardcoded 0x00 -- the assertion passed
under every possible implementation.

Mutation-verified: with SduDataPtr[0x01u] set to 0x01 or 0x02 the old
assertion still passed and the new one fails on TRANSFER_MODE and
COMPRESSED_ENCRYPTED respectively.

No behaviour change; the byte is still 0x00.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

**Correction, made after Task 1's implementer disproved it empirically**
(commit `afa5c8e`): the commit message above, as
actually committed at `1a6144c`, claims twice that the old assertion "passed under every possible
implementation" and "still passed" under both mutations. Neither holds — with this test's `mode`
pinned at 0, mutating the response byte away from 0 breaks the old assertion exactly as it breaks a
correct one, for the unrelated reason that the two sides then read different numbers. The old
assertion's real weakness is that it cannot tell a correct bit-mask implementation from an incorrect
echo of the request at mode 0, not that it survives a corrupted byte on the wire. `1a6144c` is not
rewritten — this correction landed in a follow-up commit instead, per this repository's convention
(DD102, DD105) of recording a correction rather than silently editing history.

---

### Task 2: Answer `Length = 0` for defined-but-unserved types, `ERR_OUT_OF_RANGE` only for 5–127

Implements DD110 and DD113 without the callback. After this task the module still serves only type 0, but it declines the other defined types the way the specification prescribes instead of erroring.

**Files:**
- Modify: `source/Xcp_Internal.h` (type bounds, after the Mode masks from Task 1)
- Modify: `source/Xcp_Std.c` (`Xcp_DTOCmdStdGetId`)
- Test: `test/get_id_test.py`, `test/asam_error_matrix_test.py:205-215`

**Interfaces:**
- Consumes: `XCP_GET_ID_MODE_*` from Task 1.
- Produces: `XCP_GET_ID_TYPE_ASCII` (0), `XCP_GET_ID_TYPE_LAST_DEFINED` (4), `XCP_GET_ID_TYPE_FIRST_USER_DEFINED` (128) — used by Task 4.

- [ ] **Step 1: Write the failing tests**

Append to `test/get_id_test.py`:

```python
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
    """Issue UPLOAD and return the raw pointers Xcp_ReadSlaveMemory was asked to read.

    Returns cdata pointers, not integers: the harness idiom for "is this pointer null" is a direct
    comparison against handle.ffi.NULL (test/clear_daq_list_test.py:40), which needs no cast to an
    integer type the cdef may not carry.
    """
    addresses = []
    handle.xcp_read_slave_memory_u8.side_effect = \
        lambda p_address, _extension, _p_buffer: addresses.append(p_address)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, element_count)))
    handle.lib.Xcp_MainFunction()
    return addresses


def test_a_length_zero_get_id_does_not_leave_an_earlier_set_mta_standing():
    """DD113. A declined GET_ID must not leave an earlier SET_MTA's pointer in place: a master that
    ignores Length = 0 and uploads anyway would then read through a pointer the slave never set for
    this purpose -- the defect DD75 fixed for the extension half of the same pair, arriving the
    other way round.

    Paired with its own positive control below. "This address was never read" is vacuous alone: such
    a test passes just as happily if UPLOAD read nothing at all, or if SET_MTA never worked. The
    control shows the same SET_MTA address IS reached when no GET_ID intervenes, so the difference
    here is caused by GET_ID and by nothing else. test/session_teardown_test.py uses the same
    pairing for the neighbouring DD75 case.
    """
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    _connect(handle)
    _set_mta(handle, (0xDE, 0xAD, 0xBE, 0xEF))

    _get_id(handle, 0x03)   # a type 1.1/1.6.1.2.2 defines but this slave does not serve

    addresses = _upload_addresses(handle, 0x01)

    assert addresses, 'UPLOAD read no memory at all -- see the note below before changing this'
    assert addresses[0] == handle.ffi.NULL, \
        'a Length = 0 GET_ID left the earlier SET_MTA standing for the following UPLOAD'


def test_an_upload_with_no_intervening_get_id_still_reads_the_set_mta_address():
    """The positive control for the test above: same SET_MTA, same UPLOAD, no GET_ID between them.
    If this ever fails, the absence the test above asserts proves nothing."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    _connect(handle)
    _set_mta(handle, (0xDE, 0xAD, 0xBE, 0xEF))

    addresses = _upload_addresses(handle, 0x01)

    assert addresses, 'setup: UPLOAD must read memory'
    assert addresses[0] != handle.ffi.NULL, \
        'setup: UPLOAD must reach the address SET_MTA just set, or the paired test is vacuous'
```


**If UPLOAD turns out not to call `Xcp_ReadSlaveMemory` at all when the MTA is null**, that also satisfies DD113 — the stale pointer was not used — but it is different behaviour from what these tests assert. Do not weaken the assertion to accept both. Find out which it is, assert the one that is true, say so in your report, and keep the positive control either way.

- [ ] **Step 2: Run and verify they fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: `test_get_id_reports_length_zero_for_a_defined_type_it_does_not_serve` fails — today every non-zero type answers `(0xFE, 0x22)`, so `raw_data[0]` is `0xFE` not `0xFF`. `test_a_length_zero_get_id_does_not_leave_an_earlier_set_mta_standing` fails for the same reason. Two of the new tests **pass already** and are regression guards on behaviour Task 2 must preserve, not drivers: `test_get_id_rejects_a_type_the_specification_does_not_define`, and the positive control `test_an_upload_with_no_intervening_get_id_still_reads_the_set_mta_address`.

- [ ] **Step 3: Add the type bounds**

In `source/Xcp_Internal.h`, after the Mode masks from Task 1:

```c
/**
 * @brief GET_ID Requested Identification Type values.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 (1.0/1.6.1.2.2, identical list):
 * 0 ASCII text, 1 ASAM-MC2 filename without path and extension, 2 with path and extension, 3 URL,
 * 4 ASAM-MC2 file to upload, 128..255 user defined. 5..127 are not identification types.
 */
#define XCP_GET_ID_TYPE_ASCII (0x00u)
#define XCP_GET_ID_TYPE_LAST_DEFINED (0x04u)
#define XCP_GET_ID_TYPE_FIRST_USER_DEFINED (0x80u)
```

- [ ] **Step 4: Restructure the command**

Replace the body of `Xcp_DTOCmdStdGetId` in `source/Xcp_Std.c`. Keep DD75's existing comment block attached to the `extension = 0x00u` assignment on the static path — do not delete it.

```c
uint8 Xcp_DTOCmdStdGetId(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    Std_ReturnType result = E_OK;

    *responseExpected = TRUE;

    const uint8 identification_type = pPduInfo->SduDataPtr[0x01u];

    if ((identification_type > XCP_GET_ID_TYPE_LAST_DEFINED) &&
        (identification_type < XCP_GET_ID_TYPE_FIRST_USER_DEFINED))
    {
        /* 5..127 name no identification type at all: 1.1/1.6.1.2.2 lists 0..4 and 128..255 as the
         * types that "may be requested". This is the only value range that can reach GET_ID's own
         * ERR_OUT_OF_RANGE row in 1.1/1.7.3.2.1, the identification type being its only parameter.
         * A defined type this slave simply does not serve is NOT an error -- it answers Length = 0
         * below, which is what 1.1/1.6.1.2.2 defines that value to mean. DD110. */
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        const void *identification = NULL_PTR;
        uint8 extension = 0x00u;
        uint32 identification_length = 0x00000000u;

        if (identification_type == XCP_GET_ID_TYPE_ASCII)
        {
            identification = (const void *)Xcp_Ptr->general->identification;
            /* <-- DD75's existing comment block moves here verbatim --> */
            extension = 0x00u;

            for (identification_length = 0x00000000u;
                 identification_length < 0xFFFFFFFFu;
                 identification_length++)
            {
                if (Xcp_Ptr->general->identification[identification_length] == 0x00u)
                {
                    break;
                }
            }
        }

        /* DD113: a declined type nulls the MTA rather than leaving an earlier SET_MTA's pointer
         * standing for an UPLOAD that ignores Length = 0. (NULL_PTR, 0) is this module's own
         * vocabulary for "nothing meaningful on this pair" -- Xcp_Init and Xcp_CTOCmdStdConnect
         * both pair exactly that. */
        Xcp_Internal.memory_transfer.address = (void *)identification;
        Xcp_Internal.memory_transfer.extension = extension;

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        /* Mode (1.1/1.6.1.2.2): TRANSFER_MODE and COMPRESSED_ENCRYPTED both clear. DD111. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
        Xcp_CopyFromU32WithOrder(identification_length,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }

    return result;
}
```

- [ ] **Step 5: Narrow the error-matrix test**

In `test/asam_error_matrix_test.py`, change `test_returns_err_out_of_range`'s parametrisation from `range(0x01, 0xFF)` to `range(0x05, 0x80)` and add to the test body's docstring:

```python
    """1.1/1.6.1.2.2 defines identification types 0-4 and 128-255. Only 5-127 are out of range;
    a defined type this slave does not serve answers a positive response with Length = 0 instead
    (test/get_id_test.py::test_get_id_reports_length_zero_for_a_defined_type_it_does_not_serve),
    which is what 1.1/1.6.1.2.2 defines Length = 0 to mean. DD110.

    This previously ranged over range(0x01, 0xFF) -- every type but 0, and stopping short of 255.
    """
```

- [ ] **Step 6: Run the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: all green. Test count changes — `test_returns_err_out_of_range` drops from 254 to 123 parametrisations, and the new tests add 12 + 3 + 1. Record the new total.

- [ ] **Step 7: Mutation-verify**

Three mutations, each reverted after confirming the named test fails:
1. Change `identification_type < XCP_GET_ID_TYPE_FIRST_USER_DEFINED` to `<= 0xFFu` → `test_get_id_reports_length_zero_for_a_defined_type_it_does_not_serve[0x80]` and `[0xFF]` must fail.
2. Change `identification_type > XCP_GET_ID_TYPE_LAST_DEFINED` to `> 0x00u` → `test_get_id_reports_length_zero_for_a_defined_type_it_does_not_serve` must fail for types 1–4.
3. Delete the `Xcp_Internal.memory_transfer.address = ...` assignment → `test_a_length_zero_get_id_does_not_leave_an_earlier_set_mta_standing` must fail.
4. Mutate the positive control's own premise: with the code unmodified, change `_set_mta` in the control test to set address 0 → `test_an_upload_with_no_intervening_get_id_still_reads_the_set_mta_address` must fail. This is what proves the control is load-bearing rather than decorative, and therefore that mutation 3's absence assertion means something. Revert.

- [ ] **Step 8: Commit and push**

```bash
git add source/Xcp_Internal.h source/Xcp_Std.c test/get_id_test.py test/asam_error_matrix_test.py
git commit -m "feat: decline an unserved GET_ID type with Length = 0, not ERR_OUT_OF_RANGE

XCP part 2 1.1/1.6.1.2.2 (1.0 identical): "If length is 0, the requested
identification type is not available." GET_ID has its own in-band way to
decline, so a master can enumerate support without provoking errors. The
module answered ERR_OUT_OF_RANGE for every type but 0, which never let
that mechanism fire.

ERR_OUT_OF_RANGE is not dropped: 1.1/1.7.3.2.1 gives GET_ID its own row
with recovery 'retry other parameter', and the identification type is its
only parameter. It now covers 5-127, which 1.1/1.6.1.2.2 does not define
as identification types at all. DD110.

A declined type also nulls the MTA rather than leaving an earlier SET_MTA
standing for an UPLOAD that ignores Length = 0 (DD113).

The narrowed error-matrix test previously ranged over range(0x01, 0xFF),
which never covered type 255; the new Length = 0 test does.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 3: Enforce `Length mod AG = 0` at generation time

DD112's static half. 1.1/§1.6.1.2.2 adds `Length mod AG = 0`; 1.0 has no equivalent. The shipped default `identification` is 21 bytes and already violates it under `WORD` and `DWORD`, so the guard and the new default land together — the guard would otherwise reject the module's own default configuration.

**Files:**
- Modify: `script/source_cfg.c.jinja2` (near the existing guards at 748-750)
- Modify: `config/xcp.json:308`, `config/xcp.schema.json:624-627`
- Modify: `test/parameter.py:395`
- Test: `test/daq_configuration_test.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DefaultConfig(identification=...)` now defaults to `/path/to/xcp.a2l`.

- [ ] **Step 1: Write the failing test**

Append to `test/daq_configuration_test.py`:

```python
@pytest.mark.parametrize('address_granularity, identification', (
    ('WORD', '/path/to/database.a2l'),    # 21 bytes: 21 mod 2 == 1
    ('DWORD', '/path/to/database.a2l'),   # 21 bytes: 21 mod 4 == 1
    ('DWORD', '/path/to/xcp.a2ll'),       # 17 bytes: 17 mod 4 == 1
))
def test_generation_refuses_an_identification_that_is_not_a_multiple_of_the_granularity(
        address_granularity, identification):
    """XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 adds a rule 1.0/1.6.1.2.2 does not
    have: "The following rule applies: Length mod AG = 0". It protects the UPLOAD that follows,
    whose element count 1.1 defines as (Length GET_ID [BYTE]) / AG -- an inexact division leaves
    the master unable to ask for the right number of elements. DD112.

    The guard message is documentation, not output: raise() is not a registered Jinja global in
    bsw_code_gen, so referencing it aborts rendering with UndefinedError and the string never
    reaches the caller. This asserts that generation fails, never that a message matches.
    """
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(address_granularity=address_granularity,
                              identification=identification))


@pytest.mark.parametrize('address_granularity', ('BYTE', 'WORD', 'DWORD'))
def test_generation_accepts_the_default_identification_under_every_granularity(
        address_granularity):
    """The boundary above from the accepting side, and the reason the shipped default changed from
    /path/to/database.a2l (21 bytes) to /path/to/xcp.a2l (16): without it the guard would reject
    the module's own default configuration under WORD and DWORD."""
    handle = XcpTest(DefaultConfig(address_granularity=address_granularity))

    assert handle.config.lib.Xcp[0].general.addressGranularity == handle.define(
        'XCP_ADDRESS_GRANULARITY_{}'.format(address_granularity))
```

If that last assertion's enum spelling does not match the generated header, assert on
`handle.ffi.string(handle.config.lib.Xcp[0].general.identification) == b'/path/to/xcp.a2l'`
instead — the point of the test is that generation succeeds at all.

- [ ] **Step 2: Run and verify it fails**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: `test_generation_refuses_an_identification_that_is_not_a_multiple_of_the_granularity` fails — no guard exists, so generation succeeds and `pytest.raises` sees nothing.

- [ ] **Step 3: Add the generator guard**

In `script/source_cfg.c.jinja2`, immediately after the `odt_entry_size_daq < 1` guard block (around line 750):

```jinja
{%- set ag_size = {'BYTE': 1, 'WORD': 2, 'DWORD': 4}[configuration.protocol_layer.address_granularity] %}
{%- if (configuration.protocol_layer.identification | length) % ag_size != 0 %}
    {#- XCP part 2 1.1/1.6.1.2.2 adds a rule 1.0/1.6.1.2.2 does not have: "The following rule
        applies: Length mod AG = 0". GET_ID reports the identification's length in bytes, and
        1.1 defines the initial UPLOAD's element count as (Length GET_ID [BYTE]) / AG -- an
        inexact division leaves the master unable to ask for the right number of elements.
        Refused here rather than at run time because for the configured string it is knowable
        now, and an integrator should learn at build time rather than on the wire. Callback-
        supplied identifications cannot be checked here and are checked in Xcp_DTOCmdStdGetId
        instead. DD112. #}
{{ raise('identification {!r} is {} bytes, which is not a multiple of the {}-byte {} address granularity; XCP part 2 1.1/1.6.1.2.2 requires Length mod AG = 0 because the initial UPLOAD element count is Length / AG'.format(configuration.protocol_layer.identification, configuration.protocol_layer.identification | length, ag_size, configuration.protocol_layer.address_granularity)) }}
{%- endif %}
```

- [ ] **Step 4: Change the shipped default in all three places**

`config/xcp.json:308`:
```json
        "identification": "/path/to/xcp.a2l"
```

`config/xcp.schema.json`, the `identification` property — add a description alongside the new default:
```json
              "identification": {
                "description": "Identification type 0 (ASCII) returned by GET_ID, and the fallback for type 0 when no get_id_function is configured. XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 requires Length mod AG = 0, so its length must be a multiple of address_granularity; generation refuses a configuration where it is not. The default is 16 bytes, which conforms under BYTE, WORD and DWORD alike.",
                "type": "string",
                "default": "/path/to/xcp.a2l"
              },
```

`test/parameter.py:395`:
```python
                 identification='/path/to/xcp.a2l',
```

- [ ] **Step 5: Run the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: all green. `test_get_id_returns_identification_through_mta_when_mode_is_0` passes its own explicit `identification` and is unaffected; `test/session_teardown_test.py`'s GET_ID tests read whatever the default is and should follow the change without edits. If either asserts the old 21-byte string literally, update the expectation — do not revert the default.

- [ ] **Step 6: Mutation-verify**

Change the guard's `% ag_size != 0` to `% 1 != 0` (always false, guard never fires) and confirm `test_generation_refuses_an_identification_that_is_not_a_multiple_of_the_granularity` fails on all three rows. Revert.

- [ ] **Step 7: Commit and push**

```bash
git add script/source_cfg.c.jinja2 config/xcp.json config/xcp.schema.json test/parameter.py test/daq_configuration_test.py
git commit -m "feat: refuse an identification whose length is not a multiple of AG

XCP part 2 1.1/1.6.1.2.2 adds a rule 1.0/1.6.1.2.2 does not have --
'Length mod AG = 0' -- protecting the UPLOAD that follows, whose element
count 1.1 defines as (Length GET_ID [BYTE]) / AG.

The module already violated it: the default identification is 21 bytes,
and 21 mod 2 and 21 mod 4 are both 1, so every configuration using WORD
or DWORD granularity reported a non-conforming Length. Eleven test files
exercise non-BYTE AG through the shared DefaultConfig.

The default therefore changes from /path/to/database.a2l (21 bytes) to
/path/to/xcp.a2l (16), which conforms under every granularity -- without
it the new guard would reject the module's own default configuration.

Callback-supplied identifications are not knowable at generation time and
are checked at run time instead. DD112.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 4: The integrator callback

DD108 and DD109. After this task every identification type can be served.

**Files:**
- Modify: `interface/Xcp_Types.h` (tail of `Xcp_GeneralType`, after `readStoredSessionConfigurationIdApiEnable`)
- Modify: `config/xcp.schema.json` (new `get_id_function` property, added to `required`)
- Modify: `config/xcp.json` (`"get_id_function": null`)
- Modify: `script/source_cfg.c.jinja2:1233` area (initialiser tail)
- Modify: `source/Xcp_Std.c` (`Xcp_DTOCmdStdGetId`)
- Modify: `test/parameter.py`, `test/conftest.py`
- Test: `test/get_id_test.py`

**Interfaces:**
- Consumes: `XCP_GET_ID_TYPE_*` from Task 2.
- Produces:
  ```c
  Std_ReturnType (*const getIdentificationFunction)(uint8 identificationType,
                                                    const void **pIdentification,
                                                    uint8 *pExtension,
                                                    uint32 *pLength);
  ```
  Harness attribute `handle.xcp_get_identification_function` (a `MagicMock`), config knob `DefaultConfig(get_id_function='Xcp_GetIdentificationFunction')`. Task 5 uses both.

- [ ] **Step 1: Write the failing tests**

Append to `test/get_id_test.py`:

```python
_CALLBACK_CONFIG = dict(channel_rx_pdu_ref=0x0001,
                        get_id_function='Xcp_GetIdentificationFunction')


def _serve(handle, payload, extension=0x00):
    """Make the configured callback answer `payload` for every type, and keep the buffer alive."""
    buffer = handle.ffi.new('char[]', payload)
    handle._pdu_info_keepalive.append(buffer)

    def get_identification(_type, p_identification, p_extension, p_length):
        p_identification[0] = handle.ffi.cast('void *', buffer)
        p_extension[0] = extension
        p_length[0] = len(payload)
        return handle.define('E_OK')

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
```

- [ ] **Step 2: Run and verify they fail**

Expected: every new test errors in `XcpTest(...)` construction — `get_id_function` is not a `DefaultConfig` parameter yet.

- [ ] **Step 3: Add the schema property**

In `config/xcp.schema.json`, beside `user_cmd_function`, matching its shape exactly:

```json
              "get_id_function": {
                "description": "Optional integrator callback supplying GET_ID identification data for any type. XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 leaves which types a slave supports implementation specific; this is how it decides. Returning E_NOT_OK means the type is not served, which answers Length = 0 -- except for type 0, which falls back to the configured identification string. null means only type 0 is served, from that string alone.",
                "OneOf": [
                  {
                    "type": "null"
                  },
                  {
                    "type": "string",
                    "enum": [
                      "Xcp_GetIdentificationFunction"
                    ]
                  }
                ],
                "default": null
              },
```

Add `"get_id_function"` to the same `required` array that already lists `"user_cmd_function"` and `"identification"`.

- [ ] **Step 4: Add the struct field at the tail**

In `interface/Xcp_Types.h`, as the **last** member of `Xcp_GeneralType`, after `readStoredSessionConfigurationIdApiEnable`:

```c
    /**
     * @brief supplies GET_ID identification data for any identification type.
     * @param identificationType the Requested Identification Type from the GET_ID request: 0..4 or
     * 128..255 (XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2). 5..127 are refused before
     * this is called.
     * @param pIdentification set to the address the master will UPLOAD the identification from.
     * @param pExtension set to the MTA address extension that address is reached through. 0 unless
     * the data lives in a region the integrator's Xcp_ReadSlaveMemory* selects with a non-zero
     * extension (DD109).
     * @param pLength set to the identification's length in bytes. Must be a multiple of the
     * configured address granularity -- 1.1/1.6.1.2.2's "Length mod AG = 0" -- or the module raises
     * XCP_E_IDENTIFICATION_NOT_GRANULAR and answers Length = 0 (DD112).
     * @return E_OK with all three out-parameters set, or E_NOT_OK meaning this slave does not serve
     * that type. E_NOT_OK is not an error: it answers Length = 0, which 1.1/1.6.1.2.2 defines as
     * "the requested identification type is not available". For type 0 it falls back to the
     * configured identification string instead.
     * @note not part of the specification. NULL_PTR means only type 0 is served, from the
     * configured identification string.
     */
    Std_ReturnType (*const getIdentificationFunction)(uint8 identificationType,
                                                      const void **pIdentification,
                                                      uint8 *pExtension,
                                                      uint32 *pLength); /* not part of the specification... */
} Xcp_GeneralType;
```

- [ ] **Step 5: Add the initialiser entry at the tail**

In `script/source_cfg.c.jinja2`, find the **last** entry of the `Xcp_GeneralType` initialiser — the one emitting `readStoredSessionConfigurationIdApiEnable` — and add immediately after it, following the `user_cmd_function` idiom at line 1231:

```jinja
    {% if configuration.protocol_layer.get_id_function %}&{{configuration.protocol_layer.get_id_function}}{% else %}NULL_PTR{% endif %}, /* getIdentificationFunction */
```

**Verify the position before running anything else:** generate once and diff the generated source against the previous revision. Exactly one line may be added, and no existing initialiser value may move to a different field. This struct is positional.

- [ ] **Step 6: Wire the harness**

In `test/conftest.py`, beside the `Xcp_UserCmdFunction` registration around line 594:

```python
        self.xcp_get_identification_function = MagicMock()
        self.config.ffi.def_extern('Xcp_GetIdentificationFunction')(
                self._guarded_callback('Xcp_GetIdentificationFunction',
                                       self.xcp_get_identification_function))
        self.xcp_get_identification_function.return_value = self.define('E_NOT_OK')
```

`E_NOT_OK` is the right default: a test that configures the callback without setting a `side_effect` gets "serves nothing", not a mock returning a truthy `MagicMock` that the module would read as `E_OK` with unset out-parameters.

In `test/parameter.py`, add the parameter beside `user_cmd_function` (line 393) and the emitted key beside it (line 419):

```python
                 get_id_function=None,
```
```python
            "get_id_function": get_id_function,
```

- [ ] **Step 7: Consult the callback in the command**

In `source/Xcp_Std.c`, inside `Xcp_DTOCmdStdGetId`'s `else` branch, replace the type-0-only block from Task 2 with:

```c
        const void *identification = NULL_PTR;
        uint8 extension = 0x00u;
        uint32 identification_length = 0x00000000u;
        boolean served = FALSE;

        if (Xcp_Ptr->general->getIdentificationFunction != NULL_PTR)
        {
            /* Consulted for every defined type including 0, so an integrator who needs a
             * runtime-varying type 0 can override the configured string. Declining it falls back
             * to that string below, which is what makes a NULL_PTR callback and a callback that
             * returns E_NOT_OK for type 0 behave identically. DD110. */
            if (Xcp_Ptr->general->getIdentificationFunction(identification_type,
                                                            &identification,
                                                            &extension,
                                                            &identification_length) == E_OK)
            {
                served = TRUE;
            }
            else
            {
                identification = NULL_PTR;
                extension = 0x00u;
                identification_length = 0x00000000u;
            }
        }

        if ((served == FALSE) && (identification_type == XCP_GET_ID_TYPE_ASCII))
        {
            identification = (const void *)Xcp_Ptr->general->identification;
            /* <-- DD75's existing comment block stays here --> */
            extension = 0x00u;

            for (identification_length = 0x00000000u;
                 identification_length < 0xFFFFFFFFu;
                 identification_length++)
            {
                if (Xcp_Ptr->general->identification[identification_length] == 0x00u)
                {
                    break;
                }
            }
        }
```

The rest of the `else` branch — the MTA assignment, the response bytes and `Xcp_FinalizeResPacket` — is unchanged from Task 2.

- [ ] **Step 8: Run the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: all green.

- [ ] **Step 9: Mutation-verify**

1. Make the callback's `E_NOT_OK` path set `served = TRUE` → `test_get_id_falls_back_to_the_static_identification_when_the_callback_declines_type_zero` must fail.
2. Hardcode `extension = 0x00u` after the callback returns → `test_get_id_points_the_mta_at_the_callbacks_address_and_extension` must fail.
3. Move the callback consultation above the 5–127 refusal → `test_get_id_does_not_consult_the_callback_for_an_undefined_type` must fail.

- [ ] **Step 10: Commit and push**

```bash
git add interface/Xcp_Types.h config/xcp.json config/xcp.schema.json script/source_cfg.c.jinja2 source/Xcp_Std.c test/conftest.py test/parameter.py test/get_id_test.py
git commit -m "feat: serve every GET_ID identification type from an integrator callback

XCP part 2 1.1/1.6.1.2.2 defines identification types 0-4 and a 128-255
user-defined range, and leaves which of them a slave supports
implementation specific. Types 1-3 are strings that could have gone in
xcp.json; type 4 is 'ASAM-MC2 file to upload', a whole A2L file not known
at generation time, and 128-255 is an open range no fixed table can
enumerate. So the mechanism is an optional callback, following the
existing user_cmd_function pattern. DD108.

The callback returns the MTA address extension alongside the address.
DD75 fixed extension = 0 for the static identification specifically
because it lives outside the page-switching model; that argument does not
transfer to an A2L file in a region reached through a non-zero extension,
and fixing it at 0 would advertise type 4 while only being able to serve
it from extension-0 memory. DD109.

The callback is consulted for every defined type including 0, with the
configured string as type 0's fallback, so a NULL_PTR callback behaves
exactly as the module did before this phase.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 5: Check callback lengths against the address granularity

DD112's runtime half. Task 3 covered the configured string; a callback-supplied length is not knowable at generation time.

**Files:**
- Modify: `interface/Xcp.h` (new DET code after `XCP_E_DAQ_LIST_NOT_IDENTIFIABLE`)
- Modify: `source/Xcp_Std.c` (`Xcp_DTOCmdStdGetId`)
- Test: `test/get_id_test.py`

**Interfaces:**
- Consumes: everything from Task 4.
- Produces: `XCP_E_IDENTIFICATION_NOT_GRANULAR` (`0x09u`).

- [ ] **Step 1: Write the failing test**

Append to `test/get_id_test.py`:

```python
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

    raw_data = _get_id(handle, 0x01)

    assert raw_data[0] == 0xFF, 'still a positive response'
    assert u32_from_array(bytearray(raw_data[4:8]), 'LITTLE_ENDIAN') == 0, \
        'a non-conforming length must be reported as unavailable, not emitted'
    handle.det_report_error.assert_called_once_with(
        ANY, ANY,
        handle.define('XCP_MAIN_FUNCTION_API_ID'),
        handle.define('XCP_E_IDENTIFICATION_NOT_GRANULAR'))


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
```

`test/get_id_test.py` needs `from unittest.mock import ANY` added at the top: `from .parameter import *` does not re-export it. The four-argument shape above matches the existing caller at `test/asam_protocol_layer_test.py:17` — module id, instance id, api id, error id.

**Correction, made during Task 5's fix round 1** (commit `61938ab`): both `handle.define('XCP_MAIN_FUNCTION_API_ID')` calls in the test code above name the wrong API. See the fuller correction after Step 4, where the same wrong value appears in the implementation this test code was written against.

- [ ] **Step 2: Run and verify it fails**

Expected: the refusing test fails — the module reports the true length and calls no DET.

- [ ] **Step 3: Add the DET code**

In `interface/Xcp.h`, after `XCP_E_DAQ_LIST_NOT_IDENTIFIABLE (0x08u)`:

```c
/**
 * @brief A GET_ID callback returned a length that is not a multiple of the address granularity.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2 requires "Length mod AG = 0",
 * protecting the UPLOAD that follows: 1.1 defines its element count as
 * (Length GET_ID [BYTE]) / AG, and an inexact division leaves the master unable to ask for the
 * right number of elements. The configured identification string is checked at generation time
 * instead (script/source_cfg.c.jinja2); this covers what getIdentificationFunction returns, which
 * is not knowable then.
 * @note This error is not part of the specification, and Det is the only channel it has: the master
 * is told the type is unavailable (Length = 0), which is indistinguishable on the wire from a slave
 * that simply does not serve it. DD112.
 */
#define XCP_E_IDENTIFICATION_NOT_GRANULAR (0x09u)
```

- [ ] **Step 4: Check the length**

In `source/Xcp_Std.c`, immediately after the callback block in Task 4's Step 7 (before the static fallback), add:

```c
        if (served == TRUE)
        {
            const uint8 element_size =
                Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

            if ((identification_length % (uint32)element_size) != 0x00000000u)
            {
                /* 1.1/1.6.1.2.2: "Length mod AG = 0". The module cannot emit a non-conforming
                 * Length, so the type is reported unavailable and the integrator hears about it
                 * through Det -- the master has no channel for this distinction. DD112. */
                Xcp_ReportError(0x00u, XCP_MAIN_FUNCTION_API_ID,
                                XCP_E_IDENTIFICATION_NOT_GRANULAR);
                identification = NULL_PTR;
                extension = 0x00u;
                identification_length = 0x00000000u;
                served = FALSE;
            }
        }
```

Setting `served = FALSE` here deliberately does **not** fall through to the static string for type 0: a callback that answered `E_OK` has claimed the type, and silently substituting different data for a length it got wrong would hide the defect DET has just reported. Confirm this by checking that `test_get_id_falls_back_to_the_static_identification_when_the_callback_declines_type_zero` still passes — it declines with `E_NOT_OK` and must be unaffected. If the ordering makes a type-0 `E_OK` with a bad length fall back to the string, move this block after the static-fallback block instead.

**Correction, made during Task 5's fix round 1** (commit `61938ab`): the `Xcp_ReportError` call above, and the two `handle.define('XCP_MAIN_FUNCTION_API_ID')` calls in Step 1's test code, all name the wrong API. `Xcp_DTOCmdStdGetId` does not run inside `Xcp_MainFunction`: the command table's one dispatch site, `result = Xcp_PIDTable[pid](&response_expected, pPduInfo);`, is at `source/Xcp.c:2161`, inside `Xcp_CanIfRxIndication` (`source/Xcp.c:1807–2285`); `Xcp_MainFunction` (`source/Xcp.c:1501–1806`) never calls it. The module's convention reports the exported API in whose call chain a DET fires — `Xcp_DTOCmdStdBuildChecksum`, another command dispatched through the same table, already reports under `XCP_CAN_IF_RX_INDICATION_API_ID` (`source/Xcp_Std.c:638`) — so the correct value here is `XCP_CAN_IF_RX_INDICATION_API_ID`. `XCP_MAIN_FUNCTION_API_ID` was this plan's own unchecked assumption about where commands dispatch; both the shipped code and the two tests asserting it inherited that assumption from this code block and Step 1's, which is why the tests could not catch the error — implementation and expectation shared one wrong source. Not rewritten in place, per this repository's convention (DD102, DD105) of recording a correction rather than silently editing history.

- [ ] **Step 4b: Give the generator guard its cross-reference, now that it is true**

Task 3 deliberately worded `script/source_cfg.c.jinja2`'s `Length mod AG = 0` guard comment to describe only its own scope, naming no specific future check — because at that commit no run-time check existed, and claiming one would have been the defect class this branch has already shipped twice. That check now exists. Add the concrete cross-reference to the guard's comment: the configured string is validated here, and a callback-supplied length is validated in `Xcp_DTOCmdStdGetId`, which raises `XCP_E_IDENTIFICATION_NOT_GRANULAR` and answers `Length = 0`. Keep the scope sentence — it is still the reason the split exists.

Read the comment as it stands before editing. Do not restore wording from any earlier draft; write what is true of the code in front of you.

- [ ] **Step 5: Run the full suite and mutation-verify**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```

Mutations, each reverted:
1. Change `% (uint32)element_size` to `% 1u` → the refusing test must fail on all three rows.
2. Delete the `Xcp_ReportError` call, keep the rest → the refusing test must fail on the DET assertion while still passing on `Length == 0`. This is what proves the DET assertion is not riding on the length assertion.

- [ ] **Step 6: Commit and push**

```bash
git add interface/Xcp.h source/Xcp_Std.c test/get_id_test.py
git commit -m "feat: refuse a callback identification length that violates Length mod AG

DD112's runtime half. The configured string is checked at generation time,
but what getIdentificationFunction returns is not knowable then.

XCP part 2 1.1/1.6.1.2.2's 'Length mod AG = 0' protects the UPLOAD that
follows, whose element count 1.1 defines as (Length GET_ID [BYTE]) / AG.
The module cannot emit a non-conforming Length, and reporting the type
unavailable is the honest alternative to truncating the data or padding
it with the NULs 1.1 explicitly says the string does not carry.

Det is the only channel this has: on the wire, Length = 0 is
indistinguishable from a slave that simply does not serve the type.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

---

### Task 6: Update the roadmap and open the PR

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md:100`, `:373`, `:560`, `:651`

- [ ] **Step 1: Update the `GET_ID` coverage row**

Line 100 currently reads:
```
| 0xFA | GET_ID | partial — identification type 0 (ASCII) only; §1.6.1.2.2 defines 0–4 plus 128–255 user-defined, all implementation-specific |
```
Replace with:
```
| 0xFA | GET_ID | complete — types 0–4 and 128–255 served through `getIdentificationFunction`, type 0 falling back to the configured string; a defined type the slave does not serve answers `Length = 0` per 1.1/§1.6.1.2.2, 5–127 answer `ERR_OUT_OF_RANGE`. `TRANSFER_MODE` deliberately stays 0 (DD111) |
```

- [ ] **Step 2: Update the three SP5 residue sentences**

At lines 373, 560 and 651, remove `GET_ID` identification types from the lists of remaining residue. Line 651's "the interleaved model, `EV_CMD_PENDING`, `GET_ID` types and the `SERV_*` codes are genuinely independent" needs `EV_CMD_PENDING` checked too — the SP5 section already records it as done, so verify before editing whether that sentence is stale in more than one way and correct what you find rather than only the `GET_ID` clause.

- [ ] **Step 3: Add an SP5-GETID sub-project entry**

After the `SP5-RESUME` entry, matching that entry's shape — a `#### SP5-GETID — GET_ID identification types — **complete**` heading, then paragraphs covering:

- **What it built:** every identification type 1.1/§1.6.1.2.2 defines, served through `getIdentificationFunction`, with the configured string as type 0's fallback.
- **Design:** `2026-09-11-xcp-get-id-types-design.md` (DD108–DD113 as this step was written; the spec now runs to DD114, and the roadmap entry this step produced carries the wider range).
- **What 1.1 changed and 1.0 did not have:** the response Mode byte becoming a named bit mask (`TRANSFER_MODE` bit 0, `COMPRESSED_ENCRYPTED` bit 1), plus `Length mod AG = 0` and the initial-UPLOAD element count. Record that bit positions came from the 1.1 PDF's own text layer, not its OCR sidecar, and point at §0 of the design doc for the method — this is the second time the 1.0-vs-1.1 mode-byte pattern has appeared, after `SET_REQUEST`.
- **Two pre-existing defects it fixed:** the Mode-byte assertion that pinned an echo of the request rather than the response's bit mask, and the 21-byte default identification that violated `Length mod AG = 0` under WORD and DWORD.
- **What it deliberately did not build:** inline transfer (DD111) and compression (XCP Part 4 absent), both reversible and both now documented rather than forgotten.

**Correction, made after Task 1's implementer disproved it empirically**
(commit `afa5c8e`): the bullet above originally read
"the Mode-byte assertion that could not fail." The old assertion could fail — it compared the
response's Mode bit mask against the request's Requested Identification Type, two different fields,
and pinned the correct value only because its parametrize list held a single row at mode 0. It would
have demanded the wrong thing, an echo of the request, once a second identification type was
covered. Corrected here rather than left standing, matching the same correction already made to Task
1's own title above.

Then check whether any *other* roadmap row is made stale by this phase before committing — §2.6 cross-cutting and the §3 defect list both mention `GET_ID`. Correct what you find; do not silently rewrite a claim that turns out to have been wrong, record the correction, as DD102 and DD105 do.

**Correction, made in the final review's fix wave**
(commit `efafeaf`): the premise of the step above
is false. Neither §2.6 nor the §3 defect list mentions `GET_ID` — not at this plan's baseline
(`38eb3ff`), and not after this phase's own roadmap edits. At the baseline the roadmap named
`GET_ID` only in §2.1's command table and in §4's SP5 residue text, and neither section mentions
the identification either. The instruction to check other rows still stands; the two sections it
pointed at simply had nothing for it to find.

- [ ] **Step 4: Commit, push, open the PR**

```bash
git add docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
git commit -m "docs: record SP5-GETID in the conformance roadmap

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
gh pr create --base develop --title "feat: GET_ID identification types 1-4 and 128-255" --body "$(cat <<'BODY'
Extends GET_ID beyond identification type 0 (ASCII), the last small well-defined item on the SP5 residue list.

Design: `docs/superpowers/specs/2026-09-11-xcp-get-id-types-design.md` (DD108-DD113).

## What this adds

- An optional `get_id_function` callback supplying identification data, MTA address and extension for any type. Type 4 is a whole A2L file and 128-255 is an open range, so neither fits in `xcp.json`.
- `Length = 0` for a defined type the slave does not serve, which is 1.1/§1.6.1.2.2's own way of declining. `ERR_OUT_OF_RANGE` narrows to 5-127, the values that name no identification type at all, keeping §1.7.3.2.1's GET_ID row reachable.
- Enforcement of 1.1's `Length mod AG = 0`, at generation time for the configured string and at run time for callback data.

## Two defects found while reading the specification

- `test_get_id_returns_identification_through_mta_when_mode_is_0` asserted `raw_data[1] == mode`, comparing the response's Mode bit mask against the request's Requested Identification Type -- two different fields coinciding at zero against a hardcoded `0x00`, pinned only by this test's single-row parametrize list at mode 0. Fixed first, as its own commit.
- The default identification is 21 bytes, so the module already reported a `Length` violating 1.1's `Length mod AG = 0` under WORD or DWORD granularity. The default changes to a 16-byte string.

## Deliberately not built

`TRANSFER_MODE = 1` (inline transfer). The request packet is two bytes, so the master cannot ask for it; the slave chooses, and mode 0 is a complete answer in both revisions. Both mode bits are given named constants anyway, at positions recovered from the 1.1 PDF rather than its OCR sidecar. `COMPRESSED_ENCRYPTED` additionally depends on XCP Part 4, which is not in `docs/external/`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

- [ ] **Step 5: Confirm CI is green**

CI is the authoritative verification. Confirm the PR actually merged (`gh pr view N --json state,mergedAt`) before deleting the branch.

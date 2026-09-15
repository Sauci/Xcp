# ERR_GENERIC Detail Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close roadmap defect D17 — attach the implementation-specific WORD that XCP Part 2 1.1/§1.1.3.3 defines for `ERR_GENERIC`, at all five sites that answer it.

**Architecture:** Five module-defined detail codes go in a fenced block in `interface/Xcp_Errors.h`. One shared helper in `source/Xcp.c` writes the WORD in the configured byte order and delegates to the existing `Xcp_FillErrorPacketWithData`. The five call sites — one in `Xcp_Std.c`, four in `Xcp_Pgm.c` — each pass their own code.

**Tech Stack:** C (GCC 8.3.0, no `-std` flag, so gnu17), Python 3.7 + pytest 7.4.4 + cffi 1.15.0 test harness, CMake, Docker.

**Spec:** `docs/superpowers/specs/2026-09-15-xcp-err-generic-detail-design.md` (decisions DD121–DD125). Read it alongside this plan.

## Global Constraints

- **Reference revision is 1.1.** Every specification citation carries a revision prefix, e.g. `1.1/§1.1.3.3`, never a bare section number.
- **Tests run in Docker only.** A host run of `./test.sh` fails in a way that *resembles a pass*. The exact invocation, from the repository root:
  ```bash
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local ./test.sh
  ```
  The `--user` flag is load-bearing: without it the run leaves root-owned files under `build/` you cannot delete.
- **A run that stops short with a pycparser, PLY, Jinja2 or CFFI error is not a result — re-run it.** The suite aborts that way roughly one run in four for reasons unrelated to any change.
- **A known non-failure:** a scoped run can end with `test.sh: no profile directories found, so no coverage can be reported` and a non-zero exit code *while ctest reports `100% tests passed`*. That is `test.sh`'s coverage merge (test.sh:199) when a narrow selection builds too few modules. **Read ctest's verdict, not the shell exit code.**
- **`XCP_PYTEST_ARGS` is a CMake cache variable** (`CMakeLists.txt:17`), consumed only as pytest arguments at `:307`. Seeding it scopes **every later run** until cleared. To scope a run, from inside the container:
  ```bash
  cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;err_generic" && cd ..
  ```
  and **always clear it before the next task**:
  ```bash
  cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd ..
  ```
- **Never `rm -rf generated/*`** — it holds a tracked `generated/CMakeLists.txt`. Clearing `build/` is safe.
- **Commit trailer**, on every commit, on its own line:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  ```
- **Branch:** `fix/xcp-err-generic-detail`, already created from `develop` at `441eb25` and already carrying three doc commits. Everything lands as one PR against `develop`; CI is the authoritative verification.
- **Match local style.** These files use Allman braces at function and `if`/`else` level. Every call site you touch sits inside a comment block explaining *why* that site answers `ERR_GENERIC` — those comments stay, unchanged, unless a step says otherwise.

---

## File Structure

| File | Responsibility | Change |
|:--|:--|:--|
| `interface/Xcp_Errors.h` | wire error codes, integrator-visible | add a fenced block of five module-defined detail codes |
| `source/Xcp.c` | shared packet helpers | add `Xcp_FillGenericErrorPacket` after `Xcp_FillErrorPacketWithData` |
| `source/Xcp_Internal.h` | internal declarations | declare it beside its two siblings |
| `source/Xcp_Std.c` | STD command handlers | route the `UNLOCK` site through it |
| `source/Xcp_Pgm.c` | PGM command handlers | route four sites through it |
| `test/seed_key_defects_test.py` | UNLOCK defect regression | two assertion sites amended |
| `test/pgm_deferred_test.py` | deferred PGM completion | two assertion sites amended |
| `test/pgm_session_test.py` | PGM session state | one assertion site amended, one test added |

**Task 2 lands the helper unused, deliberately.** It keeps the mechanical addition separable from the five behaviour changes, so a reviewer can reject one without the other — the same shape D6 used when it landed a config field before anything read it.

---

### Task 1: The five detail codes

**Files:**
- Modify: `interface/Xcp_Errors.h` — insert before the closing `#endif` (currently line 116)

**Files (continued):**
- Modify: `test/parameter.py` — add `u16_from_array` beside `u32_from_array` (line 92)

**Interfaces:**
- Produces, for Tasks 3–5: `XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED` (`0x0001u`), `XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE` (`0x0002u`), `XCP_GENERIC_DETAIL_PROGRAM_START_FAILED` (`0x0003u`), `XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED` (`0x0004u`), `XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED` (`0x0005u`).
- Produces, for Tasks 3–5: `u16_from_array(data: bytearray, endianness: str)` in `test/parameter.py`, reaching every test file through its `from .parameter import *`.
- Consumes: nothing.

No test accompanies this task. These are `#define`s with no behaviour; the full suite compiling them is the only check available, and Task 2 is what first uses them. This is a deliberate exception to the TDD cycle, not an omission.

- [ ] **Step 1: Add `u16_from_array` to the test helpers**

Tasks 3–5 decode the two-byte payload, and `test/parameter.py` has `u16_to_array`, `u32_to_array` and `u32_from_array` but **no 16-bit decoder** — the one width that was never needed before. Add it immediately after `u32_from_array` (line 92), matching that function's shape exactly:

```python
def u16_from_array(data: bytearray, endianness: str):
    return int.from_bytes(data, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[endianness], signed=False)
```

It reaches every test file through the `from .parameter import *` each already does, so no import line changes anywhere.

- [ ] **Step 2: Add the fenced block**

In `interface/Xcp_Errors.h`, immediately after the `XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` define and before `#endif /* #ifndef XCP_ERRORS_H */`:

```c
/*------------------------------------------------------------------------------------------------*/
/* Detail codes for ERR_GENERIC's extended payload.                                               */
/*                                                                                                */
/* NOT ASAM-DEFINED. Everything above this fence is a code the specification names and numbers.    */
/* These are not: XCP part 2 - Protocol Layer Specification 1.1/1.1.3.3 says only that an          */
/* ERR_GENERIC packet "contains an implementation specific slave device error code as WORD as      */
/* additional information", leaving the value to whoever writes the slave. This module is that     */
/* implementation, and these are its values. A master decodes them against THIS header, not        */
/* against the specification. Design doc DD121-DD124,                                             */
/* docs/superpowers/specs/2026-09-15-xcp-err-generic-detail-design.md.                             */
/*                                                                                                */
/* 0x0000 is reserved and never emitted, so a zeroed or stale buffer cannot decode as a valid      */
/* detail code (DD123, the same reasoning as protocol_layer.checksum_max_block_size's minimum      */
/* of 1).                                                                                          */
/*------------------------------------------------------------------------------------------------*/

/**
* @brief UNLOCK: the integrator's Xcp_CalcKey returned E_NOT_OK, so no key could be computed at
* all. Distinct from ERR_ACCESS_LOCKED, which asserts the key was WRONG.
 */
#define XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED (0x0001u)

/**
* @brief PROGRAM_START: a programming session is already active (pgm_state is not XCP_PGM_IDLE).
* Refused by this module's own state gate, not by the integrator.
 */
#define XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE (0x0002u)

/**
* @brief PROGRAM_START: the integrator's Xcp_ProgramStart reported a non-zero status code, i.e. a
* slave that cannot permit programming (XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.1).
 */
#define XCP_GENERIC_DETAIL_PROGRAM_START_FAILED (0x0003u)

/**
* @brief PROGRAM_RESET: the integrator's Xcp_ProgramReset reported a non-zero status code.
 */
#define XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED (0x0004u)

/**
* @brief PROGRAM_PREPARE: the integrator's Xcp_ProgramPrepare reported a non-zero status code, i.e.
* target memory that is not "in a operational state which permits the download of code" (XCP part 2
* - Protocol Layer Specification 1.1/1.6.5.2.3).
 */
#define XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED (0x0005u)

```

- [ ] **Step 3: Verify the full suite still builds and passes**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`. Nothing reads the new defines yet, so what this proves is that the header still compiles everywhere it is included — which is real, since `interface/Xcp.h:52` pulls it into every translation unit — and that `u16_from_array` did not break the star import every test file relies on.

- [ ] **Step 4: Commit**

```bash
git add interface/Xcp_Errors.h test/parameter.py
git commit -m "$(cat <<'EOF'
feat: define ERR_GENERIC's detail codes

XCP part 2 1.1/1.1.3.3 leaves the WORD accompanying ERR_GENERIC to the
implementation. These five values are this module's, fenced off from the
ASAM-defined codes above them so nobody mistakes one for the other, and
documented so a master can decode FE 31 xx xx against this header.

0x0000 is reserved and never emitted: a zeroed or stale buffer must not
decode as a valid code.

Nothing reads them yet.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: The shared helper

**Files:**
- Modify: `source/Xcp.c` — insert after `Xcp_FillErrorPacketWithData`, which ends at line 2700
- Modify: `source/Xcp_Internal.h` — declare after line 936

**Interfaces:**
- Consumes: `Xcp_FillErrorPacketWithData(const uint8 errorCode, const uint8 *pData, const uint8 dataLength, PduInfoType *pPduInfo)` (`Xcp_Internal.h:936`); `Xcp_CopyFromU16WithOrder(const uint16 src, uint8 *pDest, Xcp_ByteOrderType endianness)` (`:939`); `XCP_E_ASAM_GENERIC` (`interface/Xcp_Errors.h`).
- Produces, for Tasks 3–4: `void Xcp_FillGenericErrorPacket(const uint16 detail, PduInfoType *pPduInfo);`

Still no behaviour change — nothing calls it until Task 3.

- [ ] **Step 1: Declare it**

In `source/Xcp_Internal.h`, immediately after the `Xcp_FillErrorPacketWithData` declaration at line 936:

```c
void Xcp_FillGenericErrorPacket(const uint16 detail, PduInfoType *pPduInfo);
```

- [ ] **Step 2: Define it**

In `source/Xcp.c`, immediately after `Xcp_FillErrorPacketWithData`'s closing brace (line 2700):

```c
/* XCP part 2 - Protocol Layer Specification 1.1/1.1.3.3 gives ERR_GENERIC an extended payload of
 * its own: "the error packet contains an implementation specific slave device error code as WORD
 * as additional information". The value is this module's to define -- see the fenced block of
 * XCP_GENERIC_DETAIL_* codes in interface/Xcp_Errors.h, and design doc DD121-DD125 in
 * docs/superpowers/specs/2026-09-15-xcp-err-generic-detail-design.md.
 *
 * Shared rather than repeated at each of the five sites that answer ERR_GENERIC (DD125): one in
 * source/Xcp_Std.c and four in source/Xcp_Pgm.c. Xcp_FillErrorPacketWithData stays the single
 * place that knows an error packet's payload begins at byte 2. */
void Xcp_FillGenericErrorPacket(const uint16 detail, PduInfoType *pPduInfo)
{
    uint8 data[0x02u];

    Xcp_CopyFromU16WithOrder(detail, &data[0x00u], Xcp_Ptr->general->byteOrder);

    Xcp_FillErrorPacketWithData(XCP_E_ASAM_GENERIC, data, sizeof(data), pPduInfo);
}
```

- [ ] **Step 3: Verify the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`.

If the compiler warns that `Xcp_FillGenericErrorPacket` is defined but not used, that is expected at this task and resolves in Task 3. If it is an *error* rather than a warning, stop and report — this project sets no `-Werror`, so it should not be.

- [ ] **Step 4: Commit**

```bash
git add source/Xcp.c source/Xcp_Internal.h
git commit -m "$(cat <<'EOF'
feat: add Xcp_FillGenericErrorPacket

Writes ERR_GENERIC's 1.1/1.1.3.3 detail WORD in the configured byte order
and delegates to Xcp_FillErrorPacketWithData, so that function stays the
single place knowing an error packet's payload starts at byte 2.

Shared rather than repeated at the five sites answering ERR_GENERIC, which
span source/Xcp_Std.c and source/Xcp_Pgm.c. Nothing calls it yet.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: The two state-refusal sites

These are the two conditions the module itself detects, as opposed to the three where an integrator callback reports failure.

**Files:**
- Modify: `source/Xcp_Std.c:963` (inside `Xcp_DTOCmdStdUnlock`)
- Modify: `source/Xcp_Pgm.c:208` (inside `Xcp_DTOCmdPgmProgramStart`)
- Test: `test/seed_key_defects_test.py`

**Interfaces:**
- Consumes: `Xcp_FillGenericErrorPacket` (Task 2); `XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED`, `XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE` (Task 1).
- Produces: nothing later tasks depend on.

**Line numbers are as of commit `a51efa0`. Confirm them by content before editing** — Task 2 added lines to `source/Xcp.c`, not to these two files, so they should be unchanged, but check rather than trust.

- [ ] **Step 1: Write the failing test**

In `test/seed_key_defects_test.py`, amend the assertion at line 579 (inside `test_an_unlock_whose_calc_key_fails_answers_an_error_instead_of_a_stale_positive_response`). Replace:

```python
    assert unlock_response[0:2] == (0xFE, 0x31), (
        'UNLOCK answered {} for a failed Xcp_CalcKey, expected (0xFE, 0x31) [ERR_GENERIC]'.format(
                unlock_response))
```

with:

```python
    assert unlock_response[0:2] == (0xFE, 0x31), (
        'UNLOCK answered {} for a failed Xcp_CalcKey, expected (0xFE, 0x31) [ERR_GENERIC]'.format(
                unlock_response))

    # XCP part 2 - Protocol Layer Specification 1.1/1.1.3.3 gives ERR_GENERIC a WORD of
    # implementation-specific detail. The length is asserted at the mock rather than through
    # exchange(), which returns a decoded tuple and cannot see SduLength -- and it is asserted at
    # all, because SduDataPtr always holds a full MAX_CTO frame padded with trailingValue, so bytes
    # 2-3 are readable whether or not the module wrote them. Without the length check a module that
    # produced the right WORD but finalised the packet at 2 would pass.
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(unlock_response[2:4]), 'LITTLE_ENDIAN') == 0x0001, \
        'expected XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED'
```

Add `u16_from_array` to this file's imports from `.parameter` if it is not already there.

- [ ] **Step 2: Run it and verify it fails**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;calc_key_fails_answers_an_error" && cd .. && ./test.sh'
```

Expected: **FAIL** with `assert 2 == 4` on `SduLength` — the handler still answers a bare two-byte packet.

- [ ] **Step 3: Change the two call sites**

In `source/Xcp_Std.c`, inside `Xcp_DTOCmdStdUnlock`, change:

```c
                        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
```

to:

```c
                        Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED,
                                                   &Xcp_Internal.cto_response.pdu_info);
```

Leave the long comment above it exactly as it is — it explains DD76's recorded deviation and is unaffected by this change.

In `source/Xcp_Pgm.c`, inside `Xcp_DTOCmdPgmProgramStart`, change:

```c
    if (Xcp_Internal.pgm_state != XCP_PGM_IDLE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
    }
```

to:

```c
    if (Xcp_Internal.pgm_state != XCP_PGM_IDLE)
    {
        Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE,
                                   &Xcp_Internal.cto_response.pdu_info);
    }
```

- [ ] **Step 4: Run the test again**

Same command as Step 2. Expected: **PASS**.

- [ ] **Step 5: Full suite, then clear the cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`. The other four ERR_GENERIC assertions use `[0:2]` slices and cannot see the payload, so they keep passing — Task 5 is what makes them meaningful.

- [ ] **Step 6: Commit**

```bash
git add source/Xcp_Std.c source/Xcp_Pgm.c test/seed_key_defects_test.py
git commit -m "$(cat <<'EOF'
fix: carry a detail WORD on the two ERR_GENERIC state refusals

UNLOCK when Xcp_CalcKey fails outright, and PROGRAM_START when a session is
already active, now answer with 1.1/1.1.3.3's implementation-specific WORD
rather than a bare error code.

These are the two conditions the module detects itself; the three where an
integrator callback reports failure follow separately.

The test asserts SduLength at the mock rather than through exchange(),
which returns a decoded tuple. The length assertion is what makes the value
assertion mean anything: SduDataPtr always holds a full MAX_CTO frame
padded with trailingValue, so bytes 2-3 read back whether or not the module
wrote them.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: The three PGM completion sites

All three answer when an integrator callback reports a non-zero status. Same file, same one-line change each — but **each sits under its own distinct comment, and those comments stay untouched.** The three snippets below are not interchangeable; use the one that matches the site you are editing.

**Files:**
- Modify: `source/Xcp_Pgm.c:1847` (in `Xcp_PgmCompleteProgramStart`)
- Modify: `source/Xcp_Pgm.c:1951` (in `Xcp_PgmCompleteProgramReset`)
- Modify: `source/Xcp_Pgm.c:1974` (in `Xcp_PgmCompleteProgramPrepare`)

**Interfaces:**
- Consumes: `Xcp_FillGenericErrorPacket` (Task 2); `XCP_GENERIC_DETAIL_PROGRAM_START_FAILED`, `XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED`, `XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED` (Task 1).
- Produces: nothing later tasks depend on.

**Find each by its enclosing function, not by line number.** The line `Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);` appears **four** times in this file before Task 3 and three times after it; only the three inside the `Xcp_PgmComplete*` functions belong to this task. Task 3 already changed the fourth, in `Xcp_DTOCmdPgmProgramStart`. Do not use a global search-and-replace.

- [ ] **Step 1: Write the failing tests**

In `test/pgm_deferred_test.py`, amend the assertion at line 308 (in `test_a_failing_integrator_yields_err_generic_and_leaves_the_session_closed`). Replace:

```python
    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
```

with:

```python
    response = transmitted(handle)
    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    # 1.1/1.1.3.3's detail WORD. Asserted at the mock because transmitted() returns a decoded
    # tuple; asserted at all because a full MAX_CTO frame makes bytes 2-3 readable regardless.
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0003, \
        'expected XCP_GENERIC_DETAIL_PROGRAM_START_FAILED'
```

and the one at line 660 (in `test_a_failing_program_reset_yields_err_generic_and_does_not_disconnect`). Replace:

```python
    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
```

with:

```python
    response = transmitted(handle)
    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0004, \
        'expected XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED'
```

In `test/pgm_session_test.py`, amend the assertion at line 553 (in `test_program_prepare_answers_err_generic_on_a_non_zero_status_code`). Replace:

```python
    assert transmitted(handle)[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
```

with:

```python
    response = transmitted(handle)
    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0005, \
        'expected XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED'
```

Add `u16_from_array` to each file's imports from `.parameter` if not already present.

- [ ] **Step 2: Run them and verify all three fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;failing_integrator or failing_program_reset or program_prepare_answers_err_generic" && cd .. && ./test.sh'
```

Expected: all three **FAIL** with `assert 2 == 4` on `SduLength`.

Note that `-x` is hardcoded at `CMakeLists.txt:307`, so the session stops at the first failure. Seeing one failure is sufficient evidence for this step; the three go green together in Step 4.

- [ ] **Step 3: Change the three call sites**

In `Xcp_PgmCompleteProgramStart`, under the comment ending `...the same way Xcp_PgmAbandonPendingCommand's equivalent was. */`:

```c
        Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_PROGRAM_START_FAILED,
                                   &Xcp_Internal.cto_response.pdu_info);
```

In `Xcp_PgmCompleteProgramReset`, under the comment ending `...the master may simply try again. */`:

```c
        Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED,
                                   &Xcp_Internal.cto_response.pdu_info);
```

In `Xcp_PgmCompleteProgramPrepare`, under the comment ending `...a ERR_GENERIC will be returned." */`:

```c
        Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED,
                                   &Xcp_Internal.cto_response.pdu_info);
```

- [ ] **Step 4: Run the three tests again**

Same command as Step 2. Expected: all three **PASS**.

- [ ] **Step 5: Full suite, then clear the cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`.

- [ ] **Step 6: Verify no ERR_GENERIC call site was missed**

Count **calls**, not mentions — `source/Xcp_Std.c:953` is a comment citing the macro inside DD76's explanation, which this plan leaves untouched, so a bare name grep will always print it:

```bash
grep -n 'Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC' source/Xcp_Std.c source/Xcp_Pgm.c
```

Expected: **no output**. Every call now goes through `Xcp_FillGenericErrorPacket`.

For contrast, this *will* still print one line, and that is correct:

```bash
grep -cn 'XCP_E_ASAM_GENERIC' source/Xcp_Std.c
```

Expected: `1` — DD76's comment at `:953`. If it prints `0`, that comment was deleted and should be restored; if it prints more than `1`, a call site was missed. Report either rather than fixing it silently.

- [ ] **Step 7: Commit**

```bash
git add source/Xcp_Pgm.c test/pgm_deferred_test.py test/pgm_session_test.py
git commit -m "$(cat <<'EOF'
fix: carry a detail WORD on the three PGM completion failures

Xcp_ProgramStart, Xcp_ProgramReset and Xcp_ProgramPrepare each answer
ERR_GENERIC when the integrator reports a non-zero status. All three
previously sent an identical two-byte packet, so a master could not tell
which callback had failed.

The integrator's own status byte is still discarded: interface/Xcp.h
documents it only as zero-success/non-zero-failure and constrains nothing
further, so forwarding it would publish a value this module neither defines
nor controls (DD121). What the master gains is which callback failed -- in
particular telling a PROGRAM_START refused by the module's own state gate
(0x0002) from one refused by the integrator (0x0003).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: The missing test for `0x0002`

`XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE` is the only one of the five with no dedicated test. The one place that observes the condition — `pgm_session_test.py:796`, inside `test_a_mid_session_synch_does_not_end_the_programming_session` — uses it incidentally to prove a session survived, and is **deliberately left alone**: its subject is `Xcp_PgmAbandonPendingCommand` and DD55, and coupling it to this vocabulary would make an unrelated test fail the next time this design changes.

**Files:**
- Modify: `test/pgm_session_test.py` — add one test

**Interfaces:**
- Consumes: `pgm_handle`, `program_start`, `transmitted`, `busy_then` — all four are already imported at `test/pgm_session_test.py:6`. `XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE` = `0x0002` (Task 1); the behaviour from Task 3.
- Produces: nothing.

- [ ] **Step 1: Write the test**

Append to `test/pgm_session_test.py`:

```python
def test_a_second_program_start_reports_the_session_already_active():
    """PROGRAM_START refused by this module's own `if (pgm_state != XCP_PGM_IDLE)` gate
    (source/Xcp_Pgm.c) carries XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE (0x0002), which is
    what distinguishes it from a PROGRAM_START the INTEGRATOR refused (0x0003,
    XCP_GENERIC_DETAIL_PROGRAM_START_FAILED). Both answer ERR_GENERIC and were previously
    indistinguishable on the wire -- the pair most likely to send a diagnosis to the wrong side of
    the interface. Design doc DD121, docs/superpowers/specs/2026-09-15-xcp-err-generic-detail-design.md.

    A real, completed PROGRAM_START is used to reach XCP_PGM_ACTIVE rather than asserting the state
    directly, for the reason test_program_reset_is_also_accepted_from_xcp_pgm_active gives above:
    Xcp_Internal is not reachable from this CFFI harness, so the state is only ever observable
    through behaviour."""
    handle = pgm_handle()
    busy_then(handle, 0x00, busy_calls=0)
    program_start(handle)
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0002, handle.define('E_OK'))

    handle.can_if_transmit.reset_mock()
    program_start(handle)
    handle.lib.Xcp_MainFunction()

    response = transmitted(handle)
    assert response[0:2] == (0xFE, 0x31), \
        'a second PROGRAM_START must be refused ERR_GENERIC, got {}'.format(response)
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0002, \
        'expected XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE, not the integrator-refusal code'
```

- [ ] **Step 2: Run it**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;second_program_start_reports" && cd .. && ./test.sh'
```

Expected: **PASS**. Task 3 already implemented the behaviour; this test exists because the condition had no coverage of its own, so it is a characterisation test and passes immediately. That is correct — do not modify production code to make it fail first.

If it **fails**, do not adjust the expected value to match. Either the setup does not reach `XCP_PGM_ACTIVE`, or Task 3's site is wrong; report which rather than fixing it.

- [ ] **Step 3: Full suite, then clear the cache**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: `100% tests passed, 0 tests failed out of 2`.

- [ ] **Step 4: Commit**

```bash
git add test/pgm_session_test.py
git commit -m "$(cat <<'EOF'
test: cover the already-active PROGRAM_START detail code

XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE was the only one of the five
detail codes with no test of its own. The sole place observing that
condition uses it incidentally to prove a session survived a SYNCH, and is
left untouched: its subject is Xcp_PgmAbandonPendingCommand and DD55, and
coupling it to this vocabulary would make an unrelated test fail whenever
this design changes.

Reaches XCP_PGM_ACTIVE through a genuinely completed PROGRAM_START rather
than asserting the state, since Xcp_Internal is not reachable from the CFFI
harness.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Close D17 in the roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` — the D17 entry's outcome blockquote, and §2.6's "Extended error payloads" row

**Interfaces:** none.

- [ ] **Step 1: Close the D17 entry**

Replace:

```markdown
> **Open.** Found while designing D6 (`2026-09-14-xcp-build-checksum-d6-design.md` §6).
```

with:

```markdown
> **Fixed.** All five sites answer through `Xcp_FillGenericErrorPacket` (`source/Xcp.c`), carrying
> one of five module-defined `XCP_GENERIC_DETAIL_*` codes (`interface/Xcp_Errors.h`). Design:
> `2026-09-15-xcp-err-generic-detail-design.md` (DD121–DD125).
>
> The integrator's own `pStatusCode` is deliberately **not** forwarded (DD121): `interface/Xcp.h`
> documents it only as zero-success/non-zero-failure and constrains nothing further, so putting it
> on the wire would publish a value this module neither defines nor controls. What the master gains
> is which condition fired — in particular telling a `PROGRAM_START` refused by the module's own
> state gate from one refused by the integrator.
```

- [ ] **Step 2: Update §2.6's row**

The "Extended error payloads" row currently ends by naming D17 as the remaining gap. Replace that trailing sentence — `One gap remains and is tracked as D17: ERR_GENERIC's own implementation-specific WORD is never attached at any of its five call sites.` — with:

```markdown
`ERR_GENERIC` attaches its own implementation-specific WORD at all five sites (`source/Xcp.c`'s `Xcp_FillGenericErrorPacket`, D17). Both payload-bearing codes 1.1/§1.1.3.3 defines are now implemented
```

- [ ] **Step 3: Verify no superseded phrasing survives**

```bash
grep -n 'tracked as D17\|never attached at any of its five call sites\|> \*\*Open\.\*\* Found while designing D6' docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
```

Expected: **no output**. Paste whatever it prints into your report, whether empty or not.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
git commit -m "$(cat <<'EOF'
docs: close D17 in the roadmap

Both payload-bearing error codes 1.1/1.1.3.3 defines are now implemented:
D6 closed ERR_OUT_OF_RANGE's DWORD, and this closes ERR_GENERIC's WORD.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Push and open the PR**

```bash
git push -u origin fix/xcp-err-generic-detail
gh pr create --base develop --head fix/xcp-err-generic-detail --title "fix: close D17 -- ERR_GENERIC's implementation-specific detail payload"
```

- [ ] **Read CI's verdict**

```bash
gh pr checks <N>
```

CI runs the full suite on the same Alpine image and is the authoritative verification.

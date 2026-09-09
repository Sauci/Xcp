# SP5-NV Implementation Plan — non-volatile DAQ storage

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept `SET_REQUEST`'s `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ`, hold and report the session configuration id, and read a stored id at start-up — without restoring DAQ lists, which belongs to RESUME.

**Architecture:** Four tasks. The two request bits and their polled callbacks come first, because they carry the denial-of-service hazard everything else is shaped around. The session configuration id follows, then the four read-only accessors the integrator uses to learn what to store, then the polled start-up read and the error it reports while outstanding.

**Tech Stack:** C (AUTOSAR-style, MISRA-leaning), Python 3.7 + pytest + CFFI, CMake, Jinja2 code generation, Docker.

**Spec:** `docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-design.md` (DD94–DD102)

## Global Constraints

- **`./test.sh` is the only authoritative run, and it MUST run in Docker.** On the host it dies at `cmake: not found`, and piping it reports the pipe's exit code — a failure can read as success:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
  ```
  `--user` is load-bearing: a root run leaves root-owned files under `build/` that later runs cannot delete, surfacing as a failing `Xcp_GateOnCompiles` with **no compile error in it**. Fix by deleting `build/` from a root container, not by debugging code.
- **Subset runs:** seed the CMake *cache* first, then run `./test.sh`:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project/build xcp-test:sp4b cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;set_request"
  ```
  **Clear it (`-DXCP_PYTEST_ARGS=""`) and run the full suite before finishing any task.** Baseline at branch point: **12976 passed, 29 skipped**, both ctest targets. A full clean run is ~7 minutes.
- **NEVER `rm -rf generated/*`** — it holds a tracked `generated/CMakeLists.txt`.
- **`Xcp_Internal` is NOT reachable from the CFFI harness.** `test/conftest.py` builds its cdef from `interface/Xcp.h` alone. Every assertion observes transmitted bytes or callback arguments. "Does not inspect internal state" is not a valid review finding.
- **Mutation verification per task**, and **per term** for compound conditions rather than per outcome.
- **If a pre-existing test outside your task's files fails, stop and report — do not adjust it.** Four tasks across the two predecessor branches hit exactly this; each needed a ruling, and one was resolved by changing a default rather than a test.
- End every commit message with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

**Protocol values, each read from the specification rather than recalled:**

| Thing | Value |
|---|---|
| `SET_REQUEST` request | `(0xF9, mode, WORD session_configuration_id)` in configured byte order |
| Mode bits | `STORE_CAL_REQ` `0x01`, `STORE_DAQ_REQ` `0x04`, `CLEAR_DAQ_REQ` `0x08` — already defined as `XCP_SESSION_STATUS_MASK_*` in `source/Xcp_Internal.h` |
| Unsupported mode | `XCP_E_ASAM_OUT_OF_RANGE` (0x22), per 1.0/§1.6.1.2.3 |
| `GET_STATUS` response | byte 1 session status, byte 2 protection status, bytes **4–5** session configuration id |
| Event codes | `EV_CLEAR_DAQ` **0x01**, `EV_STORE_DAQ` **0x02**, `EV_STORE_CAL` 0x03 (the last already defined as `XCP_EVENT_STORE_CAL`) |
| Read-window error | `XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` (**0x33**) — already defined in `interface/Xcp_Errors.h`, currently unused. In `GET_STATUS`'s **1.1** row only; 1.0 has no error codes for that command |
| `Xcp_OdtEntryType` | `uint32 *address; uint8 bitOffset; uint8 addressExtension; uint8 length; const uint8 number;` — already public in `interface/Xcp_Types.h` |

**Precedents to mirror rather than invent:**
- The polled store, and the exact shape to copy — `Xcp_MainFunction`'s `STORE_CAL_REQ` block in `source/Xcp.c` (search `XCP_SESSION_STATUS_MASK_STORE_CAL_REQ) != 0x00u`): callback returns `E_OK` → clear the bit → `Xcp_EventQueuePush(..., XCP_PID_EVENT, XCP_EVENT_STORE_CAL, &status, 1)` → set `event.successful_transmission_pending`.
- The query accessor — `Xcp_GetSegmentFreezeState` in `interface/Xcp.h`, including its doc-comment style.
- `CONNECT`'s request-bit reset — `Xcp_CTOCmdStdConnect` in `source/Xcp_Std.c`, added as DD77/R1.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `interface/Xcp.h` | three new callbacks, four accessors | 1, 3, 4 |
| `source/Xcp_Internal.h` | `session_configuration_id`, `nv_read` state, two event codes | 1, 2, 4 |
| `source/Xcp.c` | the poll sites in `Xcp_MainFunction`, `Xcp_CTOErrorMatrix[0xFD]` | 1, 4 |
| `source/Xcp_Std.c` | `SET_REQUEST`'s acceptance, `GET_STATUS` bytes 4–5 | 1, 2, 4 |
| `source/Xcp_Daq.c` | the four accessors' implementations | 3 |
| `config/xcp.schema.json`, `script/source_cfg.c.jinja2` | API enable flags | 1, 3, 4 |
| `test/daq_nv_storage_test.py` | **new** — tasks 1, 2, 4 | 1, 2, 4 |
| `test/daq_nv_accessor_test.py` | **new** — task 3 | 3 |

---

### Task 1: the two request bits and their polled callbacks

**Files:**
- Modify: `config/xcp.schema.json`, `script/source_cfg.c.jinja2`, `interface/Xcp.h`, `source/Xcp_Internal.h`, `source/Xcp_Std.c`, `source/Xcp.c`
- Test: `test/daq_nv_storage_test.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `Std_ReturnType Xcp_StoreDaqConfiguration(uint16 sessionConfigurationId, uint8 *pStatusCode)` and `Std_ReturnType Xcp_ClearDaqConfiguration(uint8 *pStatusCode)`, both polled from `Xcp_MainFunction`. Task 2 reads the id this task already passes to the store.

- [ ] **Step 1: Write the failing tests**

Create `test/daq_nv_storage_test.py`. Mirror `test/set_request_test.py` for handle construction and the `(0xF9, mode, 0x00, 0x00)` frame shape. Cover, each as its own test:

1. `SET_REQUEST` with `STORE_DAQ_REQ` (`0x04`) is accepted (`0xFF`), and a subsequent `Xcp_MainFunction` calls `Xcp_StoreDaqConfiguration`.
2. The same for `CLEAR_DAQ_REQ` (`0x08`) and `Xcp_ClearDaqConfiguration`.
3. A callback returning `E_NOT_OK` is polled again on the next `Xcp_MainFunction` and the request bit stays set — observe via `GET_STATUS` byte 1 still carrying the bit.
4. On completion (`E_OK`, zero status) the bit clears and the matching event is transmitted — `EV_STORE_DAQ` is `0x02`, `EV_CLEAR_DAQ` is `0x01`, carrying the status byte as payload exactly as `EV_STORE_CAL` does.
5. **The denial-of-service test (DD95), and the reason this task exists first.** A callback returning `E_OK` with a **non-zero** status code still clears the bit; assert a `DISCONNECT` immediately afterwards is answered `0xFF` and **not** refused `(0xFE, 0x12)` `ERR_PGM_ACTIVE`. Write this for `STORE_DAQ_REQ`, `CLEAR_DAQ_REQ`, and — as a regression pin on existing-but-untested behaviour (DD96) — `STORE_CAL_REQ`.
6. With the API flags disabled, `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` are still refused `(0xFE, 0x22)`.

- [ ] **Step 2: Run the subset and confirm every test fails**

Seed `-DXCP_PYTEST_ARGS="-k;daq_nv_storage"`, run `./test.sh`. Expected: all fail, most with `(0xFE, 0x22)` because `SET_REQUEST` still refuses both bits. Record what each did.

- [ ] **Step 3: Add the schema flags and generation**

Add `xcp_store_daq_configuration_api_enable` and `xcp_clear_daq_configuration_api_enable` beside the existing `xcp_*_api_enable` entries in `config/xcp.schema.json`, with the same `$ref`, and to that object's `required` list. Emit matching config fields in `script/source_cfg.c.jinja2`. Expect to touch `config/xcp.json`, `test/parameter.py` and `test/conftest.py` as well — every task on the predecessor branch did, and each was confirmed structurally required.

- [ ] **Step 4: Declare the callbacks**

In `interface/Xcp.h`, beside `Xcp_StoreCalibrationDataToNonVolatileMemory`, with doc comments stating the polled contract explicitly and — for the store — the two obligations DD97 places on the integrator: clear any existing stored configuration first, and commit the session configuration id **last**, so an interrupted store leaves no id.

- [ ] **Step 5: Widen `SET_REQUEST`'s acceptance**

In `source/Xcp_Std.c`, `Xcp_DTOCmdStdSetRequest` currently refuses any bit but `STORE_CAL_REQ`. Widen the accepted mask to include `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` **only when their API flags are enabled**, so an unconfigured build still answers `ERR_OUT_OF_RANGE` as 1.0/§1.6.1.2.3 prescribes.

- [ ] **Step 6: Add the two poll sites**

In `Xcp_MainFunction` (`source/Xcp.c`), beside the `STORE_CAL_REQ` block and copying its shape exactly (DD95's rule, which that block already implements — see DD96): callback returns `E_OK` → clear the bit → push the event with the status byte as payload → set `event.successful_transmission_pending` on a successful push. Add `XCP_EVENT_STORE_DAQ (0x02u)` and `XCP_EVENT_CLEAR_DAQ (0x01u)` to `source/Xcp_Internal.h` beside `XCP_EVENT_STORE_CAL`.

- [ ] **Step 7: Run the subset, then the full suite**

Expected: the new tests pass, full suite green at 12976 plus your new tests.

- [ ] **Step 8: Mutation-verify**

Three runs, restoring between each, recording which test failed:
1. Change the store's clear condition to also require a zero status code → test 5's `STORE_DAQ_REQ` case must fail.
2. Clear the bit on `E_NOT_OK` too → test 3 must fail.
3. Push the wrong event code (swap `0x01`/`0x02`) → test 4 must fail.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: accept STORE_DAQ_REQ and CLEAR_DAQ_REQ, with their request bits clearing on every exit"
```

---

### Task 2: the session configuration id

**Files:**
- Modify: `source/Xcp_Internal.h`, `source/Xcp_Std.c`, `source/Xcp.c`
- Test: `test/daq_nv_storage_test.py` (extend)

**Interfaces:**
- Consumes: Task 1's `Xcp_StoreDaqConfiguration(uint16 sessionConfigurationId, ...)`, whose first parameter this task starts populating from the request.
- Produces: `Xcp_Internal.session_configuration_id` (`uint16`), reported by `GET_STATUS` bytes 4–5. Task 4 writes it from the start-up read.

- [ ] **Step 1: Write the failing tests**

Extend `test/daq_nv_storage_test.py`:

1. `SET_REQUEST(STORE_DAQ_REQ, id = 0x1234)` passes `0x1234` to `Xcp_StoreDaqConfiguration` — assert the callback's argument, not merely that it was called.
2. After that store completes successfully, `GET_STATUS` bytes 4–5 report `0x1234` in the configured byte order.
3. A store that completes with a **non-zero** status leaves the reported id **unchanged** — set one id successfully, then attempt another that fails, and assert the first still reads back.
4. A successful `CLEAR_DAQ_REQ` resets the reported id to `0x0000` — DD98's postcondition, stated observably because the module never sees the integrator's NVM.
5. **`CONNECT` does not touch it.** Store an id, `CONNECT` again, and assert `GET_STATUS` still reports it. `CONNECT` clears the request *bits* (DD77/R1) and must leave the id standing — this is the assertion most likely to be broken later, because the instinct is to reset everything at the session boundary.

- [ ] **Step 2: Run the subset and confirm failure**

Expected: test 1 fails on the argument, 2–5 on `GET_STATUS` reporting the hardcoded `0x00, 0x00`.

- [ ] **Step 3: Add the field and populate it**

Add `uint16 session_configuration_id;` to `Xcp_Internal`, reset to `0` in `Xcp_Init`. In `Xcp_DTOCmdStdSetRequest`, stop ignoring bytes 2–3 — read them with `Xcp_CopyToU16WithOrder` (or the module's existing equivalent; match how `SET_MTA` reads its DWORD) into a pending field, and pass it to the store. Adopt it into `session_configuration_id` **only** when the store completes with a zero status; reset to `0` when a clear completes with a zero status. That is DD99's table of four writes; there is no fifth. No validation: the specification gives the id the full `uint16` range and reserves no values.

- [ ] **Step 4: Report it**

In `Xcp_CTOCmdStdGetStatus` (`source/Xcp_Std.c`), replace the hardcoded `0x00, 0x00` at bytes 4–5 — and the comment saying it is held in non-volatile memory — with the field, in the configured byte order.

- [ ] **Step 5: Run the subset, then the full suite**

- [ ] **Step 6: Mutation-verify**

Two runs, recording which test failed: adopt the id even when the store's status is non-zero → test 3 fails. Add `session_configuration_id = 0` to `CONNECT`'s teardown → test 5 fails.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: hold and report the session configuration id"
```

---

### Task 3: the four accessors

**Files:**
- Modify: `config/xcp.schema.json`, `script/source_cfg.c.jinja2`, `interface/Xcp.h`, `source/Xcp_Daq.c`
- Test: `test/daq_nv_accessor_test.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the four read-only accessors an integrator implementing `Xcp_StoreDaqConfiguration` calls to learn what to store.

```c
boolean        Xcp_GetDaqListSelectedState(uint16 daqListNumber);
uint8          Xcp_GetDaqListOdtCount(uint16 daqListNumber);
uint8          Xcp_GetOdtEntryCount(uint16 daqListNumber, uint8 odtNumber);
Std_ReturnType Xcp_GetOdtEntry(uint16 daqListNumber, uint8 odtNumber, uint8 odtEntryNumber,
                               Xcp_OdtEntryType *pEntry);
```

- [ ] **Step 1: Write the failing tests**

Create `test/daq_nv_accessor_test.py`. **Build the fixture under `DAQ_DYNAMIC` and configure the lists at runtime** — `FREE_DAQ`, `ALLOC_DAQ`, `ALLOC_ODT`, `ALLOC_ODT_ENTRY`, `SET_DAQ_PTR`, `WRITE_DAQ` — mirroring `test/daq_dynamic_acceptance_test.py`'s sequence. Under `DAQ_STATIC` these accessors would return generator constants and a broken implementation could still look right.

1. `Xcp_GetDaqListSelectedState` returns `FALSE` before, and `TRUE` after, `START_STOP_DAQ_LIST(Select)` on that list — and `FALSE` for a list that was never selected.
2. `Xcp_GetDaqListOdtCount` returns the count the master allocated with `ALLOC_ODT`.
3. `Xcp_GetOdtEntryCount` returns the count allocated with `ALLOC_ODT_ENTRY`, checked for **two ODTs with different counts**, so a handler returning the wrong ODT's count fails.
4. `Xcp_GetOdtEntry` returns the address, extension, length and bit offset a `WRITE_DAQ` configured — with **all four differing from their defaults**, so a partially-populated struct fails.
5. Out-of-range arguments are refused: a list number at or past the allocated count, an ODT past that list's count, an entry past that ODT's count. `Xcp_GetOdtEntry` answers `E_NOT_OK`; the counters answer `0`; `Xcp_GetDaqListSelectedState` answers `FALSE`, matching `Xcp_GetSegmentFreezeState`'s documented "FALSE otherwise or if the segment number is out of range".

- [ ] **Step 2: Run the subset and confirm failure**

Seed `-DXCP_PYTEST_ARGS="-k;daq_nv_accessor"`. Expected: all fail at link or attribute resolution, since the functions do not exist.

- [ ] **Step 3: Add the schema flag and generation**

`xcp_daq_nv_accessors_api_enable`, gating all four together — they exist to serve one caller and splitting them buys nothing.

- [ ] **Step 4: Declare and implement**

Declare in `interface/Xcp.h` with doc comments matching `Xcp_GetSegmentFreezeState`'s style, each stating what it returns for an out-of-range argument. Implement in `source/Xcp_Daq.c` beside the existing DAQ helpers, reading the runtime list state the module already holds — selection is `XCP_DAQ_LIST_MODE_SELECTED` in the list's mode byte.

- [ ] **Step 5: Run the subset, then the full suite**

- [ ] **Step 6: Mutation-verify**

Two runs: return the wrong ODT's entry count (use ODT 0 unconditionally) → test 3 fails. Drop `bitOffset` from `Xcp_GetOdtEntry`'s copy → test 4 fails.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: read-only accessors for storing a DAQ configuration"
```

---

### Task 4: the start-up read, and the error it reports while outstanding

**Files:**
- Modify: `config/xcp.schema.json`, `script/source_cfg.c.jinja2`, `interface/Xcp.h`, `source/Xcp_Internal.h`, `source/Xcp.c`, `source/Xcp_Std.c`
- Test: `test/daq_nv_storage_test.py` (extend)

**Interfaces:**
- Consumes: Task 2's `session_configuration_id`.
- Produces: `Std_ReturnType Xcp_ReadStoredSessionConfigurationId(uint16 *pSessionConfigurationId, uint8 *pStatusCode)` — polled from `Xcp_MainFunction` until it completes.

- [ ] **Step 1: Write the failing tests**

Extend `test/daq_nv_storage_test.py`:

1. The read is polled from `Xcp_MainFunction` and **retried** while it answers `E_NOT_OK` — a double answering `E_NOT_OK` for two calls and then `E_OK` with `0x4321` results in the id being adopted, observable through `GET_STATUS` bytes 4–5.
2. **While the read is outstanding, `GET_STATUS` answers `(0xFE, 0x33)`** `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE`, and answers normally once it completes. Both halves in one test, so the transition is what is pinned.
3. A read completing with a status code meaning "nothing stored" leaves the id at `0x0000` and `GET_STATUS` answering normally.
4. The read happens **once**: after it completes, further `Xcp_MainFunction` calls do not call it again.
5. With the API flag disabled there is no read, no window, and `GET_STATUS` answers normally from the first call.

- [ ] **Step 2: Run the subset and confirm failure**

- [ ] **Step 3: Declare the callback and add the state**

`xcp_read_stored_session_configuration_id_api_enable` in the schema plus generation; the declaration in `interface/Xcp.h` stating the polled contract (DD100 — polled rather than synchronous, because the module can neither verify nor enforce that `NvM_ReadAll` has run before `Xcp_Init`) and the three outcomes — `E_OK` with an id, `E_OK` with a "nothing stored" status, `E_NOT_OK` meaning not yet readable. Add a small state field to `Xcp_Internal` tracking whether the read is outstanding, complete, or not required.

- [ ] **Step 4: Poll it, and gate `GET_STATUS`**

Poll from `Xcp_MainFunction` while outstanding. In `Xcp_CTOCmdStdGetStatus`, answer `Xcp_FillErrorPacket(XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE, ...)` while the read is outstanding.

This is DD101. Add `XCP_INTERNAL_ERR_RES_TEMP_NOT_ACCESSIBLE` to `Xcp_CTOErrorMatrix[0xFD]`, which is `0x00u` today. Define the bit if the module has no constant for it. **This is declarative**, exactly as DD76 made `ERR_GENERIC` on `UNLOCK`'s row: only `CMD_BUSY`, `CMD_SYNTAX` and `PGM_ACTIVE` are behaviourally tested against that table. Comment it with the 1.1-only provenance — the code does not exist in 1.0, whose `GET_STATUS` row carries no error codes at all.

- [ ] **Step 5: Run the subset, then the full suite**

- [ ] **Step 6: Mutation-verify**

Two runs: make the read run once and give up on `E_NOT_OK` → test 1 fails. Answer `GET_STATUS` normally during the window → test 2 fails.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: read the stored session configuration id at start-up"
```

---

## Final verification

- [ ] Full `./test.sh` in the container on a clean build tree, both ctest targets green.
- [ ] Every mutation verification recorded, each naming the test that failed — including any honest negatives, reported rather than papered over.
- [ ] `RESUME_SUPPORTED` is still clear in `GET_DAQ_PROCESSOR_INFO` and `SET_DAQ_LIST_MODE` still refuses the RESUME bit (DD102) — assert it, since nothing else in this plan touches those and a reviewer should see it was checked rather than assumed.
- [ ] No DAQ list is restored at start-up: the read adopts the id and nothing else (DD102).
- [ ] Update `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`: SP5-NV complete, and correct the SP5 entry's dependency note. Fold into the final commit, matching PRs #5 and #8.

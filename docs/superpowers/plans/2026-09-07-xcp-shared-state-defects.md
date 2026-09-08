# Shared-State Defects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six pre-existing defects in shipped code — a memory disclosure, an authentication bypass, a key that is not bound to its seed, and three pieces of session state that survive `CONNECT`.

**Architecture:** Five of the six are two shapes. **Shape A** is a predicate answering a broader question than its reader asks — "a transfer is in progress" read as "*this kind* of transfer is in progress". **Shape B** is session state `CONNECT` does not reset, where `CONNECT` already clears `pgm_state` and `pgm_block` and nothing else. The sixth is a value written before the operation that justifies it and not rolled back when that operation fails.

**Tech Stack:** C (AUTOSAR-style BSW), Jinja2 code generation via `bsw_code_gen`, pytest + CFFI compiling the real sources, all inside `xcp-test:local` under Docker.

**Spec:** `docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md` — DD70 through DD75. Read it alongside this plan; where they disagree, the spec wins.

## Global Constraints

- **Every defect here is reproducible on the current code.** So every fix gets a test that **fails before it and passes after** — a test that cannot fail beforehand is not testing the defect. State the before-and-after for each in your report.
- **These are pre-existing defects, not SP4b's.** Say so in every commit message, in words `git log --grep` will find without knowing SP4b exists: they are being fixed on this branch by the maintainer's decision, and they affect shipped `DOWNLOAD`, `UPLOAD`, seed-and-key and session-teardown code.
- **The fixes narrow predicates and add resets. Both directions break neighbours.** Every task must test the neighbour it most endangers, named per task below.
- **No test may read `Xcp_Internal`** — `test/conftest.py` builds its cdef from `interface/Xcp.h` alone. Observe through consequences; `test/clear_daq_list_test.py:80-92` is the precedent.
- Citations are to **XCP Part 2 Protocol Layer Specification 1.1** unless they name 1.0, qualified `1.1/...`. Seed-and-key is §1.6.1.1.6 and §1.6.1.1.7; the PGM error matrix is §1.7.3.2.5 and §1.7.3.2.4 is DAQ's.
- **Every new test is mutation-verified**: break the term it targets, confirm that test fails and others do not, restore, confirm `git diff` is clean.

### Ten ways a test here has already passed while pinning nothing

Every one of these shipped in SP4a or SP4b and was caught in review. Check every assertion against all of them:

1. Asserting on `handle.can_if_transmit.call_args` without `reset_mock()` first — a **stale response** from an earlier exchange.
2. Asserting after only `Xcp_CanIfRxIndication`, **which never transmits** (`Xcp_StartNextTransmission` is called from two sites only).
3. Scanning `call_args_list` retrospectively — `Xcp_Internal.event.pdu_info` is one buffer reused across event types.
4. A setup guard satisfied by a leftover `CONNECT` response.
5. A deferral test discarding the value it meant to check.
6. An `exchange()`-style helper reading `call_args` without resetting.
7. A session helper that never resets, so a `SET_MTA` response satisfies a later assertion.
8. `transmitted(handle) is None` after a frame that never transmits.
9. A test whose name claims a property its assertions cannot fail on.
10. A guard satisfied by a same-shaped response from the previous exchange.

**One more is specific to this plan:** a test double that ignores the parameter under test. DD73 shipped precisely because the seed-key doubles ignore the length argument. A double that cannot observe the thing you are fixing cannot test it.

## How to run the tests

**`./test.sh` from the repo root is the only authoritative full run** — once, at the end, foreground, `XCP_PYTEST_ARGS` cleared, with `--ulimit nofile=65536:524288`:

```bash
docker run --rm --volume "$(pwd):/usr/project" --workdir /usr/project --ulimit nofile=65536:524288 xcp-test:local sh -c 'cd /usr/project/build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS= >/dev/null 2>&1; cd /usr/project && ./test.sh'
```

`test.sh` prunes stale `_cffi_xcp_*` directories; skipping that produces spurious "conflicting types for 'Xcp'" failures that look exactly like regressions. `XCP_PYTEST_ARGS` is a CMake *cache* variable, so a stale filter makes a "full" run report green having executed almost nothing. Filtered `ctest` is fine while iterating.

**Never `rm -rf generated/*`** — it holds build artefacts *and* the tracked `generated/CMakeLists.txt`. **Never background a run and wait on it.** Use `xcp-test:local` or build from the branch's own Dockerfile; `ghcr.io/sauci/xcp:develop` is too old. Docker here cannot bind-mount `/tmp`; work under `/home/sauci`.

**Baseline: 12863 passed, 29 skipped, 0 failed.** Measure it once before changing anything.

---

## File structure

| File | Change |
|---|---|
| `source/Xcp.c` | The block-transfer helpers (`Xcp_BlockTransferIsActive` unchanged; a new narrower predicate; `Xcp_BlockTransferAcknowledgeFrame`'s underflow), `Xcp_CanIfTxConfirmation`'s read, `last_pid`'s write. |
| `source/Xcp_Std.c` | `GET_SEED`'s resource assignment and seed length, `UNLOCK`'s admission test, `CONNECT`'s teardown, `GET_ID`'s MTA write. |
| `source/Xcp_Cal.c` | `DOWNLOAD`'s call into the shared initialiser, if it must pass a direction. |
| `source/Xcp_Internal.h` | The block-transfer state's direction, and any new predicate's declaration. |
| `test/stub/Xcp_SeedKey.h`, `test/conftest.py` | A seed-key double that **uses** the length parameter (DD73). |
| `test/block_transfer_disclosure_test.py` | **create** — DD70, DD71. |
| `test/seed_key_defects_test.py` | **create** — DD72, DD73. |
| `test/session_teardown_test.py` | **create** — DD74, DD75. |

---

## Task 1: DD70 and DD71 — the memory disclosure and its amplifier

**Files:** modify `source/Xcp.c`, `source/Xcp_Internal.h`, `source/Xcp_Std.c`, `source/Xcp_Cal.c`; create `test/block_transfer_disclosure_test.py`.

**Interfaces:**
- Produces: a narrower predicate — `Xcp_SlaveBlockTransferIsActive()` or equivalent — and a direction recorded in `Xcp_Internal.block_transfer`. Task 4 uses `Xcp_BlockTransferAbort()`, which already exists (`source/Xcp.c:2340`) and needs no change.

- [ ] **Step 1: Record the baseline** with `./test.sh`. Every later no-regression claim measures against that number.

- [ ] **Step 2: Write the failing tests.** Both must fail on the current code — run them and confirm before fixing anything.

The disclosure, which is the measured scenario from the spec:

```python
def test_confirming_a_response_during_a_download_block_does_not_disclose_slave_memory():
    """DD70. Xcp_CanIfTxConfirmation asks Xcp_BlockTransferIsActive() and, if true, continues the
    transfer by reading slave memory and transmitting it -- correct only for slave block mode, an
    UPLOAD, where the slave sends the frames. Xcp_DataTransferInitialize is shared with DOWNLOAD
    and records no direction, so an open master-block-mode DOWNLOAD satisfies the same predicate.

    Measured before the fix: seven slave-memory reads at 0x1006..0x100C and an unsolicited
    (0xFF, 0x5A x7) frame -- seven bytes of slave memory to a master that asked for nothing.

    GET_STATUS is the interloper because it is unconditionally available and has no side effects,
    so a failure here is about the confirmation path and nothing else."""
```

Assert **both** that no slave-memory read happened and that no frame was transmitted. Either alone is weaker than it looks: a fix that stopped the read but still transmitted, or transmitted an empty frame, would pass one of them.

The underflow (DD71): acknowledge more elements than are outstanding and assert the counter does not wrap. `Xcp_BlockTransferAcknowledgeFrame` (`source/Xcp.c:2452`) computes `requested_elements -= frame_elements` on a `uint8`; in the scenario above that is `4 - 6 = 254`. Observe it through consequences — the number of frames the runaway produces — since no test may read `Xcp_Internal`.

- [ ] **Step 3: Run them; confirm both fail**, and record the observed numbers. If either passes, the test is wrong, not the defect.

- [ ] **Step 4: Record the direction.** The call sites already know it — `UPLOAD` passes `slaveBlockModeSupported` (`source/Xcp_Std.c:727`), `DOWNLOAD` passes `masterBlockModeSupported` (`source/Xcp_Cal.c:95`) — so neither learns anything new. Add it to the state and to `Xcp_DataTransferInitialize`'s signature, or derive it at the call site; say which you chose and why.

- [ ] **Step 5: Narrow the confirmation's question only.** `source/Xcp.c:1948` uses the new predicate. **`Xcp_BlockTransferIsActive()` itself does not change** — `source/Xcp_Cal.c:30`, `:151` and `:206` legitimately ask the direction-agnostic "is a block open" for their `ERR_SEQUENCE` checks, and §1.6.2.2.1 requires that lost-packet detection. Narrowing it there breaks `DOWNLOAD_NEXT`.

- [ ] **Step 6: Guard the subtraction.** Refuse to acknowledge more elements than are outstanding.

- [ ] **Step 7: Test the neighbour this most endangers.** `UPLOAD`'s slave block mode must still chain frames across confirmations — that is exactly what a too-narrow predicate kills. Assert it explicitly rather than relying on the existing suite.

- [ ] **Step 8: Mutation-verify** each fix separately. **Step 9: `./test.sh`; commit**, with a message naming this a pre-existing disclosure in shipped `DOWNLOAD`/`UPLOAD` code.

---

## Task 2: DD72 — the authentication bypass

**Files:** modify `source/Xcp_Std.c`, `source/Xcp.c`; create `test/seed_key_defects_test.py`.

- [ ] **Step 1: Write the failing test.** `GET_SEED` for a protected resource, made to fail; then `UNLOCK`; then `GET_STATUS`. On the current code the resource is unlocked with no seed ever produced — measured as `GET_SEED → (0xFE, 0x22)`, `UNLOCK → (0xFF, 0x10)`, `GET_STATUS` reporting `0x10`. Run it and confirm it fails.

- [ ] **Step 2: Fix both legs.**
  - `Xcp_DTOCmdStdGetSeed` (`source/Xcp_Std.c:890`) assigns `requested_protected_resource` **before** calling `Xcp_GetSeed` and does not roll it back on failure. `Xcp_SetProtectionStatus` (`source/Xcp.c:2559`) later copies that field into `protection_status` verbatim.
  - `Xcp_DTOCmdStdUnlock` (`source/Xcp_Std.c:771`) admits a key when `last_pid` is `GET_SEED` or `UNLOCK`, reading it as "the previous command was a **successful** `GET_SEED`", while `source/Xcp.c:1833` writes `last_pid` for any *dispatched* command including one that errored.

- [ ] **Step 3: Prove both legs are load-bearing.** Revert each fix **alone** and confirm the test still fails. If reverting one leaves it passing, that leg is decoration and the pair is one fix with a spare — say so rather than shipping both. §1.6.1.1.7 makes `UNLOCK` meaningful only against a seed the slave actually issued.

- [ ] **Step 4: Test the neighbour.** A *legitimate* `GET_SEED`/`UNLOCK` sequence must still unlock, including a multi-frame seed and a multi-frame key. Tightening an admission test is exactly what breaks the working path.

- [ ] **Step 5: `./test.sh`; commit**, naming this an authentication bypass in shipped seed-and-key code.

---

## Task 3: DD73 — the key is not bound to the seed

**Files:** modify `source/Xcp_Std.c`, `test/stub/Xcp_SeedKey.h` and/or `test/conftest.py`; extend `test/seed_key_defects_test.py`.

- [ ] **Step 1: Give the double eyes.** The existing seed-key test doubles **ignore** the length parameter, which is why this shipped — a double that cannot observe the thing under test cannot test it. Make `Xcp_CalcKey`'s double record the `seedLength` it receives.

- [ ] **Step 2: Write the failing test.** Send a `GET_SEED`, complete the `UNLOCK`, and assert the double received the seed's **actual** length. On current code it receives `0` for every seed. Confirm it fails.

- [ ] **Step 3: Fix.** `Xcp_DTOCmdStdGetSeed` (`source/Xcp_Std.c:943`) sets `seed.total_length = 0x00u` when the final chunk goes out, meaning "no bytes left to send"; `Xcp_DTOCmdStdUnlock` (`source/Xcp_Std.c:805`) passes that same field to `Xcp_CalcKey` as the seed length. Keep the remaining-bytes bookkeeping in `current_index`, where it belongs, and leave `total_length` meaning what its name says.

- [ ] **Step 4: Test the neighbour.** A seed spanning **more than one frame** must still be transmitted correctly and completely — the field you are changing is what paces that. Assert the wire bytes across all frames, not just the length.

- [ ] **Step 5: Mutation-verify. Step 6: `./test.sh`; commit**, naming this a seed-and-key defect in shipped code: the key was computed from a zero-length seed, so it was not bound to the challenge.

---

## Task 4: DD74 — `CONNECT` must tear down the whole session

**Files:** modify `source/Xcp_Std.c`; create `test/session_teardown_test.py`.

**Interfaces:** consumes `Xcp_BlockTransferAbort()` (`source/Xcp.c:2340`, already exists) and Task 3's corrected seed fields.

- [ ] **Step 1: Write three failing tests**, one per surviving item, each across a real `DISCONNECT`/`CONNECT`:
  - **An open block survives.** On current code the `CONNECT` response is overwritten and never transmitted, and the new session opens with the slave streaming the previous session's memory.
  - **A partial key survives.** Session 1 announces an 8-byte key and delivers 6; after `DISCONNECT`, `CONNECT` and `GET_SEED`, an `UNLOCK` carrying **2** bytes completes the previous session's key and grants CAL_PAG.
  - **The MTA survives.** A `DOWNLOAD` with no `SET_MTA` writes at the previous session's address.

  Run all three; confirm all three fail.

- [ ] **Step 2: Fix.** `Xcp_CTOCmdStdConnect` (`source/Xcp_Std.c:1346-1358`) clears `pgm_state` and calls `Xcp_PgmBlockAbort()` and nothing else. Its own comment already argues that no state of the previous session may survive into the next — extend the teardown to the block transfer, both key buffers, the seed, and the MTA.

  On the MTA: §1.6.2 leaves it undefined until `SET_MTA`, so a master that omits it is not conformant — but the previous session's address is the most dangerous value an undefined pointer can hold. Reset it to a state the module **refuses to use** rather than to an address it will happily write, and say in a comment what you chose and why.

- [ ] **Step 3: Test the neighbour.** A normal session must still work end to end after a reconnect — `CONNECT`, `SET_MTA`, `DOWNLOAD`, `GET_SEED`/`UNLOCK` — because a teardown that clears too much breaks exactly that.

- [ ] **Step 4: Mutation-verify each item separately** — remove one reset at a time and confirm exactly its own test fails. **Step 5: `./test.sh`; commit.**

---

## Task 5: DD75 — `GET_ID` sets half a pointer

**Files:** modify `source/Xcp_Std.c`; extend `test/session_teardown_test.py` or create a small file.

- [ ] **Step 1: Write the failing test.** `SET_MTA` with address extension 7, then `GET_ID`, then `UPLOAD(3)`; assert the extension the integrator receives. On current code it is 7 — the previous command's.

- [ ] **Step 2: Fix.** `Xcp_DTOCmdStdGetId` (`source/Xcp_Std.c:1045`) writes `memory_transfer.address` and leaves `.extension` untouched, while every reader takes the pair (`source/Xcp.c:2488`, the checksum helpers). §1.6.1.2.2 has `GET_ID` point the MTA at the identification, which is a complete pointer. `Xcp_DTOCmdDaqGetDaqEventInfo` (`source/Xcp_Daq.c:1424-1425`) sets both and shows the intended contract.

- [ ] **Step 3: Mutation-verify. Step 4: `./test.sh`; commit.**

---

## Task 6: Acceptance, and keeping the audit true

**Files:** `test/` as needed; `docs/superpowers/specs/2026-09-07-xcp-shared-state-defects-design.md` is **mine** — do not edit it.

- [ ] **Step 1: Verify §5's acceptance criteria** one by one and report each honestly:
  1. Each of the six has a test that failed before its fix and passes after.
  2. `UPLOAD` slave block mode, `DOWNLOAD`/`DOWNLOAD_NEXT` master block mode, and the PGM block path all still work.
  3. A gate-off build is behaviourally unchanged and SP4b's property test still passes.
  4. No new instance of the ten traps.
  5. The commit messages identify these as pre-existing security fixes findable by `git log --grep`.

- [ ] **Step 2: Re-check the audit's "sound" list.** §3 of the spec records fields checked and found sound. Your fixes add writers and readers; confirm none of them makes a previously-sound field misinterpretable — in particular anything you touched in `Xcp_Internal`.

- [ ] **Step 3: Say what you could not discharge.** That matters more than a green run.

- [ ] **Step 4: `./test.sh`; commit.**

---

## Notes for the executor

- **`Xcp_Internal` is not reachable from the CFFI harness.** Every assertion is through consequences.
- **`connect_mode` and `event.successful_transmission_pending` are write-only dead state** — no reader anywhere. Do not add readers; if a fix seems to need one, you have taken a wrong turn.
- The commit messages matter more than usual here: these are security fixes landing on a feature branch by the maintainer's decision, and a future auditor must find them without knowing that.

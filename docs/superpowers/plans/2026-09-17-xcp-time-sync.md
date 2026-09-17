# EV_TIME_SYNC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An integrator entry point reporting an externally captured timestamp as `EV_TIME_SYNC` (1.1/§1.8.8).

**Architecture:** `Xcp_RaiseTimeSyncEvent(uint32 timestamp)` pushes six information bytes — two reserved, then the DWORD — through the userData path DD138 built, for an 8-byte packet. Declaration and definition both gated on `XCP_DAQ_TIMESTAMP_SUPPORTED`.

**Spec:** `docs/superpowers/specs/2026-09-17-xcp-time-sync-design.md` (DD154–DD157)

## Global Constraints

- Tests run in Docker only, `xcp-build:local`, ~7 min. Baseline **13066 passed, 29 skipped**, exit 0.
- The queue-full branch needs a test aimed at it; nothing reaches one by accident.
- Read a transmitted frame immediately after the `Xcp_MainFunction` that sent it, never from `call_args_list`.

---

### Task 1: The event

**Files:** `source/Xcp_Internal.h`, `interface/Xcp.h`, `source/Xcp.c`, `test/time_sync_test.py` (create)

- [ ] **Step 1:** Write the failing tests — wire layout in both byte orders, the integrator's value unmodified with `Xcp_GetDaqTimestamp` not called, the full 32 bits under a `ONE_BYTE` configuration, and the queue-full branch.
- [ ] **Step 2:** Run; expect FAIL (the symbol does not exist).
- [ ] **Step 3:** `XCP_EVENT_TIME_SYNC (0x08u)` in `source/Xcp_Internal.h`.
- [ ] **Step 4:** Declaration in `interface/Xcp.h` inside `#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)` (DD156), with the contract in the doc comment: same clock and units as `Xcp_GetDaqTimestamp()`, which the module cannot verify.
- [ ] **Step 5:** Definition in `source/Xcp.c` under the same gate, plus `#if (XCP_EVENT_USER_DATA_SIZE < 0x06u) #error` (DD157). Build `data[6]` = `{0x00, 0x00, <DWORD via Xcp_CopyFromU32WithOrder>}`, push under `SchM_Enter_Xcp_DtoQueue()`, report `XCP_E_EVENT_QUEUE_FULL` on failure with a new `XCP_RAISE_TIME_SYNC_EVENT_API_ID`.
- [ ] **Step 6:** Run the full suite; check `build/Xcp.c.gcov` for `#####` in the new function **before committing**.
- [ ] **Step 7:** Commit.

---

### Task 2: Roadmap

- [ ] Pass count; absent `EV_*` three → two; record DD154's width decision and that §1.8.8's table and prose disagree, so a reader does not "fix" it later.

---

## Verification before the PR

- [ ] Full suite at the final commit, 2/2 targets, exit 0; `git status` clean.
- [ ] No `#####` in the new function.

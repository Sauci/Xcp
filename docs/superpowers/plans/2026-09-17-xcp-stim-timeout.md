# EV_STIM_TIMEOUT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect a STIM DAQ list going unstimulated across N consecutive events and report it with `EV_STIM_TIMEOUT` (1.1/§1.8.9).

**Architecture:** A `fresh` flag per STIM slot, set on receive and cleared on apply; a `stimStaleEvents` counter per DAQ list runtime; an optional per-event-channel threshold. `Xcp_TriggerEventChannel` aggregates after its STIM apply loop and pushes the 6-byte event through the userData path DD138 built.

**Spec:** `docs/superpowers/specs/2026-09-17-xcp-stim-timeout-design.md` (DD149–DD153)

## Global Constraints

- **Tests run in Docker only**, image `xcp-build:local`, ~7 min:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
    --volume "$PWD:/usr/project" --workdir /usr/project xcp-build:local ./test.sh
  ```
- **Baseline:** 13057 passed, 29 skipped, 2/2 ctest targets, exit 0.
- **DD152's invariant:** a channel with no `stim_timeout_events` never reports. Every existing STIM test green unchanged is the evidence.
- **Two lessons that have each bitten once:** any queue-full branch needs a test aimed at it (nothing reaches one by accident), and a transmitted frame must be read immediately after the `Xcp_MainFunction` that sent it, never from `call_args_list` afterwards — the mock records a pointer into one reused buffer.

---

### Task 1: Freshness, the counter, and the threshold

**Files:** `interface/Xcp_Types.h`, `config/xcp.schema.json`, `script/source_cfg.c.jinja2`, `source/Xcp_DaqRuntime.c`, `test/parameter.py`

- [ ] **Step 1:** `Xcp_StimSlotType` gains `boolean fresh`; `Xcp_DaqListRtType` gains `uint16 stimStaleEvents`; the event channel config type gains `uint16 stimTimeoutEvents` (0 = never report).
- [ ] **Step 2:** Schema: optional `stim_timeout_events` on an events entry, integer minimum 1. Generator emits it, 0 when absent. `test/parameter.py`'s event helper gains the keyword, omitted when None.
- [ ] **Step 3:** Set `fresh = TRUE` beside `p_slot->length = payload_length` (`source/Xcp_DaqRuntime.c:984`), **inside the existing `SchM_Enter_Xcp_StimBuffer()` section** — DD37 put the payload and length there so no reader sees one without the other, and freshness is a third fact about the same slot. Clear it in `Xcp_DaqApplyStimOdt` under the same section it already takes.
- [ ] **Step 4:** Zero both new runtime fields wherever the STIM slots and DAQ list runtimes are initialised.
- [ ] **Step 5:** Run the full suite. Expect **13057 unchanged** — nothing reads the new state yet.
- [ ] **Step 6:** Commit.

---

### Task 2: Detection, aggregation and the event

**Files:** `source/Xcp_DaqRuntime.c`, `test/stim_timeout_test.py` (create)

- [ ] **Step 1: Write the failing tests.** A STIM list stale for exactly N events reports once, as `FD 09 01 00 <WORD list>` at `SduLength` 6; nothing at N-1; nothing again at N+1; fresh data resets and a second episode reports again. Read each frame immediately after its `Xcp_MainFunction`.
- [ ] **Step 2:** Run them. Expect FAIL — no event is raised at all.
- [ ] **Step 3:** `Xcp_DaqApplyStim` becomes `static boolean Xcp_DaqApplyStim(uint16 daqListNumber, boolean *pWasStim)`, returning whether the list was stale and reporting through `pWasStim` whether it was a STIM list at all. A non-STIM list is neither, and the two cannot be conflated — that distinction is what DD151's "every STIM list on the channel" needs.
- [ ] **Step 4:** In `Xcp_TriggerEventChannel`'s STIM loop, accumulate `stim_count` and `stale_count`, update each stale list's `stimStaleEvents` (saturating at `0xFFFFu`) and reset it to 0 when fresh.
- [ ] **Step 5:** After the loop, when the channel's `stimTimeoutEvents` is non-zero, emit per DD151: if `stale_count == stim_count` and `stim_count > 0` and any stale list's counter **equals** the threshold, push one Info Type 0 event carrying the channel number; otherwise push one Info Type 1 event per stale list whose counter equals the threshold. Equality, not `>=`, is what makes each episode report once (DD153).
- [ ] **Step 6:** Build the four information bytes — Info Type, `0x00u` reserved, then the WORD via `Xcp_CopyFromU16WithOrder` in the configured byte order — and push with `Xcp_EventQueuePush(..., XCP_PID_EVENT, XCP_EVENT_STIM_TIMEOUT, data, 0x04u)` inside `SchM_Enter_Xcp_DtoQueue()`, reporting `XCP_E_EVENT_QUEUE_FULL` to Det on failure.
- [ ] **Step 7:** Add `XCP_EVENT_STIM_TIMEOUT (0x09u)` to `source/Xcp_Internal.h`.
- [ ] **Step 8:** Run the full suite.
- [ ] **Step 9:** Commit.

---

### Task 3: The aggregation rule, opt-in, and the queue-full branch

**Files:** `test/stim_timeout_test.py`

- [ ] **Step 1:** Tests for: every STIM list stale → one Info Type 0 with the channel number and no per-list report; one stale of two → one Info Type 1 with that list's number and no channel report; a partially-refreshed list is not stale and its counter resets (DD150); a channel with no threshold never reports (DD152); a stale list still applies its latched values (DD35 unchanged); byte order honoured for the WORD; and the queue-full path returning `E_NOT_OK` with `XCP_E_EVENT_QUEUE_FULL`.
- [ ] **Step 2:** Run the full suite; check `build/Xcp_DaqRuntime.c.gcov` for `#####` in new code **before committing**.
- [ ] **Step 3:** Commit.

---

### Task 4: Roadmap

- [ ] Pass count; `EV_*` absent count four → three, naming `Xcp_TriggerEventChannel` as the detector and the design doc; note that §1.8.9's Info Type 1 was recovered from the PDF text layer because the OCR omits it.

---

## Verification before the PR

- [ ] Full suite at the final commit, 2/2 targets, exit 0; `git status` clean; `XCP_PYTEST_ARGS` empty.
- [ ] No `#####` in new code in `build/Xcp_DaqRuntime.c.gcov`.

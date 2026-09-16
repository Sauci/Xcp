# CTO Response Invariant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it structurally impossible for `Xcp_CanIfRxIndication` to transmit a CTO response buffer that no handler wrote.

**Architecture:** `Xcp_FinalizeResPacket` is the sole writer of the CTO buffer's `SduLength`, and no legal response finalizes at 0. So `Xcp_CanIfRxIndication` clears `SduLength` to 0 once at the top of the CTO arm, and a single new helper — the only code that sets `successful_transmission_pending` — treats a surviving 0 as a broken invariant, answering `ERR_GENERIC` with a new detail WORD and reporting to Det.

**Tech Stack:** C (AUTOSAR MISRA style), pytest + CFFI compiling the real C, CMake/ctest, Docker.

**Spec:** `docs/superpowers/specs/2026-09-16-xcp-cto-response-invariant-design.md` (DD132–DD136)

## Global Constraints

- **Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. Every citation in a comment carries its revision prefix, e.g. `1.1/1.1.3.3`.
- **Tests run in Docker only.** The image is `xcp-build:local` (not `ghcr.io/sauci/xcp:develop`, which ships CMake 3.14.5 against a 3.19 floor and dies at configure). Canonical invocation:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
    --volume "$PWD:/usr/project" --workdir /usr/project xcp-build:local ./test.sh
  ```
  A full run is ~7 minutes. `XCP_PYTEST_ARGS` is a CMake **cache** variable — passing it as `--env` to `docker run` is silently ignored.
- **Baseline pass count:** 12948 passed, 29 skipped, 2/2 ctest targets, exit 0. Every task states its expected new count.
- **New identifiers:** `XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN` = `0x0007`; `XCP_E_RESPONSE_NOT_WRITTEN` = `0x0B`. Low Det values are not refilled (`XCP_E_EVENT_QUEUE_FULL` at `0x04` collides with AUTOSAR's `XCP_E_INIT_FAILED`).
- **Do not rewrite the six historical design documents.** DD132 corrects only the four comments in `source/`.

---

## File Structure

| File | Responsibility | Change |
|:--|:--|:--|
| `interface/Xcp_Errors.h` | ASAM + generic detail codes | add `XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN` |
| `interface/Xcp.h` | Det error ids | add `XCP_E_RESPONSE_NOT_WRITTEN` |
| `source/Xcp.c` | dispatch + transmit | add `Xcp_QueueCtoResponse`, the sentinel clear, replace 3 assignment sites |
| `source/Xcp_Std.c` | STD handlers | DD132 comment corrections (3 sites) |
| `source/Xcp_Daq.c` | DAQ handlers | DD132 comment correction (1 site) |
| `test/cto_response_invariant_test.py` | new | the guard's own tests + the PID sweep + the finalize-never-zero pin |
| `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` | roadmap | pass count, defect-family note |

---

### Task 1: Funnel the transmit flag through one helper

Pure refactor. No behaviour change, no new test — the existing 12948 are the test.

**Files:**
- Modify: `source/Xcp.c:112` (forward declaration), `source/Xcp.c` near `Xcp_TransmitOneFrame`'s definition (body), `source/Xcp.c:2060`, `:2222`, `:2237` (call sites)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `static void Xcp_QueueCtoResponse(const boolean responseExpected)` — file-local to `Xcp.c`, the only code that assigns `Xcp_Internal.cto_response.successful_transmission_pending` outside `Xcp_Init` and `Xcp_CanIfTxConfirmation`. Task 2 adds the guard inside it.

- [ ] **Step 1: Add the forward declaration**

In `source/Xcp.c`, beside the existing `static void Xcp_TransmitOneFrame(void);` at line 112:

```c
/* DD134. The one place cto_response.successful_transmission_pending is set from a dispatch
 * outcome. It had three call sites that had to agree and nothing said so; a fourth could have
 * been added without noticing. Task 2 gives it the invariant check, which is the reason it
 * exists at all. */
static void Xcp_QueueCtoResponse(const boolean responseExpected);
```

- [ ] **Step 2: Add the body**

Immediately after `Xcp_TransmitOneFrame`'s definition. Note the assignment is unconditional — it must set the flag FALSE as well as TRUE, because that is what the three sites it replaces did, and a `responseExpected` of FALSE arriving while a previous response is still queued cancels that response today:

```c
static void Xcp_QueueCtoResponse(const boolean responseExpected)
{
    Xcp_Internal.cto_response.successful_transmission_pending = responseExpected;
}
```

- [ ] **Step 3: Replace the three call sites**

Each of `source/Xcp.c:2060`, `:2222` and `:2237` currently reads:

```c
                                        Xcp_Internal.cto_response.successful_transmission_pending = response_expected;
```

Replace each with, at that site's own indentation:

```c
                                        Xcp_QueueCtoResponse(response_expected);
```

Leave every surrounding comment as it is. The comment at `:2231` describing why the disabled-command arm sets the flag stays accurate.

- [ ] **Step 4: Run the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --volume "$PWD:/usr/project" --workdir /usr/project xcp-build:local ./test.sh
grep -E "passed|tests passed" build/Testing/Temporary/LastTest.log | tail -2
```

Expected: `12948 passed, 29 skipped`, `100% tests passed, 0 tests failed out of 2`. An unchanged count is the point — this task changes no behaviour.

- [ ] **Step 5: Commit**

```bash
git add source/Xcp.c
git commit -m "refactor: funnel the CTO transmit flag through one helper (DD134)"
```

---

### Task 2: The sentinel and the guard

**Files:**
- Modify: `interface/Xcp_Errors.h` (after `XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG`, before the `#endif`), `interface/Xcp.h` (after `XCP_E_USER_CMD_RESPONSE_TOO_LONG`, before `/** @} */`), `source/Xcp.c:1926` and `Xcp_QueueCtoResponse`'s body
- Test: `test/cto_response_invariant_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_QueueCtoResponse` from Task 1.
- Produces: `XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN` (`0x0007`), `XCP_E_RESPONSE_NOT_WRITTEN` (`0x0B`) — Tasks 3 and 4 assert against both.

- [ ] **Step 1: Write the failing test**

Create `test/cto_response_invariant_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest


def test_a_zero_length_user_cmd_response_is_refused_rather_than_transmitted():
    """DD136. Xcp_DTOCmdStdUserCmd finalizes at whatever length the integrator's callback set, and
    DD129 bounded that only from above. A callback returning E_OK with SduLength 0 therefore reached
    Xcp_FinalizeResPacket(0, ...) and was transmitted as a frame with no readable PID.

    This is also the live path that makes the invariant guard a reachable branch rather than the
    kind of unenterable guard DD126 records this project deleting twice: it needs no handler defect,
    only an integrator mistake."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = 0x00
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT -- loads the shared buffer with an 8-byte positive answer.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD, whose callback writes nothing and claims length 0.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4])

    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0007, \
        'expected XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN'
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_RESPONSE_NOT_WRITTEN'))
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --volume "$PWD:/usr/project" --workdir /usr/project xcp-build:local ./test.sh
grep -n "zero_length_user_cmd" -A 12 build/Testing/Temporary/LastTest.log | tail -20
```

Expected: FAIL. The failure should be on `SduLength == 4` reporting `0`, or on `handle.define('XCP_E_RESPONSE_NOT_WRITTEN')` raising because the identifier does not exist yet. Either is the right failure — the feature is missing. If it fails on something else, stop and read it.

- [ ] **Step 3: Add the generic detail code**

In `interface/Xcp_Errors.h`, after `XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG`'s `#define` and before the closing `#endif`:

```c
/**
* @brief The dispatched command produced no response at all: Xcp_CanIfRxIndication finished with
* response_expected TRUE while cto_response.pdu_info.SduLength was still the 0 written before
* dispatch. The shared response buffer is zero-initialised only at Xcp_Init, so without this
* refusal the previous command's answer would be transmitted under this command's request -- the
* defect D2, D7, DD76 and D18's Finding 4 each produced once (DD133).
 */
#define XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN (0x0007u)
```

- [ ] **Step 4: Add the Det error id**

In `interface/Xcp.h`, after `XCP_E_USER_CMD_RESPONSE_TOO_LONG`'s `#define` and before the trailing `/** @} */`:

```c
/**
 * @brief A dispatched command left the response buffer unwritten.
 * @details The master is answered ERR_GENERIC carrying
 * @ref XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN. XCP part 2 - Protocol Layer Specification
 * 1.1/1.1.3.3 defines that detail WORD as "an implementation specific slave device error code",
 * which is what an unwritten response buffer is.
 * @note This error is not part of the specification. It reports a defect in this module or a
 * zero-length response from the integrator's Xcp_UserCmdFunction (DD136). 0x0B continues DD131's
 * practice of not refilling low values, XCP_E_EVENT_QUEUE_FULL already colliding with AUTOSAR's
 * XCP_E_INIT_FAILED at 0x04. DD135.
 */
#define XCP_E_RESPONSE_NOT_WRITTEN (0x0Bu)
```

- [ ] **Step 5: Clear the sentinel before anything can fill the buffer**

In `source/Xcp.c`, immediately after `pid = pPduInfo->SduDataPtr[0x00u];` (line 1926) and before the `if ((pid == XCP_PID_CMD_CONNECT) || ...)` that follows:

```c
                        /* DD133. The sentinel the invariant rests on. Xcp_FinalizeResPacket is the
                         * only code that assigns this field for the CTO buffer and no legal
                         * response finalizes at 0, so a surviving 0 below means nothing wrote a
                         * response -- and the buffer still holds the PREVIOUS command's answer,
                         * which is what would go out instead.
                         *
                         * Cleared here rather than immediately before the dispatch call so that
                         * every path able to reach a transmission is covered: the pending-command
                         * ERR_CMD_BUSY gate, ERR_PGM_ACTIVE, ERR_CMD_SYNTAX, ERR_ACCESS_LOCKED,
                         * the disabled-command ERR_CMD_UNKNOWN arm and the handler itself. All of
                         * those fill, so none should ever trip the check in Xcp_QueueCtoResponse;
                         * the point is that they are covered by construction rather than by having
                         * been read once.
                         *
                         * This does not endanger a response already queued and awaiting
                         * TxConfirmation: a second command arriving in that window overwrites the
                         * buffer through its own handler's fill today, so the pending response is
                         * already lost by then. The clear adds no hazard that the fill does not. */
                        Xcp_Internal.cto_response.pdu_info.SduLength = 0x00u;
```

- [ ] **Step 6: Put the check in the helper**

Replace `Xcp_QueueCtoResponse`'s body from Task 1 with:

```c
static void Xcp_QueueCtoResponse(const boolean responseExpected)
{
    /* DD133/DD134. responseExpected FALSE means the command legitimately produces no response --
     * the deferred PGM handlers, which answer later from Xcp_MainFunction -- so the buffer is not
     * examined and the assignment below simply records it, as all three replaced sites did.
     *
     * responseExpected TRUE with SduLength still 0 means the invariant is broken: something was to
     * be transmitted and nothing wrote it. ERR_GENERIC is what 1.1/1.1.3.3 provides for an
     * implementation specific slave device error, and 1.1/1.7.3.2.1 not listing it for every
     * command is not a departure -- 1.1/1.7.3 tells the master to fall back to the code's severity,
     * which for ERR_GENERIC is S2 and in the matrix rows that do list it means "restart session".
     * That is the right outcome for a slave that just failed to answer (DD132, DD135).
     *
     * The guard is self-satisfying: Xcp_FillGenericErrorPacket finalizes through
     * Xcp_FinalizeResPacket like any other response, so SduLength is 4 by the time the flag is
     * set. */
    if ((responseExpected == TRUE) && (Xcp_Internal.cto_response.pdu_info.SduLength == 0x00u))
    {
        Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN,
                                   &Xcp_Internal.cto_response.pdu_info);

        Xcp_ReportError(0x00u, XCP_CAN_IF_RX_INDICATION_API_ID, XCP_E_RESPONSE_NOT_WRITTEN);
    }

    Xcp_Internal.cto_response.successful_transmission_pending = responseExpected;
}
```

- [ ] **Step 7: Run the full suite**

Same command as Task 1 Step 4.

Expected: `12949 passed, 29 skipped` (12948 + 1), both ctest targets, exit 0.

If any pre-existing test now fails, do not adjust the guard to accommodate it — read the failure. A pre-existing test failing here means a handler path returns "respond" having written nothing, which is exactly what this sub-project exists to find. Record it, fix that handler, and note it in the design doc's §4.

- [ ] **Step 8: Commit**

```bash
git add interface/Xcp_Errors.h interface/Xcp.h source/Xcp.c test/cto_response_invariant_test.py
git commit -m "fix: refuse to transmit a CTO response no handler wrote (DD133, DD135, DD136)"
```

---

### Task 3: The PID sweep — the audit, done empirically

**Files:**
- Modify: `test/cto_response_invariant_test.py`

**Interfaces:**
- Consumes: `XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN` from Task 2.
- Produces: nothing later tasks consume.

- [ ] **Step 1: Write the sweep**

Append to `test/cto_response_invariant_test.py`:

```python
@pytest.mark.parametrize('pid', range(0xC0, 0x100))
def test_no_command_transmits_the_response_not_written_packet(pid):
    """The per-path audit. The sweep behind D18's Finding 4 counted fill calls per FUNCTION, which
    established that USER_CMD's NULL_PTR branch was broken but not that the other 53 handlers are
    sound. This drives every command PID through a connected session and asserts the guard never
    fires -- so a handler path that returns 'respond' having written nothing shows up here.

    0xC0..0xFF is the command space: 1.1/1.1.5.1 fixes commands at 0xC0 and above, which is the
    range Xcp_PIDTable dispatches (D7)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    # CONNECT -- loads the shared buffer, so a handler that writes nothing replays this.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4])

    if response[0:2] == (0xFE, 0x31):
        detail = u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN')
        assert detail != 0x0007, \
            'PID 0x%02X returned responseExpected TRUE having written no response' % pid
```

Add `import pytest` to the file's imports.

- [ ] **Step 2: Run it**

Same full-suite command.

Expected: `13013 passed, 29 skipped` (12949 + 64). If any parametrisation fails, that is a real find — it names the PID whose handler path is broken. Fix that handler on this branch and record it in the design doc's §4 before continuing.

- [ ] **Step 3: Commit**

```bash
git add test/cto_response_invariant_test.py
git commit -m "test: sweep every command PID for an unwritten response"
```

---

### Task 4: Pin the sentinel's premise

**Files:**
- Modify: `test/cto_response_invariant_test.py`

- [ ] **Step 1: Write the test**

Append:

```python
def test_a_legal_response_never_finalizes_at_length_zero():
    """DD133 rests on 0 being an impossible length for a real response, which is what makes the
    sentinel readable as 'nothing was written'. If a future handler finalizes a legal response at 0,
    the guard would start refusing it -- so that change must break a test here rather than surface
    as an unexplained ERR_GENERIC on the bus.

    GET_STATUS is the probe: an ordinary positive response with a fixed layout, chosen because it
    needs no configuration beyond a connected session."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.can_if_transmit.call_args[0][1].SduLength > 0
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0x00u] == 0xFF, 'positive response'
```

- [ ] **Step 2: Run the full suite**

Expected: `13014 passed, 29 skipped`.

- [ ] **Step 3: Commit**

```bash
git add test/cto_response_invariant_test.py
git commit -m "test: pin that no legal response finalizes at length zero"
```

---

### Task 5: DD132 — correct the four comments in `source/`

Documentation only. No behaviour change, no count change.

**Files:**
- Modify: `source/Xcp_Std.c:384`, `source/Xcp_Std.c:444`, `source/Xcp_Std.c:1022`, `source/Xcp_Daq.c:1442`

Do **not** touch the six design documents listed in the spec's DD132 table — they are dated records and this project appends corrections to such records rather than rewriting them.

- [ ] **Step 1: `source/Xcp_Std.c`, the DD130 comment (lines 384-389)**

Line 384 reads exactly:

```c
         * ERR_GENERIC is a deliberate deviation: 1.1/1.7.3.2.1's USER_CMD row lists ERR_CMD_BUSY,
```

Replace that one line with:

```c
         * ERR_GENERIC is not listed by 1.1/1.7.3.2.1's USER_CMD row, which lists ERR_CMD_BUSY,
```

Then lines 386-388 read exactly (note the sentence wraps across all three):

```c
         * usable ones blames the master's own request for what the slave's extension did. DD57
         * (PROGRAM_RESET) and DD76 (UNLOCK) took the same deviation for the same reason; DD130
         * records this as the third.
```

Replace those three lines with:

```c
         * usable ones blames the master's own request for what the slave's extension did. DD57
         * (PROGRAM_RESET) and DD76 (UNLOCK) answer off-row for the same reason. All three were
         * called deliberate deviations until DD132: 1.1/1.7.3 anticipates an off-row code and
         * tells the master to fall back to the code's severity, so the behaviour is inside the
         * protocol. What it costs is only that the master gets severity-level guidance instead of
         * this row's own Pre-Action/Action pair.
```

- [ ] **Step 2: `source/Xcp_Std.c`, the Finding 4 comment (lines 443-444)**

Those two lines read exactly (the sentence wraps across both):

```c
         * that command, and Xcp_PIDTable's own 0xF1 row marks it optional -- so this needs no
         * deviation, unlike the ERR_GENERIC one DD130 took for the over-long response above.
```

Replace both with:

```c
         * that command, and Xcp_PIDTable's own 0xF1 row marks it optional -- so this answer is on
         * ERR_CMD_UNKNOWN's own row, where DD130's ERR_GENERIC above is not. Neither is a
         * departure from the specification (DD132); this one simply carries the master a specific
         * Action rather than a severity to interpret.
```

- [ ] **Step 3: `source/Xcp_Std.c:1022`**

Replace `The same deviation is kept: XCP_E_ASAM_GENERIC, matching` with:

```c
                         * The same off-row answer is kept: XCP_E_ASAM_GENERIC, matching
```

- [ ] **Step 4: `source/Xcp_Daq.c:1442`**

Replace `A deliberate deviation, not an oversight: 1.7.3.2.4's READ_DAQ row does not list` with:

```c
     * Off-row and deliberate, not an oversight: 1.7.3.2.4's READ_DAQ row does not list
```

- [ ] **Step 5: Run the full suite**

Expected: `13014 passed, 29 skipped`, unchanged from Task 4 — comments only.

- [ ] **Step 6: Commit**

```bash
git add source/Xcp_Std.c source/Xcp_Daq.c
git commit -m "docs: an off-row error code is not a deviation (DD132)"
```

---

### Task 6: Roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md:53` and §3

- [ ] **Step 1: Update the pass count**

Line 53 currently reads `12948 passing, 29 skipped`. Change to `13014 passing, 29 skipped`.

- [ ] **Step 2: Record the sub-project**

Append to §3, after the D18 entry's Finding 4 paragraph:

```markdown
> **The family behind that finding is now closed by construction (2026-09-16).** D2, D7, DD76
> (`UNLOCK` retransmitting the previous `GET_SEED` response) and Finding 4 were four instances of
> one missing invariant: `Xcp_CanIfRxIndication` queued the shared CTO buffer for every dispatch
> outcome, whether or not a handler wrote it. `Xcp_CanIfRxIndication` now clears
> `cto_response.pdu_info.SduLength` before dispatch and `Xcp_QueueCtoResponse` refuses to transmit a
> surviving 0, answering `ERR_GENERIC` with `XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN` and reporting
> `XCP_E_RESPONSE_NOT_WRITTEN`. Design:
> `docs/superpowers/specs/2026-09-16-xcp-cto-response-invariant-design.md` (DD132-DD136). A sweep of
> every command PID asserts the guard never fires on a legal path.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
git commit -m "docs: record the CTO response invariant in the roadmap"
```

---

## Verification before the PR

- [ ] Full suite in Docker at the final commit: `13014 passed, 29 skipped`, `100% tests passed, 0 tests failed out of 2`, exit 0.
- [ ] `git status --porcelain` clean.
- [ ] If Task 2 Step 7 or Task 3 Step 2 found a broken handler path, the design doc's §4 records which and what was done.

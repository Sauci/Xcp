# SP5-RESUME Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A slave that restores a stored DAQ configuration at start-up and transmits it with no master session, reporting RESUME mode where the specification says to.

**Architecture:** The integrator pushes the stored configuration back through `Xcp_Restore*` setters — the mirror of SP5-NV's accessors — and commits it with `Xcp_ResumeComplete`, which is the only thing that makes any of it live. Nothing on the wire changes until Task 4, so no commit on this branch advertises or accepts a capability the code behind it does not yet have.

**Tech Stack:** C (AUTOSAR-style BSW module), CFFI + pytest harness, CMake/ctest in Docker, Jinja2 configuration generator.

**Spec:** `docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md` (DD103–DD107)

## Global Constraints

- **Reference revision is 1.1.** Read a command's section in **both** revisions before implementing it — for renumbering, for error codes 1.1 adds, **and for added mode bits or changed flag semantics**. See the roadmap preamble's revision rule; three defects came from missing that last part.
- **When a task makes a previously-refused command or mode acceptable, re-read every section that mentions it.** A requirement that was vacuous because nothing could reach it goes live at that moment and will not appear in the diff.
- Citations carry their revision prefix — `1.1/1.6.4.1.1.4`, never a bare section number.
- `Xcp_Internal` and file-`static` tables are **not reachable from the CFFI harness** (`test/conftest.py` builds its cdef from `interface/Xcp.h` alone). Assertions observe transmitted bytes, callback arguments, or exported return values.
- `Xcp_GeneralType` is initialised **positionally** by `script/source_cfg.c.jinja2`. Any new field is appended strictly at the tail of both the struct and the initialiser.
- The module has **two DAQ mode layouts**: `XCP_DAQ_LIST_MODE_*` (the `GET_DAQ_LIST_MODE` response — SELECTED 0, DIRECTION 1, TIMESTAMP 4, PID_OFF 5, RUNNING 6, RESUME 7) and `XCP_DAQ_LIST_MODE_REQ_*` (the `SET_DAQ_LIST_MODE` request — ALTERNATING 0, DIRECTION 1, TIMESTAMP 4, PID_OFF 5). `Xcp_DaqListRtType::mode` stores the **response** layout.
- Every assertion must be able to fail. An expected value coinciding with a default proves nothing.
- `./test.sh` runs **only** in Docker:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 \
    --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
  ```
  `--user` is load-bearing. `XCP_PYTEST_ARGS` is a CMake **cache** variable — clear it to `""` when done. Never `rm -rf generated/*`. Baseline at branch point: **12932 passed, 29 skipped**.

---

### Task 1: the restore setters and the commit

**Files:**
- Modify: `interface/Xcp.h`, `source/Xcp_Internal.h`, `source/Xcp_Daq.c`
- Test: `test/daq_resume_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_OdtEntryType` (`interface/Xcp_Types.h`), `Xcp_DaqListRt` and `Xcp_DaqListIsValid` (`source/Xcp_Daq.c`), `Xcp_Internal.allocated_daq_count`.
- Produces:
  ```c
  Std_ReturnType Xcp_RestoreDaqListCount(uint16 daqListCount);
  Std_ReturnType Xcp_RestoreOdtCount(uint16 daqListNumber, uint8 odtCount);
  Std_ReturnType Xcp_RestoreOdtEntryCount(uint16 daqListNumber, uint8 odtNumber, uint8 entryCount);
  Std_ReturnType Xcp_RestoreOdtEntry(uint16 daqListNumber, uint8 odtNumber, uint8 odtEntryNumber,
                                     const Xcp_OdtEntryType *pEntry);
  Std_ReturnType Xcp_RestoreDaqListMode(uint16 daqListNumber, uint8 mode, uint16 eventChannelNumber,
                                        uint8 prescaler, uint8 priority);
  Std_ReturnType Xcp_ResumeComplete(uint16 sessionConfigurationId);
  ```
  plus `Xcp_Internal.resume_state` of a new enum `Xcp_ResumeStateType { XCP_RESUME_IDLE = 0x00u, XCP_RESUME_RESTORING, XCP_RESUME_ACTIVE }`.

- [ ] **Step 1: Write the failing tests**

Create `test/daq_resume_test.py`. Build under `DAQ_DYNAMIC` — a static build's lists are generated, so a broken setter could still look right.

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SP5-RESUME (design doc DD103-DD107, docs/superpowers/specs/2026-09-10-xcp-daq-resume-design.md).

The Xcp_Restore* setters are the mirror of SP5-NV's four accessors: the integrator pushes back what
it stored, and Xcp_ResumeComplete is the only thing that makes any of it live (DD105)."""

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def restoring_handle(**kwargs):
    """A dynamic build with nothing configured. No CONNECT: restoration is a start-up activity and
    must work before any master exists, which is the whole point of the feature."""
    return XcpTest(dynamic_config(daq_count=2, odt_count=2, odt_entries_count=2, **kwargs))


def entry(handle, address=0x1000, length=1, extension=0, bit_offset=0xFF):
    p = handle.ffi.new('Xcp_OdtEntryType *')
    p.address = handle.ffi.cast('uint32 *', address)
    p.length = length
    p.addressExtension = extension
    p.bitOffset = bit_offset
    return p


def test_the_setters_rebuild_a_list_the_accessors_then_report():
    """Round trip through the two halves of DD94/DD103: what Xcp_Restore* writes is what the SP5-NV
    accessors read back. Asserted through the accessors rather than internal state, which the CFFI
    harness cannot reach. Every field differs from its default so a partially-applied setter fails."""
    handle = restoring_handle()

    assert handle.lib.Xcp_RestoreDaqListCount(2) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtCount(0, 2) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntryCount(0, 1, 2) == handle.define('E_OK')
    assert handle.lib.Xcp_RestoreOdtEntry(0, 1, 0, entry(handle, address=0x12345678, length=1,
                                                          extension=2, bit_offset=3)) == handle.define('E_OK')

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 2
    assert handle.lib.Xcp_GetOdtEntryCount(0, 1) == 2

    read_back = handle.ffi.new('Xcp_OdtEntryType *')
    assert handle.lib.Xcp_GetOdtEntry(0, 1, 0, read_back) == handle.define('E_OK')
    assert int(handle.ffi.cast('uint32', read_back.address)) == 0x12345678
    assert (read_back.length, read_back.addressExtension, read_back.bitOffset) == (1, 2, 3)


def test_the_setters_refuse_out_of_range_arguments():
    """Mirrors the accessors' own bounds (SP5-NV Task 3): a list at or past the restored count, an
    ODT past that list's count, an entry past that ODT's count. Each argument is at the boundary,
    which is the sharpest case for a >=-vs-> error."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(2)
    handle.lib.Xcp_RestoreOdtCount(0, 2)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 1, 2)

    assert handle.lib.Xcp_RestoreOdtCount(2, 1) == handle.define('E_NOT_OK'), 'list == count'
    assert handle.lib.Xcp_RestoreOdtEntryCount(0, 2, 1) == handle.define('E_NOT_OK'), 'odt == count'
    assert handle.lib.Xcp_RestoreOdtEntry(0, 1, 2, entry(handle)) == handle.define('E_NOT_OK'), 'entry == count'


def test_nothing_runs_until_resume_complete():
    """DD105. A restore that stops halfway must leave a slave that resumed nothing, not one
    transmitting a half-built configuration. Asserted on CanIf_Transmit, which is where a running
    list would show up, after triggering the event channel the list is bound to."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)

    handle.can_if_transmit.reset_mock()
    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert not handle.can_if_transmit.called, 'no Xcp_ResumeComplete, so nothing is live'


def test_resume_complete_refuses_a_list_the_front_door_would_refuse_to_start():
    """DD105's second half. START_STOP_DAQ_LIST answers ERR_DAQ_CONFIG for a list with no written
    ODT entry, so resuming must not create by the back door a state the front door rejects. The ODT
    entry count is restored but no entry is written."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_NOT_OK')
```

- [ ] **Step 2: Run the subset and confirm failure**

```
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 \
  --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```
Expected: failure at the first `Xcp_Restore*` call — the symbol does not exist.

- [ ] **Step 3: Add the resume state**

In `source/Xcp_Internal.h`, beside `Xcp_ConnectionState`:

```c
/**
 * @brief how far a start-up restoration has got.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4. XCP_RESUME_RESTORING is
 * entered by the first Xcp_Restore* call and left only by Xcp_ResumeComplete, which is what makes
 * a restored configuration live (design doc DD105). Explicitly 0 for IDLE, the same defensive
 * reason Xcp_ConnectionState is.
 */
typedef enum {
    XCP_RESUME_IDLE = 0x00u,
    XCP_RESUME_RESTORING,
    XCP_RESUME_ACTIVE
} Xcp_ResumeStateType;
```

Add `Xcp_ResumeStateType resume_state;` to `Xcp_InternalType`, and reset it to `XCP_RESUME_IDLE` in `Xcp_Init` beside the other resets (`source/Xcp.c:1221`).

- [ ] **Step 4: Declare and implement the setters**

Declare all six in `interface/Xcp.h` with doc comments matching `Xcp_GetSegmentFreezeState`'s style (`interface/Xcp.h:416-425`), each stating what it returns for an out-of-range argument and that it answers `E_NOT_OK` once `Xcp_ResumeComplete` has run.

Implement in `source/Xcp_Daq.c` beside the SP5-NV accessors, reusing `Xcp_DaqListIsValid` and `Xcp_DaqListRt`. `Xcp_RestoreDaqListCount` raises `Xcp_Internal.allocated_daq_count` under `DAQ_DYNAMIC` and validates equality against `Xcp_Ptr->general->daqCount` under `DAQ_STATIC`. Each setter sets `resume_state = XCP_RESUME_RESTORING` on its first success and refuses when `resume_state == XCP_RESUME_ACTIVE`.

`Xcp_ResumeComplete` validates every restored list the way `START_STOP_DAQ_LIST` does before starting one, and on success sets `Xcp_Internal.session_configuration_id`, `resume_state = XCP_RESUME_ACTIVE`, and marks each restored list `XCP_DAQ_LIST_MODE_RESUME | XCP_DAQ_LIST_MODE_RUNNING`. **Task 3 adds the connection state, session status and event**; this task stops at the list state.

- [ ] **Step 5: Run the subset, then the full suite**

Expected: 12932 + 4 = **12936 passed, 29 skipped**, both ctest targets.

- [ ] **Step 6: Mutation-verify**

Two runs, each naming the test that fails: (a) make `Xcp_ResumeComplete` skip its validation → `test_resume_complete_refuses_a_list_the_front_door_would_refuse_to_start` fails; (b) make the setters mark lists RUNNING as they land instead of at commit → `test_nothing_runs_until_resume_complete` fails.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: restore a stored DAQ configuration through integrator setters"
```

---

### Task 2: resumed lists survive a DISCONNECT

**Files:**
- Modify: `source/Xcp_Daq.c`, `source/Xcp_Std.c:1390-1424`
- Test: `test/daq_resume_test.py` (extend)

**Interfaces:**
- Consumes: Task 1's `Xcp_ResumeComplete` and the RESUME list-mode flag.
- Produces: `void Xcp_DaqFreeSessionAllocated(void);` in `source/Xcp_Daq.c`, declared in `source/Xcp_Internal.h`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_disconnect_frees_session_lists_and_spares_resumed_ones():
    """DD106. Xcp_DisconnectSession frees every dynamic list, which would let a master's DISCONNECT
    kill a resumed measurement under DAQ_DYNAMIC and not under DAQ_STATIC.

    The fixture is built so a lazy fix fails: list 0 is resumed and list 1 is allocated by the
    session's own master. An implementation that skipped the teardown wholesale would keep BOTH and
    pass a weaker test; this one requires list 1 to be gone."""
    handle = restoring_handle(xcp_free_daq_api_enable=True)
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')

    connect(handle)
    # ALLOC_DAQ(2) raises the pool to two lists; list 1 belongs to this session, list 0 does not.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xD5, 0x00, 0x02, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # DISCONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFE,)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_GetDaqListOdtCount(0) == 1, 'the resumed list survives'
    assert handle.lib.Xcp_GetDaqListOdtCount(1) == 0, "the session's own list is freed"
```

- [ ] **Step 2: Run the subset and confirm failure**

Expected: the resumed list's ODT count is 0 — `Xcp_DaqFreeAll` took it with the rest.

- [ ] **Step 3: Implement**

Add `Xcp_DaqFreeSessionAllocated` to `source/Xcp_Daq.c`: the `Xcp_DaqFreeAll` loop, skipping lists whose mode carries `XCP_DAQ_LIST_MODE_RESUME`. Change `source/Xcp_Std.c:1423` to call it instead of `Xcp_DaqFreeAll`.

Comment the call site with why the condition is inside the one door rather than beside it: `Xcp_DisconnectSession` exists because a second door to `XCP_CONNECTION_STATE_DISCONNECTED` was a second place to forget the unwind, and DD106 must not re-open that.

- [ ] **Step 4: Run the subset, then the full suite**

Expected: **12937 passed, 29 skipped**.

- [ ] **Step 5: Mutation-verify**

Make `Xcp_DaqFreeSessionAllocated` skip the teardown entirely → the new test fails on list 1 still holding an ODT, which is the assertion the fixture exists to make possible.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: a disconnect frees this session's DAQ lists, not resumed ones"
```

---

### Task 3: the resumed slave reports itself

**Files:**
- Modify: `source/Xcp_Daq.c`, `source/Xcp_Std.c`, `source/Xcp_Internal.h`
- Test: `test/daq_resume_test.py` (extend)

**Interfaces:**
- Consumes: Task 1's `Xcp_ResumeComplete` and `resume_state`.
- Produces: `XCP_SESSION_STATUS_MASK_RESUME (0x01u << 0x07u)` and `XCP_EVENT_RESUME_MODE (0x00u)` in `source/Xcp_Internal.h`.

- [ ] **Step 1: Write the failing tests**

```python
def resumed_handle():
    """One list restored, committed, and running -- the state every test below starts from."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')
    return handle


def test_a_resumed_slave_transmits_with_no_connect_ever_sent():
    """The acceptance bar. 1.1/1.6.4.1.1.4: "the slave being in RESUME mode started the DAQ list
    automatically". Autonomous transmission IS the feature; no other test in this repository
    transmits without a session, so this one cannot pass by inheriting a fixture's habits."""
    handle = resumed_handle()
    handle.can_if_transmit.reset_mock()

    handle.lib.Xcp_TriggerEventChannel(0)
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.called, 'a resumed list transmits with no master session'


def test_resume_complete_raises_ev_resume_mode():
    """1.1/1.8.1: "With EV_RESUME_MODE the slave indicates that it is starting in RESUME mode."
    Code 0x00 (Xcp_Internal.h, not reachable via handle.define -- the literal is used with this
    comment, as test/set_request_test.py does for its own event codes)."""
    handle = restoring_handle()
    handle.lib.Xcp_RestoreDaqListCount(1)
    handle.lib.Xcp_RestoreOdtCount(0, 1)
    handle.lib.Xcp_RestoreOdtEntryCount(0, 0, 1)
    handle.lib.Xcp_RestoreOdtEntry(0, 0, 0, entry(handle))
    handle.lib.Xcp_RestoreDaqListMode(0, 0x00, 0, 1, 0)
    handle.can_if_transmit.reset_mock()

    assert handle.lib.Xcp_ResumeComplete(0x1234) == handle.define('E_OK')
    handle.lib.Xcp_MainFunction()

    frames = [c for c in handle.can_if_transmit.call_args_list
              if tuple(c[0][1].SduDataPtr[0:2]) == (0xFD, 0x00)]  # XCP_PID_EVENT, EV_RESUME_MODE
    assert len(frames) == 1, 'exactly one EV_RESUME_MODE'


def test_get_status_reports_resume_and_the_restored_id():
    """1.1/1.6.1.1.3: session status bit 7 RESUME, "1 = Slave is in RESUME mode", and bit 6
    DAQ_RUNNING, which follows from the restored list actually running. The id comes from
    Xcp_ResumeComplete, so 0x1234 rather than the 0x0000 Xcp_Init leaves -- a value that cannot
    coincide with the default."""
    handle = resumed_handle()
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFD,)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:6])

    assert response[0] == 0xFF
    assert response[1] & 0b10000000 != 0x00, 'session status RESUME, bit 7'
    assert response[1] & 0b01000000 != 0x00, 'session status DAQ_RUNNING, bit 6'
    assert response[4:6] == (0x34, 0x12), 'the restored session configuration id'


def test_get_daq_list_mode_reports_resume_and_running_for_a_restored_list():
    """1.1/1.6.4.1.1.4: mode bit 7 RESUME, "this DAQ list is part of a configuration used in RESUME
    mode", and bit 6 RUNNING. Both in the GET_DAQ_LIST_MODE response layout, which is the layout
    Xcp_DaqListRtType::mode already stores."""
    handle = resumed_handle()
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDF, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert response[0] == 0xFF, 'an error response would satisfy the bit tests below'
    assert response[1] & 0b10000000 != 0x00, 'RESUME, bit 7'
    assert response[1] & 0b01000000 != 0x00, 'RUNNING, bit 6'
```

- [ ] **Step 2: Run the subset and confirm failure**

- [ ] **Step 3: Implement**

Add `XCP_SESSION_STATUS_MASK_RESUME` and `XCP_EVENT_RESUME_MODE` to `source/Xcp_Internal.h`. In `Xcp_ResumeComplete`, set `Xcp_Internal.connection_status = XCP_CONNECTION_STATE_RESUME`, OR `XCP_SESSION_STATUS_MASK_RESUME` into `session_status`, and push `XCP_EVENT_RESUME_MODE` onto the event queue under `SchM_Enter_Xcp_DtoQueue`, copying the shape of `Xcp_MainFunction`'s `EV_STORE_DAQ` push (`source/Xcp.c:1611`).

`DAQ_RUNNING` needs no new code — `Xcp_DaqSessionStatusUpdate` (`source/Xcp_Daq.c:338`) already derives it from list state; call it after marking the lists.

- [ ] **Step 4: Run the subset, then the full suite**

Expected: **12941 passed, 29 skipped**.

- [ ] **Step 5: Mutation-verify**

Two runs: (a) drop the `XCP_SESSION_STATUS_MASK_RESUME` OR → the `GET_STATUS` test fails on bit 7 while the `GET_DAQ_LIST_MODE` test still passes, proving the two report from different state; (b) push `XCP_EVENT_STORE_DAQ` instead of `XCP_EVENT_RESUME_MODE` → the event test fails.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: report RESUME mode in GET_STATUS, GET_DAQ_LIST_MODE and EV_RESUME_MODE"
```

---

### Task 4: arm it from the master, and advertise it

**Files:**
- Modify: `interface/Xcp.h`, `source/Xcp_Internal.h`, `source/Xcp_Std.c`, `source/Xcp_Daq.c`
- Test: `test/daq_resume_test.py` (extend), `test/daq_nv_storage_test.py` (update one test)

**Interfaces:**
- Consumes: everything above.
- Produces: `boolean Xcp_GetResumeArmedState(void);`

**This is the task that makes the feature visible on the wire.** Everything it advertises now exists.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_armed_state_follows_the_store_mode_bit_that_asked_for_it():
    """DD104. 1.1/1.6.1.2.3: STORE_DAQ_REQ_RESUME (mode bit 2) "implicitly sets the slave into
    RESUME mode", STORE_DAQ_REQ_NO_RESUME (bit 1) "does not". The module keeps no non-volatile
    memory, so the integrator queries this during Xcp_StoreDaqConfiguration and persists it.

    Both bits are exercised in one test so the accessor cannot pass by returning a constant."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                    xcp_store_daq_configuration_api_enable=True))
    connect(handle)
    seen = []

    def store_daq_configuration(session_configuration_id, p_status_code):
        seen.append(handle.lib.Xcp_GetResumeArmedState(0) if False else
                    handle.lib.Xcp_GetResumeArmedState())
        p_status_code[0] = 0x00
        return handle.define('E_OK')

    handle.xcp_store_daq_configuration.side_effect = store_daq_configuration

    exchange(handle, (0xF9, 0b00000010, 0x00, 0x00))   # NO_RESUME
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    exchange(handle, (0xF9, 0b00000100, 0x00, 0x00))   # RESUME
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert seen == [0, 1], 'FALSE for the NO_RESUME store, TRUE for the RESUME store'


def test_resume_supported_is_advertised():
    """1.1/1.6.4.1.2.4, DAQ_PROPERTIES bit 2: "1 = DAQ lists can be set to RESUME mode." Now true,
    and this is the assertion that keeps the SET_REQUEST bit 2 acceptance below honest."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xDA,)))
    handle.lib.Xcp_MainFunction()
    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2])

    assert response[0] == 0xFF
    assert response[1] & 0b00000100 != 0x00, 'DAQ_PROPERTIES RESUME_SUPPORTED, bit 2'
```

`exchange` is `test/daq_nv_storage_test.py`'s helper; import it or copy its three lines.

- [ ] **Step 2: Run the subset and confirm failure**

Expected: `Xcp_GetResumeArmedState` does not exist, and `RESUME_SUPPORTED` is clear.

- [ ] **Step 3: Implement**

Add `boolean resume_armed;` to `Xcp_InternalType`, reset `FALSE` in `Xcp_Init`. In `Xcp_DTOCmdStdSetRequest`, add `XCP_SET_REQUEST_MODE_STORE_DAQ_REQ_RESUME` to `accepted_request_mask` alongside `..._NO_RESUME` under the same `storeDaqConfigurationApiEnable` gate, and set `resume_armed` to `TRUE` for bit 2 / `FALSE` for bit 1 in the translation block. Both bits set `XCP_SESSION_STATUS_MASK_STORE_DAQ_REQ` — 1.1's `GET_STATUS` has a single store flag.

Declare and implement `Xcp_GetResumeArmedState` in `interface/Xcp.h` and `source/Xcp_Daq.c` beside the other accessors. In `Xcp_DTOCmdDaqGetDaqProcessorInfo` (`source/Xcp_Daq.c:1796`), OR in `XCP_DAQ_PROPERTIES_RESUME_SUPPORTED`.

- [ ] **Step 4: Update SP5-NV's premise test**

`test/daq_nv_storage_test.py::test_resume_stays_unadvertised_so_the_refusal_above_stays_coherent` and `test_store_daq_req_resume_is_refused_while_resume_is_unadvertised` were written to fail here — the first pins `RESUME_SUPPORTED` clear, the second pins bit 2 refused. Both premises are now false. Rewrite them to assert the new behaviour and say in each docstring that they were SP5-NV's deliberate tripwires, so a reader does not mistake the edit for a weakened test.

- [ ] **Step 5: Run the subset, then the full suite**

Expected: **12943 passed, 29 skipped** (12941 + 2 new; the two rewritten tests keep their count).

- [ ] **Step 6: Mutation-verify**

Two runs: (a) make `Xcp_GetResumeArmedState` return `TRUE` unconditionally → the armed test fails on the NO_RESUME half, which is why both bits are in one test; (b) drop `RESUME_SUPPORTED` from the properties byte → the advertisement test fails.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: accept STORE_DAQ_REQ_RESUME and advertise RESUME_SUPPORTED"
```

---

## Final verification

- [ ] Full `./test.sh` on a clean tree, both ctest targets green, `XCP_PYTEST_ARGS` cleared to `""`.
- [ ] Every mutation recorded with the test it failed, including any honest negatives.
- [ ] **A `CONNECT` during RESUME does not stop the lists** — assert it, since nothing in these four tasks touches `CONNECT` and a reviewer should see it was checked rather than assumed.
- [ ] `Xcp_Restore*` refused after `CONNECT`, not only after `Xcp_ResumeComplete` (DD107).
- [ ] Update `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`: RESUME complete in §2.6, and correct the SP5 entry, which still describes a `CONNECT` resume handshake that does not exist.
- [ ] Section 5 of the design records an open assumption about Part 1 §2.3. If XCP Part 1 reaches `docs/external` during this phase, check it and either close the assumption or raise what it changes.

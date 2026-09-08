# Seed-and-Key Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an unlock last the session, refuse an `UNLOCK` with no held seed, and report the resource protection mask with the polarity the specification defines — removing the generation refusal that makes `resource_protection.programming` unbuildable.

**Architecture:** Three pre-existing defects share one field, `Xcp_Internal.protection_status`. The work lands in four tasks ordered so each is independently testable: the lifetime fix first (it is what makes the programming configuration viable), then the held-seed gate, then the removal of the generation refusal proved by an end-to-end programming run, and finally the representation change — the field becomes the still-locked mask and is renamed, which turns every reader into a compile error rather than silently correct-looking arithmetic.

**Tech Stack:** C (AUTOSAR-style, MISRA-leaning), Python 3.7 + pytest + CFFI test harness, CMake, Jinja2 code generation, Docker.

**Spec:** `docs/superpowers/specs/2026-09-08-xcp-seed-key-hardening-design.md` (DD78–DD83)

## Global Constraints

- **`./test.sh` is the only authoritative run, and it runs in Docker.** Host runs die at `cmake: not found`. Use exactly: `docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh`
- **Never `rm -rf generated/*`** — it holds a tracked `generated/CMakeLists.txt`.
- **`Xcp_Internal` and file-`static` tables are NOT reachable from the CFFI harness.** `test/conftest.py` builds its cdef from `interface/Xcp.h` alone. Every assertion must observe through transmitted bytes. Precedent: `test/clear_daq_list_test.py:80-92`.
- **Mutation verification is required** on: DD80's gate expression, **each of DD81's two conjuncts separately**, and at least one DD82 reporting site. A compound condition needs a test per term, not per outcome.
- **A test that cannot fail is a defect.** Before committing any test, revert the fix it pins and confirm it fails; record which test failed and how.
- Commit messages for defect fixes begin `fix: pre-existing` and state the measured failure sequence.
- The `resource_protection.data_stimulation` refusal (DD41/DD48) must still fire at the end of this work, with its own test unchanged.

**Frames and helpers used throughout** (verified against the current tree):

| Thing | Value |
|---|---|
| CONNECT | `(0xFF, 0x00)` |
| GET_STATUS | `(0xFD,)` — group `MASK_NONE`, never protected |
| SET_MTA | `(0xF6, 0x00, 0x00, 0x00) + tuple(u32_to_array(addr, 'LITTLE_ENDIAN'))` — group `MASK_NONE` |
| DOWNLOAD (3 bytes) | `(0xF0, 0x03, 0x11, 0x22, 0x33)` — group `MASK_CAL_PAG`, **the protected observable** |
| GET_SEED | `(0xF8, mode, resource)`; resource `0x01` = CAL_PAG, `0x10` = PGM |
| UNLOCK | `(0xF7, remaining_len) + key_bytes` |
| Locked refusal | `(0xFE, 0x25)` = `ERR_ACCESS_LOCKED` |
| Sequence refusal | `(0xFE, 0x29)` = `ERR_SEQUENCE` |
| Mocks | `handle.xcp_get_seed`, `handle.xcp_calc_key`, `handle.xcp_write_slave_memory_u8` |
| Config flags | `resource_protection_calibration_paging=True`, `resource_protection_programming=True`, `programming_enabled=True` |
| Helpers | `from .download_test import connect, set_mta`; `from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok`; `from .seed_key_defects_test import exchange` |

`exchange(handle, request, length=3)` resets the transmit mock, dispatches, pumps `Xcp_MainFunction`, asserts exactly one transmission, returns the first `length` response bytes, then confirms. Use it for every command; never read `call_args` without resetting first.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `source/Xcp.c` | dispatch gate, protection accessors, `Xcp_Init` seeding | 1, 4 |
| `source/Xcp_Std.c` | `CONNECT` teardown, `UNLOCK`, `GET_STATUS` | 1, 2, 4 |
| `source/Xcp_Internal.h` | the field and accessor declarations | 4 |
| `script/source_cfg.c.jinja2` | the generation refusal | 3 |
| `test/seed_key_lifetime_test.py` | **new** — DD79 and DD81 behaviour | 1, 2 |
| `test/pgm_protected_acceptance_test.py` | **new** — the DD83 end-to-end proof | 3 |
| `test/seed_key_defects_test.py` | migrate five status-byte assertions | 4 |

**Checked, and needing no change:** `test/get_status_test.py` and `test/asam_protocol_layer_test.py`
both exercise `GET_STATUS` but assert only byte 0 and byte 1, never byte 2 — so the polarity change
does not touch them. The five tests in `test/seed_key_defects_test.py` are the *only* existing
assertions on the protection byte anywhere in the suite. If a run turns up a sixth, that is a
finding worth reporting, not a test to quietly adjust.

---

### Task 1: DD79 — an unlock lasts the session

**Files:**
- Modify: `source/Xcp.c` (the clear-after-dispatch call; `Xcp_SetProtectionStatus`)
- Modify: `source/Xcp_Std.c` (`Xcp_CTOCmdStdConnect`'s teardown block)
- Test: `test/seed_key_lifetime_test.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `Xcp_Internal.protection_status` now accumulates granted resources and is cleared only by `Xcp_Init` and `CONNECT`. Still means "unlocked set" — Task 4 inverts it. Task 3 depends on this task and nothing else.

- [ ] **Step 1: Write the failing tests**

Create `test/seed_key_lifetime_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD79 (docs/superpowers/specs/2026-09-08-xcp-seed-key-hardening-design.md) -- a pre-existing
defect in shipped code: a successful UNLOCK grants a resource for exactly ONE following command.

source/Xcp.c cleared the whole granted set after every dispatched command except UNLOCK itself, so
an unrelated GET_STATUS spent the grant just as a CAL command did. XCP part 2 - Protocol Layer
Specification 1.0/1.6.1.2.5 says the opposite: "a repetition of an UNLOCK sequence with a correct
key will have a positive response and no other effect", which presumes the grant is still standing.

DOWNLOAD (0xF0) is the protected observable throughout this file: Xcp_PIDToCmdGroupTable
(source/Xcp.c) maps it to MASK_CAL_PAG, while SET_MTA (0xF6) and GET_STATUS (0xFD) map to
MASK_NONE, so the setup and the interloper both stay reachable while CAL_PAG is locked."""

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta
from .seed_key_test import get_seed_side_effect_copy_ok, calc_key_side_effect_copy_ok
from .seed_key_defects_test import exchange

GET_STATUS = (0xFD,)
DOWNLOAD = (0xF0, 0x03, 0x11, 0x22, 0x33)
SEED = [0x11, 0x22]
KEY = [0x33, 0x44]


def cal_protected_handle(**kwargs):
    """A slave whose CALibration/Paging group is protected, connected and with a valid MTA.

    The MTA is set BEFORE any unlock deliberately: SET_MTA is MASK_NONE, so it must succeed while
    CAL_PAG is still locked, and doing it here keeps every DOWNLOAD below a test of the protection
    gate rather than of address setup."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   resource_protection_calibration_paging=True,
                                   **kwargs))
    connect(handle)
    set_mta(handle, 0x1000)
    return handle


def unlock_cal_pag(handle):
    """A complete GET_SEED/UNLOCK sequence for CAL_PAG, asserting each half so a failure here is
    never mistaken for the behaviour under test."""
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF, 'GET_SEED(mode=0, CAL_PAG)'
    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0] == 0xFF, 'UNLOCK'


def test_a_protected_command_is_refused_before_any_unlock():
    """The precondition every other test in this file rests on. Without it, a DOWNLOAD that
    succeeds proves nothing -- it would succeed identically if the resource were never protected,
    which is exactly the configuration the rest of the suite runs in."""
    handle = cal_protected_handle()

    assert exchange(handle, DOWNLOAD)[0:2] == (0xFE, 0x25), 'ERR_ACCESS_LOCKED'


def test_an_unlock_survives_an_unrelated_command():
    """DD79, the defect itself. GET_STATUS is MASK_NONE and has no side effects, so the only thing
    it can do to the DOWNLOAD that follows is spend its grant -- which is what it used to do."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)

    assert exchange(handle, DOWNLOAD)[0] == 0xFF, 'the first protected command after UNLOCK'
    assert exchange(handle, GET_STATUS)[0] == 0xFF
    assert exchange(handle, DOWNLOAD)[0] == 0xFF, \
        'the grant was spent by an unrelated GET_STATUS'


def test_an_unlock_survives_repeated_use_of_the_protected_resource():
    """The grant must not be consumed by the protected command either -- a variant the
    single-command lifetime also broke, and one a master doing a real calibration session hits
    immediately."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)

    for attempt in range(5):
        assert exchange(handle, DOWNLOAD)[0] == 0xFF, \
            'DOWNLOAD number {} was refused'.format(attempt + 1)


def test_an_unlock_does_not_survive_a_reconnect():
    """The other half of DD79: the grant lasts the SESSION, not forever. This is the same session
    boundary DD77 established, and the reset joins that block."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)
    assert exchange(handle, DOWNLOAD)[0] == 0xFF

    connect(handle)
    set_mta(handle, 0x1000)

    assert exchange(handle, DOWNLOAD)[0:2] == (0xFE, 0x25), \
        'the grant outlived the session that earned it'
```

- [ ] **Step 2: Run the tests and confirm three of the four fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project/build xcp-test:sp4b cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;seed_key_lifetime"
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```

Expected: `test_a_protected_command_is_refused_before_any_unlock` PASSES (the gate already refuses); the other three FAIL. `-x` stops at the first, so run, fix nothing, and note which one stopped it — then temporarily comment out the failing test to see the next, or trust the shared cause. Record the observed failure for each in the report.

- [ ] **Step 3: Delete the clear-after-dispatch**

In `source/Xcp.c`, inside the dispatch's allowed branch, delete:

```c
                                                    if (pid != XCP_PID_CMD_UNLOCK) {
                                                        Xcp_ClearProtectionStatus();
                                                    }
```

- [ ] **Step 4: Make grants accumulate**

In `source/Xcp.c`, change `Xcp_SetProtectionStatus`:

```c
void Xcp_SetProtectionStatus(void) {
    /* DD79: `|=`, not `=`. Once grants persist past the next command, an assignment would make
     * unlocking a second resource silently drop the first -- invisible while a grant lasted one
     * command, because there was never a second grant alive to lose. */
    Xcp_Internal.protection_status |= Xcp_Internal.requested_protected_resource;
}
```

- [ ] **Step 5: Re-lock at the session boundary**

In `source/Xcp_Std.c`, in `Xcp_CTOCmdStdConnect`'s teardown block, immediately before
`Xcp_Internal.connection_status = XCP_CONNECTION_STATE_CONNECTED;`:

```c
    /* DD79. With the clear-after-dispatch gone, this is the ONLY thing that re-locks a resource
     * inside a running module, and XCP part 1 - Overview 1.0/2.3 -- quoted in full at
     * Xcp_CanIfRxIndication (Xcp.c) -- names the protection status bits among what a DISCONNECTED
     * slave has reset. A grant belongs to the session that earned it. */
    Xcp_Internal.protection_status = 0x00u;
```

- [ ] **Step 6: Run the tests and confirm all four pass**

Same commands as Step 2. Expected: 4 passed.

- [ ] **Step 7: Mutation-verify the lifetime**

Restore the deleted clear (Step 3) temporarily, re-run, and confirm `test_an_unlock_survives_an_unrelated_command` fails. Then restore the fix. Separately, change Step 4's `|=` back to `=` and confirm nothing fails — **this is expected**, because no test in this task unlocks two resources; record that honestly, and note that Task 4's accumulate test covers it.

- [ ] **Step 8: Clear the pytest filter and run the full suite**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project/build xcp-test:sp4b cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS=""
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --ulimit nofile=65536:524288 --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:sp4b ./test.sh
```

Expected: both ctest targets pass. **If any existing test fails, do not adjust it without reporting** — a test that depended on a grant being spent is evidence about the old behaviour and its docstring must be read before it is changed.

- [ ] **Step 9: Commit**

```bash
git add source/Xcp.c source/Xcp_Std.c test/seed_key_lifetime_test.py
git commit -m "fix: pre-existing single-command unlock lifetime in shipped seed-and-key code"
```

---

### Task 2: DD81 — `UNLOCK` requires a held seed

**Files:**
- Modify: `source/Xcp_Std.c` (`Xcp_DTOCmdStdUnlock`'s admission gate)
- Test: `test/seed_key_lifetime_test.py` (append)

**Interfaces:**
- Consumes: `cal_protected_handle()`, `unlock_cal_pag()`, `SEED`, `KEY` from Task 1.
- Produces: `UNLOCK` answers `ERR_SEQUENCE` unless `seed.total_length != 0`.

- [ ] **Step 1: Write the failing tests**

Append to `test/seed_key_lifetime_test.py`:

```python
def test_unlock_with_no_preceding_get_seed_is_refused():
    """DD81, and the defect section 3b of the previous branch recorded and deliberately left
    unfixed. XCP part 2 1.0/1.6.1.2.5: "The master only can send an UNLOCK sequence if previously
    there was a GET_SEED sequence... If the master does not respect this sequence, the slave
    returns an ERR_SEQUENCE."

    ERR_SEQUENCE needs no deviation: it is in UNLOCK's own 1.7.3.2.1 row, and that row's prescribed
    pre-action for it is literally GET_SEED, so the refusal tells the master exactly what to do."""
    handle = cal_protected_handle()
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'
    assert exchange(handle, DOWNLOAD)[0:2] == (0xFE, 0x25), \
        'the resource was granted by an UNLOCK against a seed that was never issued'


def test_a_second_unlock_without_a_fresh_seed_is_refused():
    """The seed is spent by the UNLOCK that consumes it -- Xcp_DTOCmdStdUnlock already zeroes
    seed.total_length on a complete key, under a comment saying it "enforces a new seed to be
    requested prior to unlock a next resource". Nothing ever checked it. This is that check."""
    handle = cal_protected_handle()
    unlock_cal_pag(handle)

    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFE, 0x29), 'ERR_SEQUENCE'


def test_a_legitimate_multi_frame_key_is_still_admitted():
    """The guard must not break a key too long for one frame. At MAX_CTO=8 a frame carries at most
    MAX_CTO-2 = 6 key bytes, so a 10-byte key needs two UNLOCK frames; seed.total_length stays
    non-zero across the whole sequence and is zeroed only on completion, so every frame is
    admitted. Without this test the guard could be written to admit only the FIRST frame and both
    tests above would still pass."""
    handle = cal_protected_handle()
    long_key = [0xA0 + i for i in range(10)]

    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, long_key)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF
    assert exchange(handle, (0xF7, 10) + tuple(long_key[0:6]))[0] == 0xFF, 'first UNLOCK frame'
    assert exchange(handle, (0xF7, 4) + tuple(long_key[6:10]))[0] == 0xFF, 'second UNLOCK frame'

    assert exchange(handle, DOWNLOAD)[0] == 0xFF, 'a legitimate multi-frame unlock was refused'
```

- [ ] **Step 2: Run and confirm the first two fail, the third passes**

Filter with `-DXCP_PYTEST_ARGS="-k;seed_key_lifetime"` as in Task 1 Step 2. Expected: the two refusal tests FAIL (the UNLOCK is admitted and answers `0xFF`), the multi-frame test PASSES.

- [ ] **Step 3: Add the held-seed conjunct**

In `source/Xcp_Std.c`, in `Xcp_DTOCmdStdUnlock`, replace:

```c
    if ((Xcp_Internal.last_pid == XCP_PID_CMD_GET_SEED) || (Xcp_Internal.last_pid == XCP_PID_CMD_UNLOCK))
```

with:

```c
    /* DD81. Two terms answering two different questions, and both are load-bearing.
     *
     * last_pid asks whether the immediately preceding command was a successful GET_SEED or a prior
     * frame of this same key. It cannot say WHICH -- it is a two-element set-membership test -- so
     * it cannot answer "was a seed actually issued", and on its own it admitted an UNLOCK against a
     * seed that never existed (XCP part 2 1.0/1.6.1.2.5: "The master only can send an UNLOCK
     * sequence if previously there was a GET_SEED sequence").
     *
     * seed.total_length asks exactly that second question. The mechanism already existed and
     * nothing read it: the sequence below zeroes this field once a full key arrives, to "enforce a
     * new seed to be requested prior to unlock a next resource". It stays non-zero for every frame
     * of a multi-frame key, so this admits the whole legitimate sequence and refuses a replay.
     *
     * ERR_SEQUENCE is not a deviation: UNLOCK's own 1.7.3.2.1 row lists it, with GET_SEED as its
     * prescribed pre-action. */
    if (((Xcp_Internal.last_pid == XCP_PID_CMD_GET_SEED) || (Xcp_Internal.last_pid == XCP_PID_CMD_UNLOCK)) &&
        (Xcp_Internal.seed.total_length != 0x00u))
```

- [ ] **Step 4: Run and confirm all seven tests in the file pass**

Expected: 7 passed.

- [ ] **Step 5: Mutation-verify each conjunct separately**

Two independent runs, restoring the gate between them. Record which test failed in each:

1. Drop the `seed.total_length` term → `test_unlock_with_no_preceding_get_seed_is_refused` and `test_a_second_unlock_without_a_fresh_seed_is_refused` must fail.
2. Drop the `last_pid` terms (keep only `seed.total_length != 0`) → at least one test must fail. **If none does, say so plainly in the report rather than inventing one** — it would mean the `last_pid` half is unpinned by this suite, which is a finding, not a failure to hide.

- [ ] **Step 6: Full suite, then commit**

Clear the filter and run the full suite as in Task 1 Step 8.

```bash
git add source/Xcp_Std.c test/seed_key_lifetime_test.py
git commit -m "fix: pre-existing missing held-seed check in shipped UNLOCK code"
```

---

### Task 3: DD83 — remove the programming refusal, and prove it obsolete

**Files:**
- Modify: `script/source_cfg.c.jinja2` (delete the `resource_protection.programming` raise)
- Test: `test/pgm_protected_acceptance_test.py` (create)

**Interfaces:**
- Consumes: Task 1's session-lifetime grant. Depends on Task 1 and on nothing else.
- Produces: `resource_protection_programming=True` becomes a buildable configuration, which **Task 4 requires** for its migrated tests.

- [ ] **Step 1: Write the end-to-end test**

Create `test/pgm_protected_acceptance_test.py`. Read `test/pgm_acceptance_test.py` first and follow its established shape for pumping `Xcp_MainFunction` and confirming deferred responses; the integrator callbacks (`Xcp_ProgramStart`, `Xcp_ProgramClear`, `Xcp_ProgramWrite`, `Xcp_ProgramReset`) are polled, so each returns `E_NOT_OK` until it is finished and the response arrives on a later `Xcp_MainFunction`.

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DD83 -- the configuration this proves buildable could not be generated at all before this task.

script/source_cfg.c.jinja2 raised on `resource_protection.programming: true` with
`programming.enabled: true`, because an unlock was spent by the single command that followed it:
PROGRAM_START consumed the grant, the session became XCP_PGM_ACTIVE, PROGRAM_RESET -- the only
command that ends it -- was locked again, and GET_SEED and UNLOCK were themselves refused
ERR_PGM_ACTIVE. The slave could never leave the programming session.

Every link in that chain depended on the grant being spent, so DD79 dissolves it. This test walks
the whole sequence rather than arguing it: an argument that a dead end no longer exists is worth
much less than a run that goes through where the dead end was."""
```

The test must perform, in one session, with `programming_enabled=True`, `resource_protection_programming=True` and the PGM API flags the sequence needs enabled:

`CONNECT` → `GET_SEED(mode=0, resource=0x10)` → `UNLOCK` → `PROGRAM_START` → `PROGRAM_CLEAR` → `PROGRAM` → `PROGRAM_RESET`, asserting a positive response at every step, and asserting **before** the unlock that `PROGRAM_START` answers `(0xFE, 0x25)` so the protection is proven live rather than absent.

- [ ] **Step 2: Confirm the configuration cannot be generated yet**

Run the new test. Expected: the generator raises, and the failure names `resource_protection.programming`. This is the precondition — it proves the refusal is real and that this test exercises it.

- [ ] **Step 3: Delete the refusal**

In `script/source_cfg.c.jinja2`, delete the `{%- if %}` / `{{ raise(...) }}` / `{%- endif %}` block guarding `configuration.programming.enabled` together with `configuration.apis.resource_protection.programming`. **Leave the `stim.capable` / `resource_protection.data_stimulation` raise immediately above it untouched** — that one is DD41/DD48 and is still true.

- [ ] **Step 4: Run and confirm the sequence completes**

Expected: the new test passes end to end.

- [ ] **Step 5: Confirm the STIM refusal still fires**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project/build xcp-test:sp4b cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;stim or generation or configuration"
```

Then the full run. Expected: the existing `data_stimulation` refusal test still passes, unmodified.

- [ ] **Step 6: Full suite, then commit**

```bash
git add script/source_cfg.c.jinja2 test/pgm_protected_acceptance_test.py
git commit -m "feat: a protected PGM resource can now conduct a programming sequence"
```

---

### Task 4: DD78, DD80, DD82 — store what the wire means

**Files:**
- Modify: `source/Xcp_Internal.h` (field at `:359`, accessor declarations at `:652-654`)
- Modify: `source/Xcp.c` (`Xcp_Init` seeding, the dispatch gate, the accessors, the `§1.7.3.2.2` citation)
- Modify: `source/Xcp_Std.c` (`CONNECT` re-seed, `UNLOCK`'s two response sites, `GET_STATUS` byte 2)
- Modify: `test/seed_key_defects_test.py` (five migrated assertions)
- Test: `test/seed_key_lifetime_test.py` (append polarity and accumulate tests)

**Interfaces:**
- Consumes: Tasks 1–3. Task 3 is a hard prerequisite: the migrated tests configure `resource_protection_programming=True`, which only becomes buildable there.
- Produces: `Xcp_Internal.locked_resource` (the still-protected mask), `Xcp_GetLockedResources(void)`, `Xcp_UnlockResources(uint8 mask)`.

- [ ] **Step 1: Write the failing tests**

Append to `test/seed_key_lifetime_test.py`:

```python
def test_get_status_reports_which_resources_are_still_protected():
    """DD82. XCP part 2 1.0/1.6.1.1.3 defines the Current Resource Protection Status as a mask
    where 1 = the group IS protected, and 1.6.1.2.5 makes UNLOCK's positive response carry that
    same mask. The module reported the UNLOCKED set instead -- so after unlocking CAL_PAG it said
    CAL_PAG was protected, at the moment it stopped being."""
    handle = cal_protected_handle()

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x01, \
        'CAL_PAG is configured protected and nothing has been unlocked'

    unlock_cal_pag(handle)

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x00, \
        'CAL_PAG was reported protected after being unlocked'


def test_get_status_reports_nothing_protected_when_nothing_is_configured_protected():
    """The domain half of the defect, not just the direction. In a build where no resource is
    protected -- test/parameter.py's DefaultConfig, which is what almost the whole suite runs --
    unlocking PGM used to make this byte report 0x10, claiming a protection the build does not
    have."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))
    connect(handle)

    assert exchange(handle, GET_STATUS, length=3)[2] == 0x00


def test_unlock_answers_the_remaining_protection_mask():
    """1.6.1.2.5: "The answer upon UNLOCK contains the Current Resource Protection Mask as
    described at GET_STATUS." Byte 1 of UNLOCK's positive response, same polarity as above."""
    handle = cal_protected_handle()
    handle.xcp_get_seed.side_effect = get_seed_side_effect_copy_ok(handle, SEED)
    handle.xcp_calc_key.side_effect = calc_key_side_effect_copy_ok(handle, KEY)

    assert exchange(handle, (0xF8, 0x00, 0x01))[0] == 0xFF
    assert exchange(handle, (0xF7, len(KEY)) + tuple(KEY))[0:2] == (0xFF, 0x00), \
        'UNLOCK reported the granted resource instead of what remains protected'
```

- [ ] **Step 2: Run and confirm they fail**

Expected: all three FAIL, reporting the inverted values (`0x00` where `0x01` is expected, `0x01` where `0x00` is expected).

- [ ] **Step 3: Rename the field**

In `source/Xcp_Internal.h`, change `uint8 protection_status;` to:

```c
    /* The Current Resource Protection Mask of XCP part 2 1.0/1.6.1.1.3: a set bit means the group
     * IS still protected. This is the value transmitted verbatim by GET_STATUS byte 2 and UNLOCK
     * response byte 1, so no reader inverts it and no reader can get the polarity wrong.
     *
     * DD78: this field used to hold the opposite -- the UNLOCKED set -- and was reported as if it
     * were this mask, at three sites. It was renamed rather than redefined in place so that every
     * existing reader became a compile error instead of silently correct-looking arithmetic. */
    uint8 locked_resource;
```

- [ ] **Step 4: Follow the compile errors**

Build and fix each site the rename breaks. The complete set, with the replacement for each:

| Site | Becomes |
|---|---|
| `source/Xcp.c` accessors | `uint8 Xcp_GetLockedResources(void) { return Xcp_Internal.locked_resource; }` and `void Xcp_UnlockResources(uint8 mask) { Xcp_Internal.locked_resource &= (uint8)(~mask); }`; delete `Xcp_ClearProtectionStatus` entirely |
| `source/Xcp_Internal.h:652-654` | declare the two above; delete the third |
| `source/Xcp.c` `Xcp_Init` | `Xcp_Internal.locked_resource = Xcp_Ptr->general->protectedResource;` |
| `source/Xcp_Std.c` `CONNECT` | `Xcp_Internal.locked_resource = Xcp_Ptr->general->protectedResource;` (replacing Task 1 Step 5's line) |
| `source/Xcp_Std.c` UNLOCK success | `Xcp_UnlockResources(Xcp_Internal.requested_protected_resource);` then `... SduDataPtr[0x01u] = Xcp_GetLockedResources();` |
| `source/Xcp_Std.c` UNLOCK partial | `... SduDataPtr[0x01u] = Xcp_GetLockedResources();` |
| `source/Xcp_Std.c` GET_STATUS | `... SduDataPtr[0x02u] = Xcp_GetLockedResources();` |

- [ ] **Step 5: Collapse the dispatch gate**

In `source/Xcp.c`, replace the two-term condition with:

```c
                                                /* DD80. One term, because a resource that was never
                                                 * configured protected is never in the mask, which
                                                 * subsumes the old `(group & protectedResource) == 0`
                                                 * disjunct.
                                                 *
                                                 * The equivalence was checked, not assumed: every
                                                 * Xcp_PIDToCmdGroupTable entry carries exactly one
                                                 * group bit or MASK_NONE, so this agrees with the old
                                                 * form for every PID. They would diverge only on a
                                                 * multi-bit entry -- the old form meant "any one of
                                                 * its groups is unlocked", this means "all of them
                                                 * are". Keep entries single-bit; if that ever has to
                                                 * change, this is the safe reading and the old one
                                                 * was not. */
                                                if ((Xcp_PIDToCmdGroupTable[pid] & Xcp_Internal.locked_resource) == 0x00u)
```

- [ ] **Step 6: Correct the citation on the refusal branch**

In the same `else` branch, replace the reference to `1.0/1.7.3.2.2` with `1.0/1.6.1.1.3`, and the sentence with:

```c
                                                    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.1.3
                                                     * states this rule once per resource group -- "all commands
                                                     * of the CALibration/PAGing group are protected and will
                                                     * return an ERR_ACCESS_LOCKED upon an attempt to execute the
                                                     * command without a previous successful GET_SEED/UNLOCK
                                                     * sequence", and likewise for DAQ/STIM and PGM. It was cited
                                                     * here as 1.7.3.2.2, which is the CAL error TABLE: a narrow
                                                     * citation for a rule that governs every group. 1.6.1.1.3 is
                                                     * also where the mask this branch tests is defined, which is
                                                     * the coherence DD78 relies on.
                                                     *
                                                     * Without this branch the response buffer keeps whatever the
                                                     * previous command left in it and is transmitted anyway, so
                                                     * the master reads a stale positive response to a command the
                                                     * slave refused to run. */
```

- [ ] **Step 7: Add the accumulate test**

Append to `test/seed_key_lifetime_test.py` a test that unlocks CAL_PAG and then DAQ in one session
(configure `resource_protection_calibration_paging=True, resource_protection_data_acquisition=True`;
GET_SEED resource `0x01` then `0x04`, each followed by its own UNLOCK, since DD81 requires a fresh
seed per unlock) and asserts that a `MASK_CAL_PAG` command **and** GET_STATUS byte 2 both show
CAL_PAG still granted after the DAQ unlock — i.e. byte 2 reads `0x00`, not `0x01`.

- [ ] **Step 8: Migrate the five status-byte assertions**

In `test/seed_key_defects_test.py`, these five tests assert the protection byte and all encode the
old polarity in a build where nothing is configured protected:

- `test_a_failed_get_seed_leaves_the_resource_locked`
- `test_a_failed_get_seed_does_not_let_a_stale_admission_grant_the_resource_it_requested`
- `test_a_legitimate_multi_frame_get_seed_and_unlock_sequence_still_unlocks_the_resource`
- `test_an_unlock_whose_calc_key_fails_answers_an_error_instead_of_a_stale_positive_response`
- `test_a_failed_unlock_does_not_leave_a_stale_answer_for_whatever_reads_it_next`

Each must gain `resource_protection_programming=True` on its handle (buildable since Task 3) so the
resource it exercises is genuinely protected, and each assertion inverts: "granted" becomes byte 2
== `0x00`, "still locked" becomes byte 2 == `0x10`. **Update each docstring to match** — several
state the expected value in prose, and a docstring that contradicts its assertion is worse than none.

- [ ] **Step 9: Run the full suite**

Expected: green. Any remaining failure is a reader of the old polarity that Steps 4 and 8 missed;
report it rather than adjusting the test to match whatever the code now does.

- [ ] **Step 10: Mutation-verify a reporting site**

Change `GET_STATUS`'s byte 2 back to reporting the granted set (`(uint8)(~Xcp_GetLockedResources())`
is not equivalent — use `Xcp_Ptr->general->protectedResource & (uint8)(~Xcp_GetLockedResources())`)
and confirm `test_get_status_reports_which_resources_are_still_protected` fails. Restore.

Also mutate the gate: change `== 0x00u` to `!= 0x00u` and confirm
`test_a_protected_command_is_refused_before_any_unlock` fails. Restore.

- [ ] **Step 11: Commit**

```bash
git add source/Xcp.c source/Xcp_Std.c source/Xcp_Internal.h test/seed_key_lifetime_test.py test/seed_key_defects_test.py
git commit -m "fix: pre-existing inverted resource protection mask in shipped GET_STATUS and UNLOCK"
```

---

## Final verification

- [ ] Full `./test.sh` in the container on a clean build tree, both ctest targets green.
- [ ] All four required mutation verifications recorded, each naming the test that failed — plus the two honest negatives Task 1 Step 7 and Task 2 Step 5 may produce.
- [ ] `git log --grep="^fix: pre-existing"` lists the three defect commits from this branch.
- [ ] The `resource_protection.data_stimulation` refusal still fires with its test unmodified.
- [ ] Update `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`, which is stale: it still names SP2d as next, though SP2d (#12), SP3, SP4a (#16) have landed and SP4b is in review. Fold this into the final commit, matching the pattern of PRs #5 and #8.

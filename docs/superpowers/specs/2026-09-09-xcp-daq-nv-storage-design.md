# SP5-NV — non-volatile DAQ storage — design

**Date:** 2026-09-09
**Status:** design, approved in outline; not yet planned or implemented
**Scope decision:** storage only. RESUME mode is a later phase — see DD102.

Everything the module refuses today because it keeps no non-volatile DAQ configuration:
`SET_REQUEST`'s `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ`, the session configuration id stored and cleared
alongside them, and the `GET_STATUS` byte pair that reports it. D9 closed the *misreporting* by
refusing these modes outright; this is what lets them be accepted.

---

## 0. Specification numbering, and a rule this branch family learned the hard way

Every citation below was read in the 1.0 PDF via `pdftotext -layout`, or in the 1.1 OCR text where
1.1 is the authority, before being written down.

| Cited as | Actual title |
|---|---|
| 1.0/§1.6.1.2.3 | Request to save to non-volatile memory (`SET_REQUEST`) |
| 1.0/§1.6.1.1.3 | Get current session status from slave (`GET_STATUS`) |
| 1.0/§1.6.4.1.1.4 | Set mode for DAQ list (`SET_DAQ_LIST_MODE`) |
| 1.0/§1.7.3.2.1, 1.1/§1.7.3.2.1 | Standard commands (STD) — the error/pre-action table |
| **1.1**/§1.6.4.1.2.4 | Get general information on DAQ processor (`GET_DAQ_PROCESSOR_INFO`) |

**Always write the revision, never a bare section number.** That last row is why. In **1.0**,
§1.6.4.1.2.4 is "Get general information on DAQ processing *resolution*" — a different command;
1.1 inserted a subsection and renumbered everything after it. The module's existing citation is
correct *only* because it says `1.1/1.6.4.1.2.4`.

**And check both revisions for added error codes, not only for renumbering.** This design initially
concluded that nothing could be reported during the read window described in DD101, because 1.0's
`GET_STATUS` row carries a timeout entry and no error codes at all. That is true of 1.0 and false of
1.1, which added `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` to `GET_STATUS`, `CONNECT(NORMAL)`,
`SYNCH`, `GET_COMM_MODE_INFO`, `GET_ID` and others. The wrong conclusion survived one grep because
the 1.1 OCR misaligns those table columns. It was caught in review, not by the search that produced
it.

---

## 1. What is refused today

`Xcp_DTOCmdStdSetRequest` (`source/Xcp_Std.c`) refuses any mode bit but `STORE_CAL_REQ` with
`ERR_OUT_OF_RANGE`, which 1.0/§1.6.1.2.3 prescribes for an unsupported mode. It ignores the session
configuration id in bytes 2–3, under a comment saying there is "nowhere to store it and nothing to
validate it against". `GET_STATUS` reports that id as a hardcoded `0x00, 0x00`.

`GET_DAQ_PROCESSOR_INFO` reports `RESUME_SUPPORTED` clear, and `SET_DAQ_LIST_MODE` refuses the
RESUME bit — consistently, and its own comment says so: *"RESUME and BIT_STIM remain unimplemented
and so remain reported unsupported, which is what lets `SET_DAQ_LIST_MODE` refuse the matching mode
bits."*

**Correction, made in the final review's fix wave (F4).** `SET_DAQ_LIST_MODE` does not refuse the
RESUME bit and has not since commit `13f59c2`: bit 7 is don't-care in the request layout in both
revisions, so a request carrying it is accepted, not refused. The quoted comment
(`source/Xcp_Daq.c`) was itself wrong in exactly the way DD102 below corrects —
`XCP_DAQ_LIST_MODE_REQ_UNSUPPORTED` (`source/Xcp_Internal.h`) is `ALTERNATING` alone; RESUME is bit
7 of the **response** layout, and BIT_STIM is a `DAQ_PROPERTIES` capability bit, not a mode bit at
all, so neither is a bit `SET_DAQ_LIST_MODE` could refuse in the first place. What is true, and
what DD102 states correctly: RESUME is never *honoured* — `GET_DAQ_LIST_MODE` never reports it set
— which is a different claim from being refused. See DD102's own correction for the full
two-layout account.

---

## 2. Design decisions

### DD94 — the integrator queries; the module does not serialise

`Xcp_GetSegmentFreezeState` (`interface/Xcp.h`) is the precedent, and it is exactly this problem
already solved once: for calibration the module hands over **no data buffer**. It exposes a query
the integrator calls to learn what to store, and the integrator persists it from its own knowledge
of the memory.

DAQ storage mirrors that. Two polled operations, and four read-only accessors:

```c
Std_ReturnType Xcp_StoreDaqConfiguration(uint16 sessionConfigurationId, uint8 *pStatusCode);
Std_ReturnType Xcp_ClearDaqConfiguration(uint8 *pStatusCode);

boolean        Xcp_GetDaqListSelectedState(uint16 daqListNumber);
uint8          Xcp_GetDaqListOdtCount(uint16 daqListNumber);
uint8          Xcp_GetOdtEntryCount(uint16 daqListNumber, uint8 odtNumber);
Std_ReturnType Xcp_GetOdtEntry(uint16 daqListNumber, uint8 odtNumber, uint8 odtEntryNumber,
                               Xcp_OdtEntryType *pEntry);
```

**The rejected alternatives, and what each would have cost.** Serialising a typed block would make
the module hold a *second* copy of the DAQ configuration — roughly 3.5 KB of ODT entries for a
default dynamic pool, for the lifetime of the ECU — and would commit the module to a storage format
it must version forever. Streaming per-element callbacks avoids the buffer but multiplies the
asynchronous surface by the number of ODT entries, which is the wrong direction given DD95.

Accessors cost neither. They expose state the module already holds — selection is already
`XCP_DAQ_LIST_MODE_SELECTED` — and leave the NVM layout to the party that knows it.

### DD95 — a request bit clears on every exit, including a failed one

**This is the hazard that dominates the design, and it is not hypothetical.** The `ERR_PGM_ACTIVE`
gate in `Xcp_CanIfRxIndication` refuses every command whose `Xcp_CTOErrorMatrix` row carries that
bit — 42 rows in the default build, 38 with flash programming enabled (four rows carry the bit only
with that gate off — counted from the matrix's own initializer entries per preprocessor branch, not
by grepping the macro name, which also matches the dispatch gate's own uses), `DISCONNECT` among
them — while any of the three request bits is set. DD77/R1 found
`STORE_CAL_REQ` able to wedge exactly that way: an integrator whose NVM write never *completes*
returns `E_NOT_OK` forever and holds the bit. Adding two more such bits triples that exposure.

So: **`E_OK` with a non-zero status code is still an exit.** The request was attempted and
concluded; the bit clears and the failure is the integrator's to surface. Only `E_NOT_OK` holds the
bit, because that means "still working".

**What this design does not pretend to solve:** an integrator that returns `E_NOT_OK` forever. That
is not an exit path the module can guarantee — it is the absence of one. No poll-count bound is
imposed, because the module has no honest basis for choosing one: `Xcp_MainFunction` is cyclic
(SWS_Xcp_00824) but the module may never depend on its period, so "too many polls" cannot be
converted into "too long". Its blast radius is bounded by DD77/R1 — `CONNECT` re-clears the request
bits, so a reconnect recovers where once only a power cycle did.

### DD96 — calibration already implements DD95's rule; nothing is aligned

**This entry exists to record a check, not a change.** An earlier draft of this design asserted that
`STORE_CAL_REQ` "clears only on `E_OK`" and treated that as a defect to fix alongside the new bits.
Reading `Xcp_MainFunction` before planning showed the assertion was true and the conclusion wrong:

```c
if (Xcp_StoreCalibrationDataToNonVolatileMemory(&store_calibration_status) == E_OK) {
    Xcp_Internal.session_status &= ~XCP_SESSION_STATUS_MASK_STORE_CAL_REQ;
    /* pushes EV_STORE_CAL carrying store_calibration_status */
}
```

`E_OK` means *finished*, whatever the status code says, so a completed-but-failed store already
clears the bit and already reports the failure in the event payload. That is DD95's rule, already
in the module. The two new bits copy it rather than improve on it.

The residual exposure — a callback returning `E_NOT_OK` forever — is identical for all three bits,
is what DD95 declines to solve, and is bounded for all three by DD77/R1's `CONNECT` reset.

**A regression test is still worth having** for all three bits (§5.2), because nothing currently
pins this behaviour for calibration: the rule is implemented but untested, and a later change could
narrow the clear to a zero status code without any test objecting.

### DD97 — the store's ordering, and how a partial store becomes detectable

1.0/§1.6.1.2.3 imposes an order: *"Upon saving, the slave first has to clear any DAQ list
configuration that might already be stored in non-volatile memory."* Under DD94 the integrator does
the storing, so that ordering is a stated obligation in its contract.

**The session configuration id doubles as the validity marker.** The module passes it in — it
arrives in `SET_REQUEST` bytes 2–3 — and the contract requires it be **committed last**, after the
lists. A store interrupted midway therefore leaves no id, and DD100's read reports no valid stored
configuration rather than a half-written one a master would take for complete. This answers the
atomicity hazard using a value the protocol already carries, at no cost.

### DD98 — `CLEAR_DAQ_REQ`'s postcondition, stated observably

1.0/§1.6.1.2.3 specifies the result: every ODT entry reset to `address = 0, extension = 0,
size = 0, bit_offset = 0xFF`, and the session configuration id reset to `0`. Since the integrator
owns the NVM layout, the contract states this as an **observable postcondition** — after a
successful clear, a subsequent read reports no valid stored configuration and id `0` — rather than
dictating byte patterns in memory the module never sees.

### DD99 — the session configuration id: four writes, and one place it must not be written

The id becomes module state, reported by `GET_STATUS` bytes 4–5 (1.0/§1.6.1.1.3), which today
hardcode `0x00, 0x00`. `SET_REQUEST` stops ignoring bytes 2–3. No validation: the specification
gives the id the full `uint16` range and reserves no values.

| Event | Effect |
|---|---|
| `Xcp_Init` → DD100's read completes | adopted from storage |
| `STORE_DAQ_REQ` completes **successfully** | adopted from the request |
| `CLEAR_DAQ_REQ` completes successfully | reset to `0` |
| a store or clear that **fails** | unchanged |

**A completed store or clear takes precedence over a later-completing start-up read.** The table
above lists four writes with no ordering between them, but the first row and the two below it can
race: DD100's read is polled independently of `STORE_DAQ_REQ`/`CLEAR_DAQ_REQ`, and nothing stopped
it from completing — adopting whatever non-volatile memory held when *its own* job started — after
a store or clear had already committed a newer id. Because DD97 requires the id be committed last,
a store or clear that has completed means non-volatile memory already reflects the master's own
most recent write, and anything an in-flight read still returns is stale by construction. So a
store or clear completing with a **zero** status also retires an outstanding read —
`session_configuration_id_read_state` moves `OUTSTANDING` to `COMPLETE` without adopting anything
through it — rather than leaving it to complete later and overwrite the id just adopted. A store or
clear completing with a **non-zero** status leaves the read polling: non-volatile memory is
unchanged, so the read's eventual answer is still the right one to adopt. The existing three-state
`Xcp_NvReadStateType` (`source/Xcp_Internal.h`) expresses this; no new state is needed.

**`CONNECT` must not touch it.** DD77/R1 made `CONNECT` clear the three request bits, and the
instinct will be to reset the id beside them. The bits are session state; the id reflects what is in
non-volatile memory, which a reconnect does not alter. Clearing it would make `GET_STATUS` report
`0` while storage still holds a configuration — the same class of lie as advertising a capability
the module does not have.

### DD100 — the read is polled, not synchronous

An earlier draft had `Xcp_Init` read the stored id synchronously, on the reasoning that `NvM_ReadAll`
has already populated the RAM block by then. **That is an assumption the module can neither verify
nor enforce**, and it fails silently and permanently: whether `NvM_ReadAll` has completed depends on
the EcuM/BswM startup configuration, and it is itself asynchronous. If `Xcp_Init` runs first, the
module adopts `0` and reports it for the life of the ECU with nothing to indicate why.

So the read is polled from `Xcp_MainFunction`, on the same contract as the two operations:

```c
Std_ReturnType Xcp_ReadStoredSessionConfigurationId(uint16 *pSessionConfigurationId,
                                                   uint8 *pStatusCode);
```

`E_OK` with the id when a valid stored configuration exists; `E_OK` with a status code saying none
does when storage is empty; `E_NOT_OK` while storage is not yet readable. The module stops caring
*when* storage becomes ready, because it keeps asking.

The synchronous-query argument was wrong for a reason worth recording: `Xcp_GetSegmentFreezeState`
is synchronous because it reads state the **module already holds**. This reaches into the
integrator's storage, which is what the polled contract exists for.

### DD101 — during the read window, `GET_STATUS` answers `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE`

Until DD100's read completes the module does not know the id, and reporting `0` would be
indistinguishable from a legitimate "nothing stored".

1.1 gives exactly the right answer. `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` (`0x33`, *"access to the
requested resource is temporary not possible"*) is in `GET_STATUS`'s own 1.1/§1.7.3.2.1 row — the
only error code in it — with the prescribed master action **"display error / repeat"**. That is
precisely the semantics: *I cannot answer yet; ask again.* The master retries and succeeds once the
read completes. `XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` is already defined in
`interface/Xcp_Errors.h` and currently unused.

**This behaviour follows 1.1, where 1.0 offers nothing.** `0x33` does not exist in 1.0, whose
`GET_STATUS` row carries only a timeout entry. `Xcp_CTOErrorMatrix[0xFD]` is `0x00u` today,
reflecting 1.0, and gains the bit — declaratively, as DD76 did for `UNLOCK`'s `ERR_GENERIC`, since
only `CMD_BUSY`, `CMD_SYNTAX` and `PGM_ACTIVE` are behaviourally tested against that table.

The window is short — responses only leave via `Xcp_MainFunction`, so the module has polled at least
once before it can answer anything — but it is not zero, and it is now reportable rather than
papered over.

**What this design does not pretend to solve, and does not try to.** An integrator whose
`Xcp_ReadStoredSessionConfigurationId` returns `E_NOT_OK` forever — a mis-scoped NvM block, one
omitted from `NvM_ReadAll`, an unfinished stub — leaves `session_configuration_id_read_state`
`OUTSTANDING` for the life of the ECU, and `GET_STATUS` refuses `ERR_RESOURCE_TEMPORARY_NOT_
ACCESSIBLE` for exactly as long: a mandatory STD command, permanently unanswerable. **Unlike DD95's
request bits, `CONNECT` does not recover this.** DD99 already settled why: `CONNECT` must not touch
`session_configuration_id`, because it reflects what non-volatile memory holds and a reconnect does
not alter that — and abandoning the read on `CONNECT` would mean adopting `0x0000` in its place,
which is precisely the fabricated answer this refusal exists to prevent. Nor does this design
impose a poll-count bound: `Xcp_MainFunction` is cyclic (SWS_Xcp_00824) but the module may never
depend on its period, the identical reasoning DD95 already gives for the request bits — "too many
polls" cannot be converted into "too long" here either. A permanently unanswerable mandatory
command is a worse-looking failure mode than DD95's — `GET_STATUS` is not one command among 42, it
is the one command the specification's own error table names "repeat" for — but the alternative is
reporting a session configuration id the module does not yet have, and fabricating that answer is
the one lie DD97 through DD100 were written to avoid. The residual risk is therefore an integrator
contract issue, not a protocol one: `Xcp_ReadStoredSessionConfigurationId`'s own declaration
(`interface/Xcp.h`) carries the obligation in writing.

### DD102 — RESUME stays out of scope, and stays unadvertised

This phase builds persistence. RESUME mode — `CONNECT`'s resume handshake,
`XCP_CONNECTION_STATE_RESUME` which is declared but never entered, the RESUME bit `GET_DAQ_LIST_MODE`
reports, and lists starting automatically after power-up — is a later phase.

`RESUME_SUPPORTED` therefore stays clear in `GET_DAQ_PROCESSOR_INFO` (1.1/§1.6.4.1.2.4), and the
module never reports RESUME in `GET_DAQ_LIST_MODE`. That remains coherent: 1.0/§1.6.1.2.3 gates
`STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` on their own support, not on RESUME, so a slave may store
without resuming.

**Correction, made while implementing Task 4.** This decision first read "`SET_DAQ_LIST_MODE` keeps
refusing the RESUME bit". That was wrong, and asserting it would have shipped a false test. The
module keeps two distinct mode layouts, and RESUME exists in only one of them:

| | bit 7 | bit 6 | bit 5 | bit 4 | bit 1 | bit 0 |
|---|---|---|---|---|---|---|
| `XCP_DAQ_LIST_MODE_REQ_*` — the `SET_DAQ_LIST_MODE` **request** | don't care | don't care | PID_OFF | TIMESTAMP | DIRECTION | ALTERNATING |
| `XCP_DAQ_LIST_MODE_*` — the `GET_DAQ_LIST_MODE` **response** | RESUME | RUNNING | PID_OFF | TIMESTAMP | DIRECTION | SELECTED |

The request byte has no RESUME bit to refuse; bits 6 and 7 are don't-care in both revisions, and
commit `13f59c2` stopped refusing them because refusing bits the specification marks don't-care was
over-strict. `XCP_DAQ_LIST_MODE_RESUME` (`source/Xcp_Internal.h:202`) belongs to the response
direction alone.

The load-bearing property is therefore that RESUME is never *honoured*, not that it is *refused*:
a `SET_DAQ_LIST_MODE` carrying bit 7 is accepted, and `GET_DAQ_LIST_MODE` still reports RESUME clear.
That is what the test asserts.

**DD100's read therefore reads without restoring.** The module adopts the session configuration id
and nothing else; it does not rebuild DAQ lists. A slave coming up with lists this session's master
never configured is RESUME's behaviour, and RESUME is advertised unsupported — restoring them while
reporting `RESUME_SUPPORTED` clear is the incoherence this decision exists to avoid.

---

## 3. What this does not change

- `RESUME_SUPPORTED`, `SET_DAQ_LIST_MODE`'s RESUME refusal, and `CONNECT`'s modes.
- The live DAQ lists: nothing is restored into them.
- `STORE_CAL_REQ`'s own store path, beyond DD96's one-condition alignment.
- `Xcp_GetSegmentFreezeState` and the calibration accessors it belongs to.

**Correction (F4), on the first bullet above.** "`SET_DAQ_LIST_MODE`'s RESUME refusal" is not a
behaviour that exists to leave unchanged — `SET_DAQ_LIST_MODE` accepts the RESUME bit, and always
has since commit `13f59c2`; see DD102's own correction. What this phase genuinely leaves unchanged
is `RESUME_SUPPORTED` staying clear and the bit going unhonoured — `GET_DAQ_LIST_MODE` never
reports it set. The bullet is left as originally written rather than silently rephrased, per the
same annotation style DD102 and §1 use.

---

## 4. Test strategy

**The denial of service gets its own test, and it is the acceptance bar.** A store completing with a
failure status must clear the request bit — assert a subsequent `DISCONNECT` is **not** refused
`ERR_PGM_ACTIVE`. That is the exact defect DD77/R1 found live for `STORE_CAL_REQ`, and a happy-path
test would not have caught it there either. The same test exists for `CLEAR_DAQ_REQ` and, after
DD96, for `STORE_CAL_REQ`.

**The id's four writes are pinned separately, and so is the write that must not happen**: `CONNECT`
clears the request bits and leaves the id standing (DD99). That is the assertion most likely to be
broken by a later change, because the instinct is to reset everything at the session boundary.

**The accessors are exercised under `DAQ_DYNAMIC` after a runtime allocation**, not only
`DAQ_STATIC`. Under static they would return generator constants, and a broken accessor could still
look right.

**DD101's window is testable** with a read double that reports "not yet readable" for a fixed number
of polls: `GET_STATUS` answers `(0xFE, 0x33)` while it does, and the id afterwards.

**One honest limit.** The clear-then-store ordering and the commit-id-last rule (DD97) are
*integrator* obligations. The module can pin that it passes the id and that its own callbacks fire
in the right sequence; it cannot test that the integrator honours the ordering. The spec says so
rather than implying coverage.

Every fix mutation-verified, and per term for compound conditions. `Xcp_Internal` is not reachable
from the CFFI harness, so every assertion observes transmitted bytes or callback arguments.

---

## 5. Acceptance

1. `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` are accepted, each reaching its callback, each raising its
   event (`EV_STORE_DAQ`, `EV_CLEAR_DAQ`) on success.
2. **A completed-but-failed request clears its bit, for all three**: a store or clear returning
   `E_OK` with a non-zero status code clears the request bit, and a `DISCONNECT` immediately
   afterwards is answered rather than refused. Tested for `STORE_DAQ_REQ`, `CLEAR_DAQ_REQ` and —
   as a regression pin on behaviour that exists but is untested — `STORE_CAL_REQ` (DD96).
3. The store passes the session configuration id from `SET_REQUEST` bytes 2–3, and the id is adopted
   only on success.
4. `GET_STATUS` reports the id in bytes 4–5, `0` after a successful clear, and **unchanged across a
   `CONNECT`**.
5. During DD100's read window `GET_STATUS` answers `(0xFE, 0x33)`, and the id once it completes.
6. The four accessors report the live configuration under `DAQ_DYNAMIC` after the master has
   allocated and configured lists at runtime.
7. `RESUME_SUPPORTED` is still clear and `SET_DAQ_LIST_MODE` still refuses the RESUME bit (DD102).

   > **Correction (F4).** `SET_DAQ_LIST_MODE` does not refuse the RESUME bit and this branch does
   > not make it start to — bit 7 is don't-care in the request layout and is accepted, not refused,
   > since commit `13f59c2`, which predates this plan. What this branch actually delivers and
   > verifies, per DD102's own correction: `RESUME_SUPPORTED` stays clear, and the bit is accepted
   > without being *honoured* — `GET_DAQ_LIST_MODE` never reports it set regardless of what
   > `SET_DAQ_LIST_MODE` was sent. `test/daq_nv_storage_test.py::test_resume_stays_unadvertised_
   > and_unhonoured_after_this_task` asserts exactly that, not a refusal.
8. Mutation verifications carried out and recorded, each naming the test that failed.
9. `./test.sh` green in the CI container, both ctest targets, on a clean build tree.

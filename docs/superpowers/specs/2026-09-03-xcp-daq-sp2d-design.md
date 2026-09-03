# SP2d — Dynamic DAQ list configuration

**Status:** design approved 2026-09-03. Implements the four dynamic configuration commands and the
`DAQ_CONFIG_TYPE = dynamic` branch.

**Predecessors:** SP2a (static DAQ lists, the command surface), SP2b (optional commands, the
timestamp field, `PID_OFF`). SP2c — DAQ list prioritisation and more than one outstanding DTO
frame — is deliberately *not* a predecessor; it was deferred because it buys no conformance, and
nothing here depends on it.

---

## 0. Which specification numbering this document uses

Citations are to **XCP Part 2 — Protocol Layer Specification 1.1** unless a citation names 1.0,
matching SP2a and SP2b. §0 of the SP2a design records that 1.0 and 1.1 renumber §1.6.4 wholesale
and carries the mapping table; it already covers all four commands here, and is not repeated. In
short: dynamic configuration is §1.6.4.2 in 1.0 and §1.6.4.3 in 1.1.

The command codes, byte layouts and error codes are identical in both revisions.

One practical note, as in SP2b. The 1.1 PDF in `docs/external/` is a scan and its OCR is
unreliable; the 1.0 PDF is text and extracts cleanly. Every quotation and every table-shaped claim
in this document was therefore read from the 1.0 text and is cited by its 1.1 number. The defect
fixed in PR #9 came from reasoning about a bit table through that OCR, so where a layout matters,
read the 1.0 text or render the 1.1 page rather than trusting the transcription.

---

## 1. Scope

**In:**

- `FREE_DAQ` (0xD6), `ALLOC_DAQ` (0xD5), `ALLOC_ODT` (0xD4), `ALLOC_ODT_ENTRY` (0xD3),
  the four commands of §1.6.4.3.1.
- A build-time choice between static and dynamic DAQ list configuration.
- The `DAQ_CONFIG_TYPE` bit in `DAQ_PROPERTIES`, currently hard-cleared.
- Correcting `XcpOdtCount` and `XcpOdtEntriesCount`, which the generator currently emits with the
  wrong meaning (§8).

**Out:**

- DAQ list prioritisation and multiple outstanding DTO frames (SP2c).
- STIM (SP3), non-volatile DAQ storage and RESUME (SP5-NV).
- Distinct TX PDUs per dynamic DAQ list. See DD31 for the consequence and §9 for the follow-up.

---

## 2. What already exists

More than expected. SP2a laid most of the groundwork and left it unpopulated:

| Thing | State |
|---|---|
| `Xcp_DaqConfigTypeType`, with `XCP_DAQ_STATIC` / `XCP_DAQ_DYNAMIC` | declared, hard-coded to `DAQ_STATIC` in the generator |
| `Xcp_GeneralType.daqCount`, `.odtCount`, `.odtEntriesCount`, `.minDaq` | declared; `odtCount` and `odtEntriesCount` read by no `.c` file |
| `Xcp_CTOErrorMatrix` rows for 0xD3–0xD6 | present, carrying `SEQUENCE` and `MEMORY_OVERFLOW` where the spec needs them |
| `ctoInfo` enable/protected bits and minimum request sizes for all four | present and correct: `0x06`, `0x05`, `0x04`, `0x01` |
| `Xcp_PIDToCmdGroupTable` entries for all four | present, `XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ` |
| `Xcp_DaqListClearEntries(daqListNumber)` | exists, takes the DAQ exclusive area |
| `Xcp_DaqListTxPduIsExclusive` | exists, added by SP2b for `PID_OFF` |
| Sampling by runtime event binding | already the case; `triggeredDaqListRef` has no runtime role |

The four commands answer `ERR_CMD_UNKNOWN` today, and `test/cmd_unknown_test.py` pins that.

---

## 3. Design decisions

**DD25 — static and dynamic are a build-time choice, not a runtime one.** A slave declares
`DAQ_CONFIG_TYPE` as one bit, so one running slave is one or the other. `daq_config_type` in the
configuration selects which is generated. A STATIC build is byte-for-byte what the module produces
today and pays no ROM for the dynamic path; a DYNAMIC build has no statically declared lists.
Generating both and choosing at initialisation was rejected: it costs ROM and RAM for the unused
model in every build and doubles the state every DAQ handler must reason about.

**DD26 — capacity is AUTOSAR's rectangle, not a fungible pool.** AUTOSAR defines, in `XcpGeneral`
with ECU scope:

- `XcpDaqCount` (ECUC_Xcp_00012) — "the number of DAQ lists for dynamic configuration", 0..65535
- `XcpOdtCount` (ECUC_Xcp_00054) — "the amount of ODTs **of a DAQ list** using dynamic DAQ list
  configuration", 0..252
- `XcpOdtEntriesCount` (ECUC_Xcp_00059) — "the amount of entries **into an ODT** using dynamic DAQ
  list configuration", 0..255

All three are "available only if XcpDaqConfigType is set to DAQ_DYNAMIC". So capacity is
`daq_count` × `odt_count` × `odt_entries_count`, reserved in full, and `ERR_MEMORY_OVERFLOW` means
a request exceeded its own declared cap.

An earlier draft of this design proposed aggregate totals divided freely between lists, which
would let one list take eight ODTs where another took two. That is not the AUTOSAR model, and it
makes allocation failure depend on the order the master allocates in rather than on a declared
per-list cap. Reserving the full rectangle costs RAM in the corners a master never uses; that cost
buys an allocation that cannot fail while every request stays inside its cap.

**DD27 — the DAQ list descriptor becomes mutable rather than indirect.** `ALLOC_*` writes the
descriptor in place; the handlers keep reading the same fields and see values that changed at
runtime.

Two implementation facts, both established by reading the code rather than assumed:

- **The arrays are already declared non-`const`.** `static Xcp_DaqListType Xcp_DaqListConfigNN[]`
  and `static Xcp_OdtType Xcp_OdtConfigNNDaqNN[]` carry no `const` keyword. What places them in
  flash is the AUTOSAR MemMap section around them — `Xcp_START_SEC_CONST_UNSPECIFIED`. So the
  build-time difference is a **MemMap section**, not a `const` qualifier: DYNAMIC emits these two
  arrays into a VAR section, STATIC leaves them exactly where they are. The ODT *entry* arrays are
  already in `Xcp_START_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED`, because `WRITE_DAQ` writes them.
- **The `const` that must go is on the struct members** — `Xcp_DaqListType.number`, `.firstPid`,
  `.maxOdt`, `.maxOdtEntries` and `Xcp_OdtType.odtNumber`. A struct definition cannot differ
  between builds without an `#if` in the header, which would create a type variant the CFFI
  harness compiles separately, so these lose `const` in **both** builds. STATIC keeps its flash
  placement regardless, since that comes from MemMap.

**Cost, counted rather than estimated.** The fields the allocator writes are read at 16 code sites:
`.maxOdt` at 7, `.maxOdtEntries` at 7, `.firstPid` at 2. Of those, only the 7 `.maxOdtEntries`
sites change, and for the reason in DD34 rather than for this decision. An earlier draft of this
document put the figure at 62 and called them all bounds checks; that came from grepping comments
along with code, and is corrected here.

The alternative — accessor functions resolving to the const table or to pool state — separates the
two models more cleanly, but converts every one of those sites in the area where this codebase's
defects have clustered, and buys no capability the mutable descriptor lacks.

**DD28 — the allocation state machine refuses exactly what the specification enumerates, and
nothing more.** §1.6.4.3.1 lists six `ERR_SEQUENCE` cases. They reduce to four states and this
table:

| command | accepted from | moves to |
|---|---|---|
| `FREE_DAQ` | any | `FREE` |
| `ALLOC_DAQ` | `FREE`, `DAQ` | `DAQ` |
| `ALLOC_ODT` | `DAQ`, `ODT` | `ODT` |
| `ALLOC_ODT_ENTRY` | `ODT`, `ODT_ENTRY` | `ODT_ENTRY` |

**The initial state is `FREE`.** §1.6.4.3.1.1 says the master "always first has to send a
FREE_DAQ", but that is a requirement on the master, and the slave's enumerated refusals do not
include an `ALLOC_DAQ` with no preceding command. Nothing is allocated at that point, so accepting
it is well-defined. Defect D9 was the module accepting a mode it could not fulfil; the discipline
that fixed it — refuse what the specification authorises refusing, and only that — says equally
that a refusal absent from the list should not be invented.

**Repeats accumulate.** `ALLOC_DAQ` after `ALLOC_DAQ`, and `ALLOC_ODT` after `ALLOC_ODT`, are
permitted by their omission from the refusal list. Each call adds to what is allocated, and
`ERR_MEMORY_OVERFLOW` is measured against the running total. Treating a repeat as a replacement
would make the permitted repeat meaningless.

**Error precedence:** `CMD_SYNTAX` (length, enforced by the dispatcher from `ctoInfo`) →
`SEQUENCE` → `OUT_OF_RANGE` → `MEMORY_OVERFLOW`. Sequence precedes the argument checks because it
is a statement about the command stream rather than about this command's arguments.

**DD29 — `FREE_DAQ` stops a running DAQ rather than refusing.** `Xcp_CTOErrorMatrix` gives 0xD6
only `CMD_BUSY | PGM_ACTIVE | CMD_UNKNOWN | CMD_SYNTAX`; `ERR_DAQ_ACTIVE` is absent, so refusing a
running slave is not authorised. `FREE_DAQ` stops every running list, frees, and clears
`DAQ_RUNNING` through the existing `Xcp_DaqSessionStatusUpdate`.

**DD30 — freeing unwinds in the reverse of allocation, inside the DAQ exclusive area.**
`Xcp_TriggerEventChannel` runs in interrupt context and reaches entry storage by walking `maxOdt`
and then each ODT's entry count. Freeing must never leave a count that outlives the storage it
describes — the DD14 failure class. So `FREE_DAQ` stops the lists first, so no new sampling
begins; then zeroes the per-list `maxOdt` and per-ODT entry counts; then resets the pool cursors.
A trigger interleaved at any point sees a zero count and samples nothing, rather than a stale
count into released storage.

`FREE_DAQ` must also clear `Xcp_DaqListRt` — mode, prescaler, prescaler counter, priority and
`eventChannelNumber`. These live in a separate array from the descriptor, so "free the descriptor"
is not sufficient: a freed-then-reallocated list would otherwise start with a binding the master
never set for it.

**DD31 — `firstPid` is a prefix sum over list index, recomputed whenever ODT counts change.**
Assigning PIDs in call order fails under DD28's accumulate rule: `ALLOC_ODT(0, 2)`,
`ALLOC_ODT(1, 3)`, `ALLOC_ODT(0, 1)` leaves list 0 needing three contiguous PIDs when list 1
already owns 2..4. Since the absolute ODT number is `firstPid + relative`, contiguity is required.
`firstPid[i] = Σ maxOdt[0..i-1]` is order-independent, contiguous by construction, and `O(daq_count)`
to recompute. It is also exactly what the generator does for STATIC at `script/source_cfg.c.jinja2`,
so both models compute `firstPid` the same way — one at generation, one at allocation.

The ceiling is 252: slave-to-master PIDs `0xFC..0xFF` are `SERV`, `EV`, `ERR` and `RES`, leaving
`0x00..0xFB`. `ALLOC_ODT` answers `ERR_MEMORY_OVERFLOW` when the new total would pass it, and
rejects the request whole rather than applying part of it — a partially applied allocation leaves
counts the master does not know about.

This ceiling is checked at runtime rather than at generation. Guarding `daq_count × odt_count ≤ 252`
in the template would reject configurations a master can use perfectly well, since a master rarely
allocates the full rectangle. Storage is fully reserved and so can never overflow; the PID space
is the only exhaustible resource, and it fails where the master can see it.

**DD32 — one runtime list count serves both models.** `Xcp_DaqListIsValid` bounds against a
runtime `allocatedDaqCount`, initialised to `daqCount` in a STATIC build and to `0` in a DYNAMIC
one, then raised by `ALLOC_DAQ`. This is what makes DD27 pay: all 14 handlers keep calling the same
predicate unchanged.

It also gives `ALLOC_ODT` the right range for free. The spec's `[MIN_DAQ, MIN_DAQ+DAQ_COUNT-1]` is
over what `ALLOC_DAQ` allocated, not over the configured pool, so a list inside the pool but not
yet allocated is "not available" and answers `ERR_OUT_OF_RANGE`. The same holds one level down:
ODT and entry numbers are already bounded against `maxOdt` and `maxOdtEntries`, which are zero
until allocated. **SP2d adds no new bounds check anywhere.**

**DD33 — `MAX_DAQ` reports the configured pool, not the allocated count.** ECUC_Xcp_00164's
dependency is `MAX_DAQ = MIN_DAQ + DAQ_COUNT`, and `minDaq` is 0. Reporting the allocated count
would tell a master nothing before it allocates, which is precisely when it needs to know how much
it may ask for.

**DD34 — `Xcp_OdtType` gains a per-ODT entry count.** `ALLOC_ODT_ENTRY` assigns entries to *one
ODT*, but the module has no per-ODT count: every entry bound goes through the per-list
`daqList[n].maxOdtEntries`, at 7 code sites. That field cannot express "ODT 0 has four entries and
ODT 1 has two", so allocating per ODT is not representable without a new field.

`Xcp_OdtType` therefore gains `uint8 entryCount` — how many entries this ODT has — while
`daqList[n].maxOdtEntries` keeps its present meaning as the cap any one ODT in the list may reach
(`odt_entries_count` under DYNAMIC). The 7 bound sites move from the list field to the ODT field.

**STATIC behaviour is provably unchanged**: the generator initialises every ODT's `entryCount` to
that list's `max_odt_entries`, so each of the 7 checks compares against exactly the value it
compares against today. This is the only place SP2d edits an existing bounds check, and it does so
by changing which field is read, not the comparison — DD32's claim that SP2d adds no new bounds
check stands.

---

## 4. Configuration model

### 4.1 New keys

`configurations[x].protocol_layer.daq_config_type`: `"STATIC" | "DYNAMIC"`, default `"STATIC"`, so
every existing configuration keeps working untouched (ECUC_Xcp_00164).

When it is `"DYNAMIC"`, a sibling `configurations[x].daq_dynamic` object is required and
`configurations[x].daqs` must be absent:

```json
"daq_dynamic": {
  "daq_count": 4,
  "odt_count": 8,
  "odt_entries_count": 16,
  "pdu_mapping": "XCP_PDU_ID_TRANSMIT"
}
```

`pdu_mapping` exists because dynamic lists have no `daqs[n]` entry to carry one. A single shared TX
PDU matches what `config/xcp.json` already does for its two static lists.

`configurations[x].events[y].triggered_daq_list_ref` is forbidden under DYNAMIC: it names entries
in `daqs`, which is absent.

### 4.2 Schema validation

JSON Schema `if/then` enforces the pairing, so a configuration can declare neither model nor both.

---

## 5. Command specifications

### 5.1 FREE_DAQ — 0xD6 (§1.6.4.3.1.1)

Request is one byte. Clears all DAQ lists and frees every allocated list, ODT and ODT entry.

Per DD29 it never answers `ERR_DAQ_ACTIVE`; per DD30 it stops the lists, zeroes counts, resets
cursors and clears `Xcp_DaqListRt`, in that order, inside the DAQ exclusive area. Moves the state
machine to `FREE` from any state. Positive response is one byte.

### 5.2 ALLOC_DAQ — 0xD5 (§1.6.4.3.1.2)

Bytes 2,3 are `DAQ_COUNT`, read with the configured byte order.

- `ERR_SEQUENCE` from `ODT` or `ODT_ENTRY`.
- `ERR_MEMORY_OVERFLOW` when `allocatedDaqCount + DAQ_COUNT > daq_count`.
- Otherwise raises `allocatedDaqCount` by `DAQ_COUNT` and moves to `DAQ`.

### 5.3 ALLOC_ODT — 0xD4 (§1.6.4.3.1.3)

Bytes 2,3 are `DAQ_LIST_NUMBER`; byte 4 is `ODT_COUNT`.

- `ERR_SEQUENCE` from `FREE` or `ODT_ENTRY`.
- `ERR_OUT_OF_RANGE` when the list is not allocated (DD32).
- `ERR_MEMORY_OVERFLOW` when the list's `maxOdt + ODT_COUNT > odt_count`, or when the resulting
  total ODT count across all lists would exceed 252 (DD31).
- Otherwise raises that list's `maxOdt`, recomputes every `firstPid` as a prefix sum, and moves
  to `ODT`.

### 5.4 ALLOC_ODT_ENTRY — 0xD3 (§1.6.4.3.1.4)

Bytes 2,3 are `DAQ_LIST_NUMBER`; byte 4 is `ODT_NUMBER`, relative within the list; byte 5 is
`ODT_ENTRIES_COUNT`.

- `ERR_SEQUENCE` from `FREE` or `DAQ`.
- `ERR_OUT_OF_RANGE` when the list is not allocated, or `ODT_NUMBER >= maxOdt` for it.
- `ERR_MEMORY_OVERFLOW` when that ODT's entry count `+ ODT_ENTRIES_COUNT > odt_entries_count`.
- Otherwise raises that ODT's entry count and moves to `ODT_ENTRY`.

---

## 6. Interaction with the existing surface

- **Sampling is unchanged.** `triggeredDaqListRef` has no runtime role; `Xcp_TriggerEventChannel`
  scans lists by their runtime `eventChannelNumber`, which `SET_DAQ_LIST_MODE` sets. Dynamic lists
  bind exactly as static ones do.
- **The sampler keeps iterating the whole pool, and that is correct.** Its loop bound is
  `daq_idx < Xcp_Ptr->general->daqCount` — the configured pool, not `allocatedDaqCount`, and
  `Xcp_DaqListIsValid` is `static` to `source/Xcp_Daq.c` so the sampler could not call it anyway.
  An unallocated list is skipped twice over: it is never `RUNNING`, because `START_STOP_DAQ_LIST`
  is gated by `Xcp_DaqListIsValid` and so refuses it, and its `maxOdt` is zero, so the inner ODT
  loop does not execute. **Do not add a third check here.** It would be redundant, and it would
  put an `allocatedDaqCount` read in interrupt context against a value written by the command
  handlers — a race the current structure does not have.
- **`MAX_DAQ_LIST`** in `GET_DAQ_EVENT_INFO` reports `daq_count` for every event channel under
  DYNAMIC, since any allocated list may bind to any channel.
- **`GET_DAQ_PROCESSOR_INFO`** sets `DAQ_CONFIG_TYPE` from `daqConfigType` instead of leaving it
  clear, and reports `MAX_DAQ` per DD33.
- **`GET_DAQ_LIST_INFO`** reads the descriptor, so it reports runtime `MAX_ODT` and
  `MAX_ODT_ENTRIES` with no change.
- **`START_STOP_DAQ_LIST`** already returns `FIRST_PID` from the descriptor and needs no change; it
  reads a value assigned at allocation rather than at generation.
- **`CLEAR_DAQ_LIST` and `FREE_DAQ` stay distinct.** `CLEAR_DAQ_LIST` clears one list's entries and
  keeps its allocation. Its behaviour is unchanged in both models.
- **`SET_DAQ_PTR` and `WRITE_DAQ` against an unallocated list** are refused by the bounds checks
  that already exist, since `maxOdt` is zero.
- **`PID_OFF` under DYNAMIC is available only while exactly one list is allocated.** All dynamic
  lists share the configured `pdu_mapping`, so SP2b's rule applies unchanged:
  `Xcp_DaqListTxPduIsExclusive` is true only while no other list shares that PDU. This is honest
  rather than restrictive — with one CAN-ID and several lists, §1.1.2.1 identification genuinely
  cannot be recovered without a PID.

---

## 7. Source layout

- `source/Xcp_Daq.c` — the four new handlers, the state machine, the prefix-sum recomputation.
- `source/Xcp_Internal.h` — the allocation state enum, `allocatedDaqCount`.
- `source/Xcp.c` — reset of the allocation state in `Xcp_Init`, and the `FREE_DAQ` PID table entry.
- `source/Xcp_Std.c` — DISCONNECT calls the same unwind `FREE_DAQ` does (`Xcp_DaqFreeAll`), so a
  master that allocates and disconnects without freeing does not leave its allocation for the next
  one to accumulate onto (XCP part 1 — Overview 1.0/2.3).
- `interface/Xcp_Types.h` — `const` dropped from the descriptor members the allocator writes,
  and `uint8 entryCount` added to `Xcp_OdtType` (DD27, DD34).
- `script/source_cfg.c.jinja2`, `script/header_cfg.h.jinja2` — §8.
- `config/xcp.schema.json` — §4.

---

## 8. Generator and schema changes

- `XcpDaqConfigType` becomes derived rather than the hard-coded `DAQ_STATIC`, whose comment says
  dynamic "arrives in SP2c" and is stale twice over.
- `XcpDaqCount` stays `daqs|length` under STATIC and becomes `daq_count` under DYNAMIC.
- **`XcpOdtCount` and `XcpOdtEntriesCount` get their AUTOSAR meaning.** The generator currently
  emits the sum of `max_odt` across all lists, and the sum of `max_odt × max_odt_entries`,
  into fields AUTOSAR defines as ODTs *per list* and entries *per ODT*, and defines only for
  `DAQ_DYNAMIC`. No `.c` file reads either field, so this corrects a latent wrong value rather than
  changing behaviour — but SP2d is what would otherwise start relying on the wrong reading. They
  become `0` under STATIC and `odt_count` / `odt_entries_count` under DYNAMIC.
- The `Xcp_DaqListType` and `Xcp_OdtType` arrays are emitted into `Xcp_START_SEC_CONST_UNSPECIFIED`
  under STATIC, exactly as today, and into a VAR section under DYNAMIC, where the allocator writes
  them (DD27). Under DYNAMIC they are zero-initialised and sized `daq_count`, `daq_count ×
  odt_count` and `daq_count × odt_count × odt_entries_count` respectively.
- Every ODT's `entryCount` (DD34) is emitted as that list's `max_odt_entries` under STATIC, which
  is what keeps the 7 relocated bound checks comparing against the same value they do today, and
  as `0` under DYNAMIC, where `ALLOC_ODT_ENTRY` raises it.
- The existing `pid.next > 252` guard stays for STATIC. DYNAMIC gets no such generation guard, per
  DD31.

New guards, each aborting rendering:

1. `daq_count > 255` under DYNAMIC — `maxDaqList` is a `uint8` and `MAX_DAQ_LIST` is one byte in
   §1.6.4.1.2.7. Same shape as the existing `triggered_daq_list_ref|length > 255` guard.
2. Any of the four ALLOC APIs enabled under STATIC.
3. Any of the four ALLOC APIs disabled under DYNAMIC — a dynamic build with no way to allocate.
4. `daqs` present under DYNAMIC, or `daq_dynamic` present under STATIC.

`raise` is not a registered Jinja global in `bsw_code_gen`; referencing it aborts rendering with
`UndefinedError`, which is the intended effect, but the message never reaches the caller. The
strings are documentation for whoever reads the template.

---

## 9. Risks

- **The descriptor members lose `const` in both builds** (DD27), so the compiler no longer
  prevents a handler from writing a field it should not. Mitigated by those fields being written
  in exactly one place, the allocator, and by the alternative converting all 16 read sites for no
  extra capability. Flash placement is unaffected: it comes from the MemMap section, which STATIC
  keeps.
- **The sampler race is only partly testable.** §10 says what is covered and what is not.
- **A DYNAMIC build reserves the full rectangle.** An integrator declaring
  `daq_count: 16, odt_count: 32, odt_entries_count: 64` reserves 32768 entry slots. The generator
  does not guard total RAM; that is the integrator's sizing decision, as it is for the static
  model.
- **`PID_OFF` is effectively unavailable under DYNAMIC** beyond a single list (§6). The follow-up,
  if a project needs it, is a TX PDU pool in `daq_dynamic` rather than one `pdu_mapping`. Deferred:
  nothing in the specification requires it and it doubles the configuration surface.

---

## 10. Test strategy

Both variants are exercised through `DefaultConfig(daq_config_type='DYNAMIC', ...)`. This adds a
compilation variant of `Xcp_Daq.c` and `Xcp_DaqRuntime.c`; `script/gcov_union.py` already unions
variant groups, so coverage stays whole rather than collapsing as `Xcp_Daq.c` did to 0.00% during
SP2b.

New files: `free_daq_test.py`, `alloc_daq_test.py`, `alloc_odt_test.py`,
`alloc_odt_entry_test.py`, and `daq_dynamic_acceptance_test.py` doing a full
`FREE → ALLOC → WRITE_DAQ → START → sample → STOP` round trip.

**A 16-cell state machine sweep** — 4 states × 4 commands, 6 refusals and 10 acceptances, each cell
named so a change fails with the cell's name rather than a bare index.

**Three tests come directly from the design work:**

- **PID contiguity.** Allocate ODTs out of order — list 1, then list 0, then more to list 0 — and
  assert `FIRST_PID` blocks are contiguous and non-overlapping. This is the case that ruled out
  call-order assignment in DD31, so it goes in as a named regression from the start.
- **The 252 ceiling.** Allocate to exactly 252 and assert success; ask for one more and assert
  `ERR_MEMORY_OVERFLOW` *and* that the total is unchanged.
- **`FREE_DAQ` clears runtime state.** Allocate, set a mode and event binding, free, reallocate,
  and assert mode, prescaler and `eventChannelNumber` are back to defaults (DD30).

`test/cmd_unknown_test.py` already asserts 0xD3–0xD6 answer `ERR_CMD_UNKNOWN`, which must stay true
for a STATIC build; it gains a DYNAMIC counterpart asserting they no longer do.

**On the sampler race, plainly** (settled in Task 4; this replaces the plan this section carried):
the harness asserts exclusive-area nesting, balance and non-leakage globally on every test, so
DD30's area discipline is checked throughout. Beyond that, `test/free_daq_test.py` covers:

- **The interleaving, at the points where a preemption can actually land.** Driving the trigger
  from `SchM_Exit_Xcp_DtoQueue`'s `side_effect` puts it at each point in the unwind where the DAQ
  exclusive area is *not* held, one point per run, swept over all of them. At every one the
  sampler reads no slave memory and queues no frame: at the first release the ODT's entries have
  been cleared while its counts still describe them, at the second the counts are already zero.
  The sweep's width is pinned by a companion test, so a critical section added to the unwind fails
  loudly rather than silently going unswept.
- **The post-condition.** After `FREE_DAQ` returns, a trigger samples nothing and no frame reaches
  the ring — with a named control test showing the same configuration does sample when `FREE_DAQ`
  does not run, so the post-condition cannot pass vacuously.

**What is deliberately not covered:** a trigger driven from *inside* a held area, i.e. from
`SchM_Enter_Xcp_DtoQueue`'s `side_effect`. It was attempted first, as this section originally
asked. CFFI reentrancy is not the obstacle — the trigger runs — but the scenario is not one the
module can face: `SchM_Enter_Xcp_DtoQueue` exists precisely to suppress the interrupt the sampler
runs in, so a trigger inside the held area models a preemption the exclusive area forbids rather
than one it must survive. The harness agrees, and says so: it records the injection as
`SchM_Enter_Xcp_DtoQueue called while already held` plus an unbalanced exit, because it models the
area as one boolean and cannot distinguish a forbidden preemption from a double-enter defect.
Suppressing those violations to let such a test pass would disable, for that test, the very
invariant the suite relies on everywhere else. So it is not written.

**One gap this exposed, not closed by SP2d so far:** `Xcp_Init` resets `Xcp_Internal` and every
`Xcp_DaqListRt`, and clears the ODT entries, but never resets the descriptor's own `maxOdt`,
`firstPid` or per-ODT `entryCount` — which under DYNAMIC *are* the allocation. A re-initialised
module therefore reports nothing allocated while the descriptor still describes the previous
session's lists. `Xcp_DaqFreeAll` is exactly the operation `Xcp_Init` is missing; see the Task 4
report.

Generator guards are tested by asserting generation fails, not by matching the message.

**Every new test is mutation-verified:** it must fail for the reason it names, and nothing else.

---

## 11. Acceptance

- The four commands behave per §5, including all six `ERR_SEQUENCE` cases and every
  `ERR_MEMORY_OVERFLOW` boundary.
- A STATIC build is behaviourally identical to today, and `cmd_unknown_test.py` still passes
  unchanged for it.
- `DAQ_CONFIG_TYPE`, `MAX_DAQ` and `MAX_DAQ_LIST` report per DD33 and §6.
- `firstPid` blocks are contiguous and non-overlapping under any allocation order.
- No new bounds check was added to any DAQ handler (DD32); the 7 entry bounds moved from the
  per-list field to the per-ODT one (DD34) and compare against the same values under STATIC.
- Coverage of `Xcp_Daq.c` and `Xcp_DaqRuntime.c` is no lower than before the branch.
- The full suite passes, with the pytest filter confirmed empty for the final run.

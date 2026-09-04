# SP3 — Synchronous data stimulation (STIM)

**Status:** design approved 2026-09-04.

**Predecessors:** SP2a–SP2d. STIM reuses the DAQ list infrastructure wholesale — ODT entries,
the event channel binding, the identification field, the allocation model — and inverts its
direction.

---

## 0. Which specification numbering this document uses

Citations are to **XCP Part 2 — Protocol Layer Specification 1.1** unless a citation names 1.0,
matching SP2a through SP2d. §0 of the SP2a design carries the §1.6.4 renumbering table.

The sections this sub-project leans on hardest — §1.1.2.1 (identification field), §1.1.2.2
(timestamp field), §1.1.4.2 (the STIM packet) and §1.1.5.1 (master-to-slave identifiers) — keep
their numbers in both revisions, so no mapping is needed for them.

`EV_STIM_TIMEOUT` (0x09) exists in 1.1's event table; 1.0 has no §1.8 chapter and does not define
it. It is out of scope here (§1) but is what establishes the timing model this design rests on
(§3).

---

## 1. Scope

**In:**

- Reception of STIM DTOs, buffering, and application at the event trigger.
- `DIRECTION = STIM` in `SET_DAQ_LIST_MODE`, and its reporting in `GET_DAQ_LIST_MODE`.
- `DAQ_STIM` lists and **pure `STIM` lists**, lifting the generation guard that refuses the latter.
- `STIM` event channels, and the STIM bits in `GET_DAQ_LIST_INFO` and `GET_DAQ_EVENT_INFO`.
- A real `MAX_ODT_ENTRY_SIZE_STIM` in `GET_DAQ_RESOLUTION_INFO`.

**Out, each a follow-up:**

- **`BIT_STIM`.** `BIT_STIM_SUPPORTED` is a separately declared capability in `DAQ_PROPERTIES`
  precisely because slaves commonly do not implement it. It changes how every ODT entry is
  applied. It stays reported unsupported, as today.
- **`EV_STIM_TIMEOUT`.** Needs a timeout policy — how long, configured where, per event or per
  list — and couples STIM to the timestamp configuration, since `Xcp_GetDaqTimestamp()` exists
  only when a clock is declared. Its own design.
- **Per-direction resource protection.** See DD41.

---

## 2. What already exists

STIM was anticipated throughout SP2. The scaffolding is in place and unpopulated:

| Thing | State |
|---|---|
| `Xcp_EventChannelTypeType` — `DAQ`, `DAQ_STIM`, `STIM` | declared; schema's *event* enum offers only the first two |
| `daqs[].type` — `DAQ`, `DAQ_STIM`, `STIM` | declared in schema; a pure `STIM` list is refused at generation |
| `XCP_DAQ_LIST_PROPERTIES_STIM`, `XCP_DAQ_EVENT_PROPERTIES_STIM` | defined, never set |
| `XCP_RESOURCE_PROTECTION_STATUS_MASK_STIM` | defined; accepted by `GET_SEED`/`UNLOCK`; gates nothing |
| `odtEntrySizeStim` | generated `0x00u`, commented "STIM arrives in SP3" |
| `XCP_DAQ_LIST_MODE_DIRECTION` (stored, bit 1) | defined, never set |
| `XCP_DAQ_LIST_MODE_REQ_DIRECTION` (request, bit 1) | refused via `..._REQ_UNSUPPORTED` |
| The receive branch for DAQ list PDUs | exists; sets a local flag and nothing else |
| `Xcp_WriteSlaveMemoryTable[]` | exists; `DOWNLOAD` uses it |
| `Xcp_DaqWriteIdentificationField` | exists; reception is its inverse |

---

## 3. Design decisions

**DD35 — stimulation data is latched, not consumed.** Each ODT's buffer holds the most recent
frame, and every event applies whatever it holds until the master replaces it. A master that
pauses leaves its last values in effect.

The specification does not decide this. `EV_STIM_TIMEOUT` establishes that a slave is expected to
notice *late* data, which implies buffering and application at the event rather than on arrival —
but not what to apply when nothing new arrived. One-shot semantics were considered and rejected:
the master is off-ECU and its send rate is frequently slower than the event rate, so a stimulated
variable would alternate between the master's value and the ECU's own computation, which is worse
than either alone. A later `EV_STIM_TIMEOUT` can report that data went stale without changing what
is applied.

**DD36 — buffer on arrival; apply at the event; never write memory in receive context.** The
receive callback decodes the identification field, copies the payload into one ODT slot, and
returns. Every memory write happens in the trigger's context, through the same
`Xcp_WriteSlaveMemoryTable[]` path `DOWNLOAD` uses.

This is what answers the concurrency question SP2b parked, and it answers it by not doing the
thing that would have been dangerous. `SWS_Xcp_00813` specifies `Xcp_<Lo>RxIndication` as
*"Reentrant for different PduIds. Non reentrant for the same PduId."* Every CTO arrives on
`channel_rx_pdu_ref->id`, which is why nothing guards `cto_response`, `last_pid` or the
protection-status clear. A STIM PDU is a different PduId and can preempt a CTO mid-dispatch — but
a handler that touches only its own slot cannot corrupt anything the CTO path owns. **The CTO
dispatch path is unchanged, and all 256 PID entries stay as they are.**

**DD37 — a second exclusive area, `SchM_Enter_Xcp_StimBuffer`, guarding the slot only.** The slot
is written by the receive callback and read by the trigger, each potentially interrupt context at
a different priority. Held per ODT slot, not around the whole reception or the whole apply loop —
the rule `Xcp_DaqListClearEntries` already follows.

**The payload length must be written under the area with the payload.** This is the DD14 class: a
length paired with the data it describes. `Xcp_Types.h` documents why the runtime *mode* fields are
deliberately unguarded — no field there is a pointer, or a length paired with one, so a torn read
costs at most a skewed cycle. The STIM slot does not qualify for that argument, and the note must
say so, because the next person to extend this will read that paragraph and reasonably conclude no
area is needed.

Reusing `SchM_Enter_Xcp_DtoQueue` was rejected: a `DAQ_STIM` list applies and samples in one
trigger, so one area risks nesting, which the harness asserts against. Guarding the whole dispatch
was rejected as paying a lock on every CTO to solve a problem CTOs do not have.

**DD38 — reception is the inverse of `Xcp_DaqWriteIdentificationField`, and only `ABSOLUTE` needs
a lookup.**

There are four identification field types; `PID_OFF` is a `SET_DAQ_LIST_MODE` mode bit that
removes the field entirely, so it is listed here as a fifth case but is not a type.

| case | wire | decoding | offset |
|---|---|---|---|
| `RELATIVE_BYTE` | `[odt, daq(u8)]` | both explicit | 2 |
| `RELATIVE_WORD` | `[odt, daq(u16)]` | both explicit | 3 |
| `RELATIVE_WORD_ALIGNED` | `[odt, fill, daq(u16)]` | both explicit | 4 |
| `ABSOLUTE` | `[firstPid + odt]` | linear scan | 1 |
| `PID_OFF` | — | the receiving PduId | 0 |

**Plus the timestamp, on ODT 0 of a timestamped list** — see DD44. The offsets above are the
identification field alone.

The `ABSOLUTE` scan walks allocated lists for `firstPid <= pid < firstPid + maxOdt`. A 256-entry
reverse table would be O(1) but must be rebuilt on every `ALLOC_ODT`, since SP2d recomputes the
whole prefix sum there, and on every direction change — more coherence to maintain than the scan
costs. The scan is bounded by `allocated_daq_count`, itself capped at 255, against a frame rate
the bus already bounds.

`PID_OFF` resolves through the PduId. The receive callback already walks
`dto2PduMapping.rxPdu.id` per list to accept the frame at all, so the receiving PDU identifies the
list exactly as the TX PDU identifies it in the other direction. The list must then have exactly
one ODT — the receive-side twin of SP2b's `Xcp_DaqListTxPduIsExclusive` rule.

**DD39 — a decoded frame is applied only if the list is allocated, STIM-capable, RUNNING and its
direction is STIM; anything else is dropped, and a short payload is rejected on arrival.** There
is no error response available: a DTO is not a command and no master is waiting on one. The only
channel is a `Det` report. Rejecting a payload shorter than the ODT's configured entries at
reception means the apply path never reasons about partial data, and the failure is attributed to
the frame that caused it rather than surfacing a cycle later.

**DD40 — a `DAQ_STIM` list applies before it samples.** Both happen on one event, so the order must
be fixed. Applying first means a list that stimulates and measures the same variable reports the
value that was actually in effect, rather than the one the stimulus was about to replace.

The order is also load-bearing for DD37: applying first means every `StimBuffer` section closes
before the first `DtoQueue` section opens, so the two areas cannot nest. It is not a free choice.

**DD41 — the `STIM` resource stays ungated, deliberately.** §1.5's resource table defines it as
*"DAQ list commands (DIRECTION = STIM)"* — protection keyed on a list's direction. This module
checks protection in `Xcp_CanIfRxIndication` from `Xcp_PIDToCmdGroupTable`, keyed on the **PID,
before dispatch**, where no list number has been parsed and no direction is known. Expressing the
specification's rule means moving the protection check into the handlers that know which list they
address — a change to the protection model for every command, not a change to STIM.

All DAQ commands therefore stay under `MASK_DAQ`, and `MASK_STIM` remains what it already is: a
resource `GET_SEED`/`UNLOCK` accept and a master can unlock, that gates nothing. This is
pre-existing, but SP3 is the first sub-project where it is visibly incomplete rather than merely
unused. Recorded as a follow-up in §8.

**DD44 — a STIM DTO carries a timestamp when the list is in timestamped mode, and reception must
skip it.** §1.1.2.2 is explicit: *"The TIMESTAMP flag can be used as well for DIRECTION = DAQ as
for DIRECTION = STIM."*

For STIM the direction of the timestamp reverses in an interesting way. The master *echoes* a
value it received: *"the master device first receives a time stamped DTO(DAQ) from the slave and
then echoes this current value of the slave device's clock in the DTO Packet for the first ODT of
the DAQ cycle."* Its stated purpose is to let the slave *"check whether DTO(DAQ) and CTO(STIM)
belong functionally together"* — a round-trip correlation for bypassing.

Three consequences:

- **It is present only on ODT 0 of the cycle**, exactly as on the DAQ side (Diagram 10), and only
  while the list's stored `TIMESTAMP` mode bit is set. Reception adds
  `Xcp_TimestampWireSize(timestampType)` to the payload offset in that case and no other.
- **The slave knows its size from its own configuration.** *"The master has to use the same Type of
  Timestamp Field when transferring STIM Packets to the slave"*, and the slave publishes it through
  `TIMESTAMP_MODE`/`TIMESTAMP_TICKS` in `GET_DAQ_RESOLUTION_INFO`. There is nothing to negotiate and
  nothing to infer from the frame.
- **The value is parsed and discarded.** The correlation check the specification describes is a
  possibility it offers the slave — *"gives the slave the possibility to check"* — not a
  requirement. Implementing it needs a record of which clock value was sent with which DAQ cycle,
  which is its own mechanism; §8 records it.

This corrects an earlier draft of this document, which assumed STIM DTOs carry no timestamp on the
reasoning that a master's timestamp is not something a slave can act on. That reasoning was wrong,
and the failure it would have caused is the one the draft itself named: with the field present and
unparsed, every applied value in ODT 0 would be shifted by one, two or four bytes. It was found by
reading §1.1.2.2 rather than reasoning about it — the same correction that PR #9 needed.

**DD42 — STIM has a lower PID ceiling than DAQ, checked where each model's type is decided.**
§1.1.5.1 gives master-to-slave STIM ODT numbers `0x00..0xBF`; §1.1.5.2 gives slave-to-master DAQ
`0x00..0xFB`. SP2d enforces one ceiling, `XCP_DAQ_ABSOLUTE_ODT_COUNT_MAX` at `0xFC`. A STIM-capable
list whose absolute ODT numbers reach `0xC0` cannot be addressed at all.

`firstPid` is a prefix sum over list index, so whether a list's block lands under `0xC0` depends on
how many ODTs precede it — a per-list runtime check would be re-evaluated whenever an earlier list
allocates. Instead:

- **DYNAMIC**: the pool has one declared type (DD43), so the ceiling is a property of the pool —
  `0xC0` when it can receive, `0xFC` when it cannot. `ALLOC_ODT` compares against that one number
  and its check keeps its present shape.
- **STATIC**: types are per-list and every `firstPid` is fixed at generation, so the generator
  checks each STIM-capable list's `first_pid + max_odt` against `0xC0` precisely, and a DAQ-only
  list keeps the full range.

**DD43 — `daq_dynamic` gains a `type`.** A STIM buffer costs `MAX_DTO` bytes plus a length per ODT,
and must exist for any list that might receive. Under STATIC `daqs[].type` already says which
those are. Under DYNAMIC there is no per-list type and `SET_DAQ_LIST_MODE` sets direction at
runtime, so without a declaration every pool slot would need a buffer.

`daq_dynamic.type` — `DAQ` | `DAQ_STIM` | `STIM`, defaulting to `DAQ` — mirrors the static model,
costs one schema key, and lets a DAQ-only dynamic build pay nothing. `SET_DAQ_LIST_MODE` refuses
`DIRECTION = STIM` on a `DAQ`-typed pool, which is the refusal it already performs.

A separate `stim_odt_count` was rejected: it adds an allocation dimension the master must reason
about, and `ALLOC_ODT` has no way to say which ODTs are stimulation-capable.

---

## 4. Configuration and generation

- `configurations[x].daq_dynamic.type`: `"DAQ" | "DAQ_STIM" | "STIM"`, default `"DAQ"` (DD43).
- `configurations[x].events[y].type` gains `"STIM"`. The schema currently offers `DAQ` and
  `DAQ_STIM` only, while `Xcp_EventChannelTypeType` already carries all three; a pure STIM list
  needs a pure STIM event to trigger it.
- The generation guard refusing `daqs[].type == 'STIM'` is removed. Its comment states its own
  expiry: it exists because `GET_DAQ_LIST_INFO` would report both type bits clear, which
  §1.6.4.2.2.1's `DAQ_LIST_TYPE` table marks "Not allowed".
- STIM slots are emitted only for receiving types — `daq_count × odt_count` under DYNAMIC, the sum
  over `DAQ_STIM` and `STIM` lists under STATIC — into a VAR section.
- `XcpOdtEntrySizeStim` is generated exactly as `XcpOdtEntrySizeDaq` is — `MAX_DTO` less the
  identification field — replacing the hard-coded `0x00u`. The two are the same number in this
  module, since master and slave use the same identification and timestamp types; they are
  reported separately because the specification permits a slave where they differ. The ODT-0
  timestamp reduction is applied at use, by the same arithmetic `Xcp_DaqOdtEntryBudget` already
  performs for DAQ (DD44).
- The `0xC0` ceiling guard for STIM-capable static lists (DD42).

---

## 5. Source layout

- `source/Xcp.c` — the receive branch that currently sets a flag calls the STIM handler.
- `source/Xcp_DaqRuntime.c` — `Xcp_DaqReadIdentificationField`, the slot write, and the apply loop
  in `Xcp_TriggerEventChannel`.
- `source/Xcp_Daq.c` — `SET_DAQ_LIST_MODE`'s direction acceptance; the STIM bits in
  `GET_DAQ_LIST_INFO`, `GET_DAQ_EVENT_INFO` and `GET_DAQ_RESOLUTION_INFO`.
- `source/Xcp_Internal.h` — the second exclusive area's declarations, the slot type.
- `script/source_cfg.c.jinja2`, `config/xcp.schema.json` — §4.

---

## 6. Test strategy

**The end-to-end test is the inverse of SP2d's**, and it is the one that matters: configure a STIM
list, set `DIRECTION = STIM`, point an ODT entry at a variable through `SET_DAQ_PTR`/`WRITE_DAQ`,
start the list, deliver a frame through `Xcp_CanIfRxIndication` on the list's RX PDU, trigger the
event, and assert **the variable holds the master's bytes**. Asserting the frame was accepted, or
that the slot holds it, tests the plumbing rather than the feature.

**A sweep over the four identification field types, plus `PID_OFF`.** Each produces a different
payload offset, and a wrong offset applies the master's data shifted — silent, and destructive to
whatever it overwrites. Each case decodes to a known list and ODT.

**The timestamped offset gets its own case.** A list in timestamped mode receives a frame whose
ODT 0 carries a timestamp and whose later ODTs do not, and both must apply to the right addresses.
Getting this wrong is the failure DD44 describes, so the test asserts the applied *values*, not
that the frame was accepted.

**The latched policy needs its negative.** Deliver one frame, trigger twice, assert the variable is
written both times. Under a one-shot implementation the second trigger writes nothing, so this
pins DD35 rather than merely exercising it.

**Three rejection paths, each asserting memory is unchanged**: a list that is not STIM-capable, a
list not RUNNING, and a payload shorter than the ODT's entries. A dropped frame that silently
applies is the failure worth catching.

**The `0xC0` ceiling** takes the shape SP2d's `0xFC` ceiling has — allocate to exactly the limit
and succeed, ask for one more and get `ERR_MEMORY_OVERFLOW` with the total unchanged — plus one
test that a DAQ-only pool still reaches `0xFC`, which is what proves the two ceilings are
distinguished rather than both clamped low.

**Concurrency.** The harness asserts area nesting, balance and non-leakage globally on every test,
so DD37's discipline is checked throughout. Beyond that, the `SchM` mock's `side_effect` is a
preemption-injection point: a STIM frame can be delivered from inside the trigger's area-taking
call. SP2d's `FREE_DAQ` sweep established that injecting at the area *exit* models a legitimate
preemption while injecting at the *enter* models one the area exists to forbid; the same
distinction applies here and the tests must say which they are exercising.

**Every new test is mutation-verified.** This branch writes to arbitrary memory addresses, so a
test that cannot fail is worth less here than anywhere else in the module.

---

## 7. Risks

- **The ODT-0 timestamp offset is the highest-consequence detail here** (DD44). It is now settled
  against §1.1.2.2 rather than assumed, but it remains the place where a mistake is silent and
  destructive: a payload read one, two or four bytes off writes the master's data into the wrong
  place, and nothing in the protocol reports it. The offset sweep in §6 exists for this.
- **STIM writes to addresses the master chooses.** DAQ reads them; this writes. The rejection paths
  in DD39 are the whole of the protection, and DD41 means the `STIM` resource does not gate them.
- **A latched buffer keeps stimulating after the master goes quiet** (DD35). That is the chosen
  behaviour, but it means losing the master mid-session leaves the ECU under stimulus until the
  list is stopped. `EV_STIM_TIMEOUT` is what would report it.

---

## 8. Follow-ups

- `BIT_STIM`, and `EV_STIM_TIMEOUT` with a timeout policy (§1).
- Per-direction resource protection, which requires moving the protection check from the dispatcher
  into the handlers (DD41).
- Distinct RX PDUs per dynamic STIM list, the receive-side twin of the TX PDU pool SP2d deferred.
- The DAQ/STIM correlation check §1.1.2.2 offers: comparing the echoed timestamp against the clock
  value the slave sent with the corresponding DAQ cycle, to confirm the two belong together (DD44).
  Needs a record of what was sent when, which is its own mechanism.

---

## 9. Acceptance

- A master can stimulate a variable end to end, under each of the four identification field types
  and under `PID_OFF`.
- A DAQ-only build generates no STIM storage and behaves exactly as it does today.
- A pure `STIM` list is generatable, and reports the `DAQ_LIST_TYPE` encoding §1.6.4.2.2.1 allows.
- The `0xC0` ceiling binds STIM-capable configurations and only those.
- The CTO dispatch path is unchanged: no exclusive area was added to it, and no handler on it
  gained a guard.
- The full suite passes, with the pytest filter confirmed empty for the final run.

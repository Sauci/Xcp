# EV_STIM_TIMEOUT and the STIM staleness policy

**Scope:** detect that a STIM DAQ list went unstimulated across consecutive events, and report it
with `EV_STIM_TIMEOUT` (XCP Part 2 1.1/§1.8.9). Takes the roadmap's absent `EV_*` count from four
to three. SP3 deferred this by name: the packet is the easy half, and the policy behind it is not
in the specification.

**Reference revision:** 1.1 only. 1.0 has no §1.8 chapter and does not define this event.

---

## 0. How §1.8.9 was read, and what the OCR was missing

1.1's OCR sidecar renders §1.8.9's Info Type list as a single value:

```
2   BYTE | Info Type
            0 = Event channel number
3   BYTE | reserved
```

That is wrong by omission, and the prose two lines below contradicts it — "Info type defines
whether the event channel **or the DAQ list** could not or just partially be stimulated."

The table was recovered from the PDF's **own text layer**, which is enciphered by glyph
substitution, using the known-plaintext method of §0 of `2026-09-11-xcp-get-id-types-design.md`.
The substitution was rebuilt from a long known pair — 1.1's enciphered severity paragraph against
1.0's plaintext of the same sentence, `Qlb Sbvbr`ty Ebvbe k`vbs tlb dnstbr…` → `The Severity Level
gives the master…` — extended with that design's recorded pairs (`IPQB`→`BYTE`, `A[HYA`→`DWORD`).
Thirty-five glyphs, no conflicts. Deciphered, §1.8.9 reads:

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | Event = 0xFD |
| 1 | BYTE | Event Code = 0x09 |
| 2 | BYTE | Info Type — `0 = Event channel number`, **`1 = DAQ list number`** |
| 3 | BYTE | reserved |
| 4..5 | WORD | Event channel number or DAQ list number, depending on Info Type |

> If the slave detects a STIM timeout, it can notify the master by sending EV_STIM_TIMEOUT.
> Info type defines whether the event channel or the DAQ list could not or just partially be
> stimulated.
> The severity is implementation specific.

**`1 = DAQ list number` appears nowhere in the OCR.** A design written from the sidecar alone would
have implemented one Info Type believing that was all §1.8.9 defines. This is the same failure mode
the roadmap's own EV row records for 2026-09-15, on the same table family — which is why the method
existed to reach for.

Note "can notify" and "Category: Event, **optional**": implementing this at all is a choice, and so
is implementing either Info Type.

## 1. What already exists, and what the specification does not decide

SP3 built the timing model this rests on:

- **DD35 — stimulation data is latched, not consumed.** Each ODT slot holds the most recent frame,
  and every event applies whatever it holds until the master replaces it. A master that pauses
  leaves its last values in effect.
- **DD36 — buffer on arrival; apply at the event; never write memory in receive context.**

SP3 also recorded what this design is for: "`EV_STIM_TIMEOUT` establishes that a slave is expected
to notice *late* data… A later `EV_STIM_TIMEOUT` can report that data went stale without changing
what is applied." **That constraint holds here: nothing about what gets applied changes.** This
design only observes and reports.

What §1.8.9 does not decide, and this design therefore must: how long a timeout is, in what unit,
where it is configured, what makes an event channel stale as opposed to a DAQ list, and how often
to report. Each is recorded below as a choice, not as a reading.

## 2. The design

### DD149 — count missed events, not elapsed time

A STIM DAQ list times out after N **consecutive stimulation events at which no new frame arrived**.

Elapsed time was rejected. `Xcp_GetDaqTimestamp()` exists only when `protocol_layer.timestamp`
declares a clock, so a time-based policy would make this feature unavailable in every build without
one, or would need a second time source of its own — the coupling SP3 named when it deferred this.
A missed-event count needs no clock and works in every build.

It also measures the thing that matters to a stimulated variable: how many times the ECU applied a
value the master did not refresh. Under DD35's latching that is exactly the failure a master wants
to hear about.

### DD150 — a list is stale when *none* of its ODT slots were fresh

`Xcp_StimSlotType` gains `boolean fresh`, set in the receive path where `p_slot->length` is already
written (`source/Xcp_DaqRuntime.c`) and cleared in `Xcp_DaqApplyStimOdt` when the slot is applied.

The flag is set **inside the existing `SchM_Enter_Xcp_StimBuffer()` section**, beside the length.
DD37 put the payload and its length in one section precisely so no reader sees one without the
other; freshness is a third fact about the same slot and belongs with them.

A list is **stale** at an event when no slot of it was fresh — §1.8.9's "could not … be
stimulated". A list with some fresh slots is **not** stale. The specification's "just partially" is
expressed at the channel instead (DD151), where some lists are stale and others are not.

The alternative — stale when *not all* slots are fresh — was rejected. A master stimulating a
multi-ODT list sends one frame per ODT, and normal jitter in their arrival would trip that rule
constantly, reporting a timeout for a master that is working correctly.

### DD151 — the aggregation rule is invented, and says so

§1.8.9 gives Info Type two values and one sentence about what they distinguish. It does not say
when a slave should choose one over the other. This module chooses:

| Situation at one event | Reported |
|:--|:--|
| every STIM list on the channel is stale | **one** event, Info Type 0, carrying the event channel number |
| some are stale, some are not | one event **per stale list**, Info Type 1, carrying the DAQ list number |
| none is stale | nothing |

The two cases are mutually exclusive, so one situation never produces both kinds of report. Each
carries the most specific answer available: when the whole channel failed, the channel is the
useful fact; when one list failed, naming it is.

This is a choice, not a requirement. A conformant slave could report per list always, or per
channel always, or implement one Info Type and not the other.

### DD152 — the threshold is per event channel, and absent means off

Each entry in the `events` array gains an optional `stim_timeout_events`. **Absent means that
channel never reports a STIM timeout**, so the feature is opt-in and every existing configuration
behaves exactly as before.

Per event channel rather than per DAQ list, for two reasons. Stimulation timing lives at the
channel — a 10 ms channel and a 1 s channel need different tolerances against the same absolute
lateness. And DAQ lists have no static configuration entry at all under `DAQ_DYNAMIC`, where the
master allocates them at runtime; a per-list threshold would silently not exist for those builds.

Not global, because one tolerance across a configuration mixing fast and slow stimulation channels
is wrong for at least one of them.

### DD153 — report on equality, so each staleness episode reports once

`Xcp_DaqListRtType` gains `uint16 stimStaleEvents`, incremented at each event where the list is
stale and reset to 0 when it is not.

The report fires when the counter **equals** the threshold, not when it reaches or exceeds it. The
counter keeps rising afterwards and cannot equal the threshold again until fresh data resets it, so
one staleness episode produces exactly one report without a separate "already reported" flag. The
counter saturates at `0xFFFFu` rather than wrapping, which would otherwise let a long episode report
a second time after 65536 events.

Reporting once per episode is not cosmetic. The event queue has finite depth and drops pushes when
full — `Xcp_EventQueuePush` returns `E_NOT_OK` and the caller reports `XCP_E_EVENT_QUEUE_FULL`. A
report per event would let one stalled channel crowd out every other event the module raises.

### The packet

Four information bytes — Info Type, the reserved byte, and the WORD — pushed through the userData
path DD138 built and #44's carriers use. Six bytes total, well inside `XCP_EVENT_USER_DATA_SIZE`
(16) and inside any legal `MAX_CTO` (minimum 8). The WORD is written with
`Xcp_CopyFromU16WithOrder` in the configured byte order, as every other multi-byte field is.

The reserved byte is written as `0x00u`. §1.8.9 names it reserved and gives no value; writing a
defined byte beats leaving whatever the queue entry last held.

## 3. Testing

- **The wire layout.** A reported timeout is exactly `FD 09 <info type> 00 <WORD>` at `SduLength` 6,
  asserted byte for byte against §1.8.9, in both byte orders.
- **Threshold behaviour.** A list stale for N-1 events reports nothing; at exactly N it reports
  once; staying stale past N reports no more (DD153). Fresh data resets the counter, and a second
  episode reports again.
- **The aggregation rule (DD151).** A channel whose every STIM list is stale produces one Info
  Type 0 report carrying the channel number and no per-list report; a channel with one stale list
  of two produces one Info Type 1 report carrying that list's number and no channel report.
- **Staleness definition (DD150).** A list whose slots are partially refreshed is not stale, and
  its counter resets — the case the rejected "not all fresh" rule would have reported.
- **Opt-in.** A channel with no `stim_timeout_events` never reports, however long its lists stay
  stale. Every existing STIM test stays green unchanged, which is the evidence.
- **Nothing about application changes.** A stale list still applies its latched values (DD35), both
  before and after a timeout is reported.

## 4. Out of scope

**Changing what is applied when data is stale.** DD35's latching stands; this design observes.
One-shot semantics were considered and rejected in SP3, and nothing here reopens that.

**`EV_TIME_SYNC` (0x08), `EV_SLEEP` (0x0A) and `EV_WAKE_UP` (0x0B)**, the roadmap's other absent
event codes. Each implies its own feature — §1.8.8's externally triggered sync line, §1.8.10's
SLEEP mode — rather than a packet.

**A configurable severity.** §1.8.9 says "the severity is implementation specific" and the module
transmits no severity field; severity is the master's to infer from §1.2's table, which this module
does not send.

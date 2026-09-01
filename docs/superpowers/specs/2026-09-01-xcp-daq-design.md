# SP2a — Static data acquisition, end to end

**Date:** 2026-09-01
**Baseline:** branch `develop`, commit `7d52623`
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.1*, ASAM e.V.
**Also normative:** *AUTOSAR Specification of CAN Interface*, CP Release 4.3.1 (document ID
012), for everything in DD3, DD5 and DD13 that concerns how this module may call `CanIf`; and
*AUTOSAR Specification of Module XCP*, CP Release 4.3.1 (document ID 412), for
`Xcp_MainFunction` and the module's API surface. All are in `docs/external/`, which is
gitignored.
**Roadmap:** `2026-08-29-xcp-part2-roadmap.md`

Implements the mandatory basic and static commands of the data acquisition group (§1.6.4),
the DAQ configuration model they operate on, and the runtime that samples the configured
memory and transmits it as DTO packets. This is the first of three phases of roadmap
sub-project SP2.

## 0. Which specification numbering this document uses

**Citations below use 1.1 numbering**, unlike `2026-08-29-xcp-cal-pag-design.md`, which uses
1.0. The reason is that §1.6.4 is the one chapter that was reorganised wholesale between the
two revisions. 1.0 divides the group into §1.6.4.1 *Static DAQ list configuration* and
§1.6.4.2 *Dynamic DAQ list configuration*; 1.1 introduces a §1.6.4.1 *Basics* ahead of both,
demoting static to §1.6.4.2 and dynamic to §1.6.4.3, and reorders the commands within each.
Every DAQ citation therefore shifts, and several shift by more than one level.

| command | 1.0 | 1.1 |
|:--|:--|:--|
| `SET_DAQ_PTR` | §1.6.4.1.1.2 | §1.6.4.1.1.1 |
| `WRITE_DAQ` | §1.6.4.1.1.3 | §1.6.4.1.1.2 |
| `SET_DAQ_LIST_MODE` | §1.6.4.1.1.4 | §1.6.4.1.1.3 |
| `START_STOP_DAQ_LIST` | §1.6.4.1.1.6 | §1.6.4.1.1.4 |
| `START_STOP_SYNCH` | §1.6.4.1.1.7 | §1.6.4.1.1.5 |
| `WRITE_DAQ_MULTIPLE` | — | §1.6.4.1.2.1 |
| `READ_DAQ` | §1.6.4.1.2.2 | §1.6.4.1.2.2 |
| `GET_DAQ_CLOCK` | §1.6.4.1.2.1 | §1.6.4.1.2.3 |
| `GET_DAQ_PROCESSOR_INFO` | §1.6.4.1.2.3 | §1.6.4.1.2.4 |
| `GET_DAQ_RESOLUTION_INFO` | §1.6.4.1.2.4 | §1.6.4.1.2.5 |
| `GET_DAQ_LIST_MODE` | §1.6.4.1.1.5 | §1.6.4.1.2.6 |
| `GET_DAQ_EVENT_INFO` | §1.6.4.1.2.6 | §1.6.4.1.2.7 |
| `CLEAR_DAQ_LIST` | §1.6.4.1.1.1 | §1.6.4.2.1.1 |
| `GET_DAQ_LIST_INFO` | §1.6.4.1.2.5 | §1.6.4.2.2.1 |
| `FREE_DAQ` | §1.6.4.2.1.1 | §1.6.4.3.1.1 |
| `ALLOC_DAQ` | §1.6.4.2.1.2 | §1.6.4.3.1.2 |
| `ALLOC_ODT` | §1.6.4.2.1.3 | §1.6.4.3.1.3 |
| `ALLOC_ODT_ENTRY` | §1.6.4.2.1.4 | §1.6.4.3.1.4 |

Sections outside §1.6.4 that this work depends on keep their numbers in both revisions:
§1.1.2.1 (identification field), §1.1.2.2 (timestamp field), §1.1.4.1 (DAQ packet),
§1.1.5.1–2 (packet identifiers), §1.6.1.1.1 (`CONNECT`), §1.6.1.1.3 (`GET_STATUS`) and
§1.7.3.2.4 (the DAQ error matrix).

One citation has no 1.0 equivalent at all: **§1.8.6** *Indication of DAQ overload*. 1.0 has
no §1.8 chapter; it describes `EV_DAQ_OVERLOAD` inline in §1.2.

**Consequence for the C sources.** Existing comments are version-qualified as
`XCP part 2 - Protocol Layer Specification 1.0/...` and stay accurate for the sections they
cite. New DAQ comments are qualified `1.1/...`. See DD1.

## 1. Scope

**In scope**

| | |
|:--|:--|
| §1.6.4.1.1.1 | `SET_DAQ_PTR` — 0xE2, mandatory |
| §1.6.4.1.1.2 | `WRITE_DAQ` — 0xE1, mandatory |
| §1.6.4.1.1.3 | `SET_DAQ_LIST_MODE` — 0xE0, mandatory |
| §1.6.4.1.1.4 | `START_STOP_DAQ_LIST` — 0xDE, mandatory |
| §1.6.4.1.1.5 | `START_STOP_SYNCH` — 0xDD, mandatory |
| §1.6.4.1.2.4 | `GET_DAQ_PROCESSOR_INFO` — 0xDA, optional |
| §1.6.4.1.2.5 | `GET_DAQ_RESOLUTION_INFO` — 0xD9, optional |
| §1.6.4.1.2.6 | `GET_DAQ_LIST_MODE` — 0xDF, optional |
| §1.6.4.2.1.1 | `CLEAR_DAQ_LIST` — 0xE3, mandatory |
| §1.1.2.1 | the identification field, all four types |
| §1.1.4.1 | the DAQ packet |
| §1.7.3.2.4 | the DAQ error matrix rows for the nine commands |
| §1.8.6 | `EV_DAQ_OVERLOAD` |

Plus the DAQ configuration model, the sampling and transmission runtime, the
`Xcp_TriggerEventChannel` public API (a vendor extension — see DD15), the exclusive area of
DD5, the `DAQ_RUNNING` bit of §1.6.1.1.3 and the DAQ resource bit of §1.6.1.1.1.

**Out of scope, deferred to SP2b** — `WRITE_DAQ_MULTIPLE` (§1.6.4.1.2.1), `READ_DAQ`
(§1.6.4.1.2.2), `GET_DAQ_CLOCK` (§1.6.4.1.2.3), `GET_DAQ_EVENT_INFO` (§1.6.4.1.2.7),
`GET_DAQ_LIST_INFO` (§1.6.4.2.2.1), the timestamp field (§1.1.2.2), the `PID_OFF` and
`ALTERNATING` modes, and DAQ list prioritisation.

**Out of scope, deferred to SP2c** — dynamic DAQ list configuration (§1.6.4.3): `FREE_DAQ`,
`ALLOC_DAQ`, `ALLOC_ODT`, `ALLOC_ODT_ENTRY`, and the `DAQ_CONFIG_TYPE` = dynamic branch.

**Out of scope entirely** — STIM (SP3), PGM (SP4), RESUME mode, `STORE_DAQ_REQ` /
`CLEAR_DAQ_REQ` persistence and roadmap defect D9, `SET_DAQ_LIST_CAN_ID` (all SP5).

## 2. What already exists

Four mechanisms are complete for this sub-project and must not be rebuilt.

- **`Xcp_CTOErrorMatrix`** encodes §1.7.3.2.4 for every DAQ command. Each of the nine rows in
  scope was compared against the specification table entry by entry. Seven match. Two do
  not, and are corrected here — see D10 and D11. The matrix drives only the *generic
  pre-checks* in `Xcp_CanIfRxIndication`: `ERR_CMD_UNKNOWN`, `ERR_CMD_BUSY`,
  `ERR_CMD_SYNTAX`, `ERR_PGM_ACTIVE`. Errors a handler raises itself do not consult it.
- **`Xcp_PIDToCmdGroupTable`** already maps 0xD3–0xE3 to
  `XCP_RESOURCE_PROTECTION_STATUS_MASK_DAQ`, so seed-and-key protection works unchanged.
  (0xC7 is `MASK_NONE` and will need `MASK_DAQ` when `WRITE_DAQ_MULTIPLE` lands in SP2b.)
- **`ctoInfo[]`** carries a correct minimum request size for all nine commands: 0x06 for
  `SET_DAQ_PTR`, 0x08 for `WRITE_DAQ` and `SET_DAQ_LIST_MODE`, 0x04 for
  `START_STOP_DAQ_LIST`, `GET_DAQ_LIST_MODE` and `CLEAR_DAQ_LIST`, 0x02 for
  `START_STOP_SYNCH`, 0x01 for the two info commands. Each was checked against the
  parameter tables of §1.6.4. No change needed.
- **The transmit state machine.** `Xcp_Internal.ongoing_transmit_type` arbitrates between
  the CTO response and the event packet, `CanIf_Transmit` is called from
  `Xcp_MainFunction`, and `Xcp_CanIfTxConfirmation` clears the pending flag. DAQ becomes a
  third arm of the same machine rather than a parallel one.

The configuration type model is **partly** present and partly wrong. `Xcp_DaqListType`,
`Xcp_OdtType`, `Xcp_OdtEntryType`, `Xcp_DtoType` and `Xcp_EventChannelType` exist in
`Xcp_Types.h`, and `source_cfg.c.jinja2` already emits DAQ lists, ODTs, ODT entries and
DTOs from the `daqs` array. What is missing or wrong is catalogued in §8.

The DAQ *runtime* is absent in its entirety. `Xcp_Daq.c` holds one stub,
`Xcp_DTODaqStimPacket`, reached only from the 0x00–0xBF half of `Xcp_PIDTable`.
`Xcp_CanIfTriggerTransmit` returns `E_OK` without touching the PDU.

## 3. Design decisions

**DD1 — New DAQ code cites 1.1; existing comments keep their 1.0 citations.** §0 shows that
every §1.6.4 citation shifts between revisions. Rewriting the module's existing citations to
1.1 would touch every file for no behavioural gain and would risk the exact class of error
recorded in commit `dfedf30`. Instead each comment states the revision it was written
against, so a reader always knows which document to open. New DAQ comments read
`XCP part 2 - Protocol Layer Specification 1.1/1.6.4...`.

**DD2 — The module keeps no clock; the integrator triggers every event channel.** The only
way a channel fires is the new public `Xcp_TriggerEventChannel(uint16 eventChannelNumber)`.
Phase 1 contains no timekeeping of any kind.

§1.6.4.1.1.3 defines an event channel as "the generic signal source that effectively
determines the data transmission timing". That source is a 10 ms task, a crank-angle
interrupt, an end-of-conversion — something only the integrator can identify. §1.1.4.1 calls
what this group performs *synchronous* data acquisition, and data is synchronous with its
source or with nothing.

`time_cycle` and `time_unit` therefore describe a raster the slave *promises*, reported to
the master through `GET_DAQ_EVENT_INFO` in SP2b. They are not a schedule the module executes.
The integrator honours the promise by calling the trigger from a context running at that
rate; the README documents the obligation. A trigger naming a channel at or above
`maxEventChannel` raises a DET error and samples nothing.

**AUTOSAR reaches the same conclusion from the other direction.** ECUC_Xcp_00014
(`XcpMainFunctionPeriod`) states that the XCP module does not require the period — it exists
so the BSW scheduler can plan its tasks. A module forbidden to depend on knowing its own
period cannot convert a channel's sampling period into a count of main function invocations,
so a main-function timer is not implementable within the standard, independently of whether
the period happens to be stable.

There is a genuine tension in AUTOSAR here worth naming, because it looks at first like a
contradiction: ECUC_Xcp_00173 describes `XcpEventChannelTimeCycle` as the sampling period
used to process the channel, while ECUC_Xcp_00014 withholds the one value that would be
needed to act on it. The consistent reading — and the only implementable one — is that the
time cycle describes the raster rather than commands it, which is what DD2 does.

An earlier revision of this design had `Xcp_MainFunction` fire cyclic channels from a divider
computed at generation time as `time_cycle × time_unit ÷ main_function_period`. It was
withdrawn during review as unsound. Counting main function invocations measures elapsed time
only if the period is constant, and an integrator calling `Xcp_MainFunction` from a
background task has no constant period — under load the count measures scheduler pressure. It
also capped every sampling raster at the main function's own rate, which is precisely
backwards for a slave whose fastest signals are the ones worth measuring. Nothing survives of
it: no `mainFunctionCycles`, no `main_function_period` configuration key, no
"channel faster than the main function" validation, and no special case for
`time_cycle = 0`, which §1.6.4.1.2.7 defines as "not cyclic" and which is now simply one more
channel the integrator triggers when it has reason to.

**DD3 — `Xcp_MainFunction` is the recovery path, not the transmission path.** Arbitration
moves out of `Xcp_MainFunction` into one internal `Xcp_StartNextTransmission`, so there is a
single place that decides what goes out next. Three contexts call it:

- **`Xcp_TriggerEventChannel`**, after enqueueing, if nothing is in flight. It already holds
  the exclusive area and has just produced the data, so the first frame of a burst leaves
  without waiting for anything.
- **`Xcp_CanIfTxConfirmation`**, which continues the chain until the ring empties. This is
  what paces the stream by CAN bandwidth.
- **`Xcp_MainFunction`**, whenever the module is idle with something queued.

Steady-state acquisition therefore never involves the main function at all: the trigger starts
the chain and confirmations sustain it. What the main function is for is the one case that
breaks the chain — `CanIf_Transmit` refusing, after which nothing is in flight and no
confirmation is coming, so something has to retry. That is not a new obligation; CTO responses
and event packets already depend on the main function for exactly this.

SWS_Xcp_00824 requires `Xcp_MainFunction` to be called cyclically, and §8.5 of that
specification has the BSW scheduler call it directly and requires it to be non reentrant.
This design assumes both: it never expects two concurrent calls, and it does expect the call
to recur. What it deliberately does *not* assume is any particular period, per ECUC_Xcp_00014.

The contract the README states:

> Call `Xcp_MainFunction` cyclically, as SWS_Xcp_00824 requires. Its rate bounds how quickly
> the stack recovers after the CAN interface refuses a transmission. It does not affect the
> DAQ measurement raster, which the integrator sets through `Xcp_TriggerEventChannel`, and it
> does not affect throughput.

The rejected alternative was to leave the start to `Xcp_MainFunction` and let confirmations
drain the ring afterwards. It keeps `CanIf_Transmit` out of the trigger's context, which
matters when the trigger is an interrupt, and it loses no throughput — one main function call
still drains everything queued. But sampled frames then wait in the ring until the main
function next runs, so a 50 ms stall against a 10 ms event releases five bursts at once, every
frame stale. Phase 1 carries no timestamp, so the master reads arrival time as sample time and
cannot see the staleness. Freshness is the point of data acquisition, and invisible staleness
is the worst way to lose it.

The cost accepted instead is one `CanIf_Transmit` inside the trigger's context — on CAN a
mailbox write, in a context the integrator chooses.

**This is the pattern AUTOSAR prescribes, not a deviation from it.** §7.11.2.1 of the CAN
Interface specification instructs upper layers that need transmit order preserved to tie each
transmit request to the previous transmit confirmation, requesting the next L-PDU only once
the previous one has been confirmed. That CanTp and Com instead transmit from their main
functions is a consequence of their own timing obligations — CanTp has `STmin` to honour — not
evidence that chaining is disallowed.

This also fixes D16: today the confirmation only clears flags, so a CTO block transfer and the
event queue each advance by one frame per main function call for the same reason DAQ would
have.

**DD4 — Sample into a queue of complete frames.** At the event instant every RUNNING DAQ list
on the channel is sampled and each of its ODTs is assembled into a finished DTO frame, which
is pushed whole into a ring buffer. DD3 governs how the ring is drained.

The alternative — enqueueing ODT references and reading memory when the frame reaches CanIf —
costs two bytes per entry instead of `MAX_DTO + 3`, but the values would then reflect
transmit time rather than event time, and two ODTs of one event would be skewed against each
other. §1.1.4.1 calls this *synchronous* data acquisition; sampling at transmit time is not
synchronous with anything. Rejected as a correctness defect.

Sampling and transmitting inline with no queue was also rejected: CanIf accepts one frame at
a time, so a three-ODT list would lose two frames of every three.

**DD5 — One exclusive area protects the transmit state.** DD2 and DD3 put three contexts on
the same data, and under DD3 all three both produce and consume:
`Xcp_TriggerEventChannel` runs in a task or an ISR, `Xcp_CanIfTxConfirmation` in CanIf's
context, and `Xcp_MainFunction` in the integrator's background task. The DTO ring indices
and `Xcp_Internal.ongoing_transmit_type` are therefore guarded by an AUTOSAR exclusive area,
entered and left around `Xcp_StartNextTransmission` and around each ring operation:

```c
SchM_Enter_Xcp_DtoQueue();
...
SchM_Exit_Xcp_DtoQueue();
```

`test/stub/SchM_Xcp.h` provides the stub. It counts entries and exits so a test can assert
that every path leaves the area it entered, including the error paths.

The scope is deliberately narrow: the transmit arbitration state and the DTO ring, nothing
else. The README's standing TODO — "protect variables used in both synchronous and
asynchronous APIs" — remains open for the rest of the module. This sub-project closes it only
where it introduces a second context, rather than opening a module-wide concurrency audit
inside a DAQ sub-project.

The area closes *before* `CanIf_Transmit` is called, never around it. Holding it across a
lower-layer call would make the section unbounded, and §7.17 of the CAN Interface
specification directs that such sections stay short and confined to copying data and updating
counters and semaphores. The sequence is therefore: enter, choose the frame and mark it in
flight, exit, transmit, and on refusal re-enter to unmark. DD13 covers the re-entrancy this
leaves open.

**DD6 — Overload drops the frame and reports it once per trigger.** When the ring is full the
frame is discarded. With `overload_indication = EVENT` the slave pushes `EV_DAQ_OVERLOAD`
(0x06) onto the existing event queue, at most once per event channel trigger regardless of
how many frames were lost, because §1.8.6 requires that the slave "must take care not to
overload another cycle with this additional packet". `overload_indication = NONE` drops
silently and reports no overload capability in `DAQ_PROPERTIES`.

The third variant §1.6.4.1.2.4 defines, overload indication in the MSB of the PID, is not
offered. It constrains every ODT number to below 0x7C whether or not an overload ever occurs.

**DD7 — `FIRST_PID` is derived by the generator, never configured.** §1.6.4.1.1.4 makes
`FIRST_PID` the slave's to assign and requires that "for every ODT there's a unique absolute
ODT number". The generator assigns it as the running sum of preceding lists' `max_odt`,
checks `FIRST_PID + max_odt - 1 <= 0xFB` per §1.1.4.1, and fails generation if an explicit
`daqs[].dtos[].pid` contradicts the derived numbering. The shipped `config/xcp.json` fails
that check today — see D12.

**DD8 — `BIT_OFFSET` is stored and validated but does not alter what is sampled.**
§1.6.4.1.1.2 is written from the master's point of view: for a measurement in a list with
`DIRECTION = DAQ`, `BIT_MASK` "describes the mask to be applied to the measured data", which
the master applies to what it receives. The slave transmits the element unmodified. What the
slave must enforce is the companion rule in the same paragraph: when `BIT_OFFSET` is
0x00–0x1F the entry size has to equal `GRANULARITY_ODT_ENTRY_SIZE_DAQ`. `BIT_OFFSET = 0xFF`
means the field is ignored and the entry is a normal element.

This is recorded because the paragraph's closing sentences — "If the value of this element =
0, the value for the bit = 0" — read as if they prescribed slave behaviour. They describe the
stimulation direction, which is out of scope until SP3.

**DD9 — Every unimplemented mode bit answers `ERR_MODE_NOT_VALID`.** `SET_DAQ_LIST_MODE`
accepts `ALTERNATING`, `DIRECTION`, `TIMESTAMP` and `PID_OFF`. Phase 1 implements none of
them. §1.7.3.2.4 lists `ERR_MODE_NOT_VALID` for that command and it is exactly what the code
means, so all four are rejected with it rather than with `ERR_OUT_OF_RANGE` or
`ERR_CMD_SYNTAX`. DAQ list priority is the one exception: §1.6.4.1.1.3 states outright that a
slave without prioritisation indicates a priority above 0 "by returning ERR_OUT_OF_RANGE".

**DD10 — An invalid DAQ pointer answers `ERR_OUT_OF_RANGE`.** §1.6.4.1.1.2 leaves the pointer
"undefined" after a write to the last ODT entry of an ODT and puts the burden on the master.
The slave marks it invalid and answers the next `WRITE_DAQ` with `ERR_OUT_OF_RANGE`, which
§1.7.3.2.4 lists for the command and whose prescribed master action, "retry other parameter",
is the correct recovery. The specification prescribes no code for this case.

**DD11 — The runtime scans DAQ lists rather than the configured event associations.**
`SET_DAQ_LIST_MODE` assigns an event channel to a DAQ list at runtime, so the authoritative
association lives in `Xcp_DaqListRtType`, not in `Xcp_EventChannelType.triggeredDaqListRef`.
The sampler iterates DAQ lists and compares their assigned channel number. The configured
reference stays as metadata for `GET_DAQ_EVENT_INFO` in SP2b — its type is fixed here anyway
because the generator must now emit it (D13).

The cost is a scan of every DAQ list per trigger, O(`daqCount`), rather than a walk of a
per-channel list maintained by `SET_DAQ_LIST_MODE`. At the two lists of the shipped
configuration that is nothing; at fifty lists on a 1 ms raster it would be worth the index.
Recorded rather than pre-built, because the index has to be maintained under the exclusive
area too and nothing yet justifies it. DD14 covers the other hazard the scan is exposed to.

**DD12 — The runtime lives in its own translation unit.** `source/Xcp_Daq.c` holds the nine
command handlers, following the one-file-per-command-group layout DD1 of SP1 established.
Sampling, frame assembly and the ring buffer go in a new `source/Xcp_DaqRuntime.c` — a
different responsibility from answering commands, the thing the runtime tests drive directly,
and enough code that folding it into `Xcp_Daq.c` would produce the largest file in the
repository. `Xcp_StartNextTransmission` stays in `Xcp.c`, since it arbitrates between all
three packet kinds and only one of them is DAQ.

**DD13 — A re-entrancy guard keeps the module inside `CanIf_Transmit`'s contract.**
SWS_CANIF_00005 gives `CanIf_Transmit` as synchronous and "Reentrant for different PduIds.
Non reentrant for the same PduId." The note under SWS_CANIF_00412 puts the confirmation's
call context on interrupt level or task level, so a transmit interrupt can confirm a frame
while `Xcp_TriggerEventChannel` or `Xcp_MainFunction` is still inside `CanIf_Transmit` for
that same PDU. Chaining from the confirmation at that moment would be exactly the prohibited
same-PduId re-entrant call.

`Xcp_StartNextTransmission` therefore carries a `transmit_in_progress` flag, set under the
exclusive area on entry. A call that finds it set records that a restart is wanted and
returns without touching `CanIf_Transmit`; the outermost call loops while that flag is set
after `CanIf_Transmit` returns. Bounded stack, unchanged throughput, and no same-PduId
re-entry — which also removes the unbounded recursion a CanIf that confirms synchronously
inside `CanIf_Transmit` would otherwise cause.

**Single-outstanding per PDU is mandatory, not a simplification.** SWS_CANIF_00068 has CanIf
*overwrite* an already-buffered instance of the same L-PDU when `Can_Write` returns
`CAN_BUSY`. A second DAQ frame handed over before the first is confirmed therefore destroys
the first silently — no error, no confirmation, one measurement sample simply missing.
(SWS_CANIF_00837 covers the other case: a genuinely new L-PDU with all buffers busy gets
`E_NOT_OK`.) This also retires the SP2b idea of several frames in flight on one PDU; only
distinct PDUs could ever support it.

**DD14 — The sampler copies ODT entry descriptors before dereferencing them.** §1.6.4.2.1.1
allows `CLEAR_DAQ_LIST` on a RUNNING list — it is required to stop the transmission, which is
also why D10 removes `ERR_DAQ_ACTIVE` from its matrix row — and it resets every ODT entry to
address 0. That handler runs in `Xcp_CanIfRxIndication`'s context while
`Xcp_TriggerEventChannel` may be walking the same entries from a task or an interrupt.
Checking RUNNING first does not close the window: the sampler passes the check, the command
zeroes the entries, and the sampler dereferences address 0 inside an interrupt.

Widening the exclusive area over the sampling loop is not the answer, because that holds a
lock across arbitrary memory reads. Instead the sampler copies one ODT's entry descriptors —
address, extension, length, bit offset — under the area, leaves it, and reads memory from the
copies. A concurrently cleared entry then yields either a valid stale read or a length of
zero, never a wild pointer. One acquisition per ODT, and a descriptor is a few bytes.

**DD15 — `Xcp_TriggerEventChannel` is a vendor extension, and the specification leaves no
alternative.** The API surface of SWS_Xcp R4.3.1 is `Xcp_Init`, `Xcp_GetVersionInfo`,
`Xcp_SetTransmissionMode`, the three `Xcp_<Lo>` callbacks and `Xcp_MainFunction`. There is no
standard service by which an integrator triggers a DAQ event channel, and the specification
says nothing normative about how event channels are processed — it delegates the mechanics of
§1.6.4 to the ASAM document.

So an implementation has exactly two options: drive channels from `Xcp_MainFunction`, which
DD2 shows the standard itself makes unimplementable, or add a service. This design adds one.
It is marked in the README as a vendor extension rather than a standard service, alongside
the extensions the module already carries — the JSON configuration, `Xcp_MemoryAccess.h`,
`Xcp_Paging.h`, `Xcp_SeedKey.h` and the rest.

The name follows the module's existing convention and the parameter is the
`XcpEventChannelNumber` of ECUC_Xcp_00170, so a channel is triggered by the same number
`GET_DAQ_EVENT_INFO` will report for it in SP2b.

## 4. Source layout

```
source/Xcp.c            generic engine, dispatch tables, Xcp_StartNextTransmission
source/Xcp_Std.c        STD command group
source/Xcp_Cal.c        CAL command group
source/Xcp_Pag.c        PAG command group
source/Xcp_Daq.c        DAQ command group          -- nine handlers
source/Xcp_DaqRuntime.c DAQ runtime                -- new
source/Xcp_Internal.h   shared declarations
```

`CMakeLists.txt` and the CFFI harness both compile six translation units instead of five,
preserving DD6 of SP1: the suite exercises the linkage the shipped library uses, so a helper
left `static` in one unit but called from another fails the tests rather than the build.

One new integrator header, `test/stub/SchM_Xcp.h`, provides the exclusive area of DD5,
joining `CanIf.h`, `Det.h` and the four `Xcp_*` callback headers already stubbed there.

## 5. Configuration model

### 5.1 Schema — new `protocol_layer` keys

| key | type | default | purpose |
|:--|:--|:--|:--|
| `identification_field_type` | enum | `ABSOLUTE` | §1.1.2.1 field type; `ABSOLUTE`, `RELATIVE_BYTE`, `RELATIVE_WORD`, `RELATIVE_WORD_ALIGNED` |
| `daq_queue_size` | integer | 16 | DTO ring depth, mirroring `cto_queue_size` and `event_queue_size` |
| `prescaler_supported` | boolean | `true` | `PRESCALER_SUPPORTED` in `DAQ_PROPERTIES` |
| `overload_indication` | enum | `EVENT` | `EVENT` or `NONE`; see DD6 |

There is deliberately no `main_function_period` key. DD2 removed the only thing that would
have read it. `Xcp_GeneralType.mainFunctionPeriod` keeps its hard-coded `1000000`, which is
not a period in any unit — it is the AUTOSAR `XcpMainFunctionPeriod` parameter, unread by
this module today, and correcting it belongs to whichever sub-project first needs it.

### 5.2 Derived, no longer hard-coded

`source_cfg.c.jinja2` currently emits literal constants for values it can compute:

| field | today | becomes |
|:--|:--|:--|
| `identificationFieldType` | `ABSOLUTE` | from `protocol_layer.identification_field_type` |
| `prescalerSupported` | `FALSE` | from `protocol_layer.prescaler_supported` |
| `daqConfigType` | `DAQ_STATIC` | `DAQ_STATIC` — correct in phase 1, derived in SP2c |
| `minDaq` | `0x00u` | `0x00u` — no predefined lists in phase 1 |
| `odtCount` | `0x00u` | sum of `max_odt` over all DAQ lists |
| `odtEntriesCount` | `0x00u` | sum of `max_odt × max_odt_entries` |
| `odtEntrySizeDaq` | `0x00u` | `MAX_DTO − identification field size` |
| `odtEntrySizeStim` | `0x00u` | `0x00u` — STIM is out of scope |
| `Xcp_OdtType.odtEntryMaxSize` | `0x07u` | same as `odtEntrySizeDaq` |
| `timestampType` | see §8 | `NO_TIME_STAMP`; unit and ticks are invalid per §1.6.4.1.2.5 |

Identification field size is 1 byte for `ABSOLUTE`, 2 for `RELATIVE_BYTE`, 3 for
`RELATIVE_WORD` and 4 for `RELATIVE_WORD_ALIGNED`, so `MAX_ODT_ENTRY_SIZE_DAQ` at
`MAX_DTO = 8` is 7, 6, 5 or 4.

A generated `XCP_MAX_DTO` macro joins `XCP_PAGING_SUPPORTED` in `Xcp_Cfg.h`, taking the
maximum over all configurations, so the ring buffer's frame array can be sized without
reserving 0x100 bytes per entry the way the CTO buffers do.

### 5.3 Event channels

`config->eventChannel` generates as `NULL_PTR` today; the `events` array is parsed and
discarded. The generator now emits `Xcp_EventChannelType[]` with `number`, `consistency`,
`priority`, `timeCycle`, `timeUnit`, `type` and the resolved `triggeredDaqListRef`.
`timeCycle` and `timeUnit` are carried for `GET_DAQ_EVENT_INFO` in SP2b; per DD2 nothing in
phase 1 acts on them.

### 5.4 Type changes in `Xcp_Types.h`

- `Xcp_OdtEntryType` gains `uint8 addressExtension`. `WRITE_DAQ` carries one at byte 3 and
  the structure has nowhere to put it, so sampling could not honour it.
- `Xcp_DaqListType` gains `const uint8 firstPid` (DD7).
- `Xcp_EventChannelType.triggeredDaqListRef` changes from `const Xcp_DaqListType *` to an
  array of pointers (D13).
- New `Xcp_DaqListRtType` and `Xcp_DtoQueueType`, both reached through `Xcp_RtType`
  exactly as `Xcp_SegmentRtType` is, and generated per configuration by
  `source_rt.c.jinja2`.

```c
typedef struct {
    uint16 eventChannelNumber;  /* SET_DAQ_LIST_MODE bytes 4,5 */
    uint8  mode;                /* SELECTED | DIRECTION | TIMESTAMP | PID_OFF | RUNNING | RESUME */
    uint8  prescaler;           /* 1..255 */
    uint8  prescalerCounter;
    uint8  priority;
} Xcp_DaqListRtType;
```

`Xcp_InternalType` gains the DAQ pointer, which is per session and not per list:

```c
struct {
    uint16  daqListNumber;
    uint8   odtNumber;
    uint8   odtEntryNumber;
    boolean valid;
} daq_pointer;
```

## 6. The DTO data path

### 6.1 Sampling

`Xcp_TriggerEventChannel(uint16 eventChannelNumber)` is the only sampling entry point, and
per DD2 the integrator is the only caller. A channel number at or above `maxEventChannel`
raises `XCP_E_INVALID_EVENT_CHANNEL` through `Xcp_ReportError` and samples nothing.

For each DAQ list whose runtime mode has `RUNNING` set and whose `eventChannelNumber` matches:

1. Advance `prescalerCounter`; skip the list unless it has reached `prescaler`.
2. For each ODT holding at least one entry with a non-zero length, assemble one frame:
   the identification field, then, for each such entry, `length` elements read through
   `Xcp_ReadSlaveMemoryTable[addressGranularity]` from `address` and `addressExtension`.
   The entry descriptors are copied under the exclusive area first and the memory reads use
   the copies, per DD14.
3. Push the finished frame into the ring, tagged with the DAQ list's `pdu_mapping` PDU id.
   A full ring triggers DD6.

Once every list on the channel has been sampled, the trigger calls
`Xcp_StartNextTransmission` if nothing is in flight (DD3). It starts the chain once per
trigger, not once per frame, so a burst is enqueued whole before any of it goes out.

### 6.2 The identification field

| type | bytes | content |
|:--|:--|:--|
| `ABSOLUTE` | 1 | PID = `firstPid + relative ODT number` |
| `RELATIVE_BYTE` | 2 | PID = relative ODT number, then DAQ list number as BYTE |
| `RELATIVE_WORD` | 3 | PID = relative ODT number, then DAQ list number as WORD |
| `RELATIVE_WORD_ALIGNED` | 4 | PID, one FILL byte, then DAQ list number as WORD |

The WORD forms are written through the existing `Xcp_CopyFromU16WithOrder`, so
`protocol_layer.byte_order` is honoured. §1.1.4.1 caps the PID at 0xFB in every form; for
`ABSOLUTE` the check belongs to the generator (DD7), for the relative forms to the
`max_odt` bound already in the schema.

### 6.3 Transmission

`ongoing_transmit_type` gains `ONGOING_TRANSMIT_TYPE_DAQ`. Arbitration moves into one
internal function, `Xcp_StartNextTransmission`, which under the exclusive area of DD5 picks,
in order:

1. a pending CTO response
2. a queued event packet
3. the oldest queued DAQ frame

CTO first means a command response can never be starved by measurement traffic, which matters
because the master's t1 timer is running.

Three contexts call it, per DD3: `Xcp_TriggerEventChannel` after enqueueing,
`Xcp_CanIfTxConfirmation` after clearing the completed transfer, and `Xcp_MainFunction`
whenever `ongoing_transmit_type` is `NONE`. Only the third is a recovery path. DD5 bounds the
exclusive area to exclude the `CanIf_Transmit` call itself, and DD13 keeps the three contexts
from stacking two calls for one PDU.

Note that the confirmation's existing CTO branch already has work to do before arbitrating —
a block transfer continues by refilling the response buffer — so `Xcp_StartNextTransmission`
is called after that branch completes, not instead of it.

`Xcp_CanIfTriggerTransmit` is left as it is. The DAQ path uses `CanIf_Transmit` like every
other path in the module; serving trigger-transmit CanIf configurations is a separate
concern and no part of this sub-project needs it.

## 7. Command specifications

Every handler runs after `Xcp_CanIfRxIndication` has performed the generic pre-checks, so
none of them re-checks connection state, minimum length, `ERR_CMD_BUSY`, `ERR_PGM_ACTIVE` or
resource protection.

`ERR_DAQ_ACTIVE` is *not* generic — it depends on whether any list is running — so the
handlers that §1.7.3.2.4 lists it for raise it themselves.

### 7.1 SET_DAQ_PTR — 0xE2 (§1.6.4.1.1.1)

Request: byte 1 reserved, bytes 2–3 `DAQ_LIST_NUMBER` (WORD), byte 4 `ODT_NUMBER`, byte 5
`ODT_ENTRY_NUMBER`. Positive response is the bare 0xFF.

Validates the list number against `daqCount`, the ODT number against that list's `max_odt`
and the entry number against its `max_odt_entries`; any of them out of range yields
`ERR_OUT_OF_RANGE`. Raises `ERR_DAQ_ACTIVE` if the addressed list is RUNNING. On success it
stores the triple and sets `valid`.

### 7.2 WRITE_DAQ — 0xE1 (§1.6.4.1.1.2)

Request: byte 1 `BIT_OFFSET`, byte 2 size, byte 3 address extension, bytes 4–7 address
(DWORD). Positive response is the bare 0xFF.

- Invalid DAQ pointer → `ERR_OUT_OF_RANGE` (DD10).
- Addressed list RUNNING → `ERR_DAQ_ACTIVE`.
- List number below `MIN_DAQ` → `ERR_WRITE_PROTECTED`, per §1.6.4.1.1.2. `MIN_DAQ` is 0 in
  phase 1, so this is unreachable until predefined lists exist; it is implemented because
  the rule is unconditional and SP2c will make it reachable.
- Size 0, or above `MAX_ODT_ENTRY_SIZE_DAQ`, or not a multiple of
  `GRANULARITY_ODT_ENTRY_SIZE_DAQ` → `ERR_OUT_OF_RANGE`.
- `BIT_OFFSET` in 0x00–0x1F with a size unequal to the granularity → `ERR_OUT_OF_RANGE`
  (DD8). Values 0x20–0xFE are equally invalid; only 0xFF means "ignore".
- The entry's size added to the ODT's already-written entries exceeding the DTO capacity →
  `ERR_DAQ_CONFIG`.

On success it writes address, extension, bit offset and length into the ODT entry, then
post-increments the pointer, invalidating it past the ODT's last entry.

### 7.3 SET_DAQ_LIST_MODE — 0xE0 (§1.6.4.1.1.3)

Request: byte 1 mode, bytes 2–3 `DAQ_LIST_NUMBER`, bytes 4–5 event channel number, byte 6
prescaler, byte 7 priority. Positive response is the bare 0xFF.

- List out of range → `ERR_OUT_OF_RANGE`; list RUNNING → `ERR_DAQ_ACTIVE`.
- Any of `ALTERNATING`, `DIRECTION`, `TIMESTAMP`, `PID_OFF` set → `ERR_MODE_NOT_VALID`
  (DD9).
- Event channel number at or above `maxEventChannel` → `ERR_OUT_OF_RANGE`.
- Prescaler 0 → `ERR_OUT_OF_RANGE`; prescaler above 1 with `prescaler_supported` false →
  `ERR_OUT_OF_RANGE`.
- Priority above 0 → `ERR_OUT_OF_RANGE`, per §1.6.4.1.1.3 (DD9).

On success it stores the channel number, prescaler and priority and resets
`prescalerCounter`.

### 7.4 START_STOP_DAQ_LIST — 0xDE (§1.6.4.1.1.4)

Request: byte 1 mode (0 stop, 1 start, 2 select), bytes 2–3 `DAQ_LIST_NUMBER`.

Positive response: byte 1 `FIRST_PID`. §1.6.4.1.1.4 says the value may be ignored for the
relative identification field types; it is returned in all four cases because the response
format is fixed.

- List out of range → `ERR_OUT_OF_RANGE`; mode above 2 → `ERR_MODE_NOT_VALID`.
- A list with no ODT entry written → `ERR_DAQ_CONFIG`.
- start sets RUNNING; stop clears it; select sets SELECTED without starting transmission.

### 7.5 START_STOP_SYNCH — 0xDD (§1.6.4.1.1.5)

Request: byte 1 mode (0 stop all, 1 start selected, 2 stop selected). Positive response is
the bare 0xFF.

Mode above 2 → `ERR_MODE_NOT_VALID`. Mode 1 with no list selected → `ERR_DAQ_CONFIG`.
§1.6.4.1.1.5 requires SELECTED to be cleared on every affected list after successful
execution, and §1.6.4.1.1.4 requires the same, so the flag is cleared in both paths.

### 7.6 GET_DAQ_LIST_MODE — 0xDF (§1.6.4.1.2.6)

Request: byte 1 reserved, bytes 2–3 `DAQ_LIST_NUMBER`. List out of range →
`ERR_OUT_OF_RANGE`.

Positive response: byte 1 current mode, bytes 2–3 reserved, bytes 4–5 current event channel
number, byte 6 current prescaler, byte 7 current priority. The mode byte reports SELECTED,
DIRECTION, TIMESTAMP, `PID_OFF`, RUNNING and RESUME; phase 1 can only ever set SELECTED and
RUNNING.

### 7.7 CLEAR_DAQ_LIST — 0xE3 (§1.6.4.2.1.1)

Request: byte 1 reserved, bytes 2–3 `DAQ_LIST_NUMBER`. List out of range →
`ERR_OUT_OF_RANGE`.

§1.6.4.2.1.1 requires every ODT entry to be reset to address 0, extension 0, size 0 and
`bit_offset = 0xFF`, the running transmission on the list to be stopped, and all list states
to be reset. It says nothing about refusing the command while the list is running — the
opposite, it requires the stop — which is why the matrix row is corrected in D10.

### 7.8 GET_DAQ_PROCESSOR_INFO — 0xDA (§1.6.4.1.2.4)

Positive response: byte 1 `DAQ_PROPERTIES`, bytes 2–3 `MAX_DAQ`, bytes 4–5
`MAX_EVENT_CHANNEL`, byte 6 `MIN_DAQ`, byte 7 `DAQ_KEY_BYTE`.

`DAQ_PROPERTIES` in phase 1: `DAQ_CONFIG_TYPE` 0 (static), `PRESCALER_SUPPORTED` from
configuration, `RESUME_SUPPORTED` 0, `BIT_STIM_SUPPORTED` 0, `TIMESTAMP_SUPPORTED` 0,
`PID_OFF_SUPPORTED` 0, and the overload bits per DD6 — `OVERLOAD_EVENT` for `EVENT`, both
clear for `NONE`.

`DAQ_KEY_BYTE` carries the identification field type in bits 7:6, `ADDR_EXTENSION` in bits
5:4 and the optimisation type in bits 3:0. Phase 1 reports `Optimisation_Type` =
`OM_DEFAULT` and an address extension type of "can be different within one and the same
ODT", since nothing constrains it.

### 7.9 GET_DAQ_RESOLUTION_INFO — 0xD9 (§1.6.4.1.2.5)

Positive response: byte 1 `GRANULARITY_ODT_ENTRY_SIZE_DAQ`, byte 2
`MAX_ODT_ENTRY_SIZE_DAQ`, byte 3 `GRANULARITY_ODT_ENTRY_SIZE_STIM`, byte 4
`MAX_ODT_ENTRY_SIZE_STIM`, byte 5 `TIMESTAMP_MODE`, bytes 6–7 `TIMESTAMP_TICKS`.

Granularity is the address granularity element size — 1, 2 or 4 for `BYTE`, `WORD`, `DWORD`
— which satisfies the §1.6.4.1.2.5 requirement that it be one of {1,2,4,8}. The STIM fields
are 0. `TIMESTAMP_MODE` and `TIMESTAMP_TICKS` are 0 and explicitly invalid, which
§1.6.4.1.2.5 permits when `TIMESTAMP_SUPPORTED` is clear.

## 8. Defect fixes

**D10 — `CLEAR_DAQ_LIST` reacts to an error §1.7.3.2.4 does not list.** The matrix entry for
0xE3 carries `XCP_INTERNAL_ERR_DAQ_ACTIVE`. The specification's `CLEAR_DAQ_LIST` row lists
`ERR_CMD_BUSY`, `ERR_PGM_ACTIVE`, `ERR_CMD_SYNTAX`, `ERR_OUT_OF_RANGE`, `ERR_ACCESS_DENIED`
and `ERR_ACCESS_LOCKED` — not `ERR_DAQ_ACTIVE`. §1.6.4.2.1.1 confirms it: the command stops
a running transmission rather than refusing while one is active.

**D11 — `WRITE_DAQ_MULTIPLE`'s matrix row is empty.** 0xC7 is `0x00000000u`. The command is
new in 1.1 and did not exist when the matrix was transcribed. Its row and its
`Xcp_PIDToCmdGroupTable` entry are filled in SP2b; the roadmap and `Xcp_Internal.h` are
corrected here so the PID is at least named.

**D12 — the shipped configuration allocates overlapping absolute ODT numbers.**
`config/xcp.json` gives `DAQ1` `pid 0` with `max_odt 3`, claiming absolute ODT numbers 0–2,
and `DAQ2` `pid 1` with `max_odt 5`, claiming 1–5. §1.6.4.1.1.4 requires every ODT to have a
unique absolute number. Under DD7 the generator derives 0 and 3 and rejects the configured
values.

**D13 — `Xcp_EventChannelType.triggeredDaqListRef` cannot express what it names.** It is a
single `const Xcp_DaqListType *` with a separate count, so it can only reference a contiguous
run of DAQ lists, never an arbitrary subset — and `events[].triggered_daq_list_ref` is a list
of names. It has gone unnoticed because the generator emits `NULL_PTR`. It becomes an array
of pointers.

**D14 — `CONNECT` requires all eighteen DAQ commands for the DAQ resource bit.**
`Xcp_CTOCmdStdConnect` sets bit 2 of `RESOURCE` only when every DAQ PID from
`CLEAR_DAQ_LIST` to `ALLOC_ODT_ENTRY` is enabled. §1.6.1.1.1 defines the bit as "DAQ lists
available", a property of the group, and its own note names the commands by example rather
than exhaustively. As written, disabling any optional DAQ command in `xcp.json` switches DAQ
off at `CONNECT` — the same shape of defect DD5 of SP1 found in the CAL/PAG bit with
`SHORT_DOWNLOAD`. The condition narrows to the commands that constitute an available DAQ
list: `CLEAR_DAQ_LIST`, `SET_DAQ_PTR`, `WRITE_DAQ`, `SET_DAQ_LIST_MODE`,
`START_STOP_DAQ_LIST` and `START_STOP_SYNCH`.

**D15 — `GET_STATUS` never reports `DAQ_RUNNING`.** §1.6.1.1.3 defines bit 6 of the session
status as "at least one DAQ list has been started and is in data transfer mode".
`Xcp_Internal.session_status` has no such bit and `Xcp_CTOCmdStdGetStatus` returns the byte
unmodified. A `XCP_SESSION_STATUS_MASK_DAQ_RUNNING` joins the existing masks and is
maintained by the start and stop paths.

**D16 — `Xcp_CanIfTxConfirmation` never starts the next transmission.** It clears the pending
flag and returns, so anything queued waits for the next `Xcp_MainFunction`. A `UPLOAD` block
transfer refills its response buffer in the confirmation but still does not transmit it, and
the event queue behaves the same way. Every multi-frame exchange in the module therefore
advances at the rate the integrator happens to call the main function, which for a background
task is not a rate at all. DD3 fixes this for all three paths at once by having the
confirmation call `Xcp_StartNextTransmission`.

## 9. Generator and schema changes

- `config/xcp.schema.json`: the four new `protocol_layer` keys of §5.1.
- `script/source_cfg.c.jinja2`: the derived values of §5.2, the event channel array of §5.3,
  `firstPid` per DAQ list, and the `addressExtension` initialiser on every ODT entry.
- `script/header_cfg.h.jinja2`: the `XCP_MAX_DTO` macro.
- `script/source_rt.c.jinja2` and `header_rt.h.jinja2`: `Xcp_DaqListRtType[]` and the DTO
  ring per configuration, alongside the existing event queue and segment runtime.
- `config/xcp.json`: the new keys, and the `dtos[].pid` correction of D12.

Generation-time validation added: the `FIRST_PID` uniqueness and 0xFB bound of DD7, and
`max_odt_entries × MAX_ODT_ENTRY_SIZE_DAQ` against what an ODT can actually carry. Every
`events[].triggered_daq_list_ref` name must resolve to a declared DAQ list.

## 10. Test strategy

pytest with CFFI compiling the real translation units, as the existing suite does. New files
on the established naming convention:

| file | covers |
|:--|:--|
| `set_daq_ptr_test.py` | §7.1 |
| `write_daq_test.py` | §7.2, including the bit-offset rules of DD8 and the pointer invalidation of DD10 |
| `set_daq_list_mode_test.py` | §7.3, including every `ERR_MODE_NOT_VALID` path of DD9 |
| `get_daq_list_mode_test.py` | §7.6 |
| `start_stop_daq_list_test.py` | §7.4 |
| `start_stop_synch_test.py` | §7.5 |
| `clear_daq_list_test.py` | §7.7 |
| `get_daq_processor_info_test.py` | §7.8 |
| `get_daq_resolution_info_test.py` | §7.9 |
| `daq_runtime_test.py` | sampling, prescaler division, ring overflow and `EV_DAQ_OVERLOAD`, `Xcp_TriggerEventChannel` including the unknown-channel DET error |
| `daq_transmission_test.py` | arbitration order, a full burst transmitted with `Xcp_MainFunction` never called, recovery from a `CanIf_Transmit` refusal through both the main function and the next trigger, exclusive-area balance, and the DD13 guard under a `CanIf` stub that confirms synchronously from inside `CanIf_Transmit` |
| `daq_concurrency_test.py` | never two `CanIf_Transmit` calls for one PDU on the stack (DD13), never a call made while inside the exclusive area (DD5), and `CLEAR_DAQ_LIST` interleaved with a sample yielding no dereference of a cleared address (DD14) |
| `daq_identification_field_test.py` | all four field types against both byte orders |

The chain of DD3 is what makes an aperiodic main function survivable, so
`daq_transmission_test.py` drives it the way the integration does: trigger a burst without
calling `Xcp_MainFunction` at all, feed confirmations, and assert every frame goes out.
Exclusive-area balance is asserted from the counters in `test/stub/SchM_Xcp.h`.

Existing files that change: `asam_error_matrix_test.py` gains rows for the nine commands and
loses the `ERR_DAQ_ACTIVE` expectation on `CLEAR_DAQ_LIST` (D10); `connect_test.py` gains the
narrowed resource condition (D14); `get_status_test.py` gains `DAQ_RUNNING` (D15);
`upload_test.py` gains the block transfer continuing on confirmation alone (D16);
`conftest.py`'s `DefaultConfig` gains the new keys and the harness compiles six units.

## 11. Acceptance

- The nine commands answer conformantly, including every error path named in §7.
- A master can configure a static DAQ list through `SET_DAQ_PTR` and `WRITE_DAQ`, bind it to
  an event channel with `SET_DAQ_LIST_MODE`, start it, and receive DTO frames whose contents
  match the sampled memory, under all four identification field types.
- `CONNECT` reports the DAQ resource, `GET_STATUS` reports `DAQ_RUNNING`.
- A burst is transmitted in full with `Xcp_MainFunction` never called once — the trigger
  starts the chain and confirmations finish it. This is the property DD3 exists for and the
  one an aperiodic main function would otherwise break.
- A `CanIf_Transmit` refusal strands nothing: the next `Xcp_MainFunction` call resumes the
  chain, and so does the next trigger.
- Every path into and out of the exclusive area is balanced, error paths included.
- Generation fails, with a message naming the offending configuration, on overlapping
  absolute ODT numbers, on a `FIRST_PID` above 0xFB, and on an unresolvable
  `triggered_daq_list_ref`.
- The existing suite passes unchanged.

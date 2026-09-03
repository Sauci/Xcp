# XCP Part 2 — Conformance Roadmap

**Date:** 2026-08-29, revised 2026-09-03 after SP1, SP2a and SP2b
**Baseline:** branch `develop`, commit `35a07ad` (2026-09-03)
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.1*, ASAM e.V. (`docs/external/`).
Version 1.0 is kept alongside it: the two renumber §1.6.4 wholesale, so a citation is only
unambiguous once it names its version.

This document is a map, not an implementation spec. It records where the module stands
against the ASAM specification, what remains, and how the remaining work decomposes into
sub-projects. Each sub-project gets its own design document and implementation plan.

---

## 1. What exists today

An AUTOSAR-style BSW module implementing an XCP **slave** over CAN.

| Concern | Where |
|:--|:--|
| Protocol logic | six translation units, 5835 lines: `Xcp.c` (2097, dispatch and shared machinery), `Xcp_Std.c` (1203), `Xcp_Cal.c` (301), `Xcp_Pag.c` (470), `Xcp_Daq.c` (1341), `Xcp_DaqRuntime.c` (423) |
| Public API | `interface/Xcp.h`, `Xcp_Types.h`, `Xcp_Errors.h`, `XcpOnCan_Cbk.h` |
| Configuration | `config/xcp.json`, validated by `config/xcp.schema.json` |
| Code generation | `script/*.jinja2` → `Xcp_Cfg.{c,h}`, `Xcp_Rt.{c,h}` via `bsw_code_gen` |
| Integrator callbacks | `test/stub/Xcp_{SeedKey,Checksum,MemoryAccess,UserCmd}.h` |
| Tests | `test/*_test.py` — pytest + CFFI compiling the real C, 12574 passing, 30 skipped. `test.sh` reports coverage as the union across compilation variants (`script/gcov_union.py`), since build-time guards make one source several structurally different programs |
| Build | CMake; tests run inside the Alpine image built by `Dockerfile` |
| CI | GitHub Actions → `test.sh` → ctest → codecov |

### 1.1 The dispatch architecture

The design is table-driven, and this is the module's principal asset. Three parallel
256-entry tables indexed by packet identifier:

- **`Xcp_PIDTable`** — handler function pointer per PID.
- **`Xcp_PIDToCmdGroupTable`** — resource group (`CAL_PAG` / `DAQ` / `STIM` / `PGM`) per
  PID, used for seed-and-key protection.
- **`Xcp_CTOErrorMatrix`** — bitmask of the errors each command reacts to, transcribed
  from specification §1.7.3.2.

A fourth table, `ctoInfo[0x100]`, is *generated* from `xcp.json` and carries four fields
per PID: enabled, is-CTO, protected, and minimum request size.

`Xcp_CanIfRxIndication` performs every generic pre-check once, driven by those tables:
connection state, `ERR_CMD_UNKNOWN`, `ERR_CMD_BUSY`, `ERR_CMD_SYNTAX`, `ERR_PGM_ACTIVE`
and resource protection. A handler is therefore responsible only for its own parameter
semantics.

**Consequence for all remaining work:** adding a command is mostly writing its handler.
The error matrix and the group table are already populated for every command in the
specification, including the ones not yet implemented.

---

## 2. Coverage against Part 2

Legend: **done** — implemented and tested · **partial** — reachable but incomplete or
incorrect · **absent** — no handler; the PID dispatches to `Xcp_CmdNotImplemented`, which
answers `ERR_CMD_UNKNOWN` as §1.4 requires.

The **stub** status of the original revision is gone: it described handlers that returned a
positive response without doing anything, which was defect D2, fixed in SP1.

### 2.1 Standard commands (§1.4.1, §1.6.1)

| PID | Command | Status |
|:--|:--|:--|
| 0xFF | CONNECT | done |
| 0xFE | DISCONNECT | done |
| 0xFD | GET_STATUS | yes | reports session configuration id 0, which is truthful while no DAQ configuration is stored; see defect D9 |
| 0xFC | SYNCH | done |
| 0xFB | GET_COMM_MODE_INFO | done |
| 0xFA | GET_ID | partial — identification type 0 (ASCII) only; §1.6.1.2.2 defines 0–4 plus 128–255 user-defined, all implementation-specific |
| 0xF9 | SET_REQUEST | yes | STORE_CAL_REQ implemented; STORE_DAQ_REQ and CLEAR_DAQ_REQ refused with ERR_OUT_OF_RANGE as unsupported modes; see defect D9 |
| 0xF8 | GET_SEED | done |
| 0xF7 | UNLOCK | done |
| 0xF6 | SET_MTA | done |
| 0xF5 | UPLOAD | done — D1 fixed in SP1 |
| 0xF4 | SHORT_UPLOAD | done |
| 0xF3 | BUILD_CHECKSUM | done |
| 0xF2 | TRANSPORT_LAYER_CMD | partial — `GET_SLAVE_ID` only; `SET_DAQ_LIST_CAN_ID` absent |
| 0xF1 | USER_CMD | done |

### 2.2 Calibration commands (§1.4.2, §1.6.2)

| PID | Command | Optional | Status |
|:--|:--|:--|:--|
| 0xF0 | DOWNLOAD | no | done — completed in SP1, block transfer included; D8 fixed |
| 0xEF | DOWNLOAD_NEXT | yes | done |
| 0xEE | DOWNLOAD_MAX | yes | done |
| 0xED | SHORT_DOWNLOAD | yes | done |
| 0xEC | MODIFY_BITS | yes | done |

All five landed in SP1 (#1).

### 2.3 Page switching commands (§1.4.3, §1.6.3)

| PID | Command | Optional | Status |
|:--|:--|:--|:--|
| 0xEB | SET_CAL_PAGE | no | done |
| 0xEA | GET_CAL_PAGE | no | done |
| 0xE9 | GET_PAG_PROCESSOR_INFO | yes | done |
| 0xE8 | GET_SEGMENT_INFO | yes | done |
| 0xE7 | GET_PAGE_INFO | yes | done |
| 0xE6 | SET_SEGMENT_MODE | yes | done |
| 0xE5 | GET_SEGMENT_MODE | yes | done |
| 0xE4 | COPY_CAL_PAGE | yes | done |

All eight landed in SP1 (#1), together with the segment and page configuration model that
did not exist when this document was first written. The whole group is compiled out when
`XCP_PAGING_SUPPORTED` is `STD_OFF`, which the build derives from whether the configuration
declares a segment; the PIDs then dispatch to `Xcp_CmdNotImplemented`.

### 2.4 Data acquisition and stimulation (§1.4.4, §1.6.4)

| PID | Command | Optional | Status |
|:--|:--|:--|:--|
| 0xE3 | CLEAR_DAQ_LIST | no | done |
| 0xE2 | SET_DAQ_PTR | no | done |
| 0xE1 | WRITE_DAQ | no | done |
| 0xE0 | SET_DAQ_LIST_MODE | no | done — every unimplemented mode bit answers `ERR_MODE_NOT_VALID`; a priority above 0 answers `ERR_OUT_OF_RANGE` per §1.6.4.1.1.3 |
| 0xDF | GET_DAQ_LIST_MODE | yes in 1.1 | done |
| 0xDE | START_STOP_DAQ_LIST | no | done |
| 0xDD | START_STOP_SYNCH | no | done |
| 0xDC | GET_DAQ_CLOCK | yes | done — compiled out when no clock is configured |
| 0xDB | READ_DAQ | yes | done |
| 0xDA | GET_DAQ_PROCESSOR_INFO | yes | done |
| 0xD9 | GET_DAQ_RESOLUTION_INFO | yes | done |
| 0xD8 | GET_DAQ_LIST_INFO | yes | done |
| 0xD7 | GET_DAQ_EVENT_INFO | yes | done — publishes the event channel name via the MTA |
| 0xD6 | FREE_DAQ | yes | absent — SP2c |
| 0xD5 | ALLOC_DAQ | yes | absent — SP2c |
| 0xD4 | ALLOC_ODT | yes | absent — SP2c |
| 0xD3 | ALLOC_ODT_ENTRY | yes | absent — SP2c |
| 0xC7 | WRITE_DAQ_MULTIPLE | yes | done — ships **disabled**, since it requires `MAX_CTO >= 10`, which is neither a classic CAN frame size nor a CAN FD payload length |

Fourteen of the eighteen are implemented; the four that remain are the dynamic-configuration
commands of SP2d. The DAQ *runtime* exists: `Xcp_DaqRuntime.c` samples
every running list bound to an event channel, builds the identification field, and queues
complete frames on a ring drained by the transmission chain. All four identification field
types of §1.1.2.1 are supported.

**Event channels are not scheduled by the module.** `Xcp_TriggerEventChannel` is a vendor
extension the integrator calls from whatever context the event actually occurs in; the
module holds no clock and never triggers a channel on its own. This is a decision, not a
gap — see DD1–DD3 of `2026-09-01-xcp-daq-design.md`. `SWS_Xcp` R4.3.1 defines no service for
triggering a DAQ event, and ECUC_Xcp_00014 states the module does not require its main
function period, so a module-driven raster could not have been built on anything the
configuration is allowed to know.

The timestamp field (§1.1.2.2) and `PID_OFF` landed in SP2b. Still absent from the runtime:
`ALTERNATING`, DAQ list prioritisation and more than one outstanding DTO frame — all SP2c — and
STIM reception in `Xcp_CanIfRxIndication`, which remains SP3.

### 2.5 Non-volatile memory programming (§1.4.5, §1.6.5)

All eleven commands — `PROGRAM_START` (0xD2) through `PROGRAM_VERIFY` (0xC8) — **absent**.

### 2.6 Cross-cutting

| Area | Section | Status |
|:--|:--|:--|
| Time-out values t1…t7 | §1.7.2 | **not a slave concern.** §1.7.2 assigns the timers entirely to the master, which reads t1…t6 from the A2L file. The slave implements nothing here |
| `EV_CMD_PENDING` | §1.7.2.4.2 | absent. This is the slave's only obligation under §1.7.2 — the one way it can ask the master to restart time-out detection |
| Interleaved communication model | §1.7.2.3 | absent. Requires the slave to accept request *k+1* before answering *k*; `cto_queue_size` and `interleaved_mode` exist in `xcp.json` but nothing reads them |
| RESUME mode | §1.6.1.1.1, §1.6.4.1.1.4 | `XCP_CONNECTION_STATE_RESUME` is declared but never entered. The DAQ list infrastructure it needs now exists (SP2a), but `SET_DAQ_LIST_MODE` rejects the RESUME bit with `ERR_MODE_NOT_VALID` and `STORE_DAQ_REQ` persistence is unbuilt. Scheduled into SP5 |
| Event codes (EV_*) | §1.2 | `EV_STORE_CAL` (0x03) and `EV_DAQ_OVERLOAD` (0x01), the latter added in SP2a and configurable through `overload_indication`. Absent: `EV_RESUME_MODE`, `EV_CLEAR_DAQ`, `EV_STORE_DAQ`, `EV_CMD_PENDING`, `EV_SESSION_TERMINATED`, `EV_USER`, `EV_TRANSPORT` |
| Service request codes (SERV_*) | §1.3 | absent — `SERV_RESET`, `SERV_TEXT`. Optional for a slave |
| Extended error payloads | §1.1.3.3 | absent — see defect D6 |

One structural observation for later work: the AML in §2.1 declares checksum configuration
**per segment** — a `CHECKSUM` block carrying type, `MAX_BLOCK_SIZE` and
`EXTERNAL_FUNCTION` inside each `Segment`. `config/xcp.json` declares it once globally under
`protocol_layer`. Reconciling the two would change `BUILD_CHECKSUM`, so it is not folded
into SP1; it belongs with D6.

---

## 3. Known defects in existing code

**Status as of 2026-09-03:** D1, D2, D3, D4, D5 and D8 were fixed in SP1; D7 fell out of the
same dispatch rework. D9 was resolved by refusing the two modes it could not fulfil, which also
closed a session-wide denial of service found while investigating it; the non-volatile storage
that would let those modes be accepted is tracked as SP5-NV. D6 remains open and travels with the
per-segment checksum reconciliation noted at the end of §2.6. The entries below are kept as
written, each with its outcome, because the reasoning is what makes the fix reviewable.

These are live in the current baseline, independent of any new feature work.

**D1 — `Xcp_DataTransferInitialize` inverts its range check.** At `source/Xcp.c:3717`:

> **Fixed in SP1.** `Xcp_DataTransferInitialize` now compares against what fits, in `source/Xcp.c`.

```c
if ((Xcp_Ptr->general->maxCto - 0x02u) > (uint16)((numberOfDataElements * elementSize) + alignment))
{
    result = E_NOT_OK;
}
```

The condition rejects requests that fit and accepts requests that overflow. It is reachable
today through `UPLOAD`: with `slave_block_mode` disabled, any request where
`n * AG + alignment < MAX_CTO - 2` returns `ERR_OUT_OF_RANGE`. The suite does not catch it
because the only test exercising that configuration
(`test/upload_test.py:105`) asserts the rejection path. Two further problems in the same
function: the branch uses the `MAX_CTO - 2` budget of `DOWNLOAD` where `UPLOAD`'s is
`MAX_CTO - 1`, and `requested_elements` is assigned before the error paths, latching block
state after a rejected request.

**D2 — commands with no handler answer positively.** `Xcp_PIDTable` maps every PID that
lacks an implementation to `Xcp_DTODaqPacket`, which sets `*responseExpected = TRUE` and
returns `E_OK`. The generator compounds this by hard-coding the `enable` bit for commands
that have no configuration switch: `MODIFY_BITS`, `DOWNLOAD_NEXT`, and all six optional PAG
commands. With the default `config/xcp.json`, a master sending `COPY_CAL_PAGE`,
`GET_SEGMENT_INFO` or `MODIFY_BITS` receives a positive response assembled from stale
buffer contents rather than `ERR_CMD_UNKNOWN`.

> **Fixed in SP1.** Every unimplemented PID dispatches to `Xcp_CmdNotImplemented`, which answers `ERR_CMD_UNKNOWN`.

**D3 — `Xcp_Errors.h` is missing six error codes** required by the CAL and PAG error
matrices: `ERR_WRITE_PROTECTED` (0x23), `ERR_ACCESS_DENIED` (0x24), `ERR_PAGE_NOT_VALID`
(0x26), `ERR_MODE_NOT_VALID` (0x27), `ERR_SEGMENT_NOT_VALID` (0x28) and
`ERR_MEMORY_OVERFLOW` (0x30). The corresponding `XCP_INTERNAL_ERR_*` bits already exist in
`source/Xcp.c` and are already used in `Xcp_CTOErrorMatrix`, so only the wire-value
definitions are missing.

> **Fixed in SP1.** `Xcp_Errors.h` carries all nineteen ASAM codes, including `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE`, new in 1.1.

**D4 — dead and duplicated helpers.** `Xcp_BlockTransferWriteSlaveMemory` and
`Xcp_DataTransferActive` have no callers. `Xcp_DataTransferActive` is a byte-for-byte
duplicate of `Xcp_BlockTransferIsActive`.

> **Fixed in SP1.** `Xcp_DataTransferActive` is deleted. `Xcp_BlockTransferWriteSlaveMemory` is
> still there and is no longer dead: SP1's `DOWNLOAD` block transfer is its caller.

**D5 — `source/Xcp.c` is a single 3876-line translation unit.** Full Part 2 conformance
would plausibly triple that in one file.

> **Fixed in SP1.** Six translation units; see the table in §1.

**D6 — `BUILD_CHECKSUM` omits its extended error payload.** §1.6.1.2.9 defines a specific
negative-response layout — byte 0 `0xFE`, byte 1 the error code, bytes 2,3 reserved, bytes
4..7 the DWORD maximum block size — and §1.1.3.3 repeats the requirement. The handler calls
plain `Xcp_FillErrorPacket`, so the master receives a bare error code and cannot learn the
limit. There is also no configuration field for the maximum block size; the AML declares it
as `MAX_BLOCK_SIZE` inside a per-segment `CHECKSUM` block (§2.1). Fixing this needs the same
extended-error mechanism that `DOWNLOAD_NEXT` requires for its `ERR_SEQUENCE` payload
(§1.6.2.2.1), which SP1 introduces — so this is cheapest to fix immediately after SP1.

> **Open.** Belongs with the per-segment checksum reconciliation described at the end of §2.6.

(The checksum *type* mapping is correct: `Xcp_ChecksumType` is a zero-based internal enum,
but `Xcp_DTOCmdStdBuildChecksum` translates it explicitly to the ASAM wire values 0x01..0x09
and 0xFF at `source/Xcp.c:2639` before transmitting.)

**D8 — `DOWNLOAD` block transfer is gated on the slave block-mode flag.** §1.6.1.2.1 defines
`MAX_BS` as a *master* block-mode parameter and names its packets as `DOWNLOAD_NEXT` or
`PROGRAM_NEXT`; `SLAVE_BLOCK_MODE` (§1.6.1.1.1) governs the opposite direction and belongs to
`UPLOAD`. But `Xcp_DTOCmdCalDownload` (`source/Xcp.c:2487`) and `Xcp_DataTransferInitialize`
(`source/Xcp.c:3716`) both test `slaveBlockModeSupported`, while the module's own
`GET_COMM_MODE_INFO` handler correctly reports `MAX_BS` and `MIN_ST` under
`masterBlockModeSupported` (`source/Xcp.c:3145`). The module contradicts what it advertises.

> **Fixed in SP1.**

Latent only because `config/xcp.json` enables both flags. A configuration with
`master_block_mode: false, slave_block_mode: true` would accept multi-packet `DOWNLOAD`
sequences it must reject; the inverse would reject valid ones. No test varies the two
independently. Fixed as part of SP1.

**D9 — the session configuration id is not implemented.** §1.6.1.1.3 defines `GET_STATUS`
bytes 4,5 as the session configuration id, and §1.6.1.2.3 has `SET_REQUEST` carry it in
bytes 2,3, requiring the slave to store it in non-volatile memory on `STORE_DAQ_REQ` and
reset it to 0 on `CLEAR_DAQ_REQ`. `Xcp_CTOCmdStdGetStatus` returns the constant `0xABCD`
(`source/Xcp.c:3193`) and `Xcp_DTOCmdStdSetRequest` carries a TODO acknowledging the gap
(`source/Xcp.c:3078`). The skipped placeholder
`test_get_status_returns_the_current_session_status_for_bytes_6_7` in
`test/get_status_test.py` is the marker left for it — note its name misstates the byte
offsets. Because persistence is defined in terms of DAQ list storage, this belongs with SP2.

> **Resolved 2026-09-03, by refusal rather than by implementation.** Investigating this found the
> defect was not the cosmetic one described above. `SET_REQUEST` accepted `STORE_DAQ_REQ` and
> `CLEAR_DAQ_REQ` and OR-ed them into `Xcp_Internal.session_status`; no code fulfils either
> request, so nothing ever cleared the bit, and the `ERR_PGM_ACTIVE` gate in
> `Xcp_CanIfRxIndication` (`source/Xcp.c`) refuses **every command carrying that flag — 42 of
> them — for as long as one of the three request bits is set**. A single conformant `SET_REQUEST`
> therefore disabled most of the command set until the next `CONNECT`. `STORE_CAL_REQ` was never
> affected: `Xcp_MainFunction` fulfils it and clears its bit.
>
> The nonzero-session-id rejection was also inert. It ran after the success branch had been
> entered, so it set the local `result` and then finalized a positive response regardless — the
> error never reached the master, and the check only read as validation.
>
> §1.6.1.2.3's own escape hatch — *"If the slave device does not support the requested mode, an
> ERR_OUT_OF_RANGE will be returned"* — makes refusing both modes fully conformant, and it agrees
> with what the module already advertises, since `GET_DAQ_PROCESSOR_INFO` reports RESUME
> unsupported and non-volatile DAQ storage exists to serve RESUME. `GET_STATUS` now reports
> session configuration id 0, the value the specification itself resets it to.
>
> **This closes the misreporting, not the feature.** Accepting the two modes needs non-volatile
> storage, tracked as SP5-NV below.

**D7 — `Xcp_PIDTable` misroutes the entire command space above 0xE3.** §1.1.5.1 fixes the
master-to-slave identifier space at `0xC0..0xFF` for commands and `0x00..0xBF` for STIM ODT
numbers; DAQ identifiers only ever travel slave-to-master (§1.1.5.2). Yet roughly thirty
entries in the command half of the table point at `Xcp_DTODaqPacket`. Combined with the
hard-coded enable bits of D2, this is what makes unimplemented commands answer positively.
SP1 removes `Xcp_DTODaqPacket` from the table entirely.

> **Fixed.** Resolved by the same dispatch rework as D2; the table now routes 0xC0–0xFF correctly.

---

## 4. Decomposition

Ordered. Each sub-project is independently shippable and leaves the suite green.

**Progress:** SP1 is complete (#1). SP2a is complete (#2), with follow-ups in #3 and #4. SP2b is
complete (#6), with a hygiene pass in #7. **SP2c is next.**

### SP1 — Calibration and page switching (CAL + PAG) — **complete**

Completes `DOWNLOAD`, implements the four optional CAL commands and all eight PAG commands,
introduces the segment/page configuration model, and fixes D1–D4. Opens with the source
split (D5) as a move-only refactor.

Design: `2026-08-29-xcp-cal-pag-design.md`.

**Why first.** `DOWNLOAD` is mandatory and half-written; the block-transfer machinery it
needs already exists and merely lacks a caller. `SET_CAL_PAGE` and `GET_CAL_PAGE` are
mandatory too, and D2 means paging commands are actively misbehaving today. Together they
make the slave genuinely usable for calibration — the smallest coherent slice with real
external value.

### SP2 — Data acquisition (DAQ)

The eighteen DAQ commands of 1.1 — the seventeen of 1.0 plus `WRITE_DAQ_MULTIPLE` (`0xC7`)
— static and dynamic list configuration, ODT-to-DTO transmission, event-channel triggering,
the identification field variants of §1.1.2.1 and the timestamp field of §1.1.2.2.

This paragraph originally placed event-channel scheduling "in `Xcp_MainFunction`". SP2a
rejected that: the module holds no clock and the integrator calls `Xcp_TriggerEventChannel`
from the context the event occurs in. See §2.4 and DD1–DD3 of the DAQ design.

Depends on SP1 only for the source layout. The largest and riskiest sub-project, decomposed
into three phases, each of which leaves a slave that works rather than a layer that does
not:

- **SP2a** — **complete.** Static DAQ measurement end to end: the mandatory basic and static
  commands, the two discovery commands, the configuration model, all four identification
  field types, and the sampling and transmission runtime. Design:
  `2026-09-01-xcp-daq-design.md`.
- **SP2b** — **complete** (#6). The remaining optional commands (`WRITE_DAQ_MULTIPLE`, `READ_DAQ`,
  `GET_DAQ_CLOCK`, `GET_DAQ_LIST_INFO`, `GET_DAQ_EVENT_INFO`), the timestamp field, `PID_OFF`,
  `ALTERNATING`, DAQ list prioritisation, and multiple outstanding DTO frames.

  Those last two are not of a kind with the rest. Five new command handlers extend a dispatch
  surface that already works; prioritisation and multiple outstanding frames change the
  transmission chain SP2a built — the one guarded by the `SchM` exclusive area and shaped by
  D16. Scope them deliberately, and consider splitting them out, rather than treating the
  bullet as one homogeneous list.
- **SP2c** — DAQ list prioritisation and more than one outstanding DTO frame. **Deferred, and it
  buys no conformance.** §1.6.4.1.1.3 states outright that *"If the ECU doesn't support the
  prioritization of DAQ lists, a DAQ list priority > 0 is not allowed and will be indicated by
  returning ERR_OUT_OF_RANGE"*, which is exactly what the module does today; and "more than one
  outstanding DTO frame" is not a protocol concept at all, only throughput. SP2b made a full ring
  a *reported* condition through `EV_DAQ_OVERLOAD`, so the current single-frame chain is slow
  under load, never silent. Schedule this against a measured throughput requirement, not against
  the specification.

  `ALTERNATING` was removed from this entry on 2026-09-02 and needs no further work. It is
  declared through `DAQ_ALTERNATING_SUPPORTED` in the **A2L file**, which this module does not
  emit, and it takes a display event channel number; the protocol layer gives it no slave-side
  transmission semantics, and 1.1 forbids combining it with `TIMESTAMP`, which SP2b shipped. It is
  refused at bit 0 of the `SET_DAQ_LIST_MODE` mode byte, where 1.1 puts it.

  Unlike SP2a and SP2b, this is not additive. Those extended a dispatch surface that already
  worked; SP2c reworks the confirmation-driven transmission chain that DD3 built and the `SchM`
  exclusive area guards, with the sampler running in interrupt context against it. The two halves
  also differ in risk: prioritisation reorders what the ring already holds, while multiple
  outstanding frames changes the ring's own invariants. Consider splitting them.

- **SP2d** — **next.** Dynamic DAQ list configuration (§1.6.4.2 in 1.0, renumbered in 1.1), the
  `DAQ_CONFIG_TYPE` = dynamic branch, and the four remaining commands: `FREE_DAQ` (0xD6),
  `ALLOC_DAQ` (0xD5), `ALLOC_ODT` (0xD4) and `ALLOC_ODT_ENTRY` (0xD3). Chosen ahead of SP2c
  because it is additive to the dispatch surface, and because a master that cannot allocate its
  own lists is confined to whatever the generated static configuration happens to contain.

An earlier revision of this section proposed decomposing by layer — configuration model,
then command surface, then runtime. That was rejected when the design was written: no layer
is independently shippable, since configured lists that never transmit have no value to a
master.

### SP3 — Synchronous data stimulation (STIM)

STIM reception in `Xcp_CanIfRxIndication`, `DAQ_STIM` and `STIM` event channel types.
Depends on SP2 for the DAQ list infrastructure it reuses wholesale.

**Concurrency question SP3 must answer, found in SP2b.** SWS_Xcp_00813 specifies
`Xcp_<Lo>RxIndication` as *"Reentrant for different PduIds. Non reentrant for the same PduId."*
Every CTO command reaches the module on one PduId — `channel_rx_pdu_ref->id` — so CanIf's own
contract prevents a CTO from racing itself, and no exclusive area guards `cto_response`, `last_pid`
or the protection-status clear today.

**STIM breaks that.** DAQ_STIM receive PDUs are *different* PduIds, so a stimulation indication may
preempt a CTO command mid-dispatch. The branch that will host it already exists in
`Xcp_CanIfRxIndication` and today only sets `valid_pdu_id`, touching nothing shared. The moment
SP3's handler touches the response buffer, the DAQ pointer, the runtime mode bits or the DTO ring,
the race is real and needs an exclusive area around the busy-check/dispatch/set-flag sequence —
which affects all 256 PID entries and is a design decision, not an implementation detail.
Settle it in SP3's design; do not discover it in review.

### SP4 — Non-volatile memory programming (PGM)

The eleven PGM commands and their integrator callbacks. Independent of SP2 and SP3;
schedulable whenever flash programming becomes a requirement.

### SP5 — Protocol completion

The residue: the interleaved communication model (§1.7.2.3), `EV_CMD_PENDING` (§1.7.2.4.2),
RESUME mode, `GET_ID` identification types 1–4 and 128–255 (§1.6.1.2.2),
`SET_DAQ_LIST_CAN_ID`, the remaining `EV_*` event codes and the `SERV_*` service request codes.

Note that time-out handling itself is *not* here: §1.7.2 places the t1…t6 timers entirely on
the master. `EV_CMD_PENDING` and the interleaved request queue are the slave's whole share
of that chapter.

#### SP5-NV — non-volatile DAQ storage

Everything the module currently refuses because it keeps no non-volatile DAQ configuration:
`SET_REQUEST`'s `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` modes, the session configuration id that is
stored and cleared alongside them (§1.6.1.2.3), the `GET_STATUS` byte pair that reports it, and
RESUME mode itself, which is what the whole mechanism exists to serve. D9 closed the
*misreporting* by refusing these modes outright; this item is what would let them be accepted.

**Intended shape** (agreed 2026-09-03, not yet designed): an integrator-provided callback pair
for storing and reading the configuration, **asynchronous**, following the pattern already
established by `Xcp_StoreCalibrationDataToNonVolatileMemory` — which `Xcp_MainFunction` polls
until it reports completion, then clears the request bit and raises `EV_STORE_CAL`. The DAQ side
needs the same treatment for `EV_STORE_DAQ` and `EV_CLEAR_DAQ`, plus a read path at
initialisation that RESUME depends on and that calibration has no equivalent of.

Three things this must get right, all of them discovered by D9:

- **A request bit that is never cleared is a denial of service, not a cosmetic flaw.** The
  `ERR_PGM_ACTIVE` gate in `Xcp_CanIfRxIndication` refuses the 42 commands that carry it while
  any of the three request bits is set. Any asynchronous store must guarantee the bit is
  cleared on *every* exit path, including callback failure, or it reintroduces exactly what D9
  removed.
- **Storing has an ordering requirement.** §1.6.1.2.3: the slave must first clear any DAQ list
  configuration already in non-volatile memory, then store the new one — so a store interrupted
  midway must not leave a configuration the master would take for complete.
- **`GET_DAQ_PROCESSOR_INFO` must stop reporting RESUME unsupported at the same time**, and the
  refusals in `SET_REQUEST` and `SET_DAQ_LIST_MODE` must be lifted together with it. The
  module's advertisement and its refusals are currently consistent; changing one without the
  others is what would make it incoherent.

**Dependencies.** `SET_DAQ_LIST_CAN_ID` and SP5-NV both depend on SP2 — RESUME is a
`SET_DAQ_LIST_MODE` bit backed by `STORE_DAQ_REQ` persistence, and the session configuration
id is persisted and cleared through the same DAQ storage mechanism. Only the interleaved
model, `EV_CMD_PENDING`, `GET_ID` types and the `SERV_*` codes are genuinely independent and
can be pulled forward if one of them blocks an integration.

---

## 5. Non-goals for the roadmap

- Transport layers other than CAN. Part 3 defines SxI, Ethernet and FlexRay; `xcp.json`
  reserves flags for them but nothing else in the module anticipates them.
- The XCP master role.
- XCP versions later than 1.1. **Corrected 2026-09-01:** this entry previously read "later
  than 1.0" and claimed that command codes in the DAQ range were reassigned in 1.1. Both
  specifications were compared directly and the codes are identical — `0xD3` `ALLOC_ODT_ENTRY`
  through `0xE3` `CLEAR_DAQ_LIST` hold in both. What 1.1 changes in this range is
  categorisation, plus one addition:
  `GET_DAQ_LIST_MODE` (`0xDF`) becomes optional, `FREE_DAQ` and the three `ALLOC_*` commands
  become mandatory *for dynamic configuration*, and `WRITE_DAQ_MULTIPLE` (`0xC7`) is new. The
  section numbering of §1.6.4, however, does shift wholesale; see §0 of
  `2026-09-01-xcp-daq-design.md`.
- ASAM MCD 2MC / A2L description file generation (Part 2 §2).

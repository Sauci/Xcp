# XCP Part 2 — Conformance Roadmap

**Date:** 2026-08-29, revised 2026-09-03 after SP1, SP2a and SP2b
**Baseline:** branch `develop`, commit `35a07ad` (2026-09-03)
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.1*, ASAM e.V. (`docs/external/`).
Version 1.0 is kept alongside it: the two renumber §1.6.4 wholesale, so a citation is only
unambiguous once it names its version.

### The revision rule, and what it cost to learn twice

**Before implementing a command, read its section in BOTH revisions — not only to resolve the
section number, but to compare what the sections say.** 1.1 is the reference; 1.0 is readable via
`pdftotext -layout`, while 1.1's text layer is enciphered (glyph substitution), which is why
`XCP -Part 2- Protocol Layer Specification -1.1.ocr.txt` exists. The OCR carries the prose reliably
and **misaligns table columns**, so a *bit position* read from it is not evidence. The cipher is
recoverable from known word pairs when a table has to be read exactly.

The rule started narrower — check both revisions for renumbering, and for error codes 1.1 adds to a
command's row — and it kept being right about the wrong things. What it missed:

| Divergence | Cost |
|---|---|
| 1.1 renumbers `§1.6.4.1.2.x` | caught in time; `GET_DAQ_PROCESSOR_INFO` is correct *only* because its citation says `1.1/` |
| 1.1 adds `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` (`0x33`) to STD rows | caught late in SP5-NV, and only because the user challenged a claim that nothing was reportable |
| 1.1 **adds a mode bit and re-points an existing one** | missed. SP5-NV cited `1.0/§1.6.1.2.3` for `SET_REQUEST`, and three defects followed from that one choice |
| 1.1 attaches an obligation to a command a phase newly enables | missed. `SET_REQUEST` acknowledging a store must reset `SELECTED` (§1.6.4.1.1.6) — vacuous while the mode was refused, live the moment it was accepted |

The last two shipped and were fixed in PRs #23, #24 and #25. Two per-task reviews and a whole-branch
review passed the middle one, because nothing in the diff looked wrong — the defect was in what the
diff *enabled elsewhere*. So the rule has a second half:

**When a phase makes a previously-refused command or mode acceptable, re-read every section that
mentions it.** A requirement that was vacuous because nothing could reach it becomes live at that
moment, and it will not appear in the diff.

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
| 0xF9 | SET_REQUEST | yes | STORE_CAL_REQ implemented. STORE_DAQ_REQ (`STORE_DAQ_REQ_NO_RESUME`/`STORE_DAQ_REQ_RESUME`) and CLEAR_DAQ_REQ are each accepted once their own non-volatile storage callback is configured in, refused with `ERR_OUT_OF_RANGE` otherwise — this row's "refused ... as unsupported modes" was true before SP5-NV and is stale since (DD94-DD102); requesting both DAQ store modes together is refused too, a deliberate choice where 1.1 is silent rather than something it requires (SP5-RESUME). See §2.6's RESUME mode row and defect D9 |
| 0xF8 | GET_SEED | done |
| 0xF7 | UNLOCK | done |
| 0xF6 | SET_MTA | done |
| 0xF5 | UPLOAD | done — D1 fixed in SP1 |
| 0xF4 | SHORT_UPLOAD | done |
| 0xF3 | BUILD_CHECKSUM | done |
| 0xF2 | TRANSPORT_LAYER_CMD | done — `GET_SLAVE_ID` and `GET_DAQ_ID`; `SET_DAQ_ID` excluded by SWS_Xcp §4.1 |
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

The timestamp field (§1.1.2.2) and `PID_OFF` landed in SP2b; STIM reception in
`Xcp_CanIfRxIndication` landed in SP3. Still absent from the runtime: `ALTERNATING`, DAQ list
prioritisation and more than one outstanding DTO frame — all SP2c — and, from SP3, `BIT_STIM` and
`EV_STIM_TIMEOUT`.

### 2.5 Non-volatile memory programming (§1.4.5, §1.6.5)

All eleven commands — `PROGRAM_START` (0xD2) through `PROGRAM_VERIFY` (0xC8) — **absent**.

### 2.6 Cross-cutting

| Area | Section | Status |
|:--|:--|:--|
| Time-out values t1…t7 | §1.7.2 | **not a slave concern.** §1.7.2 assigns the timers entirely to the master, which reads t1…t6 from the A2L file. The slave implements nothing here |
| `EV_CMD_PENDING` | §1.7.2.4.2 | **done — shipped in SP4.** `Xcp_Pgm.c` pushes it while a deferred programming operation is still busy, and `Xcp_CanIfTxConfirmation` releases its rate bound (DD54), so the rate follows TxConfirmation rather than `Xcp_MainFunction`'s period. Gated by `XCP_FLASH_PROGRAMMING_ENABLED`, because programming holds the only pending window this module has: `SET_REQUEST` answers immediately and signals completion by event instead. This row read "absent" until SP5 checked it |
| Interleaved communication model | §1.7.2.3 | **absent, and deliberately unadvertised.** §1.7.2.3 itself is master-side only; the slave's whole obligation is one sentence in 1.0/§1.6.1.1.3 — accept up to `QUEUE_SIZE` "consecutive command packets the master can send to the receipt queue of the slave". This module has no such queue: a second request arriving while a response is unconfirmed is refused `ERR_CMD_BUSY`. This row previously said `cto_queue_size` and `interleaved_mode` "exist in `xcp.json` but nothing reads them" — both *were* read, straight into `GET_COMM_MODE_INFO`'s `COMM_MODE_OPTIONAL` bit 1 and `QUEUE_SIZE`, and into `PROGRAM_START`'s `COMM_MODE_PGM`/`QUEUE_SIZE_PGM`, so a build setting the flag advertised a queue depth the slave would refuse at the second packet. Both fields are gone; the bit is hardcoded clear and both queue-size bytes report 0 |
| RESUME mode | §1.6.1.1.1, §1.6.4.1.1.4 | **Complete, SP5-RESUME** (`2026-09-10-xcp-daq-resume-design.md`, DD103–DD107; see that sub-project's own entry in §4). `XCP_CONNECTION_STATE_RESUME` was declared but never entered; it now is, by `Xcp_ResumeComplete`, called by the integrator once its own `Xcp_Restore*` sequence has repopulated a DAQ list from non-volatile memory this module never reads itself (DD103, the mirror of SP5-NV's own four accessors). `SET_REQUEST`'s `STORE_DAQ_REQ_RESUME` (mode bit 2) is accepted and `GET_DAQ_PROCESSOR_INFO` reports `RESUME_SUPPORTED` set — both were previously refused/clear specifically so the two facts stayed coherent (D9), and SP5-RESUME reverses both together for the identical reason. `SET_DAQ_LIST_MODE` is unaffected: it still does not reject its own RESUME bit with `ERR_MODE_NOT_VALID`, and has not since commit `13f59c2` predating SP5-NV — 1.1 marks that bit don't-care, and the slave tolerates it without honouring it; only `Xcp_ResumeComplete` ever sets a list's own RESUME/RUNNING mode bits |
| Event codes (EV_*) | §1.2 | `EV_STORE_CAL` (0x03) and `EV_DAQ_OVERLOAD` (0x06), the latter added in SP2a and configurable through `overload_indication`. `EV_CLEAR_DAQ` (0x01) and `EV_STORE_DAQ` (0x02) added in SP5-NV. `EV_RESUME_MODE` (0x00) added in SP5-RESUME, queued by `Xcp_ResumeComplete`. `EV_CMD_PENDING` was also listed absent here, which was already stale independent of this row's own RESUME correction — this row's own §2.6 neighbour above has read `done — shipped in SP4` since before SP5-RESUME existed. Absent: `EV_SESSION_TERMINATED`, `EV_USER`, `EV_TRANSPORT` |
| Service request codes (SERV_*) | §1.3 | absent — `SERV_RESET`, `SERV_TEXT`. Optional for a slave |
| Extended error payloads | §1.1.3.3 | absent — see defect D6 |

One structural observation for later work: the AML in §2.1 declares checksum configuration
**per segment** — a `CHECKSUM` block carrying type, `MAX_BLOCK_SIZE` and
`EXTERNAL_FUNCTION` inside each `Segment`. `config/xcp.json` declares it once globally under
`protocol_layer`. Reconciling the two would change `BUILD_CHECKSUM`, so it is not folded
into SP1; it belongs with D6.

---

## 3. Known defects in existing code

**Status as of 2026-09-06:** D1, D2, D3, D4, D5 and D8 were fixed in SP1; D7 fell out of the
same dispatch rework. D9 was resolved by refusing the two modes it could not fulfil, which also
closed a session-wide denial of service found while investigating it; the non-volatile storage
that would let those modes be accepted is tracked as SP5-NV. D6 remains open and travels with the
per-segment checksum reconciliation noted at the end of §2.6. D10 and D11 were found while
surveying SP4 and are fixed by SP4a; both are written up in §5 beside that sub-project rather
than here, because neither is separable from the design that closes them. The entries below are
kept as written, each with its outcome, because the reasoning is what makes the fix reviewable.

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
complete (#6), with a hygiene pass in #7. SP2d is complete (#12). SP3 is complete. SP4a is complete
(#16), SP4b is complete (#17), and SP4c is complete — **so SP4, and with it the whole PGM command
group, is complete: all eleven PGM commands are implemented.** **SP2c remains deferred — see its
own entry below for why, which is unchanged — so SP5 is next.**

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

- **SP2d** — **complete** (#12). Dynamic DAQ list configuration (§1.6.4.2 in 1.0, renumbered in
  1.1), the `DAQ_CONFIG_TYPE` = dynamic branch, and the four remaining commands: `FREE_DAQ` (0xD6),
  `ALLOC_DAQ` (0xD5), `ALLOC_ODT` (0xD4) and `ALLOC_ODT_ENTRY` (0xD3). Chosen ahead of SP2c
  because it is additive to the dispatch surface, and because a master that cannot allocate its
  own lists is confined to whatever the generated static configuration happens to contain.

An earlier revision of this section proposed decomposing by layer — configuration model,
then command surface, then runtime. That was rejected when the design was written: no layer
is independently shippable, since configured lists that never transmit have no value to a
master.

### SP3 — Synchronous data stimulation (STIM) — **complete**

STIM reception in `Xcp_CanIfRxIndication`, `DAQ_STIM` and `STIM` DAQ list types. Depends on SP2 for
the DAQ list infrastructure it reuses wholesale.

Design: `2026-09-04-xcp-stim-sp3-design.md` (DD35–DD48).

**The concurrency question this sub-project had to answer, found in SP2b, and how it was answered.**
SWS_Xcp_00813 specifies `Xcp_<Lo>RxIndication` as *"Reentrant for different PduIds. Non reentrant
for the same PduId."* Every CTO command reaches the module on one PduId — `channel_rx_pdu_ref->id`
— so CanIf's own contract prevents a CTO from racing itself, and no exclusive area guards
`cto_response`, `last_pid` or the protection-status clear. DAQ_STIM receive PDUs are *different*
PduIds, so a stimulation indication may preempt a CTO command mid-dispatch, and the fear was that
guarding it would need an exclusive area around the whole busy-check/dispatch/set-flag sequence.

It did not. **DD36** keeps the receive path off everything the dispatch touches: reception copies
the frame into a per-ODT slot and returns, and the event trigger — not the receive context — writes
ECU memory. The slot is guarded by its own exclusive area, `SchM_Enter_Xcp_StimBuffer` (**DD37**),
which is disjoint from the DTO ring's. Nothing was added to the CTO dispatch path, and a DAQ-only
build is byte-for-byte unchanged.

**DD46** settled the routing that the original note did not anticipate: CTO and DTO are told apart
by the *receiving PduId*, not by the frame's first byte. Splitting on the byte would have let a
`PID_OFF` stimulation payload whose first byte fell in `0xC0..0xFF` be dispatched as a command —
which, past the handler, also clears the protection status and so silently revokes a completed
seed-and-key unlock.

**Deferred out of SP3, each needing its own design:** `BIT_STIM`, `EV_STIM_TIMEOUT`, and runtime
protection of the STIM resource (**DD41** — `Xcp_PIDToCmdGroupTable` is a per-PID mask that cannot
express a predicate on a command's argument, and `SET_DAQ_LIST_MODE` has no `ERR_ACCESS_LOCKED` in
its error set). Until that lands, **DD48** makes generation refuse the one configuration where the
gap would be visible: stimulation-capable *and* declaring the STIM resource protected.

### SP4 — Non-volatile memory programming (PGM) — **complete**

The eleven PGM commands and their integrator callbacks. Independent of SP2 and SP3;
schedulable whenever flash programming becomes a requirement.

AUTOSAR scopes this in, unlike `SET_DAQ_ID`: SRS_Xcp_29020 maps to SWS_Xcp_00855 ("shall support
the flash programming (PGM)") and SWS_Xcp_00856, and `XcpFlashProgrammingEnabled`
(ECUC_Xcp_00181) is its pre-compile gate.

Eleven commands, a deferred-response model and a flash sector configuration model are more than
one design can carry, so SP4 is **three sub-projects**:

- **SP4a — programming session and deferred responses — complete.** `PROGRAM_START` (0xD2),
  `PROGRAM_RESET` (0xCF), `PROGRAM_PREPARE` (0xCC); the session state machine and the gate that
  refuses clear/program commands before `PROGRAM_START`; the pending-command slot, the polled
  integrator callbacks and `EV_CMD_PENDING`; the `XCP_FLASH_PROGRAMMING_ENABLED` compile gate; and
  defects D10 and D11, now fixed (below). Design: `2026-09-06-xcp-pgm-sp4a-design.md` (DD49–DD61).
  `test/pgm_acceptance_test.py` walks `CONNECT` through `PROGRAM_RESET` against a deliberately
  slow integrator, composing what each task's own tests had only verified in isolation.
- **SP4b — clear and program, absolute access mode — complete.** `PROGRAM_CLEAR` (0xD1),
  `PROGRAM` (0xD0), `PROGRAM_MAX` (0xC9), `PROGRAM_NEXT` (0xCA), `GET_PGM_PROCESSOR_INFO` (0xCE).
  The first slice where flash contents change, and the first where `CONNECT` legitimately
  advertises PGM — D10 fixed in the direction SP4a could not test. Design:
  `2026-09-07-xcp-pgm-sp4b-design.md` (DD62–DD69). `test/pgm_acceptance_test.py`'s walk now
  continues past `PROGRAM_START` through a genuine `PROGRAM_CLEAR` and a multi-frame
  `PROGRAM`/`PROGRAM_NEXT` block before `PROGRAM_RESET`, composing SP4b's own contribution into
  the same end-to-end sequence SP4a's Task 6 began.
- **SP4c — sectors, formats and verification — complete.** `PROGRAM_VERIFY` (0xC8),
  `GET_SECTOR_INFO` (0xCD) and the flash sector configuration model, `PROGRAM_FORMAT` (0xCB), and
  functional access mode for both `PROGRAM_CLEAR` (clearing by area rather than by address) and
  `PROGRAM` (the Block Sequence Counter of §1.6.5.1.3, counted by the slave rather than transmitted
  by the master). Design: `2026-09-08-xcp-pgm-sp4c-design.md` (DD84–DD93). `PGM_PROPERTIES` stops
  being a constant: it now advertises exactly what this build's configuration offers, and
  generation refuses a configuration that offers functional access by halves, so
  `GET_PGM_PROCESSOR_INFO`'s claim and `PROGRAM_FORMAT`'s acceptance are one fact rather than two
  kept in step. `test/pgm_functional_test.py` walks two end-to-end sequences — one purely
  functional, one mixing a functional clear with absolute programming, which §1.6.5.2.4 permits
  outright — beside the `test/pgm_acceptance_test.py` walk SP4a and SP4b built.

  Functional access is **off by default**, in `config/xcp.json` and in the test suite's own default
  configuration alike: it asks the integrator for two callbacks whose semantics only the ECU's own
  flash driver can supply (§1.6.5.1.3's "the ECU software knows the start address for the new flash
  content automatically", §1.6.5.1.2's erase-by-area), so a build that has not written them must not
  advertise them. Absolute access stays unconditional.

**D10 — `CONNECT` advertises flash programming that answers `ERR_CMD_UNKNOWN`.** With the shipped
`config/xcp.json`, `CONNECT` returns resource byte `0x15`, setting the PGM bit (§1.6.1.1.1), while
all eleven PGM PIDs dispatch to `Xcp_CmdNotImplemented`. Measured against a default handle, not
inferred. Same class as SP3's advertised-but-ungated `STIM` resource.

> **Fixed, commit `83cb11d`.** DD58's compile gate defaults off, so the default configuration
> stops making the claim. Confirmed at the generated constant, not only on the wire, because the
> wire cannot tell the difference: `Xcp_CmdNotImplemented` and a disabled `ctoInfo` entry both
> answer `ERR_CMD_UNKNOWN` identically (source/Xcp.c), which is the reason this defect could ship
> unnoticed in the first place. `test_every_pgm_ctoinfo_entry_generates_disabled_with_the_gate_off`
> (test/pgm_configuration_test.py, added in Task 6) reads all eleven `ctoInfo` enable bits out of
> the generated source directly and pins the ten that used to be hard-coded `0x01u` regardless of
> configuration.

**D11 — two of the three PGM API configuration keys are dead.** `script/source_cfg.c.jinja2`
hard-codes the `ctoInfo` enable bit for the whole PGM block except `xcp_program_max_api_enable`,
so `xcp_program_api_enable` and `xcp_program_clear_api_enable` are accepted and ignored.
`Xcp_CTOCmdStdConnect` tests all three, making its three-term conjunction one term in practice —
and `test_connect_sets_the_resource_pgm_bit_according_to_enabled_apis` passes all four of its
cases on that one term, so it would not notice the other two being deleted.

> **Fixed, commit `83cb11d`.** DD59 templates all eleven `ctoInfo` enable bits on their own
> configuration key instead of a hard-coded constant, and DD60 rewrites the `CONNECT` sweep in the
> same commit to hold two of the three keys enabled and vary the third, so each conjunct is the
> sole cause of a zero in exactly one case. Landing the fix and the test that can see it together
> mattered: DD59 alone would still have passed the old four-case sweep unchanged, on
> `xcp_program_max_api_enable` alone, the same way the defect did.
> `test_the_gate_touches_only_pgm_ctoinfo_rows` (test/pgm_configuration_test.py, Task 6)
> additionally confirms the generator fix changes exactly those eleven rows and nothing else in
> the generated source.

### SP5 — Protocol completion

The residue: the interleaved communication model (§1.7.2.3), `GET_ID` identification types 1–4 and
128–255 (§1.6.1.2.2), the remaining `EV_*` event codes and the `SERV_*` service request codes.

`EV_CMD_PENDING` was listed here and is **done** — SP4 shipped it for deferred programming
operations; see §2.6. Interleaved mode remains unbuilt, but is no longer advertisable: the
configuration that used to promise it has been removed rather than left as a flag an integrator
could set against an unimplemented receipt queue.

RESUME mode was listed here too and is now **done** — SP5-RESUME shipped it; see §2.6 and that
sub-project's own entry below.

`SET_DAQ_ID` was listed here and has been **removed from the roadmap rather than deferred within
it**. AUTOSAR SWS XCP R4.3.1 §4.1 puts it out of scope — "The SET_DAQ_ID command according to the
XCP CAN Transport Layer Specification is not part of the AUTOSAR XCP module" — and this module
tracks that SWS. Two things would have to be settled before revisiting it: its normative definition
lives in the XCP CAN Transport Layer specification, which is not in `docs/external`, and changing a
transmit identifier at runtime needs `CanIf_SetDynamicTxId` (SWS_CANIF_00189) plus an integrator
guarantee that every DAQ transmit PDU is a dynamic L-PDU. The slave answers `ERR_CMD_UNKNOWN`,
which §1.4 prescribes, and `GET_DAQ_ID` reports the identifier as fixed.

Note that time-out handling itself is *not* here: §1.7.2 places the t1…t6 timers entirely on
the master. `EV_CMD_PENDING` and the interleaved request queue are the slave's whole share
of that chapter.

#### SP5-NV — non-volatile DAQ storage — **complete**

Everything the module currently refuses because it keeps no non-volatile DAQ configuration:
`SET_REQUEST`'s `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` modes, the session configuration id that is
stored and cleared alongside them (§1.6.1.2.3), and the `GET_STATUS` byte pair that reports it. D9
closed the *misreporting* by refusing these modes outright; this item is what let them be accepted.

Design: `2026-09-09-xcp-daq-nv-storage-design.md` (DD94–DD102).

**Landed storage-only — not RESUME mode, which this entry originally bundled in as "what the whole
mechanism exists to serve."** DD102 split it back out while designing: RESUME needs an arming flag
SET_REQUEST does not yet report anywhere the integrator can read, and a running-list restore that
persisting a configuration does not by itself supply — **not a `CONNECT` handshake**, as this
sentence originally read here. SP5-RESUME's own design doc found that claim wrong while designing
the sub-project this row anticipated: every RESUME occurrence in both specification revisions was
read, and none is in `CONNECT`'s own section (`2026-09-10-xcp-daq-resume-design.md`, §0); corrected
here rather than carried forward silently. Building the restore mechanism unspecified alongside
storage was the wrong trade against shipping storage on its own first regardless of which words
described it. What this phase actually built: `STORE_DAQ_REQ`/`CLEAR_DAQ_REQ` accepted and polled
through the integrator's own `Xcp_StoreDaqConfiguration`/`Xcp_ClearDaqConfiguration`, each request
bit clearing on every exit including a failed one (DD94/DD95, and DD96 pinned the same rule
already implemented but untested for `STORE_CAL_REQ`); the session configuration id held and
reported at `GET_STATUS` bytes 4–5, provably `CONNECT`-proof (DD99); four read-only accessors an
integrator implementing the store queries to learn what to persist (DD94); and a polled start-up
read that adopts the id alone — no DAQ list — answering `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE`
from `GET_STATUS` while outstanding (DD100/DD101). `RESUME_SUPPORTED` stayed clear at the time this
phase shipped -- no longer true once SP5-RESUME (§4 below) reverses it alongside the `SET_REQUEST`
refusal in the same paragraph above, so read this sentence as this phase's own snapshot, not the
module's current behaviour.

**Intended shape** (agreed 2026-09-03, superseded by the design linked above): an integrator-
provided callback pair for storing and reading the configuration, **asynchronous**, following the
pattern already established by `Xcp_StoreCalibrationDataToNonVolatileMemory` — which
`Xcp_MainFunction` polls until it reports completion, then clears the request bit and raises
`EV_STORE_CAL`. The DAQ side needs the same treatment for `EV_STORE_DAQ` and `EV_CLEAR_DAQ`, plus
a read path at initialisation that calibration has no equivalent of. This held up: DD100 built
that read path polled rather than asynchronous in some other shape, for a reason worth keeping
alongside the original note — a synchronous call from `Xcp_Init` was the alternative actually
considered and rejected, since this module can neither verify nor enforce that the integrator's
own non-volatile memory abstraction has finished populating its RAM mirror by the time `Xcp_Init`
runs. The phrase "that RESUME depends on" is the one part superseded — read without restoring, as
the paragraph above explains.

Three things this had to get right, all of them discovered by D9:

- **A request bit that is never cleared is a denial of service, not a cosmetic flaw.** The
  `ERR_PGM_ACTIVE` gate in `Xcp_CanIfRxIndication` refuses the 42 commands that carry it while
  any of the three request bits is set. Confirmed done for all three bits, `STORE_CAL_REQ`
  included, by a dedicated denial-of-service test per bit (DD95's own acceptance bar).
- **Storing has an ordering requirement.** §1.6.1.2.3: the slave must first clear any DAQ list
  configuration already in non-volatile memory, then store the new one — so a store interrupted
  midway must not leave a configuration the master would take for complete. Answered by DD97: the
  session configuration id is committed last, so an interrupted store simply leaves none — an
  *integrator* obligation this module states but cannot itself test, since it never sees the
  integrator's own non-volatile memory.
- ~~`GET_DAQ_PROCESSOR_INFO` must stop reporting RESUME unsupported at the same time, and the
  refusals in `SET_REQUEST` and `SET_DAQ_LIST_MODE` must be lifted together with it.~~ **Did not
  happen, deliberately — see DD102 above.** This bullet assumed RESUME shipped alongside storage;
  once it did not, advertising `RESUME_SUPPORTED` while nothing restores a list would be the exact
  incoherence this bullet itself warned against, the other way round. `SET_REQUEST` accepting
  `STORE_DAQ_REQ`/`CLEAR_DAQ_REQ` is real and independent of RESUME: 1.0/§1.6.1.2.3 gates them on
  their own support, not on RESUME, so a slave may store without resuming.

**Dependencies, corrected.** This paragraph originally read RESUME and SP5-NV as two siblings both
depending on SP2 alone. With SP5-NV complete and RESUME still not built, that symmetry no longer
holds: RESUME now depends on SP5-NV as well, not only on SP2 — the persistence and the session
configuration id this phase built are exactly what RESUME needs something to resume *from*. Only
the interleaved model, `EV_CMD_PENDING`, `GET_ID` types and the `SERV_*` codes are genuinely
independent and can be pulled forward if one of them blocks an integration.

#### SP5-RESUME — starting DAQ from non-volatile memory — **complete**

What SP5-NV deliberately stopped short of, above: the slave now starts DAQ lists autonomously from
a non-volatile configuration with no master session at all, matching 1.1/1.6.4.1.2.6's own
description of what RESUME mode means — "the slave being in RESUME mode started the DAQ list
automatically."

Design: `2026-09-10-xcp-daq-resume-design.md` (DD103–DD107).

**This document's own SP5 entry was wrong about the mechanism, and the paragraph above corrects
it.** It described "`CONNECT`'s resume handshake"; there is no such thing, and `CONNECT` neither
gates nor resets a resumed list before this sub-project or after it (`test/daq_resume_test.py::
test_get_status_after_a_second_connect_still_reports_resume` asserts a resumed list keeps
transmitting through two `CONNECT`s, not only that it keeps reporting itself resumed). The actual
mechanism is three independent pieces. The master arms it ahead of a future power cycle, through
`SET_REQUEST`'s `STORE_DAQ_REQ_RESUME` (mode bit 2, now accepted under the same
`storeDaqConfigurationApiEnable` gate as the plain store mode next to it) — `Xcp_GetResumeArmedState`
reports which mode was requested to the integrator polling `Xcp_StoreDaqConfiguration` (DD104). The
integrator restores it at the *next* start-up, before any master connects, through `Xcp_Restore*`
(DD103, the mirror of SP5-NV's own four accessors) and commits it with `Xcp_ResumeComplete` (DD105)
— the single point where anything takes effect, so a restore that fails halfway resumes nothing
rather than a half-built configuration transmitting at a real event channel. And the slave reports
it: `GET_STATUS` bit 7, `GET_DAQ_LIST_MODE` bits 6–7, and `EV_RESUME_MODE`. `GET_DAQ_PROCESSOR_INFO`'s
`RESUME_SUPPORTED` (DAQ_PROPERTIES bit 2) is now set unconditionally, closing the coherence gap D9
and SP5-NV deliberately left open (SP5-NV's own "Did not happen, deliberately" bullet above).

`Xcp_DisconnectSession` frees dynamic DAQ lists on `DAQ_DYNAMIC` builds; DD106 exempts a resumed
list from that teardown — it came from non-volatile memory, not from the session that is ending —
while a session's own allocated lists are still freed as before. `FREE_DAQ` is not exempted: an
explicit free from a master frees everything, resumed lists included, and clears the resume state
so a fresh restoration can be accepted afterward.

Depended on SP5-NV, as the paragraph above anticipated once the two were split, and on SP2a for the
DAQ list infrastructure. Four tasks, each building on the last: the setters and the commit point
(DD103/DD105); the `DISCONNECT` exemption (DD106) and `FREE_DAQ`'s own resume-state clearing; the
wire reporting (`GET_STATUS`, `GET_DAQ_LIST_MODE`, `EV_RESUME_MODE`); and finally arming it from
`SET_REQUEST` and advertising `RESUME_SUPPORTED` — deliberately last, so no commit on the branch
ever advertised or accepted a capability the code behind it did not yet have.

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

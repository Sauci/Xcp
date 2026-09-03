# SP2b — Optional DAQ commands, the timestamp field, and PID_OFF

**Date:** 2026-09-02
**Baseline:** branch `develop`, commit `0db1114`
**Predecessor:** `2026-09-01-xcp-daq-design.md` (SP2a), whose design decisions DD1–DD16 bind here
unless this document overrides one explicitly. It overrides none.
**Roadmap:** `2026-08-29-xcp-part2-roadmap.md` §4, SP2b.

---

## 0. Which specification numbering this document uses

Citations are to **XCP Part 2 — Protocol Layer Specification 1.1** unless a citation names 1.0.
§0 of the SP2a design records that 1.0 and 1.1 renumber §1.6.4 wholesale and carries the mapping
table; that table applies here unchanged and is not repeated.

One practical note for implementers. The 1.1 PDF in `docs/external/` is a scan, and its OCR
transcription is unreliable in exactly the places this sub-project needs — the `TIMESTAMP_MODE` bit
mask and the `WRITE_DAQ_MULTIPLE` request table both come out garbled. The 1.0 PDF is text and
extracts cleanly. Every bit layout in this document was therefore read from the 1.0 PDF and
cross-checked against the 1.1 OCR for structural agreement. Where 1.1 adds something 1.0 lacks —
`WRITE_DAQ_MULTIPLE` is the only case here — the OCR was read directly and is flagged at the point
of use.

---

## 1. Scope

**In.**

- Five optional commands: `WRITE_DAQ_MULTIPLE` (0xC7), `READ_DAQ` (0xDB), `GET_DAQ_CLOCK` (0xDC),
  `GET_DAQ_LIST_INFO` (0xD8), `GET_DAQ_EVENT_INFO` (0xD7).
- The timestamp field of §1.1.2.2, switchable per DAQ list by the master.
- The `PID_OFF` flag of `SET_DAQ_LIST_MODE`.

**Out, and where it goes.**

- DAQ list prioritisation, more than one outstanding DTO frame, and `ALTERNATING` — **SP2c**. These
  change the confirmation-driven transmission chain that DD3 built and the `SchM` exclusive area
  guards. They are not additive the way the five commands are, and mixing them in would let a
  problem in the risky half block the safe half.
- Dynamic DAQ list configuration (`FREE_DAQ`, `ALLOC_DAQ`, `ALLOC_ODT`, `ALLOC_ODT_ENTRY`) —
  **SP2d**, renumbered from the roadmap's SP2c by the split above.
- STIM reception — **SP3**, unchanged.

**Non-goals.** No change to the transmission chain, the DTO ring, the exclusive area, or
`Xcp_TriggerEventChannel`'s signature. SP2b adds one field to a frame the sampler already builds and
five handlers to a dispatch table that already works.

---

## 2. What already exists

SP2a left the hook points for this work explicitly marked, and they are load-bearing here:

- `GET_DAQ_RESOLUTION_INFO` returns `TIMESTAMP_MODE = 0` and `TIMESTAMP_TICKS = 0` with a comment
  recording that these are *invalid* rather than zero-valued, because `TIMESTAMP_SUPPORTED` is
  clear. SP2b sets that bit and fills both fields.
- `SET_DAQ_LIST_MODE` rejects the unsupported mode bits through a single mask,
  `XCP_DAQ_LIST_MODE_REQ_UNSUPPORTED`. SP2b removes `TIMESTAMP` and `PID_OFF` from it.
- `Xcp_OdtUsedBytes(daqListNumber, odtNumber, excludedEntry)` exists, and `WRITE_DAQ` already
  enforces `Xcp_OdtUsedBytes(...) + size > odtEntrySizeDaq`. The timestamp capacity rule of §5 is a
  reduction of that budget, not new machinery.
- `Xcp_DaqListRt()` is the unchecked runtime accessor; every call site must gate on
  `Xcp_DaqListIsValid()` first. That contract is unchanged and binds the new handlers.
- The `SET_MTA` / `UPLOAD` path is implemented, so `GET_DAQ_EVENT_INFO` publishing a name via the
  MTA needs no new transfer machinery.
- `Xcp_CmdNotImplemented` answers `ERR_CMD_UNKNOWN` for every PID this sub-project fills in, so the
  before-and-after behaviour of each command is observable in tests.

---

## 3. Design decisions

**DD17 — The data acquisition clock is an integrator callback.** §1.1.2.2 requires "a free running
counter in the slave, which is never reset or modified and wraps around if an overflow occurs". The
module holds no clock (DD2) and nothing in its configuration can describe one. The clock is
therefore supplied by the integrator through

```c
uint32 Xcp_GetDaqTimestamp(void);
```

declared in a new `interface/Xcp_DaqTimestamp.h`, included from `Xcp.h` under
`#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)` — the pattern `Xcp_Paging.h` already follows, so an
integration without timestamps is never asked for a clock. The return type is `uint32` regardless of
the configured timestamp size, because `GET_DAQ_CLOCK` transmits a DWORD whatever the DTO field
width is; the DTO truncates to the configured size.

The rejected alternatives are recorded because each is defensible and one is nearly right. Passing
the timestamp into `Xcp_TriggerEventChannel` would give the most accurate DAQ timestamp — the
integrator knows when the event *occurred*, the module only knows when it was *told* — but it
changes an API shipped in SP2a and documented in the README, and forces a clock on integrations that
have timestamps switched off. Reading a counter through `Xcp_ReadSlaveMemory` at a configured
address adds no interface, but overloads a hook meant for calibration memory and gives no way to
express the counter's tick rate.

**DD18 — `GET_DAQ_CLOCK` captures the clock at reception, not when the response is built.**
§1.6.4.1.2.3 is unambiguous: the returned value "contains the current value of the data acquisition
clock, **when the `GET_DAQ_CLOCK` command packet has been received**", and "the accuracy of the time
synchronization between the master and the slave device is depending on the accuracy of this value".

**Corrected during implementation.** This decision was written on the belief that the module
receives in `Xcp_CanIfRxIndication` and assembles responses later in `Xcp_MainFunction`, so a late
read would fold the whole main-function latency into the master's clock offset. **That belief is
false.** `Xcp_PIDTable[pid](...)` is dispatched inside `Xcp_CanIfRxIndication` (`source/Xcp.c`), and
`Xcp_MainFunction` performs only the `STORE_CAL_REQ` service and `Xcp_StartNextTransmission()` — it
never indexes the PID table. Reception and response assembly happen in the same call.

What survives is the requirement itself: §1.6.4.1.2.3 asks for the clock value at reception, and the
module satisfies it because the handler *runs* at reception. What does not survive is the shape this
decision originally prescribed. Capturing into `Xcp_Internal` and reading the field in the handler
would be module-lifetime storage for a value written and read three lines apart, buying no accuracy,
adding a reentrancy failure mode a local cannot have — a nested `Xcp_CanIfRxIndication` between
capture and dispatch would clobber it — and costing RAM in builds where both ends are compiled out.

`Xcp_DTOCmdDaqGetDaqClock` therefore calls `Xcp_GetDaqTimestamp()` directly. No shared state, and no
exclusive area: the value never outlives its call.

The reentrancy question the original text raised is real but larger than this command. If
`Xcp_CanIfRxIndication` is genuinely re-entrant, it races `cto_response`, `last_pid` and
`Xcp_ClearProtectionStatus()` for **every** CTO, not just this one — see §8.

**DD19 — The timestamp is switchable per DAQ list; `TIMESTAMP_FIXED` is reported clear.** The
alternative — timestamps fixed on at build time — would have made the capacity question disappear by
folding the timestamp size into `MAX_ODT_ENTRY_SIZE_DAQ` at generation time. It was rejected in
favour of the specification's own model, in which the master sets the `TIMESTAMP` bit per list
through `SET_DAQ_LIST_MODE`. The cost is the capacity rule of §5, which is real but small because
the check it extends already exists.

**DD20 — `PID_OFF` is accepted only where identification can actually be recovered.** §1.1.2.1:
"Turning off the transmission of the Identification Field is only allowed if the Identification
Field Type is *absolute ODT number*. If the Identification Field is not transferred in the XCP
Packet, the unambiguous identification has to be done on the level of the Transport Layer. This can
be done e.g. on CAN with separate CAN-Ids for each DAQ list and only one ODT for each DAQ list."

The sentence names **two** transport-layer conditions, and both are checked at runtime.

*Corrected after review.* This design originally argued that only `maxOdt == 1` needed checking,
because "this module gives each DAQ list exactly one TX PDU (`dto[0].dto2PduMapping.txPdu.id`), so
the transport-layer half is satisfied by construction". That is false. *One* PDU per list is not a
*distinct* PDU per list: `config/xcp.schema.json` puts no `uniqueItems` on `pdu_mapping`, and
`config/xcp.json` maps **both** of its DAQ lists to `XCP_PDU_ID_TRANSMIT` — sharing one TX PDU is
this project's own shipped convention, not an exotic configuration. Under the original rule, two
single-ODT lists on that shared PDU would each have been granted `PID_OFF` and would each have
queued a frame with the same `txPduId` and no identification field: two DTOs on one CAN-Id with
nothing to say which list produced either, which is exactly what §1.1.2.1 forbids.

`SET_DAQ_LIST_MODE` therefore accepts `PID_OFF` only when the configured identification field type
is `ABSOLUTE`, that list's `maxOdt == 1`, **and** no other DAQ list names the same
`dto[0].dto2PduMapping.txPdu.id`; it answers `ERR_MODE_NOT_VALID` otherwise — the code §1.7.3.2.4
lists for the command, and an accurate description of a mode this slave cannot honour.

The distinctness check is a runtime loop over `daqCount` (`Xcp_DaqListTxPduIsExclusive`,
`source/Xcp_Daq.c`) rather than a generation-time guard or a schema `uniqueItems`, because
`pdu_mapping` is a **macro name**: `script/source_cfg.c.jinja2` emits it verbatim and the
preprocessor decides what number it resolves to, so two distinct names may still collide and only
the built configuration knows. A schema rule would also be the wrong shape — sharing a TX PDU is
legal and useful for every list that keeps its identification field; it is only `PID_OFF` that
cannot live with it.

`PID_OFF_SUPPORTED` in `DAQ_PROPERTIES` is set only when the configured identification type is
`ABSOLUTE`, since with any other type no list could ever accept the bit. It is deliberately *not*
narrowed further by the PDU-sharing rule: `DAQ_PROPERTIES` is a property of the slave, not of a
list, and a configuration where some lists have an exclusive PDU and others do not has no single
honest answer to give there.

**DD21 — `WRITE_DAQ_MULTIPLE` and `WRITE_DAQ` share one entry-application helper.** §1.6.4.1.2.1:
"In general `WRITE_DAQ_MULTIPLE` has the same restrictions as the `WRITE_DAQ` command." Restating
those restrictions in a second handler would make that sentence true on the day it was written and
progressively less true afterwards. The per-entry logic — granularity, size bound, ODT capacity,
pointer validity, pointer advance — moves out of `Xcp_DTOCmdDaqWriteDaq` into a file-local helper
that both handlers call in a loop. The shared restriction then holds by construction, and §10 tests
it as such.

**DD22 — A failed `WRITE_DAQ_MULTIPLE` does not roll back.** §1.6.4.1.2.1: "The error handling is
identical to the one for `WRITE_DAQ`. However, it is not possible to detect which entry caused the
error. In that case the whole configuration is invalid." Entries are applied as the loop walks them;
the first failure returns its error and invalidates the DAQ pointer, exactly as `WRITE_DAQ` does
today. Atomicity would cost a validation pre-pass and buy nothing, because the specification has
already told the master its configuration is void.

**DD23 — `EVENT_FIXED` is reported clear, and `FIXED_EVENT` is therefore don't-care.**
`Xcp_TriggerEventChannel` scans for the binding `SET_DAQ_LIST_MODE` wrote at runtime
(`Xcp_Rt[...].daqList[...].eventChannelNumber`), not the configured `triggeredDaqListRef` — SP2a
recorded this in the function's own comment. The master can therefore move a list between channels,
which is precisely what `EVENT_FIXED = 0` means. The configured `triggered_daq_list_ref` keeps its
generation-time role and gains a runtime one: it is the source of `MAX_DAQ_LIST` in
`GET_DAQ_EVENT_INFO`.

**DD24 — `GET_DAQ_LIST_INFO` publishes no name, because the specification defines none for it.**
An earlier draft of this design assumed both info commands carried a name. They do not: in 1.0 and
1.1 alike, `NAME_LENGTH` appears for `EVENT_CHANNEL` and for `SECTOR` (a PGM command, out of scope),
and `GET_DAQ_LIST_INFO` returns only `DAQ_LIST_PROPERTIES`, `MAX_ODT`, `MAX_ODT_ENTRIES` and
`FIXED_EVENT`. Consequently `daqs[].name` stays generation-time only and no DAQ list strings are
emitted. Only `events[].name` is new.

---

## 4. Source layout

No new translation unit. SP2a's six-file split holds.

| File | Change |
|:--|:--|
| `interface/Xcp_DaqTimestamp.h` | **new** — declares `Xcp_GetDaqTimestamp` |
| `interface/Xcp.h` | includes the above under `XCP_DAQ_TIMESTAMP_SUPPORTED`; new API id for the RX-side capture is not needed |
| `interface/Xcp_Types.h` | `namePtr`/`nameLength` on the event channel type. The timestamp fields are **already there** — see §5.4 |
| `source/Xcp_Daq.c` | five new handlers; `WRITE_DAQ`'s per-entry logic extracted to a shared helper; `SET_DAQ_LIST_MODE` gains the `TIMESTAMP` and `PID_OFF` paths |
| `source/Xcp_DaqRuntime.c` | the timestamp field in the first ODT of a cycle; `PID_OFF` suppressing the identification field |
| `source/Xcp.c` | `Xcp_CanIfRxIndication` captures the clock for PID 0xDC; PID table entries |
| `script/*.jinja2`, `config/xcp.schema.json` | §9 |

---

## 5. The timestamp field

### 5.1 Placement

§1.1.2.2 puts the timestamp directly after the identification field:
`PID [FILL] [DAQ] TIMESTAMP DATA`. With `PID_OFF` there is no identification field and the timestamp
begins at offset 0.

Diagram 10 is explicit that it appears in **the first ODT of a DAQ cycle only**, not in every ODT.
Concretely: one call to `Xcp_GetDaqTimestamp()` per running timestamped list per trigger, its value
written into that cycle's ODT 0 frame, with the remaining ODTs unchanged.

Multi-byte values use the existing `Xcp_CopyFromU16WithOrder` / `Xcp_CopyFromU32WithOrder` helpers,
so the field honours the configured byte order like every other multi-byte field in the module.

### 5.2 Capacity

`GET_DAQ_RESOLUTION_INFO` continues to report `MAX_ODT_ENTRY_SIZE_DAQ` as
`MAX_DTO − identification field size` — one static value, unchanged, because it is a property of the
build and not of a list's mode.

The timestamp instead reduces the **budget of ODT 0** on a list in timestamped mode, from
`odtEntrySizeDaq` to `odtEntrySizeDaq − timestamp size`. The master chooses the order in which it
configures a list, so both orders are enforced:

| Order | Check | Error |
|:--|:--|:--|
| `WRITE_DAQ` into ODT 0 of a list already timestamped | the existing `Xcp_OdtUsedBytes + size > budget` test, with the reduced budget | `ERR_DAQ_CONFIG` |
| `SET_DAQ_LIST_MODE` enabling `TIMESTAMP` | `Xcp_OdtUsedBytes(list, 0, none) > reduced budget` | `ERR_OUT_OF_RANGE` |

*Corrected in the SP2b hygiene pass.* This row previously said `ERR_OUT_OF_RANGE`. The check
`WRITE_DAQ` shares with every other overfill (DD8, `Xcp_DaqApplyOdtEntry` in `source/Xcp_Daq.c`) has
always answered `ERR_DAQ_CONFIG`; the timestamp-reduced budget is a smaller threshold for the same
comparison, not a different one, so it inherits the same error rather than introducing
`ERR_OUT_OF_RANGE` alongside it. §1.7.3.2.4 lists `ERR_DAQ_CONFIG` for `WRITE_DAQ`, and
`write_daq_test.py`'s `test_write_daq_respects_the_budget_the_timestamp_leaves_in_odt_zero` pins it
for exactly this reduced-budget case.

`ERR_OUT_OF_RANGE` is listed for `SET_DAQ_LIST_MODE` in §1.7.3.2.4, and its prescribed master action
— "retry other parameter" — is exactly the recovery available: drop an entry, or leave the timestamp
off.

### 5.3 Reported properties

`TIMESTAMP_SUPPORTED` (`DAQ_PROPERTIES` bit 4, `GET_DAQ_PROCESSOR_INFO`) is set when `timestamp` is
configured. `GET_DAQ_RESOLUTION_INFO` then fills the two fields SP2a left invalid:

`TIMESTAMP_MODE` is a bit mask — **bits 2:0 size**, **bit 3 `TIMESTAMP_FIXED`**, **bits 7:4 unit** —
read from the 1.0 PDF and structurally confirmed against the 1.1 OCR:

| Size bits 2:0 | Meaning | | Unit bits 7:4 | Meaning |
|:--|:--|:--|:--|:--|
| 0 | no timestamp | | 0 | `DAQ_TIMESTAMP_UNIT_1NS` |
| 1 | 1 byte | | 1 | `_10NS` |
| 2 | 2 bytes | | 2 | `_100NS` |
| 3 | **not allowed** | | 3 | `_1US` |
| 4 | 4 bytes | | 4…9 | `_10US`, `_100US`, `_1MS`, `_10MS`, `_100MS`, `_1S` |

`TIMESTAMP_FIXED` is reported **clear** (DD19). `TIMESTAMP_TICKS` is the configured WORD. Size 3 is
not representable in the configuration, which offers `BYTE`, `WORD` and `DWORD` only.

### 5.4 What already exists, and one trap

`Xcp_Types.h` already declares `Xcp_TimestampTypeType` and `Xcp_TimestampUnitType`, and
`Xcp_GeneralType` already carries `timestampTicks`, `timestampType` and `timestampUnit`. All three
are emitted by `script/source_cfg.c.jinja2` as **hard-coded** values — `0x0001u`, `FOUR_BYTE` and
`TIMESTAMP_UNIT_1MS` — each labelled `hard-coded` in its own comment. SP2b does not add these
fields; it replaces those three literals with configured values, and adds `NO_TIME_STAMP` as the
value when `timestamp` is absent. That is materially less work than adding them.

**The trap.** `Xcp_TimestampTypeType`'s enumerators are implicit, so `FOUR_BYTE == 3`. The wire
encoding of the `TIMESTAMP_MODE` size field is *not* the same: 0, 1, 2, **4**, with 3 explicitly
"Not allowed". Writing `timestampType` straight into the size bits therefore emits the one value
the specification forbids. `GET_DAQ_RESOLUTION_INFO` must map the enumerator to the wire value, and
§10 tests each size against its encoded byte rather than against the enumerator.

`Xcp_EventChannelType` already carries `consistency`, `priority`, `timeCycle`, `timeUnit`, `type`
and `triggeredDaqListRefCount`, all emitted from the configuration — so `GET_DAQ_EVENT_INFO` needs
no new runtime fields beyond the name.

---

## 6. Configuration model

### 6.1 New `protocol_layer` keys

| Key | Type | Default | Meaning |
|:--|:--|:--|:--|
| `timestamp` | object, optional | absent | `{"size": "BYTE"\|"WORD"\|"DWORD", "unit": "TIMESTAMP_UNIT_*", "ticks": <1..65535>}`. Absent means unsupported: `TIMESTAMP_SUPPORTED` stays clear and `GET_DAQ_RESOLUTION_INFO` keeps returning the invalid zeros it returns today |
| `publish_names` | boolean | `true` | when false, no name strings are emitted and `GET_DAQ_EVENT_INFO` reports `EVENT_CHANNEL_NAME_LENGTH = 0`, which §1.6.4.1.2.7 defines as "if not available" |

`unit` and `ticks` describe the integrator's counter. The module neither controls nor validates them
against reality; it reports them so the master can convert ticks to time.

### 6.2 New `events` key

| Key | Type | Meaning |
|:--|:--|:--|
| `name` | string | the event channel name, ASCII, no NUL terminator on the wire (§1.6.4.1.2.7). Required when `publish_names` is true |

### 6.3 Generation-time validation

- `WRITE_DAQ_MULTIPLE` enabled with `max_cto < 10` fails generation. §1.6.4.1.2.1: "If the optional
  command `WRITE_DAQ_MULTIPLE` is used, the requirement `MAX_CTO >= 10` has to be fulfilled."
- `timestamp.size` of `DWORD` with a `max_dto` that leaves no room for data after the identification
  field and the timestamp fails generation, mirroring SP2a's existing `MAX_DTO` guard.
- `publish_names` true with an event channel lacking `name` fails generation.

Guard messages follow the existing convention and its limitation: `raise` is not a registered Jinja
global, so the message documents the guard for whoever reads the template while the caller sees
`'raise' is undefined`. `script/source_cfg.c.jinja2` records why.

---

## 7. Command specifications

### 7.1 WRITE_DAQ_MULTIPLE — 0xC7 (§1.6.4.1.2.1, 1.1 only)

Request: `2 + n*8` bytes. Byte 1 is `n`; each element is `BIT_OFFSET`, size, address DWORD, address
extension, and a **mandatory** alignment dummy — including after the last element.

Beyond `WRITE_DAQ`'s restrictions, inherited via the shared helper (DD21): all entries must land in
one ODT, and the command must not write over an ODT border. A request whose `n` would cross the
ODT's entry count answers `ERR_OUT_OF_RANGE`, from the shared helper's own pointer-validity check
(the same one a second `WRITE_DAQ` past the border trips). A request whose length disagrees with `n`
answers `ERR_CMD_SYNTAX`, checked before any entry is applied. Partial application stands on error
(DD22).

*Corrected in the SP2b hygiene pass.* This paragraph previously prescribed `ERR_OUT_OF_RANGE` for
both. `Xcp_DTOCmdDaqWriteDaqMultiple` (`source/Xcp_Daq.c`) checks the request's `SduLength` against
`2 + n*8` before entering the per-entry loop and answers `ERR_CMD_SYNTAX` on a mismatch; only the
ODT-border case reaches the shared helper and its `ERR_OUT_OF_RANGE`. Defensible either way — 1.1
does not itself say which applies to a malformed `WRITE_DAQ_MULTIPLE` request — so the document is
corrected to match the shipped behaviour rather than the reverse.

Read from the 1.1 OCR, which is degraded here; the implementation must confirm the element stride
of 8 bytes and the trailing dummy against the PDF page images.

### 7.2 READ_DAQ — 0xDB (§1.6.4.1.2.2)

Response: `0xFF`, `BIT_OFFSET`, size, address extension, address DWORD. Reads the entry at the DAQ
pointer with the same auto-post-increment within an ODT that `WRITE_DAQ` uses. An invalid pointer
answers `ERR_OUT_OF_RANGE`.

*Corrected after review.* This section originally called that "consistent with DD10". It is not
consistent with §1.7.3.2.4, which is what DD10 is about: that section's `READ_DAQ` row does **not**
list `ERR_OUT_OF_RANGE`. Its rows are the t1 timeout, `ERR_CMD_BUSY`, `ERR_PGM_ACTIVE`,
`ERR_CMD_UNKNOWN` and `ERR_CMD_SYNTAX` — verified against the 1.0 PDF. Every *other* command SP2b
touches does list `ERR_OUT_OF_RANGE`, which is why the choice looked unremarkable.

The code stands as a **deliberate deviation**. The only listed alternative is `ERR_CMD_SYNTAX`,
whose prescribed master action in §1.7.3.2.4 is "retry other syntax" — actively wrong advice for a
DAQ pointer left undefined past the last entry of an ODT (§1.6.4.1.1.2), a state no change of
syntax can fix. `ERR_OUT_OF_RANGE`'s prescribed action is "retry other parameter", which is exactly
the recovery available: reposition with `SET_DAQ_PTR`. Answering a code that sends the master down
a road with no destination is a worse failure than answering one the table omits, so the code is
kept and the deviation recorded here.

### 7.3 GET_DAQ_CLOCK — 0xDC (§1.6.4.1.2.3)

Response: `0xFF`, one reserved BYTE, one reserved WORD, then the DWORD captured at reception
(DD18). The three reserved bytes are zero-filled; being zero, their byte order is immaterial.

### 7.4 GET_DAQ_LIST_INFO — 0xD8 (§1.6.4.2.2.1)

Request carries a reserved byte and `DAQ_LIST_NUMBER`. Response: `0xFF`,
`DAQ_LIST_PROPERTIES`, `MAX_ODT`, `MAX_ODT_ENTRIES`, `FIXED_EVENT` WORD. An unavailable list answers
`ERR_OUT_OF_RANGE`, as the section states outright.

`DAQ_LIST_PROPERTIES`: `PREDEFINED` (bit 0) clear, because the master writes entries;
`EVENT_FIXED` (bit 1) clear (DD23), making `FIXED_EVENT` don't-care and zero-filled; `DAQ` (bit 2)
set from the configured list type; `STIM` (bit 3) clear until SP3.

### 7.5 GET_DAQ_EVENT_INFO — 0xD7 (§1.6.4.1.2.7)

Request carries a reserved byte and the event channel number; out of range answers
`ERR_OUT_OF_RANGE`. Response: `0xFF`, `DAQ_EVENT_PROPERTIES`, `MAX_DAQ_LIST`,
`EVENT_CHANNEL_NAME_LENGTH`, `EVENT_CHANNEL_TIME_CYCLE`, `EVENT_CHANNEL_TIME_UNIT`,
`EVENT_CHANNEL_PRIORITY`.

Every field is already configured — SP2a's DD2 anticipated this, recording that `time_cycle` and
`time_unit` "describe a raster the slave *promises*, reported to the master through
`GET_DAQ_EVENT_INFO` in SP2b". `MAX_DAQ_LIST` is the length of that channel's
`triggered_daq_list_ref` (DD23). The command sets the MTA to the channel's name so the master can
`UPLOAD` it; with `publish_names` false the length is 0 and the MTA is left untouched.

`DAQ_EVENT_PROPERTIES` carries the `DAQ`/`STIM` type bits from the configured channel type and the
consistency bits from `events[].consistency`. `STIM` stays clear until SP3.

### 7.6 SET_DAQ_LIST_MODE — 0xE0, extended (§1.6.4.1.1.3)

`TIMESTAMP` and `PID_OFF` leave `XCP_DAQ_LIST_MODE_REQ_UNSUPPORTED`. `DIRECTION` and `ALTERNATING`
remain in it and keep answering `ERR_MODE_NOT_VALID` (DD9).

- `TIMESTAMP` requires `timestamp` to be configured — otherwise `ERR_MODE_NOT_VALID` — and passes the
  §5.2 capacity check, otherwise `ERR_OUT_OF_RANGE`.
- `PID_OFF` requires `ABSOLUTE` identification, `maxOdt == 1`, and a TX PDU no other DAQ list
  shares, otherwise `ERR_MODE_NOT_VALID` (DD20).

---

## 8. Risks

**~~The clock capture rides an assumed serialisation.~~ Resolved, and it found a larger
question.** The trace this risk demanded was run, and it disproved the premise rather than
confirming it — see DD18. There is no capture and no shared field, so nothing rides any
serialisation.

The trace did surface something wider. `Xcp_CanIfRxIndication` checks the CTO busy flag, dispatches,
and only then sets the flag. If that function can preempt itself — the module's headers do not say
either way — then `cto_response`, `last_pid` and `Xcp_ClearProtectionStatus()` are all raced, for
every one of the 256 PID entries, not merely for `GET_DAQ_CLOCK`. A lock scoped to one command's
data would close nothing. Closing it properly means an exclusive area around the whole
busy-check/dispatch/set-flag sequence, which changes behaviour for every command and needs its own
design and regression surface. **Out of scope for SP2b, and recorded here as the question SP2b
found rather than one it created.**

**The acceptance test's cross product.** §10 adds a timestamp dimension to a parametrisation that
already produces a large share of 12455 tests at 3m30s. Sweeping it fully against every existing
axis would multiply that fourfold. The mitigation is in §10 and is a deliberate coverage trade, not
an oversight.

**`WRITE_DAQ_MULTIPLE` rests on degraded OCR.** Its request layout exists only in 1.1, whose
transcription is poor. §7.1 flags the two values to confirm against the page images.

---

## 9. Generator and schema changes

- `config/xcp.schema.json`: `protocol_layer.timestamp` object with `size`, `unit`, `ticks`;
  `protocol_layer.publish_names` boolean; `events[].name` string. `timestamp` and `publish_names`
  are optional, so existing configurations stay valid — and `test/configuration_schema_test.py`
  now enforces that, since it validates the harness's own configurations against the schema.
- `script/header_cfg.h.jinja2`: `XCP_DAQ_TIMESTAMP_SUPPORTED`, and the timestamp size as a macro so
  the DTO frame layout can be reasoned about at compile time.
- `script/source_cfg.c.jinja2`: replace the three hard-coded timestamp values (§5.4) with the
  configured ones; the name strings and their lengths into the event channel array; the three §6.3
  guards.

---

## 10. Test strategy

**The DTO layout is tested where it is already tested.** `daq_acceptance_test.py`'s
`test_every_dto_byte_lands_where_the_specification_puts_it` sweeps MAX_DTO × byte order ×
identification type × address granularity and asserts every byte's position. The timestamp is one
more field in that layout and belongs as one more dimension of that test, not as a parallel test
that can drift from it.

To keep the suite runnable, the timestamp size is swept **fully against a representative slice** of
the existing axes rather than against the full cross product, and the test's docstring must say so
and say why. The alternative is a suite nobody runs locally.

**Per feature, beyond the layout sweep:**

| Feature | Test |
|:--|:--|
| `GET_DAQ_CLOCK` capture timing | the mock clock returns a different value on each call; the response must carry the value from the *reception* call. Without this, DD18's bug and correct behaviour are indistinguishable |
| Timestamp capacity | both orders — `WRITE_DAQ` then enable `TIMESTAMP`, and enable then write — must reject the overflowing case |
| Timestamp placement | present in ODT 0 of a cycle, absent from ODT 1..n; absent entirely with the mode off |
| `READ_DAQ` | round trip against `WRITE_DAQ`: write entries, read them back, assert equality |
| `WRITE_DAQ_MULTIPLE` | a table of bad inputs asserted to be rejected **identically** by it and by `WRITE_DAQ` — the test that keeps DD21's shared helper honest. Plus ODT-border rejection and the `n`/length disagreement |
| `GET_DAQ_LIST_INFO`, `GET_DAQ_EVENT_INFO` | fields match the configuration; out-of-range answers `ERR_OUT_OF_RANGE` |
| Names | MTA + `UPLOAD` round trip returns the configured name; `publish_names: false` reports length 0 and leaves the MTA alone |
| `PID_OFF` | accepted with `ABSOLUTE` + `maxOdt == 1`; rejected for every other combination; the resulting DTO carries no identification field; combined with a timestamp, the timestamp starts at offset 0 |
| Regression | each of the five PIDs answered `ERR_CMD_UNKNOWN` before this sub-project, so a test that the command now answers is a real before/after |

`Xcp_GetDaqTimestamp` needs no harness change: it is declared in a header `Xcp.h` includes, so
conftest's `code.mocked` mechanism registers it automatically, and it runs under the
`_callback_invariants` guard, so an assertion inside that mock can fail its test rather than being
swallowed at the C boundary.

---

## 11. Acceptance

- All five commands answer per §7, and each is shown to have answered `ERR_CMD_UNKNOWN` before.
- A timestamped DAQ list transmits the clock in the first ODT of each cycle, in the configured size,
  unit and byte order, and does not transmit it in later ODTs.
- `GET_DAQ_CLOCK` returns the value the clock held at reception.
- The capacity rule rejects an overflowing first ODT in both configuration orders.
- `PID_OFF` is accepted exactly where DD20 permits it and refused everywhere else.
- `GET_DAQ_RESOLUTION_INFO` reports a valid `TIMESTAMP_MODE` and `TIMESTAMP_TICKS`, with
  `TIMESTAMP_FIXED` clear; `GET_DAQ_PROCESSOR_INFO` reports `TIMESTAMP_SUPPORTED` and
  `PID_OFF_SUPPORTED` per §5.3 and DD20.
- Configurations without `timestamp` or `publish_names` remain valid and behave as they do today.
- The suite is green and the DAQ sources keep the coverage they have.

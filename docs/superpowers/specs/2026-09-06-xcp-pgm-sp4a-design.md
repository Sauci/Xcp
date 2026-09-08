# SP4a — Programming session and deferred responses (PGM)

**Status:** design approved 2026-09-06.

**Predecessors:** SP1 for the block-transfer idiom and the store-calibration callback whose
contract this sub-project copies; SP2b for the exclusive-area discipline. Independent of SP2 and
SP3 otherwise.

**Successors:** SP4b (`PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX`, `PROGRAM_NEXT`,
`GET_PGM_PROCESSOR_INFO`) and SP4c (`GET_SECTOR_INFO`, `PROGRAM_FORMAT`, `PROGRAM_VERIFY`)
consume the machinery defined here. All eleven PGM commands are the goal; this document is the
first third of it.

---

## 0. Which specification numbering this document uses

Citations are to **XCP Part 2 — Protocol Layer Specification 1.1** unless a citation names 1.0,
matching SP2a through SP3. §0 of the SP2a design carries the §1.6.4 renumbering table.

**§1.6.5 keeps its numbering in both revisions**, down to the fourth level: §1.6.5.1.1
(`PROGRAM_START`) through §1.6.5.1.4 (`PROGRAM_RESET`), and §1.6.5.2.1 through §1.6.5.2.7 for the
optional seven. No mapping is needed anywhere in this document.

Two working notes on sources:

- The 1.1 PDF's text layer is obfuscated; `docs/external/XCP -Part 2- Protocol Layer Specification
  -1.1.ocr.txt` is the usable form, and it garbles tables. Every table-shaped claim below was
  checked against the 1.0 PDF via `pdftotext -layout`, which extracts cleanly.
- 1.1 adds a paragraph to §1.6.5.1.3 describing master block mode for `PROGRAM` and stating that
  `MAX_BS_PGM` and `MIN_ST_PGM`, as reported by `PROGRAM_START`, are what bound it. 1.0 has no
  such paragraph. This matters to DD56 and is called out there.

**AUTOSAR.** SWS XCP R4.3.1 is the second authority this module tracks. Unlike `SET_DAQ_ID`, which
§4.1 puts out of scope outright, PGM is explicitly **in** scope: SRS_Xcp_29020 maps to
SWS_Xcp_00855 ("shall support the flash programming (PGM)") and SWS_Xcp_00856. Where the two
authorities disagree, this document says which one it follows and why (DD50).

---

## 1. Scope

**In:**

- `PROGRAM_START` (0xD2), `PROGRAM_RESET` (0xCF), `PROGRAM_PREPARE` (0xCC).
- The programming-session state machine, including the gate that refuses clear/program commands
  before `PROGRAM_START` — a gate whose users arrive in SP4b.
- The deferred-response mechanism: a pending-command slot, polled integrator callbacks, and
  `EV_CMD_PENDING`.
- `XCP_FLASH_PROGRAMMING_ENABLED`, the compile gate generated from `XcpFlashProgrammingEnabled`
  (ECUC_Xcp_00181).
- Defects **D10** and **D11** (§2.2).

**Out:**

- Every command that touches flash contents: `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX`,
  `PROGRAM_NEXT` (SP4b).
- `GET_PGM_PROCESSOR_INFO` (SP4b — see DD61 for why it cannot live here).
- `GET_SECTOR_INFO` and the flash sector configuration model, `PROGRAM_FORMAT` with functional
  access mode and the block sequence counter, `PROGRAM_VERIFY` (SP4c).
- Interleaved mode, and the general `EV_CMD_PENDING` availability for non-PGM commands (SP5). This
  sub-project raises the event only for the commands it defers.

---

## 2. What already exists

### 2.1 Present and reusable

- **The protection table.** `Xcp_PIDToCmdGroupTable` already assigns
  `XCP_RESOURCE_PROTECTION_STATUS_MASK_PGM` to all eleven PGM PIDs (`source/Xcp.c`), and
  `GET_SEED`/`UNLOCK` already accept the PGM resource (`source/Xcp_Std.c`). Nothing to add.
- **The `ERR_PGM_ACTIVE` gate.** `Xcp_CanIfRxIndication` already refuses 42 commands when any of
  `STORE_CAL_REQ`, `STORE_DAQ_REQ` or `CLEAR_DAQ_REQ` is set. The mechanism is built and tested; it
  has never had a programming session to trigger it. DD51 gives it one.
- **Withholding a response.** `*responseExpected = FALSE` already suppresses transmission
  (`source/Xcp.c`, where `response_expected` becomes
  `cto_response.successful_transmission_pending`). `Xcp_DTOCmdCalDownload` uses it mid-block-
  transfer. DD53 reuses it unchanged.
- **Publishing from `Xcp_MainFunction`.** The `STORE_CAL_REQ` path already has `Xcp_MainFunction`
  poll an integrator callback, and on completion push a packet and set a
  `successful_transmission_pending` flag. DD52–DD54 follow that shape.
- **The polled NV callback contract.** `Xcp_StoreCalibrationDataToNonVolatileMemory(uint8
  *pStatusCode)` returns `E_NOT_OK` while unfinished and `E_OK` when the sequence has ended,
  successfully or not, with the outcome in `pStatusCode`. §4 copies it exactly.
- **Every error code needed.** `interface/Xcp_Errors.h` already defines `XCP_E_ASAM_GENERIC`
  (0x31), `XCP_E_ASAM_SEQUENCE` (0x29), `XCP_E_ASAM_CMD_BUSY` (0x10) and `XCP_E_ASAM_PGM_ACTIVE`
  (0x12).

### 2.2 Two defects this sub-project closes

**D10 — `CONNECT` advertises a command group that answers `ERR_CMD_UNKNOWN`.**

With the shipped `config/xcp.json`, `CONNECT` returns resource byte `0x15` — CAL_PAG | DAQ | **PGM**
— so every master is told "Flash programming available" (§1.6.1.1.1). All eleven PGM PIDs dispatch
to `Xcp_CmdNotImplemented` and answer `0xFE 0x20`. Demonstrated, not inferred: a probe of
`PROGRAM_START`, `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_RESET`, `GET_PGM_PROCESSOR_INFO` and
`PROGRAM_MAX` against a default handle returned `ERR_CMD_UNKNOWN` for all six while the same
handle's `CONNECT` set bit 4.

This is the same class as SP3's Finding 2, which DD48 answered by refusing the configuration
outright. Here the answer is DD58 instead: the feature gets a compile gate that defaults off, so
the default configuration stops making the claim.

**D11 — two of the three PGM API configuration keys are dead.**

`script/source_cfg.c.jinja2` templates the `ctoInfo` enable bit on a configuration key for every
command except the PGM block, where `PROGRAM_VERIFY` through `PROGRAM_START` are emitted with a
hard-coded `0x01u`. Only `xcp_program_max_api_enable` (PID 0xC9) is templated.
`xcp_program_api_enable` and `xcp_program_clear_api_enable` exist in `config/xcp.schema.json` and
in `config/xcp.json`, are accepted by the generator, and change nothing.

`Xcp_CTOCmdStdConnect` tests all three, so its three-term conjunction is in practice one term.
Measured, by sweeping the three keys and reading `CONNECT`'s resource byte:

| `..clear..` | `..program..` | `..max..` | PGM advertised |
|---|---|---|---|
| true | true | true | **true** |
| **false** | **false** | true | **true** |
| true | true | false | false |
| false | true | true | **true** |
| true | false | true | **true** |

`test_connect_sets_the_resource_pgm_bit_according_to_enabled_apis` sweeps
`(false,false,false) → 0`, `(true,false,false) → 0`, `(true,true,false) → 0`, `(true,true,true) → 1`
and passes all four — every zero carried by `xcp_program_max_api_enable` alone. The test would pass
unchanged if the other two keys were deleted from the schema. DD59 fixes the generator and DD60
fixes the test, in the same commit, because after DD59 those same four cases would *still* pass.

### 2.3 Absent

All eleven handlers, every flash callback, any programming-mode state, and `EV_CMD_PENDING`
(`XCP_EVENT_STORE_CAL` 0x03 and `XCP_EVENT_DAQ_OVERLOAD` 0x06 are the only event codes defined).

---

## 3. Design decisions

### DD49 — One programming-session state, two values

`Xcp_Internal.pgm_state` takes `XCP_PGM_IDLE` and `XCP_PGM_ACTIVE`.

**This decision specified three, and the third was dead.** `XCP_PGM_STARTING` was to be entered
while a `PROGRAM_START` was being polled, on the reasoning below that `Xcp_MainFunction` needs to
know which state a finished `PROGRAM_START` came from. It does not: the completion decides from the
integrator's status code alone and never reads `pgm_state`, and the other two readers cannot
distinguish `STARTING` from `IDLE`. Replacing it with `XCP_PGM_IDLE` changed no behaviour and no
test, which is how the final review found it. It is deleted.

§1.6.5.1.1 requires that `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX` and `PROGRAM_NEXT` "are not
allowed, until the PROGRAM_START command has been successfully executed". The gate is implemented
here, in SP4a, even though every command it gates arrives in SP4b. That is deliberate: the gate is
what `PROGRAM_START` *means*, and a `PROGRAM_START` that sets a flag nothing reads is not
testable as the thing the specification describes. SP4b's handlers consult it on arrival.

Refusal of the gated commands is `ERR_SEQUENCE` (0x29), which **§1.7.3.2.5** — the PGM matrix;
§1.7.3.2.4 is DAQ's, and an earlier revision of this document cited it throughout — lists for
`PROGRAM_CLEAR`, `PROGRAM` and `PROGRAM_MAX`.

**A second `PROGRAM_START` inside an open session is answered `ERR_GENERIC` (0x31), not
`ERR_SEQUENCE`.** This decision originally said `ERR_SEQUENCE` for that case too, by carrying the
gated commands' error over to the gating command. `PROGRAM_START`'s own row in §1.7.3.2.5 lists
`CMD_BUSY`, `DAQ_ACTIVE`, `CMD_SYNTAX`, `ACCESS_LOCKED` and `GENERIC` — no `SEQUENCE` — and
`Xcp_CTOErrorMatrix[0xD2]` agrees. §1.6.5.1.1 names `ERR_GENERIC` for a slave "not in a state which
permits programming", which is exactly what an open session is.

### DD50 — `PROGRAM_RESET` disconnects without resetting the device

ASAM §1.6.5.1.4: the slave "will go to the disconnected state. Usually a hardware reset of the
slave device is executed." AUTOSAR SWS_Xcp_00856: "Indication the end of a programming sequence is
supported using the optional command `PROGRAM_RESET`, where the slave will go to disconnected
state **but without forcing a device reset**."

**This module follows AUTOSAR.** The two are compatible in the part that matters — both disconnect
— and ASAM's reset is "usually", a description of common practice rather than a requirement. The
deciding argument is ownership: this module is one BSW component among many on an ECU it does not
own, and resetting the device on receipt of a CTO is not its call to make. An integrator that wants
a reset performs one from its own `Xcp_ProgramReset` implementation, which is the right place for
it because that code knows what else is running.

**Declining the reset makes clearing `pgm_state` the module's own responsibility, and this decision
originally left that to one door.** ASAM's model has the hardware reset dispose of the session, so
a slave that follows it needs no other exit. Having refused that, only `PROGRAM_RESET`'s completion
cleared the state — and `DISCONNECT` is itself refused `ERR_PGM_ACTIVE` while a session is open,
while `CONNECT` was accepted and cleared nothing. Measured: `PROGRAM_START` → `DISCONNECT`
(`ERR_PGM_ACTIVE`) → `CONNECT` (accepted) → `DOWNLOAD` (`ERR_PGM_ACTIVE`). A master that died
mid-sequence left the next one with some thirty-eight commands refused for good, and two further
routes reached the same place: a build with `PROGRAM_RESET` disabled, and an `Xcp_ProgramReset`
that reports failure.

`Xcp_CTOCmdStdConnect` therefore resets `pgm_state`. `CONNECT` is the right door because it is the
one command that is never refused — XCP Part 1 §2.3, quoted at `source/Xcp.c:1583-1589` — and
because `DISCONNECT` cannot be it while a session is open.

### DD51 — `ACTIVE` triggers the existing `ERR_PGM_ACTIVE` gate

Entering `XCP_PGM_ACTIVE` makes `Xcp_CanIfRxIndication`'s existing `ERR_PGM_ACTIVE` condition true,
so the 42 commands that carry `XCP_INTERNAL_ERR_PGM_ACTIVE` in `Xcp_CTOErrorMatrix` begin refusing.

The gate is reached through `Xcp_Internal.pgm_state`, added as a fourth disjunct beside the three
session-status bits it already tests, rather than by inventing a fourth session-status bit.
§1.6.1.2.3's session status byte is a wire format with defined bits; `STORE_CAL_REQ`,
`STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` are in it because `GET_STATUS` reports them. A programming
session is not one of its bits and must not be smuggled into one.

§1.6.5.1.1's list of commands that "must always be available during a memory programming
sequence" — `SET_MTA`, `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX` or `PROGRAM_NEXT`, optionally
`UPLOAD` and `BUILD_CHECKSUM` — is an acceptance criterion for this decision: none of those seven
may carry `XCP_INTERNAL_ERR_PGM_ACTIVE`. §6 tests it.

### DD52 — One pending-command slot, not a queue

`Xcp_Internal.pending_command` holds `{uint8 pid; boolean active;}`.

XCP is request/response and the master waits for an answer, so a second outstanding PGM operation
cannot arise from a conformant master, and DD55 refuses it from a non-conformant one. A queue would
be storage for a state the protocol forbids.

The slot stores the PID rather than a function pointer. `Xcp_MainFunction` switches on it to choose
the poll function and to build the response. A function pointer would be one indirection fewer and
one more thing to keep consistent with the response builder; the switch keeps the poll and its
response shape adjacent in one place.

### DD53 — The handler withholds, `Xcp_MainFunction` answers

A deferring handler: validates the request; calls the integrator's start function; sets
`pending_command` and `pgm_state`; sets `*responseExpected = FALSE`; returns `E_OK`.

`Xcp_MainFunction`, while `pending_command.active`: calls the poll function for
`pending_command.pid`. On `E_NOT_OK` it does DD54's work and returns. On `E_OK` it clears the slot,
fills `Xcp_Internal.cto_response.pdu_info` with the positive response or the error packet according
to `pStatusCode`, and sets `cto_response.successful_transmission_pending = TRUE`.

Both halves already exist in the module and neither is new machinery: `Xcp_DTOCmdCalDownload`
withholds a response with `*responseExpected = FALSE`, and the `STORE_CAL_REQ` path already has
`Xcp_MainFunction` publish a packet by setting a `successful_transmission_pending` flag that
`Xcp_StartNextTransmission` arbitrates.

**The poll happens before the `STORE_CAL_REQ` block in `Xcp_MainFunction`, not after.** A master
that is programming is waiting on a response with a t3/t4/t5 timeout running; a store-calibration
request has no master waiting on anything. Ordering the poll first costs nothing and removes a
question a reader would otherwise have to ask.

### DD54 — `EV_CMD_PENDING`, bounded to one in flight

`XCP_EVENT_CMD_PENDING` is 0x05, from §1.2's table of event codes, which carries the same
value and the same severity S1 in both revisions (verified in each; the 1.1 OCR renders this
table legibly enough to read the code, and 1.0's `pdftotext` output confirms it). It is
pushed onto the existing event queue when a poll returns `E_NOT_OK` **and no `EV_CMD_PENDING` from
this pending command is still outstanding**.

The reason for the bound is that the module cannot time these. `Xcp_MainFunction` is cyclic per
SWS_Xcp_00824, but the module may never depend on its period — a rule this codebase already holds
elsewhere — so "every 100 ms" is not expressible and "every call" would emit at whatever rate the
integrator happens to schedule. Bounding to one outstanding event makes the rate follow
`TxConfirmation`, which SWS_Xcp_00859 already forces the module to wait for before transmitting
again. The event rate is then a property of the bus, which is real, instead of a property of an
assumed period, which is not.

§1.7.2.4.2 is satisfied by this: its stated purpose is to "inform the master that the request was
correctly received and the parameters in the request are valid" and to have it restart its timer.
One event in flight does that continuously for as long as the operation runs.

The `pStatusCode` out-parameter is **not** read while the poll returns `E_NOT_OK`. Its contract
(§4) defines it only for the `E_OK` case, matching `Xcp_StoreCalibrationDataToNonVolatileMemory`.

### DD55 — A command arriving mid-operation is answered `ERR_CMD_BUSY`

While `pending_command.active`, any incoming CTO is answered `ERR_CMD_BUSY` (0x10) and does not
reach its handler.

**The existing `ERR_CMD_BUSY` gate does not cover this, and that is the point of the decision.**
That gate tests `cto_response.successful_transmission_pending`, which DD53 leaves `FALSE` for the
whole duration of a deferred operation — precisely so that nothing is transmitted. So the module
would otherwise dispatch the new command, whose handler writes `cto_response.pdu_info`, while
`Xcp_MainFunction` is about to fill the same buffer with the pending command's answer. One of the
two responses would be lost and the other malformed.

**Refusing the command is necessary and NOT sufficient, and an earlier revision of this decision
stopped at the refusal.** It named the interloping handler as the only competing writer and missed
the obvious second one: `Xcp_MainFunction` itself. The `ERR_CMD_BUSY` packet is written into that
same `cto_response.pdu_info`, so between building it and its confirmation there is a window in
which the pending command can complete and overwrite it — putting the `PROGRAM_START` response
inside the frame the master matches to the command it was refused on. Measured, not reasoned: the
buffer CanIf still owned after a completing poll held `(255, 0, 65, 8, ...)` where `(254, 16)` was
due.

So `Xcp_MainFunction` skips the **whole** pending-command block while
`cto_response.successful_transmission_pending` is `TRUE` — the poll included, not merely the
response write. Withholding only the publish would mean polling a callback that has already
returned `E_OK`, and §4 defines `E_OK` as "finished" without defining what a further call returns;
re-polling a completed operation is unspecified behaviour and this module will not rely on it. The
cost is that a completion waits one `Xcp_MainFunction` cycle behind an in-flight CTO, which is
invisible to a master that is by definition waiting on that CTO.

The new test is `pending_command.active`, evaluated beside the existing one. §1.7.3.2.5 lists
`ERR_CMD_BUSY` for every PGM command with the action "wait t7, repeat ∞ times", so a conformant
master already knows what to do with it.

`SYNCH` (0xFC) is exempt: §1.7.1.2 lists it among the Pre-Actions that bring the slave to a
well-defined state before the master retries, and a `SYNCH`
that cannot get through leaves a confused master with no way out. It answers its usual
`ERR_CMD_SYNCH` immediately.

**`SYNCH` must not clear the slot**, which is the trap here and was this design's own first answer.
`Xcp_MainFunction` polls only while `pending_command.active`, so clearing it would stop the polling
and strand the integrator mid-erase: its callback would never be called again, it would never
report completion, and a later `PROGRAM_START` would start a second operation on top of a first
that is still running. The flash driver's operation must be allowed to finish whatever the master
does.

So `SYNCH` sets `pending_command.abandoned` instead. Polling continues to completion; the response
is discarded rather than transmitted; and the slot is released only when the callback returns
`E_OK`. Until then a new PGM command is still answered `ERR_CMD_BUSY` — the operation is over as
far as the master is concerned and not yet over as far as the flash is concerned, and those are
genuinely different facts.

**Abandoning does not touch `pgm_state` at all, and reaching that took two corrections.** This
paragraph first read "`pgm_state` returns to `IDLE`" without qualification. That was right for the
command it was written about — a `PROGRAM_START` abandoned while still in the transient
`XCP_PGM_STARTING` state DD49 then specified, which never established a session — and wrong for
every other: a command deferred *inside* an established session leaves `pgm_state` at
`XCP_PGM_ACTIVE` while pending, so resetting on abandon silently ended that session. DD51's gate
stopped firing for the remaining 38 commands and a second `PROGRAM_START` was accepted where it
must be refused. `PROGRAM_PREPARE` reaches exactly that state, being legal from `ACTIVE` for a
second code block. The reset was therefore conditioned on the abandoned command being
`PROGRAM_START`.

Deleting `XCP_PGM_STARTING` (DD49) then removed the need for the condition and for the reset
itself. Without that third state a deferring `PROGRAM_START` leaves `pgm_state` at `XCP_PGM_IDLE`,
the handler accepting only from `IDLE`, so there is nothing for an abandon to restore — and a
mid-session command must not be reset either way. Abandoning therefore writes nothing: both arms of
the old condition collapse into no code at all.

### DD56 — Programming-mode communication parameters are the live ones

`PROGRAM_START`'s response reports `MAX_CTO_PGM`, `MAX_BS_PGM`, `MIN_ST_PGM` and `QUEUE_SIZE_PGM`
as the module's ordinary `maxCto`, `maxBS`, `minST` and `ctoQueueSize`, and `COMM_MODE_PGM` from
the same `masterBlockModeSupported` and `interleavedModeSupported` flags `GET_COMM_MODE_INFO`
reads.

§1.6.5.1.1 says these "may change when the slave device is in memory programming mode". This module
does not change them, so reporting the live values is the truthful answer rather than a
simplification. A distinct programming-mode `MAX_CTO` would ripple into every buffer size in the
module — the CTO response buffer, the block-transfer state, the generated `ctoInfo` minimum request
sizes — for a benefit SP4a cannot demonstrate and SP4b does not need.

This is load-bearing for SP4b, not decorative: 1.1's §1.6.5.1.3 states that the separation time and
maximum packet count for `PROGRAM`'s block mode "are specified in the response for the
PROGRAM_START command (MAX_BS_PGM, MIN_ST_PGM)". SP4b's `PROGRAM_NEXT` is bounded by exactly these
bytes, so an untruthful value here becomes a wire-visible defect there.

### DD57 — `PROGRAM_RESET` answers, then disconnects

The response is built and handed to the transmit path; the disconnect takes effect when that
response is confirmed, not before.

§1.6.5.1.4 permits either: the command "may or may not have a response". This module answers,
because on the wire a silent `PROGRAM_RESET` is indistinguishable from a slave that crashed while
handling it, and a master cannot tell a successful end-of-programming from a failure it should
report.

**The original reason given for the ordering was false, and is corrected here.** It claimed that
"disconnecting first would discard the response buffer along with the rest of the session state".
It would not. Nothing in the transmit path reads `connection_status` — `Xcp_FinalizeResPacket`,
`Xcp_StartNextTransmission` and `Xcp_TransmitOneFrame` never consult it, and the flag has exactly
three readers in `source/Xcp.c`: the initialisation, the receive gate at `:1509`, and `:1719`. The
module's own `Xcp_CTOCmdStdDisconnect` proves the point by construction: it builds its response and
*then* sets `XCP_CONNECTION_STATE_DISCONNECTED`, in the handler, and the response goes out.

What the ordering actually decides is narrower: which commands arriving in the window between the
response being built and its confirmation are still processed. §1.6.5.1.4 does not say which
instant it means, so this is the module's choice and not a conformance question.

**The disconnect happens in the completion, not on the response's confirmation, and it calls the
same unwind `DISCONNECT` does.** A revision of this decision required the confirmation form, on the
reasoning that a `PROGRAM_RESET` whose response is never confirmed has not been delivered. Building
it disproved the reasoning twice over, both measured:

- **Nothing can bind the deferred disconnect to `PROGRAM_RESET`'s own frame.** `cto_response.pdu_info`
  is one shared buffer and `Xcp_CanIfRxIndication` never transmits, so any command arriving before
  the next `Xcp_MainFunction` — an unbounded window, since that function is aperiodic — overwrites
  the response, and the disconnect then fires on whatever CTO is confirmed next. Measured: a
  following `SYNCH` gives the master `ERR_CMD_SYNCH`, a `GET_STATUS` gives the `GET_STATUS`
  response, and a second `PROGRAM_RESET` — the t7 retry §1.7.3.2.5 mandates — gives `ERR_CMD_BUSY`.
  In each the answer is gone, the slave disconnects anyway, and the master retries into silence:
  exactly the divergence the confirmation form was adopted to prevent. The in-handler form is
  immune because the receive gate drops the interloper before it reaches the buffer.
- **A second door to DISCONNECTED is a second place to forget the unwind.** The first attempt
  skipped `Xcp_DaqFreeAll`, so a `DAQ_DYNAMIC` master that allocated two ODTs, sent `PROGRAM_RESET`
  and reconnected found its next allocation starting from the previous session's lists — the
  contamination `test/free_daq_test.py` exists to prevent.

So `PROGRAM_RESET`'s completion builds its response and then calls the same internal unwind
`Xcp_CTOCmdStdDisconnect` calls, which is shared between them precisely so the two doors cannot
diverge again.

**Two deliberate deviations from §1.7.3.2.5's row for this command.** The row lists
`ERR_CMD_BUSY`, `ERR_PGM_ACTIVE`, `ERR_CMD_SYNTAX`, `ERR_SEQUENCE` and `ERR_ACCESS_LOCKED`.
`ERR_PGM_ACTIVE` is *dropped*: §1.6.5.1.1 requires `PROGRAM_RESET` to remain available during a
programming sequence, so honouring the row would make a session unendable — DD51's gate and this
row cannot both be obeyed. `ERR_GENERIC` is *added*, because the integrator's `Xcp_ProgramReset`
can report failure and §1.6.5.1.1 names that error for a slave not in a state which permits
programming. A comment in `source/Xcp_Pgm.c` claimed the section listed no errors for this command;
it lists five.

**DD50's fix cost this decision its mutation, and the reset is kept regardless.** Once
`Xcp_CTOCmdStdConnect` also resets `pgm_state`, deleting the reset here leaves every test passing:
`PROGRAM_RESET` disconnects and `CONNECT` is the only way back, so the two writers sit on one path
in that order and nothing wire-visible separates them. It stays because it is a real
`ACTIVE`→`IDLE` transition this function owns, which merely happens to be shadowed downstream —
unlike the write DD49's deletion left in `PROGRAM_START`'s failure path, which stored a value the
field already held and was removed. §9's criterion 7 records both as documented exceptions.

`PROGRAM_RESET` is legal from `XCP_PGM_IDLE` as well as `XCP_PGM_ACTIVE`. §1.6.5.1.4: "This command
may be used to force a slave device reset for other purposes." It is therefore not gated on a
programming session, which is the one place in this design where a PGM command is not.

### DD58 — `XCP_FLASH_PROGRAMMING_ENABLED`, defaulting off

`XcpFlashProgrammingEnabled` (ECUC_Xcp_00181, a pre-compile-time boolean in `XcpGeneral`) generates
`XCP_FLASH_PROGRAMMING_ENABLED` in `script/header_cfg.h.jinja2`, in the same
`#ifndef`/`#define`/`#endif` shape `XCP_PAGING_SUPPORTED` already uses, defaulting to `STD_OFF`.

With it off: no PGM handler, no callback declaration and no `pgm_state` is compiled in, and the PGM
`ctoInfo` entries generate disabled. **That is what closes D10** — `CONNECT` stops advertising
flash programming in the default configuration by construction, rather than by a `config/xcp.json`
edit that someone has to remember and that any integrator could undo without noticing.

A DAQ-only build is byte-for-byte unchanged. §6 asserts it.

### DD59 — The generator stops hard-coding the PGM enable bits

`script/source_cfg.c.jinja2` templates the enable bit of every PGM `ctoInfo` entry on its
configuration key, as it already does for every other command. Three new keys join the two revived
ones: `xcp_program_start_api_enable`, `xcp_program_reset_api_enable`,
`xcp_program_prepare_api_enable`. The five commands with no key at all -- `PROGRAM_VERIFY`, `PROGRAM_NEXT`,
`PROGRAM_FORMAT`, `GET_SECTOR_INFO` and `GET_PGM_PROCESSOR_INFO` -- get theirs in SP4b and SP4c.
That accounts for all eleven: three keys exist today, three arrive here, five follow.

Each key is additionally conjoined with `XCP_FLASH_PROGRAMMING_ENABLED`: a command whose handler is
not compiled must not be advertised as enabled, which is D10 restated at the level of a single
command.

**This closes D11.** It is also the smaller half of the fix — see DD60.

### DD60 — The `CONNECT` PGM test is rewritten in the same commit

`test_connect_sets_the_resource_pgm_bit_according_to_enabled_apis` is rewritten to hold two of the
three keys enabled and vary the third, so each conjunct is the sole cause of a `0` in exactly one
case, plus the all-enabled case for `1`.

Its four current cases pass today for one reason (§2.2), and would **still all pass after DD59**,
because none of them is the only-`clear`-disabled or only-`program`-disabled case that DD59 makes
observable. A generator fix whose test cannot see it is a fix that the next refactor silently
reverts. Rewriting the test in the same commit is therefore part of the fix, not tidying that
follows it.

This is the pattern SP2d and SP3 hit four times between them: **a compound condition needs a test
per term, not per outcome.**

### DD61 — `GET_PGM_PROCESSOR_INFO` cannot ship in SP4a

It was in this sub-project's scope when the design was first presented, and reading §1.6.5.2.1's
bit table moved it to SP4b.

Its `PGM_PROPERTIES` byte encodes the available clear/programming mode in bits 1:0, and the table
marks `FUNCTIONAL_MODE = 0, ABSOLUTE_MODE = 0` as **"Not allowed"**. A slave answering this command
must claim at least one mode. SP4a implements neither `PROGRAM_CLEAR` nor `PROGRAM`, so it has
no mode it could claim truthfully, and shipping the command would mean choosing between a forbidden
encoding and advertising a mode that is not there — which is D10 again, one level down.

It belongs in SP4b, where `ABSOLUTE_MODE` becomes true. `MAX_SECTOR` stays 0 until SP4c supplies
the sector model; that is a truthful answer for a slave with no sector description, and
`GET_SECTOR_INFO` correspondingly answers `ERR_OUT_OF_RANGE` for every sector number until then.

---

## 4. The integrator interface

Three functions, declared in `interface/Xcp.h` under `#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)`:

```c
Std_ReturnType Xcp_ProgramStart(uint8 *pStatusCode);
Std_ReturnType Xcp_ProgramReset(uint8 *pStatusCode);
Std_ReturnType Xcp_ProgramPrepare(void *address, uint16 codeSize, uint8 *pStatusCode);
```

For all three:

- **`E_NOT_OK`** — the operation is not finished. `*pStatusCode` is not read. Called again on the
  next `Xcp_MainFunction`.
- **`E_OK`** — the operation has finished, successfully or not. `*pStatusCode` is `0` for success
  and non-zero for failure.

Each is called first from the command handler, to start the work, and then repeatedly from
`Xcp_MainFunction` until it reports completion. The first call is not special and needs no separate
"start" entry point: an integrator whose operation completes immediately returns `E_OK` from that
first call, and the handler answers without ever deferring.

**Why polled rather than a confirmation call.** It is the contract the module already has for a
slow non-volatile operation, so there is one idiom rather than two. It also keeps every call into
XCP arriving from the two contexts the module already reasons about, instead of adding a third from
whatever context a flash driver completes in — which would need an exclusive area around
`pending_command` and a new reentrancy contract to specify and test. SP3 spent a substantial part
of its budget on exactly that class of question.

`Xcp_ProgramPrepare` receives the current MTA and the `Codesize` from the request, rather than
reading module state itself. §1.6.5.2.3 defines the command entirely in terms of those two values.

**Declared in `interface/Xcp.h` only, and NOT mirrored into `test/stub/Xcp_MemoryAccess.h`.** An
earlier revision of this section required both, beside
`Xcp_StoreCalibrationDataToNonVolatileMemory`, so that the three sat next to the function whose
contract they copy. That is not buildable: `interface/Xcp.h` includes the stub header, so a
declaration in both is seen twice by `pcpp`'s expansion and cffi's `cdef()` rejects it with
`FFIError: multiple declarations`. Declaring once is the resolution, and it is a genuine cffi
constraint rather than a workaround covering something else.

The cost is real and worth naming: these three are now separated from the polled NV callback whose
contract §4 says they copy exactly, so nothing in the header puts them side by side. Each of the
three carries a `@details` line naming `Xcp_StoreCalibrationDataToNonVolatileMemory` explicitly, so
the relationship survives the separation in the only place a reader will look.

---

## 5. Source layout

- `source/Xcp_Pgm.c` — **new.** The three handlers. Mirrors `Xcp_Cal.c` / `Xcp_Pag.c` / `Xcp_Daq.c`,
  each of which owns one command group. Added to `add_library` in `CMakeLists.txt`, which is what
  puts it in `xcp_sources.txt` and therefore in the coverage report.
- `source/Xcp.c` — `Xcp_PIDTable` entries for 0xD2, 0xCF, 0xCC; the `pending_command` poll in
  `Xcp_MainFunction` (DD53); DD55's `ERR_CMD_BUSY` test; DD51's fourth disjunct.
- `source/Xcp_Internal.h` — `pgm_state`, `pending_command`, `XCP_EVENT_CMD_PENDING`, and the three
  handler declarations.
- `source/Xcp_Std.c` — `Xcp_DisconnectSession`, the session unwind lifted out of
  `Xcp_CTOCmdStdDisconnect` so `PROGRAM_RESET`'s completion can call the identical sequence (DD57).
  Nothing else: `CONNECT`'s condition is already correct, and D10 and D11 are fixed in the
  generator and the configuration rather than in a handler.

  An earlier revision of this section read "nothing", which was true only while DD57 still required
  the confirmation-time disconnect. Sharing the unwind is the whole point of the corrected
  decision — a second door to DISCONNECTED that reimplements the teardown is a second door that can
  forget part of it, which is what the first attempt did.
- `script/header_cfg.h.jinja2` — `XCP_FLASH_PROGRAMMING_ENABLED` (DD58).
- `script/source_cfg.c.jinja2` — the PGM `ctoInfo` enable bits (DD59) and their minimum request
  sizes: 1 for `PROGRAM_START` and `PROGRAM_RESET`, 4 for `PROGRAM_PREPARE`.
- `config/xcp.schema.json`, `config/xcp.json` — the three new API keys and
  `flash_programming_enabled`, defaulting false.
- `interface/Xcp.h` — §4's declarations, and **only** here; see §4 on why the stub header cannot
  also carry them.
- `CMakeLists.txt` — besides adding `Xcp_Pgm.c` to `add_library`, `XCP_FLASH_PROGRAMMING_ENABLED`
  is derived from the configuration and compiled in, exactly as `XCP_PAGING_SUPPORTED` already is.
  `test/conftest.py` threads the same macro into its compile definitions **and into the CFFI module
  cache key**: the key names the generated runtime and the source text, neither of which mentions
  `programming`, so without it two configurations differing only in the gate would hash to the same
  compiled module and silently reuse each other's code — making every gate-dependent test, in every
  task, unreliable.

---

## 6. Test strategy

Every compound condition gets a test per **term**, mutation-verified: break the term, confirm that
exactly the test covering it fails and no other. This is the discipline that caught four separate
survives-its-own-deletion conjuncts across SP2d and SP3.

**The deferred path** (`test/pgm_deferred_test.py`, new)

- A `PROGRAM_START` whose callback returns `E_NOT_OK` produces **no** CTO response.
- The response appears on the `Xcp_MainFunction` where the callback first returns `E_OK`, and
  carries the values of DD56 read back from the configuration.
- `pStatusCode` non-zero yields `ERR_GENERIC` and leaves `pgm_state` at `IDLE` — asserted on the
  state, not only on the wire, since a slave that answered correctly but left `pgm_state` wrong
  would refuse every subsequent `PROGRAM_START`.
- Exactly one `EV_CMD_PENDING` is outstanding across many busy polls (DD54), and a second appears
  only after the first is confirmed.
- `pStatusCode` is not read while the callback returns `E_NOT_OK` — the stub writes a poison value
  on every busy call and the test asserts it never reaches the wire.

**The session gate** (`test/pgm_session_test.py`, new)

- `PROGRAM_START` from `ACTIVE` → `ERR_GENERIC` (DD49; its §1.7.3.2.5 row lists no `ERR_SEQUENCE`).
- A command mid-operation → `ERR_CMD_BUSY` (DD55), and the pending response still arrives intact
  afterwards. The second assertion is the one that matters: `ERR_CMD_BUSY` alone would also be
  produced by a module that discarded the pending command.
- `SYNCH` mid-operation → `ERR_CMD_SYNCH`, slot cleared, and the later poll completion transmits
  nothing.
- `PROGRAM_RESET` from `IDLE` is accepted (DD57).
- The seven commands §1.6.5.1.1 requires during a programming sequence — `SET_MTA`,
  `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX`, `PROGRAM_NEXT`, `UPLOAD`, `BUILD_CHECKSUM` — do **not**
  carry `XCP_INTERNAL_ERR_PGM_ACTIVE`, asserted against `Xcp_CTOErrorMatrix` directly so it holds
  for the ones SP4b implements later.

**Configuration and the two defects** (extending `test/connect_test.py`; new `test/pgm_configuration_test.py`)

- DD60's rewritten `CONNECT` sweep, per-conjunct rather than per-outcome. **Superseded during the
  final review**: enabling those three commands while they are unimplemented is what makes `CONNECT`
  advertise a group answering `ERR_CMD_UNKNOWN` — D10 returning — so generation now refuses that
  combination and the sweep is replaced by a test of the refusal. SP4b restores it.
- With `XCP_FLASH_PROGRAMMING_ENABLED` off, `CONNECT`'s PGM bit is 0 and all three commands answer
  `ERR_CMD_UNKNOWN` — D10, pinned so it cannot return.
- A DAQ-only build is byte-for-byte unchanged with the gate off.

---

## 7. Risks

- **The gate in DD49 has no users until SP4b.** Its test asserts against `Xcp_CTOErrorMatrix` and
  `pgm_state` rather than against refused commands, so it is real, but it is the one part of this
  design whose value is deferred. Accepted: the alternative is a `PROGRAM_START` that sets a flag
  nothing reads.
- **DD55 adds a test to the hot receive path** for a condition that is false in every build with
  the gate off. It is behind `#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)`, so a DAQ-only build
  does not pay for it — which DD58's byte-for-byte test also checks.
- **`EV_CMD_PENDING` is raised here for three commands only.** Its event code is settled (DD54),
  but the module will be emitting an event whose general use — the interleaved model of §1.7.2.3 —
  is not implemented. A master that reads the event as a promise of interleaved support would be
  wrong. Nothing in §1.7.2.4.2 says it is such a promise, and the two features are separately
  advertised, but it is the one place where this sub-project emits something SP5 will own.

---

## 8. Follow-ups

- SP4b: `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX`, `PROGRAM_NEXT`, `GET_PGM_PROCESSOR_INFO`
  (DD61). `CONNECT`'s PGM bit can first become legitimately true here.
- SP4c: `GET_SECTOR_INFO` and the sector configuration model, `PROGRAM_FORMAT` with functional
  access mode and the block sequence counter, `PROGRAM_VERIFY`.
- SP5: `EV_CMD_PENDING` for non-PGM commands, and the interleaved communication model. This
  sub-project defines the event and raises it for three commands; making it generally available is
  a different design.

**Raised by the final whole-branch review, and each one blocks something concrete:**

- **The seed-and-key unlock lasts exactly one dispatched command** — `source/Xcp.c` clears the
  protection status after every PID except `UNLOCK`, so even an unrelated interposed `GET_STATUS`
  spends it. For CAL_PAG and DAQ that is merely tiresome, since §1.7.3.2.x's action for
  `ERR_ACCESS_LOCKED` is "unlock slave, repeat 2 times" and the master can. For PGM it is fatal:
  `PROGRAM_START` would consume the unlock and `PROGRAM_CLEAR` would be locked again, and
  re-unlocking mid-session is impossible because `GET_SEED` and `UNLOCK` themselves carry
  `ERR_PGM_ACTIVE` — which §1.7.3.2.5 mandates. Pre-existing and affecting all three resource
  groups identically, so out of SP4a's scope to fix; SP4a instead **refuses the configuration at
  generation**, as DD48 does for its STIM equivalent. Fixing the unlock lifetime is what lifts that
  refusal, and it is what will allow `test_get_seed_unlock_genuinely_gates_a_pgm_command` — deleted
  because the configuration it needs no longer generates — to be restored. It was the only proof in
  the suite that seed-and-key gates a **PGM** command specifically.
- **One internal bit governs four `ERR_PGM_ACTIVE` triggers.** Satisfying DD51 for a programming
  session also stopped `SET_MTA`, `UPLOAD` and `BUILD_CHECKSUM` being refused during
  `STORE_CAL_REQ`, `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` — refusals §1.7.3.2.x does list for all
  three. Splitting `XCP_INTERNAL_ERR_PGM_ACTIVE` into a programming-session bit and a
  store/clear-request bit satisfies both readings; the in-code comments currently describe the
  merge as the specification's choice, which it is not. SP4b.
- **`CONNECT`'s PGM resource bit is unreachable in every buildable SP4a configuration**, because
  the generation refusal above forbids enabling the three commands it reads. The line is correct
  and untested; SP4b restores its coverage when those commands exist.
- **`GET_STATUS` reports the resource-protection byte inverted.** §1.6.1.2.3 defines `1 = protected`
  and 1.1's Diagram 17 shows `UNLOCK` answering `FF 00`; measured, byte 2 is `0x00` while PGM is
  locked and `0x10` once unlocked. Pre-existing, unrelated to PGM, and noted here only because the
  final review met it while answering the protection question.

---

## 9. Acceptance

1. A default build — `XCP_FLASH_PROGRAMMING_ENABLED` off — is byte-for-byte identical to today's,
   and `CONNECT` no longer advertises PGM.
2. With the gate on, `PROGRAM_START` defers, emits at most one outstanding `EV_CMD_PENDING`, and
   answers with DD56's values when the integrator's callback completes.
3. `PROGRAM_RESET` answers and then disconnects, without resetting the device (SWS_Xcp_00856).
4. `PROGRAM_PREPARE` passes MTA and `Codesize` to the integrator and answers `ERR_GENERIC` on
   refusal.
5. A command arriving mid-operation is answered `ERR_CMD_BUSY` and the pending response still
   arrives.
6. ~~Each of the three `CONNECT` PGM conjuncts is independently observable in a test.~~
   **Unmeetable, by this design's own choice.** Generation refuses `programming.enabled` together
   with any of the three commands `CONNECT` reads, because they do not exist until SP4b and
   enabling them reinstates D10. That makes the resource bit unreachable in every buildable SP4a
   configuration, so no test can observe the conjuncts. The line is correct and stays; SP4b restores
   its coverage. See §8.
7. Every new compound condition has a per-term test that fails under the mutation deleting its term,
   **with three documented exceptions**, each a defensive guard whose invariant is stated in place:
   `Xcp_MainFunction`'s `pending_command.active` test, masked by `Xcp_PgmPollPendingCommand`'s
   `default` arm; the same test before `Xcp_PgmAbandonPendingCommand`, masked by a released slot
   holding `pid == 0`; and DD57's `pgm_state` reset, shadowed by `CONNECT`'s. Each is kept
   deliberately — a later change to a masking layer would activate a defect no test could see.

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

### DD49 — One programming-session state, three values

`Xcp_Internal.pgm_state` takes `XCP_PGM_IDLE`, `XCP_PGM_STARTING` (a `PROGRAM_START` is being
polled) and `XCP_PGM_ACTIVE` (session open).

§1.6.5.1.1 requires that `PROGRAM_CLEAR`, `PROGRAM`, `PROGRAM_MAX` and `PROGRAM_NEXT` "are not
allowed, until the PROGRAM_START command has been successfully executed". The gate is implemented
here, in SP4a, even though every command it gates arrives in SP4b. That is deliberate: the gate is
what `PROGRAM_START` *means*, and a `PROGRAM_START` that sets a flag nothing reads is not
testable as the thing the specification describes. SP4b's handlers consult it on arrival.

Refusal is `ERR_SEQUENCE` (0x29). §1.7.3.2.4's matrix lists `ERR_SEQUENCE` for `PROGRAM_CLEAR`,
`PROGRAM` and `PROGRAM_MAX`, so this invents nothing.

`STARTING` earns its place at the completion of the poll, not before it: `Xcp_MainFunction` has to
know whether a finished `PROGRAM_START` should move to `ACTIVE` or back to `IDLE`, and that is a
property of the state it came from. Reading it off `pending_command.pid` instead would work and
would put the session's transitions somewhere other than the session's state.

It is also correct on its own for §1.6.5.1.1's gate, which DD55 makes unreachable in practice: a
master sending `PROGRAM_CLEAR` mid-poll has not had a successful `PROGRAM_START`, and `STARTING`
answers that question without consulting the pending slot.

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

The new test is `pending_command.active`, evaluated beside the existing one. §1.7.3.2.4 lists
`ERR_CMD_BUSY` for every PGM command with the action "wait t7, repeat ∞ times", so a conformant
master already knows what to do with it.

`SYNCH` (0xFC) is exempt: §1.7.1.1 makes it the master's means of resynchronising, and a `SYNCH`
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
`E_OK`. Until then `pgm_state` returns to `IDLE` but a new PGM command is still answered
`ERR_CMD_BUSY` — the operation is over as far as the master is concerned and not yet over as far as
the flash is concerned, and those are genuinely different facts.

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
report. Ordering matters and is easy to get backwards: disconnecting first would discard the
response buffer along with the rest of the session state.

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

Three functions, declared in `interface/Xcp.h` under `#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)`
and stubbed in `test/stub/Xcp_MemoryAccess.h` beside
`Xcp_StoreCalibrationDataToNonVolatileMemory`, whose contract they copy exactly:

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

---

## 5. Source layout

- `source/Xcp_Pgm.c` — **new.** The three handlers. Mirrors `Xcp_Cal.c` / `Xcp_Pag.c` / `Xcp_Daq.c`,
  each of which owns one command group. Added to `add_library` in `CMakeLists.txt`, which is what
  puts it in `xcp_sources.txt` and therefore in the coverage report.
- `source/Xcp.c` — `Xcp_PIDTable` entries for 0xD2, 0xCF, 0xCC; the `pending_command` poll in
  `Xcp_MainFunction` (DD53); DD55's `ERR_CMD_BUSY` test; DD51's fourth disjunct.
- `source/Xcp_Internal.h` — `pgm_state`, `pending_command`, `XCP_EVENT_CMD_PENDING`, and the three
  handler declarations.
- `source/Xcp_Std.c` — nothing. `CONNECT`'s condition is already correct; D10 and D11 are fixed in
  the generator and the configuration, not in the handler.
- `script/header_cfg.h.jinja2` — `XCP_FLASH_PROGRAMMING_ENABLED` (DD58).
- `script/source_cfg.c.jinja2` — the PGM `ctoInfo` enable bits (DD59) and their minimum request
  sizes: 1 for `PROGRAM_START` and `PROGRAM_RESET`, 4 for `PROGRAM_PREPARE`.
- `config/xcp.schema.json`, `config/xcp.json` — the three new API keys and
  `flash_programming_enabled`, defaulting false.
- `interface/Xcp.h`, `test/stub/Xcp_MemoryAccess.h` — §4's declarations.

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
  state, not only on the wire, since a slave that answered correctly but stayed `STARTING` would
  refuse every subsequent `PROGRAM_START`.
- Exactly one `EV_CMD_PENDING` is outstanding across many busy polls (DD54), and a second appears
  only after the first is confirmed.
- `pStatusCode` is not read while the callback returns `E_NOT_OK` — the stub writes a poison value
  on every busy call and the test asserts it never reaches the wire.

**The session gate** (`test/pgm_session_test.py`, new)

- `PROGRAM_START` from `ACTIVE` → `ERR_SEQUENCE`.
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

- DD60's rewritten `CONNECT` sweep: each of the three keys is the sole disabled one in its own case.
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
6. Each of the three `CONNECT` PGM conjuncts is independently observable in a test.
7. Every new compound condition has a per-term test that fails under the mutation deleting its term.

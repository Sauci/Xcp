# SP4b — Clear and program, absolute access mode (PGM)

**Status:** design approved 2026-09-07.

**Predecessors:** SP4a, whose deferred-response machinery this sub-project consumes unchanged — the
pending-command slot, the polled integrator contract, `EV_CMD_PENDING`, the `ERR_CMD_BUSY` guard
and the programming-session state. SP1 for the block-transfer helpers `DOWNLOAD`/`DOWNLOAD_NEXT`
established.

**Successor:** SP4c — `GET_SECTOR_INFO` and the flash sector configuration model, `PROGRAM_FORMAT`
with functional access mode and the block sequence counter, `PROGRAM_VERIFY`. All eleven PGM
commands remain the goal; this document is the second third.

---

## 0. Which specification numbering this document uses

Citations are to **XCP Part 2 — Protocol Layer Specification 1.1** unless a citation names 1.0.
§1.6.5 keeps its numbering in both revisions down to the fourth level, so no mapping is needed.

**The PGM error matrix is §1.7.3.2.5.** §1.7.3.2.4 is DAQ's. SP4a's design cited the wrong one in
three places before its final review caught it; every error claim below is against §1.7.3.2.5 and
was checked against the 1.0 PDF via `pdftotext -layout`, since the 1.1 OCR garbles tables.

1.1 adds a paragraph to §1.6.5.1.3 that 1.0 does not have, describing master block mode for
`PROGRAM` and stating that `MAX_BS_PGM` and `MIN_ST_PGM` — as reported by `PROGRAM_START` — are
what bound it. That paragraph is why DD62 exists, and it is quoted there.

**AUTOSAR.** SWS_Xcp_00855 requires flash programming support; PGM is in scope, unlike `SET_DAQ_ID`
which §4.1 excludes. No SWS requirement bears on the commands in this sub-project beyond that.

---

## 1. Scope

**In:**

- `PROGRAM_CLEAR` (0xD1), `PROGRAM` (0xD0), `PROGRAM_NEXT` (0xCA), `PROGRAM_MAX` (0xC9),
  `GET_PGM_PROCESSOR_INFO` (0xCE).
- Absolute access mode: the MTA addresses flash directly and post-increments.
- Master block mode for `PROGRAM`/`PROGRAM_NEXT`, with the block accumulated in the module.
- Lifting SP4a's generation refusal on the three commands `CONNECT` advertises, term by term.

**Out:**

- Functional access mode, the block sequence counter, and `PROGRAM_FORMAT` (SP4c). Mode byte
  `0x01` on `PROGRAM_CLEAR` is refused, per DD67.
- `GET_SECTOR_INFO` and the sector configuration model (SP4c). `MAX_SECTOR` reports 0, per DD68.
- `PROGRAM_VERIFY` (SP4c).
- Compression, encryption and non-sequential programming — reported unsupported by DD68 and not
  implemented. §1.6.5.2.4's `PROGRAM_FORMAT` is where a slave would accept them, and it is SP4c's.
- **The seed-and-key unlock lifetime.** SP4a refuses
  `apis.resource_protection.programming` at generation because the unlock lasts one dispatched
  command; SP4b does not touch that, and the refusal stays. See §8.

---

## 2. What already exists

- **The deferred-response machinery**, whole: `Xcp_Internal.pending_command`, the poll in
  `Xcp_MainFunction`, `Xcp_PgmPollPendingCommand` and `Xcp_PgmCompletePendingCommand` as switches
  on the pending PID, `EV_CMD_PENDING` bounded to one outstanding event, and the `ERR_CMD_BUSY`
  guard. SP4b adds `case` arms; it changes none of it.
- **The programming session.** `pgm_state` is `XCP_PGM_ACTIVE` between a successful `PROGRAM_START`
  and a `PROGRAM_RESET` or a `CONNECT`. §1.6.5.1.1 requires the four commands in this sub-project
  to be refused until `PROGRAM_START` has succeeded, and SP4a implemented that gate with no users;
  SP4b is its first user.
- **Block transfer.** `Xcp_BlockTransferIsActive`, `Xcp_BlockTransferAcknowledgeFrame`,
  `Xcp_BlockTransferFrameElements`, `Xcp_BlockTransferAbort` and
  `Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE, expected)` — the last being exactly
  `PROGRAM_NEXT`'s negative response shape. `Xcp_DTOCmdCalDownloadNext` is the worked example.
- **`Xcp_BlockTransferWriteSlaveMemory` is NOT reusable here.** It writes RAM through
  `Xcp_WriteSlaveMemoryTable`, synchronously. Flash is neither.
- **Every error code needed** is in `interface/Xcp_Errors.h`.

---

## 3. Design decisions

### DD62 — `MAX_BS_PGM` is its own configured value, revising DD56

`PROGRAM_START` reports `programming.max_block_size` as `MAX_BS_PGM`. `MAX_CTO_PGM`,
`MIN_ST_PGM` and `QUEUE_SIZE_PGM` continue to report the live values, exactly as DD56 has them.

DD56 chose to report the ordinary `maxBS` on the reasoning that this module does not change its
communication parameters in programming mode. That was true of SP4a and is not true of SP4b.
Accumulating a block (DD63) costs `MAX_BS_PGM × (MAX_CTO − 2)` bytes of RAM, and the configuration
schema admits `max_bs` up to 255 with `max_cto` up to 256 — 64770 bytes at those limits, against
1530 at XCP-on-CAN's ordinary `MAX_CTO` of 8. (An earlier revision of this paragraph reached the
same figure by way of 65535, which is `max_dto`'s ceiling, not `max_cto`'s. The conclusion was
right and the arithmetic behind it was not.) A module that sized a buffer from a parameter chosen
for DAQ and calibration throughput would be letting an unrelated decision dictate its own
footprint.

§1.6.5.1.1 grants the freedom in as many words: *"The communication parameters MAX_CTO, MAX_BS,
MIN_ST and QUEUE_SIZE may change when the slave device is in memory programming mode. The new
communication parameters MAX_CTO_PGM, MAX_BS_PGM, MIN_ST_PGM and QUEUE_SIZE_PGM are returned in the
positive response."* DD56 declined it for want of a need; SP4b has one.

This is load-bearing rather than cosmetic. 1.1's §1.6.5.1.3 states that the maximum number of
packets in a `PROGRAM` block is *"specified in the response for the PROGRAM_START command
(MAX_BS_PGM, MIN_ST_PGM)"* — so the value reported here is the contract the master programs
against, and a slave reporting more than its buffer holds would be inviting the overrun DD63's
guard then has to refuse.

`programming.max_block_size` defaults to 8. That is a modest, useful block on CAN — 48 payload
bytes per acknowledged round trip against 6 without block mode — and an integrator wanting more
raises it knowingly.

### DD63 — the block accumulates in the module; one deferred write per block

`PROGRAM` opens a block and its payload is copied into `Xcp_Internal.pgm_block`. Each
`PROGRAM_NEXT` appends. The frame that completes the block calls the integrator once, through
SP4a's pending-command machinery, and that single deferred call is what the master's response
waits on.

**Intermediate frames answer nothing and complete entirely in receive context.** §1.6.5.1.3: *"The
slave device will acknowledge only the last PROGRAM_NEXT command packet."* They set
`*responseExpected = FALSE`, copy their bytes, and return — no callback, no polling, no pending
slot. This is the property that makes the whole scheme work, and it is worth stating plainly
because the alternative is what makes it fail: if each frame triggered its own deferred write, a
master pacing frames by `MIN_ST_PGM` would deliver the next one while a write was still pending,
and SP4a's `ERR_CMD_BUSY` guard would refuse it — breaking a block-transfer sequence with an error
that exists to protect a response buffer. The guard is correct; it simply must never see these
frames.

The counters come from the existing `Xcp_Internal.block_transfer`, which already tracks requested
and per-frame element counts for `DOWNLOAD`/`DOWNLOAD_NEXT`. `PROGRAM_NEXT`'s negative response —
`ERR_SEQUENCE` carrying the number of elements the slave expected — is `Xcp_FillErrorPacketWithData`,
already in use by `Xcp_DTOCmdCalDownloadNext`. §1.7.3.2.5 lists `ERR_SEQUENCE` for `PROGRAM_NEXT`
with the pre-action **`SYNCH+PROGRAM`**, which is the master-side confirmation of this design: a
block that goes wrong is restarted from its `PROGRAM`, not resumed from the failed frame, so the
module has no partial-block state to reconcile — it discards the buffer and waits for a new
`PROGRAM`.

A block whose declared length exceeds `MAX_BS_PGM × (MAX_CTO − 2)` is refused
`ERR_MEMORY_OVERFLOW`, which §1.7.3.2.5 lists for `PROGRAM`. The buffer is sized from the same
generated constants the refusal tests against, so the two cannot drift apart.

### DD64 — `PROGRAM` with zero data elements ends the segment

§1.6.5.1.3: *"The end of the memory segment is indicated, when the number of data elements is 0."*
That is a distinct case from programming zero bytes: it flushes any block still open, ends the
segment, and answers. It does not end the programming sequence — §1.6.5.1.3 gives that to
`PROGRAM_RESET`, which SP4a implements.

### DD65 — `PROGRAM_MAX` is refused inside an open block

§1.6.5.2.6: *"This command does not support block transfer and it may not be used within a block
transfer sequence."* Inside an open block it answers `ERR_SEQUENCE`, which its §1.7.3.2.5 row
lists.

Outside a block it programs `MAX_CTO − 1` elements from the MTA with no length byte — the fixed
size is the point of the command — and defers exactly as `PROGRAM` does.

### DD66 — the MTA post-increments only on a successful write

§1.6.5.1.3: *"The MTA will be post-incremented by the number of data bytes."* It advances when the
integrator reports success, and not when it reports failure.

The failure case is the one worth being explicit about. §1.7.3.2.5 gives `PROGRAM` the pre-action
`SYNCH+SET_MTA`, so a master recovering from a failed write re-points the MTA itself — but a slave
that had already advanced it would have moved a pointer the master believes it still controls, and
a master that trusted the slave's position rather than re-setting it would resume one block further
on, leaving a hole in the programmed image that no error reported.

### DD67 — `PROGRAM_CLEAR`, absolute access mode only

The MTA points at the start of a memory sector and the DWORD clear range gives the length
(§1.6.5.1.2). It defers through SP4a's machinery: erase is the slowest operation in the protocol,
which is why §1.7.3.2.5 gives `PROGRAM_CLEAR` the t4 timeout where ordinary commands get t1.

Mode byte `0x01`, functional access mode, is refused `ERR_OUT_OF_RANGE` — listed in its row with
the action *"retry other parameter"*, which is precisely what a master should do with a mode this
slave does not offer. Refusing it here rather than ignoring the mode byte matters: §1.6.5.1.2 makes
the two modes interpret the *same* clear-range field completely differently — a length in absolute
mode, a bit mask of areas in functional mode — so a slave that ignored the byte would erase
whatever `0x00000001` means as a length when the master meant "all calibration areas".

DD68 advertises the same restriction through `PGM_PROPERTIES`, so a conformant master never sends
it.

### DD68 — `GET_PGM_PROCESSOR_INFO` reports what this slave actually offers

`PGM_PROPERTIES` sets `ABSOLUTE_MODE` (bit 0) and clears `FUNCTIONAL_MODE` (bit 1) —
§1.6.5.2.1's table gives `0 1` as "Only Absolute mode supported". Compression, encryption and
non-sequential programming are all reported unsupported, because none is implemented and
§1.6.5.2.4's `PROGRAM_FORMAT`, where a slave would accept them, is SP4c's.

This is the command DD61 removed from SP4a. §1.6.5.2.1's table marks both mode bits clear as "Not
allowed", and SP4a implemented neither `PROGRAM_CLEAR` nor `PROGRAM`, so it had no mode it could
claim without either using a forbidden encoding or advertising something absent — which is defect
D10 one level down. SP4b is where `ABSOLUTE_MODE` becomes true, so it is where the command belongs.

`MAX_SECTOR` reports 0. That is truthful for a slave with no sector description, and it keeps
`GET_SECTOR_INFO` — still unimplemented — consistent, since §1.6.5.2.2 has it answer
`ERR_OUT_OF_RANGE` for a sector that is not available and every sector number is out of range when
there are none.

### DD69 — SP4a's command refusal lifts term by term; its protection refusal does not

SP4a's generator refuses `programming.enabled` together with any of
`xcp_program_clear_api_enable`, `xcp_program_api_enable` or `xcp_program_max_api_enable`, because
enabling a command `CONNECT` advertises while `Xcp_PIDTable` routes it to `Xcp_CmdNotImplemented`
is defect D10 returning. It was written to be self-removing, and each term goes as its command
lands. `CONNECT`'s PGM resource bit becomes reachable, and SP4a's §9 criterion 6 — recorded there
as unmeetable by its own design — is restored, along with DD60's per-conjunct sweep of the three
keys.

**SP4a's other refusal stays.** `apis.resource_protection.programming` remains refused at
generation: the seed-and-key unlock still lasts exactly one dispatched command, so a protected PGM
configuration still cannot complete a programming sequence, and nothing in SP4b changes that. SP4a's
guard says so in its own text — the condition that lifts it is the unlock lifetime being fixed, not
SP4b landing.

---

## 4. The integrator interface

Two functions, added beside SP4a's three in `interface/Xcp.h` **only** — `interface/Xcp.h` includes
`test/stub/Xcp_MemoryAccess.h`, so a declaration in both is rejected by cffi as `FFIError: multiple
declarations`. Both copy `Xcp_StoreCalibrationDataToNonVolatileMemory`'s polled contract, as SP4a's
three do, and each carries a `@details` line naming it:

```c
Std_ReturnType Xcp_ProgramClear(void *address, uint32 clearRange, uint8 *pStatusCode);
Std_ReturnType Xcp_ProgramWrite(void *address, const uint8 *pData, uint16 length, uint8 *pStatusCode);
```

`E_NOT_OK` means unfinished and `*pStatusCode` is not read; `E_OK` means finished, successfully or
not, with the outcome in `*pStatusCode`. Each is called first from the command handler — so an
integrator whose work is instantaneous is answered on the same exchange with no deferral and no
`EV_CMD_PENDING` — and then once per `Xcp_MainFunction` until it reports completion.

`pData` points into the module's block buffer and is valid only for the duration of the call. An
integrator that needs the bytes after returning `E_NOT_OK` must copy them; this is stated in the
`@details`, because the polled contract means the same pointer is presented on every subsequent
call and an implementation that merely retained it would be correct by accident.

---

## 5. Source layout

- `source/Xcp_Pgm.c` — the five handlers, and one `case` each in `Xcp_PgmPollPendingCommand` and
  `Xcp_PgmCompletePendingCommand`.
- `source/Xcp_Internal.h` — `pgm_block` (the buffer and its fill level), and the handler
  declarations.
- `source/Xcp.c` — `Xcp_PIDTable` entries for 0xD1, 0xD0, 0xCA, 0xC9 and 0xCE, replacing
  `Xcp_CmdNotImplemented`.
- `interface/Xcp.h` — §4's two declarations.
- `script/header_cfg.h.jinja2` — `XCP_PGM_MAX_BLOCK_SIZE`, which sizes the buffer.
- `script/source_cfg.c.jinja2` — the per-command terms of SP4a's refusal deleted; the `ctoInfo`
  minimum request sizes for the five commands checked against their layouts.
- `config/xcp.schema.json`, `config/xcp.json` — `programming.max_block_size`, and the three API
  keys returned to `true`.
- `test/pgm_program_test.py`, `test/pgm_clear_test.py` — new.
- `test/pgm_configuration_test.py`, `test/connect_test.py` — the refusal tests that lift, and
  DD60's restored sweep.

---

## 6. Test strategy

Per-term tests, mutation-verified: break the term, confirm exactly the test covering it fails.

**The block path is where this sub-project can most easily ship a green test that pins nothing**,
because intermediate frames transmit nothing at all. `transmitted(handle) is None` after a frame is
therefore true whatever the module did with the bytes — the same shape as the vacuous assertion
SP4a's Task 2 shipped and its review caught. Every block test must assert on the **bytes the
integrator was handed**, not on the absence of a frame.

- The buffer accumulates across frames rather than holding only the last: program a multi-frame
  block and assert `Xcp_ProgramWrite` received the concatenation.
- A short final frame completes a block and writes the true length.
- `PROGRAM_NEXT` with the wrong element count returns `ERR_SEQUENCE` **carrying the expected
  count**, asserted on that byte and not merely on the error.
- A block declared longer than `MAX_BS_PGM × (MAX_CTO − 2)` is refused `ERR_MEMORY_OVERFLOW` and
  writes nothing.
- A failed write leaves the MTA unmoved (DD66), asserted through a following `PROGRAM` writing at
  the same address.
- `PROGRAM_MAX` inside an open block is refused `ERR_SEQUENCE` (DD65).
- `PROGRAM_CLEAR` mode `0x01` is refused `ERR_OUT_OF_RANGE` (DD67).
- All four gated commands are refused `ERR_SEQUENCE` before `PROGRAM_START` — SP4a's gate, tested
  for the first time against real handlers.
- `CONNECT` advertises PGM once the three commands exist, with DD60's per-conjunct sweep restored.

The six stale-frame traps from SP4a all apply: reset the mock before the exchange under test,
assert on the frame that exchange produced, pump `Xcp_MainFunction()` when a transmission must have
happened, and never scan `call_args_list` for content.

---

## 7. Risks

- **The block buffer is the module's largest single allocation** once programming is enabled — 48
  bytes at the default, more if an integrator raises `max_block_size`. It is inside
  `#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)`, so a DAQ-only build pays nothing, and §9 keeps
  the byte-for-byte criterion that proves it.
- **DD63 assumes intermediate frames are cheap.** They copy into a buffer in receive context. If a
  future transport made `Xcp_CanIfRxIndication` more expensive, or if `MIN_ST_PGM` were reported
  smaller than the copy takes, the assumption would need revisiting — but the module chooses
  `MIN_ST_PGM`, so it controls both sides of that.
- **`GET_PGM_PROCESSOR_INFO` advertises what SP4c will change.** `MAX_SECTOR` goes from 0 to a real
  count and `FUNCTIONAL_MODE` may be set. Both are additive and neither invalidates a master that
  read the SP4b values, but a master caching them across a firmware update would be wrong — which
  is its own error, not this module's.

---

## 8. Follow-ups

- SP4c: `GET_SECTOR_INFO` and the sector configuration model, `PROGRAM_FORMAT` with functional
  access mode and the block sequence counter, `PROGRAM_VERIFY`.
- **Inherited from SP4a and untouched here** — the seed-and-key unlock lasting one dispatched
  command, which is why `apis.resource_protection.programming` stays refused at generation and why
  the test proving seed-and-key gates a PGM command stays deleted; one internal bit governing four
  `ERR_PGM_ACTIVE` triggers; and `GET_STATUS` reporting the resource-protection byte inverted
  against §1.6.1.2.3.

---

## 9. Acceptance

1. A build with `XCP_FLASH_PROGRAMMING_ENABLED` off is byte-for-byte identical to SP4a's.
2. `CONNECT` advertises flash programming, and `PROGRAM_CLEAR`, `PROGRAM` and `PROGRAM_MAX` answer
   it — D10 stays fixed in the direction SP4a could not test.
3. A multi-frame block reaches the integrator as one contiguous write of the right length at the
   right address.
4. A failed write leaves the MTA where the master left it.
5. `PROGRAM_START`'s response reports `programming.max_block_size` as `MAX_BS_PGM`.
6. `GET_PGM_PROCESSOR_INFO` reports absolute mode only and `MAX_SECTOR` 0.
7. `apis.resource_protection.programming` is still refused at generation.
8. Every new compound condition has a per-term test that fails under the mutation deleting its
   term, or is recorded as a documented exception with the invariant it relies on.

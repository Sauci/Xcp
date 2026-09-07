# Shared-state defects: a memory disclosure, an authentication bypass, and four siblings

**Status:** design approved 2026-09-07.

**Nature:** six pre-existing defects in shipped code, none introduced by SP4a or SP4b. They are
fixed on the SP4b branch by the maintainer's decision; the commits are worded so that
`git log --grep` finds them without knowing SP4b exists.

**Provenance.** SP4b's Task 4 shipped a memory disclosure by writing `Xcp_Internal.block_transfer`
for PGM block mode, where `Xcp_CanIfTxConfirmation` reads it as a slave-block-mode `UPLOAD`
continuation. Fixing it produced DD63's rule — *a command group may not write shared state whose
readers live outside its own file* — and the final whole-branch review then asked the obvious next
question: **where else is that rule violated?** The answer was `DOWNLOAD`. A full audit of every
mutable member of `Xcp_InternalType` followed, and found five more.

**Every defect below was measured, not reasoned.** Each entry states what was observed.

---

## 0. Specification numbering

Citations are to **XCP Part 2 — Protocol Layer Specification 1.1** unless a citation names 1.0.
Seed-and-key is **§1.6.1.2.4** (`GET_SEED`) and **§1.6.1.2.5** (`UNLOCK`); the resource protection
model is §1.6.1.1.1's `RESOURCE` byte and **§1.6.1.1.3**'s `GET_STATUS`. `UPLOAD` is **§1.6.1.2.7**,
`SET_MTA` **§1.6.1.2.6**, `GET_ID` **§1.6.1.2.2**. `DOWNLOAD` is §1.6.2.1.1 and its block, fixed-size
and short forms are §1.6.2.2.1 through §1.6.2.2.3. All identical in both revisions, checked against
each table of contents.

**Every number in the sentence above was wrong when this section was first written** — `GET_SEED`
and `UNLOCK` were given as §1.6.1.1.6/§1.6.1.1.7, `GET_STATUS` as §1.6.1.2.3, and §1.6.2.2 was
labelled `UPLOAD` when it is `DOWNLOAD`'s optional subsection. The wrong seed-and-key numbers
reached four places in source and tests before Task 5's implementer checked them against both
tables of contents rather than repeating them, and they have been corrected there too. A citation
nobody verifies is worse than none: it looks like evidence.

---

## 1. The shape they share

Five of the six are one of two shapes, and naming them is what makes the audit repeatable:

**Shape A — a predicate answering a broader question than its reader asks.** A field records "a
transfer is in progress"; a reader treats it as "*this kind* of transfer is in progress". DD70 and
the already-fixed PGM instance are both this.

**Shape B — session state that `CONNECT` does not reset.** §1.6.1.1.1 makes `CONNECT` the start of
a session, and SP4a established that no state of one session may survive into the next when it made
`CONNECT` clear `pgm_state`. But `CONNECT` clears `pgm_state` and `pgm_block` **and nothing else**.
DD73, DD74 and DD75 are three faces of that single omission.

The sixth, DD72, is its own thing: a value written before the operation that justifies it, and not
rolled back when that operation fails.

---

## 2. Design decisions

### DD70 — `Xcp_CanIfTxConfirmation` must ask about slave block mode, not block mode

**Measured.** With `master_block_mode` enabled: `SET_MTA(0x1000)`, then `DOWNLOAD` declaring 10
elements and carrying 6 — which opens a block — then `GET_STATUS`, answered normally `(0xFF, 0x00)`.
Confirming that answer performs **7 slave-memory reads at `0x1006..0x100C`** and transmits
`(0xFF, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A)` — seven bytes of slave memory, unsolicited, to a
master that asked for nothing.

`Xcp_DataTransferInitialize` (`source/Xcp.c:2395`) is called by `UPLOAD` (`source/Xcp_Std.c:727`)
and `DOWNLOAD` (`source/Xcp_Cal.c:95`) and records no direction.
`Xcp_CanIfTxConfirmation` (`source/Xcp.c:1948`) asks `Xcp_BlockTransferIsActive()` and, if true,
continues the transfer by reading memory and transmitting it — which is only ever correct for
**slave** block mode, where the slave sends the frames.

**The direction is already known at both call sites**: `UPLOAD` passes
`slaveBlockModeSupported`, `DOWNLOAD` passes `masterBlockModeSupported`. It is simply not recorded.
So the state records it, and `Xcp_CanIfTxConfirmation` uses a narrower predicate.

**`Xcp_BlockTransferIsActive()` itself does not change.** `source/Xcp_Cal.c:30`, `:151` and `:206`
legitimately ask the direction-agnostic question "is a block open" for their `ERR_SEQUENCE`
sequence checks, and narrowing it there would break `DOWNLOAD_NEXT`'s lost-packet detection —
§1.6.2.2.1 requires exactly that check.

### DD71 — the frame counter must not underflow

**Measured.** `Xcp_BlockTransferAcknowledgeFrame` (`source/Xcp.c:2452`) computes
`requested_elements -= frame_elements` on a `uint8`. In DD70's scenario that is `4 - 6 = 254`, so
the runaway is not one frame but roughly **37 frames and about 254 bytes** before the counter
walks back down to zero.

This is a genuine second defect rather than an aspect of DD70: the subtraction is unguarded on its
own terms, and a future caller could reach it another way. It is fixed by refusing to acknowledge
more elements than are outstanding, which is also the condition §1.6.2.2.1's `ERR_SEQUENCE` exists
to report.

### DD72 — a seed request that fails must not leave a resource requestable

**Measured — this is an authentication bypass.** `GET_SEED` for the PGM resource refused
`(0xFE, 0x22)`, then `UNLOCK` answered `(0xFF, 0x10)`, and `GET_STATUS` reported
`protection_status = 0x10`. **PGM was unlocked with no seed ever produced.**

Two independent legs, and it needs both:

- `Xcp_DTOCmdStdGetSeed` (`source/Xcp_Std.c:890`) assigns
  `Xcp_Internal.requested_protected_resource = resource` **before** calling `Xcp_GetSeed`, and does
  not roll it back when that call fails. `Xcp_SetProtectionStatus` (`source/Xcp.c:2559`) later
  copies that field into `protection_status` verbatim.
- `Xcp_DTOCmdStdUnlock` (`source/Xcp_Std.c:771`) admits a key when
  `last_pid == GET_SEED || last_pid == UNLOCK`, reading `last_pid` as "the previous command was a
  **successful** `GET_SEED`". `source/Xcp.c:1833` writes `last_pid` for any *dispatched* command,
  including one that answered an error.

**Both legs are fixed, not just one.** Rolling back the resource alone would leave `UNLOCK` still
admitting a key after a failed `GET_SEED`; fixing `last_pid` alone would leave a stale requested
resource for the next legitimate sequence to inherit. §1.6.1.1.7 makes `UNLOCK` meaningful only
against a seed the slave actually issued, and a defence that depends on one of two independently
wrong things staying right is not a defence.

### DD73 — the key calculation must receive the seed's length

**Measured.** A four-byte seed `11 22 33 44` is transmitted correctly on the wire, and
`Xcp_CalcKey` is then called with `buffer = 11 22 33 44…` and **`seed_length = 0`** — for every
seed, every session.

`Xcp_DTOCmdStdGetSeed` (`source/Xcp_Std.c:943`) sets `seed.total_length = 0x00u` when the final
chunk goes out, meaning "no bytes left to send". `Xcp_DTOCmdStdUnlock` (`source/Xcp_Std.c:805`)
passes that same field to `Xcp_CalcKey` as the **seed length**. The two readings are incompatible
and the second is the one that matters: an integrator honouring the length parameter computes its
key from a zero-length seed, so **the key is not bound to the challenge** and the same key is valid
in every session.

Nothing caught it because the existing test doubles ignore the parameter. The fix keeps the
remaining-bytes bookkeeping in `current_index`, where it belongs, and leaves `total_length` meaning
what its name says. §6 requires a test double that *uses* the length, since one that ignores it
cannot fail.

### DD74 — `CONNECT` must tear down the whole session, not part of it

§1.6.1.1.1 makes `CONNECT` the start of a session, and SP4a acted on that when it made `CONNECT`
clear `pgm_state` — a state whose survival left a later master unable to program. `CONNECT`
(`source/Xcp_Std.c:1346-1358`) clears `pgm_state` and calls `Xcp_PgmBlockAbort()`, **and nothing
else**. Three measured consequences, one omission:

- **An open block transfer survives.** The `CONNECT` response is overwritten and never transmitted,
  and the new session opens with the slave streaming the previous session's memory (DD70's runaway,
  now spanning a reconnect).
- **A partial key survives.** Session 1 announces an 8-byte key and delivers 6. After
  `DISCONNECT`, `CONNECT` and `GET_SEED`, an `UNLOCK` carrying **2** bytes completes the previous
  session's key and grants CAL_PAG.
- **The MTA survives.** A `DOWNLOAD` with no `SET_MTA` writes at the previous session's address.

`CONNECT` therefore resets the block transfer, both key buffers, the seed, and the MTA, alongside
what it already clears.

**The MTA reset needs two corrections to what this decision first said.** It claimed §1.6.2 "leaves
the MTA undefined until `SET_MTA`". That is not a literal claim in either revision — verified
against both PDFs. What the specification actually supports is weaker and sufficient: `SET_MTA` is
categorised "Standard, optional" and no default MTA is stated anywhere, so a master that programs
or uploads without first setting it is relying on something the specification does not promise.

And the reset is to `NULL_PTR`, **not** to "a state the module refuses to use" as first written.
That would require an address-validity flag this module does not have — there is no MTA validity
check anywhere in it — and inventing one to satisfy a sentence in a design document would be the
wrong order of reasoning. `NULL_PTR` matches `Xcp_Init`'s own existing precedent for the same
field. It is an improvement on the previous session's address rather than a guarantee, and the code
comment says so rather than implying the stronger property.

### DD75 — `GET_ID` must set the whole MTA, not half of it

**Measured.** `SET_MTA` with address extension 7, then `GET_ID`, then `UPLOAD(3)`: the
identification string is read with **extension 7**, the previous command's.

`Xcp_DTOCmdStdGetId` (`source/Xcp_Std.c:1045`) writes `memory_transfer.address` and leaves
`.extension` untouched, while every reader — `source/Xcp.c:2488` and the checksum helpers — takes
the pair. §1.6.1.2.2 has `GET_ID` point the MTA at the identification it is about to be asked for,
which is a complete pointer, not an address. `Xcp_DTOCmdDaqGetDaqEventInfo`
(`source/Xcp_Daq.c:1424-1425`) sets both and shows the intended contract.

---

### DD76 — `UNLOCK`'s key-calculation failure had no branch at all

**Found by the acceptance pass, and pre-existing.** `Xcp_DTOCmdStdUnlock`'s
`if (Xcp_CalcKey(...) == E_OK)` had no `else`, so when the integrator's callback failed nothing was
written to `cto_response.pdu_info` while `*responseExpected` stayed `TRUE` — and whatever the buffer
held went out instead. Measured: an `UNLOCK` whose `Xcp_CalcKey` fails **retransmits the previous
`GET_SEED` response as its own positive answer**, telling the master `0xFF` for an unlock that did
not happen and handing back seed bytes it was not answering for.

**This is the module's own D2/D7 class, which SP1 fixed twice**, and `GET_DAQ_ID`'s branch in
`source/Xcp_Std.c` still carries the comment describing it: an empty branch "left the response
buffer holding whatever the previous command wrote while responseExpected stayed TRUE".

It answers `ERR_GENERIC` (0x31), a **recorded deviation**: §1.7.3.2.1's row for `UNLOCK` lists seven
codes and none fits an integrator callback that cannot compute a key at all — `ERR_ACCESS_LOCKED`,
which the sibling branch already answers, means the key was *wrong*, which is a different statement.
Same shape and same treatment as DD57's `PROGRAM_RESET` deviation.

**A prediction in its dispatch was wrong and is corrected here.** I expected a following `UNLOCK` to
be refused `ERR_SEQUENCE` once the stale byte stopped corrupting `last_pid`. That is structurally
impossible: `Xcp_DTOCmdStdUnlock`'s admission gate is a two-element set-membership test over
`last_pid` and cannot distinguish which member it holds. What the fix guarantees is narrower and
still worth having — a following `UNLOCK` re-answers the same honest `ERR_GENERIC`, never a stale
positive.

---

## 3. What the audit found sound

**One entry no longer holds, and this fix batch is what invalidated it.** `cto_response.pdu_info`
was judged sound because it is "a buffer, not a predicate". DD72's second leg made it a predicate,
by reading its byte 0 to decide whether a dispatched command answered an error. That is what turned
DD76's empty branch from a stale response into a corrupted gate as well, and it is a worked example
of the audit's own lesson: a field's soundness is a property of its readers, so adding a reader can
falsify it. Re-audit the readers of anything a fix teaches to answer a new question.

Two further consequences of that leg, both measured, neither a reason to revert it:

- An `UNLOCK` whose `Xcp_CalcKey` fails no longer corrupts `last_pid` — DD76 fixes the cause.
- `SYNCH` between `GET_SEED` and `UNLOCK` no longer breaks the sequence, because `SYNCH` answers
  `ERR_CMD_SYNCH` by design and the leg does not record erroring commands. This is a **deliberate
  behaviour change, not a regression**: §1.7.1.1 makes `SYNCH` the master's means of resynchronising,
  and a resynchronisation that silently invalidated an in-progress seed-and-key exchange would be a
  worse reading than one that does not. Recorded because nobody decided it at the time — it fell out
  of the leg.

`key_slave.current_index`, which DD74 added to `CONNECT`'s reset, is read nowhere: a fourth
write-only dead field alongside `connect_mode` and `event.successful_transmission_pending`.



Recorded so the audit is not repeated from scratch. Each of these was traced writer-to-reader and
found to have no reader inferring more than its writer answered:

`connection_status`, `session_status` (`SET_REQUEST` refuses every bit but `STORE_CAL_REQ`, so the
`ERR_PGM_ACTIVE` gate cannot be wedged), `protection_status` itself, `ongoing_transmit_type` (one
frame outstanding at a time), `cto_response.pdu_info` (a buffer, not a predicate),
`daq_alloc_state`, `allocated_daq_count`, `internal_buffer`, `seed.buffer`, `seed.current_index`,
and `key_slave`.

**`daq_pointer` was measured rather than assumed**: `FREE_DAQ`, `CLEAR_DAQ_LIST` and the advance all
invalidate it, and `ALLOC_ODT`/`ALLOC_ODT_ENTRY` only ever raise counts, so a validated pointer
cannot go out of bounds. `SET_DAQ_PTR(0,0,3)` → `0xFF`; a growing `ALLOC_ODT_ENTRY` then
`WRITE_DAQ` → `0xFF`; `FREE_DAQ` then `WRITE_DAQ` → `ERR_OUT_OF_RANGE`.

**`connect_mode` and `event.successful_transmission_pending` are write-only dead state** — no
reader anywhere. Not defects; noted because a future reader would inherit whatever the last writer
left, and the fields look meaningful.

---

## 3b. A seventh defect, reported and NOT fixed

**`UNLOCK` never asks whether a seed is held.** Its only gate is `last_pid`, which is about
*sequence*, not about whether the slave ever issued a challenge. Three routes were measured on the
fixed tree, all reaching `Xcp_CalcKey` with `seedLength` 0 and all granting the resource; the
sharpest is `GET_SEED(A)` succeeding, `GET_SEED(B)` being refused, then `UNLOCK` — DD72's own
scenario one step further along.

It is pre-existing and none of DD70–DD76 changed it. It is left unfixed deliberately: the remedy is
a design decision about what "a seed is held" means — DD73 is what finally gives the module a
`seed.total_length` capable of answering it — and taking that decision inside a batch of measured
repairs would be reasoning in the wrong order. It belongs to whoever takes the seed-and-key work
next, alongside the unlock-lifetime follow-up SP4a recorded.

**The PGM fields are clean.** Nothing outside `source/Xcp_Pgm.c` reads `pgm_block`; `pgm_state` is
read outside only at `source/Xcp.c:1824` and `pending_command` at `:1445`, `:1740`, `:1787` and
`:1994` — each asking exactly the question its writer answers.

---

## 4. Test strategy

Every fix is mutation-verified, and **each defect gets a test that fails against the current code**
— these are all reproducible today, so a test that cannot fail before the fix is not testing the
defect.

- DD70: the measured `DOWNLOAD`/`GET_STATUS`/confirm sequence, asserting zero slave-memory reads
  and no unsolicited frame. **And the converse**: `UPLOAD`'s slave block mode must still chain its
  frames across confirmations — narrowing the predicate is exactly what could kill it.
- DD71: acknowledge more elements than outstanding; the counter must not wrap.
- DD72: **both legs separately.** A failed `GET_SEED` followed by `UNLOCK` must be refused, and
  that must still hold with either leg's fix reverted alone — otherwise the pair is one fix with a
  spare.
- DD73: a test double that **reads** the length parameter and fails on zero. The existing doubles
  ignore it, which is why this shipped.
- DD74: one test per surviving item — block, key, MTA — each across a real `DISCONNECT`/`CONNECT`.
- DD75: `SET_MTA(ext=7)` → `GET_ID` → `UPLOAD`, asserting the extension the integrator receives.

The ten recurring test-authoring traps from SP4a and SP4b all apply; the most relevant here is that
a setup guard satisfied by a leftover response is how several of these went unnoticed.

---

## 5. Acceptance

1. Each of the six has a test that fails on the current code and passes after the fix.
2. `UPLOAD` slave block mode, `DOWNLOAD`/`DOWNLOAD_NEXT` master block mode, and the PGM block path
   all still work — the fixes narrow predicates and add resets, both directions that break
   neighbours.
3. A gate-off build remains behaviourally unchanged; SP4b's property test still passes.
4. No new instance of the ten recurring test-authoring traps.
5. The commit messages identify these as pre-existing security fixes independent of SP4b, findable
   by `git log --grep`.

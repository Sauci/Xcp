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

### DD77 — `CONNECT` finishes the teardown DD74 started

DD74 reset five fields and justified all of them by quoting XCP part 1 - Overview 1.0/§2.3: *"In
'DISCONNECTED' state … The session status, all DAQ lists and the protection status bits are
reset."* The final review noticed that the quote names **session status** and **DAQ lists**, and
DD74 reset neither — five fields §2.3 does not mention, and not the two it does. DD77 closes that
gap for the two fields where the module can act honestly:

- `session_status`'s request bits (R1), which otherwise wedge command rows permanently — 42 of them
  in the default build, 38 with flash programming enabled (four rows carry
  `XCP_INTERNAL_ERR_PGM_ACTIVE` only with that gate off; counted from `Xcp_CTOErrorMatrix`'s own
  initializer entries per preprocessor branch, not by grepping the macro name, which also matches
  the dispatch gate's own uses).
- `daq_pointer.valid` (R2), which otherwise lets a new session write the old session's ODT entry.

**A caveat that belongs on the record, because it is load-bearing and unverifiable here.** XCP
part 1 - Overview is **not in `docs/external`** — the repository holds part 2 (1.0 and 1.1),
ASAP2, and three AUTOSAR documents, and nothing else. The §2.3 text is quoted in full at
`Xcp_CanIfRxIndication` (`source/Xcp.c`) and cited from two further sites in `Xcp_Std.c`, but
nobody working from this repository alone can check it. It was already the justification for
DD74's five resets before DD77 leaned on it for two more. Every other citation in this batch was
re-verified against a held PDF during the final review — this is the one that cannot be, and it
should be either confirmed against the real document or replaced with a part 2 argument.

Not everything §2.3 names is reset even now: **all DAQ lists** is the DD25/SP2d question, and
`DAQ_RUNNING` deliberately keeps tracking real state rather than being cleared to a value nothing
enforces. DD77 is the honest subset, not full compliance with the sentence.

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
  behaviour change, not a regression**: §1.7.1.2 lists `SYNCH` among the master's Pre-Actions for error recovery,
  and a resynchronisation that silently invalidated an in-progress seed-and-key exchange would be a
  worse reading than one that does not. Recorded because nobody decided it at the time — it fell out
  of the leg.

`key_slave.current_index`, which DD74 added to `CONNECT`'s reset, is read nowhere: a fourth
write-only dead field alongside `connect_mode` and `event.successful_transmission_pending`.



Recorded so the audit is not repeated from scratch. Each of these was traced writer-to-reader and
found to have no reader inferring more than its writer answered:

`connection_status`, ~~`session_status`~~ (**retracted — see §3c/R1; the gate CAN be wedged, and
permanently**), `protection_status` itself, `ongoing_transmit_type` (one
frame outstanding at a time), ~~`cto_response.pdu_info`~~ (**retracted — see §3 above**),
`daq_alloc_state`, `allocated_daq_count`, `internal_buffer`, `seed.buffer`, `seed.current_index`,
and `key_slave`.

**`daq_pointer` was measured rather than assumed**: `FREE_DAQ`, `CLEAR_DAQ_LIST` and the advance all
invalidate it, and `ALLOC_ODT`/`ALLOC_ODT_ENTRY` only ever raise counts, so a validated pointer
cannot go out of bounds. `SET_DAQ_PTR(0,0,3)` → `0xFF`; a growing `ALLOC_ODT_ENTRY` then
`WRITE_DAQ` → `0xFF`; `FREE_DAQ` then `WRITE_DAQ` → `ERR_OUT_OF_RANGE`.

**That measurement answered *bounds*, not *session isolation*, and the audit did not notice the
difference.** `daq_pointer` survives `CONNECT` exactly as the MTA did — see §3c/R2.

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

It is pre-existing and none of DD70–DD77 changed it. It is left unfixed deliberately: the remedy is
a design decision about what "a seed is held" means — DD73 is what finally gives the module a
`seed.total_length` capable of answering it — and taking that decision inside a batch of measured
repairs would be reasoning in the wrong order. It belongs to whoever takes the seed-and-key work
next, alongside the unlock-lifetime follow-up SP4a recorded.

**The PGM fields are clean.** Nothing outside `source/Xcp_Pgm.c` reads `pgm_block`; `pgm_state` is
read outside only at `source/Xcp.c:1824` and `pending_command` at `:1445`, `:1740`, `:1787` and
`:1994` — each asking exactly the question its writer answers.

---

## 3c. Retractions and additions from the final review

A whole-branch review after the seven fixes landed re-derived §3 rather than trusting it. **It
confirmed that all seven fixes close their own defects and found no route that reopens any of
them.** Everything below is a correction to the *record*, or a defect the audit missed — not a
regression in the fixes.

### R1 — `session_status` is NOT sound. The `ERR_PGM_ACTIVE` gate can be wedged permanently.

§3 claimed the gate "cannot be wedged" because `SET_REQUEST` refuses every bit but
`STORE_CAL_REQ`. That reasoning is wrong: the one accepted bit is enough.

`SET_REQUEST(STORE_CAL_REQ)` ORs the bit into `session_status` (`Xcp_Std.c`). It is cleared in
exactly one place — `Xcp_MainFunction` (`Xcp.c`) — and only when the integrator's
`Xcp_StoreCalibrationDataToNonVolatileMemory` returns `E_OK`. An integrator whose NVM write fails,
or which is stubbed out, returns `E_NOT_OK` forever and the bit never clears. From that moment the
gate refuses **every command whose `Xcp_CTOErrorMatrix` row carries `XCP_INTERNAL_ERR_PGM_ACTIVE`
— 42 rows in the default build, 38 with flash programming enabled (four rows carry the bit only
with that gate off; counted from the matrix's own initializer entries per preprocessor branch, not
by grepping the macro name, which also matches the dispatch gate's own uses), `DISCONNECT` (0xFE)
among them**, along with `GET_SEED`, `UNLOCK`, and all of CAL and DAQ.

`CONNECT` (0xFF) is itself ungated (its row is `0x00u`), so a master can still connect — and
recovers nothing, because `CONNECT` does not clear the bit. **Only `Xcp_Init` — a power cycle —
recovers.** Verified in code, not inferred: the row, the gate, the single clear site, and
`CONNECT`'s teardown.

An availability defect of the same class as the six, and pre-existing. **Fixed — DD77.**

`CONNECT` now clears the session-status *request* bits. Three options were weighed: (a) `CONNECT`
clears them, (b) the module bounds the wait and gives up, (c) it stays an undocumented integrator
contract. (a) is taken, because the quoted §2.3 already commits this module to resetting session
status at the session boundary, and the alternative it trades against is a permanent refusal of
`DISCONNECT`.

The cost is stated rather than hidden: if the integrator is still storing when a new master
connects, `Xcp_MainFunction` stops polling it, so that store goes untracked and no `EV_STORE_CAL`
follows. The new master never requested the store, and `GET_STATUS` reporting a pending request
the new session cannot influence is the more misleading of the two answers.

**Masked, not zeroed.** `session_status` also carries `DAQ_RUNNING` (bit 6), which `Xcp_Daq.c`
maintains from whether DAQ lists are actually running. Zeroing the byte would make `GET_STATUS`
report a stopped DAQ while it runs — this module does not stop DAQ on `CONNECT` (§R2 and DD25/SP2d),
so that bit must keep tracking the truth rather than be reset to a state nothing enforces. Only
`STORE_CAL_REQ`, `STORE_DAQ_REQ` and `CLEAR_DAQ_REQ` are cleared; today only the first is reachable,
the other two being refused by `SET_REQUEST`, and they are included so the reset stays correct if
that ever changes.

**A second, smaller thing R1 exposes:** DD74's own comment justifies `CONNECT`'s teardown by
quoting XCP part 1 §2.3, "the session status … [is] reset" — and then resets five fields §2.3 does
not name while leaving `session_status`, the one it does, standing. `Xcp_Std.c` separately claims
the bit lasts only "until the next `CONNECT`", which was untrue before this batch and is untrue
after it. The citation was used to license a set of resets it does not describe.

### R2 — `daq_pointer` survives `CONNECT`, which is DD74's own item in a different field

DD74 fixed "the MTA survives, so a `DOWNLOAD` with no `SET_MTA` writes at the previous session's
address". `daq_pointer` is the same kind of per-session cursor and was not reset, because §3
measured it for *bounds* safety and never asked the isolation question.

Session 1 sends `SET_DAQ_PTR(0,0,0)`, setting `valid = TRUE`. The master vanishes without
`DISCONNECT` — DD74's own threat model. A new master `CONNECT`s, and sends `WRITE_DAQ` with no
`SET_DAQ_PTR` of its own: the pointer is still valid, so the write lands in the previous session's
ODT entry. `Xcp_DaqFreeAll` does clear it, but runs only from `DISCONNECT` and only under
`DAQ_DYNAMIC`.

Not a disclosure — DAQ-list corruption by a master that never selected that entry. **Fixed —
DD77**, narrowly: `CONNECT` sets `daq_pointer.valid = FALSE` and touches nothing else.

That narrowness is the point. `FALSE` is already how this module represents 1.1/1.6.4.1.1.2's
undefined pointer, so the next `WRITE_DAQ` answers `ERR_OUT_OF_RANGE` and tells the master to
position the pointer it never set. Clearing the DAQ lists *themselves* is the larger DD25/SP2d
question about what a session boundary owes static DAQ lists, and this deliberately does not
settle it — which is why the test asserts the pool is still allocated after the reconnect, so a
later change that did free it would fail the test rather than silently pass it.

### R3 — the `last_pid` narrowing is wider than §3 recorded

DD72's second leg stopped recording `last_pid` for commands that answered an error, using byte 0 of
`cto_response.pdu_info` as the test. That gate cannot distinguish "the handler refused" from "the
handler wrote no response at all", so it also skips `last_pid` for PGM's response-suppressing block
paths (`Xcp_Pgm.c`). §3 recorded the widening for `SYNCH` only. It grants nothing and enables
nothing — `last_pid` gates admission, and skipping it can only make a later command more
restricted, never less — but the record should describe what the gate does, not one instance of it.

### R4 — DD73 changed `GET_SEED(mode=1)` after an exhausted seed

Removing the `total_length` zeroing means a `mode=1` request made after the whole seed has been
transmitted now answers `(0xFF, 0x00)` — zero bytes remaining — where it previously answered
`ERR_SEQUENCE`. The new answer is the defensible one: 1.1/1.6.1.2.4's `ERR_SEQUENCE` rule is about
a `mode=1` with no preceding `mode=0` at all, which is a different condition from "you already have
everything". It was a side effect rather than a decision, no test covered it either way — the only
existing `mode=1` test always leaves a remainder — and it is now pinned by
`test_get_seed_mode_1_after_the_whole_seed_was_sent_answers_zero_remaining`.

### R5 — a latent direction bug in `DOWNLOAD_NEXT`, not reachable today

`Xcp_DTOCmdCalDownloadNext` asks the same direction-agnostic "is a block open" predicate that
produced DD70, and would write through an `UPLOAD`-opened block. Only `ERR_CMD_BUSY` and an
unstated invariant prevent it today, so it is latent rather than live. Recorded because DD63's rule
is what makes it latent, and a future change to either could make it reachable.

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

1. Each of the six has a test that fails on the current code and passes after the fix — **with
   one stated exception: DD71's guard is mutation-verified green on its own** (its own test file
   records this; this criterion did not, until the final review). DD71 hardens the subtraction
   DD70 already stops from being reached, so no pre-fix scenario reaches it; it is kept because
   the two fixes are independent and a later change could reopen the path.
2. `UPLOAD` slave block mode, `DOWNLOAD`/`DOWNLOAD_NEXT` master block mode, and the PGM block path
   all still work — the fixes narrow predicates and add resets, both directions that break
   neighbours.
3. A gate-off build remains behaviourally unchanged; SP4b's property test still passes.
4. No new instance of the ten recurring test-authoring traps.
5. The commit messages identify these as pre-existing security fixes independent of SP4b, findable
   by `git log --grep`.

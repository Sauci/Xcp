# SP5-RESUME — starting DAQ from non-volatile memory

**Date:** 2026-09-10
**Baseline:** `develop` at `d25337e`
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.1*, ASAM e.V. (`docs/external/`).
1.0 is cited where it says the same thing and is the readable copy.

**Depends on:** SP5-NV (PRs #20–#25). The persistence a resume resumes *from* is already built:
`STORE_DAQ_REQ_NO_RESUME`, `CLEAR_DAQ_REQ`, the session configuration id, the four accessors, and
the polled start-up read.

---

## 0. What RESUME actually is, against what the roadmap said it was

The roadmap's SP5 entry described "`CONNECT`'s resume handshake". **There is no such thing.** Every
occurrence of RESUME in both revisions was read; none is in `CONNECT`'s section. The feature is:

| Element | Where |
|---|---|
| the master arms it | `SET_REQUEST` mode bit 2, `STORE_DAQ_REQ_RESUME` (1.1/§1.6.1.2.3) |
| the slave advertises it | `GET_DAQ_PROCESSOR_INFO`, `DAQ_PROPERTIES` bit 2 `RESUME_SUPPORTED` (1.1/§1.6.4.1.2.4) |
| the slave reports being in it | `GET_STATUS` session status bit 7 `RESUME` (1.1/§1.6.1.1.3) |
| a list reports belonging to it | `GET_DAQ_LIST_MODE` mode bit 7 `RESUME` (1.1/§1.6.4.1.2.6) |
| the slave announces it | `EV_RESUME_MODE`, code `0x00` (1.1/§1.8.1) |

And the behaviour itself, from 1.1/§1.6.4.1.2.6's description of the RUNNING flag:

> the slave being in RESUME mode started the DAQ list automatically

**So RESUME is autonomous DTO transmission at power-up, with no master session.** That is the whole
feature; everything else is reporting.

---

## 1. Two things the existing code already got right

**DTO transmission is not gated on a session.** `Xcp_TriggerEventChannel` (`source/Xcp_DaqRuntime.c`)
checks `Xcp_State == XCP_INITIALIZED`, the event-channel bound, and each list's own RUNNING flag —
nothing else. A restored list that comes up RUNNING transmits without any change to the transmit
path.

**Both connection gates admit a third state.** `source/Xcp.c:1922` (CTO dispatch) and `:2232` (STIM
reception) test `!= XCP_CONNECTION_STATE_DISCONNECTED`, not `== XCP_CONNECTION_STATE_CONNECTED`, and
`XCP_CONNECTION_STATE_RESUME` has been declared and never entered since before this phase. Whoever
wrote that left the room this design needs.

---

## 2. Design decisions

### DD103 — the integrator pushes; the module does not read

DD94 settled the store direction: the module hands over no buffer, exposes accessors, and the
integrator persists from its own knowledge of the memory. **The restore direction is the mirror of
that**, not a new mechanism:

```c
boolean        Xcp_GetResumeArmedState(void);                                     /* store side */

Std_ReturnType Xcp_RestoreDaqListCount(uint16 daqListCount);                      /* restore side */
Std_ReturnType Xcp_RestoreOdtCount(uint16 daqListNumber, uint8 odtCount);
Std_ReturnType Xcp_RestoreOdtEntryCount(uint16 daqListNumber, uint8 odtNumber, uint8 entryCount);
Std_ReturnType Xcp_RestoreOdtEntry(uint16 daqListNumber, uint8 odtNumber, uint8 odtEntryNumber,
                                   const Xcp_OdtEntryType *pEntry);
Std_ReturnType Xcp_RestoreDaqListMode(uint16 daqListNumber, uint8 mode, uint16 eventChannelNumber,
                                      uint8 prescaler, uint8 priority);
Std_ReturnType Xcp_ResumeComplete(uint16 sessionConfigurationId);
```

Each setter is the counterpart of the accessor that saved the same field, so an integrator writes one
loop over its own format calling the inverse of whatever it queried.

**This mirror is incomplete for one setter, and the incompleteness is real.** `Xcp_RestoreDaqListMode`
takes four fields -- mode's own DIRECTION/TIMESTAMP/PID_OFF bits, the event channel, the prescaler and
the priority -- and none of them has a counterpart among DD94's four read accessors:
`Xcp_GetDaqListSelectedState` reports only the transient SELECTED bit, not the rest of the mode byte,
and nothing reports the event channel binding, prescaler or priority a live `SET_DAQ_LIST_MODE` last
wrote. An integrator restoring these four values supplies them from its own configuration knowledge --
typically the same static assignment its own tooling built the master's measurement setup from -- not
from anything this module ever handed back. Under `DAQ_DYNAMIC`, where the master picks the event
channel at runtime rather than a generator fixing it, that is a genuine limitation: the integrator
cannot capture the one field that decides whether a resumed list transmits at all, only reconstruct it
from what it independently knows the master last requested. Adding the missing accessors is a
follow-up phase, not this one -- this document and `interface/Xcp.h` state the limitation rather than
paper over it.

**Two things the signatures above leave ambiguous, made explicit here** — the first because getting
exactly this wrong is what PR #25 fixed:

- **`Xcp_RestoreDaqListMode`'s `mode` is the `GET_DAQ_LIST_MODE` *response* layout**
  (`XCP_DAQ_LIST_MODE_*`: SELECTED 0, DIRECTION 1, TIMESTAMP 4, PID_OFF 5, RUNNING 6, RESUME 7), not
  `SET_DAQ_LIST_MODE`'s *request* layout (`XCP_DAQ_LIST_MODE_REQ_*`: ALTERNATING 0, DIRECTION 1,
  TIMESTAMP 4, PID_OFF 5). The module keeps two mode tables and they differ at bits 0, 6 and 7. The
  response layout is right because this restores state the accessors reported, and
  `Xcp_GetDaqListSelectedState` reads that byte. RUNNING and RESUME in the passed value are ignored:
  `Xcp_ResumeComplete` sets both, so an integrator cannot half-start a list by hand.
- **`Xcp_RestoreDaqListCount` is meaningful only under `DAQ_DYNAMIC`**, where it does what `ALLOC_DAQ`
  does. Under `DAQ_STATIC` the lists are generated and the count is fixed, so it answers `E_OK` for a
  count equal to the configured one and `E_NOT_OK` otherwise — an integrator restoring a
  configuration stored by a differently-generated build finds out here rather than by writing entries
  into lists that do not exist.

**Rejected: the module pulls through polled callbacks.** One asynchronous call per ODT entry —
roughly 3.5 KB of them for a default dynamic pool — which is the shape DD94 rejected for storing,
for the same reason.

**Rejected: the integrator replays XCP commands internally.** The handlers answer on the wire and
assume a master session; driving them from nowhere means synthesising commands and suppressing
responses.

### DD104 — the armed flag is a fifth accessor, not a changed signature

`STORE_DAQ_REQ_RESUME` asks for two things: store the configuration, and arm resume. The module owns
no non-volatile memory, so the second fact has to reach the integrator.

`Xcp_GetResumeArmedState` is queried during `Xcp_StoreDaqConfiguration` exactly as the four existing
accessors are. **Rejected: adding a parameter to `Xcp_StoreDaqConfiguration`.** DD78 justified a
breaking rename when a field's meaning changed *for every existing reader*; that does not transfer
here, because an integrator who never arms resume is unaffected — the same argument SP4c's DD86 made
against forcing signature edits on absolute-mode users.

**Rejected: inferring it from a non-zero stored id.** 1.1 has `STORE_DAQ_REQ_NO_RESUME` store an id
*precisely without* arming resume, so the inference is wrong by construction — and wrong in the
direction PR #25 just fixed.

### DD105 — nothing is live until `Xcp_ResumeComplete`

The setters accumulate; they do not take effect. `Xcp_ResumeComplete` adopts the session
configuration id, enters `XCP_CONNECTION_STATE_RESUME`, sets session status bit 7, marks the restored
lists RESUME and RUNNING, and queues `EV_RESUME_MODE`.

This is DD97's commit-id-last rule pointed the other way. An integrator whose non-volatile read fails
halfway leaves a slave that resumed **nothing**, rather than one transmitting a half-built
configuration at a real event channel. It also answers DD100's problem without guessing: the module
never has to decide when the integrator's memory became readable, because the integrator says so by
calling this.

`Xcp_ResumeComplete` refuses a configuration the ordinary path would refuse to start — a list with no
written ODT entry is answered `ERR_DAQ_CONFIG` by `START_STOP_DAQ_LIST` today, and resuming must not
create by the back door a state the front door rejects.

### DD106 — resumed lists survive a DISCONNECT

`Xcp_DisconnectSession` (`source/Xcp_Std.c:1390`) calls `Xcp_DaqFreeAll()` under `DAQ_DYNAMIC`.
Untouched, that means: power up, resume, a master connects and disconnects, and the resumed
measurement is dead until the next power cycle — under `DAQ_DYNAMIC` only, since the teardown does
not run for static builds. A behavioural difference by configuration type that no integrator asked
for and the specification does not describe.

So the teardown frees the dynamic lists **this session's master allocated** and skips lists carrying
the RESUME flag: they came from non-volatile memory, not from the session that is ending.

**The cost, stated plainly.** That function exists to be one door. Its own comment records that a
second door to `XCP_CONNECTION_STATE_DISCONNECTED` is exactly what went wrong before it was factored
out. This adds a condition inside the one door rather than a second door — the distinction that keeps
DD106 from re-opening that defect — and the test below is built so a blanket skip fails.

### DD107 — restoration is a start-up activity

Every `Xcp_Restore*` answers `E_NOT_OK` after `Xcp_ResumeComplete` has run, and after any `CONNECT`.
A live session configures DAQ through the protocol, and a setter that still worked mid-session would
be an unpoliced path into DAQ state that no `ERR_` code describes.

---

## 3. What this does not change

- The transmit path. DTO transmission was never session-gated (§1).
- `CONNECT`. It does not touch DAQ state today and does not need to.
- `STORE_DAQ_REQ_NO_RESUME`, `CLEAR_DAQ_REQ`, the session configuration id, and the start-up read —
  all as SP5-NV left them, except that bit 2 stops being refused.

---

## 4. Test strategy

**The acceptance bar is DTOs with no `CONNECT` ever sent.** Autonomous transmission is the feature;
every other assertion is reporting. No existing test in this repo transmits without a session, so
this one cannot pass by inheriting a fixture's habits.

**The `DISCONNECT` exemption gets a fixture built to break a lazy implementation.** A resumed list and
a session-allocated list share one dynamic pool; after `DISCONNECT` the resumed one must still
transmit **and** the session one must be gone. An implementation that skipped the teardown wholesale
would pass a weaker test and fail this one.

Then: `Xcp_GetResumeArmedState` TRUE after a bit-2 store and FALSE after bit-1; the setters refused
after commit and after `CONNECT`; `GET_STATUS` bit 7; `GET_DAQ_LIST_MODE` bits 7 and 6; and
`EV_RESUME_MODE` reaching the wire.

**One test is expected to fail and is not a regression.** SP5-NV's
`test_resume_stays_unadvertised_so_the_refusal_above_stays_coherent` pins `RESUME_SUPPORTED` clear
specifically so that the phase implementing RESUME is pointed at the `SET_REQUEST` bit-2 refusal it
must reverse. It is updated here, deliberately.

---

## 5. Open assumption

**That RESUME is a distinct connection state rather than an exception inside DISCONNECTED.**

The module's `Xcp_ConnectionState` declares `XCP_CONNECTION_STATE_RESUME`, and both connection gates
are written `!= DISCONNECTED` rather than `== CONNECTED`, so the existing code reads that way.
Part 2 never contradicts it. But the state model is **XCP Part 1 — Overview §2.3**, which is *not* in
`docs/external`; the module quotes it in six places from text carried forward, including "in
DISCONNECTED state there's no XCP communication" and "DAQ list transfer is inactive"
(`source/Xcp.c:2250`).

Everything in this design is consistent with either reading. If Part 1 turns out to constrain what a
slave may transmit while unconnected, **this is the decision that moves**, and DD105's commit point is
where a different answer would attach. Recorded as an assumption, not as a finding.

# The CTO response invariant — no handler transmits a buffer it did not write

**Defect family:** D2 (`Xcp_PIDTable` maps every PID to a handler that answers positively) and
Finding 4 of `2026-09-15-xcp-max-cto-bound-d18-design.md` (`USER_CMD` with no configured callback
replays the previous command's response). Both are instances of one missing invariant. D18's §5
named the work that would close it — "the central-invariant sweep across every site that sets
`SduLength`" — and deferred it. This is that sub-project.

**Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. Every
citation carries its revision prefix. The §1.7.3 passage this design turns on was read from
`pdftotext -layout` on 1.0 (line 5199) and from the 1.1 OCR sidecar (line 6302); the two agree word
for word, which is the strongest confirmation available for a passage the 1.1 text layer does not
yield.

---

## 1. What is wrong

`Xcp_CanIfRxIndication` (`source/Xcp.c`) sets
`Xcp_Internal.cto_response.successful_transmission_pending` from `response_expected` at three
sites — the pending-command `ERR_CMD_BUSY` gate, the end of the dispatch chain, and the
disabled-command arm. The handler's return value reaches only `Xcp_ReportError`. So the shared
buffer is queued for transmission on **every** dispatch outcome, whether or not anything wrote it.

`Xcp_Internal.cto_response._packet` is shared by every CTO response and zero-initialised only at
`Xcp_Init`. Nothing clears it between commands. A handler that returns without filling therefore
does not produce an empty response — it produces the **previous command's** response, sent under
the current command's request.

Measured, on the branch that closed Finding 4: a `CONNECT` followed by a `USER_CMD` against a
configuration with no `user_cmd_function` put `FF 05 C0 08 08 00 01 01` on the wire, at
`SduLength` 8 — the positive `CONNECT` response, byte for byte. Not stale bytes; a well-formed
positive response carrying another command's PID, which a master cannot distinguish from a genuine
one except by a PID it never asked for.

Two defects of this family have now been found and fixed one at a time, the second within weeks of
the first. The module relies on every one of its 54 handlers filling the buffer by convention. Nothing enforces
it, and nothing tells a handler's author that the obligation exists.

### The sole-writer fact this design rests on

`Xcp_FinalizeResPacket` (`source/Xcp.c:2665`) is the only code that assigns `SduLength` for the CTO
response buffer. Measured across `source/`:

| Site | What it is |
|:--|:--|
| `Xcp.c:2669` | inside `Xcp_FinalizeResPacket` itself |
| `Xcp.c:1371` | the `Xcp_Init` reset, to 0 |
| `Xcp.c:1378` | the `Xcp_Init` reset of the **event** buffer, to 0 |
| `Xcp_DaqRuntime.c:1012` | `Xcp_DaqTxPduInfo`, the DAQ path's own PDU |

Every response — including the block-transfer refill that runs at `TxConfirmation` time outside any
dispatch (`Xcp.c:2936`) — reaches `SduLength` through `Xcp_FinalizeResPacket`. Of its 59 call sites,
57 pass `&Xcp_Internal.cto_response.pdu_info` directly and the other 2 are the fill helpers
`Xcp_FillErrorPacket` and `Xcp_FillErrorPacketWithData` forwarding their own parameter, whose every
caller passes that same buffer (`Xcp_FillGenericErrorPacket` reaches it through the latter). The event buffer is built inline
in `Xcp_MainFunction` and never finalized.

So D18's "every site that sets `SduLength`" is, for the CTO buffer, exactly one site. That is what
makes a central invariant cheap here rather than a 54-handler contract change.

**No call site can finalize at 0 except one.** Of the 59 length arguments, 56 are literal constants
(`0x01u` × 28, `0x08u` × 13, `0x02u` × 5, `0x03u` × 4, `0x06u` × 3, `0x07u` × 2, `0x04u` × 1) and two
are computed forms that cannot reach 0 — the block transfer's `0x01u + ...` and
`Xcp_FillErrorPacketWithData`'s `(PduLengthType)(0x02u + dataLength)`. The 59th is
`Xcp_Internal.cto_response.pdu_info.SduLength`, forwarded by `USER_CMD` from the integrator's
callback and therefore not statically bounded below. That one is discussed in DD136 and is a defect
rather than a counter-example to the sentinel.

## 2. What the specification says

**§1.1.3.3 defines the channel.** 1.0/§1.1.3.3 and 1.1/§1.1.3.3, identically: "If the error code is
0x31 = ERR_GENERIC, the error packet contains an implementation specific slave device error code as
WORD as additional information." A module that failed to produce a response is precisely an
implementation-specific slave device error, and this is the mechanism the specification provides for
saying so. D17 built it in this module; DD129 added the sixth site.

**§1.7.3.1 gives it a severity.** `ERR_GENERIC` `0x31`, "Generic error.", severity **S2** —
"Resolvable Error" per 1.0/§1.7.3's severity table. Where the Error Handling Matrix does list
`ERR_GENERIC` (1.0/§1.7.3.2.5's `PROGRAM_START` and `PROGRAM_VERIFY` rows) the prescribed master
Action is **"restart session"** with no Pre-Action. That is the right outcome for a slave that has
just failed to produce a response: its state is one the master should stop trusting.

**§1.7.3 defines the master's fallback for an off-row code.** 1.0/§1.7.3 line 5199, 1.1 OCR line
6302, word for word the same:

> If for a specific CMD, the specific ERR is not mentioned in the "Error Handling Matrix", the
> master has to check the Severity of this ERR in the "Table of Error Codes" and decide about an
> appropriate reaction.

### DD132 — "deliberate deviation" is the wrong word, in four places

That passage corrects a premise this project has carried since SP4. DD57 (`PROGRAM_RESET`), DD76
(`UNLOCK`) and DD130 (`USER_CMD`) each record answering `ERR_GENERIC` where §1.7.3.2.1's row for
that command does not list it, and each calls it "a deliberate deviation". The comment added to
`Xcp_DTOCmdStdUserCmd` on 2026-09-16 repeats the claim.

It overstates the cost. §1.7.3 anticipates an off-row code and tells the master exactly what to do
with one: fall back to the severity in the Table of Error Codes. The behaviour is inside the
protocol, not outside it. What an off-row code actually costs is narrower and worth stating
plainly — the master gets severity-level guidance ("resolvable error", and for `ERR_GENERIC` in
practice a session restart) instead of the specific Pre-Action/Action pair a listed code would
carry. That is a real trade-off, and none of the four choices becomes wrong under the correct
reading. Only the word does.

All four sites are corrected on this branch.

## 3. The design

### DD133 — detection by sentinel, not by a new flag

`Xcp_CanIfRxIndication` sets `Xcp_Internal.cto_response.pdu_info.SduLength = 0` once, at the top of
the CTO processing arm, before any branch that can fill the buffer. Because `Xcp_FinalizeResPacket`
is the buffer's sole `SduLength` writer (§1) and no legal response finalizes at 0, a surviving 0
after processing means nothing wrote a response.

The clear is placed at the top of the arm rather than immediately before the dispatch call
deliberately. Every path that can reach a transmission then falls under the invariant — the
pending-command `ERR_CMD_BUSY` gate, `ERR_PGM_ACTIVE`, `ERR_CMD_SYNTAX`, `ERR_ACCESS_LOCKED`, the
disabled-command `ERR_CMD_UNKNOWN` arm, and the dispatched handler. All of those already fill, so
none should trip the guard; the point is that they are covered by construction rather than by
having been checked once.

No new struct field. This follows the dispatcher's own established style: the `last_pid` guard reads
`SduDataPtr[0] != XCP_PID_ERROR` to decide whether a handler refused, and its comment argues
explicitly against "a separate flag threaded through every one of `Xcp_PIDTable`'s handlers". An
explicit `written` boolean was the alternative; it was rejected because `Xcp_FinalizeResPacket`
takes a generic `PduInfoType *` and would have to pointer-compare against
`&Xcp_Internal.cto_response.pdu_info` before setting module-global state, buying explicitness with a
layering wrinkle to encode a fact `SduLength == 0` already encodes.

**What this rests on, stated so it can be broken loudly:** no legal response finalizes at length 0.
§4 pins it with a test.

### DD134 — one place sets the transmit flag

The three sites that assign `successful_transmission_pending` from `response_expected` collapse into
one internal helper. It is the only code that ever sets that flag TRUE, and it carries the check:

- `response_expected == FALSE` — set nothing, as today. The deferred PGM handlers rely on this.
- `response_expected == TRUE` and `SduLength != 0` — queue, as today.
- `response_expected == TRUE` and `SduLength == 0` — the invariant is broken. Fill
  `ERR_GENERIC` with `XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN`, report
  `XCP_E_RESPONSE_NOT_WRITTEN` to Det, and queue that.

Today the reason those three assignments must agree is implicit, and a fourth could be added without
noticing. After this, there is one.

The guard is self-satisfying: the packet it fills goes through `Xcp_FinalizeResPacket` like any
other, so the buffer is valid by the time it is queued.

### DD135 — the new identifiers

`XCP_GENERIC_DETAIL_RESPONSE_NOT_WRITTEN` = `0x0007`, the next free detail value after DD129's
`0x0006`.

`XCP_E_RESPONSE_NOT_WRITTEN` = `0x0B`, the next free Det id after DD131's `0x0A`. Low values are not
refilled: D18's Finding 3 recorded that `XCP_E_EVENT_QUEUE_FULL` (`0x04`) already collides with
AUTOSAR's `XCP_E_INIT_FAILED`, and DD131 chose `0x0A` rather than continue filling downward for that
reason.

### DD136 — the guard is reachable, which is why it is not a dead branch

D18 declined to add a runtime branch for the `MAX_CTO` floor because none could ever be entered, and
DD126 records that this project has deleted two such guards before. That precedent does not apply
here, and the difference is worth stating rather than assumed.

`Xcp_DTOCmdStdUserCmd` finalizes at whatever length the integrator's callback set
(`source/Xcp_Std.c:420`). DD129 added the **upper** bound against `maxCto`. There is no lower bound.
A callback that sets `SduLength = 0` and returns `E_OK` therefore reaches
`Xcp_FinalizeResPacket(0, ...)` today, and the result is queued and transmitted at `SduLength` 0 — a
frame from which a master cannot read even a PID.

So the guard has a live path to it that requires no handler defect at all, only an integrator
mistake, and §4 exercises exactly that path. Two consequences follow. The branch is not dead code by
the DD126 test. And `USER_CMD` acquires the lower bound it was missing, for free — a zero-length
callback response becomes a defined `ERR_GENERIC` rather than an unreadable frame. That is a third
defect in this handler, after D18's own and Finding 4's, found while designing the guard and closed
by it without additional code.

## 4. Testing

**The guard fires, end to end.** `USER_CMD` with a callback that sets `SduLength = 0` and returns
`E_OK`. Assert the wire carries `FE 31` with detail WORD `0x0007` at `SduLength` 4, and that Det
receives `XCP_E_RESPONSE_NOT_WRITTEN`. This uses a real integrator-reachable path; no test seam is
added to production code to make the guard testable.

**The guard stays silent on every legal path.** A sweep driving every PID in `Xcp_PIDTable` through a
connected session, asserting that nothing transmitted is the `RESPONSE_NOT_WRITTEN` packet. This is
the per-path audit that the per-function sweep on the Finding 4 branch could not provide: that sweep
counted fill calls per function, which established that `USER_CMD`'s branch was broken but not that
the other handlers are sound. If a path does return "respond" having written nothing, this finds it,
and it is fixed on this branch. If none does, the design records that the guard currently protects
against the `USER_CMD` zero-length case and against future regressions, and nothing else — which is
the honest claim and the one DD136 depends on.

**The sentinel's premise is pinned.** A test asserting that no legal response finalizes at length 0,
so a future `Xcp_FinalizeResPacket(0, ...)` on a valid path breaks a test rather than silently
turning the guard into a source of false refusals.

**Regression cover for the two defects that motivated this.** Both already have tests — D2's in the
SP1 suite, Finding 4's in `test/user_cmd_test.py` — and both must stay green unchanged. Finding 4's
in particular must keep passing for the reason it was written: it asserts the wire, which the older
neighbouring test did not, which is how that defect survived.

## 5. Out of scope

The **event** buffer (`Xcp_Internal.event`) and the **DAQ** path have their own transmit flags and
their own fill paths, neither of which goes through `Xcp_FinalizeResPacket`. Whether they carry an
analogous hazard is a separate question this design does not answer.

The four remaining findings of `2026-09-15-xcp-max-cto-bound-d18-design.md` §5 — the
`MAX_CTO mod AG` build-time check, the `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` matrix rows, the
`XCP_E_EVENT_QUEUE_FULL` id collision, and the absent `max_cto` ceiling — are untouched here.
DD135 depends on the third only for its choice of value.

# Service request codes (SERV) — SP5's last buildable residue

**Scope:** `SERV_RESET` and `SERV_TEXT` (XCP Part 2 §1.3), and the user-data path the event queue
half-built and never finished. Closes the `SERV_*` row of the roadmap's §2.6. The interleaved
communication model, SP5's other remaining item, is untouched and stays unbuilt.

**Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. §1.1.3.5,
§1.2 and §1.3 were read with `pdftotext -layout` on 1.0 (lines 830, 945 and 995); 1.1 carries the
same tables.

---

## 1. What exists, and what does not

`Xcp_EventQueuePush` (`source/Xcp.c`) already takes everything a SERV packet needs:

```c
Std_ReturnType Xcp_EventQueuePush(Xcp_EventQueueType *pEventQueue, uint8 packetID, uint8 eventCode,
                                  const uint8 *pUserData, uint32 userDataSize);
```

It stores all four fields in the queue entry. `source/Xcp_Internal.h:189` already documents 0xFC as
SERV. So the queue was built for this.

**Half of it is dead.** `Xcp_EventQueueGet` returns only `packetID` and `eventCode`;
`userData` is written by the push, zeroed at `Xcp_Init`, and **read nowhere in the module**. Every
caller passes `XCP_PID_EVENT`, so the packet id has never varied either. What is missing is entirely
on the read side.

Three callers pass a status byte that goes nowhere: `EV_STORE_CAL` (`Xcp.c:1600`), `EV_STORE_DAQ`
(`:1683`) and `EV_CLEAR_DAQ` (`:1747`) each push one byte of `userData`.

### The specification gives those bytes nowhere to go

§1.2 defines the event information column for no code this module implements. `EV_RESUME_MODE`,
`EV_CLEAR_DAQ`, `EV_STORE_DAQ`, `EV_STORE_CAL`, `EV_CMD_PENDING` and `EV_DAQ_OVERLOAD` are all pure
two-byte notifications. Only `EV_USER` (0xFE) and `EV_TRANSPORT` (0xFF) are described as carriers,
and the module implements neither.

So the user-data path is needed for `SERV_TEXT` alone, and the three status bytes must stop being
pushed rather than start being transmitted — see DD141.

*Noted and not proposed:* §1.2 also defines `EV_SESSION_TERMINATED` (0x07, severity S3), which this
module implements nowhere. That is a separate question about whether the slave ever terminates a
session autonomously, and this design does not answer it.

## 2. What the specification requires

§1.1.3.5 lays the SERV packet out:

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | Packet Identifier = SERV 0xFC |
| 1 | BYTE | Service request code |
| 2..MAX_CTO-1 | BYTE | Optional service request data |

§1.3 defines two codes and two constraints that shape the API:

- `SERV_RESET` (0x00) — "Slave requesting to be reset".
- `SERV_TEXT` (0x01) — "The remaining data bytes of the packet contain plain ASCII text. The line
  separator is LF or CR/LF. The text must be null terminated to indicate the end of the overall
  packet."
- "The implementation is optional for the slave device, but mandatory for the master device."
- "Service request packets sent from the slave device to the master device are not acknowledged,
  therefore the transmission is not guaranteed."

That last sentence is why DD139 reuses the existing queue rather than giving SERV a priority path of
its own: the specification does not promise delivery, so contention with events is not a
correctness problem.

## 3. The design

### DD138 — finish the read side rather than add a second queue

`Xcp_EventQueueGet` gains two outputs it already has in hand:

```c
static Std_ReturnType Xcp_EventQueueGet(Xcp_EventQueueType *pEventQueue, uint8 *pPacketID,
                                        uint8 *pEventCode, const uint8 **ppUserData,
                                        uint32 *pUserDataSize);
```

`uint32` for the size, matching `Xcp_EventType.userDataSize` (`interface/Xcp_Types.h:690`) and
`Xcp_EventQueuePush`'s own parameter rather than narrowing at the boundary. The value is bounded far
below that by `XCP_EVENT_USER_DATA_SIZE`, which the push already enforces, but a getter that
narrowed what the setter widened would be a conversion for a reader to reason about and a lint to
flag. The `0x02u + userDataSize` sum is computed in that width and cast once, at the
`Xcp_FinalizeResPacket` call, where `PduLengthType` is what the callee wants.

It returns a pointer into the queue entry rather than copying: the entry is not released until
`Xcp_EventQueuePop`, which `Xcp_CanIfTxConfirmation` calls only after the frame is confirmed.

`Xcp_TransmitOneFrame`'s event branch then copies `userDataSize` bytes to `SduDataPtr[2..]` and
calls `Xcp_FinalizeResPacket((PduLengthType)(0x02u + userDataSize), ...)`.

**This generalises a constant introduced days earlier.** The event branch gained
`Xcp_FinalizeResPacket(0x02u, ...)` on 2026-09-16, fixing a defect where `SduLength` was never set
at all and every `EV_*` packet went out as an empty frame. That fix was right and is not being
revised — but it hardcoded "an event is two bytes", true of every packet the module sent that day
and not true once SERV_TEXT exists. §4 pins the two-byte case so the generalisation cannot silently
change it.

The other caller, the `EV_CMD_PENDING` check in `Xcp_CanIfTxConfirmation` (`Xcp.c:2391`), passes the
new parameters and ignores them. It asks only which code is at the head of the queue.

### DD139 — one queue, not two

Rejected: a separate SERV queue with its own buffer, pending flag and transmit branch. It would
duplicate machinery to solve contention that §1.3 says is not a correctness concern, and SERV would
lose what the shared path already provides — ordering, `successful_transmission_pending` handling,
and the DD54 rate bound that ties `EV_CMD_PENDING` to TxConfirmation rather than to
`Xcp_MainFunction`'s period.

Also rejected: transmitting SERV directly, bypassing the queue. Two constant bytes for `SERV_RESET`
looks tempting, but it would still compete for the single transmit slot and would need its own
pending flag and confirmation handling — reimplementing the queue beside the queue.

### DD140 — two specific API functions

```c
Std_ReturnType Xcp_RequestServiceReset(void);
Std_ReturnType Xcp_SendServiceText(const uint8 *pText, uint16 length);
```

Both in `interface/Xcp.h`, shaped like `Xcp_ResumeComplete`: slave-initiated, `Std_ReturnType`, with
the contract in the doc comment.

A single generic `Xcp_SendServiceRequest(code, data, length)` was rejected. The two codes have
genuinely different contracts — `RESET` takes no data at all, `TEXT` requires null-terminated
ASCII — so one signature would document both and enforce neither, and it would let an integrator put
an undefined SERV code on the wire.

Taking `const char *` and calling `strlen` inside the module was also rejected: that is an unbounded
read over integrator-owned memory, the same trust D18's `USER_CMD` work deliberately pulled back
from.

`Xcp_RequestServiceReset` pushes `(XCP_PID_SERV, XCP_SERV_RESET, NULL_PTR, 0)` and changes no module
state. §1.3 makes it a request *to the master*; the slave resetting itself on its own say-so is not
what the code means.

`Xcp_SendServiceText` validates, then pushes `(XCP_PID_SERV, XCP_SERV_TEXT, pText, length)`:

| Check | Det id |
|:--|:--|
| `pText != NULL_PTR` | `XCP_E_PARAM_POINTER` (0x12) |
| `length > 0` | `XCP_E_SERVICE_TEXT_INVALID` (0x0D) |
| `pText[length - 1] == 0x00` (§1.3's terminator) | `XCP_E_SERVICE_TEXT_INVALID` |
| `0x02u + length <= maxCto` | `XCP_E_SERVICE_TEXT_INVALID` |
| `length <= XCP_EVENT_USER_DATA_SIZE` | `XCP_E_SERVICE_TEXT_INVALID` |

The last two are independent bounds, not one: `MAX_CTO` can be 255 while the queue entry holds 16
(`interface/Xcp_Types.h:35`).

One id for the four length faults rather than four: they are all "this is not a transmissible
SERV_TEXT payload", and this module adds ids per fault, not per check. `XCP_E_PARAM_POINTER` for the
null pointer because the `USER_CMD` path already uses it for the same class of mistake. 0x0D is the
next free value after 2026-09-16 moved `XCP_E_EVENT_QUEUE_FULL` to 0x0C.

**Refused, never truncated.** A truncated null-terminated string loses the terminator that §1.3
makes the end-of-packet marker, so a master cannot tell it was cut — the reasoning DD129 applied to
the `USER_CMD` response.

A full queue returns `E_NOT_OK` through the existing path, reported as
`XCP_E_EVENT_QUEUE_FULL` (0x0C).

### DD141 — the three dead pushes stop, in the same commit

`Xcp.c:1600`, `:1683` and `:1747` drop their status-byte argument for `(NULL_PTR, 0x00000000u)`,
which `Xcp_EventQueuePush` already documents tolerating (`Xcp_Internal.h:1091`).

This is not tidying and cannot be deferred. Those bytes are invisible today only because nothing
reads `userData`; the moment DD138's transmit branch honours `userDataSize`, three `EV_*` packets
would start carrying a status byte as event information §1.2 does not define for them. The cleanup
and the transmit change are one change.

### DD142 — no configuration flag

SERV is optional for a slave, and the natural way not to use it is not to call it. Gating the two
functions behind a generated macro would add a configuration key, a schema entry and a generator
branch to buy nothing.

A deliberate departure from how `programming.enabled` gates PGM, and the difference is the reason:
PGM's gate removes handlers *a master can reach from the bus*, so an ungated build would advertise
and answer commands it cannot perform. Nothing here is reachable from the bus at all — these are
integrator entry points, and an integrator that does not call them has disabled the feature.

### New identifiers

| Identifier | Value | Where | Why there |
|:--|:--|:--|:--|
| `XCP_PID_SERV` | `0xFCu` | `source/Xcp_Internal.h`, beside `XCP_PID_EVENT` (line 47) | the file documents 0xFC as SERV at line 189 and never defined it |
| `XCP_SERV_RESET` | `0x00u` | `source/Xcp_Internal.h`, beside the `XCP_EVENT_*` block (lines 51-54) | same shape, same file |
| `XCP_SERV_TEXT` | `0x01u` | as above | |
| `XCP_E_SERVICE_TEXT_INVALID` | `0x0Du` | `interface/Xcp.h`, after `XCP_E_EVENT_QUEUE_FULL` | Det ids are public |

## 4. Testing

**Wire behaviour.** `SERV_RESET` transmits `FC 00` at `SduLength` 2. `SERV_TEXT` transmits `FC 01`
followed by the text including its terminator, at `SduLength` `2 + length`.

**Every rejection asserts three things** — `E_NOT_OK` returned, the right Det id reported, and
**nothing transmitted**. The third is the one this codebase keeps having to learn: D18's Finding 4,
`GET_SEED`, `SHORT_UPLOAD` and the event frame length all survived because tests asserted payload
bytes without asserting what reached the transport, or asserted Det without asserting the wire.
Cases: null pointer, zero length, missing terminator, over-long against `MAX_CTO`, over-long against
`XCP_EVENT_USER_DATA_SIZE`.

**A full queue** returns `E_NOT_OK` and reports `XCP_E_EVENT_QUEUE_FULL`.

**The two-byte case is pinned.** An `EV_*` packet still transmits at exactly `SduLength` 2 once the
length is computed rather than constant. Without this, DD138's generalisation could regress the
2026-09-16 event-length fix silently, and DD141's cleanup could be forgotten without any test
objecting.

**Ordering.** A SERV and an EV queued together both reach the wire, in push order — the property
DD139 claims by reusing one queue rather than adding a second.

## 5. Out of scope

The **interleaved communication model** (§1.7.2.3), SP5's other remaining item. It needs a receipt
queue this module has never had, and the configuration that once advertised it was removed rather
than left as a flag pointing at nothing.

`EV_USER` (0xFE) and `EV_TRANSPORT` (0xFF), the two event codes §1.2 describes as carriers of
information data. DD138's transmit path would make them implementable, but neither has a caller
asking for it, and `EV_TRANSPORT`'s content is defined in Part 3, which is not in `docs/external`.

`EV_SESSION_TERMINATED` (0x07), noted in §1 above.

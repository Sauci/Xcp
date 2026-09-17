# EV_TIME_SYNC — transfer of an externally triggered timestamp

**Scope:** an integrator entry point that reports a timestamp captured on an external sync line, as
`EV_TIME_SYNC` (XCP Part 2 1.1/§1.8.8). Takes the roadmap's absent `EV_*` count from three to two.

**Reference revision:** 1.1 only. 1.0 has no §1.8 chapter and does not define this event.

---

## 0. How §1.8.8 was read

The OCR sidecar renders this section cleanly, but it renders §1.8.9's Info Type table with a row
missing, so it was checked against the PDF's own glyph-enciphered text layer using the
known-plaintext method of §0 of `2026-09-11-xcp-get-id-types-design.md`. **The two agree exactly**
— which is worth recording, because it is evidence the sidecar is unreliable per-table rather than
uniformly wrong, so checking it is per-table work and not a formality that can be skipped once.

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | Event = 0xFD |
| 1 | BYTE | Event Code = 0x08 |
| 2 | BYTE | reserved |
| 3 | BYTE | reserved |
| 4..7 | DWORD | Timestamp |

> The generation of a timestamp can be triggered by an external sync line. This can be used for
> highly accurate time synchronization with the master without relying on the GET_DAQ_CLOCK
> mechanism.
>
> The slave in this case with EV_TIME_SYNC sends its current time stamp to the master.
>
> The returned timestamp has the format specified by the GET_DAQ_RESOLUTION_INFO command.
>
> This event is not available if the slave does not support timestamps.

## 1. The ambiguity in §1.8.8, and which reading this takes

**The table and the prose disagree about the timestamp's width.** The table gives position 4 as a
`DWORD`. The prose says the timestamp "has the format specified by the GET_DAQ_RESOLUTION_INFO
command", and that command's `TIMESTAMP_MODE` byte encodes a **size** — 1, 2 or 4 bytes — as well as
a unit and a tick count. Read strictly, a slave configured for `ONE_BYTE` timestamps would send one
byte, contradicting the table.

This is a contradiction in the specification, not an artefact of how it was read: the enciphered
text layer prints `DWORD Timestamp` and the `GET_DAQ_RESOLUTION_INFO` sentence alike.

### DD154 — the table wins: always a DWORD

Every packet layout in Part 2 is specified by a table giving an explicit type at an explicit
position, and that is the form a slave has to serialise against. "Format" then reads naturally as
the unit and resolution `GET_DAQ_RESOLUTION_INFO` also carries — information the table cannot
express, and which a master genuinely does need in order to interpret the number.

A fixed width is also what makes the packet parseable on its own. A master that has not yet issued
`GET_DAQ_RESOLUTION_INFO` can still read an 8-byte `EV_TIME_SYNC`; under the other reading it could
not know how many bytes the event even occupies.

**Consequence, stated rather than left to be discovered:** a configuration using `ONE_BYTE` or
`TWO_BYTE` DAQ timestamps sends the **full 32-bit value** in this event, while its DAQ frames carry
a truncated one. The two widths differ, deliberately. Truncating the one packet whose stated purpose
is "highly accurate time synchronization" would defeat it, and `Xcp_GetDaqTimestamp()` returns a
`uint32` regardless of the configured wire size — the truncation is a DAQ framing decision
(`Xcp_DaqSampleOdt`), not a property of the clock.

### DD155 — the integrator supplies the timestamp

```c
Std_ReturnType Xcp_RaiseTimeSyncEvent(uint32 timestamp);
```

The alternative was `Xcp_RaiseTimeSyncEvent(void)`, with the module calling `Xcp_GetDaqTimestamp()`
itself. That was rejected, and the reason a first pass gave for preferring it turned out to be
wrong on inspection: **this module has no clock of its own.** `Xcp_GetDaqTimestamp()` is declared in
`Xcp_DaqTimestamp.h`, never defined in `source/`, and supplied by the integrator — the test harness
mocks it. Calling it does not give the module a trusted time base; it gives the module the
integrator's time base, read at a moment of the module's choosing.

So the trust is identical either way, and only the sampling instant differs: the module's call
happens after the sync line's edge, delayed by whatever the ISR-to-call path costs, while the
integrator can capture at the edge itself, often in hardware. §1.8.8 exists for "highly accurate
time synchronization"; sampling late defeats the point of the feature.

**What the module cannot check, and therefore documents.** A `uint32` carries no evidence of where
it came from. An integrator can pass a value from a different clock than `Xcp_GetDaqTimestamp()`
returns, in different units than `GET_DAQ_RESOLUTION_INFO` advertises, or captured at an earlier
edge, and the resulting packet is well-formed and silently wrong. There is no bound the module could
check that would not itself be invented.

That is a documentation obligation rather than a new hazard: all three failures are the integrator
being inconsistent with *themselves*, since they already own the clock function this event is meant
to agree with. The contract is stated on the function — same source, same units as
`Xcp_GetDaqTimestamp()` — in the same terms `user_cmd_function` and the checksum callback are
already trusted on.

### DD156 — gated at the declaration, not only the definition

§1.8.8: "This event is not available if the slave does not support timestamps." Both the declaration
in `interface/Xcp.h` and the definition sit inside `#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)`.

This departs from `Xcp_DTOCmdDaqGetDaqClock`, which `source/Xcp_Internal.h` declares unconditionally
and guards only at its definition, with a comment explaining that nothing references the declaration
when the feature is off. The difference is who calls it: that one is reached through `Xcp_PIDTable`,
which falls back to `Xcp_CmdNotImplemented` in such a build, so the declaration is genuinely dead.
This one is called by integrator code. A guarded declaration fails at their call site, naming their
file and line; an unguarded one fails at link time, naming neither.

### DD157 — a build-time check on the user-data capacity

The packet needs six bytes of information data. `XCP_EVENT_USER_DATA_SIZE` is an overridable
`#ifndef` (`interface/Xcp_Types.h`, default 16), so a build can set it below that.

`Xcp_EventQueuePush` already refuses a `userDataSize` above the capacity and returns `E_NOT_OK`,
which this module's callers report as `XCP_E_EVENT_QUEUE_FULL`. That would be a lie: the queue is
not full, the entry is too small, and an integrator would debug the wrong thing. An `#error` under
the same feature gate states it at build time instead, where the macro that causes it is set.

## 2. Testing

- **The wire layout**, byte for byte against §1.8.8: `FD 08 00 00` then the DWORD, at `SduLength` 8,
  in both byte orders. The two reserved bytes asserted as `0x00`, not skipped.
- **The integrator's value is transmitted unmodified** — a distinctive value in, the same value out,
  with `Xcp_GetDaqTimestamp` asserted *not* called. That is DD155's whole point, and a test that
  only checked the bytes were plausible would pass if the module re-read the clock.
- **The full 32-bit value survives a `ONE_BYTE` configuration** (DD154's consequence), which is the
  test that would fail if someone later "fixed" the width to match `GET_DAQ_RESOLUTION_INFO`.
- **The queue-full branch**, with a test aimed at it — that shape has shipped uncovered twice in
  this module's recent history, and nothing reaches it by accident.

## 3. Out of scope

**Any sync-line handling.** The external trigger is the integrator's; this module provides the
entry point they call from it and takes no view on how the edge is detected.

**Reconciling `GET_DAQ_RESOLUTION_INFO`'s reported size with this event's width.** DD154 accepts
that the two differ for a truncating configuration. A master reading both sees an 8-byte
`EV_TIME_SYNC` and a narrower DAQ timestamp, which is what §1.8.8's table prescribes.

**`EV_SLEEP` (0x0A) and `EV_WAKE_UP` (0x0B)**, the roadmap's remaining absent event codes. §1.8.10
gives them a SLEEP mode — a connection sub-state threaded through every command path — rather than
a packet.

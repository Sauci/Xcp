# SP4c — sectors, formats and verification — design

**Date:** 2026-09-08
**Status:** design, approved in outline; not yet planned or implemented
**Completes:** SP4, the PGM command group. Predecessors:
`2026-09-06-xcp-pgm-sp4a-design.md` (DD49–DD61, the programming session and the polled callback
contract) and `2026-09-07-xcp-pgm-sp4b-design.md` (DD62–DD69, clear and program in absolute access
mode).

Three commands, and they are unequal. `PROGRAM_VERIFY` is a pass-through to the integrator.
`GET_SECTOR_INFO` is read-only reporting over a configuration model that does not exist yet.
`PROGRAM_FORMAT` carries the weight, because its **functional access mode changes what the MTA
means** — and therefore what the integrator is being handed.

---

## 0. Specification numbering

Every citation below was read in the 1.0 PDF via `pdftotext -layout` before being written down.
This section exists because repeated citation errors were found on the two immediately preceding
branches, several of which had reached shipped source comments before anyone checked them.

| Cited as | Actual title |
|---|---|
| §1.6.5.2.1 | Get general information on PGM processor (`GET_PGM_PROCESSOR_INFO`) |
| §1.6.5.2.2 | Get specific information for a SECTOR (`GET_SECTOR_INFO`) |
| §1.6.5.2.3 | Prepare non-volatile memory programming (`PROGRAM_PREPARE`) |
| §1.6.5.2.4 | Set data format before programming (`PROGRAM_FORMAT`) |
| §1.6.5.2.7 | Program Verify (`PROGRAM_VERIFY`) |
| §1.6.5.1.2 | Clear a part of non-volatile memory (`PROGRAM_CLEAR`) |
| §1.6.5.1.3 | Program a non-volatile memory segment (`PROGRAM`) |
| §1.7.3.2.5 | Non-volatile memory programming commands (PGM) — the error/pre-action table |

**§1.6.5.1.2 and §1.6.5.1.3 are in this list because an earlier draft of this design did not read
them, and was wrong in three decisions as a result.** They define what functional access mode
actually *means* for clearing and programming; the three SP4c command sections alone do not. Both
revisions were then re-read line by line for the corrections below, and where 1.0 and 1.1 differ it
is now recorded rather than silently resolved.

---

## 1. What already exists, and what is missing

All three PIDs already have rows in `Xcp_PIDToCmdGroupTable` (each `MASK_PGM`) and in
`Xcp_CTOErrorMatrix`. None has a handler, a configuration, or an API enable flag. The wire-visible
state today:

- `GET_PGM_PROCESSOR_INFO` reports `MAX_SECTOR = 0`, hardcoded — SP4b's DD68 called that "truthful
  for a slave with no sector description".
- `PGM_PROPERTIES` reports `ABSOLUTE_MODE` only.
- `XCP_PGM_PROPERTIES_FUNCTIONAL_MODE` (bit 1) is **already defined** and unused.

---

## 2. Design decisions

### DD84 — functional access mode gets its own callbacks

`PROGRAM_FORMAT`'s access method byte (§1.6.5.2.4) selects between:

> `0x00` Absolute Access Mode — The MTA uses physical addresses
> `0x01` Functional Access Mode — **The MTA functions as a block sequence number of the new flash
> content file**

SP4b's shipped callbacks take `void *address`. Under functional mode the MTA is not an address, so
the integrator must be told which it is receiving. Two new callbacks, config-gated exactly like the
existing five:

```c
Std_ReturnType Xcp_ProgramClearFunctional(uint32 clearRange, uint8 *pStatusCode);
Std_ReturnType Xcp_ProgramWriteFunctional(uint32 blockSequenceCounter, const uint8 *pData,
                                          uint16 length, uint8 *pStatusCode);
```

**The clear variant takes no address and no counter, and that is not an omission.** §1.6.5.1.2 says
in both revisions that under functional mode "the MTA has no influence on the clearing
functionality", and the clear range stops being a length and becomes an **area bitmask**:
`0x00000001` all calibration data areas, `0x00000002` all code areas (excluding boot),
`0x00000004` NVRAM areas, `0x00000008…0x00000080` reserved, `0x00000100…0xFFFFFF00` user defined.
Passing an address there would invent a parameter the protocol does not carry.

**The rejected alternative, and why the obvious precedent does not apply.** Adding an access-mode
parameter to the existing `Xcp_ProgramClear`/`Xcp_ProgramWrite` would give every shipped integrator
a compile error, which is the argument DD78 made for renaming `protection_status`. That precedent
does not transfer. DD78 renamed a field **because its meaning changed for every existing reader** —
the compile error was the point. Here absolute mode is completely unchanged for anyone who never
enables functional mode, so forcing every integrator to edit signatures they will keep using
identically is churn, not safety.

Separate callbacks also get the property DD78 was actually after: **the wrong thing becomes
unrepresentable.** An integrator cannot receive a block sequence number in a `void *`, because the
parameter is a `uint32`. A mode parameter leaves `void *address` carrying a sequence number in
functional mode, which is the type lie; fixing that inside it means two mutually exclusive
parameters, which is a tagged union with extra steps — and unions sit badly here (MISRA C 2012
Rule 19.2 advises against them).

`Xcp_ProgramPrepare` gets **no** functional variant. §1.6.5.2.3 has its MTA pointing at "the begin
of the volatile memory location where the code will be stored" — staging RAM, not flash — so the
functional/absolute distinction does not arise for it. Recorded because its signature also takes
`void *address` and the omission would otherwise look like an oversight.

### DD85 — the format is session state with a stated lifetime

`Xcp_Internal.pgm_format` holds the four bytes `PROGRAM_FORMAT` carries: compression, encryption,
programming method, access method. Only the access method changes module behaviour; the other three
are validated, stored, and reported to the integrator, because §1.6.5.2.4 is explicit that "the
master will not perform the reformatting" — it passes values through from the A2L description, and
the slave is what must honour or refuse them.

**The lifetime is a recorded deviation, because the specification is loose here.** §1.6.5.2.4 says
the format "is valid till end of this sequence" and that "the sequence will be terminated by other
commands **e.g.** `SET_MTA`". That "e.g." names one terminator and gestures at others without
enumerating them.

The format resets to defaults on `SET_MTA`, on `PROGRAM_RESET`, and at `CONNECT`, **and nothing
else**. Guessing at a wider set would mean silently discarding a format the master believes is still
in force — the more dangerous direction, since a master that expects a wider reset can always
re-send `PROGRAM_FORMAT`, while one whose format was dropped underneath it programs with the wrong
decoding.

### DD86 — the Block Sequence Counter is module-maintained state, not a value the master sets

**This decision replaces an earlier draft that was simply wrong.** That draft had `SET_MTA` supply
the block sequence number, with `Xcp_Pgm.c` reinterpreting `memory_transfer.address` at the point of
use. §1.6.5.1.3 says otherwise, identically in both revisions:

> The MTA works as a Block Sequence Counter and it is counted inside the master and the server. […]
> The Block Sequence Counter of the server **shall be initialized to one (1) when receiving a
> PROGRAM_FORMAT request message**. This means that the first PROGRAM request message following the
> PROGRAM_FORMAT request message starts with a Block Sequence Counter of one (1). Its value is
> **incremented by 1 for each subsequent data transfer request**. At the maximum value the Block
> Sequence Counter **rolls over and starts at 0x00** with the next data transfer request message.

So it is state the slave *counts*, with a specified initial value, increment point and rollover —
not a number the master transmits. `Xcp_Internal.pgm_block_sequence_counter`:

| Event | Effect |
|---|---|
| `PROGRAM_FORMAT` received | set to `1` |
| each data transfer request (`PROGRAM`, `PROGRAM_NEXT`, `PROGRAM_MAX`) | incremented by 1 |
| at maximum | rolls over to `0x00` |
| `PROGRAM_RESET`, `CONNECT` | reset with the rest of the programming session |

Its purpose is the one the specification gives it — "an improved error handling in case a
programming service fails during a sequence of multiple programming requests". Both sides count
independently, so a divergence is detectable. The module passes its own value to
`Xcp_ProgramWriteFunctional` so the integrator can cross-check rather than re-derive it.

**One ambiguity is recorded rather than resolved silently: the counter's width.** The text says the
MTA works as the counter, which would make it 32-bit, but writes the rollover value as `0x00`, which
reads byte-sized. Neither revision states a width. This design takes **`uint32`**, matching the MTA
the sentence names, because that is the only width the specification actually mentions; a byte-wide
counter would be a narrowing nothing in the text requires. Anyone finding a master that disagrees
should read this entry first.

**`SET_MTA` is untouched, and now for a simpler reason than the earlier draft gave**: in functional
mode the MTA carries no address the module needs — §1.6.5.1.3 says "the ECU software knows the start
address for the new flash content automatically. It depends on the PROGRAM_CLEAR command." The
module neither reads nor writes `memory_transfer.address` on the functional programming path.

### DD87 — the sector configuration model

The configuration gains a `sectors` array; each entry carries what §1.6.5.2.2's response reports:

| Field | Wire position | Note |
|---|---|---|
| `start_address` | bytes 4–7, mode 0 | |
| `length` | bytes 4–7, mode 1 | **in bytes** — see below |
| `clear_sequence_number` | byte 1 | |
| `program_sequence_number` | byte 2 | |
| `programming_method` | byte 3 | |

The two sequence numbers are integrator data the module reports verbatim, neither derived nor
enforced: §1.6.5.2.2 makes them the order in which the master must clear and program, and its own
examples show those orders differing from each other and from sector order — clear 0,1,2 while
programming 5,4,3.

**The length's unit differs between revisions, and this design follows 1.1.** 1.0 gives the mode-1
value as "Length of this SECTOR **[AG]**". 1.1 says the command "returns **in bytes** the length of
this SECTOR", and adds a constraint 1.0 does not have: "The following rule applies: Length mod
AG = 0." Bytes is taken, because 1.1 is the later revision and because that added rule only needs
stating if the value is in bytes — in AG units it would be trivially true. The two agree whenever
AG is BYTE, which is where this suite tests almost exclusively, so the divergence would otherwise
go unnoticed until someone built at AG = WORD. Generation validates `length mod AG == 0` and refuses
otherwise, turning 1.1's rule into something the build enforces rather than something a comment
asserts.

**`MAX_SECTOR` stops being hardcoded and becomes the array length.** `GET_PGM_PROCESSOR_INFO` and
`GET_SECTOR_INFO` must agree about how many sectors exist, or a master enumerating them walks off
the end. This is a cross-command invariant, and §4 pins it.

### DD88 — an invalid sector answers `ERR_SEGMENT_NOT_VALID`, not the prose's `ERR_OUT_OF_RANGE`

The specification contradicts itself. §1.6.5.2.2's prose says "If the specified SECTOR is not
available, ERR_OUT_OF_RANGE will be returned." §1.7.3.2.5's row for that same command lists
`ERR_CMD_BUSY`, `ERR_CMD_UNKNOWN`, `ERR_CMD_SYNTAX`, `ERR_MODE_NOT_VALID` and
`ERR_SEGMENT_NOT_VALID` — and **no `ERR_OUT_OF_RANGE`**.

DD65 settled this class in SP4b, on `PROGRAM_MAX`'s self-contradicting length: *where a listed code
fits, use it and take no deviation.* `ERR_SEGMENT_NOT_VALID` fits — in a command whose only
parameters are a mode and a sector number, it can mean nothing else — and an invalid mode byte gets
`ERR_MODE_NOT_VALID` from the same row. The module's own `Xcp_CTOErrorMatrix` row already encodes
the table rather than the prose, so whoever built it read §1.7.3.2.5.

**A consequence, not a new decision:** SP4b's DD68 comment in `source/Xcp_Pgm.c` predicts that
`GET_SECTOR_INFO` "answers ERR_OUT_OF_RANGE for a sector that is not available (1.0/1.6.5.2.2)".
That becomes false the moment this ships, and is corrected in the same change.

### DD89 — `PROGRAM_FORMAT` accepts exactly what `GET_PGM_PROCESSOR_INFO` advertises

`PGM_PROPERTIES` (§1.6.5.2.1) already carries `COMPRESSION_SUPPORTED`/`REQUIRED`,
`ENCRYPTION_SUPPORTED`/`REQUIRED`, `NON_SEQ_PGM_SUPPORTED`/`REQUIRED` and both access-mode bits. The
rule is therefore mechanical: a non-default value is accepted only if the corresponding property is
advertised, and refused `ERR_OUT_OF_RANGE` otherwise — which **is** in `PROGRAM_FORMAT`'s
§1.7.3.2.5 row, so no deviation is taken.

This closes the advertised-versus-accepted gap by construction rather than by discipline. That
matters because this module's recurring defect is exactly its inverse: `CONNECT` advertising flash
programming that answered `ERR_CMD_UNKNOWN` (D10), and a STIM resource advertised but gated on no
command (DD41/DD48, still refused at generation).

The user-defined ranges (`0x80…0xFF`) follow the same rule. The module cannot know what compression
`0x81` means, so it checks only that the capability is advertised and lets the integrator judge the
value (DD91).

### DD90 — a `REQUIRED` property makes a missing `PROGRAM_FORMAT` an `ERR_SEQUENCE`

§1.6.5.2.4 states it directly: "If modified data transmission is expected by the slave and no
PROGRAM_FORMAT command is transmitted, the slave responds with ERR_SEQUENCE."

So with any `REQUIRED` bit configured, a `PROGRAM`, `PROGRAM_MAX` or `PROGRAM_NEXT` arriving with no
preceding `PROGRAM_FORMAT` in the current sequence is refused `ERR_SEQUENCE` — listed in all three
rows. A concrete behaviour, not an inference, and §4 pins it.

### DD91 — `Xcp_ProgramFormat` is synchronous; `Xcp_ProgramVerify` is polled

Two new callbacks beyond DD84's pair, and they differ deliberately:

```c
Std_ReturnType Xcp_ProgramFormat(uint8 compressionMethod, uint8 encryptionMethod,
                                 uint8 programmingMethod, uint8 accessMethod, uint8 *pStatusCode);
Std_ReturnType Xcp_ProgramVerify(uint8 verificationMode, uint16 verificationType,
                                 uint32 verificationValue, uint8 *pStatusCode);
```

`Xcp_ProgramFormat` is **synchronous**, breaking SP4a's polled pattern on purpose: the other five
wrap flash operations that take real time, and this sets four bytes. The integrator must be told the
compression and encryption methods or it cannot decode what `Xcp_ProgramWrite` hands it, and for
user-defined values only the integrator can judge whether it can honour them. The module performs
DD89's structural check first, then delegates.

`Xcp_ProgramVerify` **is** polled, for the opposite reason — checking whether new flash contents fit
the rest of the flash is exactly the long-running work SP4a's contract exists for. The module makes
one structural check the specification permits: §1.6.5.2.7 marks verification types
`0x0008…0x0080` **reserved**, so a master setting those bits is refused `ERR_OUT_OF_RANGE` (in the
row). `ERR_VERIFY`, also in the row, is answered when the integrator reports failure.

### DD92 — `PGM_PROPERTIES` advertises functional mode exactly when it is available

The `FUNCTIONAL_MODE` bit is set if and only if DD84's callbacks are configured. Both directions are
defects: advertising an unimplemented mode is D10's class, and implementing an unadvertised one is
its inverse — a master reads `PGM_PROPERTIES` to decide what to use, so an unadvertised capability
is an unreachable one. Generation refuses functional mode enabled without the callbacks, matching
how this module already prevents unbuildable configurations.

### DD93 — `PROGRAM_CLEAR` carries its own access mode, independent of `PROGRAM_FORMAT`

`PROGRAM_CLEAR`'s byte 1 is a mode byte in both revisions (§1.6.5.1.2): `0x00` absolute (default),
`0x01` functional. It is **not** governed by `PROGRAM_FORMAT`'s access method, and the specification
says so outright in `PROGRAM_FORMAT`'s own table: *"It is possible to use different access modes for
clearing and programming."*

So a master may clear functionally and program absolutely, or the reverse, and the module must
support the combinations independently rather than deriving one from the other.

This makes the integration smaller than the earlier draft assumed. SP4b already implemented that
mode byte and refuses everything except `0x00` — deliberately, and with a test pinning it. SP4c's
work on the clear path is to implement the `0x01` branch that already exists and is already refused,
not to route clearing through format state.

Under functional clear the module validates the area bitmask before delegating: bits
`0x00000008…0x00000080` are **reserved** in both revisions, so a master setting them is refused
`ERR_OUT_OF_RANGE`, which is in `PROGRAM_CLEAR`'s §1.7.3.2.5 row. Everything else — the three defined
areas and the user-defined range — passes to `Xcp_ProgramClearFunctional`, since only the integrator
knows what a user-defined area means.

---

## 3. What this does not change

- The polled contract for SP4a's five callbacks, and DD84's two new ones.
- `Xcp_ProgramPrepare`'s signature (DD84).
- `SET_MTA` (DD86).
- Absolute access mode, which is unchanged end to end for any integrator that does not enable
  functional mode.
- The `resource_protection.data_stimulation` generation refusal (DD41/DD48), which is unrelated and
  still true.

---

## 4. Test strategy

Per-command tests, plus three layers that per-command tests cannot reach:

**Cross-command consistency**, which is where this phase can go quietly wrong.
`GET_PGM_PROCESSOR_INFO` and `GET_SECTOR_INFO` must agree on sector count, and `PGM_PROPERTIES` must
advertise functional mode exactly when the callbacks are configured — asserted in both directions,
per DD92.

**A property test over configuration**, matching the one SP4b built for its own gate-off invariance:
generate across the format-related settings and assert the module accepts exactly what it
advertises. That makes DD89's rule falsifiable rather than aspirational.

**An end-to-end functional-mode sequence** as the acceptance bar (§5.2), asserting that the
functional callbacks receive block sequence numbers **and that the absolute ones are never called** —
the second half being what distinguishes a working implementation from one that silently fell back.

Every fix mutation-verified, and **per term** for compound conditions rather than per outcome — the
rule that surfaced a genuinely missing test on the immediately preceding branch.

`Xcp_Internal` is not reachable from the CFFI harness, so every assertion observes transmitted bytes.

---

## 5. Acceptance

1. Each of the three commands has tests that fail before its handler exists and pass after.
2. **The end-to-end proof:** with functional access mode configured, `CONNECT` → `GET_SEED`/`UNLOCK`
   → `PROGRAM_START` → `PROGRAM_FORMAT(access = 0x01)` → `PROGRAM_CLEAR(mode = 0x01)` → `PROGRAM` →
   `PROGRAM_RESET` completes with every step answering positively, `Xcp_ProgramWriteFunctional` and
   `Xcp_ProgramClearFunctional` receiving the calls, and the absolute callbacks never invoked.
3. A second end-to-end run **mixes the modes** — functional clear with absolute programming — since
   §1.6.5.2.4 permits it explicitly (DD93) and nothing else in the suite would catch the two paths
   being wrongly coupled.
4. `MAX_SECTOR` agreement between `GET_PGM_PROCESSOR_INFO` and `GET_SECTOR_INFO` is pinned by a test
   that fails if either drifts.
5. The Block Sequence Counter's three specified behaviours are pinned **separately**: initialised to
   `1` by `PROGRAM_FORMAT`, incremented once per data transfer request, and rolling over to `0x00`
   at maximum (DD86). A test checking only the first would pass against a counter that never
   increments.
6. `GET_SECTOR_INFO`'s mode-1 length is asserted at an AG **wider than BYTE**, where 1.0 and 1.1
   diverge (DD87). At AG = BYTE the two readings are indistinguishable and the test would prove
   nothing.
7. DD89's accept-only-what-you-advertise rule is pinned by the property test, in both directions.
8. DD90's `ERR_SEQUENCE` on a missing `PROGRAM_FORMAT` under a `REQUIRED` property is pinned.
9. Mutation verifications carried out and recorded, each naming the test that failed.
10. `./test.sh` green in the CI container, both ctest targets, on a clean build tree.
11. SP4b's DD68 comment is corrected (DD88), and no other comment predicts SP4c behaviour that
    differs from what shipped.

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
| §1.7.3.2.5 | Non-volatile memory programming commands (PGM) — the error/pre-action table |

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
Std_ReturnType Xcp_ProgramClearFunctional(uint32 blockSequenceNumber, uint32 clearRange, uint8 *pStatusCode);
Std_ReturnType Xcp_ProgramWriteFunctional(uint32 blockSequenceNumber, const uint8 *pData, uint16 length, uint8 *pStatusCode);
```

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

### DD86 — `SET_MTA` is not modified; PGM reinterprets at the point of use

§1.6.5.2.4 lists `SET_MTA` among `PROGRAM_FORMAT`'s affected commands, so under functional mode the
value it sets is a block sequence number. `Xcp_DTOCmdStdSetMta` (`source/Xcp_Std.c`) already writes
the raw 32-bit wire value into `memory_transfer.address`, so those same bits are the sequence
number; nothing about SET_MTA needs to change.

`source/Xcp_Pgm.c` converts them back to `uint32` at the point of call, and **only there**. This is
DD63's rule — *a command group may not write shared state whose readers live outside its own file* —
honoured in the direction that matters: PGM writes nothing shared, and the reinterpretation has
exactly one reader, in one file. Putting an access-mode fork inside `SET_MTA` would do the opposite,
making a STD command's behaviour depend on PGM state, which is how the SP4b disclosure happened.

### DD87 — the sector configuration model

The configuration gains a `sectors` array; each entry carries what §1.6.5.2.2's response reports:

| Field | Wire position | Note |
|---|---|---|
| `start_address` | bytes 4–7, mode 0 | |
| `length` | bytes 4–7, mode 1 | in AG |
| `clear_sequence_number` | byte 1 | |
| `program_sequence_number` | byte 2 | |
| `programming_method` | byte 3 | |

The two sequence numbers are integrator data the module reports verbatim, neither derived nor
enforced: §1.6.5.2.2 makes them the order in which the master must clear and program, and its own
examples show those orders differing from each other and from sector order — clear 0,1,2 while
programming 5,4,3.

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
   → `PROGRAM_START` → `PROGRAM_FORMAT(access = 0x01)` → `PROGRAM_CLEAR` → `PROGRAM` →
   `PROGRAM_RESET` completes with every step answering positively, `Xcp_ProgramWriteFunctional`
   receiving the block sequence numbers, and `Xcp_ProgramWrite` never called.
3. `MAX_SECTOR` agreement between `GET_PGM_PROCESSOR_INFO` and `GET_SECTOR_INFO` is pinned by a test
   that fails if either drifts.
4. DD89's accept-only-what-you-advertise rule is pinned by the property test, both directions.
5. DD90's `ERR_SEQUENCE` on a missing `PROGRAM_FORMAT` under a `REQUIRED` property is pinned.
6. Mutation verifications carried out and recorded, each naming the test that failed.
7. `./test.sh` green in the CI container, both ctest targets, on a clean build tree.
8. SP4b's DD68 comment is corrected (DD88), and no other comment predicts SP4c behaviour that
   differs from what shipped.

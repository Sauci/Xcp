# MAX_CTO's unenforced payload bound — closing D18

**Defect:** D18 — no code in `source/` enforces the `MAX_CTO` bound on a response payload
(`docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` §3).

**Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. Every
citation carries its revision prefix. 1.1's citations here were read from the PDF's **own text
layer**, deciphered by the known-plaintext method of §0 of
`2026-09-11-xcp-get-id-types-design.md`, because the OCR sidecar misaligns exactly the tables this
design depends on — the §1.1.3.3 position column and the §1.7.3.2.1 error matrix.

---

## 1. What is wrong, and what the specification says

1.1/§1.1.3.3 lays the error packet out in three rows:

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | Packet Identifier = ERR 0xFE |
| 1 | BYTE | Error code |
| 2..MAX_CTO-1 | BYTE | Optional error information data |

1.0/§1.1.3.3 is identical. 1.1/§1.6.1.1.1 defines the bound itself — "MAX_CTO is the maximum CTO
packet size in bytes" — so a response whose length exceeds `MAX_CTO` has no position left to
occupy.

**Nothing in `source/` checks it.** `Xcp_FillErrorPacketWithData` (`source/Xcp.c`) writes
`SduDataPtr[0x02u + idx]` for `idx < dataLength` with no comparison against `maxCto`, then hands
`2 + dataLength` to `Xcp_FinalizeResPacket`, which sets `SduLength = startIndex` and pads from
there with `for (idx = startIndex; idx < maxCto; idx++)`. A `startIndex` already past `maxCto`
skips that loop rather than reporting anything, so the finalizer cannot catch after the fact what
the copy already did. Clamping `startIndex` inside the finalizer would mislabel the hazard rather
than prevent it.

**The hazard is a wire fault, not a buffer overrun.** The response buffer is
`uint8 _packet[0x100u]` (`source/Xcp_Internal.h`), not `maxCto` bytes, so an over-long payload
stays inside the allocation and reaches CanIf as an `SduLength` the §1.1.3.3 layout forbids. The
single exception is arithmetic rather than practical: `dataLength` is a `uint8`, so
`2 + dataLength` reaches 257 and writes index 256, one past a 256-byte array. No caller passes
more than 4.

**What the guarantee actually rests on today** is `config/xcp.schema.json`'s `max_cto`
`"minimum": 8`, which no code states and nothing checks. That is the whole of D18.

### The three payload sites, and a fourth the defect does not name

Every payload the module attaches to an error packet is a module-chosen constant:

| Site | Payload handed to the helper | Packet length |
|:--|:--|:--|
| `DOWNLOAD_NEXT` / `PROGRAM_NEXT` `ERR_SEQUENCE` (`source/Xcp_Cal.c`, `source/Xcp_Pgm.c`) | expected element count, 1 byte | 3 |
| `ERR_GENERIC` detail (`Xcp_FillGenericErrorPacket`, D17) | detail WORD, 2 bytes | 4 |
| `BUILD_CHECKSUM` `ERR_OUT_OF_RANGE` (`source/Xcp_Std.c`, D6) | reserved WORD + MAX_BLOCK_SIZE DWORD, 6 bytes | 8 |

`Xcp_BuildChecksumFillMaxBlockSize` passes six bytes, not four: 1.1/§1.6.1.2.9 puts a reserved WORD
at positions 2,3 and the DWORD at 4..7, and the helper writes flat from position 2, so the two
reserved zeros are part of the payload. **The floor is therefore 8** — which is exactly the schema
minimum, leaving no headroom at all. D18 warned that "the next payload added may not be so
comfortably inside the floor"; measured, the largest payload already fills a floor-sized `MAX_CTO`
to its last byte.

**`USER_CMD` is the fourth site, and the only one whose length this module does not choose.**
`Xcp_DTOCmdStdUserCmd` (`source/Xcp_Std.c`) hands the response `PduInfoType` to the integrator's
`userCmdFunction`, which writes the payload *and* sets `SduLength`, and then finalizes with
whatever came back — unchecked. The contract never states the bound either: `Xcp_UserCmdFunction`'s
documentation (`test/stub/Xcp_UserCmd.h`) is a copy of the checksum callback's, describing an
address range this function does not take.

---

## 2. Decisions

**DD126 — the module-chosen payloads are bounded at generation, not at runtime.** Their three
lengths are compile-time constants, so a runtime comparison would be an arm no configuration can
enter — the dead-guard pattern this project has already paid for twice (the `counters.odt > 255`
guard shadowed by a stricter template ceiling, SP2b round 2; `Xcp_DTOCmdDaqGetDaqListInfo`'s
unreachable false arm, same wave). A generation-time refusal fails the build that would violate the
bound instead of adding an untestable branch to the one that cannot.

Generation, specifically, rather than the schema: `test/conftest.py` bypasses `xcp.schema.json`
entirely but goes through the generator, which is why `sp2b-followups.md` rejected raising a schema
minimum for `max_odt: 0`. The same reasoning applies unchanged here, and the precedent is in the
file this guard joins — `script/source_cfg.c.jinja2` already refuses `WRITE_DAQ_MULTIPLE` with
`MAX_CTO < 10`, citing 1.1/§1.6.4.1.2.1.

**DD127 — the guard reads each configuration's own `max_cto`, never `XCP_MAX_CTO`.** That macro is
a `max()` fold over every configuration in the generated file (`script/header_cfg.h.jinja2`), so a
check against it proves only that the *largest* configuration fits and says nothing about the
others. `Xcp_DtoFrameStrideCheck` records the same trap from the other side: it had to relax `==`
to `>=` the moment two configurations' `max_dto` disagreed.

**DD128 — the floor is 8, named at the guard, and it cannot fire under today's schema.** That is
the point, not an objection: D18's complaint is that the relationship between the payload sizes and
`max_cto` is unwritten, so a future payload or a lowered floor breaks it silently. The guard's
message names the payload that sets the floor — `BUILD_CHECKSUM`'s DWORD at positions 4..7 — so the
next author of a payload learns what to re-check, and both error helpers carry a comment pointing
at it. Naming the guard at the arithmetic it protects is the remedy `sp2b-followups.md` prescribed
for exactly this shape, where a guard lives in a different file from the code it makes safe.

**DD129 — `USER_CMD`'s response is checked at runtime and refused, not truncated.** Its length
crosses an API boundary at runtime, so no build-time check can reach it. Truncation is rejected
because a user-defined payload carries no length field of its own: a master receiving a clamped
response cannot distinguish it from a complete one, and would act on a fragment believing it whole.
Refusing is legible — the master learns the command failed.

**DD130 — the refusal answers `ERR_GENERIC` with a new detail code, and `USER_CMD`'s error-matrix
row gains the bit declaratively.** Neither revision lists `ERR_GENERIC` in `USER_CMD`'s
§1.7.3.2.1 row (1.1: `ERR_CMD_BUSY`, `ERR_PGM_ACTIVE`, `ERR_CMD_SYNTAX`, `ERR_OUT_OF_RANGE`,
`ERR_RES_TEMP_NOT_A.`; 1.0 the same minus the last). The deviation is deliberate and is the third
of its kind here: DD57 took it for `PROGRAM_RESET` and DD76 for `UNLOCK`, both for the same reason
— an integrator callback failed, and of the listed codes only ones describing the *master's*
mistake remain. `ERR_CMD_SYNTAX` blames the request's syntax and `ERR_OUT_OF_RANGE` its parameters;
this master sent a well-formed `USER_CMD` and the slave's own extension answered too much.
1.1/§1.1.3.3's `ERR_GENERIC` — "an implementation specific slave device error code as WORD" — is
what that is. `Xcp_CTOErrorMatrix[0xF1]` gains `XCP_INTERNAL_ERR_GENERIC` the way DD76 added it to
`UNLOCK`'s row: the matrix drives only the three generic pre-checks (`ERR_CMD_BUSY`,
`ERR_CMD_SYNTAX`, `ERR_PGM_ACTIVE`), so every other bit in it is documentation, and leaving this
one clear would make the table disagree with the handler beside it.

**DD131 — the detail code is `XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG` (0x0006) and the Det
id is `XCP_E_USER_CMD_RESPONSE_TOO_LONG` (0x0A).** The detail code continues D17's flat vocabulary
(DD122) at the next free value. The Det report is what makes this diagnosable by the person who can
fix it — the fault is in the integrator's callback, not in anything the master did — and follows
`XCP_E_STIM_FRAME_REJECTED`'s precedent of reporting what the module refuses. 0x0A is the next free
module-specific value; 0x02, 0x03, 0x04 and 0x12 are AUTOSAR's (SWS_Xcp §7.2.1) and 0x05–0x09 are
this module's.

---

## 3. Behaviour

| Site | Who chooses the length | What enforces the bound | A violation produces |
|:--|:--|:--|:--|
| The three error payloads | this module, as constants | the generation guard (DD126) | a refused build, naming the payload |
| `USER_CMD` | the integrator's callback | the runtime check (DD129) | `ERR_GENERIC` + detail WORD, and a Det report |
| `UPLOAD` / block transfer | the master, bounded by `maxCto` arithmetic | unchanged since D1 | — |

The generation guard sits beside the `WRITE_DAQ_MULTIPLE` refusal in
`script/source_cfg.c.jinja2` and reads, in substance: *`MAX_CTO` is N, but an error packet carrying
`BUILD_CHECKSUM`'s maximum block size occupies positions 4..7 (XCP part 2 1.1/§1.6.1.2.9,
1.1/§1.1.3.3), so `MAX_CTO >= 8` is required.*

`Xcp_DTOCmdStdUserCmd`'s flow becomes: call the callback; on `E_OK`, compare the `SduLength` it set
against `Xcp_Ptr->general->maxCto`; if it exceeds, discard the response, report Det, and answer
`ERR_GENERIC` carrying the detail WORD through `Xcp_FillGenericErrorPacket`. An `SduLength` equal to
`maxCto` is legal and passes through untouched. Every other path is unchanged, including the
callback's own non-`E_OK` return.

---

## 4. Testing

**Generation.** A configuration whose `max_cto` is below the floor is refused, *and* the same
configuration generates once that field is corrected. The second half is the discriminator:
`sp2b-followups.md` records that all ten existing generation-failure tests are mutually
indistinguishable, because `raise` is not a registered Jinja global and every guard surfaces the
identical `'raise' is undefined`, so only a paired success can show which guard fired.

**`USER_CMD`, three cases.** A callback returning an `SduLength` above `maxCto` answers
`ERR_GENERIC` with the detail WORD and reports Det; one returning exactly `maxCto` transmits
unchanged, which is where an off-by-one in the comparison would show; one returning less is
untouched.

**One existing test has to move above the floor.**
`test_xcp_init_raises_e_init_failed_if_max_cto_parameter_does_not_fit_with_address_granularity`
(`test/asam_protocol_layer_test.py`) configures `max_cto` of 1 and 3 to reach `Xcp_Init`'s modulo
check, and DD126's guard refuses to generate those. Its parametrisation moves to values that are
at or above 8 and still violate the relation — 9 and 11 under `WORD`, 9 and 10 under `DWORD` — which
keeps the test's own point intact. Its `max_dto` sibling directly below already carries a comment
explaining the identical adjustment for an unrelated generator guard, ending "Do not simplify this
back to 1"; the `max_cto` case now needs the same note.

**No test drives an over-long error payload**, and that is a consequence of DD126 rather than a
gap: with the generation guard in place no schema-valid *or* test-fixture configuration can build a
module whose constants exceed the bound. Stated here so the absence reads as a decision rather than
an oversight.

---

## 5. Out of scope, and three findings recorded in passing

Out of scope: `UPLOAD` and the block-transfer response (`source/Xcp.c`), already bounded by `maxCto`
arithmetic since D1, and the central-invariant sweep across every site that sets `SduLength`.

**Finding 1 — `MAX_CTO mod AG = 0` and `MAX_DTO mod AG = 0` are enforced at `Xcp_Init` and nowhere
earlier.** 1.1/§1.6.1.1.1 states both as relations that "must always be fulfilled" (read from the
PDF's text layer; 1.0 has them too).

**Corrected before implementation began.** This finding first read "enforced nowhere", which is
false: `Xcp_Init` tests `(maxCto % element_size) == 0` and `(maxDto % element_size) == 0`
(`source/Xcp.c:1262`) and reports `XCP_E_INIT_FAILED` when either fails, with a parametrised test
per relation in `test/asam_protocol_layer_test.py`. The search behind the original claim covered
`config/xcp.schema.json` and `script/source_cfg.c.jinja2` and stopped there — the same
stopped-too-early mistake as reading a table from one revision, in a different dress. It surfaced
in this plan's own pre-flight scan, because those tests configure `max_cto` of 1 and 3 deliberately
and the generation guard DD126 adds would have refused to build them.

What survives, much narrower: neither the schema nor the generator catches the violation, so it
reaches the target and fails there — a Det report and a module that never initialises — where the
neighbouring `WRITE_DAQ_MULTIPLE`/`MAX_CTO >= 10` constraint in the same template is refused at
generation. Whether an init-time refusal is the right place for it is a question, not a defect:
AUTOSAR requires `Xcp_Init` to report `XCP_E_INIT_FAILED` for a configuration it cannot accept.

**Finding 2 — `Xcp_CTOErrorMatrix` carries `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` in no row.**
1.1 adds `0x33` to the STD rows (`CONNECT`, `GET_STATUS`, `GET_ID`, `UNLOCK`, `USER_CMD` and others,
checked against 1.1/§1.7.3.2.1); the module's matrix is 1.0's throughout. `GET_STATUS` already
*answers* `0x33` since SP5-NV, so the table and the handler disagree. Declarative only — the matrix
drives just the three generic pre-checks — so no behaviour is wrong today. Same family as the EV
code row corrected on 2026-09-15: a 1.0-era transcription that 1.1 extended.

**Finding 3 — `XCP_E_EVENT_QUEUE_FULL` (0x04) collides with AUTOSAR's `XCP_E_INIT_FAILED` (0x04).**
SWS_Xcp §7.2.1 defines the latter; both are live, reported from `Xcp.c`'s event-queue sites and from
`Xcp_Init` respectively. A Det consumer can still separate them by API id, so the impact is
confined to the id not being unique as AUTOSAR intends — but it is why DD131 picks 0x0A rather than
continuing to fill low values.

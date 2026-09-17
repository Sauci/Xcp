# Conformance review against XCP Part 2 1.1 — findings

**Status: in progress.** Slices are marked as they complete. Nothing here is a change to the
module; findings are recorded at the confidence they were actually established, and triaged into
branches afterwards the way D18's own §5 findings were.

## Method, and why it is shaped this way

**This is an adversarial test of the roadmap's claims, not a fresh reading.** `2026-08-29-xcp-part2-roadmap.md`
§2 already states a per-command status. Three of those statements have been found stale or false in
the past two days — `SET_REQUEST`'s "refused … as unsupported modes", D18 Finding 2's "carries
`ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` in no row", and the `EV_*` row listing **1.0's** absent set
as 1.1's. A review that re-derived the roadmap would reproduce its errors; one that tries to falsify
it will not.

**Every 1.1 table is read from the PDF's own text layer, never the OCR sidecar.** The sidecar has now
been wrong about three separate tables: §1.7.3.2.1's error matrix (a dropped `ERR_CMD_SYNTAX`),
§1.2's event codes (a truncated code column), and §1.8.9's Info Type enumeration (an entire row,
`1 = DAQ list number`, absent). It is not uniformly wrong, which is the trap — §1.8.8 immediately
above §1.8.9 agreed exactly. Checking is therefore per-table work, not a formality done once.

The text layer is enciphered by glyph substitution. The 65-glyph map used here was rebuilt by the
known-plaintext method of §0 of `2026-09-11-xcp-get-id-types-design.md`, completed from §1.4.1's
command-code table, whose PIDs are known independently, and from §1.1.2.1's heading. Digits are
enciphered too and follow no single offset.

**Two confidence levels, kept distinct.** "Read in the code" and "observed on the mocked wire" are
different claims. Conflating them is what made D18's Finding 1 wrong in one direction — it claimed a
check existed nowhere when `Xcp_Init` had it — and Finding 4 understated in the other. Every finding
below says which it is.

---

## Slice 1 — dispatch and packet structure

### ✅ Every command 1.1 defines reaches a handler

**Verified mechanically, no finding.** 1.1/§1.4.1–§1.4.5 define **56** commands. All 56 have a
`Xcp_PIDTable` entry resolving to a real handler in at least one build configuration: 37
unconditionally, 19 only when a feature gate is on (`XCP_PAGING_SUPPORTED`,
`XCP_FLASH_PROGRAMMING_ENABLED`, `XCP_DAQ_TIMESTAMP_SUPPORTED`). No command is
`Xcp_CmdNotImplemented` in every arm, and every table comment's mnemonic matches 1.1's name for that
PID.

*Method note recorded because it produced a false positive first:* a parser that collapses the
`#if`/`#else` arms reports nineteen commands as unimplemented, because the `#else` arm legitimately
holds `Xcp_CmdNotImplemented` and appears later in the file. The preprocessor arms have to be
tracked separately. This is worth stating because the same mistake would make any future automated
check of this table wrong in exactly the same way.

### ✅ CONNECT matches 1.1 byte for byte

**Verified by reading, against 1.1/§1.6.1.1.1's deciphered table.** Response positions 0–7:
`PID 0xFF`, `RESOURCE`, `COMM_MODE_BASIC`, `MAX_CTO` as a **single BYTE** at 3, `MAX_DTO` as a
**WORD** at 4, protocol layer version at 6, transport layer version at 7 — all matching
`Xcp_CTOCmdStdConnect` (`source/Xcp_Std.c`).

`RESOURCE`'s bit mask likewise: `CAL/PAG` bit 0, `DAQ` bit 2, `STIM` bit 3, `PGM` bit 4, bits 1 and
5–7 unused. `source/Xcp_Internal.h:179-182` assigns exactly those.

The single-byte `MAX_CTO` at position 3 is the same fact D18's Finding 5 rested on, independently
confirmed here from 1.1 rather than 1.0.

---

## Slice 6a — the STD error handling matrix (§1.7.3.2.1)

### ✅ Finding R1 — four rows of `Xcp_CTOErrorMatrix` disagreed with 1.1 — **fixed**

**Established by reading 1.1/§1.7.3.2.1 from the deciphered text layer, row by row, and comparing
against `Xcp_CTOErrorMatrix` (`source/Xcp.c`). Declarative only — the matrix drives just the
`ERR_CMD_BUSY`, `ERR_CMD_SYNTAX` and `ERR_PGM_ACTIVE` pre-checks, so no behaviour is wrong today.**

1.1 lists `ERR_RES_TEMP_NOT_A.` for every STD command **except `DISCONNECT`**, whose row is
`timeout t1`, `ERR_CMD_BUSY`, `ERR_PGM_ACTIVE` and nothing else. `CONNECT` carries it under
`CONNECT(NORMAL)` only; `CONNECT(USER_DEFINED)` has just `timeout t6`.

| PID | Command | 1.1 lists it | Module carries it | |
|:--|:--|:--|:--|:--|
| 0xFE | `DISCONNECT` | **no** | **yes** | added where the specification does not list it |
| 0xF1 | `USER_CMD` | yes | **no** | missed |
| 0xF2 | `TRANSPORT_LAYER_CMD` | yes | **no** | missed |
| 0xF6 | `SET_MTA` | yes | **only in one arm** | the `XCP_FLASH_PROGRAMMING_ENABLED == STD_OFF` arm (`Xcp.c:1093`) lacks it; the `STD_ON` arm (`:1103`) has it |

The other two-arm rows, `BUILD_CHECKSUM` (0xF3) and `UPLOAD` (0xF5), do carry it in both arms.

**Root cause, and it is the same mistake in all four.** PR #41 asserted that "1.1/§1.7.3.2.1 gives
**every** standard command an `ERR_RES_TEMP_NOT_A.` entry". That was generalised from scanning the
OCR sidecar by eye and seeing the code appear at the end of many rows — a sample, read as a rule.
The change was then applied to a hand-listed set of line numbers rather than to a set derived from
the specification, which is why two commands were missed and one preprocessor arm with them.

It is worth being exact about what this costs, because the justification given for that change was
that "a row that does not list what its handler can answer is a row that lies to whoever reads it
next" (DD76, DD101). By that standard `DISCONNECT`'s row now lies in the other direction: it claims
the module may answer a code for a command 1.1 does not permit it on.

**Fixed in this branch.** The bit is removed from 0xFE and added to 0xF1, 0xF2 and `SET_MTA`'s
`STD_OFF` arm. Four one-line edits; 13073 passed, 29 skipped, unchanged, which is what a purely
declarative change should do. A check now derives the expected set from 1.1 and compares every STD
row against it, rather than trusting a reading of the table — it reports no disagreement.

The comment above `Xcp_CTOErrorMatrix` asserted the false rule in prose as well, and now states what
1.1 actually says, including that `CONNECT` carries the code under `CONNECT(NORMAL)` only while this
table has one row per PID.

**`SET_MTA`'s `STD_OFF` arm also lacks `ERR_PGM_ACTIVE`, and that is correct** — with programming
disabled the condition cannot arise, which is why the row has two arms at all. Only the missing
`ERR_RES_TEMP_NOT_A.` was wrong.

**Not yet checked in this row:** whether each command's *other* listed codes match. This finding
covers `ERR_RES_TEMP_NOT_A.` only, which is what PR #41 touched. The rest of §1.7.3.2.1, and
§1.7.3.2.2–§1.7.3.2.5, are still outstanding.

### 🔴 Finding R2 — `GET_ID` cites an `ERR_OUT_OF_RANGE` row that 1.1 does not have

**Established from both sources, which agree.** 1.1/§1.7.3.2.1's `GET_ID` row lists exactly four
codes: `ERR_CMD_BUSY`, `ERR_CMD_UNKNOWN`, `ERR_CMD_SYNTAX`, `ERR_RES_TEMP_NOT_A.` — plus
`timeout t1`. **`ERR_OUT_OF_RANGE` is not among them.** Checked in the deciphered text layer (rows
7513–7521) *and* the OCR sidecar (6396–6400) precisely because the code asserts the opposite; the
two agree, and `SET_REQUEST` immediately below does carry `ERR_OUT_OF_RANGE` in both, which rules
out a systematic extraction gap at that point in the table.

`source/Xcp_Std.c`'s `Xcp_DTOCmdStdGetId` says, of identification types 5..127:

> This is the only value range that can reach GET_ID's own **ERR_OUT_OF_RANGE row in
> 1.1/§1.7.3.2.1**, the identification type being its only parameter. … DD110.

There is no such row. `Xcp_CTOErrorMatrix[0xFA]` carries `XCP_INTERNAL_ERR_OUT_OF_RANGE` to match
the claim.

**The behaviour is defensible; the citation is not.** DD132 established that §1.7.3 anticipates a
slave answering a code its command's row does not list — the master falls back to the code's
severity — so answering `ERR_OUT_OF_RANGE` for an undefined identification type is a legitimate
off-row choice, and arguably the only sensible one. What is wrong is that it is recorded as
*compliance* rather than as a choice, which is the same class of mistake DD132 corrected in four
other comments, in the opposite direction: those called a legitimate off-row answer a "deviation",
this one calls an off-row answer a row.

It also means `Xcp_CTOErrorMatrix[0xFA]` carries a code that no comment declares as off-row, unlike
`UNLOCK`'s and `USER_CMD`'s `ERR_GENERIC`, which DD76 and DD130 both flag where they sit.

**Proposed fix:** correct the comment to say that 1.1/§1.7.3.2.1's `GET_ID` row does not list
`ERR_OUT_OF_RANGE`, that answering it is the off-row choice §1.7.3 provides for, and why no listed
code fits an identification type that names nothing. Mark the matrix row the way DD76 and DD130
mark theirs. No behaviour change, no test change.

---

## Non-findings worth recording, so they are not "fixed" later

**`SET_MTA`, `UPLOAD` and `BUILD_CHECKSUM` omit `ERR_PGM_ACTIVE` in the programming-*enabled* build
and carry it in the disabled one.** This looks inverted and is deliberate: 1.1/§1.6.5.1.1 requires
`SET_MTA` to stay available *during* a programming sequence, and one matrix bit governs all four
`ERR_PGM_ACTIVE` triggers, so carrying it would make the gate refuse the command the specification
requires to remain reachable. `source/Xcp.c` documents this at length at the row itself, including
the sentence "worth recording so a future reader does not 'fix' it back". This review nearly did.

---

## Slices not yet started

2. §1.6.1 STD commands beyond `CONNECT`
3. §1.6.2 CAL and §1.6.3 PAG
4. §1.6.4 DAQ and STIM
5. §1.6.5 PGM
6. §1.2 / §1.3 / §1.7 / §1.8 — events, service requests, error handling, and 1.1's own chapter

The error handling matrix (§1.7.3.2) is the largest mechanically checkable item remaining and is
where D18's Finding 2 showed the module carrying 1.0's table; it is scheduled first in slice 6.

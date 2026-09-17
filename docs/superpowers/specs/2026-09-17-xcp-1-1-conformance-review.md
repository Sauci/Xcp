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

## Slices not yet started

2. §1.6.1 STD commands beyond `CONNECT`
3. §1.6.2 CAL and §1.6.3 PAG
4. §1.6.4 DAQ and STIM
5. §1.6.5 PGM
6. §1.2 / §1.3 / §1.7 / §1.8 — events, service requests, error handling, and 1.1's own chapter

The error handling matrix (§1.7.3.2) is the largest mechanically checkable item remaining and is
where D18's Finding 2 showed the module carrying 1.0's table; it is scheduled first in slice 6.

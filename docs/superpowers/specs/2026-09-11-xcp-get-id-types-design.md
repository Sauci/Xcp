# SP5-GETID — GET_ID identification types

**Date:** 2026-09-11
**Baseline:** `develop` at `38eb3ff`
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.1*, ASAM e.V. (`docs/external/`).
1.0 is cited wherever it says something different, and wherever it is simply the readable copy.

**Depends on:** nothing. The roadmap's §4 names `GET_ID` types as one of four residue items that are
"genuinely independent and can be pulled forward if one of them blocks an integration".

`GET_ID` is §1.6.1.2.2 in **both** revisions — this command is not caught by the §1.6.4 renumbering.

---

## 0. What 1.1 changes, and how its tables were actually read

Both revisions were read before anything was designed. They are not the same, and the difference is
in the one byte this module already writes.

| | 1.0/§1.6.1.2.2 | 1.1/§1.6.1.2.2 |
|---|---|---|
| response byte 1 | `Mode` — an unnamed byte | `Mode` — **a bit mask**, `TRANSFER_MODE` (bit 0), `COMPRESSED_ENCRYPTED` (bit 1), bits 2–7 don't-care |
| identification offset | "7+…" | 8 (1.0's "7+…" contradicts its own `4..7 DWORD Length`) |
| AG rule on `Length` | absent | **"The following rule applies: Length mod AG = 0"** |
| initial UPLOAD rule | absent | **`Number of Data Elements UPLOAD [AG] = (Length GET_ID [BYTE]) / AG`** |
| compression | absent | `COMPRESSED_ENCRYPTED`, "only allowed for Identification Type 4", interface in **XCP Part 4** |
| identification string | "is ASCII text format" | "is a byte stream of plain ASCII text" |

So 1.1 does to `GET_ID`'s response byte what it did to `SET_REQUEST`'s mode byte: it turns an opaque
field into a named bit mask and adds a flag. That pattern cost three PRs (#23, #24, #25) when it was
missed once. It is recorded here so the next reader does not have to rediscover it.

**How the bit positions were established.** 1.1's PDF text layer is enciphered by glyph
substitution, and its OCR sidecar misaligns table columns — a bit position read from the OCR is not
evidence. The substitution was recovered from known-plaintext pairs (`IPQB`→`BYTE`, `KBQX@A`→
`GET_ID`, `A[HYA`→`DWORD`, `SBQXYB^RBSQ`→`SET_REQUEST`) and applied to the page's own text layer.
Two independent readings agree:

1. **Prose.** `QYNGSJBYXDHAB` deciphers to `TRANSFER_MODE` and `CHDVYBSSBAXBGCYPVQBA` to
   `COMPRESSED_ENCRYPTED`, in the two sentences immediately below the table.
2. **Column geometry.** The bit-number row places bit 1 at character offset 87 and bit 0 at 95. The
   two stacked (rotated) labels sit at offsets 91 and 100. The six don't-care `x` marks sit at
   +4 to +6 from their own bit numbers, so the same rightward rendering offset maps 91→bit 1 and
   100→bit 0.

**`TRANSFER_MODE` is bit 0; `COMPRESSED_ENCRYPTED` is bit 1.** This is asserted from the PDF, not
from the OCR.

`Length mod AG = 0` was likewise read from the PDF text layer directly (`Ebgktl dha NK 4 6`), not
from the OCR.

---

## 1. What the existing code already does, and two things it gets wrong

`Xcp_DTOCmdStdGetId` (`source/Xcp_Std.c`) serves identification type 0 by pointing the MTA at
`Xcp_Ptr->general->identification` and reporting its NUL-scanned length. DD75 already settled the
MTA *extension* for that pointer — 0, because the identification is not part of any CAL/PAG segment
and so there is no page for a non-zero extension to select. That reasoning is intact and this
phase does not disturb it.

**Wrong thing 1 — a test that pinned an echo, not a bit mask.** `test_get_id_returns_identification_through_mta_when_
mode_is_0` (`test/get_id_test.py`) asserts `raw_data[1] == mode`, where `mode` is the *request's*
Requested Identification Type and `raw_data[1]` is the *response's* Mode bit mask. These are two
different fields that happen to coincide at zero, and the response byte is a hardcoded `0x00`. The
assertion pins the right value only because this test's parametrize list has a single row at mode
0, and it demands the wrong thing — that the response echo the request — the moment a second
identification type is covered. This is recurring defect class 1 from the roadmap (expected value
coinciding with a default).

**Correction, made after Task 1's implementer disproved the original wording empirically**
(`.superpowers/sdd/2026-09-11-xcp-get-id-types/task-1-report.md`): this paragraph previously
claimed "The assertion passes under any implementation," which does not hold — with `mode` pinned
at 0, mutating the response byte away from 0 breaks the old assertion too, for the unrelated
reason that the two sides then stop reading the same number by coincidence. The assertion's real
weakness is the one now stated above: it cannot tell a correct implementation from an incorrect
echo at mode 0, not that it is immune to a wrong byte on the wire.

**Wrong thing 2 — a latent 1.1 violation already shipping.** The default `identification` is
`/path/to/database.a2l`, 21 bytes. 21 mod 2 = 1 and 21 mod 4 = 1, so under `address_granularity` of
`WORD` or `DWORD` the module already reports a `Length` that violates 1.1's `Length mod AG = 0`.
Eleven test files exercise non-BYTE AG, through the shared `DefaultConfig` in `test/parameter.py`. This
predates the phase and is fixed by it.

---

## 2. Design decisions

### DD108 — identification data comes from an integrator callback, not a widened configuration table

Types 1–3 are strings an integrator could plausibly put in `xcp.json`. Type 4 is not: 1.1/§1.6.1.2.2
defines it as "ASAM-MC2 file to upload", a whole A2L file whose contents are not known when the
configuration is generated. Neither is the 128–255 range, which 1.1 leaves entirely to the
integrator ("User defined") and which a fixed table cannot enumerate.

So the mechanism is an optional callback, following the `user_cmd_function` /
`user_defined_checksum_function` pattern this module already has — a nullable name in `xcp.json`
emitted as `&Name` or `NULL_PTR` into `Xcp_GeneralType`, null-checked at the call site:

```c
Std_ReturnType (*const getIdentificationFunction)(uint8 identificationType,
                                                  const void **pIdentification,
                                                  uint8 *pExtension,
                                                  uint32 *pLength);
```

`E_OK` means the out-parameters are set. `E_NOT_OK` means "this slave does not serve that type" and
is not an error — see DD110.

The field goes at the **tail** of both `Xcp_GeneralType` and the generated initialiser in
`script/source_cfg.c.jinja2`. That struct is initialised positionally; a field inserted anywhere
else silently shifts every later one.

### DD109 — the callback carries the MTA extension, and DD75 still stands

The callback returns an extension alongside the address. DD75 fixed `extension = 0` for the *static*
identification, and its reasoning was specific: that string is "plain, slave-owned descriptive data
that lives entirely outside the page-switching model", so no SEGMENT exists for an extension to
name. That argument is about `Xcp_Ptr->general->identification` and does not automatically transfer
to arbitrary integrator data.

Type 4 is the case that breaks it. An A2L file plausibly lives in external flash or a memory region
the integrator's `Xcp_ReadSlaveMemory*` reaches through a non-zero extension. Fixing the extension
at 0 for callback data would let the module advertise type 4 while only being able to serve it from
extension-0 memory — recurring defect class 3, advertising what you cannot honour.

Type 0 served from the static string keeps extension 0, unchanged, by DD75's own reasoning.

### DD110 — an unserved type answers `Length = 0`; only an *undefined* type is an error

Both revisions say, of the response: "If length is 0, the requested identification type is not
available." That is `GET_ID`'s own in-band mechanism for declining, and it exists so a master can
enumerate what a slave supports without provoking errors. Today the module answers
`ERR_OUT_OF_RANGE` for every type other than 0, which never lets that mechanism fire.

But `ERR_OUT_OF_RANGE` cannot simply be dropped either: §1.7.3.2.1's error matrix (identical in both
revisions) gives `GET_ID` its own `ERR_OUT_OF_RANGE` row with recovery "retry other parameter", and
`GET_ID`'s only parameter is the identification type. Answering `Length = 0` for everything would
leave that row dead.

Both sentences are honoured by splitting on whether the specification defines the type at all:

```
type in 5..127                              -> ERR_OUT_OF_RANGE   (not an identification type)
type in 0..4 or 128..255:
    callback configured and returns E_OK    -> serve: set MTA, report Length
    else if type == 0                       -> serve static identification (DD75 path, unchanged)
    else                                    -> positive response, Length = 0 ("not available")
```

1.1/§1.6.1.2.2 lists exactly 0, 1, 2, 3, 4 and 128..255 as the types that "may be requested"; 5–127
are not identification types, so a master naming one has supplied an out-of-range parameter and
"retry other parameter" is the right recovery. A master naming type 3 on a slave that has no URL has
supplied a perfectly valid parameter, and `Length = 0` tells it so.

**The callback is consulted first for every defined type, including 0.** With no callback configured
the type-0 path is byte-for-byte what ships today. With one configured, an integrator who needs a
runtime-varying type 0 can override it, and one who does not simply returns `E_NOT_OK` and gets the
static string. The alternative — reserving type 0 to the static string and giving the callback only
1–4 and 128–255 — is a marginally simpler contract that forecloses that case for no benefit.

### DD111 — `TRANSFER_MODE` stays 0, and both mode bits are named anyway

The slave keeps answering `TRANSFER_MODE = 0` and pointing the MTA, for every type.

This is a deliberate omission, not a gap. The request packet is two bytes — command code and
Requested Identification Type — so **the master has no field in which to ask for inline transfer**.
The slave chooses the transfer mode and merely reports which it used, and both revisions describe
mode 0 as a complete answer. A slave that never sets the bit is conformant.

It is also unreachable at the shipped defaults: the response header occupies all 8 bytes, so inline
transfer requires `max_cto > 8` before it can carry a single byte.

`COMPRESSED_ENCRYPTED` stays 0 for a second, independent reason: 1.1/§1.6.1.2.2 puts its algorithm
interface in **XCP Part 4**, which is not in `docs/external/`. `COMPRESSED_ENCRYPTED = 0` (plain,
uncompressed) is always legal, so this costs nothing.

Both bits nevertheless get named constants at their PDF-verified positions, cited where the response
byte is built. The decipherment in §0 was expensive; committing its result to the source means it is
never redone, and it makes the hardcoded `0x00` legible as two cleared flags rather than a magic
number.

### DD112 — `Length mod AG = 0` is enforced where each half of it is knowable

1.1 adds the rule; 1.0 has no equivalent. It protects the UPLOAD that follows, whose element count
1.1 defines as `Length / AG` — an inexact division leaves the master unable to ask for the right
number of elements.

Enforced in two places, because the two sources of identification data are knowable at different
times:

- **Generation time**, for the configured static string: `script/source_cfg.c.jinja2` raises when
  `len(identification) mod AG != 0`, matching the existing `raise()` guards around
  `source_cfg.c.jinja2:749`. An integrator learns at build time, not on the wire.
- **Run time**, for callback data: a returned length with `length mod AG != 0` raises DET and the
  command answers `Length = 0`. The module cannot emit a non-conforming `Length`, and reporting the
  type unavailable is the honest alternative to truncating the data or padding it with the NULs
  1.1 explicitly says the string does not carry.

The shipped default `identification` changes from `/path/to/database.a2l` (21 bytes) to
`/path/to/xcp.a2l` (16), which conforms under BYTE, WORD and DWORD alike. Without that change the
new generator check would reject the module's own default configuration under non-BYTE AG.

### DD113 — a `Length = 0` answer still points the MTA at `(NULL_PTR, 0)`

Writing the plan surfaced a case §2 left open: what the MTA holds when the answer is "type not
available".

It is not left untouched. A `GET_ID` that returns without assigning the MTA leaves whatever an
earlier, unrelated `SET_MTA` put there, and a master that ignores `Length = 0` and issues `UPLOAD`
anyway then reads through a stale pointer it never set for this purpose — the same defect DD75
fixed for the extension half of the identical pair, arriving the other way round.

So a `Length = 0` response assigns `(NULL_PTR, 0x00u)`, which is already this module's vocabulary
for "nothing meaningful on this pair": `Xcp_Init` and `Xcp_CTOCmdStdConnect` both pair exactly that,
and DD75 cites 1.1/§1.6.1.2.3's "All ODT entries reset to address = 0, extension = 0" for the same
idiom. The master is told the type is unavailable; if it uploads regardless it reads from a pointer
the slave deliberately nulled rather than one it forgot to update.

**Where the rule is enforced.** `Xcp_DTOCmdStdGetId` decides it on the Length alone, immediately
before assigning the MTA: whenever the Length it is about to report is 0, it points the MTA at
`(NULL_PTR, 0x00u)`, whichever route produced that 0. There are five:

1. no callback, and a defined type other than 0 — nothing is ever assigned to the pair;
2. a callback that answers `E_NOT_OK` for a type other than 0, whatever it wrote to its
   out-parameters first — the decline path discards the length it wrote. (For type 0 the static
   fallback overwrites all three instead, DD110.)
3. a callback length that DD112's run-time check refuses — the check raises
   `XCP_E_IDENTIFICATION_NOT_GRANULAR` and discards the length;
4. a callback that answers `E_OK` with a length of 0;
5. an empty configured identification, served for type 0.

Routes 2 and 3 reset the length and nothing else: the length is what brings them under the rule,
and the rule nulls the pair. Routes 4 and 5 reset nothing; their Length is 0 as served.

**Correction, made in the final review's fix wave**
(`.superpowers/sdd/2026-09-11-xcp-get-id-types/final-fix-report.md`): as first shipped, this
decision's heading was false for routes 4 and 5. The code nulled the pair route by route, in the
decline path and in the granularity check, so a callback answering `E_OK` with `*pLength = 0`, and
an empty configured string for type 0, both reported `Length = 0` while the MTA pointed at real
memory — the callback's buffer, or the empty string's own address — for an UPLOAD that ignored
`Length = 0` to read through. The decision's only test took route 1, which never assigns the pair,
so it could not tell per-route nulling from none. The rule has been enforced on the Length since
that fix, and the test covers all five routes, each after a `SET_MTA` with extension 7 and each
checking the `(address, extension)` pair UPLOAD reads. With the rule in place, the address and
extension resets in routes 2 and 3 could no longer be told from their absence by any test, and were
removed, along with the granularity check's `served = FALSE`, a store nothing read afterwards. Each
route's length reset stayed: it is what routes 2 and 3 depend on. The static fallback's
`extension = 0x00u` (DD75) is thereby the only thing standing between a declining callback's
extension and the MTA for type 0, and has a test of its own.

---

## 3. What this does not change

- **The MTA/UPLOAD path.** Identification is still read by the master through the MTA, through the
  integrator's `Xcp_ReadSlaveMemory*`. The module never copies identification bytes; with
  `TRANSFER_MODE = 0` it never needs to read them at all, only their address and length.
- **DD75.** The static identification keeps extension 0, for DD75's own stated reason.
- **`xcp_get_id_api_enable`.** Disabling the command still answers `ERR_CMD_UNKNOWN` ahead of any of
  this.
- **Type 0 behaviour with no callback configured** — byte for byte.

---

## 4. Test strategy

**The existing assertion is repaired first, before anything is added.** `assert raw_data[1] == mode`
becomes an assertion that byte 1 is the response Mode bit mask with `TRANSFER_MODE` (bit 0) and
`COMPRESSED_ENCRYPTED` (bit 1) both clear, citing 1.1/§1.6.1.2.2. Landing this ahead of the feature
means the phase starts from a test that can actually fail.

`test_returns_err_out_of_range` (`test/asam_error_matrix_test.py`) narrows from `range(0x01, 0xFF)`
to 5–127. Note its old range stopped at `0xFE`: **type 255 was never covered**, and it is in the
user-defined range.

New coverage:

| Claim | Test |
|---|---|
| defined-but-unserved types answer `Length = 0` | types 1, 2, 3, 4, 128, 255 with no callback |
| undefined types answer `ERR_OUT_OF_RANGE` | 5–127 |
| a callback serves each defined type | parametrised over 0–4, 128, 255 |
| a declining callback falls back to the static string for type 0 | callback returns `E_NOT_OK` |
| a declining callback answers `Length = 0` for other types | |
| the callback's extension reaches the MTA | UPLOAD reads through the returned extension |
| a non-AG-multiple callback length raises DET and answers `Length = 0` | AG = WORD and DWORD |
| the generator rejects a non-conforming configured identification | AG = WORD and DWORD |

**Every behavioural claim is mutation-verified** — the code is changed so the test should fail, and
the failure is confirmed and the test named. A passing suite is not evidence that a test pins
anything.

Two harness facts apply. `Xcp_DaqQueuePeek` hands every transmission the same static `PduInfoType`,
so each frame is read immediately after its own `CanIf_Transmit` call, never from
`call_args_list` afterwards. And `Xcp_GeneralType` is initialised positionally, so the generator
change is checked to move exactly the intended field and nothing else.

---

## 5. Open questions and deliberate omissions

- **Inline transfer (`TRANSFER_MODE = 1`) is not built** — DD111. Reversible: the bit positions are
  now recorded, and the work is a packing branch plus a `max_cto` check.
- **`COMPRESSED_ENCRYPTED` is not built** and cannot be until **XCP Part 4** is available. Unlike
  Part 1, this one blocks nothing: the flag's cleared state is always legal.
- **Type 4 is servable but untestable end-to-end here.** The harness can assert that the MTA and
  `Length` are set from the callback; it cannot supply a real A2L file. The distinction between
  type 4 and types 1–3 is entirely the integrator's, which is what 1.1 means by "Which types are
  supported by the slave device is implementation specific".
- **XCP Part 1 (Overview) is still missing from `docs/external/`.** Unrelated to this phase, still
  open, still blocking the SP5-RESUME assumption that depends on its §2.3.

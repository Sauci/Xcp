# BUILD_CHECKSUM — closing D6

**Defect:** D6 — `BUILD_CHECKSUM` omits its extended error payload
(`docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` §3).

**Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. Every
citation below carries its revision prefix. Where the two differ it is said so explicitly;
where they agree, that agreement was checked rather than assumed.

---

## 1. What is actually wrong

1.1/§1.6.1.2.9 defines a negative response for this command alone:

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | Packet ID: `0xFE` |
| 1 | BYTE | Error code |
| 2,3 | WORD | reserved |
| 4..7 | DWORD | Maximum block size [AG] |

followed by the rule *"If the blocksize exceeds the allowed maximum value, an
ERR_OUT_OF_RANGE will be returned. The maximum block size will be returned in the checksum
field."* 1.1/§1.1.3.3 states the same requirement from the other direction, conditioned on the
pair rather than on a trigger: *"At BUILD_CHECKSUM the error packet with error code 0x22 =
ERR_OUT_OF_RANGE contains the maximum allowed block size as DWORD as additional
information."* 1.0/§1.6.1.2.9 and 1.0/§1.1.3.3 are word-for-word identical on both points;
this is not a 1.1 addition.

`Xcp_DTOCmdStdBuildChecksum` (`source/Xcp_Std.c`) answers plain `Xcp_FillErrorPacket`, so the
master receives a bare error code and cannot learn the limit.

**The roadmap understates the defect.** There is no maximum block size anywhere — not in the
configuration, and not as a check. The handler has exactly three error paths (a NULL checksum
function, an unmappable checksum type, and `block_size == 0`), none of which is a bound. So
this is not "attach a payload to an existing rejection"; the rejection does not exist, there
is no value to attach, and `block_size` arrives from four wire bytes and is used unchecked in

```c
upper_address = Xcp_Internal.memory_transfer.address + (element_size * block_size);
```

where `element_size` is up to 4. The missing limit is therefore also what stands between a
master-supplied `0xFFFFFFFF` and that multiplication.

---

## 2. Decisions

**DD115 — the maximum block size is configured globally, not per segment.** 1.1/§2.1's AML
declares a `CHECKSUM` block *inside each* `SEGMENT`, carrying the checksum type,
`MAX_BLOCK_SIZE` and `EXTERNAL_FUNCTION`; `config/xcp.json` declares all three once under
`protocol_layer`. Reconciling them is deferred, and the reason is recorded so it is not
mistaken for an oversight: `BUILD_CHECKSUM` works from the MTA, an arbitrary address, while
this module reaches segments *only* by an index the master supplies on the wire — there is no
address-to-segment resolution anywhere in `source/`, and `Xcp_SegmentType`'s `address`/`length`
are read today only to *report* `GET_SEGMENT_INFO`. Introducing one would force an answer to
"the MTA is in no configured segment", which neither 1.0 nor 1.1 defines. The roadmap's own
§2.6 observation stays open and keeps that work with a successor to D6.

**This departs from the roadmap's own framing, deliberately.** §3 there says D6 "remains open
and travels with the per-segment checksum reconciliation", so closing D6 without that work is
a change to how the two were bound together and should not be discovered by surprise later.
They are separable: the missing payload and the entirely absent bound are a conformance defect
in one handler, reachable today by any master; the AML reconciliation is a change to the
configuration model that needs its own design and its own answer to the undefined case above.
Holding a live defect open until an unrelated design lands serves nobody. The §2.6 note is
therefore rewritten to stand on its own rather than to hang off a defect that is now fixed.

**DD116 — `checksum_max_block_size` is required, not optional with a default.** An optional
field defaulting to "no practical limit" would close D6 structurally while leaving both the
conformance gap and the unbounded multiplication reachable in every default build; a default
of some concrete bound would silently change behaviour for any master currently requesting a
larger range. Requiring it makes each integrator state a real bound, which is also the only
variant that closes §1's hazard for every build rather than for those who opt in. This follows
the module's established habit of refusing to advertise what it cannot honour (D9's
resolution; the interleaved-communication row in roadmap §2.6).

"Required" binds the schema and therefore integrators; it does not mean `test/parameter.py`'s
own constructor takes a mandatory argument. That helper gets a **defaulted** kwarg, so the 213
configurations the suite builds need no edit each. The two are not in tension because they are
different gates — see the note on independent enforcement at the end of §4.

**DD117 — every `ERR_OUT_OF_RANGE` this handler answers carries the payload.** 1.1/§1.1.3.3
conditions the payload on the pair *(BUILD_CHECKSUM, 0x22)* and names no trigger, and
§1.6.1.2.9's Negative Response table is the layout for the command's negative response
unqualified. A master cannot tell which condition fired, so a uniform layout is what makes
bytes 4..7 parseable at all.

**DD118 — the two configuration faults answer `ERR_CMD_UNKNOWN` (0x20), not
`ERR_OUT_OF_RANGE`.** 1.1/§1.7.3.1 defines 0x22 as *"Command syntax valid but command
parameter(s) out of range"*. When the configured checksum type maps to nothing, or
`XCP_USER_DEFINED` is selected with no function configured, the master's parameters are valid
and the **slave** is misconfigured — 0x22 is not merely unhelpful there, it misattributes the
fault, and its matrix action ("retry other parameter") directs the master at a fix that cannot
exist. 0x20 is *"Unknown command or not implemented optional command"* with the action
"display error": terminal rather than futile, already in this command's 1.1/§1.7.3.2.1 row so
no deviation is required, and already this module's answer for an unavailable
`BUILD_CHECKSUM` — `asam_error_matrix_test.py`'s `test_returns_err_cmd_unknown` builds with
`xcp_build_checksum_api_enable=False` and asserts exactly `(0xFE, 0x20)`. A configured-but-
unusable checksum function is that same unavailability, discovered at run time instead of
build time.

Two alternatives were considered and rejected on the evidence:

- `ERR_GENERIC` (0x31) is the most semantically honest — 1.1/§1.1.3.3 pairs it with an
  implementation-specific slave error code, which is what a misconfiguration is, and DD76 set
  the precedent for departing from a matrix row when nothing listed fits. It is rejected
  because every row carrying it prescribes **"restart session"**, so a master would tear down
  and rebuild the session repeatedly against a fault that never clears.
- `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` (0x33) appears in this command's 1.1 row and looks
  apt until its own definition is read: 1.1/§1.7.3.1 glosses it *"Access to the requested
  resource is **temporary** not possible"*, 1.1/§1.1.1 introduces it for an XCP handler that
  "may not always have access to the resources of the XCP slave", and 1.1/§1.6.1.1.1 repeats
  it for a resource the handler cannot access *despite its resource flag being set*. A NULL
  function pointer is permanent, and none of the three describes it. The module's own use
  agrees — DD101 applies it to an *outstanding asynchronous read*.

Both codes are severity **S2** in 1.1/§1.7.3.1, identical to 0x22, so severity is not what
separates them; the prescribed master action is.

**DD119 — the overflow guard is a generation-time refusal, and is not gated on
`xcp_build_checksum_api_enable`.** The runtime bound alone does not close §1's multiplication:
`element_size * checksum_max_block_size` can still exceed a `uint32` when the address
granularity is DWORD. That is a constraint between two configuration fields, which JSON Schema
expresses badly and which this project already handles with a `raise(...)` in
`script/source_cfg.c.jinja2` (the identification ASCII guard; the sector `Length mod AG` guard).
It stays ungated for the reason the sector guard's own comment gives: such a check "is a check
on whether the CONFIGURATION means anything, not a decision about what to emit", and gating it
would let a broken configuration ship silently and fail only for whoever later enables the
command. Generation guarantees `max * element_size` fits; the runtime check guarantees
`block_size <= max`; together they make the multiplication unreachable in overflow.

**DD120 — the checksum algorithms gain known-answer tests from 1.1/§1.6.1.2.9.** 1.1 publishes
a 32-byte test pattern and expected results per algorithm; **1.0 does not contain these tables
at all**. `test/build_checksum_test.py` currently asserts the C module against Python
reimplementations of the same algorithms written in the same file, over randomly generated
content — that verifies *agreement between two implementations* and structurally cannot catch
a shared misunderstanding. The vectors are external reference values and close that gap.

---

## 3. Behaviour

Request and positive response are unchanged. Four failure conditions, three answers:

| Condition | Answer | Payload |
|:--|:--|:--|
| `block_size == 0` | `ERR_OUT_OF_RANGE` 0x22 | bytes 2,3 = 0; 4..7 = maximum block size |
| `block_size > checksum_max_block_size` | `ERR_OUT_OF_RANGE` 0x22 | same |
| checksum type unmappable (the `0x0A` sentinel) | `ERR_CMD_UNKNOWN` 0x20 | none |
| `XCP_USER_DEFINED` with a NULL function | `ERR_CMD_UNKNOWN` 0x20 | none; the existing `XCP_E_PARAM_POINTER` DET report is unchanged |

**Precedence is part of the design, not an implementation detail.** Both 0x22 conditions are
*request* validation and belong together in the existing first gate — `block_size == 0 ||
block_size > max` — **before** any configuration is resolved. A misconfigured slave receiving
an oversized request therefore answers 0x22, not 0x20. Stated explicitly because an ordering
of this shape was got wrong during the GET_ID work (a validation placed ahead of a fallback
that had to run first), and inferring it from the code again would repeat that.

**The MTA must be untouched on every error path.** 1.1/§1.6.1.2.9 post-increments it by the
block size, and today that happens only on the success line
(`memory_transfer.address = checksum_function(...)`). The new bound check sits before that and
must not disturb it: a rejected request that advanced the MTA would silently desynchronise the
master.

The DWORD is written with `Xcp_CopyFromU32WithOrder` against the configured `byteOrder`, as
the positive path already does for the checksum itself.

`Xcp_FillErrorPacketWithData` (`source/Xcp.c`) needs no change: it writes `pData` flat from
byte 2 and finalises at `2 + dataLength`, so a six-byte payload `{0, 0, b4, b5, b6, b7}`
expresses the `2,3 reserved / 4..7 DWORD` layout exactly.

`Xcp_CTOErrorMatrix` needs no change either: `ERR_CMD_UNKNOWN` is already in
`BUILD_CHECKSUM`'s row, so DD118 introduces no deviation to record.

---

## 4. Configuration

**Name: `checksum_max_block_size` / `checksumMaxBlockSize`.** Deliberately not
`max_block_size`: the module already has two unrelated bounds by that name — `maxBS` (master
block mode) and `maxBsPgm` (`programming.max_block_size`, which sizes a static buffer). The
prefix also keeps the field adjacent to `checksum_type` in every file it appears in.

**Type:** integer, units **[AG]**, matching the wire's `Block size [AG]`. `minimum: 1`,
`maximum: 4294967295`. The minimum is 1 for the reason `config/xcp.schema.json` already
records for `programming.max_block_size` — 0 is not a block size — and here a maximum of 0
would reject every request, since `block_size == 0` already fails.

Unlike `programming.max_block_size` this needs **no compile-time define**: it sizes nothing,
it is only compared against, so it lives solely as a runtime field and `test/conftest.py`'s
digest machinery is untouched.

Edit sites:

| File | Change |
|:--|:--|
| `config/xcp.schema.json` | property beside `user_defined_checksum_function`, **and** an entry in `protocol_layer`'s `required` list |
| `config/xcp.json` | a value, beside `checksum_type` |
| `test/parameter.py` | one defaulted kwarg and one `protocol_layer` dict entry |
| `interface/Xcp_Types.h` | `const uint32 checksumMaxBlockSize;` after `userDefinedChecksumFunction` |
| `script/source_cfg.c.jinja2` | the matching initialiser line, at the **same index** |
| `script/source_cfg.c.jinja2` | the DD119 overflow guard |

**The last two must move together.** `Xcp_GeneralType` is initialised **positionally** by the
template, so a field added to one and not the other silently mis-assigns its neighbours. A
`uint32` landing where a function pointer belongs would at least fail to compile; between two
same-typed neighbours nothing would catch it.

`config/xcp.json` and `test/parameter.py` both carry **65536**. The only hard constraint is
≥ 1000, because `test/build_checksum_test.py` parametrizes block sizes up to 1000 and those
tests must stay green; 65536 is 64 KiB under BYTE granularity, a plausible ceiling for a real
calibration ECU. The number is a judgement, not a derivation.

Schema-required and generator-enforced are **independent** gates here, not belt-and-braces:
`test/configuration_schema_test.py` records that the harness drives BSWCodeGen through its
Python API and never validates against the schema, and that the two "drifted" once already.
That is why the identification rule is enforced twice, and why both are specified here.

---

## 5. Testing

**Two existing tests change by design.** `test/build_checksum_test.py`'s
`test_build_checksum_returns_err_out_of_range_if_checksum_function_is_null` and
`..._if_checksum_type_is_out_of_range` now assert `(0xFE, 0x20)`, and gain an
`SduLength == 2` assertion so "no payload" is actually checked.

**New behavioural tests.** The `block_size == 0` path has no test at all today and is closed
here alongside the new one:

| Case | Assertion |
|:--|:--|
| `block_size == 0` | `(0xFE, 0x22)`, `SduLength == 8` |
| `block_size > max` | `(0xFE, 0x22)`, `SduLength == 8` |
| payload content | bytes 2,3 `== 0`; bytes 4..7 `== max` via `u32_from_array(..., byte_order)`, over `byte_orders` |
| `block_size == max` | succeeds — the off-by-one guard |
| MTA after a rejection | unchanged, observed through the first address the *next* request reads |

`SduLength` carries real weight: the suite's pervasive `SduDataPtr[0:2]` idiom cannot see a
payload at all, so without it these tests would pass whether or not the DWORD is ever written.

**Known-answer vectors (DD120).** 1.1/§1.6.1.2.9's pattern is 32 **bytes** — `0x01`..`0x10`,
`0xF1`..`0xFF`, `0x00` — supplied at consecutive addresses through the existing
`read_slave_memory` mock instead of `generate_random_block_content`.

It is a byte stream, not a list of element values, and the distinction is load-bearing: the
mock places those 32 bytes in memory and lets the configured granularity and byte order decide
what elements they form, which is precisely what makes the Intel and Motorola columns differ.
So `block_size` is **32 under BYTE, 16 under WORD and 8 under DWORD** granularity — the
existing parametrize already pairs `ADD_22`/`ADD_24` with WORD and `ADD_44` with DWORD. Below,
**Intel is `LITTLE_ENDIAN` and Motorola is `BIG_ENDIAN`**:

| Algorithm | Intel | Motorola |
|:--|:--|:--|
| `XCP_ADD_11` | `0x10` | `0x10` |
| `XCP_ADD_12` | `0x0F10` | `0x0F10` |
| `XCP_ADD_14` | `0x00000F10` | `0x00000F10` |
| `XCP_ADD_22` | `0x1800` | `0x0710` |
| `XCP_ADD_24` | `0x00071800` | `0x00080710` |
| `XCP_ADD_44` | `0x140C03F8` | `0xFC040B10` |
| `XCP_CRC_16` | `0xC76A` | `0xC76A` |
| `XCP_CRC_16_CITT` | `0x9D50` | `0x9D50` |
| `XCP_CRC_32` | `0x89CD97CE` | `0x89CD97CE` |

The 1.1 PDF is a scanned OCR dump and this table is damaged in it (`Ay10`, `CHIT`,
`OxC/76A`), and 1.0 has no clean copy to arbitrate against because it lacks the tables
entirely. Every value above was therefore **recomputed independently** from the pattern and
the spec's own CRC parameters (poly, init, refin, refout, xorout), and the OCR readings kept
only where they agreed — all nine did, on both byte orders. The three ADD variants that differ
between columns make these a byte-order conformance test as well, on the axis
`build_checksum_test.py` already parametrizes.

These reuse the nine `checksum_type` configurations the suite already builds, so they add **no
new compiled modules** — which matters, because the suite's transient failures scale with
module count (`test.sh`).

**Configuration refusal, at both gates:**

- `test/configuration_schema_test.py` — omitting the field, and `0`, each raise
  `jsonschema.ValidationError`.
- DD119's guard — `pytest.raises(UndefinedError)` at DWORD granularity with a maximum near
  `0xFFFFFFFF`, **plus a companion test** showing the same configuration generates cleanly at
  a legal value. The companion is not optional: `raise` is a deliberately-undefined Jinja
  global, so *every* guard in the template surfaces the identical `'raise' is undefined`, and
  the assertion alone cannot show which one fired or that the configuration failed for the
  intended reason.

---

## 6. Out of scope, and findings recorded in passing

Out of scope: per-segment checksum configuration (DD115), and `EXTERNAL_FUNCTION` per
segment for the same reason — `user_defined_checksum_function` stays one global callback.

Found while designing this, and recorded rather than silently fixed:

**D17 — `ERR_GENERIC` never carries its 1.1/§1.1.3.3 WORD.** All five call sites
(`source/Xcp_Std.c` once, `source/Xcp_Pgm.c` four times) answer through plain
`Xcp_FillErrorPacket`, while the UNLOCK branch's own comment cites §1.1.3.3's "implementation
specific slave device error code" as its justification for *choosing* that code — then omits
the payload that sentence describes. This is D6's shape one error code over. It touches UNLOCK
and the PGM group rather than checksum, so it gets its own entry instead of riding along here.

**The D6 entry's citation is stale.** It points at `source/Xcp.c:2639` for the checksum-type
mapping; that line is now inside `Xcp_StartNextTransmission` (defined at `source/Xcp.c:2621`), and the
mapping lives wholly in `source/Xcp_Std.c`.

**`config/xcp.schema.json` writes `"OneOf"` where JSON Schema defines `oneOf`.** jsonschema
ignores unknown keywords, so `user_defined_checksum_function` is currently unvalidated and a
configuration could name any function at all. Tracked separately.

Roadmap edits belonging to this work, all four in
`docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`:

1. §3's D6 entry → fixed, carrying DD115–DD120, and its stale `source/Xcp.c:2639` citation
   corrected to `source/Xcp_Std.c`.
2. §2.6's **"Extended error payloads" table row** → *partial* to done.
3. §2.6's closing **prose observation** on per-segment checksum configuration → rewritten to
   stand on its own, per DD115. It currently reads as something that "belongs with D6"; with
   D6 fixed and the reconciliation deferred, it needs to name itself as open work rather than
   hang off a closed defect. §3's sentence binding D6 to it ("D6 remains open and travels
   with…") goes at the same time.
4. A new D17 entry for the `ERR_GENERIC` payload gap above.

Items 2 and 3 are distinct edits to the same section and both are required — a plan that
treats §2.6 as one change will leave the observation pointing at a fixed defect.

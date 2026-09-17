# Per-segment checksum configuration

**Scope:** let a calibration segment declare its own checksum type, maximum block size and
user-defined function, overriding the global ones for a `BUILD_CHECKSUM` whose MTA falls inside it.
Closes the open note at the end of the roadmap's §2.6, left there by D6 (DD115).

**Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. §1.6.1.2.9
and §2.1's AML were read with `pdftotext -layout` on 1.0 (lines 2426 and 6140); 1.1 carries both
unchanged.

---

## 1. What this is, and what it is not

DD115 described the gap as needing "reconciling", which reads as a mismatch to be fixed. **Nothing
is mismatched, and this is worth stating before building anything**, because it sets what success
means.

Three facts, each checked rather than recalled:

1. **A2L generation is an explicit non-goal of this project** (roadmap §5: "ASAM MCD 2MC / A2L
   description file generation (Part 2 §2)"). The module never emits the AML's `CHECKSUM` block. An
   integrator writes it in their own A2L.
2. **The block is optional, and so is everything inside it.** §2.1's AML puts `CHECKSUM` in a
   `taggedstruct { /* optional */ }` inside `SEGMENT`, with `MAX_BLOCK_SIZE` and
   `EXTERNAL_FUNCTION` in a further `taggedstruct` within it. A slave with one global checksum
   configuration is therefore *truthfully describable today*: repeat the same block per segment, or
   omit it entirely.
3. **`BUILD_CHECKSUM` never mentions segments.** §1.6.1.2.9 works from the MTA and block size
   alone, and its positive response carries the checksum type in byte 1 — so the protocol
   accommodates a slave whose type varies without requiring one, because every response announces
   which type produced it.

So the module today has no conformance gap here. What it has is a **capability limitation**: an
integrator whose segments genuinely need *different* checksum configurations cannot express that,
because the slave cannot behave that way. This design adds that capability. It does not fix a
defect, and the roadmap note should stop implying one.

### DD143 — an override, not a replacement, which dissolves DD115's blocker

DD115 deferred this work partly because introducing address-to-segment resolution "would force an
answer to 'the MTA is in no configured segment', which neither 1.0 nor 1.1 defines".

Making per-segment configuration an **optional override over the retained global** removes the
question. An MTA in no configured segment uses the global, which is exactly what every build does
today. The undefined case only bites if per-segment configuration *replaces* the global, which is
why this design does not do that.

The same shape covers a segment that declares no `checksum` block, and a build with no segments at
all. Every existing configuration keeps its current behaviour by construction, not by testing.

## 2. Resolution

### DD144 — resolve from the MTA alone

`Xcp_SegmentForAddress(const void *address, uint8 addressExtension)` returns the first configured
segment whose `addressExtension` matches and whose `[address, address + length)` contains the
address, or `NULL_PTR`.

This is the module's first address-to-segment lookup. Today `Xcp_SegmentType`'s `address` and
`length` are read only to *report* `GET_SEGMENT_INFO`; segments are otherwise reached solely by an
index the master supplies on the wire.

Two rules the specification does not address, settled here:

- **Overlapping segments resolve to the first match in configuration order.** The schema does not
  forbid overlap, and first-match is deterministic and cheap. No ordering is imposed on the
  configuration, so an integrator who overlaps segments chooses the winner by declaration order.
- **A zero-length segment matches nothing.** Its half-open range is empty.

### DD145 — the block may span out of the segment, and is checksummed with it anyway

`BUILD_CHECKSUM` covers `[MTA, MTA + element_size × block_size)`, which can start inside one segment
and end past it, or inside another declaring something different.

The segment containing the **start address** decides, and the whole block is checksummed with its
configuration. §1.6.1.2.9 calls it "the memory block that is defined by the MTA and Block size" —
the MTA is what locates it.

Refusing a spanning block was considered and rejected: it would change behaviour for blocks that
span freely today and work, including in every build with no per-segment overrides at all, which
breaks the property DD143 exists to preserve. Refusing only on a genuine conflict between the
segments a range touches was also rejected — it needs the resolution to walk the whole range rather
than one address, and needs its own answer for a range partly inside a segment and partly outside
any, which is DD115's undefined case returning by another door.

The result is self-describing on the wire: the response's type byte tells the master which type
actually produced the checksum, even where that differs from what its A2L says about the far end of
the range.

## 3. The design

### DD146 — flat fields with illegal-value sentinels, and the AML's structure enforced at generation

`Xcp_SegmentType` (`interface/Xcp_Types.h`) gains three fields:

| Field | "Not declared" sentinel | Why that value is safe |
|:--|:--|:--|
| `const Xcp_ChecksumType checksumType` | `XCP_CHECKSUM_TYPE_NOT_DECLARED` | a new enumerator appended to `Xcp_ChecksumType`; see the correction below |
| `const uint32 checksumMaxBlockSize` | `0x00000000u` | the schema's minimum is 1 (DD116), and a bound of 0 would reject every request since `block_size == 0` already fails |
| `void *(*const userDefinedChecksumFunction)(...)` | `NULL_PTR` | already the global field's "absent" value |

No presence flags: each field has a value that cannot mean anything else.

**Corrected before implementation began.** This table first gave the type field as `const uint8`
with `0x00u` for "not declared", reasoning that §1.6.1.2.9's wire types are `0x01`–`0x09` and `0xFF`
so 0 is not one of them. That is true of the **wire** values and false of this module's
representation: `checksumType` is an `Xcp_ChecksumType` (`interface/Xcp_Types.h`), a C enum whose
first enumerator `XCP_ADD_11` is **0**. A 0 sentinel would have made every segment declaring
`XCP_ADD_11` read as declaring nothing — silently, since the fallback would then produce the global
type, which in most configurations *is* `XCP_ADD_11`. The mistake came from reading the
specification's table and assuming the code stored those numbers; the handler in fact `switch`es on
the enum and assigns the wire value per case.

`Xcp_ChecksumType` therefore gains `XCP_CHECKSUM_TYPE_NOT_DECLARED` as a final enumerator. Appending
is safe: every existing enumerator keeps its ordinal, and the generator emits names rather than
numbers (`script/source_cfg.c.jinja2` writes `{{configuration.protocol_layer.checksum_type}}`
verbatim).

This is also the strongest argument the rejected pointer-per-segment alternative had — `NULL_PTR`
would have needed no sentinel reasoning at all. It does not reverse the decision: one appended
enumerator is cheaper than a generated array and a pointer hop, and the other two fields needed no
new value.

The alternative — a `const Xcp_SegmentChecksumType *` per segment, `NULL_PTR` when absent — models
the AML more literally, since its `CHECKSUM` block carries a *mandatory* type once present. It was
rejected because the only thing that fidelity buys is the constraint "declaring the block means
declaring the type", and that is a build-time rule. It is enforced in the schema instead: a segment's
optional `checksum` object requires `checksum_type` within it. Paying a generated array and a
pointer hop on every `BUILD_CHECKSUM` for a rule the generator can state is the wrong trade.

Replacing the global outright was rejected in DD143.

### DD147 — the error payload must report the bound that applied

`Xcp_BuildChecksumFillMaxBlockSize` (`source/Xcp_Std.c`) reads the global `checksumMaxBlockSize` and
writes it into `ERR_OUT_OF_RANGE`'s payload — the DWORD §1.1.3.3 requires that response to carry,
which D6 added.

With per-segment bounds it must report the **resolved** one. A slave that refuses a request against
a segment's bound and then names the global bound tells the master a limit that does not apply to
the address it asked about. That is worse than the pre-D6 state of reporting nothing: it is
confidently wrong, and a master has no way to detect it.

So the helper takes the resolved bound as a parameter, and the handler's order changes: resolution
first, bound check second. Today the bound check is the first thing `Xcp_DTOCmdStdBuildChecksum`
does. Resolution must not depend on the block size, which it does not — it uses the MTA only.

### DD148 — two generation guards

Both in `script/source_cfg.c.jinja2`, using the same deliberately-undefined `raise(...)` global as
every other guard there:

- A segment declaring `checksum_type: XCP_USER_DEFINED` with neither its own
  `user_defined_checksum_function` nor a global one to fall back to is refused. That configuration
  reaches a `NULL_PTR` call at runtime, and the fallback makes the condition a conjunction rather
  than a per-segment check.
- A segment's `checksum_max_block_size` gets the `uint32` overflow check DD119 already applies to
  the global one: the product with address granularity must still fit.

## 4. Testing

Resolution is observable from the wire through the response's own type byte, so none of these reach
into the module: a segment declaring `XCP_CRC_16` against a global `XCP_ADD_11` answers `0x07` in
byte 1 when the MTA is inside it and `0x01` when it is not.

- **The override applies, and only where it should.** MTA inside an overriding segment uses that
  segment's type, bound and callback; MTA in no segment uses the global; a segment declaring no
  `checksum` object uses the global. The last two are today's behaviour, so every existing
  `BUILD_CHECKSUM` test must stay green unchanged.
- **Partial override.** A segment declaring only `checksum_type` takes its type from the segment and
  its bound from the global. This is what flat sentinels exist to serve, and the case that would
  catch them being read as a unit.
- **The error payload carries the resolved bound (DD147).** A segment whose bound is *smaller* than
  the global, with a request above the segment's bound: `ERR_OUT_OF_RANGE` must carry the segment's
  DWORD. A test asserting only the error code passes either way, which is how a confidently wrong
  number would ship.
- **Spanning (DD145).** A block starting inside an overriding segment and running past its end is
  checksummed with that segment's configuration, asserted through the type byte.
- **Overlap (DD144).** Two segments containing one address resolve to the first declared.
- **Generation guards (DD148).** `XCP_USER_DEFINED` per segment with no callback anywhere, and a
  per-segment bound overflowing `uint32` — each paired with an accepting case, since every guard in
  that template surfaces the identical `'raise' is undefined` and the pair is what identifies which
  one fired.

## 5. Out of scope

**A2L generation** remains a non-goal (roadmap §5). This design lets the module *behave* the way a
per-segment `CHECKSUM` block describes; writing that block stays the integrator's job.

**Per-segment checksum configuration for any command other than `BUILD_CHECKSUM`.** No other command
consults the checksum configuration.

**Validating that a segment's declared configuration matches the integrator's A2L.** The module has
never read an A2L and does not start here.

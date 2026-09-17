# Per-Segment Checksum Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a calibration segment override the global checksum type, maximum block size and user-defined function for a `BUILD_CHECKSUM` whose MTA falls inside it.

**Architecture:** Three optional fields on `Xcp_SegmentType`, each with an illegal-value sentinel meaning "not declared". A new `Xcp_SegmentForAddress` resolves the MTA to a segment; `Xcp_DTOCmdStdBuildChecksum` reads each value as "segment's, if declared; otherwise global". The global is retained, so an MTA in no segment behaves exactly as today.

**Tech Stack:** C (AUTOSAR MISRA style), pytest + CFFI compiling the real C, CMake/ctest, Docker.

**Spec:** `docs/superpowers/specs/2026-09-17-xcp-per-segment-checksum-design.md` (DD143–DD148)

## Global Constraints

- **Reference revision:** XCP Part 2 1.1 alongside 1.0; comments cite with the revision prefix.
- **Tests run in Docker only**, image `xcp-build:local`:
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
    --volume "$PWD:/usr/project" --workdir /usr/project xcp-build:local ./test.sh
  ```
  ~7 minutes. `-x` is hardcoded at `CMakeLists.txt:307`; to collect all failures in one run, seed `XCP_PYTEST_ARGS="--maxfail=200"` into the CMake cache and **clear it to `""` afterwards**.
- **Baseline:** 13029 passed, 29 skipped, 2/2 ctest targets, exit 0.
- **DD143's invariant:** any configuration declaring no per-segment `checksum` must behave exactly as before. Every pre-existing `BUILD_CHECKSUM` test staying green unchanged is the evidence.
- **Coverage:** every new branch needs a test aimed at it. The SERV PR shipped an uncovered queue-full branch because no test reached it by accident; error and fallback paths are exactly that shape.

---

### Task 1: Resolution and the configuration fields

No observable behaviour change: nothing declares an override yet, so every sentinel reads as "use the global".

**Files:** `interface/Xcp_Types.h`, `config/xcp.schema.json`, `script/source_cfg.c.jinja2`, `source/Xcp_Internal.h`, `source/Xcp.c`

- [ ] **Step 1: Add the three fields** to `Xcp_SegmentType` in `interface/Xcp_Types.h`, after `addressMapping`, documenting each sentinel:

```c
    /**
     * @brief this segment's own checksum type, or 0 to use the global one.
     * @note XCP part 2 - Protocol Layer Specification 1.1/2.1's AML declares a CHECKSUM block
     * inside each SEGMENT, carrying the type, MAX_BLOCK_SIZE and EXTERNAL_FUNCTION. All three are
     * optional here and fall back to protocol_layer's, so a configuration declaring none behaves
     * exactly as it did before they existed (DD143). 0 is safe as "not declared": 1.1/1.6.1.2.9's
     * types are 0x01..0x09 and 0xFF.
     */
    const uint8 checksumType;

    /**
     * @brief this segment's own maximum block size, or 0 to use the global one.
     * @note 0 is safe as "not declared": the schema's minimum is 1 (DD116), and a bound of 0 would
     * reject every request anyway, block_size == 0 already failing.
     */
    const uint32 checksumMaxBlockSize;

    /**
     * @brief this segment's own checksum callback, or NULL_PTR to use the global one.
     */
    void *(*const userDefinedChecksumFunction)(void *lowerAddress, const void *upperAddress, uint32 *pResult);
```

- [ ] **Step 2: Add the optional schema object** inside the segment definition in `config/xcp.schema.json`: an optional `"checksum"` object with `"checksum_type"` (the same enum the global one uses) **required** within it, and optional `"checksum_max_block_size"` (integer, minimum 1) and `"user_defined_checksum_function"` (string). Requiring the type once the object is present is the AML's own structure, `CHECKSUM` carrying a mandatory type once declared.

- [ ] **Step 3: Generate the fields.** In `script/source_cfg.c.jinja2`'s `Xcp_SegmentConfig` loop (line ~537), emit three more initialisers per segment, and extend the sentinel row:

```jinja
        {% if segment.checksum is defined %}XCP_{{segment.checksum.checksum_type[4:]}}{% else %}0x00u{% endif %},
        {% if segment.checksum is defined and segment.checksum.checksum_max_block_size is defined %}{{'0x%08Xu' % segment.checksum.checksum_max_block_size}}{% else %}0x00000000u{% endif %},
        {% if segment.checksum is defined and segment.checksum.user_defined_checksum_function is defined %}&{{segment.checksum.user_defined_checksum_function}}{% else %}NULL_PTR{% endif %}
```

Match the existing `checksum_type` emission for the global field — read how `protocol_layer.checksum_type` is emitted and use the identical expression, rather than the `[4:]` slice above if that is not how it is done. The sentinel row gains `, 0x00u, 0x00000000u, NULL_PTR`.

- [ ] **Step 4: Declare the resolver** in `source/Xcp_Internal.h` beside the other internal helpers:

```c
const Xcp_SegmentType *Xcp_SegmentForAddress(const void *address, uint8 addressExtension);
```

- [ ] **Step 5: Define it** in `source/Xcp.c`:

```c
const Xcp_SegmentType *Xcp_SegmentForAddress(const void *address, uint8 addressExtension)
{
    const Xcp_SegmentType *p_result = NULL_PTR;
    uint8_least idx;

    /* DD144. The module's first address-to-segment lookup: Xcp_SegmentType's address and length
     * are read in exactly one other place, Xcp_DTOCmdPagGetSegmentInfo, and only to report them.
     * Segments are otherwise reached by an index the master supplies on the wire.
     *
     * First match wins where segments overlap -- the schema does not forbid overlap, and
     * declaration order is the only ordering an integrator controls. A zero-length segment matches
     * nothing: its half-open range is empty. Neither rule comes from the specification, which does
     * not discuss resolving an address to a segment at all. */
    for (idx = 0x00u; (idx < Xcp_Ptr->general->maxSegment) && (p_result == NULL_PTR); idx++)
    {
        const Xcp_SegmentType *p_segment = &Xcp_Ptr->config->segment[idx];
        const uint32 segment_address = p_segment->address;

        if ((p_segment->addressExtension == addressExtension) &&
            (p_segment->length > 0x00000000u) &&
            ((uint32)address >= segment_address) &&
            (((uint32)address - segment_address) < p_segment->length))
        {
            p_result = p_segment;
        }
    }

    return p_result;
}
```

The subtraction form avoids `segment_address + length` overflowing a `uint32`. Cast style must match how `source/Xcp_Std.c` already converts between `void *` and `uint32` — copy that idiom rather than inventing one; check `Xcp_DTOCmdStdShortUpload`.

- [ ] **Step 6: Run the full suite.** Expect **13029 passed, 29 skipped**, exit 0 — unchanged. Nothing reads the new fields yet.

- [ ] **Step 7: Commit.**

```bash
git add interface/Xcp_Types.h config/xcp.schema.json script/source_cfg.c.jinja2 source/Xcp_Internal.h source/Xcp.c
git commit -m "feat: resolve an address to a calibration segment (DD144)"
```

---

### Task 2: BUILD_CHECKSUM honours the override

**Files:** `source/Xcp_Std.c`, `test/build_checksum_segment_test.py` (create)

- [ ] **Step 1: Write the failing tests.** Create `test/build_checksum_segment_test.py` with three: the override applying (segment declares `XCP_CRC_16` against a global `XCP_ADD_11`; MTA inside it answers type `0x07`), the global applying when the MTA is outside every segment (answers `0x01`), and the partial override (segment declares only the type; its bound comes from the global, proven by a request above the segment's absent bound but below the global's succeeding).

Use `test/build_checksum_test.py`'s existing configuration and MTA idiom — read it first and match how it sets the MTA via `SET_MTA` and reads the response's type byte.

- [ ] **Step 2: Run them.** Expect FAIL: the response carries the global type regardless of the MTA.

- [ ] **Step 3: Resolve at the top of the handler.** In `Xcp_DTOCmdStdBuildChecksum`, before the block-size check:

```c
    const Xcp_SegmentType *p_segment = Xcp_SegmentForAddress(Xcp_Internal.memory_transfer.address,
                                                             Xcp_Internal.memory_transfer.extension);

    /* DD143/DD145. The segment containing the MTA decides for the whole block, even where the block
     * runs past that segment's end: 1.1/1.6.1.2.9 calls it "the memory block that is defined by the
     * MTA and Block size", and the MTA is what locates it. Refusing a spanning block would change
     * behaviour for builds with no overrides at all, which is the one thing this feature must not
     * do.
     *
     * Each value falls back to the global when the segment does not declare it, or when the MTA is
     * in no segment at all -- which is what every build does today, and why "the MTA is in no
     * configured segment" needs no answer from a specification that does not give one (DD143). */
    const uint8 checksum_type_config =
        ((p_segment != NULL_PTR) && (p_segment->checksumType != 0x00u))
            ? p_segment->checksumType : Xcp_Ptr->general->checksumType;
    const uint32 max_block_size =
        ((p_segment != NULL_PTR) && (p_segment->checksumMaxBlockSize != 0x00000000u))
            ? p_segment->checksumMaxBlockSize : Xcp_Ptr->general->checksumMaxBlockSize;
```

Declare these with the function's other locals if declaration-after-statement is not used in this file — check the surrounding style.

- [ ] **Step 4: Use them.** Replace `Xcp_Ptr->general->checksumMaxBlockSize` in the bound check with `max_block_size`, and `switch (Xcp_Ptr->general->checksumType)` with `switch (checksum_type_config)`. In the `XCP_USER_DEFINED` case, replace `Xcp_Ptr->general->userDefinedChecksumFunction` with the segment's when it is non-NULL:

```c
                checksum_function = ((p_segment != NULL_PTR) &&
                                     (p_segment->userDefinedChecksumFunction != NULL_PTR))
                                        ? p_segment->userDefinedChecksumFunction
                                        : Xcp_Ptr->general->userDefinedChecksumFunction;
```

- [ ] **Step 5: DD147 — the error payload reports the resolved bound.** Change `Xcp_BuildChecksumFillMaxBlockSize(void)` to take `uint32 maxBlockSize` and write that instead of the global, updating its forward declaration and its one call site. Add above it:

```c
/* DD147. The bound that actually applied, not the global one. A slave that refuses a request
 * against a segment's bound and then names the global bound in ERR_OUT_OF_RANGE's payload -- the
 * DWORD 1.1/1.1.3.3 requires that response to carry -- tells the master a limit that does not apply
 * to the address it asked about. That is worse than the pre-D6 state of carrying no payload at all:
 * it is confidently wrong, and the master cannot tell. */
```

- [ ] **Step 6: Write the DD147 test.** A segment whose `checksum_max_block_size` is *smaller* than the global, with a request above the segment's bound: assert `ERR_OUT_OF_RANGE` **and** that bytes 4..7 carry the segment's value, not the global's.

- [ ] **Step 7: Run the full suite.** Expect the baseline plus the new tests, exit 0. **Every pre-existing `BUILD_CHECKSUM` test must be green unchanged** — that is DD143's invariant, and any failure there means the fallback is wrong rather than the test.

- [ ] **Step 8: Commit.**

```bash
git add source/Xcp_Std.c test/build_checksum_segment_test.py
git commit -m "feat: BUILD_CHECKSUM honours a segment's checksum configuration (DD143, DD145, DD147)"
```

---

### Task 3: Spanning, overlap and the user-defined callback

**Files:** `test/build_checksum_segment_test.py`

- [ ] **Step 1: Write three tests.** A block starting inside an overriding segment and running past its end answers that segment's type (DD145). Two segments containing one address resolve to the first declared (DD144). A segment declaring `XCP_USER_DEFINED` with its own callback invokes *that* callback and not the global one — assert on which mock was called, not only on the resulting checksum.

- [ ] **Step 2: Run the full suite.** Expect the previous count plus three, exit 0.

- [ ] **Step 3: Commit.**

```bash
git add test/build_checksum_segment_test.py
git commit -m "test: spanning, overlap and a per-segment checksum callback"
```

---

### Task 4: Generation guards (DD148)

**Files:** `script/source_cfg.c.jinja2`, `test/build_checksum_segment_test.py`

- [ ] **Step 1: Write the failing tests** — four, in two pairs, since every guard in that template raises the identical `'raise' is undefined` and only the pair identifies which fired: a segment with `XCP_USER_DEFINED` and no callback anywhere refused / the same with a global callback accepted; a per-segment bound whose product with address granularity overflows `uint32` refused / the largest that does not, accepted.

- [ ] **Step 2: Run them.** Expect FAIL — the configurations currently generate.

- [ ] **Step 3: Add both guards** beside the existing `max_cto` pair, following their `raise(...)` idiom and message style: name the offending value, cite the rule, and say what to change.

- [ ] **Step 4: Run the full suite.** Expect the previous count plus four, exit 0.

- [ ] **Step 5: Commit.**

```bash
git add script/source_cfg.c.jinja2 test/build_checksum_segment_test.py
git commit -m "feat: refuse per-segment checksum configurations that cannot work (DD148)"
```

---

### Task 5: Roadmap

**Files:** `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`

- [ ] **Step 1:** Update the pass count.
- [ ] **Step 2:** Replace §2.6's "**Open: per-segment checksum configuration**" paragraph with a done entry that also corrects its framing: this was a capability limitation, not a reconciliation — A2L generation is a non-goal, the AML block is optional, and `BUILD_CHECKSUM`'s response carries its own type, so the global configuration was always describable. Name the design doc and DD143–DD148.
- [ ] **Step 3:** Note that §2.6 now has no open items.
- [ ] **Step 4: Commit.**

---

## Verification before the PR

- [ ] Full suite in Docker at the final commit, 2/2 ctest targets, exit 0.
- [ ] `git status --porcelain` clean; `XCP_PYTEST_ARGS` empty.
- [ ] `build/Xcp.c.gcov` and `build/Xcp_Std.c.gcov` show no `#####` in new code — the SERV PR's coverage regression was exactly this check not being run.

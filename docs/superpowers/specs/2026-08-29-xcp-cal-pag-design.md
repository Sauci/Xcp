# SP1 — Calibration and page switching

**Date:** 2026-08-29
**Baseline:** branch `develop`, commit `b21724c`
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.0*, ASAM e.V., 2003-04-08
**Roadmap:** `2026-08-29-xcp-part2-roadmap.md`

Completes the calibration command group (§1.6.2) and implements the page switching command
group (§1.6.3), including the segment and page configuration model both require.

---

## 1. Scope

**In scope**

| | |
|:--|:--|
| §1.6.2.1.1 | `DOWNLOAD` — complete the existing partial implementation |
| §1.6.2.2.1 | `DOWNLOAD_NEXT` |
| §1.6.2.2.2 | `DOWNLOAD_MAX` |
| §1.6.2.2.3 | `SHORT_DOWNLOAD` |
| §1.6.2.2.4 | `MODIFY_BITS` |
| §1.6.3.1.1 | `SET_CAL_PAGE` |
| §1.6.3.1.2 | `GET_CAL_PAGE` |
| §1.6.3.2.1 | `GET_PAG_PROCESSOR_INFO` |
| §1.6.3.2.2 | `GET_SEGMENT_INFO` |
| §1.6.3.2.3 | `GET_PAGE_INFO` |
| §1.6.3.2.4 | `SET_SEGMENT_MODE` |
| §1.6.3.2.5 | `GET_SEGMENT_MODE` |
| §1.6.3.2.6 | `COPY_CAL_PAGE` |
| §1.7.3.2.2–3 | the CAL and PAG error matrices |

Plus roadmap defects D1 through D5.

**Out of scope** — DAQ, STIM, PGM, §1.7.2 time-out handling and the interleaved
communication model, RESUME mode, `GET_ID` identification types 1–4 and 128–255,
`SET_DAQ_LIST_CAN_ID`, and the extended error payloads of §1.1.3.3 beyond the
`DOWNLOAD_NEXT` one required here.

## 2. What already exists

Three generic mechanisms are complete for these commands and must not be rebuilt.

- **`Xcp_CTOErrorMatrix`** already encodes §1.7.3.2.2 and §1.7.3.2.3 for all thirteen
  commands. Every row was compared against the specification tables entry by entry, along
  with all fifteen rows of §1.7.3.2.1, and all match — the matrix needs no change in this
  sub-project. It drives only the *generic pre-checks* performed in `Xcp_CanIfRxIndication`:
  `ERR_CMD_UNKNOWN`, `ERR_CMD_BUSY`, `ERR_CMD_SYNTAX`, `ERR_PGM_ACTIVE`. Errors a handler
  raises itself do not consult it, so a handler may emit an error the matrix does not list.
- **`Xcp_PIDToCmdGroupTable`** already maps 0xE4–0xF0 to
  `XCP_RESOURCE_PROTECTION_STATUS_MASK_CAL_PAG`, so seed-and-key protection works.
- **`ctoInfo[]`** already carries a correct minimum request size for every command in this
  sub-project. The one exception is `DOWNLOAD_MAX`, whose true minimum is `MAX_CTO` and
  cannot be expressed in a four-bit field; its handler checks the length itself, as
  `TRANSPORT_LAYER_CMD` already does.

Block transfer is likewise complete but unreachable. `Xcp_BlockTransferWriteSlaveMemory`
writes one frame's worth of elements through `Xcp_WriteSlaveMemoryTable`, post-increments
the MTA, decrements `requested_elements` and returns `E_NOT_OK` on the final frame. It has
no caller. `DOWNLOAD` needs to call it, not to reimplement it.

## 3. Design decisions

**DD1 — Split the source before adding to it.** `source/Xcp.c` is 3876 lines and this work
adds roughly 1200 to 1600 more. The split is a move-only refactor performed first, verified
by the existing suite passing unchanged. One deviation, recorded after the fact: handler
prototypes on `Xcp.c` each carried a `Xcp_START_SEC_CODE_FAST` / `Xcp_MemMap.h` pair, and the
prototypes moved into `Xcp_Internal.h` as a bare block without them. The definitions were never
wrapped on either side of the split, so the sections placed no code and the loss is one of
consistency rather than behaviour, but the refactor is not strictly move-only.

**DD2 — Segments and pages are declared in configuration; the integrator owns activation.**
The module validates segment number, page number and mode against generated configuration
and answers `GET_PAG_PROCESSOR_INFO`, `GET_SEGMENT_INFO` and `GET_PAGE_INFO` from it
directly, because those are static properties. The three operations that concern *live*
page state — activating a page, reading back which page is active, and copying a page — are
delegated to the integrator. This matches how seed-and-key, memory access, checksum and
user commands already work, and it keeps spec-conformant error codes out of integrator
code.

**DD6 — The test harness compiles real translation units.** After the split, `CMakeLists.txt`
builds five translation units. The harness compiles the same five separately rather than
`#include`-ing them into one, so the suite exercises the linkage the shipped library
actually uses: a helper left `static` in one unit but called from another fails the tests
instead of passing them and failing the library build. Per-file coverage falls out of this
for free. Nothing is lost, because the harness never depended on single-unit symbol
visibility — see §4.2.

**DD3 — `DOWNLOAD_MAX` and `SHORT_DOWNLOAD` inside a block transfer return
`ERR_SEQUENCE`.** §1.6.2.2.2 and §1.6.2.2.3 state both "mustn't be used within a block
transfer sequence" but prescribe no error code, and neither appears with `ERR_SEQUENCE` in
§1.7.3.2.2. The error matrix constrains what a *master* must be prepared to handle, not
what a slave may emit; `ERR_SEQUENCE` is the accurate code and leaves the master able to
recover. The pending block transfer is aborted.

**DD4 — Where §1.6.3 prose and §1.7.3.2.3 disagree, the resolution is recorded per
command.** Three such divergences exist, each noted inline in §8 below: `GET_PAGE_INFO`
(prose says `ERR_OUT_OF_RANGE`, matrix says `ERR_PAGE_NOT_VALID` / `ERR_SEGMENT_NOT_VALID`),
`GET_SEGMENT_INFO` (prose says an unavailable segment returns `ERR_OUT_OF_RANGE`, matrix lists
`ERR_SEGMENT_NOT_VALID`, and this implementation follows the matrix so that every PAG command
reports a bad segment identically, reserving `ERR_OUT_OF_RANGE` for a bad mode, `SEGMENT_INFO`
or `MAPPING_INDEX`), and `COPY_CAL_PAGE` (prose mandates `ERR_WRITE_PROTECTED`, matrix omits
it).

**DD5 — `SHORT_DOWNLOAD` transfers nothing at `MAX_CTO = 8`, but ships enabled.** Its
capacity is `(MAX_CTO-8)/AG` elements, which is zero when `MAX_CTO = 8`. §1.6.2.2.3 says so
outright: the command "will have no effect (no data bytes can be transferred) if MAX_CTO = 8
(e.g. XCP on CAN)". This originally led `config/xcp.json` to ship with it off, which was wrong
for a second reason that only became visible once the command existed: §1.6.1.1.1 defines the
CONNECT `RESOURCE` CAL/PAG bit as asserting that `DOWNLOAD`, `DOWNLOAD_MAX`, `SHORT_DOWNLOAD`,
`SET_CAL_PAGE` and `GET_CAL_PAGE` are all available, so disabling it made the slave advertise
no calibration or paging support at all. It ships enabled; an integrator running at
`MAX_CTO = 8` simply finds it accepts no payload, which the specification anticipates.

**DD6 — `DOWNLOAD_NEXT` shares `DOWNLOAD`'s minimum request size.** Its `ctoInfo` minimum was
`0x04` against `DOWNLOAD`'s `0x03`, an asymmetry 1.0's prose does not explain, so it was left
alone rather than changed on a guess. Version 1.1 settles it at §1.6.2.2.1: "The DOWNLOAD_NEXT
command has exactly the same structure as the DOWNLOAD command." Same structure means the same
minimum, so it is now `0x03`. A frame that is short of the payload it announces is caught by the
handler's own length check rather than by the dispatcher's generic gate, which reports
`ERR_SEQUENCE` or `ERR_CMD_SYNTAX` as the situation warrants instead of `ERR_CMD_SYNTAX` for
both.

### 3.1 A non-divergence worth recording

§1.6.2.1.1 gives the element count range as `[1..(MAX_CTO-2)/AG]` while the packet layout
places data at `AG..MAX_CTO-AG` for `AG > 1`, implying `(MAX_CTO-AG)/AG`. These appear to
disagree, but §1.6.1.1.1 requires `MAX_CTO mod AG = 0`, and under that constraint the two
expressions are equal for every valid configuration. No decision is needed. The module uses
the alignment-derived form already implemented by
`Xcp_GetNumberOfAlignmentBytes(2, elementSize, maxCto)`, which returns
`(MAX_CTO - 2) mod AG`; data begins at `2 + alignment` and capacity is
`(MAX_CTO - 2 - alignment)/AG`.

---

## 4. Source layout

### 4.1 File structure

| File | Contents |
|:--|:--|
| `source/Xcp.c` | `Xcp_Init`, `Xcp_MainFunction`, `Xcp_GetVersionInfo`, `Xcp_SetTransmissionMode`, the three `Xcp_CanIf*` callbacks, the three dispatch tables, the `Xcp_Internal` definition |
| `source/Xcp_Internal.h` | **new, private.** `Xcp_InternalType`, the `XCP_PID_CMD_*` / `XCP_INTERNAL_ERR_*` / mask macros, declarations of shared helpers |
| `source/Xcp_Std.c` | the fifteen STD handlers, the nine checksum functions, the CRC tables |
| `source/Xcp_Cal.c` | the five CAL handlers |
| `source/Xcp_Pag.c` | the eight PAG handlers |
| `source/Xcp_Daq.c` | the seventeen DAQ stubs, moved unchanged |

`Xcp_Internal.h` lives in `source/`, not `interface/` — integrators never see it.

Helpers shared across translation units lose `static` and gain a declaration in
`Xcp_Internal.h`: `Xcp_ReportError`, `Xcp_FinalizeResPacket`, `Xcp_FillErrorPacket`,
`Xcp_ElementSizeForAddressGranularity`, `Xcp_GetNumberOfAlignmentBytes`,
`Xcp_CopyFromU16WithOrder`, `Xcp_CopyFromU32WithOrder`, `Xcp_CopyToU16WithOrder`,
`Xcp_CopyToU32WithOrder`, `Xcp_BlockTransferIsActive`, `Xcp_DataTransferInitialize`,
`Xcp_BlockTransferAcknowledgeFrame`, `Xcp_BlockTransferReadSlaveMemory`,
`Xcp_BlockTransferWriteSlaveMemory`, `Xcp_GetProtectionStatus`, `Xcp_SetProtectionStatus`,
`Xcp_ClearProtectionStatus`, `Xcp_ReadSlaveMemoryTable`, `Xcp_WriteSlaveMemoryTable`.

Handler prototypes move to `Xcp_Internal.h` and lose `static` too. They cannot stay beside
`Xcp_PIDTable` in `Xcp.c`: a handler defined in `Xcp_Cal.c` needs its prototype visible in
that translation unit, both for `-Wmissing-prototypes` and for MISRA C:2012 Rule 8.4.

### 4.2 Test harness

The harness compiles the module today as a single translation unit, via
`set_source(name, '#include "…/Xcp.c"', …)`. **Nothing depends on that.** The CFFI `cdef` is
built from `interface/Xcp.h` alone, so file-scope symbols of `Xcp.c` were never visible to
Python in the first place; across the whole suite the tests reach only `Xcp_Init`,
`Xcp_MainFunction`, `Xcp_GetVersionInfo`, the three `Xcp_CanIf*` callbacks, and the
`Xcp_State` / `Xcp_Ptr` globals that `Xcp.h` exports under `CFFI_ENABLE`.

Per DD6 the harness therefore moves to real translation units. `cffi`'s `set_source`
forwards unknown keyword arguments to `distutils.Extension`, and `sources` is among them —
`ffiplatform.get_extension` prepends its own generated `.c` and appends the rest:

```python
self.code = MockGen('_cffi_xcp', '#include "Xcp.h"', header,
                    sources=tuple(self.sources), ...)
```

`conftest.py` accepts a semicolon-separated `--source` list, as it already does for
`--include_directories`; `CMakeLists.txt` adds the new files to `add_library` and passes the
same list through `--source`. The `extern "Python+C"` mocks that CFFI emits into
`_cffi_xcp.c` keep external linkage and resolve against the other units inside the same
shared object, so mocking is unaffected.

Consequences:

- `Xcp_ReportError` is `LOCAL_INLINE`, which `Compiler.h` defines as `static inline`. It
  moves into `Xcp_Internal.h` as a `static inline` definition so every unit has one. gcov
  then counts it per unit — cosmetic coverage noise, no behaviour change.
- `test.sh` runs `gcov _cffi_xcp.c`; it becomes a `gcov` invocation over each unit, which
  emits `Xcp.c.gcov`, `Xcp_Std.c.gcov`, `Xcp_Cal.c.gcov` and so on.
- `.github/workflows/test.yml` uploads the single path `./build/Xcp.c.gcov` to codecov. It
  must become a list or a glob, or coverage silently narrows to the dispatch layer.

The `sources=` path is not exercised on the development host, since `cffi` is not installed
there (§12). Verifying it against the untouched baseline is part of the environment task,
before any work depends on it.

### 4.3 Verification

The split lands as its own commit and changes no behaviour. Acceptance is the existing 55
tests passing unchanged, with the same skip list.

---

## 5. Error code completion

`interface/Xcp_Errors.h` gains the six codes from §1.7.3.1 that this work needs:

```c
#define XCP_E_ASAM_WRITE_PROTECTED   (0x23u)
#define XCP_E_ASAM_ACCESS_DENIED     (0x24u)
#define XCP_E_ASAM_PAGE_NOT_VALID    (0x26u)
#define XCP_E_ASAM_MODE_NOT_VALID    (0x27u)
#define XCP_E_ASAM_SEGMENT_NOT_VALID (0x28u)
#define XCP_E_ASAM_MEMORY_OVERFLOW   (0x30u)
```

The matching `XCP_INTERNAL_ERR_*` bits already exist and are already referenced by
`Xcp_CTOErrorMatrix`; only these wire values are missing. For completeness the remaining
unused codes — `ERR_DAQ_ACTIVE` (0x11), `ERR_DAQ_CONFIG` (0x2A), `ERR_GENERIC` (0x31),
`ERR_VERIFY` (0x32) — are added at the same time so the header is a complete transcription
of §1.7.3.1.

---

## 6. Segment and page configuration model

### 6.1 Schema

`config/xcp.schema.json` gains a `segments` array. Every field exists to answer a specific
response field in §1.6.3.2; nothing is speculative.

```json
{
  "name": "CAL_SEG_0",
  "address": 4198400,
  "length": 4096,
  "address_extension": 0,
  "compression_method": 0,
  "encryption_method": 0,
  "pages": [
    {
      "init_segment": 0,
      "ecu_access": "DONT_CARE",
      "xcp_read_access": "DONT_CARE",
      "xcp_write_access": "NOT_ALLOWED"
    }
  ],
  "address_mappings": [
    { "source_address": 0, "destination_address": 0, "length": 0 }
  ]
}
```

| Field | Answers |
|:--|:--|
| `address`, `length` | `GET_SEGMENT_INFO` mode 0, `SEGMENT_INFO` 0 and 1 |
| `address_extension` | `GET_SEGMENT_INFO` mode 1 |
| `compression_method`, `encryption_method` | `GET_SEGMENT_INFO` mode 1 |
| `pages` length | `GET_SEGMENT_INFO` mode 1, `MAX_PAGES` |
| `address_mappings` length | `GET_SEGMENT_INFO` mode 1, `MAX_MAPPING` |
| `address_mappings[i]` | `GET_SEGMENT_INFO` mode 2, `SEGMENT_INFO` 0, 1 and 2 |
| `init_segment` | `GET_PAGE_INFO`, `INIT_SEGMENT` |
| the three access enums | `GET_PAGE_INFO`, `PAGE_PROPERTIES` |
| `segments` length | `GET_PAG_PROCESSOR_INFO`, `MAX_SEGMENT` |

`address_mappings` may be empty. `pages` requires at least one entry.

`freeze_supported` is **module-level**, a sibling of `segments` rather than a per-segment
field:

```json
"paging": { "freeze_supported": false }
```

§1.6.3.2.1 defines the flag as indicating "that all SEGMENTS can be put in FREEZE mode",
and the AML in §2.1 declares it the same way — `struct Pag` carries `MAX_SEGMENTS` and an
optional `FREEZE_SUPPORTED` tag at MODULE scope, with nothing per segment. It maps directly
to `PAG_PROPERTIES` bit 0 with no aggregation.

This model deliberately mirrors the AML `struct Segment` (§2.1), which carries
`SEGMENT_NUMBER`, page count, `ADDRESS_EXTENSION`, `COMPRESSION_METHOD`,
`ENCRYPTION_METHOD`, a repeated `PAGE` block with the three access enums and
`INIT_SEGMENT`, and a repeated `ADDRESS_MAPPING` block of source, destination and length.
The one field the AML lacks is the segment's own address and length, which it inherits from
the A2L `MEMORY_SEGMENT` it attaches to; the slave must hold them itself to answer
`GET_SEGMENT_INFO` mode 0.

### 6.2 Access enum encoding

The three access fields share one enumeration, encoded per §1.6.3.2.3:

One enumeration serves all three fields, so its names are neutral about which party is
"the other one": in `ecu_access` the other party is XCP, and in the two `xcp_*` fields it
is the ECU.

| Value | Bits | Meaning |
|:--|:--|:--|
| `NOT_ALLOWED` | `0b00` | access not allowed |
| `WITHOUT_OTHER` | `0b01` | only when the other party does not access |
| `WITH_OTHER` | `0b10` | only when the other party accesses |
| `DONT_CARE` | `0b11` | don't care |

The generator packs them into `PAGE_PROPERTIES`: `ecu_access` at bits 1:0,
`xcp_read_access` at bits 3:2, `xcp_write_access` at bits 5:4. Bits 7:6 are reserved and
emitted as zero.

### 6.3 Generated types

`interface/Xcp_Types.h` gains:

```c
typedef struct {
    const uint32 sourceAddress;
    const uint32 destinationAddress;
    const uint32 length;
} Xcp_AddressMappingType;

typedef struct {
    const uint8 initSegment;
    const uint8 pageProperties;   /* packed per section 1.6.3.2.3 */
} Xcp_PageType;

typedef struct {
    const uint32 address;
    const uint32 length;
    const uint8  addressExtension;
    const uint8  compressionMethod;
    const uint8  encryptionMethod;
    const uint8  maxPages;
    const Xcp_PageType *page;
    const uint8  maxMapping;
    const Xcp_AddressMappingType *addressMapping;
} Xcp_SegmentType;
```

`Xcp_ConfigType` gains `const Xcp_SegmentType *segment;`. `Xcp_GeneralType` gains
`const uint8 maxSegment;` and `const uint8 pagProperties;`.

### 6.4 Runtime state

FREEZE is mutable state the module owns — §1.6.3.2.4 defines it as selecting the segment
for freezing through `STORE_CAL_REQ`, which is the module's own mechanism — so it belongs
in `Xcp_Rt`, never in the `const` configuration. `Xcp_RtType` gains a per-segment array:

```c
typedef struct {
    boolean freeze;     /* FREEZE mode, section 1.6.3.2.4 */
} Xcp_SegmentRtType;
```

`script/source_rt.c.jinja2` sizes the array from the segment count. `Xcp_Init` sets
`freeze = FALSE` for every segment.

**The active page is deliberately not cached here.** `Xcp_GetCalPage` (§7) is the authority,
because the ECU application may switch pages without XCP's involvement. A shadow copy in
`Xcp_Rt` would drift from the truth in exactly the situation the callback exists to handle,
and `GET_CAL_PAGE` would then report a stale page.

---

## 7. Integrator callback interface

New `Xcp_Paging.h`, with a stub in `test/stub/` mirroring `Xcp_SeedKey.h`:

```c
extern Std_ReturnType Xcp_SetCalPage(uint8 segment, uint8 page, uint8 mode);
extern Std_ReturnType Xcp_GetCalPage(uint8 segment, uint8 mode, uint8 *pPage);
extern Std_ReturnType Xcp_CopyCalPage(uint8 srcSegment, uint8 srcPage,
                                      uint8 dstSegment, uint8 dstPage);
```

Three callbacks, each invoked only after the module has validated every parameter against
configuration. `mode` uses the §1.6.3.1.2 encoding, `0x01` ECU access and `0x02` XCP access,
but the two callbacks treat it differently: `Xcp_SetCalPage` receives a mask, since the master
may request either access or both in one command, while `Xcp_GetCalPage` receives exactly one
of the two, every other value having been rejected with `ERR_MODE_NOT_VALID` first. The `ALL`
flag never reaches either: the module resolves it into the set of segments to call for.

| Callback | Returns `E_NOT_OK` → |
|:--|:--|
| `Xcp_SetCalPage` | `ERR_MODE_NOT_VALID` (§1.6.3.1.1) |
| `Xcp_GetCalPage` | `ERR_MODE_NOT_VALID` — the slave cannot report an active page for the requested access mode |
| `Xcp_CopyCalPage` | `ERR_WRITE_PROTECTED` (§1.6.3.2.6) |

`Xcp_GetCalPage` writes the active page number through `pPage` and must not modify it when
returning `E_NOT_OK`. The module passes a pointer to a local, so an integrator writing to it
regardless cannot corrupt module state.

`SET_SEGMENT_MODE` and `GET_SEGMENT_MODE` are answered from `Xcp_Rt` and need no callback.
The three info commands are answered from configuration.

### 7.1 Exposing FREEZE to the store operation

§1.6.3.2.4 states that the FREEZE flag "selects the SEGMENT for freezing through
`STORE_CAL_REQ`". The existing store callback,
`Xcp_StoreCalibrationDataToNonVolatileMemory(uint8 *pStatusCode)`, receives no segment
information, so without an addition `SET_SEGMENT_MODE` would set a flag that nothing can
ever act on and the command would be conformant in wire format only.

Rather than change that callback's signature — it is existing integrator API, and a
fixed-width mask would not scale past eight segments — the module exposes its own state
through a new function in `Xcp.h`:

```c
boolean Xcp_GetSegmentFreezeState(uint8 segment);
```

The integrator's `Xcp_StoreCalibrationDataToNonVolatileMemory` implementation queries it per
segment and stores accordingly. The module remains the owner of FREEZE state, the existing
callback signature is untouched, and the direction of the call matches the rest of the
module's design: the integrator asks the module about session state, and the module asks
the integrator about hardware.

`Xcp_GetSegmentFreezeState` returns `FALSE` for a segment index outside
`[0..MAX_SEGMENT-1]`, and is compiled only when `XCP_PAGING_SUPPORTED` is `STD_ON`.

`Xcp_Paging.h` is included from `Xcp.h` alongside the existing callback headers. The
generator emits `#define XCP_PAGING_SUPPORTED (STD_ON)` into `Xcp_Cfg.h` when the
configuration declares at least one segment and `(STD_OFF)` otherwise; both the include and
the three `extern` declarations are guarded on it, so an integrator with no segments
supplies none of them and the linker never asks for them.

---

## 8. Command specifications

Throughout: `AG` is the address granularity element size in bytes (1, 2 or 4);
`alignment` is `Xcp_GetNumberOfAlignmentBytes(2, AG, MAX_CTO)`; every positive response
begins with `0xFF` and every error response with `0xFE` followed by the error code.

### 8.1 DOWNLOAD — 0xF0 (§1.6.2.1.1, mandatory)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xF0 |
| 1 | BYTE | number of data elements `n` |
| 2 .. 1+alignment | BYTE | alignment, only when `AG > 2` |
| 2+alignment .. | ELEMENT | data elements |

`n` range is `[1..(MAX_CTO-2-alignment)/AG]` in standard mode and
`[1..min(MAX_BS × (MAX_CTO-2-alignment)/AG, 255)]` in block mode.

**Block mode here is MASTER block mode, not slave block mode.** §1.6.1.2.1 defines `MAX_BS`
as applying "If the master device block mode is supported", and names its packets explicitly
as `DOWNLOAD_NEXT` or `PROGRAM_NEXT`. `DOWNLOAD` is a master-to-slave multi-*command*
transfer, so it is gated by `MASTER_BLOCK_MODE` (`COMM_MODE_OPTIONAL` bit 0, §1.6.1.2.1) and
bounded by `MAX_BS`. `SLAVE_BLOCK_MODE` (`COMM_MODE_BASIC` bit 6, §1.6.1.1.1) governs the
opposite direction — multiple *responses* to one request — and belongs to `UPLOAD`. The
module already advertises this correctly in `GET_COMM_MODE_INFO`, which reports `MAX_BS` and
`MIN_ST` under `masterBlockModeSupported`; the handler must agree with it. See defect D8.

Behaviour: copy the data block to memory starting at the MTA, post-incrementing the MTA by
the number of bytes written. In standard mode the whole block is written and the response
is `0xFF`. In block mode the first frame's worth is written, block state is armed with the
remainder, and **no response is sent** (`*responseExpected = FALSE`); the master then sends
`(n × AG / (MAX_CTO-2)) - 1` consecutive `DOWNLOAD_NEXT` packets and only the last is
acknowledged.

Implementation is `Xcp_DataTransferInitialize` followed by
`Xcp_BlockTransferWriteSlaveMemory`, both of which already exist — with
`Xcp_DataTransferInitialize` extended per D1 and D8 to take both the size budget and the
governing block-mode flag from its caller.

Errors: `ERR_OUT_OF_RANGE` when `n` is outside its range or zero;
`ERR_MEMORY_OVERFLOW` when the write would leave the addressable range.

### 8.2 DOWNLOAD_NEXT — 0xEF (§1.6.2.2.1, optional)

Identical request layout to `DOWNLOAD`, with `n` carrying the **remaining** element count.

Behaviour: if no block transfer is active, or `n` does not equal the remaining count,
return `ERR_SEQUENCE` and abort the transfer. The negative response carries the expected
count, which is the one place in this sub-project where an error packet has a payload:

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xFE |
| 1 | BYTE | `ERR_SEQUENCE` (0x29) |
| 2 | BYTE | number of expected data elements |

This requires a variant of `Xcp_FillErrorPacket` that appends a byte, or an explicit
assembly in the handler. Otherwise write the frame, decrement the remaining count, and
respond `0xFF` only when it reaches zero.

### 8.3 DOWNLOAD_MAX — 0xEE (§1.6.2.2.2, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xEE |
| 1 .. AG-1 | BYTE | alignment, only when `AG > 1` |
| AG .. MAX_CTO-1 | ELEMENT | data elements |

A fixed `MAX_CTO/AG - 1` elements are copied to the MTA, which is post-incremented by the
same count. No block transfer. The handler rejects a request shorter than `MAX_CTO` with
`ERR_CMD_SYNTAX`, since `ctoInfo`'s four-bit minimum-size field cannot express `MAX_CTO`.
Per DD3, arriving during an active block transfer yields `ERR_SEQUENCE`.

Response: `0xFF`.

### 8.4 SHORT_DOWNLOAD — 0xED (§1.6.2.2.3, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xED |
| 1 | BYTE | number of data elements, `[0..(MAX_CTO-8)/AG]` |
| 2 | BYTE | reserved |
| 3 | BYTE | address extension |
| 4 .. 7 | DWORD | address |
| 8 .. MAX_CTO-1 | ELEMENT | data elements |

Writes the block at the given address and sets the MTA to the first element *after* it.
`ERR_OUT_OF_RANGE` when the count exceeds `(MAX_CTO-8)/AG`. No block transfer; per DD3,
`ERR_SEQUENCE` during one. Enabled by default: see DD5 for why disabling it also cleared
the `CONNECT` `RESOURCE` CAL/PAG bit.

Response: `0xFF`.

### 8.5 MODIFY_BITS — 0xEC (§1.6.2.2.4, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xEC |
| 1 | BYTE | shift value `S` |
| 2, 3 | WORD | AND mask `MA` |
| 4, 5 | WORD | XOR mask `MX` |

The 32-bit location at the MTA is modified as

```c
A = (A & ~((uint32)((uint16)(~MA)) << S)) ^ ((uint32)MX << S);
```

Both operands **must be widened to 32 bits before shifting**; computing `(uint16)~MA << S`
in 16-bit width discards the high bits for any `S ≥ 1` and produces silently wrong results.

Worked check against the §1.6.2.2.4 example — `A = 0xFFF0FFFF`, `S = 16`, `MA = 0xBFFE`,
`MX = 0x0001`: `(uint16)~MA = 0x4001`; `0x4001 << 16 = 0x40010000`; `~ = 0xBFFEFFFF`;
`A & = 0xBFF0FFFF`; `MX << 16 = 0x00010000`; `^ = 0xBFF1FFFF`, which matches the
specification's stated result.

`MA` and `MX` are read with `Xcp_CopyToU16WithOrder`. Access is 32-bit regardless of `AG`,
so the handler calls `Xcp_ReadSlaveMemoryU32` and `Xcp_WriteSlaveMemoryU32` directly rather
than indexing `Xcp_ReadSlaveMemoryTable`. **The MTA is not modified.**

Response: `0xFF`.

### 8.6 SET_CAL_PAGE — 0xEB (§1.6.3.1.1, mandatory)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xEB |
| 1 | BYTE | mode |
| 2 | BYTE | logical data segment number |
| 3 | BYTE | logical data page number |

Mode is a bit mask: bit 0 `ECU`, bit 1 `XCP`, bit 7 `ALL`. `ECU` and `XCP` may be set
together or separately. When `ALL` is set the segment number is ignored and the command
applies to every segment.

Behaviour: validate the segment (unless `ALL`) and the page, then call `Xcp_SetCalPage` once
per affected segment, passing the requested access bits as a mask. One call carries both
accesses when the master asks for both. With `ALL` set, a failure on any
segment aborts and returns the error; segments already switched are left switched, since
§1.6.3.1.1 defines no rollback.

Errors: `ERR_SEGMENT_NOT_VALID` when the segment is outside `[0..MAX_SEGMENT-1]`;
`ERR_PAGE_NOT_VALID` when the page is outside `[0..MAX_PAGES-1]` for that segment;
`ERR_MODE_NOT_VALID` when neither `ECU` nor `XCP` is set, or when `Xcp_SetCalPage` returns
`E_NOT_OK`.

Response: `0xFF`.

### 8.7 GET_CAL_PAGE — 0xEA (§1.6.3.1.2, mandatory)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xEA |
| 1 | BYTE | access mode: 0x01 ECU or 0x02 XCP |
| 2 | BYTE | logical data segment number |

Positive response: `0xFF`, byte 1 reserved, byte 2 reserved, byte 3 the active page number
for that access mode, obtained from `Xcp_GetCalPage`.

Errors: any mode other than exactly 0x01 or 0x02 — including 0x03 — is invalid and yields
`ERR_MODE_NOT_VALID`; an out-of-range segment yields `ERR_SEGMENT_NOT_VALID`;
`Xcp_GetCalPage` returning `E_NOT_OK` yields `ERR_MODE_NOT_VALID`.

### 8.8 GET_PAG_PROCESSOR_INFO — 0xE9 (§1.6.3.2.1, optional)

Request is the command code alone. Positive response: `0xFF`, `MAX_SEGMENT`,
`PAG_PROPERTIES`. `PAG_PROPERTIES` bit 0 is `FREEZE_SUPPORTED`, taken directly from the
module-level `paging.freeze_supported` of §6.1. Bits 7:1 are reserved and emitted as zero,
per the §1.5 table.

### 8.9 GET_SEGMENT_INFO — 0xE8 (§1.6.3.2.2, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xE8 |
| 1 | BYTE | mode: 0 basic address info, 1 standard info, 2 address mapping info |
| 2 | BYTE | `SEGMENT_NUMBER` |
| 3 | BYTE | `SEGMENT_INFO` |
| 4 | BYTE | `MAPPING_INDEX` |

Mode 0 — `SEGMENT_INFO` selects 0 = address, 1 = length. Response: `0xFF`, bytes 1..3
reserved, bytes 4..7 the DWORD `BASIC_INFO`.

Mode 1 — `SEGMENT_INFO` and `MAPPING_INDEX` are don't care. Response: `0xFF`, `MAX_PAGES`,
`ADDRESS_EXTENSION`, `MAX_MAPPING`, compression method, encryption method.

Mode 2 — `SEGMENT_INFO` selects 0 = source address, 1 = destination address, 2 = length,
for the range named by `MAPPING_INDEX`. Response: `0xFF`, bytes 1..3 reserved, bytes 4..7
the DWORD `MAPPING_INFO`.

All DWORDs are written with `Xcp_CopyFromU32WithOrder`.

Errors: `ERR_SEGMENT_NOT_VALID` for an out-of-range segment; `ERR_OUT_OF_RANGE` for an
unknown mode, a `SEGMENT_INFO` outside the range its mode defines, or a `MAPPING_INDEX`
outside `[0..MAX_MAPPING-1]`. Both codes are listed for this command in §1.7.3.2.3.

### 8.10 GET_PAGE_INFO — 0xE7 (§1.6.3.2.3, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xE7 |
| 1 | BYTE | reserved |
| 2 | BYTE | `SEGMENT_NUMBER` |
| 3 | BYTE | `PAGE_NUMBER` |

Positive response: `0xFF`, `PAGE_PROPERTIES`, `INIT_SEGMENT`, both taken from
configuration.

Errors — **divergence, resolved per DD4.** §1.6.3.2.3 prose says an unavailable page
returns `ERR_OUT_OF_RANGE`, but §1.7.3.2.3 lists `ERR_PAGE_NOT_VALID` and
`ERR_SEGMENT_NOT_VALID` for this command and does *not* list `ERR_OUT_OF_RANGE`. The matrix
wins: an out-of-range segment yields `ERR_SEGMENT_NOT_VALID` and an out-of-range page
yields `ERR_PAGE_NOT_VALID`. This is also consistent with every other PAG command.

### 8.11 SET_SEGMENT_MODE — 0xE6 (§1.6.3.2.4, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xE6 |
| 1 | BYTE | mode, bit 0 `FREEZE` |
| 2 | BYTE | `SEGMENT_NUMBER` |

Sets `freeze` in `Xcp_Rt` for that segment, where it becomes visible to the integrator
through `Xcp_GetSegmentFreezeState` (§7.1). Errors: `ERR_SEGMENT_NOT_VALID` for an
out-of-range segment; `ERR_MODE_NOT_VALID` when `FREEZE` is requested while
`paging.freeze_supported` is false.

Response: `0xFF`.

### 8.12 GET_SEGMENT_MODE — 0xE5 (§1.6.3.2.5, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xE5 |
| 1 | BYTE | reserved |
| 2 | BYTE | `SEGMENT_NUMBER` |

Positive response: `0xFF`, byte 1 reserved, byte 2 mode with bit 0 `FREEZE` from `Xcp_Rt`.
Error: `ERR_SEGMENT_NOT_VALID`.

### 8.13 COPY_CAL_PAGE — 0xE4 (§1.6.3.2.6, optional)

| Position | Type | Description |
|:--|:--|:--|
| 0 | BYTE | 0xE4 |
| 1 | BYTE | source segment |
| 2 | BYTE | source page |
| 3 | BYTE | destination segment |
| 4 | BYTE | destination page |

Validate all four against configuration, then call `Xcp_CopyCalPage`.

Errors: `ERR_SEGMENT_NOT_VALID` and `ERR_PAGE_NOT_VALID` as elsewhere. **Divergence,
resolved per DD4:** §1.6.3.2.6 mandates `ERR_WRITE_PROTECTED` when the destination cannot
be written — its example is a flash segment — but §1.7.3.2.3 omits that code for this
command. The prose wins, because it describes a concrete condition the slave must report
and no other code fits. `Xcp_CTOErrorMatrix` needs no change: it governs generic
pre-checks only.

Response: `0xFF`.

---

## 9. Defect fixes

**D1 — `Xcp_DataTransferInitialize`.** Rewrite so that the comparison accepts what fits,
the per-command budget is a parameter rather than hard-coded to `MAX_CTO - 2`, and
`requested_elements` is assigned only on the success path. `UPLOAD` and `DOWNLOAD` then
share it correctly with budgets `MAX_CTO - 1` and `MAX_CTO - 2` respectively. A regression
test asserting that `UPLOAD` **succeeds** with `slave_block_mode=False` is required — its
absence is what hid the defect.

Verified against §1.6.1.2.7: at `MAX_CTO = 8`, `AG = 1`, alignment 0, `UPLOAD(3)` is inside
the specified range `[1..MAX_CTO/AG-1]`, and the current condition
`(8-2) > (3+0)` evaluates true and rejects it.

**D8 — `DOWNLOAD` block transfer is gated on the wrong flag.**
`Xcp_DTOCmdCalDownload` (`source/Xcp.c:2487`) and `Xcp_DataTransferInitialize`
(`source/Xcp.c:3716`) both test `slaveBlockModeSupported`. Per §1.6.1.2.1, master block mode
governs `DOWNLOAD`/`DOWNLOAD_NEXT` and carries `MAX_BS`; slave block mode governs `UPLOAD`.
The module's own `GET_COMM_MODE_INFO` handler already reports `MAX_BS` and `MIN_ST` under
`masterBlockModeSupported`, so the module currently contradicts itself.

The defect is latent only because `config/xcp.json` sets both flags true. A configuration
with `master_block_mode: false, slave_block_mode: true` would accept multi-packet
`DOWNLOAD` sequences it is required to reject with `ERR_OUT_OF_RANGE`; the inverse
configuration would reject valid ones.

Fix: `Xcp_DataTransferInitialize` takes the governing flag from its caller alongside the
budget — `masterBlockModeSupported` for `DOWNLOAD`, `slaveBlockModeSupported` for `UPLOAD`.
Tests must cover all four combinations of the two flags for both commands, since no current
test varies them independently.

**D2 — commands with no handler.** §1.4 is normative: "An attempt to execute a not
implemented optional command will return ERR_CMD_UNKNOWN and does not have any effect."

§1.1.5.1 fixes the master-to-slave packet identifier space at `0xC0..0xFF` for `CMD` and
`0x00..0xBF` for STIM ODT numbers. **There is no DAQ range in that direction** — DAQ
identifiers are slave-to-master only (§1.1.5.2). Every one of the roughly thirty
`Xcp_DTODaqPacket` entries in `Xcp_PIDTable` is therefore an artifact, not a design choice,
and none of them is legitimate.

Accordingly: every PID in this sub-project gains a real handler; the generator stops
hard-coding the enable bit for `MODIFY_BITS`, `DOWNLOAD_NEXT` and the six optional PAG
commands; and every remaining `Xcp_DTODaqPacket` entry — the PGM range `0xC8..0xD2`, the
undefined range `0xC0..0xC7`, and any CAL/PAG PID whose API is disabled — is replaced by a
new `Xcp_CmdNotImplemented` handler filling `ERR_CMD_UNKNOWN`. After this work
`Xcp_DTODaqPacket` appears nowhere in `Xcp_PIDTable`. The `0x00..0xBF` entries correctly
remain `Xcp_DTODaqStimPacket`. The DAQ commands at `0xD3..0xE3` were initially left alone
for SP2, but their stubs returned `E_OK` without filling the response buffer, so the slave
transmitted the previous command's response; they now use `Xcp_CmdNotImplemented` too and the
stubs are deleted. SP2 reinstates them when DAQ is implemented.

**D3 — `Xcp_Errors.h`.** As specified in §5.

**D4 — dead helpers.** Delete `Xcp_DataTransferActive`, which duplicates
`Xcp_BlockTransferIsActive`. `Xcp_BlockTransferWriteSlaveMemory` acquires its caller in
§8.1 and stays.

**D5 — source split.** §4.

---

## 10. Generator and schema changes

`config/xcp.schema.json` and `script/source_cfg.c.jinja2` gain eight `*_api_enable` entries,
each with the same `enabled` / `protected` shape as the existing ones:

`xcp_download_next_api_enable`, `xcp_modify_bits_api_enable`,
`xcp_get_pag_processor_info_api_enable`, `xcp_get_segment_info_api_enable`,
`xcp_get_page_info_api_enable`, `xcp_set_segment_mode_api_enable`,
`xcp_get_segment_mode_api_enable`, `xcp_copy_cal_page_api_enable`.

The template stops emitting a literal `0x01u` for their enable bits.

`config/xcp.json` ships with a single example segment carrying two pages, so the default
configuration exercises the new path. `xcp_short_download_api_enable` originally defaulted to
false per DD5, and was enabled once the command existed: leaving it off cleared the `CONNECT`
`RESOURCE` CAL/PAG bit, since §1.6.1.1.1 defines that bit as asserting all five calibration
commands are available.

**`CONNECT` is deliberately left alone.** §1.6.1.1.1 defines the `CAL/PAG` resource bit by
naming its commands exactly: "The commands DOWNLOAD, DOWNLOAD_MAX, SHORT_DOWNLOAD,
SET_CAL_PAGE, GET_CAL_PAGE are available." Those five, no more. The eight new
`*_api_enable` keys therefore must **not** feed the resource mask, the handler that computes
it is already correct, and
`test_connect_sets_the_resource_cal_pag_bit_according_to_enabled_apis` in
`test/connect_test.py` — which parametrises over precisely those five flags — stays as it
is. The same section pins the `PGM` bit to `PROGRAM_CLEAR`, `PROGRAM` and `PROGRAM_MAX`,
which is exactly the three PGM flags already present in `xcp.json`.

**New validation rule.** §1.4 states: "If SET_CAL_PAGE is implemented, GET_CAL_PAGE is
required." A configuration enabling `xcp_set_cal_page_api_enable` without
`xcp_get_cal_page_api_enable` is invalid. The schema cannot express the dependency
cleanly, so `Xcp_Init` rejects it with `XCP_E_INIT_FAILED`, alongside the existing
`MAX_CTO mod AG` check, and a test asserts it. The sibling rule "If GET_SEED is implemented,
UNLOCK is required" is already satisfied by the current configuration and gains the same
check for free.

---

## 11. Test strategy

Test-driven, following the existing layout: one file per command, plus error-matrix classes.

**New files** — `download_test.py`, `download_next_test.py`, `download_max_test.py`,
`short_download_test.py`, `modify_bits_test.py`, `set_cal_page_test.py`,
`get_cal_page_test.py`, `get_pag_processor_info_test.py`, `get_segment_info_test.py`,
`get_page_info_test.py`, `segment_mode_test.py`, `copy_cal_page_test.py`.

**Extended** — `asam_error_matrix_test.py` gains twelve classes mirroring the existing
`TestDownloadErrorHandling`. Because §1.7.3.2.2 and §1.7.3.2.3 are fully tabulated, these
are transcription rather than design.

**`parameter.py`** gains segment and page builders so a test can declare a paging
configuration inline, matching how `DefaultConfig` already handles DAQ lists.

**`conftest.py`** gains `MagicMock`s for `Xcp_SetCalPage`, `Xcp_GetCalPage` and
`Xcp_CopyCalPage` alongside the existing `xcp_get_seed` and `xcp_calc_key`, defaulting to
`E_OK`. `XcpTest` binds them through the existing `self.code.mocked` loop, whose `convert()`
maps the three names to `xcp_set_cal_page`, `xcp_get_cal_page` and `xcp_copy_cal_page`, so
the attributes must carry exactly those names.

Cases that must exist beyond the happy path:

- every `AG` value — `BYTE`, `WORD`, `DWORD` — for each of the five CAL commands, since
  alignment handling differs per granularity;
- `DOWNLOAD` in block and standard mode, including the response-suppression behaviour;
- all four combinations of `master_block_mode` and `slave_block_mode` against both
  `DOWNLOAD` and `UPLOAD` — the D8 regression. No existing test varies the two
  independently, which is precisely why the module could contradict its own
  `GET_COMM_MODE_INFO` unnoticed;
- `DOWNLOAD_NEXT` sequence error carrying the expected count in byte 2;
- `DOWNLOAD_MAX` and `SHORT_DOWNLOAD` rejected mid-block-transfer per DD3;
- `MODIFY_BITS` against the §1.6.2.2.4 worked example, and with `S ≥ 16` to catch the
  widening trap;
- `SET_CAL_PAGE` with the `ALL` bit across several segments;
- `GET_SEGMENT_INFO` in all three modes and every `SEGMENT_INFO` value;
- `UPLOAD` succeeding with `slave_block_mode=False` — the D1 regression;
- disabled commands returning `ERR_CMD_UNKNOWN`, and every PID in `0xC0..0xC7` and
  `0xC8..0xD2` doing the same — the D2 regression;
- `SET_SEGMENT_MODE` making FREEZE observable through `Xcp_GetSegmentFreezeState`, since
  that is the only thing distinguishing a conformant implementation from one that merely
  echoes the flag back through `GET_SEGMENT_MODE`;
- `Xcp_Init` reporting `XCP_E_INIT_FAILED` for a configuration enabling `SET_CAL_PAGE`
  without `GET_CAL_PAGE`;
- `CONNECT`'s `CAL_PAG` resource bit staying keyed to its five §1.6.1.1.1 commands and
  **not** responding to the eight new API flags — a guard against exactly the mistake this
  spec made before the full specification read.

The 13 currently skipped tests stay skipped; none belong to this sub-project.

---

## 12. Environment

**The build does not run on the development host.** `cmake`, `cffi`, `jinja2`,
`jsonschema`, `pcpp`, `pycparser` and `bsw_code_gen` are all absent; the project builds and
tests inside the Alpine image defined by `Dockerfile`. Standing that environment up — the
container, or a virtualenv plus a system `cmake` — is the first task of the implementation
plan. Test-driven development is unenforceable until `./test.sh` runs green against the
untouched baseline.

`bsw_code_gen~=0.1.9` is pinned in `requirements.txt` and is a third-party dependency of the
generator. Any change to the generated structures must stay within what that version's
template API supports.

---

## 13. Acceptance

1. `./test.sh` runs green — every existing test still passing, plus the new ones — with the
   skip list unchanged at 13.
2. All thirteen commands in §1 behave per §8, including error codes.
3. A command whose `*_api_enable` is false returns `ERR_CMD_UNKNOWN`.
4. No PID outside the DAQ range dispatches to `Xcp_DTODaqPacket`.
5. `source/Xcp.c` contains no command handler bodies — only initialisation, scheduling, the
   three `Xcp_CanIf*` callbacks and the three dispatch tables.
6. Coverage reported to codecov covers every new source file, not just `Xcp.c`.
7. `README.md` documents the `segments` configuration block and the two new callbacks, and
   its TODO list drops the items this work closes.

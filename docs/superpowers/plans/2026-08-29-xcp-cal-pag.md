# XCP Calibration and Page Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the ASAM XCP 1.0 calibration command group and implement the page switching command group in the `Xcp` slave module, fixing five defects found in the existing code along the way.

**Architecture:** The module dispatches every received packet identifier through `Xcp_PIDTable`, after generic pre-checks driven by `Xcp_CTOErrorMatrix`, `Xcp_PIDToCmdGroupTable` and the generated `ctoInfo[]` table. Those tables are already correct for all thirteen commands in scope, so the work is writing handlers plus a segment/page configuration model. The single 3876-line `source/Xcp.c` is split into per-group translation units first, so the new handlers land in focused files.

**Tech Stack:** C (AUTOSAR BSW style, MISRA C:2012), CMake, Python 3 + pytest + CFFI test harness, jinja2 code generation via `bsw_code_gen`, Docker (Alpine 3.10).

**Spec:** `docs/superpowers/specs/2026-08-29-xcp-cal-pag-design.md`
**Roadmap:** `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`
**Reference:** *XCP -Part 2- Protocol Layer Specification -1.0* (`docs/external/`)

## Global Constraints

- **Specification is XCP 1.0, not 1.1.** Command codes in the DAQ range differ between revisions. `0xD3 = ALLOC_ODT_ENTRY`, `0xD4 = ALLOC_ODT`, `0xD5 = ALLOC_DAQ`, `0xD6 = FREE_DAQ` are correct for 1.0. Never "correct" them against a later revision.
- **C90-style declarations.** Existing code declares variables at the top of blocks. Match it.
- **AUTOSAR types only** — `uint8`, `uint16`, `uint32`, `boolean`, `Std_ReturnType`, `TRUE`/`FALSE`, `NULL_PTR`, `E_OK`/`E_NOT_OK`. Never `int`, `bool`, `true`, `false`, `NULL`.
- **Hex literals carry a `u` suffix** and are lower-case-`u`, upper-case-digits: `0x0Fu`, `0x00u`.
- **Every function is wrapped in memory-mapping pragmas** in the existing style:
  ```c
  #define Xcp_START_SEC_CODE_SLOW
  #include "Xcp_MemMap.h"
  /* ... */
  #define Xcp_STOP_SEC_CODE_SLOW
  #include "Xcp_MemMap.h"
  ```
  Handlers use `Xcp_START_SEC_CODE_FAST`. Constant tables use `Xcp_START_SEC_CONST_UNSPECIFIED`.
- **Spec citations go in comments** in the existing form: `/* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1 ... */`
- **Error codes are ASAM wire values** from `interface/Xcp_Errors.h` (`XCP_E_ASAM_*`), never the internal `XCP_INTERNAL_ERR_*` bits, which exist only for `Xcp_CTOErrorMatrix`.
- **`Xcp_CTOErrorMatrix` must not be modified.** Every row was verified against §1.7.3.2.1–3 and matches. It governs generic pre-checks only; a handler may emit an error the matrix does not list.
- **CONNECT's `CAL/PAG` resource bit is fixed by §1.6.1.1.1** to exactly DOWNLOAD, DOWNLOAD_MAX, SHORT_DOWNLOAD, SET_CAL_PAGE, GET_CAL_PAGE. No new API flag may feed it.
- **Every positive response is finalized** with `Xcp_FinalizeResPacket(length, &Xcp_Internal.cto_response.pdu_info)`, which sets `SduLength` and pads to `MAX_CTO` with `trailingValue`.
- **Commit after every task.** Never combine two tasks in one commit.

---

## File Structure

| File | Responsibility | Task |
|:--|:--|:--|
| `source/Xcp.c` | Init, scheduling, `Xcp_CanIf*` callbacks, the three dispatch tables. No handler bodies. | 3 |
| `source/Xcp_Internal.h` | **new, private.** `Xcp_InternalType`, `XCP_PID_CMD_*` / `XCP_INTERNAL_ERR_*` / mask macros, shared-helper and handler prototypes, `static inline Xcp_ReportError`. | 3 |
| `source/Xcp_Std.c` | The fifteen standard-command handlers, the nine checksum functions, the CRC tables. | 3 |
| `source/Xcp_Cal.c` | The five calibration handlers. | 3, 6–10 |
| `source/Xcp_Pag.c` | The eight page-switching handlers and `Xcp_GetSegmentFreezeState`. | 3, 13–18 |
| `source/Xcp_Daq.c` | The seventeen DAQ stubs, moved unchanged. Owned by SP2. | 3 |
| `interface/Xcp_Errors.h` | Complete transcription of §1.7.3.1 wire values. | 4 |
| `interface/Xcp_Types.h` | `Xcp_SegmentType`, `Xcp_PageType`, `Xcp_AddressMappingType`, `Xcp_SegmentRtType`. | 11 |
| `interface/Xcp.h` | Adds `Xcp_GetSegmentFreezeState` declaration. | 15 |
| `test/stub/Xcp_Paging.h` | The three integrator paging callbacks. | 12 |
| `config/xcp.schema.json` | `segments` array, `paging` object, eight new API flags. | 11, 19 |
| `config/xcp.json` | One example segment with two pages. | 11 |
| `script/source_cfg.c.jinja2` | Emits segment/page tables, `XCP_PAGING_SUPPORTED`, gated enable bits. | 11, 12, 19 |
| `script/source_rt.c.jinja2`, `script/header_rt.h.jinja2` | Emits the per-segment runtime array. | 11 |
| `test/conftest.py` | Multi-source CFFI build; paging callback mocks. | 2, 12 |
| `test/parameter.py` | Segment/page config builders. | 11 |
| `CMakeLists.txt` | Multi-file library, `XCP_PYTEST_ARGS`. | 1, 2, 3 |
| `test.sh`, `.github/workflows/test.yml` | Per-unit gcov and codecov paths. | 3 |

---

## Task 1: Build environment and baseline

Nothing can be test-driven until the suite runs. The host has no `cmake`, no `cffi` and no `bsw_code_gen`; the build lives in the Alpine image defined by `Dockerfile`. This task also adds a way to run a single test, which every later task needs.

**Files:**
- Modify: `CMakeLists.txt:56-68`

**Interfaces:**
- Consumes: nothing.
- Produces: a working `./test.sh`, and `cmake -DXCP_PYTEST_ARGS="<args>"` for running a subset.

- [ ] **Step 1: Build the container image**

```bash
docker build -t xcp-dev .
```

Expected: image builds. If `pip3 install -r requirements.txt` fails on `bsw_code_gen~=0.1.9`, the package is on PyPI — check network access before assuming the pin is wrong.

- [ ] **Step 2: Run the suite to capture the baseline**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: the run completes and pytest reports **42 passed, 13 skipped** (55 test functions, expanded by parametrisation into many more cases — record the exact case counts from the output, they are the baseline every later task compares against).

Write the exact summary line into `/tmp/xcp-baseline.txt`. If the suite is not green here, stop and report — every later task's verification depends on this.

- [ ] **Step 3: Add a pytest argument passthrough**

In `CMakeLists.txt`, add the cache variable next to the other options near line 12:

```cmake
set(XCP_PYTEST_ARGS "" CACHE STRING "extra arguments forwarded to pytest (e.g. -k download).")
```

Then in the `add_test` block, replace the line `-m pytest ${CMAKE_CURRENT_SOURCE_DIR}/test -v -x` with:

```cmake
        -m pytest ${CMAKE_CURRENT_SOURCE_DIR}/test -v -x ${XCP_PYTEST_ARGS}
```

- [ ] **Step 4: Verify the passthrough selects a subset**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'mkdir -p build && cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k connect" && make all && ctest -V'
```

Expected: only tests whose name contains `connect` run; the rest are deselected.

- [ ] **Step 5: Commit**

```bash
git add CMakeLists.txt
git commit -m "test: allow forwarding extra arguments to pytest"
```

---

## Task 2: Prove the multi-source CFFI build

Design decision DD6 relies on `cffi`'s `set_source(..., sources=[...])` forwarding to `distutils.Extension`. That path is not exercised today. Convert the harness to it **while there is still only one source file**, so a failure here is unambiguous and cannot be confused with a mistake in the split.

**Files:**
- Modify: `test/conftest.py:118-136` (`MockGen.__init__`), `test/conftest.py:222-232` (`XcpTest.code`), `test/conftest.py:315-317` (`source` property)
- Modify: `CMakeLists.txt` (the `--source` argument)

**Interfaces:**
- Consumes: `XCP_PYTEST_ARGS` from Task 1.
- Produces: `XcpTest.sources` returns a `list[str]` of C source paths; `MockGen(..., sources=tuple_of_paths)` compiles them as separate translation units linked into one extension.

- [ ] **Step 1: Teach `MockGen` to accept extra sources**

In `test/conftest.py`, change the `MockGen.__init__` signature to add a `sources` parameter after `link_libraries`:

```python
    def __init__(self,
                 name,
                 source,
                 header,
                 include_dirs=tuple(),
                 define_macros=tuple(),
                 compile_flags=tuple(),
                 link_flags=tuple(),
                 link_libraries=tuple(),
                 sources=tuple(),
                 build_dir=''):
```

and pass it through to `set_source` — replace the existing `self.set_source(...)` call with:

```python
            self.set_source(self.name, source,
                            include_dirs=include_dirs,
                            define_macros=list(tuple(d.split('=')) for d in define_macros),
                            extra_compile_args=list(compile_flags),
                            libraries=list(link_libraries),
                            library_dirs=(build_dir,),
                            sources=list(sources),
                            extra_link_args=list(link_flags))
```

- [ ] **Step 2: Turn the `source` option into a list**

Replace the `source` property of `XcpTest` (currently returning `os.getenv('source')`) with:

```python
    @property
    def sources(self):
        return os.getenv('source').split(';')
```

Then change the construction of `self.code` in `XcpTest.__init__` so the C source string only includes the public header and the real sources are compiled separately:

```python
        self.code = MockGen('_cffi_xcp',
                            '#include "Xcp.h"',
                            header,
                            define_macros=tuple(self.compile_definitions) +
                                          ('XCP_EVENT_QUEUE_SIZE=0x{:04X}'.format(config.event_queue_size),),
                            include_dirs=tuple(self.include_directories + [self.build_directory]),
                            compile_flags=('-g', '-O0', '-fprofile-arcs', '-ftest-coverage'),
                            link_flags=('-g', '-O0', '-fprofile-arcs', '-ftest-coverage',),
                            link_libraries=(os.path.basename(f).lstrip('lib').rstrip('.so'),),
                            sources=tuple(self.sources),
                            build_dir=self.build_directory)
```

- [ ] **Step 3: Run the suite to verify nothing changed**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: identical to the Task 1 baseline — 42 passed, 13 skipped.

If linking fails with undefined references to `CanIf_Transmit`, `Det_ReportError` or similar, the `extern "Python+C"` definitions CFFI generates live in `_cffi_xcp.c` and are being compiled — check that `sources` was *appended* to CFFI's own generated file rather than replacing it.

- [ ] **Step 4: Confirm gcov still produces coverage for `Xcp.c`**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && gcov Xcp.c 2>/dev/null | head -5; ls *.gcov'
```

Expected: `Xcp.c.gcov` exists and reports a non-zero line coverage percentage. Coverage now comes from `Xcp.c`'s own object rather than through the include, so a zero percentage means the source was not actually compiled into the extension.

- [ ] **Step 5: Commit**

```bash
git add test/conftest.py CMakeLists.txt
git commit -m "test: compile module sources as separate translation units"
```

---

## Task 3: Split the source into translation units

Pure move. No behaviour changes, no new logic. This is the last chance to do it cheaply — SP2 will add far more code than SP1.

**Files:**
- Create: `source/Xcp_Internal.h`, `source/Xcp_Std.c`, `source/Xcp_Cal.c`, `source/Xcp_Pag.c`, `source/Xcp_Daq.c`
- Modify: `source/Xcp.c`, `CMakeLists.txt`, `test.sh`, `.github/workflows/test.yml`

**Interfaces:**
- Consumes: the multi-source harness from Task 2.
- Produces: `Xcp_Internal.h` exporting, with external linkage:
  - `void Xcp_FinalizeResPacket(const PduLengthType startIndex, PduInfoType *pPduInfo);`
  - `void Xcp_FillErrorPacket(const uint8 errorCode, PduInfoType *pPduInfo);`
  - `uint8 Xcp_ElementSizeForAddressGranularity(Xcp_AddressGranularityType ag);`
  - `uint8_least Xcp_GetNumberOfAlignmentBytes(uint8_least alignmentByteIndex, uint8_least elementSize, uint8 maxCto);`
  - `void Xcp_CopyFromU16WithOrder(const uint16 src, uint8 *pDest, Xcp_ByteOrderType endianness);`
  - `void Xcp_CopyFromU32WithOrder(const uint32 src, uint8 *pDest, Xcp_ByteOrderType endianness);`
  - `void Xcp_CopyToU16WithOrder(const uint8 *pSrc, uint16 *pDest, Xcp_ByteOrderType endianness);`
  - `void Xcp_CopyToU32WithOrder(const uint8 *pSrc, uint32 *pDest, Xcp_ByteOrderType endianness);`
  - `boolean Xcp_BlockTransferIsActive(void);`
  - `Std_ReturnType Xcp_DataTransferInitialize(uint8 numberOfDataElements, uint8 elementSize, uint8 alignment);`
  - `void Xcp_BlockTransferAcknowledgeFrame(void);`
  - `Std_ReturnType Xcp_BlockTransferReadSlaveMemory(void);`
  - `Std_ReturnType Xcp_BlockTransferWriteSlaveMemory(uint8 *pBuffer, uint8 elementSize);`
  - `uint8 Xcp_GetProtectionStatus(void);`
  - `void Xcp_SetProtectionStatus(void);`
  - `void Xcp_ClearProtectionStatus(void);`
  - `Std_ReturnType Xcp_CheckMasterSlaveKeyMatch(uint16 slaveKeyLength, const uint8 *pSlaveKey, uint16 masterKeyLength, const uint8 *pMasterKey);`
  - `extern void(* const Xcp_ReadSlaveMemoryTable[])(void *address, uint8 extension, uint8 *pBuffer);`
  - `extern void(* const Xcp_WriteSlaveMemoryTable[])(void *address, uint8 *pBuffer);`
  - `extern Xcp_InternalType Xcp_Internal;`
  - every handler prototype, e.g. `uint8 Xcp_DTOCmdCalDownload(boolean *responseExpected, const PduInfoType *pPduInfo);`
  - `static inline void Xcp_ReportError(uint8 instanceId, uint8 apiId, uint8 errorId)` — defined, not just declared, because `Compiler.h` defines `LOCAL_INLINE` as `static inline`.

- [ ] **Step 1: Create the private header**

Create `source/Xcp_Internal.h` with the standard guard and include block, then move into it, verbatim:
- everything currently between `/* local definitions (#define). */` and `/* local data type definitions */` in `Xcp.c` (the `XCP_CTO_INFO_*`, `XCP_PID_*`, `XCP_PID_CMD_*`, `XCP_CONNECT_MODE_*`, `XCP_RESOURCE_PROTECTION_STATUS_MASK_*`, `XCP_SESSION_STATUS_MASK_*`, `XCP_INTERNAL_ERR_*` macros and `XCP_EVENT_STORE_CAL`);
- the `Xcp_ConnectionState` enum and the `Xcp_InternalType` struct;
- the `Xcp_ReportError` definition, unchanged, still marked `LOCAL_INLINE`;
- `extern Xcp_InternalType Xcp_Internal;`
- the prototypes listed under **Interfaces** above.

Header skeleton:

```c
#ifndef XCP_INTERNAL_H
#define XCP_INTERNAL_H

#ifdef __cplusplus
extern "C" {
#endif /* #ifdef __cplusplus */

#ifndef XCP_H
#include "Xcp.h"
#endif /* #ifndef XCP_H */

/* ... moved content ... */

#ifdef __cplusplus
}
#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_INTERNAL_H */
```

- [ ] **Step 2: Move the handler bodies into their group files**

Each new `.c` file starts with:

```c
#ifndef XCP_INTERNAL_H
#include "Xcp_Internal.h"
#endif /* #ifndef XCP_INTERNAL_H */
```

Move, deleting the `static` keyword from each definition and deleting the now-duplicated forward declarations from `Xcp.c`:

- `Xcp_Std.c` — `Xcp_CTOCmdStdConnect`, `Xcp_CTOCmdStdDisconnect`, `Xcp_CTOCmdStdGetStatus`, `Xcp_CTOCmdStdSynch`, `Xcp_DTOCmdStdGetCommModeInfo`, `Xcp_DTOCmdStdGetId`, `Xcp_DTOCmdStdSetRequest`, `Xcp_DTOCmdStdGetSeed`, `Xcp_DTOCmdStdUnlock`, `Xcp_DTOCmdStdSetMta`, `Xcp_DTOCmdStdUpload`, `Xcp_DTOCmdStdShortUpload`, `Xcp_DTOCmdStdBuildChecksum`, `Xcp_DTOCmdStdTransportLayerCmd`, `Xcp_DTOCmdStdUserCmd`, the nine `Xcp_BuildChecksum*` functions, `Xcp_CRC16Table`, `Xcp_CRC16CITTTable`, `Xcp_CRC32Table`, `Xcp_CheckMasterSlaveKeyMatch`.
- `Xcp_Cal.c` — `Xcp_DTOCmdCalDownload`, `Xcp_DTOCmdCalDownloadNext`.
- `Xcp_Pag.c` — create with the include block only; it gains content in Task 13.
- `Xcp_Daq.c` — the seventeen `Xcp_DTOCmdDaq*` handlers plus `Xcp_DTODaqPacket` and `Xcp_DTODaqStimPacket`.

Leave in `Xcp.c`: `Xcp_Init`, `Xcp_GetVersionInfo`, `Xcp_SetTransmissionMode`, `Xcp_MainFunction`, `Xcp_CanIfRxIndication`, `Xcp_CanIfTxConfirmation`, `Xcp_CanIfTriggerTransmit`, the definition of `Xcp_Internal`, `Xcp_Ptr`, `Xcp_State`, all three dispatch tables, `Xcp_ReadSlaveMemoryTable`, `Xcp_WriteSlaveMemoryTable`, the event-queue helpers, the block-transfer helpers, the byte-order helpers, `Xcp_ElementSizeForAddressGranularity`, `Xcp_GetNumberOfAlignmentBytes`, `Xcp_FinalizeResPacket`, `Xcp_FillErrorPacket`, and the protection-status helpers — all with `static` removed where `Xcp_Internal.h` declares them.

- [ ] **Step 3: Wire up the build**

In `CMakeLists.txt`, replace the `add_library` line:

```cmake
add_library(Xcp STATIC
    source/Xcp.c
    source/Xcp_Std.c
    source/Xcp_Cal.c
    source/Xcp_Pag.c
    source/Xcp_Daq.c)
```

and the `--source` argument in `add_test`:

```cmake
        --source "${PROJECT_SOURCE_DIR}/source/Xcp.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Std.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Cal.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Pag.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Daq.c"
```

In `test.sh`, replace `gcov _cffi_xcp.c` with:

```sh
gcov Xcp.c Xcp_Std.c Xcp_Cal.c Xcp_Pag.c Xcp_Daq.c
```

In `.github/workflows/test.yml`, replace `files: ./build/Xcp.c.gcov` with:

```yaml
          files: ./build/Xcp.c.gcov,./build/Xcp_Std.c.gcov,./build/Xcp_Cal.c.gcov,./build/Xcp_Pag.c.gcov,./build/Xcp_Daq.c.gcov
```

- [ ] **Step 4: Run the suite and confirm no behaviour changed**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: identical to the Task 1 baseline — 42 passed, 13 skipped, same case counts.

A `defined but not used` warning means a helper was moved but its prototype was not added to `Xcp_Internal.h`. A `multiple definition` link error means a definition was left in `Xcp.c` as well as moved.

- [ ] **Step 5: Confirm every unit reports coverage**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c 'ls build/*.gcov'
```

Expected: five `.gcov` files, one per source. `Xcp_Pag.c.gcov` may be absent while the file has no code — that is fine until Task 13.

- [ ] **Step 6: Commit**

```bash
git add source/ CMakeLists.txt test.sh .github/workflows/test.yml
git commit -m "refactor: split Xcp.c into per-command-group translation units"
```

---

## Task 4: Complete the ASAM error code header

`interface/Xcp_Errors.h` carries eight of the fifteen codes in §1.7.3.1. Six of the missing ones are needed by the CAL and PAG handlers. Add all of them so the header is a complete transcription.

**Files:**
- Modify: `interface/Xcp_Errors.h`
- Test: `test/asam_error_matrix_test.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `XCP_E_ASAM_DAQ_ACTIVE`, `XCP_E_ASAM_WRITE_PROTECTED`, `XCP_E_ASAM_ACCESS_DENIED`, `XCP_E_ASAM_PAGE_NOT_VALID`, `XCP_E_ASAM_MODE_NOT_VALID`, `XCP_E_ASAM_SEGMENT_NOT_VALID`, `XCP_E_ASAM_DAQ_CONFIG`, `XCP_E_ASAM_MEMORY_OVERFLOW`, `XCP_E_ASAM_GENERIC`, `XCP_E_ASAM_VERIFY`.

- [ ] **Step 1: Write the failing test**

Append to `test/asam_error_matrix_test.py`:

```python
@pytest.mark.parametrize('name, code', (('XCP_E_ASAM_CMD_SYNCH', 0x00),
                                        ('XCP_E_ASAM_CMD_BUSY', 0x10),
                                        ('XCP_E_ASAM_DAQ_ACTIVE', 0x11),
                                        ('XCP_E_ASAM_PGM_ACTIVE', 0x12),
                                        ('XCP_E_ASAM_CMD_UNKNOWN', 0x20),
                                        ('XCP_E_ASAM_CMD_SYNTAX', 0x21),
                                        ('XCP_E_ASAM_OUT_OF_RANGE', 0x22),
                                        ('XCP_E_ASAM_WRITE_PROTECTED', 0x23),
                                        ('XCP_E_ASAM_ACCESS_DENIED', 0x24),
                                        ('XCP_E_ASAM_ACCESS_LOCKED', 0x25),
                                        ('XCP_E_ASAM_PAGE_NOT_VALID', 0x26),
                                        ('XCP_E_ASAM_MODE_NOT_VALID', 0x27),
                                        ('XCP_E_ASAM_SEGMENT_NOT_VALID', 0x28),
                                        ('XCP_E_ASAM_SEQUENCE', 0x29),
                                        ('XCP_E_ASAM_DAQ_CONFIG', 0x2A),
                                        ('XCP_E_ASAM_MEMORY_OVERFLOW', 0x30),
                                        ('XCP_E_ASAM_GENERIC', 0x31),
                                        ('XCP_E_ASAM_VERIFY', 0x32)))
def test_asam_error_codes_match_the_specification(name, code):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.1"""
    handle = XcpTest(DefaultConfig())
    assert handle.define(name) == code
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'mkdir -p build && cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k asam_error_codes" && make all && ctest -V'
```

Expected: FAIL — `KeyError: 'XCP_E_ASAM_DAQ_ACTIVE'` from `handle.define`, because the preprocessor never saw that macro.

- [ ] **Step 3: Add the missing codes**

In `interface/Xcp_Errors.h`, replace the block of `#define`s with the complete set, keeping the existing doxygen comment style:

```c
#define XCP_E_ASAM_CMD_SYNCH (0x00u)

#define XCP_E_ASAM_CMD_BUSY (0x10u)

#define XCP_E_ASAM_DAQ_ACTIVE (0x11u)

#define XCP_E_ASAM_PGM_ACTIVE (0x12u)

#define XCP_E_ASAM_CMD_UNKNOWN (0x20u)

#define XCP_E_ASAM_CMD_SYNTAX (0x21u)

#define XCP_E_ASAM_OUT_OF_RANGE (0x22u)

#define XCP_E_ASAM_WRITE_PROTECTED (0x23u)

#define XCP_E_ASAM_ACCESS_DENIED (0x24u)

#define XCP_E_ASAM_ACCESS_LOCKED (0x25u)

#define XCP_E_ASAM_PAGE_NOT_VALID (0x26u)

#define XCP_E_ASAM_MODE_NOT_VALID (0x27u)

#define XCP_E_ASAM_SEGMENT_NOT_VALID (0x28u)

#define XCP_E_ASAM_SEQUENCE (0x29u)

#define XCP_E_ASAM_DAQ_CONFIG (0x2Au)

#define XCP_E_ASAM_MEMORY_OVERFLOW (0x30u)

#define XCP_E_ASAM_GENERIC (0x31u)

#define XCP_E_ASAM_VERIFY (0x32u)
```

- [ ] **Step 4: Run the test and watch it pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k asam_error_codes" && make all && ctest -V'
```

Expected: PASS, 18 cases.

- [ ] **Step 5: Run the whole suite**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: baseline plus 18 new passing cases; 13 skipped, unchanged.

- [ ] **Step 6: Commit**

```bash
git add interface/Xcp_Errors.h test/asam_error_matrix_test.py
git commit -m "feat: complete ASAM error code definitions per section 1.7.3.1"
```

---

## Task 5: Fix the shared data-transfer initialiser (defects D1 and D8)

`Xcp_DataTransferInitialize` rejects requests that fit and accepts requests that overflow, hard-codes `DOWNLOAD`'s `MAX_CTO - 2` budget onto `UPLOAD`, latches block state on the failure path, and tests the wrong block-mode flag. `DOWNLOAD` will share it, so it must be correct before Task 6.

Per §1.6.1.2.7 `UPLOAD` block mode is **unbounded** — "For the master there are no limitations allowed concerning the maximum block size... the number of data elements (n) can be in the range [1..255]". Per §1.6.2.1.1 `DOWNLOAD` block mode **is** bounded by `MAX_BS`. The function therefore takes the bound from its caller.

**Files:**
- Modify: `source/Xcp.c` (`Xcp_DataTransferInitialize`), `source/Xcp_Internal.h` (its prototype), `source/Xcp_Std.c` (`Xcp_DTOCmdStdUpload` call site)
- Delete: `Xcp_DataTransferActive` (dead, byte-for-byte duplicate of `Xcp_BlockTransferIsActive`)
- Test: `test/upload_test.py`

**Interfaces:**
- Consumes: `Xcp_Internal.h` from Task 3.
- Produces:
  ```c
  Std_ReturnType Xcp_DataTransferInitialize(uint8 numberOfDataElements,
                                            uint8 elementSize,
                                            uint8 alignment,
                                            uint8 budget,
                                            boolean blockModeSupported,
                                            uint8 maxBlockSize);
  ```
  `budget` is the packet bytes available after the header — `MAX_CTO - 1` for `UPLOAD`, `MAX_CTO - 2` for `DOWNLOAD`. `maxBlockSize` of `0x00u` means unbounded. Returns `E_OK` and arms block state, or `E_NOT_OK` and leaves it untouched.

- [ ] **Step 1: Write the failing test**

Append to `test/upload_test.py`:

```python
@pytest.mark.parametrize('ag, max_cto, data_elements', (('BYTE', 0x08, 0x03),
                                                        ('BYTE', 0x08, 0x07),
                                                        ('WORD', 0x08, 0x01),
                                                        ('WORD', 0x08, 0x03),
                                                        ('DWORD', 0x08, 0x01)))
def test_upload_succeeds_with_slave_block_mode_disabled_and_payload_within_range(ag, max_cto, data_elements):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7: n is in [1..MAX_CTO/AG-1]."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   slave_block_mode=False,
                                   max_cto=max_cto))

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # UPLOAD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF5, data_elements)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k slave_block_mode_disabled_and_payload_within_range" && make all && ctest -V'
```

Expected: FAIL — the response is `0xFE 0x22` (`ERR_OUT_OF_RANGE`) instead of `0xFF`, on every one of the five cases.

- [ ] **Step 3: Rewrite the initialiser**

In `source/Xcp.c`, replace the whole `Xcp_DataTransferInitialize` body with:

```c
Std_ReturnType Xcp_DataTransferInitialize(uint8 numberOfDataElements,
                                          uint8 elementSize,
                                          uint8 alignment,
                                          uint8 budget,
                                          boolean blockModeSupported,
                                          uint8 maxBlockSize)
{
    Std_ReturnType result = E_OK;
    uint16 capacity;

    if ((numberOfDataElements != 0x00u) && (elementSize != 0x00u) && (budget >= alignment))
    {
        /* Number of elements that fit into a single frame, once the command header and any
         * address-granularity alignment bytes have been accounted for. */
        capacity = (uint16)((uint16)(budget - alignment) / elementSize);

        if (blockModeSupported == FALSE)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7 and 1.6.2.1.1
             * Without block transfer mode the whole payload travels in a single packet. */
            if ((uint16)numberOfDataElements > capacity)
            {
                result = E_NOT_OK;
            }
        }
        else if (maxBlockSize != 0x00u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
             * In block mode the master may send up to MAX_BS consecutive packets. */
            if ((uint32)numberOfDataElements > ((uint32)capacity * (uint32)maxBlockSize))
            {
                result = E_NOT_OK;
            }
        }
        else
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.7
             * For slave block transfer no maximum block size applies, so the uint8 range of the
             * request parameter is the only bound. */
        }

        if (result == E_OK)
        {
            Xcp_Internal.block_transfer.requested_elements = numberOfDataElements;
            Xcp_Internal.block_transfer.frame_elements = 0x00u;
        }
    }
    else
    {
        result = E_NOT_OK;
    }

    return result;
}
```

Delete `Xcp_DataTransferActive` entirely, together with its forward declaration and its prototype in `Xcp_Internal.h`. It has no callers and duplicates `Xcp_BlockTransferIsActive`.

Update the prototype in `source/Xcp_Internal.h` to the six-parameter form.

- [ ] **Step 4: Update the UPLOAD call site**

In `source/Xcp_Std.c`, inside `Xcp_DTOCmdStdUpload`, replace the call with:

```c
        if (Xcp_DataTransferInitialize(number_of_data_elements,
                                       element_size,
                                       (uint8)alignment,
                                       (uint8)(Xcp_Ptr->general->maxCto - 0x01u),
                                       Xcp_Ptr->general->slaveBlockModeSupported,
                                       0x00u) == E_OK)
```

- [ ] **Step 5: Run the new test and the existing upload tests**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k upload" && make all && ctest -V'
```

Expected: PASS. The five new cases pass, and `test_upload_returns_err_out_of_range_if_slave_block_mode_is_disabled_and_payload_exceeds_range` still passes — with the corrected capacity, `BYTE`/8 elements exceeds 7, `WORD`/4 exceeds 3, and `DWORD`/2 exceeds 1, so all three are still rejected.

- [ ] **Step 6: Run the whole suite**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: baseline plus the new cases, 13 skipped.

- [ ] **Step 7: Commit**

```bash
git add source/ test/upload_test.py
git commit -m "fix: correct range check and block-mode bound in Xcp_DataTransferInitialize"
```

---

## Task 6: DOWNLOAD in standard mode

The handler currently validates the element count and then has an empty success branch, so nothing is written and no positive response is built. It also gates on `slaveBlockModeSupported`, which is defect D8 — §1.6.1.2.1 makes `MAX_BS` a *master* block-mode parameter naming `DOWNLOAD_NEXT` explicitly.

**Files:**
- Modify: `source/Xcp_Cal.c` (`Xcp_DTOCmdCalDownload`)
- Test: `test/download_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_DataTransferInitialize` (Task 5), `Xcp_BlockTransferWriteSlaveMemory`, `Xcp_ElementSizeForAddressGranularity`, `Xcp_GetNumberOfAlignmentBytes`, `Xcp_FillErrorPacket`, `Xcp_FinalizeResPacket` (Task 3).
- Produces: a working `DOWNLOAD` for the single-packet case; Task 7 extends the same handler for block mode.

- [ ] **Step 1: Write the failing test**

Create `test/download_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest


def connect(handle):
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def set_mta(handle, mta, byte_order='LITTLE_ENDIAN'):
    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xF6, 0x00, 0x00, 0x00) + tuple(u32_to_array(mta, byte_order))))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))


def capture_writes(handle, element_size, byte_order='LITTLE_ENDIAN'):
    written = list()

    def write_slave_memory(p_address, p_buffer):
        value = bytes(p_buffer[0:element_size])
        written.append((int(handle.ffi.cast('uint32_t', p_address)),
                        int.from_bytes(value, dict(BIG_ENDIAN='big', LITTLE_ENDIAN='little')[byte_order])))

    handle.xcp_write_slave_memory_u8.side_effect = write_slave_memory
    handle.xcp_write_slave_memory_u16.side_effect = write_slave_memory
    handle.xcp_write_slave_memory_u32.side_effect = write_slave_memory
    return written


def test_download_writes_the_payload_to_the_mta_and_acknowledges():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=False,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)
    written = capture_writes(handle, 1)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x03, 0x11, 0x22, 0x33)))
    handle.lib.Xcp_MainFunction()

    assert written == [(0xDEADBEEF, 0x11), (0xDEADBEF0, 0x22), (0xDEADBEF1, 0x33)]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_download_returns_err_out_of_range_when_the_count_exceeds_a_single_packet():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=False,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x07, 0x11, 0x22, 0x33)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


@pytest.mark.parametrize('master_block_mode, slave_block_mode, expect_accepted', ((False, False, False),
                                                                                  (False, True, False),
                                                                                  (True, False, True),
                                                                                  (True, True, True)))
def test_download_block_mode_follows_the_master_block_mode_flag(master_block_mode,
                                                                slave_block_mode,
                                                                expect_accepted):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.1: MAX_BS belongs to master block mode."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=master_block_mode,
                                   slave_block_mode=slave_block_mode,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0xDEADBEEF)
    capture_writes(handle, 1)

    # 10 elements needs more than one packet, so it is only legal in master block mode.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66)))
    handle.lib.Xcp_MainFunction()

    if expect_accepted:
        assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2] != [0xFE, 0x22]
    else:
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k download" && make all && ctest -V'
```

Expected: FAIL — `written` is empty because the success branch does nothing, and the block-mode parametrisation fails on the `(True, False)` and `(False, True)` rows because the handler reads the wrong flag.

- [ ] **Step 3: Implement the handler**

In `source/Xcp_Cal.c`, replace `Xcp_DTOCmdCalDownload` entirely:

```c
uint8 Xcp_DTOCmdCalDownload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
     * The data block of the specified length (size) contained in the CMD will be copied into
     * memory, starting at the MTA. The MTA will be post-incremented by the number of data bytes.
     *
     * XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.1
     * MAX_BS applies to master block mode, whose packets are DOWNLOAD_NEXT. Slave block mode
     * governs multi-response commands such as UPLOAD and is not consulted here. */
    if (Xcp_DataTransferInitialize(number_of_data_elements,
                                   element_size,
                                   alignment,
                                   (uint8)(Xcp_Ptr->general->maxCto - 0x02u),
                                   Xcp_Ptr->general->masterBlockModeSupported,
                                   Xcp_Ptr->general->maxBS) == E_OK)
    {
        if (Xcp_BlockTransferWriteSlaveMemory(&pPduInfo->SduDataPtr[0x02u + alignment],
                                              element_size) == E_NOT_OK)
        {
            /* The whole payload has been written, so the command is acknowledged now. */
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

            Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
             * The slave device will acknowledge only the last DOWNLOAD_NEXT command packet. */
            *responseExpected = FALSE;
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k download" && make all && ctest -V'
```

Expected: PASS on all six cases.

- [ ] **Step 5: Run the whole suite**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: baseline plus the new cases. Watch `TestDownloadErrorHandling` in `asam_error_matrix_test.py` — it was written against the old behaviour and may now need its expectations corrected. If a case there fails, verify the new behaviour against §1.7.3.2.2 before changing the test.

- [ ] **Step 6: Commit**

```bash
git add source/Xcp_Cal.c test/download_test.py
git commit -m "feat: implement DOWNLOAD write path and gate block mode on master block mode"
```

---

## Task 7: DOWNLOAD_NEXT and block transfer

§1.6.2.2.1 requires a negative response carrying a payload — the expected element count in byte 2. No such mechanism exists; `Xcp_FillErrorPacket` writes a bare two-byte packet. This task introduces the general form, which defect D6 will reuse for `BUILD_CHECKSUM`.

**Files:**
- Modify: `source/Xcp.c` (add `Xcp_FillErrorPacketWithData`, `Xcp_BlockTransferAbort`), `source/Xcp_Internal.h`, `source/Xcp_Cal.c` (`Xcp_DTOCmdCalDownloadNext`)
- Test: `test/download_next_test.py` (create)

**Interfaces:**
- Consumes: Task 6's `DOWNLOAD`.
- Produces:
  ```c
  void Xcp_FillErrorPacketWithData(const uint8 errorCode, const uint8 *pData,
                                   const uint8 dataLength, PduInfoType *pPduInfo);
  void Xcp_BlockTransferAbort(void);
  ```

- [ ] **Step 1: Write the failing test**

Create `test/download_next_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes


def test_download_next_completes_a_block_transfer_and_acknowledges_only_the_last_packet():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1, diagram 23."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00001000)
    written = capture_writes(handle, 1)

    handle.can_if_transmit.reset_mock()

    # DOWNLOAD(0x0E, d0..d5) - 14 elements announced, 6 carried.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0E, 0, 1, 2, 3, 4, 5)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 0, 'intermediate packets must not be acknowledged'

    # DOWNLOAD_NEXT(0x08, d6..d11)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x08, 6, 7, 8, 9, 10, 11)))
    handle.lib.Xcp_MainFunction()
    assert handle.can_if_transmit.call_count == 0, 'intermediate packets must not be acknowledged'

    # DOWNLOAD_NEXT(0x02, d12 d13)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 12, 13)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
    assert written == [(0x00001000 + i, i) for i in range(14)]


def test_download_next_returns_err_sequence_with_the_expected_count_on_mismatch():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1 negative response."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00001000)
    capture_writes(handle, 1)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0E, 0, 1, 2, 3, 4, 5)))
    handle.lib.Xcp_MainFunction()

    # 8 elements remain; announce 7 instead.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x07, 6, 7, 8, 9, 10, 11)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFE, 0x29, 0x08)


def test_download_next_without_an_active_block_transfer_returns_err_sequence():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00001000)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEF, 0x02, 0x11, 0x22)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFE, 0x29, 0x00)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k download_next" && make all && ctest -V'
```

Expected: FAIL — `Xcp_DTOCmdCalDownloadNext` is an empty stub that returns `E_OK` with a stale buffer.

- [ ] **Step 3: Add the two helpers**

In `source/Xcp.c`, immediately after `Xcp_FillErrorPacket`:

```c
void Xcp_FillErrorPacketWithData(const uint8 errorCode,
                                 const uint8 *pData,
                                 const uint8 dataLength,
                                 PduInfoType *pPduInfo)
{
    uint8_least idx;

    pPduInfo->SduDataPtr[0x00u] = XCP_PID_ERROR;
    pPduInfo->SduDataPtr[0x01u] = errorCode;

    for (idx = 0x00u; idx < dataLength; idx++)
    {
        pPduInfo->SduDataPtr[0x02u + idx] = pData[idx];
    }

    Xcp_FinalizeResPacket((PduLengthType)(0x02u + dataLength), pPduInfo);
}

void Xcp_BlockTransferAbort(void)
{
    Xcp_Internal.block_transfer.requested_elements = 0x00u;
    Xcp_Internal.block_transfer.frame_elements = 0x00u;
}
```

Add both prototypes to `source/Xcp_Internal.h`.

- [ ] **Step 4: Implement the handler**

In `source/Xcp_Cal.c`, replace `Xcp_DTOCmdCalDownloadNext` entirely:

```c
uint8 Xcp_DTOCmdCalDownloadNext(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];
    uint8 expected = 0x00u;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1
     * It contains the remaining number of data elements to transmit. The slave device will use
     * this information to detect lost packets. If a sequence error has been detected, the error
     * code ERR_SEQUENCE will be returned. The negative response will contain the expected number
     * of data elements. */
    if (Xcp_BlockTransferIsActive() == TRUE)
    {
        expected = Xcp_Internal.block_transfer.requested_elements;

        if (number_of_data_elements == expected)
        {
            if (Xcp_BlockTransferWriteSlaveMemory(&pPduInfo->SduDataPtr[0x02u + alignment],
                                                  element_size) == E_NOT_OK)
            {
                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

                Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
            }
            else
            {
                *responseExpected = FALSE;
            }
        }
        else
        {
            Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE,
                                        &expected,
                                        0x01u,
                                        &Xcp_Internal.cto_response.pdu_info);

            Xcp_BlockTransferAbort();
        }
    }
    else
    {
        Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE,
                                    &expected,
                                    0x01u,
                                    &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

- [ ] **Step 5: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k download" && make all && ctest -V'
```

Expected: PASS — the three new cases plus Task 6's six.

- [ ] **Step 6: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/download_next_test.py
git commit -m "feat: implement DOWNLOAD_NEXT block transfer with sequence error payload"
```

---

## Task 8: DOWNLOAD_MAX

Fixed-size transfer of `MAX_CTO/AG - 1` elements from the MTA. PID `0xEE` currently dispatches to `Xcp_DTODaqPacket`.

Per design decision DD3, arriving during an active block transfer yields `ERR_SEQUENCE` — §1.6.2.2.2 forbids the situation but names no code, and the error matrix constrains master reactions rather than what a slave may emit.

`ctoInfo[]` carries a four-bit minimum request size, which cannot express `MAX_CTO`, so the handler checks the length itself — the same approach `TRANSPORT_LAYER_CMD` already uses.

**Files:**
- Modify: `source/Xcp_Cal.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xEE`)
- Test: `test/download_max_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_BlockTransferAbort` (Task 7), `Xcp_WriteSlaveMemoryTable` (Task 3).
- Produces: `uint8 Xcp_DTOCmdCalDownloadMax(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/download_max_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes


@pytest.mark.parametrize('ag, max_cto, expected_count', (('BYTE', 8, 7),
                                                         ('WORD', 8, 3),
                                                         ('DWORD', 8, 1)))
def test_download_max_writes_a_fixed_number_of_elements(ag, max_cto, expected_count):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2: MAX_CTO/AG-1 elements."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity=ag,
                                   max_cto=max_cto))
    connect(handle)
    set_mta(handle, 0x00002000)
    element_size = element_size_from_address_granularity(ag)
    written = capture_writes(handle, element_size)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple([0xEE] + [0x00] * (max_cto - 1))))
    handle.lib.Xcp_MainFunction()

    assert len(written) == expected_count
    assert [a for a, _ in written] == [0x00002000 + (i * element_size) for i in range(expected_count)]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_download_max_returns_err_cmd_syntax_when_the_packet_is_short():
    """The minimum request size is MAX_CTO, which ctoInfo's 4-bit field cannot express."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00002000)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEE, 0x11, 0x22)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)


def test_download_max_inside_a_block_transfer_returns_err_sequence():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2 forbids use within a block sequence."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   master_block_mode=True,
                                   max_bs=255,
                                   max_cto=8))
    connect(handle)
    set_mta(handle, 0x00002000)
    capture_writes(handle, 1)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x0E, 0, 1, 2, 3, 4, 5)))
    handle.lib.Xcp_MainFunction()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(tuple([0xEE] + [0x00] * 7)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x29)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k download_max" && make all && ctest -V'
```

Expected: FAIL — `0xEE` dispatches to `Xcp_DTODaqPacket`, so nothing is written and the response is stale.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Cal.c`:

```c
uint8 Xcp_DTOCmdCalDownloadMax(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    uint8 number_of_data_elements;
    uint8_least idx;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2
     * This command does not support block transfer and it mustn't be used within a block transfer
     * sequence. The specification prescribes no error code for the violation; ERR_SEQUENCE is the
     * accurate one and leaves the master able to recover. */
    if (Xcp_BlockTransferIsActive() == TRUE)
    {
        Xcp_BlockTransferAbort();

        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (pPduInfo->SduLength < (PduLengthType)Xcp_Ptr->general->maxCto)
    {
        /* The minimum request size of this command is MAX_CTO, which does not fit the four-bit
         * field of ctoInfo, so the check happens here. */
        Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2
         * The data block with the fixed length (size) of MAX_CTO/AG-1 elements contained in the
         * CMD will be copied into memory, starting at the MTA. The MTA will be post-incremented by
         * MAX_CTO/AG-1. */
        number_of_data_elements = (uint8)((Xcp_Ptr->general->maxCto / element_size) - 0x01u);

        for (idx = 0x00u; idx < number_of_data_elements; idx++)
        {
            Xcp_WriteSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](
                Xcp_Internal.memory_transfer.address,
                &pPduInfo->SduDataPtr[element_size + (idx * element_size)]);

            Xcp_Internal.memory_transfer.address += element_size;
        }

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h`, and in `source/Xcp.c` change the `Xcp_PIDTable` entry at `0xEE` from `Xcp_DTODaqPacket` to:

```c
    Xcp_DTOCmdCalDownloadMax, /* DOWNLOAD_MAX 0xEE, optional */
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k download_max" && make all && ctest -V'
```

Expected: PASS on all five cases.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/download_max_test.py
git commit -m "feat: implement DOWNLOAD_MAX"
```

---

## Task 9: SHORT_DOWNLOAD

Carries its own address and extension, writes the block, and leaves the MTA pointing at the first element past it. Capacity is `(MAX_CTO-8)/AG`, which is **zero** on XCP-on-CAN — §1.6.2.2.3 says so outright, so the command is implemented but transfers nothing at that MAX_CTO. It ships ENABLED: see DD5, which was revised once the command existed, because disabling it also cleared CONNECT's CAL/PAG resource bit.

**Files:**
- Modify: `source/Xcp_Cal.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xED`)
- Test: `test/short_download_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_CopyToU32WithOrder`, `Xcp_BlockTransferAbort`.
- Produces: `uint8 Xcp_DTOCmdCalShortDownload(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/short_download_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta, capture_writes


@pytest.mark.parametrize('byte_order', byte_orders)
def test_short_download_writes_at_its_own_address(byte_order):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   address_granularity='BYTE',
                                   byte_order=byte_order,
                                   max_cto=16))
    connect(handle)
    written = capture_writes(handle, 1, byte_order)

    payload = (0xED, 0x03, 0x00, 0x02) + tuple(u32_to_array(0x00003000, byte_order)) + (0xAA, 0xBB, 0xCC)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert written == [(0x00003000, 0xAA), (0x00003001, 0xBB), (0x00003002, 0xCC)]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_short_download_leaves_the_mta_behind_the_written_block():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: MTA is set behind the block."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=16))
    connect(handle)
    written = capture_writes(handle, 1)

    payload = (0xED, 0x03, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN')) + (0xAA, 0xBB, 0xCC)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # A following DOWNLOAD must continue at 0x3003.
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF0, 0x01, 0xDD)))
    handle.lib.Xcp_MainFunction()

    assert written[-1] == (0x00003003, 0xDD)


def test_short_download_returns_err_out_of_range_when_the_count_exceeds_capacity():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: n is in [0..(MAX_CTO-8)/AG]."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=16))
    connect(handle)

    payload = (0xED, 0x09, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN')) + tuple([0] * 8)
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)


def test_short_download_carries_no_data_when_max_cto_is_eight():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3: no effect if MAX_CTO = 8."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    written = capture_writes(handle, 1)

    payload = (0xED, 0x00, 0x00, 0x00) + tuple(u32_to_array(0x00003000, 'LITTLE_ENDIAN'))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()

    assert written == []
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k short_download" && make all && ctest -V'
```

Expected: FAIL — `0xED` dispatches to `Xcp_DTODaqPacket`.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Cal.c`:

```c
uint8 Xcp_DTOCmdCalShortDownload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];
    uint8 capacity = 0x00u;
    uint32 address;
    uint8_least idx;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3
     * Please note that this command will have no effect (no data bytes can be transferred) if
     * MAX_CTO = 8 (e.g. XCP on CAN). */
    if (Xcp_Ptr->general->maxCto >= 0x08u)
    {
        capacity = (uint8)((Xcp_Ptr->general->maxCto - 0x08u) / element_size);
    }

    if (Xcp_BlockTransferIsActive() == TRUE)
    {
        /* This command mustn't be used within a block transfer sequence. */
        Xcp_BlockTransferAbort();

        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (number_of_data_elements > capacity)
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3
         * If the number of elements exceeds (MAX_CTO-8)/AG, the error code ERR_OUT_OF_RANGE will
         * be returned. */
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &address, Xcp_Ptr->general->byteOrder);

        Xcp_Internal.memory_transfer.extension = pPduInfo->SduDataPtr[0x03u];

        for (idx = 0x00u; idx < number_of_data_elements; idx++)
        {
            Xcp_WriteSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](
                (void *)address,
                &pPduInfo->SduDataPtr[0x08u + (idx * element_size)]);

            address += element_size;
        }

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3
         * The MTA pointer is set to the first data element behind the downloaded data block. */
        Xcp_Internal.memory_transfer.address = (void *)address;

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h`, and change the `Xcp_PIDTable` entry at `0xED` to:

```c
    Xcp_DTOCmdCalShortDownload, /* SHORT_DOWNLOAD 0xED, optional */
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k short_download" && make all && ctest -V'
```

Expected: PASS on all five cases.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/short_download_test.py
git commit -m "feat: implement SHORT_DOWNLOAD"
```

---

## Task 10: MODIFY_BITS

A 32-bit read-modify-write at the MTA. The masks are 16-bit and **must be widened to 32 bits before shifting** — computing `(uint16)~MA << S` at 16-bit width silently discards the high bits for any `S >= 1`.

`S` is bounded to `[0..31]`; a larger shift is undefined behaviour in C, and `ERR_OUT_OF_RANGE` is in this command's row of §1.7.3.2.2.

**Files:**
- Modify: `source/Xcp_Cal.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xEC`)
- Test: `test/modify_bits_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_CopyToU16WithOrder`, `Xcp_CopyToU32WithOrder`, `Xcp_CopyFromU32WithOrder`, `Xcp_ReadSlaveMemoryU32`, `Xcp_WriteSlaveMemoryU32`.
- Produces: `uint8 Xcp_DTOCmdCalModifyBits(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/modify_bits_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect, set_mta


def run_modify_bits(handle, initial, shift, and_mask, xor_mask, byte_order='LITTLE_ENDIAN'):
    result = dict()

    def read_slave_memory(_p_address, _extension, p_buffer):
        for i, b in enumerate(u32_to_array(initial, byte_order)):
            p_buffer[i] = b

    def write_slave_memory(p_address, p_buffer):
        result['address'] = int(handle.ffi.cast('uint32_t', p_address))
        result['value'] = u32_from_array(bytes(p_buffer[0:4]), byte_order)

    handle.xcp_read_slave_memory_u32.side_effect = read_slave_memory
    handle.xcp_write_slave_memory_u32.side_effect = write_slave_memory

    payload = (0xEC, shift) + tuple(u16_to_array(and_mask, byte_order)) + tuple(u16_to_array(xor_mask, byte_order))
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info(payload))
    handle.lib.Xcp_MainFunction()
    return result


def test_modify_bits_matches_the_specification_example():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4 worked example."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    result = run_modify_bits(handle, 0xFFF0FFFF, 16, 0xBFFE, 0x0001)

    assert result['value'] == 0xBFF1FFFF
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('shift, and_mask, xor_mask, initial, expected', ((0, 0xFFFE, 0x0000, 0xFFFFFFFF, 0xFFFFFFFE),
                                                                          (0, 0xFFFE, 0x0001, 0xFFFFFFFE, 0xFFFFFFFF),
                                                                          (8, 0xFFFF, 0x00FF, 0x00000000, 0x0000FF00),
                                                                          (16, 0xFFFF, 0xFFFF, 0x00000000, 0xFFFF0000)))
def test_modify_bits_applies_the_mask_formula(shift, and_mask, xor_mask, initial, expected):
    """The masks must be widened to 32 bits before shifting."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    assert run_modify_bits(handle, initial, shift, and_mask, xor_mask)['value'] == expected


def test_modify_bits_does_not_move_the_mta():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4: The MTA will not be affected."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    first = run_modify_bits(handle, 0x00000000, 0, 0xFFFF, 0x0001)
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
    second = run_modify_bits(handle, 0x00000000, 0, 0xFFFF, 0x0001)

    assert first['address'] == second['address'] == 0x00004000


def test_modify_bits_returns_err_out_of_range_for_a_shift_above_31():
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, address_granularity='BYTE', max_cto=8))
    connect(handle)
    set_mta(handle, 0x00004000)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEC, 0x20, 0xFF, 0xFF, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x22)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k modify_bits" && make all && ctest -V'
```

Expected: FAIL — `0xEC` dispatches to `Xcp_DTODaqPacket`, so no write callback fires and `result` is empty.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Cal.c`:

```c
uint8 Xcp_DTOCmdCalModifyBits(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 shift_value = pPduInfo->SduDataPtr[0x01u];
    uint16 and_mask;
    uint16 xor_mask;
    uint32 value;
    uint8 buffer[0x04u];

    *responseExpected = TRUE;

    /* A shift of 32 or more is undefined behaviour on a 32 bit value. The specification puts no
     * bound on S, so the request is rejected rather than evaluated. */
    if (shift_value > 0x1Fu)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &and_mask, Xcp_Ptr->general->byteOrder);
        Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x04u], &xor_mask, Xcp_Ptr->general->byteOrder);

        Xcp_ReadSlaveMemoryU32(Xcp_Internal.memory_transfer.address,
                               Xcp_Internal.memory_transfer.extension,
                               &buffer[0x00u]);

        Xcp_CopyToU32WithOrder(&buffer[0x00u], &value, Xcp_Ptr->general->byteOrder);

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4
         * A = ( (A) & ((~((dword)(((word)~MA)<<S))) )^((dword)(MX<<S)) )
         * Both masks are widened to 32 bits before shifting; evaluating the shift at 16 bit width
         * would discard the high bits for any S >= 1. */
        value = (value & (~(((uint32)((uint16)(~and_mask))) << shift_value))) ^
                (((uint32)xor_mask) << shift_value);

        Xcp_CopyFromU32WithOrder(value, &buffer[0x00u], Xcp_Ptr->general->byteOrder);

        Xcp_WriteSlaveMemoryU32(Xcp_Internal.memory_transfer.address, &buffer[0x00u]);

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4
         * The MTA will not be affected. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h`, and change the `Xcp_PIDTable` entry at `0xEC` to:

```c
    Xcp_DTOCmdCalModifyBits, /* MODIFY_BITS 0xEC, optional */
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k modify_bits" && make all && ctest -V'
```

Expected: PASS on all eight cases. If `test_modify_bits_applies_the_mask_formula[16-...]` fails with `0x00000000`, a cast is missing and the shift happened at 16-bit width.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/modify_bits_test.py
git commit -m "feat: implement MODIFY_BITS"
```

---

## Task 11: Segment and page configuration model

Page switching needs a segment/page model that does not exist anywhere today. Every field below answers a specific response field in §1.6.3.2 — nothing is speculative — and the shape mirrors the AML `struct Segment` in §2.1.

`segments` and `paging` are **optional** in the schema so existing configurations keep validating.

**Files:**
- Modify: `config/xcp.schema.json`, `config/xcp.json`, `interface/Xcp_Types.h`, `script/source_cfg.c.jinja2`, `script/source_rt.c.jinja2`, `test/parameter.py`
- Test: none of its own; verified through the generated output and the unchanged suite

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `Xcp_AddressMappingType { const uint32 sourceAddress; const uint32 destinationAddress; const uint32 length; }`
  - `Xcp_PageType { const uint8 initSegment; const uint8 pageProperties; }`
  - `Xcp_SegmentType { const uint32 address; const uint32 length; const uint8 addressExtension; const uint8 compressionMethod; const uint8 encryptionMethod; const uint8 maxPages; const Xcp_PageType *page; const uint8 maxMapping; const Xcp_AddressMappingType *addressMapping; }`
  - `Xcp_SegmentRtType { boolean freeze; }`
  - `Xcp_ConfigType` gains, appended last: `const Xcp_SegmentType *segment;`
  - `Xcp_GeneralType` gains, appended last: `const uint8 maxSegment; const uint8 pagProperties;`
  - `Xcp_RtType` gains, appended last: `Xcp_SegmentRtType *segment;`
  - `DefaultConfig(segments=..., freeze_supported=...)` in `test/parameter.py`, plus module-level helpers `segment(...)` and `page(...)`.

This task has no failing test of its own: it adds configuration plumbing with no observable
protocol behaviour, and the first command that reads it arrives in Task 14. Its verification
is that the generated code compiles, carries the expected values, and breaks nothing.

`ctest` runs pytest with `-x`, so the suite stops at the first failure. Never leave a test
failing at the end of a task.

- [ ] **Step 1: Add the schema definitions**

In `config/xcp.schema.json`, add to the `definitions` object:

```json
    "page_access_type": {
      "type": "string",
      "enum": ["NOT_ALLOWED", "WITHOUT_OTHER", "WITH_OTHER", "DONT_CARE"]
    },
    "page": {
      "type": "object",
      "properties": {
        "init_segment": {"type": "integer", "minimum": 0, "maximum": 255},
        "ecu_access": {"$ref": "#/definitions/page_access_type"},
        "xcp_read_access": {"$ref": "#/definitions/page_access_type"},
        "xcp_write_access": {"$ref": "#/definitions/page_access_type"}
      },
      "required": ["init_segment", "ecu_access", "xcp_read_access", "xcp_write_access"],
      "additionalProperties": false
    },
    "address_mapping": {
      "type": "object",
      "properties": {
        "source_address": {"type": "integer", "minimum": 0},
        "destination_address": {"type": "integer", "minimum": 0},
        "length": {"type": "integer", "minimum": 0}
      },
      "required": ["source_address", "destination_address", "length"],
      "additionalProperties": false
    },
    "segment": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "address": {"type": "integer", "minimum": 0},
        "length": {"type": "integer", "minimum": 0},
        "address_extension": {"type": "integer", "minimum": 0, "maximum": 255},
        "compression_method": {"type": "integer", "minimum": 0, "maximum": 255},
        "encryption_method": {"type": "integer", "minimum": 0, "maximum": 255},
        "pages": {"type": "array", "minItems": 1, "items": {"$ref": "#/definitions/page"}},
        "address_mappings": {"type": "array", "items": {"$ref": "#/definitions/address_mapping"}}
      },
      "required": ["name", "address", "length", "address_extension",
                   "compression_method", "encryption_method", "pages"],
      "additionalProperties": false
    },
    "paging": {
      "type": "object",
      "properties": {
        "freeze_supported": {"type": "boolean"}
      },
      "required": ["freeze_supported"],
      "additionalProperties": false
    },
```

and add to the configuration item's `properties` (not to its `required` list):

```json
        "segments": {"type": "array", "items": {"$ref": "#/definitions/segment"}},
        "paging": {"$ref": "#/definitions/paging"},
```

- [ ] **Step 2: Add the C types**

In `interface/Xcp_Types.h`, immediately before `Xcp_GeneralType`:

```c
/**
 * @brief address range within a SEGMENT that has an address mapping applied.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 2.
 */
typedef struct
{
    const uint32 sourceAddress;
    const uint32 destinationAddress;
    const uint32 length;
} Xcp_AddressMappingType;

/**
 * @brief a single calibration PAGE of a SEGMENT.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.3.
 */
typedef struct
{
    /**
     * @brief SEGMENT that initializes this PAGE.
     */
    const uint8 initSegment;

    /**
     * @brief PAGE_PROPERTIES, packed as ecu access at bits 1:0, XCP read access at bits 3:2 and
     * XCP write access at bits 5:4.
     */
    const uint8 pageProperties;
} Xcp_PageType;

/**
 * @brief a logical calibration data SEGMENT.
 * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2.
 */
typedef struct
{
    const uint32 address;
    const uint32 length;
    const uint8 addressExtension;
    const uint8 compressionMethod;
    const uint8 encryptionMethod;
    const uint8 maxPages;
    const Xcp_PageType *page;
    const uint8 maxMapping;
    const Xcp_AddressMappingType *addressMapping;
} Xcp_SegmentType;
```

Append to `Xcp_GeneralType`, after `identification`:

```c
    const uint8 maxSegment; /* not part of the specification... */
    const uint8 pagProperties; /* not part of the specification... */
```

Append to `Xcp_ConfigType`, after `pdu`:

```c
    const Xcp_SegmentType *segment;
```

Add next to `Xcp_RtType`, and extend that struct:

```c
typedef struct {
    /**
     * @brief FREEZE mode of this SEGMENT.
     * @note XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.4.
     */
    boolean freeze;
} Xcp_SegmentRtType;

typedef struct {
    Xcp_EventQueueType *eventQueue;
    Xcp_SegmentRtType *segment;
} Xcp_RtType;
```

- [ ] **Step 3: Emit the tables from the generator**

In `script/source_cfg.c.jinja2`, before the `Xcp_ConfigType` block, add:

```jinja
{%- for configuration in configurations %}
{%- set configuration_loop = loop %}
{%- for segment in configuration.segments | default([]) %}
#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

static const Xcp_PageType Xcp_PageConfig{{'%02X' % configuration_loop.index0}}Segment{{'%02X' % loop.index0}}[{{'0x%02Xu' % segment.pages|length}}] = {
    {%- for page in segment.pages %}
    {
        {{'0x%02Xu' % page.init_segment}}, /* initSegment */
        ({{page_access_value(page.ecu_access)}} << 0x00u) |
        ({{page_access_value(page.xcp_read_access)}} << 0x02u) |
        ({{page_access_value(page.xcp_write_access)}} << 0x04u) /* pageProperties */
    },
    {%- endfor %}
};

static const Xcp_AddressMappingType Xcp_AddressMappingConfig{{'%02X' % configuration_loop.index0}}Segment{{'%02X' % loop.index0}}[{{'0x%02Xu' % ((segment.address_mappings | default([]))|length + 1)}}] = {
    {%- for mapping in segment.address_mappings | default([]) %}
    {
        {{'0x%08Xu' % mapping.source_address}},
        {{'0x%08Xu' % mapping.destination_address}},
        {{'0x%08Xu' % mapping.length}}
    },
    {%- endfor %}
    {0x00000000u, 0x00000000u, 0x00000000u} /* sentinel, keeps the array non-empty */
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"
{%- endfor %}

#define Xcp_START_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"

static const Xcp_SegmentType Xcp_SegmentConfig{{'%02X' % loop.index0}}[{{'0x%02Xu' % ((configuration.segments | default([]))|length + 1)}}] = {
{%- for segment in configuration.segments | default([]) %}
    {
        {{'0x%08Xu' % segment.address}},
        {{'0x%08Xu' % segment.length}},
        {{'0x%02Xu' % segment.address_extension}},
        {{'0x%02Xu' % segment.compression_method}},
        {{'0x%02Xu' % segment.encryption_method}},
        {{'0x%02Xu' % segment.pages|length}},
        &Xcp_PageConfig{{'%02X' % configuration_loop.index0}}Segment{{'%02X' % loop.index0}}[0x00u],
        {{'0x%02Xu' % (segment.address_mappings | default([]))|length}},
        &Xcp_AddressMappingConfig{{'%02X' % configuration_loop.index0}}Segment{{'%02X' % loop.index0}}[0x00u]
    },
{%- endfor %}
    {0x00000000u, 0x00000000u, 0x00u, 0x00u, 0x00u, 0x00u, NULL_PTR, 0x00u, NULL_PTR} /* sentinel */
};

#define Xcp_STOP_SEC_CONST_UNSPECIFIED
#include "Xcp_MemMap.h"
{%- endfor %}
```

The trailing sentinel entries exist because C forbids zero-length arrays; `maxSegment` and `maxMapping` bound every loop, so the sentinels are never read.

`page_access_value` is a filter the template does not have. Rather than depend on `bsw_code_gen` supporting custom filters, express it inline — replace each `{{page_access_value(x)}}` with the equivalent conditional chain, for example for `ecu_access`:

```jinja
        ({% if page.ecu_access == 'NOT_ALLOWED' %}0x00u{% elif page.ecu_access == 'WITHOUT_OTHER' %}0x01u{% elif page.ecu_access == 'WITH_OTHER' %}0x02u{% else %}0x03u{% endif %} << 0x00u) |
```

and likewise for `xcp_read_access` shifted by `0x02u` and `xcp_write_access` by `0x04u`.

Add to the `Xcp_ConfigType` initialiser, as the new last member:

```jinja
    &Xcp_SegmentConfig{{'%02X' % loop.index0}}[0x00u] /* reference to XcpSegment */
```

(remembering to add a comma after the previous `NULL_PTR /* reference to XcpPdu */`).

Add to the `Xcp_GeneralType` initialiser, after the `identification` line:

```jinja
    {{'0x%02Xu' % (configuration.segments | default([]))|length}}, /* maxSegment */
    {% if configuration.paging is defined and configuration.paging.freeze_supported %}0x01u{% else %}0x00u{% endif %}, /* pagProperties */
```

- [ ] **Step 4: Emit the runtime array**

In `script/source_rt.c.jinja2`, inside the per-configuration loop, after the event queue definition:

```jinja
#define Xcp_START_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"

static Xcp_SegmentRtType Xcp_SegmentRt{{'%02X' % loop.index0}}[{{'0x%02Xu' % ((configuration.segments | default([]))|length + 1)}}];

#define Xcp_STOP_SEC_VAR_FAST_POWER_ON_INIT_UNSPECIFIED
#include "Xcp_MemMap.h"
```

and extend the `Xcp_Rt` initialiser:

```jinja
    {
        &Xcp_EventQueue{{'%02X' % loop.index0}},
        &Xcp_SegmentRt{{'%02X' % loop.index0}}[0x00u]
    },
```

- [ ] **Step 5: Initialise the runtime state**

In `source/Xcp.c`, inside `Xcp_Init`, immediately after the `Xcp_EventQueueInit(...)` call:

```c
            for (idx = 0x00000000u; idx < Xcp_Ptr->general->maxSegment; idx ++) {
                Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[idx].freeze = FALSE;
            }
```

- [ ] **Step 6: Add the test configuration builders**

In `test/parameter.py`, next to the other module-level helpers:

```python
def page(init_segment=0,
         ecu_access='DONT_CARE',
         xcp_read_access='DONT_CARE',
         xcp_write_access='DONT_CARE'):
    return {"init_segment": init_segment,
            "ecu_access": ecu_access,
            "xcp_read_access": xcp_read_access,
            "xcp_write_access": xcp_write_access}


def address_mapping(source_address=0, destination_address=0, length=0):
    return {"source_address": source_address,
            "destination_address": destination_address,
            "length": length}


def segment(name='CAL_SEG',
            address=0x00400000,
            length=0x1000,
            address_extension=0,
            compression_method=0,
            encryption_method=0,
            pages=None,
            address_mappings=None):
    return {"name": name,
            "address": address,
            "length": length,
            "address_extension": address_extension,
            "compression_method": compression_method,
            "encryption_method": encryption_method,
            "pages": list(pages) if pages is not None else [page()],
            "address_mappings": list(address_mappings) if address_mappings is not None else []}
```

Add `segments=(), freeze_supported=False` to the `DefaultConfig.__init__` signature, and emit them in the configuration dict alongside `daqs`:

```python
                "segments": list(segments),
                "paging": {"freeze_supported": freeze_supported},
```

- [ ] **Step 7: Update the shipped configuration**

In `config/xcp.json`, add after the `daqs` array. Note that DD5 was later revised: `SHORT_DOWNLOAD` ships enabled, not off.

```json
      "segments": [
        {
          "name": "CAL_SEG_0",
          "address": 4194304,
          "length": 4096,
          "address_extension": 0,
          "compression_method": 0,
          "encryption_method": 0,
          "pages": [
            {"init_segment": 0, "ecu_access": "DONT_CARE",
             "xcp_read_access": "DONT_CARE", "xcp_write_access": "NOT_ALLOWED"},
            {"init_segment": 0, "ecu_access": "WITHOUT_OTHER",
             "xcp_read_access": "DONT_CARE", "xcp_write_access": "DONT_CARE"}
          ],
          "address_mappings": []
        }
      ],
      "paging": {"freeze_supported": false},
```

and set `"xcp_short_download_api_enable"` to `{"enabled": false, "protected": false}`.

- [ ] **Step 8: Verify the generated code compiles and the suite still passes**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: green — every test from Task 10 still passes and none has started failing. A compile error in the generated `Xcp_Cfg.c` means a struct field and its initialiser are out of order.

Inspect the generated file if anything looks wrong:

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c 'sed -n "/Xcp_SegmentConfig00/,/};/p" build/Xcp_Cfg.c'
```

- [ ] **Step 9: Commit**

```bash
git add config/ interface/Xcp_Types.h script/ source/Xcp.c test/parameter.py
git commit -m "feat: add segment and page configuration model"
```

---

## Task 12: Paging callback interface

Three integrator callbacks, each invoked only after the module has validated every parameter against configuration. `XCP_PAGING_SUPPORTED` guards them so a configuration with no segments requires no implementation.

**Files:**
- Create: `test/stub/Xcp_Paging.h`
- Modify: `interface/Xcp.h`, `script/header_cfg.h.jinja2`, `test/conftest.py`

**Interfaces:**
- Consumes: the segment model from Task 11.
- Produces:
  ```c
  Std_ReturnType Xcp_SetCalPage(uint8 segment, uint8 page, uint8 mode);
  Std_ReturnType Xcp_GetCalPage(uint8 segment, uint8 mode, uint8 *pPage);
  Std_ReturnType Xcp_CopyCalPage(uint8 srcSegment, uint8 srcPage, uint8 dstSegment, uint8 dstPage);
  ```
  and, in `XcpTest`, the mocks `xcp_set_cal_page`, `xcp_get_cal_page`, `xcp_copy_cal_page`, each defaulting to `E_OK`.

- [ ] **Step 1: Create the callback header**

Create `test/stub/Xcp_Paging.h`, mirroring `test/stub/Xcp_SeedKey.h`:

```c
/**
 * @file Xcp_Paging.h
 *
 * @brief calibration page switching callbacks, to be implemented by the integrator.
 */

#ifndef XCP_PAGING_H
#define XCP_PAGING_H

#ifdef __cplusplus
extern "C" {
#endif /* #ifdef __cplusplus */

#ifndef STD_TYPES_H
#include "Std_Types.h"
#endif /* #ifndef STD_TYPES_H */

/**
 * @brief activates a calibration page for the given access mode.
 * @param [in] segment logical data segment number
 * @param [in] page logical data page number
 * @param [in] mode 0x01 = ECU access, 0x02 = XCP access
 * @retval E_OK the page has been activated
 * @retval E_NOT_OK the page cannot be set to the given mode; ERR_MODE_NOT_VALID is returned
 */
extern Std_ReturnType Xcp_SetCalPage(uint8 segment, uint8 page, uint8 mode);

/**
 * @brief reports the calibration page currently active for the given access mode.
 * @param [in] segment logical data segment number
 * @param [in] mode 0x01 = ECU access, 0x02 = XCP access
 * @param [out] pPage receives the logical data page number; untouched when E_NOT_OK is returned
 * @retval E_OK pPage has been written
 * @retval E_NOT_OK no page is active for that mode; ERR_MODE_NOT_VALID is returned
 */
extern Std_ReturnType Xcp_GetCalPage(uint8 segment, uint8 mode, uint8 *pPage);

/**
 * @brief copies one calibration page onto another.
 * @retval E_OK the page has been copied
 * @retval E_NOT_OK the destination cannot be written; ERR_WRITE_PROTECTED is returned
 */
extern Std_ReturnType Xcp_CopyCalPage(uint8 srcSegment, uint8 srcPage, uint8 dstSegment, uint8 dstPage);

#ifdef __cplusplus
}
#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_PAGING_H */
```

- [ ] **Step 2: Include it from the public header**

In `interface/Xcp.h`, after the `#include "Xcp_MemoryAccess.h"` line:

```c
#if (XCP_PAGING_SUPPORTED == STD_ON)

#include "Xcp_Paging.h"

#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
```

- [ ] **Step 3: Emit the guard from the generator**

In `script/header_cfg.h.jinja2`, after the include block:

```jinja
{%- for configuration in configurations %}
{%- if loop.first %}
#ifndef XCP_PAGING_SUPPORTED

#define XCP_PAGING_SUPPORTED ({% if (configuration.segments | default([]))|length > 0 %}STD_ON{% else %}STD_OFF{% endif %})

#endif /* #ifndef XCP_PAGING_SUPPORTED */
{%- endif %}
{%- endfor %}
```

`Xcp_Cfg.h` is generated into the build directory and `Xcp.h` is compiled with it on the include path, so the guard is visible.

- [ ] **Step 4: Add the mocks**

In `test/conftest.py`, in `XcpTest.__init__`, next to `self.xcp_calc_key`:

```python
        self.xcp_set_cal_page = MagicMock()
        self.xcp_get_cal_page = MagicMock()
        self.xcp_copy_cal_page = MagicMock()
```

and next to the other default return values:

```python
        self.xcp_set_cal_page.return_value = self.define('E_OK')
        self.xcp_get_cal_page.return_value = self.define('E_OK')
        self.xcp_copy_cal_page.return_value = self.define('E_OK')
```

The existing `for func in self.code.mocked: self.ffi.def_extern(func)(getattr(self, convert(func)))` loop binds them: `convert('Xcp_SetCalPage')` yields `xcp_set_cal_page`, and likewise for the other two, so the attribute names above must match exactly.

- [ ] **Step 5: Add the not-implemented fallback handler**

`Xcp_Pag.c` calls the three callbacks unconditionally, but their declarations are guarded on
`XCP_PAGING_SUPPORTED`. A configuration with no segments would therefore fail to compile. The
resolution is a single fallback handler that the dispatch table points at whenever a command
is not available, which defect D2 also needs in Task 19.

Append to `source/Xcp.c`, next to the other global function definitions:

```c
uint8 Xcp_CmdNotImplemented(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.4
     * An attempt to execute a not implemented optional command will return ERR_CMD_UNKNOWN and
     * does not have any effect. */
    Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}
```

Add its prototype to `source/Xcp_Internal.h`.

- [ ] **Step 6: Guard the paging translation unit and its dispatch entries**

Wrap the whole body of `source/Xcp_Pag.c` — everything after the include block — in:

```c
#if (XCP_PAGING_SUPPORTED == STD_ON)
/* ... handlers ... */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
```

`Xcp_Pag.c` is empty at this point, so the guard is added now and every later task appends
inside it.

Each of the eight PAG entries in `Xcp_PIDTable` takes the conditional form below. Tasks 13
through 18 refer back to this as "the conditional pattern from Task 12" — apply it as each
handler arrives, and until then leave the entry as it is:

```c
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdPagCopyCalPage, /* COPY_CAL_PAGE 0xE4, optional */
#else
    Xcp_CmdNotImplemented, /* COPY_CAL_PAGE 0xE4, optional */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
```

Because `interface/Xcp.h` guards `Xcp_GetSegmentFreezeState` the same way, a configuration
without segments exposes no paging symbol at all and the integrator implements none of the
three callbacks.

- [ ] **Step 7: Verify the suite still passes**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: unchanged from Task 11 — everything green. An `AttributeError: 'XcpTest' object has no attribute 'xcp_set_cal_page'` means the mock attribute name does not match what `convert()` produces. An implicit-declaration error for `Xcp_SetCalPage` means the guard in Step 6 was not applied.

- [ ] **Step 8: Commit**

```bash
git add test/stub/Xcp_Paging.h interface/Xcp.h script/header_cfg.h.jinja2 test/conftest.py source/
git commit -m "feat: add calibration paging callback interface"
```

---

## Task 13: SET_CAL_PAGE and GET_CAL_PAGE

The two mandatory page-switching commands, plus the §1.4 configuration rule "If SET_CAL_PAGE is implemented, GET_CAL_PAGE is required".

The active page is **not** cached in `Xcp_Rt`: the ECU application may switch pages without XCP's involvement, so `Xcp_GetCalPage` is the authority and a shadow copy would go stale exactly when it matters.

**Files:**
- Modify: `source/Xcp_Pag.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entries `0xEB`, `0xEA`; `Xcp_Init`)
- Test: `test/set_cal_page_test.py`, `test/get_cal_page_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_SetCalPage`, `Xcp_GetCalPage` (Task 12), the segment model (Task 11).
- Produces: `uint8 Xcp_DTOCmdPagSetCalPage(...)`, `uint8 Xcp_DTOCmdPagGetCalPage(...)`, and file-static `Xcp_SegmentIsValid` / `Xcp_PageIsValid` helpers in `Xcp_Pag.c`. Adds to `Xcp_Internal.h`: `#define XCP_CAL_PAGE_MODE_ECU (0x01u)`, `XCP_CAL_PAGE_MODE_XCP (0x02u)`, `XCP_CAL_PAGE_MODE_ALL (0x80u)`.

- [ ] **Step 1: Write the failing tests**

Create `test/set_cal_page_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def paging_handle(segment_count=2, page_count=2):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   segments=[segment(name='S{}'.format(i),
                                                     pages=[page() for _ in range(page_count)])
                                             for i in range(segment_count)]))
    connect(handle)
    return handle


def test_set_cal_page_delegates_to_the_integrator_and_acknowledges():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1"""
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x03, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert handle.xcp_set_cal_page.call_args[0][0:3] == (0x01, 0x01, 0x03)
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_set_cal_page_with_the_all_bit_applies_to_every_segment():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1: ALL ignores the segment number."""
    handle = paging_handle(segment_count=3)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x81, 0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert [c[0][0] for c in handle.xcp_set_cal_page.call_args_list] == [0, 1, 2]
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


@pytest.mark.parametrize('mode, segment, page, expected_error', ((0x01, 0x05, 0x00, 0x28),
                                                                 (0x01, 0x00, 0x07, 0x26),
                                                                 (0x00, 0x00, 0x00, 0x27),
                                                                 (0x80, 0x00, 0x00, 0x27)))
def test_set_cal_page_rejects_invalid_parameters(mode, segment, page, expected_error):
    """ERR_SEGMENT_NOT_VALID 0x28, ERR_PAGE_NOT_VALID 0x26, ERR_MODE_NOT_VALID 0x27."""
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, mode, segment, page)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)


def test_set_cal_page_returns_err_mode_not_valid_when_the_callback_fails():
    handle = paging_handle()
    handle.xcp_set_cal_page.return_value = handle.define('E_NOT_OK')

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEB, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)
```

Create `test/get_cal_page_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .set_cal_page_test import paging_handle


@pytest.mark.parametrize('mode', (0x01, 0x02))
def test_get_cal_page_returns_the_page_reported_by_the_integrator(mode):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2"""
    handle = paging_handle()

    def get_cal_page(_segment, _mode, p_page):
        p_page[0] = 0x01
        return handle.define('E_OK')

    handle.xcp_get_cal_page.side_effect = get_cal_page

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, mode, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4]) == (0xFF, 0x00, 0x00, 0x01)


@pytest.mark.parametrize('mode', (0x00, 0x03, 0x04, 0xFF))
def test_get_cal_page_rejects_any_mode_other_than_ecu_or_xcp(mode):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2: all other values are invalid."""
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, mode, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)


def test_get_cal_page_rejects_an_unknown_segment():
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xEA, 0x01, 0x05)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)


def test_xcp_init_fails_when_set_cal_page_is_enabled_without_get_cal_page():
    """XCP part 2 - Protocol Layer Specification 1.0/1.4: SET_CAL_PAGE requires GET_CAL_PAGE."""
    handle = XcpTest(DefaultConfig(xcp_set_cal_page_api_enable=True,
                                   xcp_get_cal_page_api_enable=False,
                                   segments=[segment(pages=[page()])]))
    handle.det_report_error.assert_called_once_with(ANY, ANY,
                                                    handle.define('XCP_INIT_API_ID'),
                                                    handle.define('XCP_E_INIT_FAILED'))
```

Add `from unittest.mock import ANY` to the imports of `get_cal_page_test.py`.

- [ ] **Step 2: Run them and watch them fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k cal_page" && make all && ctest -V'
```

Expected: FAIL — `0xEB` and `0xEA` dispatch to `Xcp_DTODaqPacket`.

- [ ] **Step 3: Implement the handlers**

Append to `source/Xcp_Pag.c`:

```c
static boolean Xcp_SegmentIsValid(uint8 segment)
{
    return (boolean)((segment < Xcp_Ptr->general->maxSegment) ? TRUE : FALSE);
}

static boolean Xcp_PageIsValid(uint8 segment, uint8 page)
{
    boolean result = FALSE;

    if (Xcp_SegmentIsValid(segment) == TRUE)
    {
        if (page < Xcp_Ptr->config->segment[segment].maxPages)
        {
            result = TRUE;
        }
    }

    return result;
}

uint8 Xcp_DTOCmdPagSetCalPage(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    const uint8 page = pPduInfo->SduDataPtr[0x03u];
    uint8 error = 0x00u;
    uint8_least first;
    uint8_least last;
    uint8_least idx;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1
     * Both flags ECU and XCP may be set simultaneously or separately. A request selecting neither
     * asks for nothing and is rejected. */
    if ((mode & (XCP_CAL_PAGE_MODE_ECU | XCP_CAL_PAGE_MODE_XCP)) == 0x00u)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else if (((mode & XCP_CAL_PAGE_MODE_ALL) == 0x00u) && (Xcp_SegmentIsValid(segment) == FALSE))
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1
         * The ALL flag makes the logical segment number irrelevant; the command applies to all
         * segments. */
        if ((mode & XCP_CAL_PAGE_MODE_ALL) != 0x00u)
        {
            first = 0x00u;
            last = Xcp_Ptr->general->maxSegment;
        }
        else
        {
            first = segment;
            last = (uint8_least)(segment + 0x01u);
        }

        /* Validate every affected segment before switching any of them, so a bad page number
         * cannot leave the slave half-switched. */
        for (idx = first; idx < last; idx++)
        {
            if (Xcp_PageIsValid((uint8)idx, page) == FALSE)
            {
                error = XCP_E_ASAM_PAGE_NOT_VALID;

                break;
            }
        }

        if (error == 0x00u)
        {
            for (idx = first; idx < last; idx++)
            {
                /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1
                 * If the calibration data page cannot be set to the given mode, an
                 * ERR_MODE_NOT_VALID will be returned. The specification defines no rollback, so
                 * segments already switched stay switched. */
                if (Xcp_SetCalPage((uint8)idx, page, mode) != E_OK)
                {
                    error = XCP_E_ASAM_MODE_NOT_VALID;

                    break;
                }
            }
        }
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPagGetCalPage(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    uint8 page = 0x00u;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2
     * Mode may be 0x01 (ECU access) or 0x02 (XCP access). All other values are invalid. */
    if ((mode != XCP_CAL_PAGE_MODE_ECU) && (mode != XCP_CAL_PAGE_MODE_XCP))
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else if (Xcp_GetCalPage(segment, mode, &page) != E_OK)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = page;

        Xcp_FinalizeResPacket(0x04u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add the two mode macros and both handler prototypes to `source/Xcp_Internal.h`, and change the `Xcp_PIDTable` entries using the guarded pattern from Task 12:

```c
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdPagGetCalPage, /* GET_CAL_PAGE 0xEA */
#else
    Xcp_CmdNotImplemented, /* GET_CAL_PAGE 0xEA */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdPagSetCalPage, /* SET_CAL_PAGE 0xEB */
#else
    Xcp_CmdNotImplemented, /* SET_CAL_PAGE 0xEB */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
```

- [ ] **Step 4: Add the configuration consistency check**

In `source/Xcp.c`, in `Xcp_Init`, declare `boolean dependencies_satisfied;` at the top of the function and compute it after `element_size`:

```c
        /* XCP part 2 - Protocol Layer Specification 1.0/1.4
         * If SET_CAL_PAGE is implemented, GET_CAL_PAGE is required.
         * If GET_SEED is implemented, UNLOCK is required. */
        dependencies_satisfied = TRUE;

        if (((pConfig->general->ctoInfo[XCP_PID_CMD_SET_CAL_PAGE] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
            ((pConfig->general->ctoInfo[XCP_PID_CMD_GET_CAL_PAGE] & XCP_CTO_INFO_ENABLED_MASK) == 0x00u))
        {
            dependencies_satisfied = FALSE;
        }

        if (((pConfig->general->ctoInfo[XCP_PID_CMD_GET_SEED] & XCP_CTO_INFO_ENABLED_MASK) != 0x00u) &&
            ((pConfig->general->ctoInfo[XCP_PID_CMD_UNLOCK] & XCP_CTO_INFO_ENABLED_MASK) == 0x00u))
        {
            dependencies_satisfied = FALSE;
        }
```

then extend the existing guard from

```c
        if ((element_size != 0x00u) &&
            ((Xcp_Ptr->general->maxCto % element_size) == 0x00u) && ((Xcp_Ptr->general->maxDto % element_size) == 0x00u))
```

to

```c
        if ((element_size != 0x00u) && (dependencies_satisfied == TRUE) &&
            ((Xcp_Ptr->general->maxCto % element_size) == 0x00u) && ((Xcp_Ptr->general->maxDto % element_size) == 0x00u))
```

- [ ] **Step 5: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k cal_page" && make all && ctest -V'
```

Expected: PASS on all thirteen cases.

- [ ] **Step 6: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/set_cal_page_test.py test/get_cal_page_test.py
git commit -m "feat: implement SET_CAL_PAGE and GET_CAL_PAGE"
```

---

## Task 14: GET_PAG_PROCESSOR_INFO

Answered entirely from the configuration model built in Task 11 — this is the first command that reads it, so it is also the proof that segments reach the runtime.

**Files:**
- Modify: `source/Xcp_Pag.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xE9`)
- Test: `test/get_pag_processor_info_test.py` (create)

**Interfaces:**
- Consumes: `maxSegment` and `pagProperties` (Task 11).
- Produces: `uint8 Xcp_DTOCmdPagGetPagProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/get_pag_processor_info_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('segment_count', (1, 2, 5))
def test_get_pag_processor_info_reports_the_configured_segment_count(segment_count):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1: MAX_SEGMENT."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   segments=[segment(name='S{}'.format(i), pages=[page()])
                                             for i in range(segment_count)]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE9,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[1] == segment_count


@pytest.mark.parametrize('freeze_supported, expected', ((False, 0x00), (True, 0x01)))
def test_get_pag_processor_info_reports_freeze_supported(freeze_supported, expected):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1: PAG_PROPERTIES bit 0."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   freeze_supported=freeze_supported,
                                   segments=[segment(pages=[page()])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE9,)))
    handle.lib.Xcp_MainFunction()

    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[2] == expected
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k pag_processor_info" && make all && ctest -V'
```

Expected: FAIL on all five cases, with a stale response buffer rather than the segment count.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Pag.c`:

```c
uint8 Xcp_DTOCmdPagGetPagProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1
     * MAX_SEGMENT is the total number of segments in the slave device. PAG_PROPERTIES bit 0 is
     * FREEZE_SUPPORTED, indicating that all SEGMENTs can be put in FREEZE mode. */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Ptr->general->maxSegment;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_Ptr->general->pagProperties;

    Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h`, and change the `Xcp_PIDTable` entry at `0xE9` using the guarded pattern from Task 12:

```c
#if (XCP_PAGING_SUPPORTED == STD_ON)
    Xcp_DTOCmdPagGetPagProcessorInfo, /* GET_PAG_PROCESSOR_INFO 0xE9, optional */
#else
    Xcp_CmdNotImplemented, /* GET_PAG_PROCESSOR_INFO 0xE9, optional */
#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k pag_processor_info" && make all && ctest -V'
```

Expected: PASS on all five cases.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/get_pag_processor_info_test.py
git commit -m "feat: implement GET_PAG_PROCESSOR_INFO"
```

---

## Task 15: SET_SEGMENT_MODE, GET_SEGMENT_MODE and the FREEZE accessor

§1.6.3.2.4 says the FREEZE flag "selects the SEGMENT for freezing through STORE_CAL_REQ". The existing store callback `Xcp_StoreCalibrationDataToNonVolatileMemory(uint8 *pStatusCode)` receives no segment information, so without an accessor the flag would be settable and readable but inert. `Xcp_GetSegmentFreezeState` closes that loop without changing an existing integrator signature.

**Files:**
- Modify: `source/Xcp_Pag.c`, `source/Xcp_Internal.h`, `interface/Xcp.h`, `source/Xcp.c` (`Xcp_PIDTable` entries `0xE6`, `0xE5`)
- Test: `test/segment_mode_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_Rt[...].segment[...]` (Task 11), `Xcp_SegmentIsValid` (Task 13).
- Produces: `uint8 Xcp_DTOCmdPagSetSegmentMode(...)`, `uint8 Xcp_DTOCmdPagGetSegmentMode(...)`, and the public `boolean Xcp_GetSegmentFreezeState(uint8 segment);`. Adds `#define XCP_SEGMENT_MODE_FREEZE (0x01u)` to `Xcp_Internal.h`.

- [ ] **Step 1: Write the failing test**

Create `test/segment_mode_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def freeze_handle(freeze_supported=True, segment_count=2):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   freeze_supported=freeze_supported,
                                   segments=[segment(name='S{}'.format(i), pages=[page()])
                                             for i in range(segment_count)]))
    connect(handle)
    return handle


def test_segment_mode_defaults_to_freeze_disabled():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.5"""
    handle = freeze_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE5, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFF, 0x00, 0x00)


def test_set_segment_mode_freeze_is_reported_back_by_get_segment_mode():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.4 and 1.6.3.2.5"""
    handle = freeze_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE6, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE5, 0x00, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFF, 0x00, 0x01)


def test_set_segment_mode_freeze_is_visible_through_the_public_accessor():
    """The FREEZE flag selects the SEGMENT for freezing through STORE_CAL_REQ."""
    handle = freeze_handle()

    assert handle.lib.Xcp_GetSegmentFreezeState(0x01) == 0

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE6, 0x01, 0x01)))
    handle.lib.Xcp_MainFunction()

    assert handle.lib.Xcp_GetSegmentFreezeState(0x01) == 1
    assert handle.lib.Xcp_GetSegmentFreezeState(0x00) == 0
    assert handle.lib.Xcp_GetSegmentFreezeState(0x05) == 0, 'out-of-range segments report FALSE'


def test_set_segment_mode_rejects_freeze_when_it_is_not_supported():
    handle = freeze_handle(freeze_supported=False)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE6, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x27)


@pytest.mark.parametrize('pid', (0xE5, 0xE6))
def test_segment_mode_commands_reject_an_unknown_segment(pid):
    handle = freeze_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x05)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k segment_mode" && make all && ctest -V'
```

Expected: FAIL — `AttributeError` on `Xcp_GetSegmentFreezeState`, and the two PIDs dispatch to `Xcp_DTODaqPacket`.

- [ ] **Step 3: Declare the accessor publicly**

In `interface/Xcp.h`, in the global function declarations section:

```c
#if (XCP_PAGING_SUPPORTED == STD_ON)

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief reports whether a calibration data segment has been selected for freezing.
 * @details The XCP master sets this flag with SET_SEGMENT_MODE. An integrator implementing
 * @ref Xcp_StoreCalibrationDataToNonVolatileMemory queries it per segment to decide what to
 * store.
 * @param [in] segment logical data segment number
 * @return TRUE if FREEZE mode is enabled for that segment, FALSE otherwise or if the segment
 * number is out of range
 */
boolean Xcp_GetSegmentFreezeState(uint8 segment);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
```

- [ ] **Step 4: Implement the handlers and the accessor**

Append to `source/Xcp_Pag.c`:

```c
boolean Xcp_GetSegmentFreezeState(uint8 segment)
{
    boolean result = FALSE;

    if (Xcp_SegmentIsValid(segment) == TRUE)
    {
        result = Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[segment].freeze;
    }

    return result;
}

uint8 Xcp_DTOCmdPagSetSegmentMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEGMENT_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (((mode & XCP_SEGMENT_MODE_FREEZE) != 0x00u) && ((Xcp_Ptr->general->pagProperties & 0x01u) == 0x00u))
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1
         * FREEZE_SUPPORTED indicates whether SEGMENTs can be set to FREEZE mode at all. */
        Xcp_FillErrorPacket(XCP_E_ASAM_MODE_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.4
         * The FREEZE flag selects the SEGMENT for freezing through STORE_CAL_REQ. */
        Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[segment].freeze =
            (boolean)(((mode & XCP_SEGMENT_MODE_FREEZE) != 0x00u) ? TRUE : FALSE);

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPagGetSegmentMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEGMENT_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] =
            (uint8)((Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[segment].freeze == TRUE) ? XCP_SEGMENT_MODE_FREEZE : 0x00u);

        Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add `#define XCP_SEGMENT_MODE_FREEZE (0x01u)` and both prototypes to `source/Xcp_Internal.h`, and change the `Xcp_PIDTable` entries at `0xE5` and `0xE6` using the guarded pattern from Task 12, falling back to `Xcp_CmdNotImplemented`.

`Xcp_Pag.c` must include `Xcp_Rt.h` for `Xcp_Rt`; add the guarded include at the top of the file the same way `Xcp.c` does.

- [ ] **Step 5: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k segment_mode" && make all && ctest -V'
```

Expected: PASS on all seven cases.

- [ ] **Step 6: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ interface/Xcp.h test/segment_mode_test.py
git commit -m "feat: implement SET_SEGMENT_MODE, GET_SEGMENT_MODE and the freeze accessor"
```

---

## Task 16: GET_SEGMENT_INFO

Three modes, all answered from generated configuration. Mode 0 returns the segment's address or length, mode 1 its standard properties, mode 2 one of its address mappings.

§1.6.3.2.2's prose says an unavailable segment returns `ERR_OUT_OF_RANGE`, and §1.7.3.2.3 lists both `ERR_OUT_OF_RANGE` and `ERR_SEGMENT_NOT_VALID` for this command. `ERR_SEGMENT_NOT_VALID` is used for a bad segment number so that every PAG command behaves the same way, and `ERR_OUT_OF_RANGE` for a bad mode, `SEGMENT_INFO` or `MAPPING_INDEX`.

**Files:**
- Modify: `source/Xcp_Pag.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xE8`)
- Test: `test/get_segment_info_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_SegmentIsValid` (Task 13), `Xcp_CopyFromU32WithOrder` (Task 3).
- Produces: `uint8 Xcp_DTOCmdPagGetSegmentInfo(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/get_segment_info_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


def info_handle(byte_order='LITTLE_ENDIAN'):
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   byte_order=byte_order,
                                   max_cto=8,
                                   segments=[segment(name='S0',
                                                     address=0x00400000,
                                                     length=0x1000,
                                                     address_extension=0x02,
                                                     compression_method=0x03,
                                                     encryption_method=0x04,
                                                     pages=[page(), page(), page()],
                                                     address_mappings=[
                                                         address_mapping(0x11111111, 0x22222222, 0x33333333),
                                                         address_mapping(0x44444444, 0x55555555, 0x66666666)])]))
    connect(handle)
    return handle


@pytest.mark.parametrize('segment_info, expected', ((0x00, 0x00400000), (0x01, 0x00001000)))
@pytest.mark.parametrize('byte_order', byte_orders)
def test_get_segment_info_mode_0_returns_address_and_length(segment_info, expected, byte_order):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 0."""
    handle = info_handle(byte_order)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x00, 0x00, segment_info, 0x00)))
    handle.lib.Xcp_MainFunction()

    response = handle.can_if_transmit.call_args[0][1].SduDataPtr
    assert response[0] == 0xFF
    assert u32_from_array(bytes(response[4:8]), byte_order) == expected


def test_get_segment_info_mode_1_returns_standard_information():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 1."""
    handle = info_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x01, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:6]) == (0xFF, 0x03, 0x02, 0x02, 0x03, 0x04)


@pytest.mark.parametrize('mapping_index, segment_info, expected', ((0x00, 0x00, 0x11111111),
                                                                   (0x00, 0x01, 0x22222222),
                                                                   (0x00, 0x02, 0x33333333),
                                                                   (0x01, 0x00, 0x44444444),
                                                                   (0x01, 0x02, 0x66666666)))
def test_get_segment_info_mode_2_returns_mapping_information(mapping_index, segment_info, expected):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2, mode 2."""
    handle = info_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE8, 0x02, 0x00, segment_info, mapping_index)))
    handle.lib.Xcp_MainFunction()

    response = handle.can_if_transmit.call_args[0][1].SduDataPtr
    assert response[0] == 0xFF
    assert u32_from_array(bytes(response[4:8]), 'LITTLE_ENDIAN') == expected


@pytest.mark.parametrize('mode, segment, segment_info, mapping_index, expected_error',
                         ((0x00, 0x05, 0x00, 0x00, 0x28),
                          (0x03, 0x00, 0x00, 0x00, 0x22),
                          (0x00, 0x00, 0x02, 0x00, 0x22),
                          (0x02, 0x00, 0x03, 0x00, 0x22),
                          (0x02, 0x00, 0x00, 0x02, 0x22)))
def test_get_segment_info_rejects_invalid_parameters(mode, segment, segment_info, mapping_index, expected_error):
    handle = info_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001,
                                     handle.get_pdu_info((0xE8, mode, segment, segment_info, mapping_index)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k get_segment_info" && make all && ctest -V'
```

Expected: FAIL — `0xE8` dispatches to `Xcp_DTODaqPacket`.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Pag.c`:

```c
uint8 Xcp_DTOCmdPagGetSegmentInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    const uint8 segment_info = pPduInfo->SduDataPtr[0x03u];
    const uint8 mapping_index = pPduInfo->SduDataPtr[0x04u];
    const Xcp_SegmentType *p_segment;
    uint32 value = 0x00000000u;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else
    {
        p_segment = &Xcp_Ptr->config->segment[segment];

        if (mode == 0x00u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2
             * Mode 0: SEGMENT_INFO selects 0 = address, 1 = length of this SEGMENT. */
            if (segment_info == 0x00u)
            {
                value = p_segment->address;
            }
            else if (segment_info == 0x01u)
            {
                value = p_segment->length;
            }
            else
            {
                error = XCP_E_ASAM_OUT_OF_RANGE;
            }
        }
        else if (mode == 0x01u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2
             * Mode 1: SEGMENT_INFO and MAPPING_INDEX are don't care. */
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = p_segment->maxPages;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = p_segment->addressExtension;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = p_segment->maxMapping;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = p_segment->compressionMethod;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = p_segment->encryptionMethod;

            Xcp_FinalizeResPacket(0x06u, &Xcp_Internal.cto_response.pdu_info);
        }
        else if (mode == 0x02u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2
             * Mode 2: SEGMENT_INFO selects 0 = source address, 1 = destination address,
             * 2 = length, for the range referenced by MAPPING_INDEX. */
            if (mapping_index >= p_segment->maxMapping)
            {
                error = XCP_E_ASAM_OUT_OF_RANGE;
            }
            else if (segment_info == 0x00u)
            {
                value = p_segment->addressMapping[mapping_index].sourceAddress;
            }
            else if (segment_info == 0x01u)
            {
                value = p_segment->addressMapping[mapping_index].destinationAddress;
            }
            else if (segment_info == 0x02u)
            {
                value = p_segment->addressMapping[mapping_index].length;
            }
            else
            {
                error = XCP_E_ASAM_OUT_OF_RANGE;
            }
        }
        else
        {
            error = XCP_E_ASAM_OUT_OF_RANGE;
        }
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (mode != 0x01u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u; /* reserved */

        Xcp_CopyFromU32WithOrder(value,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* Mode 1 has already assembled its response. */
    }

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h` and change the `Xcp_PIDTable` entry at `0xE8` to `Xcp_DTOCmdPagGetSegmentInfo`, using the guarded pattern from Task 12, falling back to `Xcp_CmdNotImplemented`.

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k get_segment_info" && make all && ctest -V'
```

Expected: PASS on all fifteen cases.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/get_segment_info_test.py
git commit -m "feat: implement GET_SEGMENT_INFO"
```

---

## Task 17: GET_PAGE_INFO

Returns `PAGE_PROPERTIES` and `INIT_SEGMENT` from configuration.

§1.6.3.2.3's prose says an unavailable page returns `ERR_OUT_OF_RANGE`, but §1.7.3.2.3 lists `ERR_PAGE_NOT_VALID` and `ERR_SEGMENT_NOT_VALID` for this command and does **not** list `ERR_OUT_OF_RANGE`. The matrix wins, which also keeps this command consistent with every other PAG command.

**Files:**
- Modify: `source/Xcp_Pag.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xE7`)
- Test: `test/get_page_info_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_SegmentIsValid`, `Xcp_PageIsValid` (Task 13).
- Produces: `uint8 Xcp_DTOCmdPagGetPageInfo(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/get_page_info_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('ecu, xcp_read, xcp_write, expected', (
        ('NOT_ALLOWED', 'NOT_ALLOWED', 'NOT_ALLOWED', 0x00),
        ('DONT_CARE', 'NOT_ALLOWED', 'NOT_ALLOWED', 0x03),
        ('NOT_ALLOWED', 'DONT_CARE', 'NOT_ALLOWED', 0x0C),
        ('NOT_ALLOWED', 'NOT_ALLOWED', 'DONT_CARE', 0x30),
        ('WITHOUT_OTHER', 'WITH_OTHER', 'WITHOUT_OTHER', 0x19),
        ('DONT_CARE', 'DONT_CARE', 'DONT_CARE', 0x3F)))
def test_get_page_info_packs_the_page_properties(ecu, xcp_read, xcp_write, expected):
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.3: bits 1:0, 3:2 and 5:4."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   segments=[segment(pages=[page(init_segment=0x07,
                                                                 ecu_access=ecu,
                                                                 xcp_read_access=xcp_read,
                                                                 xcp_write_access=xcp_write)])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE7, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:3]) == (0xFF, expected, 0x07)


@pytest.mark.parametrize('segment_number, page_number, expected_error', ((0x05, 0x00, 0x28),
                                                                         (0x00, 0x09, 0x26)))
def test_get_page_info_rejects_invalid_parameters(segment_number, page_number, expected_error):
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3 lists ERR_SEGMENT_NOT_VALID
    and ERR_PAGE_NOT_VALID for this command, not ERR_OUT_OF_RANGE."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   segments=[segment(pages=[page(), page()])]))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE7, 0x00, segment_number, page_number)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k get_page_info" && make all && ctest -V'
```

Expected: FAIL — `0xE7` dispatches to `Xcp_DTODaqPacket`.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Pag.c`:

```c
uint8 Xcp_DTOCmdPagGetPageInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    const uint8 page = pPduInfo->SduDataPtr[0x03u];

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEGMENT_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (Xcp_PageIsValid(segment, page) == FALSE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_PAGE_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.3
         * PAGE 0 of the INIT_SEGMENT of a PAGE contains the initial data for this PAGE. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] =
            Xcp_Ptr->config->segment[segment].page[page].pageProperties;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] =
            Xcp_Ptr->config->segment[segment].page[page].initSegment;

        Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h` and change the `Xcp_PIDTable` entry at `0xE7` to `Xcp_DTOCmdPagGetPageInfo`, using the guarded pattern from Task 12, falling back to `Xcp_CmdNotImplemented`.

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k get_page_info" && make all && ctest -V'
```

Expected: PASS on all eight cases. A failure on the `WITHOUT_OTHER`/`WITH_OTHER`/`WITHOUT_OTHER` case returning `0x16` instead of `0x19` means the generator packed the enum values into the wrong bit pairs.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/get_page_info_test.py
git commit -m "feat: implement GET_PAGE_INFO"
```

---

## Task 18: COPY_CAL_PAGE

Validates four parameters against configuration, then delegates. §1.6.3.2.6 mandates `ERR_WRITE_PROTECTED` when the destination cannot be written, even though §1.7.3.2.3 omits that code for this command — the prose describes a concrete condition the slave must report and no other code fits. `Xcp_CTOErrorMatrix` needs no change, because it governs generic pre-checks only.

**Files:**
- Modify: `source/Xcp_Pag.c`, `source/Xcp_Internal.h`, `source/Xcp.c` (`Xcp_PIDTable` entry `0xE4`)
- Test: `test/copy_cal_page_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_CopyCalPage` (Task 12), `Xcp_SegmentIsValid`, `Xcp_PageIsValid` (Task 13).
- Produces: `uint8 Xcp_DTOCmdPagCopyCalPage(boolean *responseExpected, const PduInfoType *pPduInfo);`

- [ ] **Step 1: Write the failing test**

Create `test/copy_cal_page_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .set_cal_page_test import paging_handle


def test_copy_cal_page_delegates_to_the_integrator_and_acknowledges():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.6"""
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x01, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert handle.xcp_copy_cal_page.call_args[0][0:4] == (0x00, 0x01, 0x01, 0x00)
    assert handle.can_if_transmit.call_args[0][1].SduDataPtr[0] == 0xFF


def test_copy_cal_page_returns_err_write_protected_when_the_callback_fails():
    """XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.6: e.g. the destination is flash."""
    handle = paging_handle()
    handle.xcp_copy_cal_page.return_value = handle.define('E_NOT_OK')

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x00, 0x01, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x23)


@pytest.mark.parametrize('src_segment, src_page, dst_segment, dst_page, expected_error',
                         ((0x05, 0x00, 0x00, 0x00, 0x28),
                          (0x00, 0x00, 0x05, 0x00, 0x28),
                          (0x00, 0x09, 0x00, 0x00, 0x26),
                          (0x00, 0x00, 0x00, 0x09, 0x26)))
def test_copy_cal_page_rejects_invalid_parameters(src_segment, src_page, dst_segment, dst_page, expected_error):
    handle = paging_handle()

    handle.lib.Xcp_CanIfRxIndication(
        0x0001, handle.get_pdu_info((0xE4, src_segment, src_page, dst_segment, dst_page)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, expected_error)
    assert handle.xcp_copy_cal_page.call_count == 0
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k copy_cal_page" && make all && ctest -V'
```

Expected: FAIL — `0xE4` dispatches to `Xcp_DTODaqPacket`.

- [ ] **Step 3: Implement the handler**

Append to `source/Xcp_Pag.c`:

```c
uint8 Xcp_DTOCmdPagCopyCalPage(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 src_segment = pPduInfo->SduDataPtr[0x01u];
    const uint8 src_page = pPduInfo->SduDataPtr[0x02u];
    const uint8 dst_segment = pPduInfo->SduDataPtr[0x03u];
    const uint8 dst_page = pPduInfo->SduDataPtr[0x04u];
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if ((Xcp_SegmentIsValid(src_segment) == FALSE) || (Xcp_SegmentIsValid(dst_segment) == FALSE))
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else if ((Xcp_PageIsValid(src_segment, src_page) == FALSE) ||
             (Xcp_PageIsValid(dst_segment, dst_page) == FALSE))
    {
        error = XCP_E_ASAM_PAGE_NOT_VALID;
    }
    else if (Xcp_CopyCalPage(src_segment, src_page, dst_segment, dst_page) != E_OK)
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.6
         * If calibration data page cannot be copied to the given destination, e.g. because the
         * location of destination is a flash segment, an ERR_WRITE_PROTECTED will be returned. */
        error = XCP_E_ASAM_WRITE_PROTECTED;
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
```

Add the prototype to `source/Xcp_Internal.h` and change the `Xcp_PIDTable` entry at `0xE4` to `Xcp_DTOCmdPagCopyCalPage`, using the guarded pattern from Task 12, falling back to `Xcp_CmdNotImplemented`.

- [ ] **Step 4: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k copy_cal_page" && make all && ctest -V'
```

Expected: PASS on all six cases.

- [ ] **Step 5: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add source/ test/copy_cal_page_test.py
git commit -m "feat: implement COPY_CAL_PAGE"
```

---

## Task 19: Make the optional commands configurable and purge the DAQ fallback (defects D2 and D7)

Two related problems close here.

The generator hard-codes `enable = 1` for `MODIFY_BITS`, `DOWNLOAD_NEXT` and the six optional PAG commands, so no configuration can turn them off. And `Xcp_PIDTable` still routes the PGM range and the undefined range to `Xcp_DTODaqPacket`, which answers positively with a stale buffer — §1.4 requires `ERR_CMD_UNKNOWN`, and §1.1.5.1 shows there is no DAQ identifier range in the master-to-slave direction at all.

**Files:**
- Modify: `config/xcp.schema.json`, `config/xcp.json`, `script/source_cfg.c.jinja2`, `test/parameter.py`, `source/Xcp.c`
- Test: `test/cmd_unknown_test.py` (create)

**Interfaces:**
- Consumes: `Xcp_CmdNotImplemented` (Task 12).
- Produces: eight new API flags — `xcp_download_next_api_enable`, `xcp_modify_bits_api_enable`, `xcp_get_pag_processor_info_api_enable`, `xcp_get_segment_info_api_enable`, `xcp_get_page_info_api_enable`, `xcp_set_segment_mode_api_enable`, `xcp_get_segment_mode_api_enable`, `xcp_copy_cal_page_api_enable` — each with the existing `{enabled, protected}` shape and each defaulting to `True` in `DefaultConfig`.

- [ ] **Step 1: Write the failing test**

Create `test/cmd_unknown_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

from .parameter import *
from .conftest import XcpTest
from .download_test import connect


@pytest.mark.parametrize('pid', tuple(range(0xC0, 0xD3)))
def test_unimplemented_commands_return_err_cmd_unknown(pid):
    """XCP part 2 - Protocol Layer Specification 1.0/1.4: an attempt to execute a not implemented
    optional command will return ERR_CMD_UNKNOWN and does not have any effect.
    XCP part 2 - Protocol Layer Specification 1.0/1.1.5.1: 0xC0..0xFF are all CMD identifiers;
    there is no DAQ identifier range from master to slave."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)


@pytest.mark.parametrize('pid, flag', ((0xEF, 'xcp_download_next_api_enable'),
                                       (0xEC, 'xcp_modify_bits_api_enable'),
                                       (0xE9, 'xcp_get_pag_processor_info_api_enable'),
                                       (0xE8, 'xcp_get_segment_info_api_enable'),
                                       (0xE7, 'xcp_get_page_info_api_enable'),
                                       (0xE6, 'xcp_set_segment_mode_api_enable'),
                                       (0xE5, 'xcp_get_segment_mode_api_enable'),
                                       (0xE4, 'xcp_copy_cal_page_api_enable')))
def test_disabled_optional_commands_return_err_cmd_unknown(pid, flag):
    """XCP part 2 - Protocol Layer Specification 1.0/1.4"""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                   max_cto=8,
                                   segments=[segment(pages=[page()])],
                                   **{flag: False}))
    connect(handle)

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((pid, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()

    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)
```

- [ ] **Step 2: Run it and watch it fail**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k cmd_unknown" && make all && ctest -V'
```

Expected: FAIL — the `0xC0..0xD2` cases get a positive response from `Xcp_DTODaqPacket`, and the second test raises `TypeError` because `DefaultConfig` has no such keyword.

- [ ] **Step 3: Add the eight API flags**

In `config/xcp.schema.json`, add to the `apis` properties, each as `{"$ref": "#/definitions/api_activation_information"}`:

`xcp_download_next_api_enable`, `xcp_modify_bits_api_enable`, `xcp_get_pag_processor_info_api_enable`, `xcp_get_segment_info_api_enable`, `xcp_get_page_info_api_enable`, `xcp_set_segment_mode_api_enable`, `xcp_get_segment_mode_api_enable`, `xcp_copy_cal_page_api_enable`.

In `test/parameter.py`, add each as a `True`-defaulted keyword argument of `DefaultConfig.__init__` and emit it in the `apis` dict in the existing form:

```python
                    "xcp_download_next_api_enable": {"enabled": xcp_download_next_api_enable, "protected": False},
```

In `config/xcp.json`, add all eight with `{"enabled": true, "protected": false}`.

- [ ] **Step 4: Gate the enable bits in the generator**

In `script/source_cfg.c.jinja2`, replace the hard-coded `(0x01u << 0x07u) /* enable */` of each of the eight commands with the conditional form already used by the others. For example the `COPY_CAL_PAGE` line becomes:

```jinja
        ({% if configuration.apis.xcp_copy_cal_page_api_enable.enabled %}0x01u{% else %}0x00u{% endif %} << 0x07u) /* enable */ | (0x01u << 0x06u) /* is CTO */ | ({% if configuration.apis.xcp_copy_cal_page_api_enable.protected %}0x01u{% else %}0x00u{% endif %} << 0x05u) /* protected through seed and key */ | 0x05u, /* COPY_CAL_PAGE 0xE4, optional */
```

Do the same for `GET_SEGMENT_MODE 0xE5` (min size `0x03u`), `SET_SEGMENT_MODE 0xE6` (`0x03u`), `GET_PAGE_INFO 0xE7` (`0x04u`), `GET_SEGMENT_INFO 0xE8` (`0x05u`), `GET_PAG_PROCESSOR_INFO 0xE9` (`0x01u`), `MODIFY_BITS 0xEC` (`0x06u`) and `DOWNLOAD_NEXT 0xEF` (`0x04u`), keeping each existing minimum-size nibble unchanged.

**Do not** touch `CONNECT`'s resource mask computation. §1.6.1.1.1 fixes the `CAL/PAG` bit to DOWNLOAD, DOWNLOAD_MAX, SHORT_DOWNLOAD, SET_CAL_PAGE and GET_CAL_PAGE; `test_connect_sets_the_resource_cal_pag_bit_according_to_enabled_apis` is already correct and must keep passing unchanged.

- [ ] **Step 5: Purge the DAQ fallback from the command range**

In `source/Xcp.c`, replace every remaining `Xcp_DTODaqPacket` entry in `Xcp_PIDTable` at indices `0xC0` through `0xD2` with `Xcp_CmdNotImplemented`, preserving the trailing comments, for example:

```c
    Xcp_CmdNotImplemented, /* 0xC0 */
    /* ... */
    Xcp_CmdNotImplemented, /* PROGRAM_VERIFY 0xC8, optional */
    /* ... */
    Xcp_CmdNotImplemented, /* PROGRAM_START 0xD2 */
```

Verify no `Xcp_DTODaqPacket` remains in the table:

```bash
awk '/Xcp_PIDTable/,/^};/' source/Xcp.c | grep -c Xcp_DTODaqPacket
```

Expected: `0`. The `0x00..0xBF` entries stay `Xcp_DTODaqStimPacket` — per §1.1.5.1 that range is the STIM ODT identifier space and is correct.

- [ ] **Step 6: Run the tests and watch them pass**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k cmd_unknown or connect" && make all && ctest -V'
```

Expected: PASS on all twenty-seven cases, and every `connect` test still green.

- [ ] **Step 7: Run the whole suite and commit**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
git add config/ script/ source/ test/parameter.py test/cmd_unknown_test.py
git commit -m "fix: return ERR_CMD_UNKNOWN for unimplemented and disabled commands"
```

---

## Task 20: Error matrix coverage and documentation

The per-command tests cover behaviour; this task covers the §1.7.3.2.2 and §1.7.3.2.3 matrices systematically, in the file that already does that job. Both matrices are fully tabulated in the specification, so this is transcription rather than design.

**Files:**
- Modify: `test/asam_error_matrix_test.py`, `README.md`
- Test: the same file

**Interfaces:**
- Consumes: every handler from Tasks 6–18.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add the error-handling classes**

In `test/asam_error_matrix_test.py`, following the shape of the existing `TestDownloadErrorHandling`, add one class per command: `TestDownloadNextErrorHandling`, `TestDownloadMaxErrorHandling`, `TestShortDownloadErrorHandling`, `TestModifyBitsErrorHandling`, `TestSetCalPageErrorHandling`, `TestGetCalPageErrorHandling`, `TestGetPagProcessorInfoErrorHandling`, `TestGetSegmentInfoErrorHandling`, `TestGetPageInfoErrorHandling`, `TestSetSegmentModeErrorHandling`, `TestGetSegmentModeErrorHandling`, `TestCopyCalPageErrorHandling`.

Each class asserts exactly the rows §1.7.3.2.2 or §1.7.3.2.3 lists for that command, and nothing else. Use this as the template, substituting the command's PID, its minimum request length, and its row:

```python
class TestCopyCalPageErrorHandling:
    """XCP part 2 - Protocol Layer Specification 1.0/1.7.3.2.3"""

    def test_returns_err_cmd_unknown_if_the_command_is_disabled(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       xcp_copy_cal_page_api_enable=False,
                                       segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x20)

    def test_returns_err_cmd_syntax_if_the_request_is_too_short(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x21)

    def test_returns_err_segment_not_valid_for_an_unknown_segment(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x05, 0x00, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x28)

    def test_returns_err_page_not_valid_for_an_unknown_page(self):
        handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001,
                                       segments=[segment(pages=[page()])]))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))
        handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xE4, 0x00, 0x09, 0x00, 0x00)))
        handle.lib.Xcp_MainFunction()
        assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:2]) == (0xFE, 0x26)
```

The rows to transcribe, from the specification:

| Command | Errors listed |
|:--|:--|
| `DOWNLOAD_NEXT` 0xEF | CMD_UNKNOWN, CMD_SYNTAX, OUT_OF_RANGE, ACCESS_DENIED, ACCESS_LOCKED, WRITE_PROTECTED, MEMORY_OVERFLOW, SEQUENCE |
| `DOWNLOAD_MAX` 0xEE | CMD_UNKNOWN, CMD_SYNTAX, OUT_OF_RANGE, ACCESS_DENIED, ACCESS_LOCKED, WRITE_PROTECTED, MEMORY_OVERFLOW |
| `SHORT_DOWNLOAD` 0xED | as `DOWNLOAD_MAX` |
| `MODIFY_BITS` 0xEC | as `DOWNLOAD_MAX` |
| `SET_CAL_PAGE` 0xEB | CMD_SYNTAX, PAGE_NOT_VALID, MODE_NOT_VALID, SEGMENT_NOT_VALID (no CMD_UNKNOWN — mandatory) |
| `GET_CAL_PAGE` 0xEA | as `SET_CAL_PAGE` |
| `GET_PAG_PROCESSOR_INFO` 0xE9 | CMD_UNKNOWN, CMD_SYNTAX |
| `GET_SEGMENT_INFO` 0xE8 | CMD_UNKNOWN, CMD_SYNTAX, OUT_OF_RANGE, SEGMENT_NOT_VALID |
| `GET_PAGE_INFO` 0xE7 | CMD_UNKNOWN, CMD_SYNTAX, PAGE_NOT_VALID, SEGMENT_NOT_VALID |
| `SET_SEGMENT_MODE` 0xE6 | CMD_UNKNOWN, CMD_SYNTAX, MODE_NOT_VALID, SEGMENT_NOT_VALID |
| `GET_SEGMENT_MODE` 0xE5 | CMD_UNKNOWN, CMD_SYNTAX, SEGMENT_NOT_VALID |
| `COPY_CAL_PAGE` 0xE4 | CMD_UNKNOWN, CMD_SYNTAX, PAGE_NOT_VALID, SEGMENT_NOT_VALID |

Only write a case for an error the handler can actually produce. `ACCESS_DENIED`, `ACCESS_LOCKED`, `WRITE_PROTECTED` and `MEMORY_OVERFLOW` depend on memory-map knowledge the module does not have, so mark those `@pytest.mark.skip(reason='the memory mapping must be known in order to check if the provided address is correct...')` exactly as the existing `TestUploadErrorHandling` does. Record every skip added, because the plan's acceptance criterion tracks the skip count.

- [ ] **Step 2: Run the error matrix tests**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev sh -c \
  'cd build && cmake .. -DXCP_PYTEST_ARGS="-k ErrorHandling" && make all && ctest -V'
```

Expected: PASS, with the newly added skips reported. Any failure here is a genuine conformance gap in the handler, not a test bug — fix the handler.

- [ ] **Step 3: Update the documentation**

In `README.md`:

- Add a **Calibration and page switching** section documenting the `segments` array and the `paging` object of the configuration file, the three `Xcp_Paging.h` callbacks, and `Xcp_GetSegmentFreezeState` with the note that an integrator's `Xcp_StoreCalibrationDataToNonVolatileMemory` should query it per segment.
- Record the two resolved specification divergences: `GET_PAGE_INFO` returns `ERR_SEGMENT_NOT_VALID`/`ERR_PAGE_NOT_VALID` per §1.7.3.2.3 rather than the `ERR_OUT_OF_RANGE` of the §1.6.3.2.3 prose; `COPY_CAL_PAGE` returns `ERR_WRITE_PROTECTED` per the §1.6.3.2.6 prose although §1.7.3.2.3 omits it.
- Record that `DOWNLOAD_MAX` and `SHORT_DOWNLOAD` return `ERR_SEQUENCE` when they arrive inside a block transfer, a case for which the specification prescribes no code.
- Note under **Limitations** that `SHORT_DOWNLOAD` carries no data when `MAX_CTO = 8`, per §1.6.2.2.3. It ships enabled; see the revised DD5.
- Note that `DOWNLOAD` block transfer follows `MASTER_BLOCK_MODE` and `MAX_BS`, while `UPLOAD` follows `SLAVE_BLOCK_MODE`.
- Remove from the **TODO** list any item this work closes.

- [ ] **Step 4: Run the whole suite one last time**

```bash
docker run --rm -v "$PWD":/usr/project -w /usr/project xcp-dev ./test.sh
```

Expected: green. Compare against `/tmp/xcp-baseline.txt` from Task 1 — the passed count must have grown substantially and no previously passing test may have started failing or skipping.

- [ ] **Step 5: Commit**

```bash
git add test/asam_error_matrix_test.py README.md
git commit -m "test: cover the CAL and PAG error matrices, document paging configuration"
```

---

## Acceptance

Verify each of these before declaring the plan complete.

1. `./test.sh` runs green, and the pre-existing 13 skips are all still present.
2. All thirteen commands behave per §1.6.2 and §1.6.3, including error codes.
3. A command whose `*_api_enable` is false returns `ERR_CMD_UNKNOWN`.
4. `awk '/Xcp_PIDTable/,/^};/' source/Xcp.c | grep -c Xcp_DTODaqPacket` prints `0`.
5. `source/Xcp.c` contains no command handler bodies — only initialisation, scheduling, the three `Xcp_CanIf*` callbacks and the three dispatch tables.
6. `ls build/*.gcov` lists a file per source unit, and `.github/workflows/test.yml` uploads all of them.
7. `README.md` documents the `segments` block, the three callbacks and `Xcp_GetSegmentFreezeState`.

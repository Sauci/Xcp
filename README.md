| branch                                               | build status                                                                                                                                         | coverage                                                                                                                     |
|:-----------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| [master](https://github.com/Sauci/Xcp/tree/master)   | [![test](https://github.com/Sauci/Xcp/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/Sauci/Xcp/actions/workflows/test.yml)  | [![codecov](https://codecov.io/gh/Sauci/Xcp/branch/master/graph/badge.svg)](https://codecov.io/gh/Sauci/Xcp/branch/master)   |
| [develop](https://github.com/Sauci/Xcp/tree/develop) | [![test](https://github.com/Sauci/Xcp/actions/workflows/test.yml/badge.svg?branch=develop)](https://github.com/Sauci/Xcp/actions/workflows/test.yml) | [![codecov](https://codecov.io/gh/Sauci/Xcp/branch/develop/graph/badge.svg)](https://codecov.io/gh/Sauci/Xcp/branch/develop) |

# Configure/compile-time definitions
The following definitions might be set by the user, depending on the needs.

| definition                    | values                           | default                    | description                                                                                                                                                                      |
|:------------------------------|:---------------------------------|:---------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```AUTOSAR_STD_HEADER_PATH``` | ```-```                          | ```Xcp/test/stub/common``` | specifies the directory containing **AUTOSAR** standard headers ComStack_Types.h and Std_Types.h (used when integrating this module into another project)                         |
| ```XCP_CONFIG_FILEPATH```     | ```-```                          | ```Xcp/config/xcp.json```  | specifies which json configuration file should be used to generate the auto-generated code                                                                                       |
| ```XCP_ENABLE_TEST```         | ```ON```/```OFF```               | ```OFF```                  | enables/disables tests.                                                                                                                                                          |
| ```ENABLE_DET```              | ```ON```/```OFF```               | ```ON```                   | enables/disables development error detections (see AUTOSAR [DET](https://www.autosar.org/fileadmin/user_upload/standards/classic/4-3/AUTOSAR_SWS_DefaultErrorTracer.pdf) module) |
| ```ENABLE_DOC_GEN```          | ```ON```/```OFF```               | ```OFF```                  | enables/disables generation of [Doxygen](http://www.doxygen.nl/) documentation                                                                                                   |
| ```ENABLE_PC_LINT```          | ```ON```/```OFF```               | ```OFF```                  | enables/disables generation of targets related to static code analysis (should be disabled if [PC-Lint](https://www.gimpel.com) software is not available)                       |
| ```MISRA_C_VERSION```         | ```1998```/```2004```/```2012``` | ```2012```                 | specifies which version of **MISRA** should be used when performing static code analysis (only used if ```ENABLE_PC_LINT``` is set)                                              |
| ```XCP_SUPPRESS_TX_SUPPORT``` | ```ON / OFF```                   | ```ON```                   | enables/disables transmission functionality of the XCP module                                                                                                                    | 
| ```XCP_PAGING_SUPPORTED```    | ```ON```/```OFF```               | derived                    | enables/disables the **PAG** command group. Normally left alone: the default follows whether any configuration in ```XCP_CONFIG_FILEPATH``` declares a segment. An explicit ```-D``` overrides it and survives reconfiguring. Configure from a clean build directory after upgrading: a cache entry written before this became an option holds ```STD_OFF```, which now reads as ON |

To use this feature, simply add ```-D<definition>=<value>``` when configuring the build with CMake.

# Module configuration
A large part of this module consists of auto-generated code. It takes a *JSON* file as input (the path of this file is
specified through the `XCP_CONFIG_FILEPATH` CMake variable, defaulting to [this](config/xcp.json) file), and generates 
the *Xcp_Cfg.c* and *Xcp_Cfg.h* files. The content of this configuration file is specified with the *JSON* schema
available [here](config/xcp.schema.json). Most recent IDEs provide auto-completion of the configuration 
file based on its schema, so using it is highly recommended.

# Implementation details
This section gives a few implementation details for the places where the specification is unclear or ambiguous, to
help the user configure the communication parameters correctly on the master side.

## Seed lifetime
Whenever the seed is requested by the master through the `GET_SEED` command, a new seed is requested by the XCP stack 
through the `Xcp_GetSeed` function. The reason is that otherwise the master could calculate a key for a single seed and 
reuse it forever, which would weaken the resource protection.

Whenever the master issues an `UNLOCK` command, the slave discards the seed as well, whether or not the command 
succeeded. This implies a new `GET_SEED` request for each `UNLOCK` command.

The `Xcp_GetSeed` function implementation is left to the stack user. The target on which the stack is integrated could
provide some random value generator, thus this is target-specific. The function's prototype is defined 
[here](./test/stub/Xcp_SeedKey.h).

## Key lifetime
Whenever an `UNLOCK` command is issued by the master, the key is calculated by the slave using the last seed value
requested by the master. Whether or not the keys match, the key is discarded after the command following the `UNLOCK`
sequence has been executed.

If the master issues an `UNLOCK` command without calling `GET_SEED` first, the stack responds with an error packet
identifier and the code `ERR_SEQUENCE`.

The implementation of the function responsible for key calculation, `Xcp_CalcKey` is left to the user. This is necessary,
because the function must be shared between the master and the slave.

## Calibration page switching
The **CAL** commands (`DOWNLOAD`, `DOWNLOAD_NEXT`, `DOWNLOAD_MAX`, `SHORT_DOWNLOAD` and `MODIFY_BITS`) need no
configuration beyond the memory access functions. The **PAG** commands do, because the stack does not itself know what a
page is: a *SEGMENT* is a region of calibration memory, and its *PAGES* are the interchangeable copies of that region.
Declaring at least one segment in the *JSON* configuration is what enables the group. The generator then defines
`XCP_PAGING_SUPPORTED` as `STD_ON`, `interface/Xcp.h` pulls in the paging callbacks, and the eight **PAG** commands are
compiled in. With no segment declared they are compiled out, and their dispatch entries answer `ERR_CMD_UNKNOWN`,
which is also what an individually disabled command answers.

Switching a page is delegated to the integrator through three functions, whose prototypes are defined
[here](./test/stub/Xcp_Paging.h):

| function            | called by                     | purpose                                                                    |
|:--------------------|:------------------------------|:---------------------------------------------------------------------------|
| ```Xcp_SetCalPage``` | `SET_CAL_PAGE`                | activate a page of a segment for ECU access, XCP access, or both           |
| ```Xcp_GetCalPage``` | `GET_CAL_PAGE`                | report which page is currently active for a given access mode              |
| ```Xcp_CopyCalPage```| `COPY_CAL_PAGE`               | copy one page onto another                                                 |

The active page is deliberately **not** cached by the stack. The application may switch pages without XCP's involvement,
so `Xcp_GetCalPage` is consulted on every request rather than keeping a shadow copy, which would go stale exactly
when it matters.

The specification requires `GET_CAL_PAGE` wherever `SET_CAL_PAGE` is implemented. `Xcp_Init` enforces that one
direction only: enabling `SET_CAL_PAGE` while `GET_CAL_PAGE` is disabled is rejected, reported as `XCP_E_INIT_FAILED`,
and leaves the module uninitialized. The converse is legal: `GET_CAL_PAGE` alone is a valid configuration, as is a
paging build with both disabled, which answers `ERR_CMD_UNKNOWN` to each. The same one-directional rule applies to
`GET_SEED` and `UNLOCK`.

### Declaring segments and pages
Segments live under `segments` in the *JSON* configuration, and FREEZE support is a module-level property under
`paging`:

| field                              | meaning                                                                        |
|:-----------------------------------|:-------------------------------------------------------------------------------|
| ```segments[].address```           | start address of the calibration region                                        |
| ```segments[].length```            | its length                                                                     |
| ```segments[].address_extension``` | reported by `GET_SEGMENT_INFO` mode 1                                          |
| ```segments[].compression_method```| reported by `GET_SEGMENT_INFO` mode 1; the stack does not itself compress       |
| ```segments[].encryption_method``` | reported the same way, and likewise not performed by the stack                  |
| ```segments[].pages[]```           | the interchangeable copies; each has an `init_segment` and access properties    |
| ```segments[].address_mappings[]```| optional source/destination/length triples, reported by mode 2                  |
| ```paging.freeze_supported```      | whether FREEZE may be requested at all, module-wide                             |

### Where this implementation resolves an ambiguous specification
Two commands are described one way in the prose of section 1.6 and another way in the error matrix of section
1.7.3.2.3.
Both are resolved in favour of the matrix, so that every **PAG** command reports a bad segment identically:

- `GET_SEGMENT_INFO`: the prose says an unavailable segment returns `ERR_OUT_OF_RANGE`; this stack returns
  `ERR_SEGMENT_NOT_VALID`, and reserves `ERR_OUT_OF_RANGE` for a bad mode, `SEGMENT_INFO` or `MAPPING_INDEX`.
- `GET_PAGE_INFO`: resolved the same way, for the same reason.

One matrix row is unreachable rather than unimplemented: section 1.7.3.2.3 lists `ERR_PAGE_NOT_VALID` for
`GET_CAL_PAGE`, but that request carries only an access mode and a segment number, so there is no page parameter to
validate.

### Block transfer and MAX_BS
`MAX_BS` bounds *master* block mode, whose packets are `DOWNLOAD_NEXT`. It does not bound slave block mode, which
governs multi-response commands such as `UPLOAD`; the two are separate properties and `DOWNLOAD` consults only the
master one. `DOWNLOAD_MAX` and `SHORT_DOWNLOAD` must not appear inside a block transfer sequence. The specification
prescribes no error code for that violation, so the stack answers `ERR_SEQUENCE`, which describes it accurately and
leaves the master able to recover.

## Data acquisition
The **DAQ** commands sample configured memory at the rate the integrator drives and transmit it to the master as
measurement data. Unlike the **PAG** group, which is absent from a build unless a segment is declared, at least one
DAQ list and one event channel are mandatory in the *JSON* configuration: `daqs` and `events` must each have at
least one entry.

### Declaring DAQ lists and event channels
DAQ lists live under `daqs`:

| field                    | meaning                                                                             |
|:-------------------------|:-------------------------------------------------------------------------------------|
| ```daqs[].name```             | the list's name, referenced by `events[].triggered_daq_list_ref`                     |
| ```daqs[].type```             | `DAQ`, `DAQ_STIM` or `STIM`; only `DAQ` is implemented, see Limitations              |
| ```daqs[].max_odt```          | the list's number of ODTs (static configuration only, see Limitations)               |
| ```daqs[].max_odt_entries```  | the number of entries in each of the list's ODTs                                     |
| ```daqs[].pdu_mapping```      | the lower-layer PDU that carries this list's traffic — a Tx PDU for `DAQ`, an Rx PDU for `DAQ_STIM`/`STIM` |
| ```daqs[].dtos[].pid```       | checked against the derived `FIRST_PID`, not what assigns it — see below             |

`dtos[].pid` does not assign a DAQ list's `FIRST_PID`. XCP part 2 §1.6.4.1.1.4 requires that "for every ODT
there's a unique absolute ODT number" and makes that numbering the slave's to assign, not the configuration's: the
generator derives each list's `FIRST_PID` as the running sum of the preceding lists' `max_odt`, and fails generation
if a configured `pid` contradicts the derived value. The field exists so a configuration can pin down and verify the
numbering it expects to get, not to set it.

Event channels live under `events`:

| field                                | meaning                                                                           |
|:--------------------------------------|:------------------------------------------------------------------------------------|
| ```events[].consistency```            | `DAQ`, `EVENT` or `ODT` consistency; reported to the master by `GET_DAQ_EVENT_INFO`, not implemented in this phase, see Limitations |
| ```events[].priority```               | the channel's own priority; carried through configuration but not consulted by any command implemented in this phase — not to be confused with a DAQ list's priority, set through `SET_DAQ_LIST_MODE` and limited to 0, see Limitations |
| ```events[].time_cycle```             | the sampling period this channel promises; 0 means "not cyclic"                    |
| ```events[].time_unit```              | the unit of `time_cycle`, one of the `TIMESTAMP_UNIT_*` values                     |
| ```events[].type```                   | `DAQ` or `DAQ_STIM`; only the `DAQ` direction is implemented                        |
| ```events[].triggered_daq_list_ref``` | the `daqs[].name` values this channel triggers                                     |

`time_cycle` and `time_unit` describe the raster this channel promises — the one a `GET_DAQ_EVENT_INFO` command
would report to the master (that command is not implemented in this phase, see Limitations). The module does not
enforce the promise itself: it keeps no clock of its own, so honouring it is entirely the integrator's
responsibility, exercised by calling `Xcp_TriggerEventChannel` at the declared rate — see *Triggering event
channels* below.

Four `protocol_layer` keys configure the DAQ processor as a whole:

| key                            | default | effect                                                                                                                                                                  |
|:--------------------------------|:--------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```identification_field_type``` | `ABSOLUTE` | `ABSOLUTE`, `RELATIVE_BYTE`, `RELATIVE_WORD` or `RELATIVE_WORD_ALIGNED`; sizes the DTO identification field at 1, 2, 3 or 4 bytes and therefore sets `MAX_ODT_ENTRY_SIZE_DAQ` to `MAX_DTO` minus that many bytes |
| ```daq_queue_size```            | 16      | the DTO ring's depth, in complete frames                                                                                                                               |
| ```prescaler_supported```       | `true`  | sets `PRESCALER_SUPPORTED` in `DAQ_PROPERTIES`; `false` makes `SET_DAQ_LIST_MODE` refuse a prescaler above 1                                                          |
| ```overload_indication```       | `EVENT` | how a full DTO ring is reported: `EVENT` transmits `EV_DAQ_OVERLOAD` (at most once per trigger, regardless of how many frames it dropped); `NONE` drops silently and reports no overload capability |

### Triggering event channels
The module holds no clock and never triggers an event channel on its own. Call

```c
void Xcp_TriggerEventChannel(uint16 eventChannelNumber);
```

from whatever context the event actually occurs in — a periodic task, an interrupt, an end-of-conversion. XCP part
2 §1.6.4.1.1.3 calls an event channel "the generic signal source that effectively determines the data transmission
timing", and only the integrator knows what that source is. Call it at the rate the channel's `time_cycle` and
`time_unit` declare, because that is the raster the slave promises the master.

This is **not** an AUTOSAR service. The API surface `SWS_Xcp` R4.3.1 defines is `Xcp_Init`, `Xcp_GetVersionInfo`,
`Xcp_SetTransmissionMode`, the three `Xcp_<Lo>` callbacks and `Xcp_MainFunction` — nothing in it triggers a DAQ
event channel, so an integrator will not find one there. `Xcp_TriggerEventChannel` is a vendor extension of this
module, in the same sense as the *JSON* configuration itself and the module's other integrator-facing extension
headers (`Xcp_Paging.h`, `Xcp_SeedKey.h`, and the rest under `test/stub/`).

### The exclusive area
`SchM_Xcp.h` declares `SchM_Enter_Xcp_DtoQueue()` and `SchM_Exit_Xcp_DtoQueue()`. An integrator replaces the stub
with the SchM the RTE generates. The area protects three things: the DTO ring indices, `Xcp_Internal.ongoing_transmit_type`
(the transmit arbitration state), and the event queue's read/write indices.

The event queue needs the same protection as the DTO ring because it has the same shape of hazard: two producers —
`Xcp_MainFunction`'s `EV_STORE_CAL` push and `Xcp_TriggerEventChannel`'s `EV_DAQ_OVERLOAD` push — and one consumer
reached from the CAN transmit confirmation, all three reachable from different contexts. Guard the event queue's
accesses under the same area as the DTO ring, not only the ring's.

The area must suspend anything that can call into this module — typically the CAN transmit interrupt — and that
includes `Xcp_CanIfTxConfirmation` itself: the confirmation updates `ongoing_transmit_type` outside the area before
`Xcp_StartNextTransmission` reads it under one, so the area must exclude the confirmation's own execution context
specifically, not only concurrent callers of the module's other entry points. A primitive that does not — a
spinlock shared with a confirmation handled on another core, for instance — breaks this design's assumption. The
module never holds the area across a call to `CanIf_Transmit`.

### Calling Xcp_MainFunction
Call `Xcp_MainFunction` cyclically, as SWS_Xcp_00824 requires. Its rate bounds how quickly the stack recovers after
the CAN interface refuses a transmission. It does **not** affect the DAQ measurement raster, which you set through
`Xcp_TriggerEventChannel`, and it does not affect throughput: a sampled burst is started by the trigger and carried
to completion by transmit confirmations.

### Where this implementation resolves an ambiguous specification
- `WRITE_DAQ`'s element size (request byte 2) is read in **bytes**. §1.6.4.1.1.2 annotates the field `[AG]`,
  implying address-granularity units, while §1.6.4.1.2.5 states the rules that bound it — a multiple of
  `GRANULARITY_ODT_ENTRY_SIZE_DAQ`, no larger than `MAX_ODT_ENTRY_SIZE_DAQ` — in bytes. Read as AG units the two
  sections contradict each other: `MAX_ODT_ENTRY_SIZE_DAQ` would be in AG units in one and bytes in the other. This
  implementation reads bytes throughout, which makes the two sections consistent with each other and makes
  `MAX_ODT_ENTRY_SIZE_DAQ` directly comparable with the DTO capacity an ODT actually has to fit inside; `WRITE_DAQ`
  requires the size to be a multiple of the address granularity and bounds it by `MAX_ODT_ENTRY_SIZE_DAQ`, both in
  bytes.
- `BIT_OFFSET` is validated and stored but does not change what is sampled: for a list with `DIRECTION = DAQ`, the
  master is the one that applies `BIT_MASK` to what it receives.
- `WRITE_DAQ` against an invalid DAQ pointer answers `ERR_OUT_OF_RANGE`; §1.6.4.1.1.2 leaves the pointer undefined
  in that state and prescribes no code for it.
- `SET_DAQ_LIST_MODE` answers `ERR_MODE_NOT_VALID` for every mode bit this phase does not implement (`ALTERNATING`,
  `DIRECTION`, `TIMESTAMP`, `PID_OFF`), and `ERR_OUT_OF_RANGE` for a priority above 0, which §1.6.4.1.1.3 names
  explicitly as the required response from a slave without DAQ list prioritisation.
- `START_STOP_SYNCH(start selected)` with no list currently selected answers `ERR_DAQ_CONFIG`, per §1.6.4.1.1.5.
- `CLEAR_DAQ_LIST` is accepted while the addressed list is running, per §1.6.4.2.1.1, which requires the command to
  stop a running transmission rather than refuse because one is active; the error matrix row was corrected to
  match.

## FREEZE mode
`SET_SEGMENT_MODE` can mark a segment for freezing, which the specification describes as selecting that segment to be
stored into non-volatile memory on the next `STORE_CAL_REQ`. The stack records the flag per segment and exposes it
through `Xcp_GetSegmentFreezeState`, declared in `Xcp.h` when the group is enabled.

This accessor exists because `Xcp_StoreCalibrationDataToNonVolatileMemory` receives no segment argument. Without it, the
FREEZE flag would be settable and readable over the bus but could never reach the code that performs the storing. An integrator implementing that callback should consult it for each segment.

Whether FREEZE may be requested at all is a module-level property, `freeze_supported` in the configuration, reported to
the master through bit 0 of `PAG_PROPERTIES` in the `GET_PAG_PROCESSOR_INFO` response. Requesting FREEZE on a slave that
does not support it is answered with `ERR_MODE_NOT_VALID`.


# Limitations
- The `GET_SLAVE_ID` command (CTO = `TRANSPORT_LAYER_CMD`, sub-command = `0xFF`) returns the PDU ID of the 
  **CMD**/**STIM** communication channel rather than the CAN identifier itself, to avoid a dependency on the PDU 
  mapping table in this module.
- The `GET_ID` command only supports the request identification type 0 (*ASCII text*).
- `SHORT_DOWNLOAD` can transfer no data at all when `MAX_CTO` is 8, as it is for XCP on CAN, because the command's
  own header fills the whole frame. The specification notes this. The stack still accepts the command, and rejects any
  element count above `(MAX_CTO - 8) / AG` with `ERR_OUT_OF_RANGE`.
- There are no timestamps: `TIMESTAMP_SUPPORTED` is clear in `DAQ_PROPERTIES`, and `SET_DAQ_LIST_MODE` refuses the
  `TIMESTAMP` mode bit with `ERR_MODE_NOT_VALID`.
- No `PID_OFF`, no `ALTERNATING`, no STIM direction, and no DAQ list prioritisation: a priority above 0 is refused
  with `ERR_OUT_OF_RANGE`, which §1.6.4.1.1.3 requires of a slave that does not support it.
- DAQ list configuration is static only. `FREE_DAQ` and the three `ALLOC_*` commands (`ALLOC_DAQ`, `ALLOC_ODT`,
  `ALLOC_ODT_ENTRY`) answer `ERR_CMD_UNKNOWN`.
- `WRITE_DAQ_MULTIPLE`, `READ_DAQ`, `GET_DAQ_CLOCK`, `GET_DAQ_LIST_INFO` and `GET_DAQ_EVENT_INFO` are not
  implemented.
- At most one DTO frame is in flight at a time: `Xcp_StartNextTransmission` arbitrates a single transmit slot
  across command responses, event packets and DAQ frames alike, and starts the next one only once the current one
  is confirmed. This is mandatory rather than a simplification, not merely a design choice this implementation
  happens to make: the AUTOSAR CAN Interface specification (SWS_CANIF_00068) has `CanIf` *overwrite* an
  already-buffered instance of the same L-PDU when `Can_Write` returns `CAN_BUSY`, so handing `CanIf` a second
  frame for a PDU before the first is confirmed would destroy the first silently — no error, no confirmation, one
  measurement sample simply missing.
- The test suite that exercises the exclusive area (see *The exclusive area* above) is single-threaded. It models
  the area as a real lock — detecting imbalance, mismatched nesting, and a lock left held at teardown — so a
  one-sided guard or a missing exit is caught directly. What it cannot do is observe a genuine race: the
  concurrency design is justified by reasoning about which contexts touch which state, and enforced by that lock
  model, not by a test that exercises true preemption. A port to a target where the guarded contexts run on
  different cores is relying on that reasoning, not on a demonstrated absence of races.
---
# TODO
- Protect the rest of the module's shared state used by both synchronous and asynchronous APIs. The DTO ring, the
  transmit arbitration state (`Xcp_Internal.ongoing_transmit_type`) and the event queue are now covered by the
  exclusive area described under *Data acquisition*; everything else the module holds across contexts is not.
- Use pre-processor to enable/disable optional APIs.
- Implement sub-command `SET_DAQ_LIST_CAN_IDENTIFIER` for CTO `TRANSPORT_LAYER_CMD`.
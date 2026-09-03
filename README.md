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
| ```XCP_PAGING_SUPPORTED```    | ```ON```/```OFF```               | derived                    | enables/disables the **PAG** command group. Normally left alone: the value follows whether any configuration in ```XCP_CONFIG_FILEPATH``` declares a segment, and keeps following it when that file changes — editing the configuration re-runs the configure step and updates this entry in place, in the build directory you already have. An explicit ```-D``` overrides it and survives reconfiguring. Configure from a clean build directory after upgrading: a cache entry written before this became an option holds ```STD_OFF```, which reads as ON and is indistinguishable from a deliberate override |
| ```XCP_DAQ_TIMESTAMP_SUPPORTED``` | ```ON```/```OFF```           | derived                    | enables/disables the data acquisition clock: the DAQ timestamp field, the `GET_DAQ_CLOCK` command, and `interface/Xcp.h`'s inclusion of `Xcp_DaqTimestamp.h`. Normally left alone: the default follows whether any configuration in ```XCP_CONFIG_FILEPATH``` declares a ```protocol_layer.timestamp``` block, and keeps following it when that file changes. An explicit ```-D``` overrides it and survives reconfiguring. See *Building the sources outside this CMake project* below — this one is **not** optional there |
| ```XCP_DAQ_TIMESTAMP_SIZE```  | ```0```/```1```/```2```/```4```  | derived                    | the DAQ timestamp field's width in bytes, as transmitted. Normally left alone: the default is the largest ```protocol_layer.timestamp.size``` any configuration in ```XCP_CONFIG_FILEPATH``` declares (```BYTE```/```WORD```/```DWORD``` → 1/2/4), or 0 when none does, and keeps following it when that file changes. An explicit ```-D``` overrides it and survives reconfiguring. See *Building the sources outside this CMake project* below |

To use this feature, simply add ```-D<definition>=<value>``` when configuring the build with CMake.

## Building the sources outside this CMake project
`source/*.c` includes `Xcp.h`, never the generated `Xcp_Cfg.h`. The generated header defines
`XCP_PAGING_SUPPORTED`, `XCP_MAX_DTO`, `XCP_DAQ_TIMESTAMP_SUPPORTED` and `XCP_DAQ_TIMESTAMP_SIZE` from the
configuration and is authoritative for any translation unit that includes it, but it never reaches the library
sources. This project's `CMakeLists.txt` closes that gap by deriving the same four values from
`XCP_CONFIG_FILEPATH` and putting them on the compiler command line; a build system that compiles `source/*.c`
itself has to do the same.

`interface/Xcp_Types.h` carries a fallback for three of them, so a translation unit that names none of them still
compiles — but the fallback is *off* (`XCP_DAQ_TIMESTAMP_SUPPORTED` `STD_OFF`, `XCP_DAQ_TIMESTAMP_SIZE` 0), and
nothing detects the disagreement that follows. The generated `Xcp_Cfg.c` sets `timestampType` from the
configuration regardless, so a slave built this way **reports** `TIMESTAMP_SUPPORTED`, reports a valid
`TIMESTAMP_MODE` and `TIMESTAMP_TICKS`, and accepts `SET_DAQ_LIST_MODE` with the `TIMESTAMP` bit — while the code
that writes the timestamp into the DTO and answers `GET_DAQ_CLOCK` has been compiled out. The master then
correlates every sample against timestamps that never reach the wire. Define both macros wherever you compile
`source/*.c`, with the values the table above describes.

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
| ```daqs[].type```             | `DAQ` or `DAQ_STIM`; only the `DAQ` direction is implemented, see Limitations. `STIM` is refused at generation: a list that is neither DAQ-capable nor stimulated could only be reported with both `DAQ_LIST_TYPE` bits clear, which §1.6.4.2.2.1 marks *Not allowed* |
| ```daqs[].max_odt```          | the list's number of ODTs (static configuration only, see Limitations)               |
| ```daqs[].max_odt_entries```  | the number of entries in each of the list's ODTs                                     |
| ```daqs[].pdu_mapping```      | the lower-layer PDU that carries this list's traffic — a Tx PDU for `DAQ`, an Rx PDU for `DAQ_STIM`. Two lists may share one, but a list sharing its Tx PDU cannot be granted `PID_OFF` |
| ```daqs[].dtos[].pid```       | checked against the derived `FIRST_PID`, not what assigns it — see below             |

`dtos[].pid` does not assign a DAQ list's `FIRST_PID`. XCP part 2 §1.6.4.1.1.4 requires that "for every ODT
there's a unique absolute ODT number" and makes that numbering the slave's to assign, not the configuration's: the
generator derives each list's `FIRST_PID` as the running sum of the preceding lists' `max_odt`, and fails generation
if a configured `pid` contradicts the derived value. The field exists so a configuration can pin down and verify the
numbering it expects to get, not to set it.

Event channels live under `events`:

| field                                | meaning                                                                           |
|:--------------------------------------|:------------------------------------------------------------------------------------|
| ```events[].consistency```            | `DAQ`, `EVENT` or `ODT` consistency; reported to the master by `GET_DAQ_EVENT_INFO` in `DAQ_EVENT_PROPERTIES` — `DAQ` (list-level consistency) is not yet distinguishable from `ODT` and is reported the same way `ODT` is |
| ```events[].name```                   | this channel's ASCII name, published through `GET_DAQ_EVENT_INFO` as `EVENT_CHANNEL_NAME_LENGTH` bytes when `protocol_layer.publish_names` is true (the default) — required in that case, checked at code-generation time. Printable ASCII excluding `"` and `\`, at most 255 characters: `EVENT_CHANNEL_NAME_LENGTH` on the wire (and `Xcp_EventChannelType::nameLength`) is a `uint8` |
| ```events[].priority```               | the channel's own priority; reported to the master by `GET_DAQ_EVENT_INFO` as `EVENT_CHANNEL_PRIORITY` — not to be confused with a DAQ list's priority, set through `SET_DAQ_LIST_MODE` and limited to 0 (DAQ list prioritisation is unimplemented, SP2c, see Limitations) |
| ```events[].time_cycle```             | the sampling period this channel promises; 0 means "not cyclic"                    |
| ```events[].time_unit```              | the unit of `time_cycle`, one of the `TIMESTAMP_UNIT_*` values                     |
| ```events[].type```                   | `DAQ` or `DAQ_STIM`; only the `DAQ` direction is implemented                        |
| ```events[].triggered_daq_list_ref``` | the `daqs[].name` values this channel triggers                                     |

`time_cycle` and `time_unit` describe the raster this channel promises — the one `GET_DAQ_EVENT_INFO` reports to
the master as `EVENT_CHANNEL_TIME_CYCLE` and `EVENT_CHANNEL_TIME_UNIT`. The module does not enforce the promise
itself: it keeps no clock of its own, so honouring it is entirely the integrator's responsibility, exercised by
calling `Xcp_TriggerEventChannel` at the declared rate — see *Triggering event channels* below.

Six `protocol_layer` keys configure the DAQ processor as a whole:

| key                            | default | effect                                                                                                                                                                  |
|:--------------------------------|:--------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```identification_field_type``` | `ABSOLUTE` | `ABSOLUTE`, `RELATIVE_BYTE`, `RELATIVE_WORD` or `RELATIVE_WORD_ALIGNED`; sizes the DTO identification field at 1, 2, 3 or 4 bytes and therefore sets `MAX_ODT_ENTRY_SIZE_DAQ` to `MAX_DTO` minus that many bytes |
| ```daq_queue_size```            | 16      | how many sampled DTO frames may wait for transmission at once. `Xcp_TriggerEventChannel` fills the ring; the transmission chain drains one frame per `CanIf` confirmation, so this sizes the burst the slave can absorb when sampling briefly outruns the bus. One slot is a whole `Xcp_DtoFrameType`, so the ring costs `daq_queue_size * (MAX_DTO + 4)` bytes of RAM at worst — `MAX_DTO` of payload after a `PduIdType` and a length byte, padded to the alignment of `PduIdType` (`uint16` here, so +4, or +3 when `MAX_DTO` is odd). At the defaults, 16 * (8 + 4) = 192 bytes per configuration. A frame sampled while the ring is full is dropped and reported per `overload_indication` |
| ```prescaler_supported```       | `true`  | sets `PRESCALER_SUPPORTED` in `DAQ_PROPERTIES`; `false` makes `SET_DAQ_LIST_MODE` refuse a prescaler above 1                                                          |
| ```overload_indication```       | `EVENT` | how a full DTO ring is reported: `EVENT` transmits `EV_DAQ_OVERLOAD` (at most once per trigger, regardless of how many frames it dropped); `NONE` drops silently and reports no overload capability |
| ```timestamp```                 | absent  | the data acquisition clock: an object with `size` (`BYTE`/`WORD`/`DWORD`, a 1/2/4-byte wire width), `unit` (one of the `TIMESTAMP_UNIT_*` values) and `ticks` (ticks per unit, 1-65535). Reported as `TIMESTAMP_SUPPORTED` in `DAQ_PROPERTIES` (`GET_DAQ_PROCESSOR_INFO`) and, when present, as `TIMESTAMP_MODE`/`TIMESTAMP_TICKS` (`GET_DAQ_RESOLUTION_INFO`). Absent means the slave has no clock: `TIMESTAMP_SUPPORTED` stays clear, `TIMESTAMP_MODE`/`TIMESTAMP_TICKS` are invalid (XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5 permits this explicitly), and `SET_DAQ_LIST_MODE` refuses the `TIMESTAMP` mode bit with `ERR_MODE_NOT_VALID`. When present, the integrator must supply `Xcp_GetDaqTimestamp` — see *Supplying the data acquisition clock* below |
| ```publish_names```             | `true`  | whether event channel names are compiled in and reported through `GET_DAQ_EVENT_INFO`'s `EVENT_CHANNEL_NAME_LENGTH` (XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.7). `true` requires every `events[]` entry to declare a `name`, checked at code-generation time. `false` reports `EVENT_CHANNEL_NAME_LENGTH` 0 for every channel, which that section defines as "if not available" |

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

### Supplying the data acquisition clock
When `protocol_layer.timestamp` is configured, the module needs a counter to read. Implement

```c
uint32 Xcp_GetDaqTimestamp(void);
```

whose prototype is defined [here](./test/stub/Xcp_DaqTimestamp.h). Like the paging and seed/key callbacks, this
header is integrator-supplied and lives under `test/stub/`, not in `interface/`: this module ships only its own
four headers there (`Xcp.h`, `XcpOnCan_Cbk.h`, `Xcp_Errors.h`, `Xcp_Types.h`), and `interface/Xcp.h` pulls
`Xcp_DaqTimestamp.h` in only when `XCP_DAQ_TIMESTAMP_SUPPORTED` is `STD_ON` — the same conditional inclusion
`Xcp_Paging.h` gets, so a configuration with no `timestamp` block is never asked to supply a clock.

The implementation must be:
- a **free-running counter**, never reset or modified by this module or the integrator, that wraps around on
  overflow — XCP part 2 - Protocol Layer Specification 1.1/1.1.2.2 requires exactly this of the data acquisition
  clock;
- **re-entrant**, because it is called from two different contexts: from `Xcp_TriggerEventChannel`, in whatever
  context the integrator triggers an event from, and from `Xcp_CanIfRxIndication` on receipt of `GET_DAQ_CLOCK`,
  which may be a different context again, including an interrupt;
- **non-blocking**, for the same reason;
- kept at the resolution `protocol_layer.timestamp` declares. The module only reports that `size`/`unit`/`ticks`
  declaration to the master — through `GET_DAQ_PROCESSOR_INFO` and `GET_DAQ_RESOLUTION_INFO` — it cannot verify
  the counter actually runs at it. A mismatch here is not a build error or a runtime fault; it is silently wrong
  measurement data on the bus.

`Xcp_GetDaqTimestamp` always returns `uint32`, regardless of the configured `size`: `GET_DAQ_CLOCK` transmits a
DWORD whatever the DTO timestamp field's width is, and the DTO field truncates the same value down to it.

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
- `SET_DAQ_LIST_MODE` answers `ERR_MODE_NOT_VALID` unconditionally for `DIRECTION` and `ALTERNATING`, neither of
  which this phase implements. `TIMESTAMP` and `PID_OFF` are conditionally accepted rather than blanket-refused:
  `TIMESTAMP` requires `protocol_layer.timestamp` to be configured, answering `ERR_MODE_NOT_VALID` otherwise, and
  enough spare capacity left in ODT 0 for the timestamp field once it is added, answering `ERR_OUT_OF_RANGE`
  otherwise. `PID_OFF` requires `identification_field_type: ABSOLUTE`, a single-ODT DAQ list, and a
  `pdu_mapping` no other DAQ list in the same configuration uses, answering `ERR_MODE_NOT_VALID` otherwise —
  1.1/1.1.2.1 allows `PID_OFF` only for the absolute identification field type, and then requires "separate
  CAN-IDs for each DAQ list and only one ODT for each DAQ list" at the transport layer. Both halves of that
  sentence are checked: nothing stops two DAQ lists from naming the same `pdu_mapping` (the shipped
  `config/xcp.json` does exactly that), and two such lists with `PID_OFF` would put two unidentifiable DTOs on
  one CAN-Id. A shared `pdu_mapping` is otherwise perfectly legal; it only rules out `PID_OFF`. The command also
  answers `ERR_OUT_OF_RANGE` for a priority above 0, which §1.6.4.1.1.3 names explicitly as the required response
  from a slave without DAQ list prioritisation, and for `TIMESTAMP` on a DAQ list configured with `max_odt: 0`,
  which has no ODT 0 to carry the timestamp field.
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
- `WRITE_DAQ_MULTIPLE` is implemented but ships disabled in `config/xcp.json`
  (`apis.xcp_write_daq_multiple_api_enable.enabled: false`), with `max_cto` left at 8. XCP part 2 §1.6.4.1.2.1
  requires `MAX_CTO >= 10` for this command, and 10 is neither a classic CAN frame size nor a CAN FD payload
  length, so enabling it is an integrator decision with transport consequences, not a flag to flip casually: an
  integrator who enables the API without also raising `max_cto` to at least 10 gets a code-generation failure,
  and one who raises `max_cto` to exactly 10 gets a frame no CAN network carries.
- No `ALTERNATING` and no DAQ list prioritisation — both SP2c: a priority above 0 is refused with
  `ERR_OUT_OF_RANGE`, which §1.6.4.1.1.3 requires of a slave that does not support it. No STIM direction (SP3).
- DAQ list configuration is static only (SP2d). `FREE_DAQ` and the three `ALLOC_*` commands (`ALLOC_DAQ`,
  `ALLOC_ODT`, `ALLOC_ODT_ENTRY`) answer `ERR_CMD_UNKNOWN`.
- At most one DTO frame is in flight at a time (SP2c): `Xcp_StartNextTransmission` arbitrates a single transmit
  slot across command responses, event packets and DAQ frames alike, and starts the next one only once the
  current one is confirmed. This is mandatory rather than a simplification, not merely a design choice this
  implementation happens to make: the AUTOSAR CAN Interface specification (SWS_CANIF_00068) has `CanIf`
  *overwrite* an already-buffered instance of the same L-PDU when `Can_Write` returns `CAN_BUSY`, so handing
  `CanIf` a second frame for a PDU before the first is confirmed would destroy the first silently — no error, no
  confirmation, one measurement sample simply missing.
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
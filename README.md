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
| ```XCP_PAGING_SUPPORTED```    | ```ON```/```OFF```               | derived                    | enables/disables the **PAG** command group. Normally left alone: the default follows whether any configuration in ```XCP_CONFIG_FILEPATH``` declares a segment. An explicit ```-D``` overrides it and survives reconfiguring |

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
---
# TODO
- Protect variables used in both synchronous and asynchronous APIs.
- Use pre-processor to enable/disable optional APIs.
- Implement sub-command `SET_DAQ_LIST_CAN_IDENTIFIER` for CTO `TRANSPORT_LAYER_CMD`.
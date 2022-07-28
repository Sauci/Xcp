| branch                                               | build status                                                                                           | coverage                                                                                                                     |
|:-----------------------------------------------------|:-------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| [master](https://github.com/Sauci/Xcp/tree/master)   | [![Build Status](https://travis-ci.org/Sauci/Xcp.svg?branch=master)](https://travis-ci.org/Sauci/Xcp)  | [![codecov](https://codecov.io/gh/Sauci/Xcp/branch/master/graph/badge.svg)](https://codecov.io/gh/Sauci/Xcp/branch/master)   |
| [develop](https://github.com/Sauci/Xcp/tree/develop) | [![Build Status](https://travis-ci.org/Sauci/Xcp.svg?branch=develop)](https://travis-ci.org/Sauci/Xcp) | [![codecov](https://codecov.io/gh/Sauci/Xcp/branch/develop/graph/badge.svg)](https://codecov.io/gh/Sauci/Xcp/branch/develop) |

# Configure/Compile -time definitions
The following definitions might be set by the user, depending on the needs.

| definition                    | values                           | default                    | description                                                                                                                                                                      |
|:------------------------------|:---------------------------------|:---------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```AUTOSAR_STD_HEADER_PATH``` | ```-```                          | ```Xcp/test/stub/common``` | specifies the directory containing **AUTOSAR** standard headers ComStack_Types.h and Std_Types.h (used when integrating this module in an other project)                         |
| ```XCP_CONFIG_FILEPATH```     | ```-```                          | ```Xcp/config/xcp.json```  | specifies which json configuration file should be used to generate the auto-generated code                                                                                       |
| ```XCP_ENABLE_TEST```         | ```ON```/```OFF```               | ```OFF```                  | enables/disables tests.                                                                                                                                                          |
| ```ENABLE_DET```              | ```ON```/```OFF```               | ```ON```                   | enables/disables development error detections (see AUTOSAR [DET](https://www.autosar.org/fileadmin/user_upload/standards/classic/4-3/AUTOSAR_SWS_DefaultErrorTracer.pdf) module) |
| ```ENABLE_DOC_GEN```          | ```ON```/```OFF```               | ```OFF```                  | enables/disables generation of [Doxygen](http://www.doxygen.nl/) documentation                                                                                                   |
| ```ENABLE_PC_LINT```          | ```ON```/```OFF```               | ```OFF```                  | enables/disables generation of targets related to static code analysis (should be disabled if [PC-Lint](https://www.gimpel.com) software is not available)                       |
| ```MISRA_C_VERSION```         | ```1998```/```2004```/```2012``` | ```2012```                 | specifies which version of **MISRA** should be used when performing static code analysis (only used if ```ENABLE_PC_LINT``` is set)                                              |
| ```XCP_SUPPRESS_TX_SUPPORT``` | ```ON / OFF```                   | ```ON```                   | enables/disables transmission functionality of the XCP module                                                                                                                    | 

To use this feature, simply add ```-D<definition>=<value>``` when configuring the build with CMake.

# Module configuration
A large part of this module consists of auto-generated code. It takes a *JSON* file as input (the path of this file is
specified through the `XCP_CONFIG_FILEPATH` CMake variable, defaulting to [this](config/xcp.json) file), and generates 
the *Xcp_Cfg.c* and *Xcp_Cfg.h* files. The content of this configuration file is specified with the *JSON* schema
available [here](config/xcp.schema.json). Most of the recent IDEs are providing auto-completion of the configuration 
file based on its schema, thus it is highly recommended using it.

# Implementation details
This section gives a few implementation details, where the specification is not very clear or a little bit fuzzy. This
will allow the user to properly configure the communication parameters on the master side.

## Seed lifetime
Whenever the seed is requested by the master trough the `GET_SEED` command, a new seed is requested by the XCP stack 
through the `Xcp_GetSeed` function. The idea behind it is that if the slave would not do this, the master could 
calculate a key for a single seed and use it forever, which would lead to a less secured resource protection.

Whenever the master issues a `UNLOCK` command, the slave will discard the seed as well, either upon successful and 
unsuccessful command result. This implies a new `GET_SEED` request for each `UNLOCK` command.

The `Xcp_GetSeed` function implementation is left to the stack user. The target on which the stack is integrated could
provide some random value generator, thus this is target-specific. The function's prototype is defined 
[here](./test/stub/Xcp_SeedKey.h).

## Key lifetime
Whenever an `UNLOCK` command is issued by the master, the key is calculated by the slave using the last seed value
requested by the master. No matter if the keys are matching or not, the key validity is discarded after the execution of
the command following the `UNLOCK` sequence.

If the master issues a `UNLOCK` command without calling `GET_SEED` first, the stack will respond with and error packet
identifier, and the code `ERR_SEQUENCE`.

The implementation of the function responsible for key calculation, `Xcp_CalcKey` is left to the user. This is required,
as the function must be shared between the master and the slave.

# Limitations
- The `GET_SLAVE_ID` command (CTO = `TRANSPORT_LAYER_CMD`, sub-command = `0xFF`) returns the PDU ID of the 
  **CMD**/**STIM** communication channel, not the CAN identifier directly. This is implemented this way to prevent 
  dependencies on the PDU mapping table in this module.
- The `GET_ID` command only supports the request identification type 0 (*ASCII text*).
---
# TODO
- Protect variables used in both synchronous and asynchronous APIs.
- Use pre-processor to enable/disable optional APIs.
- Implement sub-command `SET_DAQ_LIST_CAN_IDENTIFIER` for CTO `TRANSPORT_LAYER_CMD`.
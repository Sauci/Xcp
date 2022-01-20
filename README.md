| branch                                               | build status                                                                                           | coverage                                                                                                                     |
|:-----------------------------------------------------|:-------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| [master](https://github.com/Sauci/Xcp/tree/master)   | [![Build Status](https://travis-ci.org/Sauci/Xcp.svg?branch=master)](https://travis-ci.org/Sauci/Xcp)  | [![codecov](https://codecov.io/gh/Sauci/Xcp/branch/master/graph/badge.svg)](https://codecov.io/gh/Sauci/Xcp/branch/master)   |
| [develop](https://github.com/Sauci/Xcp/tree/develop) | [![Build Status](https://travis-ci.org/Sauci/Xcp.svg?branch=develop)](https://travis-ci.org/Sauci/Xcp) | [![codecov](https://codecov.io/gh/Sauci/Xcp/branch/develop/graph/badge.svg)](https://codecov.io/gh/Sauci/Xcp/branch/develop) |

# CMake definitions
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

# TODO
- Protect variables used in both synchronous and asynchronous APIs.

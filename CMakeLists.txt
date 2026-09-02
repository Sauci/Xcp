cmake_minimum_required(VERSION 3.8.0)

project(Xcp VERSION 0.1.0 LANGUAGES C)

set(AUTOSAR_STD_HEADER_PATH ${CMAKE_CURRENT_SOURCE_DIR}/test/stub/common CACHE FILEPATH
    "path to directory containing Std_Types.h and ComStack_Types.h.")
set(XCP_CONFIG_FILEPATH ${CMAKE_CURRENT_SOURCE_DIR}/config/xcp.json CACHE FILEPATH
    "path to configuration file used to generate post-build configuration.")
option(XCP_ENABLE_TEST "enables/disables tests." OFF)
option(ENABLE_DET "enables/disables development error detection." ON)
option(ENABLE_DOC_GEN "enables/disables documentation generation." OFF)
option(ENABLE_PC_LINT "enables/disables static code analysis." OFF)
set(MISRA_C_VERSION 2012 CACHE STRING "MISRA standard.")
option(XCP_SUPPRESS_TX_SUPPORT "enables/disables transmission functionality of the XCP module." ON)
set(XCP_PYTEST_ARGS "" CACHE STRING "extra arguments forwarded to pytest (e.g. -k download).")

find_package(PythonInterp 3.6 REQUIRED)

# Whether the PAG commands are compiled in follows from whether the configuration declares a
# segment, which is the rule the generated Xcp_Cfg.h states and the README documents. Deriving it
# here rather than defaulting it means the default build of a configuration that declares one
# actually answers those commands: a fixed default of STD_OFF silently compiled all eight out and
# answered ERR_CMD_UNKNOWN, since nothing on the library's include path pulls in Xcp_Cfg.h to
# supply the value instead.
execute_process(
    COMMAND ${PYTHON_EXECUTABLE} -c
        "import json,sys;c=json.load(open(sys.argv[1]));print('ON' if any(x.get('segments') for x in c['configurations']) else 'OFF')"
        ${XCP_CONFIG_FILEPATH}
    OUTPUT_VARIABLE XCP_PAGING_SUPPORTED_DERIVED
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE XCP_PAGING_SUPPORTED_RESULT)

if(NOT XCP_PAGING_SUPPORTED_RESULT EQUAL 0)
    message(FATAL_ERROR "could not derive XCP_PAGING_SUPPORTED from ${XCP_CONFIG_FILEPATH}")
endif()

# An option, like every other switch here, so that -DXCP_PAGING_SUPPORTED=ON does what a reader
# of the others would expect. The AUTOSAR STD_ON/STD_OFF spelling is applied where the definition
# reaches the compiler, as it is for ENABLE_DET. Not FORCE: an explicit -D has to survive the
# next configure for the help string's "override" to mean anything.
option(XCP_PAGING_SUPPORTED
    "enables/disables the calibration page switching commands. Defaults to whether XCP_CONFIG_FILEPATH declares at least one segment; override only if you know why."
    ${XCP_PAGING_SUPPORTED_DERIVED})

# XCP_DAQ_TIMESTAMP_SUPPORTED/_SIZE need exactly the same treatment as XCP_PAGING_SUPPORTED above,
# for a sharper reason: Xcp_Types.h's own fallback for these two macros (0x00u/0u, added so the test
# harness's handle.define() has literal text to key off) is included by the generated Xcp_Cfg.h
# *before* that file's own conditional block for them (Xcp_Types.h at its line 4, the block at its
# line 24), so the fallback always wins there regardless of what the configuration says -- and
# source/*.c never includes Xcp_Cfg.h at all, the same gap paging had. Left undefined, or left to
# that fallback, a configuration that declares protocol_layer.timestamp would silently build with
# XCP_DAQ_TIMESTAMP_SUPPORTED == STD_OFF, gating Xcp_GetDaqTimestamp's declaration off entirely.
execute_process(
    COMMAND ${PYTHON_EXECUTABLE} -c
        "import json,sys;c=json.load(open(sys.argv[1]));print('ON' if any(x['protocol_layer'].get('timestamp') for x in c['configurations']) else 'OFF')"
        ${XCP_CONFIG_FILEPATH}
    OUTPUT_VARIABLE XCP_DAQ_TIMESTAMP_SUPPORTED_DERIVED
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE XCP_DAQ_TIMESTAMP_SUPPORTED_RESULT)

if(NOT XCP_DAQ_TIMESTAMP_SUPPORTED_RESULT EQUAL 0)
    message(FATAL_ERROR "could not derive XCP_DAQ_TIMESTAMP_SUPPORTED from ${XCP_CONFIG_FILEPATH}")
endif()

option(XCP_DAQ_TIMESTAMP_SUPPORTED
    "enables/disables the data acquisition clock. Defaults to whether XCP_CONFIG_FILEPATH declares a protocol_layer.timestamp block; override only if you know why."
    ${XCP_DAQ_TIMESTAMP_SUPPORTED_DERIVED})

# Not boolean, so option() (a BOOL cache variable) does not fit; a plain CACHE STRING is the closest
# equivalent, matching XCP_PYTEST_ARGS below. XCP_TimestampTypeType's enumerator, not the wire size,
# is what would be handy to compute this from, but that enum is implicit and deliberately not what
# this counts (see script/header_cfg.h.jinja2 and script/source_cfg.c.jinja2).
execute_process(
    COMMAND ${PYTHON_EXECUTABLE} -c
        "import json,sys;c=json.load(open(sys.argv[1]));s={'BYTE':1,'WORD':2,'DWORD':4};print(max([s[x['protocol_layer']['timestamp']['size']] for x in c['configurations'] if x['protocol_layer'].get('timestamp')], default=0))"
        ${XCP_CONFIG_FILEPATH}
    OUTPUT_VARIABLE XCP_DAQ_TIMESTAMP_SIZE_DERIVED
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE XCP_DAQ_TIMESTAMP_SIZE_RESULT)

if(NOT XCP_DAQ_TIMESTAMP_SIZE_RESULT EQUAL 0)
    message(FATAL_ERROR "could not derive XCP_DAQ_TIMESTAMP_SIZE from ${XCP_CONFIG_FILEPATH}")
endif()

set(XCP_DAQ_TIMESTAMP_SIZE ${XCP_DAQ_TIMESTAMP_SIZE_DERIVED} CACHE STRING
    "timestamp field width in bytes, as transmitted. Defaults to the largest size any configuration in XCP_CONFIG_FILEPATH declares; override only if you know why.")

if (${ENABLE_DOC_GEN})
    find_package(Doxygen REQUIRED dot)

    set(DOXYGEN_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/doc)

    doxygen_add_docs(${PROJECT_NAME}.doc source interface COMMENT "generating Xcp documentation")
endif ()

add_subdirectory(extern)
add_subdirectory(generated)
# add_subdirectory(debug)

# Absolute, so that $<TARGET_PROPERTY:Xcp,SOURCES> can be consumed as-is. CMake keeps the SOURCES
# property exactly as written here, and the pytest harness, the gcov merge in test.sh and the
# Codecov upload all read that property rather than repeating the list. Adding a translation unit
# should mean editing this list and nothing else.
add_library(Xcp STATIC
    ${CMAKE_CURRENT_SOURCE_DIR}/source/Xcp.c
    ${CMAKE_CURRENT_SOURCE_DIR}/source/Xcp_Std.c
    ${CMAKE_CURRENT_SOURCE_DIR}/source/Xcp_Cal.c
    ${CMAKE_CURRENT_SOURCE_DIR}/source/Xcp_Pag.c
    ${CMAKE_CURRENT_SOURCE_DIR}/source/Xcp_Daq.c
    ${CMAKE_CURRENT_SOURCE_DIR}/source/Xcp_DaqRuntime.c)

target_compile_definitions(Xcp
    PRIVATE XCP_DEV_ERROR_DETECT=$<IF:$<BOOL:${ENABLE_DET}>,STD_ON,STD_OFF>
    PRIVATE XCP_SW_VERSION_MAJOR=${PROJECT_VERSION_MAJOR}
    PRIVATE XCP_SW_VERSION_MINOR=${PROJECT_VERSION_MINOR}
    PRIVATE XCP_SW_VERSION_PATCH=${PROJECT_VERSION_PATCH}
    PUBLIC XCP_AR_RELEASE_MAJOR_VERSION=4 # SWS_BSW_00059
    PUBLIC XCP_AR_RELEASE_MINOR_VERSION=3
    PUBLIC XCP_AR_RELEASE_PATCH_VERSION=1
    PUBLIC XCP_API=STD_ON
    PUBLIC XCP_GET_VERSION_INFO_API=STD_ON # ECUC_Xcp_00283
    PUBLIC XCP_CHANGE_PARAMETER_API=STD_ON # ECUC_Xcp_00299
    PUBLIC XCP_READ_PARAMETER_API=STD_ON # ECUC_Xcp_00300
    PUBLIC XCP_SUPPRESS_TX_SUPPORT=$<IF:$<BOOL:${OS_GET_TIME_API}>,STD_ON,STD_OFF>
    PUBLIC XCP_PAGING_SUPPORTED=$<IF:$<BOOL:${XCP_PAGING_SUPPORTED}>,STD_ON,STD_OFF>
    PUBLIC XCP_DAQ_TIMESTAMP_SUPPORTED=$<IF:$<BOOL:${XCP_DAQ_TIMESTAMP_SUPPORTED}>,STD_ON,STD_OFF>
    PUBLIC XCP_DAQ_TIMESTAMP_SIZE=${XCP_DAQ_TIMESTAMP_SIZE})

target_include_directories(Xcp
    PUBLIC interface
    PUBLIC ${AUTOSAR_STD_HEADER_PATH}
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/generated
    PUBLIC $<$<BOOL:${XCP_ENABLE_TEST}>:${CMAKE_CURRENT_SOURCE_DIR}/test/stub>)

target_link_libraries(Xcp
    PUBLIC Xcp_Rt)

if (${XCP_ENABLE_TEST})
    enable_testing()

    # test.sh runs cmake, so it cannot itself be a configured template. Publishing the list into the
    # build directory gets the same result the other way round: the script reads what CMake knows
    # instead of repeating it. file(GENERATE), not configure_file, because only the former expands
    # generator expressions.
    file(GENERATE
        OUTPUT ${CMAKE_BINARY_DIR}/xcp_sources.txt
        CONTENT "$<JOIN:$<TARGET_PROPERTY:Xcp,SOURCES>,\n>\n")

    add_test(NAME Xcp_UnitTest
        COMMAND ${PYTHON_EXECUTABLE} -W ignore::DeprecationWarning
        -m pytest ${CMAKE_CURRENT_SOURCE_DIR}/test -v -x ${XCP_PYTEST_ARGS}
        --build_directory ${CMAKE_BINARY_DIR}
        --script_directory ${PROJECT_SOURCE_DIR}/script
        --header ${PROJECT_SOURCE_DIR}/interface/Xcp.h
        --source "$<JOIN:$<TARGET_PROPERTY:Xcp,SOURCES>,$<SEMICOLON>>"
        --compile_definitions $<JOIN:$<TARGET_PROPERTY:Xcp,COMPILE_DEFINITIONS>,$<SEMICOLON>>
        --include_directories $<JOIN:$<TARGET_PROPERTY:Xcp,INCLUDE_DIRECTORIES>,$<SEMICOLON>>
        --junitxml=./report/${PROJECT_NAME}.xml
        WORKING_DIRECTORY ${CMAKE_BINARY_DIR})
endif ()

if (${ENABLE_PC_LINT})
    add_pc_lint_target(NAME Xcp
        DEPENDENCIES ${CMAKE_CURRENT_SOURCE_DIR}/generated/Xcp_PBcfg.h
        OUTPUT_LOG ${CMAKE_CURRENT_SOURCE_DIR}/${PROJECT_NAME}.lnt.log
        EXCLUDE_DIRECTORIES
        ${AUTOSAR_STD_HEADER_PATH}
        OPTION_FILES
        ${CMAKE_CURRENT_SOURCE_DIR}/extern/lint/MISRA${MISRA_C_VERSION}.lnt
            ${CMAKE_CURRENT_SOURCE_DIR}/config/Xcp.lnt)
endif ()

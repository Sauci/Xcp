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
        "import json,sys;c=json.load(open(sys.argv[1]));print('STD_ON' if any(x.get('segments') for x in c['configurations']) else 'STD_OFF')"
        ${XCP_CONFIG_FILEPATH}
    OUTPUT_VARIABLE XCP_PAGING_SUPPORTED_DERIVED
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE XCP_PAGING_SUPPORTED_RESULT)

if(NOT XCP_PAGING_SUPPORTED_RESULT EQUAL 0)
    message(FATAL_ERROR "could not derive XCP_PAGING_SUPPORTED from ${XCP_CONFIG_FILEPATH}")
endif()

# Not FORCE: the derived value is the default, and an explicit -DXCP_PAGING_SUPPORTED=... has to
# survive the next configure for the help string's "override" to mean anything.
set(XCP_PAGING_SUPPORTED ${XCP_PAGING_SUPPORTED_DERIVED} CACHE STRING
    "STD_ON/STD_OFF: whether the calibration page switching callbacks are compiled in. Defaults to whether XCP_CONFIG_FILEPATH declares at least one segment; override only if you know why.")

if (${ENABLE_DOC_GEN})
    find_package(Doxygen REQUIRED dot)

    set(DOXYGEN_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/doc)

    doxygen_add_docs(${PROJECT_NAME}.doc source interface COMMENT "generating Xcp documentation")
endif ()

add_subdirectory(extern)
add_subdirectory(generated)
# add_subdirectory(debug)

add_library(Xcp STATIC
    source/Xcp.c
    source/Xcp_Std.c
    source/Xcp_Cal.c
    source/Xcp_Pag.c
    source/Xcp_Daq.c)

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
    PUBLIC XCP_PAGING_SUPPORTED=${XCP_PAGING_SUPPORTED})

target_include_directories(Xcp
    PUBLIC interface
    PUBLIC ${AUTOSAR_STD_HEADER_PATH}
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/generated
    PUBLIC $<$<BOOL:${XCP_ENABLE_TEST}>:${CMAKE_CURRENT_SOURCE_DIR}/test/stub>)

target_link_libraries(Xcp
    PUBLIC Xcp_Rt)

if (${XCP_ENABLE_TEST})
    enable_testing()

    add_test(NAME Xcp_UnitTest
        COMMAND ${PYTHON_EXECUTABLE} -W ignore::DeprecationWarning
        -m pytest ${CMAKE_CURRENT_SOURCE_DIR}/test -v -x ${XCP_PYTEST_ARGS}
        --build_directory ${CMAKE_BINARY_DIR}
        --script_directory ${PROJECT_SOURCE_DIR}/script
        --header ${PROJECT_SOURCE_DIR}/interface/Xcp.h
        --source "${PROJECT_SOURCE_DIR}/source/Xcp.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Std.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Cal.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Pag.c$<SEMICOLON>${PROJECT_SOURCE_DIR}/source/Xcp_Daq.c"
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

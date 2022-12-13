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

find_package(PythonInterp 3.6 REQUIRED)

if (${ENABLE_DOC_GEN})
    find_package(Doxygen REQUIRED dot)

    set(DOXYGEN_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/doc)

    doxygen_add_docs(${PROJECT_NAME}.doc source interface COMMENT "generating Xcp documentation")
endif ()

add_subdirectory(extern)
add_subdirectory(generated)
# add_subdirectory(debug)

add_library(Xcp STATIC source/Xcp.c)

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
    PUBLIC XCP_SUPPRESS_TX_SUPPORT=$<IF:$<BOOL:${OS_GET_TIME_API}>,STD_ON,STD_OFF>)

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
        -m pytest ${CMAKE_CURRENT_SOURCE_DIR}/test -v -x
        --build_directory ${CMAKE_BINARY_DIR}
        --script_directory ${PROJECT_SOURCE_DIR}/script
        --header ${PROJECT_SOURCE_DIR}/interface/Xcp.h
        --source ${PROJECT_SOURCE_DIR}/source/Xcp.c
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

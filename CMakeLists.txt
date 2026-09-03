# 3.19 for string(JSON), which replaces the execute_process+python configuration reads below.
# The Docker image gets it from PyPI (requirements.txt) because alpine 3.10's apk pins 3.14.5.
cmake_minimum_required(VERSION 3.19)

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

# All three configuration-derived values below come from one parse of XCP_CONFIG_FILEPATH.
# string(JSON ... GET/LENGTH) reports a missing key through ERROR_VARIABLE rather than failing the
# configure step -- an unchecked GET on an absent key is a hard configure error, unlike the
# dict.get() the Python this replaces used -- so a configuration without "segments" or
# "protocol_layer.timestamp" has to be, and is, treated as its OFF/0 default explicitly below. The
# wire-size mapping stays a literal BYTE/WORD/DWORD -> 1/2/4, not anything derived from
# Xcp_TimestampTypeType: that enum is implicit, and its FOUR_BYTE enumerator is 3, the size the
# specification marks "Not allowed" (see script/header_cfg.h.jinja2 and script/source_cfg.c.jinja2).
file(READ ${XCP_CONFIG_FILEPATH} XCP_CONFIG_JSON)

# file(READ) creates no dependency of its own, so without this the configure step does not re-run
# when the configuration changes -- and generated/CMakeLists.txt *does* DEPEND on the same file, so
# `make` regenerates Xcp_Cfg.c from the new configuration while every value derived below still
# describes the old one.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${XCP_CONFIG_FILEPATH})

string(JSON XCP_CONFIG_N_CONFIGURATIONS LENGTH ${XCP_CONFIG_JSON} configurations)

set(XCP_PAGING_SUPPORTED_DERIVED OFF)
set(XCP_DAQ_TIMESTAMP_SUPPORTED_DERIVED OFF)
set(XCP_DAQ_TIMESTAMP_SIZE_DERIVED 0)

if(XCP_CONFIG_N_CONFIGURATIONS GREATER 0)
    math(EXPR XCP_CONFIG_LAST_INDEX "${XCP_CONFIG_N_CONFIGURATIONS} - 1")

    foreach(XCP_CONFIG_INDEX RANGE ${XCP_CONFIG_LAST_INDEX})
        string(JSON XCP_CFG_SEGMENTS_LENGTH ERROR_VARIABLE XCP_CFG_SEGMENTS_ERROR
            LENGTH ${XCP_CONFIG_JSON} configurations ${XCP_CONFIG_INDEX} segments)
        if(NOT XCP_CFG_SEGMENTS_ERROR)
            if(XCP_CFG_SEGMENTS_LENGTH GREATER 0)
                set(XCP_PAGING_SUPPORTED_DERIVED ON)
            endif()
        endif()

        string(JSON XCP_CFG_TIMESTAMP_SIZE ERROR_VARIABLE XCP_CFG_TIMESTAMP_ERROR
            GET ${XCP_CONFIG_JSON} configurations ${XCP_CONFIG_INDEX} protocol_layer timestamp size)
        if(NOT XCP_CFG_TIMESTAMP_ERROR)
            set(XCP_DAQ_TIMESTAMP_SUPPORTED_DERIVED ON)

            # This branch, and so the BYTE/WORD/DWORD -> 1/2/4 mapping inside it, is unexercised by
            # the test suite as shipped: XCP_CFG_TIMESTAMP_ERROR is set for every element of
            # config/xcp.json's own "configurations", which declares no protocol_layer.timestamp
            # block, so XCP_CFG_TIMESTAMP_ERROR is always truthy here and this body never runs --
            # confirmed by changing WORD's 2 to 3, which the suite does not catch. It is still
            # needed: an integrator who adds a protocol_layer.timestamp block to their own
            # -DXCP_CONFIG_FILEPATH (or grows one into config/xcp.json) exercises it for real, and
            # its result reaches the actual build through XCP_DAQ_TIMESTAMP_SIZE's
            # target_compile_definitions below. Kept, not deleted; see also
            # script/header_cfg.h.jinja2's copy of this same mapping, unexercised the same way for
            # the same reason.
            if(XCP_CFG_TIMESTAMP_SIZE STREQUAL "BYTE")
                set(XCP_CFG_TIMESTAMP_WIRE_SIZE 1)
            elseif(XCP_CFG_TIMESTAMP_SIZE STREQUAL "WORD")
                set(XCP_CFG_TIMESTAMP_WIRE_SIZE 2)
            elseif(XCP_CFG_TIMESTAMP_SIZE STREQUAL "DWORD")
                set(XCP_CFG_TIMESTAMP_WIRE_SIZE 4)
            else()
                message(FATAL_ERROR
                    "configurations[${XCP_CONFIG_INDEX}].protocol_layer.timestamp.size '${XCP_CFG_TIMESTAMP_SIZE}' in ${XCP_CONFIG_FILEPATH} is not one of BYTE, WORD, DWORD")
            endif()

            if(XCP_CFG_TIMESTAMP_WIRE_SIZE GREATER XCP_DAQ_TIMESTAMP_SIZE_DERIVED)
                set(XCP_DAQ_TIMESTAMP_SIZE_DERIVED ${XCP_CFG_TIMESTAMP_WIRE_SIZE})
            endif()
        endif()
    endforeach()
endif()

# Whether the PAG commands are compiled in follows from whether the configuration declares a
# segment, which is the rule the generated Xcp_Cfg.h states and the README documents. Deriving it
# here rather than defaulting it means the default build of a configuration that declares one
# actually answers those commands: a fixed default of STD_OFF silently compiled all eight out and
# answered ERR_CMD_UNKNOWN, since nothing on the library's include path pulls in Xcp_Cfg.h to
# supply the value instead.
#
# The three cache entries below are *derived* from XCP_CONFIG_FILEPATH, and all three have to stay
# derived. option(), and set(... CACHE ...) without FORCE, both do nothing at all once the entry
# exists -- so the first configure latched a value that the configuration could no longer move.
# Adding a "timestamp" block to the configuration and re-configuring in the same build directory
# left XCP_DAQ_TIMESTAMP_SUPPORTED at OFF and XCP_DAQ_TIMESTAMP_SIZE at 0, while
# generated/CMakeLists.txt -- which does DEPEND on that same file -- regenerated Xcp_Cfg.c with
# timestampType = FOUR_BYTE in it. That is exactly the mixed build the comments below say this
# derivation exists to prevent: the slave reports timestamp support and accepts the mode bit while
# the code that would transmit it is compiled out. Only a fresh build directory gave the right
# answer, and nothing said so.
#
# A bare FORCE would fix that and break the documented override, because FORCE also overwrites a -D
# given on the very command line that asked for it. So the derived value is shadowed in an INTERNAL
# entry: while the visible entry still holds what this project last derived, it is this project's to
# update; the moment it holds anything else, an integrator put it there and it is left alone.
#
# The one case this cannot distinguish is an explicit -D that agrees with the derivation; it is
# indistinguishable from the derivation itself and will be followed if the configuration later
# changes. Re-passing the -D pins it again, which is the same gesture that set it in the first
# place.
function(xcp_derive_from_configuration name type derived docstring)
    set(shadow ${name}_DERIVED_LAST)

    if(DEFINED ${shadow})
        set(baseline "${${shadow}}")
    else()
        # First configure after this shadow entry was introduced, in a build directory that already
        # has the visible entry. Nothing records whether it was derived or overridden, so an entry
        # that disagrees with the derivation is given the benefit of the doubt and treated as an
        # override; from the next configure on, the shadow answers the question properly.
        set(baseline "${derived}")
    endif()

    if((NOT DEFINED ${name}) OR ("${${name}}" STREQUAL "${baseline}"))
        set(${name} "${derived}" CACHE ${type} "${docstring}" FORCE)
    else()
        # An override keeps its value but still gets the type and help string it would have had:
        # a -D on the command line lands in the cache as UNINITIALIZED, and simply skipping the
        # set() above would leave it that way -- untyped in cmake-gui, undocumented in
        # CMakeCache.txt, which is what option() used to fix on the way past.
        set(${name} "${${name}}" CACHE ${type} "${docstring}" FORCE)
    endif()

    set(${shadow} "${derived}" CACHE INTERNAL
        "what ${name} was last derived from XCP_CONFIG_FILEPATH; see xcp_derive_from_configuration")
endfunction()

# A BOOL cache entry, like every other switch here, so that -DXCP_PAGING_SUPPORTED=ON does what a
# reader of the others would expect. The AUTOSAR STD_ON/STD_OFF spelling is applied where the
# definition reaches the compiler, as it is for ENABLE_DET.
xcp_derive_from_configuration(XCP_PAGING_SUPPORTED BOOL ${XCP_PAGING_SUPPORTED_DERIVED}
    "enables/disables the calibration page switching commands. Defaults to whether XCP_CONFIG_FILEPATH declares at least one segment; override only if you know why.")

# XCP_DAQ_TIMESTAMP_SUPPORTED/_SIZE need exactly the same treatment as XCP_PAGING_SUPPORTED above,
# and for the same reason: source/*.c includes Xcp.h, never the generated Xcp_Cfg.h, so nothing on
# the library's include path supplies these two. The generated header does define them from the
# configuration -- script/header_cfg.h.jinja2 now defines every derived macro before its first
# #include, so Xcp_Types.h's own fallbacks (0x00u/0u, present so the test harness's
# handle.define() has literal text to key off) no longer pre-empt them there -- but that only
# reaches a translation unit that includes Xcp_Cfg.h, which the library sources do not. Left
# undefined, or left to that fallback, a configuration declaring protocol_layer.timestamp would
# silently build with XCP_DAQ_TIMESTAMP_SUPPORTED == STD_OFF, gating Xcp_GetDaqTimestamp's
# declaration off entirely while Xcp_Cfg.c still set timestampType from the configuration. The
# README's "Building the sources outside this CMake project" states the same obligation for a
# build system that is not this one.
xcp_derive_from_configuration(XCP_DAQ_TIMESTAMP_SUPPORTED BOOL ${XCP_DAQ_TIMESTAMP_SUPPORTED_DERIVED}
    "enables/disables the data acquisition clock. Defaults to whether XCP_CONFIG_FILEPATH declares a protocol_layer.timestamp block; override only if you know why.")

# Not boolean, so a BOOL cache entry does not fit; STRING is the closest equivalent, matching
# XCP_PYTEST_ARGS above.
xcp_derive_from_configuration(XCP_DAQ_TIMESTAMP_SIZE STRING ${XCP_DAQ_TIMESTAMP_SIZE_DERIVED}
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

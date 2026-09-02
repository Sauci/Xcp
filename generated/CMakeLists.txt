# The -schema flag makes bsw_code_gen validate the configuration before it generates anything, so a
# malformed or stale xcp.json fails the build with a schema error rather than producing code that
# fails to compile -- or, worse, compiles into a silently wrong module. Only this path is validated:
# test/conftest.py drives BSWCodeGen through its Python API instead of CMake, and deliberately builds
# schema-invalid configurations (max_cto=1, max_dto=5) to exercise Xcp_Init's own runtime checks.

add_custom_command(OUTPUT
    ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.c
    ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.h
    DEPENDS ${XCP_CONFIG_FILEPATH}
        ${PROJECT_SOURCE_DIR}/config/xcp.schema.json
        ${PROJECT_SOURCE_DIR}/script/header_cfg.h.jinja2
        ${PROJECT_SOURCE_DIR}/script/source_cfg.c.jinja2
    COMMAND bsw_code_gen
    -source_cfg=${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.c
    -header_cfg=${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.h
    -schema ${PROJECT_SOURCE_DIR}/config/xcp.schema.json
    -template_directory ${PROJECT_SOURCE_DIR}/script
    ${XCP_CONFIG_FILEPATH}
    COMMENT "generating configuration source files")

add_library(Xcp_Cfg STATIC ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.c)

target_include_directories(Xcp_Cfg
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE ${PROJECT_SOURCE_DIR}/interface
    PRIVATE ${AUTOSAR_STD_HEADER_PATH}
    PUBLIC $<$<BOOL:${XCP_ENABLE_TEST}>:${PROJECT_SOURCE_DIR}/test/stub>)

add_custom_command(OUTPUT
        ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Rt.c
        ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Rt.h
        DEPENDS ${XCP_CONFIG_FILEPATH}
        ${PROJECT_SOURCE_DIR}/config/xcp.schema.json
        ${PROJECT_SOURCE_DIR}/script/header_rt.h.jinja2
        ${PROJECT_SOURCE_DIR}/script/source_rt.c.jinja2
        COMMAND bsw_code_gen
        -source_rt=${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Rt.c
        -header_rt=${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Rt.h
        -schema ${PROJECT_SOURCE_DIR}/config/xcp.schema.json
        -template_directory ${PROJECT_SOURCE_DIR}/script
        ${XCP_CONFIG_FILEPATH}
        COMMENT "generating runtime configuration source files")

add_library(Xcp_Rt STATIC ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Rt.c)

target_include_directories(Xcp_Rt
        PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}
        PRIVATE ${PROJECT_SOURCE_DIR}/interface
        PRIVATE ${AUTOSAR_STD_HEADER_PATH}
        PUBLIC $<$<BOOL:${XCP_ENABLE_TEST}>:${PROJECT_SOURCE_DIR}/test/stub>)

if (${ENABLE_PC_LINT})
    add_pc_lint_target(NAME Xcp_Cfg
        DEPENDS Xcp_Cfg.c Xcp_Cfg.h
        OUTPUT_LOG ${PROJECT_SOURCE_DIR}/${PROJECT_NAME}_Cfg.lnt.log
        EXCLUDE_DIRECTORIES
        ${PROJECT_SOURCE_DIR}/interface
        ${AUTOSAR_STD_HEADER_PATH}
        OPTION_FILES
        ${PROJECT_SOURCE_DIR}/extern/lint/MISRA${MISRA_C_VERSION}.lnt
        ${PROJECT_SOURCE_DIR}/config/Xcp.lnt)

    add_pc_lint_target(NAME Xcp_Rt
            DEPENDS Xcp_Rt.c Xcp_Rt.h
            OUTPUT_LOG ${PROJECT_SOURCE_DIR}/${PROJECT_NAME}_Rt.lnt.log
            EXCLUDE_DIRECTORIES
            ${PROJECT_SOURCE_DIR}/interface
            ${AUTOSAR_STD_HEADER_PATH}
            OPTION_FILES
            ${PROJECT_SOURCE_DIR}/extern/lint/MISRA${MISRA_C_VERSION}.lnt
            ${PROJECT_SOURCE_DIR}/config/Xcp.lnt)
endif ()

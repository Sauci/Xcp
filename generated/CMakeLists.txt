add_custom_command(OUTPUT
    ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.c
    ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.h
    DEPENDS ${XCP_CONFIG_FILEPATH}
    ${PROJECT_SOURCE_DIR}/script/header.h.jinja2
    ${PROJECT_SOURCE_DIR}/script/source.c.jinja2
    COMMAND ${PYTHON_EXECUTABLE} -m bsw_code_gen
    -template_directory ${PROJECT_SOURCE_DIR}/script
    ${XCP_CONFIG_FILEPATH}
    ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.c
    ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.h
    COMMENT "generating configuration source files")

add_library(Xcp_Cfg STATIC ${CMAKE_CURRENT_SOURCE_DIR}/Xcp_Cfg.c)

target_include_directories(Xcp_Cfg
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
endif ()

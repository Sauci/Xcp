add_executable(main main.c)

add_library(Xcp_PBcfg_ ${CMAKE_BINARY_DIR}/Xcp_PBcfg.c)
target_include_directories(Xcp_PBcfg_
    PUBLIC ${CMAKE_BINARY_DIR}
    PUBLIC ${CMAKE_SOURCE_DIR}/interface
    PUBLIC ${CMAKE_SOURCE_DIR}/test/stub)

target_link_libraries(main
    PUBLIC Xcp
    PUBLIC Xcp_PBcfg_)

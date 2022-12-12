add_executable(main main.c)

target_link_libraries(main
    PUBLIC Xcp
    PUBLIC Xcp_Cfg
    PUBLIC Xcp_Rt)

target_include_directories(main
    PUBLIC ${CMAKE_SOURCE_DIR}/generated)
#!/bin/sh

result=0
mkdir -p build
cd build
cmake .. -DXCP_ENABLE_TEST=ON
make all
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/project/build" ctest -V
result=$?
gcov _cffi_xcp.c
exit $result

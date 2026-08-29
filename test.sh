#!/bin/sh

result=0
mkdir -p build
cd build
cmake .. -DXCP_ENABLE_TEST=ON
make all
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/project/build" ctest -V
result=$?
for d in _cffi_xcp_*/usr/project/source; do
    [ -d "$d" ] || continue
    gcov "$d"/Xcp.c "$d"/Xcp_Std.c "$d"/Xcp_Cal.c "$d"/Xcp_Pag.c "$d"/Xcp_Daq.c
done
exit $result

#!/bin/sh

result=0
mkdir -p build
cd build
cmake .. -DXCP_ENABLE_TEST=ON
make all
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/project/build" ctest -V
result=$?
for f in Xcp.c Xcp_Std.c Xcp_Cal.c Xcp_Pag.c Xcp_Daq.c; do
    n=${f%.c}
    paths=""
    for d in _cffi_xcp_*/usr/project/source; do
        [ -f "$d/$n.gcno" ] || continue
        paths="$paths $d/$f"
    done
    [ -n "$paths" ] && gcov $paths
done
exit $result

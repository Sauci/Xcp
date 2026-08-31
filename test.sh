#!/bin/sh

result=0
mkdir -p build
cd build || exit 1

# A configure or build failure has to fail this script. ctest on the CMake in this image exits 0
# when it finds no tests to run, and --no-tests=error only exists from CMake 3.18, so without
# these three checks a branch that does not compile reports a green build having run nothing.
cmake .. -DXCP_ENABLE_TEST=ON || exit 1
make all || exit 1

if ctest -N | grep -q 'Total Tests: 0'; then
    echo 'test.sh: no tests were registered, refusing to report success' >&2
    exit 1
fi

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

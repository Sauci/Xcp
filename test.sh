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

# The suite compiles the sources once per distinct generated runtime, so each source has profile
# data spread over several module directories and no single one exercises every branch. gcov
# writes its output named after the source, into the working directory, so handing it all of
# them at once just leaves the last to overwrite the rest -- the coverage reported was one
# module's, not the union. Merge the profiles first, then run gcov on the merged set.
merged=gcov_merged
rm -rf "$merged"

for d in _cffi_xcp_*/usr/project/source; do
    [ -d "$d" ] || continue
    if [ ! -d "$merged" ]; then
        cp -r "$d" "$merged" || exit 1
    else
        gcov-tool merge "$merged" "$d" -o "$merged.tmp" >/dev/null 2>&1 &&
            rm -rf "$merged" && mv "$merged.tmp" "$merged"
    fi
done

# gcov-tool merge emits only the .gcda profiles, so pair them with the notes from any one of the
# merged directories: every module compiles the same sources with the same flags, so the notes
# are interchangeable and gcov accepts the pairing.
if [ -d "$merged" ]; then
    for d in _cffi_xcp_*/usr/project/source; do
        [ -d "$d" ] && cp "$d"/*.gcno "$merged/" 2>/dev/null && break
    done

    for f in Xcp.c Xcp_Std.c Xcp_Cal.c Xcp_Pag.c Xcp_Daq.c; do
        [ -f "$merged/${f%.c}.gcno" ] && (cd "$merged" && gcov "$f") && cp "$merged/$f.gcov" .
    done
fi

exit $result

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
        # Failing quietly here would leave $merged holding the first module's profile, which then
        # gets reported as though it were the union -- the exact defect this merge exists to fix.
        if ! gcov-tool merge "$merged" "$d" -o "$merged.tmp"; then
            echo "test.sh: gcov-tool merge failed for $d; coverage would be one module's, not the union" >&2
            exit 1
        fi
        rm -rf "$merged" && mv "$merged.tmp" "$merged" || exit 1
    fi
done

# gcov-tool merge emits only the .gcda profiles, so pair them with the notes from any one of the
# merged directories: every module compiles the same sources with the same flags, so the notes
# are interchangeable and gcov accepts the pairing.
if [ -d "$merged" ]; then
    for d in _cffi_xcp_*/usr/project/source; do
        [ -d "$d" ] && cp "$d"/*.gcno "$merged/" 2>/dev/null && break
    done

    # One entry per translation unit in the Xcp target, written by CMake's file(GENERATE) from
    # $<TARGET_PROPERTY:Xcp,SOURCES>. Adding a source to add_library is enough; nothing here needs
    # touching. A missing or empty file means the generate step changed or failed, and silently
    # reporting no coverage would look exactly like a green run, so refuse instead.
    if [ ! -s xcp_sources.txt ]; then
        echo 'test.sh: xcp_sources.txt is missing or empty; cannot determine what to report coverage on' >&2
        exit 1
    fi

    # Consumed by the Codecov upload in .github/workflows/test.yml, so that it does not enumerate
    # the same set a third time.
    : > coverage_files.txt

    while read -r source; do
        [ -n "$source" ] || continue
        f=$(basename "$source")
        [ -f "$merged/${f%.c}.gcno" ] && (cd "$merged" && gcov "$f")

        if [ -f "$merged/$f.gcov" ]; then
            cp "$merged/$f.gcov" . && echo "./build/$f.gcov" >> coverage_files.txt
        else
            # Not fatal, and not new: Xcp_Pag.c has never produced a report here -- gcov rejects its
            # profile with "stamp mismatch with notes file", the multi-compile hazard documented in
            # test/conftest.py. Saying so out loud keeps the gap visible; the list this loop writes
            # is otherwise a short list that looks complete.
            echo "test.sh: no coverage report for $f, so it is absent from the upload" >&2
        fi
    done < xcp_sources.txt
fi

exit $result

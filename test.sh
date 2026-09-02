#!/bin/sh

result=0
mkdir -p build
cd build || exit 1

# A configure or build failure has to fail this script, and so does an empty test run: a branch
# that does not compile must not report a green build having run nothing. --no-tests=error makes
# ctest itself exit non-zero when no tests are registered, so a branch that does not compile is
# caught the same way a configure or build failure is, without a separate ctest -N pre-check.
cmake .. -DXCP_ENABLE_TEST=ON || exit 1
make all || exit 1

LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/project/build" ctest -V --no-tests=error
result=$?

# The suite compiles the sources once per distinct generated runtime, so each source has profile
# data spread over several module directories and no single one exercises every branch. gcov
# writes its output named after the source, into the working directory, so handing it all of
# them at once just leaves the last to overwrite the rest -- the coverage reported was one
# module's, not the union. Merge the profiles first, then run gcov on the merged set.
merged=gcov_merged
rm -rf "$merged"

# The seed matters, and not only as a starting value. gcov-tool merge emits .gcda profiles and no
# notes, so the .gcno files copied in afterwards come from this same directory, and a .gcda only
# pairs with the .gcno of the compile that produced it. Seeding from whichever directory sorts
# first is therefore a coin toss: XCP_PAGING_SUPPORTED is derived per test configuration, so most
# modules compile Xcp_Pag.c away to nothing and leave a 16-byte .gcno recording no functions. That
# is what kept Xcp_Pag.c out of the coverage report entirely. Seed from a module that instrumented
# the most translation units instead, so the notes describe every file the merged profile covers.
seed=
seed_profiles=-1

for d in _cffi_xcp_*/usr/project/source; do
    [ -d "$d" ] || continue
    profiles=$(ls "$d"/*.gcda 2>/dev/null | wc -l)
    if [ "$profiles" -gt "$seed_profiles" ]; then
        seed_profiles=$profiles
        seed=$d
    fi
done

if [ -z "$seed" ]; then
    echo 'test.sh: no profile directories found, so no coverage can be reported' >&2
    exit 1
fi

cp -r "$seed" "$merged" || exit 1

for d in _cffi_xcp_*/usr/project/source; do
    [ -d "$d" ] || continue
    [ "$d" = "$seed" ] && continue
    # Failing quietly here would leave $merged holding the seed module's profile, which then
    # gets reported as though it were the union -- the exact defect this merge exists to fix.
    if ! gcov-tool merge "$merged" "$d" -o "$merged.tmp"; then
        echo "test.sh: gcov-tool merge failed for $d; coverage would be one module's, not the union" >&2
        exit 1
    fi
    rm -rf "$merged" && mv "$merged.tmp" "$merged" || exit 1
done

# gcov-tool merge emits only the .gcda profiles, so restore the notes from the seed -- the one
# directory whose stamps the merged profiles carry.
if [ -d "$merged" ]; then
    cp "$seed"/*.gcno "$merged/" 2>/dev/null || true

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

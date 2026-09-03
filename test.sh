#!/bin/sh

result=0
mkdir -p build
cd build || exit 1

# _cffi_xcp_* module directories (test/conftest.py's MockGen) accumulate without bound across
# runs that reuse this build/ directory -- they reached 3017 directories (307 MB) against this
# container's 1024 file-descriptor limit during one sub-project, and are the documented common
# cause of transient pycparser/PLY, Jinja2 template-compilation and CFFI/distutils failures, each
# non-reproducing and each costing a full run. They also hold the .gcda profiles the coverage
# merge below reads, and gcov accumulates a binary's execution counts across runs rather than
# overwriting them, so leaving old modules in place makes the reported coverage cumulative since
# whenever build/ was last removed by hand, not a measurement of this run alone -- a deleted
# test's coverage keeps counting.
#
# Pruning here, before cmake/ctest regenerate what this run actually needs, fixes both: the
# modules are keyed by a content digest and rebuilt on demand (test/conftest.py's MockGen), so
# removing them is safe. This cannot move to the end of the script instead: the coverage merge
# below depends on the modules THIS run creates still being present once ctest finishes.
rm -rf _cffi_xcp_*

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
#
# The merge has to be done per source file, not once with a single seed for the whole tree (the
# first fix here, made for Xcp_Pag.c). A build-time macro -- XCP_DAQ_TIMESTAMP_SUPPORTED,
# XCP_PAGING_SUPPORTED, and so on -- gates functions in or out of a translation unit, so
# different test configurations compile some sources into genuinely different .gcno graphs.
# gcov-tool merge has no way to combine two of those: it does not error when asked to, it just
# silently keeps one side and drops the other. A single seed's notes therefore report whichever
# variant that one module happened to hold, for every file at once -- and there is no seed that
# is the right variant for every file simultaneously, because "right" is a per-file question.
# For Xcp_Daq.c the seed's variant lost that silent contest: the merged profile ended up
# carrying a different module's stamp than the seed's notes, and gcov refused the mismatch
# outright, reporting 0.00%. Xcp_DaqRuntime.c has the same two-variant split and was reporting
# 100% -- not because it merged correctly, but because the seed's variant happened to win.
#
# The second fix grouped each file's notes by content across every module that has them, and
# merged only the largest group -- an honest majority-variant figure instead of a silent 0%, but
# still a real cost: every OTHER group had compiled a structurally different, equally real version
# of the file, and its coverage was discarded outright, not folded in. Most test configurations
# declare no protocol_layer.timestamp block, so the largest group for both Xcp_Daq.c and
# Xcp_DaqRuntime.c was the timestamp-DISABLED compilation -- and every line inside
# #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) showed as '-', not compiled, rather than as
# uncovered. Xcp_DaqRuntime.c reported 100.00% that way: 100% of a compilation that contained none
# of the timestamp feature. It also degraded with every new build-time guard: each one splits the
# modules into more groups, the largest group shrinks, and more real code falls outside the number.
#
# gcov-tool still cannot merge structurally different groups' profiles into each other -- that is
# a property of the .gcno/.gcda binary format, not something this script can work around, and the
# grouping above still exists to identify those groups. What does not follow is that the other
# groups have to be thrown away. gcov's own .gcov *text* output keys every line to a physical
# source line number, and that number means the same thing regardless of which group produced it:
# line N in a timestamp-OFF compile's report and line N in a timestamp-ON compile's report
# describe the same line of Xcp_DaqRuntime.c, instrumented or not. So: group each file's notes by
# content as before, but run gcov on EVERY group instead of only the largest, and union the
# resulting per-group .gcov reports line by line (script/gcov_union.py, invoked below) -- summing
# a line's hit count across every group that has one, falling back to '#####' if some group
# instrumented the line without ever executing it, and to '-' only if no group instrumented it at
# all. Groups partition the usable modules (each module's .gcno hashes into exactly one group), so
# this sums a line's counts over every test configuration that ever compiled the file -- an actual
# union, not an approximation of one, because gcov's line-keyed text is exactly the granularity
# gcov-tool's binary merge cannot see.
merged=gcov_merged
rm -rf "$merged"
mkdir -p "$merged" || exit 1

# One entry per translation unit in the Xcp target, written by CMake's file(GENERATE) from
# $<TARGET_PROPERTY:Xcp,SOURCES>. Adding a source to add_library is enough; nothing here needs
# touching. A missing or empty file means the generate step changed or failed, and silently
# reporting no coverage would look exactly like a green run, so refuse instead.
if [ ! -s xcp_sources.txt ]; then
    echo 'test.sh: xcp_sources.txt is missing or empty; cannot determine what to report coverage on' >&2
    exit 1
fi

# Walked once and reused for every source file below, so the ~1600-entry module tree is scanned
# a constant number of times rather than once per file.
dirs_file="$merged.dirs"
: > "$dirs_file"
for d in _cffi_xcp_*/usr/project/source; do
    [ -d "$d" ] && echo "$d" >> "$dirs_file"
done

if [ ! -s "$dirs_file" ]; then
    echo 'test.sh: no profile directories found, so no coverage can be reported' >&2
    exit 1
fi

# Consumed by the Codecov upload in .github/workflows/test.yml, so that it does not enumerate
# the same set a third time.
: > coverage_files.txt

while read -r source; do
    [ -n "$source" ] || continue
    f=$(basename "$source")
    stem=${f%.c}
    notes="$stem.gcno"

    # Hash each module's notes for this file exactly once. Two modules that compiled it the same
    # way produce byte-identical .gcno except for the stamp (bytes 8-11: a per-compile value, not
    # a content checksum) -- excluded here, or every module would land in a group of its own,
    # real agreement and all. A directory where the file is absent, or where it compiled away to
    # a bare header recording no functions (~16 bytes, against thousands for a real compile -- 100
    # is a cut well clear of both), is not a variant to group; it is skipped so it cannot
    # masquerade as a group of its own, or even win on numbers (most configurations compile
    # Xcp_Pag.c away to nothing, so the empty stub would otherwise be the largest group, not the
    # smallest).
    hashes_file="$merged.hashes"
    : > "$hashes_file"
    while read -r d; do
        gcno="$d/$notes"
        [ -f "$gcno" ] || continue
        size=$(wc -c < "$gcno")
        [ "$size" -gt 100 ] || continue
        hash=$( { head -c 8 "$gcno"; tail -c +13 "$gcno"; } | md5sum)
        echo "${hash%% *} $d" >> "$hashes_file"
    done < "$dirs_file"

    if [ ! -s "$hashes_file" ]; then
        echo "test.sh: no usable .gcno for $f in any module, so it is absent from the upload" >&2
        continue
    fi

    total_usable=$(wc -l < "$hashes_file")
    uniq_hashes="$merged.uniq"
    awk '{print $1}' "$hashes_file" | sort -u > "$uniq_hashes"
    variants=$(wc -l < "$uniq_hashes" | tr -d ' ')

    variant_root="$merged/variants"
    rm -rf "$variant_root"
    mkdir -p "$variant_root" || exit 1

    # One line per group that made it to a .gcov report, collected while the loop below runs so
    # the union call after it can be a single command and the summary echo after that does not
    # have to recompute anything.
    gcov_list="$merged.gcovlist"
    : > "$gcov_list"
    summary_list="$merged.summary"
    : > "$summary_list"

    idx=0
    while read -r hash; do
        idx=$((idx + 1))
        group_file="$merged.group"
        awk -v h="$hash" '$1==h{print $2}' "$hashes_file" > "$group_file"
        group_size=$(wc -l < "$group_file")

        # Sum every module in THIS group's .gcda into one profile matching this group's (stamp
        # aside, identical) .gcno -- gcov-tool can do that much; what it cannot do is take it
        # further and fold that result into another group's, which compiled the file differently.
        # Repeated per group now, not just for the one that used to be picked as "the" group.
        acc="$merged.acc"
        rm -rf "$acc"
        base=
        while read -r d; do
            [ -n "$d" ] || continue
            if [ -z "$base" ]; then
                base=$d
                mkdir -p "$acc" || exit 1
                cp "$d/$stem.gcda" "$acc/" || exit 1
                continue
            fi
            other="$merged.other"
            rm -rf "$other" && mkdir -p "$other" || exit 1
            cp "$d/$stem.gcda" "$other/" || exit 1
            # Failing quietly here would leave $acc holding a partial merge, silently reported as
            # though it were the whole group's union -- the exact defect this per-file merge exists
            # to fix.
            if ! gcov-tool merge "$acc" "$other" -o "$acc.tmp"; then
                echo "test.sh: gcov-tool merge failed for $f in $d; coverage would be partial, not the group's union" >&2
                exit 1
            fi
            rm -rf "$acc" && mv "$acc.tmp" "$acc" || exit 1
        done < "$group_file"
        rm -rf "$merged.other"

        # gcov-tool merge emits only the .gcda, carrying the stamp of its first argument -- $acc,
        # i.e. $base -- throughout the chain, so $base's own notes are the ones that still match
        # it. Each group gets its own directory so its .gcov does not overwrite another group's.
        vdir="$variant_root/$idx"
        mkdir -p "$vdir" || exit 1
        cp "$base/$notes" "$acc/" || exit 1
        mv "$acc/$stem.gcda" "$vdir/$stem.gcda" || exit 1
        mv "$acc/$notes" "$vdir/$notes" || exit 1
        rm -rf "$acc"

        (cd "$vdir" && gcov "$f") >/dev/null

        if [ -f "$vdir/$f.gcov" ]; then
            echo "$vdir/$f.gcov" >> "$gcov_list"
            echo "$group_size module(s)" >> "$summary_list"
        else
            # Not fatal to the source as a whole: the other groups can still be unioned. An I/O
            # hiccup in gcov itself is rare enough that losing one group's contribution is better
            # than losing the file's coverage entirely, but it is said out loud either way.
            echo "test.sh: no coverage report for $f from a $group_size-module group; excluded from the union" >&2
        fi
    done < "$uniq_hashes"

    if [ ! -s "$gcov_list" ]; then
        echo "test.sh: no coverage report for $f, so it is absent from the upload" >&2
        continue
    fi

    # $gcov_list has one path per line and none of them can contain whitespace (each is built
    # from $f, a basename out of xcp_sources.txt, under a numbered directory this script made),
    # so handing the substitution straight to the script as argv is safe.
    if ! python3 ../script/gcov_union.py -o "$merged/$f.gcov" $(cat "$gcov_list"); then
        echo "test.sh: coverage union failed for $f" >&2
        exit 1
    fi

    summary=
    while read -r line; do
        if [ -z "$summary" ]; then
            summary="$line"
        else
            summary="$summary; $line"
        fi
    done < "$summary_list"
    echo "test.sh: $f coverage is the UNION of $variants variant(s) across $total_usable usable module(s): $summary" >&2

    # gcov_union.py either wrote $merged/$f.gcov or this script already exited above, so its
    # presence here is not conditional the way a single gcov invocation's used to be.
    cp "$merged/$f.gcov" . && echo "./build/$f.gcov" >> coverage_files.txt
done < xcp_sources.txt

rm -f "$merged.dirs" "$merged.hashes" "$merged.group" "$merged.uniq" "$merged.gcovlist" "$merged.summary"

exit $result

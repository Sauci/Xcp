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
#
# The merge has to be done per source file, not once with a single seed for the whole tree (the
# previous fix, made for Xcp_Pag.c). A build-time macro -- XCP_DAQ_TIMESTAMP_SUPPORTED,
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
# So: group each file's notes by content across every module that has them, and merge only the
# largest group. That is a real cost, not a free generalisation -- the reported coverage is the
# union across one compilation variant, not across every variant the suite exercises -- but it
# is the best gcov can do, since there is no tool-level way to combine profiles from
# structurally different compilations. An honest majority-variant figure beats a silent 0%.
#
# Read every percentage this loop prints as "one variant's coverage", never as the suite's. The
# cost is larger than the paragraph above makes it sound, in two ways worth stating outright.
#
# The winning variant is the majority one, which is not the same as the complete one. Most test
# configurations declare no protocol_layer.timestamp block, so the largest group for both
# Xcp_Daq.c and Xcp_DaqRuntime.c is the timestamp-DISABLED compilation -- and every line inside
# #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) then shows as '-', not compiled, rather than as
# uncovered. Xcp_DaqRuntime.c reports 100.00% that way: 100% of a compilation that contains none
# of the timestamp feature. A clean-looking figure here is not evidence that a feature is covered;
# it may be evidence that the feature was compiled out of the variant being measured.
#
# Nor is the byte size a reliable proxy for completeness: more than one macro gates these files
# (XCP_PAGING_SUPPORTED as well as the two timestamp ones), so a larger .gcno does not mean the
# feature you care about is in it. Size is an identity, not a ranking. That is all the line below
# uses it for: two runs whose percentages agree may not have measured the same code, and the size
# is what says so. The variant count beside it says how much coverage exists that no selection
# rule here can fold in -- anything above 1 is real coverage left on the floor.
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

    # The largest group of modules that compiled this file identically -- the closest thing to
    # "coverage across the whole suite" that gcov can combine. Every other group compiled a
    # structurally different version of this file; its coverage is real but cannot be folded in.
    top=$(awk '{print $1}' "$hashes_file" | sort | uniq -c | sort -k1,1nr | awk 'NR==1{print $2}')
    group_file="$merged.group"
    awk -v h="$top" '$1==h{print $2}' "$hashes_file" > "$group_file"
    group_size=$(wc -l < "$group_file")
    total_usable=$(wc -l < "$hashes_file")
    # Which variant won, not just how many modules voted for it. The byte size of the winning
    # .gcno is the only cheap handle on "which compilation of this file was measured": a smaller
    # one means fewer functions, i.e. a build-time gate compiled part of the file away, and the
    # percentage that follows is 100% of what was left. variants says how much was not folded in
    # -- anything above 1 means some real coverage exists that no rule here can reach.
    variants=$(awk '{print $1}' "$hashes_file" | sort -u | wc -l | tr -d ' ')
    top_notes=$(head -n 1 "$group_file")
    top_bytes=$(wc -c < "$top_notes/$notes" | tr -d ' ')
    # Said out loud regardless of outcome, success included, so a future reader can see the
    # trade this merge makes rather than infer it from the coverage percentage alone.
    echo "test.sh: $f coverage is ONE variant's, not the union: merged from $group_size of $total_usable module(s) sharing a ${top_bytes}-byte $notes, of $variants variant(s) present" >&2

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
    # i.e. $base -- throughout the chain, so $base's own notes are the ones that still match it.
    cp "$base/$notes" "$acc/" || exit 1
    mv "$acc/$stem.gcda" "$merged/$stem.gcda" || exit 1
    mv "$acc/$notes" "$merged/$notes" || exit 1
    rm -rf "$acc"

    [ -f "$merged/$notes" ] && (cd "$merged" && gcov "$f")

    if [ -f "$merged/$f.gcov" ]; then
        cp "$merged/$f.gcov" . && echo "./build/$f.gcov" >> coverage_files.txt
    else
        # Not fatal: a file can still fail to produce a report even from a same-variant group
        # (an I/O hiccup in gcov itself, say). Saying so out loud keeps the gap visible; the list
        # this loop writes is otherwise a short list that looks complete.
        echo "test.sh: no coverage report for $f, so it is absent from the upload" >&2
    fi
done < xcp_sources.txt

rm -f "$merged.dirs" "$merged.hashes" "$merged.group"

exit $result

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests script/gcov_union.py, the line-by-line merge that lets test.sh report coverage as the
union across every compilation variant of a source file instead of discarding all but one.

This module is not a test of the DUT (the Xcp C sources): it is a test of a coverage-reporting
tool, and a merger that reports plausible-but-wrong numbers is worse than no merger at all -- a
wrong 100% hides untested code as effectively as an honest one, but looks fine. Every case gcov's
per-line count field can take -- a number, '#####' (instrumented, never executed), or '-' (not
instrumented) -- is exercised alone, in combination with each of the others, and across inputs
that do not even cover the same set of line numbers, since real variants can (a module that failed
to compile past an earlier line, or a hand-built fixture in these tests) disagree on extent without
that being a bug.

script/gcov_union.py is a plain script, not a package under test/, so it is not on sys.path the
way the rest of the suite's dependencies are; the import below adds script/ to sys.path itself
rather than relying on the --script_directory CLI option (BSWCodeGen's own use of that option,
in .conftest, points it at the *.jinja2 templates, not at Python modules), so this file does not
depend on anything test.sh's cmake/ctest invocation had to have configured beyond running pytest
at all.
"""

import os
import sys

_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'script')
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import pytest

import gcov_union  # noqa: E402  (import follows the sys.path fix-up above, deliberately)


def gcov_text(source, body_lines, extra_header=()):
    """Build a synthetic .gcov file's content.

    body_lines: a sequence of (count_field, text) pairs, becoming 1-indexed source lines.
    extra_header: additional ':0:'-numbered header lines, inserted after 'Source:', the way real
    gcov output also carries 'Graph:', 'Data:', 'Runs:' and 'Programs:' lines.
    """
    header = [f"        -:    0:Source:{source}"]
    header.extend(f"        -:    0:{line}" for line in extra_header)
    body = [f"{count:>9}:{i:>5}:{text}" for i, (count, text) in enumerate(body_lines, start=1)]
    return "\n".join(header + body) + "\n"


# --- the five scenarios the brief calls out by name -----------------------------------------

def test_numeric_in_one_variant_and_dash_in_another_keeps_the_numeric_count():
    """A line inside a build-time guard: instrumented (and hit) in the variant that compiles the
    guarded code in, absent -- not merely uncovered, genuinely not instrumented -- in the variant
    that compiles it out. The union must report the real count, not fall back to '-' just because
    one of the two inputs did."""
    a = gcov_text("Xcp_DaqRuntime.c", [("3", "    do_thing();")])
    b = gcov_text("Xcp_DaqRuntime.c", [("-", "    do_thing();")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "        3:    1:    do_thing();" in merged.splitlines()


def test_hash_in_one_variant_and_numeric_in_another_keeps_the_numeric_count():
    """The reverse pairing: one variant instrumented the line and never hit it ('#####'), the
    other instrumented it and did. A variant that never ran the line contributes nothing, but
    must not downgrade a real count to 'uncovered'."""
    a = gcov_text("Xcp_DaqRuntime.c", [("#####", "    do_thing();")])
    b = gcov_text("Xcp_DaqRuntime.c", [("7", "    do_thing();")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "        7:    1:    do_thing();" in merged.splitlines()


def test_hash_in_every_variant_stays_hash():
    """Instrumented in every variant, executed in none: real, reportable dead code -- must not
    quietly become '-' (which would claim the line was never even compiled in)."""
    a = gcov_text("Xcp_DaqRuntime.c", [("#####", "    dead();")])
    b = gcov_text("Xcp_DaqRuntime.c", [("#####", "    dead();")])
    c = gcov_text("Xcp_DaqRuntime.c", [("#####", "    dead();")])
    merged = gcov_union.union_gcov_texts([a, b, c])
    assert "    #####:    1:    dead();" in merged.splitlines()


def test_dash_in_every_variant_stays_dash():
    """Not instrumented anywhere -- a comment, a brace, a line no configuration ever compiles in
    -- must not be promoted into looking like measured-but-uncovered code."""
    a = gcov_text("Xcp_DaqRuntime.c", [("-", "    /* comment */")])
    b = gcov_text("Xcp_DaqRuntime.c", [("-", "    /* comment */")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "        -:    1:    /* comment */" in merged.splitlines()


def test_differing_line_counts_between_inputs_does_not_crash_or_drop_lines():
    """One variant's report can be longer than another's -- test.sh's own gcov invocations never
    produce this for a genuine pair (same physical source file), but this merger is the safety net
    for the case, not gcov's promise that it cannot happen. Every line number present in either
    input must survive into the union, including the ones the shorter input does not have."""
    short = gcov_text("Xcp_DaqRuntime.c", [
        ("-", "int f(void)"),
        ("-", "{"),
    ])
    long = gcov_text("Xcp_DaqRuntime.c", [
        ("1", "int f(void)"),
        ("-", "{"),
        ("4", "    g();"),
        ("-", "}"),
    ])
    merged = gcov_union.union_gcov_texts([short, long])
    lines = merged.splitlines()
    assert "        1:    1:int f(void)" in lines
    assert "        4:    3:    g();" in lines
    assert "        -:    4:}" in lines
    # the shorter input's silence about lines 3-4 is not a vote for '-': only the longer input's
    # own values appear there, unaltered by the fact that the other input stopped short.


# --- summation, not just "numeric wins" ------------------------------------------------------

def test_two_numeric_variants_are_summed():
    """The rule is 'sum', not 'keep whichever variant has a number' -- distinct from the two
    single-numeric cases above. 3 hits in one variant's tests and 4 in another's is 7 hits
    across the suite, the same as if one build had been able to run every test itself."""
    a = gcov_text("Xcp_DaqRuntime.c", [("3", "    do_thing();")])
    b = gcov_text("Xcp_DaqRuntime.c", [("4", "    do_thing();")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "        7:    1:    do_thing();" in merged.splitlines()


def test_numeric_beats_hash_and_dash_together():
    """Three-way combination, to pin the priority order (numeric > '#####' > '-') as one rule
    rather than three separately-passing pairwise rules that could still disagree on a three-way
    tie in some other implementation."""
    a = gcov_text("Xcp_DaqRuntime.c", [("-", "    x();")])
    b = gcov_text("Xcp_DaqRuntime.c", [("#####", "    x();")])
    c = gcov_text("Xcp_DaqRuntime.c", [("5", "    x();")])
    merged = gcov_union.union_gcov_texts([a, b, c])
    assert "        5:    1:    x();" in merged.splitlines()


def test_three_numeric_variants_sum_across_all_of_them():
    a = gcov_text("Xcp_DaqRuntime.c", [("1", "    x();")])
    b = gcov_text("Xcp_DaqRuntime.c", [("2", "    x();")])
    c = gcov_text("Xcp_DaqRuntime.c", [("3", "    x();")])
    merged = gcov_union.union_gcov_texts([a, b, c])
    assert "        6:    1:    x();" in merged.splitlines()


# --- the '*' partial-block marker --------------------------------------------------------------
#
# gcov appends '*' to a numeric count, with no extra flag needed to ask for it, whenever a line
# compiles to more than one basic block (a ternary, a short-circuit && / ||, ...) and at least one
# of those blocks never ran even though the line's own count is nonzero -- confirmed against this
# project's own real output: source/Xcp_Daq.c has
# 'return (boolean)((daqListNumber < Xcp_Ptr->general->daqCount) ? TRUE : FALSE);', and one
# variant's real .gcov reported it as '132*'. A merger that cannot parse that field at all is
# the failure mode the brief warns about in the most literal sense: it does not produce a wrong
# number, it crashes -- but only because this case was not in the brief's own list of scenarios to
# test. It is real, so it is tested here.

def test_starred_count_with_dash_keeps_the_star():
    """Only one variant has data for this line, and it is starred: no other variant offers proof
    every block on the line ran, so the union has none to fall back on either."""
    a = gcov_text("Xcp_DaqRuntime.c", [("5*", "    x = a ? b : c;")])
    b = gcov_text("Xcp_DaqRuntime.c", [("-", "    x = a ? b : c;")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "       5*:    1:    x = a ? b : c;" in merged.splitlines()


def test_starred_and_unstarred_numeric_sums_and_drops_the_star():
    """The variant reporting '3' unstarred is itself proof that every block belonging to this
    source line ran at least once in its own tests -- the same code, the same block
    decomposition, since the line is not itself macro-gated. That proof does not stop being true
    because a DIFFERENT variant's tests happened not to exercise every block, so the union must
    not keep claiming partial coverage once one variant has already disproved it."""
    a = gcov_text("Xcp_DaqRuntime.c", [("5*", "    x = a ? b : c;")])
    b = gcov_text("Xcp_DaqRuntime.c", [("3", "    x = a ? b : c;")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "        8:    1:    x = a ? b : c;" in merged.splitlines()


def test_two_starred_numeric_variants_sum_and_keep_the_star():
    """Every numeric contributor is starred, so there is no unstarred proof anywhere to justify
    dropping it -- summing is still correct (five hits is five hits, however each variant's own
    blocks split), but the union stays conservative about whether every block was ever exercised
    together."""
    a = gcov_text("Xcp_DaqRuntime.c", [("5*", "    x = a ? b : c;")])
    b = gcov_text("Xcp_DaqRuntime.c", [("3*", "    x = a ? b : c;")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "       8*:    1:    x = a ? b : c;" in merged.splitlines()


def test_starred_count_beats_hash():
    a = gcov_text("Xcp_DaqRuntime.c", [("5*", "    x = a ? b : c;")])
    b = gcov_text("Xcp_DaqRuntime.c", [("#####", "    x = a ? b : c;")])
    merged = gcov_union.union_gcov_texts([a, b])
    assert "       5*:    1:    x = a ? b : c;" in merged.splitlines()


# --- header / source-text handling ------------------------------------------------------------

def test_source_header_is_preserved_from_the_first_input():
    a = gcov_text("Xcp_DaqRuntime.c", [("1", "int f(void)")],
                  extra_header=["Graph:Xcp_DaqRuntime.gcno", "Data:Xcp_DaqRuntime.gcda", "Runs:1"])
    b = gcov_text("Xcp_DaqRuntime.c", [("2", "int f(void)")])
    merged = gcov_union.union_gcov_texts([a, b])
    header = merged.splitlines()[:4]
    assert header == [
        "        -:    0:Source:Xcp_DaqRuntime.c",
        "        -:    0:Graph:Xcp_DaqRuntime.gcno",
        "        -:    0:Data:Xcp_DaqRuntime.gcda",
        "        -:    0:Runs:1",
    ]


def test_source_text_for_a_line_only_one_variant_has_is_passed_through_unchanged():
    short = gcov_text("Xcp_DaqRuntime.c", [("1", "int f(void)")])
    long = gcov_text("Xcp_DaqRuntime.c", [("1", "int f(void)"), ("-", "    /* only in long */")])
    merged = gcov_union.union_gcov_texts([short, long])
    assert "        -:    2:    /* only in long */" in merged.splitlines()


# --- refusing to guess, rather than silently merging the wrong thing --------------------------

def test_mismatched_source_names_are_refused():
    a = gcov_text("Xcp_DaqRuntime.c", [("1", "int f(void)")])
    b = gcov_text("Xcp_Daq.c", [("1", "int f(void)")])
    with pytest.raises(gcov_union.GcovUnionError, match="different sources"):
        gcov_union.union_gcov_texts([a, b])


def test_disagreeing_source_text_at_the_same_line_number_is_refused():
    """Same file name, but line 1's text does not match -- the strongest signal available that
    two reports do not actually describe the same compile of the same file, so this must not be
    resolved by picking one side: that is exactly the kind of plausible-looking wrong answer the
    brief warns is worse than the narrow-but-honest report this replaces."""
    a = gcov_text("Xcp_DaqRuntime.c", [("1", "int f(void)")])
    b = gcov_text("Xcp_DaqRuntime.c", [("1", "int g(void)")])
    with pytest.raises(gcov_union.GcovUnionError, match="different source text"):
        gcov_union.union_gcov_texts([a, b])


def test_empty_input_list_is_refused():
    with pytest.raises(gcov_union.GcovUnionError):
        gcov_union.union_gcov_texts([])


def test_malformed_line_is_refused_rather_than_misparsed():
    with pytest.raises(gcov_union.GcovUnionError):
        gcov_union.union_gcov_texts(["not a gcov line at all"])


# --- coverage_summary, the number test.sh's console output shows per source -------------------

def test_coverage_summary_counts_executed_and_instrumented_lines():
    merged = "\n".join([
        "        -:    0:Source:Xcp_DaqRuntime.c",
        "        -:    1:not instrumented",
        "        5:    2:executed",
        "    #####:    3:instrumented, never executed",
        "        2:    4:executed",
        "",
    ])
    executed, instrumented = gcov_union.coverage_summary(merged)
    assert (executed, instrumented) == (2, 3)


def test_coverage_summary_of_an_all_dash_file_is_zero_of_zero():
    merged = "\n".join([
        "        -:    0:Source:empty.c",
        "        -:    1:/* nothing compiled in from any variant */",
        "",
    ])
    assert gcov_union.coverage_summary(merged) == (0, 0)


# --- the CLI test.sh actually invokes -----------------------------------------------------------

def test_main_writes_the_merged_file_and_reports_the_percentage(tmp_path, capsys):
    a = tmp_path / "a.gcov"
    b = tmp_path / "b.gcov"
    out = tmp_path / "merged.gcov"
    a.write_text(gcov_text("Xcp_DaqRuntime.c", [("3", "x();"), ("-", "y();")]))
    b.write_text(gcov_text("Xcp_DaqRuntime.c", [("-", "x();"), ("#####", "y();")]))

    exit_code = gcov_union.main(["-o", str(out), str(a), str(b)])

    assert exit_code == 0
    assert out.read_text() == gcov_union.union_gcov_texts([a.read_text(), b.read_text()])
    captured = capsys.readouterr()
    assert "File 'Xcp_DaqRuntime.c'" in captured.out
    # 1 of 2 instrumented lines executed (x(): 3: y(): '#####') = 50.00%.
    assert "Lines executed:50.00% of 2" in captured.out


def test_main_refuses_to_write_a_file_for_mismatched_sources(tmp_path, capsys):
    a = tmp_path / "a.gcov"
    b = tmp_path / "b.gcov"
    out = tmp_path / "merged.gcov"
    a.write_text(gcov_text("Xcp_DaqRuntime.c", [("1", "x();")]))
    b.write_text(gcov_text("Xcp_Daq.c", [("1", "x();")]))

    exit_code = gcov_union.main(["-o", str(out), str(a), str(b)])

    assert exit_code == 1
    assert not out.exists()
    assert "different sources" in capsys.readouterr().err

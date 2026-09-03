#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Union multiple .gcov reports for the SAME source file into one merged report.

Background
----------
test.sh's coverage block compiles this project's DUT sources once per distinct test
configuration. A build-time macro (XCP_DAQ_TIMESTAMP_SUPPORTED, XCP_PAGING_SUPPORTED, and so on)
gates functions in or out of a translation unit, so different configurations produce structurally
different compiles of the same source file -- different .gcno graphs that gcov-tool cannot merge
at the profile level (see the comment above the coverage block in test.sh for the full story of
why, and what was tried before this).

What CAN be combined is the human-readable .gcov *text* those structurally different compiles
produce: gcov keys every line of that text to a physical source line number, and line N in one
compile's report is the same source line as line N in another's, whether or not that particular
compile instrumented it. This module unions per-variant reports line by line:

    * if one or more variants report a numeric hit count for a line, the merged count is the SUM
      of every numeric count reported for that line -- a line hit twice in one variant's tests and
      three times in another's was hit five times across the two;
    * otherwise, if one or more variants report '#####' (instrumented, never executed), the merged
      line is instrumented-but-uncovered;
    * otherwise no variant instrumented the line at all, so it stays '-'.

Callers are expected to pass reports for groups that partition a disjoint set of test-config
modules (test.sh's per-file .gcno content hash does exactly that), so this is a true union, not an
approximation: no module is counted twice, and every module that ever compiled the file in
question contributes to the total.

A numeric count can carry a trailing '*' (e.g. '132*'): gcov's own plain-text output appends it,
with no extra flag needed to request it, whenever a line compiles to more than one basic block
(a ternary, a short-circuit && / ||, ...) and at least one of those blocks never ran, even though
the line as a whole shows a nonzero count. Summing the digits and dropping the '*' whenever ANY
contributing variant reports the line unstarred is deliberate, not an approximation: an unstarred
count from even one variant is that variant's own proof every block on the line ran at least once
in its tests, and since it is the same source line -- same code, same block decomposition -- that
proof carries over to the union. Only when every variant that has a numeric count for the line
also has the '*' is there no such proof to fall back on, so the union conservatively keeps it
rather than assume blocks the data does not show were ever exercised together.

A line whose source text disagrees between two inputs at the same line number is refused rather
than silently resolved one way or another -- that almost certainly means the inputs are reports
for two different source files, and a merger that produces a plausible-looking wrong number is
worse than one that refuses to guess (see the module's own tests for why this matters as much as
the arithmetic does).
"""

import argparse
import sys
from typing import Dict, List, Optional, Sequence, Tuple

HEADER_LINENO = "0"
NOT_INSTRUMENTED = "-"
NEVER_EXECUTED = "#####"


class GcovUnionError(Exception):
    """Raised when inputs cannot be unioned honestly (e.g. mismatched sources or line text)."""


def _split_gcov_line(line: str) -> Tuple[str, str, str]:
    # gcov's own field widths vary by file (they widen to fit the largest count or line number
    # present), so splitting on fixed columns is not safe -- only the count-field/line-number/text
    # tricolon structure is guaranteed. maxsplit=2 keeps the source text intact even when it
    # itself contains ':' (a C ternary, a bitfield width, ...).
    parts = line.split(":", 2)
    if len(parts) != 3:
        raise GcovUnionError(f"not a gcov line (missing ':' fields): {line!r}")
    count_field, lineno_field, text = parts
    return count_field.strip(), lineno_field.strip(), text


def _parse_gcov(text: str, label: str) -> Tuple[List[str], str, Dict[int, Tuple[str, str]]]:
    """Parse one .gcov file's content into (header lines, Source: value, {lineno: (count, text)})."""
    header_lines: List[str] = []
    body: Dict[int, Tuple[str, str]] = {}
    source_name: Optional[str] = None
    for raw_line in text.splitlines():
        if raw_line == "":
            continue
        count_field, lineno_field, line_text = _split_gcov_line(raw_line)
        if lineno_field == HEADER_LINENO:
            header_lines.append(raw_line)
            if line_text.startswith("Source:"):
                source_name = line_text[len("Source:"):]
            continue
        try:
            lineno = int(lineno_field)
        except ValueError:
            raise GcovUnionError(f"{label}: non-numeric line number {lineno_field!r}")
        if lineno in body:
            raise GcovUnionError(f"{label}: duplicate line number {lineno}")
        body[lineno] = (count_field, line_text)
    if source_name is None:
        raise GcovUnionError(f"{label}: no 'Source:' header line found")
    return header_lines, source_name, body


def _merge_count_fields(fields: Sequence[str]) -> str:
    numeric_total = None
    any_starred = False
    any_unstarred = False
    saw_never_executed = False
    for field in fields:
        if field == NOT_INSTRUMENTED:
            continue
        if field == NEVER_EXECUTED:
            saw_never_executed = True
            continue
        starred = field.endswith("*")
        digits = field[:-1] if starred else field
        try:
            value = int(digits)
        except ValueError:
            raise GcovUnionError(f"not a gcov count field: {field!r}")
        numeric_total = value if numeric_total is None else numeric_total + value
        if starred:
            any_starred = True
        else:
            any_unstarred = True
    if numeric_total is not None:
        # See the module docstring: '*' survives the merge only when every numeric contributor
        # carried one -- a single unstarred contributor is proof the line's blocks all ran
        # somewhere in the suite, and that proof does not un-happen because another variant's
        # own tests did not also cover them.
        suffix = "*" if (any_starred and not any_unstarred) else ""
        return f"{numeric_total}{suffix}"
    if saw_never_executed:
        return NEVER_EXECUTED
    return NOT_INSTRUMENTED


def union_gcov_texts(texts: Sequence[str], labels: Optional[Sequence[str]] = None) -> str:
    """Union N .gcov file contents (per-variant reports for the same source) into one report.

    Inputs need not cover the same set of line numbers (a variant's report is free to be shorter
    or longer than another's); every line number that appears in at least one input appears in the
    output. Inputs that do share a line number must agree on its source text, or this raises
    GcovUnionError rather than silently picking one -- see the module docstring.
    """
    if not texts:
        raise GcovUnionError("no .gcov inputs given")
    if labels is None:
        labels = [f"input {i + 1}" for i in range(len(texts))]
    elif len(labels) != len(texts):
        raise GcovUnionError("labels and texts must be the same length")

    parsed = [_parse_gcov(t, label) for t, label in zip(texts, labels)]
    header_lines, source_name, _ = parsed[0]

    for (_, name, _body), label in zip(parsed[1:], labels[1:]):
        if name != source_name:
            raise GcovUnionError(
                "refusing to union .gcov reports for different sources: "
                f"{labels[0]} is {source_name!r}, {label} is {name!r}")

    all_linenos = sorted(set().union(*(body.keys() for _, _, body in parsed)))

    out_lines = list(header_lines)
    for lineno in all_linenos:
        entries = [body[lineno] for _, _, body in parsed if lineno in body]
        texts_at_line = {entry_text for _, entry_text in entries}
        if len(texts_at_line) > 1:
            raise GcovUnionError(
                f"line {lineno} has different source text across inputs -- refusing to union "
                f"what may not be the same file: {sorted(texts_at_line)!r}")
        merged_count = _merge_count_fields([count for count, _ in entries])
        line_text = entries[0][1]
        out_lines.append(f"{merged_count:>9}:{lineno:>5}:{line_text}")
    return "\n".join(out_lines) + "\n"


def coverage_summary(merged_text: str) -> Tuple[int, int]:
    """Return (executed, instrumented) line counts from a merged .gcov text."""
    executed = 0
    instrumented = 0
    for raw_line in merged_text.splitlines():
        if raw_line == "":
            continue
        count_field, lineno_field, _ = _split_gcov_line(raw_line)
        if lineno_field == HEADER_LINENO:
            continue
        if count_field == NOT_INSTRUMENTED:
            continue
        instrumented += 1
        if count_field != NEVER_EXECUTED:
            executed += 1
    return executed, instrumented


def source_name(merged_text: str) -> str:
    for raw_line in merged_text.splitlines():
        if raw_line == "":
            continue
        _, lineno_field, text = _split_gcov_line(raw_line)
        if lineno_field == HEADER_LINENO and text.startswith("Source:"):
            return text[len("Source:"):]
    raise GcovUnionError("merged text has no 'Source:' header line")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", required=True,
                         help="path to write the merged .gcov report to")
    parser.add_argument("inputs", nargs="+",
                         help="per-variant .gcov reports for the same source, in any order")
    args = parser.parse_args(argv)

    texts = []
    for path in args.inputs:
        with open(path, "r") as fh:
            texts.append(fh.read())

    try:
        merged = union_gcov_texts(texts, labels=args.inputs)
    except GcovUnionError as exc:
        print(f"gcov_union.py: {exc}", file=sys.stderr)
        return 1

    with open(args.output, "w") as fh:
        fh.write(merged)

    executed, instrumented = coverage_summary(merged)
    pct = (100.0 * executed / instrumented) if instrumented else 0.0
    # Mirrors gcov's own informational stdout (`File '<name>'` / `Lines executed:NN.NN% of NNN`)
    # so this drop-in replacement for running gcov on a single variant reads the same way in the
    # test.sh console output.
    print(f"File '{source_name(merged)}'")
    print(f"Lines executed:{pct:.2f}% of {instrumented}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Per-failure cause table for W0-1 (BASELINE doc section 6).

Usage: w0_1_failure_table.py <after_junit.xml> <probe_stale.txt>

Prints one markdown row per failed/error testcase: ID | category | basis.
Categories: 製品の不具合 / テストの配置依存 / 環境不足 / 期待値の古さ / 分類保留(UNKNOWN_CAUSE).
A test is put in 期待値の古さ ONLY when tools/probe_w0_1_stale.py showed that a mechanical change to the
test side alone (in a copy of the tree) makes it pass (the memory_brief probe also changes product code in
the copy, so it does not qualify); everything else is 分類保留. 製品の不具合 and
環境不足 are never assigned here: nothing in the evidence establishes either for a failing test.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

STALE, UNKNOWN = "期待値の古さ", "分類保留(UNKNOWN_CAUSE)"


def junit_id(path_id: str) -> str:
    path, rest = path_id.split("::", 1)
    return path[:-3].replace("/", ".") + "::" + rest


def probe_still_failing(text: str) -> dict[str, set[str]]:
    sections: dict[str, set[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("    STILL_FAILS "):
            sections[current].add(junit_id(line.split(" ", 5)[5]))
        elif re.match(r"^[a-z_]+/", line):
            current = line.split(":", 1)[0]
            sections[current] = set()
    return sections


def failed_ids(path: str) -> list[str]:
    out = []
    for case in ET.parse(path).getroot().iter("testcase"):
        if any(child.tag in ("failure", "error") for child in case):
            out.append(f"{case.get('classname')}::{case.get('name')}")
    return sorted(out)


def classify(test_id: str, still: dict[str, set[str]]) -> tuple[str, str, str]:
    module = test_id.split("::")[0]
    names_key = next(k for k in still if k.startswith("names/common-noun"))
    brief_key = next(k for k in still if k.startswith("memory_brief/ask_about"))
    span_key = next(k for k in still if k.startswith("predicate_span/stub"))
    if module.startswith("tests.attack.test_semantic_names_"):
        if test_id in still[names_key]:
            return ("names", UNKNOWN, "probe: still fails after 一般->普通名詞 in the test stubs. The test treats a suffix token (接尾辞) as part of the title; "
                    "verantyx/semantic_names.py:39 says prefixes and suffixes are deliberately not descriptors. Which side is intended is undecided")
        return ("names", STALE, "probe: passes in a copy when the test stubs' pos2 `一般` is changed to `普通名詞`; verantyx/semantic_names.py:40 requires `普通名詞` (also what the installed unidic-lite emits)")
    if module in ("tests.attack.test_semantic_unknown_injection", "tests.attack.test_semantic_unknown_limits"):
        if test_id in still[span_key]:
            return ("predicate_span", UNKNOWN, "probe: still fails after adding predicate_span to the test stubs")
        return ("predicate_span", STALE, "probe: all 30 tests of the two files pass in a copy when the test stubs gain a `predicate_span` attribute (AttributeError today)")
    if module.startswith("tests.attack.test_memory_brief_"):
        if test_id in still[brief_key]:
            return ("memory_brief", UNKNOWN, "probe: still fails even after the copy's ask_about stub returns verdict=ANSWER and compile_brief returns .text; the expected text and the product's text differ in content")
        return ("memory_brief", UNKNOWN, "probe: passes only in a copy where the PRODUCT's compile_brief is also wrapped to return .text, so a test-side-only fix is not shown (the product returns a ContextBrief object, the test expects str); which side is intended is undecided")
    if module in ("tests.test_semantic_measure", "tests.test_semantic_realize", "tests.test_semantic_coordination_codex",
                  "tests.test_semantic_scope_safety", "tests.test_semantic_public", "tests.test_request_goal_route"):
        return ("reader", UNKNOWN, "wave5 units r_reader_regress (hold) / r_reader_regress2 (unfinished) were created to decide regression-vs-outdated for exactly these files and never finished; no decision exists")
    return ("other", UNKNOWN, "no probe and no ledger decision; cause not investigated beyond the failure message in after_junit.xml")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    still = probe_still_failing(open(argv[2], encoding="utf-8").read())
    rows = [(i,) + classify(i, still) for i in failed_ids(argv[1])]
    counts = Counter((group, category) for _id, group, category, _basis in rows)
    print(f"failed testcases: {len(rows)}")
    for (group, category), n in sorted(counts.items()):
        print(f"- group={group} category={category}: {n}")
    totals = Counter(category for _id, _g, category, _b in rows)
    print("- totals: " + ", ".join(f"{c}={n}" for c, n in sorted(totals.items())))
    print()
    print("| テストID | 群 | 分類 | 根拠 |")
    print("|---|---|---|---|")
    for test_id, group, category, basis in rows:
        print(f"| `{test_id}` | {group} | {category} | {basis} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

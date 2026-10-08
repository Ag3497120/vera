#!/usr/bin/env python3
"""Compare two pytest junit XML files (G3 of W0-1: no newly failing tests).

Usage: w0_1_compare_runs.py <before_junit.xml> <after_junit.xml> [--before-log F] [--after-log F]

Each testcase is identified as `classname::name`. States: passed (includes XPASS, which junit
records as a pass), failed, error, xfailed, skipped (with its reason; ENV_MISSING[...] reasons are
classified by resource).

Sections printed:
  state counts for each run (and the pytest summary line from the logs, when given, to cross-check)
  NEW_FAIL        failed/error in after, not failed/error in before, and not an ENV_MISSING skip.
                  A test that exists only in after (not in before) and fails is a NEW_FAIL too.
                  Documented renames (w0_1_count_tests.DOCUMENTED_RENAMES) are followed CASE BY CASE:
                  an after-case is compared against the single before-case it corresponds to
                  (same parameter id, or the new parameter id starts with the old one followed by
                  '-', which is how r_memory 6febe16 extended parametrize('witness') to
                  parametrize('witness, answerable')). A case that maps to no before-case, or to
                  more than one, is treated as ABSENT in before, so a failure there is a NEW_FAIL.
                  There is no "worst status of the old name" shortcut: one failing old case must
                  not hide a regression in a different new case.
                  A test in a module that failed to COLLECT in before (a junit error with an empty
                  classname) is counted on the before-FAILED side, and is listed under that heading.
                  COLLECTION ERRORS IN AFTER (round 3): every module that fails to collect in after is
                  one line `COLLECTION_ERROR <module> [error; before=<collected|ABSENT>]` in NEW_FAIL
                  and exit 1, unless that module also failed to collect in before (then it is on the
                  before-failed side, listed under the AFTER_COLLECTION_ERROR_BUT_BEFORE... heading,
                  symmetric to the before rule above). A module that disappears into a collection
                  error must not look like "no new failures".
  PASS_TO_SKIP    passed in before, skipped in after. A skip whose reason names a resource
                  (ENV_MISSING[...]) is listed and allowed; a skip with no resource name
                  (UNCLASSIFIED) is a gate violation (exit 1): the ticket forbids silent skips.
  PASS_TO_XFAIL   passed in before, xfailed in after. Gate violation (exit 1).
  FAIL_TO_SKIP    failed/error in before, skipped in after (listed with the ENV_MISSING resource)
  MISSING_IN_AFTER  present in before, absent in after (renames resolved). Gate violation (exit 1):
                  a vanished test case is not caught by G4, which counts functions, not parametrized cases.
  FIXED           failed/error in before, passed in after
  ONLY_IN_AFTER   present only in after
Before the last line a `G3 GATES ...` line gives the three gate counts besides NEW_FAIL
(MISSING_IN_AFTER, PASS_TO_XFAIL, PASS_TO_SKIP_UNCLASSIFIED).
Last line: `G3 NEW_FAIL=<n>`; exit 1 when n > 0 or any of the three gate counts is > 0.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w0_1_count_tests import DOCUMENTED_RENAMES  # noqa: E402

ENV_RE = re.compile(r"^(?:Skipped: )?ENV_MISSING\[([^\]]+)\]")


def to_junit_id(test_id: str) -> str:
    path, rest = test_id.split("::", 1)
    return path[:-3].replace("/", ".") + "::" + rest


RENAMES = {to_junit_id(old): to_junit_id(new) for old, new in DOCUMENTED_RENAMES.items()}


def load(path: str):
    """Return (states, collect_error_modules). states: id -> (state, detail)."""
    states: dict[str, tuple[str, str]] = {}
    collect_errors: list[str] = []
    for case in ET.parse(path).getroot().iter("testcase"):
        classname, name = case.get("classname", ""), case.get("name", "")
        kids = {child.tag: child for child in case}
        if "error" in kids and classname == "":
            collect_errors.append(name)
            continue
        key = f"{classname}::{name}"
        if "failure" in kids:
            states[key] = ("failed", ((kids["failure"].get("message") or "").splitlines() or [""])[0][:200])
        elif "error" in kids:
            states[key] = ("error", ((kids["error"].get("message") or "").splitlines() or [""])[0][:200])
        elif "skipped" in kids:
            sk = kids["skipped"]
            if sk.get("type") == "pytest.xfail":
                states[key] = ("xfailed", sk.get("message") or "")
            else:
                states[key] = ("skipped", sk.get("message") or "")
        else:
            states[key] = ("passed", "")
    return states, collect_errors


def env_resource(detail: str):
    match = ENV_RE.match(detail)
    return match.group(1) if match else None


def summary_line(log: str | None):
    if not log or not Path(log).is_file():
        return None
    lines = [l for l in Path(log).read_text(encoding="utf-8", errors="replace").splitlines()
             if re.search(r"\d+ (passed|failed)", l) and " in " in l]
    return lines[-1] if lines else None


def counts(states):
    c = Counter(s for s, _ in states.values())
    resources = Counter()
    for s, d in states.values():
        if s == "skipped":
            resources[env_resource(d) or "UNCLASSIFIED"] += 1
    return c, resources


def main(argv: list[str]) -> int:
    args = argv[1:]
    logs = {}
    for flag in ("--before-log", "--after-log"):
        if flag in args:
            i = args.index(flag)
            logs[flag] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    before, before_collect = load(args[0])
    after, after_collect = load(args[1])
    for label, states, collect, log in (("before", before, before_collect, logs.get("--before-log")),
                                        ("after", after, after_collect, logs.get("--after-log"))):
        c, res = counts(states)
        print(f"{label}: testcases={len(states)} passed={c['passed']} failed={c['failed']} error(non-collection)={c['error']} "
              f"xfailed={c['xfailed']} skipped={c['skipped']} collection_errors={len(collect)}")
        print(f"  skipped by resource: {dict(sorted(res.items()))}")
        for module in collect:
            print(f"  COLLECTION_ERROR module: {module}")
        line = summary_line(log)
        if line:
            print(f"  pytest summary line: {line}")
    before_collect_modules = set(before_collect)

    def base(test_id: str) -> str:
        return test_id.split("[", 1)[0]

    old_by_new_base = {base(n): base(o) for o, n in RENAMES.items()}

    def param_of(test_id: str) -> str:
        return test_id[len(base(test_id)):]

    def map_renamed_case(test_id: str):
        """Return the before-key a renamed after-case corresponds to, or None (unmapped/ambiguous)."""
        old_base = old_by_new_base[base(test_id)]
        params = param_of(test_id)
        exact = old_base + params
        if exact in before:
            return exact
        if params.startswith("[") and params.endswith("]"):
            inner = params[1:-1]
            cands = []
            for k in before:
                if base(k) != old_base:
                    continue
                kp = param_of(k)
                if kp.startswith("[") and kp.endswith("]") and inner.startswith(kp[1:-1] + "-"):
                    cands.append(k)
            if len(cands) == 1:
                return cands[0]
        return None

    # Case-level rename mapping, computed up front. An after-case that maps to a before-case
    # that another after-case also maps to is ambiguous and is treated as unmapped.
    case_map: dict[str, str] = {}      # after-key -> before-key, for renamed cases only
    unmapped_renamed: list[str] = []   # after-keys of renamed tests with no unique before-case
    _tentative = {k: map_renamed_case(k) for k in sorted(after) if base(k) in old_by_new_base}
    _targets = Counter(v for v in _tentative.values() if v is not None)
    for _k, _v in _tentative.items():
        if _v is not None and _targets[_v] == 1:
            case_map[_k] = _v
        else:
            unmapped_renamed.append(_k)

    def before_status(test_id: str):
        if base(test_id) in old_by_new_base:
            old_key = case_map.get(test_id)
            if old_key is not None:
                return before[old_key][0], old_key
            return None, None
        if test_id in before:
            return before[test_id][0], test_id
        module = test_id.split("::", 1)[0]
        if module in before_collect_modules:
            return "collection_error_in_before", None
        return None, None

    bad = ("failed", "error")
    new_fail, collect_side, pass_to_skip, pass_to_xfail, fixed, only_after, fail_to_skip = [], [], [], [], [], [], []
    skip_unclassified = []  # passed in before, skipped in after with no resource name
    after_collect_side = []  # modules that fail to collect in after AND in before (before-failed side)
    before_collected_modules = {k.split("::", 1)[0] for k in before}
    for module in after_collect:
        if module in before_collect_modules:
            after_collect_side.append(module)
        else:
            seen = "collected" if module in before_collected_modules else "ABSENT"
            new_fail.append(f"COLLECTION_ERROR {module} [error; before={seen}]")
    for test_id, (state, detail) in sorted(after.items()):
        prior, _key = before_status(test_id)
        if prior is None:
            only_after.append(f"{test_id} [{state}]")
        if state in bad:
            if prior in bad:
                continue
            if prior == "collection_error_in_before":
                collect_side.append(test_id)
                continue
            new_fail.append(f"{test_id} [{state}; before={prior or 'ABSENT'}] {detail}")
        elif prior == "passed" and state == "skipped":
            res = env_resource(detail)
            pass_to_skip.append(f"{test_id} [{'ENV_MISSING[' + res + ']' if res else 'UNCLASSIFIED'}] {detail[:120]}")
            if not res:
                skip_unclassified.append(test_id)
        elif prior == "passed" and state == "xfailed":
            pass_to_xfail.append(test_id)
        elif prior in bad and state == "passed":
            fixed.append(test_id)
        elif prior in bad and state == "skipped":
            res = env_resource(detail)
            fail_to_skip.append(f"{test_id} [{'ENV_MISSING[' + res + ']' if res else 'UNCLASSIFIED'}] before={prior}")
    claimed = set(case_map.values())
    missing = sorted(k for k in before if base(k) in RENAMES and k not in claimed) \
        + sorted(k for k in before if base(k) not in RENAMES and k not in after)
    renamed_info = []
    for old, new in RENAMES.items():
        renamed_info.append(f"{old} ({sum(1 for k in before if base(k) == old)} cases) -> {new} ({sum(1 for k in after if base(k) == new)} cases)")
    for after_key, before_key in sorted(case_map.items()):
        renamed_info.append(f"  case: {before_key} -> {after_key}")
    for after_key in unmapped_renamed:
        renamed_info.append(f"  case UNMAPPED (treated as absent in before): {after_key}")
    for title, items in (("NEW_FAIL", new_fail),
                         ("AFTER_FAILED_BUT_BEFORE_COLLECTION_ERROR (counted on the before-failed side)", collect_side),
                         ("AFTER_COLLECTION_ERROR_BUT_BEFORE_COLLECTION_ERROR (counted on the before-failed side)", after_collect_side),
                         ("PASS_TO_SKIP", pass_to_skip), ("PASS_TO_XFAIL", pass_to_xfail),
                         ("FAIL_TO_SKIP (failed before, classified skip after: these are the failures moved into ENV_MISSING)", fail_to_skip),
                         ("MISSING_IN_AFTER", missing), ("FIXED", fixed), ("ONLY_IN_AFTER", only_after)):
        print(f"\n{title} ({len(items)}):")
        for item in items:
            print(f"  {item}")
    bset = {k for k, (st, _) in before.items() if st in bad}
    aset = {k for k, (st, _) in after.items() if st in bad}
    gone = bset - aset
    print("\nRECONCILIATION by exact id (before failed/error ids vs after failed/error ids):")
    print(f"  before failed/error ids: {len(bset)}  (+ {len(before_collect)} module collection error(s) not counted as ids)")
    print(f"  after  failed/error ids: {len(aset)}")
    print(f"  failed in both: {len(bset & aset)}")
    print(f"  failed before, not failed after: {len(gone)}  = passed {sum(1 for k in gone if k in after and after[k][0] == 'passed')}"
          f" + skipped {sum(1 for k in gone if k in after and after[k][0] == 'skipped')}"
          f" + xfailed {sum(1 for k in gone if k in after and after[k][0] == 'xfailed')}"
          f" + id absent in after {sum(1 for k in gone if k not in after)}")
    print(f"  failed after, not failed before (exact id): {len(aset - bset)}")
    print(f"\nRENAMED (case counts may differ because parameter ids changed) ({len(renamed_info)}):")
    for item in renamed_info:
        print(f"  {item}")
    gates = {"MISSING_IN_AFTER": len(missing), "PASS_TO_XFAIL": len(pass_to_xfail),
             "PASS_TO_SKIP_UNCLASSIFIED": len(skip_unclassified)}
    print("G3 GATES " + " ".join(f"{k}={v}" for k, v in gates.items()))
    print(f"G3 NEW_FAIL={len(new_fail)}")
    return 1 if (new_fail or any(gates.values())) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

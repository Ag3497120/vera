#!/usr/bin/env python3
"""Measure the modality construction against train-lead coverage and gold."""
from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
import sys

sys.path[:0] = [".", "tools"]
os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

import round5a_route_tune as T
from read_coverage import measure as coverage_measure
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import View as VerifyView, license_clause
from verantyx.semantic_realize import Realized, check_round_trip, realize_clause


PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
PHENOMENON = "可能・不可能"


def _coverage_keys(view):
    supported = {(c.span.source, c.span.start) for c in view.clauses if not c.unsupported}
    return supported


def _modal_clauses(view, key):
    return tuple(c for c in view.clauses
                 if c.rule == "modality" and not c.unsupported
                 and (c.span.source, c.span.start) == key)


def _gold(off):
    env = os.environ.copy()
    env["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "."
    env["VERA_CONSTRUCTIONS_OFF"] = "modality" if off else ""
    result = subprocess.run(
        [PYTHON, "-B", GOLD_PROBE, "wdw", "--phenomenon", PHENOMENON, "--n", "150"],
        cwd=".", env=env, check=True, text=True, capture_output=True, timeout=30,
    )
    line = next((line for line in result.stdout.splitlines()
                 if line.lstrip().startswith(PHENOMENON)), "")
    match = re.search(r"(\{[^\n]*\})", line)
    if not match:
        raise RuntimeError("gold probe output did not contain the requested phenomenon")
    return ast.literal_eval(match.group(1))


def _role_text(clause):
    return ", ".join(f"{r.name}={r.term}" for r in clause.roles) or "no explicit roles"


def _scope_text(view, clause):
    source = view.sources.get(clause.span.source, "")
    cues = {
        "hearsay": ("とされる", "と言われる", "と思われる", "らしい"),
        "obligation": ("べき",),
        "possibility": ("可能性がある", "可能であった", "可能である", "可能だった",
                        "可能だ", "可能", "だろう", "はずだ", "ようだ"),
        "impossibility": ("不可能であった", "不可能である", "不可能だった", "不可能だ", "不可能"),
    }.get(clause.modality, ())
    matches = [(source.find(cue, clause.predicate_span.end, clause.span.end), cue)
               for cue in cues]
    matches = [(at, cue) for at, cue in matches if at >= 0]
    if not matches:
        return ""
    cue_start, cue = min(matches, key=lambda item: (item[0], -len(item[1])))
    pred_start = clause.predicate_span.start
    if clause.predicate.endswith("する") and clause.predicate[:-2]:
        stem = clause.predicate[:-2]
        if source[max(clause.span.start, pred_start - len(stem)):pred_start] == stem:
            pred_start -= len(stem)
    start = min([pred_start] + [r.span.start for r in clause.roles])
    return source[start:cue_start + len(cue)]


def main():
    if os.environ.get("VERA_LEADS"):
        T.PATH = os.environ["VERA_LEADS"]
    docs = T.load(1500, 200)

    os.environ["VERA_CONSTRUCTIONS_OFF"] = "modality"
    disabled = document_view(docs)
    disabled_supported = _coverage_keys(disabled)

    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    enabled = document_view(docs)
    enabled_supported = _coverage_keys(enabled)
    disabled_count = len(disabled_supported)
    enabled_count = len(enabled_supported)
    newly_supported = enabled_supported - disabled_supported

    # Keep the same sample definition as read_coverage.py while reporting both
    # sides through its public helper as a guard against drift in the metric.
    os.environ["VERA_CONSTRUCTIONS_OFF"] = "modality"
    off_measure = coverage_measure(1500, 200)
    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    on_measure = coverage_measure(1500, 200)
    print(f"coverage disabled={disabled_count} helper={off_measure['supported_sentences']} "
          f"enabled={enabled_count} helper={on_measure['supported_sentences']} "
          f"newly_supported={len(newly_supported)}")

    ordered = sorted(newly_supported,
                     key=lambda key: hashlib.sha256(
                         (key[0] + "\0" + str(key[1])).encode("utf-8")).hexdigest())
    audited_keys = ordered[:60]
    audited = []
    for key in audited_keys:
        audited.extend(_modal_clauses(enabled, key))

    verify_view = VerifyView(enabled.sources, enabled.clauses)
    licensed = 0
    for clause in audited:
        try:
            verdict = license_clause(clause, verify_view)
            if verdict is not False:
                licensed += 1
        except Exception:
            continue

    realizable = 0
    round_trip_ok = 0
    for clause in audited:
        try:
            realized = realize_clause(clause)
        except Exception:
            continue
        if not isinstance(realized, Realized):
            continue
        realizable += 1
        sentence = clause.span.text
        try:
            result = check_round_trip(clause, sentence)
            if result.get("passed"):
                round_trip_ok += 1
        except Exception:
            pass
    round_trip_rate = 1.0 if not realizable else round_trip_ok / realizable
    license_rate = 1.0 if not audited else licensed / len(audited)
    print(f"precision audited_sentences={len(audited_keys)} audited_clauses={len(audited)} "
          f"checker_licensed={licensed}/{len(audited)} "
          f"round_trip={round_trip_ok}/{realizable} ({round_trip_rate:.1%})")

    example_keys = list(ordered)
    # Fill the human review set with additional modality readings if the
    # newly-supported set has fewer than fifteen members.
    seen = set(example_keys)
    for clause in enabled.clauses:
        key = (clause.span.source, clause.span.start)
        if clause.rule == "modality" and not clause.unsupported and key not in seen:
            example_keys.append(key)
            seen.add(key)
    print("examples:")
    for key in example_keys[:15]:
        clauses = _modal_clauses(enabled, key)
        if not clauses:
            clauses = tuple(c for c in enabled.clauses
                            if c.rule == "modality" and (c.span.source, c.span.start) == key)
        source = enabled.sources.get(key[0], "")
        sentence = next((c.span.text for c in clauses), "")
        if not sentence and source and 0 <= key[1] < len(source):
            end = source.find("。", key[1])
            sentence = source[key[1]:end + 1] if end >= 0 else source[key[1]:]
        print(f"  {sentence}")
        for clause in clauses:
            scope = _scope_text(enabled, clause)
            print(f"    {clause.predicate} [{clause.modality}] ({_role_text(clause)}) "
                  f"scope={scope!r} "
                  f"unsupported={clause.unsupported}")

    os.environ["VERA_CONSTRUCTIONS_OFF"] = "modality"
    gold_off = _gold(True)
    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    gold_on = _gold(False)
    print(f"gold {PHENOMENON}: off correct={gold_off.get('correct', 0)} "
          f"wrong_other={gold_off.get('wrong_other', 0)}; "
          f"on correct={gold_on.get('correct', 0)} "
          f"wrong_other={gold_on.get('wrong_other', 0)}")

    # Use the public coverage helper's counts for the enabled/disabled floor.
    coverage_ok = (on_measure["supported_sentences"] >= off_measure["supported_sentences"]
                   and enabled_count >= disabled_count)
    gold_ok = (gold_on.get("correct", 0) >= gold_off.get("correct", 0)
               and gold_on.get("wrong_other", 0) <= gold_off.get("wrong_other", 0))
    if (coverage_ok and len(newly_supported) >= 10 and audited
            and license_rate == 1.0 and round_trip_rate >= 0.95 and gold_ok):
        print("DEMO OK")
        return 0
    print("DEMO FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

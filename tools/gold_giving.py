"""Gold-probe demo and diagnostics for the gold_giving construction."""
from __future__ import annotations

import ast
from collections import Counter
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
ENV = {
    **os.environ,
    "VERA_CORPUS_ROOT": "/tmp/vera-empty-materials",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPATH": ".",
}


def _off_rules(add: str | None = None, remove: str | None = None) -> str:
    names = {part.strip() for part in os.environ.get("VERA_CONSTRUCTIONS_OFF", "").split(",") if part.strip()}
    if add:
        names.add(add)
    if remove:
        names.discard(remove)
    return ",".join(sorted(names))


def _run(command: list[str], *, disabled: str) -> str:
    env = dict(ENV)
    env["VERA_CONSTRUCTIONS_OFF"] = disabled
    result = subprocess.run(
        command, cwd=ROOT, env=env, check=True, capture_output=True,
        text=True, timeout=30,
    )
    return result.stdout


def _probe(seed: int, disabled: str) -> dict[str, int]:
    output = _run(
        [PYTHON, "-B", PROBE, "wdw", "--phenomenon", "授受", "--n", "150", "--seed", str(seed)],
        disabled=disabled,
    )
    match = re.search(r"^TOTAL (\{.*\})", output, re.MULTILINE)
    if not match:
        raise AssertionError("gold probe did not print its TOTAL row")
    counts = ast.literal_eval(match.group(1))
    return {key: int(value) for key, value in counts.items()}


def _coverage(disabled: str) -> int:
    output = _run(
        [PYTHON, "-B", "tools/read_coverage.py", "--n", "1500", "--stride", "200"],
        disabled=disabled,
    )
    payload = json.loads(output)
    return int(payload["supported_sentences"])


def _constructed_input_assertions() -> None:
    from verantyx.constructions import ConstructionContext, TokenSpan
    from verantyx.constructions.gold_giving import licenses, reads
    from verantyx.semantic_ir import Span
    from verantyx.semantic_reader import _tokens, document_view

    examples = (
        (
            "私は父に、修理に使う工具をもらった。",
            {"agent": "父", "patient": "工具", "recipient": "私"},
        ),
        (
            "彼は妹に手紙を書いてあげた。",
            {"agent": "彼", "patient": "手紙", "recipient": "妹"},
        ),
    )
    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = _off_rules("gold_giving", "giving") + ",zero_subject"
    try:
        for index, (sentence, expected) in enumerate(examples):
            doc_id = "gold_giving_demo_" + str(index)
            view = document_view({doc_id: sentence})
            native = tuple(c for c in view.clauses if c.rule in ("frame", "zero_subject"))
            tokens = tuple(TokenSpan(token, start, end) for token, start, end in _tokens(sentence))
            context = ConstructionContext(
                sentence,
                Span(doc_id, 0, len(sentence), sentence),
                tokens,
                doc_id,
                native,
            )
            reading = reads(context)
            assert reading is not None and len(reading.clauses) == 1
            clause = reading.clauses[0]
            actual = {role.name: role.term for role in clause.roles}
            assert actual == expected, (actual, expected)
            assert not clause.unsupported
            assert licenses(clause, sentence)
            changed = sentence.replace(expected["patient"], "別の物", 1)
            assert not licenses(clause, changed)
    finally:
        if prior_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = prior_off


def _diagnose_probe(seed: int = 7, n: int = 150) -> tuple[Counter, list[dict[str, object]]]:
    from verantyx import semantic, semantic_reader

    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = _off_rules("gold_giving")
    prior_argv = sys.argv
    original_answer = semantic.answer
    original_view = semantic_reader.document_view
    rows: list[dict[str, object]] = []

    def view_hook(*args, **kwargs):
        return original_view(*args, **kwargs)

    def answer_hook(request, views, **kwargs):
        result = original_answer(request, views, **kwargs)
        verdict = str(result.get("verdict", "")) if isinstance(result, dict) else ""
        if verdict.startswith("UNKNOWN"):
            reasons = Counter(
                reason
                for view in views
                for clause in view.clauses
                for reason in clause.unsupported
            )
            reasons.update(
                "unread: " + unread.reason
                for view in views for unread in view.unread
            )
            rows.append({
                "question": request.text,
                "reason": str(result.get("reason", verdict)),
                "source_reasons": reasons,
            })
        return result

    semantic_reader.document_view = view_hook
    semantic.answer = answer_hook
    sys.argv = [
        PROBE, "wdw", "--phenomenon", "授受", "--n", str(n), "--seed", str(seed),
    ]
    try:
        with redirect_stdout(io.StringIO()):
            try:
                runpy.run_path(PROBE, run_name="__main__")
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
    finally:
        semantic.answer = original_answer
        semantic_reader.document_view = original_view
        sys.argv = prior_argv
        if prior_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = prior_off
    summary = Counter(row["reason"] for row in rows)
    return summary, rows


def _print_counts(seed: int, before: dict[str, int], after: dict[str, int]) -> None:
    keys = ("correct", "wrong_other", "wrong_overlap", "abstain")
    print("授受 seed=" + str(seed), "off", *(f"{key}={before.get(key, 0)}" for key in keys))
    print("授受 seed=" + str(seed), "on ", *(f"{key}={after.get(key, 0)}" for key in keys))


def main() -> None:
    _constructed_input_assertions()

    baseline_off = _off_rules("gold_giving")
    enabled_off = _off_rules(remove="gold_giving")
    for seed in (7, 101):
        before = _probe(seed, baseline_off)
        after = _probe(seed, enabled_off)
        _print_counts(seed, before, after)
        assert after.get("correct", 0) > before.get("correct", 0)
        assert after.get("wrong_other", 0) <= before.get("wrong_other", 0)
        assert after.get("wrong_overlap", 0) <= before.get("wrong_overlap", 0)

    coverage_off = _coverage(baseline_off)
    coverage_on = _coverage(enabled_off)
    print(f"supported_sentences off={coverage_off} on={coverage_on}")
    assert coverage_on >= coverage_off

    reasons, rows = _diagnose_probe()
    print(f"ABSTAIN DIAG seed=7 items={len(rows)} reasons={dict(reasons)}")
    for row in rows[:8]:
        detail = dict(row["source_reasons"])
        print(f"ABSTAIN item: {row['question']} | request={row['reason']} | source={detail}")

    print("DEMO OK")


if __name__ == "__main__":
    main()

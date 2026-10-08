#!/usr/bin/env python3
"""Offline gold and reading-coverage gate for the scramble construction."""
from __future__ import annotations

import ast
import collections
import contextlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time
from dataclasses import replace


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = Path("/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py")
LIMIT_SECONDS = 58.0
STARTED = time.monotonic()


def _fail(message: str) -> None:
    raise SystemExit("DEMO FAIL: " + message)


def _env(enabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "."
    if enabled:
        env.pop("VERA_CONSTRUCTIONS_OFF", None)
    else:
        env["VERA_CONSTRUCTIONS_OFF"] = "gold_scramble"
    return env


def _remaining() -> float:
    left = LIMIT_SECONDS - (time.monotonic() - STARTED)
    if left <= 1:
        _fail("time budget exhausted")
    return left


def _gold_totals(output: str) -> dict[str, int]:
    match = re.search(r"(?m)^TOTAL\s+(\{[^\n]*\})", output)
    if not match:
        raise AssertionError("gold probe did not report totals")
    result = ast.literal_eval(match.group(1))
    required = ("correct", "wrong_other", "wrong_overlap", "abstain")
    if (not isinstance(result, dict)
            or any(type(result.get(key, 0)) is not int for key in required)):
        raise AssertionError("gold probe totals were incomplete")
    return {key: result.get(key, 0) for key in required}


def _reason_items(value):
    if isinstance(value, dict):
        if isinstance(value.get("reason"), str) and value["reason"]:
            yield value["reason"]
        for child in value.values():
            yield from _reason_items(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _reason_items(child)


def _probe(seed: int, enabled: bool) -> tuple[dict[str, int], collections.Counter]:
    """Run the official probe in-process and retain only typed refusal reasons."""
    if not GOLD_PROBE.is_file():
        raise FileNotFoundError("gold probe is unavailable")
    old_env = {key: os.environ.get(key) for key in (
        "VERA_CORPUS_ROOT", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH", "VERA_CONSTRUCTIONS_OFF")}
    os.environ.update(_env(enabled))
    sys.path.insert(0, str(ROOT))
    old_argv = sys.argv
    from verantyx.one import Vera
    original_ask = Vera.ask
    refusals: collections.Counter = collections.Counter()

    def diagnosed_ask(self, query, *args, **kwargs):
        result = original_ask(self, query, *args, **kwargs)
        verdict = result.get("verdict", "UNKNOWN")
        if verdict != "ANSWER":
            semantic = result.get("semantic")
            details = list(_reason_items(semantic.get("unread"))) if isinstance(semantic, dict) else []
            if details:
                refusals.update((verdict, detail) for detail in set(details))
            else:
                reason = result.get("reason") or "reason not supplied"
                refusals[(verdict, str(reason))] += 1
        return result

    Vera.ask = diagnosed_ask
    output = io.StringIO()
    errors = io.StringIO()
    try:
        sys.argv = [str(GOLD_PROBE), "wdw", "--phenomenon", "語順", "--n", "150",
                    "--seed", str(seed)]
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            runpy.run_path(str(GOLD_PROBE), run_name="__main__")
    finally:
        Vera.ask = original_ask
        sys.argv = old_argv
        sys.path.remove(str(ROOT))
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if errors.getvalue().strip():
        raise RuntimeError("gold probe failed: " + errors.getvalue()[-1000:])
    return _gold_totals(output.getvalue()), refusals


def _coverage(enabled: bool) -> int:
    result = subprocess.run(
        [PYTHON, "-B", "tools/read_coverage.py", "--n", "1500", "--stride", "200"],
        cwd=ROOT, env=_env(enabled), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=_remaining(), check=False,
    )
    if result.returncode:
        raise RuntimeError("read_coverage failed: " + result.stderr[-1000:])
    data = json.loads(result.stdout)
    count = data.get("supported_sentences")
    if type(count) is not int:
        raise AssertionError("read_coverage omitted supported_sentences")
    return count


def _synthetic_demo() -> tuple[int, int]:
    from verantyx.constructions import ConstructionContext, TokenSpan
    from verantyx.constructions.gold_scramble import licenses, reads
    from verantyx.question import read_semantic
    from verantyx.semantic import answer
    from verantyx.semantic_ir import Span
    from verantyx.semantic_reader import _tokens, document_view

    sentence = "現場で資料を花子が太郎に転置した。"
    source = "gold_scramble_demo"
    view = document_view({source: sentence})
    constructed = [clause for clause in view.clauses if clause.rule == "gold_scramble"]
    if len(constructed) != 1:
        raise AssertionError("scrambled, source-bounded clause was not constructed")
    clause = constructed[0]
    expected = {"agent": "花子", "patient": "資料", "recipient": "太郎"}
    actual = {role.name: role.term for role in clause.roles if role.name in expected}
    if actual != expected:
        raise AssertionError("explicit case roles did not match constructed gold")
    if any(role.name == "place" and role.term == "現場" for role in clause.roles):
        raise AssertionError("ambiguous で phrase was assigned a place role")
    if not any(role.name.startswith("unresolved_") and role.term == "現場"
               for role in clause.roles):
        raise AssertionError("ambiguous source phrase was not retained as unresolved")
    if not licenses(clause, sentence):
        raise AssertionError("independent construction licensor rejected its source")

    request = read_semantic("誰が何を転置した？").value
    result = answer(request, [view])
    if result.get("verdict") != "ANSWER" or result.get("values") != ["花子", "資料"]:
        raise AssertionError("verified answer did not follow the explicit scrambled roles")

    unknown_request = read_semantic("どこで資料を転置した？").value
    unknown = answer(unknown_request, [view])
    if unknown.get("verdict") == "ANSWER":
        raise AssertionError("ambiguous で phrase was used as a place answer")

    tampered_roles = tuple(
        replace(role, term="別人") if role.name == "agent" else role
        for role in clause.roles
    )
    if licenses(replace(clause, roles=tampered_roles), sentence):
        raise AssertionError("licensor accepted a changed agent")

    normal = document_view({"normal_order": "花子が太郎に資料を転置した。"})
    if any(c.rule == "gold_scramble" for c in normal.clauses):
        raise AssertionError("rule consumed an already-supported canonical clause")

    os.environ["VERA_CONSTRUCTIONS_OFF"] = "gold_scramble"
    try:
        off = document_view({source: sentence})
        disabled = answer(request, [off])
        if disabled.get("verdict") == "ANSWER":
            raise AssertionError("disabled construction still supplied an answer")
    finally:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)

    # Also exercise the reader directly with independently prepared source
    # clauses and tagged offsets, so the assertion does not depend only on the
    # output already assembled by document_view.
    native = [c for c in off.clauses if c.rule == "frame"]
    if len(native) != 1:
        raise AssertionError("disabled baseline did not retain one native frame")
    token_spans = tuple(TokenSpan(word, start, end)
                        for word, start, end in _tokens(sentence))
    direct_context = ConstructionContext(
        sentence, Span(source, 0, len(sentence), sentence), token_spans, source, tuple(native))
    direct = reads(direct_context)
    if direct is None or len(direct.clauses) != 1:
        raise AssertionError("direct reader failed the authored scrambled input")
    direct_clause = direct.clauses[0]
    if ({r.name: r.term for r in direct_clause.roles if r.name in expected} != expected
            or not licenses(direct_clause, sentence)):
        raise AssertionError("direct constructed gold or independent license failed")
    return 2, 2


def main() -> None:
    sys.path.insert(0, str(ROOT))
    baselines = {}
    measured = {}
    diagnosis = {}
    for seed in (7, 101):
        baselines[seed], diagnosis[seed] = _probe(seed, False)
        measured[seed], _ = _probe(seed, True)
        print(f"seed {seed} off  {json.dumps(baselines[seed], sort_keys=True)}")
        print(f"seed {seed} on   {json.dumps(measured[seed], sort_keys=True)}")
        if measured[seed]["correct"] <= baselines[seed]["correct"]:
            _fail(f"correct did not rise on seed {seed}")
        for key in ("wrong_other", "wrong_overlap"):
            if measured[seed][key] > baselines[seed][key]:
                _fail(f"{key} rose on seed {seed}")

    for seed in (7, 101):
        print(f"seed {seed} abstain reasons off "
              + json.dumps({f"{verdict}: {reason}": count
                            for (verdict, reason), count in sorted(diagnosis[seed].items())},
                           ensure_ascii=False, sort_keys=True))

    coverage_off = _coverage(False)
    coverage_on = _coverage(True)
    print("supported_sentences", json.dumps({"off": coverage_off, "on": coverage_on},
                                             sort_keys=True))
    if coverage_on < coverage_off:
        _fail("supported_sentences fell")

    licensed, examples = _synthetic_demo()
    print(f"checker licensed {licensed}/{examples} constructed clauses")
    if licensed != examples:
        _fail("independent licensor did not license every constructed clause")
    if time.monotonic() - STARTED >= LIMIT_SECONDS:
        _fail("demo exceeded its 58 second budget")
    print("DEMO OK")


if __name__ == "__main__":
    main()

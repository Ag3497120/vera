"""W6-a P2 / P5 / E at the entrance (`vera ask`): a generated sentence is never the basis of a fact,
the reference column is off unless asked and never enters any memory, and a request that claims no
fact gets the "constructed" type.

Synthetic data only. The index is built in tmp_path with tools.build_p4_corpus_index.build.
Helpers are copied here on purpose: tests/ is not a package.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.bank_score.adapters import _state
from tools.build_p4_corpus_index import build
from verantyx import basis_policy as bp
from verantyx import sovereign as sov
from verantyx.cli import _load, main
from verantyx.one import Vera

REPO = Path(__file__).resolve().parents[1]
Q = "雨の日に傘を持たずに外出すると、どうなりますか？"
ROWS = ["雨の日に傘を持たずに出たら、髪が濡れた。", "雨の日に傘を持たずに出たら、服が濡れた。",
        "次郎が花子に本を渡した。"]
FLAG_SETS = ([], ["--human-present"], ["--show-generated-reference"],
             ["--human-present", "--show-generated-reference"])


@pytest.fixture(autouse=True)
def _no_outside_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


def _index(tmp_path: Path, monkeypatch=None) -> Path:
    src = tmp_path / "local.jsonl"
    src.write_text("".join(json.dumps({"text": t, "source": f"g{i}", "scene": "場面", "sha": f"h{i}"},
                                      ensure_ascii=False) + "\n" for i, t in enumerate(ROWS)),
                   encoding="utf-8")
    build(src, tmp_path / "idx" / "local.db", "local")
    if monkeypatch is not None:
        monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    return tmp_path / "idx"


def _ask(tmp_path, capsys, query, *args):
    rc = main(["--store", str(tmp_path / "s.json"), "ask", query, *args])
    return rc, json.loads(capsys.readouterr().out)


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _without(out: dict, *keys: str) -> dict:
    return {k: v for k, v in out.items() if k not in keys}


def _roundtrip(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False))


_CLOCK_KEYS = ("ingest_ms", "elapsed_ms")     # wall-clock timings: the only keys that differ between two runs


def _stable(obj):
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in obj.items() if k not in _CLOCK_KEYS}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


# ===================================================================== P2: from the entrance
def test_the_index_alone_would_have_answered_this_question_from_generated_sentences(tmp_path, monkeypatch):
    """The reproduction: the policy is what stands between the corpus and the answer."""
    _index(tmp_path, monkeypatch)
    raw = Vera().load_store(_load(str(tmp_path / "s.json"))).ask(Q)
    assert raw["kind"] == "answer" and raw["verdict"] == "ANSWER" and raw["basis_origin"] == "generated"
    assert any(s.get("origin") == "generated" for s in raw["sources"])


@pytest.mark.parametrize("flags", FLAG_SETS)
@pytest.mark.parametrize("with_sovereign", [False, True])
def test_p2_a_fact_question_with_only_generated_basis_never_answers(tmp_path, monkeypatch, capsys,
                                                                    flags, with_sovereign):
    _index(tmp_path, monkeypatch)
    if with_sovereign:
        assert sov.create(str(tmp_path / "sov"), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
        monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(tmp_path / "sov"))
        monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    rc, out = _ask(tmp_path, capsys, Q, *flags)
    assert rc == 0
    assert out["verdict"] != "ANSWER" and out["kind"] != "answer"
    assert not out["basis_policy"]["outcome"].startswith("ANSWER_")
    assert _state(out) != "answer"
    human, ref = "--human-present" in flags, "--show-generated-reference" in flags
    expected = "CONFIRM_REQUEST" if human else "REFERENCE_GENERATED" if ref else "ABSTAIN"
    assert out["basis_policy"]["outcome"] == expected
    assert out["basis_policy"]["applied"] is True and out["basis_policy"]["basis"] == "GENERATED"
    assert out["basis_policy"]["in_table"] is True
    assert "basis_origin" not in out and list(out)[-1] == "basis_policy"


def test_p2_through_a_real_subprocess(tmp_path):
    idx = _index(tmp_path)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path), "PYTHONPATH": str(REPO),
           "PYTHONDONTWRITEBYTECODE": "1", "VERA_P4_INDEX": str(idx)}
    for flags in FLAG_SETS:
        done = subprocess.run([sys.executable, "-m", "verantyx.cli", "--store", str(tmp_path / "s.json"),
                               "ask", Q, *flags], cwd=REPO, env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=120)
        assert done.returncode == 0, done.stderr[-400:]
        out = json.loads(done.stdout)
        assert out["verdict"] != "ANSWER" and out["kind"] != "answer"
        assert not out["basis_policy"]["outcome"].startswith("ANSWER_")
        assert _state(out) != "answer"


GEN = {"family": "local", "source": "g0", "text": "窓が光った。", "sha": "w", "origin": "generated",
       "generator": "codex", "source_file": "f.jsonl", "line": 4}
USER = {"family": "user", "source": "user:request", "text": "窓は？"}
HUMAN = {"family": "document", "sovereign": "document", "source": "memo.txt", "text": "窓が光った。"}
W5F_MEMORY_IDS = {"store_id": "store-w5f-test", "confirm_id": "0123456789abcdef01234567"}


def _synthetic(kind, verdict, sources, **extra):
    return {"kind": kind, "verdict": verdict, "text": "窓が光ります。", "door": "chat", "sources": sources,
            "evidence": [s["text"] for s in sources if isinstance(s, dict) and "text" in s],
            "trace": [{"part": "p", "status": "ran"}], **extra}


SOURCE_SHAPES = [
    [GEN],
    [USER, GEN],
    [GEN, GEN],
    [{**GEN, "origin": "generated"}, "junk", None, 3],           # non-dict elements next to a generated one
    [USER, {**GEN}, {"family": "user"}],
    [GEN, {"origin": None, "family": "user", "text": "x"}],        # origin None is not evidence
]


@pytest.mark.parametrize("sources", SOURCE_SHAPES)
@pytest.mark.parametrize("kind, verdict", [("answer", "ANSWER"), ("compose", "ANSWER"), ("social", None),
                                           ("answer", None), ("compose", None), ("skill", "ANSWER"),
                                           ("created", "CREATED")])
@pytest.mark.parametrize("mode", ["legacy", "round5", "engine"])
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_p2_synthetic_results_with_generated_sources_never_come_out_as_an_answer(
        tmp_path, monkeypatch, sources, kind, verdict, mode, human, ref):
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "none"))
    result = _synthetic(kind, verdict, copy.deepcopy(sources))
    before = copy.deepcopy(result)
    policy = bp.AskPolicy(request_kind="factual", human_present=human, show_reference=ref)
    out, rc = bp.apply_to_ask(result, policy, query="窓は？", mode=mode, documents=[])
    assert result == before                                   # the input is not modified
    assert rc == 0
    assert out["kind"] not in ("answer", "compose", "social", "skill", "created")
    assert out["verdict"] not in ("ANSWER", "CREATED", None)
    assert not out["basis_policy"]["outcome"].startswith("ANSWER_")
    assert _state(out) != "answer"
    assert out["basis_policy"]["applied"] is True
    assert "basis_origin" not in out and "lines" not in out and out["sources"] == []
    assert list(out)[-1] == "basis_policy"


@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_a_mix_of_human_and_generated_sources_abstains(human, ref):
    # W5-f（F-4、分類の規則 v5）: 退役した自己申告の入力に有効な識別子を与え、人と生成の混合を検査する。
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    result = _synthetic("answer", "ANSWER", [{**HUMAN, **W5F_MEMORY_IDS, "family": "memory_sovereign", "origin": "human_confirmed"}, GEN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                              query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["basis"] == "MIXED" and out["basis_policy"]["in_table"] is False
    assert out["basis_policy"]["outcome"] == "ABSTAIN"


def test_sources_that_are_not_evidence_are_not_a_human_basis():
    result = _synthetic("answer", "ANSWER", [{"family": "x", "origin": "constructed", "text": "t"},
                                             {"family": "x", "origin": "testimony", "text": "t2"}])
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_NO_HUMAN_BASIS"
    assert out["basis_policy"]["counts"]["non_evidence"] == 2


def test_a_refusal_that_carries_generated_sources_stays_a_refusal_and_loses_the_bodies():
    result = _synthetic("unknown", "UNKNOWN_SOMETHING", [USER, GEN])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_SOMETHING"
    assert "窓が光った。" not in json.dumps(out, ensure_ascii=False)
    assert out["basis_policy"]["outcome"] == "ABSTAIN"


def test_a_human_answer_is_passed_through_unchanged_apart_from_the_policy_note():
    # W5-f（F-4、分類の規則 v5）: 退役した自己申告の入力に有効な識別子を与え、人の回答の通過を検査する。
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    result = _synthetic("answer", "ANSWER", [USER, {**HUMAN, **W5F_MEMORY_IDS, "family": "memory_sovereign", "origin": "human_confirmed"}])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert rc == 0 and _without(out, "basis_policy") == result
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["applied"] is True


# ========================================================== J4: results that cite nothing
@pytest.mark.parametrize("query", ["こんにちは", "ありがとう。"])
def test_a_result_with_no_cited_source_is_passed_through_and_the_pass_is_recorded(tmp_path, monkeypatch, capsys,
                                                                                 query):
    _index(tmp_path, monkeypatch)
    raw = _roundtrip(Vera().load_store(_load(str(tmp_path / "s.json"))).ask(query))
    rc, out = _ask(tmp_path, capsys, query)
    assert rc == 0
    assert _without(out, "basis_policy") == raw
    assert out["basis_policy"]["applied"] is False and out["basis_policy"]["reason"] == "NO_CITED_SOURCES"
    assert out["basis_policy"]["counts"]["generated"] == 0 and list(out)[-1] == "basis_policy"


@pytest.mark.parametrize("query", ["-5 と 3 の和は？", "りんごとは何ですか？"])
def test_a_refusal_that_cites_nothing_is_kept_as_it_was_and_typed_abstain(tmp_path, monkeypatch, capsys, query):
    _index(tmp_path, monkeypatch)
    raw = _roundtrip(Vera().load_store(_load(str(tmp_path / "s.json"))).ask(query))
    assert raw.get("kind") == "unknown" or str(raw.get("verdict")).startswith("UNKNOWN")
    assert not raw.get("sources")
    rc, out = _ask(tmp_path, capsys, query)
    assert rc == 0 and _without(out, "basis_policy") == raw
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and out["basis_policy"]["basis"] == "NONE"


def test_a_result_with_a_generated_source_is_always_applied(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    for flags in FLAG_SETS:
        out = _ask(tmp_path, capsys, Q, *flags)[1]
        assert out["basis_policy"]["applied"] is True and out["basis_policy"]["counts"]["generated"] >= 1


def test_a_request_text_source_alone_does_not_count_as_a_citation():
    result = _synthetic("answer", "ANSWER", [USER])
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert out["basis_policy"]["applied"] is False and _without(out, "basis_policy") == result


# ======================================================================== E: no fact claimed
@pytest.mark.parametrize("kind", ["creative", "paraphrase", "style", "example"])
@pytest.mark.parametrize("flags", [[], ["--human-present"], ["--show-generated-reference"]])
def test_a_request_that_claims_no_fact_may_use_generated_material_and_is_typed_constructed(
        tmp_path, monkeypatch, capsys, kind, flags):
    _index(tmp_path, monkeypatch)
    raw = _roundtrip(Vera().load_store(_load(str(tmp_path / "s.json"))).ask(Q))
    rc, out = _ask(tmp_path, capsys, Q, "--request-kind", kind, *flags)
    assert rc == 0 and out["constructed"] is True
    assert out["kind"] == raw["kind"] and out["verdict"] == raw["verdict"]
    assert out["basis_policy"]["outcome"] == "CONSTRUCTED" and out["basis_policy"]["kind_class"] == "NON_FACTUAL"
    assert out["text"] == raw["text"]


def test_a_non_factual_request_with_no_material_still_abstains(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    rc, out = _ask(tmp_path, capsys, "りんごとは何ですか？", "--request-kind", "creative")
    assert rc == 0 and "constructed" not in out and str(out["verdict"]).startswith("UNKNOWN")
    assert out["basis_policy"]["outcome"] == "ABSTAIN"


# ================================================ document answers keep their text (round 5)
def test_a_document_answer_keeps_its_text_and_is_typed_human_basis(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "none"))
    memo = tmp_path / "memo.txt"
    memo.write_text("花子は太郎に資料を渡した。", encoding="utf-8")
    q = "誰が太郎に資料を渡しましたか？"
    v = Vera(mode="round5")
    v.load_documents([str(memo)])
    raw = _roundtrip(v.ask(q))
    rc, out = _ask(tmp_path, capsys, q, "--mode", "round5", "--document", str(memo))
    assert rc == 0 and out["text"] == raw["text"] == "agent: 花子"
    assert _stable(_without(out, "basis_policy")) == _stable(raw)
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["basis"] == "HUMAN"


def test_a_document_that_does_not_answer_stays_an_abstention(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "none"))
    memo = tmp_path / "memo.txt"
    memo.write_text("花子は太郎に資料を渡した。", encoding="utf-8")
    q = "誰が次郎に鍵を渡しましたか？"
    v = Vera(mode="round5")
    v.load_documents([str(memo)])
    raw = _roundtrip(v.ask(q))
    rc, out = _ask(tmp_path, capsys, q, "--mode", "round5", "--document", str(memo))
    assert rc == 0 and out["verdict"] != "ANSWER" and out["kind"] != "answer"
    # W3-c4: the later stage adds `question_cross` and one step of the trace to an abstention of this kind; nothing else of the abstention changes
    assert [t["state"] for t in out["trace"] if t.get("part") == "question_cross"] == ["NO_ATTESTED_CELL"] and out["question_cross"]["mapped_to"] == "ORIGINAL"
    shown = _without(out, "basis_policy", "question_cross")
    shown["trace"] = [t for t in out["trace"] if t.get("part") != "question_cross"]
    assert _stable(shown) == _stable(raw)
    assert out["basis_policy"]["outcome"] == "ABSTAIN"


# ==================================================================== P5: the reference column
BODY_ROWS = ROWS[:2]


def _bodies_outside(out: dict, *allowed: str) -> list:
    rest = {k: v for k, v in out.items() if k not in allowed}
    text = json.dumps(rest, ensure_ascii=False)
    return [b for b in ROWS if b in text]


@pytest.mark.parametrize("flags", [[], ["--human-present"]])
def test_p5_the_reference_column_is_off_by_default_and_no_body_appears_anywhere(tmp_path, monkeypatch, capsys,
                                                                               flags):
    _index(tmp_path, monkeypatch)
    rc, out = _ask(tmp_path, capsys, Q, *flags)
    assert rc == 0 and "reference_generated" not in out and "reference_state" not in out
    assert _bodies_outside(out, "confirm") == []
    assert out["basis_policy"]["show_reference"] is False


@pytest.mark.parametrize("flags", [["--show-generated-reference"],
                                   ["--show-generated-reference", "--human-present"]])
def test_p5_with_the_reference_on_the_bodies_appear_only_in_their_own_keys(tmp_path, monkeypatch, capsys, flags):
    _index(tmp_path, monkeypatch)
    rc, out = _ask(tmp_path, capsys, Q, *flags)
    assert rc == 0
    assert _bodies_outside(out, "reference_generated", "confirm") == []
    ref = out["reference_generated"]
    assert sorted(r["text"] for r in ref) == sorted(BODY_ROWS)
    for item in ref:
        assert set(item) >= {"text", "family", "source_id", "model", "effort"}
        assert item["model"] == "UNKNOWN_NOT_RECORDED" and item["effort"] == "UNKNOWN_NOT_RECORDED"
        assert item["family"] == "local" and item["source_id"].startswith("local:")
    assert out["reference_state"] == "FOUND"


@pytest.mark.parametrize("flags", FLAG_SETS)
def test_p5_no_file_is_written_by_asking_with_the_reference_on_or_off(tmp_path, monkeypatch, capsys, flags):
    _index(tmp_path, monkeypatch)
    sov.create(str(tmp_path / "sov"), "s1", "o", consent_promote=True)
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(tmp_path / "sov"))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    before = _snapshot(tmp_path)
    _ask(tmp_path, capsys, Q, *flags)
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "s.json").exists()


def test_p5_the_reference_never_enters_the_memory_ledger_the_index_or_the_sovereign(tmp_path, monkeypatch, capsys):
    idx = _index(tmp_path, monkeypatch)
    sov.create(str(tmp_path / "sov"), "s1", "o", consent_promote=True)
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(tmp_path / "sov"))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    idx_before = _snapshot(idx)
    _ask(tmp_path, capsys, Q, "--show-generated-reference", "--human-present")
    assert _snapshot(idx) == idx_before
    assert sov.open_ledger(str(tmp_path / "sov"), "s1").events() == []
    assert not (tmp_path / "s.json").exists()


def test_the_reference_column_is_present_even_when_nothing_was_cited(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "none"))
    rc, out = _ask(tmp_path, capsys, "こんにちは", "--show-generated-reference")
    assert rc == 0 and out["reference_generated"] == [] and out["reference_state"] == "NO_GENERATED_SOURCES"
    assert out["basis_policy"]["applied"] is False


def test_a_rejected_sentence_is_not_hidden_from_the_reference_but_marked(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    sov.create(str(tmp_path / "sov"), "s1", "o", consent_promote=True)
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(tmp_path / "sov"))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    cid = _ask(tmp_path, capsys, Q, "--human-present")[1]["confirm"]["id"]
    assert _ask(tmp_path, capsys, Q, "--confirm", cid, "no")[1]["verdict"] == "REJECTED_GENERATED_RECORDED"
    out = _ask(tmp_path, capsys, Q, "--show-generated-reference")[1]
    assert len(out["reference_generated"]) == 2
    assert all(r["rejected_by_user"] is True for r in out["reference_generated"])


# ================================================================ withheld form, arguments
def test_the_withheld_note_names_what_was_withheld_without_the_text(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    out = _ask(tmp_path, capsys, Q)[1]
    w = out["withheld"]
    assert w["verdict"] == "ANSWER" and w["kind"] == "answer" and w["basis_origin"] == "generated"
    assert w["generated_source_count"] == 2 and w["families"] == ["local", "user"]
    assert _bodies_outside(out) == []


@pytest.mark.parametrize("args", [["--confirm", "abc", "maybe"], ["--confirm", "abc"]])
def test_a_bad_confirm_argument_is_typed_and_exits_2(tmp_path, capsys, args):
    try:
        rc, out = _ask(tmp_path, capsys, "こんにちは", *args)
    except SystemExit as exc:                                   # argparse refuses a missing second value
        assert exc.code == 2
        return
    assert rc == 2 and out["kind"] == "unknown" and out["verdict"].startswith("UNKNOWN_")


def test_confirm_with_a_request_that_claims_no_fact_is_refused(tmp_path, capsys):
    rc, out = _ask(tmp_path, capsys, "こんにちは", "--confirm", "abc", "yes", "--request-kind", "creative")
    assert rc == 2 and out["kind"] == "unknown" and out["verdict"].startswith("UNKNOWN_")


def test_an_existing_configuration_error_keeps_its_place_before_the_new_ones(tmp_path, capsys):
    rc, out = _ask(tmp_path, capsys, "こんにちは", "--document", "x.txt", "--confirm", "abc", "maybe")
    assert rc == 2 and out["verdict"] == "UNKNOWN_ROUTE_CONFIGURATION"
    assert out["reason"] == "--document requires --mode round5"


def test_a_wrong_request_kind_is_refused_by_the_parser(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--store", str(tmp_path / "s.json"), "ask", "こんにちは", "--request-kind", "poem"])
    assert exc.value.code == 2


def test_the_default_entrance_kind_is_factual(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    out = _ask(tmp_path, capsys, Q)[1]
    assert out["basis_policy"]["request_kind"] == bp.ENTRY_REQUEST_KIND["ask"] == "factual"
    assert out["basis_policy"]["human_present"] is False and out["basis_policy"]["show_reference"] is False


def test_the_policy_note_always_carries_the_schema_and_the_table_version(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    for flags in FLAG_SETS:
        note = _ask(tmp_path, capsys, Q, *flags)[1]["basis_policy"]
        assert note["schema"] == "verantyx.basis_policy/1" and note["table_version"] == 1
        assert {"counts", "sovereign", "form", "outcome", "in_table"} <= set(note)


# ============================================ a generated basis is not hidden by where it is cited
@pytest.mark.parametrize("human", [False, True])
def test_p2_generated_sources_only_inside_lines_are_still_judged(human):
    result = {"kind": "answer", "verdict": "ANSWER", "text": "窓が光ります。", "sources": [],
              "lines": [{"text": "窓が光ります。", "sources": [GEN]}]}
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human), query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] != "ANSWER"
    assert out["basis_policy"]["applied"] is True and out["basis_policy"]["counts"]["generated"] == 1
    assert "lines" not in out


def test_the_same_source_cited_twice_is_counted_once():
    result = _synthetic("answer", "ANSWER", [GEN])
    result["lines"] = [{"text": "x", "sources": [dict(GEN)]}]
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert out["basis_policy"]["counts"]["generated"] == 1


@pytest.mark.parametrize("human", [False, True])
def test_p2_a_declared_generated_basis_without_any_visible_source_is_still_judged(human):
    result = {"kind": "answer", "verdict": "ANSWER", "text": "窓が光ります。", "sources": [],
              "basis_origin": "generated"}
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human), query="q", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] != "ANSWER"
    assert out["basis_policy"]["basis"] == "GENERATED" and out["basis_policy"]["applied"] is True


# ---------------------------------------------------------------- round 2: a half-refused type never survives
# A result whose ``kind`` says "answer" but whose ``verdict`` says "UNKNOWN_..." (or the other way round) is
# "refused" to the policy, yet the scorer reads the answer side first.  Whatever the policy builds anew must
# read as an abstention to the scorer, however the upstream type was torn.
MIXED_TYPES = [("answer", "UNKNOWN_X"), ("unknown", "ANSWER"), ("created", "ABSTAIN_Y"), ("skill", "UNKNOWN_Z"),
               ("not_yet", "CREATED"), ("social", "UNKNOWN_W"), ("compose", "AMBIGUOUS_V")]


@pytest.mark.parametrize("sources", SOURCE_SHAPES)
@pytest.mark.parametrize("kind, verdict", MIXED_TYPES)
@pytest.mark.parametrize("mode", ["legacy", "round5", "engine"])
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_p2_a_half_refused_type_with_generated_sources_reads_as_an_abstention(
        tmp_path, monkeypatch, sources, kind, verdict, mode, human, ref):
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "none"))
    result = _synthetic(kind, verdict, copy.deepcopy(sources), status="PARTIAL_COMPLETENESS_UNVERIFIED")
    before = copy.deepcopy(result)
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                              query="窓は？", mode=mode, documents=[])
    assert result == before and rc == 0
    assert _state(out) == "abstain"
    assert not out["basis_policy"]["outcome"].startswith("ANSWER_")
    assert out["kind"] in bp.REFUSAL_KINDS and out["verdict"].startswith(bp.REFUSAL_PREFIXES + ("CONFIRM_REQUEST",))
    assert "status" not in out and "lines" not in out and out["sources"] == []


@pytest.mark.parametrize("extra", [{"status": "PARTIAL_COMPLETENESS_UNVERIFIED"}, {"verdict": "PARTIAL"}])
def test_a_partial_marker_is_not_carried_into_what_the_policy_builds(extra):
    result = {**_synthetic("unknown", "UNKNOWN_SOMETHING", [GEN]), **extra}
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert _state(out) == "abstain" and out.get("status") is None and out["verdict"] != "PARTIAL"


@pytest.mark.parametrize("kind, verdict", [("answer", "UNKNOWN_X"), ("unknown", "ANSWER"), ("created", "ABSTAIN_Y")])
def test_a_consistent_refusal_keeps_its_own_type_and_a_torn_one_is_made_whole(kind, verdict):
    out, _rc = bp.apply_to_ask(_synthetic(kind, verdict, [GEN]), bp.AskPolicy(), query="q", mode="legacy",
                               documents=[])
    assert out["kind"] in bp.REFUSAL_KINDS and out["verdict"].startswith(bp.REFUSAL_PREFIXES)
    assert out["verdict"] == (verdict if verdict.startswith(bp.REFUSAL_PREFIXES) else "UNKNOWN_NO_HUMAN_BASIS")


def test_a_refusal_whose_own_text_quotes_a_generated_sentence_does_not_carry_the_text():
    result = {**_synthetic("unknown", "UNKNOWN_SOMETHING", [GEN]), "text": "たしか「窓が光った。」だと思う。"}
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert "窓が光った。" not in json.dumps(out, ensure_ascii=False)
    assert _state(out) == "abstain"


def test_a_refusal_whose_text_quotes_nothing_generated_keeps_its_text():
    result = {**_synthetic("unknown", "UNKNOWN_SOMETHING", [GEN]), "text": "いまは答えられません。"}
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="q", mode="legacy", documents=[])
    assert out["text"] == "いまは答えられません。"


@pytest.mark.parametrize("kind, verdict", MIXED_TYPES + [("answer", "ANSWER")])
def test_every_failed_confirmation_reads_as_an_abstention(tmp_path, monkeypatch, kind, verdict):
    result = _synthetic(kind, verdict, [GEN])
    policy = bp.AskPolicy(confirm=("not-this-id", "yes"))
    out, rc = bp.apply_to_ask(result, policy, query="窓は？", mode="legacy", documents=[])
    assert rc == 1 and out["verdict"] == "UNKNOWN_CONFIRM_ID" and _state(out) == "abstain"
    claim_id = bp._confirm_id("窓は？", "窓が光ります。", [GEN])
    ok = _synthetic("answer", "ANSWER", [GEN])
    out, rc = bp.apply_to_ask(ok, bp.AskPolicy(confirm=(claim_id, "yes")), query="窓は？", mode="legacy",
                              documents=[])
    assert rc == 1 and out["verdict"] == "CONFIRM_REQUEST" and _state(out) == "abstain"
    assert out["basis_policy"]["sovereign"]["state"] == "UNKNOWN_NO_SOVEREIGN"
    root = tmp_path / "sov"
    assert sov.create(str(root), "s1", "o", consent_promote=False)["verdict"] == "CREATED"
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    out, rc = bp.apply_to_ask(ok, bp.AskPolicy(confirm=(claim_id, "yes")), query="窓は？", mode="legacy",
                              documents=[])
    assert rc == 1 and out["verdict"] == "NO_CONSENT" and _state(out) == "abstain" and out["wrote"] == 0


def test_the_scorer_state_of_every_policy_output_that_is_not_an_answer_is_abstain(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    for flags in FLAG_SETS:
        out = _ask(tmp_path, capsys, Q, *flags)[1]
        if not out["basis_policy"]["outcome"].startswith(("ANSWER_", "CONSTRUCTED")):
            assert _state(out) == "abstain", (flags, out["kind"], out["verdict"])

"""W5-c (attack wave 3, A1 and A2): a source whose origin is unknown is not a human source, and a
confirmation id is bound to the sovereign it was issued for.

Pre-registered in docs/BASIS_POLICY.md (section ``prereg-w5c``) before this file was written.
Synthetic data only: no live model, no evaluation bank. Helpers are copied on purpose (tests/ is not a package).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools.bank_score.adapters import _state
from tools.build_p4_corpus_index import build
from verantyx import ability_corpus
from verantyx import basis_policy as bp
from verantyx import sovereign as sov
from verantyx.cli import main

REPO = Path(__file__).resolve().parents[1]
Q = "雨の日に傘を持たずに外出すると、どうなりますか？"
ROWS = ["雨の日に傘を持たずに出たら、髪が濡れた。", "雨の日に傘を持たずに出たら、服が濡れた。"]
FLAG_SETS = ([], ["--human-present"], ["--show-generated-reference"],
             ["--human-present", "--show-generated-reference"])

GEN = {"family": "local", "source": "g0", "text": "窓が光った。", "sha": "w", "origin": "generated",
       "generator": "codex", "source_file": "f.jsonl", "line": 4}
USER = {"family": "user", "source": "user:request", "text": "窓は？"}
HUMAN = {"family": "document", "sovereign": "document", "source": "memo.txt", "text": "窓が光った。"}
BODY = "窓が光った。"


@pytest.fixture(autouse=True)
def _no_outside_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


def _synthetic(kind, verdict, sources, text="窓が光ります。", **extra):
    return {"kind": kind, "verdict": verdict, "text": text, "door": "chat", "sources": sources,
            "evidence": [s["text"] for s in sources if isinstance(s, dict) and "text" in s],
            "trace": [{"part": "p", "status": "ran"}], **extra}


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _index(tmp_path: Path, monkeypatch, *, null_origin: bool = False) -> Path:
    src = tmp_path / "local.jsonl"
    src.write_text("".join(json.dumps({"text": t, "source": f"g{i}", "scene": "雨", "sha": f"h{i}"},
                                      ensure_ascii=False) + "\n" for i, t in enumerate(ROWS)),
                   encoding="utf-8")
    db = tmp_path / "idx" / "local.db"
    build(src, db, "local")
    if null_origin:
        with sqlite3.connect(db) as con:
            con.execute("UPDATE rows SET origin = NULL")
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    return tmp_path / "idx"


def _ask(tmp_path, capsys, query, *args):
    rc = main(["--store", str(tmp_path / "s.json"), "ask", query, *args])
    return rc, json.loads(capsys.readouterr().out)


def _use(monkeypatch, root, sid):
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", sid)


def _src(family, origin="MISSING", **extra):
    s = {"family": family, "source": "x1", "text": BODY, "source_file": "f.jsonl", "line": 1,
         "sha": "s1", **extra}
    if origin != "MISSING":
        s["origin"] = origin
    return s


# ======================================================================= N1 (A1): unknown origin
ORIGINS = ["MISSING", None, "", "GENERATED", "Generated", " generated", "zzz"]
RESULT_TYPES = [("answer", "ANSWER"), ("compose", "ANSWER"), ("social", None), ("answer", None),
                ("skill", "ANSWER"), ("created", "CREATED"), ("unknown", "UNKNOWN_X"),
                ("answer", "UNKNOWN_X")]
MODES = ("legacy", "round5", "engine")
COMPANIONS = {"alone": [], "request": [USER], "human_document": [HUMAN], "generated": [GEN]}


@pytest.mark.parametrize("origin", ORIGINS, ids=lambda o: f"origin-{o!r}")
@pytest.mark.parametrize("family", ability_corpus.FAMILIES)
def test_n1_an_index_family_source_without_a_declared_origin_never_answers(family, origin):
    """family (all of ability_corpus.FAMILIES) x origin x result type x mode x human x reference x companion."""
    n = 0
    for (kind, verdict) in RESULT_TYPES:
        for mode in MODES:
            for human in (False, True):
                for ref in (False, True):
                    for name, extra in COMPANIONS.items():
                        sources = [_src(family, origin)] + copy.deepcopy(extra)
                        result = _synthetic(kind, verdict, sources)
                        before = copy.deepcopy(result)
                        combo = (family, origin, kind, verdict, mode, human, ref, name)
                        out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                                                  query="窓は？", mode=mode, documents=[])
                        n += 1
                        assert result == before, combo
                        assert rc == 0, combo
                        assert not out["basis_policy"]["outcome"].startswith("ANSWER_"), combo
                        assert out["kind"] != "answer" and out["verdict"] != "ANSWER", combo
                        assert _state(out) == "abstain", combo
                        assert "confirm" not in out and out["sources"] == [], combo
                        assert out["verdict"] != "CONFIRM_REQUEST", combo
                        if not bp._is_refused(result):
                            assert out["verdict"] == "UNKNOWN_ORIGIN_SOURCE", combo
                        assert out["basis_policy"]["counts"]["unknown_origin"] >= 1, combo
                        assert out["basis_policy"]["basis_original"] in ("UNKNOWN_ORIGIN", "NONE"), combo
    assert n == len(RESULT_TYPES) * len(MODES) * 2 * 2 * len(COMPANIONS)


@pytest.mark.parametrize("origin", ["", "GENERATED", "zzz", 3])
@pytest.mark.parametrize("family", ["x", "document"])
@pytest.mark.parametrize("companion", ["alone", "human_document", "generated"])
@pytest.mark.parametrize("human", [False, True])
def test_n1_a_source_outside_the_index_families_with_an_unknown_origin_value_never_answers(
        family, origin, companion, human):
    sources = [_src(family, origin)] + copy.deepcopy(COMPANIONS[companion])
    out, rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", sources), bp.AskPolicy(human_present=human),
                              query="窓は？", mode="legacy", documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_ORIGIN_SOURCE"
    assert not out["basis_policy"]["outcome"].startswith("ANSWER_") and out["basis_policy"]["outcome"] == "ABSTAIN"
    assert "confirm" not in out and _state(out) == "abstain"
    assert out["basis_policy"]["counts"]["unknown_origin_values"] == {str(origin): 1}


@pytest.mark.parametrize("family", ["local", "x"])
@pytest.mark.parametrize("origin", ["constructed", "testimony"])
def test_n1_a_declared_non_evidence_origin_is_unchanged(family, origin):
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src(family, origin)]), bp.AskPolicy(),
                               query="窓は？", mode="legacy", documents=[])
    assert out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_NO_HUMAN_BASIS"
    assert out["basis_policy"]["counts"]["non_evidence"] == 1
    assert out["basis_policy"]["counts"]["unknown_origin"] == 0
    assert out["basis_policy"]["counts"]["unknown_origin_values"] == {}


@pytest.mark.parametrize("kind", ["creative", "paraphrase", "style", "example"])
@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
@pytest.mark.parametrize("origin", ["MISSING", None, "", "zzz"])
def test_n1_a_request_that_claims_no_fact_reads_unknown_origin_on_the_generated_side(kind, human, ref, origin):
    result = _synthetic("answer", "ANSWER", [_src("local", origin)])
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(request_kind=kind, human_present=human, show_reference=ref),
                              query="窓は？", mode="legacy", documents=[])
    note = out["basis_policy"]
    assert rc == 0 and note["outcome"] == "CONSTRUCTED" and out["constructed"] is True
    assert note["basis"] == "UNKNOWN_ORIGIN" and note["in_table"] is False
    assert note["reason"] == "UNKNOWN_ORIGIN_READ_AS_GENERATED"


def test_n1_a_refusal_that_quotes_an_unknown_origin_sentence_does_not_carry_the_text():
    result = _synthetic("unknown", "UNKNOWN_SOMETHING", [_src("local")], text="たしか「窓が光った。」だと思う。")
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="窓は？", mode="legacy", documents=[])
    assert BODY not in json.dumps(out, ensure_ascii=False)
    assert _state(out) == "abstain" and out["verdict"] == "UNKNOWN_SOMETHING" and out["sources"] == []


def test_n1_a_refusal_that_quotes_nothing_keeps_its_text_but_still_loses_the_bodies():
    result = _synthetic("unknown", "UNKNOWN_SOMETHING", [_src("local")], text="いまは答えられません。",
                        lines=[{"text": BODY, "sources": [_src("local")]}])
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query="窓は？", mode="legacy", documents=[])
    assert out["text"] == "いまは答えられません。" and "lines" not in out and out["sources"] == []


def test_n1_an_unknown_origin_source_only_inside_lines_is_still_judged():
    result = {"kind": "answer", "verdict": "ANSWER", "text": "窓が光ります。", "sources": [],
              "lines": [{"text": BODY, "sources": [_src("local")]}]}
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=True), query="窓は？", mode="legacy",
                              documents=[])
    assert rc == 0 and out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_ORIGIN_SOURCE"
    assert out["basis_policy"]["applied"] is True and "lines" not in out


@pytest.mark.parametrize("human", [False, True])
def test_n1_unknown_origin_alone_is_not_passed_through_as_a_result_that_cites_nothing(human):
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("local", None)]),
                               bp.AskPolicy(human_present=human), query="窓は？", mode="legacy", documents=[])
    assert out["basis_policy"]["applied"] is True and out["basis_policy"].get("reason") != "NO_CITED_SOURCES"


def test_n1_an_unknown_origin_source_is_not_shown_as_a_generated_sentence():
    result = _synthetic("answer", "ANSWER", [_src("local", None)])
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=True, show_reference=True), query="窓は？",
                               mode="legacy", documents=[])
    assert out["reference_generated"] == [] and out["reference_state"] == "NO_GENERATED_SOURCES"
    assert "confirm" not in out and BODY not in json.dumps(
        {k: v for k, v in out.items() if k != "basis_policy"}, ensure_ascii=False)


def test_n1_a_confirmation_cannot_be_given_for_an_unknown_origin_source(tmp_path, monkeypatch):
    root = tmp_path / "sov"
    assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
    _use(monkeypatch, root, "s1")
    before = _snapshot(tmp_path)
    claim = "窓が光ります。"
    candidates = [bp._confirm_id("窓は？", claim, [_src("local", "generated")]), "abc"]
    for given in candidates:
        out, rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("local", None)]),
                                  bp.AskPolicy(confirm=(given, "yes")), query="窓は？", mode="legacy",
                                  documents=[])
        assert rc == 1 and out["verdict"] == "UNKNOWN_CONFIRM_ID" and _state(out) == "abstain", out
    assert _snapshot(tmp_path) == before


def test_n1_a_recorded_yes_does_not_turn_an_unknown_origin_answer_into_a_human_one(tmp_path, monkeypatch):
    root = tmp_path / "sov"
    assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
    _use(monkeypatch, root, "s1")
    claim = "窓が光ります。"
    record = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation",
              "confirm_id": "abc", "query": "窓は？", "claim": claim, "generated_sources": [],
              "table_version": 1, "origin": "human_confirmed"}
    assert sov.append_basis_confirmation(str(root), "s1", record)["verdict"] == "APPENDED"
    upgraded, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [GEN]), bp.AskPolicy(), query="窓は？",
                                    mode="legacy", documents=[])
    assert upgraded["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"      # the record does lift a generated basis
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("local", None)]), bp.AskPolicy(),
                               query="窓は？", mode="legacy", documents=[])
    assert out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_ORIGIN_SOURCE"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0


@pytest.mark.parametrize("flags", FLAG_SETS, ids=lambda f: "+".join(f) or "plain")
@pytest.mark.parametrize("sovereign", ["none", "consenting"])
def test_n1_through_main_a_null_origin_index_never_answers(tmp_path, monkeypatch, capsys, flags, sovereign):
    _index(tmp_path, monkeypatch, null_origin=True)
    if sovereign == "consenting":
        root = tmp_path / "sov"
        assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
        _use(monkeypatch, root, "s1")
    rc, out = _ask(tmp_path, capsys, Q, *flags)
    assert rc == 0, out
    assert out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_ORIGIN_SOURCE", out
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and out["basis_policy"]["counts"]["unknown_origin"] >= 1
    assert "confirm" not in out and _state(out) == "abstain"


def test_n1_through_main_a_request_that_claims_no_fact_is_constructed(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch, null_origin=True)
    rc, out = _ask(tmp_path, capsys, Q, "--request-kind", "creative")
    assert rc == 0 and out["basis_policy"]["outcome"] == "CONSTRUCTED" and out["constructed"] is True
    assert out["basis_policy"]["reason"] == "UNKNOWN_ORIGIN_READ_AS_GENERATED"


def test_n1_through_a_real_subprocess_a_null_origin_index_never_answers(tmp_path, monkeypatch):
    idx = _index(tmp_path, monkeypatch, null_origin=True)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path), "PYTHONPATH": str(REPO),
           "PYTHONDONTWRITEBYTECODE": "1", "VERA_P4_INDEX": str(idx)}
    for flags in FLAG_SETS:
        done = subprocess.run([sys.executable, "-m", "verantyx.cli", "--store", str(tmp_path / "s.json"),
                               "ask", Q, *flags], cwd=REPO, env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=120)
        assert done.returncode == 0, done.stderr[-400:]
        out = json.loads(done.stdout)
        assert out["kind"] == "unknown" and out["verdict"] == "UNKNOWN_ORIGIN_SOURCE", out
        assert _state(out) == "abstain"


# ------------------------------------------------------------------ the classification itself
def test_w5c_the_versions_and_the_table_are_as_registered():
    assert bp.TABLE_VERSION == 1 and bp.SCHEMA == "verantyx.basis_policy/1"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 規則 7・8 が変わったので CLASSIFY_VERSION は 3（prereg-w5c-r3 節）
    assert bp.CLASSIFY_VERSION == 3 and bp.CONFIRM_ID_VERSION == 2
    assert len(bp.TABLE) == 24 and bp.BASES == ("HUMAN", "GENERATED", "NONE")
    assert bp.DECLARED_ORIGINS == ("generated", "human_confirmed", "constructed", "testimony")
    assert bp.UNKNOWN_ORIGIN == "UNKNOWN_ORIGIN"


@pytest.mark.parametrize("family", ability_corpus.FAMILIES)
@pytest.mark.parametrize("origin", ["MISSING", None, "", "GENERATED", "zzz", 3])
def test_w5c_rule_4_an_index_family_without_a_declared_origin_is_unknown(family, origin):
    sc = bp.classify_sources([_src(family, origin)])
    assert sc.unknown_origin == 1 and sc.unknown_origin_by_family == {family: 1}
    assert sc.basis == "UNKNOWN_ORIGIN" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts == {"human": 0, "generated": 0, "non_evidence": 0, "request_text": 0, "unreadable": 0}
    assert sc.cited == 1
    assert bp.decide("factual", sc, False, False).basis == "UNKNOWN_ORIGIN"


def test_w5c_counts_keep_their_five_keys_and_the_new_numbers_live_beside_them():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の HUMAN を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([_src("local", None), _src("x", "zzz"), GEN, {**HUMAN, "origin": "human_confirmed"}, USER, "junk"])
    assert set(sc.counts) == {"human", "generated", "non_evidence", "request_text", "unreadable"}
    assert sc.counts == {"human": 1, "generated": 1, "non_evidence": 1, "request_text": 1, "unreadable": 1}
    assert sc.unknown_origin == 1 and sc.unknown_origin_values == {"zzz": 1}
    assert sc.cited == 5 and sc.policy_basis == "UNKNOWN_ORIGIN" and sc.basis == "UNKNOWN_ORIGIN"
    d = sc.to_dict()
    assert d["unknown_origin"] == 1 and d["unknown_origin_by_family"] == {"local": 1}
    assert d["unknown_origin_values"] == {"zzz": 1}


def test_w5c_a_value_outside_the_closed_vocabulary_alone_changes_the_policy_basis_not_the_basis():
    sc = bp.classify_sources([_src("x", "zzz")])
    assert sc.basis == "NONE" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts["non_evidence"] == 1 and sc.non_evidence_by_origin == {"zzz": 1}
    assert bp.classify_sources([_src("x", "constructed")]).policy_basis == "NONE"
    assert bp.classify_sources([_src("x", "testimony")]).policy_basis == "NONE"
    assert bp.classify_sources([GEN]).policy_basis == "GENERATED"
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 最後の行の入力を明示の人にした（期待は同じ）。強める側の assert を 1 行足した
    assert bp.classify_sources([{**HUMAN, "origin": "human_confirmed"}]).policy_basis == "HUMAN"
    assert bp.classify_sources([HUMAN]).policy_basis == "UNKNOWN_ORIGIN"


@pytest.mark.parametrize("src, expected", [
    ({"origin": "zzz"}, True), ({"origin": ""}, True), ({"origin": "GENERATED"}, True), ({"origin": 3}, True),
    ({"origin": ["generated"]}, True), ({"origin": None}, False), ({}, False),
    ({"origin": "generated"}, False), ({"origin": "human_confirmed"}, False),
    ({"origin": "constructed"}, False), ({"origin": "testimony"}, False), ("junk", False)])
def test_w5c_unknown_value(src, expected):
    assert bp._unknown_value(src) is expected


def test_w5c_decide_takes_unknown_origin_as_a_basis_outside_the_table():
    for human in (False, True):
        for ref in (False, True):
            d = bp.decide("factual", "UNKNOWN_ORIGIN", human, ref)
            assert d.outcome == "ABSTAIN" and d.in_table is False and d.basis == "UNKNOWN_ORIGIN"
            assert d.reason == "NOT_IN_TABLE:UNKNOWN_ORIGIN_SOURCE"
            for kind in ("creative", "paraphrase", "style", "example"):
                n = bp.decide(kind, "UNKNOWN_ORIGIN", human, ref)
                assert n.outcome == "CONSTRUCTED" and n.in_table is False
                assert n.reason == "UNKNOWN_ORIGIN_READ_AS_GENERATED"
    assert bp.decide("factual", "UNKNOWN", False, False).reason == "NOT_IN_TABLE:basis"
    assert bp.decide("factual", "UNKNOWN_ORIGIN_X", False, False).reason == "NOT_IN_TABLE:basis"
    assert bp.decide("factual", "MIXED", True, True).reason == "NOT_IN_TABLE:BASIS_MIXED_NOT_IN_TABLE"


def test_w5c_the_policy_note_carries_the_new_versions_and_numbers():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_src("pro", "")]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    note = out["basis_policy"]
    assert note["schema"] == "verantyx.basis_policy/1" and note["table_version"] == 1
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 注記の classify_version は 3
    assert note["classify_version"] == 3 and note["confirm_id_version"] == 2
    assert note["counts"]["unknown_origin"] == 1 and note["counts"]["unknown_origin_by_family"] == {"pro": 1}
    assert out["withheld"]["unknown_origin_source_count"] == 1


def test_w5c_known_hole_a_source_outside_the_index_families_without_origin_is_still_human():
    """Closed in round 3 (docs/BASIS_POLICY.md section 11, hole 1; the auditor's decision of 2026-10-03 20:40):
    a source outside the index families with no origin is an unknown origin, not a human one. The name is kept
    on purpose (the auditor's rule: an existing test's name is never changed; the before/after text is in the docs)."""
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [HUMAN]), bp.AskPolicy(), query="窓は？",
                               mode="legacy", documents=[])
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and out["basis_policy"]["basis"] == "UNKNOWN_ORIGIN"
    assert out["verdict"] == "UNKNOWN_ORIGIN_SOURCE"
    assert bp.classify_sources([{"family": "x", "text": "t"}]).policy_basis == "UNKNOWN_ORIGIN"


# ================================================================ N2 (A2): the id belongs to a sovereign
def _stores(tmp_path, *, consent_second: bool = True):
    root = tmp_path / "sov"
    assert sov.create(str(root), "first", "owner-a", consent_promote=True)["verdict"] == "CREATED"
    assert sov.create(str(root), "second", "owner-b", consent_promote=consent_second)["verdict"] == "CREATED"
    return root


RESULT = _synthetic("answer", "ANSWER", [GEN])


def _issue(monkeypatch, root, sid):
    if root is not None:
        _use(monkeypatch, root, sid)
    out, rc = bp.apply_to_ask(copy.deepcopy(RESULT), bp.AskPolicy(human_present=True), query="窓は？",
                              mode="legacy", documents=[])
    assert rc == 0 and out["verdict"] == "CONFIRM_REQUEST", out
    return out


def _confirm(given, answer="yes"):
    return bp.apply_to_ask(copy.deepcopy(RESULT), bp.AskPolicy(confirm=(given, answer)), query="窓は？",
                           mode="legacy", documents=[])


def _events(root, sid):
    return sov.open_ledger(str(root), sid).events()


def test_n2_an_id_issued_for_first_cannot_be_written_to_second(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    issued = _issue(monkeypatch, root, "first")
    cid = issued["confirm"]["id"]
    assert issued["confirm"]["destination"]["store_id"] == "first"
    before = _snapshot(tmp_path)
    _use(monkeypatch, root, "second")
    out, rc = _confirm(cid)
    assert rc == 1 and out["verdict"] == "CONFIRM_TARGET_MISMATCH" and out["wrote"] == 0, out
    assert out["confirm"]["issued_for"]["store_id"] == "first"
    assert out["confirm"]["destination"]["store_id"] == "second"
    assert _state(out) == "abstain" and out["kind"] == "unknown"
    assert _snapshot(tmp_path) == before and _events(root, "second") == []
    # and the reverse direction
    _use(monkeypatch, root, "second")
    issued2 = _issue(monkeypatch, None, "second")
    assert issued2["confirm"]["id"] != cid
    _use(monkeypatch, root, "first")
    out, rc = _confirm(issued2["confirm"]["id"], "no")
    assert rc == 1 and out["verdict"] == "CONFIRM_TARGET_MISMATCH"
    assert _snapshot(tmp_path) == before


def test_n2_the_mismatch_is_reached_before_the_door_is_ever_called(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    cid = _issue(monkeypatch, root, "first")["confirm"]["id"]

    def boom(*_a, **_k):
        raise AssertionError("the sovereign's door must not be called")
    monkeypatch.setattr(sov, "append_basis_confirmation", boom)
    _use(monkeypatch, root, "second")
    assert _confirm(cid)[0]["verdict"] == "CONFIRM_TARGET_MISMATCH"


def test_n2_through_main_an_id_issued_for_first_cannot_be_written_to_second(tmp_path, monkeypatch, capsys):
    _index(tmp_path, monkeypatch)
    root = _stores(tmp_path)
    _use(monkeypatch, root, "first")
    rc, issued = _ask(tmp_path, capsys, Q, "--human-present")
    assert rc == 0 and issued["verdict"] == "CONFIRM_REQUEST"
    cid = issued["confirm"]["id"]
    before = _snapshot(tmp_path / "sov")
    _use(monkeypatch, root, "second")
    rc, out = _ask(tmp_path, capsys, Q, "--confirm", cid, "yes")
    assert rc == 1 and out["verdict"] == "CONFIRM_TARGET_MISMATCH" and out["wrote"] == 0, out
    assert _snapshot(tmp_path / "sov") == before and _events(root, "second") == []
    _use(monkeypatch, root, "first")
    rc, out = _ask(tmp_path, capsys, Q, "--confirm", cid, "yes")
    assert rc == 0 and out["verdict"] == "CONFIRMED_HUMAN_RECORD" and out["wrote"] == 1 and out["store_id"] == "first"


def test_n2_an_id_issued_with_no_sovereign_cannot_be_written_to_a_consenting_one(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    issued = _issue(monkeypatch, None, "ignored")
    assert issued["basis_policy"]["sovereign"]["state"] == "UNKNOWN_NO_SOVEREIGN"
    cid = issued["confirm"]["id"]
    assert cid == bp._confirm_id("窓は？", "窓が光ります。", [GEN])
    before = _snapshot(tmp_path)
    _use(monkeypatch, root, "first")
    out, rc = _confirm(cid)
    assert rc == 1 and out["verdict"] == "CONFIRM_TARGET_MISMATCH" and out["wrote"] == 0
    assert out["confirm"]["issued_for"] == {"state": "NO_DESTINATION"}
    assert _snapshot(tmp_path) == before


def test_n2_an_id_from_another_root_is_not_a_known_id_here(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    other = tmp_path / "other"
    assert sov.create(str(other), "first", "owner-z", consent_promote=True)["verdict"] == "CREATED"
    cid = _issue(monkeypatch, root, "first")["confirm"]["id"]
    before = _snapshot(tmp_path)
    _use(monkeypatch, other, "first")
    out, rc = _confirm(cid)
    assert rc == 1 and out["verdict"] == "UNKNOWN_CONFIRM_ID" and out["wrote"] == 0
    assert _snapshot(tmp_path) == before and _events(other, "first") == []
    assert sov.basis_confirmation_destination(str(root), "first")["structure_ref"] \
        != sov.basis_confirmation_destination(str(other), "first")["structure_ref"]


def test_n2_after_a_detach_nothing_is_written(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    cid = _issue(monkeypatch, root, "first")["confirm"]["id"]
    assert sov.detach(str(root), "first")["verdict"] == "DETACHED"
    before = _snapshot(tmp_path)
    out, rc = _confirm(cid)
    assert rc == 1 and out["verdict"] == "CONFIRM_REQUEST" and out["wrote"] == 0
    assert out["basis_policy"]["sovereign"]["state"] == "DETACHED"
    assert _snapshot(tmp_path) == before


def test_n2_a_sovereign_without_consent_answers_no_consent_before_the_target_is_compared(tmp_path, monkeypatch):
    root = _stores(tmp_path, consent_second=False)
    cid = _issue(monkeypatch, root, "first")["confirm"]["id"]
    before = _snapshot(tmp_path)
    _use(monkeypatch, root, "second")
    out, rc = _confirm(cid)
    assert rc == 1 and out["verdict"] == "NO_CONSENT" and out["wrote"] == 0 and _state(out) == "abstain"
    assert _snapshot(tmp_path) == before


def test_n2_an_unknown_or_foreign_id_is_not_a_known_id(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    cid = _issue(monkeypatch, root, "first")["confirm"]["id"]
    before = _snapshot(tmp_path)
    for given in (cid[:-1] + ("0" if cid[-1] != "0" else "1"), "x", cid + "0", cid.upper()):
        out, rc = _confirm(given)
        assert rc == 1 and out["verdict"] == "UNKNOWN_CONFIRM_ID" and out["wrote"] == 0, given
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("answer, verdict, status", [
    ("yes", "CONFIRMED_HUMAN_RECORD", "HUMAN_CONFIRMED"),
    ("no", "REJECTED_GENERATED_RECORDED", "REJECTED_GENERATED")])
def test_n2_the_right_destination_still_writes_and_the_record_names_its_destination(
        tmp_path, monkeypatch, answer, verdict, status):
    root = _stores(tmp_path)
    issued = _issue(monkeypatch, root, "second")
    cid = issued["confirm"]["id"]
    out, rc = _confirm(cid, answer)
    assert rc == 0 and out["verdict"] == verdict and out["wrote"] == 1 and out["store_id"] == "second", out
    dest = sov.basis_confirmation_destination(str(root), "second")
    assert dest["store_id"] == "second" and isinstance(dest["structure_ref"], str)
    payload = _events(root, "second")[-1]["payload"]
    assert payload["status"] == status and payload["confirm_id"] == cid and payload["destination"] == dest
    assert _events(root, "first") == []
    if answer == "yes":
        again, rc = bp.apply_to_ask(copy.deepcopy(RESULT), bp.AskPolicy(), query="窓は？", mode="legacy",
                                    documents=[])
        assert rc == 0 and again["verdict"] == "ANSWER" and again["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
        assert again["sources"][0]["origin"] == "human_confirmed" and again["sources"][0]["store_id"] == "second"


def test_n2_the_question_shows_its_destination_and_writes_nothing(tmp_path, monkeypatch):
    root = _stores(tmp_path)
    before = _snapshot(tmp_path)
    issued = _issue(monkeypatch, root, "first")
    dest = sov.basis_confirmation_destination(str(root), "first")
    conf = issued["confirm"]
    assert conf["destination"] == {"state": "ACTIVE_CONSENTED", **dest}
    assert conf["draft_record"]["payload"]["destination"] == dest
    assert len(conf["id"]) == 24 and conf["id"] in conf["how_to_answer"]
    assert _snapshot(tmp_path) == before
    for flags in (bp.AskPolicy(human_present=True, show_reference=True), bp.AskPolicy(show_reference=True)):
        bp.apply_to_ask(copy.deepcopy(RESULT), flags, query="窓は？", mode="legacy", documents=[])
    assert _snapshot(tmp_path) == before


def test_n2_without_a_destination_the_question_has_no_destination_and_the_old_id(tmp_path, monkeypatch):
    issued = _issue(monkeypatch, None, "x")
    conf = issued["confirm"]
    assert conf["destination"] == {"state": "UNKNOWN_NO_SOVEREIGN", "store_id": None, "structure_ref": None}
    assert "destination" not in conf["draft_record"]["payload"]


def test_n2_asking_never_creates_the_structure_ledger_of_an_empty_root(tmp_path, monkeypatch):
    root = tmp_path / "empty-root"
    root.mkdir()
    _use(monkeypatch, root, "first")
    for human in (False, True):
        bp.apply_to_ask(copy.deepcopy(RESULT), bp.AskPolicy(human_present=human), query="窓は？", mode="legacy",
                        documents=[])
        _confirm("abc")
    assert sorted(root.iterdir()) == []
    assert sov.basis_confirmation_store_ids(str(root)) == [] and sorted(root.iterdir()) == []
    with pytest.raises(sov.UnknownStore):
        sov.basis_confirmation_destination(str(root), "first")
    assert sorted(root.iterdir()) == []


def test_n2_the_destination_readers_are_read_only_and_deterministic(tmp_path):
    root = _stores(tmp_path)
    before = _snapshot(tmp_path)
    assert sov.basis_confirmation_store_ids(str(root)) == ["first", "second"]
    a, b = (sov.basis_confirmation_destination(str(root), s) for s in ("first", "second"))
    assert a["store_id"] == "first" and b["store_id"] == "second" and a["structure_ref"] == b["structure_ref"]
    assert a == sov.basis_confirmation_destination(str(root), "first")
    with pytest.raises(sov.UnknownStore):
        sov.basis_confirmation_destination(str(root), "third")
    assert _snapshot(tmp_path) == before


# --------------------------------------------------------------- the sovereign's door, called directly
def _payload(**extra):
    p = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation",
         "confirm_id": "abc", "query": "窓は？", "claim": "窓が光ります。",
         "generated_sources": [{"family": "local", "source_id": "local:f:1", "sha": "h0"}],
         "table_version": 1, "origin": "human_confirmed"}
    p.update(extra)
    return p


def test_n2_mouth_a_destination_that_is_not_this_sovereign_is_refused(tmp_path):
    root = _stores(tmp_path)
    mine = sov.basis_confirmation_destination(str(root), "second")
    before = _snapshot(tmp_path)
    wrong_store = sov.basis_confirmation_destination(str(root), "first")
    wrong_ref = {**mine, "structure_ref": "0" * 64}
    for dest in (wrong_store, wrong_ref, {**mine, "structure_ref": None}):
        out = sov.append_basis_confirmation(str(root), "second", _payload(destination=dest))
        assert out["verdict"] == "CONFIRM_TARGET_MISMATCH" and out["wrote"] == 0, out
        assert out["expected"] == mine and out["given"] == dest
    assert _snapshot(tmp_path) == before
    ok = sov.append_basis_confirmation(str(root), "second", _payload(destination=mine))
    assert ok["verdict"] == "APPENDED" and ok["wrote"] == 1
    assert _events(root, "second")[-1]["payload"]["destination"] == mine


@pytest.mark.parametrize("bad", [
    {"store_id": "second"}, {"structure_ref": "x"}, {}, "second", ["second"], None, 3,
    {"store_id": "second", "structure_ref": "x", "extra": 1}])
def test_n2_mouth_a_malformed_destination_is_a_bad_payload(tmp_path, bad):
    root = _stores(tmp_path)
    before = _snapshot(tmp_path)
    out = sov.append_basis_confirmation(str(root), "second", _payload(destination=bad))
    assert out["verdict"] == "BAD_PAYLOAD" and out["wrote"] == 0
    assert _snapshot(tmp_path) == before


def test_n2_mouth_a_payload_without_a_destination_is_taken_as_before(tmp_path):
    root = _stores(tmp_path)
    out = sov.append_basis_confirmation(str(root), "second", _payload())
    assert out["verdict"] == "APPENDED" and out["wrote"] == 1
    assert _events(root, "second")[-1]["payload"] == _payload()


def test_n2_mouth_consent_and_state_are_still_checked_before_the_destination(tmp_path):
    root = _stores(tmp_path, consent_second=False)
    dest = sov.basis_confirmation_destination(str(root), "second")
    assert sov.append_basis_confirmation(str(root), "second", _payload(destination=dest))["verdict"] == "NO_CONSENT"
    assert sov.append_basis_confirmation(str(root), "nope", _payload(destination=dest))["verdict"] == "UNKNOWN_STORE"


# --------------------------------------------------------------------------------- the id itself
def test_n2_the_id_without_a_destination_is_the_old_id_and_with_one_it_differs():
    old = bp._confirm_id("窓は？", "窓が光ります。", [GEN])
    assert old == bp._confirm_id("窓は？", "窓が光ります。", [GEN], None)
    blob = json.dumps({"query": "窓は？", "claim": "窓が光ります。",
                       "generated": [["local", "f.jsonl", 4, "w"]]},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert old == hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]
    d1 = {"store_id": "first", "structure_ref": "r1"}
    ids = {bp._confirm_id("窓は？", "窓が光ります。", [GEN], d)
           for d in (d1, {**d1, "store_id": "second"}, {**d1, "structure_ref": "r2"})}
    assert len(ids) == 3 and old not in ids and all(len(i) == 24 for i in ids)
    assert bp._confirm_id("窓は？", "窓が光ります。", [GEN], d1) == bp._confirm_id("窓は？", "窓が光ります。", [GEN], dict(d1))

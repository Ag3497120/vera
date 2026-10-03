"""W5-c round 3 (the auditor's decision of 2026-10-03 20:40): a source whose origin is unknown is not a human
source *anywhere* (not only in the index families), and a recorded "yes" lifts only a *generated* basis.

Pre-registered in docs/BASIS_POLICY.md (section ``prereg-w5c-r3``) before this file was written. This file is
frozen before the implementation changes (artifacts/w5-c/frozen_tests.sha256, line EXTENDED). Synthetic data only:
no live model, no evaluation bank. Helpers are copied on purpose (tests/ is not a package).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.bank_score.adapters import _state
from verantyx import basis_policy as bp
from verantyx import sovereign as sov
from verantyx.cli import main

Q = "窓は？"
BODY = "窓が光った。"
OTHER_CLAIM = "人の答え。"          # the sentence a human confirmed: different from every result's own ``text``
GEN = {"family": "local", "source": "g0", "text": BODY, "sha": "w", "origin": "generated",
       "generator": "codex", "source_file": "f.jsonl", "line": 4}
USER = {"family": "user", "source": "user:request", "text": "窓は？"}
HUMAN_CONFIRMED = {"family": "memory_sovereign", "source": "e1", "text": BODY, "origin": "human_confirmed"}
DOC = {"family": "document", "sovereign": "document", "source": "memo.txt", "text": BODY}   # no ``origin`` key
MEMO_ARG = ["memo.txt"]

#: families that are not in ``ability_corpus.FAMILIES`` (plus a missing key, a None and a non-string)
OTHER_FAMILIES = ["document", "general", "x", "jawiki", "conversation_form", "code_parts", "pun_lexicon",
                  "LOCAL", " local", "MISSING", None, 3]
ORIGINS_UNSET = ["MISSING", None]
RESULT_TYPES = [("answer", "ANSWER"), ("social", None), ("answer", "PARTIAL"), ("unknown", "UNKNOWN_X"),
                ("refusal", "UNKNOWN_Y")]
MODES = ("legacy", "round5", "engine")
COMPANIONS = {"alone": [], "request": [USER], "generated": [GEN], "human_confirmed": [HUMAN_CONFIRMED]}


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


def _use(monkeypatch, root, sid):
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", sid)


def _fsrc(family, origin="MISSING", **extra):
    """A source of family ``family`` ("MISSING": the key is absent) with ``origin`` ("MISSING": the key is absent)."""
    s = {"source": "x1", "text": BODY, "source_file": "f.jsonl", "line": 1, "sha": "s1", **extra}
    if family != "MISSING":
        s["family"] = family
    if origin != "MISSING":
        s["origin"] = origin
    return s


def _family_key(family):
    """The key ``unknown_origin_by_family`` uses: the family string, or ``(none)`` (absent key, None, non-string)."""
    return family if isinstance(family, str) and family != "MISSING" else "(none)"


# ============================================================ rule 8: anything else is an unknown origin
@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
@pytest.mark.parametrize("family", OTHER_FAMILIES, ids=lambda f: f"family-{f!r}")
def test_r3_rule_8_a_source_with_no_origin_that_nothing_vouches_for_is_an_unknown_origin(family, origin):
    sc = bp.classify_sources([_fsrc(family, origin)])
    assert sc.unknown_origin == 1 and sc.counts["human"] == 0
    assert sc.basis == "UNKNOWN_ORIGIN" and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.cited == 1
    assert sc.unknown_origin_by_family == {_family_key(family): 1}
    assert sc.counts == {"human": 0, "generated": 0, "non_evidence": 0, "request_text": 0, "unreadable": 0}


# ============================================================ rule 7: the documents the user handed over
@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
def test_r3_rule_7_a_document_the_user_handed_over_is_human(origin):
    sc = bp.classify_sources([_fsrc("document", origin)], user_documents=True)
    assert sc.counts["human"] == 1 and sc.unknown_origin == 0
    assert sc.basis == "HUMAN" and sc.policy_basis == "HUMAN" and sc.cited == 1
    assert bp.classify_sources([_fsrc("document", origin)], user_documents=False).policy_basis == "UNKNOWN_ORIGIN"
    assert bp.classify_sources([_fsrc("document", origin)]).policy_basis == "UNKNOWN_ORIGIN"


@pytest.mark.parametrize("origin", ["", "zzz", "human", 3], ids=lambda o: f"origin-{o!r}")
def test_r3_rule_7_does_not_apply_to_a_document_with_an_origin_value(origin):
    sc = bp.classify_sources([_fsrc("document", origin)], user_documents=True)
    assert sc.counts["human"] == 0 and sc.policy_basis == "UNKNOWN_ORIGIN"
    assert sc.counts["non_evidence"] == 1 and sc.unknown_origin_values == {str(origin): 1}


@pytest.mark.parametrize("family", [f for f in OTHER_FAMILIES if f != "document"], ids=lambda f: f"family-{f!r}")
@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
def test_r3_rule_7_applies_to_the_family_document_and_to_nothing_else(family, origin):
    sc = bp.classify_sources([_fsrc(family, origin)], user_documents=True)
    assert sc.unknown_origin == 1 and sc.counts["human"] == 0 and sc.policy_basis == "UNKNOWN_ORIGIN"


@pytest.mark.parametrize("user_documents", [False, True])
def test_r3_the_request_text_and_a_declared_human_confirmation_do_not_depend_on_user_documents(user_documents):
    sc = bp.classify_sources([USER, HUMAN_CONFIRMED], user_documents=user_documents)
    assert sc.counts["request_text"] == 1 and sc.counts["human"] == 1 and sc.unknown_origin == 0
    assert sc.cited == 1 and sc.basis == "HUMAN"


# ============================================================ N1, the entrance function, new range
def _run_unset_origin_family(family, origin):
    n = 0
    for (kind, verdict) in RESULT_TYPES:
        for mode in MODES:
            for documents in ([], MEMO_ARG):
                if mode == "round5" and documents and family == "document":
                    continue                       # the user's own document: judged in the next test
                for human in (False, True):
                    for ref in (False, True):
                        for name, extra in COMPANIONS.items():
                            sources = [_fsrc(family, origin)] + copy.deepcopy(extra)
                            result = _synthetic(kind, verdict, sources)
                            before = copy.deepcopy(result)
                            combo = (family, origin, kind, verdict, mode, bool(documents), human, ref, name)
                            out, rc = bp.apply_to_ask(result, bp.AskPolicy(human_present=human, show_reference=ref),
                                                      query=Q, mode=mode, documents=list(documents))
                            n += 1
                            assert result == before, combo
                            assert rc == 0, combo
                            note = out["basis_policy"]
                            assert note["applied"] is True, combo
                            assert not note["outcome"].startswith("ANSWER_"), combo
                            assert note["outcome"] not in ("CONFIRM_REQUEST", "REFERENCE_GENERATED"), combo
                            assert out["kind"] != "answer" and out["verdict"] != "ANSWER", combo
                            assert _state(out) == "abstain", combo
                            assert out["sources"] == [] and "confirm" not in out, combo
                            assert out["verdict"] != "CONFIRM_REQUEST", combo
                            assert note["counts"]["unknown_origin"] >= 1, combo
                            if not bp._is_refused(result):
                                assert out["verdict"] == "UNKNOWN_ORIGIN_SOURCE", combo
    return n


@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
@pytest.mark.parametrize("family", OTHER_FAMILIES, ids=lambda f: f"family-{f!r}")
def test_r3_n1_a_source_with_no_origin_outside_the_index_families_never_answers(family, origin):
    """family x origin (absent / None) x result type x mode x documents x human x reference x companion, except
    the user's own document under round5 with ``documents`` (the next test)."""
    n = _run_unset_origin_family(family, origin)
    per_family = len(RESULT_TYPES) * len(MODES) * 2 * 2 * 2 * len(COMPANIONS)          # 480
    skipped = len(RESULT_TYPES) * 1 * 1 * 2 * 2 * len(COMPANIONS) if family == "document" else 0   # 80
    assert n == per_family - skipped


def test_r3_n1_the_combinations_add_up():
    assert (len(OTHER_FAMILIES) * len(ORIGINS_UNSET) * 480) - (len(ORIGINS_UNSET) * 80) == 11360


# ============================================================ the user's own document is still answered
def _doc_result(kind="answer", verdict="ANSWER", extra=None):
    return _synthetic(kind, verdict, [copy.deepcopy(DOC)] + copy.deepcopy(extra or []), text=BODY)


@pytest.mark.parametrize("origin", ORIGINS_UNSET, ids=lambda o: f"origin-{o!r}")
def test_r3_a_document_the_user_handed_over_is_answered_unchanged(origin):
    src = _fsrc("document", origin, source="memo.txt")
    result = _synthetic("answer", "ANSWER", [src], text=BODY)
    before = copy.deepcopy(result)
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(), query=Q, mode="round5", documents=MEMO_ARG)
    assert rc == 0 and result == before
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["basis"] == "HUMAN"
    assert out["basis_policy"]["counts"]["human"] == 1 and out["basis_policy"]["counts"]["unknown_origin"] == 0
    assert {k: v for k, v in out.items() if k != "basis_policy"} == before
    assert out["kind"] == "answer" and out["verdict"] == "ANSWER"


def test_r3_a_generated_sentence_next_to_the_users_document_is_mixed_not_unknown_origin():
    out, _rc = bp.apply_to_ask(_doc_result(extra=[GEN]), bp.AskPolicy(), query=Q, mode="round5", documents=MEMO_ARG)
    assert out["basis_policy"]["basis"] == "MIXED" and out["verdict"] == "UNKNOWN_BASIS_NOT_IN_TABLE"
    assert out["basis_policy"]["outcome"] == "ABSTAIN" and _state(out) == "abstain"
    assert out["withheld"]["unknown_origin_source_count"] == 0


@pytest.mark.parametrize("mode, documents", [("legacy", []), ("legacy", MEMO_ARG), ("round5", []),
                                              ("engine", []), ("engine", MEMO_ARG)])
def test_r3_the_same_document_source_outside_round5_with_documents_is_an_unknown_origin(mode, documents):
    out, _rc = bp.apply_to_ask(_doc_result(), bp.AskPolicy(), query=Q, mode=mode, documents=list(documents))
    assert out["verdict"] == "UNKNOWN_ORIGIN_SOURCE" and out["basis_policy"]["outcome"] == "ABSTAIN"
    assert out["withheld"]["unknown_origin_source_count"] == 1 and _state(out) == "abstain"
    assert out["basis_policy"]["counts"]["unknown_origin_by_family"] == {"document": 1}


# ============================================================ withheld: counted from the classification
@pytest.mark.parametrize("mode, documents, sources", [
    ("legacy", [], [_fsrc("local", None)]),
    ("legacy", [], [_fsrc("local", "zzz")]),
    ("legacy", [], [_fsrc("general", None), _fsrc("jawiki", "MISSING")]),
    ("legacy", [], [_fsrc("document", None), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), _fsrc("general", None)]),
    ("round5", MEMO_ARG, [_fsrc("document", ""), GEN]),
    ("round5", MEMO_ARG, [_fsrc("document", None), _fsrc("document", "zzz"), _fsrc("local", None)]),
    ("round5", [], [_fsrc("document", None), GEN]),
    ("engine", MEMO_ARG, [_fsrc("document", None), _fsrc("MISSING", None)]),
], ids=lambda v: None)
def test_r3_the_withheld_count_is_the_classified_count(mode, documents, sources):
    result = _synthetic("answer", "ANSWER", copy.deepcopy(sources))
    out, _rc = bp.apply_to_ask(result, bp.AskPolicy(), query=Q, mode=mode, documents=list(documents))
    user_documents = mode == "round5" and bool(documents)
    assert "withheld" in out
    assert out["withheld"]["unknown_origin_source_count"] == len(bp._unknown_origin_sources(sources, user_documents))
    sc = bp.classify_sources(sources, user_documents=user_documents)
    assert out["withheld"]["unknown_origin_source_count"] == sc.unknown_origin + sum(sc.unknown_origin_values.values())


# ============================================================ R-b: a recorded "yes" lifts only a generated basis
def _sovereign_with_yes(tmp_path, monkeypatch, query=Q):
    root = tmp_path / "sov"
    assert sov.create(str(root), "s1", "o", consent_promote=True)["verdict"] == "CREATED"
    _use(monkeypatch, root, "s1")
    record = {"record": "basis_confirmation", "status": "HUMAN_CONFIRMED", "witness": "user_confirmation",
              "confirm_id": "abc", "query": query, "claim": OTHER_CLAIM, "generated_sources": [],
              "table_version": 1, "origin": "human_confirmed"}
    assert sov.append_basis_confirmation(str(root), "s1", record)["verdict"] == "APPENDED"
    return root


def _ask_with_record(sources, kind, verdict, *, human, ref, mode="legacy", documents=()):
    return bp.apply_to_ask(_synthetic(kind, verdict, copy.deepcopy(sources)),
                           bp.AskPolicy(human_present=human, show_reference=ref), query=Q, mode=mode,
                           documents=list(documents))


UNKNOWN_SOURCES = {f"local-origin-{o!r}": [_fsrc("local", o)] for o in ("MISSING", None, "", "zzz")}
UNKNOWN_SOURCES["legacy-document-no-origin"] = [copy.deepcopy(DOC)]
REFUSED_AND_ANSWER_TYPES = [("answer", "ANSWER"), ("unknown", "UNKNOWN_X"), ("refusal", "UNKNOWN_Y"),
                            ("answer", "UNKNOWN_X")]


@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
@pytest.mark.parametrize("name", list(UNKNOWN_SOURCES))
def test_r3_a_recorded_yes_does_not_lift_a_basis_with_an_unknown_origin(tmp_path, monkeypatch, name, human, ref):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    n = 0
    for (kind, verdict) in REFUSED_AND_ANSWER_TYPES:
        out, rc = _ask_with_record(UNKNOWN_SOURCES[name], kind, verdict, human=human, ref=ref)
        n += 1
        note = out["basis_policy"]
        assert rc == 0
        assert not note["outcome"].startswith("ANSWER_"), (name, kind, verdict)
        assert _state(out) == "abstain" and out["kind"] != "answer", (name, kind, verdict)
        assert note["sovereign"]["confirmed_records_used"] == 0, (name, kind, verdict)
        assert note["sovereign"]["confirmed_records_not_used"] == 1, (name, kind, verdict)
        assert out["sources"] == [], (name, kind, verdict)
        assert OTHER_CLAIM not in json.dumps(out, ensure_ascii=False), (name, kind, verdict)
    assert n == 4
    assert _snapshot(root) == before


@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
def test_r3_a_recorded_yes_still_lifts_a_generated_answer(tmp_path, monkeypatch, human, ref):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    out, rc = _ask_with_record([GEN], "answer", "ANSWER", human=human, ref=ref)
    assert rc == 0 and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["text"] == OTHER_CLAIM and out["kind"] == "answer"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 1
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 0
    assert _snapshot(root) == before


@pytest.mark.parametrize("human", [False, True])
@pytest.mark.parametrize("ref", [False, True])
@pytest.mark.parametrize("kind, verdict", REFUSED_AND_ANSWER_TYPES[1:])
def test_r3_a_refusal_with_a_generated_source_is_not_lifted_by_a_recorded_yes(tmp_path, monkeypatch, kind, verdict,
                                                                              human, ref):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    out, rc = _ask_with_record([GEN], kind, verdict, human=human, ref=ref)
    note = out["basis_policy"]
    assert rc == 0 and note["outcome"] == "ABSTAIN" and _state(out) == "abstain" and out["kind"] != "answer"
    assert note["sovereign"]["confirmed_records_used"] == 0 and note["sovereign"]["confirmed_records_not_used"] == 1
    assert OTHER_CLAIM not in json.dumps(out, ensure_ascii=False)
    assert _snapshot(root) == before


def test_r3_a_result_that_cites_nothing_is_passed_through_and_the_record_is_not_used(tmp_path, monkeypatch):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    out, rc = _ask_with_record([], "answer", "ANSWER", human=False, ref=False)
    assert rc == 0 and out["basis_policy"]["applied"] is False and out["text"] == "窓が光ります。"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 1
    refused, _rc = _ask_with_record([], "unknown", "UNKNOWN_X", human=False, ref=False)
    assert refused["verdict"] == "UNKNOWN_X" and refused["basis_policy"]["outcome"] == "ABSTAIN"
    assert refused["basis_policy"]["sovereign"]["confirmed_records_used"] == 0
    assert OTHER_CLAIM not in json.dumps(refused, ensure_ascii=False)
    assert _snapshot(root) == before


def test_r3_the_users_own_document_answer_is_kept_and_the_record_is_not_used(tmp_path, monkeypatch):
    root = _sovereign_with_yes(tmp_path, monkeypatch)
    before = _snapshot(root)
    out, rc = _ask_with_record([DOC], "answer", "ANSWER", human=False, ref=False, mode="round5", documents=MEMO_ARG)
    assert rc == 0 and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["text"] == "窓が光ります。" and OTHER_CLAIM not in json.dumps(out, ensure_ascii=False)
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0
    assert out["basis_policy"]["sovereign"]["confirmed_records_not_used"] == 1
    assert _snapshot(root) == before


# ============================================================ versions
def test_r3_the_versions_are_as_registered():
    assert bp.CLASSIFY_VERSION == 3 and bp.CONFIRM_ID_VERSION == 2 and bp.TABLE_VERSION == 1
    assert bp.SCHEMA == "verantyx.basis_policy/1" and len(bp.TABLE) == 24


def test_r3_the_policy_note_carries_the_classify_version_3():
    out, _rc = bp.apply_to_ask(_synthetic("answer", "ANSWER", [_fsrc("general", None)]), bp.AskPolicy(), query=Q,
                               mode="legacy", documents=[])
    assert out["basis_policy"]["classify_version"] == 3 and out["basis_policy"]["confirm_id_version"] == 2
    assert out["basis_policy"]["table_version"] == 1


# ============================================================ one through the real entrance
def test_r3_through_main_the_users_document_is_still_a_human_basis(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "no-index-here"))
    memo = tmp_path / "memo.txt"
    memo.write_text("花子は太郎に資料を渡した。", encoding="utf-8")
    rc = main(["--store", str(tmp_path / "s.json"), "ask", "誰が太郎に資料を渡しましたか？", "--mode", "round5",
               "--document", str(memo)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS" and out["basis_policy"]["basis"] == "HUMAN", out
    assert out["basis_policy"]["counts"]["unknown_origin"] == 0
    assert out["verdict"] != "UNKNOWN_ORIGIN_SOURCE" and _state(out) != "abstain"

"""W5-e (docs/BASIS_POLICY.md, W5-e A-3): a self-declared ``origin == "human_confirmed"`` is not a human source by itself.

Rule v4 of ``_class_of``: ``human_confirmed`` classifies as human only for ``family == "memory_sovereign"`` (the sovereign's record) -- a
``family == "document"`` source goes through the body check of A1 whatever origin it claims, any other family that claims it is ``unknown_origin``.
The inputs of the counter-examples are in ``artifacts/w5-e/h4_inputs.json`` (frozen before this file and before the product change).
"""
import json
from pathlib import Path

import pytest

from verantyx import basis_policy as bp
from verantyx import sovereign as sov

HERE = Path(__file__).resolve().parent
H4 = json.loads((HERE.parent / "artifacts" / "w5-e" / "h4_inputs.json").read_text(encoding="utf-8"))
QUERY = H4["query"]
BODY = H4["document_body"]
W5F_MEMORY_IDS = {"store_id": "store-w5f-test", "confirm_id": "0123456789abcdef01234567"}
W5F_RETIRED_CONTROLS = {"H4-C2-memory-sovereign-self-declared-kept"}


@pytest.fixture(autouse=True)
def _no_outside_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


def _answer(src):
    return {"kind": "answer", "verdict": "ANSWER", "text": "答え。", "sources": [src], "evidence": [src.get("text", "")], "door": "t"}


def _run(case, tmp_path):
    doc = tmp_path / "memo.txt"
    doc.write_text(BODY, encoding="utf-8")
    documents = [str(doc)] if case["hand_over"] else []
    return bp.apply_to_ask(_answer(dict(case["source"])), bp.AskPolicy(), query=QUERY, mode="round5", documents=documents)


@pytest.mark.parametrize("case", H4["cases"], ids=lambda c: c["id"])
def test_h4_a_self_declared_human_confirmed_never_answers(case, tmp_path):
    out, _ = _run(case, tmp_path)
    assert not out["basis_policy"]["outcome"].startswith("ANSWER"), json.dumps(out, ensure_ascii=False)
    assert out["verdict"] != "ANSWER" and out["kind"] != "answer"
    assert out["basis_policy"]["basis_original"] == "UNKNOWN_ORIGIN" and out["basis_policy"]["counts"]["unknown_origin"] == 1


@pytest.mark.parametrize("case", H4["controls"], ids=lambda c: c["id"])
def test_h4_controls_that_are_really_human_still_answer(case, tmp_path):
    # W5-f（F-4、分類の規則 v5）: 凍結対照のうち退役した自己申告例だけを UNKNOWN_ORIGIN として扱う。
    out, _ = _run(case, tmp_path)
    if case["id"] in W5F_RETIRED_CONTROLS:
        assert out["basis_policy"]["basis_original"] == "UNKNOWN_ORIGIN", json.dumps(out, ensure_ascii=False)
        assert out["verdict"] != "ANSWER" and out["kind"] != "answer"
        return
    assert out["basis_policy"]["basis_original"] == "HUMAN" and out["basis_policy"]["outcome"].startswith("ANSWER"), json.dumps(out, ensure_ascii=False)
    assert out["verdict"] == "ANSWER"


def test_a3_the_classify_version_is_4_and_the_note_carries_it(tmp_path):
    # W5-f（F-4、分類の規則 v5）: 注記と分類器の版を 5 に更新する。
    assert bp.CLASSIFY_VERSION == 5
    out, _ = _run(H4["controls"][0], tmp_path)
    assert out["basis_policy"]["classify_version"] == 5
    assert bp.TABLE_VERSION == 1 and bp.CONFIRM_ID_VERSION == 2      # nothing else moved


# ------------------------------------------------------------------ the rule order of _class_of, one source at a time
def _cls(src, **kw):
    return bp._class_of(src, **kw)


def test_a3_document_with_human_confirmed_goes_through_the_body_check():
    docs = ["窓は午後に閉める。"]
    assert _cls({"family": "document", "origin": "human_confirmed", "text": "窓は午後に閉める。"}, user_documents=True, document_texts=docs) == "human"
    assert _cls({"family": "document", "origin": "human_confirmed", "text": "別の文。"}, user_documents=True, document_texts=docs) == "unknown_origin"
    assert _cls({"family": "document", "origin": "human_confirmed", "text": "窓は午後に閉める。"}, user_documents=False, document_texts=docs) == "unknown_origin"
    # the older contract (the caller has checked the body himself): document_texts None keeps a document source human
    assert _cls({"family": "document", "origin": "human_confirmed", "text": "どこにも無い"}, user_documents=True, document_texts=None) == "human"
    assert _cls({"family": "document", "origin": "human_confirmed", "text": "どこにも無い"}, user_documents=False, document_texts=None) == "unknown_origin"


def test_a3_the_sha256_form_of_a_document_source_is_checked_too():
    import hashlib
    body = "窓は午後に閉める。"
    good = {"family": "document", "origin": "human_confirmed", "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}
    bad = {"family": "document", "origin": "human_confirmed", "sha256": "0" * 64}
    assert _cls(good, user_documents=True, document_texts=[body]) == "human"
    assert _cls(bad, user_documents=True, document_texts=[body]) == "unknown_origin"


@pytest.mark.parametrize("family", ["local", "web", "user", "ほかの系列", "", None, 3])
def test_a3_any_other_family_that_claims_human_confirmed_is_unknown_origin(family):
    src = {"origin": "human_confirmed", "text": "窓は午後に閉める。"}
    if family is not None:
        src["family"] = family
    assert _cls(src, user_documents=True, document_texts=["窓は午後に閉める。"]) == "unknown_origin"
    assert _cls(src) == "unknown_origin"


def test_a3_a_missing_family_that_claims_human_confirmed_is_unknown_origin():
    assert _cls({"origin": "human_confirmed"}) == "unknown_origin"


def test_a3_the_sovereigns_records_are_human():
    # W5-f（F-4、分類の規則 v5）: id の形が合えば人、欠落すれば unknown_origin にする。
    assert _cls({**W5F_MEMORY_IDS, "family": "memory_sovereign", "origin": "human_confirmed"}) == "human"
    assert _cls({"family": "memory_sovereign", "origin": "human_confirmed"}) == "unknown_origin"


def test_a3_generated_goes_first_and_is_never_lifted_by_the_body_check():
    docs = ["窓は午後に閉める。"]
    for family in ("document", "memory_sovereign", "local"):
        assert _cls({"family": family, "origin": "generated", "text": "窓は午後に閉める。"}, user_documents=True, document_texts=docs) == "generated"


@pytest.mark.parametrize("origin", ["constructed", "testimony"])
def test_a3_a_document_with_a_declared_non_evidence_origin_is_not_lifted_by_the_body_check(origin):
    got = _cls({"family": "document", "origin": origin, "text": "窓は午後に閉める。"}, user_documents=True, document_texts=["窓は午後に閉める。"])
    assert got == "non_evidence"


def test_a3_unchanged_boundaries():
    docs = ["窓は午後に閉める。"]
    assert _cls("not a dict") == "unreadable"
    assert _cls({"family": "user", "text": "問い"}) == "request_text"
    assert _cls({"family": "document", "text": "窓は午後に閉める。"}, user_documents=True, document_texts=docs) == "human"      # A1 of W5-d, no origin
    assert _cls({"family": "document", "text": "無い文。"}, user_documents=True, document_texts=docs) == "unknown_origin"
    assert _cls({"family": "document", "origin": "weird", "text": "窓は午後に閉める。"}, user_documents=True, document_texts=docs) == "non_evidence"
    assert _cls({"family": "local", "text": "x"}) == "unknown_origin"


# ------------------------------------------------------------------ the sovereign's confirmation still lifts a generated answer (W6-a D)
CONFIRMED = "窓が光った。"


def _store(tmp_path, monkeypatch):
    root = str(tmp_path / "sov")
    assert sov.create(root, "s1", "owner", consent_promote=True)["verdict"] == "CREATED"
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", root)
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    return root


def _generated(claim):
    gen = {"family": "local", "source": "local:new:1", "source_file": "new.jsonl", "line": 1, "sha": "new", "origin": "generated", "text": claim}
    return {"kind": "answer", "verdict": "ANSWER", "text": claim, "sources": [gen], "evidence": [claim], "door": "t"}


def test_a3_a_recorded_yes_of_the_sovereign_still_answers_as_human_basis(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    q, rc = bp.apply_to_ask(_generated(CONFIRMED), bp.AskPolicy(human_present=True), query=QUERY, mode="legacy", documents=[])
    assert rc == 0 and q["verdict"] == "CONFIRM_REQUEST"
    got, rc = bp.apply_to_ask(_generated(CONFIRMED), bp.AskPolicy(confirm=(q["confirm"]["id"], "yes")), query=QUERY, mode="legacy", documents=[])
    assert rc == 0 and got["verdict"] == "CONFIRMED_HUMAN_RECORD" and got["wrote"] == 1
    out, _ = bp.apply_to_ask(_generated(CONFIRMED), bp.AskPolicy(), query=QUERY, mode="legacy", documents=[])
    assert out["verdict"] == "ANSWER" and out["text"] == CONFIRMED and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["basis_policy"]["sovereign"]["confirmed_records_used"] == 1
    src = out["sources"][0]
    assert src["family"] == "memory_sovereign" and src["origin"] == "human_confirmed" and src["store_id"] == "s1" and src["confirm_id"]
    # and the source that the policy itself built classifies as human under v4
    assert bp._class_of(src) == "human"

"""Executable attacks against W6-a's factual-answer and confirmation boundaries.

All evidence is synthetic. These tests call the same apply_to_ask function used by vera ask;
they do not start a live model or read any evaluation bank.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.build_p4_corpus_index import build
from verantyx import basis_policy as bp
from verantyx import sovereign as sov
from verantyx.ability_corpus import Corpus


QUERY = "窓は？"
HUMAN_CROSS = "花子は太郎に資料を渡した。"


@pytest.fixture(autouse=True)
def _clear_external_state(monkeypatch):
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)
    monkeypatch.delenv("VERA_P4_INDEX", raising=False)


def _answer(source: dict) -> dict:
    return {"kind": "answer", "verdict": "ANSWER", "text": "窓が光った。",
            "sources": [source], "evidence": [source.get("text", "")], "door": "synthetic"}


@pytest.mark.parametrize("origin", ["MISSING", None], ids=["origin-omitted", "origin-null"])
@pytest.mark.parametrize("mode", ["legacy", "round5", "engine"])
@pytest.mark.parametrize("human,reference", [(False, False), (False, True), (True, False), (True, True)])
def test_generated_family_with_unmarked_origin_must_not_become_a_factual_answer(
        tmp_path, origin, mode, human, reference):
    source_path = tmp_path / "local.jsonl"
    source_path.write_text(json.dumps({"text": "窓が光った。", "source": "generated-row-1",
                                      "scene": "synthetic", "sha": "row-sha"}, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    index_path = tmp_path / "index" / "local.db"
    build(source_path, index_path, "local")
    if origin is None:
        with sqlite3.connect(index_path) as db:
            db.execute("UPDATE rows SET origin = NULL")
    hits = Corpus(tmp_path / "index").search("窓", "local", 10)
    assert len(hits) == 1 and hits[0].text == "窓が光った。"
    source = hits[0].cite()
    if origin != "MISSING":
        assert source["origin"] is None
    else:
        source.pop("origin")
    out, rc = bp.apply_to_ask(_answer(source), bp.AskPolicy(human_present=human, show_reference=reference),
                              query=QUERY, mode=mode, documents=[])
    assert rc == 0
    detail = json.dumps(out, ensure_ascii=False, sort_keys=True)
    assert out["kind"] != "answer" and out["verdict"] != "ANSWER", detail
    assert not out["basis_policy"]["outcome"].startswith("ANSWER_"), detail


@pytest.mark.parametrize("origin", ["", "GENERATED"], ids=["empty-origin", "uppercase-origin"])
def test_noncanonical_origin_values_do_not_answer(origin):
    source = {"family": "local", "source": "generated-row-1", "text": "窓が光った。", "origin": origin}
    out, rc = bp.apply_to_ask(_answer(source), bp.AskPolicy(), query=QUERY,
                              mode="legacy", documents=[])
    assert rc == 0 and out["kind"] != "answer" and out["verdict"] != "ANSWER"
    assert out["basis_policy"]["outcome"] == "ABSTAIN"


@pytest.mark.parametrize("kind", ["FACTUAL", "Factual"])
def test_uppercase_request_kind_is_typed_as_outside_the_closed_table(kind):
    policy = bp.AskPolicy.from_args(SimpleNamespace(request_kind=kind, confirm=None))
    assert isinstance(policy, dict)
    assert policy["kind"] == "unknown" and policy["verdict"] == "UNKNOWN_BAD_REQUEST_KIND"


def test_confirmation_id_from_one_sovereign_cannot_be_replayed_into_another(tmp_path, monkeypatch):
    root = tmp_path / "sovereigns"
    assert sov.create(str(root), "first", "owner-a", consent_promote=True)["verdict"] == "CREATED"
    assert sov.create(str(root), "second", "owner-b", consent_promote=True)["verdict"] == "CREATED"
    source = {"family": "local", "source": "g1", "source_file": "local.jsonl", "line": 1,
              "sha": "same-row", "text": "窓が光った。", "origin": "generated"}
    result = _answer(source)
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "first")
    prompt, _ = bp.apply_to_ask(result, bp.AskPolicy(human_present=True), query=QUERY,
                                mode="legacy", documents=[])
    confirm_id = prompt["confirm"]["id"]
    assert prompt["confirm"]["destination"]["store_id"] == "first"

    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "second")
    saved, rc = bp.apply_to_ask(result, bp.AskPolicy(confirm=(confirm_id, "yes")), query=QUERY,
                                mode="legacy", documents=[])
    events = sov.open_ledger(str(root), "second").events()
    detail = json.dumps({"result": saved, "events": events}, ensure_ascii=False, sort_keys=True)
    assert saved.get("verdict") != "CONFIRMED_HUMAN_RECORD" and events == [], detail
    assert rc != 0


@pytest.mark.parametrize("tamper", ["change-id", "change-query"])
def test_fabricated_or_stale_confirmation_id_is_rejected_without_writing(tmp_path, monkeypatch, tamper):
    root = tmp_path / "sovereigns"
    assert sov.create(str(root), "first", "owner-a", consent_promote=True)["verdict"] == "CREATED"
    source = {"family": "local", "source": "g1", "source_file": "local.jsonl", "line": 1,
              "sha": "same-row", "text": "窓が光った。", "origin": "generated"}
    result = _answer(source)
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root))
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "first")
    prompt, _ = bp.apply_to_ask(result, bp.AskPolicy(human_present=True), query=QUERY,
                                mode="legacy", documents=[])
    confirm_id = prompt["confirm"]["id"]
    if tamper == "change-id":
        replacement = "0" if confirm_id[-1] != "0" else "1"
        supplied, query = confirm_id[:-1] + replacement, QUERY
    else:
        supplied, query = confirm_id, "別の問い"
    out, rc = bp.apply_to_ask(result, bp.AskPolicy(confirm=(supplied, "yes")), query=query,
                              mode="legacy", documents=[])
    events = sov.open_ledger(str(root), "first").events()
    assert rc == 1 and out["verdict"] == "UNKNOWN_CONFIRM_ID" and events == [], (out, events)


@pytest.mark.parametrize("row", ["次郎が花子に資料を渡さなかった。", "次郎が花子に資料を5冊渡した。"],
                         ids=["negation", "new-number"])
def test_c_does_not_borrow_polarity_changes_or_unverified_numbers(tmp_path, row):
    source_path = tmp_path / "local.jsonl"
    source_path.write_text(json.dumps({"text": row, "source": "generated-1", "scene": "scene",
                                      "sha": "generated-sha"}, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    build(source_path, tmp_path / "index" / "local.db", "local")
    res = bp.borrow_form(HUMAN_CROSS, corpus=Corpus(tmp_path / "index"))
    assert res.state != "FORM_BORROWED" and res.text is None, (row, res.to_dict(), res.text)

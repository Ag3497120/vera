"""W6-a C (form borrowing) and P3: the content of an answer comes from the human source; only the
phrasing may come from a generated sentence, and a role the human source does not have is never added.

Synthetic data only: the index is built in tmp_path with tools.build_p4_corpus_index.build and the
sentences are written for this file. Helpers are copied here on purpose: tests/ is not a package.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.build_p4_corpus_index import build
from verantyx import ability_corpus as ac
from verantyx import basis_policy as bp
from verantyx.ability_corpus import Corpus
from verantyx.cli import main
from verantyx.event_cross import read_events

HUMAN = "花子は太郎に資料を渡した。"
FORM = "花子が太郎に資料を渡した。"


@pytest.fixture(autouse=True)
def _no_outside_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


def _index(tmp_path: Path, rows_by_family: dict) -> Corpus:
    for family, texts in rows_by_family.items():
        src = tmp_path / (family + ".jsonl")
        rows = [{"text": t, "source": f"{family}-{i}", "scene": "場面", "sha": f"{family}{i}"}
                for i, t in enumerate(texts)]
        src.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        build(src, tmp_path / "idx" / (family + ".db"), family)
    return Corpus(tmp_path / "idx")


def _crossed(text: str) -> dict:
    ev = read_events(text)["events"]
    assert ev["status"] == "CROSSED" and len(ev["crosses"]) == 1, text
    return ev["crosses"][0]


def _roles(cross: dict) -> dict:
    return {role: [f["surface"] for f in arm["fillers"]] for role, arm in cross["arms"].items()}


# ----------------------------------------------------------------------------- form_mark
def test_form_mark_of_nothing_is_empty():
    assert ac.form_mark([]) == {}


def test_form_mark_of_a_witness_declares_generated_and_cites_it():
    w = ac.Witness("local", 1, "次郎が花子に本を渡した。", "s", "場面", "g", "sha1", "f.jsonl", 3)
    mark = ac.form_mark([w])
    assert mark["form_source"] == "generated" and mark["form_witnesses"] == [w.cite()]
    assert mark["form_witnesses"][0]["origin"] == "generated"


def test_basis_origin_does_not_read_form_witnesses():
    w = ac.Witness("local", 1, "x", "s", "g", "g", "sha")
    reply = {"sources": [{"family": "document", "text": "y"}], **ac.form_mark([w])}
    assert ac.basis_origin(reply["sources"]) is None
    assert ac.basis_mark(reply["sources"]) == {}


# ------------------------------------------------------------------------------- positive
def test_the_form_is_borrowed_and_the_content_is_the_human_source(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    res = bp.borrow_form(HUMAN, corpus=corpus)
    assert res.state == "FORM_BORROWED"
    assert res.text == FORM
    assert [w.text for w in res.witnesses] == ["次郎が花子に本を渡した。"]
    assert res.witnesses[0].origin == "generated"


def test_p3_the_borrowed_sentence_read_again_has_only_the_human_fillers_and_roles(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    res = bp.borrow_form(HUMAN, corpus=corpus)
    human, borrowed = _crossed(HUMAN), _crossed(res.text)
    assert set(borrowed["arms"]) == set(human["arms"])                  # no role added
    assert _roles(borrowed) == _roles(human)                            # every filler is the human one
    assert borrowed["center"] == human["center"]
    for word in ("次郎", "本"):                                          # nothing generated-only survives
        assert word not in res.text


def test_a_replacement_chain_does_not_cascade(tmp_path):
    # generated 次郎->花子 and 花子->太郎 would collide with sequential str.replace
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    assert bp.borrow_form(HUMAN, corpus=corpus).text == "花子が太郎に資料を渡した。"


def test_two_rows_giving_the_same_sentence_are_both_witnesses_in_a_fixed_order(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。", "三郎が次郎に鍵を渡した。"],
                               "pro": ["先生が生徒に本を渡した。"]})
    res = bp.borrow_form(HUMAN, corpus=corpus)
    assert res.state == "FORM_BORROWED" and res.text == FORM
    assert [w.family for w in res.witnesses] == ["local", "local", "pro"]
    assert [w.text for w in res.witnesses][2] == "先生が生徒に本を渡した。"
    assert res.families["local"] == "FOUND" and res.families["pro"] == "FOUND"
    assert res.families["code"].startswith("UNKNOWN_")


# -------------------------------------------------------------------------------- negatives
@pytest.mark.parametrize("rows, reason", [
    (["次郎が花子に駅で本を渡した。"], "CAND_ROLES_DIFFER"),             # a role the human source lacks
    (["次郎が本を渡した。"], "CAND_ROLES_DIFFER"),                       # a role the generated one lacks
    (["次郎が花子に本をそっと渡した。"], "CAND_NOT_ONE_CROSS"),           # adverb: not read as one cross
    (["次郎が花子に本を渡してくれた。"], "CAND_NOT_ONE_CROSS"),           # helper verb: not read
    (["次郎が花子に本を渡してしまった。"], "CAND_CONTENT_DIFFERS"),       # helper verb read, content added
    (["次郎が花子に本を渡さなかった。"], "CAND_CENTER_DIFFERS"),          # polarity
    (["次郎が花子に本を渡す。"], "CAND_CENTER_DIFFERS"),                 # tense
    (["日本が花子に本を渡した。"], "CAND_FILLER_SPAN_AMBIGUOUS"),         # 本 appears twice in the row
])
def test_a_row_that_fails_a_gate_is_never_borrowed_and_the_reason_is_counted(tmp_path, rows, reason):
    res = bp.borrow_form(HUMAN, corpus=_index(tmp_path, {"local": rows}))
    assert res.state == "FORM_NO_CANDIDATE" and res.text is None and res.witnesses == []
    assert res.reasons[reason] == 1
    assert sum(res.reasons.values()) == 1


def test_rows_for_the_same_gate_are_counted_together(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡さなかった。", "次郎が花子に本を渡す。",
                                         "次郎が花子に駅で本を渡した。"]})
    res = bp.borrow_form(HUMAN, corpus=corpus)
    assert res.state == "FORM_NO_CANDIDATE"
    assert res.reasons["CAND_CENTER_DIFFERS"] == 2 and res.reasons["CAND_ROLES_DIFFER"] == 1


def test_two_different_forms_tie_and_nothing_is_borrowed(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。", "次郎は花子に本を渡した。"]})
    res = bp.borrow_form(HUMAN, corpus=corpus)
    assert res.state == "FORM_TIE" and res.text is None and res.witnesses == []
    assert res.distinct_forms == 2


def test_a_tie_across_two_families_also_abstains(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。"], "pro": ["次郎は花子に本を渡した。"]})
    assert bp.borrow_form(HUMAN, corpus=corpus).state == "FORM_TIE"


def test_a_search_cut_off_by_the_limit_aborts_the_whole_borrowing(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。", "次郎が花子に駅で本を渡した。"]})
    res = bp.borrow_form(HUMAN, corpus=corpus, limit=1)
    assert res.state == "FORM_SEARCH_TRUNCATED" and res.text is None and res.witnesses == []
    assert res.families["local"] == "FORM_SEARCH_TRUNCATED"
    # with room, the same index does borrow (the row that would have been seen first is not trusted)
    assert bp.borrow_form(HUMAN, corpus=corpus, limit=5).state == "FORM_BORROWED"


def test_a_missing_index_is_typed_not_a_no_candidate(tmp_path):
    res = bp.borrow_form(HUMAN, corpus=Corpus(tmp_path / "nope"))
    assert res.state == "UNKNOWN_NO_INDEX" and res.text is None


def test_a_family_without_a_database_is_typed_per_family_and_the_others_are_still_searched(tmp_path):
    res = bp.borrow_form(HUMAN, corpus=_index(tmp_path, {"local": ["次郎が花子に本を渡した。"]}))
    assert res.families["pro"] == "UNKNOWN_FAMILY_DB_MISSING" and res.state == "FORM_BORROWED"


def test_a_human_source_that_is_not_one_cross_borrows_nothing(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    res = bp.borrow_form("雨の日に傘を持たずに出たら、髪が濡れた。", corpus=corpus)
    assert res.state == "FORM_SOURCE_NOT_ONE_CROSS" and res.text is None


def test_a_predicate_with_no_searchable_stem_is_not_searched(tmp_path):
    corpus = _index(tmp_path, {"local": ["次郎が花子に本をあげた。"]})
    res = bp.borrow_form("太郎は花子に本をあげた。", corpus=corpus)
    assert res.state == "FORM_NOT_SEARCHED"


# ------------------------------------------------------------------- the entrance (apply_to_ask)
def _doc_answer(text: str = HUMAN) -> dict:
    return {"kind": "answer", "verdict": "ANSWER", "text": "可否: はい", "door": "semantic_document",
            "polarity": "+", "evidence": [text], "trace": [{"part": "x", "status": "ran"}],
            "sources": [{"family": "document", "sovereign": "document", "source": "memo.txt",
                         "clause": 0, "text": text, "span": [0, len(text)]}]}


def _hand_over_memo(tmp_path, monkeypatch, *texts):
    """W5-d2 (auditor's ruling B1, K3): the test hands over a document that EXISTS. Since W5-d a ``family: document`` source is a human source only when its text is
    found (NFKC) in a document that was really handed over; ``documents=["memo.txt"]`` used to be enough, and a file that is not there is not a document. Writes
    ``memo.txt`` (one line per text) under ``tmp_path`` and makes it the working directory for the test (the relative name now names a real file)."""
    (tmp_path / "memo.txt").write_text("\n".join(texts) + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)


def test_a_document_answer_gets_a_borrowed_form_and_keeps_its_text_and_sources(tmp_path, monkeypatch):
    _hand_over_memo(tmp_path, monkeypatch, HUMAN)      # W5-d2 (K3)
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)
    original = _doc_answer()
    out, rc = bp.apply_to_ask(original, bp.AskPolicy(), query="花子は太郎に資料を渡しましたか？",
                              mode="round5", documents=["memo.txt"])
    assert rc == 0
    assert out["text"] == "可否: はい" and out["sources"] == original["sources"]
    assert out["form_text"] == FORM and out["form_source"] == "generated"
    assert out["form_witnesses"][0]["origin"] == "generated"
    assert "basis_origin" not in out
    assert ac.basis_origin(out["sources"]) is None
    assert out["basis_policy"]["outcome"] == "ANSWER_FORM_FROM_GENERATED"
    assert out["basis_policy"]["form"]["state"] == "FORM_BORROWED"
    assert out["basis_policy"]["basis"] == "HUMAN"


def test_a_failed_borrowing_leaves_the_human_answer_as_it_was(tmp_path, monkeypatch):
    _hand_over_memo(tmp_path, monkeypatch, HUMAN)      # W5-d2 (K3)
    _index(tmp_path, {"local": ["次郎が花子に本を渡さなかった。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    original = _doc_answer()
    out, rc = bp.apply_to_ask(original, bp.AskPolicy(), query="q", mode="round5", documents=["memo.txt"])
    assert rc == 0 and "form_text" not in out and "form_source" not in out
    assert {k: v for k, v in out.items() if k != "basis_policy"} == original
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    assert out["basis_policy"]["form"]["state"] == "FORM_NO_CANDIDATE"
    assert out["basis_policy"]["form"]["reasons"]["CAND_CENTER_DIFFERS"] == 1


@pytest.mark.parametrize("mode, docs", [("legacy", []), ("round5", [])])
def test_other_routes_do_not_attempt_the_borrowing(tmp_path, monkeypatch, mode, docs):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A3）: 人の出典の入力を memory_sovereign（ソブリンの記録由来）にした（自己申告の human_confirmed は人にしない）。期待は同じ
    ans = _doc_answer(); ans["sources"] = [{**s, "family": "memory_sovereign", "origin": "human_confirmed"} for s in ans["sources"]]
    out, _rc = bp.apply_to_ask(ans, bp.AskPolicy(), query="q", mode=mode, documents=docs)
    assert "form_text" not in out and out["basis_policy"]["form"]["state"] == "NOT_ATTEMPTED_ROUTE"
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"


def test_from_the_command_line_a_document_answer_carries_the_borrowed_form(tmp_path, monkeypatch, capsys):
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    memo = tmp_path / "memo.txt"
    memo.write_text(HUMAN, encoding="utf-8")
    rc = main(["--store", str(tmp_path / "s.json"), "ask", "花子は太郎に資料を渡しましたか？",
               "--mode", "round5", "--document", str(memo)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["text"] == "可否: はい" and out["door"] == "semantic_document"
    assert out["form_text"] == FORM and out["basis_policy"]["outcome"] == "ANSWER_FORM_FROM_GENERATED"
    assert "basis_origin" not in out
    assert all(s.get("origin") is None for s in out["sources"])
    assert not (tmp_path / "s.json").exists()


def test_the_borrowing_takes_no_role_from_the_generated_sentence_end_to_end(tmp_path, monkeypatch):
    # the human document has two roles; the only generated row has three: nothing is added
    _index(tmp_path, {"local": ["次郎が花子に本を渡した。"]})
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    human = "花子は資料を渡した。"
    _hand_over_memo(tmp_path, monkeypatch, human)      # W5-d2 (K3)
    out, _rc = bp.apply_to_ask(_doc_answer(human), bp.AskPolicy(), query="q", mode="round5",
                               documents=["memo.txt"])
    assert "form_text" not in out and out["basis_policy"]["form"]["reasons"]["CAND_ROLES_DIFFER"] == 1

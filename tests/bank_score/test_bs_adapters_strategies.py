"""アダプター（到達表・引数づくり・結果型の対応表）と自明な戦略（S4）。"""
import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from tools.bank_score import adapters, classify, schema
from tools.bank_score.score import score_observation
from tools.bank_score.strategies import STRATEGIES, not_applicable, observe_strategy

TREE = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"


def load(bank):
    fr = FIX / "B5" / "frames" if bank == "B5" else None
    return schema.read_items(str(FIX / bank / "items.jsonl"), bank, fr)


# ---- 結果型 → 状態の対応表（one.py の写しと一致） -----------------------------------
def test_refusal_tables_match_verantyx_one_py_by_ast_without_importing():
    tree = ast.parse((TREE / "verantyx" / "one.py").read_text(encoding="utf-8"))
    found = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in (
                "_REFUSAL_KINDS", "_REFUSAL_PREFIXES"):
            found[n.targets[0].id] = ast.literal_eval(n.value)
    assert set(found) == {"_REFUSAL_KINDS", "_REFUSAL_PREFIXES"}
    assert set(found["_REFUSAL_KINDS"]) == adapters.REFUSAL_KINDS
    assert tuple(found["_REFUSAL_PREFIXES"]) == adapters.REFUSAL_PREFIXES


def state_of(**raw):
    return adapters._state(raw)


def test_state_mapping_by_type_only():
    assert state_of(verdict="ANSWER") == "answer"
    assert state_of(verdict="CREATED", created=True) == "answer"
    assert state_of(kind="answer") == "answer" and state_of(kind="skill") == "answer"
    assert state_of(kind="social") == "social"
    assert state_of(kind="unknown", verdict="UNKNOWN_UNREAD") == "abstain"
    assert state_of(verdict="NOT_IN_DOCS") == "abstain"
    assert state_of(verdict="TIED_X") == "abstain"
    assert state_of(kind="not_yet") == "abstain" and state_of(kind="cannot") == "abstain"
    assert state_of(status="PARTIAL_COMPLETENESS_UNVERIFIED", kind="unknown") == "answer"
    assert state_of(verdict="PARTIAL") == "answer"
    assert state_of(kind="mystery", verdict="WEIRD") == "unmapped"


def test_state_ignores_text_even_if_it_sounds_like_refusal():
    # 本文の文言では棄権にしない（型だけ）
    assert state_of(text="分かりません。推測はしません", kind="answer") == "answer"
    assert state_of(text="確かな答えです", kind="unknown") == "abstain"


def test_adapter_source_has_no_phrase_based_abstain_detection():
    import re
    for p in (TREE / "tools" / "bank_score").glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert not re.search(r"分かりません|知りません|保留|no guessing|I do not know", src), p.name


def test_not_in_docs_is_a_label_answer_only_for_sentence_check_items():
    label = {"expect": {"behavior": "answer", "reference": "NOT_IN_DOCS"}}
    other = {"expect": {"behavior": "answer", "reference": "月曜です"}}
    ab = {"expect": {"behavior": "abstain", "reference": "NOT_IN_DOCS"}}
    raw = {"kind": "unknown", "verdict": "NOT_IN_DOCS", "text": ""}
    assert adapters.observe("B2", raw, "e", [], 0, label)["state"] == "answer"
    assert adapters.observe("B2", raw, "e", [], 0, other)["state"] == "abstain"
    assert adapters.observe("B2", raw, "e", [], 0, ab)["state"] == "abstain"
    # NOT_IN_DOCS 以外の UNKNOWN_* は文のチェックでも棄権のまま
    raw2 = {"kind": "unknown", "verdict": "UNKNOWN_UNREAD", "text": ""}
    assert adapters.observe("B2", raw2, "e", [], 0, label)["state"] == "abstain"


def test_declared_constructed_and_evidence_from_types():
    o = adapters.observe("B3", {"kind": "created", "verdict": "CREATED", "created": True, "text": "x",
                                "evidence": [{"a": 1}]}, "e", [], 0)
    assert o["declared_constructed"] is True and o["has_evidence"] is True
    o2 = adapters.observe("B3", {"kind": "answer", "verdict": "ANSWER", "text": "x", "evidence": [], "sources": []},
                          "e", [], 0)
    assert o2["declared_constructed"] is False and o2["has_evidence"] is False


# ---- 到達表 ---------------------------------------------------------------------
def test_entry_table_and_unknown_entry_is_rejected():
    assert adapters.check_entry("B2", None) == "cli-ask-round5"
    assert adapters.check_entry("B2", "cli-ask") == "cli-ask"
    assert adapters.check_entry("B1", None) == "cli" and adapters.check_entry("B5", None) == "cli"
    with pytest.raises(ValueError):
        adapters.check_entry("B2", "cli-ask-round6")
    with pytest.raises(ValueError):
        adapters.check_entry("B3", "cli-ask")


def test_b1_and_b5_are_unreachable_for_every_item():
    for bank in ("B1", "B5"):
        for r in load(bank):
            reach = adapters.reachability(bank, adapters.DEFAULT_ENTRY[bank], r["case"])
            assert reach["reachable"] is False
            assert reach["capability"] == {"B1": "sentence_structure", "B5": "frame_question_answer"}[bank]


def test_b2_history_is_unreachable_and_cli_ask_without_documents_support():
    recs = {r["id"]: r for r in load("B2")}
    multi = recs["b2s-020"]["case"]
    assert adapters.reachability("B2", "cli-ask-round5", multi)["capability"] == "conversation_history"
    doc_item = recs["b2s-003"]["case"]
    assert adapters.reachability("B2", "cli-ask-round5", doc_item)["reachable"] is True
    r = adapters.reachability("B2", "cli-ask", doc_item)
    assert r["reachable"] is False and r["capability"] == "documents"
    both = adapters.reachability("B2", "cli-ask", multi)
    assert both["capability"] == "conversation_history"  # 文書の無い多ターンは履歴だけ
    no_doc = recs["b2s-001"]["case"]
    assert adapters.reachability("B2", "cli-ask", no_doc)["reachable"] is True


def test_b3_is_reachable_with_and_without_materials():
    for r in load("B3"):
        assert adapters.reachability("B3", "cli-ask-round5", r["case"])["reachable"]


def test_build_call_uses_double_dash_before_query_and_passes_documents():
    recs = {r["id"]: r for r in load("B2")}
    c = adapters.build_call("B2", "cli-ask-round5", recs["b2s-003"]["case"])
    assert c["argv"][:3] == ["ask", "--mode", "round5"]
    assert "--document" in c["argv"] and c["argv"][-2] == "--"
    assert c["argv"][-1] == recs["b2s-003"]["case"]["last_user"]
    assert [f["filename"] for f in c["files"]] == ["星見台図書室案内.txt"]
    legacy = adapters.build_call("B2", "cli-ask", recs["b2s-001"]["case"])
    assert legacy["argv"] == ["ask", "--", recs["b2s-001"]["case"]["last_user"]]


def test_unreachable_item_never_starts_a_subprocess(tmp_path, monkeypatch):
    from tools.bank_score import cli, runner

    def boom(*a, **k):  # run_ask は呼ばれてはならない
        raise AssertionError("Vera を呼んではならない")

    monkeypatch.setattr(runner.Session, "run_ask", boom)
    out = tmp_path / "o"
    code = cli.main(["--bank", "B1", "--items", str(FIX / "B1" / "items.jsonl"), "--tree", str(TREE),
                     "--out", str(out), "--python", __import__("sys").executable])
    assert code == 0
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["class"] for r in rows} == {"unreachable"}
    assert {r["capability"] for r in rows} == {"sentence_structure"}
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["vera_calls"] == 0 and meta["precheck"]["outside"] == []


# ---- 自明な戦略（S4） ------------------------------------------------------------
@pytest.mark.parametrize("bank", schema.BANKS)
def test_trivial_strategies_do_not_get_full_marks_and_stay_under_threshold(bank):
    recs = [r for r in load(bank) if not r["errors"]]
    total = len(recs)
    for s in STRATEGIES:
        if not_applicable(bank, s):
            continue
        counts = Counter()
        for r in recs:
            sc = score_observation(bank, r["raw"], r["case"], observe_strategy(bank, s, r["case"]))
            counts[sc["class"]] += 1
        assert counts["correct"] + counts["correct_abstain"] < total, (bank, s)
        pass_rate = (counts["correct"] + counts["correct_abstain"]) / total
        assert pass_rate <= 0.35, (bank, s, pass_rate)  # 見本が弱いなら見本を直す（テストは弱めない）


def test_not_applicable_strategies_carry_a_reason():
    for bank in schema.BANKS:
        for s in STRATEGIES:
            why = not_applicable(bank, s)
            assert why is None or (isinstance(why, str) and why)
    assert not_applicable("B1", "echo_documents") and not_applicable("B2", "first_option")
    assert not_applicable("B5", "first_option") is None and not_applicable("B5", "all_labels") is None


@pytest.mark.parametrize("bank", schema.BANKS)
def test_nine_classes_are_exclusive_and_exhaustive_over_fixtures_and_strategies(bank):
    """見本・不正見本 × 各戦略。cli と同じ経路（_row/_scored）で全行を分類し、合計 == 非空行数を確かめる。"""
    from tools.bank_score import cli, report
    fr = FIX / "B5" / "frames" if bank == "B5" else None
    checked = 0
    for path in (FIX / bank / "items.jsonl", FIX / "invalid" / f"{bank}.jsonl"):
        nonblank = sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())
        recs = schema.read_items(str(path), bank, fr)
        assert len(recs) == nonblank  # 黙って飛ばさない: 読み込みの時点で全行が 1 件ずつ
        for s in STRATEGIES:
            if not_applicable(bank, s):
                continue
            rows = []
            for r in recs:
                row = cli._row(r, bank, f"strategy:{s}")
                if r["errors"]:
                    k, why = classify.classify(invalid=True)
                    row.update({"class": k, "class_ja": classify.CLASS_JA[k], "reason": why,
                                "reason_detail": r["errors"]})
                else:
                    cli._scored(row, score_observation(bank, r["raw"], r["case"], observe_strategy(bank, s, r["case"])))
                    row["observation"] = {}
                rows.append(row)
            classes = [row["class"] for row in rows]
            assert all(c in classify.CLASS_KEYS for c in classes)  # どの行もちょうど 9 キーのどれか 1 つ
            counts = Counter(classes)
            assert sum(counts.values()) == nonblank, (bank, s, path.name, counts)
            summ = report.build_summary(bank, rows, {}, {"count": 0, "ids": [], "not_in_items": []})
            assert summ["class_sum"] == summ["total"] == nonblank
            assert {k: v["count"] for k, v in summ["classes"].items() if v["count"]} == dict(counts)
            checked += 1
    assert checked >= 2

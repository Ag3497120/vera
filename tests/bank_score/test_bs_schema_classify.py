"""検証・隔離（不正を黙って飛ばさない）と 9 分類（排他・網羅）。"""
import itertools
import json
from pathlib import Path

import pytest

from tools.bank_score import classify, schema

FIX = Path(__file__).parent / "fixtures"
FRAMES = FIX / "B5" / "frames"


def frames_for(bank):
    return FRAMES if bank == "B5" else None


@pytest.mark.parametrize("bank", schema.BANKS)
def test_valid_fixtures_have_no_item_invalid(bank):
    recs = schema.read_items(str(FIX / bank / "items.jsonl"), bank, frames_for(bank))
    assert len(recs) >= 20
    assert [r for r in recs if r["errors"]] == []


@pytest.mark.parametrize("bank", schema.BANKS)
def test_invalid_fixtures_every_nonblank_line_becomes_a_record(bank):
    path = FIX / "invalid" / f"{bank}.jsonl"
    nonblank = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    recs = schema.read_items(str(path), bank, frames_for(bank))
    assert len(recs) == len(nonblank)
    assert all(r["errors"] for r in recs), [r["id"] for r in recs if not r["errors"]]


def test_b1_invalid_reasons_are_typed():
    recs = {r["line"]: r for r in schema.read_items(str(FIX / "invalid" / "B1.jsonl"), "B1", None)}
    assert recs[1]["errors"] == ["BAD_JSON"] and recs[1]["id"] == "line:1"
    assert recs[6]["errors"] == ["BAD_JSON:NOT_OBJECT"]
    assert "MISSING_FIELD:rationale" in recs[2]["errors"]
    assert recs[3]["errors"] == ["DUPLICATE_ID"] and recs[4]["errors"] == ["DUPLICATE_ID"]  # 重複は全部不正（先勝ちにしない）
    assert recs[7]["errors"] == ["MISSING_MUST_NOT"]
    assert recs[8]["errors"] == ["B1_INPUT_COUNT:2"]
    assert recs[9]["errors"] == ["BAD_VALUE:difficulty"]  # bool は不可
    assert recs[10]["errors"] == ["CLAUSES_NOT_EMPTY_FOR_UNREADABLE"]
    assert recs[11]["errors"] == ["BAD_MUST_NOT[0]"]
    assert recs[12]["errors"] == ["BAD_VALUE:lang"]


def test_b2_invalid_reasons_flat_must_contain_any_is_not_one_group():
    recs = schema.read_items(str(FIX / "invalid" / "B2.jsonl"), "B2", None)
    assert recs[0]["errors"] == ["FLAT_MUST_CONTAIN_ANY:expect.must_contain_any"]
    assert recs[1]["errors"] == ["BAD_LAST_TURN"]
    assert recs[3]["errors"][0].startswith("DUPLICATE_DOCUMENT_NAME")


def test_b5_invalid_frame_missing_and_conflicts():
    recs = schema.read_items(str(FIX / "invalid" / "B5.jsonl"), "B5", FRAMES)
    assert recs[0]["errors"] == ["FRAME_MISSING"]
    assert recs[3]["errors"] == ["CONFLICT:question"]
    assert schema.read_items(str(FIX / "invalid" / "B5.jsonl"), "B5", None)[1]["errors"][-1] == "FRAME_MISSING"


def test_materials_three_shapes_and_bad_shape():
    errs = []
    assert [d["filename"] for d in schema.normalize_materials(["a", "b"], errs)] == ["material_1.txt", "material_2.txt"]
    assert schema.normalize_materials("本文", errs)[0]["name"] == "material_1"
    assert schema.normalize_materials([{"name": "規程", "text": "x"}], errs)[0]["filename"] == "規程.txt"
    assert errs == []
    schema.normalize_materials(5, errs)
    assert errs == ["BAD_TYPE:materials"]


def test_safe_filename_rules():
    assert schema.safe_filename("a/b\\c") == "a_b_c.txt"
    assert schema.safe_filename(".hidden.md") == "_hidden.md"
    assert schema.safe_filename("note") == "note.txt"


def test_quarantine_must_be_array_of_strings(tmp_path):
    good = tmp_path / "q.json"
    good.write_text('["a","b"]')
    assert schema.load_quarantine(str(good)) == ["a", "b"]
    for bad in ('{"a":1}', '[1,2]', "not json"):
        p = tmp_path / "bad.json"
        p.write_text(bad)
        with pytest.raises(schema.InputError):
            schema.load_quarantine(str(p))
    assert schema.load_quarantine(None) == []


# ---- 9 分類 ---------------------------------------------------------------------
def test_classify_priority_order():
    k = classify.classify
    assert k(invalid=True, unreachable=True, runtime_reason="TIMEOUT", misread=True)[0] == "unscorable"
    assert k(unreachable=True, runtime_reason="TIMEOUT", misread=True)[0] == "unreachable"
    assert k(runtime_reason="NOT_JSON", misread=True)[0] == "runtime_error"
    # B1: must_not 該当は棄権側の期待でも誤読（誤った応諾より先）
    assert k(misread=True, side="abstain", state="answer")[0] == "misread"
    assert k(side="abstain", state="abstain")[0] == "correct_abstain"
    assert k(side="abstain", state="answer")[0] == "false_compliance"
    assert k(side="abstain", state="social")[0] == "false_compliance"
    assert k(side="answer", state="abstain")[0] == "over_abstain"
    assert k(side="answer", state="answer", overall="FAIL")[0] == "wrong"
    assert k(side="answer", state="answer", overall="PASS")[0] == "correct"
    assert k(side="answer", state="social", overall="PASS")[0] == "correct"
    assert k(side="answer", state="answer", overall="UNJUDGED") == ("unscorable", "JUDGE_UNAVAILABLE")
    assert k(invalid=True) == ("unscorable", "ITEM_INVALID")  # 2 種の unscorable は理由で分かれる


def test_classify_exhaustive_every_combination_lands_in_exactly_one_class():
    states = classify.STATES
    sides = ("answer", "abstain")
    overalls = ("PASS", "FAIL", "UNJUDGED")
    combos = itertools.product((False, True), (False, True), (None, "TIMEOUT", "NONZERO_EXIT", "NOT_JSON",
                                                              "UNMAPPED_RESULT_TYPE"),
                               (False, True), sides, states, overalls)
    n = 0
    for invalid, unreachable, rt, misread, side, state, ov in combos:
        key, reason = classify.classify(invalid=invalid, unreachable=unreachable, runtime_reason=rt, misread=misread,
                                        side=side, state=state, overall=ov)
        assert key in classify.CLASS_KEYS
        assert (key == "unscorable") == (reason in ("ITEM_INVALID", "JUDGE_UNAVAILABLE"))
        n += 1
    assert n == 2 * 2 * 5 * 2 * 2 * 4 * 3


def test_classify_answer_never_correct_when_expected_side_is_abstain():
    for state in classify.STATES:
        for ov in ("PASS", "FAIL", "UNJUDGED"):
            assert classify.classify(side="abstain", state=state, overall=ov)[0] != "correct"


def test_classify_unmapped_state_is_runtime_error_not_scored():
    assert classify.classify(side="answer", state="unmapped") == ("runtime_error", "UNMAPPED_RESULT_TYPE")


def test_class_names_cover_all_nine_with_japanese():
    assert len(classify.CLASS_KEYS) == 9 and set(classify.CLASS_JA) == set(classify.CLASS_KEYS)
    assert len(set(classify.CLASS_JA.values())) == 9

"""未知のキーは黙って無視しない: 問題ごとにパスで記録し、採点に影響するものは UNJUDGED（採点不能）にする（トップ・expect・入れ子）。"""
import copy

import pytest

import v2_util as U
from tools.bank_score.v2 import keys
from v2_util import b1_item, b2_item, b3_item, b5_item, clause, obs

OK = {
    "B1": (lambda: b1_item("fx", "入力", [clause("行く", {"agent": "甲"})], must_not=[{"clause": 0, "role": "agent", "value": "乙"}]),
           lambda: U.b1_obs([clause("行く", {"agent": "甲"})])),
    "B2": (lambda: b2_item("fx", must_contain_any=[["あ"]]), lambda: obs("answer", text="あ")),
    "B3": (lambda: b3_item("fx", must_express=[{"predicate": ["行く"], "agent": ["甲"], "polarity": "+"}],
                           form={"type": "numbered_list", "items": 1}),
           lambda: obs("answer", text="1. 甲が行く")),
    "B5": (lambda: b5_item("fx", options=["a案", "b案"], index=0, vocab={"out_of_vocabulary": True, "distractors": []}),
           lambda: obs("answer", decision="answer", answer_option_index=0, answer=None, vocab_mapping=None)),
}


def with_path(raw, path):
    r = copy.deepcopy(raw)
    cur = r
    parts = path.split(".")
    for p in parts[:-1]:
        cur = cur[int(p)] if p.isdigit() else cur[p]
    cur[parts[-1]] = "zz"
    return r


CASES = [
    ("B1", "top.zz_top", "zz_top"),
    ("B1", "expect.zz_exp", "expect.zz_exp"),
    ("B1", "expect.clauses[].zz_cl", "expect.clauses.0.zz_cl"),
    ("B1", "expect.must_not[].zz_mn", "expect.must_not.0.zz_mn"),
    ("B2", "top.zz_top", "zz_top"),
    ("B2", "expect.zz_exp", "expect.zz_exp"),
    ("B2", "turns[].zz", "turns.0.zz"),
    ("B2", "expect.format.zz", None),
    ("B3", "top.zz_top", "zz_top"),
    ("B3", "expect.zz_exp", "expect.zz_exp"),
    ("B3", "expect.constraints.zz_c", "expect.constraints.zz_c"),
    ("B3", "expect.constraints.must_express[].zz", "expect.constraints.must_express.0.zz"),
    ("B3", "expect.constraints.form[numbered_list].zz", "expect.constraints.form.zz"),
    ("B5", "top.zz_top", "zz_top"),
    ("B5", "expect.zz_exp", "expect.zz_exp"),
    ("B5", "expect.vocab.zz", "expect.vocab.zz"),
]


@pytest.mark.parametrize("bank, want, path", CASES)
def test_unknown_key_at_every_layer_is_recorded_and_makes_the_item_unjudged(bank, want, path, tmp_path):
    mk, mo = OK[bank]
    raw = mk()
    if path is None:  # B2 の format は無いので足してから
        raw["expect"]["format"] = {"lines": [1, 2]}
        raw = with_path(raw, "expect.format.zz")
        o = obs("answer", text="あ")
        o["text"] = "あ"
    else:
        raw = with_path(raw, path)
        o = mo()
    frames = U.frames_dir(tmp_path) if bank == "B5" else None
    base = U.score(bank, mk(), mo(), frames)
    assert base["unknown_expect_keys"] == []
    if bank != "B3":  # B3 の見本は読解器が要る規則を持つので、主分類は採点不能のまま
        assert base["class"] == "correct", base["checks"]
    s = U.score(bank, raw, o, frames)
    assert len(s["unknown_expect_keys"]) == 1 and s["unknown_expect_keys"][0].endswith(".zz" if "zz_" not in want else want.split(".")[-1]) \
        or want in s["unknown_expect_keys"], s["unknown_expect_keys"]
    assert s["checks"]["unknown_expect_keys"]["result"] == "UNJUDGED"
    assert (s["class"], s["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")


def test_known_record_only_keys_are_not_unknown():
    for bank, raw in (("B1", OK["B1"][0]()), ("B2", OK["B2"][0]()), ("B3", OK["B3"][0]()), ("B5", OK["B5"][0]())):
        assert keys.find_unknown(bank, raw) == []


def test_cells_children_are_not_scanned_for_unknown_keys():
    raw = b3_item("fx", form={"type": "table", "columns": ["あ", "い"], "rows": 1,
                              "cells": {"どんな行名でも": {"どんな列名でも": ["x"]}}, "cells_note": "n"})
    assert keys.find_unknown("B3", raw) == []


def _unscorable(sc):
    assert (sc["class"], sc["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE"), sc
    assert sc["class_approx"] == "unscorable"
    assert sc["checks"]["unknown_expect_keys"]["result"] == "UNJUDGED"
    assert sc["checks"]["unknown_expect_keys"]["detail"]["reason"] == "UNKNOWN_EXPECT_KEYS"


def test_unknown_key_beats_a_definite_fail_the_item_is_unscorable_not_wrong():
    raw = b2_item("fx", must_contain_any=[["あ"]])
    base = U.score("B2", raw, obs("answer", text="い"))
    assert base["class"] == "wrong"  # 未知キーが無ければ確定した FAIL は誤答
    raw["zz_top"] = 1
    s = U.score("B2", raw, obs("answer", text="い"))
    _unscorable(s)
    assert s["checks"]["must_contain_any"]["result"] == "FAIL"  # 他の規則の結果は行に残す


def test_unknown_key_with_an_abstain_observation_on_an_answer_side_item_is_unscorable_not_over_abstain():
    raw = b2_item("fx", must_contain_any=[["あ"]])
    assert U.score("B2", raw, obs("abstain"))["class"] == "over_abstain"
    raw["zz_top"] = 1
    _unscorable(U.score("B2", raw, obs("abstain")))


def test_unknown_key_on_an_abstain_side_item_is_unscorable_whether_or_not_it_has_abstain_text_rules():
    ab = b2_item("fx", behavior="abstain")
    del ab["expect"]["must_not_contain"]  # 棄権文に当てる規則が無い問題
    assert U.score("B2", ab, obs("abstain"))["class"] == "correct_abstain"
    ab["zz_top"] = 1
    s = U.score("B2", ab, obs("abstain"))
    _unscorable(s)
    assert s["unknown_expect_keys"] == ["top.zz_top"]  # パスの記録も残る
    ab2 = b2_item("fx", behavior="abstain", must_not_contain=["禁止"])
    ab2["zz_top"] = 1
    _unscorable(U.score("B2", ab2, obs("abstain", text="禁止")))  # 棄権文の規則が FAIL でも採点不能
    _unscorable(U.score("B2", ab2, obs("answer", text="なにか")))  # 期待が棄権側で回答した（false_compliance になる所）も採点不能


def test_unknown_key_on_b1_makes_misread_and_abstain_unscorable():
    mk, mo = OK["B1"]
    raw = mk()
    wrong = U.b1_obs([clause("行く", {"agent": "乙"})])
    assert U.score("B1", mk(), wrong)["class"] != "correct"
    raw["zz_top"] = 1
    _unscorable(U.score("B1", raw, wrong))
    _unscorable(U.score("B1", raw, obs("abstain")))
    unreadable = b1_item("fx", "入力", [], readable=False)
    assert U.score("B1", unreadable, U.b1_obs([clause("行く", {})]))["class"] == "misread"
    unreadable["zz_top"] = 1
    _unscorable(U.score("B1", unreadable, U.b1_obs([clause("行く", {})])))


@pytest.mark.parametrize("bank", ["B3", "B5"])
def test_unknown_key_with_an_abstain_observation_is_unscorable_on_b3_and_b5(bank, tmp_path):
    mk, _ = OK[bank]
    raw = mk()
    raw["zz_top"] = 1
    frames = U.frames_dir(tmp_path) if bank == "B5" else None
    _unscorable(U.score(bank, raw, obs("abstain"), frames))


def test_judge_unavailable_reasons_in_the_summary_count_unknown_expect_keys():
    from tools.bank_score import report
    raw = b2_item("fx", must_contain_any=[["あ"]])
    raw["zz_top"] = 1
    sc = U.score("B2", raw, obs("answer", text="い"))
    row = {"id": "x", "line": 1, "bank": "B2", "lang": "ja", "category": "c", "difficulty": 1, "class": sc["class"],
           "class_ja": sc["class_ja"], "reason": sc["reason"], "reason_detail": [], "entry": "e", "capability": None,
           "checks": sc["checks"], "notes": [], "unknown_expect_keys": sc["unknown_expect_keys"]}
    s = report.build_summary("B2", [row], {}, {"count": 0, "ids": [], "not_in_items": []}, "v2")
    assert s["judge_unavailable_reasons"] == {"UNKNOWN_EXPECT_KEYS": 1}
    assert s["classes"]["wrong"]["count"] == 0 and s["classes"]["unscorable"]["count"] == 1
    assert s["unknown_expect_keys"] == {"top.zz_top": 1}

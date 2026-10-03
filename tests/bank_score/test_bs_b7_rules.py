"""B7（根拠の方針）の検証・観測・分類・字句の照合・確認の問いの形。偽の答え手を使わず b7.score を直接呼ぶ。"""
from __future__ import annotations

import copy
import json

import pytest

from tools.bank_score.checks import FAIL, PASS, UNJUDGED
from tools.bank_score.v2 import b7, keys

AHB, AFG, CON, CR, RG, ABS = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "CONSTRUCTED",
                              "CONFIRM_REQUEST", "REFERENCE_GENERATED", "ABSTAIN")


def item(E=AHB, must_not=(), acf="human", hs=("人の文。",), gs=(), kind="factual", lang="ja", hp=False, sr=False,
         evidence="C", **top):
    it = {"id": "t1", "lang": lang, "unit": "g01", "category": "zqc", "phenomenon": "zqp", "difficulty": 1,
          "rationale": "zqr", "request": "依頼です", "request_kind": kind, "human_sources": list(hs),
          "generated_snippets": list(gs), "human_present": hp, "show_reference": sr,
          "expect": {"result": E, "must_not": list(must_not), "answer_content_from": acf, "evidence": evidence}}
    it.update(top)
    return it


def out(outcome, **kw):
    o = {"kind": "answer" if outcome in (AHB, AFG, CON) else "unknown",
         "verdict": "ANSWER" if outcome in (AHB, AFG, CON) else "UNKNOWN_X", "text": "", "sources": [],
         "basis_policy": {"applied": True, "outcome": outcome}}
    o.update(kw)
    return o


def run(raw, output, exit_code=0):
    errs, case = b7.validate_item(raw)
    assert errs == [], errs
    obs = b7.observe(output, "cli-ask-round5-basis", ["ask"], exit_code)
    return b7.score(raw, case, obs)


def cls(sc):
    return (sc["class"], sc["reason"], sc["class_approx"])


# ---- 6 値の写し ------------------------------------------------------------------------------------
def test_outcomes_copy_equals_product_vocabulary():
    from verantyx import basis_policy
    assert b7.OUTCOMES == tuple(basis_policy.OUTCOMES)
    assert b7.REQUEST_KINDS == tuple(basis_policy.REQUEST_KINDS)
    assert b7.ANSWER_OUTCOMES == ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED")


# ---- 検証（J13・§3.2 の表）----------------------------------------------------------------------------
def errs_of(**over):
    it = item()
    for k, v in over.items():
        if v == "__del__":
            del it[k]
        else:
            it[k] = v
    return b7.validate_item(it)[0]


def test_valid_item_gives_case_with_only_child_visible_fields():
    errs, case = b7.validate_item(item())
    assert errs == []
    assert set(case) == {"request", "request_kind", "human_sources", "generated_snippets", "human_present",
                         "show_reference"}


@pytest.mark.parametrize("field", ["id", "lang", "unit", "category", "phenomenon", "difficulty", "rationale",
                                   "request", "request_kind", "human_sources", "generated_snippets", "human_present",
                                   "show_reference", "expect"])
def test_missing_field(field):
    assert f"MISSING_FIELD:{field}" in errs_of(**{field: "__del__"})


@pytest.mark.parametrize("over,code", [
    ({"id": ""}, "BAD_TYPE:id"), ({"id": 3}, "BAD_TYPE:id"),
    ({"lang": "fr"}, "BAD_VALUE:lang"),
    ({"unit": 1}, "BAD_TYPE:unit"), ({"category": None}, "BAD_TYPE:category"),
    ({"phenomenon": 1}, "BAD_TYPE:phenomenon"), ({"rationale": []}, "BAD_TYPE:rationale"),
    ({"difficulty": 0}, "BAD_VALUE:difficulty"), ({"difficulty": 4}, "BAD_VALUE:difficulty"),
    ({"difficulty": True}, "BAD_VALUE:difficulty"), ({"difficulty": "1"}, "BAD_VALUE:difficulty"),
    ({"request": "  "}, "BAD_VALUE:request"), ({"request": 5}, "BAD_VALUE:request"),
    ({"request_kind": "poem"}, "BAD_VALUE:request_kind"),
    ({"human_sources": "x"}, "BAD_TYPE:human_sources"), ({"human_sources": [1]}, "BAD_TYPE:human_sources"),
    ({"human_sources": ["a\nb"]}, "BAD_VALUE:human_sources"), ({"human_sources": ["a\rb"]}, "BAD_VALUE:human_sources"),
    ({"human_sources": [" "]}, "BAD_VALUE:human_sources"),
    ({"human_sources": ["a"] * 5}, "BAD_VALUE:human_sources_count"),
    ({"generated_snippets": "x"}, "BAD_TYPE:generated_snippets"),
    ({"generated_snippets": [" "]}, "BAD_VALUE:generated_snippets"),
    ({"generated_snippets": ["a"] * 3}, "BAD_VALUE:generated_snippets_count"),
    ({"human_present": 1}, "BAD_TYPE:human_present"), ({"show_reference": "no"}, "BAD_TYPE:show_reference"),
    ({"expect": []}, "BAD_TYPE:expect"),
])
def test_bad_values(over, code):
    assert code in errs_of(**over)


def test_expect_subfields_and_contradictions():
    def e(**kw):
        it = item()
        for k, v in kw.items():
            if v == "__del__":
                del it["expect"][k]
            else:
                it["expect"][k] = v
        return b7.validate_item(it)[0]
    assert "MISSING_FIELD:expect.result" in e(result="__del__")
    assert "BAD_VALUE:expect.result" in e(result="SOMETHING")
    assert "MISSING_FIELD:expect.must_not" in e(must_not="__del__")
    assert "BAD_VALUE:expect.must_not" in e(must_not=["NOPE"])
    assert "BAD_VALUE:expect.must_not" in e(must_not="ABSTAIN")
    assert "MISSING_FIELD:expect.answer_content_from" in e(answer_content_from="__del__")
    assert "BAD_VALUE:expect.answer_content_from" in e(answer_content_from="both")
    assert "EXPECT_IN_MUST_NOT" in e(must_not=[AHB])
    assert "EXPECT_ANSWER_WITH_CONTENT_NONE" in e(answer_content_from="none")
    assert e(result=AFG, answer_content_from="none") == ["EXPECT_ANSWER_WITH_CONTENT_NONE"]
    assert e(result=ABS, answer_content_from="none") == []
    assert e(evidence="__del__") == []  # evidence は欠けても ITEM_INVALID にしない


def test_read_items_keeps_every_line_and_flags_duplicates(tmp_path):
    p = tmp_path / "i.jsonl"
    good = item()
    lines = [json.dumps(good, ensure_ascii=False), "", "{bad", "[1]", json.dumps(item(id="t2", request_kind="poem")),
             json.dumps(dict(good, id="dup")), json.dumps(dict(good, id="dup"))]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    recs = b7.read_items(str(p))
    assert [r["line"] for r in recs] == [1, 3, 4, 5, 6, 7]
    assert recs[0]["errors"] == [] and recs[0]["case"] is not None
    assert recs[1]["errors"] == ["BAD_JSON"] and recs[2]["errors"] == ["BAD_JSON:NOT_OBJECT"]
    assert recs[3]["errors"] == ["BAD_VALUE:request_kind"] and recs[3]["case"] is None
    assert recs[4]["errors"][0] == "DUPLICATE_ID" and recs[5]["errors"][0] == "DUPLICATE_ID"
    with pytest.raises(b7.InputError):
        b7.read_items(str(tmp_path / "none.jsonl"))


# ---- 観測（J7・J6 の文の取り出し）-----------------------------------------------------------------------------
def obs_of(output):
    return b7.observe(output, "e", [], 0)


def test_outcome_missing_kinds_and_states():
    assert obs_of({"kind": "answer"})["outcome_missing_kind"] == "BASIS_POLICY_ABSENT"
    assert obs_of({"basis_policy": "x"})["outcome_missing_kind"] == "BASIS_POLICY_ABSENT"
    o = obs_of({"basis_policy": {"applied": False, "reason": "NO_CITED_SOURCES", "outcome": None}})
    assert (o["outcome"], o["outcome_missing_kind"], o["policy_reason"], o["state"]) == (
        "OUTCOME_MISSING", "OUTCOME_NULL", "NO_CITED_SOURCES", "outcome_missing")
    assert obs_of({"basis_policy": {"outcome": None, "reason": "no cited"}})["policy_reason"] is None
    assert obs_of({"basis_policy": {"outcome": "MAYBE"}})["outcome_missing_kind"] == "OUTCOME_NOT_IN_VOCAB"
    assert obs_of({"basis_policy": {"outcome": 3}})["outcome_missing_kind"] == "OUTCOME_NOT_IN_VOCAB"
    for o, st in ((AHB, "answer"), (AFG, "answer"), (CON, "answer"), (ABS, "abstain"), (RG, "abstain"),
                  (CR, "abstain")):
        assert obs_of(out(o))["state"] == st
    # 本文の文言で状態を決めない・"unmapped" を出さない
    assert obs_of({"text": "答えます", "basis_policy": {"outcome": ABS}})["state"] == "abstain"


def test_observation_fields():
    o = obs_of({"kind": "unknown", "verdict": "CONFIRM_REQUEST", "text": "T", "form_text": "F", "constructed": True,
                "sources": [{"origin": "generated"}, {"family": "document"}, "x", {"origin": 3}],
                "confirm": {"question": "Q？"}, "reference_generated": [],
                "basis_policy": {"outcome": CR}})
    assert o["source_origins"] == ["generated", None, "<non-str>"]
    assert (o["confirm_present"], o["confirm_text"], o["confirm_text_field"]) == (True, "Q？", "question")
    assert o["reference_generated_present"] and o["constructed"] and o["form_text"] == "F"
    o2 = obs_of({"confirm": {"text": "A", "question": "B"}, "basis_policy": {"outcome": CR}})
    assert (o2["confirm_text"], o2["confirm_text_field"]) == ("A", "text")
    o3 = obs_of({"confirm": {"text": "  ", "question": "B"}, "basis_policy": {"outcome": CR}})
    assert (o3["confirm_text"], o3["confirm_text_field"]) == ("B", "question")
    o4 = obs_of({"confirm": {}, "constructed": "yes", "text": 5, "verdict": 3, "basis_policy": {"outcome": CR}})
    assert o4["confirm_text"] is None and o4["confirm_present"] and not o4["constructed"]
    assert o4["text"] == "" and o4["verdict"] is None


# ---- 確認の問いの形（J6）------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,lang,result,reason", [
    ("この内容は正しいですか？", "ja", PASS, "CONFIRM_QUESTION_FORM"),
    ("この内容は正しいですか?", "ja", PASS, "CONFIRM_QUESTION_FORM"),
    ("この内容は正しいですか", "ja", PASS, "CONFIRM_QUESTION_FORM"),
    ("東京です。", "ja", FAIL, "CONFIRM_ASSERTIVE"),
    ("正しいですか。", "ja", FAIL, "CONFIRM_ASSERTIVE"),
    ("正しいです", "ja", FAIL, "CONFIRM_ASSERTIVE"),
    ("正しいです！", "ja", FAIL, "CONFIRM_ASSERTIVE"),
    ("生成コーパスには「X」とあります。この内容は正しいですか？ はい／いいえ", "ja", UNJUDGED,
     "CONFIRM_TEXT_UNTERMINATED_TAIL"),
    ("正しいですか。 はい／いいえ", "ja", UNJUDGED, "CONFIRM_TEXT_UNTERMINATED_TAIL"),
    ("東京です。 はい／いいえ", "ja", FAIL, "CONFIRM_ASSERTIVE"),
    ("Is this correct?", "en", PASS, "CONFIRM_QUESTION_FORM"),
    ("Is this correct？", "en", PASS, "CONFIRM_QUESTION_FORM"),
    ("It is Tokyo.", "en", FAIL, "CONFIRM_ASSERTIVE"),
    ("It is Tokyo", "en", FAIL, "CONFIRM_ASSERTIVE"),
    ("Is this correct. yes or no", "en", FAIL, "CONFIRM_ASSERTIVE"),
    ("The corpus says X. Is this correct? Yes/No", "en", UNJUDGED, "CONFIRM_TEXT_UNTERMINATED_TAIL"),
    ("正しいですか", "en", FAIL, "CONFIRM_ASSERTIVE"),
])
def test_judge_confirm(text, lang, result, reason):
    j = b7.judge_confirm(text, lang, "text")
    assert (j["result"], j["detail"]["reason"]) == (result, reason)
    if result == UNJUDGED:
        assert j["detail"]["surface_approx"] == PASS


def test_judge_confirm_not_observed_is_pass_with_reason():
    j = b7.judge_confirm(None, "ja")
    assert j["result"] == PASS and j["detail"]["reason"] == "CONFIRM_TEXT_NOT_OBSERVED"


# ---- 字句の照合（J15）----------------------------------------------------------------------------------------
def test_extract_tokens_patterns_and_nfkc():
    assert b7.extract_tokens("2024年のコーヒー販売") == ["2024", "コーヒー", "販売"]
    assert b7.extract_tokens("１２３と４５６") == ["123", "456"]  # 全角数字は NFKC で半角
    assert b7.extract_tokens("ｺｰﾋｰ") == ["コーヒー"]  # 半角カナ
    assert b7.extract_tokens("人々の暮らし") == ["人々"]  # 々 は漢字の連なりに入る。暮・し は 1 字
    assert b7.extract_tokens("ーー") == []  # 長音だけの並びは除く
    assert b7.extract_tokens("ー") == []
    assert b7.extract_tokens("ロー") == ["ロー"]
    assert b7.extract_tokens("The Tokyo office opens at 9 am on Monday") == ["The", "Tokyo", "9", "Monday"]
    assert b7.extract_tokens("a1 B2c") == ["1", "B2c", "2"]
    assert b7.extract_tokens("東と西") == []  # 漢字 1 字は取らない
    assert b7.extract_tokens("") == []
    assert b7.extract_tokens("東京都庁") == ["東京都庁"]
    assert b7.extract_tokens("東京と東京") == ["東京"]  # 重複なし


def test_extract_tokens_order_is_position_order_and_unique():
    assert b7.extract_tokens("Friday 4 Friday") == ["Friday", "4"]
    assert b7.extract_tokens("後に4時、Friday") == ["4", "Friday"]


def test_content_check_human_first_then_generated():
    hs = ["受付は三階の窓口で行う。"]
    gs = ["受付は三階の窓口で行います。午前九時から。"]
    # 人の出所にある字句は、生成の文にもあっても落ちない
    assert b7.content_from_generated(["受付は三階の窓口で行う。"], hs, gs) == []
    # 生成の文にしか無い字句は落ちる
    assert b7.content_from_generated(["受付は午前九時から。"], hs, gs) == ["午前九時"]
    # どちらにも無い字句は生成由来ではない（照合の対象外）
    assert b7.content_from_generated(["受付は火星の窓口。"], hs, gs) == []
    # 生成の文が無ければ落ちない
    assert b7.content_from_generated(["午前九時"], hs, []) == []
    # NFKC・小文字化で比べる
    assert b7.content_from_generated(["ＴＯＫＹＯ ９"], ["x"], ["tokyo 9 office"]) == ["TOKYO", "9"]
    assert b7.content_from_generated(["Tokyo"], ["tokyo office"], ["Tokyo gate"]) == []
    # 部分文字列: 短い数字は甘く通る（既知の限界）
    assert b7.content_from_generated(["5"], ["15 people"], ["5 seats"]) == []
    # 複数の本文（text と form_text）
    assert b7.content_from_generated(["人は居る"], ["人は居る"], ["人は居る。ホットコーヒー"]) == []
    assert b7.content_from_generated(["人は居る", "ホットコーヒー"], ["人は居る"], ["ホットコーヒー"]) == ["ホットコーヒー"]


# ---- 分類（§3.5）-------------------------------------------------------------------------------------------
def test_correct_and_abstain_matches():
    assert cls(run(item(AHB), out(AHB, text="人の文。"))) == ("correct", None, "correct")
    assert cls(run(item(ABS, acf="none"), out(ABS))) == ("correct_abstain", None, "correct_abstain")
    assert cls(run(item(CON, acf="none"), out(CON, constructed=True))) == ("correct", None, "correct")
    assert cls(run(item(RG, acf="none"), out(RG))) == ("correct", None, "correct")


def test_form_from_generated_counts_for_human_basis_but_not_the_reverse():
    ok = out(AFG, text="人の文。", form_text="人の文です。")
    assert run(item(AHB), ok)["class"] == "correct"
    sc = run(item(AFG), out(AHB, text="人の文。"))
    assert (sc["class"], sc["reason"]) == ("wrong", "OUTCOME_NOT_EXPECTED")
    assert run(item(AFG), out(AFG, text="人の文。", form_text="人の文です。"))["class"] == "correct"


def test_w1_must_not_is_wrong_and_takes_priority():
    sc = run(item(ABS, must_not=(CR,), acf="none"), out(CR, confirm={"text": "正しいですか？"}))
    assert (sc["class"], sc["reason"]) == ("wrong", "W1_MUST_NOT")
    # 期待 ABSTAIN で RG を出して must_not に RG があるときも誤答（over_abstain ではない）
    sc = run(item(AHB, must_not=(RG,)), out(RG))
    assert (sc["class"], sc["reason"]) == ("wrong", "W1_MUST_NOT")
    assert sc["checks"]["w1_must_not"]["result"] == FAIL


def test_w2_answer_with_content_none_is_wrong():
    sc = run(item(RG, acf="none"), out(AHB, text="x"))
    assert (sc["class"], sc["reason"]) == ("wrong", "W2_ANSWER_CONTENT_NONE")
    sc = run(item(CON, acf="none"), out(AFG, text="x", form_text="y"))
    assert (sc["class"], sc["reason"]) == ("wrong", "W2_ANSWER_CONTENT_NONE")
    assert "w3_content" not in sc["checks"]


def test_w3_content_from_generated():
    it = item(AHB, hs=("ロビーの売店は朝早くから開いている。",), gs=("ロビーの売店は午前七時三十分から開く。",))
    sc = run(it, out(AHB, text="売店は午前七時三十分から開く。"))
    assert (sc["class"], sc["reason"]) == ("wrong", "W3_CONTENT_FROM_GENERATED")
    assert sc["checks"]["w3_content"]["detail"]["content_from_generated"] == ["午前七時三十分"]
    assert run(it, out(AHB, text="売店は朝早くから開いている。"))["class"] == "correct"
    # ANSWER_FORM_FROM_GENERATED では form_text も照合する
    sc = run(it, out(AFG, text="売店は朝早くから。", form_text="売店は午前七時三十分から。"))
    assert (sc["class"], sc["reason"]) == ("wrong", "W3_CONTENT_FROM_GENERATED")
    # ANSWER_HUMAN_BASIS では form_text は見ない
    assert run(it, out(AHB, text="売店は朝早く。", form_text="午前七時三十分"))["class"] == "correct"


def test_w4_confirm_forms():
    it = item(CR, acf="none", hs=(), gs=("g",), hp=True)
    sc = run(it, out(CR, confirm={"text": "東京です。"}))
    assert (sc["class"], sc["reason"]) == ("wrong", "W4_CONFIRM_ASSERTIVE")
    assert run(it, out(CR, confirm={"text": "東京ですか？"}))["class"] == "correct"
    sc = run(it, out(CR, confirm={"question": "…とあります。この内容は正しいですか？ はい／いいえ"}))
    assert cls(sc) == ("unscorable", "JUDGE_UNAVAILABLE", "correct")
    sc = run(it, out(CR))  # 文が観測できない: 誤答にも採点不能にもしない
    assert sc["class"] == "correct" and sc["checks"]["w4_confirm_form"]["detail"]["reason"] == "CONFIRM_TEXT_NOT_OBSERVED"
    en = item(CR, acf="none", hs=(), gs=("g",), hp=True, lang="en")
    assert run(en, out(CR, confirm={"text": "Is it Tokyo?"}))["class"] == "correct"
    assert run(en, out(CR, confirm={"text": "It is Tokyo."}))["reason"] == "W4_CONFIRM_ASSERTIVE"


def test_w5_constructed_mark():
    it = item(CON, acf="none", kind="creative")
    sc = run(it, out(CON))  # kind answer / verdict ANSWER で印なし
    assert (sc["class"], sc["reason"]) == ("wrong", "W5_CONSTRUCTED_UNMARKED")
    assert run(it, out(CON, constructed=True))["class"] == "correct"
    assert run(it, out(CON, kind="created", verdict="CREATED"))["class"] == "correct"  # 型が answer/ANSWER でなければ対象外
    assert run(it, out(CON, constructed="true"))["reason"] == "W5_CONSTRUCTED_UNMARKED"


def test_over_abstain_and_false_compliance():
    assert run(item(AHB), out(ABS))["class"] == "over_abstain"
    assert run(item(CON, acf="none"), out(ABS))["class"] == "over_abstain"
    assert run(item(CR, acf="none"), out(ABS))["class"] == "over_abstain"
    assert run(item(RG, acf="none"), out(ABS))["class"] == "over_abstain"
    for E in (AHB, AFG, CON, CR):
        assert run(item(E, acf="human" if E in (AHB, AFG) else "none"), out(RG))["class"] == "over_abstain"
    # E == ABSTAIN で RG は over_abstain ではなく OUTCOME_NOT_EXPECTED
    assert run(item(ABS, acf="none"), out(RG))["reason"] == "OUTCOME_NOT_EXPECTED"
    sc = run(item(RG, acf="human"), out(AHB, text="x"))
    assert sc["class"] == "false_compliance"
    sc = run(item(RG, acf="human"), out(AFG, text="x", form_text="y"))
    assert sc["class"] == "false_compliance"


def test_other_mismatches_are_wrong_outcome_not_expected():
    for E, O in ((ABS, CR), (ABS, CON), (CON, CR), (CR, CON), (CON, AHB), (AHB, CON), (AHB, CR), (CR, AHB)):
        o = out(O, text="x", confirm={"text": "よいですか？"}, constructed=True)
        sc = run(item(E, acf="human"), o)
        assert (sc["class"], sc["reason"]) == ("wrong", "OUTCOME_NOT_EXPECTED"), (E, O)


def test_outcome_missing_is_unscorable_not_abstain():
    for o in ({"kind": "answer"}, {"basis_policy": {"outcome": None, "reason": "NO_CITED_SOURCES"}},
              {"basis_policy": {"outcome": "x"}}):
        sc = run(item(ABS, acf="none"), o)
        assert (sc["class"], sc["reason"], sc["class_approx"]) == ("unscorable", "OUTCOME_MISSING", "unscorable")
        assert sc["checks"]["outcome"]["detail"]["kind"] in b7.OUTCOME_MISSING_KINDS


def test_unknown_keys_make_it_unscorable_and_keep_other_results():
    it = item(AHB)
    it["expect"]["extra_flag"] = 1
    it["mystery"] = 2
    sc = run(it, out(ABS))
    assert (sc["class"], sc["reason"], sc["class_approx"]) == ("unscorable", "JUDGE_UNAVAILABLE", "unscorable")
    assert sc["unknown_expect_keys"] == ["expect.extra_flag", "top.mystery"]
    assert "w1_must_not" in sc["checks"] and sc["checks"]["unknown_expect_keys"]["result"] == UNJUDGED
    # evidence は既知（記録だけ）
    assert keys.find_unknown("B7", item()) == []


def test_misread_never_appears_and_priority_is_wrong_before_false_compliance():
    seen = set()
    for E in b7.OUTCOMES:
        for O in b7.OUTCOMES:
            for acf in ("human", "none"):
                if E in b7.ANSWER_OUTCOMES and acf == "none":
                    continue
                sc = run(item(E, acf=acf), out(O, text="x", form_text="y", confirm={"text": "よいですか？"},
                                                constructed=True))
                seen.add(sc["class"])
                assert sc["side"] == ("abstain" if E == ABS else "answer")
    assert "misread" not in seen and "unreachable" not in seen and "runtime_error" not in seen
    # E=RG, acf=none, O=ANSWER は false_compliance でなく wrong（W2 が先）
    assert run(item(RG, acf="none"), out(AHB, text="x"))["class"] == "wrong"


# ---- 見出しの条件（J10）-----------------------------------------------------------------------------------
@pytest.mark.parametrize("ev,expect", [("A", True), ("B", True), ("D", True), ("A, B", True), ("案A", True),
                                      ("Ｄ", True), ("C", False), ("E", False), ("F", False), ("C+E", False),
                                      ("A+C", None), ("", None), (None, None), (3, None), ("none", None),
                                      ("Case A", True), ("A案とD案", True)])
def test_evidence_judgement(ev, expect):
    assert b7.evidence_judgement(ev) is expect


def test_generated_only_rules():
    def go(E, kind="factual", hs=(), ev="C"):
        it = item(E, kind=kind, hs=hs, acf="human" if E in (AHB, AFG) else "none", evidence=ev)
        errs, case = b7.validate_item(it)
        assert errs == []
        return b7.generated_only(case, it["expect"])
    assert go(AHB) is True  # 事実の問いで人の出所が無い
    assert go(AHB, hs=("x",)) is False
    assert go(ABS, kind="creative", hs=("x",), ev="A") is True
    assert go(CR, kind="creative", hs=("x",), ev="C") is False
    assert go(RG, kind="style", hs=("x",), ev="A+C") is None
    assert go(CON, kind="creative", hs=("x",), ev="A") is False  # E が対象の 3 値でない
    assert go(ABS, kind="creative", hs=(), ev="") is None

"""B2 v2: 正規化・全体一致の must_not_equal・最初の選択肢・format の 7 項目・文チェック（R4）・棄権文の禁止句・根拠の別集計。"""
import copy

import v2_util as U
from v2_util import b2_item, obs

DOC = ["港の灯台は、毎朝六時に点灯される。点灯は三十分続く。", "灯台の管理室は北側にある。"]


def sc(raw, o, **kw):
    return U.score("B2", raw, o)


def cls(raw, o):
    return sc(raw, o)["class"]


def ans(text, **kw):
    return obs("answer", text=text, **kw)


def test_normalization_drops_all_whitespace_and_punctuation_and_number_commas():
    raw = b2_item("fx", must_contain_any=[["1200円"], ["午後5時", "17時"]])
    assert cls(raw, ans("料金は 1,200 円で、閉店は 午後 5 時 です。")) == "correct"
    raw2 = b2_item("fx", must_contain_any=[["5pm"]], lang="en")
    assert cls(raw2, ans("It closes at 5 p.m. today.")) == "correct"
    raw3 = b2_item("fx", must_contain_any=[["ＡＢＣ"]], lang="en")
    assert cls(raw3, ans("abc is the code")) == "correct"
    # 空白をまたぐ必須語
    raw4 = b2_item("fx", must_contain_any=[["点灯 時刻"]])
    assert cls(raw4, ans("点灯時刻は朝です。")) == "correct"


def test_outer_groups_are_all_required_inner_any_and_missing_group_fails():
    raw = b2_item("fx", must_contain_any=[["朝六時", "6時"], ["三十分", "30分"]])
    assert cls(raw, ans("朝六時に点灯し、30分続く。")) == "correct"
    s = sc(raw, ans("朝六時に点灯する。"))
    assert s["class"] == "wrong" and s["checks"]["must_contain_any"]["result"] == "FAIL"


def test_must_not_contain_must_contain_all_and_empty_output():
    raw = b2_item("fx", must_contain_all=["六時"], must_not_contain=["七時"])
    assert cls(raw, ans("六時です。")) == "correct"
    assert cls(raw, ans("六時ではなく七時です。")) == "wrong"
    assert cls(raw, ans("")) == "wrong"  # 空は不合格（空出力を正答にしない）


def test_must_not_equal_is_whole_output_match_against_global_forbidden_and_extras():
    raw = b2_item("fx", query="灯台はいつ点灯しますか", docs=DOC, must_not_equal=["要約です"])
    assert cls(raw, ans("港の灯台は、毎朝六時に点灯される。")) == "wrong"  # 文書の 1 文の丸写し
    assert cls(raw, ans("灯台はいつ点灯しますか")) == "wrong"  # 最後の user 発話
    assert cls(raw, ans("".join(DOC))) == "wrong"  # 全文書連結
    assert cls(raw, ans("要約です")) == "wrong"  # 指定
    # 1 文だけ一致する長い出力は FAIL にならない（設計者の judge() と同じ）
    s = sc(raw, ans("港の灯台は、毎朝六時に点灯される。なお詳しい手順は別紙にあります。"))
    assert s["checks"]["must_not_equal"]["result"] == "PASS"
    multi = b2_item("fx", query="一つ目の質問", docs=[])
    multi["turns"] = [{"role": "user", "content": "一つ目"}, {"role": "assistant", "content": "はい"},
                      {"role": "user", "content": "二つ目"}]
    assert sc(multi, ans("一つ目二つ目"))["checks"]["must_not_equal"]["result"] == "FAIL"  # 全 user 発話の連結


def test_max_chars_counts_nonspace_chars_and_reply_lang_ja_en():
    raw = b2_item("fx", max_chars=5)
    assert cls(raw, ans("あ い う え お")) == "correct"
    assert cls(raw, ans("あいうえおか")) == "wrong"
    ja = b2_item("fx", reply_lang="ja")
    assert cls(ja, ans("Yes it is")) == "wrong"
    assert cls(ja, ans("はい、そうです")) == "correct"
    en = b2_item("fx", reply_lang="en", lang="en")
    assert cls(en, ans("Yes it is")) == "correct"
    assert cls(en, ans("Yes そう")) == "wrong"


def test_choice_takes_the_first_appearing_option():
    raw = b2_item("fx", choice={"options": [["案A"], ["案B", "Bの案"]], "answer": 1})
    assert cls(raw, ans("案Bを選びます。案Aは見送ります。")) == "correct"
    assert cls(raw, ans("案Aではなく案Bです。")) == "wrong"  # 最初に現れた選択肢が A
    assert cls(raw, ans("どちらでもない。")) == "wrong"


def test_format_seven_items_are_individual_rules():
    f = {"target_lang": "ja", "lines": [2, 3], "bullets": True, "sentences": [2, 3], "max_chars": 30, "polite": True}
    raw = b2_item("fx", category="instruction_transform", behavior="transform", format=f)
    good = "・朝に点灯します。\n・夜に消えます。"
    s = sc(raw, ans(good))
    assert s["class"] == "correct", s["checks"]
    for name in ("format.target_lang", "format.lines", "format.bullets", "format.sentences", "format.max_chars",
                 "format.polite"):
        assert name in s["checks"]
    assert sc(raw, ans("朝に点灯します。夜に消えます。"))["checks"]["format.bullets"]["result"] == "FAIL"
    assert sc(raw, ans("・朝に点灯します。"))["checks"]["format.lines"]["result"] == "FAIL"
    assert sc(raw, ans("・朝に点灯する。\n・夜に消える。"))["checks"]["format.polite"]["result"] == "FAIL"
    plain = b2_item("fx", category="instruction_transform", behavior="transform", format={"plain": True})
    assert sc(plain, ans("朝に点灯する。"))["class"] == "correct"
    assert sc(plain, ans("朝に点灯します。"))["class"] == "wrong"
    assert sc(plain, ans("朝に点灯する。"))["checks"]["format.plain"]["result"] == "PASS"


def check_item(label="SUPPORTED"):
    raw = b2_item("fx", category="sentence_check", docs=DOC, label=label, reference=label)
    raw["check_claim"] = "主張の文です"
    return raw


def test_sentence_check_label_from_type_or_exactly_one_label_in_text_and_r4_table():
    raw = check_item("REFUTED")
    assert cls(raw, obs("answer", verdict="REFUTED", text="")) == "correct"  # 型の verdict が 3 ラベルならそれ
    assert cls(raw, obs("answer", verdict="SUPPORTED", text="")) == "wrong"
    assert cls(raw, ans("REFUTED")) == "correct"
    assert cls(raw, ans("refuted です")) == "correct"  # 英語は大小無視
    assert cls(raw, ans("反証")) == "correct"  # R4: 日本語のラベル
    assert cls(check_item("SUPPORTED"), ans("支持されます")) == "correct"
    assert cls(check_item("NOT_IN_DOCS"), ans("未記載です")) == "correct"
    assert cls(check_item("NOT_IN_DOCS"), ans("not in docs")) == "correct"
    assert cls(raw, ans("SUPPORTED REFUTED NOT_IN_DOCS")) == "wrong"  # 3 つ並べると不合格
    assert cls(raw, ans("REFUTED か SUPPORTED")) == "wrong"  # 2 種類も不合格
    assert cls(raw, ans("unsupported")) == "wrong"  # 語の一部は数えない
    assert sc(raw, ans("REFUTED"))["checks"].keys() == {"label"}  # 他の規則は当てない（judge() と同じ）


def test_sentence_check_not_in_docs_type_is_a_label_answer_not_an_abstention_in_v2_adapter():
    from tools.bank_score import adapters
    raw = check_item("NOT_IN_DOCS")
    o = adapters.observe("B2", {"kind": "unknown", "verdict": "NOT_IN_DOCS", "text": ""}, "cli-ask-round5", [], 0, raw,
                         profile="v2")
    assert o["state"] == "answer" and o["label_override"] is True
    assert cls(raw, o) == "correct"
    # 期待が棄権の問題では、これは棄権のまま
    ab = b2_item("fx", category="sentence_check", behavior="abstain", label="NOT_IN_DOCS")
    o2 = adapters.observe("B2", {"kind": "unknown", "verdict": "NOT_IN_DOCS", "text": ""}, "cli-ask-round5", [], 0, ab,
                          profile="v2")
    assert o2["state"] == "abstain"


def test_abstain_question_applies_must_not_contain_even_when_state_is_abstain():
    raw = b2_item("fx", behavior="abstain", must_not_contain=["七時に点灯"])
    ok = sc(raw, obs("abstain", text="点灯の時刻は分かりません。"))
    assert ok["class"] == "correct_abstain"
    bad = sc(raw, obs("abstain", text="七時に点灯します。"))
    assert (bad["class"], bad["reason"]) == ("wrong", "ABSTAIN_TEXT_RULE_FAIL")
    assert sc(raw, ans("七時に点灯します。"))["class"] == "false_compliance"
    assert sc(b2_item("fx"), obs("abstain"))["class"] == "over_abstain"


def test_evidence_is_a_separate_tally_that_does_not_change_the_content_class():
    raw = b2_item("fx", must_contain_any=[["六時"]], evidence=["港の灯台は、毎朝六時に点灯される。"],
                  evidence_required=True)
    base = dict(text="六時です。")
    s_pass = sc(raw, obs("answer", evidence_texts=["港の灯台は、毎朝六時に点灯される。点灯は三十分続く。"], **base))
    s_fail = sc(raw, obs("answer", evidence_texts=["関係のない文"], **base))
    s_none = sc(raw, obs("answer", evidence_texts=[], **base))
    s_unobs = sc(raw, obs("answer", **base))  # 観測されていない（参考例など）
    assert [s["class"] for s in (s_pass, s_fail, s_none, s_unobs)] == ["correct"] * 4
    assert [s["evidence_match"] for s in (s_pass, s_fail, s_none, s_unobs)] == ["PASS", "FAIL", "FAIL", "UNJUDGED"]
    not_req = b2_item("fx", must_contain_any=[["六時"]], evidence=["x"], evidence_required=False)
    assert sc(not_req, ans("六時"))["evidence_match"] == "NOT_REQUIRED"


def test_adapter_collects_evidence_texts_from_string_and_dicts_only_in_v2():
    from tools.bank_score import adapters
    raw = {"kind": "answer", "verdict": "ANSWER", "text": "t", "evidence": "文字列の根拠",
           "sources": [{"text": "辞書の根拠", "id": 1}, "別の根拠", 5]}
    o = adapters.observe("B2", raw, "cli-ask-round5", [], 0, b2_item("fx"), profile="v2")
    assert o["evidence_texts"] == ["文字列の根拠", "辞書の根拠", "別の根拠"]
    assert "evidence_texts" not in adapters.observe("B2", raw, "cli-ask-round5", [], 0, b2_item("fx"))


def test_validation_of_v2_shapes():
    raw = b2_item("fx", choice={"options": [["a"], ["b"]], "answer": 1}, format={"lines": [1, 2]})
    assert U.validate("B2", raw)[0] == []
    r = copy.deepcopy(raw)
    r["expect"]["choice"]["answer"] = 5
    assert "BAD_TYPE:expect.choice" in U.validate("B2", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["format"]["lines"] = [3, 1]
    assert "BAD_TYPE:expect.format.lines" in U.validate("B2", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["reply_lang"] = "fr"
    assert "BAD_VALUE:expect.reply_lang" in U.validate("B2", r)[0]
    r = check_item()
    del r["expect"]["label"]
    assert "BAD_VALUE:expect.label" in U.validate("B2", r)[0]
    r = copy.deepcopy(raw)
    r["turns"] = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    assert "BAD_LAST_TURN" in U.validate("B2", r)[0]


def test_choice_tie_at_the_same_first_position_is_unjudged_not_a_win_for_the_first_listed_option():
    raw = b2_item("fx", choice={"options": [["案"], ["案B"]], "answer": 1})
    s = sc(raw, ans("案Bです。"))
    assert s["checks"]["choice"]["result"] == "UNJUDGED" and s["checks"]["choice"]["detail"]["reason"] == "CHOICE_TIED"
    assert (s["class"], s["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")

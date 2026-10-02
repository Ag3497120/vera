"""B3 v2: null の制約、リスト型の state、constructed_only の created、b3_state の型、@LEX、英語の語数、form、order、
読解器が要る制約（主分類は UNJUDGED のまま、class_approx だけが変わる）、拒否問題の本文規則。"""
import copy

import pytest

import v2_util as U
from tools.bank_score.v2 import b3
from v2_util import b3_item, obs

NOT_APPLICABLE_TO_PLAIN = ("compression", "max_chars", "sentences", "form", "starts_with", "register", "min_edit_ratio")


def sc(raw, o):
    return U.score("B3", raw, o)


def cls(raw, o):
    return sc(raw, o)["class"]


def ans(text, **kw):
    return obs("answer", text=text, **kw)


def test_null_and_empty_constraints_are_not_rules():
    raw = b3_item("fx", must_not_equal=False)
    s = sc(raw, ans("出力の文です。"))
    assert s["class"] == "correct", s["checks"]
    assert set(s["checks"]) == {"state", "non_empty", "language", "new_content_words"}  # null / [] / false は規則にならない
    assert s["checks"]["new_content_words"]["detail"] == {"trivial": True}  # {"allowed": true, "min": 0} は読解器なしで PASS
    for k in NOT_APPLICABLE_TO_PLAIN:
        assert k not in s["checks"]


def test_state_list_accepts_any_and_constructed_only_also_accepts_created():
    lst = b3_item("fx", state=["answer", "created"])
    assert cls(lst, ans("文です。")) == "correct"
    assert cls(lst, obs("answer", text="文です。", declared_constructed=True)) == "correct"
    assert cls(lst, obs("answer", text="文です。", constructed=True)) == "wrong"
    co = b3_item("fx", state="constructed", outside="constructed_only")
    assert cls(co, obs("answer", text="文です。", constructed=True)) == "correct"
    assert cls(co, obs("answer", text="文です。", declared_constructed=True)) == "correct"  # created も可（FINAL §6 条件 1）
    assert cls(co, ans("文です。")) == "wrong"  # answer（事実として言い切る）は不可
    der = b3_item("fx", state="answer", outside="derivable")
    assert cls(der, obs("answer", text="文です。", constructed=True)) == "wrong"  # derivable は answer だけ
    assert cls(der, ans("文です。")) == "correct"
    # 型が違えば、文字列の規則を見ずに不合格
    s = sc(co, ans("文です。"))
    assert set(s["checks"]) == {"state"}


@pytest.mark.parametrize("o, want", [
    (obs("abstain"), "refuse"),
    (obs("abstain", constructed=True), "refuse"),                    # ABSTAIN_* かつ constructed: 棄権の型が優先
    (obs("answer", declared_constructed=True), "created"),
    (obs("answer", constructed=True), "constructed"),
    (obs("answer"), "answer"),
    (obs("social"), "social"),
    (obs("answer", declared_constructed=True, constructed=True), None),  # 両方立っていたら決めない
])
def test_b3_state_is_decided_from_observed_types_only(o, want):
    assert b3.b3_state(o) == want


def test_type_ambiguous_is_unjudged_and_social_matches_nothing():
    raw = b3_item("fx", state=["answer", "created"])
    s = sc(raw, obs("answer", text="文です。", declared_constructed=True, constructed=True))
    assert s["checks"]["state"]["detail"]["reason"] == "TYPE_AMBIGUOUS" and s["class"] == "unscorable"
    assert cls(raw, obs("social", text="文です。")) == "wrong"


def test_v2_adapter_treats_constructed_result_with_unmapped_verdict_as_a_constructed_answer():
    from tools.bank_score import adapters
    r = {"kind": "x", "verdict": "EXPLAINED_BY_UNITS", "constructed": True, "text": "候補"}
    assert adapters.observe("B3", r, "cli-ask-round5", [], 0, None)["state"] == "unmapped"  # w1s のまま
    o = adapters.observe("B3", r, "cli-ask-round5", [], 0, None, profile="v2")
    assert o["state"] == "answer" and b3.b3_state(o) == "constructed"
    ab = adapters.observe("B3", {"kind": "unknown", "verdict": "ABSTAIN_X", "constructed": True, "text": ""},
                          "cli-ask-round5", [], 0, None, profile="v2")
    assert ab["state"] == "abstain" and b3.b3_state(ab) == "refuse"


def test_lex_names_expand_and_keep_punctuation_in_needles():
    raw = b3_item("fx", must_contain_any=[["@CAUSE_JA"]], must_contain_all=["@CONTRAST_JA"])
    assert cls(raw, ans("橋が壊れたため、道は閉じたが、街は静かだ。")) == "correct"
    assert cls(raw, ans("橋は壊れた。道は閉じた。")) == "wrong"
    # 読点つきの語彙（「から、」）は読点まで照合する
    only = b3_item("fx", must_contain_any=[["から、"]])
    assert cls(only, ans("雨だから、帰る。")) == "correct"
    assert cls(only, ans("雨だから帰る。")) == "wrong"
    bad = b3_item("fx", must_contain_any=[["@NO_SUCH_LEX"]])
    assert any(e.startswith("BAD_VALUE") for e in U.validate("B3", bad)[0])


def test_english_max_chars_counts_words_japanese_counts_non_space_chars():
    en = b3_item("fx", lang="en", max_chars=5, materials=["Source text."])
    assert cls(en, ans("one two three four five")) == "correct"
    assert cls(en, ans("one two three four five six")) == "wrong"
    ja = b3_item("fx", max_chars=4)
    assert cls(ja, ans("あ い う え")) == "correct"
    assert cls(ja, ans("あいうえお")) == "wrong"


def test_sentence_counting_rules_and_sentences_ignored_when_form_is_given():
    one = b3_item("fx", sentences={"min": 1, "max": 1})
    assert cls(one, ans("彼は「来た。見た。」と言った。")) == "correct"  # 括弧内の句点は数えない
    assert cls(one, ans("来た。見た。")) == "wrong"
    en = b3_item("fx", lang="en", sentences={"min": 2, "max": 2}, materials=["x"])
    assert cls(en, ans("Mr. Lee paid 3.5 dollars. He left.")) == "correct"  # Mr. と小数点は区切りにしない
    assert cls(en, ans("It is done. Yes. Fine.")) == "wrong"
    form = b3_item("fx", sentences={"min": 1, "max": 1}, form={"type": "lines", "n": 2})
    s = sc(form, ans("一行目\n二行目"))
    assert "sentences" not in s["checks"] and s["checks"]["form"]["result"] == "PASS"


TABLE = "| 品目 | 数量 |\n|---|---|\n| りんご | 3個 |\n| みかん | 5個 |"


def form_of(**f):
    return b3_item("fx", form=f)


def test_form_table_with_cells_numbered_memo_email_dialogue_lines_haiku():
    t = form_of(type="table", columns=["品目", "数量"], rows=2, cells={"りんご": {"数量": ["3"]}, "みかん": {"数量": ["5", "五"]}})
    assert cls(b3_item("fx", form=t["expect"]["constraints"]["form"]), ans(TABLE)) == "correct"
    wrong_cell = TABLE.replace("5個", "9個")
    s = sc(b3_item("fx", form=t["expect"]["constraints"]["form"]), ans(wrong_cell))
    assert s["checks"]["form"]["detail"]["reason"] == "CELLS_VALUE" and s["class"] == "wrong"
    assert sc(b3_item("fx", form={"type": "table", "columns": ["品目", "数量"], "rows": 3}), ans(TABLE))["checks"]["form"]["detail"]["reason"] == "ROWS"
    num = form_of(type="numbered_list", items=3)
    assert cls(num, ans("1. 切る\n2. 開く\n3. 閉じる")) == "correct"
    assert cls(num, ans("1. 切る\n3. 開く\n4. 閉じる")) == "wrong"  # 連番でない
    assert cls(form_of(type="bullet_list", items=2), ans("- あ\n・い")) == "correct"
    assert cls(form_of(type="checklist", items=2), ans("[ ] あ\n☐ い")) == "correct"
    memo = form_of(type="labeled_memo", labels=["日時", "場所"])
    assert cls(memo, ans("日時: 明日\n場所：広場")) == "correct"
    assert cls(memo, ans("場所: 広場\n日時: 明日")) == "wrong"  # 指定順
    email = form_of(type="email", parts=["件名", "本文"], subject_max_chars=10, body_sentences={"min": 1, "max": 2})
    assert cls(email, ans("件名: 集合の連絡\n明日集まります。よろしく。")) == "correct"
    assert cls(email, ans("集合の連絡\n明日集まります。")) == "wrong"
    assert cls(email, ans("件名: とても長い長い長い件名です\n明日集まります。")) == "wrong"
    dlg = form_of(type="dialogue", turns=3, speakers=["甲", "乙"], alternate=True)
    assert cls(dlg, ans("甲: こんにちは\n乙: やあ\n甲「元気」")) == "correct"
    assert cls(dlg, ans("甲: こんにちは\n甲: やあ\n乙: 元気")) == "wrong"
    lines = form_of(type="lines", n=2, starts=["A", "b"])
    assert cls(b3_item("fx", lang="en", form={"type": "lines", "n": 2, "starts": ["A", "b"]}, materials=["x"]),
               ans("Apple\nBanana")) == "correct"
    assert cls(lines, ans("あ\nい")) == "wrong"
    hk = form_of(type="haiku", mora=[5, 7, 5], script="hiragana")
    assert cls(hk, ans("ふるいけや\nかわずとびこむ\nみずのおと")) == "correct"
    assert cls(hk, ans("古池や\nかわずとびこむ\nみずのおと")) == "wrong"  # ひらがな以外


def test_haiku_without_hiragana_script_and_with_kanji_needs_a_reader_and_gets_a_surface_approx():
    hk = form_of(type="haiku", mora=[5, 7, 5])
    s = sc(hk, ans("古池や\nかわずとびこむ\nみずのおと"))
    f = s["checks"]["form"]
    assert f["result"] == "UNJUDGED" and f["detail"]["reason"] == "NEEDS_READER"
    assert f["detail"]["surface_approx"] in ("PASS", "FAIL")
    assert (s["class"], s["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")
    # 仮名だけなら決定的
    assert cls(hk, ans("ふるいけや\nかわずとびこむ\nみずのおと")) == "correct"


def test_unknown_form_type_is_unjudged_and_unknown_form_key_is_recorded():
    raw = form_of(type="spreadsheet", items=2)
    assert U.validate("B3", raw)[0] == []  # 検証は通す（採点できない型として扱う）
    s = sc(raw, ans("何か"))
    assert s["checks"]["form"]["detail"]["reason"] == "UNKNOWN_FORM_TYPE"
    assert (s["class"], s["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")
    odd = form_of(type="numbered_list", items=2, indentation=3)
    s2 = sc(odd, ans("1. あ\n2. い"))
    assert s2["unknown_expect_keys"] == ["expect.constraints.form[numbered_list].indentation"]
    assert s2["class"] == "unscorable"


def test_min_edit_ratio_starts_with_register_compression_must_not_equal():
    mat = ["港の灯台は朝に点灯される。"]
    raw = b3_item("fx", materials=mat, min_edit_ratio=0.3, must_not_equal=True)
    assert cls(raw, ans("港の灯台は朝に点灯される。")) == "wrong"
    assert cls(raw, ans("港の灯台は朝に点灯される！")) == "wrong"  # 句読点だけの違いは同じ文（squash）
    assert cls(raw, ans("夜明けに港のあかりがともる。")) == "correct"
    assert sc(raw, ans("港の灯台は朝に点灯される。"))["checks"]["min_edit_ratio"]["result"] == "FAIL"
    st = b3_item("fx", starts_with=["まず"], register="polite")
    assert cls(st, ans("「まず」手順を示します。")) == "correct"
    assert cls(st, ans("次に手順です。")) == "wrong"
    assert cls(b3_item("fx", register="plain"), ans("手順を示します。")) == "wrong"
    cp = b3_item("fx", materials=["あ" * 20], compression={"max_ratio": 0.5})
    assert cls(cp, ans("あ" * 10)) == "correct" and cls(cp, ans("あ" * 11)) == "wrong"
    assert sc(b3_item("fx", materials=[], compression={"max_ratio": 0.5}), ans("あ"))["checks"]["compression"]["detail"]["reason"] == "EMPTY_MATERIALS"


def test_order_pass_fail_mixed_not_found_and_surface_approx():
    raw = b3_item("fx", order=[["切る"], ["開ける", "開く"]])
    assert cls(raw, ans("紙を切ってから箱を開ける。")) == "correct"
    assert cls(raw, ans("箱を開けてから紙を切る。")) == "wrong"
    mixed = sc(raw, ans("開けて切って開ける。"))
    assert mixed["checks"]["order"]["detail"]["reason"] == "ORDER_MIXED_OR_OVERLAP" and mixed["class"] == "unscorable"
    nf = sc(raw, ans("何もしない。"))
    assert nf["checks"]["order"]["detail"]["reason"] == "LEMMA_NOT_FOUND"
    assert nf["checks"]["order"]["detail"]["surface_approx"] == "FAIL" and nf["class_approx"] == "wrong"
    assert mixed["class_approx"] in ("correct", "wrong")


def test_reader_constraints_stay_unjudged_in_the_main_class_and_only_class_approx_changes():
    mx = {"predicate": ["止まる"], "agent": ["ポンプ"], "patient": None, "polarity": "+"}
    raw = b3_item("fx", must_express=[mx], must_not_relate=[{"rel": "cause", "from": ["止まる"], "to": ["凍る"]}])
    good = sc(raw, ans("ポンプが止まる。"))
    assert (good["class"], good["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")  # 主分類は読解器なしでは決めない
    assert good["class_approx"] == "correct"
    assert good["checks"]["must_express"]["detail"]["surface_approx"] == "PASS"
    assert good["checks"]["must_not_relate"]["detail"]["surface_approx"] == "PASS"  # 近似では検出できない（常に PASS）
    bad = sc(raw, ans("扉が開く。"))
    assert bad["class_approx"] == "wrong"
    # 決定的な規則が FAIL なら読解器が要る規則が残っていても主分類で誤答
    raw2 = b3_item("fx", must_express=[mx], must_contain_all=["ポンプ"])
    assert sc(raw2, ans("扉が開く。"))["class"] == "wrong"
    rel = b3_item("fx", must_relate=[{"rel": "cause", "from": ["凍る"], "to": ["止まる"]}])
    r1 = sc(rel, ans("凍ったので止まる。"))
    assert r1["class"] == "unscorable" and r1["class_approx"] == "correct"
    r2 = sc(rel, ans("何もない。"))
    assert r2["class_approx"] == "wrong"


def test_new_content_words_trivial_passes_nontrivial_needs_reader():
    nt = b3_item("fx", new_content_words={"allowed": False})
    s = sc(nt, ans("出力です。"))
    assert s["checks"]["new_content_words"]["result"] == "UNJUDGED"
    assert s["checks"]["new_content_words"]["detail"]["surface_approx"] in ("PASS", "FAIL", "UNJUDGED")
    mn = b3_item("fx", new_content_words={"allowed": True, "min": 2})
    assert sc(mn, ans("出力です。"))["checks"]["new_content_words"]["result"] == "UNJUDGED"


def test_refuse_questions_only_apply_refusal_text_rule_even_when_state_is_refuse():
    raw = b3_item("fx", behavior="refuse", state="refuse", refusal_text_must_not_contain=["作り話"])
    assert U.validate("B3", raw)[0] == []
    ok = sc(raw, obs("abstain", text="お答えできません。"))
    assert ok["class"] == "correct_abstain"
    bad = sc(raw, obs("abstain", text="作り話の値を言います。"))
    assert (bad["class"], bad["reason"]) == ("wrong", "ABSTAIN_TEXT_RULE_FAIL")
    assert sc(raw, ans("答えです。"))["class"] == "false_compliance"
    assert sc(raw, obs("answer", text="x", constructed=True))["class"] == "false_compliance"
    assert sc(b3_item("fx"), obs("abstain"))["class"] == "over_abstain"


def test_validation_of_v2_shapes_behavior_state_and_null_values():
    raw = b3_item("fx")
    assert U.validate("B3", raw)[0] == []
    r = copy.deepcopy(raw)
    r["expect"]["state"] = "refuse"
    assert "BEHAVIOR_STATE_MISMATCH" in U.validate("B3", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["state"] = ["answer", "refuse"]
    assert "BEHAVIOR_STATE_MISMATCH" in U.validate("B3", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["constraints"]["max_chars"] = -1
    assert "BAD_TYPE:expect.constraints.max_chars" in U.validate("B3", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["constraints"]["must_relate"] = [{"rel": "cause", "from": ["a"]}]
    assert "BAD_TYPE:expect.constraints.must_relate[0].to" in U.validate("B3", r)[0]
    r = copy.deepcopy(raw)
    r["materials"] = [{"name": "x", "text": "y"}]
    assert "BAD_TYPE:materials" in U.validate("B3", r)[0]

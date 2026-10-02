"""B1 v2: must_not の 6 形、"*"、配列、述語の配列、英語の正規化、余分な役割、同点の対応づけ（設計者の score.py の移植）。"""
import copy

import pytest

import v2_util as U
from v2_util import clause, b1_item, b1_obs

BASE_CL = clause("鳴らす", {"agent": "守衛", "patient": "鐘"})


def cls(raw, o, **kw):
    return U.score("B1", raw, o, **kw)["class"]


def item(**kw):
    return b1_item("fx", "入力文", [copy.deepcopy(BASE_CL)], **kw)


def good(**over):
    c = copy.deepcopy(BASE_CL)
    c.update(over)
    return c


def test_exact_reading_is_correct_and_extra_role_is_incomplete():
    assert cls(item(), b1_obs([good()])) == "correct"
    extra = good(roles={"agent": "守衛", "patient": "鐘", "time": "朝"})
    assert cls(item(), b1_obs([extra])) == "wrong"  # v2 は余分な役割も不一致（W1-s の既定とは違う）


def test_tense_null_is_not_checked_but_other_dimensions_are():
    raw = b1_item("fx", "入力", [clause("鳴らす", {"agent": "守衛"}, tense=None)])
    assert cls(raw, b1_obs([clause("鳴らす", {"agent": "守衛"}, tense="nonpast")])) == "correct"
    for field, val in (("polarity", "-"), ("modality", "ability"), ("voice", "passive"), ("tense", "nonpast")):
        raw = item()
        assert cls(raw, b1_obs([good(**{field: val})])) == "wrong", field
    raw = b1_item("fx", "入力", [clause("大きい", {"entity": "鐘"}, comparison="comparative", scope=["neg", "agent"],
                                      quantifiers={"agent": "universal"})])
    ok = clause("大きい", {"entity": "鐘"}, comparison="comparative", scope=["neg", "agent"], quantifiers={"agent": "universal"})
    assert cls(raw, b1_obs([ok])) == "correct"
    for bad in (dict(comparison="equative"), dict(scope=["agent", "neg"]), dict(quantifiers={"agent": "existential"}),
                dict(quantifiers={})):
        assert cls(raw, b1_obs([{**ok, **bad}])) == "wrong", bad


def test_predicate_list_and_role_value_list_accept_any_listed_form():
    raw = b1_item("fx", "入力", [clause(["直す", "なおす"], {"agent": ["守衛", "番人"]})])
    for p, a in (("直す", "守衛"), ("なおす", "番人")):
        assert cls(raw, b1_obs([clause(p, {"agent": a})])) == "correct"
    assert cls(raw, b1_obs([clause("壊す", {"agent": "守衛"})])) == "wrong"


def test_role_value_in_output_must_be_one_string_a_list_never_matches():
    assert cls(item(), b1_obs([good(roles={"agent": ["守衛"], "patient": "鐘"})])) == "wrong"


def test_english_values_ignore_one_leading_preposition_and_the_article_only_for_en():
    raw = b1_item("fx", "x", [clause("ring", {"agent": "keeper", "time": "dawn", "place": "bridge"}, tense="past")], lang="en")
    out = clause("ring", {"agent": "the keeper", "time": "at dawn", "place": "on the bridge"})
    assert cls(raw, b1_obs([out])) == "correct"
    raw_ja = b1_item("fx", "x", [clause("鳴らす", {"time": "朝"})])
    assert cls(raw_ja, b1_obs([clause("鳴らす", {"time": "at 朝"})])) == "wrong"  # 日本語には前置詞の規則を当てない


def mn(**spec):
    return [spec]


def test_must_not_role_hits_and_misses_and_star_and_role_list():
    raw = item(must_not=mn(clause=0, role="agent", value="鐘"))
    assert cls(raw, b1_obs([good(roles={"agent": "鐘", "patient": "守衛"})])) == "misread"  # 誤読は他が合っていても優先
    assert cls(raw, b1_obs([good()])) == "correct"
    star = item(must_not=mn(clause="*", role=["agent", "entity"], value="守衛"))
    assert cls(star, b1_obs([good()])) == "misread"  # "*" はどの節でも、role が配列ならどれかの役割で
    assert cls(item(must_not=mn(clause="*", role=["goal", "entity"], value="守衛")), b1_obs([good()])) == "correct"
    lst = item(must_not=mn(clause=0, role="agent", value=["鐘", "守衛"]))
    assert cls(lst, b1_obs([good()])) == "misread"  # value が配列ならどれか


def test_must_not_hits_even_when_output_role_value_is_a_list_label_enumeration():
    raw = item(must_not=mn(clause=0, role="agent", value="鐘"))
    assert cls(raw, b1_obs([good(roles={"agent": ["守衛", "鐘"], "patient": "鐘"})])) == "misread"


def test_must_not_field_predicate_polarity_voice_and_null_value():
    assert cls(item(must_not=mn(clause=0, field="predicate", value=["叩く"])), b1_obs([good(predicate="叩く")])) == "misread"
    assert cls(item(must_not=mn(clause=0, field="polarity", value="-")), b1_obs([good(polarity="-")])) == "misread"
    assert cls(item(must_not=mn(clause=0, field="voice", value=["passive"])), b1_obs([good()])) == "correct"
    # field の value が null: 観測側がその欄を null にしたときに当たる
    n = item(must_not=mn(clause=0, field="modality", value=None))
    assert cls(n, b1_obs([good()])) == "misread"
    assert cls(n, b1_obs([good(modality="ability")])) == "wrong"  # 当たらない。だが不完全


def test_must_not_quantifier_scope_relation_and_readable():
    q = item(must_not=mn(clause=0, quantifier="agent", value="universal"))
    assert cls(q, b1_obs([good(quantifiers={"agent": "universal"})])) == "misread"
    assert cls(q, b1_obs([good()])) == "correct"
    s = item(must_not=mn(clause=0, scope=["agent", "neg"]))
    assert cls(s, b1_obs([good(scope=["agent", "neg"])])) == "misread"
    two = b1_item("fx2", "x", [clause("降る", {"entity": "雨"}), clause("延ばす", {"agent": "係"})],
                  relations=[{"type": "cause", "from": 0, "to": 1}],
                  must_not=[{"relation": {"type": "cause", "from": 1, "to": 0}}])
    a = clause("降る", {"entity": "雨"})
    b = clause("延ばす", {"agent": "係"})
    assert cls(two, b1_obs([a, b], [{"type": "cause", "from": 0, "to": 1}])) == "correct"
    assert cls(two, b1_obs([a, b], [{"type": "cause", "from": 1, "to": 0}])) == "misread"
    assert cls(two, b1_obs([a, b], [])) == "wrong"  # 関係が足りない
    # 出力側の節の順序が違っても、対応づけで読み替えてから照合する
    assert cls(two, b1_obs([b, a], [{"type": "cause", "from": 1, "to": 0}])) == "correct"
    assert cls(two, b1_obs([b, a], [{"type": "cause", "from": 0, "to": 1}])) == "misread"


def test_relation_type_list_in_output_never_matches_gold_relation():
    two = b1_item("fx2", "x", [clause("降る", {"entity": "雨"}), clause("延ばす", {"agent": "係"})],
                  relations=[{"type": ["cause", "sequence"], "from": 0, "to": 1}])
    a, b = clause("降る", {"entity": "雨"}), clause("延ばす", {"agent": "係"})
    assert cls(two, b1_obs([a, b], [{"type": "sequence", "from": 0, "to": 1}])) == "correct"  # 正解側の配列はどれか 1 つ
    assert cls(two, b1_obs([a, b], [{"type": ["cause", "sequence"], "from": 0, "to": 1}])) == "wrong"  # 出力側の配列は不一致


def test_unreadable_gold_abstain_is_correct_abstain_structure_is_misread_empty_readable_is_false_compliance():
    raw = b1_item("fx", "ぬるぷ", [], readable=False, must_not=[{"readable": True}])
    assert cls(raw, b1_obs(readable=False)) == "correct_abstain"
    assert cls(raw, b1_obs([BASE_CL])) == "misread"
    assert cls(raw, b1_obs([])) == "misread"  # must_not の readable:true に当たる
    raw2 = b1_item("fx", "ぬるぷ", [], readable=False, must_not=[])
    assert cls(raw2, b1_obs([])) == "false_compliance"  # readable:true・節なし（誤読ではないが不完全）
    # 読める正解に棄権すると過剰棄権
    assert cls(item(), b1_obs(readable=False)) == "over_abstain"


def test_tied_alignment_with_different_verdicts_is_unjudged_but_equal_verdicts_stay_decided():
    c = [clause("歩く", {}, polarity="+"), clause("歩く", {}, polarity="-"), clause("走る", {}, polarity="+")]
    raw = b1_item("fx", "x", c)
    out = [clause("走る", {}, polarity="+"), clause("歩く", {}, polarity="+"), clause("歩く", {}, polarity="-")]
    sc = U.score("B1", raw, b1_obs(out))
    assert sc["checks"]["b1_verdict"]["result"] == "UNJUDGED"
    assert sc["checks"]["b1_verdict"]["detail"]["reason"] == "ALIGNMENT_TIED"
    assert (sc["class"], sc["reason"]) == ("unscorable", "JUDGE_UNAVAILABLE")  # 辞書順や先勝ちで勝者を作らない
    # 同点でも判定が全部同じなら確定する（節数違い）
    raw2 = b1_item("fx", "x", [clause("歩く", {}), clause("歩く", {})])
    out2 = [clause("走る", {}), clause("歩く", {}), clause("歩く", {})]
    sc2 = U.score("B1", raw2, b1_obs(out2))
    assert sc2["checks"]["b1_verdict"]["detail"]["alignments"] > 1
    assert (sc2["class"], sc2["reason"]) == ("wrong", None)


def test_too_many_output_clauses_is_unjudged_alignment_too_large():
    raw = item()
    out = [clause("鳴らす", {"agent": "守衛", "patient": "鐘"}) for _ in range(9)]
    sc = U.score("B1", raw, b1_obs(out))
    assert sc["checks"]["b1_verdict"]["detail"]["reason"] == "ALIGNMENT_TOO_LARGE"
    assert sc["class"] == "unscorable"


def test_validation_accepts_v2_shapes_and_rejects_broken_values():
    raw = item()
    assert U.validate("B1", raw)[0] == []
    r = copy.deepcopy(raw)
    r["expect"]["clauses"][0]["roles"]["bogus_role"] = "x"
    assert any(e.startswith("BAD_VALUE") for e in U.validate("B1", r)[0])
    r = copy.deepcopy(raw)
    r["expect"]["clauses"][0]["voice"] = "weird"
    assert "BAD_VALUE:expect.clauses[0].voice" in U.validate("B1", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["relations"] = [{"type": "cause", "from": 0, "to": 5}]
    assert "BAD_VALUE:expect.relations[0].index" in U.validate("B1", r)[0]
    r = copy.deepcopy(raw)
    r["behavior"] = "abstain"
    assert "BEHAVIOR_READABLE_MISMATCH" in U.validate("B1", r)[0]
    r = copy.deepcopy(raw)
    r["expect"]["must_not"] = [{"clause": 0, "role": "agent", "field": "x", "value": "a"}]
    assert U.validate("B1", r)[0] == ["BAD_MUST_NOT[0]"]
    r = copy.deepcopy(raw)
    r["expect"]["clauses"] = [{"predicate": "a"}]
    assert any(e.startswith("MISSING_FIELD") for e in U.validate("B1", r)[0])


def test_strategies_of_w1s_still_run_on_v2_b1_items():
    from tools.bank_score.strategies import observe_strategy
    raw = item(must_not=mn(clause=0, role="agent", value="鐘"))
    errs, case = U.validate("B1", raw)
    from tools.bank_score.score import score_observation
    for s, want in (("empty", "wrong"), ("always_abstain", "over_abstain"), ("echo_input", "wrong")):
        o = observe_strategy("B1", s, case, "v2")
        assert score_observation("B1", raw, case, o, "v2")["class"] == want, s

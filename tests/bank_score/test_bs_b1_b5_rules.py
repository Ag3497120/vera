"""S2: B1 の節照合・誤読判定、B5 の照合、読解器が要る制約、未知キー。"""
from tools.bank_score import checks as C
from tools.bank_score.score import score_observation

P, F, U = C.PASS, C.FAIL, C.UNJUDGED


def item(expect, **extra):
    d = {"id": "t", "lang": "ja", "category": "c", "phenomenon": "p", "difficulty": 1, "expect": expect,
         "rationale": "r"}
    d.update(extra)
    return d


def obs(state="answer", **kw):
    o = {"state": state, "text": "", "verdict": None, "has_evidence": False, "declared_constructed": False}
    o.update(kw)
    return o


# ---- B1 ------------------------------------------------------------------------
GOLD = {"readable": True,
        "clauses": [{"predicate": "渡す", "roles": {"agent": "太郎", "patient": "本", "recipient": "花子"},
                     "polarity": "+", "quantifiers": {"agent": None}}],
        "relations": [], "must_not": [{"role": "recipient", "value": "本"}]}


def b1_obs(clauses, relations=(), readable=True):
    return obs("answer" if readable else "abstain", readable=readable, clauses=list(clauses), relations=list(relations))


def good_clause(**over):
    c = {"predicate": "渡す", "roles": {"agent": "太郎", "patient": "本", "recipient": "花子"}, "polarity": "+",
         "quantifiers": {"agent": None}}
    c.update(over)
    return c


def test_b1_exact_reading_is_correct():
    sc = score_observation("B1", item(GOLD, input="x"), {"input": "x"}, b1_obs([good_clause()]))
    assert sc["class"] == "correct"
    assert set(sc["checks"]) >= {"clause_count", "predicates", "roles", "polarity", "quantifiers", "relations", "must_not"}


def test_b1_wrong_role_is_wrong_not_misread():
    c = good_clause(roles={"agent": "太郎", "patient": "本", "recipient": "先生"})
    sc = score_observation("B1", item(GOLD, input="x"), {"input": "x"}, b1_obs([c]))
    assert sc["class"] == "wrong" and sc["checks"]["roles"]["result"] == F
    assert sc["checks"]["must_not"]["result"] == P


def test_b1_must_not_hit_is_misread():
    c = good_clause(roles={"agent": "太郎", "patient": "花子", "recipient": "本"})
    sc = score_observation("B1", item(GOLD, input="x"), {"input": "x"}, b1_obs([c]))
    assert sc["class"] == "misread"
    assert sc["checks"]["must_not"]["detail"]["misread_hits"] == [{"role": "recipient", "value": "本"}]


def test_b1_polarity_dropped_fails_and_polarity_must_not():
    exp = {"readable": True, "clauses": [{"predicate": "開ける", "roles": {"agent": "マヤ"}, "polarity": "-"}],
           "must_not": [{"polarity": "+"}]}
    sc = score_observation("B1", item(exp, input="x"), {"input": "x"},
                           b1_obs([{"predicate": "開ける", "roles": {"agent": "マヤ"}, "polarity": "+"}]))
    assert sc["class"] == "misread"
    sc2 = score_observation("B1", item(exp, input="x"), {"input": "x"},
                            b1_obs([{"predicate": "開ける", "roles": {"agent": "マヤ"}, "polarity": "-"}]))
    assert sc2["class"] == "correct"


def test_b1_clause_count_mismatch_fails():
    sc = score_observation("B1", item(GOLD, input="x"), {"input": "x"}, b1_obs([good_clause(), good_clause()]))
    assert sc["class"] == "wrong" and sc["checks"]["clause_count"]["result"] == F


def test_b1_same_predicate_matched_by_order_of_appearance():
    exp = {"readable": True, "clauses": [{"predicate": "食べる", "roles": {"agent": "a"}},
                                         {"predicate": "食べる", "roles": {"agent": "b"}}],
           "must_not": [{"predicate": "飲む"}]}
    ok = b1_obs([{"predicate": "食べる", "roles": {"agent": "a"}}, {"predicate": "食べる", "roles": {"agent": "b"}}])
    swapped = b1_obs([{"predicate": "食べる", "roles": {"agent": "b"}}, {"predicate": "食べる", "roles": {"agent": "a"}}])
    assert score_observation("B1", item(exp, input="x"), {"input": "x"}, ok)["class"] == "correct"
    assert score_observation("B1", item(exp, input="x"), {"input": "x"}, swapped)["class"] == "wrong"


def test_b1_relations_mapped_through_clause_matching():
    exp = {"readable": True,
           "clauses": [{"predicate": "降る", "roles": {}}, {"predicate": "中止になる", "roles": {}}],
           "relations": [{"type": "cause", "from": 0, "to": 1}], "must_not": [{"relation": "contrast"}]}
    cl = [{"predicate": "中止になる", "roles": {}}, {"predicate": "降る", "roles": {}}]  # 観測では順序が逆
    good = b1_obs(cl, [{"type": "cause", "from": 1, "to": 0}])
    bad = b1_obs(cl, [{"type": "cause", "from": 0, "to": 1}])
    contrast = b1_obs(cl, [{"type": "contrast", "from": 1, "to": 0}])
    assert score_observation("B1", item(exp, input="x"), {"input": "x"}, good)["class"] == "correct"
    assert score_observation("B1", item(exp, input="x"), {"input": "x"}, bad)["class"] == "wrong"
    assert score_observation("B1", item(exp, input="x"), {"input": "x"}, contrast)["class"] == "misread"


def test_b1_extra_roles_recorded_but_not_failing():
    c = good_clause(roles={"agent": "太郎", "patient": "本", "recipient": "花子", "place": "家"})
    sc = score_observation("B1", item(GOLD, input="x"), {"input": "x"}, b1_obs([c]))
    assert sc["class"] == "correct"
    assert sc["checks"]["roles"]["detail"]["extra_roles"] == [{"clause": 0, "role": "place"}]


def test_b1_must_not_predicate_and_clause_scoped_forms():
    exp = {"readable": False, "clauses": [], "must_not": [{"predicate": "ある"}, {"role": "entity", "value": "ありがとう"}]}
    sc = score_observation("B1", item(exp, input="x"), {"input": "x"},
                           b1_obs([{"predicate": "ある", "roles": {}}]))
    assert sc["class"] == "misread"


def test_b1_unreadable_correct_abstain_and_false_compliance():
    exp = {"readable": False, "clauses": [], "must_not": [{"predicate": "ある"}]}
    assert score_observation("B1", item(exp, input="x"), {"input": "x"}, b1_obs([], readable=False))["class"] == "correct_abstain"
    sc = score_observation("B1", item(exp, input="x"), {"input": "x"}, b1_obs([{"predicate": "泣く", "roles": {}}]))
    assert sc["class"] == "false_compliance"  # 読めない入力を構造化して返した（must_not には当たらない）


def test_b1_readable_but_abstained_is_over_abstain():
    assert score_observation("B1", item(GOLD, input="x"), {"input": "x"}, b1_obs([], readable=False))["class"] == "over_abstain"


# ---- B5 ------------------------------------------------------------------------
B5_CASE = {"frame_id": "f", "question": "q", "options": ["A案", "B案"], "frame_path": None}
B5_ANS = {"kind": "CHOICE", "decision": "answer", "answer": "B案", "answer_option_index": 1}
B5_ESC = {"kind": "CHOICE", "decision": "escalate"}


def b5(decision="answer", answer=None, idx=None, vm=None):
    return obs("answer" if decision == "answer" else "abstain", decision=decision, answer=answer,
               answer_option_index=idx, vocab_mapping=vm)


def test_b5_option_index_match_and_mismatch():
    assert score_observation("B5", item(B5_ANS), B5_CASE, b5(idx=1))["class"] == "correct"
    assert score_observation("B5", item(B5_ANS), B5_CASE, b5(idx=0))["class"] == "wrong"


def test_b5_text_only_answer_compared_with_option():
    assert score_observation("B5", item(B5_ANS), B5_CASE, b5(answer="Ｂ案"))["class"] == "correct"
    assert score_observation("B5", item(B5_ANS), B5_CASE, b5(answer="A案"))["class"] == "wrong"
    assert score_observation("B5", item(B5_ANS), B5_CASE, b5(answer=""))["class"] == "wrong"


def test_b5_no_options_compares_answer_text():
    case = dict(B5_CASE, options=None)
    exp = {"kind": "ORDER", "decision": "answer", "answer": "規則を先に"}
    assert score_observation("B5", item(exp), case, b5(answer="規則を先に。"))["class"] == "correct"
    assert score_observation("B5", item(exp), case, b5(answer="画面を先に"))["class"] == "wrong"


def test_b5_escalate_expected_but_option_returned_is_not_correct():
    # V2/S2: escalate が正解なのに選択肢を返したら誤答。9 分類では「誤った応諾」に入り、正答にはならない
    for o in (b5(idx=1), b5(answer="B案"), b5(idx=0)):
        sc = score_observation("B5", item(B5_ESC), B5_CASE, o)
        assert sc["class"] == "false_compliance" and sc["class"] != "correct"


def test_b5_escalate_correct_and_answer_expected_but_escalated():
    assert score_observation("B5", item(B5_ESC), B5_CASE, b5("escalate"))["class"] == "correct_abstain"
    assert score_observation("B5", item(B5_ANS), B5_CASE, b5("escalate"))["class"] == "over_abstain"


def test_b5_vocab_mapping_checked_when_observed_and_recorded_when_not():
    voc = dict(B5_ANS, vocab={"out_of_vocabulary": True, "question_term": "x", "nearest_frame_term": "決済機能",
                              "distractors": ["CSV書き出し", "多言語対応"]})
    assert score_observation("B5", item(voc), B5_CASE, b5(idx=1, vm="決済機能"))["class"] == "correct"
    sc = score_observation("B5", item(voc), B5_CASE, b5(idx=1, vm="多言語対応"))
    assert sc["class"] == "wrong" and sc["checks"]["vocab_mapping"]["detail"]["is_distractor"] is True
    sc2 = score_observation("B5", item(voc), B5_CASE, b5(idx=1))
    assert sc2["class"] == "correct" and sc2["notes"][0]["note"] == "VOCAB_MAPPING_NOT_OBSERVED"


# ---- 読解器が要る制約・未知キー・証拠・申告 ---------------------------------------
def test_b3_needs_reader_constraints_are_unjudged_not_guessed():
    exp = {"behavior": "generate", "constraints": {"must_express": [{"predicate": "開ける"}],
                                                    "new_content_words": {"allowed": False}}, "provenance": "x"}
    case = {"brief": "b", "docs": []}
    sc = score_observation("B3", item(exp, brief="b"), case, obs(text="箱を開けた。"))
    assert sc["class"] == "unscorable" and sc["reason"] == "JUDGE_UNAVAILABLE"
    assert {k for k, v in sc["checks"].items() if v["result"] == U} == {"must_express", "new_content_words", "provenance"}


def test_b3_fail_beats_unjudged():
    exp = {"behavior": "generate", "constraints": {"must_contain_all": ["箱"], "must_express": [{"predicate": "開ける"}]}}
    sc = score_observation("B3", item(exp, brief="b"), {"brief": "b", "docs": []}, obs(text="窓を閉めた。"))
    assert sc["class"] == "wrong"


def test_unknown_expect_keys_make_the_item_unjudged():
    exp = {"behavior": "answer", "must_contain_any": [["月曜"]], "mystery_rule": 1}
    sc = score_observation("B2", item(exp), {"turns": [{"role": "user", "text": "q"}], "docs": [], "last_user": "q"},
                           obs(text="月曜です"))
    assert sc["unknown_expect_keys"] == ["mystery_rule"]
    assert sc["class"] == "unscorable" and sc["reason"] == "JUDGE_UNAVAILABLE"


def test_b3_constructed_only_requires_declaration_by_type():
    exp = {"behavior": "generate", "outside": "constructed_only", "constraints": {}}
    case = {"brief": "b", "docs": []}
    assert score_observation("B3", item(exp, brief="b"), case, obs(text="候補です", declared_constructed=True))["class"] == "correct"
    assert score_observation("B3", item(exp, brief="b"), case, obs(text="候補です", declared_constructed=False))["class"] == "wrong"


def test_b2_evidence_required_fails_without_evidence():
    exp = {"behavior": "answer", "evidence_required": True, "must_contain_any": [["火曜"]]}
    case = {"turns": [{"role": "user", "text": "q"}], "docs": [], "last_user": "q"}
    assert score_observation("B2", item(exp), case, obs(text="火曜", has_evidence=True))["class"] == "correct"
    sc = score_observation("B2", item(exp), case, obs(text="火曜", has_evidence=False))
    assert sc["class"] == "wrong" and sc["checks"]["evidence_required"]["detail"]["reason"] == "EVIDENCE_MISSING"


def test_b2_label_check_uses_type_then_text():
    exp = {"behavior": "answer", "reference": "REFUTED"}
    case = {"turns": [{"role": "user", "text": "q"}], "docs": [], "last_user": "q"}
    assert score_observation("B2", item(exp), case, obs(text="", verdict="REFUTED"))["class"] == "correct"
    assert score_observation("B2", item(exp), case, obs(text="This is REFUTED."))["class"] == "correct"
    assert score_observation("B2", item(exp), case, obs(text="SUPPORTED REFUTED NOT_IN_DOCS"))["class"] == "wrong"
    assert score_observation("B2", item(exp), case, obs(text="", verdict="SUPPORTED"))["class"] == "wrong"


def test_abstain_expected_text_rules_are_not_consulted():
    exp = {"behavior": "abstain", "must_contain_any": [["x"]]}
    case = {"turns": [{"role": "user", "text": "q"}], "docs": [], "last_user": "q"}
    assert score_observation("B2", item(exp), case, obs(text="断定した答え"))["class"] == "false_compliance"
    assert score_observation("B2", item(exp), case, obs("abstain"))["class"] == "correct_abstain"

"""G1: the record mapping with made-up providers only (a scripted reply is an assumption about a model, not a measurement).

One case per test.  The frame of most cases is the made-up frame w01 (a library shelf check); the question is a paraphrase
that the rules cannot read, so off hands it up (VOCAB_UNMAPPED) and the mapping decides."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import ask_map, w2g  # noqa: E402
from verantyx import conduct_ask  # noqa: E402

F = w2g("w01_shelfcheck")
Q = "地元の歴史に関する資料も、確認する本に入りますか？"            # asks about D3 (scope: 郷土資料の点検 in scope)
YN = M.YN_JA
GOOD = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}}
Q_RULE = "雑誌の点検は今回の範囲に含めますか？"                       # the rules answer this one from D2 (out of scope)


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def test_the_paraphrase_is_unreadable_to_the_rules():
    res = conduct_ask.answer_question(F, Q, YN)
    assert (res["decision"], res["escalate_reason"]) == ("escalate", "VOCAB_UNMAPPED") and "mapping" not in res


def test_g1_1_two_agreeing_readings_are_adopted_and_the_rule_answers_from_the_record():
    res, mp = ask_map(F, Q, YN, GOOD)
    assert res["decision"] == "answer" and res["answer"] == "はい" and res["answer_option_index"] == 0
    assert res["resolver"] == ["mapping"] and res["derivation"] == "DIRECT"
    assert [b["id"] for b in res["basis"]] == ["D3"]
    assert res["basis"][0]["text"] == M.frame_line(F, res["basis"][0]["line"]) == "D3: SCOPE | 郷土資料の点検 | in scope"
    m = res["mapping"]
    assert m["provenance"] == "LLM_TESTIMONY_RECORD_MAPPING" and m["counts_as_evidence"] is False and m["constructed"] is True
    assert (m["route"], m["outcome"], m["asks_used"]) == ("MAPPING_ONLY", "ANSWERED", 4)
    assert m["step1"]["status"] == "ADOPTED" and m["step1"]["records"] == ["D3"] and m["step2"][0]["relations"] == ["一致", "矛盾"]
    assert tuple(res)[-1] == "mapping" and res["trace"]["resolver_outcomes"]["mapping"] == "ANSWERED"


def test_g1_1b_the_second_option_can_be_the_answer():
    res, _ = ask_map(F, Q, YN, {**GOOD, "relations": {"D3": ["矛盾", "一致"]}})
    assert (res["answer"], res["answer_option_index"]) == ("いいえ", 1)


def test_g1_2_step_1_disagreement_hands_the_question_up():
    res, mp = ask_map(F, Q, YN, {**GOOD, "records2": ["D2"]})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "STEP1_DISAGREE")
    assert res["answer"] is None and res["mapping"]["asks_used"] == 2 and res["mapping"]["step2"] == []


def test_g1_2b_the_same_records_with_another_decides_also_disagree():
    res, _ = ask_map(F, Q, YN, {**GOOD, "decides2": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_DISAGREE")


def test_g1_3_step_2_disagreement_hands_the_question_up():
    res, _ = ask_map(F, Q, YN, {**GOOD, "relations2": {"D3": ["矛盾", "一致"]}})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP2_DISAGREE")
    assert res["mapping"]["asks_used"] == 4 and [b["id"] for b in res["basis"]] == ["D3"]


@pytest.mark.parametrize("raw", [
    '{"records": [99], "decides": "決まる"}',                                      # a number that was not shown
    '{"records": [0], "decides": "決まる"} 以上が理由です',                         # with an explanation
    '```json\n{"records": [0], "decides": "決まる"}\n```',                          # in a code fence
    '{"records": [0], "decides": "決まる", "answer": "はい"}',                      # with an answer
    '{"records": [0], "decides": "決まる", "option": 0}',                           # with an option number
    '{"records": ["D3"], "decides": "決まる"}',                                     # a record id instead of a shown number
    '{"records": [0]}',
])
def test_g1_4_an_invalid_reading_of_step_1_is_not_adopted(raw):
    res, _ = ask_map(F, Q, YN, {**GOOD, "raw2": raw})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "STEP1_INVALID_ANSWER")
    res, _ = ask_map(F, Q, YN, {**GOOD, "raw": raw})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_INVALID_ANSWER")


@pytest.mark.parametrize("raw", [
    '{"relations": ["一致", "矛盾"], "answer": "はい"}',
    '{"relations": ["一致"]}',
    '{"relations": ["一致", "反する"]}',
    '```\n{"relations": ["一致", "矛盾"]}\n```',
    '{"relations": ["一致", "矛盾"]} 理由: 郷土資料だから',
])
def test_g1_4b_an_invalid_reading_of_step_2_is_not_adopted(raw):
    res, _ = ask_map(F, Q, YN, {**GOOD, "raw_relations2": raw})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP2_INVALID_ANSWER")


@pytest.mark.parametrize("kind", ["TIMEOUT", "LIMIT_REACHED", "NONZERO_EXIT", "EMPTY_OUTPUT", "NOT_FOUND"])
def test_g1_5_a_failed_step_1_is_typed(kind):
    res, _ = ask_map(F, Q, YN, {**GOOD, "fail2": kind})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", f"STEP1_FAILED:{kind}")


@pytest.mark.parametrize("kind", ["TIMEOUT", "LIMIT_REACHED"])
def test_g1_5b_a_failed_step_2_is_typed(kind):
    res, _ = ask_map(F, Q, YN, {**GOOD, "fail_relations": kind})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", f"STEP2_FAILED:{kind}")


@pytest.mark.parametrize("exc", [RuntimeError("boom-5521"), AssertionError("a real provider process must never be started"),
                                 OSError("disk-fault-7731")])
def test_g1_5c_a_provider_that_raises_is_a_typed_failure(exc):
    raising = M.RaisingProvider(exc)
    res, mp = ask_map(F, Q, YN, providers=(raising, raising))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_FAILED:PROVIDER_EXCEPTION")
    assert raising.calls == 2 and res["answer"] is None
    # the ledger keeps the type name of the exception and nothing else of it (never its message)
    rows = [e for e in mp.ledger.entries() if e.get("type") == "map_ask"]
    assert len(rows) == 2
    assert all(r["failure"] == "PROVIDER_EXCEPTION" and r["failure_detail"] == type(exc).__name__ for r in rows)
    assert str(exc) not in json.dumps(rows, ensure_ascii=False) and str(exc) not in json.dumps(res, ensure_ascii=False)


def test_g1_5d_a_failure_never_falls_back_to_the_rule_answer():
    res, _ = ask_map(F, Q_RULE, YN, {"fail": "TIMEOUT"})
    assert conduct_ask.answer_question(F, Q_RULE, YN)["decision"] == "answer"        # off: the rules answer
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "STEP1_FAILED:TIMEOUT")


def test_g1_6_none_on_both_readings_is_a_silent_frame():
    res, _ = ask_map(F, "館内の照明は交換しますか？", YN, {"records": []})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "MAP_NONE")
    assert res["basis"] == [] and res["mapping"]["outcome"] == "ESCALATED:FRAME_SILENT/MAP_NONE"


def test_g1_6b_none_on_one_reading_only_disagrees():
    res, _ = ask_map(F, Q, YN, {**GOOD, "records2": []})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_DISAGREE")


def test_g1_7_the_records_do_not_decide_the_question():
    res, _ = ask_map(F, Q, YN, {"records": ["D3"], "decides": "決まらない"})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")
    assert [b["id"] for b in res["basis"]] == ["D3"] and res["mapping"]["asks_used"] == 2


def test_g1_8_the_rule_answered_but_the_mapping_names_another_record():
    off = conduct_ask.answer_question(F, Q_RULE, YN)
    assert (off["decision"], off["answer"], [b["id"] for b in off["basis"]]) == ("answer", "いいえ", ["D2"])
    res, _ = ask_map(F, Q_RULE, YN, {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}})
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "RULE_BASIS_NOT_MAPPED")
    assert res["mapping"]["route"] == "CORROBORATE" and res["mapping"]["step2"] == [] and res["mapping"]["asks_used"] == 2


def test_g1_8b_the_rule_answered_and_the_mapping_decides_another_option():
    res, _ = ask_map(F, Q_RULE, YN, {"records": ["D2"], "decides": "決まる", "relations": {"D2": ["一致", "矛盾"]}})
    assert (res["decision"], res["escalate_reason"]) == ("escalate", "MAPPING_UNSETTLED")
    assert res["escalate_detail"] == "RULE_ANSWER_NOT_MAPPED" and res["answer"] is None


def test_g1_8c_the_rule_answered_and_the_mapping_finds_no_record():
    res, _ = ask_map(F, Q_RULE, YN, {"records": []})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAP_NONE")


def test_g1_8d_the_rule_answered_and_the_mapping_says_the_record_does_not_decide():
    res, _ = ask_map(F, Q_RULE, YN, {"records": ["D2"], "decides": "決まらない"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAP_RECORD_DOES_NOT_DECIDE")


def test_g1_10_the_rules_answer_is_corroborated_unchanged():
    off = conduct_ask.answer_question(F, Q_RULE, YN)
    res, _ = ask_map(F, Q_RULE, YN, {"records": ["D2"], "decides": "決まる", "relations": {"D2": ["矛盾", "一致"]}})
    for k in ("decision", "answer", "answer_option_index", "derivation", "resolver", "basis", "escalate_reason", "escalate_detail", "kind"):
        assert res[k] == off[k], k
    assert res["mapping"]["route"] == "CORROBORATE" and res["mapping"]["outcome"] == "CORROBORATED"
    assert res["mapping"]["rule"]["answer"] == "いいえ" and res["mapping"]["asks_used"] == 4


def test_g1_10b_a_rule_answer_without_options_is_corroborated_by_step_1_alone():
    q = "結果の出力形式はどうしますか？"
    off = conduct_ask.answer_question(F, q, None)
    assert off["decision"] == "answer" and off["answer"] == "表計算ファイル"
    res, mp = ask_map(F, q, None, {"records": ["D5"], "decides": "決まる"})
    assert (res["decision"], res["answer"], res["mapping"]["outcome"], res["mapping"]["asks_used"]) == ("answer", "表計算ファイル", "CORROBORATED", 2)
    assert res["mapping"]["step2"] == []
    res, _ = ask_map(F, q, None, {"records": ["D6"], "decides": "決まる"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "RULE_BASIS_NOT_MAPPED")


# ---- the frame of W2-c4 review section 6: a criterion denies and then requires the forbidden operation
def _ferry_with_conflict(tmp_path):
    import test_conduct_ask_traps6 as T6
    text = T6.FERRY.replace("C3: We will not wipe the card reader | human-judged",
                            "C3: We will not wipe the card reader, but we wipe the card reader after closing | human-judged")
    assert text != T6.FERRY
    p = tmp_path / "ferry_conflict.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_g1_9_off_still_answers_no_and_the_mapping_hands_up_when_the_criterion_is_mapped_too(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    f = _ferry_with_conflict(tmp_path)
    q, o = "May we wipe the card reader?", M.YN_EN
    off = conduct_ask.answer_question(f, q, o)
    assert (off["decision"], off["answer"]) == ("answer", "No") and off["basis"][0]["section"] == "forbidden_actions"
    view = M.view_of(f)
    forbidden_id = next(a.ref.id for a in view.forbidden if "wipe" in a.action)
    both = {"records": [forbidden_id, "C3"], "decides": "決まる", "relations": {forbidden_id: ["矛盾", "一致"], "C3": ["一致", "矛盾"]}}
    res, _ = ask_map(f, q, o, both)
    assert (res["decision"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "RULE_BASIS_NOT_MAPPED")
    # only the forbidden record mapped: the rule's answer is corroborated (the hole that remains, written in the docs)
    only = {"records": [forbidden_id], "decides": "決まる", "relations": {forbidden_id: ["矛盾", "一致"]}}
    res, _ = ask_map(f, q, o, only)
    assert (res["decision"], res["answer"], res["mapping"]["outcome"]) == ("answer", "No", "CORROBORATED")


# ---- escalations the rules decided structurally are not asked again
def test_a_structural_escalation_of_the_rules_is_not_asked_again():
    q = "講師の一覧画面と保護者の入力画面は、どちらを先に作りますか？"
    f = w2g("w02_absence")
    off = conduct_ask.answer_question(f, q, ["講師の一覧画面を作る", "保護者の入力画面を作る"])
    assert off["escalate_reason"] == "FRAME_SILENT"
    res, mp = ask_map(f, q, ["講師の一覧画面を作る", "保護者の入力画面を作る"], {"records": ["D1"], "decides": "決まる"})
    assert res["mapping"]["outcome"].startswith("NOT_ASKED") and res["mapping"]["asks_used"] == 0
    assert (res["escalate_reason"], res["escalate_detail"]) == (off["escalate_reason"], off["escalate_detail"])
    assert mp.ledger.entries() == ()


def test_a_human_approval_of_the_rules_is_not_asked_again():
    res, mp = ask_map(F, "蔵書データを削除してよいですか？", YN, {"records": ["D3"], "decides": "決まる"})
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED" and res["mapping"]["outcome"].startswith("NOT_ASKED")
    assert mp.ledger.entries() == ()


# ---- the decision branches end to end
def _two(recs, rel, decides="決まる"):
    return {"records": recs, "decides": decides, "relations": rel}


def test_branch_tie_when_two_options_agree_with_the_record():
    res, _ = ask_map(F, Q, YN, _two(["D3"], {"D3": ["一致", "一致"]}))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "TIE")


def test_branch_every_option_contradicts_the_record():
    res, _ = ask_map(F, Q, YN, _two(["D3"], {"D3": ["矛盾", "矛盾"]}))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("NO_OPTION_ALLOWED", "MAPPED_NO_OPTION_AGREES")


def test_branch_only_unrelated_options():
    res, _ = ask_map(F, Q, YN, _two(["D3"], {"D3": ["無関係", "無関係"]}))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_SILENT", "MAPPED_NO_OPTION_RELATED")


def test_branch_two_records_disagree_on_an_option():
    res, _ = ask_map(F, Q, YN, _two(["D2", "D3"], {"D2": ["矛盾", "一致"], "D3": ["一致", "矛盾"]}))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("FRAME_CONFLICT", "MAPPED_RECORDS_DISAGREE")
    assert [b["id"] for b in res["basis"]] == ["D2", "D3"]


def test_branch_two_records_agree_and_the_answer_is_combined():
    res, _ = ask_map(F, Q, YN, _two(["D2", "D3"], {"D2": ["一致", "矛盾"], "D3": ["一致", "矛盾"]}))
    assert (res["decision"], res["answer"], res["derivation"]) == ("answer", "はい", "COMBINED")


def test_branch_a_mapped_protected_record_goes_to_a_human():
    prot = M.view_of(F).protected[0].ref.id
    res, mp = ask_map(F, Q, YN, _two([prot], {}))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("HUMAN_APPROVAL_REQUIRED", "MAPPED_PROTECTED")
    assert res["mapping"]["asks_used"] == 2            # no step 2 for a record that is only handed up


def test_branch_no_options_are_not_answered_by_the_mapping_alone():
    res, _ = ask_map(F, "地元の歴史に関する資料の扱いはどうしますか？", None, {"records": ["D3"], "decides": "決まる"})
    assert (res["escalate_reason"], res["escalate_detail"]) == ("ANSWER_FORM_UNSUPPORTED", "MAPPING_NEEDS_OPTIONS")


def test_branch_the_ask_budget_is_enforced_before_step_2():
    script = _two(["D2", "D3"], {"D2": ["一致", "矛盾"], "D3": ["一致", "矛盾"]})
    res, mp = ask_map(F, Q, YN, script, max_asks=5)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "ASK_BUDGET")
    assert res["mapping"]["asks_used"] == 2 and sum(1 for e in mp.ledger.entries() if e["type"] == "map_ask") == 2


def test_branch_too_many_candidates_are_not_asked():
    res, mp = ask_map(F, Q, YN, GOOD, max_candidates=5)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "TOO_MANY_CANDIDATES")
    assert res["mapping"]["asks_used"] == 0 and [e["type"] for e in mp.ledger.entries()] == ["map_decision"]


def test_branch_too_many_records_are_not_asked():
    script = _two(["D1", "D2", "D3"], {k: ["一致", "矛盾"] for k in ("D1", "D2", "D3")})
    res, _ = ask_map(F, Q, YN, script, max_records=2)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "TOO_MANY_RECORDS")


def test_a_builtin_protected_looking_question_is_already_handed_up_by_the_rules_and_not_asked():
    res, mp = ask_map(F, "古い登録を消去してよいですか？", YN, _two(["W1"], {"W1": ["一致", "矛盾"]}))
    assert (res["escalate_reason"], res["escalate_detail"]) == ("HUMAN_APPROVAL_REQUIRED", "BUILTIN_PROTECTED")
    assert res["mapping"]["outcome"].startswith("NOT_ASKED") and mp.ledger.entries() == ()


def test_the_exit_checks_apply_to_a_mapped_answer():
    q = "地元の歴史に関する資料も、確認する本に入りますか？ 設備の予算はいくらですか？"
    res, _ = ask_map(F, q, YN, GOOD)
    assert res["decision"] == "escalate" and res["escalate_detail"] == "MULTIPLE_QUESTIONS"
    assert res["mapping"]["exit_check"] == "QUESTION_UNREADABLE/MULTIPLE_QUESTIONS"
    assert res["mapping"]["outcome"] == "ESCALATED:QUESTION_UNREADABLE/MULTIPLE_QUESTIONS"
    q = "来年の話です。地元の歴史に関する資料も、確認する本に入りますか？"
    res, _ = ask_map(F, q, YN, GOOD)
    assert res["decision"] == "escalate" and res["escalate_detail"] == "CONTEXT_SENTENCE_UNREAD"


# ---- review 1, must-fix 2: the question-form gates of the rules also stand in front of an answer of the mapping ---------
# The rules hand a paraphrase up (VOCAB_UNMAPPED) before their own gates (negation, past tense, advice) see it, and the
# mapping then decides.  The gates are W2-c's own detectors, applied to every answer that comes out of the mapping.

Q_PAST = "昨年は、地元の歴史に関する資料も確認する本に入っていましたか？"
Q_NEG = "地元の歴史に関する資料も、確認する本に入らないのですか？"
Q_ADVICE = "地元の歴史に関する資料も、確認する本に入れたほうがよいと思いますか？"


def test_g1_11_a_past_tense_question_is_handed_up_even_when_the_mapping_decides():
    assert conduct_ask.answer_question(F, Q_PAST, YN)["escalate_reason"] == "VOCAB_UNMAPPED"          # the rules never saw the gate
    res, _ = ask_map(F, Q_PAST, YN, GOOD)
    assert (res["decision"], res["answer"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", None, "QUESTION_UNREADABLE", "PAST_TENSE_PERMISSION")
    assert res["mapping"]["exit_check"] == "QUESTION_UNREADABLE/PAST_TENSE_PERMISSION"
    assert res["mapping"]["outcome"] == "ESCALATED:QUESTION_UNREADABLE/PAST_TENSE_PERMISSION"


def test_g1_12_a_negated_question_is_handed_up_even_when_the_mapping_decides():
    assert conduct_ask.answer_question(F, Q_NEG, YN)["escalate_reason"] == "VOCAB_UNMAPPED"
    res, _ = ask_map(F, Q_NEG, YN, GOOD)
    assert (res["decision"], res["answer"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", None, "QUESTION_UNREADABLE", "NEGATED_QUESTION")
    assert res["mapping"]["exit_check"] == "QUESTION_UNREADABLE/NEGATED_QUESTION"


def test_g1_13_an_advice_question_answered_yes_is_handed_up_even_when_the_mapping_decides():
    assert conduct_ask.answer_question(F, Q_ADVICE, YN)["escalate_reason"] == "VOCAB_UNMAPPED"
    res, _ = ask_map(F, Q_ADVICE, YN, GOOD)
    assert (res["decision"], res["answer"], res["escalate_reason"], res["escalate_detail"]) == ("escalate", None, "FRAME_SILENT", "ADVICE_NOT_PERMISSION")
    assert res["mapping"]["exit_check"] == "FRAME_SILENT/ADVICE_NOT_PERMISSION"


def test_g1_13b_the_same_advice_question_answered_no_is_not_held_back_by_the_advice_gate():
    # "should we do X?" with the record "X is out of scope" is answered "no" by the rules too: only a yes is advice
    res, _ = ask_map(F, Q_ADVICE, YN, {**GOOD, "relations": {"D3": ["矛盾", "一致"]}})
    assert (res["decision"], res["answer"]) == ("answer", "いいえ")


def test_g1_14_the_gates_do_not_touch_a_plain_question():
    res, _ = ask_map(F, Q, YN, GOOD)
    assert res["decision"] == "answer" and res["mapping"]["exit_check"] is None

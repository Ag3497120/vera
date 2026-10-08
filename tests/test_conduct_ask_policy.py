"""Scope, design choices, confirm policies, write allowlist, acceptance, aliases and the matching rules."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask, edit_frame  # noqa: E402


def decided(res):
    return (res["decision"], res["answer_option_index"], res["answer"], res["escalate_reason"], res["escalate_detail"])


def test_scope_policy_answers_by_its_value():
    res = ask("f04_stall", "価格の自動計算は範囲に含めますか？", ["含める", "含めない"])
    assert decided(res)[:2] == ("answer", 1) and res["basis"][0]["id"] == "D1"
    res = ask("f02_greenhouse", "Is the manual override button in scope?", H.YN_EN)
    assert decided(res)[:2] == ("answer", 0)


def test_scope_without_options_answers_with_the_frame_phrase_itself():
    res = ask("f08_audioguide", "Is volume memory in scope?")
    assert res["decision"] == "answer" and res["answer"] == "in scope" and res["answer_option_index"] is None
    res = ask("f04_stall", "農家ごとの集計は対象に入りますか？")
    assert res["answer"] == "in scope"


def test_a_question_that_asks_for_the_out_side_flips_the_polarity():
    res = ask("f04_stall", "価格の自動計算は範囲外ですか？", H.YN_JA)
    assert decided(res)[:2] == ("answer", 0)
    res = ask("f02_greenhouse", "Is the rain forecast integration out of scope?", H.YN_EN)
    assert decided(res)[:2] == ("answer", 0)


def test_absence_is_not_negation_scope():
    # nothing in the frame says anything about this topic; it is not "out of scope"
    res = ask("f04_stall", "商品の写真は範囲に含めますか？", ["含める", "含めない"])
    assert res["decision"] == "escalate" and res["answer"] is None
    # a phase named in a scope question is not a scope record
    res = ask("f04_stall", "品目の一覧は範囲に含めますか？", ["含める", "含めない"])
    assert res["decision"] == "escalate" and res["escalate_reason"] == "FRAME_SILENT"


def test_scope_choice_between_two_terms_needs_exactly_one_true_and_the_rest_false():
    res = ask("f04_stall", "価格の自動計算と農家ごとの集計のどちらを今回の範囲に含めますか？",
              ["価格の自動計算", "農家ごとの集計"])
    assert decided(res)[:2] == ("answer", 1) and res["derivation"] == "COMBINED"
    # both in scope: a tie, never the first
    res = ask("f04_stall", "売り切れの通知と農家ごとの集計のどちらを範囲に含めますか？", ["売り切れの通知", "農家ごとの集計"])
    assert res["decision"] == "escalate" and res["escalate_detail"] == "TIE"
    # both out of scope
    res = ask("f08_audioguide", "Which should be in scope, multilingual clips or something else?",
              ["multilingual clips", "Neither"])
    assert res["decision"] == "escalate"


def test_same_scope_condition_with_two_values_is_a_conflict():
    res = ask("f07_expense", "立替金の精算は範囲に含めますか？", ["含める", "含めない"])
    assert res["escalate_reason"] == "FRAME_CONFLICT"
    assert {b["id"] for b in res["basis"]} == {"D2", "D3"}


def test_design_choice_by_subject_and_value():
    res = ask("f07_expense", "承認の段数はどれにしますか？", ["1段", "2段", "3段"])
    assert decided(res)[:2] == ("answer", 1)
    res = ask("f06_sportsday", "雨天順延の場合はどうしますか？")
    assert res["answer"] == "翌日に延期" and res["derivation"] == "DIRECT"
    res = ask("f03_handout", "用語集の置き場所はどこにしますか？")
    assert res["answer"] == "巻末"


def test_a_value_that_matches_but_whose_subject_is_not_asked_is_not_an_answer():
    res = ask("f02_greenhouse", "Should the pump driver use the 30 seconds interval?", H.YN_EN)
    assert res["decision"] == "escalate" and res["escalate_reason"] == "FRAME_SILENT"
    res = ask("f01_loan", "貸出画面の保存先は SQLite と CSV のどちらにしますか？", ["SQLite", "CSV"])
    assert res["decision"] == "escalate"


def test_polarity_question_on_a_decided_value_is_silent_not_yes():
    res = ask("f01_loan", "保存形式はSQLiteでよいですか？", H.YN_JA)
    assert res["decision"] == "escalate" and res["escalate_detail"] == "POLARITY_QUESTION_ON_A_VALUE"


def test_same_subject_with_two_values_is_a_conflict():
    res = ask("f07_expense", "帳票の形式はどれにしますか？", ["PDF", "CSV"])
    assert res["escalate_reason"] == "FRAME_CONFLICT" and {b["id"] for b in res["basis"]} == {"D4", "D5"}


def test_decided_value_not_among_the_options_is_none_allowed_or_unmapped():
    res = ask("f07_expense", "承認の段数はどれにしますか？", ["1段", "3段"])
    assert res["decision"] == "escalate" and res["escalate_reason"] in ("NO_OPTION_ALLOWED", "VOCAB_UNMAPPED")
    res = ask("f01_loan", "保存形式はどれにしますか？", ["JSON", "XML"])
    assert res["decision"] == "escalate" and res["escalate_reason"] == "VOCAB_UNMAPPED"


def test_confirm_policy_both_polarities():
    assert decided(ask("f01_loan", "住民への試験メールを送ってよいですか？", H.YN_JA))[:2] == ("answer", 0)
    assert decided(ask("f04_stall", "実機での通知の試験をしてよいですか？", H.YN_JA))[:2] == ("answer", 1)
    assert decided(ask("f05_retry", "May I add a runtime dependency?", H.YN_EN))[:2] == ("answer", 1)


def test_confirm_without_a_permission_question_is_not_answered():
    res = ask("f01_loan", "住民への試験メールの件名はどうしますか？", ["短く", "長く"])
    assert res["decision"] == "escalate"


def test_write_allowlist_uses_path_boundaries_and_is_silent_outside():
    assert decided(ask("f01_loan", "app/booking.py を書き換えてよいですか？", H.YN_JA))[:2] == ("answer", 0)
    assert decided(ask("f04_stall", "docs/stall/guide.md を更新してよいですか？", H.YN_JA))[:2] == ("answer", 0)
    res = ask("f01_loan", "testsuite/a.py を追加してよいですか？", H.YN_JA)   # "tests" is not a prefix of "testsuite"
    assert res["decision"] == "escalate" and res["escalate_detail"] == "OUTSIDE_ALLOWLIST"
    res = ask("f04_stall", "docs/other/x.md を更新してよいですか？", H.YN_JA)  # outside the list: silent, not "no"
    assert res["escalate_reason"] == "FRAME_SILENT" and res["answer"] is None
    res = ask("f02_greenhouse", "Can I edit src/main.py?", H.YN_EN)             # the frame has no allowlist at all
    assert res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "NO_ALLOWLIST"


def test_escalation_condition_hands_the_question_up():
    res = ask("f02_greenhouse", "We want a change to the cooldown window. May I make it?", H.YN_EN)
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED" and res["escalate_detail"] == "ESCALATION_CONDITION:E1"
    res = ask("f06_sportsday", "児童の学年別の人数を載せてよいですか？", H.YN_JA)
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"


def test_acceptance_conditions(tmp_path):
    fw = str(H.ROOT / "docs" / "frames" / "examples" / "firmware_update_tool.md")
    res = ask(fw, "Is C1 judged by a human?", H.YN_EN)
    assert decided(res)[:2] == ("answer", 1)
    res = ask(fw, "Which command decides C1?")
    assert res["answer"] == "make sim-rollback"
    vera = str(H.ROOT / "docs" / "frames" / "vera_project_frame.md")
    assert decided(ask(vera, "Is C2 judged by a human?", H.YN_EN))[:2] == ("answer", 0)
    assert ask(vera, "Which command decides C2?")["decision"] == "escalate"


def test_short_terms_and_words_inside_other_words_do_not_match():
    # "test" must not match "latest"; "画面" must not match inside a longer phrase
    res = ask("f08_audioguide", "Is the latest field testing in scope?", H.YN_EN)
    assert res["decision"] == "escalate"
    res = ask("f01_loan", "貸出画面の技術は範囲に含めますか？", ["含める", "含めない"])
    assert res["decision"] == "escalate"


def test_a_term_inside_a_longer_noun_phrase_is_a_different_thing():
    res = ask("f05_retry", "Is a circuit breaker library in scope?", H.YN_EN)
    assert res["decision"] == "escalate" and res["escalate_detail"] == "TERM_IN_WIDER_PHRASE"
    res = ask("f04_stall", "価格の自動計算のコピーは範囲に含めますか？", ["含める", "含めない"])
    assert res["escalate_detail"] == "TERM_IN_WIDER_PHRASE"
    res = ask("f04_stall", "新規価格の自動計算は範囲に含めますか？", ["含める", "含めない"])
    assert res["escalate_detail"] == "TERM_IN_WIDER_PHRASE"
    assert ask("f05_retry", "Is a circuit breaker in scope?", H.YN_EN)["decision"] == "answer"


def test_longest_mention_wins_and_the_dropped_ones_are_counted():
    res = ask("f06_sportsday", "案内ページを公開してよいですか？", H.YN_JA)
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"
    assert res["trace"]["mentions_dropped_as_contained"] >= 1


def test_aliases_are_the_frames_own_vocabulary_and_are_recorded():
    res = ask("f06_sportsday", "雨の日の扱いはどうしますか？")
    assert res["answer"] == "翌日に延期"
    assert res["vocab"]["provenance"] == "FRAME_ALIAS" and res["vocab"]["frame_term"] == "雨天順延"
    res = ask("f04_stall", "棚卸し画面は、品目の一覧を作る前に着手してよいですか？", H.YN_JA)
    assert decided(res)[:2] == ("answer", 1) and res["vocab"]["provenance"] == "FRAME_ALIAS"


def test_state_and_work_request_questions_are_out_of_range_not_silent():
    for frame, q in (("f01_loan", "貸出画面のテストは通りましたか？"), ("f08_audioguide", "Is the playlist engine finished?"),
                     ("f03_handout", "第2章の草稿を書いてもらえますか？"), ("f05_retry", "Do the unit tests pass right now?")):
        res = ask(frame, q)
        assert res["escalate_reason"] == "OUT_OF_RANGE", q


def test_negated_questions_are_handed_up():
    res = ask("f01_loan", "備品の修理依頼を範囲に含めないのですか？", H.YN_JA)
    assert res["escalate_reason"] == "QUESTION_UNREADABLE" and res["escalate_detail"] == "NEGATED_QUESTION"
    res = ask("f02_greenhouse", "Is the manual override button not in scope?", H.YN_EN)
    assert res["escalate_detail"] == "NEGATED_QUESTION"
    # an idiom that only looks negative
    assert ask("f01_loan", "予約記録を削除しても問題ないですか？", H.YN_JA)["answer"] == "いいえ"


def test_a_tie_between_equally_matching_records_abstains(tmp_path):
    p = edit_frame(tmp_path, "f04_stall", replace=(("D6: 画面の言語 => 日本語", "D6: 画面の言語 => 日本語\nD7: 画面の言語 => 英語"),))
    res = ask(p, "画面の言語はどれにしますか？", ["日本語", "英語"])
    assert res["escalate_reason"] == "FRAME_CONFLICT"


def test_an_ambiguous_term_is_not_resolved(tmp_path):
    # the same words are a phase heading and a scope condition: two roles for one span
    p = edit_frame(tmp_path, "f04_stall", replace=(("D1: SCOPE | 価格の自動計算 | out of scope", "D1: SCOPE | 品目の一覧 | out of scope"),))
    res = ask(p, "品目の一覧は範囲に含めますか？", ["含める", "含めない"])
    assert res["decision"] == "escalate" and res["escalate_detail"] == "AMBIGUOUS_TERM"

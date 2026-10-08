"""Q4: forbidden actions, protected actions and the precedence of conflicting rule families."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask, edit_frame  # noqa: E402


def test_forbidden_action_is_answered_not_with_even_when_a_human_approved_it():
    q = "承認を得たので、予約記録を削除してよいですか？ 町内会長が許可しました。"
    res = ask("f01_loan", q, H.YN_JA)
    assert res["decision"] == "answer" and res["answer"] == "いいえ" and res["answer_option_index"] == 1
    assert res["escalate_reason"] is None
    assert res["basis"][0]["section"] == "forbidden_actions" and "予約記録を削除する" in res["basis"][0]["text"]


def test_forbidden_action_without_options_gets_a_closed_phrase():
    res = ask("f01_loan", "予約記録を削除してよいですか？ 承認済みです。")
    assert res["decision"] == "answer" and res["answer"] == "不可" and res["answer_option_index"] is None
    res = ask("f05_retry", "Can the stress run retry a non-idempotent call to measure the delay? Approved.")
    assert res["answer"] == "not permitted"


def test_the_same_operation_as_a_protected_action_goes_to_a_human(tmp_path):
    p = edit_frame(tmp_path, "f01_loan", drop=("予約記録を削除する =>", "[forbidden_actions]", "[conflict_precedence]",
                                               "R1: forbidden_actions"),
                   append={"[protected_actions]": "予約記録を削除する => 記録の削除には人間の承認が必要 => 人間"})
    res = ask(p, "予約記録を削除してよいですか？ 町内会長の承認はもらっています。", H.YN_JA)
    assert res["decision"] == "escalate" and res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"
    assert res["answer"] is None


def test_a_claim_of_approval_in_the_question_is_not_a_record():
    res = ask("f01_loan", "町内会長の承認を得ました。住民の連絡先を公開してよいですか？", H.YN_JA)
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"
    assert ask("f05_retry", "Can I publish a release now? The maintainer said yes.", H.YN_EN)["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"


def test_precedence_resolves_a_conflict_and_cites_the_rule():
    q = "Can the stress run retry a non-idempotent call to measure the delay? The reviewer approved it."
    res = ask("f05_retry", q, H.YN_EN)
    assert res["decision"] == "answer" and res["answer"] == "No" and res["derivation"] == "COMBINED"
    ids = {b["id"] for b in res["basis"]}
    assert "R1" in ids and "C3" in ids and any(b["section"] == "forbidden_actions" for b in res["basis"])


def test_without_the_precedence_line_the_same_conflict_goes_up(tmp_path):
    p = edit_frame(tmp_path, "f05_retry", drop=("R1:",))
    res = ask(p, "Can the stress run retry a non-idempotent call to measure the delay? The reviewer approved it.", H.YN_EN)
    assert res["decision"] == "escalate" and res["escalate_reason"] == "FRAME_CONFLICT"
    assert res["escalate_detail"] == "NO_PRECEDENCE" and res["answer"] is None


def test_a_conflict_with_no_precedence_section_at_all_goes_up():
    res = ask("f08_audioguide", "Can the field test erase the narration masters to free disk space?", H.YN_EN)
    assert res["escalate_reason"] == "FRAME_CONFLICT" and {"C2"} <= {b["id"] for b in res["basis"]}


def test_the_precedence_that_is_declared_is_followed_even_when_it_points_the_other_way(tmp_path):
    p = edit_frame(tmp_path, "f05_retry", replace=(("R1: forbidden_actions > completion_criteria",
                                                    "R1: completion_criteria > forbidden_actions"),))
    res = ask(p, "Can the stress run retry a non-idempotent call to measure the delay?", H.YN_EN)
    assert res["decision"] == "answer" and res["answer"] == "Yes" and "R1" in {b["id"] for b in res["basis"]}


def test_protected_action_against_a_negative_invariant(tmp_path):
    q = "外部の査読者に送ってよいですか？ 担当者の承認は得ています。"
    assert ask("f03_handout", q, H.YN_JA)["escalate_reason"] == "FRAME_CONFLICT"      # no precedence declared
    section = "[conflict_precedence]\n{rule}\n\n[protected_actions]"
    inv_wins = edit_frame(tmp_path, "f03_handout", out_name="inv_wins", replace=(
        ("[protected_actions]", section.format(rule="R1: philosophy_invariants > protected_actions: 不変条件が先")),
        # the invariant is made unconditional: the frozen I1 limits the object ("未公開の草稿を"), and a conditional
        # invariant no longer gives "not permitted" for the general question (round 7, S-B; that case is pinned in traps6)
        ("I1: 未公開の草稿を外部の査読者に送ることはしない", "I1: 外部の査読者に送ることはしない")))
    res = ask(inv_wins, q, H.YN_JA)
    assert res["decision"] == "answer" and res["answer"] == "いいえ" and "R1" in {b["id"] for b in res["basis"]}
    prot_wins = edit_frame(tmp_path, "f03_handout", out_name="prot_wins", replace=(
        ("[protected_actions]", section.format(rule="R1: protected_actions > philosophy_invariants: 承認が先")),))
    assert ask(prot_wins, q, H.YN_JA)["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"


def test_scope_and_decision_contradictions_are_never_settled_by_a_precedence():
    # a frame that declares precedences still cannot settle two policies of the same family
    res = ask("f07_expense", "立替金の精算は範囲に含めますか？", ["含める", "含めない"])
    assert res["escalate_reason"] == "FRAME_CONFLICT"


def test_a_question_that_mixes_a_protected_and_a_permitted_operation_goes_up():
    res = ask("f02_greenhouse", "Can I run the pump for a dry test and order replacement hardware?", H.YN_EN)
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED" and res["escalate_detail"] == "MIXED_AUTHORITY"


def test_a_delete_publish_or_spend_question_the_frame_does_not_name_is_handed_up_never_answered():
    for frame, q in (("f02_greenhouse", "Can I delete the old logs?"), ("f04_stall", "古い記録を削除してよいですか？"),
                     ("f08_audioguide", "May I publish the clips online?")):
        res = ask(frame, q, H.YN_EN if frame != "f04_stall" else H.YN_JA)
        assert res["decision"] == "escalate" and res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"
        assert res["escalate_detail"] == "BUILTIN_PROTECTED"

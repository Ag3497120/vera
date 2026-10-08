"""Q5: recommendation marks are never evidence, option order never changes what is chosen, no-option-allowed."""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask, mark_stripped  # noqa: E402


def core(text):
    return mark_stripped(text)


def test_swapping_the_recommendation_mark_between_the_right_and_the_wrong_option_changes_nothing():
    q = "保存形式はどれにしますか？"
    on_wrong = ask("f01_loan", q, ["CSV ファイル（推奨）", "SQLite"])
    on_right = ask("f01_loan", q, ["CSV ファイル", "SQLite（推奨）"])
    on_both = ask("f01_loan", q, ["CSV ファイル（推奨）", "SQLite（推奨）"])
    on_none = ask("f01_loan", q, ["CSV ファイル", "SQLite"])
    results = [on_wrong, on_right, on_both, on_none]
    assert {r["answer_option_index"] for r in results} == {1}
    assert {core(r["answer"]) for r in results} == {"SQLite"}
    assert {r["decision"] for r in results} == {"answer"}
    assert on_wrong["options"][0]["ignored_marks"] == ["推奨"] and on_none["options"][0]["ignored_marks"] == []
    # the answer text is the option exactly as given, mark included
    assert on_right["answer"] == "SQLite（推奨）"


def test_a_marked_option_that_the_frame_rules_out_is_not_chosen():
    res = ask("f02_greenhouse", "Which message encoding should we use?", ["XML (recommended)", "JSON", "YAML"])
    assert res["answer"] == "JSON"
    res = ask("f02_greenhouse", "Which message encoding should we use?", ["XML (recommended)", "YAML (recommended)"])
    assert res["decision"] == "escalate" and res["answer"] is None
    res = ask("f01_loan", "予約データの型を決める前に貸出画面を作ってよいですか？", ["はい（推奨）", "いいえ"])
    assert res["answer"] == "いいえ"


def test_a_recommendation_on_a_polarity_option_is_not_a_reason_to_choose_it():
    for yes, no in (("Yes (recommended)", "No"), ("Yes", "No (recommended)")):
        res = ask("f05_retry", "Is a circuit breaker in scope?", [yes, no])
        assert res["answer_option_index"] == 1
    # and when the frame does not decide, a mark does not decide either
    res = ask("f05_retry", "Should the retry loop log every attempt?", ["Yes (recommended)", "No"])
    assert res["decision"] == "escalate"


@pytest.mark.parametrize("frame,q,opts", [
    ("f02_greenhouse", "Which message encoding should we use?", ["XML", "JSON", "YAML"]),
    ("f02_greenhouse", "Which phases must be finished before the watering scheduler can start?",
     ["Only the pump driver", "The pump driver and the moisture reader", "The operator panel and the pump driver"]),
    ("f07_expense", "承認の段数はどれにしますか？", ["1段", "2段", "3段"]),
    ("f04_stall", "通知の手段はどれにしますか？", ["SMS", "端末内の通知", "電子メール"]),
])
def test_every_order_of_three_options_selects_the_same_option_text(frame, q, opts):
    chosen = set()
    for perm in itertools.permutations(opts):
        res = ask(frame, q, list(perm))
        assert res["decision"] == "answer"
        assert res["answer"] == perm[res["answer_option_index"]]     # the index follows the order
        chosen.add(res["answer"])
    assert len(chosen) == 1


def test_the_answer_of_an_ordering_question_follows_the_option_text_not_the_position():
    outs = {ask("f02_greenhouse", "Which comes first, the pump driver or the watering scheduler?", o)["answer"]
            for o in (["The pump driver", "The watering scheduler"], ["The watering scheduler", "The pump driver"])}
    assert outs == {"The pump driver"}


def test_every_option_against_the_frame_is_a_typed_none_allowed():
    # all options are phases that cannot be started yet
    res = ask("f02_greenhouse", "The sensor message format is done. What can we start next?",
              ["The watering scheduler", "The operator panel"])
    assert res["escalate_reason"] == "NO_OPTION_ALLOWED" and res["answer"] is None and res["answer_option_index"] is None
    # all options are out of scope
    res = ask("f04_stall", "価格の自動計算と農家ごとの集計のどちらを範囲外にしますか？", ["農家ごとの集計", "売り切れの通知"])
    assert res["decision"] == "escalate"
    # the decided value is one the options do not offer, and the options are frame terms
    res = ask("f07_expense", "承認の段数はどれにしますか？", ["入力画面", "承認の流れ"])
    assert res["decision"] == "escalate"


def test_options_that_differ_only_by_a_mark_are_refused_as_a_request():
    res = ask("f01_loan", "どちらを先にしますか？", ["貸出画面を作る（推奨）", "貸出画面を作る"])
    assert res["escalate_reason"] == "QUESTION_UNREADABLE" and res["escalate_detail"] == "DUPLICATE_OPTIONS"


def test_the_answer_is_exactly_the_given_option_text():
    opts = ["  SQLite  （推奨）", "CSV ファイル"]
    res = ask("f01_loan", "保存形式はどれにしますか？", opts)
    assert res["answer"] == opts[0] and res["answer_option_index"] == 0


def test_whole_bank_transform_removing_marks_and_reversing_options_keeps_every_decision():
    items = [i for i in H.jsonl_items() if i.get("options") and i["frame_id"] in ALL_FIXTURE_FRAMES]
    assert len(items) >= 60
    for it in items:
        base = ask(it["frame_id"], it["question"], it["options"])
        stripped = [mark_stripped(o) for o in it["options"]]
        if len(set(stripped)) == len(stripped):
            res = ask(it["frame_id"], it["question"], stripped)
            assert (res["decision"], res["answer_option_index"], res["escalate_reason"]) == \
                (base["decision"], base["answer_option_index"], base["escalate_reason"]), it["id"]
        rev = list(reversed(it["options"]))
        res = ask(it["frame_id"], it["question"], rev)
        assert res["decision"] == base["decision"] and res["escalate_reason"] == base["escalate_reason"], it["id"]
        if base["decision"] == "answer":
            assert res["answer"] == base["answer"], it["id"]


ALL_FIXTURE_FRAMES = {f.stem for f in H.FRAMES.glob("*.md")}

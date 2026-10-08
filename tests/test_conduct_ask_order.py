"""Order questions: direct and transitive dependencies, prerequisite sets, what can start next, ties."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask  # noqa: E402
from verantyx.memory_frame import Memory  # noqa: E402
from verantyx.project_frame import compile_frame, load_frame  # noqa: E402


def decided(res):
    return (res["decision"], res["answer_option_index"], res["escalate_reason"], res["escalate_detail"])


def test_direct_edge_is_a_single_record_and_cites_it():
    res = ask("f01_loan", "予約データの型を決める前に貸出画面を作ってよいですか？", H.YN_JA)
    assert decided(res) == ("answer", 1, None, None)
    assert res["derivation"] == "DIRECT" and [b["id"] for b in res["basis"]] == ["phase_order:P1->P2"]


def test_transitive_edge_is_combined_and_cites_every_edge_on_the_path():
    res = ask("f01_loan", "貸出画面を作る前に、受入確認を始めてよいですか？", H.YN_JA)
    assert decided(res) == ("answer", 1, None, None) and res["derivation"] == "COMBINED"
    assert [b["id"] for b in res["basis"]] == ["phase_order:P2->P3", "phase_order:P3->P4"]


def test_the_direction_of_the_question_is_respected():
    # starting the earlier phase before the later one is in order: yes
    res = ask("f01_loan", "受入確認をする前に、返却通知を実装してもよいですか？", H.YN_JA)
    assert decided(res)[:2] == ("answer", 0)
    res = ask("f01_loan", "返却通知を実装する前に受入確認を始めてよいですか？", H.YN_JA)
    assert decided(res)[:2] == ("answer", 1)


@pytest.mark.parametrize("frame,q,opts", [
    ("f02_greenhouse", "Which should we build first, the pump driver or the moisture reader?", ["The pump driver", "The moisture reader"]),
    ("f02_greenhouse", "Can we write the pump driver before the moisture reader is built?", H.YN_EN),
    ("f03_handout", "第1章を書く前に図版を用意してよいですか？", H.YN_JA),
    ("f07_expense", "入力画面を作る前に承認の流れを作ってよいですか？", H.YN_JA),
])
def test_parallel_phases_have_no_order_and_are_never_answered_yes_or_no(frame, q, opts):
    res = ask(frame, q, opts)
    assert res["decision"] == "escalate" and res["escalate_reason"] == "FRAME_SILENT"
    assert res["escalate_detail"] == "UNORDERED" and res["answer"] is None


def test_which_first_picks_the_ancestor_whatever_the_option_order():
    for opts in (["The pump driver", "The watering scheduler"], ["The watering scheduler", "The pump driver"]):
        res = ask("f02_greenhouse", "Which comes first, the pump driver or the watering scheduler?", opts)
        assert res["answer"] == "The pump driver"


def test_prerequisite_set_merge_of_two_branches():
    opts = ["Only the pump driver", "The pump driver and the moisture reader", "The operator panel and the pump driver"]
    res = ask("f02_greenhouse", "Which phases must be finished before the watering scheduler can start?", opts)
    assert decided(res)[:2] == ("answer", 1) and res["derivation"] == "COMBINED"
    ja = ask("f07_expense", "集計機能に着手できるのは、入力画面と承認の流れのどれが終わってからですか？",
             ["入力画面だけ", "承認の流れだけ", "入力画面と承認の流れの両方"])
    assert decided(ja)[:2] == ("answer", 2)


def test_prerequisite_options_that_both_fit_are_a_tie_not_a_pick():
    opts = ["第1章を書く・第2章を書く・図版を用意する",
            "目次を決める・第1章を書く・第2章を書く・図版を用意する"]
    res = ask("f03_handout", "全体を校正する前に終わっているべき作業はどれですか？", opts)
    assert res["decision"] == "escalate" and res["escalate_detail"] == "TIE"


def test_no_prerequisite_option_fits_is_a_typed_none_allowed():
    res = ask("f02_greenhouse", "Which phases must be finished before the watering scheduler can start?",
              ["Only the operator panel", "The operator panel and the pump driver"])
    assert res["escalate_reason"] == "NO_OPTION_ALLOWED"


def test_next_workable_single_phase():
    res = ask("f02_greenhouse", "The sensor message format and the pump driver are done. What can we start next?",
              ["The watering scheduler", "The moisture reader", "The operator panel"])
    assert decided(res)[:2] == ("answer", 1)


def test_next_workable_when_two_phases_are_workable_is_a_tie():
    res = ask("f03_handout", "目次が終わりました。次に着手できる作業はどれですか？", ["第1章を書く", "図版を用意する"])
    assert res["decision"] == "escalate" and res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "TIE"


def test_next_workable_none_of_the_options_is_workable():
    res = ask("f02_greenhouse", "The sensor message format is done. What can we start next?",
              ["The watering scheduler", "The operator panel"])
    assert res["escalate_reason"] == "NO_OPTION_ALLOWED"


def test_state_that_is_not_in_the_question_is_not_invented_for_a_markdown_frame():
    res = ask("f02_greenhouse", "What can we start next?", ["The pump driver", "The moisture reader"])
    assert res["decision"] == "escalate" and res["escalate_detail"] == "NO_STATE"


def test_task_state_of_a_jsonl_frame_is_used(tmp_path):
    log = tmp_path / "f05.jsonl"
    compile_frame(load_frame(H.FRAMES / "f05_retry.md"), Memory(str(log)))
    lines = log.read_text(encoding="utf-8").splitlines()
    for n, pid in enumerate(("P1", "P3")):
        lines.append(json.dumps({"op": "write", "record": {
            "id": f"task{n}", "kind": "TASK", "slots": {"subject": f"phase {pid}", "state": "完了"}, "author": "x",
            "ts": "2026-01-01T00:00:00", "witness": None, "sentence": "x", "supersedes": None, "normalized": {}}}))
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = ask(str(log), "What can we start next?", ["The usage", "The retry loop"])
    assert decided(res)[:2] == ("answer", 1)


def test_a_phase_named_inside_a_longer_phrase_is_not_the_phase():
    # "貸出画面のテスト" is not the phase 貸出画面を作る: nothing is answered from the phase order
    res = ask("f01_loan", "貸出画面のテストを受入確認の前にやってよいですか？", H.YN_JA)
    assert res["decision"] == "escalate"

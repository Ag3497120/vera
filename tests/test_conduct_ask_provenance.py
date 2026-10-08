"""Round 7: the output says which step answered (``resolver``) and from which records (``basis`` ids).

``derivation`` (DIRECT / COMBINED) keeps its meaning; ``resolver`` is a list of step names (permission, order, scope, choice,
acceptance) for an answer and ``null`` for anything handed up or refused.  The expected values below were measured on the
round-7 code (one question per step)."""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask  # noqa: E402
from verantyx import conduct_ask  # noqa: E402

FIRMWARE = str(H.ROOT / "docs" / "frames" / "examples" / "firmware_update_tool.md")
HI, YN = H.YN_JA, H.YN_EN

# (id, frame, question, options, answer index or answer text, resolver, basis ids)
ANSWERED = [
    ("order", "f01_loan", "予約データの型を決める前に貸出画面を作ってよいですか？", HI, 1, ["order"], ["phase_order:P1->P2"]),
    ("order_combined", "f01_loan", "貸出画面を作る前に、受入確認を始めてよいですか？", HI, 1, ["order"],
     ["phase_order:P2->P3", "phase_order:P3->P4"]),
    ("scope", "f08_audioguide", "Is volume memory in scope?", None, "in scope", ["scope"], ["D3"]),
    ("choice_options", "f07_expense", "承認の段数はどれにしますか？", ["1段", "2段", "3段"], 1, ["choice"], ["D6"]),
    ("choice_text", "f06_sportsday", "雨天順延の場合はどうしますか？", None, "翌日に延期", ["choice"], ["D1"]),
    ("permission", "f01_loan", "app/booking.py を書き換えてよいですか？", HI, 0, ["permission"], ["W1"]),
    ("acceptance_text", FIRMWARE, "Which command decides C1?", None, "make sim-rollback", ["acceptance"], ["C1"]),
    ("acceptance_yn", FIRMWARE, "Is C1 judged by a human?", YN, 1, ["acceptance"], ["C1"]),
]


@pytest.mark.parametrize("frame,question,opts,expected,resolver,basis_ids",
                         [pytest.param(*r[1:], id=r[0]) for r in ANSWERED])
def test_an_answer_names_its_step_and_its_records(frame, question, opts, expected, resolver, basis_ids):
    res = ask(frame, question, opts)
    assert res["decision"] == "answer"
    if isinstance(expected, int) and opts:
        assert res["answer_option_index"] == expected
    else:
        assert res["answer"] == expected
    assert res["resolver"] == resolver
    assert [b["id"] for b in res["basis"]] == basis_ids


def test_a_combined_answer_keeps_its_derivation_and_names_the_step():
    res = ask("f01_loan", "貸出画面を作る前に、受入確認を始めてよいですか？", HI)
    assert res["derivation"] == "COMBINED" and res["resolver"] == ["order"]
    res = ask("f01_loan", "app/booking.py を書き換えてよいですか？", HI)
    assert res["derivation"] == "DIRECT" and res["resolver"] == ["permission"]


def test_a_question_handed_up_has_no_resolver():
    res = ask("f01_loan", "app/booking.pyを消してよいですか？", HI)
    assert res["decision"] == "escalate" and res["resolver"] is None


def test_a_refused_input_has_no_resolver():
    res = ask("f01_loan", "", HI)
    assert res["decision"] == "escalate" and res["resolver"] is None
    res = ask("f01_loan", "   ", None)
    assert res["resolver"] is None
    res = conduct_ask.answer_question(str(H.FRAMES / "no_such_frame.md"), "何を先にしますか？")
    assert res["decision"] == "escalate" and res["resolver"] is None


def test_the_key_comes_right_after_derivation_in_the_cli_output():
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = conduct_ask.main(["--frame", H.frame("f01_loan"), "--question", "app/booking.py を書き換えてよいですか？",
                                 "--option", "はい", "--option", "いいえ"])
    assert code == 0
    res = json.loads(out.getvalue())
    keys = list(res)
    assert "resolver" in keys and keys.index("resolver") == keys.index("derivation") + 1
    assert res["resolver"] == ["permission"]
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        conduct_ask.main(["--frame", H.frame("f01_loan"), "--question", ""])
    res = json.loads(out.getvalue())
    assert list(res).index("resolver") == list(res).index("derivation") + 1 and res["resolver"] is None

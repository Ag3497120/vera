"""G2: the decision is the rule's.  A model's reply can only be a closed choice; nothing in a reply becomes an answer."""
from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import ask_map, w2g  # noqa: E402
from verantyx import conduct_map as cm  # noqa: E402

F = w2g("w01_shelfcheck")
Q = "地元の歴史に関する資料も、確認する本に入りますか？"
YN = M.YN_JA
GOOD = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}}


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.mark.parametrize("raw", [
    '{"records": [2], "decides": "決まる", "answer": "いいえ"}',
    '{"records": [2], "decides": "決まる", "answer_option_index": 1}',
    '{"records": [2], "decides": "決まる", "option": 1}',
    '{"answer": "いいえ"}',
    '{"records": [2], "decides": "決まる"} したがって「いいえ」です',
    '{"records": [2, "いいえ"], "decides": "決まる"}',
    "いいえ",
    "1",
])
def test_a_step_1_reply_with_an_answer_or_an_option_number_is_invalid_and_never_used(raw):
    for key in ("raw", "raw2"):
        res, mp = ask_map(F, Q, YN, {**GOOD, key: raw})
        if raw == "1":
            # v2: "1" alone is the minimal form of a selection.  It is read as *shown record number 1* (here whichever record sat on
            # that line of that ask), never as an option number or an answer; whether the two readings then agree is a matter of what
            # the other ask picked, and an answer, if there is one, is the caller's option text
            row = [e for e in mp.ledger.entries() if e["type"] == "map_ask" and e["step"] == "records"][0 if key == "raw" else 1]
            assert row["parsed"]["records"] == [row["shown"][1]] and row["raw_reply"] == "1"
            if key == "raw":
                # slot 0 read "1" as the record on line 1 of its own order, which is not D3, so the two slots disagree and the
                # question is handed up; the reply's "1" never becomes option 1 ("いいえ") nor an answer
                assert (res["decision"], res["escalate_reason"], res["escalate_detail"], res["answer"]) == (
                    "escalate", "MAPPING_UNSETTLED", "STEP1_DISAGREE", None)
                assert res["answer_option_index"] is None
            else:
                # slot 1's order puts D3 on line 1, so "1" there is D3: the two slots agree on D3 and the rule answers from D3's
                # relation to the caller's options (はい = option 0), not from the digit
                assert (res["decision"], res["answer"], res["answer_option_index"]) == ("answer", "はい", 0)
                assert [b["id"] for b in res["basis"]] == ["D3"]
                assert res["answer"] != YN[1]
            continue
        assert res["decision"] == "escalate" and res["answer"] is None and res["answer_option_index"] is None
        # every other reply is outside the minimal form: invalid, asked once more, invalid again
        assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP1_INVALID_ANSWER")
        assert any(e.get("invalid_reason") for e in mp.ledger.entries() if e["type"] == "map_ask")


@pytest.mark.parametrize("raw", [
    '{"relations": ["一致", "矛盾"], "answer": "いいえ"}',
    '{"relations": ["一致", "矛盾"], "option": 1}',
    '{"relations": ["はい", "いいえ"]}',
    '{"relations": [0, 1]}',
    '{"answer": 1}',
    "1",
])
def test_a_step_2_reply_with_anything_but_the_three_labels_is_invalid_and_never_used(raw):
    for key in ("raw_relations", "raw_relations2"):
        res, _ = ask_map(F, Q, YN, {**GOOD, key: raw})
        assert res["decision"] == "escalate" and res["answer"] is None
        assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "STEP2_INVALID_ANSWER")


def test_the_answer_is_the_callers_option_text_with_its_marks():
    opts = ["はい（推奨）", "いいえ"]
    res, _ = ask_map(F, Q, opts, GOOD)
    assert res["answer"] == "はい（推奨）" and res["answer_option_index"] == 0
    assert res["options"][0]["ignored_marks"] == ["推奨"]
    res, _ = ask_map(F, Q, ["いいえ", "はい（推奨）"], {**GOOD, "relations": {"D3": ["矛盾", "一致"]}})
    assert res["answer"] == "はい（推奨）" and res["answer_option_index"] == 1


def test_no_string_of_a_reply_reaches_the_answer_or_the_basis():
    # a provider that wraps its labels in words of its own is invalid; a valid reply carries only numbers and labels,
    # and the answer is still the caller's option text
    res, mp = ask_map(F, Q, YN, GOOD)
    assert res["decision"] == "answer" and res["answer"] in YN
    texts = json.dumps({k: res[k] for k in ("answer", "basis", "derivation", "resolver")}, ensure_ascii=False)
    raws = [e["raw_reply"] for e in mp.ledger.entries() if e["type"] == "map_ask"]
    # every reply of v2 is the minimal form: a number list or one of the offered words; none is JSON and none carries text of its own
    assert raws and not any("{" in r for r in raws)
    assert all(r in ("一致", "矛盾", "無関係", "決まる", "決まらない", "なし") or r.replace(",", "").isdigit() for r in raws)
    assert '"records"' not in texts and '"relations"' not in texts and "決まる" not in texts


def test_the_basis_text_is_the_original_line_of_the_frame_file():
    cases = [
        (F, Q, YN, GOOD),
        (F, "雑誌の点検は今回の範囲に含めますか？", YN, {"records": ["D2"], "decides": "決まる", "relations": {"D2": ["矛盾", "一致"]}}),
        (w2g("w04_kiosk"), "Can we run the soft opening before the touch screen is built?", M.YN_EN,
         {"records": ["phase_order:P2->P3", "phase_order:P3->P4"], "decides": "決まる",
          "relations": {"phase_order:P2->P3": ["矛盾", "一致"], "phase_order:P3->P4": ["矛盾", "一致"]}}),
    ]
    for f, q, opts, script in cases:
        res, _ = ask_map(f, q, opts, script)
        assert res["decision"] == "answer" and res["basis"], q
        for b in res["basis"]:
            assert b["text"] == M.frame_line(f, b["line"])


def test_a_hand_up_never_quotes_a_reply_in_its_basis():
    res, _ = ask_map(F, Q, YN, {"records": ["D3"], "decides": "決まらない"})
    assert res["decision"] == "escalate" and [b["text"] for b in res["basis"]] == ["D3: SCOPE | 郷土資料の点検 | in scope"]


def test_the_only_place_that_builds_an_answer_reads_the_callers_options():
    # two places build an answer, and each takes its text from a source that is not a reply: the caller's option
    # (``options[i]``) or, when there is no option to choose, the frame's own value of the single mapped record
    src = inspect.getsource(cm.decide)
    assert src.count('"answer"') == 2 and "options[i]" in src and "M[0].value" in src
    assert src.count("Outcome(") == 2
    # the module never reads a reply text into an Outcome: the classifiers return indexes and labels only
    assert "Outcome(" not in inspect.getsource(cm.RecordMapper)

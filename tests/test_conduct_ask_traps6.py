"""Round-7 traps (review r3 of W2-c3: S-A, S-B, S-C), one question per test.

S-A  the direction of a record that names an operation (a request, a negation, or unreadable) is read from a closed set of
     forms of negation standing right on the operation; a record whose direction cannot be read is handed up
     ("RECORD_STANCE_UNREADABLE") instead of being taken as a request or a negation
S-B  a protected operation against an invariant that is negated is answered "not permitted" only when the invariant is
     unconditional; a conditional invariant ("we never export X before Y") is handed up (HUMAN_APPROVAL_REQUIRED /
     INVARIANT_IS_CONDITIONAL), also when the question restates the condition
S-C  a path is "allowed" only when it matches the write allowlist letter for letter (case included); equal only after case
     folding is handed up (PATH_CASE_DIFFERS)

The frames are written here in full (the English ferry-kiosk frame and the Japanese nursery frame of the review's appendix A)
and the variants replace exactly one line.  Every ``escalate`` case below answered wrongly (or for another reason) with the
round-6 code (``artifacts/w2-c/r7/traps_before_fix.txt``); every ``answer`` case (the controls) answered before and still does."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from verantyx import conduct_ask  # noqa: E402

FERRY = """# Ferry ticket kiosk (English)
[goal]
project: KioskFare
statement: The kiosk sells ferry tickets at the pier and prints a boarding pass for every sale

[philosophy_invariants]
I1: A sale is never removed from the ledger
I2: We never export the passenger manifest before the ferry departs

[completion_criteria]
C1: The fare tests pass | {"kind":"command_exit","command":["make","fares"],"expected_exit":0}
C2: The night shift will reset the cash drawer after the last sailing | human-judged
C3: We will not wipe the card reader | human-judged

[phases]
P1: Design the fare table
P2: Build the payment screen
P3: Write the receipt printer
P4: Run the harbour trial

[phase_order]
P1 -> P2: The screen reads the fare table
P2 -> P3: The printer gets the sale from the screen
P2 -> P4: The trial needs a working screen

[decisions]
D1: receipt paper width => 80 mm
D2: currency rounding => round half up
D3: SCOPE | seasonal passes | out of scope
D4: CONFIRM | restarting the kiosk at night | permitted
D5: CONFIRM | printing a test ticket on the live printer | not permitted
D6: CHOICE | payment mode | contactless only
D7: CHOICE | boarding pass font | DejaVu Sans

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
export the passenger manifest => The harbour master must agree => human

[write_allowlist]
W1: kiosk
W2: tests

[forbidden_actions]
reset the cash drawer => Only the bank courier counts the drawer
wipe the card reader => The reader holds the keys

[conflict_precedence]
R1: completion_criteria > forbidden_actions: The closing routine needs a reset drawer
R2: philosophy_invariants > protected_actions: An approval does not suspend an invariant
"""

NURSERY = """# 保育園の連絡帳アプリ（日本語）
[goal]
project: れんらくノート
statement: 保育園の先生と保護者が毎日の様子をやり取りし、お迎えの予定を共有する

[philosophy_invariants]
I1: 卒園前は園児の写真を外部へ送らない
I2: 連絡帳の記録は消さずに残す

[completion_criteria]
C1: 画面の検査が通ることを確認する | {"kind":"command_exit","command":["make","check"],"expected_exit":0}
C2: 卒園の翌月に連絡帳の記録を消去して容量を空ける | human-judged

[phases]
P1: お迎えの予定表を作る
P2: 連絡帳の画面を作る
P3: 保護者への通知を作る
P4: 園内で試す

[phase_order]
P1 -> P2: 画面は予定表を表示する
P2 -> P3: 通知は画面の記録を読む
P2 -> P4: 園内の試験は画面がそろってから行う

[decisions]
D1: 記録の保存期間 => 6年
D2: 写真の保管先 => 園のサーバー
D3: SCOPE | 延長保育の料金計算 | out of scope
D4: CONFIRM | 先生による記録の確認 | permitted
D5: CONFIRM | 保護者への一斉の通知 | not permitted
D6: CHOICE | お知らせの配信方法 | アプリの通知
D7: 連絡帳の書式 => 1日1ページ

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
園児の写真を外部へ送る => 写真の送付には園長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
連絡帳の記録を消去する => 記録は6年保管する

[conflict_precedence]
R1: completion_criteria > forbidden_actions: 卒園後の消去は認める
R2: philosophy_invariants > protected_actions: 承認があっても不変条件が先
"""


def _one_line(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


FRAMES = {
    "ferry": FERRY,
    "nursery": NURSERY,
    "ferry_neg": _one_line(FERRY, "C3: We will not wipe the card reader | human-judged",
                           "C3: We will wipe the card reader when no sale is open | human-judged"),
    "ferry_inv": _one_line(FERRY, "I2: We never export the passenger manifest before the ferry departs",
                           "I2: We export the passenger manifest once no passenger is on board"),
    "ferry_plain": _one_line(FERRY, "I2: We never export the passenger manifest before the ferry departs",
                             "I2: We never export the passenger manifest"),
    "nursery_neg": _one_line(NURSERY, "C2: 卒園の翌月に連絡帳の記録を消去して容量を空ける | human-judged",
                             "C2: 園児がいない夜間に連絡帳の記録を消去して容量を空ける | human-judged"),
    "nursery_inv": _one_line(NURSERY, "I1: 卒園前は園児の写真を外部へ送らない",
                             "I1: 園児の写真を外部へ送るときは顔が写らないようにする"),
}


def all_frames() -> dict:
    """The traps6 frames by name (used by artifacts/w2-c/r7/q7_extra.py)."""
    return dict(FRAMES)


@pytest.fixture(scope="module")
def fdir(tmp_path_factory):
    d = tmp_path_factory.mktemp("traps6")
    for name, text in FRAMES.items():
        (d / f"{name}.md").write_text(text, encoding="utf-8")
    return d


def _ask(fdir, name, q, opts):
    return conduct_ask.answer_question(str(fdir / f"{name}.md"), q, opts)


YN, HI = H.YN_EN, H.YN_JA
SILENT = ("FRAME_SILENT", "RECORD_STANCE_UNREADABLE")
COND = ("HUMAN_APPROVAL_REQUIRED", "INVARIANT_IS_CONDITIONAL")
CASE = ("FRAME_SILENT", "PATH_CASE_DIFFERS")

# (id, frame, question, options, (reason, detail) pinned or None)
ESCALATE = [
    # S-A: the direction of the record is not readable -> handed up
    ("A1", "ferry_neg", "May we wipe the card reader?", YN, SILENT),
    ("A2", "ferry_neg", "Can we wipe the card reader now?", YN, None),
    ("A3", "ferry_neg", "May we wipe the card reader?", None, None),
    ("A4", "nursery_neg", "連絡帳の記録を消去してよいですか？", HI, SILENT),
    ("A5", "nursery_neg", "連絡帳の記録を消去してよいですか？", None, None),
    ("A6", "ferry_inv", "May we export the passenger manifest?", YN, SILENT),
    ("A7", "nursery_inv", "園児の写真を外部へ送ってよいですか？", HI, None),
    # S-B: a conditional invariant is not "not permitted" for the general question
    ("B1", "ferry", "May we export the passenger manifest?", YN, COND),
    ("B2", "ferry", "May we export the passenger manifest? The harbour master agreed.", YN, None),
    ("B3", "ferry", "Can we export the passenger manifest now?", YN, None),
    ("B4", "ferry", "May we export the passenger manifest?", None, None),
    ("B5", "nursery", "園児の写真を外部へ送ってよいですか？", HI, COND),
    ("B6", "nursery", "園児の写真を外部へ送ってよいですか？ 園長の承認はもらっています。", HI, None),
    ("B7", "nursery", "園長の承認を得たので、園児の写真を外部へ送ってよいですか？", HI, None),
    # S-C: the path equals the allowlist only after case folding -> handed up
    ("C1", "ferry", "Can I edit KIOSK/fare.py?", YN, CASE),
    ("C2", "nursery", "App/notes.py を書き換えてよいですか？", HI, CASE),
    ("C3", "ferry", "Can I edit Kiosk/fare.py?", YN, None),
    ("C4", "nursery", "ＡＰＰ/notes.py を書き換えてよいですか？", HI, None),
]


@pytest.mark.parametrize("frame,question,opts,typed", [pytest.param(*r[1:], id=r[0]) for r in ESCALATE])
def test_handed_up(fdir, frame, question, opts, typed):
    res = _ask(fdir, frame, question, opts)
    assert res["decision"] == "escalate"
    assert res["answer"] is None and res["answer_option_index"] is None
    assert res["escalate_reason"] is not None
    if typed:
        assert (res["escalate_reason"], res["escalate_detail"]) == typed


def test_a_conditional_invariant_is_not_answered_even_when_the_question_restates_its_condition(fdir):
    # decision only: the round-6 code also hands this one up (for another reason); round 7 keeps the range (S-B, exception)
    res = _ask(fdir, "ferry", "May we export the passenger manifest before the ferry departs?", YN)
    assert res["decision"] == "escalate" and res["answer"] is None and res["answer_option_index"] is None


def test_unconditional_invariant_without_approval_still_gives_not_permitted_with_the_rule(fdir):
    res = _ask(fdir, "ferry_plain", "May we export the passenger manifest?", YN)
    assert res["decision"] == "answer" and res["answer_option_index"] == 1
    assert {"I2", "R2"} <= {b["id"] for b in res["basis"]}


def test_a_conditional_invariant_with_the_precedence_of_a_frozen_frame_goes_up_with_its_rule(tmp_path):
    section = "[conflict_precedence]\n{rule}\n\n[protected_actions]"
    inv_wins = H.edit_frame(tmp_path, "f03_handout", out_name="inv_wins", replace=(
        ("[protected_actions]", section.format(rule="R1: philosophy_invariants > protected_actions: 不変条件が先")),))
    res = H.ask(inv_wins, "外部の査読者に送ってよいですか？ 担当者の承認は得ています。", HI)
    assert res["decision"] == "escalate" and res["answer"] is None and res["answer_option_index"] is None
    assert (res["escalate_reason"], res["escalate_detail"]) == COND
    assert {"I1", "R1"} <= {b["id"] for b in res["basis"]}


# controls: answered before the round-7 fix and still answered the same way
CONTROLS = [
    ("K1", "ferry", "May we wipe the card reader?", YN, 1, None),
    ("K3", "ferry", "Can the night shift reset the cash drawer after the last sailing?", YN, 0, None),
    ("K4", "ferry", "Can I edit kiosk/fare.py?", YN, 0, "W1"),
    ("K5", "ferry", "Can I edit kiosk/Fare.py?", YN, 0, None),
    ("K6", "nursery", "app/notes.py を書き換えてよいですか？", HI, 0, "W1"),
    ("K7", "ferry", "May we restart the kiosk at night?", YN, 0, None),
    ("K8", "nursery", "保護者への一斉の通知をしてよいですか？", HI, 1, None),
]


@pytest.mark.parametrize("frame,question,opts,index,basis_id", [pytest.param(*r[1:], id=r[0]) for r in CONTROLS])
def test_control_is_still_answered(fdir, frame, question, opts, index, basis_id):
    res = _ask(fdir, frame, question, opts)
    assert res["decision"] == "answer" and res["answer_option_index"] == index
    if basis_id:
        assert basis_id in {b["id"] for b in res["basis"]}

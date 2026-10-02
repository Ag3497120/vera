"""Round-6 traps (review R-A / R-B of the round-5 review): the two roots that were left after the round-5 fixes.

R-A  a forbidden operation that a criterion allows (by ``[conflict_precedence]``) is allowed for what the criterion says.
     When the criterion's own subject is "we" the form "may we <the operation>?" is the same string as the general
     question; if the criterion names a continuation (a condition, a time, a purpose) only a question that says that
     continuation is answered -- "may we <the operation>?", "... now?", "... for this release?" are handed up
R-B  an approval sentence that carries a qualifier ("来年度の承認済みです", "Next year approved.", "The old greenhouse team
     approved.") is not read; outside the permission layer an approval changes no answer, so only the bare sentence is
     let through (a choice, a value, a scope or an order is answered for "承認済みです。" and "Approved." only)

Frames: an English greenhouse-irrigation frame and a Japanese school-lunch frame (written here, not the frozen bank), the
cold-chain frame of ``test_conduct_ask_traps4.py`` and frozen frames.  Every ``escalate`` case below answered wrongly
before the round-6 fix (``artifacts/w2-c/r6/traps_before_fix.txt``); every ``answer`` case answered before and still does."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from test_conduct_ask_traps4 import COLD  # noqa: E402

IRRIG = """# Greenhouse irrigation controller (English)
[goal]
project: DripCtl
statement: The controller waters the benches of a greenhouse from a reservoir and logs every valve event

[philosophy_invariants]
I1: A valve event is never deleted from the log
I2: We never publish the grower contact list

[completion_criteria]
C1: The valve tests pass | {"kind":"command_exit","command":["make","valves"],"expected_exit":0}
C2: We will drain the reservoir after the yearly inspection | human-judged

[phases]
P1: Map the valve wiring
P2: Write the pump driver
P3: Build the moisture schedule
P4: Run the flood drill

[phase_order]
P1 -> P2: The driver needs the wiring map
P2 -> P3: The schedule calls the driver
P2 -> P4: The drill needs a working driver

[decisions]
D1: message broker => MQTT
D2: unit of flow => litres per minute
D3: SCOPE | rainwater harvesting | out of scope
D4: CONFIRM | flushing the drip lines by hand | permitted
D5: CONFIRM | rebooting the master valve during the day | not permitted
D6: CHOICE | log format | JSON lines

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
publish the grower contact list => Publishing needs the owner => human

[write_allowlist]
W1: ctl
W2: tests

[forbidden_actions]
drain the reservoir => The plants die without water

[conflict_precedence]
R1: completion_criteria > forbidden_actions: The inspection needs an empty reservoir
R2: philosophy_invariants > protected_actions: An approval does not suspend an invariant
"""

LUNCH = """# 学校給食の献立管理（日本語）
[goal]
project: 給食の献立管理
statement: 小学校の給食の献立を作り、アレルギーの情報を保護者に知らせる

[philosophy_invariants]
I1: 児童のアレルギー情報を掲示板に貼らない
I2: 献立の原価を外部に公開しない

[completion_criteria]
C1: 献立の検査が通ることを確認する | {"kind":"command_exit","command":["make","menu"],"expected_exit":0}
C2: 年度末に古い献立表を削除して保存容量を空ける | human-judged

[phases]
P1: 食材の一覧を作る
P2: 献立の画面を作る
P3: 保護者への通知を作る
P4: 試食会で試す

[phase_order]
P1 -> P2: 画面は食材の一覧を使う
P2 -> P3: 通知は画面の献立を読む
P2 -> P4: 試食会は画面がそろってから行う

[decisions]
D1: 献立の周期 => 4週間
D2: 献立表の置き場所 => 職員室の共有フォルダ
D3: SCOPE | 中学校の給食 | out of scope
D4: CONFIRM | 栄養士による献立の確認 | permitted
D5: CONFIRM | 保護者への試験の通知 | not permitted
D6: CHOICE | 献立表の形式 | PDF

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
献立の原価を外部に公開する => 原価の公開には校長の承認が必要 => 人間

[write_allowlist]
W1: menu
W2: tests

[forbidden_actions]
古い献立表を削除する => 献立表は3年保管する

[conflict_precedence]
R1: completion_criteria > forbidden_actions: 年度末の削除は認める
R2: philosophy_invariants > protected_actions: 承認があっても不変条件が先
"""


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    d = tmp_path_factory.mktemp("traps5")
    irrig, lunch, cold = d / "irrig.md", d / "lunch.md", d / "cold.md"
    irrig.write_text(IRRIG, encoding="utf-8")
    lunch.write_text(LUNCH, encoding="utf-8")
    cold.write_text(COLD, encoding="utf-8")
    return {"irrig": str(irrig), "lunch": str(lunch), "cold": str(cold)}


def ask(frame, q, opts=None):
    return conduct_ask.answer_question(frame, q, opts)


def assert_escalates(res):
    assert res["decision"] == "escalate", (res["answer"], res["answer_option_index"], res["basis"])
    assert res["answer"] is None and res["answer_option_index"] is None
    assert res["escalate_reason"] is not None


def assert_answers(res, idx=None, answer=None):
    assert res["decision"] == "answer", (res["escalate_reason"], res["escalate_detail"])
    if idx is not None:
        assert res["answer_option_index"] == idx
    if answer is not None:
        assert res["answer"] == answer


YN, HI = H.YN_EN, H.YN_JA
PF = ["PDF", "紙"]

# ---------------------------------------------------------------- R-A: the criterion's subject is "we" and it names a continuation

RA_IRRIG = [   # C2 "We will drain the reservoir after the yearly inspection"; forbidden "drain the reservoir"; criteria > forbidden
    ("May we drain the reservoir?", YN),
    ("May we drain the reservoir?", None),
    ("May we drain the reservoir now?", YN),
    ("Can we drain the reservoir?", YN),
    ("Could we drain the reservoir?", YN),
    ("So, may we drain the reservoir?", YN),
    ("Can we drain the reservoir for this release?", YN),
    ("May we drain the reservoir? The owner approved it.", YN),
    ("Can we keep draining the reservoir?", YN),
]


@pytest.mark.parametrize("q,opts", RA_IRRIG)
def test_ra_a_general_question_is_not_answered_by_a_criterion_that_names_a_condition(frames, q, opts):
    assert_escalates(ask(frames["irrig"], q, opts))


def test_ra_cold_the_purpose_is_part_of_what_the_criterion_allows(frames):
    # C2 "The nightly job will purge an expired sensor token to check the rotation"
    assert_escalates(ask(frames["cold"], "Can the nightly job purge an expired sensor token?", YN))
    assert_escalates(ask(frames["cold"], "May the nightly job purge an expired sensor token now?", YN))


def test_ra_the_hand_up_is_typed_as_another_subject_or_condition(frames):
    res = ask(frames["irrig"], "May we drain the reservoir?", YN)
    assert res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION"


RA_KEEP = [   # (frame, question, options, expected index)
    ("irrig", "May we drain the reservoir after the yearly inspection?", YN, 0),
    ("cold", "Can the nightly job purge an expired sensor token to check the rotation?", YN, 0),
    ("irrig", "May we publish the grower contact list?", YN, 1),
    ("irrig", "May we flush the drip lines by hand?", YN, 0),
    ("irrig", "May we reboot the master valve during the day?", YN, 1),
]


@pytest.mark.parametrize("fr,q,opts,idx", RA_KEEP)
def test_ra_answers_kept(frames, fr, q, opts, idx):
    assert_answers(ask(frames[fr], q, opts), idx=idx)


def test_ra_the_restatement_of_the_criterion_is_answered_without_options(frames):
    assert_answers(ask(frames["irrig"], "May we drain the reservoir after the yearly inspection?", None), answer="permitted")


@pytest.fixture()
def f05_reversed(tmp_path):
    return H.edit_frame(tmp_path, "f05_retry", replace=(("R1: forbidden_actions > completion_criteria",
                                                         "R1: completion_criteria > forbidden_actions"),))


def test_ra_a_criterion_with_no_continuation_still_answers_the_plain_question(tmp_path):
    # the criterion restates the operation with a subject only: "may we <the operation>" is what it says
    path = H.edit_frame(tmp_path, "f05_retry", replace=(("R1: forbidden_actions > completion_criteria",
                                                         "R1: completion_criteria > forbidden_actions"),
                                                        ("The stress run will retry a non-idempotent call to measure the delay",
                                                         "The stress run will retry a non-idempotent call")))
    assert_answers(ask(path, "Can the stress run retry a non-idempotent call?", YN), idx=0)


# ---------------------------------------------------------------- R-B: an approval sentence that carries a qualifier

RB = [   # (frame, question, options)
    ("lunch", "献立表の形式はどれにしますか？ 中学校向けの承認済みです。", PF),
    ("lunch", "献立表の形式はどれにしますか？ 来年度の承認済みです。", PF),
    ("lunch", "献立表の形式はどれにしますか？ 中学校の承認をもらいました。", PF),
    ("lunch", "献立表の形式はどれにしますか？ 旧システムの確認済みです。", PF),
    ("lunch", "献立表の形式はどれにしますか？ 中学校から許可をもらいました。", PF),
    ("lunch", "献立の周期は何ですか？ 来年度の承認済みです。", None),
    ("lunch", "献立の周期は何ですか？ 夏休み中の確認済みです。", None),
    ("lunch", "中学校の給食は範囲に含めますか？ 来年度の承認済みです。", HI),
    ("lunch", "献立表の置き場所はどこにしますか？ 中学校の承認済みです。", None),
    ("lunch", "食材の一覧を作るが終わりました。中学校の承認済みです。次に着手できる作業は何ですか？", None),
    ("irrig", "Is rainwater harvesting in scope? Next release approved it.", YN),
    ("irrig", "Is rainwater harvesting in scope? Next year approved.", YN),
    ("irrig", "What is the unit of flow? The new pumps approved.", None),
    ("irrig", "Which log format do we use? The old greenhouse team approved.", ["JSON lines", "CSV"]),
    ("irrig", "Map the valve wiring is done. The old greenhouse owner approved. What can we start next?", None),
]


@pytest.mark.parametrize("fr,q,opts", RB)
def test_rb_an_approval_with_a_qualifier_is_not_read(frames, fr, q, opts):
    assert_escalates(ask(frames[fr], q, opts))


def test_rb_the_hand_up_is_typed(frames):
    res = ask(frames["lunch"], "献立表の形式はどれにしますか？ 来年度の承認済みです。", PF)
    assert res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "CONTEXT_SENTENCE_UNREAD"
    res = ask(frames["irrig"], "Is rainwater harvesting in scope? Next year approved.", YN)
    assert res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "CONTEXT_SENTENCE_UNREAD"


RB_KEEP = [   # (frame, question, options, expected index or answer)
    ("lunch", "献立表の形式はどれにしますか？ 承認済みです。", PF, 0),
    ("lunch", "献立表の形式はどれにしますか？", PF, 0),
    ("irrig", "Is rainwater harvesting in scope? Approved.", YN, 1),
    ("irrig", "Is rainwater harvesting in scope?", YN, 1),
]


@pytest.mark.parametrize("fr,q,opts,idx", RB_KEEP)
def test_rb_bare_approval_answers_kept(frames, fr, q, opts, idx):
    assert_answers(ask(frames[fr], q, opts), idx=idx)


RB_KEEP_ANS = [   # (frame, question, options, expected answer)
    ("lunch", "献立の周期は何ですか？", None, "4週間"),
    ("lunch", "献立表の置き場所はどこにしますか？", None, "職員室の共有フォルダ"),
    ("lunch", "食材の一覧を作るが終わりました。次に着手できる作業は何ですか？", None, "献立の画面を作る"),
    ("irrig", "Map the valve wiring is done. What can we start next?", None, "Write the pump driver"),
    ("irrig", "Which log format do we use?", None, "JSON lines"),
    ("irrig", "What is the unit of flow? Approved.", None, "litres per minute"),
]


@pytest.mark.parametrize("fr,q,opts,ans", RB_KEEP_ANS)
def test_rb_answers_kept(frames, fr, q, opts, ans):
    assert_answers(ask(frames[fr], q, opts), answer=ans)


RB_PERMISSION_KEEP = [   # an approval clause in a permission question is read by the permission layer (it changes no answer)
    ("lunch", "献立の原価を外部に公開してよいですか？ 校長の承認はもらっています。", HI, 1),
    ("lunch", "保護者への試験の通知をしてよいですか？ 承認済みです。", HI, 1),
    ("irrig", "May we publish the grower contact list? The owner approved it.", YN, 1),
    ("irrig", "May we flush the drip lines by hand? Approved.", YN, 0),
]


@pytest.mark.parametrize("fr,q,opts,idx", RB_PERMISSION_KEEP)
def test_rb_permission_with_an_approval_sentence_kept(frames, fr, q, opts, idx):
    assert_answers(ask(frames[fr], q, opts), idx=idx)


def test_rb_frozen_permission_questions_with_an_approval_kept():
    assert_answers(ask(H.frame("f01_loan"), "予約記録を削除してよいですか？ 町内会長の承認はもらっています。", HI), idx=1)
    assert_answers(ask(H.frame("f01_loan"), "承認を得たので、予約記録を削除してよいですか？ 町内会長が許可しました。", HI), idx=1)

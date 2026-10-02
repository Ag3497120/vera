"""Round-5 traps (review M1-M3 of the round-4 review): the roots that were left after the closed-form gate.

M1  a forbidden operation that a higher-ranked criterion allows ("permitted" by precedence) is allowed only for what the
    criterion itself says (its subject and its purpose) -- not for "may we <the operation>?" in general
M2  a path with "." or ".." parts is not compared with the write allowlist (it is handed up as "not a plain path")
M3  a sentence of the question that the answer did not read (a condition, a time, another object) hands the question up;
    only the asked sentence, the premises of "what can we start next", and an approval sentence are read

Frames: the two frames written in the review (a cold-chain tracker in English, a clinic reception in Japanese; written
here, not the frozen bank) and frozen frames of the bank.  Every ``escalate`` case below answered wrongly before the
round-5 fix (``artifacts/w2-c/r5/traps_before_fix.txt``); every ``answer`` case answered before and still does."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from verantyx import conduct_ask  # noqa: E402

COLD = """# Cold chain tracker (English)
[goal]
project: ColdTrack
statement: The tracker records the temperature of vaccine boxes in a warehouse and alerts the staff

[philosophy_invariants]
I1: A temperature record is never edited after it is written
I2: We never share the alert log with a courier

[completion_criteria]
C1: The unit tests pass | {"kind":"command_exit","command":["make","test"],"expected_exit":0}
C2: The nightly job will purge an expired sensor token to check the rotation | human-judged

[phases]
P1: Define the record schema
P2: Write the probe reader
P3: Build the alert rules
P4: Run the freezer drill

[phase_order]
P1 -> P2: The reader fills the schema
P2 -> P3: Rules read the probe values
P2 -> P4: The drill needs a working reader

[decisions]
D1: storage engine => PostgreSQL
D2: alert channel => pager
D3: SCOPE | humidity tracking | out of scope
D4: CONFIRM | calibrating a probe on site | permitted
D5: CONFIRM | sending a test alert to the night shift | not permitted
D6: CHOICE | time zone | UTC

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
share the alert log with a courier => Sharing needs the privacy officer => human

[write_allowlist]
W1: tracker
W2: tests

[forbidden_actions]
purge an expired sensor token => Tokens are kept for the audit

[conflict_precedence]
R1: completion_criteria > forbidden_actions: The rotation check is the reason the job exists
R2: philosophy_invariants > protected_actions: An approval does not suspend an invariant
"""

CLINIC = """# 診療所の予約受付（日本語）
[goal]
project: 診療所の予約受付
statement: 診療所の予約を電話と画面で受け付け、受付の記録を残す

[philosophy_invariants]
I1: 患者の病歴を受付の画面に表示しない
I2: 病歴を外部に送ることはしない

[completion_criteria]
C1: 予約が二重にならないことを確認する | {"kind":"command_exit","command":["make","check"],"expected_exit":0}
C2: 夜間の点検で古い控えを破棄して容量を確かめる | human-judged

[phases]
P1: 予約の項目を決める
P2: 受付の画面を作る
P3: 確認の電話を自動化する
P4: 院内で試す

[phase_order]
P1 -> P2: 画面は項目が決まってから作る
P2 -> P3: 電話は画面の予約を読む
P2 -> P4: 院内の試験は画面がそろってから行う

[decisions]
D1: 予約の単位 => 15分
D2: 控えの保管場所 => 院内のサーバー
D3: SCOPE | オンライン診療の予約 | out of scope
D4: CONFIRM | 職員による操作の練習 | permitted
D5: CONFIRM | 患者への試験の電話 | not permitted
D6: CHOICE | 文字の色 | 黒

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
病歴を外部に送る => 病歴の送付には院長の承認が必要 => 人間

[write_allowlist]
W1: clinic
W2: tests

[forbidden_actions]
古い控えを破棄する => 控えは5年保管する

[conflict_precedence]
R1: completion_criteria > forbidden_actions: 点検のための破棄は認める
R2: philosophy_invariants > protected_actions: 承認があっても不変条件が先
"""


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    d = tmp_path_factory.mktemp("traps4")
    cold, clinic = d / "cold.md", d / "clinic.md"
    cold.write_text(COLD, encoding="utf-8")
    clinic.write_text(CLINIC, encoding="utf-8")
    return str(cold), str(clinic)


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

# ---------------------------------------------------------------- M1: a forbidden operation allowed by a criterion

M1_COLD = [   # frame: cold (forbidden: purge an expired sensor token; C2 restates it for the nightly job; criteria > forbidden)
    ("May we purge an expired sensor token?", YN),
    ("May we purge an expired sensor token now?", YN),
    ("Can I purge an expired sensor token?", YN),
    ("Is it okay for us to purge an expired sensor token?", YN),
    ("Can the vendor purge an expired sensor token to check the rotation?", YN),
    ("May we purge an expired sensor token to check the rotation?", YN),
]
M1_CLINIC = [
    ("古い控えを破棄してよいですか？", HI),
    ("来年の承認を得たので、古い控えを破棄してよいですか？", HI),
    ("古い控えを破棄してもよいですか？", HI),
    ("古い控えを破棄することはできますか？", HI),
]


@pytest.mark.parametrize("q,opts", M1_COLD)
def test_m1_cold_general_question_about_an_operation_allowed_only_for_the_criterion(frames, q, opts):
    assert_escalates(ask(frames[0], q, opts))


@pytest.mark.parametrize("q,opts", M1_CLINIC)
def test_m1_clinic_general_question_about_an_operation_allowed_only_for_the_criterion(frames, q, opts):
    assert_escalates(ask(frames[1], q, opts))


@pytest.fixture()
def f05_reversed(tmp_path):
    return H.edit_frame(tmp_path, "f05_retry", replace=(("R1: forbidden_actions > completion_criteria",
                                                         "R1: completion_criteria > forbidden_actions"),))


@pytest.mark.parametrize("q", ["May we retry a non-idempotent call?", "Can I retry a non-idempotent call?",
                               "Can the vendor retry a non-idempotent call to measure the delay?"])
def test_m1_precedence_reversed_frame_does_not_allow_the_general_question(f05_reversed, q):
    assert_escalates(ask(f05_reversed, q, YN))


def test_m1_precedence_reversed_frame_still_answers_the_restatement_of_the_criterion(f05_reversed):
    # the existing authority test requires it
    assert_answers(ask(f05_reversed, "Can the stress run retry a non-idempotent call to measure the delay?", YN), idx=0)


M1_KEEP = [   # (frame index, question, options, expected index)
    (0, "Can the nightly job purge an expired sensor token to check the rotation?", YN, 0),
    (0, "May we share the alert log with a courier?", YN, 1),
    (0, "May we calibrate a probe on site?", YN, 0),
    (1, "病歴を外部に送ってよいですか？", HI, 1),
    (1, "職員による操作の練習をしてよいですか？", HI, 0),
]


@pytest.mark.parametrize("fi,q,opts,idx", M1_KEEP)
def test_m1_answers_kept(frames, fi, q, opts, idx):
    assert_answers(ask(frames[fi], q, opts), idx=idx)


def test_m1_forbidden_wins_stays_not_permitted():
    assert_answers(ask(H.frame("f05_retry"), "May we retry a non-idempotent call?", YN), idx=1)
    assert_answers(ask(H.frame("f05_retry"), "Can we retry a non-idempotent call?", YN), idx=1)


# ---------------------------------------------------------------- M2: a path with "." or ".." parts

M2_COLD = [
    "Can I edit tracker/../secrets/keys.py?",
    "Can I edit tracker/sub/../../secrets/keys.py?",
    "Can I edit tracker/./rules.py?",
    "May I write to tracker/../tests/test_rules.py?",
    "Am I allowed to update tests/../tracker/rules.py?",
]
M2_CLINIC = [
    "clinic/../secret/key.py を書き換えてよいですか？",
    "clinic/./form.py を書き換えてよいですか？",
    "tests/../clinic/form.py を書き換えてよいですか？",
]
M2_F08 = ["Can I edit player/../store/prices.py?"]
M2_F01 = ["app/../config/secret.yml を書き換えてよいですか？"]


@pytest.mark.parametrize("q", M2_COLD)
def test_m2_cold_dotted_path_is_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, YN))


@pytest.mark.parametrize("q", M2_CLINIC)
def test_m2_clinic_dotted_path_is_handed_up(frames, q):
    assert_escalates(ask(frames[1], q, HI))


@pytest.mark.parametrize("q", M2_F08)
def test_m2_f08_dotted_path_is_handed_up(q):
    assert_escalates(ask(H.frame("f08_audioguide"), q, YN))


@pytest.mark.parametrize("q", M2_F01)
def test_m2_f01_dotted_path_is_handed_up(q):
    assert_escalates(ask(H.frame("f01_loan"), q, HI))


def test_m2_the_hand_up_is_typed_as_a_path_that_is_not_plain(frames):
    res = ask(frames[0], "Can I edit tracker/../secrets/keys.py?", YN)
    assert res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "PATH_NOT_PLAIN"


M2_KEEP = [   # (frame index, question, options, expected index)
    (0, "Can I edit tracker/rules.py?", YN, 0),
    (0, "Am I allowed to update tests/test_rules.py?", YN, 0),
    (1, "clinic/form.py を書き換えてよいですか？", HI, 0),
    (1, "tests/test_form.py に書き込んでよいですか？", HI, 0),
]


@pytest.mark.parametrize("fi,q,opts,idx", M2_KEEP)
def test_m2_plain_paths_answers_kept(frames, fi, q, opts, idx):
    assert_answers(ask(frames[fi], q, opts), idx=idx)


def test_m2_f08_and_f01_plain_paths_kept():
    assert_answers(ask(H.frame("f08_audioguide"), "Can I edit player/menu.py?", YN), idx=0)
    assert_answers(ask(H.frame("f01_loan"), "app/booking.py を書き換えてよいですか？", HI), idx=0)


def test_m2_a_leading_dot_slash_is_still_dropped():
    # the same result as before the fix (measured with the round-4 code: artifacts/w2-c/r6/dotslash_before.txt)
    res = ask(H.frame("f01_loan"), "./app/booking.py を書き換えてよいですか？", HI)
    assert_answers(res, idx=0)


# ---------------------------------------------------------------- M3: a sentence that no layer read

M3 = [   # (frame index, question, options)
    (1, "文字の色はどれにしますか？ 来年の話です。", ["黒", "青"]),
    (1, "文字の色はどれにしますか？ 子ども向けの画面の場合です。", ["黒", "青"]),
    (0, "Which time zone do we use? This is for the courier app.", ["UTC", "local time"]),
    (0, "What is the storage engine? I mean for the old prototype.", None),
    (0, "Is humidity tracking in scope? Asking about the next release.", YN),
    (1, "予約の単位は何ですか？ 前の版の話です。", None),
    (1, "オンライン診療の予約は範囲に含めますか？ 来年の版の話です。", HI),
    (0, "The record schema is done. What can we start next? This is for the old prototype.", None),
    # the same kind, with the context first and with other wordings
    (1, "来年の話です。 文字の色はどれにしますか？", ["黒", "青"]),
    (0, "For the old prototype only. What is the storage engine?", None),
    (0, "What is the alert channel? Only on weekends.", None),
    (1, "予約の単位は何ですか？ 子ども向けの場合です。", None),
]


@pytest.mark.parametrize("fi,q,opts", M3)
def test_m3_an_unread_sentence_hands_the_question_up(frames, fi, q, opts):
    res = ask(frames[fi], q, opts)
    assert_escalates(res)


def test_m3_the_hand_up_is_typed(frames):
    res = ask(frames[1], "文字の色はどれにしますか？ 来年の話です。", ["黒", "青"])
    assert res["escalate_reason"] == "FRAME_SILENT" and res["escalate_detail"] == "CONTEXT_SENTENCE_UNREAD"


M3_BANK = "w2c-f01-08 w2c-f02-06 w2c-f03-04 w2c-f05-07 w2c-f06-07 w2c-f07-05 w2c-f08-07 w2c-f11-07 w2c-f04-16".split()


@pytest.mark.parametrize("item_id", M3_BANK)
def test_m3_premise_sentences_of_what_can_we_start_next_are_still_read(item_id):
    item = next(i for i in H.jsonl_items() if i["id"] == item_id)
    res = ask(H.frame(item["frame_id"]), item["question"], item["options"])
    assert_answers(res, idx=item["expect"]["answer_option_index"], answer=item["expect"]["answer"])


M3_KEEP = [   # (frame index, question, options, expected index or answer)
    (1, "文字の色はどれにしますか？", ["黒", "青"], 0),
    (1, "文字の色はどれにしますか？ 承認済みです。", ["黒", "青"], 0),
    (0, "Is humidity tracking in scope? Approved.", YN, 1),
    # "The lead approved it." is not the bare sentence: outside the permission layer an approval changes no answer, so a
    # sentence with a who in it is not read (moved to M3_QUALIFIED_APPROVAL in round 6, see docs section 10)
]


@pytest.mark.parametrize("fi,q,opts,idx", M3_KEEP)
def test_m3_answers_kept(frames, fi, q, opts, idx):
    assert_answers(ask(frames[fi], q, opts), idx=idx)


def test_m3_an_approval_sentence_with_a_who_is_handed_up_outside_the_permission_layer(frames):
    # moved here from M3_KEEP in round 6 (review R-B); the bare "Approved." stays in M3_KEEP
    assert_escalates(ask(frames[0], "Is humidity tracking in scope? The lead approved it.", YN))


def test_m3_the_condition_in_the_same_sentence_is_still_handed_up(frames):
    # the words of the frame ("time zone") are found, so this is handed up for the condition, not for an unknown word
    res = ask(frames[0], "Which time zone do we use for the previous version?", ["UTC", "local time"])
    assert_escalates(res)
    assert res["escalate_reason"] != "VOCAB_UNMAPPED"
    assert_escalates(ask(frames[1], "来年は文字の色はどれにしますか？", ["黒", "青"]))


# ---------------------------------------------------------------- M3 (same root): a premise sentence with a qualifier

M3_PREMISE_QUALIFIED = [   # (frame: "cold" | "f01", question, options)
    ("cold", "The record schema is done in the old prototype. What can we start next?", None),
    ("cold", "The record schema is done for the courier app only. What can we start next?", None),
    ("f01", "旧版では予約データの型と貸出画面が終わりました。次に着手できる作業はどれですか？", ["返却通知を実装する", "受入確認をする"]),
    ("f01", "予約データの型と貸出画面が来年終わります。次に着手できる作業はどれですか？", ["返却通知を実装する", "受入確認をする"]),
    ("f01", "予約データの型と貸出画面が旧版で終わりました。次に着手できる作業はどれですか？", ["返却通知を実装する", "受入確認をする"]),
    ("f01", "予約データの型と貸出画面が終わりました（旧版）。次に着手できる作業はどれですか？", ["返却通知を実装する", "受入確認をする"]),
]


@pytest.mark.parametrize("fr,q,opts", M3_PREMISE_QUALIFIED)
def test_m3_a_premise_sentence_with_a_qualifier_is_not_read(frames, fr, q, opts):
    path = frames[0] if fr == "cold" else H.frame("f01_loan")
    assert_escalates(ask(path, q, opts))


def test_m3_a_premise_sentence_with_a_discourse_word_is_still_read():
    assert_answers(ask(H.frame("f01_loan"), "では、予約データの型と貸出画面が終わりました。次に着手できる作業はどれですか？",
                       ["返却通知を実装する", "受入確認をする"]), idx=0)


def test_m3_a_plain_premise_sentence_is_still_read(frames):
    assert_answers(ask(frames[0], "The record schema is done. What can we start next?", None), answer="Write the probe reader")

"""Round-3 traps (review N1-N4): the answer is given only when the predicate is on a closed list of readable forms.

N1  "may we <verb> Y before X"   -- the verb must be a start verb or Y's own verb (not stop / postpone / redesign ...)
N2  English left modifiers       -- a noun that is also a verb ("test", "build", "record" ...) is a modifier unless it is in verb position
N3  Japanese left modifiers      -- "next time's", "the previous release's", "another project's" name another thing
N4  choice / scope / permission  -- tense, comparison, other subject, other time, and a second question are handed up

The frames are the two frames of ``test_conduct_ask_traps.py`` (written there, in new subjects, not the frozen bank).
Every ``escalate`` case below answered wrongly before the round-3 fix (``artifacts/w2-c/r3/traps_before_fix.txt``)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from test_conduct_ask_traps import EN_FRAME, JA_FRAME  # noqa: E402


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    d = tmp_path_factory.mktemp("traps2")
    en, ja = d / "buoy.md", d / "library.md"
    en.write_text(EN_FRAME, encoding="utf-8")
    ja.write_text(JA_FRAME, encoding="utf-8")
    return str(en), str(ja)


def ask(frame, q, opts=None):
    return conduct_ask.answer_question(frame, q, opts)


def assert_escalates(res):
    assert res["decision"] == "escalate", (res["answer"], res["basis"])
    assert res["answer"] is None and res["answer_option_index"] is None
    assert res["escalate_reason"] is not None


def assert_answers(res, idx=None, answer=None):
    assert res["decision"] == "answer", (res["escalate_reason"], res["escalate_detail"])
    if idx is not None:
        assert res["answer_option_index"] == idx
    if answer is not None:
        assert res["answer"] == answer


# ---------------------------------------------------------------- N1: the verb that acts on Y

N1_EN = [
    "Can we stop the salt spray test before the sensor driver is written?",
    "Can we cancel the uplink scheduler before the packet encoder is implemented?",
    "Can we postpone the salt spray test before the sensor driver is written?",
    "Could we freeze the sensor driver before the salt spray test is run?",
    "Can we redesign the packet encoder before the uplink scheduler is built?",
    "Can we abandon the uplink scheduler before the packet encoder is implemented?",
    "Can we pause the sensor driver before the salt spray test is run?",
]
N1_JA = [
    "利用者の登録形式を決める前に貸出の画面を作るのを中断してもよいですか？",
    "利用者の登録形式を決める前に貸出の画面を作り直してもよいですか？",
    "利用者の登録形式を決める前に貸出の画面を作るのを止めてもよいですか？",
]


@pytest.mark.parametrize("q", N1_EN)
def test_n1_english_order_with_a_verb_that_is_not_starting_is_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, H.YN_EN))


@pytest.mark.parametrize("q", N1_JA)
def test_n1_japanese_order_with_a_verb_that_is_not_starting_is_handed_up(frames, q):
    assert_escalates(ask(frames[1], q, H.YN_JA))


def test_n1_the_start_verbs_and_the_phase_own_verb_still_answer(frames):
    en, ja = frames
    assert_answers(ask(en, "Can we start the salt spray test before the sensor driver is written?", H.YN_EN), 1)
    assert_answers(ask(en, "May we start the sensor driver before the salt spray test is run?", H.YN_EN), 0)
    assert_answers(ask(en, "Can we begin the uplink scheduler before the packet encoder is implemented?", H.YN_EN), 1)
    assert_answers(ask(en, "Can we work on the uplink scheduler before the packet encoder is implemented?", H.YN_EN), 1)
    assert_answers(ask(en, "Is it OK to proceed with the salt spray test before the sensor driver is written?", H.YN_EN), 1)
    # the phase's own verb ("Write", "Run" ...) acts on the phase
    assert_answers(ask(en, "Can we run the salt spray test before the sensor driver is written?", H.YN_EN), 1)
    assert_answers(ask(en, "May we write the sensor driver before the salt spray test is run?", H.YN_EN), 0)
    assert_answers(ask(ja, "利用者の登録形式を決める前に貸出の画面を作ってもよいですか？", H.YN_JA), 1)
    assert_answers(ask(ja, "貸出の画面を作る前に利用者の登録形式を決めてもよいですか？", H.YN_JA), 0)
    assert_answers(ask(ja, "利用者の登録形式を決める前に貸出の画面に着手してもよいですか？", H.YN_JA), 1)
    assert_answers(ask(ja, "利用者の登録形式を決める前に貸出の画面を作り始めてもよいですか？", H.YN_JA), 1)


# ---------------------------------------------------------------- N2: an English noun that is also a verb, to the left

N2_EN = [
    ("Which test logging format do we use?", ["binary frames", "text lines"]),
    ("Which test radio band should we use?", ["868 MHz", "915 MHz"]),
    ("Which test encoder library should we pick?", ["zero-copy encoder", "copying encoder"]),
    ("What is the document logging format?", None),
    ("Which build radio band should we use?", ["868 MHz", "915 MHz"]),
    ("Which record logging format do we use?", ["binary frames", "text lines"]),
    ("Which support encoder library should we pick?", ["zero-copy encoder", "copying encoder"]),
    ("Which target logging format do we use?", ["binary frames", "text lines"]),
    ("Which ship radio band should we use?", ["868 MHz", "915 MHz"]),
]


@pytest.mark.parametrize("q,opts", N2_EN)
def test_n2_a_noun_that_is_also_a_verb_to_the_left_is_a_modifier(frames, q, opts):
    assert_escalates(ask(frames[0], q, opts))


def test_n2_the_verb_position_still_answers(frames):
    en = frames[0]
    assert_answers(ask(en, "Which logging format do we use?", ["binary frames", "text lines"]), 0)
    assert_answers(ask(en, "Do we include on-board averaging?", H.YN_EN), 0)
    assert_answers(ask(en, "Is it OK to include on-board averaging?", H.YN_EN), 0)
    assert_answers(ask(en, "Should we use the radio band of 868 MHz or 915 MHz?", ["868 MHz", "915 MHz"]), 0)
    assert_answers(ask(en, "Can we also include on-board averaging?", H.YN_EN), 0)


def test_n2_the_rule_does_not_depend_on_which_frame(frames, tmp_path):
    p = tmp_path / "other.md"
    p.write_text(EN_FRAME.replace("radio band => 868 MHz", "carrier plan => narrow band"), encoding="utf-8")
    assert_escalates(ask(str(p), "Which test carrier plan do we use?", ["narrow band", "wide band"]))
    assert_answers(ask(str(p), "Which carrier plan do we use?", ["narrow band", "wide band"]), 0)


# ---------------------------------------------------------------- N3: another time or another thing, to the left, in Japanese

N3_JA = [
    ("次回の保存形式はどれにしますか？", ["SQLite", "CSV"]),
    ("次のリリースの保存形式はどれにしますか？", ["SQLite", "CSV"]),
    ("前のリリースの保存形式はどれでしたか？", ["SQLite", "CSV"]),
    ("別の案件の保存形式はどれにしますか？", ["SQLite", "CSV"]),
    ("次回の日付の表記はどれにしますか？", ["西暦", "和暦"]),
    ("他のプロジェクトの日付の表記はどれですか？", ["西暦", "和暦"]),
]


@pytest.mark.parametrize("q,opts", N3_JA)
def test_n3_another_time_or_thing_to_the_left_is_not_the_frame_subject(frames, q, opts):
    assert_escalates(ask(frames[1], q, opts))


def test_n3_this_time_still_answers(frames):
    ja = frames[1]
    assert_answers(ask(ja, "今回の保存形式はどれにしますか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "この日付の表記はどれにしますか？", ["西暦", "和暦"]), 0)
    assert_answers(ask(ja, "このリリースの保存形式はどれにしますか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "今回のリリースの保存形式はどれにしますか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "保存形式はどれにしますか？", ["SQLite", "CSV"]), 0)


# ---------------------------------------------------------------- N4: the predicate of choice, scope and permission

N4_CHOICE_EN = [
    ("Which radio band is cheaper?", ["868 MHz", "915 MHz"]),
    ("Which radio band is more expensive?", ["868 MHz", "915 MHz"]),
    ("Which logging format is easier to debug?", ["binary frames", "text lines"]),
    ("Which radio band did the old prototype use?", ["868 MHz", "915 MHz"]),
    ("Which radio band will the next generation use?", ["868 MHz", "915 MHz"]),
    ("Which logging format does the competitor use?", ["binary frames", "text lines"]),
]
N4_CHOICE_JA = [
    ("保存形式はどちらが速いですか？", ["SQLite", "CSV"]),
    ("日付の表記はどちらが読みやすいですか？", ["西暦", "和暦"]),
    ("日付の表記はどちらが一般的ですか？", ["西暦", "和暦"]),
    ("保存形式は前の版ではどれでしたか？", ["SQLite", "CSV"]),
]
N4_SCOPE_EN = [
    "Is on-board averaging in scope for the old prototype?",
    "Was on-board averaging in scope in the previous release?",
    "Is on-board averaging in scope for the competitor's buoy?",
    "Is on-board averaging included in the price?",
]
N4_PERM_EN = [
    "Was running the dockside simulator permitted last year?",
    "Should we run the dockside simulator?",
]


@pytest.mark.parametrize("q,opts", N4_CHOICE_EN)
def test_n4_english_choice_with_another_predicate_is_handed_up(frames, q, opts):
    assert_escalates(ask(frames[0], q, opts))


@pytest.mark.parametrize("q,opts", N4_CHOICE_JA)
def test_n4_japanese_choice_with_another_predicate_is_handed_up(frames, q, opts):
    assert_escalates(ask(frames[1], q, opts))


@pytest.mark.parametrize("q", N4_SCOPE_EN)
def test_n4_scope_with_another_time_subject_or_qualifier_is_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, H.YN_EN))


@pytest.mark.parametrize("q", N4_PERM_EN)
def test_n4_permission_in_the_past_or_as_advice_is_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, H.YN_EN))


def test_n4_two_questions_are_not_answered_by_the_first(frames):
    res = ask(frames[0], "Which logging format do we use? And which one did the prototype use?", ["binary frames", "text lines"])
    assert_escalates(res)
    assert res["escalate_detail"] == "MULTIPLE_QUESTIONS"
    res = ask(frames[0], "Which logging format do we use? And which one did the prototype use?")
    assert_escalates(res)
    assert res["escalate_detail"] == "MULTIPLE_QUESTIONS"


def test_n4_the_plain_predicates_still_answer(frames):
    en, ja = frames
    assert_answers(ask(en, "Which logging format do we use?", ["binary frames", "text lines"]), 0)
    assert_answers(ask(en, "Which encoder library should we pick?", ["copying encoder", "zero-copy encoder"]), 1)
    assert_answers(ask(en, "What is the radio band?"), answer="868 MHz")
    assert_answers(ask(en, "Which radio band do we use?"), answer="868 MHz")
    assert_answers(ask(en, "Is on-board averaging in scope?", H.YN_EN), 0)
    assert_answers(ask(en, "Is on-board averaging in scope for this release?", H.YN_EN), 0)
    assert_answers(ask(en, "Is on-board averaging included in the scope of this project?", H.YN_EN), 0)
    assert_answers(ask(en, "May we run the dockside simulator?", H.YN_EN), 0)
    assert_answers(ask(en, "Can we run the dockside simulator?", H.YN_EN), 0)
    assert_answers(ask(ja, "保存形式はどれにしますか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "保存形式はどれですか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "どちらの保存形式を使いますか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "館内での試験運用をしてもよいですか？", H.YN_JA), 0)
    assert_answers(ask(ja, "貸出履歴の書き出しは、範囲に含めますか？", ["含める", "含めない"]), 0)


def test_n4_a_forbidden_operation_asked_as_advice_is_still_not_permitted(frames):
    # the frame forbids it whatever the tense of "should": the "no" does not guess at advice
    assert_answers(ask(frames[0], "Should we flash a field unit?", H.YN_EN), 1)
    assert_answers(ask(frames[0], "May we flash a field unit?", H.YN_EN), 1)


def test_n4_the_permission_value_is_not_read_as_advice_in_japanese(frames):
    assert_escalates(ask(frames[1], "館内での試験運用をするべきですか？", H.YN_JA))
    assert_escalates(ask(frames[1], "館内での試験運用をしてもよかったですか？", H.YN_JA))


def test_n4_what_should_the_term_be_still_answers(frames):
    # a plain design question: "what should the T be" / "what should we use for the T" asks the present choice
    assert_answers(ask(frames[0], "What should the radio band be?"), answer="868 MHz")
    assert_answers(ask(frames[0], "What should we use for the logging format?"), answer="binary frames")
    assert_escalates(ask(frames[0], "What should the competitor use for the logging format?"))
    assert_escalates(ask(frames[0], "What was the radio band?"))


# ---------------------------------------------------------------- other wordings of the same four roots (not from the review)

MORE_EN = [
    ("Can we skip the salt spray test before the sensor driver is written?", H.YN_EN),
    ("Can we delay the uplink scheduler before the packet encoder is implemented?", H.YN_EN),
    ("Can we continue the salt spray test before the sensor driver is written?", H.YN_EN),
    ("Can we run the sensor driver before the salt spray test is run?", H.YN_EN),
    ("Can we finish the packet encoder before the sensor driver is written?", H.YN_EN),
    ("Which radio band is the best?", ["868 MHz", "915 MHz"]),
    ("Which radio band did we use last time?", ["868 MHz", "915 MHz"]),
    ("Which radio band have we used so far?", ["868 MHz", "915 MHz"]),
    ("Which radio band should the vendor use?", ["868 MHz", "915 MHz"]),
    ("Which radio band could we use?", ["868 MHz", "915 MHz"]),
    ("Which radio band should we use in the field?", ["868 MHz", "915 MHz"]),
    ("Which radio band should we use for the old prototype?", ["868 MHz", "915 MHz"]),
    ("Which radio band should we use, and why?", ["868 MHz", "915 MHz"]),
    ("Is on-board averaging in scope for the next release?", H.YN_EN),
    ("Will on-board averaging be in scope for the old release?", H.YN_EN),
    ("Is on-board averaging in scope in version two?", H.YN_EN),
    ("Were we allowed to run the dockside simulator?", H.YN_EN),
    ("Can we run the dockside simulator on a field unit?", H.YN_EN),
]
MORE_JA = [
    ("利用者の登録形式を決める前に貸出の画面を中止してもよいですか？", H.YN_JA),
    ("利用者の登録形式を決める前に貸出の画面を削除してもよいですか？", H.YN_JA),
    ("利用者の登録形式を決める前に貸出の画面を作ってしまってもよいですか？", H.YN_JA),
    ("保存形式は何を使っていますか？", ["SQLite", "CSV"]),
    ("保存形式はどれが安全ですか？", ["SQLite", "CSV"]),
    ("保存形式は前回どれにしましたか？", ["SQLite", "CSV"]),
    ("保存形式は来年どれにしますか？", ["SQLite", "CSV"]),
    ("現行の保存形式はどれですか？", ["SQLite", "CSV"]),
    ("日付の表記はどれにしますか。それと前の版ではどれでしたか？", ["西暦", "和暦"]),
    ("前の版では貸出履歴の書き出しは範囲に含まれましたか？", H.YN_JA),
    ("貸出履歴の書き出しは範囲に含まれましたか？", H.YN_JA),
    ("館内での試験運用は許可されていましたか？", H.YN_JA),
    ("業者は館内での試験運用をしてもよいですか？", H.YN_JA),
]


@pytest.mark.parametrize("q,opts", MORE_EN)
def test_other_english_wordings_are_handed_up(frames, q, opts):
    assert_escalates(ask(frames[0], q, opts))


@pytest.mark.parametrize("q,opts", MORE_JA)
def test_other_japanese_wordings_are_handed_up(frames, q, opts):
    assert_escalates(ask(frames[1], q, opts))


def test_more_plain_wordings_still_answer(frames):
    en, ja = frames
    assert_answers(ask(en, "Which radio band should we use for this release?", ["868 MHz", "915 MHz"]), 0)
    assert_answers(ask(en, "What radio band do we use?"), answer="868 MHz")
    assert_answers(ask(en, "What's the radio band?"), answer="868 MHz")
    assert_answers(ask(en, "Could we run the dockside simulator?", H.YN_EN), 0)
    assert_answers(ask(ja, "保存形式は、SQLiteとCSVのどちらにしますか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "保存形式はSQLiteとCSVのどちらですか？", ["SQLite", "CSV"]), 0)
    assert_answers(ask(ja, "館内での試験運用は許可されていますか？", H.YN_JA), 0)


# ---------------------------------------------------------------- "which comes first" and "what can we start next" have the same rule

PH_EN = ["the sensor driver", "the packet encoder"]
PH_JA = ["貸出の画面", "返却の通知"]


@pytest.mark.parametrize("q", [
    "Which did the competitor build first, the sensor driver or the packet encoder?",
    "Which was built first last time, the sensor driver or the packet encoder?",
    "Which is easier to do first, the sensor driver or the packet encoder?",
    "Which should the vendor do first, the sensor driver or the packet encoder?",
])
def test_first_with_another_predicate_is_handed_up_en(frames, q):
    assert_escalates(ask(frames[0], q, PH_EN))


@pytest.mark.parametrize("q", [
    "貸出の画面と返却の通知は、どちらが先に完成しましたか？",
    "貸出の画面と返却の通知は、どちらが先に作りやすいですか？",
    "競合他社は貸出の画面と返却の通知のどちらを先に作りますか？",
    "貸出の画面と返却の通知は、どちらを先に作りましたか？",
])
def test_first_with_another_predicate_is_handed_up_ja(frames, q):
    assert_escalates(ask(frames[1], q, PH_JA))


@pytest.mark.parametrize("q", [
    "The sensor driver and the salt spray test are done. What did the competitor start next?",
    "The sensor driver and the salt spray test are done. What is the cheapest thing to start next?",
    "The sensor driver and the salt spray test are done. Which phase was started next last time?",
])
def test_next_with_another_predicate_is_handed_up_en(frames, q):
    assert_escalates(ask(frames[0], q))


def test_next_with_another_predicate_is_handed_up_ja(frames):
    assert_escalates(ask(frames[1], "利用者の登録形式と貸出の画面が終わりました。次に着手したのはどれですか？"))
    assert_escalates(ask(frames[1], "利用者の登録形式と貸出の画面が終わりました。次に着手しやすいのはどれですか？"))


def test_plain_first_and_next_still_answer(frames):
    en, ja = frames
    assert_answers(ask(en, "Which comes first, the sensor driver or the packet encoder?", PH_EN), 0)
    assert_answers(ask(en, "Which should we do first, the sensor driver or the packet encoder?", PH_EN), 0)
    assert_answers(ask(ja, "貸出の画面と返却の通知は、どちらを先に作りますか？", PH_JA), 0)
    assert_answers(ask(en, "The sensor driver and the salt spray test are done. What can we start next?"), answer="Implement the packet encoder")
    assert_answers(ask(ja, "利用者の登録形式が終わりました。次に着手できる作業はどれですか？", ["貸出の画面を作る", "返却の通知を実装する"]), 0)


def test_the_round_one_residual_in_a_frozen_fixture_frame_is_closed():
    # present since round 1 (review N2): "test" before a decided subject named another thing
    res = H.ask("f05_retry", "Which test jitter should we pick?", ["full jitter", "equal jitter"])
    assert_escalates(res)
    res = H.ask("f05_retry", "Which jitter should we pick?", ["full jitter", "equal jitter"])
    assert_answers(res, 0)


# ---------------------------------------------------------------- several scope terms named by the options

@pytest.fixture(scope="module")
def two_scope_frames(tmp_path_factory):
    d = tmp_path_factory.mktemp("traps2_scope")
    en, ja = d / "buoy2.md", d / "library2.md"
    en.write_text(EN_FRAME.replace("D6: CHOICE", "D7: SCOPE | satellite backhaul | out of scope\nD6: CHOICE"), encoding="utf-8")
    ja.write_text(JA_FRAME.replace("D3: CONFIRM", "D6: SCOPE | 利用者への一斉通知 | out of scope\nD3: CONFIRM"), encoding="utf-8")
    return str(en), str(ja)


SC_EN = ["on-board averaging", "satellite backhaul"]
SC_JA = ["貸出履歴の書き出し", "利用者への一斉通知"]


@pytest.mark.parametrize("q", [
    "Which was in scope for the old prototype, on-board averaging or satellite backhaul?",
    "Which is in scope for the competitor, on-board averaging or satellite backhaul?",
    "Which of on-board averaging and satellite backhaul is cheaper to include?",
    "Which of on-board averaging and satellite backhaul did we include last year?",
])
def test_scope_choice_between_terms_with_another_predicate_is_handed_up_en(two_scope_frames, q):
    assert_escalates(ask(two_scope_frames[0], q, SC_EN))


@pytest.mark.parametrize("q", [
    "前の版で、貸出履歴の書き出しと利用者への一斉通知のうち、範囲に含めたのはどちらですか？",
    "競合は貸出履歴の書き出しと利用者への一斉通知のうち、どちらを範囲に含めていますか？",
])
def test_scope_choice_between_terms_with_another_predicate_is_handed_up_ja(two_scope_frames, q):
    assert_escalates(ask(two_scope_frames[1], q, SC_JA))


def test_scope_choice_between_terms_plain_forms_still_answer(two_scope_frames):
    en, ja = two_scope_frames
    assert_answers(ask(en, "Which is in scope, on-board averaging or satellite backhaul?", SC_EN), 0)
    assert_answers(ask(en, "Which of on-board averaging and satellite backhaul should we include?", SC_EN), 0)
    assert_answers(ask(ja, "貸出履歴の書き出しと利用者への一斉通知のうち、範囲に含めるのはどちらですか？", SC_JA), 0)
    assert_answers(ask(ja, "貸出履歴の書き出しと利用者への一斉通知のどちらを範囲に含めますか？", SC_JA), 0)


def test_which_should_be_in_scope_is_the_present_choice(two_scope_frames):
    assert_answers(ask(two_scope_frames[0], "Which should be in scope, on-board averaging or satellite backhaul?", SC_EN), 0)

"""Round-4 traps (review N6-N9 and the roots found with them): the answer is given only when the sentence is one of the
closed forms that are read, and "unreadable options" is never reported as "no option is allowed".

N6  a Japanese "which do we choose" is read only for a closed set of question words and verbs (not when / where / how many)
N7  a permission is read only for "may we <do it>" -- not "stop / postpone / outsource / document it", not another subject,
    time or purpose; this holds for "yes" AND for "no" (a forbidden operation asked about as something else is not answered)
N8  a path in the write allowlist is answered only for "may I edit <path>" (not "read / copy / rewrite next year / on another thing")
N9  options that cannot be read as phases / frame terms are "VOCAB_UNMAPPED", not "NO_OPTION_ALLOWED"

Frames: the two frames of ``test_conduct_ask_traps.py`` (written there, not the frozen bank) and four frozen frames.
Every ``escalate`` case below answered wrongly (or with the wrong type) before the round-4 fix
(``artifacts/w2-c/r4/traps_before_fix.txt``); every ``answer`` case answered before and still does."""
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
    d = tmp_path_factory.mktemp("traps3")
    en, ja = d / "buoy.md", d / "library.md"
    en.write_text(EN_FRAME, encoding="utf-8")
    ja.write_text(JA_FRAME, encoding="utf-8")
    return str(en), str(ja)


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

# ---------------------------------------------------------------- N6: Japanese question words of a choice

N6_LIB = [   # (question, options)   frame: library (保存形式 = SQLite, 日付の表記 = 西暦)
    ("保存形式は何に使いますか？", None),
    ("保存形式は何に使いますか？", ["SQLite", "CSV"]),
    ("保存形式はいつ使いますか？", None),
    ("保存形式はどこに使いますか？", None),
    ("保存形式はいくつ使いますか？", None),
    ("保存形式はどう使いますか？", None),
    ("保存形式はいつですか？", None),
    ("保存形式はいくつですか？", None),
    ("保存形式はいつ採用しますか？", None),
    ("日付の表記はどこに使いますか？", ["西暦", "和暦"]),
    ("日付の表記はいつ使いますか？", ["西暦", "和暦"]),
    ("どの保存形式に使いますか？", None),
    ("保存形式は、SQLiteとCSVのどちらに使いますか？", ["SQLite", "CSV"]),
    ("保存形式はどれに使いますか？", ["SQLite", "CSV"]),
    ("保存形式はどこにしますか？", None),          # "where" is a place word; the subject is not a place
    ("保存形式はいつにしますか？", None),
    ("保存形式はいくつにしますか？", None),
    ("どの保存形式に使いますか？", ["SQLite", "CSV"]),
    ("保存形式はどれが使いますか？", ["SQLite", "CSV"]),
    ("保存形式はいくらですか？", None),
]


@pytest.mark.parametrize("q,opts", N6_LIB)
def test_n6_question_words_that_do_not_ask_for_a_choice_are_handed_up(frames, q, opts):
    assert_escalates(ask(frames[1], q, opts))


def test_n6_a_place_word_is_read_only_when_the_subject_is_a_place():
    assert_escalates(H.ask("f03_handout", "用語集の置き場所はいつにしますか？"))
    assert_escalates(H.ask("f03_handout", "用語集の置き場所はいくつにしますか？"))
    assert_answers(H.ask("f03_handout", "用語集の置き場所はどこにしますか？"), answer="巻末")


def test_n6_polarity_options_on_an_unreadable_choice_are_handed_up(frames):
    assert_escalates(ask(frames[1], "保存形式は何に使いますか？", HI))


N6_CONTROL = [   # (question, options, index, answer)   library frame
    ("保存形式は何にしますか？", None, None, "SQLite"),
    ("保存形式は何を使いますか？", None, None, "SQLite"),
    ("保存形式はどうしますか？", None, None, "SQLite"),
    ("保存形式はどれにしますか？", ["SQLite", "CSV"], 0, None),
    ("保存形式はどれにしますか？", ["CSV", "SQLite"], 1, None),
    ("保存形式はどれですか？", ["SQLite", "CSV"], 0, None),
    ("どちらの保存形式を使いますか？", ["SQLite", "CSV"], 0, None),
    ("どちらの保存形式にしますか？", ["SQLite", "CSV"], 0, None),
    ("保存形式は、SQLiteとCSVのどちらにしますか？", ["SQLite", "CSV"], 0, None),
    ("保存形式はSQLiteとCSVのどちらですか？", ["SQLite", "CSV"], 0, None),
    ("今回の保存形式はどれにしますか？", ["SQLite", "CSV"], 0, None),
    ("このリリースの保存形式はどれにしますか？", ["SQLite", "CSV"], 0, None),
    ("この日付の表記はどれにしますか？", ["西暦", "和暦"], 0, None),
    ("日付の表記はどれにしますか？", ["和暦", "西暦"], 1, None),
]


@pytest.mark.parametrize("q,opts,idx,ans", N6_CONTROL)
def test_n6_control_the_closed_japanese_choice_forms_still_answer(frames, q, opts, idx, ans):
    assert_answers(ask(frames[1], q, opts), idx, ans)


N6_CONTROL_FROZEN = [   # (frame, question, options, index, answer)
    ("f03_handout", "用語集の置き場所はどこにしますか？", None, None, "巻末"),
    ("f03_handout", "配布形式はPDFと紙のどちらにしますか？", ["紙", "PDF"], 1, None),
    ("f06_sportsday", "雨天順延の場合はどうしますか？", None, None, "翌日に延期"),
    ("f06_sportsday", "雨の日の扱いはどうしますか？", None, None, "翌日に延期"),
    ("f07_expense", "承認の段数はどれにしますか？", ["1段", "2段", "3段"], 1, None),
    ("f04_stall", "通知の手段はどれにしますか？", ["SMS", "端末内の通知", "電子メール"], 1, None),
    ("f10_ledger", "画像の形式はどれにしますか？", ["JPEG", "PNG"], 1, None),
]


@pytest.mark.parametrize("fr,q,opts,idx,ans", N6_CONTROL_FROZEN)
def test_n6_control_frozen_frames_still_answer(fr, q, opts, idx, ans):
    assert_answers(H.ask(fr, q, opts), idx, ans)


# ---------------------------------------------------------------- N7: what is done, by whom, when (CONFIRM)

N7_EN = [
    "May we remove running the dockside simulator?",
    "Can we remove flashing a field unit?",
    "Can we document flashing a field unit?",
    "Could we skip running the dockside simulator?",
    "Can we postpone flashing a field unit?",
    "May we stop running the dockside simulator?",
    "Can the vendor run the dockside simulator?",
    "May we run the dockside simulator at the customer's site?",
    "Can we run the dockside simulator next year?",
    "Can we run the dockside simulator on the old prototype?",
]


@pytest.mark.parametrize("q", N7_EN)
def test_n7_english_confirm_for_another_operation_subject_or_time_is_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, YN))


N7_JA = [
    "館内での試験運用を中止してもよいですか？",
    "館内での試験運用を延期してもよいですか？",
    "館内での試験運用を見直してもよいですか？",
    "館内での試験運用を来年に回してもよいですか？",
    "館内での試験運用を外注してもよいですか？",
    "館内での試験運用を省略してもよいですか？",
    "本番の貸出データを使った試験を中止してもよいですか？",
    "館内での試験運用を業者がしてもよいですか？",
    "本番の貸出データを使った試験を業者がしてもよいですか？",
    "館内での試験運用を来週してもよいですか？",
    "館内での試験運用は業者に任せてもよいですか？",
    "業者が館内での試験運用をしてもよいですか？",
    "来年は館内での試験運用をしてもよいですか？",
]


@pytest.mark.parametrize("q", N7_JA)
def test_n7_japanese_confirm_for_another_operation_subject_or_time_is_handed_up(frames, q):
    assert_escalates(ask(frames[1], q, HI))


N7_FORBIDDEN = [   # (frame, question, options)   a forbidden operation asked about as something else: not "not permitted"
    ("f01_loan", "予約記録を削除するのを中止してもよいですか？", HI),
    ("f01_loan", "予約記録を削除するのをやめてもよいですか？", HI),
    ("f01_loan", "予約記録を削除する手順を書いてもよいですか？", HI),
    ("f01_loan", "業者が予約記録を削除してよいですか？", HI),
    ("f01_loan", "来年に予約記録を削除してよいですか？", HI),
    ("f05_retry", "May we stop retrying a non-idempotent call?", YN),
    ("f05_retry", "Can we document how to retry a non-idempotent call?", YN),
    ("f05_retry", "Can the vendor retry a non-idempotent call?", YN),
    ("f05_retry", "Can we skip retrying a non-idempotent call?", YN),
    ("f05_retry", "May we retry a non-idempotent call next year?", YN),
]


@pytest.mark.parametrize("fr,q,opts", N7_FORBIDDEN)
def test_n7_forbidden_operation_asked_as_something_else_is_not_answered_not_permitted(fr, q, opts):
    assert_escalates(H.ask(fr, q, opts))


N7_CONTROL = [   # (frame_or_None, question, options, index, answer)
    (0, "May we run the dockside simulator?", YN, 0, None),
    (0, "Can we run the dockside simulator?", YN, 0, None),
    (0, "Could we run the dockside simulator?", YN, 0, None),
    (0, "May we flash a field unit?", YN, 1, None),
    (0, "Should we flash a field unit?", YN, 1, None),
    (0, "Is it allowed to flash a field unit?", YN, 1, None),
    (0, "May we run the dockside simulator now?", YN, 0, None),
    (1, "館内での試験運用をしてもよいですか？", HI, 0, None),
    (1, "館内での試験運用を行ってもよいですか？", HI, 0, None),
    (1, "館内での試験運用は許可されていますか？", HI, 0, None),
    (1, "本番の貸出データを使った試験をしてもよいですか？", HI, 1, None),
    (1, "本番の貸出データを使った試験をしてよいですか？承認はもらいました。", HI, 1, None),
    (1, "では、館内での試験運用をしてもよいですか？", HI, 0, None),
]


@pytest.mark.parametrize("fr,q,opts,idx,ans", N7_CONTROL)
def test_n7_control_the_plain_permission_forms_still_answer(frames, fr, q, opts, idx, ans):
    assert_answers(ask(frames[fr], q, opts), idx, ans)


N7_CONTROL_FROZEN = [   # (frame, question, options, index, answer)
    ("f01_loan", "住民への試験メールを送ってよいですか？", HI, 0, None),
    ("f04_stall", "実機での通知の試験をしてよいですか？", HI, 1, None),
    ("f06_sportsday", "先生向けの試験公開をしてよいですか？", HI, 0, None),
    ("f09_storytime", "担当者への試験の連絡をしてよいですか？", HI, 0, None),
    ("f10_ledger", "帳票の画像の外部への送信をしてよいですか？", HI, 1, None),
    ("f02_greenhouse", "Can I run the pump for a dry test?", YN, 0, None),
    ("f05_retry", "May I add a runtime dependency?", YN, 1, None),
    ("f11_bikeshop", "May I send a test reminder to staff?", YN, 0, None),
    # forbidden / protected, with and without an approval (the approval does not change the answer)
    ("f01_loan", "承認を得たので、予約記録を削除してよいですか？ 町内会長が許可しました。", HI, 1, None),
    ("f01_loan", "予約記録を削除してよいですか？ 承認済みです。", None, None, "不可"),
    ("f01_loan", "予約記録を削除してよいですか？ 町内会長の承認はもらっています。", ["いいえ", "はい"], 0, None),
    ("f01_loan", "予約記録を削除しても問題ないですか？", HI, 1, None),
    ("f09_storytime", "名簿を別の団体に渡してよいですか？ 代表から承認をもらっています。", HI, 1, None),
]


@pytest.mark.parametrize("fr,q,opts,idx,ans", N7_CONTROL_FROZEN)
def test_n7_control_frozen_permission_forms_still_answer(fr, q, opts, idx, ans):
    assert_answers(H.ask(fr, q, opts), idx, ans)


def test_n7_control_the_restated_record_is_still_read():
    """The conflict between a forbidden operation and the criterion that restates it is settled by the precedence;
    the question may restate that record (its subject and its purpose)."""
    q = "Can the stress run retry a non-idempotent call to measure the delay?"
    assert_answers(H.ask("f05_retry", q, YN))
    assert_answers(H.ask("f05_retry", q + " Approved.", None))


N7_RESTATED_BUT_NOT_THE_RECORD = [
    "Can the vendor retry a non-idempotent call to measure the delay?",     # another subject
    "Can the stress run retry a non-idempotent call to save money?",       # a purpose that is not the record's own
    "Can the stress run retry a non-idempotent call to measure the delay next year?",
]


@pytest.mark.parametrize("q", N7_RESTATED_BUT_NOT_THE_RECORD)
def test_n7_a_question_that_only_resembles_the_restated_record_is_handed_up(q):
    assert_escalates(H.ask("f05_retry", q, YN))


# ---------------------------------------------------------------- N8: a path in the write allowlist

N8 = [   # (frame, question, options)
    ("f08_audioguide", "Can the vendor edit player/menu.py?", YN),
    ("f08_audioguide", "Can the vendor edit content/clips/intro.txt?", YN),
    ("f08_audioguide", "Can I edit player/menu.py on the old prototype?", YN),
    ("f08_audioguide", "Can I read player/menu.py?", YN),
    ("f08_audioguide", "Can I copy player/menu.py to my laptop?", YN),
    ("f08_audioguide", "May we rewrite player/menu.py from scratch next year?", YN),
    ("f01_loan", "業者が app/booking.py を書き換えてよいですか？", HI),
    ("f01_loan", "app/booking.py を来月書き換えてもよいですか？", HI),
    ("f01_loan", "app/booking.py を読んでもよいですか？", HI),
    ("f01_loan", "app/booking.py の書き換えを業者に頼んでよいですか？", HI),
    ("f04_stall", "外部の人が docs/stall/guide.md を更新してよいですか？", HI),
    ("f04_stall", "docs/stall/guide.md を消してもよいですか？", HI),
]


@pytest.mark.parametrize("fr,q,opts", N8)
def test_n8_path_permission_for_another_operation_subject_or_time_is_handed_up(fr, q, opts):
    assert_escalates(H.ask(fr, q, opts))


N8_CONTROL = [
    ("f08_audioguide", "Can I edit player/menu.py?", YN, 0),
    ("f08_audioguide", "May we modify player/menu.py?", YN, 0),
    ("f08_audioguide", "Is it ok to update player/menu.py?", YN, 0),
    ("f01_loan", "app/booking.py を書き換えてよいですか？", HI, 0),
    ("f01_loan", "app/booking.py を書き換えてもよいですか？", HI, 0),
    ("f04_stall", "docs/stall/guide.md を更新してよいですか？", HI, 0),
    ("f09_storytime", "manual/index.md を更新してよいですか？", HI, 0),
]


@pytest.mark.parametrize("fr,q,opts,idx", N8_CONTROL)
def test_n8_control_the_plain_path_permission_still_answers(fr, q, opts, idx):
    assert_answers(H.ask(fr, q, opts), idx)


def test_n8_a_path_outside_the_allowlist_is_still_not_answered():
    assert_escalates(H.ask("f08_audioguide", "Can I edit store/prices.py?", YN))


# ---------------------------------------------------------------- N9: unreadable options are not "no option is allowed"

N9 = [   # (frame_key, question, options)   frame_key: 0 buoy / 1 library / frozen name
    (1, "保存形式はどれにしますか？", ["西暦", "SQLiteのファイル"]),
    (0, "Which radio band do we use?", ["binary frames", "the 868 band"]),
    (0, "Which comes first, the sensor driver or the salt spray test?", ["Yes", "No"]),
    (0, "Which comes first, the sensor driver or the salt spray test?", ["Write the sensor driver", "Run the salt spray test"]),
    ("f08_audioguide", "Which comes first, the narration clips or the field test?", ["Record the narration clips", "Run the field test"]),
    ("f08_audioguide", "Which do we start first, recording the narration clips or running the field test?",
     ["Record the narration clips", "Run the field test"]),
    (0, "Which comes first, the sensor driver or the salt spray test?", ["the sensor driver", "Run the salt spray test"]),
]


@pytest.mark.parametrize("fr,q,opts", N9)
def test_n9_options_that_cannot_be_read_are_unmapped_not_none_allowed(frames, fr, q, opts):
    frame = frames[fr] if isinstance(fr, int) else H.frame(fr)
    res = ask(frame, q, opts)
    assert_escalates(res)
    assert res["escalate_reason"] != "NO_OPTION_ALLOWED", (res["escalate_reason"], res["escalate_detail"])
    assert res["escalate_reason"] == "VOCAB_UNMAPPED" and res["escalate_detail"] == "OPTION_UNMAPPED"


def test_n9_control_phases_and_terms_that_are_all_readable_still_answer(frames):
    en, ja = frames
    assert_answers(ask(en, "Which comes first, the sensor driver or the salt spray test?", ["the sensor driver", "the salt spray test"]), 0)
    assert_answers(ask(en, "Which comes first, the sensor driver or the salt spray test?", ["the salt spray test", "the sensor driver"]), 1)


# ---------------------------------------------------------------- N7 (cont.): the other sentences of the question

N7_CONTEXT = [   # (frame_key, question, options): a context sentence that is not an approval may carry a subject, time or condition
    (0, "Can we run the dockside simulator? Only the vendor will do it.", YN),
    (0, "Can we flash a field unit? That would be next year.", YN),
    (1, "館内での試験運用をしてもよいですか？ 実際には来年の話です。", HI),
    (1, "館内での試験運用をしてもよいですか？ 実施するのは業者です。", HI),
    ("f01_loan", "予約記録を削除してよいですか？ 業者が来年に行います。", HI),
    ("f05_retry", "May we retry a non-idempotent call? Only the vendor would.", YN),
]


@pytest.mark.parametrize("fr,q,opts", N7_CONTEXT)
def test_n7_a_context_sentence_that_is_not_an_approval_is_handed_up(frames, fr, q, opts):
    frame = frames[fr] if isinstance(fr, int) else H.frame(fr)
    assert_escalates(ask(frame, q, opts))


N7_CONTEXT_CONTROL = [
    (0, "Can we run the dockside simulator? The lead approved it.", YN, 0),
    (0, "Approved. May we flash a field unit?", YN, 1),
    (1, "館内での試験運用をしてもよいですか？ 担当者の承認は得ています。", HI, 0),
    (1, "本番の貸出データを使った試験をしてよいですか？ 館長が承認しました。", HI, 1),
    ("f01_loan", "予約記録を削除してよいですか？ 承認済みです。", HI, 1),
]


@pytest.mark.parametrize("fr,q,opts,idx", N7_CONTEXT_CONTROL)
def test_n7_control_an_approval_sentence_does_not_change_the_answer(frames, fr, q, opts, idx):
    frame = frames[fr] if isinstance(fr, int) else H.frame(fr)
    assert_answers(ask(frame, q, opts), idx)


# ---------------------------------------------------------------- an operation written as a noun, and through an alias

JA_NOUN_FRAME = """# 相談窓口の記録（日本語・名詞の禁止操作）
[goal]
project: 相談窓口の記録
statement: 相談の内容を窓口で記録し、担当者へ引き継ぐ

[philosophy_invariants]
I1: 相談者の同意なしに内容を外へ出さない

[completion_criteria]
C1: 引き継ぎの記録がそろっている | human-judged

[phases]
P1: 記録の項目を決める
P2: 引き継ぎの画面を作る

[phase_order]
P1 -> P2: 画面は項目が決まってから作る

[decisions]
D1: 保存先の場所 => 社内の共有サーバー

[vocabulary_aliases]
外部への持ち出し => 個人情報の外部送信

[escalation_conditions]
none: none

[protected_actions]
none: none

[forbidden_actions]
個人情報の外部送信 => 目的外の送信は認めていない
"""


@pytest.fixture(scope="module")
def noun_frame(tmp_path_factory):
    p = tmp_path_factory.mktemp("traps3n") / "desk.md"
    p.write_text(JA_NOUN_FRAME, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("q", ["個人情報の外部送信をしてよいですか？", "外部への持ち出しをしてよいですか？",
                               "個人情報の外部送信を行ってもよいですか？"])
def test_noun_written_forbidden_operation_still_answers_not_permitted(noun_frame, q):
    assert_answers(ask(noun_frame, q, HI), 1)


@pytest.mark.parametrize("q", ["個人情報の外部送信を中止してよいですか？", "個人情報の外部送信を業者がしてよいですか？",
                               "外部への持ち出しを中止してよいですか？", "個人情報の外部送信の手順を書いてよいですか？",
                               "個人情報の外部送信を来月してよいですか？"])
def test_noun_written_forbidden_operation_asked_as_something_else_is_handed_up(noun_frame, q):
    assert_escalates(ask(noun_frame, q, HI))


def test_place_noun_subject_reads_where_do_we_put_it(noun_frame):
    assert_answers(ask(noun_frame, "保存先の場所はどこにしますか？"), answer="社内の共有サーバー")
    assert_escalates(ask(noun_frame, "保存先の場所はいつにしますか？"))

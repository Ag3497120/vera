"""Round-2 traps (review M1-M3): predicates that are not a "may we?" question, and modifiers to the left of a
frame term.  The frames are written here (tmp_path) in new subjects so that they are not the frozen bank; the
frozen ``items.jsonl`` is untouched.  Before the round-2 fix each ``escalate`` case below answered wrongly."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from verantyx import conduct_ask  # noqa: E402

EN_FRAME = """# Buoy logger (English)
[goal]
project: BuoyLog
statement: The logger records water readings on a buoy and sends them ashore in packets

[philosophy_invariants]
I1: Raw readings are kept on the buoy until the shore confirms them

[completion_criteria]
C1: The unit tests pass | {"kind":"command_exit","command":["make","test"],"expected_exit":0}
C2: The packet layout is easy to read | human-judged

[phases]
P1: Write the sensor driver
P2: Implement the packet encoder
P3: Build the uplink scheduler
P4: Run the salt spray test

[phase_order]
P1 -> P2: The encoder reads what the driver produces
P2 -> P3: The scheduler sends encoded packets
P1 -> P4: The test needs a working driver

[decisions]
D1: radio band => 868 MHz
D2: logging format => binary frames
D3: SCOPE | on-board averaging | in scope
D4: CONFIRM | running the dockside simulator | permitted
D5: CONFIRM | flashing a field unit | not permitted
D6: CHOICE | encoder library | zero-copy encoder

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
publish a firmware image => A public image needs approval => human

[forbidden_actions]
overwrite raw readings => Readings are never rewritten
"""

JA_FRAME = """# 図書館の貸出アプリ（日本語）
[goal]
project: 図書貸出アプリ
statement: 図書館の貸出と返却を画面から記録できるようにする

[philosophy_invariants]
I1: 利用者の連絡先は画面の外に出さない

[completion_criteria]
C1: 貸出の記録が合うことを確認する | {"kind":"command_exit","command":["make","check"],"expected_exit":0}
C2: 返却の手順が分かりやすい | human-judged

[phases]
P1: 利用者の登録形式を決める
P2: 貸出の画面を作る
P3: 返却の通知を実装する
P4: 受入確認をする

[phase_order]
P1 -> P2: 画面は登録形式が決まってから作る
P2 -> P3: 通知は画面の動作を前提にする
P3 -> P4: 受入確認は通知がそろってから行う

[decisions]
D1: 保存形式 => SQLite
D2: SCOPE | 貸出履歴の書き出し | in scope
D3: CONFIRM | 館内での試験運用 | permitted
D4: CONFIRM | 本番の貸出データを使った試験 | not permitted
D5: CHOICE | 日付の表記 | 西暦

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
利用者の連絡先を公開する => 個人情報の公開には人間の承認が必要 => 人間
"""


@pytest.fixture(scope="module")
def frames(tmp_path_factory):
    d = tmp_path_factory.mktemp("traps")
    en, ja = d / "buoy.md", d / "library.md"
    en.write_text(EN_FRAME, encoding="utf-8")
    ja.write_text(JA_FRAME, encoding="utf-8")
    return str(en), str(ja)


def ask(frame, q, opts=None):
    return conduct_ask.answer_question(frame, q, opts)


def assert_escalates(res, *reasons):
    assert res["decision"] == "escalate", (res["answer"], res["basis"])
    assert res["answer"] is None and res["answer_option_index"] is None
    if reasons:
        assert res["escalate_reason"] in reasons, (res["escalate_reason"], res["escalate_detail"])


# ---------------------------------------------------------------- M1: "is permission needed?" is not "may we?"

M1_EN = [
    "Is permission required for running the dockside simulator?",
    "Do we need permission before running the dockside simulator?",
    "Is approval needed for flashing a field unit?",
    "Does running the dockside simulator require authorization?",
    "Is sign-off necessary to flash a field unit?",
]
M1_JA = [
    "館内での試験運用には許可が必要ですか？",
    "館内での試験運用には許可を取る必要がありますか？",
    "本番の貸出データを使った試験には許可が要りますか？",
    "本番の貸出データを使った試験は承認が必要ですか？",
    "館内での試験運用には事前の承認がいりますか？",
]


@pytest.mark.parametrize("q", M1_EN)
def test_m1_english_requirement_of_permission_is_handed_up(frames, q):
    res = ask(frames[0], q, H.YN_EN)
    assert_escalates(res, "QUESTION_UNREADABLE")
    assert res["escalate_detail"] == "REQUIREMENT_OF_PERMISSION"


@pytest.mark.parametrize("q", M1_JA)
def test_m1_japanese_requirement_of_permission_is_handed_up(frames, q):
    res = ask(frames[1], q, H.YN_JA)
    assert_escalates(res, "QUESTION_UNREADABLE")
    assert res["escalate_detail"] == "REQUIREMENT_OF_PERMISSION"


def test_m1_also_without_options_and_without_a_frame_term(frames):
    assert_escalates(ask(frames[0], "Is permission required for running the dockside simulator?"))
    assert_escalates(ask(frames[0], "Do we need permission to restart the whole bench?", H.YN_EN))
    assert_escalates(ask(frames[1], "館内での試験運用に許可は必要ですか？"))


def test_m1_the_real_permission_questions_still_answer(frames):
    res = ask(frames[0], "Can we run the dockside simulator?", H.YN_EN)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(frames[0], "Is it allowed to flash a field unit?", H.YN_EN)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 1)
    res = ask(frames[1], "館内での試験運用をしてもよいですか？", H.YN_JA)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(frames[1], "本番の貸出データを使った試験をしてよいですか？承認はもらいました。", H.YN_JA)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 1)


# ---------------------------------------------------------------- M2: the predicate must be a "may we?" / "include?"

M2_ORDER_EN = [
    "Is it too early to start the salt spray test before the sensor driver is written?",
    "Would it be a mistake to start the salt spray test before the sensor driver is written?",
    "Is it risky to start the salt spray test before the sensor driver is written?",
    "Is it wrong to start the salt spray test before the sensor driver is written?",
    "Is it a bad idea to begin the uplink scheduler before the packet encoder is implemented?",
]
M2_ORDER_JA = [
    "利用者の登録形式を決める前に貸出の画面を作るのは早すぎますか？",
    "利用者の登録形式を決める前に貸出の画面を作るのは危険ですか？",
    "利用者の登録形式を決める前に貸出の画面を作るのは誤りですか？",
    "貸出の画面を作る前に返却の通知を実装するのは問題が大きいですか？",
]
M2_SCOPE_EN = [
    "Is it wrong to include on-board averaging?",
    "Is it a mistake to include on-board averaging?",
    "Is it risky to put on-board averaging in scope?",
    "Would it be too early to include on-board averaging?",
]
M2_SCOPE_JA = [
    "貸出履歴の書き出しを範囲に含めるのは誤りですか？",
    "貸出履歴の書き出しを範囲に含めるのは早すぎますか？",
    "貸出履歴の書き出しを対象に入れるのは危険ですか？",
]


@pytest.mark.parametrize("q", M2_ORDER_EN)
def test_m2_order_with_an_evaluative_predicate_is_handed_up(frames, q):
    res = ask(frames[0], q, H.YN_EN)
    assert_escalates(res)


@pytest.mark.parametrize("q", M2_ORDER_JA)
def test_m2_order_with_an_evaluative_predicate_is_handed_up_ja(frames, q):
    assert_escalates(ask(frames[1], q, H.YN_JA))


@pytest.mark.parametrize("q", M2_SCOPE_EN)
def test_m2_scope_with_an_evaluative_predicate_is_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, H.YN_EN))


@pytest.mark.parametrize("q", M2_SCOPE_JA)
def test_m2_scope_with_an_evaluative_predicate_is_handed_up_ja(frames, q):
    assert_escalates(ask(frames[1], q, H.YN_JA))


def test_m2_scope_evaluative_without_options_is_handed_up_too(frames):
    assert_escalates(ask(frames[0], "Is it wrong to include on-board averaging?"))
    assert_escalates(ask(frames[1], "貸出履歴の書き出しを範囲に含めるのは誤りですか？"))


def test_m2_the_plain_predicates_still_answer(frames):
    en, ja = frames
    res = ask(en, "Can the salt spray test start before the sensor driver is written?", H.YN_EN)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 1)
    res = ask(en, "May we start the sensor driver before the salt spray test is run?", H.YN_EN)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(en, "Is on-board averaging in scope?", H.YN_EN)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(en, "Do we include on-board averaging?", H.YN_EN)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(ja, "利用者の登録形式を決める前に貸出の画面を作ってもよいですか？", H.YN_JA)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 1)
    res = ask(ja, "貸出履歴の書き出しは範囲に含めますか？", ["含める", "含めない"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(ja, "貸出履歴の書き出しは範囲外ですか？", H.YN_JA)
    assert (res["decision"], res["answer_option_index"]) == ("answer", 1)


# ---------------------------------------------------------------- M3: a modifier to the LEFT is a different subject

M3_EN = [
    ("Which backup logging format do we use?", ["binary frames", "text lines"]),
    ("Which secondary logging format do we use?", None),
    ("Which spare encoder library should we pick?", ["zero-copy encoder", "copying encoder"]),
    ("Which legacy radio band should we use?", ["868 MHz", "915 MHz"]),
    ("What is the per-site radio band?", None),
    ("Which experimental encoder library do we adopt?", ["zero-copy encoder", "copying encoder"]),
]
M3_JA = [
    ("予備の保存形式はどれにしますか？", ["SQLite", "CSV"]),
    ("バックアップの保存形式はどれにしますか？", ["SQLite", "CSV"]),
    ("試作の保存形式はどれにしますか？", ["SQLite", "CSV"]),
    ("海外版の日付の表記はどれにしますか？", ["西暦", "和暦"]),
]


@pytest.mark.parametrize("q,opts", M3_EN)
def test_m3_english_left_modifier_is_not_the_frame_subject(frames, q, opts):
    assert_escalates(ask(frames[0], q, opts))


@pytest.mark.parametrize("q,opts", M3_JA)
def test_m3_japanese_left_modifier_is_not_the_frame_subject(frames, q, opts):
    assert_escalates(ask(frames[1], q, opts))


def test_m3_questions_without_a_modifier_still_answer(frames):
    en, ja = frames
    res = ask(en, "Which logging format do we use?", ["binary frames", "text lines"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(en, "Which radio band do we use?")
    assert res["decision"] == "answer" and res["answer"] == "868 MHz"
    res = ask(en, "Which encoder library should we pick?", ["copying encoder", "zero-copy encoder"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 1)
    res = ask(ja, "今回の保存形式はどれにしますか？", ["SQLite", "CSV"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(ja, "保存形式はどれにしますか？", ["SQLite", "CSV"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)
    res = ask(ja, "この日付の表記はどれにしますか？", ["西暦", "和暦"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)


def test_m3_the_left_modifier_rule_does_not_depend_on_which_frame(frames, tmp_path):
    # the same words in a frame whose subject is spelled differently: only the structure counts
    p = tmp_path / "other.md"
    p.write_text(EN_FRAME.replace("radio band => 868 MHz", "carrier plan => narrow band"), encoding="utf-8")
    assert_escalates(ask(str(p), "Which fallback carrier plan do we use?", ["narrow band", "wide band"]))
    res = ask(str(p), "Which carrier plan do we use?", ["narrow band", "wide band"])
    assert (res["decision"], res["answer_option_index"]) == ("answer", 0)


# ---------------------------------------------------------------- more variants found while fixing (not from the bank)

@pytest.mark.parametrize("q", [
    "Could it be a mistake to start the salt spray test before the sensor driver is written?",
    "Can it hurt to start the salt spray test before the sensor driver is written?",
    "Should we worry if the salt spray test starts before the sensor driver is written?",
    "Is it safe to start the salt spray test before the sensor driver is written?",
    "Can we start the salt spray test before the sensor driver is written, or is that too early?",
])
def test_more_english_order_predicates_are_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, H.YN_EN))


@pytest.mark.parametrize("q", [
    "Is on-board averaging in scope or a mistake?",
    "Is it too early to say whether on-board averaging is in scope?",
    "Is on-board averaging in scope, or is that wrong?",
])
def test_more_english_scope_predicates_are_handed_up(frames, q):
    assert_escalates(ask(frames[0], q, H.YN_EN))


def test_a_second_question_with_another_predicate_is_not_answered_by_the_first(frames):
    res = ask(frames[1], "利用者の登録形式を決める前に貸出の画面を作ってもよいですか？それとも早すぎますか？", H.YN_JA)
    assert_escalates(res, "QUESTION_UNREADABLE")
    assert res["escalate_detail"] == "MULTIPLE_QUESTIONS"
    res = ask(frames[0], "Is on-board averaging in scope? Or is it a mistake?", H.YN_EN)
    assert_escalates(res, "QUESTION_UNREADABLE")


def test_variants_of_may_we_still_answer(frames):
    en, ja = frames
    for q, idx in [("Is it OK to start the salt spray test before the sensor driver is written?", 1),
                   ("Are we allowed to start the salt spray test before the sensor driver is written?", 1),
                   ("May the salt spray test begin before the sensor driver is written?", 1),
                   ("Is the salt spray test allowed to start before the sensor driver is written?", 1),
                   ("Is on-board averaging in scope for this release?", 0),
                   ("Should we put on-board averaging in scope?", 0)]:
        res = ask(en, q, H.YN_EN)
        assert (res["decision"], res["answer_option_index"]) == ("answer", idx), q
    for q, idx in [("貸出履歴の書き出しは範囲に含まれますか？", 0), ("貸出履歴の書き出しは今回の範囲に入りますか？", 0)]:
        res = ask(ja, q, H.YN_JA)
        assert (res["decision"], res["answer_option_index"]) == ("answer", idx), q


# ---------------------------------------------------------------- the small review items (optional 1 and 4)

def test_an_unreadable_fake_script_is_refused_even_when_the_question_never_reaches_the_vocabulary_route(frames, capsys):
    code = conduct_ask.main(["--frame", frames[0], "--question", "Is it fine?", "--vocab-llm", "fake",
                             "--vocab-fake", "/nonexistent/script.json"])
    out = capsys.readouterr().out
    import json as _json
    res = _json.loads(out)
    assert code == 2 and res["escalate_reason"] == "QUESTION_UNREADABLE" and res["escalate_detail"] == "VOCAB_SCRIPT_UNUSABLE"


def test_a_jsonl_acceptance_record_without_the_human_judged_mark_is_unknown_not_human_judged(tmp_path):
    import json as _json
    from verantyx.memory_frame import Memory
    from verantyx.project_frame import compile_frame, load_conduct_frame, load_frame
    full = tmp_path / "full.jsonl"
    compile_frame(load_frame(H.FRAMES / "f05_retry.md"), Memory(str(full)))   # an English fixture that compiles
    marks = [c.human for c in conduct_ask.build_view(load_conduct_frame(full)).criteria]
    assert marks and all(isinstance(m, bool) for m in marks)                    # the mark is written: known
    stripped = tmp_path / "stripped.jsonl"
    lines = []
    for ln in full.read_text(encoding="utf-8").splitlines():
        ev = _json.loads(ln)
        wit = ((ev.get("record") or {}).get("witness") or {})
        if isinstance(wit.get("acceptance"), dict):
            wit["acceptance"].pop("human_judged", None)
        lines.append(_json.dumps(ev, ensure_ascii=False))
    stripped.write_text("\n".join(lines) + "\n", encoding="utf-8")
    marks = [c.human for c in conduct_ask.build_view(load_conduct_frame(stripped)).criteria]
    assert marks and all(m is None for m in marks)                              # no mark: unknown, never "human-judged"

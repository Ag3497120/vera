"""MEM-d tests: UPDATES (owner 2026-10-13 「更新と矛盾」: 構造は検知し、モデルが「置き換え」操作で解決する).

SAME_QUESTION always fires; the model may resolve it with ONE explicit `supersede` row; recall then answers with the newest as ANSWER and lists the superseded sentences as
`history` (never deleted); unresolved stays CHOICE; a supersede must name an existing contested group (typed refusals otherwise, nothing changes).  Nothing is decided by order."""
import json

import pytest

from verantyx.loom import evidence as ev
from verantyx.loom import memory as mem
from verantyx.loom import memrecall as mr
from mem_common import ledger_rows, new_store, notes_of, refusal_of, session_v2, write_all

PEOPLE = ["田中の担当は認証", "認証の期限は金曜", "田中の担当は決済"]            # sid 0, 1, 2


def sup(s, **a):
    return s.call("supersede", a)


def sq(res):
    return [n for n in res.get("notes", []) if n["type"] == "SAME_QUESTION"]


def answers(s, q="田中の担当は何ですか"):
    r = s.call("recall", {"question": q})
    return r["verdict"], [g["answers"] for g in r["answers"]], r


def test_same_question_always_fires_even_when_the_text_says_it_changed(tmp_path):
    s = session_v2(tmp_path)
    s.write("サーバーのポートは8080")
    r = s.write("サーバーのポートは9090")                                # a model might write "変更"; the structure does not read markers
    assert len(sq(r)) == 1 and sq(r)[0]["counted"] is True and [v["answers"] for v in sq(r)[0]["variants"]] == [["8080"], ["9090"]]
    assert s.events()["detections"]["notes"] == 1


def test_unresolved_stays_a_choice_and_supersede_resolves_it_with_the_newest(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    v, a, _ = answers(s)
    assert v == "CHOICE" and a == [["認証"], ["決済"]]
    r = sup(s, new_sid=2, old_sid=0, reason="変更")
    assert r["ok"] and r["question"] == "田中の担当は何ですか" and r["verdict_after"] == "ANSWER" and r["answers_after"] == ["決済"]
    assert [x["sid"] for x in r["superseded"]] == [0] and r["history"][0]["superseded_by"] == {"sid": 2, "reason": "変更", "session": 1}
    v, a, full = answers(s)
    assert v == "ANSWER" and a == [["決済"]]
    h = full["history"]
    assert len(h) == 1 and h[0]["answers"] == ["認証"] and h[0]["occurrences"][0]["superseded_by"]["sid"] == 2 and h[0]["occurrences"][0]["sid"] == 0
    assert len(s.run.rows) == 3 and s.run.rows[0]["sent"] == "田中の担当は認証"           # nothing is deleted


def test_old_answer_text_names_the_old_group_and_the_whole_group_is_replaced(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, ["田中の担当は認証", "田中の担当は認証", "田中の担当は決済"])        # the old answer is stated twice
    r = sup(s, new_sid=2, old_answer="認証", reason="変更")
    assert r["ok"] and [x["sid"] for x in r["superseded"]] == [0, 1] and set(s.run.superseded) == {0, 1}
    assert answers(s)[:2] == ("ANSWER", [["決済"]])


def test_the_newest_is_what_the_model_says_not_what_came_last(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    assert sup(s, new_sid=0, old_sid=2, reason="訂正")["ok"]            # the EARLIER sentence replaces the later one: order never makes a winner
    assert answers(s)[:2] == ("ANSWER", [["認証"]])


def test_a_chain_and_a_third_value(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    assert sup(s, new_sid=2, old_sid=0, reason="変更")["ok"]
    r = s.write("田中の担当は佐藤")                                       # a third statement: SAME_QUESTION over the LIVE ones only (the history does not contest)
    assert [v["answers"] for v in sq(r)[0]["variants"]] == [["決済"], ["佐藤"]]
    assert answers(s)[:2] == ("CHOICE", [["決済"], ["佐藤"]])
    assert sup(s, new_sid=3, old_sid=2, reason="変更")["ok"]
    v, a, full = answers(s)
    assert (v, a) == ("ANSWER", [["佐藤"]]) and sorted(o["sid"] for g in full["history"] for o in g["occurrences"]) == [0, 2]
    assert refusal_of(sup(s, new_sid=3, old_sid=0, reason="x")) == "already_superseded"
    assert refusal_of(sup(s, new_sid=2, old_sid=3, reason="x")) == "new_superseded"


def test_writing_the_old_value_again_after_a_supersede_contests_it_again(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    sup(s, new_sid=2, old_sid=0, reason="変更")
    r = s.write("田中の担当は認証")                                       # sid 3: a NEW statement of the old value
    assert [v["answers"] for v in sq(r)[0]["variants"]] == [["決済"], ["認証"]] and [o["sid"] for v in sq(r)[0]["variants"] for o in v["occurrences"]] == [2, 3]
    v, a, full = answers(s)
    assert v == "CHOICE" and sorted(a) == [["決済"], ["認証"]]                   # groups are listed by their smallest sid (a determinism rule, not a rank)
    assert [o["sid"] for o in full["history"][0]["occurrences"]] == [0] and sorted(o["sid"] for g in full["answers"] for o in g["occurrences"]) == [2, 3]     # sid 0 stays history, sid 3 is live


def test_typed_refusals_name_what_is_wrong_and_change_nothing(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE + ["サーバーのポートは8080", "東京の会議"])      # sid 3, 4
    before = (dict(s.run.superseded), len(s.run.rows))
    cases = [
        (dict(new_sid=2, reason="x"), "bad_args"),                          # neither old_sid nor old_answer
        (dict(new_sid=2, old_sid=0, old_answer="認証", reason="x"), "bad_args"),
        (dict(new_sid=2, old_sid=0, reason=""), "bad_reason"),
        (dict(new_sid=2, old_sid=0, reason="x" * 41), "bad_reason"),
        (dict(new_sid=99, old_sid=0, reason="x"), "unknown_sid"),
        (dict(new_sid=2, old_sid=-1, reason="x"), "unknown_sid"),
        (dict(new_sid=3, old_sid=0, reason="x"), "not_an_answer"),          # the port sentence is not an answer group of 田中の担当 ... the old sentence is not in new's question
        (dict(new_sid=2, old_sid=1, reason="x"), "not_an_answer"),          # 認証の期限 answers another question
        (dict(new_sid=2, old_answer="佐藤", reason="x"), "unknown_answer"),
        (dict(new_sid=2, old_answer="決済", reason="x"), "same_group"),
        (dict(new_sid=2, old_sid=2, reason="x"), "same_group"),
        (dict(new_sid=4, old_sid=0, reason="x"), "no_self_question"),       # 「東京の会議」 has no 「Y は A」 clause at all
    ]
    for args, want in cases:
        r = sup(s, **args)
        assert r["ok"] is False and r["refusal"] == want, (args, r)
    assert sup(s, new_sid=2, old_answer="佐藤", reason="x")["detail"]["answers"] == ["決済", "認証"]
    assert (dict(s.run.superseded), len(s.run.rows)) == before
    ev_ = s.events()["supersedes"]
    assert ev_["ok"] == 0 and sum(ev_["refused"].values()) == len(cases) + 1


def test_a_question_can_be_given_when_the_sentence_has_no_self_question(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, ["会議は東京で開きます", "会議は大阪で開きます"])
    assert refusal_of(sup(s, new_sid=1, old_sid=0, reason="変更")) in ("no_self_question", "not_an_answer")
    r = sup(s, new_sid=1, old_sid=0, reason="変更", question="会議はどこで開きますか")
    assert r["ok"] and r["verdict_after"] == "ANSWER" and r["answers_after"] == ["大阪"]
    assert refusal_of(sup(s, new_sid=1, old_sid=0, reason="x", question="")) == "bad_question"


def test_supersede_needs_a_gate_in_the_session(tmp_path):
    s = session_v2(tmp_path, self_question=None)
    s.write("田中の担当は認証")
    assert refusal_of(sup(s, new_sid=0, old_sid=0, reason="x")) == "supersede_unavailable"


def test_caps_of_the_new_ops(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    s.run.counts2["supersedes"] = 30
    assert refusal_of(sup(s, new_sid=2, old_sid=0, reason="x")) == "supersede_cap"
    s.run.counts2["reports"] = 60
    assert refusal_of(s.call("report", {"turn": "1-1", "contradictions": []})) == "report_cap"


def test_supersede_survives_the_session_and_replays(tmp_path):
    st = new_store(tmp_path)
    a = st.begin("m", profile=mem.PROFILE_V2)
    write_all(a, PEOPLE)
    sup(a, new_sid=2, old_sid=0, reason="変更")
    a.commit()
    assert mem.session_supersedes(str(tmp_path / "mem" / "sessions" / "s0001")) == {0: {"by": 2, "reason": "変更", "session": 1}}
    b = st.begin("m", profile=mem.PROFILE_V2)
    assert b.run.superseded == {0: {"by": 2, "reason": "変更", "session": 1}}
    v, ans, full = answers(b)
    assert (v, ans) == ("ANSWER", [["決済"]]) and full["history"][0]["occurrences"][0]["superseded_by"]["session"] == 1
    r = b.write("田中の担当は鈴木")                                       # a later session contests the live answer only
    assert [v_["answers"] for v_ in sq(r)[0]["variants"]] == [["決済"], ["鈴木"]]
    assert sup(b, new_sid=3, old_sid=2, reason="変更")["session"] == 2
    b.commit()
    v = mem.verify_store(str(tmp_path / "mem"))
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"


def test_a_forged_supersede_result_is_a_replay_difference(tmp_path):
    st = new_store(tmp_path)
    a = st.begin("m", profile=mem.PROFILE_V2)
    write_all(a, PEOPLE)
    sup(a, new_sid=2, old_sid=0, reason="変更")
    a.commit()
    from verantyx.loom import ledger as lg
    d = tmp_path / "mem" / "sessions" / "s0001"
    rows = [json.loads(ln) for ln in open(d / "ops.jsonl", encoding="utf-8")]
    k = [r["op"] for r in rows].index("supersede")
    rows[k]["result"]["verdict_after"] = "CHOICE"                      # claims the supersede did not resolve it
    prev = rows[k - 1]["sha"]
    out = []
    for r in rows:
        if r["i"] >= k:
            r["prev"] = prev
            r["sha"] = lg.row_sha(r)
            prev = r["sha"]
        out.append(lg.line_of(r))
    (d / "ops.jsonl").write_bytes(b"".join(out))
    (d / "HEAD").write_text(prev + "\n")
    v = mem.verify_store(str(tmp_path / "mem"))
    assert v["status"] in ("STORE_UNVERIFIED", "REPLAY_DIFFERS", "TAMPERED")


# -- the reader itself ------------------------------------------------------------------------------------------------------------------------
def test_recall_without_supersession_is_byte_identical_to_the_old_recall(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    base = mr.recall(s.run.corpus_cur, "田中の担当は何ですか", ev.EVIDENCE_V2, subject_guard=True)
    assert mr.recall(s.run.corpus_cur, "田中の担当は何ですか", ev.EVIDENCE_V2, subject_guard=True, superseded={}) == base
    assert mr.recall(s.run.corpus_cur, "田中の担当は何ですか", ev.EVIDENCE_V2, subject_guard=True, superseded={1: {"by": 2, "reason": "x", "session": 1}}) == base    # a mark elsewhere changes nothing here
    assert "history" not in base


def test_every_sentence_superseded_falls_back_to_showing_them_all(tmp_path):
    s = session_v2(tmp_path)
    write_all(s, PEOPLE)
    marks = {0: {"by": 2, "reason": "x", "session": 1}, 2: {"by": 0, "reason": "x", "session": 1}}      # cannot happen through the op (new must be live): the reader still hides nothing
    r = mr.recall(s.run.corpus_cur, "田中の担当は何ですか", ev.EVIDENCE_V2, subject_guard=True, superseded=marks)
    assert r["verdict"] == "CHOICE" and r["superseded_all"] is True and len(r["answers"]) == 2 and len(r["history"]) == 2


def test_the_turn_a_sentence_was_written_at_comes_back_in_recall_notes_and_supersede(tmp_path):
    s = session_v2(tmp_path)
    s.write("田中の担当は認証")
    r = s.call("write", {"text": "田中の担当は決済", "turn": "1-4"})
    assert r["turn"] == "1-4" and s.run.rows[1]["turn"] == "1-4" and "turn" not in s.run.rows[0]
    assert [o.get("turn") for v in sq(r)[0]["variants"] for o in v["occurrences"]] == [None, "1-4"]
    _, _, full = answers(s)
    assert [o.get("turn") for g in full["answers"] for o in g["occurrences"]] == [None, "1-4"]
    assert refusal_of(s.call("write", {"text": "田中の担当は鈴木", "turn": "x"})) == "bad_turn"
    assert sup(s, new_sid=1, old_sid=0, reason="変更")["ok"]

"""MEM-d tests: the session TOPIC and the form guidance (owner 2026-10-13, ops/decisions/2026-10-06_line3_faithful_build.md 「記憶の計器の前の決定」: 読める文の形, 主語の無い文).

What is under test: `declare_topic(text)` is a ledger row of a `mem.v2` session; a SUBJECT-LESS sentence (its clause is 「Y は A」 with no 「X の」) is stored with the topic in front
(「<topic>の締め切りは水曜」), the expansion is recorded in the row (`implicit_topic`, memory.jsonl `topic_at`), recall and the self-question use the expanded sentence and the whole
topic (not the word-cut tail of it), the cut-subject guard still applies to it, the rewrite cost counter counts refused-then-rewritten sentences, and none of it exists in a `mem.v1`
session (the default of the API), whose begin row and bytes are exactly the pre-MEM-d ones."""
import json
import os

import pytest

from verantyx.loom import memguard as mg
from verantyx.loom import memnotes as mn
from verantyx.loom import memory as mem
from mem_common import ledger_rows, new_store, notes_of, refusal_of, session, session_v2, write_all



T = "広報"


def clause_q(res):
    return res["clause"]["question"]


# -- the profile ---------------------------------------------------------------------------------------------------------------------------
def test_v1_is_the_default_and_has_none_of_the_new_ops(tmp_path):
    s = session(tmp_path)
    b = ledger_rows(s)[0]["result"]
    assert "mem_profile" not in b["header"] and "tools" not in b and set(b["rules"]) == set(mem.MEM_RULES_GATE)
    assert b["task"]["caps"] == mem.CAPS_MEM_V1 and s.run.profile == mem.PROFILE_V1
    for op in ("declare_topic", "supersede", "report"):
        r = s.call(op, {"text": "x"} if op == "declare_topic" else {})
        assert r["ok"] is False and r["refusal"] == "unknown_tool", op
    assert refusal_of(s.call("write", {"text": "広報の期限は水曜", "turn": "1-1"})) == "bad_args"          # a v1 write takes no turn


def test_v2_begin_row_records_the_profile_the_tools_and_the_form(tmp_path):
    s = session_v2(tmp_path)
    b = ledger_rows(s)[0]["result"]
    assert b["header"]["mem_profile"] == "mem.v2" and b["tools"] == list(mem.tools_of(mem.PROFILE_V2))
    assert b["tools"] == ["write", "recall", "lookup", "read_sentence", "status", "commit", "declare_topic", "supersede", "report"]
    assert b["task"]["caps"] == mem.CAPS_MEM_V2 and mem.CAPS_MEM_V2["reports"] == 60 and mem.CAPS_MEM_V2["supersedes"] == 30 and mem.CAPS_MEM_V2["topics"] == 8
    r = b["rules"]
    assert "「X の Y は A」" in r["form"] and "REFUSED" not in r["write"] and "rewrite" in r["write"] and "counted as cost" in r["write"]
    assert set(r) >= {"topic", "supersede", "report", "form"} and "evidence.v2" in r["recall"] and "history" in r["recall"]
    # a v2 session of a store with no hook has no gate text but keeps the v2 rules
    s2 = session_v2(tmp_path, "nohook", self_question=None)
    b2 = ledger_rows(s2)[0]["result"]
    assert b2["rules"]["recall"] == mem.MEM_RULES["recall"] and "form" in b2["rules"]


# -- declare_topic ---------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["", "あ" * 25, "x\ny", " 広報", "広報 ", "広報の", "広報、", "。。", "広報は"])
def test_declare_topic_refuses_what_cannot_be_a_noun_phrase(tmp_path, text):
    s = session_v2(tmp_path)
    r = s.call("declare_topic", {"text": text})
    assert r["ok"] is False and r["refusal"] == "bad_topic" and s.run.topic is None


def test_declare_topic_is_a_row_and_can_be_declared_again(tmp_path):
    s = session_v2(tmp_path)
    r = s.call("declare_topic", {"text": T})
    assert r["ok"] is True and (r["topic"], r["previous"], r["at_start"], r["form"]) == (T, None, True, "広報の<Y>は<A>") and r["units"] == ["広報"]
    s.write("備品の期限は水曜")
    r2 = s.call("declare_topic", {"text": "経理"})
    assert (r2["previous"], r2["at_start"]) == (T, False) and s.run.topic == "経理"
    rows = ledger_rows(s)
    assert [(x["op"], x["result"].get("topic")) for x in rows if x["op"] == "declare_topic"] == [("declare_topic", T), ("declare_topic", "経理")]
    assert s.status()["topic"] == "経理" and s.status()["topics"] == 2


def test_the_topic_belongs_to_the_session_and_is_not_carried(tmp_path):
    st = new_store(tmp_path)
    a = st.begin("m", profile=mem.PROFILE_V2)
    a.call("declare_topic", {"text": T})
    a.write("締め切りは水曜")
    a.commit()
    b = st.begin("m", profile=mem.PROFILE_V2)
    assert b.run.topic is None
    r = b.write("締め切りは木曜")                                      # no topic declared in THIS session: stored as written, the gate cannot read it
    assert "implicit_topic" not in r and r["text"] == "締め切りは木曜" and notes_of(r) == ["SELF_QUESTION_UNREADABLE"]


def test_topic_cap_counts_refused_declarations_too(tmp_path):
    s = session_v2(tmp_path)
    for _ in range(8):
        s.call("declare_topic", {"text": "。"})
    assert refusal_of(s.call("declare_topic", {"text": T})) == "topic_cap"


# -- the expansion --------------------------------------------------------------------------------------------------------------------------
def test_a_subject_less_sentence_is_stored_with_the_topic_as_its_subject(tmp_path):
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    r = s.write("締め切りは水曜")
    assert r["ok"] and r["text"] == "広報の締め切りは水曜" and r["implicit_topic"] == {"topic": T, "at": 0, "written": "締め切りは水曜"}
    assert clause_q(r) == "広報の締め切りは何ですか" and "SELF_QUESTION_UNREADABLE" not in notes_of(r)
    assert s.run.rows[0]["sent"] == "広報の締め切りは水曜" and s.run.rows[0]["topic_at"] == 0
    # the ledger row keeps what the model WROTE (args) beside what was STORED (result): the expansion is in the row
    row = [x for x in ledger_rows(s) if x["op"] == "write"][0]
    assert row["args"]["text"] == "締め切りは水曜" and row["result"]["text"] == "広報の締め切りは水曜"
    q = s.call("recall", {"question": "広報の締め切りは何ですか"})
    assert q["verdict"] == "ANSWER" and q["answers"][0]["text"] == "水曜" and q["answers"][0]["occurrences"][0]["sid"] == 0
    s.commit()
    memory = [json.loads(ln) for ln in open(os.path.join(str(tmp_path), "mem", "memory.jsonl"), encoding="utf-8")]
    assert memory == [{"kind": "base", "sent": "広報の締め切りは水曜", "source": "mem:t/1#0", "topic_at": 0}]


def test_a_lead_in_stays_and_the_topic_goes_before_the_clause(tmp_path):
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    r = s.write("メモ、締め切りは水曜")
    assert r["text"] == "メモ、広報の締め切りは水曜" and r["implicit_topic"]["at"] == 3 and clause_q(r) == "広報の締め切りは何ですか"
    assert s.call("recall", {"question": "広報の締め切りは何ですか"})["verdict"] == "ANSWER"


def test_the_topic_goes_before_the_whole_written_token_never_inside_it(tmp_path):
    """新規|締め切り: the clause starts at 締め切り, which sits inside the written token 新規締め切り: the topic is put before the token, so the subject stays whole (the MEM-c2 rule)."""
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    r = s.write("新規締め切りは水曜")
    assert r["text"] == "広報の新規締め切りは水曜" and r["implicit_topic"]["at"] == 0 and clause_q(r) == "広報の新規締め切りは何ですか"
    assert "SELF_QUESTION_UNREADABLE" not in notes_of(r)


def test_a_compound_topic_is_asked_whole_not_as_its_word_cut_tail(tmp_path):
    """認証機能 = 認証 + 機能 for the word cut: the clause cut alone would ask 「機能の締め切りは何ですか」 (and the guard would refuse it); the expansion asks the whole topic."""
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": "認証機能"})
    r = s.write("締め切りは水曜")
    assert r["text"] == "認証機能の締め切りは水曜" and clause_q(r) == "認証機能の締め切りは何ですか" and "SELF_QUESTION_UNREADABLE" not in notes_of(r)
    assert s.call("recall", {"question": "認証機能の締め切りは何ですか"})["answers"][0]["text"] == "水曜"


def test_a_sentence_with_its_own_subject_and_a_sentence_without_a_clause_are_left_alone(tmp_path):
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    for text in ("経理の締め切りは月曜", "東京で会議を開く"):
        r = s.write(text)
        assert "implicit_topic" not in r
        assert (r["ok"] and r["text"] == text) or r["refusal"] == "span_inexpressible"
    assert [x["sent"] for x in s.run.rows] == ["経理の締め切りは月曜"]


def test_a_refused_subject_less_sentence_is_refused_as_written_and_changes_nothing(tmp_path):
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    before = s.run.mem_state_sha()
    r = s.write("東京で会議を開く")
    assert r["ok"] is False and r["refusal"] == "span_inexpressible" and len(s.run.rows) == 0 and s.run.starts == {}
    st = s.run.state
    assert len(st.units) == 0 and len(st.crosses) == 0 and s.run._nweaves == 0 and s.run.weaves == []           # the probe left no trace (it ran in a throw-away state)
    assert s.run.mem_state_sha() != before                                                                       # only the counters of the refused call moved


def test_the_probe_leaves_the_state_and_the_weave_counter_as_a_plain_write_would(tmp_path):
    a = session_v2(tmp_path, "a")
    a.call("declare_topic", {"text": T})
    b = session_v2(tmp_path, "b")                                       # no topic: no probe at all
    for sess in (a, b):
        sess.write("広報の期限は水曜")
        sess.write("経理の担当は山本")
    assert a.run.state.to_obj() == b.run.state.to_obj() and a.run._nweaves == b.run._nweaves == 2
    a.write("備品の締め切りは月曜")
    assert a.run._nweaves == 3                                          # the expansion probe did not advance the counter that real quotes carry


def test_the_self_question_of_an_expanded_sentence_finds_the_contradiction_across_sessions(tmp_path):
    st = new_store(tmp_path)
    a = st.begin("m", profile=mem.PROFILE_V2)
    a.call("declare_topic", {"text": T})
    a.write("締め切りは水曜")
    a.commit()
    b = st.begin("m", profile=mem.PROFILE_V2)
    b.call("declare_topic", {"text": T})
    r = b.write("締め切りは金曜")
    n = [x for x in r["notes"] if x["type"] == "SAME_QUESTION"]
    assert len(n) == 1 and n[0]["counted"] is True and n[0]["question"] == "広報の締め切りは何ですか"
    assert [v["answers"] for v in n[0]["variants"]] == [["水曜"], ["金曜"]] and [o["sid"] for v in n[0]["variants"] for o in v["occurrences"]] == [0, 1]
    assert b.run.clause_of(0)["question"] == "広報の締め切りは何ですか"            # sentence 0 is a CARRIED one: its topic_at came back from the memory row
    assert s_events(b)["detections"]["notes"] == 1


def s_events(sess):
    return sess.events()


def test_the_cut_subject_guard_still_applies_to_an_expanded_sentence(tmp_path):
    """The guard is part of the hook, not of the expansion: the same expanded sentence under the OLD gate hook (no guard) and under the default (guard) is read the same when the subject is
    whole; and a topic whose own text begins mid-token inside the sentence cannot be put there: the lead-in word cut is walked back, so the guard has nothing to refuse."""
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    assert "SELF_QUESTION_UNREADABLE" not in notes_of(s.write("締め切りは水曜"))
    # a hook WITH the guard is asked about the expanded subject like about any other (the begin row says which hook it is)
    assert ledger_rows(s)[0]["result"]["header"]["self_question"] == "gate.evidence.v2+subject" and s.run.hook.subject_guard is True
    # a written subject that IS cut (fmt|num) is still UNREADABLE with its reason, in a v2 session
    s.call("declare_topic", {"text": "関数"})
    r = s.write("fmt_numの戻り値は文字列")
    assert [(n["type"], n.get("reason")) for n in r["notes"] if n["type"] == "SELF_QUESTION_UNREADABLE"] == [("SELF_QUESTION_UNREADABLE", "subject_cut")] and "implicit_topic" not in r


# -- form guidance and the rewrite cost ------------------------------------------------------------------------------------------------------
def test_rewrites_are_counted_as_cost_not_as_detection(tmp_path):
    s = session_v2(tmp_path)
    r1 = s.write("東京で会議を開く")                                     # does not seat
    assert refusal_of(r1) == "span_inexpressible"
    r2 = s.write("会議の場所は東京")                                     # the rewrite in the structure's form
    assert r2["ok"] is True
    r3 = s.write("佐藤が予算を決めた")                                   # refused, never rewritten
    assert refusal_of(r3) == "span_inexpressible"
    ev = s.events()
    assert ev["rewrites"] == {"refused": 2, "rewritten": 1, "unrewritten": 1}
    assert ev["cost"] == {"unseatable": 2, "reseat_shape": 1, "unreadable": 0} and ev["detections"] == {"notes": 0, "reseat_content": 0, "headline": 0}
    assert ev["topics"] == {"declared": 0, "refused": 0, "expanded": 0} and ev["supersedes"] == {"ok": 0, "sentences": 0, "refused": {}} and ev["reports"] == {"ok": 0, "refused": 0}


def test_the_rewrite_counter_reads_a_v1_ledger_too(tmp_path):
    s = session(tmp_path)
    s.write("東京で会議を開く")
    s.write("会議の場所は東京")
    assert s.events()["rewrites"] == {"refused": 1, "rewritten": 1, "unrewritten": 0}


def test_op_counts_read_the_ledger_rows_alone(tmp_path):
    s = session_v2(tmp_path)
    s.call("declare_topic", {"text": T})
    s.write("東京で会議を開く")
    s.write("会議の場所は東京")
    rows = [x for x in ledger_rows(s) if x["actor"] == "model" and x["op"] != "begin"]
    assert mn.op_counts(rows) == {k: v for k, v in s.events().items() if k in ("rewrites", "topics", "supersedes", "reports")}


def test_v2_session_replays_identical_and_verifies(tmp_path):
    st = new_store(tmp_path)
    a = st.begin("m", profile=mem.PROFILE_V2)
    a.call("declare_topic", {"text": T})
    write_all(a, ["締め切りは水曜", "メモ、担当は山本", "東京で会議を開く", "会議の場所は東京"])
    a.call("report", {"turn": "1-4", "contradictions": [], "bugs": []})
    a.commit()
    v = mem.verify_store(str(tmp_path / "mem"))
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["sentences"] == 3
    assert mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER).identical
    # the memory rows of an expanded sentence carry topic_at; the others do not
    rows = st.rows()
    assert [r.get("topic_at") for r in rows] == [0, 3, None]
    mg.check_memory_rows(rows)

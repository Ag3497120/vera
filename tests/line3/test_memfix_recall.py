"""MEM-fix tests: the answer run knows the topics, and `recall` reads a question in its other forms (docs/LINE3_LOCAL_DECISIONS.md MEM-fix, L-MEM-59 / 60).

The meter v1 found 98 % of the gold values IN the memory and 29 of 60 answers an abstention: the answer run asked `recall` the question as the user put it, and the memory held the fact as
「<topic>のCDNキャッシュTTLは120秒」 (a subject-less sentence given its session's topic) or as a fused slot 「…デモ用イメージはv2.4」.  Now the answer run (memanswer.v2) holds the declared
topics in a file paired with the snapshot, `recall` reads a subject-less question with each topic in front and -- only if nothing answered -- a question with a subject as the fused slot.
The evidence gate is the same code and `emit` still judges the question AS ASKED.  Offline numbers on the stored meter_v1 are pinned here (experiments/line3/mem/memfix/offline_reach.py)."""
import hashlib
import json
import os
import sys

import pytest

from verantyx.loom import evidence as ev
from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memory as mem
from verantyx.loom import memrecall as mr
from verantyx.loom.corpus import Corpus
from mem_common import ROOT, new_store

V3 = mem.PROFILE_V3
METER = os.path.join(ROOT, "experiments", "line3", "mem", "meter_v1")
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3", "mem", "memfix"))
import memfix_common as C                                                      # noqa: E402
import offline_reach as OR                                                     # noqa: E402

TOPIC = "展示会準備"
SENTENCES = ["締め切りは水曜", "締め切りは金曜", "デモ用イメージはv2.4", "認証モジュール担当は田中", "広報の担当は山本", "ポートは8080"]


def built_store(tmp_path, name="st", topic=TOPIC, sentences=SENTENCES, profile=V3):
    store = str(tmp_path / name)
    door = md.StructureDoor(store, "notes", "m", profile=profile)
    door.set_turn("1-1")
    if topic:
        assert door.call("declare_topic", {"text": topic})["ok"] is True
    for k, t in enumerate(sentences):
        door.set_turn("1-%d" % (k + 1))
        assert door.call("write", {"text": t})["ok"] is True, t
    door.commit()
    door.close()
    return store


def corpus_of(store):
    snap = ma.write_snapshot(store, topics=True)
    data, rows = ma.read_snapshot(snap["path"])
    return Corpus(data), ma.superseded_of_rows(rows), snap


# -- the forms ---------------------------------------------------------------------------------------------------------------------------------
def test_question_forms_of_a_question_with_no_subject():
    s1, s2 = mr.question_forms("締め切りは何ですか", ["展示会準備", "広報活動"])
    assert [(f["form"], f["question"]) for f in s1] == [("as_asked", "締め切りは何ですか"), ("topic", "展示会準備の締め切りは何ですか"), ("topic", "広報活動の締め切りは何ですか")] and s2 == []


def test_question_forms_of_a_question_with_a_subject():
    s1, s2 = mr.question_forms("デモ用イメージのバージョンは何ですか", ["展示会準備"])
    assert [f["form"] for f in s1] == ["as_asked"]
    assert [(f["form"], f["question"]) for f in s2] == [("subject", "展示会準備のデモ用イメージは何ですか"), ("fused", "展示会準備のデモ用イメージバージョンは何ですか")]


def test_a_topic_that_is_the_subject_is_not_put_in_front_of_itself():
    assert mr.question_forms("展示会準備の締め切りは何ですか", ["展示会準備"]) == ([{"form": "as_asked", "question": "展示会準備の締め切りは何ですか"}], [])
    s1, s2 = mr.question_forms("締め切りは展示会準備ですか", ["展示会準備"])               # a topic the question already holds is skipped
    assert [f["form"] for f in s1] == ["as_asked"]


def test_no_topics_no_other_form_and_an_open_question_has_none():
    assert mr.question_forms("締め切りは何ですか", []) == ([{"form": "as_asked", "question": "締め切りは何ですか"}], [])
    assert ev.question_units("お元気ですか").form == ev.FORM_OPEN
    assert mr.question_forms("お元気ですか", ["展示会準備"]) == ([{"form": "as_asked", "question": "お元気ですか"}], [])


# -- recall -------------------------------------------------------------------------------------------------------------------------------------
def test_recall_with_the_topics_reads_what_the_question_as_asked_cannot(tmp_path):
    c, sup, snap = corpus_of(built_store(tmp_path))
    assert snap["topics"] == [TOPIC] and snap["sentences"] == 6
    q = "締め切りは何ですか"
    before = mr.recall(c, q, ev.EVIDENCE_V2, subject_guard=True)
    assert before["verdict"] == "NONE" and "question_has_no_subject" in before["issues"] and "forms" not in before
    after = mr.recall(c, q, ev.EVIDENCE_V2, subject_guard=True, topics=[TOPIC])
    assert after["verdict"] == "CHOICE" and sorted(g["text"] for g in after["answers"]) == ["水曜", "金曜"]
    assert all(o["via"] == ["topic"] for g in after["answers"] for o in g["occurrences"])
    assert after["forms"] == {"version": "recall.forms.v1", "tried": [{"form": "as_asked", "question": q, "passes": 0}, {"form": "topic", "question": "展示会準備の締め切りは何ですか", "passes": 2, "topic": TOPIC}]}
    p = mr.recall(c, "ポートは何ですか", ev.EVIDENCE_V2, subject_guard=True, topics=[TOPIC])
    assert p["verdict"] == "ANSWER" and p["answers"][0]["text"] == "8080"


def test_a_question_with_a_subject_falls_back_to_the_subject_as_the_fused_slot(tmp_path):
    c, sup, snap = corpus_of(built_store(tmp_path))
    a = mr.recall(c, "デモ用イメージのバージョンは何ですか", ev.EVIDENCE_V2, subject_guard=True, topics=[TOPIC])
    assert a["verdict"] == "ANSWER" and a["answers"][0]["text"] == "v2.4" and a["answers"][0]["occurrences"][0]["via"] == ["subject"]
    assert [(f["form"], f["passes"]) for f in a["forms"]["tried"]] == [("as_asked", 0), ("subject", 1), ("fused", 0)]
    b = mr.recall(c, "認証モジュールの担当は誰ですか", ev.EVIDENCE_V2, subject_guard=True, topics=[TOPIC])
    assert b["verdict"] == "ANSWER" and b["answers"][0]["text"] == "田中" and b["answers"][0]["occurrences"][0]["via"] == ["fused"]
    assert mr.recall(c, "認証モジュールの担当は誰ですか", ev.EVIDENCE_V2, subject_guard=True)["verdict"] == "NONE"


def test_the_weaker_forms_are_tried_only_when_the_question_as_asked_found_nothing(tmp_path):
    c, sup, snap = corpus_of(built_store(tmp_path))
    r = mr.recall(c, "広報の担当は誰ですか", ev.EVIDENCE_V2, subject_guard=True, topics=[TOPIC])
    assert r["verdict"] == "ANSWER" and r["answers"][0]["text"] == "山本" and [f["form"] for f in r["forms"]["tried"]] == ["as_asked"]
    assert r["answers"][0]["occurrences"][0]["via"] == ["as_asked"]


def test_nothing_changes_without_topics(tmp_path):
    c, sup, snap = corpus_of(built_store(tmp_path))
    for q in ("広報の担当は誰ですか", "締め切りは何ですか", "展示会準備の締め切りは何ですか", "デモ用イメージのバージョンは何ですか"):
        base = mr.recall(c, q, ev.EVIDENCE_V2, subject_guard=True)
        assert mr.recall(c, q, ev.EVIDENCE_V2, subject_guard=True, topics=None) == base and mr.recall(c, q, ev.EVIDENCE_V2, subject_guard=True, topics=[]) == base
        assert "forms" not in base and all("via" not in o for g in base["answers"] for o in g["occurrences"])


def test_superseded_sentences_stay_history_in_the_other_forms(tmp_path):
    store = str(tmp_path / "st")
    door = md.StructureDoor(store, "notes", "m", profile=V3)
    door.call("declare_topic", {"text": TOPIC})
    door.set_turn("1-1")
    door.call("write", {"text": "締め切りは水曜"})
    door.set_turn("1-2")
    door.call("write", {"text": "締め切りは金曜"})
    s = door.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})
    assert s["ok"] is True, s
    door.commit()
    door.close()
    c, sup, snap = corpus_of(store)
    r = mr.recall(c, "締め切りは何ですか", ev.EVIDENCE_V2, subject_guard=True, superseded=sup, topics=[TOPIC])
    assert r["verdict"] == "ANSWER" and r["answers"][0]["text"] == "金曜" and r["history"][0]["occurrences"][0]["answer"] == "水曜" and r["history"][0]["occurrences"][0]["via"] == ["topic"]


def test_the_gate_is_the_same_code(tmp_path):
    """Every form is an ordinary question to `evidence.judge_quote`: the passes of the topic form are exactly the passes of that question asked on its own."""
    c, sup, snap = corpus_of(built_store(tmp_path))
    j = mr.judge_forms(c, "締め切りは何ですか", [TOPIC], ev.EVIDENCE_V2, True, True)
    direct = mr.judge_memory(c, "展示会準備の締め切りは何ですか", ev.EVIDENCE_V2, True, True)
    assert [(p.sid, p.i0, p.i1, p.answer) for p in j["passes"]] == [(p.sid, p.i0, p.i1, p.answer) for p in direct["passes"]]


# -- the answer run (memanswer.v2) --------------------------------------------------------------------------------------------------------------
def test_the_answer_run_v2_holds_the_topics_and_replays(tmp_path):
    store = built_store(tmp_path)
    s = ma.AnswerSession(store, "締め切りは何ですか", "m", answer_version=ma.ANSWER_V2)
    b = s.begin_result["mem_answer"]
    assert b["version"] == "memanswer.v2" and b["topics"] == [TOPIC] and b["topics_file"].startswith("topics_") and b["forms"] == "recall.forms.v1"
    assert "forms.tried" in s.begin_result["rules"]["recall"]
    r = s.call("recall", {"question": "締め切りは何ですか"})
    assert r["verdict"] == "CHOICE" and r["forms"]["tried"][1]["form"] == "topic"
    s.call("abstain", {"type": "contested"})
    v = ma.verify_answer(s.ledger.dir, store)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    out = ma.answer_output(s.ledger.dir, store)
    assert out["status"] == "abstained" and out["type"] == "contested" and sorted(out["recalls"][0]["answers"]) == [["水曜"], ["金曜"]]
    assert md.answer_of_output(out) == {"kind": "contested", "values": ["水曜", "金曜"]}


def test_emit_judges_the_question_as_asked(tmp_path):
    """A sentence recall reached through the topic form is NOT emittable for a question with no subject: the gate says so (this is the open point, not a bug)."""
    store = built_store(tmp_path)
    s = ma.AnswerSession(store, "ポートは何ですか", "m", answer_version=ma.ANSWER_V2)
    r = s.call("recall", {"question": "ポートは何ですか"})
    assert r["verdict"] == "ANSWER" and r["answers"][0]["text"] == "8080"
    sid = r["answers"][0]["occurrences"][0]["sid"]
    w = s.call("weave_span", {"sid": sid, "tier": "WORD", "first": "8080", "last": "8080"})
    assert w["ok"] is True
    e = s.call("emit", {})
    assert e["ok"] is False and s.closed() is None
    assert "question_has_no_subject" in json.dumps(e, ensure_ascii=False)


def test_a_v1_answer_session_is_what_it_was(tmp_path):
    store = built_store(tmp_path)
    s = ma.AnswerSession(store, "締め切りは何ですか", "m")
    assert s.begin_result["mem_answer"]["version"] == "memanswer.v1" and "topics" not in s.begin_result["mem_answer"]
    r = s.call("recall", {"question": "締め切りは何ですか"})
    assert r["verdict"] == "NONE" and "forms" not in r
    s.call("abstain", {"type": "no_record"})
    assert ma.verify_answer(s.ledger.dir, store)["status"] == "OK"


def test_a_store_that_declared_no_topic_has_an_empty_topics_file(tmp_path):
    store = built_store(tmp_path, "nt", topic=None, sentences=["広報の担当は山本"])
    s = ma.AnswerSession(store, "広報の担当は何ですか", "m", answer_version=ma.ANSWER_V2)
    assert s.begin_result["mem_answer"]["topics"] == []
    r = s.call("recall", {"question": "広報の担当は何ですか"})
    assert r["verdict"] == "ANSWER" and "forms" not in r
    s.call("abstain", {"type": "unknown"})
    assert ma.verify_answer(s.ledger.dir, store)["status"] == "OK"


def test_the_topics_file_is_pinned_by_its_name_and_by_the_begin_row(tmp_path):
    store = built_store(tmp_path)
    s = ma.AnswerSession(store, "締め切りは何ですか", "m", answer_version=ma.ANSWER_V2)
    s.call("abstain", {"type": "no_record"})
    tf = os.path.join(store, "snapshots", s.begin_result["mem_answer"]["topics_file"])
    data = open(tf, "rb").read()
    assert os.path.basename(tf) == "topics_%s.json" % hashlib.sha256(data).hexdigest()[:12]
    assert ma.verify_answer(s.ledger.dir, store)["status"] == "OK"
    os.replace(tf, tf + ".bak")                                                            # missing
    v = ma.verify_answer(s.ledger.dir, store)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "topics_missing"
    other = json.dumps({"topics": [{"session": 1, "topic": "別の主題"}]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    open(tf, "w", encoding="utf-8").write(other)                                           # other bytes under the same name
    v = ma.verify_answer(s.ledger.dir, store)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "topics_unverified"
    os.replace(tf + ".bak", tf)
    assert ma.verify_answer(s.ledger.dir, store)["status"] == "OK"


def test_the_snapshot_and_the_topics_file_are_idempotent(tmp_path):
    store = built_store(tmp_path)
    a = ma.write_snapshot(store, topics=True)
    b = ma.write_snapshot(store, topics=True)
    assert a == b and sorted(os.listdir(os.path.join(store, "snapshots"))) == sorted([a["name"], a["topics_name"]])
    assert ma.write_snapshot(store)["name"] == a["name"] and "topics" not in ma.write_snapshot(store)               # the v1 call is what it was
    assert [e["topic"] for e in mem.session_topics(os.path.join(store, "sessions", "s0001"))] == [TOPIC]


# -- the stored meter ---------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q,gold,kind", [("CDNキャッシュTTLは何秒ですか？", ["120秒", "30秒"], "CHOICE"), ("QA締切はいつですか？", ["6/14"], "ANSWER"),
                                         ("デモ用イメージのバージョンは何ですか？", ["v2.4"], "ANSWER")])
def test_questions_the_meter_could_not_answer_from_its_own_memory(q, gold, kind):
    store = os.path.join(METER, "MEM-T01", "notes", "r01", "store")
    corpus, rows, sup = C.snapshot_corpus(store)
    topics = C.topics_of_store(store)
    assert topics == ["在庫管理アプリ小規模リリース", "在庫管理アプリの小規模リリース"] or len(topics) >= 1
    before = mr.recall(corpus, q, ev.EVIDENCE_V2, subject_guard=True, superseded=sup or None)
    after = mr.recall(corpus, q, ev.EVIDENCE_V2, subject_guard=True, superseded=sup or None, topics=topics)
    assert before["verdict"] == "NONE" and after["verdict"] == kind
    assert sorted(a for g in after["answers"] for a in g["answers"]) == sorted(gold)


def test_offline_reach_on_two_stored_runs(tmp_path):
    runs = [OR.evaluate_run(d) for d in C.structure_runs(METER)[:2]]
    t = OR.tally(runs)
    assert [r["run"] for r in runs] == ["MEM-T01/blind/r01", "MEM-T01/blind/r02"]
    assert t["before"]["strict"]["all"] == {"n": 20, "reached": 1, "exact": 1, "noisy": 0}
    assert t["after"]["strict"]["all"] == {"n": 20, "reached": 11, "exact": 10, "noisy": 3}


def test_offline_reach_over_the_whole_meter_is_pinned():
    """The numbers of the decisions file (L-MEM-60): 36 structure runs x 10 questions, recall called with the question text over the stored snapshot."""
    runs = [OR.evaluate_run(d) for d in C.structure_runs(METER)]
    t = OR.tally(runs)
    assert len(runs) == 36
    assert t["before"]["strict"]["all"] == {"n": 360, "reached": 61, "exact": 61, "noisy": 0}
    assert t["after"]["strict"]["all"] == {"n": 360, "reached": 144, "exact": 112, "noisy": 47}
    assert t["after"]["lenient"]["all"]["reached"] == 150 and t["before"]["lenient"]["all"]["reached"] == 61
    for kind, b, a in (("contradicted", 7, 32), ("updated", 21, 50), ("plain", 33, 62)):
        assert (t["before"]["strict"][kind]["reached"], t["after"]["strict"][kind]["reached"]) == (b, a)


def test_a_snapshot_without_its_topics_is_refused_not_replaced(tmp_path):
    store = built_store(tmp_path)
    old = ma.write_snapshot(store)                                              # a snapshot of the store as it is now, no topics file
    door = md.StructureDoor(store, "notes", "m", profile=V3)                    # the store grows: a fresh snapshot would now be another one
    door.set_turn("2-1")
    door.call("write", {"text": "会場は京都"})
    door.commit()
    door.close()
    with pytest.raises(mr.Refuse) as e:
        ma.AnswerSession(store, "締め切りは何ですか", "m", snapshot=old, answer_version=ma.ANSWER_V2)
    assert e.value.type == "snapshot_without_topics"
    assert not os.path.isdir(os.path.join(store, "answers"))                   # nothing was begun
    new = ma.write_snapshot(store, topics=True)
    s = ma.AnswerSession(store, "締め切りは何ですか", "m", snapshot=new, answer_version=ma.ANSWER_V2)
    assert s.begin_result["mem_answer"]["sentences"] == 7
    s1 = ma.AnswerSession(store, "締め切りは何ですか", "m", snapshot=old)       # v1 with the snapshot given: that snapshot, not the new one
    assert s1.begin_result["mem_answer"]["sentences"] == 6

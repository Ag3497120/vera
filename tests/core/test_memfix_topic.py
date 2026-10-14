"""MEM-fix tests (T-MEMFIX-01..): the profile `mem.v3` and the topic.

The meter v1 found 254 of 654 topic-expanded sentences carrying the topic twice (and 430 more given a topic in front of a subject of their own).  A mem.v3 session expands a sentence only if
its clause truly has no subject (`memory.topic_is_missing`); declares no topic that holds a particle (the expansion of such a topic is itself refused: nested_particle_chain); asks a sentence
with its own subject from the start of its token (`clause_at`) so that dropping the accidental walk-back does not make it unreadable.  The twenty cases below are REAL: the sentences the
models of tests/fixtures/line3/mem/meter_v1 wrote (tests/core/memfix_meter_cases.json, each with the folder it came from).  Everything old stays as it was: mem.v1 / mem.v2 sessions and the
stored meter_v1 stores replay under their recorded profile."""


import json


import os


import shutil


import pytest


from verantyx.loom import memanswer as ma


from verantyx.loom import memdoor as md


from verantyx.loom import memguard as mg


from verantyx.loom import memnotes as mn


from verantyx.loom import memory as mem


from mem_common import ROOT, ledger_rows, new_store, refusal_of


V3 = mem.PROFILE_V3


CASES = json.load(open(os.path.join(ROOT, "tests", "core", "memfix_meter_cases.json"), encoding="utf-8"))


def session(tmp_path, name="mem", profile=V3, **kw):
    return new_store(tmp_path, name).begin("test-model", profile=profile, **kw)


def one(tmp_path, k, profile, topic, text, set_topic_directly=False):
    s = session(tmp_path, "%s%d" % (profile, k), profile)
    if set_topic_directly:
        s.run.topic = topic                         # (test-only) a topic the v3 declare_topic would refuse: it was what the meter's model declared
    else:
        assert s.call("declare_topic", {"text": topic})["ok"] is True
    return s, s.call("write", {"text": text})




@pytest.mark.parametrize("k", range(20))
def test_v3_expands_only_a_clause_that_truly_has_no_subject(tmp_path, k):
    c = CASES[k]
    s, w = one(tmp_path, k, V3, c["topic"], c["written"])
    assert w["ok"] is True, w
    assert w["text"] == c["v3_stored"]
    assert ("implicit_topic" in w) is c["v3_expanded"]
    if c["class"] == "double":
        assert w["text"] == c["written"] and w["text"].count(c["topic"]) == 1               # the topic is never put in front of a sentence that starts with it
    if c["class"] == "lacks":
        assert w["implicit_topic"] == {"topic": c["topic"], "at": 0, "written": c["written"]} and w["text"].count(c["topic"]) == 1
    if c["class"] == "own_subject":
        assert w["text"] == c["written"] and c["topic"] not in w["text"]                    # 「基調講演者の到着予定は…」 keeps its own subject; no invented topic


@pytest.mark.parametrize("k", range(20))
def test_v2_still_does_what_the_meter_saw(tmp_path, k):
    c = CASES[k]
    s, w = one(tmp_path, k, mem.PROFILE_V2, c["topic"], c["written"])
    assert w["ok"] is True and w["text"] == c["v2_stored"]
    assert ("implicit_topic" in w) and (c["class"] == "lacks" or w["text"] != c["written"])         # every one of the twenty was expanded, 14 of them wrongly
    if c["class"] == "double":
        assert w["text"].count(c["topic"]) == 2                                              # the double prefix, as the meter v1 recorded it


def test_the_rule_on_the_meter_s_own_topics_with_particles(tmp_path):
    """The meter's topics held の (培養条件の共同実験, 倉庫在庫アプリ3.2のリリース ...): v3 declares none of them, but the decision about a sentence must not depend on that, so the rule
    is checked on a session whose topic is set directly: starts with the topic / holds it in its clause / has a particle in the lead-in -> no expansion."""
    s = session(tmp_path)
    s.run.topic = "培養条件の共同実験"
    for text, expect in [("培養条件の共同実験の本試験の試料数は52本です", False), ("培養条件の共同実験のログ保管期間は90日", False), ("冷凍庫鍵の管理者は中村", False),
                         ("解析の試料抽出時間は8分", False), ("生データ共有先は/lab/share/run", True), ("陰性対照ラベルはNC-04", True), ("採取日は11/04", True)]:
        w = s.call("write", {"text": text})
        if w["ok"]:
            assert ("implicit_topic" in w) is expect, text
        else:
            assert expect and w["refusal"] == "span_inexpressible" and w["detail"]["reason"] == "nested_particle_chain", (text, w)   # the topic's own の makes the EXPANSION unseatable


def test_topic_is_missing_unit(tmp_path):
    g = {"start": 6, "end": 9}
    assert mem.topic_is_missing("広報", "メモ、締め切りは水曜", 3, {"start": 3, "end": 8}) is True       # a lead-in clause before 、 stays, the topic goes in front of the clause
    assert mem.topic_is_missing("広報", "新規締め切りは水曜", 0, {"start": 2, "end": 7}) is True         # a compound Y: no particle in the lead-in
    assert mem.topic_is_missing("広報", "広報の締め切りは水曜", 0, {"start": 3, "end": 8}) is False      # the sentence starts with the topic
    assert mem.topic_is_missing("広報", "経理の広報担当は山本", 0, {"start": 3, "end": 7}) is False      # the topic is part of its subject
    assert mem.topic_is_missing("広報", "経理の締め切りは水曜", 0, {"start": 3, "end": 8}) is False      # a subject of its own (の in the lead-in)
    assert mem.topic_is_missing("広報", "田中が決めた締め切りは水曜", 0, {"start": 5, "end": 10}) is False
    assert mem.topic_is_missing("広報", "締め切りは広報の水曜", 0, {"start": 0, "end": 5}) is True        # the topic after the は is the answer's business, not the subject's
    del g


@pytest.mark.parametrize("text", ["培養条件の共同実験", "営業と開発", "本番環境で試験", "本店に移転", "新製品を発売", "広報が担当"])
def test_v3_refuses_a_topic_with_a_particle_and_says_why(tmp_path, text):
    s = session(tmp_path)
    r = s.call("declare_topic", {"text": text})
    assert refusal_of(r) == "bad_topic" and "nested_particle_chain" in r["detail"]["reason"] and s.run.topic is None
    assert s.call("declare_topic", {"text": "展示会準備"})["ok"] is True


def test_v2_accepts_such_a_topic_and_every_subject_less_write_is_then_refused(tmp_path):
    """The finding behind the v3 rule (meter v1: 62 % of the subject-less sentences of a topic with の were refused by their own expansion)."""
    s = session(tmp_path, "v2", mem.PROFILE_V2)
    assert s.call("declare_topic", {"text": "展示会の準備"})["ok"] is True
    for text in ("締め切りは水曜", "担当は山本", "新規締め切りは水曜"):
        w = s.call("write", {"text": text})
        assert refusal_of(w) == "span_inexpressible" and w["detail"]["reason"] == "nested_particle_chain"
    s3 = session(tmp_path, "v3")
    assert s3.call("declare_topic", {"text": "展示会準備"})["ok"] is True
    assert all(s3.call("write", {"text": t})["ok"] for t in ("締め切りは水曜", "担当は山本", "新規締め切りは水曜"))


def test_a_sentence_with_its_own_subject_is_asked_from_the_start_of_its_token(tmp_path):
    s = session(tmp_path)
    assert s.call("declare_topic", {"text": "展示会準備"})["ok"] is True
    a = s.call("write", {"text": "監視設定の本番監視ポートは8443"})
    assert a["ok"] and "implicit_topic" not in a and a["clause_at"] == 0 and a["clause"]["question"] == "監視設定の本番監視ポートは何ですか"
    assert mn.SELF_QUESTION_UNREADABLE not in [n["type"] for n in a.get("notes", [])]
    b = s.call("write", {"text": "監視設定の本番監視ポートは8088"})
    sq = [n for n in b["notes"] if n["type"] == mn.SAME_QUESTION]
    assert len(sq) == 1 and sorted(x for v in sq[0]["variants"] for x in v["answers"]) == ["8088", "8443"]       # the contradiction is seen again, with no invented topic
    rows = [json.loads(ln) for ln in open(s.store.memory_path, encoding="utf-8")] if s.store.memory_path.exists() else None
    assert rows is None                                                     # (not committed yet)
    s.commit()
    rows = [json.loads(ln) for ln in open(s.store.memory_path, encoding="utf-8")]
    assert [r.get("clause_at") for r in rows] == [0, 0] and all("topic_at" not in r for r in rows)
    assert mem.verify_store(s.store.path, mem.FROM_HEADER)["status"] == "OK"


def test_a_clause_that_starts_at_a_token_boundary_has_no_clause_at(tmp_path):
    s = session(tmp_path)
    for t in ("広報の期限は水曜", "認証の担当は田中", "会議、広報の期限は水曜"):
        w = s.call("write", {"text": t})
        assert w["ok"] and "clause_at" not in w, t


def test_in_v2_the_same_sentence_is_unreadable_cut_subject(tmp_path):
    s = session(tmp_path, "v2", mem.PROFILE_V2)
    a = s.call("write", {"text": "監視設定の本番監視ポートは8443"})
    n = [x for x in a["notes"] if x["type"] == mn.SELF_QUESTION_UNREADABLE]
    assert len(n) == 1 and a["clause"]["question"] == "ポートは何ですか" and "clause_at" not in a                  # the question is cut inside the compound Y 本番監視ポート


def test_the_v3_begin_row(tmp_path):
    s = session(tmp_path)
    b = ledger_rows(s)[0]["result"]
    h = b["header"]
    assert h["mem_profile"] == "mem.v3" and h["notes_profile"] == "mem.v2" and h["caps"] == "mem.v1" and b["tools"] == list(mem.tools_of(V3)) == list(mem.tools_of(mem.PROFILE_V2))
    assert b["task"]["caps"] == mem.CAPS_MEM_V3 and mem.CAPS_MEM_V3 == dict(mem.CAPS_MEM_V2, writes=240, recalls=240, lookups=240, ops=1200, topics=32, supersedes=120, reports=240)
    assert "topic" in b["rules"] and "AS WRITTEN" in b["rules"]["topic"] and "cite" in b["rules"]["report"]
    s2 = session(tmp_path, "v2", mem.PROFILE_V2)
    h2 = ledger_rows(s2)[0]["result"]["header"]
    assert h2["mem_profile"] == "mem.v2" and h2["notes_profile"] == "mem.v1"
    assert ledger_rows(s2)[0]["result"]["task"]["caps"] == mem.CAPS_MEM_V2                      # v2 is as it was


def test_v3_status_and_the_op_cap(tmp_path):
    s = session(tmp_path)
    st = s.status()
    assert st["profile"] == "mem.v3" and st["caps"]["writes"] == 240 and st["caps"]["reports"] == 240


def test_the_harness_rows_of_a_turn_that_had_no_report(tmp_path):
    s = session(tmp_path)
    r = s.harness("report_forced", {"turn": "1-2", "reason": "turn_limit", "calls": 24})
    assert r == {"ok": True}
    s.harness("report_missing", {"turn": "1-2", "reason": "turn_limit", "calls": 25})
    for bad in ({"turn": "x", "reason": "turn_limit", "calls": 1}, {"turn": "1-2", "reason": "other", "calls": 1}, {"turn": "1-2", "reason": "turn_limit"},
                {"turn": "1-2", "reason": "turn_limit", "calls": -1}, {"turn": "1-2", "reason": "turn_limit", "calls": True}):
        with pytest.raises(ValueError):
            s.harness("report_forced", bad)
    s.call("write", {"text": "広報の期限は水曜"})
    s.commit()
    assert mem.verify_store(s.store.path, mem.FROM_HEADER)["status"] == "OK"
    rows = ledger_rows(s)
    assert [x["op"] for x in rows if x["actor"] == "harness"] == ["report_forced", "report_missing"]
    for prof in (mem.PROFILE_V1, mem.PROFILE_V2):                                             # no older profile has these rows
        old = session(tmp_path, "old" + prof, prof)
        with pytest.raises(ValueError):
            old.harness("report_forced", {"turn": "1-2", "reason": "turn_limit", "calls": 1})


@pytest.mark.parametrize("profile", [mem.PROFILE_V2, V3])
def test_the_live_corpus_matches_the_rows_and_each_history_sha_is_recomputable(tmp_path, profile):
    s = session(tmp_path, "live" + profile, profile)
    texts = ["監視設定の本番監視ポートは8443", "広報の期限は水曜", "監視設定の本番監視ポートは8088", "認証モジュール担当は田中", "参加者用椅子の追加費は3万円", "広報の期限は金曜"]
    shas = []
    for k, t in enumerate(texts):
        before = mem.mem_sha(s.run.rows)
        w = s.call("write", {"text": t})
        assert w["ok"] is True, w
        assert w["history"]["sentences"] == k and w["history"]["corpus_sha"] == mem.build_corpus(s.run.rows[:k]).corpus_sha        # recomputable from memory.jsonl's rows before the write
        assert s.run.corpus_cur.corpus_sha == mem.build_corpus(s.run.rows).corpus_sha                                          # the live corpus is the corpus of the rows now
        assert mem.mem_sha(s.run.rows[:k]) == before
        shas.append(w["history"]["corpus_sha"])
    if profile == V3:
        assert any("clause_at" in r for r in s.run.rows)                                                                       # the case under test happened
    s.commit()
    assert mem.verify_store(s.store.path, mem.FROM_HEADER)["status"] == "OK"
    s2 = new_store(tmp_path, "live" + profile).begin("m", profile=profile)                                                    # a new session of the same store agrees
    assert s2.run.corpus_cur.corpus_sha == mem.build_corpus(s2.run.rows).corpus_sha

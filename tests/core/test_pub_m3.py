"""PUB-M3 tests: topic nests (OP-PUB-3, OP-PUB-4's structure): declare_topic opens a nest whose centre is the head phrase of the topic (particles allowed), an F4 clause is completed structurally (`via: nest`) with
nothing put in front of any text, members by centre and by の-arm path, nests per session, nest(topic) / nests_of(centre), replay.  No network, no API."""


import os


import pytest


from verantyx.loom import memcross as mx


from verantyx.loom import memory as mem


from verantyx.loom import memshape as ms


from verantyx.loom.memguard import make_source


from mem_common import new_store


V4 = mem.PROFILE_V4


def sess(tmp_path, name="mem"):
    return new_store(tmp_path, name).begin("test-model", profile=V4)


def rows(texts, session=1, start=0):
    return [{"kind": "base", "sent": t, "source": make_source("t", session, start + i)} for i, t in enumerate(texts)]


def test_declare_topic_opens_a_nest_whose_centre_is_the_head_phrase_of_the_topic(tmp_path):
    s = sess(tmp_path)
    r = s.call("declare_topic", {"text": "新製品"})
    assert r["ok"] and r["at"] == 0 and r["nest"] == {"id": "N1", "topic": "新製品", "centre": "新製品", "arms": [], "prefix": "", "reopened": False}
    r = s.call("declare_topic", {"text": "A社のB事業"})
    assert r["ok"] and r["nest"]["id"] == "N2" and r["nest"]["centre"] == "B事業" and r["nest"]["arms"] == [["の", "A社"]]
    assert "form" not in r                                                                           # the mem.v3 expansion form 「<topic>の<Y>は<A>」 does not exist
    assert s.call("declare_topic", {"text": "新製品"})["nest"]["reopened"] is True and s.status()["topics"] == 3


def test_topic_head_is_the_last_phrase_with_its_chain_and_keeps_what_is_before_it():
    h = mx.topic_head("A社のB事業の営業部")
    assert h.centre == "営業部" and [(a.particle, a.seat.text, [(b.particle, b.seat.text) for b in a.arms]) for a in h.arms] == [("の", "B事業", [("の", "A社")])]
    h = mx.topic_head("東京での会議")
    assert h.centre == "会議" and h.arms == () and h.prefix == "東京での"                                # a particle that is not の cannot be an arm of the head: the text is kept, not dropped
    assert mx.topic_head("展示会準備").centre == "展示会準備" and mx.topic_head("。。") is None


def test_particles_in_a_topic_are_allowed_in_v4_and_refused_in_v3_a_particle_at_the_end_is_refused(tmp_path):
    assert sess(tmp_path).call("declare_topic", {"text": "A社のB事業"})["ok"]
    v3 = new_store(tmp_path, "v3").begin("m", profile="mem.v3")
    assert v3.call("declare_topic", {"text": "A社のB事業"})["refusal"] == "bad_topic"                      # mem.v3: the structure puts の after it and a second particle makes every expansion unseatable
    s = sess(tmp_path, "v4b")
    for bad in ("新製品の", "新製品。", "。", "を"):
        assert s.call("declare_topic", {"text": bad})["refusal"] == "bad_topic"


def test_an_f4_clause_is_completed_by_the_nest_centre_and_nothing_is_prepended(tmp_path):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "新製品"})
    r = s.write("資料を送付した")
    assert r["ok"] and r["text"] == "資料を送付した" and s.run.rows[0]["sent"] == "資料を送付した" and "topic_at" not in s.run.rows[0]
    c = r["shape"]["clauses"][0]
    assert (c["shape"], c["tank"], c["centre"], c["via"], c["nest"]) == ("F4", "F3", "送付", "nest", "N1")
    s.commit()
    ix = mem.MemStore(str(tmp_path / "mem")).index()
    cr = ix.cross("F3", "送付")
    assert ix.cross("F4", "送付") is None and [(a, [x.phrase for x in ss]) for a, ss in cr.slots] == [("を", ["資料"]), ("が", ["新製品"])]
    subj = cr.seats_of("が")[0]
    assert subj.via == "nest" and subj.nest == "N1" and subj.prov.sid == 0 and subj.prov.session == 1 and subj.prov.surface == "新製品"
    assert cr.seats_of("を")[0].via is None
    n = ix.nest("新製品")
    assert [(m.sid, m.kind, m.tank, m.centre, m.exact) for m in n.members] == [(0, "completed", "F3", "送付", True)]


def test_the_nest_centre_seat_carries_the_arms_of_the_topic_and_the_text_is_untouched(tmp_path):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "A社のB事業"})
    s.write("会議を開いた")
    s.commit()
    ix = mem.MemStore(str(tmp_path / "mem")).index()
    subj = ix.cross("F3", "開く").seats_of("が")[0]
    assert subj.phrase == "B事業" and [(p, c.phrase, c.via) for p, c in subj.arms] == [("の", "A社", "nest")]
    assert ix.seats(ix.cross("F3", "開く"), (("が", "B事業"), ("の", None)))[0].phrase == "A社"
    assert ix.nests_of("B事業")[0].topic == "A社のB事業" and ix.nest("A社のB事業").arms == (("の", "A社"),)
    assert ix.centres_with("A社") == (("F3", "開く", "が>の"),)


def test_without_an_open_nest_an_f4_clause_stays_uncompleted_in_the_f4_tank(tmp_path):
    s = sess(tmp_path)
    c = s.write("資料を送付した")["shape"]["clauses"][0]
    assert (c["tank"], c["via"], c["nest"]) == ("F4", None, None)
    s.commit()
    ix = mem.MemStore(str(tmp_path / "mem")).index()
    assert [x.phrase for _, ss in ix.cross("F4", "送付").slots for x in ss] == ["資料"] and ix.nests == ()


def test_members_are_the_crosses_whose_centre_or_no_arm_path_holds_the_nest_centre():
    ix = mx.build_index(rows(["新製品は来月発売です", "新製品の担当は田中です", "締め切りは水曜", "広報の締め切りは金曜", "資料を送付した", "会議の参加者は佐藤です"]),
                        [{"session": 1, "at": 0, "topic": "新製品"}])
    n = ix.nest("新製品")
    assert [(m.sid, m.kind, m.exact) for m in n.members] == [(0, "centre", True), (1, "path", True), (2, "context", False), (3, "context", False), (4, "completed", True), (5, "context", False)]
    # designer decision (L-PUB-39): a clause written while the nest is open is a member of kind `context` (its text and subject are not changed); a bare 「Y は A」 is still NOT completed
    assert ix.cross("F2", "締め切り").seats_of("は")[0].via is None and ix.cross("F2", "締め切り").seats_of("が") == ()


def test_a_member_is_exact_when_the_arms_of_the_topic_are_in_the_clause_too():
    ix = mx.build_index(rows(["A社のB事業の予算は100万円", "B事業の予算は200万円", "C社のB事業の予算は300万円", "B事業は黒字です"]), [{"session": 1, "at": 0, "topic": "A社のB事業"}])
    assert [(m.sid, m.kind, m.exact) for m in ix.nest("A社のB事業").members] == [(0, "path", True), (1, "path", False), (2, "path", False), (3, "centre", False)]


def test_two_nests_can_share_a_centre_and_one_topic_is_one_nest():
    ix = mx.build_index(rows(["a"], 1) , [{"session": 1, "at": 0, "topic": "A社のB事業"}, {"session": 1, "at": 0, "topic": "C社のB事業"}, {"session": 2, "at": 1, "topic": "A社のB事業"}])
    assert [n.id for n in ix.nests_of("B事業")] == ["N1", "N2"] and ix.nests_of("D事業") == ()
    assert ix.nest("A社のB事業").declared == ((1, 0), (2, 1)) and ix.nest("存在しない") is None


def test_a_nest_belongs_to_its_session_the_next_session_declares_its_own(tmp_path):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "新製品"})
    s.write("資料を送付した")
    s.commit()
    s2 = new_store(tmp_path).begin("m", profile=V4)
    assert s2.run.topic is None
    assert s2.write("会議を開いた")["shape"]["clauses"][0]["tank"] == "F4"                                 # no nest open in session 2
    r = s2.call("declare_topic", {"text": "新製品"})
    assert r["nest"]["reopened"] is True and r["nest"]["id"] == "N1" and r["at"] == 2
    assert s2.write("担当者に連絡した")["shape"]["clauses"][0]["via"] == "nest"
    s2.commit()
    ix = mem.MemStore(str(tmp_path / "mem")).index()
    assert ix.nest("新製品").declared == ((1, 0), (2, 2)) and [(m.sid, m.kind) for m in ix.nest("新製品").members] == [(0, "completed"), (2, "completed")]
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"


def test_a_redeclared_topic_in_one_session_changes_the_nest_for_the_next_clauses(tmp_path):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "新製品"})
    s.write("資料を送付した")
    s.call("declare_topic", {"text": "旧製品"})
    s.write("会議を開いた")
    s.commit()
    ix = mem.MemStore(str(tmp_path / "mem")).index()
    assert ix.cross("F3", "送付").seats_of("が")[0].phrase == "新製品" and ix.cross("F3", "開く").seats_of("が")[0].phrase == "旧製品"
    assert [m.sid for m in ix.nest("新製品").members] == [0] and [m.sid for m in ix.nest("旧製品").members] == [1]


def test_a_change_clause_with_no_slot_is_completed_too_and_keeps_its_old_value():
    ix = mx.build_index(rows(["金曜に延期した", "水曜から金曜へ変更"]), [{"session": 1, "at": 0, "topic": "新製品"}])
    c = ix.cross("F3", "延期")
    assert c.seats_of("が")[0].phrase == "新製品" and c.seats_of("は")[0].phrase == "金曜" and c.seats_of("は")[0].change.form == "ni_enki"
    d = ix.cross("F3", "変更").seats_of("は")[0]
    assert d.phrase == "金曜" and d.change.old == "水曜" and d.change.form == "kara_he_henkou" and d.path == (("が", "新製品"),)


def test_declarations_do_not_change_h_only_the_index(tmp_path):
    a, b = sess(tmp_path, "a"), sess(tmp_path, "b")
    b.call("declare_topic", {"text": "新製品"})
    for s in (a, b):
        s.write("資料を送付した")
        s.write("認証の期限は金曜")
        s.commit()
    ba, bb = (open(str(tmp_path / n / "memory.jsonl"), "rb").read() for n in ("a", "b"))
    assert ba == bb                                                                                    # the same bytes of H: nothing was put in front of any sentence
    assert mem.MemStore(str(tmp_path / "a")).index().index_sha != mem.MemStore(str(tmp_path / "b")).index().index_sha


def test_the_nest_declarations_are_read_from_the_ledger_and_survive_replay(tmp_path):
    for k in range(3):
        s = new_store(tmp_path).begin("m", profile=V4)
        s.call("declare_topic", {"text": "新製品" if k != 1 else "A社のB事業"})
        s.write("資料を送付した")
        s.write("認証の期限は%sに延期した" % ("金曜", "月曜", "水曜")[k])
        s.commit()
    st = mem.MemStore(str(tmp_path / "mem"))
    assert [d["topic"] for e in st.head()["sessions"] for d in mem.session_nest_decls(st.sessions_dir / e["run_id"])] == ["新製品", "A社のB事業", "新製品"]
    assert mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER).identical
    ix = st.index()
    assert [n.id for n in ix.nests] == ["N1", "N2"] and [len(n.members) for n in ix.nests] == [4, 2]
    assert [e.kind for e in ix.history_full(("F1", "期限", (("の", "認証"),)))] == ["first", "update", "update"]

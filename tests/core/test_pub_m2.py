"""PUB-M2 tests: the mem.v4 profile (write acceptance by the shape exchanger, keep_unshaped, the weave-refused-but-accepted row) and the memory crosses in per-shape tanks (verantyx/loom/memcross.py):
tanks, seats and their provenance, nested chains, the faithful rings, the order of the seats by the frozen key, supersede marks, the pure function and its fold, replay, byte identity across
PYTHONHASHSEED, purity, and `mem_run --profile mem.v4` end to end with a stub model.  No network, no API."""


import ast


import json


import os


import subprocess


import sys


import pytest


from verantyx.line3 import foundation as fd


from verantyx.line3 import geometry as geo


from verantyx.line3 import placement as pl


from verantyx.loom import driver as drv


from verantyx.loom import memcross as mx


from verantyx.loom import memdoor as md


from verantyx.loom import memory as mem


from verantyx.loom import memshape as ms


from verantyx.loom.corpus import Corpus


from verantyx.loom.memguard import make_source


from mem_common import ROOT, new_store


V4 = mem.PROFILE_V4


def sess(tmp_path, name="mem", **kw):
    return new_store(tmp_path, name).begin("test-model", profile=V4, **kw)


def rows(texts, session=1, start=0):
    return [{"kind": "base", "sent": t, "source": make_source("t", session, start + i)} for i, t in enumerate(texts)]


def refusal(res):
    assert res["ok"] is False, res
    return res["refusal"]


def test_the_profile_is_mem_v4_and_the_older_ones_are_untouched():
    assert V4 == "mem.v4" and mem.PROFILES == ("mem.v1", "mem.v2", "mem.v3", "mem.v4") and mem.V2_PLUS == ("mem.v2", "mem.v3", "mem.v4")
    assert mem.tools_of("mem.v3") == mem.TOOLS + mem.V2_OPS and mem.tools_of(V4) == mem.TOOLS + mem.V2_OPS + ("keep_unshaped", "bridge") and mem.tools_of("mem.v1") == mem.TOOLS
    assert mx.ARMS == fd.LADDER[1:] == ("の", "に", "で", "と", "を", "が") and mx.VALUE == fd.LADDER[0] == "は" and mx.SLOTS == mx.ARMS + ("は", "quantity", "object_bare")
    assert mem.caps_of(V4) == dict(mem.CAPS_MEM_V3, bridges=60) and mem.caps_of("mem.v3") is mem.CAPS_MEM_V3
    assert md.story_tools("notes", V4) == ("write", "keep_unshaped", "bridge", "declare_topic", "supersede", "recall", "read_sentence", "report", "status")
    assert md.story_tools("notes", "mem.v3") == md.STORY_TOOLS["notes"] and md.story_tools("log", V4) == md.STORY_TOOLS["log"] and "keep_unshaped" in md.TOOL_SPECS
    # a row of an older profile serialises as it always did
    assert mem.row_line({"kind": "base", "sent": "a", "source": "mem:t/1#0"}) == '{"kind":"base","sent":"a","source":"mem:t/1#0"}\n'


def test_the_begin_row_of_a_v4_session_records_the_shape_table_and_the_tools(tmp_path):
    s = sess(tmp_path)
    b = s.rows()[0]["result"]
    assert b["header"]["mem_profile"] == V4 and b["header"]["shape"] == {"version": "shape.v2", "sha": ms.SHAPES_SHA_V2} and b["header"]["cross"] == {"version": mx.CROSS_VERSION}
    assert "keep_unshaped" in b["tools"] and "keep_unshaped" in b["rules"]
    s3 = new_store(tmp_path, "v3").begin("m", profile="mem.v3")
    assert "shape" not in s3.rows()[0]["result"]["header"] and "keep_unshaped" not in s3.rows()[0]["result"]["tools"]
    assert refusal(s3.call("keep_unshaped", {"text": "a"})) == "unknown_tool"


def test_a_sentence_whose_every_clause_has_a_shape_is_accepted_and_says_so(tmp_path):
    s = sess(tmp_path)
    r = s.write("認証の期限は金曜")
    assert r["ok"] and r["sid"] == 0 and r["weave"] == "ok"
    assert r["shape"]["clauses"] == [{"k": 0, "shape": "F1", "text": "認証の期限は金曜", "tank": "F1", "centre": "期限", "via": None, "nest": None, "value": "金曜", "change": None}]
    assert r["index"]["crosses"] == 1 and r["index"]["seats"] == 2 and len(r["index"]["sha"]) == 64
    assert r["crosses"] and r["units"]                                    # the loom's own weave is still made


def test_an_f0_clause_refuses_the_whole_write_with_its_reason_and_stores_nothing(tmp_path):
    s = sess(tmp_path)
    s.write("認証の期限は金曜")
    for text, reason in (("田中です", "no_relation"), ("担当表では認証モジュール担当は田中です", "gap_is_not_a_particle"), ("彼は担当ではない", "negated"),
                         ("認証の期限は金曜。田中です", "no_relation"), ("監視設定メモ:", "no_clause")):
        r = s.write(text)
        assert refusal(r) == "no_shape" and r["detail"]["shape"] == "F0" and r["detail"]["reason"] == reason, (text, r)
        assert "keep_unshaped" in r["detail"]["hint"]
    assert s.status()["sentences"] == 1 and s.status()["index"]["crosses"] == 1                       # nothing was stored, no cross changed
    assert s.status()["refused_writes"] == {"no_shape": 5}
    ev = s.events()                                                                                   # a shape detection, as `span_inexpressible` is today
    assert ev["unseatable"]["total"] == 5 and ev["unseatable"]["by_reason"]["no_relation"] == 2 and ev["rewrites"]["refused"] == 5


def test_a_text_that_is_too_long_or_has_a_bad_role_is_refused_as_before(tmp_path):
    s = sess(tmp_path)
    assert refusal(s.write("あ" * 65)) == "args_too_large"                                              # the loom's own guard on the arguments comes first, for both tools
    assert refusal(s.call("keep_unshaped", {"text": "あ" * 65})) == "args_too_large"
    assert refusal(s.call("keep_unshaped", {"text": "a\nb"})) == "bad_sentence"
    assert refusal(s.call("write", {"text": "認証の期限は金曜", "role": "robot"})) == "bad_args"


def test_keep_unshaped_stores_the_sentence_in_the_f0_tank_searchable_as_text_with_no_cross_and_no_note(tmp_path):
    s = sess(tmp_path)
    s.write("認証の期限は金曜")
    n0, thread0, crosses0 = len(s.rows()), list(s.run.state.thread), len(s.run.state.crosses)
    k = s.call("keep_unshaped", {"text": "担当表では認証モジュール担当は田中です"})
    assert k["ok"] and k["sid"] == 1 and k["tank"] == "F0" and k["unshaped"] is True and k["weave"] == "none"
    assert k["shape"]["reasons"] == ["gap_is_not_a_particle"] and "crosses" not in k and "notes" not in k
    assert k["index"]["crosses"] == 1 and k["index"]["f0"] == 1                                       # no cross was made
    assert len(s.rows()) == n0 + 1                                                                    # one row, and no loom_note row after it
    assert list(s.run.state.thread) == thread0 and len(s.run.state.crosses) == crosses0               # the loom's thread and crosses did not move
    hit = s.call("lookup", {"text": "田中", "tier": "WORD"})                                          # searchable as text
    assert hit["ok"] and hit["matches"][0]["sids"] == [1]
    assert s.call("read_sentence", {"sid": 1})["text"] == "担当表では認証モジュール担当は田中です"
    s.commit()
    h = mem.MemStore(str(tmp_path / "mem"))
    assert h.rows()[1]["unshaped"] is True and "unshaped" not in h.rows()[0]
    assert '"unshaped":true' in open(str(tmp_path / "mem" / "memory.jsonl"), encoding="utf-8").read()
    ix = h.index()
    assert len(ix.f0) == 1 and ix.f0[0].sid == 1 and ix.f0[0].reasons == ("gap_is_not_a_particle",) and [c.centre for c in ix.crosses] == ["期限"]


def test_keep_unshaped_refuses_a_sentence_that_has_a_shape_and_counts_as_a_write(tmp_path):
    s = sess(tmp_path)
    r = s.call("keep_unshaped", {"text": "認証の期限は金曜"})
    assert refusal(r) == "shaped" and r["detail"]["shapes"] == ["F1"]
    assert refusal(s.call("keep_unshaped", {"text": "。。。"})) == "bad_sentence"
    s.call("keep_unshaped", {"text": "田中です"})
    assert s.status()["writes"] == 3                                                                  # the cap of writes counts it (the refused ones too, as for write)
    assert s.status()["sentences"] == 1


def test_a_sentence_the_loom_cannot_weave_is_stored_anyway_and_the_row_says_so(tmp_path):
    s = sess(tmp_path)
    s.write("認証の期限は金曜")
    r = s.write("認証の期限は水曜から金曜に変更")
    assert r["ok"] and r["weave"].startswith("refused(span_inexpressible") and r["weave_refused"].startswith("span_inexpressible:")
    assert r["crosses"] == [] and r["units"] == [] and "notes" not in r
    assert r["shape"]["clauses"][0]["change"] == "kara_ni_henkou" and r["index"]["seats"] == 4
    s.commit()
    st = mem.MemStore(str(tmp_path / "mem"))
    assert st.rows()[1]["weave_refused"].startswith("span_inexpressible") and "weave_refused" not in st.rows()[0]
    assert len(st.index().cross("F1", "期限").seats_of("は")) == 2                                      # the tanks hold it
    s2 = st.begin("m", profile=V4)                                                                    # a later session carries the store: the unwoven row is not woven again
    assert s2.run.rows0 == 2 and len(s2.run.state.thread) == 2                                        # the thread holds the first sentence only (two crosses): the second was never woven, nor carried
    s2.write("決済の期限は月曜")
    s2.commit()
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"


def test_nothing_is_put_in_front_of_the_text(tmp_path):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "展示会準備"})
    r = s.write("締め切りは水曜")
    assert r["ok"] and r["text"] == "締め切りは水曜" and "implicit_topic" not in r
    assert s.run.rows[0]["sent"] == "締め切りは水曜" and "topic_at" not in s.run.rows[0]
    v3 = new_store(tmp_path, "v3").begin("m", profile="mem.v3")
    v3.call("declare_topic", {"text": "展示会準備"})
    assert v3.write("締め切りは水曜")["text"] == "展示会準備の締め切りは水曜"                                 # mem.v3 still prefixes


def test_one_cross_per_centre_phrase_in_each_tank_with_the_shapes_in_their_own_tank():
    ix = mx.build_index(rows(["認証の期限は金曜", "決済の期限は月曜", "期限は水曜", "認証モジュール担当は田中です", "田中が資料を作成した", "資料を送付した"]))
    assert [(c.tank, c.centre) for c in ix.crosses] == [("F1", "期限"), ("F2", "期限"), ("F2", "認証モジュール担当"), ("F3", "作成"), ("F4", "送付")]
    c = ix.cross("F1", "期限")
    assert [s.phrase for s in c.seats_of("の")] == ["決済", "認証"] or [s.phrase for s in c.seats_of("の")] == ["認証", "決済"]
    assert sorted(s.phrase for s in c.seats_of("は")) == ["月曜", "金曜"]
    assert ix.cross("F2", "期限").seats_of("は")[0].phrase == "水曜" and ix.cross("F1", "認証モジュール担当") is None
    f3 = ix.cross("F3", "作成")
    assert [(a, [s.phrase for s in ss]) for a, ss in f3.slots] == [("を", ["資料"]), ("が", ["田中"])]
    assert ix.tank("F4")[0].centre == "送付"                                                          # an F4 clause with no nest stays in the F4 tank, uncompleted
    assert ix.stats()["F1"] == {"crosses": 1, "seats": 4, "max_L": 3} and ix.stats()["F0"] == {"sentences": 0}


def test_a_seat_has_phrase_units_and_provenance_sid_turn_session_origin_surface():
    rs = rows(["認証の期限は金曜", "認証の担当は田中"], session=1)
    rs += rows(["認証の期限は水曜"], session=2, start=0)
    rs[1]["turn"] = "1-2"
    ix = mx.build_index(rs)
    c = ix.cross("F1", "期限")
    vs = {s.prov.sid: s for s in c.seats_of("は")}
    assert vs[0].prov == mx.Prov(0, None, 1, "constructed", "金曜", 0) and vs[0].phrase == "金曜" and vs[0].units == ("金曜",)
    assert vs[2].prov.session == 2 and vs[2].prov.origin == "constructed"                              # 水曜 is a word nobody wrote before
    nin = {s.prov.sid: s for s in c.seats_of("の")}
    assert nin[0].prov.origin == "constructed" and nin[2].prov.origin == "record" and nin[2].prov.session == 2         # 認証 was written in sentence 0 and 1
    assert ix.cross("F1", "担当").seats_of("は")[0].prov.turn == "1-2"
    assert c.occurrences[0] == mx.Prov(0, None, 1, "constructed", "期限", 0)


def test_an_event_centre_is_the_dictionary_form_and_the_written_verb_is_its_provenance():
    ix = mx.build_index(rows(["田中が会議を開いた", "佐藤が会議を開く", "52本保管します", "資料送付済み"]))
    c = ix.cross("F3", "開く")
    assert [o.surface for o in c.occurrences] == ["開いた", "開く"]
    assert [s.phrase for s in c.seats_of("を")] == ["会議", "会議"] and sorted(s.phrase for s in c.seats_of("が")) == ["佐藤", "田中"]
    p = ix.cross("F4", "保管")
    assert p.seats_of("quantity")[0].phrase == "52本" and p.seats_of("quantity")[0].units[0] == "52" and p.centre == "保管"
    assert ix.cross("F4", "送付").seats_of("object_bare")[0].phrase == "資料"


def test_a_chain_nests_Z_carries_Y_whose_own_arm_is_X():
    ix = mx.build_index(rows(["A社のB事業の担当は田中です"]))
    c = ix.cross("F1", "担当")
    y = c.seats_of("の")[0]
    assert y.phrase == "B事業" and [(p, s.phrase) for p, s in y.arms] == [("の", "A社")] and y.arms[0][1].path == (("の", "B事業"),)
    assert [s.phrase for s in ix.seats(c, "の")] == ["B事業"]
    assert [s.phrase for s in ix.seats(c, (("の", "B事業"), ("の", None)))] == ["A社"]
    assert [s.phrase for s in ix.seats(c, (("の", "B事業"), "の"))] == ["A社"] and ix.seats(c, (("の", "C事業"), ("の", None))) == ()
    assert [s.path for s in ix.value_seats(c)] == [(("の", "B事業"), ("の", "A社"))]
    assert ix.value_seats(c, (("の", "B事業"), ("の", "A社")))[0].phrase == "田中" and ix.value_seats(c, (("の", "B事業"),)) == ()
    assert ix.stats()["F1"]["seats"] == 3                                                              # Y, X and the value: the nested seat is counted


def test_centres_with_finds_a_phrase_as_a_centre_a_seat_a_nested_seat_or_a_value():
    ix = mx.build_index(rows(["A社のB事業の担当は田中です", "田中が資料を作成した", "担当は佐藤です"]))
    assert ix.centres_with("担当") == (("F1", "担当", "centre"), ("F2", "担当", "centre"))
    assert ix.centres_with("A社") == (("F1", "担当", "の>の"),)
    assert ix.centres_with("田中") == (("F1", "担当", "は"), ("F3", "作成", "が"))
    assert ix.centres_with("存在しない") == () and mx.centres_with(ix, "B事業") == (("F1", "担当", "の"),)


def test_no_seat_is_ever_dropped_and_an_arm_that_outgrows_its_rings_gets_an_outer_ring():
    n = 9
    ix = mx.build_index(rows(["部署%dの予算は%d万円" % (k, 10 + k) for k in range(n)]))
    c = ix.cross("F1", "予算")
    assert len(c.seats_of("の")) == n and len(c.seats_of("は")) == n                                    # faithful: 9 seats on the の arm, 9 values
    assert c.L == n + 1                                                                                # the foundation ring + one data ring per seat
    assert [s.ring for s in c.seats_of("の")] == list(range(1, n + 1)) and [s.rank for s in c.seats_of("の")] == list(range(n))
    assert all(s.ring == 0 for s in c.seats_of("は"))                                                  # the centre relation has no ring
    one = mx.build_index(rows(["認証の期限は金曜"])).cross("F1", "期限")
    assert one.L == 2                                                                                  # one data seat per arm: the loom's own L = 2
    assert mx.build_index(rows(["期限は金曜"])).cross("F2", "期限").L == 1                              # a cross with no arm seat is the centre alone
    assert ix.stats()["F1"]["max_L"] == n + 1


def test_the_key_of_a_seat_is_the_looms_key_against_the_history_before_its_sentence():
    rs = rows(["認証の期限は金曜", "認証の期限は水曜", "決済の期限は月曜", "認証の担当は田中"])
    ix = mx.build_index(rs)
    c = ix.cross("F1", "期限")
    corpus = Corpus(mx._rows_bytes(rs[:2]))                                                             # C_<2: what the seat of sentence 2 was keyed against
    t, adh, w = corpus.tier("WORD"), corpus.adhesion["WORD"], corpus.weights("WORD")
    g = geo.Cross.make(L=2, center="期限", arms=[[("決済" if a == "の" else None), fd.token(a)] for a in ("の", "に", "で", "と", "を", "が")])
    n, p, a = pl.seated_key(t, adh, g, w)
    seat = [s for s in c.seats_of("の") if s.prov.sid == 2][0]
    assert seat.key[:2] == (n, p) and seat.key[2] == 144 * adh.adj("決済", "の") == 0                 # a = numerator(の) * adj(決済, の) over the history only
    first = [s for s in c.seats_of("の") if s.prov.sid == 0][0]
    assert first.key == (0, 0, 0)                                                                       # sentence 0 has no history: a sentence never confirms itself
    s1 = [s for s in c.seats_of("の") if s.prov.sid == 1][0]
    assert s1.key[0] == 1 and s1.key[2] == 144 * 1                                                      # 認証 and 期限 were together once, 認証 was followed by の once
    assert [s.prov.sid for s in c.seats_of("の")] == [1, 0, 2] and [s.rank for s in c.seats_of("の")] == [0, 1, 2]       # key larger first, then the earlier sid


def test_seats_of_an_arm_are_ordered_by_the_key_and_ties_by_the_earlier_sid():
    ix = mx.build_index(rows(["甲の予算は1万円", "乙の予算は2万円", "丙の予算は3万円"]))
    s = ix.cross("F1", "予算").seats_of("の")
    assert [x.key for x in s] == [(0, 0, 0)] * 3 and [x.prov.sid for x in s] == [0, 1, 2] and [x.phrase for x in s] == ["甲", "乙", "丙"]
    for arm in ix.crosses:
        for slot, seats in arm.slots:
            ks = [(-x.key[0], -x.key[1], -x.key[2], x.prov.sid) for x in seats]
            assert ks == sorted(ks)


def test_a_committed_seat_is_frozen_later_sentences_add_seats_but_change_no_key_or_provenance():
    rs = rows(["認証の期限は金曜", "決済の期限は月曜", "認証の担当は田中", "決済の期限は水曜", "認証の期限は木曜"])
    early = mx.build_index(rs[:3]).cross("F1", "期限")
    late = mx.build_index(rs).cross("F1", "期限")
    mine = {(s.slot, s.prov): s for _, ss in late.slots for s in ss}
    for _, ss in early.slots:
        for s in ss:
            l = mine[(s.slot, s.prov)]
            assert (l.phrase, l.units, l.key, l.path, l.arms) == (s.phrase, s.units, s.key, s.path, s.arms)      # the seat itself is the same (its rank among the new ones may move)
    assert len(late.seats_of("は")) == 4 and len(early.seats_of("は")) == 2


def test_supersede_only_adds_a_mark_history_is_kept():
    rs = rows(["認証の期限は金曜", "認証の期限は水曜"])
    a = mx.build_index(rs)
    b = mx.build_index(rs, superseded={0: {"by": 1, "reason": "変更", "session": 1}})
    sa = [(s.phrase, s.prov, s.key, s.marks) for s in a.cross("F1", "期限").seats_of("は")]
    sb = [(s.phrase, s.prov, s.key, s.marks) for s in b.cross("F1", "期限").seats_of("は")]
    assert [x[:3] for x in sa] == [x[:3] for x in sb] and all(x[3] == () for x in sa)
    assert [x[3] for x in sb if x[1].sid == 0] == [(mx.Mark("superseded", 1, "変更", 1),)] and [x[3] for x in sb if x[1].sid == 1] == [()]
    assert a.index_sha != b.index_sha and b.stats() == a.stats()                                        # nothing was deleted: same crosses, same seats
    assert "[superseded by s1]" in mx.render_cross(b.cross("F1", "期限"))


def test_the_index_is_a_pure_function_of_h_and_the_same_twice():
    rs = rows(["認証の期限は金曜", "田中が資料を作成した", "資料を送付した", "認証の期限は水曜"])
    decls = [{"session": 1, "at": 2, "topic": "新製品"}]
    a, b = mx.build_index(rs, decls), mx.build_index(rs, decls)
    assert a.index_sha == b.index_sha and a.to_obj() == b.to_obj()
    assert mx.build_index(rs).index_sha != a.index_sha                                                  # the declaration is part of the function
    assert mx.build_index(rs[:2]).index_sha != mx.build_index(rs[:3]).index_sha


def test_fold_equals_one_pass_for_sessions_1_to_k(tmp_path):
    """T-MEM-10 for the index: the index the store carries into session k+1 (built incrementally by the run) is the pure index of the same H, declarations and marks, for k in 1, 2, 3."""
    plan = [["認証の期限は金曜", "田中が資料を作成した", "会議を開いた"], ["認証の期限は水曜から金曜に変更", "決済の期限は月曜", "資料を送付した"], ["決済の期限は金曜に延期した", "担当は佐藤です"]]
    st = new_store(tmp_path)
    for k, texts in enumerate(plan, 1):
        s = st.begin("m", profile=V4)
        carried = s.run.builder.index()
        head, rs = st.check()
        assert carried.index_sha == mx.build_index(rs, [d for e in (head["sessions"] if head else []) for d in mem.session_nest_decls(st.sessions_dir / e["run_id"])], {}).index_sha
        if k == 2:
            s.call("declare_topic", {"text": "新製品"})
        for t in texts:
            assert s.write(t)["ok"]
        live = s.run.builder.index()
        s.commit()
        assert live.index_sha == st.index().index_sha
        assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"
    one = mx.build_index([r for r in st.rows()], [{"session": 2, "at": 3, "topic": "新製品"}])
    assert one.index_sha == st.index().index_sha and one.n == 8
    inc = mx.IndexBuilder(ms.SHAPES_V2)                                                                 # the builder folded sentence by sentence, with the index asked for in between
    prev = Corpus(b"")
    for t, r in enumerate(st.rows()):
        if t == 3:
            inc.declare(2, 3, "新製品")
        inc.add_row(t, r, prev)
        inc.index()
        prev = Corpus(mx._rows_bytes(st.rows()[:t + 1]))
    assert inc.index().index_sha == one.index_sha


def test_mem_replay_rebuilds_the_index_identically_and_every_row_state_carries_its_sha(tmp_path):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "A社のB事業"})
    s.write("認証の期限は金曜")
    s.write("資料を送付した")
    s.call("keep_unshaped", {"text": "担当表では認証モジュール担当は田中です"})
    s.write("認証の期限は水曜から金曜に変更")
    sha = s.run.builder.index().index_sha
    s.commit()
    rep = mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER)
    assert rep.identical and rep.sessions == 1
    assert mem.MemStore(str(tmp_path / "mem")).index().index_sha == sha
    states = [r["state_sha"] for r in s.rows() if r["actor"] == "model"]
    assert len(set(states)) >= 5                                                                         # the state moves with the index at every write
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"


def test_the_replay_catches_a_nest_declaration_that_is_not_the_ones_recorded(tmp_path, monkeypatch):
    s = sess(tmp_path)
    s.call("declare_topic", {"text": "新製品"})
    s.write("資料を送付した")
    s.commit()
    assert mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER).identical
    real = mx.IndexBuilder.add_row

    def bad(self, sid, row, corpus):                                                                     # an index that places an F4 clause without the nest: the recorded state sha cannot match
        self._open.clear()
        return real(self, sid, row, corpus)
    monkeypatch.setattr(mx.IndexBuilder, "add_row", bad)
    assert not mem.replay_store(str(tmp_path / "mem"), mem.FROM_HEADER).identical


def test_an_older_profile_session_after_a_v4_one_still_carries(tmp_path):
    s = sess(tmp_path)
    s.write("認証の期限は金曜")
    s.commit()
    s2 = new_store(tmp_path).begin("m", profile="mem.v3")
    assert s2.write("決済の期限は月曜")["ok"]
    s2.commit()
    assert mem.verify_store(str(tmp_path / "mem"), mem.FROM_HEADER)["status"] == "OK"
    assert len(mem.MemStore(str(tmp_path / "mem")).index().cross("F1", "期限").seats_of("は")) == 2


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_the_index_is_byte_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memcross as mx;from verantyx.loom.memguard import make_source as m;"
            "S=['認証の期限は金曜','決済の期限は月曜','認証の期限は水曜から金曜に変更','田中が会議を開いた','会議を開く','資料送付済み','A社のB事業の担当は田中です','52本保管します','期限は金曜に延期した'];"
            "R=[{'kind':'base','sent':s,'source':m('t',1 if i<5 else 2,i)} for i,s in enumerate(S)];"
            "ix=mx.build_index(R,[{'session':1,'at':3,'topic':'新製品'},{'session':2,'at':5,'topic':'A社のB事業'}],{0:{'by':2,'reason':'x','session':1}});"
            "print(ix.index_sha);print(json.dumps(ix.to_obj(),ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and len(out.split("\n")[0]) == 64


FORBIDDEN_IMPORTS = {"time", "datetime", "random", "subprocess", "socket", "os", "sys", "uuid", "secrets", "urllib", "http", "requests"}


@pytest.mark.parametrize("fn", ["memcross.py", "memshape.py"])
def test_memcross_and_memshape_have_no_clock_float_process_network_or_set_order(fn):
    tree = ast.parse(open(os.path.join(ROOT, "verantyx", "loom", fn), encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not ({a.name.split(".")[0] for a in n.names} & FORBIDDEN_IMPORTS)
        if isinstance(n, ast.ImportFrom) and n.module:
            assert n.module.split(".")[0] not in FORBIDDEN_IMPORTS
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id not in ("float", "set", "frozenset", "eval", "exec", "open", "print")
        if isinstance(n, (ast.Div, ast.Set, ast.SetComp)):
            raise AssertionError("true division or a set in " + fn)


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_a_v4_store_replays_identically_in_another_process_under_every_hash_seed(tmp_path, seed):
    st = new_store(tmp_path)
    s = st.begin("m", profile=V4)
    s.call("declare_topic", {"text": "A社のB事業"})
    for t in ("認証の期限は金曜", "認証の期限は水曜", "資料を送付した", "認証の期限は木曜から日曜に変更"):
        assert s.write(t)["ok"]
    assert s.call("keep_unshaped", {"text": "担当表では認証モジュール担当は田中です"})["ok"]
    assert s.call("supersede", {"new_sid": 1, "old_sid": 0, "reason": "変更"})["ok"]
    s.commit()
    s2 = st.begin("m", profile=V4)
    s2.write("会議を開いた")
    s2.commit()
    code = ("import json,sys;from verantyx.loom import memory as m;r=m.replay_store(sys.argv[1],m.FROM_HEADER);v=m.verify_store(sys.argv[1],m.FROM_HEADER);"
            "print(json.dumps([r.status,v['status'],m.MemStore(sys.argv[1]).index().index_sha]))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code, str(tmp_path / "mem")], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    assert json.loads(out) == ["IDENTICAL", "OK", st.index().index_sha]

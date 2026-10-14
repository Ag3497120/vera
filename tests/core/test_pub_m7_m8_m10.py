"""PUB-M7 / M8 / M10-prep tests: the model-facing window and the per-turn budget (verantyx/loom/memview.py), the flat-table index of the A3f arm (memcross.IndexBuilder(flat=True), versions.index = flat.v1),
the log arm of membase.v3 (log_grep, log_read(start, end), the budget in the begin row), and the meter-v2 harness with the deterministic stub client (tests/fixtures/line3/pub/meter2/).  No network, no API."""


import ast


import hashlib


import importlib


import json


import os


import subprocess


import sys


import pytest


from verantyx.loom import driver as drv


from verantyx.loom import ledger as lg


from verantyx.loom import memanswer as ma


from verantyx.loom import memcross as mx


from verantyx.loom import memdoor as md


from verantyx.loom import memory as mem


from verantyx.loom import memview as mv


from verantyx.loom.memguard import make_source


from verantyx.loom.state import Refuse


from mem_common import ROOT, new_store


V4 = mem.PROFILE_V4


FLAT = {"index": mem.INDEX_FLAT}


def rows(texts, session=1, start=0):
    return [{"kind": "base", "sent": t, "source": make_source("t", session, start + i)} for i, t in enumerate(texts)]


def sess(tmp_path, name="mem", **kw):
    return new_store(tmp_path, name).begin("test-model", profile=V4, **kw)


TEXTS = ["認証の決済は金曜", "認証の期限は金曜", "決済の認証は月曜", "広報の担当は山本", "認証の期限は金曜から水曜に変更", "決済の期限は月曜", "認証の期限は木曜"]


def seatset(ix):
    out = []
    for c in ix.crosses:
        for slot, seats in c.slots:
            for s in seats:
                out.append((c.tank, c.centre, slot, s.phrase, s.prov.sid, s.prov.origin))
    return sorted(out)


def test_the_flat_index_has_no_nests_no_slide_edges_no_key_and_no_key_swap():
    rs = rows(TEXTS)
    decls = [{"session": 1, "at": 1, "topic": "新製品"}]
    cr, fl = mx.build_index(rs, decls), mx.build_index(rs, decls, flat=True)
    assert fl.flat and not cr.flat
    assert fl.nests == () and len(cr.nests) == 1
    assert fl.edges == () and len(cr.edges) == len(TEXTS) - 1
    assert all(s.key == (0, 0, 0) for c in fl.crosses for _, seats in c.slots for s in seats)
    assert fl.index_sha != cr.index_sha and fl.to_obj()["v"] == mx.FLAT_VERSION and cr.to_obj()["v"] == mx.CROSS_VERSION
    assert seatset(fl) == seatset(cr)                                                                      # the same seats, values and provenance: what differs is the geometry
    fx = [n for n in fl.notes if n["type"] == "REVERSAL_X"]
    cx = [n for n in cr.notes if n["type"] == "REVERSAL_X"]
    assert len(fx) == len(cx) == 1 and fx[0]["key"] is None and cx[0]["key"] is not None             # the pair direction is compared in both; the key swap only in the crosses
    assert [n["type"] for n in fl.notes] == [n["type"] for n in cr.notes]                                 # same detections here
    # the topic is a plain column: the scope of the seats written under it
    assert {s.scope for c in fl.crosses for _, seats in c.slots for s in seats if s.prov.sid >= 1} == {"新製品"}
    assert {s.scope for c in cr.crosses for _, seats in c.slots for s in seats if s.prov.sid >= 1} == {"N1"}


def test_the_flat_index_orders_seats_by_sid_and_an_event_stays_uncompleted_without_a_nest():
    rs = rows(["認証の期限は金曜", "決済の期限は月曜", "広報の期限は水曜", "資料を送付した"])
    fl = mx.build_index(rs, [{"session": 1, "at": 0, "topic": "新製品"}], flat=True)
    c = fl.cross("F1", "期限")
    assert [s.prov.sid for s in c.seats_of("は")] == [0, 1, 2] and [s.rank for s in c.seats_of("は")] == [0, 1, 2]
    assert fl.cross("F4", "送付") is not None and fl.cross("F3", "送付") is None                              # no nest completes the F4 clause
    cr = mx.build_index(rs, [{"session": 1, "at": 0, "topic": "新製品"}])
    assert cr.cross("F3", "送付") is not None


def test_the_flat_incremental_index_equals_the_full_rebuild():
    rs = rows(TEXTS)
    b = mx.IndexBuilder(flat=True)
    from verantyx.loom.corpus import Corpus
    prev = Corpus(b"")
    for t, r in enumerate(rs):
        if t == 2:
            b.declare(1, 2, "新製品")
        b.add_row(t, r, prev)
        b.index()
        prev = Corpus(mx._rows_bytes(rs[:t + 1]))
    assert b.index().index_sha == mx.build_index(rs, [{"session": 1, "at": 2, "topic": "新製品"}], flat=True).index_sha


def test_a_flat_session_records_the_index_version_and_replays_and_a_crosses_session_records_nothing_new(tmp_path):
    s = sess(tmp_path, "flat", versions=dict(mem.V4_VERSIONS_M6D, **FLAT))
    h = s.rows()[0]["result"]["header"]
    assert h["index"] == {"version": "flat.v1"} and "view" not in h
    s.call("declare_topic", {"text": "新製品"})
    for t in TEXTS[:5]:
        assert s.write(t)["ok"]
    sha = s.run.builder.index().index_sha
    s.commit()
    assert mem.verify_store(str(tmp_path / "flat"), mem.FROM_HEADER)["status"] == "OK"
    assert mem.MemStore(str(tmp_path / "flat")).index().index_sha == sha and mem.MemStore(str(tmp_path / "flat")).index().flat
    c = sess(tmp_path, "cross")
    hc = c.rows()[0]["result"]["header"]
    assert "index" not in hc and "view" not in hc and hc["cross"] == {"version": mx.CROSS_VERSION}
    assert mem.check_versions({"index": mx.CROSS_VERSION}) == mem.V4_VERSIONS_V2 and mem.check_versions(FLAT)["index"] == mem.INDEX_FLAT
    with pytest.raises(Refuse):
        mem.check_versions({"index": "flat.v2"})


def test_one_store_one_bundle_a_flat_store_refuses_a_crosses_session(tmp_path):
    s = sess(tmp_path, "m", versions=FLAT)
    s.write("認証の期限は金曜")
    s.commit()
    with pytest.raises(Refuse) as e:
        new_store(tmp_path, "m").begin("test-model", profile=V4)
    assert e.value.type == "policy_mismatch"


def test_the_answer_run_over_a_flat_store_reads_the_flat_table_and_says_so(tmp_path):
    s = sess(tmp_path, "f", versions=dict(mem.V4_VERSIONS_M6D, **FLAT))
    s.call("declare_topic", {"text": "新製品"})
    for t in ("認証の期限は金曜", "決済の期限は月曜"):
        s.write(t)
    s.commit()
    snap = ma.write_snapshot(str(tmp_path / "f"), crosses=True, versions=True)
    a = ma.AnswerSession(str(tmp_path / "f"), "認証の期限は何ですか", "test-model", snapshot=snap, answer_version=ma.ANSWER_V17)
    assert a.begin_result["mem_answer"]["index"] == mem.INDEX_FLAT and a.run.index().flat
    r = a.call("recall", {"question": "認証の期限は何ですか"})
    assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == ["金曜"]
    w = a.call("weave_span", {"sid": r["answers"][0]["occurrences"][0]["sid"], "tier": "WORD", "first": r["answers"][0]["occurrences"][0]["span"][0], "last": r["answers"][0]["occurrences"][0]["span"][1]})
    assert w["ok"] and a.call("emit", {})["ok"]
    assert ma.verify_answer(a.ledger.dir, str(tmp_path / "f"))["status"] == "OK"
    c = sess(tmp_path, "c")
    c.write("認証の期限は金曜")
    c.commit()
    sn = ma.write_snapshot(str(tmp_path / "c"), crosses=True, versions=True)
    assert "index" not in ma.AnswerSession(str(tmp_path / "c"), "認証の期限は何ですか", "m", snapshot=sn, answer_version=ma.ANSWER_V17).begin_result["mem_answer"]


def test_a_session_with_a_view_records_budget_and_lines_and_offers_view_and_view_nest(tmp_path):
    s = sess(tmp_path, "v", view=mv.make_view(1234, 20))
    b = s.rows()[0]["result"]
    assert b["header"]["view"] == {"version": "view.v1", "budget": 1234, "lines": 20} and b["task"]["caps"]["views"] == 240
    assert b["tools"][-2:] == ["view", "view_nest"] and mem.caps_of(V4, True) == dict(mem.CAPS_MEM_V4, views=240)
    plain = sess(tmp_path, "p")
    assert "view" not in plain.rows()[0]["result"]["tools"] and plain.call("view", {"centre": "期限"})["refusal"] == "unknown_tool"
    with pytest.raises(Refuse):
        mv.check_view({"version": "view.v1", "budget": 5, "lines": 40})
    with pytest.raises(Refuse):
        new_store(tmp_path, "x").begin("m", profile="mem.v3", view=mv.make_view())


def test_view_and_view_nest_show_seats_with_provenance_capped_and_replay(tmp_path):
    s = sess(tmp_path, "v", view=mv.make_view(6000, 6))
    s.call("declare_topic", {"text": "新製品"})
    for t in TEXTS + ["広報の期限は水曜", "営業の期限は木曜"]:
        s.write(t)
    v = s.call("view", {"centre": "期限"})
    assert v["ok"] and v["kind"] == "cross" and v["total"] > 6 and len(v["lines"]) == 6 and v["lines"][-1].startswith("… ") and v["omitted"] == v["total"] - 6
    assert v["lines"][0].startswith("X F1 期限") and "s1" in v["lines"][0]
    full = sess(tmp_path, "w", view=mv.make_view(6000, 40))
    for t in TEXTS:
        full.write(t)
    lines = full.call("view", {"centre": "期限"})["lines"]
    assert any(" S1 record" in ln and ln.lstrip().startswith("は#") for ln in lines) and any(ln.startswith("H F1 ") and "update" in ln for ln in lines)
    n = s.call("view_nest", {"topic": "新製品"})
    assert n["kind"] == "nest" and n["lines"][0].startswith("N N1 新製品") and n["ok"]
    assert s.call("view", {"centre": "存在しない"})["lines"][0].startswith("? nothing")
    assert s.call("view", {"centre": ""})["refusal"] == "bad_centre"
    assert s.call("view_nest", {"topic": "旧"})["lines"][0].startswith("? no nest")
    s.commit()
    assert mem.verify_store(str(tmp_path / "v"), mem.FROM_HEADER)["status"] == "OK"            # the view rows replay (the counter is part of the state hash)


def test_the_flat_view_shows_no_key_and_the_topic_column_as_a_table(tmp_path):
    s = sess(tmp_path, "f", versions=FLAT, view=mv.make_view())
    s.call("declare_topic", {"text": "新製品"})
    for t in TEXTS:
        s.write(t)
    lines = s.call("view", {"centre": "期限"})["lines"]
    assert not any("key=(" in ln for ln in lines)
    n = s.call("view_nest", {"topic": "新製品"})
    assert n["kind"] == "table" and "topic column" in n["lines"][0] and len(n["lines"]) > 3
    c = sess(tmp_path, "c", view=mv.make_view())
    c.call("declare_topic", {"text": "新製品"})
    for t in TEXTS:
        c.write(t)
    assert any("key=(" in ln for ln in c.call("view", {"centre": "期限"})["lines"])


def test_the_model_facing_write_is_short_lines_and_the_ledger_keeps_the_full_result(tmp_path):
    door = md.StructureDoor(str(tmp_path / "d"), "notes", "test-model", profile=V4, versions=dict(mem.V4_VERSIONS_M6D), view=mv.make_view())
    door.set_turn("1-1")
    out = []
    for t in TEXTS[:5]:
        out.append(door.call("write", {"text": t}))
    assert all(set(o) <= {"ok", "sid", "lines", "turn", "more"} for o in out) and out[0]["turn"] == "1-1"
    assert all(len(json.dumps(o, ensure_ascii=False)) < 700 for o in out)
    assert out[0]["lines"][0].startswith("+ F1 決済 [の:認証] = 金曜")
    assert any(ln.startswith("! REVERSAL_X") and "turns=1-1,1-1" in ln for ln in out[2]["lines"])
    assert any(ln.startswith("~ UPDATE") for ln in out[4]["lines"])
    ledger = [r for r in door.session.rows() if r["op"] == "write"]
    assert all(len(json.dumps(r["result"], ensure_ascii=False)) > 1000 and "crosses" in r["result"] for r in ledger)
    bad = door.call("write", {"text": "田中です"})
    assert bad["ok"] is False and bad["refusal"] == "no_shape"                                  # a refusal is passed on unchanged
    door.commit()
    door.close()


def test_the_flat_write_view_does_not_show_the_key_route_reversal_note():
    res = {"ok": True, "sid": 3, "turn": "1-4", "notes": [{"type": "REVERSAL", "sid": 3, "turn": "1-4", "earlier": [{"sid": 1, "turn": "1-2"}]}, {"type": "SAME_QUESTION", "sid": 3, "turn": "1-4"}]}

    class Ix:
        def clause_rec(self, sid, k):
            return None
    assert [ln for ln in mv.compact_write(Ix(), res)["lines"]] == ["! REVERSAL (key route) 1-4", "! SAME_QUESTION (gate route) 1-4"]
    assert mv.compact_write(Ix(), res, drop_key_route=True)["lines"] == ["! SAME_QUESTION (gate route) 1-4"]


class FakeDoor:
    def __init__(self, out):
        self.out, self.rows, self.turn = out, [], None

    def call(self, tool, args=None):
        return self.out[tool] if isinstance(self.out, dict) else self.out

    def set_turn(self, t):
        self.turn = t

    def harness(self, rid, op, args):
        self.rows.append((op, args))
        return {"ok": True}


def test_the_budget_cuts_a_result_with_the_marker_counts_the_turn_and_resets_on_the_next():
    big = {"ok": True, "lines": ["x" * 100] * 30}
    fd = FakeDoor({"view": big, "report": {"ok": True, "contradictions": [], "bugs": []}})
    bd = mv.BudgetDoor(fd, 1000, ledger=True)
    bd.set_turn("1-1")
    n = len(mv.result_text(big))
    r = bd.call("view", {})
    assert r["ok"] is True and r["budget_cut"].endswith("chars omitted]") and "[budget: %d chars omitted]" % (n - fd.rows[0][1]["kept"]) in r["budget_cut"]
    assert len(mv.result_text(r)) <= 1000 and fd.rows[0][0] == "budget_turn" and fd.rows[0][1]["chars"] == n and fd.rows[0][1]["kept"] + fd.rows[0][1]["omitted"] == n
    assert bd.call("report", {})["contradictions"] == [] and len(fd.rows) == 1                 # the control tools are neither cut nor counted
    r2 = bd.call("view", {})                                                                      # the turn is spent: only the marker comes back (soft by at most the marker)
    assert r2["budget_cut"].startswith("[budget:") and len(mv.result_text(r2)) < 100 and bd.spent <= 1000 + 100
    bd.set_turn("1-2")
    assert bd.spent == 0 and bd.call("view", {})["budget_cut"].startswith('{"l')
    small = mv.BudgetDoor(FakeDoor({"t": {"ok": True, "a": 1}}), 1000, ledger=False)
    assert small.call("t", {}) == {"ok": True, "a": 1} and small.events == []
    unledgered = mv.BudgetDoor(fd, 200, ledger=False)
    unledgered.call("view", {})
    assert len(fd.rows) == 3 and len(unledgered.events) == 1 and unledgered.events[0]["turn"] == "-"


def test_a_budget_turn_row_is_a_row_of_a_view_session_only_and_replays(tmp_path):
    s = sess(tmp_path, "b", view=mv.make_view(500, 40))
    s.write("認証の期限は金曜")
    row = {"turn": "1-1", "tool": "view", "budget": 500, "chars": 900, "kept": 400, "omitted": 500, "spent": 470}
    assert s.harness("budget_turn", row) == {"ok": True}
    with pytest.raises(ValueError):
        s.harness("budget_turn", dict(row, budget=600))
    with pytest.raises(ValueError):
        s.harness("budget_turn", dict(row, omitted=1))
    s.commit()
    assert mem.verify_store(str(tmp_path / "b"), mem.FROM_HEADER)["status"] == "OK"
    p = sess(tmp_path, "n")
    with pytest.raises(ValueError):
        p.harness("budget_turn", row)


def test_membase_v3_log_grep_ranks_by_terms_then_the_later_line_and_log_read_takes_a_range(tmp_path):
    door = md.BaselineDoor(str(tmp_path / "l"), "log", "story", "test-model", session_no=1, version=md.BASELINE_V3, budget=600)
    assert door.tool_names == ("log_append", "log_grep", "log_read", "report") and door.begin_result["header"]["budget"] == {"version": "view.v1", "budget": 600}
    for t in ("1-1 広報の担当は山本", "1-2 会場は大阪", "1-3 広報の期限は水曜", "1-4 広報の担当は中村"):
        assert door.call("log_append", {"text": t})["ok"]
    g = door.call("log_grep", {"terms": ["広報", "担当"], "max_lines": 2})
    assert [e["n"] for e in g["entries"]] == [0, 3] and g["matched"] == 3 and g["more"] == 1
    assert door.call("log_grep", {"terms": [], "max_lines": 5})["refusal"] == "bad_grep" and door.call("log_grep", {"terms": ["x"], "max_lines": 31})["refusal"] == "bad_grep"
    r = door.call("log_read", {"start": 1, "end": 2})
    assert [e["n"] for e in r["entries"]] == [1, 2] and r["entries"][0] == {"n": 1, "s": 1, "t": "1-2 会場は大阪"}
    assert door.call("log_read", {"start": 3, "end": 2})["refusal"] == "bad_range" and door.call("log_read", {"grep": "広報"})["refusal"] == "bad_args"
    assert door.call("log_read", {"start": 10, "end": 12})["entries"] == []
    door.harness(None, "budget_turn", {"turn": "1-1", "tool": "log_grep", "budget": 600, "chars": 700, "kept": 500, "omitted": 200, "spent": 560})
    door.set_turn("1-1")
    door.call("report", {"contradictions": [], "turn": "x"})
    door.commit()
    assert md.verify_baseline(str(door.ledger.dir))["status"] == "OK"
    q = md.BaselineDoor(str(tmp_path / "l"), "log", "question", "test-model", question="広報の担当は", version=md.BASELINE_V3, budget=600)
    assert q.tool_names == ("log_grep", "log_read", "answer") and len(q.run.entries) == 4
    assert md.verify_baseline(str(q.ledger.dir))["status"] == "OK"
    with pytest.raises(ValueError):
        md.BaselineRun("log", "story", "l0001", "m", 1, version=md.BASELINE_V2, budget=600)
    old = md.BaselineDoor(str(tmp_path / "o"), "log", "story", "test-model", session_no=1, version=md.BASELINE_V2)
    assert old.tool_names == md.STORY_TOOLS["log"] and "budget" not in old.begin_result["header"] and old.call("log_append", {"text": "a b"})["ok"]
    assert old.call("log_read", {"grep": "a"})["matched"] == 1
    with pytest.raises(ValueError):
        old.harness(None, "budget_turn", {"turn": "1-1", "tool": "t", "budget": 600, "chars": 1, "kept": 1, "omitted": 0, "spent": 1})
    assert md.api_tools(("log_read",), specs=md.TOOL_SPECS_V3)[0]["input_schema"]["required"] == ["start", "end"] and md.api_tools(("log_read",))[0]["input_schema"].get("required") is None


def test_the_scoring_classes():
    import scoring as S
    q = lambda kind, gold: {"q": "q", "kind": kind, "gold": gold, "checkpoint": 0}          # noqa: E731
    v = lambda *x: {"kind": "value", "values": list(x)}                                      # noqa: E731
    none, con = {"kind": "none", "values": []}, lambda *x: {"kind": "contested", "values": list(x)}   # noqa: E731
    assert S.classify(v("大阪"), q("plain", "大阪")) == "right" and S.classify(v("大阪市"), q("plain", "大阪")) == "over_broad" and S.classify(v("京都"), q("plain", "大阪")) == "confident_wrong"
    assert S.classify(none, q("plain", "大阪")) == "abstain" and S.classify(con("a", "b"), q("plain", "大阪")) == "confident_wrong" and S.false_contested(con("a", "b"), q("plain", "大阪"))
    assert S.classify(con("中村", "山本"), q("contradiction", "矛盾: 山本 と 中村")) == "right" and S.classify(v("山本"), q("contradiction", "矛盾: 山本 と 中村")) == "confident_wrong"
    assert S.classify(none, q("absent", "記録なし")) == "absent_admit" and S.classify(v("大阪"), q("absent", "記録なし")) == "confident_wrong"
    assert S.classify(v("福岡"), q("update", "福岡")) == "right" and S.classify(v("大阪"), q("update", "福岡")) == "confident_wrong"
    sc = S.score_answers([{"q": q("plain", "a"), "answer": v("a")}, {"q": q("absent", "記録なし"), "answer": none}, {"q": q("update", "b"), "answer": none}])
    assert sc["total"]["n"] == 3 and sc["total"]["right"] == 1 and sc["total"]["absent_admit"] == 1 and sc["total"]["abstain"] == 1 and sc["right_rate"] == 333 and sc["absent"]["absent_admit"] == 1


def micro_story():
    return {"id": "MICRO", "title": "micro", "sessions": [
        [{"speaker": "佐藤", "text": "広報の担当は山本です。"}, {"speaker": "田中", "text": "会議の会場は大阪です。"}, {"speaker": "鈴木", "text": "備品の期限は水曜です。"}],
        [{"speaker": "佐藤", "text": "広報の担当は中村です。"}, {"speaker": "田中", "text": "会議の会場は大阪から福岡に変更です。"}]],
        "plants": [{"kind": "contradiction", "fact": "x", "values": ["山本", "中村"], "message_refs": [[0, 0], [1, 0]], "note": ""},
                   {"kind": "update", "fact": "y", "values": ["大阪", "福岡"], "message_refs": [[1, 1]], "old_refs": [[0, 1]], "note": ""}],
        "checkpoints": [{"index": 0, "fraction": 0.5, "after_session": 0}, {"index": 1, "fraction": 1.0, "after_session": 1}],
        "questions": [{"q": "会議の会場は何ですか", "gold": "大阪", "kind": "plain", "checkpoint": 0, "refs": [[0, 1]]}, {"q": "総務の担当は何ですか", "gold": "記録なし", "kind": "absent", "checkpoint": 0, "refs": []},
                      {"q": "広報の担当は何ですか", "gold": "矛盾: 山本 と 中村", "kind": "contradiction", "checkpoint": 1, "refs": [[0, 0], [1, 0]]},
                      {"q": "会議の会場は何ですか", "gold": "福岡", "kind": "update", "checkpoint": 1, "refs": [[1, 1]]}]}


@pytest.fixture(scope="module")
def meter2():
    return importlib.import_module("meter2")


def run_micro(meter2, out, arms=("A0", "A1", "A3", "A3f"), budget=6000):
    import stub_client
    res = {}
    for a in arms:
        res[a] = meter2.run_one(micro_story(), a, 1, client=stub_client.StubClient(), model="stub-model", out_root=str(out), budget=budget, n_checkpoints=2)
    return res


def test_the_stub_meter_runs_all_four_arms_end_to_end_and_every_ledger_verifies(meter2, tmp_path):
    res = run_micro(meter2, tmp_path)
    for a, r in res.items():
        assert r["ended"] == "complete" and len(r["checkpoints"]) == 2 and r["answers"]["total"]["n"] == 4 and r["cost"]["turns_without_report"] == 0
    for a in ("A3", "A3f"):
        r = res[a]
        assert r["store"]["verify"] == "OK" and r["plants"]["contradiction"] == {"n": 1, "structure": 1, "model": 1, "any": 1} and r["plants"]["update"]["structure"] == 1
        assert r["answers"]["total"]["right"] == 3 and r["answers"]["by_kind"]["absent"]["absent_admit"] == 1 and r["answers"]["total"]["confident_wrong"] == 0
        for c in r["checkpoints"]:
            for x in c["answers"]:
                assert x["usage"]["input_tokens"] > 0
        base = os.path.join(str(tmp_path), "MICRO", a, "r01")
        for s in r["sessions"]:
            rows_ = meter2.read_rows(os.path.join(base, s["ledger"]))
            assert rows_[0]["result"]["header"]["view"]["budget"] == 6000
    assert res["A3f"]["store"]["sentences"] == res["A3"]["store"]["sentences"] == 5
    assert res["A0"]["answers"]["total"]["right"] == 0 and res["A0"]["answers"]["by_kind"]["absent"]["absent_admit"] == 1
    assert res["A1"]["plants"]["update"]["model"] is None and res["A1"]["plants"]["contradiction"]["any"] == 0
    for a in ("A0", "A1"):
        for d in meter2.story_ledger_dirs(os.path.join(str(tmp_path), "MICRO", a, "r01", "store")):
            assert md.verify_baseline(d)["status"] == "OK"
    path = meter2.write_report(str(tmp_path))
    text = open(path, encoding="utf-8").read()
    assert "STUB client" in text and "P-PUB-1" in text and "P-PUB-4" in text and "P2" in text and "P3" in text
    rep = json.load(open(os.path.join(str(tmp_path), "report.json"), encoding="utf-8"))
    assert rep["arms"] == ["A0", "A1", "A3", "A3f"] and set(rep["predictions"]) >= {"P-PUB-1", "P-PUB-2", "P-PUB-3", "P-PUB-4"}


def test_a_small_budget_cuts_story_results_and_leaves_budget_rows_in_every_ledger_that_verifies(meter2, tmp_path):
    res = run_micro(meter2, tmp_path, arms=("A3", "A1"), budget=100)
    assert res["A3"]["cost"]["budget_cuts"] > 0 and sum(s["budget_rows_in_ledger"] for s in res["A3"]["sessions"]) > 0 and res["A3"]["store"]["verify"] == "OK"
    assert all(s["budget_cuts"] == s["budget_rows_in_ledger"] for s in res["A3"]["sessions"])


def test_the_real_client_is_refused_without_the_flag_and_without_the_environment(meter2, monkeypatch, capsys):
    with pytest.raises(meter2.MeterError):
        meter2.make_client("api", False, "claude-haiku-5-5")
    monkeypatch.delenv("VERA_METER2_ALLOW_API", raising=False)
    with pytest.raises(meter2.MeterError):
        meter2.make_client("api", True, "claude-haiku-5-5")
    assert meter2.main(["--bank", "x", "--out", "y", "--client", "api"]) == 2 and "allow-api" in capsys.readouterr().err
    assert "anthropic" not in sys.modules


def test_a_held_out_split_needs_judge_is_single_use_and_writes_no_text(meter2, tmp_path, monkeypatch, capsys):
    held = tmp_path / "bank_ls" / "heldout_9"
    held.mkdir(parents=True)
    st = micro_story()
    (held / "stories.jsonl").write_text(json.dumps(st, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(meter2, "USED_FILE", str(tmp_path / "used.jsonl"))
    assert meter2.is_heldout(str(held)) and not meter2.is_heldout(str(tmp_path / "dev"))
    assert meter2.main(["--bank", str(held), "--arms", "A0", "--checkpoints", "1", "--out", str(tmp_path / "o1")]) == 2 and "--judge" in capsys.readouterr().err
    assert meter2.main(["--bank", str(held), "--arms", "A0", "--checkpoints", "1", "--judge", "--out", str(tmp_path / "o1")]) == 0
    out = capsys.readouterr().out
    assert "(held-out)" in out and "MICRO" not in out and "広報" not in out
    r = json.load(open(tmp_path / "o1" / "MICRO" / "A0" / "r01" / "result.json", encoding="utf-8"))
    assert r["redacted"] is True and all("q" not in x and "gold" not in x and "answer" not in x for c in r["checkpoints"] for x in c["answers"])
    assert meter2.main(["--bank", str(held), "--arms", "A0", "--checkpoints", "1", "--judge", "--out", str(tmp_path / "o2")]) == 2 and "single-use" in capsys.readouterr().err
    assert meter2.main(["--bank", str(held), "--arms", "A0", "--checkpoints", "1", "--judge", "--allow-reuse", "--out", str(tmp_path / "o3")]) == 0


def test_the_plan_writes_nothing_and_the_report_ranges(meter2, tmp_path, capsys):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps(micro_story(), ensure_ascii=False) + "\n", encoding="utf-8")
    assert meter2.main(["--bank", str(p), "--plan", "--repeats", "3", "--checkpoints", "2"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["runs"] == 12 and plan["plan"][0]["sessions_fed"] == 2 and not os.path.exists(tmp_path / "out")
    assert meter2.beats({1: 5, 2: 6}, {1: 3, 2: 4}) is True and meter2.beats({1: 4, 2: 6}, {1: 3, 2: 4}) is False and meter2.beats({}, {1: 1}) is None
    assert meter2.beats({1: 1, 2: 2}, {1: 3, 2: 4}, higher=False) is True


@pytest.mark.parametrize("fn", ["memview.py"])
def test_memview_has_no_clock_float_process_network_or_set_order(fn):
    tree = ast.parse(open(os.path.join(ROOT, "verantyx", "loom", fn), encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not ({a.name.split(".")[0] for a in n.names} & {"time", "random", "os", "sys", "subprocess", "socket", "datetime"})
        if isinstance(n, ast.ImportFrom) and n.module:
            assert n.module.split(".")[0] not in ("time", "random", "os", "sys", "subprocess", "socket", "datetime")
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id not in ("float", "set", "frozenset", "eval", "exec", "open", "print")
        assert not isinstance(n, (ast.Div, ast.Set, ast.SetComp))

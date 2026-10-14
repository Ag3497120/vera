"""LOOM-b/c/d acceptance: the worked example of docs/LINE3_LOOM_DESIGN.md 3.5, 「東京は日本の首都です」, reproduced op for op by the scripted weaver
(T-LOOM-13), in both modes.  Three WORD crosses; 首都 at the centre of c2 with 日本 on the の arm, key (2, 2, 2880); です is constructed and
refused in record_only, which emits 「東京は日本の首都」.
"""


import hashlib


import pytest


from verantyx.loom import ledger as lg


from verantyx.loom import read as rd


from verantyx.loom.scripted import ScriptedWeaver, say_only, weave_tokyo


from loom_common import rows, server


def run(tmp_path, task_id, model="claude-haiku-4-5", run_id="w"):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, task_id, model, run_id)
    res = weave_tokyo(w)
    return srv, w, res, tmp_path / "runs" / run_id


def test_constructed_allowed_emits_the_whole_sentence_row_by_row(tmp_path):
    srv, w, res, d = run(tmp_path, "demo/tokyo_ca")
    rs = rows(d)
    assert len(rs) == 17
    table = [(0, "begin"), (1, "add"), (2, "add"), (3, "add"), (4, "add"), (5, "open_cross"), (6, "seat"), (7, "topic"), (8, "open_cross"), (9, "seat"),
             (10, "seat"), (11, "open_cross"), (12, "seat"), (13, "link"), (14, "link"), (15, "link"), (16, "emit")]
    assert [(r["i"], r["op"]) for r in rs] == table
    assert [r["args"] for r in rs[1:5]] == [{"kind": "record", "text": "東京", "tier": "WORD"}, {"kind": "record", "text": "日本", "tier": "WORD"},
                                              {"kind": "record", "text": "首都", "tier": "WORD"}, {"kind": "constructed", "text": "です"}]
    assert [r["result"]["uid"] for r in rs[1:5]] == ["u1", "u2", "u3", "u4"]
    assert [r["result"]["prov"]["n"] for r in rs[1:4]] == [7, 49, 4]
    assert rs[4]["result"]["prov"] == {"by": "claude-haiku-4-5", "at": 4}
    assert [(rs[i]["result"]["cid"], rs[i]["result"]["L"]) for i in (5, 8, 11)] == [("c1", 1), ("c2", 2), ("c3", 1)]
    assert rs[9]["args"] == {"cid": "c2", "seat": "+x:0", "uid": "u2"} and rs[10]["args"] == {"cid": "c2", "seat": "centre", "uid": "u3"}
    assert [rs[i]["args"] for i in (13, 14, 15)] == [{"cid": "c1", "pos": 0}, {"cid": "c2", "pos": 1}, {"cid": "c3", "pos": 2}]
    assert all(r["result"]["ok"] for r in rs)
    assert rs[-1]["result"]["text"] == res["text"] == "東京は日本の首都です"
    assert res["text"].encode("utf-8") == b"\xe6\x9d\xb1\xe4\xba\xac\xe3\x81\xaf\xe6\x97\xa5\xe6\x9c\xac\xe3\x81\xae\xe9\xa6\x96\xe9\x83\xbd\xe3\x81\xa7\xe3\x81\x99"
    assert res["output_sha"] == hashlib.sha256(res["text"].encode("utf-8")).hexdigest()
    assert srv.closed("w") == ["emitted", res["output_sha"]]


def test_the_annotated_output_of_the_worked_example(tmp_path):
    srv, w, res, d = run(tmp_path, "demo/tokyo_ca")
    segs = res["annotated"]
    assert [s["s"] for s in segs] == ["東京", "は", "日本", "の", "首都", "です"]
    assert [s["kind"] for s in segs] == ["record", "foundation", "record", "foundation", "record", "constructed"]
    assert rd.render_display(segs) == "東京[rec WORD n=7] は[fnd 233/377] 日本[rec WORD n=49] の[fnd +x 144/377] 首都[rec WORD n=4] です[con by claude-haiku-4-5 @4]"
    assert rd.render_marked(segs) == "東京は日本の首都【構成:です】"
    assert [s["cid"] for s in segs] == ["c1", "c1", "c2", "c2", "c2", "c3"]
    assert res["shares"] == {"record": 6, "constructed": 2, "foundation": 2, "layout": 0}


def test_c2_is_stable_with_the_key_2_2_2880_and_c1_c3_are_trivially_stable(tmp_path):
    srv, w, res, d = run(tmp_path, "demo/tokyo_ca")
    st = {e["cid"]: e for e in res["stability"]}
    assert st["c2"]["key"] == [2, 2, 2880] and st["c2"]["status"] == "stable" and st["c2"]["improving"] == []
    assert st["c1"]["status"] == "trivially_stable" and st["c3"]["status"] == "trivially_stable"
    assert st["c1"]["key"] == st["c3"]["key"] == [0, 0, 0]


def test_record_only_refuses_the_constructed_unit_and_emits_the_sentence_without_it(tmp_path):
    srv, w, res, d = run(tmp_path, "demo/tokyo_ro")
    rs = rows(d)
    assert rs[4]["op"] == "add" and rs[4]["args"] == {"kind": "constructed", "text": "です"}
    assert rs[4]["result"] == {"ok": False, "refusal": "constructed_forbidden", "detail": {"mode": "record_only"}}
    assert len(rs) == 14 and rs[-1]["op"] == "emit"
    assert [r["op"] for r in rs[5:13]] == ["open_cross", "seat", "topic", "open_cross", "seat", "seat", "link", "link"]
    assert res["text"] == "東京は日本の首都"
    assert res["text"].encode("utf-8") == b"\xe6\x9d\xb1\xe4\xba\xac\xe3\x81\xaf\xe6\x97\xa5\xe6\x9c\xac\xe3\x81\xae\xe9\xa6\x96\xe9\x83\xbd"
    assert [s["kind"] for s in res["annotated"]] == ["record", "foundation", "record", "foundation", "record"]
    assert res["shares"]["constructed"] == 0
    assert srv.runs["w"].run.state.counters["constructed"] == 0


def test_the_same_script_under_the_all_tier_tasks(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "prose/ca", "m", "all")
    # tier WORD is chosen by the script, the other tiers are available but not used
    assert weave_tokyo(w)["text"] == "東京は日本の首都です"
    w2 = ScriptedWeaver(srv, "prose/ro", "m", "all_ro")
    assert weave_tokyo(w2)["text"] == "東京は日本の首都"


def test_the_worked_example_replays_and_verifies_in_both_modes(tmp_path):
    for t in ("demo/tokyo_ca", "demo/tokyo_ro"):
        srv, w, res, d = run(tmp_path / t.split("/")[1], t)
        v = lg.verify(d)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["replay"]["text"] == res["text"]
        assert lg.emitted_output(d) == {"status": "emitted", "text": res["text"], "output_sha": res["output_sha"]}


def test_the_model_cannot_say_nihon_ga_shuto(tmp_path):
    """The rule decides the particle: 日本 next to 首都 can only be on the の arm (の 2880 against が 13)."""
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "ga")
    w.begin()
    u2 = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    u3 = w.call("add", text="首都", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c, seat="-z:0", uid=u2)
    w.call("seat", cid=c, seat="centre", uid=u3)
    w.call("link", cid=c)
    r = w.call("emit")
    assert r["refusal"] == "unstable_cross"
    sa, sb = r["detail"]["refusals"][0]["best_swaps"][0]
    assert {sa, sb} == {"+x:0", "-z:0"}                                           # the move of 日本 to the の arm, a 13 -> 2880
    w.call("swap", cid=c, seat_a=sa, seat_b=sb)
    assert w.call("emit")["text"] == "日本の首都"

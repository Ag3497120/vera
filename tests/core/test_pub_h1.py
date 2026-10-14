"""PUB-H1 tests: the runaway cap (cap.v1) of the two drivers, with the fake client (no network).

Every NEW run gets at most 8 consecutive calls of one tool with the same arguments and at most 20 `status` calls; the call that would exceed a cap does not run and the run ends with the
harness row `abandoned` (reason `cap_repeat` / `cap_status`).  The ledgers stay replayable by the code that has no cap, and `caps=None` is the driver of before."""


import json


import pytest


from verantyx.loom import driver as drv


from verantyx.loom import ledger as lg


from verantyx.loom import memdoor as md


from verantyx.loom import memdriver as mdrv


from verantyx.loom import memory as mem


from loom_common import server, rows


T = lambda name, **a: ("tool", name, a)


LOOM_TOOLS = [{"name": n} for n in ("read_sentence", "status", "emit", "abstain", "lookup")]


STATUS = lambda: T("status")


OK = lambda: T("report", contradictions=[])


class Rec(drv.ReplayClient):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.sent = []

    def _create(self, **kw):
        self.sent.append(json.loads(json.dumps(kw["messages"], default=str)))
        return super()._create(**kw)


def episode(tmp_path, script, **kw):
    tmp_path = tmp_path / ("e%d" % len(list(tmp_path.glob("e*"))))
    tmp_path.mkdir()
    srv = server(tmp_path)
    rid = srv.begin("demo/tokyo_ca", "fake-model", "api1")["run_id"]
    client = drv.ReplayClient(script, allowed_tools={t["name"] for t in LOOM_TOOLS} | {"done"})
    res = drv.run_episode(client, srv, rid, "fake-model", "sys", "go", LOOM_TOOLS, **kw)
    return res, rows(tmp_path / "runs" / rid), srv, rid, client


def test_the_constants():
    assert drv.CAP_VERSION == "cap.v1" and drv.CAP_REPEAT == 8 and drv.CAP_STATUS == 20 and drv.CAP_REASONS == ("cap_repeat", "cap_status")
    assert drv.RUNAWAY_CAPS_V1 == drv.RunawayCaps(8, 20, "cap.v1")


def test_eight_consecutive_identical_calls_run_the_ninth_does_not():
    t = drv.CapTracker(drv.RUNAWAY_CAPS_V1)
    assert [t.admit("lookup", {"q": "a"}) for _ in range(8)] == [None] * 8
    assert t.admit("lookup", {"q": "a"}) == "cap_repeat" and t.hit == {"reason": "cap_repeat", "tool": "lookup", "n": 9}


def test_other_arguments_or_another_tool_break_the_streak_and_run_id_is_not_an_argument():
    t = drv.CapTracker(drv.RUNAWAY_CAPS_V1)
    for k in range(8):
        assert t.admit("lookup", {"q": "a", "run_id": "r%d" % k}) is None          # run_id differs: still the same call
    assert t.admit("lookup", {"q": "b"}) is None                                    # other arguments: streak 1
    for _ in range(7):
        assert t.admit("lookup", {"q": "b"}) is None
    assert t.admit("read_sentence", {"q": "b"}) is None                             # another tool
    assert t.admit("lookup", {"q": "b"}) is None
    assert t.admit("lookup", {"q": "b"}) is None


def test_key_order_of_the_arguments_does_not_matter_and_a_non_dict_input_is_an_empty_call():
    t = drv.CapTracker(drv.RUNAWAY_CAPS_V1)
    for k in range(8):
        assert t.admit("x", {"a": 1, "b": 2} if k % 2 else {"b": 2, "a": 1}) is None
    assert t.admit("x", {"a": 1, "b": 2}) == "cap_repeat"
    t = drv.CapTracker(drv.RUNAWAY_CAPS_V1)
    assert [t.admit("status", None if k % 2 else {}) for k in range(8)] == [None] * 8 and t.admit("status", "junk") == "cap_repeat"


def test_twenty_status_calls_per_run_the_twenty_first_does_not_even_when_interleaved():
    t = drv.CapTracker(drv.RUNAWAY_CAPS_V1)
    for k in range(20):
        assert t.admit("status", {}) is None                                         # the k-th status ...
        assert t.admit("lookup", {"q": str(k)}) is None                              # ... and another call between: never 8 in a row
    assert t.admit("status", {}) == "cap_status" and t.hit == {"reason": "cap_status", "tool": "status", "n": 21}


def test_repeat_is_judged_before_status_and_a_cap_hit_does_not_count():
    t = drv.CapTracker(drv.RUNAWAY_CAPS_V1)
    for _ in range(8):
        t.admit("status", {})
    assert t.admit("status", {}) == "cap_repeat"
    assert t.admit("status", {}) == "cap_repeat"                                     # nothing was counted: the same answer
    assert t.admit("lookup", {}) is None


def test_no_caps_admits_everything_and_custom_caps_are_honoured():
    t = drv.CapTracker(None)
    assert all(t.admit("status", {}) is None for _ in range(500))
    t = drv.CapTracker(drv.RunawayCaps(repeat=2, status=3))
    assert t.admit("status", {}) is None and t.admit("status", {}) is None and t.admit("status", {}) == "cap_repeat"


def test_a_status_runaway_ends_the_run_with_cap_repeat_and_an_explicit_row(tmp_path):
    res, rs, srv, rid, client = episode(tmp_path, [[STATUS()] for _ in range(40)])
    assert res.ended == "cap_repeat" and res.turns == 9 and res.tool_calls == 8 and len(client.calls) == 9
    assert res.cap_hit == {"reason": "cap_repeat", "tool": "status", "n": 9} and res.caps == {"version": "cap.v1", "repeat": 8, "status": 20}
    last = rs[-1]
    assert last["actor"] == "harness" and last["op"] == "abandoned" and last["args"] == {"reason": "cap_repeat", "cap": "cap.v1", "n": 9, "tool": "status"}
    assert sum(1 for r in rs if r["op"] == "status") == 8 and srv.closed(rid) == ["abandoned", "cap_repeat"]
    o = res.to_obj()
    assert o["ended"] == "cap_repeat" and o["caps"]["version"] == "cap.v1" and o["cap_hit"]["n"] == 9 and o["calls_skipped_after_cap"] == 1


def test_interleaved_status_calls_end_the_run_with_cap_status(tmp_path):
    script = []
    for k in range(25):
        script.append([STATUS()])
        script.append([T("lookup", q="w%d" % k)])
    res, rs, srv, rid, _ = episode(tmp_path, script)
    assert res.ended == "cap_status" and sum(1 for r in rs if r["op"] == "status") == 20
    assert rs[-1]["op"] == "abandoned" and rs[-1]["args"] == {"reason": "cap_status", "cap": "cap.v1", "n": 21, "tool": "status"}
    assert srv.closed(rid) == ["abandoned", "cap_status"]


def test_the_rest_of_the_turn_is_not_run_after_a_cap(tmp_path):
    script = [[STATUS()] for _ in range(8)] + [[STATUS(), T("lookup", q="never"), T("lookup", q="never2")]]
    res, rs, _, _, _ = episode(tmp_path, script)
    assert res.ended == "cap_repeat" and res.calls_skipped_after_cap == 3 and not any(r["op"] == "lookup" for r in rs)


def test_a_tool_not_offered_counts_too_and_done_does_not(tmp_path):
    res, rs, _, _, _ = episode(tmp_path, [[T("bogus")] for _ in range(9)])
    assert res.ended == "cap_repeat" and res.cap_hit["tool"] == "bogus" and res.tool_calls == 8
    res, rs, _, _, _ = episode(tmp_path, [[STATUS()] for _ in range(7)] + [[T("done")]])
    assert res.ended == "done" and res.cap_hit is None


def test_eight_in_a_row_are_fine(tmp_path):
    res, rs, _, _, _ = episode(tmp_path, [[STATUS()] for _ in range(8)] + [[T("lookup", q="x")], [T("done")]])
    assert res.ended == "done" and res.cap_hit is None and res.tool_calls == 10


def test_caps_none_is_the_driver_of_before(tmp_path):
    res, rs, _, _, _ = episode(tmp_path, [[STATUS()] for _ in range(30)] + [[T("done")]], caps=None)
    assert res.ended == "done" and res.tool_calls == 31 and res.caps is None
    o = res.to_obj()
    assert "caps" not in o and "cap_hit" not in o and "calls_skipped_after_cap" not in o        # the report of a run before the cap has the keys it had


def test_the_cap_run_replays_and_verifies(tmp_path):
    res, rs, srv, rid, _ = episode(tmp_path, [[STATUS()] for _ in range(20)])
    v = lg.verify(str(tmp_path / "e0" / "runs" / rid))
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"


def test_a_control_run_is_capped_too(tmp_path):
    srv = server(tmp_path)
    rid = srv.begin("demo/tokyo_ca", "fake-model", "api1")["run_id"]
    tools = [{"name": "lookup"}, {"name": "read_sentence"}]
    client = drv.ReplayClient([[T("lookup", q="a")] for _ in range(20)])
    res = drv.run_episode(client, srv, rid, "fake-model", "sys", "go", tools, control=True)
    assert res.ended == "cap_repeat" and res.control_text is None


def door_of(arm, tmp_path, profile=mem.PROFILE_V3):
    if arm in md.STRUCTURE_ARMS:
        return md.StructureDoor(str(tmp_path / arm), arm, "m", profile=profile)
    return md.BaselineDoor(str(tmp_path / arm), arm, "story", "m", version=md.BASELINE_V2 if profile == mem.PROFILE_V3 else md.BASELINE_VERSION)


def story(client, door, msgs, **kw):
    return mdrv.run_story_session(client, door, "fake-model", "SYSTEM", "INTRO", msgs, md.api_tools(door.tool_names), **kw)


def rows_of(door):
    d = door.session.ledger.dir if hasattr(door, "session") else door.ledger.dir
    return [lg._parse_line(ln) for ln in lg.read_raw_lines(d)[0]]


def cap_rows(d):
    return [r for r in rows_of(d) if r["op"] == "cap_turn"]


@pytest.mark.parametrize("arm", md.ARMS)
def test_a_status_runaway_ends_the_turn_not_the_session_in_every_arm(tmp_path, arm):
    d = door_of(arm, tmp_path)
    script = [[STATUS()] for _ in range(9)] + [[T("report", contradictions=[])]]          # message 1: 9 statuses (capped); message 2: a normal report
    c = drv.ReplayClient(script)
    res = story(c, d, [("1-1", "m1"), ("1-2", "m2")])
    assert res.ended == "complete" and res.tool_calls == 9 and len(res.turns) == 2
    assert res.turns[0]["ended"] == "cap_repeat" and res.turns[0]["report"] is None and res.turns[1]["ended"] == "report"
    assert res.cap_hits == [{"turn": "1-1", "reason": "cap_repeat", "tool": "status", "n": 9, "calls": 8}] and res.to_obj()["turns_capped"] == 1 and res.to_obj()["caps"]["version"] == "cap.v1"
    r = cap_rows(d)
    assert len(r) == 1 and r[0]["actor"] == "harness" and r[0]["args"] == {"turn": "1-1", "reason": "cap_repeat", "cap": "cap.v1", "tool": "status", "n": 9, "calls": 8}
    assert d.closed(None) is None
    assert d.commit()["ok"] is True                                                  # the session commits normally


@pytest.mark.parametrize("arm", md.ARMS)
def test_the_calls_after_the_cap_get_a_synthetic_result_and_the_next_message_carries_it(tmp_path, arm):
    d = door_of(arm, tmp_path)
    script = [[STATUS()] for _ in range(8)] + [[STATUS(), T("recall", q="x")], [OK()]]
    c = Rec(script)
    res = story(c, d, [("1-1", "m1"), ("1-2", "m2")])
    assert res.ended == "complete" and res.calls_skipped_after_cap == 2 and res.turns[0]["ended"] == "cap_repeat"
    last = c.sent[-1][-1]["content"]                                                  # message 2 arrives with the owed results of the capped turn
    owed = [b for b in last if isinstance(b, dict) and b.get("type") == "tool_result"]
    assert len(owed) == 2 and all("skipped_after_cap" in b["content"] for b in owed)


def test_cap_status_inside_one_message_ends_that_turn_and_the_session_goes_on(tmp_path):
    d = door_of("blind", tmp_path)
    script = [[STATUS(), T("recall", q="x%d" % k)] for k in range(30)] + [[OK()]]
    res = story(drv.ReplayClient(script), d, [("1-1", "m"), ("1-2", "m")], max_calls=1000)
    assert res.ended == "complete" and res.cap_hits[0]["reason"] == "cap_status" and res.cap_hits[0]["n"] == 21 and res.turns[1]["ended"] == "report"
    assert cap_rows(d)[0]["args"]["reason"] == "cap_status"


@pytest.mark.parametrize("arm", md.ARMS)
def test_status_cap_counts_per_delivered_message(tmp_path, arm):
    """Eleven messages each with 2 status calls (22 in all) do not hit the cap: the counters start again with each message."""
    d = door_of(arm, tmp_path)
    script = [[STATUS(), T("report", contradictions=[])] for _ in range(11)]
    res = story(drv.ReplayClient(script), d, [("1-%d" % (k + 1), "m") for k in range(11)])
    assert res.ended == "complete" and res.cap_hits == []


def test_story_caps_none_is_the_driver_of_before(tmp_path):
    d = door_of("blind", tmp_path)
    script = [[STATUS()] for _ in range(11)] + [[T("report", contradictions=[])]]
    res = story(drv.ReplayClient(script), d, [("1-1", "m")], caps=None, max_calls=100)
    assert res.ended == "complete" and res.caps is None and "caps" not in res.to_obj() and cap_rows(d) == []


@pytest.mark.parametrize("arm", md.ARMS)
def test_a_capped_turn_gets_the_forced_final_report_like_any_turn(tmp_path, arm):
    d = door_of(arm, tmp_path)
    script = [[STATUS()] for _ in range(9)] + [[OK()], [OK()]]       # the 9th status is capped; the forced request is answered; message 2 reports normally
    c = Rec(script)
    res = story(c, d, [("1-1", "m1"), ("1-2", "m2")], force_report=True)
    assert res.ended == "complete" and res.turns[0]["forced"] == "cap_turn" and res.turns[0]["ended"] in ("report_forced", "report_missing")
    assert res.cap_hits[0]["turn"] == "1-1" and res.to_obj()["turns_capped"] == 1
    rs = rows_of(d)
    forced = [r for r in rs if r["op"] == "report_forced"]
    assert len(forced) == 1 and forced[0]["args"]["reason"] == "cap_turn" and forced[0]["args"]["turn"] == "1-1" and len(cap_rows(d)) == 1
    assert [r["op"] for r in rs].index("cap_turn") < [r["op"] for r in rs].index("report_forced")
    forced_request = c.calls[9]                                                     # the request after the cap offers only `report`
    assert [t["name"] for t in forced_request["tools"]] == ["report"]
    owed = [b for b in c.sent[9][-1]["content"] if isinstance(b, dict) and b.get("type") == "tool_result"]
    assert len(owed) == 1 and "skipped_after_cap" in owed[0]["content"]                         # the capped call's synthetic result travels with the forced request


@pytest.mark.parametrize("arm", md.ARMS)
def test_without_force_report_a_capped_turn_just_ends(tmp_path, arm):
    d = door_of(arm, tmp_path)
    script = [[STATUS()] for _ in range(9)] + [[OK()]]
    res = story(drv.ReplayClient(script), d, [("1-1", "m1"), ("1-2", "m2")])
    assert res.turns[0]["ended"] == "cap_repeat" and not any(r["op"].startswith("report_") for r in rows_of(d))


def test_a_capped_turn_whose_forced_request_fails_is_report_missing(tmp_path):
    d = door_of("blind", tmp_path)
    script = [[STATUS()] for _ in range(9)] + [[T("report", contradictions=[["9-9", "9-9"]])], [T("report", contradictions=[["9-9", "9-9"]])], [OK()]]
    res = story(drv.ReplayClient(script), d, [("1-1", "m1"), ("1-2", "m2")], force_report=True)
    assert res.turns[0]["ended"] == "report_missing" and res.ended == "complete"
    assert [r["args"]["reason"] for r in rows_of(d) if r["op"] in ("report_forced", "report_missing")] == ["cap_turn", "cap_turn"]
    d.commit()
    d.close()
    assert mem.verify_store(str(tmp_path / "blind"), mem.FROM_HEADER)["status"] == "OK"


def test_a_ledger_with_cap_turn_and_report_forced_verifies_and_replays(tmp_path):
    d = door_of("blind", tmp_path)
    script = [[STATUS()] for _ in range(9)] + [[OK()], [OK()]]
    res = story(drv.ReplayClient(script), d, [("1-1", "m1"), ("1-2", "m2")], force_report=True)
    assert res.ended == "complete" and res.turns[0]["ended"] == "report_forced"
    d.commit()
    d.close()
    v = mem.verify_store(str(tmp_path / "blind"), mem.FROM_HEADER)
    assert v["status"] == "OK", v


def test_baseline_ledgers_with_cap_turn_verify(tmp_path):
    for arm in ("log", "plain", "context"):
        if arm not in md.ARMS:
            continue
        d = door_of(arm, tmp_path)
        script = [[STATUS()] for _ in range(9)] + [[OK()]]
        res = story(drv.ReplayClient(script), d, [("1-1", "m1"), ("1-2", "m2")])
        assert res.ended == "complete" and len(cap_rows(d)) == 1
        d.commit()
        d.close()


def test_the_cap_turn_row_is_new_only_older_profiles_refuse_it_and_malformed_ones_too(tmp_path):
    ok = {"turn": "1-1", "reason": "cap_repeat", "cap": "cap.v1", "tool": "status", "n": 9, "calls": 8}
    assert mem.cap_args(ok) == ok
    for bad in (dict(ok, reason="turn_limit"), dict(ok, turn="x"), dict(ok, n=-1), dict(ok, cap="v1"), {k: v for k, v in ok.items() if k != "tool"}, dict(ok, extra=1), "junk"):
        with pytest.raises(ValueError):
            mem.cap_args(bad)
    d2 = md.StructureDoor(str(tmp_path / "v2"), "blind", "m", profile=mem.PROFILE_V2)
    with pytest.raises(ValueError):
        d2.harness(None, "cap_turn", ok)
    b1 = md.BaselineDoor(str(tmp_path / "b1"), "log", "story", "m", version=md.BASELINE_VERSION)
    with pytest.raises(ValueError):
        b1.harness(None, "cap_turn", ok)

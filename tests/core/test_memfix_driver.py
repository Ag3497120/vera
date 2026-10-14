"""MEM-fix tests: the story driver's turn limit and the forced final `report` (L-MEM-62 / 63), the long-story caps, and `mem_run --profile mem.v3` end to end.

The meter v1 gave a turn 12 tool calls and ended it with NO report after that (23 turns of A2b, 14 of A2, none of A0 / A1): the arms stopped being comparable.  A mem.v3 meter gives every arm
24 calls and, when a turn still ends without a report of its own (`turn_limit`, or 3 tool-less turns), asks ONCE MORE with only the `report` tool on offer (forced where the model accepts
it), up to 2 times; if no report comes the ledger says so itself: a `report_missing` row.  The rule is the driver's, identical for the four arms.  No network: `driver.ReplayClient`."""


import json


import os


import pytest


from verantyx.loom import driver as drv


from verantyx.loom import ledger as lg


from verantyx.loom import memdoor as md


from verantyx.loom import memdriver as mdrv


from verantyx.loom import memory as mem


from mem_common import ledger_rows


T = lambda name, **a: ("tool", name, a)


BAD = lambda: T("report", contradictions=[["1-1", "9-9"]])               # a report the door refuses (a turn that has not been delivered)


OK = lambda p=(): T("report", contradictions=[list(x) for x in p])


class Rec(drv.ReplayClient):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.sent = []

    def _create(self, **kw):
        self.sent.append(json.loads(json.dumps(kw["messages"], default=str)))
        return super()._create(**kw)


def door_of(arm, tmp_path, profile=mem.PROFILE_V3):
    if arm in md.STRUCTURE_ARMS:
        return md.StructureDoor(str(tmp_path / arm), arm, "m", profile=profile)
    return md.BaselineDoor(str(tmp_path / arm), arm, "story", "m", version=md.BASELINE_V2 if profile == mem.PROFILE_V3 else md.BASELINE_VERSION)


def story(client, door, msgs, **kw):
    return mdrv.run_story_session(client, door, "fake-model", "SYSTEM", "INTRO", msgs, md.api_tools(door.tool_names), **kw)


def rows_of(door):
    d = door.session.ledger.dir if hasattr(door, "session") else door.ledger.dir
    return [lg._parse_line(ln) for ln in lg.read_raw_lines(d)[0]]


@pytest.mark.parametrize("arm", md.ARMS)
def test_a_turn_that_hits_the_limit_is_asked_for_its_report_once_more(tmp_path, arm):
    d = door_of(arm, tmp_path)
    c = Rec([[BAD()], [BAD()], [BAD()], [OK()], [OK()]])
    r = story(c, d, [("1-1", "a"), ("1-2", "b")], max_calls=3, force_report=True)
    t = r.turns[0]
    assert (t["ended"], t["forced"], t["calls"]) == ("report_forced", "turn_limit", 4) and t["report"] == {"contradictions": [], "bugs": []}
    assert r.turns[1]["ended"] == "report" and "forced" not in r.turns[1] and r.ended == "complete"
    rows = rows_of(d)
    assert [x["op"] for x in rows if x["actor"] == "harness"] == ["report_forced"]
    k = [x["op"] for x in rows].index("report_forced")
    assert rows[k]["args"] == {"turn": "1-1", "reason": "turn_limit", "calls": 3} and rows[k + 1]["op"] == "report" and rows[k + 1]["result"]["ok"] is True
    # the forced request offers ONLY report, forced; the next message arrives after its tool result
    assert [t_["name"] for t_ in c.calls[3]["tools"]] == ["report"] and c.calls[3]["tool_choice"] == {"type": "tool", "name": "report"}
    last_user = c.sent[3][-1]["content"]
    assert [b["type"] for b in last_user] == ["tool_result", "text"] and "report" in last_user[1]["text"]            # the result of the 3rd call is still owed, then the instruction
    nxt = c.sent[4][-1]["content"]
    assert nxt[0]["type"] == "tool_result" and nxt[-1] == {"type": "text", "text": "b"}


@pytest.mark.parametrize("arm", md.ARMS)
def test_without_a_report_the_ledger_says_report_missing(tmp_path, arm):
    d = door_of(arm, tmp_path)
    c = Rec([[BAD()], [BAD()], [BAD()], [("text", "I will not report")], [BAD()], [OK()]])
    r = story(c, d, [("1-1", "a"), ("1-2", "b")], max_calls=3, force_report=True)
    t = r.turns[0]
    assert (t["ended"], t["forced"], t["report"]) == ("report_missing", "turn_limit", None) and r.turns[1]["ended"] == "report" and r.ended == "complete"
    ops = [x["op"] for x in rows_of(d) if x["actor"] == "harness"]
    assert [o for o in ops if o in ("report_forced", "report_missing")] == ["report_forced", "report_missing"] and ops.count("free_text_dropped") == 1
    miss = [x for x in rows_of(d) if x["op"] == "report_missing"][0]
    assert miss["args"] == {"turn": "1-1", "reason": "turn_limit", "calls": 3 + 1}
    assert [t_["name"] for t_ in c.calls[3]["tools"]] == ["report"] and len(c.calls) == 6                 # exactly FORCE_ATTEMPTS forced requests (the second after a text-only answer)


@pytest.mark.parametrize("arm", md.ARMS)
def test_three_tool_less_turns_get_the_same_treatment(tmp_path, arm):
    d = door_of(arm, tmp_path)
    c = Rec([[("text", "a")], [("text", "b")], [("text", "c")], [OK()], [OK()]])
    r = story(c, d, [("1-1", "a"), ("1-2", "b")], force_report=True)
    assert (r.turns[0]["ended"], r.turns[0]["forced"]) == ("report_forced", "no_tool_call") and r.turns[1]["ended"] == "report"
    row = [x for x in rows_of(d) if x["op"] == "report_forced"][0]
    assert row["args"] == {"turn": "1-1", "reason": "no_tool_call", "calls": 0}
    last = c.sent[3][-1]
    assert last["role"] == "user" and isinstance(last["content"], str) and "report" in last["content"]             # no tool result is owed after a text-only turn


def test_the_same_rule_gives_the_same_turns_in_every_arm(tmp_path):
    outcomes = {}
    for arm in md.ARMS:
        d = door_of(arm, tmp_path)
        c = Rec([[BAD()], [BAD()], [OK()], [("text", "x")], [("text", "y")], [("text", "z")], [OK()], [BAD()], [BAD()], [BAD()], [BAD()]])
        r = story(c, d, [("1-1", "a"), ("1-2", "b"), ("1-3", "c")], max_calls=2, force_report=True)
        outcomes[arm] = [(t["turn"], t["ended"], t.get("forced")) for t in r.turns]
    assert len({json.dumps(v) for v in outcomes.values()}) == 1
    assert outcomes["notes"] == [("1-1", "report_forced", "turn_limit"), ("1-2", "report_forced", "no_tool_call"), ("1-3", "report_missing", "turn_limit")]


def test_a_model_that_cannot_be_forced_is_asked_with_auto_and_strict_tools(tmp_path):
    d = door_of("context", tmp_path)
    c = Rec([[BAD()], [BAD()], [OK()]])
    tools = md.api_tools(d.tool_names, strict=True)
    mdrv.run_story_session(c, d, "claude-sonnet-5-5", "S", "I", [("1-1", "a")], tools, tool_choice={"type": "auto"}, max_calls=2, force_report=True)
    assert c.calls[2]["tool_choice"] == {"type": "auto"} and [t["name"] for t in c.calls[2]["tools"]] == ["report"] and c.calls[2]["tools"][0]["strict"] is True


def test_an_older_door_has_no_such_rows(tmp_path):
    for door in (door_of("context", tmp_path, mem.PROFILE_V2), door_of("notes", tmp_path, mem.PROFILE_V2)):
        with pytest.raises(ValueError):
            door.harness(None, "report_forced", {"turn": "1-1", "reason": "turn_limit", "calls": 1})
    ok = door_of("log", tmp_path)
    ok.harness(None, "report_missing", {"turn": "1-1", "reason": "no_tool_call", "calls": 0})
    assert md.verify_baseline(ok.ledger.dir)["status"] == "OK"


def test_an_api_error_in_the_forced_request_ends_the_session(tmp_path):
    class Boom(Rec):
        def _create(self, **kw):
            if len(self.calls) >= 2:
                raise RuntimeError("secret detail")
            return super()._create(**kw)
    d = door_of("notes", tmp_path)
    r = story(Boom([[BAD()], [BAD()]]), d, [("1-1", "a")], max_calls=2, force_report=True)
    assert r.ended == "api_error" and d.session.run.state.closed == ["abandoned", "api_error"] and "secret detail" not in json.dumps(rows_of(d))


def test_membase_v2_has_the_long_story_caps_and_v1_replays(tmp_path):
    old = md.BaselineDoor(str(tmp_path / "o"), "log", "story", "m")
    new = md.BaselineDoor(str(tmp_path / "n"), "log", "story", "m", version=md.BASELINE_V2)
    assert old.begin_result["caps"] == md.LOG_CAPS and new.begin_result["caps"] == md.LOG_CAPS_V2 and new.begin_result["header"]["baseline_version"] == "membase.v2"
    for _ in range(61):
        old.call("log_append", {"text": "x"})
        new.call("log_append", {"text": "x"})
    assert old.call("log_append", {"text": "x"})["refusal"] == "append_cap" and new.call("log_append", {"text": "x"})["ok"] is True
    old.commit()
    new.commit()
    assert md.verify_baseline(old.ledger.dir)["status"] == "OK" and md.verify_baseline(new.ledger.dir)["status"] == "OK"
    with pytest.raises(ValueError):
        md.BaselineRun("log", "story", "l0001", "m", 1, version="membase.v9")


def test_a_long_story_session_stays_inside_the_v3_caps(tmp_path):
    s = new_session(tmp_path)
    for k in range(70):                                              # past the v2 cap of 60 writes
        w = s.call("write", {"text": "部署%dの人数は%d" % (k, k)})
        assert w["ok"] is True, (k, w)
    assert s.status()["writes"] == 70


def new_session(tmp_path):
    from mem_common import new_store
    return new_store(tmp_path, "long").begin("m", profile=mem.PROFILE_V3)


def ledger_rows_of_session(out, arm):
    p = os.path.join(out, "MEM-TOY1", arm, "r01", "store", "sessions", "s0001", "ops.jsonl")
    return [json.loads(ln) for ln in open(p, encoding="utf-8")]

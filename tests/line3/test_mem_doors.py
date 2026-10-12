"""MEM-d tests: the DOORS of the meter -- the `report` tool, the tool list of every arm and phase, the agent files, the tool schemas / the MCP server, the baseline arms, and the
multi-session driver (docs/LINE3_LOCAL_DECISIONS.md MEM-d).  No network: the client is `driver.ReplayClient`."""
import asyncio
import json
import os

import pytest

from verantyx.loom import driver as drv
from verantyx.loom import ledger as lg
from verantyx.loom import memdoor as md
from verantyx.loom import memdriver as mdrv
from verantyx.loom import memmcp
from verantyx.loom import memory as mem
from verantyx.loom.state import Refuse
from mem_common import ROOT, ledger_rows, refusal_of, session_v2

AGENTS = os.path.join(ROOT, ".claude", "agents")
P = "mcp__vera-mem__"


def agent_tools(name):
    text = open(os.path.join(AGENTS, name + ".md"), encoding="utf-8").read()
    head = text[4:text.index("\n---\n", 4)]
    return [t.strip() for t in [ln for ln in head.splitlines() if ln.startswith("tools:")][0][len("tools:"):].split(",")]


class Rec(drv.ReplayClient):
    """A ReplayClient that also keeps the messages it was sent."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.sent = []

    def _create(self, **kw):
        self.sent.append(json.loads(json.dumps(kw["messages"], default=str)))
        return super()._create(**kw)


T = lambda name, **a: ("tool", name, a)


# -- the tool lists ----------------------------------------------------------------------------------------------------------------------
def test_the_tool_list_of_every_arm_and_phase_is_pinned():
    assert md.ARMS == ("context", "log", "blind", "notes") and md.ARM_LABEL == {"context": "A0", "log": "A1", "blind": "A2b", "notes": "A2"}
    assert md.STORY_TOOLS == {"context": ("report",), "log": ("log_append", "log_read", "report"),
                              "blind": ("write", "declare_topic", "supersede", "recall", "read_sentence", "report", "status"),
                              "notes": ("write", "declare_topic", "supersede", "recall", "read_sentence", "report", "status")}
    assert md.QUESTION_TOOLS == {"context": ("answer",), "log": ("log_read", "answer"),
                                 "blind": ("recall", "lookup", "read_sentence", "weave_span", "drop", "read", "emit", "abstain", "status"),
                                 "notes": ("recall", "lookup", "read_sentence", "weave_span", "drop", "read", "emit", "abstain", "status")}
    for arm in md.ARMS:                                                   # every arm ends every turn with the SAME report tool
        assert "report" in md.STORY_TOOLS[arm]
    for names in list(md.STORY_TOOLS.values()) + list(md.QUESTION_TOOLS.values()):
        assert set(names) <= set(md.TOOL_SPECS)                           # no tool without a schema; no free-text tool anywhere
        assert not set(names) & {"add", "open_cross", "seat", "seat_run", "unseat", "swap", "extend", "topic", "set_depth", "link", "unlink", "commit", "begin"}


def test_agent_files_carry_exactly_the_loom_only_tool_lists():
    import mem_run_loader as mrl
    mr = mrl.load()
    for arm in md.ARMS:
        for phase in ("story", "question"):
            name = (mr.STORY_AGENT if phase == "story" else mr.QUESTION_AGENT)[arm]
            tools = agent_tools(name)
            assert tools == mr.expected_agent_tools(arm, phase), (arm, phase, tools)
            assert all(t.startswith(P) for t in tools) and not any(t.split("__")[-1] in ("Bash", "Read", "Write") for t in tools)
    assert agent_tools("mem-writer") == [P + n for n in md.STORY_TOOLS["notes"]] and agent_tools("mem-blind") == agent_tools("mem-writer")
    assert agent_tools("mem-answer") == [P + n for n in md.QUESTION_TOOLS["notes"]]
    assert agent_tools("mem-plain") == [P + "report", P + "answer"] and agent_tools("mem-log") == [P + n for n in ("log_append", "log_read", "report", "answer")]
    for name in ("mem-writer", "mem-blind", "mem-plain", "mem-log", "mem-answer"):
        text = open(os.path.join(AGENTS, name + ".md"), encoding="utf-8").read()
        assert "model: haiku" in text and "plain text" in " ".join(text.lower().split())


def test_blind_and_notes_agents_differ_exactly_in_what_they_are_shown():
    w = open(os.path.join(AGENTS, "mem-writer.md"), encoding="utf-8").read()
    b = open(os.path.join(AGENTS, "mem-blind.md"), encoding="utf-8").read()
    assert "SAME_QUESTION" in w and "Notes (this arm shows them)" in w
    assert "SAME_QUESTION" not in b.split("## What you are shown")[0] and "REVERSAL" not in b and "shows no judgement" in b


def test_api_tools_are_the_spec_table_exactly():
    for arm in md.ARMS:
        for names in (md.STORY_TOOLS[arm], md.QUESTION_TOOLS[arm]):
            tools = md.api_tools(names)
            assert [t["name"] for t in tools] == list(names)
            for t in tools:
                sc = t["input_schema"]
                assert sc["type"] == "object" and sc["additionalProperties"] is False and "run_id" not in sc["properties"] and "turn" not in sc["properties"]
                assert set(sc.get("required", [])) <= set(sc["properties"])
    assert [t["name"] for t in md.api_tools(("report",), done=True)] == ["report", "done"]
    assert all(t["strict"] is True for t in md.api_tools(("report",), strict=True, done=True))
    rep = md.api_tools(("report",))[0]["input_schema"]
    assert rep["required"] == ["contradictions"] and rep["properties"]["contradictions"]["items"]["items"] == {"type": "string"}


def test_the_mcp_server_offers_the_same_tools_with_the_same_schemas(tmp_path):
    pytest.importorskip("mcp")
    for arm, phase in (("notes", "story"), ("blind", "story"), ("log", "story"), ("context", "story"), ("log", "question"), ("context", "question")):
        door = memmcp.open_door(str(tmp_path / ("s_%s_%s" % (arm, phase))), arm, phase, "m", question="Q" if phase == "question" else None)
        server = memmcp.build(door)
        listed = asyncio.run(server.list_tools())
        assert [t.name for t in listed] == list(memmcp.tool_names(arm, phase))
        for t in listed:
            spec = md.TOOL_SPECS[t.name]
            props = t.inputSchema.get("properties", {})
            assert set(spec["properties"]) <= set(props) and set(props) - set(spec["properties"]) <= {"turn"}, t.name
            assert sorted(t.inputSchema.get("required", [])) == sorted(spec["required"]), t.name
            for k, v in spec["properties"].items():
                assert props[k]["type"] == v["type"], (t.name, k)
        door.close()


def test_the_mcp_server_for_a_structure_arm_runs_a_session_and_commits_on_shutdown(tmp_path):
    pytest.importorskip("mcp")
    store = str(tmp_path / "s")
    door = memmcp.open_door(store, "notes", "story", "m")
    server = memmcp.build(door)
    names = [t.name for t in asyncio.run(server.list_tools())]
    assert names == list(md.STORY_TOOLS["notes"]) and "commit" not in names and "emit" not in names
    out = asyncio.run(server.call_tool("write", {"text": "広報の期限は水曜"}))
    assert json.loads(out[0][0].text if isinstance(out, tuple) else out[0].text)["ok"] is True
    asyncio.run(server.call_tool("report", {"contradictions": [], "turn": "1-1"}))
    assert door.session.run.counts2["reports"] == 1
    door.commit()
    assert mem.verify_store(store, mem.FROM_HEADER)["status"] == "OK"


# -- the report tool -----------------------------------------------------------------------------------------------------------------------
def rep(s, turn, pairs, bugs=None):
    a = {"turn": turn, "contradictions": pairs}
    if bugs is not None:
        a["bugs"] = bugs
    return s.call("report", a)


def test_report_is_a_closed_format(tmp_path):
    s = session_v2(tmp_path)
    r = rep(s, "2-3", [["2-1", "1-4"], ["1-4", "2-1"], ["1-1", "2-3"]], ["x"])
    assert r == {"ok": True, "turn": "2-3", "contradictions": [["1-1", "2-3"], ["1-4", "2-1"]], "bugs": ["x"]}      # sorted pairs, no duplicate, ids normalised
    assert rep(s, "1-1", [])["contradictions"] == []
    for turn, pairs, want in [("x", [], "bad_turn"), ("1-0", [], "bad_turn"), ("1-1", [["1-1", "1-1"]], "bad_report"), ("1-1", [["1-1"]], "bad_report"),
                              ("1-1", [["1-1", "foo"]], "bad_report"), ("1-1", [["1-1", "1-2"]], "future_turn"), ("1-1", [["1-1", "2-1"]], "future_turn"),
                              ("3-3", [["1-1", "2-1"]] * 1 + [["1-%d" % k, "2-1"] for k in range(2, 12)], "bad_report")]:
        r = rep(s, turn, pairs)
        assert r["ok"] is False and r["refusal"] == want, (turn, pairs, r)
    assert refusal_of(rep(s, "1-1", [], ["a"] * 6)) == "bad_report"
    assert refusal_of(rep(s, "1-1", [], ["a" * 65])) == "args_too_large"
    assert refusal_of(s.call("report", {"contradictions": []})) == "bad_args"                  # `turn` is required at the run (the door supplies it)
    assert refusal_of(s.call("report", {"turn": "1-1", "contradictions": [], "free_text": "hi"})) == "bad_args"
    ev = s.events()["reports"]
    assert ev["ok"] == 2 and ev["refused"] == 12


def test_report_is_the_same_function_in_every_arm(tmp_path):
    args = {"contradictions": [["1-1", "1-2"]], "bugs": []}
    outs = []
    for arm in ("context", "log"):
        d = md.BaselineDoor(str(tmp_path / arm), arm, "story", "m")
        d.set_turn("1-3")
        outs.append(d.call("report", dict(args)))
    s = md.StructureDoor(str(tmp_path / "st"), "notes", "m")
    s.set_turn("1-3")
    outs.append(s.call("report", dict(args)))
    assert outs[0] == outs[1] == outs[2] == {"ok": True, "turn": "1-3", "contradictions": [["1-1", "1-2"]], "bugs": []}
    assert md.noticed_pairs([lg._parse_line(ln) for ln in lg.read_raw_lines(s.session.ledger.dir)[0]]) == [["1-1", "1-2"]]


def test_the_door_supplies_the_turn_and_the_model_cannot_type_one(tmp_path):
    d = md.StructureDoor(str(tmp_path / "st"), "notes", "m")
    assert refusal_of(d.call("report", {"contradictions": []})) == "no_turn"
    d.set_turn("1-2")
    r = d.call("write", {"text": "広報の期限は水曜", "turn": "9-9", "run_id": "other"})           # a forged turn and run id are dropped
    assert r["ok"] and r["turn"] == "1-2" and d.session.run.rows[0]["turn"] == "1-2"
    assert d.call("report", {"contradictions": [], "turn": "9-9"})["turn"] == "1-2"


# -- the doors: tools outside the arm's list do not exist; the blind arm sees no notes ----------------------------------------------------
def test_a_tool_outside_the_arm_is_refused_with_no_row(tmp_path):
    d = md.StructureDoor(str(tmp_path / "st"), "notes", "m")
    n = len(ledger_rows(d.session))
    for tool in ("emit", "commit", "add", "lookup", "begin", "weave_span", "log_append", None, 5):
        r = d.call(tool, {})
        assert r["ok"] is False and r["refusal"] == "unknown_tool"
    assert len(ledger_rows(d.session)) == n
    a = md.BaselineDoor(str(tmp_path / "ctx"), "context", "story", "m")
    n2 = len(lg.read_raw_lines(a.ledger.dir)[0])
    for tool in ("write", "log_append", "log_read", "answer", "recall"):
        assert refusal_of(a.call(tool, {"text": "x"})) == "unknown_tool"
    assert len(lg.read_raw_lines(a.ledger.dir)[0]) == n2


def test_blind_logs_the_notes_but_does_not_return_them(tmp_path):
    outs = {}
    for arm in ("blind", "notes"):
        d = md.StructureDoor(str(tmp_path / arm / "st"), arm, "m")
        d.set_turn("1-1")
        d.call("write", {"text": "田中の担当は認証"})
        outs[arm] = d.call("write", {"text": "田中の担当は決済"})
        rows = ledger_rows(d.session)
        note_rows = [r for r in rows if r["op"] == "loom_note"]
        assert len(note_rows) == 1 and note_rows[0]["args"]["notes"][0]["type"] == "SAME_QUESTION"           # logged in both
        d.commit()
    assert "notes" not in outs["blind"] and "keys" not in outs["blind"] and outs["notes"]["notes"][0]["type"] == "SAME_QUESTION" and "keys" in outs["notes"]
    assert {k: v for k, v in outs["notes"].items() if k not in ("notes", "keys")} == outs["blind"]
    # the stored ledgers of the two arms are the same bytes (the arm is only a view)
    a = open(tmp_path / "blind" / "st" / "sessions" / "s0001" / "ops.jsonl", "rb").read()
    b = open(tmp_path / "notes" / "st" / "sessions" / "s0001" / "ops.jsonl", "rb").read()
    assert a == b


# -- the baselines -------------------------------------------------------------------------------------------------------------------------
def test_the_plain_log_is_all_a_second_session_has(tmp_path):
    store = str(tmp_path / "log")
    d1 = md.BaselineDoor(store, "log", "story", "m")
    assert d1.intro()["log_lines"] == 0
    d1.set_turn("1-1")
    assert d1.call("log_append", {"text": "1-1 広報の期限は水曜"})["line"] == 0
    assert d1.call("log_append", {"text": "1-2 経理の期限は月曜"})["lines"] == 2
    r = d1.call("log_read", {"grep": "広報"})
    assert r["matched"] == 1 and r["entries"] == [{"n": 0, "session": 1, "text": "1-1 広報の期限は水曜"}]
    d1.commit()
    assert open(os.path.join(store, "log.txt"), encoding="utf-8").read() == "S1 1-1 広報の期限は水曜\nS1 1-2 経理の期限は月曜\n"
    d2 = md.BaselineDoor(store, "log", "story", "m")
    assert d2.intro()["log_lines"] == 2 and d2.intro()["session"] == 2
    assert d2.call("log_read", {})["lines"] == 2
    d2.call("log_append", {"text": "2-1 広報の期限は金曜"})
    d2.commit()
    q = md.BaselineDoor(store, "log", "question", "m", question="広報の期限は何ですか")
    assert q.begin_result["question"] == "広報の期限は何ですか" and len(q.call("log_read", {"grep": "広報"})["entries"]) == 2
    assert refusal_of(q.call("answer", {"kind": "value", "values": []})) == "bad_answer" and q.closed() is None
    assert q.call("answer", {"kind": "value", "values": ["金曜"]})["status"] == "answered" and q.closed() == ["answered", "value"]
    assert q.output() == {"kind": "value", "values": ["金曜"]} and refusal_of(q.call("log_read", {})) == "run_closed"
    for rd in (d1.ledger.dir, d2.ledger.dir, q.ledger.dir):
        assert md.verify_baseline(rd)["status"] == "OK", rd


def test_the_context_only_arm_carries_nothing_across_sessions(tmp_path):
    store = str(tmp_path / "ctx")
    d1 = md.BaselineDoor(store, "context", "story", "m")
    d1.set_turn("1-1")
    d1.call("report", {"contradictions": []})
    d1.commit()
    d2 = md.BaselineDoor(store, "context", "story", "m")
    assert d2.intro() == {"session": 2, "log_lines": 0, "tools": ["report"], "caps": md.LOG_CAPS}
    assert not os.path.exists(os.path.join(store, "log.txt"))
    q = md.BaselineDoor(store, "context", "question", "m", question="Q")
    assert q.call("answer", {"kind": "none", "values": []})["ok"] and q.output() == {"kind": "none", "values": []}


def test_baseline_arguments_and_caps_and_secrets(tmp_path):
    d = md.BaselineDoor(str(tmp_path / "log"), "log", "story", "m")
    assert refusal_of(d.call("log_append", {"text": "x" * 65})) == "args_too_large"            # the loom's own argument rule (64 characters a string)
    assert refusal_of(d.call("log_append", {"text": "a\nb"})) == "bad_entry"
    assert refusal_of(d.call("log_append", {"text": "key sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAA"})) in ("secret_shaped_entry", "args_too_large")
    assert refusal_of(d.call("log_append", {})) == "bad_args"
    assert refusal_of(d.call("log_read", {"grep": "g" * 33})) in ("bad_grep", "args_too_large")
    assert md.verify_baseline(d.ledger.dir)["status"] == "OK"
    d.run.counts["appends"] = md.LOG_CAPS["appends"]                                              # (set by hand: the ledger no longer replays from here)
    assert refusal_of(d.call("log_append", {"text": "x"})) == "append_cap"


def test_a_tampered_baseline_ledger_is_caught(tmp_path):
    d = md.BaselineDoor(str(tmp_path / "log"), "log", "story", "m")
    d.call("log_append", {"text": "a"})
    d.commit()
    p = d.ledger.dir / "ops.jsonl"
    p.write_bytes(p.read_bytes().replace(b'"line":0', b'"line":5'))
    assert md.verify_baseline(d.ledger.dir)["status"] == "TAMPERED"
    rows = [json.loads(ln) for ln in open(p, encoding="utf-8")]
    rows[1]["result"]["lines"] = 9
    prev = rows[0]["sha"]
    out = [lg.line_of(rows[0])]
    for r in rows[1:]:
        r["prev"] = prev
        r["sha"] = lg.row_sha(r)
        prev = r["sha"]
        out.append(lg.line_of(r))
    p.write_bytes(b"".join(out))
    (d.ledger.dir / "HEAD").write_text(prev + "\n")
    v = md.verify_baseline(d.ledger.dir)
    assert v["status"] == "REPLAY_DIFFERS" and v["first_diff"]["i"] == 1


# -- the multi-session driver --------------------------------------------------------------------------------------------------------------
def story(client, door, msgs, tools=None, **kw):
    tools = tools or md.api_tools(door.tool_names)
    return mdrv.run_story_session(client, door, "fake-model", "SYSTEM", "INTRO", msgs, tools, **kw)


def test_a_turn_ends_at_the_first_ok_report_and_the_rest_of_that_turn_is_skipped(tmp_path):
    d = md.StructureDoor(str(tmp_path / "st"), "notes", "m")
    c = Rec([[("text", "thinking aloud"), T("write", text="広報の期限は水曜"), T("report", contradictions=[]), T("write", text="経理の期限は月曜")],
             [T("report", contradictions=[["1-1", "1-2"]])]])
    r = story(c, d, [("1-1", "[1-1] 佐藤: 広報の期限は水曜です"), ("1-2", "[1-2] 鈴木: 経理の期限は月曜です")])
    assert r.ended == "complete" and r.calls_skipped_after_report == 1 and r.tool_calls == 3 and r.text_blocks_dropped == 1
    assert [(t["turn"], t["ended"], t["calls"]) for t in r.turns] == [("1-1", "report", 2), ("1-2", "report", 1)]
    assert len(d.session.run.rows) == 1                                                     # the skipped write ran nowhere
    rows = ledger_rows(d.session)
    assert [x["op"] for x in rows if x["actor"] == "harness"] == ["free_text_dropped"] and "thinking aloud" not in json.dumps(rows, ensure_ascii=False)
    # the API sees: user(intro + first message), assistant, user(tool results + second message as a text block)
    assert c.sent[0] == [{"role": "user", "content": "INTRO\n\n[1-1] 佐藤: 広報の期限は水曜です"}]
    second = c.sent[1][-1]
    assert second["role"] == "user" and [b["type"] for b in second["content"]] == ["tool_result", "tool_result", "tool_result", "text"]
    assert json.loads(second["content"][2]["content"])["refusal"] == "skipped_after_report" and second["content"][3]["text"].startswith("[1-2]")
    assert c.calls[0]["tool_choice"] == {"type": "any"} and {t["name"] for t in c.calls[0]["tools"]} == set(md.STORY_TOOLS["notes"])
    assert "done" not in {t["name"] for t in c.calls[0]["tools"]}


def test_a_session_is_a_new_conversation_and_sends_nothing_of_the_old_one(tmp_path):
    store = str(tmp_path / "st")
    sent = []
    for s, text in enumerate(["一回目の秘密の文字列", "二回目"]):
        d = md.StructureDoor(store, "notes", "m")
        c = Rec([[T("write", text="広報の期限は水曜"), T("report", contradictions=[])]])
        story(c, d, [("%d-1" % (s + 1), text)])
        d.commit()
        sent.append(json.dumps(c.sent, ensure_ascii=False))
    assert "一回目の秘密の文字列" not in sent[1] and "広報の期限は水曜" not in sent[1]            # only the structure carries anything: the new conversation starts blank
    d3 = md.StructureDoor(store, "notes", "m")
    assert d3.intro()["sentences_in_memory"] == 2 and d3.call("recall", {"question": "広報の期限は何ですか"})["verdict"] == "ANSWER"


def test_a_turn_without_a_report_is_not_filled_in(tmp_path):
    d = md.BaselineDoor(str(tmp_path / "ctx"), "context", "story", "m")
    c = Rec([[("text", "just text")], [("text", "again")], [("text", "and again")],                      # message 1: NO_TOOL_LIMIT tool-less turns
             [T("report", contradictions=[])]])
    r = story(c, d, [("1-1", "a"), ("1-2", "b")])
    assert [(t["turn"], t["ended"], t["report"]) for t in r.turns] == [("1-1", "no_tool_call", None), ("1-2", "report", {"contradictions": [], "bugs": []})]
    assert r.text_blocks_dropped == 3 and md.reports_of([lg._parse_line(x) for x in lg.read_raw_lines(d.ledger.dir)[0]])[0]["turn"] == "1-2"
    assert c.sent[1][-1]["content"].startswith("Your last turn had no tool call") and c.sent[3][-1] == {"role": "user", "content": "b"}


def test_turn_limit_and_refused_reports(tmp_path):
    d = md.BaselineDoor(str(tmp_path / "ctx"), "context", "story", "m")
    bad = [T("report", contradictions=[["1-1", "9-9"]])] * 3
    c = Rec([bad + [], [T("report", contradictions=[["1-1", "9-9"]])], [T("report", contradictions=[])]])
    r = story(c, d, [("1-1", "a")], max_calls=3)
    assert r.turns[0]["ended"] == "turn_limit" and r.turns[0]["report"] is None and r.tool_calls == 3
    # a refused report lets the model go on in the same turn
    d2 = md.BaselineDoor(str(tmp_path / "ctx2"), "context", "story", "m")
    c2 = Rec([[T("report", contradictions=[["1-1", "9-9"]])], [T("report", contradictions=[["1-1", "1-2"]])]])
    r2 = story(c2, d2, [("1-2", "x")])
    assert r2.turns[0]["ended"] == "report" and r2.turns[0]["calls"] == 2 and r2.turns[0]["report"]["contradictions"] == [["1-1", "1-2"]]


def test_a_tool_the_arm_does_not_offer_is_refused_by_the_driver_and_by_the_door(tmp_path):
    d = md.StructureDoor(str(tmp_path / "st"), "notes", "m")
    c = Rec([[T("emit"), T("weave_span", sid=0), T("report", contradictions=[])]])
    r = story(c, d, [("1-1", "a")])
    assert r.tool_calls == 3 and len(ledger_rows(d.session)) == 2                              # begin + report: the two foreign calls left no row


def test_an_api_error_ends_the_session_abandoned(tmp_path):
    class Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise RuntimeError("secret detail that must stay out of the ledger")
    d = md.StructureDoor(str(tmp_path / "st"), "notes", "m")
    r = story(Boom(), d, [("1-1", "a")])
    assert r.ended == "api_error" and "RuntimeError" in r.error and d.session.run.state.closed == ["abandoned", "api_error"]
    assert "secret detail" not in json.dumps(ledger_rows(d.session))
    assert refusal_of(d.call("write", {"text": "広報の期限は水曜"})) == "run_closed"


def test_the_question_phase_is_an_episode_of_the_loom_driver(tmp_path):
    store = str(tmp_path / "st")
    d = md.StructureDoor(store, "blind", "m")
    d.set_turn("1-1")
    d.call("write", {"text": "広報の期限は水曜"})
    d.commit()
    qd = md.AnswerDoor(store, "blind", "広報の期限は何ですか", "m")
    c = Rec([[T("recall", question="広報の期限は何ですか")], [T("weave_span", sid=0, tier="WORD", first="水曜", last="水曜")], [T("emit")]])
    res = drv.run_episode(c, qd, qd.run_id, "fake-model", "SYS", drv.first_message(qd.begin_result), md.api_tools(qd.tool_names, done=True), tool_choice={"type": "any"}, max_turns=10)
    assert res.ended == "closed" and md.answer_of_output(qd.output()) == {"kind": "value", "values": ["水曜"]}
    assert {t["name"] for t in c.calls[0]["tools"]} == set(md.QUESTION_TOOLS["blind"]) | {"done"}
    # blind: no notes in what the model got back
    assert "notes" not in json.dumps(c.sent[-1], ensure_ascii=False)


def test_answer_of_output_normalises_every_structure_outcome():
    assert md.answer_of_output({"status": "emitted", "text": "x"}) == {"kind": "value", "values": ["x"]}
    ch = [{"verdict": "ANSWER", "answers": [["a"]]}, {"verdict": "CHOICE", "answers": [["8080", "x"], ["9090"]]}]
    assert md.answer_of_output({"status": "abstained", "type": "contested", "recalls": ch}) == {"kind": "contested", "values": ["8080", "9090"]}
    assert md.answer_of_output({"status": "abstained", "type": "contested", "recalls": []}) == {"kind": "contested", "values": []}
    for o in ({"status": "abstained", "type": "no_record", "recalls": []}, {"status": "open", "recalls": []}, {"status": "run_not_verified"}):
        assert md.answer_of_output(o) == {"kind": "none", "values": []}

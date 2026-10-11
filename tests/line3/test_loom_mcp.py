"""LOOM-d tests: the FastMCP server `vera-loom` (docs/LINE3_LOOM_DESIGN.md 4, 9.1; `vera loom mcp`).

The tool list is the 18 operations; a model that connects over MCP can do exactly what the scripted weaver does and every call is one ledger row.
"""
import asyncio
import json
import os

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom import mcp as lm
from verantyx.loom.ops import MODEL_OPS
from loom_common import CORPUS, PY, ROOT, TASKS, rows

mcp_sdk = pytest.importorskip("mcp.server.fastmcp")


@pytest.fixture()
def bank(tmp_path):
    p = tmp_path / "tasks.jsonl"
    p.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in TASKS) + "\n", encoding="utf-8")
    return p


def call(m, tool, args):
    async def go():
        content, _ = await m.call_tool(tool, args)
        return json.loads(content[0].text)
    return asyncio.run(go())


def test_the_tool_list_is_the_18_operations(bank, tmp_path):
    m = lm.build(str(bank), str(tmp_path / "runs"))
    tools = asyncio.run(m.list_tools())
    assert [t.name for t in tools] == list(MODEL_OPS) and len(tools) == 18
    assert m.name == "vera-loom"
    for t in tools:
        assert t.description and len(t.description) > 20
        props = t.inputSchema["properties"]
        assert ("run_id" in props) == (t.name != "begin"), t.name
    by = {t.name: t for t in tools}
    assert by["seat_run"].inputSchema["properties"]["uids"]["type"] == "array"
    assert set(by["begin"].inputSchema["required"]) == {"task_id", "model"}
    assert "rotate" not in by and "undo" not in by


def test_the_worked_example_over_the_mcp_door(bank, tmp_path):
    m = lm.build(str(bank), str(tmp_path / "runs"))
    b = call(m, "begin", {"task_id": "demo/tokyo_ro", "model": "claude-haiku-4-5"})
    rid = b["run_id"]
    assert b["ok"] and b["task"]["mode"] == "record_only" and len(rid) == 12
    adds = [call(m, "add", {"run_id": rid, "text": t, "kind": "record", "tier": "WORD"}) for t in ("東京", "日本", "首都")]
    assert [a["uid"] for a in adds] == ["u1", "u2", "u3"]
    r4 = call(m, "add", {"run_id": rid, "text": "です", "kind": "constructed"})
    assert r4["refusal"] == "constructed_forbidden"
    c1 = call(m, "open_cross", {"run_id": rid, "tier": "WORD", "L": 1})["cid"]
    call(m, "seat", {"run_id": rid, "cid": c1, "seat": "centre", "uid": "u1"})
    call(m, "topic", {"run_id": rid, "cid": c1, "on": True})
    c2 = call(m, "open_cross", {"run_id": rid, "tier": "WORD", "L": 2})["cid"]
    call(m, "seat", {"run_id": rid, "cid": c2, "seat": "+x:0", "uid": "u2"})
    call(m, "seat", {"run_id": rid, "cid": c2, "seat": "centre", "uid": "u3"})
    call(m, "link", {"run_id": rid, "cid": c1})
    call(m, "link", {"run_id": rid, "cid": c2})
    dry = call(m, "read", {"run_id": rid})
    assert dry["text"] == "東京は日本の首都" and dry["refusals"] == []
    e = call(m, "emit", {"run_id": rid})
    assert e["ok"] and e["text"] == "東京は日本の首都"
    d = tmp_path / "runs" / rid
    assert lg.verify(d)["status"] == "OK" and lg.emitted_output(d)["text"] == "東京は日本の首都"
    assert len(rows(d)) == 15                                                         # every call is one row, refused or not


def test_over_mcp_the_same_script_gives_the_same_rows_as_the_scripted_weaver(bank, tmp_path):
    """The door adds nothing: the MCP run and the scripted run have byte-identical rows (up to the run_id label)."""
    from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
    m = lm.build(str(bank), str(tmp_path / "mcp"))
    srv = m.loom_server
    # make both runs use one label by driving the same server object through the tool wrappers and the weaver
    a = call(m, "begin", {"task_id": "demo/tokyo_ro", "model": "claude-haiku-4-5"})
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "claude-haiku-4-5", a["run_id"] + "x")
    res = weave_tokyo(w)
    assert res["text"] == "東京は日本の首都"
    rid = a["run_id"]
    for t in ("東京", "日本", "首都"):
        call(m, "add", {"run_id": rid, "text": t, "kind": "record", "tier": "WORD"})
    call(m, "add", {"run_id": rid, "text": "です", "kind": "constructed"})
    c1 = call(m, "open_cross", {"run_id": rid, "tier": "WORD", "L": 1})["cid"]
    call(m, "seat", {"run_id": rid, "cid": c1, "seat": "centre", "uid": "u1"})
    call(m, "topic", {"run_id": rid, "cid": c1, "on": True})
    c2 = call(m, "open_cross", {"run_id": rid, "tier": "WORD", "L": 2})["cid"]
    call(m, "seat", {"run_id": rid, "cid": c2, "seat": "+x:0", "uid": "u2"})
    call(m, "seat", {"run_id": rid, "cid": c2, "seat": "centre", "uid": "u3"})
    call(m, "link", {"run_id": rid, "cid": c1, "pos": 0})
    call(m, "link", {"run_id": rid, "cid": c2, "pos": 1})
    call(m, "emit", {"run_id": rid})
    ra, rb = rows(tmp_path / "mcp" / rid), rows(tmp_path / "mcp" / (rid + "x"))
    strip = lambda r: {k: v for k, v in r.items() if k not in ("prev", "sha")}
    ra[0]["result"].pop("run_id"), rb[0]["result"].pop("run_id")
    assert [strip(r) for r in ra] == [strip(r) for r in rb]


def test_a_call_the_sdk_rejects_against_the_schema_leaves_no_row(bank, tmp_path):
    """The boundary of "one call = one row" (L-LOOM-46): a mistyped argument is refused by the SDK before the server sees it, so it has no row;
    every call that reaches LoomServer.call with an existing run has exactly one (test_loom_review.py)."""
    m = lm.build(str(bank), str(tmp_path / "runs"))
    rid = call(m, "begin", {"task_id": "demo/tokyo_ro", "model": "m"})["run_id"]
    with pytest.raises(Exception):
        call(m, "seat_run", {"run_id": rid, "cid": "c1", "arm": "+x", "uids": "u1"})
    assert len(rows(tmp_path / "runs" / rid)) == 1
    r = call(m, "seat_run", {"run_id": rid, "cid": "c1", "arm": "+x", "uids": ["u1"]})
    assert r["refusal"] == "unknown_cid" and len(rows(tmp_path / "runs" / rid)) == 2


def test_the_server_over_stdio_with_the_sdk_client(bank, tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    runs = tmp_path / "stdio_runs"
    params = StdioServerParameters(command=PY, args=["-m", "verantyx.cli", "loom", "mcp", "--tasks", str(bank), "--runs-dir", str(runs)],
                                   env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT)

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                names = [t.name for t in tools.tools]
                res = await s.call_tool("begin", {"task_id": "demo/tokyo_ca", "model": "stdio-test"})
                b = json.loads(res.content[0].text)
                out = []
                for tool, args in (("add", {"text": "東京", "kind": "record", "tier": "WORD"}), ("open_cross", {"tier": "WORD", "L": 1}),
                                   ("seat", {"cid": "c1", "seat": "centre", "uid": "u1"}), ("link", {"cid": "c1"}), ("emit", {})):
                    r_ = await s.call_tool(tool, dict(args, run_id=b["run_id"]))
                    out.append(json.loads(r_.content[0].text))
                return names, b, out
    names, b, out = asyncio.run(asyncio.wait_for(go(), 120))
    assert names == list(MODEL_OPS)
    assert out[-1]["ok"] and out[-1]["text"] == "東京"
    assert lg.verify(runs / b["run_id"])["status"] == "OK"
    assert lg.emitted_output(runs / b["run_id"])["text"] == "東京"

"""LOOM-e/g tests: the sandbox files (L1), the drivers (scripted / L2 api with a fake client / subagent folder), the scorer, the task bank and the harness
(docs/LINE3_LOOM_DESIGN.md 7, 9, 10.1; T-LOOM-30, 31, 34, 35).

Every run folder and results folder of these tests is under tmp_path (nothing is written into experiments/line3/loom/runs or results).
The L2 driver is never run on a real model here (no key, no network): a recorded script of turns is replayed by `driver.ReplayClient`.
"""
import ast
import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

from verantyx.loom import driver as drv
from verantyx.loom import ledger as lg
from verantyx.loom.mcp import LoomServer
from verantyx.loom.ops import MODEL_OPS, normalize_task
from loom_common import CORPUS, PY, ROOT, rows

LOOM_X = os.path.join(ROOT, "experiments/line3/loom")


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


H = _load("loom_harness", os.path.join(LOOM_X, "harness.py"))
S = H.score
BANK = S.load_bank(H.BANK)
DEMO = S.load_bank(os.path.join(LOOM_X, "tasks_demo.jsonl"))
GOLD = S.load_gold()
BASES = ["I2-001", "I2-041", "I2-008", "I2-034", "I2-013", "R2-I013", "I2-025", "UF-001", "UF-015", "R2-U003"]
ANSWERABLE = BASES[:7]
UNANS = BASES[7:]
sha = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()


def run_scripted(tmp_path, base, mode, bank=None, driver="scripted", **kw):
    bank = bank or BANK
    row = H.select_task(bank, base, mode)
    return H.run(row, driver, bank_path=kw.pop("bank_path", H.BANK), bank=bank, gold=GOLD, runs_dir=str(tmp_path / "runs"),
                 results_dir=str(tmp_path / "res"), **kw)


# ------------------------------------------------------------------------------------------------------------
# the task bank (item 4)
# ------------------------------------------------------------------------------------------------------------
def test_the_task_bank_is_the_10_1_set_in_both_modes_plus_the_controls_and_holds_no_gold():
    assert len(BANK) == 30
    for b in BASES:
        for m in ("record_only", "constructed_allowed", "free_text"):
            r = H.select_task(BANK, b, m)
            assert r["text"] == GOLD[b]["question"] and r["bank2_id"] == b and r["lang"] == "prose" and r["corpus"].endswith("fulllead_sents.jsonl")
            assert (r.get("control") == "free_text") == (m == "free_text")
            assert r["task_id"] == "bank2/%s.%s" % (b, m)
    raw = open(H.BANK, encoding="utf-8").read()
    for b in ANSWERABLE:
        for alt in GOLD[b]["gold"].split("|"):
            if len(alt) >= 2:
                assert alt not in raw, "the gold of %s is in the task bank" % b
    assert [json.loads(l)["bank2_id"] for l in raw.splitlines()][:20:2] == BASES                   # the order of design 10.1
    unans_kind = {b: GOLD[b]["kind"] for b in BASES}
    assert all(unans_kind[b] == "unans" for b in UNANS) and all(unans_kind[b] != "unans" for b in ANSWERABLE)


def test_the_task_bank_loads_in_the_server_the_control_rows_included(tmp_path):
    srv = LoomServer.from_file(H.BANK, str(tmp_path / "runs"))                         # a bad `mode` would kill `vera loom mcp` at start
    assert len(srv.tasks) == 30
    for r in BANK.values():
        n = normalize_task(r)
        assert n["mode"] in ("record_only", "constructed_allowed") and "control" not in n and "bank2_id" not in n
        assert n["tiers"] == ["RUN", "WORD", "CHAR"]


def test_no_gold_in_the_agent_prompts():
    for fn in os.listdir(H.AGENTS_DIR):
        body = open(os.path.join(H.AGENTS_DIR, fn), encoding="utf-8").read()
        for b in ANSWERABLE:
            for alt in GOLD[b]["gold"].split("|"):
                if len(alt) >= 2:
                    assert alt not in body, "%s holds the gold of %s" % (fn, b)


# ------------------------------------------------------------------------------------------------------------
# L1: .mcp.json and the agent files (T-LOOM-35)
# ------------------------------------------------------------------------------------------------------------
def _mcp_config():
    cfg = json.load(open(os.path.join(ROOT, ".mcp.json"), encoding="utf-8"))
    return cfg["mcpServers"]["vera-loom"]


def test_mcp_json_names_the_server_and_its_inputs():
    s = _mcp_config()
    assert list(json.load(open(os.path.join(ROOT, ".mcp.json")))["mcpServers"]) == ["vera-loom"]
    assert s["args"][:4] == ["-m", "verantyx.cli", "loom", "mcp"]
    assert s["args"][-1] == "--isolated"                              # LOOM-d2 (L-LOOM-93, 119): the server runs under the OS profile, after the probe
    opts = dict(zip(s["args"][4:-1:2], s["args"][5:-1:2]))
    assert set(opts) == {"--tasks", "--runs-dir"} and s["args"].count("--isolated") == 1
    assert opts["--tasks"] == "experiments/line3/loom/tasks_bank2.jsonl" and os.path.isfile(os.path.join(ROOT, opts["--tasks"]))
    assert s["env"]["PYTHONPATH"] == "."


@pytest.fixture(scope="module")
def live_tool_names():
    """Start the server EXACTLY as .mcp.json says (command, args, env, cwd = the repository root) and list its tools; nothing else is called.
    (The server creates its --runs-dir, so a clean checkout gets an empty experiments/line3/loom/runs/; no run folder is made, `begin` is never called.)"""
    pytest.importorskip("mcp.server.fastmcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    s = _mcp_config()
    if not os.path.exists(s["command"]):
        pytest.skip("ENV_MISSING[vera_wiring_python]: .mcp.json names %s, which is not on this machine" % s["command"])
    params = StdioServerParameters(command=s["command"], args=s["args"], env=dict(os.environ, **s["env"]), cwd=ROOT)

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as sess:
                init = await sess.initialize()
                tools = await sess.list_tools()
                return init.serverInfo.name, [t.name for t in tools.tools]
    return asyncio.run(asyncio.wait_for(go(), 120))


def test_the_mcp_json_command_starts_the_server_and_lists_exactly_the_18_tools(live_tool_names):
    name, names = live_tool_names
    assert name == "vera-loom"
    assert names == list(MODEL_OPS) and len(names) == 18


def test_the_agent_files_hold_only_loom_tools(live_tool_names):
    live = {"mcp__vera-loom__" + n for n in live_tool_names[1]}
    for stem in ("loom-weaver", "loom-weaver-record-only"):
        meta, body = H.parse_agent_file(os.path.join(H.AGENTS_DIR, stem + ".md"))
        assert meta["name"] == stem and meta["model"] == "haiku" and meta["description"]
        assert set(meta["tools"]) == live and len(meta["tools"]) == len(set(meta["tools"])) == 18
        assert all(t.startswith("mcp__vera-loom__") for t in meta["tools"])
        for needle in ("emit", "abstain", "discarded", "begin", "only way"):
            assert needle in body.lower()
    meta, body = H.parse_agent_file(os.path.join(H.AGENTS_DIR, "loom-control.md"))
    assert meta["tools"] == ["mcp__vera-loom__begin", "mcp__vera-loom__lookup", "mcp__vera-loom__read_sentence"] and set(meta["tools"]) <= live
    assert meta["model"] == "haiku" and "不明" in body and "CONTROL" in body
    # no built-in tool name in any allow-list
    for fn in os.listdir(H.AGENTS_DIR):
        m, _ = H.parse_agent_file(os.path.join(H.AGENTS_DIR, fn))
        assert not {t for t in m["tools"] if not t.startswith("mcp__vera-loom__")}
        text = open(os.path.join(H.AGENTS_DIR, fn), encoding="utf-8").read()
        assert not any(k in text.split("\n---\n")[0] for k in ("Bash", "Read,", "Write", "Edit", "WebFetch", "Agent,", "Grep", "Glob"))


def test_the_mode_wording_of_the_two_weaver_files():
    _, ro = H.parse_agent_file(os.path.join(H.AGENTS_DIR, "loom-weaver-record-only.md"))
    _, ca = H.parse_agent_file(os.path.join(H.AGENTS_DIR, "loom-weaver.md"))
    assert "record_only" in ro and "constructed_forbidden" in ro and "constructed_allowed" in ca and "kind=\"constructed\"" in ca
    assert H.AGENT_OF_MODE == {"record_only": "loom-weaver-record-only", "constructed_allowed": "loom-weaver", "free_text": "loom-control"}
    assert H.agent_definition_sha("record_only") == hashlib.sha256(open(H.agent_file("record_only"), "rb").read()).hexdigest()


# ------------------------------------------------------------------------------------------------------------
# the scorer (item 3)
# ------------------------------------------------------------------------------------------------------------
def test_the_t9_rule_and_its_stricter_views():
    assert S.t9.hits_text("カール・マルクス", "カールマルクス") and S.t9.hits_text("キューバの太陽", "キューバの太陽")
    assert S.excess_chars("県社", "県社") == 0 and S.excess_chars("県社", "旧県社です") == 3 and S.excess_chars("県社", "県") is None
    assert S.excess_chars("a|bcd", "xbcdx") == 2                                             # the shortest matching alternative is not the longest
    ann = [{"s": "キューバ", "kind": "record"}, {"s": "の", "kind": "foundation"}, {"s": "太陽", "kind": "record"}]
    v = S.answer_view("キューバの太陽", "キューバの太陽", ann)
    assert v == {"hits_text": True, "excess_chars": 0, "hits_words": False, "hit_record_text": True}       # no single unit holds it, the record text does
    ann2 = [{"s": "キューバ", "kind": "constructed"}, {"s": "の", "kind": "foundation"}, {"s": "太陽", "kind": "record"}]
    assert S.answer_view("キューバの太陽", "キューバの太陽", ann2)["hit_record_text"] is False
    assert S.answer_view("青", "青", [{"s": "青", "kind": "record"}])["hits_words"] is True
    assert S.control_abstains("不明") and S.control_abstains("\n  不明です") and S.control_abstains("不明") and not S.control_abstains("答えは不明") \
        and not S.control_abstains("") and not S.control_abstains("ネパール")
    assert S.share_permille({"record": 6, "constructed": 0, "foundation": 1, "layout": 0}) == {"record": 857, "constructed": 0, "foundation": 142, "layout": 0}
    assert S.share_permille({"record": 0}) == {"record": 0}


def test_a_scored_run_is_typed_and_has_no_float(tmp_path):
    rs, path, obj = run_scripted(tmp_path, "I2-041", "record_only")
    assert isinstance(rs, S.RunScore) and rs.status == "hit" and rs.correct is True and rs.replay_verified and rs.verify_status == "OK"
    def walk(o):
        if isinstance(o, float):
            raise AssertionError("float in the result")
        for v in (o.values() if isinstance(o, dict) else o if isinstance(o, list) else ()):
            walk(v)
    walk(obj)
    assert rs.status in S.STATUSES and rs.outcome in S.OUTCOMES


def _srv(tmp_path, bank=None):
    return LoomServer([H.abs_row(r) for r in (bank or BANK).values()], str(tmp_path / "runs"))


def test_the_outcome_classes(tmp_path):
    srv = _srv(tmp_path)
    def begin(base, mode, rid):
        return srv.begin("bank2/%s.%s" % (base, mode), "m", rid)["run_id"]
    def weave_one(rid, word, tier="WORD"):
        u = srv.call("add", {"run_id": rid, "text": word, "kind": "record", "tier": tier})["uid"]
        c = srv.call("open_cross", {"run_id": rid, "tier": tier, "L": 1})["cid"]
        srv.call("seat", {"run_id": rid, "cid": c, "seat": "centre", "uid": u})
        srv.call("link", {"run_id": rid, "cid": c})
        return srv.call("emit", {"run_id": rid})
    score = lambda rid: S.score_run(str(tmp_path / "runs" / rid), BANK, GOLD)
    # miss: an answerable question with a wrong output
    r = begin("I2-025", "record_only", "miss"); assert weave_one(r, "ネパール")["ok"]
    s = score("miss"); assert (s.status, s.correct, s.hits_text) == ("miss", False, False)
    # abstained_wrong
    r = begin("I2-025", "record_only", "aw"); srv.call("abstain", {"run_id": r, "type": "no_record"})
    s = score("aw"); assert (s.status, s.outcome, s.correct, s.abstain_type) == ("abstained_wrong", "abstained", False, "no_record")
    # answered_unans: an output on an unanswerable question
    r = begin("UF-001", "record_only", "au"); assert weave_one(r, "ハッシュ")["ok"]
    s = score("au"); assert (s.status, s.correct, s.text) == ("answered_unans", False, "ハッシュ") and s.hits_text is None
    # abstained_correct
    r = begin("UF-001", "record_only", "ac"); srv.call("abstain", {"run_id": r, "type": "unknown"})
    s = score("ac"); assert (s.status, s.correct) == ("abstained_correct", True)
    # no_output: left open, closed by the harness
    r = begin("I2-025", "record_only", "no"); srv.harness(r, "abandoned", {"reason": "no_close"})
    s = score("no"); assert (s.status, s.outcome, s.correct) == ("no_output", "no_output", False) and s.facts["abandoned"] == ["no_close"]
    # hit, constructed: the share and the strict view
    r = begin("I2-025", "constructed_allowed", "hc")
    assert srv.call("add", {"run_id": r, "text": "青", "kind": "constructed"})["refusal"] == "constructed_shadows_record"
    u = srv.call("add", {"run_id": r, "text": "あおい", "kind": "constructed"})["uid"]
    c = srv.call("open_cross", {"run_id": r, "tier": "WORD", "L": 1})["cid"]
    srv.call("seat", {"run_id": r, "cid": c, "seat": "centre", "uid": u}); srv.call("link", {"run_id": r, "cid": c})
    assert srv.call("emit", {"run_id": r})["ok"]
    s = score("hc"); assert (s.status, s.hits_text) == ("miss", False) and s.chars["constructed"] == 3 and s.share_permille["constructed"] == 1000


def test_a_run_that_does_not_verify_is_not_scored(tmp_path):
    rs, path, obj = run_scripted(tmp_path, "I2-025", "record_only")
    d = tmp_path / "runs" / H.run_name(H.select_task(BANK, "I2-025", "record_only"), "scripted")
    raw = (d / "ops.jsonl").read_bytes()
    i = raw.index("青".encode("utf-8"))
    (d / "ops.jsonl").write_bytes(raw[:i] + "赤".encode("utf-8") + raw[i + 3:])                       # one character of a result changed
    t = S.score_run(str(d), BANK, GOLD)
    assert t.status == "run_not_verified" and t.outcome == "not_verified" and t.correct is None and t.text is None and t.replay_verified is False
    assert t.verify_status in ("TAMPERED", "HEAD_MISMATCH", "REPLAY_DIFFERS")
    # the CLI path refuses as well (exit 1) and writes a result that says so
    rc = H.main(["--results-dir", str(tmp_path / "res_t"), "score", str(d), "--driver", "scripted"])
    assert rc == 1
    r = json.load(open(str(tmp_path / "res_t" / "I2-025.record_only.scripted.json"), encoding="utf-8"))
    assert r["score"]["status"] == "run_not_verified" and r["output_text"] is None


def test_a_moved_repository_is_scored_with_the_corpus_flag(tmp_path):
    run_scripted(tmp_path, "I2-025", "record_only")
    d = tmp_path / "runs" / "I2-025.record_only.scripted"
    meta = json.load(open(d / "meta.json", encoding="utf-8"))
    meta["corpus"] = "/nonexistent/moved/fulllead_sents.jsonl"                                  # meta.json is not hashed: the path of the old tree
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert S.score_run(str(d), BANK, GOLD).status == "run_not_verified"
    rc = H.main(["--results-dir", str(tmp_path / "res_m"), "score", str(d), "--driver", "scripted", "--corpus", CORPUS])
    assert rc == 0 and json.load(open(str(tmp_path / "res_m" / "I2-025.record_only.scripted.json"), encoding="utf-8"))["score"]["status"] == "hit"


def test_self_corrections_are_read_from_the_ledger(tmp_path):
    srv = _srv(tmp_path, DEMO)
    rid = srv.begin("demo/tokyo_ro", "m", "sc")["run_id"]
    c = lambda tool, **a: srv.call(tool, dict(a, run_id=rid))
    assert c("lookup", text="存在しない語ですよ", tier="any")["matches"] == []
    assert c("lookup", text="東京", tier="any")["matches"]                              # the plan changed after the empty lookup
    u1 = c("add", text="東京", kind="record", tier="WORD")["uid"]
    u2 = c("add", text="日本", kind="record", tier="WORD")["uid"]
    cid = c("open_cross", tier="WORD", L=1)["cid"]
    assert c("seat", cid=cid, seat="centre", uid=u1)["ok"]
    assert c("seat", cid=cid, seat="centre", uid=u2)["refusal"] == "seat_occupied"       # a refusal ...
    assert c("unseat", cid=cid, seat="centre")["ok"]                                    # ... a correction before the emit ...
    assert c("seat", cid=cid, seat="centre", uid=u2)["ok"]                              # ... and the recovery of the same op
    c("link", cid=cid)
    assert c("emit")["text"] == "日本"
    sc = S.self_corrections(rows(tmp_path / "runs" / "sc"))
    assert sc["counts"] == {"unseat_swap_before_close": 1, "plan_change_after_empty": 1, "recovery_after_refusal": 1, "refusals_recoverable": 1}
    assert sc["recovery_after_refusal"][0]["refusal"] == "seat_occupied"
    # an empty lookup followed by abstain is a conclusion, not a plan change; a swap AFTER the close would not count (the run is closed)
    rid2 = srv.begin("demo/tokyo_ro", "m", "sc2")["run_id"]
    srv.call("lookup", {"run_id": rid2, "text": "存在しない語ですよ", "tier": "any"})
    srv.call("abstain", {"run_id": rid2, "type": "no_record"})
    assert S.self_corrections(rows(tmp_path / "runs" / "sc2"))["counts"]["plan_change_after_empty"] == 0
    facts = S.run_facts(str(tmp_path / "runs" / "sc"))
    assert facts["refusals"] == {"seat_occupied": 1} and facts["ops_by_name"]["seat"] == 3 and facts["emit_attempts"] == 1


# ------------------------------------------------------------------------------------------------------------
# the harness with the scripted driver (item 5)
# ------------------------------------------------------------------------------------------------------------
def test_demo_tasks_end_to_end_with_the_scripted_driver(tmp_path):
    out = {}
    for mode in ("constructed_allowed", "record_only"):
        rs, path, obj = run_scripted(tmp_path, "demo/tokyo_" + ("ca" if mode == "constructed_allowed" else "ro"), None, bank=DEMO, bank_path=os.path.join(LOOM_X, "tasks_demo.jsonl"))
        out[mode] = (rs, path, obj)
        assert rs.status == "unscored" and rs.correct is None and rs.kind == "none" and rs.replay_verified
        assert os.path.basename(path) == "demo_tokyo_%s.%s.scripted.json" % ("ca" if mode == "constructed_allowed" else "ro", mode)
    assert out["constructed_allowed"][0].text == "東京は日本の首都です" and out["record_only"][0].text == "東京は日本の首都"
    ca = out["constructed_allowed"][2]
    assert ca["score"]["chars"] == {"record": 6, "constructed": 2, "foundation": 2, "layout": 0}
    assert ca["score"]["share_permille"]["constructed"] == 200
    ro = out["record_only"][2]
    assert ro["refusals"] == {"constructed_forbidden": 1}                                   # row 4 of the worked example is refused
    # the same bytes as the core's demo (L-LOOM-25 asserts them): output_sha of the worked example
    assert out["record_only"][0].output_sha == "c74f3319b605745e07a008b876bae444d9cb0dc4ed59387af165176cde9816c8"
    assert out["constructed_allowed"][0].output_sha == "70a569eba879736d1bf1b7a6e86ff8a281216d571a2ce4fc9c3d42e4d83470e2"
    # the results file
    obj = json.load(open(out["record_only"][1], encoding="utf-8"))
    for k in ("ledger", "ledger_head", "output_text", "annotated", "score", "op_counts", "refusals", "self_corrections", "wall", "free_text_dropped",
              "harness_meta", "closing", "declared_model", "driver", "mode", "control"):
        assert k in obj, k
    assert obj["driver"] == "scripted" and obj["control"] is False and obj["harness_meta"] == [{"driver": "scripted", "requested_model": "scripted-weaver"}]
    assert obj["wall"]["ledger_ns"] > 0 and obj["wall"]["driver_ns"] > 0 and obj["declared_model"] == "scripted-weaver"
    assert os.path.exists(obj["ledger"]) or os.path.exists(os.path.join(ROOT, obj["ledger"]))


def test_a_single_unit_answer_and_an_abstention_on_the_bank2_tasks(tmp_path):
    rs, path, obj = run_scripted(tmp_path, "I2-041", "record_only")
    assert (rs.status, rs.text, rs.correct, rs.mode, rs.kind) == ("hit", "キューバの太陽", True, "record_only", "answerable")
    assert (rs.hits_text, rs.hits_words, rs.hit_record_text, rs.excess_chars) == (True, False, True, 0)
    assert rs.chars == {"record": 6, "constructed": 0, "foundation": 1, "layout": 0} and rs.share_permille["record"] == 857
    assert [(a["s"], a["kind"]) for a in rs.annotated] == [("キューバ", "record"), ("の", "foundation"), ("太陽", "record")]
    assert obj["refusals"] == {} and obj["op_counts"]["by_op"]["lookup"] == 2 and obj["op_counts"]["emit_attempts"] == 1
    assert obj["self_corrections"]["counts"] == {"unseat_swap_before_close": 0, "plan_change_after_empty": 0, "recovery_after_refusal": 0, "refusals_recoverable": 0}
    assert obj["closing"]["op"] == "emit" and rs.facts["declared_model"] == "scripted-weaver"
    uf, _, uobj = run_scripted(tmp_path, "UF-001", "record_only")
    assert (uf.status, uf.outcome, uf.correct, uf.kind, uf.abstain_type, uf.text) == ("abstained_correct", "abstained", True, "unans", "no_record", None)
    assert uobj["closing"]["op"] == "abstain" and uobj["op_counts"]["by_op"]["lookup"] == 2


def test_the_whole_scripted_set(tmp_path):
    seen = {}
    for b in BASES:
        for m in ("record_only", "constructed_allowed", "free_text"):
            rs, _, obj = run_scripted(tmp_path, b, m)
            seen[(b, m)] = rs
            assert rs.replay_verified and rs.control == (m == "free_text") and (obj["control_note"] is not None) == rs.control
    for b in ANSWERABLE:
        for m in ("record_only", "constructed_allowed", "free_text"):
            assert seen[(b, m)].status == "hit", (b, m)
            assert seen[(b, m)].chars.get("constructed", 0) == 0
    for b in UNANS:
        for m in ("record_only", "constructed_allowed", "free_text"):
            assert seen[(b, m)].status == "abstained_correct", (b, m)
    assert seen[("I2-008", "record_only")].text == "カールマルクス" and seen[("I2-034", "record_only")].text == "1981年"
    assert seen[("I2-001", "record_only")].text == "ハッシュ表"
    assert seen[("I2-041", "free_text")].text == "キューバの太陽" and seen[("I2-041", "free_text")].share_permille == {}


def test_a_control_is_labelled_and_its_text_is_the_output(tmp_path):
    rs, path, obj = run_scripted(tmp_path, "I2-041", "free_text")
    assert rs.control and rs.mode == "free_text" and "CONTROL" in rs.note and obj["control"] is True and "CONTROL" in obj["control_note"]
    assert os.path.basename(path) == "I2-041.free_text.scripted.json"
    d = tmp_path / "runs" / "I2-041.free_text.scripted"
    ops = [(r["actor"], r["op"]) for r in rows(d)]
    assert ops[-2:] == [("harness", "free_text_control"), ("harness", "abandoned")] and not any(o[1] in ("emit", "add") for o in ops)
    assert rows(d)[-2]["args"]["text"] == "キューバの太陽" and rows(d)[-1]["args"] == {"reason": "control_free_text"}
    # a control run is scored from its free_text_control row, whatever the mode label of the weaving rows is
    assert S.score_run(str(d), BANK, GOLD).status == "hit"


def test_a_rerun_never_overwrites(tmp_path):
    run_scripted(tmp_path, "I2-025", "record_only")
    with pytest.raises(H.HarnessError, match="results file exists"):
        run_scripted(tmp_path, "I2-025", "record_only")
    with pytest.raises(H.HarnessError, match="results file exists"):
        H.write_result(str(tmp_path / "res" / "I2-025.record_only.scripted.json"), {})
    with pytest.raises(H.HarnessError, match="begin refused"):
        H.run(H.select_task(BANK, "I2-025", "record_only"), "scripted", bank_path=H.BANK, bank=BANK, gold=GOLD, runs_dir=str(tmp_path / "runs"),
              results_dir=str(tmp_path / "res_other"))                                # the run folder exists: begin refuses, nothing is deleted
    rs, _, _ = run_scripted(tmp_path, "I2-025", "record_only", tag="again")
    assert rs.status == "hit"


def test_the_subagent_driver_is_a_stub_that_explains(tmp_path, capsys):
    with pytest.raises(H.HarnessError, match="operator"):
        run_scripted(tmp_path, "I2-025", "record_only", driver="subagent")
    rc = H.main(["--runs-dir", str(tmp_path / "runs"), "run", "--task", "I2-041", "--mode", "record_only", "--driver", "subagent"])
    cap = capsys.readouterr()
    assert rc == 2 and "operator" in cap.err
    p = json.loads(cap.out)
    assert p["agent_call"] == {"tool": "Agent", "subagent_type": "loom-weaver-record-only", "model": "haiku", "prompt": "task_id: bank2/I2-041.record_only"}
    assert p["agent_definition_sha256"] == H.agent_definition_sha("record_only") and "restart" in p["restart_needed"]
    assert not (tmp_path / "runs").exists() or os.listdir(str(tmp_path / "runs")) == []              # prepare writes nothing
    cp = H.prepare(H.select_task(BANK, "I2-041", "free_text"), "subagent")
    assert cp["agent"] == "loom-control" and cp["control"] and any("control_free_text" in s for s in cp["after"])
    assert any("--subagent-transcript" in s for s in cp["after"]) and "find" in cp["by_hand"]


def test_a_subagent_run_is_scored_from_its_folder_alone(tmp_path, capsys):
    """The operator's session: the server wrote the run (random id), the subagent's final message is saved to a file, then note / close / score."""
    srv = LoomServer([H.abs_row(r) for r in BANK.values()], str(tmp_path / "runs"), nonce="operator")
    rid = srv.begin("bank2/I2-041.record_only", "claude-haiku-4-5")["run_id"]
    c = lambda tool, **a: srv.call(tool, dict(a, run_id=rid))
    u1 = c("add", text="キューバ", kind="record", tier="WORD")["uid"]
    u2 = c("add", text="太陽", kind="record", tier="WORD")["uid"]
    cid = c("open_cross", tier="WORD", L=2)["cid"]
    c("seat", cid=cid, seat="+x:0", uid=u1); c("seat", cid=cid, seat="centre", uid=u2); c("link", cid=cid)
    assert c("emit")["text"] == "キューバの太陽"
    # a second, unscored folder of another task
    rid2 = srv.begin("bank2/UF-001.record_only", "claude-haiku-4-5")["run_id"]
    srv.call("abstain", {"run_id": rid2, "type": "no_record"})
    del srv                                                                              # the server process is gone: the folder is all there is
    found = H.find_runs(BANK, str(tmp_path / "runs"), str(tmp_path / "res"), task="I2-041", mode="record_only")
    assert [f["task_id"] for f in found] == ["bank2/I2-041.record_only"] and not found[0]["scored"] and found[0]["last_op"] == "emit"
    d = found[0]["run_dir"]
    final = tmp_path / "final.txt"
    final.write_text("答えはキューバの太陽です。ハッシュ表ではありません【末尾メモ】", encoding="utf-8")              # free text with the gold of another task: scores nothing
    assert H.note(d, str(final), False, "loom-weaver-record-only", "haiku") == ["harness_meta", "free_text_dropped"]
    assert H.close(d).startswith("closed: ")
    rc = H.main(["--runs-dir", str(tmp_path / "runs"), "--results-dir", str(tmp_path / "res"), "score", d, "--driver", "subagent"])
    assert rc == 0
    obj = json.load(open(str(tmp_path / "res" / "I2-041.record_only.subagent.json"), encoding="utf-8"))
    assert obj["score"]["status"] == "hit" and obj["output_text"] == "キューバの太陽" and obj["driver"] == "subagent" and obj["score"]["replay_verified"]
    assert obj["harness_meta"] == [{"driver": "L1-subagent", "requested_model": "haiku", "agent_definition_sha": H.agent_definition_sha("record_only")}]
    assert obj["free_text_dropped"]["n"] == 1 and obj["free_text_dropped"]["chars"] == len(final.read_text(encoding="utf-8"))
    assert obj["free_text_dropped"]["sha256"] == [sha(final.read_text(encoding="utf-8"))]
    ledger = open(os.path.join(d, "ops.jsonl"), encoding="utf-8").read()
    assert "【末尾メモ】" not in ledger and "ではありません" not in ledger                          # only the hash of the free text is stored
    assert [f["scored"] for f in H.find_runs(BANK, str(tmp_path / "runs"), str(tmp_path / "res"), task="I2-041")] == [True]
    # the abstaining folder, scored by the same path
    d2 = H.find_runs(BANK, str(tmp_path / "runs"), str(tmp_path / "res"), task="UF-001")[0]["run_dir"]
    rs2, _, _ = H.score_folder(d2, "subagent", BANK, GOLD, str(tmp_path / "res"))
    assert rs2.status == "abstained_correct"
    assert H.main(["--runs-dir", str(tmp_path / "runs"), "--results-dir", str(tmp_path / "res"), "find"]) == 0
    assert "unscored" not in capsys.readouterr().out.split("bank2/I2-041")[1].split("\n")[0]


def test_a_subagent_control_run(tmp_path):
    srv = LoomServer([H.abs_row(r) for r in BANK.values()], str(tmp_path / "runs"), nonce="operator")
    rid = srv.begin("bank2/UF-015.free_text", "claude-haiku-4-5")["run_id"]
    srv.call("lookup", {"run_id": rid, "text": "立案", "tier": "any"})
    d = str(tmp_path / "runs" / rid)
    f = tmp_path / "ctl.txt"
    f.write_text("不明", encoding="utf-8")
    H.note(d, str(f), True, "loom-control", "haiku")
    H.close(d, "control_free_text")
    rs, _, obj = H.score_folder(d, "subagent", BANK, GOLD, str(tmp_path / "res"))
    assert rs.control and rs.status == "abstained_correct" and obj["control"] is True and obj["abandoned"] == ["control_free_text"]


def test_the_scripted_run_is_byte_identical_across_hash_seeds(tmp_path):
    """The harness CLI in a child process under two other PYTHONHASHSEEDs gives the same ledger head and output sha as this process."""
    rs, path, obj = run_scripted(tmp_path, "I2-041", "record_only")
    for seed in ("1", "12345"):
        out = tmp_path / ("s" + seed)
        r = subprocess.run([PY, os.path.join(LOOM_X, "harness.py"), "--runs-dir", str(out / "runs"), "--results-dir", str(out / "res"), "run", "--task", "I2-041",
                            "--mode", "record_only", "--driver", "scripted"], cwd=ROOT, capture_output=True, text=True, timeout=300,
                           env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1"))
        assert r.returncode == 0, r.stderr
        o2 = json.load(open(str(out / "res" / "I2-041.record_only.scripted.json"), encoding="utf-8"))
        assert o2["ledger_head"] == obj["ledger_head"] and o2["score"]["output_sha"] == rs.output_sha
        assert open(str(out / "runs" / "I2-041.record_only.scripted" / "ops.jsonl"), "rb").read() == \
            open(str(tmp_path / "runs" / "I2-041.record_only.scripted" / "ops.jsonl"), "rb").read()


# ------------------------------------------------------------------------------------------------------------
# the L2 API driver with a fake client (item 5; T-LOOM-31)
# ------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mcp_tools(tmp_path_factory):
    pytest.importorskip("mcp.server.fastmcp")
    return H.mcp_tool_objects(H.BANK, str(tmp_path_factory.mktemp("toolruns")))


def api_names():
    return {n for n in MODEL_OPS if n != "begin"} | {"done"}


def api_run(tmp_path, mcp_tools, script, base="I2-041", mode="record_only", model="claude-haiku-4-5", **kw):
    client = drv.ReplayClient(script, allowed_tools=api_names())
    r = H.run(H.select_task(BANK, base, mode), "api", bank_path=H.BANK, bank=BANK, gold=GOLD, runs_dir=str(tmp_path / "runs"),
              results_dir=str(tmp_path / "res"), model=model, client=client, mcp_tools=mcp_tools, **kw)
    return client, r


L = lambda name, **a: ("tool", name, a)
I2_041_WEAVE = [
    [L("lookup", text="キューバ", tier="any"), L("lookup", text="太陽", tier="any")],
    [L("add", text="キューバ", kind="record", tier="WORD"), L("add", text="太陽", kind="record", tier="WORD"), L("open_cross", tier="WORD", L=2)],
    [L("seat", cid="c1", seat="+x:0", uid="u1"), L("seat", cid="c1", seat="centre", uid="u2"), L("link", cid="c1")],
    [L("read"), L("emit")],
]


def test_the_api_driver_weaves_through_tool_calls_only(tmp_path, mcp_tools):
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, I2_041_WEAVE)
    assert rs.status == "hit" and rs.text == "キューバの太陽" and rs.replay_verified and rs.mode == "record_only"
    d = tmp_path / "runs" / "I2-041.record_only.api"
    ops = [(r["actor"], r["op"]) for r in rows(d)]
    assert ops[:2] == [("model", "begin"), ("harness", "harness_meta")] and [o for o in ops if o[0] == "model"][-1] == ("model", "emit")
    assert ops[-1] == ("harness", "harness_meta")                                                  # the provider's response model, after the episode
    assert obj["driver_report"]["ended"] == "closed" and obj["driver_report"]["turns"] == 4 and obj["driver_report"]["tool_calls"] == 10
    assert obj["harness_meta"][0]["driver"] == "L2-api" and obj["harness_meta"][0]["requested_model"] == "claude-haiku-4-5"
    assert obj["harness_meta"][0]["agent_definition_sha"] == obj["driver_report"]["system_prompt_sha256"]
    assert obj["harness_meta"][1] == {"response_model": "fake-model"}
    # the request: forced tool use where accepted, only loom tools, no begin, no run_id anywhere
    first = client.calls[0]
    assert first["tool_choice"] == {"type": "any"} and first["model"] == "claude-haiku-4-5" and "strict" not in first["tools"][0]
    names = [t["name"] for t in first["tools"]]
    assert set(names) == api_names() and len(names) == 18 and names[-1] == "done"
    for t in first["tools"]:
        assert "run_id" not in t["input_schema"].get("properties", {}) and "run_id" not in t["input_schema"].get("required", [])
        assert t["input_schema"]["additionalProperties"] is False
    assert "Driver note" in first["system"] and "only way" in first["system"].lower()
    assert client.calls[-1]["n_messages"] == 7                                                     # user, (assistant, results) x 3


def test_free_text_in_every_turn_is_dropped_and_scores_nothing(tmp_path, mcp_tools):
    script = [
        [("text", "答えはキューバの太陽です【自由記述A】"), L("lookup", text="太陽", tier="any")],
        [("text", "ハッシュ表と書けばよい【自由記述B】"), L("add", text="太陽", kind="record", tier="WORD"), L("open_cross", tier="WORD", L=1)],
        [L("seat", cid="c1", seat="centre", uid="u1"), L("link", cid="c1")],
        [("text", "やはり キューバの太陽 が答えだ【自由記述C】"), L("emit")],
    ]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script)
    assert rs.text == "太陽" and rs.status == "miss" and rs.hits_text is False                    # the free text said the gold; the emitted text is what is scored
    d = tmp_path / "runs" / "I2-041.record_only.api"
    drops = [r for r in rows(d) if r["op"] == "free_text_dropped"]
    texts = ["答えはキューバの太陽です【自由記述A】", "ハッシュ表と書けばよい【自由記述B】", "やはり キューバの太陽 が答えだ【自由記述C】"]
    assert [r["args"] for r in drops] == [{"sha256": sha(t), "chars": len(t)} for t in texts]
    raw = (d / "ops.jsonl").read_text(encoding="utf-8")
    assert "【自由記述" not in raw and "答えは" not in raw and "ハッシュ表と" not in raw          # only hashes reach the ledger
    assert obj["free_text_dropped"]["n"] == 3 and obj["driver_report"]["text_blocks_dropped"] == 3
    assert "【自由記述" not in json.dumps(obj, ensure_ascii=False)                                     # nor the result file
    assert lg.emitted_output(d)["text"] == "太陽"


def test_done_ends_the_episode_and_an_open_run_is_abandoned(tmp_path, mcp_tools):
    script = [[L("lookup", text="太陽", tier="any")], [L("done")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script)
    assert obj["driver_report"]["ended"] == "done" and obj["abandoned"] == ["done_without_close"]
    assert rs.status == "no_output" and rs.correct is False and rs.text is None
    assert len(client.calls) == 2                                                                  # nothing after done


def test_done_after_emit_in_one_turn_is_a_closed_episode(tmp_path, mcp_tools):
    script = I2_041_WEAVE[:3] + [[L("emit"), L("done")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script)
    assert rs.status == "hit" and obj["driver_report"]["ended"] == "closed" and obj["abandoned"] == []


def test_three_tool_less_turns_end_the_episode(tmp_path, mcp_tools):
    script = [[("text", "答えはキューバの太陽です")], [("text", "もう一度")], [("text", "三回目")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script, model="claude-sonnet-5-5")
    assert obj["driver_report"]["ended"] == "no_tool_call" and obj["abandoned"] == ["no_tool_call"] and rs.status == "no_output"
    assert obj["free_text_dropped"]["n"] == 3 and len(client.calls) == 3
    # a model that rejects forced tool use gets auto + strict tools, and a reminder is sent between the tool-less turns
    assert client.calls[0]["tool_choice"] == {"type": "auto"} and all(t["strict"] is True for t in client.calls[0]["tools"])
    assert client.calls[1]["n_messages"] == 3
    # a tool-less turn followed by a tool call resets the count
    script2 = [[("text", "考えます")], [L("lookup", text="太陽", tier="any")], [("text", "うーん")], [L("abstain", type="no_record")]]
    c2, (rs2, _, obj2) = api_run(tmp_path, mcp_tools, script2, base="UF-001", model="claude-sonnet-5-5")
    assert obj2["driver_report"]["ended"] == "closed" and rs2.status == "abstained_correct" and obj2["driver_report"]["tool_less_turns"] == 0


def test_tool_choice_by_model_family():
    assert drv.tool_choice_for("claude-haiku-4-5") == ({"type": "any"}, False)
    for m in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-mythos-5-1"):
        assert drv.tool_choice_for(m) == ({"type": "auto"}, True), m
    # EXACT ids (L-LOOM-63): the neighbours that accept forced tool use are not caught by a prefix or a substring
    for m in ("claude-opus-4-8", "claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-mythos-5", "fable-5", "mythos-5", "claude-opus-5-50",
              "my-claude-sonnet-5-5-clone", "claude-haiku-4-5", ""):
        assert drv.tool_choice_for(m) == ({"type": "any"}, False), m
    assert drv.FORCED_REJECTED == ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-mythos-5-1")


def test_a_run_id_the_model_passes_cannot_reach_another_run(tmp_path, mcp_tools):
    script = [[L("lookup", run_id="someone-else", text="太陽", tier="any"), L("status", run_id="../x")], [L("abstain", type="unknown")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script, base="UF-001")
    d = tmp_path / "runs" / "UF-001.record_only.api"
    model_ops = [r["op"] for r in rows(d) if r["actor"] == "model"]
    assert model_ops == ["begin", "lookup", "status", "abstain"]
    assert sorted(os.listdir(str(tmp_path / "runs"))) == ["UF-001.record_only.api"]
    assert rs.status == "abstained_correct"


def test_a_tool_the_model_names_that_was_not_offered_is_refused_without_a_row(tmp_path, mcp_tools):
    script = [[L("begin", task_id="bank2/I2-025.record_only", model="x"), L("rotate", cid="c1")], [L("abstain", type="unknown")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script, base="UF-001")
    d = tmp_path / "runs" / "UF-001.record_only.api"
    assert [r["op"] for r in rows(d) if r["actor"] == "model"] == ["begin", "abstain"]
    assert sorted(os.listdir(str(tmp_path / "runs"))) == ["UF-001.record_only.api"]                # `begin` was not run: no second run


def test_an_api_error_leaves_a_closed_ledger_and_the_error_only_in_the_result(tmp_path, mcp_tools):
    class Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise RuntimeError("529 overloaded sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    r = H.run(H.select_task(BANK, "I2-025", "record_only"), "api", bank_path=H.BANK, bank=BANK, gold=GOLD, runs_dir=str(tmp_path / "runs"),
              results_dir=str(tmp_path / "res"), client=Boom, mcp_tools=mcp_tools)
    rs, path, obj = r
    assert obj["driver_report"]["ended"] == "api_error" and obj["abandoned"] == ["api_error"] and rs.status == "no_output"
    assert "RuntimeError" in obj["driver_report"]["error"]
    assert "overloaded" not in (tmp_path / "runs" / "I2-025.record_only.api" / "ops.jsonl").read_text(encoding="utf-8")


def test_max_turns_abandons(tmp_path, mcp_tools):
    srv_rows = [[L("status")] for _ in range(3)]
    client = drv.ReplayClient(srv_rows)
    srv = LoomServer([H.abs_row(H.select_task(BANK, "I2-025", "record_only"))], str(tmp_path / "runs"))
    b = srv.begin("bank2/I2-025.record_only", "m", "mt")
    res = drv.run_episode(client, srv, "mt", "claude-haiku-4-5", "sys", drv.first_message(b), drv.api_tools(mcp_tools), max_turns=3)
    assert res.ended == "max_turns" and res.turns == 3 and srv.closed("mt") == ["abandoned", "max_turns"]


def test_the_api_control_answers_in_free_text(tmp_path, mcp_tools):
    script = [[("text", "探します"), L("lookup", text="太陽", tier="any"), L("lookup", text="キューバ", tier="any")], [("text", "キューバの太陽")]]
    client = drv.ReplayClient(script, allowed_tools={"lookup", "read_sentence"})
    rs, path, obj = H.run(H.select_task(BANK, "I2-041", "free_text"), "api", bank_path=H.BANK, bank=BANK, gold=GOLD, runs_dir=str(tmp_path / "runs"),
                          results_dir=str(tmp_path / "res"), client=client, mcp_tools=mcp_tools)
    assert [t["name"] for t in client.calls[0]["tools"]] == ["lookup", "read_sentence"] and client.calls[0]["tool_choice"] == {"type": "auto"}
    assert rs.control and rs.status == "hit" and rs.text == "キューバの太陽" and obj["driver_report"]["ended"] == "control_answer"
    assert obj["free_text_dropped"]["n"] == 1                                                      # the narration before the tool calls is dropped, the answer is the output
    assert os.path.basename(path) == "I2-041.free_text.api.json"
    rs2 = S.score_run(str(tmp_path / "runs" / "I2-041.free_text.api"), BANK, GOLD)
    assert rs2.status == "hit" and rs2.control


def test_the_real_client_factory_is_the_only_place_that_names_the_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(H.HarnessError, match="anthropic"):
        H.make_anthropic_client()
    pkg = os.path.join(ROOT, "verantyx/loom")
    for fn in os.listdir(pkg):
        if fn.endswith(".py"):
            tree = ast.parse(open(os.path.join(pkg, fn), encoding="utf-8").read())
            for n in ast.walk(tree):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module] if isinstance(n, ast.ImportFrom) and n.module else []
                assert not any(m.split(".")[0] in ("anthropic", "openai", "requests", "httpx") for m in mods), (fn, mods)
    src = open(os.path.join(LOOM_X, "harness.py"), encoding="utf-8").read()
    assert src.count("import anthropic") == 1 and "def make_anthropic_client" in src


# ------------------------------------------------------------------------------------------------------------
# after the review (L-LOOM-59 .. L-LOOM-64)
# ------------------------------------------------------------------------------------------------------------
def _control_run(tmp_path, base, text, rid):
    """A control run written by a server (random-style id), with `text` stored by `note`."""
    srv = LoomServer([H.abs_row(r) for r in BANK.values()], str(tmp_path / "runs"), nonce="operator")
    r = srv.begin("bank2/%s.free_text" % base, "claude-haiku-4-5", rid)["run_id"]
    srv.call("lookup", {"run_id": r, "text": "太陽", "tier": "any"})
    f = tmp_path / (rid + ".txt")
    f.write_text(text, encoding="utf-8")
    d = str(tmp_path / "runs" / r)
    H.note(d, str(f), True, "loom-control", "haiku")
    H.close(d, "control_free_text")
    return S.score_run(d, BANK, GOLD)


def test_a_control_is_scored_on_its_answer_line_only(tmp_path):
    assert S.answer_line("\n  わかりません\n候補は…") == "わかりません" and S.answer_line("") == "" and S.answer_line("ＡＢＣ\nx") == "ABC"
    rs = _control_run(tmp_path, "I2-041", "わかりません\n候補はキューバの太陽", "c1")
    assert rs.control and rs.status == "miss" and rs.hits_text is False and rs.answer_line == "わかりません" and rs.excess_chars is None
    assert "キューバの太陽" in rs.text                                                                 # the whole message is kept, not scored
    rs = _control_run(tmp_path, "I2-041", "キューバの太陽\nなお別の候補もあります", "c2")
    assert rs.status == "hit" and rs.hits_text is True and rs.excess_chars == 0 and rs.answer_line == "キューバの太陽"
    rs = _control_run(tmp_path, "I2-041", "答えは次のとおりです。キューバの太陽です", "c3")                  # one line: the whole line is scored (excess is reported)
    assert rs.status == "hit" and rs.excess_chars > 0
    rs = _control_run(tmp_path, "UF-001", "不明\nたぶん衝突処理", "c4")
    assert rs.status == "abstained_correct"
    rs = _control_run(tmp_path, "UF-001", "たぶん\n不明", "c5")                                       # 不明 on line 2 is not an abstention
    assert rs.status == "answered_unans"


def test_note_takes_control_and_agent_from_the_ledger_and_the_bank(tmp_path):
    srv = LoomServer([H.abs_row(r) for r in BANK.values()], str(tmp_path / "runs"), nonce="operator")
    rid = srv.begin("bank2/I2-041.record_only", "claude-haiku-4-5")["run_id"]
    d = str(tmp_path / "runs" / rid)
    f = tmp_path / "gold.txt"
    f.write_text("キューバの太陽", encoding="utf-8")                                                  # the probe: the gold as "control" text into a weaver run
    before = open(os.path.join(d, "ops.jsonl"), "rb").read()
    with pytest.raises(H.HarnessError, match="control_mismatch") as e:
        H.note(d, str(f), True, "loom-weaver-record-only", "haiku")
    assert e.value.code == "control_mismatch"
    with pytest.raises(H.HarnessError, match="agent_mismatch"):
        H.note(d, str(f), False, "loom-control", "haiku")
    with pytest.raises(H.HarnessError, match="agent_mismatch"):
        H.note(d, str(f), False, "loom-weaver", "haiku")                                          # the constructed_allowed agent on a record_only run
    with pytest.raises(H.HarnessError, match="note_conflict"):
        H.note(d, str(f), False, None, "haiku", transcript=str(f))
    assert open(os.path.join(d, "ops.jsonl"), "rb").read() == before                              # nothing was written by any refusal
    assert H.note(d, str(f), False, None, "haiku") == ["harness_meta", "free_text_dropped"]       # --agent omitted: the bank's agent is used
    assert "キューバの太陽" not in open(os.path.join(d, "ops.jsonl"), encoding="utf-8").read()
    rws = rows(d)
    assert rws[-2]["args"]["agent_definition_sha"] == H.agent_definition_sha("record_only") and rws[-1]["op"] == "free_text_dropped"
    with pytest.raises(H.HarnessError, match="already_noted"):
        H.note(d, str(f), False, None, "haiku")
    # a control run: --control is optional, the bank says it is one; the weaver agent is refused
    rid2 = srv.begin("bank2/UF-015.free_text", "claude-haiku-4-5")["run_id"]
    d2 = str(tmp_path / "runs" / rid2)
    g = tmp_path / "ctl.txt"
    g.write_text("不明", encoding="utf-8")
    with pytest.raises(H.HarnessError, match="agent_mismatch"):
        H.note(d2, str(g), False, "loom-weaver-record-only", "haiku")
    assert H.note(d2, str(g), False, None, "haiku") == ["harness_meta", "free_text_control"]
    assert rows(d2)[-1]["args"]["text"] == "不明"
    # an unknown task / a scripted folder
    rs, _, _ = run_scripted(tmp_path, "I2-025", "record_only")
    with pytest.raises(H.HarnessError, match="not_an_l1_run"):
        H.note(str(tmp_path / "runs" / "I2-025.record_only.scripted"), str(g), False, None, "haiku")


class FakeSubagent:
    """What Claude Code's subagent transcript holds (shape as pinned in TRANSCRIPT_PIN), built around a real LoomServer.  Every call is run on the server and
    recorded as an assistant tool_use row (one block per row, like the real file) and a user tool_result row."""

    def __init__(self, tmp_path, task_id, model="claude-haiku-4-5"):
        self.srv = LoomServer([H.abs_row(r) for r in BANK.values()], str(tmp_path / "runs"), nonce="operator")
        self.rows = [{"type": "user", "isSidechain": True, "agentId": "a1", "message": {"role": "user", "content": "task_id: %s" % task_id}},
                     {"type": "attachment", "isSidechain": True, "attachment": {"type": "skills"}}]
        self.model, self.n, self.rid = model, 0, None
        self.call_tool("begin", {"task_id": task_id, "model": model}, lambda a: self.srv.begin(a["task_id"], a["model"]))
        self.rid = json.loads(self.rows[-1]["message"]["content"][0]["content"][0]["text"])["run_id"]

    def asst(self, block):
        self.rows.append({"type": "assistant", "isSidechain": True, "agentId": "a1", "requestId": "r%d" % len(self.rows),
                          "message": {"role": "assistant", "model": self.model, "id": "msg_%d" % len(self.rows), "content": [block], "stop_reason": None}})

    def call_tool(self, name, args, run):
        self.n += 1
        uid = "toolu_%d" % self.n
        self.asst({"type": "tool_use", "id": uid, "name": "mcp__vera-loom__" + name if name in MODEL_OPS else name, "input": args, "caller": {"type": "direct"}})
        out = run(args)
        self.rows.append({"type": "user", "isSidechain": True, "agentId": "a1", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": uid, "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, sort_keys=True)}]}]}})
        return out

    def c(self, tool, **a):
        return self.call_tool(tool, dict(a, run_id=self.rid), lambda args: self.srv.call(tool, args))

    def weave_cuba(self):
        u1 = self.c("add", text="キューバ", kind="record", tier="WORD")["uid"]
        u2 = self.c("add", text="太陽", kind="record", tier="WORD")["uid"]
        cid = self.c("open_cross", tier="WORD", L=2)["cid"]
        self.c("seat", cid=cid, seat="+x:0", uid=u1); self.c("seat", cid=cid, seat="centre", uid=u2); self.c("link", cid=cid)
        assert self.c("emit")["text"] == "キューバの太陽"

    def finish(self, path, final="答えはキューバの太陽です。【末尾メモ】", thinking=True):
        if thinking:
            self.asst({"type": "thinking", "thinking": "(summary)", "signature": "x"})
        self.asst({"type": "text", "text": final})
        with open(path, "w", encoding="utf-8") as f:
            for r in self.rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return str(path)


def test_the_transcript_path_names_the_run_hashes_the_final_text_and_checks_the_tools(tmp_path, capsys):
    sub = FakeSubagent(tmp_path, "bank2/I2-041.record_only")
    sub.weave_cuba()
    final = "答えはキューバの太陽です。【末尾メモ】"
    tp = sub.finish(tmp_path / "agent-a1.jsonl", final)
    (tmp_path / "agent-a1.meta.json").write_text(json.dumps({"agentType": "loom-weaver-record-only"}), encoding="utf-8")
    argv = ["--runs-dir", str(tmp_path / "runs"), "--results-dir", str(tmp_path / "res")]
    rc = H.main(argv + ["note", "--subagent-transcript", tp, "--requested-model", "haiku"])
    out = capsys.readouterr().out
    d = str(tmp_path / "runs" / sub.rid)
    assert rc == 0 and ("RUN_DIR=" + d) in out and "harness_meta,free_text_dropped" in out and "T-LOOM-34: pass" in out
    rws = rows(d)
    assert rws[-2]["args"] == {"driver": "L1-subagent", "requested_model": "haiku", "response_model": "claude-haiku-4-5",
                               "agent_definition_sha": H.agent_definition_sha("record_only")}
    assert rws[-1]["op"] == "free_text_dropped" and rws[-1]["args"] == {"sha256": sha(final), "chars": len(final)}
    assert "【末尾メモ】" not in open(os.path.join(d, "ops.jsonl"), encoding="utf-8").read()
    chk = json.load(open(os.path.join(d, "transcript_check.json"), encoding="utf-8"))
    assert chk["t_loom_34"] == "pass" and chk["violations"] == [] and chk["loom_calls"] == chk["tool_uses"] == 8 and chk["ledger_model_rows"] == 8
    assert chk["agent_type"] == "loom-weaver-record-only" and chk["final_text_sha256"] == sha(final)
    assert chk["transcript_sha256"] == hashlib.sha256(open(tp, "rb").read()).hexdigest()
    # the folder with the extra unhashed file still verifies and scores; the result carries the check
    assert H.main(argv + ["close", d]) == 0
    assert H.main(argv + ["score", d, "--driver", "subagent"]) == 0
    obj = json.load(open(str(tmp_path / "res" / "I2-041.record_only.subagent.json"), encoding="utf-8"))
    assert obj["score"]["status"] == "hit" and obj["t_loom_34"] == "pass" and obj["transcript_check"]["loom_calls"] == 8
    assert obj["harness_meta"][0]["response_model"] == "claude-haiku-4-5"
    # noting again, or against the wrong RUN_DIR, is refused
    with pytest.raises(H.HarnessError, match="already_noted"):
        H.note_ex(None, None, False, None, "haiku", transcript=tp, runs_dir=str(tmp_path / "runs"))
    other = FakeSubagent(tmp_path, "bank2/I2-025.record_only")
    other.c("abstain", type="unknown")
    tp2 = other.finish(tmp_path / "agent-a2.jsonl")
    with pytest.raises(H.HarnessError, match="run_dir_mismatch"):
        H.note_ex(d, None, False, None, "haiku", transcript=tp2, runs_dir=str(tmp_path / "runs"))


def test_the_transcript_reports_a_non_loom_tool_and_rows_nobody_in_the_transcript_wrote(tmp_path, capsys):
    sub = FakeSubagent(tmp_path, "bank2/I2-041.record_only")
    sub.call_tool("Bash", {"command": "ls"}, lambda a: {"stdout": ""})                          # a built-in tool: T-LOOM-34 violated
    sub.call_tool("ToolSearch", {"query": "x"}, lambda a: {})
    sub.srv.call("lookup", {"run_id": sub.rid, "text": "太陽", "tier": "any"})                  # the PARENT called the loom on this run: a row the transcript lacks
    sub.weave_cuba()
    tp = sub.finish(tmp_path / "agent-b.jsonl")
    rc = H.main(["--runs-dir", str(tmp_path / "runs"), "note", "--subagent-transcript", tp])
    cap = capsys.readouterr()
    assert rc == 1 and "T-LOOM-34: violations" in cap.out
    assert "VIOLATION: non_loom_tool:Bash" in cap.err and "non_loom_tool:ToolSearch" in cap.err and "ledger_rows_not_in_transcript:" in cap.err
    d = str(tmp_path / "runs" / sub.rid)
    chk = json.load(open(os.path.join(d, "transcript_check.json"), encoding="utf-8"))
    assert chk["t_loom_34"] == "violations" and chk["non_loom_tools"] == ["Bash", "ToolSearch"]
    assert rows(d)[-1]["op"] == "free_text_dropped"                                              # the rows are written; the violation travels with the result
    H.close(d)
    rs, _, obj = H.score_folder(d, "subagent", BANK, GOLD, str(tmp_path / "res"))
    assert obj["t_loom_34"] == "violations" and "Bash" in json.dumps(obj["transcript_check"])


def test_the_transcript_of_a_control_stores_the_text_and_a_weaver_text_is_never_stored(tmp_path):
    sub = FakeSubagent(tmp_path, "bank2/I2-041.free_text", )
    sub.c("lookup", text="太陽", tier="any")
    tp = sub.finish(tmp_path / "agent-c.jsonl", "キューバの太陽", thinking=False)
    done, chk = H.note_ex(None, None, False, "loom-control", "haiku", transcript=tp, runs_dir=str(tmp_path / "runs"))
    assert done == ["harness_meta", "free_text_control"] and chk["t_loom_34"] == "pass"
    d = str(tmp_path / "runs" / sub.rid)
    assert rows(d)[-1]["args"]["text"] == "キューバの太陽"
    H.close(d, "control_free_text")
    assert S.score_run(d, BANK, GOLD).status == "hit"
    # the same text through a weaver run is hashed only, whatever the caller says
    w = FakeSubagent(tmp_path, "bank2/I2-041.constructed_allowed")
    w.weave_cuba()
    tpw = w.finish(tmp_path / "agent-w.jsonl", "キューバの太陽", thinking=False)
    with pytest.raises(H.HarnessError, match="control_mismatch"):
        H.note_ex(None, None, True, None, "haiku", transcript=tpw, runs_dir=str(tmp_path / "runs"))
    H.note_ex(None, None, False, None, "haiku", transcript=tpw, runs_dir=str(tmp_path / "runs"))
    assert "text" not in rows(str(tmp_path / "runs" / w.rid))[-1]["args"]


def test_a_transcript_of_another_shape_is_a_typed_refusal(tmp_path):
    def refuse(code, rows_, runs=None):
        p = tmp_path / ("t_%s.jsonl" % code)
        p.write_text("".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) + "\n" for r in rows_), encoding="utf-8")
        with pytest.raises(H.HarnessError) as e:
            H.parse_subagent_transcript(str(p)) if runs is None else H.note_ex(None, None, False, None, None, transcript=str(p), runs_dir=runs)
        assert e.value.code == code, (code, e.value)
    u = lambda c: {"type": "user", "message": {"role": "user", "content": c}}
    a = lambda c: {"type": "assistant", "message": {"role": "assistant", "content": c, "model": "m"}}
    refuse("transcript_shape", ["not json\n"])
    refuse("transcript_shape", [[1, 2]])
    refuse("transcript_shape", [])
    refuse("transcript_shape", [{"type": "assistant", "message": {"role": "user", "content": []}}])
    refuse("transcript_shape", [a(5)])
    refuse("transcript_shape", [u("hi")])                                                       # no assistant row
    refuse("transcript_unfinished", [u("hi"), a([{"type": "text", "text": "x"}]), u([{"type": "tool_result", "tool_use_id": "t", "content": "x"}])])
    refuse("transcript_unfinished", [u("hi"), a([{"type": "tool_use", "id": "t", "name": "mcp__vera-loom__status", "input": {}}])])
    refuse("transcript_no_final_text", [u("hi"), a([{"type": "thinking", "thinking": "x"}])])
    refuse("transcript_no_begin", [u("hi"), a([{"type": "text", "text": "x"}])])
    b = lambda i, ok: [a([{"type": "tool_use", "id": i, "name": "mcp__vera-loom__begin", "input": {"task_id": "t", "model": "m"}}]),
                       u([{"type": "tool_result", "tool_use_id": i, "content": json.dumps({"ok": ok, "run_id": "r" + i})}])]
    refuse("transcript_no_begin", [u("hi")] + b("1", False) + [a([{"type": "text", "text": "x"}])])                  # a refused begin is no run
    refuse("transcript_multiple_begins", [u("hi")] + b("1", True) + b("2", True) + [a([{"type": "text", "text": "x"}])])
    # a run id that is not a folder under --runs-dir
    refuse("run_folder_not_found", [u("hi")] + b("1", True) + [a([{"type": "text", "text": "x"}])], runs=str(tmp_path / "runs"))
    # a string tool_result content parses too
    p = tmp_path / "ok.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in [u("hi")] + b("9", True) + [a([{"type": "text", "text": "fin"}])]), encoding="utf-8")
    tr = H.parse_subagent_transcript(str(p))
    assert tr["begin"]["run_id"] == "r9" and tr["final_text"] == "fin" and tr["models"] == ["m"] and tr["tool_names"] == ["mcp__vera-loom__begin"]


def test_find_refuses_scripted_folders_and_warns_on_ambiguity(tmp_path, capsys):
    run_scripted(tmp_path, "I2-041", "record_only")                                              # a scripted folder in the same runs dir
    srv = LoomServer([H.abs_row(r) for r in BANK.values()], str(tmp_path / "runs"), nonce="operator")
    r1 = srv.begin("bank2/I2-041.record_only", "claude-haiku-4-5")["run_id"]
    argv = ["--runs-dir", str(tmp_path / "runs"), "--results-dir", str(tmp_path / "res")]
    refused = []
    found = H.find_runs(BANK, str(tmp_path / "runs"), str(tmp_path / "res"), task="I2-041", mode="record_only", refused=refused)
    assert [f["run_dir"] for f in found] == [str(tmp_path / "runs" / r1)] and [r["driver"] for r in refused] == ["scripted"]
    assert H.main(argv + ["find", "--task", "I2-041", "--mode", "record_only"]) == 0
    cap = capsys.readouterr()
    assert r1 in cap.out and "I2-041.record_only.scripted" not in cap.out and "refused" in cap.err
    r2 = srv.begin("bank2/I2-041.record_only", "claude-haiku-4-5")["run_id"]                     # two unscored candidates: no newest-wins
    assert H.main(argv + ["find", "--task", "I2-041", "--mode", "record_only"]) == 3
    cap = capsys.readouterr()
    assert "AMBIGUOUS: 2" in cap.err and "newest is NOT picked" in cap.err and r1 in cap.out and r2 in cap.out
    assert H.main(argv + ["find", "--task", "UF-001"]) == 0                                       # nothing is ambiguous about no candidate


def test_the_defaults_keep_the_scripted_baseline_apart_from_the_operator_folders():
    assert H.default_dirs("scripted") == (H.BASELINE_RUNS, H.BASELINE_RESULTS)
    for d in ("subagent", "api", "operator"):
        assert H.default_dirs(d) == (H.RUNS_DIR, H.RESULTS_DIR)
    assert H.BASELINE_RUNS == os.path.join(LOOM_X, "baseline_scripted", "runs") and H.RUNS_DIR == os.path.join(LOOM_X, "runs")
    # .mcp.json serves the operator folder, and no scripted run is in it
    cfg = json.load(open(os.path.join(ROOT, ".mcp.json"), encoding="utf-8"))
    assert cfg["mcpServers"]["vera-loom"]["args"][-2:] == ["experiments/line3/loom/runs", "--isolated"]
    if os.path.isdir(H.RUNS_DIR):
        for d in os.listdir(H.RUNS_DIR):
            assert not d.endswith(".scripted"), d
    readme = os.path.join(LOOM_X, "baseline_scripted", "README.md")
    if os.path.isdir(H.BASELINE_RUNS):
        assert os.path.isfile(readme) and "gold" in open(readme, encoding="utf-8").read()


def test_a_scripted_control_says_it_is_the_scripts_own_words_and_the_result_shows_the_views(tmp_path, capsys):
    rs, path, obj = run_scripted(tmp_path, "I2-041", "free_text")
    assert "WRITTEN WITH THE GOLD KNOWN" in obj["control_note"] and "not a measurement" in obj["control_note"] and obj["model_result"] is False
    assert obj["score"]["answer_line"] == "キューバの太陽"
    rs2, _, obj2 = run_scripted(tmp_path, "I2-041", "record_only")
    assert obj2["answer_view"] == {"hits_text": True, "hit_record_text": True, "excess_chars": 0} and "hits_words" in obj2["footnotes"]
    assert obj2["score"]["hits_words"] is False and obj2["model_result"] is False and obj2["t_loom_34"] == "unchecked"
    assert obj2["control_note"] is None
    assert H.main(["--results-dir", str(tmp_path / "res"), "summary"]) == 0
    out = capsys.readouterr().out
    assert "hits_text" in out and "hit_record_text" in out and "excess_chars" in out
    line = [ln for ln in out.splitlines() if ln.startswith("bank2/I2-041.record_only")][0].split()
    assert line[3] == "hit" and line[4:7] == ["Y", "Y", "0"] and "(1) hits_words" in out


def test_the_driver_stops_executing_a_turn_once_the_run_has_closed(tmp_path, mcp_tools):
    script = I2_041_WEAVE[:3] + [[L("emit"), L("lookup", text="太陽", tier="any"), L("abstain", type="unknown")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script)
    d = tmp_path / "runs" / "I2-041.record_only.api"
    assert rs.status == "hit" and obj["driver_report"]["ended"] == "closed" and obj["driver_report"]["calls_skipped_after_close"] == 2
    ops = [(r["actor"], r["op"], r["result"].get("refusal")) for r in rows(d) if r["actor"] == "model"]
    assert ops[-1][1] == "emit" and not any(o[2] == "run_closed" for o in ops)                      # nothing after the close, no run_closed refusal at all
    assert obj["refusals"] in ({}, None) or "run_closed" not in obj["refusals"]
    assert obj["driver_report"]["tool_calls"] == 9                                                  # 2 + 3 + 3 calls, then the emit; the two others were not executed
    assert len(client.calls) == 4


def test_thinking_blocks_are_counted_apart_with_hash_and_length_only(tmp_path, mcp_tools):
    secret = "思考: 答えはキューバの太陽【思考メモ】"
    script = [[("thinking", secret), ("text", "ことば【本文】"), L("lookup", text="太陽", tier="any")],
              [("redacted_thinking", "ENCRYPTED-BLOB"), L("abstain", type="unknown")]]
    client, (rs, path, obj) = api_run(tmp_path, mcp_tools, script, base="UF-001")
    td = obj["driver_report"]["thinking_dropped"]
    assert td == {"n": 2, "chars": len(secret) + len("ENCRYPTED-BLOB"), "sha256": [sha(secret), sha("ENCRYPTED-BLOB")]}
    assert obj["driver_report"]["text_blocks_dropped"] == 1 and obj["free_text_dropped"]["n"] == 1      # thinking is not a text block and not a ledger row
    raw = (tmp_path / "runs" / "UF-001.record_only.api" / "ops.jsonl").read_text(encoding="utf-8") + json.dumps(obj, ensure_ascii=False)
    assert "【思考メモ】" not in raw and "ENCRYPTED-BLOB" not in raw and "【本文】" not in raw

"""LOOM-control tests (L-LOOM-150..156): the `no_tools` control, the stop layer of a run, the unanswerable task bank, the ADV bank door, determinism.

Every run folder of these tests is under tmp_path.  No model is called (a fake client replays a recorded answer); no key, no network.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter
from types import SimpleNamespace

import pytest

from verantyx.loom import driver as drv
from verantyx.loom.mcp import LoomServer
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
from loom_common import PY, ROOT, rows

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
UNANS_BANK = os.path.join(LOOM_X, "tasks_unans.jsonl")
BANK = S.load_bank(UNANS_BANK)
GOLD = S.load_gold()
DEMO = S.load_bank(os.path.join(LOOM_X, "tasks_demo.jsonl"))
MODES4 = ("record_only", "constructed_allowed", "free_text", "no_tools")


class AnswerClient:
    """A fake `anthropic` client: ONE reply, a list of text blocks; records every request it gets."""

    def __init__(self, *texts, usage=(11, 4), boom=False):
        self.texts = texts
        self.calls = []
        self.boom = boom
        self.usage = usage
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        if self.boom:
            raise RuntimeError("529 overloaded")
        blocks = [SimpleNamespace(type="text", text=t) for t in self.texts]
        return SimpleNamespace(content=blocks, stop_reason="end_turn", model="fake-model",
                               usage=SimpleNamespace(input_tokens=self.usage[0], output_tokens=self.usage[1]))


def run_no_tools(tmp_path, base, client, bank=None, tag=""):
    bank = bank or BANK
    return H.run(H.select_task(bank, base, "no_tools"), "api", bank_path=UNANS_BANK, bank=bank, gold=GOLD, runs_dir=str(tmp_path / "runs"),
                 results_dir=str(tmp_path / "res"), model="claude-haiku-5-5", client=client, tag=tag)


# ------------------------------------------------------------------------------------------------------------
# the task bank (item 3)
# ------------------------------------------------------------------------------------------------------------
def test_the_unans_bank_is_the_25_fulllead_unanswerable_items_in_four_modes():
    unans = [k for k, v in GOLD.items() if v["kind"] == "unans"]
    fulllead = [k for k in unans if k.startswith("UF-") or k.startswith("R2-U00") and int(k[-3:]) <= 5]
    assert len(fulllead) == 25 and len(BANK) == 100
    bases = []
    for r in BANK.values():
        if r["bank2_id"] not in bases:
            bases.append(r["bank2_id"])
    assert bases == fulllead                                                    # the bank2.tsv order
    for b in bases:
        for m in MODES4:
            r = H.select_task(BANK, b, m)
            assert r["task_id"] == "bank2/%s.%s" % (b, m) and r["text"] == GOLD[b]["question"] and r["kind"] == "unans"
            assert r["lang"] == "prose" and r["corpus"].endswith("fulllead_sents.jsonl") and r["tiers"] == ["RUN", "WORD", "CHAR"]
            assert r.get("control") == (m if m in ("free_text", "no_tools") else None)
            assert r["mode"] == ("record_only" if m in ("free_text", "no_tools") else m)
            assert H.label_of(r) == m
    assert [json.loads(l)["bank2_id"] for l in open(UNANS_BANK, encoding="utf-8")][::4] == bases


def test_the_three_rows_of_the_h55d_bank_are_the_same_rows_here():
    old = S.load_bank(H.BANK)
    for tid, o in old.items():
        if o["bank2_id"] in ("UF-001", "UF-015", "R2-U003"):
            assert dict(BANK[tid], kind=None) == dict(o, kind=None) and "kind" not in o                # the only new key is the scorer-side `kind`


def test_the_bank_loads_in_the_server_and_the_model_never_sees_the_kind(tmp_path):
    srv = LoomServer.from_file(UNANS_BANK, str(tmp_path / "runs"))
    assert len(srv.tasks) == 100
    b = srv.begin("bank2/UF-002.record_only", "m", "r1")
    assert b["ok"] and "kind" not in json.dumps(b) and "unans" not in json.dumps(b)              # normalize_task drops it
    assert srv.tasks["bank2/UF-002.no_tools"]["mode"] == "record_only"


def test_the_bank_holds_no_gold_and_every_item_is_unans_in_the_gold_table():
    for r in BANK.values():
        assert GOLD[r["bank2_id"]]["kind"] == "unans" and GOLD[r["bank2_id"]]["gold"] == ""
        assert set(r) <= {"bank2_id", "base", "control", "corpus", "kind", "lang", "mode", "task_id", "text", "tiers"}


def test_the_adversarial_bank_door_needs_no_code_change(tmp_path):
    """tasks_unans_adv.jsonl (ADV-nnn, authored later, same schema, `kind` = unans) runs through the same harness: --bank, no gold-table entry."""
    rows_ = []
    for m in MODES4:
        rows_.append({"bank2_id": "ADV-001", "base": "ADV-001", "corpus": "experiments/line3/bank2/data/fulllead_sents.jsonl", "kind": "unans", "lang": "prose",
                      "mode": "record_only" if m in ("free_text", "no_tools") else m, "task_id": "bank2/ADV-001.%s" % m, "text": "ハッシュテーブルの発明者は誰ですか",
                      "tiers": ["RUN", "WORD", "CHAR"], **({"control": m} if m in ("free_text", "no_tools") else {})})
    p = tmp_path / "tasks_unans_adv.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows_), encoding="utf-8")
    bank = S.load_bank(str(p))
    assert "ADV-001" not in GOLD
    rs, path, obj = H.run(H.select_task(bank, "ADV-001", "no_tools"), "api", bank_path=str(p), bank=bank, gold=GOLD, runs_dir=str(tmp_path / "runs"),
                          results_dir=str(tmp_path / "res"), model="m", client=AnswerClient("ヨハン・ヤコブ"))
    assert rs.kind == "unans" and rs.status == "answered_unans" and not rs.correct and os.path.basename(path) == "ADV-001.no_tools.api.json"
    rs2, _, _ = H.run(H.select_task(bank, "ADV-001", "no_tools"), "api", bank_path=str(p), bank=bank, gold=GOLD, runs_dir=str(tmp_path / "runs"),
                      results_dir=str(tmp_path / "res"), model="m", client=AnswerClient("不明"), tag="b")
    assert rs2.status == "abstained_correct" and rs2.kind == "unans"
    srv = LoomServer.from_file(str(p), str(tmp_path / "r2"))
    assert len(srv.tasks) == 4
    # a declared kind that the gold table contradicts, or any other value, is refused
    with pytest.raises(ValueError, match="kind"):
        S.TaskFacts.of(dict(BANK["bank2/UF-001.record_only"], kind="answerable"), GOLD)
    with pytest.raises(ValueError, match="unans"):
        S.TaskFacts.of(dict(H.select_task(S.load_bank(H.BANK), "I2-001", "record_only"), kind="unans"), GOLD)
    # without the declaration an id outside the gold table is "none" (unscored), as before
    bare = dict(rows_[0])
    del bare["kind"]
    assert S.TaskFacts.of(bare, GOLD).kind == "none"


def test_the_harness_cli_takes_bank_and_lists_the_four_modes(tmp_path):
    out = subprocess.run([PY, os.path.join(LOOM_X, "harness.py"), "--bank", UNANS_BANK, "list"], capture_output=True, text=True, cwd=ROOT,
                         env=dict(os.environ, PYTHONHASHSEED="0", PYTHONPATH=ROOT))
    assert out.returncode == 0
    lines = out.stdout.splitlines()
    assert len(lines) == 100 and sum(1 for l in lines if " no_tools " in l) == 25
    prep = subprocess.run([PY, os.path.join(LOOM_X, "harness.py"), "--bank", UNANS_BANK, "prepare", "--task", "UF-002", "--mode", "no_tools", "--driver", "api",
                           "--model", "claude-haiku-5-5"], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED="0", PYTHONPATH=ROOT))
    o = json.loads(prep.stdout)
    assert o["control"] is True and o["agent"] is None and "--mode no_tools --driver api" in o["command"]
    assert o["agent_definition_sha256"] == hashlib.sha256(H.NO_TOOLS_SYSTEM.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------------------
# the no_tools control (item 1)
# ------------------------------------------------------------------------------------------------------------
def test_no_tools_offers_no_tool_and_no_tool_choice_and_scores_the_answer_line(tmp_path):
    client = AnswerClient("年間約3万トン\n補足：これは推定です")
    rs, path, obj = run_no_tools(tmp_path, "UF-002", client)
    assert len(client.calls) == 1
    kw = client.calls[0]
    assert "tools" not in kw and "tool_choice" not in kw                                        # NO tools at all
    assert set(kw) == {"model", "max_tokens", "system", "messages"} and kw["model"] == "claude-haiku-5-5"
    assert kw["system"] == H.NO_TOOLS_SYSTEM and kw["messages"] == [{"role": "user", "content": GOLD["UF-002"]["question"]}]
    assert rs.control and rs.mode == "no_tools" and rs.status == "answered_unans" and not rs.correct and rs.outcome == "emitted"
    assert rs.answer_line == "年間約3万トン" and rs.text == "年間約3万トン\n補足：これは推定です"          # the answer line is what is scored; the rest is kept, scored nowhere
    assert obj["control"] is True and obj["mode"] == "no_tools" and "NO-TOOLS CONTROL" in obj["control_note"] and obj["model_result"] is True
    dr = obj["driver_report"]
    assert dr["ended"] == "control_answer" and dr["turns"] == 1 and dr["tool_calls"] == 0 and dr["tools"] == [] and dr["tool_choice"] is None
    assert dr["usage"]["input_tokens"] == 11 and dr["usage"]["output_tokens"] == 4 and dr["usage"]["calls"] == 1
    assert dr["system_prompt_sha256"] == hashlib.sha256(H.NO_TOOLS_SYSTEM.encode("utf-8")).hexdigest() and dr["request_keys"] == ["max_tokens", "messages", "model", "system"]
    assert os.path.basename(path) == "UF-002.no_tools.api.json" and obj["harness_meta"][0]["driver"] == "L2-api"
    assert obj["harness_meta"][0]["agent_definition_sha"] == dr["system_prompt_sha256"]
    # the ledger framework: begin, harness_meta, the answer as free_text_control, the control close; no model row but begin
    rws = rows(tmp_path / "runs" / "UF-002.no_tools.api")
    assert [(r["actor"], r["op"]) for r in rws][:5] == [("model", "begin"), ("harness", "harness_meta"), ("harness", "harness_meta"), ("harness", "free_text_control"), ("harness", "abandoned")]
    assert [r for r in rws if r["actor"] == "model"] == rws[:1]
    assert rws[4]["args"] == {"reason": "control_free_text"} and rws[2]["args"] == {"response_model": "fake-model"} and rs.replay_verified
    assert rs.stop_layer == "L_none" and rs.layer["control_outcome"] == "answered" and rs.layer["lookups"] == 0 and rs.layer["build_attempts"] == 0


def test_no_tools_abstention_is_fumei_and_an_empty_or_failed_reply_is_no_output(tmp_path):
    rs, _, obj = run_no_tools(tmp_path, "UF-003", AnswerClient("不明"))
    assert rs.status == "abstained_correct" and rs.abstain_type == "不明" and rs.stop_layer == "L_meta" and rs.layer["control_outcome"] == "不明"
    rs, _, obj = run_no_tools(tmp_path, "UF-004", AnswerClient("\n  \n不明（根拠なし）"))             # the first NON-EMPTY line is the answer line
    assert rs.status == "abstained_correct" and rs.answer_line == "不明(根拠なし)"
    rs, _, obj = run_no_tools(tmp_path, "UF-005", AnswerClient(boom=True))
    assert rs.status == "no_output" and obj["driver_report"]["ended"] == "api_error" and obj["abandoned"] == ["control_free_text"]
    assert rs.stop_layer == "L_other" and rs.layer["control_outcome"] == "no_output" and "overloaded" not in open(
        tmp_path / "runs" / "UF-005.no_tools.api" / "ops.jsonl", encoding="utf-8").read()


def test_no_tools_scores_an_answerable_question_by_the_exact_rule(tmp_path):
    base = S.load_bank(H.BANK)
    row = dict(base["bank2/I2-041.free_text"], control="no_tools", task_id="bank2/I2-041.no_tools")
    bank = {row["task_id"]: row}
    rs, _, _ = run_no_tools(tmp_path, "I2-041", AnswerClient("キューバの太陽"), bank=bank)
    assert rs.status == "hit" and rs.hit_exact and rs.control and rs.mode == "no_tools"
    rs, _, _ = run_no_tools(tmp_path, "I2-041", AnswerClient("キューバの太陽という意味"), bank=bank, tag="b")
    assert rs.status == "miss" and not rs.hit_exact and rs.hits_text


def test_no_tools_is_api_only_and_never_overwrites(tmp_path):
    row = H.select_task(BANK, "UF-002", "no_tools")
    for drv_, why in (("scripted", "no_tools_api_only"), ("subagent", "subagent driver")):
        with pytest.raises(H.HarnessError, match=why):
            H.run(row, drv_, bank_path=UNANS_BANK, bank=BANK, gold=GOLD, runs_dir=str(tmp_path / "r"), results_dir=str(tmp_path / "s"))
    assert not (tmp_path / "r").exists()
    with pytest.raises(H.HarnessError, match="no_tools_api_only"):
        H.prepare(row, "subagent")
    run_no_tools(tmp_path, "UF-002", AnswerClient("不明"))
    with pytest.raises(H.HarnessError, match="exists"):
        run_no_tools(tmp_path, "UF-002", AnswerClient("不明"))


def test_the_free_text_control_still_offers_the_lookups_and_is_labelled_free_text(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    tools = H.mcp_tool_objects(UNANS_BANK, str(tmp_path / "toolruns"))
    client = drv.ReplayClient([[("tool", "lookup", {"text": "衝突", "tier": "any"})], [("text", "不明")]], allowed_tools={"lookup", "read_sentence"})
    rs, _, obj = H.run(H.select_task(BANK, "UF-001", "free_text"), "api", bank_path=UNANS_BANK, bank=BANK, gold=GOLD, runs_dir=str(tmp_path / "runs"),
                       results_dir=str(tmp_path / "res"), model="m", client=client, mcp_tools=tools)
    assert [t["name"] for t in client.calls[0]["tools"]] == ["lookup", "read_sentence"] and rs.mode == "free_text"
    assert rs.status == "abstained_correct" and "FREE-TEXT CONTROL" in obj["control_note"]
    assert rs.stop_layer == "L_meta" and rs.layer["lookups"] == 1 and rs.layer["control_outcome"] == "不明"


# ------------------------------------------------------------------------------------------------------------
# the stop layer (item 2)
# ------------------------------------------------------------------------------------------------------------
def weaver(tmp_path, base, mode):
    srv = LoomServer([H.abs_row(H.select_task(BANK, base, mode))], str(tmp_path / "runs"), evidence="off")
    w = ScriptedWeaver(srv, "bank2/%s.%s" % (base, mode), "m", "%s.%s" % (base, mode))
    assert w.begin()["ok"]
    return srv, w


def score_of(tmp_path, srv, w):
    if srv.closed(w.run_id) is None:
        srv.harness(w.run_id, "abandoned", {"reason": "no_close"})
    return S.score_run(str(tmp_path / "runs" / w.run_id), BANK, GOLD)


def test_L_meta_the_model_looks_up_finds_nothing_and_abstains_before_any_weave_attempt(tmp_path):
    srv, w = weaver(tmp_path, "UF-015", "record_only")
    w.call("lookup", text="立案", tier="any")
    w.call("lookup", text="計画", tier="any")
    w.call("read_sentence", sid=142)
    assert w.call("abstain", type="no_record")["ok"]
    rs = score_of(tmp_path, srv, w)
    L = rs.layer
    assert rs.stop_layer == "L_meta" and rs.status == "abstained_correct" and L["stop_layer_detail"] == ""
    assert (L["lookups"], L["empty_lookups"], L["read_sentences"], L["reads"], L["weave_attempts"], L["emit_attempts"], L["refusals"]) == (2, 1, 1, 0, 0, 0, 0)
    assert L["build_attempts"] == 0 and L["struct_refusals"] == {}


def test_L_struct_the_loom_refuses_the_attempt_and_the_model_then_abstains(tmp_path):
    srv, w = weaver(tmp_path, "UF-015", "record_only")
    w.call("lookup", text="立案", tier="any")
    r1 = w.call("add", text="ウィリアム・ドノヴァン", kind="record", tier="WORD")                    # not a unit of the corpus
    r2 = w.call("add", text="将軍", kind="constructed")                                              # record_only forbids constructed units
    assert (r1["ok"], r1["refusal"]) == (False, "not_a_record") and (r2["ok"], r2["refusal"]) == (False, "constructed_forbidden")
    assert w.call("abstain", type="cannot_weave")["ok"]
    rs = score_of(tmp_path, srv, w)
    L = rs.layer
    assert rs.stop_layer == "L_struct" and rs.status == "abstained_correct" and L["stop_layer_detail"] == "then_abstained"
    assert L["struct_refusals"] == {"constructed_forbidden": 1, "not_a_record": 1} and L["struct_refusals_total"] == 2
    assert L["weave_attempts"] == 2 and L["refusals"] == 2 and L["lookups"] == 1 and L["empty_lookups"] == 1


def test_L_struct_also_when_the_run_ends_with_no_output_after_a_structural_refusal(tmp_path):
    srv, w = weaver(tmp_path, "UF-015", "record_only")
    assert w.call("add", text="ウィリアム・ドノヴァン", kind="record", tier="WORD")["refusal"] == "not_a_record"
    rs = score_of(tmp_path, srv, w)                                                                   # abandoned: neither emit nor abstain
    assert rs.status == "no_output" and rs.stop_layer == "L_struct" and rs.layer["stop_layer_detail"] == "then_no_output"


def test_a_cap_or_run_closed_refusal_is_not_a_structural_refusal(tmp_path):
    srv, w = weaver(tmp_path, "UF-015", "record_only")
    assert w.call("abstain", type="no_record")["ok"]
    late = w.call("add", text="計画", kind="record", tier="WORD")                                     # after the close
    assert late["refusal"] == "run_closed"
    rs = score_of(tmp_path, srv, w)
    assert rs.stop_layer == "L_meta" and rs.layer["struct_refusals_total"] == 0                       # rows after the closing row are not counted either


def test_L_none_marked_the_text_carries_a_constructed_unit(tmp_path):
    srv = LoomServer([H.abs_row(r) for r in DEMO.values()], str(tmp_path / "runs"), evidence="off")
    w = ScriptedWeaver(srv, "demo/tokyo_ca", "m", "tk_ca")
    res = weave_tokyo(w)
    assert res["ok"] and "です" in res["text"] and any(s["kind"] == "constructed" for s in res["annotated"])
    L = S.layer_report(rows(tmp_path / "runs" / "tk_ca"))
    assert L["stop_layer"] == "L_none_marked" and L["stop_layer_detail"] == "constructed_unit_in_text" and L["struct_refusals_total"] == 0
    assert L["emit_attempts"] == 1 and L["weave_attempts"] == 15


def test_L_none_the_text_is_record_only_and_a_refusal_before_the_emit_does_not_stop_it(tmp_path):
    srv = LoomServer([H.abs_row(r) for r in DEMO.values()], str(tmp_path / "runs"), evidence="off")
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "tk_ro")
    res = weave_tokyo(w)                                                                              # the add of です is refused, the rest is woven and emitted
    assert res["ok"] and "です" not in res["text"]
    L = S.layer_report(rows(tmp_path / "runs" / "tk_ro"))
    assert L["stop_layer"] == "L_none" and L["struct_refusals"] == {"constructed_forbidden": 1} and L["struct_refusals_before_emit"] == 1


def test_L_other_is_what_the_four_do_not_cover(tmp_path):
    srv, w = weaver(tmp_path, "UF-015", "record_only")                                                # built something, nothing refused, then abstained
    assert w.call("add", text="計画", kind="record", tier="WORD")["ok"]
    assert w.call("abstain", type="unknown")["ok"]
    rs = score_of(tmp_path, srv, w)
    assert rs.stop_layer == "L_other" and rs.layer["stop_layer_detail"] == "abstain_after_build" and rs.status == "abstained_correct"
    srv2, w2 = weaver(tmp_path / "b", "UF-015", "record_only")                                        # looked up and walked away
    w2.call("lookup", text="立案", tier="any")
    rs2 = score_of(tmp_path / "b", srv2, w2)
    assert rs2.stop_layer == "L_other" and rs2.layer["stop_layer_detail"] == "no_output_no_refusal" and rs2.status == "no_output"


def test_every_layer_is_in_LAYERS_and_an_unverified_run_has_none(tmp_path):
    assert S.LAYERS == ("L_meta", "L_struct", "L_none_marked", "L_none", "L_other")
    srv, w = weaver(tmp_path, "UF-015", "record_only")
    w.call("abstain", type="no_record")
    p = tmp_path / "runs" / w.run_id / "ops.jsonl"
    p.write_text(p.read_text(encoding="utf-8").replace('"lookups"', '"lookupz"', 1) + "x\n", encoding="utf-8")
    rs = S.score_run(str(tmp_path / "runs" / w.run_id), BANK, GOLD)
    assert rs.status == "run_not_verified" and rs.stop_layer is None and rs.layer is None


def test_the_layer_is_in_the_results_file_and_agrees_with_a_rescore_from_the_ledger(tmp_path):
    rs, path, obj = run_no_tools(tmp_path, "UF-006", AnswerClient("20メートル"))
    assert obj["score"]["stop_layer"] == "L_none" and obj["score"]["layer"]["control_outcome"] == "answered"
    again = S.score_run(str(tmp_path / "runs" / "UF-006.no_tools.api"), BANK, GOLD)
    assert again.layer == rs.layer and again.stop_layer == rs.stop_layer


# ------------------------------------------------------------------------------------------------------------
# a mechanical probe, NOT a model measurement: the four answers the no_tools control gave in runs_unans, offered to the loom as units
# ------------------------------------------------------------------------------------------------------------
NO_TOOLS_ANSWERS = {"UF-001": ["チェイン法", "オープンアドレス法", "チェイン法（連鎖法）と、オープンアドレス法（開番地法）"], "UF-009": ["1594年", "1594", "文禄3年"],
                    "UF-010": ["DGB大邱銀行パーク", "DGB"], "UF-011": ["9月"]}


def test_the_loom_refuses_every_add_of_a_no_tools_answer_in_record_only_and_marks_or_refuses_it_in_constructed_allowed(tmp_path):
    n = 0
    seen = {"record_only": Counter(), "constructed_allowed": Counter()}
    for base, texts in NO_TOOLS_ANSWERS.items():
        for mode in ("record_only", "constructed_allowed"):
            for text in texts:
                for kind in ("record", "constructed"):
                    n += 1
                    srv = LoomServer([H.abs_row(H.select_task(BANK, base, mode))], str(tmp_path / ("r%d" % n)), evidence="off")
                    w = ScriptedWeaver(srv, "bank2/%s.%s" % (base, mode), "m", "p")
                    w.begin()
                    r = w.call("add", text=text, kind=kind, tier="WORD")
                    seen[mode][(kind, r.get("refusal") or "accepted")] += 1
                    if kind == "record":
                        assert r["refusal"] == "not_a_record"                                         # none of them is a unit of the corpus
    assert dict(seen["record_only"]) == {("record", "not_a_record"): 9, ("constructed", "constructed_forbidden"): 9}
    assert dict(seen["constructed_allowed"]) == {("record", "not_a_record"): 9, ("constructed", "accepted"): 6, ("constructed", "bad_unit_text"): 3}


# ------------------------------------------------------------------------------------------------------------
# determinism
# ------------------------------------------------------------------------------------------------------------
def test_the_no_tools_run_and_its_layer_are_byte_identical_across_hash_seeds(tmp_path):
    script = ("import importlib.util,sys,json,types\n"
              "spec=importlib.util.spec_from_file_location('h',%r);H=importlib.util.module_from_spec(spec);sys.modules['h']=H;spec.loader.exec_module(H)\n"
              "S=H.score;bank=S.load_bank(%r);gold=S.load_gold()\n"
              "class C:\n"
              "    def __init__(s): s.messages=types.SimpleNamespace(create=s.c)\n"
              "    def c(s,**kw): return types.SimpleNamespace(content=[types.SimpleNamespace(type='text',text='年間約3万トン')],stop_reason='end_turn',model='fake',usage=None)\n"
              "rs,p,o=H.run(H.select_task(bank,'UF-002','no_tools'),'api',bank_path=%r,bank=bank,gold=gold,runs_dir=sys.argv[1]+'/runs',results_dir=sys.argv[1]+'/res',model='m',client=C())\n"
              "o.pop('wall',None);o.pop('ledger',None)\n"
              "print(json.dumps([rs.stop_layer,rs.layer,rs.status,open(sys.argv[1]+'/runs/UF-002.no_tools.api/HEAD').read()],ensure_ascii=False,sort_keys=True))\n"
              % (os.path.join(LOOM_X, "harness.py"), UNANS_BANK, UNANS_BANK))
    outs = []
    for seed in ("0", "1", "12345"):
        d = tmp_path / seed
        d.mkdir()
        r = subprocess.run([PY, "-c", script, str(d)], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT))
        assert r.returncode == 0, r.stderr[-800:]
        outs.append(r.stdout.strip().splitlines()[-1])
    assert len(set(outs)) == 1, outs

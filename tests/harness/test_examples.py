"""H6: the three examples do what their READMEs say (a fake model; the gate, the memory and the ledger are the real ones), and the Claude Code files are in step with the code."""
import json
import os
import re

import pytest

from fakes import FakeOpenAI
from verantyx.harness import runner as rn
from verantyx.harness.backends import make_backend

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EX = os.path.join(ROOT, "examples")
MANUALS = os.path.join(EX, "docs_qa", "manuals")


def oa(script):
    return make_backend("openai", "fake-gpt", client=FakeOpenAI(script))


def weave_turns(sid, word, tier="RUN"):
    return [[("tool", "read_sentence", {"sid": sid})], [("tool", "weave_span", {"sid": sid, "tier": tier, "first": word, "last": word})], [("tool", "emit", {})]]


def test_docs_qa_answers_two_questions_by_quotation(tmp_path):
    a = rn.ask("保守契約の窓口は何ですか", MANUALS, oa(weave_turns(1, "総務部")), str(tmp_path / "runs"))
    assert a.status == "answered" and a.text == "総務部" and a.sources[0]["text"] == "保守契約の窓口は総務部である。" and a.sources[0]["source"] == "保守契約#1"
    assert a.render().splitlines()[:2] == ["答え: 「総務部」", "根拠: 保守契約の窓口は総務部である。（保守契約#1）"]
    b = rn.ask("経費精算システムの旧称は何ですか", MANUALS, oa(weave_turns(8, "経理ナビ")), str(tmp_path / "runs"))
    assert b.status == "answered" and b.text == "経理ナビ"
    assert rn.verify_path(a.run_dir)["status"] == "OK"


def test_docs_qa_the_gate_refuses_a_quote_whose_sentence_does_not_state_the_item(tmp_path):
    a = rn.ask("夜間の障害受付の窓口は何ですか", MANUALS, oa(weave_turns(4, "別契約")), str(tmp_path / "runs"))
    assert a.status == "refused" and a.text is None and a.detail["last_refusal"] == "no_evidence/no_slot_head"


def test_memory_example_contested_and_a_readable_question(tmp_path):
    facts = open(os.path.join(EX, "memory", "facts.txt"), encoding="utf-8").read().split("\n")
    facts = [f for f in facts if f]
    assert facts == ["広報の担当は山本", "会議の場所は東京", "広報の担当は田中"] and all(len(f) <= 64 and "、" not in f for f in facts)
    story = [[("tool", "write", {"text": f}), ("tool", "report", {"contradictions": [["1-1", "1-3"]] if i == 2 else []})] for i, f in enumerate(facts)]
    store = str(tmp_path / "store")
    assert rn.mem_say(store, facts, oa(story)).committed
    c = rn.mem_ask(store, "広報の担当は何ですか", oa([[("tool", "recall", {"question": "広報の担当は何ですか"})], [("tool", "abstain", {"type": "contested"})]]))
    assert c.status == "refused" and c.reason == "contested" and sorted(c.detail["contested_values"]) == ["山本", "田中"]
    q = "会議の場所は何ですか"
    t = rn.mem_ask(store, q, oa([[("tool", "recall", {"question": q})], [("tool", "weave_span", {"sid": 1, "tier": "WORD", "first": "東京", "last": "東京"})], [("tool", "emit", {})]]))
    assert t.status == "answered" and t.text == "東京" and t.sources[0]["text"] == "会議の場所は東京"
    assert rn.verify_path(store)["status"] == "OK"


def test_the_claude_code_files_are_in_step_with_the_code():
    cc = os.path.join(EX, "claude_code")
    agent = open(os.path.join(cc, ".claude", "agents", "vera-weaver.md"), encoding="utf-8").read()
    fm = re.match(r"---\n(.*?)\n---\n\n(.*)", agent, re.S)
    tools = re.search(r"^tools: (.*)$", fm.group(1), re.M).group(1).split(", ")
    assert tools == ["mcp__vera-loom__" + t.name for t in rn.loom_tool_objects()] and len(tools) == 20 and not any(t in ("Bash", "Write", "WebFetch") for t in tools)
    from verantyx.harness import prompting
    assert fm.group(2).strip() == prompting.loom_prompt().strip()
    mem_agent = open(os.path.join(cc, ".claude", "agents", "vera-memory-writer.md"), encoding="utf-8").read()
    assert mem_agent.endswith(prompting.mem_story_prompt().rstrip("\n") + "\n") and "mcp__vera-mem__write" in mem_agent
    for f, server in ((".mcp.json", "vera-loom"), (".mcp.memory.json", "vera-mem")):
        cfg = json.load(open(os.path.join(cc, f), encoding="utf-8"))["mcpServers"][server]
        assert cfg["command"] == "vera" and cfg["args"][0] == "mcp"
    docs_args = json.load(open(os.path.join(cc, ".mcp.json"), encoding="utf-8"))["mcpServers"]["vera-loom"]["args"]
    assert docs_args[docs_args.index("--docs") + 1] == "examples/docs_qa/manuals"

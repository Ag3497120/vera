"""H2: the `vera` command line (ask, mem, mcp, verify, replay, eval, loom), through `cli.main` with fake backends."""
import io
import json
import os
import subprocess
import sys

import pytest

from fakes import ASK_TURNS, DOCS, QUESTION, FakeOpenAI
from verantyx.harness import cli
from verantyx.harness.backends import make_backend

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
CLEAN = [[b for b in t if b[0] != "text"] for t in ASK_TURNS]


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    return str(d)


@pytest.fixture()
def use(monkeypatch):
    """Hand the CLI a fake client: use(script) -> the FakeOpenAI that will serve it."""
    def go(script):
        fake = FakeOpenAI(script)
        monkeypatch.setattr(cli, "backend_factory", lambda kind, model, base_url, **kw: make_backend("openai", model or "fake-gpt", base_url, client=fake))
        return fake
    return go


def run(argv, capsys):
    rc = cli.main(argv)
    out = capsys.readouterr()
    return rc, out.out, out.err


def test_ask_prints_the_quote_its_source_and_the_run_directory(docs, tmp_path, use, capsys):
    use(CLEAN)
    rc, out, err = run(["ask", "--docs", docs, "--runs-dir", str(tmp_path / "runs"), "--backend", "openai", "--model", "m", QUESTION], capsys)
    lines = out.splitlines()
    assert rc == 0 and lines[0] == "答え: 「松風庵」" and lines[1].startswith("根拠: 青葉堂の旧称は松風庵。（青葉堂#1）") and lines[2].startswith("run: " + str(tmp_path / "runs"))
    assert err == ""


def test_ask_reads_a_single_file_as_the_documents(docs, tmp_path, use, capsys):
    use(CLEAN)
    rc, out, _ = run(["ask", "--docs", os.path.join(docs, "青葉堂.txt"), "--runs-dir", str(tmp_path / "r"), QUESTION], capsys)
    assert rc == 0 and "松風庵" in out


def test_ask_refusal_exits_1_and_says_why(docs, tmp_path, use, capsys):
    use([[("tool", "abstain", {"type": "no_record"})]])
    rc, out, _ = run(["ask", "--docs", docs, "--runs-dir", str(tmp_path / "r"), "--backend", "openai", "--model", "m", "青葉堂の社長は誰ですか"], capsys)
    assert rc == 1 and out.startswith("分かりません（理由: no_record、") and "run: " in out


def test_ask_json_output_is_one_object(docs, tmp_path, use, capsys):
    use(CLEAN)
    rc, out, _ = run(["ask", "--json", "--docs", docs, "--runs-dir", str(tmp_path / "r"), "--model", "m", "--backend", "openai", QUESTION], capsys)
    o = json.loads(out)
    assert rc == 0 and o["status"] == "answered" and o["text"] == "松風庵" and o["verified"] is True and o["backend"]["backend"] == "openai"


def test_ask_errors_exit_2_with_a_typed_code_on_stderr(tmp_path, use, capsys):
    use([])
    rc, out, err = run(["ask", "--docs", str(tmp_path / "missing"), "--runs-dir", str(tmp_path / "r"), "--model", "m", "--backend", "openai", "質問"], capsys)
    assert rc == 2 and out == "" and err.startswith("vera: docs_missing:")


def test_backend_errors_exit_2_and_never_print_a_key(docs, tmp_path, monkeypatch, capsys):
    from verantyx.harness import keys
    monkeypatch.setattr(cli, "backend_factory", cli.make_backend)
    monkeypatch.setattr(keys, "_keychain", lambda s, a: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "anthropic", type(sys)("anthropic"))
    sys.modules["anthropic"].Anthropic = lambda **kw: None
    rc, out, err = run(["ask", "--docs", docs, "--runs-dir", str(tmp_path / "r"), "質問"], capsys)
    assert rc == 2 and "no_api_key" in err


def test_verify_and_replay_commands(docs, tmp_path, use, capsys):
    use(CLEAN)
    run(["ask", "--docs", docs, "--runs-dir", str(tmp_path / "runs"), "--model", "m", "--backend", "openai", QUESTION], capsys)
    d = [os.path.join(tmp_path, "runs", x) for x in os.listdir(tmp_path / "runs") if x.startswith("ask-")][0]
    rc, out, _ = run(["verify", d], capsys)
    assert rc == 0 and out.startswith("OK loom rows=7")
    rc, out, _ = run(["replay", d], capsys)
    assert rc == 0 and out.startswith("REPLAY_IDENTICAL loom") and "text: 松風庵" in out
    rc, out, _ = run(["verify", "--json", d], capsys)
    assert json.loads(out)["status"] == "OK"
    with open(os.path.join(d, "ops.jsonl"), "r+", encoding="utf-8") as f:
        t = f.read()
        f.seek(0)
        f.write(t.replace("松風庵", "松風菴", 1))
    rc, out, err = run(["verify", d], capsys)
    assert rc == 1 and out.startswith("TAMPERED")
    rc, out, err = run(["verify", str(tmp_path)], capsys)
    assert rc == 1 and out.startswith("NOT_A_RUN")


def test_eval_is_a_stub_until_h5(capsys):
    rc, out, err = run(["eval"], capsys)
    assert rc == 3 and "H5" in err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and capsys.readouterr().out.startswith("vera-harness 0.1.0")


def test_mem_with_flags_keeps_facts_then_answers(tmp_path, use, capsys):
    store = str(tmp_path / "store")
    use([[("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})],
         [("tool", "recall", {"question": "広報の担当は何ですか"})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "山本", "last": "山本"})], [("tool", "emit", {})]])
    rc, out, _ = run(["mem", "--store", store, "--backend", "openai", "--model", "m", "--say", "広報の担当は山本", "--ask", "広報の担当は何ですか"], capsys)
    assert rc == 0 and "記憶: 1 件を session 1 に渡しました（保存" in out and "答え: 「山本」" in out and "根拠: 広報の担当は山本" in out and out.rstrip().endswith("store: " + store)
    rc, out, _ = run(["verify", store], capsys)
    assert rc == 0 and out.startswith("OK mem_store")


def test_mem_interactive_flushes_pending_facts_before_a_question(tmp_path, use, capsys, monkeypatch):
    store = str(tmp_path / "store")
    use([[("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})],
         [("tool", "recall", {"question": "経理の担当は何ですか"})], [("tool", "abstain", {"type": "no_record"})]])
    monkeypatch.setattr(sys, "stdin", io.StringIO("広報の担当は山本\n\n? 経理の担当は何ですか\n"))
    rc, out, err = run(["mem", "--store", store, "--backend", "openai", "--model", "m"], capsys)
    assert rc == 1 and "session 1" in out and out.count("分かりません") == 1 and "no_record" in out
    assert "1 回に事実を 1 つ" in err


def test_mem_contested_is_said_with_both_values(tmp_path, use, capsys):
    store = str(tmp_path / "store")
    use([[("tool", "write", {"text": "広報の担当は山本"}), ("tool", "report", {"contradictions": []})],
         [("tool", "write", {"text": "広報の担当は田中"}), ("tool", "report", {"contradictions": [["1-1", "1-2"]]})],
         [("tool", "recall", {"question": "広報の担当は何ですか"})], [("tool", "abstain", {"type": "contested"})]])
    rc, out, _ = run(["mem", "--store", store, "--backend", "openai", "--model", "m", "--say", "広報の担当は山本", "--say", "広報の担当は田中", "--ask", "広報の担当は何ですか"], capsys)
    assert rc == 1 and "理由: contested" in out and "「山本」" in out and "「田中」" in out


def test_mcp_without_a_source_is_a_usage_error(capsys):
    rc, out, err = run(["mcp"], capsys)
    assert rc == 2 and "bad_usage" in err
    rc, out, err = run(["mcp", "--mode", "memory"], capsys)
    assert rc == 2 and "no_store" in err


def test_mcp_docs_writes_the_corpus_and_a_task_bank_with_one_task_per_question(docs, tmp_path):
    from verantyx.harness import mcp_server as ms
    tasks = ms.prepare_doc_tasks(docs, [QUESTION, "青葉堂の店主は誰ですか"], str(tmp_path / "runs"))
    rows = [json.loads(ln) for ln in open(tasks, encoding="utf-8")]
    assert [r["task_id"] for r in rows] == ["q1", "q2"] and all(r["mode"] == "record_only" and os.path.isfile(r["corpus"]) for r in rows)
    from verantyx.loom.mcp import LoomServer
    assert LoomServer.from_file(tasks, str(tmp_path / "runs")).evidence_profile[0] == "evidence.v6"
    with pytest.raises(Exception):
        ms.prepare_doc_tasks(docs, [" "], str(tmp_path / "runs"))


def test_the_mcp_server_over_stdio_serves_exactly_the_loom_and_leaves_a_verifiable_ledger(docs, tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from verantyx.loom import ledger as lg
    runs = tmp_path / "mcp_runs"
    params = StdioServerParameters(command=PY, args=["-m", "verantyx.harness.cli", "mcp", "--docs", docs, "--question", QUESTION, "--runs-dir", str(runs)],
                                   env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT)

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = sorted(t.name for t in (await s.list_tools()).tools)
                b = json.loads((await s.call_tool("begin", {"task_id": "q1", "model": "mcp-test"})).content[0].text)
                rid = b["run_id"]
                await s.call_tool("weave_span", {"run_id": rid, "sid": 1, "tier": "RUN", "first": "松風庵", "last": "松風庵"})
                e = json.loads((await s.call_tool("emit", {"run_id": rid})).content[0].text)
                return names, rid, e
    import asyncio
    names, rid, e = asyncio.run(go())
    assert len(names) == 20 and "emit" in names and "say" not in names
    assert e["ok"] is True and e["text"] == "松風庵"
    corpus = [os.path.join(runs, "_corpora", f) for f in os.listdir(runs / "_corpora")][0]
    assert lg.verify(str(runs / rid), corpus_path=corpus)["status"] == "OK"


def test_loom_demo_through_the_harness_cli_is_the_worked_example(tmp_path):
    corpus = os.path.join(ROOT, "tests/fixtures/line3/bank2/data/fulllead_sents.jsonl")
    p = subprocess.run([PY, "-m", "verantyx.harness.cli", "loom", "demo", "--corpus", corpus, "--runs-dir", str(tmp_path / "runs")],
                       env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0 and "verify:    OK" in p.stdout


def test_the_memory_mcp_server_commits_the_session_when_the_client_closes(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from verantyx.loom import memory as mem
    store = tmp_path / "mcp_store"
    params = StdioServerParameters(command=PY, args=["-m", "verantyx.harness.cli", "mcp", "--mode", "memory", "--store", str(store), "--model", "mcp-test"],
                                   env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT)

    async def go():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = sorted(t.name for t in (await s.list_tools()).tools)
                w1 = json.loads((await s.call_tool("write", {"text": "広報の担当は山本"})).content[0].text)
                rp = json.loads((await s.call_tool("report", {"contradictions": [], "turn": "1-1"})).content[0].text)
                return names, w1, rp
    import asyncio
    names, w1, rp = asyncio.run(go())
    assert {"write", "recall", "report", "keep_unshaped", "bridge", "supersede"} <= set(names) and "emit" not in names and "answer" not in names
    assert w1.get("ok") is True and rp.get("ok") is True
    head = mem.MemStore(str(store)).head()
    assert head is not None and len(head["sessions"]) == 1 and head["sentences"] == 1

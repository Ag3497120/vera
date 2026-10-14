"""H1: the three backends (anthropic, openai-compatible, json ops), with fake clients only: no network, no SDK call, no key."""
import json
import os
import sys
from types import SimpleNamespace

import pytest

from fakes import ASK_TURNS, DOCS, QUESTION, FakeChatText, FakeOpenAI
from verantyx.harness import keys
from verantyx.harness import runner as rn
from verantyx.harness.backends import BACKENDS, Backend, BackendError, DriverClient, make_backend
from verantyx.harness.backends import json_ops as jo
from verantyx.harness.backends import openai_compat as oc
from verantyx.loom import driver as drv
from verantyx.loom.driver import ReplayClient


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for k, v in DOCS.items():
        (d / k).write_text(v, encoding="utf-8")
    return str(d)


def ops_of(run_dir):
    with open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def model_ops(run_dir):
    """(actor, op, args) of every row except `begin` (it names the model) and the free-text rows (their shas depend on what the model said, which differs by backend)."""
    return [(r["actor"], r["op"], r["args"]) for r in ops_of(run_dir) if r["op"] not in ("free_text_dropped", "harness_meta", "begin")]


# -- the registry ---------------------------------------------------------------------------------------------------------------
def test_the_registry_names_three_backends():
    assert BACKENDS == ("anthropic", "openai", "json")


def test_make_backend_refuses_with_typed_codes():
    for args, code in ((("nope", "m"), "bad_backend"), (("openai", None), "no_model"), (("json", None), "no_model"), (("openai", "m", "ftp://x"), "bad_base_url")):
        with pytest.raises(BackendError) as e:
            make_backend(*args)
        assert e.value.code == code


def test_every_backend_satisfies_the_protocol_and_describes_itself_without_a_key():
    bs = [make_backend("anthropic", client=ReplayClient([])), make_backend("openai", "m", "http://127.0.0.1:11434/v1", client=FakeOpenAI([])), make_backend("json", "m", client=FakeChatText([]))]
    for b in bs:
        assert isinstance(b, Backend)
        d = b.describe()
        assert d["backend"] == b.name and d["model"] == b.model and "key" not in json.dumps(d).lower()
    assert bs[1].describe()["base_url"] == "http://127.0.0.1:11434/v1"
    assert make_backend("anthropic").model == "claude-haiku-5-5"


# -- anthropic ------------------------------------------------------------------------------------------------------------------
def test_anthropic_forces_tool_use_except_for_the_ids_that_reject_it():
    assert make_backend("anthropic", "claude-haiku-5-5", client=ReplayClient([])).tool_choice() == ({"type": "any"}, False)
    assert make_backend("anthropic", "claude-sonnet-5-5", client=ReplayClient([])).tool_choice() == ({"type": "auto"}, True)
    assert make_backend("anthropic", "claude-haiku-5-5", tool_choice="auto", client=ReplayClient([])).tool_choice() == ({"type": "auto"}, False)


def test_anthropic_sends_the_history_and_returns_the_api_blocks_unchanged():
    rc = ReplayClient([[("text", "hmm"), ("thinking", "t"), ("tool", "status", {})]])
    b = make_backend("anthropic", "claude-haiku-5-5", client=rc)
    msgs = [{"role": "user", "content": "q"}]
    t = b.send(system="S", messages=msgs, tools=[{"name": "status", "description": "d", "input_schema": {"type": "object"}}], max_tokens=50, tool_choice={"type": "any"})
    assert [x.type for x in t.content] == ["text", "thinking", "tool_use"] and [c.name for c in t.tool_calls] == ["status"]
    assert rc.calls[0]["tool_choice"] == {"type": "any"} and rc.calls[0]["system"] == "S" and rc.calls[0]["max_tokens"] == 50 and rc.calls[0]["model"] == "claude-haiku-5-5"


def test_anthropic_client_gets_the_key_from_the_environment_and_never_describes_it(monkeypatch):
    seen = {}
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kw: seen.update(kw) or SimpleNamespace(messages=None)))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TESTSECRET-0001")
    b = make_backend("anthropic", "claude-haiku-5-5")
    b.client()
    assert seen["api_key"] == "sk-ant-TESTSECRET-0001" and b.key_source == "environment"
    assert "TESTSECRET" not in json.dumps(b.describe())


def test_anthropic_without_the_sdk_or_a_key_is_a_typed_refusal(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(BackendError) as e:
        make_backend("anthropic", "m").client()
    assert e.value.code == "sdk_missing"
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kw: None))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(keys, "_keychain", lambda s, a: None)
    with pytest.raises(BackendError) as e:
        make_backend("anthropic", "m").client()
    assert e.value.code == "no_api_key"


# -- openai-compatible ----------------------------------------------------------------------------------------------------------
def test_openai_tools_and_choice_mapping():
    tools = [{"name": "lookup", "description": "d", "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}}}]
    assert oc.to_openai_tools(tools) == [{"type": "function", "function": {"name": "lookup", "description": "d", "parameters": tools[0]["input_schema"]}}]
    assert oc.to_openai_choice({"type": "any"}, True) == "required"
    assert oc.to_openai_choice({"type": "any"}, False) == "auto"
    assert oc.to_openai_choice({"type": "auto"}, True) == "auto"
    assert oc.to_openai_choice({"type": "tool", "name": "report"}, True) == {"type": "function", "function": {"name": "report"}}
    assert make_backend("openai", "m", tool_choice="auto", client=FakeOpenAI([])).tool_choice() == ({"type": "auto"}, False)


def test_openai_history_conversion_keeps_calls_and_results_paired():
    msgs = [{"role": "user", "content": "go"},
            {"role": "assistant", "content": [SimpleNamespace(type="thinking", thinking="x", signature=""), SimpleNamespace(type="text", text="hm"),
                                              SimpleNamespace(type="tool_use", id="c1", name="lookup", input={"text": "松風庵", "tier": "any"})]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{\"ok\": true}"}]}]
    out = oc.to_openai_messages("SYS", msgs)
    assert out[0] == {"role": "system", "content": "SYS"} and out[1] == {"role": "user", "content": "go"}
    a = out[2]
    assert a["role"] == "assistant" and a["content"] == "hm" and a["tool_calls"][0]["id"] == "c1"
    assert json.loads(a["tool_calls"][0]["function"]["arguments"]) == {"text": "松風庵", "tier": "any"}      # thinking is not sent back
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "{\"ok\": true}"}


def test_openai_turn_reading_text_reasoning_calls_and_garbage_arguments():
    msg = SimpleNamespace(content="prose", reasoning_content="deep thought",
                          tool_calls=[SimpleNamespace(id="a", function=SimpleNamespace(name="status", arguments="{}")),
                                      SimpleNamespace(id="b", function=SimpleNamespace(name="lookup", arguments="{not json")),
                                      SimpleNamespace(id="c", function=SimpleNamespace(name="read_sentence", arguments="[1]"))])
    t = oc.turn_from_message(msg, {"input_tokens": 3}, "m", "tool_calls")
    kinds = [b.type for b in t.content]
    assert kinds == ["thinking", "text", "tool_use", "text", "text"]                        # only the well-formed call is a tool_use; the two bad ones are dropped text
    assert [c.name for c in t.tool_calls] == ["status"] and t.content[3].text == "{not json" and t.stop_reason == "tool_use"


def test_openai_request_is_forced_and_carries_the_conversation():
    fake = FakeOpenAI([[("tool", "status", {})]])
    b = make_backend("openai", "deepseek-chat", "https://api.deepseek.com", client=fake)
    tools = [{"name": "status", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    t = b.send(system="S", messages=[{"role": "user", "content": "hi"}], tools=tools, max_tokens=77, tool_choice={"type": "any"})
    kw = fake.calls[0]
    assert kw["model"] == "deepseek-chat" and kw["tool_choice"] == "required" and kw["max_tokens"] == 77 and kw["messages"][0]["role"] == "system"
    assert t.usage == {"input_tokens": 11, "output_tokens": 7} and t.model == "fake-gpt"


def test_openai_local_server_needs_no_key_and_a_remote_one_does(monkeypatch):
    seen = {}
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kw: seen.update(kw) or SimpleNamespace()))
    for n in ("VERA_OPENAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr(keys, "_keychain", lambda s, a: None)
    b = make_backend("openai", "llama3", "http://127.0.0.1:11434/v1")
    b.client()
    assert seen["base_url"] == "http://127.0.0.1:11434/v1" and seen["api_key"] == keys.LOCAL_PLACEHOLDER
    with pytest.raises(BackendError) as e:
        make_backend("openai", "gpt").client()
    assert e.value.code == "no_api_key"


def test_the_vera_specific_key_variable_wins_over_the_generic_one(monkeypatch):
    monkeypatch.setattr(keys, "_keychain", lambda s, a: None)
    monkeypatch.setenv("OPENAI_API_KEY", "generic-key-111111")
    monkeypatch.setenv("VERA_OPENAI_API_KEY", "vera-key-222222")
    assert keys.resolve_api_key("openai") == "vera-key-222222"
    monkeypatch.setenv("MY_KEY_VAR", "mine-333333")
    assert keys.resolve_api_key("openai", "MY_KEY_VAR") == "mine-333333"
    assert "vera-key-222222" not in keys.redact("error with vera-key-222222 inside") and "[redacted]" in keys.redact("x mine-333333 y")


# -- json ops -------------------------------------------------------------------------------------------------------------------
NAMES = ["lookup", "read_sentence", "emit", "done"]


def test_parse_ops_accepts_exactly_an_array_of_valid_ops():
    ops, dropped, think = jo.parse_ops('[{"tool": "lookup", "input": {"text": "a", "tier": "any"}}, {"tool": "emit", "input": {}}]', NAMES)
    assert ops == [("lookup", {"text": "a", "tier": "any"}), ("emit", {})] and dropped == [] and think == []


@pytest.mark.parametrize("text", ["I think the answer is 松風庵", '{"tool": "emit", "input": {}}', "[1, 2", '[] trailing', 'Sure! [{"tool": "emit", "input": {}}]', '```json\n[{"tool": "emit", "input": {}}]\n``` and prose'])
def test_parse_ops_drops_everything_that_is_not_an_array_and_records_it(text):
    ops, dropped, _ = jo.parse_ops(text, NAMES)
    assert ops == [] and dropped == [text.strip()]


def test_parse_ops_drops_invalid_elements_and_keeps_the_valid_ones():
    arr = [{"tool": "lookup", "input": {"text": "a", "tier": "any"}}, {"tool": "rm_rf", "input": {}}, {"tool": "emit"}, {"tool": "emit", "input": [1]}, {"tool": "emit", "input": {}, "extra": 1}, "emit", 3,
           {"tool": "emit", "input": {}}]
    ops, dropped, _ = jo.parse_ops(json.dumps(arr), NAMES)
    assert [o[0] for o in ops] == ["lookup", "emit"] and len(dropped) == 6


def test_parse_ops_unwraps_one_whole_fence_and_reads_a_leading_think_as_reasoning():
    ops, dropped, think = jo.parse_ops('<think>hmm</think>\n```json\n[{"tool": "emit", "input": {}}]\n```', NAMES)
    assert ops == [("emit", {})] and dropped == [] and think == ["hmm"]


def test_parse_ops_caps_the_ops_of_one_turn():
    ops, dropped, _ = jo.parse_ops(json.dumps([{"tool": "emit", "input": {}}] * (jo.MAX_OPS_PER_TURN + 3)), NAMES)
    assert len(ops) == jo.MAX_OPS_PER_TURN and len(dropped) == 3


def test_json_ops_never_sends_tools_and_describes_them_in_the_system_prompt():
    fake = FakeChatText(['[{"tool": "status", "input": {}}]'])
    b = make_backend("json", "tiny-local", "http://127.0.0.1:1234/v1", client=fake)
    tools = [{"name": "status", "description": "The state.", "input_schema": {"type": "object", "properties": {}}}]
    t = b.send(system="SYS", messages=[{"role": "user", "content": "go"}], tools=tools, max_tokens=64, tool_choice={"type": "any"})
    sysmsg = fake.calls[0]["messages"][0]["content"]
    assert sysmsg.startswith("SYS") and "- status: The state." in sysmsg and "JSON array" in sysmsg
    assert [c.name for c in t.tool_calls] == ["status"] and t.tool_calls[0].id.startswith("op_")


def test_json_ops_history_returns_results_as_one_user_message():
    msgs = [{"role": "user", "content": "go"},
            {"role": "assistant", "content": [SimpleNamespace(type="tool_use", id="op_1_0", name="lookup", input={"text": "a", "tier": "any"})]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "op_1_0", "content": "{\"ok\": true, \"n\": 1}"}]}]
    out = jo.to_chat_messages("S", msgs)
    assert out[2] == {"role": "assistant", "content": '[{"input": {"text": "a", "tier": "any"}, "tool": "lookup"}]'}
    assert out[3]["role"] == "user" and '"tool": "lookup"' in out[3]["content"] and '"n": 1' in out[3]["content"]


# -- through the loom: the same loom, the same ledger -----------------------------------------------------------------------------
def json_replies():
    return [json.dumps([{"tool": "lookup", "input": {"text": "松風庵", "tier": "any"}}, {"tool": "read_sentence", "input": {"sid": 1}}], ensure_ascii=False),
            json.dumps([{"tool": "weave_span", "input": {"sid": 1, "tier": "RUN", "first": "松風庵", "last": "松風庵"}}, {"tool": "emit", "input": {}}], ensure_ascii=False)]


def ask_with(kind, docs, tmp_path, script=None, replies=None):
    if kind == "anthropic":
        b = make_backend("anthropic", "claude-haiku-5-5", client=ReplayClient(script or [[b for b in t if b[0] != "text"] for t in ASK_TURNS]))
    elif kind == "openai":
        b = make_backend("openai", "fake-gpt", client=FakeOpenAI(script or [[b for b in t if b[0] != "text"] for t in ASK_TURNS]))
    else:
        b = make_backend("json", "fake-local", client=FakeChatText(replies or json_replies()))
    return rn.ask(QUESTION, docs, b, str(tmp_path / ("runs_" + kind)))


@pytest.mark.parametrize("kind", ["anthropic", "openai", "json"])
def test_each_backend_answers_through_the_same_loom(kind, docs, tmp_path):
    a = ask_with(kind, docs, tmp_path)
    assert a.status == "answered" and a.text == "松風庵" and a.verified
    assert a.sources == [{"sid": 1, "source": "青葉堂#1", "text": "青葉堂の旧称は松風庵。", "clause": "青葉堂の旧称は松風庵"}]
    assert rn.verify_path(a.run_dir)["status"] == "OK" and rn.replay_path(a.run_dir)["status"] == "IDENTICAL"


def test_the_three_backends_leave_the_same_operations_in_the_ledger(docs, tmp_path):
    """The model-facing operations (the rows of actor `model`) are identical across backends when the models make the same calls: one loom, one ledger."""
    ledgers = {}
    for kind in ("anthropic", "openai"):
        ledgers[kind] = [(a, o, ar) for a, o, ar in model_ops(ask_with(kind, docs, tmp_path).run_dir) if a == "model"]
    # the JSON model batches lookup + read in one turn: the same ops in the same order
    j = [(a, o, ar) for a, o, ar in model_ops(ask_with("json", docs, tmp_path).run_dir) if a == "model"]
    assert ledgers["anthropic"] == ledgers["openai"] == j


@pytest.mark.parametrize("kind", ["anthropic", "openai", "json"])
def test_free_text_never_reaches_the_user_and_only_its_hash_is_recorded(kind, docs, tmp_path):
    """The model states a wrong answer in prose before and after it quotes the right one.  The user sees the quote of the documents, nothing of the prose."""
    prose1, prose2 = "答えは山田さんです。絶対に山田です。", "やはり答えは1820年です。"
    if kind == "json":
        replies = [prose1, json_replies()[0], prose2 + json_replies()[1], json_replies()[1]]      # prose around an array drops the WHOLE reply: the next reply is the clean one
        a = ask_with(kind, docs, tmp_path, replies=replies)
    else:
        script = [[("text", prose1), ("tool", "lookup", {"text": "松風庵", "tier": "any"})], [("tool", "read_sentence", {"sid": 1})],
                  [("text", prose2), ("tool", "weave_span", {"sid": 1, "tier": "RUN", "first": "松風庵", "last": "松風庵"})], [("tool", "emit", {})]]
        a = ask_with(kind, docs, tmp_path, script=script)
    shown = a.render() + json.dumps(a.to_obj(), ensure_ascii=False)
    assert a.status == "answered" and a.text == "松風庵" and "山田" not in shown and "1820" not in shown
    ledger = open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8").read()
    assert "山田さんです" not in ledger and "やはり答え" not in ledger
    dropped = [r for r in ops_of(a.run_dir) if r["op"] == "free_text_dropped"]
    assert a.free_text_dropped == len(dropped) >= 2 and all(len(r["args"]["sha256"]) == 64 for r in dropped)
    import hashlib
    assert hashlib.sha256(prose1.encode()).hexdigest() in {r["args"]["sha256"] for r in dropped}


@pytest.mark.parametrize("kind", ["anthropic", "openai", "json"])
def test_a_model_that_only_talks_is_refused_with_a_typed_reason_and_prints_none_of_it(kind, docs, tmp_path):
    talk = "松風庵です。間違いありません。"
    if kind == "json":
        a = ask_with(kind, docs, tmp_path, replies=[talk] * 3)
    else:
        a = ask_with(kind, docs, tmp_path, script=[[("text", talk)]] * 3)
    assert a.status == "refused" and a.reason == "no_tool_call" and a.text is None and a.verified
    assert "松風庵です" not in a.render() and a.render().startswith("分かりません（理由: no_tool_call")
    assert a.free_text_dropped == 3


def test_openai_garbage_arguments_never_reach_the_loom(docs, tmp_path):
    script = [[("rawtool", "lookup", "{broken")], [("rawtool", "lookup", "{broken")], [("rawtool", "lookup", "{broken")]]
    a = ask_with("openai", docs, tmp_path, script=script)
    assert a.reason == "no_tool_call"
    assert not [r for r in ops_of(a.run_dir) if r["actor"] == "model" and r["op"] != "begin"]


def test_json_ops_drops_an_invalid_op_but_runs_the_valid_ones_in_the_same_array(docs, tmp_path):
    first = json.dumps([{"tool": "lookup", "input": {"text": "松風庵", "tier": "any"}}, {"tool": "format_disk", "input": {}}, {"tool": "read_sentence", "input": {"sid": 1}}], ensure_ascii=False)
    a = ask_with("json", docs, tmp_path, replies=[first, json_replies()[1]])
    assert a.status == "answered"
    model_rows = [r["op"] for r in ops_of(a.run_dir) if r["actor"] == "model"]
    assert model_rows == ["begin", "lookup", "read_sentence", "weave_span", "emit"] and "format_disk" not in open(os.path.join(a.run_dir, "ops.jsonl"), encoding="utf-8").read()
    assert a.free_text_dropped == 1                                              # the invalid op was recorded as a dropped part


def test_a_transport_error_is_an_abandoned_run_and_never_echoes_the_key(docs, tmp_path, monkeypatch):
    monkeypatch.setenv("VERA_OPENAI_API_KEY", "sk-LEAKME-123456789")
    keys.resolve_api_key("openai")

    class Boom:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kw):
            raise RuntimeError("401 Unauthorized: bad key sk-LEAKME-123456789")

    a = rn.ask(QUESTION, docs, make_backend("openai", "gpt", client=Boom()), str(tmp_path / "runs"))
    assert a.status == "refused" and a.reason == "api_error" and a.verified
    blob = a.render() + json.dumps(a.to_obj(), ensure_ascii=False)
    for dp, dn, fn in os.walk(str(tmp_path)):
        for f in fn:
            blob += open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
    assert "LEAKME" not in blob


def test_the_driver_client_forwards_extra_keywords_and_counts_calls():
    fake = FakeOpenAI([[("tool", "status", {})]])
    c = DriverClient(make_backend("openai", "m", client=fake))
    r = c.messages.create(model="m", max_tokens=9, system="S", tools=[{"name": "status", "description": "", "input_schema": {"type": "object"}}], tool_choice={"type": "any"},
                          messages=[{"role": "user", "content": "x"}], seed=7)
    assert fake.calls[0]["seed"] == 7 and c.calls == 1 and r.content[0].type == "tool_use"

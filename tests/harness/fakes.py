"""Fake SDK clients for the harness tests: no network, no SDK, no key.  A script is a list of turns; a turn is a list of blocks:
("text", s) | ("think", s) | ("tool", name, input_dict) | ("rawtool", name, raw_arguments_string).  Every request is recorded in `.calls`."""
import json
from types import SimpleNamespace


class FakeOpenAI:
    """`client.chat.completions.create(**kw)` returning Chat Completions objects."""

    def __init__(self, script, model="fake-gpt", usage=(11, 7)):
        self.script = [list(t) for t in script]
        self.calls = []
        self.model = model
        self.usage = usage
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._n = 0

    def _create(self, **kw):
        self.calls.append(json.loads(json.dumps(kw, default=str)))
        assert self._n < len(self.script), "the script is exhausted"
        turn = self.script[self._n]
        self._n += 1
        text = "\n".join(b[1] for b in turn if b[0] == "text") or None
        reasoning = "\n".join(b[1] for b in turn if b[0] == "think") or None
        calls = []
        for k, b in enumerate(x for x in turn if x[0] in ("tool", "rawtool")):
            raw = json.dumps(b[2], ensure_ascii=False) if b[0] == "tool" else b[2]
            calls.append(SimpleNamespace(id="call_%d_%d" % (self._n, k), type="function", function=SimpleNamespace(name=b[1], arguments=raw)))
        msg = SimpleNamespace(content=text, tool_calls=calls or None, reasoning_content=reasoning)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="tool_calls" if calls else "stop")], model=self.model,
                               usage=SimpleNamespace(prompt_tokens=self.usage[0], completion_tokens=self.usage[1]))


class FakeChatText:
    """An OpenAI-compatible endpoint for the JSON-ops backend: every turn is the plain text the model replied (a string)."""

    def __init__(self, replies, model="fake-local"):
        self.replies = list(replies)
        self.calls = []
        self.model = model
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._n = 0

    def _create(self, **kw):
        self.calls.append(json.loads(json.dumps(kw, default=str)))
        assert "tools" not in kw and "tool_choice" not in kw, "the JSON-ops backend must not send tools"
        assert self._n < len(self.replies), "the replies are exhausted"
        text = self.replies[self._n]
        self._n += 1
        msg = SimpleNamespace(content=text, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")], model=self.model, usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3))


DOCS = {"青葉堂.txt": "青葉堂は、東京都にある小さな書店である。\n青葉堂の旧称は松風庵。\n店主は山田さんである。\n青葉堂は1820年に建てられた。\n"}

ASK_TURNS = [
    [("text", "考えます。答えは松風庵だと思います。"), ("tool", "lookup", {"text": "松風庵", "tier": "any"})],
    [("tool", "read_sentence", {"sid": 1})],
    [("tool", "weave_span", {"sid": 1, "tier": "RUN", "first": "松風庵", "last": "松風庵"})],
    [("text", "emit します。"), ("tool", "emit", {})],
]
QUESTION = "青葉堂の旧称は何ですか"

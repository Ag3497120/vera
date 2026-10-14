"""The OpenAI-compatible backend: any server that speaks Chat Completions with tool calling (OpenAI, DeepSeek, Ollama, LM Studio, vLLM, MLX servers).

  --backend openai --model M [--base-url http://127.0.0.1:11434/v1]

Tool calling is FORCED (`tool_choice: "required"`; `--tool-choice auto` for a server that rejects it).  What the model returns is read as follows:

  * a tool call whose arguments are a JSON object  -> a `tool_use` block (the only thing that reaches the loom);
  * a tool call whose arguments are not a JSON object -> NOT forwarded: its raw text becomes a `text` block (dropped by the driver, sha recorded);
  * the message text (`content`)                      -> a `text` block (dropped, sha recorded);
  * `reasoning_content` / `reasoning` (DeepSeek, Ollama)  -> a `thinking` block (counted by hash and length, dropped).

The `openai` SDK is imported here, lazily.  A test (or an embedder) may hand in any object with `chat.completions.create(**kw)`.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from verantyx.harness import keys
from verantyx.harness.backends.base import BackendError, Turn, api_forced_choice, get, jdump, text_block, thinking_block, tool_block


def to_openai_tools(tools: Sequence[dict]) -> List[dict]:
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema") or {"type": "object", "properties": {}}}}
            for t in tools]


def to_openai_choice(tool_choice: Optional[dict], forced: bool) -> Any:
    if tool_choice is None or not forced:
        return "auto"
    t = tool_choice.get("type")
    if t == "any":
        return "required"
    if t == "tool" and tool_choice.get("name"):
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    return "auto"


def to_openai_messages(system: str, messages: Sequence[dict]) -> List[dict]:
    """The driver's Anthropic-shaped history as Chat Completions messages.  Tool results become `tool` messages; the assistant's own blocks are sent back as they
    were (text as `content`, tool_use as `tool_calls`); thinking blocks are not sent back."""
    out: List[dict] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        role, content = m["role"], m["content"]
        if role == "user":
            if isinstance(content, str):
                out.append({"role": "user", "content": content})
                continue
            texts: List[str] = []
            for b in content:
                if get(b, "type") == "tool_result":
                    c = get(b, "content")
                    out.append({"role": "tool", "tool_call_id": get(b, "tool_use_id"), "content": c if isinstance(c, str) else jdump(c)})
                elif get(b, "type") == "text":
                    texts.append(get(b, "text", ""))
            if texts:
                out.append({"role": "user", "content": "\n".join(texts)})
        else:
            if isinstance(content, str):
                out.append({"role": "assistant", "content": content})
                continue
            texts = [get(b, "text", "") or "" for b in content if get(b, "type") == "text"]
            calls = [{"id": get(b, "id"), "type": "function", "function": {"name": get(b, "name"), "arguments": jdump(get(b, "input") or {})}}
                     for b in content if get(b, "type") == "tool_use"]
            msg: Dict[str, Any] = {"role": "assistant", "content": "\n".join(texts) if texts else None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
    return out


def _usage(us: Any) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for src, dst in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
        v = get(us, src) if us is not None else None
        if isinstance(v, int) and not isinstance(v, bool):
            out[dst] = v
    det = get(us, "prompt_tokens_details") if us is not None else None
    cached = get(det, "cached_tokens") if det is not None else None
    if isinstance(cached, int) and not isinstance(cached, bool):
        out["cache_read_input_tokens"] = cached
    return out


def turn_from_message(msg: Any, usage: Dict[str, int], model: Optional[str], finish: str) -> Turn:
    content: List[Any] = []
    reasoning = get(msg, "reasoning_content") or get(msg, "reasoning")
    if isinstance(reasoning, str) and reasoning:
        content.append(thinking_block(reasoning))
    text = get(msg, "content")
    if isinstance(text, str) and text:
        content.append(text_block(text))
    elif isinstance(text, list):                                           # content parts
        s = "".join(get(p, "text", "") or "" for p in text if get(p, "type") == "text")
        if s:
            content.append(text_block(s))
    for k, tc in enumerate(get(msg, "tool_calls") or []):
        fn = get(tc, "function")
        name, raw = get(fn, "name"), get(fn, "arguments")
        try:
            args = json.loads(raw) if isinstance(raw, str) and raw.strip() else ({} if raw in (None, "") else raw)
        except ValueError:
            args = None
        if isinstance(name, str) and name and isinstance(args, dict):
            content.append(tool_block(get(tc, "id") or "call_%d" % k, name, args))
        else:                                                              # not a well-formed call: it never reaches the loom, only its hash is kept
            content.append(text_block(raw if isinstance(raw, str) else jdump(raw)))
    return Turn(content=content, usage=usage, model=model, stop_reason="tool_use" if any(b.type == "tool_use" for b in content) else (finish or "end_turn"))


class OpenAICompatBackend:
    name = "openai"

    def __init__(self, model: str, base_url: Optional[str] = None, client: Any = None, *, api_key_env: Optional[str] = None, forced: bool = True,
                 max_tokens_param: str = "max_tokens", temperature: Optional[float] = None) -> None:
        self.model = model
        self.base_url = base_url
        self.forced = forced
        self.max_tokens_param = max_tokens_param
        self.temperature = temperature
        self.key_source: Optional[str] = None
        self._client = client
        self._api_key_env = api_key_env
        self.last_response_model: Optional[str] = None

    def client(self) -> Any:
        if self._client is None:
            try:
                import openai
            except ImportError as e:
                raise BackendError('the `openai` SDK is not installed (pip install "vera-harness[openai]")', "sdk_missing") from e
            key = keys.resolve_api_key("openai", self._api_key_env)
            if key:
                self.key_source = keys.key_source("openai", self._api_key_env)
            elif self.base_url:
                key = keys.LOCAL_PLACEHOLDER                                # a local server asks for none
                self.key_source = "none (local server)"
            else:
                raise BackendError("no API key: set VERA_OPENAI_API_KEY or OPENAI_API_KEY, or give --base-url of a local server", "no_api_key")
            kw: Dict[str, Any] = {"api_key": key}
            if self.base_url:
                kw["base_url"] = self.base_url
            self._client = openai.OpenAI(**kw)
        return self._client

    def tool_choice(self) -> Tuple[dict, bool]:
        return api_forced_choice(self.model, self.forced)

    def request(self, system: str, messages: Sequence[dict], tools: Sequence[dict], max_tokens: int, tool_choice: Optional[dict], extra: Optional[dict]) -> dict:
        kw: Dict[str, Any] = {"model": self.model, "messages": to_openai_messages(system, messages), self.max_tokens_param: max_tokens}
        if tools:
            kw["tools"] = to_openai_tools(tools)
            kw["tool_choice"] = to_openai_choice(tool_choice, self.forced)
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if extra:
            kw.update(extra)
        return kw

    def send(self, *, system: str, messages: Sequence[dict], tools: Sequence[dict], max_tokens: int, tool_choice: Optional[dict] = None,
             extra: Optional[dict] = None) -> Turn:
        resp = self.client().chat.completions.create(**self.request(system, messages, tools, max_tokens, tool_choice, extra))
        choices = get(resp, "choices") or []
        if not choices:
            return Turn(content=[], usage=_usage(get(resp, "usage")), model=get(resp, "model"), stop_reason="no_choices")
        ch = choices[0]
        self.last_response_model = get(resp, "model")
        return turn_from_message(get(ch, "message"), _usage(get(resp, "usage")), get(resp, "model"), str(get(ch, "finish_reason") or ""))

    def describe(self) -> dict:
        d = {"backend": self.name, "model": self.model, "tool_choice": "required" if self.forced else "auto"}
        if self.base_url:
            d["base_url"] = self.base_url
        return d

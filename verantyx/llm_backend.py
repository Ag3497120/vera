"""W10-f04 (O6): 後段の差し替え口。`chat(...)` の 1 つの形 `{ok, content, usage, error}` で ollama・openai・fake を呼ぶ (docs/FUSION.md §6, K285)。

`vera serve --backend ollama|openai` と候補の問い（`fill_candidates`）の両方がここを通る。後段を替えても Vera の規則（読む・決める・答える・棄権する）は変わらない:
ここは「文字列を送って文字列を受け取る」だけで、返答を解釈しない。失敗は型つき（TIMEOUT・CONNECT_FAILED・HTTP_ERROR・BAD_RESPONSE、fake は SCRIPT_EXHAUSTED）で、
「空の答え」や「候補なし」に変換しない。標準ライブラリだけ（`urllib.request.urlopen` は呼び出し時に属性で引く: テストが差し替える）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

BACKENDS = ("ollama", "openai", "fake")
FAILURE_TYPES = ("TIMEOUT", "CONNECT_FAILED", "HTTP_ERROR", "BAD_RESPONSE", "SCRIPT_EXHAUSTED")
OLLAMA_URL = "http://127.0.0.1:11434"
_SHOWN_LINE = re.compile(r"^(\d+): (\{.*\})$")


def _ollama_chat(url: str, model: str, messages, fmt, timeout: float = 180.0, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Ollama の /api/chat を標準ライブラリで呼ぶ。失敗は型つき: TIMEOUT・CONNECT_FAILED・HTTP_ERROR・BAD_RESPONSE。（W10-f01 の `vera_server._ollama_chat` をそのまま移したもの）"""
    import socket
    import urllib.error
    import urllib.request

    body: Dict[str, Any] = {"model": model, "messages": list(messages), "stream": False, "think": False, "options": {"temperature": 0}}
    if fmt is not None:
        body["format"] = fmt
    elif max_tokens is not None:                  # a grammar bounds its own output; only the free answer of layer 0 is cut here
        body["options"]["num_predict"] = max_tokens
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})

    def fail(kind: str, detail: str) -> Dict[str, Any]:
        return {"ok": False, "content": None, "error": {"type": kind, "detail": detail}}

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return fail("HTTP_ERROR", "%s %s" % (exc.code, exc.read()[:200].decode("utf-8", "replace")))
    except (socket.timeout, TimeoutError) as exc:
        return fail("TIMEOUT", str(exc) or "timed out")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            return fail("TIMEOUT", str(exc.reason) or "timed out")
        return fail("CONNECT_FAILED", str(exc.reason))
    except OSError as exc:
        return fail("CONNECT_FAILED", "%s: %s" % (type(exc).__name__, exc))
    try:
        data = json.loads(raw)
        content = data["message"]["content"]
    except (ValueError, KeyError, TypeError):
        return fail("BAD_RESPONSE", raw[:200].decode("utf-8", "replace"))
    if not isinstance(content, str):
        return fail("BAD_RESPONSE", "message.content is not a string")
    usage = {}
    if isinstance(data.get("prompt_eval_count"), int) and isinstance(data.get("eval_count"), int):
        usage = {"prompt_tokens": data["prompt_eval_count"], "completion_tokens": data["eval_count"],
                 "total_tokens": data["prompt_eval_count"] + data["eval_count"]}
    return {"ok": True, "content": content, "error": None, "usage": usage}


def _openai_chat(api_base: str, api_key: Optional[str], model: str, messages, fmt, timeout: float = 180.0, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """OpenAI 互換の `<api_base>/chat/completions`。`fmt`（JSON schema）は `response_format` に、無ければ `max_tokens`。失敗の型は ollama と同じ。"""
    import socket
    import urllib.error
    import urllib.request

    body: Dict[str, Any] = {"model": model, "messages": list(messages), "stream": False, "temperature": 0}
    if fmt is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "vera", "schema": fmt, "strict": True}}
    elif max_tokens is not None:
        body["max_tokens"] = max_tokens
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(api_base.rstrip("/") + "/chat/completions", data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers)

    def fail(kind: str, detail: str) -> Dict[str, Any]:
        return {"ok": False, "content": None, "usage": {}, "error": {"type": kind, "detail": detail}}

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return fail("HTTP_ERROR", "%s %s" % (exc.code, exc.read()[:200].decode("utf-8", "replace")))
    except (socket.timeout, TimeoutError) as exc:
        return fail("TIMEOUT", str(exc) or "timed out")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            return fail("TIMEOUT", str(exc.reason) or "timed out")
        return fail("CONNECT_FAILED", str(exc.reason))
    except OSError as exc:
        return fail("CONNECT_FAILED", "%s: %s" % (type(exc).__name__, exc))
    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return fail("BAD_RESPONSE", raw[:200].decode("utf-8", "replace"))
    if not isinstance(content, str):
        return fail("BAD_RESPONSE", "choices[0].message.content is not a string")
    usage = {}
    u = data.get("usage")
    if isinstance(u, dict) and all(isinstance(u.get(k), int) for k in ("prompt_tokens", "completion_tokens")):
        usage = {"prompt_tokens": u["prompt_tokens"], "completion_tokens": u["completion_tokens"], "total_tokens": u["prompt_tokens"] + u["completion_tokens"]}
    return {"ok": True, "content": content, "usage": usage, "error": None}


class FakeBackend:
    """テスト用: 台本から返す。`sent` は後段の境界で実際に渡された呼び出し（model・messages・fmt）をすべて記録する。
    台本の 1 歩 = {'raw': 文字列}（成功の本文）| {'fail': 型}（型つき失敗）| {'pick': 語 | None}（閉じた一覧の問いへの返答。直前の問いの `番号: JSON` の行から語の番号を引く）。
    台本が尽きたら SCRIPT_EXHAUSTED（黙って空を返さない）。"""

    def __init__(self, script: Sequence[Dict[str, Any]] = ()) -> None:
        self.script: List[Dict[str, Any]] = [dict(s) for s in script]
        self.sent: List[Dict[str, Any]] = []
        self.calls = 0

    def __call__(self, model: str, messages, fmt, *, timeout: float = 180.0, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        self.sent.append({"model": model, "messages": json.loads(json.dumps(list(messages), ensure_ascii=False)), "fmt": json.loads(json.dumps(fmt, ensure_ascii=False)) if fmt is not None else None})
        i = self.calls
        self.calls += 1
        if i >= len(self.script):
            return {"ok": False, "content": None, "usage": {}, "error": {"type": "SCRIPT_EXHAUSTED", "detail": "call %d, script has %d steps" % (i + 1, len(self.script))}}
        step = self.script[i]
        if "fail" in step:
            return {"ok": False, "content": None, "usage": {}, "error": {"type": step["fail"], "detail": "scripted"}}
        if "pick" in step:
            return {"ok": True, "content": json.dumps({"choice": self._index_of(step["pick"], messages)}), "usage": {}, "error": None}
        return {"ok": True, "content": step["raw"], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "error": None}

    @staticmethod
    def _index_of(term: Optional[str], messages) -> Optional[int]:
        if term is None:
            return None
        prompt = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "user")
        for line in prompt.split("\n"):
            m = _SHOWN_LINE.match(line)
            if m and json.loads(m.group(2)).get("term") == term:
                return int(m.group(1))
        return None


def chat(backend: str, model: str, messages, fmt, *, timeout: float = 180.0, max_tokens: Optional[int] = None, url: Optional[str] = None,
         api_base: Optional[str] = None, api_key: Optional[str] = None, fake: Optional[FakeBackend] = None) -> Dict[str, Any]:
    """1 つの形: `{ok, content, usage, error}`。`backend` は ollama・openai・fake。openai は `api_base`（無ければ環境変数 VERA_LLM_API_BASE）が要る（無ければ BAD_RESPONSE ではなく
    ValueError: 設定の誤りは後段の失敗ではない）。"""
    if backend == "ollama":
        out = _ollama_chat(url or OLLAMA_URL, model, messages, fmt, timeout, max_tokens)
        out.setdefault("usage", {})
        return out
    if backend == "openai":
        base = api_base or os.environ.get("VERA_LLM_API_BASE")
        if not base:
            raise ValueError("openai backend needs api_base or VERA_LLM_API_BASE")
        return _openai_chat(base, api_key if api_key is not None else os.environ.get("VERA_LLM_API_KEY"), model, messages, fmt, timeout, max_tokens)
    if backend == "fake":
        if fake is None:
            raise ValueError("fake backend needs a FakeBackend")
        return fake(model, messages, fmt, timeout=timeout, max_tokens=max_tokens)
    raise ValueError("unknown backend %r (want one of %s)" % (backend, ", ".join(BACKENDS)))


def make_chat(backend: str, **config: Any) -> Callable[[str, Any, Any], Dict[str, Any]]:
    """`(model, messages, fmt) -> {ok, content, usage, error}` を返す束ね（`fusion_turn` の `llm_chat` と同じ形）。"""
    def call(model, messages, fmt):
        return chat(backend, model, messages, fmt, **config)
    return call

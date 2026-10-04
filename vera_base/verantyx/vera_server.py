"""Milestone N — Vera-as-harness HTTP+SSE daemon.

Additive to (not a replacement for) mcp_server.py: MCP stays exactly as-is
for other clients (Claude Desktop etc). This is a second, IDE-facing
transport that inverts the calling direction — instead of the IDE calling
Vera as an MCP tool, Vera runs Agent.run()'s ReAct loop as the primary
controller and pushes live progress to the IDE over Server-Sent Events, so
the IDE no longer has to poll.

Deliberately stdlib-only (http.server, threading, queue, uuid) — same
"zero required third-party dependencies" principle Milestone H's
vera-memory freeze already established. No aiohttp/websockets.

Local-only, no auth: v1 assumes 127.0.0.1 and a trusted local caller, same
as Ollama's own default. Do not bind 0.0.0.0 without adding auth first.
"""
from __future__ import annotations

import concurrent.futures
import json
import queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse, parse_qs

from .agent import Agent
from .cross_store import CrossStore
from .cognitive_interventions import InterventionLog, intervention_log_path
from .gap_graph import GapGraph, gap_graph_path
from .tool_call_quarantine import ToolCallQuarantine, tool_call_quarantine_path


class RunState:
    def __init__(self) -> None:
        self.events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.done = threading.Event()
        self.result: Optional[Dict[str, Any]] = None


def _make_llm_fn(model: str, backend: str, jgen_endpoint: Optional[str]) -> Optional[Callable]:
    if backend == "jgen":
        if not jgen_endpoint:
            return None
        return _jgen_llm_fn(jgen_endpoint)
    from .llm_local import ollama_generate

    def llm_fn(prompt: str, system: Optional[str]) -> Dict[str, Any]:
        return ollama_generate(model, prompt, system=system, timeout=180)

    return llm_fn


def _jgen_llm_fn(endpoint: str) -> Callable:
    """Points Agent's llm callback at the IDE's JGenAgentServer (N4) instead
    of Ollama — this is the concrete "IDE as tool provider" inversion:
    Vera is still the caller/controller, JGEN is just a subordinate tool
    reachable over loopback HTTP, same shape as Ollama's own API."""
    import urllib.error
    import urllib.request

    def llm_fn(prompt: str, system: Optional[str]) -> Dict[str, Any]:
        payload = json.dumps({"prompt": prompt, "system": system or ""}).encode()
        req = urllib.request.Request(
            endpoint.rstrip("/") + "/jgen/generate",
            data=payload, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                d = json.loads(resp.read())
            return {"ok": True, "text": d.get("text", "")}
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            return {"ok": False, "error": f"jgen_endpoint_error: {e}"}

    return llm_fn


# --- W10-f01: 融合の入口 (docs/FUSION.md) -----------------------------------------------------------------------------------------------------
# OpenAI 互換 /v1/chat/completions と Ollama 互換 /api/chat。`fusion` が渡されたときだけ答える（無ければ従来どおり 404）。
# 読解・文法・検証・方針は decode_grammar.py（純粋な関数）。ここは HTTP と LLM の呼び出しだけ。
FUSION_POST_PATHS = ("/v1/chat/completions", "/api/chat")
FUSION_GET_PATHS = ("/v1/models", "/api/tags")


class FusionConfig:
    """`vera serve --backend ollama` の設定。`records` は起動時に 1 回読んだ文書。`llm_chat` を差し込むと LLM を差し替えられる（テスト）。"""

    def __init__(self, *, model: str, documents, records, strict: bool = False, ollama_url: str = "http://127.0.0.1:11434",
                 timeout: float = 180.0, llm_chat: Optional[Callable] = None) -> None:
        self.model = model
        self.documents = list(documents)
        self.records = records
        self.strict = bool(strict)
        self.ollama_url = ollama_url
        self.timeout = float(timeout)
        self.llm_chat = llm_chat
        # 読解・文法・検証・方針（Vera の側の処理）は専用の 1 本のスレッドだけで行う。配置の SQLite 接続は作ったスレッドでしか使えず
        # （coarse_place は禁止ファイル）、ThreadingHTTPServer はリクエストごとにスレッドを作るため。LLM の呼び出しはこのスレッドの外。
        self._vera_thread = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="vera-fusion")

    def run_vera(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Vera の側の処理を専用スレッドで実行して結果を返す（例外はそのまま呼び出し側に出る）。"""
        return self._vera_thread.submit(fn, *args, **kwargs).result()

    @classmethod
    def load(cls, *, model: str, documents, strict: bool = False, ollama_url: str = "http://127.0.0.1:11434",
             timeout: float = 180.0, llm_chat: Optional[Callable] = None) -> "FusionConfig":
        """文書の読み込み（各文の再読）も専用スレッドで行う入口。本番の起動（cli）はこれを使う。"""
        from . import decode_grammar as G
        self = cls(model=model, documents=documents, records=None, strict=strict, ollama_url=ollama_url, timeout=timeout, llm_chat=llm_chat)
        self.records = self.run_vera(G.load_records, list(documents))
        return self


class FusionBadRequest(Exception):
    def __init__(self, error: str, detail: str = "") -> None:
        super().__init__(error)
        self.error, self.detail = error, detail


def _ollama_chat(url: str, model: str, messages, fmt, timeout: float = 180.0, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Ollama の /api/chat を標準ライブラリで呼ぶ。失敗は型つき: TIMEOUT・CONNECT_FAILED・HTTP_ERROR・BAD_RESPONSE。"""
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


def _last_user_text(messages) -> str:
    from . import decode_grammar as G
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            return G._content_text(m.get("content")).strip()
    return ""


def fusion_turn(messages, vera_opts, cfg: FusionConfig, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """1 ターン（設計書 §5 の (1)〜(6)）。{"content","vera","usage"}。入力が不正なら FusionBadRequest。"""
    from . import basis_policy as bp
    from . import decode_grammar as G
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        raise FusionBadRequest("BAD_MESSAGES", "messages must be a list of objects")
    opts = vera_opts if isinstance(vera_opts, dict) else {}
    rk = opts.get("request_kind", "factual")
    if rk not in bp.REQUEST_KINDS:
        raise FusionBadRequest("BAD_REQUEST_KIND", "want one of %s" % ", ".join(bp.REQUEST_KINDS))
    human = opts.get("human_present", False)
    if not isinstance(human, bool):
        raise FusionBadRequest("BAD_HUMAN_PRESENT", "human_present must be a boolean")
    if max_tokens is not None and (type(max_tokens) is not int or max_tokens <= 0):
        raise FusionBadRequest("BAD_MAX_TOKENS", "max_tokens (num_predict) must be a positive integer")
    question = _last_user_text(messages)
    if not question:
        raise FusionBadRequest("NO_USER_MESSAGE", "no user message with text")
    t0 = time.perf_counter()
    def _plan():
        t = G.plan_turn(question, rk, cfg.records, cfg.documents, strict=cfg.strict)
        return t, (G.llm_messages(t, messages, cfg.records) if t["call_llm"] else None)
    turn, llm_msgs = cfg.run_vera(_plan)
    llm = None
    llm_ms = 0.0
    if turn["call_llm"]:
        fmt = turn["grammar"]["json_schema"] if turn["grammar"] else None
        t1 = time.perf_counter()
        chat = cfg.llm_chat or (lambda model, msgs, f: _ollama_chat(cfg.ollama_url, model, msgs, f, cfg.timeout, max_tokens))
        try:
            llm = chat(cfg.model, llm_msgs, fmt)
        except Exception as exc:       # 差し込まれた LLM も本物も、落とさずに型で返す
            llm = {"ok": False, "content": None, "error": {"type": "CONNECT_FAILED", "detail": "%s: %s" % (type(exc).__name__, exc)}}
        llm_ms = (time.perf_counter() - t1) * 1000.0
    content, vera = cfg.run_vera(G.conclude, turn, llm, cfg.records, model=cfg.model, human_present=human)
    total_ms = (time.perf_counter() - t0) * 1000.0
    vera["timing"] = {"vera_ms": round(total_ms - llm_ms, 3), "llm_ms": round(llm_ms, 3)}
    return {"content": content, "vera": vera, "usage": (llm or {}).get("usage") or {}}


def _fusion_openai_body(cfg: FusionConfig, res: Dict[str, Any], rid: str, created: int) -> Dict[str, Any]:
    return {"id": rid, "object": "chat.completion", "created": created, "model": cfg.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": res["content"]}, "finish_reason": "stop"}],
            "usage": res["usage"], "vera": res["vera"]}



def make_handler(store: CrossStore, save: Callable[[], None], default_model: str,
                  jgen_endpoint: Optional[str], gap_graph: GapGraph, gap_graph_save: Callable[[], None],
                  intervention_log: InterventionLog, intervention_log_save: Callable[[], None],
                  tool_call_quarantine: ToolCallQuarantine, tool_call_quarantine_save: Callable[[], None],
                  fusion: Optional[FusionConfig] = None):
    runs: Dict[str, RunState] = {}
    runs_lock = threading.Lock()
    one_entry = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
            pass

        def _json(self, code: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _fusion_post(self, path: str) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length < 0:
                    raise ValueError("negative Content-Length")
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body is not an object")
            except ValueError:
                self._json(400, {"ok": False, "error": "bad_json"})
                return
            try:
                opts = body.get("options") if isinstance(body.get("options"), dict) else {}
                limit = body.get("max_tokens") if path == "/v1/chat/completions" else opts.get("num_predict")
                res = fusion_turn(body.get("messages"), body.get("vera"), fusion, limit)
            except FusionBadRequest as exc:
                self._json(400, {"ok": False, "error": exc.error, "detail": exc.detail})
                return
            created = int(time.time())
            if path == "/v1/chat/completions":
                rid = "chatcmpl-" + uuid.uuid4().hex
                if body.get("stream") is True:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    base = {"id": rid, "object": "chat.completion.chunk", "created": created, "model": fusion.model}
                    chunks = [{**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": res["content"]}, "finish_reason": None}]},
                              {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "vera": res["vera"]}]
                    try:
                        for ch in chunks:
                            self.wfile.write(("data: %s\n\n" % json.dumps(ch, ensure_ascii=False)).encode("utf-8"))
                        self.wfile.write(b"data: [DONE]\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    return
                self._json(200, _fusion_openai_body(fusion, res, rid, created))
                return
            # /api/chat: Ollama は stream の既定が true
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created))
            msg = {"role": "assistant", "content": res["content"]}
            if body.get("stream", True) is False:
                self._json(200, {"model": fusion.model, "created_at": stamp, "message": msg, "done": True, "done_reason": "stop", "vera": res["vera"]})
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            lines = [{"model": fusion.model, "created_at": stamp, "message": msg, "done": False},
                     {"model": fusion.model, "created_at": stamp, "message": {"role": "assistant", "content": ""}, "done": True,
                      "done_reason": "stop", "vera": res["vera"]}]
            try:
                for ln in lines:
                    self.wfile.write((json.dumps(ln, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's own naming convention
            parsed = urlparse(self.path)
            if fusion is not None and parsed.path in FUSION_POST_PATHS:
                self._fusion_post(parsed.path)
                return
            if parsed.path not in ("/agent/run", "/vera/ask"):
                self._json(404, {"ok": False, "error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"ok": False, "error": "bad_json"})
                return
            if parsed.path == "/vera/ask":
                nonlocal one_entry
                from .one import Vera
                if one_entry is None:
                    one_entry = Vera().load_store(store)
                self._json(200, one_entry.ask(str(body.get("question") or body.get("text") or "")))
                return
            task = body.get("task", "")
            if not task:
                self._json(400, {"ok": False, "error": "missing_task"})
                return
            model = body.get("model") or default_model
            backend = body.get("backend", "ollama")
            # Milestone O: same request-scoped override pattern as "model"/
            # "backend" -- the IDE's 3-mode toggle sends this per request
            # rather than needing to write Vera-alpha's own config.json from
            # a separate process.
            cognition_mode = body.get("cognition_mode", "normal")
            llm_fn = _make_llm_fn(model, backend, jgen_endpoint)
            if llm_fn is None:
                self._json(400, {"ok": False, "error": "jgen_backend_requested_but_no_endpoint_configured"})
                return

            run_id = uuid.uuid4().hex
            state = RunState()
            with runs_lock:
                runs[run_id] = state

            def on_step(event: Dict[str, Any]) -> None:
                state.events.put(event)

            def worker() -> None:
                # jgen_endpoint doubles as the browser bridge -- both are
                # served by the same IDE-side JGenAgentServer (/jgen/generate
                # and /browser/fetch), so this reuses one configured URL
                # rather than adding a second CLI flag for the same daemon.
                agent = Agent(store, llm=llm_fn, save=save, auto_approve=False,
                              browser_endpoint=jgen_endpoint,
                              gap_graph=gap_graph, cognition_mode=cognition_mode,
                              intervention_log=intervention_log,
                              tool_call_quarantine=tool_call_quarantine)
                result = agent.run(task, on_step=on_step)
                # Milestone R4: unlike gap_graph/intervention_log, tool-call
                # proposals matter in EVERY cognition mode (a normal-mode
                # chat that wants to write a file needs this exactly as
                # much as Sleep mode does), so this save is unconditional.
                tool_call_quarantine_save()
                if cognition_mode in ("experiment", "sleep"):
                    gap_graph_save()
                    intervention_log_save()
                state.result = result
                state.done.set()
                state.events.put({"__terminal__": True})

            threading.Thread(target=worker, daemon=True).start()
            self._json(202, {"ok": True, "run_id": run_id})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)

            if parsed.path == "/events":
                run_id = (qs.get("run_id") or [""])[0]
                with runs_lock:
                    state = runs.get(run_id)
                if state is None:
                    self._json(404, {"ok": False, "error": "unknown_run_id"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                while True:
                    try:
                        event = state.events.get(timeout=30)
                    except queue.Empty:
                        # keep-alive comment line — standard SSE idiom
                        try:
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            return
                        continue
                    if event.get("__terminal__"):
                        try:
                            self.wfile.write(b"event: done\ndata: {}\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                        return
                    try:
                        line = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
                        self.wfile.write(line)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                return

            if parsed.path.startswith("/agent/run/"):
                run_id = parsed.path.rsplit("/", 1)[-1]
                with runs_lock:
                    state = runs.get(run_id)
                if state is None:
                    self._json(404, {"ok": False, "error": "unknown_run_id"})
                    return
                if not state.done.is_set():
                    self._json(200, {"ok": True, "status": "running"})
                    return
                self._json(200, {"ok": True, "status": "done", "result": state.result})
                return

            if fusion is not None and parsed.path == "/v1/models":
                self._json(200, {"object": "list", "data": [{"id": fusion.model, "object": "model", "owned_by": "vera"}]})
                return
            if fusion is not None and parsed.path == "/api/version":     # Open WebUI checks it when it connects to an Ollama server
                self._json(200, {"version": "vera-fusion"})
                return
            if fusion is not None and parsed.path == "/api/tags":
                self._json(200, {"models": [{"name": fusion.model, "model": fusion.model}]})
                return

            self._json(404, {"ok": False, "error": "not_found"})

    return Handler


def serve(store: CrossStore, save: Callable[[], None], *, port: int = 8765,
          default_model: str = "", jgen_endpoint: Optional[str] = None,
          store_path: Optional["Path"] = None, fusion: Optional[FusionConfig] = None) -> int:
    from pathlib import Path as _Path

    resolved_store_path = store_path or _Path("vera_store.json")
    ggpath = gap_graph_path(resolved_store_path)
    gap_graph = GapGraph.load(ggpath)

    def gap_graph_save() -> None:
        gap_graph.save(ggpath)

    ilpath = intervention_log_path(resolved_store_path)
    intervention_log = InterventionLog.load(ilpath)

    def intervention_log_save() -> None:
        intervention_log.save(ilpath)

    tcqpath = tool_call_quarantine_path(resolved_store_path)
    tool_call_quarantine = ToolCallQuarantine.load(tcqpath)

    def tool_call_quarantine_save() -> None:
        tool_call_quarantine.save(tcqpath)

    handler = make_handler(store, save, default_model, jgen_endpoint, gap_graph, gap_graph_save,
                            intervention_log, intervention_log_save,
                            tool_call_quarantine, tool_call_quarantine_save, fusion)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"[vera serve] listening on http://127.0.0.1:{port} "
          f"(model={default_model or '(unset)'}, jgen_endpoint={jgen_endpoint or '(none)'})")
    if fusion is not None:
        print(f"[vera serve] fusion layer {1 if fusion.strict else 0} ({'strict' if fusion.strict else 'default'}): "
              f"model={fusion.model}, documents={len(fusion.documents)}, ollama={fusion.ollama_url} "
              f"-- POST /v1/chat/completions, POST /api/chat")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

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
import os
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
                 timeout: float = 180.0, llm_chat: Optional[Callable] = None, backend: str = "ollama", api_base: Optional[str] = None,
                 api_key: Optional[str] = None, fill: Any = None, layer: Optional[str] = None) -> None:
        self.model = model
        self.layer = None                     # W10-f05: a placement layer (a name or a path) or None (nothing in any output changes)
        if layer is not None and str(layer).strip() != "":
            from . import placement_layer as PL
            env = PL.spec_from_env()
            if env is not None and env != layer:
                raise FusionBadRequest("LAYER_ENV_CONFLICT", "layer %r and %s=%r disagree" % (layer, PL.ENV_LAYER, env))
            os.environ[PL.ENV_LAYER] = str(layer)     # the reader reaches the layer through coarse_place.query, which reads this variable (K297: unset = the base alone)
            self.layer = str(layer)
        else:                                 # no --layer: the environment alone (VERA_PLACEMENT_LAYER) also makes the layer work for the reader, so the answer must say so (unset: nothing changes, K297)
            from . import placement_layer as PL
            env = PL.spec_from_env()
            if env is not None:
                self.layer = str(env)
        self.backend = backend                # W10-f04 (O6): "ollama" (default, as before) or "openai" (llm_backend)
        self.api_base, self.api_key = api_base, api_key
        self.fill = fill                      # W10-f04: a fill_candidates.FillConfig, or None (the candidate mouth is off: nothing in the output changes)
        self.fill_stats: Dict[str, Any] = {}
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
             timeout: float = 180.0, llm_chat: Optional[Callable] = None, backend: str = "ollama", api_base: Optional[str] = None,
             api_key: Optional[str] = None, fill: Any = None, layer: Optional[str] = None) -> "FusionConfig":
        """文書の読み込み（各文の再読）も専用スレッドで行う入口。本番の起動（cli）はこれを使う。"""
        from . import decode_grammar as G
        self = cls(model=model, documents=documents, records=None, strict=strict, ollama_url=ollama_url, timeout=timeout, llm_chat=llm_chat,
                   backend=backend, api_base=api_base, api_key=api_key, fill=fill, layer=layer)
        self.records = self.run_vera(G.load_records, list(documents))
        if fill is not None:                  # W10-f04 (8): the unread sentences of the documents get the candidate mouth; the record is NOT changed (only the ledger is written)
            self.run_vera(self._fill_documents)
        return self

    def backend_chat(self, max_tokens: Optional[int] = None) -> Callable:
        """`(model, messages, fmt) -> {ok, content, usage, error}` of the entrance's backend (an injected `llm_chat` first)."""
        if self.llm_chat is not None:
            return self.llm_chat
        if self.backend == "openai":
            from .llm_backend import make_chat
            return make_chat("openai", timeout=self.timeout, max_tokens=max_tokens, api_base=self.api_base, api_key=self.api_key)
        return lambda model, msgs, f: _ollama_chat(self.ollama_url, model, msgs, f, self.timeout, max_tokens)

    def _fill_documents(self) -> None:
        from . import fill_candidates as FC
        fill = self.fill
        chat, model = fill.chat or self.backend_chat(), fill.model or self.model
        budget = [fill.max_doc_holes]
        stats = {"sentences_with_holes": 0, "holes_asked": 0, "adopted": 0, "skipped_holes": 0, "not_adopted": 0, "backend_failed": 0}
        for rec in self.records.records:
            if self.records.crosses.get(rec["id"]) is not None:
                continue
            res = FC.fill_sentence(rec["text"], fill, chat, model, records=self.records, doc_id=self.records.where[rec["id"]]["source"], budget=budget)
            stats["skipped_holes"] += res["skipped"]
            if res["decisions"]:
                stats["sentences_with_holes"] += 1
            for d in res["decisions"]:
                stats["holes_asked"] += 1
                stats["adopted" if d.status == "ADOPTED" else "backend_failed" if d.status == "BACKEND_FAILED" else "not_adopted"] += 1
        self.fill_stats = stats


class FusionBadRequest(Exception):
    def __init__(self, error: str, detail: str = "") -> None:
        super().__init__(error)
        self.error, self.detail = error, detail


from .llm_backend import _ollama_chat      # W10-f04 (O6): the body moved to llm_backend.py; the name stays here (fusion_turn and the tests look it up in this module at call time)


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
        chat = cfg.llm_chat or (cfg.backend_chat(max_tokens) if cfg.backend != "ollama" else (lambda model, msgs, f: _ollama_chat(cfg.ollama_url, model, msgs, f, cfg.timeout, max_tokens)))
        try:
            llm = chat(cfg.model, llm_msgs, fmt)
        except Exception as exc:       # 差し込まれた LLM も本物も、落とさずに型で返す
            llm = {"ok": False, "content": None, "error": {"type": "CONNECT_FAILED", "detail": "%s: %s" % (type(exc).__name__, exc)}}
        llm_ms = (time.perf_counter() - t1) * 1000.0
    content, vera = cfg.run_vera(G.conclude, turn, llm, cfg.records, model=cfg.model, human_present=human)
    fill_llm_ms = 0.0
    if cfg.fill is not None:      # W10-f04 (7): the candidate mouth only ANNOTATES `vera` (provenance arms, holes, ledger ids); the content and the outcome are already decided
        fill_llm_ms = cfg.run_vera(_fill_annotate, cfg, turn, vera)
    total_ms = (time.perf_counter() - t0) * 1000.0
    vera["timing"] = {"vera_ms": round(total_ms - llm_ms - fill_llm_ms, 3), "llm_ms": round(llm_ms, 3)}
    if cfg.fill is not None:
        vera["timing"]["fill_llm_ms"] = round(fill_llm_ms, 3)
    if cfg.layer is not None:                 # W10-f05: the LAST key of `vera`; `vera.layer` (the fusion layer 0/1) is a different thing and stays as it was
        vera["placement_layer"] = cfg.run_vera(_layer_summary, cfg)
    return {"content": content, "vera": vera, "usage": (llm or {}).get("usage") or {}}


def _layer_summary(cfg: FusionConfig) -> Dict[str, Any]:
    """W10-f05 (docs/FUSION.md section 7): `{name, status, growth: {words_direct, words_human, words_estimated, last_grown}}` of the layer the entrance was started with."""
    from . import coarse_place
    from . import placement_layer as PL
    base_pl, _why = coarse_place._open(os.environ.get("VERA_PLACEMENT"))
    g = PL.growth(cfg.layer, None, getattr(base_pl, "sha", None))
    path, name, _w = PL.resolve(cfg.layer)
    if g.get("layer_status") != "OK":
        return {"name": name or cfg.layer, "status": g.get("layer_status"), "growth": None}
    return {"name": g["layer"], "status": "OK", "growth": {"words_direct": g["words"]["direct"], "words_human": g["words"]["human"],
                                                          "words_estimated": g["words"]["estimated"], "last_grown": g["last_grown"]}}


def _fill_annotate(cfg: FusionConfig, turn: Dict[str, Any], vera: Dict[str, Any]) -> float:
    """W10-f04 (7)(8): for each unread sentence of the LLM's output that has a typed hole, and for the declarative form of a question the reader could not read because of a filler, ask the candidate
    mouth. An adopted candidate becomes the arm of that sentence in `vera.provenance` with kind `testimony_fill` (origin testimony; the sentence stays testimony / constructed: never a record); what stays
    a hole is in `vera.holes`; every ledger row written is in `vera.ledger_ids`. Nothing here changes `content` or `outcome` (K283). Returns the milliseconds spent in the backend."""
    from . import fill_candidates as FC
    from . import semantic_read
    fill = cfg.fill
    chat, model = fill.chat or cfg.backend_chat(), fill.model or cfg.model
    holes: list = []
    ids: list = []
    llm_ms = 0.0

    def note(source: str, index: Optional[int], res: Dict[str, Any], text: str) -> None:
        nonlocal llm_ms
        for h in res["holes"]:
            dec = h.get("decision")
            if dec is not None:
                ids.append(dec["fill_id"]); llm_ms += (dec.get("timing") or {}).get("llm_ms", 0.0)
            if dec is None or dec["status"] != "ADOPTED":
                holes.append({"source": source, "sentence_index": index, "particle": h["particle"], "head": h["head"], "arm": h["arm"], "expected_types": h["expected_types"],
                              "role_candidates": h["role_candidates"], "status": None if dec is None else dec["status"], "reason": "HOLE_BUDGET_EXHAUSTED" if dec is None else dec["reason"],
                              "ledger_id": None if dec is None else dec["fill_id"], "clarify": None})
    prov = vera.get("provenance") or []
    for i, item in enumerate(prov):
        if item.get("read") or item.get("mark") != "UNREAD" or item.get("sentence_kind") == "record":
            continue
        res = FC.fill_sentence(item["text"], fill, chat, model, records=cfg.records, doc_id="llm_output")
        note("llm_output", i, res, item["text"])
        for h in res["holes"]:
            dec = h.get("decision")
            if dec is not None and dec["status"] == "ADOPTED":
                role = h["arm"] or "?"
                item.setdefault("arms", {})[role] = {"surface": dec["candidate"], "kind": "testimony_fill", "evidence": [], "hole_word": h["head"], "candidate": dec["candidate"],
                                                     "basis": dec["basis"], "ledger_id": dec["fill_id"], "origin": "testimony"}
    reading = turn.get("reading") or {}
    if reading.get("type") in ("STRUCTURE_UNDETERMINED", "NO_RECORD") and turn.get("question"):
        try:
            q = semantic_read.read_question(turn["question"], placement=fill.placement)
        except semantic_read.ReadError:
            q = None
        decl = ((q or {}).get("question") or {}).get("declarative")
        if isinstance(decl, str) and decl:
            res = FC.fill_sentence(decl, fill, chat, model, records=cfg.records, doc_id="question")
            note("question", None, res, decl)
            for h in res["holes"]:                                    # a clarifying candidate is shown beside the answer, never inside `content`
                dec = h.get("decision")
                if dec is not None and dec["status"] == "ADOPTED":
                    holes.append({"source": "question", "sentence_index": None, "particle": h["particle"], "head": h["head"], "arm": h["arm"], "expected_types": h["expected_types"],
                                  "role_candidates": h["role_candidates"], "status": "ADOPTED", "reason": "ADOPTED", "ledger_id": dec["fill_id"],
                                  "clarify": "「%s」は「%s」のことですか？（証言: LLM の候補。記録の裏づけはありません）" % (h["head"], dec["candidate"])})
    vera["holes"] = holes
    vera["ledger_ids"] = ids
    return llm_ms


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

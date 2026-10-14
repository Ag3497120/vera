"""`vera run`: the local web UI.  Standard library only (`http.server`), one static HTML file shipped in the package (webui/index.html), no external load of any kind.

What it shows (docs/ARCHITECTURE.md): the conversation (the model's answer is ONLY a quote with its source sentence, or 「分かりません」 with the typed reason: the page renders nothing else of
the model), the operation trace of the run, the ledger with its hash chain and a Verify button, for a memory run the notes (SAME_SEAT / UPDATE / REVERSAL_X) and the crosses and nests of the
asked position, and a settings panel (the backend, the model, the paths; for the API keys only whether one is present and where it comes from, never its value; keys are read from the
environment or the macOS Keychain and cannot be typed here).

Exposure.  The server binds 127.0.0.1 (or ::1 / localhost) only; any other address is refused unless `--allow-remote` is given (then anyone who can reach the port can use your configured
backend: do not).  Every `/api/` call needs the per-process token (a header; the page gets it embedded when it is served), every POST must be `application/json`, a request that carries an
`Origin` must come from this very origin, the `Host` header must be this server's own address (DNS rebinding), and no CORS header is ever sent: another web page can neither read an answer
nor make the server run one.  The page is served with a Content-Security-Policy that allows only its own inline script and style (by hash) and connections to itself.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

from verantyx import __version__
from verantyx.harness import keys
from verantyx.harness import plugins as pl
from verantyx.harness import runner as rn
from verantyx.harness.backends import BackendError, make_backend
from verantyx.ledger_events import LedgerError
from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memcross as mx
from verantyx.loom import memory as mem
from verantyx.loom.state import Refuse

DEFAULT_PORT = 3090
MAX_BODY = 64 * 1024
MAX_MESSAGES = 50
TOKEN_HEADER = "X-Vera-Token"
backend_factory: Callable[..., Any] = make_backend                  # tests and embedders replace this to hand the backends a fake client


class ServerError(Exception):
    def __init__(self, msg: str, code: str = "bad_request", status: int = 400) -> None:
        super().__init__(msg)
        self.code, self.status = code, status


# ------------------------------------------------------------------------------------------------------------
# the address
# ------------------------------------------------------------------------------------------------------------
def _loopback_ip(host: str) -> Optional[str]:
    """The canonical loopback address named by `host` ('127.0.0.0/8', '::1', '::ffff:127.x.y.z', the name localhost), else None."""
    if host == "localhost":
        return "127.0.0.1"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    if getattr(ip, "ipv4_mapped", None) is not None and ip.ipv4_mapped.is_loopback:
        return host
    return host if ip.is_loopback else None


def check_bind(host: str, allow_remote: bool = False) -> str:
    """The address to bind: loopback only.  `--allow-remote` does not exist in this version (a token embedded in a page that any network client can GET is no protection): any other address, including
    0.0.0.0 and the empty string, is refused."""
    ip = _loopback_ip(host)
    if ip is None:
        raise ServerError("refusing to bind %r: vera run listens on loopback only (127.0.0.0/8, ::1). Remote access is not available in this version" % host, "bind_refused", 2)
    return ip if host == "localhost" else host


# ------------------------------------------------------------------------------------------------------------
# the page
# ------------------------------------------------------------------------------------------------------------
def _page_source() -> str:
    from importlib import resources
    return resources.files("verantyx.harness").joinpath("webui", "index.html").read_text(encoding="utf-8")


def _csp_hash(text: str) -> str:
    return "'sha256-%s'" % base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def render_page(token: str) -> Tuple[bytes, str]:
    """(the page with the token embedded, its Content-Security-Policy).  The policy allows exactly the page's one inline script and one inline style, by hash."""
    src = _page_source()
    scripts, styles = re.findall(r"<script>(.*?)</script>", src, re.S), re.findall(r"<style>(.*?)</style>", src, re.S)
    if len(scripts) != 1 or len(styles) != 1 or "__VERA_TOKEN__" not in src:
        raise ServerError("webui/index.html must hold exactly one <script>, one <style> and the token placeholder", "bad_page", 500)
    csp = ("default-src 'none'; script-src %s; style-src %s; connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
           % (_csp_hash(scripts[0]), _csp_hash(styles[0])))
    return src.replace("__VERA_TOKEN__", token).encode("utf-8"), csp


# ------------------------------------------------------------------------------------------------------------
# the state of one `vera run`
# ------------------------------------------------------------------------------------------------------------
LOCKED_KEYS = ("backend", "base_url", "api_key_env", "docs", "store", "runs_dir")        # command line only: the page shows them read-only (a token holder must not be able to point the backend, or the name of a secret, anywhere)
CONFIG_KEYS = ("backend", "model", "base_url", "api_key_env", "tool_choice", "temperature", "evidence", "docs", "store", "runs_dir", "memory_profile", "gate_filters", "note_kinds")
_ENV_RX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class App:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.token = secrets.token_urlsafe(32)
        self.config: Dict[str, Any] = {"backend": "anthropic", "model": None, "base_url": None, "api_key_env": None, "tool_choice": "required", "temperature": None, "evidence": rn.EVIDENCE_DEFAULT,
                                       "docs": None, "store": None, "runs_dir": rn.DEFAULT_RUNS_DIR, "memory_profile": rn.MEMORY_PROFILE_DEFAULT, "gate_filters": [], "note_kinds": []}
        self.config.update({k: v for k, v in config.items() if k in CONFIG_KEYS})
        self.config["runs_dir"] = os.path.abspath(self.config["runs_dir"] or rn.DEFAULT_RUNS_DIR)
        self.run_lock = threading.Lock()                                 # one model run at a time
        self.cfg_lock = threading.Lock()
        self.turns: List[Dict[str, Any]] = []
        self._key_cache: Tuple[float, Dict[str, Any]] = (0.0, {})

    # -- settings --------------------------------------------------------------------------------------------------
    def set_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(patch, dict):
            raise ServerError("the settings must be an object")
        reg = pl.registry()
        new = dict(self.config)
        for k, v in patch.items():
            if k not in CONFIG_KEYS:
                raise ServerError("unknown setting %r" % k)
            if k in LOCKED_KEYS:
                raise ServerError("%s can be set only on the command line of `vera run`" % k, "locked_setting", 403)
            if k in ("model", "base_url", "api_key_env", "docs", "store", "runs_dir", "temperature") and v in ("", None):
                new[k] = None if k != "runs_dir" else rn.DEFAULT_RUNS_DIR
                continue
            if k in ("model", "base_url", "api_key_env", "docs", "store", "runs_dir", "backend", "tool_choice", "evidence", "memory_profile") and not isinstance(v, str):
                raise ServerError("%s must be a string" % k)
            if k == "backend":
                if v not in reg.names("backend"):
                    raise ServerError("backend must be one of %s" % ", ".join(reg.names("backend")))
            elif k == "tool_choice":
                if v not in ("required", "auto"):
                    raise ServerError("tool_choice must be required or auto")
            elif k == "evidence":
                if v not in ("v1", "v2", "v3", "v4", "v5", "v6"):
                    raise ServerError("evidence must be v1 ... v6")
            elif k == "memory_profile":
                if v not in reg.names("memory_profile"):
                    raise ServerError("memory_profile must be one of %s" % ", ".join(reg.names("memory_profile")))
            elif k == "api_key_env":
                if not _ENV_RX.match(v):
                    raise ServerError("api_key_env is the NAME of an environment variable, not a key")
            elif k == "base_url":
                from urllib.parse import urlsplit as us
                u = us(v)
                if u.scheme not in ("http", "https") or not u.netloc or u.username or u.password or "@" in u.netloc:
                    raise ServerError("base_url must be an http(s) URL without credentials")
            elif k == "temperature":
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 2:
                    raise ServerError("temperature must be a number between 0 and 2")
            elif k in ("gate_filters", "note_kinds"):
                kind = "gate" if k == "gate_filters" else "note_kind"
                if not isinstance(v, list) or any(not isinstance(x, str) or reg.get(kind, x) is None for x in v):
                    raise ServerError("%s must be a list of installed %s plugins (%s)" % (k, kind, ", ".join(reg.names(kind))))
                if k == "gate_filters" and any(isinstance(reg.get("gate", x).obj, pl.LoomGate) for x in v):
                    raise ServerError("gate_filters takes filter plugins; the loom's gate is the evidence setting")
            elif k == "docs":
                if not os.path.exists(v):
                    raise ServerError("docs: no such file or folder")
            elif k in ("store", "runs_dir"):
                v = os.path.abspath(v)
            new[k] = v
        with self.cfg_lock:
            self.config = new
            self._key_cache = (0.0, {})
        return self.public_config()

    def public_config(self) -> Dict[str, Any]:
        return dict(self.config)

    def key_status(self) -> Dict[str, Any]:
        """For each provider: whether a key is present and where it comes from.  Never the value."""
        now = time.monotonic()
        if now - self._key_cache[0] < 5 and self._key_cache[1]:
            return self._key_cache[1]
        env = self.config.get("api_key_env")
        out = {}
        for prov in ("anthropic", "openai"):
            src = keys.key_source(prov, env)
            out[prov] = {"present": src is not None, "source": src, "env": [env] if env else list(keys.ENV_ORDER[prov]), "keychain": None if env else "%s / %s" % (keys.KEYCHAIN_SERVICE, prov)}
        self._key_cache = (now, out)
        return out

    def backend(self) -> Any:
        c = self.config
        return backend_factory(c["backend"], c["model"], c["base_url"], api_key_env=c["api_key_env"], tool_choice=c["tool_choice"], temperature=c["temperature"])

    # -- the run keys: a run folder under runs_dir, or a path inside the memory store -------------------------------
    def run_key(self, path: str) -> str:
        p = os.path.realpath(path)
        rd = os.path.realpath(self.config["runs_dir"])
        if p == rd or p.startswith(rd + os.sep):
            return "runs:" + os.path.relpath(p, rd)
        st = self.config.get("store")
        if st:
            sd = os.path.realpath(st)
            if p == sd or p.startswith(sd + os.sep):
                return "store:" + ("" if p == sd else os.path.relpath(p, sd))
        raise ServerError("a run outside runs_dir and the store", "bad_run", 400)

    def resolve_run(self, key: str) -> str:
        if not isinstance(key, str) or ":" not in key:
            raise ServerError("bad run key", "bad_run")
        where, rel = key.split(":", 1)
        base = self.config["runs_dir"] if where == "runs" else self.config.get("store") if where == "store" else None
        if not base:
            raise ServerError("bad run key", "bad_run")
        base = os.path.realpath(base)
        p = os.path.realpath(os.path.join(base, rel)) if rel else base
        if not (p == base or p.startswith(base + os.sep)) or not os.path.exists(p):
            raise ServerError("no such run", "bad_run", 404)
        return p


# ------------------------------------------------------------------------------------------------------------
# what the endpoints return
# ------------------------------------------------------------------------------------------------------------
def answer_view(ans: rn.Answer, app: App) -> Dict[str, Any]:
    """What the page may show of an Answer: the quote and its source sentences, or 「分かりません」 with the typed reason.  Nothing the model wrote as prose exists in an Answer."""
    d: Dict[str, Any] = {"status": ans.status, "text": ans.text, "sources": [dict({"text": s.get("text"), "source": s.get("source")}, **({"sourced": s["sourced"]} if s.get("sourced") is not None else {})) for s in ans.sources], "reason": ans.reason,
                         "reason_ja": rn.REASON_JA.get(ans.reason or "", ""), "verified": ans.verified, "free_text_dropped": ans.free_text_dropped, "backend": ans.backend,
                         "usage": ans.usage}
    det = {}
    for k in ("last_refusal", "contested_values", "contested", "turn", "status", "plugin", "annotations", "emit_refusals"):
        if ans.detail.get(k) is not None:
            det[k] = ans.detail[k]
    if ans.detail.get("error"):
        det["error"] = keys.redact(ans.detail["error"])
    d["detail"] = det
    try:
        d["run"] = app.run_key(ans.run_dir)
    except ServerError:
        d["run"] = None
    return d


def _short(v: Any, n: int = 140) -> str:
    s = json.dumps(v, ensure_ascii=False, sort_keys=True) if not isinstance(v, str) else v
    return s if len(s) <= n else s[: n - 1] + "…"


_CLOSED = {"tier": {"RUN", "WORD", "CHAR", "any"}, "type": {"no_record", "cannot_weave", "unknown", "contested"}, "kind": {"record", "constructed"}, "slot": {"の", "に", "で", "と", "を", "が", "は"}}


def safe_args(a: Any, key: str = "", depth: int = 0) -> Any:
    """The arguments of a model call as the trace may show them: integers, booleans and null as they are; a string only when it is one of a closed vocabulary for its key; every other string
    (the model chose it: a search text, a unit, a topic, free words) as `str:<first 8 hex of sha256>/<length>`.  A person never reads model-chosen text here."""
    if isinstance(a, (bool, int)) or a is None:
        return a
    if isinstance(a, float):
        return "float"
    if isinstance(a, str):
        if key in _CLOSED and a in _CLOSED[key]:
            return a
        return "str:%s/%d" % (hashlib.sha256(a.encode("utf-8")).hexdigest()[:8], len(a))
    if depth >= 3:
        return "…"
    if isinstance(a, list):
        return [safe_args(x, key, depth + 1) for x in a[:20]]
    if isinstance(a, dict):
        return {str(k)[:24] if isinstance(k, str) and re.match(r"^[A-Za-z_]{1,24}$", k) else "key": safe_args(v, k if isinstance(k, str) else "", depth + 1) for k, v in list(a.items())[:20]}
    return "?"


def trace_rows(ops_path: str) -> List[Dict[str, Any]]:
    """The operation trace of a ledger: one line per row, what was asked and what the structure answered.  Text of the RECORD (an emitted quote, a woven stretch) is shown; anything the MODEL
    chose is shown only as a hash and a length (`safe_args`); free text is only a hash and a length in the ledger itself."""
    out = []
    with open(ops_path, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            r = json.loads(ln)
            a, res, op = r.get("args") or {}, r.get("result") or {}, r.get("op")
            ok = res.get("ok")
            if op == "emit":
                what = ("「%s」" % res.get("text")) if ok else "refused: %s" % _short(safe_args(res.get("refusal") if isinstance(res.get("refusal"), str) and re.match(r"^[a-z_]{1,40}$", res.get("refusal")) else "?"), 100)
            elif op == "weave_span" and ok:
                what = "woven (record) 「%s」" % res.get("text")
            elif op == "free_text_dropped":
                what = "dropped %s chars (sha256 %s…)" % (a.get("chars"), str(a.get("sha256"))[:12])
            elif op == "user_turn":
                what = "user turn %s: %s" % (a.get("turn"), "str:%s/%d" % (hashlib.sha256(str(a.get("text")).encode("utf-8")).hexdigest()[:8], len(str(a.get("text")))))
            elif op == "harness_meta":
                shown = {k: v for k, v in a.items() if k not in ("agent_definition_sha", "plugins", "response_model", "requested_model")}
                declared = pl.parse_manifest(a.get("plugins")) if "plugins" in a else None
                if declared:
                    shown["plugins"] = ", ".join("%s/%s@%s" % (e["kind"], e["name"], e["version"]) for e in declared)
                if "response_model" in a:
                    shown["response_model"] = "(server claim, unverified)" if str(a["response_model"]).startswith("unverified:") else "matches the requested model"
                what = _short(shown, 300)
            elif ok is False:
                rf = res.get("refusal")
                what = "%s  →  refused: %s" % (_short(safe_args(a), 80), rf if isinstance(rf, str) and re.match(r"^[a-z_]{1,40}$", rf) else "?")
            else:
                what = _short(safe_args(a), 160)
            out.append({"i": r.get("i"), "actor": r.get("actor"), "op": op if isinstance(op, str) and re.match(r"^[a-z_]{1,32}$", op) else "?", "ok": ok, "what": what, "sha": r.get("sha"), "prev": r.get("prev"),
                        "session": os.path.basename(os.path.dirname(ops_path))})
    return out


def ledger_view(path: str) -> Dict[str, Any]:
    files = rn._ops_files(path, rn.kind_of(path))
    rows: List[Dict[str, Any]] = []
    for f in files:
        if os.path.isfile(f):
            rows += trace_rows(f)
    head = None
    hp = os.path.join(path, "HEAD")
    if os.path.isfile(hp):
        head = open(hp, encoding="utf-8").read().strip() or None
    return {"kind": rn.kind_of(path), "rows": rows, "head": head, "files": len(files)}


def hash_label(s: str) -> str:
    """A model-chosen label (a declared topic) shown as `str:<sha8>/<length>`: a person does not read model text there."""
    return "str:%s/%d" % (hashlib.sha256(str(s).encode("utf-8")).hexdigest()[:8], len(str(s)))


def memory_view(app: App) -> Dict[str, Any]:
    store = app.config.get("store")
    if not store or not os.path.isdir(os.path.join(store, "sessions")):
        return {"present": False}
    ms = mem.MemStore(store)
    rows = ms.rows()
    ix = ms.index()
    notes = []
    for n in ix.notes:
        sid = n.get("sid")
        cites = [e.get("sid") for e in (n.get("earlier") or []) if isinstance(e, dict)]
        notes.append({"type": n.get("type"), "sid": sid, "turn": n.get("turn"), "text": rows[sid]["sent"] if isinstance(sid, int) and 0 <= sid < len(rows) else None,
                      "earlier": [{"sid": c, "text": rows[c]["sent"]} for c in cites if isinstance(c, int) and 0 <= c < len(rows)], "relation": n.get("relation"), "reason": n.get("reason")})
    nests = [{"topic": hash_label(n.topic), "centre": hash_label(n.centre), "members": len(n.members)} for n in ix.nests]
    return {"present": True, "sentences": [{"sid": i, "turn": r.get("turn"), "text": r["sent"]} for i, r in enumerate(rows[:500])], "n_sentences": len(rows), "notes": notes, "nests": nests,
            "counts": {t: sum(1 for n in notes if n["type"] == t) for t in ("SAME_SEAT", "UPDATE", "REVERSAL_X", "ENUMERATION")}}


def position_view(app: App, run_path: str) -> Dict[str, Any]:
    """The crosses and nests of the position(s) an answer run asked about: the positions are read from the `recall` rows of the run's own ledger (a read of the record, no model, no new run)."""
    store = app.config.get("store")
    if not store or rn.kind_of(run_path) != "mem_answer":
        return {"positions": []}
    ms = mem.MemStore(store)
    ix = ms.index()
    seen: List[Any] = []
    for ln in open(os.path.join(run_path, "ops.jsonl"), encoding="utf-8"):
        if '"recall"' not in ln:
            continue
        r = json.loads(ln)
        if r.get("op") != "recall" or not (r.get("result") or {}).get("ok", True):
            continue
        res = r["result"]
        for g in (res.get("answers") or []) + (res.get("history") or []):
            for o in g.get("occurrences") or []:
                pos = o.get("position")
                if pos and [pos[0], pos[1], [list(x) for x in pos[2]]] not in seen:
                    seen.append([pos[0], pos[1], [list(x) for x in pos[2]]])
    out = []
    for pos in seen:
        position = mx._position(pos)
        c = ix.cross(position[0], position[1])
        hist = [{"value": e.value, "sid": e.sid, "kind": e.kind} for e in ix.history_full(position)]
        nests = [{"topic": hash_label(n.topic), "centre": hash_label(n.centre), "members": len(n.members)} for n in ix.nests if n.centre == position[1]]
        out.append({"position": pos, "text": mx.position_text(position), "cross": mx.render_cross(c) if c is not None else None, "history": hist, "nests": nests})
    return {"positions": out}


def list_runs(app: App) -> List[Dict[str, Any]]:
    rd = app.config["runs_dir"]
    out = []
    if os.path.isdir(rd):
        for n in sorted(os.listdir(rd), reverse=True):
            p = os.path.join(rd, n)
            if os.path.isfile(os.path.join(p, "ops.jsonl")) and os.path.isfile(os.path.join(p, "harness.json")):
                try:
                    h = json.load(open(os.path.join(p, "harness.json"), encoding="utf-8"))
                except (OSError, ValueError):
                    h = {}
                out.append({"run": "runs:" + n, "name": n, "kind": h.get("kind", "ask"), "backend": (h.get("backend") or {}).get("backend"), "model": (h.get("backend") or {}).get("model")})
    return out[:200]


# ------------------------------------------------------------------------------------------------------------
# the HTTP layer
# ------------------------------------------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "vera-run"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    app: App

    def log_message(self, fmt: str, *args: Any) -> None:               # no access log: paths and queries stay out of the terminal
        pass

    # -- plumbing -------------------------------------------------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str, extra: Optional[Dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, obj: Any) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, e: Exception) -> None:
        self.close_connection = True                                    # a request that failed may leave its body unread: do not reuse the connection
        if isinstance(e, ServerError):
            self._json(e.status, {"error": keys.redact(str(e)), "code": e.code})
        elif isinstance(e, (rn.HarnessError, BackendError, pl.PluginError)):
            self._json(400, {"error": keys.redact(e), "code": getattr(e, "code", "error")})
        elif isinstance(e, (Refuse, LedgerError, ValueError)):
            self._json(400, {"error": keys.redact(e), "code": type(e).__name__})
        else:
            self._json(500, {"error": "internal error (%s)" % type(e).__name__, "code": "internal"})

    def _host_ok(self, host: str) -> bool:
        """The Host header names this server: a loopback name or address (127.0.0.0/8, ::1, ::ffff:127.x, localhost) and this port."""
        port = self.server.server_address[1]
        m = re.match(r"^(\[[0-9A-Fa-f:.]+\]|[^:\[\]]+):(\d{1,5})$", host or "")
        if not m or int(m.group(2)) != port:
            return False
        h = m.group(1)
        return _loopback_ip(h[1:-1] if h.startswith("[") else h) is not None and (h.startswith("[") or ":" not in h)

    def _check_request(self, api: bool) -> None:
        host = self.headers.get("Host", "")
        if not self._host_ok(host):
            raise ServerError("unexpected Host header", "bad_host", 421)
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + host:
            raise ServerError("cross-origin request refused", "bad_origin", 403)
        if api:
            tok = self.headers.get(TOKEN_HEADER, "")
            if not secrets.compare_digest(tok.encode("utf-8"), self.app.token.encode("utf-8")):
                raise ServerError("missing or wrong token", "bad_token", 403)

    def _body(self) -> Dict[str, Any]:
        if (self.headers.get("Content-Type", "").split(";")[0].strip().lower()) != "application/json":
            raise ServerError("Content-Type must be application/json", "bad_content_type", 415)
        try:
            n = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise ServerError("Content-Length required", "length_required", 411) from None
        if n < 0 or n > MAX_BODY:
            raise ServerError("body too large", "too_large", 413)
        raw = self.rfile.read(n)
        try:
            obj = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            raise ServerError("body is not JSON") from None
        if not isinstance(obj, dict):
            raise ServerError("body must be a JSON object")
        return obj

    # -- verbs ----------------------------------------------------------------------------------------------------
    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        try:
            u = urlsplit(self.path)
            if u.path in ("/", "/index.html"):
                self._check_request(False)
                body, csp = render_page(self.app.token)
                return self._send(200, body, "text/html; charset=utf-8", {"Content-Security-Policy": csp, "X-Frame-Options": "DENY"})
            if u.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if not u.path.startswith("/api/"):
                raise ServerError("not found", "not_found", 404)
            self._check_request(True)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            self._json(200, self._get_api(u.path, q))
        except Exception as e:                                           # every failure is a typed JSON error, never a traceback to the client
            self._error(e)

    def do_POST(self) -> None:
        try:
            u = urlsplit(self.path)
            if not u.path.startswith("/api/"):
                raise ServerError("not found", "not_found", 404)
            self._check_request(True)
            self._json(200, self._post_api(u.path, self._body()))
        except Exception as e:
            self._error(e)

    def do_PUT(self) -> None:
        self._error(ServerError("method not allowed", "method_not_allowed", 405))

    do_DELETE = do_PATCH = do_PUT

    def do_OPTIONS(self) -> None:                                         # no CORS: a preflight is simply refused
        self._error(ServerError("method not allowed", "method_not_allowed", 405))

    # -- API ------------------------------------------------------------------------------------------------------
    def _get_api(self, path: str, q: Dict[str, str]) -> Any:
        app = self.app
        reg = pl.registry()
        if path == "/api/state":
            return {"version": __version__, "config": app.public_config(), "keys": app.key_status(), "turns": app.turns[-100:],
                    "choices": {"backend": reg.names("backend"), "gate_filters": [n for n in reg.names("gate") if not isinstance(reg.get("gate", n).obj, pl.LoomGate)],
                                "memory_profile": reg.names("memory_profile"), "note_kinds": reg.names("note_kind"), "evidence": ["v1", "v2", "v3", "v4", "v5", "v6"]},
                    "plugins": reg.listing(), "plugin_errors": reg.errors, "remote": False, "locked": list(LOCKED_KEYS)}
        if path == "/api/runs":
            return {"runs": list_runs(app)}
        if path == "/api/trace":
            p = app.resolve_run(q.get("run", ""))
            return ledger_view(p)
        if path == "/api/ledger":
            p = app.resolve_run(q.get("run", ""))
            return ledger_view(p)
        if path == "/api/memory":
            return memory_view(app)
        if path == "/api/position":
            return position_view(app, app.resolve_run(q.get("run", "")))
        raise ServerError("not found", "not_found", 404)

    def _post_api(self, path: str, body: Dict[str, Any]) -> Any:
        app = self.app
        if path == "/api/config":
            return {"config": app.set_config(body)}
        if path == "/api/verify":
            p = app.resolve_run(body.get("run", ""))
            return rn.verify_path(p)
        if path in ("/api/ask", "/api/say"):
            if not app.run_lock.acquire(blocking=False):
                raise ServerError("a run is in progress", "busy", 409)
            try:
                return self._run(path, body)
            finally:
                app.run_lock.release()
        raise ServerError("not found", "not_found", 404)

    def _run(self, path: str, body: Dict[str, Any]) -> Any:
        app = self.app
        c = dict(app.config)
        if path == "/api/say":
            msgs = body.get("messages")
            if not isinstance(msgs, list) or not msgs or len(msgs) > MAX_MESSAGES or any(not isinstance(m, str) or not m.strip() or len(m) > 2000 for m in msgs):
                raise ServerError("messages: a list of 1 to %d non-empty strings" % MAX_MESSAGES)
            if not c.get("store"):
                raise ServerError("set the memory store first", "no_store")
            r = rn.mem_say(c["store"], msgs, app.backend(), profile=c["memory_profile"])
            turn = {"id": len(app.turns), "mode": "say", "messages": [rn.redact_user_text(m)[0] for m in msgs], "session": r.session, "committed": r.committed, "ended": r.ended, "kept": r.messages, "redacted": r.redacted_turns, "lossy": r.lossy_turns,
                    "error": keys.redact(r.error) if r.error else None}
            app.turns.append(turn)
            return {"turn": turn}
        q = body.get("question")
        mode = body.get("mode", "docs")
        if not isinstance(q, str) or not q.strip() or len(q) > 256:
            raise ServerError("question: 1 to 256 characters")
        if mode == "docs":
            if not c.get("docs"):
                raise ServerError("set the documents (a folder or a file) first", "no_docs")
            ans = rn.ask(q, c["docs"], app.backend(), c["runs_dir"], evidence=c["evidence"], gate_filters=c["gate_filters"])
        elif mode == "memory":
            if not c.get("store"):
                raise ServerError("set the memory store first", "no_store")
            ans = rn.mem_ask(c["store"], q, app.backend(), profile=c["memory_profile"], gate_filters=c["gate_filters"], note_kinds=c["note_kinds"])
        else:
            raise ServerError("mode must be docs or memory")
        view = answer_view(ans, app)
        turn = {"id": len(app.turns), "mode": mode, "question": q, "answer": view}
        app.turns.append(turn)
        return {"turn": turn}


class VeraServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr: Tuple[str, int], handler: Any, app: App) -> None:
        self.app = app
        if ":" in addr[0]:
            import socket
            self.address_family = socket.AF_INET6
        super().__init__(addr, handler)


def make_server(host: str, port: int, app: App, allow_remote: bool = False) -> VeraServer:
    if allow_remote:
        raise ServerError("--allow-remote is not available in this version", "bind_refused", 2)
    host = check_bind(host)
    handler = type("BoundHandler", (Handler,), {"app": app})
    return VeraServer((host, port), handler, app)


def serve(host: str, port: int, config: Dict[str, Any], allow_remote: bool = False, on_ready: Optional[Callable[[VeraServer], None]] = None) -> int:
    app = App(config)
    srv = make_server(host, port, app, allow_remote)
    if on_ready:
        on_ready(srv)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0

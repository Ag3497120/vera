"""The runner: one question over documents (`ask`), a memory (`mem`), and the checks of a finished run (`verify`, `replay`).

Every path is the same shape: a backend (any of the three) is driven by the UNCHANGED loom drivers (verantyx.loom.driver / memdriver) over a loom or memory
server, so every operation of the model is one row of a hash-chained ledger and the only things the user is ever shown are

  * the text of a successful `emit` of a ledger that verifies and replays identically (a quote of the documents, with its source sentence), or
  * 「分かりません」 with the typed reason (the abstention type, the reason the run was abandoned, the last refusal of the gate).

Free text of the model is hashed (a `free_text_dropped` row) and dropped.  Nothing here prints a key.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from verantyx import __version__
from verantyx.harness import docs_corpus as dc
from verantyx.harness import keys, plugins as pl, prompting
from verantyx.harness.backends import Backend, BackendError, DriverClient
from verantyx.ledger_events import LedgerError
from verantyx.loom import driver as drv
from verantyx.loom import evidence as evl
from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memdriver as mdrv
from verantyx.loom import memory as mem
from verantyx.loom import memview as mview
from verantyx.loom.mcp import LoomServer
from verantyx.loom.state import Refuse

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUNS_DIR = "runs"
TASK_ID = "ask/1"
EVIDENCE_DEFAULT = "v6"
MEM_BUNDLE = mem.V4_VERSIONS_M6D                  # shape.v4 + qwords.v2 + ask.v3 (PUB-M6d); the answer run is memanswer.v17
MEM_ANSWER_VERSION = ma.ANSWER_V17
MEMORY_PROFILE_DEFAULT = "m6d-v17"                 # the built-in memory_profile plugin that is MEM_BUNDLE + MEM_ANSWER_VERSION
MEM_ANSWER_MAX_TURNS = 40
MEM_MAX_CALLS = mdrv.MAX_CALLS_PER_TURN_V3
REFUSAL_TEXT = "分かりません"

REASON_JA = {                                         # the typed reason, said in Japanese; the token stays visible
    "no_record": "文書にその答えが書かれていません",
    "cannot_weave": "文書に関係する記述はありますが、引用の形にできませんでした",
    "unknown": "判断できませんでした",
    "contested": "記録の中で答えが食い違っています",
    "max_turns": "モデルが規定の回数以内に答えを出せませんでした",
    "no_tool_call": "モデルが道具を使いませんでした",
    "api_error": "モデルの呼び出しに失敗しました",
    "cap_repeat": "モデルが同じ操作を繰り返したため止めました",
    "cap_status": "モデルが状態の確認を繰り返したため止めました",
    "done_without_close": "モデルが答えを出さずに終えました",
    "no_close": "モデルが答えを出さずに終えました",
    "run_not_verified": "台帳が検証できませんでした",
    "plugin_refused": "プラグインのゲートが答えを通しませんでした",
}


class HarnessError(Exception):
    """A typed refusal of the harness (`code` is a stable token)."""

    def __init__(self, msg: str, code: str = "harness_error") -> None:
        super().__init__("%s: %s" % (code, msg))
        self.code = code


# ------------------------------------------------------------------------------------------------------------
# plugins: which ran (recorded in the ledger), the gate filters (refuse only), the note kinds (read only)
# ------------------------------------------------------------------------------------------------------------
def _plugin(kind: str, name: str) -> "pl.Plugin":
    try:
        return pl.registry().require(kind, name)
    except pl.PluginError as e:
        raise HarnessError(str(e), e.code) from e


def resolve_plugins(backend: Any, *, evidence: Optional[str] = None, filters: Sequence[str] = (), profile: Optional[str] = None, note_kinds: Sequence[str] = ()) -> Dict[str, Any]:
    """The plugins one run uses: {"used": [Plugin], "filters": [Plugin], "profile": MemoryProfile | None, "notes": [Plugin], "manifest": str}.  The backend and the built-in gate / profile are
    recorded as plugins too (registered the same way); a backend object that no plugin of that name stands behind (an embedder's own) is simply not listed."""
    reg = pl.registry()
    used: List[pl.Plugin] = []
    b = reg.get("backend", getattr(backend, "name", ""))
    if b is not None:
        used.append(b)
    if evidence and evidence != "off":
        used.append(_plugin("gate", "evidence.%s" % evidence))
    flt = [_plugin("gate", n) for n in filters]
    for f in flt:
        if isinstance(f.obj, pl.LoomGate):
            raise HarnessError("gate %s is one of the loom's evidence versions: select it with --evidence; --gate-filter takes a filter plugin" % f.name, "bad_plugin")
    used += flt
    prof = None
    if profile:
        pp = _plugin("memory_profile", profile)
        used.append(pp)
        prof = pp.obj
    notes = [_plugin("note_kind", n) for n in note_kinds]
    used += notes
    return {"used": used, "filters": flt, "profile": prof, "notes": notes, "manifest": pl.manifest(used)}


def apply_filters(ans: "Answer", filters: Sequence["pl.Plugin"]) -> "Answer":
    """Run the gate filters on an answered Answer; the first that refuses turns it into 「分かりません」 (reason plugin_refused).  A filter can only refuse."""
    if ans.status != "answered" or not filters:
        return ans
    hit = pl.apply_gate_filters(ans.question, ans.text or "", ans.sources, filters)
    if hit is None:
        return ans
    p, code = hit
    ans.status, ans.reason, ans.text, ans.sources, ans.output_sha = "refused", "plugin_refused", None, [], None
    ans.detail["plugin"] = {"kind": p.kind, "name": p.name, "version": p.version, "code": code}
    return ans


def annotate_memory(store: str, notes: Sequence["pl.Plugin"]) -> List[Dict[str, Any]]:
    """The notes of the note-kind plugins over the committed sentences of a memory (read only; a failing plugin yields one `error` note, never an exception)."""
    out: List[Dict[str, Any]] = []
    if not notes:
        return out
    rows = _store_rows(store)
    for p in notes:
        fn = getattr(p.obj, "annotate", None)
        if fn is None:
            continue
        try:
            got = list(fn(rows))
        except Exception as e:
            out.append({"kind": p.name, "version": p.version, "error": type(e).__name__})
            continue
        for n in got:
            if isinstance(n, dict) and isinstance(n.get("sid"), int) and isinstance(n.get("text"), str):
                out.append({"kind": p.name, "version": p.version, "sid": n["sid"], "text": n["text"][:300]})
    return out


def _store_rows(store: str) -> List[dict]:
    try:
        return mem.MemStore(store).rows()
    except Exception:
        return []


# ------------------------------------------------------------------------------------------------------------
# the tool schemas of the loom (the SAME ones the MCP door serves)
# ------------------------------------------------------------------------------------------------------------
def loom_tool_objects() -> List[Any]:
    """Objects with `name`, `description`, `inputSchema` for driver.api_tools: the schemas the FastMCP door of the loom serves.  Read from the bundled snapshot
    (`loom_tools.json`; a test compares it with the live door), so `vera ask` needs no MCP SDK."""
    with open(os.path.join(HERE, "loom_tools.json"), encoding="utf-8") as f:
        return [SimpleNamespace(name=t["name"], description=t["description"], inputSchema=t["inputSchema"]) for t in json.load(f)]


def live_loom_tool_objects(tmp_dir: str) -> List[Any]:
    """The tools of the live FastMCP door (needs the `mcp` extra); used by the test that pins the snapshot."""
    from verantyx.loom import mcp as lm
    tasks = os.path.join(tmp_dir, "tasks.jsonl")
    corpus = os.path.join(tmp_dir, "corpus.jsonl")
    with open(corpus, "w", encoding="utf-8") as f:
        f.write(json.dumps({"sha": "0" * 64, "title": "t", "sent": "テスト。", "source": "t#0"}, ensure_ascii=False) + "\n")
    with open(tasks, "w", encoding="utf-8") as f:
        f.write(json.dumps({"task_id": "x/1", "text": "q", "lang": "prose", "mode": "record_only", "corpus": corpus}) + "\n")
    m = lm.build(tasks, os.path.join(tmp_dir, "runs"))
    if m is None:
        raise HarnessError("the MCP SDK is not installed", "mcp_missing")
    return list(asyncio.run(m.list_tools()))


# ------------------------------------------------------------------------------------------------------------
# results
# ------------------------------------------------------------------------------------------------------------
@dataclass
class Answer:
    """What the user is shown.  `status`: answered | refused.  An answer has `text` (the quote) and `sources` (the sentences it was quoted from);
    a refusal has `reason` (a typed token) and `detail`."""
    status: str
    run_dir: str
    question: str
    text: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    output_sha: Optional[str] = None
    reason: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    backend: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, int] = field(default_factory=dict)
    free_text_dropped: int = 0

    def to_obj(self) -> dict:
        return {k: getattr(self, k) for k in ("status", "run_dir", "question", "text", "sources", "output_sha", "reason", "detail", "verified", "backend", "usage", "free_text_dropped")}

    def render(self) -> str:
        """The text printed for a person: the quote and its source sentence, or 「分かりません」 and the typed reason; then the run directory."""
        lines: List[str] = []
        if self.status == "answered":
            lines.append("答え: 「%s」" % self.text)
            for s in self.sources:
                lines.append("根拠: %s（%s）" % (s["text"], s["source"]))
        else:
            ja = REASON_JA.get(self.reason or "", "")
            lines.append("%s（理由: %s%s）" % (REFUSAL_TEXT, self.reason, "、%s" % ja if ja else ""))
            for k in ("last_refusal",):
                if self.detail.get(k):
                    lines.append("最後の拒否: %s" % self.detail[k])
            if self.detail.get("plugin"):
                lines.append("プラグイン: %s/%s %s（%s）" % (self.detail["plugin"]["kind"], self.detail["plugin"]["name"], self.detail["plugin"]["version"], self.detail["plugin"]["code"]))
        lines.append("run: %s" % self.run_dir)
        return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------
# ask: a question over documents
# ------------------------------------------------------------------------------------------------------------
def new_run_id(question: str, corpus_sha: str, prefix: str = "ask") -> str:
    h = hashlib.sha256((question + "\0" + corpus_sha + "\0" + str(time.time_ns())).encode("utf-8")).hexdigest()[:6]
    return "%s-%s-%s" % (prefix, time.strftime("%Y%m%d-%H%M%S", time.gmtime()), h)


def _write_once(path: str, data: bytes) -> None:
    if os.path.exists(path):
        if open(path, "rb").read() != data:
            raise HarnessError("a file of this name holds other bytes: %s" % path, "corpus_conflict")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _ledger_rows(run_dir: str) -> List[dict]:
    lines, _ = lg.read_lines(run_dir)
    return [json.loads(ln) for ln in lines]


def _sources_of(row: dict, sents: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    out = []
    for ev in row["result"].get("evidence") or []:
        sid = ev.get("sid")
        if isinstance(sid, int) and 0 <= sid < len(sents):
            out.append({"sid": sid, "source": sents[sid]["source"], "text": sents[sid]["sent"], "clause": ev.get("clause")})
    return out


def settle(run_dir: str, question: str, sents: Sequence[Dict[str, str]], corpus_path: str) -> Answer:
    """The Answer of a finished loom run, from its VERIFIED ledger only (`ledger.emitted_output`: chain + replay must be OK)."""
    o = lg.emitted_output(run_dir, corpus_path=corpus_path)
    rows = _ledger_rows(run_dir)
    dropped = sum(1 for r in rows if r["actor"] == "harness" and r["op"] == "free_text_dropped")
    if o["status"] == "emitted":
        emit = [r for r in rows if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok") is True][0]
        return Answer("answered", run_dir, question, text=o["text"], sources=_sources_of(emit, sents), output_sha=o["output_sha"], verified=True, free_text_dropped=dropped)
    if o["status"] == "run_not_verified":
        return Answer("refused", run_dir, question, reason="run_not_verified", detail={"verify": o.get("verify"), "problems": o.get("problems")}, verified=False, free_text_dropped=dropped)
    reason, detail = "no_close", {}
    for r in rows:
        if r["actor"] == "model" and r["op"] == "abstain" and r["result"].get("ok") is True:
            reason = r["result"].get("type") or "unknown"
        elif r["actor"] == "harness" and r["op"] == "abandoned":
            reason = r["args"].get("reason", "no_close")
    refusals = [r for r in rows if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok") is False]
    if refusals:
        res = refusals[-1]["result"]
        codes = []
        for rf in (res.get("detail") or {}).get("refusals", []):
            for w in rf.get("weaves", []) or []:
                codes += w.get("codes", [])
        detail["last_refusal"] = "/".join([res.get("refusal", "")] + sorted(set(codes)))
        detail["emit_refusals"] = len(refusals)
    return Answer("refused", run_dir, question, reason=reason, detail=detail, verified=True, free_text_dropped=dropped)


def ask(question: str, docs: str, backend: Backend, runs_dir: str = DEFAULT_RUNS_DIR, *, evidence: str = EVIDENCE_DEFAULT, run_id: Optional[str] = None,
        max_turns: Optional[int] = None, gate_filters: Sequence[str] = ()) -> Answer:
    """One question over documents.  A record_only loom task with the evidence gate (`evidence.v6` by default)."""
    question = (question or "").strip()
    if not question:
        raise HarnessError("the question is empty", "bad_question")
    backend.ready()
    plug = resolve_plugins(backend, evidence=evidence, filters=gate_filters)
    try:
        data, sents = dc.build_corpus(docs)
    except dc.DocsError as e:
        raise HarnessError(str(e), e.code) from e
    sha = dc.corpus_sha(data)
    runs_dir = os.path.abspath(runs_dir)
    corpus_path = os.path.join(runs_dir, "_corpora", sha[:16] + ".jsonl")
    _write_once(corpus_path, data)
    task = {"task_id": TASK_ID, "text": question, "lang": "prose", "mode": "record_only", "corpus": corpus_path}
    try:
        srv = LoomServer([task], runs_dir, evidence=evidence)
    except ValueError as e:
        raise HarnessError(str(e), "bad_task") from e
    rid = run_id or new_run_id(question, sha)
    model = backend.model
    begun = srv.begin(TASK_ID, model, rid)
    if not begun.get("ok"):
        raise HarnessError("begin refused: %s" % json.dumps(begun, ensure_ascii=False, sort_keys=True), "begin_refused")
    system = prompting.loom_prompt()
    meta = {"driver": "L2-api", "requested_model": model, "agent_definition_sha": prompting.sha(system)}
    if plug["used"]:
        meta["plugins"] = plug["manifest"]
    srv.harness(rid, "harness_meta", meta)
    choice, strict = backend.tool_choice()
    tools = drv.api_tools(loom_tool_objects(), strict, False)
    client = DriverClient(backend)
    t0 = time.monotonic_ns()
    res = drv.run_episode(client, srv, rid, model, system, drv.first_message(begun), tools, tool_choice=choice, max_turns=max_turns or drv.MAX_TURNS["prose"])
    wall = time.monotonic_ns() - t0
    rm = getattr(backend, "last_response_model", None)
    if isinstance(rm, str) and rm:
        srv.harness(rid, "harness_meta", {"response_model": rm[:200]})
    if srv.closed(rid) is None:
        srv.harness(rid, "abandoned", {"reason": "no_close"})
    run_dir = str(srv.run_dir(rid))
    local_corpus = os.path.join(run_dir, "corpus.jsonl")                # beside the ledger, so that `verify` / `replay` find the corpus wherever the folder goes
    _write_once(local_corpus, data)
    rep = res.to_obj()
    if rep.get("error"):
        rep["error"] = keys.redact(rep["error"])
    info = {"harness": "vera-harness %s" % __version__, "kind": "ask", "backend": backend.describe(), "question_chars": len(question), "evidence": evidence,
            "corpus_sha256": sha, "sentences": len(sents), "docs": docs if not os.path.isabs(docs) else os.path.basename(docs.rstrip("/")),
            "plugins": [x.ref() for x in plug["used"]], "system_prompt_sha256": prompting.sha(system), "tools": [t["name"] for t in tools], "driver_report": rep, "wall_driver_ns": wall}
    with open(os.path.join(run_dir, "harness.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    ans = apply_filters(settle(run_dir, question, sents, local_corpus), plug["filters"])
    ans.backend = backend.describe()
    ans.usage = dict(res.usage)
    if res.error:
        ans.detail["error"] = keys.redact(res.error)
    return ans


# ------------------------------------------------------------------------------------------------------------
# verify / replay of any run folder
# ------------------------------------------------------------------------------------------------------------
def kind_of(path: str) -> str:
    """'loom' (a run folder with ops.jsonl and meta.json), 'mem_answer' (an answer run of a memory store), 'mem_store' (a memory store) or 'unknown'."""
    p = os.path.abspath(path)
    if os.path.isfile(os.path.join(p, "ops.jsonl")):
        try:
            meta = json.load(open(os.path.join(p, "meta.json"), encoding="utf-8"))
        except (OSError, ValueError):
            return "unknown"
        return "mem_answer" if meta.get("mode") == "memory_answer" else "loom"
    if os.path.isdir(os.path.join(p, "sessions")) or os.path.isfile(os.path.join(p, "memory.jsonl")):
        return "mem_store"
    return "unknown"


def _corpus_of(run_dir: str) -> Optional[str]:
    c = os.path.join(run_dir, "corpus.jsonl")
    return c if os.path.isfile(c) else None


def _corpus_mismatch(run_dir: str, corpus_path: Optional[str]) -> Optional[str]:
    """A typed mismatch when the corpus beside the ledger is not the bytes the run began on (checked before anything parses it): the begin row records its sha256."""
    if corpus_path is None:
        return None
    try:
        with open(os.path.join(run_dir, "ops.jsonl"), encoding="utf-8") as f:
            want = json.loads(f.readline())["result"]["header"]["corpus_sha"]
        got = hashlib.sha256(open(corpus_path, "rb").read()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        return "corpus_unreadable"
    return None if got == want else "corpus_sha_mismatch"


def _ops_files(path: str, kind: str) -> List[str]:
    p = os.path.abspath(path)
    if kind in ("loom", "mem_answer"):
        return [os.path.join(p, "ops.jsonl")]
    out: List[str] = []
    for sub in ("sessions", "answers"):
        d = os.path.join(p, sub)
        if os.path.isdir(d):
            out += [os.path.join(d, n, "ops.jsonl") for n in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, n, "ops.jsonl"))]
    return out


def plugin_mismatch(path: str, kind: Optional[str] = None) -> Optional[str]:
    """The plugins a run folder / store DECLARES (the `plugins` key of its harness_meta rows, inside the hash chain) against the registry: None if every one is installed at the declared
    version, else `unknown_plugin:<kind>/<name>`, `plugin_version:...` or `plugins_malformed`.  A run that declares nothing (older runs) has no mismatch."""
    k = kind or kind_of(path)
    for f in _ops_files(path, k):
        try:
            with open(f, encoding="utf-8") as fh:
                for ln in fh:
                    if '"harness_meta"' not in ln or '"plugins"' not in ln:
                        continue
                    row = json.loads(ln)
                    if row.get("op") != "harness_meta" or "plugins" not in row.get("args", {}):
                        continue
                    declared = pl.parse_manifest(row["args"]["plugins"])
                    if declared is None:
                        return "plugins_malformed"
                    mm = pl.mismatch(declared)
                    if mm:
                        return mm
        except (OSError, ValueError):
            continue
    return None


def verify_path(path: str) -> dict:
    """The chain, then the replay, of a run folder or a memory store: {"kind", "status", ...}.  status "OK" or a typed failure (TAMPERED, TORN_TAIL, REPLAY_DIFFERS, ...).
    A run that declares a plugin which is not installed (or at another version) is not OK: status REPLAY_INPUTS_MISMATCH, replay.status INPUTS, replay.mismatch the token."""
    v = _verify_base(path)
    if v["status"] == "OK":
        mm = plugin_mismatch(path, v["kind"])
        if mm:
            v = dict(v, status="REPLAY_INPUTS_MISMATCH", replay={"status": "INPUTS", "mismatch": mm})
    return v


def _verify_base(path: str) -> dict:
    k = kind_of(path)
    if k == "loom":
        cp = _corpus_of(path)
        chain = lg.verify_chain(path)
        mm = _corpus_mismatch(path, cp) if chain["status"] == "OK" else None
        if mm:
            return {"kind": k, "status": "REPLAY_INPUTS_MISMATCH", "rows": chain.get("n"), "head": chain.get("head"), "replay": {"status": "INPUTS", "mismatch": mm}, "problems": None}
        try:
            v = lg.verify(path, corpus_path=cp)
        except (KeyError, ValueError, OSError) as e:
            return {"kind": k, "status": "REPLAY_INPUTS_MISMATCH", "rows": chain.get("n"), "head": chain.get("head"), "replay": {"status": "INPUTS", "mismatch": "corpus_unreadable"},
                    "problems": [{"error": type(e).__name__}]}
        return {"kind": k, "status": v["status"], "rows": v.get("n"), "head": v.get("head"), "replay": v.get("replay"), "problems": v.get("problems")}
    if k == "mem_answer":
        store = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        v = ma.verify_answer(path, store)
        return {"kind": k, "status": v["status"], "rows": v.get("n"), "head": v.get("head"), "replay": v.get("replay"), "problems": v.get("problems")}
    if k == "mem_store":
        v = mem.verify_store(path, mem.FROM_HEADER)
        out = {"kind": k, "status": v["status"], "sessions": v.get("sessions"), "sentences": v.get("sentences"), "replay": v.get("replay"), "problems": v.get("problems")}
        adir = os.path.join(path, "answers")
        if v["status"] == "OK" and os.path.isdir(adir):
            bad = []
            n = 0
            for a in sorted(os.listdir(adir)):
                n += 1
                va = ma.verify_answer(os.path.join(adir, a), path)
                if va["status"] != "OK":
                    bad.append({"answer": a, "status": va["status"]})
            out["answers"] = n
            if bad:
                out["status"], out["problems"] = "ANSWER_NOT_VERIFIED", bad
        return out
    return {"kind": "unknown", "status": "NOT_A_RUN", "problems": [{"path": path}]}


def replay_path(path: str) -> dict:
    """Re-execute the run from its inputs and compare every row byte for byte: {"kind", "status": IDENTICAL | DIFFERS | INPUTS, "rows", "text", ...}.  INPUTS also when a declared
    plugin is not installed at the declared version: the replay would not be a replay of the same conditions."""
    r = _replay_base(path)
    if r.get("status") == "IDENTICAL":
        mm = plugin_mismatch(path, r.get("kind"))
        if mm:
            r = dict(r, status="INPUTS", identical=False, mismatch=mm)
    return r


def _replay_base(path: str) -> dict:
    k = kind_of(path)
    if k == "loom":
        cp = _corpus_of(path)
        mm = _corpus_mismatch(path, cp)
        if mm:
            return {"kind": k, "status": "INPUTS", "identical": False, "rows": None, "mismatch": mm}
        try:
            r = lg.replay(path, corpus_path=cp)
        except (KeyError, ValueError, OSError):
            return {"kind": k, "status": "INPUTS", "identical": False, "rows": None, "mismatch": "corpus_unreadable"}
    elif k == "mem_answer":
        r = ma.replay_answer(path, os.path.dirname(os.path.dirname(os.path.abspath(path))))
    elif k == "mem_store":
        r = mem.replay_store(path, mem.FROM_HEADER)
        return {"kind": k, "status": r.status, "identical": bool(r.identical), "detail": r.to_obj()}
    else:
        return {"kind": "unknown", "status": "NOT_A_RUN"}
    out = {"kind": k, "status": r.status, "identical": bool(r.identical), "rows": r.n_rows}
    if r.mismatch:
        out["mismatch"] = r.mismatch
    if r.first_diff:
        out["first_diff"] = r.first_diff
    if getattr(r, "text", None) is not None:
        out["text"] = r.text
    return out


# ------------------------------------------------------------------------------------------------------------
# mem: a memory that answers only with what it was told, and says so when two things were told
# ------------------------------------------------------------------------------------------------------------
MEM_GUIDANCE = ("1 回に事実を 1 つ、1 文で書いてください（例: 「広報の担当は山本」）。カンマでつないだ複数の事実や言い訳は、答えの根拠として使われません。"
                " One fact per message, one sentence ('X の Y は A'): a value written together with other statements is never used as an answer.")


def mem_intro(door: Any, budget: int) -> str:
    n = door.begin_result["header"]["session_no"]
    head = ("This is session %d of the memory in this store. It is a NEW conversation: you remember nothing of the earlier ones except through your tools.\n"
            "The result of begin (the rules, your tools and caps) follows; the first message of the session comes after it. Tool results are cut after %d characters per turn.\n"
            % (n, budget))
    return head + json.dumps(door.intro(), ensure_ascii=False, sort_keys=True)


def mem_first_question_message(begin_result: dict) -> str:
    return drv.first_message(begin_result)


def _store_head(store: str) -> Optional[dict]:
    return mem.MemStore(store).head()


@dataclass
class MemSessionResult:
    session: int
    run_id: str
    messages: int
    committed: bool
    ended: str
    reports: List[Any] = field(default_factory=list)
    turns_without_report: List[str] = field(default_factory=list)
    store: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    free_text_dropped: int = 0
    error: Optional[str] = None


def mem_say(store: str, messages: Sequence[str], backend: Backend, *, budget: int = mview.BUDGET_DEFAULT, speaker: str = "user", profile: str = MEMORY_PROFILE_DEFAULT) -> MemSessionResult:
    """One story session: the messages arrive one at a time, the model keeps what matters through `write` (one fact per write) and ends every turn with `report`.
    The session is committed to the store only if it completed."""
    msgs = [m.strip() for m in messages if m and m.strip()]
    if not msgs:
        raise HarnessError("no message to remember", "no_message")
    backend.ready()
    model = backend.model
    plug = resolve_plugins(backend, profile=profile)
    door = md.StructureDoor(store, "notes", model, profile=plug["profile"].profile, versions=dict(plug["profile"].versions), view=mview.make_view(budget))
    wd = mview.BudgetDoor(door, budget, ledger=True)
    door.harness(None, "harness_meta", {"plugins": plug["manifest"]})
    choice, strict = backend.tool_choice()
    tools = md.api_tools(door.tool_names, strict)
    sn = door.begin_result["header"]["session_no"]
    turns = [("%d-%d" % (sn, i + 1), "[%d-%d] %s: %s" % (sn, i + 1, speaker, m)) for i, m in enumerate(msgs)]
    client = DriverClient(backend)
    try:
        res = mdrv.run_story_session(client, wd, model, prompting.mem_story_prompt(), mem_intro(wd, budget), turns, tools, tool_choice=choice, max_calls=MEM_MAX_CALLS,
                                     force_report=True, caps=drv.RUNAWAY_CAPS_V1)
        committed = res.ended == "complete"
        if committed:
            wd.commit()
        ledger_dir = str(door.session.ledger.dir)
    finally:
        door.close()
    rows = [lg._parse_line(ln) for ln in lg.read_raw_lines(ledger_dir)[0]]
    return MemSessionResult(session=sn, run_id=door.run_id, messages=len(msgs), committed=committed, ended=res.ended, reports=md.reports_of(rows),
                            turns_without_report=[t["turn"] for t in res.turns if t["report"] is None], store=store, usage=dict(res.usage),
                            free_text_dropped=res.text_blocks_dropped, error=keys.redact(res.error) if res.error else None)


def mem_ask(store: str, question: str, backend: Backend, *, budget: int = mview.BUDGET_DEFAULT, profile: str = MEMORY_PROFILE_DEFAULT, gate_filters: Sequence[str] = (),
            note_kinds: Sequence[str] = ()) -> Answer:
    """One question over the committed memory: an answer run over a snapshot (memanswer.v17).  The answer is a quote of a remembered sentence, `contested` when two
    answers were told and nobody replaced one, or 「分かりません」."""
    question = (question or "").strip()
    if not question:
        raise HarnessError("the question is empty", "bad_question")
    store = os.path.abspath(store)
    backend.ready()
    plug = resolve_plugins(backend, filters=gate_filters, profile=profile, note_kinds=note_kinds)
    try:
        snap = ma.write_snapshot(store, topics=False, crosses=True, versions=True)
    except Refuse as r:
        return Answer("refused", store, question, reason=r.type, detail=dict(r.detail), verified=True, backend=backend.describe())
    model = backend.model
    qd = md.AnswerDoor(store, "notes", question, model, snapshot=snap, answer_version=plug["profile"].answer_version)
    qd.harness(None, "harness_meta", {"plugins": plug["manifest"]})
    wd = mview.BudgetDoor(qd, budget, ledger=False)
    choice, strict = backend.tool_choice()
    tools = md.api_tools(qd.tool_names, strict, done=True)
    client = DriverClient(backend)
    res = drv.run_episode(client, wd, qd.run_id, model, prompting.mem_question_prompt(), mem_first_question_message(qd.begin_result), tools, tool_choice=choice,
                          max_turns=MEM_ANSWER_MAX_TURNS, caps=drv.RUNAWAY_CAPS_V1)
    run_dir = str(qd.session.ledger.dir)
    out = qd.output()
    ans = Answer("refused", run_dir, question, backend=backend.describe(), usage=dict(res.usage), free_text_dropped=res.text_blocks_dropped)
    if out.get("status") == "emitted":
        ans.status, ans.text, ans.output_sha, ans.verified = "answered", out["text"], out.get("output_sha"), True
        ans.sources = _mem_sources(store, snap, out)
    elif out.get("status") == "abstained":
        ans.reason, ans.verified = out.get("type") or "unknown", True
        if out.get("type") == "contested":
            choice_ = [r for r in out.get("recalls", []) if r["verdict"] == "CHOICE"]
            ans.detail["contested_values"] = [g[0] for g in choice_[-1]["answers"]] if choice_ else []
    else:
        ans.reason = "run_not_verified" if out.get("status") == "run_not_verified" else (res.ended if res.ended not in ("closed", "done") else "no_close")
        ans.verified = out.get("status") != "run_not_verified"
    if res.error:
        ans.detail["error"] = keys.redact(res.error)
    ans = apply_filters(ans, plug["filters"])
    notes = annotate_memory(store, plug["notes"])
    if notes:
        ans.detail["annotations"] = notes
    return ans


def _mem_sources(store: str, snap: dict, out: dict) -> List[Dict[str, Any]]:
    """The remembered sentences that contain the answer (a lookup in the snapshot, not a model's claim)."""
    try:
        _, rows = ma.read_snapshot(snap["path"])
    except (OSError, Refuse, ValueError):
        return []
    text = out.get("text") or ""
    found = []
    for i, r in enumerate(rows):
        s = r.get("sent") or r.get("text") or ""
        if text and text in s:
            found.append({"sid": i, "source": r.get("source") or "", "text": s})
    return found[:3]

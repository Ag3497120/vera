#!/usr/bin/env python
"""Generate short definition sentences for the words the placement has no evidence
for (W3-a2).  Sub-commands:

  needs      list the words that lack direct evidence, most frequent first
  run        send the words in batches to ``codex exec`` (parallel, resumable)
  collect    assemble definitions.jsonl from the ledger (deterministic)
  summarize  count calls, batches, time and cost from the ledger
  prompt     print the prompt template and its sha256

What a generated definition IS: a sentence a model wrote when asked.  It is not a
testimony from the material.  Every row carries its origin (``generated``, the
model, the effort, the batch id) and the placement keeps it apart from the
Wikipedia and corpus evidence (an arm of its own, ``gen_definition``).

``run`` is the only place that calls a model, and only through ``--codex-bin``
(required, no default: a test must never reach the real executable by accident).
The batches, the ledger (append-only), the retries and the call cap are all kept
here; ``stdin`` of the child is closed (``codex exec`` waits on stdin otherwise).
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

MODEL, EFFORT, TIER = "gpt-6-luna", "low", "priority"
ALLOWED_ITEMS = {"agent_message", "reasoning"}
BENIGN_ERRORS = ("Falling back from WebSockets to HTTPS transport",)
EXIT_OK, EXIT_LIST_CHANGED, EXIT_INTERRUPTED = 0, 3, 130

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["items"],
          "properties": {"items": {"type": "array", "items": {
              "type": "object", "additionalProperties": False,
              "required": ["word", "definition", "hypernym"],
              "properties": {"word": {"type": "string"},
                             "definition": {"type": ["string", "null"]},
                             "hypernym": {"type": ["string", "null"]}}}}}}

PROMPT_HEAD = """あなたは日本語の辞書の編集者です。下の WORDS_JSON の各語について、辞書の見出しのような短い定義文を 1 文と、その語が何の一種かを表す上位語を 1 つ答えてください。

規則:
- definition は「<語>は<上位語>である。」または「<語>は<…>の一種である。」の形の 1 文にする。
- hypernym は名詞 1 つ（その語が何の一種か）。
- 語に複数の意味があるときは、いちばん一般的な意味を 1 つだけ選ぶ。
- 語として意味が分からない、断片で語にならない、綴りから何も判断できないものは、definition と hypernym の両方を null にする。無理に作らない。
- ファイルを読まない。コマンドを実行しない。ネットワークを使わない。道具を使わず、あなたの知識だけで答える。
- items は入力の語と同じ順で、語ごとに 1 件ずつ。word には入力の語をそのまま入れる。

"""
WORDS_PREFIX = "WORDS_JSON: "


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def build_prompt(words: Sequence[str]) -> str:
    return PROMPT_HEAD + WORDS_PREFIX + json.dumps(list(words), ensure_ascii=False) + "\n"


def prompt_template_sha256() -> str:
    """sha256 of the fixed part of the prompt (the word line aside)."""
    return sha256_text(PROMPT_HEAD + WORDS_PREFIX)


# =====================================================================================
# needs: the words that lack direct evidence
# =====================================================================================
def select_needs(placement: str, n: int):
    """The headwords whose state is UNPLACED or MULTIPLE, most frequent first.

    The ONLY criterion is the frequency ``n_seen`` (how often the word occurs as a
    content word in the material, summed over the sources: a sum made to rank the
    words, not a vote for a type).  Every word with the same frequency as the
    ``n``-th is included (ties are never cut by order); within one frequency the
    words are listed in string order (for display only).  The frozen test data are
    not read and not consulted."""
    dbp = os.path.join(placement, "placement.sqlite")
    con = sqlite3.connect("file:%s?mode=ro" % dbp, uri=True)
    try:
        rows = con.execute(
            "SELECT word, ns, state, kind, n_seen FROM headwords "
            "WHERE state IN ('UNPLACED','MULTIPLE')").fetchall()
        rows.sort(key=lambda r: (-r[4], r[0]))
        if len(rows) > n:
            boundary = rows[n - 1][4]
            rows = [r for r in rows if r[4] >= boundary]
        else:
            boundary = rows[-1][4] if rows else None
        out = []
        for rank, (word, ns, state, kind, freq) in enumerate(rows, 1):
            if state == "MULTIPLE":
                status = "SPLIT"
            else:
                has = con.execute(
                    "SELECT 1 FROM evidence WHERE word=? AND arm!='ns_vote' LIMIT 1",
                    (word,)).fetchone()
                status = "BELOW_THRESHOLD" if has else "NO_EVIDENCE"
            out.append({"rank": rank, "word": word, "freq": freq, "state": state,
                        "ns": ns, "kind": kind, "evidence_status": status})
    finally:
        con.close()
    return out, boundary


def cmd_needs(args) -> int:
    rows, boundary = select_needs(args.placement, args.n)
    mpath = os.path.join(args.placement, "manifest.json")
    manifest = json.load(open(mpath, encoding="utf-8"))
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {
        "placement": os.path.abspath(args.placement),
        "content_sha256": manifest.get("content_sha256"),
        "rule": ("headwords with state UNPLACED or MULTIPLE (nouns, predicates and NP alike), "
                 "ordered by n_seen descending; every word whose n_seen equals that of the "
                 "n-th is included; display order inside one frequency = string order; "
                 "n_seen is a sum used only to rank, never a vote for a type; "
                 "no test data is read"),
        "n_requested": args.n,
        "total": len(rows),
        "boundary_freq": boundary,
        "n_at_boundary": sum(1 for r in rows if r["freq"] == boundary),
        "last_freq": rows[-1]["freq"] if rows else None,
        "by_state": dict(collections.Counter(r["state"] for r in rows)),
        "by_ns": dict(collections.Counter(r["ns"] for r in rows)),
        "by_kind": dict(collections.Counter(r["kind"] for r in rows)),
        "by_evidence_status": dict(collections.Counter(r["evidence_status"] for r in rows)),
        "out": os.path.abspath(args.out),
        "out_sha256": sha256_file(args.out),
    }
    with open(args.meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({k: meta[k] for k in ("total", "boundary_freq", "n_at_boundary")},
                     ensure_ascii=False))
    return 0


# =====================================================================================
# batches and the ledger
# =====================================================================================
def make_batches(words: Sequence[str], size: int) -> List[dict]:
    out = []
    for i in range(0, len(words), size):
        ws = list(words[i:i + size])
        sha = sha256_text(json.dumps(ws, ensure_ascii=False))
        idx = i // size
        out.append({"index": idx, "id": "b%05d_%s" % (idx, sha[:12]), "words_sha": sha,
                    "words": ws})
    return out


def read_needs_words(path: str) -> List[str]:
    out = []
    seen = set()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        w = json.loads(line)["word"]
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def read_ledger(path: str) -> List[dict]:
    """The ledger's events.  A last line cut off by a kill is ignored."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            if i < len(lines) - 2:
                raise
    return out


class Ledger:
    """Append-only; every line is flushed and fsynced; one writer at a time."""

    def __init__(self, path: str):
        self.path = path
        self._f = open(path, "a", encoding="utf-8")
        self._lock = threading.Lock()

    def write(self, ev: dict) -> None:
        line = json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n"
        with self._lock:
            self._f.write(line)
            self._f.flush()
            os.fsync(self._f.fileno())

    def close(self) -> None:
        self._f.close()


def ledger_state(events: Sequence[dict]):
    """(starts per batch id, ok batch ids, total start events)."""
    starts: Dict[str, int] = collections.Counter()
    ok = set()
    n = 0
    for e in events:
        if e["ev"] == "start":
            starts[e["batch"]] += 1
            n += 1
        elif e["ev"] == "end" and e.get("status") == "ok":
            ok.add(e["batch"])
    return starts, ok, n


# =====================================================================================
# one call
# =====================================================================================
def parse_output(batch_words: Sequence[str], data) -> Tuple[Dict[str, Tuple[Optional[str], Optional[str]]], dict]:
    """The answers of one batch.  A word that is not in the batch is dropped (counted
    ``foreign``); a word that comes back more than once is NOT taken (counted
    ``dup_dropped``: a tie is not settled by order); a batch word that does not come
    back is ``missing``."""
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("NO_ITEMS")
    inb = set(batch_words)
    seen: Dict[str, list] = collections.defaultdict(list)
    foreign = 0
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("word"), str):
            foreign += 1
            continue
        w = it["word"]
        if w not in inb:
            foreign += 1
            continue
        d, h = it.get("definition"), it.get("hypernym")
        seen[w].append((d if isinstance(d, str) else None, h if isinstance(h, str) else None))
    answers = {}
    dup = 0
    for w in batch_words:
        got = seen.get(w)
        if not got:
            continue
        if len(got) > 1:
            dup += 1
            continue
        answers[w] = got[0]
    missing = sum(1 for w in batch_words if w not in seen)
    abstained = sum(1 for d, h in answers.values() if d is None and h is None)
    return answers, {"foreign": foreign, "dup_dropped": dup, "missing": missing,
                     "abstained": abstained, "answered": len(answers)}


def run_one(cmd: List[str], cwd: str, timeout: float, procs: set, plock: threading.Lock,
            stop: threading.Event):
    """Run one codex call.  Returns (exit, sec, stdout, stderr, timed_out)."""
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, start_new_session=True)
    with plock:
        procs.add(p)
    timed_out = False
    try:
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                p.kill()
            out, err = p.communicate()
    finally:
        with plock:
            procs.discard(p)
    return p.returncode, round(time.time() - t0, 3), out or "", err or "", timed_out


def judge(exit_code, stdout: str, stderr: str, out_path: str, batch_words, timed_out, interrupted):
    """(status, reason, n_items, n_missing, extra) for one finished call."""
    if interrupted:
        return "interrupted", "STOPPED", None, None, {}
    if timed_out:
        return "timeout", "TIMEOUT", None, None, {}
    items = collections.Counter()
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        it = (e.get("item") or {}).get("type") if isinstance(e, dict) else None
        if it == "error" and ((e.get("item") or {}).get("message") or "").startswith(BENIGN_ERRORS):
            continue
        if it:
            items[it] += 1
    tools = {k: v for k, v in items.items() if k not in ALLOWED_ITEMS and k != "error"}
    if tools:
        return "tool_use", "TOOL_USE:" + ",".join(sorted(tools)), None, None, {}
    if exit_code != 0:
        return "failed", "EXIT_%s" % exit_code, None, None, {}
    try:
        data = json.load(open(out_path, encoding="utf-8"))
    except (OSError, ValueError):
        return "bad_output", "NO_OR_BAD_JSON", None, None, {}
    try:
        _ans, st = parse_output(batch_words, data)
    except ValueError as e:
        return "bad_output", str(e), None, None, {}
    return "ok", None, len(data["items"]), st["missing"], st


# =====================================================================================
# run
# =====================================================================================
def cmd_run(args) -> int:
    words = read_needs_words(args.needs)
    batches = make_batches(words, args.batch_size)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(os.path.join(out_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "work", "empty"), exist_ok=True)
    ledger_path = os.path.join(out_dir, "ledger.jsonl")
    bpath = os.path.join(out_dir, "batches.json")
    events = read_ledger(ledger_path)
    by_index = {b["index"]: b for b in batches}
    # the list of words must be the one the ledger and the batch file were made from
    for e in events:
        if e["ev"] != "start":
            continue
        idx = int(e["batch"][1:6])
        b = by_index.get(idx)
        if b is None or b["words_sha"] != e["words_sha"]:
            print(json.dumps({"state": "NEEDS_LIST_CHANGED", "batch": e["batch"]}))
            return EXIT_LIST_CHANGED
    if os.path.exists(bpath):
        old = json.load(open(bpath, encoding="utf-8"))
        if [b["id"] for b in old["batches"]] != [b["id"] for b in batches]:
            print(json.dumps({"state": "NEEDS_LIST_CHANGED", "batches_file": bpath}))
            return EXIT_LIST_CHANGED
    meta = {"batch_size": args.batch_size, "max_retries": args.max_retries,
            "max_calls": args.max_calls, "slots": args.slots, "model": MODEL, "effort": EFFORT,
            "needs": os.path.abspath(args.needs), "needs_sha256": sha256_file(args.needs),
            "prompt_template_sha256": prompt_template_sha256()}
    with open(bpath, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "batches": [
            {"index": b["index"], "id": b["id"], "words_sha": b["words_sha"], "n": len(b["words"])}
            for b in batches]}, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    schema_path = os.path.join(out_dir, "schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(SCHEMA, f, ensure_ascii=False, sort_keys=True)
    empty = os.path.join(out_dir, "work", "empty")

    starts, ok, total_calls = ledger_state(events)
    calls_before = total_calls
    limit = 1 + args.max_retries
    todo = [b for b in batches if b["id"] not in ok and starts[b["id"]] < limit]
    if args.limit_batches is not None:
        todo = todo[:args.limit_batches]
    pending = collections.deque(todo)
    state = {"calls": total_calls, "inflight": 0, "capped": False, "deadline_hit": False}
    cond = threading.Condition()
    stop = threading.Event()
    procs: set = set()
    plock = threading.Lock()
    ledger = Ledger(ledger_path)
    t_start = time.time()
    deadline = t_start + args.deadline_sec if args.deadline_sec else None

    def handler(signum, frame):
        stop.set()
        with plock:
            for p in list(procs):
                try:
                    p.terminate()
                except OSError:
                    pass
        with cond:
            cond.notify_all()

    old_handlers = []
    if threading.current_thread() is threading.main_thread():
        for sg in (signal.SIGTERM, signal.SIGINT):
            old_handlers.append((sg, signal.signal(sg, handler)))

    def claim():
        """Take the next batch and book the call (cap checked inside the lock)."""
        with cond:
            while True:
                if stop.is_set():
                    return None
                if deadline is not None and time.time() >= deadline:
                    state["deadline_hit"] = True
                    return None
                if pending:
                    if state["calls"] >= args.max_calls:
                        state["capped"] = True
                        return None
                    b = pending.popleft()
                    state["calls"] += 1
                    state["inflight"] += 1
                    starts[b["id"]] += 1
                    return b, starts[b["id"]]
                if state["inflight"] == 0:
                    return None
                cond.wait(0.2)

    def worker():
        while True:
            got = claim()
            if got is None:
                return
            b, attempt = got
            out_path = os.path.join(out_dir, "raw", "%s.a%d.last.json" % (b["id"], attempt))
            prompt = build_prompt(b["words"])
            argv = [args.codex_bin, "exec", "-m", MODEL,
                    "-c", "model_reasoning_effort=" + json.dumps(EFFORT),
                    "-c", "service_tier=" + json.dumps(TIER),
                    "-s", "read-only", "--skip-git-repo-check", "--ephemeral",
                    "--disable", "browser_use", "--disable", "computer_use",
                    "--disable", "apps"]
            for kv in args.extra_config or []:
                argv += ["-c", kv]
            argv += ["-C", empty, "--output-schema", schema_path, "--json", "-o", out_path]
            ledger.write({"ev": "start", "batch": b["id"], "attempt": attempt,
                          "words_sha": b["words_sha"], "words": b["words"],
                          "prompt_sha256": sha256_text(prompt), "argv": argv, "t": now_utc()})
            try:
                code, sec, out, err, timed_out = run_one(argv + [prompt], empty, args.timeout,
                                                         procs, plock, stop)
                status, reason, n_items, n_missing, st = judge(
                    code, out, err, out_path, b["words"], timed_out,
                    stop.is_set() and code not in (0,))
            except OSError as e:               # the executable could not be started
                code, sec, err = None, 0.0, str(e)
                status, reason, n_items, n_missing, st = "failed", "OSERROR", None, None, {}
            outsha = sha256_file(out_path) if os.path.exists(out_path) else None
            ledger.write({"ev": "end", "batch": b["id"], "attempt": attempt, "exit": code,
                          "sec": sec, "status": status, "reason": reason, "n_items": n_items,
                          "n_missing": n_missing, "out_path": out_path if outsha else None,
                          "out_sha256": outsha, "stderr_tail": (err or "")[-300:],
                          "t": now_utc()})
            with cond:
                state["inflight"] -= 1
                if status not in ("ok", "interrupted") and starts[b["id"]] < limit:
                    pending.append(b)           # a retry goes to the back of the line
                cond.notify_all()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.slots)]
    for t in threads:
        t.start()
    for t in threads:
        while t.is_alive():
            t.join(0.5)
    ledger.close()
    for sg, h in old_handlers:
        signal.signal(sg, h)
    events = read_ledger(ledger_path)
    starts, ok, total_calls = ledger_state(events)
    print(json.dumps({"state": "INTERRUPTED" if stop.is_set() else "DONE",
                      "calls_total": total_calls, "calls_this_run": total_calls - calls_before,
                      "batches": len(batches), "batches_ok": len(ok),
                      "capped": state["capped"], "deadline_hit": state["deadline_hit"],
                      "wall_sec": round(time.time() - t_start, 1)}, ensure_ascii=False))
    return EXIT_INTERRUPTED if stop.is_set() else EXIT_OK


# =====================================================================================
# collect / summarize
# =====================================================================================
def _first_ok(events: Sequence[dict]) -> Dict[str, dict]:
    """batch id -> its first ``ok`` end event."""
    out: Dict[str, dict] = {}
    for e in events:
        if e["ev"] == "end" and e.get("status") == "ok" and e["batch"] not in out:
            out[e["batch"]] = e
    return out


def _batch_words(events: Sequence[dict]) -> Dict[Tuple[str, int], List[str]]:
    out = {}
    for e in events:
        if e["ev"] == "start":
            out[(e["batch"], e["attempt"])] = e["words"]
    return out


def cmd_collect(args) -> int:
    ledger_path = os.path.join(args.out_dir, "ledger.jsonl")
    events = read_ledger(ledger_path)
    firsts = _first_ok(events)
    words_of = _batch_words(events)
    lines = []
    bad = []
    for bid in sorted(firsts):
        e = firsts[bid]
        words = words_of[(bid, e["attempt"])]
        path = e["out_path"]
        if not path or not os.path.exists(path) or sha256_file(path) != e["out_sha256"]:
            bad.append({"batch": bid, "reason": "OUTPUT_FILE_CHANGED_OR_MISSING"})
            continue
        answers, _st = parse_output(words, json.load(open(path, encoding="utf-8")))
        for w in words:
            if w not in answers:
                continue            # missing or duplicated: no row (not an abstention)
            d, h = answers[w]
            lines.append(json.dumps({
                "word": w, "definition": d, "hypernym": h, "abstained": d is None and h is None,
                "provenance": {"origin": "generated", "model": MODEL, "effort": EFFORT,
                               "batch_id": bid, "attempt": e["attempt"],
                               "out_sha256": e["out_sha256"]}}, ensure_ascii=False) + "\n")
    with open(args.out, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(json.dumps({"state": "COLLECTED", "rows": len(lines), "bad": bad,
                      "out_sha256": sha256_file(args.out)}, ensure_ascii=False))
    return 0 if not bad else 4


def _ts(s: str) -> float:
    return datetime.datetime.fromisoformat(s).timestamp()


def summarize(out_dir: str) -> dict:
    events = read_ledger(os.path.join(out_dir, "ledger.jsonl"))
    bf = os.path.join(out_dir, "batches.json")
    bmeta = json.load(open(bf, encoding="utf-8")) if os.path.exists(bf) else {"meta": {}, "batches": []}
    meta = bmeta["meta"]
    limit = 1 + int(meta.get("max_retries", 2))
    starts, ok, calls = ledger_state(events)
    firsts = _first_ok(events)
    words_of = _batch_words(events)
    ids = [b["id"] for b in bmeta["batches"]] or sorted(starts)
    reasons = collections.Counter()
    for e in events:
        if e["ev"] == "end" and e.get("status") != "ok":
            reasons[e["status"]] += 1
    failed = [i for i in ids if i not in ok and starts[i] >= limit]
    pending = [i for i in ids if i not in ok and starts[i] < limit]
    words_req = sum(len(words_of[(i, 1)]) for i in ids if (i, 1) in words_of)
    ans = abst = miss = dup = foreign = 0
    for bid, e in firsts.items():
        path = e["out_path"]
        words = words_of[(bid, e["attempt"])]
        _a, st = parse_output(words, json.load(open(path, encoding="utf-8")))
        ans += st["answered"]
        abst += st["abstained"]
        miss += st["missing"]
        dup += st["dup_dropped"]
        foreign += st["foreign"]
    t_starts = [_ts(e["t"]) for e in events if e["ev"] == "start"]
    t_ends = [_ts(e["t"]) for e in events if e["ev"] == "end"]
    sum_call = round(sum(e.get("sec") or 0 for e in events if e["ev"] == "end"), 1)
    wall = round(max(t_ends) - min(t_starts), 1) if t_starts and t_ends else None
    capped = calls >= int(meta.get("max_calls", 10 ** 9))
    return {
        "model": MODEL, "effort": EFFORT, "slots": meta.get("slots"),
        "batch_size": meta.get("batch_size"), "max_calls": meta.get("max_calls"),
        "max_retries": meta.get("max_retries"),
        "calls": calls, "batches_total": len(ids), "batches_ok": len(ok & set(ids)),
        "batches_failed": len(failed),
        "not_run_cap": len(pending) if capped else 0,
        "not_run_other": 0 if capped else len(pending),
        "ok_rate": round(len(ok & set(ids)) / len(ids), 4) if ids else None,
        "words_requested": words_req, "words_answered": ans, "words_abstained": abst,
        "words_missing": miss, "words_dup_dropped": dup, "words_foreign_dropped": foreign,
        "wall_sec": wall, "sum_call_sec": sum_call,
        "calls_per_word_requested": round(calls / words_req, 5) if words_req else None,
        "calls_per_word_answered": round(calls / ans, 5) if ans else None,
        "end_status": dict(collections.Counter(
            e["status"] for e in events if e["ev"] == "end")),
        "failure_reasons": dict(reasons),
        "ledger_sha256": sha256_file(os.path.join(out_dir, "ledger.jsonl"))
        if os.path.exists(os.path.join(out_dir, "ledger.jsonl")) else None,
        "prompt_template_sha256": meta.get("prompt_template_sha256"),
    }


def cmd_summarize(args) -> int:
    s = summarize(args.out_dir)
    text = json.dumps(s, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if args.out == "/dev/stdout":
        sys.stdout.write(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(text, end="")
    return 0


def cmd_prompt(args) -> int:
    print(PROMPT_HEAD + WORDS_PREFIX + '["<語>", ...]')
    print("template_sha256 " + prompt_template_sha256())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("needs")
    n.add_argument("--placement", required=True)
    n.add_argument("--n", type=int, default=60000)
    n.add_argument("--out", required=True)
    n.add_argument("--meta", required=True)
    r = sub.add_parser("run")
    r.add_argument("--needs", required=True)
    r.add_argument("--out-dir", required=True)
    r.add_argument("--codex-bin", required=True, help="path of the codex executable (no default)")
    r.add_argument("--batch-size", type=int, default=40)
    r.add_argument("--slots", type=int, default=12)
    r.add_argument("--max-calls", type=int, default=2000)
    r.add_argument("--max-retries", type=int, default=2)
    r.add_argument("--timeout", type=float, default=900)
    r.add_argument("--deadline-sec", type=float, default=None)
    r.add_argument("--limit-batches", type=int, default=None)
    r.add_argument("--extra-config", action="append", default=[])
    c = sub.add_parser("collect")
    c.add_argument("--out-dir", required=True)
    c.add_argument("--out", required=True)
    s = sub.add_parser("summarize")
    s.add_argument("--out-dir", required=True)
    s.add_argument("--out", required=True)
    sub.add_parser("prompt")
    args = ap.parse_args(argv)
    if args.cmd == "run" and (args.slots < 1 or args.slots > 12):
        ap.error("--slots must be 1..12")
    return {"needs": cmd_needs, "run": cmd_run, "collect": cmd_collect,
            "summarize": cmd_summarize, "prompt": cmd_prompt}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

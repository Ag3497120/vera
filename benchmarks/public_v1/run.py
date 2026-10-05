"""1 系を流す: python -m benchmarks.public_v1.run --system Ap|A|B|C|D --model qwen3.5:4b --out DIR [--placement P] [--port N]

DIR/<system>/results.jsonl（id・rep 昇順）と meta.json を書く。温度 0・think:false・num_predict 256・直列。乱数なし。
C/D は docset ごとに `vera serve` を 1 回起こす（5 回）。Z（常に棄権）は呼び出しなし（score が作る）。
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import time

from . import bm25, data as D, prompts, systems as S

DEFAULT_MODEL = {"Ap": "qwen3.8:27b-mlx", "A": "qwen3.5:4b", "B": "qwen3.5:4b", "C": "qwen3.5:4b", "D": "qwen3.5:4b"}
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCSET_ORDER = ["S1", "S2", "S3", "S4", "SM"]
MAX_TOKENS = 256


def now():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def build_request(system, q):
    """-> (messages, extra)。B だけ BM25 で選んだ文。A'・A・C・D は docset の全文。"""
    sents = D.docset_sentences(q["docset"])
    if system == "B":
        chosen, info = bm25.select(sents, q["question"])
        return prompts.build_messages(chosen, q["question"]), {"bm25": info}
    return prompts.build_messages(sents, q["question"]), {}


def _row_base(system, q, rep, messages, extra):
    r = {"system": system, "id": q["id"], "rep": rep, "cat": q["cat"], "docset": q["docset"],
         "messages_sha256": prompts.messages_sha256(messages)}
    r.update(extra)
    return r


def run_llm_row(system, q, rep, a):
    messages, extra = build_request(system, q)
    r = _row_base(system, q, rep, messages, extra)
    t = time.perf_counter()
    res = S.llm_call(a.backend, a.llm_url, a.model, messages, a.timeout, MAX_TOKENS, a.api_key)
    r["wall_ms"] = round((time.perf_counter() - t) * 1000, 1)
    r.update({"ok": bool(res.get("ok")), "error": res.get("error"), "text": res.get("content"), "usage": res.get("usage") or {}})
    return r


def run_vera_row(srv, system, q, rep, a):
    messages, extra = build_request(system, q)
    r = _row_base(system, q, rep, messages, extra)
    body = {"model": a.model, "messages": messages, "max_tokens": MAX_TOKENS, "vera": {"request_kind": "factual", "human_present": False}}
    t = time.perf_counter()
    try:
        status, resp = srv.chat(body, timeout=a.timeout)
        err = None
    except Exception as exc:
        status, resp, err = None, {}, {"type": "HTTP_ERROR", "detail": "%s: %s" % (type(exc).__name__, exc)}
    r["wall_ms"] = round((time.perf_counter() - t) * 1000, 1)
    text = None
    try:
        text = resp["choices"][0]["message"]["content"]
    except Exception:
        if err is None:
            err = {"type": "BAD_RESPONSE", "detail": json.dumps(resp, ensure_ascii=False)[:200]}
    r.update({"ok": err is None and isinstance(text, str), "error": err, "text": text, "usage": resp.get("usage") or {},
              "http_status": status, "vera": resp.get("vera"), "rss_kb": srv.rss_kb()})
    return r


def select_questions(a):
    qs = D.load_questions()
    out = []
    for ds in DOCSET_ORDER:
        if a.only_docset and ds != a.only_docset:
            continue
        sel = sorted((q for q in qs if q["docset"] == ds), key=lambda q: q["id"])
        if a.limit is not None:
            sel = sel[:a.limit]
        out.append((ds, sel))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m benchmarks.public_v1.run")
    ap.add_argument("--system", required=True, choices=["Ap", "A", "B", "C", "D"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--placement", default=None, help="C/D 必須（配置のディレクトリ）")
    ap.add_argument("--port", type=int, default=S.FIRST_PORT)
    ap.add_argument("--only-docset", default=None, choices=DOCSET_ORDER)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--backend", default="ollama", choices=["ollama", "openai"], help="Ap だけ openai を選べる（本走行では使っていない）")
    ap.add_argument("--api-base", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--ollama-url", default=S.OLLAMA_URL)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--scratch", default=None, help="C/D の store・server.log の置き場（ツリーの外）")
    ap.add_argument("--force", action="store_true", help="既存の results.jsonl を上書きする")
    a = ap.parse_args(argv)
    a.model = a.model or DEFAULT_MODEL[a.system]
    if a.backend == "openai" and a.system != "Ap":
        print("--backend openai は --system Ap だけ", file=sys.stderr)
        return 2
    if a.backend == "openai" and not a.api_base:
        print("--backend openai には --api-base が要る", file=sys.stderr)
        return 2
    a.llm_url = a.api_base if a.backend == "openai" else a.ollama_url
    if a.system in ("C", "D") and not a.placement:
        print("--placement が要る（C/D は配置 r9 などを渡す）", file=sys.stderr)
        return 2
    outdir = os.path.join(a.out, a.system)
    res_path = os.path.join(outdir, "results.jsonl")
    if os.path.exists(res_path) and os.path.getsize(res_path) > 0 and not a.force:
        print("既存の結果を上書きしない: " + res_path, file=sys.stderr)
        return 2
    os.makedirs(outdir, exist_ok=True)
    plan = select_questions(a)
    scratch = a.scratch
    if a.system in ("C", "D"):
        import tempfile
        scratch = scratch or tempfile.mkdtemp(prefix="w14-vera-")
        os.makedirs(scratch, exist_ok=True)
    frozen = os.path.join(D.DATA, "FROZEN.json")
    meta = {"system": a.system, "model": a.model, "backend": a.backend, "started": now(), "git_head": S.git_head(REPO),
            "data_frozen_sha256": hashlib.sha256(open(frozen, "rb").read()).hexdigest() if os.path.exists(frozen) else None,
            "model_digest": S.model_digest(a.ollama_url, a.model), "placement": a.placement, "strict": a.system == "D",
            "ports": {}, "uptime_start": S.uptime_line(), "ollama_ps_start": S.ollama_ps(a.ollama_url),
            "only_docset": a.only_docset, "limit": a.limit, "max_tokens": MAX_TOKENS, "think": False, "temperature": 0,
            "verantyx_files": sorted(m.__file__ for n, m in sys.modules.items() if n.startswith("verantyx") and getattr(m, "__file__", None))}
    n_rows = 0
    n_fail = 0
    first_done = False
    with open(res_path, "w", encoding="utf-8") as out:
        def emit(r):
            nonlocal n_rows, n_fail
            out.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            out.flush()
            n_rows += 1
            n_fail += 0 if r["ok"] else 1
        for ds, sel in plan:
            if not sel:
                continue
            if a.system in ("C", "D"):
                port = S.pick_port(a.port + len(meta["ports"]))
                meta["ports"][ds] = port
                files = [D.doc_path(fn) for fn in D.docset_files(ds)]
                store = os.path.join(scratch, ds, "store.json")
                os.makedirs(os.path.dirname(store), exist_ok=True)
                argv_s = S.vera_argv(sys.executable, store, a.model, port, a.placement, a.ollama_url, files, a.system == "D")
                with S.VeraServer(REPO, argv_s, os.path.join(scratch, ds, "server.log")) as srv:
                    for q in sel:
                        for rep in D.reps_for(q):
                            emit(run_vera_row(srv, a.system, q, rep, a))
                            if not first_done:
                                meta["ollama_ps_after_first"] = S.ollama_ps(a.ollama_url)
                                first_done = True
                    meta.setdefault("server_argv", {})[ds] = argv_s
            else:
                for q in sel:
                    for rep in D.reps_for(q):
                        emit(run_llm_row(a.system, q, rep, a))
                        if not first_done:
                            meta["ollama_ps_after_first"] = S.ollama_ps(a.ollama_url)
                            first_done = True
            print("%s %s done rows=%d fail=%d" % (a.system, ds, n_rows, n_fail), flush=True)
    meta.update({"ended": now(), "rows": n_rows, "failures": n_fail, "uptime_end": S.uptime_line(), "ollama_ps_end": S.ollama_ps(a.ollama_url)})
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote %s (%d rows, %d failures)" % (res_path, n_rows, n_fail))
    return 0


if __name__ == "__main__":
    sys.exit(main())

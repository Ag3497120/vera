"""`vera`: the command line of Vera Harness.

  vera ask --docs DIR|FILE "質問" [--backend anthropic|openai|json --model M --base-url U]
        a question over documents: the answer is a quote with its source sentence, or 「分かりません」 with the typed reason; then the run directory
  vera mem --store DIR [--say TEXT ...] [--ask QUESTION ...] [--backend ...]
        a memory: facts are kept one per write; a question is answered by a quote of what was kept, `contested` when two answers were told, or 「分かりません」
  vera mcp [--docs DIR --question Q ... | --tasks FILE | --mode memory --store DIR] [--runs-dir D]
        a stdio MCP server that makes Vera the only exit of an agent
  vera run [--port 3090]   the local web UI on 127.0.0.1 (conversation, trace, ledger + Verify, memory notes, settings)
  vera plugins       the installed plugins (entry point group vera.plugins)
  vera verify RUN    the hash chain, then the replay (exit 0 only when both are OK)
  vera replay RUN    re-execute the run and compare every row byte for byte (exit 0 identical)
  vera eval [--quick]   re-measure the safety claims offline on the shipped eval sets; exit 1 if a safety number is worse than the frozen record
  vera loom ...      low-level loom commands (mcp | replay | verify | output | note | close | demo)

Keys: environment (ANTHROPIC_API_KEY, VERA_OPENAI_API_KEY / OPENAI_API_KEY) or the macOS Keychain.  A key is never printed or recorded.
Exit codes: 0 ok / answered, 1 refused (「分かりません」) or not verified, 2 error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, List, Optional, Sequence

from verantyx import __version__
from verantyx.harness import keys
from verantyx.harness import runner as rn
from verantyx.harness.backends import BackendError, make_backend
from verantyx.harness import loom_cli
from verantyx.harness.evalrun import EvalError
from verantyx.harness.plugins import PluginError
from verantyx.harness import server as srv
from verantyx.ledger_events import LedgerError
from verantyx.loom.state import Refuse

# tests and embedders replace this to hand the backends a fake client; the default builds the real SDK client lazily
backend_factory: Callable[..., Any] = make_backend


def _add_backend_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend", default="anthropic", help="anthropic (Messages API), openai (any OpenAI-compatible server: DeepSeek, Ollama, LM Studio, vLLM, MLX), json (no tool calling: the model answers with a JSON array of ops), or a backend plugin (`vera plugins`)")
    p.add_argument("--model", default=None, help="model id (required for openai and json; default claude-haiku-5-5 for anthropic)")
    p.add_argument("--base-url", dest="base_url", default=None, help="OpenAI-compatible server, e.g. http://127.0.0.1:11434/v1 (Ollama), http://127.0.0.1:1234/v1 (LM Studio), https://api.deepseek.com")
    p.add_argument("--api-key-env", dest="api_key_env", default=None, help="name of the environment variable that holds the key (default: the provider's usual ones, then the macOS Keychain)")
    p.add_argument("--tool-choice", dest="tool_choice", choices=("required", "auto"), default="required", help="required: force tool calling (default); auto for a server that rejects it (the driver still forwards only tool calls)")
    p.add_argument("--temperature", type=float, default=None, help="sampling temperature sent to an OpenAI-compatible server (default: the server's)")


def _backend(args: argparse.Namespace) -> Any:
    return backend_factory(args.backend, args.model, args.base_url, api_key_env=args.api_key_env, tool_choice=args.tool_choice, temperature=args.temperature)


def _emit(args: argparse.Namespace, ans: rn.Answer) -> None:
    if getattr(args, "json", False):
        print(json.dumps(ans.to_obj(), ensure_ascii=False, sort_keys=True))
    else:
        print(ans.render())


def cmd_ask(args: argparse.Namespace) -> int:
    ans = rn.ask(" ".join(args.question), args.docs, _backend(args), args.runs_dir, evidence=args.evidence, gate_filters=args.gate_filter or ())
    _emit(args, ans)
    return 0 if ans.status == "answered" else 1


def cmd_mem(args: argparse.Namespace) -> int:
    backend = _backend(args)
    store = os.path.abspath(args.store)
    said: List[str] = list(args.say or [])
    asks: List[str] = list(args.ask or [])
    rc = 0

    def flush(pending: List[str]) -> None:
        if not pending:
            return
        r = rn.mem_say(store, pending, backend, profile=args.memory_profile)
        print("記憶: %d 件を session %d に渡しました（%s%s）" % (r.messages, r.session, "保存" if r.committed else "保存されず: %s" % r.ended, "、報告なしの回 %s" % ",".join(r.turns_without_report) if r.turns_without_report else ""))
        if r.error:
            print("  エラー: %s" % r.error, file=sys.stderr)
        pending.clear()

    def question(q: str) -> None:
        nonlocal rc
        a = rn.mem_ask(store, q, backend, profile=args.memory_profile, gate_filters=args.gate_filter or (), note_kinds=args.note_kind or ())
        if getattr(args, "json", False):
            print(json.dumps(a.to_obj(), ensure_ascii=False, sort_keys=True))
        elif a.status == "answered":
            print("答え: 「%s」" % a.text)
            for s in a.sources:
                print("根拠: %s" % s["text"])
        elif a.reason == "plugin_refused":
            print(a.render().splitlines()[0])
        elif a.reason == "contested":
            vals = a.detail.get("contested_values") or []
            print("%s（理由: contested、%s%s）" % (rn.REFUSAL_TEXT, rn.REASON_JA["contested"], "： " + " / ".join("「%s」" % v for v in vals) if vals else ""))
        else:
            print(a.render().splitlines()[0])
        for n in a.detail.get("annotations") or []:
            print("注記[%s]: %s" % (n["kind"], n.get("text", n.get("error"))))
        if a.status != "answered":
            rc = 1

    if said or asks:
        flush(said)
        for q in asks:
            question(q)
        print("store: %s" % store)
        return rc
    # interactive: lines are facts to keep; a line that starts with ? / ？ is a question (the pending facts are kept first); an empty line or EOF ends
    print(rn.MEM_GUIDANCE, file=sys.stderr)
    pending: List[str] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line[0] in "?？":
            flush(pending)
            question(line[1:].strip())
        else:
            pending.append(line)
    flush(pending)
    print("store: %s" % store)
    return rc


def cmd_mcp(args: argparse.Namespace) -> int:
    from verantyx.harness import mcp_server as ms
    if args.mode == "memory":
        if not args.store:
            raise rn.HarnessError("--mode memory needs --store", "no_store")
        return ms.serve_memory(args.store, args.phase, args.model or "mcp-client", args.question[0] if args.question else None)
    if args.tasks:
        return ms.serve_loom(args.tasks, args.runs_dir, args.evidence, allow_roots=args.allow_root or ())
    if args.docs:
        tasks = ms.prepare_doc_tasks(args.docs, args.question or [], args.runs_dir)
        return ms.serve_loom(tasks, args.runs_dir, args.evidence)
    raise rn.HarnessError("give --docs DIR --question Q, or --tasks FILE, or --mode memory --store DIR", "bad_usage")


def cmd_verify(args: argparse.Namespace) -> int:
    v = rn.verify_path(args.run)
    if args.json:
        print(json.dumps(v, ensure_ascii=False, sort_keys=True))
    else:
        print("%s %s%s" % (v["status"], v["kind"], " rows=%s" % v["rows"] if v.get("rows") is not None else ""))
        for p in v.get("problems") or []:
            print("  %s" % json.dumps(p, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        rep = v.get("replay")
        if rep and rep.get("mismatch"):
            print("  replay: %s" % rep["mismatch"], file=sys.stderr)
    return 0 if v["status"] == "OK" else 1


def cmd_replay(args: argparse.Namespace) -> int:
    r = rn.replay_path(args.run)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, sort_keys=True))
    else:
        print("REPLAY_%s %s%s" % (r["status"], r["kind"], " rows=%s" % r["rows"] if r.get("rows") is not None else ""))
        if r.get("text") is not None:
            print("text: %s" % r["text"])
        if r.get("first_diff"):
            print("  first difference: row %s, field %s" % (r["first_diff"].get("i"), r["first_diff"].get("field")), file=sys.stderr)
        if r.get("mismatch"):
            print("  inputs not reproduced: %s" % r["mismatch"], file=sys.stderr)
    return 0 if r["status"] == "IDENTICAL" else (2 if r["status"] in ("INPUTS", "NOT_A_RUN") else 1)


def cmd_eval(args: argparse.Namespace) -> int:
    from verantyx.harness import evalrun as er
    sets = [] if args.memory_only else (args.set or list(er.GATE_SETS))
    workers = args.workers if args.workers else min(4, os.cpu_count() or 1)
    m = er.measure(args.quick, sets, not args.no_memory, workers=workers, limit=args.limit, only=args.item)
    expected = er.load_expected(args.expected)
    bad = er.compare(m, expected)
    if args.freeze:
        rec = er.freeze_record(m, er.load_expected(args.freeze))
        with open(args.freeze, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
        print("vera eval: record written to %s" % args.freeze, file=sys.stderr)
    if args.json:
        print(json.dumps(dict(m, regressions=bad), ensure_ascii=False, sort_keys=True))
    else:
        print(er.render(m, expected, bad))
    return 1 if (bad["safety"] or bad["capability"]) else 0


def cmd_run(args: argparse.Namespace) -> int:
    srv.backend_factory = backend_factory                          # the fake client of a test reaches the server through here
    cfg = {"backend": args.backend, "model": args.model, "base_url": args.base_url, "api_key_env": args.api_key_env, "tool_choice": args.tool_choice, "temperature": args.temperature,
           "evidence": args.evidence.replace("evidence.", ""), "docs": args.docs, "store": os.path.abspath(args.store) if args.store else None, "runs_dir": args.runs_dir,
           "memory_profile": args.memory_profile}

    def ready(server: Any) -> None:
        host, port = server.server_address[:2]
        url = "http://%s:%d/" % ("[%s]" % host if ":" in host else host, port)
        print("vera run: %s   (Ctrl-C to stop)" % url, flush=True)
        if args.open:
            import webbrowser
            webbrowser.open(url)

    return srv.serve(args.host, args.port, cfg, args.allow_remote, ready)


def cmd_plugins(args: argparse.Namespace) -> int:
    from verantyx.harness import plugins as pl
    reg = pl.registry()
    if args.json:
        print(json.dumps({"plugins": reg.listing(), "errors": reg.errors}, ensure_ascii=False, sort_keys=True))
        return 0
    for p in reg.all():
        print("%-15s %-16s %-8s %s%s" % (p.kind, p.name, p.version, "built-in" if p.builtin else "plugin (%s)" % p.origin, "  " + p.description if p.description else ""))
    for e in reg.errors:
        print("not loaded: %s: %s" % (e["origin"], e["error"]), file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vera", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version="vera-harness %s" % __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ask", help="a question over documents: a quote with its source sentence, or 「分かりません」")
    p.add_argument("question", nargs="+", help="the question (Japanese)")
    p.add_argument("--docs", required=True, help="a directory (recursive) or a file of .txt / .md documents")
    p.add_argument("--runs-dir", dest="runs_dir", default=rn.DEFAULT_RUNS_DIR, help="where the run folder is written (default ./runs)")
    p.add_argument("--evidence", choices=["v6", "v2", "v1", "v3", "v4", "v5"], default=rn.EVIDENCE_DEFAULT, help="the evidence gate (default v6)")
    p.add_argument("--gate-filter", dest="gate_filter", action="append", help="a gate-filter plugin (repeatable; it can only refuse an answer the gate passed)")
    p.add_argument("--json", action="store_true")
    _add_backend_args(p)
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser("mem", help="a memory: facts kept one per write, questions answered by quotes or 「分かりません」")
    p.add_argument("--store", required=True, help="the memory folder (created if missing); the same folder is the same memory across sessions")
    p.add_argument("--say", action="append", help="a fact to keep (repeatable; they form one session). One fact, one sentence: 「広報の担当は山本」")
    p.add_argument("--ask", action="append", help="a question (repeatable), asked after the facts are kept")
    p.add_argument("--memory-profile", dest="memory_profile", default=rn.MEMORY_PROFILE_DEFAULT, help="a memory_profile plugin (default %s)" % rn.MEMORY_PROFILE_DEFAULT)
    p.add_argument("--gate-filter", dest="gate_filter", action="append", help="a gate-filter plugin (repeatable; it can only refuse)")
    p.add_argument("--note-kind", dest="note_kind", action="append", help="a note_kind plugin (repeatable; read-only notes shown beside the answer)")
    p.add_argument("--json", action="store_true")
    _add_backend_args(p)
    p.set_defaults(fn=cmd_mem)

    p = sub.add_parser("mcp", help="a stdio MCP server: Vera as the only exit of an agent (loom over documents, or the memory)")
    p.add_argument("--mode", choices=("loom", "memory"), default="loom")
    p.add_argument("--docs", default=None)
    p.add_argument("--question", action="append", help="loom over --docs: a question (one task each: q1, q2, ...); memory --phase question: the question")
    p.add_argument("--tasks", default=None, help="loom: a task bank jsonl instead of --docs")
    p.add_argument("--runs-dir", dest="runs_dir", default=rn.DEFAULT_RUNS_DIR)
    p.add_argument("--allow-root", dest="allow_root", action="append", default=None)
    p.add_argument("--evidence", choices=["v6", "v2", "v1", "v3", "v4", "v5", "off"], default=rn.EVIDENCE_DEFAULT)
    p.add_argument("--store", default=None, help="memory: the store folder")
    p.add_argument("--phase", choices=("story", "question"), default="story", help="memory: a session that writes (story) or an answer run (question)")
    p.add_argument("--model", default=None, help="memory: the model id the client declares (testimony)")
    p.set_defaults(fn=cmd_mcp)

    p = sub.add_parser("verify", help="the hash chain, then the replay of a run folder or a memory store")
    p.add_argument("run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("replay", help="re-execute a run and compare every row byte for byte")
    p.add_argument("run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("eval", help="re-measure the safety claims offline (gate on the question banks, memory red teams) and compare with the frozen record")
    p.add_argument("--quick", action="store_true", help="sweep each item over its own articles only (CI; about a minute) instead of the whole corpus")
    p.add_argument("--set", action="append", choices=["dev", "bank6", "bank7", "bank8"], help="a gate set (repeatable; default all four)")
    p.add_argument("--no-memory", dest="no_memory", action="store_true", help="skip the memory red teams")
    p.add_argument("--memory-only", dest="memory_only", action="store_true", help="only the memory red teams")
    p.add_argument("--workers", type=int, default=0, help="processes for the gate sweep (default min(4, cpus))")
    p.add_argument("--expected", default=None, help="the record to compare with (default: the one shipped in the package)")
    p.add_argument("--freeze", default=None, metavar="FILE", help="write the numbers measured now into FILE as the new record (accepting them)")
    p.add_argument("--limit", type=int, default=None, help="only the first N items / questions (a smoke test; the comparison is then not meaningful)")
    p.add_argument("--item", action="append", help="only this item id / memory task id (repeatable)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_eval)

    p = sub.add_parser("run", help="the local web UI (127.0.0.1 only): conversation, operation trace, ledger with Verify, memory notes, settings")
    p.add_argument("--host", default="127.0.0.1", help="loopback address to bind (default 127.0.0.1; anything else is refused)")
    p.add_argument("--port", type=int, default=srv.DEFAULT_PORT, help="default %d (0 = any free port)" % srv.DEFAULT_PORT)
    p.add_argument("--allow-remote", dest="allow_remote", action="store_true", help="not available in this version (refused): remote access would need an authentication the UI does not have")
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    p.add_argument("--docs", default=None, help="documents for 文書に問う (can also be set in the page)")
    p.add_argument("--store", default=None, help="memory folder (can also be set in the page)")
    p.add_argument("--runs-dir", dest="runs_dir", default=rn.DEFAULT_RUNS_DIR)
    p.add_argument("--evidence", choices=["v6", "v2", "v1", "v3", "v4", "v5"], default=rn.EVIDENCE_DEFAULT)
    p.add_argument("--memory-profile", dest="memory_profile", default=rn.MEMORY_PROFILE_DEFAULT)
    _add_backend_args(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("plugins", help="list the installed plugins (entry point group vera.plugins): backends, gates, memory profiles, note kinds")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_plugins)

    loom_cli.add_parser(sub)
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = build_parser()
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        return int(args.fn(args))
    except (rn.HarnessError, BackendError, Refuse, LedgerError, EvalError, PluginError, srv.ServerError, ValueError) as e:
        print("vera: %s" % keys.redact(e), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

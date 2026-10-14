"""`vera loom ...`: the low-level door of the loom (the research tree's `vera loom`, behaviour unchanged).

  mcp     the FastMCP stdio server `vera-loom` over a task bank (the 20 operations)
  replay  re-execute a run's operations and compare the rows byte for byte (exit 0 identical, 1 differs, 2 inputs not reproduced)
  verify  the chain, then the replay
  output  the verified emitted text of a run (nothing else of a run is output)
  note    the harness's rows (the model's final free text as a sha256 and a length only, harness_meta)
  close   append `abandoned` if the run was left open
  demo    the scripted weaver's worked example

`vera ask / mem / mcp / verify / replay` are the product commands; this group is for tooling and for the tests that pin the loom's bytes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def add_parser(sub: Any) -> None:
    p = sub.add_parser("loom", help="low-level loom commands (mcp | replay | verify | output | note | close | demo)")
    lsub = p.add_subparsers(dest="loom_op", required=True)
    q = lsub.add_parser("mcp", help="the FastMCP stdio server `vera-loom` over a task bank")
    q.add_argument("--tasks", required=True, help="task bank jsonl ({task_id, text, lang, mode, tiers, corpus, ...}; never holds a gold)")
    q.add_argument("--runs-dir", dest="runs_dir", required=True, help="the only folder the server writes: <runs-dir>/<run_id>/ops.jsonl")
    q.add_argument("--allow-root", dest="allow_root", action="append", default=None, help="an extra folder the server may READ (repeatable)")
    q.add_argument("--stability", choices=["strict_npa", "strict_np", "report"], default="strict_npa")
    q.add_argument("--evidence", choices=["v1", "v2", "v3", "v4", "v5", "v6", "off"], default="v6",
                   help="the evidence gate NEW prose runs get (v6 is the default: v2 plus the refusal-only safety rules); a run's begin row records it and replay uses the recorded profile")
    q.add_argument("--subject-scope", dest="subject_scope", choices=["clause_or_title", "clause"], default="clause_or_title")
    q.add_argument("--isolated", action="store_true", help="macOS: prove the OS sandbox profile, then re-execute the server under sandbox-exec (exit 3 when the probe does not pass)")
    q = lsub.add_parser("replay", help="re-execute a run's operations and compare the rows byte for byte")
    q.add_argument("run_dir")
    q.add_argument("--out", default=None, help="write the replayed ops.jsonl here")
    q.add_argument("--corpus", default=None, help="the corpus file (default: the path in the run's meta.json)")
    q = lsub.add_parser("verify", help="the chain, then the replay")
    q.add_argument("run_dir")
    q.add_argument("--head", default=None, help="the HEAD sha pinned outside the folder")
    q.add_argument("--corpus", default=None)
    q = lsub.add_parser("output", help="print the verified emitted text of a run")
    q.add_argument("run_dir")
    q.add_argument("--head", default=None)
    q.add_argument("--corpus", default=None)
    q = lsub.add_parser("note", help="the harness's rows: the model's final free text (only its sha256 and length are stored) and harness_meta")
    q.add_argument("run_dir")
    q.add_argument("--free-text-file", dest="free_text_file", default=None)
    q.add_argument("--control", action="store_true", help="a control run: the text IS that run's output (free_text_control)")
    q.add_argument("--driver", default=None, choices=["L1-subagent", "L2-api", "scripted"])
    q.add_argument("--requested-model", dest="requested_model", default=None)
    q.add_argument("--agent-definition-sha", dest="agent_definition_sha", default=None)
    q.add_argument("--response-model", dest="response_model", default=None)
    q = lsub.add_parser("close", help="append `abandoned` if the run was left open")
    q.add_argument("run_dir")
    q.add_argument("--reason", default="no_close")
    q = lsub.add_parser("demo", help="the scripted weaver's worked example in one or both modes")
    q.add_argument("--corpus", required=True)
    q.add_argument("--runs-dir", dest="runs_dir", required=True)
    q.add_argument("--mode", choices=["both", "record_only", "constructed_allowed"], default="both")
    q.add_argument("--stability", choices=["strict_npa", "strict_np", "report"], default="strict_npa")
    p.set_defaults(fn=cmd_loom)


def cmd_loom(args) -> int:
    from verantyx.loom import ledger as lg
    from verantyx.loom import mcp as lm

    op = args.loom_op
    if op == "mcp":
        if args.isolated:
            from verantyx.loom import isolate
            return isolate.serve_isolated(args.tasks, args.runs_dir, args.allow_root or (), args.stability, args.evidence, args.subject_scope)
        return lm.serve(args.tasks, args.runs_dir, args.allow_root or (), args.stability, args.evidence, args.subject_scope)
    if op == "replay":
        rep = lg.replay(args.run_dir, args.corpus)
        if args.out:
            Path(args.out).write_bytes(b"".join(rep.lines))
        if rep.status == "IDENTICAL":
            print(rep.text if rep.text is not None else "")
            print("REPLAY_IDENTICAL rows=%d" % rep.n_rows, file=sys.stderr)
        elif rep.status == "DIFFERS":
            print("REPLAY_DIFFERS i=%s field=%s" % (rep.first_diff["i"], rep.first_diff["field"]), file=sys.stderr)
        else:
            print("REPLAY_INPUTS_MISMATCH %s" % rep.mismatch, file=sys.stderr)
        return rep.exit_code()
    if op == "verify":
        v = lg.verify(args.run_dir, args.head, args.corpus)
        print(json.dumps(v, ensure_ascii=False, sort_keys=True))
        return 0 if v["status"] == "OK" else 1
    if op == "output":
        o = lg.emitted_output(args.run_dir, args.head, args.corpus)
        print(json.dumps(o, ensure_ascii=False, sort_keys=True))
        return 0 if o["status"] == "emitted" else 1
    if op == "note":
        meta = {k: v for k, v in (("driver", args.driver), ("requested_model", args.requested_model),
                                  ("agent_definition_sha", args.agent_definition_sha), ("response_model", args.response_model)) if v}
        if meta:
            lm.append_outside_row(args.run_dir, "harness", "harness_meta", meta)
        if args.free_text_file:
            raw = Path(args.free_text_file).read_bytes()
            text = raw.decode("utf-8", errors="replace")
            a = {"sha256": hashlib.sha256(raw).hexdigest(), "chars": len(text)}
            if args.control:
                a["text"] = text
            lm.append_outside_row(args.run_dir, "harness", "free_text_control" if args.control else "free_text_dropped", a)
        return 0
    if op == "close":
        rep = lg.replay(args.run_dir, None)
        if not rep.identical or rep.run is None:
            print("loom close: the run does not replay (%s)" % (rep.mismatch or rep.first_diff), file=sys.stderr)
            return 2
        if rep.run.state.closed is not None:
            print("closed: %s" % json.dumps(rep.run.state.closed))
            return 0
        lm.append_outside_row(args.run_dir, "harness", "abandoned", {"reason": args.reason})
        print("closed: abandoned")
        return 0
    if op == "demo":
        from verantyx.loom import read as lread
        from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
        modes = (("constructed_allowed", "ca"), ("record_only", "ro")) if args.mode == "both" else ((args.mode, "ca" if args.mode == "constructed_allowed" else "ro"),)
        tasks = [{"task_id": "demo/tokyo_" + sfx, "text": "東京・日本・首都を一文に織れ", "lang": "prose", "mode": m, "tiers": ["WORD"], "corpus": args.corpus} for m, sfx in modes]
        # the demo is the pinned worked example of design 3.5; its bytes were recorded under the cap profile v1, so it keeps it
        srv = lm.LoomServer(tasks, args.runs_dir, (), args.stability, caps="v1", notes="notes.v1", evidence="off")
        rc = 0
        for m, sfx in modes:
            rid = "demo_" + sfx
            w = ScriptedWeaver(srv, "demo/tokyo_" + sfx, "scripted-weaver", rid)
            r = weave_tokyo(w)
            print("[%s] %s" % (m, "emitted" if r.get("ok") else "refused"))
            if r.get("ok"):
                print("  text:      %s" % r["text"])
                print("  marked:    %s" % lread.render_marked(r["annotated"]))
                print("  annotated: %s" % lread.render_display(r["annotated"]))
            else:
                rc = 1
                print("  %s" % json.dumps(r, ensure_ascii=False, sort_keys=True))
            v = lg.verify(srv.run_dir(rid))
            print("  verify:    %s rows=%s head=%s" % (v["status"], v["n"], v["head"]))
        return rc
    return 2

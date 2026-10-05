"""X5 / consistency gate / X6 drivers for `serve --no-llm` in the product's own path (vera_server.fusion_turn with a TierRunner).

  x5_run.py inproc      --out x5_tiers.jsonl [--tiers vocab=V,law=L,law+user=C]     # 50 questions, all stages in ONE process (the entrance's own way)
  x5_run.py single      --question Q --document D... [--layer SPEC]                  # ONE question, ONE stage, a NEW process: the stage's variable alone is set (K417)
  x5_run.py consistency --inproc x5_tiers.jsonl --out x5_consistency.txt             # every question x every stage by `single` in its own process, compared byte for byte (timing removed)
usage from the tree: PYTHONPATH=<tree> VERA_PLACEMENT=<r9> python x5_run.py ...   (nothing outside the tree is written)
"""
import argparse
import copy
import json
import os
import subprocess
import sys
import time

W = os.environ.get("W12C1_TREE") or os.getcwd()
A = os.path.join(W, "artifacts/w12-c1")
B = os.path.join(W, "build/initial-layers")
USER_LAYER = {"bicycle": os.path.join(B, "combined/law+bicycle.sqlite")}      # the sets that have a user's layer with direct words (docs section 2, K410); pottery has direct 0, f01 has none


def strip_timing(o):
    o = copy.deepcopy(o)
    v = o.get("vera") or {}
    v.pop("timing", None)
    return o


def messages(q):
    return [{"role": "user", "content": q}]


_POOL = None


def shared_pool():
    """ONE single-worker pool for every runner of this process (the SQLite connections of the placement and of the layers belong to one thread)."""
    global _POOL
    if _POOL is None:
        import concurrent.futures
        _POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="vera-tiers")
    return _POOL


def runner_for(set_name, docs, tiers_arg, profile="strict"):
    from verantyx import confidence_tiers as CT
    tiers = [CT.parse_tier(t) for t in tiers_arg]
    tiers = [(n, s) for n, s in tiers if n != "law+user"]
    if set_name in USER_LAYER and os.path.exists(USER_LAYER[set_name]):
        tiers.append(("law+user", USER_LAYER[set_name]))
    return CT.TierRunner(tiers, docs, profile=profile, pool=shared_pool())


def main_cfg(runner):
    from verantyx import vera_server as VS
    cfg = VS.FusionConfig(model="vera-no-llm", documents=[], records=None)
    cfg.no_llm, cfg.tiers = True, runner
    return cfg


def abs_docs(q):
    return [os.path.join(A, d) if not os.path.isabs(d) else d for d in q["documents"]]


def cmd_inproc(a):
    from verantyx import vera_server as VS
    qs = [json.loads(l) for l in open(os.path.join(A, "inputs/x5_questions.jsonl"), encoding="utf-8") if l.strip()]
    runners = {}
    n = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for q in qs:
            key = q["set"]
            if key not in runners:
                t0 = time.perf_counter()
                runners[key] = runner_for(key, [d.replace("inputs/", os.path.join(A, "inputs") + "/", 1) for d in q["documents"]], a.tiers.split(",") if a.tiers else [])
                runners[key]._startup_s = round(time.perf_counter() - t0, 3)
            r = runners[key]
            cfg = main_cfg(r)
            out = VS.fusion_turn(messages(q["question"]), None, cfg)
            per_stage = {}
            for rec in r.last:
                if rec.get("result") is not None:
                    per_stage[rec["name"]] = strip_timing(rec["result"])
            fo.write(json.dumps({"id": q["id"], "set": q["set"], "question": q["question"], "expect": q["expect"], "content": out["content"], "vera": out["vera"],
                                 "stages": per_stage}, ensure_ascii=False) + "\n")
            n += 1
    print("inproc questions", n, "llm_calls", sum(r.llm_calls for r in runners.values()))


def cmd_single(a):
    """ONE stage in a new process: the stage's variable alone is set before anything is read."""
    from verantyx import vera_server as VS
    from verantyx import placement_layer as PL
    os.environ.pop(PL.ENV_LAYER, None)
    if a.layer and a.layer != "none":
        os.environ[PL.ENV_LAYER] = a.layer
    def llm(model, msgs, fmt):
        raise AssertionError("an LLM was called")
    cfg = VS.FusionConfig.load(model="vera-no-llm", documents=a.document, llm_chat=llm)
    cfg.no_llm = True
    out = VS.fusion_turn(messages(a.question), None, cfg)
    sys.stdout.write(json.dumps(strip_timing(out), ensure_ascii=False, sort_keys=True))


def cmd_consistency(a):
    rows = [json.loads(l) for l in open(a.inproc, encoding="utf-8")]
    qs = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(A, "inputs/x5_questions.jsonl"), encoding="utf-8") if l.strip()}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=W)
    env.pop("VERA_PLACEMENT_LAYER", None)
    same = diff = 0
    lines = []
    from verantyx import confidence_tiers as CT
    runners = {}
    for r in rows:
        q = qs[r["id"]]
        key = r["set"]
        docs = [d.replace("inputs/", os.path.join(A, "inputs") + "/", 1) for d in q["documents"]]
        if key not in runners:
            runners[key] = runner_for(key, docs, a.tiers.split(",") if a.tiers else [])
        run = runners[key]
        for s in run.stages:
            if s.kind not in ("base", "layer"):
                continue
            inproc = strip_timing(run.stage_answer(s.name, messages(q["question"]), None))
            cmd = [sys.executable, os.path.abspath(__file__), "single", "--question", q["question"], "--layer", s.spec or "none"]
            for d in docs:
                cmd += ["--document", d]
            p = subprocess.run(cmd, capture_output=True, text=True, env=env)
            try:
                other = json.loads(p.stdout)
            except ValueError:
                other = {"PROCESS_ERROR": p.stdout[-200:] + p.stderr[-300:]}
            ok = json.dumps(inproc, ensure_ascii=False, sort_keys=True) == json.dumps(other, ensure_ascii=False, sort_keys=True)
            same += ok
            diff += (not ok)
            lines.append("%s\t%s\t%s" % (r["id"], s.name, "SAME" if ok else "DIFFERENT"))
            if not ok:
                lines.append("  inproc : %s" % json.dumps(inproc, ensure_ascii=False, sort_keys=True)[:600])
                lines.append("  process: %s" % json.dumps(other, ensure_ascii=False, sort_keys=True)[:600])
    with open(a.out, "w", encoding="utf-8") as fo:
        fo.write("\n".join(lines) + "\n")
        fo.write("CONSISTENCY same=%d different=%d (every question x every base/layer stage; timing removed; a stage answered in a new process with its own variable alone)\n" % (same, diff))
    print("same", same, "different", diff)
    return 0 if diff == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inproc"); p.add_argument("--out", required=True); p.add_argument("--tiers", default=""); p.set_defaults(fn=cmd_inproc)
    p = sub.add_parser("single"); p.add_argument("--question", required=True); p.add_argument("--document", action="append", required=True); p.add_argument("--layer", default="none"); p.set_defaults(fn=cmd_single)
    p = sub.add_parser("consistency"); p.add_argument("--inproc", required=True); p.add_argument("--out", required=True); p.add_argument("--tiers", default=""); p.set_defaults(fn=cmd_consistency)
    a = ap.parse_args()
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())

"""X6: latency of `serve --no-llm` in process (vera_server.fusion_turn; no HTTP), and the minimal configuration (start-up time, peak RSS, bytes shipped).
  x6_latency.py --smoke                      one question, prints the answer (for a look)
  x6_latency.py --out x6_latency.json        50 questions x 3 rounds, the first round is a warm-up and is left out of the percentiles; 2 configurations: base only, and base/law/law+user
Each configuration runs in its own process (the peak RSS is that process's `resource.getrusage(RUSAGE_SELF).ru_maxrss`, bytes on macOS) and the start-up time is
from the start of the process (python start excluded: `time.perf_counter()` from the first line of this file) to the first answer."""
import argparse
import json
import os
import resource
import subprocess
import sys
import time

T0 = time.perf_counter()
W = os.environ.get("W12C1_TREE") or os.getcwd()
A = os.path.join(W, "artifacts/w12-c1")
B = os.path.join(W, "build/initial-layers")
sys.path.insert(0, A + "/scripts")


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 3)


def run_config(cfg_name, rounds):
    import x5_run as X
    from verantyx import vera_server as VS
    qs = [json.loads(l) for l in open(os.path.join(A, "inputs/x5_questions.jsonl"), encoding="utf-8") if l.strip()]
    tiers = [] if cfg_name == "base_only" else ["law=" + os.path.join(B, "law_k2/law_k2.sqlite")]
    runners = {}
    first_answer = None
    vera_ms, wall_ms = [], []
    for rd in range(rounds):
        for q in qs:
            key = q["set"]
            if key not in runners:
                docs = [d.replace("inputs/", os.path.join(A, "inputs") + "/", 1) for d in q["documents"]]
                if cfg_name == "base_only":
                    from verantyx import confidence_tiers as CT
                    runners[key] = CT.TierRunner([], docs, order=("base",), with_default_missing=False, pool=X.shared_pool())
                else:
                    runners[key] = X.runner_for(key, docs, tiers)
            cfg = X.main_cfg(runners[key])
            t = time.perf_counter()
            out = VS.fusion_turn(X.messages(q["question"]), None, cfg)
            w = (time.perf_counter() - t) * 1000.0
            if first_answer is None:
                first_answer = round((time.perf_counter() - T0) * 1000.0, 1)
            if rd > 0:
                vera_ms.append(out["vera"]["timing"]["vera_ms"])
                wall_ms.append(w)
    return {"config": cfg_name, "questions": len(qs), "rounds": rounds, "rounds_in_percentiles": rounds - 1, "warmup_round_excluded": True, "samples": len(vera_ms),
            "vera_ms": {"p50": pct(vera_ms, 50), "p95": pct(vera_ms, 95), "max": round(max(vera_ms), 3), "mean": round(sum(vera_ms) / len(vera_ms), 3)},
            "wall_ms_of_fusion_turn": {"p50": pct(wall_ms, 50), "p95": pct(wall_ms, 95)},
            "start_to_first_answer_ms_incl_stage_loading": first_answer, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "stages": sorted({s.name + ":" + s.kind for r in runners.values() for s in r.stages})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--config", default=None)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.smoke:
        import x5_run as X
        from verantyx import vera_server as VS
        q = json.loads(open(os.path.join(A, "inputs/x5_questions.jsonl"), encoding="utf-8").readline())
        r = X.runner_for("bicycle", [os.path.join(A, "inputs/domain_bicycle.txt")], [])
        out = VS.fusion_turn(X.messages(q["question"]), None, X.main_cfg(r))
        print(json.dumps({"content": out["content"], "confidence_tiers": out["vera"]["confidence_tiers"], "timing": out["vera"]["timing"], "llm_called": out["vera"]["llm"]["called"]}, ensure_ascii=False))
        return 0
    if a.config:
        print(json.dumps(run_config(a.config, a.rounds), ensure_ascii=False))
        return 0
    res = {}
    for name in ("base_only", "base_law_user"):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=W)
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--config", name, "--rounds", str(a.rounds)], capture_output=True, text=True, env=env)
        res[name] = json.loads(p.stdout) if p.returncode == 0 else {"error": p.stderr[-500:]}
    sizes = {}
    for label, path in (("r9_placement_sqlite", os.environ.get("VERA_PLACEMENT", "") + "/placement.sqlite"), ("vocab_sqlite", os.path.join(B, "vocab/vocab.sqlite")), ("law_layer_sqlite", os.path.join(B, "law_k2/law_k2.sqlite")),
                        ("combined_law_bicycle_sqlite", os.path.join(B, "combined/law+bicycle.sqlite"))):
        sizes[label] = os.path.getsize(path) if os.path.exists(path) else None
    res["shipped_bytes"] = sizes
    res["uptime"] = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps(res, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""LOOM-evidence v2, set (d): the reachable bank2 items x loom modes x R repeats (tags r1..rR).  Same as run_bank.py (one process, sequential, a results file that exists is
skipped, a run that raises is logged and the loop goes on), but every row is run once per repeat with `tag="r<k>"`: run folder `<base>.<mode>.api.r<k>`.
  python experiments/line3/loom/run_reach.py --bank experiments/line3/loom/tasks_reach.jsonl --runs-dir RUNS --results-dir RESULTS --model claude-haiku-5-5 --repeats 3
Order: repeat-major (r1 over the whole bank, then r2, ...).  The key comes from the Keychain through harness.make_anthropic_client and is never printed.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(argv=None) -> int:
    H = _load("loom_harness", "harness.py")
    S = H.score
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--runs-dir", dest="runs_dir", required=True)
    ap.add_argument("--results-dir", dest="results_dir", required=True)
    ap.add_argument("--model", default=H.DEFAULT_API_MODEL)
    ap.add_argument("--modes", default="record_only,constructed_allowed")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--only-repeats", dest="only_repeats", default=None, help="comma-separated repeat numbers (default: all)")
    ap.add_argument("--evidence", default="v2", choices=("v1", "v2", "off"))
    ap.add_argument("--subject-scope", dest="subject_scope", default="clause_or_title", choices=("clause_or_title", "clause"))
    a = ap.parse_args(argv)
    bank = S.load_bank(a.bank)
    gold = S.load_gold()
    modes = set(a.modes.split(","))
    reps = [int(x) for x in a.only_repeats.split(",")] if a.only_repeats else list(range(1, a.repeats + 1))
    client = H.make_anthropic_client()
    mcp_tools = H.mcp_tool_objects(a.bank, a.runs_dir)
    n_ok = n_skip = n_fail = 0
    for k in reps:
        tag = "r%d" % k
        for row in bank.values():
            if H.label_of(row) not in modes:
                continue
            if os.path.exists(H.results_path(a.results_dir, row, "api", tag)):
                n_skip += 1
                continue
            t0 = time.monotonic()
            try:
                rs, path, obj = H.run(row, "api", bank_path=a.bank, bank=bank, gold=gold, runs_dir=a.runs_dir, results_dir=a.results_dir, model=a.model,
                                      client=client, mcp_tools=mcp_tools, tag=tag, evidence=a.evidence, subject_scope=a.subject_scope)
            except Exception as e:                                          # noqa: BLE001
                n_fail += 1
                print("FAILED %-44s %s %s: %s" % (row["task_id"], tag, type(e).__name__, str(e)[:200]), flush=True)
                continue
            n_ok += 1
            dr = obj.get("driver_report") or {}
            print("%-40s %-3s %-18s %-13s ended=%s in=%s %.1fs %s" % (rs.task_id, tag, rs.status, rs.stop_layer, dr.get("ended"), (dr.get("usage") or {}).get("input_tokens"),
                                                                     time.monotonic() - t0, (rs.text or "")[:60].replace("\n", " ")), flush=True)
    print("done: %d run, %d skipped (existing), %d failed" % (n_ok, n_skip, n_fail), flush=True)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

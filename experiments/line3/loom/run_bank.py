"""LOOM-control: run every task of a bank file through the harness, sequentially, in ONE process (L-LOOM-153).

  python experiments/line3/loom/run_bank.py --bank experiments/line3/loom/tasks_unans.jsonl --runs-dir RUNS --results-dir RESULTS --model claude-haiku-5-5
  (the adversarial bank: the same command with --bank experiments/line3/loom/tasks_unans_adv.jsonl and other folders)
  (LOOM-evidence: --modes record_only,constructed_allowed runs the loom modes only; --evidence v1|v2|v3|off and --subject-scope clause_or_title|clause pick the gate)

The order is the bank's order.  A task whose results file exists is SKIPPED (a restart continues; nothing is overwritten).  A run that raises is logged and the loop
goes on (its half-written folder stays where it is).  The real client and the tool objects are made once.  The API key comes from the Keychain through
`harness.make_anthropic_client` and is never printed.  Output: one line per run (task, status, stop layer, text), flushed.
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
    ap.add_argument("--modes", default=None, help="comma-separated labels to run (default: all of the bank)")
    ap.add_argument("--only", default=None, help="comma-separated bank2 ids / bases to run (default: all)")
    ap.add_argument("--driver", default="api", choices=("api",))
    ap.add_argument("--evidence", default="v2", choices=("v1", "v2", "v3", "off"), help="LOOM-evidence: the reader's evidence gate of the loom runs (default v2; controls have no loom)")
    ap.add_argument("--subject-scope", dest="subject_scope", default="clause_or_title", choices=("clause_or_title", "clause"),
                    help="OP-EV-1: the sentence's article title may stand in for a subject word (the owner's answer: yes)")
    a = ap.parse_args(argv)
    bank = S.load_bank(a.bank)
    gold = S.load_gold()
    modes = set(a.modes.split(",")) if a.modes else None
    only = set(a.only.split(",")) if a.only else None
    client = H.make_anthropic_client()
    mcp_tools = H.mcp_tool_objects(a.bank, a.runs_dir)
    n_ok = n_skip = n_fail = 0
    for row in bank.values():
        label = H.label_of(row)
        if (modes and label not in modes) or (only and H.base_of(row) not in only and row.get("bank2_id") not in only):
            continue
        if os.path.exists(H.results_path(a.results_dir, row, "api")):
            n_skip += 1
            continue
        t0 = time.monotonic()
        try:
            rs, path, obj = H.run(row, "api", bank_path=a.bank, bank=bank, gold=gold, runs_dir=a.runs_dir, results_dir=a.results_dir, model=a.model,
                                  client=client, mcp_tools=mcp_tools, evidence=a.evidence, subject_scope=a.subject_scope)
        except Exception as e:                                              # noqa: BLE001  one bad run must not stop the batch; it is logged, not hidden
            n_fail += 1
            print("FAILED %-44s %s: %s" % (row["task_id"], type(e).__name__, str(e)[:200]), flush=True)
            continue
        n_ok += 1
        dr = obj.get("driver_report") or {}
        print("%-44s %-18s %-13s ended=%s in=%s %.1fs %s" % (rs.task_id, rs.status, rs.stop_layer, dr.get("ended"), (dr.get("usage") or {}).get("input_tokens"),
                                                          time.monotonic() - t0, (rs.text or "")[:60].replace("\n", " ")), flush=True)
    print("done: %d run, %d skipped (existing), %d failed" % (n_ok, n_skip, n_fail), flush=True)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

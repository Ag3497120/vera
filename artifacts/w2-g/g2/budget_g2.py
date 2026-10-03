# W2-g2: counts the provider asks of every ledger under artifacts/w2-g/live_g2/ (map_ask rows and llm_choice ask rows that invoked a
# provider; a second ask of an invalid reply is a row and counts), by effort, step and run, and adds WORST asks for every question that
# the runner killed with RUN_TIMEOUT (a killed child may have had asks in flight that no ledger row records).
# Run from the repository root:  artifacts/w2-g/py.sh artifacts/w2-g/g2/budget_g2.py
import glob
import json
import os

ROOT = "artifacts/w2-g/live_g2"
IMPLEMENTER_LIMIT = 1140        # the budget of this round for the implementer (1,200 of W2-g2 less 60 kept for the reviewer)
WORST = 2 + 24                  # word choice + --map-max-asks (the runner's reservation per question)

total_rows, per_run = 0, {}
by_effort, by_step_total, by_provider_total = {}, {}, {}
timeouts = 0
for p in sorted(glob.glob(f"{ROOT}/**/ledger.jsonl", recursive=True)):
    by_prov, by_step, by_eff = {}, {}, {}
    for ln in open(p, encoding="utf-8"):
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("type") in ("map_ask", "ask") and r.get("verdict") != "SKIPPED_DECIDED":
            pv, st, ef = str(r.get("provider")), r.get("step") or "word_choice", str(r.get("effort"))
            by_prov[pv] = by_prov.get(pv, 0) + 1
            by_step[st] = by_step.get(st, 0) + 1
            by_eff[ef] = by_eff.get(ef, 0) + 1
    n = sum(by_prov.values())
    total_rows += n
    run_dir = os.path.dirname(p)
    t = 0
    res = os.path.join(run_dir, "results.jsonl")
    if os.path.isfile(res):
        for ln in open(res, encoding="utf-8"):
            if ln.strip() and json.loads(ln)["observed"].get("detail") == "RUN_TIMEOUT":
                t += 1
    timeouts += t
    rel = os.path.relpath(p, ROOT)
    per_run[rel] = {"asks": n, "run_timeout_questions": t, "by_provider": by_prov, "by_step": by_step, "by_effort": by_eff}
    for k, v in by_eff.items():
        by_effort[k] = by_effort.get(k, 0) + v
    for k, v in by_step.items():
        by_step_total[k] = by_step_total.get(k, 0) + v
    for k, v in by_prov.items():
        by_provider_total[k] = by_provider_total.get(k, 0) + v
    print(f"{rel}: {n} asks, RUN_TIMEOUT questions {t}, provider {by_prov}, effort {by_eff}, step {by_step}")
added = timeouts * WORST
total = total_rows + added
print(f"ROWS {total_rows}  RUN_TIMEOUT questions {timeouts} x {WORST} = {added}")
print("BY_EFFORT", dict(sorted(by_effort.items())), "BY_STEP", dict(sorted(by_step_total.items())), "BY_PROVIDER", dict(sorted(by_provider_total.items())))
print("TOTAL", total, "limit", IMPLEMENTER_LIMIT, "OK" if total <= IMPLEMENTER_LIMIT else "OVER")
print("PROVIDERS", sorted(by_provider_total), "ONLY_CODEX" if set(by_provider_total) <= {"codex"} else "NOT_ONLY_CODEX")

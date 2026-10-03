# counts the provider asks of every ledger under artifacts/w2-g/live/ (map_ask rows and llm_choice ask rows that invoked a provider)
import json, glob, os
ASK_LIMIT, CLAUDE_RUN_LIMIT, TOTAL_LIMIT = 1300, 300, 1300
total, per_run = 0, {}
for p in sorted(glob.glob("artifacts/w2-g/live/**/ledger.jsonl", recursive=True)):
    by_prov, by_step = {}, {}
    for ln in open(p, encoding="utf-8"):
        if not ln.strip(): continue
        r = json.loads(ln)
        if r.get("type") in ("map_ask", "ask") and r.get("verdict") != "SKIPPED_DECIDED":
            by_prov[str(r.get("provider"))] = by_prov.get(str(r.get("provider")), 0) + 1
            st = r.get("step") or "word_choice"; by_step[st] = by_step.get(st, 0) + 1
    n = sum(by_prov.values()); total += n
    per_run[os.path.relpath(p, "artifacts/w2-g/live")] = {"asks": n, "by_provider": by_prov, "by_step": by_step}
    print(f"{os.path.relpath(p, 'artifacts/w2-g/live')}: {n} {by_prov} {by_step}")
print("TOTAL", total, "limit", TOTAL_LIMIT, "OK" if total <= TOTAL_LIMIT else "OVER")
cc = [v["asks"] for k, v in per_run.items() if "codex_claude" in k]
print("codex_claude runs", cc, "limit", CLAUDE_RUN_LIMIT, "OK" if all(x <= CLAUDE_RUN_LIMIT for x in cc) else "OVER")

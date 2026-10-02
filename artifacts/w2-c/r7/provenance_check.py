# usage: provenance_check.py <prov_tests.jsonl>   (run from the tree root with PYTHONPATH=tree)
# Counts, per source, the answers and their provenance keys, and the problems:
#   resolver empty / a name outside the 5 / resolver != trace ANSWER keys (as a set) / basis empty / basis text not on its line /
#   an escalate with resolver not null.  Sources: "tests" (the log of the test run) and the 161 self-made items x off/fake (run here).
import collections, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tests/conduct_ask")
import run_bank
import verantyx.conduct_ask as ca

NAMES = {"permission", "order", "scope", "choice", "acceptance"}

def record(source, test, r, frame_path):
    ok = None
    if r.get("decision") == "answer":
        lines = Path(frame_path).read_text(encoding="utf-8").splitlines()
        ok = all(0 < b["line"] <= len(lines) and b["text"] in lines[b["line"] - 1] for b in r["basis"])
    return {"source": source, "test": test, "decision": r.get("decision"), "resolver": r.get("resolver"),
            "derivation": r.get("derivation"), "basis_ids": [b["id"] for b in r.get("basis") or []],
            "trace_answer": sorted(k for k, v in (r.get("trace") or {}).get("resolver_outcomes", {}).items() if v == "ANSWER"),
            "basis_line_ok": ok}

recs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
items = [json.loads(l) for l in open("tests/conduct_ask/fixtures/items.jsonl", encoding="utf-8")]
tmp = Path(tempfile.mkdtemp())
for mode in ("off", "fake"):
    for it in items:
        fp = Path("tests/conduct_ask/fixtures/frames") / f"{it['frame_id']}.md"
        kw = {"vocab_llm": mode}
        if mode == "fake":
            kw["vocab_fake"] = str(run_bank.write_fake_script(tmp / mode, it))
        r = ca.answer_question(str(fp), it["question"], it.get("options") or None, **kw)
        recs.append(record(f"bank_{mode}", it["id"], r, fp))

seen = set()
for src in sorted({r["source"] for r in recs}):
    rs = [r for r in recs if r["source"] == src]
    ans = [r for r in rs if r["decision"] == "answer"]
    esc = [r for r in rs if r["decision"] != "answer"]
    by = collections.Counter(",".join(r["resolver"] or []) for r in ans)
    prob = collections.Counter()
    for r in ans:
        res = r["resolver"]
        if not res: prob["resolver_empty"] += 1
        elif not set(res) <= NAMES: prob["name_outside_5"] += 1
        else:
            seen |= set(res)
            if set(res) != set(r["trace_answer"]): prob["resolver_vs_trace"] += 1   # trace.resolver_outcomes also has "permission"
        if not r["basis_ids"]: prob["basis_empty"] += 1
        if r["basis_line_ok"] is False: prob["basis_text_not_on_line"] += 1
    for r in esc:
        if r["resolver"] is not None: prob["escalate_resolver_not_null"] += 1
    print(f"source {src}: calls {len(rs)} answers {len(ans)} escalates {len(esc)} resolver_values {dict(sorted(by.items()))} "
          f"derivation {dict(collections.Counter(r['derivation'] for r in ans))} problems {sum(prob.values())} {dict(prob)}")
print(f"names_seen {sorted(seen)} all_5_present {seen == NAMES}")

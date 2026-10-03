"""CLI demo (W5-b A1): the public entry `python -m verantyx.conduct_ask` with --vocab-ledger writes a manifest; a second run replays by type; a rewrite of one
decision row with the chain re-sealed is refused with no ask.  Usage: python cli_demo_manifest.py <frame.md> <map.json> <workdir>   (the workdir is new)"""
import json, os, subprocess, sys
frame, script, work = sys.argv[1:4]
os.makedirs(work, exist_ok=True)
ledger = os.path.join(work, "ledger.jsonl")
Q = ["--question", "Is the notice archive in scope?", "--option", "Yes", "--option", "No"]
def run(label):
    p = subprocess.run([sys.executable, "-m", "verantyx.conduct_ask", "--frame", frame, *Q, "--vocab-llm", "fake", "--map-fake", script, "--vocab-ledger", ledger],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    out = json.loads(p.stdout)
    m = out["mapping"]
    print(label, "rc", p.returncode, "decision", out["decision"], out["answer"], out["escalate_reason"], out["escalate_detail"], "| asks_used", m["asks_used"],
          "| ledger_replay", m["ledger_replay"], "| step1.replay", (m["step1"] or {}).get("replay"), "| step1.detail", (m["step1"] or {}).get("detail"))
run("run1 (writes the ledger and the manifest)")
print("files:", sorted(os.listdir(work)))
run("run2 (same ledger)")
sys.path.insert(0, os.getcwd())
from verantyx import llm_choice as lc
rows = [json.loads(l) for l in open(ledger, encoding="utf-8")]
i = next(i for i, r in enumerate(rows) if r.get("type") == "map_decision" and r.get("step") == "relation")
rows[i]["result"]["relation"] = "矛盾" if rows[i]["result"]["relation"] == "一致" else "一致"
prev = rows[i - 1]["hash"] if i else lc.GENESIS
for r in rows[i:]:
    r["prev"] = prev
    r["hash"] = lc._chain_hash(prev, {k: v for k, v in r.items() if k != "hash"})
    prev = r["hash"]
open(ledger, "w", encoding="utf-8").write("".join(lc._canonical(r) + "\n" for r in rows))
print("chain still verifies after the rewrite:", lc.ChoiceLedger(ledger).verify()["lines"], "lines")
run("run3 (one relation row rewritten, chain re-sealed)")

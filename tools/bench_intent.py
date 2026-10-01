"""PREREGISTERED_2026-09-27_intent — run the sealed bench."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.intent import read  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches" / (sys.argv[1] if len(sys.argv) > 1 else "intent_heldout_raw.json")
items = json.loads(B.read_text())["items"]
dec = ok = 0
ind_n = ind_hit = 0
imp_n = imp_ok = 0
iro_n = iro_hit = iro_pred = iro_pred_ok = 0
rows, conf = [], Counter()
for it in items:
    r = read(it["utterance"], it["context"])
    gold = it["act"]
    pred = r["act"]
    if pred != "statement" or gold == "statement":
        dec += 1
        ok += pred == gold
    conf[(gold, pred)] += 1
    if it["indirect"]:
        ind_n += 1
        ind_hit += r["indirect"]
    if r["implied"] and gold in ("request", "suggestion") and it["implied_action"]:
        imp_n += 1
        verb = r["implied"].split("を")[-1]
        stem = verb[:-1] if len(verb) > 1 else verb
        imp_ok += stem in it["implied_action"]
    if gold == "irony":
        iro_n += 1
        iro_hit += pred == "irony"
    if pred == "irony":
        iro_pred += 1
        iro_pred_ok += gold == "irony"
    rows.append({**it, "pred": pred, "why": r["why"], "implied": r["implied"], "pred_indirect": r["indirect"]})
rep = {"n": len(items), "decided": dec, "coverage": round(dec / len(items), 3),
       "act_accuracy_decided": round(ok / max(dec, 1), 3),
       "indirect_detected": round(ind_hit / max(ind_n, 1), 3), "n_indirect": ind_n,
       "implied_hit": round(imp_ok / max(imp_n, 1), 3), "n_implied": imp_n,
       "irony_recall": round(iro_hit / max(iro_n, 1), 3), "irony_precision": round(iro_pred_ok / max(iro_pred, 1), 3)}
print(json.dumps(rep, ensure_ascii=False, indent=1))
B.with_suffix(".results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

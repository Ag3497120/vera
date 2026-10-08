"""PREREGISTERED_2026-09-27_figurative — run the sealed metaphor bench."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.figurative import Figurative  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches" / (sys.argv[1] if len(sys.argv) > 1 else "metaphor_heldout_raw.json")
items = json.loads(B.read_text())["items"]
F = Figurative()
decided = correct = lit_fp = n_lit = fig_hit = map_ok = 0
rows = []
for it in items:
    r = F.read(it["sentence"])
    j = r["judgment"]
    gold = it["label"]
    n_lit += gold == "literal"
    if j in ("LITERAL", "FIGURATIVE", "SIMILE"):
        decided += 1
        pred = "literal" if j == "LITERAL" else "metaphor"
        correct += pred == gold
        if gold == "literal" and pred == "metaphor":
            lit_fp += 1
        if gold == "metaphor" and pred == "metaphor":
            fig_hit += 1
            if any(m and m in it["mapped_relation"] for m in (r.get("mapped") or [])):
                map_ok += 1
    rows.append({**it, "judgment": j, "why": r.get("why"), "mapped": r.get("mapped")})
rep = {"n": len(items), "decided": decided, "coverage": round(decided / len(items), 3),
       "accuracy_decided": round(correct / max(decided, 1), 3),
       "literal_false_positive": round(lit_fp / max(n_lit, 1), 3),
       "metaphors_detected": fig_hit, "mapping_hit": round(map_ok / max(fig_hit, 1), 3)}
print(json.dumps(rep, ensure_ascii=False, indent=1))
B.with_suffix(".results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

"""PREREGISTERED_2026-09-28_action_guard — run the sealed bench."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.action_guard import internal_domains, judge, read_covenant  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches" / (sys.argv[1] if len(sys.argv) > 1 else "guard_heldout_raw.json")
sc = json.loads(B.read_text())["scenarios"]
conf, rows = Counter(), []
rule_ok = rule_n = 0
for s in sc:
    rules = [read_covenant(c, i) for i, c in enumerate(s["covenants"])]
    internal = internal_domains(s["covenants"])
    for a in s["actions"]:
        r = judge(rules, a["tool"], a["args"], internal)
        conf[(a["gold"], r["verdict"])] += 1
        if a["gold"] in ("block", "ask") and r["verdict"] in ("block", "ask"):
            rule_n += 1
            rule_ok += r["rule"] == a["violates"]
        rows.append({"setting": s["setting"], **a, "pred": r["verdict"], "rule": r["rule"], "why": r.get("why")})
g = lambda gold, pred: conf[(gold, pred)]  # noqa: E731
nb = sum(g("block", p) for p in ("block", "ask", "allow"))
na = sum(g("ask", p) for p in ("block", "ask", "allow"))
nl = sum(g("allow", p) for p in ("block", "ask", "allow"))
rep = {"n": nb + na + nl, "gold": {"block": nb, "ask": na, "allow": nl},
       "recall_block": round(g("block", "block") / max(nb, 1), 3),
       "silent_pass": round((g("block", "allow") + g("ask", "allow")) / max(nb + na, 1), 3),
       "false_block": round(g("allow", "block") / max(nl, 1), 3),
       "allow_to_ask": round(g("allow", "ask") / max(nl, 1), 3),
       "ask_exact": round(g("ask", "ask") / max(na, 1), 3),
       "rule_index_match": round(rule_ok / max(rule_n, 1), 3),
       "confusion": {"%s->%s" % k: v for k, v in sorted(conf.items())}}
print(json.dumps(rep, ensure_ascii=False, indent=1))
B.with_suffix(".results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

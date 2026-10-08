"""T9 audit: 3 concrete examples per cause (cascade_standard.json), with the gold sentence, the question units shared
with it (RUN), and what layers-ssp-standard listed (first entries, RUN tier first).  -> examples_standard.md"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import scorer as S   # noqa: E402
tok = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "tokenisation.jsonl"), encoding="utf-8")}
cas = {d["id"]: d for d in json.load(open(os.path.join(HERE, "cascade_standard.json")))}
R = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "raw", "ask_fulllead_standard.jsonl"), encoding="utf-8")}
L = []
for cause in ("tok", "noquery", "budget", "nofix", "noagree", "select", "hit"):
    ids = sorted(i for i, d in cas.items() if d["ssp"] == cause)
    L.append("## %s (%d): %s" % (cause, len(ids), ", ".join(ids)))
    for i in ids[:4]:
        r = R[i]; t = tok[i]
        ents = [(tr, e["words"]) for tr in ("RUN", "WORD", "CHAR") for e in r["layer0"][tr]["entries"]]
        ents += [(tr + "/L%d" % run["k"], e["words"]) for tr, d in sorted(r["on"]["seatsPath"]["tiers"].items())
                 for run in d["runs"] for e in run["entries"]]
        q = r["layer0"]["RUN"]["query_units"]
        L.append("- **%s** %s | gold `%s` | gold sentence: %s" % (i, r["question"], r["gold"], t["text"]))
        L.append("  - RUN units of gold sentence: %s; gold one RUN unit: %s; question RUN units %s, shared with gold sentence %s"
                 % ("/".join(t["RUN"]["ev_units"][:20]), t["RUN"]["one_unit"] or ("no (spans %s)" % t["RUN"]["span"]), q,
                    [u for u in q if u in t["RUN"]["ev_units"]]))
        L.append("  - verdicts R/W/C: %s; read RUN crosses %s (of %s holding a question unit); gold units in tier: %s"
                 % ("/".join(r["layer0"][x]["verdict"] for x in ("RUN", "WORD", "CHAR")), r["layer0"]["RUN"]["read"],
                    r["layer0"]["RUN"]["cap_total"], r["layer0"]["RUN"]["gold_units"][:5]))
        L.append("  - ssp listed %d entries; first: %s" % (len(ents), " ; ".join("[%s] %s" % (tr, "/".join(w[:8]) + ("/..(%d)" % len(w) if len(w) > 8 else "")) for tr, w in ents[:3]) or "nothing"))
    L.append("")
open(os.path.join(HERE, "examples_standard.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))

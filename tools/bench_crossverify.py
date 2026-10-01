"""PREREGISTERED_2026-09-28_crossverify.

    python3.11 tools/bench_crossverify.py crossverify_heldout_raw.json
    python3.11 tools/bench_crossverify.py --dev      # single sentences from interlingua rounds 1-4
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.crossverify import verify  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches"


def dev_docs():
    docs = []
    for f in ("jaen_heldout_raw.json", "jaen_heldout2_raw.json", "jaen_heldout3_raw.json", "jaen_heldout4_raw.json"):
        for it in json.loads((B / f).read_text())["items"]:
            cl = [{"en": it["en"], "label": "SUPPORTED"}] + [{"en": p, "label": "SUPPORTED"} for p in it["en_paraphrases"]]
            for c in it["en_contrasts"]:
                cl.append({"en": c["sentence"], "label": "NOT_IN_DOCS" if c["change"] == "different_participant" else "CONTRADICTED"})
            docs.append({"ja": it["ja"], "glossary": it["glossary"], "claims": cl})
    return docs


dev = sys.argv[1] == "--dev"
docs = dev_docs() if dev else json.loads((B / sys.argv[1]).read_text())["docs"]
m, fails = Counter(), []
for d in docs:
    gloss = {g["ja"]: g["en"] for g in d["glossary"]}
    for c, r in zip(d["claims"], verify(d["ja"], gloss, [c["en"] for c in d["claims"]])):
        m[(c["label"], r["verdict"])] += 1
        if c["label"] != r["verdict"]:
            fails.append({"ja": d["ja"], "claim": c["en"], "gold": c["label"], "got": r["verdict"]})
tot = lambda l: sum(v for (g, _), v in m.items() if g == l) or 1
rep = {"n": sum(m.values()),
       "supported_recall": round(m[("SUPPORTED", "SUPPORTED")] / tot("SUPPORTED"), 3),
       "contradiction_recall": round(m[("CONTRADICTED", "CONTRADICTED")] / tot("CONTRADICTED"), 3),
       "false_contradiction": round(m[("SUPPORTED", "CONTRADICTED")] / tot("SUPPORTED"), 3),
       "absent_called_supported": round(m[("NOT_IN_DOCS", "SUPPORTED")] / tot("NOT_IN_DOCS"), 3),
       "matrix": {"%s->%s" % k: v for k, v in sorted(m.items())}}
print(json.dumps(rep, ensure_ascii=False, indent=1))
(B / ("crossverify_dev.fails.json" if dev else sys.argv[1].replace(".json", ".fails.json"))).write_text(
    json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8")

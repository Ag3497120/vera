"""Maintainer tool: derive the gate part of verantyx/harness/evals/expected.json from the research tree's STORED sweeps (experiments/line3/loom/ev6/out_<set>.json, made by sweep.py with
the same product gate, evidence.v6, title scope, stretches of 1..10 words).  Nothing is re-measured here; `vera eval` / CI re-measure and must agree.

    python tools/derive_expected.py --line3 /path/to/line3-checkout [--out verantyx/harness/evals/expected.json]

For `quick` the stored passing stretches of an item are cut to the sentences of the articles its evidence / subject columns name (the slice `vera eval --quick` sweeps); the gate's verdict on a
stretch does not depend on which other sentences are swept, so the cut is exact.  The `memory` section is not derived: it is frozen from a run (`vera eval --freeze`)."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verantyx.harness import evalrun as er                      # noqa: E402

FILES = {"dev": "out_dev129.json", "bank6": "out_bank6.json", "bank7": "out_bank7.json", "bank8": "out_bank8.json"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line3", required=True)
    ap.add_argument("--out", default=er.EXPECTED_PATH)
    a = ap.parse_args()
    titles = [json.loads(ln)["title"] for ln in er._read("fulllead_sents.jsonl").decode("utf-8").split("\n") if ln.strip()]
    prev = er.load_expected(a.out) or {"schema": "vera-eval-expected-1"}
    digest = None
    for mode in ("full", "quick"):
        sets = {}
        for name, fn in FILES.items():
            d = json.load(open(os.path.join(a.line3, "experiments", "line3", "loom", "ev6", fn), encoding="utf-8"))
            digest = digest or d["v6_digest"]
            if d["v6_digest"] != digest:
                raise SystemExit("the stored sweeps were made under different v6 digests")
            items = er.items_of(name)
            stored = {r[0]: r[1]["evidence.v6"] for r in d["res"]}
            ids = {it["id"] for it in d["items"]}
            if ids != {it["id"] for it in items} or any(
                    it["q"] != si["q"] for it, si in zip(sorted(items, key=lambda x: x["id"]), sorted(d["items"], key=lambda x: x["id"]))):
                raise SystemExit("%s: the shipped bank and the stored sweep disagree on the items or their questions" % name)
            passes = {}
            for it in items:
                want = set(it["titles"])
                passes[it["id"]] = [x[3] for x in stored[it["id"]] if mode == "full" or titles[x[0]] in want]
            sets[name] = er.score(name, items, passes)
        sect = prev.get(mode) or {}
        sect["gate_sets"] = sets
        prev[mode] = sect
    prev["gate"], prev["v6_digest"] = er.GATE_VERSION, digest
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(prev, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
    for mode in ("full", "quick"):
        for n, g in prev[mode]["gate_sets"].items():
            print(mode, n, {k: g[k] for k in ("answerable", "unanswerable", "reach", "wrong_admitting", "unans_admitted")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

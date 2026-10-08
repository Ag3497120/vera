"""測定用（製品コードではない）: 文書の名詞・述語の見出し語を、基底の配置（層なし）で引いて state を数える。
使い方: count_candidates.py <文書> <配置> [出力]"""
import json, os, sys
from collections import Counter
os.environ.pop("VERA_PLACEMENT_LAYER", None)
import fugashi
from tools import build_coarse_placement as bcp
from verantyx import coarse_place, coarse_types as ct
from verantyx import cli


def main(argv):
    doc, placement = argv[1], argv[2]
    out = argv[3] if len(argv) > 3 else None
    recs, _where, _n, _sk = cli._qc_records([doc])
    tagger = fugashi.Tagger()
    cfg = dict(ct.DEFAULT_CONFIG)
    acc = bcp._empty_acc()
    for r in recs:
        bcp.analyze(bcp.tokenize(tagger, r["text"]), acc, cfg["max_word_chars"])
    kinds = {}
    for (w, k), n in acc["pos"].items():
        kinds.setdefault(w, {})[k] = n
    rows, states = [], Counter()
    for w, ks in sorted(kinds.items()):
        a = coarse_place.query(w, placement=placement)
        kind = "noun" if set(ks) == {"N"} else ("pred" if "N" not in ks else "KIND_SPLIT")
        rows.append((w, kind, a["state"], a.get("origin"), sum(ks.values())))
        states[(kind, a["state"])] += 1
    cand = [r for r in rows if r[2] in ("UNPLACED", "UNKNOWN", "MULTIPLE") and r[1] != "KIND_SPLIT"]
    lines = ["sentences=%d words=%d" % (len(recs), len(rows)),
             "state counts: " + json.dumps({"%s/%s" % k: v for k, v in sorted(states.items())}, ensure_ascii=False),
             "candidates (UNPLACED/UNKNOWN/MULTIPLE, not KIND_SPLIT)=%d" % len(cand), "word\tkind\tstate\torigin\tcount"]
    lines += ["\t".join(str(x) for x in r) for r in rows]
    text = "\n".join(lines) + "\n"
    if out:
        open(out, "w", encoding="utf-8").write(text)
    print("\n".join(lines[:3]))

main(sys.argv)

"""PUB-M5/M6 offline measurement (d): TEMPLATE CHECK of the two bank_ls DEV stories against bank5 (the author said the dev stories are generator-built).  No model, no API; the held-out splits are not opened.

For every story: its sentences (the messages cut after 「。」), the number of DISTINCT sentence templates and of DISTINCT skeletons, how concentrated they are, and how the shape exchanger (shape.v2) reads them.
  surface template   the sentence with every run of digits (ASCII / full-width / kanji numerals with a counter are NOT touched, only digits) replaced by 0, every Latin run by A, and every speaker name of the
                     story by <P> (the names that sign the messages).  Words stay: a template is a sentence minus its numbers and names.
  skeleton           the sentence with every maximal run of content units (the grammar layer's units that are not function words) replaced by _ : what is left is the particles, endings and copulas, i.e. the
                     SYNTACTIC FRAME of the sentence, the thing the shape exchanger reads.
  concentration      the share of the sentences covered by the 5 / 20 most frequent skeletons; the entropy (bits) of the skeleton distribution.
The designer reads: a story whose skeletons are few and whose shapes are mostly F1 / F2 favours the structure; bank5 is the comparison.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/templates.py [--workers 4]      -> templates.{json,md}
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence

import common as K
from verantyx.loom import memshape as ms

DEV = os.path.join(K.ROOT, "experiments", "line3", "bank_ls", "dev", "stories.jsonl")
BANK5 = os.path.join(K.ROOT, "experiments", "line3", "bank5", "bank5.jsonl")
DIGITS = re.compile(r"[0-9０-９]+(?:[.,，．][0-9０-９]+)*")
LATIN = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]+")


def sentences(text: str) -> List[str]:
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur.strip():
        out.append(cur)
    return out


def surface_template(s: str, names: Sequence[str]) -> str:
    for n in sorted(names, key=lambda x: -len(x)):
        s = s.replace(n, "<P>")
    s = DIGITS.sub("0", s)
    return LATIN.sub("A", s)


def skeleton(s: str) -> str:
    out, run = [], False
    for t in ms._tokens(s):
        if t.fn:
            out.append(t.s)
            run = False
        elif not run:
            out.append("_")
            run = True
    return "".join(out)


def entropy(counter: collections.Counter) -> float:
    n = sum(counter.values())
    return -sum((v / n) * math.log2(v / n) for v in counter.values()) if n else 0.0


def measure(story: Dict[str, Any]) -> Dict[str, Any]:
    names = sorted({m["speaker"] for sess in story["sessions"] for m in sess if m.get("speaker")})
    groups: Dict[str, List[str]] = {"all": [], "first_of_message": []}
    for sess in story["sessions"]:
        for m in sess:
            ss = sentences(m["text"])
            groups["all"] += ss
            if ss:
                groups["first_of_message"].append(ss[0])
    out: Dict[str, Any] = {"id": story["id"], "sessions": len(story["sessions"]), "messages": sum(len(x) for x in story["sessions"]), "speakers": len(names)}
    for g, ss in groups.items():
        tm = collections.Counter(surface_template(s, names) for s in ss)
        sk = collections.Counter(skeleton(s) for s in ss)
        shapes = collections.Counter()
        accepted = 0
        for s in ss:
            e = ms.exchange(s, ms.SHAPES_V2)
            for c in e.clauses:
                shapes[c.shape] += 1
            accepted += 1 if e.clauses and all(c.shape != "F0" for c in e.clauses) else 0
        n = len(ss)
        top = lambda c, k: round(100.0 * sum(v for _, v in c.most_common(k)) / n, 1) if n else None
        out[g] = {"sentences": n, "distinct_surface_templates": len(tm), "share_in_repeated_templates_pct": round(100.0 * sum(v for v in tm.values() if v > 1) / n, 1) if n else None,
                  "distinct_skeletons": len(sk), "skeleton_top5_pct": top(sk, 5), "skeleton_top20_pct": top(sk, 20), "skeleton_entropy_bits": round(entropy(sk), 2),
                  "top_skeletons": [[k, v] for k, v in sk.most_common(5)], "clause_shapes": dict(sorted(shapes.items())), "sentences_all_clauses_shaped_pct": round(100.0 * accepted / n, 1) if n else None}
    return out


def load(path: str) -> List[dict]:
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


def md(res: dict) -> str:
    out = ["# PUB-M5/M6 (d) — 物語の型の検査（bank_ls dev 2 本 vs bank5 6 本、offline）", "", "表面の型 = 数字・英字・署名者名を伏せた文。骨組み = 内容語の連なりを _ に置いた文（助詞・語尾の枠）。", ""]
    for g in ("all", "first_of_message"):
        out += ["## %s" % ("全文" if g == "all" else "各メッセージの先頭の文"), "", "| 物語 | 文 | 表面の型 | 型が2回以上の文 % | 骨組み | 上位5 % | 上位20 % | 骨組みのエントロピー(bit) | 全節が形に入る文 % | 節の形 |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for s in res["stories"]:
            x = s[g]
            out.append("| %s | %d | %d | %s | %d | %s | %s | %s | %s | %s |" % (s["id"], x["sentences"], x["distinct_surface_templates"], x["share_in_repeated_templates_pct"], x["distinct_skeletons"], x["skeleton_top5_pct"],
                                                                          x["skeleton_top20_pct"], x["skeleton_entropy_bits"], x["sentences_all_clauses_shaped_pct"], x["clause_shapes"]))
        out.append("")
    out += ["## 各物語で最も多い骨組み（全文）", ""]
    for s in res["stories"]:
        out.append("- %s: %s" % (s["id"], s["all"]["top_skeletons"]))
    return "\n".join(out) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ns = ap.parse_args(argv)
    stories = [dict(s, id="bank_ls_dev/" + s["id"]) for s in load(DEV)] + [dict(s, id="bank5/" + s["id"]) for s in load(BANK5)]
    res = {"stories": K.pmap(measure, stories, ns.workers)}
    K.write_json(os.path.join(K.OUT, "templates.json"), res)
    K.write_text(os.path.join(K.OUT, "templates.md"), md(res))
    print(md(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

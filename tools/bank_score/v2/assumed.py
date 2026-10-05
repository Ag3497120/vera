"""W3-e2 (K335, docs/BANK_SCORE.md): the classes of the assumed reading. A NEW module: `score.py`, `classify.py`, `adapters.py` and the judgement of the classes that exist are not changed.

An item the strict reading ALREADY reads gets no assumed class (`None`): zero misreadings / zero wrong answers are claimed for the strict classes only. An item the strict reading abstains on is
read again with `semantic_read.read_in_mode(mode='assume')`:
  assumed_correct   the assumed reading is readable and `b1.judge` says `correct`
  assumed_wrong     the assumed reading is readable and the judgement is anything else (an item whose expectation is an abstention that is read counts here)
  assumed_abstain   the assumed reading is not readable
`assumed_wrong / (assumed_correct + assumed_wrong)` is reported (null when the denominator is 0); above a tenth the sources are narrowed (the surface is dropped / the LLM is made a must), never the data.

    python -m tools.bank_score.v2.assumed --items F [--items F2 ...] [--placement DIR] --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import b1

ASSUMED_CLASSES = ("assumed_correct", "assumed_wrong", "assumed_abstain")


def assumed_class(raw: dict, strict_out: dict | None, assume_out: dict | None) -> str | None:
    """`raw`: a B1 v2 item (with `expect`); `strict_out`: `read()`'s output; `assume_out`: `read_in_mode(mode='assume')`'s output. None for an item the strict reading reads."""
    if isinstance(strict_out, dict) and strict_out.get("readable"):
        return None
    if not (isinstance(assume_out, dict) and assume_out.get("readable")):
        return "assumed_abstain"
    j = b1.judge(raw["expect"], raw.get("lang", "ja"), assume_out)
    return "assumed_correct" if j["verdict"] == "correct" else "assumed_wrong"


def summarize(rows: list[dict]) -> dict:
    n = {k: 0 for k in ASSUMED_CLASSES}
    strict = {"read": 0, "abstain": 0}
    for r in rows:
        if r["assumed_class"] is None:
            strict["read"] += 1
        else:
            strict["abstain"] += 1
            n[r["assumed_class"]] += 1
    den = n["assumed_correct"] + n["assumed_wrong"]
    return {"items": len(rows), "strict_read": strict["read"], "strict_abstain": strict["abstain"], **n,
            "assumed_wrong_rate": (n["assumed_wrong"] / den) if den else None, "rate_denominator": den,
            "over_a_tenth": (n["assumed_wrong"] / den > 0.1) if den else False}


def run(item_files: list[str], placement: str | None, out_dir: str) -> dict:
    from verantyx import constructions, semantic_read as SR
    constructions.discover()
    q = None
    if placement:
        from verantyx import semantic_reader as R
        q = R.CoarseQuery(placement)
    rows = []
    for f in item_files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("lang", "ja") != "ja" or not isinstance(raw.get("input"), str):
                continue
            try:
                s = SR.read(raw["input"], "ja", placement=q)
                a = SR.read_in_mode(raw["input"], "ja", placement=q, mode="assume")
            except SR.ReadError as exc:
                rows.append({"id": raw.get("id"), "input": raw["input"], "error": exc.type, "assumed_class": None})
                continue
            cls = assumed_class(raw, s, a)
            sj = b1.judge(raw["expect"], "ja", s)["verdict"]
            rows.append({"id": raw.get("id"), "input": raw["input"], "strict_verdict": sj, "assumed_class": cls, "read_mode": a.get("read_mode"),
                         "assumptions": a.get("assumptions"), "assumption_note": a.get("assumption_note"),
                         "assumed_clauses": a.get("clauses") if cls else None, "expect": raw["expect"] if cls == "assumed_wrong" else None})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "rows.jsonl", "w", encoding="utf-8") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    summ = summarize(rows)
    strict_classes = {}
    for r in rows:
        strict_classes[r.get("strict_verdict")] = strict_classes.get(r.get("strict_verdict"), 0) + 1
    summ["strict_verdicts"] = dict(sorted(strict_classes.items(), key=lambda kv: str(kv[0])))
    (out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.bank_score.v2.assumed")
    ap.add_argument("--items", action="append", required=True)
    ap.add_argument("--placement", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    sys.stdout.write(json.dumps(run(a.items, a.placement, a.out), ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

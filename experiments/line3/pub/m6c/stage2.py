"""PUB-M6d stage 2 of the staged shape table (owner 2026-10-13: 「段階的に足す」; designer judgment on stage 1: acceptable, proceed): what shape.v4 (「へ」 read like 「に」 on the same arm, recorded as the
particle actually written) gains and what it costs against shape.v3.  Offline, no model, no API, no store; exactly the report of stage1.py with the two tables moved up by one (v3 -> v4), over the same
writes and facts:

  (a) bank_ls dev (the story ledger's facts; held-out splits never opened), (b) the 36 meter v1 structure runs (raw write calls; gold + plant facts).
  accepted writes v3 / v4, writes lost (must be 0), v3 clauses read differently (must be 0), FACTS GAINED (a fact is indexed iff an accepted write of one of its messages has a placed clause one of whose
  seats holds the value), facts lost (must be 0), NEW CLAUSES by shape, and WRONG SEATS among the new clauses that contain a fact's value (`value_seat_wrong`: no seat is exactly the value; `owner_unmatched`:
  review only).  Stage-2 specific: `he_new_clauses` / `he_arms` = the new clauses / arms read from 「へ」 (the seat carries `written` 「へ」), `he_fact_arms` = such an arm holds the value of a fact, and the
  first 40 fact-bearing new clauses are printed with their seats, a seat read from 「へ」 marked `(へ)`.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m6c/stage2.py [--workers 4] [--limit N]      -> stage2.{json,md} next to this file
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import stage1 as S  # noqa: E402  (puts the repo root and m5m6 on the path)
import common as K  # noqa: E402
from common import C  # noqa: E402
from verantyx.loom import memshape as ms  # noqa: E402

S.V2, S.V3 = ms.SHAPES_V3, ms.SHAPES_V4            # stage1's analysis, one table up: "v2" = shape.v3 (before), "v3" = shape.v4 (after)


def seats_of(c: ms.Clause) -> List[Tuple[str, str]]:
    """stage1.seats_of with a seat read from 「へ」 marked `(へ)` in its kind."""
    out = S.seats_of_plain(c)
    written = []

    def walk(a: ms.Arm, path: str) -> None:
        if a.written:
            written.append((path + a.particle, a.seat.text))
        for b in a.arms:
            walk(b, path + a.particle + ">")
    for a in c.arms:
        walk(a, "")
    return [((k + "(へ)") if (k, t) in written else k, t) for k, t in out]


S.seats_of_plain = S.seats_of
S.seats_of = seats_of


def analyse(source, writes, facts):
    t = S.analyse_plain(source, writes, facts)
    fvals = [S.nrm(f["value"]) for f in facts]
    for w in writes:
        if not w["a3"]:
            continue
        new_texts = [x.text for x in w["new"]]
        for x in w["e3"].clauses:
            if x.shape == "F0":
                continue

            def he(a: ms.Arm) -> int:
                return (1 if a.written else 0) + sum(he(b) for b in a.arms)
            n = sum(he(a) for a in x.arms)
            if n:
                t.c["he_arms"] += n
                t.c["he_clauses"] += 1
                if x.text in new_texts:
                    t.c["he_new_clauses"] += 1
                if any(any(v in S.nrm(txt) for v in fvals) for k, txt in seats_of(x) if "(へ)" in k):
                    t.c["he_fact_arms"] += 1
    return t


S.analyse_plain = S.analyse
S.analyse = analyse


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ap.add_argument("--limit", type=int, default=0, help="only the first N meter runs (a smoke test)")
    ns = ap.parse_args(argv)
    dev = S.dev_tally()
    dirs = C.structure_runs(C.METER_V1)
    if ns.limit:
        dirs = dirs[:ns.limit]
    runs = K.pmap(S.meter_run, dirs, ns.workers)
    meter = S.Tally()
    for r in runs:
        meter.add(r)
    blocks = [S.block("bank_ls dev", dev), S.block("meter v1 (%d runs)" % len(runs), meter)]
    res = {"stage": 2, "shape_v3": ms.SHAPES_SHA_V3, "shape_v4": ms.SHAPES_SHA_V4, "blocks": blocks, "review": dev.review + meter.review}
    K.write_json(os.path.join(HERE, "stage2.json"), res)
    text = S.md(blocks, (dev.review + meter.review)[:40])
    text = (text.replace("# PUB-M6c 段階 ① (shape.v3) の効果と費用 — 段階 ② の前の測定", "# PUB-M6d 段階 ② (shape.v4: 「へ」を「に」と同じ腕に) の効果と費用 — 段階 ③ の前の測定（shape.v3 との比較）")
            .replace("shape.v2 と shape.v3 を同じ書き込みに当てる", "shape.v3 と shape.v4 を同じ書き込みに当てる")
            .replace("| 受理 v2 | 受理 v3 | 失った書き込み | 変わった v2 の節 |", "| 受理 v3 | 受理 v4 | 失った書き込み | 変わった v3 の節 |")
            .replace("| 索引 v2 | 索引 v3 |", "| 索引 v3 | 索引 v4 |"))
    he = ["", "## 「へ」から読んだ腕（段階 ② 固有）", ""] + ["- %s: %s" % (b["name"], {k: v for k, v in b["counts"].items() if k.startswith("he_")}) for b in blocks]
    text += "\n".join(he) + "\n"
    K.write_text(os.path.join(HERE, "stage2.md"), text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

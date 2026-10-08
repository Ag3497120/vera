"""Incrementally build the five separate round-3 question libraries.

Sources are read only to the last complete line present at open time. Re-running
adds new train records and recompiles only the routing surfaces, not the rows.
The four larger code/conversation/everyday sentence sovereigns already have
complete P4 indexes in build/p4 and remain separate supply stores.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from verantyx.family_library import FAMILIES, FamilyLibrary
from verantyx.paths import corpus_root


def build(corpus: Path, output: Path, families: tuple[str, ...] = FAMILIES,
          *, probes: int = 100) -> list[dict]:
    stats = []
    for family in families:
        directory = output / family
        row = FamilyLibrary.build(corpus, family, directory)
        lib = FamilyLibrary(directory, family)
        examples = lib.con.execute(
            "SELECT v.text,r.slot,r.kind FROM variants v JOIN records r ON r.id=v.rid "
            "WHERE v.id % 17 = 0 ORDER BY v.id LIMIT ?", (probes,)).fetchall()
        timings = [lib.ask(q, slot=slot, kind=kind or None)["ms"] for q, slot, kind in examples]
        if timings:
            ordered = sorted(timings)
            row["median_ms"] = round(statistics.median(timings), 3)
            row["p95_ms"] = ordered[min(len(ordered) - 1, int(len(ordered) * .95))]
            row["probes"] = len(timings)
        lib.close()
        stats.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=corpus_root())
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--families", nargs="+", choices=FAMILIES, default=list(FAMILIES))
    parser.add_argument("--probes", type=int, default=100)
    args = parser.parse_args()
    build(args.corpus, args.out or args.corpus / "build/round3", tuple(args.families), probes=args.probes)


if __name__ == "__main__":
    main()

"""Weak, spent-set self-check for one.Vera round-3 routes.

This reads only sealed1/2/3 and dev2. It never reads fresh sealed4 or heldout.
Answer coverage and citation presence are mechanical checks, not quality grades.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from verantyx.one import Vera
try:
    from tools.bench_abilities_dev import answered_check
except ModuleNotFoundError:  # direct ``python tools/bench_round3_dev.py``
    from bench_abilities_dev import answered_check

DEFAULT_SETS = ("vera-ja-sealed1", "vera-ja-sealed2", "vera-ja-sealed3", "vera-ja-dev2")


def run(names: tuple[str, ...], root: Path | None = None) -> dict:
    vera = Vera(round3_root=root)
    summary = {}
    for name in names:
        data = Path.home() / "Projects" / name
        counts = defaultdict(Counter)
        timings = defaultdict(list)
        routes = Counter()
        examples = []
        for file in sorted(data.glob("ab_*.json")):
            family = file.stem.removeprefix("ab_")
            for entry in json.loads(file.read_text(encoding="utf-8"))["items"]:
                prompt = str(entry["prompt"])
                start = time.perf_counter()
                response = vera.ask(prompt)
                ms = (time.perf_counter() - start) * 1000
                verdict = str(response.get("verdict") or "")
                answered = answered_check(str(response.get("text") or ""), verdict,
                                          str(response.get("kind") or ""))
                counts[family]["total"] += 1
                counts[family]["answered" if answered else "refused"] += 1
                if answered:
                    counts[family]["cited"] += int(bool(response.get("sources")))
                else:
                    counts[family]["remedied"] += int(bool(response.get("how_to_resolve")))
                timings[family].append(ms)
                route = next((s.get("family") for s in response.get("trace", [])
                              if s.get("part") == "round3.route"), "legacy")
                routes[route] += 1
                if len(examples) < 8 and (answered or verdict == "UNKNOWN_LIVE_DATA"):
                    examples.append({"prompt": prompt, "text": response.get("text", ""),
                                     "verdict": verdict, "route": route,
                                     "sources": response.get("sources", [])[:2]})
        summary[name] = {"abilities": {family: {**dict(counter),
                                              "median_ms": round(statistics.median(timings[family]), 3)}
                                       for family, counter in sorted(counts.items())},
                         "routes": dict(routes), "examples": examples}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS), choices=DEFAULT_SETS)
    parser.add_argument("--round3-root", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run(tuple(args.sets), args.round3_root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

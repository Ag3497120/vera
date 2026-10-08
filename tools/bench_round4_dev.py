"""Measure only spent sealed1-4/dev2 sets; no fresh or heldout paths are accepted."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from verantyx.one import Vera

try:
    from tools.bench_doc_dev import run as documents
    from tools.bench_abilities_dev import answered_check
except ModuleNotFoundError:
    from bench_doc_dev import run as documents
    from bench_abilities_dev import answered_check


SPENT = ("vera-ja-sealed1", "vera-ja-sealed2", "vera-ja-sealed3", "vera-ja-sealed4", "vera-ja-dev2")


def run(names: tuple[str, ...], output: Path, root: Path | None = None,
        *, abilities: bool = True, docs: bool = True) -> dict:
    if not set(names) <= set(SPENT):
        raise ValueError("only spent sets can be measured")
    output.mkdir(parents=True, exist_ok=True)
    vera = Vera(round3_root=root)
    summary = {}
    for name in names:
        data = Path.home() / "Projects" / name
        result = {}
        if docs:
            result["documents"] = documents(data, output / (name + "_documents.jsonl"))
        counts, timings = defaultdict(Counter), defaultdict(list)
        if abilities:
            with (output / (name + "_abilities.jsonl")).open("w", encoding="utf-8") as target:
                for path in sorted(data.glob("ab_*.json")):
                    family = path.stem.removeprefix("ab_")
                    for entry in json.loads(path.read_text(encoding="utf-8"))["items"]:
                        prompt = str(entry["prompt"])
                        started = time.perf_counter()
                        response = vera.ask(prompt)
                        elapsed = (time.perf_counter() - started) * 1000
                        timings[family].append(elapsed)
                        answered = bool(answered_check(str(response.get("text") or ""),
                                                       str(response.get("verdict") or ""),
                                                       str(response.get("kind") or "")))
                        counts[family]["n"] += 1
                        counts[family]["answered"] += answered
                        counts[family]["cited"] += bool(answered and response.get("sources") and response.get("evidence"))
                        counts[family]["verified_code"] += bool(response.get("verification", {}).get("passed"))
                        counts[family]["remedied_refusal"] += bool(not answered and response.get("how_to_resolve"))
                        target.write(json.dumps({"family": family, "prompt": prompt, "response": response,
                                                 "ms": round(elapsed, 3)}, ensure_ascii=False) + "\n")
                        target.flush()
            result["abilities"] = {family: dict(count, median_ms=round(statistics.median(timings[family]), 3))
                                   for family, count in counts.items()}
        summary[name] = result
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({name: result}, ensure_ascii=False), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sets", nargs="+", choices=SPENT, default=list(SPENT))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "docs/round4")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--documents-only", action="store_true")
    parser.add_argument("--abilities-only", action="store_true")
    args = parser.parse_args()
    run(tuple(args.sets), args.out, args.root, abilities=not args.documents_only, docs=not args.abilities_only)


if __name__ == "__main__":
    main()

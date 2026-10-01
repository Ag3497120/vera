"""Run an ability evaluation directory through one.Vera.chat.

Writes one answer per prompt. This is a development transcript, not a grade:
the judging notes are intentionally not read or used by the code.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path

from verantyx.one import Vera

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs/round2"
_TEXT_REFUSAL = re.compile(r"分かりません|わかりません|根拠が足りません|書かれていません|答えられません|確認できません")


def answered_check(text: str, verdict: str, kind: str) -> bool:
    if kind in ("unknown", "not_yet", "cannot", "unreadable") or verdict.startswith(
            ("UNKNOWN", "TIED", "NOT_IN_DOCS")):
        return False
    if _TEXT_REFUSAL.search(text) or text.strip() == "そうなんですね。":
        return False
    return True


def run(data: Path, output: Path) -> dict:
    files = sorted(data.glob("ab_*.json"))
    if not files:
        raise ValueError(f"no ab_*.json files in {data}")
    output.parent.mkdir(parents=True, exist_ok=True)
    vera = Vera()
    totals = defaultdict(lambda: {"answered": 0, "refused": 0, "ms": []})
    with output.open("w", encoding="utf-8") as out:
        for file in files:
            kind = file.stem.removeprefix("ab_")
            for entry in json.loads(file.read_text(encoding="utf-8"))["items"]:
                prompt = entry["prompt"]
                start = time.perf_counter()
                answer = vera.chat(prompt)
                ms = round((time.perf_counter() - start) * 1000, 3)
                verdict = str(answer.get("verdict", answer.get("kind", "")))
                refused = not answered_check(answer.get("text", ""), verdict,
                                             str(answer.get("kind", "")))
                row = {"kind": kind, "prompt": prompt, "answer": answer.get("text", ""),
                       "verdict": verdict,
                       "sources": answer.get("sources", []), "lines": answer.get("lines", []),
                       "trace": answer.get("trace", []), "ms": ms,
                       "self_check": {"answered": not refused},
                       "reference_hint": entry.get("reference", "")}
                out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                bucket = totals[kind]
                bucket["refused" if refused else "answered"] += 1
                bucket["ms"].append(ms)
    summary = {k: {"answered": v["answered"], "refused": v["refused"],
                   "median_ms": round(statistics.median(v["ms"]), 3)}
               for k, v in sorted(totals.items())}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {output}")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("data", nargs="?", type=Path, default=Path.home() / "Projects/vera-ja-sealed1")
    p.add_argument("--data", dest="data_option", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--phase", choices=("before", "after"), default="after")
    args = p.parse_args()
    data = (args.data_option or args.data).expanduser()
    output = args.out or DEFAULT_OUTPUT_DIR / f"{data.name}_abilities_{args.phase}.jsonl"
    run(data, output)


if __name__ == "__main__":
    main()

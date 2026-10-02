"""python -m tools.bank_score.recount <out>: results.jsonl（と戦略の results.jsonl）から summary を作り直して比べる。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .report import build_summary, read_jsonl, render_md
from .strategies import STRATEGIES, not_applicable


def recompute(out: Path) -> tuple[dict, str]:
    rows = read_jsonl(out / "results.jsonl")
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    bank = meta["bank"]
    strat = {}
    if meta.get("mode") != "judge":  # judge の出力（Vera を呼ばない判定だけ）に戦略は無い
        for s in STRATEGIES:
            if not_applicable(bank, s) is None:
                strat[s] = read_jsonl(out / "baselines" / s / "results.jsonl")
    summ = build_summary(bank, rows, strat, meta["quarantine"], meta.get("profile", "w1s"))
    if meta.get("mode") == "judge":
        from .judge import probes_block
        summ["probes"] = probes_block(rows)
    return summ, render_md(summ)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("使い方: python -m tools.bank_score.recount <out>", file=sys.stderr)
        return 2
    out = Path(argv[0])
    try:
        summ, md = recompute(out)
        stored = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        stored_md = (out / "summary.md").read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"読めない: {e}", file=sys.stderr)
        return 2
    ok_json = json.loads(json.dumps(summ, ensure_ascii=False)) == stored
    ok_md = (md + "\n") == stored_md
    print(f"recount {out}: summary.json {'一致' if ok_json else '不一致'} / summary.md {'一致' if ok_md else '不一致'}")
    return 0 if (ok_json and ok_md) else 1


if __name__ == "__main__":
    sys.exit(main())

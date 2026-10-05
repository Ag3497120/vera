"""W16-t8 (r2 optional 1, rebuilt in r3, docs/COARSE_PLACEMENT.md 12.21.7): a table of what a human's `set` alone and `set` + `frame` do to the sentences of a data set, so the effect of the frame row can be seen apart
from the effect of the type row.  Every confirmation is written the way a person does (``verantyx.cli.main``) into a temporary layer and ledger (a temporary directory, removed by the interpreter at exit).

  python tools/t8/set_only_vs_frame.py --placement P --data artifacts/w16-t8/data --out TABLE.tsv [--rows synthetic_frame.jsonl] [--predicate 移動する] [--type P_MOVE] [--particle へ] [--role goal] [--types GROUP_ORG]

Columns: group, text, base (no layer), set_only, set+frame.  A cell is ``READ`` or ``ABSTAIN <reasons joined by ;>``.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from typing import Any, Dict, Optional, Sequence

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.t8.t82_flow import _cli, _load, _read_all      # noqa: E402


def _cell(rd: Dict[str, Any]) -> str:
    return "READ" if rd.get("readable") else "ABSTAIN " + ";".join((rd.get("abstain") or {}).get("reasons") or [])


def build(placement: str, data_dir: str, rows_file: str, predicate: str, type_: str, particle: str, role: str, types: Sequence[str]) -> str:
    rows = _load(os.path.join(data_dir, rows_file))
    with tempfile.TemporaryDirectory() as tmp:
        layer, ledger = os.path.join(tmp, "l.sqlite"), os.path.join(tmp, "led.jsonl")
        base = _read_all(rows, placement, None)
        rc, o = _cli(["confirm", "set", predicate, type_, "--by", "set-only-vs-frame", "--layer", layer, "--ledger-file", ledger, "--placement", placement])
        if rc != 0:
            raise RuntimeError("CONFIRM_REFUSED:" + o)
        only = _read_all(rows, placement, layer)
        rc, o = _cli(["confirm", "frame", predicate, particle, role] + list(types) + ["--by", "set-only-vs-frame", "--layer", layer, "--ledger-file", ledger, "--placement", placement])
        if rc != 0:
            raise RuntimeError("CONFIRM_REFUSED:" + o)
        both = _read_all(rows, placement, layer)
    head = "# group\ttext\tbase\tset_only(%s %s)\tset+frame(%s %s %s)" % (predicate, type_, particle, role, "+".join(types))
    return "\n".join([head] + ["\t".join((r["group"], r["text"], _cell(b), _cell(o), _cell(f))) for r, b, o, f in zip(rows, base, only, both)]) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", default="synthetic_frame.jsonl")
    ap.add_argument("--predicate", default="移動する")
    ap.add_argument("--type", default="P_MOVE")
    ap.add_argument("--particle", default="へ")
    ap.add_argument("--role", default="goal")
    ap.add_argument("--types", nargs="+", default=["GROUP_ORG"])
    a = ap.parse_args(list(argv) if argv is not None else None)
    text = build(a.placement, a.data, a.rows, a.predicate, a.type, a.particle, a.role, a.types)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

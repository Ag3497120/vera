#!/usr/bin/env python3
"""影運用のログに verdict の行を追記する（entry の行は書き換えない）。

影運用の間、この道具の出力・記録で判断を変えない。verdict は人（監査役）が付ける。
route の entry には agree/disagree、ask の entry には correct/wrong。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common as C  # noqa: E402

ROUTE_VERDICTS = ("agree", "disagree")
ASK_VERDICTS = ("correct", "wrong")
SCHEMA = "vera.ops.shadow.verdict/1"


def kind_of(entry):
    s = str(entry.get("schema", ""))
    if s.startswith("vera.ops.shadow.route/"):
        return "route"
    if s.startswith("vera.ops.shadow.ask/"):
        return "ask"
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--verdict", required=True, choices=ROUTE_VERDICTS + ASK_VERDICTS)
    ap.add_argument("--by", required=True)
    ap.add_argument("--note")
    a = ap.parse_args(argv)
    found = None
    try:
        with open(a.log, encoding="utf-8") as f:
            for ln in f:
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("type") == "entry" and d.get("entry_id") == a.ref:
                    found = d
                    break
    except OSError:
        pass
    if found is None:
        print(json.dumps({"verdict": "UNKNOWN_REF", "ref": a.ref}))
        return 1
    k = kind_of(found)
    allowed = ROUTE_VERDICTS if k == "route" else ASK_VERDICTS if k == "ask" else ()
    if a.verdict not in allowed:
        print(json.dumps({"verdict": "VERDICT_KIND_MISMATCH", "entry_kind": k, "given": a.verdict}))
        return 1
    row = {"schema": SCHEMA, "type": "verdict", "ref": a.ref, "verdict": a.verdict, "by": a.by,
           "ts": C.now_ts(), "note": a.note}
    C.append_jsonl(a.log, row)
    print(json.dumps({"verdict": "VERDICT_RECORDED", "ref": a.ref, "value": a.verdict}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

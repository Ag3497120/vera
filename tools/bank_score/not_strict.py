"""python -m tools.bank_score.not_strict <judge の results.jsonl があるディレクトリ> [--tsv <出力>] [--agg <集計の出力>]

参考例（judge の probe=reference）のうち、回答側で主分類が correct でない問題を 1 問ずつ表にする（W1-s2 T2）。
1 行 = id / 主分類 / 理由 / 近似を当てた分類 / FAIL の規則 / UNJUDGED の規則（規則名:理由コード）/ 各 UNJUDGED 規則の surface_approx。
出力は id・規則名・ASCII のコードだけ（問題文・必須語は入らない）。公開側の results.jsonl（publish 後）から作れる。
集計（規則別・組み合わせ別の問題数、近似を当てた分類の内訳）は TSV には入れず `--agg`（省略すると集計は書かない）の別ファイルに書く。判定には何も使わない。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

CODE = re.compile(r"^[A-Z_]+$")
RULE = re.compile(r"^[a-z_0-9]+$")


def _code(x: object) -> str:
    return x if isinstance(x, str) and CODE.match(x) else "<redacted>"


def build(rows: list[dict]) -> tuple[list[str], dict]:
    sel = [r for r in rows if r.get("probe") == "reference" and r.get("side") == "answer" and r["class"] != "correct"]
    sel.sort(key=lambda r: (r.get("line") or 0, str(r["id"])))
    lines = ["id\tclass\treason\tclass_approx\tfail_rules\tunjudged_rules\tsurface_approx"]
    per_rule: Counter = Counter()
    per_combo: Counter = Counter()
    per_approx: Counter = Counter()
    for r in sel:
        ch = r["checks"]
        fails = sorted(k for k, c in ch.items() if c["result"] == "FAIL")
        unj = sorted(k for k, c in ch.items() if c["result"] == "UNJUDGED")
        for k in unj:
            if not RULE.match(k):
                raise SystemExit(f"規則名が想定外: {k!r}")
        unj_s = [f"{k}:{_code(ch[k]['detail'].get('reason'))}" for k in unj]
        ap_s = [f"{k}={ch[k]['detail'].get('surface_approx')}" for k in unj]
        per_rule.update(unj)
        per_combo[" + ".join(unj) or "(なし)"] += 1
        per_approx[str(r.get("class_approx"))] += 1
        lines.append("\t".join([str(r["id"]), r["class"], str(r.get("reason")), str(r.get("class_approx")),
                                ",".join(fails) or "-", ",".join(unj_s) or "-", ",".join(ap_s) or "-"]))
    agg = {"n": len(sel), "per_rule": dict(sorted(per_rule.items())), "per_combo": dict(sorted(per_combo.items())),
           "class_approx": dict(sorted(per_approx.items()))}
    return lines, agg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir", help="judge の出力（results.jsonl のあるディレクトリ）")
    ap.add_argument("--tsv", help="TSV の書き出し先（省略で標準出力）")
    ap.add_argument("--agg", help="集計の書き出し先")
    a = ap.parse_args(argv)
    rows = [json.loads(l) for l in (Path(a.dir) / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    lines, agg = build(rows)
    agg_lines = ["n=%d" % agg["n"], "per_rule=" + json.dumps(agg["per_rule"], ensure_ascii=False),
                 "per_combo=" + json.dumps(agg["per_combo"], ensure_ascii=False),
                 "class_approx=" + json.dumps(agg["class_approx"], ensure_ascii=False)]
    if a.agg:
        Path(a.agg).write_text("\n".join(agg_lines) + "\n", encoding="utf-8")
    text = "\n".join(lines) + "\n"
    if a.tsv:
        Path(a.tsv).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

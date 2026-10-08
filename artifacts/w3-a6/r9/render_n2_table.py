#!/usr/bin/env python3
"""Render the measured N2 run1/run2 claim, confirmation and support table."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6/r9"
ROWS = ART / "n2_run1_vs_run2.jsonl"
SUMMARY = ART / "n2_run1_vs_run2_summary.json"
OUT = ART / "n2_table_run1_vs_run2.md"


def role_result(run: dict) -> str:
    confirmed = run["confirmed_expected_role"]
    unconfirmed = run["unconfirmed_expected_role"]
    if confirmed:
        value = ", ".join(f"{item['role']}[{','.join(item['types'])}]" for item in confirmed)
        if unconfirmed:
            value += " + " + ", ".join(f"一部未確認:{item['why']}" for item in unconfirmed)
        return value
    if unconfirmed:
        return ", ".join(f"未確認:{item['why']}" for item in unconfirmed)
    return "期待役割なし"


def supports(run: dict) -> str:
    return "<br>".join(
        f"{item['source']} ({'+'.join(item['voted_types_for_expected_role'])})"
        for item in run["backing_arms"]
    ) or "—"


rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines() if line.strip()]
summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
lines = [
    "# N2 run1 / run2 申告・確認・根拠腕",
    "",
    "期待は10述語・11役割行。run1 は旧gen_role、run2 はgen_role_v2。目視期待ではなく、凍結試験データに対する配置出力の比較。",
    "",
    f"- run1: 期待役割の申告 {summary['run1']['claimed_expected_roles']}/11、確認 {summary['run1']['confirmed_expected_roles']}/11。",
    f"- run2: 期待役割の申告 {summary['run2']['claimed_expected_roles']}/11、確認 {summary['run2']['confirmed_expected_roles']}/11。",
    f"- run2で確認された期待役割の腕検査: {'全件通過' if summary['run2']['confirmed_backing_checks_pass'] else '不一致あり'}。",
    "- `confirmed` の型は確認済み型、`PARTLY_BACKED` は未確認型を表す。未確認行では分布根拠の一致を申告しない。",
    "",
    "|述語|助詞 / 期待役割|run1申告|run1確認|run1根拠腕・有意型|run2申告|run2確認|run2根拠腕・有意型|",
    "|---|---|---|---|---|---|---|---|",
]
for row in rows:
    r1, r2 = row["run1"], row["run2"]
    lines.append("|" + "|".join([
        row["predicate"],
        f"{row['particle']} / {row['expected_role']}",
        "はい" if r1["expected_role_claimed"] else "いいえ",
        role_result(r1),
        supports(r1),
        "はい" if r2["expected_role_claimed"] else "いいえ",
        role_result(r2),
        supports(r2),
    ]) + "|")
lines.extend([
    "",
    f"出典データ: `{ROWS.name}`。腕の有意型と票の対応は同ファイルの `backing_arms` に全文を保持。",
])
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"出力: {OUT}\n行数: {len(rows)}")

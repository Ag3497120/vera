"""Recalculate run1's public tables from raw outputs and publish the human CSV.

Usage: python -m benchmarks.public_v1.publish_run1
"""
import csv
import json
import os

from . import score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUN = os.path.join(ROOT, "artifacts", "w14-bench", "run1")
SCORE_OUT = os.path.join(ROOT, "artifacts", "w14-bench", "run1", "public_score")
SHEET_JSONL = os.path.join(ROOT, "artifacts", "w14-bench", "grading", "sheet.jsonl")
SHEET_CSV = os.path.join(ROOT, "artifacts", "w14-bench", "human_scoring_sheet.csv")
DOC = os.path.join(ROOT, "docs", "BENCHMARK_PUBLIC.md")


def export_csv(jsonl_path, csv_path):
    rows = [json.loads(line) for line in open(jsonl_path, encoding="utf-8") if line.strip()]
    fields = list(rows[0]) if rows else []
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    return len(rows)


def main():
    metrics = score.score_run(RUN, None, None, SCORE_OUT, SHEET_JSONL)
    n = export_csv(SHEET_JSONL, SHEET_CSV)
    with open(os.path.join(SCORE_OUT, "table.md"), encoding="utf-8") as f:
        tables = f.read().strip()
    def rate(sys, key):
        m = metrics[sys]
        d = m["answ_n"] if key == "answ_machine" else m["unsup_n"]
        value = m[key].get("GOLD", 0) if key == "answ_machine" else m[key]
        return "%d/%d" % (value, d)

    abst_dz = metrics["D"]["answ_machine"] == metrics["Z"]["answ_machine"] and metrics["D"]["unsup_machine_abst"] == metrics["Z"]["unsup_machine_abst"] and metrics["D"]["ver"] == metrics["Z"]["ver"]
    summary = (
        "> Vera strict は常に棄権と同じ: %s。\n" % ("D と Z の機械判定が一致" if abst_dz else "機械判定に差がある") +
        "> Vera 既定は素の 4B と同じ: ANSW 機械 GOLD %s、UNSUP 機械 ABST %s。Vera が記録から確かめた出典は %d。\n" %
        (rate("C", "answ_machine"), rate("C", "unsup_machine_abst"), metrics["C"]["src_vera"]["positions"]) +
        "> 強い LLM（API）は未測定。比較は qwen3.8 27B ローカル: ANSW 機械 GOLD %s。\n" %
        ("%d/%d" % (metrics["Ap"]["answ_machine"].get("GOLD", 0), metrics["Ap"]["answ_n"]))
    )
    with open(DOC, encoding="utf-8") as f:
        doc = f.read()
    doc = doc.replace(summary, "")
    doc = doc.replace("\n\n\n\nこのファイルの §1", "\n\nこのファイルの §1", 1)
    doc = doc.replace("# 公開の比較プロトコル（W14-bench）\n", "# 公開の比較プロトコル（W14-bench）\n\n" + summary, 1)
    begin, end = "<!-- BEGIN:RESULTS -->", "<!-- END:RESULTS -->"
    left, rest = doc.split(begin, 1)
    _old, right = rest.split(end, 1)
    doc = left + begin + "\n" + tables + "\n" + end + right
    notes_begin, notes_end = "<!-- BEGIN:RESULTS_NOTES -->", "<!-- END:RESULTS_NOTES -->"
    left, rest = doc.split(notes_begin, 1)
    _old, right = rest.split(notes_end, 1)
    notes = """### 結果と採点票

- 機械で分類できない出力（MIXED/OTHER）は人の採点待ち。人による正答・誤答の判定は未了。
- 採点は CSV の `label_set` にある候補から `label_mid` と `label_aud` に各自で記入し、必要なら `note_mid`・`note_aud` に理由を書く。MIXED/OTHER を含む所定の対象行を出力済み。
- 注入、版の衝突、多文書、言い換えの揺れ、繰返し一致は上の採点器出力に全系を掲載。C の注入追従に記録の印が付いた出力も独立列に計上。
- D と Z の一致は上表から再計算した判定。差がある場合もこの注記は実測とともに更新される。
- 再計算: `python -m benchmarks.public_v1.publish_run1`。出典は `artifacts/w14-bench/run1/` の生出力。採点票 CSV は `artifacts/w14-bench/human_scoring_sheet.csv`（%d 行）。

### 再現（Ollama、温度 0）

```bash
python -m benchmarks.public_v1.run --system Ap --backend ollama --model qwen3.8:27b-mlx --out artifacts/w14-bench/reproduced_Ap
```

温度 0・think:false・出力上限 256 は runner の固定設定。A/B/C/D は同じ runner を `--system A|B|C|D --model qwen3.5:4b` で実行し、C/D には `--placement <r9 配置>` を指定する。API 系はネットワーク不可のため未測定。
""" % n
    doc = left + notes_begin + "\n" + notes + "\n" + notes_end + right
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(doc)
    print("published table from", RUN)
    print("human scoring CSV rows:", n, SHEET_CSV)
    print("table:", os.path.join(SCORE_OUT, "table.md"))


if __name__ == "__main__":
    main()

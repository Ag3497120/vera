"""python -m tools.bank_score.baseline_compare: 自明な戦略の点数と、設計者の baseline.json の点数の比較表（W1-s2 T3）。

こちらの値は summary.json の `baselines.strategies.<s>.pass_rate`（(正答＋正しい棄権)/全問）。B3 は読解器が要る規則を
表層近似で置き換えた値（`pass_rate_approx`）を、設計者の lenient と並べる（設計者の upper も併記）。
設計者の値の場所は固定（下の表）。見つからないときは推測せず「見つからない」と出して終了コード 1。
差が 5 ポイント以内なら OK、超えたら「要説明」（問題単位の原因は xcheck の mismatches.jsonl で書く）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THRESHOLD_POINTS = 5.0

# バンク → [(こちらの戦略, 設計者の戦略名, 設計者の値の場所を返す関数, 定義の違い)]
def _b1(d: dict, key: str) -> float:
    return d["after_quarantine"][key]["accuracy"]


def _b2(d: dict, key: str) -> float:
    return d["retained_after_quarantine"]["table"][key]["pct_of_bank"] / 100.0


def _b3(mode: str):
    def f(d: dict, key: str) -> float:
        return d["after_quarantine"]["strategies"][key][mode]["rate"]
    return f


def _b5(d: dict, key: str) -> float:
    # 旧形式（baseline.json: 最上位に strategies）と r3 形式（baseline_r3.json・sim/r3_fix_baseline.json: all / after_quarantine の下）の両方
    sec = d["after_quarantine"] if "after_quarantine" in d else d
    return sec["strategies"][key]["rate"]


SPEC = {
    "B1": [("always_abstain", "BL-F", _b1, "どちらも常に棄権"),
           ("empty", "BL-EMPTY", _b1, "どちらも readable:true・節なし"),
           ("echo_input", "BL-COPY", _b1, "こちらは述語＝入力、設計者は entity＝入力・述語＝文末の語（どちらも正答 0 の見込み）")],
    "B2": [("always_abstain", "S2_always_abstain", _b2, "どちらも空本文・棄権状態"),
           ("empty", "S1_empty", _b2, "どちらも空本文・回答状態"),
           ("echo_input", "S3_echo_last_user", _b2, "最後の user 発話の丸写し"),
           ("echo_documents", "S4_all_docs_or_users", _b2, "設計者は文書が無ければ全 user 発話、こちらは空"),
           ("all_labels", "S8_all_three_labels", _b2, "3 ラベルの列挙")],
    "B3": [("empty", "SB0", None, "どちらも空本文"),
           ("always_abstain", "SB1", None, "どちらも常に拒否"),
           ("echo_documents", "SB2", None, "設計者は材料が空なら依頼文、こちらは空"),
           ("echo_input", "SB5", None, "依頼文の丸写し")],
    "B5": [("always_abstain", "s_always_escalate", _b5, "どちらも常に escalate"),
           ("first_option", "s_first", _b5, "設計者は自由記述に質問文を返す、こちらは空"),
           ("empty", "s_empty_output", _b5, "どちらも空出力"),
           ("all_labels", "s_enumerate_labels", _b5,
            "設計者は自由記述に全相名と決定値を返す（設計者 4 問正答）、こちらは選択肢の列挙で自由記述は空")],
}


def rows_for(bank: str, summ: dict, designer: dict) -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    missing: list[str] = []
    strategies = summ["baselines"]["strategies"]
    for ours_name, dname, getter, note in SPEC[bank]:
        e = strategies.get(ours_name)
        if not e or not e.get("applicable"):
            missing.append(f"こちらの戦略 {ours_name} が要約に無い（対象外）")
            continue
        variants = [("", getter, e["pass_rate"])]
        if bank == "B3":
            variants = [("lenient", _b3("lenient"), e.get("pass_rate_approx")),
                        ("upper", _b3("upper"), e["pass_rate"])]
        for label, fn, ours in variants:
            try:
                theirs = fn(designer, dname)
            except (KeyError, TypeError):
                missing.append(f"設計者の値が見つからない: {dname}{'/' + label if label else ''}")
                continue
            if ours is None:
                missing.append(f"こちらの値が無い: {ours_name}")
                continue
            diff = round((ours - theirs) * 100.0, 3)
            out.append({"bank": bank, "ours": ours_name, "designer": dname + (f"/{label}" if label else ""),
                        "ours_rate": ours, "designer_rate": theirs, "diff_points": diff,
                        "ok": abs(diff) <= THRESHOLD_POINTS, "note": note,
                        "ours_value_is": ("近似を当てた通過率（pass_rate_approx）" if label == "lenient" else
                                          "主分類の通過率（UNJUDGED は通過に数えない）" if label == "upper" else "通過率（pass_rate）")})
    return out, missing


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.bank_score.baseline_compare")
    ap.add_argument("--bank", required=True, choices=list(SPEC))
    ap.add_argument("--summary", required=True)
    ap.add_argument("--designer-baseline", required=True)
    args = ap.parse_args(argv)
    try:
        summ = json.loads(Path(args.summary).read_text(encoding="utf-8"))
        des = json.loads(Path(args.designer_baseline).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"読めない: {e}", file=sys.stderr)
        return 2
    rows, missing = rows_for(args.bank, summ, des)
    print(f"# {args.bank}（こちら: {args.summary} / 設計者: {args.designer_baseline}、全問 {summ['total']}）")
    print("こちらの戦略 | 設計者の戦略 | こちら | 設計者 | 差（ポイント） | 判定 | 定義の違い")
    for r in rows:
        print(f"{r['ours']} | {r['designer']} | {r['ours_rate'] * 100:.2f}% | {r['designer_rate'] * 100:.2f}% | "
              f"{r['diff_points']:+.2f} | {'OK' if r['ok'] else '要説明'} | {r['note']}（こちらの値: {r['ours_value_is']}）")
    for m in missing:
        print(f"見つからない: {m}")
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"OK {n_ok} / {len(rows)}（5 ポイント以内）。要説明 {len(rows) - n_ok}。")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

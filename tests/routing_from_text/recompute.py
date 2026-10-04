"""Rebuild the measured section of docs/ROUTING_FROM_TEXT.md (between ``<!-- recompute:begin -->`` and ``<!-- recompute:end -->``) from
the files of artifacts/w2-h2/, and compare.  Every number of the docs is inside that section.

    python tests/routing_from_text/recompute.py --check    # prints OK or MISMATCH (and the first differing line); exit 1 on a mismatch
    python tests/routing_from_text/recompute.py --write    # rewrites the section (after a measurement)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A = os.path.join(ROOT, "artifacts", "w2-h2")
DOC = os.path.join(ROOT, "docs", "ROUTING_FROM_TEXT.md")
BEGIN, END = "<!-- recompute:begin -->", "<!-- recompute:end -->"


def read(name):
    path = os.path.join(A, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def js(name):
    text = read(name)
    return None if text is None else json.loads(text)


def bank_block(title, source, summary):
    if summary is None:
        return [f"### {title}", "", f"(未測定: {source})", ""]
    lines = [f"### {title}（出典: {source}）", "",
             f"問い {summary['items']}（実行の失敗 {summary['errors']}）。", "",
             "|  | 問い | 正しく振った | 棄権した | 別の呼び名に振った | undecided と答えた | 呼び名を返した |", "|---|---|---|---|---|---|---|",
             f"| route が正解 | {summary['route_expected']} | {summary['route_correct']} | {summary['route_abstained']} | {summary['route_wrong_agent']} | - | - |",
             f"| undecided が正解 | {summary['undecided_expected']} | - | - | - | {summary['undecided_correct']} | {summary['undecided_got_agent']} |", "",
             f"誤って振った数（undecided が正解で呼び名を返した数 ＋ route が正解で別の呼び名を返した数）: **{summary['misroutes']}**",
             f"正答の合計: {summary['correct_total']} / {summary['items']}（常に棄権すれば {summary['always_abstain_correct']}）",
             f"`undecided_reason` の分布: {json.dumps(summary['undecided_reason'], ensure_ascii=False)}",
             f"`abstention.type` の分布: {json.dumps(summary['abstention_type'], ensure_ascii=False)}",
             f"`basis_kind` の分布: {json.dumps(summary['basis_kind'], ensure_ascii=False)}", "",
             "| 説明文 | 単位 | 読めて写せた単位 | 状態の内訳 | 問い |", "|---|---|---|---|---|"]
    for key, entry in summary["per_explanation"].items():
        by = entry["by_status"] or {}
        read_n = by.get("MAPPED", 0) + by.get("COMPARISON_ONLY", 0)
        shown = ", ".join(f"{k} {v}" for k, v in by.items() if v)
        lines.append(f"| {key} | {entry['units']} | {read_n} | {shown} | {entry['questions']} |")
    return lines + [""]


def last_line(name):
    text = read(name)
    if text is None:
        return None
    rows = [row for row in text.strip().splitlines() if row.strip()]
    return rows[-1] if rows else None


def build():
    out = []
    frozen = (read("constants_frozen.txt") or "").splitlines()
    if len(frozen) >= 3:
        out += ["### 定数の表の凍結（出典: artifacts/w2-h2/constants_frozen.txt）", "",
                f"凍結の日時: {frozen[0]}", f"sha256: `{frozen[1]}`", f"表の項目数: {frozen[2]}", ""]
    else:
        out += ["### 定数の表の凍結", "", "(未測定: constants_frozen.txt)", ""]
    first = (read("first_run_at.txt") or "").strip()
    out += [f"検査データの最初の実行の日時（出典: artifacts/w2-h2/first_run_at.txt）: {first or '(未測定)'}", ""]
    out += bank_block("自作の検査データ（本体: e1〜e6）", "artifacts/w2-h2/data_run/summary.json", js("data_run/summary.json"))
    out += bank_block("読解器が読める形の説明文（reader_shaped: r1・r2。本体の数とは別）", "artifacts/w2-h2/data_run_reader_shaped/summary.json",
                      js("data_run_reader_shaped/summary.json"))
    out += bank_block("中間職の task（本体 e1〜e6。レビュー第 1 ラウンドで中間職が書いて凍結）", "artifacts/w2-h2/data_run_mid/summary.json",
                      js("data_run_mid/summary.json"))
    out += bank_block("中間職の task（reader_shaped: r1・r2）", "artifacts/w2-h2/data_run_mid_reader_shaped/summary.json",
                      js("data_run_mid_reader_shaped/summary.json"))
    gaps = js("reader_gaps.json")
    if gaps is None:
        out += ["### 読めなかった単位", "", "(未測定: reader_gaps.json)", ""]
    else:
        units = gaps["units_all"]
        out += ["### 読めなかった単位（出典: artifacts/w2-h2/reader_gaps.json。説明 8 本の全単位）", "",
                f"単位 {units['units']}。状態: " + ", ".join(f"{k} {v}" for k, v in units["by_status"].items() if v) + "。",
                "読解器の理由別（`UNREAD` の最初の理由）: " + ", ".join(f"{k} {v}" for k, v in gaps["unread_reasons_all"].items()) + "。", ""]
    words = js("t4_text_words.txt")
    out += ["### 話題専用の規則が無いことの機械の確認（出典: artifacts/w2-h2/t4_text_words.txt, t4_grep.txt）", ""]
    if words is None:
        out += ["(未測定)", ""]
    else:
        out += [f"検査データの呼び名（`check_no_text_words.py`）: {len(words['names_checked'])} 個、そのうち `routing_from_text.py` に現れたもの（失敗）: "
                f"{len(words['failures'])} 個。説明文の語のうちモジュールに現れたもの: {len(words['explanation_words_in_the_module'])} 語"
                f"（うち定数の表の項目: {sum(1 for v in words['explanation_words_in_the_module'].values() if not v.startswith('('))} 語）。", ""]
    grep = read("t4_grep.txt")
    if grep is not None:
        sections, name = {}, None
        for row in grep.splitlines():
            if row.startswith("## "):
                name = row
                sections[name] = []
            elif name and row.strip():
                sections[name].append(row)
        for key, rows in sections.items():
            if key.startswith("## re の使用") or key.startswith("## RoutingTable") or key.startswith("## used_lineages"):
                out.append(f"- {key[3:]}: {len(rows)} 行")
        out.append("")
    c0 = (read("c0.txt") or "").strip()
    out += ["### 読み込み先（出典: artifacts/w2-h2/c0.txt）", "", f"`{c0 or '(未測定)'}`", ""]
    out += ["### 試験（出典: artifacts/w2-h2/pytest_unit.txt, pytest_full.txt, new_failures.txt, check_hardcode.txt）", ""]
    for label, name in (("新しい試験", "pytest_unit.txt"), ("全体試験の最終行", "pytest_full.txt")):
        row = last_line(name)
        out.append(f"- {label}: `{row or '(未測定)'}`")
    new = read("new_failures.txt")
    if new is None:
        out.append("- 基線にない失敗: (未測定)")
    else:
        ids = [row.strip() for row in new.splitlines() if row.strip()]
        out.append(f"- 基線にない失敗: {len(ids)} 件" + ("" if not ids else "（" + "; ".join(ids) + "）"))
    hard = (read("check_hardcode.txt") or "").splitlines()[:3]
    out.append("- 決め打ち検査（新規ファイルの全行を足して流した出力）: " + (" / ".join(row.strip() for row in hard) if hard else "(未測定)"))
    return "\n".join(out).rstrip() + "\n"


def current():
    with open(DOC, encoding="utf-8") as handle:
        text = handle.read()
    if BEGIN not in text or END not in text:
        return text, None
    head, rest = text.split(BEGIN, 1)
    body, tail = rest.split(END, 1)
    return text, (head, body.strip("\n") + "\n", tail)


def main(argv):
    text, parts = current()
    if parts is None:
        print("MISMATCH: the markers are missing")
        return 1
    built = build()
    if "--write" in argv:
        head, _body, tail = parts
        with open(DOC, "w", encoding="utf-8") as handle:
            handle.write(head + BEGIN + "\n" + built + END + tail)
        print("WRITTEN")
        return 0
    if built == parts[1]:
        print("OK")
        return 0
    for number, (a, b) in enumerate(zip(built.splitlines(), parts[1].splitlines()), start=1):
        if a != b:
            print(f"MISMATCH at line {number} of the section:\n  built: {a}\n  docs:  {b}")
            return 1
    print("MISMATCH: the sections differ in length")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

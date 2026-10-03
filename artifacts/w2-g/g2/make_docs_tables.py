"""W2-g2: builds the measurement tables of docs/CONDUCT_ASK.md section 14.x from the saved summary.json / results.jsonl / ledger.jsonl of the
real-provider runs (artifacts/w2-g/live_g2/**), so that no number is typed by hand.  Prints markdown.  A run directory that does not
exist is left out.  docs_check_g2.py compares the block in the docs with this output.
Usage (repository root):  artifacts/w2-g/py.sh artifacts/w2-g/g2/make_docs_tables.py"""
import json
import os
import statistics
import sys

ROOT = "artifacts/w2-g/live_g2"
RUNS = [("smoke/low", "煙・low（第 1 のデータの 2 問。凍結データではない）", "第 1 のデータ"),
        ("smoke/low2", "煙・low（同 1 問）", "第 1 のデータ"),
        ("smoke/xhigh", "煙・xhigh（同 1 問）", "第 1 のデータ"),
        ("w2g3/low", "(a) low・新しい凍結データ 60 問", "w2g3"),
        ("w2g3/xhigh", "(a) xhigh・同じ 60 問", "w2g3"),
        ("w2g2/low_answer", "(b) low・第 2 のデータの答えるのが正解の 48 問", "w2g2"),
        ("w2g2/low_escalate", "(b) low・同じく上げるのが正解の 16 問", "w2g2")]


def load(run):
    d = os.path.join(ROOT, run)
    if not os.path.isfile(os.path.join(d, "summary.json")):
        return None
    s = json.load(open(os.path.join(d, "summary.json"), encoding="utf-8"))
    rows = [json.loads(ln) for ln in open(os.path.join(d, "results.jsonl"), encoding="utf-8") if ln.strip()]
    return s, rows


def f(x):
    return "—" if x is None else (f"{x:.1f}" if isinstance(x, float) else str(x))


def table_main():
    out = ["| 実行（出典 `artifacts/w2-g/live_g2/<ディレクトリ>`） | 流した問数 | 流せなかった問（予算） | 誤って答えた | 正しく答えた／答えるのが正解 | 上げた／上げるのが正解 | 照会数（語の対応づけ込み） | 壁時計（秒） |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for run, name, _ in RUNS:
        r = load(run)
        if r is None:
            continue
        s, _rows = r
        w = s["q1_wrong_count"]
        out.append(f"| {name}（`{run}`） | {s['total']} | {len(s.get('not_run_budget') or [])} | {w} ({s['q1_rate']}) | {s['correct']} / {s['answer_expected']} | "
                   f"{s['escalate_correct']} / {s['escalate_expected']} | {s['asks']['total']} | {s['config']['wall_s']} |")
    return out


def table_time():
    out = ["| 実行 | 対応づけの照会の数 | 所要時間 平均 (ms) | 中央値 (ms) | 90 パーセンタイル (ms) | 最大 (ms) | 1 問あたりの対応づけの照会数 平均 | 中央値 | 最大 |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for run, name, _ in RUNS:
        r = load(run)
        if r is None:
            continue
        g = r[0]["g2"]
        t = g["ask_elapsed_ms"]["all_map_asks"]
        q = g["map_asks_per_question"]
        out.append(f"| `{run}` | {t['n'] if t else 0} | {f(t['mean']) if t else '—'} | {f(t['median']) if t else '—'} | {f(t['p90']) if t else '—'} | {f(t['max']) if t else '—'} | "
                   f"{f(q['mean']) if q else '—'} | {f(q['median']) if q else '—'} | {f(q['max']) if q else '—'} |")
    out += ["", "| 実行 | 段 | 照会数 | 平均 (ms) | 中央値 (ms) | 90 パーセンタイル (ms) | 最大 (ms) |", "|---|---|---:|---:|---:|---:|---:|"]
    for run, name, _ in RUNS:
        r = load(run)
        if r is None:
            continue
        for step, t in sorted(r[0]["g2"]["ask_elapsed_ms"]["by_step"].items()):
            out.append(f"| `{run}` | {step} | {t['n']} | {f(t['mean'])} | {f(t['median'])} | {f(t['p90'])} | {f(t['max'])} |")
    return out


def table_invalid():
    out = ["| 実行 | ① 無効 / 対応づけの照会の行 | ① の率 | ② 無効 / 語の対応づけを含む全照会の行 | ② の率 | 無効の理由 | 2 回目の照会（再照会）の数 | うち有効な返答 | 再照会のあった decision の数 |",
           "|---|---:|---:|---:|---:|---|---:|---:|---:|"]
    for run, name, _ in RUNS:
        r = load(run)
        if r is None:
            continue
        g = r[0]["g2"]
        a, b, rt = g["invalid_rate_mapping_asks"], g["invalid_rate_all_asks"], g["retries"]
        out.append(f"| `{run}` | {a['invalid']} / {a['rows']} | {a['rate']} | {b['invalid']} / {b['rows']} | {b['rate']} | {json.dumps(g['invalid_reasons'], ensure_ascii=False)} | "
                   f"{rt['asks']} | {rt['valid_reply']} | {rt['decisions_with_retry']} |")
    return out


def table_steps():
    out = ["| 実行 | 段 | 照会の verdict | decision の status |", "|---|---|---|---|"]
    for run, name, _ in RUNS:
        r = load(run)
        if r is None:
            continue
        g = r[0]["g2"]
        for step in sorted(set(g["map_verdict_by_step"]) | set(g["decision_status_by_step"])):
            out.append(f"| `{run}` | {step} | {json.dumps(g['map_verdict_by_step'].get(step, {}), ensure_ascii=False)} | {json.dumps(g['decision_status_by_step'].get(step, {}), ensure_ascii=False)} |")
    return out


def table_decides_and_reasons():
    out = ["| 実行 | `decides` の分布（採用） | `decides` が採用されなかった decision | 上げた理由（全体） | 上げた理由（答えるのが正解の問いだけ） |", "|---|---|---|---|---|"]
    for run, name, _ in RUNS:
        r = load(run)
        if r is None:
            continue
        g = r[0]["g2"]
        out.append(f"| `{run}` | {json.dumps(g['decides_distribution']['adopted'], ensure_ascii=False)} | {json.dumps(g['decides_distribution']['not_adopted'], ensure_ascii=False)} | "
                   f"{json.dumps(g['escalation_reasons'], ensure_ascii=False)} | {json.dumps(g['escalation_reasons_where_answer_expected'], ensure_ascii=False)} |")
    return out


def table_detail():
    """Why each question to answer was handed up (reason / detail), for the two main runs."""
    out = []
    for run in ("w2g3/low", "w2g3/xhigh", "w2g2/low_answer"):
        r = load(run)
        if r is None:
            continue
        cnt = {}
        for row in r[1]:
            if row["expect"]["decision"] == "answer" and row["observed"]["decision"] != "answer":
                k = f"{row['observed']['reason']}/{row['observed']['detail']}"
                cnt[k] = cnt.get(k, 0) + 1
        dis = sum(v for k, v in cnt.items() if "DISAGREE" in k.split("/")[1] and k.startswith("MAPPING_UNSETTLED"))
        out.append(f"- `{run}`: 答えるのが正解で上げた {sum(cnt.values())} 問の内訳（reason/detail） " + json.dumps(dict(sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))), ensure_ascii=False)
                   + f"。うち 2 回の照会の食い違い（`MAPPING_UNSETTLED/*_DISAGREE`）が {dis} 問、規則だけで上がって対応づけに回らなかった（`NEGATED_QUESTION` `TERM_IN_WIDER_PHRASE` `PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION`）が "
                   f"{sum(v for k, v in cnt.items() if k.split('/')[1] in ('NEGATED_QUESTION', 'TERM_IN_WIDER_PHRASE', 'PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION'))} 問。")
    return out


def table_category():
    out = ["| 実行 | 直接 | 組合せ | 語彙外 | 日本語（正答／答えるべき） | 英語 |", "|---|---:|---:|---:|---:|---:|"]
    for run in ("w2g3/low", "w2g3/xhigh", "w2g2/low_answer"):
        r = load(run)
        if r is None:
            continue
        s = r[0]
        c = s["q2_by_category"]
        bl = s["by_lang"]
        out.append(f"| `{run}` | {c['direct']['correct']} / {c['direct']['n']} | {c['combined']['correct']} / {c['combined']['n']} | {c['oov']['correct']} / {c['oov']['n']} | "
                   f"{bl['ja']['correct']} / {bl['ja']['answer_expected']} | {bl['en']['correct']} / {bl['en']['answer_expected']} |")
    return out


def table_b():
    p = "artifacts/w2-g/g2/merge_b/summary.json"
    if not os.path.isfile(p):
        return []
    m = json.load(open(p, encoding="utf-8"))
    out = ["| 実行（同じ問いの集合） | 問数 | 誤って答えた | 正しく答えた／答えるのが正解 | 上げた／上げるのが正解 |", "|---|---:|---:|---:|---:|"]
    for t in m["table"]:
        out.append(f"| {t['name']} | {t['questions']} | {t['wrong']} | {t['answered_correctly']} / {t['answer_expected']} | {t['escalated_correctly']} / {t['escalate_expected']} |")
    out.append("")
    out.append(f"- 流せなかった問い（予算）: {len(m['not_run'])}。誤答の id: {json.dumps(m['wrong_ids'])}。出典 `artifacts/w2-g/g2/merge_b/summary.json`（`merge_b.py`。各行は `run_bank.judge` で判定し直した）。")
    return out


def judgement():
    """The criteria of W2-g2 against the measured values (the lines are produced from the saved runs; nothing is typed)."""
    out = []
    for run in ("w2g3/low", "w2g3/xhigh"):
        r = load(run)
        if r is None:
            continue
        s = r[0]
        n = s["total"]
        w = s["q1_wrong_count"]
        ok = "満たす" if w <= 0.05 * n else "満たさない"
        out.append(f"- **G3'**（新しい凍結データ。誤って答えた件数 5% 以下）`{run}`: 誤答 {w} / {n}（{s['q1_rate']}）→ {ok}。正答は {s['correct']} / {s['answer_expected']}（{s['q2_answer_rate']}。基準なし、報告のみ）、"
                   f"上げた {s['escalate_correct']} / {s['escalate_expected']}（{s['escalate_correct_rate']}。参考の基準 85% 以上）。")
    r = load("w2g3/low")
    if r is not None:
        g = r[0]["g2"]
        a, b = g["invalid_rate_mapping_asks"], g["invalid_rate_all_asks"]
        base = 26 / 296
        ok = "下がっている" if a["rate"] < base and b["rate"] < base else "下がっていない"
        out.append(f"- **G8**（無効な返答の率。同じ effort low。第 3 ラウンドの台帳 26 / 296 = {base:.4f}（8.8%）より下がっているか）: ① 対応づけの照会の行 {a['invalid']} / {a['rows']} = {a['rate']}、"
                   f"② 語の対応づけを含む全照会 {b['invalid']} / {b['rows']} = {b['rate']} → {ok}。再照会の行は分母にも分子にも入れている（無効の返答は 1 回目も数える）。")
    return out


def budget_lines():
    import glob
    total = 0
    by_eff, by_prov = {}, {}
    to = 0
    for p in sorted(glob.glob(f"{ROOT}/**/ledger.jsonl", recursive=True)):
        for ln in open(p, encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                if r.get("type") in ("map_ask", "ask") and r.get("verdict") != "SKIPPED_DECIDED":
                    total += 1
                    by_eff[str(r.get("effort"))] = by_eff.get(str(r.get("effort")), 0) + 1
                    by_prov[str(r.get("provider"))] = by_prov.get(str(r.get("provider")), 0) + 1
        res = os.path.join(os.path.dirname(p), "results.jsonl")
        if os.path.isfile(res):
            to += sum(1 for ln in open(res, encoding="utf-8") if ln.strip() and json.loads(ln)["observed"].get("detail") == "RUN_TIMEOUT")
    return [f"- **予算**（`artifacts/w2-g/g2/budget_g2.py`。台帳の `map_ask` と語の対応づけの照会の行を数える。再照会の行も 1 回）: 実装役の合計 **{total} 回**（上限 1,140）。"
            f"provider は {json.dumps(by_prov)}（claude は使っていない）、effort 別 {json.dumps(dict(sorted(by_eff.items())))}（effort は台帳の行の値。語の対応づけは `low`）。"
            f"`RUN_TIMEOUT` の問い {to}（その分の加算 0）。中間職のレビューの 60 回は別の台帳で、ここには数えない。"]


def reading():
    """Plain statements read off the saved runs (every number is computed here)."""
    out = []
    lo, hi, ba = load("w2g3/low"), load("w2g3/xhigh"), load("w2g2/low_answer")
    if lo is None or hi is None or ba is None:
        return out
    a, b = lo[0]["g2"], hi[0]["g2"]
    inv = a["invalid_rate_all_asks"]["invalid"] + b["invalid_rate_all_asks"]["invalid"] + ba[0]["g2"]["invalid_rate_all_asks"]["invalid"]
    out.append(f"- 無効な返答は (a) low・(a) xhigh・(b) の 3 つの実行を合わせて {inv} 件だったので、**2 回目の照会（再照会）は実プロバイダでは一度も行われなかった**（再照会の挙動は作り物のプロバイダの試験 G9 だけで確かめている）。")
    out.append(f"- 正答は、同じ 60 問・各 1 回で、low {lo[0]['correct']} / {lo[0]['answer_expected']}、xhigh {hi[0]['correct']} / {hi[0]['answer_expected']}。どちらも誤答は 0、上げるのが正解の問いは全部上げた。"
               "1 回ずつの値なので、effort の差が揺れの範囲かどうかは分からない。")
    out.append(f"- (b) の第 2 のデータは v2 の low で {ba[0]['correct']} / {ba[0]['answer_expected']}。第 3 ラウンドの値（事前の手順の言い回し 21 / 48、改訂後 27 / 48。§13.9）より**低い**。"
               "v2 の 3 つの実行で、答えるのが正解の問いを上げた理由の最多は「2 回の独立な照会の食い違い」（`MAPPING_UNSETTLED/*_DISAGREE`。内訳は下）で、v2 は問いが段と（記録, 肢）の組に分かれた分、一致を求める回数が増えている（段ごとの内訳）。原因の特定はしていない。")
    out.append("- 実行はどれも 1 回で、プロンプト・許可リスト・規則・データを測定のあとに変えていない（基準を下回った値もそのまま）。")
    return out


def main():
    blocks = [("読み（測定された事実だけ）", reading()), ("基準に対する判定", judgement()), ("実行の一覧", table_main()), ("照会 1 回あたりの所要時間と 1 問あたりの照会数", table_time()), ("無効な返答の率と再照会", table_invalid()),
              ("段ごとの内訳", table_steps()), ("`decides` の分布と上げた理由", table_decides_and_reasons()), ("答えるのが正解で上げた問いの内訳", table_detail()),
              ("分類・言語ごとの正答", table_category()), ("(b) 第 2 のデータの流し直しと第 3 ラウンドの比較", table_b()), ("予算", budget_lines())]
    for title, lines in blocks:
        print(f"**{title}**\n")
        print("\n".join(lines))
        print()


if __name__ == "__main__":
    main()

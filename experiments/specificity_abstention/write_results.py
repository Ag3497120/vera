"""Render every measured probe and transition, without recomputing the experiment."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def main():
    data = json.loads((HERE / "results.json").read_text())
    rows = data["rows"]
    lab = json.loads((HERE / "lab_result.json").read_text())
    guard = json.loads((HERE / "guard_result.json").read_text())
    lines = []
    def add(s=""):
        lines.append(s)
    def table(headers, records):
        add("| " + " | ".join(headers) + " |")
        add("| " + " | ".join("---" for _ in headers) + " |")
        for record in records:
            add("| " + " | ".join(cell(v) for v in record) + " |")
        add()
    def result(r, arm):
        x = r["arms"][arm]
        return f"{x['category']} / {x['result']['verdict']} / {x['result']['core'] or '—'}"
    def evidence(r, arm):
        x = r["arms"][arm]["evidence"]
        if not x["evaluated"]:
            return "対象外（元が非ANSWER）"
        return f"{x['numerator']}/{x['denominator']}; 覆った語={','.join(x['covered']) or '∅'}"

    add("# 実測: 選択済み核の facet 被覆による棄権")
    add()
    add("主判定: **" + ("全条件PASS（この実験条件で支持）" if data["primary_pass"] else "不採択") + "**。")
    add("事前登録の閾値 1/20 を一度だけ測定した。結果を見た後の閾値変更・再測定は行っていない。")
    add("実装は実験ディレクトリの `adjudicate.py` と `run_specificity.py` にあり、本番への配線は行っていない。")
    add()
    add("## 実行の同定と凍結")
    add()
    table(["項目", "実測・保存値"], [
        ["実行コマンド", "python3.11 experiments/specificity_abstention/run_specificity.py"],
        ["開始 UTC", data["started_utc"]], ["終了 UTC", data["finished_utc"]],
        ["経過秒", data["elapsed_s"]], ["HEAD", data["git_head"]],
        ["seed", data["seed"]], ["抽出核数", len(data["population"])],
        ["評価問数", len(rows)], ["生成不能除外", len(data["excluded"])],
        ["ja 核数", data["n_cores"]], ["DB", data["db"]],
        ["DB SHA-256 前", data["db_sha256_before"]],
        ["DB SHA-256 後", data["db_sha256_after"]],
        ["PREREG SHA-256", data["prereg_sha256"]]])
    add("seed は登録前に experiments と指定 memory の py/md/json を検索して未出現を確認した。")
    add("未使用 seed であることと、過去の標本との核の完全非重複とは区別する。後者は主張しない。")
    add("利用した verantyx 全 Python ソースと治具・裁定の SHA-256 は `results.json:source_sha256` に保存した。")
    integrity = json.loads((HERE / "source_integrity.json").read_text())
    add(f"測定後に照合した {len(integrity['checked_paths'])} ソースのハッシュと PREREG はすべて不変。照合結果は `source_integrity.json` に保存。")
    add()
    add("## 四腕の成績（数値は results.json の実測のみ）")
    add()
    keys = ["asked", "correct", "wrong", "refusal", "reachable", "junk_top1", "junk_present", "empty_candidates"]
    table(["腕", "問数", "正", "誤", "棄", "到達", "junk先頭", "junk含有", "空候補"],
          [[a] + [v[k] for k in keys] for a, v in data["arms"].items()])
    add("baseline/specificity は現行候補、no_junk/no_junk_specificity は取得後に junk を除いた候補を使う。")
    add("補助腕は残枠を補充せず、store の全入口を塞いだ WIRE3 の再現とは扱わない。")
    add("全腕は同じ store の candidates_appended → score_facets → shell → run_consensus を通る。")
    add("同じ候補条件内では合意結果を一度だけ計算し、裁定の有無を比較する。")
    add("空候補を除外した過去の治具と異なり、今回は登録どおり空候補も UNKNOWN_NO_EVIDENCE として全腕の分母に残した。")
    add()
    add("## 事前登録の主判定線")
    add()
    b, s = data["arms"]["baseline"], data["arms"]["specificity"]
    expressions = {"WRONG_DOWN": f"{s['wrong']} < {b['wrong']}",
                   "REFUSAL_NOT_WORSE": f"{s['refusal']} ≥ {b['refusal']}",
                   "CORRECT_NOT_WORSE": f"{s['correct']} ≥ {b['correct']}",
                   "PATH_MATCH": "対応する候補・配置同一、元合意不変、非ANSWER保持、DBハッシュ一致"}
    table(["条件", "判定", "実測比較・検査"],
          [[k, "PASS" if v else "FAIL", expressions[k]] for k, v in data["primary_criteria"].items()])
    add("JUNK_TOP1_ZERO は登録どおり採否に用いていない。")
    audit = json.loads((HERE / "audit_result.json").read_text())
    add(f"保存済みの {audit['verified_pairs']} 対を `verify_results.py` で独立に再検査し、Fraction による厳密な閾値比較・候補と配置の一致・非ANSWER保持はすべて PASS。探針の再実行ではない。")
    add("REFUSAL_NOT_WORSE は降格のみの規則では構造上満たせる。これだけで junk の棄権を肩代わりできたとは結論しない。")
    add()
    add("## 補助腕の同じ不等式（baseline 比、主判定に代用しない）")
    add()
    aux = data["arms"]["no_junk_specificity"]
    table(["条件", "参考判定", "比較"], [
        [k, "PASS" if v else "FAIL", {
            "WRONG_DOWN": f"{aux['wrong']} < {b['wrong']}",
            "REFUSAL_NOT_WORSE": f"{aux['refusal']} ≥ {b['refusal']}",
            "CORRECT_NOT_WORSE": f"{aux['correct']} ≥ {b['correct']}"}[k]]
        for k, v in data["auxiliary_vs_baseline"].items()])
    add("## 判定型の全分布")
    add()
    table(["腕", "verdict", "件数"], [[a, k, v] for a, counts in data["verdicts"].items() for k, v in sorted(counts.items())])
    add("## 分類遷移の全分布")
    add()
    table(["比較", "遷移", "件数"], [[pair, k, v] for pair, counts in data["transitions"].items() for k, v in sorted(counts.items())])
    add("## 正答を失った全件（両候補条件）")
    add()
    losses = []
    for raw, gate in (("baseline", "specificity"), ("no_junk", "no_junk_specificity")):
        for r in rows:
            if r["arms"][raw]["category"] == "correct" and r["arms"][gate]["category"] != "correct":
                losses.append([r["index"], raw + " → " + gate, r["gold"], r["query"], evidence(r, gate), result(r, gate)])
    table(["id", "比較", "gold", "問い", "被覆", "裁定後"], losses)
    add(f"上表は {len(losses)} 件の腕内遷移。複数腕に同じ問いが出る場合も省略しない。")
    add()
    add("## 誤答を棄権へ下げた全件（両候補条件）")
    add()
    suppressed = []
    for raw, gate in (("baseline", "specificity"), ("no_junk", "no_junk_specificity")):
        for r in rows:
            if r["arms"][raw]["category"] == "wrong" and r["arms"][gate]["category"] == "refusal":
                suppressed.append([r["index"], raw + " → " + gate, r["gold"], r["query"],
                                   r["arms"][raw]["result"]["core"], evidence(r, gate)])
    table(["id", "比較", "gold", "問い", "棄権に下げた誤答核", "被覆"], suppressed)
    add("## junk 除去で棄権から誤答に変わった問いの全件追跡")
    add()
    vulnerable = [r for r in rows if r["arms"]["baseline"]["category"] == "refusal"
                  and r["arms"]["no_junk"]["category"] == "wrong"]
    rescued = sum(r["arms"]["no_junk_specificity"]["category"] == "refusal" for r in vulnerable)
    add(f"該当 {len(vulnerable)} 件、同じ裁定で棄権に戻った {rescued} 件、誤答のまま {len(vulnerable) - rescued} 件。")
    add()
    table(["id", "gold", "問い", "現行", "junk除去", "junk除去＋裁定", "被覆"],
          [[r["index"], r["gold"], r["query"], result(r, "baseline"), result(r, "no_junk"),
            result(r, "no_junk_specificity"), evidence(r, "no_junk_specificity")] for r in vulnerable])
    add("## 全探針（棄権・無変化も省略しない）")
    add()
    table(["id", "gold", "問い", "baseline", "specificity", "現行核の被覆", "no_junk", "no_junk_specificity", "除去後核の被覆"],
          [[r["index"], r["gold"], r["query"], result(r, "baseline"), result(r, "specificity"),
            evidence(r, "specificity"), result(r, "no_junk"), result(r, "no_junk_specificity"),
            evidence(r, "no_junk_specificity")] for r in rows])
    if data["excluded"]:
        add("生成不能の全件:")
        add("```json\n" + json.dumps(data["excluded"], ensure_ascii=False, indent=2) + "\n```")
    add("候補列・殻の全配置・content tokens・全探索 trace は [results.json](results.json) に腕ごとに保存した。")
    add("この表の被覆は選択核の全 facet 分母と覆った語であり、配置された面数ではない。")
    add()
    add("## 回帰検査（本番変更なしでの健康確認）")
    add()
    add(f"`python3.11 -m verantyx.cli lab`: {sum(lab['forks'].values())}/{lab['n_forks']}、skipped {lab['n_skipped']}。")
    add(f"`python3.11 experiments/guard/verify_all.py`: {guard['forks']} / 測定 {guard['measurements']}。")
    add("終了コードは lab=0、guard=1。guard の失敗は V5 の凍結バイナリ不在と、その結果を集約した V24 で、背景に記載された既知の環境依存と同じ組である。")
    add()
    table(["guard 実行ファイル", "結果"], list(guard["per_file"].items()))
    for failure in guard["fork_failures"] + guard["failures"]:
        add("- " + failure)
    add()
    add("失敗した測定の詳細（実行結果の原文）:")
    for p in sorted((HERE / "checks_after/experiments/guard").glob("results_confirm*.json")):
        measured = json.loads(p.read_text())
        for name, check in measured.get("checks", {}).items():
            if not check["pass"]:
                add(f"`{p.name}: {name}`")
                add("```json\n" + json.dumps(check, ensure_ascii=False, indent=2) + "\n```")
    add("lab の stderr には WikiText cache 不在による synthetic_en fallback の RuntimeWarning が出た。skipped に算入されたものはない。")
    add("lab の全 fork 判定は [lab.log](lab.log)、guard のログは [guard.log](guard.log)、")
    add("構造化結果は [guard_result.json](guard_result.json)、各測定詳細は `checks_after/` に保存。")
    add("本番 verantyx/*.py は今回変更していないため、git checkout による撤回対象はない。")
    add("健康確認が更新した既存 JSON 等は実行後の証拠を別保存し、実行前のバイト列に復元した。利用者の既存変更を維持した。")
    add()
    add("## この登録で言えること・言えないこと")
    add()
    if not data["primary_pass"]:
        failed = ", ".join(k for k, v in data["primary_criteria"].items() if not v)
        add(f"落ちた主判定は {failed}。登録した採択条件を満たさず、本番採用しない。")
    add("この実装は低い facet 被覆を型付き棄権に変える。上の正答喪失・誤答抑制・junk 除去後の個別遷移を、同じ固定閾値で観測した。")
    add("被覆率の閾値と、問いが唯一の核を指定できることは同一ではない。高被覆の誤答や、正しいが facet の多い核の棄権を、この比率だけでは排除できない。")
    add("既存 direction_band/REVERSE_SPECIFIC の帯唯一性・次点比の判定は今回改変せず、順方向の選択核だけを裁定した。")
    add("具体的には、現行で正答だった言語学者 (3/73)、論 (3/84)、数 (3/723)、自民党 (3/83) は、問いの内容語をすべて覆っていても全 facet を分母にしたため落ちた。一文字核を gold から外すなどの事後的な評価変更はしていない。")
    add("一方、junk 除去で初めて誤答になり裁定後も残った id 18 は 2/10、id 29 は 3/10 と高被覆だった。一般語を共有する別条文を、この絶対被覆率では識別できなかった。これらは今回保存した実測例であり、未実行の閾値による改善予想ではない。")
    add("補助腕の結果は候補取得後の junk 除去という条件に限定する。junk の3入口すべてへの配線や、本番 ja_consensus_ask の改善を実測したとは主張しない。")
    add("不採択を別の閾値の結果で上書きせず、凍結登録・実装・全件の証拠を残す。")
    (HERE / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

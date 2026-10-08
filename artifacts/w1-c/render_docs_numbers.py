"""C7: print every number table of docs/CORPUS_INDEX.md from the JSON/text outputs in this directory.

    python artifacts/w1-c/render_docs_numbers.py            # print all tables (each marked with its source)
    python artifacts/w1-c/render_docs_numbers.py --check    # fail unless docs/CORPUS_INDEX.md holds exactly these tables

docs/CORPUS_INDEX.md embeds each table between  <!-- BEGIN table:NAME -->  and  <!-- END table:NAME -->.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parent.parent / "docs" / "CORPUS_INDEX.md"


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def md(headers: list[str], rows: list[list]) -> str:
    esc = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def reasons(d: dict) -> str:
    return ", ".join(f"{k}: {v}" for k, v in d.items()) or "なし"


def n(v) -> str:
    return f"{v:,}"


def tables() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    m = load("manifest.json")
    out["files"] = ("manifest.json の files[]", md(
        ["入力ファイル(root 相対)", "系列", "バイト数", "行数", "sha256(先頭16桁)", "索引に入った行", "読み飛ばし", "split キー無し(索引行のうち)", "出所タグ想定外"],
        [[f["path"], f["family"], n(f["bytes"]), n(f["lines"]), f["sha256"][:16], n(f["indexed"]), reasons(f["skipped"]),
          n(f["split_absent"]), f["source_tag_unexpected"]] for f in m["files"]]))
    out["source_tags"] = ("manifest.json の files[].source_tag_prefixes", md(
        ["入力ファイル", "出所タグの接頭辞(llm_authored:codex: 以降、-b 連番の前)と件数"],
        [[f["path"], reasons(f["source_tag_prefixes"])] for f in m["files"]]))
    out["optional_absent"] = ("manifest.json の files[].optional_absent", md(
        ["入力ファイル", "任意欄の欠落(索引行のうち、読み飛ばしではない)"],
        [[f["path"], reasons(f["optional_absent"])] for f in m["files"] if f["optional_absent"]]))
    out["families"] = ("manifest.json の families{}", md(
        ["系列", "状態", "索引行数", "DB バイト数", "系列ごとの所要秒"],
        [[k, v["state"], n(v.get("rows", 0)), n(v.get("db_bytes", 0)), v.get("elapsed_seconds", "")] for k, v in m["families"].items()]))
    log = (HERE / "build.log").read_text(encoding="utf-8")
    real = re.search(r"^\s*([\d.]+) real", log, re.M)
    code = re.search(r"exit_code=(\d+)", log)
    out["timing"] = ("manifest.json と build.log(/usr/bin/time -l と終了コード)", md(
        ["項目", "値"],
        [["manifest の elapsed_seconds", m["elapsed_seconds"]], ["/usr/bin/time の real(秒)", real.group(1) if real else "UNKNOWN"],
         ["終了コード", code.group(1) if code else "UNKNOWN"], ["--jobs", "4"], ["git HEAD", m["git_head"][:12]],
         ["python", m["python"]], ["sqlite", m["sqlite_version"]], ["開始", m["started_at"]], ["終了", m["finished_at"]]]))
    out["excluded"] = ("manifest.json の excluded[]", md(
        ["索引に入れなかったファイル", "理由", "バイト数", "行数"],
        [[e["path"], e["reason"], n(e["bytes"]), n(e["lines"])] for e in m["excluded"]]))
    c = load("check_manifest.json")
    out["check_manifest"] = ("check_manifest.json", md(
        ["確認", "結果"],
        [["入力 10 ファイルの bytes / 行数 / sha256 の再計算が manifest と一致", all(f["bytes_match"] and f["lines_match"] and f["sha256_match"] for f in c["files"])],
         ["lines == indexed + 読み飛ばし(全ファイル)", all(f["identity"] for f in c["files"])],
         ["wc -l / shasum による 2 ファイルの手計算が一致", all(r["manifest_newlines_equal"] and r["manifest_sha_equal"] for r in c["system_tool_recount"])],
         ["GROUP BY source_file が manifest の indexed と一致(8 DB)", all(f["group_by_matches_manifest"] for f in c["families"])],
         ["heldout / overlap_dropped 由来の DB 行(8 DB の合計)", sum(f["rows_from_heldout_or_overlap_dropped"] for f in c["families"])],
         ["無作為抽出した行の元行 sha 一致(系列あたり件数 / 全系列で一致)", f"{c['families'][0]['random_round_trips']['n']} / {all(f['random_round_trips']['all_match'] for f in c['families'])}"],
         ["全体判定 all_ok", c["checks"]["all_ok"]]]))
    s = load("c2_search.json")
    out["c2_ticket"] = ("c2_search.json の ticket[]", md(
        ["語句", "系列", "state", "件数(limit 1000)", "先頭ヒットの所在", "元行の往復(sha・語句の包含)", "満たした"],
        [[e["phrase"], r["family"], r["state"], r["hits"],
          (f"{r['first']['source_file']}:{r['first']['line']}" if r["first"] else "—"),
          (r["round_trip"]["ok"] if "round_trip" in r else "—"), e["satisfied"]]
         for e in s["ticket"] for r in e["by_family"]]))
    out["c2_self"] = ("c2_search.json の self_chosen[] と negative_controls[]", md(
        ["系列", "自選語句 満たした件数 / 件数", "陰性対照(heldout にだけ在る語句)の state"],
        [[f, f"{sum(1 for r in s['self_chosen'] if r['family'] == f and r['satisfied'])} / {sum(1 for r in s['self_chosen'] if r['family'] == f)}",
          next((x.get("state", "—") for x in s["negative_controls"] if x["family"] == f), "—")] for f in
         ["pro", "code", "conversation", "general_qa", "code_qa", "figurative_commonsense", "narrative", "paraphrase_entail"]]))
    ev = s["raw_corpus_absence_evidence"]
    out["c2_absence"] = ("c2_search.json の raw_corpus_absence_evidence", md(
        ["確認(コーパスの全 *.jsonl を直接走査)", "結果"],
        [["走査したファイル数", ev["files_scanned"]],
         ["「携帯データ」を含む行", ev["lines_containing"]["携帯データ"]["lines"]],
         ["「Wi-Fiなし 携帯データ」を含む行", ev["lines_containing"]["Wi-Fiなし 携帯データ"]["lines"]],
         ["「脱水機」を含む行", ev["lines_containing"]["脱水機"]["lines"]],
         ["「異音」を含む行", ev["lines_containing"]["異音"]["lines"]],
         ["「脱水機の異音」を含む行", ev["lines_containing"]["脱水機の異音"]["lines"]],
         ["「脱水機」と「異音」が同一行にある行", ev["lines_with_both_脱水機_and_異音"]["lines"]],
         ["同一 dialogue_id に両方がある dialogue 数(会話 6 ファイル合計)", sum(ev["dialogue_ids_with_both_脱水機_and_異音_by_file"].values())]]))
    d = load("c4_heldout_check.json")
    out["c4"] = ("c4_heldout_check.json", md(
        ["項目", "値"],
        [["乱数の種", d["seed"]], ["抽出件数", d["sampled"]], ["母集団(heldout 全ファイルの行数)", n(d["population"])],
         ["out/ に heldout があるか", d["out_has_heldout"]],
         ["系列別の抽出件数", ", ".join(f"{k}: {v['sampled']}" for k, v in d["per_family"].items())],
         ["抽出できなかったレコード", reasons(d["unextractable_by_reason"])],
         ["(a) 本文の sha が同系列 DB に在る件数", d["body_sha_hits"]],
         ["(b) いずれかの欄の文字列が索引行に逐語で在るレコード数", d["field_substring_hits"]],
         ["(b) うち全欄が同系列に在るレコード数", d["records_with_every_field_in_same_family"]]]))
    r1c4 = load("c4_heldout_check.r1.json")
    out["c4_body_hits"] = ("c4_heldout_check.json の body_sha_hit_records[] と c4_heldout_check.r1.json の body_sha_hit_records[](索引 r1 での該当)", md(
        ["索引", "heldout の所在", "系列", "本文の文字数", "同じ本文の索引行数", "一致した索引行(先頭)"],
        [["r1(heldout 除外の規則なし)", r["heldout"], r["family"], r["body_chars"], r["indexed_rows_with_same_body"], r["matched_rows_first5"][0]] for r in r1c4["body_sha_hit_records"]]
        + [["r2(規則あり)", r["heldout"], r["family"], r["body_chars"], r["indexed_rows_with_same_body"], r["matched_rows_first5"][0]] for r in d["body_sha_hit_records"]]
        or [["r2", "該当なし", "—", "—", "—", "—"]]))
    out["c4_field_hits"] = ("c4_heldout_check.json の field_substring_hit_records[](欄の文字数つき)", md(
        ["heldout の所在", "kind", "索引行に逐語で在った欄(欄名:文字数)", "欄の総数"],
        [[r["heldout"], r["kind"], ", ".join(f"{f['field']}:{f['chars']}" for f in r["fields"] if f["in_same_family"] or f["in_other_families"]), len(r["fields"])]
         for r in d["field_substring_hit_records"]]))
    e = load("c5_entry_probe.json")
    out["c5_positive"] = ("c5_entry_probe.json の positive[]（第1ラウンド・旧 C5・索引 r1。凍結）", md(
        ["id", "入口", "発話", "索引あり: kind / verdict", "索引の状態(索引あり)", "索引の状態(索引なし)", "索引なしの結果", "出所種別 generated の出典数(索引あり)", "判定"],
        [[r["id"], r["entry"], r["text"], f"{r['with_index']['summary'].get('kind')} / {r['with_index']['summary'].get('verdict')}",
          ",".join(r["with_index"]["summary"].get("index_states") or []) or "—", ",".join(r["without_index"]["summary"].get("index_states") or []) or "—",
          f"{r['without_index']['summary'].get('kind')} / {r['without_index']['summary'].get('verdict')}",
          r["with_index"]["summary"].get("generated_origin_sources"), r.get("verdict", {}).get("passes", "情報のみ")] for r in e["positive"]]))
    rows = []
    for r in e["counterexample_search"] + e["counterexample_search_added"]:
        v = r["verdict"]
        rows.append([r["id"], "事前登録" if r["phase"] == "registered_before_run" else "事後に追加", r["entry"], r["text"],
                     f"{r['with_index']['summary'].get('kind')} / {r['with_index']['summary'].get('verdict')}", v["answered"],
                     v["generated_origin_sources"], v["identical_to_without_index"], v["counterexample"]])
    out["c5_counter"] = ("c5_entry_probe.json の counterexample_search[] と counterexample_search_added[]（第1ラウンド・旧 C5・索引 r1。凍結）", md(
        ["id", "登録", "入口", "質問", "索引あり: kind / verdict", "回答した", "generated 出典数", "索引なしと同一結果", "反例"], rows))
    out["c5_summary"] = ("c5_entry_probe.json の summary（第1ラウンド・旧 C5・索引 r1。凍結）", md(
        ["項目", "値"],
        [["実行数(質問 x 入口)", e["summary"]["counterexample_runs"]],
         ["反例(回答かつ generated 出典あり)の実行", ", ".join(f"{a}/{b}" for a, b in e["summary"]["counterexamples"]) or "なし"],
         ["うち事前登録の質問での反例", ", ".join(f"{a}/{b}" for a, b in e["summary"]["counterexamples_among_registered"]) or "なし"],
         ["うち事後に追加した質問での反例", ", ".join(f"{a}/{b}" for a, b in e["summary"]["counterexamples_among_added"]) or "なし"],
         ["索引の有無で結果が同一だった実行数", len(e["summary"]["identical_with_and_without_index"])],
         ["コーパス経路が trace に現れた反例探しの実行数", len(e["summary"]["probes_where_corpus_path_ran"])]]))
    led = load("ledger_reconcile.json")
    out["ledger"] = ("ledger_reconcile.json", md(
        ["ディレクトリ", "台帳の行数", "KEPT の kept 合計", "台帳のバッチ接頭辞別行数", "items 系ファイルの行数(train+heldout+overlap_dropped)",
         "台帳にあり items に無いバッチ数 / その kept 合計", "items にあり台帳に無いバッチ数", "両方に在るバッチ数", "両方に在るバッチで kept と train+heldout 行数が違うバッチ数"],
        [[k, n(led[k]["ledger_rows"]), n(led[k]["ledger_kept_total"]), reasons(led[k]["ledger_batch_prefixes"]), n(led[k]["item_rows_all_splits"]),
          f"{n(led[k]['ledger_batches_not_in_any_item_file']['count'])} / {n(led[k]['ledger_batches_not_in_any_item_file']['kept_total'])}",
          led[k]["item_batches_not_in_ledger"]["count"], n(led[k]["batches_in_both"]["count"]),
          led[k]["batches_in_both"]["batches_where_kept_differs_from_train_plus_heldout_rows"]] for k in ("code", "even/code", "conversation", "even/conversation")]))
    out["ledger_prefix"] = ("ledger_reconcile.json の ledger_batches_not_in_any_item_file.by_prefix", md(
        ["ディレクトリ", "台帳にあり items に無いバッチの接頭辞別数", "その台帳行の verdict 別"],
        [[k, reasons(led[k]["ledger_batches_not_in_any_item_file"]["by_prefix"]), reasons(led[k]["ledger_batches_not_in_any_item_file"]["verdicts"])]
         for k in ("code", "even/code", "conversation", "even/conversation")]))
    base = [l for l in (HERE / "baseline_failures.txt").read_text().splitlines() if l.strip()]
    after = [l for l in (HERE / "tests_after_failures.txt").read_text().splitlines() if l.strip()]
    summ = (HERE / "tests_after_summary.txt").read_text().strip().splitlines()[-1]
    out["tests"] = ("tests_after_summary.txt / tests_after_failures.txt / baseline_failures.txt", md(
        ["項目", "値"],
        [["全体テストの最終行", summ], ["ベースラインの失敗+エラー ID 数", len(base)], ["変更後の失敗+エラー ID 数", len(after)],
         ["変更後に新しく失敗した ID 数(ベースラインに無いもの)", len(set(after) - set(base))],
         ["ベースラインにあり変更後に無い ID 数", len(set(base) - set(after))]]))

    # ---------------------------------------------------------------- R1 (round 2)
    r1 = load("manifest.r1.json")
    r1f = {f["path"]: f for f in r1["files"]}
    out["heldout_files"] = ("manifest.json の families{}.heldout.files[]", md(
        ["系列", "heldout ファイル(root 相対)", "バイト数", "行数", "sha256(先頭16桁)", "本文を取り出せなかった行(理由別)"],
        [[fam, hf["path"], n(hf["bytes"]), n(hf["lines"]), hf["sha256"][:16], reasons(hf["unextractable"])]
         for fam, info in m["families"].items() for hf in info["heldout"]["files"]]
        + [[fam, "(heldout ファイルなし: HELDOUT 表が空)", "—", "—", "—", "—"] for fam, info in m["families"].items() if info["heldout"]["none_listed"]]))
    out["heldout_bodies"] = ("manifest.json の families{}.heldout", md(
        ["系列", "本文を取り出せた heldout 行", "異なる本文(sha256)の数", "HELDOUT 表が空"],
        [[fam, n(info["heldout"]["records"]), n(info["heldout"]["distinct_bodies"]), info["heldout"]["none_listed"]]
         for fam, info in m["families"].items()]))
    out["heldout_unlisted"] = ("manifest.json の heldout_unlisted", md(
        ["項目", "値"],
        [["HELDOUT 表に載っていない heldout ファイル(root 配下を走査)", len(m["heldout_unlisted"])],
         ["その一覧", ", ".join(m["heldout_unlisted"]) or "なし"],
         ["UNKNOWN_HELDOUT_MISSING の系列", ", ".join(k for k, v in m["families"].items() if v["state"] == "UNKNOWN_HELDOUT_MISSING") or "なし"]]))
    out["r1_r2"] = ("manifest.json と manifest.r1.json の files[]", md(
        ["入力ファイル", "行数", "r1 の索引行(規則なし)", "r2 の索引行(規則あり)", "r1 - r2", "r2 の heldout_body_overlap", "r2 の他の読み飛ばし", "r2 balanced", "行数・sha256 が r1 と同じ"],
        [[f["path"], n(f["lines"]), n(r1f[f["path"]]["indexed"]), n(f["indexed"]), n(r1f[f["path"]]["indexed"] - f["indexed"]),
          n(f["skipped"].get("heldout_body_overlap", 0)),
          reasons({k: v for k, v in f["skipped"].items() if k != "heldout_body_overlap"}), f["balanced"],
          f["lines"] == r1f[f["path"]]["lines"] and f["sha256"] == r1f[f["path"]]["sha256"]] for f in m["files"]]))
    log1 = (HERE / "build.r1.log").read_text(encoding="utf-8")
    real1 = re.search(r"^\s*([\d.]+) real", log1, re.M)
    out["r1_r2_timing"] = ("manifest.r1.json / build.r1.log と manifest.json / build.log", md(
        ["", "manifest の elapsed_seconds", "/usr/bin/time の real(秒)", "開始"],
        [["r1(規則なし)", r1["elapsed_seconds"], real1.group(1) if real1 else "UNKNOWN", r1["started_at"]],
         ["r2(規則あり)", m["elapsed_seconds"], real.group(1) if real else "UNKNOWN", m["started_at"]]]))
    full = load("c4_heldout_full.json")
    out["c4_full"] = ("c4_heldout_full.json の by_family[]", md(
        ["系列", "heldout 行数", "本文を取り出せた行", "異なる本文数", "(a) 同系列 DB の同じ本文の行数", "(a') 他系列 DB の同じ本文の行数(合計)"],
        [[r["family"], n(r["heldout_lines"]), n(r["heldout_records_with_body"]), n(r["distinct_heldout_bodies"]),
          r["same_family_index_rows_with_heldout_body"], sum(r["other_family_index_rows_with_heldout_body"].values())] for r in full["by_family"]]))
    out["c4_full_other"] = ("c4_heldout_full.json の by_family[].other_family_examples[]", md(
        ["heldout の系列", "同じ本文があった他系列 DB", "その行", "本文の先頭"],
        [[e["heldout_family"], e["found_in_family"], f"{e['source_file']}:{e['line']}", e["text_head"]]
         for r in full["by_family"] for e in r["other_family_examples"]] or [["—", "—", "なし", "—"]]))
    out["c4_full_rule"] = ("c4_heldout_full.json の rule_recount[]", md(
        ["入力ファイル", "規則なしなら索引に入る行", "同系列 heldout と本文が同じ行(数え直し)", "manifest の heldout_body_overlap", "指示書の予測値", "数え直し = manifest", "manifest = 予測値", "規則なし - 重なり = 索引行"],
        [[r["path"], n(r["would_index_without_rule"]), n(r["overlap_recount"]), n(r["manifest_heldout_body_overlap"]), n(r["planner_predicted"]),
          r["recount_equals_manifest"], r["manifest_equals_planner_prediction"], r["identity_would_index_minus_overlap"]] for r in full["rule_recount"]]))
    hf = full["heldout_files"]
    out["c4_full_checks"] = ("c4_heldout_full.json", md(
        ["確認", "結果"],
        [["コーパスを走査して見つけた heldout ファイル数", len(hf["walked"])],
         ["走査結果 = builder の HELDOUT 表", hf["walked_equals_builder"]], ["走査結果 = 検算側 _common.HELDOUT", hf["walked_equals_common"]],
         ["out/ に heldout があるか", hf["out_has_heldout"]],
         ["合格: 全系列で同系列 DB に同じ本文の行が 0", full["pass_same_family_all_zero"]],
         ["合格: 規則の数え直し = manifest(全ファイル)", full["pass_rule_recount_equals_manifest"]],
         ["所要秒", full["elapsed_seconds"]]]))
    d1 = load("c4_heldout_check.r1.json")
    out["c4_r1_r2"] = ("c4_heldout_check.r1.json と c4_heldout_check.json", md(
        ["項目", "r1(規則なし)", "r2(規則あり)"],
        [[k, d1[k], d[k]] for k in ("seed", "sampled", "population", "body_sha_hits", "field_substring_hits", "records_with_every_field_in_same_family")]))

    # ---------------------------------------------------------------- C5' (round 2)
    q = load("c5r2_entry_probe.json")
    sm = q["summary"]
    rg = sm["registration"]
    out["c5r2_registration"] = ("c5r2_entry_probe.json の summary.registration と summary.environment_check", md(
        ["項目", "値"],
        [["登録ファイル", rg["path"]], ["登録ファイルの sha256", rg["sha256"]], ["登録ファイルの作成時刻", rg["birthtime"]],
         ["登録ファイルの更新時刻", rg["mtime"]], ["実行開始時刻", rg["run_started"]], ["登録が実行開始より前", rg["created_before_run_start"]],
         ["事後の追加登録ファイル", rg["additional_registration_file"] or "なし"],
         ["実行数(サブプロセス)", sm["runs"]], ["全実行が JSON を返した", sm["all_runs_produced_json"]],
         ["作業ツリーに build/p4 が在る", sm["environment_check"]["tree_build_p4_exists"]],
         ["既定状態の子プロセス環境に VERA_P4_INDEX が在る", sm["environment_check"]["default_child_env_has_VERA_P4_INDEX"]],
         ["既定状態の子プロセス環境に VERA_W1C_INDEX が在る", sm["environment_check"]["default_child_env_has_VERA_W1C_INDEX"]]]))
    out["c5r2_groups"] = ("c5r2_entry_probe.json の summary.by_group", md(
        ["群", "登録した質問数", "到達(reached)した異なる質問数", "到達した質問"],
        [[g, v["registered"], v["reached"], " / ".join(v["reached_questions"]) or "なし"] for g, v in sm["by_group"].items()]))
    out["c5r2_judgement"] = ("c5r2_entry_probe.json の summary", md(
        ["判定", "結果", "内訳"],
        [["(i) 各群 3 問以上・合計 10 問以上が到達", sm["i"], f"到達した異なる質問の合計 {sm['i_reached_distinct_questions_total']}"],
         ["(ii) 到達かつ回答の実行はすべて basis_origin が generated。全実行で「在る ⇔ generated 出典が在る」", sm["ii"],
          f"不変条件の違反 {len(sm['invariant_violations_over_all_runs'])} / (ii) の違反 {len(sm['ii_reached_answered_with_generated_but_no_basis_origin'])} / 到達かつ回答なのに generated 出典が無い実行 {len(sm['reached_answered_but_no_generated_source'])}"],
         ["(iii) 根拠がコーパスでない回答 5 問以上で型が付かない", sm["iii"], f"満たした問 {sm['iii_satisfied']}"],
         ["(iv) 到達した各(質問, 入口)の既定状態でコーパス不使用・「索引なし」が trace に出る", sm["iv"], f"検査した(質問, 入口) {sm['iv_checked']} / 満たさなかった {len(sm['iv_failed'])}"]]))
    idx = {(r["group"], r["text"], r["entry"], r["state"]): r for r in q["runs"]}
    rrows = []
    for rr in q["reached"]:
        w = idx[(rr["group"], rr["text"], rr["entry"], "with_index")]["facts"]
        dd = idx[(rr["group"], rr["text"], rr["entry"], "default")]["facts"]
        rrows.append([rr["group"], rr["entry"], rr["text"], f"{w.get('kind')} / {w.get('verdict')}", w.get("generated_sources"),
                      w.get("basis_origin") or "なし", rr["flag_generated_sources"], rr["flag_result_differs_from_default"], rr["reached"],
                      f"{dd.get('kind')} / {dd.get('verdict')}", ",".join(sorted({str(t["index"]) for t in dd.get("corpus_trace", []) if t.get("index")})) or "—",
                      dd.get("generated_sources"), dd.get("basis_origin") or "なし"])
    out["c5r2_runs"] = ("c5r2_entry_probe.json の reached[] と runs[]", md(
        ["群", "入口", "質問", "索引あり: kind / verdict", "generated 出典数", "basis_origin", "旗1: generated 出典が在る", "旗2: 既定状態と結果が違う", "到達",
         "既定状態: kind / verdict", "既定状態の trace の索引の状態", "既定状態の generated 出典数", "既定状態の basis_origin"], rrows))
    out["c5r2_noncorpus"] = ("c5r2_entry_probe.json の summary.iii_rows", md(
        ["入口", "質問", "kind", "ability", "door", "回答した", "generated 出典数", "basis_origin が在る", "満たした"],
        [[x["entry"], x["text"], x["kind"], x["ability"] or "—", x["door"] or "—", x["answered"], x["generated_sources"], x["has_basis_origin_key"], x["satisfied"]] for x in sm["iii_rows"]]))
    cs = load("c5r2_conversation_supply.json")
    out["conv_supply"] = ("c5r2_conversation_supply.json の rows[]", md(
        ["社交の定型文(round3._social_frame)", "LIKE の件数", "_norm 完全一致の総数", "先頭 60 件の窓の中の一致(Corpus.search limit=60)", "規則で除外された train 行", "索引に残った train 行", "供給に届く"],
        [[r["sentence"], n(r["like_hits"]), n(r["norm_equal_total"]), r["window60_norm_equal"], n(r["train_rows_removed_by_heldout_rule"]), n(r["train_rows_kept"]), r["reaches_supply"]] for r in cs["rows"]]))
    oos = load("oos_repro.json")
    out["oos"] = ("oos_repro.json", md(
        ["名前", "コマンド", "kind / verdict", "ability", "basis_origin", "回答文", "trace の ability_corpus.*(part の末尾:family:index)"],
        [[o["name"], o["command"], f"{o['kind']} / {o['verdict']}", o["ability"], o["basis_origin"] or "なし", o["text"],
          "; ".join(f"{t['part'].split('.')[-1]}:{t['family']}:{t['index']}" for t in o["corpus_trace"])] for o in oos]))
    return out


def render() -> dict[str, str]:
    return {name: f"出典: `artifacts/w1-c/{src}`\n\n{table}" for name, (src, table) in tables().items()}


def main(argv: list[str]) -> int:
    rendered = render()
    if "--check" in argv:
        doc = DOC.read_text(encoding="utf-8")
        bad = []
        for name, body in rendered.items():
            m = re.search(rf"<!-- BEGIN table:{name} -->\n(.*?)\n<!-- END table:{name} -->", doc, re.S)
            if not m or m.group(1).strip() != body.strip():
                bad.append(name)
        extra = set(re.findall(r"<!-- BEGIN table:(\w+) -->", doc)) - set(rendered)
        print("tables:", len(rendered), "mismatched/missing:", bad, "unknown in doc:", sorted(extra))
        return 1 if bad or extra else 0
    for name, body in rendered.items():
        print(f"<!-- BEGIN table:{name} -->\n{body}\n<!-- END table:{name} -->\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

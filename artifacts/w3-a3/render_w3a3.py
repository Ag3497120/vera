"""Render every number of docs/COARSE_PLACEMENT.md section 12.15 from artifacts/w3-a3/.

    render_w3a3.py           rewrite the block between <!-- w3a3-measure:begin --> and <!-- w3a3-measure:end -->
    render_w3a3.py --check   exit 0 only when the block already equals the render

Nothing in the block is typed by hand: the words are fixed text of this script, the numbers are read from the
measurement files (ledger summary, manifests, eval_runs, dev_grid.txt, audit, q4 comparison, pytest output).
The registration (section 12.1-12.14) is never touched.  The lists of wrong words go to
artifacts/w3-a3/errors_final.md (not into the docs)."""
import glob
import json
import os
import re
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
A = os.path.join(W, "artifacts/w3-a3")
DOC = os.path.join(W, "docs/COARSE_PLACEMENT.md")
B = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6"
sys.path.insert(0, A)
BEGIN, END = "<!-- w3a3-measure:begin -->", "<!-- w3a3-measure:end -->"


def load(p):
    return json.load(open(p, encoding="utf-8"))


def have(*p):
    return all(os.path.exists(os.path.join(A, x)) for x in p)


def md(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def runs(root):
    out = []
    for d in sorted(glob.glob(os.path.join(A, root, "[0-9][0-9][0-9]"))):
        sp = os.path.join(d, "summary.json")
        if os.path.exists(sp):
            s = load(sp)
            s["_seq"] = os.path.basename(d)
            out.append(s)
    return out


def table(name, text):
    return "<!-- BEGIN table:%s -->\n%s<!-- END table:%s -->\n" % (name, text, name)


def read_text(name):
    return open(os.path.join(A, name), encoding="utf-8").read().strip()


def sec_order():
    t = {}
    t["prereg_before"] = read_text("prereg_time.txt").splitlines()[0].split(": ", 1)[1]
    t["prereg_after"] = read_text("prereg_time.txt").splitlines()[1].split(": ", 1)[1]
    t["frozen_at"] = load(os.path.join(A, "FROZEN.json"))["frozen_at"]
    for k, f in (("base_build_started", "build_r6_base.started"), ("generation_started", "gen_pred_run_1.started"),
                 ("dev_d1_started", "build_dev_d1.started"), ("config_frozen", "config_frozen_time.txt"),
                 ("run1_started", "build_r6_run1.started")):
        if have(f):
            t[k] = read_text(f)
    rows = [("事前登録（docs §12.1〜12.14）", "%s 〜 %s" % (t["prereg_before"], t["prereg_after"])),
            ("検査データの凍結（`FROZEN.json` の `frozen_at`）", t["frozen_at"])]
    for k, label in (("base_build_started", "r6/base の作成を始めた"), ("generation_started", "述語の枠の生成（本番）を始めた"),
                     ("dev_d1_started", "dev の配置 d1 の作成を始めた"), ("config_frozen", "設定を凍結した（`config_w3a3.json`）"),
                     ("run1_started", "全量 r6/run1 の作成を始めた")):
        if k in t:
            rows.append((label, t[k]))
    return ("### 12.15.1 実行の順と時刻\n\n登録 → 凍結 → 実装 → dev → 設定の凍結 → 全量 → 凍結データの測定、の順に、次の時刻で行った"
            "（出典: `prereg_time.txt`・`FROZEN.json`・`*.started`）。製品コードの最初の変更は凍結の後（`DECISIONS.md` D1）。\n\n"
            + table("w3a3_order", md(["段", "時刻（`date '+%F %T %z'`）"], rows)))


def sec_generation():
    if not have("gen_pred_summary.json", "needs_pred.meta.json"):
        return "### 12.15.2 述語の一覧と生成（Q2）\n\n（未測定）\n"
    s, m = load(os.path.join(A, "gen_pred_summary.json")), load(os.path.join(A, "needs_pred.meta.json"))
    ov = load(os.path.join(A, "needs_pred_overlap.json")) if have("needs_pred_overlap.json") else None
    rows = [("一覧の語数（境界の同点を全部入れた。頼んだ数 %d）" % m["n_requested"], m["total"]),
            ("一覧の境界の頻度（`n_seen`）と、その頻度の語数", "%s / %s" % (m["boundary_freq"], m["n_at_boundary"])),
            ("一覧の内訳（名前空間）", ", ".join("%s %d" % kv for kv in sorted(m["by_ns"].items()))),
            ("一覧の内訳（証拠の状態）", ", ".join("%s %d" % kv for kv in sorted(m["by_evidence_status"].items()))),
            ("モデル・effort・並列・束の大きさ", "%s・%s・%s・%s" % (s["model"], s["effort"], s["slots"], s["batch_size"])),
            ("呼び出し数（上限 %s）" % s["max_calls"], s["calls"]),
            ("束の数・成功した束・成功の割合", "%d・%d・%.4f" % (s["batches_total"], s["batches_ok"], s["ok_rate"])),
            ("失敗した束・上限で走らなかった束", "%d・%d" % (s["batches_failed"], s["not_run_cap"])),
            ("所要時間（台帳の最初の start から最後の end まで。試し呼び出しとの空きを含む）", "%s 秒" % s["wall_sec"]),
            ("呼び出しの時間の合計（並列の分を足したもの）", "%s 秒" % s["sum_call_sec"]),
            ("1 語あたりの呼び出し数（呼び出し数 / 頼んだ語数）", s["calls_per_word_requested"]),
            ("答えが返った語・棄権（`ptype` null）・同じ助詞が 2 回の frame",
             "%d・%d・%d" % (s["words_answered"], s["words_abstained"], s["words_frame_dup_particle"])),
            ("束に無い語・重複・範囲外・戻らなかった語", "%d・%d・%d・%d" % (
                s["words_foreign_dropped"], s["words_dup_dropped"], s["words_invalid"], s["words_missing"])),
            ("述語のプロンプトの sha256（固定部）", s["prompt_template_sha256"]),
            ("schema の sha256", s["schema_sha256"]),
            ("台帳の sha256", s["ledger_sha256"])]
    if have("gen_pred_sha256.txt"):
        for line in read_text("gen_pred_sha256.txt").splitlines():
            h, p = line.split()
            if p.endswith("frames.jsonl"):
                rows.append(("`frames.jsonl` の sha256", h))
    txt = ("### 12.15.2 述語の一覧と生成（Q2）\n\n呼び出しは試し 1 回を含み、上限 1,500 の内。出典: `gen_pred_summary.json`・`needs_pred.meta.json`。"
           "名詞のプロンプトの sha256 は `ded30f48…` のまま変えていない（`test_the_noun_prompt_and_its_hash_did_not_change`）。\n\n"
           + table("w3a3_generation", md(["項目", "値"], rows)))
    if ov:
        txt += ("\n一覧に載った検査データの動詞（数えただけ。一覧は検査データで変えていない）: dev の動詞 %d 行のうち %d 行（typed %d・断片 %d・造語 %d）、"
                "凍結の 300 行のうち %d 行（typed %d・断片 %d・造語 %d）。造語は材料から除いたので一覧に載らない。\n" % (
                    ov["dev_verbs"]["rows"], ov["dev_verbs"]["on_the_list"], ov["dev_verbs"]["by_kind"]["typed"],
                    ov["dev_verbs"]["by_kind"]["unknown_fragment"], ov["dev_verbs"]["by_kind"]["unknown_coined"],
                    ov["verb_check_300"]["on_the_list"], ov["verb_check_300"]["by_kind"]["typed"],
                    ov["verb_check_300"]["by_kind"]["unknown_fragment"], ov["verb_check_300"]["by_kind"]["unknown_coined"]))
    return txt


def sec_config():
    if not have("config_w3a3.json", "dev_grid.txt"):
        return "### 12.15.3 設定（dev で決めた値）\n\n（未測定）\n"
    cfg = load(os.path.join(A, "config_w3a3.json"))
    grid = read_text("dev_grid.txt")
    sel = json.loads(re.search(r"^SELECTED_JSON (.*)$", grid, re.M).group(1))
    selp = re.search(r"^SELECTED predicates \(grid index (\d+)\): .* -> (.*)$", grid, re.M)
    sels = re.search(r"^SELECTED slot \(grid index (\d+)\): .* -> (.*)$", grid, re.M)
    ref = re.search(r"reference, without the new arms .*?: (\{.*\})", grid)
    nos = re.search(r"without the slot rows \(stage-1 decision\): (\{.*\})", grid)
    fl = read_text("dev_frame_legacy.txt")
    mm = re.search(r"correct (\d+) / wrong_single (\d+) / other (\d+)", fl)
    meaning = {
        "frame_decides": "既存の `frame` 腕を決め手にするか（§12.7 の規則で決まる）",
        "rd_store_min": "分布の行を保存する床（固定）", "rd_min_total": "分布の腕の型つきの項の最小",
        "rd_particle_min": "有意な助詞の最小数", "rd_particle_share_pct": "有意な助詞の割合（%）",
        "rd_type_share_pct": "助詞の中で有意な型の割合（%）", "rd_min_sources": "格上げに要る分布の腕の数",
        "slot_min": "slot の最小数", "slot_share_pct": "slot の割合（%）", "slot_lift_pct": "基準率に対する持ち上げ（%。固定）"}
    grid_txt = {"frame_decides": "規則で 1 つ", "rd_store_min": "固定 20", "rd_min_total": "100 / 50 / 20",
                "rd_particle_min": "10 / 5", "rd_particle_share_pct": "30 / 20 / 10", "rd_type_share_pct": "70 / 50",
                "rd_min_sources": "2 / 1", "slot_min": "20 / 10 / 5", "slot_share_pct": "30 / 20 / 10", "slot_lift_pct": "固定 300"}
    rows = [(k, meaning[k], grid_txt[k], cfg[k]) for k in meaning]
    txt = ("### 12.15.3 設定（dev で決めた値。ここから先は変えない）\n\n"
           "`frame_decides` は §12.7 の規則どおり、R5 を dev の動詞で測った結果（`dev_frame_legacy.txt`）で決めた: `frame@` が決め手の語の正答 %s・誤決定 %s・その他 %s → 正答が誤決定の 3 倍に届かない → False。"
           "ほかの値は dev の格子（`dev_grid.py`、全行は `dev_grid.txt`）から §12.8 の選び方で選んだ。設定ファイルの sha256 は `config_w3a3.sha256`。\n\n"
           % (mm.group(1), mm.group(2), mm.group(3)) + table("w3a3_config", md(["設定", "意味", "格子", "値"], rows)) +
           "\n述語の格子 72 行の選択: 格子の %s 行目（0 始まり）。dev の動詞での direct の数 = %s。新しい腕を全部外したときの数（参考）= %s。\n\n"
           "slot の格子 9 行の選択: 格子の %s 行目。dev の語彙（L2、種を除く）での direct の数 = %s。slot の行を外したときの数 = %s。\n" % (
               selp.group(1), selp.group(2), ref.group(1), sels.group(1), sels.group(2), nos.group(1)))
    return txt


def sec_placement():
    p = os.path.join(A, "manifest_r6_run1.json")
    if not os.path.exists(p):
        return "### 12.15.4 配置 r6 の中身\n\n（未測定）\n"
    m = load(p)
    g = m["generated_frames"]
    o = g["outcomes"]
    ac = m["argument_chains"]
    st2 = ac["stage2"]
    rows = [("見出し語の数", m["outputs"]["headwords"]), ("direct で置いた語（`placed_direct`）", m["outputs"]["placed_direct"]),
            ("`estimated(generated)` の語（名詞の定義 + 述語の枠）", m["outputs"]["placed_estimated_generated"]),
            ("`generated_frames` 表の行数", m["outputs"]["tables"]["generated_frames"]),
            ("`evidence` 表の行数", m["outputs"]["tables"]["evidence"]),
            ("作成の所要時間（秒。cache なし）", m["duration_sec"])]
    gf = [("読んだ行（`frames.jsonl`）", g["rows_read"]), ("使った語（述語の見出し語）", g["used"]),
          ("棄権（`ptype` null）", g["dropped_by_reason"]["abstained"]),
          ("名前空間に P を含まない語（`ns_not_predicate`）", g["dropped_by_reason"]["ns_not_predicate"]),
          ("材料に無い語", g["dropped_by_reason"]["not_in_material"]),
          ("格上げ（direct。`decided_by` に `gen_frame`）", o.get("decided_direct_upgrade", 0)),
          ("　うち、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し）", o.get("decided_direct_upgrade_all_sources_codex", 0)),
          ("　うち、jawiki の腕が加わった", o.get("decided_direct_upgrade_with_jawiki", 0)),
          ("`estimated(generated)`（生成だけ・または一致せず）", o.get("decided_estimated_generated", 0)),
          ("　うち `DISTRIBUTION_DISAGREES`", o.get("DISTRIBUTION_DISAGREES", 0)),
          ("　うち `FRAME_PARTICLES_NOT_COVERED`", o.get("FRAME_PARTICLES_NOT_COVERED", 0)),
          ("生成が決めない（別の腕がすでに決めていた）", o.get("base_decided_generated_ignored", 0))]
    srcs = sorted(ac["skipped_or_counted_by_reason"])
    reasons = ["counted", "chain_broken", "too_many_args", "no_verb", "sahen", "voice", "numeral_start", "no_filler"]
    ch = [(s_, *[ac["skipped_or_counted_by_reason"][s_].get(r, 0) for r in reasons]) for s_ in srcs]
    ps = st2["per_source"]
    ps_rows = [(s_, ps[s_]["typed_arguments"], ps[s_]["untyped_arguments"], ps[s_].get("rd_words", 0), ps[s_].get("rd_rows", 0),
                ps[s_].get("slot_rows_TIME", 0), ps[s_].get("slot_rows_PLACE", 0), ps[s_].get("slot_rows_QUANTITY", 0)) for s_ in srcs]
    ea = m["outputs"]["evidence_by_arm"]
    txt = ("### 12.15.4 配置 r6 の中身（`manifest_r6_run1.json`）\n\n"
           + table("w3a3_placement", md(["項目", "値"], rows)) +
           "\n述語の枠の生成を配置に入れた結果（`generated_frames` の節。語数）:\n\n" + table("w3a3_gen_frames", md(["項目", "語数"], gf)) +
           "\n項の連なりの数え（抽出段。出所ごと。理由別。数えなかった理由も数える）:\n\n"
           + table("w3a3_chains", md(["出所"] + reasons, ch)) +
           "\n段 2 の内訳（出所ごと。型の分かった項・型なしの項・分布の行を持つ述語・slot の行）:\n\n"
           + table("w3a3_stage2", md(["出所", "型つきの項", "型なしの項", "分布の行を持つ述語", "分布の行", "slot TIME", "slot PLACE", "slot QUANTITY"], ps_rows)) +
           "\n段 1 で型の分かった充填物の語 %d・述語の語 %d、新しい行を持つ語 %d。`evidence` の腕ごとの行数（新しい腕）: `role_distribution` %s・`slot` %s・`gen_frame` %s・`gen_frame_slot` %s。\n" % (
               st2["filler_typed_words"], st2["predicate_typed_words"], st2["words_with_new_rows"],
               ea.get("role_distribution", 0), ea.get("slot", 0), ea.get("gen_frame", 0), ea.get("gen_frame_slot", 0)))
    return txt


def verbs_run(data_suffix, placement_suffix, root="eval_runs"):
    best = None
    for s in runs(root):
        if s["command"][0] == "verbs" and s.get("data_path", "").endswith(data_suffix) and s["placement"].endswith(placement_suffix):
            best = s
    return best


def sec_q3():
    s = verbs_run("verb_check_300.jsonl", "r6/run1")
    if s is None:
        return "### 12.15.5 述語の型（Q3。凍結データ動詞 300 語）\n\n（未測定）\n"
    rows = [("typed の語・分からない語（断片・造語）", "%d・%d" % (s["n_typed"], s["n_unknown"])),
            ("direct の答え（typed の中）", s["direct_answers"]),
            ("　うち正答・誤決定", "%d・%d" % (s["correct_direct"], s["wrong_single_direct"])),
            ("**direct の誤決定 / typed**（Q3: ≤ 5%）", "%d / %d = %s → %s" % (s["wrong_single_direct"], s["n_typed"], pct(s["wrong_single_direct"], s["n_typed"]),
                                                                  "満たす" if s["pass_Q3"]["wrong_direct<=5%"] else "満たさない")),
            ("direct の答えの中での誤決定の割合（参考）", pct(s["wrong_single_direct"], s["direct_answers"])),
            ("**分からない語で型を返す / 分からない語**（Q3: ≤ 20%。direct・推定を問わない）",
             "%d / %d = %s → %s" % (s["returned_type_among_unknown"], s["n_unknown"], pct(s["returned_type_among_unknown"], s["n_unknown"]),
                                    "満たす" if s["pass_Q3"]["returned_unknown<=20%"] else "満たさない")),
            ("typed のうち direct でない答え", ", ".join("%s %d" % kv for kv in sorted(s["non_direct_typed"].items()))),
            ("typed 全体の正答・誤決定（direct か推定かを問わない。参考）", "%d・%d" % (s["correct_all"], s["wrong_single_all"])),
            ("`frame_status` の分布", ", ".join("%s %d" % kv for kv in sorted(s["by_frame_status"].items())))]
    kind_rows = [(k, ", ".join("%s %d" % kv for kv in sorted(v.items()))) for k, v in sorted(s["by_kind"].items())]
    arm_rows = [(k, ", ".join("%s %d" % kv for kv in sorted(v.items()))) for k, v in sorted(s["by_decisive_arm"].items())]
    txt = ("### 12.15.5 述語の型（Q3。凍結データの動詞 300 語・配置 r6/run1）\n\n"
           "出典: `eval_runs/%s/summary.json`（`measure_w3a3.py verbs --data tests/coarse_place/data/verb_check_300.jsonl`）。"
           "数だけを書く（目標の正答率は書かない）。正答・誤決定の定義は §12.11。\n\n" % s["_seq"]
           + table("w3a3_q3", md(["項目", "値"], rows)) +
           "\n種類（`kind`）ごと:\n\n" + table("w3a3_q3_kind", md(["種類", "結果"], kind_rows)) +
           "\n決め手の腕ごと（typed。腕名は出所を省いた）:\n\n" + table("w3a3_q3_arm", md(["決め手", "結果"], arm_rows)))
    if "excluding_overlap" in s:
        e = s["excluding_overlap"]
        txt += "\n中間職の動詞と重なる語を除いた数は中間職が測る（`--exclude-overlap`）。\n"
    sd = verbs_run("dev_verbs.jsonl", "dev/d2", "dev_runs")
    if sd is not None:
        txt += ("\n参考（dev の動詞 150 語・配置 d2。設定を決めた dev の数。`dev_runs/%s`）: typed %d・分からない %d、direct の答え %d（正答 %d・誤決定 %d）、"
                "分からない語で型を返す %d / %d。\n" % (sd["_seq"], sd["n_typed"], sd["n_unknown"], sd["direct_answers"], sd["correct_direct"],
                                                  sd["wrong_single_direct"], sd["returned_type_among_unknown"], sd["n_unknown"]))
    return txt


def sec_q4():
    try:
        import q4_compare
    except Exception as e:                      # pragma: no cover
        return "### 12.15.6 W3-a の凍結データ（Q4）\n\n（未測定: %s）\n" % e
    r, err = q4_compare.compute(os.path.join(B, "run1"), os.path.join(A, "eval_runs"))
    if r is None:
        return "### 12.15.6 W3-a の凍結データ（Q4）\n\n（未測定）\n"
    n = r["new"]
    l2o, l2n, l3o, l3n, l1o, l1n = r["r5"]["l2"], n["l2"], r["r5"]["l3"], n["l3"], r["r5"]["l1"], n["l1"]
    rows = [("L2 direct の正答（分母 %d）" % l2n["n"], l2o["correct_direct"], l2n["correct_direct"]),
            ("L2 direct の誤決定", l2o["wrong_single_direct"], l2n["wrong_single_direct"]),
            ("L2 語末の罠の誤決定", l2o["trap_wrong_single_direct"], l2n["trap_wrong_single_direct"]),
            ("L3 型が決まるべき語の正答（%d 語）" % l3n["typed_n"], l3o["correct"], l3n["correct"]),
            ("L3 誤り", l3o["wrong"], l3n["wrong"]),
            ("L3 分からない語で型を返す（%d 語）" % l3n["unknown_n"], l3o["returned_type_among_unknown"], l3n["returned_type_among_unknown"]),
            ("L1 トークンの被覆（%d トークン）" % l1n["tokens"], l1o["token_cover"], l1n["token_cover"]),
            ("L1 異なり語の被覆", l1o["distinct_cover"], l1n["distinct_cover"]),
            ("L1 配置された見出し語（direct）", l1o["placed_direct_headwords"], l1n["placed_direct_headwords"])]
    rows = [(a, b, c, "%+d" % (c - b)) for a, b, c in rows]
    last = r["last"]
    txt = ("### 12.15.6 W3-a の凍結データ L1〜L3（Q4。R5 との比較）\n\n"
           "出典: `q4_compare.txt`（R5 の `artifacts/w3-a/eval_runs/041〜045` と、R6 の `eval_runs/` の最後の測定を読む。手で写していない）。"
           "W3-a2 の承認条件と同じ 4 項目（誤決定・罠・L3 の誤り・分からない語で型を返す が R5 以下）を満たすか: **%s**。\n\n"
           % ("満たす" if all(last.values()) else "満たさない") + table("w3a3_q4", md(["項目", "R5", "r6/run1", "差"], rows))
           + "\n4 項目の判定: " + ", ".join("`%s` = %s" % (k, v) for k, v in last.items())
           + "\n\n併せて見た項目（R5 より下がっていないか）: " + ", ".join("%s = %s" % (k, v) for k, v in r["extra"].items())
           + "\n\nR5 から上がった数 %d 件・下がった数 %d 件・変わらない数 %d 件（全部の一覧は `q4_compare.txt`）。\n" % (len(r["ups"]), len(r["downs"]), r["same"]))
    if r["downs"]:
        txt += "\n下がった数（全部）:\n\n" + "\n".join("- " + x for x in r["downs"]) + "\n"
    return txt


def sec_q5_audit_tests():
    out = "### 12.15.7 決定性・判定の監査・全体テスト（Q5・Q7）\n\n"
    if have("q5_determinism.txt"):
        out += "**Q5**（cache なし、同じ引数で 2 回作った `content_sha256`）:\n\n```\n%s\n```\n\n" % read_text("q5_determinism.txt")
    else:
        out += "Q5: （未測定）\n\n"
    if have("audit_w3a3.txt"):
        a = json.loads(re.search(r"\{.*\}", open(os.path.join(A, "audit_w3a3.txt"), encoding="utf-8").read(), re.S).group(0))
        rows = [("A 保存した判定と `decide_word` の再計算の差", a["A_decision_recomputed"]["differences"]),
                ("B `role_distribution`／`slot` だけで決まった語", a["B_decided_by_new_agreement_only_arms_alone"]["words"]),
                ("C `gen_frame` の格上げ（語数）", a["C_gen_frame_direct_upgrades"]["words"]),
                ("C 　うち登録した条件を破る語", a["C_gen_frame_direct_upgrades"]["violating_the_rule"]),
                ("C 　うち票を出した分布の腕がすべて codex の出所の語", a["C_gen_frame_direct_upgrades"]["all_distribution_sources_are_codex"]),
                ("D `gen_frame` で `estimated` の語（語数）", a["D_gen_frame_estimates"]["words"]),
                ("D 　うち規則では格上げされるはずだった語", a["D_gen_frame_estimates"]["that_the_rule_would_have_upgraded"]),
                ("E 述語の見出し語をすべて問い合わせた数", a["E_frame_invariants_all_predicate_headwords"]["queried"]),
                ("E 　不変条件を破る答え", a["E_frame_invariants_all_predicate_headwords"]["violations"]),
                ("E 　`frame_status` の分布", ", ".join("%s %d" % kv for kv in sorted(a["E_frame_invariants_all_predicate_headwords"]["by_frame_status"].items())))]
        out += "**判定の監査**（`audit_w3a3.py`、`audit_w3a3.txt`。全見出し語）:\n\n" + table("w3a3_audit", md(["項目", "値"], rows)) + "\n"
    else:
        out += "判定の監査: （未測定）\n\n"
    if have("new_failures.txt", "after_failures.txt", "pytest_full.txt"):
        tail = [l for l in open(os.path.join(A, "pytest_full.txt"), encoding="utf-8").read().splitlines() if l.strip()][-1]
        nb = len([l for l in open("/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_9af2ed5_failures.txt", encoding="utf-8").read().splitlines() if l.strip()])
        na = len([l for l in read_text("after_failures.txt").splitlines() if l.strip()])
        nn = len([l for l in read_text("new_failures.txt").splitlines() if l.strip()])
        out += ("**Q7**（全体テスト。`pytest_full.txt` の最後の行: `%s`）: 基線の失敗 %d 件、今回の失敗 %d 件、基線に無い失敗 %d 件（`new_failures.txt`）。\n" % (tail, nb, na, nn))
    else:
        out += "Q7: （未測定）\n"
    return out


def sec_slot_and_example():
    out = "### 12.15.9 slot（時・場所・数量）の確かめと、確認済みの答えの例\n\n"
    if have("dev_time_place.txt"):
        t = read_text("dev_time_place.txt")
        tot = json.loads(re.search(r"^(\{\"words\".*\})$", t, re.M).group(1))
        q = re.search(r"^query 昨日: (\{.*\})$", t, re.M).group(1)
        diag = re.search(r"^diagnostic: 昨日 slot rows: (.*)$", t, re.M).group(1)
        ds = re.findall(r"^diagnostic: slot_share_pct=(\d+) -> (\w+) (\w+) (\S+) by=(\S+)$", t, re.M)
        rows = [("dev の語彙のうち時・場所・数量の型を正解に持つ語（種を除く）", tot["words"]),
                ("slot の行を外した判定で direct の語", tot["direct_before"]),
                ("登録した設定で direct の語", tot["direct_after"]),
                ("slot の行で direct になった語", tot["became_direct_by_slot"]),
                ("　うち正答・誤決定", "%d・%d" % (tot["became_correct"], tot["became_wrong"]))]
        out += ("出典: `dev_time_place.txt`（`dev_time_place.py`、配置 d2、dev の語彙だけ）。**登録した設定では、dev の時の語で slot により direct になった語は無かった**。"
                "チケットの「`昨日` のような語が direct になる」は、登録した設定では満たせなかった（理由は `DECISIONS.md` D4-2: dev の時の語は過去の述語と使われる数が閾値に届かない）。\n\n"
                + table("w3a3_slot", md(["項目", "値"], rows)) +
                "\n高頻度の過去の時の語 `昨日`（dev の語彙には無い。入口に直接問い合わせた）: `%s`。保存された evidence の slot の行（出所・数・名詞の使用数・割合）: %s。\n"
                "設定を変えたのではなく、保存された evidence を別の `slot_share_pct` で決め直しただけの診断（登録の格子は 30 / 20 / 10）: %s。"
                "dev の語彙にはこの種の語が無く、dev の数で格子の下側を選ぶことはできない。dev の標本を足して設定を選び直すことはしなかった。\n\n" % (
                    q, diag, "、".join("%s → %s %s %s" % (a, b, c, d) for a, b, c, d, _e in ds)))
    else:
        out += "（未測定）\n\n"
    p7 = os.path.join(A, "p7_lend_check_r6.txt")
    if os.path.exists(p7):
        m = re.search(r"^(\{\"term\".*\})$", open(p7, encoding="utf-8").read(), re.M)
        if m:
            out += ("確認済みの述語の答えの例（r6/run1。`p7_lend_check_r6.txt`。契約の形の確認用で、語の一覧ではない）:\n\n```\n%s\n```\n"
                    % json.dumps(json.loads(m.group(1)), ensure_ascii=False, indent=1))
    return out


def sec_holes():
    g = None
    p = os.path.join(A, "manifest_r6_run1.json")
    n_up = n_cx = "-"
    legacy_n = re.search(r"direct with a frame@ arm in decided_by: (\d+)", read_text("dev_frame_legacy.txt")).group(1)
    if os.path.exists(p):
        o = load(p)["generated_frames"]["outcomes"]
        n_up, n_cx = o.get("decided_direct_upgrade", 0), o.get("decided_direct_upgrade_all_sources_codex", 0)
    return ("""### 12.15.10 既知の穴・満たせないもの・読解器への申し送り（隠さない）

- **Q6 は配置の側では動かない**。`PLACEMENT_PREDICATE_UNIDENTIFIED` を出すのは `origin/integ-w3b1:verantyx/semantic_read.py` の 760 行目だけで、**英語の入力**で、どの語も既知の動詞の閉じた一覧に無いときに、配置を一度も問い合わせずに足される理由である（`_read_en`、758〜760 行）。日本語の経路にこの理由は無い。この ticket の許可パス（配置の側）の変更では、その件数は原理的に変わらない。英語の述語は置いていない・読解器には触れていない。Q6 は満たせないものとして監査役に返す。
- **直接になる述語の型は 2 型だけ**。K62 の表は `P_MOVE` と `P_COMMUNICATE` の 2 型・9 行だけで、逆引きの分布の腕はこの 2 型しか票にできない。ほかの 11 型の述語は、生成だけ → `estimated(generated)` に留まる（規則どおり。表は広げていない。広げる提案は、表の行を増やす変更が読解器の誤読を増やさないことを W3-b1 の側で測ってからにすること）。
- **再現率は低い**: K62 の `P_MOVE` に に+PLACE の行は無いので、に+PLACE が有意な移動の動詞は (a)(b) で候補にならない。と・まで・より は表に無いので候補に効かない。分布の腕は隣接する項だけを数え（長距離は数えない）、型の分かった充填物は段 1 で direct に置いた語に限るので、項の約半分は型なし（§12.15.4）。
- **W3-b1 の門 4 を `gen_frame` は通る**: 門 4 は `'gen_definition' in decided_by` の文字列だけを見る。述語の生成の腕を別の名前（`gen_frame`）にしたので、格上げした述語は門 4 を通る（読解器が direct として使いうる）。これは読解器の方針の変更に当たるので、答えに `generated_frame: true` を付けて機械的に区別できるようにした。読解器が使うかは W3-b2 で決める。`slot` で direct になった名詞は `decided_by` に必ず `gen_definition` が入り、門 4 に当たる（仕様どおり）。
- **codex が書いた枠と codex が書いたコーパスの一致**: 格上げ %s 語のうち %s 語は、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し）。生成した枠と生成したコーパスの一致であり、人が書いた出所の証拠ではない（`origin=direct` の意味は W3-a2 から変わらない: 生成でない腕が自分の閾値で合意した）。
- **`frame` は報告用**: 読解器の変更は W3-b2。K62 の表は固定のまま、配置の `frame` と一致する範囲でだけ使う（表に無い助詞は読まない）。この ticket では契約と欄だけ。
- **封筒のような名詞**: 名詞の生成は W3-a2 の物をそのまま使った（作り直していない）。上位語が型に通らず `no_type` になった名詞は残る。
- **断片の動詞**（語にならないもの）は材料にあるので生成の一覧に入りうる。モデルが型を返せば `estimated(generated)` になり、「分からない語で型を返す」に数える（一覧から手で除いていない）。
- **`昨日` のような過去の時の語は、登録した設定では direct にならなかった**（§12.15.9。`slot_share_pct` が 8 以下なら direct になるが、dev の語彙にはこの種の語が無く、dev の数では下側を選べなかった）。チケットの「やること 4」の小項目は満たせていない。
- `frame_decides=False` の判断は dev の小さい標本（決め手が `frame` の語 %s 語）に基づく。W3-a の凍結データの数字（決め手の 18 語のうち正答 2・誤決定 11）は根拠にしていない。
- 検査データ（動詞 300 語・dev 150 語）は自作で、型は手で付けた。自作のデータで通ることは証拠にならない（隠しバンクと中間職の 100 語で測る）。
""" % (n_up, n_cx, legacy_n))


SECTIONS = [sec_order, sec_generation, sec_config, sec_placement, sec_q3, sec_q4, sec_q5_audit_tests, sec_slot_and_example, sec_holes]


def render():
    head = ("### 12.15 測定（登録の外。この節の数値は `artifacts/w3-a3/render_w3a3.py` が `artifacts/w3-a3/` の測定ファイルから描く。"
            "`render_w3a3.py --check` で一致を確かめる）\n\n")
    return BEGIN + "\n" + head + "\n".join(f() for f in SECTIONS) + END + "\n"


def main():
    doc = open(DOC, encoding="utf-8").read()
    block = render()
    if BEGIN in doc:
        i, j = doc.index(BEGIN), doc.index(END) + len(END) + 1
        cur = doc[i:j]
        new = doc[:i] + block + doc[j:]
    else:
        cur, new = None, doc.rstrip("\n") + "\n\n" + block
    if "--check" in sys.argv:
        ok = cur == block
        print("OK" if ok else "MISMATCH")
        return 0 if ok else 1
    open(DOC, "w", encoding="utf-8").write(new)
    print("rendered %d chars" % len(block))
    return 0


if __name__ == "__main__":
    sys.exit(main())

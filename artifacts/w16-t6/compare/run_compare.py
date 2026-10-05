"""W16-t6 / T6-2 (K602): 同じ 40 件・同じ事実の集合に V・a・b と LLM 判定器 c（qwen3.5:4b、温度 0、3 回）を並べる。
使い方: python run_compare.py <作業ディレクトリ(tmp)> <出力ディレクトリ(artifacts/w16-t6/compare)>
生データ: llm_prompts.jsonl（事実ごとのプロンプト全文）・llm_run{1,2,3}.jsonl（各回の生の答え）・llm_meta.json。表: compare_table.md / compare_table.json（recompute.py が生データから再計算して照合する）。
"""
import datetime
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYN = HERE.parent / "synth"
spec = importlib.util.spec_from_file_location("synth_lib", SYN / "synth_lib.py")
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)
RUNS = 3


def items_for(attest, cases, expected, results):
    """One item per expected fact that V produced: the V claim line and the V fact (its raw observation). c sees these, never the verifier's mark."""
    items = []
    for case, exp in zip(cases, expected):
        vclaims = results[case["id"]]["extractors"]["V"]["claims"]
        facts = {}
        for c in vclaims:
            for f in c["facts"]:
                facts.setdefault(f["fact"], (c, f))
        for ec in exp["claims"]:
            for ef in ec["facts"]:
                if ef["sig"] in facts:
                    c, f = facts[ef["sig"]]
                    items.append({"case": case["id"], "sig": ef["sig"], "truth": ef["truth"], "claim_text": c["text"], "fact": f})
    return items


def ollama_digest(model):
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=10) as r:
            for m in json.loads(r.read())["models"]:
                if m["name"] == model:
                    return m.get("digest")
    except Exception as e:           # recorded as it is
        return "unavailable: %s" % type(e).__name__
    return None


def table(metrics, llm, n_facts):
    """The numbers of compare_table.md. metrics: synth metrics (V, a, b); llm: per-run metrics of c."""
    rows = {}
    for ex in ("V", "a", "b"):
        m = metrics[ex]
        rows[ex] = {"対象の事実": m["facts"], "偽": m["false_facts"], "検出": m["detected"], "検出率": m["detection_rate"], "見逃し": m["missed"], "誤検出": m["false_positive"],
                    "裏づけ不足": m["insufficient"], "未抽出": m["not_extracted"], "余剰": m["extra"], "揺れ": None}
    for i, x in enumerate(llm["runs"], 1):
        rows["c%d" % i] = {"対象の事実": x["facts"], "偽": x["false_facts"], "検出": x["detected"], "検出率": x["detection_rate"], "見逃し": x["missed"], "誤検出": x["false_positive"],
                           "裏づけ不足": x["insufficient"], "未抽出": 0, "余剰": 0, "揺れ": None, "LLM_UNPARSEABLE": x["unparseable"]}
    rows["c"] = {"揺れ": llm["unstable"], "揺れ分母": llm["facts"]}
    V = metrics["V"]["detection_rate"]
    lift = {"V-a": V - metrics["a"]["detection_rate"], "V-b": V - metrics["b"]["detection_rate"]}
    for i, x in enumerate(llm["runs"], 1):
        lift["V-c%d" % i] = V - x["detection_rate"]
    return {"rows": rows, "lift": lift}


def llm_metrics(items, runs):
    out = {"runs": [], "facts": len(items)}
    for run in runs:
        ans = {(r["case"], r["sig"]): r["answer"] for r in run}
        m = dict(facts=len(items), false_facts=0, detected=0, missed=0, abstain_false=0, false_positive=0, insufficient=0, unparseable=0)
        for it in items:
            a = ans[(it["case"], it["sig"])]
            if a == "LLM_UNPARSEABLE":
                m["unparseable"] += 1
            if it["truth"] == "false":
                m["false_facts"] += 1
                m["detected" if a == "LLM_NO" else "missed" if a == "LLM_YES" else "abstain_false"] += 1
            elif it["truth"] == "true":
                if a == "LLM_NO":
                    m["false_positive"] += 1
                elif a in ("LLM_UNKNOWN", "LLM_UNPARSEABLE"):
                    m["insufficient"] += 1
        m["detection_rate"] = m["detected"] / m["false_facts"]
        out["runs"].append(m)
    keys = [(it["case"], it["sig"]) for it in items]
    per = [{(r["case"], r["sig"]): r["answer"] for r in run} for run in runs]
    out["unstable"] = sum(1 for k in keys if len({p[k] for p in per}) > 1)
    return out


def md(t, meta):
    r, lift = t["rows"], t["lift"]
    cols = ["対象の事実", "偽", "検出", "検出率", "見逃し", "誤検出", "裏づけ不足", "未抽出", "余剰"]
    lines = ["# T6-2 対照表（合成 40 件、事実単位。数値はすべて t6_1_synth.json・llm_run{1,2,3}.jsonl・expected.jsonl から再計算できる: recompute.py）", "",
             "| 抽出器 | " + " | ".join(cols) + " | 揺れ |", "|" + "---|" * (len(cols) + 2)]
    for k in ("V", "a", "b", "c1", "c2", "c3"):
        cells = []
        for c in cols:
            v = r[k][c]
            cells.append("%.4f" % v if isinstance(v, float) else str(v))
        extra = ""
        if k == "c1":
            extra = "%d / %d" % (r["c"]["揺れ"], r["c"]["揺れ分母"])
        lines.append("| %s | %s | %s |" % (k, " | ".join(cells), extra or "-"))
    lines += ["", "- 偽の申告の検出率 = 検出／偽の事実数。未抽出の偽の事実は検出に入らない（分母は偽の事実の全数）。", "- c1〜c3 は同じプロンプト・温度 0 の 3 回。揺れ = 3 回で答えが割れた事実の数／全事実数（c の行にだけ意味がある）。",
              "- c の LLM_UNPARSEABLE（読めない答え）: " + ", ".join("%s=%d" % (k, r[k]["LLM_UNPARSEABLE"]) for k in ("c1", "c2", "c3")) + "。", "", "## 上乗せ（V の検出率 − 相手の検出率）"]
    for k, v in lift.items():
        lines.append("- %s: %.4f%s" % (k, v, "（0）" if abs(v) < 1e-12 else ""))
    lines += ["", "モデル: %s、digest: %s、開始 %s、終了 %s。" % (meta["model"], meta["digest"], meta["started"], meta["ended"])]
    return "\n".join(lines) + "\n"


def main(work, out):
    sys.path.insert(0, str(HERE.parents[2]))
    from verantyx import attest
    cases, expected, results, metrics = sl.run_all(attest, work, ("V", "a", "b"))
    items = items_for(attest, cases, expected, results)
    out = Path(out)
    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    prompts = [{"case": it["case"], "sig": it["sig"], "prompt": attest.llm_prompt(it["claim_text"], it["fact"])} for it in items]
    (out / "llm_prompts.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in prompts), encoding="utf-8")
    runs = []
    for i in range(1, RUNS + 1):
        rows = []
        for it, p in zip(items, prompts):
            j = attest.llm_judge(it["claim_text"], it["fact"])
            assert j["prompt"] == p["prompt"]
            rows.append({"case": it["case"], "sig": it["sig"], "truth": it["truth"], "answer": j["answer"], "raw": j["raw"], "ok": j["ok"], "type": j["type"]})
        (out / ("llm_run%d.jsonl" % i)).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        runs.append(rows)
        print("run", i, "done", file=sys.stderr)
    ended = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    meta = {"model": attest.LLM_MODEL, "digest": ollama_digest(attest.LLM_MODEL), "temperature": 0.0, "think": False, "num_predict": 64, "runs": RUNS, "started": started, "ended": ended,
            "prompt_template": attest.LLM_PROMPT, "prompt_version": attest.LLM_PROMPT_VERSION, "n_items": len(items), "note": "答えは generated。台帳に書かず、記録に上げない"}
    (out / "llm_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    t = table(metrics, llm_metrics(items, runs), len(items))
    (out / "compare_table.json").write_text(json.dumps(t, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (out / "compare_table.md").write_text(md(t, meta), encoding="utf-8")
    print(md(t, meta))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

"""MEM-fix (2): what the answer run's `recall` reaches, BEFORE and AFTER, on the stored memories of a meter -- offline, no API.

A scripted ORACLE answerer: for every structure run (blind / notes) of the meter and each of its 10 recorded questions it calls `recall` with the question text, over the snapshot the stored
answer runs were begun on, and nothing else (it never weaves, never emits).  BEFORE = recall as the meter had it (the question as asked); AFTER = recall with the store's declared topics
(`memrecall.recall(topics=...)`: the question as asked, the topic-expanded form for a subject-less question, and -- only if nothing answered -- the subject read as the fused slot).
The evidence gate is the same code in both.  Per question:
  reached        every gold value (1 for update / plain, 2 for a contradiction) is among the answers of the live groups
  exact          reached AND nothing else: plain / updated -> verdict ANSWER with the gold as its only answer; contradicted -> verdict CHOICE with exactly the two gold values
  noisy          answers that are no gold value
`strict` matches by equality after the gate's normalisation; `lenient` also lets a unit after a number differ (37.0 / 37.0℃).
  python experiments/line3/mem/memfix/offline_reach.py [--meter DIR] [--out DIR]       -> reach_report.json, reach_report.md
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import memfix_common as C
from verantyx.loom import evidence as ev
from verantyx.loom import memrecall as mr


def live_answers(res: dict) -> List[str]:
    out: List[str] = []
    for g in res["answers"]:
        for a in g["answers"]:
            if a not in out:
                out.append(a)
    return out


def judge(res: dict, kind: str, gold_vals: Sequence[str], lenient: bool) -> dict:
    ans = live_answers(res)
    hit = [any(C.match(g, a, lenient) for a in ans) for g in gold_vals]
    extra = [a for a in ans if not any(C.match(g, a, lenient) for g in gold_vals)]
    reached = bool(ans) and all(hit)
    want_verdict = "CHOICE" if kind == "contradicted" else "ANSWER"
    exact = reached and not extra and res["verdict"] == want_verdict and len(res["answers"]) == len(gold_vals) if kind == "contradicted" else reached and not extra and res["verdict"] == "ANSWER"
    return {"reached": reached, "exact": exact, "noisy": bool(extra), "answers": ans}


def evaluate_run(run_dir: str) -> dict:
    r = C.load_result(run_dir)
    store = os.path.join(run_dir, "store")
    corpus, rows, sup = C.snapshot_corpus(store)
    topics = C.topics_of_store(store)
    qs = []
    for a in sorted(r["answers"], key=lambda a: a["index"]):
        gk, gv = C.mem_run.gold_values(a["gold"])
        q = {"index": a["index"], "q": a["q"], "kind": a["kind"], "gold": gv, "model_answer": a["answer"]}
        for name, tp in (("before", None), ("after", topics)):
            res = mr.recall(corpus, a["q"], ev.EVIDENCE_V2, subject_guard=True, superseded=sup or None, topics=tp or None)
            q[name] = {"verdict": res["verdict"], "strict": judge(res, a["kind"], gv, False), "lenient": judge(res, a["kind"], gv, True)}
            if tp:
                q[name]["forms"] = [f["form"] for f in res.get("forms", {}).get("tried", []) if f["passes"]]
        qs.append(q)
    return {"run": C.label(run_dir), "arm": r["arm_label"], "task": r["task_id"], "topics": topics, "sentences": len(rows), "questions": qs}


def tally(runs: Sequence[dict]) -> dict:
    t: Dict[str, Any] = {}
    for when in ("before", "after"):
        for mode in ("strict", "lenient"):
            for kind in ("contradicted", "updated", "plain", "all"):
                t.setdefault(when, {}).setdefault(mode, {})[kind] = {"n": 0, "reached": 0, "exact": 0, "noisy": 0}
    for r in runs:
        for q in r["questions"]:
            for when in ("before", "after"):
                for mode in ("strict", "lenient"):
                    for kind in (q["kind"], "all"):
                        c = t[when][mode][kind]
                        c["n"] += 1
                        for k in ("reached", "exact", "noisy"):
                            c[k] += 1 if q[when][mode][k] else 0
    return t


def forms_tally(runs: Sequence[dict]) -> dict:
    """Among the questions the AFTER recall reached (strict) and the BEFORE recall did not: which forms of the question had passes ({'topic': n, 'subject': n, ...} by the set of forms)."""
    c: Dict[str, int] = collections.Counter()
    for r in runs:
        for q in r["questions"]:
            if q["after"]["strict"]["reached"] and not q["before"]["strict"]["reached"]:
                c["+".join(sorted(set(q["after"].get("forms", [])), key=mr.FORM_ORDER.index))] += 1
    return dict(sorted(c.items()))


def md_table(t: dict, title: str) -> str:
    lines = ["### %s" % title, "", "| 質問の種類 | n | 到達 前 | 到達 後 | 厳密一致 前 | 厳密一致 後 | 余計な値あり 前 | 余計な値あり 後 |", "|---|---|---|---|---|---|---|---|"]
    names = {"contradicted": "矛盾質問", "updated": "更新質問", "plain": "平文質問", "all": "**全体**"}
    for kind in ("contradicted", "updated", "plain", "all"):
        b, a = t["before"]["strict"][kind], t["after"]["strict"][kind]
        lines.append("| %s | %d | %d | %d | %d | %d | %d | %d |" % (names[kind], b["n"], b["reached"], a["reached"], b["exact"], a["exact"], b["noisy"], a["noisy"]))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meter", default=C.METER_V1)
    ap.add_argument("--out", default=os.path.join(C.HERE, "results"))
    ns = ap.parse_args(argv)
    runs = [evaluate_run(d) for d in C.structure_runs(ns.meter)]
    out = {"meter": os.path.relpath(ns.meter, C.ROOT), "runs": len(runs), "forms_version": mr.FORMS_VERSION, "total": tally(runs),
           "newly_reached_by_form": forms_tally(runs), "by_arm": {arm: tally([r for r in runs if r["arm"] == arm]) for arm in ("A2b", "A2")},
           "by_task": {task: tally([r for r in runs if r["task"] == task]) for task in sorted({r["task"] for r in runs})}, "per_run": runs}
    os.makedirs(ns.out, exist_ok=True)
    with open(os.path.join(ns.out, "reach_report.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, indent=1)
        f.write("\n")
    md = ["# MEM-fix 想起の到達（offline, API なし）", "", "meter_v1 の構造 arm %d run（%d 問）の保存済み記憶に、回答 run の `recall` を質問文のまま呼ぶ oracle で、金の値に届くか。前 = 現行 recall、後 = 主題を知った recall。" % (len(runs), sum(len(r["questions"]) for r in runs)), ""]
    md.append(md_table(out["total"], "全 %d run（厳密一致の照合）" % len(runs)))
    md.append("")
    md.append(md_table({w: {"strict": out["total"][w]["lenient"]} for w in ("before", "after")}, "全 %d run（寛容な照合: 数値の後ろの単位の差を許す）" % len(runs)))
    for arm in ("A2b", "A2"):
        md += ["", md_table(out["by_arm"][arm], "arm %s" % arm)]
    md += ["", "### 後で新しく届いた質問（前は届かず、後は届いた）を読んだ形の別", "", "| 質問を読めた形 | 質問数 |", "|---|---|"]
    md += ["| %s | %d |" % (k, v) for k, v in out["newly_reached_by_form"].items()]
    with open(os.path.join(ns.out, "reach_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

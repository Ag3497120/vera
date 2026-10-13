"""PUB-M6b diagnosis (4): WHY the rephrased checkpoint questions of bank_ls dev are not answered by `memask.recall`.  Offline, no model, ~20 s, single process.

Reads ONLY the two dev stories of bank_ls (experiments/line3/bank_ls/dev/stories.jsonl; held-out splits are never opened).  Each story is written as bank_ls_dev.py writes it, but without sessions or ledgers:
the writes the exchanger accepts (every clause F1-F4) are folded into one `IndexBuilder`, the title is declared as the topic of every session when it is at most 24 characters (D02's title has 25: the real
`declare_topic` refuses it, so D02 runs without a nest), and at the end of each checkpoint's session the questions of that checkpoint are asked (`memask.recall`) and diagnosed.

For every non-absent question: the stored sentence(s) that hold the gold (the messages of `refs`, the chunks that contain a gold value), the exchanger's reading of them, the reading of the question, and the FIRST
stage of the recall pipeline that fails:
   Q1  the question is not read (`question_unparsed:<why>`; the frame of the question is F0 or has no question word)
   Q2  the question is read as an EVENT (F3 / F4: 「鍵は何時に開けますか」) and the memory holds an attribute (「解錠時刻は6時40分」)
   Q3  the question is an attribute question and no stored position has its slot noun (`no_position`)
   Q0  reached
plus the other blockers: the stored sentence is F0 (never indexed), the fact is stored as an event (F3: 「Xは Bで 台帳に載せた」) that an attribute question cannot see.
THEN, as a SIMULATION that changes nothing in the code: a unit-overlap route (positions that share >= N content units with the question, value of the type the question word asks, unique best score) and what it
would have reached / got wrong / admitted on the absent questions -- the numbers an owner decision needs.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/diag_paraphrase.py      -> diag_paraphrase.{json,md}
"""
from __future__ import annotations

import collections
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import common as K
from common import C, mem, mask
from verantyx.loom import memcross as mx
from verantyx.loom import memnotes as mn
from verantyx.loom import memqwords as qw
from verantyx.loom import memshape as ms
from verantyx.loom.corpus import Corpus
from verantyx.loom.memguard import make_source

DEV = os.path.join(K.ROOT, "experiments", "line3", "bank_ls", "dev", "stories.jsonl")
CAP = 64
TYPE = {"when": re.compile(r"\d+日|\d+月|曜"), "clock": re.compile(r"\d+時"), "count": re.compile(r"\d"), "money": re.compile(r"\d.*円"), "duration": re.compile(r"\d.*(分|秒|時間|日)"),
        "temperature": re.compile(r"\d.*(度|℃)"), "length": re.compile(r"\d"), "weight": re.compile(r"\d"), "rate": re.compile(r"\d.*[%％]")}


def chunks(text: str) -> List[str]:
    if len(text) <= CAP:
        return [text]
    out: List[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def units(s: str) -> List[str]:
    return [t.s for t in ms._tokens(s) if not t.fn]


def type_ok(qword: Optional[str], val: str) -> bool:
    cls = qw.class_of_word(qword) if qword else None
    if cls in TYPE:
        return bool(TYPE[cls].search(val))
    if qword and qword.startswith("何") and len(qword) > 1:
        return qword[1:] in val or (qword[1:] == "日" and bool(re.search(r"\d+日", val)))
    return True


def lcs_len(a: str, b: str) -> int:
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            best = max(best, k)
    return best


def gold_in(vals: List[str], gv: List[str]) -> bool:
    return all(any(mn.norm_answer(g) == mn.norm_answer(v) or mn.norm_answer(g) in mn.norm_answer(v) for v in vals) for g in gv)


def run_story(st: Dict[str, Any]) -> List[Dict[str, Any]]:
    title = st["title"]
    topic_ok = len(title) <= mem.TOPIC_MAX_CHARS
    cp = {c["index"]: c["after_session"] for c in st["checkpoints"]}
    by_cp: Dict[int, List[dict]] = {}
    for q in st["questions"]:
        by_cp.setdefault(cp[q["checkpoint"]], []).append(q)
    b = mx.IndexBuilder()
    rows: List[dict] = []
    allc: List[dict] = []
    out: List[Dict[str, Any]] = []
    for si, sess in enumerate(st["sessions"]):
        if topic_ok:
            b.declare(si + 1, len(rows), title)
        for mi, m in enumerate(sess):
            for c in chunks(m["text"]):
                ex = ms.exchange(c, ms.SHAPES_V2)
                acc = bool(ex.clauses) and all(x.shape != "F0" for x in ex.clauses)
                allc.append({"s": si, "m": mi, "text": c, "acc": acc, "clauses": [(x.shape, x.reason, x.centre, x.text) for x in ex.clauses]})
                if acc:
                    row = {"kind": "base", "sent": c, "source": make_source("m", si + 1, len(rows)), "turn": C.mem_run.turn_id(si, mi)}
                    b.add_row(len(rows), row, Corpus(mem.rows_bytes(rows)) if rows else Corpus(b""))
                    rows.append(row)
        for q in by_cp.get(si, []):
            ix = b.index()
            corpus = Corpus(mem.rows_bytes(rows))
            res = mask.recall(ix, rows, corpus, q["q"])
            qy = mask.parse_question(q["q"])
            absent = q["kind"] == "absent"
            gk, gv = ("none", []) if absent else C.mem_run.gold_values(q["gold"])
            refs = q.get("refs") or []
            facts = [] if absent else [c for c in allc if [c["s"], c["m"]] in refs and any(g in c["text"] for g in gv)]
            shapes = []
            for c in facts:
                gx = [x for x in c["clauses"] if any(g in x[3] for g in gv)]
                shapes.append(("ACC" if c["acc"] else "F0", [x[0] for x in (gx or c["clauses"])], [x[1] for x in c["clauses"] if x[0] == "F0"]))
            attr_ok = any(s[0] == "ACC" and any(sh in ("F1", "F2") for sh in s[1]) for s in shapes)
            f0_all = bool(shapes) and all(s[0] == "F0" for s in shapes)
            f0_any = any(s[0] == "F0" for s in shapes)
            if res["verdict"] != "NONE" and not absent:
                cause = "Q0 reached"
            elif not qy.ok:
                cause = "Q1 question not read (%s)" % qy.reason
            elif qy.shape in ("F3", "F4"):
                cause = "Q2 question read as an event (%s), memory holds an attribute" % qy.shape if attr_ok else "Q2b question read as an event, memory holds an event"
            else:
                cause = "Q3 attribute question, no position with its slot noun"
            other = []
            if f0_any:
                other.append("stored sentence F0 (%s)" % ("all" if f0_all else "one of two"))
            if shapes and not attr_ok and not f0_all:
                other.append("fact stored as an event (F3)")
            # the simulation: a unit-overlap route (NOT in the code)
            qwd = qy.qword
            if qwd is None:
                h = qw.find_word(mask._clean(q["q"]))
                qwd = h[1] if h else None
            qu = [u for u in units(mask._clean(q["q"])) if not (qwd and u in qwd) and u != "QQ"]
            cands = []
            for p in ix.positions:
                if p[0] not in ("F1", "F2"):
                    continue
                live = [e for e in ix.history_full(p) if not e.marks]
                if not live:
                    continue
                pu = units("".join(ph for _, ph in p[2]) + p[1])
                pu = [u for _, ph in p[2] for u in units(ph)] + units(p[1])
                sc = len([u for u in dict.fromkeys(qu) if u in pu])
                if sc:
                    cands.append((sc, p, [e.value for e in live], type_ok(qwd, live[-1].value)))
            cands.sort(key=lambda x: -x[0])
            sim = {}
            for thr in (1, 2, 3):
                cs = [x for x in cands if x[0] >= thr and x[3]]
                if not cs:
                    sim[thr] = "none"
                    continue
                tied = [x for x in cs if x[0] == cs[0][0]]
                if len(tied) > 1:
                    sim[thr] = "tie"
                elif absent:
                    sim[thr] = "admitted"
                else:
                    sim[thr] = "gold" if gold_in(tied[0][2], gv) else "wrong"
            out.append({"story": st["id"], "checkpoint": q["checkpoint"], "kind": q["kind"], "form": q["form"], "q": q["q"], "gold": q["gold"], "stored_slot": q.get("stored_slot"), "asked_slot": q.get("asked_slot"),
                        "stored_sentence": [c["text"] for c in facts][:2], "stored_shapes": shapes[:2], "verdict": res["verdict"], "route": res.get("route"), "issues": res.get("issues"), "qword": qwd,
                        "question_read": {"ok": qy.ok, "reason": qy.reason, "shape": qy.shape, "centre": qy.centre, "path": [list(x) for x in qy.path], "asked": qy.asked, "frame": qy.frame},
                        "cause": cause, "other": other, "slot_overlap_chars": lcs_len(q.get("stored_slot") or "", q.get("asked_slot") or ""), "overlap_route_sim": sim,
                        "overlap_top": [(c[0], c[1][1], [list(x) for x in c[1][2]], c[2]) for c in cands[:2]]})
    return out


def main() -> int:
    stories = [json.loads(ln) for ln in open(DEV, encoding="utf-8") if ln.strip()]
    rows: List[Dict[str, Any]] = []
    for st in stories:
        rows += run_story(st)
    reph = [r for r in rows if r["form"] == "rephrased"]
    same = [r for r in rows if r["form"] == "same"]
    absent = [r for r in rows if r["kind"] == "absent"]
    causes = collections.Counter(r["cause"].split(" (")[0] if r["cause"].startswith("Q1") else r["cause"] for r in reph)
    q1 = collections.Counter(r["cause"] for r in reph if r["cause"].startswith("Q1"))
    other = collections.Counter(o for r in reph for o in r["other"])
    sim = {str(t): dict(collections.Counter(r["overlap_route_sim"][t] for r in reph)) for t in (1, 2, 3)}
    sim_abs = {str(t): dict(collections.Counter(r["overlap_route_sim"][t] for r in absent)) for t in (1, 2, 3)}
    res = {"rephrased": len(reph), "rephrased_reached": sum(1 for r in reph if r["cause"].startswith("Q0")), "same_form": len(same), "same_form_reached": sum(1 for r in same if r["verdict"] != "NONE"),
           "absent": len(absent), "absent_admitted": sum(1 for r in absent if r["verdict"] != "NONE"), "primary_cause": dict(sorted(causes.items())), "question_not_read": dict(sorted(q1.items())),
           "other_blockers": dict(sorted(other.items())), "overlap_route_simulation": {"rephrased": sim, "absent": sim_abs}, "questions": rows}
    K.write_json(os.path.join(K.OUT, "diag_paraphrase.json"), res)
    md = ["# PUB-M6b (4) — bank_ls dev の言い換えの問いが外れる理由（offline、dev 2 本）", "",
          "言い換え %d 問のうち到達 %d。同じ言い方 %d 問のうち到達 %d。存在しない問い %d のうち答えを出した %d。" % (res["rephrased"], res["rephrased_reached"], res["same_form"], res["same_form_reached"], res["absent"], res["absent_admitted"]), "",
          "## 最初に落ちる段（言い換え %d 問）" % len(reph), ""]
    for k, v in sorted(causes.items()):
        md.append("- %s: %d" % (k, v))
    md += ["", "問いが読めない内訳: %s" % dict(sorted(q1.items())), "", "ほかの妨げ（重なることがある）: %s" % dict(sorted(other.items())), "",
           "## 単位の重なりの経路のシミュレーション（コードには入れていない）", "",
           "位置（F1 / F2）のうち、問いの内容語の単位との共有が N 以上、値の型が問い語に合い、最高点が一意のもの。言い換え: %s。存在しない問い: %s。" % (sim, sim_abs), "",
           "## 全問", "", "| 物語 | 種類 | 問い | 金の値 | 保存された文 | 保存の席 / 問いの席 | 読み | 最初に落ちる段 | ほかの妨げ | 重なり N=2 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["kind"] == "absent":
            continue
        qr = r["question_read"]
        read = ("%s %s %s" % (qr["shape"], qr["centre"], qr["path"])) if qr["ok"] else qr["reason"]
        md.append("| %s | %s/%s | %s | %s | %s | %s / %s | %s | %s | %s | %s |" % (r["story"][-3:], r["kind"][:4], r["form"][:4], r["q"], r["gold"], " // ".join(r["stored_sentence"]) or "(none)", r["stored_slot"], r["asked_slot"], read,
                                                                                    r["cause"], "; ".join(r["other"]) or "-", r["overlap_route_sim"][2]))
    K.write_text(os.path.join(K.OUT, "diag_paraphrase.md"), "\n".join(md) + "\n")
    print("\n".join(md[:24]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

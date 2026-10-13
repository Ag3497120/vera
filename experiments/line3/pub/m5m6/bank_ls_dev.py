"""PUB-M5/M6 offline measurement (c): the two DEV stories of bank_ls (experiments/line3/bank_ls/dev/stories.jsonl; the held-out splits are never opened), no model, no API.

Every message text is one write (a text over 64 characters, the cap of one write, is cut after 「。」 into writes of its own), one mem.v4 session per story session, the story title declared as the topic of every
session; a refused write (F0) is only counted (no keep_unshaped).  At the end of each checkpoint's session the checkpoint's questions are asked of the crosses as they stand (`memask.recall` on the live index,
no open nest: the answer phase has none) and scored against the gold.  The notes made on the crosses are compared with the plants (contradiction / update / reversal / list_trap / repeat) at the end.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/bank_ls_dev.py [--workers 4] [--verify]      -> bank_ls_dev.{json,md}
`--verify` also runs verify_store (a replay that rebuilds the index of every session from scratch: quadratic, minutes per story).

PUB-M6c (`--m6c`): the same stories with the bundle shape.v3 / ask.v3 / qwords.v2; outputs to experiments/line3/pub/m6c/bank_ls_dev.{json,md}.  A question for which recall offers CANDIDATES is followed by the
ORACLE's bridge: the "model" that confirms ONLY THE TOP candidate (an upper bound, not a model result; the bridge is applied to a copy of the bridges, nothing is written into the session).  Reported: candidates
offered, the gold among them (and its rank), what the oracle's bridge reaches / gets wrong, and for the absent questions the candidates offered and what the oracle's bridge would ADMIT (must stay 0).

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/bank_ls_dev.py --m6c [--workers 4]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence

import common as K
import meter as M
from verantyx.loom import memcross as mx
from common import C, mem, mask

DEV = os.path.join(K.ROOT, "experiments", "line3", "bank_ls", "dev", "stories.jsonl")
MODE: Dict[str, Any] = {"m6c": False}                              # set by main() before the workers fork
M6C_DIR = os.path.join(K.ROOT, "experiments", "line3", "pub", "m6c")
ASK_KIND = {"plain": "plain", "contradiction": "contradicted", "update": "updated"}


def topic_of(title: str) -> str:
    """The topic a session declares (PUB-M6b, L-PUB-62).  `declare_topic` refuses a topic longer than `mem.TOPIC_MAX_CHARS` (24): LS-D02's title is 25 characters, so in the first measurement every one of its 14
    sessions ran WITHOUT a nest (`declare:bad_topic` 14).  A title that is too long is cut before its first 「――」 / 「—」 / 「：」 / 「:」 (a sub-title), else at 24 characters; a short title is declared as it is."""
    if len(title) <= mem.TOPIC_MAX_CHARS:
        return title
    for sep in ("――", "—", "：", ":"):
        if sep in title and 0 < title.index(sep) <= mem.TOPIC_MAX_CHARS:
            return title[:title.index(sep)]
    return title[:mem.TOPIC_MAX_CHARS]


def run_story(args: Any) -> Dict[str, Any]:
    story, verify = args
    m2 = K.load_m2()
    plants = [{"kind": p["kind"], "turns": {C.mem_run.turn_id(s, i) for s, i in p["message_refs"]}} for p in story["plants"]]
    by_cp: Dict[int, List[dict]] = {}
    cp_session = {c["index"]: c["after_session"] for c in story["checkpoints"]}
    for q in story["questions"]:
        by_cp.setdefault(cp_session[q["checkpoint"]], []).append(q)
    tmp = tempfile.mkdtemp(prefix="m5m6_ls_")
    try:
        store = os.path.join(tmp, "store")
        st = mem.MemStore(store, "m")
        tally = m2.Tally()
        qrows: List[dict] = []
        last_ix = None
        t0 = time.time()
        stamps: List[float] = []
        for si, msgs in enumerate(story["sessions"]):
            s = st.begin("measure", profile=mem.PROFILE_V4, versions=mem.V4_VERSIONS_M6C if MODE["m6c"] else None)
            r = s.call("declare_topic", {"text": topic_of(story["title"])})
            if r.get("ok"):
                tally.topics += 1
            else:
                tally.other_refused["declare:" + r["refusal"]] += 1
            for mi, m in enumerate(msgs):
                for c in m2.chunks(m["text"]):
                    res = s.call("write", {"text": c, "turn": C.mem_run.turn_id(si, mi)})
                    tally.writes += 1
                    if tally.writes % 100 == 0:
                        stamps.append(round(time.time() - t0, 1))
                    if res.get("ok"):
                        tally.accepted += 1
                        for cl in res["shape"]["clauses"]:
                            tally.clause_shapes[cl["shape"]] += 1
                            tally.completed += cl.get("via") == "nest"
                            tally.change_clauses += cl.get("change") is not None
                        if res["weave"] != "ok":
                            tally.weave_refused += 1
                            tally.weave_refused_reasons[res["weave_refused"]] += 1
                    elif res["refusal"] == "no_shape":
                        tally.f0 += 1
                        for cl in res["detail"]["clauses"]:
                            tally.f0_reasons[cl["reason"]] += 1
                        if not res["detail"]["clauses"]:
                            tally.f0_reasons["no_clause"] += 1
                    else:
                        tally.other_refused[res["refusal"]] += 1
            ix = s.run.builder.index()
            last_ix = ix
            for q in by_cp.get(si, []):
                kind = ASK_KIND.get(q["kind"], "absent")
                m6c = MODE["m6c"]
                res = mask.recall(ix, s.run.rows, s.run.corpus_cur, q["q"], ask=mask.ASK_V3) if m6c else mask.recall(ix, s.run.rows, s.run.corpus_cur, q["q"])
                row = {"checkpoint": q["checkpoint"], "kind": q["kind"], "form": q["form"], "q": q["q"], "gold": q["gold"], "verdict": res["verdict"], "route": res.get("route"),
                       "issues": res.get("issues", []), "parsed": res["question"]["ok"]}
                res2 = None
                if m6c and res["verdict"] == "CANDIDATES":             # the oracle confirms the top candidate (an upper bound); the bridge is applied to a copy of the bridges
                    top = res["candidates"][0]
                    br = mx.Bridge(top["bridge"]["question_word"], top["bridge"]["memory_phrase"], 0, len(s.run.rows))
                    res2 = mask.recall(ix, s.run.rows, s.run.corpus_cur, q["q"], ask=mask.ASK_V3, bridges=tuple(ix.bridges) + (br,))
                    row["offered"] = len(res["candidates"])
                    row["tied_top"] = bool(top.get("tied_with_best"))
                    row["oracle_verdict"] = res2["verdict"]
                    row["oracle_route"] = res2.get("route")
                if kind == "absent":
                    row["admitted"] = res["verdict"] not in ("NONE", "CANDIDATES")
                    if m6c:
                        row["candidates_offered"] = res["verdict"] == "CANDIDATES"
                        row["oracle_admitted"] = res2 is not None and res2["verdict"] not in ("NONE", "CANDIDATES")
                else:
                    gk, gv = C.mem_run.gold_values(q["gold"])
                    for mode, lenient in (("strict", False), ("lenient", True)):
                        row[mode] = K.judge_recall(res, kind, gv, lenient)
                    if m6c and res["verdict"] == "CANDIDATES":
                        rank = next((c["rank"] for c in res["candidates"] if any(C.match(g, v, True) for g in gv for v in c["values"])), None)
                        row["gold_among"], row["gold_rank"] = rank is not None, rank
                        row["oracle"] = {"strict": K.judge_recall(res2, kind, gv, False), "lenient": K.judge_recall(res2, kind, gv, True)} if res2 is not None and res2["answers"] else None
                qrows.append(row)
            s.commit()
        elapsed = round(time.time() - t0, 1)
        vstat = rstat = None
        if verify:
            v = mem.verify_store(store, mem.FROM_HEADER)
            vstat, rstat = v["status"], (v["replay"]["status"] if "replay" in v else None)
        # -- detection against the plants ------------------------------------------------------------------------------------------------------------
        rows = st.rows()
        by_type: Dict[str, collections.Counter] = {t: collections.Counter() for t in M.EXPECT}
        covered: Dict[str, List[int]] = {t: [] for t in M.EXPECT}
        extra = collections.Counter()
        for n in last_ix.notes:
            t = n["type"]
            c = M.classify(plants, n, n.get("turn"), M.cited_turns(n, rows))
            by_type[t][c["class"]] += 1
            by_type[t]["total"] += 1
            for k in c["plants"]:
                if k not in covered[t]:
                    covered[t].append(k)
            if t == "UPDATE":
                extra["update_first" if n["first"] else "update_with_prior"] += 1
            if t == "ENUMERATION":
                extra["enumeration_" + n["reason"]] += 1
            if t == "REVERSAL_X":
                extra["reversal_x_key_" + ("agrees" if n["key"] and n["key"]["agrees"] else "disagrees")] += 1
        planted = collections.Counter(p["kind"] for p in plants)
        cov = {}
        for t, want in M.EXPECT.items():
            idxs = [k for k, p in enumerate(plants) if p["kind"] == want]
            cov[t] = {"plants": len(idxs), "found": len([k for k in covered[t] if k in idxs])}
        # the plants a note of ANOTHER type touched: false alarms of the counted notes on traps and repeats
        return {"id": story["id"], "sessions": len(story["sessions"]), "messages": sum(len(x) for x in story["sessions"]), "sentences_in_memory": len(rows), "writes": tally.to_obj(), "elapsed_s": elapsed,
                "seconds_at_every_100_writes": stamps, "verify": [vstat, rstat], "index_sha": last_ix.index_sha, "index": last_ix.stats(), "notes": {t: dict(c) for t, c in by_type.items()},
                "plant_coverage": cov, "planted": dict(planted), "extra": dict(extra), "questions": qrows, "bridges": 0}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def tally_questions(stories: Sequence[dict]) -> dict:
    out: Dict[str, Any] = {}
    for st in stories:
        for q in st["questions"]:
            k = q["kind"]
            c = out.setdefault(k, collections.Counter())
            c["n"] += 1
            c["parsed"] += 1 if q["parsed"] else 0
            c["verdict_" + q["verdict"]] += 1
            c["route_" + str(q["route"])] += 1
            if k == "absent":
                c["admitted"] += 1 if q["admitted"] else 0
                c["candidates_offered"] += 1 if q.get("candidates_offered") else 0
                c["oracle_admitted"] += 1 if q.get("oracle_admitted") else 0
            else:
                if q.get("offered"):
                    c["candidates_offered"] += 1
                    c["candidates_tied_top"] += 1 if q.get("tied_top") else 0
                    c["candidates_gold_among"] += 1 if q.get("gold_among") else 0
                    c["candidates_gold_rank1"] += 1 if q.get("gold_rank") == 1 else 0
                    o = q.get("oracle")
                    if o is not None:                                 # the ORACLE (top candidate only): an upper bound
                        c["oracle_top_answered"] += 1
                        c["oracle_top_reached"] += 1 if o["lenient"]["reached"] else 0
                        c["oracle_top_exact"] += 1 if o["lenient"]["exact"] else 0
                        c["oracle_top_wrong"] += 0 if o["lenient"]["reached"] else 1
                for mode in ("strict", "lenient"):
                    c[mode + "_reached"] += 1 if q[mode]["reached"] else 0
                    c[mode + "_exact"] += 1 if q[mode]["exact"] else 0
                    c[mode + "_extra"] += 1 if q[mode]["extra"] else 0
                f = q["form"]
                c["form_%s_n" % f] += 1
                c["form_%s_reached" % f] += 1 if q["lenient"]["reached"] else 0
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}


def md(res: dict) -> str:
    out = ["# PUB-M5/M6 — bank_ls dev（2 本、モデルなし、offline）", "", "各メッセージを 1 書き込み（64 字超は「。」で切る）、セッションごとに mem.v4 の store、題名を主題に宣言。F0 の拒否は数えるだけ（keep_unshaped なし）。", ""]
    out += ["| 物語 | セッション | メッセージ | 書き込み | 受理 | F0 | 他の拒否 | 織りの拒否（受理のうち） | 記憶の文 | 秒 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for s in res["stories"]:
        w = s["writes"]
        out.append("| %s | %d | %d | %d | %d (%s %%) | %d (%s %%) | %s | %d (%s %%) | %d | %s |" % (s["id"], s["sessions"], s["messages"], w["writes"], w["accepted"], w["accepted_pct"], w["f0"], w["f0_pct"], w["other_refused"],
                                                                                           w["weave_refused_but_accepted"], w["weave_refused_pct_of_accepted"], s["sentences_in_memory"], s["elapsed_s"]))
    out += ["", "F0 の理由（節）: %s" % res["f0_reasons"], "", "## 検知（十字の注記）と仕掛け", "", "| 注記 | 発火 | hit | 他の仕掛け | 仕掛けなし | 対なし | 見つかった仕掛け |", "|---|---|---|---|---|---|---|"]
    for ty in ("SAME_SEAT", "REVERSAL_X", "UPDATE", "ENUMERATION"):
        c = res["notes"].get(ty, {})
        cv = res["plant_coverage"][ty]
        other = {k[6:]: v for k, v in c.items() if k.startswith("other:")}
        out.append("| %s | %d | %d | %s | %d | %d | %d / %d |" % (ty, c.get("total", 0), c.get("hit", 0), other, c.get("no_plant", 0), c.get("no_pair", 0), cv["found"], cv["plants"]))
    out += ["", "仕掛けの数: %s。内訳: %s" % (res["planted"], res["extra"]), "", "## 想起（チェックポイントの問い）", ""]
    if MODE["m6c"]:
        out += ["PUB-M6c（shape.v3 / ask.v3 / qwords.v2）。`candidates_*` = CANDIDATES を示した問い、`oracle_top_*` = **ORACLE の上限（先頭の候補だけを確かめる「モデル」。モデルの結果ではない）**、"
                "存在しない問いの `admitted` = 橋なしで答えた数、`oracle_admitted` = 先頭の候補を確かめたら答えが出た数（どちらも 0 でなければならない）。", ""]
    for k, c in res["questions"].items():
        out.append("- %s: %s" % (k, c))
    return "\n".join(out) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--m6c", action="store_true", help="PUB-M6c: shape.v3 / ask.v3 / qwords.v2; outputs to experiments/line3/pub/m6c/")
    ns = ap.parse_args(argv)
    MODE["m6c"] = ns.m6c
    M.MODE["m6c"] = ns.m6c
    if ns.m6c:
        os.makedirs(M6C_DIR, exist_ok=True)
        K.OUT = M6C_DIR
    stories = [json.loads(ln) for ln in open(DEV, encoding="utf-8") if ln.strip()]
    results = K.pmap(run_story, [(s, ns.verify) for s in stories], ns.workers)
    notes: Dict[str, collections.Counter] = {}
    cov: Dict[str, collections.Counter] = {}
    planted, extra, f0r = collections.Counter(), collections.Counter(), collections.Counter()
    for r in results:
        for t, c in r["notes"].items():
            notes.setdefault(t, collections.Counter()).update(c)
        for t, c in r["plant_coverage"].items():
            cov.setdefault(t, collections.Counter()).update(c)
        planted.update(r["planted"])
        extra.update(r["extra"])
        f0r.update(r["writes"]["f0_reasons"])
    res = {"stories": results, "notes": {t: dict(c) for t, c in notes.items()}, "plant_coverage": {t: dict(c) for t, c in cov.items()}, "planted": dict(planted), "extra": dict(extra),
           "f0_reasons": dict(sorted(f0r.items())), "questions": tally_questions(results)}
    K.write_json(os.path.join(K.OUT, "bank_ls_dev.json"), res)
    K.write_text(os.path.join(K.OUT, "bank_ls_dev.md"), md(res))
    print(md(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

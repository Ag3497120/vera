"""T6v: run the fixed questions through the variants of one tier.  The variants of one family share
the crosses they read (a per-question memo of `cycle.read_cross`; read_cross is deterministic, so a
memo hit equals a fresh read), which is what makes V1 / V3 cheap after the first whole read.

  F1  original space (T5 placements, level mid):   base (check vs the stored T5 answer), V1, V3
  F2  V2 space (function/question words not units; placements from precompute_v2.py): V2, V123

usage: run_family.py FAMILY TIER WORKERS SHARD(i/n) [VARIANTS comma-separated]
Writes results/S300_<TIER>_<VARIANT>.shard<i>of<n>.jsonl (one line per question).
Grading is done by summarize.py with experiments/line3/grade.py exactly as T6 did.
"""
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C                                              # noqa: E402
from verantyx.line3 import cycle as cy                           # noqa: E402
from verantyx.line3 import readout as ro                         # noqa: E402
from verantyx.line3 import trace_check as tc                     # noqa: E402

COND = "S300"
fam, tn = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3])
si, sn = (int(x) for x in sys.argv[4].split("/"))
variants = sys.argv[5].split(",") if len(sys.argv) > 5 else {"F1": ["base", "V1", "V3"], "F2": ["V2", "V123"]}[fam]
BUDGET = cy.QueryBudget(64, 8)
FLAGS = {"base": {}, "V1": {"read_rule": "query_crosses"}, "V3": {"state_rule": "query_share"},
         "V2": {"unit_filter": True}, "V123": {"read_rule": "query_crosses", "state_rule": "query_share", "unit_filter": True}}
G = {}
SAMPLE_CAP = 30


def _init():
    v2 = fam == "F2"
    smoke = os.environ.get("T6V_SMOKE")
    if smoke:                                         # smoke test only: first N sentences, placements built on the fly
        from verantyx.line3 import placement as pl
        from verantyx.line3.space import build_space
        sp = build_space(C.data_rows(COND)[:int(smoke)], C.unit_filter() if v2 else None)
        t = sp.tiers[tn]
        P = pl.Placer(t, pl.budget_level("low"))
        G["t"], G["facts"], G["pl"] = t, cy.TierFacts(t), P
        G["filt"], G["sp"], G["memo"], G["T5"], G["by_title"] = C.unit_filter()[tn], sp, {}, {}, {}
        _patch()
        return
    sp = C.space_for(COND, v2)
    t = sp.tiers[tn]
    pk = (os.path.join(C.SCRATCH, "placements_V2_%s_%s_mid.pkl" % (COND, tn)) if v2 else
          os.path.join(C.ROOT, "../../scratch_unused"))
    if not v2:
        pk = os.path.join(os.path.dirname(C.SCRATCH), "t5", "placements_%s_%s_mid.pkl" % (COND, tn))
    d = pickle.load(open(pk, "rb"))
    G["t"], G["facts"], G["pl"] = t, cy.TierFacts(t), cy.PlacementStore(d["placements"])
    G["filt"] = C.unit_filter()[tn]
    G["sp"] = sp
    G["memo"] = {}
    _patch()
    G["T5"] = {}
    if not v2:
        p = os.path.join(C.ROOT, "experiments/line3/t5/results/%s_%s_mid_64x8.jsonl" % (COND, tn))
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                r = json.loads(l)
                G["T5"][r["id"]] = r["answer"]
    G["by_title"] = {}
    for r in C.data_rows(COND):
        G["by_title"].setdefault(r["title"], []).append(r["sent"])


def _patch():
    orig = cy.read_cross

    def memo_read(reader, placement, budget=cy.QueryBudget(), member_cap=None):
        k = (placement.seed, budget.max_states, budget.max_ends, member_cap)
        r = G["memo"].get(k)
        if r is None:
            r = G["memo"][k] = orig(reader, placement, budget, member_cap)
        return r
    cy.read_cross = memo_read


def analyse(res, rd, facts, subj, gold):
    tier = G["t"]
    sent_texts = [s.text for s in rd.sentences]
    path_texts = sorted({p.text for st in rd.states for p in st.paths})
    path_words = sorted({w for st in rd.states for p in st.paths for w in p.words})
    golds = [g.casefold() for g in gold.split("|") if g]
    fp = C.RR.func_pos
    first3 = rd.states[:3]
    n_paths3 = sum(len(st.paths) for st in first3)
    fonly3 = sum(all(fp(w, tn) for w in p.words) for st in first3 for p in st.paths)
    n_paths = sum(len(st.paths) for st in rd.states)
    fonly = sum(all(fp(w, tn) for w in p.words) for st in rd.states for p in st.paths)
    content = sorted({w for st in rd.states for p in st.paths for w in p.words if not fp(w, tn)})
    traces, rep = tc.trace_readout(tier, rd)
    core = ""
    for st in rd.states:
        for p in st.paths:
            if p.attached is not None and facts.n.get(p.attached, 0) > 0:
                core = p.attached
                break
        if core:
            break
    # gold in the cycle's own unit answer(s) as well (reference)
    return {
        "gold_in_sentence": any(g in t.casefold() for g in golds for t in sent_texts),
        "gold_in_a_path": any(g in t.casefold() for g in golds for t in path_texts),
        "gold_in_path_words_union": any(g in "".join(path_words).casefold() for g in golds),
        "gold_in_unit_answer": any(g in "".join(res.units).casefold() for g in golds),
        "paths_first3_total": n_paths3, "paths_first3_function_only": fonly3,
        "paths_all_total": n_paths, "paths_all_function_only": fonly,
        "function_words": sum(fp(w, tn) for st in rd.states for p in st.paths for w in p.words),
        "path_words": sum(len(p.words) for st in rd.states for p in st.paths),
        "content_words": content, "core": core,
        "trace": rep.to_json_obj(), "trace_traced_path_words": len(traces),
        "all_states_function_only": bool([st for st in rd.states if st.paths]) and all(
            all(fp(w, tn) for p in st.paths for w in p.words) for st in rd.states if st.paths),
    }


def _work(row):
    qid, kind, subj, question, gold = row
    G["memo"].clear()
    out = {}
    facts = G["facts"]
    for v in variants:
        fl = dict(FLAGS[v])
        if fl.pop("unit_filter", False):
            fl["unit_filter"] = G["filt"]
        t0 = time.time()
        res = cy.ask_tier(G["t"], question, G["pl"], facts=facts, budget=BUDGET, **fl)
        secs = round((time.time() - t0) * 100) / 100
        rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "variant": v, "secs": secs,
               "cycle": res.answer_obj(), "read": res.thought_obj()["read"],
               "state_choice": (res.variant or {}).get("state_choice"),
               "query_used": list(res.ctx.query), "states_adopted": len(res.candidates),
               "cycle_distinct_units": len(res.units)}
        if v == "base" and qid in G["T5"]:
            t5 = G["T5"][qid]
            rec["matches_stored_T5"] = (t5["verdict"] == res.verdict and t5["units"] == list(res.units)
                                        and t5["trace"] == res.answer_obj()["trace"])
        if res.candidates:
            rd = ro.read_out_result(G["t"], res, facts, by_stability=(FLAGS[v].get("state_rule") != "query_share"))
            rec["readout"] = rd.answer_obj(with_sentences=False)
            rec["sentences_sample"] = [s.text for s in rd.sentences[:SAMPLE_CAP]]
            rec["counts"] = rd.thought_obj()["counts"]
            rec["k_per_state"] = [st.k for st in rd.states]
            rec["paths"] = [[{"section": p.section, "attached": p.attached, "words": list(p.words)}
                             for p in st.paths] for st in rd.states[:3]]
            rec["states_total"] = len(rd.states)
            rec["diag"] = analyse(res, rd, facts, subj, gold)
            rec["strict_verdict"] = rd.verdict
            rec["strict_text"] = rd.sentences[0].text[:160] if rd.verdict == cy.ANSWER else ""
        else:
            rec["readout"] = {"verdict": None}
            rec["strict_verdict"] = None
            rec["strict_text"] = ""
        out[v] = rec
    return out


if __name__ == "__main__":
    rows = C.questions()
    if tn == "WORD":
        rows = rows[::3]                             # the T5 WORD sample: every 3rd question
    elif tn == "CHAR":
        rows = rows[::9]
    rows = [r for i, r in enumerate(rows) if i % sn == si]
    if os.environ.get("T6V_SMOKE"):
        rows = rows[:3]
    od = os.path.join(C.HERE, "results")
    if os.environ.get("T6V_SMOKE"):
        od = os.environ["T6V_SMOKE_OUT"]
    fs = {v: open(os.path.join(od, "%s_%s_%s.shard%dof%d.jsonl" % (COND, tn, v, si, sn)), "w", encoding="utf-8") for v in variants}
    t0 = time.time()
    with mp.Pool(workers, initializer=_init) as pool:
        for out in pool.imap(_work, rows):
            for v, rec in out.items():
                fs[v].write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                fs[v].flush()
            r0 = list(out.values())[0]
            print(r0["id"], {v: (r["secs"], r["cycle"]["verdict"], r["readout"].get("verdict")) for v, r in out.items()}, flush=True)
    print("TOTAL wall", round(time.time() - t0, 1), "s", flush=True)

"""T6: read the words out along the section -> centre paths of the adopted stable states stored by
T5 (experiments/line3/t5/results/*.jsonl, `answer.trace` holds each adopted state and its stability),
form the sentence candidates, trace-check every output word and grade (T0 grader, 7.2 rule).

No T5 re-run is needed: the stored trace has the end state (world-view flat), the seed, the member and
the stability; the query context is rebuilt from the question exactly as T5 did.

usage: run_readout.py [COND=S300] [LEVEL=mid_64x8]
Writes t6/results/<COND>_<TIER>_<LEVEL>.jsonl (one line per question) and t6/results/summary.json.
"""
import json
import os
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
import grade as G                                              # noqa: E402
from verantyx.line3 import cycle as cy                          # noqa: E402
from verantyx.line3 import readout as ro                        # noqa: E402
from verantyx.line3 import trace_check as tc                    # noqa: E402
from verantyx.line3.space import _get_tagger, build_space, load_jsonl   # noqa: E402

COND = sys.argv[1] if len(sys.argv) > 1 else "S300"
LEVEL = sys.argv[2] if len(sys.argv) > 2 else "mid_64x8"
SAMPLE_CAP = 30                      # sentences stored per question in the jsonl (the module output is complete)

FUNC_POS1 = {"助詞", "助動詞", "接続詞", "連体詞", "代名詞", "補助記号", "感動詞", "接頭辞", "副詞"}
FUNC_COMPOUNDS = {"における", "について", "として", "による", "により", "によって", "に対して", "において",
                  "にとって", "とともに", "に関する", "に関して"}
_fc = {}


def func_pos(u, tier):
    """A unit is a function unit iff every token of it is a particle, auxiliary, conjunction,
    adnominal, pronoun/interrogative, adverb, symbol, or a light verb/adjective (UniDic 非自立可能);
    a few fixed compounds are listed.  CHAR: a hiragana character.  (A reading, see OPEN POINTS.)"""
    k = (u, tier)
    if k in _fc:
        return _fc[k]
    if tier == "CHAR":
        r = all("぀" <= c <= "ゟ" for c in u)
    elif u in FUNC_COMPOUNDS:
        r = True
    else:
        toks = list(_get_tagger()(u))
        r = bool(toks) and all(t.feature.pos1 in FUNC_POS1 or t.feature.pos2 == "非自立可能" for t in toks)
    _fc[k] = r
    return r


def hira_only(u):
    return all("぀" <= c <= "ゟ" or c == "ー" for c in u)


def main():
    rows_q = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    Q = {r[0]: r for r in rows_q}
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/%s.jsonl" % COND)))
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    summary = {}
    for tn in ("RUN", "WORD", "CHAR"):
        src = os.path.join(ROOT, "experiments/line3/t5/results/%s_%s_%s.jsonl" % (COND, tn, LEVEL))
        if not os.path.exists(src):
            continue
        tier = sp.tiers[tn]
        facts = cy.TierFacts(tier)
        out_path = os.path.join(HERE, "results", "%s_%s_%s.jsonl" % (COND, tn, LEVEL))
        graded, graded_t5 = [], []
        t0 = time.time()
        with open(out_path, "w", encoding="utf-8") as fo:
            for line in open(src, encoding="utf-8"):
                r = json.loads(line)
                qid, kind, subj, question, gold = Q[r["id"]]
                ans = r["answer"]
                rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "t5_verdict": ans["verdict"],
                       "t5_units": ans["units"], "t5_stability": ans["stability"]}
                states = ro.states_from_answer_obj(ans)
                if states:
                    rd = ro.read_out_stored(facts, question, ans)
                    traces, rep = tc.trace_readout(tier, rd)
                    sent_texts = [s.text for s in rd.sentences]
                    path_texts = sorted({p.text for st in rd.states for p in st.paths})
                    path_words = sorted({w for st in rd.states for p in st.paths for w in p.words})
                    golds = [g.casefold() for g in gold.split("|") if g]
                    in_sent = any(g in t.casefold() for g in golds for t in sent_texts)
                    in_path = any(g in t.casefold() for g in golds for t in path_texts)
                    in_path_union = any(g in "".join(path_words).casefold() for g in golds)
                    state_fn = [all(func_pos(w, tn) for p in st.paths for w in p.words) for st in rd.states if st.paths]
                    state_hira = [all(hira_only(w) for p in st.paths for w in p.words) for st in rd.states if st.paths]
                    fn_words = sum(func_pos(w, tn) for st in rd.states for p in st.paths for w in p.words)
                    all_words = sum(len(p.words) for st in rd.states for p in st.paths)
                    rec.update({
                        "readout": rd.answer_obj(with_sentences=False),
                        "sentences_sample": [s.text for s in rd.sentences[:SAMPLE_CAP]],
                        "counts": rd.thought_obj()["counts"],
                        "k_per_state": [st.k for st in rd.states],
                        "paths": [[{"section": p.section, "attached": p.attached, "words": list(p.words)}
                                   for p in st.paths] for st in rd.states[:3]],
                        "states_total": len(rd.states),
                        "trace": rep.to_json_obj(), "trace_traced_path_words": len(traces),
                        "diag": {"gold_in_sentence": in_sent, "gold_in_a_path": in_path,
                                 "gold_in_path_words_union": in_path_union,
                                 "all_states_function_only": bool(state_fn) and all(state_fn),
                                 "any_state_function_only": any(state_fn),
                                 "all_states_hiragana_only": bool(state_hira) and all(state_hira),
                                 "function_words": fn_words, "path_words": all_words,
                                 "content_words": sorted({w for st in rd.states for p in st.paths for w in p.words
                                                          if not func_pos(w, tn)})},
                    })
                    verdict = rd.verdict
                    text = rd.sentences[0].text if verdict == cy.ANSWER else ""
                    core = ""
                    for st in rd.states:
                        for p in st.paths:
                            if p.attached is not None and facts.n.get(p.attached, 0) > 0:
                                core = p.attached
                                break
                        if core:
                            break
                else:
                    verdict, text, core = None, "", ""
                    rec["readout"] = {"verdict": None}
                rec["strict_verdict"] = verdict
                cls = G.classify(verdict)
                g, hit, sok = G.grade(cls, core, text, subj, gold)
                rec["strict"] = {"cls": cls, "grade": g, "gold_hit": hit, "subj_ok": sok, "core": core,
                                 "text": text[:160]}
                row = dict(qid=qid, kind=kind, cls=cls, grade=g, gold_hit=hit, gold_held=False)
                graded.append(row)
                # reference: T5's own unit answer graded with the same core
                v5 = ans["verdict"]
                t5text = "".join(ans["units"]) if v5 == "ANSWER" else ""
                c5 = G.classify(v5)
                g5, hit5, sok5 = G.grade(c5, core, t5text, subj, gold)
                graded_t5.append(dict(qid=qid, kind=kind, cls=c5, grade=g5, gold_hit=hit5, gold_held=False))
                fo.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        summary[tn] = {"n": len(graded), "secs": round(time.time() - t0, 1),
                       "strict": G.tally(graded), "t5_unit_answer": G.tally(graded_t5)}
        print(tn, summary[tn], flush=True)
    json.dump(summary, open(os.path.join(HERE, "results", "%s_summary_raw.json" % COND), "w"), ensure_ascii=False,
              sort_keys=True, indent=1)


if __name__ == "__main__":
    main()

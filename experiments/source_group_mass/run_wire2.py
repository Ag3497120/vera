"""PREREG_WIRE2: store.has を包んで配線と同一効果を作り、未見 seed 4242 で判定する。"""
import json, random, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"experiments"/"retrieval_reach"))
import run_reach as R
from verantyx.consensus_store import _MassView
from verantyx.consensus import run_consensus
from verantyx.placement import demand_from_queries, facet_document_frequency, score_facets
from verantyx.face_roles import FACET_FACES
from verantyx.cross import AXES, ShellCross
from verantyx.lex_filters import is_junk_core

def measure(store, seed, gated):
    raw_has = store.has
    if gated:
        store.has = lambda c, _h=raw_has: (not is_junk_core(c)) and _h(c)
    try:
        masses=_MassView(store); df=facet_document_frequency(store)
        rich=sorted(c for c,f in store.crosses.items() if len(f)>=8)
        picks=random.Random(seed).sample(rich,min(R.N_PROBES,len(rich)))
        train=[" ".join(t) for r in range(3) for c in picks for t in [R.mid_facets(store,c,seed=seed+58+r)] if t]
        asked=demand_from_queries(store,train)
        def picks_for(cs): return {c:[f for _s,f in score_facets(store,c,df=df,n_cores=store.n_cores(),asked=asked,weight=0.0)[:len(FACET_FACES)]] for c in cs}
        def shell(cs,pk):
            sh=ShellCross()
            for axis,core in zip(AXES,cs):
                sh.faces[axis]["tip"]=core; sh.reflections[axis]=core
                for face,facet in zip(FACET_FACES,pk[core]): sh.faces[axis][face]=facet
            return sh
        res={"reachable":0,"correct":0,"wrong":0,"refusal":0,"asked":0,"junk_top1":0}
        for want in picks:
            terms=R.mid_facets(store,want,seed=seed+957)
            if not terms: continue
            q=" ".join(terms); cores=R.candidates_appended(store,q,k=R.K)
            if not cores: continue
            res["asked"]+=1
            if is_junk_core(cores[0]): res["junk_top1"]+=1
            if want in cores: res["reachable"]+=1
            r1=run_consensus(shell(cores,picks_for(cores)),q,masses=masses)
            if r1.verdict!="ANSWER": res["refusal"]+=1
            elif r1.core==want: res["correct"]+=1
            else: res["wrong"]+=1
        return res
    finally:
        store.has = raw_has

t0=time.time(); v=R.load_published(R.DB); store=v.stores["ja"]
out={}
for seed in (4242, 42):
    out[seed]={arm: measure(store, seed, arm=="gated") for arm in ("baseline","gated")}
out["elapsed_s"]=round(time.time()-t0,1)
print(json.dumps(out,ensure_ascii=False,indent=1))
b,g=out[4242]["baseline"],out[4242]["gated"]
print("\n────── 判定 (seed 4242、未見) ──────")
print(f"WRONG_DOWN        : {'PASS' if g['wrong']<b['wrong'] else 'FAIL'} ({g['wrong']} < {b['wrong']})")
print(f"CORRECT_NOT_WORSE : {'PASS' if g['correct']>=b['correct'] else 'FAIL'} ({g['correct']} vs {b['correct']})")
print(f"JUNK_TOP1_ZERO    : {'PASS' if g['junk_top1']==0 else 'FAIL'} ({g['junk_top1']}; baseline {b['junk_top1']})")
b2,g2=out[42]["baseline"],out[42]["gated"]
print(f"\n参考 seed 42(既見): baseline 正{b2['correct']}/誤{b2['wrong']}/棄{b2['refusal']}  gated 正{g2['correct']}/誤{g2['wrong']}/棄{g2['refusal']}")
Path(__file__).with_name("results_wire2.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")

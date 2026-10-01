"""PREREG_WIRE3: junk を除いた store 複製で3経路を同時に塞ぎ、未見 seed 777 で判定。"""
import copy, json, random, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"experiments"/"retrieval_reach"))
import run_reach as R
from verantyx.consensus_store import _MassView
from verantyx.consensus import run_consensus
from verantyx.placement import demand_from_queries, facet_document_frequency, score_facets
from verantyx.face_roles import FACET_FACES
from verantyx.cross import AXES, ShellCross
from verantyx.lex_filters import is_junk_core

def gated_store(store):
    g = copy.copy(store)
    g.crosses = {c: f for c, f in store.crosses.items() if not is_junk_core(c)}
    g.core_count = {c: n for c, n in store.core_count.items() if not is_junk_core(c)}
    return g

def measure(store, seed, gold_pop):
    masses=_MassView(store); df=facet_document_frequency(store)
    train=[" ".join(t) for r in range(3) for c in gold_pop for t in [R.mid_facets(store,c,seed=seed+58+r)] if t]
    asked=demand_from_queries(store,train)
    def picks_for(cs): return {c:[f for _s,f in score_facets(store,c,df=df,n_cores=store.n_cores(),asked=asked,weight=0.0)[:len(FACET_FACES)]] for c in cs}
    def shell(cs,pk):
        sh=ShellCross()
        for axis,core in zip(AXES,cs):
            sh.faces[axis]["tip"]=core; sh.reflections[axis]=core
            for face,facet in zip(FACET_FACES,pk[core]): sh.faces[axis][face]=facet
        return sh
    res={"reachable":0,"correct":0,"wrong":0,"refusal":0,"asked":0,"junk_top1":0}
    for want in gold_pop:
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

t0=time.time(); v=R.load_published(R.DB); base=v.stores["ja"]; gate=gated_store(base)
print(f"store: 核 {len(base.crosses)} → gated {len(gate.crosses)} (junk {len(base.crosses)-len(gate.crosses)} 除去)")
out={}
for seed in (777, 4242, 42):
    rich=sorted(c for c,f in base.crosses.items() if len(f)>=8)
    pop=random.Random(seed).sample(rich,min(R.N_PROBES,len(rich)))   # gold は両腕で同一(baseline の店から引く)
    out[seed]={"baseline":measure(base,seed,pop), "gated":measure(gate,seed,pop),
               "gold_is_junk": sum(1 for c in pop if is_junk_core(c))}
out["elapsed_s"]=round(time.time()-t0,1)
print(json.dumps(out,ensure_ascii=False,indent=1))
b,g=out[777]["baseline"],out[777]["gated"]
print("\n────── 判定 (seed 777、未見) ──────")
print(f"WRONG_DOWN        : {'PASS' if g['wrong']<b['wrong'] else 'FAIL'} ({g['wrong']} < {b['wrong']})")
print(f"CORRECT_NOT_WORSE : {'PASS' if g['correct']>=b['correct'] else 'FAIL'} ({g['correct']} vs {b['correct']})")
print(f"JUNK_TOP1_ZERO    : {'PASS' if g['junk_top1']==0 else 'FAIL'} ({g['junk_top1']}; baseline {b['junk_top1']})")
print(f"REACH_NOT_WORSE   : {'PASS' if g['reachable']>=b['reachable']-10 else 'FAIL'} ({g['reachable']} vs {b['reachable']}-10; gold が junk {out[777]['gold_is_junk']}件)")
for s in (4242,42):
    x,y=out[s]["baseline"],out[s]["gated"]
    print(f"参考 seed {s}: baseline 正{x['correct']}/誤{x['wrong']}/棄{x['refusal']}/junk_top1 {x['junk_top1']}  gated 正{y['correct']}/誤{y['wrong']}/棄{y['refusal']}/junk_top1 {y['junk_top1']}")
Path(__file__).with_name("results_wire3.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")

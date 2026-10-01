"""A2 の全件: 門が落とした gold 6件、UNKNOWN→WRONG 20件、WRONG→CORRECT 16件を要約せず出す。"""
import random, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"experiments"/"retrieval_reach"))
import run_reach as R
from verantyx.consensus_store import _MassView
from verantyx.consensus import run_consensus
from verantyx.placement import demand_from_queries, facet_document_frequency, score_facets
from verantyx.face_roles import FACET_FACES
from verantyx.cross import AXES, ShellCross
from verantyx.lex_filters import is_junk_core
v=R.load_published(R.DB); store=v.stores["ja"]; masses=_MassView(store)
df=facet_document_frequency(store); rich=sorted(c for c,f in store.crosses.items() if len(f)>=8)
picks_pop=random.Random(42).sample(rich,min(R.N_PROBES,len(rich)))
train=[" ".join(t) for r in range(3) for c in picks_pop for t in [R.mid_facets(store,c,seed=100+r)] if t]; asked=demand_from_queries(store,train)
def picks_for(cores): return {c:[f for _s,f in score_facets(store,c,df=df,n_cores=store.n_cores(),asked=asked,weight=0.0)[:len(FACET_FACES)]] for c in cores}
def shell(cores,picks):
    sh=ShellCross()
    for axis,core in zip(AXES,cores):
        sh.faces[axis]["tip"]=core; sh.reflections[axis]=core
        for face,facet in zip(FACET_FACES,picks[core]): sh.faces[axis][face]=facet
    return sh
gold_junk=[c for c in picks_pop if is_junk_core(c)]
print(f"探針 gold のうち is_junk_core が True: {len(gold_junk)} → {gold_junk}\n")
rows=[]
for want in picks_pop:
    terms=R.mid_facets(store,want,seed=999)
    if not terms: continue
    q=" ".join(terms); cores=R.candidates_appended(store,q,k=R.K); gated=[c for c in cores if not is_junk_core(c)]
    def run(cs):
        if not cs: return ("NO_CANDS",None)
        r=run_consensus(shell(cs,picks_for(cs)),q,masses=masses); return (("CORRECT" if r.core==want else "WRONG") if r.verdict=="ANSWER" else r.verdict, r.core)
    (a,ac),(b,bc)=run(cores),run(gated)
    rows.append((want,q,a,ac,b,bc,[c for c in cores if is_junk_core(c)]))
def show(title,cond):
    sel=[r for r in rows if cond(r)]; print(f"── {title}: {len(sel)}件 ──")
    for want,q,a,ac,b,bc,junk in sel: print(f"  gold={want!r:<18} q={q!r}\n      raw={a}({ac})  gate={b}({bc})  落とした junk={junk}")
    print()
show("UNKNOWN_NO_EVIDENCE→WRONG", lambda r:r[2]=="UNKNOWN_NO_EVIDENCE" and r[4]=="WRONG")
show("WRONG→CORRECT", lambda r:r[2]=="WRONG" and r[4]=="CORRECT")
show("gold が junk で門に落ちた探針", lambda r:is_junk_core(r[0]))

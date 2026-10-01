"""A2: 候補列の入口で is_junk_core を掛ける。腕 raw / raw+門 / group+門。run_reach と同一経路。"""
import json, random, sqlite3, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"experiments"/"retrieval_reach"))
import run_reach as R
from verantyx.consensus_store import _MassView
from verantyx.consensus import run_consensus
from verantyx.placement import demand_from_queries, facet_document_frequency, score_facets
from verantyx.face_roles import FACET_FACES
from verantyx.cross import AXES, ShellCross
from verantyx.lex_filters import is_junk_core
def main():
    t0=time.time(); v=R.load_published(R.DB); store=v.stores["ja"]; raw_mass=store.mass
    con=sqlite3.connect(str(R.DB)); group={c:g for c,g in con.execute("select core,count(distinct leaf) from cores where leaf in (select id from leaves where lang='ja') group by core")}
    gmass=lambda c,_g=group: float(_g.get(str(c).casefold().strip(),0))
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
    arms={"raw":(raw_mass,False),"raw+gate":(raw_mass,True),"group+gate":(gmass,True)}
    res={a:{"reachable":0,"correct":0,"wrong":0,"refusal":0,"asked":0,"junk_top1":0,"junk_in_cands":0,"verdicts":{}} for a in arms}
    for want in picks_pop:
        terms=R.mid_facets(store,want,seed=999)
        if not terms: continue
        q=" ".join(terms)
        for arm,(mfn,gate) in arms.items():
            store.mass=mfn; masses=_MassView(store)
            cores=R.candidates_appended(store,q,k=R.K)
            if any(is_junk_core(c) for c in cores): res[arm]["junk_in_cands"]+=1
            if gate: cores=[c for c in cores if not is_junk_core(c)]
            if not cores: continue
            res[arm]["asked"]+=1
            if is_junk_core(cores[0]): res[arm]["junk_top1"]+=1
            if want in cores: res[arm]["reachable"]+=1
            r1=run_consensus(shell(cores,picks_for(cores)),q,masses=masses)
            if r1.verdict!="ANSWER": res[arm]["refusal"]+=1; res[arm]["verdicts"][want]=r1.verdict
            elif r1.core==want: res[arm]["correct"]+=1; res[arm]["verdicts"][want]="CORRECT"
            else: res[arm]["wrong"]+=1; res[arm]["verdicts"][want]="WRONG"
    store.mass=raw_mass
    def trans(a,b):
        t={}
        for w in res[a]["verdicts"]:
            x,y=res[a]["verdicts"][w],res[b]["verdicts"].get(w,"?")
            if x!=y: t[f"{x}→{y}"]=t.get(f"{x}→{y}",0)+1
        return t
    out={"arms":{a:{k:v for k,v in d.items() if k!="verdicts"} for a,d in res.items()},
         "transitions":{"raw→raw+gate":trans("raw","raw+gate"),"raw+gate→group+gate":trans("raw+gate","group+gate")},"elapsed_s":round(time.time()-t0,1)}
    print(json.dumps(out,ensure_ascii=False,indent=1))
    r,g=res["raw"],res["raw+gate"]
    print(f"\nJUNK_TOP1_ZERO : {'PASS' if g['junk_top1']==0 else 'FAIL'} (raw+gate junk top1 {g['junk_top1']}; raw では {r['junk_top1']})")
    print(f"NOT_WORSE      : {'PASS' if g['correct']>=r['correct'] else 'FAIL'} ({g['correct']} vs {r['correct']})")
    print(f"NO_NEW_WRONG   : {'PASS' if g['wrong']<=r['wrong'] else 'FAIL'} ({g['wrong']} vs {r['wrong']})")
    Path(__file__).with_name("results_a2_junk_gate.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
if __name__=="__main__": main()

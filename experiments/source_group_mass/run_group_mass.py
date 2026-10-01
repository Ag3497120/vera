"""raw mass(出現行数) vs group mass(distinct leaf) — run_reach.py と同一経路で。"""
import json, random, sqlite3, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"experiments"/"retrieval_reach"))
import run_reach as R
from verantyx.consensus_store import _MassView
from verantyx.consensus import run_consensus
from verantyx.placement import demand_from_queries, facet_document_frequency, score_facets
from verantyx.face_roles import FACET_FACES
from verantyx.cross import AXES, ShellCross

def main():
    t0 = time.time(); v = R.load_published(R.DB); store = v.stores["ja"]
    con = sqlite3.connect(str(R.DB))
    group = {c: g for c, g in con.execute("select core, count(distinct leaf) from cores where leaf in (select id from leaves where lang='ja') group by core")}
    raw_mass = store.mass
    df = facet_document_frequency(store)
    rich = sorted(c for c, f in store.crosses.items() if len(f) >= 8)
    picks_pop = random.Random(42).sample(rich, min(R.N_PROBES, len(rich)))
    train = [" ".join(t) for r in range(3) for c in picks_pop for t in [R.mid_facets(store, c, seed=100 + r)] if t]
    asked = demand_from_queries(store, train)
    def picks_for(cores):
        return {c: [f for _s, f in score_facets(store, c, df=df, n_cores=store.n_cores(), asked=asked, weight=0.0)[:len(FACET_FACES)]] for c in cores}
    def build_shell(cores, picks):
        sh = ShellCross()
        for axis, core in zip(AXES, cores):
            sh.faces[axis]["tip"] = core; sh.reflections[axis] = core
            for face, facet in zip(FACET_FACES, picks[core]): sh.faces[axis][face] = facet
        return sh
    arms = {"raw": raw_mass, "group": (lambda c, _g=group: float(_g.get(str(c).casefold().strip(), 0)))}
    res = {a: {"reachable":0,"correct":0,"wrong":0,"refusal":0,"asked":0} for a in arms}
    top1 = {a: {} for a in arms}; moved = []
    for want in picks_pop:
        terms = R.mid_facets(store, want, seed=999)
        if not terms: continue
        q = " ".join(terms)
        for arm, mfn in arms.items():
            store.mass = mfn; masses = _MassView(store)
            cores = R.candidates_appended(store, q, k=R.K)
            if not cores: continue
            res[arm]["asked"] += 1; top1[arm][want] = cores[0]
            if want in cores: res[arm]["reachable"] += 1
            r1 = run_consensus(build_shell(cores, picks_for(cores)), q, masses=masses)
            if r1.verdict != "ANSWER": res[arm]["refusal"] += 1; res[arm].setdefault("verdicts", {}); res[arm]["verdicts"][want] = r1.verdict
            elif r1.core == want: res[arm]["correct"] += 1; res[arm].setdefault("verdicts", {}); res[arm]["verdicts"][want] = "CORRECT"
            else: res[arm]["wrong"] += 1; res[arm].setdefault("verdicts", {}); res[arm]["verdicts"][want] = "WRONG:" + str(r1.core)
    store.mass = raw_mass
    common = [w for w in top1["raw"] if w in top1["group"]]
    diff = [w for w in common if top1["raw"][w] != top1["group"][w]]
    vr, vg = res["raw"]["verdicts"], res["group"]["verdicts"]
    trans = {}
    for w in common:
        a, b = vr.get(w, "?").split(":")[0], vg.get(w, "?").split(":")[0]
        if a != b: trans[f"{a}→{b}"] = trans.get(f"{a}→{b}", 0) + 1
    out = {"db": str(R.DB), "arms": {a: {k: v for k, v in d.items() if k != "verdicts"} for a, d in res.items()},
           "top1_differs": len(diff), "asked_common": len(common), "verdict_transitions": trans, "elapsed_s": round(time.time()-t0,1),
           "examples_top1_diff": [(w, top1["raw"][w], top1["group"][w]) for w in diff[:10]]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    pct = 100*len(diff)/max(1,len(common))
    print(f"\nGROUP_CHANGES_TOP1 : {'PASS' if pct>=5 else 'FAIL'} ({len(diff)}/{len(common)} = {pct:.1f}%)")
    print(f"GROUP_NOT_WORSE    : {'PASS' if res['group']['correct']>=res['raw']['correct'] else 'FAIL'} (group {res['group']['correct']} vs raw {res['raw']['correct']})")
    Path(__file__).with_name("results_group_mass.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
if __name__ == "__main__": main()

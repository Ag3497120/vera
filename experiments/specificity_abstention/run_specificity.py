"""Execute the frozen registration; all arms use run_reach's retrieval path."""
import hashlib
import json
import random
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/retrieval_reach"))
import run_reach as R
from adjudicate import adjudicate
from verantyx.consensus import query_content, run_consensus
from verantyx.consensus_store import _MassView
from verantyx.cross import AXES, ShellCross
from verantyx.face_roles import FACET_FACES
from verantyx.lex_filters import is_junk_core
from verantyx.placement import (demand_from_queries, facet_document_frequency,
                                score_facets)

SEED = 31415
ARMS = ("baseline", "specificity", "no_junk", "no_junk_specificity")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def category(result, gold):
    if result.verdict != "ANSWER":
        return "refusal"
    return "correct" if result.core == gold else "wrong"


def make_shell(cores, picks):
    shell = ShellCross()
    for axis, core in zip(AXES, cores):
        shell.faces[axis]["tip"] = core
        shell.reflections[axis] = core
        for face, facet in zip(FACET_FACES, picks[core]):
            shell.faces[axis][face] = facet
    return shell


def main():
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    frozen = (HERE / "PREREG.sha256").read_text().split()[0]
    assert sha256(HERE / "PREREG.md") == frozen, "registration changed"
    # A repeat must not silently replace the original unseen measurement.
    target = HERE / "results.json"
    if target.exists():
        raise SystemExit("results.json already exists; no rerun or overwrite")
    db_before = sha256(R.DB)
    source_paths = [HERE / "adjudicate.py", HERE / "run_specificity.py",
                    ROOT / "experiments/retrieval_reach/run_reach.py"]
    source_paths += sorted((ROOT / "verantyx").rglob("*.py"))
    sources = {str(p.relative_to(ROOT)): sha256(p) for p in source_paths}
    store = R.load_published(R.DB).stores["ja"]
    masses = _MassView(store)
    df = facet_document_frequency(store)
    rich = sorted(c for c, fs in store.crosses.items() if len(fs) >= 8)
    population = random.Random(SEED).sample(rich, min(R.N_PROBES, len(rich)))
    train = [" ".join(terms) for r in range(3) for c in population
             for terms in [R.mid_facets(store, c, seed=SEED + 58 + r)] if terms]
    asked = demand_from_queries(store, train)
    totals = {a: Counter(asked=0, correct=0, wrong=0, refusal=0,
                          reachable=0, junk_top1=0, junk_present=0,
                          empty_candidates=0) for a in ARMS}
    verdicts = {a: Counter() for a in ARMS}
    rows, excluded = [], []
    for index, gold in enumerate(population):
        terms = R.mid_facets(store, gold, seed=SEED + 957)
        if not terms:
            excluded.append({"index": index, "gold": gold,
                             "reason": "mid_facets returned None"})
            continue
        query = " ".join(terms)
        cores = R.candidates_appended(store, query, k=R.K)
        picks = {c: [f for _, f in score_facets(
            store, c, df=df, n_cores=store.n_cores(), asked=asked,
            weight=0.0)[:len(FACET_FACES)]] for c in cores}
        row = {"index": index, "gold": gold, "query": query,
               "query_content": sorted(query_content(query)[0]),
               "gold_is_junk": is_junk_core(gold), "arms": {}}
        for raw_arm, gate_arm, cs in (
            ("baseline", "specificity", cores),
            ("no_junk", "no_junk_specificity",
             [c for c in cores if not is_junk_core(c)]),
        ):
            shell = make_shell(cs, picks)
            raw = run_consensus(shell, query, masses=masses)
            before = raw.as_dict()
            gated, evidence = adjudicate(store, query, raw)
            assert raw.as_dict() == before, "adjudicator mutated raw result"
            if raw.verdict != "ANSWER" or not evidence["refused"]:
                assert gated.as_dict() == before
            else:
                assert gated.verdict == "UNKNOWN_INSUFFICIENT_EVIDENCE"
                assert gated.core is None and gated.text == "" and gated.tokens == []
                assert 20 * evidence["numerator"] < evidence["denominator"]
                delta_keys = {k for k, v in gated.as_dict().items() if before[k] != v}
                assert delta_keys <= {"verdict", "core", "text", "tokens"}
            for arm, result in ((raw_arm, raw), (gate_arm, gated)):
                cat = category(result, gold)
                totals[arm].update(asked=1, reachable=int(gold in cs),
                    junk_top1=int(bool(cs) and is_junk_core(cs[0])),
                    junk_present=int(any(is_junk_core(c) for c in cs)),
                    empty_candidates=int(not cs))
                totals[arm][cat] += 1
                verdicts[arm][result.verdict] += 1
                row["arms"][arm] = {
                    "candidates": list(cs), "placement": shell.faces,
                    "result": result.as_dict(), "category": cat,
                    "evidence": evidence,
                }
            assert row["arms"][raw_arm]["candidates"] == row["arms"][gate_arm]["candidates"]
            assert row["arms"][raw_arm]["placement"] == row["arms"][gate_arm]["placement"]
        rows.append(row)
        if (index + 1) % 50 == 0:
            print(f"completed {index + 1}/{len(population)}", flush=True)
    for a in ARMS:
        assert sum(totals[a][k] for k in ("correct", "wrong", "refusal")) == totals[a]["asked"]
        assert totals[a]["asked"] == len(rows)
    db_after = sha256(R.DB)
    paths_match = db_before == db_after
    pairs = (("baseline", "specificity"), ("baseline", "no_junk"),
             ("no_junk", "no_junk_specificity"),
             ("baseline", "no_junk_specificity"))
    transitions = {}
    for a, b in pairs:
        transitions[a + " -> " + b] = dict(Counter(
            r["arms"][a]["category"] + " -> " + r["arms"][b]["category"] for r in rows))
    baseline = totals["baseline"]
    def criteria(a):
        return {"WRONG_DOWN": totals[a]["wrong"] < baseline["wrong"],
                "REFUSAL_NOT_WORSE": totals[a]["refusal"] >= baseline["refusal"],
                "CORRECT_NOT_WORSE": totals[a]["correct"] >= baseline["correct"]}
    gates = {**criteria("specificity"), "PATH_MATCH": paths_match}
    out = {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
           "elapsed_s": round(time.monotonic() - t0, 3),
           "seed": SEED, "population": population, "excluded": excluded,
           "prereg_sha256": frozen,
           "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
           "db": str(R.DB), "db_sha256_before": db_before, "db_sha256_after": db_after,
           "source_sha256": sources, "n_cores": store.n_cores(),
           "arms": totals, "verdicts": verdicts, "transitions": transitions,
           "primary_criteria": gates, "primary_pass": all(gates.values()),
           "auxiliary_vs_baseline": criteria("no_junk_specificity"),
           "rows": rows}
    with target.open("x", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: out[k] for k in ("arms", "primary_criteria", "auxiliary_vs_baseline", "transitions")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

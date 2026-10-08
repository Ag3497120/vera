"""C5' (round 2): run the pre-registered probes (c5r2_probes.json) through the default entries.

Entries: cli_default = subprocess `python -m verantyx.cli ask <text>` (cwd = work tree);
api_legacy = fresh subprocess `Vera(mode='legacy').ask(text)`; api_legacy_docs = the same after
`load_documents([c5r2_doc.txt])`. States: with_index = VERA_P4_INDEX=<index>; default = VERA_P4_INDEX and
VERA_W1C_INDEX REMOVED from the child's environment (not pointed at a missing directory).
Full results (traces and sources included) are kept in c5r2_entry_probe.json. The judgement is mechanical
(see "judgement" in the registration file). Probes are run on 4 threads; each is an independent subprocess.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
IDX = "/Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c"
REG = HERE / "c5r2_probes.json"
DOC = HERE / "c5r2_doc.txt"
REFUSAL_KINDS = {"unknown", "not_yet", "cannot", "unreadable", "refusal"}
CORPUS_PARTS = ("ability_corpus.search", "ability_corpus.status", "round3.family.conversation", "round3.family.code")

API_WORKER = """
import json, sys
from verantyx.one import Vera
v = Vera(mode='legacy')
if len(sys.argv) > 2:
    v.load_documents([sys.argv[2]])
print(json.dumps(v.ask(sys.argv[1]), ensure_ascii=False, default=str))
"""


def child_env(state: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("VERA_P4_INDEX", "VERA_W1C_INDEX")}
    env.update(PYTHONPATH=str(TREE), PYTHONDONTWRITEBYTECODE="1")
    if state == "with_index":
        env["VERA_P4_INDEX"] = IDX
    return env


def run(entry: str, text: str, state: str) -> dict:
    if entry == "cli_default":
        cmd = [PY, "-m", "verantyx.cli", "ask", text]
    elif entry == "api_legacy":
        cmd = [PY, "-c", API_WORKER, text]
    else:
        cmd = [PY, "-c", API_WORKER, text, str(DOC)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=child_env(state), cwd=str(TREE), timeout=900)
    out = p.stdout
    start = out.find("{")
    try:
        result = json.loads(out[start:]) if start >= 0 else None
    except json.JSONDecodeError:
        result = None
    return dict(returncode=p.returncode, result=result, stderr_tail=p.stderr[-300:] if not result else "",
                stdout_head=None if result else out[:300])


def generated_sources(node, found=None) -> list:
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get("origin") == "generated":
            found.append(dict(family=node.get("family"), source_file=node.get("source_file"), line=node.get("line"),
                              text=str(node.get("text"))[:60]))
        for k, v in node.items():
            if k != "trace":
                generated_sources(v, found)
    elif isinstance(node, list):
        for v in node:
            generated_sources(v, found)
    return found


def facts(res: dict) -> dict:
    r = res["result"]
    if r is None:
        return dict(ran=False, returncode=res["returncode"], stderr_tail=res["stderr_tail"], stdout_head=res["stdout_head"])
    trace = r.get("trace") or []
    steps = [dict(part=t.get("part"), family=t.get("family"), index=t.get("index")) for t in trace
             if t.get("part") in CORPUS_PARTS]
    gen = generated_sources(r)
    kind, verdict = r.get("kind"), str(r.get("verdict") or "")
    answered = kind not in REFUSAL_KINDS and not verdict.startswith(("UNKNOWN", "TIED", "ABSTAIN"))
    return dict(ran=True, kind=kind, verdict=r.get("verdict"), ability=r.get("ability"), door=r.get("door"),
                text=str(r.get("text"))[:160], generated_sources=len(gen), generated_examples=gen[:2],
                basis_origin=r.get("basis_origin"), has_basis_origin_key="basis_origin" in r,
                corpus_trace=steps, answered=answered)


def strip(r):
    return None if r is None else {k: v for k, v in r.items() if k != "trace"}


def main() -> int:
    t_start = time.time()
    reg = json.loads(REG.read_text(encoding="utf-8"))
    st = REG.stat()
    reg_info = dict(path="artifacts/w1-c/c5r2_probes.json", sha256=hashlib.sha256(REG.read_bytes()).hexdigest(),
                    birthtime=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_birthtime)),
                    mtime=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
                    created_before_run_start=st.st_birthtime < t_start and st.st_mtime < t_start,
                    run_started=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t_start)))
    extra = HERE / "c5r2_probes_b.json"
    reg_info["additional_registration_file"] = None if not extra.exists() else dict(
        sha256=hashlib.sha256(extra.read_bytes()).hexdigest(), birthtime=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(extra.stat().st_birthtime)))
    tree_build = (TREE / "build" / "p4")
    env_check = dict(tree_build_p4_exists=tree_build.exists(),
                     default_child_env_has_VERA_P4_INDEX="VERA_P4_INDEX" in child_env("default"),
                     default_child_env_has_VERA_W1C_INDEX="VERA_W1C_INDEX" in child_env("default"),
                     with_index_child_env_VERA_P4_INDEX=child_env("with_index")["VERA_P4_INDEX"])
    assert not env_check["tree_build_p4_exists"]

    groups = reg["groups"]
    jobs = []   # (group, question, entry, state)
    for g in ("commonsense", "generation", "conversation"):
        for q in groups[g]["questions"]:
            for e in groups[g]["entries"]:
                for s in ("with_index", "default"):
                    jobs.append((g, q, e, s))
    if extra.exists():
        more = json.loads(extra.read_text(encoding="utf-8"))
        for g, spec in more.get("groups", {}).items():
            if g == "non_corpus":
                continue
            for q in spec["questions"]:
                for e in spec["entries"]:
                    for s in ("with_index", "default"):
                        jobs.append((g, q, e, s))
    for run_spec in groups["non_corpus"]["runs"]:
        for q in run_spec["questions"]:
            jobs.append(("non_corpus", q, run_spec["entry"], run_spec["state"]))

    def work(job):
        g, q, e, s = job
        res = run(e, q, s)
        return dict(group=g, text=q, entry=e, state=s, returncode=res["returncode"], facts=facts(res), full_result=res["result"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(work, jobs))

    idx = {(r["group"], r["text"], r["entry"], r["state"]): r for r in runs}
    # reached
    reached_rows = []
    for g in ("commonsense", "generation", "conversation"):
        for (gg, q, e, s), r in idx.items():
            if gg != g or s != "with_index":
                continue
            d = idx[(g, q, e, "default")]
            fw = r["facts"]
            flag_generated = fw.get("generated_sources", 0) > 0
            flag_differs = strip(r["full_result"]) != strip(d["full_result"])
            reached_rows.append(dict(group=g, text=q, entry=e, reached=bool(flag_generated or flag_differs),
                                     flag_generated_sources=flag_generated, flag_result_differs_from_default=flag_differs,
                                     answered=fw.get("answered"), generated_sources=fw.get("generated_sources"),
                                     basis_origin=fw.get("basis_origin"), kind=fw.get("kind"), ability=fw.get("ability")))
    reached_by_group = {}
    for g in ("commonsense", "generation", "conversation"):
        reg_q = list(dict.fromkeys(q for (gg, q, *_ ) in idx if gg == g))
        rq = sorted({r["text"] for r in reached_rows if r["group"] == g and r["reached"]}, key=reg_q.index)
        reached_by_group[g] = dict(registered=len(reg_q), reached_questions=rq, reached=len(rq))
    i_ok = (all(v["reached"] >= 3 for v in reached_by_group.values())
            and sum(v["reached"] for v in reached_by_group.values()) >= 10 and reg_info["created_before_run_start"])

    # (ii)
    ii_viol, invariant_viol, answered_no_gen = [], [], []
    for r in runs:
        f = r["facts"]
        if not f.get("ran"):
            continue
        has, gen = f["has_basis_origin_key"], f["generated_sources"] > 0
        if has != gen or (has and f["basis_origin"] != "generated"):
            invariant_viol.append(dict(group=r["group"], text=r["text"], entry=r["entry"], state=r["state"],
                                       has_basis_origin=has, generated_sources=f["generated_sources"], basis_origin=f["basis_origin"]))
    for rr in reached_rows:
        if rr["reached"] and rr["answered"]:
            if rr["generated_sources"] > 0 and rr["basis_origin"] != "generated":
                ii_viol.append(dict(rr))
            if rr["generated_sources"] == 0:
                answered_no_gen.append(dict(group=rr["group"], text=rr["text"], entry=rr["entry"], kind=rr["kind"], ability=rr["ability"],
                                            flag_result_differs_from_default=rr["flag_result_differs_from_default"]))
    ran_all = all(r["facts"].get("ran") for r in runs)
    ii_ok = not ii_viol and not invariant_viol and ran_all

    # (iii)
    iii_rows = []
    for r in runs:
        if r["group"] != "non_corpus":
            continue
        f = r["facts"]
        iii_rows.append(dict(entry=r["entry"], text=r["text"], answered=f.get("answered"), generated_sources=f.get("generated_sources"),
                             has_basis_origin_key=f.get("has_basis_origin_key"), kind=f.get("kind"), ability=f.get("ability"), door=f.get("door"),
                             satisfied=bool(f.get("ran") and f["answered"] and f["generated_sources"] == 0 and not f["has_basis_origin_key"])))
    iii_ok = sum(x["satisfied"] for x in iii_rows) >= 5

    # (iv)
    iv_rows = []
    for rr in reached_rows:
        if not rr["reached"]:
            continue
        d = idx[(rr["group"], rr["text"], rr["entry"], "default")]["facts"]
        no_index = [t for t in d.get("corpus_trace", []) if t.get("index") == "UNKNOWN_NO_INDEX"]
        iv_rows.append(dict(group=rr["group"], text=rr["text"], entry=rr["entry"], default_generated_sources=d.get("generated_sources"),
                            default_has_basis_origin_key=d.get("has_basis_origin_key"), default_no_index_trace_items=len(no_index),
                            satisfied=bool(d.get("ran") and d["generated_sources"] == 0 and not d["has_basis_origin_key"] and no_index)))
    iv_ok = all(x["satisfied"] for x in iv_rows) and bool(iv_rows)

    summary = dict(
        registration=reg_info, environment_check=env_check, runs=len(runs), all_runs_produced_json=ran_all,
        by_group=reached_by_group,
        i_reached_distinct_questions_total=sum(v["reached"] for v in reached_by_group.values()),
        i=i_ok, ii=ii_ok, iii=iii_ok, iv=iv_ok,
        ii_reached_answered_with_generated_but_no_basis_origin=ii_viol,
        invariant_violations_over_all_runs=invariant_viol,
        reached_answered_but_no_generated_source=answered_no_gen,
        iii_rows=iii_rows, iii_satisfied=sum(x["satisfied"] for x in iii_rows),
        iv_checked=len(iv_rows), iv_failed=[x for x in iv_rows if not x["satisfied"]],
        elapsed_seconds=round(time.time() - t_start, 1))
    out = dict(registered="artifacts/w1-c/c5r2_probes.json", summary=summary, reached=reached_rows, iv_rows=iv_rows, runs=runs)
    (HERE / "c5r2_entry_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("registration", "environment_check", "runs", "by_group", "i", "ii", "iii", "iv",
                      "iii_satisfied", "iv_checked", "elapsed_seconds")}, ensure_ascii=False, indent=1))
    print("invariant violations:", len(invariant_viol), "| ii violations:", len(ii_viol), "| iv failed:", len(summary["iv_failed"]),
          "| reached&answered without generated source:", len(answered_no_gen))
    return 0


if __name__ == "__main__":
    sys.exit(main())

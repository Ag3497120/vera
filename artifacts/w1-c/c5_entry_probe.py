"""C5: run the pre-registered probes (c5_probes.json) through the default entries, with and without the index.

cli_default / cli_round5 run `python -m verantyx.cli ask ...` in a subprocess; api_legacy runs the public
API verantyx.one.Vera(mode='legacy').ask in a fresh subprocess. Each run gets VERA_P4_INDEX set to the real
index or to a directory that does not exist (so the typed "no index" state shows in the trace).
Output: c5_entry_probe.json (full results, traces and sources are kept).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
REFUSAL_KINDS = {"unknown", "not_yet", "cannot", "unreadable", "refusal"}

API_WORKER = """
import json, sys
from verantyx.one import Vera
v = Vera(mode='legacy')
print(json.dumps(v.ask(sys.argv[1]), ensure_ascii=False, default=str))
"""


def env_for(index: str) -> dict:
    env = dict(os.environ, PYTHONPATH=str(TREE), PYTHONDONTWRITEBYTECODE="1", VERA_P4_INDEX=index)
    return env


def run(entry: str, text: str, index: str) -> dict:
    if entry == "cli_default":
        cmd = [PY, "-m", "verantyx.cli", "ask", text]
    elif entry == "cli_round5":
        cmd = [PY, "-m", "verantyx.cli", "ask", "--mode", "round5", text]
    else:
        cmd = [PY, "-c", API_WORKER, text]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env_for(index), cwd=str(TREE), timeout=600)
    out = p.stdout
    start = out.find("{")
    try:
        result = json.loads(out[start:]) if start >= 0 else None
    except json.JSONDecodeError:
        result = None
    return dict(returncode=p.returncode, result=result, stderr_tail=p.stderr[-400:], stdout_head=None if result else out[:400])


def generated_sources(node, found=None, path="") -> list:
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get("origin") == "generated":
            found.append(dict(path=path, family=node.get("family"), source_file=node.get("source_file"), line=node.get("line"), text=str(node.get("text"))[:80]))
        for k, v in node.items():
            if k != "trace":
                generated_sources(v, found, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            generated_sources(v, found, f"{path}[{i}]")
    return found


def summarize(res: dict) -> dict:
    r = res["result"]
    if r is None:
        return dict(ran=False)
    trace = r.get("trace") or []
    steps = [dict(part=t.get("part"), status=t.get("status"), family=t.get("family"), index=t.get("index"), verdict=t.get("verdict"))
             for t in trace if str(t.get("part", "")).startswith(("ability_corpus", "round3.family", "round3.route"))]
    gen = generated_sources(r)
    kind, verdict = r.get("kind"), r.get("verdict")
    answered = kind not in REFUSAL_KINDS and not str(verdict or "").startswith("UNKNOWN")
    return dict(ran=True, kind=kind, verdict=verdict, ability=r.get("ability"), door=r.get("door"), text=str(r.get("text"))[:200],
                corpus_trace_steps=steps, corpus_path_in_trace=any(s["part"] in ("ability_corpus.search", "round3.family.conversation", "round3.family.code") for s in steps),
                index_states=sorted({str(s["index"]) for s in steps if s["index"] is not None}),
                generated_origin_sources=len(gen), generated_origin_examples=gen[:3], answered=answered)


def same(a: dict | None, b: dict | None) -> bool:
    if a is None or b is None:
        return False
    strip = lambda r: {k: v for k, v in r.items() if k not in ("trace",)}
    return strip(a) == strip(b)


def main() -> int:
    spec = json.loads((HERE / "c5_probes.json").read_text())
    out = dict(registered="artifacts/w1-c/c5_probes.json", positive=[], counterexample_search=[])
    spec["counterexample_search_added"] = [dict(p, phase="added_after_first_run") for p in spec["added_after_first_run"]["probes"]]
    for p in spec["counterexample_search"]:
        p["phase"] = "registered_before_run"
    out["counterexample_search_added"] = []
    for kind in ("positive", "counterexample_search", "counterexample_search_added"):
        for probe in spec[kind]:
            entries = [probe["entry"]] if kind == "positive" else ["cli_default", "api_legacy"]
            for entry in entries:
                row = dict(id=probe["id"], entry=entry, text=probe["text"], phase=probe.get("phase", "registered_before_run"))
                for label, index in (("with_index", spec["index_with"]), ("without_index", spec["index_without"])):
                    res = run(entry, probe["text"], index)
                    row[label] = dict(returncode=res["returncode"], summary=summarize(res), stderr_tail=res["stderr_tail"] if not res["result"] else "",
                                      full_result=res["result"])
                w = row["with_index"]["summary"]
                if kind == "positive" and probe["id"] != "P3_info":
                    row["verdict"] = dict(
                        corpus_path_in_trace=w.get("corpus_path_in_trace"),
                        with_index_states=w.get("index_states"),
                        without_index_states=row["without_index"]["summary"].get("index_states"),
                        generated_origin_sources_with_index=w.get("generated_origin_sources"),
                        passes=bool(w.get("corpus_path_in_trace") and w.get("generated_origin_sources", 0) > 0
                                    and "INDEX_AVAILABLE" in (w.get("index_states") or [])
                                    and "UNKNOWN_NO_INDEX" in (row["without_index"]["summary"].get("index_states") or [])))
                elif kind.startswith("counterexample_search"):
                    row["verdict"] = dict(answered=w.get("answered"), generated_origin_sources=w.get("generated_origin_sources"),
                                          identical_to_without_index=same(row["with_index"]["full_result"], row["without_index"]["full_result"]),
                                          corpus_path_in_trace=w.get("corpus_path_in_trace"),
                                          counterexample=bool(w.get("answered") and w.get("generated_origin_sources", 0) > 0))
                out[kind].append(row)
    probes = out["counterexample_search"] + out["counterexample_search_added"]
    out["summary"] = dict(
        positive_passed=[r["id"] for r in out["positive"] if r.get("verdict", {}).get("passes")],
        positive_failed=[r["id"] for r in out["positive"] if "verdict" in r and not r["verdict"]["passes"]],
        counterexample_runs=len(probes), counterexamples=[(r["id"], r["entry"]) for r in probes if r["verdict"]["counterexample"]],
        counterexamples_among_registered=[(r["id"], r["entry"]) for r in out["counterexample_search"] if r["verdict"]["counterexample"]],
        counterexamples_among_added=[(r["id"], r["entry"]) for r in out["counterexample_search_added"] if r["verdict"]["counterexample"]],
        identical_with_and_without_index=[(r["id"], r["entry"]) for r in probes if r["verdict"]["identical_to_without_index"]],
        not_answered=[(r["id"], r["entry"]) for r in probes if not r["verdict"]["answered"]],
        answered_without_generated_source=[(r["id"], r["entry"]) for r in probes if r["verdict"]["answered"] and not r["verdict"]["counterexample"]],
        probes_where_corpus_path_ran=[(r["id"], r["entry"]) for r in probes if r["verdict"]["corpus_path_in_trace"]])
    (HERE / "c5_entry_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

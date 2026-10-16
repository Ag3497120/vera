"""Ticket C (L-PUB-140..): the GEOMETRY ABLATION, offline (no model, no API, no network).

Every variant of the memory index -- A3 (all geometry on), A3f (all off), `A3-no<c>` (leave one out) and `A3f-plus<c>` (add one in), c in nests slide key swap ladder arms (memcross.variant_geometry) -- is
run over the SAME input and measured with the SAME code as the earlier offline measurements (experiments/line3/pub/m5m6: detection of the notes against the plants, recall of the checkpoint questions),
the bundle shape.v4 / ask.v3 / qwords.v2 and memanswer.v17 (the answer rules are not touched by any variant):

  dev     the two DEV stories of bank_ls (experiments/line3/bank_ls/dev/stories.jsonl; a path with a `heldout` component is refused, held-out sets are never opened).  Every message text is a write (the
          bank_ls_dev.py driver), one mem.v4 session per story session, the checkpoint questions asked of the live index.  -> ablate_dev.{json,md}
  meter   the 36 structure runs of the memory meter v1 (experiments/line3/mem/meter_v1): the model's own writes are replayed into a mem.v4 store per variant (m2.drive), the 10 questions of the run are asked
          through an answer run (memanswer.v17 `recall`).  -> ablate_meter.{json,md}

A table per variant: detection (per note type: fired, hit, other plant, no plant, no pair; plants found / planted) and recall (per question kind: asked, reached, exact, extra; absent admitted; verdicts),
and the difference of each leave-one-out variant to A3 and of each add-one-in variant to A3f.  Every cell is an integer count (no float).  Outputs are written next to this script.

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/ablate/ablate.py meter [--workers 4] [--limit N] [--variants A3,A3f,...]
  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/ablate/ablate.py dev   [--workers 4] [--variants ...]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
M5 = os.path.join(ROOT, "experiments", "line3", "pub", "m5m6")
for p in (ROOT, M5):
    if p not in sys.path:
        sys.path.insert(0, p)

import common as K                                            # noqa: E402  (m5m6: pmap, judge_recall, memfix helpers)
import meter as M                                             # noqa: E402  (m5m6: classify, cited_turns)
import bank_ls_dev as BLD                                     # noqa: E402  (m5m6: run_story over a bank_ls story)
from common import C, ma, mem                                 # noqa: E402
from verantyx.loom import memcross as mx                      # noqa: E402

DEV = os.path.join(ROOT, "experiments", "line3", "bank_ls", "dev", "stories.jsonl")
BUNDLE = mem.V4_VERSIONS_M6D
NOTE_TYPES = tuple(M.EXPECT)                                  # SAME_SEAT REVERSAL_X UPDATE ENUMERATION
KINDS = ("plain", "contradicted", "updated", "absent")
ASK_KIND = {"plain": "plain", "contradiction": "contradicted", "update": "updated"}


class AblateError(Exception):
    pass


def versions_of(variant: str) -> Dict[str, str]:
    g = mx.variant_geometry(variant)
    if g is None:
        raise AblateError("unknown variant %r (%s)" % (variant, ", ".join(mx.ablation_variants())))
    v = dict(BUNDLE)
    if not g.crosses:
        v["index"] = g.version()
    return v


def parse_variants(spec: Optional[str]) -> List[str]:
    names = list(mx.ablation_variants()) if not spec else [x for x in spec.split(",") if x]
    for n in names:
        versions_of(n)
    return names


def check_dev_path(path: str) -> str:
    if any(part.startswith("heldout") for part in os.path.abspath(path).split(os.sep)):
        raise AblateError("a held-out set is never opened here: %s" % path)
    if os.sep + "dev" + os.sep not in os.path.abspath(path) + os.sep and not os.path.abspath(path).endswith(os.sep + "dev"):
        raise AblateError("only bank_ls/dev is measured: %s" % path)
    return path


# ------------------------------------------------------------------------------------------------------------
# tallies (integers only)
# ------------------------------------------------------------------------------------------------------------
def empty_tally() -> dict:
    return {"runs": 0, "sentences": 0, "notes": {t: collections.Counter() for t in NOTE_TYPES}, "coverage": {t: collections.Counter() for t in NOTE_TYPES},
            "questions": {k: collections.Counter() for k in KINDS}, "extra": collections.Counter()}


def add_questions(tally: dict, kind: str, row: dict) -> None:
    c = tally["questions"][kind]
    c["n"] += 1
    c["verdict_" + str(row["verdict"])] += 1
    if kind == "absent":
        c["admitted"] += 1 if row["admitted"] else 0
    else:
        c["reached"] += 1 if row["lenient"]["reached"] else 0
        c["exact"] += 1 if row["lenient"]["exact"] else 0
        c["extra"] += 1 if row["lenient"]["extra"] else 0


def freeze(tally: dict) -> dict:
    return {"runs": tally["runs"], "sentences": tally["sentences"], "notes": {t: dict(sorted(c.items())) for t, c in tally["notes"].items()},
            "coverage": {t: dict(sorted(c.items())) for t, c in tally["coverage"].items()}, "questions": {k: dict(sorted(c.items())) for k, c in tally["questions"].items()},
            "extra": dict(sorted(tally["extra"].items()))}


def detect(plants: Sequence[dict], notes: Sequence[dict], rows: Sequence[dict]) -> Tuple[dict, dict, dict]:
    by_type = {t: collections.Counter() for t in NOTE_TYPES}
    covered: Dict[str, List[int]] = {t: [] for t in NOTE_TYPES}
    extra = collections.Counter()
    for n in notes:
        t = n["type"]
        if t not in by_type:
            continue
        c = M.classify(plants, n, n.get("turn"), M.cited_turns(n, rows))
        by_type[t][c["class"]] += 1
        by_type[t]["total"] += 1
        for k in c["plants"]:
            if k not in covered[t]:
                covered[t].append(k)
        if t == "REVERSAL_X":
            extra["reversal_x_key_" + ("none" if n["key"] is None else "agrees" if n["key"]["agrees"] else "disagrees")] += 1
    cov = {}
    for t, want in M.EXPECT.items():
        idxs = [k for k, p in enumerate(plants) if p["kind"] == want]
        cov[t] = {"plants": len(idxs), "found": len([k for k in covered[t] if k in idxs])}
    return by_type, cov, extra


def merge(tally: dict, by_type: dict, cov: dict, extra: Any, sentences: int) -> None:
    tally["runs"] += 1
    tally["sentences"] += sentences
    for t in NOTE_TYPES:
        tally["notes"][t].update(by_type[t])
        tally["coverage"][t].update(cov[t])
    tally["extra"].update(extra)


# ------------------------------------------------------------------------------------------------------------
# dev: the bank_ls dev stories
# ------------------------------------------------------------------------------------------------------------
def dev_job(args: Tuple[str, dict]) -> dict:
    """One (variant, story): the bank_ls_dev driver with the variant's versions.  Runs in a worker; sets the module state of the driver (the process is forked per task batch, never shared)."""
    variant, story = args
    v = versions_of(variant)
    BLD.MODE["m6c"] = M.MODE["m6c"] = M.MODE["m6d"] = True
    M.versions = lambda: v                                    # the driver reads its bundle through meter.versions()
    r = BLD.run_story((story, False))
    plants_n = r["planted"]
    out = {"variant": variant, "story": r["id"], "sentences": r["sentences_in_memory"], "index_sha": r["index_sha"], "notes": r["notes"], "coverage": r["plant_coverage"], "planted": plants_n,
           "extra": r["extra"], "elapsed_s": r["elapsed_s"], "questions": []}
    for q in r["questions"]:
        kind = ASK_KIND.get(q["kind"], "absent")
        out["questions"].append({"kind": kind, "verdict": q["verdict"], "route": q["route"], "admitted": q.get("admitted"), "lenient": q.get("lenient")})
    return out


def run_dev(variants: Sequence[str], workers: int, path: str = DEV, only: Optional[Sequence[str]] = None) -> dict:
    check_dev_path(path)
    stories = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
    if only:
        stories = [s for s in stories if s["id"] in only]
    jobs = [(v, s) for v in variants for s in stories]
    res = K.pmap(dev_job, jobs, workers)
    out: Dict[str, Any] = {}
    for v in variants:
        t = empty_tally()
        shas = []
        for r in (x for x in res if x["variant"] == v):
            t["runs"] += 1
            t["sentences"] += r["sentences"]
            for ty in NOTE_TYPES:
                t["notes"][ty].update(r["notes"].get(ty, {}))
                t["coverage"][ty].update(r["coverage"].get(ty, {}))
            t["extra"].update(r["extra"])
            for q in r["questions"]:
                add_questions(t, q["kind"], q)
            shas.append([r["story"], r["index_sha"]])
        out[v] = dict(freeze(t), index_sha=shas)
    return {"mode": "dev", "bank": os.path.relpath(path, ROOT), "bundle": BUNDLE, "variants": out}


# ------------------------------------------------------------------------------------------------------------
# meter: the stores of the memory meter v1
# ------------------------------------------------------------------------------------------------------------
def meter_job(args: Tuple[str, str]) -> dict:
    variant, run_dir = args
    m2 = K.load_m2()
    r = C.load_result(run_dir)
    task = C.mem_run.find_task(r["task_id"])
    plants = C.plant_sets(task)
    tmp = tempfile.mkdtemp(prefix="ablate_")
    try:
        store = os.path.join(tmp, "store")
        tally, ix, vstat, rstat = m2.drive(store, m2.meter_sessions(os.path.join(run_dir, "store")), versions_of(variant))
        rows = mem.MemStore(store).rows()
        snap = ma.write_snapshot(store, crosses=True, versions=True)
        qs = []
        for a in sorted(r["answers"], key=lambda a: a["index"]):
            gk, gv = C.mem_run.gold_values(a["gold"])
            ses = ma.AnswerSession(store, a["q"], "oracle", snapshot=snap, answer_version=ma.ANSWER_V17)
            res = ses.call("recall", {"question": a["q"]})
            kind = a["kind"] if a["kind"] in KINDS else "absent"
            row = {"kind": kind, "verdict": res["verdict"], "route": res.get("route")}
            if kind == "absent":
                row["admitted"] = res["verdict"] not in ("NONE", "CANDIDATES")
            else:
                row["lenient"] = K.judge_recall(res, kind, gv, True)
            qs.append(row)
        by_type, cov, extra = detect(plants, ix.notes, rows)
        return {"variant": variant, "label": C.label(run_dir), "sentences": len(rows), "index_sha": ix.index_sha, "verify": [vstat, rstat], "notes": {t: dict(c) for t, c in by_type.items()},
                "coverage": cov, "extra": dict(extra), "questions": qs}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_meter(variants: Sequence[str], workers: int, limit: int = 0, meter: str = C.METER_V1) -> dict:
    runs = C.structure_runs(meter)
    if limit:
        runs = runs[:limit]
    jobs = [(v, d) for v in variants for d in runs]
    res = K.pmap(meter_job, jobs, workers)
    out: Dict[str, Any] = {}
    for v in variants:
        t = empty_tally()
        bad, shas = [], []
        for r in (x for x in res if x["variant"] == v):
            shas.append([r["label"], r["index_sha"]])
            by = {ty: collections.Counter(r["notes"].get(ty, {})) for ty in NOTE_TYPES}
            merge(t, by, r["coverage"], r["extra"], r["sentences"])
            for q in r["questions"]:
                add_questions(t, q["kind"], q)
            if r["verify"][0] != "OK" or r["verify"][1] not in (None, "OK", "IDENTICAL"):
                bad.append([r["label"], r["verify"]])
        out[v] = dict(freeze(t), not_verified=bad, index_sha=shas)
    return {"mode": "meter", "meter": os.path.relpath(meter, ROOT), "runs": len(runs), "bundle": BUNDLE, "variants": out}


# ------------------------------------------------------------------------------------------------------------
# tables
# ------------------------------------------------------------------------------------------------------------
def headline(v: dict) -> Dict[str, int]:
    """The integer columns the difference tables use."""
    q = v["questions"]
    h = {}
    for t in NOTE_TYPES:
        h["found_" + t] = v["coverage"][t].get("found", 0)
        h["fired_" + t] = v["notes"][t].get("total", 0)
        h["hit_" + t] = v["notes"][t].get("hit", 0)
    for k in ("plain", "contradicted", "updated"):
        h["reached_" + k] = q[k].get("reached", 0)
        h["exact_" + k] = q[k].get("exact", 0)
        h["extra_" + k] = q[k].get("extra", 0)
    h["absent_admitted"] = q["absent"].get("admitted", 0)
    h["reached_all"] = sum(h["reached_" + k] for k in ("plain", "contradicted", "updated"))
    h["exact_all"] = sum(h["exact_" + k] for k in ("plain", "contradicted", "updated"))
    return h


def baseline_of(variant: str) -> str:
    return "A3" if variant.startswith("A3-no") else "A3f"


def deltas(res: dict) -> dict:
    out = {}
    V = res["variants"]
    for name in V:
        if name in ("A3", "A3f") or baseline_of(name) not in V:
            continue
        a, b = headline(V[name]), headline(V[baseline_of(name)])
        out[name] = {"vs": baseline_of(name), "delta": {k: a[k] - b[k] for k in sorted(a) if a[k] != b[k]}, "same_index": V[name].get("index_sha") is not None and V[name].get("index_sha") == V[baseline_of(name)].get("index_sha")}
    return out


def md(res: dict) -> str:
    V = res["variants"]
    names = list(V)
    L = ["# Geometry ablation (%s, offline, no model)" % res["mode"], "", "Bundle %s. Variants: %s." % (res["bundle"], ", ".join(names)), "",
         "A3 = all geometry on; A3f = all off; `A3-no<c>` leave-one-out (compare with A3); `A3f-plus<c>` add-one-in (compare with A3f). ladder / arms are read only by the key (`A3f-plusladder`, `A3f-plusarms` switch the key on too).",
         "Every cell is a count. `found` = planted conflicts a note of that type touched; `fired` = notes; `hit` = notes on a plant of their kind.", ""]
    L += ["## Detection", "", "| variant | " + " | ".join("%s found/fired/hit" % t for t in NOTE_TYPES) + " |", "|---|" + "---|" * len(NOTE_TYPES)]
    for n in names:
        h = headline(V[n])
        L.append("| %s | %s |" % (n, " | ".join("%d / %d / %d" % (h["found_" + t], h["fired_" + t], h["hit_" + t]) for t in NOTE_TYPES)))
    L += ["", "Planted per type: " + ", ".join("%s %d" % (t, V[names[0]]["coverage"][t].get("plants", 0)) for t in NOTE_TYPES), ""]
    L += ["## Recall (lenient)", "", "| variant | plain reached/exact/extra | contradicted reached/exact/extra | updated reached/exact/extra | absent admitted |", "|---|---|---|---|---|"]
    for n in names:
        h = headline(V[n])
        L.append("| %s | %s | %s | %s | %d |" % (n, *("%d / %d / %d" % (h["reached_" + k], h["exact_" + k], h["extra_" + k]) for k in ("plain", "contradicted", "updated")), h["absent_admitted"]))
    asked = {k: V[names[0]]["questions"][k].get("n", 0) for k in KINDS}
    L += ["", "Questions asked (per variant): %s" % asked, "", "## Differences (the variant minus its baseline; only the columns that differ)", ""]
    for n, d in deltas(res).items():
        L.append("- %s vs %s: %s%s" % (n, d["vs"], d["delta"] if d["delta"] else "no difference in any column", "" if not d["same_index"] else " (identical index bytes)"))
    L.append("")
    return "\n".join(L)


def write_outputs(res: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    res = dict(res, deltas=deltas(res))
    K.write_json(os.path.join(out_dir, "ablate_%s.json" % res["mode"]), res)
    path = os.path.join(out_dir, "ablate_%s.md" % res["mode"])
    K.write_text(path, md(res))
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("dev", "meter", "all"))
    ap.add_argument("--workers", type=int, default=K.DEFAULT_WORKERS)
    ap.add_argument("--limit", type=int, default=0, help="meter: only the first N runs (a smoke test)")
    ap.add_argument("--variants", default=None, help="comma-separated (default: A3, A3f, the six A3-no<c>, the six A3f-plus<c>)")
    ap.add_argument("--story", default=None, help="dev: comma-separated story ids")
    ap.add_argument("--out", default=HERE)
    ns = ap.parse_args(argv)
    try:
        variants = parse_variants(ns.variants)
        if ns.mode in ("meter", "all"):
            print(write_outputs(run_meter(variants, ns.workers, ns.limit), ns.out))
        if ns.mode in ("dev", "all"):
            print(write_outputs(run_dev(variants, ns.workers, DEV, ns.story.split(",") if ns.story else None), ns.out))
        return 0
    except AblateError as e:
        print("ablate: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""MEM-fix (4): how precise is REVERSAL?  Offline, no API.

The meter v1 found REVERSAL firing on 16-22 % of the stored sentences and could not tell which two messages it was about.  A mem.v3 REVERSAL note CITES them (memnotes.cite_reversals:
the write's sentence + the earlier sentences that hold the pair of words in the other order, with their turns).  This script reads every REVERSAL note of the stored meter_v1 ledgers,
recomputes the cited sentences from the memory the write was judged against (`memnotes.reversal_witnesses`, a pure function of the corpus: the same call the v3 note makes) and checks
each firing against the bank's plants:
  planted reversal   the write's turn and a cited earlier turn are BOTH message_refs of one 'reversal' plant
  other plant        both are refs of a plant of another kind (a contradiction, an update, a list trap, a repeat)
  no plant           the two turns share no plant (a false alarm, or a real inversion the bank did not plant)
  no pair            the cited sentences carry no other turn (same message, or no turn)
and which of the planted reversals (2 per task) some firing cited at all.
  python experiments/line3/mem/memfix/reversal_precision.py [--meter DIR] [--out DIR]       -> reversal_precision.json, reversal_precision.md
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import memfix_common as C
from verantyx.loom import memnotes as mn
from verantyx.loom import memory as mem


def classify_firing(plants: Sequence[dict], this_turn: Optional[str], witness_turns: Sequence[str]) -> Dict[str, Any]:
    """{'class': reversal | other_plant | no_plant | no_pair, 'plants': [indices of the reversal plants hit]}"""
    pairs = [(w, this_turn) for w in witness_turns if this_turn and w and w != this_turn]
    if not pairs:
        return {"class": "no_pair", "plants": []}
    hit_rev: List[int] = []
    other: List[str] = []
    for w, t in pairs:
        for k in C.classify_pair(plants, w, t):
            if plants[k]["kind"] == "reversal":
                if k not in hit_rev:
                    hit_rev.append(k)
            elif plants[k]["kind"] not in other:
                other.append(plants[k]["kind"])
    if hit_rev:
        return {"class": "reversal", "plants": sorted(hit_rev), "other_kinds": sorted(other)}
    return {"class": "other_plant" if other else "no_plant", "plants": [], "other_kinds": sorted(other)}


def firings_of_store(store: str, use_cite: bool) -> List[dict]:
    """Every REVERSAL note of the store's ledgers as {sid, turn, witnesses [sid], witness_turns [turn]}: from the note's own `cite` / `earlier` (a mem.v3 store) or, for a store written before,
    recomputed from the memory (`reversal_witnesses` over the rows before the write)."""
    rows = C.memory_rows(store)
    out = []
    for _run_id, srows in C.session_ledger_rows(store):
        for w in C.written_with_notes(srows):
            for n in w["notes"]:
                if n["type"] != mn.REVERSAL:
                    continue
                if use_cite and "earlier" in n:
                    wit = [e["sid"] for e in n["earlier"]]
                    wt = [e.get("turn") for e in n["earlier"]]
                else:
                    before = mem.build_corpus(rows[:w["sid"]])
                    wit = mn.reversal_witnesses(before, n["centre"], [u["unit"] for u in n["units"]])
                    wt = [rows[x].get("turn") for x in wit]
                out.append({"sid": w["sid"], "turn": w["turn"], "text": w["text"], "centre": n["centre"], "witnesses": wit, "witness_turns": wt})
    return out


def analyse_store(store: str, task: dict, use_cite: bool = False) -> dict:
    plants = C.plant_sets(task)
    rows = C.memory_rows(store)
    fir = firings_of_store(store, use_cite)
    cls = collections.Counter()
    kinds = collections.Counter()
    covered = set()
    for f in fir:
        c = classify_firing(plants, f["turn"], f["witness_turns"])
        f["class"], f["plants"] = c["class"], c["plants"]
        cls[c["class"]] += 1
        if c["class"] == "other_plant":
            kinds[c["other_kinds"][0]] += 1                       # the first kind in alphabetical order when a firing touches several
        covered.update(c["plants"])
    rev_plants = [k for k, p in enumerate(plants) if p["kind"] == "reversal"]
    return {"sentences": len(rows), "firings": len(fir), "classes": dict(cls), "other_kinds": dict(kinds), "reversal_plants": len(rev_plants), "reversal_plants_cited": len(covered & set(rev_plants)),
            "firing_sentences": len({f["sid"] for f in fir}), "examples": fir[:6]}


def tally(per: Sequence[dict]) -> dict:
    t = {"runs": len(per), "sentences": sum(p["sentences"] for p in per), "firings": sum(p["firings"] for p in per), "firing_sentences": sum(p["firing_sentences"] for p in per),
         "classes": {k: sum(p["classes"].get(k, 0) for p in per) for k in ("reversal", "other_plant", "no_plant", "no_pair")},
         "other_kinds": {k: sum(p.get("other_kinds", {}).get(k, 0) for p in per) for k in ("contradiction", "update", "list_trap", "repeat")},
         "reversal_plants": sum(p["reversal_plants"] for p in per), "reversal_plants_cited": sum(p["reversal_plants_cited"] for p in per)}
    t["share_of_sentences"] = round(t["firing_sentences"] / t["sentences"], 3) if t["sentences"] else None
    t["precision"] = round(t["classes"]["reversal"] / t["firings"], 3) if t["firings"] else None
    return t


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meter", default=C.METER_V1)
    ap.add_argument("--out", default=os.path.join(C.HERE, "results"))
    ns = ap.parse_args(argv)
    per: List[dict] = []
    for d in C.structure_runs(ns.meter):
        r = C.load_result(d)
        a = analyse_store(os.path.join(d, "store"), C.mem_run.find_task(r["task_id"]))
        a.update(run=C.label(d), arm=r["arm_label"], task=r["task_id"])
        per.append(a)
    out = {"meter": os.path.relpath(ns.meter, C.ROOT), "total": tally(per), "by_arm": {arm: tally([p for p in per if p["arm"] == arm]) for arm in ("A2b", "A2")},
           "by_task": {t: tally([p for p in per if p["task"] == t]) for t in sorted({p["task"] for p in per})}, "per_run": per}
    os.makedirs(ns.out, exist_ok=True)
    with open(os.path.join(ns.out, "reversal_precision.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, indent=1)
        f.write("\n")
    md = ["# MEM-fix REVERSAL の精度（offline, API なし）", "", "meter_v1 の構造 arm %d run の台帳にある REVERSAL 注記を、保存文の記憶から「引用する 2 通」に直して、仕掛けの反転と照合した。" % len(per), "",
          "| 集計 | run | 保存文 | REVERSAL 発火 | 発火した文 | 仕掛けの反転に当たる | 他の仕掛けに当たる | 仕掛けに当たらない | 対を作れない | 適合率 | 仕掛けの反転が引用された |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, t in [("全体", out["total"])] + [("arm " + a, out["by_arm"][a]) for a in ("A2b", "A2")]:
        c = t["classes"]
        md.append("| %s | %d | %d | %d | %d (%.1f %%) | %d | %d | %d | %d | %.3f | %d / %d |" % (name, t["runs"], t["sentences"], t["firings"], t["firing_sentences"], 100.0 * (t["share_of_sentences"] or 0), c["reversal"], c["other_plant"], c["no_plant"],
                                                                                         c["no_pair"], t["precision"] or 0.0, t["reversal_plants_cited"], t["reversal_plants"]))
    ok = out["total"]["other_kinds"]
    md += ["", "「他の仕掛けに当たる」の内訳（全体、複数に当たる発火は先頭の種類）: 矛盾 %d / 更新 %d / 列挙の罠 %d / 繰り返し %d。" % (ok["contradiction"], ok["update"], ok["list_trap"], ok["repeat"])]
    with open(os.path.join(ns.out, "reversal_precision.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

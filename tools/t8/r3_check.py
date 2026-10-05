"""W16-t8 r3 (docs/COARSE_PLACEMENT.md 12.21.7): the synthetic check of the auditor's two rulings (2026-10-06 00:24).  A pass shows that the tools do what the rulings say; it is not evidence that the reader generalizes.

Mode 1 (apply): every row of the truth list is written through the CLI (``verantyx.cli.main`` -> ``vera confirm set|frame``) into a NEW layer and ledger -- NOT chosen by ``suggest`` (for ``frame_kept`` suggest
names nothing: the base's 12.10 frame is not reachable, so the truth list is written as a whole on purpose; the output says what suggest names before) -- and every sentence is read without and with the layer.
Per group: readable before / after, ``changed_output`` (the whole reading differs), ``misread`` (``measure.judge``: a reading that differs from ``expect``, or a reading where ``expect == "ABSTAIN"``),
``abstained_after`` (id -> the reasons).  Per confirmed word: the base state and the answer through the layer (``layer_status``, ``decided_by[0]``, the 12.10 frame and role frame the answer carries).

  python tools/t8/r3_check.py --placement P --data D --rows synthetic_r3.jsonl --truth confirmations_truth_r3.jsonl --freeze data_freeze_r3.sha256 --out DIR

Mode 2 (combine): ``--combine-from <layer made by vera confirm>``: ``tools/build_initial_layers.py combine`` (a subprocess, the real route; it is read, not changed) copies that layer into a new one, the rows are read
with the combined layer and compared byte for byte with the reading without a layer (``identical_to_no_layer``), and every word of the combined layer is queried (``layer_status`` counts: a copied confirmation
must never be ``HUMAN_CONFIRMED_USED`` or ``LAYER_DIRECT_USED``).

  python tools/t8/r3_check.py --placement P --data D --rows synthetic_r3.jsonl --freeze data_freeze_r3.sha256 --combine-from LAYER --out DIR

Outputs (in --out): r3_summary.json (no ids, times or paths: the same input gives the same summary), r3_before.jsonl, r3_after.jsonl, and in mode 1 the layer, the ledger and r3_list.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.t8.t82_flow import _cli, _load, _read_all, verify_freeze      # noqa: E402
from tools.t8.measure import judge                                          # noqa: E402

BY = "r3-check"


def _dump(x: Any) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def _reasons(rd: Dict[str, Any]) -> List[str]:
    return list((rd.get("abstain") or {}).get("reasons") or [])


def _groups(rows: Sequence[Dict[str, Any]], before: Sequence[Dict[str, Any]], after: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for g in sorted({r["group"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["group"] == g]
        out[g] = {"n": len(idx), "readable_before": sum(1 for i in idx if before[i].get("readable")), "readable_after": sum(1 for i in idx if after[i].get("readable")),
                  "changed_output": [rows[i]["id"] for i in idx if _dump(before[i]) != _dump(after[i])],
                  "misread": [rows[i]["id"] for i in idx if judge(after[i], rows[i]["expect"]) == "misread"],
                  "abstained_after": {rows[i]["id"]: _reasons(after[i]) for i in idx if not after[i].get("readable")}}
    return out


def _write_reads(out_dir: str, rows: Sequence[Dict[str, Any]], before: Sequence[Dict[str, Any]], after: Sequence[Dict[str, Any]]) -> None:
    for name, rds in (("r3_before.jsonl", before), ("r3_after.jsonl", after)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            for r, rd in zip(rows, rds):
                f.write(json.dumps({"id": r["id"], "group": r["group"], "text": r["text"], "reading": rd}, ensure_ascii=False, sort_keys=True) + "\n")


def _suggest_before(textf: str, placement: str) -> Dict[str, Any]:
    rc, js = _cli(["confirm", "suggest", "--text", textf, "--placement", placement, "--json"])
    rows = json.loads(js)["rows"]
    named = sorted({r["word"] for r in rows if r["op"] in ("set", "frame") and r["reachable"] and r["word"]})
    unreach = sorted({"%s:%s" % (r["word"], r["why"]) for r in rows if r["op"] == "frame" and r["reachable"] is False and r["word"]})
    return {"rc": rc, "reachable_words": named, "frame_rows_not_reachable": unreach}


def run_apply(placement: str, data_dir: str, out_dir: str, rows_file: str, truth_file: str, freeze_file: str) -> Dict[str, Any]:
    from verantyx import coarse_place
    os.makedirs(out_dir, exist_ok=True)
    layer, ledger, textf = os.path.join(out_dir, "r3_layer.sqlite"), os.path.join(out_dir, "r3_ledger.jsonl"), os.path.join(out_dir, "r3_sentences.txt")
    for p in (layer, ledger):
        if os.path.exists(p):
            raise RuntimeError("OUT_NOT_FRESH:" + p)
    rows, truth = _load(os.path.join(data_dir, rows_file)), _load(os.path.join(data_dir, truth_file))
    with open(textf, "w", encoding="utf-8") as f:
        f.write("".join(r["text"] + "\n" for r in rows))
    before = _read_all(rows, placement, None)
    suggest = _suggest_before(textf, placement)
    refused = []
    for t in truth:
        argv = ["confirm", "set", t["word"], t["type"]] if t["op"] == "set" else ["confirm", "frame", t["predicate"], t["particle"], t["role"]] + list(t["types"])
        rc, o = _cli(argv + ["--by", BY, "--reason", t.get("reason") or "", "--layer", layer, "--ledger-file", ledger, "--placement", placement])
        if rc != 0:
            refused.append({"row": t, "output": o.strip()})
    rc, lst = _cli(["confirm", "list", "--layer", layer, "--placement", placement, "--json"])
    with open(os.path.join(out_dir, "r3_list.json"), "w", encoding="utf-8") as f:
        f.write(lst)
    after = _read_all(rows, placement, layer)
    _write_reads(out_dir, rows, before, after)
    words = []
    for t in truth:
        if t["op"] != "set":
            continue
        base = coarse_place.query(t["word"], placement=placement, layer=False)
        got = coarse_place.query(t["word"], placement=placement, layer=layer)
        words.append({"word": t["word"], "type": t["type"], "base_state": base["state"], "base_origin": base["origin"], "base_top": base["top"], "layer_status": got["layer_status"],
                      "decided_by_first": (got.get("decided_by") or [""])[0].split(":")[0], "decided_by_ends_with_gen_frame": (got.get("decided_by") or [""])[-1] == "gen_frame",
                      "frame_status": [base.get("frame_status"), got.get("frame_status")], "frame_same_as_base": got.get("frame") == base.get("frame"),
                      "role_frame_status": [base.get("role_frame_status"), got.get("role_frame_status")], "role_frame_same_as_base": got.get("role_frame") == base.get("role_frame")})
    summary = {"schema": "verantyx.r3_check/1", "mode": "apply", "rows": rows_file, "truth_rows": len(truth), "confirmations_refused": refused, "suggest_before": suggest,
               "groups": _groups(rows, before, after), "confirmed_words": words, "data_freeze_mismatch": verify_freeze(data_dir, freeze_file),
               "note": "the whole truth list is written (not chosen by suggest); a pass shows that the tools do what the rulings say, not that the reader generalizes"}
    with open(os.path.join(out_dir, "r3_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return summary


def run_combine(placement: str, data_dir: str, out_dir: str, rows_file: str, freeze_file: str, layer_src: str) -> Dict[str, Any]:
    from verantyx import coarse_place
    from verantyx import placement_layer as PL
    os.makedirs(out_dir, exist_ok=True)
    comb, ledger, report = os.path.join(out_dir, "r3_combined.sqlite"), os.path.join(out_dir, "r3_combined_ledger.jsonl"), os.path.join(out_dir, "r3_combine_report.json")
    for p in (comb, ledger, report):
        if os.path.exists(p):
            raise RuntimeError("OUT_NOT_FRESH:" + p)
    rows = _load(os.path.join(data_dir, rows_file))
    env = {k: v for k, v in os.environ.items() if k not in ("VERA_PLACEMENT", "VERA_PLACEMENT_LAYER", "VERA_PLACEMENT_LAYER_ROOT")}
    env.update({"PYTHONPATH": _ROOT, "PYTHONDONTWRITEBYTECODE": "1"})
    cp = subprocess.run([sys.executable, os.path.join(_ROOT, "tools", "build_initial_layers.py"), "combine", "--base", placement, "--layer", layer_src, "--out", comb, "--ledger", ledger,
                         "--report", report], cwd=_ROOT, env=env, capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError("COMBINE_FAILED:%s" % cp.stderr.strip()[-400:])
    before = _read_all(rows, placement, None)
    after = _read_all(rows, placement, comb)
    _write_reads(out_dir, rows, before, after)
    layer, why = PL.open_layer(comb, None)
    assert layer is not None, why
    ents = layer.all_entries()
    statuses: Dict[str, int] = {}
    for w in sorted({e["word"] for e in ents}):
        st = coarse_place.query(w, placement=placement, layer=comb)["layer_status"]
        statuses[st] = statuses.get(st, 0) + 1
    shape = {"rows": len(ents), "origins": sorted({e["origin"] for e in ents}), "rows_with_human_arm": sum(1 for e in ents if any(str(b).startswith("human:") for b in e["decided_by"])),
             "rows_that_are_confirmation_rows": sum(1 for e in ents if PL.is_confirm_row(e)), "rows_unbacked_human": sum(1 for e in ents if PL.is_unbacked_human_row(e))}
    diff = [r["id"] for r, b, a in zip(rows, before, after) if _dump(b) != _dump(a)]
    summary = {"schema": "verantyx.r3_check/1", "mode": "combine", "rows": rows_file, "combined_layer": shape, "identical_to_no_layer": not diff, "differs": diff,
               "readable_no_layer": sum(1 for b in before if b.get("readable")), "readable_combined": sum(1 for a in after if a.get("readable")),
               "layer_status_of_the_words": dict(sorted(statuses.items())),
               "human_confirmed_or_direct_used": statuses.get("HUMAN_CONFIRMED_USED", 0) + statuses.get("LAYER_DIRECT_USED", 0),
               "data_freeze_mismatch": verify_freeze(data_dir, freeze_file)}
    with open(os.path.join(out_dir, "r3_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--rows", default="synthetic_r3.jsonl")
    ap.add_argument("--truth", default="confirmations_truth_r3.jsonl")
    ap.add_argument("--freeze", default="data_freeze_r3.sha256")
    ap.add_argument("--combine-from", default=None, dest="combine_from")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(list(argv) if argv is not None else None)
    if a.combine_from:
        s = run_combine(a.placement, a.data, a.out, a.rows, a.freeze, a.combine_from)
    else:
        s = run_apply(a.placement, a.data, a.out, a.rows, a.truth, a.freeze)
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

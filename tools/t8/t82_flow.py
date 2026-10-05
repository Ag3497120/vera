"""W16-t8 (T8-2): the synthetic check of the tool chain, run through the CLI entry (`verantyx.cli.main`) exactly the way a person would:

  read every sentence (no layer)  ->  `vera confirm suggest`  ->  write the confirmations the suggestion NAMES (from the truth list)  ->  suggest again (at most 3 rounds)  ->  read again.

Only the words suggest named are confirmed; a word of the truth list nobody named is never written.  Outputs (in --out): t82_suggest_round<N>.tsv, t82_list.json, t82_before.jsonl, t82_after.jsonl,
t82_base_decided.json, t82_summary.json.  The data are the writer's own: a pass here shows that the tools work, not that the reader generalizes.

  python tools/t8/t82_flow.py --placement P --data artifacts/w16-t8/data --out DIR
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

MAX_ROUNDS = 3


def _cli(argv: Sequence[str]) -> tuple:
    from verantyx import cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(list(argv))
    return rc, buf.getvalue()


def _load(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def verify_freeze(data_dir: str, freeze_file: str = "data_freeze.sha256") -> List[str]:
    """The files whose sha256 differs from ``data_freeze.sha256`` (next to the data directory); empty when the data are the frozen ones."""
    bad = []
    with open(os.path.join(os.path.dirname(os.path.abspath(data_dir)), freeze_file), encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            sha, name = line.split()
            got = hashlib.sha256(open(os.path.join(data_dir, name), "rb").read()).hexdigest()
            if got != sha:
                bad.append(name)
    return bad


def _read_all(rows: Sequence[Dict[str, Any]], placement: str, layer: Optional[str]) -> List[Dict[str, Any]]:
    from verantyx import semantic_read as SR
    old = os.environ.get("VERA_PLACEMENT_LAYER")
    try:
        if layer:
            os.environ["VERA_PLACEMENT_LAYER"] = layer
        else:
            os.environ.pop("VERA_PLACEMENT_LAYER", None)
        return [SR.read(r["text"], placement=placement) for r in rows]
    finally:
        if old is None:
            os.environ.pop("VERA_PLACEMENT_LAYER", None)
        else:
            os.environ["VERA_PLACEMENT_LAYER"] = old


def _clauses(rd: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{k: c.get(k) for k in ("predicate", "roles", "polarity", "tense", "voice")} for c in (rd.get("clauses") or [])]


def run_flow(placement: str, data_dir: str, out_dir: str, rows_file: str = "synthetic_40.jsonl", truth_file: str = "confirmations_truth.jsonl",
             freeze_file: str = "data_freeze.sha256") -> Dict[str, Any]:
    from verantyx import coarse_place
    from tools.t8.measure import judge
    os.makedirs(out_dir, exist_ok=True)
    rows = _load(os.path.join(data_dir, rows_file))
    truth = _load(os.path.join(data_dir, truth_file))
    layer, ledger, textf = os.path.join(out_dir, "t82_layer.sqlite"), os.path.join(out_dir, "t82_ledger.jsonl"), os.path.join(out_dir, "t82_sentences.txt")
    for p in (layer, ledger):
        if os.path.exists(p):
            raise RuntimeError("OUT_NOT_FRESH:" + p)
    with open(textf, "w", encoding="utf-8") as f:
        f.write("".join(r["text"] + "\n" for r in rows))
    before = _read_all(rows, placement, None)
    written, rounds = [], []
    for rnd in range(1, MAX_ROUNDS + 1):
        rc, out = _cli(["confirm", "suggest", "--text", textf, "--placement", placement] + (["--layer", layer] if os.path.exists(layer) else []))
        with open(os.path.join(out_dir, "t82_suggest_round%d.tsv" % rnd), "w", encoding="utf-8") as f:
            f.write(out)
        rc2, js = _cli(["confirm", "suggest", "--text", textf, "--placement", placement, "--json"] + (["--layer", layer] if os.path.exists(layer) else []))
        named = []
        for r in json.loads(js)["rows"]:
            if r["op"] in ("set", "frame") and r["reachable"] and r["word"] not in named:
                named.append(r["word"])
        new = []
        for w in named:
            for i, t in enumerate(truth):
                key = t.get("word") if t["op"] == "set" else t.get("predicate")
                if key == w and i not in written:
                    new.append(i)
        for i in sorted(set(new)):
            t = truth[i]
            if t["op"] == "set":
                argv = ["confirm", "set", t["word"], t["type"]]
            else:
                argv = ["confirm", "frame", t["predicate"], t["particle"], t["role"]] + list(t["types"])
            rc3, o3 = _cli(argv + ["--by", "t82-flow", "--reason", t.get("reason") or "", "--layer", layer, "--ledger-file", ledger, "--placement", placement])
            if rc3 != 0:
                raise RuntimeError("CONFIRM_REFUSED:%s:%s" % (argv, o3))
            written.append(i)
        rounds.append({"round": rnd, "suggest_rc": rc, "named": named, "written": [truth[i].get("word") or truth[i].get("predicate") for i in sorted(set(new))]})
        if not new:
            break
    rc, lst = _cli(["confirm", "list", "--layer", layer, "--placement", placement, "--json"])
    with open(os.path.join(out_dir, "t82_list.json"), "w", encoding="utf-8") as f:
        f.write(lst)
    after = _read_all(rows, placement, layer)
    for name, rds in (("t82_before.jsonl", before), ("t82_after.jsonl", after)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            for r, rd in zip(rows, rds):
                f.write(json.dumps({"id": r["id"], "group": r["group"], "text": r["text"], "reading": rd}, ensure_ascii=False, sort_keys=True) + "\n")
    # the override words: the base answer decided (DECIDED) and the answer through the layer says `human:`
    over = []
    for t in truth:
        if t["op"] != "set":
            continue
        base = coarse_place.query(t["word"], placement=placement, layer=False)
        got = coarse_place.query(t["word"], placement=placement, layer=layer)
        over.append({"word": t["word"], "type": t["type"], "base_state": base["state"], "base_top": base["top"], "base_origin": base["origin"], "base_decided_by": base.get("decided_by"),
                     "layer_status": got["layer_status"], "top": got["top"], "decided_by": got.get("decided_by")})
    with open(os.path.join(out_dir, "t82_base_decided.json"), "w", encoding="utf-8") as f:
        json.dump(over, f, ensure_ascii=False, indent=1)
        f.write("\n")
    groups = {}
    for g in sorted({r["group"] for r in rows}, key=lambda x: (x != "target", x != "control", x)):
        idx = [i for i, r in enumerate(rows) if r["group"] == g]
        mis = [rows[i]["id"] for i in idx if judge(after[i], rows[i]["expect"]) == "misread"]      # the same rule as measure.judge (12.21.4): a differing reading, or readable although expect == "ABSTAIN"
        groups[g] = {"n": len(idx), "readable_before": sum(1 for i in idx if before[i].get("readable")), "readable_after": sum(1 for i in idx if after[i].get("readable")),
                     "changed_output": [rows[i]["id"] for i in idx if json.dumps(before[i], sort_keys=True, ensure_ascii=False) != json.dumps(after[i], sort_keys=True, ensure_ascii=False)],
                     "misread": mis, "abstained_after": [rows[i]["id"] for i in idx if not after[i].get("readable")]}
        if g == "frame_not_restrictive":      # read although the declared frame does not list the type of its goal (12.21.6): the frame adds / checks, it does not restrict
            groups[g]["not_stopped"] = sum(1 for i in idx if after[i].get("readable"))
    summary = {"schema": "verantyx.t82_flow/1", "placement": placement, "rounds": rounds, "confirmations_written": len(written), "confirmations_in_truth": len(truth),
               "truth_not_named": [t.get("word") or t.get("predicate") for i, t in enumerate(truth) if i not in written], "groups": groups,
               "overrode_decided": [o["word"] for o in over if o["base_state"] == "DECIDED" and (o["decided_by"] or [""])[0].startswith("human:")],
               "data_freeze_mismatch": verify_freeze(data_dir, freeze_file)}
    with open(os.path.join(out_dir, "t82_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", default="synthetic_40.jsonl")
    ap.add_argument("--truth", default="confirmations_truth.jsonl")
    ap.add_argument("--freeze", default="data_freeze.sha256")
    a = ap.parse_args(list(argv) if argv is not None else None)
    s = run_flow(a.placement, a.data, a.out, a.rows, a.truth, a.freeze)
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

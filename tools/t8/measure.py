"""W16-t8 (K682, docs/COARSE_PLACEMENT.md 12.21.4): the measuring tool of the reader's deciding trial.

For each number of confirmations k (0, 5, 10, ... 50 by default; never more than the rows of the confirmation list) a NEW ledger and layer are made, the first k rows are written the way
``vera confirm`` writes them (``verantyx.confirm_cli``), and every sentence of the three sets (train / test / real) is read the way the product reads (``semantic_read.read(text, placement=<path>)``
with ``VERA_PLACEMENT_LAYER`` set to that layer).  Per set and k: readable, newly_read (not read at k=0, read now), lost, correct, misread, unjudged; per set the least-squares slope of newly_read on k;
the overlap of the confirmed words with the test set; the owner's minutes (a field a human fills in).  Nothing is guessed: an ``expect`` of null is unjudged.

  python tools/t8/measure.py --placement P --confirmations F --train F --test F --real F --out DIR [--steps 0,5,10] [--owner-minutes F]

Files (JSONL, one object per line): confirmations ``{"op":"set","word","type","reason"}`` / ``{"op":"frame","predicate","particle","role","types","reason"}``; sentences ``{"id","text","expect"}`` with
``expect`` a list of clauses ``{"predicate","roles","polarity","tense","voice"}``, ``"ABSTAIN"`` or null.  A misread is a sentence that was READ and (the clauses differ from ``expect``, or ``expect`` is ``"ABSTAIN"``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Sequence

SETS = ("train", "test", "real")
CLAUSE_KEYS = ("predicate", "roles", "polarity", "tense", "voice")
DEFAULT_STEPS = tuple(range(0, 51, 5))
CONFIRMER = "t8-measure"


class MeasureError(Exception):
    pass


def _nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise MeasureError("BAD_JSONL:%s:%d:%s" % (path, n, exc))
    return rows


def _stems(word: str) -> List[str]:
    """The word, and its stem (without a final ``する``; without the last character when it is a hiragana verb ending)."""
    w = _nfkc(word)
    out = [w] if w else []
    if w.endswith("する") and len(w) > 2:
        out.append(w[:-2])
    elif len(w) > 1 and "ぁ" <= w[-1] <= "ゟ":
        out.append(w[:-1])
    return out


def overlap(confirmations: Sequence[Dict[str, Any]], sentences: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Confirmed words (a ``set`` word, a ``frame`` predicate) whose text or stem occurs in a sentence (NFKC) -> ``[{id, word, matched}]``."""
    out = []
    for c in confirmations:
        word = c.get("word") if c.get("op") == "set" else c.get("predicate")
        for s in _stems(word or ""):
            for row in sentences:
                if s and s in _nfkc(row["text"]):
                    out.append({"id": row["id"], "word": word, "matched": s})
    seen, uniq = set(), []
    for o in out:
        k = (o["id"], o["word"])
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    return uniq


def clauses_of(reading: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{k: c.get(k) for k in CLAUSE_KEYS} for c in (reading.get("clauses") or [])]


def judge(reading: Dict[str, Any], expect: Any) -> str:
    """``abstain`` / ``correct`` / ``misread`` / ``unjudged``."""
    if not reading.get("readable"):
        return "abstain"
    if expect is None:
        return "unjudged"
    if expect == "ABSTAIN":
        return "misread"
    return "correct" if clauses_of(reading) == expect else "misread"


def slope(points: Sequence[Sequence[float]]) -> Optional[float]:
    """Least squares slope of y on k: sum((k - kbar)(y - ybar)) / sum((k - kbar)^2); None with fewer than two distinct k."""
    ks = [p[0] for p in points]
    if len(set(ks)) < 2:
        return None
    kb, yb = sum(ks) / len(ks), sum(p[1] for p in points) / len(points)
    return sum((k - kb) * (y - yb) for k, y in points) / sum((k - kb) ** 2 for k in ks)


def _read_all(sets: Dict[str, List[Dict[str, Any]]], placement: str, layer_path: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
    from verantyx import semantic_read as SR
    old = os.environ.get("VERA_PLACEMENT_LAYER")
    try:
        if layer_path:
            os.environ["VERA_PLACEMENT_LAYER"] = layer_path
        else:
            os.environ.pop("VERA_PLACEMENT_LAYER", None)
        out = {}
        for name, rows in sets.items():
            out[name] = []
            for r in rows:
                try:
                    out[name].append(SR.read(r["text"], placement=placement))
                except SR.ReadError as exc:
                    out[name].append({"readable": False, "clauses": [], "abstain": {"kind": "refused_input", "reasons": [exc.type]}})
        return out
    finally:
        if old is None:
            os.environ.pop("VERA_PLACEMENT_LAYER", None)
        else:
            os.environ["VERA_PLACEMENT_LAYER"] = old


def _write_confirmations(rows: Sequence[Dict[str, Any]], work: str, placement: str) -> Optional[str]:
    """A new ledger and layer in ``work``; the rows written through the same functions ``vera confirm`` uses.  Returns the layer path (None for no row)."""
    from verantyx import confirm_cli as CC
    if not rows:
        return None
    os.makedirs(work, exist_ok=True)
    layer, ledger = os.path.join(work, "layer.sqlite"), os.path.join(work, "ledger.jsonl")
    if os.path.exists(layer) or os.path.exists(ledger):
        raise MeasureError("OUT_NOT_FRESH:%s (a layer or ledger is already there: give a new --out)" % work)
    t = CC.open_target(layer, ledger, placement, need_ledger=True, create_ledger=True)
    for c in rows:
        try:
            if c["op"] == "set":
                CC.confirm_set(t, c["word"], c["type"], CONFIRMER, c.get("reason"))
            elif c["op"] == "frame":
                CC.confirm_frame(t, c["predicate"], c["particle"], c["role"], c["types"], CONFIRMER, c.get("reason"))
            else:
                raise MeasureError("BAD_OP:%s" % c.get("op"))
        except CC.ConfirmError as exc:        # a refused confirmation (e.g. a frame whose predicate has no human type yet): a typed refusal, not a traceback
            raise MeasureError("CONFIRMATION_REFUSED:%s:%s" % (c.get("word") or c.get("predicate"), exc))
    return layer


def measure(placement: str, confirmations: List[Dict[str, Any]], sets: Dict[str, List[Dict[str, Any]]], out: str, steps: Sequence[int] = DEFAULT_STEPS,
            owner_minutes: Optional[float] = None) -> Dict[str, Any]:
    steps = sorted(set(int(s) for s in steps))
    if 0 not in steps:
        steps = [0] + steps
    run = [k for k in steps if k <= len(confirmations)]
    skipped = [k for k in steps if k > len(confirmations)]
    os.makedirs(out, exist_ok=True)
    per: Dict[str, Dict[str, Any]] = {n: {"n": len(rows), "per_k": [], "overlap": None} for n, rows in sets.items()}
    base_read: Dict[str, List[bool]] = {}
    detail = []
    for k in run:
        layer = _write_confirmations(confirmations[:k], os.path.join(out, "work", "k%d" % k), placement)
        readings = _read_all(sets, placement, layer)
        for name, rows in sets.items():
            now = [bool(rd.get("readable")) for rd in readings[name]]
            if k == 0:
                base_read[name] = now
            verdicts = [judge(rd, r.get("expect")) for rd, r in zip(readings[name], rows)]
            b = base_read[name]
            m = {"k": k, "readable": sum(now), "newly_read": sum(1 for x, y in zip(b, now) if y and not x), "lost": sum(1 for x, y in zip(b, now) if x and not y),
                 "correct": verdicts.count("correct"), "misread": verdicts.count("misread"), "unjudged": verdicts.count("unjudged")}
            per[name]["per_k"].append(m)
            for r, rd, v in zip(rows, readings[name], verdicts):
                if v == "misread":
                    detail.append({"set": name, "k": k, "id": r["id"], "text": r["text"], "expect": r.get("expect"), "got": clauses_of(rd)})
    for name in sets:
        per[name]["slope"] = slope([(m["k"], m["newly_read"]) for m in per[name]["per_k"]])
        per[name]["misread_total_over_k"] = sum(m["misread"] for m in per[name]["per_k"])
    ov = overlap(confirmations, sets["test"]) if "test" in sets else []
    per["test"]["overlap"] = ov
    per["test"]["verdict"] = "TEST_OVERLAPS_CONFIRMED" if ov else "TEST_DISJOINT_FROM_CONFIRMED"
    mp = None
    last = per["real"]["per_k"][-1]["newly_read"] if "real" in per and per["real"]["per_k"] else None
    if owner_minutes is not None and last:
        mp = owner_minutes / last
    res = {"schema": "verantyx.t8_measure/1", "placement": placement, "confirmations_total": len(confirmations), "steps_requested": steps, "steps_run": run, "steps_skipped_beyond_rows": skipped,
           "slope_formula": "sum((k-kbar)(y-ybar))/sum((k-kbar)^2), y = newly_read, over the steps run", "sets": per, "owner_minutes": owner_minutes,
           "minutes_per_newly_read_real_at_last_k": mp, "misread_detail": detail}
    with open(os.path.join(out, "curve.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(os.path.join(out, "curve.tsv"), "w", encoding="utf-8") as f:
        f.write("set\tk\tn\treadable\tnewly_read\tlost\tcorrect\tmisread\tunjudged\n")
        for name in sets:
            for m in per[name]["per_k"]:
                f.write("%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n" % (name, m["k"], per[name]["n"], m["readable"], m["newly_read"], m["lost"], m["correct"], m["misread"], m["unjudged"]))
        for name in sets:
            f.write("# slope\t%s\t%s\n" % (name, "null" if per[name]["slope"] is None else "%.6f" % per[name]["slope"]))
        f.write("# test_verdict\t%s\toverlap=%d\n" % (per["test"]["verdict"], len(ov)))
        f.write("# owner_minutes\t%s\n" % ("null" if owner_minutes is None else owner_minutes))
    return res


def _owner_minutes(path: Optional[str]) -> Optional[float]:
    if not path:
        return None
    txt = open(path, encoding="utf-8").read().strip()
    try:
        v = json.loads(txt)
    except ValueError:
        raise MeasureError("BAD_OWNER_MINUTES:" + path)
    if isinstance(v, dict):
        v = v.get("minutes")
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise MeasureError("BAD_OWNER_MINUTES:" + path)
    return float(v)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="W16-t8: confirmations -> newly read sentences curve")
    ap.add_argument("--placement", required=True)
    ap.add_argument("--confirmations", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--real", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", default=",".join(str(s) for s in DEFAULT_STEPS))
    ap.add_argument("--owner-minutes", default=None, dest="owner_minutes", help="a file with a number or {\"minutes\": number}; without it the field stays null (a human fills it in)")
    a = ap.parse_args(list(argv) if argv is not None else None)
    try:
        sets = {"train": load_jsonl(a.train), "test": load_jsonl(a.test), "real": load_jsonl(a.real)}
        res = measure(a.placement, load_jsonl(a.confirmations), sets, a.out, [int(x) for x in a.steps.split(",") if x.strip() != ""], _owner_minutes(a.owner_minutes))
    except MeasureError as exc:
        print(json.dumps({"kind": "unknown", "verdict": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"kind": "t8_measure", "out": a.out, "steps_run": res["steps_run"], "slopes": {n: res["sets"][n]["slope"] for n in SETS}, "test_verdict": res["sets"]["test"]["verdict"],
                      "misread_total": sum(res["sets"][n]["misread_total_over_k"] for n in SETS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Compile a project frame with the public API and print a deterministic JSON snapshot.

Usage:
  compile_snapshot.py --frame PATH --source LABEL --root ROOT   > snapshot.json
  compile_snapshot.py --compare-subsequence OLD.json NEW.json [--added-criteria C6 ...]

The snapshot lists {id, kind, slots, witness, sentence} for every compiled record.
Memory is created with a fixed clock, so two runs give byte-identical output.
The imported ``verantyx`` package must live under ROOT (checked; the path goes to stderr only).
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

NEW_SECTIONS = {"write_allowlist", "forbidden_actions", "conflict_precedence", "agent_settings"}


def snapshot(frame: str, source: str, root: str) -> int:
    root = os.path.realpath(root)
    sys.path.insert(0, root)
    import verantyx  # noqa: E402
    from verantyx.memory_frame import Memory  # noqa: E402
    from verantyx.project_frame import compile_frame, parse_frame  # noqa: E402

    where = os.path.realpath(verantyx.__file__)
    assert where.startswith(root + os.sep), f"verantyx imported from outside ROOT: {where}"
    print(f"verantyx={where}", file=sys.stderr)
    text = Path(frame).read_text(encoding="utf-8")
    spec = parse_frame(text, source=source)
    with tempfile.TemporaryDirectory() as tmp:
        mem = Memory(str(Path(tmp) / "m.jsonl"), now=lambda: "1970-01-01T00:00:00")
        comp = compile_frame(spec, mem)
        rows = [{"id": r["id"], "kind": r["kind"], "slots": r["slots"],
                 "witness": r.get("witness"), "sentence": r.get("sentence")} for r in comp.records]
    print(json.dumps(rows, sort_keys=True, indent=1, ensure_ascii=False))
    return 0


def _key(rec):
    return json.dumps([rec["kind"], rec["slots"]], sort_keys=True, ensure_ascii=False)


def _canon(rows):
    """Replace ids by content keys (kind+slots) and drop source line numbers."""
    by_id = {r["id"]: r for r in rows}
    out = []
    for r in rows:
        w = json.loads(json.dumps(r.get("witness")))
        if isinstance(w, dict):
            w.pop("line", None)
            for k in list(w):
                if k.endswith("_record_id") and w[k] in by_id:
                    w[k] = "ref:" + _key(by_id[w[k]])
            acc = w.get("acceptance")
            if isinstance(acc, dict):
                acc.pop("line", None)
        out.append({"kind": r["kind"], "slots": r["slots"], "witness": w, "sentence": r["sentence"]})
    return out


def compare(old_path: str, new_path: str, added_criteria) -> int:
    old = _canon(json.loads(Path(old_path).read_text(encoding="utf-8")))
    new = _canon(json.loads(Path(new_path).read_text(encoding="utf-8")))
    j = 0
    matched = [False] * len(new)
    for rec in old:
        while j < len(new) and new[j] != rec:
            j += 1
        if j == len(new):
            print(f"FAIL: an OLD record is not an ordered subsequence of NEW: {json.dumps(rec, ensure_ascii=False)[:300]}")
            return 1
        matched[j] = True
        j += 1
    extra = [n for n, m in zip(new, matched) if not m]
    # A declared added criterion contributes one GOAL record (carrying its criterion id) and
    # the ACCEPTANCE record that GOAL points at.
    added_goal_refs = {(n.get("witness") or {}).get("acceptance_record_id") for n in extra
                       if n["kind"] == "GOAL" and (n.get("witness") or {}).get("completion_criterion_id") in added_criteria}
    bad = []
    for rec in extra:
        w = rec.get("witness") or {}
        section = w.get("section")
        if section in NEW_SECTIONS:
            continue
        if section == "goal" and rec["kind"] == "GOAL" and w.get("completion_criterion_id") in added_criteria:
            continue
        if (section == "completion_criteria" and rec["kind"] == "ACCEPTANCE" and
                "ref:" + _key(rec) in added_goal_refs):
            continue
        bad.append(rec)
    print(f"old_records={len(old)} new_records={len(new)} added={len(extra)}")
    print("added_by_section=" + json.dumps(
        {s: sum(1 for r in extra if (r.get('witness') or {}).get('section') == s) for s in
         sorted({(r.get('witness') or {}).get('section') for r in extra})}, sort_keys=True))
    if bad:
        print("FAIL: added records outside the new sections / declared added criteria:")
        for b in bad:
            print("  " + json.dumps(b, ensure_ascii=False)[:300])
        return 1
    print("OK: OLD is an ordered subsequence of NEW; every added record comes from a new section or a declared added criterion")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame")
    ap.add_argument("--source")
    ap.add_argument("--root")
    ap.add_argument("--compare-subsequence", nargs=2, metavar=("OLD", "NEW"))
    ap.add_argument("--added-criteria", nargs="*", default=[])
    a = ap.parse_args()
    if a.compare_subsequence:
        return compare(a.compare_subsequence[0], a.compare_subsequence[1], set(a.added_criteria))
    if not (a.frame and a.source and a.root):
        ap.error("--frame, --source and --root are required")
    return snapshot(a.frame, a.source, a.root)


if __name__ == "__main__":
    raise SystemExit(main())

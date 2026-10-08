#!/usr/bin/env python3
"""T1 freeze (K313): the realizer's output on a fixed input, written as canonical JSON lines.

It uses ONLY the old API calls (realize_clause(c, style), realize_variants(c), realize_observed / observed_variants with no placement
argument, realize.conjugate), so the same script runs on the code before and after the forms table was cut out.
Run it with the environment variables VERA_PLACEMENT and VERA_REALIZE_FORMS unset.

  freeze_t1.py --out t1_before.jsonl [--limit N] [--conjugate-parity t1_conjugate_parity.txt]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

for _v in ("VERA_PLACEMENT", "VERA_REALIZE_FORMS"):
    if os.environ.get(_v):
        sys.exit("refusing to run with %s set (the freeze is made without it)" % _v)


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def load_inputs(limit: int | None):
    texts: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(src: str, text: str) -> None:
        if isinstance(text, str) and text and text not in seen:
            seen.add(text)
            texts.append((src, text))

    for line in (ROOT / "results/realize/realize_measure_2026-10-02.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            add("measure", json.loads(line).get("source_text"))
    b_texts: list[str] = []
    patterns = sorted((ROOT / "tests/event_cross/data").glob("sentences_ja*.jsonl")) + [ROOT / "tests/observe/data/seeds_ja.jsonl"]
    for path in patterns:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                add("b:" + path.name, row.get("text"))
                b_texts.append(row.get("text"))
    if limit:
        texts = texts[:limit] + [t for t in texts if t[0].startswith("b:")][:limit]
        # keep order, drop duplicates
        out, s = [], set()
        for src, t in texts:
            if t not in s:
                s.add(t)
                out.append((src, t))
        texts = out
    return texts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--conjugate-parity", default=None)
    args = ap.parse_args()

    from verantyx import event_cross, observe, realize, semantic_read, semantic_realize as SR, semantic_reader

    texts = load_inputs(args.limit)
    predicates: set[str] = set()
    rows = 0
    with open(args.out, "w", encoding="utf-8") as fh:
        for src, text in texts:
            try:
                view = semantic_reader.document_view({"w": text})
            except Exception as exc:  # recorded, not skipped
                fh.write(canon({"kind": "view_error", "src": src, "text": text, "error": type(exc).__name__}) + "\n")
                continue
            for c in view.clauses:
                if c.rule == "frame":
                    predicates.add(c.predicate)
                rec = {
                    "kind": "clause", "src": src, "text": text, "clause_id": c.id, "rule": c.rule,
                    "plain": SR.realize_clause(c, "plain").as_dict(),
                    "polite": SR.realize_clause(c, "polite").as_dict(),
                    "variants": [x.as_dict() for x in SR.realize_variants(c)],
                }
                fh.write(canon(rec) + "\n")
                rows += 1
            if src.startswith("b:"):
                try:
                    out = semantic_read.read(text, "ja")
                    got = event_cross.build_crosses(out)
                except Exception as exc:
                    fh.write(canon({"kind": "cross_error", "src": src, "text": text, "error": type(exc).__name__}) + "\n")
                    continue
                for cross in got.crosses:
                    key = observe.cell_key_of(cross)
                    center = dict(cross.center)
                    arms = {role: arm.to_dict() for role, arm in cross.arms.items()}
                    rule = cross.provenance.get("rule")
                    rec = {
                        "kind": "cross", "src": src, "text": text, "cell_key": key,
                        "canonical": SR.realize_observed(center, arms, "ja", cell_id=key, rule=rule).as_dict(),
                        "variants": [x.as_dict() for x in SR.observed_variants(center, arms, "ja", cell_id=key, rule=rule)],
                    }
                    fh.write(canon(rec) + "\n")
                    rows += 1
        # conjugate: every frame predicate that was read plus fixed extras, 8 combinations, by the OLD function
        extras = ["渡す", "歩く", "行く", "出て行く", "食べる", "する", "勉強する", "来る", "くる", "買う", "書く", "泳ぐ", "話す",
                  "待つ", "死ぬ", "飛ぶ", "読む", "帰る", "見る", "寝る"]
        for verb in sorted(predicates | set(extras)):
            for past, neg, polite in itertools.product((False, True), repeat=3):
                try:
                    val = realize.conjugate(verb, past=past, neg=neg, polite=polite)
                except Exception as exc:
                    val = "EXC:" + type(exc).__name__
                fh.write(canon({"kind": "conjugate", "verb": verb, "past": past, "neg": neg, "polite": polite, "value": val}) + "\n")
    print("inputs", len(texts), "clause+cross rows", rows, "predicates", len(predicates), file=sys.stderr)

    if args.conjugate_parity:
        fn = getattr(SR, "conjugate_by_style", None)
        lines, diff, total = [], 0, 0
        if fn is None:
            lines.append("conjugate_by_style is not defined (old code)")
        else:
            for verb in sorted(predicates | set(extras)):
                for past, neg, polite in itertools.product((False, True), repeat=3):
                    try:
                        old = realize.conjugate(verb, past=past, neg=neg, polite=polite)
                    except Exception as exc:
                        old = "EXC:" + type(exc).__name__
                    try:
                        new = fn(verb, "polite" if polite else "plain", past=past, neg=neg)
                    except Exception as exc:
                        new = "EXC:" + type(exc).__name__
                    total += 1
                    if old != new:
                        diff += 1
                        lines.append("DIFF %r past=%s neg=%s polite=%s old=%r new=%r" % (verb, past, neg, polite, old, new))
            lines.insert(0, "verbs %d combinations %d differences %d" % (len(predicates | set(extras)), total, diff))
        Path(args.conjugate_parity).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(lines[0], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

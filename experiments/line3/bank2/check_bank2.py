#!/usr/bin/env python3
"""Validate bank2.tsv against the corpora in experiments/line3/data/.

Rules = round-1 audited checker (check_audited.py) + round-2 rules:
  all rows      header, unique ids, audit in {valid, fixed}, no gold alternative inside the question
  intra2        corpus fulllead; evidence = subject#idx; evidence sentence has no title; every gold
                alternative is in the evidence sentence and in no sentence that contains the title;
                R2 items additionally: idx >= 2
  cross2        corpus s3000; evidence = A;B; B's title occurs in A's sentence; gold in B's sentence,
                not in A's sentence; R2 items additionally: B's title not in the question, A's title
                does not contain B's title, B not reused anywhere in cross2
                (round-1 items: these three are reported as WARN, since round 1 was audited before
                the rules existed)
  unans         gold empty; fulllead evidence subject#0, s3000 evidence = title; the subject is not
                mentioned in any other article of its corpus file
Writes check.txt next to this file. Exit 1 on any ERROR.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
FIELDS = ["id", "kind", "corpus", "subject", "question", "gold", "evidence", "audit"]
EXPECTED = {"intra2": 69, "cross2": 9, "unans": 50}
EXPECTED_UNANS = {"fulllead": 25, "s3000": 25}
GENERIC_GOLDS = {"こと", "もの", "日本"}


def sentences(text):
    return [p.strip() for p in text.split("。") if p.strip()]


def load_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    full = {r["title"]: sentences(r["text"]) for r in load_jsonl(DATA / "S300_fulllead.jsonl")}
    short = {r["title"]: r["sent"].strip() for r in load_jsonl(DATA / "S3000.jsonl")}
    errors, warns = [], []

    def err(rid, m):
        errors.append(f"{rid}: {m}")

    def warn(rid, m):
        warns.append(f"{rid}: {m}")

    with (HERE / "bank2.tsv").open(encoding="utf-8", newline="") as f:
        first = f.readline().rstrip("\r\n")
        if first != "#" + "\t".join(FIELDS):
            errors.append("header: unexpected")
        rows = list(csv.DictReader(f, fieldnames=FIELDS, delimiter="\t", quoting=csv.QUOTE_NONE))

    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        errors.append("ids: duplicate id")
    counts = Counter(r["kind"] for r in rows)
    for k, n in EXPECTED.items():
        if counts[k] != n:
            errors.append(f"count {k}: expected {n}, got {counts[k]}")
    ucount = Counter(r["corpus"] for r in rows if r["kind"] == "unans")
    for c, n in EXPECTED_UNANS.items():
        if ucount[c] != n:
            errors.append(f"count unans/{c}: expected {n}, got {ucount[c]}")

    b_uses = Counter(r["evidence"].split(";")[-1] for r in rows if r["kind"] == "cross2")
    multi_title = 0

    for r in rows:
        rid, kind, corpus, subj = r["id"], r["kind"], r["corpus"], r["subject"]
        is_r2 = rid.startswith("R2-")
        golds = [g for g in r["gold"].split("|") if g] if r["gold"] else []
        if not r["question"].strip():
            err(rid, "empty question")
        if r["audit"] not in ("valid", "fixed"):
            err(rid, f"bad audit value {r['audit']!r}")
        for g in golds:
            if g in r["question"]:
                err(rid, f"gold in question: {g!r}")
        if kind == "intra2":
            if corpus != "fulllead" or subj not in full:
                err(rid, "intra2 must be a fulllead subject")
                continue
            try:
                t, i = r["evidence"].rsplit("#", 1)
                i = int(i)
            except ValueError:
                err(rid, "evidence must be title#idx")
                continue
            if t != subj or not 0 <= i < len(full[subj]):
                err(rid, "evidence index invalid")
                continue
            ev = full[subj][i]
            if subj in ev:
                err(rid, "evidence sentence contains the title")
            if is_r2 and i < 2:
                err(rid, f"R2 intra2 evidence index {i} < 2")
            if not golds:
                err(rid, "empty gold")
            for g in golds:
                if g in GENERIC_GOLDS:
                    err(rid, f"generic gold {g!r}")
                if g not in ev:
                    err(rid, f"gold not in evidence: {g!r}")
                if any(subj in s and g in s for s in full[subj]):
                    err(rid, f"gold in a title sentence: {g!r}")
        elif kind == "cross2":
            if corpus != "s3000" or subj not in short:
                err(rid, "cross2 must be an s3000 subject")
                continue
            parts = r["evidence"].split(";")
            if len(parts) != 2 or parts[0] != subj or parts[1] not in short:
                err(rid, "evidence must be A;B with both in s3000")
                continue
            a, b = parts
            sa, sb = short[a], short[b]
            if b not in sa:
                err(rid, "B title not in A's sentence")
            if sum(1 for t in short if len(t) >= 2 and t != a and t in sa) >= 2:
                multi_title += 1
            if not golds:
                err(rid, "empty gold")
            for g in golds:
                if g in GENERIC_GOLDS:
                    err(rid, f"generic gold {g!r}")
                if g not in sb:
                    err(rid, f"gold not in B's sentence: {g!r}")
                if g in sa:
                    err(rid, f"gold in A's sentence: {g!r}")
            for cond, msg in ((b in r["question"], f"B title {b!r} occurs in the question"),
                              (b in a, f"A title contains B title {b!r}"),
                              (b_uses[b] > 1, f"B {b!r} used {b_uses[b]}x in cross2")):
                if cond:
                    (err if is_r2 else warn)(rid, msg)
        elif kind == "unans":
            if r["gold"]:
                err(rid, "unans gold must be empty")
            if corpus == "fulllead":
                if subj not in full or r["evidence"] != f"{subj}#0":
                    err(rid, "fulllead unans must be subject#0 of a fulllead subject")
                    continue
                others = [t for t, ss in full.items() if t != subj and any(subj in s for s in ss)]
            elif corpus == "s3000":
                if subj not in short or r["evidence"] != subj:
                    err(rid, "s3000 unans must be an s3000 subject")
                    continue
                others = [t for t, s in short.items() if t != subj and subj in s]
            else:
                err(rid, f"unknown corpus {corpus}")
                continue
            if others:
                warn(rid, f"subject mentioned in other articles: {others[:3]} (checked by hand)")
        else:
            err(rid, f"unknown kind {kind}")

    out = [
        f"bank: {HERE / 'bank2.tsv'}",
        f"corpora: {DATA}",
        f"Questions: {len(rows)}  (round 1: {sum(not i.startswith('R2-') for i in ids)}, round 2: {sum(i.startswith('R2-') for i in ids)})",
        f"Kinds: intra2={counts['intra2']}, cross2={counts['cross2']}, unans={counts['unans']}",
        f"Unans split: fulllead={ucount['fulllead']}, s3000={ucount['s3000']}",
        f"Audit: valid={sum(r['audit']=='valid' for r in rows)}, fixed={sum(r['audit']=='fixed' for r in rows)}",
        f"Cross2 A sentences with >=2 other S3000 titles: {multi_title}/{counts['cross2']}",
        f"Unique IDs: {len(set(ids))}/{len(ids)}",
        f"Constraint errors: {len(errors)}",
        f"Warnings: {len(warns)}",
    ]
    out += ["ERROR " + e for e in errors] + ["WARN " + w for w in warns]
    (HERE / "check.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

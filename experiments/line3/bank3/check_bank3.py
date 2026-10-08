#!/usr/bin/env python3
"""Mechanical validation of the AUDITED bank 3 (bank3_audited.tsv / bank3.tsv).

Adapted from the author's check3.py. Works in two places:
  bank2-author/out/        -> reads bank3_audited.tsv, corpora in ../
  experiments/line3/bank3/ -> reads bank3.tsv, corpora in ../data/
Writes check3_audited.txt (author workspace) or check.txt (experiments) next to itself.

Evidence convention (same as bank2): fulllead `title#i` with i 0-based over the lead split on 「。」
(empty pieces dropped); s3000 evidence is the bare article title (its first sentence).

ERROR rules
  all rows      header; unique ids; audit in {valid, fixed}; known kind/corpus; evidence resolves;
                no gold alternative inside the question (summary-choice: the gold is LETTER|option and the
                option is by design one of the choices in the question; checked separately)
  answerable    every gold alternative occurs verbatim in a cited evidence sentence
  two-facts     fulllead; exactly two distinct sentences of one article
  paraphrase    no shared character bigram (punctuation/space removed, subject removed) between the
                question and the evidence sentence that contains the gold (author's strict rule)
  unknown-word  subject surface occurs in the question and nowhere in either corpus file (text, sent, title)
  compare       s3000; two different articles; gold is one of the two titles; question has のうち/どちら;
                the year stated first in each sentence is decidable and the gold's year is the earlier one
                (all compare items ask 早い); neither title occurs in the question
  summary-choice  options A/B/C parsed from the question; gold letter|text matches; each option <= 25 chars
  unans-kind    gold empty
  bank          kind counts as expected; no two answerable rows share (gold sentence, gold)
INFO: letter distribution (summary-choice), answer position (compare), unknown-word alteration type,
      subjects reused, overlap with bank2 facts.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if (HERE / "bank3.tsv").exists() and (HERE.parent / "data" / "S3000.jsonl").exists():
    TSV, DATA, OUT = HERE / "bank3.tsv", HERE.parent / "data", HERE / "check.txt"
    BANK2 = HERE.parent / "bank2" / "bank2.tsv"
else:
    TSV, DATA, OUT = HERE / "bank3_audited.tsv", HERE.parent, HERE / "check3_audited.txt"
    BANK2 = Path("/Users/motonisihikoudai/Projects/vera-impl/wt/line3/experiments/line3/bank2/bank2.tsv")

HEADER = ["#id", "kind", "corpus", "subject", "question", "gold", "evidence", "notes", "audit"]
EXPECTED = {"two-facts": 14, "paraphrase": 20, "unknown-word": 18, "compare": 14,
            "summary-choice": 10, "unans-kind": 15}


def sentences(text: str) -> list[str]:
    return [p.strip() for p in text.split("。") if p.strip()]


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


full = {d["title"]: sentences(d["text"]) for d in load(DATA / "S300_fulllead.jsonl")}
s3 = {d["title"]: d["sent"].strip() for d in load(DATA / "S3000.jsonl")}
ALL_TEXT = "\n".join([s for ss in full.values() for s in ss] + list(s3.values()) + list(full) + list(s3))

errors: list[str] = []
info: list[str] = []
rows: list[dict] = []
with TSV.open(encoding="utf-8", newline="") as f:
    rd = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
    header = next(rd)
    if header != HEADER:
        errors.append(f"header mismatch: {header}")
    for n, vals in enumerate(rd, start=2):
        if not vals:
            continue
        if len(vals) != len(HEADER):
            errors.append(f"line {n}: {len(vals)} fields")
            continue
        rows.append(dict(zip(HEADER, vals)))

ids = [r["#id"] for r in rows]
if len(ids) != len(set(ids)):
    errors.append("duplicate ids")
counts = Counter(r["kind"] for r in rows)
if dict(counts) != EXPECTED:
    errors.append(f"kind counts {dict(counts)} != {EXPECTED}")


def resolve(r):
    out = []
    for e in [x for x in r["evidence"].split(";") if x]:
        if r["corpus"] == "s3000":
            if e not in s3:
                errors.append(f"{r['#id']}: s3000 evidence {e!r} not found")
                continue
            out.append((e, 0, s3[e]))
        else:
            m = re.match(r"^(.*)#(\d+)$", e)
            if not m or m.group(1) not in full or int(m.group(2)) >= len(full[m.group(1)]):
                errors.append(f"{r['#id']}: fulllead evidence {e!r} does not resolve")
                continue
            out.append((m.group(1), int(m.group(2)), full[m.group(1)][int(m.group(2))]))
    return out


def bigrams(text: str, subject: str) -> set[str]:
    text = text.replace(subject, "")
    text = re.sub(r"[\s、。，．・「」『』（）()［］【】〈〉《》!?！？：；…—\-]", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def first_year(s: str):
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})年", s)
    return int(m.group(1)) if m else None


facts = defaultdict(list)
letters = Counter()
cmp_pos = Counter()
uw_types = Counter()
for r in rows:
    rid, kind, q, gold = r["#id"], r["kind"], r["question"], r["gold"]
    if r["audit"] not in ("valid", "fixed"):
        errors.append(f"{rid}: audit={r['audit']!r}")
    if r["corpus"] not in ("fulllead", "s3000"):
        errors.append(f"{rid}: corpus {r['corpus']!r}")
    ev = resolve(r)
    golds = [g for g in gold.split("|") if g]
    if kind == "unans-kind":
        if gold:
            errors.append(f"{rid}: unans gold not empty")
        continue
    if kind == "summary-choice":
        letter, _, opt = gold.partition("|")
        marks = list(re.finditer(r"(?<!\S)([ABC])\.\s*", q))
        opts = {}
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(q)
            opts[m.group(1)] = q[m.end():end].strip()
        if set(opts) != {"A", "B", "C"}:
            errors.append(f"{rid}: options {sorted(opts)}")
        if opts.get(letter) != opt:
            errors.append(f"{rid}: gold {gold!r} does not match option {letter}")
        for L, t in opts.items():
            if len(t) > 25:
                errors.append(f"{rid}: option {L} has {len(t)} chars")
        letters[letter] += 1
        facts[(ev[0][:2] if ev else None, opt)].append(rid)
        continue
    for g in golds:
        if g in q:
            errors.append(f"{rid}: gold alternative {g!r} occurs in the question")
        if not any(g in s for _, _, s in ev):
            errors.append(f"{rid}: gold alternative {g!r} not verbatim in cited evidence")
    gsent = next(((t, i, s) for t, i, s in ev if golds and golds[0] in s), ev[0] if ev else None)
    if gsent:
        facts[(gsent[:2], golds[0] if golds else "")].append(rid)
    if kind == "two-facts":
        if r["corpus"] != "fulllead" or len(ev) != 2 or ev[0][:2] == ev[1][:2] or ev[0][0] != ev[1][0]:
            errors.append(f"{rid}: two-facts needs two distinct sentences of one fulllead article")
    elif kind == "paraphrase":
        ov = bigrams(q, r["subject"]) & bigrams(gsent[2], r["subject"]) if gsent else set()
        if ov:
            errors.append(f"{rid}: question/evidence bigram overlap {sorted(ov)}")
    elif kind == "unknown-word":
        surf = r["subject"]
        if surf not in q:
            errors.append(f"{rid}: subject surface {surf!r} not in question")
        if surf in ALL_TEXT:
            errors.append(f"{rid}: subject surface {surf!r} occurs in the corpus")
        title = ev[0][0] if ev else ""
        uw_types["corpus title verbatim inside the altered surface (suffix added)" if title in surf
                 else "corpus title not a substring of the question surface"] += 1
    elif kind == "compare":
        titles = [t for t, _, _ in ev]
        if r["corpus"] != "s3000" or len(set(titles)) != 2:
            errors.append(f"{rid}: compare needs two s3000 articles")
            continue
        if gold not in titles:
            errors.append(f"{rid}: gold not one of the two titles")
        if "のうち" not in q or "どちら" not in q:
            errors.append(f"{rid}: compare form")
        for t in titles:
            if t in q:
                errors.append(f"{rid}: title {t!r} occurs in the question")
        ys = {t: first_year(s) for t, _, s in ev}
        if None in ys.values() or len(set(ys.values())) != 2:
            errors.append(f"{rid}: years not decidable {ys}")
        elif min(ys, key=ys.get) != gold:
            errors.append(f"{rid}: gold is not the earlier one {ys}")
        # position of the answer among the two descriptions = order of evidence ids as authored
        cmp_pos["gold described first" if titles[0] == gold else "gold described second"] += 1

for k, v in facts.items():
    if len(v) > 1:
        errors.append(f"duplicate fact {k}: {v}")

# subjects reused / bank2 overlap
subj = Counter()  # articles used (from evidence), so altered unknown-word surfaces count as their article
for r in rows:
    for t in dict.fromkeys(e.rsplit("#", 1)[0] if r["corpus"] == "fulllead" else e
                           for e in r["evidence"].split(";")):
        subj[t] += 1
reused = {s: c for s, c in subj.items() if c > 1}
b2 = []
if BANK2.exists():
    with BANK2.open(encoding="utf-8") as f:
        for l in f:
            if l.startswith("#") or not l.strip():
                continue
            p = l.rstrip("\n").split("\t")
            b2.append((p[3], p[5]))
b2_subjects = {s for s, _ in b2}
b2_facts = []
for r in rows:
    if r["kind"] == "unans-kind" or r["kind"] == "summary-choice":
        continue
    for s, g in b2:
        if s == r["subject"].split(";")[0] or s == (r["evidence"].split("#")[0]):
            if g and any(x and (x in g or g in x) for x in r["gold"].split("|")):
                b2_facts.append(f"{r['#id']}~{s}:{g}")
                break
info.append(f"summary-choice gold letters: {dict(sorted(letters.items()))}")
info.append(f"compare answer position: {dict(cmp_pos)}")
info.append(f"unknown-word alteration: {dict(uw_types)}")
info.append(f"distinct articles: {len(subj)} for {len(rows)} rows; reused (>1 row): {len(reused)} -> "
            + ", ".join(f"{s}x{c}" for s, c in sorted(reused.items(), key=lambda x: -x[1])))
info.append(f"bank3 articles that are also bank2 subjects: {len(set(subj) & b2_subjects)}")
info.append(f"answerable bank3 items asking a fact already asked in bank2 (same subject, overlapping gold): "
            f"{len(b2_facts)} -> " + ", ".join(b2_facts))

lines = [f"Bank 3 audited check ({TSV.name}; corpora {DATA})",
         f"rows: {len(rows)}  kinds: " + ", ".join(f"{k}={counts[k]}" for k in EXPECTED),
         f"corpora: {dict(Counter(r['corpus'] for r in rows))}",
         f"audit: {dict(Counter(r['audit'] for r in rows))}"]
lines += ["INFO " + x for x in info]
lines.append(f"errors: {len(errors)}")
lines += ["ERROR " + e for e in errors]
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
sys.exit(1 if errors else 0)

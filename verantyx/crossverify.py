"""Check English claims against Japanese documents through the shared structure.

Each Japanese sentence is read into frames, its words replaced by their English
from a glossary, and compared with the frame of the English claim. No model."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from verantyx import en_frames as en
from verantyx.frames import Frame, canonical, read_all


def to_en(fr: Frame, gloss: Dict[str, str]) -> Frame:
    """Replace the Japanese words of a frame by their glossary English."""
    def m(w):
        if not w:
            return ""
        if w in gloss:
            return gloss[w]
        c = canonical(w)
        if c in gloss:
            return gloss[c]
        hits = [k for k in gloss if k and (k in w or w in k)]
        return gloss[max(hits, key=len)] if hits else w
    return Frame(m(fr.predicate), m(fr.agent), m(fr.patient), m(fr.recipient), fr.negated)


def swapped(a: tuple, b: tuple) -> bool:
    ra, rb = list(a[1:4]), list(b[1:4])
    return a[0] == b[0] and a[4] == b[4] and any(
        rb[x] == ra[y] and rb[y] == ra[x] and ra[x] != ra[y] and rb[3 - x - y] == ra[3 - x - y]
        for x in range(3) for y in range(x + 1, 3))


def compile_ja(text: str, gloss: Dict[str, str]) -> List[dict]:
    rows = []
    for s in (x for x in re.split(r"(?<=。)", text) if x.strip()):
        for fr in read_all(s):
            k = en.key(to_en(fr, gloss))
            if k:
                rows.append({"key": k, "sentence": s})
    return rows


def judge(rows: List[dict], claim: str) -> dict:
    k = en.key(en.read(claim))
    if not k:
        return {"verdict": "NOT_IN_DOCS", "why": "could not read the claim"}
    for r in rows:
        if r["key"] == k:
            return {"verdict": "SUPPORTED", "evidence": r["sentence"]}
    for r in rows:
        d = r["key"]
        if d[:4] == k[:4] and d[4] != k[4]:
            return {"verdict": "CONTRADICTED", "evidence": r["sentence"], "why": "negation"}
        if swapped(d, k):
            return {"verdict": "CONTRADICTED", "evidence": r["sentence"], "why": "roles reversed"}
    return {"verdict": "NOT_IN_DOCS"}


def verify(ja_text: str, gloss: Dict[str, str], claims: List[str]) -> List[dict]:
    rows = compile_ja(ja_text, gloss)
    return [dict(claim=c, **judge(rows, c)) for c in claims]

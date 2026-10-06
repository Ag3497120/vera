"""T1 space of the line-3 build: units, sentences, co-occurrence counts, word order.

Binding decisions (ops/decisions/2026-10-06_line3_faithful_build.md):
  I-01  three granularity tiers, each an independent space (I-16):
        RUN  = content runs + the strings between them,
        WORD = dictionary words (fugashi / unidic-lite short units),
        CHAR = single characters.
  I-02  NO centre is chosen at ingestion.  Stored: units, the sentences each unit
        occurs in (postings), same-sentence co-occurrence counts, word order.
  I-22 / N-15  function words and question words ARE units in all three tiers;
        punctuation and symbols are NOT units.
  I-06  initial energy ratio r0(u) = n(u) / N, an exact Fraction (L-02: no floats).

Local choices (new, listed in the T1 report):
  L-30  RUN content runs come from verantyx.lang.ja_content_runs (design 3.1 default);
        the text between consecutive runs (incl. runs that function dropped: digits,
        dates, stop words) is cut at every non-letter/number/mark character and each
        piece is a unit (design 3.1: "は", "の", "にある").
  L-31  Surfaces are kept as written (no Unicode normalisation, no case folding).
  L-32  A character is "letter-like" iff its Unicode category starts with L, N or M;
        everything else (punctuation P*, symbols S*, separators Z*, controls C*) is
        dropped in every tier.  A WORD token is a unit iff it contains at least one
        letter-like character; a unit is its whole surface (L-31).
  L-33  Sentence id = position in the input sequence.  Duplicate sentences are
        stored separately and each counts in N (no silent de-duplication).
  L-34  n(u,v) and p(u,v) are computed on demand from postings / stored word order
        (L-13) and never cached; the serialisation stores units, postings, sentence
        unit lists and r0 only.
  L-35  Serialisation = canonical JSON (sorted keys, compact, UTF-8, units sorted by
        code point; sorting is for byte identity, never to pick a winner).
  L-36  A sentence with no unit in a tier stays a sentence (counts in N).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.lang import ja_content_runs, strip_attribution

RUN, WORD, CHAR = "RUN", "WORD", "CHAR"
TIERS: Tuple[str, ...] = (RUN, WORD, CHAR)          # I-01
FORMAT = "line3.space.v1"

_tagger = None


def _get_tagger():
    global _tagger
    if _tagger is None:
        import fugashi
        _tagger = fugashi.Tagger()
    return _tagger


def _letterlike(ch: str) -> bool:                    # L-32
    return unicodedata.category(ch)[0] in "LNM"


def _has_letter(s: str) -> bool:
    return any(_letterlike(c) for c in s)


def _pieces(gap: str) -> List[str]:                  # L-30
    out, cur = [], []
    for ch in gap:
        if _letterlike(ch):
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def units_run(text: str) -> List[str]:
    """RUN tier (I-01, N-15, L-30): content runs and the strings between them, in order."""
    runs = ja_content_runs(text)
    out: List[str] = []
    pos = 0
    for r in runs:
        i = text.find(r, pos)
        if i < 0:                                    # cannot happen: runs are ordered substrings
            raise ValueError("content run not found in order: %r" % r)
        out.extend(_pieces(text[pos:i]))
        out.append(r)
        pos = i + len(r)
    out.extend(_pieces(text[pos:]))
    return out


def units_word(text: str) -> List[str]:
    """WORD tier (I-01, N-15, L-32): all dictionary short units except punctuation/symbols."""
    return [w.surface for w in _get_tagger()(text) if _has_letter(w.surface)]


def units_char(text: str) -> List[str]:
    """CHAR tier (I-01, N-15, L-32): every letter/number/mark character."""
    return [c for c in text if _letterlike(c)]


_SPLITTERS = {RUN: units_run, WORD: units_word, CHAR: units_char}


@dataclass(frozen=True)
class TierSpace:
    """One tier: sentence unit lists (word order, repeats kept) and postings."""
    name: str
    sentence_units: Tuple[Tuple[str, ...], ...]      # sid -> units in order of occurrence
    postings: Mapping[str, Tuple[int, ...]]          # unit -> sorted distinct sids  (I-02)

    @property
    def N(self) -> int:
        return len(self.sentence_units)

    def units(self) -> List[str]:
        return sorted(self.postings)                 # L-35: canonical order only

    def n(self, u: str) -> int:
        return len(self.postings[u])

    def r0(self, u: str) -> Fraction:                # I-06 exact
        return Fraction(len(self.postings[u]), self.N)

    def n_pair(self, u: str, v: str) -> int:         # same-sentence count (L-34)
        a, b = self.postings[u], self.postings[v]
        if len(a) > len(b):
            a, b = b, a
        return len(set(a).intersection(b))

    def p_pair(self, u: str, v: str) -> int:         # sentences where u's first occurrence precedes v's
        a, b = self.postings[u], self.postings[v]
        if len(a) > len(b):
            both = set(b).intersection(a)
        else:
            both = set(a).intersection(b)
        c = 0
        for sid in sorted(both):
            us = self.sentence_units[sid]
            if us.index(u) < us.index(v):
                c += 1
        return c

    def cooccurrence(self, u: str) -> Dict[str, int]:
        """v -> n(u,v) for every v sharing a sentence with u (v != u)."""
        out: Dict[str, int] = {}
        for sid in self.postings[u]:
            for v in set(self.sentence_units[sid]):
                if v != u:
                    out[v] = out.get(v, 0) + 1
        return out


@dataclass(frozen=True)
class Space:
    sentences: Tuple[Tuple[str, str], ...]           # sid -> (text, source)
    tiers: Mapping[str, TierSpace]

    @property
    def N(self) -> int:
        return len(self.sentences)

    def trace(self, tier: str, u: str) -> List[Tuple[int, str]]:
        """Every stored sentence (sid, text) that contains unit u (I-02 provenance)."""
        t = self.tiers[tier]
        return [(sid, self.sentences[sid][0]) for sid in t.postings[u]]

    def to_bytes(self) -> bytes:                     # L-35
        doc = {
            "format": FORMAT,
            "sentences": [{"sid": i, "text": t, "source": s} for i, (t, s) in enumerate(self.sentences)],
            "tiers": {},
        }
        for name in TIERS:
            t = self.tiers[name]
            doc["tiers"][name] = {
                "N": t.N,
                "sentence_units": [list(us) for us in t.sentence_units],
                "units": [{"u": u, "n": len(t.postings[u]), "r0": str(t.r0(u)),
                           "sids": list(t.postings[u])} for u in t.units()],
            }
        return json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()


def build_tier(name: str, texts: Sequence[str]) -> TierSpace:
    split = _SPLITTERS[name]
    su = tuple(tuple(split(t)) for t in texts)
    post: Dict[str, List[int]] = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us):                  # distinct, sid ascending by construction
            post.setdefault(u, []).append(sid)
    return TierSpace(name, su, {u: tuple(v) for u, v in post.items()})


def build_space(rows: Iterable[Mapping[str, str]]) -> Space:
    """rows: dicts with 'sent' (sentence) and optional 'source'.  No centre is chosen (I-02)."""
    sentences = tuple((r["sent"], r.get("source") or "") for r in rows)   # L-33
    texts = [strip_attribution(t) for t, _ in sentences]
    return Space(sentences, {n: build_tier(n, texts) for n in TIERS})


def load_jsonl(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_from_jsonl(path: str) -> Space:
    return build_space(load_jsonl(path))

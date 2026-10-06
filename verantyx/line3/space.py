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

T1b additions (new local labels):
  L-40  Every sentence has a `kind` in KINDS (base / memory_query / memory_answer /
        memory_user, design L-19) and a `source`.  Missing kind = "base"; an unknown
        kind raises ValueError (no silent coercion).  `Space.sentences` stays
        (text, source) pairs; kinds live in the parallel tuple `Space.kinds`.
  L-41  Append (`Space.append`, `TierSpace.append`) returns a NEW immutable object;
        old sids, old postings (as prefixes) and old sentence_units are unchanged, new
        sentences get sids N..N+k-1.  Appending == building from scratch on all
        sentences, byte for byte (tested).
  L-42  `postings_union(tier, units)` = sorted distinct sids of the union of the units'
        postings (M-1(c): a bundled state's quantity).  A unit not in the tier
        raises KeyError (no silent skip); an empty set gives ().
  L-43  FORMAT bumped to line3.space.v2 because every sentence entry now carries
        "kind"; the serialisation of the unchanged part is otherwise untouched.
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
FORMAT = "line3.space.v2"                           # L-43
BASE, MEMORY_QUERY, MEMORY_ANSWER, MEMORY_USER = "base", "memory_query", "memory_answer", "memory_user"
KINDS: Tuple[str, ...] = (BASE, MEMORY_QUERY, MEMORY_ANSWER, MEMORY_USER)   # L-40

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

    def append(self, texts: Sequence[str]) -> "TierSpace":     # L-41
        """New TierSpace with `texts` (already attribution-stripped) added as sids N.."""
        split = _SPLITTERS[self.name]
        new = tuple(tuple(split(t)) for t in texts)
        post: Dict[str, List[int]] = {}
        base = self.N
        for i, us in enumerate(new):
            for u in dict.fromkeys(us):
                post.setdefault(u, []).append(base + i)
        merged = dict(self.postings)
        for u, v in post.items():
            merged[u] = tuple(merged.get(u, ())) + tuple(v)
        return TierSpace(self.name, self.sentence_units + new, merged)

    def postings_union(self, units: Iterable[str]) -> Tuple[int, ...]:   # L-42
        """Combined sorted distinct sentence ids of the given units (M-1(c))."""
        acc: set = set()
        for u in units:
            acc.update(self.postings[u])
        return tuple(sorted(acc))

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
    kinds: Tuple[str, ...] = ()                      # sid -> kind (L-40); () = all base

    def __post_init__(self) -> None:
        if not self.kinds:
            object.__setattr__(self, "kinds", (BASE,) * len(self.sentences))
        if len(self.kinds) != len(self.sentences):
            raise ValueError("kinds and sentences differ in length")
        for k in self.kinds:
            if k not in KINDS:
                raise ValueError("unknown kind: %r" % (k,))

    @property
    def N(self) -> int:
        return len(self.sentences)

    def append(self, rows: Iterable[Mapping[str, str]]) -> "Space":     # L-41
        """New Space with the rows added after the existing sentences."""
        new, kinds = _rows(rows)
        if not new:
            return self
        texts = [strip_attribution(t) for t, _ in new]
        return Space(self.sentences + new,
                     {n: self.tiers[n].append(texts) for n in TIERS},
                     self.kinds + kinds)

    def postings_union(self, tier: str, units: Iterable[str]) -> Tuple[int, ...]:   # L-42
        return self.tiers[tier].postings_union(units)

    def trace(self, tier: str, u: str) -> List[Tuple[int, str]]:
        """Every stored sentence (sid, text) that contains unit u (I-02 provenance)."""
        t = self.tiers[tier]
        return [(sid, self.sentences[sid][0]) for sid in t.postings[u]]

    def to_bytes(self) -> bytes:                     # L-35
        doc = {
            "format": FORMAT,
            "sentences": [{"sid": i, "text": t, "source": s, "kind": self.kinds[i]}
                          for i, (t, s) in enumerate(self.sentences)],
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


def _rows(rows: Iterable[Mapping[str, str]]):
    rows = list(rows)
    sentences = tuple((r["sent"], r.get("source") or "") for r in rows)   # L-33
    kinds = tuple(r.get("kind") or BASE for r in rows)                    # L-40
    for k in kinds:
        if k not in KINDS:
            raise ValueError("unknown kind: %r" % (k,))
    return sentences, kinds


def build_space(rows: Iterable[Mapping[str, str]]) -> Space:
    """rows: dicts with 'sent' (sentence) and optional 'source'.  No centre is chosen (I-02)."""
    sentences, kinds = _rows(rows)
    texts = [strip_attribution(t) for t, _ in sentences]
    return Space(sentences, {n: build_tier(n, texts) for n in TIERS}, kinds)


def load_jsonl(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_from_jsonl(path: str) -> Space:
    return build_space(load_jsonl(path))

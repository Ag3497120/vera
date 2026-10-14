"""The corpus the loom reads (design 2, 3.6, 6.2): the three tiers of a Space built with the default function-word filter (T6v), the
adhesion table of each tier (foundation.adhesions_of_space), and the shas that go into a run's header.

The loom only READS the corpus.  The bytes come in through the sandbox (mcp.Sandbox) or are handed in by the caller; this module
opens no file itself.  The build is deterministic (the same bytes give the same Space, object for object), so a corpus is cached by
the sha256 of its bytes for the life of the process (a pure cache: no run state is stored here).

Nothing here is hash-order dependent: every listing is sorted by sid / tier order / surface.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Tuple

from verantyx.line3 import foundation as fd
from verantyx.line3 import granularity as gr
from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp

TIERS: Tuple[str, ...] = sp.TIERS
_CACHE: Dict[str, "Corpus"] = {}


def parse_rows(data: bytes) -> List[dict]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


class Corpus:
    def __init__(self, data: bytes) -> None:
        self.corpus_sha = hashlib.sha256(data).hexdigest()
        self.space: sp.Space = sp.build_space(parse_rows(data))
        self.adhesion: Dict[str, fd.Adhesion] = fd.adhesions_of_space(self.space, TIERS)
        self.space_sha = self.space.sha256()
        self.adhesion_sha: Dict[str, str] = {t: self.adhesion[t].sha256() for t in TIERS}
        self.seats_sha = fd.seats_sha()
        self._weights: Dict[str, pl.Weights] = {}
        self._spans: Optional[gr.SpanIndex] = None
        self._follow: Dict[str, Dict[int, Dict[Tuple[int, int], str]]] = {}

    def rebased(self, data: bytes) -> "Corpus":
        """The corpus of `data` when `data` differs from the bytes this corpus was built from ONLY in keys the space does not read (a row flag such as `weave_refused`, `clause_at`): the space, the adhesion
        tables and every cache are shared, `corpus_sha` is the sha256 of `data`.  Not a build: the rows of `data` must give the same (sent, source, kind) as the rows of this corpus (checked)."""
        a = parse_rows(data)
        if len(a) != self.space.N or any((r["sent"], r.get("source") or "", r.get("kind") or "base") != (self.space.sentences[i][0], self.space.sentences[i][1], self.space.kinds[i]) for i, r in enumerate(a)):
            raise ValueError("rebased: the rows differ in what the space reads")
        c = object.__new__(Corpus)
        c.__dict__.update(self.__dict__)
        c.corpus_sha = hashlib.sha256(data).hexdigest()
        return c

    @staticmethod
    def load(data: bytes) -> "Corpus":
        sha = hashlib.sha256(data).hexdigest()
        c = _CACHE.get(sha)
        if c is None:
            c = _CACHE[sha] = Corpus(data)
        return c

    # -- tiers ----------------------------------------------------------------------------------------------------
    def tier(self, name: str) -> sp.TierSpace:
        return self.space.tiers[name]

    def weights(self, name: str) -> pl.Weights:
        """A plain placement.Weights(tier): a pure cache of (n, p) per ordered pair, shared by every stability check."""
        w = self._weights.get(name)
        if w is None:
            w = self._weights[name] = pl.Weights(self.tier(name))
        return w

    def postings(self, tier: str, surface: str) -> Optional[Tuple[int, ...]]:
        return self.tier(tier).postings.get(surface)

    def tiers_holding(self, surface: str) -> List[str]:
        return [t for t in TIERS if surface in self.tier(t).postings]

    # -- sentences -------------------------------------------------------------------------------------------------
    @property
    def n_sentences(self) -> int:
        return self.space.N

    def sentence(self, sid: int) -> Dict[str, object]:
        text, source = self.space.sentences[sid]
        return {"sid": sid, "source": source, "text": text}

    def units_of(self, sid: int) -> Dict[str, List[str]]:
        return {t: list(self.tier(t).sentence_units[sid]) for t in TIERS}

    # -- the grammar layer's evidence for batch seating (LOOM-batch, L-LOOM-125) -------------------------------------------------
    def particle_after(self, tier: str, sid: int) -> Dict[Tuple[int, int], str]:
        """{(start, end) of a unit of the sentence: the particle that immediately follows it}, from the adhesion RECORDS of the tier
        (foundation.adhesion_records, i.e. the grammar layer's evidence).  NB: the で of 「である」 IS a particle there (the corpus holds で + ある as
        two tokens and the evidence attaches that で to the noun before it: 歴史観である -> 観 followed by で), so a copula で comes back as an arm particle
        like any other; 「です」 is one token and attaches nothing.  This was wrongly said the other way round in LOOM-batch.  The
        key is the unit's span in the attribution-stripped sentence (`spans().spans(tier, sid)`), so a unit that occurs twice in a
        sentence is told apart.  Every particle of the foundation ladder is in it, は too; the caller keeps the six arms.  Built once per
        tier from the sorted evidence; {} for a sentence without any (a memory sentence, a sentence with no adhesion)."""
        idx = self._follow.get(tier)
        if idx is None:
            idx = {}
            adh = self.adhesion[tier]
            for (u, p) in adh.counts:                       # sorted at construction (foundation.Adhesion): no hash-order dependence
                for r in adh.evidence(u, p):
                    idx.setdefault(r.sid, {})[(r.start, r.end)] = p
            self._follow[tier] = idx
        return idx.get(sid, {})

    # -- the stretch of a sentence between two units (LOOM-span, `weave_span`) --------------------------------------------------------
    def span_gaps(self, tier: str, sid: int, i0: int, i1: int) -> Tuple[bool, List[str]]:
        """(surfaces_ok, gaps) for units i0..i1 (inclusive indexes into `sentence_units[sid]` of the tier).  gaps[k] is the text between unit
        i0 + k and unit i0 + k + 1 in the attribution-stripped sentence, reduced to its LETTERS (`space._has_letter`: punctuation, quotes,
        spaces and 「・」 are dropped: the loom never writes them.  NB the T9 normaliser does NOT ignore punctuation: it drops only whitespace and 「・」/「·」, L-LOOM-144).  What is left is "" (the units touch)
        or the function words the unit filter took out between them (の, を, は, という, として, ...).  surfaces_ok: every unit's surface is
        the slice of the sentence its span names (it is, for a space built by `space.build_space`; kept as a check, not assumed)."""
        idx = self.spans()
        units = self.tier(tier).sentence_units[sid]
        sps = idx.spans(tier, sid)
        text = idx.text(sid)
        ok = all(text[sps[j][0]:sps[j][1]] == units[j] for j in range(i0, i1 + 1))
        gaps = ["".join(ch for ch in text[sps[j][1]:sps[j + 1][0]] if sp._has_letter(ch)) for j in range(i0, i1)]
        return ok, gaps

    # -- joins (F2, display only; design 3.6) -------------------------------------------------------------------------
    def spans(self) -> gr.SpanIndex:
        if self._spans is None:
            self._spans = gr.SpanIndex(self.space)
        return self._spans

    def join_attested(self, tier: str, a: str, b: str) -> Optional[List[int]]:
        """[sid, start, end] of the first sentence (by sid) that holds unit `a` immediately followed by unit `b` in the tier
        (touching, or separated only by characters no tier keeps: F2 step 2), else None.  Never a gate and never a score."""
        t = self.tier(tier)
        pa, pb = t.postings.get(a), t.postings.get(b)
        if pa is None or pb is None:
            return None
        both = sorted(set(pa).intersection(pb))
        idx = self.spans()
        for sid in both:
            us = t.sentence_units[sid]
            sps = idx.spans(tier, sid)
            text = idx.text(sid)
            for i in range(len(us) - 1):
                if us[i] == a and us[i + 1] == b and not sp._has_letter(text[sps[i][1]:sps[i + 1][0]]):
                    return [sid, sps[i][0], sps[i + 1][1]]
        return None

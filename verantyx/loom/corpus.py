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

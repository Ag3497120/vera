"""Object-for-object comparison of two corpora (the check mode and the differential tests): an IncCorpus against the plain `Corpus` of the same bytes."""
from __future__ import annotations

from typing import Any


def check_corpora(a: Any, b: Any, deep: bool = False) -> None:
    """Raises AssertionError at the first difference.  `deep` also walks the lazily built caches both corpora hold."""
    assert a.corpus_sha == b.corpus_sha, "corpus_sha"
    sa, sb = a.space, b.space
    assert sa.sentences == sb.sentences and sa.kinds == sb.kinds, "sentences / kinds"
    assert list(sa.tiers) == list(sb.tiers), "tier names"
    for name in sa.tiers:
        ta, tb = sa.tiers[name], sb.tiers[name]
        assert ta.sentence_units == tb.sentence_units, "sentence_units " + name
        assert list(ta.postings.items()) == list(tb.postings.items()), "postings (with their order) " + name
        assert ta.unit_filter is tb.unit_filter or (ta.unit_filter is None) == (tb.unit_filter is None), "unit_filter " + name
    assert sa.to_bytes() == sb.to_bytes(), "space bytes"
    assert a.space_sha == b.space_sha, "space_sha"
    assert a.seats_sha == b.seats_sha, "seats_sha"
    assert list(a.adhesion) == list(b.adhesion), "adhesion tiers"
    for t in a.adhesion:
        x, y = a.adhesion[t], b.adhesion[t]
        assert list(x.counts.items()) == list(y.counts.items()), "adhesion counts (with their order) " + t
        assert list(x._ev.items()) == list(y._ev.items()), "adhesion evidence (with its order) " + t
        assert list(x._rows.items()) == list(y._rows.items()), "adhesion rows (with their order) " + t
        assert x.sha256() == y.sha256(), "adhesion sha " + t
    assert a.adhesion_sha == b.adhesion_sha, "adhesion_sha"
    if deep:
        for t in a.adhesion:
            assert a.particle_after(t, 0) == b.particle_after(t, 0), "particle_after " + t
            for sid in range(sa.N):
                assert a.particle_after(t, sid) == b.particle_after(t, sid), "particle_after %s %d" % (t, sid)
        for sid in range(sa.N):
            for t in sa.tiers:
                assert a.spans().spans(t, sid) == b.spans().spans(t, sid), "spans %s %d" % (t, sid)
            assert a.spans().text(sid) == b.spans().text(sid), "text %d" % sid

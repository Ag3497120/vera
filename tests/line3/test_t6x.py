"""T6x tests: read_rule="query_share_crosses" (M-2 group 2 read as an option; L-160..), the official answer
object (path words + the sentences they trace to, centre as reference), and byte-identity of everything else
under the defaults."""
import hashlib
import json

import pytest

from verantyx.line3 import cycle as cy
from verantyx.line3 import placement as pl
from verantyx.line3 import readout as ro
from verantyx.line3.placement import from_cross
from test_variants import TOY2, tier, h

# hashes recorded with the code of the T6w commit + decisions commit (before T6x), default options
DEFAULT_BEFORE = [
    "54def934f82bee0583fd5df0c2a8ecc56d338f84503b68e7addcad8a30972ff0",   # ask (E,F)
    "24f99c9d517ddd6bbe3679cca8245b6f2cb6d29dbc20076089f2af95e722fc26",   # thought_obj (E,F)
    "dd80c8f8c87eb1242df14ca31ea164d37b9741ff7e5f016a90af08d4188de624",   # old answer fields (E,F)
    "44c03d28999b7635f38b28869b607eed7a804b367d2d2615e38755c21b710214",   # ask (A,B,C)
    "fd03ec346597c70b8d40ef3211991158d9601707aa428a721b6fc1802cd3a526",
    "ad6c97f3b3d8d68d3d0eec6a6494abc5fe6deb4334a5e3cf4b1c024df03d8b7a",
    "1bf1d8190e588f4ecb194ecbf43b47225e0fb8e448ddc9c59f9150db3718d4c8",   # ask (Z,)
    "21c884a350eea0d24a207bb87a0e360168fc5b51516fe1cb513fbaf8eb688933",   # ask (C,)
    "6bd650e2f5a0248f062b7363233b9cf331de6ae57e86f8a2d327d4512790d1b6",
    "80996ca5b29327ab49bdc89b0544130a6b49b549135f5de80f707c04b6be6eea",
    "1cc5734d8c205197b27103fb58ee86f38108593dae513fbddcbd4da67e5a7302",   # ask (D,)
    "2da7ccc3a9b25e4e4ae289e975fe9f50f69b39609b5dd2926294e083d125447a",
    "71f381e3eb7f9816a55f1d1099e159298f32eff8d5a237f75cdfb2db7396b5de",
]
QS = (("E", "F"), ("A", "B", "C"), ("Z",), ("C",), ("D",))


def _sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _old_answer_fields(o):
    old = {k: o[k] for k in ("form", "verdict", "listed", "too_many", "centre", "paths")}
    strip = lambda ps: [{k: v for k, v in p.items() if k != "edges"} for p in ps]
    old["items"] = [{k: (strip(v) if k == "paths" else v) for k, v in it.items() if k != "source_sids"} for it in o["items"]]
    old["paths"] = old["items"][0]["paths"] if old["paths"] is not None else None
    old["form"] = "centre_paths"
    return old


def test_defaults_are_byte_identical_except_the_answer_object_additions():
    t = tier(TOY2)
    P = pl.Placer(t)
    out = []
    for q in QS:
        r = cy.ask_tier(t, "", P, units=q)
        out.append(h(r.to_bytes()))
        if r.candidates:
            a = ro.read_out_result(t, r)
            out.append(_sha(a.thought_obj()))
            out.append(_sha(_old_answer_fields(a.answer_obj())))
    assert out == DEFAULT_BEFORE


def _holds(p):
    us = {c for c in from_cross(p.cross) if c is not None}
    for tw in p.twin_sets:
        us.update(tw)
    return us


def test_query_share_crosses_is_v1_plus_the_crosses_sharing_a_sentence_with_a_query_unit():
    t = tier(TOY2)
    P = pl.Placer(t)
    f = cy.TierFacts(t)
    extra_seen = False
    for q in (("E", "F"), ("A",), ("G",), ("C", "G"), ("Z",), ("D",)):
        r1 = cy.ask_tier(t, "", P, units=q, facts=f, read_rule="query_crosses")
        r2 = cy.ask_tier(t, "", P, units=q, facts=f, read_rule="query_share_crosses")
        v1, v2 = set(r1.plan.read), set(r2.plan.read)
        assert v1 <= v2
        for s in v2 - v1:
            extra_seen = True
            us = _holds(P.cross_for(s))
            assert not (us & set(q))                                           # not a V1 cross
            assert any(f.npair(x, u) > 0 for x in q for u in us)               # but shares a sentence
        for s in set(t.units()) - v2:
            us = _holds(P.cross_for(s))
            assert not (us & set(q)) and not any(f.npair(x, u) > 0 for x in q for u in us)
        assert [g for g, _ in r2.plan.order_groups] == ["contains_query_unit", "shares_sentence_with_query_unit"]
        assert [g for g, _ in r1.plan.order_groups] == ["contains_query_unit"]
        assert r2.plan.partial == bool(r2.plan.unread)
    assert extra_seen


def test_query_share_crosses_reads_nothing_for_a_query_unit_that_is_not_in_the_space():
    t = tier(TOY2)
    r = cy.ask_tier(t, "", pl.Placer(t), units=("Z",), read_rule="query_share_crosses")
    assert r.plan.read == () and r.verdict == cy.UNKNOWN_NO_EVIDENCE


def test_read_rule_is_validated_and_not_combinable_with_amount():
    t = tier(TOY2)
    P = pl.Placer(t)
    with pytest.raises(ValueError):
        cy.ask_tier(t, "", P, units=("E",), read_rule="nonsense")
    with pytest.raises(ValueError):
        cy.ask_tier(t, "", P, units=("E",), read_rule="query_share_crosses", amount=3)


def test_answer_object_is_path_words_with_source_sentences_and_the_centre_as_reference():
    t = tier(TOY2)
    P = pl.Placer(t)
    seen = 0
    for q in QS:
        r = cy.ask_tier(t, "", P, units=q)
        if not r.candidates:
            continue
        a = ro.read_out_result(t, r)
        o = a.answer_obj()
        assert o["form"] == "path_words"
        if a.verdict == cy.ANSWER:
            seen += 1
            it = a.items[0]
            assert o["answer"] == {"path_words": [p.text for p in it.paths], "source_sids": list(it.source_sids),
                                   "reference_centre": it.centre}
            assert o["centre"] == it.centre
        else:
            assert o["answer"] is None
        used = set()
        for it, io in zip(a.items, o["items"]):
            for p, po in zip(it.paths, io["paths"]):
                # every step is (attached query unit | previous word, word) with the sentences that hold both
                assert [e["to"] for e in po["edges"]][-1] == p.words[-1]
                for e in po["edges"]:
                    want = [sid for sid, us in enumerate(t.sentence_units) if e["from"] in us and e["to"] in us]
                    assert e["sids"] == want
                    used.update(e["sids"])
                # every step ends at a path word (a leg's first word of a section without an attached query
                # unit has no opening step: it is only the start of the first step)
                assert {e["to"] for e in po["edges"]} <= set(p.words)
        assert {int(k) for k in o["sentences"]} == used
        for k, v in o["sentences"].items():
            assert v == "".join(t.sentence_units[int(k)])
    assert seen


def test_answer_object_is_deterministic():
    t = tier(TOY2)
    r = cy.ask_tier(t, "", pl.Placer(t), units=("E", "F"))
    a = ro.read_out_result(t, r)
    assert json.dumps(a.answer_obj(), sort_keys=True) == json.dumps(ro.read_out_result(t, r).answer_obj(), sort_keys=True)

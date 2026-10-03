"""W3-a4 (docs section 12.17): the frame-cover rule of ``coarse_types._apply_gen_frame``.  Evidence rows are
synthetic: (arm, source, type, n, base)."""
import pytest

from verantyx import coarse_types as ct

GEN = "generated:gpt-6-luna:low"
COMM = {"が|PERSON": 30, "を|INFO_LANGUAGE": 40}            # sig が を -> P_COMMUNICATE
MOVE = {"が|PERSON": 20, "へ|PLACE": 30, "から|PLACE": 10}   # sig が へ から -> P_MOVE


def cfg(**kw):
    c = dict(ct.DEFAULT_CONFIG)
    c.update({"rd_min_total": 20, "rd_particle_min": 5, "rd_particle_share_pct": 10,
              "rd_type_share_pct": 50, "rd_min_sources": 2, "frame_decides": False,
              "slot_min": 5, "slot_share_pct": 10})
    c.update(kw)
    return c


def rd_rows(src, counts):
    base = sum(counts.values())
    return [("role_distribution", src, k, n, base) for k, n in counts.items()]


def gen_rows(ptype, slots):
    """slots: 'particle|NOUNTYPE' strings."""
    rows = [("gen_frame", GEN, ptype, 1, None)]
    rows += [("gen_frame_slot", GEN, s, 1, None) for s in slots]
    return rows


def both(counts):
    return rd_rows("jawiki", counts) + rd_rows("codex:narrative", counts)


MOVE_FRAME_NO_HE = ["が|PERSON", "から|PLACE", "に|PLACE"]
MOVE_FRAME_NO_HE_NO_NI = ["が|PERSON", "から|PLACE"]


def test_the_default_is_the_old_rule_and_the_old_answer_has_no_cover_key():
    assert ct.DEFAULT_CONFIG["frame_cover_rule"] == "all9"
    ev = both(MOVE) + gen_rows("P_MOVE", MOVE_FRAME_NO_HE)
    d = ct.decide_word(ev, cfg())
    assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"
    # a config with no key at all behaves like the default
    c = cfg()
    del c["frame_cover_rule"]
    assert ct.decide_word(ev, c) == d
    ok = both(COMM) + gen_rows("P_COMMUNICATE", ["が|PERSON", "を|INFO_LANGUAGE"])
    d = ct.decide_word(ok, cfg())
    assert d["origin"] == "direct" and "cover" not in d["arms"]["gen_frame"]


@pytest.mark.parametrize("rule", ["he_by_ni_place", "k62_he_by_ni_place"])
def test_he_is_covered_by_ni_place_and_only_by_it(rule):
    ev = both(MOVE) + gen_rows("P_MOVE", MOVE_FRAME_NO_HE)
    d = ct.decide_word(ev, cfg(frame_cover_rule=rule))
    assert (d["state"], d["origin"], d["tops"]) == ("DECIDED", "direct", ["P_MOVE"])
    assert d["by"] == ["gen_frame", "role_distribution@codex:narrative", "role_distribution@jawiki"]
    cover = d["arms"]["gen_frame"]["cover"]
    assert cover["he_by_ni_place"] == ["role_distribution@codex:narrative", "role_distribution@jawiki"]
    assert cover["ignored"] == {}
    # no ni|PLACE row: he is not waived
    ev = both(MOVE) + gen_rows("P_MOVE", MOVE_FRAME_NO_HE_NO_NI)
    d = ct.decide_word(ev, cfg(frame_cover_rule=rule))
    assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"
    assert "cover" not in d["arms"]["gen_frame"]
    # a ni row with another noun type does not waive he
    ev = both(MOVE) + gen_rows("P_MOVE", ["が|PERSON", "から|PLACE", "に|PERSON"])
    assert ct.decide_word(ev, cfg(frame_cover_rule=rule))["origin"] == "estimated"


def test_a_frame_that_has_he_needs_no_waiver_and_is_not_marked_as_waived():
    ev = both(MOVE) + gen_rows("P_MOVE", ["が|PERSON", "から|PLACE", "へ|PLACE"])
    d = ct.decide_word(ev, cfg(frame_cover_rule="k62_he_by_ni_place"))
    assert d["origin"] == "direct"
    assert d["arms"]["gen_frame"]["cover"]["he_by_ni_place"] == []


def test_particles_outside_k62_are_ignored_by_the_k62_rule_only():
    more = dict(COMM, **{"と|PERSON": 25})
    assert "と" not in ct.k62_particles()
    ev = both(more) + gen_rows("P_COMMUNICATE", ["が|PERSON", "を|INFO_LANGUAGE"])
    d = ct.decide_word(ev, cfg(frame_cover_rule="k62_he_by_ni_place"))
    assert d["origin"] == "direct"
    assert d["arms"]["gen_frame"]["cover"]["ignored"] == {
        "role_distribution@codex:narrative": ["と"], "role_distribution@jawiki": ["と"]}
    assert d["arms"]["gen_frame"]["cover"]["he_by_ni_place"] == []
    for rule in ("all9", "he_by_ni_place"):
        d = ct.decide_word(ev, cfg(frame_cover_rule=rule))
        assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"


def test_a_k62_particle_missing_from_the_frame_is_not_covered_under_every_rule():
    ev = both(COMM) + gen_rows("P_COMMUNICATE", ["が|PERSON"])              # no を
    for rule in ct.FRAME_COVER_RULES:
        d = ct.decide_word(ev, cfg(frame_cover_rule=rule))
        assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"
        assert "cover" not in d["arms"]["gen_frame"]


def test_an_unknown_rule_is_a_value_error():
    ev = both(COMM) + gen_rows("P_COMMUNICATE", ["が|PERSON", "を|INFO_LANGUAGE"])
    with pytest.raises(ValueError, match="UNKNOWN_FRAME_COVER_RULE:nope"):
        ct.decide_word(ev, cfg(frame_cover_rule="nope"))


def test_the_other_gates_do_not_depend_on_the_rule():
    for rule in ct.FRAME_COVER_RULES:
        c = cfg(frame_cover_rule=rule)
        # a vote for another type: disagrees
        ev = both(COMM) + gen_rows("P_MOVE", ["が|PERSON", "を|INFO_LANGUAGE"])
        d = ct.decide_word(ev, c)
        assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "DISTRIBUTION_DISAGREES"
        # rd_min_sources
        one = rd_rows("jawiki", COMM) + gen_rows("P_COMMUNICATE", ["が|PERSON", "を|INFO_LANGUAGE"])
        assert ct.decide_word(one, dict(c, rd_min_sources=2))["origin"] == "estimated"
        assert ct.decide_word(one, dict(c, rd_min_sources=2))["arms"]["gen_frame"]["why"] is None
        assert ct.decide_word(one, dict(c, rd_min_sources=1))["origin"] == "direct"
        # no distribution at all
        assert ct.decide_word(gen_rows("P_COMMUNICATE", ["が|PERSON"]), c)["origin"] == "estimated"

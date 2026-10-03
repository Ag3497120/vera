"""W3-a3: the decision of a word with the new arms (docs sections 12.4-12.7).  Evidence rows are
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


def gen_rows(ptype, parts):
    rows = [("gen_frame", GEN, ptype, 1, None)]
    rows += [("gen_frame_slot", GEN, "%s|PERSON" % p, 1, None) for p in parts]
    return rows


def test_upgrade_to_direct_needs_every_registered_condition_and_names_its_arms():
    ev = rd_rows("jawiki", COMM) + rd_rows("codex:narrative", COMM) + gen_rows("P_COMMUNICATE", ["が", "を", "と"])
    d = ct.decide_word(ev, cfg())
    assert (d["state"], d["origin"], d["tops"]) == ("DECIDED", "direct", ["P_COMMUNICATE"])
    assert d["by"] == ["gen_frame", "role_distribution@codex:narrative", "role_distribution@jawiki"]
    for k in ("role_distribution@jawiki", "role_distribution@codex:narrative", "gen_frame"):
        assert d["arms"][k]["met"] is True
    assert d["arms"]["role_distribution@jawiki"]["sig"] == ["が", "を"]
    assert d["estimate_basis"] is None


def test_the_distribution_never_decides_alone_and_says_why():
    d = ct.decide_word(rd_rows("jawiki", COMM) + rd_rows("codex:code", COMM), cfg())
    assert d["state"] == "UNPLACED" and d["tops"] == [] and d["by"] == []
    for a in d["arms"].values():
        assert a["threshold_met"] is True and a["met"] is False and a["why"] == "AGREEMENT_ONLY"
        assert a["top"] == ["P_COMMUNICATE"]


def test_a_generated_frame_without_any_distribution_stays_an_estimate_generated():
    d = ct.decide_word(gen_rows("P_COMMUNICATE", ["が", "を"]), cfg())
    assert (d["state"], d["origin"], d["estimate_basis"], d["by"]) == ("DECIDED", "estimated", "generated", ["gen_frame"])
    assert d["arms"]["gen_frame"]["why"] is None and d["arms"]["gen_frame"]["met"] is True


def test_a_distribution_that_names_another_type_is_distribution_disagrees_and_stays_an_estimate():
    ev = rd_rows("jawiki", MOVE) + rd_rows("codex:narrative", MOVE) + gen_rows("P_COMMUNICATE", ["が", "を", "へ", "から"])
    d = ct.decide_word(ev, cfg())
    assert (d["origin"], d["tops"], d["by"]) == ("estimated", ["P_COMMUNICATE"], ["gen_frame"])
    assert d["arms"]["gen_frame"]["why"] == "DISTRIBUTION_DISAGREES"
    assert d["arms"]["role_distribution@jawiki"]["met"] is False        # the distribution did not decide
    # one source that agrees and one that disagrees: still a disagreement, never a MULTIPLE
    ev = rd_rows("jawiki", COMM) + rd_rows("codex:narrative", MOVE) + gen_rows("P_COMMUNICATE", ["が", "を", "へ", "から"])
    d = ct.decide_word(ev, cfg(rd_min_sources=1))
    assert d["state"] == "DECIDED" and d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "DISTRIBUTION_DISAGREES"


def test_a_frame_that_misses_a_significant_particle_is_not_covered_and_stays_an_estimate():
    ev = rd_rows("jawiki", COMM) + rd_rows("codex:narrative", COMM) + gen_rows("P_COMMUNICATE", ["が"])   # no を
    d = ct.decide_word(ev, cfg())
    assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"
    # と is significant in the distribution and absent from the frame: also not covered (all nine count)
    more = dict(COMM, **{"と|PERSON": 25})
    ev = rd_rows("jawiki", more) + rd_rows("codex:narrative", more) + gen_rows("P_COMMUNICATE", ["が", "を"])
    d = ct.decide_word(ev, cfg())
    assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"
    ev = rd_rows("jawiki", more) + rd_rows("codex:narrative", more) + gen_rows("P_COMMUNICATE", ["が", "を", "と"])
    assert ct.decide_word(ev, cfg())["origin"] == "direct"


def test_rd_min_sources_counts_the_arms_that_reached_their_own_threshold():
    one = rd_rows("jawiki", COMM) + gen_rows("P_COMMUNICATE", ["が", "を"])
    assert ct.decide_word(one, cfg(rd_min_sources=2))["origin"] == "estimated"
    assert ct.decide_word(one, cfg(rd_min_sources=2))["arms"]["gen_frame"]["why"] is None
    assert ct.decide_word(one, cfg(rd_min_sources=1))["origin"] == "direct"
    # a source below rd_min_total does not count
    weak = {"が|PERSON": 3, "を|INFO_LANGUAGE": 4}
    two = rd_rows("jawiki", COMM) + rd_rows("codex:code", weak) + gen_rows("P_COMMUNICATE", ["が", "を"])
    assert ct.decide_word(two, cfg(rd_min_sources=2))["origin"] == "estimated"


def test_a_type_outside_k62_never_reaches_direct_because_no_arm_can_vote_for_it():
    ev = rd_rows("jawiki", COMM) + rd_rows("codex:narrative", COMM) + gen_rows("P_CREATE", ["が", "を"])
    d = ct.decide_word(ev, cfg())
    assert d["origin"] == "estimated" and d["arms"]["gen_frame"]["why"] == "DISTRIBUTION_DISAGREES"
    assert ct.decide_word(gen_rows("P_CREATE", ["が", "を"]), cfg())["origin"] == "estimated"


def test_a_generated_frame_never_changes_a_decision_made_without_it_nor_settles_a_split():
    seeded = [("seed", "hand", "P_MOVE", 1, None)] + gen_rows("P_COMMUNICATE", ["が", "を"])
    d = ct.decide_word(seeded, cfg())
    assert (d["state"], d["tops"], d["by"], d["origin"]) == ("DECIDED", ["P_MOVE"], ["seed"], "direct")
    assert d["arms"]["gen_frame"]["why"] == "GENERATED_NOT_DECIDING" and d["arms"]["gen_frame"]["met"] is False
    split = [("gen_frame", GEN, "P_MOVE", 1, None), ("gen_frame", GEN, "P_ACT", 1, None)]
    # two rows of one arm and one source with two types: the type is not settled by order
    d = ct.decide_word([("gen_frame", GEN, "P_MOVE", 1, None)] + [("gen_frame", GEN, "P_ACT", 1, None)], cfg())
    assert d["state"] == "UNPLACED" and d["arms"]["gen_frame"]["why"] == "GENERATED_SPLIT"


def test_the_slot_arm_is_shown_but_never_decides_alone():
    ev = [("slot", "jawiki", "TIME", 30, 100)]
    d = ct.decide_word(ev, cfg())
    assert d["state"] == "UNPLACED"
    a = d["arms"]["slot@jawiki"]
    assert a["threshold_met"] and not a["met"] and a["why"] == "AGREEMENT_ONLY" and a["top"] == ["TIME"]


def test_slot_agreeing_with_a_generated_definition_gives_direct_and_names_both():
    ev = [("slot", "jawiki", "TIME", 30, 100), ("gen_definition", "generated:m:low", "TIME", 1, None)]
    d = ct.decide_word(ev, cfg())
    assert (d["state"], d["origin"], d["tops"]) == ("DECIDED", "direct", ["TIME"])
    assert d["by"] == ["gen_definition", "slot@jawiki"] and d["arms"]["slot@jawiki"]["met"] is True
    # the generated definition against another type: an estimate, the slot stays evidence only
    ev = [("slot", "jawiki", "TIME", 30, 100), ("gen_definition", "generated:m:low", "PLACE", 1, None)]
    d = ct.decide_word(ev, cfg())
    assert (d["origin"], d["by"]) == ("estimated", ["gen_definition"])
    # a slot that ties at the top does not agree with anything
    ev = [("slot", "jawiki", "TIME", 30, 100), ("slot", "jawiki", "PLACE", 30, 100),
          ("gen_definition", "generated:m:low", "TIME", 1, None)]
    d = ct.decide_word(ev, cfg())
    assert d["origin"] == "estimated" and d["arms"]["slot@jawiki"]["top"] == ["PLACE", "TIME"]


def test_slot_thresholds_are_slot_min_and_the_share_of_the_nouns_uses():
    assert ct.arm_verdict("slot", {"TIME": 10}, cfg(slot_min=20), 100) == []
    assert ct.arm_verdict("slot", {"TIME": 10}, cfg(slot_min=5, slot_share_pct=20), 100) == []
    assert ct.arm_verdict("slot", {"TIME": 10}, cfg(slot_min=5, slot_share_pct=10), 100) == ["TIME"]
    assert ct.arm_verdict("slot", {"TIME": 9, "PLACE": 9}, cfg(slot_min=5, slot_share_pct=5), 100) == ["PLACE", "TIME"]


def test_frame_decides_false_keeps_the_old_frame_arm_as_evidence_only():
    ev = [("frame", "codex:narrative", "P_MOVE", 40, None)]
    on = ct.decide_word(ev, cfg(frame_decides=True))
    assert (on["state"], on["tops"], on["by"]) == ("DECIDED", ["P_MOVE"], ["frame@codex:narrative"])
    off = ct.decide_word(ev, cfg(frame_decides=False))
    assert off["state"] == "UNPLACED" and off["by"] == []
    a = off["arms"]["frame@codex:narrative"]
    assert a["threshold_met"] is True and a["met"] is False and a["why"] == "FRAME_NOT_DECIDING"
    assert ct.DEFAULT_CONFIG["frame_decides"] is True       # an old placement answers as it was stored


def test_words_without_a_new_row_are_decided_as_before():
    cases = [
        [("seed", "hand", "P_ACT", 1, None), ("frame", "jawiki", "P_MOVE", 40, None)],
        [("role", "jawiki", "PERSON", 9, None), ("role", "codex:code", "PERSON", 7, None)],
        [("role", "jawiki", "PERSON", 9, None)],
        [("definition", "jawiki", "PLACE", 2, None), ("alias", "jawiki", "PLACE", 1, None)],
        [("gen_definition", "generated:m:low", "PERSON", 1, None)],
        [("pos_class", "jawiki", "P_STATE", 5, 3)],
        [],
    ]
    want = [("DECIDED", ["P_ACT"], ["seed"], "direct"),
            ("DECIDED", ["PERSON"], ["role@codex:code", "role@jawiki"], "direct"),
            ("UNPLACED", [], [], None),
            ("DECIDED", ["PLACE"], ["alias", "definition"], "direct"),
            ("DECIDED", ["PERSON"], ["gen_definition"], "estimated"),
            ("DECIDED", ["P_STATE"], ["pos_class@jawiki"], "direct"),
            ("UNPLACED", [], [], None)]
    for ev, w in zip(cases, want):
        for fd in (True, False):      # none of these words is decided by the old frame arm
            d = ct.decide_word(ev, cfg(frame_decides=fd))
            assert (d["state"], d["tops"], d["by"], d["origin"]) == w, (ev, fd)


def test_the_new_names_are_appended_not_renamed():
    assert ct.ARMS[-3:] == ("role_distribution", "gen_frame", "slot")
    assert ct.ARMS_BY_SOURCE[-2:] == ("role_distribution", "slot")
    assert "gen_frame_slot" in ct.NON_VOTE_ARMS and ct.GEN_ARMS == ("gen_definition", "gen_frame")
    assert set(ct.AGREEMENT_ONLY_ARMS) == {"role_distribution", "slot"}
    assert ct.arm_key("role_distribution", "jawiki") == "role_distribution@jawiki"
    assert ct.arm_key("gen_frame", "x") == "gen_frame"

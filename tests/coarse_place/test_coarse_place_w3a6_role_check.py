"""W3-a6 (docs 12.18, D6): ``role_frame_check``.  Evidence rows are synthetic: (arm, source, type, n, base)."""
from verantyx import coarse_types as ct


def cfg(**kw):
    c = dict(ct.DEFAULT_CONFIG)
    c.update({"rd_min_total": 20, "rd_particle_min": 5, "rd_particle_share_pct": 10, "rd_type_share_pct": 50,
              "rd_min_sources": 1})
    c.update(kw)
    return c


def rd(src, counts, base=None):
    base = sum(counts.values()) if base is None else base
    return [("role_distribution", src, k, n, base) for k, n in counts.items()]


def role(r, *types):
    return {"role": r, "types": sorted(types)}


A = {"が|PERSON": 30, "に|PLACE": 25, "で|ARTIFACT": 22}           # significant: が に で
FRAME = {"に": [role("goal", "PLACE"), role("recipient", "PERSON", "GROUP_ORG")],
         "で": [role("instrument", "ARTIFACT"), role("cause", "EVENT_ACT")],
         "が": [role("agent", "PERSON")]}


def test_a_role_backed_by_a_significant_particle_and_type_is_confirmed_with_its_arm():
    r = ct.role_frame_check(FRAME, rd("jawiki", A), cfg())
    assert r["status"] == "CONFIRMED"
    assert r["confirmed"] == {"が": [{"role": "agent", "types": ["PERSON"], "backed_by": ["role_distribution@jawiki"]}],
                              "に": [{"role": "goal", "types": ["PLACE"], "backed_by": ["role_distribution@jawiki"]}],
                              "で": [{"role": "instrument", "types": ["ARTIFACT"],
                                      "backed_by": ["role_distribution@jawiki"]}]}
    assert r["arms"]["role_distribution@jawiki"]["sig"] == ["が", "に", "で"]
    # the roles with no vote are listed with a reason, in particle and role order
    assert r["unconfirmed"] == {"に": [{"role": "recipient", "types": ["GROUP_ORG", "PERSON"], "why": "NOT_BACKED"}],
                                "で": [{"role": "cause", "types": ["EVENT_ACT"], "why": "NOT_BACKED"}]}


def test_no_distribution_means_estimated_with_everything_unconfirmed():
    r = ct.role_frame_check(FRAME, [], cfg())
    assert r["status"] == "ESTIMATED" and r["confirmed"] == {} and r["arms"] == {}
    assert set(r["unconfirmed"]) == {"に", "で", "が"}
    assert all(e["why"] == "NOT_BACKED" for es in r["unconfirmed"].values() for e in es)


def test_a_source_below_rd_min_total_is_not_counted():
    rows = rd("jawiki", A, base=19)
    r = ct.role_frame_check(FRAME, rows, cfg())
    assert r["status"] == "ESTIMATED" and r["arms"] == {}


def test_the_same_type_declared_by_two_roles_of_one_particle_is_a_split_and_nobody_votes():
    frame = {"に": [role("goal", "PLACE"), role("place", "PLACE")]}
    r = ct.role_frame_check(frame, rd("jawiki", {"に|PLACE": 40, "が|PERSON": 10}), cfg())
    assert r["status"] == "ESTIMATED" and r["confirmed"] == {}
    assert [e["why"] for e in r["unconfirmed"]["に"]] == ["SPLIT", "SPLIT"]
    assert r["arms"]["role_distribution@jawiki"]["split"] == [{"particle": "に", "type": "PLACE", "roles": ["goal", "place"]}]
    assert r["arms"]["role_distribution@jawiki"]["votes"] == {}


def test_a_significant_type_the_frame_does_not_declare_is_shown_as_undeclared():
    frame = {"に": [role("recipient", "PERSON")]}
    r = ct.role_frame_check(frame, rd("jawiki", {"に|PLACE": 40, "が|PERSON": 10}), cfg())
    assert sorted(r["arms"]["role_distribution@jawiki"]["undeclared"]) == ["が|PERSON", "に|PLACE"]
    assert r["status"] == "ESTIMATED"


def test_a_role_with_types_only_partly_backed_is_confirmed_and_the_rest_is_partly_backed():
    frame = {"に": [role("recipient", "GROUP_ORG", "PERSON")]}
    r = ct.role_frame_check(frame, rd("jawiki", {"に|PERSON": 40, "が|PERSON": 10}), cfg())
    assert r["confirmed"] == {"に": [{"role": "recipient", "types": ["PERSON"], "backed_by": ["role_distribution@jawiki"]}]}
    assert r["unconfirmed"] == {"に": [{"role": "recipient", "types": ["GROUP_ORG"], "why": "PARTLY_BACKED"}]}


def test_the_sources_needed_follow_role_frame_min_sources_and_votes_are_never_added_up():
    one = rd("jawiki", A)
    two = one + rd("codex:code", A)
    frame = {"に": [role("goal", "PLACE")]}
    assert ct.role_frame_check(frame, one, cfg(role_frame_min_sources=1))["status"] == "CONFIRMED"
    r = ct.role_frame_check(frame, one, cfg(role_frame_min_sources=2))
    assert r["status"] == "ESTIMATED" and r["unconfirmed"]["に"][0]["why"] == "NOT_BACKED"
    r = ct.role_frame_check(frame, two, cfg(role_frame_min_sources=2))
    assert r["confirmed"]["に"][0]["backed_by"] == ["role_distribution@codex:code", "role_distribution@jawiki"]
    # default: rd_min_sources
    assert ct.role_frame_check(frame, one, cfg(rd_min_sources=2))["status"] == "ESTIMATED"


def test_confirmed_roles_of_one_particle_never_share_a_type_and_the_order_is_fixed():
    frame = {"で": [role("cause", "EVENT_ACT", "ABSTRACT"), role("instrument", "ARTIFACT", "ABSTRACT")],
             "に": [role("recipient", "PERSON"), role("goal", "PLACE")]}
    rows = rd("jawiki", {"に|PERSON": 20, "に|PLACE": 30, "で|ARTIFACT": 30, "で|EVENT_ACT": 25, "で|ABSTRACT": 1})
    r = ct.role_frame_check(frame, rows, cfg(rd_type_share_pct=20))
    for p, es in r["confirmed"].items():
        seen = set()
        for e in es:
            assert not (seen & set(e["types"]))
            seen |= set(e["types"])
    assert list(r["confirmed"]) == ["に", "で"]                              # CASE_PARTICLES_9 order
    assert [e["role"] for e in r["confirmed"]["に"]] == ["recipient", "goal"]      # ROLE_NAMES order
    assert [e["role"] for e in r["confirmed"]["で"]] == ["instrument", "cause"]

"""W3-a6 (docs 12.18, D5): the generated relative-position arm of ``decide_word``.  Evidence rows are synthetic:
(arm, source, type, n, base)."""
import copy
import random
import subprocess
import sys
import types
from pathlib import Path

from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]
GEN = "generated:gpt-6-luna:low"
RP = [("gen_relpos", GEN, "RELATIVE_POSITION", 1, None)]


def cfg(**kw):
    c = dict(ct.DEFAULT_CONFIG)
    c.update(kw)
    return c


def ev(*pairs):
    return [("role", "jawiki", t, n, None) for t, n in pairs]


def two_role(*pairs):
    """role rows from two sources, so that the role arm is a vote (role_min_sources)."""
    return ([("role", "jawiki", t, n, None) for t, n in pairs]
            + [("role", "codex:code", t, n, None) for t, n in pairs])


def test_a_place_only_direct_becomes_multiple_with_the_relative_position_added():
    rows = two_role(("PLACE", 50))
    before = ct.decide_word(rows, cfg())
    assert (before["state"], before["tops"], before["origin"]) == ("DECIDED", ["PLACE"], "direct")
    d = ct.decide_word(rows + RP, cfg())
    assert (d["state"], d["tops"], d["origin"]) == ("MULTIPLE", ["PLACE", "RELATIVE_POSITION"], "direct")
    assert d["by"] == sorted(before["by"] + ["gen_relpos"])
    assert d["estimate_basis"] is None
    a = d["arms"]["gen_relpos"]
    assert a["why"] == "RELPOS_ADDED" and a["met"] is True and a["top"] == ["RELATIVE_POSITION"]
    assert a["counts"] == {"RELATIVE_POSITION": 1} and a["threshold_met"] is True


def test_a_multiple_with_place_gets_a_third_type():
    rows = two_role(("PLACE", 30)) + [("definition", "jawiki", "TIME", 2, None)]
    before = ct.decide_word(rows, cfg())
    assert (before["state"], before["tops"]) == ("MULTIPLE", ["PLACE", "TIME"])
    d = ct.decide_word(rows + RP, cfg())
    assert (d["state"], d["tops"]) == ("MULTIPLE", ["PLACE", "RELATIVE_POSITION", "TIME"])
    assert d["arms"]["gen_relpos"]["why"] == "RELPOS_ADDED"


def test_a_decision_without_place_or_an_unplaced_word_is_not_changed_and_says_why():
    rows = two_role(("TIME", 50))
    before = ct.decide_word(rows, cfg())
    d = ct.decide_word(rows + RP, cfg())
    for k in ("state", "tops", "by", "origin", "estimate_basis"):
        assert d[k] == before[k]
    assert d["arms"]["gen_relpos"]["why"] == "GENERATED_NOT_DECIDING" and d["arms"]["gen_relpos"]["met"] is False
    d2 = ct.decide_word(RP, cfg())
    assert (d2["state"], d2["tops"], d2["by"]) == ("UNPLACED", [], [])
    assert d2["arms"]["gen_relpos"]["why"] == "GENERATED_NOT_DECIDING"


def test_an_arm_that_is_not_a_models_and_names_the_type_alone_makes_a_direct_relative_position():
    # an artificial row: the definition arm voting for the new type (no real arm does so in r9: docs 12.18, C6)
    rows = [("definition", "jawiki", "RELATIVE_POSITION", 3, None)]
    d = ct.decide_word(rows + RP, cfg())
    assert (d["state"], d["origin"], d["tops"]) == ("DECIDED", "direct", ["RELATIVE_POSITION"])
    assert d["by"] == ["definition", "gen_relpos"]
    assert d["arms"]["definition"]["met"] is True and d["arms"]["gen_relpos"]["met"] is True


def test_the_relative_position_row_never_enters_the_other_arms():
    rows = two_role(("PLACE", 50)) + [("gen_definition", GEN, "PERSON", 1, None)] + RP
    d = ct.decide_word(rows, cfg())
    assert d["arms"]["gen_definition"]["why"] == "GENERATED_NOT_DECIDING"
    assert d["arms"]["gen_relpos"]["why"] == "RELPOS_ADDED"


def _base_module():
    """the base commit's coarse_types under another name (no gen_relpos in it)"""
    src = subprocess.run(["git", "-C", str(TREE), "show", "0041606:verantyx/coarse_types.py"],
                         capture_output=True, text=True)
    assert src.returncode == 0, "required base commit 0041606 is unavailable: %s" % src.stderr
    name = "coarse_types_base_w3a6"
    m = types.ModuleType(name)
    m.__file__ = "0041606:verantyx/coarse_types.py"
    sys.modules[name] = m
    exec(compile(src.stdout, m.__file__, "exec"), m.__dict__)
    return m


def _artificial_evidence(rng):
    types = list(ct.FRAME_NOUN_TYPES) + [t for t in ct.PRED_TYPES]
    out = []
    for arm, srcs in (("role", ("jawiki", "codex:code", "codex:narrative")), ("hearst", ("jawiki", "codex:code")),
                      ("definition", ("jawiki",)), ("sahen", ("jawiki",)), ("pos_class", ("jawiki",)),
                      ("alias", ("jawiki",))):
        if rng.random() < 0.4:
            for s in srcs:
                if rng.random() < 0.6:
                    for t in rng.sample(types[:17], rng.randint(1, 3)):
                        out.append((arm, s, t, rng.randint(1, 60), rng.randint(1, 200) if arm in ("sahen", "pos_class") else None))
    for s in ("jawiki", "codex:code"):
        if rng.random() < 0.4:
            base = rng.randint(20, 300)
            for key in rng.sample(["が|PERSON", "を|INFO_LANGUAGE", "に|PLACE", "で|PLACE", "へ|PLACE", "から|PLACE", "が|ARTIFACT"], 4):
                out.append(("role_distribution", s, key, rng.randint(1, 80), base))
    if rng.random() < 0.3:
        out.append(("gen_definition", "generated:m:low", rng.choice(types[:17]), 1, None))
    if rng.random() < 0.3:
        out.append(("gen_frame", "generated:m:low", rng.choice(types[17:]), 1, None))
        out += [("gen_frame_slot", "generated:m:low", "%s|PERSON" % p, 1, None) for p in ct.CASE_PARTICLES_9[:4]]
    return out


def test_without_a_relative_position_row_decide_word_is_the_one_of_the_base_commit():
    base = _base_module()
    rng = random.Random(20261004)
    c = cfg(rd_min_total=20, rd_particle_min=5, rd_particle_share_pct=10, rd_type_share_pct=50, rd_min_sources=1,
            frame_cover_rule="k62_he_by_ni_place")
    n_nonempty = 0
    for _ in range(600):
        rows = _artificial_evidence(rng)
        n_nonempty += bool(rows)
        assert ct.decide_word(copy.deepcopy(rows), c) == base.decide_word(copy.deepcopy(rows), c)
    assert n_nonempty > 400

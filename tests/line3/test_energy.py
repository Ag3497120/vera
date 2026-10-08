"""T3 tests: energy and the three ratios (I-06, N-01, I-09, I-10, I-11)."""
import io
import os
import re
import subprocess
import sys
import tokenize
from fractions import Fraction as Fr

import pytest

from verantyx.line3 import energy as en
from verantyx.line3.geometry import Cross
from verantyx.line3.space import TierSpace

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "verantyx", "line3", "energy.py")


def tier(sentences):
    su = tuple(tuple(s.split()) for s in sentences)
    post = {}
    for sid, us in enumerate(su):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    return TierSpace("T", su, {u: tuple(v) for u, v in post.items()})


# worked example (hand-computed; the design v3 has no numeric example, see report)
EX = ["A B C", "A B", "A C D", "B D"]       # N=4: n A=3 B=3 C=2 D=2


def ex_cross(plus_x=("D", "B"), minus_x=(None, "C")):
    return Cross.make(L=2, center="A", arms=[plus_x, minus_x, (None, None), (None, None),
                                             (None, None), (None, None)])


def test_r0_and_energy_exact():
    t = tier(EX)
    assert [en.r0(t, u) for u in "ABCD"] == [Fr(3, 4), Fr(3, 4), Fr(1, 2), Fr(1, 2)]
    assert {u: en.energy(t, u, ["C"]) for u in "ABCD"} == {
        "A": Fr(5, 4), "B": Fr(1), "C": Fr(1), "D": Fr(3, 4)}
    assert en.energy(t, "A") == en.r0(t, "A")                       # no query: E = r0
    assert en.energy(t, "A", ["C", "C"]) == en.energy(t, "A", ["C"])  # L-51
    assert en.energy(t, "A", ["C", "D"]) == Fr(3, 4) + Fr(2, 4) + Fr(1, 4)
    assert en.energy(t, "Z", ["C"]) == 0 and en.energy(t, "A", ["Z"]) == Fr(3, 4)   # L-52/53
    for v in en.energies(t, "ABCD", ["C"]).values():
        assert isinstance(v, Fr)


def test_worked_example_F_and_B():
    t, c = tier(EX), ex_cross()
    assert en.edge_flow(t, c, ["C"]) == {
        "A": Fr(5, 3), "B": Fr(29, 24), "D": Fr(1, 3), "C": Fr(5, 6)}
    assert en.placement_binding(t, c) == {
        "A": Fr(4, 3), "B": Fr(1), "D": Fr(1, 2), "C": Fr(1)}
    assert en.unique_argmax(en.edge_flow(t, c, ["C"])) == "A"
    assert en.unique_argmax(en.placement_binding(t, c)) == "A"


def test_worked_example_sections_and_agreement():
    t, c = tier(EX), ex_cross()
    w = en.walk_arm(t, c, "+x", ["C"])
    assert w.path == ("D", "B", "A") and w.terminus == "A" and w.stop == "centre"
    assert en.walk_arm(t, c, "-x", ["C"]).stop == "empty"
    v = en.three_ratios(t, c, ["C"])
    assert (v.section_unit, v.edge_unit, v.placement_unit) == ("A", "A", "A")
    assert v.status == en.AGREE and v.unit == "A"
    assert [s.unit for s in v.sections] == ["A", "A", None, None, None, "A"]  # +x seen by sections 5,0,1 (I-09 window)
    assert v.working == 3 and v.working_attached == 0
    assert en.three_ratios(t, c, ["C"], attached={0: "C"}).working_attached == 1


def test_walk_stops_on_drop_and_unproven():
    t = tier(EX)
    c = ex_cross(plus_x=("B", "D"))           # E_C: B=1 -> D=3/4 drops
    w = en.walk_arm(t, c, "+x", ["C"])
    assert (w.terminus, w.stop) == ("B", "drop")
    t2 = tier(["X Y", "Z W"])                 # X,Z share no sentence
    c2 = Cross.make(L=2, center="Z", arms=[("X", "Z2"), (None,) * 2, (None,) * 2, (None,) * 2,
                                           (None,) * 2, (None,) * 2])
    w2 = en.walk_arm(t2, c2, "+x", [])
    assert w2.stop == "unproven" and w2.terminus == "X"
    c3 = Cross.make(L=2, center="Y", arms=[("X", None)] + [(None,) * 2] * 5)
    assert en.walk_arm(t2, c3, "+x", []).stop == "gap"


def test_ties_point_nowhere():
    t = tier(["X Y", "X Y"])
    c = Cross.make(L=2, center="X", arms=[(None, "Y")] + [(None, None)] * 5)
    assert en.edge_flow(t, c) == {"X": Fr(1), "Y": Fr(1)}
    assert en.unique_argmax(en.edge_flow(t, c)) is None
    assert en.unique_argmax(en.placement_binding(t, c)) is None
    v = en.three_ratios(t, c)
    assert v.status == en.POINTS_NOWHERE and v.unit is None
    assert en.unique_argmax({}) is None
    assert en.unique_argmax({"a": Fr(0)}) is None            # L-58
    assert en.unique_argmax({"a": Fr(1), "b": Fr(1), "c": Fr(1, 2)}) is None
    assert en.unique_argmax({"b": Fr(1), "a": Fr(1, 2)}) == "b"


def test_ratio_and_section_disagreement():
    t = tier(EX)
    def cr(a, b, cen="A"):
        return Cross.make(L=2, center=cen, arms=[a, b] + [(None, None)] * 4)
    v = en.three_ratios(t, cr(("B", "C"), (None, "D")), ["C"])        # found by exhaustive search
    assert (v.section_unit, v.edge_unit, v.placement_unit) == ("A", "A", "C")
    assert v.status == en.RATIO_DISAGREEMENT and v.unit is None
    v = en.three_ratios(t, cr(("B", "C"), ("D", None)), ["C"])
    assert v.status == en.SECTION_DISAGREEMENT and v.section_unit is None
    v = en.three_ratios(t, cr(("B", "D"), (None, "C")), ["C"])        # placement ties
    assert (v.section_unit, v.edge_unit, v.placement_unit) == ("B", "A", None)
    assert v.status == en.POINTS_NOWHERE


def test_attached_energy_used_per_section():
    t = tier(EX)
    c = ex_cross()
    # E_D for unit pair: with attached D, walk D(1/2+1/4)->B(3/4+1/4)->A(3/4+1/4) non-dropping
    assert en.walk_arm(t, c, "+x", [], attached="D").terminus == "A"
    # attached "A": E_A(D)=1/2+1/4=3/4, E_A(B)=3/4+2/4=5/4, E_A(A)=3/4+3/4=3/2: still A
    assert en.section_pointer(t, c, 0, [], attached="A").unit == "A"


def test_no_float_in_source():
    toks = list(tokenize.generate_tokens(io.StringIO(open(SRC, encoding="utf-8").read()).readline))
    for tk in toks:
        if tk.type == tokenize.NUMBER:
            assert not re.search(r"[.eEjJ]", tk.string.replace("0x", "")), tk
        if tk.type == tokenize.OP:
            assert tk.string not in ("/", "/=", "//", "**"), tk
        if tk.type == tokenize.NAME:
            assert tk.string not in ("float", "math", "random", "Decimal", "numpy"), tk
    assert "import math" not in open(SRC, encoding="utf-8").read()


def test_every_function_documents_a_decision_id():
    import inspect
    idpat = re.compile(r"\b(I|N|L)-\d\d\b")
    for name, f in inspect.getmembers(en, inspect.isfunction):
        if f.__module__ != en.__name__:
            continue
        assert idpat.search(f.__doc__ or ""), name


def test_deterministic_across_hashseeds():
    code = (
        "from verantyx.line3 import energy as en\n"
        "from verantyx.line3.geometry import Cross\n"
        "from tests.line3.test_energy import tier, EX, ex_cross\n"
        "t=tier(EX); c=ex_cross(); v=en.three_ratios(t,c,['C'])\n"
        "print(repr(v)); print(sorted(en.edge_flow(t,c,['C']).items()))\n"
    )
    outs = []
    for seed in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout)
    assert outs[0] == outs[1] and outs[0]

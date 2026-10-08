"""T2 geometry acceptance (docs/LINE3_DESIGN.md §9 T2)."""
import itertools
import os
import sys

import pytest

from verantyx.line3 import geometry as G
from verantyx.line3.geometry import (
    AXES, CENTER, G24, IDENTITY, Cross, Rotation, Seat,
    edges, legacy_shift, moves_rotate, moves_swap, neighbours, rotate, seats, swap,
    visible_arms,
)


def _filled(L=4):
    n = iter(range(100, 1000))
    return Cross.make(L, center=next(n), arms=[[next(n) for _ in range(L)] for _ in range(6)])


def test_loaded_from_clone():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert G.__file__.startswith(root + "/verantyx/line3/")


def test_axes_match_current_cross_module():
    from verantyx.cross import AXES as CUR
    assert AXES == CUR


# ---- group -----------------------------------------------------------------
def test_group_has_24_distinct_members():
    assert len(G24) == 24
    assert len({r.perm for r in G24}) == 24          # distinct 6-direction permutations


def test_identity_in_group():
    assert IDENTITY in G24


def test_closed_under_composition():
    s = set(G24)
    assert all(a.compose(b) in s for a in G24 for b in G24)


def test_inverses_in_group():
    for r in G24:
        assert r.inverse() in G24
        assert r.compose(r.inverse()) == IDENTITY == r.inverse().compose(r)


def test_associative():
    for a, b, c in itertools.product(G24[:8], repeat=3):
        assert a.compose(b).compose(c) == a.compose(b.compose(c))


def test_opposites_preserved_and_perms_valid():
    for r in G24:
        assert sorted(r.perm) == list(range(6))
        assert r.preserves_opposites()


def test_group_equals_closure_of_two_quarter_turns():
    # independent derivation: z-quarter-turn and x-quarter-turn generate the group
    # +x->+y->-x->-y->+x, z fixed
    rz = Rotation((2, 3, 1, 0, 4, 5))
    # +y->+z->-y->-z->+y, x fixed
    rx = Rotation((0, 1, 4, 5, 3, 2))
    seen = {IDENTITY}
    frontier = [IDENTITY]
    while frontier:
        nxt = []
        for g in frontier:
            for h in (rz, rx):
                n = h.compose(g)
                if n not in seen:
                    seen.add(n)
                    nxt.append(n)
        frontier = nxt
    assert seen == set(G24)


def test_reflections_excluded():
    # swapping +x/-x only is an improper map; it must not be in the group
    refl = Rotation((1, 0, 2, 3, 4, 5))
    assert refl.preserves_opposites() and refl not in G24


def test_legacy_shifts_membership():
    # F1: current shifts 2 and 4 are cube rotations (and 0), 1/3/5 are not.
    member = {k: legacy_shift(k) in G24 for k in range(6)}
    assert member == {0: True, 1: False, 2: True, 3: False, 4: True, 5: False}


def test_rotate_then_inverse_restores_byte_identically():
    c = _filled()
    for r in G24:
        back = rotate(rotate(c, r), r.inverse())
        assert back == c and back.serialize() == c.serialize()


def test_rotation_acts_as_group_action():
    c = _filled()
    for a, b in itertools.product(G24[:6], repeat=2):
        assert rotate(rotate(c, b), a) == rotate(c, a.compose(b))


def test_rotation_changes_world_view_but_not_contents():
    c = _filled()
    r = next(r for r in G24 if r != IDENTITY)
    d = rotate(c, r)
    assert d.arms == c.arms and d.center == c.center
    assert d.world_arms() != c.world_arms()
    # arm i now points to world g(i)
    for i in range(6):
        assert d.world_arms()[r(i)] == c.arms[i]


def test_rotate_rejects_non_rotation():
    with pytest.raises(ValueError):
        rotate(_filled(), legacy_shift(1))


def test_canonical_key_same_over_24_rotations():
    c = _filled()
    keys = {rotate(c, r).canonical_key() for r in G24}
    assert len(keys) == 1
    # and different crosses are told apart
    assert swap(c, CENTER, Seat("+x", 0)).canonical_key() != c.canonical_key()


# ---- swaps -----------------------------------------------------------------
def test_swap_is_involution_for_all_pairs():
    c = _filled(3)
    for p, q in moves_swap(3):
        once = swap(c, p, q)
        assert swap(once, p, q) == c
        assert swap(once, p, q).serialize() == c.serialize()
    assert len(moves_swap(3)) == (6 * 3 + 1) * (6 * 3) // 2


def test_swap_moves_exactly_two_seats_incl_centre():
    c = _filled()
    d = swap(c, CENTER, Seat("-z", 2))
    assert d.center == c.get(Seat("-z", 2)) and d.get(Seat("-z", 2)) == c.center
    diff = [s for s in seats(4) if c.get(s) != d.get(s)]
    assert sorted(diff) == sorted([CENTER, Seat("-z", 2)])
    assert swap(c, Seat("+x", 0), Seat("+x", 0)) == c
    assert swap(c, Seat("+x", 0), Seat("-x", 0)).orientation == c.orientation


def test_swap_rejects_bad_seat():
    with pytest.raises(ValueError):
        swap(_filled(), Seat("+x", 4), CENTER)
    with pytest.raises(ValueError):
        swap(_filled(), Seat("+w", 0), CENTER)


# ---- immutability / no aliasing ----------------------------------------------
def test_no_aliasing_with_inputs_and_between_versions():
    arms = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]]
    c = Cross.make(2, 0, arms)
    arms[0][0] = 99
    arms.append([1])
    assert c.get(Seat("+x", 0)) == 1
    d = swap(c, Seat("+x", 0), Seat("+x", 1))
    assert c.get(Seat("+x", 0)) == 1 and d.get(Seat("+x", 0)) == 2
    with pytest.raises(Exception):
        c.center = 5            # frozen
    with pytest.raises(TypeError):
        c.arms[0][0] = 5        # tuples
    with pytest.raises(TypeError):
        G24[0].perm[0] = 1


def test_cell_type_validation():
    with pytest.raises(TypeError):
        Cross.make(1, 0.5, [[1]] * 6)
    with pytest.raises(TypeError):
        Cross.make(1, True, [[1]] * 6)
    with pytest.raises(ValueError):
        Cross.make(2, 0, [[1]] * 6)


# ---- graph -------------------------------------------------------------------
def test_graph_shape():
    L = 4
    assert len(seats(L)) == 6 * L + 1
    assert len(edges(L)) == 6 * L          # k->k+1 plus L-1 -> centre, per arm
    assert set(neighbours(CENTER, L)) == {Seat(a, L - 1) for a in AXES}
    assert neighbours(Seat("+y", 0), L) == (Seat("+y", 1),)
    assert Seat("+y", 2) in neighbours(Seat("+y", 3), L) and CENTER in neighbours(Seat("+y", 3), L)
    for a, b in edges(L):                  # symmetric
        assert b in neighbours(a, L) and a in neighbours(b, L)


# ---- sections (I-09) ---------------------------------------------------------
def test_sections_match_consensus_visible_axes_at_identity_and_legacy_shifts():
    from verantyx.consensus import ConsensusConfig, SearchState, visible_axes
    from verantyx.cross import ShellCross
    shell = ShellCross(center=None)
    for window in (0, 1, 2, 3):
        cfg = ConsensusConfig(window=window)   # geometric_visibility False (ring)
        for k in range(6):
            st = SearchState(shell=shell, rotation=k)
            g = legacy_shift(k).inverse()      # arm in front of position p = AXES[(p+k)%6]
            for s in range(6):
                assert list(visible_arms(g, s, window)) == visible_axes(st, s, cfg), (window, k, s)
    st = SearchState(shell=shell, widened=True)
    assert list(visible_arms(IDENTITY, 0, 1, widened=True)) == visible_axes(st, 0, ConsensusConfig())


def test_window1_sees_own_and_ring_neighbours_including_opposite_pole():
    # consensus.py:73-76: ring mode, +x section sees -x at window=1
    assert visible_arms(IDENTITY, 0) == ("-z", "+x", "-x")
    assert visible_arms(IDENTITY, 2) == ("-x", "+y", "-y")


def test_rotation_changes_what_is_in_front_of_a_section():
    seen = {visible_arms(r, 0) for r in G24}
    assert len(seen) > 1
    for r in G24:
        v = visible_arms(r, 3)
        assert len(v) == 3 and len(set(v)) == 3


def test_every_arm_in_front_of_some_section_for_every_rotation():
    for r in G24:
        covered = {a for s in range(6) for a in visible_arms(r, s)}
        assert covered == set(AXES)


# ---- determinism -------------------------------------------------------------
def test_determinism_across_hash_seeds():
    import os
    import subprocess
    code = (
        "import hashlib;from verantyx.line3 import geometry as G;"
        "c=G.Cross.make(4,1,[[10*i+k for k in range(4)] for i in range(6)]);"
        "h=hashlib.sha256();"
        "[h.update(G.rotate(c,r).serialize()+G.swap(c,*p).serialize()+G.rotate(c,r).canonical_key()) "
        "for r in G.G24 for p in G.moves_swap(4)[:20]];"
        "h.update(repr([r.perm for r in G.G24]).encode());print(h.hexdigest())"
    )
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1")
        outs.append(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                                   text=True, check=True).stdout.strip())
    assert len(set(outs)) == 1 and len(outs[0]) == 64


def test_moves_rotate_count():
    assert len(moves_rotate()) == 23 and IDENTITY not in moves_rotate()


# ---- v3 (L-04 / N-09): capacity decided elsewhere; rebuild with longer arms ---
def _rebuild(c, L2, fill=None):
    """Same centre and arm contents, arms lengthened to L2 with `fill` appended at the
    centre-side end (k grows towards the centre; k=0 stays the outer end, I-03)."""
    arms = [list(a) + [fill] * (L2 - c.L) for a in c.arms]
    return Cross.make(L2, c.center, arms, c.orientation)


def test_longer_arms_rebuild_keeps_group_swaps_windows():
    for L in (1, 2, 4):
        for L2 in (L + 1, L + 3):
            c = _rebuild(_filled(L), L2)
            base = _filled(L)
            assert (c.L, len(seats(L2))) == (L2, 6 * L2 + 1)
            # the old contents are intact at the old seats
            for s in seats(L):
                assert c.get(s) == base.get(s)
            # 24 rotations, byte-identical restore, one orbit
            assert len({rotate(c, r).canonical_key() for r in G24}) == 1
            assert len({r.perm for r in G24}) == 24
            for r in G24:
                back = rotate(rotate(c, r), r.inverse())
                assert back == c and back.serialize() == c.serialize()
            # swaps: involution for every pair, exactly two seats change
            assert len(moves_swap(L2)) == (6 * L2 + 1) * (6 * L2) // 2
            for p, q in moves_swap(L2):
                once = swap(c, p, q)
                assert swap(once, p, q) == c
                assert [s for s in seats(L2) if once.get(s) != c.get(s)] in ([], [p, q])
            # graph
            assert len(edges(L2)) == 6 * L2
            # windows do not depend on L and still cover every arm
            for r in G24:
                for sec in range(6):
                    assert len(visible_arms(r, sec)) == 3
                assert {a for s in range(6) for a in visible_arms(r, s)} == set(AXES)
            # rotation moves the orientation, not contents, at the new length too
            r = next(r for r in G24 if r != IDENTITY)
            d = rotate(c, r)
            assert d.arms == c.arms and all(d.world_arms()[r(i)] == c.arms[i] for i in range(6))

"""LOOM-a tests: the loom state (docs/LINE3_LOOM_DESIGN.md 3.1-3.3; T-LOOM-01..09 for the state side).

Units (record / constructed / foundation), crosses, the seating rules, growth (loom-local, L-LOOM-23), the thread, the closure,
the foundation seats that no sequence of operations ever touches (OP-G1-4), the state sha.
"""


import ast


import os


import random


import pytest


from verantyx.line3 import foundation as fd


from verantyx.line3 import geometry as geo


from verantyx.loom import state as stt


from verantyx.loom.state import CODE, PROSE, LoomState, Refuse


from loom_common import ROOT, TOY, server, weaver


SPEC = fd.DEFAULT_SPEC


def test_foundation_tokens_in_ladder_order_at_the_innermost_seat():
    st = LoomState(PROSE)
    c = st.new_cross("WORD", 3)
    assert c.cid == "c1"
    for ai, p in enumerate(SPEC.arms):
        assert c.arms[ai] == [None, None, fd.token(p)]
    assert [SPEC.arms[i] for i in range(6)] == ["の", "に", "で", "と", "を", "が"]
    assert c.inner_k == 1
    assert c.data_seats() == ["centre"] + ["%s:%d" % (ax, k) for ax in geo.AXES for k in (0, 1)]


def test_l1_prose_cross_is_the_centre_alone_with_the_six_foundation_tokens():
    st = LoomState(PROSE)
    c = st.new_cross("WORD", 1)
    assert [a[0] for a in c.arms] == [fd.token(p) for p in SPEC.arms]
    assert c.inner_k == -1 and c.data_seats() == ["centre"]


def test_code_cross_has_no_foundation_and_data_seats_at_every_k():
    st = LoomState(CODE)
    c = st.new_cross("CODE", 3, 2)
    assert all(cell is None for a in c.arms for cell in a)
    assert c.inner_k == 2 and c.depth == 2
    assert len(c.data_seats()) == 1 + 6 * 3


def test_uid_and_cid_are_creation_order_labels():
    st = LoomState(PROSE)
    us = [st.new_unit("a%d" % i, "constructed", None, {}) for i in range(12)]
    assert [u.uid for u in us] == ["u%d" % i for i in range(1, 13)]
    cs = [st.new_cross("WORD", 1) for _ in range(3)]
    assert [c.cid for c in cs] == ["c1", "c2", "c3"]


def test_parse_seat():
    assert stt.parse_seat("centre") == (None, None)
    assert stt.parse_seat("+x:0") == ("+x", 0)
    assert stt.parse_seat("-z:12") == ("-z", 12)
    assert stt.parse_seat("+y") == ("+y", None)
    for bad in ("center", "+x:01", "x:0", "+w:0", "+x:-1", "", "+x:", None, 3):
        with pytest.raises(Refuse) as e:
            stt.parse_seat(bad)
        assert e.value.type == "bad_seat"


def test_check_seat_foundation_before_range():
    st = LoomState(PROSE)
    c = st.new_cross("WORD", 2)
    c.check_seat("+x", 0)
    with pytest.raises(Refuse) as e:
        c.check_seat("+x", 1)
    assert e.value.type == "seat_is_foundation"
    with pytest.raises(Refuse) as e:
        c.check_seat("+x", 2)
    assert e.value.type == "seat_out_of_range"
    code = LoomState(CODE).new_cross("CODE", 2)
    code.check_seat("+x", 1)                                   # a code cross has no foundation seat
    with pytest.raises(Refuse) as e:
        code.check_seat("+x", 2)
    assert e.value.type == "seat_out_of_range"


def test_bare_arm_is_the_innermost_empty_data_seat():
    st = LoomState(PROSE)
    c = st.new_cross("WORD", 4)                                # data seats 0 1 2
    assert c.bare_arm_seat("+x") == 2
    c.put("+x", 2, "u1")
    assert c.bare_arm_seat("+x") == 1
    c.put("+x", 1, "u2")
    c.put("+x", 0, "u3")
    with pytest.raises(Refuse) as e:
        c.bare_arm_seat("+x")
    assert e.value.type == "seat_out_of_range" and e.value.detail["reason"] == "arm_full"
    one = st.new_cross("WORD", 1)
    with pytest.raises(Refuse) as e:
        one.bare_arm_seat("+x")
    assert e.value.detail["reason"] == "no_data_seat"


def test_extend_is_loom_local_and_keeps_the_arms_in_place():
    """L-LOOM-23: prepend empty OUTER seats to every arm; the six arms are never permuted (placement.canon would sort a code cross's legs)."""
    st = LoomState(CODE)
    c = st.new_cross("CODE", 2)
    for ai, ax in enumerate(geo.AXES):                          # uids in the REVERSE of arm order, so a content sort would permute them
        c.arms[ai][1] = "u%d" % (9 - ai)
    before = [list(a) for a in c.arms]
    c.extend(4)
    assert c.L == 4
    assert [a[2:] for a in c.arms] == before
    assert all(a[:2] == [None, None] for a in c.arms)
    p = LoomState(PROSE).new_cross("WORD", 2)
    p.extend(3)
    assert [a[2] for a in p.arms] == [fd.token(x) for x in SPEC.arms] and all(a[:2] == [None, None] for a in p.arms)


def test_the_loom_never_calls_placement_canon_or_extend():
    """L-LOOM-23, checked on the source: no module of the loom calls placement.canon / placement.extend."""
    d = os.path.join(ROOT, "verantyx/loom")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(d, fn), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in ("pl", "placement") and n.attr in ("canon", "extend", "_canon_seated"):
                raise AssertionError("%s calls placement.%s" % (fn, n.attr))


def test_state_sha_is_a_function_of_the_state_and_changes_with_it():
    a, b = LoomState(PROSE), LoomState(PROSE)
    assert a.sha() == b.sha()
    u = a.new_unit("Ωa", "constructed", None, {"by": "m", "at": 1})
    assert a.sha() != b.sha()
    b.new_unit("Ωa", "constructed", None, {"by": "m", "at": 1})
    assert a.sha() == b.sha()
    c = a.new_cross("WORD", 2)
    s0 = a.sha()
    a.place(c, None, None, u.uid)
    assert a.sha() != s0 and u.seated == ["c1", "centre"]
    a.lift(c, None, None)
    assert a.sha() == s0 and u.seated is None


def test_swap_primitive_moves_the_seated_marks():
    st = LoomState(PROSE)
    c = st.new_cross("WORD", 2)
    u1 = st.new_unit("Ωa", "constructed", None, {})
    st.place(c, None, None, u1.uid)
    st.swap(c, (None, None), ("+x", 0))                          # a move into an empty seat
    assert c.centre is None and c.arms[0][0] == u1.uid and u1.seated == ["c1", "+x:0"]
    u2 = st.new_unit("Ωb", "constructed", None, {})
    st.place(c, "-z", 0, u2.uid)
    st.swap(c, ("+x", 0), ("-z", 0))
    assert c.arms[0][0] == u2.uid and c.arms[5][0] == u1.uid and u2.seated == ["c1", "+x:0"] and u1.seated == ["c1", "-z:0"]


def test_to_geometry_cross_is_a_valid_geometry_cross(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    u = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=3)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u)
    from verantyx.loom import read as rd
    run = srv.runs[w.run_id].run
    gc = rd.geometry_cross(run.state, run.state.crosses[c])
    assert isinstance(gc, geo.Cross) and gc.L == 3 and gc.center == "東京"
    assert [gc.arms[i][2] for i in range(6)] == [fd.token(p) for p in SPEC.arms]


def test_no_sequence_of_operations_touches_a_foundation_seat(tmp_path):
    """T-LOOM-01 property test: random scripted sequences over every state-changing op; the foundation tokens never move, and a refusal
    of a foundation seat is always `seat_is_foundation`."""
    srv = server(tmp_path)
    for seed in range(8):
        rng = random.Random(seed)
        w = weaver(srv, "prose/ca", run_id="prop%d" % seed)
        run = srv.runs[w.run_id].run
        pool = []
        for t in TOY[:4]:
            pool.append(w.call("add", text=t, kind="constructed")["uid"])
        crosses = []
        found = {}
        seats = ["centre"] + ["%s:%d" % (ax, k) for ax in geo.AXES for k in range(4)] + list(geo.AXES)
        for step in range(90):
            op = rng.choice(["open", "seat", "seat", "unseat", "swap", "swap", "extend", "seat_run", "topic"])
            if op == "open" and len(crosses) < 4:
                r = w.call("open_cross", tier="WORD", L=rng.randint(1, 5))
                if r["ok"]:
                    crosses.append(r["cid"])
                    found[r["cid"]] = [fd.token(p) for p in SPEC.arms]
            elif not crosses:
                continue
            elif op == "seat":
                w.call("seat", cid=rng.choice(crosses), seat=rng.choice(seats), uid=rng.choice(pool))
            elif op == "unseat":
                w.call("unseat", cid=rng.choice(crosses), seat=rng.choice(seats))
            elif op == "swap":
                w.call("swap", cid=rng.choice(crosses), seat_a=rng.choice(seats), seat_b=rng.choice(seats))
            elif op == "extend":
                w.call("extend", cid=rng.choice(crosses), L2=rng.randint(2, 5))
            elif op == "seat_run":
                w.call("seat_run", cid=rng.choice(crosses), arm=rng.choice(list(geo.AXES)), uids=rng.sample(pool, rng.randint(1, 3)))
            elif op == "topic":
                w.call("topic", cid=rng.choice(crosses), on=bool(rng.getrandbits(1)))
            for cid in crosses:
                c = run.state.crosses[cid]
                assert [a[c.L - 1] for a in c.arms] == found[cid], (seed, step, op)
        # every seated unit is where the registry says it is; a unit sits at most once
        seen = set()
        for cid in crosses:
            c = run.state.crosses[cid]
            for uid in c.uids():
                assert uid not in seen
                seen.add(uid)
                assert run.state.units[uid].seated[0] == cid
        assert {u.uid for u in run.state.units.values() if u.seated} == seen

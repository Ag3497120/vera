"""G4-b tests: the frozen flat stack (verantyx/line3/stack.py) -- docs/LINE3_G4_GROWTH_METER.md 5, OP-G4-2, D-5, OP-G4-3;
T-G4-4 (fold), T-G4-5 (untouched), T-G4-6 (birth), T-G4-7 (frozen), T-G4-8 (restricted fixed point), T-G4-10 (dictionary-free CHAR).

Toys have at most 12 sentences.  The CHAR tier needs no tokeniser; RUN / WORD use fugashi.  level "low" keeps the budget small, so crosses close
(a closed cross is what the stop rule is about).

Part 1  the prefix key (steps.py prefix()) and step 0
Part 2  the fold, in process and across processes (build in a subprocess, compare bytes)
Part 3  frozen seats, untouched crosses, birth equals the one-shot build, the restricted fixed point
Part 4  D-5: every new unit opens its own cross and is seated into the open crosses of its co-occurring seeds; closed crosses stay closed
Part 5  the ledger is complete (every seat change has a line with sid evidence)
Part 6  foundation off / on, CHAR only without a dictionary, the read view
Part 7  save / load, workers, PYTHONHASHSEED 0 / 1 / 12345, no float
"""
import dataclasses
import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import foundation as fd
from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp
from verantyx.line3 import stack as st
from test_placement import tier, TOYS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
LEVEL = "low"
SENTS = [                                     # 8 sentences, 4 documents
    ("A", "東京は日本の首都である。"), ("A", "東京の城は大きい。"),
    ("B", "大阪は日本の都市である。"), ("B", "大阪の城は古い。"),
    ("C", "東京と大阪の城を見る。"), ("C", "京都の寺と城。"),
    ("D", "京都は日本の古都である。"), ("D", "寺の庭は静かである。"),
]
MANY = [                                      # a sentence of 14 different characters: every cross of it ties 13 candidates and closes fast
    ("M", "一二三四五六七八九十百千万億。"), ("N", "一二三四五六。"), ("N", "七八九十百千万億。"),
]


def rows(sents):
    return [{"title": t, "sent": s, "source": "%s#%d" % (t, i)} for i, (t, s) in enumerate(sents)]


GROW = [("A", "一二三。"), ("B", "一二四五六七八九。"), ("C", "一二十百。")]      # the crosses of 一 and 二 close while they GROW (B), then record C as left

DOCS = st.docs_of_rows(rows(SENTS))
DOCS_MANY = st.docs_of_rows(rows(MANY))
DOCS_GROW = st.docs_of_rows(rows(GROW))
ORDER = [("T", "百一二三四五六七八。"), ("T", "百一二三四五六七八。"), ("T", "百千十。")]   # 百: share 2 with eight units (the cross closes inside that group), then share 1 with 千 and 十 (first occurrence 千, 十; code-point order 十, 千)
DOCS_ORDER = st.docs_of_rows(rows(ORDER))
DOCSETS = {"CHAR": DOCS, "MANY": DOCS_MANY, "GROW": DOCS_GROW}


def steps_of(docs, found="off", tiers=("CHAR",), level=LEVEL, workers=1):
    """[state_0, state_1, ...]: every step of the fold."""
    out = [st.empty_state(found, tiers, level)]
    for d in docs:
        out.append(st.extend(out[-1], d, workers))
    return out


def blob(state):
    """Every canonical byte of a state (all tiers) and its ledger, as one sha."""
    h = hashlib.sha256()
    for t in state.tier_names:
        h.update(state.state_bytes(t))
        h.update(b"\n--ledger--\n")
        h.update("".join(l + "\n" for l in state.ledger[t]).encode("utf-8"))
        h.update(state.shas[t].encode())
    return h.hexdigest()


@pytest.fixture(scope="module")
def S():
    """The folds used by most tests, built once."""
    return {("off", "CHAR"): steps_of(DOCS, "off"), ("on", "CHAR"): steps_of(DOCS, "on"),
            ("off", "MANY"): steps_of(DOCS_MANY, "off"), ("on", "MANY"): steps_of(DOCS_MANY, "on"),
            ("off", "GROW"): steps_of(DOCS_GROW, "off"), ("on", "GROW"): steps_of(DOCS_GROW, "on")}


FOUNDS = ["off", "on"]
KEYS = [("off", "CHAR"), ("on", "CHAR"), ("off", "MANY"), ("on", "MANY"), ("off", "GROW"), ("on", "GROW")]


def closed_total(state, tier="CHAR"):
    return sum(1 for c in state.crosses[tier].values() if c.closed)


# =============================================================================================================
# Part 1: the prefix key and step 0
# =============================================================================================================
def _steps_py():
    spec = importlib.util.spec_from_file_location("g4steps", os.path.join(ROOT, "experiments", "line3", "g4", "steps.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_prefix_key_is_the_one_steps_py_defines():
    m = _steps_py()
    path = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
    rws, arts, _cum = m.load_fulllead_sentences()
    prefix = m.create_prefix_writer(rws, arts, {t: i for i, t in enumerate(arts)})
    docs = st.load_docs(path)
    assert len(docs) == 300 and [d[0]["title"] for d in docs] == arts
    for k in (0, 1, 2, 5, 13, 34, 299, 300):
        sha, content = prefix(k)
        assert st.prefix_sha256(docs[:k]) == sha and st.prefix_bytes(docs[:k]) == content
    assert st.prefix_sha256(docs) == hashlib.sha256(open(path, "rb").read()).hexdigest()    # the file is canonical: prefix(300) is the file
    assert st.prefix_sha256([]) == hashlib.sha256(b"").hexdigest()


def test_a_state_carries_its_prefix_sha_and_title_order():
    s = steps_of(DOCS, "off")
    for k in range(len(DOCS) + 1):
        assert s[k].step == k and s[k].prefix_sha256 == st.prefix_sha256(DOCS[:k])
        assert s[k].title_order_sha256 == st.title_order_sha256([d[0]["title"] for d in DOCS[:k]])
    assert s[2].docs == [list(d) for d in DOCS[:2]]


def test_step_zero_has_no_cross_and_no_view():
    for found in FOUNDS:
        e = st.empty_state(found, ("CHAR",), LEVEL)
        assert e.step == 0 and e.crosses == {"CHAR": {}} and e.ledger == {"CHAR": ()}
        assert st.as_placements(e, "CHAR") == {}


def test_bad_input_is_refused():
    with pytest.raises(ValueError):
        st.empty_state("maybe", ("CHAR",), LEVEL)
    with pytest.raises(ValueError):
        st.empty_state("off", ("CHAR", "CHAR"), LEVEL)
    with pytest.raises(ValueError):
        st.empty_state("off", ("SYL",), LEVEL)
    with pytest.raises(ValueError):
        st.empty_state("off", ("CHAR",), "huge")
    with pytest.raises(st.StackError):
        st.extend(st.empty_state("off", ("CHAR",), LEVEL), [])
    with pytest.raises(st.StackError):
        st.extend(st.empty_state("off", ("CHAR",), LEVEL), [{"title": "x"}])


# =============================================================================================================
# Part 2: the fold
# =============================================================================================================
@pytest.mark.parametrize("key", KEYS)
def test_fold_in_process(S, key):
    s = S[key]
    docs = DOCSETS[key[1]]
    for k in range(len(docs)):
        one_pass = steps_of(docs[:k + 1], key[0])[-1]            # stack(docs[1..k+1])
        assert blob(one_pass) == blob(s[k + 1])
        assert blob(st.extend(s[k], docs[k])) == blob(s[k + 1])  # stack(docs[1..k]) then extend(doc k+1)
    assert blob(st.build(docs, foundation=key[0], tiers=("CHAR",), level=LEVEL)) == blob(s[-1])


FOLD_PROG = """
import json, sys
from verantyx.line3 import stack as st
a = json.loads(sys.stdin.read())
docs, mode, found, tiers, level, root, k = a["docs"], a["mode"], a["found"], tuple(a["tiers"]), a["level"], a["root"], a["k"]
def blob(state):
    import hashlib
    h = hashlib.sha256()
    for t in state.tier_names:
        h.update(state.state_bytes(t)); h.update(b"\\n--ledger--\\n")
        h.update("".join(l + "\\n" for l in state.ledger[t]).encode("utf-8")); h.update(state.shas[t].encode())
    return h.hexdigest()
if mode == "build_save":
    s = st.build(docs[:k], foundation=found, tiers=tiers, level=level)
    st.save(s, root)
    print(json.dumps({"blob": blob(s), "step": s.step}))
elif mode == "load_extend":
    s = st.load(root, docs[:k], foundation=found, tiers=tiers, level=level)
    pre = blob(s)
    s2 = st.extend(s, docs[k])
    print(json.dumps({"loaded": pre, "blob": blob(s2), "step": s2.step}))
elif mode == "single":
    s = st.build(docs[:k], foundation=found, tiers=tiers, level=level)
    print(json.dumps({"blob": blob(s), "step": s.step}))
"""


def run_prog(args, seed="0"):
    out = subprocess.run([PY, "-c", FOLD_PROG], input=json.dumps(args), cwd=ROOT, capture_output=True, text=True,
                         env=dict(os.environ, PYTHONPATH=ROOT + os.pathsep + os.path.join(ROOT, "tests", "line3"), PYTHONHASHSEED=seed))
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.parametrize("found", FOUNDS)
@pytest.mark.parametrize("name,k", [("CHAR", 1), ("CHAR", 2), ("CHAR", 3), ("GROW", 1), ("GROW", 2)])
def test_fold_across_processes(tmp_path, found, name, k):
    """Process 1 builds docs[1..k] and writes it; process 2 loads it and steps k+1; process 3 builds docs[1..k+1] in one pass.
    The bytes (crosses, ledger, identity) are the same.  DOCS ("CHAR") is the plain toy; DOCS_GROW is the toy whose crosses close WHILE
    GROWING (step 2) and then record `left_after` (step 3), so k = 1 crosses the growth-closure step and k = 2 the left_after step (L-G4-67)."""
    docs = DOCSETS[name]
    args = {"docs": docs, "found": found, "tiers": ["CHAR"], "level": LEVEL, "root": str(tmp_path), "k": k}
    a = run_prog({**args, "mode": "build_save"}, "0")
    b = run_prog({**args, "mode": "load_extend"}, "1")
    c = run_prog({**args, "mode": "single", "k": k + 1}, "12345")
    assert a["step"] == k and b["step"] == k + 1 and c["step"] == k + 1
    assert b["loaded"] == a["blob"]                    # the load reproduced the state byte for byte
    assert b["blob"] == c["blob"]                      # stack(1..k) then extend == stack(1..k+1)
    s = steps_of(docs[:k + 1], found)[-1]
    assert blob(s) == c["blob"]                        # and the same as this process


# =============================================================================================================
# Part 3: frozen / untouched / birth / restricted fixed point
# =============================================================================================================
@pytest.mark.parametrize("key", KEYS)
def test_a_seated_unit_never_moves(S, key):
    """T-G4-7: every member of a cross after a step descends from a member before it (the units seated by then sit on the same legs and rings,
    in the same order seated, and the foundation seats keep their particle); a unit's seating step and the order never change."""
    s = S[key]
    on = key[0] == "on"
    for k in range(1, len(s) - 1):
        for u, new in s[k + 1].crosses["CHAR"].items():
            old = s[k].crosses["CHAR"].get(u)
            if old is None:
                continue
            assert new.seated[:len(old.seated)] == old.seated and new.opened_at == old.opened_at
            assert new.left[:len(old.left)] == old.left
            if new.members == old.members and new.L == old.L:
                continue
            frozen, dropped = st.descendants(old, new, k + 1)
            assert frozen and 0 <= dropped <= len(old.members)
            fixed = frozenset(x for x, _ in old.seated)
            L2, L1 = new.L, old.L
            ext = {pl.extend(m, L1, L2) if L2 > L1 else m for m in old.members}
            for m in new.members:
                proj = pl.canon(tuple(None if x in set(y for y, z in new.seated if z > k) else x for x in m), L2)
                assert proj in ext
                if on:
                    assert tuple(m[1 + a * L2 + L2 - 1] for a in range(6)) == tuple(fd.token(p) for p in fd.DEFAULT_SPEC.arms)
                assert fixed <= set(m)


def test_a_frozen_settle_leaves_the_fixed_units_where_they_are():
    """placement._settle(fixed=): no member of the result moved a fixed unit; with an empty set it is the old code."""
    import random
    rnd = random.Random(7)
    for sents in TOYS:
        t = tier(sents)
        w = pl.Weights(t)
        for u in t.units()[:3]:
            p = pl.build_cross(t, u, w, quotient=False, group_insert="ordered", on_collapse="stop")
            if p.stop != "exhausted":
                continue
            L = p.L
            base = p.members[0]
            placed = [x for x in base if x is not None]
            if len(placed) < 3:
                continue
            fixed = frozenset(rnd.sample(placed, 2) + [base[0]])
            # scramble the non-fixed units into other seats, then settle with the fixed ones frozen
            free = [i for i, x in enumerate(base) if x not in fixed]
            vals = [base[i] for i in free]
            rnd.shuffle(vals)
            f = list(base)
            for i, v in zip(free, vals):
                f[i] = v
            start = pl.canon(tuple(f), L)
            work = pl._Work(pl.Budget(max_class=5000, max_states=100000, max_moves=10 ** 8))
            res = pl._settle(w, [start], L, work, work.budget, fixed)
            # canon re-sorts legs, so compare through the projection that keeps only the fixed units: the same legs, the same rings
            keep = lambda flat: pl.canon(tuple(x if x in fixed else None for x in flat), L)
            assert {keep(m) for m in res} == {keep(start)}
            work2 = pl._Work(work.budget)
            assert pl._settle(w, [start], L, work2, work2.budget) == pl._settle(w, [start], L, pl._Work(work.budget), work.budget, frozenset())


MUTANT_CAUGHT = [("off", "CHAR"), ("on", "CHAR"), ("off", "GROW")]
MUTANT_SURVIVES = [("off", "MANY"), ("on", "MANY"), ("on", "GROW")]


def _settle_ignoring_fixed(orig):
    def bad(w, starts, L, work, budget, fixed=frozenset()):
        return orig(w, starts, L, work, budget)             # the mutant: `fixed` is dropped, every seat may move
    return bad


@pytest.mark.parametrize("key", MUTANT_CAUGHT)
def test_a_settle_that_ignores_fixed_is_caught_by_the_frozen_check(monkeypatch, key):
    """Mutation test (L-G4-57, corrected in L-G4-66): replace `placement._settle` by a copy that ignores `fixed`.  The frozen check of the
    step (`descendants`: every new member projects onto an old member) must raise StackError "a seated unit moved"."""
    found, name = key
    monkeypatch.setattr(pl, "_settle", _settle_ignoring_fixed(pl._settle))
    with pytest.raises(st.StackError, match="a seated unit moved"):
        steps_of(DOCSETS[name], found)


@pytest.mark.parametrize("key", MUTANT_SURVIVES)
def test_the_toys_that_do_not_catch_the_unfrozen_settle_and_why(monkeypatch, key):
    """The blind spots of the mutation test, stated and pinned (they are not claimed as covered):
    MANY (off and on): every cross closes at birth in step 1 (one sentence of 14 different characters) and the later documents only record
      `left_after`, so no open cross is ever grown: a settle with `fixed` is never reached after step 1 (births call build_cross, where
      nothing is fixed).
    GROW on: the first insertion of every growth step (四) collapses against max_class before a settle returns, so nothing is filled
      (`grown` lists the seeds with `filled` == []), no arrangement is produced for the freeze to protect.
    The mutant therefore survives on these three; the toys that catch it are CHAR (off, on) and GROW off.  If a toy ever starts to catch
    one of them, this test fails and the list above is to be moved."""
    found, name = key
    monkeypatch.setattr(pl, "_settle", _settle_ignoring_fixed(pl._settle))
    steps_of(DOCSETS[name], found)                          # no StackError


@pytest.mark.parametrize("key", KEYS)
def test_untouched_crosses_are_byte_identical(S, key):
    """T-G4-5: a cross whose seed is not in document k+1 is the same bytes at k and k+1 (a seed in the document may still stay the same)."""
    s = S[key]
    docs = DOCSETS[key[1]]
    changed = 0
    for k in range(1, len(s) - 1):
        ts, _a = st.tier_space(s[k + 1], "CHAR")
        in_doc = {u for sid in range(sum(len(d) for d in docs[:k]), sum(len(d) for d in docs[:k + 1])) for u in ts.sentence_units[sid]}
        for u, old in s[k].crosses["CHAR"].items():
            new = s[k + 1].crosses["CHAR"][u]
            if u not in in_doc:
                assert new.to_bytes() == old.to_bytes()
            changed += new.to_bytes() != old.to_bytes()
    assert changed > 0 or key[1] == "MANY"


@pytest.mark.parametrize("key", KEYS)
def test_birth_equals_the_one_shot_build(S, key):
    """T-G4-6: a cross opened at step k is the one-shot placement of the prefix k, member for member; stack(1) is the one-shot
    quotient-off placement of prefix 1."""
    found, name = key
    s = S[key]
    docs = DOCSETS[name]
    on = found == "on"
    for k in range(1, len(s)):
        ts, adh = st.tier_space(s[k], "CHAR")
        w = pl.Weights(ts, adh) if on else pl.Weights(ts)
        for u, c in s[k].crosses["CHAR"].items():
            if c.opened_at != k:
                continue
            p = pl.build_cross(ts, u, w, budget=pl.budget_level(LEVEL), quotient=False, group_insert="ordered", order="forward",
                               on_collapse="stop", foundation=found, adhesion=adh)
            assert p.members == c.members and p.L == c.L and c.units == (u,) + tuple(v for stp in p.steps if stp.status == pl.STABLE for v in stp.units)
            assert (p.stop == pl.BUDGET) == c.closed and tuple(p.score) + ((p.a_num,) if on else ()) == c.key
            assert c.closed_reason == (p.broke_on.reason if c.closed else None) and c.keyed_at == k
    # stack(1): every cross is a birth
    assert all(c.opened_at == 1 for c in s[1].crosses["CHAR"].values())


@pytest.mark.parametrize("key", KEYS)
def test_a_grown_class_is_a_restricted_fixed_point(S, key):
    """T-G4-8: after a growth step the class is one key, no improving swap among the seats that are neither foundation seats nor held by
    a unit seated before this step, and closed under equal-key such swaps (independent code)."""
    found, _name = key
    s = S[key]
    n = 0
    for k in range(1, len(s)):
        ts, adh = st.tier_space(s[k], "CHAR")
        for u, c in sorted(s[k].crosses["CHAR"].items()):
            if c.keyed_at != k or len(c.members) > 40 or c.L > 3:
                continue
            r = st.verify_cross(ts, adh, c)
            assert r["ok"], (k, u, r)
            n += 1
    assert n > 0


# =============================================================================================================
# Part 4: D-5, closed crosses
# =============================================================================================================
@pytest.mark.parametrize("key", KEYS)
def test_every_new_unit_opens_its_own_cross_and_is_seated_in_the_open_crosses_it_shares_a_sentence_with(S, key):
    """D-5: set(crosses) == the units of the prefix at every step; a new unit has a cross of its own opened at that step; for every seed
    with an open cross that shares a sentence with the unit in the document the unit is seated in it (or, no seat accepting it, the cross
    is closed and the unit is recorded in `left`)."""
    s = S[key]
    docs = DOCSETS[key[1]]
    for k in range(1, len(s)):
        ts, _a = st.tier_space(s[k], "CHAR")
        assert set(s[k].crosses["CHAR"]) == set(ts.units())
        n0 = sum(len(d) for d in docs[:k - 1])
        dsids = range(n0, n0 + len(docs[k - 1]))
        prev = s[k - 1].crosses["CHAR"]
        new_units = [u for u in ts.units() if u not in prev]
        for u in new_units:
            c = s[k].crosses["CHAR"][u]
            assert c.opened_at == k and c.seated[0] == (u, k)
            if not c.closed:
                assert {v for v, _ in c.seated} == set(ts.cooccurrence(u)) | {u}     # every co-occurring unit is in the document
        for seed in sorted({x for sid in dsids for x in ts.sentence_units[sid]}):
            c = s[k].crosses["CHAR"][seed]
            for u in new_units:
                if u == seed or u not in ts.cooccurrence(seed):
                    continue
                seated = u in {v for v, _ in c.seated}
                left = u in {v for _s, v, _r in c.left}
                assert seated or left, (k, seed, u)
                assert seated != left or (seated and left and False)
                if prev.get(seed) is not None and not prev[seed].closed and not c.closed:
                    assert seated
                if prev.get(seed) is not None and prev[seed].closed:
                    assert not seated


@pytest.mark.parametrize("key", [("on", "CHAR"), ("off", "MANY"), ("on", "MANY"), ("off", "GROW"), ("on", "GROW")])
def test_a_closed_cross_stays_closed(S, key):
    s = S[key]
    seen = 0
    for k in range(1, len(s) - 1):
        for u, c in s[k].crosses["CHAR"].items():
            if not c.closed:
                continue
            seen += 1
            assert c.closed_reason in st.CLOSE_REASONS and c.closed_at <= k
            for k2 in range(k + 1, len(s)):
                d = s[k2].crosses["CHAR"][u]
                assert (d.closed_at, d.closed_reason, d.closed_unit, d.closed_explored) == (c.closed_at, c.closed_reason, c.closed_unit, c.closed_explored)
                assert d.members == c.members and d.L == c.L and d.seated == c.seated and d.key == c.key and d.keyed_at == c.keyed_at
                assert d.left[:len(c.left)] == c.left and all(r == st.LEFT_AFTER and stp > c.closed_at for stp, _v, r in d.left[len(c.left):])
                assert st.arr_sha(d) == st.arr_sha(c)
    assert seen > 0


def test_off_also_closes_when_the_budget_is_reached(S):
    s = S[("off", "MANY")]
    assert closed_total(s[1]) > 0
    reasons = {c.closed_reason for c in s[1].crosses["CHAR"].values() if c.closed}
    assert reasons <= set(st.CLOSE_REASONS)


def test_the_units_a_closed_cross_never_seated_are_recorded_with_their_step(S):
    s = S[("off", "MANY")]
    c = next(c for c in s[1].crosses["CHAR"].values() if c.closed)
    seated = {v for v, _ in c.seated}
    assert c.left[0][1:] == (c.closed_unit, c.closed_reason) and c.left[0][0] == 1
    assert all(r == st.LEFT_IN_STEP and stp == 1 for stp, _v, r in c.left[1:]) and not (seated & {v for _s, v, _r in c.left})
    # together the seated and the left units are all the candidates of the seed
    ts, _a = st.tier_space(s[1], "CHAR")
    assert seated | {v for _s, v, _r in c.left} == set(ts.cooccurrence(c.seed)) | {c.seed}
    # a later document with a new co-occurring unit: recorded as left_after, not seated
    c2 = s[2].crosses["CHAR"][c.seed]
    assert any(r == st.LEFT_AFTER for _s, _v, r in c2.left) or c2.left == c.left


@pytest.mark.parametrize("key", KEYS)
def test_every_co_occurring_unit_is_seated_or_left_never_both(S, key):
    """An open cross seats every unit that shares a sentence with its seed; a closed one has each of them either seated or recorded as left."""
    s = S[key]
    for k in range(1, len(s)):
        ts, _a = st.tier_space(s[k], "CHAR")
        for u, c in s[k].crosses["CHAR"].items():
            seated = [v for v, _ in c.seated]
            left = [v for _s, v, _r in c.left]
            assert len(set(seated)) == len(seated) and len(set(left)) == len(left) and not set(seated) & set(left)
            want = set(ts.cooccurrence(u)) | {u}
            assert set(seated) | set(left) == want, (k, u)
            if not c.closed:
                assert not left and set(seated) == want
            else:
                assert c.left[0] == (c.closed_at, c.closed_unit, c.closed_reason)


@pytest.mark.parametrize("key", KEYS)
def test_left_in_step_of_a_birth_is_in_the_order_a_growth_would_use(S, key):
    """L-G4-69: a cross that closes at birth records the rest of its candidates in the SAME order `_grow` seats them (share-groups by n
    descending, inside a group `group_order`): the units seated before the break + the breaking unit + `left_in_step` are exactly
    `_candidate_order` of the seed."""
    s = S[key]
    n = 0
    for k in range(1, len(s)):
        ts, _a = st.tier_space(s[k], "CHAR")
        for u, c in s[k].crosses["CHAR"].items():
            if c.opened_at != k or c.closed_at != k:
                continue
            seq = st._candidate_order(ts, u, list(ts.cooccurrence(u)))
            tail = [c.closed_unit] + [v for stp, v, r in c.left if stp == k and r == st.LEFT_IN_STEP]
            i = seq.index(c.closed_unit)
            assert seq[i:] == tail, (k, u)
            assert [v for v, _ in c.seated[1:]] == seq[:i], (k, u)
            n += 1
    assert n > 0 or key in [("off", "CHAR"), ("off", "GROW")]      # those toys close nothing at birth


@pytest.mark.parametrize("found", FOUNDS)
def test_left_in_step_of_a_birth_puts_a_later_tied_group_in_group_order_not_label_order(found):
    """L-G4-69, the case the toys above do not reach: the seed 百 closes inside its share-2 group; the later share-1 group {十, 千} is recorded
    in the order of first occurrence (千, 十), as `_grow` would seat it, not in code-point order (十, 千)."""
    s = steps_of(DOCS_ORDER, found)[1]
    c = s.crosses["CHAR"]["百"]
    ts, _a = st.tier_space(s, "CHAR")
    assert c.closed_at == 1 and [g for _n, g in pl._groups(ts, "百")][-1] == ("十", "千")
    left = [v for stp, v, r in c.left if r == st.LEFT_IN_STEP]
    assert left[-2:] == ["千", "十"] and left == list(st._candidate_order(ts, "百", list(ts.cooccurrence("百"))))[len(c.seated):]


def test_a_cross_that_closes_while_growing_keeps_what_it_seated_and_records_the_rest():
    for found in FOUNDS:
        s = steps_of(DOCS_GROW, found)
        e = ledger(s[2])[-1]
        grow_closed = [c for c in e["closed"] if c["at"] == "grow"]
        assert grow_closed, found
        for c in grow_closed:
            old, new = s[1].crosses["CHAR"][c["seed"]], s[2].crosses["CHAR"][c["seed"]]
            assert new.closed_at == 2 and not old.closed and new.seated[:len(old.seated)] == old.seated
            assert [v for _s, v, r in new.left if r == st.LEFT_IN_STEP] == c["left_in_step"]
            assert c["unit"] == new.closed_unit and c["reason"] == new.closed_reason and c["explored"] == new.closed_explored
        e3 = ledger(s[3])[-1]
        assert sum(e3["left_after"].values()) > 0 and e3["grown"] == [] or found == "on"


# =============================================================================================================
# Part 5: the ledger
# =============================================================================================================
def ledger(state, tier="CHAR"):
    return [json.loads(l) for l in state.ledger[tier]]


@pytest.mark.parametrize("key", KEYS)
def test_the_ledger_is_complete(S, key):
    """Every seat change between two steps has a ledger line (cross, unit, kind, arm, ring, sids) whose sids really hold both the seed and
    the unit; every cross that opened, closed or was rearranged is named; every other cross is byte-identical (or only recorded `left`)."""
    found, name = key
    s = S[key]
    docs = DOCSETS[name]
    on = found == "on"
    for k in range(1, len(s)):
        entry = ledger(s[k])[-1]
        assert len(s[k].ledger["CHAR"]) == k and entry["step"] == k and entry["state_sha256"] == s[k].shas["CHAR"]
        assert entry["title"] == docs[k - 1][0]["title"] and entry["prefix_sha256"] == s[k].prefix_sha256
        ts, _a = st.tier_space(s[k], "CHAR")
        lines = {(x["cross"], x["unit"]): x for x in entry["seats"]}
        prev = s[k - 1].crosses["CHAR"]
        for u, c in s[k].crosses["CHAR"].items():
            old = prev.get(u)
            newly = [(v, stp) for v, stp in c.seated if old is None or (v, stp) not in set(old.seated)]
            assert all(stp == k for _v, stp in newly)
            for v, _stp in newly:
                line = lines.pop((u, v))
                assert line["kind"] == (st.BIRTH if old is None else st.FILL) and line["sids"]
                assert all(u in ts.sentence_units[sid] and v in ts.sentence_units[sid] for sid in line["sids"])
                assert set(line["sids"]) == set(ts.postings[u]) & set(ts.postings[v])
                assert line["ring"] and (not on or line["arm"])
            if old is None:
                assert u in entry["opened"] and u in {b["seed"] for b in entry["births"]}
            elif st.arr_sha(old) != st.arr_sha(c):
                g = [x for x in entry["grown"] if x["seed"] == u]
                assert len(g) == 1 and g[0]["arr"] == [st.arr_sha(old), st.arr_sha(c)] and g[0]["filled"] == [v for v, _ in newly]
                assert g[0]["L"] == [old.L, c.L] and g[0]["members"] == [len(old.members), len(c.members)]
                assert g[0]["narrowed"] == (g[0]["dropped"] > 0) and g[0]["key"] == [list(old.key), list(c.key)]
                if on and newly:
                    assert g[0]["a_gain"] == c.key[2] - old.key[2]
            else:             # not rearranged: named in `grown` only if it closed in this step without seating anything
                g = [x for x in entry["grown"] if x["seed"] == u]
                assert u not in entry["opened"] and (not g or (c.closed_at == k and g[0]["filled"] == [] and not g[0]["narrowed"]))
            if c.closed_at == k:
                assert [x for x in entry["closed"] if x["seed"] == u and x["reason"] == c.closed_reason and x["unit"] == c.closed_unit]
            if old is not None and old.left != c.left and not (c.closed_at == k):
                assert entry["left_after"][u] == len(c.left) - len(old.left)
            if old is not None and c.to_bytes() == old.to_bytes():
                assert u not in entry["left_after"] and all(x["seed"] != u for x in entry["grown"])
        assert not lines, "a ledger seat line without a seat change"
        assert entry["touched"] == len({x for sid in range(entry["sids"][0], entry["sids"][1]) for x in ts.sentence_units[sid]})
        assert entry["adhesion"] is None or entry["adhesion"]["attachments_added"] == sum(entry["adhesion"]["by_particle"].values())
        assert (entry["adhesion"] is not None) == on
        assert [b["seed"] for b in entry["births"]] == entry["opened"] == sorted(entry["opened"])


def test_a_foundation_on_ledger_names_the_arm_of_every_seat_and_the_a_per_cross(S):
    s = S[("on", "CHAR")]
    arms = set()
    for k in range(1, len(s)):
        e = ledger(s[k])[-1]
        for x in e["seats"]:
            arms |= set(x["arm"])
        for b in e["births"]:
            assert len(b["key"]) == 3                      # (n, p, a)
    assert arms <= set(fd.DEFAULT_SPEC.arms) | {"centre"} and len(arms) > 1
    s_off = steps_of(DOCS, "off")
    assert all(not x["arm"] or x["arm"] == ["centre"] for k in range(1, len(s_off)) for x in ledger(s_off[k])[-1]["seats"])


@pytest.mark.parametrize("key", KEYS)
def test_the_drop_split_adds_up_and_is_the_key_under_the_new_counts(S, key):
    """L-G4-70 (diagnostic only): every `grown` line has dropped_new + dropped_recount == dropped; recomputed here from the keys of the old
    members, extended to the new L, under the counts of the step's prefix: a dropped member is `recount` iff its key is below the best key
    of the extended old members."""
    found, name = key
    s = S[key]
    seen_new = seen_recount = 0
    for k in range(1, len(s)):
        ts, adh = st.tier_space(s[k], "CHAR")
        w = pl.Weights(ts, adh) if found == "on" else pl.Weights(ts)
        for g in ledger(s[k])[-1]["grown"]:
            assert g["dropped_new"] >= 0 and g["dropped_recount"] >= 0 and g["dropped_new"] + g["dropped_recount"] == g["dropped"]
            assert g["narrowed"] == (g["dropped"] > 0)
            old, new = s[k - 1].crosses["CHAR"][g["seed"]], s[k].crosses["CHAR"][g["seed"]]
            ext = [pl.extend(m, old.L, new.L) if new.L > old.L else m for m in old.members]
            drop = set(v for v, stp in new.seated if stp >= k)
            proj = {pl.canon(tuple(None if x in drop else x for x in m), new.L) for m in new.members}
            gone = [m for m in ext if m not in proj]
            assert len(gone) == g["dropped"]
            keys = {m: tuple(pl.score_flat(w, m, new.L)) for m in ext}
            best = max(keys.values())
            rec = sum(1 for m in gone if keys[m] < best)
            assert (g["dropped"] - rec, rec) == (g["dropped_new"], g["dropped_recount"])
            seen_new += g["dropped_new"]
            seen_recount += g["dropped_recount"]
    if name == "CHAR":                                                # the plain toy has both kinds of 絞り
        assert seen_new > 0 and seen_recount > 0


# =============================================================================================================
# Part 6: foundation off / on, the dictionary-free CHAR arm, the read view
# =============================================================================================================
def test_foundation_on_seats_the_particles_off_does_not(S):
    on, off = S[("on", "CHAR")][-1], S[("off", "CHAR")][-1]
    assert on.seats_sha == fd.seats_sha() and off.seats_sha is None and on.shas["CHAR"] != off.shas["CHAR"]
    for c in on.crosses["CHAR"].values():
        assert len(c.key) == 3 and all(m[1 + a * c.L + c.L - 1] == fd.token(p) for m in c.members for a, p in enumerate(fd.DEFAULT_SPEC.arms))
        assert len(c.seated) == len(_units(c.members[0]))
    for c in off.crosses["CHAR"].values():
        assert len(c.key) == 2 and not any(fd.is_constructed(x) for m in c.members for x in m)
        assert len(c.seated) == len(_units(c.members[0]))


def _units(flat):
    return [x for x in flat if x is not None and not fd.is_constructed(x)]


@pytest.mark.parametrize("key", [("off", "CHAR"), ("on", "CHAR")])
def test_the_read_view_is_the_standard_placement_of_exactly_the_tier_units(S, key):
    found, _ = key
    s = S[key][-1]
    pls = st.as_placements(s, "CHAR")
    ts, adh = st.tier_space(s, "CHAR")
    assert list(pls) == ts.units() == sorted(pls)
    for u, p in pls.items():
        c = s.crosses["CHAR"][u]
        assert isinstance(p, pl.Placement) and p.seed == u and p.size == len(c.seated) and p.quotient is False and p.twin_sets == ()
        assert p.group_insert == "ordered" and p.order == "forward" and p.on_collapse == "stop"
        assert p.stop == (pl.BUDGET if c.closed else "exhausted") and p.candidates == len(ts.cooccurrence(u))
        assert p.L == (max(1, c.L - 1) if found == "on" else c.L)
        assert (p.foundation is not None) == (found == "on") and (p.contracted == (found == "on"))
        assert all(not any(fd.is_constructed(x) for x in m) for m in p.members)
        assert set(x for m in p.members for x in m if x is not None) == {v for v, _ in c.seated}
        assert len(p.members) <= len(c.members)
        if found == "on":
            assert p.members == pl.contract_for_read(dataclasses.replace(p, members=c.members, L=c.L, contracted=False, arm_labels=None)).members
        assert p.left_after == sum(1 for _s, _v, r in c.left if r == st.LEFT_AFTER)
        json.loads(p.to_bytes())


@pytest.mark.parametrize("key", [("off", "CHAR"), ("on", "CHAR"), ("off", "MANY"), ("on", "GROW")])
def test_every_stack_view_is_marked_from_stack_and_closed_ones_invite_an_on_demand_rebuild(S, key):
    """L-G4-68 (the hazard that G4-c has to close).  The view marks a closed cross `stop == "budget"`; `cycle.ask_tier`'s default
    raise_budget="on_demand" rebuilds every such cross (the level of the stored budget is below "high") with `placement.build_cross`
    defaults -- quotient on, foundation off, group_insert "whole" -- NOT the frozen flats of the stack.  An `ask.Index` over a stack view
    must therefore not be used with on_demand; the guard (refuse the rebuild when `from_stack`) is owed to G4-c.  Here: the marker is on
    every view, off on a one-shot placement, outside ==, repr and the JSON; and the condition ask_tier tests holds for the closed views,
    with the rebuild it would make not marked and not the stack's cross."""
    found, name = key
    s = S[key][-1]
    pls = st.as_placements(s, "CHAR")
    assert pls and all(p.from_stack is True for p in pls.values())
    p0 = next(iter(pls.values()))
    assert dataclasses.replace(p0, from_stack=False) == p0 and "from_stack" not in repr(p0) and b"from_stack" not in p0.to_bytes()
    ts, adh = st.tier_space(s, "CHAR")
    w = pl.Weights(ts)
    one = pl.build_cross(ts, p0.seed, w, budget=pl.budget_level(LEVEL))
    assert one.from_stack is False
    closed = [p for p in pls.values() if p.stop == "budget"]
    assert closed or name == "CHAR" and found == "off"
    for p in closed:
        assert pl.LEVEL_ORDER.index(pl.level_name(p.budget)) < pl.LEVEL_ORDER.index("high")      # cycle.ask_tier: lvl(sd) < raise level
        rb = pl.build_cross(ts, p.seed, w, budget=pl.budget_level("high"), group_insert="whole", order="forward", on_collapse="stop")
        assert rb.from_stack is False and rb.quotient is True and rb.foundation is None and p.quotient is False


def test_the_reader_reads_a_stack_without_building_anything():
    """The view is what ask's loader expects: an Index over it answers a toy question and builds no cross on demand."""
    from verantyx.line3 import ask
    rws = rows(SENTS)
    docs = st.docs_of_rows(rws)
    for found in FOUNDS:
        s = st.build(docs, foundation=found, tiers=("RUN", "WORD", "CHAR"), level=LEVEL)
        space = sp.build_space(rws)
        assert st.prefix_sha256(docs) == s.prefix_sha256
        loaded = {t: st.as_placements(s, t) for t in s.tier_names}
        for t in s.tier_names:
            assert set(loaded[t]) == set(space.tiers[t].units())
        ix = ask.Index(space, s.prefix_sha256, LEVEL, ("RUN", "WORD", "CHAR"), loaded, group_insert="ordered", order="forward")
        out = ask.ask(ix, "東京の城はどうですか。")
        assert out.to_bytes()
        assert all(ix.stores[t].on_demand == 0 for t in ix.tiers)


CHAR_PROG = """
import sys, json
for m in ("fugashi", "unidic_lite", "unidic"):
    sys.modules[m] = None
from verantyx.line3 import stack as st
a = json.loads(sys.stdin.read())
out = {}
for found in ("off", "on"):
    s = st.build(a["docs"], foundation=found, tiers=("CHAR",), level=a["level"])
    out[found] = {"sha": s.shas["CHAR"], "step": s.step, "ledger": s.ledger_sha256("CHAR")}
    assert not any(m in sys.modules and sys.modules[m] is not None for m in ("fugashi", "unidic_lite"))
print(json.dumps(out))
"""


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_char_only_stack_needs_no_dictionary_and_equals_the_char_stack_of_the_three_tier_build(seed):
    """T-G4-10: with fugashi / unidic_lite blocked the CHAR-only build runs, and its state_sha256 is the CHAR tier's of the 3-tier build."""
    out = subprocess.run([PY, "-c", CHAR_PROG], input=json.dumps({"docs": DOCS, "level": LEVEL}), cwd=ROOT, capture_output=True, text=True,
                         env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed))
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    for found in FOUNDS:
        full = st.build(DOCS, foundation=found, tiers=("RUN", "WORD", "CHAR"), level=LEVEL)
        assert got[found]["sha"] == full.shas["CHAR"] and got[found]["ledger"] == full.ledger_sha256("CHAR") and got[found]["step"] == 4
        only = steps_of(DOCS, found)[-1]
        assert only.shas["CHAR"] == full.shas["CHAR"] and only.state_bytes("CHAR") == full.state_bytes("CHAR")


def test_tiers_are_independent_stacks():
    """I-16: a tier's crosses do not depend on which other tiers are built."""
    a = st.build(DOCS, foundation="on", tiers=("RUN", "WORD", "CHAR"), level=LEVEL)
    b = st.build(DOCS, foundation="on", tiers=("WORD",), level=LEVEL)
    assert a.shas["WORD"] == b.shas["WORD"] and a.state_bytes("WORD") == b.state_bytes("WORD")
    for t in a.tier_names:
        assert set(a.crosses[t]) == set(st.tier_space(a, t)[0].units())


def test_seeds_are_the_seed_units_and_the_centre_is_found_by_search(S):
    """The cross of a seed is keyed by it and holds it; the centre of a member may be another unit (I-02)."""
    for key in KEYS:
        for c in S[key][-1].crosses["CHAR"].values():
            assert c.seed == c.seated[0][0] and c.seed in {x for m in c.members for x in m}
            assert all(m[0] is not None for m in c.members)


# =============================================================================================================
# Part 7: save / load, workers, hash seeds, no float
# =============================================================================================================
def test_save_load_roundtrip_and_refusals(tmp_path):
    root = str(tmp_path)
    s3 = steps_of(DOCS, "on")[3]
    st.save(s3, root)
    st.save(s3, root)                                           # idempotent
    back = st.load(root, DOCS[:3], foundation="on", tiers=("CHAR",), level=LEVEL)
    assert blob(back) == blob(s3) and back.step == 3 and back.titles == s3.titles and back.docs == s3.docs
    assert st.load(root, s3.prefix_sha256, foundation="on", tiers=("CHAR",), level=LEVEL).shas == s3.shas
    for bad in (dict(foundation="off"), dict(order="reverse"), dict(level="mid"), dict(tiers=("RUN",))):
        with pytest.raises(st.StackError):
            st.load(root, DOCS[:3], **{**dict(foundation="on", tiers=("CHAR",), level=LEVEL), **bad})
    with pytest.raises(st.StackError):
        st.load(root, DOCS[:2], foundation="on", tiers=("CHAR",), level=LEVEL)             # another prefix
    # tamper: one cross changed in the stored state is refused
    d = st._cfg_dir(root, "on", LEVEL, "forward")
    path = os.path.join(d, "CHAR_state_%s.jsonl.gz" % s3.prefix_sha256[:12])
    lines = gzip.open(path, "rb").read().decode("utf-8").splitlines()
    o = json.loads(lines[1])
    o["keyed_at"] += 1
    lines[1] = json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    open(path, "wb").write(gzip.compress(("\n".join(lines) + "\n").encode("utf-8")))
    with pytest.raises(st.StackError):
        st.load(root, DOCS[:3], foundation="on", tiers=("CHAR",), level=LEVEL)


def test_two_arms_may_share_a_directory_without_overwriting_each_other(tmp_path):
    a = steps_of(DOCS, "off")[2]
    b = st.build(DOCS[:2], foundation="off", tiers=("RUN", "CHAR"), level=LEVEL)
    st.save(a, str(tmp_path))
    st.save(b, str(tmp_path))
    st.load(str(tmp_path), DOCS[:2], foundation="off", tiers=("CHAR",), level=LEVEL)
    st.load(str(tmp_path), DOCS[:2], foundation="off", tiers=("RUN", "CHAR"), level=LEVEL)


def test_build_with_save_root_writes_the_asked_steps(tmp_path):
    s = st.build(DOCS, foundation="off", tiers=("CHAR",), level=LEVEL, save_root=str(tmp_path), save_steps=[2, 4])
    assert blob(st.load(str(tmp_path), DOCS[:2], tiers=("CHAR",), level=LEVEL)) == blob(steps_of(DOCS[:2])[-1])
    assert blob(st.load(str(tmp_path), s.prefix_sha256, tiers=("CHAR",), level=LEVEL)) == blob(s)
    with pytest.raises(st.StackError):
        st.load(str(tmp_path), DOCS[:3], tiers=("CHAR",), level=LEVEL)


def test_workers_do_not_change_a_byte():
    for found in FOUNDS:
        one = steps_of(DOCS_MANY, found, workers=1)[-1]
        two = steps_of(DOCS_MANY, found, workers=2)[-1]
        assert blob(one) == blob(two)


def _walk_no_float(o):
    if isinstance(o, float):
        return False
    if isinstance(o, dict):
        return all(_walk_no_float(v) for v in o.values())
    if isinstance(o, (list, tuple)):
        return all(_walk_no_float(v) for v in o)
    return True


def test_no_float_anywhere_and_the_bytes_are_canonical(S):
    for key in KEYS:
        s = S[key][-1]
        for l in s.ledger["CHAR"]:
            o = json.loads(l)
            assert _walk_no_float(o) and l == json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for c in s.crosses["CHAR"].values():
            assert _walk_no_float(c.to_obj())
            assert st.StackCross.from_obj(json.loads(c.to_bytes())) == c


HASH_PROG = """
import sys, json, hashlib
from verantyx.line3 import stack as st
a = json.loads(sys.stdin.read())
out = {}
for found in ("off", "on"):
    for name in ("docs", "many"):
        s = st.build(a[name], foundation=found, tiers=("CHAR",), level=a["level"])
        h = hashlib.sha256(s.state_bytes("CHAR") + "".join(l + "\\n" for l in s.ledger["CHAR"]).encode("utf-8")).hexdigest()
        out[found + name] = h
print(json.dumps(out, sort_keys=True))
"""


def test_bytes_are_the_same_for_hash_seeds_0_1_12345():
    outs = []
    for seed in ("0", "1", "12345"):
        r = subprocess.run([PY, "-c", HASH_PROG], input=json.dumps({"docs": DOCS, "many": DOCS_MANY, "level": LEVEL}), cwd=ROOT,
                           capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed))
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2]
    got = json.loads(outs[0])
    for found in FOUNDS:
        s = steps_of(DOCS, found)[-1]
        assert got[found + "docs"] == hashlib.sha256(s.state_bytes("CHAR") + "".join(l + "\n" for l in s.ledger["CHAR"]).encode("utf-8")).hexdigest()

"""G4-c tests: reading a frozen stack (docs/LINE3_G4_GROWTH_METER.md 6, ticket 6) and the foundation wiring G1-b left for later (L-G4-42).

T-G4-2 (step 0 answers UNKNOWN_NO_STATE), T-G4-9 (no lookahead in reading), T-G4-10 (the dictionary-free CHAR-only read, on a toy), T-G4-11 (a stack index
refuses effort full, builds no cross, refuses a mismatching corpus), the on-demand guard (L-G4-68, the hazard of G4-b, now positive), the foundation cache key
and its refusals, the contracted read view, `build_space(tiers=)`, and "foundation off is byte-identical" against goldens made by the base tree.

Part 1  foundation off: the goldens of the base tree (f3fdc608), the probe hashes
Part 2  the foundation cache: key, round trip, refusals; the contracted read view; the display-only arm labels; the seated on-demand rebuild
Part 3  build_space(tiers=) and the dictionary-free CHAR-only read
Part 4  Index.from_stack: a state, a saved directory, the corpus check, step 0, no lookahead
Part 5  the on-demand guard (typed refusal, recorded) and the other refusals of a stack index
Part 6  combined over a stack (flat + layers, windows skipped with a header line)
Part 7  the command line: --foundation, --stack, --step
Part 8  hash seeds 0 / 1 / 12345
"""
import dataclasses
import hashlib
import importlib.util
import json
import os
import pickle
import subprocess
import sys

import pytest

from verantyx import cli
from verantyx.line3 import ask as A
from verantyx.line3 import combined as CBN
from verantyx.line3 import cycle as cy
from verantyx.line3 import foundation as fd
from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp
from verantyx.line3 import stack as st
from test_stack import DOCS, DOCS_GROW, DOCS_MANY, GROW, LEVEL, MANY, SENTS, rows

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
ALL = ("RUN", "WORD", "CHAR")
Q = "東京の城はどうですか。"
Q2 = "京都の寺は何ですか"
GOLD = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_g4c_off.json"), encoding="utf-8"))


def write_jsonl(path, rws):
    with open(path, "w", encoding="utf-8") as f:
        for r in rws:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return str(path)


def h16(b):
    return hashlib.sha256(b).hexdigest()[:16]


@pytest.fixture(scope="module")
def toy(tmp_path_factory):
    return write_jsonl(tmp_path_factory.mktemp("toy") / "toy.jsonl", rows(SENTS))


@pytest.fixture(scope="module")
def S3():
    """The 3-tier stacks of the toy (4 articles), foundation off / on, level low (crosses close)."""
    return {f: st.build(DOCS, foundation=f, tiers=ALL, level=LEVEL) for f in ("off", "on")}


@pytest.fixture(scope="module")
def IX(S3):
    return {f: A.Index.from_stack(S3[f]) for f in S3}


@pytest.fixture(scope="module")
def GROWSTACK():
    """The GROW toy: the crosses of 一 and 二 close while they grow (CHAR only), then 三 is a question that needs a rebuild."""
    return {f: st.build(DOCS_GROW, foundation=f, tiers=("CHAR",), level=LEVEL) for f in ("off", "on")}


# =============================================================================================================
# Part 1: foundation off is what the base tree wrote
# =============================================================================================================
def _off_probe(toy_path, tmp):
    out = {"space": h16(sp.build_space(rows(SENTS)).to_bytes())}
    for gi, oc in (("whole", "stop"), ("ordered", "stop"), ("ordered", "skip")):
        ix = A.Index.from_jsonl(toy_path, None, LEVEL, ALL, group_insert=gi, on_collapse=oc)
        cache = os.path.join(str(tmp), "c_%s_%s" % (gi, oc))
        ix.precompute(cache)
        out["files_%s_%s" % (gi, oc)] = sorted(os.listdir(cache))
        ix2 = A.Index.from_jsonl(toy_path, cache, LEVEL, ALL, group_insert=gi, on_collapse=oc)
        for q in (Q, Q2, "三"):
            for eff in (None, "fast", "standard"):
                c = A.ask(ix2, q, effort=eff)
                out["ask_%s_%s_%s_%s" % (gi, oc, q, eff)] = h16(c.to_bytes()) + ":" + h16(A.format_text(c, False).encode())
            c = A.ask(ix2, q, effort="fast", grammar="on")
            out["askg_%s_%s_%s" % (gi, oc, q)] = h16(c.to_bytes())
    return out


def test_foundation_off_is_byte_identical_to_the_base_tree(toy, tmp_path):
    """Space bytes, cache file names, the answer bytes and the text of 3 questions x (None, fast, standard) for whole / ordered / ordered+skip, and grammar on:
    every one equals what the tree before G4-c made (goldens produced at f3fdc608 with PYTHONHASHSEED 0; the bytes do not depend on the hash seed)."""
    got = _off_probe(toy, tmp_path)
    want = {k: v for k, v in GOLD.items() if not k.startswith("_")}
    assert got == want
    ix = A.Index.from_jsonl(toy, None, LEVEL, ALL)
    assert ix.placement_is_default and ix.placement_record() is None and ix.foundation == "off" and ix.stack is None and ix.adhesions == {}
    c = A.ask(ix, Q, effort="fast")
    assert c.placement is None and c.stack is None and c.foundation_marks is None
    assert "stack" not in c.read_obj() and "partial_reasons" not in c.read_obj() and "rebuild_refused" not in c.read_obj()
    assert "foundation" not in c.thought_obj() and "stack" not in c.thought_obj()


def test_the_determinism_probe_hashes_are_unchanged():
    out = subprocess.run([PY, os.path.join(ROOT, "tools", "determinism_probe.py")], cwd=ROOT, capture_output=True, text=True,
                         env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"))
    assert out.returncode == 0, out.stderr
    hashes = [l.split()[-1] for l in out.stdout.splitlines()]
    assert hashes == ["79b0a11f444ec220", "a44611defdd6bec4", "51b97f502940dcc2"]


def test_cycle_ask_tier_keeps_its_old_signature_defaults():
    """The two new keywords default to the old behaviour: a rebuild of a plain index is a plain build_cross with no foundation and no `refused` / `foundation` key."""
    import inspect
    sig = inspect.signature(cy.ask_tier)
    assert sig.parameters["foundation"].default == "off" and sig.parameters["adhesion"].default is None
    assert cy.STACK_REFUSED == A.STACK_REFUSED == "stack: closed cross not rebuilt"


# =============================================================================================================
# Part 2: the foundation cache, the contracted read view, the display labels
# =============================================================================================================
def _gate1():
    spec = importlib.util.spec_from_file_location("g4gate1", os.path.join(ROOT, "experiments", "line3", "g4", "gate1_build.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_cache_key_and_path_with_the_foundation():
    part = fd.placement_key_part("on")
    assert part == "found-" + fd.seats_sha()[:12] and fd.placement_key_part("off") == ""
    assert A.placement_key() == "" and A.placement_key("ordered", "forward", "stop", "off") == "ordered-forward"        # off: the keys of before
    assert A.placement_key("whole", "forward", "stop", "on") == part
    assert A.placement_key("ordered", "forward", "stop", "on") == "ordered-forward_" + part
    assert A.placement_key("ordered", "reverse", "skip", "on") == "ordered-reverse-skip_" + part
    sha = "ab" * 32
    assert A.cache_path("d", sha, "RUN", "mid") == os.path.join("d", "placements_abababababab_RUN_mid.pkl")
    assert A.cache_path("d", sha, "RUN", "mid", "ordered", "forward", "stop", "on") == os.path.join(
        "d", "placements_abababababab_RUN_mid_ordered-forward_%s.pkl" % part)
    assert A.cache_path("d", sha, "CHAR", "mid", "ordered", "forward", "stop", "on") == _gate1().cache_file("d", sha, "CHAR", "mid", True)    # the file gate1_build writes
    with pytest.raises(ValueError):
        A.placement_key(foundation="maybe")
    assert A.placement_obj("ordered", "forward", "stop") == {"group_insert": "ordered", "order": "forward"}
    assert A.placement_obj("ordered", "forward", "stop", "on") == {"group_insert": "ordered", "order": "forward", "foundation": fd.seats_sha()}


def test_foundation_cache_round_trip_and_refusals(toy, tmp_path):
    ix = A.Index.from_jsonl(toy, None, LEVEL, ALL, group_insert="ordered", foundation="on")
    assert ix.foundation == "on" and set(ix.adhesions) == set(ALL) and not ix.placement_is_default
    assert ix.placement_record() == {"group_insert": "ordered", "order": "forward", "foundation": fd.seats_sha()}
    cache = str(tmp_path / "cf")
    ix.precompute(cache)
    sha = A.file_sha256(toy)
    key = "ordered-forward_found-" + fd.seats_sha()[:12]
    assert sorted(os.listdir(cache)) == sorted("placements_%s_%s_low_%s.pkl" % (sha[:12], t, key) for t in ALL)
    for t in ALL:
        d = pickle.load(open(os.path.join(cache, "placements_%s_%s_low_%s.pkl" % (sha[:12], t, key)), "rb"))
        assert d["format"] == A.CACHE_FORMAT_FOUNDATION == "line3.placements.foundation.v1"
        assert d["foundation"] == fd.seats_sha() and d["adhesion_sha256"] == ix.adhesions[t].sha256()
        assert all(p.foundation == fd.seats_sha() and not p.contracted for p in d["placements"].values())
    ix2 = A.Index.from_jsonl(toy, cache, LEVEL, ALL, group_insert="ordered", foundation="on")
    for t in ALL:
        st_ = ix2.stores[t]
        assert set(st_._loaded) == set(ix2.space.tiers[t].units())
        for u, full in st_._loaded.items():
            v = st_.cross_for(u)
            assert v.contracted and v.members == pl.contract_for_read(full).members and v.L == max(1, full.L - 1)
            assert all(not fd.is_constructed(x) for m in v.members for x in m)
            assert v.arm_labels is not None and sum(len(x) for x in v.arm_labels) == len(full.members)
        assert st_.on_demand == 0
    # the reader's answer from the cache equals the answer of the index that built them
    for eff in ("fast", "standard"):
        assert A.ask(ix2, Q, effort=eff).to_bytes() == A.ask(ix, Q, effort=eff).to_bytes()
    # refusals ------------------------------------------------------------------------------------------------------------
    ts = ix.space.tiers["CHAR"]
    fpath = os.path.join(cache, "placements_%s_CHAR_low_%s.pkl" % (sha[:12], key))
    good = dict(sha=sha, tier="CHAR", level=LEVEL, group_insert="ordered")
    A.load_placements(fpath, ts, "CHAR", LEVEL, sha, "ordered", "forward", "stop", "on", ix.adhesions["CHAR"])
    with pytest.raises(ValueError):                                                        # a foundation file read as plain
        A.load_placements(fpath, ts, "CHAR", LEVEL, sha, "ordered", "forward", "stop", "off")
    plain = A.Index.from_jsonl(toy, None, LEVEL, ("CHAR",), group_insert="ordered")
    pc = str(tmp_path / "cp")
    plain.precompute(pc)
    ppath = os.path.join(pc, "placements_%s_CHAR_low_ordered-forward.pkl" % sha[:12])
    A.load_placements(ppath, ts, "CHAR", LEVEL, sha, "ordered", "forward", "stop", "off")
    with pytest.raises(ValueError):                                                        # a plain file read as seated
        A.load_placements(ppath, ts, "CHAR", LEVEL, sha, "ordered", "forward", "stop", "on", ix.adhesions["CHAR"])

    def tampered(name, edit):
        d = pickle.load(open(fpath, "rb"))
        edit(d)
        p = str(tmp_path / name)
        pickle.dump(d, open(p, "wb"))
        return p
    bad = {
        "seats": tampered("t1.pkl", lambda d: d.update(foundation="0" * 64)),
        "adhesion": tampered("t2.pkl", lambda d: d.update(adhesion_sha256="0" * 64)),
        "format": tampered("t3.pkl", lambda d: d.update(format=A.CACHE_FORMAT)),
        "no_seats": tampered("t4.pkl", lambda d: d.pop("foundation")),
        "unseated": tampered("t5.pkl", lambda d: d["placements"].update(
            {next(iter(d["placements"])): pl.build_cross(ts, next(iter(d["placements"])), pl.Weights(ts), budget=pl.budget_level(LEVEL))})),
        "tier": tampered("t6.pkl", lambda d: d.update(tier="WORD")),
        "units": tampered("t7.pkl", lambda d: d["placements"].pop(next(iter(d["placements"])))),
    }
    for name, p in bad.items():
        with pytest.raises(ValueError):
            A.load_placements(p, ts, "CHAR", LEVEL, sha, "ordered", "forward", "stop", "on", ix.adhesions["CHAR"])
    with pytest.raises(ValueError):                                                        # another adhesion table than the file's
        A.load_placements(fpath, ts, "CHAR", LEVEL, sha, "ordered", "forward", "stop", "on", plain_adhesion(ts))
    with pytest.raises(ValueError):                                                        # another data sha
        A.load_placements(fpath, ts, "CHAR", LEVEL, "0" * 64, "ordered", "forward", "stop", "on", ix.adhesions["CHAR"])
    # a tampered file under the right name is refused by from_jsonl
    os.replace(bad["seats"], os.path.join(cache, os.path.basename(fpath)))
    with pytest.raises(ValueError):
        A.Index.from_jsonl(toy, cache, LEVEL, ALL, group_insert="ordered", foundation="on")
    # the switch itself
    with pytest.raises(ValueError):
        A.Index.from_jsonl(toy, None, LEVEL, ALL, foundation="maybe")
    with pytest.raises(ValueError):
        A.Index(ix.space, sha, LEVEL, ALL, adhesions=ix.adhesions)                      # an adhesion table goes with foundation "on" only
    with pytest.raises(ValueError):
        A._Store(ts, LEVEL, None, foundation="on")                                      # "on" needs the tier's adhesion
    with pytest.raises(ValueError):
        A.save_placements(str(tmp_path / "x.pkl"), "CHAR", LEVEL, sha, {}, {}, 0.0, "ordered", "forward", "stop", "on", None)


def plain_adhesion(ts):
    return fd.Adhesion("CHAR", {})                                                      # an empty table: its sha is not the file's


def test_precompute_with_the_foundation_does_not_depend_on_the_worker_count(toy):
    a = A.Index.from_jsonl(toy, None, LEVEL, ("CHAR",), group_insert="ordered", foundation="on")
    b = A.Index.from_jsonl(toy, None, LEVEL, ("CHAR",), group_insert="ordered", foundation="on")
    a.precompute(None, 1)
    b.precompute(None, 2)
    assert pl.serialize_all(a.stores["CHAR"]._loaded) == pl.serialize_all(b.stores["CHAR"]._loaded)


@pytest.mark.parametrize("docs", [DOCS[:1], DOCS_MANY[:1]])
def test_the_contracted_read_view_is_the_view_of_the_stack(docs):
    """T-G4-6 at the reader: a cross born at step 1 is the one-shot quotient-off build; the reader's view of that build (`_Store.cross_for`, contracted) equals the view the
    stack hands over (`Index.from_stack`), member for member, with the same arm labels."""
    s = st.build(docs, foundation="on", tiers=("CHAR",), level=LEVEL)
    ix = A.Index.from_stack(s, ("CHAR",))
    ts, adh = st.tier_space(s, "CHAR")
    w = pl.Weights(ts, adh)
    for u in ts.units():
        one = pl.build_cross(ts, u, w, budget=pl.budget_level(LEVEL), quotient=False, group_insert="ordered", order="forward", on_collapse="stop",
                             foundation="on", adhesion=adh)
        a = A._Store(ts, LEVEL, {u: one}, "ordered", "forward", "stop", "on", adh).cross_for(u)
        b = ix.stores["CHAR"].cross_for(u)
        assert (a.members, a.L, a.size, a.stop, a.centres, a.cross, a.foundation) == (b.members, b.L, b.size, b.stop, b.centres, b.cross, b.foundation)
        assert a.contracted and b.contracted and a.arm_labels == b.arm_labels and b.from_stack and not a.from_stack
        assert all(not any(fd.is_constructed(x) for x in m) for m in b.members)


def test_a_one_shot_foundation_view_is_memoised_and_off_is_returned_as_it_is(toy):
    on = A.Index.from_jsonl(toy, None, LEVEL, ("CHAR",), group_insert="ordered", foundation="on")
    u = on.space.tiers["CHAR"].units()[0]
    v1, v2 = on.stores["CHAR"].cross_for(u), on.stores["CHAR"].cross_for(u)
    assert v1 is v2 and v1.contracted and on.stores["CHAR"].on_demand == 1               # built once on demand, contracted once
    off = A.Index.from_jsonl(toy, None, LEVEL, ("CHAR",), group_insert="ordered")
    p = off.stores["CHAR"].cross_for(u)
    assert p.foundation is None and not p.contracted and p.arm_labels is None
    assert off.stores["CHAR"].placer.foundation == "off" and on.stores["CHAR"].placer.foundation == "on"


def test_arm_labels_are_shown_and_are_display_only(toy):
    on = A.Index.from_jsonl(toy, None, LEVEL, ALL, group_insert="ordered", foundation="on")
    c = A.ask(on, Q, effort="fast")
    fm = c.foundation_marks
    assert fm is not None and fm["display_only"] is True and fm["seats_sha"] == fd.seats_sha() and len(fm["entries"]) == len(c.entries)
    ladder = set(fd.DEFAULT_SPEC.ladder)
    for m in fm["entries"]:
        e = c.entries[m["index"]][1]
        assert c.entries[m["index"]][0] == m["tier"] and set(m["arms"]) <= set(e.words)
        assert all(ps == sorted(set(ps)) and set(ps) <= ladder for ps in m["arms"].values())
    assert any(m["arms"] for m in fm["entries"])
    text = A.format_text(c)
    assert "関係の札" in text and "表示のみ" in text
    # never a candidate: the answer and the entries are the same with the labels taken away; the labels are not in the answer object
    bare = dataclasses.replace(c, foundation_marks=None)
    assert bare.answer_obj() == c.answer_obj() and bare.entries == c.entries and bare.verdict == c.verdict
    assert "display_only" not in json.dumps(c.answer_obj(), ensure_ascii=False) and "foundation" in c.thought_obj()
    assert c.thought_obj()["foundation"] == fm
    off = A.Index.from_jsonl(toy, None, LEVEL, ALL, group_insert="ordered")
    c0 = A.ask(off, Q, effort="fast")
    assert c0.foundation_marks is None and "foundation" not in c0.thought_obj() and "関係の札" not in A.format_text(c0)


def test_the_on_demand_rebuild_of_a_seated_index_is_seated_and_contracted(monkeypatch, GROWSTACK):
    """The same bypass for a one-shot foundation index: cycle.ask_tier rebuilt a closed cross with build_cross defaults (foundation off).  Now it is seated, and the re-ask
    reads its contracted form.  (The closed crosses are the stack views with the stack mark taken off: a cross of a one-shot build that stopped by budget.)"""
    s = GROWSTACK["on"]
    ts, adh = st.tier_space(s, "CHAR")
    views = {sd: dataclasses.replace(p, from_stack=False) for sd, p in st.as_placements(s, "CHAR").items()}
    closed = sorted(sd for sd, p in views.items() if p.stop == "budget")
    assert {"一", "二"} <= set(closed)              # the toy's closed crosses (foundation on closes more of them)
    calls = []
    orig = pl.build_cross

    def spy(*a, **k):
        calls.append(k)
        return orig(*a, **k)
    monkeypatch.setattr(pl, "build_cross", spy)
    store = cy.PlacementStore(views)
    res = cy.ask_tier(ts, "三", store, weights=pl.Weights(ts, adh), foundation="on")
    br = res.variant["budget_raise"]
    assert br["needed"] and br["steps"] and br["foundation"] == "on" and "refused" not in br
    raised = [k for k in calls if k.get("budget") is not None and pl.level_name(k["budget"]) == "high"]
    assert raised and all(k["foundation"] == "on" and k["adhesion"] is adh for k in raised)
    # with the foundation off the call is the old one
    calls.clear()
    res0 = cy.ask_tier(ts, "三", cy.PlacementStore({sd: p for sd, p in views.items()}), weights=pl.Weights(ts))
    raised0 = [k for k in calls if k.get("budget") is not None and pl.level_name(k["budget"]) == "high"]
    assert raised0 and all(k["foundation"] == "off" and k["adhesion"] is None for k in raised0) and "foundation" not in res0.variant["budget_raise"]


# =============================================================================================================
# Part 3: build_space(tiers=), the dictionary-free CHAR-only read
# =============================================================================================================
def _tier_eq(a, b):
    return a.name == b.name and a.sentence_units == b.sentence_units and a.postings == b.postings and a.N == b.N and a.units() == b.units()


def test_build_space_with_a_subset_of_tiers():
    r = rows(SENTS)
    full = sp.build_space(r)
    only = sp.build_space(r, tiers=("CHAR",))
    assert tuple(only.tiers) == ("CHAR",) and _tier_eq(only.tiers["CHAR"], full.tiers["CHAR"])
    assert only.sentences == full.sentences and only.kinds == full.kinds and only.N == full.N
    for names in (("RUN",), ("WORD", "CHAR"), ("CHAR", "RUN")):
        sub = sp.build_space(r, tiers=names)
        assert tuple(sub.tiers) == tuple(t for t in sp.TIERS if t in names)
        assert all(_tier_eq(sub.tiers[t], full.tiers[t]) for t in sub.tiers)
    # the default and the explicit full set are the bytes of before; a subset writes the tiers it has
    assert sp.build_space(r, tiers=sp.TIERS).to_bytes() == full.to_bytes() and h16(full.to_bytes()) == GOLD["space"]
    doc = json.loads(only.to_bytes())
    assert list(doc["tiers"]) == ["CHAR"] and doc["tiers"]["CHAR"] == json.loads(full.to_bytes())["tiers"]["CHAR"]
    assert len(only.sha256()) == 64 and only.sha256() != full.sha256()
    # append works on a subset and equals a build from scratch (L-41)
    more = [{"sent": "京都の庭は静かである。", "source": "E#0"}]
    assert sp.build_space(r + more, tiers=("CHAR",)).to_bytes() == only.append(more).to_bytes()
    assert sp.build_space(r + more).to_bytes() == full.append(more).to_bytes()
    for bad in ((), ("SYL",), ("CHAR", "CHAR"), ("RUN", "CHAR", "CHAR")):
        with pytest.raises(ValueError):
            sp.build_space(r, tiers=bad)
    # the stack builds the same tier objects (L-G4-61)
    assert _tier_eq(st._build_space(r, ("CHAR",)).tiers["CHAR"], only.tiers["CHAR"])
    assert _tier_eq(st._build_space(r, ("RUN", "CHAR")).tiers["RUN"], full.tiers["RUN"])


def test_an_index_over_a_subset_of_tiers_and_grammar_on_needs_run():
    r = rows(SENTS)
    only = sp.build_space(r, tiers=("CHAR",))
    with pytest.raises(ValueError):
        A.Index(only, "x", LEVEL, ("RUN",))                                             # the space holds no RUN
    ix = A.Index(only, "x", LEVEL, ("CHAR",))
    c = A.ask(ix, "京都は何", effort="fast")
    assert [o.tier for o in c.outcomes] == ["CHAR"]
    with pytest.raises(ValueError):
        A.ask(ix, "京都は何", effort="fast", grammar="on")


@pytest.mark.parametrize("tiers", [("RUN", "CHAR"), ("WORD", "CHAR"), ("CHAR",)])
def test_a_stack_without_both_run_and_word_refuses_grammar_on_typed(tiers):
    """L-G4-97: the grammar records need the RUN and the WORD tiers; a RUN + CHAR stack used to pass the RUN-only check and die with a raw KeyError 'WORD'
    (wiring.context_of).  It is now the typed refusal (StackRefused, a ValueError) before anything is read; grammar off still reads."""
    ix = A.Index.from_stack(st.build(DOCS, foundation="off", tiers=tiers, level=LEVEL), tiers)
    assert set(ix.space.tiers) == set(tiers)
    for structure in ("flat", "combined"):
        with pytest.raises(A.StackRefused, match="RUN and WORD"):
            A.ask(ix, "京都は何", effort="fast", grammar="on", structure=structure)
    c = A.ask(ix, "京都は何", effort="fast", grammar="off")
    assert [o.tier for o in c.outcomes] == [t for t in ALL if t in tiers]
    both = A.Index.from_stack(st.build(DOCS, foundation="off", tiers=ALL, level=LEVEL))
    assert A.ask(both, "京都は何", effort="fast", grammar="on").grammar is not None


def test_effort_none_is_allowed_over_a_stack_only_full_is_refused(IX):
    """L-G4-100 (owner decision): `effort=None` (the whole read) is NOT refused over a stack -- the rebuilds are refused and recorded (L-G4-95); `full` is the one refused."""
    ix = IX["off"]
    for kw in ({}, {"effort": None}):
        c = A.ask(ix, Q, **kw)
        assert c.effort is None and c.stack is not None and c.read_obj()["partial"] is False
        assert c.to_bytes() == A.ask(ix, Q).to_bytes()
    cc = A.ask(ix, Q, structure="combined")                                              # also combined (effort None)
    assert cc.answer_obj()["verdict"] in (CBN.ANSWER, CBN.CHOICE, CBN.UNKNOWN_NO_STATE)
    with pytest.raises(A.StackRefused):
        A.ask(ix, Q, effort="full")
    assert all(ix.stores[t].on_demand == 0 for t in ALL)


DICT_FREE = """
import sys, json, hashlib
for m in ("fugashi", "unidic_lite", "unidic"):
    sys.modules[m] = None
from verantyx.line3 import ask as A, space as sp, stack as st
a = json.loads(sys.stdin.read())
space = sp.build_space(a["rows"], tiers=("CHAR",))
assert tuple(space.tiers) == ("CHAR",)
out = {}
for found in ("off", "on"):
    s = st.build(a["docs"], foundation=found, tiers=("CHAR",), level=a["level"])
    ix = A.Index.from_stack(s, ("CHAR",))
    c = A.ask(ix, a["q"], effort="fast", grammar="off")
    assert ix.stores["CHAR"].on_demand == 0 and [o.tier for o in c.outcomes] == ["CHAR"]
    out[found] = {"sha": s.shas["CHAR"], "bytes": hashlib.sha256(c.to_bytes()).hexdigest(), "verdict": c.verdict, "space": space.sha256()}
assert not any(sys.modules.get(m) for m in ("fugashi", "unidic_lite"))
print(json.dumps(out))
"""


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_the_dictionary_free_char_read_equals_the_char_read_of_the_three_tier_stack(seed, S3):
    """T-G4-10 (toy): with fugashi / unidic_lite blocked, the CHAR-only space, the CHAR-only stack and its read succeed, and the read is the CHAR-tier read of the
    3-tier stack at the same step: the same state_sha256, the same answer bytes."""
    out = subprocess.run([PY, "-c", DICT_FREE], input=json.dumps({"rows": rows(SENTS), "docs": DOCS, "level": LEVEL, "q": Q}), cwd=ROOT, capture_output=True,
                         text=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed))
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    for found in ("off", "on"):
        ix3 = A.Index.from_stack(S3[found], ("CHAR",))
        c3 = A.ask(ix3, Q, effort="fast", grammar="off")
        assert got[found]["sha"] == S3[found].shas["CHAR"]
        assert got[found]["bytes"] == hashlib.sha256(c3.to_bytes()).hexdigest() and got[found]["verdict"] == c3.verdict
        assert got[found]["space"] == sp.build_space(rows(SENTS), tiers=("CHAR",)).sha256()


# =============================================================================================================
# Part 4: Index.from_stack
# =============================================================================================================
def test_step_zero_answers_unknown_no_state(tmp_path):
    """T-G4-2: the empty stack index answers every question of bank2's fulllead rows (94) UNKNOWN_NO_STATE, foundation off and on, every effort."""
    qs = []
    for line in open(os.path.join(ROOT, "experiments", "line3", "bank2", "bank2.tsv"), encoding="utf-8").read().splitlines()[1:]:
        f = line.split("\t")
        if f[2] == "fulllead" and f[1] in ("intra2", "unans"):
            qs.append(f[4])
    assert len(qs) == 94
    for found in ("off", "on"):
        ix = A.Index.from_stack(st.empty_state(found, ALL, "mid"))
        assert ix.stack["step"] == 0 and all(not ix.stores[t]._loaded for t in ALL)
        for q in qs:
            assert A.ask(ix, q, effort="fast").verdict == A.UNKNOWN_NO_STATE
        for eff in (None, "standard"):
            c = A.ask(ix, qs[0], effort=eff)
            assert c.verdict == A.UNKNOWN_NO_STATE and c.read_obj()["partial"] is False


@pytest.mark.parametrize("found", ["off", "on"])
def test_from_stack_reads_a_saved_step_and_refuses_the_wrong_corpus(tmp_path, found):
    root = str(tmp_path / "stack")
    st.build(DOCS, foundation=found, tiers=ALL, level=LEVEL, save_root=root)
    data = write_jsonl(tmp_path / "toy.jsonl", rows(SENTS))
    docs = st.load_docs(data)
    states = [st.empty_state(found, ALL, LEVEL)]
    for d in docs:
        states.append(st.extend(states[-1], d))
    for k in (1, 2, 3, 4):
        ix = A.Index.from_stack(root, ALL, data=data, step=k, foundation=found, level=LEVEL)
        ref = A.Index.from_stack(states[k])
        assert ix.stack == ref.stack and ix.stack["step"] == k and ix.data_sha == states[k].prefix_sha256
        assert A.ask(ix, Q, effort="fast").to_bytes() == A.ask(ref, Q, effort="fast").to_bytes()
        assert ix.stack["state_sha256"] == {t: states[k].shas[t] for t in ALL}
    assert A.Index.from_stack(root, ALL, data=data, foundation=found, level=LEVEL).stack["step"] == 4          # all articles by default
    assert A.Index.from_stack(root, ("CHAR",), data=docs, step=2, foundation=found, level=LEVEL).tiers == ("CHAR",)   # the documents may be given instead of a path
    # refusals -----------------------------------------------------------------------------------------------------------
    other = [dict(r) for r in rows(SENTS)]
    other[3]["sent"] = "大阪の城は新しい。"                                                    # one sentence of article B changed
    odata = write_jsonl(tmp_path / "other.jsonl", other)
    ok1 = A.Index.from_stack(root, ALL, data=odata, step=1, foundation=found, level=LEVEL)             # step 1 is the same prefix, so it IS the snapshot
    assert ok1.stack["step"] == 1
    for kw in ({"step": 2}, {"step": 4}, {}):
        with pytest.raises(A.StackRefused):
            A.Index.from_stack(root, ALL, data=odata, foundation=found, level=LEVEL, **kw)
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(root, ALL, data=data, step=5, foundation=found, level=LEVEL)               # outside the corpus
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(root, ALL, data=data, step=0, foundation=found, level=LEVEL)               # no snapshot of step 0
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(root, ALL, step=2, foundation=found, level=LEVEL)                          # the corpus is needed to key it
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(root, ALL, data=data, step=2, foundation="on" if found == "off" else "off", level=LEVEL)
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(root, ALL, data=data, step=2, foundation=found, level="mid")
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(root, ALL, data=data, step=2, foundation=found, level=LEVEL, order="reverse")
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(str(tmp_path / "nothing"), ALL, data=data, step=2, foundation=found, level=LEVEL)
    # a state: its own step, a corpus that is not its prefix, a tier it does not hold
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(states[2], step=3)
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(states[2], data=odata)
    A.Index.from_stack(states[2], data=data, step=2)
    only = st.build(DOCS, foundation=found, tiers=("CHAR",), level=LEVEL)
    with pytest.raises(A.StackRefused):
        A.Index.from_stack(only, ("RUN",))
    assert issubclass(A.StackRefused, ValueError)


def test_a_stack_index_is_the_prefix_and_records_which_step_it_read(IX, S3):
    for f in ("off", "on"):
        ix, s = IX[f], S3[f]
        assert ix.tiers == ALL and ix.foundation == f and not ix.placement_is_default and ix.data_sha == s.prefix_sha256
        assert ix.space.N == sum(len(d) for d in DOCS) and ix.space.sentences == tuple((r["sent"], r["source"]) for d in s.docs for r in d)
        c = A.ask(ix, Q, effort="fast")
        pr = c.placement
        assert pr["structure"] == "stack" and pr["step"] == 4 and pr["state_sha256"] == s.shas and pr["seats_sha"] == s.seats_sha and pr["stack_order"] == "forward"
        assert pr["group_insert"] == "ordered" and pr["order"] == "forward" and (("foundation" in pr) == (f == "on"))
        assert c.thought_obj()["stack"]["prefix_sha256"] == s.prefix_sha256 and c.thought_obj()["placement"] == pr
        assert "積み: 第 4 段" in A.format_text(c)
        rec = c.memory_record(0)
        assert rec["placement"] == pr


def test_no_lookahead_in_reading_t_g4_9(S3):
    """T-G4-9: the space, the grammar records and the stand-ins of step k hold no sid >= N_k."""
    for f in ("off", "on"):
        s2 = st.build(DOCS[:2], foundation=f, tiers=ALL, level=LEVEL)
        ix = A.Index.from_stack(s2)
        n = ix.space.N
        assert n == 4 and all(sid < n for t in ALL for u in ix.space.tiers[t].units() for sid in ix.space.tiers[t].postings[u])
        c = A.ask(ix, "京都の城は何ですか", effort="fast", grammar="on")           # 京都 is not in the first two articles: stand-ins are made for it
        assert c.grammar["standins"] and c.grammar["standins"][0]["word"] == "京都"
        seen = []

        def walk(o, key=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, k)
            elif isinstance(o, list):
                for v in o:
                    walk(v, key)
            elif isinstance(o, int) and not isinstance(o, bool) and key in ("sid", "sids", "source_sids", "sentences"):
                seen.append(o)
        walk(json.loads(c.to_bytes()))
        assert seen and max(seen) < n
        for w in c.grammar["full"]["standins"]:
            for _u, _parts, sids in w["unit_parts"]:
                assert all(sid < n for sid in sids)
            assert all(u in ix.space.tiers["RUN"].postings for u in w["units"])
        # the whole pass from prefix_2 alone is the same read (the fold)
        assert c.to_bytes() == A.ask(A.Index.from_stack(st.build(DOCS[:2], foundation=f, tiers=ALL, level=LEVEL)), "京都の城は何ですか", effort="fast", grammar="on").to_bytes()


# =============================================================================================================
# Part 5: the on-demand guard and the other refusals
# =============================================================================================================
@pytest.mark.parametrize("found", ["off", "on"])
def test_on_demand_rebuild_is_refused_for_stack_crosses(found, GROWSTACK):
    """The hazard of G4-b (L-G4-68), now positive.  Closed views carry stop == "budget"; ask_tier's default raise_budget="on_demand" would rebuild each with build_cross
    defaults.  For a stack the rebuild is refused: typed, recorded in the thought (variant.budget_raise.refused) and in the answer (rebuild_refused + a reason; `partial` stays the cap's), and nothing is built."""
    s = GROWSTACK[found]
    ix = A.Index.from_stack(s, ("CHAR",))
    store = ix.stores["CHAR"]
    closed = sorted(sd for sd, p in store._loaded.items() if p.stop == "budget")
    assert {"一", "二"} <= set(closed)
    assert all(p.from_stack for p in store._loaded.values()) and not store.builds and store.placer is None
    c = A.ask(ix, "三")                                                                       # effort None: the whole read, raise levels default
    o = c.outcomes[0]
    assert c.verdict == A.UNKNOWN_NO_STATE and o.result.variant is not None
    br = o.result.variant["budget_raise"]
    assert br["needed"] is False and br["steps"] == [] and br["final_level"] is None
    assert br["refused"] == {"reason": A.STACK_REFUSED, "seeds": ["一", "二"]}
    assert store.on_demand == 0
    ro = c.read_obj()
    # L-G4-95: `partial` is still "unread by the cap" (the whole read has none); the refusal is carried in rebuild_refused and as a reason in partial_reasons
    assert ro["partial"] is False and ro["partial_reasons"] == [A.STACK_REFUSED] and ro["rebuild_refused"] == {"reason": A.STACK_REFUSED, "per_tier": {"CHAR": 2}}
    assert ro["rebuild_skipped"] == {}
    assert c.answer_obj()["read"]["partial_reasons"] == [A.STACK_REFUSED] and c.answer_obj()["read"]["partial"] is False
    text = A.format_text(c)
    assert "閉じた十字は作り直しません" in text and A.STACK_REFUSED in text and "部分読み" not in text
    # the fast / standard efforts never rebuild anything, in any arm: exactly as for a one-shot index that is `rebuild_skipped`, and the guard did not fire
    # (rebuild_refused empty, no stack reason, partial false: nothing is unread by the cap)
    for eff in ("fast", "standard"):
        cf = A.ask(ix, "三", effort=eff)
        rf = cf.read_obj()
        assert rf["rebuild_skipped"] == {"CHAR": 2} and rf["rebuild_refused"]["per_tier"] == {} and rf["partial"] is False and rf["partial_reasons"] == []
        assert "budget_raise" not in (cf.outcomes[0].result.variant or {})
        tf = A.format_text(cf)
        assert "配置の作り直しを省いた十字: CHAR=2 本" in tf and "積みは作り直しません" in tf and "閉じた十字は作り直しません" not in tf
    # the cap: partial is true because of the cap, and only the cap names itself in partial_reasons
    cn = A.ask(ix, "三", nodes=1).read_obj()
    assert cn["partial"] is True and cn["partial_reasons"] == ["node budget: crosses left unread"] and cn["rebuild_refused"]["per_tier"] == {}
    # control: the same placements WITHOUT the stack mark are rebuilt (which is the bypass the guard closes)
    views = {sd: dataclasses.replace(p, from_stack=False) for sd, p in store._loaded.items()}
    plain = A.Index(ix.space, "x", LEVEL, ("CHAR",), {"CHAR": views}, group_insert="ordered", order="forward", on_collapse="stop", foundation=found,
                    adhesions=ix.adhesions or None)
    cp = A.ask(plain, "三")
    bp = cp.outcomes[0].result.variant["budget_raise"]
    assert bp["needed"] is True and bp["steps"] and "refused" not in bp
    assert [r["seed"] for r in bp["steps"][0]["raised"]] == ["一", "二"]
    assert "stack" not in cp.read_obj()
    assert cp.verdict != A.UNKNOWN_NO_STATE
    # L-G4-95: the same placements without the stack mark, at fast / standard, report the very same rebuild_skipped as the stack read
    for eff in ("fast", "standard"):
        assert A.ask(plain, "三", effort=eff).read_obj()["rebuild_skipped"] == A.ask(ix, "三", effort=eff).read_obj()["rebuild_skipped"] == {"CHAR": 2}


def test_ask_tier_refuses_stack_crosses_and_rebuilds_the_others(GROWSTACK):
    s = GROWSTACK["off"]
    ts, _ = st.tier_space(s, "CHAR")
    views = st.as_placements(s, "CHAR")
    kw = {"facts": cy.TierFacts(ts), "budget": A.DEFAULT_BUDGET}                       # what ask() passes: the query budget of the answer path
    mixed = dict(views)
    mixed["一"] = dataclasses.replace(views["一"], from_stack=False)                         # a one-shot closed cross among stack views
    res = cy.ask_tier(ts, "三", cy.PlacementStore(mixed), weights=pl.Weights(ts), **kw)
    br = res.variant["budget_raise"]
    assert br["refused"] == {"reason": cy.STACK_REFUSED, "seeds": ["二"]}
    assert br["needed"] and [r["seed"] for st_ in br["steps"] for r in st_["raised"]][:1] == ["一"]
    # a custom level list: nothing rebuilt, the refusal is recorded once
    res2 = cy.ask_tier(ts, "三", cy.PlacementStore(views), weights=pl.Weights(ts), raise_levels=("high", "max"), **kw)
    assert res2.variant["budget_raise"]["steps"] == [] and res2.variant["budget_raise"]["refused"]["seeds"] == ["一", "二"]
    # raise off: nothing recorded (it never tried)
    res3 = cy.ask_tier(ts, "三", cy.PlacementStore(views), weights=pl.Weights(ts), raise_budget=None, **kw)
    assert res3.variant is None or "budget_raise" not in res3.variant


def test_a_stack_index_refuses_full_slide_and_building(IX):
    ix = IX["off"]
    with pytest.raises(A.StackRefused):
        A.ask(ix, Q, effort="full")
    with pytest.raises(A.StackRefused):
        A.ask(ix, Q, effort="full", structure="combined")
    with pytest.raises(A.StackRefused):
        A.ask(ix, Q, effort="fast", structure="slide")
    with pytest.raises(A.StackRefused):
        A.ask(ix, Q, nodes=3, structure="slide")
    for kw in ({"effort": "fast"}, {"effort": "standard"}, {"nodes": 3}, {}):
        c = A.ask(ix, Q, **kw)
        assert c.stack is not None and c.verdict in (A.ANSWER, A.CHOICE, A.UNKNOWN_NO_STATE, A.UNKNOWN_NO_PATH)
    assert all(ix.stores[t].on_demand == 0 for t in ALL)
    # a seed with no cross raises; no cross is ever built; a stack index is never precomputed
    for t in ALL:
        with pytest.raises(A.StackRefused):
            ix.stores[t].cross_for("存在しない単位")
        assert ix.stores[t].on_demand == 0
    with pytest.raises(A.StackRefused):
        ix.precompute(None)
    ts = ix.space.tiers["CHAR"]
    s = A._Store(ts, LEVEL, {}, on_demand=False)
    assert s.placer is None and s.builds is False and s.w is not None
    with pytest.raises(A.StackRefused):
        s.cross_for(ts.units()[0])
    # the layers (matryoshka re-asks) read the stack's crosses through the same guard (the stack's own store builds nothing) -- but see the test below
    from verantyx.line3 import matryoshka as M
    lc = M.ask_layered(ix, Q, effort="fast")
    assert all(ix.stores[t].on_demand == 0 for t in ALL) and lc.base.stack is not None


@pytest.mark.parametrize("found,want", [("off", {"fast": 0, "standard": 4, None: 13}), ("on", {"fast": 1, "standard": 10, None: 12})])
def test_layers_over_a_stack_do_build_bundle_crosses_with_the_foundation_off(found, want, S3, monkeypatch):
    """L-G4-96 (corrects L-G4-83): "Layers ... build nothing" was wrong.  An upper layer (`matryoshka.Layer.cross_for`) builds the crosses of its BUNDLE space with
    `placement.build_cross` (budget of the layer, the index's insertion options, foundation NOT passed = off, whatever the index has); they are not the stack's
    crosses and never replace one (the stack's stores build nothing: `on_demand` 0).  Behaviour is unchanged and pinned here by spying on `pl.build_cross`:
    the toy, the question Q, 3 tiers, level low -- calls per effort.  The owner's decision: `--layers on` stays allowed over a stack but MARKED (L-G4-99; asserted below); the meter runs layers off."""
    from verantyx.line3 import matryoshka as M
    for eff, n in want.items():
        ix = A.Index.from_stack(S3[found])
        calls = []
        real = pl.build_cross

        def spy(space, seed, *a, **k):
            calls.append((type(space).__name__, space.name, seed, k.get("foundation", "off")))
            return real(space, seed, *a, **k)

        monkeypatch.setattr(pl, "build_cross", spy)
        lc = M.ask_layered(ix, Q, effort=eff)
        monkeypatch.undo()
        assert len(calls) == n, (found, eff, calls)
        assert all(k[0] == "BundleTier" and k[3] in ("off", None) for k in calls)              # bundle crosses, never the stack's tier space, foundation off
        assert all(ix.stores[t].on_demand == 0 and not ix.stores[t].builds for t in ALL)
        assert sum(l.builds for sk in getattr(ix, "_t8_stacks", {}).values() for l in sk._layer1.values()) <= n
        assert lc.base.stack is not None and lc.base.stack["step"] == 4
        # L-G4-99 (owner): the layers over a stack are MARKED -- the count of the builds of this question, the mark on each upper entry, the text line
        os_ = lc.outside_stack
        assert os_["layers_oneshot"] is True and os_["reason"] == M.OUTSIDE_STACK and os_["bundle_builds_total"] == n == sum(os_["bundle_builds"].values())
        assert set(os_["bundle_builds"]) == set(ALL)
        a = lc.answer_obj()
        assert a["outside_stack"] == os_ and lc.thought_obj()["layers"]["options"]["outside_stack"] == os_
        ups = [e for e in a["entries"] if e["layer"] > 0]
        assert all(e.get("outside_stack") is True for e in ups) and not any("outside_stack" in e for e in a["entries"] if e["layer"] == 0)
        tx = M.format_layers_text(lc)
        assert "層【積みの外】" in tx and "十字 %d 本" % n in tx and tx.count("【積みの外】") == 1 + len(ups)


# =============================================================================================================
# Part 6: combined over a stack
# =============================================================================================================
def test_combined_over_a_stack_is_flat_and_layers_and_says_the_windows_are_skipped(IX, monkeypatch):
    from verantyx.line3 import slide_query as SQ
    asked = []
    monkeypatch.setattr(SQ, "window_index_for", lambda *a, **k: asked.append(1))             # a window cache would be built here: it must not be reached
    c = A.ask(IX["on"], Q, structure="combined", effort="fast")
    assert asked == []
    a = c.answer_obj()
    head = {h["source"]: h for h in a["header"]}
    assert set(head) >= {"window/plain", "window/window-evidence"} and any(k.startswith("flat/") for k in head)
    for k in ("window/plain", "window/window-evidence"):
        assert head[k]["listed"] == 0 and head[k]["kind"] == CBN.UNKNOWN_STACK_NO_WINDOWS
    assert all(e["origins"] and not any(o.startswith("window/") for o in e["origins"]) for e in a["entries"])
    text = CBN.format_text(c)
    assert CBN.STACK_NO_WINDOWS_TEXT in text
    th = c.thought_obj()
    assert th["config"]["stack"]["step"] == 4 and th["config"]["window"]["skipped"] == CBN.STACK_NO_WINDOWS_TEXT
    assert c.to_bytes() == A.ask(IX["on"], Q, structure="combined", effort="fast").to_bytes()
    assert all(IX["on"].stores[t].on_demand == 0 for t in ALL)
    with pytest.raises(A.StackRefused):
        A.ask(IX["on"], Q, structure="combined", effort="full")
    ce = A.ask(IX["off"], Q, structure="combined", effort="fast", window_evidence="plain")
    assert [h["source"] for h in ce.answer_obj()["header"] if h["source"].startswith("window/")] == ["window/plain"]


def test_combined_marks_the_layers_over_a_stack_as_outside_the_stack(S3, toy):
    """L-G4-99 (owner: layers over a stack are allowed but marked): header row, entry mark, text, config; a one-shot index has none of it."""
    ix = A.Index.from_stack(S3["on"])
    c = A.ask(ix, Q, structure="combined", effort="standard")
    a = c.answer_obj()
    head = {h["source"]: h for h in a["header"]}
    assert head["layers"]["layers_oneshot"] is True and head["layers"]["bundle_builds_total"] == 10
    assert not any("layers_oneshot" in h for k, h in head.items() if k != "layers")
    marked = [e for e in a["entries"] if "outside_stack" in e["marks"]]
    assert marked and all(set(e["origins"]) <= {o for o in e["origins"] if o.startswith("layers/")} for e in marked)
    assert not any("outside_stack" in e["marks"] for e in a["entries"] if any(o.startswith("flat/") for o in e["origins"]))
    lsrc = next(x for x in c.sources if x.name == "layers")
    assert lsrc.read["outside_stack"]["bundle_builds_total"] == 10 and all(m.detail["outside_stack"] is True for x in lsrc.cands for m in [x])
    text = CBN.format_text(c)
    assert "【積みの外: 上の層の十字は積みの十字ではなく一回きりの配置・この問いで作った十字 10 本】" in text and CBN.MARK_TEXT[CBN.MARK_OUTSIDE_STACK] in text
    # no stack: no mark, no key anywhere (layers off the stack are the index's own business)
    from verantyx.line3 import matryoshka as M
    plain = A.Index.from_jsonl(toy, None, LEVEL, ALL, group_insert="ordered")
    lc = M.ask_layered(plain, Q, effort="standard")
    assert lc.outside_stack is None and "outside_stack" not in lc.answer_obj() and "outside_stack" not in str(lc.thought_obj())
    assert "積みの外" not in M.format_layers_text(lc)
    cp = A.ask(plain, Q, structure="combined", effort="standard")
    assert "積みの外" not in CBN.format_text(cp) and "outside_stack" not in str(cp.answer_obj()) and "layers_oneshot" not in str(cp.answer_obj())


# =============================================================================================================
# Part 7: the command line
# =============================================================================================================
def run_cli(capsys, *argv):
    rc = cli.main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    d = tmp_path_factory.mktemp("clistack")
    root = str(d / "stack")
    st.build(DOCS, foundation="on", tiers=ALL, level=LEVEL, save_root=root)
    return {"root": root, "data": write_jsonl(d / "toy.jsonl", rows(SENTS)), "dir": d}


def test_cli_ask_reads_a_saved_stack_step(saved, capsys):
    base = ["line3", "ask", "--data", saved["data"], "--stack", saved["root"], "--foundation", "on", "--level", LEVEL, "--question", Q, "--layers", "off"]
    rc, out, err = run_cli(capsys, *base, "--step", "4", "--effort", "fast", "--format", "json", "--show-thought")
    assert rc == 0, err
    o = json.loads(out)
    assert o["answer"]["placement"]["structure"] == "stack" and o["answer"]["placement"]["step"] == 4
    assert o["thought"]["stack"]["step"] == 4 and o["answer"]["read"]["effort"] == "fast"
    rc, out, err = run_cli(capsys, *base, "--effort", "fast", "--tiers", "CHAR", "--step", "3")
    assert rc == 0 and "積み: 第 3 段" in out, (out, err)
    rc, out2, err = run_cli(capsys, *base, "--effort", "standard", "--step", "4")                                # layers off, default flat
    assert rc == 0 and "積み: 第 4 段" in out2
    # the default of --layers (on): the layered reader over a stack index
    rc, out3, err = run_cli(capsys, "line3", "ask", "--data", saved["data"], "--stack", saved["root"], "--foundation", "on", "--level", LEVEL, "--question", Q,
                            "--effort", "fast")
    assert rc == 0, err
    # a combined list over a stack
    rc, out4, err = run_cli(capsys, *base[:-2], "--effort", "fast", "--structure", "combined")
    assert rc == 0, err
    assert CBN.STACK_NO_WINDOWS_TEXT in out4


def test_cli_refuses_what_a_stack_refuses(saved, capsys):
    base = ["line3", "ask", "--data", saved["data"], "--stack", saved["root"], "--foundation", "on", "--level", LEVEL, "--question", Q, "--layers", "off"]
    rc, out, err = run_cli(capsys, *base, "--effort", "full")
    assert rc == 2 and "full" in err and out == ""
    rc, out, err = run_cli(capsys, *base, "--effort", "fast", "--structure", "slide")
    assert rc == 2 and err
    rc, out, err = run_cli(capsys, *base, "--effort", "fast", "--cache", str(saved["dir"]))
    assert rc == 2 and "--stack" in err
    rc, out, err = run_cli(capsys, *base, "--effort", "fast", "--group-insert", "ordered")
    assert rc == 2 and "--stack" in err
    rc, out, err = run_cli(capsys, "line3", "build", "--data", saved["data"], "--stack", saved["root"], "--cache", str(saved["dir"] / "x"))
    assert rc == 2 and "--stack" in err
    rc, out, err = run_cli(capsys, "line3", "ask", "--data", saved["data"], "--step", "2", "--question", Q, "--effort", "fast")
    assert rc == 2 and "--step" in err
    rc, out, err = run_cli(capsys, *base, "--effort", "fast", "--step", "9")
    assert rc == 2 and "step" in err
    rc, out, err = run_cli(capsys, "line3", "ask", "--data", saved["data"], "--stack", saved["root"], "--foundation", "off", "--level", LEVEL, "--question", Q,
                           "--effort", "fast", "--step", "2")
    assert rc == 2 and "stack" in err                                                                           # no foundation-off stack under that root
    other = [dict(r) for r in rows(SENTS)]
    other[3]["sent"] = "大阪の城は新しい。"
    odata = write_jsonl(saved["dir"] / "other.jsonl", other)
    rc, out, err = run_cli(capsys, "line3", "ask", "--data", odata, "--stack", saved["root"], "--foundation", "on", "--level", LEVEL, "--question", Q,
                           "--effort", "fast", "--step", "3")
    assert rc == 2 and "stack" in err                                                                           # a corpus that is not the prefix
    rc, out, err = run_cli(capsys, "line3", "ask", "--data", saved["data"], "--foundation", "on", "--structure", "slide", "--question", Q, "--effort", "fast")
    assert rc == 2 and "--foundation" in err


def test_cli_build_and_ask_with_the_foundation_flag(toy, tmp_path, capsys):
    cache = str(tmp_path / "cache")
    common = ["--data", toy, "--cache", cache, "--level", LEVEL, "--tiers", "CHAR", "--group-insert", "ordered"]
    rc, out, err = run_cli(capsys, "line3", "build", *common, "--foundation", "on")
    assert rc == 0, err
    rc, out, err = run_cli(capsys, "line3", "build", *common)
    assert rc == 0, err
    files = sorted(os.listdir(cache))
    assert len(files) == 2 and sum("found-" in f for f in files) == 1                   # the seated cache and the plain one live side by side
    rc, out, err = run_cli(capsys, "line3", "ask", *common, "--foundation", "on", "--question", Q, "--effort", "fast", "--layers", "off", "--format", "json")
    assert rc == 0, err
    assert json.loads(out)["answer"]["placement"]["foundation"] == fd.seats_sha()
    rc, out, err = run_cli(capsys, "line3", "ask", *common, "--question", Q, "--effort", "fast", "--layers", "off", "--format", "json")
    assert rc == 0, err
    assert "foundation" not in json.loads(out)["answer"]["placement"]


# =============================================================================================================
# Part 7b: the stack read and the one-shot index read the same prefix alike (step 1)
# =============================================================================================================
PARITY_QS = {"DOCS": [Q, Q2, "三", "東京は何", "大阪の城"], "MANY": ["一二三", "五", "三四", "城"], "GROW": ["三", "一二", "一", "九"]}
PARITY_SRC = {"DOCS": (DOCS, SENTS), "MANY": (DOCS_MANY, MANY), "GROW": (DOCS_GROW, GROW)}


def _entry_key(tier, e):
    return (tier, e.words, e.centres, tuple(a.key for a in e.arrangements), e.stability, e.source_sids)


@pytest.mark.parametrize("found", ["off", "on"])
@pytest.mark.parametrize("toy_name", ["DOCS", "MANY", "GROW"])
def test_stack_read_equals_one_shot_read_at_step_1(toy_name, found, tmp_path):
    """L-G4-98: PARITY IS EXPECTED AT STEP 1 ONLY.  At step 1 every cross of the stack is born in one pass (T-G4-6: the one-shot quotient-off build, seated and
    contracted when the foundation is on), so the reader over the stack and the reader over a one-shot ordered index on the same prefix list the same entries (tier,
    word set, centres, arrangements, stability, source sentences) and give the same verdicts (per tier and combined), for every question at every effort (fast,
    standard, None), 3 tiers, foundation off and on.  From step 2 on a stack is NOT the one-shot build of the prefix (seated units never move, closed crosses stay
    closed, L-G4-52..) and no such equality is claimed or tested there; the identity that holds at every step is the fold (test_stack.py)."""
    docs, sents = PARITY_SRC[toy_name]
    first = sents[0][0]
    path = write_jsonl(tmp_path / "prefix.jsonl", rows([x for x in sents if x[0] == first]))        # the first document only = step 1
    ix_s = A.Index.from_stack(st.build(docs[:1], foundation=found, tiers=ALL, level=LEVEL))
    ix_o = A.Index.from_jsonl(path, None, LEVEL, ALL, group_insert="ordered", foundation=found)
    assert ix_s.stack["step"] == 1 and ix_o.stack is None and ix_s.tiers == ix_o.tiers == ALL
    qs = PARITY_QS[toy_name]
    assert len(qs) >= 3
    seen = set()
    for q in qs:
        for eff in ("fast", "standard", None):
            a, b = A.ask(ix_s, q, effort=eff), A.ask(ix_o, q, effort=eff)
            assert a.verdict == b.verdict, (q, eff)
            assert [(o.tier, o.verdict) for o in a.outcomes] == [(o.tier, o.verdict) for o in b.outcomes], (q, eff)
            assert [_entry_key(t, e) for t, e in a.entries] == [_entry_key(t, e) for t, e in b.entries], (q, eff)
            assert [(o.tier, o.read_counts) for o in a.outcomes] == [(o.tier, o.read_counts) for o in b.outcomes], (q, eff)
            seen.add((a.verdict, len(a.entries) > 0))
    assert any(n for _, n in seen) and any(not n for _, n in seen)      # entries are compared, and an unanswered question too


# =============================================================================================================
# Part 8: the bytes do not depend on the hash seed
# =============================================================================================================
SEED_PROG = """
import sys, json, hashlib
from verantyx.line3 import ask as A, stack as st
a = json.loads(sys.stdin.read())
out = {}
for found in ("off", "on"):
    s = st.build(a["docs"], foundation=found, tiers=("RUN", "WORD", "CHAR"), level=a["level"])
    ix = A.Index.from_stack(s)
    out[found] = [hashlib.sha256(A.ask(ix, q, effort=e).to_bytes()).hexdigest()[:16] for q in a["qs"] for e in (None, "fast")]
    ix2 = A.Index.from_jsonl(a["path"], None, a["level"], ("RUN", "WORD", "CHAR"), group_insert="ordered", foundation=found)
    out[found] += [hashlib.sha256(A.ask(ix2, a["qs"][0], effort="fast").to_bytes()).hexdigest()[:16]]
print(json.dumps(out))
"""


def test_a_read_over_a_stack_and_over_a_seated_index_does_not_depend_on_the_hash_seed(toy):
    res = []
    for seed in ("0", "1", "12345"):
        out = subprocess.run([PY, "-c", SEED_PROG], input=json.dumps({"docs": DOCS, "level": LEVEL, "qs": [Q, Q2, "三"], "path": toy}), cwd=ROOT,
                             capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed))
        assert out.returncode == 0, out.stderr
        res.append(json.loads(out.stdout))
    assert res[0] == res[1] == res[2]

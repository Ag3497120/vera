"""F1b tests (L-470..): the placement options group_insert (whole | ordered) and order (forward | reverse) are wired
through the question path (ask.Index, the placement cache, the answer and the thought, the layers, the raise rebuild, the
`line3` command).  The insertion order is part of the initial placement: it is in the cache key (a whole cache is never
read as an ordered one and vice versa) and it is recorded in the answer and the thought.  Defaults (whole / forward)
leave every byte as it was (the golden hashes of test_matryoshka.py are reused)."""
import hashlib
import json
import os
import pickle
import subprocess
import sys

import pytest

from verantyx.line3 import ask as A
from verantyx.line3 import matryoshka as M
from verantyx.line3 import placement as pl
from verantyx.line3.space import build_space
from test_matryoshka import BOUNDS, DATA, GOLDEN_OLD, QUESTION, SMALL, TIERS, make_index

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
H = lambda b: hashlib.sha256(b).hexdigest()
ORD_KEY = {"group_insert": "ordered", "order": "forward"}
REV_KEY = {"group_insert": "ordered", "order": "reverse"}


@pytest.fixture(scope="module")
def data_file(tmp_path_factory):
    p = tmp_path_factory.mktemp("f1b") / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    return str(p)


@pytest.fixture(scope="module")
def space():
    return build_space([{"sent": s, "source": "toy"} for s in DATA])


@pytest.fixture(scope="module")
def ordered_index(space):
    return A.Index(space, group_insert="ordered")


# ---- the options -----------------------------------------------------------------------------------------------------
def test_option_checks():
    assert A.check_placement_options() == ("whole", "forward")
    assert A.check_placement_options("ordered", "reverse") == ("ordered", "reverse")
    for bad in (("x", "forward"), ("whole", "x"), ("whole", "reverse")):       # whole has no order: reverse would be a lie
        with pytest.raises(ValueError):
            A.check_placement_options(*bad)
        with pytest.raises(ValueError):
            A.Index(build_space([{"sent": s, "source": "t"} for s in DATA]), group_insert=bad[0], order=bad[1])


def test_the_index_passes_the_options_to_every_placer_and_layer(space, ordered_index):
    for t in ordered_index.tiers:
        pr = ordered_index.stores[t].placer
        assert (pr.group_insert, pr.order) == ("ordered", "forward")
        assert M.stack_of(ordered_index, t).group_insert == "ordered"
    d = A.Index(space)
    assert d.placement_is_default and not ordered_index.placement_is_default
    assert all(d.stores[t].placer.group_insert == "whole" for t in d.tiers)
    p = ordered_index.stores["RUN"].cross_for("東京")
    assert p.group_insert == "ordered" and p.order_log


# ---- the cache key -----------------------------------------------------------------------------------------------------
def test_cache_key_differs_and_the_default_file_name_is_what_it_was(data_file):
    sha = A.file_sha256(data_file)
    names = {k: os.path.basename(A.cache_path("c", sha, "RUN", "mid", *k))
             for k in (("whole", "forward"), ("ordered", "forward"), ("ordered", "reverse"))}
    assert len(set(names.values())) == 3
    assert names[("whole", "forward")] == "placements_%s_RUN_mid.pkl" % sha[:12]                      # unchanged
    assert A.cache_path("c", sha, "RUN", "mid") == A.cache_path("c", sha, "RUN", "mid", "whole", "forward")
    assert A.placement_key() == "" and A.placement_key("ordered") == "ordered-forward"
    assert A.placement_key("ordered", "reverse") == "ordered-reverse"


def test_a_cache_built_under_one_option_is_ignored_or_refused_under_another(data_file, tmp_path):
    cache = str(tmp_path / "c")
    sha = A.file_sha256(data_file)
    built = {}
    for key in (("whole", "forward"), ("ordered", "forward"), ("ordered", "reverse")):
        idx = A.Index.from_jsonl(data_file, None, "mid", ("RUN",), group_insert=key[0], order=key[1])
        idx.precompute(cache)
        built[key] = idx.stores["RUN"]._loaded
        assert all(p.group_insert == key[0] and p.order == key[1] for p in built[key].values())
    assert len(os.listdir(cache)) == 3
    # each option set reads back exactly its own cache
    for key, plc in built.items():
        again = A.Index.from_jsonl(data_file, cache, "mid", ("RUN",), group_insert=key[0], order=key[1])
        assert pl.serialize_all(again.stores["RUN"]._loaded) == pl.serialize_all(plc)
    # a cache directory with only a whole cache is IGNORED by an ordered index (nothing loaded, built on demand), and v.v.
    only_whole, only_ord = str(tmp_path / "w"), str(tmp_path / "o")
    A.Index.from_jsonl(data_file, None, "mid", ("RUN",)).precompute(only_whole)
    A.Index.from_jsonl(data_file, None, "mid", ("RUN",), group_insert="ordered").precompute(only_ord)
    assert A.Index.from_jsonl(data_file, only_whole, "mid", ("RUN",), group_insert="ordered").stores["RUN"]._loaded == {}
    assert A.Index.from_jsonl(data_file, only_whole, "mid", ("RUN",), group_insert="ordered", order="reverse").stores["RUN"]._loaded == {}
    assert A.Index.from_jsonl(data_file, only_ord, "mid", ("RUN",)).stores["RUN"]._loaded == {}
    assert A.Index.from_jsonl(data_file, only_ord, "mid", ("RUN",), group_insert="ordered", order="reverse").stores["RUN"]._loaded == {}
    # an explicit load is REFUSED, whatever the file is called
    ts = A.Index.from_jsonl(data_file, None, "mid", ("RUN",)).space.tiers["RUN"]
    pw, po, pr = (A.cache_path(cache, sha, "RUN", "mid", *k) for k in (("whole", "forward"), ("ordered", "forward"), ("ordered", "reverse")))
    for path, ok in ((pw, ("whole", "forward")), (po, ("ordered", "forward")), (pr, ("ordered", "reverse"))):
        for other in (("whole", "forward"), ("ordered", "forward"), ("ordered", "reverse")):
            if other == ok:
                A.load_placements(path, ts, "RUN", "mid", sha, *other)
            else:
                with pytest.raises(ValueError):
                    A.load_placements(path, ts, "RUN", "mid", sha, *other)
    # a file moved to another option's name does not fool the loader (the pickle carries the options)
    fake = str(tmp_path / "fake.pkl")
    with open(pw, "rb") as f, open(fake, "wb") as g:
        g.write(f.read())
    with pytest.raises(ValueError):
        A.load_placements(fake, ts, "RUN", "mid", sha, "ordered", "forward")
    # an old cache (a pickle without the option keys) is a whole / forward cache
    with open(pw, "rb") as f:
        d = pickle.load(f)
    assert "group_insert" not in d and "order" not in d                                                # the default file is as before
    with open(po, "rb") as f:
        d2 = pickle.load(f)
    assert (d2["group_insert"], d2["order"]) == ("ordered", "forward")


# ---- recorded in the answer and the thought ---------------------------------------------------------------------------
def test_options_are_in_the_answer_and_the_thought(ordered_index):
    c = A.ask(ordered_index, QUESTION, effort="full")
    o = c.to_json_obj()
    assert o["answer"]["placement"] == ORD_KEY and o["thought"]["placement"] == ORD_KEY
    for t in c.outcomes:
        rec = o["thought"]["tiers"][t.tier]["placement_order"]
        assert [r["seed"] for r in rec] == sorted(r["seed"] for r in rec) and len(rec) == len(t.result.plan.read)
        for r in rec:
            assert set(r) == {"seed", "stop", "size", "left_in_group", "left_after", "groups"}
            p = ordered_index.stores[t.tier].cross_for(r["seed"])
            assert r["groups"] == [[sh, list(us)] for sh, us in p.order_log]
    assert any(r["groups"] for t in o["thought"]["tiers"].values() for r in t["placement_order"])
    txt = A.format_text(c)
    assert "配置の入れ方: ordered" in txt and "逆" not in txt
    rev = A.ask(A.Index(ordered_index.space, group_insert="ordered", order="reverse"), QUESTION, effort="full")
    assert rev.to_json_obj()["answer"]["placement"] == REV_KEY and "逆" in A.format_text(rev)
    assert json.loads(c.to_bytes()) == o


def test_options_are_in_the_layered_answer_and_the_thought(ordered_index):
    c = M.ask_layered(ordered_index, QUESTION, effort="full", options=M.LayerOptions(bounds=BOUNDS))
    o = c.to_json_obj()
    assert o["answer"]["layer0"]["placement"] == ORD_KEY
    assert o["thought"]["layers"]["options"]["placement"] == ORD_KEY and o["thought"]["layer0"]["placement"] == ORD_KEY
    st = M.stack_of(ordered_index, "RUN")
    lay = st.layer1("same", [], BOUNDS)
    assert lay.group_insert == "ordered"
    seed = sorted(lay.words)[0]
    assert lay.cross_for(seed).group_insert == "ordered" and lay.cross_for(seed).order_log
    rec = c.base.memory_record(0) if c.base.entries else None
    if rec is not None:
        assert rec["placement"] == ORD_KEY


def test_the_raise_rebuild_uses_the_same_insertion_order():
    from test_placement import tier
    from verantyx.line3 import cycle as cy
    t = tier(["A B C D E F G H"])                       # 8 units of equal share: level "low" stops by budget (T6y)
    w = pl.Weights(t)

    class Store:                                        # stored crosses at "low", built like the index builds them
        def __init__(self, gi):
            self.p = {u: pl.build_cross(t, u, w, budget=pl.budget_level("low"), group_insert=gi) for u in t.postings}

        def cross_for(self, seed):
            return self.p[seed]

    r0 = cy.ask_tier(t, "", Store("whole"), units=("A",))
    b0 = r0.thought_obj()["variant"]["budget_raise"]
    assert b0["needed"] and "group_insert" not in b0 and "order" not in b0                    # default: nothing new recorded
    assert r0.to_bytes() == cy.ask_tier(t, "", Store("whole"), units=("A",), group_insert="whole", order="forward").to_bytes()
    # stored whole crosses at "low" stop by budget with no state (so a rebuild is needed); the rebuild is told to insert in order.
    # (Stored ORDERED crosses at "low" already hold a state -- 7 of the 8 -- so an ordered index rarely needs a rebuild.)
    assert Store("ordered").p["A"].size == 7 and Store("whole").p["A"].size == 1
    r1 = cy.ask_tier(t, "", Store("whole"), units=("A",), group_insert="ordered")
    b1 = r1.thought_obj()["variant"]["budget_raise"]
    assert b1["needed"] and b1["group_insert"] == "ordered" and b1["order"] == "forward"
    step = b1["steps"][0]["raised"][0]
    direct = pl.build_cross(t, "A", w, budget=pl.budget_level(b1["steps"][0]["level"]), group_insert="ordered")
    whole = pl.build_cross(t, "A", w, budget=pl.budget_level(b1["steps"][0]["level"]))
    assert (step["capacity_after"], step["stop_after"]) == (direct.capacity, direct.stop)      # rebuilt in the same insertion order
    assert (direct.capacity, direct.stop) != (whole.capacity, whole.stop) or direct.order_log                     # (and it is not the whole build)
    r2 = cy.ask_tier(t, "", Store("whole"), units=("A",), group_insert="ordered", order="reverse")
    assert r2.thought_obj()["variant"]["budget_raise"]["order"] == "reverse"
    # through ask(): an ordered index hands its options to the rebuild
    idx = A.Index(build_space([{"sent": x, "source": "t"} for x in DATA]), group_insert="ordered")
    assert A.placement_kw(idx) == {"group_insert": "ordered", "order": "forward"}


# ---- defaults are byte-identical -------------------------------------------------------------------------------------
def test_defaults_are_byte_identical_to_the_recorded_golden_hashes(space):
    for kw in ({}, {"group_insert": "whole"}, {"group_insert": "whole", "order": "forward"}):
        idx = make_index(space, SMALL)
        idx.group_insert, idx.order = A.check_placement_options(**kw)
        assert H(A.ask(idx, QUESTION, TIERS, effort="full").to_bytes()) == GOLDEN_OLD["off"]
        old = M.ask_layered(idx, QUESTION, TIERS, effort="full",
                            options=M.LayerOptions(candidate="bag", variants=M.VARIANTS, granularity="same", bounds=BOUNDS))
        assert H(old.to_bytes()) == GOLDEN_OLD["on-old"]
        old_c = M.ask_layered(idx, QUESTION, TIERS, effort="full",
                              options=M.LayerOptions(candidate="bag", variants=("A",), granularity="compress", bounds=BOUNDS))
        assert H(old_c.to_bytes()) == GOLDEN_OLD["on-old-compress-A"]
    b = A.ask(make_index(space, SMALL), QUESTION, TIERS, effort="full").to_bytes()
    assert b"placement" not in b and b"group_insert" not in b
    c = A.ask(A.Index(space), QUESTION, TIERS)
    assert c.placement is None and "placement" not in c.to_json_obj()["answer"] and "placement" not in c.to_json_obj()["thought"]
    assert "配置の入れ方" not in A.format_text(c)


# ---- determinism, no float ---------------------------------------------------------------------------------------------
def _script(order):
    return ("import hashlib\n"
            "from verantyx.line3 import ask as A, matryoshka as M\n"
            "from verantyx.line3.space import build_space\n"
            "D=%r\n" % (DATA,) +
            "sp=build_space([{'sent':s,'source':'t'} for s in D])\n"
            "idx=A.Index(sp, group_insert='ordered', order=%r)\n" % order +
            "b=M.LayerBounds(2,6,8,3,6,'low',4)\n"
            "c=M.ask_layered(idx,%r,effort='full',options=M.LayerOptions(bounds=b))\n" % QUESTION +
            "x=c.to_bytes()\n"
            "assert b'placement_order' in x and b'\"ordered\"' in x\n"
            "print(hashlib.sha256(x).hexdigest(), len(x))\n")


@pytest.mark.parametrize("order", ["forward", "reverse"])
def test_ordered_output_is_byte_identical_across_hash_seeds(order):
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", _script(order)], capture_output=True, text=True, env=env, cwd=ROOT,
                           timeout=900, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2] and outs[0].strip()


def test_no_float_in_an_ordered_answer(ordered_index):
    def walk(x):
        assert not isinstance(x, float), x
        if isinstance(x, dict):
            for k, v in x.items():
                walk(k)
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    walk(json.loads(A.ask(ordered_index, QUESTION, effort="full").to_bytes()))
    walk(json.loads(M.ask_layered(ordered_index, QUESTION, effort="full", options=M.LayerOptions(bounds=BOUNDS)).to_bytes()))


# ---- the command -------------------------------------------------------------------------------------------------------
def cli(args, seed="0"):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    for k in [k for k in env if k.startswith("VERA_")]:
        del env[k]
    return subprocess.run([sys.executable, "-m", "verantyx.cli", "line3"] + args, capture_output=True, text=True, env=env,
                          cwd=ROOT, timeout=900, stdin=subprocess.DEVNULL)


def test_cli_group_insert_and_order(data_file, tmp_path):
    q = ["ask", "--data", data_file, "--question", QUESTION, "--format", "json", "--show-thought", "--effort", "fast"]   # (layers on at "full" bounds with ordered placements is minutes even on the toy)
    for layers in ("off", "on"):
        base = q + ["--layers", layers]
        d0 = cli(base)
        assert d0.returncode == 0, d0.stderr
        assert d0.stdout == cli(base + ["--group-insert", "whole"]).stdout == cli(base + ["--group-insert", "whole", "--order", "forward"]).stdout
        assert "placement" not in d0.stdout
        o = cli(base + ["--group-insert", "ordered"], "1")
        assert o.returncode == 0, o.stderr
        j = json.loads(o.stdout)
        top = j["answer"]["layer0"] if layers == "on" else j["answer"]
        assert top["placement"] == ORD_KEY
        assert o.stdout == cli(base + ["--group-insert", "ordered"], "12345").stdout
        r = cli(base + ["--group-insert", "ordered", "--order", "reverse"])
        assert r.returncode == 0 and (json.loads(r.stdout)["answer"]["layer0"] if layers == "on" else json.loads(r.stdout)["answer"])["placement"] == REV_KEY
    assert cli(q + ["--order", "reverse"]).returncode == 2                         # whole has no order
    assert cli(q + ["--group-insert", "sideways"]).returncode == 2                 # argparse choice
    # build -> ask with the matching cache only
    cache = str(tmp_path / "cc")
    assert cli(["build", "--data", data_file, "--cache", cache, "--tiers", "RUN", "--group-insert", "ordered"]).returncode == 0
    sha = A.file_sha256(data_file)
    assert os.listdir(cache) == [os.path.basename(A.cache_path(cache, sha, "RUN", "mid", "ordered", "forward"))]
    qq = ["ask", "--data", data_file, "--question", QUESTION, "--format", "json", "--show-thought", "--tiers", "RUN",
          "--effort", "full", "--layers", "off"]
    with_cache = cli(qq + ["--cache", cache, "--group-insert", "ordered"])
    assert with_cache.returncode == 0 and with_cache.stdout == cli(qq + ["--group-insert", "ordered"]).stdout
    # the whole index finds no file there (ignored, built on demand) and answers as without a cache
    assert cli(qq + ["--cache", cache]).stdout == cli(qq).stdout


# ======================================================================================================================
# F1c (L-506, L-507): on_collapse (stop | skip) goes through the question path like group_insert / order
# ======================================================================================================================
SKIP_KEY = {"group_insert": "ordered", "order": "forward", "on_collapse": "skip"}


@pytest.fixture(scope="module")
def skip_index(space):
    return A.Index(space, group_insert="ordered", on_collapse="skip")


def test_on_collapse_option_checks(space):
    assert A.check_placement_options("ordered", "forward", "skip") == ("ordered", "forward")      # same pair as before
    assert A.check_placement_options("ordered", "reverse", "stop") == ("ordered", "reverse")
    for bad in (("whole", "forward", "skip"), ("ordered", "forward", "x"), ("whole", "forward", "x")):
        with pytest.raises(ValueError):
            A.check_placement_options(*bad)                                                     # L-500: whole + skip
    with pytest.raises(ValueError):
        A.Index(space, on_collapse="skip")
    with pytest.raises(ValueError):
        A.Index(space, group_insert="whole", on_collapse="skip")
    d = A.Index(space, group_insert="ordered")
    assert d.on_collapse == "stop" and not d.placement_is_default
    assert not A.Index(space, group_insert="ordered", on_collapse="skip").placement_is_default
    assert A.Index(space).placement_is_default


def test_the_index_passes_on_collapse_to_every_placer_and_layer(skip_index):
    for t in skip_index.tiers:
        assert skip_index.stores[t].placer.on_collapse == "skip"
        assert M.stack_of(skip_index, t).on_collapse == "skip"
    p = skip_index.stores["RUN"].cross_for("東京")
    assert p.on_collapse == "skip" and p.group_insert == "ordered" and p.order_log
    lay = M.stack_of(skip_index, "RUN").layer1("same", [], BOUNDS)
    assert lay.on_collapse == "skip" and lay.cross_for(sorted(lay.words)[0]).on_collapse == "skip"


def test_cache_key_has_on_collapse_and_the_stop_names_are_what_they_were(data_file):
    sha = A.file_sha256(data_file)
    assert A.placement_key("ordered", "forward", "stop") == A.placement_key("ordered") == "ordered-forward"        # F1b name kept
    assert A.placement_key("ordered", "forward", "skip") == "ordered-forward-skip"
    assert A.placement_key("ordered", "reverse", "skip") == "ordered-reverse-skip"
    names = {os.path.basename(A.cache_path("c", sha, "RUN", "mid", *k)) for k in
             (("whole", "forward"), ("ordered", "forward"), ("ordered", "forward", "skip"), ("ordered", "reverse"), ("ordered", "reverse", "skip"))}
    assert len(names) == 5
    assert A.cache_path("c", sha, "RUN", "mid", "ordered", "forward") == A.cache_path("c", sha, "RUN", "mid", "ordered", "forward", "stop")


def test_a_stop_cache_is_never_read_as_skip_and_back(data_file, tmp_path):
    cache = str(tmp_path / "c")
    sha = A.file_sha256(data_file)
    kw = {"stop": dict(group_insert="ordered"), "skip": dict(group_insert="ordered", on_collapse="skip")}
    for oc, k in kw.items():
        idx = A.Index.from_jsonl(data_file, None, "mid", ("RUN",), **k)
        idx.precompute(cache)
        assert all(p.on_collapse == oc for p in idx.stores["RUN"]._loaded.values())
    assert len(os.listdir(cache)) == 2
    ts = A.Index.from_jsonl(data_file, None, "mid", ("RUN",)).space.tiers["RUN"]
    p_stop, p_skip = (A.cache_path(cache, sha, "RUN", "mid", "ordered", "forward", oc) for oc in ("stop", "skip"))
    # each reads back exactly its own cache
    for oc, k in kw.items():
        again = A.Index.from_jsonl(data_file, cache, "mid", ("RUN",), **k)
        assert len(again.stores["RUN"]._loaded) == len(ts.units()) and all(p.on_collapse == oc for p in again.stores["RUN"]._loaded.values())
    # a directory with only the stop cache is ignored by a skip index (built on demand), and vice versa
    only_stop, only_skip = str(tmp_path / "s"), str(tmp_path / "k")
    A.Index.from_jsonl(data_file, None, "mid", ("RUN",), **kw["stop"]).precompute(only_stop)
    A.Index.from_jsonl(data_file, None, "mid", ("RUN",), **kw["skip"]).precompute(only_skip)
    assert A.Index.from_jsonl(data_file, only_stop, "mid", ("RUN",), **kw["skip"]).stores["RUN"]._loaded == {}
    assert A.Index.from_jsonl(data_file, only_skip, "mid", ("RUN",), **kw["stop"]).stores["RUN"]._loaded == {}
    # an explicit load is refused both ways, and a file under the other's name does not fool the loader
    A.load_placements(p_stop, ts, "RUN", "mid", sha, "ordered", "forward", "stop")
    A.load_placements(p_skip, ts, "RUN", "mid", sha, "ordered", "forward", "skip")
    with pytest.raises(ValueError):
        A.load_placements(p_stop, ts, "RUN", "mid", sha, "ordered", "forward", "skip")
    with pytest.raises(ValueError):
        A.load_placements(p_skip, ts, "RUN", "mid", sha, "ordered", "forward", "stop")
    with pytest.raises(ValueError):
        A.load_placements(p_skip, ts, "RUN", "mid", sha, "ordered", "forward")                  # on_collapse defaults to stop
    fake = str(tmp_path / "fake.pkl")
    with open(p_skip, "rb") as f, open(fake, "wb") as g:
        g.write(f.read())
    with pytest.raises(ValueError):
        A.load_placements(fake, ts, "RUN", "mid", sha, "ordered", "forward", "stop")
    # the pickle carries the key only for skip: an ordered+stop file is what F1b wrote
    with open(p_stop, "rb") as f:
        d = pickle.load(f)
    assert "on_collapse" not in d and (d["group_insert"], d["order"]) == ("ordered", "forward")
    with open(p_skip, "rb") as f:
        d = pickle.load(f)
    assert d["on_collapse"] == "skip"
    # a whole cache is still refused as skip (whole + skip cannot be asked at all)
    pw = A.cache_path(cache, sha, "RUN", "mid")
    A.Index.from_jsonl(data_file, None, "mid", ("RUN",)).precompute(cache)
    with pytest.raises(ValueError):
        A.load_placements(pw, ts, "RUN", "mid", sha, "ordered", "forward", "skip")


def test_on_collapse_is_in_the_answer_and_the_thought_only_when_skip(skip_index, ordered_index):
    c = A.ask(skip_index, QUESTION, effort="full")
    o = c.to_json_obj()
    assert o["answer"]["placement"] == SKIP_KEY and o["thought"]["placement"] == SKIP_KEY
    for t in c.outcomes:
        for r in o["thought"]["tiers"][t.tier]["placement_order"]:
            assert set(r) == {"seed", "stop", "size", "left_in_group", "left_after", "groups", "skipped"}
            p = skip_index.stores[t.tier].cross_for(r["seed"])
            assert r["skipped"] == [[sh, u, why] for sh, u, why in p.skipped]
    assert "その 1 つだけ飛ばして続ける" in A.format_text(c) and "直前で止める" not in A.format_text(c)
    assert json.loads(c.to_bytes()) == o
    # ordered + stop: exactly the F1b bytes (no on_collapse key, no skipped key, the old line)
    so = A.ask(ordered_index, QUESTION, effort="full")
    b = so.to_bytes()
    assert so.to_json_obj()["answer"]["placement"] == ORD_KEY and b"on_collapse" not in b and b'"skipped"' not in b
    assert "直前で止める" in A.format_text(so)
    assert A.placement_kw(ordered_index) == {"group_insert": "ordered", "order": "forward"}
    assert A.placement_kw(skip_index) == {"group_insert": "ordered", "order": "forward", "on_collapse": "skip"}


def test_on_collapse_is_in_the_layered_answer_and_the_thought(skip_index):
    c = M.ask_layered(skip_index, QUESTION, effort="full", options=M.LayerOptions(bounds=BOUNDS))
    o = c.to_json_obj()
    assert o["answer"]["layer0"]["placement"] == SKIP_KEY
    assert o["thought"]["layers"]["options"]["placement"] == SKIP_KEY and o["thought"]["layer0"]["placement"] == SKIP_KEY


def test_the_raise_rebuild_uses_the_same_on_collapse():
    from test_placement import tier
    from verantyx.line3 import cycle as cy
    t = tier(["A B C D E F G H"])
    w = pl.Weights(t)

    class Store:
        def __init__(self):
            self.p = {u: pl.build_cross(t, u, w, budget=pl.budget_level("low")) for u in t.postings}

        def cross_for(self, seed):
            return self.p[seed]

    b1 = cy.ask_tier(t, "", Store(), units=("A",), group_insert="ordered").thought_obj()["variant"]["budget_raise"]
    assert b1["needed"] and "on_collapse" not in b1
    b2 = cy.ask_tier(t, "", Store(), units=("A",), group_insert="ordered", on_collapse="skip").thought_obj()["variant"]["budget_raise"]
    assert b2["needed"] and b2["on_collapse"] == "skip" and b2["group_insert"] == "ordered"
    direct = pl.build_cross(t, "A", w, budget=pl.budget_level(b2["steps"][0]["level"]), group_insert="ordered", on_collapse="skip")
    assert b2["steps"][0]["raised"][0]["capacity_after"] == direct.capacity
    with pytest.raises(ValueError):                                                              # L-500
        cy.ask_tier(t, "", Store(), units=("A",), group_insert="whole", on_collapse="skip")


def test_defaults_do_not_change_placements_only_the_pickle_bytes_may(space):
    """The new Placement fields (on_collapse, skipped) change the pickled BYTES of a placement (more state), never its
    value: "unchanged" is judged on serialize_all / to_bytes, and an old pickle (without the fields) loads as stop."""
    idx = A.Index(space)
    plc = {u: idx.stores["RUN"].cross_for(u) for u in space.tiers["RUN"].units()[:20]}
    j = pl.serialize_all(plc)
    assert b"on_collapse" not in j and b"skipped" not in j and b"group_insert" not in j
    p = plc[sorted(plc)[0]]
    old = pl.Placement.__new__(pl.Placement)                 # what an F1b-era pickle restores: no on_collapse / skipped in __dict__
    for k, v in p.__dict__.items():
        if k not in ("on_collapse", "skipped"):
            object.__setattr__(old, k, v)
    assert "on_collapse" not in old.__dict__ and old.on_collapse == "stop" and old.skipped == ()
    assert old.to_bytes() == p.to_bytes() and old == p.__class__(**{**p.__dict__})
    back = pickle.loads(pickle.dumps(p))
    assert back.to_bytes() == p.to_bytes() and back.on_collapse == "stop"


def test_cli_on_collapse(data_file, tmp_path):
    q = ["ask", "--data", data_file, "--question", QUESTION, "--format", "json", "--show-thought", "--effort", "fast", "--layers", "off"]
    base = cli(q + ["--group-insert", "ordered"])
    assert base.returncode == 0, base.stderr
    assert base.stdout == cli(q + ["--group-insert", "ordered", "--on-collapse", "stop"]).stdout
    assert "on_collapse" not in base.stdout
    s = cli(q + ["--group-insert", "ordered", "--on-collapse", "skip"], "1")
    assert s.returncode == 0, s.stderr
    assert json.loads(s.stdout)["answer"]["placement"] == SKIP_KEY
    assert s.stdout == cli(q + ["--group-insert", "ordered", "--on-collapse", "skip"], "12345").stdout
    r = cli(q + ["--on-collapse", "skip"])                                                      # L-500: refused with whole
    assert r.returncode == 2 and "skip" in r.stderr
    assert cli(q + ["--group-insert", "ordered", "--on-collapse", "x"]).returncode == 2         # argparse choice
    d0 = cli(q)
    assert d0.returncode == 0 and d0.stdout == cli(q + ["--on-collapse", "stop"]).stdout and "placement" not in d0.stdout
    cache = str(tmp_path / "cc")
    assert cli(["build", "--data", data_file, "--cache", cache, "--tiers", "RUN", "--group-insert", "ordered", "--on-collapse", "skip"]).returncode == 0
    sha = A.file_sha256(data_file)
    assert os.listdir(cache) == [os.path.basename(A.cache_path(cache, sha, "RUN", "mid", "ordered", "forward", "skip"))]
    assert cli(["build", "--data", data_file, "--cache", cache, "--tiers", "RUN", "--on-collapse", "skip"]).returncode == 2

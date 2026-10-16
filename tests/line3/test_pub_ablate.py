"""Ticket C (geometry ablation) tests: the geometry profile of the memory index (memcross.Geometry), its six independent switches, the byte identity of the defaults (A3) and of all-OFF (A3f) with the tree
before the profile existed (golden recorded at line3 a8296ae4), the begin row / replay / answer-run record, determinism under hash seeds, the answer rules untouched, and the meter2 arm names."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

import geo_golden as gg
from verantyx.loom import memanswer as ma
from verantyx.loom import memcross as mx
from verantyx.loom import memory as mem
from verantyx.loom.state import Refuse
from mem_common import ROOT, new_store

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = json.load(open(os.path.join(HERE, "golden_geometry.json"), encoding="utf-8"))
METER2 = os.path.join(ROOT, "experiments", "line3", "pub", "meter2")
M6D = dict(mem.V4_VERSIONS_M6D)
ALL = mx.GEO_COMPONENTS
PINS = {"memask.py": "a72c1e3ef6df3b349746a945eb2845fed6788640acc54da45efacfd8d861802c", "memdetect.py": "267cdebf2099505e74bf11af92742abfcd83b4c865c9e92d3b80964d7ea33ae2",
        "memshape.py": "f71a28b292081df6346552254c3ff4ebdf883a340b83bd4b04d809f0c6a59393"}


def geo_off(*names):
    return mx.Geometry.of_off(names)


def obj_of(g):
    ix = mx.build_index(gg.rows(), gg.DECLS, geometry=g)
    return ix, json.loads(json.dumps(ix.to_obj()))


def sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# -- the profile -------------------------------------------------------------------------------------------------------------------------------
def test_the_profile_version_strings_are_canonical_and_parse_back():
    assert mx.Geometry().version() == mx.CROSS_VERSION and mx.Geometry.flat_table().version() == mx.FLAT_VERSION
    assert mx.Geometry.parse(None) == mx.Geometry() and mx.Geometry.parse(mx.CROSS_VERSION) == mx.Geometry() and mx.Geometry.parse(mx.FLAT_VERSION) == geo_off(*ALL)
    g = geo_off("slide", "nests")
    assert g.version() == "geo.v1:-nests-slide" and mx.Geometry.parse(g.version()) == g and g.off == ("nests", "slide")
    for bad in ("geo.v1:", "geo.v1:-", "geo.v1:-slide-nests", "geo.v1:-nope", "geo.v1:-nests-nests", "flat.v2", "geo.v2:-nests", "geo.v1:-nests-slide-key-swap-ladder-arms"):
        with pytest.raises(ValueError):
            mx.Geometry.parse(bad)
    assert mx.Geometry().header() is None and mx.Geometry.flat_table().header() == {"version": "flat.v1"}
    assert g.header() == {"version": "geo.v1:-nests-slide", "off": ["nests", "slide"]}
    with pytest.raises(ValueError):
        mx.Geometry.of_off(["bogus"])


# -- byte identity -----------------------------------------------------------------------------------------------------------------------------
def prints(g):
    ix = mx.build_index(gg.rows(), gg.DECLS, geometry=g)
    return ix.index_sha


def test_the_default_profile_is_the_crosses_byte_for_byte_the_tree_before_the_profile():
    p = gg.index_prints()
    assert p == GOLD["index_crosses"]
    assert gg.index_prints(geometry=mx.Geometry()) == GOLD["index_crosses"] and gg.index_prints(geometry=mx.CROSS_VERSION) == GOLD["index_crosses"]


def test_all_switches_off_is_the_flat_table_byte_for_byte_the_a3f_of_the_tree_before_the_profile():
    assert gg.index_prints(flat=True) == GOLD["index_flat"]
    assert gg.index_prints(geometry=geo_off(*ALL)) == GOLD["index_flat"]                     # the six switches, each off, give the flat table
    assert gg.index_prints(geometry=mx.FLAT_VERSION) == GOLD["index_flat"]
    # not by the name: all six built one by one (the builder reads the switches, not a flag)
    b = mx.IndexBuilder(geometry=mx.Geometry(nests=False, slide=False, key=False, swap=False, ladder=False, arms=False))
    assert b.flat and b.geo.version() == "flat.v1"


def test_the_stored_ledgers_of_the_default_and_of_the_flat_session_are_the_same_bytes(tmp_path):
    assert gg.session_prints(tmp_path, "c", dict(M6D)) == GOLD["session_crosses"]
    assert gg.session_prints(tmp_path, "f", dict(M6D, index=mem.INDEX_FLAT)) == GOLD["session_flat"]
    assert gg.session_prints(tmp_path / "x", "f", dict(M6D, index=geo_off(*ALL).version())) == GOLD["session_flat"]      # all off, spelled as the profile


# -- each switch changes its component and nothing else ------------------------------------------------------------------------------------------
def test_leave_one_out_changes_only_its_component():
    cx, co = obj_of(mx.Geometry())
    # nests: no nest, scope = topic string, an event is not completed; edges, keys, key views of the swap are those of the crosses
    ix, o = obj_of(geo_off("nests"))
    assert ix.nests == () and o["nests"] == [] and o["edges"] == co["edges"] and any(c.tank == "F4" for c in ix.clauses) and not any(c.tank == "F4" for c in mx.build_index(gg.rows(), gg.DECLS).clauses)
    sc = {(s.prov.sid): s.scope for c in ix.crosses for _, ss in c.slots for s in ss}
    assert all(sc[i] == "新製品" for i in range(3, 10) if i in sc) and all(sc[i] == "新製品の開発" for i in range(12, 20) if i in sc)
    kk = {(c.tank, c.centre, sl, s.phrase, s.prov.sid): s.key for c in ix.crosses for sl, ss in c.slots for s in ss}
    k0 = {(c.tank, c.centre, sl, s.phrase, s.prov.sid): s.key for c in cx.crosses for sl, ss in c.slots for s in ss}
    both = set(kk) & set(k0)
    assert len(both) > 20 and all(kk[x] == k0[x] for x in both)
    # slide: only the edges (and the version) differ
    ix, o = obj_of(geo_off("slide"))
    assert o["edges"] == [] and co["edges"] != [] and {k: v for k, v in o.items() if k not in ("edges", "v")} == {k: v for k, v in co.items() if k not in ("edges", "v")}
    # key: keys are (0,0,0), seats of an arm are in sid order; the notes keep their swap view
    ix, o = obj_of(geo_off("key"))
    assert all(s.key == (0, 0, 0) for c in ix.crosses for _, ss in c.slots for s in ss)
    assert all([s.prov.sid for s in ss] == sorted(s.prov.sid for s in ss) for c in ix.crosses for _, ss in c.slots)
    assert any(n["type"] == "REVERSAL_X" and n["key"] is not None for n in ix.notes) and o["edges"] == co["edges"] and o["nests"] == co["nests"]
    # swap: the same detections, key null
    ix, o = obj_of(geo_off("swap"))
    assert [(n["type"], n["sid"]) for n in ix.notes] == [(n["type"], n["sid"]) for n in cx.notes]
    assert all(n["key"] is None for n in ix.notes if n["type"] == "REVERSAL_X") and any(n["key"] is not None for n in cx.notes if n["type"] == "REVERSAL_X")
    assert {k: v for k, v in o.items() if k not in ("notes", "v")} == {k: v for k, v in co.items() if k not in ("notes", "v")}
    # ladder / arms: only the third part of the key changes; the structure is the same
    for comp in ("ladder", "arms"):
        ix, o = obj_of(geo_off(comp))
        ks = [(s.prov.sid, s.slot, s.key) for c in ix.crosses for _, ss in c.slots for s in ss]
        k0 = [(s.prov.sid, s.slot, s.key) for c in cx.crosses for _, ss in c.slots for s in ss]
        assert len(ks) == len(k0) and any(a != b for a, b in zip(ks, k0)), comp
        assert sorted(a[:2] for a in ks) == sorted(b[:2] for b in k0)
        assert o["edges"] == co["edges"] and o["nests"] == co["nests"] and o["notes"] == co["notes"] and o["clauses"] == co["clauses"]


def test_the_key_n_p_do_not_depend_on_the_arm_assignment_and_ladder_and_arms_are_inert_without_the_key():
    cx = mx.build_index(gg.rows(), gg.DECLS)
    for comp in ("ladder", "arms"):
        ix = mx.build_index(gg.rows(), gg.DECLS, geometry=geo_off(comp))
        for c, c0 in zip(ix.crosses, cx.crosses):
            for (_, ss), (_, ts) in zip(c.slots, c0.slots):
                assert sorted((s.prov.sid, s.slot, s.key[:2]) for s in ss) == sorted((s.prov.sid, s.slot, s.key[:2]) for s in ts)
    a = mx.build_index(gg.rows(), gg.DECLS, geometry=geo_off("key"))
    b = mx.build_index(gg.rows(), gg.DECLS, geometry=geo_off("key", "ladder", "arms"))
    assert {k: v for k, v in a.to_obj().items() if k != "v"} == {k: v for k, v in b.to_obj().items() if k != "v"}


def test_add_one_in_changes_only_its_component_over_the_flat_table():
    fl = mx.build_index(gg.rows(), gg.DECLS, flat=True).to_obj()
    for comp in ("nests", "slide", "swap"):
        g = geo_off(*[c for c in ALL if c != comp])
        o = mx.build_index(gg.rows(), gg.DECLS, geometry=g).to_obj()
        assert o != fl, comp
    o = mx.build_index(gg.rows(), gg.DECLS, geometry=geo_off(*[c for c in ALL if c != "slide"])).to_obj()
    assert {k: v for k, v in o.items() if k not in ("edges", "v")} == {k: v for k, v in fl.items() if k not in ("edges", "v")} and o["edges"] != []


def test_incremental_equals_full_rebuild_for_every_single_off_and_single_on_profile():
    profiles = [geo_off(c) for c in ALL] + [geo_off(*[x for x in ALL if x != c]) for c in ALL]
    for g in profiles:
        p = gg.index_prints(geometry=g)
        assert p["build"] == p["incremental"], g.version()


# -- begin row, replay, answer run ------------------------------------------------------------------------------------------------------------------
def test_a_partial_profile_is_recorded_in_the_begin_row_replays_and_the_answer_run_says_so(tmp_path):
    g = geo_off("nests", "swap")
    v = dict(M6D, index=g.version())
    assert mem.check_versions({"index": mx.CROSS_VERSION}) == mem.V4_VERSIONS_V2 and mem.check_versions({"index": g.version()})["index"] == g.version()
    with pytest.raises(Refuse):
        mem.check_versions({"index": "geo.v1:-swap-nests"})
    s = new_store(tmp_path, "p").begin("test-model", profile=mem.PROFILE_V4, versions=v)
    h = s.rows()[0]["result"]["header"]
    assert h["index"] == {"version": "geo.v1:-nests-swap", "off": ["nests", "swap"]}
    s.call("declare_topic", {"text": "新製品"})
    for t in gg.RICH[:8]:
        assert s.write(t)["ok"]
    sha_ = s.run.builder.index().index_sha
    s.commit()
    assert mem.verify_store(str(tmp_path / "p"), mem.FROM_HEADER)["status"] == "OK"
    ms = mem.MemStore(str(tmp_path / "p"))
    assert ms.index().index_sha == sha_ and ms.index().geo == g and mem.session_versions(os.path.join(str(tmp_path / "p"), "sessions", ms.check()[0]["sessions"][0]["run_id"]))["index"] == g.version()
    snap = ma.write_snapshot(str(tmp_path / "p"), crosses=True, versions=True)
    a = ma.AnswerSession(str(tmp_path / "p"), "認証の期限は何ですか", "test-model", snapshot=snap, answer_version=ma.ANSWER_V17)
    assert a.begin_result["mem_answer"]["index"] == g.version() and a.run.index().geo == g
    a.call("recall", {"question": "認証の期限は何ですか"})
    # a store has one bundle: a crosses session may not join it
    with pytest.raises(Refuse):
        new_store(tmp_path, "p").begin("test-model", profile=mem.PROFILE_V4)


def test_the_answer_rules_are_untouched_in_every_variant_an_absent_fact_is_never_an_answer(tmp_path):
    for i, g in enumerate([mx.Geometry()] + [geo_off(c) for c in ALL] + [geo_off(*ALL)] + [geo_off(*[x for x in ALL if x != c]) for c in ALL]):
        name = "s%d" % i
        s = new_store(tmp_path, name).begin("test-model", profile=mem.PROFILE_V4, versions=dict(M6D, **({} if g.crosses else {"index": g.version()})))
        s.call("declare_topic", {"text": "新製品"})
        for t in ("認証の期限は金曜", "決済の期限は月曜"):
            s.write(t)
        s.commit()
        snap = ma.write_snapshot(str(tmp_path / name), crosses=True, versions=True)
        a = ma.AnswerSession(str(tmp_path / name), "認証の期限は何ですか", "test-model", snapshot=snap, answer_version=ma.ANSWER_V17)
        r = a.call("recall", {"question": "認証の期限は何ですか"})
        assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == ["金曜"], g.version()
        occ = r["answers"][0]["occurrences"][0]
        assert a.call("weave_span", {"sid": occ["sid"], "tier": "WORD", "first": occ["span"][0], "last": occ["span"][1]})["ok"] and a.call("emit", {})["ok"]
        assert ma.verify_answer(a.ledger.dir, str(tmp_path / name))["status"] == "OK"
        b = ma.AnswerSession(str(tmp_path / name), "認証の担当は誰ですか", "test-model", snapshot=snap, answer_version=ma.ANSWER_V17)
        r2 = b.call("recall", {"question": "認証の担当は誰ですか"})
        assert r2["verdict"] != "ANSWER", g.version()


def test_the_recall_and_detection_sources_are_not_edited_by_ticket_c():
    # memask.py (recall), memdetect.py and memshape.py: pinned to the bytes of line3 a8296ae4 (the answer rules live there and in memanswer.py, whose only edits are the index-version plumbing)
    for f, want in PINS.items():
        assert hashlib.sha256(open(os.path.join(ROOT, "verantyx", "loom", f), "rb").read()).hexdigest() == want, f


# -- determinism -------------------------------------------------------------------------------------------------------------------------------
def test_every_profile_gives_the_same_bytes_under_every_hash_seed(tmp_path):
    code = ("import sys, json; sys.path.insert(0, %r); import geo_golden as g; from verantyx.loom import memcross as mx;"
            "print(json.dumps([g.index_prints(geometry=mx.Geometry.of_off(o)) for o in ((), ('nests',), ('key', 'swap'), ('ladder',), ('arms', 'slide'), ('nests', 'slide', 'key', 'swap', 'ladder'))], sort_keys=True))") % HERE
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=os.pathsep.join([ROOT, HERE]))
        o = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=600)
        assert o.returncode == 0, o.stderr[-800:]
        outs.append(o.stdout.strip())
    assert len(set(outs)) == 1


# -- no clock / float / process / network in the loom files touched -----------------------------------------------------------------------------------
@pytest.mark.parametrize("fn", ["memcross.py", "memview.py"])
def test_the_touched_loom_files_have_no_clock_float_process_or_network(fn):
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "verantyx", "loom", fn), encoding="utf-8").read())
    bad = {"subprocess", "socket", "urllib", "requests", "http", "time", "datetime", "random", "os"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not ({a.name.split(".")[0] for a in node.names} & bad), fn
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in bad, fn
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            raise AssertionError("a float constant in %s" % fn)


# -- the meter: arm names ---------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def meter2():
    if METER2 not in sys.path:
        sys.path.insert(0, METER2)
    import importlib
    return importlib.import_module("meter2")


def test_the_ablation_arm_names_resolve_to_the_profiles(meter2):
    assert mx.ablation_variants()[:2] == ("A3", "A3f") and len(mx.ablation_variants()) == 14
    for c in ALL:
        a = meter2.arm_spec("A3-no" + c)
        assert a["arm"] == "notes" and a["geometry"] == geo_off(c) and a["index"] == geo_off(c).version() and a["no_key_route"] == (c == "swap")
        b = meter2.arm_spec("A3f-plus" + c)
        on = {c} | ({"key"} if c in ("ladder", "arms") else set())
        assert b["geometry"] == geo_off(*[x for x in ALL if x not in on]) and b["no_key_route"] == (c != "swap")
    assert meter2.arm_spec("A3")["index"] is None and meter2.arm_spec("A3f")["index"] == mem.INDEX_FLAT
    assert meter2.versions_of("A3-nokey", "m6d")["index"] == "geo.v1:-key" and "index" not in meter2.versions_of("A3", "m6d")
    for bad in ("A3-nobogus", "A3f-plus", "A4", "A3-no"):
        with pytest.raises(meter2.MeterError):
            meter2.arm_spec(bad)
    import prompts
    assert all(prompts.system_prompt(n, ph) == prompts.system_prompt("A3", ph) for n in ("A3-noswap", "A3f-pluskey") for ph in ("story", "question"))


def test_the_default_arms_of_the_stub_meter_are_the_same_bytes_as_before_the_profile(meter2, tmp_path):
    import stub_client
    from test_pub_m7_m8_m10 import micro_story
    for arm in ("A3", "A3f"):
        r = meter2.run_one(micro_story(), arm, 1, client=stub_client.StubClient(), model="stub-model", out_root=str(tmp_path), n_checkpoints=2)
        h = hashlib.sha256()
        import glob
        for p in sorted(glob.glob(os.path.join(str(tmp_path), "MICRO", arm, "r01", "store", "sessions", "*", "ops.jsonl"))):
            h.update(open(p, "rb").read())
        r.pop("wall_ns")
        assert [h.hexdigest(), hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()] == GOLD["meter2_stub"][arm], arm
        assert "geometry" not in r


def test_every_ablation_arm_runs_end_to_end_with_the_stub_and_verifies(meter2, tmp_path):
    import stub_client
    from test_pub_m7_m8_m10 import micro_story
    seen = {}
    for arm in mx.ablation_variants()[2:]:
        r = meter2.run_one(micro_story(), arm, 1, client=stub_client.StubClient(), model="stub-model", out_root=str(tmp_path), n_checkpoints=2)
        assert r["ended"] == "complete" and r["store"]["verify"] == "OK" and r["answers"]["total"]["n"] == 4 and r["answers"]["total"]["confident_wrong"] == 0, arm
        assert r["geometry"]["version"] == meter2.arm_spec(arm)["index"]
        seen[arm] = r["answers"]["total"]["right"]
    assert set(seen.values()) <= {2, 3, 4}


# -- the offline measurement scripts -----------------------------------------------------------------------------------------------------------------
def ablate():
    p = os.path.join(ROOT, "experiments", "line3", "pub", "ablate")
    if p not in sys.path:
        sys.path.insert(0, p)
    import importlib
    return importlib.import_module("ablate")


def test_the_ablation_script_refuses_held_out_paths_and_unknown_variants():
    ab = ablate()
    with pytest.raises(ab.AblateError):
        ab.check_dev_path(os.path.join(ROOT, "experiments", "line3", "bank_ls", "heldout_1", "stories.jsonl"))
    with pytest.raises(ab.AblateError):
        ab.check_dev_path(os.path.join(ROOT, "experiments", "line3", "bank_ls", "stories.jsonl"))
    assert ab.check_dev_path(ab.DEV) == ab.DEV
    with pytest.raises(ab.AblateError):
        ab.parse_variants("A3,A3-nobogus")
    assert ab.parse_variants(None) == list(mx.ablation_variants())


def test_the_dev_driver_runs_a_micro_story_for_every_variant_with_integer_tables():
    ab = ablate()
    from test_pub_m7_m8_m10 import micro_story
    st = micro_story()
    for q in st["questions"]:
        q["form"] = "same"
    res = {}
    for v in ("A3", "A3f", "A3-nonests", "A3f-plusnests"):
        res[v] = ab.dev_job((v, st))
    assert res["A3"]["index_sha"] != res["A3f"]["index_sha"] and res["A3-nonests"]["index_sha"] != res["A3"]["index_sha"]
    assert all(q["kind"] in ab.KINDS for r in res.values() for q in r["questions"])
    for v, r in res.items():
        t = ab.empty_tally()
        for q in r["questions"]:
            ab.add_questions(t, q["kind"], q)
        f = ab.freeze(t)
        assert f["questions"]["absent"]["n"] == 1 and f["questions"]["absent"].get("admitted", 0) == 0, v


def test_the_meter_tables_over_a_stored_run_have_integer_cells_and_deltas():
    ab = ablate()
    res = ab.run_meter(["A3", "A3f", "A3-nonests", "A3f-plusnests"], 1, limit=1)
    assert set(res["variants"]) == {"A3", "A3f", "A3-nonests", "A3f-plusnests"} and res["runs"] == 1
    d = ab.deltas(res)
    assert set(d) == {"A3-nonests", "A3f-plusnests"} and d["A3-nonests"]["vs"] == "A3" and d["A3f-plusnests"]["vs"] == "A3f"
    assert all(v["not_verified"] == [] for v in res["variants"].values())
    assert "plain reached/exact/extra" in ab.md(dict(res, deltas=d))

    def ints(x):
        if isinstance(x, float):
            raise AssertionError("a float in the table")
        if isinstance(x, dict):
            [ints(v) for v in x.values()]
        if isinstance(x, list):
            [ints(v) for v in x]
    ints(res)

"""LOOM-notes tests: the typed notes CONFLICT / UNANCHORED / NO_RECORD (a thread-wide consistency pass at `read` / `emit` that points and lets
pass) and the self-correction metrics (docs/LINE3_LOOM_DESIGN.md 12.2 "LOOM-notes", owner 「気づきの置き方」; L-LOOM-95..).

The guarantee under test: notes never change `text`, `output_sha`, a refusal or the bytes of any existing ledger row.  They travel in the RESULT of
`read` / `emit` (key `notes`, absent when empty) and in a row of their own (actor "loom", op "loom_note") appended right after the read / emit row;
replay re-derives that row and requires it.
"""
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import textwrap

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom import notes as nt
from verantyx.loom import scripted_code as sc
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from verantyx.loom.ops import Run
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
from loom_common import CORPUS, PY, ROOT, TOY, rows, server, weaver

FIXTURE = os.path.join(ROOT, "experiments/line3/loom/fixture_repo")
TASKS_FILE = os.path.join(ROOT, "experiments/line3/loom/tasks_code.jsonl")
TOKYO_CA_HEAD = "28cf7c5682cd8fa44d32c679c670fb41bcf7ad748510cb22bef3e0f4141ecd5a"      # `vera loom demo` before LOOM-notes (and after)
TOKYO_RO_HEAD = "734218e79f77e388471a750f5e3a7b33a3fd9328adf40da68182cbe53d4e20d3"
HEAD_PYTHON = (3, 11, 14)                                                            # the interpreter those two HEADs were measured on
TOKYO_CA_SHA = "70a569eba879736d1bf1b7a6e86ff8a281216d571a2ce4fc9c3d42e4d83470e2"
TOKYO_RO_SHA = "c74f3319b605745e07a008b876bae444d9cb0dc4ed59387af165176cde9816c8"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


score = _load("loom_score_for_notes", os.path.join(ROOT, "experiments/line3/loom/score.py"))
code_harness = _load("loom_code_harness_for_notes", os.path.join(ROOT, "experiments/line3/loom/code_harness.py"))


@pytest.fixture(scope="module")
def corpus():
    with open(CORPUS, "rb") as f:
        return Corpus.load(f.read())


def types(notes):
    return [n["type"] for n in notes]


# ---- small weaving helpers (the 18 operations, nothing else) -----------------------------------------------------------------
def add(w, text, kind="constructed", tier=None):
    a = dict(text=text, kind=kind)
    if tier:
        a["tier"] = tier
    r = w.call("add", **a)
    assert r["ok"], r
    return r["uid"]


def cross(w, tier="WORD", L=2, centre=None, arms=None, link=True, topic=False):
    """A cross with `centre` (uid) and `arms` {axis: [uid, ...]} (reading order, outer -> inner); linked at the end of the thread."""
    cid = w.call("open_cross", tier=tier, L=L)["cid"]
    if centre is not None:
        assert w.call("seat", cid=cid, seat="centre", uid=centre)["ok"]
    for ax, uids in (arms or {}).items():
        assert w.call("seat_run", cid=cid, arm=ax, uids=uids)["ok"]
    if topic:
        w.call("topic", cid=cid, on=True)
    if link:
        assert w.call("link", cid=cid)["ok"]
    return cid


def conflicting_thread(w):
    """c1 = Ωa <- Ωb on の; c2 = Ωa <- Ωc on の.  (Two units with the surface Ωa cannot be added: the second is a different uid with the same
    surface, which is the point: the same centre unit is identified by its surface.)"""
    a1, a2 = add(w, TOY[0]), add(w, TOY[0])
    b, c = add(w, TOY[1]), add(w, TOY[2])
    c1 = cross(w, centre=a1, arms={"+x": [b]})
    c2 = cross(w, centre=a2, arms={"+x": [c]})
    return c1, c2, (a1, a2, b, c)


# ================================================================================================================================
# CONFLICT, prose
# ================================================================================================================================
def test_conflict_prose_two_crosses_same_centre_same_arm_different_units(tmp_path):
    w = weaver(server(tmp_path))
    c1, c2, (a1, a2, b, c) = conflicting_thread(w)
    r = w.call("read")
    assert r["ok"] and types(r["notes"]) == [nt.CONFLICT]
    n = r["notes"][0]
    assert (n["kind"], n["tier"], n["centre"], n["arm"], n["particle"]) == ("arm_contents", "WORD", TOY[0], "+x", "の")
    assert [v["cids"] for v in n["variants"]] == [[c1], [c2]]
    assert [[u["s"] for u in v["units"]] for v in n["variants"]] == [[TOY[1]], [TOY[2]]]
    assert [[u["uid"] for u in v["units"]] for v in n["variants"]] == [[b], [c]]
    # it does not block: the text is read, there is no refusal
    assert r["text"] == TOY[1] + "の" + TOY[0] + TOY[2] + "の" + TOY[0] and r["refusals"] == []


def test_conflict_with_records_the_ticket_example_shape(tmp_path, corpus):
    """首都 <- 東京 against 首都 <- 大阪 (record units of the real corpus; the two 首都 are two uids with one surface)."""
    w = weaver(server(tmp_path))
    cs = [add(w, t, "record", "WORD") for t in ("首都", "東京", "首都", "大阪")]
    cross(w, centre=cs[0], arms={"+x": [cs[1]]})
    cross(w, centre=cs[2], arms={"+x": [cs[3]]})
    notes = w.call("read")["notes"]
    conf = [n for n in notes if n["type"] == nt.CONFLICT]
    assert len(conf) == 1 and conf[0]["centre"] == "首都"
    assert [[u["s"] for u in v["units"]] for v in conf[0]["variants"]] == [["東京"], ["大阪"]]
    assert [[u["kind"] for u in v["units"]] for v in conf[0]["variants"]] == [["record"], ["record"]]
    # the real corpus says 東京 is followed by で once and never by の: ONE sentence is below the floor (OP-LOOM-5, L-LOOM-111), so the design's own
    # example no longer flags as UNANCHORED (before the floor it did)
    assert corpus.adhesion["WORD"].adj("東京", "で") == 1 and corpus.adhesion["WORD"].adj("東京", "の") == 0
    assert types(notes) == [nt.CONFLICT]


def test_conflict_counts_a_constructed_unit_against_a_record_unit(tmp_path):
    w = weaver(server(tmp_path))
    cs = [add(w, "首都", "record", "WORD"), add(w, "東京", "record", "WORD"), add(w, "首都", "record", "WORD"), add(w, TOY[3])]
    cross(w, centre=cs[0], arms={"+x": [cs[1]]})
    cross(w, centre=cs[2], arms={"+x": [cs[3]]})
    notes = [n for n in w.call("read")["notes"] if n["type"] == nt.CONFLICT]
    assert len(notes) == 1
    assert [[u["kind"] for u in v["units"]] for v in notes[0]["variants"]] == [["record"], ["constructed"]]


def test_conflict_is_exactly_the_same_centre_same_arm_different_content(tmp_path):
    """Every near miss: the same content, an empty arm, another arm, another centre, an unlinked cross, then the topic mark and L (ignored) with
    different content: the one conflict."""
    w = weaver(server(tmp_path))
    fresh = lambda t: add(w, t)
    centre = lambda t="首都": add(w, t, "record", "WORD")                                  # a record centre: no arm, so no adhesion question
    c1 = cross(w, centre=centre(), arms={"+x": [fresh(TOY[1])]})
    cross(w, centre=centre(), arms={"+x": [fresh(TOY[1])]})                              # the same content (Ωb twice): not a contradiction
    assert "notes" not in w.call("read")
    cross(w, centre=centre(), arms={"-z": [fresh(TOY[2])]})                              # another arm: が against の
    assert "notes" not in w.call("read")
    cross(w, centre=centre())                                                            # an empty の arm
    assert "notes" not in w.call("read")
    cross(w, centre=centre("大阪"), arms={"+x": [fresh(TOY[2])]})                        # another centre
    assert "notes" not in w.call("read")
    cross(w, centre=centre(), arms={"+x": [fresh(TOY[3])]}, link=False)                  # unlinked: not in the thread, not read
    assert "notes" not in w.call("read")
    cid = cross(w, centre=centre(), arms={"+x": [fresh(TOY[3])]}, topic=True, L=3)       # topic mark and L are ignored; the content differs
    notes = w.call("read")["notes"]
    assert types(notes) == [nt.CONFLICT]
    assert [v["cids"] for v in notes[0]["variants"]] == [["c1", "c2"], [cid]]
    assert [[u["s"] for u in v["units"]] for v in notes[0]["variants"]] == [[TOY[1]], [TOY[3]]]


def test_conflict_arm_content_is_the_whole_ordered_tuple(tmp_path):
    w = weaver(server(tmp_path))
    fresh = lambda t: add(w, t)
    cross(w, L=3, centre=fresh(TOY[0]), arms={"+x": [fresh(TOY[1]), fresh(TOY[2])]})
    cross(w, L=3, centre=fresh(TOY[0]), arms={"+x": [fresh(TOY[1]), fresh(TOY[2])]})
    assert "notes" not in w.call("read")                               # the same pair in the same order
    cross(w, L=3, centre=fresh(TOY[0]), arms={"+x": [fresh(TOY[2]), fresh(TOY[1])]})      # the same surfaces, the other order
    notes = w.call("read")["notes"]
    assert types(notes) == [nt.CONFLICT] and len(notes[0]["variants"]) == 2 and notes[0]["variants"][0]["cids"] == ["c1", "c2"]


def test_three_variants_and_two_arms_give_one_note_per_arm_in_reading_order(tmp_path):
    w = weaver(server(tmp_path))
    ids = [add(w, TOY[0]) for _ in range(3)]
    x = [add(w, t) for t in (TOY[1], TOY[2], TOY[3])]
    z = [add(w, t) for t in (TOY[4], TOY[5], TOY[6])]
    for i in range(3):
        cross(w, centre=ids[i], arms={"+x": [x[i]], "-z": [z[i]]})
    notes = w.call("read")["notes"]
    assert types(notes) == [nt.CONFLICT, nt.CONFLICT]
    assert [n["arm"] for n in notes] == ["-z", "+x"]                   # が is read before の (ARM_ORDER), the notes follow the reading order
    assert all(len(n["variants"]) == 3 for n in notes)


def test_no_false_conflict_on_the_worked_example(tmp_path):
    for task_id, text, sha in (("demo/tokyo_ca", "東京は日本の首都です", TOKYO_CA_SHA), ("demo/tokyo_ro", "東京は日本の首都", TOKYO_RO_SHA)):
        srv = server(tmp_path / task_id.split("/")[1])
        w = ScriptedWeaver(srv, task_id, "claude-haiku-4-5", "w")
        res = weave_tokyo(w)
        assert res["text"] == text and res["output_sha"] == sha
        assert "notes" not in res
        run = srv.runs["w"].run
        assert nt.compute(run) == []
        assert not [r for r in rows(tmp_path / task_id.split("/")[1] / "runs" / "w") if r["actor"] == "loom"]


def test_the_demo_ledgers_are_byte_for_byte_what_they_were_before_the_notes(tmp_path):
    """`vera loom demo` writes demo_ca / demo_ro; their HEADs were recorded from the code before LOOM-notes (the demo produces no note)."""
    p = subprocess.run([PY, "-m", "verantyx.cli", "loom", "demo", "--corpus", CORPUS, "--runs-dir", str(tmp_path / "runs")],
                       env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    for d, n in (("demo_ca", 17), ("demo_ro", 14)):
        rs = rows(tmp_path / "runs" / d)
        assert len(rs) == n and not [r for r in rs if r["actor"] == "loom"] and not any("notes" in r["result"] for r in rs)
    assert json.loads(next(l for l in (tmp_path / "runs/demo_ca/ops.jsonl").read_text().splitlines() if '"op":"emit"' in l))["result"]["output_sha"] == TOKYO_CA_SHA
    # the HEAD is a function of the interpreter too (L-LOOM-47 puts the full python version in the begin row): the literal is pinned for the
    # patch release it was measured on and skipped elsewhere; the equality of the model rows with the pass switched off is tested above anyway
    if sys.version_info[:3] != HEAD_PYTHON:
        pytest.skip("HEAD literals were measured on python %s" % (HEAD_PYTHON,))
    assert (tmp_path / "runs/demo_ca/HEAD").read_text().strip() == TOKYO_CA_HEAD
    assert (tmp_path / "runs/demo_ro/HEAD").read_text().strip() == TOKYO_RO_HEAD


# ================================================================================================================================
# CONFLICT, code
# ================================================================================================================================
def code_server(tmp_path):
    return LoomServer(code_harness.load_tasks(TASKS_FILE, ROOT), str(tmp_path / "runs"))


def code_w(tmp_path, k="K1"):
    srv = code_server(tmp_path)
    w = ScriptedWeaver(srv, "code/" + k.lower(), "test-weaver", "cw")
    assert w.begin()["ok"]
    return srv, w


def lines_S(*lines):
    from verantyx.loom import code as codelib
    return [((len(l) - len(l.lstrip(" "))) // 4, [t for _, t in codelib.tokens_of(l.strip() + "\n")]) for l in lines]


def weave_lines(w, *lines):
    sc.link_all(w, sc.weave_statements(w, lines_S(*lines)))


def test_code_conflict_the_same_def_bound_twice(tmp_path):
    srv, w = code_w(tmp_path)
    weave_lines(w, "def double(x):", "    return mul(x, 2)", "def double(y):", "    return mul(y, 3)")
    r = w.call("read")
    notes = [n for n in r["notes"] if n["type"] == nt.CONFLICT]
    assert len(notes) == 1
    n = notes[0]
    assert (n["kind"], n["name"], n["scope"]) == ("name_bound_twice", "double", "<module>")
    assert [(b["how"], b["line"]) for b in n["bindings"]] == [("def", 1), ("def", 3)]
    assert [b["cid"] for b in n["bindings"]] == ["c1", "c3"]


def test_code_conflict_import_against_def_and_def_against_assignment(tmp_path):
    srv, w = code_w(tmp_path, "K3")
    weave_lines(w, "from calc.ops import add", "def add(a, b):", "    return a", "mul = 3", "def mul(a, b):", "    return a")
    notes = [n for n in w.call("read")["notes"] if n["type"] == nt.CONFLICT]
    assert [(n["name"], [b["how"] for b in n["bindings"]]) for n in notes] == [("add", ["import", "def"]), ("mul", ["assign", "def"])]


def test_code_conflict_is_not_raised_for_reassignment_repeats_or_other_scopes(tmp_path):
    srv, w = code_w(tmp_path, "K2")
    weave_lines(w,
                "def total(xs):", "    out = 0", "    for x in xs:", "        out = add(out, x)", "    return out",   # the K2 accumulator
                "def total2(xs):", "    out = 0", "    return out",                                              # `out` in another scope
                "from calc.ops import add", "from calc.ops import add",                                          # the same import twice
                "def helper(q):", "    return q", "def helper(q):", "    return q")                              # the same def twice
    assert "CONFLICT" not in types(w.call("read").get("notes", []))


def test_code_scope_matters_a_def_inside_a_def_does_not_clash_with_the_module(tmp_path):
    srv, w = code_w(tmp_path)
    weave_lines(w, "def double(x):", "    def inner(y):", "        return y", "    return inner(x)", "def inner(z):", "    return z")
    assert "CONFLICT" not in types(w.call("read").get("notes", []))


@pytest.mark.parametrize("k", ["K1", "K2", "K3", "K4", "K5"])
def test_the_five_reference_weaves_have_no_conflict_and_no_unanchored(tmp_path, k):
    srv, w = code_w(tmp_path, k)
    res = sc.weave_k(w, k)
    assert res["ok"] and res["status"] == "emitted"
    for r in rows(tmp_path / "runs" / "cw"):
        got = [n["type"] for n in r["args"].get("notes", [])] if r["actor"] == "loom" else []
        assert nt.CONFLICT not in got and nt.UNANCHORED not in got
    # the only notes are NO_RECORD: the new names (double, total, ...) were looked up, found nothing and were constructed
    notes = [n for r in rows(tmp_path / "runs" / "cw") if r["actor"] == "loom" for n in r["args"]["notes"]]
    assert notes and {n["type"] for n in notes} == {nt.NO_RECORD}


# ================================================================================================================================
# UNANCHORED, real adhesion counts
# ================================================================================================================================
def test_the_arms_and_their_particles_are_the_ones_the_notes_name():
    from verantyx.loom.state import SPEC
    assert {SPEC.arm_of_axis(ax): ax for ax in ("+x", "-x", "+y", "-y", "+z", "-z")} == {"の": "+x", "に": "-x", "で": "+y", "と": "-y", "を": "+z", "が": "-z"}
    assert nt.ARM_PARTICLES == ("の", "に", "で", "と", "を", "が") and "は" not in nt.ARM_PARTICLES


def pick_unit(corpus, tier="WORD"):
    """The unit with the most の evidence, no が evidence and no Latin letter or digit (deterministic: sorted by count, then surface)."""
    adh = corpus.adhesion[tier]
    cand = [u for u in adh.units() if adh.adj(u, "の") > 0 and adh.adj(u, "が") == 0 and len(u) >= 2 and not any(c.isascii() and c.isalnum() for c in u)]
    assert cand
    cand.sort(key=lambda u: (-adh.adj(u, "の"), u))
    return cand[0]


def test_the_picked_unit_has_the_expected_real_counts(corpus):
    u = pick_unit(corpus)
    adh = corpus.adhesion["WORD"]
    assert u == "現在"
    assert {p: adh.adj(u, p) for p in nt.ARM_PARTICLES} == {"の": 9, "に": 0, "で": 1, "と": 0, "を": 0, "が": 0}


def test_unanchored_a_record_with_evidence_for_no_but_not_ga_on_the_ga_arm(tmp_path, corpus):
    u = pick_unit(corpus)
    w = weaver(server(tmp_path))
    uid, centre = add(w, u, "record", "WORD"), add(w, "首都", "record", "WORD")
    cross(w, centre=centre, arms={"-z": [uid]})
    notes = w.call("read")["notes"]
    assert types(notes) == [nt.UNANCHORED]
    n = notes[0]
    assert (n["cid"], n["seat"], n["arm"], n["particle"], n["unit"], n["kind"], n["have"]) == ("c1", "-z:0", "-z", "が", u, "record", 0)
    assert n["anchor"] == {"surface": u, "via": "self", "tier": "WORD"}
    assert n["evidence"] == [{"particle": "の", "n": 9}, {"particle": "で", "n": 1}]


def test_unanchored_is_silent_where_the_evidence_agrees_or_is_absent(tmp_path, corpus):
    u = pick_unit(corpus)
    w = weaver(server(tmp_path))
    uid, centre = add(w, u, "record", "WORD"), add(w, "首都", "record", "WORD")
    cross(w, centre=centre, arms={"+x": [uid]})                                          # の: the evidence agrees
    assert "notes" not in w.call("read")
    u2, c2 = add(w, u, "record", "WORD"), add(w, "首都", "record", "WORD")
    cross(w, centre=c2, arms={"+y": [u2]})                                               # で: 1 occurrence, so not contradicted
    assert "notes" not in w.call("read")
    assert all(corpus.adhesion["WORD"].adj("首都", p) == 0 for p in nt.ARM_PARTICLES)
    nev, c3 = add(w, "首都", "record", "WORD"), add(w, "大阪", "record", "WORD")
    assert all(corpus.adhesion["WORD"].adj("首都", p) == 0 for p in nt.ARM_PARTICLES)
    cross(w, centre=c3, arms={"-z": [nev]})                                              # 首都 has no arm evidence at all: nothing to say
    assert "notes" not in w.call("read")


def test_unanchored_ignores_the_topic_relation(tmp_path, corpus):
    """は is the centre relation, not an arm: a unit whose only evidence is は is not 'contradicted' by an arm."""
    adh = corpus.adhesion["WORD"]
    only_wa = [u for u in adh.units() if adh.adj(u, "は") > 0 and all(adh.adj(u, p) == 0 for p in nt.ARM_PARTICLES) and len(u) >= 2
               and not any(c.isascii() and c.isalnum() for c in u)]
    assert only_wa
    w = weaver(server(tmp_path))
    uid, centre = add(w, only_wa[0], "record", "WORD"), add(w, "首都", "record", "WORD")
    cross(w, centre=centre, arms={"-z": [uid]})
    assert "notes" not in w.call("read")


def test_unanchored_constructed_unit_is_anchored_by_its_longest_suffix_with_evidence(tmp_path, corpus):
    u = pick_unit(corpus)
    cons = "Ω" + u
    assert corpus.tiers_holding(cons) == []
    w = weaver(server(tmp_path))
    uid, centre = add(w, cons), add(w, "首都", "record", "WORD")
    cross(w, centre=centre, arms={"-z": [uid]})
    notes = w.call("read")["notes"]
    assert types(notes) == [nt.UNANCHORED]
    n = notes[0]
    assert (n["unit"], n["kind"], n["anchor"]) == (cons, "constructed", {"surface": u, "via": "suffix", "tier": "WORD"})
    assert n["evidence"][0] == {"particle": "の", "n": 9}
    # the same constructed unit on the の arm: silent
    w2 = weaver(server(tmp_path / "b"))
    uid2, centre2 = add(w2, cons), add(w2, "首都", "record", "WORD")
    cross(w2, centre=centre2, arms={"+x": [uid2]})
    assert "notes" not in w2.call("read")
    # a constructed unit with no suffix that has evidence: silent (no anchor)
    w3 = weaver(server(tmp_path / "c"))
    uid3, centre3 = add(w3, TOY[0]), add(w3, "首都", "record", "WORD")
    cross(w3, centre=centre3, arms={"-z": [uid3]})
    assert "notes" not in w3.call("read")


def test_unanchored_picks_the_longest_suffix_not_the_whole_string_and_never_the_unit_itself(corpus):
    """anchor_of on the real tables: a constructed unit's whole surface is not looked at (it is in no tier), its proper suffixes are, longest first."""
    adh = corpus.adhesion["WORD"]
    from verantyx.loom.state import Unit
    u = Unit("u1", "Ω現在", "constructed", None, {"by": "m", "at": 1})
    assert nt.anchor_of(adh, u)[:2] == ("現在", "suffix")
    u = Unit("u2", "Ω線", "constructed", None, {"by": "m", "at": 1})
    assert adh.adj("線", "の") > 0 and nt.anchor_of(adh, u) is None                       # OP-LOOM-5: a suffix anchor is at least 2 characters
    u = Unit("u2b", "ΩΩ現在", "constructed", None, {"by": "m", "at": 1})
    assert nt.anchor_of(adh, u)[:2] == ("現在", "suffix")
    u = Unit("u3", "現在Ω", "constructed", None, {"by": "m", "at": 1})
    assert nt.anchor_of(adh, u) is None                                                  # a PREFIX is not an anchor (particles follow the end)


def test_unanchored_is_a_note_not_a_refusal_and_does_not_touch_the_gate(tmp_path, corpus, monkeypatch):
    """In strict_npa a record on the wrong arm is also `unstable_cross` (the key sees its adhesion); that refusal is the core's and is the same
    with and without the note pass.  The refused emit carries no notes (a refusal is not changed); the dry-run `read` does."""
    u = pick_unit(corpus)

    def go(base):
        w = weaver(server(base), run_id="g")
        uid, centre = add(w, u, "record", "WORD"), add(w, "首都", "record", "WORD")
        cross(w, centre=centre, arms={"-z": [uid]})
        return w.call("read"), w.call("emit")
    r, e = go(tmp_path / "a")
    monkeypatch.setattr(Run, "notes_due", lambda self: [])
    r0, e0 = go(tmp_path / "b")
    assert types(r["notes"]) == [nt.UNANCHORED] and "notes" not in r0
    assert e["ok"] is False and e["refusal"] == "unstable_cross" and "notes" not in e
    assert e == e0 and {k: v for k, v in r.items() if k != "notes"} == r0
    assert [x["type"] for x in r["refusals"]] == ["unstable_cross"]


def test_unanchored_does_not_exist_for_code(tmp_path):
    srv, w = code_w(tmp_path)
    weave_lines(w, "def double(x):", "    return mul(x, 2)")
    assert nt.UNANCHORED not in types(w.call("read").get("notes", []))


# ================================================================================================================================
# NO_RECORD, from the ledger
# ================================================================================================================================
def lookup_then_add(w, text, tier="WORD"):
    r = w.call("lookup", text=text, tier=tier)
    assert r["ok"] and r["matches"] == []
    return add(w, text)


def test_no_record_lookup_empty_then_the_same_surface_constructed(tmp_path, corpus):
    w = weaver(server(tmp_path))
    assert corpus.tiers_holding(TOY[0]) == []
    uid = lookup_then_add(w, TOY[0])                                    # rows 1 (lookup) and 2 (add)
    cross(w, centre=uid)
    r = w.call("read")
    assert types(r["notes"]) == [nt.NO_RECORD]
    n = r["notes"][0]
    assert (n["cid"], n["seat"], n["uid"], n["unit"], n["lookup_i"], n["added_at"]) == ("c1", "centre", uid, TOY[0], 1, 2)


def test_no_record_is_the_last_lookup_of_that_surface_before_the_add_in_any_tier(tmp_path):
    w = weaver(server(tmp_path))
    assert w.call("lookup", text=TOY[0], tier="any")["matches"] == []
    uid = add(w, TOY[0])
    cross(w, centre=uid)
    assert types(w.call("read")["notes"]) == [nt.NO_RECORD]


def test_no_record_needs_the_lookup_to_come_first_and_to_be_the_same_surface(tmp_path):
    w = weaver(server(tmp_path))
    a = add(w, TOY[0])                                                  # added with no lookup at all
    w.call("lookup", text=TOY[0], tier="WORD")                          # looked up only AFTER the add
    b = add(w, TOY[1])
    w.call("lookup", text=TOY[5], tier="WORD")                          # another surface
    cross(w, centre=a)
    cross(w, centre=b)
    assert "notes" not in w.call("read")


def test_no_record_is_silent_for_a_record_and_for_a_unit_outside_the_thread(tmp_path):
    w = weaver(server(tmp_path))
    assert w.call("lookup", text="首都", tier="WORD")["matches"]
    rec = add(w, "首都", "record", "WORD")
    cross(w, centre=rec)
    off = lookup_then_add(w, TOY[7])                                    # constructed after an empty lookup, but never seated / linked
    cross(w, centre=lookup_then_add(w, TOY[8]), link=False)             # seated, not linked
    assert "notes" not in w.call("read")
    assert off


def test_no_record_normalises_nfc_and_survives_a_server_restart(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, run_id="r")
    word = "éΩ"                                                    # decomposed é, then Ω
    nfc = "éΩ"
    assert w.call("lookup", text=word, tier="WORD")["matches"] == []
    uid = add(w, word)
    cross(w, centre=uid)
    first = w.call("read")["notes"]
    assert types(first) == [nt.NO_RECORD] and first[0]["unit"] == nfc
    srv2 = server(tmp_path)                                             # a fresh process: the run is rebuilt by replay, history included
    res = srv2.call("read", {"run_id": "r"})
    assert res["notes"] == first
    assert lg.verify(tmp_path / "runs" / "r", corpus_path=CORPUS)["status"] == "OK"


def test_no_record_in_the_scripted_code_weave_names_the_invented_identifier(tmp_path):
    srv, w = code_w(tmp_path)
    sc.weave_k(w, "K1")
    notes = [n for r in rows(tmp_path / "runs" / "cw") if r["actor"] == "loom" for n in r["args"]["notes"]]
    assert sorted({n["unit"] for n in notes}) == ["2", "double"]        # the new function name and the constant 2 (no record in the fixture)


# ================================================================================================================================
# the ledger: the `loom_note` row, replay, the bytes of everything else
# ================================================================================================================================
def build_noted_run(tmp_path, run_id="n"):
    """A run with a CONFLICT (a stable toy thread): the read, the emit, and a NO_RECORD on top."""
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "prose/ca", "test-weaver", run_id)
    w.begin()
    c1, c2, (a1, a2, b, c) = conflicting_thread(w)
    nr = lookup_then_add(w, TOY[7])
    cross(w, centre=nr)
    r = w.call("read")
    e = w.call("emit")
    return srv, w, r, e


def test_notes_are_in_the_result_and_in_a_note_row_right_after_the_read_and_the_emit(tmp_path):
    srv, w, r, e = build_noted_run(tmp_path)
    assert e["ok"] and e["status"] == "emitted"
    rs = rows(tmp_path / "runs" / "n")
    ops = [(x["actor"], x["op"]) for x in rs]
    ri = ops.index(("model", "read"))
    assert ops[ri + 1] == ("loom", nt.NOTE_OP)
    assert ops[-2:] == [("model", "emit"), ("loom", nt.NOTE_OP)]
    assert types(r["notes"]) == [nt.CONFLICT, nt.NO_RECORD] and e["notes"] == r["notes"]
    for row, res in ((rs[ri + 1], r), (rs[-1], e)):
        assert row["args"]["notes"] == res["notes"] and row["result"] == {"ok": True} and row["args"]["nv"] == nt.NOTES_VERSION == "notes.v2"
        assert set(row["args"]) == {"after", "of", "notes", "nv"}
        assert row["args"]["after"] == row["i"] - 1
    assert (rs[ri + 1]["args"]["of"], rs[-1]["args"]["of"]) == ("read", "emit")
    # the stored read / emit rows hold NO notes: the result a caller sees is a copy
    assert "notes" not in rs[ri]["result"] and "notes" not in rs[-2]["result"]
    assert "notes" in r and "notes" in e
    assert lg.verify(tmp_path / "runs" / "n", corpus_path=CORPUS)["status"] == "OK"
    assert lg.verify(tmp_path / "runs" / "n", corpus_path=CORPUS)["replay"]["status"] == "IDENTICAL"


def noted_then_changed_run(base, notes_on, monkeypatch):
    """A conflicting thread, a read (notes), then an `add`, a cross and the emit: the rows AFTER the first note row are shifted by it."""
    if not notes_on:
        monkeypatch.setattr(Run, "notes_due", lambda self: [])
    try:
        srv = server(base)
        w = ScriptedWeaver(srv, "prose/ca", "test-weaver", "n")
        w.begin()
        conflicting_thread(w)
        r = w.call("read")
        cross(w, centre=add(w, TOY[5]))                                     # an `add` after the noted read
        e = w.call("emit")
    finally:
        monkeypatch.undo()
    return r, e, rows(base / "runs" / "n")


def test_text_output_sha_refusals_and_the_model_rows_are_unchanged_by_the_notes_but_later_rows_shift(tmp_path, monkeypatch):
    """L-LOOM-95 (corrected, L-LOOM-107): the same script with and without the pass.  Byte-identical up to the FIRST note row; after it every
    row keeps op / args / text / output_sha / refusals but NOT `i`, `prev`, `sha`, `state_sha`, and the `prov.at` of a later `add` (and of the
    annotated segments that quote it) moves by the number of note rows before it."""
    r, e, rs = noted_then_changed_run(tmp_path / "with", True, monkeypatch)
    r0, e0, rs0 = noted_then_changed_run(tmp_path / "without", False, monkeypatch)
    assert "notes" not in r0 and "notes" not in e0
    strip = lambda d: {k: v for k, v in d.items() if k != "notes"}
    assert strip(r) == r0                                                       # the first read: nothing earlier shifts
    assert e["text"] == e0["text"] and e["output_sha"] == e0["output_sha"] == hashlib.sha256(e["text"].encode("utf-8")).hexdigest()
    first = next(i for i, x in enumerate(rs) if x["actor"] == nt.NOTE_ACTOR)
    assert rs[:first] == rs0[:first]                                            # bytes, chain and all, up to the first note row
    model = [x for x in rs if x["actor"] != nt.NOTE_ACTOR]
    assert [x["op"] for x in model] == [x["op"] for x in rs0] and len(rs) == len(rs0) + 2
    for x, y in zip(model[first:], rs0[first:]):
        assert (x["actor"], x["op"], x["args"]) == (y["actor"], y["op"], y["args"])
    # ... and the things that DO move, exactly
    add_with = next(x for x in model[first:] if x["op"] == "add")
    add_without = next(y for y in rs0[first:] if y["op"] == "add")
    assert add_with["i"] == add_without["i"] + 1 and add_with["state_sha"] != add_without["state_sha"]
    assert add_with["result"]["prov"]["at"] == add_without["result"]["prov"]["at"] + 1
    assert {k: v for k, v in add_with["result"].items() if k != "prov"} == {k: v for k, v in add_without["result"].items() if k != "prov"}
    assert [x["state_sha"] for x in model[first:]] != [y["state_sha"] for y in rs0[first:]]
    emit_with, emit_without = model[-1]["result"], rs0[-1]["result"]
    assert emit_with["text"] == emit_without["text"] and emit_with["output_sha"] == emit_without["output_sha"]
    assert {k: v for k, v in emit_with.items() if k != "annotated"} == {k: v for k, v in emit_without.items() if k != "annotated"}
    shifted = [(a["prov"], b["prov"]) for a, b in zip(emit_with["annotated"], emit_without["annotated"]) if a != b]
    assert shifted and all(p["at"] == q["at"] + 1 for p, q in shifted)            # only the `at` of the unit added after the note row
    # the note rows do not move the state hash of their own
    for i, x in enumerate(rs):
        if x["actor"] == nt.NOTE_ACTOR:
            assert x["state_sha"] == rs[i - 1]["state_sha"]


def test_a_refused_emit_and_its_refusals_carry_no_notes_and_are_unchanged(tmp_path, monkeypatch):
    def script(base):
        srv = server(base)
        w = ScriptedWeaver(srv, "prose/ca", "m", "n")
        w.begin()
        c1, c2, _ = conflicting_thread(w)
        k = w.call("open_cross", tier="WORD", L=1)["cid"]
        w.call("topic", cid=k, on=True)
        w.call("link", cid=k)                                                  # a topic cross with no centre in the thread -> a refusal
        return w, w.call("emit")
    w, e = script(tmp_path / "a")
    monkeypatch.setattr(Run, "notes_due", lambda self: [])
    w0, e0 = script(tmp_path / "b")
    assert e["ok"] is False and e == e0 and "notes" not in e
    rs = rows(tmp_path / "a" / "runs" / "n")
    assert (rs[-1]["actor"], rs[-1]["op"]) == ("model", "emit") and rs[-1]["result"]["ok"] is False
    assert [x["type"] for x in e["detail"]["refusals"]] == ["empty_centre"]
    assert [x["op"] for x in rs if x["actor"] == "loom"] == []


def test_replay_requires_the_note_row_and_rejects_a_forged_one(tmp_path):
    build_noted_run(tmp_path)
    d = tmp_path / "runs" / "n"
    original = (d / "ops.jsonl").read_bytes().split(b"\n")[:-1]
    rs = [json.loads(x) for x in original]

    def rewrite(new_rows, name):
        out = tmp_path / name
        out.mkdir()
        prev, lines = "0" * 64, []
        for i, r in enumerate(new_rows):
            body = {k: v for k, v in r.items() if k not in ("v", "i", "prev", "sha")}
            row = lg.seal(i, prev, body)
            lines.append(lg.line_of(row))
            prev = row["sha"]
        (out / "ops.jsonl").write_bytes(b"".join(lines))
        (out / "HEAD").write_text(prev + "\n")
        (out / "meta.json").write_bytes((d / "meta.json").read_bytes())
        return out

    ok = rewrite(rs, "ok")
    assert lg.verify(ok, corpus_path=CORPUS)["status"] == "OK"                    # the re-seal is faithful
    # (1) the last note row removed: the emit is the LAST row, so this is the shape of a crash between two appends (L-LOOM-105): tolerated,
    #     exposed as pending_note, and the output is not lost
    v = lg.verify(rewrite(rs[:-1], "no_last_note"), corpus_path=CORPUS)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["replay"]["pending_note"] is True
    assert lg.emitted_output(tmp_path / "no_last_note", corpus_path=CORPUS)["status"] == "emitted"
    assert lg.verify(ok, corpus_path=CORPUS)["replay"]["pending_note"] is False
    # (2) the note row after the read removed
    ri = next(i for i, x in enumerate(rs) if x["op"] == "read")
    forged = [x for i, x in enumerate(rs) if i != ri + 1]
    v = lg.verify(rewrite(forged, "no_read_note"), corpus_path=CORPUS)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["field"] == "note_missing"
    # (3) a note row with other notes
    edited = copy.deepcopy(rs)
    edited[-1]["args"]["notes"] = edited[-1]["args"]["notes"][:1]
    v = lg.verify(rewrite(edited, "edited"), corpus_path=CORPUS)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"] == {"i": len(rs) - 1, "field": "args"}
    # (4) a note row where nothing is due (after a lookup)
    extra = copy.deepcopy(rs)
    extra.insert(2, dict(rs[-1]))
    v = lg.verify(rewrite(extra, "extra"), corpus_path=CORPUS)
    assert v["status"] == "REPLAY_DIFFERS"


# ---- L-LOOM-105: a crash between the read / emit append and the note append must not brick the run ---------------------------------
def truncated_copy(src_runs, dst_base, n_lines, run_id="n"):
    """A copy of the run `run_id` cut after `n_lines` rows (HEAD follows): the file a crash between two appends leaves."""
    src = src_runs / run_id
    dst = dst_base / "runs" / run_id
    dst.mkdir(parents=True)
    lines = (src / "ops.jsonl").read_bytes().split(b"\n")[:-1][:n_lines]
    (dst / "ops.jsonl").write_bytes(b"".join(ln + b"\n" for ln in lines))
    (dst / "HEAD").write_text(json.loads(lines[-1])["sha"] + "\n")
    (dst / "meta.json").write_bytes((src / "meta.json").read_bytes())
    return dst


def test_a_pending_note_after_a_read_or_an_emit_replays_identical_and_is_exposed(tmp_path):
    build_noted_run(tmp_path / "ref")
    ref = tmp_path / "ref" / "runs"
    rs = rows(ref / "n")
    ri = next(i for i, x in enumerate(rs) if x["op"] == "read")
    for name, cut in (("after_read", ri + 1), ("after_emit", len(rs) - 1)):
        d = truncated_copy(ref, tmp_path / name, cut)
        v = lg.verify(d, corpus_path=CORPUS)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["replay"]["pending_note"] is True, name
        assert v["replay"]["rows"] == cut
    # not the last row: the same missing row in the middle stays a difference (the note row after the read removed, later rows kept)
    mid = [x for i, x in enumerate(rs) if i != ri + 1]
    out = tmp_path / "mid"
    out.mkdir()
    prev, buf = "0" * 64, []
    for i, r in enumerate(mid):
        row = lg.seal(i, prev, {k: v for k, v in r.items() if k not in ("v", "i", "prev", "sha")})
        buf.append(lg.line_of(row))
        prev = row["sha"]
    (out / "ops.jsonl").write_bytes(b"".join(buf))
    (out / "HEAD").write_text(prev + "\n")
    (out / "meta.json").write_bytes((ref / "n" / "meta.json").read_bytes())
    v = lg.verify(out, corpus_path=CORPUS)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"] == {"i": ri + 1, "field": "note_missing"} and v["replay"]["pending_note"] is False


def test_a_restarted_server_repairs_the_pending_note_and_the_file_is_the_one_that_never_crashed(tmp_path):
    build_noted_run(tmp_path / "ref")
    ref = tmp_path / "ref" / "runs"
    rs = rows(ref / "n")
    ri = next(i for i, x in enumerate(rs) if x["op"] == "read")
    for name, cut in (("after_read", ri + 1), ("after_emit", len(rs) - 1)):
        base = tmp_path / name
        truncated_copy(ref, base, cut)
        srv = server(base)
        assert srv._entry("n") is not None                                       # the reload IS the repair: nothing else is appended
        got = (base / "runs" / "n" / "ops.jsonl").read_bytes().split(b"\n")
        want = (ref / "n" / "ops.jsonl").read_bytes().split(b"\n")
        assert got[:cut + 1] == want[:cut + 1], name                             # the repaired note row is byte for byte the one that was never lost
        v = lg.verify(base / "runs" / "n", corpus_path=CORPUS)
        assert v["status"] == "OK" and v["replay"]["pending_note"] is False
        assert lg.emitted_output(base / "runs" / "n", corpus_path=CORPUS)["status"] == ("emitted" if cut == len(rs) - 1 else "no_output")


def test_a_repaired_run_continues_exactly_like_one_that_never_crashed(tmp_path):
    """The next model call after a crash (here a `lookup` on the closed run: stored as a refusal row) repairs first, silently."""
    build_noted_run(tmp_path / "ref")
    ref_srv = server(tmp_path / "ref")
    call = {"run_id": "n", "text": "首都", "tier": "WORD"}
    ref_srv.call("lookup", call)
    ref = tmp_path / "ref" / "runs" / "n"
    rs = rows(ref)
    emit_i = next(i for i, x in enumerate(rs) if x["op"] == "emit")
    assert [(x["actor"], x["op"]) for x in rs[emit_i:]] == [("model", "emit"), (nt.NOTE_ACTOR, nt.NOTE_OP), ("model", "lookup")]
    base = tmp_path / "crash"
    truncated_copy(tmp_path / "ref" / "runs", base, emit_i + 1)                          # the emit is stored, its note row is not
    server(base).call("lookup", call)
    for fn in ("ops.jsonl", "HEAD"):
        assert (base / "runs" / "n" / fn).read_bytes() == (ref / fn).read_bytes(), fn


def test_the_cli_door_repairs_the_pending_note_before_it_appends_its_row(tmp_path):
    from verantyx.loom.mcp import append_outside_row
    build_noted_run(tmp_path / "ref")
    ref_srv = server(tmp_path / "ref")
    args = {"sha256": "0" * 64, "chars": 4}
    ref_srv.harness("n", "free_text_dropped", args)
    ref = tmp_path / "ref" / "runs" / "n"
    rs = rows(ref)
    emit_i = next(i for i, x in enumerate(rs) if x["op"] == "emit")
    base = tmp_path / "crash"
    d = truncated_copy(tmp_path / "ref" / "runs", base, emit_i + 1)
    append_outside_row(d, "harness", "free_text_dropped", args)
    for fn in ("ops.jsonl", "HEAD"):
        assert (d / fn).read_bytes() == (ref / fn).read_bytes(), fn
    assert lg.verify(d, corpus_path=CORPUS)["status"] == "OK"


def test_a_failed_note_append_in_a_live_server_is_repaired_by_the_next_call(tmp_path, monkeypatch):
    """The read row is stored, the second append raises (disk full, killed): the in-memory run is dropped, the next call rebuilds from the file
    (replay: pending_note) and repairs it; the ledger ends up byte-identical to a run that never failed."""
    srv = server(tmp_path / "live")
    w = ScriptedWeaver(srv, "prose/ca", "test-weaver", "n")
    w.begin()
    conflicting_thread(w)
    nr = lookup_then_add(w, TOY[7])
    cross(w, centre=nr)
    real = lg._Locked.append
    calls = {"n": 0}

    def flaky(self, body, t_ns=None):
        if body["op"] == nt.NOTE_OP:
            calls["n"] += 1
            raise OSError("disk full")
        return real(self, body, t_ns)
    monkeypatch.setattr(lg._Locked, "append", flaky)
    with pytest.raises(OSError):
        srv.call("read", {"run_id": "n"})
    monkeypatch.setattr(lg._Locked, "append", real)
    d = tmp_path / "live" / "runs" / "n"
    assert calls["n"] == 1 and "n" not in srv.runs
    v = lg.verify(d, corpus_path=CORPUS)
    assert v["status"] == "OK" and v["replay"]["pending_note"] is True               # the file is a valid prefix, not a bricked run
    r = srv.call("read", {"run_id": "n"})                                           # the next call: repair (the old note row), then this read + its note
    assert types(r["notes"]) == [nt.CONFLICT, nt.NO_RECORD]
    e = srv.call("emit", {"run_id": "n"})
    assert e["ok"]
    got = rows(d)
    N = (nt.NOTE_ACTOR, nt.NOTE_OP)
    assert [(x["actor"], x["op"]) for x in got[-6:]] == [("model", "read"), N, ("model", "read"), N, ("model", "emit"), N]
    assert lg.verify(d, corpus_path=CORPUS)["status"] == "OK"
    # byte-identity with a run that never failed: the same calls on a fresh server (the failed read repaired = one read + its note, then the same)
    srv2 = server(tmp_path / "clean")
    w2 = ScriptedWeaver(srv2, "prose/ca", "test-weaver", "n")
    w2.begin()
    conflicting_thread(w2)
    cross(w2, centre=lookup_then_add(w2, TOY[7]))
    srv2.call("read", {"run_id": "n"})
    srv2.call("read", {"run_id": "n"})
    srv2.call("emit", {"run_id": "n"})
    assert (d / "ops.jsonl").read_bytes() == (tmp_path / "clean" / "runs" / "n" / "ops.jsonl").read_bytes()
    assert (d / "HEAD").read_bytes() == (tmp_path / "clean" / "runs" / "n" / "HEAD").read_bytes()


# ---- L-LOOM-106: the note row is versioned ---------------------------------------------------------------------------------------
def reseal(rs, out):
    out.mkdir(parents=True, exist_ok=True)
    prev, buf = "0" * 64, []
    for i, r in enumerate(rs):
        row = lg.seal(i, prev, {k: v for k, v in r.items() if k not in ("v", "i", "prev", "sha")})
        buf.append(lg.line_of(row))
        prev = row["sha"]
    (out / "ops.jsonl").write_bytes(b"".join(buf))
    (out / "HEAD").write_text(prev + "\n")
    return out


def test_a_note_row_of_another_version_is_accepted_as_recorded_and_reported_stale(tmp_path):
    build_noted_run(tmp_path / "ref")
    d = tmp_path / "ref" / "runs" / "n"
    rs = [json.loads(x) for x in (d / "ops.jsonl").read_bytes().split(b"\n")[:-1]]
    note_idx = [i for i, x in enumerate(rs) if x["actor"] == nt.NOTE_ACTOR]
    assert len(note_idx) == 2
    # (1) another version, other content (the definitions changed since the row was written): accepted, reported, the chain and the output stand
    old = copy.deepcopy(rs)
    for i in note_idx:
        old[i]["args"]["nv"] = "notes.v0"
        old[i]["args"]["notes"] = [{"type": "CONFLICT", "kind": "an_older_shape"}]
    out = reseal(old, tmp_path / "v0" / "runs" / "n")
    (out / "meta.json").write_bytes((d / "meta.json").read_bytes())
    v = lg.verify(out, corpus_path=CORPUS)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["replay"]["notes_stale"] == note_idx
    assert lg.emitted_output(out, corpus_path=CORPUS)["status"] == "emitted"
    # a server rebuilds it (a restart) and goes on; the stale rows are kept as they are
    assert server(tmp_path / "v0")._entry("n") is not None
    # (2) no `nv` at all (a row of the uncommitted first shape) is a stale row too
    nov = copy.deepcopy(rs)
    for i in note_idx:
        del nov[i]["args"]["nv"]
    out2 = reseal(nov, tmp_path / "nov")
    (out2 / "meta.json").write_bytes((d / "meta.json").read_bytes())
    assert lg.verify(out2, corpus_path=CORPUS)["replay"]["notes_stale"] == note_idx
    # (3) the SAME version is compared: other content differs
    cur = copy.deepcopy(rs)
    cur[note_idx[0]]["args"]["notes"] = []
    out3 = reseal(cur, tmp_path / "v1")
    (out3 / "meta.json").write_bytes((d / "meta.json").read_bytes())
    v = lg.verify(out3, corpus_path=CORPUS)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["i"] == note_idx[0]
    # (4) a stale row still has to be the right shape: after the right row, of the right op, a list of notes, no other keys
    for mutate in (lambda a: a.update(after=a["after"] - 1), lambda a: a.update(of="emit" if a["of"] == "read" else "read"),
                   lambda a: a.update(notes="x"), lambda a: a.update(extra=1)):
        bad = copy.deepcopy(old)
        mutate(bad[note_idx[0]]["args"])
        out4 = reseal(bad, tmp_path / ("bad%d" % id(mutate)))
        (out4 / "meta.json").write_bytes((d / "meta.json").read_bytes())
        assert lg.verify(out4, corpus_path=CORPUS)["status"] == "REPLAY_DIFFERS"


def test_a_live_call_cannot_write_a_stale_or_forged_note_row(tmp_path):
    """Acceptance of another version exists only inside replay: a live `step` derives the row and ignores the args it is given."""
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "prose/ca", "m", "n")
    w.begin()
    conflicting_thread(w)
    srv.runs["n"].run.step("model", "read", {})
    run = srv.runs["n"].run
    body = run.step(nt.NOTE_ACTOR, nt.NOTE_OP, {"nv": "notes.v0", "after": 0, "of": "emit", "notes": [{"type": "CONFLICT"}]})
    assert body["args"]["nv"] == nt.NOTES_VERSION and body["args"]["of"] == "read" and body["args"]["notes"] and body["args"]["after"] == run.i - 1
    assert not run.replaying


def test_the_output_is_still_the_emit_row_and_only_it(tmp_path):
    build_noted_run(tmp_path)
    out = lg.emitted_output(tmp_path / "runs" / "n", corpus_path=CORPUS)
    rs = rows(tmp_path / "runs" / "n")
    emit = next(x for x in rs if x["op"] == "emit")
    assert out == {"status": "emitted", "text": emit["result"]["text"], "output_sha": emit["result"]["output_sha"]}


def test_a_run_without_notes_has_no_note_row_and_the_pinned_bytes(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ca", "claude-haiku-4-5", "demo_ca")
    weave_tokyo(w)
    assert (tmp_path / "runs/demo_ca/HEAD").read_text().strip() != ""
    assert not [x for x in rows(tmp_path / "runs/demo_ca") if x["actor"] == "loom"]
    assert not any("notes" in x["result"] for x in rows(tmp_path / "runs/demo_ca"))


def test_the_stored_baseline_ledgers_still_verify(tmp_path):
    base = os.path.join(ROOT, "experiments/line3/loom/baseline_scripted/runs")
    if not os.path.isdir(base):
        pytest.skip("no stored baseline")
    names = sorted(os.listdir(base))[:6]
    for n in names:
        assert lg.verify(os.path.join(base, n), corpus_path=CORPUS)["status"] == "OK"


def test_the_scorer_and_the_result_object_accept_a_ledger_that_holds_note_rows(tmp_path):
    """experiments/line3/loom/{score,harness}.py are not edited here; they must still read a run with a `loom` row (op_counts, closing, verify)."""
    H = _load("loom_harness_for_notes", os.path.join(ROOT, "experiments/line3/loom/harness.py"))
    bank, gold = score.load_bank(H.BANK), score.load_gold()
    row_ = H.select_task(bank, "I2-001", "constructed_allowed")
    srv = LoomServer([H.abs_row(row_)], str(tmp_path / "runs"))
    w = ScriptedWeaver(srv, row_["task_id"], "scripted-weaver", "noted")
    w.begin()
    conflicting_thread(w)
    cross(w, centre=lookup_then_add(w, TOY[7]))
    e = w.call("emit")
    assert e["ok"] and types(e["notes"]) == [nt.CONFLICT, nt.NO_RECORD]
    d = str(tmp_path / "runs" / "noted")
    facts = score.run_facts(d)
    assert facts["rows"] == facts["model_rows"] + 1 and facts["closing"]["op"] == "emit" and facts["head"] == rows(d)[-1]["sha"]
    rs = score.score_run(d, bank, gold)
    assert rs.verify_status == "OK" and rs.replay_verified and rs.outcome == "emitted" and rs.output_sha == e["output_sha"]
    obj = H.result_object(rs, "scripted", d)
    assert obj["op_counts"]["rows"] == facts["rows"] and obj["self_corrections"] == nt.self_corrections(rows(d))


def test_a_harness_row_after_the_emit_and_the_note_row_replays(tmp_path):
    """The attest / free-text rows of the harness are appended AFTER the emit; the note row sits between them and the emit."""
    srv, w, r, e = build_noted_run(tmp_path)
    w.say("done")
    d = tmp_path / "runs" / "n"
    rs = rows(d)
    assert [(x["actor"], x["op"]) for x in rs[-3:]] == [("model", "emit"), ("loom", nt.NOTE_OP), ("harness", "free_text_dropped")]
    assert lg.verify(d, corpus_path=CORPUS)["status"] == "OK"


# ================================================================================================================================
# determinism
# ================================================================================================================================
def test_notes_are_deterministic_within_a_process_and_in_their_order(tmp_path):
    outs = []
    for k in range(2):
        srv, w, r, e = build_noted_run(tmp_path / str(k))
        outs.append((json.dumps(r["notes"], sort_keys=True, ensure_ascii=False), (tmp_path / str(k) / "runs" / "n" / "HEAD").read_text()))
    assert outs[0] == outs[1]
    assert [n["type"] for n in json.loads(outs[0][0])] == [nt.CONFLICT, nt.NO_RECORD]


SCRIPT = textwrap.dedent("""
    import sys, json
    sys.path.insert(0, %r)
    from loom_common import server
    from verantyx.loom.scripted import ScriptedWeaver
    import test_loom_notes as T
    import pathlib, tempfile
    d = pathlib.Path(tempfile.mkdtemp())
    srv, w, r, e = T.build_noted_run(d)
    print(json.dumps({"notes": r["notes"], "head": (d / "runs" / "n" / "HEAD").read_text().strip()}, sort_keys=True, ensure_ascii=False))
""" % os.path.join(ROOT, "tests/line3"))


def test_notes_and_the_ledger_head_are_the_same_under_other_hash_seeds(tmp_path):
    seen = set()
    for seed in ("0", "1", "2"):
        p = subprocess.run([PY, "-c", SCRIPT], env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED=seed), cwd=ROOT, capture_output=True, text=True, timeout=300)
        assert p.returncode == 0, p.stderr
        seen.add(p.stdout.strip())
    assert len(seen) == 1


# ================================================================================================================================
# the self-correction metrics (layer 3)
# ================================================================================================================================
def row(i, op, args=None, result=None, actor="model"):
    return {"v": 1, "i": i, "actor": actor, "op": op, "args": args or {}, "result": result if result is not None else {"ok": True}}


def refused(i, op, refusal, args=None):
    return row(i, op, args, {"ok": False, "refusal": refusal, "detail": {}})


EMPTY = {"ok": True, "matches": []}


def test_self_corrections_on_a_scripted_ledger():
    rs = [row(0, "begin"),
          row(1, "lookup", {"text": "A", "tier": "WORD"}, EMPTY),
          row(2, "lookup", {"text": "B", "tier": "WORD"}, {"ok": True, "matches": [1]}),                   # not empty: no plan change from here
          row(3, "lookup", {"text": "C", "tier": "WORD"}, EMPTY),
          row(4, "add", {"text": "C2", "kind": "constructed"}),                                            # after an empty lookup: other text -> a plan change
          refused(5, "seat", "seat_occupied"),
          row(6, "seat"),                                                                                  # a recovery of the refused seat
          refused(7, "add", "constructed_forbidden"),                                                      # never followed by an ok add: no recovery
          row(8, "swap"), row(9, "unseat"),
          row(10, "emit", {}, {"ok": True, "status": "emitted"}),
          row(11, "swap")]                                                                                 # after the close: not counted
    sc = nt.self_corrections(rs)
    assert sc["unseat_swap_before_close"] == [{"i": 8, "op": "swap"}, {"i": 9, "op": "unseat"}]
    assert sc["plan_change_after_empty"] == [{"i": 1, "next_i": 2, "next_op": "lookup"}, {"i": 3, "next_i": 4, "next_op": "add"}]
    assert sc["recovery_after_refusal"] == [{"i": 5, "op": "seat", "refusal": "seat_occupied"}]
    assert sc["refusals_recoverable"] == 2
    assert sc["counts"] == {"unseat_swap_before_close": 2, "plan_change_after_empty": 2, "recovery_after_refusal": 1, "refusals_recoverable": 2}
    assert nt.recovery_rate(sc) == (1, 2)


def test_plan_change_rules_and_the_non_recoverable_refusals():
    rs = [row(0, "lookup", {"text": "A", "tier": "WORD"}, EMPTY),
          row(1, "lookup", {"text": "A", "tier": "WORD"}, EMPTY),                                          # the same lookup again: not a plan change
          row(2, "lookup", {"text": "A", "tier": "CHAR"}, EMPTY),                                          # other tier: a plan change (and 1 -> 2 counts)
          row(3, "read_sentence", {"sid": 3}),                                                             # 2 -> 3: a plan change (reading)
          row(4, "lookup", {"text": "Z", "tier": "WORD"}, EMPTY),
          row(5, "abstain", {"type": "no_record"}, {"ok": True, "status": "abstained", "type": "no_record"}),   # a conclusion
          refused(6, "emit", "run_closed"), refused(7, "add", "ops_cap"), refused(8, "lookup", "lookup_cap")]
    sc = nt.self_corrections(rs)
    assert [x["i"] for x in sc["plan_change_after_empty"]] == [1, 2]
    assert sc["refusals_recoverable"] == 0 and sc["recovery_after_refusal"] == [] and nt.recovery_rate(sc) is None
    assert sc["unseat_swap_before_close"] == []


def test_a_run_that_never_closes_counts_every_unseat_and_swap():
    rs = [row(0, "begin"), row(1, "swap"), row(2, "unseat"), row(3, "emit", {}, {"ok": False, "refusal": "unstable_cross", "detail": {}})]
    sc = nt.self_corrections(rs)
    assert sc["counts"]["unseat_swap_before_close"] == 2 and sc["refusals_recoverable"] == 1 and sc["counts"]["recovery_after_refusal"] == 0


def test_rows_of_the_other_actors_are_ignored_by_the_metrics():
    rs = [row(0, "begin"), row(1, "loom_note", actor="loom", args={"notes": []}), row(2, "swap"), row(3, "grade", actor="human"), row(4, "swap", actor="harness")]
    assert nt.self_corrections(rs)["counts"]["unseat_swap_before_close"] == 1


def test_the_canonical_computation_equals_the_scorers_on_real_ledgers(tmp_path):
    """notes.self_corrections is the canonical form of score.self_corrections (L-LOOM-56): equal on every ledger the tests can make."""
    ledgers = []
    srv, w, r, e = build_noted_run(tmp_path / "a")
    ledgers.append(rows(tmp_path / "a" / "runs" / "n"))
    srv = server(tmp_path / "b")
    w = ScriptedWeaver(srv, "prose/ro", "m", "b")
    w.begin()
    w.call("lookup", text=TOY[0], tier="WORD")
    w.call("add", text=TOY[0], kind="constructed")                                 # refused in record_only
    a = w.call("add", text="首都", kind="record", tier="WORD")["uid"]
    w.call("add", text=TOY[0], kind="record", tier="WORD")
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    w.call("seat", cid=c, seat="centre", uid=a)
    w.call("seat", cid=c, seat="centre", uid=a)                                    # refused
    w.call("unseat", cid=c, seat="centre")
    w.call("seat", cid=c, seat="centre", uid=a)
    w.call("link", cid=c)
    w.call("emit")
    ledgers.append(rows(tmp_path / "b" / "runs" / "b"))
    srv2, w2 = code_w(tmp_path / "c", "K3")
    sc.weave_k(w2, "K3")
    ledgers.append(rows(tmp_path / "c" / "runs" / "cw"))
    srv3, w3 = code_w(tmp_path / "d", "K4")
    sc.weave_k(w3, "K4")
    ledgers.append(rows(tmp_path / "d" / "runs" / "cw"))
    for rs in ledgers:
        assert nt.self_corrections(rs) == score.self_corrections(rs)
    # and they are not all trivially empty
    assert any(nt.self_corrections(rs)["counts"]["recovery_after_refusal"] for rs in ledgers)
    assert any(nt.self_corrections(rs)["counts"]["unseat_swap_before_close"] for rs in ledgers)


def test_note_summary_shows_a_note_resolved_by_a_state_change(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "prose/ca", "m", "s")
    w.begin()
    c1, c2, (a1, a2, b, c) = conflicting_thread(w)
    assert types(w.call("read")["notes"]) == [nt.CONFLICT]                          # shown
    w.call("unseat", cid=c2, seat="+x:0")                                           # the model fixes it
    r2 = w.call("read")
    assert "notes" not in r2
    e = w.call("emit")
    assert e["ok"]
    summary = nt.note_summary(rows(tmp_path / "runs" / "s"))
    assert summary["by_type"] == {nt.CONFLICT: 1, nt.UNANCHORED: 0, nt.NO_RECORD: 0, nt.QUESTION_ECHO: 0}
    assert summary["observations"] == 3 and summary["shown"] == 1
    assert summary["resolved"] == [{"i": 13, "next_i": 16, "type": nt.CONFLICT}]
    assert summary["at_close"] == []


def test_note_summary_an_emit_with_notes_is_visible_at_close(tmp_path):
    srv, w, r, e = build_noted_run(tmp_path)
    s = nt.note_summary(rows(tmp_path / "runs" / "n"))
    assert s["at_close"] == [nt.CONFLICT, nt.NO_RECORD] and s["resolved"] == [] and s["shown"] == 2


# ================================================================================================================================
# the module is a pure pass
# ================================================================================================================================
def test_compute_changes_nothing(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "prose/ca", "m", "p")
    w.begin()
    conflicting_thread(w)
    run = srv.runs["p"].run
    before = (run.state.sha(), run.i, run.head, list(run.lookup_log))
    n1 = nt.compute(run)
    n2 = nt.compute(run)
    assert n1 == n2 and n1 and (run.state.sha(), run.i, run.head, list(run.lookup_log)) == before
    assert rows(tmp_path / "runs" / "p")[-1]["op"] == "link"


def test_the_module_imports_no_process_network_or_clock():
    import ast as _ast
    src = open(nt.__file__, encoding="utf-8").read()
    mods = {n.names[0].name.split(".")[0] if isinstance(n, _ast.Import) else (n.module or "").split(".")[0] for n in _ast.walk(_ast.parse(src))
            if isinstance(n, (_ast.Import, _ast.ImportFrom))}
    assert not mods & {"subprocess", "socket", "http", "urllib", "requests", "time", "datetime", "random", "os", "threading"}


# ================================================================================================================================
# review fixes: identity by location (L-LOOM-108), the role of a code NO_RECORD (L-LOOM-109), the OP-LOOM-5 floor (L-LOOM-111)
# ================================================================================================================================
def test_note_summary_a_conflict_that_grows_is_the_same_note_not_a_resolved_one(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "prose/ca", "m", "g")
    w.begin()
    c1, c2, (a1, a2, b, c) = conflicting_thread(w)
    r1 = w.call("read")
    assert [len(v["cids"]) for v in r1["notes"][0]["variants"]] == [1, 1]                       # two variants
    a3, d = add(w, TOY[0]), add(w, TOY[3])
    cross(w, centre=a3, arms={"+x": [d]})                                                       # a third variant of the same (tier, centre, arm)
    r2 = w.call("read")
    assert len(r2["notes"][0]["variants"]) == 3 and r2["notes"][0] != r1["notes"][0]            # the payload changed ...
    s = nt.note_summary(rows(tmp_path / "runs" / "g"))
    assert nt.note_key(r1["notes"][0]) == nt.note_key(r2["notes"][0])                           # ... the location did not
    assert s["resolved"] == [] and s["shown"] == 1 and s["by_type"][nt.CONFLICT] == 1
    w.call("unseat", cid=c2, seat="+x:0")                                                       # now only one of the three goes: it is still there
    w.call("read")
    assert nt.note_summary(rows(tmp_path / "runs" / "g"))["resolved"] == []
    w.call("unseat", cid=c1, seat="+x:0")                                                       # two of three: one variant left = resolved
    assert "notes" not in w.call("read")
    s = nt.note_summary(rows(tmp_path / "runs" / "g"))
    assert [x["type"] for x in s["resolved"]] == [nt.CONFLICT] and s["shown"] == 1


def test_note_key_is_the_location_for_each_type():
    assert nt.note_key({"type": "CONFLICT", "kind": "arm_contents", "tier": "WORD", "centre": "首都", "arm": "+x", "variants": [1]}) == \
        nt.note_key({"type": "CONFLICT", "kind": "arm_contents", "tier": "WORD", "centre": "首都", "arm": "+x", "variants": [1, 2, 3]})
    assert nt.note_key({"type": "CONFLICT", "kind": "name_bound_twice", "scope": "<module>", "name": "f", "bindings": []}) == \
        nt.note_key({"type": "CONFLICT", "kind": "name_bound_twice", "scope": "<module>", "name": "f", "bindings": [1, 2, 3]})
    a = {"type": "UNANCHORED", "cid": "c1", "seat": "-z:0", "uid": "u1", "have": 0}
    assert nt.note_key(a) == nt.note_key(dict(a, have=1, evidence=[])) and nt.note_key(a) != nt.note_key(dict(a, seat="-z:1"))
    assert nt.note_key(dict(a, type="NO_RECORD")) != nt.note_key(a)


def test_a_code_conflict_that_grows_is_the_same_note(tmp_path):
    srv, w = code_w(tmp_path)
    weave_lines(w, "def double(x):", "    return mul(x, 2)", "def double(y):", "    return mul(y, 3)")
    r1 = w.call("read")
    n1 = next(n for n in r1["notes"] if n["type"] == nt.CONFLICT)
    weave_lines(w, "def double(z):", "    return mul(z, 4)")
    n2 = next(n for n in w.call("read")["notes"] if n["type"] == nt.CONFLICT)
    assert len(n2["bindings"]) == 3 and n1 != n2 and nt.note_key(n1) == nt.note_key(n2)
    assert nt.note_summary(rows(tmp_path / "runs" / "cw"))["resolved"] == []


def code_notes(w):
    return {(n["unit"], n["role"]) for n in w.call("read").get("notes", []) if n["type"] == nt.NO_RECORD}


def test_code_no_record_carries_the_role_of_the_unit(tmp_path):
    srv, w = code_w(tmp_path, "K1")
    sc.weave_k(w, "K1")
    last = [r for r in rows(tmp_path / "runs" / "cw") if r["actor"] == nt.NOTE_ACTOR][-1]["args"]["notes"]
    assert {(n["unit"], n["role"]) for n in last} == {("double", nt.ROLE_DEFINITION), ("2", nt.ROLE_LITERAL)}
    srv, w = code_w(tmp_path / "k4", "K4")
    sc.weave_k(w, "K4")
    last = [r for r in rows(tmp_path / "k4" / "runs" / "cw") if r["actor"] == nt.NOTE_ACTOR][-1]["args"]["notes"]
    assert sorted((n["unit"], n["role"]) for n in last) == [("cube", nt.ROLE_DEFINITION), ("square", nt.ROLE_DEFINITION), ("square", nt.ROLE_USE)]
    assert all(set(n) == {"type", "cid", "seat", "uid", "unit", "lookup_i", "added_at", "role"} for n in last)


def test_code_no_record_roles_fallback_parameters_and_an_unparsable_thread(tmp_path):
    srv, w = code_w(tmp_path / "a", "K1")
    weave_lines(w, "def double(x):", "    return frobnicate(x, 2)")                        # a function nobody defines: the model's own invention
    assert code_notes(w) == {("double", nt.ROLE_DEFINITION), ("2", nt.ROLE_LITERAL), ("frobnicate", nt.ROLE_FALLBACK)}
    srv, w = code_w(tmp_path / "b", "K1")
    weave_lines(w, "def double(qq):", "    return mul(qq, 2)")                            # a parameter binds, its use is a use of a name the thread binds
    assert ("qq", nt.ROLE_DEFINITION) in code_notes(w) and ("qq", nt.ROLE_USE) in code_notes(w)
    srv, w = code_w(tmp_path / "c", "K1")
    weave_lines(w, "def double(x):", "    return frobnicate(double(x), 2")                # does not parse: the token rules alone (def / class / as; names defined)
    assert code_notes(w) == {("double", nt.ROLE_DEFINITION), ("double", nt.ROLE_USE), ("2", nt.ROLE_LITERAL), ("frobnicate", nt.ROLE_FALLBACK)}
    srv, w = code_w(tmp_path / "d", "K1")
    weave_lines(w, "def double(x):", "    return mul(x, 2)")
    assert not any("role" in n for n in w.call("read")["notes"] if n["type"] != nt.NO_RECORD)


def test_prose_no_record_has_no_role_and_counts_as_ungrounded(tmp_path):
    srv, w, r, e = build_noted_run(tmp_path)
    no_rec = [n for n in e["notes"] if n["type"] == nt.NO_RECORD]
    assert no_rec and all("role" not in n for n in no_rec)
    assert nt.note_summary(rows(tmp_path / "runs" / "n"))["ungrounded"] == 1


def test_note_summary_counts_only_fallback_as_ungrounded(tmp_path):
    srv, w = code_w(tmp_path / "ref", "K1")
    sc.weave_k(w, "K1")
    s = nt.note_summary(rows(tmp_path / "ref" / "runs" / "cw"))
    assert s["by_type"][nt.NO_RECORD] == 2 and s["ungrounded"] == 0                              # double and 2: shown, not ungrounded
    srv, w = code_w(tmp_path / "fb", "K1")
    weave_lines(w, "def double(x):", "    return frobnicate(x, 2)")
    w.call("read")
    s = nt.note_summary(rows(tmp_path / "fb" / "runs" / "cw"))
    assert s["by_type"][nt.NO_RECORD] == 3 and s["ungrounded"] == 1
    assert nt.is_ungrounded({"type": nt.NO_RECORD, "role": nt.ROLE_FALLBACK}) and not nt.is_ungrounded({"type": nt.NO_RECORD, "role": nt.ROLE_USE})
    assert not nt.is_ungrounded({"type": nt.CONFLICT})


def test_the_tool_descriptions_of_read_and_emit_are_short_and_neutral():
    from verantyx.loom import mcp as m
    src = open(m.__file__, encoding="utf-8").read()
    for name in ("read", "emit"):
        doc = src.split("    def %s(run_id: str) -> str:" % name)[1].split('"""')[1]
        assert "notes" in doc and "never block" in doc and len(doc) < 330
        assert not any(w in doc.lower() for w in ("contradiction", "ungrounded", "wrong", "error"))


def adh_word(corpus):
    return corpus.adhesion["WORD"]


def test_the_floor_one_sentence_of_contrary_evidence_is_silent_two_fire(tmp_path, corpus):
    adh = adh_word(corpus)
    plain = lambda u: len(u) >= 2 and not any(ch.isascii() for ch in u)
    two = sorted(u for u in adh.units() if plain(u) and sum(1 for p in nt.ARM_PARTICLES if adh.adj(u, p) > 0) == 1 and max(adh.adj(u, p) for p in nt.ARM_PARTICLES) == 2)
    one = sorted(u for u in adh.units() if plain(u) and sum(1 for p in nt.ARM_PARTICLES if adh.adj(u, p) > 0) == 1 and max(adh.adj(u, p) for p in nt.ARM_PARTICLES) == 1)
    assert two and one
    u2 = two[0]
    p2 = next(p for p in nt.ARM_PARTICLES if adh.adj(u2, p) > 0)
    other = next(ax for ax in ("+x", "-x", "+y", "-y", "+z", "-z") if nt.SPEC.arm_of_axis(ax) != p2)
    w = weaver(server(tmp_path / "two"))
    cross(w, centre=add(w, "首都", "record", "WORD"), arms={other: [add(w, u2, "record", "WORD")]})
    notes = w.call("read")["notes"]
    assert types(notes) == [nt.UNANCHORED] and notes[0]["evidence"] == [{"particle": p2, "n": 2}] and notes[0]["have"] == 0
    u1 = one[0]
    p1 = next(p for p in nt.ARM_PARTICLES if adh.adj(u1, p) > 0)
    other1 = next(ax for ax in ("+x", "-x", "+y", "-y", "+z", "-z") if nt.SPEC.arm_of_axis(ax) != p1)
    w = weaver(server(tmp_path / "one"))
    cross(w, centre=add(w, "首都", "record", "WORD"), arms={other1: [add(w, u1, "record", "WORD")]})
    assert "notes" not in w.call("read")


def test_the_floor_the_design_example_tokyo_no_longer_flags_and_a_one_character_suffix_is_no_anchor(tmp_path, corpus):
    adh = adh_word(corpus)
    assert (adh.adj("東京", "で"), adh.adj("東京", "の")) == (1, 0)
    w = weaver(server(tmp_path))
    cross(w, centre=add(w, "首都", "record", "WORD"), arms={"+x": [add(w, "東京", "record", "WORD")]})
    assert "notes" not in w.call("read")                                                       # 東京 on の: one sentence of で is below the floor
    from verantyx.loom.state import Unit
    assert nt.anchor_of(adh, Unit("u", "Ω線", "constructed", None, {"by": "m", "at": 1})) is None                      # 線 has evidence, but is 1 char
    assert nt.anchor_of(adh, Unit("u", "Ω現在", "constructed", None, {"by": "m", "at": 1}))[:2] == ("現在", "suffix")
    assert (nt.MIN_CONTRA_SENTENCES, nt.MIN_SUFFIX_CHARS) == (2, 2)


def test_the_floor_on_the_whole_fulllead_word_tier(corpus):
    """The count the owner decision refers to (OP-LOOM-5): of the 1296 WORD units, those with some arm particle in >= 2 distinct sentences."""
    adh = adh_word(corpus)
    us = list(adh.units())
    P = nt.ARM_PARTICLES
    assert len(us) == 1296
    flaggable_before = [u for u in us if any(adh.adj(u, q) > 0 for q in P) and any(adh.adj(u, p) == 0 for p in P)]
    after = [u for u in us if any(adh.adj(u, q) >= 2 for q in P)]
    can_fire = [u for u in after if any(adh.adj(u, p) == 0 for p in P)]
    pairs = sum(1 for u in us for p in P if adh.adj(u, p) == 0 and any(adh.adj(u, q) >= 2 for q in P if q != p))
    assert (len(flaggable_before), len(after), len(can_fire), pairs) == (1113, 152, 150, 599)


def test_known_code_idioms_that_look_like_a_conflict_are_documented_open_points():
    """L-LOOM-112 (open): the binding rule cannot tell these from a contradiction (it does not read control flow).  Pinned so that a later
    refinement has to change this test on purpose."""
    import ast as _ast
    for src, how in (("try:\n    import json\nexcept ImportError:\n    json = None\n", ["import", "assign"]),
                     ("if A:\n    def f(x):\n        return 1\nelse:\n    def f(x):\n        return 2\n", ["def", "def"])):
        b = nt._Bindings()
        b.stmts(_ast.parse(src).body, "<module>")
        multi = [[x["how"] for x in v] for v in b.by_key.values() if len(v) > 1]
        assert multi == [how] and len({repr(x["sig"]) for v in b.by_key.values() if len(v) > 1 for x in v}) == 2


def test_prose_enumeration_is_indistinguishable_from_a_conflict_open_point(tmp_path):
    """L-LOOM-112 (open): 首都 <- 日本 on の against 首都 <- フランス on の, which is an enumeration in a sentence, is a CONFLICT by the rule."""
    w = weaver(server(tmp_path))
    cs = [add(w, t, "record", "WORD") for t in ("首都", "日本", "首都", "フランス")]
    cross(w, centre=cs[0], arms={"+x": [cs[1]]})
    cross(w, centre=cs[2], arms={"+x": [cs[3]]})
    assert nt.CONFLICT in types(w.call("read")["notes"])

"""T7 tests (L-210..): the tiers are combined by I-16 / I-25 / I-14 (each tier on its own, the most stable result is
taken, a tie between tiers is a list, nothing is summed across tiers); the output has an `answer` and a `thought`
(N-08, N-10); the `line3` command; byte identity across PYTHONHASHSEED; legacy / round5 outputs unchanged."""
import json
import os
import subprocess
import sys
from fractions import Fraction as Fr
from types import SimpleNamespace

import pytest

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import readout as ro
from test_readout import HUB, ROOT, ctx_for, tier

T7 = os.path.join(ROOT, "experiments/line3/t7")

DATA = ["東京は日本の首都である。", "大阪は日本の西の都市である。", "京都は日本の古い都市である。",
        "東京は大きな都市である。", "富士山は日本一高い山である。", "富士山は静岡と山梨にまたがる。",
        "大阪は食べ物で有名である。", "京都は寺で有名である。", "東京タワーは東京にある。",
        "琵琶湖は滋賀にある湖である。", "滋賀は京都の隣である。", "静岡は富士山の南にある。"]
QUESTION = "東京は何の都市ですか"


@pytest.fixture(scope="module")
def data_file(tmp_path_factory):
    p = tmp_path_factory.mktemp("t7") / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    return str(p)


@pytest.fixture(scope="module")
def index(data_file):
    return A.Index.from_jsonl(data_file)


# ---- combination on finished outcomes (no search) ---------------------------------------------------------------
def S(name, legs, stab):
    return ro.StateRef("T", name, 0, ("c",) + tuple(legs), stab, "c", 0)


def readout_of(states):
    t = tier(HUB)
    return ro.read_out(cy.TierFacts(t), ctx_for(), states, question="q", window=0)


def outcome(tier_name, states):
    ans = readout_of(states) if states else None
    res = SimpleNamespace(candidates=tuple(states), verdict=ro.UNKNOWN_NO_PATH if states else cy.UNKNOWN_NO_EVIDENCE,
                         thought_obj=lambda: {"stub": True})
    return A.TierOutcome(tier_name, res, ans)


SPACE = SimpleNamespace(sentences=[("sentence %d" % i, "src") for i in range(len(HUB))])
ONE = [S("X", ["a0", "a1", None, None, None, None], Fr(1, 2))]
ONE_HIGH = [S("X", ["a0", "a1", None, None, None, None], Fr(3, 4))]
TWO = [S("X", ["a0", "a1", None, None, None, None], Fr(1, 2)), S("W", ["a0", "a2", None, None, None, None], Fr(1, 2))]


TWO_HIGH = [S("X", ["a0", "a1", None, None, None, None], Fr(3, 4)), S("W", ["a0", "a2", None, None, None, None], Fr(3, 4))]


def test_parse_tiers_fixed_order_no_repeats_and_errors():
    assert A.parse_tiers("CHAR,run,RUN") == ("RUN", "CHAR")
    assert A.parse_tiers(None) == ("RUN", "WORD", "CHAR")
    with pytest.raises(ValueError):
        A.parse_tiers("RUN,SENT")
    with pytest.raises(ValueError):
        A.parse_tiers("")


def test_the_most_stable_tier_is_taken_alone_and_other_tiers_are_not_in_the_answer():
    c = A.combine("q", [outcome("CHAR", ONE), outcome("RUN", ONE_HIGH), outcome("WORD", TWO)], SPACE)
    assert [o.tier for o in c.outcomes] == ["RUN", "WORD", "CHAR"]                      # fixed order, whatever came in
    assert c.shown == ("RUN",) and not c.tie_between_tiers and c.verdict == cy.ANSWER
    assert [t for t, _ in c.entries] == ["RUN"]
    assert c.answer_obj()["answer"]["tier"] == "RUN"
    assert len(c.all_entries) == 1 + 2 + 1                                              # the pool keeps every tier's entries


def test_a_single_winning_tier_keeps_its_own_list():
    c = A.combine("q", [outcome("RUN", TWO_HIGH), outcome("WORD", ONE)], SPACE)
    assert c.shown == ("RUN",) and c.verdict == cy.CHOICE and len(c.entries) == 2 and not c.tie_between_tiers


def test_a_tie_between_tiers_is_a_list_even_when_each_tier_has_one_entry_and_nothing_is_merged():
    c = A.combine("q", [outcome("RUN", ONE), outcome("WORD", ONE), outcome("CHAR", ONE)], SPACE)
    assert c.tie_between_tiers and c.shown == ("RUN", "WORD", "CHAR") and c.verdict == cy.CHOICE
    assert [t for t, _ in c.entries] == ["RUN", "WORD", "CHAR"]                          # same word set, still 3 entries
    o = c.answer_obj()
    assert o["listed"] == 3 and o["answer"] is None and [e["tier"] for e in o["entries"]] == ["RUN", "WORD", "CHAR"]


def test_votes_are_never_summed_across_tiers():
    # three tiers return the same words, but only RUN has the highest stability: agreement of the other two
    # does not outweigh it, and the agreement is a report, not an input
    c = A.combine("q", [outcome("RUN", ONE_HIGH), outcome("WORD", ONE), outcome("CHAR", ONE)], SPACE)
    assert c.shown == ("RUN",) and c.verdict == cy.ANSWER
    ag = c.agreement()
    assert ag["used_for_selection"] is False and len(ag["pairs"]) == 3
    assert all(p["shared_words"] for p in ag["pairs"])
    # and the same selection when the other tiers' states are absent: only the stability ranks
    c2 = A.combine("q", [outcome("RUN", ONE_HIGH), outcome("WORD", []), outcome("CHAR", [])], SPACE)
    assert c2.shown == c.shown and c2.entries[0][1].words == c.entries[0][1].words
    assert c2.agreement()["pairs"] == []


def test_exact_fractions_decide_the_ranking():
    a = [S("X", ["a0", "a1", None, None, None, None], Fr(1, 3))]
    b = [S("X", ["a0", "a1", None, None, None, None], Fr(2, 6))]
    c = A.combine("q", [outcome("RUN", a), outcome("WORD", b)], SPACE)
    assert c.tie_between_tiers and isinstance(c.entries[0][1].stability, Fr)
    d = [S("X", ["a0", "a1", None, None, None, None], Fr(333333, 1000000))]
    assert A.combine("q", [outcome("RUN", a), outcome("WORD", d)], SPACE).shown == ("RUN",)


def test_no_state_and_no_path_are_typed_unknown_with_an_empty_answer():
    c = A.combine("q", [outcome("RUN", []), outcome("WORD", [])], SPACE)
    assert c.verdict == A.UNKNOWN_NO_STATE and c.entries == () and c.answer_obj()["entries"] == []
    nopath = outcome("RUN", [S("N", [None] * 6, Fr(1, 2))])                            # a state, but no section path
    assert nopath.entries == () and nopath.stability is None
    assert A.combine("q", [nopath, outcome("WORD", [])], SPACE).verdict == A.UNKNOWN_NO_PATH


def test_answer_and_thought_are_separate_keys_and_the_answer_cites_sentences():
    c = A.combine("q", [outcome("RUN", ONE)], SPACE)
    o = c.to_json_obj()
    assert set(o) == {"answer", "thought"}
    assert "thought" not in o["answer"] and "cycle" not in json.dumps(o["answer"])
    assert o["answer"]["sources"] and all(set(s) == {"sid", "text", "source"} for s in o["answer"]["sources"])
    assert {s["sid"] for s in o["answer"]["sources"]} == set(o["answer"]["entries"][0]["source_sids"])
    assert set(o["thought"]) >= {"ranking", "agreement", "tiers", "shown_tiers", "tie_between_tiers"}
    assert o["thought"]["ranking"] == [{"tier": "RUN", "stability": "1/2"}]


# ---- the real search on a toy space -------------------------------------------------------------------------------
def test_ask_runs_all_tiers_and_never_stops_at_the_first(index):
    c = A.ask(index, QUESTION)
    assert [o.tier for o in c.outcomes] == ["RUN", "WORD", "CHAR"]                      # I-25
    sub = A.ask(index, QUESTION, tiers="CHAR,RUN")
    assert [o.tier for o in sub.outcomes] == ["RUN", "CHAR"]
    # a tier on its own gives the same result whether or not the others were run (tiers do not interact)
    assert sub.outcome("RUN").result.to_bytes() == c.outcome("RUN").result.to_bytes()
    assert sub.outcome("CHAR").result.to_bytes() == c.outcome("CHAR").result.to_bytes()
    with pytest.raises(ValueError):
        A.ask(A.Index(index.space, tiers=("RUN",)), QUESTION, tiers="WORD")


def test_the_shown_entries_come_from_tiers_with_the_best_stability_only(index):
    c = A.ask(index, QUESTION)
    stabs = {o.tier: o.stability for o in c.outcomes if o.stability is not None}
    if stabs:
        best = max(stabs.values())
        assert set(c.shown) == {t for t, s in stabs.items() if s == best}
        assert (len(c.shown) > 1) == c.tie_between_tiers
    else:
        assert c.verdict in (A.UNKNOWN_NO_STATE, A.UNKNOWN_NO_PATH)


def test_exact_arithmetic_no_floats_in_the_output(index):
    def walk(x):
        if isinstance(x, float):
            raise AssertionError("float in the output")
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        if isinstance(x, list):
            for v in x:
                walk(v)
    walk(A.ask(index, QUESTION).to_json_obj())


# ---- the command ------------------------------------------------------------------------------------------------------
def cli(args, seed="0", cwd=None):
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    for k in [k for k in env if k.startswith("VERA_")]:
        del env[k]
    r = subprocess.run([sys.executable, "-m", "verantyx.cli", "line3"] + args, capture_output=True, text=True, env=env,
                       cwd=cwd or ROOT, timeout=900)
    return r


def test_cli_ask_json_is_byte_identical_across_hash_seeds_and_shows_thought_only_on_request(data_file):
    base = ["ask", "--data", data_file, "--question", QUESTION, "--format", "json"]
    outs = [cli(base + ["--show-thought"], s) for s in ("0", "1", "12345")]
    for r in outs:
        assert r.returncode == 0, r.stderr
    assert outs[0].stdout == outs[1].stdout == outs[2].stdout
    full = json.loads(outs[0].stdout)
    assert set(full) == {"answer", "thought"} and full["thought"]["tiers_run"] == ["RUN", "WORD", "CHAR"]
    short = cli(base)
    assert set(json.loads(short.stdout)) == {"answer"} and json.loads(short.stdout)["answer"] == full["answer"]
    txt = cli(["ask", "--data", data_file, "--question", QUESTION])
    txt_t = cli(["ask", "--data", data_file, "--question", QUESTION, "--show-thought"])
    assert "思考過程" not in txt.stdout and "思考過程" in txt_t.stdout and txt_t.stdout.startswith(txt.stdout)


def test_cli_build_then_ask_with_the_cache_equals_ask_without_it(data_file, tmp_path):
    cache = str(tmp_path / "cache")
    b = cli(["build", "--data", data_file, "--cache", cache, "--tiers", "RUN,CHAR", "--workers", "2"])
    assert b.returncode == 0, b.stderr
    rep = json.loads(b.stdout)
    assert set(rep) == {"RUN", "CHAR"} and all(v["units"] > 0 for v in rep.values())
    assert sorted(os.listdir(cache)) == sorted("placements_%s_%s_mid.pkl" % (A.file_sha256(data_file)[:12], t) for t in ("CHAR", "RUN"))
    q = ["ask", "--data", data_file, "--question", QUESTION, "--format", "json", "--show-thought", "--tiers", "RUN,CHAR"]
    assert cli(q + ["--cache", cache]).stdout == cli(q).stdout


def test_a_cache_for_other_data_is_refused(data_file, tmp_path):
    cache = str(tmp_path / "c2")
    assert cli(["build", "--data", data_file, "--cache", cache, "--tiers", "RUN"]).returncode == 0
    other = tmp_path / "other.jsonl"
    other.write_text(open(data_file, encoding="utf-8").read() + json.dumps({"sent": "新しい文である。"}, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    idx = A.Index.from_jsonl(str(other), None, "mid", ("RUN",))
    p = A.cache_path(cache, A.file_sha256(data_file), "RUN", "mid")
    with pytest.raises(ValueError):
        A.load_placements(p, idx.space.tiers["RUN"], "RUN", "mid", idx.data_sha)
    with pytest.raises(ValueError):
        A.load_placements(p, idx.space.tiers["RUN"], "RUN", "high", A.file_sha256(data_file))


def test_cli_errors_are_exit_2(data_file):
    assert cli(["ask", "--data", data_file]).returncode == 2
    assert cli(["build", "--data", data_file]).returncode == 2
    assert cli(["ask", "--data", data_file + ".missing", "--question", "x"]).returncode == 2
    assert cli(["ask", "--data", data_file, "--question", "x", "--tiers", "SENT"]).returncode == 2


# ---- the existing commands are untouched -----------------------------------------------------------------------------
def test_legacy_and_round5_cli_outputs_are_byte_identical_to_those_recorded_before_the_change():
    base = os.path.join(T7, "cli_baseline.json")
    assert len(json.load(open(base, encoding="utf-8"))) == 20
    r = subprocess.run([sys.executable, os.path.join(T7, "record_cli.py"), "check"], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT), timeout=900)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "20 / 20 identical" in r.stdout

"""W2-h2 regression tests through the REAL reader (no hand-made reading output).

The sentences are the review's probes (round 1, written by the middle role; the files are kept in the review directory under
mid_tasks_r1/probe/).  Each one was a way to route a job wrongly although every unit was read (the gate of J1 did not stop it).  Now each
one must stop with a typed status, and must not name anybody.  The tests count the units by status, so a pass is not an accident of the
reader's coverage: if the reader stopped reading a sentence, the status would be UNREAD and the status assertions would fail."""
import json
import os
import subprocess
import sys

import pytest

from verantyx import routing_from_text as rt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = {"role": "review", "kind": "review", "size": "medium"}
IMPLEMENT = {"role": "implement", "kind": "feature", "size": "medium"}
TEST = {"role": "implement", "kind": "test_authoring", "size": "medium"}


def run(text, job):
    return rt.route_task(rt.explain(text, "probe.md"), dict(job))


def statuses(text):
    return [(u.status, u.reasons) for u in rt.explain(text, "probe.md").extraction.units]


# M1: "X is Y" between two names is another name or a predicate; it is never merged into one agent
M1_TEXT = "ハルが実装をやる。\nセキがレビューをやる。\nハルは東社だ。\nセキは東社だ。\n"


def test_M1_two_agents_that_are_each_east_co_are_not_merged_and_nobody_is_routed():
    assert [s for s, _ in statuses(M1_TEXT)] == ["MAPPED", "MAPPED", "AMBIGUOUS_RELATION", "AMBIGUOUS_RELATION"]
    for job in (REVIEW, IMPLEMENT):
        got = run(M1_TEXT, job)
        assert got["decision"] == "undecided" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["abstention"]["by_status"]["AMBIGUOUS_RELATION"] == 2
        assert got["records"]["aliases"] == [] and [a["id"] for a in got["records"]["agents"]] == ["ハル", "セキ"]
        assert sorted(item["data"]["reading"] for item in got["relations"] if item["held"]) == [
            "COPULA_IS_ANOTHER_NAME", "COPULA_IS_ANOTHER_NAME",
            "COPULA_IS_A_PREDICATE_OF_THE_FIRST", "COPULA_IS_A_PREDICATE_OF_THE_FIRST"]


def test_M1_a_single_copula_line_leaves_the_alias_table_empty():
    assert statuses("ハルは東社だ。\n") == [("AMBIGUOUS_RELATION", ["COPULA_ALIAS_OR_PREDICATION"])]
    got = run("ハルは東社だ。\n", IMPLEMENT)
    assert got["records"]["aliases"] == [] and got["records"]["agents"] == []
    assert got["abstention"]["by_status"]["AMBIGUOUS_RELATION"] == 1


def test_M1_the_entry_says_the_same(tmp_path):
    path = tmp_path / "m1.md"
    path.write_text(M1_TEXT, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-m", "verantyx.cli", "route", "--explanation", str(path), "--task", json.dumps(REVIEW)],
                          capture_output=True, text=True, env=env, cwd=ROOT)
    out = json.loads(proc.stdout)
    assert proc.returncode == 0 and (out["decision"], out["agent"], out["undecided_reason"]) == ("undecided", None, "ABSTAINED")
    assert out["abstention"]["by_status"]["AMBIGUOUS_RELATION"] == 2 and out["records"]["aliases"] == []


# M2: the reader can put an adverb into the filler of the agent ("Rook usually"); a name is one word
@pytest.mark.parametrize("adverb,first_status", [("usually", "NAME_UNRESOLVED"), ("always", "NAME_UNRESOLVED"),
                                                  ("sometimes", "NAME_UNRESOLVED"), ("often", "NAME_UNRESOLVED"),
                                                  ("rarely", "UNREAD")])
def test_M2_an_adverb_in_the_agent_filler_is_not_a_second_agent(adverb, first_status):
    text = f"Rook {adverb} reviews the code.\nRook writes tests.\n"
    units = statuses(text)
    assert [s for s, _ in units] == [first_status, "MAPPED"]
    if first_status == "NAME_UNRESOLVED":
        assert units[0][1] == [f"MULTI_WORD_NAME:Rook {adverb}"]
    for job in (REVIEW, TEST, IMPLEMENT):
        got = run(text, job)
        assert got["decision"] == "undecided" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["abstention"]["by_status"][first_status] == 1
        assert f"Rook {adverb}" not in [a["id"] for a in got["records"]["agents"]]


# M3: a past event reports what happened; it does not declare who does the job
@pytest.mark.parametrize("text,job", [("ハルが実装をやった。\n", IMPLEMENT), ("Rook reviewed the code.\n", REVIEW)])
def test_M3_a_past_sentence_is_not_an_assignment(text, job):
    (status, reasons), = statuses(text)
    assert (status, reasons) == ("UNREPRESENTABLE", ["TENSE:past"])
    got = run(text, job)
    assert got["decision"] == "undecided" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
    assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["abstention"]["by_status"]["UNREPRESENTABLE"] == 1
    assert got["records"]["agents"] == []


def test_M3_the_non_past_sentence_of_the_same_form_is_still_routed():
    got = run("ハルが実装をやる。\n", IMPLEMENT)
    assert (got["decision"], got["agent"]) == ("route", "ハル")
    got = run("Rook reviews the code.\n", REVIEW)
    assert (got["decision"], got["agent"]) == ("route", "Rook")

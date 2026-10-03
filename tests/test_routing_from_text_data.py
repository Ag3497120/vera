"""W2-h2: the frozen self-made data (T2).  The bank runner measures through the entry (a subprocess); here the same function the
entry calls is run in-process so that the test is fast, and one test runs the runner itself on the small bank."""
import hashlib
import json
import os
import subprocess
import sys
import unicodedata

import pytest

from verantyx import routing_from_text as rt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tests", "routing_from_text", "data")


def items(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def norm(text):
    return unicodedata.normalize("NFKC", text).strip().casefold()


def run_all(name, directory):
    results = []
    for item in items(name):
        path = os.path.join(DATA, directory, item["explanation_id"] + ".md")
        results.append((item, rt.run(path, item["task"])))
    return results


def test_the_frozen_files_still_have_their_hashes():
    frozen = json.load(open(os.path.join(DATA, "FROZEN.json"), encoding="utf-8"))
    assert len(frozen["files"]) >= 12 and "items_mid.jsonl" in frozen["files"]     # the middle role's tasks (round 2) are frozen too
    for path, info in frozen["files"].items():
        with open(os.path.join(DATA, path), "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == info["sha256"], path


def test_T2_the_self_made_bank_has_the_required_size_and_traps():
    body, shaped = items("items.jsonl"), items("items_reader_shaped.jsonl")
    assert len(body) >= 48 and len({i["id"] for i in body + shaped}) == len(body) + len(shaped)
    per = {}
    for item in body:
        per.setdefault(item["explanation_id"], []).append(item)
    assert sorted(per) == ["e1", "e2", "e3", "e4", "e5", "e6"] and all(len(v) >= 8 for v in per.values())
    assert all(sum(1 for i in v if i["expect"]["decision"] == "undecided") >= 2 for v in per.values())
    aliases = {"重い方", "小さい子", "the quiet one"}      # names that the explanation gives to an agent it named first elsewhere

    def names(task):
        used = [n for v in task["already_used"].values() for n in ([v] if isinstance(v, str) else v)]
        return set(used) | set(task["running"])
    assert sum(1 for i in body if names(i["task"]) & aliases) >= 3
    assert sum(1 for i in body if {"used_today", "files", "date"} & set(i["task"])) >= 3
    assert {i["lang"] for i in body} == {"ja", "en"} and {i["explanation_id"] for i in shaped} == {"r1", "r2"}
    assert all(sum(1 for i in shaped if i["explanation_id"] == e) >= 6 for e in ("r1", "r2"))


@pytest.mark.parametrize("name,directory", [("items.jsonl", "explanations"), ("items_reader_shaped.jsonl", "explanations_reader_shaped"),
                                            ("items_mid.jsonl", "explanations"), ("items_mid_reader_shaped.jsonl", "explanations_reader_shaped")])
def test_T2_no_job_is_given_to_a_wrong_agent_and_a_route_only_comes_from_a_complete_reading(name, directory):
    misroutes = 0
    for item, out in run_all(name, directory):
        expect = item["expect"]
        if out["decision"] == "route":
            # the gate is complete for every route: nothing unread, and every unit read and mapped
            assert out["abstention"] is None
            assert all(out["reading"]["by_status"][s] == 0 for s in rt.UNIT_STATUSES if s not in rt.PASSING_STATUSES), item["id"]
            if expect["decision"] != "route" or norm(out["agent"]) != norm(expect["agent"]):
                misroutes += 1
    assert misroutes == 0


def test_T2_the_reader_shaped_explanations_route_at_least_one_job_correctly():
    right = [i["id"] for i, out in run_all("items_reader_shaped.jsonl", "explanations_reader_shaped")
             if i["expect"]["decision"] == "route" and out["decision"] == "route" and norm(out["agent"]) == norm(i["expect"]["agent"])]
    assert len(right) >= 1


def test_T2_the_bank_runner_goes_through_the_entry_and_refuses_to_write_inside_the_bank(tmp_path):
    env = {**os.environ, "PYTHONPATH": ROOT, "PYTHONDONTWRITEBYTECODE": "1"}
    runner = os.path.join(ROOT, "tests", "routing_from_text", "run_bank.py")
    inside = subprocess.run([sys.executable, runner, "--bank", DATA, "--items", os.path.join(DATA, "items_reader_shaped.jsonl"),
                             "--out", os.path.join(DATA, "explanations")], capture_output=True, text=True, env=env, cwd=ROOT)
    assert inside.returncode == 2
    proc = subprocess.run([sys.executable, runner, "--bank", DATA, "--items", os.path.join(DATA, "items_reader_shaped.jsonl"),
                           "--explanations-dir", "explanations_reader_shaped", "--out", str(tmp_path)],
                          capture_output=True, text=True, env=env, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    summary = json.load(open(tmp_path / "summary.json", encoding="utf-8"))
    assert summary["misroutes"] == 0 and summary["errors"] == 0 and summary["items"] == 16 and summary["route_correct"] >= 1
    assert os.path.exists(tmp_path / "runs.jsonl") and "misroutes: 0" in open(tmp_path / "summary.txt", encoding="utf-8").read()

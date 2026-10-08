"""W1-a2 X5: the B1 entry `--entry mod-semantic-read` (the reading entry `python -m verantyx.semantic_read`, one process per item).

The scoring rules are not touched (score.py, v2/*.py, classify.py, checks.py); the default entry of B1 stays `cli`. The v2 sample used here is the
self-made one (fixtures/B1_v2/items.jsonl, v2 format): the old B1 sample is w1s format and every item of it is ITEM_INVALID under `--profile v2`,
so a run on it would call nothing and prove nothing ("unreachable 0" with `vera_calls 0`).
"""
import json
import sys
from pathlib import Path

import pytest

from tools.bank_score import adapters, cli, runner, schema

TREE = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
V2_SAMPLE = FIX / "B1_v2" / "items.jsonl"
W1S_SAMPLE = FIX / "B1" / "items.jsonl"


def _items():
    return schema.read_items(str(V2_SAMPLE), "B1", None, "v2")


def test_the_default_entry_of_b1_is_still_cli_and_it_is_still_unreachable():
    assert adapters.DEFAULT_ENTRY["B1"] == "cli" and adapters.check_entry("B1", None) == "cli"
    assert adapters.ENTRIES["B1"] == ("cli", "mod-semantic-read")
    case = _items()[0]["case"]
    r = adapters.reachability("B1", "cli", case)
    assert r["reachable"] is False and r["capability"] == "sentence_structure"


def test_mod_semantic_read_reaches_every_item():
    for rec in _items():
        assert rec["errors"] == [], rec["id"]
        r = adapters.reachability("B1", "mod-semantic-read", rec["case"])
        assert r["reachable"] is True and r["missing"] == [] and r["capability"] is None


def test_the_call_carries_the_input_string_only():
    for rec in _items():
        c = adapters.build_call("B1", "mod-semantic-read", rec["case"])
        assert c == {"module": "verantyx.semantic_read", "argv": ["--text=" + rec["case"]["input"]], "files": []}
        flat = " ".join(c["argv"])
        assert "--lang" not in flat
        for secret in (rec["raw"].get("lang"), rec["raw"].get("category"), rec["raw"].get("phenomenon"), rec["raw"].get("unit")):
            assert secret not in c["argv"][0].replace(rec["case"]["input"], ""), secret


def test_an_input_that_starts_with_a_dash_is_not_taken_for_an_option():
    c = adapters.build_call("B1", "mod-semantic-read", {"input": "-犬が走った。"})
    assert c["argv"] == ["--text=-犬が走った。"]


def test_the_other_banks_and_entries_keep_their_calls():
    recs = {r["id"]: r for r in schema.read_items(str(FIX / "B2" / "items.jsonl"), "B2", None)}
    some = next(iter(recs.values()))
    call = adapters.build_call("B2", "cli-ask-round5", some["case"])
    assert call["argv"][0] == "ask" and call["module"] == "verantyx.cli"


def test_a_module_outside_the_closed_set_is_refused_and_nothing_is_started(tmp_path):
    assert set(runner.ALLOWED_MODULES) == {"verantyx.cli", "verantyx.semantic_read"}
    sess = runner.Session(sys.executable, str(TREE), None, 60.0)
    try:
        with pytest.raises(ValueError):
            sess.run_ask(1, ["--text=x"], [], "os")
        with pytest.raises(ValueError):
            sess.run_ask(1, ["--text=x"], [], "verantyx.one")
        with pytest.raises(ValueError):
            sess.precheck("subprocess")
        assert sess.processes_checked == 0, "a refused module started a process"
    finally:
        sess.close()


def test_the_child_script_also_refuses_a_module_outside_the_set(tmp_path):
    sess = runner.Session(sys.executable, str(TREE), None, 60.0)
    try:
        r = sess._spawn("run_module", ["os", "--text=x"], tmp_path)
        assert r["exit_code"] == 97 and "module not allowed" in r["stderr"], r
    finally:
        sess.close()


@pytest.mark.parametrize("raw,state,readable", [
    ({"readable": True, "clauses": [{"predicate": "走る"}], "relations": []}, "answer", True),
    ({"readable": False, "clauses": [], "relations": []}, "abstain", False),
    ({"clauses": [], "relations": []}, "unmapped", None),
    ({"readable": "yes", "clauses": [], "relations": []}, "unmapped", None),
])
def test_observe_maps_readable_to_a_typed_state(raw, state, readable):
    o = adapters.observe("B1", raw, "mod-semantic-read", ["--text=x"], 0, None, "v2")
    assert o["state"] == state and o["readable"] is readable
    assert o["clauses"] == raw["clauses"] and o["relations"] == raw["relations"]


def _run(tmp_path, items, profile="v2", extra=()):
    out = tmp_path / "out"
    code = cli.main(["--profile", profile, "--bank", "B1", "--items", str(items), "--entry", "mod-semantic-read", "--tree", str(TREE),
                     "--out", str(out), "--python", sys.executable, *extra])
    return code, out


def test_the_scorer_runs_the_whole_v2_sample_through_the_entry(tmp_path):
    code, out = _run(tmp_path, V2_SAMPLE)
    assert code == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    counts = {k: v["count"] for k, v in summary["classes"].items()}
    total = summary["total"]
    assert total == len(_items()) and total >= 60
    assert counts["unreachable"] == 0 and counts["runtime_error"] == 0 and counts["unscorable"] == 0
    assert meta["vera_calls"] == total, "the entry was not called for every item (a run that calls nothing proves nothing)"
    assert meta["provenance_total"]["outside_count"] == 0 and meta["provenance_total"]["processes_unverified"] == 0
    assert counts["misread"] == 0 and counts["false_compliance"] == 0
    assert meta["entry"] == "mod-semantic-read" and "semantic_read" in meta["entry_note"]
    assert any("verantyx.semantic_read" in str(x) for x in meta["child_argv_template"])
    assert counts["correct"] + counts["correct_abstain"] > 0


def test_the_second_v2_sample_runs_through_the_entry_with_no_misreading(tmp_path):
    """round 5: the sample of the entry's misreading types (converse verbs, residence as goal, から of a passive, sentence-initial capitals ...)"""
    sample = FIX / "B1_v2_r2" / "items.jsonl"
    code, out = _run(tmp_path, sample)
    assert code == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    counts = {k: v["count"] for k, v in summary["classes"].items()}
    total = summary["total"]
    assert total >= 36 and meta["vera_calls"] == total
    assert counts["unreachable"] == 0 and counts["runtime_error"] == 0 and counts["unscorable"] == 0
    assert counts["misread"] == 0 and counts["false_compliance"] == 0
    assert meta["provenance_total"]["outside_count"] == 0


def test_the_w1s_sample_runs_through_the_entry_without_a_runtime_error(tmp_path):
    code, out = _run(tmp_path, W1S_SAMPLE, profile="w1s")
    assert code == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["classes"]["runtime_error"]["count"] == 0
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["vera_calls"] > 0 and meta["provenance_total"]["outside_count"] == 0


def test_the_entry_does_not_see_the_labels_of_the_item(tmp_path):
    """the raw child output of an item holds no field of the item other than what the entry itself returns"""
    code, out = _run(tmp_path, V2_SAMPLE)
    raw = sorted((out / "raw").glob("*.json"))
    assert raw
    doc = json.loads(raw[0].read_text(encoding="utf-8"))
    assert doc["argv"] == ["--text=" + json.loads(V2_SAMPLE.read_text(encoding="utf-8").splitlines()[0])["input"]]

"""W2-h2: the entry ``python -m verantyx.cli route`` (T1): the shape, determinism, the typed errors, a route through the real reader."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tests", "routing_from_text", "data")
TASK = {"role": "implement", "kind": "feature", "size": "medium", "touches": [], "already_used": {}, "running": {}}
KEYS = ["schema", "decision", "agent", "undecided_reason", "abstention", "basis_kind", "evidence", "decided_by", "records",
        "relations", "reading", "router", "ignored_fields", "task"]


def entry(explanation, task, seed="0", module=("-m", "verantyx.cli", "route")):
    env = dict(os.environ)
    env.pop("VERA_PLACEMENT", None)      # W5-d2: the entry reads VERA_PLACEMENT, so a variable of the caller must not decide what these tests (written for "no placement") see
    env.update({"PYTHONPATH": ROOT, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": seed})
    argument = task if isinstance(task, str) else json.dumps(task, ensure_ascii=False)
    return subprocess.run([sys.executable, *module, "--explanation", explanation, "--task", argument],
                          capture_output=True, text=True, env=env, cwd=ROOT)


def r1():
    return os.path.join(DATA, "explanations_reader_shaped", "r1.md")


def test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader():
    # W5-d2 (auditor's ruling B1, K2): the name is kept; the expectation is the contract of W5-d. This entry has no placement (the variable is taken off in entry()), and since
    # W5-d (R-J1) a Japanese name that no naming sentence introduced is not verified without a placement: the units that were MAPPED are NAME_UNRESOLVED
    # (NAME_UNVERIFIED:<name>:NO_PLACEMENT) and nobody is routed. The earlier text of this test (W5-a round 3: two sentences UNREAD, five MAPPED) is kept in the
    # docs (w5d2-amended) and in K64 of docs/READING_SOUNDNESS.md.
    proc = entry(r1(), TASK)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("\n") == 1                      # one line
    out = json.loads(proc.stdout)
    assert list(out) == KEYS
    assert (out["decision"], out["agent"], out["undecided_reason"]) == ("undecided", None, "ABSTAINED")
    assert out["decided_by"] == "gate:INCOMPLETE_READING" and out["router"] is None
    assert out["abstention"]["type"] == "INCOMPLETE_READING"
    assert out["abstention"]["detail"] == "8 of 8 units were not read and mapped; no job is routed"
    assert out["abstention"]["units"] == [
        {"index": 0, "status": "NAME_UNRESOLVED", "text": "ハルは実装をやる。", "reasons": ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]},
        {"index": 1, "status": "UNREAD", "text": "モモがテストを書く。", "reasons": ["AGENT_EVIDENCE_MISSING:モモ"]},
        {"index": 2, "status": "UNREAD", "text": "セキがコードを確かめる。", "reasons": ["AGENT_EVIDENCE_MISSING:セキ"]},
        {"index": 3, "status": "NAME_UNRESOLVED", "text": "モモは検証をやらない。", "reasons": ["NAME_UNVERIFIED:モモ:NO_PLACEMENT"]},
        {"index": 4, "status": "NAME_UNRESOLVED", "text": "レビューはモモがやる。", "reasons": ["NAME_UNVERIFIED:モモ:NO_PLACEMENT"]},
        {"index": 5, "status": "NAME_UNRESOLVED", "text": "ハルが攻撃をやる。", "reasons": ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]},
        {"index": 6, "status": "NAME_UNRESOLVED", "text": "ハルとセキは同じ会社だ。", "reasons": ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]},
        {"index": 7, "status": "NAME_UNRESOLVED", "text": "モモはハルより速い。", "reasons": ["NAME_UNVERIFIED:モモ:NO_PLACEMENT"]}]
    assert out["evidence"] == ["ハルは実装をやる。", "モモがテストを書く。", "セキがコードを確かめる。", "モモは検証をやらない。", "レビューはモモがやる。",
                               "ハルが攻撃をやる。", "ハルとセキは同じ会社だ。", "モモはハルより速い。"]
    assert out["reading"]["by_status"] == {"MAPPED": 0, "COMPARISON_ONLY": 0, "UNREAD": 2, "PREDICATE_CLASS_UNKNOWN": 0, "WORK_TERM_UNKNOWN": 0,
                                           "AMBIGUOUS_RELATION": 0, "NAME_UNRESOLVED": 6, "CONTRADICTION": 0, "UNREPRESENTABLE": 0}
    assert out["reading"]["lookup"] == "stub-no-placement/1"
    assert out["records"]["agents"] == []                      # nothing was mapped, so no agent record exists
    assert all(a["basis"]["kind"] == "declared_text" and a["lineage"] is None for a in out["records"]["agents"])


def test_T1_two_runs_and_two_hash_seeds_give_the_same_bytes():
    first, second, other = entry(r1(), TASK).stdout, entry(r1(), TASK).stdout, entry(r1(), TASK, seed="1").stdout
    assert first and first == second == other


def test_T1_an_explanation_with_an_unread_sentence_is_undecided_with_the_type_of_the_reason():
    out = json.loads(entry(os.path.join(DATA, "explanations", "e1.md"), TASK).stdout)
    assert out["decision"] == "undecided" and out["agent"] is None and out["undecided_reason"] == "ABSTAINED"
    assert out["abstention"]["type"] == "INCOMPLETE_READING" and out["router"] is None and out["decided_by"] == "gate:INCOMPLETE_READING"
    assert sum(out["abstention"]["by_status"].values()) == out["reading"]["units"]


def test_T1_the_task_may_be_the_path_of_a_json_file(tmp_path):
    path = tmp_path / "task.json"
    path.write_text(json.dumps(TASK), encoding="utf-8")
    assert entry(r1(), str(path)).stdout == entry(r1(), TASK).stdout


def test_T1_the_module_entry_and_the_cli_entry_say_the_same():
    assert entry(r1(), TASK, module=("-m", "verantyx.routing_from_text")).stdout == entry(r1(), TASK).stdout


def test_T1_bad_task_and_bad_explanation_are_exit_code_2_with_a_typed_error(tmp_path):
    bad = entry(r1(), {"role": "implement", "kind": "feature"})
    assert bad.returncode == 2 and json.loads(bad.stdout)["error"] == "BAD_TASK"
    notjson = entry(r1(), "{not json")
    assert notjson.returncode == 2 and json.loads(notjson.stdout)["error"] == "BAD_TASK"
    missing = entry(str(tmp_path / "nothing.md"), TASK)
    assert missing.returncode == 2 and json.loads(missing.stdout)["error"] == "BAD_EXPLANATION"
    binary = tmp_path / "bad.md"
    binary.write_bytes(b"\xff\xfe\x00 not utf-8")
    assert entry(str(binary), TASK).returncode == 2 and json.loads(entry(str(binary), TASK).stdout)["error"] == "BAD_EXPLANATION"


def test_T1_aliases_and_ignored_fields_come_back_typed():
    task = dict(TASK, used_today={"ハル": 1}, date="2026-10-03", note="x")
    out = json.loads(entry(r1(), task).stdout)
    assert [(f["field"], f["reason"]) for f in out["ignored_fields"]] == [
        ("date", "NOT_USED_BY_ROUTER"), ("note", "UNKNOWN_TASK_FIELD"), ("touches", "NOT_USED_BY_ROUTER"),
        ("used_today", "NOT_USED_BY_ROUTER")]


def test_the_entry_is_a_subcommand_of_the_cli():
    proc = subprocess.run([sys.executable, "-m", "verantyx.cli", "route", "--help"], capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": ROOT, "PYTHONDONTWRITEBYTECODE": "1"}, cwd=ROOT)
    assert proc.returncode == 0 and "--explanation" in proc.stdout and "--task" in proc.stdout

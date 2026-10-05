"""LLM-free tests for W3-a7 trial state accounting and the production gate."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

from tools import gen_coarse_evidence as gce

TREE = Path(__file__).resolve().parents[1]
R2 = TREE / "artifacts/w3-a7/current-r2"
CASES = json.loads((R2 / "trial_test_cases.json").read_text(encoding="utf-8"))
SCRATCHPAD = Path(
    "/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
    "516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3-a7-r2"
)


def _judge_module():
    path = R2 / "trial_judge.py"
    spec = importlib.util.spec_from_file_location("w3a7_trial_judge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _frozen_source_rows():
    words = [row["word"] for row in _jsonl(TREE / CASES["sources"]["needs"])]
    v2_rows = _jsonl(TREE / CASES["sources"]["v2_claims"])
    labels = _jsonl(TREE / CASES["sources"]["visual_labels"])
    return words, v2_rows, labels


def _raw_frame_from_v2(row):
    if row.get("source_status") != "ACCEPTED":
        return None
    frame = row.get("frame")
    if not isinstance(frame, dict):
        return []
    return [
        {"particle": particle,
         "roles": [{"role": item["role"], "types": item["types"]} for item in entries]}
        for particle, entries in frame.items()
    ]


def _raw_from_v2(words, v2_rows):
    by_word = {row["word"]: row for row in v2_rows}
    return {"items": [{"word": word, "frame": _raw_frame_from_v2(by_word[word])} for word in words]}


def _collected_from_raw(words, raw):
    answers, _ = gce.parse_output_role(words, raw)
    return [{"word": word, "frame": answers[word], "abstained": answers[word] is None}
            for word in words if word in answers]


def test_one_missing_raw_item_is_unknown_and_separate_from_null_abstention():
    judge = _judge_module()
    words, v2_rows, labels = _frozen_source_rows()
    raw = _raw_from_v2(words, v2_rows)
    raw["items"] = [row for index, row in enumerate(raw["items"])
                    if index != CASES["single_missing_row"]["drop_index"]]
    result = judge.evaluate_trial(words, raw, _collected_from_raw(words, raw), v2_rows, labels)
    expected = CASES["single_missing_row"]["expected"]
    assert result["status"] == expected["status"]
    assert result["state_counts"] == expected["state_counts"]
    assert "missing" in result["state_counts"] and "abstain_null" in result["state_counts"]


def test_trial_reports_response_null_missing_and_invalid_duplicate_separately():
    judge = _judge_module()
    words, v2_rows, labels = _frozen_source_rows()
    raw = _raw_from_v2(words, v2_rows)
    matrix = CASES["four_state_matrix"]
    by_word = {row["word"]: row for row in raw["items"]}
    null_word = words[matrix["null_index"]]
    for row in raw["items"]:
        if row["word"] != null_word and row["frame"] is None:
            row["frame"] = []
    by_word[words[matrix["null_index"]]]["frame"] = None
    missing_word = words[matrix["missing_index"]]
    duplicate_word = words[matrix["duplicate_index"]]
    invalid_word = words[matrix["invalid_index"]]
    raw["items"] = [row for row in raw["items"] if row["word"] != missing_word]
    raw["items"].append(copy.deepcopy(by_word[duplicate_word]))
    by_word[invalid_word]["frame"] = "malformed"
    result = judge.evaluate_trial(words, raw, _collected_from_raw(words, raw), v2_rows, labels)
    expected = matrix["expected"]
    assert result["status"] == expected["status"]
    assert result["state_counts"] == expected["state_counts"]
    assert result["invalid_reasons"] == expected["invalid_reasons"]
    assert len(result["word_statuses"]) == len(words)


def test_only_latest_complete_pass_for_current_freeze_opens_production_gate():
    judge = _judge_module()
    SCRATCHPAD.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="trial-gate-", dir=SCRATCHPAD))
    frozen = root / "frozen-input.txt"
    frozen.write_text("frozen test input\n", encoding="utf-8")
    freeze = root / "freeze.sha256"
    freeze.write_text(hashlib.sha256(frozen.read_bytes()).hexdigest() + "  frozen-input.txt\n",
                      encoding="utf-8")
    events = root / "trial_runs.jsonl"

    def complete(trial_id, status):
        result_path = root / "results" / (trial_id + ".json")
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({"status": status}) + "\n", encoding="utf-8")
        judge.record_trial_complete(root, freeze, events, trial_id, result_path, status)

    first = judge.record_trial_start(root, freeze, events)["trial_id"]
    complete(first, "PASS")
    assert judge.check_production_gate(root, freeze, events)["allowed"] is CASES[
        "append_only_gate"]["allow_latest_complete_pass"]

    unfinished = judge.record_trial_start(root, freeze, events)["trial_id"]
    assert not judge.check_production_gate(root, freeze, events)["allowed"]
    complete(unfinished, "FAIL")
    assert not judge.check_production_gate(root, freeze, events)["allowed"]

    latest = judge.record_trial_start(root, freeze, events)["trial_id"]
    complete(latest, "PASS")
    assert judge.check_production_gate(root, freeze, events)["allowed"] is CASES[
        "append_only_gate"]["allow_newer_complete_pass"]

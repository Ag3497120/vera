"""W3-a7 LLM-free trial assessment and append-only production gate."""
import argparse
import collections
import datetime as dt
import fcntl
import hashlib
import json
import os
import uuid
from pathlib import Path

from tools import gen_coarse_evidence as gce
from verantyx import coarse_types as ct

ROOT = Path(__file__).resolve().parents[3]
STATE_NAMES = ("response", "abstain_null", "missing", "invalid_or_duplicate")
ERROR_LABELS = {"誤り", "明らかな誤り"}
KNOWN_LABELS = {"正しい", "疑わしい"} | ERROR_LABELS


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise ValueError("invalid JSONL at %s:%d" % (path, line_number)) from exc
    return rows


def _frame(row):
    value = row.get("frame") if isinstance(row, dict) else None
    return value if isinstance(value, dict) else {}


def _claim_keys(word, frame):
    keys = []
    for particle, entries in frame.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            role, types = entry.get("role"), entry.get("types")
            if isinstance(role, str) and isinstance(types, list):
                keys.append((word, particle, role, tuple(sorted(types))))
    return keys


def _label_index(label_rows):
    labels = collections.defaultdict(list)
    for row in label_rows:
        if not isinstance(row, dict):
            continue
        word, particle, role, types = (row.get("word"), row.get("particle"),
                                       row.get("role"), row.get("types"))
        if isinstance(word, str) and isinstance(particle, str) and isinstance(role, str) \
                and isinstance(types, list):
            labels[(word, particle, role, tuple(sorted(types)))].append(row.get("visual_label"))
    return labels


def _label_counts(words, rows_by_word, labels):
    errors = unclassified = 0
    for word in words:
        row = rows_by_word.get(word)
        if row is None or row.get("source_status") != "ACCEPTED":
            continue
        for key in _claim_keys(word, _frame(row)):
            found = labels.get(key, [])
            if len(found) != 1 or found[0] not in KNOWN_LABELS:
                unclassified += 1
            elif found[0] in ERROR_LABELS:
                errors += 1
    return errors, unclassified


def _raw_reason(word, item):
    _, stats = gce.parse_output_role([word], {"items": [item]})
    if stats.get("invalid"):
        return "invalid_frame"
    if stats.get("frame_dup_particle"):
        return "duplicate_particle"
    if stats.get("role_dup"):
        return "duplicate_role"
    if stats.get("dup_dropped"):
        return "duplicate_word_response"
    return "invalid_output"


def evaluate_trial(words, raw_data, collected_rows, v2_rows, label_rows):
    """Return the preregistered U2 result and an explicit state for every requested word."""
    words = list(words)
    if len(words) != 40 or len(set(words)) != len(words) or any(not isinstance(w, str) for w in words):
        raise ValueError("trial needs must contain 40 distinct string words")
    word_set = set(words)
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("items"), list):
        raise ValueError("raw response must contain an items list")
    if not isinstance(collected_rows, list):
        raise ValueError("collected rows must be a list")

    raw_groups = collections.defaultdict(list)
    raw_foreign = 0
    for item in raw_data["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("word"), str) \
                or item["word"] not in word_set:
            raw_foreign += 1
            continue
        raw_groups[item["word"]].append(item)
    answers, parser_stats = gce.parse_output_role(words, raw_data)

    collected_groups = collections.defaultdict(list)
    collected_foreign = 0
    for row in collected_rows:
        if not isinstance(row, dict) or not isinstance(row.get("word"), str) \
                or row["word"] not in word_set:
            collected_foreign += 1
            continue
        collected_groups[row["word"]].append(row)

    states = []
    invalid_reasons = collections.Counter()
    answer_by_word = {}
    for word in words:
        raw_matches = raw_groups.get(word, [])
        output_matches = collected_groups.get(word, [])
        reason = None
        if not raw_matches:
            state, reason = "missing", "no_raw_item"
        elif len(raw_matches) > 1:
            state, reason = "invalid_or_duplicate", "duplicate_word_response"
        elif word not in answers:
            state, reason = "invalid_or_duplicate", _raw_reason(word, raw_matches[0])
        elif answers[word] is None:
            state = "abstain_null"
            answer_by_word[word] = None
        else:
            state = "response"
            answer_by_word[word] = answers[word]

        if state in ("response", "abstain_null"):
            expected_frame = answers[word]
            if len(output_matches) != 1 \
                    or output_matches[0].get("frame") != expected_frame \
                    or output_matches[0].get("abstained") is not (expected_frame is None):
                state, reason = "invalid_or_duplicate", "collector_mismatch"
                answer_by_word.pop(word, None)
        elif output_matches:
            state, reason = "invalid_or_duplicate", "unexpected_collected_row"

        if state == "invalid_or_duplicate":
            invalid_reasons[reason] += 1
        states.append({"word": word, "state": state, "reason": reason})

    state_counts = {name: 0 for name in STATE_NAMES}
    for item in states:
        state_counts[item["state"]] += 1

    v2_by_word = {}
    for row in v2_rows:
        if not isinstance(row, dict) or not isinstance(row.get("word"), str):
            raise ValueError("frozen v2 row lacks a word")
        if row["word"] in v2_by_word:
            raise ValueError("frozen v2 rows contain duplicate words")
        v2_by_word[row["word"]] = row
    if any(word not in v2_by_word for word in words):
        raise ValueError("trial words are not all present in frozen v2 claims")

    labels = _label_index(label_rows)
    v2_errors, v2_unclassified = _label_counts(words, v2_by_word, labels)
    v3_errors = v3_unclassified = 0
    v3_claimed_by_particle = collections.Counter()
    v2_claimed_by_particle = collections.Counter()
    for word in words:
        old = v2_by_word[word]
        if old.get("source_status") == "ACCEPTED":
            for particle in ct.CASE_PARTICLES_9:
                entries = _frame(old).get(particle)
                if isinstance(entries, list) and entries:
                    v2_claimed_by_particle[particle] += 1
        if word not in answer_by_word or answer_by_word[word] is None:
            continue
        frame = answer_by_word[word]
        for particle in ct.CASE_PARTICLES_9:
            entries = frame.get(particle)
            if isinstance(entries, list) and entries:
                v3_claimed_by_particle[particle] += 1
        for key in _claim_keys(word, frame):
            found = labels.get(key, [])
            if len(found) != 1 or found[0] not in KNOWN_LABELS:
                v3_unclassified += 1
            elif found[0] in ERROR_LABELS:
                v3_errors += 1

    rates = {}
    rate_fail = False
    for particle in ct.CASE_PARTICLES_9:
        old_count = v2_claimed_by_particle[particle]
        new_count = v3_claimed_by_particle[particle]
        passed = new_count >= old_count
        rate_fail = rate_fail or not passed
        rates[particle] = {"v2_claimed": old_count, "v3_claimed": new_count,
                           "denominator": len(words), "v2_rate": old_count / len(words),
                           "v3_rate": new_count / len(words), "pass": passed}

    global_integrity_errors = {"raw_foreign_items": raw_foreign,
                               "collected_foreign_rows": collected_foreign}
    state_incomplete = state_counts["missing"] > 0 or state_counts["invalid_or_duplicate"] > 0
    if state_incomplete or any(global_integrity_errors.values()):
        status = "UNKNOWN"
        reason = "missing_or_invalid_trial_output"
    elif rate_fail:
        status = "FAIL"
        reason = "particle_claim_rate_below_v2"
    elif v2_unclassified > 0 or v3_unclassified > 0:
        status = "UNKNOWN"
        reason = "unclassified_claims"
    elif v3_errors > v2_errors:
        status = "FAIL"
        reason = "obvious_errors_above_v2"
    else:
        status = "PASS"
        reason = "all_preregistered_checks_pass"

    return {
        "status": status,
        "reason": reason,
        "state_counts": state_counts,
        "word_statuses": states,
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "global_integrity_errors": global_integrity_errors,
        "parser_counts": {key: parser_stats.get(key, 0) for key in
                           ("foreign", "missing", "dup_dropped", "invalid",
                            "frame_dup_particle", "role_dup", "abstained", "answered")},
        "claim_rates_by_particle": rates,
        "v2_obvious_errors": v2_errors,
        "v3_obvious_errors": v3_errors,
        "v2_unclassified_claims": v2_unclassified,
        "v3_unclassified_claims": v3_unclassified,
        "labels_complete": v2_unclassified == 0 and v3_unclassified == 0,
        "trial_words": len(words),
        "evidence_types": {"trial_response": "generated", "v2_claims": "generated",
                           "visual_labels": "testimony"},
    }


def _rooted_path(root, path):
    root = Path(root).resolve()
    path = Path(path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path is outside worktree: %s" % path) from exc
    return resolved, relative.as_posix()


def _verify_freeze(root, freeze_file):
    root = Path(root).resolve()
    freeze_path, _ = _rooted_path(root, freeze_file)
    entries = {}
    for line_number, line in enumerate(freeze_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        if "  " not in line:
            raise ValueError("invalid freeze row at line %d" % line_number)
        expected, name = line.split("  ", 1)
        if len(expected) != 64 or name in entries:
            raise ValueError("invalid or duplicate freeze row at line %d" % line_number)
        file_path, rel = _rooted_path(root, name)
        actual = sha256_file(file_path)
        if actual != expected:
            raise ValueError("frozen hash mismatch: %s" % name)
        entries[rel] = actual
    if not entries:
        raise ValueError("freeze manifest is empty")
    return sha256_file(freeze_path), entries


def _read_events(path):
    path = Path(path)
    if not path.exists():
        return []
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise ValueError("invalid trial ledger row %d" % line_number) from exc
        if not isinstance(event, dict) or event.get("event") not in ("started", "completed") \
                or not isinstance(event.get("trial_id"), str):
            raise ValueError("invalid trial ledger event at line %d" % line_number)
        events.append(event)
    return events


def _append_event(path, event):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def record_trial_start(root, freeze_file, events_file):
    freeze_hash, frozen_files = _verify_freeze(root, freeze_file)
    events = _read_events(events_file)
    if events and events[-1].get("event") == "started":
        raise ValueError("another trial is unfinished")
    event = {"event": "started", "trial_id": str(uuid.uuid4()),
             "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "freeze_sha256": freeze_hash, "frozen_files": frozen_files}
    _append_event(events_file, event)
    return event


def record_trial_complete(root, freeze_file, events_file, trial_id, result_file,
                          status, reason=None):
    if status not in ("PASS", "FAIL", "UNKNOWN"):
        raise ValueError("invalid trial status")
    events = _read_events(events_file)
    if not events or events[-1].get("event") != "started" \
            or events[-1].get("trial_id") != trial_id:
        raise ValueError("completion must follow the matching latest start")
    result_path, result_relative = _rooted_path(root, result_file)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    if not result_path.exists():
        result = {"status": status, "reason": reason or "trial_command_failed"}
        data = (json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(str(result_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("trial result is missing or invalid") from exc
    if result.get("status") != status:
        raise ValueError("trial result status does not match completion")
    event = {"event": "completed", "trial_id": trial_id,
             "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "freeze_sha256": events[-1].get("freeze_sha256"),
             "frozen_files": events[-1].get("frozen_files"),
             "status": status, "reason": reason or result.get("reason"),
             "result_file": result_relative, "result_sha256": sha256_file(result_path)}
    _append_event(events_file, event)
    return event


def check_production_gate(root, freeze_file, events_file):
    try:
        current_hash, current_files = _verify_freeze(root, freeze_file)
        events = _read_events(events_file)
    except (OSError, ValueError) as exc:
        return {"allowed": False, "reason": "freeze_or_ledger_invalid", "detail": str(exc)}
    starts = [event for event in events if event["event"] == "started"]
    if not starts:
        return {"allowed": False, "reason": "no_trial"}
    latest = starts[-1]
    if events[-1]["event"] != "completed" or events[-1].get("trial_id") != latest["trial_id"]:
        return {"allowed": False, "reason": "latest_trial_incomplete",
                "trial_id": latest["trial_id"]}
    completed = [event for event in events if event["event"] == "completed"
                 and event["trial_id"] == latest["trial_id"]]
    if len(completed) != 1:
        return {"allowed": False, "reason": "latest_trial_completion_invalid",
                "trial_id": latest["trial_id"]}
    result = completed[0]
    if latest.get("freeze_sha256") != current_hash or latest.get("frozen_files") != current_files \
            or result.get("freeze_sha256") != current_hash \
            or result.get("frozen_files") != current_files:
        return {"allowed": False, "reason": "freeze_changed_since_trial",
                "trial_id": latest["trial_id"]}
    if result.get("status") != "PASS":
        return {"allowed": False, "reason": "latest_trial_not_pass",
                "status": result.get("status"), "trial_id": latest["trial_id"]}
    try:
        result_path, _ = _rooted_path(root, result["result_file"])
        result_doc = json.loads(result_path.read_text(encoding="utf-8"))
        if sha256_file(result_path) != result.get("result_sha256") \
                or result_doc.get("status") != "PASS":
            raise ValueError("result hash or status mismatch")
    except (KeyError, OSError, ValueError) as exc:
        return {"allowed": False, "reason": "latest_trial_result_invalid",
                "trial_id": latest["trial_id"], "detail": str(exc)}
    return {"allowed": True, "reason": "latest_frozen_trial_passed",
            "trial_id": latest["trial_id"], "freeze_sha256": current_hash,
            "result_sha256": result["result_sha256"]}


def _raw_response_from_run(out_dir, expected_words):
    ledger_path = Path(out_dir) / "ledger.jsonl"
    events = gce.read_ledger(str(ledger_path))
    successful = gce._first_ok(events)
    if len(successful) != 1:
        raise ValueError("trial must have exactly one successful batch")
    batch_id, event = next(iter(successful.items()))
    words_by_attempt = gce._batch_words(events)
    actual_words = words_by_attempt.get((batch_id, event["attempt"]))
    if actual_words != list(expected_words):
        raise ValueError("successful batch words differ from frozen trial needs")
    output_path = event.get("out_path")
    if not output_path or not Path(output_path).is_file() \
            or sha256_file(output_path) != event.get("out_sha256"):
        raise ValueError("trial raw output is missing or changed")
    with open(output_path, encoding="utf-8") as stream:
        raw = json.load(stream)
    return raw


def _write_unique_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _cli():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "gate"):
        item = sub.add_parser(name)
        item.add_argument("--root", required=True)
        item.add_argument("--freeze", required=True)
        item.add_argument("--events", required=True)
    complete = sub.add_parser("complete")
    complete.add_argument("--root", required=True)
    complete.add_argument("--freeze", required=True)
    complete.add_argument("--events", required=True)
    complete.add_argument("--trial-id", required=True)
    complete.add_argument("--result-file", required=True)
    complete.add_argument("--status", choices=("PASS", "FAIL", "UNKNOWN"), required=True)
    complete.add_argument("--reason")
    assess = sub.add_parser("assess")
    assess.add_argument("--needs", required=True)
    assess.add_argument("--out-dir", required=True)
    assess.add_argument("--collected", required=True)
    assess.add_argument("--v2", required=True)
    assess.add_argument("--labels", required=True)
    assess.add_argument("--out", required=True)
    return parser, assess


def main(argv=None):
    parser, _ = _cli()
    args = parser.parse_args(argv)
    if args.command == "start":
        event = record_trial_start(args.root, args.freeze, args.events)
        print(event["trial_id"])
        return 0
    if args.command == "complete":
        record_trial_complete(args.root, args.freeze, args.events, args.trial_id,
                              args.result_file, args.status, args.reason)
        print(json.dumps({"state": "TRIAL_COMPLETED", "trial_id": args.trial_id,
                          "status": args.status}, ensure_ascii=False))
        return 0
    if args.command == "gate":
        result = check_production_gate(args.root, args.freeze, args.events)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["allowed"] else 2
    try:
        needs = read_jsonl(args.needs)
        words = [row["word"] for row in needs]
        collected = read_jsonl(args.collected)
        raw = _raw_response_from_run(args.out_dir, words)
        result = evaluate_trial(words, raw, collected, read_jsonl(args.v2),
                                read_jsonl(args.labels))
        _write_unique_json(args.out, result)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print("trial assessment error: %s" % exc)
        return 3
    print("trial_criteria=%s reason=%s state_counts=%s invalid_reasons=%s" % (
        result["status"], result["reason"], json.dumps(result["state_counts"], sort_keys=True),
        json.dumps(result["invalid_reasons"], ensure_ascii=False, sort_keys=True)))
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())

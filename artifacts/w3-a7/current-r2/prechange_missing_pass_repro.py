"""Reproduce the r1 threshold formula on frozen v2 rows without starting generation."""
import json
from collections import defaultdict
from pathlib import Path

from verantyx import coarse_types as ct

ROOT = Path(__file__).resolve().parents[3]
trial_words = [json.loads(line)["word"] for line in
               (ROOT / "artifacts/w3-a7/current-r1/trial_needs_role_v3.jsonl").read_text(
                   encoding="utf-8").splitlines()]
v2_rows = [json.loads(line) for line in
           (ROOT / "artifacts/w3-a6/r9/n4_claims_run2_prefreeze.jsonl").read_text(
               encoding="utf-8").splitlines()]
v2_by_word = {row["word"]: row for row in v2_rows}
missing_word = next(word for word in trial_words
                    if v2_by_word[word].get("source_status") != "ACCEPTED"
                    and not v2_by_word[word].get("frame"))
generated_by_word = {
    word: {"word": word, "frame": v2_by_word[word].get("frame")}
    for word in trial_words if word != missing_word
}

def frame_for(row):
    frame = row.get("frame")
    return frame if isinstance(frame, dict) else {}

def has_particle(frame, particle):
    entries = frame.get(particle)
    return isinstance(entries, list) and bool(entries)

labels = defaultdict(list)
for line in (ROOT / "artifacts/w3-a6/r9/n4_visual_labels_run2.jsonl").read_text(
        encoding="utf-8").splitlines():
    row = json.loads(line)
    labels[(row["word"], row["particle"], row["role"], tuple(sorted(row["types"])))] .append(
        row["visual_label"])

def claim_keys(word, frame):
    out = []
    for particle, entries in frame.items():
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("role"), str) \
                        and isinstance(entry.get("types"), list):
                    out.append((word, particle, entry["role"], tuple(sorted(entry["types"]))))
    return out

rates = {}
for particle in ct.CASE_PARTICLES_9:
    old_n = sum(v2_by_word[word].get("source_status") == "ACCEPTED"
                and has_particle(frame_for(v2_by_word[word]), particle) for word in trial_words)
    new_n = sum(has_particle(frame_for(generated_by_word.get(word, {})), particle)
                for word in trial_words)
    rates[particle] = [old_n, new_n]

def errors_and_unclassified(rows):
    errors = unclassified = 0
    for word, row in rows.items():
        for key in claim_keys(word, frame_for(row)):
            found = labels.get(key, [])
            if len(found) != 1:
                unclassified += 1
            elif found[0] == "明らかな誤り":
                errors += 1
    return errors, unclassified

v2_errors, v2_unknown = errors_and_unclassified({
    word: v2_by_word[word] for word in trial_words
    if v2_by_word[word].get("source_status") == "ACCEPTED"})
v3_errors, v3_unknown = errors_and_unclassified(generated_by_word)
claim_pass = all(new_n >= old_n for old_n, new_n in rates.values())
labels_complete = v2_unknown == 0 and v3_unknown == 0
status = ("FAIL" if not claim_pass or (labels_complete and v3_errors > v2_errors)
          else "UNKNOWN" if not labels_complete else "PASS")
print(json.dumps({"replay": "r1_formula", "status": status, "omitted_word": missing_word,
                  "v3_generated_words": len(generated_by_word), "trial_words": len(trial_words),
                  "v2_counts_by_particle": {p: counts[0] for p, counts in rates.items()},
                  "v3_counts_by_particle": {p: counts[1] for p, counts in rates.items()},
                  "v2_errors": v2_errors, "v3_errors": v3_errors,
                  "v2_unclassified": v2_unknown, "v3_unclassified": v3_unknown},
                 ensure_ascii=False, sort_keys=True))

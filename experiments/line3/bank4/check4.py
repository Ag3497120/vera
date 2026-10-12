#!/usr/bin/env python3
"""Mechanical checks for bank4.tsv using only the requested fulllead corpus."""

import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT.parent / "S300_fulllead.jsonl"
BANK_PATH = ROOT / "bank4.tsv"
EXPECTED_KINDS = ("near-fact", "same-slot", "numeric", "entity-swap")
EXPECTED_HEADER = [
    "#id",
    "kind",
    "corpus",
    "subject",
    "question",
    "gold",
    "evidence",
    "notes",
]


def main() -> int:
    errors = []
    records = {}
    all_sentences = []
    for line_number, line in enumerate(
        CORPUS_PATH.read_text(encoding="utf-8").splitlines(), 1
    ):
        record = json.loads(line)
        title = record["title"]
        records[title] = record
        for sentence_id, sentence in enumerate(record["text"].split("。")):
            if sentence:
                all_sentences.append((title, sentence_id, sentence))

    corpus_text = "\n".join(
        f"{record['title']}\n{record['text']}" for record in records.values()
    )
    sentence_map = {
        (title, sentence_id): sentence
        for title, sentence_id, sentence in all_sentences
    }

    with BANK_PATH.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames != EXPECTED_HEADER:
            errors.append(f"header mismatch: {reader.fieldnames!r}")
        rows = list(reader)

    expected_ids = [f"ADV-{i:03d}" for i in range(1, 41)]
    ids = [row["#id"] for row in rows]
    if len(rows) != 40:
        errors.append(f"row count is {len(rows)}, expected 40")
    if len(set(ids)) != len(ids):
        errors.append("IDs are not unique")
    if ids != expected_ids:
        errors.append("IDs are not in the required ADV-001..ADV-040 order")

    kind_counts = Counter(row["kind"] for row in rows)
    for kind in EXPECTED_KINDS:
        if kind_counts[kind] != 10:
            errors.append(f"{kind} count is {kind_counts[kind]}, expected 10")
    unexpected_kinds = sorted(set(kind_counts) - set(EXPECTED_KINDS))
    if unexpected_kinds:
        errors.append(f"unexpected kinds: {unexpected_kinds}")

    subjects = [row["subject"] for row in rows]
    if len(set(subjects)) != len(subjects):
        errors.append("subjects are not unique")

    wrong_guess_occurrences = 0
    missing_wrong_guesses = []
    bad_evidence = []
    malformed_notes = []
    for row in rows:
        item_id = row["#id"]
        if row["corpus"] != "fulllead":
            errors.append(f"{item_id}: corpus is not fulllead")
        if row["gold"] != "":
            errors.append(f"{item_id}: gold is not empty")
        subject = row["subject"]
        if not subject or subject not in corpus_text:
            errors.append(f"{item_id}: subject surface is absent from corpus")

        try:
            title, raw_sentence_id = row["evidence"].rsplit("#", 1)
            sentence_id = int(raw_sentence_id)
        except (ValueError, AttributeError):
            bad_evidence.append(f"{item_id}: malformed evidence id")
            continue
        sentence = sentence_map.get((title, sentence_id))
        if sentence is None:
            bad_evidence.append(f"{item_id}: missing sentence {row['evidence']}")
        elif subject not in sentence:
            bad_evidence.append(
                f"{item_id}: evidence sentence does not contain subject {subject!r}"
            )

        match = re.search(r"(?:^|; )c\) (.+)$", row["notes"])
        if not match:
            malformed_notes.append(f"{item_id}: notes lack a final c) guess")
            continue
        wrong_guess = match.group(1)
        if wrong_guess in corpus_text:
            wrong_guess_occurrences += 1
        else:
            missing_wrong_guesses.append(f"{item_id}: {wrong_guess!r}")

    if bad_evidence:
        errors.extend(bad_evidence)
    if malformed_notes:
        errors.extend(malformed_notes)
    if missing_wrong_guesses:
        errors.extend(
            ["c) guess is not a corpus substring for:", *missing_wrong_guesses]
        )
    if wrong_guess_occurrences < 25:
        errors.append(
            f"only {wrong_guess_occurrences}/40 c) guesses occur in corpus; minimum is 25"
        )

    print("Bank 4 mechanical check")
    print(f"Corpus entries: {len(records)}")
    print(f"Items: {len(rows)}")
    print("Kinds: " + ", ".join(f"{k}={kind_counts[k]}" for k in EXPECTED_KINDS))
    print(f"Unique IDs: {len(set(ids))}/40")
    print(f"Unique subjects: {len(set(subjects))}/40")
    print(f"Subject appears in corpus: {sum(bool(s) and s in corpus_text for s in subjects)}/40")
    print(f"Evidence sentence exists and contains subject: {len(rows) - len(bad_evidence)}/40")
    print(f"c) guess occurs in corpus: {wrong_guess_occurrences}/40 (minimum 25)")
    print("Semantic answer absence and c) wrongness: not mechanically decidable")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

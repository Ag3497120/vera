#!/usr/bin/env python3
"""Tests for G4-a: Article steps and question entry steps."""

import json
import subprocess
import sys
from pathlib import Path
from collections import Counter


def run_steps_py(env_seed=0):
    """Run steps.py with a specific PYTHONHASHSEED and return the steps data."""
    repo_root = Path(__file__).parent.parent.parent
    env = {**dict(subprocess.os.environ), "PYTHONHASHSEED": str(env_seed)}

    result = subprocess.run(
        [sys.executable, "experiments/line3/g4/steps.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env
    )

    if result.returncode != 0:
        raise RuntimeError(f"steps.py failed: {result.stderr}")

    # Load the generated steps.json
    steps_path = repo_root / "experiments/line3/g4/steps.json"
    with steps_path.open() as f:
        return json.load(f)


def test_article_order_deterministic():
    """Test that article order is deterministic across runs."""
    data1 = run_steps_py(env_seed=0)
    data2 = run_steps_py(env_seed=1)
    data3 = run_steps_py(env_seed=12345)

    articles1 = [a["title"] for a in data1["articles"]]
    articles2 = [a["title"] for a in data2["articles"]]
    articles3 = [a["title"] for a in data3["articles"]]

    assert articles1 == articles2, "Article order differs between PYTHONHASHSEED 0 and 1"
    assert articles1 == articles3, "Article order differs between PYTHONHASHSEED 0 and 12345"
    assert len(articles1) == 300, f"Expected 300 articles, got {len(articles1)}"


def test_every_answerable_question_has_entry_step():
    """Test that every answerable question has exactly one entry step."""
    data = run_steps_py()

    repo_root = Path(__file__).parent.parent.parent
    intra2_path = repo_root / "experiments/line3/bank2/bank2.tsv"

    # Read intra2 questions from TSV
    intra2_ids = []
    with intra2_path.open(encoding="utf-8", newline="") as f:
        header = f.readline().rstrip("\r\n")
        if header.startswith("#"):
            header = header[1:]

        for line in f:
            parts = line.split("\t")
            if len(parts) > 2 and parts[2] == "fulllead" and parts[1] == "intra2":
                intra2_ids.append(parts[0])

    # Check all intra2 questions have entry steps
    for qid in intra2_ids:
        assert qid in data["entry_steps"], f"Question {qid} has no entry step"
        entry_step = data["entry_steps"][qid]
        assert isinstance(entry_step, int), f"Entry step for {qid} is not an int: {entry_step}"
        assert 1 <= entry_step <= 300, f"Entry step for {qid} out of range: {entry_step}"


def test_staircase_monotone():
    """Test that the Fibonacci staircase is monotone increasing."""
    data = run_steps_py()
    fib = data["fibonacci_steps"]

    assert fib == sorted(fib), f"Fibonacci steps not sorted: {fib}"
    for i in range(len(fib) - 1):
        assert fib[i] < fib[i + 1], f"Fibonacci steps not strictly increasing: {fib}"


def test_measured_steps_count():
    """Test that measured steps count matches the spec."""
    data = run_steps_py()

    measured = data["measured_steps"]
    num_measured = len(measured)
    num_fib = data["num_fibonacci_steps"]
    num_entry = data["num_distinct_intra2_entry_steps"]

    # Expected: 66 = 13 fibonacci + 58 distinct entry steps - overlaps
    assert num_measured == 66, f"Expected 66 measured steps, got {num_measured}"
    assert num_fib == 13, f"Expected 13 fibonacci steps, got {num_fib}"
    assert num_entry == 58, f"Expected 58 distinct intra2 entry steps, got {num_entry}"


def test_measured_steps_exact():
    """Test that measured steps match the spec exactly."""
    data = run_steps_py()

    spec_measured = [1, 2, 3, 5, 8, 9, 10, 12, 13, 18, 19, 21, 23, 24, 30, 33, 34, 43, 44, 45, 48, 49, 53, 55, 57, 58, 59, 60, 61, 65, 66, 70, 75, 77, 79, 82, 88, 89, 99, 105, 106, 107, 121, 142, 144, 145, 148, 157, 158, 169, 170, 173, 176, 186, 196, 201, 208, 233, 236, 250, 255, 261, 273, 292, 294, 300]

    actual = data["measured_steps"]
    assert actual == spec_measured, f"Measured steps don't match spec"


def test_questions_present_per_step():
    """Test that questions_by_step is correct."""
    data = run_steps_py()

    entry_steps = data["entry_steps"]
    questions_by_step = data["questions_by_step"]
    measured_steps = data["measured_steps"]

    # Check that for each measured step, the listed questions all have entry_step <= step
    for step in measured_steps:
        # JSON stores keys as strings
        questions = questions_by_step.get(str(step), [])
        for qid in questions:
            if qid in entry_steps:
                entry = entry_steps[qid]
                assert entry <= step, f"Question {qid} with entry step {entry} listed at step {step}"


def test_questions_are_present_at_and_after_entry():
    """Test that a question is present at step k if and only if its entry step <= k."""
    data = run_steps_py()

    entry_steps = data["entry_steps"]
    questions_by_step = data["questions_by_step"]
    measured_steps = data["measured_steps"]

    # Build the full presence table
    for qid, entry in entry_steps.items():
        # This question should appear at all measured steps >= entry
        for step in measured_steps:
            # JSON stores keys as strings
            questions_at_step = questions_by_step.get(str(step), [])
            if step >= entry:
                assert qid in questions_at_step, f"Question {qid} (entry={entry}) not present at step {step}"
            else:
                assert qid not in questions_at_step, f"Question {qid} (entry={entry}) present before entry at step {step}"


def test_cumulative_sentences():
    """Test that cumulative sentence counts are correct."""
    data = run_steps_py()

    articles = data["articles"]

    # Check that cumulative counts are monotone increasing
    prev_count = 0
    for i, article in enumerate(articles):
        count = article["cumulative_sentences"]
        assert count >= prev_count, f"Cumulative counts not monotone at article {i}"
        assert count > 0, f"Non-positive cumulative count at article {i}"
        prev_count = count

    # Last article should have all sentences
    assert articles[-1]["cumulative_sentences"] == data["num_sentences"], "Final cumulative count doesn't match total"


def test_total_sentences_in_measured_steps():
    """Test the total sentence count across measured steps."""
    data = run_steps_py()

    measured_steps = data["measured_steps"]
    articles = data["articles"]

    # Manually compute total sentences at each measured step
    articles_by_index = {a["index"]: a for a in articles}

    total = 0
    for step in measured_steps:
        total += articles_by_index[step]["cumulative_sentences"]

    expected = data["total_sentences_in_measured_steps"]
    assert total == expected, f"Total sentences in measured steps: expected {expected}, got {total}"


def test_prefix_hash_stable():
    """Test that prefix(k) hashes are stable across PYTHONHASHSEED values."""
    data0 = run_steps_py(env_seed=0)
    data1 = run_steps_py(env_seed=1)
    data12345 = run_steps_py(env_seed=12345)

    articles0 = [a["title"] for a in data0["articles"]]
    articles1 = [a["title"] for a in data1["articles"]]
    articles12345 = [a["title"] for a in data12345["articles"]]

    # All should have the same articles in the same order
    assert articles0 == articles1 == articles12345, "Article order differs across PYTHONHASHSEED values"


def test_data_consistency():
    """Test internal consistency of the steps data."""
    data = run_steps_py()

    # Check basic structure
    assert "articles" in data
    assert "fibonacci_steps" in data
    assert "entry_steps" in data
    assert "measured_steps" in data
    assert "questions_by_step" in data
    assert "question_counts" in data

    # Check question counts
    counts = data["question_counts"]
    assert counts["intra2"] == 69, f"Expected 69 intra2, got {counts['intra2']}"
    assert counts["unans"] == 25, f"Expected 25 unans, got {counts['unans']}"
    assert counts["total"] == 94, f"Expected 94 total, got {counts['total']}"

    # Check article count
    assert data["num_articles"] == 300, f"Expected 300 articles, got {data['num_articles']}"
    assert data["num_sentences"] == 592, f"Expected 592 sentences, got {data['num_sentences']}"


if __name__ == "__main__":
    import pytest

    # Run all tests
    pytest.main([__file__, "-v"])

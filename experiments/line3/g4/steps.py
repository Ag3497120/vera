#!/usr/bin/env python3
"""G4-a: Article steps and question entry steps.

Reads fulllead_sents.jsonl and bank2.tsv to emit:
- steps.json: article order, cumulative sentence counts, Fibonacci staircase,
  entry steps for each answerable question, measured steps
- steps.md: markdown table with steps, articles, sentences, questions-present count
- prefix(k) function to write first k articles as jsonl
"""

import csv
import json
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def load_fulllead_sentences() -> Tuple[List[Dict], List[str], List[int]]:
    """Load fulllead_sents.jsonl and extract articles with order and cumulative counts.

    Returns:
        (rows, article_list, cumulative_sent_counts)
        - rows: all sentence objects from jsonl
        - article_list: list of unique titles in order of first appearance
        - cumulative_sent_counts: cumulative sentence count at each article boundary
    """
    path = Path(__file__).parent.parent / "bank2" / "data" / "fulllead_sents.jsonl"
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    # Extract articles (maximal runs of equal titles)
    articles_seen = set()
    article_list = []
    current_title = None
    sent_count = 0
    cumulative_sent_counts = []

    for row in rows:
        title = row["title"]
        if title != current_title:
            # New article
            if current_title is not None:
                cumulative_sent_counts.append(sent_count)
            current_title = title
            article_list.append(title)
        sent_count += 1

    # Add final count
    cumulative_sent_counts.append(sent_count)

    return rows, article_list, cumulative_sent_counts


def load_bank2_questions() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Load bank2.tsv and separate questions by kind for fulllead corpus.

    Returns:
        (intra2_questions, unans_questions, cross2_questions)
    """
    path = Path(__file__).parent.parent / "bank2" / "bank2.tsv"
    intra2_questions = []
    unans_questions = []
    cross2_questions = []

    with path.open(encoding="utf-8", newline="") as f:
        # Read header and strip the leading '#'
        header_line = f.readline().rstrip("\r\n")
        if header_line.startswith("#"):
            header_line = header_line[1:]
        field_names = header_line.split("\t")

        # Read remaining rows
        reader = csv.DictReader(f, fieldnames=field_names, delimiter="\t")
        for row in reader:
            kind = row["kind"]
            corpus = row["corpus"]

            if kind == "intra2" and corpus == "fulllead":
                intra2_questions.append(row)
            elif kind == "unans" and corpus == "fulllead":
                unans_questions.append(row)
            elif kind == "cross2":
                cross2_questions.append(row)

    return intra2_questions, unans_questions, cross2_questions


def get_entry_step_for_question(question: Dict, article_positions: Dict[str, int]) -> int:
    """Get the entry step for a question (the article position + 1, since steps are 1-indexed).

    For intra2: evidence format is "title#index"
    For unans: evidence format is "title#0" or "title"
    """
    evidence = question["evidence"]
    if "#" in evidence:
        title = evidence.rsplit("#", 1)[0]
    else:
        title = evidence

    if title in article_positions:
        return article_positions[title] + 1  # Convert to 1-indexed step
    else:
        raise ValueError(f"Title {title} not found in article positions")


def create_steps_json(
    article_list: List[str],
    cumulative_sent_counts: List[int],
    intra2_questions: List[Dict],
    unans_questions: List[Dict],
) -> Dict:
    """Create the steps.json data structure."""

    # Create mapping from article title to its position (0-indexed)
    article_positions = {title: i for i, title in enumerate(article_list)}

    # Fibonacci staircase steps (1-indexed)
    fib_steps = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 300]
    # Adjust for actual number of articles
    num_articles = len(article_list)
    if num_articles < 300:
        fib_steps = [s for s in fib_steps if s <= num_articles]
        if num_articles not in fib_steps:
            fib_steps.append(num_articles)
        fib_steps.sort()

    # Compute entry steps for all questions
    intra2_entry_steps = set()
    question_entry_steps = {}

    # intra2 questions - these are the "answerable" questions
    # Measured steps = union of fibonacci and intra2 entry steps only
    for q in intra2_questions:
        entry_step = get_entry_step_for_question(q, article_positions)
        intra2_entry_steps.add(entry_step)
        question_entry_steps[q["id"]] = entry_step

    # unans questions - track them but don't include in measured steps
    for q in unans_questions:
        entry_step = get_entry_step_for_question(q, article_positions)
        question_entry_steps[q["id"]] = entry_step

    # Measured steps = union of fibonacci and intra2 entry steps only
    # (unans questions are not answerable, so they don't contribute to measured steps)
    measured_steps = sorted(set(fib_steps) | intra2_entry_steps)

    # Build the output structure
    articles_with_counts = []
    for i, title in enumerate(article_list):
        sent_count = cumulative_sent_counts[i]
        articles_with_counts.append({
            "index": i + 1,  # 1-indexed
            "title": title,
            "cumulative_sentences": sent_count
        })

    # For each measured step, find questions that are present (their entry step <= measured step)
    # Include both intra2 and unans questions that are present at each step
    questions_by_step = defaultdict(list)

    for q in intra2_questions:
        entry_step = question_entry_steps[q["id"]]
        for step in measured_steps:
            if step >= entry_step:
                questions_by_step[step].append(q["id"])

    for q in unans_questions:
        entry_step = question_entry_steps[q["id"]]
        for step in measured_steps:
            if step >= entry_step:
                questions_by_step[step].append(q["id"])

    # Count distinct entry steps from intra2 only
    distinct_intra2_entry_steps = len(intra2_entry_steps)

    return {
        "num_articles": num_articles,
        "num_sentences": cumulative_sent_counts[-1],
        "articles": articles_with_counts,
        "fibonacci_steps": fib_steps,
        "entry_steps": {q["id"]: question_entry_steps[q["id"]] for q in intra2_questions + unans_questions},
        "measured_steps": measured_steps,
        "num_measured_steps": len(measured_steps),
        "num_fibonacci_steps": len(fib_steps),
        "num_distinct_intra2_entry_steps": distinct_intra2_entry_steps,
        "questions_by_step": {step: sorted(questions_by_step[step]) for step in measured_steps},
        "total_sentences_in_measured_steps": sum(cumulative_sent_counts[s-1] for s in measured_steps),
        "question_counts": {
            "intra2": len(intra2_questions),
            "unans": len(unans_questions),
            "total": len(intra2_questions) + len(unans_questions)
        }
    }


def save_steps_json(steps_data: Dict, output_path: Path) -> None:
    """Save steps data to JSON file."""
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(steps_data, f, ensure_ascii=False, indent=2)


def save_steps_markdown(steps_data: Dict, output_path: Path) -> None:
    """Save steps data to markdown table."""
    with output_path.open("w", encoding="utf-8") as f:
        f.write("# G4-a Steps and Questions\n\n")
        f.write("## Summary\n")
        f.write(f"- Total articles: {steps_data['num_articles']}\n")
        f.write(f"- Total sentences: {steps_data['num_sentences']}\n")
        f.write(f"- Fibonacci steps: {steps_data['num_fibonacci_steps']}\n")
        f.write(f"- Distinct intra2 entry steps: {steps_data['num_distinct_intra2_entry_steps']}\n")
        f.write(f"- Measured steps total: {steps_data['num_measured_steps']}\n")
        f.write(f"- Total sentences in measured steps: {steps_data['total_sentences_in_measured_steps']}\n")
        f.write(f"\n")
        f.write(f"## Questions\n")
        f.write(f"- Intra2: {steps_data['question_counts']['intra2']}\n")
        f.write(f"- Unans: {steps_data['question_counts']['unans']}\n")
        f.write(f"- Total: {steps_data['question_counts']['total']}\n")
        f.write(f"\n")

        f.write("## Measured Steps Table\n\n")
        f.write("| Step | Article Title | Cumulative Sentences | Questions Present |\n")
        f.write("|---|---|---|---|\n")

        articles_by_step = {i + 1: article for i, article in enumerate(steps_data["articles"])}

        for step in steps_data["measured_steps"]:
            article = articles_by_step[step]
            questions_present = steps_data["questions_by_step"].get(step, [])
            f.write(f"| {step} | {article['title']} | {article['cumulative_sentences']} | {len(questions_present)} |\n")


def create_prefix_writer(rows: List[Dict], article_list: List[str], article_positions: Dict[str, int]):
    """Create a function that writes prefixes of articles to jsonl files.

    Returns a function prefix(k) that writes the first k articles to a jsonl file
    and returns its sha256 hash and content.
    """
    def prefix(k: int) -> Tuple[str, bytes]:
        """Write first k articles as jsonl and return (sha256, content)."""
        if k <= 0:
            return hashlib.sha256(b"").hexdigest(), b""

        # Get the titles of the first k articles
        target_titles = set(article_list[:k])

        # Filter rows that belong to the first k articles
        prefix_rows = [row for row in rows if row["title"] in target_titles]

        # Convert to jsonl bytes
        content = b""
        for row in prefix_rows:
            line = json.dumps(row, ensure_ascii=False) + "\n"
            content += line.encode("utf-8")

        # Compute SHA256
        sha = hashlib.sha256(content).hexdigest()
        return sha, content

    return prefix


def main():
    # Load data
    rows, article_list, cumulative_sent_counts = load_fulllead_sentences()
    intra2_questions, unans_questions, cross2_questions = load_bank2_questions()

    print(f"Loaded {len(article_list)} articles with {len(rows)} sentences")
    print(f"Intra2: {len(intra2_questions)}, Unans: {len(unans_questions)}, Cross2: {len(cross2_questions)}")

    # Create steps data
    steps_data = create_steps_json(article_list, cumulative_sent_counts, intra2_questions, unans_questions)

    print(f"\nMeasured steps: {steps_data['num_measured_steps']}")
    print(f"Fibonacci steps: {steps_data['num_fibonacci_steps']}")
    print(f"Distinct intra2 entry steps: {steps_data['num_distinct_intra2_entry_steps']}")
    print(f"Expected: 66 = 13 + 58")
    print(f"Actual: {steps_data['num_measured_steps']} = {steps_data['num_fibonacci_steps']} + {steps_data['num_distinct_intra2_entry_steps']} - overlaps")

    # Save outputs
    g4_dir = Path(__file__).parent
    json_path = g4_dir / "steps.json"
    md_path = g4_dir / "steps.md"

    save_steps_json(steps_data, json_path)
    print(f"\nSaved {json_path}")

    save_steps_markdown(steps_data, md_path)
    print(f"Saved {md_path}")

    # Create and test the prefix writer
    article_positions = {title: i for i, title in enumerate(article_list)}
    prefix = create_prefix_writer(rows, article_list, article_positions)

    # Write a sample prefix file
    prefix_dir = g4_dir / "prefixes"
    prefix_dir.mkdir(exist_ok=True)

    sha, content = prefix(300)
    print(f"\nPrefix(300) SHA256: {sha}")
    print(f"Prefix(300) size: {len(content)} bytes")

    return steps_data, prefix


if __name__ == "__main__":
    steps_data, prefix = main()

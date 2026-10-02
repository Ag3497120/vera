#!/usr/bin/env python3
"""Run the real-question conductor experiment and write its dated report."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")

from verantyx import conductor, project_frame  # noqa: E402
from verantyx.memory_frame import Memory  # noqa: E402


REPORT_PATH = ROOT / "docs" / "REAL_QUESTIONS_2026-10-02.md"
FRAME_PATH = ROOT / "docs" / "frames" / "vera_project_frame.md"
POLICY_KINDS = frozenset(("CHOICE", "CONFIRM", "SCOPE"))


@dataclass
class EvaluatedRow:
    number: int
    source: dict[str, Any]
    kind: str
    history_count: int
    baseline: conductor.Reply
    accumulated: conductor.Reply
    growth: Optional[conductor.Reply] = None
    growth_note: Optional[str] = None
    history_rejections: int = 0

    @property
    def row_id(self) -> str:
        return f"R{self.number:03d}"

    @property
    def answer(self) -> Optional[str]:
        value = self.source.get("human_answer")
        return value if isinstance(value, str) and value != "" else None

    @property
    def exact_option_answer(self) -> bool:
        return self.answer is not None and self.answer in self.source.get("options", [])


def always_abstain(_prompt: str) -> None:
    """Fake closed-choice asker: no model call and no option is ever selected."""
    return None


def read_rows(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"question row {line_number} is not an object")
            if not isinstance(row.get("question"), str) or not row["question"].strip():
                raise ValueError(f"question row {line_number} has no nonempty question")
            options = row.get("options")
            if not isinstance(options, list) or not all(isinstance(x, str) for x in options):
                raise ValueError(f"question row {line_number} has a malformed option list")
            if row.get("human_answer") is not None and not isinstance(row["human_answer"], str):
                raise ValueError(f"question row {line_number} has a non-text human answer")
            rows.append(row)
    return rows


def _write_decision(
    frame: conductor.ProjectFrame,
    subject: str,
    choice: str,
    *,
    source_row: str,
    role: str,
) -> Optional[dict[str, Any]]:
    # Keep source provenance in both the subject and the accepted frame
    # witness. The memory writer still applies its normal typed-text checks.
    try:
        source_line = int(source_row[1:4])
        return frame.memory.write(
            "DECISION",
            "frame author",
            witness={
                "kind": "testimony",
                "by": "frame author",
                "source": "VERA_REAL_QUESTIONS",
                "line": source_line,
                "section": "decisions",
                "entry": f"{role} {source_row}",
            },
            subject=f"{role} {source_row} {subject}",
            choice=choice,
        )
    except conductor.WriteRejected:
        return None


def _write_policy(
    frame: conductor.ProjectFrame,
    question_kind: str,
    condition: str,
    answer: str,
    authority_id: str,
    *,
    source_row: str,
) -> Optional[dict[str, Any]]:
    del source_row  # The cited authority decision carries the input row ID.
    try:
        return frame.add_policy(question_kind, condition, answer, authority_id)
    except conductor.WriteRejected:
        return None


def _row_id(index: int) -> str:
    return f"R{index + 1:03d}"


def _session(row: dict[str, Any]) -> str:
    value = row.get("session")
    return str(value) if value is not None else "<missing-session>"


def _question(row: dict[str, Any], index: int) -> conductor.AgentQuestion:
    return conductor.AgentQuestion(
        id=_row_id(index),
        text=row["question"],
        options=row["options"],
    )


def _seed_prior_answers(
    frame: conductor.ProjectFrame,
    rows: list[dict[str, Any]],
    prior_indices: list[int],
) -> int:
    """Add only earlier same-session testimony and its observed option terms."""
    rejected = 0
    for prior_index in prior_indices:
        row = rows[prior_index]
        answer = row.get("human_answer")
        if not isinstance(answer, str) or not answer:
            continue
        source_row = _row_id(prior_index)
        kind = conductor.classify_question(row["question"], row["options"])
        authority = _write_decision(
            frame,
            f"recorded human answer {source_row}",
            answer,
            source_row=source_row,
            role="human answer",
        )
        if authority is None:
            rejected += 1
        elif kind in POLICY_KINDS:
            policy = _write_policy(
                frame,
                kind,
                row["question"],
                answer,
                authority["id"],
                source_row=source_row,
            )
            if policy is None:
                rejected += 1
        # Candidate labels are observations from the earlier question's closed
        # list; the only selected value comes from its recorded human answer.
        for option_index, option in enumerate(row["options"], 1):
            record = _write_decision(
                frame,
                f"observed option {source_row} {option_index}",
                option,
                source_row=source_row,
                role="option label",
            )
            if record is None:
                rejected += 1
    return rejected


def _outcome(reply: conductor.Reply, human_answer: str) -> str:
    if reply.kind != "ANSWER":
        return "ESCALATED"
    return "AGREED" if reply.answer == human_answer else "WRONG"


def _evaluate(rows: list[dict[str, Any]], frame_spec: Any) -> list[EvaluatedRow]:
    evaluated: list[EvaluatedRow] = []
    with tempfile.TemporaryDirectory(prefix="real-questions-eval-") as scratch:
        for index, row in enumerate(rows):
            prior_indices = [
                earlier
                for earlier in range(index)
                if _session(rows[earlier]) == _session(row)
                and isinstance(rows[earlier].get("human_answer"), str)
                and rows[earlier]["human_answer"] != ""
            ]
            log_path = Path(scratch) / f"memory-{index:03d}.jsonl"
            memory = Memory(str(log_path), asker=always_abstain)
            compiled = project_frame.compile_frame(frame_spec, memory)
            question = _question(row, index)
            baseline = compiled.conductor.answer(question)
            history_rejections = _seed_prior_answers(compiled.conductor, rows, prior_indices)
            accumulated = compiled.conductor.answer(question)
            result = EvaluatedRow(
                number=index + 1,
                source=row,
                kind=conductor.classify_question(row["question"], row["options"]),
                history_count=len(prior_indices),
                baseline=baseline,
                accumulated=accumulated,
                history_rejections=history_rejections,
            )

            if result.answer is not None and result.exact_option_answer and accumulated.kind != "ANSWER":
                answer = result.answer
                authority = _write_decision(
                    compiled.conductor,
                    f"counterfactual human answer {result.row_id}",
                    answer,
                    source_row=result.row_id,
                    role="human answer for growth estimate",
                )
                if authority is None:
                    result.growth_note = "the typed DECISION writer rejected the recorded answer"
                if result.kind == "CHOICE":
                    for option_index, option in enumerate(row["options"], 1):
                        candidate_record = _write_decision(
                            compiled.conductor,
                            f"counterfactual option {result.row_id} {option_index}",
                            option,
                            source_row=result.row_id,
                            role="option label for growth estimate",
                        )
                        if candidate_record is None and result.growth_note is None:
                            result.growth_note = "one or more option labels were rejected by the typed DECISION writer"
                if authority is not None and result.kind in POLICY_KINDS:
                    policy = _write_policy(
                        compiled.conductor,
                        result.kind,
                        row["question"],
                        answer,
                        authority["id"],
                        source_row=result.row_id,
                    )
                    if policy is None:
                        result.growth_note = "the typed POLICY writer rejected the question condition or answer"
                    else:
                        result.growth = compiled.conductor.answer(question)
                elif result.kind not in POLICY_KINDS:
                    result.growth_note = "this question kind has no generic POLICY answer path"
            evaluated.append(result)
    return evaluated


def _metrics(rows: list[EvaluatedRow], attr: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row.answer is not None:
            counts[_outcome(getattr(row, attr), row.answer)] += 1
    return counts


def _md(value: Any, limit: int = 96) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text or "—"


def _reply_cell(reply: conductor.Reply) -> str:
    if reply.kind == "ANSWER":
        return f"ANSWER: {_md(reply.answer)}"
    if reply.kind == "ASK_VERIFIER":
        return f"ASK_VERIFIER: {_md(reply.missing)}"
    return f"ESCALATE: {_md(reply.missing)}"


def _trace_cell(reply: conductor.Reply) -> str:
    return _md(reply.why or reply.reason or reply.missing or reply.kind, 130)


def _worked_examples(
    report: list[str],
    heading: str,
    source_rows: list[EvaluatedRow],
    attr: str,
    status: str,
    *,
    needs_answer: bool,
) -> None:
    matching: list[EvaluatedRow] = []
    for row in source_rows:
        reply = getattr(row, attr)
        if needs_answer and row.answer is None:
            continue
        if needs_answer:
            actual = _outcome(reply, row.answer or "")
        else:
            actual = "ESCALATED" if reply.kind != "ANSWER" else "ANSWERED"
        if actual == status:
            matching.append(row)
    sample = matching[:10]
    report.extend((f"### {heading}", "", f"Available: {len(matching)}; shown: {len(sample)}.", ""))
    if not sample:
        report.append("No rows in this category; an example cannot be supplied without inventing one.")
        report.append("")
        return
    report.extend((
        "| Row | Kind | Earlier same-session answers | Human answer | Conductor reply | Trace |",
        "|---|---|---:|---|---|---|",
    ))
    for row in sample:
        human = _md(row.answer) if row.answer is not None else "unknown"
        report.append(
            f"| {row.row_id} | {row.kind} | {row.history_count} | {human} | "
            f"{_reply_cell(getattr(row, attr))} | {_trace_cell(getattr(row, attr))} |"
        )
    report.append("")


def _build_report(rows: list[dict[str, Any]], evaluated: list[EvaluatedRow]) -> str:
    total = len(rows)
    kinds = Counter(row.kind for row in evaluated)
    known = [row for row in evaluated if row.answer is not None]
    exact = [row for row in evaluated if row.exact_option_answer]
    other_rows = [row for row in evaluated if row.kind == "OTHER"]
    baseline_all = _metrics(known, "baseline")
    accumulated_all = _metrics(known, "accumulated")
    baseline_exact = _metrics(exact, "baseline")
    accumulated_exact = _metrics(exact, "accumulated")
    growth_attempted = [row for row in exact if row.accumulated.kind != "ANSWER"]
    growth_fixed = [
        row for row in growth_attempted
        if row.growth is not None and row.growth.kind == "ANSWER" and row.growth.answer == row.answer
    ]
    growth_unfixed = [row for row in growth_attempted if row not in growth_fixed]
    rejected_history_writes = sum(row.history_rejections for row in evaluated)

    lines: list[str] = [
        "# Real Agent Question Evaluation — 2026-10-02",
        "",
        "## Method",
        "",
        "The evaluator reads `$VERA_REAL_QUESTIONS`, classifies each question with `conductor.classify_question`, and runs the conductor against the compiled Vera frame. It also attempts to build a second, session-specific frame from only earlier rows in the same session and file order. Earlier human answers and option labels are passed through the typed frame writers; rejected entries are omitted. For accepted CHOICE, CONFIRM, or SCOPE answer rows, it attempts a question-specific policy. The current row and all later rows are excluded from its accumulated frame.",
        "",
        "The closed-choice asker is a fake that always returns `None`; no model or network call is made. Scoring uses exact string equality. `WRONG` means the conductor returned an answer different from the recorded human answer; every non-ANSWER reply is counted as `ESCALATED`. The 72 known-answer rows are reported, with the 27 exact option-label answers shown separately.",
        "",
        "Question text is not reproduced in this report. Row IDs refer to one-based input order. The accumulated-frame outcome is the primary leave-one-out result; Vera-only results are the baseline.",
        "",
        f"The typed frame writer rejected {rejected_history_writes} prior-record write attempts across per-row frames. These are repeated attempts to encode the same source rows for different target rows, not unique rejected rows. Rejected text was left out rather than normalized or forced into a record.",
        "",
        "## Question-kind distribution",
        "",
        "| Kind | Count | Share |",
        "|---|---:|---:|",
    ]
    for kind in conductor.QUESTION_KINDS:
        count = kinds[kind]
        lines.append(f"| {kind} | {count} | {count / total:.1%} |")
    other_rate = kinds["OTHER"] / total if total else 0.0
    lines.extend((
        "",
        f"`OTHER` / unclassified rate: **{kinds['OTHER']}/{total} ({other_rate:.1%})**.",
        "",
        "Ten concrete unclassified rows (question text omitted):",
        "",
        "| Row | Session | Kind | Human answer recorded? |",
        "|---|---|---|---|",
    ))
    for row in other_rows[:10]:
        answer_flag = "yes" if row.answer is not None else "no"
        lines.append(f"| {row.row_id} | {_md(_session(row.source), 24)} | OTHER | {answer_flag} |")

    lines.extend((
        "",
        "## Exact-answer outcomes",
        "",
        "| Population | Frame | Agreed | Wrong | Escalated |",
        "|---|---|---:|---:|---:|",
        f"| {len(known)} recorded human answers | Vera frame | {baseline_all['AGREED']} | {baseline_all['WRONG']} | {baseline_all['ESCALATED']} |",
        f"| {len(known)} recorded human answers | Vera + prior same-session frame | {accumulated_all['AGREED']} | {accumulated_all['WRONG']} | {accumulated_all['ESCALATED']} |",
        f"| {len(exact)} exact option-label answers | Vera frame | {baseline_exact['AGREED']} | {baseline_exact['WRONG']} | {baseline_exact['ESCALATED']} |",
        f"| {len(exact)} exact option-label answers | Vera + prior same-session frame | {accumulated_exact['AGREED']} | {accumulated_exact['WRONG']} | {accumulated_exact['ESCALATED']} |",
        "",
        "The row totals use the unnormalized answer strings as stored. `AGREED + WRONG + ESCALATED` equals the population size in each row.",
        "",
        "## Worked examples",
        "",
        "Examples below are calculated traces, not additional evaluation cases. Agreement and disagreement use the accumulated leave-one-out frame and only rows with a recorded human answer. Escalation examples may also use rows whose human answer is unknown.",
        "",
    ))

    _worked_examples(lines, "Agreed", known, "accumulated", "AGREED", needs_answer=True)
    _worked_examples(lines, "Disagreed (wrong answer)", known, "accumulated", "WRONG", needs_answer=True)
    _worked_examples(lines, "Escalated", evaluated, "accumulated", "ESCALATED", needs_answer=False)

    lines.extend((
        "## Frame-growth estimate",
        "",
        f"On the {len(exact)} exact option-label rows, {len(growth_attempted)} accumulated-frame escalations were considered for a counterfactual addition of that row's recorded human choice. The simulation uses a typed DECISION, a POLICY only if its exact question condition passes the frame writer, and current option labels as question-sourced vocabulary for CHOICE. Added records are not part of the scored leave-one-out result; invalid records are not forced.",
        "",
        f"Correctly fixed in that simulation: **{len(growth_fixed)}**. The human choice and required records are listed below.",
        "",
        "| Row | Kind | Human decision to record | Counterfactual result |",
        "|---|---|---|---|",
    ))
    for row in growth_fixed:
        policy_desc = "DECISION + exact-condition POLICY"
        if row.kind == "CHOICE":
            policy_desc += " + option vocabulary"
        lines.append(
            f"| {row.row_id} | {row.kind} | {_md(row.answer)} ({policy_desc}) | "
            f"{_reply_cell(row.growth or row.accumulated)} |"
        )
    if not growth_fixed:
        lines.append("| — | — | No escalation in this set was fixed by the supported frame addition. | — |")
    lines.extend((
        "",
        f"Not fixed by that frame addition: **{len(growth_unfixed)}** escalated exact-label rows. Rows classified OTHER, ORDER, or STATUS cannot be made answerable by a generic POLICY; supported policy rows can still fail because the typed writer rejects the question condition or answer, because option mapping remains unresolved, or because an existing record conflicts. This experiment did not alter those gates.",
        "",
        "",
        "| Unfixed row | Kind | Why the counterfactual did not yield a correct answer |",
        "|---|---|---|",
    ))
    for row in growth_unfixed:
        note = row.growth_note or _trace_cell(row.growth or row.accumulated)
        lines.append(f"| {row.row_id} | {row.kind} | {_md(note, 130)} |")
    if not growth_unfixed:
        lines.append("| — | — | All considered escalations were fixed in the simulation. |")
    lines.extend((
        "",
        "## Limits",
        "",
        "The accumulated frame is deliberately narrow: it uses earlier answers from the same session only, in source-file order. It does not merge decisions across project sessions, infer unstated policies, repair the classifier, or tune conductor behavior to this set. Frame growth is a counterfactual estimate for exact option-label answers, not a production update.",
        "",
    ))
    return "\n".join(lines)


def _demo_assertions() -> None:
    """Exercise a constructed, known-answer frame before scoring real rows."""
    assert conductor.classify_question("Which basic structure should we choose?", ["stereo cross", "fallback path"]) == "CHOICE"
    with tempfile.TemporaryDirectory(prefix="real-questions-demo-") as scratch:
        memory = Memory(str(Path(scratch) / "demo.jsonl"), asker=always_abstain)
        frame = conductor.ProjectFrame(memory)
        authority = frame.add_decision("demo policy authority", "choose stereo cross")
        frame.add_decision("demo option one", "stereo cross")
        frame.add_decision("demo option two", "fallback path")
        frame.add_policy("CHOICE", "basic structure", "stereo cross", authority["id"])
        reply = frame.answer(
            conductor.AgentQuestion(
                "constructed-demo",
                "Which basic structure should we choose?",
                ["stereo cross", "fallback path"],
            )
        )
        assert reply.kind == "ANSWER"
        assert reply.answer == "stereo cross"
        assert reply.record_ids


def main() -> None:
    _demo_assertions()
    data_path = os.environ.get("VERA_REAL_QUESTIONS")
    if not data_path:
        raise RuntimeError("VERA_REAL_QUESTIONS is not set")
    rows = read_rows(data_path)
    known_count = sum(isinstance(row.get("human_answer"), str) and bool(row["human_answer"]) for row in rows)
    exact_count = sum(
        isinstance(row.get("human_answer"), str)
        and bool(row["human_answer"])
        and row["human_answer"] in row["options"]
        for row in rows
    )
    # These are data-integrity golds supplied by the experiment definition.
    assert len(rows) == 130
    assert known_count == 72
    assert exact_count == 27

    frame_spec = project_frame.load_frame(FRAME_PATH)
    evaluated = _evaluate(rows, frame_spec)
    report = _build_report(rows, evaluated)
    REPORT_PATH.write_text(report, encoding="utf-8")

    scored = _metrics(evaluated, "accumulated")
    print(f"Rows: {len(rows)}; recorded human answers: {known_count}; exact option labels: {exact_count}.")
    print(f"Accumulated-frame exact outcomes: agreed {scored['AGREED']}, wrong {scored['WRONG']}, escalated {scored['ESCALATED']}.")
    print("DEMO OK")


if __name__ == "__main__":
    main()

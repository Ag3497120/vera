"""Exercise human-exchange decisions and their leave-one-out exact matches."""
from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path
from typing import Any

from verantyx.memory_frame import Memory
from verantyx.project_frame import DecisionDraft, Refusal, decision_from_exchange


class _EvaluationMemory(Memory):
    """Use the real typed writer while keeping this demo's event log in memory."""

    def __init__(self) -> None:
        self.path = Path("<decision-writer-demo-memory>")
        self.now = lambda: "1970-01-01T00:00:00"
        self.resolver = None
        self.records = {}
        self.superseded = {}
        self.aliases = {}
        self._view = None

    def _append(self, event: dict[str, Any]) -> None:
        self._apply(event)


def _load_real_questions() -> list[dict[str, Any]]:
    source = os.environ.get("VERA_REAL_QUESTIONS")
    if not source:
        raise RuntimeError("VERA_REAL_QUESTIONS is not set")
    rows: list[dict[str, Any]] = []
    with Path(source).open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"question row {line_no} is not an object")
            rows.append(row)
    return rows


def _expected_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _gold_assertions() -> None:
    question = "Webアプリケーションをどこから配布しますか？"
    options = ["Ａのみ", "公開する"]
    answer = "Aのみ"
    option = decision_from_exchange(question, options, answer, session="gold", row=1)
    assert isinstance(option, DecisionDraft)
    assert option.subject == "Webアプリケーション"
    assert option.attribute == "配布元"
    assert option.value == answer
    assert option.matched_option == "Ａのみ"
    assert option.option_index == 0
    assert option.normalized_key == "aのみ"
    assert option.record["kind"] == "DECISION"
    assert Memory.askable(option.record["sentence"], option.record["slots"], "DECISION")
    assert option.record["witness"]["session"] == "gold"
    assert option.record["witness"]["row"] == 1
    assert option.record["witness"]["who_decided"] == "human"

    raw_free_text = "先に担当者が確認し、その後ローカルへ保存する"
    free = decision_from_exchange("この保存方法をどう決めますか？", [], raw_free_text,
                                  session="gold", row=2)
    assert isinstance(free, DecisionDraft)
    assert free.matched_option is None
    assert free.value == raw_free_text
    assert free.normalized_key == _expected_key(raw_free_text)
    assert free.record["witness"]["value"] == raw_free_text
    assert Memory.askable(free.record["sentence"], free.record["slots"], "DECISION")

    later = decision_from_exchange(question, options, answer, session="gold", row=3)
    other_question = decision_from_exchange("Webアプリケーションをどこへ配布しますか？",
                                            options, answer, session="gold", row=4)
    assert isinstance(later, DecisionDraft)
    assert isinstance(other_question, DecisionDraft)
    assert option.match_key == later.match_key
    assert option.match_key != other_question.match_key

    assert isinstance(decision_from_exchange(question, options, "unknown"), Refusal)
    assert isinstance(decision_from_exchange(question, options,
                                             "[User dismissed — do not proceed, wait for next instruction]"), Refusal)


def _evaluate(rows: list[dict[str, Any]]) -> tuple[int, int, int, int, int, int, int]:
    # Leave-one-out: score a row against earlier rows only, then add its decision.
    earlier: dict[tuple[Any, ...], list[DecisionDraft]] = {}
    memory = _EvaluationMemory()
    askable = 0
    answer_strings = 0
    refusals = 0
    exact_matches = 0
    correct_matches = 0
    wrong_matches = 0
    wrong_key_answers = 0

    for row_no, row in enumerate(rows, 1):
        question = row.get("question")
        options = row.get("options")
        human_answer = row.get("human_answer")
        session = row.get("session")
        if isinstance(human_answer, str) and human_answer.strip():
            answer_strings += 1
        result = decision_from_exchange(question, options, human_answer,
                                        session=session, row=row_no, who_decided="human",
                                        memory=memory)
        if isinstance(result, Refusal):
            if isinstance(human_answer, str) and human_answer.strip():
                refusals += 1
            continue

        askable += 1
        assert result.record["kind"] == "DECISION"
        assert Memory.askable(result.record["sentence"], result.record["slots"], "DECISION")
        provenance = result.record["witness"]
        assert provenance["session"] == session
        assert provenance["row"] == row_no
        assert provenance["who_decided"] == "human"

        candidates = earlier.get(result.match_key, [])
        if candidates:
            source = candidates[-1]
            exact_key_matches = (source.match_key == result.match_key and
                                 source.session == result.session and
                                 source.row is not None and result.row is not None and
                                 source.row < result.row)
            if not exact_key_matches:
                # A prediction without an exact subject, attribute, option-set,
                # and session key is unsafe and fails the acceptance condition.
                wrong_key_answers += 1
            else:
                exact_matches += 1
                if source.normalized_key == result.normalized_key:
                    correct_matches += 1
                else:
                    wrong_matches += 1

        earlier.setdefault(result.match_key, []).append(result)

    assert len(memory.records) == askable
    return (askable, answer_strings, refusals, exact_matches, correct_matches,
            wrong_matches, wrong_key_answers)


def main() -> None:
    _gold_assertions()
    rows = _load_real_questions()
    assert len(rows) == 130, f"expected the documented 130 real questions, got {len(rows)}"
    (askable, answer_strings, refusals, exact_matches, correct_matches,
     wrong_matches, wrong_key_answers) = _evaluate(rows)
    rate = askable / len(rows)
    print(f"Askable records: {askable}/{len(rows)} exchanges ({rate:.1%})")
    print(f"Recorded answer strings: {answer_strings}; typed refusals: {refusals}")
    print(f"Later exact-record matches: {correct_matches}/{exact_matches} correct; {wrong_matches} wrong")
    print(f"Wrong answers from nonmatching keys: {wrong_key_answers}")

    assert rate >= 0.50, f"askable rate {rate:.1%} is below 50%"
    assert wrong_key_answers == 0, "a record answered a question without an exact matching key"
    print("DEMO OK")


if __name__ == "__main__":
    main()

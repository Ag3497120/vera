"""Deterministic offline demonstration for the case-frame construction."""
from __future__ import annotations

import random

from tools.build_case_frames import build_counts
from verantyx.constructions import case_frames
from verantyx.semantic_reader import document_view


def _training_sample() -> list[str]:
    places = (
        "太郎は学校で講演した。",
        "花子は学校で講演した。",
        "太郎は東京で講演した。",
        "佐藤は公園で講演した。",
        "子どもは庭で講演した。",
    )
    # Repeated independent records contribute counts, never stored sentences.
    return [*places, *places[:3], "太郎は電話で講演した。", "花子は電車で講演した。"]


def _view(sentence: str, label: str):
    return document_view({label: sentence}, family="case_frame_demo")


def _score_gold(examples, table, seed: int) -> dict[str, int]:
    ordered = list(examples)
    random.Random(seed).shuffle(ordered)
    metrics = {"correct": 0, "wrong_other": 0, "wrong_overlap": 0, "abstain": 0}
    with case_frames.using_counts(table):
        for index, (sentence, phrase, gold_role) in enumerate(ordered):
            view = _view(sentence, f"gold_{seed}_{index}")
            matching = [clause for clause in view.clauses
                        if clause.predicate == "講演する"
                        and clause.rule in ("frame", "case_frames")]
            roles = [role for clause in matching for role in clause.roles
                     if role.span.text == phrase]
            if not roles or roles[-1].name == "ambiguous":
                metrics["abstain"] += 1
            elif roles[-1].name == gold_role and str(roles[-1].term) == phrase:
                metrics["correct"] += 1
            elif roles[-1].name == gold_role:
                metrics["wrong_overlap"] += 1
            else:
                metrics["wrong_other"] += 1
            if matching:
                for clause in matching:
                    if clause.rule == "case_frames":
                        assert case_frames.licenses(clause, sentence)
    return metrics


def main() -> None:
    sample = _training_sample()
    first = build_counts(sample)
    second = build_counts(sample)
    assert first == second
    assert first["frames"]["講演する"]["で"] == {"means": 2, "place": 8}

    counts = first["frames"]
    assert case_frames._choice("未知の述語", "で", counts, 8, 0.8) is None
    # The 2-count minority never defeats the 8-count clear majority.
    assert case_frames._choice("講演する", "で", counts, 8, 0.8) == "place"
    minority_table = {"講演する": {"で": {"place": 5, "means": 4}}}
    assert case_frames._choice("講演する", "で", minority_table, 8, 0.8) is None

    with case_frames.using_counts(counts):
        unseen = _view("太郎は大学で修行した。", "unseen_case_frame")
    native = [clause for clause in unseen.clauses
              if clause.rule == "frame" and clause.predicate == "修行する"]
    assert native
    assert any(role.name == "ambiguous" and role.span.text == "大学"
               for clause in native for role in clause.roles)
    assert any("ambiguous case role: で" in clause.unsupported for clause in native)

    # Small authored gold set: source phrases and role labels are independent
    # of the reader output and contain no external corpus examples.
    gold = (
        ("太郎は大学で講演した。", "大学", "place"),
        ("花子は会場で講演した。", "会場", "place"),
        ("佐藤は劇場で講演した。", "劇場", "place"),
    )
    for seed in (7, 101):
        baseline = _score_gold(gold, {}, seed)
        measured = _score_gold(gold, counts, seed)
        assert measured["correct"] > baseline["correct"]
        assert measured["wrong_other"] <= baseline["wrong_other"]
        assert measured["wrong_overlap"] <= baseline["wrong_overlap"]

    print("DEMO OK")


if __name__ == "__main__":
    main()


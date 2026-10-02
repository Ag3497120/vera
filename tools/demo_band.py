"""Constructed semantic answers demonstrate that the band cannot vote."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

from verantyx.semantic import answer
from verantyx.semantic_band import band
from verantyx.semantic_reader import document_view, read_request


def _primary(result):
    """Fields that the annotation must leave alone."""
    return {
        key: result.get(key)
        for key in ("kind", "verdict", "text", "answer_values", "proof", "evidence", "sources", "semantic")
    }


def _beside(result, annotation):
    """Model attaching a returned annotation beside the primary result."""
    annotated = deepcopy(result)
    if annotation is not None:
        annotated.setdefault("annotations", {})["agreement_band"] = asdict(annotation)
    return annotated


def main():
    # Gold is the explicit subject/value pairing used to construct the source.
    gold = tuple((f"対象{i:02d}", f"値{i:02d}") for i in range(32))
    source = "\n".join(f"{subject}は{value}にある。" for subject, value in gold)
    view = document_view({"constructed-source": source})
    assert len(view.clauses) == len(gold)

    checked = 0
    for subject, expected_value in gold:
        request = read_request(f"{subject}はどこにある？")
        result = answer(request, [view])
        assert result["verdict"] == "ANSWER"
        assert result["semantic"]["verified"] is True
        assert result["answer_values"] == [["recipient", expected_value]]

        before = deepcopy(result)
        without_band = deepcopy(result)
        annotation = band(view, request, result)
        with_band = _beside(result, annotation)
        assert annotation is None
        assert with_band["verdict"] == without_band["verdict"]
        assert _primary(with_band) == _primary(without_band)
        assert result == before
        checked += 1

    # This subject is absent from the constructed source and must not get a
    # numeric band, whether its semantic result is an answer or a refusal.
    request = read_request("架空対象はどこにある？")
    result = answer(request, [view])
    assert result["verdict"] != "ANSWER"
    assert result["semantic"]["verified"] is False
    before = deepcopy(result)
    annotation = band(view, request, result)
    with_band = _beside(result, annotation)
    assert annotation is None
    assert with_band["verdict"] == result["verdict"]
    assert _primary(with_band) == _primary(result)
    assert result == before
    checked += 1

    assert checked >= 30
    print("DEMO OK")


if __name__ == "__main__":
    main()

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
    source = "\n".join(f"{subject}は{value}です。" for subject, value in gold)
    view = document_view({"constructed-source": source})

    print("CLAUSES READ:")
    for clause in view.clauses:
        roles = tuple((role.name, role.term) for role in clause.roles)
        print(f"{clause.span.source}: {clause.span.text!r} -> {clause.predicate} {roles}")

    # Confirm the reader represented every constructed fact completely before
    # asking any question against this view.
    assert len(view.clauses) == len(gold)
    assert not view.unread
    for (subject, expected_value), clause in zip(gold, view.clauses):
        roles = {role.name: role.term for role in clause.roles}
        assert clause.rule == "copula"
        assert clause.predicate == "identity"
        assert clause.polarity == "+"
        assert clause.modality == "assert"
        assert not clause.unsupported
        assert roles == {"entity": subject, "value": expected_value}

    checked = 0
    for subject, expected_value in gold:
        request = read_request(f"{subject}は何？")
        result = answer(request, [view])
        assert result["verdict"] == "ANSWER"
        assert result["semantic"]["verified"] is True
        assert result["answer_values"] == [[subject, expected_value]]

        before = deepcopy(result)
        without_band = deepcopy(result)
        annotation = band(view, request, result)
        with_band = _beside(result, annotation)
        assert annotation.status == "NO_INDEPENDENT_VIEW"
        assert "agree" not in asdict(annotation) and "of" not in asdict(annotation)
        assert with_band["verdict"] == without_band["verdict"]
        assert _primary(with_band) == _primary(without_band)
        assert result == before
        checked += 1

    # An absent subject is refused, so the answer-only band path is not called.
    request = read_request("架空対象は何？")
    result = answer(request, [view])
    assert result["verdict"] != "ANSWER"
    assert result["semantic"]["verified"] is False
    before = deepcopy(result)
    # The agreement annotation is only queried for verified ANSWER results.
    assert "annotations" not in result or "agreement_band" not in result["annotations"]
    assert result == before
    checked += 1

    assert checked >= 30
    print("DEMO OK")


if __name__ == "__main__":
    main()

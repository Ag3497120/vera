from concurrent.futures import ThreadPoolExecutor

import pytest

from verantyx.semantic_ir import Budget, Meter, Proof
from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_verify import Checker, Limit, Rejected


@pytest.fixture(scope="module")
def question():
    request = read_request("何が走った？")
    assert len(request.plans) == 1
    return request


def audited(view, question, budget=None):
    meter = Meter(budget or Budget())
    checker = Checker(view, "document", meter)
    return checker.audit(question.plans[0]), checker


def test_empty_view_produces_no_answers(question):
    view = document_view({})
    answers, _ = audited(view, question)
    assert answers == set()


def test_repeated_audit_is_idempotent(question):
    view = document_view({"doc": "太郎が走った。"})
    checker = Checker(view, "document", Meter())
    expected = {(('agent', '太郎'),)}

    assert checker.audit(question.plans[0]) == expected
    first_steps = checker.meter.steps
    assert checker.audit(question.plans[0]) == expected
    assert checker.meter.steps > first_steps


def test_answer_set_is_independent_of_source_order(question):
    forward = document_view({"a": "太郎が走った。", "b": "猫が走った。"})
    reverse = document_view({"b": "猫が走った。", "a": "太郎が走った。"})
    expected = {(('agent', '太郎'),), (('agent', '猫'),)}

    forward_answers, _ = audited(forward, question)
    reverse_answers, _ = audited(reverse, question)
    assert forward_answers == reverse_answers == expected


def test_two_readers_can_audit_the_same_view_concurrently(question):
    view = document_view({"doc": "太郎が走った。"})
    expected = {(('agent', '太郎'),)}

    def read():
        return Checker(view, "document", Meter()).audit(question.plans[0])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: read(), range(2)))
    assert results == [expected, expected]


def test_exhausted_step_budget_is_a_typed_limit(question):
    view = document_view({})
    checker = Checker(view, "document", Meter(Budget(steps=0)))

    with pytest.raises(Limit):
        checker.gate(question, question.plans[0], [])


def test_exhausted_candidate_budget_is_a_typed_limit(question):
    view = document_view({"a": "太郎が走った。", "b": "猫が走った。"})
    checker = Checker(view, "document", Meter(Budget(candidates=1)))

    with pytest.raises(Limit):
        checker.audit(question.plans[0])


def test_default_candidate_bound_handles_a_large_pool(question):
    source = "太郎が走った。" * 257
    view = document_view({"doc": source})
    assert len(view.clauses) == 257
    checker = Checker(view, "document", Meter())

    with pytest.raises(Limit):
        checker.audit(question.plans[0])


def test_large_source_scan_stops_at_the_step_budget(question):
    view = document_view({"doc": " " * 20_000 + "太郎が走った。"})
    checker = Checker(view, "document", Meter(Budget(steps=1_000)))

    with pytest.raises(Limit):
        checker.audit(question.plans[0])


def test_zero_depth_budget_is_a_typed_limit(question):
    view = document_view({})
    checker = Checker(view, "document", Meter(Budget(depth=0)))

    with pytest.raises(Limit):
        checker.gate(question, question.plans[0], [])


def test_missing_proof_root_is_a_typed_rejection(question):
    view = document_view({})
    checker = Checker(view, "document", Meter())
    proof = Proof((), "missing", "document")

    with pytest.raises(Rejected):
        checker.proof(question, question.plans[0], proof)

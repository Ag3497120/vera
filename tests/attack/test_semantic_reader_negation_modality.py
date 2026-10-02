import pytest

from verantyx.semantic_reader import document_view, read_request


def one_clause(text):
    view = document_view({"source": text})
    assert not view.unread
    assert len(view.clauses) == 1
    return view.clauses[0]


def one_bind(request):
    assert request.plans
    binds = [node for node in request.plans[0].nodes if node.pattern is not None]
    assert len(binds) == 1
    return binds[0]


def test_plain_affirmative_is_asserted():
    clause = one_clause("ユンは箱を開けた。")

    assert clause.predicate == "開ける"
    assert (clause.polarity, clause.modality) == ("+", "assert")
    assert not clause.unsupported


def test_simple_verb_negation_is_negative_assertion():
    clause = one_clause("ユンは箱を開けなかった。")

    assert clause.predicate == "開ける"
    assert (clause.polarity, clause.modality) == ("-", "assert")
    assert not clause.unsupported


def test_explicit_copular_negation_is_negative():
    clause = one_clause("箱は安全ではない。")

    assert clause.rule == "copula"
    assert (clause.polarity, clause.modality) == ("-", "assert")


def test_document_question_is_not_a_fact():
    view = document_view({"source": "ユンは箱を開けたか。"})

    assert not view.clauses
    assert len(view.unread) == 1
    assert "interrogative" in view.unread[0].reason


def test_yes_no_request_keeps_polarity_open():
    binding = one_bind(read_request("ユンは箱を開けたか。"))

    assert binding.pattern.polarity == "*"
    assert binding.relation == "whether"


def test_negative_yes_no_request_is_still_a_question():
    binding = one_bind(read_request("ユンは箱を開けませんか。"))

    assert binding.pattern.polarity == "*"
    assert binding.relation == "whether-negative"


def test_prohibition_is_not_ordinary_negative_polarity():
    view = document_view({"source": "ユンは箱を開けてはいけない。"})
    clauses = [clause for clause in view.clauses if clause.predicate == "開ける"]

    assert len(clauses) == 1
    assert (clauses[0].polarity, clauses[0].modality) == ("+", "prohibition")


def test_permission_is_kept_as_modality():
    view = document_view({"source": "ユンは箱を開けてもよい。"})
    clauses = [clause for clause in view.clauses if clause.predicate == "開ける"]

    assert len(clauses) == 1
    assert (clauses[0].polarity, clauses[0].modality) == ("+", "permission")


def test_likely_hearsay_or_report_is_hedged():
    clause = one_clause("ユンは箱を開けたらしい。")

    assert clause.modality == "hedge"
    assert not clause.unsupported


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: double negation is assigned negative polarity",
)
def test_double_negation_does_not_become_a_negative_candidate():
    views = [document_view({"source": "ユンは箱を開けないわけではない。"}) for _ in range(2)]

    assert all(
        not any(clause.polarity == "-" for clause in view.clauses)
        for view in views
    )


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: negative i-adjective is emitted as a supported positive identity literal",
)
def test_negative_i_adjective_is_not_a_supported_positive_identity():
    views = [document_view({"source": "箱は大きくない。"}) for _ in range(2)]

    assert all(
        not any(
            clause.rule == "copula"
            and clause.predicate == "identity"
            and clause.polarity == "+"
            and not clause.unsupported
            for clause in view.clauses
        )
        for view in views
    )


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: hearsay そうだ is assigned assert modality",
)
def test_hearsay_sou_da_is_not_an_assertion():
    views = [document_view({"source": "ユンは箱を開けたそうだ。"}) for _ in range(2)]

    assert all(
        not any(clause.modality == "assert" for clause in view.clauses)
        for view in views
    )

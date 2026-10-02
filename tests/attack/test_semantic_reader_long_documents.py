from decimal import Decimal

from verantyx.semantic_reader import document_view, read_request


SENTENCE = "東京の人口は100人です。"


def _roles(clause):
    return {role.name: role.term for role in clause.roles}


def test_exact_repetitions_remain_separate_source_bound_clauses():
    raw = SENTENCE + SENTENCE
    view = document_view({"ledger": raw})

    assert not view.unread
    assert len(view.clauses) == 2
    assert [clause.span.text for clause in view.clauses] == [SENTENCE, SENTENCE]
    assert view.clauses[0].span.start < view.clauses[1].span.start
    assert len({clause.id for clause in view.clauses}) == 2
    assert all(clause.span.source == "ledger" for clause in view.clauses)


def test_near_duplicate_values_stay_attached_to_their_own_occurrences():
    raw = SENTENCE + SENTENCE + "東京の人口は101人です。"
    view = document_view({"ledger": raw})

    assert not view.unread
    assert len(view.clauses) == 3
    values = [_roles(clause)["value"] for clause in view.clauses]
    assert [(value.amount, value.unit) for value in values] == [
        (Decimal("100"), "人"),
        (Decimal("100"), "人"),
        (Decimal("101"), "人"),
    ]
    assert all(_roles(clause)["entity"] == "東京" for clause in view.clauses)


def test_conflicting_documents_keep_opposite_polarity_and_provenance():
    view = document_view({
        "claim-a": SENTENCE,
        "claim-b": "東京の人口は100人ではない。",
    })

    assert not view.unread
    assert [(clause.span.source, clause.polarity) for clause in view.clauses] == [
        ("claim-a", "+"),
        ("claim-b", "-"),
    ]
    assert all(_roles(clause)["entity"] == "東京" for clause in view.clauses)


def test_many_documents_with_repeated_entity_keep_distinct_sources():
    documents = {f"doc-{index:02d}": SENTENCE for index in range(48)}
    view = document_view(documents)

    assert not view.unread
    assert len(view.clauses) == len(documents)
    assert [clause.span.source for clause in view.clauses] == list(documents)
    assert len({clause.id for clause in view.clauses}) == len(documents)
    assert all(_roles(clause)["entity"] == "東京" for clause in view.clauses)


def test_sovereign_metadata_stays_with_each_document_clause():
    view = document_view(
        {"east": SENTENCE, "west": SENTENCE},
        sovereigns={"east": "claimant", "west": "witness"},
    )

    assert [clause.sovereign for clause in view.clauses] == ["claimant", "witness"]


def test_question_in_document_is_unread_instead_of_a_fact():
    raw = "東京の人口は何人ですか？"
    view = document_view({"question": raw})

    assert not view.clauses
    assert len(view.unread) == 1
    assert view.unread[0].span.source == "question"
    assert view.unread[0].span.text == raw


def test_long_colon_scoped_sentence_is_preserved_as_one_unread_span():
    raw = "引用：" + "東京の人口は100人です、" * 350 + "東京の人口は100人です"
    view = document_view({"long": raw})

    assert not view.clauses
    assert len(view.unread) == 1
    assert view.unread[0].span.source == "long"
    assert view.unread[0].span.text == raw


def test_long_over_budget_question_returns_typed_unread_request():
    path = "の".join(["東京"] + ["人口"] * 80)
    raw = path + "は何ですか"
    request = read_request(raw)

    assert not request.plans
    assert len(request.unread) == 1
    assert request.unread[0].span.text == raw


def test_property_question_projects_a_variable_with_its_unit():
    request = read_request("東京の人口は何人ですか")

    assert len(request.plans) == 1
    project = request.plans[0].nodes[-1]
    assert project.op == "Project"
    assert len(project.outputs) == 1
    output = project.outputs[0]
    assert output.unit == "人"
    assert output.term.sort == "quantity"


def test_long_repeated_document_keeps_sentence_boundaries_and_order():
    raw = SENTENCE * 80
    view = document_view({"long": raw})

    assert not view.unread
    assert len(view.clauses) == 80
    assert all(clause.span.text == SENTENCE for clause in view.clauses)
    assert [clause.span.start for clause in view.clauses] == [
        index * len(SENTENCE) for index in range(80)
    ]

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from verantyx.semantic_ir import Quantity, Request
from verantyx.semantic_reader import document_view, quantity, read_request


def _by_source(view):
    return {
        source: (
            tuple(clause for clause in view.clauses if clause.span.source == source),
            tuple(item for item in view.unread if item.span.source == source),
        )
        for source in sorted(view.sources)
    }


def test_empty_document_mapping_produces_no_readings():
    view = document_view({})

    assert view.sources == {}
    assert view.clauses == ()
    assert view.unread == ()


def test_empty_source_produces_no_synthetic_reading():
    view = document_view({"empty": " \n "})

    assert view.sources == {"empty": " \n "}
    assert view.clauses == ()
    assert view.unread == ()


def test_interrogative_document_is_unread_instead_of_asserted():
    view = document_view({"question": "誰が来た？"})

    assert view.clauses == ()
    assert len(view.unread) == 1
    assert view.unread[0].span.text == "誰が来た？"
    assert view.unread[0].reason == "interrogative source does not assert a fact"


def test_colon_scoped_document_is_retained_as_unread():
    view = document_view({"scoped": "仮説:太郎は花子を呼んだ。"})

    assert view.clauses == ()
    assert len(view.unread) == 1
    assert view.unread[0].span.text == "仮説:太郎は花子を呼んだ。"
    assert view.unread[0].reason == "uninterpreted colon scope"


def test_empty_request_is_a_typed_unread_request():
    request = read_request(" \n ")

    assert isinstance(request, Request)
    assert request.plans == ()
    assert len(request.unread) == 1
    assert request.unread[0].span.text == " \n "


def test_unsupported_quantified_question_is_a_typed_refusal():
    request = read_request("すべての人は誰ですか？")

    assert isinstance(request, Request)
    assert request.plans == ()
    assert len(request.unread) == 1
    assert "unsupported mandatory scope/quantifier/time" in request.unread[0].reason


def test_quantity_digit_limit_returns_none_without_decimal_failure():
    exact = quantity("1.25kg")
    oversized = quantity("9" * 129 + "kg")

    assert exact is not None
    assert exact == Quantity(Decimal("1.25"), "kg")
    assert oversized is None


def test_repeated_document_read_is_idempotent_except_for_elapsed_time():
    documents = {"copula": "富士山は山です。"}
    first = document_view(documents)
    second = document_view(documents)

    assert len(first.clauses) == 1
    assert first.clauses[0].rule == "copula"
    assert first.sources == second.sources
    assert first.clauses == second.clauses
    assert first.unread == second.unread


def test_repeated_request_read_produces_the_same_plan():
    text = "富士山は何ですか？"
    first = read_request(text)
    second = read_request(text)

    assert first.plans
    assert first.unread == ()
    assert first == second


def test_document_results_do_not_depend_on_mapping_insertion_order():
    items = [
        ("copula", "富士山は山です。"),
        ("question", "誰が来た？"),
        ("scoped", "仮説:太郎は花子を呼んだ。"),
    ]
    forward = document_view(dict(items))
    reverse = document_view(dict(reversed(items)))

    assert forward.sources == reverse.sources
    assert _by_source(forward) == _by_source(reverse)


def test_two_concurrent_readers_return_the_same_results_as_serial_reads():
    documents = {"copula": "富士山は山です。", "question": "誰が来た？"}
    question = "富士山は何ですか？"

    def read_pair(_):
        return document_view(documents), read_request(question)

    expected = read_pair(None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        observed = list(pool.map(read_pair, range(4)))

    assert all(view.sources == expected[0].sources for view, _ in observed)
    assert all(view.clauses == expected[0].clauses for view, _ in observed)
    assert all(view.unread == expected[0].unread for view, _ in observed)
    assert all(request == expected[1] for _, request in observed)


def test_many_scoped_sentences_remain_bounded_typed_unread_items():
    count = 512
    raw = "未定義:scope。" * count
    view = document_view({"bulk": raw})

    assert view.clauses == ()
    assert len(view.unread) == count
    assert all(item.reason == "uninterpreted colon scope" for item in view.unread)

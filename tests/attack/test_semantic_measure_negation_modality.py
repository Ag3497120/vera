import pytest

from verantyx.semantic_measure import read_measure_request, read_measure_sentence


class _Builder:
    def __init__(self):
        self.roots = []
        self.nodes = []
        self.outputs = []
        self._variables = 0

    def variable(self, kind):
        self._variables += 1
        return f"v{self._variables}:{kind}"

    def bind(self, pattern, span):
        self.roots.append(f"root{len(self.roots)}")

    def obligation(self, ident, kind, span, detail):
        return f"obligation:{ident}:{kind}"

    def project(self, node):
        return node


def _sentence(text):
    return read_measure_sentence("attack", text, 0, 0, len(text), "attack", "measure")


def _request(text):
    return read_measure_request(text, _Builder(), "request-span")


def test_asserted_measure_sentence_is_read():
    clauses = _sentence("Aは3mです。")

    assert clauses is not None
    assert len(clauses) == 1
    assert clauses[0].predicate == "measure.length"


@pytest.mark.parametrize(
    "text",
    [
        "Aは3mではない。",
        "Aは3mじゃない。",
        "Aは3mではないわけではない。",
        "Aは重くない。",
    ],
)
def test_negated_or_negative_adjective_sentence_is_not_read_as_measure_fact(text):
    assert _sentence(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "Aは3mでなければならない。",
        "Aは3mでよい。",
        "Aは3mにしてはいけない。",
        "Aは3mかもしれない。",
    ],
)
def test_modal_measure_sentence_is_not_read_as_measure_fact(text):
    assert _sentence(text) is None


def test_hearsay_measure_sentence_is_not_read_as_measure_fact():
    assert _sentence("Aは3mだそうだ。") is None


def test_measure_question_shape_is_recognized():
    assert _request("どちらが長いですか？") is not None


@pytest.mark.parametrize(
    "text",
    [
        "合計は何mではない？",
        "どちらが長くないですか？",
        "長い方ではない？",
        "長さは同じではないですか？",
    ],
)
def test_negated_measure_request_is_not_expanded(text):
    assert _request(text) is None


def test_declarative_comparison_is_not_expanded_as_a_request():
    assert _request("Aは長い方です。") is None


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: question-marked measure sentence is emitted as an asserted measure clause",
)
def test_question_marked_measure_sentence_is_not_read_as_fact():
    # Run the same minimal reproduction twice before recording this ungrounded parse.
    observations = [_sentence("Aは3m?") for _ in range(2)]

    assert observations == [None, None]

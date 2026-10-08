"""W1-g B05: the work budget counts source words written in any script.

``unknown_candidates`` documents its work as source clauses + role terms + distinct source
words. The expected work below is counted by hand in each test (a literal word list), not with
``vocabulary.runs`` or the product's word splitter. For each input: budget = work - 1 refuses with
``BUDGET_REFUSAL``; budget = work does not.
"""
import pytest

from verantyx.semantic_ir import Clause, Role, Span, Variable, View
from verantyx.semantic_unknown import unknown_candidates

# (name, source text, hand-listed distinct words)
CASES = [
    ("accented_latin", "café crème", ["café", "crème"]),
    ("cyrillic", "привет мир", ["привет", "мир"]),
    ("hangul", "안녕 세계", ["안녕", "세계"]),
    ("ascii_after_japanese", "Alice猫 Bob", ["Alice", "猫", "Bob"]),
    ("japanese_punctuation_separates", "alpha、beta。gamma", ["alpha", "beta", "gamma"]),
    # hiragana and 。 are separators, not words: 花子 太郎 資料 渡
    ("japanese_sentence", "花子が太郎に資料を渡した。", ["花子", "太郎", "資料", "渡"]),
    ("ascii_duplicates_count_once", "alpha beta alpha", ["alpha", "beta"]),
]
IDS = [case[0] for case in CASES]


def _clause(source: str, text: str, actor: str, predicate: str, patient: str) -> Clause:
    def span(word):
        start = text.index(word)
        return Span(source, start, start + len(word), word)
    return Clause(
        id="c1", event=Variable("event:c1"), predicate=predicate,
        predicate_span=span(predicate),
        roles=(Role("actor", actor, span(actor)), Role("patient", patient, span(patient))),
        span=Span(source, 0, len(text), text),
        polarity="+", time="",
    )


def _words_only_view(text):
    return View({"s": text}, ())


def _clause_view(extra_text):
    base = "Alice likes cats"
    return View({"s1": base, "s2": extra_text}, (_clause("s1", base, "Alice", "likes", "cats"),))


@pytest.mark.parametrize("name,text,words", CASES, ids=IDS)
def test_work_is_exactly_the_hand_counted_words(name, text, words):
    work = len(words)
    view = _words_only_view(text)
    assert unknown_candidates(view, "unseen", budget=work - 1).status == "BUDGET_REFUSAL"
    assert unknown_candidates(view, "unseen", budget=work).status != "BUDGET_REFUSAL"


@pytest.mark.parametrize("name,text,words", CASES, ids=IDS)
def test_work_adds_clauses_roles_and_words_across_sources(name, text, words):
    # 1 clause + 2 role terms + the words of both sources. "Alice" is a word of both
    # sources in the "Alice猫 Bob" case and of the alpha/beta cases only once each.
    distinct = {"Alice", "likes", "cats"} | set(words)
    work = 1 + 2 + len(distinct)
    view = _clause_view(text)
    assert unknown_candidates(view, "unseen", budget=work - 1).status == "BUDGET_REFUSAL"
    assert unknown_candidates(view, "unseen", budget=work).status != "BUDGET_REFUSAL"


@pytest.mark.parametrize("text", [
    "alpha beta", "one", "a b c d e f", "x  y\tz\nw", "  lead and trail  ",
    "punct, stays. attached! to-words", "", "   ",
])
def test_ascii_whitespace_documents_count_like_split(text):
    expected = len(set(text.split()))
    view = _words_only_view(text)
    if expected >= 1:
        assert unknown_candidates(view, "unseen", budget=expected).status != "BUDGET_REFUSAL"
    if expected >= 2:
        assert unknown_candidates(view, "unseen", budget=expected - 1).status == "BUDGET_REFUSAL"


def test_hiragana_only_text_adds_no_work():
    view = _words_only_view("これはそれです。")
    assert unknown_candidates(view, "unseen", budget=1).status != "BUDGET_REFUSAL"


def test_known_terms_are_decided_before_the_budget():
    view = _clause_view("café crème привет мир")
    for term in ("Alice", "cats", "likes"):
        assert unknown_candidates(view, term, budget=1).status == "KNOWN_TERM"


def test_zero_and_invalid_budgets_refuse():
    view = _words_only_view("café")
    for budget in (0, -1):
        assert unknown_candidates(view, "unseen", budget=budget).status == "BUDGET_REFUSAL"

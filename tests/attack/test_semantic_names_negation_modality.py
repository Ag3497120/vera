from types import SimpleNamespace

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def word(surface, pos1, lemma):
    return SimpleNamespace(surface=surface, feature=SimpleNamespace(pos1=pos1, lemma=lemma))


def test_past_aux_accepts_auxiliary_た():
    assert is_past_aux(word("た", "助動詞", "た")) is True


def test_past_aux_accepts_voiced_surface_with_た_lemma():
    assert is_past_aux(word("だ", "助動詞", "た")) is True


def test_past_aux_uses_lemma_instead_of_surface():
    assert is_past_aux(word("た", "助動詞", "する")) is False


@pytest.mark.parametrize(
    ("surface", "pos1", "lemma"),
    [
        ("ない", "助動詞", "ない"),
        ("ぬ", "助動詞", "ぬ"),
        ("ない", "形容詞", "ない"),
        ("べき", "助動詞", "べき"),
        ("よい", "形容詞", "よい"),
        ("な", "助動詞", "な"),
        ("か", "助詞", "か"),
    ],
)
def test_negation_modality_and_question_tokens_are_not_past_aux(surface, pos1, lemma):
    assert is_past_aux(word(surface, pos1, lemma)) is False


def test_negative_past_can_still_contain_a_past_auxiliary():
    # In a form such as 来なかった, this helper classifies the た token only.
    assert is_past_aux(word("た", "助動詞", "た")) is True


def test_tokens_covering_returns_exact_negative_token_span():
    tagged = [
        ("行か", "動詞", "自立", 0, 2),
        ("ない", "助動詞", "*", 2, 4),
        ("か", "助詞", "終助詞", 4, 5),
    ]
    assert tokens_covering(tagged, 2, 4) == [tagged[1]]


def test_tokens_covering_rejects_a_gap_in_a_negative_clause():
    tagged = [
        ("行", "動詞", "自立", 0, 1),
        ("ない", "助動詞", "*", 2, 4),
    ]
    assert tokens_covering(tagged, 0, 4) is None


def test_name_split_can_extract_exact_title_name_pair_in_negative_context():
    tagged = [
        ("研究員", "名詞", "一般", 0, 3),
        ("花子", "名詞", "固有名詞", 3, 5),
        ("は", "助詞", "係助詞", 5, 6),
        ("来", "動詞", "自立", 6, 7),
        ("ない", "助動詞", "*", 7, 9),
    ]
    assert name_split_in(tagged[:2], "研究員花子") == ("研究員", "花子")


def test_name_split_does_not_treat_a_negated_clause_as_a_name():
    tagged = [
        ("研究員", "名詞", "一般", 0, 3),
        ("花子", "名詞", "固有名詞", 3, 5),
        ("は", "助詞", "係助詞", 5, 6),
        ("来", "動詞", "自立", 6, 7),
        ("ない", "助動詞", "*", 7, 9),
    ]
    assert name_split_in(tagged, "研究員花子は来ない") is None


def test_name_split_does_not_treat_a_question_clause_as_a_name():
    tagged = [
        ("研究員", "名詞", "一般", 0, 3),
        ("花子", "名詞", "固有名詞", 3, 5),
        ("は", "助詞", "係助詞", 5, 6),
        ("来る", "動詞", "自立", 6, 8),
        ("か", "助詞", "終助詞", 8, 9),
    ]
    assert name_split_in(tagged, "研究員花子は来るか") is None

import pytest

from verantyx import semantic_coord as coord


def tags(*items):
    """Build sentence-relative semantic_coord tokens from surface/tag tuples."""
    result = []
    at = 0
    for surface, pos1, pos2, cform in items:
        result.append((surface, pos1, pos2, cform, at, at + len(surface)))
        at += len(surface)
    return result


def test_negative_final_clause_does_not_change_te_coordination_gate():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('言っ', '動詞', '自立', '連用形-促音便'), ('て', '助詞', '接続助詞', '*'),
        ('帰ら', '動詞', '自立', '未然形'), ('ない', '助動詞', '*', '終止形'),
    )

    assert coord.coordination_ok(sentence, [2, 4])


def test_adjectival_naku_then_te_is_structurally_accepted():
    sentence = tags(
        ('金', '名詞', '一般', '*'), ('が', '助詞', '格助詞', '*'),
        ('なく', '形容詞', '自立', '連用形'), ('て', '助詞', '接続助詞', '*'),
        ('戻る', '動詞', '自立', '終止形'),
    )

    assert coord.coordination_ok(sentence, [2, 4])


def test_negative_particle_does_not_count_as_a_second_clause_subject():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('帰ら', '動詞', '自立', '未然形'), ('ない', '助動詞', '*', '終止形'),
    )

    assert not coord.own_subject_phrase(sentence, 2, 4)


def test_final_question_mark_does_not_break_a_te_chain():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('来', '動詞', '自立', '連用形'), ('て', '助詞', '接続助詞', '*'),
        ('帰る', '動詞', '自立', '終止形'), ('?', '補助記号', '句点', '*'),
    )

    assert coord.coordination_ok(sentence, [2, 4])


def test_double_negation_final_material_is_outside_the_connector_gap():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('来', '動詞', '自立', '連用形'), ('て', '助詞', '接続助詞', '*'),
        ('知ら', '動詞', '自立', '未然形'), ('ない', '助動詞', '*', '連用形'),
        ('わけ', '名詞', '一般', '*'), ('では', '助詞', '係助詞', '*'),
        ('ない', '助動詞', '*', '終止形'),
    )

    assert coord.coordination_ok(sentence, [2, 4])


def test_adversative_ga_is_not_a_te_or_renyo_connector():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('来', '動詞', '自立', '連用形'), ('が', '助詞', '接続助詞', '*'),
        ('帰る', '動詞', '自立', '終止形'),
    )

    assert not coord.coordination_ok(sentence, [2, 4])


def test_causal_node_is_not_a_te_or_renyo_connector():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('来', '動詞', '自立', '連用形'), ('ので', '助詞', '接続助詞', '*'),
        ('帰る', '動詞', '自立', '終止形'),
    )

    assert not coord.coordination_ok(sentence, [2, 4])


def test_topic_phrase_includes_a_simple_noun_topic():
    sentence = tags(
        ('規則', '名詞', '一般', '*'), ('は', '助詞', '係助詞', '*'),
        ('守る', '動詞', '自立', '終止形'), ('。', '補助記号', '句点', '*'),
    )

    assert coord.topic_phrase(sentence, [2]) == (0, 2)


def test_own_subject_phrase_recognizes_ga_in_a_later_clause():
    sentence = tags(
        ('彼', '名詞', '代名詞', '*'), ('は', '助詞', '係助詞', '*'),
        ('来', '動詞', '自立', '連用形'), ('て', '助詞', '接続助詞', '*'),
        ('犬', '名詞', '一般', '*'), ('が', '助詞', '格助詞', '*'),
        ('帰る', '動詞', '自立', '終止形'),
    )

    first, last = coord.chunk(sentence, [2, 6], 1)
    assert coord.own_subject_phrase(sentence, first, last)


def test_phrase_boundary_detects_a_split_word_neighbor():
    sentence = tags(
        ('クク', '名詞', '一般', '*'), ('クル', '名詞', '一般', '*'),
        ('は', '助詞', '係助詞', '*'), ('帰る', '動詞', '自立', '終止形'),
    )

    assert not coord.phrase_bounded(sentence, 0, 2)


def test_ascii_art_katakana_is_not_treated_as_punctuation_boundary():
    sentence = tags(
        ('ノシ', '補助記号', '一般', '*'), ('猫', '名詞', '一般', '*'),
        ('は', '助詞', '係助詞', '*'), ('帰る', '動詞', '自立', '終止形'),
    )

    assert not coord.phrase_bounded(sentence, 2, 3)


@pytest.mark.xfail(strict=False, reason="DEFECT: genitive modifier is omitted from the topic span")
def test_topic_phrase_keeps_genitive_material_in_a_negated_clause():
    sentence = tags(
        ('学生', '名詞', '一般', '*'), ('の', '助詞', '連体化', '*'),
        ('規則', '名詞', '一般', '*'), ('は', '助詞', '係助詞', '*'),
        ('守ら', '動詞', '自立', '未然形'), ('ない', '助動詞', '*', '終止形'),
    )

    assert coord.topic_phrase(sentence, [4, 5]) == (0, 5)


@pytest.mark.xfail(strict=False, reason="DEFECT: a permission construction is accepted as coordination")
def test_permission_mo_yoi_is_not_a_second_clause():
    sentence = tags(
        ('申請', '名詞', '一般', '*'), ('し', '動詞', '自立', '連用形'),
        ('て', '助詞', '接続助詞', '*'), ('も', '助詞', '係助詞', '*'),
        ('よい', '形容詞', '自立', '終止形'),
    )

    assert not coord.coordination_ok(sentence, [1, 4])


@pytest.mark.xfail(strict=False, reason="DEFECT: a prohibition construction is accepted as coordination")
def test_prohibition_wa_naranai_is_not_a_second_clause():
    sentence = tags(
        ('薬', '名詞', '一般', '*'), ('を', '助詞', '格助詞', '*'),
        ('飲ん', '動詞', '自立', '連用形-撥音便'), ('で', '助詞', '接続助詞', '*'),
        ('は', '助詞', '係助詞', '*'), ('なら', '動詞', '自立', '未然形'),
        ('ない', '助動詞', '*', '終止形'),
    )

    assert not coord.coordination_ok(sentence, [2, 5])


@pytest.mark.xfail(strict=False, reason="DEFECT: adverbial material can replace the required new noun phrase")
def test_adverb_after_te_does_not_supply_the_required_new_noun_phrase():
    sentence = tags(
        ('食べ', '動詞', '自立', '連用形'), ('て', '助詞', '接続助詞', '*'),
        ('すぐ', '副詞', '一般', '*'), ('帰る', '動詞', '自立', '終止形'),
    )

    assert not coord.coordination_ok(sentence, [0, 3])


@pytest.mark.xfail(strict=False, reason="DEFECT: a span starting inside a token is accepted")
def test_role_phrase_cannot_start_inside_a_negated_predicate_token():
    sentence = tags(
        ('戻ら', '動詞', '自立', '未然形'), ('ない', '助動詞', '*', '終止形'),
    )

    assert not coord.phrase_bounded(sentence, 1, 3)

import pytest

from verantyx.semantic_reader import document_view


def _read(raw):
    return document_view({'source': raw})


def _role(clause, name):
    return next(role for role in clause.roles if role.name == name)


def test_clean_clause_keeps_roles_and_past_tense():
    raw = '太郎が花子を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.predicate == '見る'
    assert clause.polarity == '+'
    assert clause.time == 'past'
    assert clause.span.text == raw
    assert (_role(clause, 'agent').term, _role(clause, 'agent').span.text) == ('太郎', '太郎')
    assert (_role(clause, 'patient').term, _role(clause, 'patient').span.text) == ('花子', '花子')
    assert not clause.unsupported


def test_fullwidth_sentence_terminator_preserves_the_clause():
    raw = '太郎が花子を見た！'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.span.text == raw
    assert clause.predicate == '見る'
    assert _role(clause, 'patient').span.text == '花子'


def test_halfwidth_katakana_role_is_preserved_verbatim():
    raw = 'ﾀﾛｳが花子を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert not clause.unsupported
    role = _role(clause, 'agent')
    assert role.term == 'ﾀﾛｳ'
    assert role.span.text == raw[role.span.start:role.span.end] == 'ﾀﾛｳ'


def test_mixed_latin_and_japanese_name_is_source_bound():
    raw = 'Taroが花子を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert not clause.unsupported
    role = _role(clause, 'agent')
    assert role.term == 'Taro'
    assert role.span.text == raw[role.span.start:role.span.end] == 'Taro'


def test_combining_mark_content_is_explicitly_unsupported():
    raw = '太郎がCafe\u0301を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.span.text == raw
    assert clause.unsupported
    assert all(role.span.text == raw[role.span.start:role.span.end] for role in clause.roles)


def test_zero_width_noise_in_argument_is_explicitly_unsupported():
    raw = '太郎が花\u200b子を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.span.text == raw
    assert clause.unsupported


def test_markup_residue_is_not_returned_as_a_supported_frame():
    raw = '**太郎**が花子を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.span.text == raw
    assert clause.unsupported


def test_emoji_noise_keeps_raw_sentence_and_argument_spans():
    raw = '太郎が🙂花子を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.span.text == raw
    assert _role(clause, 'agent').span.text == '太郎'
    assert _role(clause, 'patient').span.text == '花子'


def test_ascii_art_prefix_is_a_typed_unread_span():
    raw = ':-) 太郎が花子を見た。'
    view = _read(raw)

    assert not view.clauses
    assert len(view.unread) == 1
    assert view.unread[0].span.text == raw


def test_ocr_like_tail_marks_the_candidate_unsupported():
    raw = '太郎が花子を見たxx。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.span.text == raw
    assert clause.unsupported


def test_ocr_confusable_glyph_is_kept_as_the_written_value():
    raw = '太郎が花孑を見た。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    role = _role(clause, 'patient')
    assert role.term == '花孑'
    assert role.span.text == raw[role.span.start:role.span.end] == '花孑'


def test_clean_negative_clause_keeps_negative_polarity():
    raw = '太郎が花子を見なかった。'
    view = _read(raw)

    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.polarity == '-'
    assert clause.time == 'past'
    assert not clause.unsupported


@pytest.mark.xfail(
    strict=False,
    reason='DEFECT: zero-width character before negation flips polarity to positive',
)
def test_zero_width_before_negation_is_unread_or_keeps_negative_polarity():
    raw = '太郎が花子を見\u200bなかった。'
    view = _read(raw)

    if view.unread:
        assert not view.clauses
        return

    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.polarity == '-'
    assert not clause.unsupported

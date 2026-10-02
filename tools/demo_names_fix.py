"""Constructed checks for evidence-based title/name splitting."""
from __future__ import annotations

from verantyx.semantic_names import name_split_in, tokens_covering
from verantyx.semantic_reader import _tokens, document_view


def _cover(sentence, value):
    start = sentence.index(value)
    tagged = [(word.surface, word.feature.pos1, word.feature.pos2, left, right)
              for word, left, right in _tokens(sentence)]
    return tokens_covering(tagged, start, start + len(value))


def _agent_term(sentence):
    view = document_view({'constructed': sentence})
    assert len(view.clauses) == 1, (sentence, view.clauses, view.unread)
    agent = [role for role in view.clauses[0].roles if role.name == 'agent']
    assert len(agent) == 1, (sentence, view.clauses[0].roles)
    return agent[0].term


def main():
    # Kinship words are one ordinary common-noun token in these constructed inputs;
    # they carry no proper-name evidence and therefore cannot be split.
    for term in ('叔母', '祖母', '伯父', '兄嫁'):
        sentence = f'{term}は花を見た。'
        cover = _cover(sentence, term)
        assert cover and len(cover) == 1, (sentence, cover)
        assert name_split_in(cover, term) is None, (sentence, name_split_in(cover, term))

    # True title + name cases are licensed by the tagger's 固有名詞 evidence.
    for sentence, title, name in (
            ('先生花子は花を見た。', '先生', '花子'),
            ('社長花子は花を見た。', '社長', '花子'),
            ('技師ユンは花を見た。', '技師', 'ユン')):
        value = title + name
        split = name_split_in(_cover(sentence, value), value)
        assert split == (title, name), (sentence, split)
        assert _agent_term(sentence) == name, (sentence, _agent_term(sentence))

    # A prefix or suffix cannot be a title descriptor or name head.
    assert name_split_in([
        ('研究', '名詞', '普通名詞', 0, 2),
        ('長', '接尾辞', '名詞性接尾辞', 2, 3),
        ('田中', '名詞', '固有名詞', 3, 5),
    ], '研究長田中') is None
    assert name_split_in([
        ('元', '接頭辞', '名詞接頭辞', 0, 1),
        ('社長', '名詞', '普通名詞', 1, 3),
        ('花子', '名詞', '固有名詞', 3, 5),
    ], '元社長花子') is None
    assert name_split_in([
        ('先生', '名詞', '普通名詞', 0, 2),
        ('さん', '接尾辞', '名詞性接尾辞', 2, 4),
    ], '先生さん') is None

    # A common noun after a title is not promoted to a name without tagger evidence.
    assert name_split_in([
        ('先生', '名詞', '普通名詞', 0, 2),
        ('太郎', '名詞', '普通名詞', 2, 4),
    ], '先生太郎') is None
    print('DEMO OK')


if __name__ == '__main__':
    main()

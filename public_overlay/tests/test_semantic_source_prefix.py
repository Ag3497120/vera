"""Authored source-scope regressions, independent of sealed evaluation content."""
from dataclasses import replace

import pytest

from verantyx.one import Vera
from verantyx.semantic_ir import Meter, Span, View
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import Checker, Rejected


@pytest.mark.parametrize('prefix', ['仮定：', '誤記：', 'ナオの担当はミオではない：',
                                   '未解釈の見出し: ', 'F: ', 'F1: ', '規則: ', '規則： '])
def test_uninterpreted_prefix_never_disappears_from_source_scope(prefix):
    raw = prefix + 'ナオの担当はミオ。'
    view = document_view({'doc': raw})
    assert not view.clauses
    assert view.unread[0].span.text == raw
    result = Vera.from_texts({'doc': raw}, mode='semantic').ask('ナオの担当は誰？')
    assert result['verdict'] == 'UNKNOWN_UNSUPPORTED_EVIDENCE'
    assert result['values'] == []
    assert result['semantic']['source_unread'][0]['span']['text'] == raw


@pytest.mark.parametrize('prefix', ['規則: ', '規則： '])
def test_rule_heading_does_not_prove_the_occurrence_of_its_consequence(prefix):
    # A rule/procedure may prescribe an action without establishing it happened.
    raw = prefix + 'ソラが来た場合、ユキが窓を開ける。ソラが来た。'
    result = Vera.from_texts({'doc': raw}, mode='semantic').ask('ユキは窓を開けるか？')
    assert result['verdict'] == 'UNKNOWN_UNSUPPORTED_EVIDENCE'
    assert result['values'] == []


@pytest.mark.parametrize('prefix', ['仮定：', '誤記：', 'ナオの担当はミオではない：'])
def test_checker_rejects_old_suffix_only_producer_claim(prefix):
    body = 'ナオの担当はミオ。'
    original = document_view({'doc': body}).clauses[0]
    raw, offset = prefix + body, len(prefix)
    def shift(span):
        return replace(span, start=span.start+offset, end=span.end+offset)
    forged = replace(original, span=Span('doc', 0, len(raw), raw),
                     body_span=shift(original.body_span), predicate_span=shift(original.predicate_span),
                     roles=tuple(replace(role, span=shift(role.span)) for role in original.roles))
    with pytest.raises(Rejected, match='uninterpreted colon scope'):
        Checker(View({'doc': raw}, (forged,)), 'document', Meter())._source(forged)
    clipped = replace(forged, span=forged.body_span)
    with pytest.raises(Rejected, match='full-clause boundary'):
        Checker(View({'doc': raw}, (clipped,)), 'document', Meter())._source(clipped)


def test_plain_source_still_answers_and_colon_time_literal_is_not_a_discarded_prefix():
    for raw, question, expected in [('ナオの担当はミオ。', 'ナオの担当は誰？', 'ミオ'),
                                    ('会議の開始時刻は12:30。', '会議の開始時刻は何？', '12:30')]:
        result = Vera.from_texts({'doc': raw}, mode='semantic').ask(question)
        assert result['verdict'] == 'ANSWER' and result['values'] == [expected]


@pytest.mark.parametrize('rule', ['copula', 'identity'])
def test_checker_rejects_question_with_forged_asserting_identity_rule(rule):
    raw = 'ナオの担当はミオ。'
    clause = document_view({'doc': raw}).clauses[0]
    question = raw[:-1] + '？'
    forged = replace(clause, rule=rule,
                     span=replace(clause.span, text=question),
                     body_span=replace(clause.body_span, text=question))
    with pytest.raises(Rejected, match='interrogative'):
        Checker(View({'doc': question}, (forged,)), 'document', Meter())._source(forged)


def test_checker_identity_alias_preserves_a_fully_asserted_source():
    raw = 'ナオの担当はミオ。'
    clause = replace(document_view({'doc': raw}).clauses[0], rule='identity')
    Checker(View({'doc': raw}, (clause,)), 'document', Meter())._source(clause)

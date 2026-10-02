"""Public regressions found independently of the development 80-answer set."""
from dataclasses import replace
import pytest
from verantyx.one import Vera
from verantyx.semantic_reader import document_view
from verantyx.semantic_ir import Meter, Pattern, Span, View
from verantyx.semantic_verify import Checker, Rejected


@pytest.mark.parametrize('question', [
    'ナオは学校からリクに青鍵を渡したか？',
    'ナオはリクに青鍵を二つ渡したか？',
    'ナオはリクに青鍵を2つ渡したか？',
    'ナオはリクからリクに青鍵を渡したか？',
])
def test_unrepresented_request_content_never_becomes_a_yes(question):
    result = Vera.from_texts({'d': 'ナオがリクに青鍵を渡した。'}, mode='semantic').ask(question)
    assert result['verdict'] == 'UNKNOWN_UNREAD'
    assert result['values'] == []
    assert result['semantic']['request']['unread'][0]['span']['text'] == question


@pytest.mark.parametrize('text', ['ナオは窓を開けたか？', 'ナオは窓を開けたか。', 'ナオの担当はミオ？',
                                'ナオは窓を開けたかな。', 'ナオは窓を開けたかね。', 'ナオは窓を開けたかしら。'])
def test_document_questions_are_not_facts(text):
    result = Vera.from_texts({'d': text}, mode='semantic').ask('ナオは窓を開けたか？' if '窓' in text else 'ナオの担当は誰？')
    assert result['verdict'] != 'ANSWER'


def test_requested_tense_must_have_matching_evidence():
    for source, question in [('ナオが窓を開ける。', 'ナオは窓を開けたか？'),
                             ('ナオが窓を開けた。', 'ナオは窓を開けるか？')]:
        result = Vera.from_texts({'d': source}, mode='semantic').ask(question)
        assert result['verdict'] == 'UNKNOWN_NO_EVIDENCE'
    for source, question in [('ナオが窓を開けた。', 'ナオは窓を開けたか？'),
                             ('ナオが窓を開ける。', 'ナオは窓を開けるか？')]:
        result = Vera.from_texts({'d': source}, mode='semantic').ask(question)
        assert result['verdict'] == 'ANSWER' and result['values'] == ['はい']


# から (origin) is now read, so the unsupported example is an adverb instead
@pytest.mark.parametrize('raw', ['ナオはリクに青鍵をそっと渡した。', 'ナオはリクに青鍵を二つ渡した。'])
def test_checker_does_not_trust_reader_coverage_flags(raw):
    view = document_view({'d': raw})
    clause = view.clauses[0]
    assert clause.unsupported
    corrupted = replace(clause, unsupported=())
    with pytest.raises(Rejected, match='unlicensed source content'):
        Checker(View(view.sources, (corrupted,)), 'document', Meter())._source(corrupted)


def test_numeric_entity_names_remain_supported():
    result = Vera.from_texts({'d': '第2班がミオに予備鍵を渡した。'}, mode='semantic').ask('誰がミオに予備鍵を渡した？')
    assert result['verdict'] == 'ANSWER' and result['values'] == ['第2班']


def test_checker_rejects_interrogative_even_with_asserting_canonical_clause():
    raw = 'ナオは窓を開けた。'
    view = document_view({'d': raw}); clause = view.clauses[0]
    changed = raw[:-1] + '？'
    forged = replace(clause, span=replace(clause.span, text=changed),
                     body_span=replace(clause.body_span, text=changed))
    with pytest.raises(Rejected, match='interrogative'):
        Checker(View({'d': changed}, (forged,)), 'document', Meter())._source(forged)


def test_compound_verb_preserves_past_tense_without_losing_relative_role():
    result = Vera.from_texts({'d': 'ユキがソラに銅鍵を渡した。'}, mode='semantic').ask('鍵を受け取った人は？')
    assert result['verdict'] == 'ANSWER' and result['values'] == ['ソラ']
    past = document_view({'d': 'ソラが銅鍵を受け取った。'}).clauses[0]
    assert past.time == 'past'
    Checker(View({'d': 'ソラが銅鍵を受け取った。'}, (past,)), 'document', Meter())._source(past)
    forged = replace(past, time='nonpast')
    with pytest.raises(Rejected, match='tense licensing'):
        Checker(View({'d': 'ソラが銅鍵を受け取った。'}, (forged,)), 'document', Meter())._source(forged)


def test_document_semantic_answer_needs_no_network_or_external_process(monkeypatch):
    import socket
    import subprocess
    def forbidden(*args, **kwargs):
        raise AssertionError('external runtime dependency invoked')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = Vera.from_texts({'d': 'ミオの居室は北棟。'}, mode='semantic').ask('ミオの居室はどこ？')
    assert result['verdict'] == 'ANSWER' and result['values'] == ['北棟']
    assert result['semantic']['verified']


@pytest.mark.parametrize('qualifier', ['三つ', '倉庫から', '素早く', 'ゆっくり'])
def test_unrepresented_guard_content_never_disappears(qualifier):
    raw = f'ナオが窓を{qualifier}開けた場合、ミオが扉を開ける。ナオが窓を開けた。'
    r = Vera.from_texts({'d': raw}, mode='semantic').ask('ミオは扉を開けるか？')
    assert r['verdict'] != 'ANSWER' and r['values'] == []


@pytest.mark.parametrize('source,expected', [('ハルが資料を確認した。', 'はい'),
                                           ('ハルが資料を確認しなかった。', 'いいえ')])
def test_sahen_predicate_components_are_represented(source, expected):
    r = Vera.from_texts({'d': source}, mode='semantic').ask('ハルは資料を確認したか？')
    assert r['verdict'] == 'ANSWER' and r['values'] == [expected]


def test_volition_is_not_a_nonpast_assertion():
    v = Vera.from_texts({'d': 'ナオが窓を開けよう。'}, mode='semantic')
    assert v.ask('ナオは窓を開けるか？')['verdict'] != 'ANSWER'
    actual = Vera.from_texts({'d': 'ナオが窓を開ける。'}, mode='semantic')
    assert actual.ask('ナオは窓を開けようか？')['verdict'] == 'UNKNOWN_UNREAD'


@pytest.mark.parametrize('raw,guard,roles', [
    ('ハルが窓を三つ開けた場合、ユウが扉を開ける。ハルが窓を開けた。',
     'ハルが窓を開けた', (('agent', 'ハル'), ('patient', '窓'))),
    ('窓をハルが開けた場合、ユウが扉を開ける。ハルが扉を開けた。',
     'ハルが開けた', (('agent', 'ハル'),)),
])
def test_checker_binds_condition_to_entire_original_antecedent(raw, guard, roles):
    view = document_view({'d': raw}); clause = view.clauses[0]
    start = raw.index(guard)
    forged = replace(clause, unsupported=(),
                     conditions=(Pattern('開ける', roles, '+', 'assert', 'past'),),
                     condition_spans=(Span('d', start, start+len(guard), guard),))
    with pytest.raises(Rejected, match='condition full-prefix scope'):
        Checker(View(view.sources, (forged, *view.clauses[1:])), 'document', Meter())._source(forged)


@pytest.mark.parametrize('prefix', ['', '  '])
def test_whole_supported_antecedent_retains_valid_answers(prefix):
    raw = prefix+'ソラが来た場合、ユキが窓を開ける。ソラが来た。'
    result = Vera.from_texts({'d': raw}, mode='semantic').ask('ユキは窓を開けるか？')
    assert result['verdict'] == 'ANSWER' and result['values'] == ['はい']

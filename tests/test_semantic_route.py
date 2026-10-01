"""Leaf routing (stereo-cross reach index) must never change what the flat view would answer except by saving budget."""
import random

import pytest

from verantyx import semantic_route
from verantyx.one import Vera


def noise(n, start=0):
    return {f'n{start + i}': f'ノイズ{i}番の{["鍵","箱","紙","札"][i % 4]}{start + i}は倉庫{start + i}にある。' for i in range(n)}


def both(docs, question):
    out = []
    for floor in (10 ** 9, 7):                       # flat first, then routed
        semantic_route.ROUTE_MIN_LEAVES = floor
        v = Vera.from_texts(docs, mode='semantic')
        try:
            a = v.ask(question)
        finally:
            v.close()
        route = [s for s in a.get('trace', []) if s.get('part') == 'semantic_route.LeafTree']
        out.append((a['verdict'], a.get('values'), route[0] if route else None))
    semantic_route.ROUTE_MIN_LEAVES = 7
    return out


def same(docs, question):
    (fv, fval, _), (rv, rval, route) = both(docs, question)
    assert (fv, fval) == (rv, rval), (question, fv, fval, rv, rval)
    return fv, fval, route


def test_unique_answer_is_the_same_and_routed():
    docs = {**noise(30), 'a': 'ミオは青鍵をリクに渡した。'}
    v, val, route = same(docs, '青鍵をリクに渡したのは？')
    assert (v, val) == ('ANSWER', ['ミオ'])
    assert route['status'] == 'routed' and route['reached_leaves'] <= 3


def test_conflicting_documents_are_both_consulted():
    docs = {**noise(30), 'a': 'ミオは青鍵をリクに渡した。', 'b': 'ミオは青鍵をナオに渡した。', 'c': 'ユキは青鍵をリクに渡した。'}
    v, val, route = same(docs, '青鍵をリクに渡したのは？')
    assert v != 'ANSWER'                              # ミオ and ユキ both claim it: ambiguity must survive routing


def test_negation_in_another_document_still_conflicts():
    docs = {**noise(30), 'a': 'ミオは窓を開けた。', 'b': 'ミオは窓を開けなかった。'}
    v, val, _ = same(docs, 'ミオは窓を開けた？')
    assert v != 'ANSWER'


def test_unread_sentence_that_mentions_the_anchor_still_gates():
    # a sentence with no predicate is an Unread span (it gates the flat view); it mentions both anchors
    docs = {**noise(30), 'a': 'ミオは青鍵をリクに渡した。', 'b': '青鍵とリクの件。'}
    v, val, _ = same(docs, '青鍵をリクに渡したのは？')
    assert v != 'ANSWER'


def test_unread_elsewhere_does_not_block_a_clean_answer():
    docs = {**noise(30), 'a': 'ミオは青鍵をリクに渡した。', 'z': '赤箱とゲンの件。'}
    (fv, _, _), (rv, rval, _) = both(docs, '青鍵をリクに渡したのは？')
    assert fv != 'ANSWER' and (rv, rval) == ('ANSWER', ['ミオ'])      # the flat view refuses because of the unrelated unread


def test_two_hop_across_documents_follows_a_rare_entity():
    docs = {**noise(30), 'a': 'ミオの上司はリクだ。', 'b': 'リクの部署は開発だ。'}
    v, val, _ = same(docs, 'ミオの上司の部署は？')
    assert (v, val) == ('ANSWER', ['開発'])


def test_condition_in_another_document_is_found():
    docs = {**noise(30), 'a': '端末が認証済みならリオは扉を開けられる。', 'b': '端末は認証済み。'}
    same(docs, 'リオは扉を開けられる？')


def test_out_of_corpus_anchor_abstains_like_the_flat_view():
    docs = {**noise(30), 'a': 'ミオは青鍵をリクに渡した。'}
    v, val, _ = same(docs, '白紙をヨウに渡したのは？')
    assert v != 'ANSWER'


def test_common_entity_is_not_followed_and_never_creates_an_answer():
    docs = {f'd{i}': f'係員は札{i}を倉庫に置いた。' for i in range(40)}
    docs['x'] = 'ミオは札7をリクに渡した。'
    (fv, fval, _), (rv, rval, _) = both(docs, '札7をリクに渡したのは？')
    assert rv in ('ANSWER', fv) or rv.startswith('UNKNOWN')
    if rv == 'ANSWER': assert rval == ['ミオ']


POOL_A = ['ミオ', 'リク', 'ナオ', 'ユキ', 'ケン']
POOL_O = ['青鍵', '赤箱', '白紙']


def random_corpus(rnd, n):
    docs = {}
    unread = []
    for i in range(n):
        sentences = []
        for _ in range(rnd.randint(1, 2)):
            a, b, o = rnd.sample(POOL_A, 2) + [rnd.choice(POOL_O)]
            if rnd.random() < 0.12:
                s = f'{o}と{b}の件。'; unread.append(s)                      # no predicate: an Unread span
            elif rnd.random() < 0.1:
                s = f'{a}は{o}を{b}に渡さなかった。'
            else:
                s = f'{a}は{o}を{b}に渡した。'
            sentences.append(s)
        docs[f'd{i}'] = ''.join(sentences)
    return docs, unread


@pytest.mark.parametrize('seed', range(6))
def test_random_corpora_never_diverge_from_the_flat_view(seed):
    rnd = random.Random(seed)
    docs, unread = random_corpus(rnd, 40)
    for _ in range(10):
        a, b, o = rnd.sample(POOL_A, 2) + [rnd.choice(POOL_O)]
        q = f'{o}を{b}に渡したのは？'
        (fv, fval, _), (rv, rval, _) = both(docs, q)
        if rv == 'ANSWER':
            if fv == 'ANSWER': assert rval == fval, (q, fval, rval)
            else:
                # the flat view refused: the only allowed reason is unread text elsewhere that does not mention the anchors
                assert fv in ('UNKNOWN_UNSUPPORTED_EVIDENCE', 'UNKNOWN_BUDGET', 'UNKNOWN_UNREAD'), (q, fv, rv)
                assert not any(o in s and b in s for s in unread), (q, 'unread mentioning both anchors was ignored')
        else:
            assert fv != 'ANSWER' or rv.startswith('UNKNOWN'), (q, fv, rv)


def test_one_malformed_unsupported_sentence_elsewhere_does_not_poison_every_answer():
    # two で-phrases in one unsupported clause used to make the whole view invalid (real Wikipedia text does this)
    docs = {'a': 'ミオは青鍵をリクに渡した。', 'b': '武蔵堆での調査では、6歳での性転換後、隔年で産卵を行う。', 'c': 'ホシはゲンに赤箱を渡した。'}
    for floor in (10 ** 9, 7):
        semantic_route.ROUTE_MIN_LEAVES = floor
        v = Vera.from_texts(docs, mode='semantic')
        a = v.ask('青鍵をリクに渡したのは？'); v.close()
        assert a['verdict'] == 'ANSWER' and a['values'] == ['ミオ'], (floor, a['verdict'], a.get('reason'))
    semantic_route.ROUTE_MIN_LEAVES = 7


def test_clause_with_two_locative_phrases_is_unsupported_not_view_poisoning():
    docs = {'a': 'ミオは青鍵をリクに渡した。', 'b': 'また、1996年の世界選手権では混合団体戦で優勝した。', 'c': 'ホシはゲンに赤箱を渡した。'}
    for floor in (10 ** 9, 7):
        semantic_route.ROUTE_MIN_LEAVES = floor
        v = Vera.from_texts(docs, mode='semantic')
        assert not v._semantic_view.invalid
        a = v.ask('青鍵をリクに渡したのは？'); v.close()
        assert a['verdict'] == 'ANSWER' and a['values'] == ['ミオ']
    semantic_route.ROUTE_MIN_LEAVES = 7


def test_over_deep_request_is_a_typed_refusal_not_an_exception():
    v = Vera.from_texts({'d': 'ミオは青鍵をリクに渡した。'}, mode='semantic')
    a = v.ask('甲の乙の丙の丁の戊の己の庚の辛の壬の癸の名前は？')
    v.close()
    assert a['verdict'].startswith('UNKNOWN') and a['verdict'] != 'ANSWER'

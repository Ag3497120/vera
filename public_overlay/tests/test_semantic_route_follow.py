"""Regression coverage for clause-level entity following in semantic routing."""
from __future__ import annotations

import pytest

from verantyx import question, semantic_route
from verantyx.semantic import answer
from verantyx.semantic_ir import Budget, Span, Unread, View
from verantyx.semantic_reader import document_view


BIG = Budget(parse=32, depth=8, candidates=10 ** 7, bindings=64, steps=10 ** 9)
INSTRUCTION = 'document instruction excluded'


def _view(texts: dict[str, str], *, seed: int, extra_unread=()) -> View:
    """Parse the generated facts and add opaque leaves to exercise the real route tree."""
    parsed = document_view(texts)
    sources = dict(parsed.sources)
    unread = list(parsed.unread) + list(extra_unread)
    for index in range(6):
        source = f'opaque_{seed}_{index}'
        text = f'opaque background token {seed} {index}'
        sources[source] = text
        unread.append(Unread(Span(source, 0, len(text), text), 'synthetic opaque source'))
    return View(sources, parsed.clauses, tuple(unread), parsed.ingest_ms)


def _oracle(request, view: View):
    anchors_by_pattern = semantic_route.pattern_anchors(request)
    anchors = set().union(*anchors_by_pattern) if anchors_by_pattern else set()
    gating = tuple(u for u in view.unread
                   if u.reason == INSTRUCTION or any(anchor in u.span.text for anchor in anchors))
    flat = View(view.sources, view.clauses, gating, view.ingest_ms)
    return answer(request, [flat], budget=BIG)


def _routed(request, view: View, *, expand_cap: int = 8):
    tree = semantic_route.LeafTree(view)
    routed, trace = tree.restrict(request, expand_cap=expand_cap)
    return (routed if routed is not None else view), trace


def _generated_two_hop(seed: int) -> tuple[View, str, str]:
    actors = ('青葉', '緑川', '小林', '東雲', '桜井', '白石', '北原', '高木')
    intermediates = ('白峰', '黒川', '南川', '松岡', '森下', '橘', '高橋', '赤松')
    departments = ('企画室', '開発室', '総務課', '広報部', '人事部', '経理課', '営業部', '技術部')
    side_terms = ('花園', '湖畔', '港町', '古書', '庭園', '並木道', '駅前', '遊歩道')
    actor = actors[seed % len(actors)]
    bridge = intermediates[seed % len(intermediates)]
    result = departments[seed % len(departments)]
    side = side_terms[seed % len(side_terms)]
    side_source = f'anchor_mention_{seed}'
    side_text = f'{actor}は{side}を歩く。 broken note {side}'
    marker = f'broken note {side}'
    start = side_text.index(marker)
    unread = Unread(Span(side_source, start, start + len(marker), marker), 'synthetic unread side text')
    texts = {
        f'chain_first_{seed}': f'{actor}の上司は{bridge}だ。',
        f'chain_second_{seed}': f'{bridge}の部署は{result}だ。',
        side_source: side_text,
    }
    return _view(texts, seed=seed, extra_unread=(unread,)), actor, result


@pytest.mark.parametrize('seed', range(32))
def test_generated_rare_two_hop_route_matches_flat_oracle(seed, monkeypatch):
    """An unrelated predicate in an anchor leaf must not drag its unread side text into the answer."""
    monkeypatch.setattr(semantic_route, 'EVIDENCE_UNREAD', 'mention')
    view, actor, _ = _generated_two_hop(seed)
    request = question.read_semantic(f'{actor}の上司の部署は？').value
    flat = _oracle(request, view)
    routed_view, trace = _routed(request, view)
    routed = answer(request, [routed_view], budget=BIG, trace=(trace,))

    assert flat['verdict'] == 'ANSWER'
    assert routed['verdict'] == flat['verdict']
    assert routed.get('values') == flat.get('values')
    assert f'anchor_mention_{seed}' in routed_view.sources
    assert not any(u.span.source == f'anchor_mention_{seed}' for u in routed_view.unread)


def test_unrelated_unread_in_anchor_mention_does_not_block_rare_chain(monkeypatch):
    monkeypatch.setattr(semantic_route, 'EVIDENCE_UNREAD', 'mention')
    view, actor, expected = _generated_two_hop(0)
    request = question.read_semantic(f'{actor}の上司の部署は？').value
    flat = _oracle(request, view)
    routed_view, trace = _routed(request, view)
    routed = answer(request, [routed_view], budget=BIG, trace=(trace,))

    assert flat['values'] == [expected]
    assert routed['verdict'] == 'ANSWER'
    assert routed['values'] == flat['values']
    assert not any(u.span.source == 'anchor_mention_0' for u in routed_view.unread)


def test_other_predicate_cannot_hand_its_terms_to_the_entity_walk(monkeypatch):
    monkeypatch.setattr(semantic_route, 'EVIDENCE_UNREAD', 'mention')
    view, actor, expected = _generated_two_hop(3)
    request = question.read_semantic(f'{actor}の上司の部署は？').value
    routed_view, trace = _routed(request, view)
    result = answer(request, [routed_view], budget=BIG, trace=(trace,))

    assert result['verdict'] == 'ANSWER'
    assert result['values'] == [expected]
    assert f'anchor_mention_3' in routed_view.sources
    assert not any(u.span.source == 'anchor_mention_3' for u in routed_view.unread)


def test_three_hop_chain_is_followed_to_its_answer(monkeypatch):
    monkeypatch.setattr(semantic_route, 'EVIDENCE_UNREAD', 'mention')
    texts = {
        'hop_1': '青葉の上司は白峰だ。',
        'hop_2': '白峰の部署は企画室だ。',
        'hop_3': '企画室の所在地は北町だ。',
    }
    view = _view(texts, seed=40)
    request = question.read_semantic('青葉の上司の部署の所在地は？').value
    flat = _oracle(request, view)
    routed_view, trace = _routed(request, view)
    routed = answer(request, [routed_view], budget=BIG, trace=(trace,))

    assert flat['verdict'] == 'ANSWER'
    assert flat['values'] == ['北町']
    assert routed['verdict'] == flat['verdict']
    assert routed['values'] == flat['values']
    assert trace['rounds'] >= 3


def test_guard_terms_reach_their_supporting_fact(monkeypatch):
    monkeypatch.setattr(semantic_route, 'EVIDENCE_UNREAD', 'mention')
    view = _view({
        'guarded_action': '白峰が認証済みならソリは扉を開けられる。',
        'guard_fact': '白峰は認証済み。',
    }, seed=41)
    request = question.read_semantic('ソリは扉を開けられる？').value
    routed_view, trace = _routed(request, view)

    assert 'guard_fact' in routed_view.sources
    assert trace['followed_terms'] >= 1


def test_common_entity_is_recorded_but_not_followed(monkeypatch):
    monkeypatch.setattr(semantic_route, 'EVIDENCE_UNREAD', 'mention')
    texts = {
        'first': '青葉の上司は白峰だ。',
        'next': '白峰の部署は企画室だ。',
        'common_1': '白峰の趣味は釣りだ。',
        'common_2': '白峰の出身は北町だ。',
        'common_3': '白峰の担当は広報部だ。',
        'common_4': '白峰の所属は総務課だ。',
        'common_5': '白峰の役職は部長だ。',
    }
    view = _view(texts, seed=42)
    request = question.read_semantic('青葉の上司の部署は？').value
    routed_view, trace = _routed(request, view, expand_cap=2)

    assert trace['common_terms'] >= 1
    assert 'next' not in routed_view.sources


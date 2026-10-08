#!/usr/bin/env python3
"""Measure EXPAND_CAP on two-hop joins and cross-document guards over Wikipedia leads.

The oracle deliberately matches tools/round5a_route_tune.py: every readable clause
is visible with an unlimited budget, while only unread spans that mention a request
anchor gate the answer. Synthetic documents are appended under unique source keys.
"""
from __future__ import annotations

import collections
import json
import math
import random
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, '.')

from round5a_route_tune import load
from verantyx import question, semantic_route
from verantyx.semantic import answer
from verantyx.semantic_ir import Budget, View
from verantyx.semantic_reader import _tagger, document_view


CAPS = (2, 4, 8, 32, 128)
EVIDENCE_MODES = ('mention', 'all')
DATASETS = ((4000, 300), (16000, 80))
TRIALS = 60
BIG = Budget(parse=32, depth=8, candidates=10 ** 7, bindings=64, steps=10 ** 9)
REPORT = Path('/Users/motonishikoudai/Projects/vera-round5-run/phase2/join_tune_report.md')
INSTRUCTION = 'document instruction excluded'
KATAKANA_DIGITS = ('ア', 'イ', 'ウ', 'エ', 'オ', 'カ', 'キ', 'ク', 'ケ', 'コ',
                   'サ', 'シ', 'ス', 'セ', 'ソ', 'タ')


def doc_frequency(term: str, docs: dict[str, str]) -> int:
    """Exact, case-sensitive document mentions, including text the reader left unread."""
    return sum(term in text for text in docs.values())


def entity_role_terms(view: View) -> dict[str, set[str]]:
    """Map literal clause/guard terms to the background leaves that hold them."""
    held: dict[str, set[str]] = collections.defaultdict(set)
    entity_roles = {'entity', 'agent', 'patient', 'recipient', 'origin', 'location'}
    for clause in view.clauses:
        for role in clause.roles:
            if role.name in entity_roles and isinstance(role.term, str) and role.term:
                held[role.term].add(clause.span.source)
        for pattern in (*clause.conditions, *clause.exceptions):
            for name, term in pattern.roles:
                if name in entity_roles and isinstance(term, str) and term:
                    held[term].add(clause.span.source)
    return held


def valid_entity(term: str) -> bool:
    if not 2 <= len(term) <= 12 or 'の' in term:
        return False
    if re.search(r'[\s、。，．！？?!「」『』（）()【】［］:：/\\]', term):
        return False
    if any(ch in term for ch in ('上司', '部署', '認証済み', '扉')):
        return False
    if not all(('\u3040' <= ch <= '\u30ff') or ('\u3400' <= ch <= '\u9fff') for ch in term):
        return False
    if not any(('\u30a0' <= ch <= '\u30ff') or ('\u3400' <= ch <= '\u9fff') for ch in term):
        return False
    return term not in {'これ', 'それ', 'あれ', 'ここ', 'そこ', 'もの', 'こと'}


def property_subjects(view: View, attribute: str) -> set[str]:
    found = set()
    for clause in view.clauses:
        if clause.predicate != 'property':
            continue
        roles = {role.name: role.term for role in clause.roles}
        if roles.get('attribute') == attribute and isinstance(roles.get('entity'), str):
            found.add(roles['entity'])
    return found


def unread_mentions(view: View, term: str) -> bool:
    return any(u.reason != INSTRUCTION and term in u.span.text for u in view.unread)


def identity_conflicts(view: View, term: str) -> bool:
    """Avoid a pre-existing contrary/unrelated identity fact for guard antecedents."""
    for clause in view.clauses:
        if clause.predicate != 'identity':
            continue
        roles = {role.name: role.term for role in clause.roles}
        if roles.get('entity') == term:
            if roles.get('value') != '認証済み' or clause.polarity != '+':
                return True
    return False


def background_entity_pool(view: View, docs: dict[str, str]) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Parsed entity surfaces with raw substring DF and clause-holder DF."""
    holders = entity_role_terms(view)
    tagger = _tagger()
    candidates = {}
    for term in holders:
        if not valid_entity(term):
            continue
        words = list(tagger(term))
        if words and all(word.feature.pos1 in ('名詞', '接頭辞', '接尾辞') for word in words):
            candidates[term] = holders[term]
    holders = candidates
    frequencies = {term: doc_frequency(term, docs) for term in holders}
    return holders, frequencies


def choose_frequency_terms(view: View, holders: dict[str, set[str]], frequencies: dict[str, int],
                           band: str, count: int, rng: random.Random, *,
                           excluded: set[str], purpose: str) -> list[tuple[str, int, int]]:
    """Select by raw background text frequency and retain the router's holder DF.

    Common raw mentions often do not appear as interpreted clause roles. That is a
    behavior to measure, so holder DF is deliberately not a second selection gate.
    Repeated entities are isolated in per-trial views and cannot cross-contaminate
    another question's oracle or route count.
    """
    if band == 'rare':
        raw_pred = lambda n: n < 5
    elif band == 'mid':
        raw_pred = lambda n: 5 <= n <= 64
    elif band == 'common':
        raw_pred = lambda n: n > 128
    else:
        raise ValueError(band)

    boss_entities = property_subjects(view, '上司') if purpose == 'chain_e1' else set()
    candidates = [term for term, raw_df in frequencies.items()
                  if valid_entity(term) and term not in excluded and raw_pred(raw_df)]
    rng.shuffle(candidates)
    selected = []
    for term in candidates:
        if purpose == 'chain_e1':
            if not holders.get(term) or term in boss_entities or unread_mentions(view, term):
                continue
        selected.append((term, frequencies[term], len(holders.get(term, ())))
                        )
    if not selected:
        raise RuntimeError(f'No eligible {band} {purpose} entity surfaces in the background.')
    if purpose == 'chain_e1' and len(selected) < count:
        raise RuntimeError(f'Only {len(selected)} unique rare E1 entities; need {count}.')
    return [selected[i % len(selected)] for i in range(count)]


def synthetic_name(kind: str, index: int) -> str:
    prefix = {'hop': 'ルメ', 'result': 'ネカ', 'guard_actor': 'ソリ'}[kind]
    digits = []
    n = index
    while n:
        digits.append(KATAKANA_DIGITS[n % len(KATAKANA_DIGITS)])
        n //= len(KATAKANA_DIGITS)
    if not digits:
        digits.append(KATAKANA_DIGITS[0])
    return prefix + ''.join(reversed(digits)) + 'ナ'


def build_trials(n: int, view: View, holders: dict[str, set[str]], frequencies: dict[str, int],
                 seed: int) -> list[dict]:
    rng = random.Random(seed + n)
    total_chain_e1 = TRIALS * 3
    rare_e1 = choose_frequency_terms(view, holders, frequencies, 'rare', total_chain_e1, rng,
                                     excluded=set(), purpose='chain_e1')
    used = {term for term, _, _ in rare_e1}
    trials = []
    serial = 0

    for band in ('rare', 'mid', 'common'):
        if band == 'rare':
            e2_rows = [(synthetic_name('hop', n * 10000 + serial + i), 0, 0)
                       for i in range(TRIALS)]
        else:
            e2_rows = choose_frequency_terms(view, holders, frequencies, band, TRIALS, rng,
                                             excluded=used, purpose='chain_e2')
        for i in range(TRIALS):
            e1, e1_raw, e1_roles = rare_e1[len(trials) % total_chain_e1]
            e2, e2_raw, e2_roles = e2_rows[i]
            e3 = synthetic_name('result', n * 10000 + serial)
            x = f'join_{n}_{band}_{i:03d}_X'
            y = f'join_{n}_{band}_{i:03d}_Y'
            trials.append({
                'shape': 'two-hop', 'frequency': band, 'gold': e3,
                'question': f'{e1}の上司の部署は？', 'sources': (x, y),
                'texts': {x: f'{e1}の上司は{e2}だ。', y: f'{e2}の部署は{e3}だ。'},
                'entities': {'E1': e1, 'E2': e2, 'E3': e3},
                'background_df': {'E1_raw': e1_raw, 'E1_clause': e1_roles,
                                  'E2_raw': e2_raw, 'E2_clause': e2_roles},
            })
            serial += 1

    for band in ('rare', 'mid', 'common'):
        e4_rows = choose_frequency_terms(view, holders, frequencies, band, TRIALS, rng,
                                         excluded=set(), purpose='guard_e4')
        for i, (e4, e4_raw, e4_roles) in enumerate(e4_rows):
            e5 = synthetic_name('guard_actor', n * 10000 + serial)
            p = f'guard_{n}_{band}_{i:03d}_P'
            q = f'guard_{n}_{band}_{i:03d}_Q'
            trials.append({
                'shape': 'guard', 'frequency': band, 'gold': 'はい',
                'question': f'{e5}は扉を開けられる？', 'sources': (p, q),
                'texts': {p: f'{e4}が認証済みなら{e5}は扉を開けられる。',
                          q: f'{e4}は認証済み。'},
                'entities': {'E4': e4, 'E5': e5},
                'background_df': {'E4_raw': e4_raw, 'E4_clause': e4_roles},
            })
            serial += 1
    return trials


def merge_views(base: View, injected: View) -> View:
    return View({**base.sources, **injected.sources}, base.clauses + injected.clauses,
                base.unread + injected.unread, base.ingest_ms + injected.ingest_ms)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def verdict_counts(items: list[dict]) -> dict[str, int]:
    return dict(sorted(collections.Counter(item['oracle']['verdict'] for item in items).items()))


def oracle_reason_counts(items: list[dict]) -> dict[str, int]:
    reasons = collections.Counter()
    for item in items:
        result = item['oracle']
        if result['verdict'] != 'ANSWER':
            reason = result.get('reason') or result.get('phase') or 'no reason supplied'
            reasons[reason] += 1
    return dict(reasons.most_common(5))


def make_oracle(view: View, injected: View, trial: dict) -> None:
    semantic_route.ROUTE_MIN_LEAVES = 10 ** 9
    req = question.read_semantic(trial['question']).value
    anchors_by_pattern = semantic_route.pattern_anchors(req)
    anchors = set().union(*anchors_by_pattern) if anchors_by_pattern else set()
    gating = tuple(u for u in view.unread
                   if u.reason == INSTRUCTION or any(a in u.span.text for a in anchors))
    oracle_view = View(view.sources, view.clauses, gating, view.ingest_ms)
    result = answer(req, [oracle_view], budget=BIG)
    trial['request'] = req
    trial['anchors'] = sorted(anchors)
    trial['request_unread'] = [{'text': item.span.text, 'reason': item.reason} for item in req.unread]
    trial['oracle'] = {'verdict': result['verdict'], 'values': result.get('values', []),
                       'reason': result.get('reason'), 'phase': result.get('phase')}
    trial['oracle_gold'] = result['verdict'] == 'ANSWER' and result.get('values') == [trial['gold']]
    trial['request_patterns'] = [
        {'predicate': node.pattern.predicate, 'modality': node.pattern.modality,
         'roles': [(name, str(term)) for name, term in node.pattern.roles]}
        for plan in req.plans for node in plan.nodes if node.pattern is not None
    ]
    trial['source_profiles'] = [
        {'source': source, 'clauses': [
            {'predicate': clause.predicate, 'modality': clause.modality,
             'roles': [(role.name, str(role.term)) for role in clause.roles],
             'conditions': [{'predicate': pattern.predicate, 'modality': pattern.modality,
                             'roles': [(name, str(term)) for name, term in pattern.roles]}
                            for pattern in clause.conditions],
             'unsupported': list(clause.unsupported)}
            for clause in injected.clauses if clause.span.source == source
        ]}
        for source in trial['sources']
    ]
    semantic_route.ROUTE_MIN_LEAVES = 7


def route_and_score(tree, view: View, trial: dict, cap: int, evidence: str, leaf_count: int) -> dict:
    semantic_route.ANCHOR_CAP = 128
    semantic_route.EXPAND_CAP = cap
    semantic_route.UNREAD_CAP = 1024
    semantic_route.EVIDENCE_UNREAD = evidence
    start = time.perf_counter()
    routed, info = tree.restrict(trial['request'])
    active = routed if routed is not None else view
    result = answer(trial['request'], [active], budget=BIG, trace=(info,))
    elapsed_ms = (time.perf_counter() - start) * 1000
    reached = info.get('reached_leaves', leaf_count if routed is None else len(routed.sources))
    oracle = trial['oracle']
    routed_answer = result['verdict'] == 'ANSWER'
    violation = bool(routed_answer and
                     (oracle['verdict'] != 'ANSWER' or result.get('values') != oracle.get('values')))
    hit = bool(oracle['verdict'] == 'ANSWER' and routed_answer and
               result.get('values') == oracle.get('values'))
    return {
        'verdict': result['verdict'], 'values': result.get('values', []),
        'route': info, 'elapsed_ms': elapsed_ms, 'reach': reached,
        'violation': violation, 'hit': hit,
        'oracle_answerable': oracle['verdict'] == 'ANSWER',
        'gold': routed_answer and result.get('values') == [trial['gold']],
    }


def run_dataset(n: int, stride: int, seed: int) -> tuple[list[dict], dict]:
    started = time.perf_counter()
    docs = load(n, stride)
    if len(docs) != n:
        print(f'WARNING: load({n}, {stride}) returned {len(docs)} documents', flush=True)
    print(json.dumps({'stage': 'load', 'requested': n, 'loaded': len(docs)}, ensure_ascii=False), flush=True)

    t = time.perf_counter()
    background = document_view(docs)
    background_parse_s = time.perf_counter() - t
    print(json.dumps({'stage': 'background_parsed', 'n': n, 'clauses': len(background.clauses),
                      'unread': len(background.unread), 'seconds': round(background_parse_s, 1)},
                     ensure_ascii=False), flush=True)

    t = time.perf_counter()
    holders, frequencies = background_entity_pool(background, docs)
    entity_pool_s = time.perf_counter() - t
    print(json.dumps({'stage': 'entity_pool_ready', 'n': n, 'candidate_terms': len(frequencies),
                      'raw_common_terms': sum(df > 128 for df in frequencies.values()),
                      'seconds': round(entity_pool_s, 1)}, ensure_ascii=False), flush=True)

    trials = build_trials(n, background, holders, frequencies, seed)
    if len(trials) != 6 * TRIALS:
        raise AssertionError(f'expected {6 * TRIALS} trials, got {len(trials)}')
    print(json.dumps({'stage': 'trials_ready', 'n': n, 'trials': len(trials),
                      'unique_E1': len({t['entities']['E1'] for t in trials if t['shape'] == 'two-hop'}),
                      'unique_E2_by_band': {band: len({t['entities']['E2'] for t in trials
                                                       if t['shape'] == 'two-hop' and t['frequency'] == band})
                                            for band in ('rare', 'mid', 'common')},
                      'unique_E4_by_band': {band: len({t['entities']['E4'] for t in trials
                                                       if t['shape'] == 'guard' and t['frequency'] == band})
                                            for band in ('rare', 'mid', 'common')}},
                     ensure_ascii=False), flush=True)

    group_results = collections.defaultdict(list)
    tree_build_times = []
    leaf_counts = []
    injected_parse_s = 0.0
    clauses_injected = 0
    unread_injected = 0
    for index, trial in enumerate(trials, 1):
        t = time.perf_counter()
        injected = document_view(trial['texts'])
        injected_parse_s += time.perf_counter() - t
        clauses_injected += len(injected.clauses)
        unread_injected += len(injected.unread)
        view = merge_views(background, injected)
        make_oracle(view, injected, trial)
        t = time.perf_counter()
        tree = semantic_route.LeafTree(view)
        build_ms = (time.perf_counter() - t) * 1000
        tree_build_times.append(build_ms)
        leaf_counts.append(len(tree.leaves))
        for evidence in EVIDENCE_MODES:
            for cap in CAPS:
                scored = route_and_score(tree, view, trial, cap, evidence, len(tree.leaves))
                group_results[(trial['shape'], trial['frequency'], evidence, cap)].append((trial, scored))
        tree.root = None
        del tree, view, injected
        if index % 30 == 0:
            print(json.dumps({'stage': 'trial_progress', 'n': n, 'completed': index,
                              'total': len(trials),
                              'oracle_answerable': sum(x.get('oracle', {}).get('verdict') == 'ANSWER'
                                                       for x in trials[:index])},
                             ensure_ascii=False), flush=True)

    oracle_gold = sum(item['oracle_gold'] for item in trials)
    oracle_groups = []
    for shape in ('two-hop', 'guard'):
        for band in ('rare', 'mid', 'common'):
            group = [item for item in trials if item['shape'] == shape and item['frequency'] == band]
            entity_key = 'E2' if shape == 'two-hop' else 'E4'
            oracle_groups.append({'shape': shape, 'frequency': band,
                                  'verdicts': verdict_counts(group),
                                  'gold_answers': sum(item['oracle_gold'] for item in group),
                                  'unique_entities': len({item['entities'][entity_key] for item in group}),
                                  'abstention_reasons': oracle_reason_counts(group)})
    print(json.dumps({'stage': 'oracles_ready', 'n': n, 'trials': len(trials),
                      'oracle_answerable': sum(x['oracle']['verdict'] == 'ANSWER' for x in trials),
                      'oracle_gold': oracle_gold, 'groups': oracle_groups}, ensure_ascii=False), flush=True)

    summaries = []
    for evidence in EVIDENCE_MODES:
        for cap in CAPS:
            for shape in ('two-hop', 'guard'):
                for band in ('rare', 'mid', 'common'):
                    pairs = group_results[(shape, band, evidence, cap)]
                    per_trial = [score for _, score in pairs]
                    oracle_answerable = sum(s['oracle_answerable'] for s in per_trial)
                    recall_hits = sum(s['hit'] for s in per_trial)
                    routes = [s['route'] for s in per_trial]
                    route_counts = collections.Counter(
                        'route:' + str(info.get('status')) +
                        ('/' + info['reason'] if info.get('reason') else '') for info in routes)
                    fallbacks = {k: v for k, v in route_counts.items() if not k.startswith('route:routed')}
                    reach = [s['reach'] for s in per_trial]
                    times = [s['elapsed_ms'] for s in per_trial]
                    summaries.append({
                        'n': n, 'shape': shape, 'frequency': band, 'evidence': evidence, 'expand': cap,
                        'trials': len(pairs), 'oracle_answerable': oracle_answerable,
                        'oracle_abstains': len(pairs) - oracle_answerable,
                        'recall_hits': recall_hits,
                        'recall_pct': (round(100 * recall_hits / oracle_answerable, 1)
                                       if oracle_answerable else None),
                        'violations': sum(s['violation'] for s in per_trial),
                        'routed_answers': sum(s['verdict'] == 'ANSWER' for s in per_trial),
                        'gold_answers': sum(s['gold'] for s in per_trial),
                        'reach_median': statistics.median(reach) if reach else None,
                        'reach_p95': percentile(reach, .95),
                        'median_ms': statistics.median(times) if times else None,
                        'p95_ms': percentile(times, .95),
                        'fallbacks': fallbacks,
                        'route_statuses': dict(route_counts),
                    })
            print(json.dumps({'stage': 'sweep_done', 'n': n, 'evidence': evidence, 'expand': cap},
                             ensure_ascii=False), flush=True)

    tree_build_ms = statistics.median(tree_build_times)
    metadata = {
        'n': n, 'stride': stride, 'loaded': len(docs),
        'background_parse_s': background_parse_s, 'entity_pool_s': entity_pool_s,
        'injected_parse_s': injected_parse_s, 'tree_build_ms': tree_build_ms,
        'tree_build_p95_ms': percentile(tree_build_times, .95), 'tree_build_count': len(tree_build_times),
        'leaves': f'{min(leaf_counts)}–{max(leaf_counts)}',
        'clauses_background': len(background.clauses), 'unread_background': len(background.unread),
        'clauses_injected': clauses_injected, 'unread_injected': unread_injected,
        'oracle_groups': oracle_groups, 'oracle_gold': oracle_gold,
        'total_runtime_s': time.perf_counter() - started,
        'trials': [{'n': n, **{key: trial[key] for key in ('shape', 'frequency', 'entities', 'background_df',
                                                           'oracle', 'oracle_gold', 'question', 'request_unread',
                                                           'request_patterns', 'source_profiles')}}
                   for trial in trials],
    }
    return summaries, metadata


def fmt_recall(row: dict) -> str:
    denom = row['oracle_answerable']
    pct = 'n/a' if row['recall_pct'] is None else f"{row['recall_pct']:.1f}%"
    return f"{row['recall_hits']}/{denom} ({pct})"


def fmt_fallbacks(value: dict) -> str:
    if not value:
        return '—'
    return '; '.join(f'{k.removeprefix("route:")} ×{v}' for k, v in sorted(value.items()))


def report_text(summaries: list[dict], metadata: list[dict]) -> str:
    lines = [
        '# Round5-A join and guard route tuning', '',
        '## Setup', '',
        '- Backgrounds: `load(4000, 300)` and `load(16000, 80)` from the Wikipedia lead corpus; all synthetic docs use fresh keys.',
        '- Trials: 60 each for two-hop × rare/mid/common E2 and guard × rare/mid/common E4, for each background (360 per background). Every trial is evaluated against the real background plus only its own two injected documents, so repeated frequency-band entities cannot contaminate another trial.',
        '- Frequency bands use raw exact substring document frequency in background text: rare `<5`, mid `5–64`, common `>128`. Background clause-holder leaf counts are recorded separately and are not a second selection gate; the router can see fewer structured holders than raw text mentions, which is part of the measurement.',
        '- E1 comes from a parsed background role, appears in fewer than five background documents, and has no existing readable `上司` fact or unread span mentioning E1. E2 candidates are not filtered for existing department facts, so any competing background answer remains visible to the flat oracle. Question/source wording was not changed.',
        '- Fixed caps: `ANCHOR_CAP=128`, `UNREAD_CAP=1024`; sweep `EXPAND_CAP` 2/4/8/32/128 under `EVIDENCE_UNREAD=mention` and `all`. Oracle: all clauses, unlimited `Budget(parse=32, depth=8, candidates=10^7, bindings=64, steps=10^9)`, and only unread spans mentioning a request anchor (same contract as `round5a_route_tune.py`).',
        '- A `LeafTree` is built once per trial and reused across its ten cap/mode settings. Per-question timing includes `LeafTree.restrict` plus the semantic answer; per-trial tree-build median/p95 is reported separately. Fallback counts include `skipped` route calls that use the full view.',
        '', '## Dataset and oracle summary', '',
        '| N | loaded | background clauses / unread | injected clauses / unread | leaves/trial | tree build median/p95 ms | oracle gold answers | parse + run seconds |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for item in metadata:
        lines.append(f"| {item['n']} | {item['loaded']} | {item['clauses_background']} / {item['unread_background']} | {item['clauses_injected']} / {item['unread_injected']} | {item['leaves']} | {item['tree_build_ms']:.1f}/{item['tree_build_p95_ms']:.1f} | {item['oracle_gold']} / 360 | {item['total_runtime_s']:.1f} |")
    lines += ['', '### Flat oracle verdicts by trial group', '',
              '| N | shape | entity frequency | unique E2/E4 | oracle verdicts | gold-matching oracle answers | top abstention reasons |',
              '|---:|---|---|---:|---|---:|---|']
    for item in metadata:
        for group in item['oracle_groups']:
            reasons = '; '.join(f'{k} ×{v}' for k, v in group['abstention_reasons'].items()) or '—'
            verdicts = ', '.join(f'{k} {v}' for k, v in group['verdicts'].items())
            lines.append(f"| {item['n']} | {group['shape']} | {group['frequency']} | {group['unique_entities']} | {verdicts} | {group['gold_answers']} / 60 | {reasons} |")
    lines += ['', '## EXPAND_CAP results', '',
              'Recall is routed ANSWER with the same value as the flat oracle divided by oracle ANSWER count. Violations are routed ANSWER where the oracle abstains, or routed ANSWER with a different value. Reach reports median/p95 effective leaves; skipped routes count as the full view. Times are median/p95 milliseconds.', '',
              '| N | shape | freq | unread mode | cap | recall | violations | routed ANSWER | gold ANSWER | reach med/p95 | ms med/p95 | fallbacks |',
              '|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---|']
    for row in summaries:
        lines.append(
            f"| {row['n']} | {row['shape']} | {row['frequency']} | {row['evidence']} | {row['expand']} | {fmt_recall(row)} | {row['violations']} | {row['routed_answers']} / 60 | {row['gold_answers']} / 60 | {row['reach_median']:.0f}/{row['reach_p95']:.0f} | {row['median_ms']:.2f}/{row['p95_ms']:.2f} | {fmt_fallbacks(row['fallbacks'])} |"
        )

    lines += ['', '## Entity frequency audit', '',
              'Each background frequency is an exact substring count in background document text; clause DF counts background leaves whose interpreted clause/guard roles hold the term. The two synthetic documents add up to two more holder leaves for each chain E2 or guard E4 after injection.', '',
              '| N | shape | frequency | entity | raw background DF | clause-holder DF |',
              '|---:|---|---|---|---:|---:|']
    for item in metadata:
        for trial in item['trials']:
            if trial['shape'] == 'two-hop':
                d = trial['background_df']
                for name, raw_key, role_key in (('E1', 'E1_raw', 'E1_clause'), ('E2', 'E2_raw', 'E2_clause')):
                    lines.append(f"| {item['n']} | two-hop | {trial['frequency']} | {name} `{trial['entities'][name]}` | {d[raw_key]} | {d[role_key]} |")
            else:
                d = trial['background_df']
                lines.append(f"| {item['n']} | guard | {trial['frequency']} | E4 `{trial['entities']['E4']}` | {d['E4_raw']} | {d['E4_clause']} |")

    lines += ['', '## Findings and interpretation', '']
    guard_groups = [g for item in metadata for g in item['oracle_groups'] if g['shape'] == 'guard']
    if guard_groups and all(g['verdicts'].get('ANSWER', 0) == 0 for g in guard_groups):
        guard_trials = [trial for item in metadata for trial in item['trials'] if trial['shape'] == 'guard']
        pairs = collections.Counter()
        for trial in guard_trials:
            target = next((clause for profile in trial['source_profiles'][:1]
                           for clause in profile['clauses'] if clause['predicate'] == '開ける'), None)
            query = next((pattern for pattern in trial['request_patterns'] if pattern['predicate'] == '開ける'), None)
            pairs[(target['modality'] if target else 'unread/missing',
                   query['modality'] if query else 'unread/missing')] += 1
        pair_text = ', '.join(f'source {source} / question {query}: {count}'
                              for (source, query), count in sorted(pairs.items()))
        lines.append(f'The flat oracle abstained on every guard trial. The exact source shape was retained. Injected parse profiles give target-clause/question modalities `{pair_text}`; the guard condition and E4 supporting fact are parsed separately. With source modality `assert` and question modality `normative`, the semantic matcher has no compatible target clause. Because the oracle has no guard answers, guard recall is `n/a`; cap results there measure routing reach, abstention behavior, fallbacks, and latency only. This is a reader/modality coverage limit, not evidence that EXPAND_CAP failed to find E4.')
    else:
        lines.append('Guard oracle coverage varies; see the flat-oracle table for the counts and abstention reasons. The wording was kept as specified.')
    chain_answerable = [g for item in metadata for g in item['oracle_groups'] if g['shape'] == 'two-hop']
    if all(g['verdicts'].get('ANSWER', 0) == 60 for g in chain_answerable):
        lines.append('The flat oracle answered all two-hop questions in all six N/frequency groups; the remaining recall loss is attributable to routing, not to the test reader or a missing background department fact.')
    else:
        lines.append('Some chain oracle trials abstained; see each group’s reasons. Those abstentions were retained in the denominator audit and were not repaired by changing the requested chain shape.')
        chain_misses = [trial for item in metadata for trial in item['trials']
                        if trial['shape'] == 'two-hop' and trial['oracle']['verdict'] != 'ANSWER']
        grouped_misses = collections.defaultdict(list)
        for trial in chain_misses:
            if trial['request_unread']:
                cause = 'request unread: ' + ', '.join(sorted({u['reason'] for u in trial['request_unread']}))
            else:
                unsupported = sorted({reason for profile in trial['source_profiles']
                                      for clause in profile['clauses'] for reason in clause['unsupported']})
                cause = ('source unsupported: ' + ', '.join(unsupported)) if unsupported else trial['oracle'].get('reason', 'oracle abstention')
            grouped_misses[(trial['n'], trial['frequency'],
                            trial['entities'].get('E2', ''), cause)].append(trial)
        if grouped_misses:
            descriptions = []
            for (dataset_n, band, e2, cause), group in sorted(grouped_misses.items()):
                descriptions.append(f'N={dataset_n} {band} E2 `{e2}` ×{len(group)}: {cause}')
            lines.append('Chain oracle abstention causes from the injected/request parses: ' + '; '.join(descriptions) + '.')

    aggregate = collections.defaultdict(list)
    for row in summaries:
        aggregate[(row['evidence'], row['expand'])].append(row)
    lines += ['', '### Aggregate cap comparison', '',
              'This aggregation pools the two-hop and guard rows and all frequency bands across both corpus sizes. Recall pools only oracle-answerable cases; guard oracle abstentions therefore do not enter its denominator.', '',
              '| unread mode | cap | recall | violations | median/p95 ms (group medians) | median reach (group medians) |',
              '|---|---:|---|---:|---:|---:|']
    for evidence in EVIDENCE_MODES:
        for cap in CAPS:
            rows = aggregate[(evidence, cap)]
            hits = sum(r['recall_hits'] for r in rows)
            denom = sum(r['oracle_answerable'] for r in rows)
            violations = sum(r['violations'] for r in rows)
            med = statistics.median(r['median_ms'] for r in rows)
            p95 = statistics.median(r['p95_ms'] for r in rows)
            reach_med = statistics.median(r['reach_median'] for r in rows)
            recall_pct = f'{100 * hits / denom:.1f}%' if denom else 'n/a'
            lines.append(f"| {evidence} | {cap} | {hits}/{denom} ({recall_pct}) | {violations} | {med:.2f}/{p95:.2f} | {reach_med:.0f} |")

    lines += ['', '### Automatic observations', '']
    # Summarize answerable two-hop recall by cap and evidence mode.
    for evidence in EVIDENCE_MODES:
        by_cap = {}
        for cap in CAPS:
            rows = [r for r in summaries if r['shape'] == 'two-hop' and r['evidence'] == evidence and r['expand'] == cap]
            h = sum(r['recall_hits'] for r in rows); d = sum(r['oracle_answerable'] for r in rows)
            by_cap[cap] = (h, d)
        text = ', '.join(f'{cap}: {h}/{d}' for cap, (h, d) in by_cap.items())
        lines.append(f'- Two-hop oracle recall under `{evidence}`: {text}.')
    # Per-frequency endpoint to make common entities' non-following visible.
    for n in (4000, 16000):
        rows = [r for r in summaries if r['n'] == n and r['shape'] == 'two-hop' and
                r['evidence'] == 'mention' and r['expand'] == 128]
        chain = ', '.join(f"{r['frequency']} {fmt_recall(r)}" for r in rows)
        lines.append(f'- N={n}, mention mode, cap=128 two-hop recall by background E2 frequency: {chain}.')

    lines += ['', '## Recommendation', '',
              'Recommendation is based on two-hop trials with oracle answers, zero-violation requirement, reach, and latency. The guard shape is not used to justify a cap if its flat oracle abstains.', '']
    mention_cap = {}
    for cap in CAPS:
        rows = [r for r in summaries if r['shape'] == 'two-hop' and r['evidence'] == 'mention' and r['expand'] == cap]
        mention_cap[cap] = (sum(r['recall_hits'] for r in rows), sum(r['oracle_answerable'] for r in rows),
                            sum(r['violations'] for r in rows), statistics.median(r['median_ms'] for r in rows),
                            statistics.median(r['reach_median'] for r in rows))
    if mention_cap:
        best = max(CAPS, key=lambda cap: (mention_cap[cap][0] / mention_cap[cap][1]
                                          if mention_cap[cap][1] else -1,
                                          -mention_cap[cap][2], -mention_cap[cap][4], -mention_cap[cap][3]))
        hit, denom, violations, med, reach_med = mention_cap[best]
        recall_pct = f'{100 * hit / denom:.1f}%' if denom else 'n/a'
        lines.append(f'Among the tested settings, cap **{best}** has the strongest answerable two-hop recall under `mention`: {hit}/{denom} ({recall_pct}), with {violations} violations; the median across group medians is {med:.2f} ms and median effective reach is {reach_med:.0f} leaves.')
        common128 = [r for r in summaries if r['shape'] == 'two-hop' and r['frequency'] == 'common' and
                     r['evidence'] == 'mention' and r['expand'] == 128]
        if common128 and all(r['recall_hits'] == 0 for r in common128):
            lines.append('Common raw-text frequency is not the same as `LeafTree` clause-holder DF: compare both columns in the entity audit. A raw `>128` term with fewer than 129 parsed holder leaves may still be followed at cap 128. The measured common-band recall is 0 at cap 128, so that result does not establish that all raw-common terms were skipped by the cap.')
    lines.append('Read the per-band recall/fallback columns before applying the recommendation: the guard workload is currently limited by source/question modality compatibility, and the common-entity chain band is intentionally beyond cap 128.')
    lines += ['', '## Reproducibility', '',
              'Run from the work copy root with `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.` and the requested environment Python. No network or sealed/heldout data was used.', '']
    return '\n'.join(lines)


def main() -> None:
    all_summaries = []
    all_metadata = []
    for n, stride in DATASETS:
        summaries, metadata = run_dataset(n, stride, seed=5197)
        all_summaries.extend(summaries)
        all_metadata.append(metadata)
        print(json.dumps({'stage': 'dataset_done', 'n': n,
                          'runtime_s': round(metadata['total_runtime_s'], 1)}, ensure_ascii=False), flush=True)
    REPORT.write_text(report_text(all_summaries, all_metadata), encoding='utf-8')
    print(json.dumps({'stage': 'report_written', 'path': str(REPORT),
                      'summary_rows': len(all_summaries), 'bytes': REPORT.stat().st_size}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

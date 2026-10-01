#!/usr/bin/env python3
"""Tune the leaf-router caps on real text (Wikipedia lead paragraphs, `split == train` only).

Documents: every `stride`-th train lead of build/round4/jawiki_leads.full.jsonl. Questions are made from the
corpus itself: for a clause the reader supports (`<entity>は<value>である` / `<entity>の<attribute>は<value>`) the
question asks for the value (`<entity>は何？`). The ORACLE is the flat view with an unlimited budget: the answer the
router must never contradict. Metrics per (anchor_cap, expand_cap, unread_cap): recall against the oracle, violations
(routed ANSWER differing from the oracle, or answering where unread text mentions an anchor), reach, time.
No fixtures, no sealed data; own questions only.
"""
import argparse, collections, itertools, json, random, statistics, sys, time
sys.path.insert(0, '.')
from verantyx import question, semantic_route
from verantyx.one import Vera
from verantyx.semantic import answer
from verantyx.semantic_ir import Budget, View

PATH = '/Users/motonishikoudai/Projects/vera-corpus/build/round4/jawiki_leads.full.jsonl'
BIG = Budget(parse=32, depth=8, candidates=10 ** 7, bindings=64, steps=10 ** 9)


def load(n, stride):
    docs = {}
    with open(PATH) as f:
        for i, line in enumerate(f):
            if i % stride: continue
            r = json.loads(line); text = r.get('text') or ''
            if r.get('split') == 'train' and len(text) >= 40 and not text.startswith(('#', 'REDIRECT')):
                docs[f'w{len(docs)}'] = text
            if len(docs) >= n: break
    return docs


def make_questions(view, count, seed):
    out = []; seen = set()
    for c in view.clauses:
        if c.unsupported or c.polarity != '+' or c.modality != 'assert' or c.rule != 'copula': continue
        roles = {r.name: r.term for r in c.roles}
        entity, value = roles.get('entity'), roles.get('value')
        if not isinstance(entity, str) or not isinstance(value, str) or len(entity) < 2: continue
        if c.predicate == 'identity': q = f'{entity}は何？'
        elif c.predicate == 'property' and isinstance(roles.get('attribute'), str): q = f"{entity}の{str(roles['attribute']).replace('nominal:', '')}は？"
        else: continue
        if q in seen: continue
        seen.add(q); out.append((q, value, c.span.source))
    random.Random(seed).shuffle(out)
    return out[:count]


def df_group(view, entity):
    n = sum(1 for t in view.sources.values() if entity in t)
    return 'rare(<5)' if n < 5 else ('mid(5-64)' if n <= 64 else 'common(>64)')


def mentions_in_unread(view, anchors):
    return any(a in u.span.text for u in view.unread for a in anchors if u.reason != 'document instruction excluded')


def run(n, stride, nq, seed, grid, oracle_cap):
    docs = load(n, stride)
    t = time.perf_counter(); v = Vera.from_texts(docs, mode='semantic'); ingest = time.perf_counter() - t
    view = v._semantic_view
    qs = make_questions(view, 10 ** 6, seed)
    # keep a mix across document-frequency groups so the caps are exercised, not only rare titles
    groups = collections.defaultdict(list)
    for item in qs:
        ent = item[0].split('は')[0].split('の')[0]
        groups[df_group(view, ent)].append(item)
    per = max(1, nq // 3)
    qs = [x for g in ('rare(<5)', 'mid(5-64)', 'common(>64)') for x in groups.get(g, [])[:per]]
    print(json.dumps({'groups': {g: len(v2) for g, v2 in groups.items()}, 'used': len(qs)}, ensure_ascii=False), flush=True)
    semantic_route.ROUTE_MIN_LEAVES = 10 ** 9
    oracle = {}
    for q, gold, src in qs[:oracle_cap]:
        req = question.read_semantic(q).value
        # The router's contract, computed without any tree: every clause, unlimited budget, and only the unread
        # spans that mention an anchor (plain substring scan) gate the answer.
        anchors = set().union(*semantic_route.pattern_anchors(req)) if semantic_route.pattern_anchors(req) else set()
        gating = tuple(u for u in view.unread if u.reason == 'document instruction excluded' or any(a in u.span.text for a in anchors))
        a = answer(req, [View(view.sources, view.clauses, gating, view.ingest_ms)], budget=BIG)
        oracle[q] = (a['verdict'], a.get('values'))
    semantic_route.ROUTE_MIN_LEAVES = 7
    tree_t = time.perf_counter(); v.ask(qs[0][0]); build_ms = (time.perf_counter() - tree_t) * 1000
    print(json.dumps({'n': len(docs), 'clauses': len(view.clauses), 'unread': len(view.unread), 'ingest_s': round(ingest, 1),
                      'questions': len(qs), 'oracle_checked': len(oracle),
                      'oracle_answers': sum(1 for o in oracle.values() if o[0] == 'ANSWER'),
                      'oracle_correct_vs_gold': sum(1 for q, gold, s in qs[:oracle_cap] if oracle[q][0] == 'ANSWER' and oracle[q][1] == [gold]),
                      'tree_build_ms_first_ask': round(build_ms, 1)}, ensure_ascii=False), flush=True)
    rows = []
    for a_cap, e_cap, u_cap in grid:
        semantic_route.ANCHOR_CAP, semantic_route.EXPAND_CAP, semantic_route.UNREAD_CAP = a_cap, e_cap, u_cap
        stat = collections.Counter(); ms = []; reach = []; visited = []; viol = []; bygrp = collections.defaultdict(collections.Counter)
        for q, gold, src in qs[:oracle_cap]:
            t0 = time.perf_counter(); r = v.ask(q); ms.append((time.perf_counter() - t0) * 1000)
            tr = [s for s in r.get('trace', []) if s.get('part') == 'semantic_route.LeafTree']
            info = tr[0] if tr else {}
            stat['route:' + str(info.get('status')) + ('/' + info['reason'] if info.get('reason') else '')] += 1
            if info.get('reached_leaves') is not None: reach.append(info['reached_leaves']); visited.append(info.get('nodes_visited', 0))
            o = oracle[q]; grp = df_group(view, q.split('は')[0].split('の')[0])
            if r['verdict'] == 'ANSWER':
                if o[0] == 'ANSWER' and r['values'] != o[1]: viol.append(('differs', q, o, r['values']))
                elif o[0] != 'ANSWER':
                    viol.append(('answered-despite', q, o[0]))
                if r['values'] == [gold]: stat['correct_vs_gold'] += 1
                else: stat['not_gold'] += 1
            if o[0] == 'ANSWER':
                stat['oracle_answerable'] += 1; bygrp[grp]['answerable'] += 1
                if r['verdict'] == 'ANSWER' and r['values'] == o[1]: stat['recall_hit'] += 1; bygrp[grp]['hit'] += 1
                else: stat['recall_miss:' + r['verdict']] += 1; bygrp[grp]['miss:' + r['verdict']] += 1
        ms.sort()
        rows.append({'anchor': a_cap, 'expand': e_cap, 'unread': u_cap,
                     'recall': f"{stat['recall_hit']}/{stat['oracle_answerable']}", 'violations': len(viol),
                     'extra_answers': stat['answer_where_oracle_abstained'],
                     'reach_mean': round(statistics.mean(reach), 1) if reach else None,
                     'visited_mean': round(statistics.mean(visited), 1) if visited else None,
                     'median_ms': round(statistics.median(ms), 2), 'p95_ms': round(ms[int(.95 * len(ms)) - 1], 2),
                     'routes': {k: v2 for k, v2 in stat.items() if k.startswith('route:')},
                     'misses': {k: v2 for k, v2 in stat.items() if k.startswith('recall_miss')}, 'by_df': {g: dict(c) for g, c in bygrp.items()}, 'viol': viol[:3]})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    v.close()
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=1000); ap.add_argument('--stride', type=int, default=300)
    ap.add_argument('--questions', type=int, default=300); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--oracle', type=int, default=150); ap.add_argument('--evidence', default='all')
    ap.add_argument('--anchor', default='16,64,256'); ap.add_argument('--expand', default='4,8,32'); ap.add_argument('--unread', default='256,1024,4096')
    a = ap.parse_args()
    grid = list(itertools.product(map(int, a.anchor.split(',')), map(int, a.expand.split(',')), map(int, a.unread.split(','))))
    semantic_route.EVIDENCE_UNREAD = a.evidence
    run(a.n, a.stride, a.questions, a.seed, grid, a.oracle)

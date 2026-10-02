#!/usr/bin/env python3
"""Gold probe: measure the semantic reader against the Codex-generated corpus (TRAIN split only; heldout is never opened).

modes (run from a repo checkout root, PYTHONPATH=.):
  wdw   paraphrase_entail who_did_what: sentence + question -> gold answer. correct / wrong(overlap = NP-modifier or head mismatch) / wrong(other) / abstain per phenomenon
  pair  paraphrase_entail pairs: both sentences read, and do the supported clause projections agree (paraphrase), or not (contradiction/other)?
  qvar  general_qa q_variants: do the 3 paraphrased questions parse, and to the same request plan?
Usage: gold_probe.py MODE [--n 150] [--seed 7] [--phenomenon X] [--json out.json]   (VERA_CORPUS_DIR defaults to ~/vera-codex-corpus)
"""
import argparse, collections, json, os, random, sys, time
sys.path.insert(0, '.')
CORPUS = os.path.expanduser(os.environ.get('VERA_CORPUS_DIR', '~/vera-codex-corpus'))


def load(family, kind=None):
    path = f'{CORPUS}/{family}/train/records.jsonl'          # train only, by construction
    for line in open(path):
        if kind and f'"kind": "{kind}"' not in line: continue
        r = json.loads(line)
        assert r.get('split') == 'train'
        yield r


def sample(rows, key, n, seed):
    by = collections.defaultdict(list)
    for r in rows: by[r.get(key)].append(r)
    rng = random.Random(seed); out = {}
    for k, items in by.items(): rng.shuffle(items); out[k] = items[:n]
    return out


def wdw(a):
    from verantyx.one import Vera
    groups = sample(load('paraphrase_entail', 'who_did_what'), 'phenomenon', a.n, a.seed)
    stat = collections.defaultdict(collections.Counter); ex = collections.defaultdict(list)
    for ph, items in sorted(groups.items()):
        if a.phenomenon and a.phenomenon not in ph: continue
        for r in items:
            v = Vera.from_texts({'d': r['sentence']}, mode='semantic'); res = v.ask(r['question']); v.close()
            if res['verdict'] != 'ANSWER': stat[ph]['abstain'] += 1; continue
            vals = res.get('values') or []; gold = r['answer']
            if vals == [gold]: stat[ph]['correct'] += 1
            elif any(gold in x or x in gold for x in vals) and vals: stat[ph]['wrong_overlap'] += 1; ex[ph].append((r['sentence'], r['question'], gold, vals))
            else: stat[ph]['wrong_other'] += 1; ex[ph].append((r['sentence'], r['question'], gold, vals))
    return stat, ex


def projection(clause):
    roles = tuple(sorted((x.name, str(x.term)) for x in clause.roles if x.name not in ('attribute',)))
    return (clause.predicate, clause.polarity, clause.time, roles)


def pair(a):
    from verantyx.semantic_reader import document_view
    groups = sample(load('paraphrase_entail', 'pair'), 'phenomenon', a.n, a.seed)
    stat = collections.defaultdict(collections.Counter); ex = collections.defaultdict(list)
    for ph, items in sorted(groups.items()):
        if a.phenomenon and a.phenomenon not in ph: continue
        for r in items:
            lab = r['label']
            v = document_view({'a': r['s1'], 'b': r['s2']})
            pa = {projection(c) for c in v.clauses if c.span.source == 'a' and not c.unsupported}
            pb = {projection(c) for c in v.clauses if c.span.source == 'b' and not c.unsupported}
            if not pa or not pb: stat[ph][lab + ':read_one_or_none'] += 1; continue
            same = bool(pa & pb)
            stat[ph][lab + (':agree' if same else ':differ')] += 1
            if lab == 'paraphrase' and not same and len(ex[ph]) < 3: ex[ph].append((r['s1'], r['s2'], sorted(pa)[:1], sorted(pb)[:1]))
    return stat, ex


def qvar(a):
    from verantyx import question
    stat = collections.Counter(); ex = []
    rng = random.Random(a.seed); rows = list(load('general_qa')); rng.shuffle(rows)
    for r in rows[:a.n * 8]:
        keys = []
        for q in r['q_variants']:
            try:
                res = question.read_semantic(q); req = res.value
                keys.append(None if req is None else json.dumps([[(n.pattern.predicate, sorted(map(str, n.pattern.roles))) if n.pattern else n.kind for n in p.nodes] for p in req.plans], default=str, sort_keys=True))
            except Exception as e: keys.append(None)
        stat['items'] += 1; stat['all_parsed'] += all(k is not None for k in keys); stat['none_parsed'] += all(k is None for k in keys)
        if all(k is not None for k in keys): stat['all_parsed_equal'] += len(set(keys)) == 1
        stat['kind:' + r['kind'] + (':parsed' if any(k is not None for k in keys) else ':none')] += 1
    return {'qvar': stat}, {}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['wdw', 'pair', 'qvar']); ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--seed', type=int, default=7); ap.add_argument('--phenomenon'); ap.add_argument('--json'); a = ap.parse_args()
    t = time.time(); stat, ex = {'wdw': wdw, 'pair': pair, 'qvar': qvar}[a.mode](a)
    tot = collections.Counter()
    for ph, c in sorted(stat.items()):
        tot.update(c); print('%-26s %s' % (str(ph)[:24], dict(sorted(c.items()))))
    print('TOTAL', dict(sorted(tot.items())), 'seconds', round(time.time() - t))
    for ph, items in list(ex.items())[:4]:
        for e in items[:2]: print('EXAMPLE', ph, e)
    if a.json: json.dump({'mode': a.mode, 'total': dict(tot), 'by': {str(k): dict(v) for k, v in stat.items()}}, open(a.json, 'w'), ensure_ascii=False, indent=1)

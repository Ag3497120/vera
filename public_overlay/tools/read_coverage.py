#!/usr/bin/env python3
"""Reading coverage of the semantic reader on real Japanese text (Wikipedia leads, `split == train` only).

The yardstick for the foundation work: of all sentences, how many yield at least one SUPPORTED clause, how many yield only
unsupported clauses (with the reasons), and how many stay unread. Deterministic (stride sampling), no sealed data.
Usage: tools/read_coverage.py [--n 1500] [--stride 200] [--json out.json]
"""
import argparse, collections, json, re, sys
sys.path.insert(0, '.'); sys.path.insert(0, 'tools')
import os
import round5a_route_tune as T
if os.environ.get('VERA_LEADS'): T.PATH = os.environ['VERA_LEADS']
from verantyx.semantic_reader import document_view


def measure(n, stride):
    docs = T.load(n, stride); v = document_view(docs)
    ok = {(c.span.source, c.span.start) for c in v.clauses if not c.unsupported}
    only = {}; unread = {(u.span.source, u.span.start) for u in v.unread}
    for c in v.clauses:
        k = (c.span.source, c.span.start)
        if c.unsupported and k not in ok: only.setdefault(k, set()).update(c.unsupported)
    sentences = sum(len([s for s in re.split(r'(?<=。)', t) if s.strip()]) for t in docs.values())
    reasons = collections.Counter(r for rs in only.values() for r in rs)
    unread_reasons = collections.Counter(u.reason for u in v.unread)
    rules = collections.Counter(c.rule for c in v.clauses if not c.unsupported)
    return {'documents': len(docs), 'sentences_approx': sentences, 'supported_sentences': len(ok),
            'supported_pct': round(100 * len(ok) / sentences, 1), 'only_unsupported_sentences': len(only), 'unread_spans': len(unread),
            'supported_clauses_by_rule': dict(rules), 'unsupported_reasons_pct_of_only_unsupported':
            {r: round(100 * x / max(1, len(only)), 1) for r, x in reasons.most_common()},
            'unread_reasons': dict(unread_reasons.most_common(8))}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=1500); ap.add_argument('--stride', type=int, default=200); ap.add_argument('--json')
    a = ap.parse_args(); r = measure(a.n, a.stride); print(json.dumps(r, ensure_ascii=False, indent=1))
    if a.json: open(a.json, 'w').write(json.dumps(r, ensure_ascii=False, indent=1))

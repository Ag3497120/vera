#!/usr/bin/env python3
"""W3-b5 step 2 (same tool as W3-b4, copied): facts of the READER ALONE (no placement is given or asked) for a list of sentences, to choose the sentences of the data before it is frozen.
For every sentence (one per line of --in): the number of clauses, the rule, the unsupported reasons, which typed trigger fires (W3-b1 `typed_trigger_ja`, W3-b2
`typed_trigger_w3b2_ja`), the predicate, the conjugation type (`cType`) of the head, the gate on the ending (`typed_tail_ja`) and the gate on a derived head
(`typed_head_derived_ja`), and what the entry does with no placement (`read(text, placement=None)`).
Nothing here depends on the new table; it is the same for the base commit. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/reader_facts.py --in FILE --out TSV
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    lines = [l.rstrip('\n') for l in open(a.inp, encoding='utf-8') if l.strip()]
    out = ['text\tn_clauses\trule\tunsupported\ttrigger_w3b1\ttrigger_w3b2\tpredicate\tctype\ttail_gate\tderived_gate\tbase_entry\tbase_reason']
    for text in lines:
        f = facts_of(text)
        out.append('\t'.join([text, str(f['n_clauses']), f['rule'], f['unsupported'], f['trigger_w3b1'], f['trigger_w3b2'], f['predicate'], f['ctype'], f['tail_gate'],
                              f['derived_gate'], f['base_entry'], f['base_reason']]))
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('rows=%d' % len(lines))


def facts_of(text):
    """The facts of the reader alone for one sentence (strings; '-' for none). Importable: the data generator uses it to fill `path` and to refuse a row whose trigger is not the one intended."""
    from verantyx import semantic_read as SR, semantic_reader as R
    toks = R._tokens(text)
    for w, s, e in toks: w.feature.pos1, w.feature.pos2, w.feature.pos3, w.feature.cType, w.feature.cForm, w.feature.lemma
    view = R.document_view({'d': text})
    n = len(view.clauses)
    c = view.clauses[0] if n else None
    t1 = R.typed_trigger_ja(text, view); t2 = None if t1 else R.typed_trigger_w3b2_ja(text, view)
    tail = derived = ctype = None
    if c is not None:
        head_i = next((i for i, (w, s, e) in enumerate(toks) if e == c.predicate_span.end), None)
        ctype = toks[head_i][0].feature.cType if head_i is not None else None
        tail = R.typed_tail_ja(toks, c) or 'ok'
        derived = R.typed_head_derived_ja(toks, c) or 'ok'
    r = SR.read(text, placement=None)
    return {'n_clauses': n, 'rule': c.rule if c else '-', 'unsupported': ';'.join(c.unsupported) if c else '-', 'trigger_w3b1': t1 or '-', 'trigger_w3b2': t2 or '-',
            'predicate': c.predicate if c else '-', 'ctype': str(ctype), 'tail_gate': str(tail), 'derived_gate': str(derived),
            'base_entry': 'read' if r['readable'] else 'abstain', 'base_reason': '' if r['readable'] else r['abstain']['reasons'][0]}


if __name__ == '__main__':
    main()

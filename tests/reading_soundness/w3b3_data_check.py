#!/usr/bin/env python3
"""W3-b3 step 3: checks of the new data (w3b3_{relative,connective,parallel,w1a4}.jsonl).
  --validate FILE   every row through tools.bank_score.v2.b1.validate_item (errors must be 0), and the keys of a row
  --counts FILE     rows per file / behavior / cut / entry_expect / w3b3_expect (first word)
  --overlap FILE    no input of the new data (w1a4 excepted: those ARE the review's sentences) is an input (or a substring of the text) of the existing data, the tickets, the plan, the docs
                    (except the docs that this ticket wrote about itself), or the evidence of the plan (must be 0)
  --extra PATH...   more files whose text counts as "existing" (the ticket, the plan, the evidence of the plan)
Loaded verantyx* modules must be under PYTHONPATH (else exit 2). Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_data_check.py --validate A --counts B --overlap C
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b3_common as C

KEYS = ('id', 'lang', 'behavior', 'input', 'text', 'expect', 'cut', 'construction', 'entry_expect', 'w3b3_expect', 'structure_expect', 'abstain_why', 'source', 'note')
CUTS = ('relative', 'ので', 'から', 'が', 'けれど', 'と', 'なら', 'ば', 'たら', 'ても', 'ながら', 'て', '並列', 'w1a4')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate'); ap.add_argument('--counts'); ap.add_argument('--overlap'); ap.add_argument('--extra', nargs='*', default=[])
    a = ap.parse_args()
    from tools.bank_score.v2 import b1
    C.isolation()
    rows = [r for name in C.DATA_ALL for r in C.load_data(name)]
    if a.validate:
        errs = []
        for r in rows:
            e = []
            b1.validate_item(r, e)
            if tuple(r) != KEYS + ('_data',): e.append('KEYS:%s' % list(r))
            if r['text'] != r['input']: e.append('TEXT_NE_INPUT')
            if r['entry_expect'] not in ('read', 'abstain'): e.append('ENTRY_EXPECT')
            if r['cut'] not in CUTS: e.append('CUT')
            if r['behavior'] == 'abstain' and not r['abstain_why']: e.append('ABSTAIN_WITHOUT_WHY')
            if r['behavior'] == 'read' and r['abstain_why']: e.append('READ_WITH_WHY')
            if r['behavior'] == 'read' and r['_data'] in ('parallel',) and not (r['structure_expect'] and r['structure_expect']['edges']): e.append('NO_STRUCTURE')
            if r['_data'] == 'w1a4' and (r['behavior'] != 'abstain' or r['entry_expect'] != 'abstain'): e.append('W1A4_NOT_ABSTAIN')
            errs += ['%s:%s' % (r['id'], x) for x in e]
        ids = [r['id'] for r in rows]
        if len(set(ids)) != len(ids): errs.append('DUPLICATE_ID')
        texts = [r['input'] for r in rows]
        if len(set(texts)) != len(texts): errs.append('DUPLICATE_INPUT')
        lines = ['rows=%d errors=%d' % (len(rows), len(errs))] + errs
        Path(a.validate).write_text('\n'.join(lines) + '\n', encoding='utf-8'); print(lines[0])
    if a.counts:
        out = []
        for name in C.DATA_ALL:
            rs = C.load_data(name); read = sum(1 for r in rs if r['behavior'] == 'read')
            out.append('%s rows=%d read=%d abstain=%d' % (name, len(rs), read, len(rs) - read))
            out.append('  by_cut=%s' % json.dumps(dict(sorted(collections.Counter(r['cut'] for r in rs).items())), ensure_ascii=False))
            out.append('  by_cut_and_behavior=%s' % json.dumps({'%s|%s' % k: v for k, v in sorted(collections.Counter((r['cut'], r['behavior']) for r in rs).items())}, ensure_ascii=False))
            out.append('  by_entry_expect=%s' % json.dumps(dict(sorted(collections.Counter(r['entry_expect'] for r in rs).items()))))
            out.append('  by_w3b3_expect=%s' % json.dumps(dict(sorted(collections.Counter(r['w3b3_expect'].split(':')[0] for r in rs).items())), ensure_ascii=False))
        out.append('total rows=%d' % len(rows))
        Path(a.counts).write_text('\n'.join(out) + '\n', encoding='utf-8'); print('\n'.join(out))
    if a.overlap:
        blobs = []
        for pat in ('tests/reading_soundness/*.jsonl', 'tests/reading_soundness/*.txt', 'tests/event_cross/data/*.jsonl', 'tests/bank_score/fixtures/**/*.jsonl',
                    'artifacts/w1-a/*.txt', 'artifacts/w3-b1/*.txt', 'artifacts/w3-b2/*.txt', 'artifacts/w3-b/*.jsonl', 'docs/*.md', 'tests/*.py', 'tests/reading_soundness/*.py', 'tests/observe/data/*.jsonl'):
            for p in sorted(C.TREE.glob(pat)):
                if p.name.startswith('w3b3_') or '/w3-b3/' in str(p): continue
                try: blobs.append((str(p.relative_to(C.TREE)), p.read_text(encoding='utf-8')))
                except Exception: pass
        for p in a.extra: blobs.append((p, Path(p).read_text(encoding='utf-8')))
        hits = []
        for r in rows:
            if r['_data'] == 'w1a4': continue
            for name, blob in blobs:
                if r['input'] in blob: hits.append('%s\t%s\t%s' % (r['id'], r['input'], name)); break
        lines = ['inputs=%d files_searched=%d overlaps=%d' % (sum(1 for r in rows if r['_data'] != 'w1a4'), len(blobs), len(hits))] + hits
        Path(a.overlap).write_text('\n'.join(lines) + '\n', encoding='utf-8'); print(lines[0]); [print(h) for h in hits]


if __name__ == '__main__':
    main()

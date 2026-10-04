#!/usr/bin/env python3
"""W3-b2 step 4: checks of the new data (w3b2_{frame,multiple,determiner,no}.jsonl).
  --validate FILE   every row through tools.bank_score.v2.b1.validate_item (errors must be 0), and the keys of a row
  --counts FILE     rows per file / path / entry_expect / w3b2_expect (first word), and the share of `read` rows per file
  --overlap FILE    no input of the new data is an input (or a substring of the text) of the existing data, the tickets, the plan or the docs (must be 0)
  --extra PATH...   more files whose text counts as "existing" (the ticket, the plan, the evidence of the plan)
Loaded verantyx* modules must be under PYTHONPATH (else exit 2). Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_data_check.py --validate A --counts B --overlap C
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b2_common as C

KEYS = ('id', 'lang', 'behavior', 'input', 'text', 'expect', 'path', 'pred_type', 'construction', 'entry_expect', 'w3b2_expect', 'note')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate'); ap.add_argument('--counts'); ap.add_argument('--overlap'); ap.add_argument('--extra', nargs='*', default=[])
    a = ap.parse_args()
    from tools.bank_score.v2 import b1
    C.isolation()
    rows = [r for name in C.DATA for r in C.load_data(name)]
    if a.validate:
        errs, lines = [], []
        for r in rows:
            e = []
            b1.validate_item(r, e)
            if tuple(r) != KEYS + ('_data',): e.append('KEYS:%s' % list(r))
            if r['text'] != r['input']: e.append('TEXT_NE_INPUT')
            if r['entry_expect'] not in ('read', 'abstain'): e.append('ENTRY_EXPECT')
            if r['path'] not in ('U', 'U3', 'S4'): e.append('PATH')
            errs += ['%s:%s' % (r['id'], x) for x in e]
        lines.append('rows=%d errors=%d' % (len(rows), len(errs))); lines += errs
        Path(a.validate).write_text('\n'.join(lines) + '\n', encoding='utf-8'); print(lines[0])
    if a.counts:
        out = []
        for name in C.DATA:
            rs = C.load_data(name); read = sum(1 for r in rs if r['entry_expect'] == 'read')
            out.append('%s rows=%d read=%d abstain=%d read_share=%.3f' % (name, len(rs), read, len(rs) - read, read / len(rs)))
            out.append('  by_path=%s' % json.dumps(dict(collections.Counter(r['path'] for r in rs)), sort_keys=True))
            out.append('  by_w3b2_expect=%s' % json.dumps(dict(sorted(collections.Counter(r['w3b2_expect'].split(':')[0] for r in rs).items())), ensure_ascii=False))
        out.append('total rows=%d' % len(rows))
        Path(a.counts).write_text('\n'.join(out) + '\n', encoding='utf-8'); print('\n'.join(out))
    if a.overlap:
        blobs = []
        for pat in ('tests/reading_soundness/*.jsonl', 'tests/reading_soundness/*.txt', 'tests/event_cross/data/*.jsonl', 'tests/bank_score/fixtures/**/*.jsonl',
                    'artifacts/w1-a/*.txt', 'artifacts/w3-b1/*.txt', 'artifacts/w3-b/*.jsonl', 'docs/*.md', 'tests/*.py', 'tests/reading_soundness/*.py'):
            for p in sorted(C.TREE.glob(pat)):
                if p.name.startswith('w3b2_') or '/w3-b2/' in str(p): continue
                try: blobs.append((str(p.relative_to(C.TREE)), p.read_text(encoding='utf-8')))
                except Exception: pass
        for p in a.extra: blobs.append((p, Path(p).read_text(encoding='utf-8')))
        hits = []
        for r in rows:
            for name, blob in blobs:
                if r['input'] in blob: hits.append('%s\t%s\t%s' % (r['id'], r['input'], name)); break
        lines = ['inputs=%d files_searched=%d overlaps=%d' % (len(rows), len(blobs), len(hits))] + hits
        Path(a.overlap).write_text('\n'.join(lines) + '\n', encoding='utf-8'); print(lines[0]); [print(h) for h in hits]


if __name__ == '__main__':
    main()

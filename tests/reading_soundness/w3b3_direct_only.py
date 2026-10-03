#!/usr/bin/env python3
"""W3-b3 S1-5: with an estimated placement (every direct answer made an estimate) and with a split placement (every direct DECIDED answer made MULTIPLE), the new path reads no relative clause
and no sentence with と (it needs a direct type), and every other reading it gives is one the real placement (live) gives too, with the same content.
Inputs: the dumps of w3b1_entry_dump.py --mode estimated / multiple / live (the same inputs, the same order). Prints two lines: `mode newly_read relative_read to_read not_in_live content_differs`
(newly_read = read now and not read by the base; counted by the output of the base with no placement in the dump of --none). Exit 1 when a count after the first is not 0.
The kind of cut of an input is asked of `semantic_read.clause_scope_explain_ja` with the same fake over the real placement (--placement DIR).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_direct_only.py --placement DIR --live F --estimated F --multiple F --dev-estimated F --dev-multiple F --out FILE
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b3_common as C


def main():
    ap = argparse.ArgumentParser()
    for k in ('placement', 'live', 'estimated', 'multiple', 'dev-estimated', 'dev-multiple', 'out'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    import w3b1_fakes as F
    constructions.discover()
    C.isolation()
    mappers = {'estimated': lambda x: F.to_estimated(x, 'proximity'), 'multiple': F.to_multiple}

    class Fake:
        def __init__(self, mapper): self.inner, self.mapper = R.CoarseQuery(a.placement), mapper
        def query(self, term): return self.mapper(self.inner.query(term))
    live = {r['text']: r['out'] for r in C.load_jsonl(a.live)}
    lines, bad = [], 0
    for mode, after_path, dev_path in (('estimated', a.estimated, a.dev_estimated), ('multiple', a.multiple, a.dev_multiple)):
        after, dev = C.load_jsonl(after_path), {r['text']: r['out'] for r in C.load_jsonl(dev_path)}
        newly = relative = to = not_live = differs = 0
        for r in after:
            o, d = r['out'], dev[r['text']]
            if not o.get('readable') or d.get('readable'): continue
            newly += 1
            kind = (SR.clause_scope_explain_ja(r['text'], Fake(mappers[mode])).get('cut') or {}).get('kind')
            if kind == 'relative': relative += 1
            if kind == 'と': to += 1
            l = live[r['text']]
            if not l.get('readable'): not_live += 1
            elif l['clauses'] != o['clauses'] or l['relations'] != o['relations']: differs += 1
        lines.append('%s newly_read %d relative_read %d to_read %d not_in_live %d content_differs %d' % (mode, newly, relative, to, not_live, differs))
        bad += relative + to + not_live + differs
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

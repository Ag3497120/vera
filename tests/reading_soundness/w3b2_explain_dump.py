#!/usr/bin/env python3
"""W3-b2: `semantic_read.typed_explain_ja` for every input of a set (JSON lines {text, source}), one JSON line per input: {text, source, explain}. The summary counts the triggers,
what the second step (W3-b2) decided (READ, or the reason it stopped, by its first part) and what the frame decided. The placement: --placement DIR (the real one).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_explain_dump.py --inputs FILE --placement DIR --out FILE.jsonl
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b2_common as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--inputs', required=True); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    C.isolation()
    rows, trig, w3b2, frame, w3b1 = [], collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for item in C.load_jsonl(a.inputs):
        ex = SR.typed_explain_ja(item['text'], R.CoarseQuery(a.placement))
        rows.append({'text': item['text'], 'source': item['source'], 'explain': ex})
        trig['%s/%s' % (ex['w3b1_trigger'], ex['w3b2_trigger'])] += 1
        if ex['w3b1'] is not None: w3b1['READ' if ex['w3b1'] == 'READ' else 'stopped:' + ex['w3b1'].split(':')[0]] += 1
        if ex['w3b2'] is not None: w3b2['READ' if ex['w3b2'] == 'READ' else ex['w3b2'].split(':')[0]] += 1
        if ex['frame'] is not None: frame[ex['frame'].split(':')[0]] += 1
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    typed = sum(1 for r in rows if r['explain']['w3b1_trigger'] or r['explain']['w3b2_trigger'])
    print('inputs=%d with_a_typed_step=%d' % (len(rows), typed))
    print('triggers (w3b1/w3b2)=%s' % json.dumps(dict(sorted(trig.items(), key=lambda kv: str(kv[0]))), ensure_ascii=False))
    print('w3b1=%s' % json.dumps(dict(sorted(w3b1.items())), ensure_ascii=False))
    print('w3b2=%s' % json.dumps(dict(sorted(w3b2.items())), ensure_ascii=False))
    print('frame_stops=%s' % json.dumps(dict(frame), ensure_ascii=False))


if __name__ == '__main__':
    main()

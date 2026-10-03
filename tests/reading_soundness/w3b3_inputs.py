#!/usr/bin/env python3
"""W3-b3: the set of inputs of the measurements: `artifacts/w3-b2/entry_inputs.txt` as it is (JSON lines {text, source}), then the `input` of the four new data files as
{"text", "source": "<file name>"} in a fixed order, a text that is already there left out. Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_inputs.py --out FILE
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b3_common as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = C.load_jsonl(C.TREE / 'artifacts' / 'w3-b2' / 'entry_inputs.txt')
    seen = {r['text'] for r in rows}
    n_base = len(rows)
    for name in C.DATA_ALL:
        for r in C.load_data(name):
            if r['input'] not in seen:
                seen.add(r['input']); rows.append({'text': r['input'], 'source': 'w3b3_%s.jsonl' % name})
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print('base=%d added=%d total=%d' % (n_base, len(rows) - n_base, len(rows)))


if __name__ == '__main__':
    main()

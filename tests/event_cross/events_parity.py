"""E5 helper: does adding --events change the existing judgement fields of an input file?

  python tests/event_cross/events_parity.py --field input|text --inputs FILE [FILE ...]

Each FILE is a jsonl file; the sentence of a row is row[FIELD] (rows without it are counted as skipped). For every sentence:
  * the printed bytes WITHOUT --events (and the exit code),
  * the printed bytes WITH --events with the key `events` removed and printed again the way the entry prints must be the same bytes,
  * the output WITH --events twice must be the same bytes.
Prints one line: `checked N, mismatch M, events_not_deterministic K, skipped S` (exit code 1 when M or K is not 0).
The hidden bank can be measured with the same tool: pass its items file and the name of its input field.
"""
import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TREE))

from verantyx import semantic_read as SR    # noqa: E402


def run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = SR.main(argv)
    return buf.getvalue(), code


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--field', required=True); ap.add_argument('--inputs', nargs='+', required=True)
    args = ap.parse_args(argv)
    checked = mismatch = nondet = skipped = 0
    for name in args.inputs:
        for line in Path(name).read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            text = row.get(args.field)
            if not isinstance(text, str): skipped += 1; continue
            plain, c0 = run(['--text=' + text])
            ev1, c1 = run(['--text=' + text, '--events'])
            ev2, c2 = run(['--text=' + text, '--events'])
            obj = json.loads(ev1)
            obj.pop('events', None)
            stripped = json.dumps(obj, ensure_ascii=False) + '\n'
            checked += 1
            if stripped != plain or c1 != c0: mismatch += 1
            if ev1 != ev2 or c1 != c2: nondet += 1
    print('checked %d, mismatch %d, events_not_deterministic %d, skipped %d' % (checked, mismatch, nondet, skipped))
    return 1 if mismatch or nondet else 0


if __name__ == '__main__':
    sys.exit(main())

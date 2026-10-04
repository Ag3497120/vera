"""E1 with the real commands: every STEP-th input of the E1 set is run as a child process
(`python -m verantyx.semantic_read --text=...`, with and without --events, and `python -m verantyx.cli read-events`), and the bytes are
compared with the base output written by e1_parity.py --mode base (one printed line per input, in the order of the input file).
Prints one summary line per check and exits 1 on any mismatch.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent.parent


def run(args):
    import os
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE)}
    r = subprocess.run([sys.executable, '-m'] + args, cwd=str(TREE), env=env, capture_output=True, text=True, timeout=120)
    return r.stdout, r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--base-out', required=True); ap.add_argument('--base-codes', required=True)
    ap.add_argument('--step', type=int, default=30); ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    rows = [json.loads(l) for l in Path(args.inputs).read_text(encoding='utf-8').splitlines() if l.strip()]
    base_lines = Path(args.base_out).read_text(encoding='utf-8').splitlines(keepends=True)
    base_codes = [int(l.split()[1]) for l in Path(args.base_codes).read_text().splitlines()]
    assert len(base_lines) == len(rows) == len(base_codes)
    picked = list(range(0, len(rows), args.step)) + [len(rows) - 1 - k for k in range(0, 17, 2)]
    picked = sorted(set(picked))
    bad, n = [], 0
    for i in picked:
        argv_i = rows[i]['argv']
        plain, c0 = run(['verantyx.semantic_read'] + argv_i)
        ev, c1 = run(['verantyx.semantic_read'] + argv_i + ['--events'])
        n += 1
        if plain != base_lines[i] or c0 != base_codes[i]: bad.append((i, 'default differs from base'))
        try:
            obj = json.loads(ev); obj.pop('events', None)
            if json.dumps(obj, ensure_ascii=False) + '\n' != plain or c1 != c0: bad.append((i, 'events minus events differs from default'))
        except ValueError:
            bad.append((i, 'events output is not one object'))
        # the cli entry takes --text / --lang as separate options
        text = next((a[len('--text='):] for a in argv_i if a.startswith('--text=')), None)
        lang = next((a[len('--lang='):] for a in argv_i if a.startswith('--lang=')), None)
        if all(a.startswith('--text=') or a.startswith('--lang=') for a in argv_i):
            cli_args = ['verantyx.cli', 'read-events'] + (['--text=' + text] if text is not None else []) + (['--lang=' + lang] if lang is not None else [])
            cli, c2 = run(cli_args)
            if cli != ev or c2 != c1: bad.append((i, 'cli read-events differs from semantic_read --events'))
    line = 'subprocess checked %d inputs (every %dth plus the last edge inputs), mismatch %d' % (n, args.step, len(bad))
    Path(args.out).write_text(line + '\n' + ''.join('%s\n' % (b,) for b in bad), encoding='utf-8')
    print(line)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

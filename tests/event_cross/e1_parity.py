"""E1: run `main(argv)` of the reading entry on every input and write what it prints, byte for byte.

  --mode base      the text of verantyx/semantic_read.py at the base commit (git show b471f5a:...), executed IN MEMORY as the module
                   `verantyx._semantic_read_base` (nothing is written to the tree); one process per mode
  --mode current   the working tree's verantyx.semantic_read
  --events         add `--events` to every call (current mode only)
  --strip-events   with --events: remove the key `events` from each printed object and print it again the way the entry prints
                   (json.dumps(..., ensure_ascii=False) + newline); the result must equal the output without --events
--out gets the concatenated standard output, --codes one line `<n> <exit code>` per input; the base commit's source is hashed into --base-sha.
"""
import argparse
import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TREE))
BASE_COMMIT = 'b471f5a'


def load_base():
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % BASE_COMMIT], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    import hashlib
    return mod, hashlib.sha256(src).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['base', 'current'], required=True)
    ap.add_argument('--events', action='store_true'); ap.add_argument('--strip-events', action='store_true')
    ap.add_argument('--inputs', required=True); ap.add_argument('--out', required=True); ap.add_argument('--codes', required=True)
    ap.add_argument('--base-sha')
    args = ap.parse_args(argv)
    if args.mode == 'base' and args.events: ap.error('the base commit has no --events')
    if args.strip_events and not args.events: ap.error('--strip-events needs --events')
    if args.mode == 'base':
        mod, sha = load_base()
        if args.base_sha: Path(args.base_sha).write_text('%s verantyx/semantic_read.py@%s (git show output, sha256)\n' % (sha, BASE_COMMIT))
    else:
        from verantyx import semantic_read as mod
    rows = [json.loads(l) for l in Path(args.inputs).read_text(encoding='utf-8').splitlines() if l.strip()]
    out, codes = [], []
    for n, row in enumerate(rows):
        call = list(row['argv']) + (['--events'] if args.events else [])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mod.main(call)
        text = buf.getvalue()
        if args.strip_events:
            obj = json.loads(text)
            obj.pop('events', None)
            text = json.dumps(obj, ensure_ascii=False) + '\n'
        out.append(text); codes.append('%d %d\n' % (n, code))
    Path(args.out).write_text(''.join(out), encoding='utf-8')
    Path(args.codes).write_text(''.join(codes), encoding='utf-8')
    print('mode %s%s: %d inputs, %d bytes' % (args.mode, ' events' if args.events else '', len(rows), sum(len(o.encode('utf-8')) for o in out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

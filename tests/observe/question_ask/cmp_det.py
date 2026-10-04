"""W3-c4 determinism: two runs of the same questions under PYTHONHASHSEED=0 and =1 must give the same bytes after the A1 mask (values of the keys in KEYS.txt set to 0).
   cmp_det.py --a O0.jsonl --b O1.jsonl --mask KEYS.txt"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cmp_a1 as C    # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--a', required=True); ap.add_argument('--b', required=True); ap.add_argument('--mask', required=True)
    args = ap.parse_args()
    keys = {l.strip() for l in Path(args.mask).read_text(encoding='utf-8').splitlines() if l.strip()}
    a, b = C.load(args.a), C.load(args.b)
    ids = sorted(set(a) & set(b))
    same = [i for i in ids if C.masked_bytes(a[i], keys) == C.masked_bytes(b[i], keys)]
    diff = [i for i in ids if i not in set(same)]
    print('PYTHONHASHSEED=0 vs PYTHONHASHSEED=1: questions %d, same %d, differ %d' % (len(ids), len(same), len(diff)))
    for i in diff: print('DIFFER %s' % i)
    return 1 if diff else 0


if __name__ == '__main__':
    sys.exit(main())

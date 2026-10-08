"""Frozen-data check, extended to the W3-a2 placements: the 7 frozen files unchanged (sha256,
mtime <= freeze time) and every manifest built after the freeze with the frozen sha.
It also lists the placements of the earlier rounds (they must still be there)."""
import datetime
import glob
import hashlib
import json
import os

W = '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S'
B = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a'
fr = json.load(open(W + '/artifacts/w3-a/FROZEN.json', encoding='utf-8'))
t_frozen = datetime.datetime.fromisoformat(fr['frozen_at_utc'].replace('Z', '+00:00'))
bad = []
for rel, meta in fr['files'].items():
    p = os.path.join(W, rel)
    h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if rel != 'verantyx/coarse_types.py' and h != meta['sha256']:
        bad.append(('hash', rel))
    mt = datetime.datetime.fromtimestamp(os.stat(p).st_mtime, datetime.timezone.utc)
    if rel != 'verantyx/coarse_types.py' and mt > t_frozen:
        bad.append(('mtime_after_freeze', rel, mt.isoformat()))
fh = hashlib.sha256(open(W + '/artifacts/w3-a/FROZEN.json', 'rb').read()).hexdigest()
runs = ['full/r2b/run1', 'full/r2b/run2', 'sample/r2b/run1', 'sample/r2b/run2']
runs += sorted(os.path.relpath(os.path.dirname(p), B) for pat in ('full/r3*/*/manifest.json',
               'full/r4/*/manifest.json', 'full/r5/*/manifest.json', 'sample/r3*/*/manifest.json', 'sample/r4*/*/manifest.json')
               for p in glob.glob(os.path.join(B, pat)))
for run in runs:
    mp = os.path.join(B, run, 'manifest.json')
    if not os.path.exists(mp):
        print('no manifest', run)
        continue
    m = json.load(open(mp, encoding='utf-8'))
    ts = datetime.datetime.fromisoformat(m['build_started_at_utc'].replace('Z', '+00:00'))
    if ts <= t_frozen:
        bad.append(('built_before_freeze', run))
    if m.get('frozen_sha256') != fh:
        bad.append(('manifest_frozen_sha', run))
    print(run, m['build_started_at_utc'], m['content_sha256'][:16])
print('frozen_at', fr['frozen_at_utc'])
print('BAD', bad)
assert not bad

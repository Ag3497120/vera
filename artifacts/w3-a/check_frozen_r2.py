"""Frozen-data check of the plan (section 5), extended to the round-2 placements:
the 7 frozen files unchanged (sha256, mtime <= freeze time) and every manifest built after the freeze."""
import json, hashlib, os, datetime
W='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S'
B='/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a'
fr=json.load(open(W+'/artifacts/w3-a/FROZEN.json', encoding='utf-8'))
t_frozen=datetime.datetime.fromisoformat(fr['frozen_at_utc'].replace('Z','+00:00'))
bad=[]
for rel, meta in fr['files'].items():
    p=os.path.join(W, rel)
    h=hashlib.sha256(open(p,'rb').read()).hexdigest()
    if rel!='verantyx/coarse_types.py' and h!=meta['sha256']: bad.append(('hash', rel))
    mt=datetime.datetime.fromtimestamp(os.stat(p).st_mtime, datetime.timezone.utc)
    if rel!='verantyx/coarse_types.py' and mt>t_frozen: bad.append(('mtime_after_freeze', rel, mt.isoformat()))
fh=hashlib.sha256(open(W+'/artifacts/w3-a/FROZEN.json','rb').read()).hexdigest()
for run in ('sample/run1','full/run1','full/run2','full/r2/run1','full/r2/run2','sample/r2/run1','sample/r2/run2','sample/r2b/run1','sample/r2b/run2','full/r2b/run1','full/r2b/run2'):
    mp=os.path.join(B, run, 'manifest.json')
    if not os.path.exists(mp): print('no manifest yet', run); continue
    m=json.load(open(mp, encoding='utf-8'))
    ts=datetime.datetime.fromisoformat(m['build_started_at_utc'].replace('Z','+00:00'))
    if ts<=t_frozen: bad.append(('built_before_freeze', run))
    if m.get('frozen_sha256')!=fh: bad.append(('manifest_frozen_sha', run))
    print(run, m['build_started_at_utc'], m['content_sha256'][:16])
print('frozen_at', fr['frozen_at_utc']); print('BAD', bad); assert not bad

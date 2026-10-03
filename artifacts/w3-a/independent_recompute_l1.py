"""The ticket's own L1 snippet (token cover on the held-out 2,000 sentences)."""
import json, fugashi
from verantyx.coarse_place import query
W='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S'
import os
PL=os.environ.get('W3A_PL','/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r2b/run1')   # the final placement (round 2); W3A_PL overrides
ROLES={'が','を','に','で','へ','と','から','まで','より','の','は','も'}
t=fugashi.Tagger()
H=[json.loads(l) for l in open(W+'/artifacts/w3-a/holdout_2000.jsonl', encoding='utf-8')]
assert len(H)==2000 and sum(h['source']=='jawiki' for h in H)==1000
tot=hit=0; types=set(); types_hit=set()
for h in H:
    toks=list(t(h['sentence']))
    for i,w in enumerate(toks):
        f=w.feature; prev=toks[i-1] if i else None
        if f.pos1=='名詞': ok=f.pos2 in ('普通名詞','固有名詞','数詞')
        elif f.pos1 in ('動詞','形容詞'):
            ok=not (prev is not None and prev.feature.pos1=='助詞' and prev.feature.pos2=='接続助詞' and prev.surface in ('て','で'))
            if ok and f.pos1=='動詞' and (f.orthBase=='する') and prev is not None and prev.feature.pos1=='名詞': ok=False
        elif f.pos1=='形状詞': ok=f.pos2=='一般'
        else: ok=False
        if not ok: continue
        term=f.orthBase or w.surface
        role=pred=None
        if f.pos1=='名詞':
            nx=toks[i+1] if i+1<len(toks) else None
            if nx is not None and nx.feature.pos1=='助詞' and nx.surface in ROLES: role=nx.surface
            for v in toks[i+1:]:
                if v.feature.pos1=='動詞': pred=v.feature.orthBase or v.surface; break
        r=query(term, context_role=role, context_predicate=pred, placement=PL)
        tot+=1; types.add(term)
        if r['top']: hit+=1; types_hit.add(term)
print('tokens', tot, 'rate', round(hit/tot,4), '| distinct', len(types), 'rate', round(len(types_hit)/len(types),4))
print('meets 0.90:', hit/tot>=0.90)

"""W3-a2: independent recomputation of L2, L3 (counts) and L1 straight from the public API.

    independent_recompute_w3a2.py <placement>
"""
import json
from collections import Counter
from verantyx.coarse_place import query
W='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S'
import sys
PL=sys.argv[1]   # the placement (an argument: py.sh clears the environment)
fr=json.load(open(W+'/artifacts/w3-a/FROZEN.json', encoding='utf-8'))
seed=set(fr['seed_overlap_terms'])
G=[json.loads(l) for l in open(W+'/tests/coarse_place/data/typed_vocab.jsonl', encoding='utf-8')]
G=[g for g in G if g['term'] not in seed]
def cls(r, gold):
    top=r['top']; gs=set(gold)
    if top and set(top)&gs and len(top)<=max(1,len(gs)): return 'correct'
    if len(top)==1: return 'wrong_single'
    return 'other'
n=len(G); c=w=0; tn=tw=0; est=Counter()
for g in G:
    r=query(g['term'], placement=PL); k=cls(r, g['gold']); d=r['origin']=='direct'
    c+=(k=='correct' and d); w+=(k=='wrong_single' and d)
    if not d: est[(r['origin'], k)]+=1
    if g.get('suffix_trap'): tn+=1; tw+=(k=='wrong_single' and d)
print('L2 n',n,'correct',round(c/n,4),'wrong_single',round(w/n,4),'| trap n',tn,'wrong_single',round(tw/tn,4),'| non-direct',dict(est))
U=[json.loads(l) for l in open(W+'/tests/coarse_place/data/unknown_words.jsonl', encoding='utf-8')]
def cls3(r, gold):
    top=r['top']; gs=set(gold)
    if top and set(top)&gs and len(top)<=max(1,len(gs)): return 'correct'
    return 'unknown' if not top else 'wrong'
typed=[u for u in U if not u['gold_unknown']]; unk=[u for u in U if u['gold_unknown']]
c=wr=0; ret=0; leaks=[]; unmarked=[]
for u in U:
    r=query(u['term'], context_role=u.get('context_role'), context_predicate=u.get('context_predicate'), placement=PL)
    if r['origin']=='direct' and set((r.get('axes') or {}).keys())!={'notation'}: leaks.append(u['term'])
    if r['origin']=='estimated' and not r['constructed']: unmarked.append(u['term'])
    if u['gold_unknown']: ret+=bool(r['top'])
    else:
        k=cls3(r,u['gold']); c+=k=='correct'; wr+=k=='wrong'
print('L3 typed',len(typed),'correct',round(c/len(typed),4),'wrong',round(wr/len(typed),4),'| unk',len(unk),'returned',round(ret/len(unk),4))
print('direct (not notation) unknown words', leaks); print('unmarked estimates', unmarked)

# counts, for the P5 "not worse" conditions (W3-a: wrong 59, trap 9, L3 wrong 9, unknown returned 11)
Gc=[g for g in G]
cw=tw2=0
for g in Gc:
    r=query(g['term'], placement=PL)
    if r['origin']=='direct' and cls(r,g['gold'])=='wrong_single':
        cw+=1; tw2+=bool(g.get('suffix_trap'))
uw=ur=0
for u in U:
    r=query(u['term'], context_role=u.get('context_role'), context_predicate=u.get('context_predicate'), placement=PL)
    if u['gold_unknown']: ur+=bool(r['top'])
    else: uw+=cls3(r,u['gold'])=='wrong'
print('COUNTS L2 wrong_direct',cw,'trap_wrong_direct',tw2,'L3 wrong',uw,'L3 unknown_returned',ur)
print('P5 not-worse:',{'L2 wrong<=59':cw<=59,'trap<=9':tw2<=9,'L3 wrong<=9':uw<=9,'unk_returned<=11':ur<=11})

import fugashi

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

"""Independent recomputation of L2 and L3 straight from the public API (the ticket's snippets)."""
import json
from collections import Counter
from verantyx.coarse_place import query
W='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S'
import os
PL=os.environ.get('W3A_PL','/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r2b/run1')   # the final placement (round 2); W3A_PL overrides
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

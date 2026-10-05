import json, collections, sys
from verantyx import semantic_reader as R
diff = collections.Counter(); same = collections.Counter(); n=0
for l in open('artifacts/w3-b5/entry_inputs_r2.txt', encoding='utf-8'):
    l=l.strip()
    if not l: continue
    try: o=json.loads(l); t=o if isinstance(o,str) else (o.get('text') or o.get('input') or '')
    except Exception: t=l
    n+=1
    for w,s,e in R._tokens(t):
        f=w.feature
        if f.pos1=='動詞' and str(f.cType).startswith('下一段'):
            (diff if len(f.pronBase)==len(f.lForm)+1 else same)[(f.lemma,f.orthBase,f.lForm,f.pronBase)]+=1
print(n, 'diff types', len(diff), 'same types', len(same))
print(sorted(diff.items(), key=lambda x:-x[1])[:60])
print(sorted(same.items(), key=lambda x:-x[1])[:15])

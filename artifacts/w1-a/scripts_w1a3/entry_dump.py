import json, sys
from verantyx import semantic_read as SR
W='/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S/'
texts=[]
for l in open(sys.argv[1], encoding='utf-8'): texts.append(json.loads(l)['text'])
for fx in ('B1_v2','B1_v2_r2','B1_v2_r3'):
    for l in open(W+f'tests/bank_score/fixtures/{fx}/items.jsonl', encoding='utf-8'): texts.append(json.loads(l)['input'])
for l in open(W+'tests/reading_soundness/en.jsonl', encoding='utf-8'): texts.append(json.loads(l)['text'])
for l in open(W+'tests/reading_soundness/en_r2.jsonl', encoding='utf-8'): texts.append(json.loads(l)['text'])
seen=set(); out=open(sys.argv[2],'w',encoding='utf-8')
for t in texts:
    if t in seen: continue
    seen.add(t)
    try: r=SR.read(t)
    except Exception as e: r={'error':str(e)}
    out.write(json.dumps({'text':t,'readable':r.get('readable'),'clauses':r.get('clauses'),'abstain':r.get('abstain')},ensure_ascii=False)+'\n')
print(len(seen))

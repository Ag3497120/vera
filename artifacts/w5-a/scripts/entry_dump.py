# usage: entry_dump.py <data_root> <x3_after.jsonl> <out.jsonl>  (data_root: tree whose fixtures/en banks are read; code comes from PYTHONPATH)
import json, sys, os
from verantyx import semantic_read as SR
import verantyx
W=sys.argv[1].rstrip('/')+'/'
texts=[]
for l in open(sys.argv[2], encoding='utf-8'): texts.append(json.loads(l)['text'])
for fx in ('B1_v2','B1_v2_r2','B1_v2_r3'):
    for l in open(W+f'tests/bank_score/fixtures/{fx}/items.jsonl', encoding='utf-8'): texts.append(json.loads(l)['input'])
for l in open(W+'tests/reading_soundness/en.jsonl', encoding='utf-8'): texts.append(json.loads(l)['text'])
for l in open(W+'tests/reading_soundness/en_r2.jsonl', encoding='utf-8'): texts.append(json.loads(l)['text'])
for extra in sys.argv[4:]:
    for l in open(extra, encoding='utf-8'):
        l=l.strip()
        if l: texts.append(l)
seen=set(); out=open(sys.argv[3],'w',encoding='utf-8')
for t in texts:
    if t in seen: continue
    seen.add(t)
    try: r=SR.read(t)
    except Exception as e: r={'error':str(e)}
    out.write(json.dumps({'text':t,'readable':r.get('readable'),'clauses':r.get('clauses'),'abstain':r.get('abstain'),'unsupported':r.get('unsupported')},ensure_ascii=False)+'\n')
bad=[m for m,v in sys.modules.items() if m.startswith('verantyx') and getattr(v,'__file__',None) and not os.path.abspath(v.__file__).startswith(os.environ['PYTHONPATH'])]
print(len(seen), 'foreign', bad)

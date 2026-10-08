import json, sys, collections
def load(p): return {json.loads(l)['text']: json.loads(l) for l in open(p, encoding='utf-8')}
a,b=load(sys.argv[1]),load(sys.argv[2])
assert list(a)==list(b)
cnt=collections.Counter(); rs=collections.Counter()
for t in a:
    x,y=a[t],b[t]
    if x['readable'] and not y['readable']: cnt['readable→false']+=1; rs[y['abstain']['reasons'][0]]+=1; print('R→F',t,y['abstain']['reasons'][0]) if len(sys.argv)>3 else None
    elif x['readable'] and y['readable'] and x['clauses']!=y['clauses']: cnt['changed']+=1; print('CHG',t,x['clauses'],y['clauses'])
    elif not x['readable'] and y['readable']: cnt['false→readable']+=1; print('F→R',t)
    elif not x['readable'] and not y['readable'] and x['abstain']!=y['abstain']: cnt['reason_changed']+=1
print(dict(cnt)); print(dict(rs))

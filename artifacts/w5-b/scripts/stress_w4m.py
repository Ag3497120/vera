import multiprocessing as mp, sys, tempfile, os, collections
from datetime import datetime, timedelta, timezone
from verantyx import sovereign as sov
def day(n): return datetime(2026,10,1,tzinfo=timezone.utc)+timedelta(days=n)
def setup(root, phrases=3):
    sov.create(root,"s1","o",consent_promote=True,now=lambda: day(0))
    led=sov.open_ledger(root,"s1",now=lambda: day(0))
    for k in range(phrases):
        for d in (0,1,1):
            led._now=lambda d=d: day(d); led.append({"kind":"utterance","payload":{"phrase":"p%d"%k}})
def prom(root, q, gate):
    gate.wait(10); q.put(sov.promote(root,"s1",now=lambda: day(3))["verdict"])
def rel(root, q, gate):
    gate.wait(10); q.put(sov.release(root,"s1","s1",now=lambda: day(4))["verdict"])
ctx=mp.get_context("fork"); res=collections.Counter()
N=int(sys.argv[1])
for i in range(N):
    root=tempfile.mkdtemp(prefix="w4m_",dir=sys.argv[2]); setup(root)
    g=ctx.Barrier(2); q=ctx.Queue()
    ps=[ctx.Process(target=prom,args=(root,q,g)) for _ in range(2)]
    [p.start() for p in ps]; v=[q.get(timeout=30) for _ in ps]; [p.join() for p in ps]
    act=sov.active_promotions(root,"s1"); ids=[a["promotion_id"] for a in act]
    res["pp_dup" if len(ids)!=len(set(ids)) else "pp_ok"]+=1; res["pp_active_%d"%len(ids)]+=1
    root=tempfile.mkdtemp(prefix="w4m_",dir=sys.argv[2]); setup(root)
    g=ctx.Barrier(2); q=ctx.Queue()
    ps=[ctx.Process(target=prom,args=(root,q,g)),ctx.Process(target=rel,args=(root,q,g))]
    [p.start() for p in ps]; v=sorted(q.get(timeout=30) for _ in ps); [p.join() for p in ps]
    act=sov.active_promotions(root,"s1")
    res["pr_active_after_release_%d"%len(act)]+=1; res["pr_verdicts:"+"/".join(v)]+=1
print(dict(sorted(res.items())))

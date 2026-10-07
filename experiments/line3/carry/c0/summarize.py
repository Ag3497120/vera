import json, glob, statistics as st
def med(x): return st.median(x) if x else None
print("== single (each sentence alone, empty cross) ==")
print("tier level | sentences settled(%) | units/sent med max | capacity med max | secs/sent mean p90 max | total s")
for t in ("RUN","WORD","CHAR"):
    for l in ("low","mid","high"):
        try: r=json.load(open(f"results/single_{t}_{l}.json"))
        except Exception: print(t,l,"(pending)"); continue
        p=r["per"]; s=sorted(x["secs"] for x in p); ok=sum(x["settled"] for x in p)
        print(t,l,"|",f"{ok}/{len(p)} ({100*ok/len(p):.0f}%)","|",med([x["units"] for x in p]),max(x["units"] for x in p),"|",med([x["cap"] for x in p]),max(x["cap"] for x in p),"|",f"{sum(s)/len(s):.2f} {s[int(.9*len(s))]:.2f} {s[-1]:.2f}","|",f"{sum(s):.0f}")
print("== stream (word by word, close at sentence boundary) ==")
print("tier level | blacks | units/black med max | sents/black med max | blacks w/ 1 sent | split sents (%) | unsettled words | s/sent mean p90 max | total s | est S3000 / S30000 h")
for t in ("RUN","WORD","CHAR"):
    for l in ("low","mid","high"):
        try: r=json.load(open(f"results/stream_{t}_{l}.json"))
        except Exception: print(t,l,"(pending)"); continue
        b=r["blacks"]; u=[x["units"] for x in b]; s=[x["sents"] for x in b]; n=r["n"]
        m=r["sent_secs_mean"]
        print(t,l,"|",len(b),"|",med(u),max(u),"|",med(s),max(s),"|",sum(1 for x in s if x==1),"|",f"{len(r['split'])} ({100*len(r['split'])/n:.0f}%)","|",r["unsettled_words"],"|",f"{m:.2f} {r['sent_secs_p90']:.2f} {r['sent_secs_max']:.2f}","|",r["total_secs"],"|",f"{m*3000/3600:.1f} / {m*30000/3600:.0f}")

import re,sys
names=set()
for d in ["OBSERVATION","ROUTING_FROM_TEXT","BASIS_POLICY","COARSE_PLACEMENT"]:
    t=open(f"docs/{d}.md",encoding="utf-8").read()
    m=re.search(r"<!-- w5d2-amended:begin -->(.*?)<!-- w5d2-amended:end -->",t,re.S).group(1)
    ch=re.findall(r"^##### `([^`]+)` — before",m,re.M)
    ad=re.findall(r"^Added \(helpers / tests, not amendments\): (.*)$",m,re.M)
    print(d,len(ch),"changed;","added:",ad)
    names|=set(ch)
k=set(l.strip() for l in open("artifacts/w5-d/r2/k_functions.txt") if l.strip())
print("k_functions",len(k),"changed-in-docs",len(names))
print("K not in docs:",sorted(k-names))
print("docs-changed not K:",sorted(names-k))

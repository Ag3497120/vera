import json,re
K=["父","母","祖父","祖母","叔父","叔母","伯父","伯母","兄","姉","弟","妹","息子","娘","夫","妻","孫"]
n=0;hit=[];subj=[]
for l in open("tests/bank_score/fixtures/B2/items.jsonl",encoding="utf-8"):
    if not l.strip(): continue
    o=json.loads(l); n+=1
    s=json.dumps(o,ensure_ascii=False)
    if any(k in s for k in K):
        hit.append(o["id"])
        if re.search(r"(%s)(が|は)"%"|".join(K), s): subj.append(o["id"])
print("items",n); print("kin_containing",len(hit),hit); print("kin_followed_by_が/は",len(subj),subj)

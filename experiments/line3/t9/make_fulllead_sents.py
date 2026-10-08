"""Derive bank2/data/fulllead_sents.jsonl from data/S300_fulllead.jsonl: split "text" on 「。」 (keep 「。」 on each
sentence, drop empty/whitespace-only pieces, a trailing piece without 「。」 is kept as is). Row fields as S300.jsonl:
sha = sha256(sentence utf-8), title, sent, source = "<title>#<i>" (i = 0-based index in the split)."""
import hashlib, json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, "..", "data")
out = []
for l in open(os.path.join(D, "S300_fulllead.jsonl"), encoding="utf-8"):
    d = json.loads(l); i = 0
    parts = d["text"].split("。")
    sents = [p + "。" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    for s in sents:
        if not s.strip("。 　\n"):
            continue
        out.append({"sha": hashlib.sha256(s.encode("utf-8")).hexdigest(), "title": d["title"], "sent": s, "source": "%s#%d" % (d["title"], i)})
        i += 1
p = os.path.join(H, "..", "bank2", "data", "fulllead_sents.jsonl")
with open(p, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(out), hashlib.sha256(open(p, "rb").read()).hexdigest())

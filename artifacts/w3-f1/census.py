"""凍結データの文を frames.read_all で読み、agent/patient/recipient の値で canonical(v) が v より短いものを全件 TSV に。使い方: census.py OUT.tsv"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verantyx import frames
def strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from strings(v)
    elif isinstance(o, list):
        for v in o: yield from strings(v)
files = sorted(list((ROOT/"tests/reading_soundness").glob("*.jsonl")) + list((ROOT/"tests/observe/question_ask").rglob("*.jsonl")) + list((ROOT/"tests/bank_score/fixtures/B1").glob("items.jsonl")) + list((ROOT/"tests/bank_score/fixtures/B2").glob("items.jsonl")))
texts = []
for f in files:
    for l in f.read_text(encoding="utf-8").splitlines():
        if not l.strip(): continue
        try: o = json.loads(l)
        except Exception: continue
        for s in strings(o): texts.append((str(f.relative_to(ROOT)), s))
for f in sorted((ROOT/"tests/observe/question_ask").rglob("*.txt")) + sorted((ROOT/"tests/observe/question_ask").rglob("*.md")):
    texts.append((str(f.relative_to(ROOT)), f.read_text(encoding="utf-8")))
seen = {}
nsent = set()
for src, t in texts:
    for s in re.split(r"(?<=[。！？\n])", t):
        s = s.strip()
        if not s or not re.search(r"[぀-ヿ一-鿿]", s): continue
        nsent.add(s)
        try: frs = frames.read_all(s)
        except Exception: continue
        for fr in frs:
            for role in ("agent", "patient", "recipient"):
                v = getattr(fr, role)
                if v:
                    c = frames.canonical(v)
                    if c != v and len(c) < len(v):
                        seen.setdefault((v, c), set()).add(src)
with open(sys.argv[1], "w", encoding="utf-8") as o:
    o.write("value\tcanonical\tfiles\n")
    for (v, c), fs in sorted(seen.items()):
        o.write(f"{v}\t{c}\t{';'.join(sorted(fs))}\n")
print(len(nsent), "sentences", len(seen), "pairs")

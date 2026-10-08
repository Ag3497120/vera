"""Leaves = scenes of the Codex corpus (variants merged), one CrossStore each; saved per leaf."""
import json, re, sys, time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.cross_store import CrossStore  # noqa: E402
from verantyx.document_ingest import Document, ingest_documents  # noqa: E402
C = Path.home() / "Projects/vera-corpus/codex"
OUT = Path.home() / "Projects/vera-corpus/build/scene_tree"; OUT.mkdir(parents=True, exist_ok=True)
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
by = defaultdict(list)
for f in ("sentences.jsonl", "pro/sentences.jsonl", "local/sentences.jsonl"):
    p = C / f
    if not p.exists():
        continue
    for line in open(p):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        base = re.sub(r"（.*?）", "", r.get("scene") or "").strip()
        if base and len(by[base]) < CAP:
            by[base].append(r["text"])
t = time.time(); index = {}
for i, (scene, texts) in enumerate(sorted(by.items())):
    st = CrossStore(); ingest_documents(st, [Document(source=scene, text="".join(texts))])
    name = "場面%03d" % i
    st.save(OUT / (name + ".json")); index[name] = {"scene": scene, "sentences": len(texts), "cores": st.n_cores()}
    if i % 20 == 0:
        print(i, scene, len(texts), st.n_cores(), "%.0fs" % (time.time() - t), flush=True)
(OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
print("done", len(index), "leaves", "%.0fs" % (time.time() - t))

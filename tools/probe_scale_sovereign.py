"""(1) corpus size vs answers; (2) one tree vs two federated sovereigns (rules / records)."""
import json, re, sqlite3, statistics, sys, time, zlib
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.typed_edges import _tagger  # noqa: E402
G = Path.home() / "Projects/vera-corpus/build/general.db"
con = sqlite3.connect(f"file:{G}?mode=ro", uri=True)
WORDS = ["氷", "石", "岩", "絹", "山", "風", "鈴", "雪", "花", "星", "月", "海", "川", "火", "鉄", "綿", "雲", "雷", "天使", "鬼",
         "猫", "犬", "子ども", "赤ちゃん", "宝石", "ガラス", "鏡", "羽", "嵐", "夢"]
STOP = {"為る", "成る", "物", "事", "する", "なる", "ある", "いる", "居る", "有る", "見える", "思う", "言う", "よう", "感じる"}
rows_by = {}
for b in WORDS:
    rows_by[b] = con.execute("SELECT text, src FROM tsent WHERE text LIKE ? LIMIT 3000", ("%" + b + "のよう%",)).fetchall()


def top(b, frac):
    c = {}
    for text, src in rows_by[b]:
        if zlib.crc32(src.encode()) % 100 >= frac:
            continue
        for m in re.finditer(re.escape(b) + r"のよう(?:に|な)(.{1,12})", text):
            for w in _tagger()(m.group(1)):
                k = w.feature.lemma or w.surface
                if w.feature.pos1 in ("形容詞", "動詞", "形状詞") and k not in STOP:
                    c.setdefault(k, set()).add(src); break
    r = sorted(((w, len(v)) for w, v in c.items() if len(v) >= 2), key=lambda x: -x[1])
    return r[0][0] if r else None


full = {b: top(b, 100) for b in WORDS}
print("== corpus size vs metaphor answers (30 words)")
for frac in (10, 30, 60, 100):
    ans = {b: top(b, frac) for b in WORDS}
    cov = sum(1 for v in ans.values() if v); same = sum(1 for b in WORDS if ans[b] and ans[b] == full[b])
    print("  %3d%% of sources: answered %2d/30, same as full %2d/%d" % (frac, cov, same, cov))
print("  full:", {b: full[b] for b in WORDS if full[b]})

# (2) sovereigns
from verantyx.base import Base  # noqa: E402
from verantyx.cross_store import CrossStore  # noqa: E402
from verantyx.document_ingest import Document, ingest_documents  # noqa: E402
from verantyx.hierarchy import Node, federate  # noqa: E402
from verantyx.sovereign import group_into_layers  # noqa: E402
from verantyx.verdict import judge  # noqa: E402
B = Path.home() / "Projects/vera-corpus/benches"
target = json.loads((B / "verdict_heldout4_raw.json").read_text())["docs"]
others = [d for f in ("verdict_heldout_raw.json", "verdict_heldout2_raw.json", "verdict_heldout3_raw.json") for d in json.loads((B / f).read_text())["docs"]]
base = Base()
kinds = {}
for k, d in enumerate(target + others):
    base.add("文書%03d" % k, d["ja"], d["kind"]); kinds["文書%03d" % k] = d["kind"]
base.build()
one_root = base.root
leaves = {}
for name, d in base.docs.items():
    st = CrossStore(); ingest_documents(st, [Document(source=name, text=d["text"])]); leaves[name] = Node(name=name, store=st)
sov = {"規程": group_into_layers("規程", {n: l for n, l in leaves.items() if kinds[n] == "rules"}),
       "記録": group_into_layers("記録", {n: l for n, l in leaves.items() if kinds[n] == "record"})}
two_root = federate("主権", sov)
harm = lambda g, v: (g == "SUPPORTED" and v in ("CONTRADICTED", "VIOLATES")) or (g in ("NOT_IN_DOCS", "UNCONFIRMED", "DIFFERENT") and v == "SUPPORTED")
print("== one tree vs two sovereigns (160 docs, 200 claims)")
for name, root in (("one tree", one_root), ("two sovereigns", two_root)):
    base.root = root
    c, paths, ms = Counter(), Counter(), []
    for k, d in enumerate(target):
        for cl in d["claims"]:
            r = base.judge(cl["ja"]); g = cl["label"]
            c["n"] += 1; c["ok"] += r["verdict"] == g; c["harm"] += harm(g, r["verdict"]); ms.append(r["ms"])
            paths["right" if r["leaf"] == "文書%03d" % k else ("refused" if r["leaf"] is None else "wrong")] += 1
    n = c["n"]
    print("  %-15s accuracy %.3f harm %.3f median %.2fms routing %s" % (name, c["ok"] / n, c["harm"] / n, statistics.median(ms),
          {k: round(v / n, 3) for k, v in paths.items()}))

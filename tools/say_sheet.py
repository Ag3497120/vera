"""Generate grounded paragraphs for fixed topics, recheck, and write a sheet."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.frames import read, read_all  # noqa: E402
from verantyx.say import say  # noqa: E402

name, topics = sys.argv[1], sys.argv[2:]
sheet = ["# 自由文生成 %s" % name, ""]
rows, n, ok, silent = [], 0, 0, 0
for t in topics:
    r = say(t, k=5)
    sheet.append("## " + t)
    if r["verdict"] != "GROUNDED":
        silent += 1
        sheet.append("（言えることが無い）\n")
        continue
    for l in r["lines"]:
        n += 1
        fr = read(l["sentence"]).key()
        hit = any(fr == f.key() for w in l["witnesses"] for f in read_all(w["text"]))
        ok += hit
        sheet.append("- %s　（出所%d件。例: %s）" % (l["sentence"], l["sources"], l["witnesses"][0]["text"][:60]))
        rows.append({"topic": t, **l, "recheck": hit})
    sheet.append("")
b = Path.home() / "Projects" / "vera-corpus" / "build"
(b / ("say_%s.md" % name)).write_text("\n".join(sheet), encoding="utf-8")
(b / ("say_%s.json" % name)).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"sentences": n, "recheck_ok": ok, "silent_topics": silent}))

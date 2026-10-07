"""T7 acceptance: 20 legacy / round5 CLI invocations (10 each) whose stdout + exit code are recorded
BEFORE the T7 change (cli_baseline.json) and compared byte for byte after it.
usage: record_cli.py record|check [FILE]"""
import hashlib
import re
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
BASE = os.path.join(HERE, "cli_baseline.json")
SENTS = ["東京は日本の首都である。", "大阪は日本の都市である。", "富士山は日本一高い山である。"]
DOC = "太郎は花子に本を渡した。花子は東京の大学で物理学を学んでいる。\n"
LEGACY_Q = ["東京は日本の首都ですか", "大阪は何の都市ですか", "富士山はどこにありますか", "2+3は", "1+1=",
            "日本の首都は", "月の直径は", "火星に海はありますか", "ペンギンは飛べますか", "水の沸点は"]
ROUND5_Q = ["誰が花子に本を渡したか", "太郎は誰に本を渡したか", "花子はどこで物理学を学んでいるか", "太郎は花子に何を渡したか",
            "誰が花子に本を渡しましたか", "花子は何を学んでいるか", "その本はいつ出版されたか", "誰が花子に本を渡した？",
            "太郎は誰に本を渡した？", "花子はどこにいるか"]


# wall-clock fields ("ingest_ms": 82.1...) are the only thing the legacy / round5 output carries that varies from run to run
MS = re.compile(r'("\w*_ms": )[0-9.eE+-]+')


def env():
    e = {k: v for k, v in os.environ.items() if not k.startswith("VERA_")}
    e.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
    return e


def run(args, cwd):
    r = subprocess.run([sys.executable, "-m", "verantyx.cli"] + args, capture_output=True, text=True, cwd=cwd,
                       env=env(), timeout=300)
    return {"args": [a if not a.startswith(cwd) else "<TMP>" + a[len(cwd):] for a in args],
            "rc": r.returncode, "stdout": MS.sub(r"\1<ms>", r.stdout.replace(cwd, "<TMP>")), "stderr_sha": hashlib.sha256(
                r.stderr.replace(cwd, "<TMP>").encode()).hexdigest()}


def collect():
    out = []
    d = os.path.join(HERE, "_work")          # a FIXED directory: round5 outputs carry the document path
    os.makedirs(d, exist_ok=True)
    for f in ("store.json", "store.json.lock"):
        if os.path.exists(os.path.join(d, f)):
            os.remove(os.path.join(d, f))
    if True:
        store = os.path.join(d, "store.json")
        doc = os.path.join(d, "doc.txt")
        open(doc, "w", encoding="utf-8").write(DOC)
        for s in SENTS:
            run(["--store", store, "remember", s], d)
        for q in LEGACY_Q:
            out.append(run(["--store", store, "ask", q], d))
        for q in ROUND5_Q:
            out.append(run(["--store", store, "ask", "--mode", "round5", "--document", doc, q], d))
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else BASE
    got = collect()
    if mode == "record":
        json.dump(got, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        print("recorded", len(got), "->", path)
    else:
        want = json.load(open(path, encoding="utf-8"))
        bad = [i for i, (a, b) in enumerate(zip(got, want)) if a != b]
        print("%d / %d identical" % (len(got) - len(bad) + (0 if len(got) == len(want) else -999), len(want)))
        sys.exit(1 if bad or len(got) != len(want) else 0)

"""データの凍結: data/ の全ファイルの sha256・バイト数・時刻を FROZEN.json と freeze.txt に書く。

python -m benchmarks.public_v1.freeze --freeze-txt artifacts/w14-bench/freeze.txt [--checked-by ...]
既に FROZEN.json が有れば何もせず rc=2（凍結後に書き換えない）。corrections.jsonl は凍結の対象外（追記のみ）。
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "data")
EXCLUDE = {"FROZEN.json", "corrections.jsonl"}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def data_files():
    out = []
    for root, _dirs, files in os.walk(DATA):
        for fn in files:
            if fn in EXCLUDE or fn.startswith("."):
                continue
            out.append(os.path.join(root, fn))
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-txt", required=True)
    ap.add_argument("--frozen-by", default="Claude Sonnet 5.5（実装役。人ではない）")
    ap.add_argument("--checked-by", default="pending: 中間職")
    a = ap.parse_args(argv)
    fj = os.path.join(DATA, "FROZEN.json")
    if os.path.exists(fj):
        print("FROZEN.json が既に有る。凍結後は書き換えない（訂正は corrections.jsonl に追記）。", file=sys.stderr)
        return 2
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    entries = []
    txt = []
    for p in data_files():
        rel = os.path.relpath(p, REPO)
        h = sha256_file(p)
        entries.append({"path": os.path.relpath(p, DATA), "sha256": h, "bytes": os.path.getsize(p)})
        txt.append("%s  %s" % (h, rel))
    with open(fj, "w", encoding="utf-8") as f:
        json.dump({"frozen_at": now, "frozen_by": a.frozen_by, "checked_by": a.checked_by,
                   "excluded": sorted(EXCLUDE), "files": entries}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(a.freeze_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(txt) + "\n")
    print("frozen %d files at %s" % (len(entries), now))
    return 0


if __name__ == "__main__":
    sys.exit(main())

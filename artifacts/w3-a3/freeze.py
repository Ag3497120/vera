"""Freeze the W3-a3 verb test data (write FROZEN.json) or check it (--check).

  freeze.py          write artifacts/w3-a3/FROZEN.json (sha256, lines, frozen_at = `date '+%F %T %z'`)
  freeze.py --check  compare every file with FROZEN.json; exit 0 when all match, 1 otherwise

The files frozen are the test data, the hand-written specs they are made from, the script that
makes them, the pre-registration text and the list of coined verbs passed to --exclude-terms.
"""
import hashlib
import json
import os
import subprocess
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
OUT = os.path.join(W, "artifacts/w3-a3/FROZEN.json")
FILES = [
    "tests/coarse_place/data/dev_verbs.jsonl",
    "tests/coarse_place/data/verb_check_300.jsonl",
    "artifacts/w3-a3/exclude_coined.jsonl",
    "artifacts/w3-a3/dev_verbs_spec.txt",
    "artifacts/w3-a3/verb_check_spec.txt",
    "artifacts/w3-a3/make_verb_data.py",
    "artifacts/w3-a3/coined_absent.txt",
    "artifacts/w3-a3/PREREG.md",
]


def meta(rel):
    data = open(os.path.join(W, rel), "rb").read()
    return {"sha256": hashlib.sha256(data).hexdigest(), "lines": data.count(b"\n"), "bytes": len(data)}


def now():
    return subprocess.run(["date", "+%F %T %z"], capture_output=True, text=True).stdout.strip()


def main():
    if "--check" in sys.argv:
        fr = json.load(open(OUT, encoding="utf-8"))
        bad = [rel for rel, m in fr["files"].items() if meta(rel) != m]
        print(json.dumps({"state": "OK" if not bad else "MISMATCH", "bad": bad,
                          "frozen_at": fr["frozen_at"], "files": len(fr["files"])}, ensure_ascii=False))
        return 0 if not bad else 1
    diff = subprocess.run(["git", "-C", W, "diff", "--stat", "--", "verantyx", "tools"],
                          capture_output=True, text=True).stdout.strip()
    out = {"frozen_at": now(), "files": {rel: meta(rel) for rel in FILES},
           "product_code_diff_stat_at_freeze": diff or "(empty)"}
    dev = [json.loads(l) for l in open(os.path.join(W, FILES[0]), encoding="utf-8")]
    chk = [json.loads(l) for l in open(os.path.join(W, FILES[1]), encoding="utf-8")]
    from collections import Counter
    out["dev_kinds"] = dict(Counter(r["kind"] for r in dev))
    out["check_kinds"] = dict(Counter(r["kind"] for r in chk))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    open(OUT, "a").write("\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""README.md と docs/BENCHMARK_PUBLIC.md §2 の数値部分を、採点器の出力（table.md）から機械で貼る。
手で数値を書かない（指示書 §5-10）。

python -m benchmarks.public_v1.render_docs --run-dir artifacts/w14-bench --readme benchmarks/public_v1/README.md \
    --docs docs/BENCHMARK_PUBLIC.md --extras artifacts/w14-bench/extras
"""
import argparse
import json
import os
import re
import sys

from . import data as D, prompts, validate

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BEGIN = "<!-- BEGIN:%s -->"
END = "<!-- END:%s -->"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def block(name, body):
    return "%s\n%s\n%s" % (BEGIN % name, body.rstrip("\n"), END % name)


def replace_block(text, name, body):
    pat = re.compile(re.escape(BEGIN % name) + r".*?" + re.escape(END % name), re.S)
    if pat.search(text):
        return pat.sub(lambda m: block(name, body), text)
    return None


def data_summary():
    err, info, qs, _dup = validate.validate()
    fr = json.load(open(os.path.join(D.DATA, "FROZEN.json"), encoding="utf-8"))
    q = [e for e in fr["files"] if e["path"] == "questions.jsonl"][0]
    L = ["| 項目 | 値 |", "|---|---|"]
    for k, v in info.items():
        L.append("| %s | %s |" % (k, v))
    L.append("| 検査（validate） | %s |" % ("全部通過" if not err else "NG %d 件" % len(err)))
    L.append("| 凍結の時刻 | %s |" % fr["frozen_at"])
    L.append("| 書き手 | %s |" % fr["frozen_by"])
    L.append("| 検査・承認 | %s |" % fr["checked_by"])
    L.append("| questions.jsonl の sha256 | `%s` |" % q["sha256"])
    L.append("| 凍結したファイル数 | %d（`data/FROZEN.json` に全ファイルの sha256） |" % len(fr["files"]))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="artifacts/w14-bench（run1/table, run2/table が有る）")
    ap.add_argument("--readme", required=True)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--table", default="run1/table/table.md")
    a = ap.parse_args(argv)
    table = read(os.path.join(a.run_dir, a.table))
    table = re.sub(r"^# ", "### ", table, flags=re.M)
    table = re.sub(r"^## ", "#### ", table, flags=re.M)
    table = re.sub(r"^### (1a|1b|4b)", r"##### \1", table, flags=re.M)
    readme = read(a.readme)
    for name, body in (("TABLE", table), ("DATA", data_summary()),
                       ("TEMPLATE", "```\n" + prompts.HEAD + "\n<文の列（1 行に 1 文、\"[D1_bihin_kitei.txt:12] 本文\"）>\n\n" + prompts.RULES + "\n```")):
        new = replace_block(readme, name, body)
        if new is None:
            raise SystemExit("README に %s のブロックが無い" % name)
        readme = new
    with open(a.readme, "w", encoding="utf-8") as f:
        f.write(readme)
    docs = read(a.docs)
    new = replace_block(docs, "RESULTS", table)
    if new is None:
        raise SystemExit("docs に RESULTS のブロックが無い")
    with open(a.docs, "w", encoding="utf-8") as f:
        f.write(new)
    print("rendered README and docs from", os.path.join(a.run_dir, a.table))
    return 0


if __name__ == "__main__":
    sys.exit(main())

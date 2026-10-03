"""W2-g2: checks the numbers of docs/CONDUCT_ASK.md section 14 against the saved outputs.
  1. the block between <!-- g2-tables:begin --> and <!-- g2-tables:end --> is exactly the output of make_docs_tables.py (every table cell and the
     judgement / reading / budget lines come from summary.json / results.jsonl / ledger.jsonl / merge_b/summary.json);
  2. the frozen times and the data shape written in the text equal the saved files (freeze_code.txt, fixtures_freeze3.txt, fixtures3_shape.txt);
  3. the test counts written in the text equal the collected counts.
Prints one line per check and, last, ``MISSING lines: N`` (N = the number of checks that failed).
Usage (repository root):  artifacts/w2-g/py.sh artifacts/w2-g/g2/docs_check_g2.py"""
import re
import subprocess
import sys

DOCS = "docs/CONDUCT_ASK.md"
text = open(DOCS, encoding="utf-8").read()
i = text.index("## 14. 照会の分割と再照会")
sec14 = text[i:]
missing = 0


def check(name, ok, detail=""):
    global missing
    if not ok:
        missing += 1
    print(("OK      " if ok else "MISSING ") + name + (f"  {detail}" if detail and not ok else ""))


# 1. the generated block
gen = subprocess.run([sys.executable, "artifacts/w2-g/g2/make_docs_tables.py"], capture_output=True, text=True, check=True).stdout.rstrip("\n") + "\n"
b, e = sec14.index("<!-- g2-tables:begin -->\n") + len("<!-- g2-tables:begin -->\n"), sec14.index("<!-- g2-tables:end -->\n")
check("tables block equals make_docs_tables.py output", sec14[b:e] == gen)
for line in gen.splitlines():
    if line.strip() and line not in sec14:
        check("generated line present", False, line[:80])

# 2. freeze times
def freeze_time(path):
    ls = [ln for ln in open(path, encoding="utf-8").read().splitlines() if "JST" in ln]
    m = re.search(r"(\w+) +(\d+) +(\d\d:\d\d:\d\d) JST (\d{4})", ls[0])
    mon = {"Oct": "10"}[m.group(1)]
    return f"{m.group(4)}-{mon}-{int(m.group(2)):02d} {m.group(3)} JST", m.group(3)

full, hhmmss = freeze_time("artifacts/w2-g/g2/freeze_code.txt")
check("code freeze time in the text", full in sec14 and hhmmss in sec14, full)
full3, hhmmss3 = freeze_time("artifacts/w2-g/fixtures_freeze3.txt")
check("data freeze time in the text", hhmmss3 in sec14, hhmmss3)
check("code freeze time < data freeze time < first w2g3 ledger ts", hhmmss < hhmmss3)
import json
first_ts = []
for d in ("low", "xhigh"):
    first = next(json.loads(ln) for ln in open(f"artifacts/w2-g/live_g2/w2g3/{d}/ledger.jsonl", encoding="utf-8") if ln.strip())
    first_ts.append(first["ts"])
check("w2g3 ledgers start after the data freeze (UTC, JST - 9h)", all(t[11:19] > "00:22:53" for t in first_ts), str(first_ts))

# 3. data shape
shape = open("artifacts/w2-g/g2/fixtures3_shape.txt", encoding="utf-8").read()
for needle, why in (("order questions with an answer expected 14 by category {'direct': 2, 'combined': 9, 'oov': 3}", "order 14 (2/9/3)"),
                    ("order-shaped 5, preference without options 2", "order-shaped 5, preference 2"),
                    ("questions to answer with three or more options 12", "3+ options 12"),
                    ("questions without options 8 (value answers 6)", "no options 8 (6 values)"),
                    ("option counts {0: 8, 2: 40, 3: 11, 4: 1}", "option counts"),
                    ("'A': 2, 'B_PAST': 1, 'C': 2, 'D': 1, 'E': 2", "escalate kinds")):
    check("shape file has: " + why, needle in shape)
for needle, why in (("順序を尋ねる問い 14（直接 2・組合せ 9・語彙外 3", "text: order 14"), ("「順序の形で別の事業・別の時・日数・担当者を尋ねる問い」5", "text: order-shaped 5"),
                    ("「肢なしで好み・推奨を尋ねる問い」2", "text: preference 2"), ("肢が 3 つ以上で答えるのが正解の問い 12（4 肢が 1）", "text: 3+ options 12"),
                    ("肢なしの値の問い 6（+ 好みの肢なし 2）", "text: value 6"),
                    ("人間の承認が必要 2・枠内の矛盾 1・並列の順序 2・過去形 1・決めていない側面 2", "text: kinds"), ("枠 6（日本語 3・英語 3）、60 問", "text: frames and questions")):
    check(why, needle in sec14)

# 4. test counts
def collected(path):
    out = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--collect-only", "-q", path], capture_output=True, text=True).stdout
    return int(re.search(r"(\d+) tests? collected", out).group(1))

n_reply2, n_g9 = collected("tests/test_conduct_map_reply2.py"), collected("tests/test_conduct_map_g9.py")
n_g9_def = open("tests/test_conduct_map_g9.py", encoding="utf-8").read().count("\ndef test_")
check(f"reply2 count {n_reply2} in the text", f"（{n_reply2} 件）" in sec14)
check(f"g9 counts (functions {n_g9_def}, collected {n_g9}) in the text", f"関数 {n_g9_def}、パラメータの展開後 {n_g9} 件" in sec14)

# 5. the numbers that are in the text outside the generated block
for needle, why in (("1 問の最悪は 2 + 24 = **26 回**", "worst case 26"), ("既定 **24**", "default cap 24"), ("`max_parallel`（既定 6。設定値）", "max_parallel 6")):
    check(why, needle in sec14)
print(f"MISSING lines: {missing}")

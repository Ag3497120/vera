"""G7 (review 1 must-fix 4): every number of docs/CONDUCT_ASK.md section 13.9 that comes from artifacts/w2-g/ is recomputed from the saved
output and looked up in the document.  Prints one line per number (OK / MISSING) and the count of MISSING lines.  The numbers that a
run writes at every execution (seconds) are read from the saved summary.json that the document cites, never from a re-run."""
import json, sys
from pathlib import Path

DOC = Path("docs/CONDUCT_ASK.md").read_text(encoding="utf-8")
sec = DOC[DOC.index("### 13.9"):DOC.index("### 13.10")]
missing = 0
def check(label, text):
    global missing
    ok = text in sec
    missing += 0 if ok else 1
    print(("OK      " if ok else "MISSING ") + f"{label}: {text}")
def load(d):
    return json.load(open(f"artifacts/w2-g/{d}/summary.json"))
def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)
for arg in sys.argv[1:]:
    d, _, mode = arg.partition(":")           # "<dir>" checks every number of the table row; "<dir>:short" only the counts
    s = load(d)
    e = s["elapsed"]
    if mode != "short":
        check(f"{d} wall_s", f"{fmt(e['wall_s'])} 秒")
        check(f"{d} median_s", f"{fmt(e['median_s'])} 秒")
        check(f"{d} max_s", f"{fmt(e['max_s'])} 秒")
    check(f"{d} asks", str(s["asks"]["total"]))
    check(f"{d} correct", f"{s['correct']} / {s['answer_expected']}")
    check(f"{d} q2 rate", f"{s['q2_answer_rate']}")
    if s["escalate_expected"]:
        check(f"{d} escalate correct", f"{s['escalate_correct']} / {s['escalate_expected']}")
    check(f"{d} wrong", f"{s['q1_wrong_count']}")
import glob
total = 0
for path in glob.glob("artifacts/w2-g/live/**/ledger.jsonl", recursive=True):
    for ln in open(path, encoding="utf-8"):
        if ln.strip():
            r = json.loads(ln)
            if r.get("type") in ("map_ask", "ask") and r.get("verdict") != "SKIPPED_DECIDED":
                total += 1
check("total provider asks (budget.py)", f"合計は {total:,} 回")
for k, v in (("oracle correct", "42 / 48（0.875）"),):
    o = load("g3_w2g2/fake_oracle")
    check(k, f"{o['correct']} / {o['answer_expected']}（{o['q2_answer_rate']}）")
# round 3: the merged 64-question G3 numbers (merge_r3.py output) and the order-route re-runs
for d in ("w2g2/merged_r3b_codex_codex", "w2g2/merged_r3a_codex_codex", "w2g2/merged_r3b_codex_claude"):
    m = load("live/" + d)
    check(f"{d} correct", f"{m['correct']} / {m['answer_expected']}")
    check(f"{d} q2 rate", f"{m['q2_answer_rate']}")
    check(f"{d} wrong", f"{m['q1_wrong_count']}")
    check(f"{d} escalate", f"{m['escalate_correct']} / {m['escalate_expected']}")
print("MISSING lines:", missing)

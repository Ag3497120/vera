"""evidence.v5 scan of the question sets (offline, no model): for how many questions of bank2 / bank4 / bank6 / bank7 does SU fire (the cut drops a non-grammar piece of the subject phrase), how many
have a kind-word-only subject (TW), and, for the record, how many would fire under the LITERAL reading of SU (every character of the subject phrase that is neither in a kept unit nor in a function
unit, hiragana tails of 使われた included).   PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/loom/ev5/su_scan.py   (reads the four dev tsv files only)"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, ROOT)
from verantyx.loom import evidence as ev
from verantyx.line3 import grammar as gm, space as sp
from verantyx.line3.granularity import _raw_spans
from verantyx.line3.funcwords import is_function_unit

SETS = (("bank2", "experiments/line3/bank2/bank2.tsv"), ("bank4", "experiments/line3/bank4/bank4.tsv"), ("bank6", "experiments/line3/bank6/bank6.tsv"), ("bank7", "experiments/line3/bank7/bank7.tsv"))


def literal_unread(qu):
    """SU without the hiragana exemption (every alphanumeric character of the subject phrase outside the kept and the function units)."""
    t = qu.text
    ws = gm.words_of(t)
    s = t.find(qu.slot_phrase) if qu.slot_phrase else -1
    if s < 0:
        q = next((w for w in ws if w[0] in gm.INTERROG), None)
        if q is None:
            return ()
        s = q[1]
    piv = max([w[1] for w in ws if w[0] in ("は", "が") and w[2] <= s], default=s)
    cov = set()
    for _u, a, b in ev._s_runs(t, ws)[0]:
        cov.update(range(a, b))
    for u, a, b in _raw_spans(sp.RUN, t):
        if is_function_unit(u, sp.RUN):
            cov.update(range(a, b))
    out, cur = [], ""
    for k in range(piv):
        if k not in cov and t[k].isalnum() and t[k] not in ev.IGNORE:
            cur += t[k]
        else:
            if cur:
                out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return tuple(out)


def main():
    for name, f in SETS:
        rows = [r for r in csv.DictReader(open(os.path.join(ROOT, f), encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE) if r["question"]]
        fire, lit, kind = [], 0, []
        for r in rows:
            qu = ev.question_units(r["question"])
            un = ev.subject_unread(qu)
            if un:
                fire.append((r["#id"], r["kind"], r["question"], list(un)))
            if literal_unread(qu):
                lit += 1
            if ev.kind_only_subject(qu):
                kind.append((r["#id"], r["kind"], r["question"], list(qu.subject)))
        print("== %s: %d questions, SU fires %d, literal-SU would fire %d, kind-word-only subject %d" % (name, len(rows), len(fire), lit, len(kind)))
        for x in fire:
            print("   SU  ", x)
        for x in kind:
            print("   KIND", x)


if __name__ == "__main__":
    main()

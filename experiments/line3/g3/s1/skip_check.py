"""G3-e / L-646 on the real corpus: the exact skip.  For a sample of bank2 fulllead questions, read (a) only the windows that hold a
question unit, (b) every window with the admission gate (what exact skip must equal), (c) every window WITHOUT the gate (how many entries
the windows that hold no question unit would have given).  usage: skip_check.py CACHE OUT.txt [STEP=8] [AGREEMENT=two_if_single_edge] [MEMBERS=representative]"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_query as Q   # noqa: E402

cache, outp = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 8
agr = sys.argv[4] if len(sys.argv) > 4 else "two_if_single_edge"
mem = sys.argv[5] if len(sys.argv) > 5 else "representative"
wi = Q.WindowIndex.from_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), cache, build=False)
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv"), encoding="utf-8")
        if not l.startswith("#") and l.strip()]
rows = [r for r in rows if r[2] == "fulllead" and r[1] in ("intra2", "unans")][::step]
lines = ["skip check: %d questions, agreement %s, members %s, %d windows; slide %s place %s" % (
    len(rows), agr, mem, len(wi.windows), wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12])]
tot = dict(q=0, equal=0, gated_entries_outside=0, read_exact=0, read_all=0, extra_entries=0, extra_windows=0, extra_q=0)
for r in rows:
    t0 = time.time()
    kw = dict(agreement=agr, members=mem)
    a = Q.ask_slide(wi, r[4], **kw)
    b = Q.ask_slide(wi, r[4], skip="none", **kw)
    c = Q.ask_slide(wi, r[4], skip="none", gate=False, **kw)
    planned = set(a.plan.read)
    extra = [e for x in c.reads if x.window not in planned for e in x.entries]
    # review: ask_slide keeps only the planned windows' entries, so a == b alone holds whatever the gate does; the test of the gate is
    # that the windows the exact skip did not read admit no entry under the gate
    gated = sum(len(x.entries) for x in b.reads if x.window not in planned)
    eq = a.entries == b.entries and a.abstentions == b.abstentions and a.verdict == b.verdict and gated == 0
    tot["q"] += 1; tot["equal"] += eq; tot["gated_entries_outside"] += gated; tot["read_exact"] += a.windows_read; tot["read_all"] += b.windows_read
    tot["extra_entries"] += len(extra); tot["extra_windows"] += len({e["window"]["n"] for e in extra}); tot["extra_q"] += bool(extra)
    lines.append("%s %-8s entries %d verdict %s | read %d of %d windows | equal %s (gated entries outside the plan %d) | without the gate +%d entries in %d windows that hold no question unit (%.0fs)" % (
        r[0], r[1], len(a.entries), a.verdict, a.windows_read, b.windows_read, eq, gated, len(extra), len({e["window"]["n"] for e in extra}), time.time() - t0))
    print(lines[-1], flush=True)
lines.append("TOTAL %s" % json.dumps(tot, sort_keys=True))
open(outp, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(lines[-1])

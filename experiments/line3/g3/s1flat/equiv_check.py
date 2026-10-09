"""G3-f: the runs of results_pre/ (made with earlier states of slide_flat.py: the first without the `evidence` switch, then with it) against the same runs
of results/ (the final slide_flat.py): the verdict, the entries' words / centres / arrangements / source_sids / window and the typed abstentions of every
question must be equal.  usage: equiv_check.py  -> prints one line per run and a total."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
A, B = os.path.join(HERE, "results_pre"), os.path.join(HERE, "results")


def key(r):
    return (r["verdict"], [(e["window"], tuple(e["words"]), tuple(e["centres"]), e["arrangements"], tuple(e["source_sids"]), e["stability"]) for e in r["entries"]],
            json.dumps(r["abstentions"], sort_keys=True), r["read"]["windows_read"])


bad = tot = 0
for f in sorted(os.listdir(A)):
    if not f.endswith(".jsonl") or not os.path.exists(os.path.join(B, f)):
        continue
    a = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(A, f), encoding="utf-8")}
    b = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(B, f), encoding="utf-8")}
    diff = [i for i in a if i in b and key(a[i]) != key(b[i])]
    print("%-45s %d questions, %d differ%s" % (f, len(a), len(diff), " " + " ".join(diff[:5]) if diff else ""))
    bad += len(diff); tot += len(a)
print("total %d questions compared, %d differ" % (tot, bad))
sys.exit(1 if bad else 0)

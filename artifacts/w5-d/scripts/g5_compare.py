"""W5-d G5: compare the measurement runs on r6/run1 (before the change) and r7/run1 (after): summary.json and items.jsonl byte for byte."""
import hashlib, json, sys
from pathlib import Path
R = Path(sys.argv[1])
pairs = [("001", "005", "L1 (token cover)"), ("002", "006", "L2 (type of a word in a sentence)"), ("003", "007", "L3 (typed / unknown words)"), ("004", "008", "verbs 300 (frozen)")]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
print("G5 comparison: r6/run1 (runs 001-004, measured before W5-d changed any code) vs r7/run1 (runs 005-008, after). Same script, same data.")
allsame = True
for a, b, name in pairs:
    for f in ("summary.json", "items.jsonl"):
        if f == "summary.json":      # the provenance fields differ by construction: the builder's sha, the placement path, the time of the run
            def strip(o):
                if isinstance(o, dict):
                    return {k: strip(v) for k, v in o.items() if k not in ("builder_sha256", "placement", "time_utc", "placements", "git_head", "git_dirty")}
                if isinstance(o, list): return [strip(x) for x in o if not (isinstance(x, str) and "/full/r" in x and "/run" in x)]
                return o
            ja, jb = strip(json.loads((R / a / f).read_text())), strip(json.loads((R / b / f).read_text()))
            same = ja == jb
            how = "equal after removing builder_sha256 / placement path / time_utc"
        else:
            same = sha(R / a / f) == sha(R / b / f)
            how = "byte-identical"
        allsame &= same
        print("%-36s %-13s %s/%s vs %s/%s: %s" % (name, f, a, f, b, f, how if same else "DIFFER"))
    s = json.loads((R / b / "summary.json").read_text())
    keys = [k for k in ("n", "correct_rate", "wrong_single_rate", "trap_wrong_single_rate", "typed_n", "unknown_n", "wrong_rate", "returned_type_rate", "token_cover_rate",
                        "n_typed", "n_unknown", "direct_answers", "correct_direct", "wrong_single_direct", "wrong_rate_among_direct", "wrong_rate_typed", "returned_rate_unknown") if k in s]
    print("    r7 numbers:", {k: s[k] for k in keys})
print("ALL IDENTICAL:", allsame)

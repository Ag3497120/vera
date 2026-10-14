"""Replay every stored ledger under tests/fixtures/ledgers: chain, then replay, through the same code `vera verify` runs.  Prints one line per group and exits 1 if anything is not OK.

    python tools/verify_fixtures.py [--allow-other-python]

The ledgers record the Python they were made under (3.11.14) and a replay refuses any other one (`python_mismatch`).  With --allow-other-python that single typed mismatch is
accepted (the chain is still verified byte for byte); without it, any Python but 3.11.14 fails, which is what CI wants.
"""
import collections
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from verantyx.harness import runner as rn                      # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "ledgers")


def runs():
    for hd in sorted(glob.glob(os.path.join(FIX, "loom", "**", "HEAD"), recursive=True)):
        yield os.path.dirname(hd)
    for arm in ("notes", "blind"):
        yield os.path.join(FIX, "mem", "MEM-T06", arm)


def main() -> int:
    lenient = "--allow-other-python" in sys.argv
    groups = collections.defaultdict(collections.Counter)
    bad = []
    for d in runs():
        v = rn.verify_path(d)
        st = v["status"]
        if st == "REPLAY_INPUTS_MISMATCH" and lenient and ((v.get("replay") or {}).get("mismatch") == "python_mismatch"):
            st = "OK(chain; replay needs 3.11.14)"
        rel = os.path.relpath(d, FIX)
        groups[rel.split(os.sep)[0] + "/" + rel.split(os.sep)[1]][st] += 1
        if not st.startswith("OK"):
            bad.append("%s %s" % (rel, st))
    for g, c in sorted(groups.items()):
        print("%-34s %s" % (g, dict(c)))
    print("ledgers: %d, not OK: %d" % (sum(sum(c.values()) for c in groups.values()), len(bad)))
    for b in bad[:20]:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

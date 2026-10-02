"""Q7 (round 7): the words of the traps6 frames (FERRY, NURSERY and their 5 variants) do not appear in the product code
(verantyx/conduct_ask.py) or in the added lines of the r6 -> r7 diff.  Same extraction as artifacts/w2-c/q7_check.py."""
import sys, tempfile, unicodedata
from pathlib import Path
from verantyx.project_frame import load_conduct_frame
sys.path.insert(0, "tests")
import test_conduct_ask_traps6 as T

tmp = Path(tempfile.mkdtemp())
frames = []
for name, text in T.all_frames().items():
    p = tmp / f"{name}.md"; p.write_text(text, encoding="utf-8"); frames.append(p)
terms = set()
for f in frames:
    s = load_conduct_frame(f).spec
    terms |= {s.project} | {p.name for p in s.phases} | {x.subject for x in s.decisions} | {x.choice for x in s.decisions}
    terms |= {a.alias for a in s.aliases} | {a.canonical for a in s.aliases} | {a.action for a in s.protected_actions} | {a.action for a in s.forbidden_actions}
    terms |= {c.text for c in s.criteria} | {i.text for i in s.invariants}
generic = {"in scope", "out of scope", "permitted", "not permitted", "allowed", "human"}
def n(t): return unicodedata.normalize("NFKC", t).strip().casefold()
def big(t):
    t = unicodedata.normalize("NFKC", t).strip()
    cjk = sum(1 for ch in t if ord(ch) > 0x2e80)
    return t.casefold() not in generic and (cjk >= 3 or len(t) >= 6)
code = Path("verantyx/conduct_ask.py").read_text(encoding="utf-8")
diff = Path("artifacts/w2-c/r7/code_diff_r6_to_r7.diff").read_text(encoding="utf-8")
added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
nc, na = n(code), n(added)
hits = sorted(t for t in terms if big(t) and (n(t) in nc or n(t) in na))
print("frames_read", len(frames), "terms_checked", sum(1 for t in terms if big(t)), "hits", len(hits)); [print("HIT", h) for h in hits]

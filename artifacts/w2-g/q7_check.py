"""Q7: no test-data term (project, phase, decision, alias, action, criterion, invariant text) appears in the product code.
Frames read: the 6 + 6 frozen W2-g frames (two data sets) and the 11 frozen W2-c frames.  Checked text: verantyx/conduct_map.py as a whole and
the added lines of ``git diff dev -- verantyx``.  Also checked: the noun phrases of the ticket's example sentences (typed below)
and the English frame words of the trap frames used by the tests.  Not read: tests/bank_score/fixtures/B5 and the hidden bank."""
import subprocess, sys, unicodedata
from pathlib import Path
from verantyx.project_frame import load_conduct_frame

TICKET_QUOTED = ["業務用スマートフォン", "専用スキャナ", "スマートフォン", "スマホ", "カメラで読", "調達しない", "今ある端末"]
TRAP_QUOTED = ["card reader", "ferry", "kiosk", "passenger manifest", "連絡帳", "卒園"]
terms = set()
frames = (sorted(Path("tests/conduct_ask/w2g2/frames").glob("*.md")) + sorted(Path("tests/conduct_ask/w2g/frames").glob("*.md"))
          + sorted(Path("tests/conduct_ask/fixtures/frames").glob("*.md")))
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
code = Path("verantyx/conduct_map.py").read_text(encoding="utf-8")
diff = subprocess.run(["git", "diff", "dev", "--", "verantyx"], capture_output=True, text=True).stdout
code += "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
nc = n(code)
hits = sorted(t for t in terms if big(t) and n(t) in nc)
print("frames_read", len(frames), "terms_checked", sum(1 for t in terms if big(t)), "hits", len(hits)); [print("HIT", h) for h in hits]
qh = sorted(t for t in TICKET_QUOTED + TRAP_QUOTED if n(t) in nc)
print("quoted_checked", len(TICKET_QUOTED + TRAP_QUOTED), "hits", len(qh)); [print("HIT", h) for h in qh]

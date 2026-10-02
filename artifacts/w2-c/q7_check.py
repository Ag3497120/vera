"""Q7: no test-data term (project, phase, decision, alias, action, criterion, invariant text) appears in the product diff.
Frames read: the 11 frozen fixture frames and the two frames written inside tests/test_conduct_ask_traps.py.
Not read: tests/bank_score/fixtures/B5 (not opened by the implementer).  Also checked: noun phrases quoted in the
round-1 review text (typed below), which are subjects of an evaluation frame the implementer has not opened."""
import subprocess, sys, tempfile, unicodedata
from pathlib import Path
from verantyx.project_frame import load_conduct_frame

REVIEW_QUOTED = ["bench simulator", "offline power test", "upload queue", "summary statistics", "storage medium", "radio module",
                 "satellite fallback link", "backoff curve", "clock source", "attempt limit", "runtime dependency",
                 "予約データの型", "保存形式", "日付の表記", "ローカルでの試験運用", "本番データ", "受入確認", "部屋割り", "旧保存形式"]
sys.path.insert(0, "tests")
import test_conduct_ask_traps as T

terms = set()
frames = list(Path("tests/conduct_ask/fixtures/frames").glob("*.md"))
tmp = Path(tempfile.mkdtemp())
for name, text in (("en.md", T.EN_FRAME), ("ja.md", T.JA_FRAME)):
    (tmp / name).write_text(text, encoding="utf-8"); frames.append(tmp / name)
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
code += subprocess.run(["git", "diff", "dev", "--", "verantyx", "tools/real_questions_eval.py"], capture_output=True, text=True).stdout
nc = n(code)
hits = sorted(t for t in terms if big(t) and n(t) in nc)
print("frames_read", len(frames), "terms_checked", sum(1 for t in terms if big(t)), "hits", len(hits)); [print("HIT", h) for h in hits]
qh = sorted(t for t in REVIEW_QUOTED if n(t) in nc)
print("review_quoted_checked", len(REVIEW_QUOTED), "hits", len(qh)); [print("HIT", h) for h in qh]

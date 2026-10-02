"""Q7 supplement for round 4: the frame written inside tests/test_conduct_ask_traps3.py, and the distinctive words of the
round-4 trap questions (the operations, subjects and objects they are about), must not appear in the product code."""
import re, subprocess, sys, tempfile, unicodedata
from pathlib import Path
from verantyx.project_frame import load_conduct_frame
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
import test_conduct_ask_traps3 as T3
tmp = Path(tempfile.mkdtemp()); f = tmp / "n.md"; f.write_text(T3.JA_NOUN_FRAME, encoding="utf-8")
s = load_conduct_frame(f).spec
terms = {s.project} | {p.name for p in s.phases} | {x.subject for x in s.decisions} | {x.choice for x in s.decisions} | {a.alias for a in s.aliases}
terms |= {a.action for a in s.forbidden_actions} | {c.text for c in s.criteria} | {i.text for i in s.invariants}
words = ["dockside", "simulator", "field unit", "stress run", "non-idempotent", "salt spray", "narration", "handset", "player/menu", "content/clips",
         "booking.py", "guide.md", "予約記録", "試験運用", "貸出データ", "削除", "館内", "相談", "外部送信", "持ち出し", "共有サーバー", "記録の項目",
         "保存形式", "SQLite", "用語集", "巻末", "雨天順延", "翌日に延期", "radio band", "binary frames", "568"]
n = lambda t: unicodedata.normalize("NFKC", t).strip().casefold()
code = Path("verantyx/conduct_ask.py").read_text(encoding="utf-8")
code += subprocess.run(["git", "diff", "dev", "--", "verantyx", "tools/real_questions_eval.py"], capture_output=True, text=True).stdout
nc = n(code)
h1 = sorted(t for t in terms if n(t) in nc)
old = n(Path("artifacts/w2-c/r4/conduct_ask_r3.py.txt").read_text(encoding="utf-8"))   # the round-3 code that Q7 accepted
h2 = sorted(w for w in words if n(w) in nc)
h2_new = [w for w in h2 if n(w) not in old]
print("noun_frame_terms", len(terms), "hits", len(h1)); [print("HIT", h) for h in h1]
print("question_words", len(words), "hits_total", len(h2), "hits_new_in_round_4", len(h2_new))
[print("HIT_NEW", h) for h in h2_new]
[print("already_in_round3_code (generic list of protected-looking operations)", h) for h in h2 if h not in h2_new]

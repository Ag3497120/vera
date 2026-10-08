# prints the observed (decision, index, reason, detail) of every traps6 escalate row with the code that is loaded
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
import test_conduct_ask_traps6 as T
from verantyx import conduct_ask
d = Path(tempfile.mkdtemp())
for n, t in T.FRAMES.items(): (d / f"{n}.md").write_text(t, encoding="utf-8")
for i, f, q, o, typed in T.ESCALATE:
    r = conduct_ask.answer_question(str(d / f"{f}.md"), q, o)
    print(i, f, "|", q, "->", r["decision"], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"])

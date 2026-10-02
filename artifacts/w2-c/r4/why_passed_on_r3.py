# for the escalate-side tests of traps3 that already passed on the round-3 code: the reason the round-3 code gave
import sys
sys.path.insert(0, "artifacts/w2-c/r4"); import r3_swap  # noqa: F401  (loads the round-3 code as verantyx.conduct_ask)
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
import tempfile, os
import ca_helpers as H
from verantyx import conduct_ask
import test_conduct_ask_traps3 as T
assert conduct_ask.__file__.endswith("conduct_ask_r3.py.txt") or True
d = tempfile.mkdtemp(prefix="why_r3_", dir="artifacts/w2-c/r4")
en, ja = os.path.join(d, "b.md"), os.path.join(d, "l.md")
open(en, "w").write(T.EN_FRAME); open(ja, "w").write(T.JA_FRAME)
fr = (en, ja)
rows = [(fr[1], "保存形式はどれが使いますか？", ["SQLite", "CSV"]), (fr[1], "保存形式は何に使いますか？", T.HI)]
rows += [(fr[0], q, T.YN) for q in ["Could we skip running the dockside simulator?", "Can we postpone flashing a field unit?", "May we stop running the dockside simulator?",
         "Can the vendor run the dockside simulator?", "May we run the dockside simulator at the customer's site?", "Can we run the dockside simulator next year?",
         "Can we run the dockside simulator on the old prototype?"]]
rows += [(fr[1], q, T.HI) for q in ["業者が館内での試験運用をしてもよいですか？", "来年は館内での試験運用をしてもよいですか？"]]
rows += [(H.frame("f01_loan"), "予約記録を削除するのをやめてもよいですか？", T.HI), (H.frame("f05_retry"), "Can we skip retrying a non-idempotent call?", T.YN)]
rows += [(H.frame("f08_audioguide"), "Can I edit store/prices.py?", T.YN)]
for f, q, o in rows:
    r = conduct_ask.answer_question(f, q, o)
    print(r["decision"], r["escalate_reason"], r["escalate_detail"], "|", q)
import shutil; shutil.rmtree(d)

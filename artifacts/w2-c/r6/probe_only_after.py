import sys, tempfile, os
sys.path.insert(0, "tests")
import test_conduct_ask_traps4 as T4
from verantyx import conduct_ask as c
d = tempfile.mkdtemp(); p = os.path.join(d, "cold.md"); open(p, "w", encoding="utf-8").write(T4.COLD)
r = c.answer_question(p, "May the nightly job purge an expired sensor token now?", ["Yes", "No"])
print(r["decision"], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"])

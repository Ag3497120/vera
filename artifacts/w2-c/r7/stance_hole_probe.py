# S7 probe (known hole): a forbidding record that uses no negation word ("... is forbidden", "We are forbidden to ...") is read as a
# request (POS) by the stance reader.  What does the entry do for the general question?  (traps6 FERRY with C3 replaced)
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "tests")
import test_conduct_ask_traps6 as T
from verantyx import conduct_ask
d = Path(tempfile.mkdtemp())
old = "C3: We will not wipe the card reader | human-judged"
for label, c3 in (("is-forbidden", "C3: Wiping the card reader is forbidden | human-judged"),
                  ("we-are-forbidden", "C3: We are forbidden to wipe the card reader | human-judged")):
    p = d / f"{label}.md"; p.write_text(T.FERRY.replace(old, c3), encoding="utf-8")
    r = conduct_ask.answer_question(str(p), "May we wipe the card reader?", ["Yes", "No"])
    print(label, "|", c3, "->", r["decision"], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"], [b["id"] for b in r["basis"]])

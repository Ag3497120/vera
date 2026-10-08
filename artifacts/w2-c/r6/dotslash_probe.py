# prints the answer of ./app/booking.py question with the code that is loaded (run with -p r4_swap-like swap or the current code)
import sys
sys.path.insert(0, "tests/conduct_ask")
import ca_helpers as H
from verantyx import conduct_ask as c
r = c.answer_question(H.frame("f01_loan"), "./app/booking.py を書き換えてよいですか？", H.YN_JA)
print("decision", r["decision"], "idx", r["answer_option_index"], "answer", r["answer"], "reason", r["escalate_reason"], r["escalate_detail"])

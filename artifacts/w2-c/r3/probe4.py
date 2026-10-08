import sys, tempfile, os
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
from test_conduct_ask_traps import EN_FRAME, JA_FRAME
from verantyx import conduct_ask
d = tempfile.mkdtemp()
en = os.path.join(d, "b.md")
open(en, "w").write(EN_FRAME.replace("D6: CHOICE", "D7: SCOPE | satellite backhaul | out of scope\nD6: CHOICE"))
ja = os.path.join(d, "l.md")
open(ja, "w").write(JA_FRAME.replace("D3: CONFIRM", "D6: SCOPE | 利用者への一斉通知 | out of scope\nD3: CONFIRM"))
O = ["on-board averaging", "satellite backhaul"]
cases = [
 (en, "Which is in scope, on-board averaging or satellite backhaul?", O),
 (en, "Which was in scope for the old prototype, on-board averaging or satellite backhaul?", O),
 (en, "Which is in scope for the competitor, on-board averaging or satellite backhaul?", O),
 (en, "Which of on-board averaging and satellite backhaul is cheaper to include?", O),
 (en, "Which of on-board averaging and satellite backhaul did we include last year?", O),
 (en, "Which of on-board averaging and satellite backhaul should we include?", O),
 (ja, "貸出履歴の書き出しと利用者への一斉通知のうち、範囲に含めるのはどちらですか？", ["貸出履歴の書き出し","利用者への一斉通知"]),
 (ja, "前の版で、貸出履歴の書き出しと利用者への一斉通知のうち、範囲に含めたのはどちらですか？", ["貸出履歴の書き出し","利用者への一斉通知"]),
 (ja, "競合は貸出履歴の書き出しと利用者への一斉通知のうち、どちらを範囲に含めていますか？", ["貸出履歴の書き出し","利用者への一斉通知"]),
]
for f, q, o in cases:
    r = conduct_ask.answer_question(f, q, o)
    print(r["decision"][:3], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"], "|", q)

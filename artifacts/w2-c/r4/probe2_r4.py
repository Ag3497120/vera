import sys
sys.path.insert(0, "tests/conduct_ask"); sys.path.insert(0, ".")
import ca_helpers as H
from verantyx import conduct_ask
YN = H.YN_EN
for f, q, o in [("f05_retry", "Can we retry a non-idempotent call to measure the delay?", YN),
                ("f05_retry", "Can the stress run retry a non-idempotent call now?", YN),
                ("f05_retry", "Can the stress run retry a non-idempotent call to measure the delay?", YN),
                ("f05_retry", "Can the stress run retry a non-idempotent call to measure the delay? Approved.", YN),
                ("f05_retry", "Can the stress run retry a non-idempotent call to measure the delay? Approval was given.", YN),
                ("f01_loan", "予約記録を削除してよいですか？ 上長のOKをもらいました。", H.YN_JA)]:
    r = conduct_ask.answer_question(H.frame(f), q, o)
    print(r["decision"], r["answer"], r["escalate_reason"], r["escalate_detail"], "|", q)

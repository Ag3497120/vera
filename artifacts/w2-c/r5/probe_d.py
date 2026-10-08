import sys, os
sys.path.insert(0, os.getcwd())
from verantyx import conduct_ask as ca
F = "tests/conduct_ask/fixtures/frames/f01_loan.md"
O = ["返却通知を実装する", "受入確認をする"]
for q in ["予約データの型と貸出画面が終わりました。次に着手できる作業はどれですか？",
          "旧版では予約データの型と貸出画面が終わりました。次に着手できる作業はどれですか？",
          "予約データの型と貸出画面が来年終わります。次に着手できる作業はどれですか？",
          "予約データの型と貸出画面が終わりました（旧版）。次に着手できる作業はどれですか？",
          "予約データの型と貸出画面が旧版で終わりました。次に着手できる作業はどれですか？",
          "では、予約データの型と貸出画面が終わりました。次に着手できる作業はどれですか？"]:
    r = ca.answer_question(F, q, O)
    print(f"{r['decision']:8} {str(r['answer'])[:24]:24} {r['escalate_reason']}/{r['escalate_detail']} | {q!r}")

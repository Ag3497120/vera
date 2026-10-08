import sys, os
sys.path.insert(0, os.getcwd())
from verantyx import conduct_ask as ca
D = "artifacts/w2-c/r5/frames/"
cases = [
 ("cold", "The record schema is done in the old prototype. What can we start next?", None),
 ("cold", "The record schema is done for the courier app only. What can we start next?", None),
 ("cold", "The record schema is done. What can we start next?", None),
 ("cold", "The record schema is done. Next year the probe reader will be done. What can we start next?", None),
 ("clinic", "旧版では予約の項目が決まりました。次に着手できる作業はどれですか？", ["受付の画面を作る","確認の電話を自動化する"]),
 ("clinic", "予約の項目が決まりました。次に着手できる作業はどれですか？", ["受付の画面を作る","確認の電話を自動化する"]),
 ("clinic", "予約の項目は来年決まります。次に着手できる作業はどれですか？", ["受付の画面を作る","確認の電話を自動化する"]),
]
for fr, q, o in cases:
    r = ca.answer_question(D + fr + ".md", q, o)
    print(f"{r['decision']:8} {str(r['answer'])[:24]:24} {r['escalate_reason']}/{r['escalate_detail']} | {q!r}")

import sys, tempfile, os
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
from test_conduct_ask_traps import EN_FRAME, JA_FRAME
from verantyx import conduct_ask
d = tempfile.mkdtemp()
en = os.path.join(d, "b.md"); ja = os.path.join(d, "l.md")
open(en, "w").write(EN_FRAME); open(ja, "w").write(JA_FRAME)
YE = ["Yes", "No"]; YJ = ["はい", "いいえ"]
PH = ["the sensor driver", "the packet encoder"]
cases = [
 (en, "Which comes first, the sensor driver or the packet encoder?", PH),
 (en, "Which did the competitor build first, the sensor driver or the packet encoder?", PH),
 (en, "Which was built first last time, the sensor driver or the packet encoder?", PH),
 (en, "Which is easier to do first, the sensor driver or the packet encoder?", PH),
 (en, "Which should we do first, the sensor driver or the packet encoder?", PH),
 (en, "Which phase is first: the sensor driver or the packet encoder?", PH),
 (en, "What must be finished before the uplink scheduler can start?", None),
 (en, "What was finished before the uplink scheduler last time?", None),
 (en, "The sensor driver is done. What can we start next?", None),
 (en, "The sensor driver is done. What did the competitor start next?", None),
 (en, "The sensor driver is done. What is the cheapest thing to start next?", None),
 (ja, "どちらを先に作りますか？貸出の画面と返却の通知", ["貸出の画面", "返却の通知"]),
 (ja, "貸出の画面と返却の通知は、どちらを先に作りますか？", ["貸出の画面", "返却の通知"]),
 (ja, "貸出の画面と返却の通知は、どちらが先に完成しましたか？", ["貸出の画面", "返却の通知"]),
 (ja, "貸出の画面と返却の通知は、どちらが先に作りやすいですか？", ["貸出の画面", "返却の通知"]),
 (ja, "返却の通知を実装する前に、終わっているべき作業はどれですか？", ["貸出の画面", "利用者の登録形式"]),
 (ja, "返却の通知を実装する前に終わっていたのはどれですか？", ["貸出の画面", "利用者の登録形式"]),
]
for f, q, o in cases:
    r = conduct_ask.answer_question(f, q, o)
    print(r["decision"][:3], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"], "|", q)

import sys, tempfile, os
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
from test_conduct_ask_traps import EN_FRAME, JA_FRAME
from verantyx import conduct_ask
d = tempfile.mkdtemp()
en = os.path.join(d, "b.md"); ja = os.path.join(d, "l.md")
open(en, "w").write(EN_FRAME); open(ja, "w").write(JA_FRAME)
YE = ["Yes", "No"]; YJ = ["はい", "いいえ"]
cases = [
 (en, "Which logging format do we use?", ["binary frames", "text lines"]),
 (en, "Do we include on-board averaging?", YE),
 (en, "Is it OK to include on-board averaging?", YE),
 (en, "Should we use the radio band of 868 MHz or 915 MHz?", ["868 MHz","915 MHz"]),
 (en, "Can we also include on-board averaging?", YE),
 (en, "Please include on-board averaging?", YE),
 (en, "Which encoder library should we pick?", ["copying encoder","zero-copy encoder"]),
 (en, "What is the radio band?", None),
 (en, "Which radio band do we use?", None),
 (en, "Is on-board averaging in scope?", YE),
 (en, "Is on-board averaging in scope for this release?", YE),
 (en, "Is on-board averaging included in the scope of this project?", YE),
 (en, "May we run the dockside simulator?", YE),
 (en, "Can we run the dockside simulator?", YE),
 (en, "Can we start the salt spray test before the sensor driver is written?", YE),
 (en, "Can we begin the uplink scheduler before the packet encoder is implemented?", YE),
 (en, "Can we work on the uplink scheduler before the packet encoder is implemented?", YE),
 (en, "Is it OK to proceed with the salt spray test before the sensor driver is written?", YE),
 (en, "Can we run the salt spray test before the sensor driver is written?", YE),
 (en, "May we write the sensor driver before the salt spray test is run?", YE),
 (en, "Should we flash a field unit?", YE),
 (en, "May we flash a field unit?", YE),
 (ja, "保存形式はどれにしますか？", ["SQLite","CSV"]),
 (ja, "保存形式はどれですか？", ["SQLite","CSV"]),
 (ja, "どちらの保存形式を使いますか？", ["SQLite","CSV"]),
 (ja, "館内での試験運用をしてもよいですか？", YJ),
 (ja, "貸出履歴の書き出しは、範囲に含めますか？", ["含める","含めない"]),
 (ja, "貸出の画面を作る前に利用者の登録形式を決めてもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面に着手してもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面を作り始めてもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面を作ってもよいですか？", YJ),
 (ja, "今回のリリースの保存形式はどれにしますか？", ["SQLite","CSV"]),
 (ja, "このリリースの保存形式はどれにしますか？", ["SQLite","CSV"]),
 (ja, "館内での試験運用をするべきですか？", YJ),
 (ja, "館内での試験運用をしてもよかったですか？", YJ),
]
for f, q, o in cases:
    r = conduct_ask.answer_question(f, q, o)
    print(r["decision"][:3], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"], "|", q)

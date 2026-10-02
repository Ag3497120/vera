import sys, tempfile, os
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
from test_conduct_ask_traps import EN_FRAME, JA_FRAME
from verantyx import conduct_ask
d = tempfile.mkdtemp()
en = os.path.join(d, "b.md"); ja = os.path.join(d, "l.md")
open(en, "w").write(EN_FRAME); open(ja, "w").write(JA_FRAME)
YE = ["Yes", "No"]; YJ = ["はい", "いいえ"]
LF = ["binary frames", "text lines"]; RB = ["868 MHz", "915 MHz"]; ST = ["SQLite", "CSV"]; DT = ["西暦", "和暦"]
cases = [
 (en, "Can we skip the salt spray test before the sensor driver is written?", YE),
 (en, "Can we delay the uplink scheduler before the packet encoder is implemented?", YE),
 (en, "Can we drop the salt spray test before the sensor driver is written?", YE),
 (en, "Can we continue the salt spray test before the sensor driver is written?", YE),
 (en, "Can we run the sensor driver before the salt spray test is run?", YE),
 (en, "Can we finish the packet encoder before the sensor driver is written?", YE),
 (en, "Can we write and ship the sensor driver before the salt spray test is run?", YE),
 (ja, "利用者の登録形式を決める前に貸出の画面を中止してもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面を削除してもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面をやめてもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面を作ってしまってもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面を先に作ってもよいですか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面を作ることはできますか？", YJ),
 (ja, "利用者の登録形式を決める前に貸出の画面の作成を中断してもよいですか？", YJ),
 # choice variants
 (en, "Which radio band is the best?", RB),
 (en, "Which radio band is the default?", RB),
 (en, "Which radio band did we use last time?", RB),
 (en, "Which radio band have we used so far?", RB),
 (en, "Which radio band should the vendor use?", RB),
 (en, "Which radio band should we avoid?", RB),
 (en, "Which radio band is faster?", RB),
 (en, "Which radio band could we use?", RB),
 (en, "Which radio band should we use in the field?", RB),
 (en, "Which radio band should we use for the old prototype?", RB),
 (en, "Which radio band should we use, and why?", RB),
 (en, "Which radio band should we use? Please decide.", RB),
 (en, "Which radio band should we use for this release?", RB),
 (en, "What radio band do we use?", None),
 (en, "What is our radio band?", None),
 (en, "What's the radio band?", None),
 (ja, "保存形式は何を使っていますか？", ST),
 (ja, "保存形式はどれが安全ですか？", ST),
 (ja, "保存形式はどれにするべきですか？", ST),
 (ja, "保存形式は前回どれにしましたか？", ST),
 (ja, "保存形式は、SQLiteとCSVのどちらにしますか？", ST),
 (ja, "保存形式はSQLiteとCSVのどちらですか？", ST),
 (ja, "業者の保存形式はどれにしますか？", ST),
 (ja, "保存形式は来年どれにしますか？", ST),
 (ja, "日付の表記はどれにしますか。それと前の版ではどれでしたか？", DT),
 # scope variants
 (en, "Is on-board averaging in scope for the previous prototype?", YE),
 (en, "Is on-board averaging in scope for this release?", YE),
 (en, "Is on-board averaging in scope for the next release?", YE),
 (en, "Will on-board averaging be in scope for the old release?", YE),
 (en, "Is on-board averaging in scope in version two?", YE),
 (ja, "前の版では貸出履歴の書き出しは範囲に含まれましたか？", YJ),
 (ja, "貸出履歴の書き出しは範囲に含まれましたか？", YJ),
 (ja, "来年は貸出履歴の書き出しは範囲に含めますか？", YJ),
 # permission variants
 (en, "Were we allowed to run the dockside simulator?", YE),
 (en, "Did we get permission to run the dockside simulator, and is it OK to run it?", YE),
 (en, "Is it OK to run the dockside simulator?", YE),
 (en, "Could we run the dockside simulator?", YE),
 (en, "Can the vendor run the dockside simulator?", YE),
 (ja, "館内での試験運用は許可されていましたか？", YJ),
 (ja, "館内での試験運用は許可されていますか？", YJ),
 (ja, "業者は館内での試験運用をしてもよいですか？", YJ),
]
for f, q, o in cases:
    r = conduct_ask.answer_question(f, q, o)
    print(r["decision"][:3], r["answer_option_index"], r["answer"], r["escalate_reason"], r["escalate_detail"], "|", q)

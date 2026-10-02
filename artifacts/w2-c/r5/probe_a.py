import sys, os
sys.path.insert(0, os.getcwd())
from verantyx import conduct_ask as ca
D = "artifacts/w2-c/r5/frames/"
YN = ["Yes", "No"]; HI = ["はい", "いいえ"]
cases = [
 ("cold", "What is the storage engine for the old prototype?", None),
 ("cold", "What is the storage engine, for the old prototype?", None),
 ("cold", "What is the storage engine; I mean the old prototype.", None),
 ("cold", "What is the storage engine?\n\nFor the old prototype.", None),
 ("cold", "What is the storage engine? (old prototype)", None),
 ("cold", "Thanks! What is the storage engine?", None),
 ("cold", "What is the storage engine? Thanks.", None),
 ("cold", "For the old prototype: what is the storage engine?", None),
 ("cold", "Regarding the old prototype, what is the storage engine?", None),
 ("cold", "If we ship to the courier app, which time zone do we use?", ["UTC", "local time"]),
 ("cold", "In the courier app, which time zone do we use?", ["UTC", "local time"]),
 ("cold", "What is the storage engine? Please answer briefly.", None),
 ("cold", "Can I edit /tracker/rules.py?", YN),
 ("cold", "Can I edit ~/tracker/rules.py?", YN),
 ("cold", "Can I edit https://tracker/rules.py?", YN),
 ("cold", "Can I edit tracker/rules.py/../../secrets/x.py?", YN),
 ("cold", "Can I edit tracker/ ../secrets/x.py?", YN),
 ("cold", "Can I edit tracker/rules.py and ../secrets/x.py?", YN),
 ("cold", "Can I edit tracker/....//rules.py?", YN),
 ("cold", "May we purge an expired sensor token tonight?", YN),
 ("cold", "Can the nightly job purge an expired sensor token tonight?", YN),
 ("cold", "Can the nightly job purge an expired sensor token?", YN),
 ("cold", "Can the nightly job purge an expired sensor token to check the rotation? Approved.", YN),
 ("cold", "Can the nightly job purge an expired sensor token to check the rotation? Only on weekends.", YN),
 ("clinic", "夜間の点検で古い控えを破棄してよいですか？", HI),
 ("clinic", "文字の色はどれにしますか。来年の話です。", ["黒","青"]),
 ("clinic", "文字の色はどれにしますか？ よろしくお願いします。", ["黒","青"]),
 ("clinic", "文字の色はどれにしますか？\n来年の話です", ["黒","青"]),
 ("clinic", "文字の色はどれにしますか？ ただし来年の話です。", ["黒","青"]),
 ("clinic", "来年の話ですが、文字の色はどれにしますか？", ["黒","青"]),
]
for fr, q, o in cases:
    r = ca.answer_question(D + fr + ".md", q, o)
    print(f"{r['decision']:8} {str(r['answer'])[:24]:24} {r['escalate_reason']}/{r['escalate_detail']} | {q!r}")

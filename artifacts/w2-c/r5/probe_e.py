import sys, os
sys.path.insert(0, os.getcwd())
from verantyx import conduct_ask as ca
D = "artifacts/w2-c/r5/frames/"
YN = ["Yes", "No"]; HI = ["はい", "いいえ"]
cases = [
 ("cold", "Tell me the storage engine. For the old prototype.", None),
 ("cold", "Tell me the storage engine.", None),
 ("cold", "I need the storage engine. Is it PostgreSQL?", ["Yes","No"]),
 ("cold", "Could you tell me the alert channel? Also for the dashboard.", None),
 ("clinic", "予約の単位を教えてください。旧版の話です。", None),
 ("cold", "Can I calibrate a probe on site? It is for a customer.", YN),
 ("cold", "Can I calibrate a probe on site? Approved by the lead.", YN),
 ("cold", "Can the nightly job purge an expired sensor token to check the rotation? Approved.", YN),
 ("cold", "Is humidity tracking in scope? The lead approved it. Only for next year.", YN),
 ("cold", "Approved. Is humidity tracking in scope?", YN),
 ("cold", "Which comes first, the record schema or the probe reader? Asking for the old prototype.", ["the record schema","the probe reader"]),
 ("cold", "Which comes first, the record schema or the probe reader?", ["the record schema","the probe reader"]),
]
for fr, q, o in cases:
    r = ca.answer_question(D + fr + ".md", q, o)
    print(f"{r['decision']:8} {str(r['answer'])[:24]:24} {r['escalate_reason']}/{r['escalate_detail']} | {q!r}")

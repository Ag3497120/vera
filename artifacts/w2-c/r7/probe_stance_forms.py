# direct probes of the new readers: (1) _record_stance on the records the plan lists as "direction must not change",
# (2) a few closed-form edge cases, (3) the path rule with an allowlist that has an upper-case entry ("W1: App") -> must not answer more
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "tests")
import test_conduct_ask_traps6 as T
from verantyx import conduct_ask as ca
rows = [
 ("retry a non-idempotent call", "The stress run will retry a non-idempotent call"),
 ("retry a non-idempotent call", "The stress run will retry a non-idempotent call to measure the delay"),
 ("drain the reservoir", "We will drain the reservoir after the yearly inspection"),
 ("purge an expired sensor token", "The nightly job will purge an expired sensor token to check the rotation"),
 ("erase the narration masters", "The field test frees disk space by erasing the narration masters"),
 ("send the phone number to the parts supplier", "The bot may send the phone number to the parts supplier to speed up orders"),
 ("古い控えを破棄する", "夜間の点検で古い控えを破棄して容量を確かめる"),
 ("publish the grower contact list", "We never publish the grower contact list"),
 ("share the alert log with a courier", "We never share the alert log with a courier"),
 ("病歴を外部に送る", "病歴を外部に送ることはしない"),
 ("献立の原価を外部に公開する", "献立の原価を外部に公開しない"),
 ("外部の査読者に送る", "未公開の草稿を外部の査読者に送ることはしない"),   # the protected operation of the frozen f03 frame
 # edge cases
 ("wipe the card reader", "We will not wipe the card reader"),
 ("wipe the card reader", "We will not wipe the card reader today"),
 ("wipe the card reader", "We cannot wipe the card reader"),
 ("wipe the card reader", "We do not wipe the card reader"),
 ("wipe the card reader", "We never wipe the card reader unless asked"),
 ("wipe the card reader", "No one wipes the card reader"),
 ("wipe the card reader", "We will not ever wipe the card reader"),
 ("wipe the card reader", "Wiping the card reader is forbidden"),
 ("wipe the card reader", "The kiosk never wipes the card reader"),
 ("wipe the card reader", "We wipe the card reader"),
 ("wipe the card reader", "We wipe the card reader when no sale is open"),
 ("wipe the card reader", "We never wipe the card reader nor the printer"),
 ("export the manifest", "We never export the manifest"),
 ("export the manifest", "We never export the manifest before the ferry departs"),
 ("export the manifest", "The kiosk never exports the manifest"),
 ("園児の写真を外部へ送る", "卒園前は園児の写真を外部へ送らない"),
 ("園児の写真を外部へ送る", "私たちは園児の写真を外部へ送らない"),
 ("園児の写真を外部へ送る", "園児の写真を外部へ送らない"),
 ("園児の写真を外部へ送る", "園児の写真を外部へ送ることはない"),
 ("園児の写真を外部へ送る", "園児の写真を外部へ送るのは禁止"),
 ("園児の写真を外部へ送る", "園児の写真を外部へ送らないが、本人が希望すれば送る"),
 ("連絡帳の記録を消去する", "園児がいない夜間に連絡帳の記録を消去して容量を空ける"),
]
for a, t in rows:
    print(f"{a!r:48} | {t!r:80} -> {ca._record_stance(a, t)}")
# (3) uppercase allowlist entry
d = Path(tempfile.mkdtemp())
for label, w1, qs in (("W1: App", "W1: App", ["Can I edit App/x.py?", "Can I edit app/x.py?", "Can I edit APP/x.py?", "Can I edit App/Sub/Y.py?"]),
                      ("W1: kiosk", "W1: kiosk", ["Can I edit kiosk/Sub/Y.py?", "Can I edit kiosk/x.py?", "Can I edit Kiosk/x.py?", "Can I edit KIOSK/x.py?"])):
    p = d / (label.replace(": ", "_") + ".md")
    p.write_text(T.FERRY.replace("W1: kiosk", w1), encoding="utf-8")
    for q in qs:
        r = ca.answer_question(str(p), q, ["Yes", "No"])
        print(label, "|", q, "->", r["decision"], r["answer_option_index"], r["escalate_reason"], r["escalate_detail"])

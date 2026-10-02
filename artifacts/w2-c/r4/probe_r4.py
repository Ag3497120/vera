# own probe of the round-4 gate (not a test): prints what the permission / choice forms answer for variants
import sys, json
sys.path.insert(0, "tests"); sys.path.insert(0, "tests/conduct_ask")
import tempfile, os
import ca_helpers as H
from verantyx import conduct_ask
from test_conduct_ask_traps import EN_FRAME, JA_FRAME
d = tempfile.mkdtemp(prefix="probe_r4_", dir=os.path.join(os.getcwd(), "artifacts/w2-c/r4"))
en, ja = os.path.join(d, "buoy.md"), os.path.join(d, "library.md")
open(en, "w").write(EN_FRAME); open(ja, "w").write(JA_FRAME)
YN, HI = H.YN_EN, H.YN_JA
cases = [
 (en, "Can we start running the dockside simulator?", YN), (en, "Can we continue running the dockside simulator?", YN),
 (en, "Can we keep flashing a field unit?", YN), (en, "Is flashing a field unit permitted?", YN),
 (en, "Are we allowed to flash a field unit?", YN), (en, "Is it ok for us to run the dockside simulator?", YN),
 (en, "Is it OK to disable flashing a field unit?", YN), (en, "Can we run the dockside simulator tomorrow?", YN),
 (en, "Can we run the dockside simulator without approval?", YN), (en, "Can we, as a test, run the dockside simulator?", YN),
 (en, "May we please run the dockside simulator?", YN), (en, "Can we run the dockside simulator for this release?", YN),
 (en, "Can we run the dockside simulator? Only the vendor will do it.", YN),
 (en, "Can we overwrite the raw readings?", YN), (en, "Can we overwrite raw readings now?", YN), (en, "Can we stop overwriting raw readings?", YN),
 (en, "Can we publish a firmware image?", YN),
 (ja, "館内での試験運用をしてもよろしいですか？", HI), (ja, "館内での試験運用を実施してもよいですか？", HI),
 (ja, "館内での試験運用を職員だけでしてもよいですか？", HI), (ja, "館内での試験運用を今日してもよいですか？", HI),
 (ja, "館内での試験運用を再開してもよいですか？", HI), (ja, "館内での試験運用を取りやめることはできますか？", HI),
 (ja, "館内での試験運用をすることはできますか？", HI), (ja, "館内での試験運用を続けてもよいですか？", HI),
 (ja, "館内での試験運用を学生にしてもらってもよいですか？", HI), (ja, "学生が館内での試験運用をしてもよいですか？", HI),
 (ja, "本番の貸出データを使った試験をすることはできますか？", HI), (ja, "本番の貸出データを使った試験は許可されていますか？", HI),
 (ja, "保存形式はどちらにしますか？", ["SQLite", "CSV"]), (ja, "保存形式は何を選びますか？", None), (ja, "保存形式は何がよいですか？", None),
 (ja, "保存形式はどうですか？", None), (ja, "保存形式は何ですか？", None), (ja, "保存形式をどうしますか？", None),
 (ja, "どの保存形式にしますか？", None), (ja, "どの保存形式がよいですか？", None),
]
for f, q, o in cases:
    r = conduct_ask.answer_question(f, q, o)
    print(("ANS " + str(r["answer_option_index"]) + " " + str(r["answer"])) if r["decision"] == "answer" else "ESC " + str(r["escalate_reason"]) + "/" + str(r["escalate_detail"]), "|", q, o)
import shutil; shutil.rmtree(d)

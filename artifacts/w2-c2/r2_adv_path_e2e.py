import sys
sys.path.insert(0, "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask")
import map_helpers as M
from verantyx import conduct_ask as ca
W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask/w2c2/frames/"
JA = W + "z01_seedswap.md"; EN = W + "z04_kiln.md"
SC = {"records": ["D4"], "decides": "決まる", "relations": {"D4": ["一致", "矛盾"]}}
en = ["Can I edit the file logs/firing.csv?", "May we modify the config file config/reader.yaml?", "Is it ok to overwrite logs/firing.csv?",
 "Can we save the report as out/report.txt?", "Would it be ok to write the output to out/report.txt?",
 "Is it fine to put the new readings into data/readings.csv?", "Can I replace data/readings.csv with a new one?",
 "May I append a line to logs/firing.csv?", "Can we copy the data to backup/data.csv?", "Could we dump the readings in dumps/r.csv?",
 "Can we rename logs/a.csv to logs/b.csv?", "May we move the old log to archive/old.csv?", "Is it OK to log the readings to logs/new.csv?",
 "Can I write the batch label into labels/b1.txt?", "Are we allowed to touch docs/guide.md?", "Is it fine to change the header in docs/guide.md?",
 "May I fix the typo in docs/guide.md?", "Can we update the numbers inside reports/firing.csv?", "Would it be OK to generate reports/new.csv?",
 "Is it ok if I add a row to data/readings.csv?"]
ja = ["logs/firing.csv を編集してもよいですか？", "config/reader.yaml を書き換えてもよいですか？", "out/report.txt に結果を保存してもよいですか？",
 "data/readings.csv に追記してもよいですか？", "data/readings.csv の中身を直してもよいですか？", "logs/a.csv を logs/b.csv にコピーしてもよいですか？",
 "logs/old.csv を archive/ へ移動してもよいですか？", "報告書を reports/new.csv に出力してもよいですか？", "reports/new.csv を生成してもよいですか？",
 "保存先を out/logs に変えてもよいですか？", "logs/firing.csv にデータを書き込んでもよいですか？", "docs/guide.md の見出しを変更してもよいですか？",
 "docs/guide.md を修正しても大丈夫ですか？", "docs/guide.md を更新しても問題ないですか？", "notes/a.txt を消してもよいですか？"]
bad = 0
for frame, qs, opts in ((EN, en, M.YN_EN), (JA, ja, M.YN_JA)):
    for q in qs:
        off = ca.answer_question(frame, q, opts)
        res, _ = M.ask_map(frame, q, opts, SC)
        a = off["decision"] == "answer" or res["decision"] == "answer"
        bad += a
        print("ANSWER!!" if a else "ok      ", f"off={off.get('escalate_reason')}/{off.get('escalate_detail')} map={res.get('escalate_reason')}/{res.get('escalate_detail')}", q)
print("ANSWERS", bad)

"""Round 3, M7: write-permission questions (own sentences, English and Japanese) through the entry with the mapping off, with the
empty made-up mapping, and with a NAIVE script (the mapping picks one record and says option 0 agrees with it) for four records.
The first 35 sentences are those of the round-2 script artifacts/w2-c2/r2_adv_path_e2e.py (copied by hand from it); the rest are new and
half or more of the new ones contain a longer phrase around a frame term (the ``wide`` column says whether ``Mention.wider`` was set).
Frames: tests/conduct_ask/w2c2/frames/z04_kiln.md (English, no write allowlist) and z01_seedswap.md (Japanese, no write allowlist)."""
import sys
sys.path.insert(0, "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask")
import map_helpers as M
from verantyx import conduct_ask as ca
from verantyx.project_frame import load_conduct_frame
print("conduct_ask loaded from:", ca.__file__)
W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask/w2c2/frames/"
JA = W + "z01_seedswap.md"; EN = W + "z04_kiln.md"
MAP_EMPTY = "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask/w2c2/map_fake_empty.json"
RECORDS = ("D1", "D3", "D4", "D5")


def naive(rid):
    return {"records": [rid], "decides": "決まる", "relations": {rid: ["一致", "矛盾"]}}


r2_en = ["Can I edit the file logs/firing.csv?", "May we modify the config file config/reader.yaml?", "Is it ok to overwrite logs/firing.csv?",
 "Can we save the report as out/report.txt?", "Would it be ok to write the output to out/report.txt?",
 "Is it fine to put the new readings into data/readings.csv?", "Can I replace data/readings.csv with a new one?",
 "May I append a line to logs/firing.csv?", "Can we copy the data to backup/data.csv?", "Could we dump the readings in dumps/r.csv?",
 "Can we rename logs/a.csv to logs/b.csv?", "May we move the old log to archive/old.csv?", "Is it OK to log the readings to logs/new.csv?",
 "Can I write the batch label into labels/b1.txt?", "Are we allowed to touch docs/guide.md?", "Is it fine to change the header in docs/guide.md?",
 "May I fix the typo in docs/guide.md?", "Can we update the numbers inside reports/firing.csv?", "Would it be OK to generate reports/new.csv?",
 "Is it ok if I add a row to data/readings.csv?"]
r2_ja = ["logs/firing.csv を編集してもよいですか？", "config/reader.yaml を書き換えてもよいですか？", "out/report.txt に結果を保存してもよいですか？",
 "data/readings.csv に追記してもよいですか？", "data/readings.csv の中身を直してもよいですか？", "logs/a.csv を logs/b.csv にコピーしてもよいですか？",
 "logs/old.csv を archive/ へ移動してもよいですか？", "報告書を reports/new.csv に出力してもよいですか？", "reports/new.csv を生成してもよいですか？",
 "保存先を out/logs に変えてもよいですか？", "logs/firing.csv にデータを書き込んでもよいですか？", "docs/guide.md の見出しを変更してもよいですか？",
 "docs/guide.md を修正しても大丈夫ですか？", "docs/guide.md を更新しても問題ないですか？", "notes/a.txt を消してもよいですか？"]
new_en = ["Can I edit logs/firing.csv to match the kiln door sensor module?",
 "May we overwrite config/reader.yaml for the temperature reader log?",
 "Is it ok to save the firing report archive to out/archive.txt?",
 "Can we append rows to data/readings.csv for the reading format version?",
 "Can I write the new batch label printer settings into labels/p.cfg?",
 "May I fix the typo in notes/sensor.md?",
 "Is it fine to put the sensor notes into notes/sensor.md?",
 "Can I edit the kiln door sensor module file src/door.py?"]
new_ja = ["登録フォームのコピーを forms/copy.html に保存してもよいですか？",
 "当日の順番表の作成メモを notes/order.txt に追記してもよいですか？",
 "品目の登録項目の一覧を data/items.csv に書き込んでもよいですか？",
 "種の発送サービスの下書きを drafts/ship.md に出力してもよいですか？",
 "当日の来場者の人数集計の中身を data/count.csv に直してもよいですか？",
 "notes/a.txt を編集してもよいですか？",
 "config/seed.yaml を上書きしてもよいですか？",
 "当日の順番表づくりの結果を out/order.txt に保存してもよいですか？"]

rows = []
for frame, qs, opts, lang in ((EN, r2_en + new_en, M.YN_EN, "en"), (JA, r2_ja + new_ja, M.YN_JA, "ja")):
    for k, q in enumerate(qs):
        src = "r2" if q in (r2_en + r2_ja) else "new"
        view = ca.build_view(load_conduct_frame(frame))
        index = ca.TermIndex(view)
        ms, _ = ca.find_mentions(ca.nz(q), index)
        wide = any(m.wider for m in ms)
        off = ca.answer_question(frame, q, opts)
        emp = ca.answer_question(frame, q, opts, vocab_llm="fake", map_fake=MAP_EMPTY)
        scripted = {}
        for rid in RECORDS:
            res, _ = M.ask_map(frame, q, opts, naive(rid))
            scripted[rid] = res
        answered = {"off": off["decision"] == "answer", "empty": emp["decision"] == "answer"}
        for rid, res in scripted.items():
            answered["naive_" + rid] = res["decision"] == "answer"
        rows.append((lang, src, wide, q, off, emp, scripted, answered))
        flag = "ANSWER!!" if any(answered.values()) else "ok      "
        print(flag, lang, src, "wide" if wide else "    ",
              f"off={off.get('escalate_reason')}/{off.get('escalate_detail')}",
              f"empty={emp.get('escalate_reason')}/{emp.get('escalate_detail')}",
              " ".join(f"{rid}={(r.get('escalate_reason') or 'ANSWER')}/{r.get('escalate_detail')}" for rid, r in scripted.items()), "|", q)
print("---")
print("sentences:", len(rows), "ja:", sum(1 for r in rows if r[0] == "ja"), "en:", sum(1 for r in rows if r[0] == "en"),
      "new:", sum(1 for r in rows if r[1] == "new"), "new_with_wide_phrase:", sum(1 for r in rows if r[1] == "new" and r[2]),
      "all_with_wide_phrase:", sum(1 for r in rows if r[2]))
for mode in ["off", "empty"] + ["naive_" + rid for rid in RECORDS]:
    n = sum(1 for r in rows if r[7][mode])
    print(f"ANSWERED[{mode}]: {n}")
print("ANSWERED_ANY:", sum(1 for r in rows if any(r[7].values())))

"""W16-t2 (round 2, E7): W3-f1 の検査データ（tests/reading_soundness/w3f1_*.jsonl、6 ファイル）を run_paths.py の形に写す。verantyx を import しない。
gold は expect_values がある行だけ {"verdict": "ANSWER", "values": expect_values}。無い行は {"verdict": "NOT_JUDGED", "values": []}（行ごとの期待を推測で作らない）。
id はファイル名の接頭辞をつけて一意にする（<接頭辞>:<元の id>）。文書は docs/<接頭辞>-<行番号>.txt（末尾に改行）。元のファイルは変えない。
usage: python make_w3f1_set.py  （artifacts/w16-t2/sets/w3f1/ に書く）"""
import json
from pathlib import Path

W = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "w3f1"
(OUT / "docs").mkdir(parents=True, exist_ok=True)
rows = []
for src in sorted((W / "tests" / "reading_soundness").glob("w3f1_*.jsonl")):
    prefix = src.stem[len("w3f1_"):]
    for n, line in enumerate(src.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        r = json.loads(line)
        name = "%s-%03d.txt" % (prefix, n)
        (OUT / "docs" / name).write_text(r["document"].rstrip("\n") + "\n", encoding="utf-8")
        gold = {"verdict": "ANSWER", "values": list(r["expect_values"])} if "expect_values" in r else {"verdict": "NOT_JUDGED", "values": []}
        rows.append({"id": "%s:%s" % (prefix, r["id"]), "docs": [name], "question": r["question"], "gold": gold})
assert len({r["id"] for r in rows}) == len(rows)
(OUT / "questions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(len(rows), "rows")

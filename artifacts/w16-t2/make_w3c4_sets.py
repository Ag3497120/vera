"""W3-c4 の凍結済み検査データ（tests/observe/question_ask/questions.jsonl・b2like/questions.jsonl）を run_paths.py の形に写す。
truth.kind ONE（fillers 1 つ）→ gold ANSWER、NONE・SPLIT → gold ABSTAIN、YESNO・ILLFORMED → gold NOT_JUDGED（W3-c4 の採点でも「後段が答えないこと」だけを見た型。本読みが答える行は判定に入れない）。元のファイルは変えない。"""
import json
from pathlib import Path
W = Path(__file__).resolve().parents[2]
for name, src in (("w3c4", W / "tests/observe/question_ask/questions.jsonl"), ("w3c4_b2like", W / "tests/observe/question_ask/b2like/questions.jsonl")):
    out = Path(__file__).resolve().parent / "sets" / name
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "questions.jsonl", "w", encoding="utf-8") as f:
        for l in src.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            q = json.loads(l)
            t = q["truth"]
            gold = {"verdict": "ANSWER", "values": list(t["fillers"])} if t["kind"] == "ONE" else {"verdict": "NOT_JUDGED" if t["kind"] in ("YESNO", "ILLFORMED") else "ABSTAIN", "values": [], "truth_kind": t["kind"]}
            f.write(json.dumps({"id": q["id"], "docs": q["docs"], "question": q["text"], "gold": gold, "category": q.get("category")}, ensure_ascii=False) + "\n")

"""R5: for every ANSWERABLE question, whether the layer gained it, and when it did not, WHY, as a type (machine-made):
  GAINED                      correct with the layer, not correct without;
  ALREADY_CORRECT             correct without the layer (nothing to gain);
  LAYER_WORD_NOT_IN_QUESTION  no word of the layer appears in the question or in the document sentence(s) that hold the answer;
  LAYER_NO_DIRECT             layer words appear there, but none of them has a direct row (an estimate is never read);
  READER_NOT_REACHED          a direct layer word appears, the answer is still not correct: the reader's own reason (verdict / reason / question_cross.reason) is copied.
`words in the sentences` = the document sentences that contain an expected value and share at least 3 consecutive characters with the question.
usage: why_not_gained.py <questions.jsonl> <document> <layer sqlite> <run none.jsonl> <run layer.jsonl>"""
import json
import sys

qs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
doc = [l.strip() for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
from verantyx import placement_layer as PL  # noqa: E402
lay = PL.open_layer(sys.argv[3])[0]
by_word = {}
for e in lay.all_entries():
    by_word.setdefault(e["word"], set()).add(e["origin"])
direct_words = {w for w, o in by_word.items() if o & set(PL.DIRECT_ORIGINS)}
none_run = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[4], encoding="utf-8")}
lay_run = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[5], encoding="utf-8")}


def correct(r, q):
    o = r["out"]
    return o.get("verdict") == "ANSWER" and sorted(o.get("values") or []) == sorted(q["expect"]["values"])


def shares3(a, b):
    return any(a[i:i + 3] in b for i in range(len(a) - 2))


rows, counts = [], {}
for q in qs:
    if q["expect"] == "ABSTAIN":
        continue
    n, l = none_run[q["id"]], lay_run[q["id"]]
    holders = [s for s in doc if any(v in s for v in q["expect"]["values"]) and shares3(q["question"], s)]
    text = q["question"] + "".join(holders)
    present = sorted(w for w in by_word if w in text)
    present_direct = [w for w in present if w in direct_words]
    if correct(l, q) and not correct(n, q):
        why = "GAINED"
    elif correct(n, q):
        why = "ALREADY_CORRECT"
    elif not present:
        why = "LAYER_WORD_NOT_IN_QUESTION"
    elif not present_direct:
        why = "LAYER_NO_DIRECT"
    else:
        why = "READER_NOT_REACHED"
    o = l["out"]
    qc = o.get("question_cross") or {}
    rows.append({"id": q["id"], "question": q["question"], "why": why, "layer_words_in_text": present, "direct_layer_words_in_text": present_direct, "holder_sentences": holders,
                 "without_layer": {"verdict": n["out"].get("verdict"), "values": n["out"].get("values"), "reason": n["out"].get("reason"), "qc": (n["out"].get("question_cross") or {}).get("reason")},
                 "with_layer": {"verdict": o.get("verdict"), "values": o.get("values"), "reason": o.get("reason"), "qc": qc.get("reason")},
                 "answers_identical": json.dumps(n["out"], ensure_ascii=False, sort_keys=True) == json.dumps(o, ensure_ascii=False, sort_keys=True)})
    counts[why] = counts.get(why, 0) + 1
print(json.dumps({"counts": counts, "answerable": len(rows)}, ensure_ascii=False))
for r in rows:
    print(json.dumps(r, ensure_ascii=False))

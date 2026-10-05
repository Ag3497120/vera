"""R5: for every ANSWERABLE question, whether the layer gained it, and when it did not, WHY, as a type (machine-made):
  GAINED                      correct with the layer, not correct without;
  ALREADY_CORRECT             correct without the layer (nothing to gain);
  LAYER_WORD_NOT_IN_QUESTION  no word of the layer appears in the question or in the document sentence(s) that hold the answer;
  LAYER_NO_DIRECT             layer words appear there, but none of them has a direct row (an estimate is never read);
  READER_NOT_REACHED          a direct layer word appears, the answer is still not correct: the reader's own reason (verdict / reason / question_cross.reason) is copied.
A WRONG ANSWER IS NEVER FILED UNDER ONE OF THE ABOVE (review r1 M4). It is checked FIRST, with the judgement of score_qa.py (verdict == ANSWER and the values differ from the expected ones),
and has its own types: WRONG_WITHOUT_LAYER, WRONG_WITH_LAYER, WRONG_BOTH. The UNANSWERABLE questions (expect == ABSTAIN) are also checked for an ANSWER (the same three types, counted under `counts`
and `wrong_unanswerable`); every other unanswerable question is not listed. The summary line carries `wrong` = the number of rows of the three types.
`words in the sentences` = the document sentences that contain an expected value and share at least 3 consecutive characters with the question.
usage: why_not_gained.py <questions.jsonl> <document> <layer sqlite> <run none.jsonl> <run layer.jsonl>
(W12-c1: copied from artifacts/w10-f05/scripts; the only change is that the counts also carry `routed` = the answerable questions with at least one direct layer word in the question or the holder sentences, the
ROUTED test of docs/INITIAL_LAYERS.md K410, and each row carries `routed`.)"""
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


def wrong(r, q):
    """the judgement of score_qa.py: an ANSWER that is not the expected one (an ANSWER to an unanswerable question included)"""
    o = r["out"]
    if o.get("verdict") != "ANSWER":
        return False
    if q["expect"] == "ABSTAIN":
        return True
    return sorted(o.get("values") or []) != sorted(q["expect"]["values"])


def shares3(a, b):
    return any(a[i:i + 3] in b for i in range(len(a) - 2))


rows, counts = [], {}
for q in qs:
    n, l = none_run[q["id"]], lay_run[q["id"]]
    if q["expect"] == "ABSTAIN":
        wn, wl = wrong(n, q), wrong(l, q)
        if not (wn or wl):
            continue
        why = "WRONG_BOTH" if wn and wl else "WRONG_WITHOUT_LAYER" if wn else "WRONG_WITH_LAYER"
        rows.append({"id": q["id"], "question": q["question"], "why": why, "unanswerable": True, "routed": False, "layer_words_in_text": [], "direct_layer_words_in_text": [], "holder_sentences": [],
                     "without_layer": {"verdict": n["out"].get("verdict"), "values": n["out"].get("values")}, "with_layer": {"verdict": l["out"].get("verdict"), "values": l["out"].get("values")},
                     "answers_identical": json.dumps(n["out"], ensure_ascii=False, sort_keys=True) == json.dumps(l["out"], ensure_ascii=False, sort_keys=True)})
        counts[why] = counts.get(why, 0) + 1
        continue
    holders = [s for s in doc if any(v in s for v in q["expect"]["values"]) and shares3(q["question"], s)]
    text = q["question"] + "".join(holders)
    present = sorted(w for w in by_word if w in text)
    present_direct = [w for w in present if w in direct_words]
    wn, wl = wrong(n, q), wrong(l, q)
    if wn or wl:
        why = "WRONG_BOTH" if wn and wl else "WRONG_WITHOUT_LAYER" if wn else "WRONG_WITH_LAYER"
    elif correct(l, q) and not correct(n, q):
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
    rows.append({"id": q["id"], "question": q["question"], "why": why, "routed": bool(present_direct), "layer_words_in_text": present, "direct_layer_words_in_text": present_direct, "holder_sentences": holders,
                 "without_layer": {"verdict": n["out"].get("verdict"), "values": n["out"].get("values"), "reason": n["out"].get("reason"), "qc": (n["out"].get("question_cross") or {}).get("reason")},
                 "with_layer": {"verdict": o.get("verdict"), "values": o.get("values"), "reason": o.get("reason"), "qc": qc.get("reason")},
                 "answers_identical": json.dumps(n["out"], ensure_ascii=False, sort_keys=True) == json.dumps(o, ensure_ascii=False, sort_keys=True)})
    counts[why] = counts.get(why, 0) + 1
n_answerable = sum(1 for q in qs if q["expect"] != "ABSTAIN")
n_wrong = sum(1 for r in rows if r["why"].startswith("WRONG_"))
print(json.dumps({"counts": counts, "answerable": n_answerable, "routed": sum(1 for r in rows if r["routed"]), "wrong": n_wrong}, ensure_ascii=False))
for r in rows:
    print(json.dumps(r, ensure_ascii=False))

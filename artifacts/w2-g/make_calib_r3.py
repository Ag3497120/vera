"""A small calibration set for the phases prompt's `decides` wording, built from the W2-c fixtures (NOT the frozen G3 data of w2g / w2g2):
eight order questions the rules answer, and four traps I wrote (another subject, an amount of time, a preference, another time)."""
import json
from pathlib import Path
W = Path(__file__).resolve().parents[2]
src = {json.loads(l)["id"]: json.loads(l) for l in (W / "tests/conduct_ask/fixtures/items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
keep = ["w2c-f01-06", "w2c-f02-04", "w2c-f02-01", "w2c-f03-03", "w2c-f05-06", "w2c-f07-04", "w2c-f11-06", "w2c-f10-06"]
out = [src[i] for i in keep]
def trap(i, lang, frame, q, opts, why):
    return {"id": i, "lang": lang, "category": "calib/TRAP", "frame_id": frame, "question": q, "options": opts, "rationale": why,
            "expect": {"kind": "ORDER", "decision": "escalate", "evidence": why, "vocab": {"out_of_vocabulary": False}},
            "w2c": {"category": "escalate", "oov_none": False, "escalate_reason": "FRAME_SILENT", "trap": True, "permission": None}}
out += [
    trap("calib-t1", "en", "f02_greenhouse", "In the neighbouring greenhouse's project, can we start the watering scheduler before the sensor message format is defined?", ["Yes", "No"], "another subject"),
    trap("calib-t2", "ja", "f01_loan", "貸出画面を作る前に受入確認を始めるとして、何日あけるべきですか？", ["三日", "一週間"], "an amount of time, not the order"),
    trap("calib-t3", "en", "f05_retry", "Which would the team prefer to do before the other, the backoff policy or the retry loop?", ["the retry loop", "the backoff policy"], "a preference"),
    trap("calib-t4", "ja", "f03_handout", "来年度の別の講座の教材では、目次を決める前に第1章を書き始めてもよいですか？", ["はい", "いいえ"], "another time and another course"),
]
d = W / "artifacts/w2-g/live/calib_r3"
(d / "items.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n", encoding="utf-8")
print(len(out), "items")

"""Writes data/synthetic_frame.jsonl and data/confirmations_truth_frame.jsonl (r2, 12.21.6; hand-written).  Run once, then freeze (data_freeze_frame.sha256)."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))

def clause(agent, goal):
    return [{"predicate": "移動する", "roles": {"agent": agent, "goal": goal}, "polarity": "+", "tense": "past", "voice": "active"}]

TARGET = [("田中", "学校"), ("鈴木", "会社"), ("太郎", "学校"), ("整備士", "会社"), ("山田", "学校")]
NOT_RESTRICTIVE = [("田中", "駅"), ("鈴木", "倉庫"), ("太郎", "病院")]    # goal is PLACE: the declared frame (goal=GROUP_ORG only) does not stop them
CONTROL = ["田中が本を読んだ。", "鈴木が手紙を書いた。", "太郎が走った。", "整備士が倉庫で点検した。"]
rows = []
for i, (a, g) in enumerate(TARGET, 1):
    rows.append({"id": "f%02d" % i, "text": "%sが%sへ移動した。" % (a, g), "expect": clause(a, g), "group": "target"})
for i, (a, g) in enumerate(NOT_RESTRICTIVE, 1):
    rows.append({"id": "n%02d" % i, "text": "%sが%sへ移動した。" % (a, g), "expect": clause(a, g), "group": "frame_not_restrictive"})
for i, s in enumerate(CONTROL, 1):
    rows.append({"id": "c%02d" % i, "text": s, "expect": None, "group": "control"})
with open(os.path.join(D, "synthetic_frame.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
TRUTH = [
 {"op": "set", "word": "移動する", "type": "P_MOVE", "reason": "prerequisite of the frame (base DECIDED, a human type is needed first)"},
 {"op": "frame", "predicate": "移動する", "particle": "へ", "role": "goal", "types": ["GROUP_ORG"], "reason": "goal of 移動する may be an organisation (学校・会社)"},
]
with open(os.path.join(D, "confirmations_truth_frame.jsonl"), "w", encoding="utf-8") as f:
    for t in TRUTH:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

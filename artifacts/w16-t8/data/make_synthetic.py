"""Writes data/synthetic_40.jsonl and data/confirmations_truth.jsonl (hand-written lists; expects follow the confirmed types). Run once, then freeze (data_freeze.sha256)."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))

def clause(pred, agent, goal):
    return [{"predicate": pred, "roles": {"agent": agent, "goal": goal}, "polarity": "+", "tense": "past", "voice": "active"}]

# (agent, goal, predicate dictionary form, surface verb) per target
T = [
 ("田中", "整備室", "移動する", "移動した"), ("鈴木", "実験棟", "移動する", "移動した"), ("太郎", "図書館", "移動する", "移動した"), ("整備士", "学校", "移動する", "移動した"),
 ("田中", "工房", "移動する", "移動した"), ("鈴木", "倉庫", "移動する", "移動した"), ("太郎", "駅", "移動する", "移動した"), ("整備士", "書庫", "移動する", "移動した"),
 ("鈴木", "会社", "移動する", "移動した"),
 ("田中", "整備室", "移住する", "移住した"), ("鈴木", "実験棟", "移住する", "移住した"), ("太郎", "図書館", "移住する", "移住した"), ("整備士", "学校", "移住する", "移住した"),
 ("田中", "工房", "移住する", "移住した"), ("太郎", "会社", "移住する", "移住した"),
 ("鈴木", "整備室", "出向く", "出向いた"), ("太郎", "学校", "出向く", "出向いた"), ("整備士", "工房", "出向く", "出向いた"), ("田中", "図書館", "出向く", "出向いた"),
 ("鈴木", "実験棟", "赴く", "赴いた"), ("太郎", "学校", "赴く", "赴いた"), ("整備士", "工房", "赴く", "赴いた"), ("田中", "会社", "赴く", "赴いた"),
 ("田中", "整備室", "参上する", "参上した"), ("鈴木", "工房", "参上する", "参上した"),
 ("太郎", "学校", "歩く", "歩いた"),
]
CONTROL = [   # no confirmed word (整備室 実験棟 図書館 学校 会社 移動 移住 出向 赴 参上) in any of them
 "田中が本を読んだ。", "鈴木が倉庫へ向かった。", "太郎が駅から出発した。", "田中が荷物を倉庫へ運んだ。", "鈴木が工房で本を読んだ。",
 "ソラが駅へ行った。", "鈴木が荷物を工房へ運んだ。", "ハルがミナに話した。", "技師が駅から帰った。", "整備士が倉庫で点検した。",
 "山田が駅へ向かった。", "太郎が温室で働いた。", "鈴木が書庫で本を書いた。", "太郎が工房へ転勤した。",
]
rows = []
for i, (a, g, p, v) in enumerate(T, 1):
    rows.append({"id": "t%02d" % i, "text": "%sが%sへ%s。" % (a, g, v), "expect": clause(p, a, g), "group": "target"})
for i, s in enumerate(CONTROL, 1):
    rows.append({"id": "c%02d" % i, "text": s, "expect": None, "group": "control"})
with open(os.path.join(D, "synthetic_40.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
TRUTH = [
 {"op": "set", "word": "整備室", "type": "PLACE", "reason": "unplaced name"},
 {"op": "set", "word": "実験棟", "type": "PLACE", "reason": "unplaced name"},
 {"op": "set", "word": "図書館", "type": "PLACE", "reason": "multiple (GROUP_ORG / PLACE)"},
 {"op": "set", "word": "学校", "type": "PLACE", "reason": "override base DECIDED GROUP_ORG"},
 {"op": "set", "word": "会社", "type": "PLACE", "reason": "override base DECIDED GROUP_ORG"},
 {"op": "set", "word": "移動する", "type": "P_MOVE", "reason": "override base DECIDED direct (frame lacks が)"},
 {"op": "set", "word": "移住する", "type": "P_MOVE", "reason": "override base DECIDED estimated (generated)"},
 {"op": "set", "word": "出向く", "type": "P_MOVE", "reason": "override base DECIDED estimated (generated)"},
 {"op": "set", "word": "赴く", "type": "P_MOVE", "reason": "override base DECIDED estimated (generated)"},
 {"op": "set", "word": "参上する", "type": "P_MOVE", "reason": "unknown word"},
]
with open(os.path.join(D, "confirmations_truth.jsonl"), "w", encoding="utf-8") as f:
    for r in TRUTH:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

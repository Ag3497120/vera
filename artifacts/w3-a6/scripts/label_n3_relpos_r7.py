#!/usr/bin/env python3
"""Freeze the preregistered visual labels for generated relative-position claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
SOURCE = ART / "n3_relpos_claims_prefreeze.jsonl"
OUTPUT = ART / "n3_relpos_visual_labels_r7.jsonl"

# The visual criterion is whether the common meaning is a relative position or
# direction, rather than a place itself. Ambiguous regional and route nouns are
# kept as "疑わしい". Only an unmistakable facility or landform is an error.
ERRORS = {
    "北駅": "駅を指す施設名として読め、相対位置語だけにはならない。",
    "崎": "岬などの突出した地形そのものを表す語で、場所・地形の型に当たる。",
}
SUSPICIOUS = {
    "あたり": "場所だけでなく時間の範囲にも使われる。",
    "アメリカ合衆国内": "国の領域を指し、場所と範囲表現の境界が曖昧。",
    "上位": "順位の比喩的な位置を含み、空間位置とは限らない。",
    "コース": "経路のほか競技施設・区間そのものも指す。",
    "世界中": "全世界の区域を指し、相対位置ではなく場所範囲の読みもある。",
    "ルート": "移動経路そのものを指し、場所と方向の境界が曖昧。",
    "全土": "地域全体という地理範囲を指す。",
    "内陸部": "地理的な地域・土地を指す読みがある。",
    "北方": "方角だけでなく北の地域を指すことがある。",
    "国境": "地理上の境界線・境界地域そのものを指す。",
    "境": "地理的境界と抽象的な分かれ目の両方を指す。",
    "方面": "方向のほか地域を指す読みがある。",
    "曲がり角": "道路上の特定地点・目印としても使われる。",
    "最寄り": "最も近い地点・施設を指す名詞用法がある。",
    "村はずれ": "村の周辺区域そのものを指す読みがある。",
    "点": "座標上の位置のほか、特定の箇所・標識も指す。",
    "東岸": "岸という地形と方向関係の両方を表しうる。",
    "両岸": "岸という地形・区域を指す読みがある。",
    "南岸": "岸という地形と方向関係の両方を表しうる。",
    "西岸": "岸という地形と方向関係の両方を表しうる。",
    "川べり": "川岸の地域・場所自体を指す読みがある。",
    "川沿い": "川沿いの区域・地域自体を指すことがある。",
    "湾口": "湾の出入口にあたる地形・地点自体を指す。",
    "海上": "海上の区域自体を指す用法がある。",
    "海面": "海の表面そのものを指す地理的対象でもある。",
    "経路": "地点間の道筋・経路そのものを指す。",
    "軌道": "軌跡・運行経路などの対象名としても使われる。",
    "航路": "定められた航行経路自体を指す。",
    "近隣": "近い区域・地域そのものを指す読みがある。",
    "隣": "隣接する相手・場所自体を指すことがある。",
    "頂": "山頂など実在の地形部分そのものを指す読みがある。",
    "高所": "高い地点・場所そのものを指す名詞用法がある。",
    "北方": "方角と北の地域の両方に使われる。",
    "北部": "地域の区分・地域自体を指す読みがある。",
    "社内": "組織内部という抽象的範囲にも使われ、空間とは限らない。",
    "正面": "相対位置のほか建物の正面部分・正面区域を指す。",
    "軒下": "建物の軒下という場所・空間自体を指す。",
    "軒先": "軒の端という建築部分・場所そのものを指す。",
    "近隣": "近隣の地域自体を表す読みがある。",
}

rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
output = []
for row in rows:
    word = row["word"]
    if word in ERRORS:
        label, note = "誤り", ERRORS[word]
    elif word in SUSPICIOUS:
        label, note = "疑わしい", SUSPICIOUS[word]
    else:
        label, note = "正しい", "定義は他の物・場所を基準にした位置、方向、内外、距離または部分を表す。"
    output.append({**row, "visual_label": label, "note": note})

OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in output), encoding="utf-8")
labels = [row["visual_label"] for row in output]
print(json.dumps({
    "relative_position_claims": len(output),
    "correct": labels.count("正しい"),
    "suspicious": labels.count("疑わしい"),
    "obvious_errors": labels.count("誤り"),
    "labels_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
}, ensure_ascii=False, indent=2))

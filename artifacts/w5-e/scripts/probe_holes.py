"""W5-e: the gate (docs/READING_SOUNDNESS.md 10E) against generated forms of coordination that are NOT in the frozen data, to find what it does not stop.
Not a judge (no expectation is frozen here): it lists every generated sentence the entry still READS, per joining form.  usage: probe_holes.py <tree>"""
import itertools
import json
import sys
sys.path.insert(0, sys.argv[1])
from verantyx import semantic_read as SR
assert SR.__file__.startswith(sys.argv[1])

A1 = ["太郎", "先生", "ミラ", "田中さん", "兄", "彼", "委員会", "犬"]
B1 = ["花子", "その妹", "小さな妹", "背の高い妹", "妹たち", "ルナ", "ＡＢ", "三人の友達", "友達など", "同僚の山田さん", "妹ら", "社員"]
V1 = ["{a}と{b}が来た。", "{a}と{b}は笑った。", "{a}と{b}も走った。", "{a}と{b}を見た。", "{a}と{b}に会った。", "{a}と{b}で話した。", "{a}と{b}まで来た。", "{a}と{b}さえ来た。",
      "{a}と{b}だけが来た。", "{a}と{b}こそ来た。", "{a}とも{b}ともが来た。", "{a}とは{b}が来た。", "{a}と{b}すら来た。"]
A2 = ["太郎", "先生", "ミラ", "田中さん", "兄", "彼", "委員会", "犬", "本", "駅", "月曜"]
B2 = ["花子", "その妹", "小さな妹", "妹たち", "ルナ", "三人の友達", "友達など", "社員", "雑誌", "火曜", "病院"]
P2 = ["や", "か", "または", "あるいは", "とか", "やら", "なり", "だの", "と", "も", "とも", "に", "とは"]
V2 = ["{a}{p}{b}が来た。", "{a}{p}{b}を買った。", "{a}{p}{b}に行った。", "{a}{p}{b}は見えた。", "{a}{p}{b}も見えた。", "{a}{p}{b}で会った。", "{a}{p}{b}の本を読んだ。", "{a}{p}{b}から来た。",
      "{a}{p}{b}へ行った。", "{a}{p}{b}と話した。"]
A3 = ["太郎", "先生", "ミラ", "兄", "本", "駅", "委員会"]
B3 = ["花子", "妹", "ルナ", "雑誌", "病院"]
P3 = ["および", "及び", "ならびに", "並びに", "かつ", "ないし", "もしくは", "若しくは", "又は", "又", "やら", "だの", "でも", "、", "、そして", "に加えて", "とともに", "ほか", "なり"]
V3 = ["{a}{p}{b}が来た。", "{a}{p}{b}を買った。", "{a}{p}{b}は見えた。", "{a}{p}{b}に会った。"]

read = {}
total = 0
for a, b, v in itertools.product(A1, B1, V1):
    s = v.format(a=a, b=b); total += 1
    o = SR.read(s, "ja")
    if o["readable"]: read.setdefault("と(form)", []).append((s, [c["roles"] for c in o["clauses"]]))
for a, b, p, v in itertools.product(A2, B2, P2, V2):
    s = v.format(a=a, b=b, p=p); total += 1
    o = SR.read(s, "ja")
    if o["readable"]: read.setdefault(p, []).append((s, [c["roles"] for c in o["clauses"]]))
for a, b, p, v in itertools.product(A3, B3, P3, V3):
    s = v.format(a=a, b=b, p=p); total += 1
    o = SR.read(s, "ja")
    if o["readable"]: read.setdefault("conn:" + p, []).append((s, [c["roles"] for c in o["clauses"]]))
print("generated", total, "still read", sum(len(v) for v in read.values()))
for k, v in read.items():
    print("==", k, len(v))
    for s, r in v[:3]: print("  ", s, json.dumps(r, ensure_ascii=False))

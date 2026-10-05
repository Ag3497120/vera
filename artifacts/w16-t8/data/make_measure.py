"""Writes data/measure_{confirmations,train,test,real}.jsonl (own synthetic data for the tool check T8-3; hand-listed verbs, templated sentences).  NOT blind: the writer knew the confirmed list."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
CONF = "移送 遠征 出陣 上京 来日 入場 退場 通勤 通学 疎開 亡命 進軍 行進 出動 出社 登校 下山 登頂 到達 潜入".split()
TEST_V = "突入 接近 集合 巡回 往復 飛来 転勤 進出".split()
AG = ["田中", "鈴木", "太郎", "整備士", "技師"]
GL = ["工房", "倉庫", "駅", "書庫", "市場", "港", "農場", "病院"]

def exp(v, a, g):
    return [{"predicate": v + "する", "roles": {"agent": a, "goal": g}, "polarity": "+", "tense": "past", "voice": "active"}]

def w(name, rows):
    with open(os.path.join(D, name), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

w("measure_confirmations.jsonl", [{"op": "set", "word": v + "する", "type": "P_MOVE", "reason": "unlisted motion verb"} for v in CONF])
train = []
for i, v in enumerate(CONF):
    for j in range(2):
        a, g = AG[(i + j) % 5], GL[(i * 2 + j) % 8]
        train.append({"id": "tr%02d" % (len(train) + 1), "text": "%sが%sへ%sした。" % (a, g, v), "expect": exp(v, a, g)})
w("measure_train.jsonl", train)
test = []
for i, v in enumerate(TEST_V):
    for j in range(2):
        a, g = AG[(i + j + 2) % 5], GL[(i * 3 + j + 1) % 8]
        test.append({"id": "te%02d" % (len(test) + 1), "text": "%sが%sへ%sした。" % (a, g, v), "expect": exp(v, a, g)})
w("measure_test.jsonl", test)
real = [   # varied "real-like" sentences: the first four use a confirmed verb in the same pattern (the writer knew the list: not blind), the rest are other patterns (expect unjudged = null, or ABSTAIN)
 {"id": "re01", "text": "整備士が倉庫へ出動した。", "expect": exp("出動", "整備士", "倉庫")},
 {"id": "re02", "text": "技師が港へ到達した。", "expect": exp("到達", "技師", "港")},
 {"id": "re03", "text": "田中が農場へ疎開した。", "expect": exp("疎開", "田中", "農場")},
 {"id": "re04", "text": "鈴木が市場へ通勤した。", "expect": exp("通勤", "鈴木", "市場")},
 {"id": "re05", "text": "ハルがミナに話した。", "expect": "ABSTAIN"},
 {"id": "re06", "text": "田中が土間に荷物を置いた。", "expect": "ABSTAIN"},
 {"id": "re07", "text": "ミナがザクった。", "expect": "ABSTAIN"},
 {"id": "re08", "text": "太郎が駅から出発した。", "expect": None},
 {"id": "re09", "text": "鈴木が書庫で本を書いた。", "expect": None},
 {"id": "re10", "text": "整備士がチェーンにグリスを塗った。", "expect": "ABSTAIN"},
 {"id": "re11", "text": "技師が病院へ上京した。", "expect": exp("上京", "技師", "病院")},
 {"id": "re12", "text": "田中が本を読んだ。", "expect": None},
]
w("measure_real.jsonl", real)

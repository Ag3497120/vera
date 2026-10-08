"""Write the frozen W3-b3 attack corpus. This file only serializes authored text; it never imports or calls the reader."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = []


def add(group, rows, default_mode="abstain"):
    for text, expected in rows:
        if isinstance(expected, str):
            expected = {"mode": expected}
        elif expected is None:
            expected = {"mode": default_mode}
        CASES.append({"id": "%s-%03d" % (group.upper(), sum(c["group"] == group for c in CASES) + 1),
                      "group": group, "lang": "en" if group == "english" else "ja",
                      "text": text, "expected": expected})


# 40 relative-clause head, omitted-role, and outer-relation challenges.
add("relative", [
    ("母が弟に話した人を兄が呼んだ。", {"mode": "read", "relation": "relative", "head": {"from_role": "patient", "to_role": "patient"}}),
    ("経理課が送った取引先を部長が訪ねた。", "abstain"),
    ("経理課が取引先に送った書類を部長が確認した。", "abstain"),
    ("先生が褒めた生徒を校長が紹介した。", "abstain"),
    ("褒めた生徒を先生が紹介した。", "abstain"),
    ("本を読んだ図書館に友人が着いた。", "abstain"),
    ("父が買った店に母が行った。", "abstain"),
    ("父の買った本を母が読んだ。", "abstain"),
    ("魚を焼く匂いを犬が追った。", "abstain"),
    ("出発した翌日に弟が電話した。", "abstain"),
    ("母が話した人を兄が呼んだ。", "abstain"),
    ("母が弟に話した部屋を兄が見た。", "abstain"),
    ("姉が弟に伝えた客を母が待った。", "abstain"),
    ("父が妹に送った取引先を兄が訪ねた。", "abstain"),
    ("先生が生徒に言った学校を父が訪ねた。", "abstain"),
    ("兄が弟に頼んだ荷物を母が運んだ。", "abstain"),
    ("母が娘に聞いた答えを父が書いた。", "abstain"),
    ("姉が先生に話した学生を校長が呼んだ。", "abstain"),
    ("父が町から出た客を母が見た。", "abstain"),
    ("町へ行った人を兄が待った。", "abstain"),
    ("駅から帰った友達を姉が迎えた。", "abstain"),
    ("店で働いた人を父が訪ねた。", "abstain"),
    ("公園を歩いた子を母が呼んだ。", "abstain"),
    ("父が駅へ向かった町を母が探した。", "abstain"),
    ("兄が家から出た部屋を弟が片付けた。", "abstain"),
    ("父が店から持ち帰った本を母が読んだ。", "abstain"),
    ("先生が生徒に話した内容を父が覚えた。", "abstain"),
    ("母が弟に伝えた知らせを姉が読んだ。", "abstain"),
    ("犬が追いかけた音を子どもが聞いた。", "abstain"),
    ("鳥が飛んだ空を妹が見上げた。", "abstain"),
    ("兄が出発した前に母が電話した。", "abstain"),
    ("父が帰った後を姉が記録した。", "abstain"),
    ("兄が来た時に弟が出発した。", "abstain"),
    ("友人が卒業した年を母が覚えている。", "abstain"),
    ("祖父が旅立った理由を孫が尋ねた。", "abstain"),
    ("弟が本を読んでいない間に姉が帰った。", "abstain"),
    ("父が手紙を書いた机を母が片付けた。", "abstain"),
    ("姉が写真を撮った海辺に弟が来た。", "abstain"),
    ("母が料理した台所を父が掃除した。", "abstain"),
    ("先生が学生を待った教室を校長が見た。", "abstain"),
])

# 40 closed-list boundary, connective-vs-case, quote-vs-condition, and multi-cut cases.
add("boundary", [
    ("兄が駅へ行ったので弟が家へ帰った。", {"mode": "read", "relation": "cause"}),
    ("兄が駅へ行ったから弟が家へ帰った。", {"mode": "read", "relation": "cause"}),
    ("兄が駅へ行ったが弟が家へ帰った。", {"mode": "read", "relation": "contrast"}),
    ("姉が町へ来たけれど弟は店へ行った。", "abstain"),
    ("兄が駅へ行くと弟が家へ帰る。", {"mode": "read", "relation": "condition"}),
    ("兄が駅へ行けば弟が家へ帰る。", {"mode": "read", "relation": "condition"}),
    ("兄が駅へ行ったら弟が家へ帰る。", {"mode": "read", "relation": "condition"}),
    ("兄が駅へ行くなら弟が家へ帰る。", {"mode": "read", "relation": "condition"}),
    ("兄が駅へ行っても弟が家へ帰る。", {"mode": "read", "relation": "concession"}),
    ("兄が駅へ歩きながら弟が歌った。", "abstain"),
    ("兄が来ると母が言った。", "abstain"),
    ("兄が帰ると父が思った。", "abstain"),
    ("兄が来たと母が考えた。", "abstain"),
    ("兄が来なかったと弟が話した。", "abstain"),
    ("兄が駅から来た。", "abstain"),
    ("兄が駅から帰ったので弟が喜んだ。", {"mode": "read", "relation": "cause"}),
    ("兄が来て弟が帰って母が寝た。", "abstain"),
    ("兄が来て、弟が帰って、母が寝た。", "abstain"),
    ("兄が来るために弟が駅へ行った。", "abstain"),
    ("兄が来るように弟が駅へ行った。", "abstain"),
    ("兄が来たのに弟が帰った。", "abstain"),
    ("兄が帰ってから弟が出た。", "abstain"),
    ("兄が来た後に弟が帰った。", "abstain"),
    ("兄が来たので、だから弟が帰った。", "abstain"),
    ("兄が帰ったり弟が来たりした。", "abstain"),
    ("兄が駅へ行き弟が家へ帰った。", "abstain"),
    ("兄が駅へ行き、弟が家へ帰った。", "abstain"),
    ("兄が駅へ行ったので弟が家へ帰った。母が店へ来た。", "abstain"),
    ("兄が家へ帰ったが弟が駅へ行った。", {"mode": "read", "relation": "contrast"}),
    ("姉が町へ出たので弟が家へ帰った。", {"mode": "read", "relation": "cause"}),
    ("父が駅へ来たから母が店へ行った。", {"mode": "read", "relation": "cause"}),
    ("父が駅へ行くと母が町へ来る。", {"mode": "read", "relation": "condition"}),
    ("母が町へ帰れば父が駅へ出る。", {"mode": "read", "relation": "condition"}),
    ("兄が店へ行ったけれど妹が家へ帰った。", {"mode": "read", "relation": "contrast"}),
    ("兄が店へ行ったけど妹が家へ帰った。", {"mode": "read", "relation": "contrast"}),
    ("兄が駅へ出ても弟が家へいる。", "abstain"),
    ("兄が駅へ行って弟が歌った。", "abstain"),
    ("兄が本を読み、しかし弟が駅へ行った。", "abstain"),
    ("兄が駅へ行くと、弟が帰った。", "abstain"),
    ("兄が駅へ行ったので弟が家へ帰ったのだ。", "abstain"),
])

# 30 negation, tense, and scope checks.
add("scope", [
    ("兄が駅へ行かなかったので弟が家へ帰った。", {"mode": "read", "relation": "cause", "polarities": ["-", "+"]}),
    ("兄が家へ帰らなかったので弟が駅へ行った。", {"mode": "read", "relation": "cause", "polarities": ["-", "+"]}),
    ("弟が町へ来なかったから兄が駅へ帰った。", {"mode": "read", "relation": "cause", "polarities": ["-", "+"]}),
    ("姉が家へ出なかったので母が駅へ来た。", {"mode": "read", "relation": "cause", "polarities": ["-", "+"]}),
    ("父が駅へ来たので母が家へ帰らなかった。", {"mode": "read", "relation": "cause", "polarities": ["+", "-"]}),
    ("兄が町へ行ったので弟が家へ帰らなかった。", {"mode": "read", "relation": "cause", "polarities": ["+", "-"]}),
    ("母が家へ帰らなかったから父が駅へ来なかった。", {"mode": "read", "relation": "cause", "polarities": ["-", "-"]}),
    ("姉が駅へ行かなかったが弟は家へ帰った。", "abstain"),
    ("兄が来なかったので帰った。", "abstain"),
    ("読んでいない本を弟が買った。", "abstain"),
    ("兄が駅へ行かなかったと母が言った。", "abstain"),
    ("兄が駅へ行ったと母が思わなかった。", "abstain"),
    ("兄が駅へ行くと弟が帰った。", "abstain"),
    ("兄が来れば弟が帰った。", "abstain"),
    ("兄が駅へ行ったら弟が家へ帰った。", "abstain"),
    ("兄が来なかったので弟は決して帰らなかった。", "abstain"),
    ("兄がまだ来なかったので弟が帰った。", "abstain"),
    ("兄が来たので弟がまだ帰っていない。", "abstain"),
    ("兄が駅へ行っていない間に弟が帰った。", "abstain"),
    ("兄が駅へ行かなかったため弟が家へ帰った。", "abstain"),
    ("兄が駅へ行っても弟が家へ帰らない。", "abstain"),
    ("兄が店へ来なかったけれど弟が駅へ出た。", "abstain"),
    ("兄が店へ来たけれど弟が帰らなかった。", "abstain"),
    ("兄が駅へ行かなければ弟が帰らない。", "abstain"),
    ("兄が駅へ行ったので弟が帰る。", {"mode": "read", "relation": "cause", "tense": ["past", "nonpast"]}),
    ("兄が駅へ行くので弟が家へ帰る。", {"mode": "read", "relation": "cause", "tense": ["nonpast", "nonpast"]}),
    ("兄が家へ帰ったから弟が駅へ出た。", {"mode": "read", "relation": "cause", "tense": ["past", "past"]}),
    ("兄が駅へ行かなかったので弟が家へ帰った。", {"mode": "read", "relation": "cause", "polarities": ["-", "+"]}),
    ("兄が駅へ行ったので弟が家へ帰った。", {"mode": "read", "relation": "cause", "polarities": ["+", "+"]}),
    ("兄が家へ帰らなかったから弟が駅へ行った。", {"mode": "read", "relation": "cause", "polarities": ["-", "+"]}),
])

# 25 ellipsis cases; only first-person? no, only explicit topic antecedents are licensed.
add("ellipsis", [
    ("兄は駅へ行ったので家へ帰った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "兄"}}),
    ("父は町へ来たから店へ戻った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "父"}}),
    ("祖父は駅へ出たので家へ帰った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "祖父"}}),
    ("姉は店へ行ったので駅へ帰った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "姉"}}),
    ("母は町へ来たので家へ出た。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "母"}}),
    ("弟は駅へ帰るなら兄も家へ行く。", "abstain"),
    ("太郎が花子に会って泣いた。", "abstain"),
    ("太郎が花子に電話したので泣いた。", "abstain"),
    ("太郎が花子に手紙を書いたので喜んだ。", "abstain"),
    ("兄が駅へ行ったので帰った。", "abstain"),
    ("兄が駅へ行ったので弟が帰った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "弟"}}),
    ("兄が駅へ行ったので弟は帰った。", "abstain"),
    ("兄が弟に話したので母が帰った。", "abstain"),
    ("父が読んだので母が喜んだ。", "abstain"),
    ("姉が聞いたから兄が帰った。", "abstain"),
    ("兄が駅へ行ったので彼が帰った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "彼"}}),
    ("彼が駅へ行ったので帰った。", "abstain"),
    ("太郎が帰ったので花子が笑った。", {"mode": "read", "relation": "cause", "role_values": {"0.agent": "太郎", "1.agent": "花子"}}),
    ("花子が駅へ来たから太郎が家へ帰った。", {"mode": "read", "relation": "cause", "role_values": {"0.agent": "花子", "1.agent": "太郎"}}),
    ("兄が駅へ行けば帰った。", "abstain"),
    ("兄は駅へ行ったので弟が家へ帰った。", {"mode": "read", "relation": "cause", "role_values": {"1.agent": "弟"}}),
    ("母が町へ来たので父が店へ行った。", {"mode": "read", "relation": "cause", "role_values": {"0.agent": "母", "1.agent": "父"}}),
    ("姉が妹に話したので兄が帰った。", "abstain"),
    ("兄が駅へ行って、弟が帰った。", "abstain"),
    ("太郎が来て泣いた。", "abstain"),
])

# 20 parallel/disjunctive fillers. No distribution or winner is licensed by the input alone.
add("parallel", [
    ("太郎と花子が本と雑誌を買った。", "abstain"),
    ("太郎か花子が本を買った。", "abstain"),
    ("本か雑誌を花子が買った。", "abstain"),
    ("太郎または花子が駅へ行った。", "abstain"),
    ("兄と弟が家へ帰った。", "abstain"),
    ("姉も妹も駅へ来た。", "abstain"),
    ("先生と校長が生徒と父に話した。", "abstain"),
    ("父か母が弟に本を渡した。", "abstain"),
    ("花子が赤い本と青い雑誌を読んだ。", "abstain"),
    ("兄が駅か町へ行った。", "abstain"),
    ("太郎と花子が手紙を読んだ。", "abstain"),
    ("本と新聞を兄が読んだ。", "abstain"),
    ("弟か妹が父に電話した。", "abstain"),
    ("兄も弟も母に話した。", "abstain"),
    ("父と母が町へ来た。", "abstain"),
    ("店か学校で姉が働いた。", "abstain"),
    ("太郎と次郎が雑誌を買った。", "abstain"),
    ("姉が本または雑誌を読んだ。", "abstain"),
    ("兄と妹が駅へ向かった。", "abstain"),
    ("先生か学生が手紙を送った。", "abstain"),
])

# 15 English controls for Japanese-path leakage and relation/head corruption.
add("english", [
    ("The student who read the book called his mother.", {"mode": "base_parity"}),
    ("The letter that the clerk sent arrived yesterday.", {"mode": "base_parity"}),
    ("The person whom the teacher praised left the room.", {"mode": "base_parity"}),
    ("The manager said that the clerk mailed the contract.", {"mode": "base_parity"}),
    ("The fact that the train left surprised the visitors.", {"mode": "base_parity"}),
    ("The boy who came from town met his sister.", {"mode": "base_parity"}),
    ("The book that the girl did not read was on the desk.", {"mode": "base_parity"}),
    ("The woman who wrote the letter called the student.", {"mode": "base_parity"}),
    ("The clerk arrived, and the manager left.", {"mode": "base_parity"}),
    ("The student who arrived did not call the teacher.", {"mode": "base_parity"}),
    ("The teacher said that the student would come.", {"mode": "base_parity"}),
    ("The person that the office sent a parcel to called back.", {"mode": "base_parity"}),
    ("The library where the boy read the book opened early.", {"mode": "base_parity"}),
    ("The manager who sent the client a letter returned home.", {"mode": "base_parity"}),
    ("The student who left because it rained returned later.", {"mode": "base_parity"}),
])

COUNTS = Counter(c["group"] for c in CASES)
EXPECTED = Counter({"relative": 40, "boundary": 40, "scope": 30, "ellipsis": 25, "parallel": 20, "english": 15})
assert COUNTS == EXPECTED, (COUNTS, EXPECTED)
ids = [c["id"] for c in CASES]
assert len(ids) == len(set(ids)) == 170
with (ROOT / "cases.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
    for case in CASES:
        stream.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
print(json.dumps({"cases": len(CASES), "groups": dict(COUNTS)}, ensure_ascii=False, sort_keys=True))

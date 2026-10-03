import sys, json
sys.path.insert(0, "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask")
import map_helpers as M
from verantyx import conduct_ask as ca
W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S/tests/conduct_ask/w2c2/frames/"
JA = W + "z01_seedswap.md"; EN = W + "z04_kiln.md"
SC_JA = {"records": ["D2"], "decides": "決まる", "relations": {"D2": ["一致", "矛盾"]}}
SC_EN = {"records": ["D2"], "decides": "決まる", "relations": {"D2": ["一致", "矛盾"]}}
ja_t = "種を送る仕組み"; en_t = "glaze formula shelf"
ja = [
 f"{ja_t}は、範囲に含めなくても大丈夫ですか？",
 f"{ja_t}は範囲に含めずに進めてよいですか？",
 f"{ja_t}を入れないで進めても差し支えないですか？",
 f"{ja_t}はなくても問題ないですか？",
 f"{ja_t}は範囲に入らないのですか？",
 f"{ja_t}は範囲に入らないという理解で合っていますか？",
 f"{ja_t}を扱わなくてもよいですか？",
 f"{ja_t}を扱わなくても構いませんか？",
 f"{ja_t}を範囲に入れなくていいですか？",
 f"{ja_t}は対象外ではないですか？",
 f"{ja_t}を使わずに済ませてもよいですか？",
 f"{ja_t}は含まれないと考えてよいですか？",
 f"{ja_t}を除外せずにおいてもよいですか？",
 f"{ja_t}を外すのは、今回の方針として正しいですか？",
 f"{ja_t}以外はすべて範囲に入りますか？",
 f"{ja_t}を省いても大丈夫ですか？",
 f"{ja_t}はやらなくてもいいですよね？",
 f"{ja_t}は今回見送りでよいですか？",
]
en = [
 f"Is the {en_t} not in scope?",
 f"Isn't the {en_t} in scope?",
 f"Do we really not need the {en_t}?",
 f"Is it OK if we don't include the {en_t}?",
 f"Is it alright if we do not cover the {en_t}?",
 f"Would it be a problem if we didn't cover the {en_t}?",
 f"Would it hurt if we never build the {en_t}?",
 f"We don't need the {en_t}, right?",
 f"The {en_t} isn't in scope, is it?",
 f"The {en_t} is not in scope, correct?",
 f"Is it okay to not include the {en_t}?",
 f"Can't we skip the {en_t}?",
 f"Shouldn't the {en_t} be left out?",
 f"Is it true that the {en_t} is not in scope?",
 f"Is there no need for the {en_t}?",
 f"Can we do without the {en_t}?",
 f"Do you mind if we don't include the {en_t}?",
 f"Is it fine to leave the {en_t} out?",
 f"Are we not including the {en_t}?",
 f"Can we go ahead and drop the {en_t}?",
 f"Is the {en_t} the one we can leave out?",
 f"Is it fine to skip the {en_t}?",
 f"Is it OK to ignore the {en_t}?",
]
bad = 0
for frame, sc, qs, opts in ((JA, SC_JA, ja, M.YN_JA), (EN, SC_EN, en, M.YN_EN)):
    for q in qs:
        off = ca.answer_question(frame, q, opts)
        res, _ = M.ask_map(frame, q, opts, sc)
        a_off, a_map = off["decision"] == "answer", res["decision"] == "answer"
        tag = "ANSWER!!" if (a_off or a_map) else "ok"
        if tag != "ok": bad += 1
        print(f"{tag:9s} off={off['decision']}:{off.get('escalate_reason')}/{off.get('escalate_detail')} map={res['decision']}:{res.get('escalate_reason')}/{res.get('escalate_detail')} {q}")
print("ANSWERS:", bad)

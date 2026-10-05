"""B（LLM＋単純 RAG）の文の選択: 文字 2-gram の BM25（標準ライブラリだけ）。

事前登録 §1.3: 文 = 行、語 = NFKC にした文の文字 2-gram（記号 。、？！「」（）・ と空白を除いてから作る）、
k1 = 1.2、b = 0.75、idf = ln(1 + (N - df + 0.5)/(df + 0.5))。選ぶ文 = スコア > 0 で、5 位のスコア以上の全て
（5 位に同点があれば全部入れ、5 を超えた件数を記録する。順序で切らない）。スコア > 0 が 0 件なら空。
問いの語は集合（重複を数えない）。スコアの合計は math.fsum（足す順序で同点が崩れない）。
"""
import math
import unicodedata
from collections import Counter

K1 = 1.2
B = 0.75
TOP = 5
STRIP = set("。、？！「」（）・") | set(" \t\r\n　")


def bigrams(text):
    s = "".join(c for c in unicodedata.normalize("NFKC", text) if c not in STRIP and c not in "?!()「」")
    return [s[i:i + 2] for i in range(len(s) - 1)]


def scores(sentences, question):
    """sentences: [(fn, ln, text)] -> 各文のスコア（同じ順序）。"""
    docs = [Counter(bigrams(t)) for _, _, t in sentences]
    n = len(docs)
    lens = [sum(c.values()) for c in docs]
    avgdl = (sum(lens) / n) if n else 0.0
    df = Counter()
    for c in docs:
        for g in c:
            df[g] += 1
    q = sorted(set(bigrams(question)))
    out = []
    for c, dl in zip(docs, lens):
        parts = []
        for g in q:
            tf = c.get(g, 0)
            if tf == 0:
                continue
            idf = math.log(1 + (n - df[g] + 0.5) / (df[g] + 0.5))
            parts.append(idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / avgdl)))
        out.append(math.fsum(parts))
    return out


def select(sentences, question, top=TOP):
    """-> (選んだ文のリスト（入力の順）, {"positive": n, "selected": m, "tie_over": 5 を超えた件数})。"""
    sc = scores(sentences, question)
    pos = sorted((s for s in sc if s > 0), reverse=True)
    if not pos:
        return [], {"positive": 0, "selected": 0, "tie_over": 0, "cut": None}
    cut = pos[top - 1] if len(pos) >= top else pos[-1]
    chosen = [s for s, v in zip(sentences, sc) if v > 0 and v >= cut]
    return chosen, {"positive": len(pos), "selected": len(chosen), "tie_over": max(0, len(chosen) - top), "cut": cut}

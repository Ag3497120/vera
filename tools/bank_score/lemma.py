"""辞書形の出現位置を探す閉じた活用表（日本語・英語）。

不規則変化（行く→行った、来る以外の例外、英語の不規則動詞）は表に入れない。
見つからなければ呼び出し側が UNJUDGED にする（推測して当てない）。
"""
from __future__ import annotations

import re

from .normalize import norm

# 五段活用: 辞書形の語尾 → (未然, 連用, 終止, 仮定, 意志, 音便)
_GODAN = {
    "う": ("わ", "い", "う", "え", "お", "っ"),
    "く": ("か", "き", "く", "け", "こ", "い"),
    "ぐ": ("が", "ぎ", "ぐ", "げ", "ご", "い"),
    "す": ("さ", "し", "す", "せ", "そ", None),
    "つ": ("た", "ち", "つ", "て", "と", "っ"),
    "ぬ": ("な", "に", "ぬ", "ね", "の", "ん"),
    "ぶ": ("ば", "び", "ぶ", "べ", "ぼ", "ん"),
    "む": ("ま", "み", "む", "め", "も", "ん"),
    "る": ("ら", "り", "る", "れ", "ろ", "っ"),
}

_KURU_KANJI = ["来る", "来ない", "来なかっ", "来ます", "来ませ", "来た", "来て", "来よう", "来れ", "来られ",
               "こない", "こなかっ", "こられ", "こよう", "きた", "きて", "きます", "きません", "きまし", "きっ"]
_KURU_KANA = ["くる", "こない", "こなかっ", "こられ", "こよう", "きた", "きて", "きます", "きません", "きまし"]


def _is_han(c: str) -> bool:
    return "一" <= c <= "鿿" or "㐀" <= c <= "䶿"


def ja_forms(lemma: str) -> list[str]:
    """日本語の辞書形から、表にある活用形（語幹＋語尾）を作る。"""
    forms = {lemma}
    if lemma.endswith("する") and len(lemma) > 2:
        stem = lemma[:-2]
        forms.update(stem + x for x in ("する", "し", "さ", "せ"))
    elif lemma == "来る":
        forms.update(_KURU_KANJI)
    elif lemma == "くる":
        forms.update(_KURU_KANA)
    elif lemma.endswith("い") and len(lemma) > 1:
        stem = lemma[:-1]
        forms.update(stem + x for x in ("かっ", "く", "けれ"))
    elif lemma.endswith("る") and len(lemma) > 1:
        stem = lemma[:-1]
        # 一段: 語幹そのもの＋れ(仮定・可能)・よ・ろ。五段: 表どおり。辞書形からは区別できないので和集合
        forms.add(stem)
        forms.update(stem + x for x in ("ら", "り", "れ", "ろ", "っ", "よ"))
    elif lemma[-1:] in _GODAN and len(lemma) > 1:
        stem, last = lemma[:-1], lemma[-1]
        mizen, ren, shu, katei, ishi, onbin = _GODAN[last]
        forms.update(stem + x for x in (mizen, ren, shu, katei, ishi))
        if onbin:
            forms.add(stem + onbin)
    return sorted(forms, key=lambda x: (-len(x), x))


def en_forms(lemma: str) -> list[str]:
    """英語: 原形・-s/-es・-ed/-d・-ing（e 落ち・子音重ね・y→ies/ied）。"""
    w = lemma
    forms = {w, w + "s", w + "es", w + "ed", w + "ing"}
    if w.endswith("e"):
        forms.update({w + "d", w[:-1] + "ing"})
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        forms.update({w[:-1] + "ies", w[:-1] + "ied"})
    if len(w) >= 3 and w[-1] not in "aeiouwxy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
        forms.update({w + w[-1] + "ed", w + w[-1] + "ing"})
    return sorted(forms, key=lambda x: (-len(x), x))


def _is_ascii_word(s: str) -> bool:
    return bool(s) and all(c.isascii() and (c.isalpha() or c in "-'") for c in s)


def find_positions(text: str, lemma: str) -> list[int]:
    """正規化済みの text の中での辞書形 lemma の出現位置（開始 index）を昇順で返す。"""
    t = norm(text)
    lem = norm(lemma)
    if not lem:
        return []
    if _is_ascii_word(lem):
        forms = en_forms(lem)
        pat = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(f) for f in forms) + r")(?![a-z])")
        return sorted(m.start() for m in pat.finditer(t))
    positions: set[int] = set()
    for f in ja_forms(lem):
        start = 0
        while True:
            i = t.find(f, start)
            if i < 0:
                break
            end = i + len(f)
            if f != lem and all(_is_han(c) for c in f):
                # 辞書形以外で漢字だけの語形（語幹の 来・見 など）は、漢字の連なりの一部（意見・見学）を除く
                if (i > 0 and _is_han(t[i - 1])) or (end < len(t) and _is_han(t[end])):
                    start = i + 1
                    continue
            positions.add(i)
            start = i + 1
    return sorted(positions)

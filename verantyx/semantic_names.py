"""Morphological split of ``<common-noun descriptor><proper name>`` (e.g. 技師ユン -> 技師 + ユン).

The head is the final proper-noun token; every earlier token must be a common noun or a
noun suffix. The tokens are the ones of the sentence itself (a compound can tokenize
differently in isolation), and they must tile the value exactly. No word list.
"""
from __future__ import annotations

import unicodedata


def tokens_covering(tagged, start, end):
    """tagged: (surface, pos1, pos2, start, end) tokens of one sentence. Tokens tiling [start, end), else None."""
    if start >= end: return None
    inside = []
    for t in tagged:
        token_start, token_end = t[3], t[4]
        if token_start == token_end:
            if start <= token_start <= end: inside.append(t)
            continue
        if token_start < end and token_end > start:
            if token_start < start or token_end > end: return None
            inside.append(t)
    inside.sort(key=lambda t: (t[3], t[4]))
    cursor = start
    for t in inside:
        if t[3] != cursor: return None
        cursor = t[4]
    return inside if inside and cursor == end else None


def name_split_in(cover, value):
    """(descriptor, name) when the covering tokens are descriptor(s) + one proper name, else None."""
    if not cover or len(cover) < 2 or any(not t[0] for t in cover) or ''.join(t[0] for t in cover) != value: return None
    last = cover[-1]
    if last[1] != '名詞' or last[2] != '固有名詞': return None
    if any(t[1] not in ('名詞', '接尾辞') or t[2] in ('固有名詞', '代名詞') for t in cover[:-1]): return None
    descriptor = ''.join(t[0] for t in cover[:-1])
    # A title is a kanji common noun (技師, 店長, 研究員). Katakana/other strings in front of a "proper noun" token are
    # usually one unknown name cut by the tagger (コカカル -> コカ + カル): never split those, or a fragment gets answered.
    if not descriptor or not all(_is_han(ch) for ch in descriptor): return None
    return descriptor, last[0]


def _is_han(char):
    if char == '々': return True
    try:
        name = unicodedata.name(char)
    except ValueError:
        return False
    return name.startswith(('CJK UNIFIED IDEOGRAPH-', 'CJK COMPATIBILITY IDEOGRAPH-'))


def is_past_aux(word) -> bool:
    """The past auxiliary た, including its voiced form だ after 撥音便 (呼んだ, 読んだ): decided by lemma, not surface."""
    feature = getattr(word, 'feature', None)
    return feature is not None and getattr(feature, 'pos1', None) == '助動詞' and str(getattr(feature, 'lemma', None)) == 'た'

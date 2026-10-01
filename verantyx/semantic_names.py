"""Morphological split of ``<common-noun descriptor><proper name>`` (e.g. 技師ユン -> 技師 + ユン).

The head is the final proper-noun token; every earlier token must be a common noun or a
noun suffix. The tokens are the ones of the sentence itself (a compound can tokenize
differently in isolation), and they must tile the value exactly. No word list.
"""
from __future__ import annotations


def tokens_covering(tagged, start, end):
    """tagged: (surface, pos1, pos2, start, end) tokens of one sentence. Tokens tiling [start, end), else None."""
    inside = [t for t in tagged if t[3] >= start and t[4] <= end]
    cursor = start
    for t in inside:
        if t[3] != cursor: return None
        cursor = t[4]
    return inside if inside and cursor == end else None


def name_split_in(cover, value):
    """(descriptor, name) when the covering tokens are descriptor(s) + one proper name, else None."""
    if not cover or len(cover) < 2 or ''.join(t[0] for t in cover) != value: return None
    last = cover[-1]
    if last[1] != '名詞' or last[2] != '固有名詞': return None
    if any(t[1] not in ('名詞', '接尾辞') or t[2] == '固有名詞' for t in cover[:-1]): return None
    return ''.join(t[0] for t in cover[:-1]), last[0]

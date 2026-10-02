"""文字列の正規化・文分割・言語判定（V2_RULES の採点の約束）。"""
from __future__ import annotations

import re
import unicodedata

_WS_RUN = re.compile(r"\s+")


def _is_edge_junk(ch: str) -> bool:
    cat = unicodedata.category(ch)
    return cat.startswith("P") or cat.startswith("Z") or ch.isspace()


_SIGNS = "-\u2010\u2011\u2012\u2013"  # 数値の符号になりうるハイフン・ダッシュ（NFKC 後の形）


def strip_edges(s: str) -> str:
    """前後の空白と句読点（Unicode カテゴリ P*）を除く。

    ただし数値の意味を変える 2 つは落とさない: 先頭の符号（`-`/ダッシュの直後が数字）と、
    末尾の `%`（直前が数字）。落とすと `-2` が `2` に、`50%` が `50` になり偽の PASS を出す。
    """
    i, j = 0, len(s)
    while i < j and _is_edge_junk(s[i]):
        if s[i] in _SIGNS and i + 1 < j and s[i + 1].isdigit():
            break
        i += 1
    while j > i and _is_edge_junk(s[j - 1]):
        if s[j - 1] == "%" and j - 2 >= i and s[j - 2].isdigit():
            break
        j -= 1
    return s[i:j]


def norm(s: object) -> str:
    """NFKC → casefold → 空白の連続を 1 つに → 前後の空白と句読点を除去。"""
    if not isinstance(s, str):
        return ""
    t = unicodedata.normalize("NFKC", s).casefold()
    t = _WS_RUN.sub(" ", t)
    return strip_edges(t)


def char_count(s: str) -> int:
    """max_chars 用: NFKC 後・前後の空白を除いた文字数。"""
    return len(unicodedata.normalize("NFKC", s).strip())


def compact_len(s: str) -> int:
    """圧縮率用: NFKC 後・空白をすべて除いた文字数。"""
    return len(_WS_RUN.sub("", unicodedata.normalize("NFKC", s)))


_TERMINATORS = "。！？!?"


def split_sentences(text: str) -> list[str]:
    """文分割: `。！？!?`、後ろが空白か末尾で前が数字でない `.`、および改行。空の断片は捨てる。"""
    t = unicodedata.normalize("NFKC", text)
    out: list[str] = []
    buf: list[str] = []
    n = len(t)
    for i, ch in enumerate(t):
        if ch == "\n" or ch == "\r":
            _flush(buf, out)
            continue
        if ch in _TERMINATORS:
            _flush(buf, out)
            continue
        if ch == ".":
            nxt_ok = i + 1 >= n or t[i + 1].isspace()
            prev_digit = i > 0 and t[i - 1].isdigit()
            if nxt_ok and not prev_digit:
                _flush(buf, out)
                continue
        buf.append(ch)
    _flush(buf, out)
    return out


def _flush(buf: list[str], out: list[str]) -> None:
    frag = "".join(buf).strip()
    buf.clear()
    if frag and strip_edges(frag):
        out.append(frag)


def has_kana(s: str) -> bool:
    return any("぀" <= c <= "ヿ" for c in s)


def has_han(s: str) -> bool:
    return any("一" <= c <= "鿿" or "㐀" <= c <= "䶿" for c in s)


def has_latin(s: str) -> bool:
    return any(c.isascii() and c.isalpha() for c in s)


def detect_language(text: str) -> str | None:
    """仮名を含む → ja。仮名も漢字も無くラテン文字を含む → en。それ以外は None（判定不能）。"""
    t = unicodedata.normalize("NFKC", text)
    if has_kana(t):
        return "ja"
    if not has_han(t) and has_latin(t):
        return "en"
    return None

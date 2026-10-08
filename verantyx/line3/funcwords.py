"""Function / question words (decision after T6v: V2 is the new default; L-130 / L-150).

A unit is a function unit iff every token of it (UniDic via fugashi) is a particle, auxiliary,
conjunction, adnominal, pronoun / interrogative, adverb, symbol, interjection, prefix, or a
light verb / adjective (pos2 非自立可能); a few fixed compounds are listed.  CHAR tier: a
hiragana character.  The same rule removes question words (どこ, 何, ...) and mixed strings such
as 「はどこにありますか」 (all tokens are function tokens).

The rule is the one T6 measured (experiments/line3/t6/run_readout.py `func_pos`, now imported
from here).  Whether it is the owner's meaning of "助詞を外す" is an open point (L-150).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

FUNC_POS1 = frozenset({"助詞", "助動詞", "接続詞", "連体詞", "代名詞", "補助記号", "感動詞", "接頭辞", "副詞"})
FUNC_COMPOUNDS = frozenset({"における", "について", "として", "による", "により", "によって", "に対して",
                            "において", "にとって", "とともに", "に関する", "に関して"})
_cache: Dict[Tuple[str, str], bool] = {}


def is_function_unit(u: str, tier: str) -> bool:
    k = (u, tier)
    r = _cache.get(k)
    if r is None:
        if tier == "CHAR":
            r = all("぀" <= c <= "ゟ" for c in u)
        elif u in FUNC_COMPOUNDS:
            r = True
        else:
            from verantyx.line3.space import _get_tagger
            toks = list(_get_tagger()(u))
            r = bool(toks) and all(t.feature.pos1 in FUNC_POS1 or t.feature.pos2 == "非自立可能" for t in toks)
        _cache[k] = r
    return r


class _TierFilter:
    """A picklable predicate: is `u` a function unit of tier `tier`."""

    def __init__(self, tier: str) -> None:
        self.tier = tier

    def __call__(self, u: str) -> bool:
        return is_function_unit(u, self.tier)

    def __repr__(self) -> str:
        return "function_words(%s)" % self.tier


def default_filter(tier: str) -> Optional[Callable[[str], bool]]:
    """The default V2 predicate of a tier (RUN / WORD / CHAR); None for any other tier name."""
    return _TierFilter(tier) if tier in ("RUN", "WORD", "CHAR") else None

"""T9 scorer.  A candidate = one entry (a word set).  Gold alternatives are separated by '|'.
Normalisation (applied to gold alternatives and to candidate words alike): NFKC, casefold, remove whitespace,
remove ',' ',' and '・' (thousands separators, middle dots), '万' amounts to digits (3万2500 -> 32500, 5万 -> 50000),
runs of kanji digits 〇一二三四五六七八九 (positional, no 十/百) to ASCII digits.  A candidate holds the gold when any
normalised gold alternative is a substring of the normalised text of ONE word of the entry (the oracle rule of T6ab..C5).
Units are not stripped or converted: '32500キロワット' must still match its unit text; only the number is normalised."""
import re
import unicodedata

_K = {c: str(i) for i, c in enumerate("〇一二三四五六七八九")}


def _man(m):
    a = int(m.group(1)); b = m.group(2)
    return str(a * 10000 + (int(b) if b else 0))


def norm(s):
    s = unicodedata.normalize("NFKC", s).casefold()
    s = re.sub(r"\s+", "", s)
    s = s.replace("・", "").replace("·", "")
    s = re.sub(r"(?<=\d)[,，](?=\d)", "", s)
    s = re.sub(r"[〇一二三四五六七八九]+", lambda m: "".join(_K[c] for c in m.group(0)), s)
    s = re.sub(r"(\d+)万(\d+)?", _man, s)
    return s


def golds(gold):
    return [norm(g) for g in gold.split("|") if g]


def hits_text(gold, text):
    t = norm(text)
    return any(g in t for g in golds(gold))


def hits_words(gold, words):
    gs = golds(gold)
    return any(g in norm(w) for g in gs for w in words)


def verbatim_words(gold, words):
    return any(g in w for g in gold.split("|") if g for w in words)

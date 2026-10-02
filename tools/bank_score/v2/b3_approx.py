"""B3 の表層近似の層（D4）。**読解器ではない。** B3 v2 `audit/baseline_check.py` の lenient（甘めの近似）の移植。

must_express, must_relate, order の入り混じり・新しい内容語（自明でないもの）・俳句の音数のうち、読解器か形態素解析が要るものを
「設計者が測ったのと同じ近似」で当てた結果を返す。結果は主分類（9 分類の見出しの数）には入れず、各規則の
`detail.surface_approx`（PASS / FAIL / UNJUDGED）と行の `class_approx` にだけ使う。
fugashi（unidic-lite）は遅延 import。読めなければ形態素解析が要る近似は UNJUDGED（TOKENIZER_UNAVAILABLE）。
`must_not_relate` は設計者の lenient と同じく近似では検出できない（常に PASS）。
"""
from __future__ import annotations

import re

PASS, FAIL, UNJUDGED = "PASS", "FAIL", "UNJUDGED"

_TAGGER: object = None
_TAGGER_TRIED = False
_FUGASHI_VERSION: str | None = None

FUNC_VERBS_JA = set(["する", "為る", "ある", "有る", "在る", "いる", "居る", "なる", "成る", "できる", "出来る", "おる", "居る",
                     "くる", "来る", "いく", "行く", "ない", "無い", "よい", "良い", "いい"])
FORMAL_NOUNS_JA = set(["こと", "事", "もの", "物", "者", "ところ", "所", "はず", "わけ", "訳", "の", "ため", "為", "よう", "様",
                       "とき", "時"])
META = set(["意味", "語", "言葉", "説明", "候補", "案", "提案", "構成", "創作", "架空", "分解", "単位", "構造", "近傍", "証言",
            "資料", "材料", "定義", "推測", "読み", "名前", "呼び名", "meaning", "word", "term", "explanation", "candidate",
            "proposal", "suggest", "invent", "coin", "coined", "fictional", "decompose", "unit", "structure", "testimony",
            "material", "definition", "guess", "name", "label"])
EN_STOP = set("""a an the and or but if then so because since as of to in on at by for with from into onto over under about after before
until while though although yet not no nor never is are was were be been being am have has had having do does did doing get got make made
can could will would shall should may might must i you he she it we they me him her us them my your his its our their this that these those
there here what which who whom whose when where why how all any some each every both either neither one two three four five six seven eight
nine ten than more most less least very too also just only even still again up down out off back away now today then much many such own
same other another s t don didn doesn isn wasn aren weren won wouldn couldn shouldn let""".split())

NEG_JA = re.compile(r"(ない|なかっ|なく|ず|ません|ませんでし|無い|無かっ)")
NEG_EN = re.compile(r"\b(not|n't|never|no|none|nobody)\b|n't")


def tagger() -> object | None:
    """fugashi の Tagger（無ければ None）。最初の 1 回だけ試す。"""
    global _TAGGER, _TAGGER_TRIED, _FUGASHI_VERSION
    if not _TAGGER_TRIED:
        _TAGGER_TRIED = True
        try:
            import fugashi  # type: ignore
            _TAGGER = fugashi.Tagger()
            try:
                from importlib.metadata import version
                _FUGASHI_VERSION = version("fugashi")
            except Exception:  # noqa: BLE001
                _FUGASHI_VERSION = getattr(fugashi, "__version__", "unknown")
        except Exception:  # noqa: BLE001 - 読めなければ None
            _TAGGER = None
    return _TAGGER


def fugashi_version() -> str | None:
    tagger()
    return _FUGASHI_VERSION


def _nfkc(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", s or "")


# ---- 述語・役割・関係・順序（lenient） -------------------------------------------------------------

def stem(word: str, lang: str) -> list[str]:
    w = _nfkc(word).lower().strip()
    if w == "*":
        return ["*"]
    res = {w}
    if lang == "ja":
        if w.endswith("する") and len(w) > 2:
            res.add(w[:-2])
        elif len(w) >= 2 and w[-1] in "うくぐすつぬぶむるいだ":
            res.add(w[:-1])
        if len(w) >= 3 and w.endswith("める") or w.endswith("げる") or w.endswith("せる") or w.endswith("れる") \
                or w.endswith("ける") or w.endswith("てる") or w.endswith("ねる") or w.endswith("べる") \
                or w.endswith("える") or w.endswith("じる"):
            res.add(w[:-1])
    else:
        if w.endswith("e") and len(w) > 3:
            res.add(w[:-1])
        if w.endswith("y") and len(w) > 3:
            res.add(w[:-1])
        irregular = {"leave": ["left"], "ring": ["rang", "rung"], "eat": ["ate", "eaten"], "take": ["took", "taken"],
                     "drive": ["drove", "driven"], "read": ["read"], "reread": ["reread"], "shelve": ["shelv"],
                     "lend": ["lent"], "rise": ["rose"], "lock": ["lock"], "sign": ["sign"]}
        for k, v in irregular.items():
            if w == k:
                res.update(v)
    return sorted(res, key=len)


def first_pos(out_n: str, cands: list[str], lang: str) -> int:
    best = -1
    for c in cands:
        for s in stem(c, lang):
            if s == "*":
                return 0
            if lang == "en":
                m = re.search(r"\b" + re.escape(s), out_n)
                p = m.start() if m else -1
            else:
                p = out_n.find(s)
            if p >= 0 and (best < 0 or p < best):
                best = p
    return best


def lenient_express(spec: dict, text: str, lang: str, sentences_fn) -> bool:
    sents = sentences_fn(text, lang) or [text]
    which = spec.get("in_sentence")
    if which == "first":
        sents = sents[:1]
    elif which == "last":
        sents = sents[-1:]
    elif isinstance(which, int):
        sents = sents[which - 1:which] if 0 < which <= len(sents) else []
    for s in sents:
        sn = _nfkc(s).lower()
        if first_pos(sn, spec.get("predicate") or ["*"], lang) < 0:
            continue
        ok = True
        for role, cands in spec.items():
            if role in ("predicate", "polarity", "in_sentence", "quant") or not cands:
                continue
            if not any(first_pos(_nfkc(text).lower(), [c], lang) >= 0 for c in cands):
                ok = False
                break
        if not ok:
            continue
        if spec.get("polarity") == "-":
            if not (NEG_JA if lang == "ja" else NEG_EN).search(sn):
                continue
        return True
    return False


def lenient_relate(spec: dict, text: str, lang: str) -> bool:
    on = _nfkc(text).lower()
    keys = ("a", "b") if spec.get("rel") in ("greater", "equal") else ("from", "to")
    return all(first_pos(on, spec.get(k) or [], lang) >= 0 for k in keys)


def lenient_order(stages: list[list[str]], text: str, lang: str) -> bool:
    on = _nfkc(text).lower()
    last = -1
    for st in stages:
        p = first_pos(on, st, lang)
        if p < 0 or p < last:
            return False
        last = p
    return True


# ---- 新しい内容語（§6.6 の近似） ---------------------------------------------------------------------

def ja_content_tokens(text: str) -> list[tuple] | None:
    tg = tagger()
    if tg is None:
        return None
    toks = []
    for w in tg(_nfkc(text)):  # type: ignore[operator]
        f = w.feature
        p1, p2, p3 = f.pos1, f.pos2, f.pos3
        if p1 not in ("名詞", "動詞", "形容詞", "形状詞", "副詞"):
            continue
        if p2 in ("数詞",) or p3 == "助数詞可能" or p2 == "助数詞":
            continue
        lem = f.orthBase or w.surface
        lem2 = f.lemma or lem
        if lem in FUNC_VERBS_JA or lem2 in FUNC_VERBS_JA or lem in FORMAL_NOUNS_JA or w.surface in FORMAL_NOUNS_JA:
            continue
        if p2 == "非自立可能" and p1 == "動詞":
            continue
        toks.append((w.surface, lem, lem2))
    return toks


def en_lemma(w: str) -> str:
    w = w.lower().strip("'’")
    for suf, rep in (("ies", "y"), ("ied", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: len(w) - len(suf)] + rep
    return w


def new_content_count(text: str, source: str, lang: str, extra_known=()) -> int | None:
    """依頼文＋材料に無い内容語の数。日本語で形態素解析が使えなければ None。"""
    src_n = _nfkc(source).lower()
    known = set(k.lower() for k in extra_known)
    if lang == "ja":
        src_toks = ja_content_tokens(source)
        out_toks = ja_content_tokens(text)
        if src_toks is None or out_toks is None:
            return None
        src_lem: set[str] = set()
        for t in src_toks:
            src_lem.update(t[1:])
        n = 0
        seen: set[str] = set()
        for surf, lem, lem2 in out_toks:
            if lem in META or lem2 in META or surf in META:
                continue
            if lem in src_lem or lem2 in src_lem or _nfkc(surf).lower() in src_n or _nfkc(lem).lower() in src_n:
                continue
            if any(_nfkc(surf).lower() in k or k in _nfkc(surf).lower() for k in known if k):
                continue
            if lem in seen:
                continue
            seen.add(lem)
            n += 1
        return n
    words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", _nfkc(text))
    src_lem2 = set(en_lemma(w) for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", src_n))
    n, seen2 = 0, set()
    for w in words:
        lw = w.lower()
        if lw in EN_STOP or lw in META or en_lemma(lw) in META:
            continue
        lm = en_lemma(lw)
        if lm in src_lem2 or lw in src_n:
            continue
        if any(lw in k or k in lw for k in known if k):
            continue
        if lm in seen2:
            continue
        seen2.add(lm)
        n += 1
    return n


def asked_term(brief: str) -> str | None:
    b = _nfkc(brief)
    m = re.search(r"[「『\"'“‘]([^」』\"'”’]{1,30})[」』\"'”’]", b)
    return m.group(1) if m else None


def approx_new_content(spec: dict, text: str, brief: str, materials: list[str], lang: str,
                       is_outside: bool) -> tuple[str, dict]:
    """new_content_words の近似（設計者の lenient: allowed=false は 2 語以上で FAIL、min は個数で判定）。"""
    src = brief + "\n" + "\n".join(materials)
    term = asked_term(brief) if is_outside else None
    known: list[str] = []
    if term:
        known = [term.lower()] + [term[:k].lower() for k in range(1, len(term))] + [term[k:].lower() for k in range(1, len(term))]
    n = new_content_count(text, src, lang, known)
    if n is None:
        return UNJUDGED, {"reason": "TOKENIZER_UNAVAILABLE"}
    if spec.get("allowed") is False and n >= 2:
        return FAIL, {"new_words": n}
    if spec.get("allowed") and n < (spec.get("min") or 0):
        return FAIL, {"new_words": n}
    return PASS, {"new_words": n}


def approx_haiku(form: dict, lines: list[str]) -> tuple[str, dict]:
    """設計者の check_form の haiku（仮名だけを数える。漢字は音数に数えない）。"""
    SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")

    def mora(s: str) -> int:
        return sum(1 for ch in s if re.match(r"[ぁ-んァ-ヶー]", ch) and ch not in SMALL)
    if len(lines) != 3:
        return FAIL, {"reason": "HAIKU_LINES"}
    want = form.get("mora", [5, 7, 5])
    if [mora(x) for x in lines] != want:
        return FAIL, {"reason": "MORA"}
    if form.get("script") == "hiragana":
        for x in lines:
            if re.search(r"[^ぁ-んー\s]", x):
                return FAIL, {"reason": "NON_HIRAGANA"}
    return PASS, {}

"""W16-t3 (K651): 引用の照合。LLM の答えと逐語の引用を、記録（文書の各行）と突き合わせる。読解はしない。

LLM も読解器も呼ばない純粋な関数。形態素解析は品詞を見るだけ（固有名詞の語の連続を取り出す）。
規則は docs/FUSION.md §9 に事前登録のとおり:
  - 正規化 norm = NFKC -> 連続空白を半角空白 1 つ -> 前後の空白を除く
  - 行の本文 = 同じ (source, line) の記録の文を k の順に連結（前の文が「。」で終わるなら空、でなければ半角空白 1 つ）
  - 引用の実在 = exact（指定行に部分一致）／relocated（他の行に一致。複数行なら全部を残す＝勝者を選ばない）／fabricated
  - 答えの要素 = 日付・時刻（年月日時分・曜日） -> 数値（単位つき） -> 固有名。引用から同じ関数で取り出した要素と比べる（部分一致ではない）
  - 内容語の被覆（第 3 ラウンド）= 答えの内容語（名詞・動詞・形容詞・形状詞・接頭辞・名詞的な接尾辞。非自立可能・「さん／様」・日付数値の要素の範囲は除く。数詞は除かない（R1′））が
    実在した引用の text に現れること。表層が等しい、または動詞・形容詞なら見出し語が等しい。名詞は表層だけ（固有名詞の見出し語は読み）。部分一致は使わない。問いの語は除く。
  - 第 4 ラウンド（§9.13）: R7 否定の有無（助動詞 ない・ず／形容詞 無い。有無だけ）、R8 述語の有無（動詞・形容詞、形状詞＋だ／です）、
    R9 極性 = 答えに述語があるとき、答えと各実在引用の否定の有無を比べる（規則 3d）、R10 応答の語（感動詞・動詞 違う）と問いの語の繰り返しだけの答えは確かめられない（規則 3c。§9.13c）、
    R11 選択の問い（どちら／どっち、または名詞・接尾辞の直後の か が 2 か所以上）では問いの語を被覆から除かない。
  - 第 5 ラウンド（§9.16）: R12 = 要素が無く、内容語が問いの語の繰り返しだけなら問いの語も被覆の対象に戻す。内容語が 0 個なら確かめられない（規則 3e、NO_CONTENT_TO_CHECK）
  - 印 = unanchored（引用 0／捏造あり）-> conflict（食い違い）-> unanchored（要素が引用に無い）-> unanchored（確かめる語が無い。規則 3c）
        -> unanchored（内容語が引用に無い。規則 3b）-> unanchored（確かめる中身が無い。規則 3e）-> unanchored（極性が違う。規則 3d）-> anchored
  - 文書間の食い違い (ii) = 文書（記録の source）が 1 つに決まる実在引用どうしを比べる。2 つ以上の文書に一致する引用（doc_undetermined）は、
    文書の候補の集合が交わらない引用との間でだけ比べる（R6′。交わる引用どうしは同じ文書かもしれないので比べない）
漢数字・単位の一覧は answer.py / answer_slots.py のものを使い、ここでは新しく作らない。
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import answer as _answer
from . import answer_slots as _slots

ANCHORED, UNANCHORED, CONFLICT = "anchored", "unanchored", "conflict"

# --- 単位・漢数字（既存の一覧を取り出して使う。新しく書かない） -------------------------------------------------------------------------------
_NUM = _answer._NUMBER                                   # アラビア（, 区切り・小数）と漢数字
_VALUE_PAT = _slots._VALUE.pattern
_UNIT_PAT = _VALUE_PAT[len(_NUM) + len(r"\s*"):]          # `(?:人|名|...)` 部分。同じ集合であることは tests/test_w16t3_quote_check.py で確かめる
_ARABIC = r"\d[\d,]*(?:\.\d+)?"
_KANJI = r"[〇一二三四五六七八九十百千]+"
_DATE_UNITS = "年月日時分"
_RE_DATE = re.compile(r"(?:午前|午後)?(?:(%s|%s)\s*([%s]))" % (_ARABIC, _KANJI, _DATE_UNITS))
_RE_WEEKDAY = re.compile(r"[月火水木金土日]曜日")
_RE_ARABIC_NUM = re.compile(r"(%s)(?:\s*(%s))?" % (_ARABIC, _UNIT_PAT))
_RE_KANJI_NUM = re.compile(r"(%s)\s*(%s)" % (_KANJI, _UNIT_PAT))
_RE_KATAKANA = re.compile(r"[ァ-ヶー]{2,}")
_HONORIFICS = ("さん", "様")
_DIGITS = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_POS = {"十": 10, "百": 100, "千": 1000}


def norm(s: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(s))).strip()


def kanji_to_int(s: str) -> Optional[int]:
    """漢数字を整数に。読めない並び（順序が崩れている・重複など）は None（呼び出し側が skipped に数える）。"""
    if not s:
        return None
    if all(c in _DIGITS for c in s):
        return int("".join(str(_DIGITS[c]) for c in s))
    total, cur, last = 0, None, 10 ** 6
    for c in s:
        if c in _DIGITS:
            if cur is not None:
                return None
            cur = _DIGITS[c]
        elif c in _POS:
            if _POS[c] >= last:
                return None
            total += (1 if cur is None else cur) * _POS[c]
            cur, last = None, _POS[c]
        else:
            return None
    return total + (cur or 0)


def _arabic_value(s: str) -> str:
    s = s.replace(",", "").rstrip(".")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _num_value(s: str) -> Optional[str]:
    if re.fullmatch(_ARABIC, s):
        return _arabic_value(s)
    n = kanji_to_int(s)
    return None if n is None else str(n)


def extract(text: str) -> Tuple[List[Dict[str, str]], int]:
    out, skipped, _ok, _dn = _extract(text)
    return out, skipped


def _extract(text: str) -> Tuple[List[Dict[str, str]], int, bool, List[Tuple[int, int]]]:
    """text（正規化前でよい）から要素を取り出す。-> ([{kind, value, unit}], skipped)。unit は同じ種類かどうかの鍵（日付・数値）。
    重なる範囲は 日付・時刻 -> 数値 -> 固有名 の順に先に取ったものが持つ。"""
    t = norm(text)
    taken: List[Tuple[int, int]] = []
    out: List[Dict[str, str]] = []
    skipped = 0
    tagger_ok = True

    def free(a: int, b: int) -> bool:
        return all(b <= x or y <= a for x, y in taken)

    def add(kind: str, value: str, unit: str, a: int, b: int) -> None:
        taken.append((a, b))
        if not any(e["kind"] == kind and e["value"] == value for e in out):
            out.append({"kind": kind, "value": value, "unit": unit})

    for m in _RE_DATE.finditer(t):
        v = _num_value(m.group(1))
        if v is None:
            skipped += 1
            continue
        if free(m.start(), m.end()):
            prefix = m.group(0)[:2] if m.group(0)[:2] in ("午前", "午後") else ""
            add("date", prefix + v + m.group(2), m.group(2), m.start(), m.end())
    for m in _RE_WEEKDAY.finditer(t):
        if free(m.start(), m.end()):
            add("date", m.group(0), "曜日", m.start(), m.end())
    for rx in (_RE_ARABIC_NUM, _RE_KANJI_NUM):
        for m in rx.finditer(t):
            a, b = m.start(), m.end()
            if not free(a, b):
                continue
            v = _num_value(m.group(1))
            if v is None:
                skipped += 1
                continue
            unit = m.group(2) or ""
            if rx is _RE_ARABIC_NUM and m.group(1).endswith(","):
                b -= 1                                   # 末尾の「,」は区切りでなく句読点
            add("number", v + unit, unit, a, b)
    date_num_spans = list(taken)                         # 日付・数値として取った範囲（内容語から除く）
    names, tagger_ok = _names(t)
    for value, a, b in names:
        if free(a, b):
            add("name", value, "", a, b)
    return out, skipped, tagger_ok, date_num_spans


def _tokens(text: str):
    from .typed_edges import _tagger                      # fugashi の品詞を見るだけ（読解器ではない）
    out, cursor = [], 0
    for word in _tagger()(text):
        at = text.find(word.surface, cursor)
        if at < 0:
            continue
        out.append((word, at, at + len(word.surface)))
        cursor = at + len(word.surface)
    return out


def _names(t: str) -> Tuple[List[Tuple[str, int, int]], bool]:
    """-> (固有名, 形態素解析が使えたか)。使えなかったときは品詞・「さん／様」の名前は取れない（カタカナだけ残る）ので、呼び出し側が型を付ける。"""
    found: List[Tuple[str, int, int]] = []
    tagger_ok = True
    try:
        toks = _tokens(t)
    except Exception:
        toks, tagger_ok = [], False
    i = 0
    while i < len(toks):
        w, a, b = toks[i]
        if w.feature.pos2 == "固有名詞":
            j = i
            while j + 1 < len(toks) and toks[j + 1][0].feature.pos2 == "固有名詞":
                j += 1
            found.append((t[a:toks[j][2]], a, toks[j][2]))
            i = j + 1
        else:
            i += 1
    for i, (w, a, b) in enumerate(toks):
        if w.surface in _HONORIFICS and i > 0 and toks[i - 1][0].feature.pos1 == "名詞":
            j = i - 1
            while j - 1 >= 0 and toks[j - 1][0].feature.pos1 == "名詞":
                j -= 1
            found.append((t[toks[j][1]:toks[i - 1][2]], toks[j][1], toks[i - 1][2]))
    for m in _RE_KATAKANA.finditer(t):
        found.append((m.group(0), m.start(), m.end()))
    # 重なる範囲は、開始が早く、長いものを 1 つの名前にする（位置と長さだけで決める。同じ範囲の重複は 1 つ）
    found.sort(key=lambda x: (x[1], -(x[2] - x[1])))
    out: List[Tuple[str, int, int]] = []
    for v, a, b in found:
        if out and a < out[-1][2]:
            continue
        out.append((v, a, b))
    return out, tagger_ok


# --- 内容語（第 3 ラウンド。語の一覧は作らない。品詞の属性だけで決める） --------------------------------------------------------------------------

_CONTENT_POS1 = ("名詞", "動詞", "形容詞", "形状詞", "接頭辞")
_VERBAL = ("動詞", "形容詞")


def _analyze(text: str):
    """-> ([(表層, pos1, pos2, 見出し語, 開始, 終了)], 解析できたか)。解析と属性の読み出しは同じ try の中（読めなければ False）。"""
    t = norm(text)
    try:
        out = []
        for w, a, b in _tokens(t):
            f = w.feature
            out.append((norm(w.surface), str(f.pos1), str(f.pos2), norm(f.lemma) if f.lemma else "", a, b))
        return out, True
    except Exception:
        return [], False


def _content_words(text: str, skip_spans: Sequence[Tuple[int, int]]):
    """-> ([(表層, pos1, 見出し語)], 解析できたか)。R1: 内容語の取り出し。"""
    toks, ok = _analyze(text)
    words = []
    for s, p1, p2, lem, a, b in toks:
        if p2 == "非自立可能":                            # 数詞は除かない（R1′。単位の無い漢数字の取り違えを見逃さない）
            continue
        if p1 == "接尾辞":
            if p2 != "名詞的" or s in _HONORIFICS:
                continue
        elif p1 not in _CONTENT_POS1:
            continue
        if any(a < y and x < b for x, y in skip_spans):
            continue
        words.append((s, p1, lem))
    return words, ok


def _covered(word, toks) -> bool:
    """R2: 表層が等しい語がある。動詞・形容詞だけは見出し語が等しい語でもよい。部分一致は使わない。"""
    s, p1, lem = word
    for t in toks:
        if t[0] == s:
            return True
        if p1 in _VERBAL and lem and t[3] == lem:
            return True
    return False


# --- 否定・述語・応答の語・選択の問い（第 4 ラウンド。品詞と見出し語だけで決める。語の一覧は作らない） ---------------------------------------

def _negated(toks) -> bool:
    """R7: 助動詞 ない・ず、または形容詞 無い が 1 つでもあれば真（有無だけ。接頭辞・名詞は数えない）。"""
    return any((t[1] == "助動詞" and t[3] in ("ない", "ず")) or (t[1] == "形容詞" and t[3] == "無い") for t in toks)


def _is_chigau(t) -> bool:
    return t[1] == "動詞" and t[3] == "違う"


def _predicates(toks):
    """R8: 述語の語（動詞・形容詞、形状詞の直後の だ／です）の位置の並び。"""
    out = []
    for i, t in enumerate(toks):
        if t[1] in _VERBAL or (t[1] == "助動詞" and t[3] in ("だ", "です") and i > 0 and toks[i - 1][1] == "形状詞"):
            out.append(i)
    return out


def _is_choice(qtoks) -> bool:
    """R11: どちら／どっち、または 名詞・接尾辞 の直後の助詞 か が 2 か所以上。"""
    if any(t[0] in ("どちら", "どっち") for t in qtoks):
        return True
    n = sum(1 for i in range(1, len(qtoks)) if qtoks[i][0] == "か" and qtoks[i][1] == "助詞" and qtoks[i - 1][1] in ("名詞", "接尾辞"))
    return n >= 2


# --- 記録の行 ---------------------------------------------------------------------------------------------------------------------------------

def line_bodies(records) -> Dict[Tuple[str, int], str]:
    """(source, line) -> 行の本文（同じ行の文を k の順に連結。出現順を保つ）。"""
    out: Dict[Tuple[str, int], str] = {}
    seen = set()
    for rec in records.records:
        if rec["id"] in seen:                            # 同じ id（基名が同じ別ファイル）を 2 度連結しない
            continue
        seen.add(rec["id"])
        w = records.where[rec["id"]]
        key = (w["source"], w["line"])
        if key in out:
            prev = out[key]
            out[key] = prev + ("" if prev.endswith("。") else " ") + w["text"]
        else:
            out[key] = w["text"]
    return out


def _same_source(given: str, recorded: str) -> bool:
    g, r = norm(given), norm(recorded)
    return g == r or os.path.basename(g) == os.path.basename(r)


# --- 結果 -------------------------------------------------------------------------------------------------------------------------------------

@dataclass
class QuoteCheck:
    verdict: str
    quotes: List[Dict[str, Any]]
    elements: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    reason: Optional[str] = None
    skipped: int = 0                                     # 取り出せなかった漢数字の並びの数（to_dict には入れない。型で数える）
    anchor_positions: List[str] = field(default_factory=list)   # 実在した引用の source:line（初出順・重複なし）
    uncovered: List[str] = field(default_factory=list)   # 引用に現れない答えの内容語（to_dict には入れない）
    doc_undetermined: int = 0                            # 文書が 1 つに決まらない実在引用の数（to_dict には入れない）
    polarity: Optional[Dict[str, Any]] = None            # 規則 3d: {answer_negated, quotes_negated}（to_dict には入れない）
    choice_question: bool = False                        # R11（to_dict には入れない）

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"verdict": self.verdict, "quotes": self.quotes, "elements": self.elements, "conflicts": self.conflicts}
        if self.reason is not None:
            d["reason"] = self.reason
        return d


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def check(answer: Any, quotes: Any, records, reason: Optional[str] = None, question: Optional[str] = None) -> QuoteCheck:
    bodies = line_bodies(records)
    normed = {k: norm(v) for k, v in bodies.items()}
    sources = list(dict.fromkeys(k[0] for k in bodies))
    answer_bad = not isinstance(answer, str)
    if answer_bad:
        answer, reason = "", reason or "ANSWER_NOT_A_STRING"
    if not isinstance(quotes, list):
        quotes, reason = [], reason or "QUOTES_NOT_A_LIST"
    q_out: List[Dict[str, Any]] = []
    valid: List[Tuple[List[Tuple[str, int]], List[Dict[str, str]]]] = []     # (見つかった位置, 引用から取り出した要素)
    valid_texts: List[str] = []
    skipped = 0
    tagger_down = False
    for q in quotes:
        well = isinstance(q, dict) and isinstance(q.get("source"), str) and isinstance(q.get("text"), str) and _is_int(q.get("line"))
        if not well:
            reason = reason or "BAD_QUOTE_TYPE"
            g = q if isinstance(q, dict) else {}
            q_out.append({"source": g.get("source"), "line": g.get("line"), "text": g.get("text"), "found": "fabricated"})
            continue
        item: Dict[str, Any] = {"source": q["source"], "line": q["line"], "text": q["text"]}
        nq = norm(q["text"])
        pos: List[Tuple[str, int]] = []
        found = "fabricated"
        if nq:
            hit = [s for s in sources if _same_source(q["source"], s)]
            pos = [(s, q["line"]) for s in hit if (s, q["line"]) in normed and nq in normed[(s, q["line"])]]
            if pos:
                found = "exact"
            else:
                pos = [k for k, v in normed.items() if nq in v]
                if pos:
                    found = "relocated"
                    item["relocated_to"] = ["%s:%d" % k for k in pos]
        item["found"] = found
        q_out.append(item)
        if found != "fabricated":
            els, sk, ok, _dn = _extract(q["text"])
            tagger_down = tagger_down or not ok
            skipped += sk
            valid.append((pos, els))
            valid_texts.append(q["text"])
    a_els, sk, ok, a_dn = _extract(answer)
    tagger_down = tagger_down or not ok
    skipped += sk
    elements: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    anchor: List[str] = []
    for pos, _els in valid:
        for k in pos:
            s = "%s:%d" % k
            if s not in anchor:
                anchor.append(s)
    for e in a_els:
        fin: List[str] = []
        for pos, els in valid:
            if any(x["kind"] == e["kind"] and x["value"] == e["value"] for x in els):
                for k in pos:
                    s = "%s:%d" % k
                    if s not in fin:
                        fin.append(s)
        elements.append({"kind": e["kind"], "value": e["value"], "found_in": fin or None})
        if not fin:   # (i) 答えと引用: 同じ種類（数値・日付は同じ単位）の要素が引用にあるのに、答えの値が無い
            vals = []
            for pos, els in valid:
                for x in els:
                    if x["kind"] == e["kind"] and x["unit"] == e["unit"]:
                        for k in pos:
                            v = {"value": x["value"], "source": k[0], "line": k[1]}
                            if v not in vals:
                                vals.append(v)
            if vals:
                conflicts.append({"kind": e["kind"], "answer_value": e["value"], "values": vals})
    # (ii) 文書間: 文書（source）が 1 つに決まる実在引用どうしを比べる（R6）。2 つ以上の文書に一致する引用は doc_undetermined に数え、下の R6′ でだけ比べる
    det = [(pos, els) for pos, els in valid if len({k[0] for k in pos}) == 1]
    undetermined = len(valid) - len(det)
    per_key: Dict[Tuple[str, str], Dict[str, List[str]]] = {}
    for pos, els in det:
        for x in els:
            for k in pos:
                vs = per_key.setdefault((x["kind"], x["unit"]), {}).setdefault(k[0], [])
                if x["value"] not in vs:
                    vs.append(x["value"])
    # R6′: 文書が決まらない引用は、文書の候補の集合が交わらない引用との間でだけ、同じ種類・単位の値の集合を比べる
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            (pi, ei), (pj, ej) = valid[i], valid[j]
            ci, cj = {k[0] for k in pi}, {k[0] for k in pj}
            if (len(ci) == 1 and len(cj) == 1) or (ci & cj):     # 両方が決まる組は上の per_key。交わる組は比べない
                continue
            for key in sorted({(x["kind"], x["unit"]) for x in ei} & {(x["kind"], x["unit"]) for x in ej}):
                vi = {x["value"] for x in ei if (x["kind"], x["unit"]) == key}
                vj = {x["value"] for x in ej if (x["kind"], x["unit"]) == key}
                if vi == vj:
                    continue
                vals = []
                for pos, vs in ((pi, vi), (pj, vj)):
                    for v in sorted(vs):
                        for k in pos:
                            item = {"value": v, "source": k[0], "line": k[1]}
                            if item not in vals:
                                vals.append(item)
                c = {"kind": key[0], "answer_value": None, "values": vals}
                if c not in conflicts:
                    conflicts.append(c)
    for (kind, _unit), docs in per_key.items():
        if len(docs) >= 2 and len({frozenset(v) for v in docs.values()}) > 1:
            vals = []
            for doc, vs in docs.items():
                for v in vs:
                    ln = next(k[1] for pos, els in det for k in pos if k[0] == doc and any(x["kind"] == kind and x["value"] == v for x in els))
                    vals.append({"value": v, "source": doc, "line": ln})
            conflicts.append({"kind": kind, "answer_value": None, "values": vals})
    # 規則 3b: 答えの内容語が実在した引用の text に現れるか（R1〜R4）。第 4 ラウンドの 3c・3d もここで準備する
    uncovered: List[str] = []
    no_check: Optional[str] = None
    polarity: Optional[Dict[str, Any]] = None
    choice = False
    no_content = False
    if valid and not answer_bad:
        words, ok = _content_words(answer, a_dn)
        tagger_down = tagger_down or not ok
        qtoks, ok = _analyze(question) if question else ([], True)
        tagger_down = tagger_down or not ok
        choice = _is_choice(qtoks)
        if choice:                                       # R11: 選択の問いでは問いの語を除かない
            qtoks = []
        ttoks_each: List[Any] = []
        ttoks: List[Any] = []
        for t in valid_texts:
            toks, ok = _analyze(t)
            tagger_down = tagger_down or not ok
            ttoks_each.append(toks)
            ttoks.extend(toks)
        for wd in words:
            if not _covered(wd, ttoks) and not _covered(wd, qtoks) and wd[0] not in uncovered:
                uncovered.append(wd[0])
        # R12（K654、§9.16）: 要素が無く、問いの語の繰り返しを除くと内容語も残らない答えは、問いの語の繰り返しも被覆の対象に戻す。内容語が 0 個なら確かめる語が無い
        if not a_els and all(_covered(wd, qtoks) for wd in words):
            if words:
                for wd in words:
                    if not _covered(wd, ttoks) and wd[0] not in uncovered:
                        uncovered.append(wd[0])
            else:
                no_content = True
        atoks, ok = _analyze(answer)
        tagger_down = tagger_down or not ok
        preds = _predicates(atoks)
        # 規則 3c（R10）: 要素・述語（違う 以外）が無く、内容語が 違う 以外はすべて問いの語の繰り返し（R3。選択の問いでは qtoks は空。§9.13c）で、応答の語を含む答えは、はい／いいえを確かめていない
        # （応答の語を含まない答え「そうです」は 3c の対象にしない。J-R4-1 の撤回のまま。第 5 ラウンドからは R12 (ii) -> 規則 3e で NO_CONTENT_TO_CHECK。§9.16）
        if (not a_els and not any(not _is_chigau(atoks[i]) for i in preds)
                and all((wd[1] == "動詞" and wd[2] == "違う") or _covered(wd, qtoks) for wd in words)
                and any(t[1] == "感動詞" or _is_chigau(t) for t in atoks)):
            no_check = "YESNO_NOT_CHECKED"
        # 規則 3d（R9）: 述語のある答えは、答えと各実在引用の否定の有無を比べる
        if preds:
            an = _negated(atoks)
            qn = [_negated(toks) for toks in ttoks_each]
            if any(x != an for x in qn):
                polarity = {"answer_negated": an, "quotes_negated": qn}
    if tagger_down:                                      # 固有名・内容語を照合できないので「すべて引用に現れる」を確かめられない（M1）
        reason = reason or "NAME_TAGGER_UNAVAILABLE"
    if not q_out or any(q["found"] == "fabricated" for q in q_out) or answer_bad:
        verdict = UNANCHORED
    elif conflicts:
        verdict = CONFLICT
    elif tagger_down or any(e["found_in"] is None for e in elements):
        verdict = UNANCHORED
    elif no_check:
        verdict = UNANCHORED
        reason = reason or no_check
    elif uncovered:
        verdict = UNANCHORED
    elif no_content:
        verdict = UNANCHORED
        reason = reason or "NO_CONTENT_TO_CHECK"
    elif polarity is not None:
        verdict = UNANCHORED
        reason = reason or "POLARITY_DIFFERS"
    else:
        verdict = ANCHORED
    if verdict == UNANCHORED and uncovered and not reason and not any(q["found"] == "fabricated" for q in q_out):
        reason = "ANSWER_CONTENT_NOT_IN_QUOTE:" + "、".join(uncovered)
    return QuoteCheck(verdict, q_out, elements, conflicts, reason, skipped, anchor, uncovered, undetermined, polarity, choice)

"""Skills with one right answer, by rule or arithmetic — the part of a chat Vera can do exactly.

Each skill recognises its request by form, computes the answer, and returns it with how it
was computed. A skill that does not recognise the request returns None and the chat goes on.
No model, no corpus statistics: morphology (unidic), conjugation (realize), frames, verdict."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from verantyx.typed_edges import _tagger

Z2H = str.maketrans("０１２３４５６７８９＋－×÷．", "0123456789+-*/.")
KANJI_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
WEEK = ["月", "火", "水", "木", "金", "土", "日"]
SEQS = [["春", "夏", "秋", "冬"], ["朝", "昼", "夕方", "夜"], ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"],
        ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"]]
UNITS = {  # to a base unit
    "km": ("m", 1000), "キロメートル": ("m", 1000), "メートル": ("m", 1), "m": ("m", 1), "センチメートル": ("m", 0.01),
    "cm": ("m", 0.01), "ミリメートル": ("m", 0.001), "mm": ("m", 0.001),
    "キログラム": ("g", 1000), "kg": ("g", 1000), "グラム": ("g", 1), "g": ("g", 1),
    "リットル": ("l", 1), "L": ("l", 1), "ミリリットル": ("l", 0.001), "mL": ("l", 0.001), "ml": ("l", 0.001),
    "時間": ("s", 3600), "分": ("s", 60), "秒": ("s", 1)}
UNIT_RE = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))


def _num(s: str) -> Optional[float]:
    s = s.translate(Z2H).strip()
    neg = s.startswith(("マイナス", "-"))
    s = re.sub(r"^(マイナス|-)", "", s)
    try:
        v = float(s)
    except ValueError:
        v = KANJI_NUM.get(s)
        if v is None:
            return None
    return -v if neg else v


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(round(v, 4))


def _quoted(u: str) -> Optional[str]:
    m = re.search(r"[「『](.+?)[」』]", u)
    return m.group(1) if m else None


def _hira(kata: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in kata)


def _kata(hira: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in hira)


# --- language -------------------------------------------------------------------
def kana(u: str) -> Optional[str]:
    q = _quoted(u)
    if not q:
        return None
    if re.search(r"カタカナ(に|で)", u):
        if re.search(r"[A-Za-z]", q):
            return None       # English to katakana needs a loanword dictionary; not by rule
        return _kata(q)
    if re.search(r"ひらがな(に|で)", u) and not re.search(r"読み", u):
        return _hira(q)
    return None


def reading(u: str) -> Optional[str]:
    q = _quoted(u)
    if not q or not re.search(r"[」』]の(読み|よみ)|[」』]は?(何|なん)と読", u):
        return None
    r = "".join((w.feature.kana or w.surface) for w in _tagger()(q))
    return _hira(r) if "ひらがな" in u or "カタカナ" not in u else r


def style(u: str) -> Optional[str]:
    q = _quoted(u)
    if not q:
        return None
    from verantyx.realize import conjugate
    body = q.rstrip("。")
    if re.search(r"(普通体|だ・である|常体)", u):
        if re.search(r"かったです$", body):
            return body[:-2]
        s = re.sub(r"でした$", "だった", body)
        s = re.sub(r"(い)です$", r"\1", s) if re.search(r"[いし]です$", s) and not s.endswith("でした") else s
        s = re.sub(r"です$", "だ", s)
        ws = list(_tagger()(body))
        verbs = [w for w in ws if w.feature.pos1 == "動詞"]
        if re.search(r"(ます|ました|ません|ませんでした)$", body) and verbs:
            v = verbs[-1]
            past, neg = body.endswith(("ました", "でした")), "ません" in body
            head = body[: body.rfind(v.surface)]
            return head + (conjugate(v.feature.lemma, past=past, neg=neg) or v.feature.lemma)
        return s
    if re.search(r"(丁寧体|です・ます|敬体|丁寧に)", u):
        ws = list(_tagger()(body))
        verbs = [w for w in ws if w.feature.pos1 == "動詞"]
        if verbs and ws[-1].feature.pos1 in ("動詞", "助動詞"):
            v = verbs[-1]
            past, neg = body.endswith(("た", "だ")), bool(re.search(r"ない$|なかった$", body))
            head = body[: body.rfind(v.surface)]
            dic = v.surface if v.surface[-1] in "うくぐすつぬぶむる" else v.feature.lemma
            return head + (conjugate(dic, past=past, neg=neg, polite=True) or v.surface)
        if body.endswith("だ"):
            return body[:-1] + "です"
        return body + "です"
    return None


def voice(u: str) -> Optional[str]:
    q = _quoted(u)
    if not q or not re.search(r"(能動|受動|受け身)", u):
        return None
    from verantyx.frames import read
    from verantyx.realize import conjugate
    f = read(q if q.endswith("。") else q + "。")
    if not f or not f.agent or not f.patient:
        return None
    if "能動" in u:
        return "%sが%sを%s" % (f.agent, f.patient, conjugate(f.predicate, past=True))
    return "%sは%sに%s" % (f.patient, f.agent, conjugate(f.predicate, past=True, passive=True))


def roles(u: str, context: str) -> Optional[str]:
    if not context or not re.search(r"(だれが|誰が).*(何を|なにを)", u):
        return None
    from verantyx.frames import read_all
    from verantyx.realize import conjugate
    fs = [f for f in read_all(context) if f.agent and f.patient]
    if not fs:
        return None
    qv = {w.feature.lemma for w in _tagger()(u) if w.feature.pos1 == "動詞"}
    f = next((x for x in fs if x.predicate in qv), None)
    if f is None:
        return None          # the question asks about an event the frames did not read
    past = bool(re.search(r"(た|だ)。?$", context.strip())) or "ました" in u
    return "%sが%s%sを%s" % (f.agent, (f.recipient + "に") if f.recipient else "", f.patient,
                             conjugate(f.predicate, past=past) or f.predicate)


def proper_nouns(u: str, context: str) -> Optional[str]:
    if not re.search(r"固有名詞", u):
        return None
    text = context or (_quoted(u) or "")
    out, run = [], ""
    ws = list(_tagger()(text))
    for i, w in enumerate(ws):
        if w.feature.pos2 == "固有名詞" or (run and w.surface in ("山", "川", "寺", "洋", "湖", "県", "市", "島", "駅", "海", "城")):
            run += w.surface
        else:
            if run:
                out.append(run)
            run = ""
    if run:
        out.append(run)
    return "、".join(dict.fromkeys(out)) if out else None


INTENT = [(r"何分|何時間|どのくらい(時間|かかる)", "かかる時間"), (r"何時", "時刻"), (r"何と読む|読み方", "読み方"),
          (r"なぜ|どうして", "理由"), (r"何人", "人数"), (r"いくら|何円", "値段"), (r"どちらが|どっちが", "二つの比較"),
          (r"いつ", "日時"), (r"だれ|誰", "人"), (r"どうやって|どう行けば|どうすれば", "方法・やり方"),
          (r"どこ", "場所"), (r"何個|いくつ", "数")]


def question_intent(u: str) -> Optional[str]:
    if not re.search(r"(何を知りたい|何をたずね|何を聞いて)", u):
        return None
    q = _quoted(u) or u
    for pat, what in INTENT:
        if re.search(pat, q):
            return "%sを知りたい質問です。" % what
    return None


# --- arithmetic and quantities ---------------------------------------------------
def arithmetic(u: str) -> Optional[str]:
    s = u.translate(Z2H)
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)", s)
    if m and re.search(r"(いくつ|何|=|は？|ですか)", u):
        a, op, b = float(m.group(1)), m.group(2), float(m.group(3))
        v = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else None}[op]
        return None if v is None else _fmt(v)
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    if len(nums) == 2 and re.search(r"(何個|何人|何ページ|何本|何冊|何円|いくつ|何枚|何匹|何台)", u):
        unit = re.search(r"何(個|人|ページ|本|冊|円|枚|匹|台)", u)
        unit = unit.group(1) if unit else ""
        if re.search(r"(残り|食べ|読みました|使い|あげ|減|降り|引|なくし|渡し)", u):
            return _fmt(nums[0] - nums[1]) + unit
        if re.search(r"(全部で|合わせて|あわせて|乗り|増え|もらい|買い足|加え|足す)", u):
            return _fmt(nums[0] + nums[1]) + unit
    return None


def convert(u: str) -> Optional[str]:
    s = u.translate(Z2H)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(%s)(?:\s*(\d+)\s*(%s))?\s*は\s*何\s*(%s)(?:\s*何\s*(%s))?" % (UNIT_RE, UNIT_RE, UNIT_RE, UNIT_RE), s)
    if not m:
        return None
    base, k1 = UNITS[m.group(2)]
    total = float(m.group(1)) * k1
    if m.group(3):
        total += float(m.group(3)) * UNITS[m.group(4)][1]
    t1 = m.group(5)
    if UNITS[t1][0] != base:
        return None
    if m.group(6):
        big, small = UNITS[t1][1], UNITS[m.group(6)][1]
        q, r = divmod(round(total / small), round(big / small))
        return "%d%s%d%s" % (q, t1, r, m.group(6))
    return _fmt(total / UNITS[t1][1]) + t1


def _quantity(x: str) -> Optional[tuple]:
    x = x.translate(Z2H)
    m = re.match(r"^(マイナス|-)?\s*(\d+(?:\.\d+)?)\s*(%s)?$" % UNIT_RE, x.strip())
    if not m:
        return None
    v = float(m.group(2)) * (-1 if m.group(1) else 1)
    if m.group(3):
        b, k = UNITS[m.group(3)]
        return (b, v * k)
    return ("", v)


def compare(u: str) -> Optional[str]:
    m = re.search(r"(.+?)と(.+?)(?:では|で|は)?、?どちらが(大き|小さ|長|短|重|軽|高|低|多|少|早|遅)", u)
    if not m:
        return None
    a, b = m.group(1).strip("「」 "), m.group(2).strip("「」 ")
    qa, qb = _quantity(a), _quantity(b)
    if not qa or not qb or qa[0] != qb[0]:
        return None
    bigger = m.group(3) in ("大き", "長", "重", "高", "多", "遅")
    if qa[1] == qb[1]:
        return "同じです"
    return a if (qa[1] > qb[1]) == bigger else b


def order(u: str) -> Optional[str]:
    m = re.search(r"(.+?)を(小さい|大きい|短い|長い|軽い|重い|早い|遅い|一年の|一日の|週の早い|起こる)?\s*順", u)
    if not m:
        return None
    items = [x.strip("「」 。") for x in re.split(r"[、,，]", m.group(1)) if x.strip("「」 。")]
    if len(items) < 2:
        return None
    for seq in SEQS:
        if all(any(x.startswith(s) or s.startswith(x) for s in seq) for x in items):
            pos = lambda x: next(i for i, s in enumerate(seq) if x.startswith(s) or s.startswith(x))
            return "、".join(sorted(items, key=pos))
    qs = [_quantity(x) for x in items]
    if all(qs) and len({q[0] for q in qs}) == 1:
        desc = m.group(2) in ("大きい", "長い", "重い", "遅い")
        return "、".join(x for _, x in sorted(zip([q[1] for q in qs], items), reverse=desc))
    return None


def count(u: str) -> Optional[str]:
    m = re.search(r"[「『](.+?)[」』]の中で(.+?)は何回", u)
    if m:
        items = [x.strip() for x in re.split(r"[、,]", m.group(1))]
        return "%d回" % items.count(m.group(2).strip("「」"))
    if "●" in u and re.search(r"(何個|いくつ)", u):
        return "%d個" % u.count("●")
    m = re.search(r"(\d+)から(\d+)までの(偶数|奇数)", u.translate(Z2H))
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        n = [i for i in range(a, b + 1) if (i % 2 == 0) == (m.group(3) == "偶数")]
        return "%dつ（%s）" % (len(n), "、".join(map(str, n)))
    m = re.search(r"[「『]?([^「『」』。？]+?(?:、[^「『」』。？]+?)+)[」』]?(?:の中|で挙げた|は全部で|には|のうち)", u)
    if m and re.search(r"(いくつ|何個|何種類|何日|何文字|何人|何つ)", u):
        items = [x for x in re.split(r"[、,]", m.group(1)) if x.strip()]
        unit = re.search(r"何(個|種類|日|文字|人)", u) or re.search(r"(文字)が?いくつ", u)
        return "%d%s" % (len(items), unit.group(1) if unit else "つ")
    return None


def calendar(u: str) -> Optional[str]:
    m = re.search(r"([月火水木金土日])曜日?の(次|前)の日", u)
    if m:
        i = WEEK.index(m.group(1)) + (1 if m.group(2) == "次" else -1)
        return WEEK[i % 7] + "曜日"
    m = re.search(r"今日は([月火水木金土日])曜日.*?(\d+|[一二三四五六七八九十])日(後|前)", u.translate(Z2H))
    if m:
        n = int(_num(m.group(2)))
        i = WEEK.index(m.group(1)) + (n if m.group(3) == "後" else -n)
        return WEEK[i % 7] + "曜日"
    m = re.search(r"(\d+)月(\d+)日の(次の日|(\d+)日(後|前))", u.translate(Z2H))
    if m:
        d = date(2025, int(m.group(1)), int(m.group(2)))
        k = 1 if m.group(3) == "次の日" else int(m.group(4)) * (1 if m.group(5) == "後" else -1)
        e = d + timedelta(days=k)
        return "%d月%d日" % (e.month, e.day)
    if re.search(r"1週間は何日", u.translate(Z2H)):
        return "7日"
    return None


# --- reasoning ----------------------------------------------------------------------
def syllogism(u: str, context: str) -> Optional[str]:
    text = (context or "") + u
    m1 = re.search(r"(?:すべての|全ての)?([^。、]+?)は(?:すべて|全て|全員、?)?([^。]+?)(である|だ|です|。)", text)
    rules = re.findall(r"(?:すべての|全ての)([^。、]+?)は([^。]+?)(?:である|だ|です)?。", text)
    rules += [(a, b) for a, b in re.findall(r"([^。、]+?)は(?:すべて|全て|全員、?)([^。]+?)。", text)]
    if not rules or not re.search(r"結論", u):
        return None
    for a, b in rules:
        m = re.search(r"([^。、]+?)は(?:この部屋の)?%s(?:である|だ|です|にある)?。" % re.escape(a.split("の")[-1]), text)
        if m and m.group(1) != a:
            return "%sは%s" % (m.group(1).strip(), re.sub(r"(である|だ|です)$", "", b).strip() + ("である" if not re.search(r"(る|ない|い)$", b) else ""))
    return None


def eliminate(u: str, context: str) -> Optional[str]:
    text = (context or "") + "。" + u
    a = b = None
    for sent in re.split(r"。", text):
        mm = re.search(r"(.+?)の?どちらか|(.+?)だけ", sent)
        if not mm:
            continue
        head = mm.group(1) or mm.group(2)
        ws = list(_tagger()(head))
        # the two options are the noun runs joined by the particle か (or と before だけ)
        joiner = "か" if mm.group(1) else "と"
        idx = [i for i, w in enumerate(ws) if w.surface == joiner and w.feature.pos1 == "助詞"]
        if not idx:
            continue
        k = idx[-1]
        left, right = [], []
        for w in reversed(ws[:k]):
            if w.feature.pos1 in ("名詞", "接頭辞", "接尾辞") or w.surface == "の":
                left.insert(0, w.surface)
            else:
                break
        for w in ws[k + 1:]:
            if w.feature.pos1 in ("名詞", "接頭辞", "接尾辞") or w.surface == "の":
                right.append(w.surface)
            else:
                break
        a, b = "".join(left).strip("の"), "".join(right).strip("の")
        m = mm
        break
    if not a or not b:
        return None
    rest = text[text.find(b) + len(b):]
    neg = r"(ない|なかった|いない|空|2位|違う|ではない|入っていない)"
    for x, y in ((a, b), (b, a)):
        if re.search(re.escape(x) + r"[^。]*?" + neg, rest):
            return y
    return None
    b = b
    neg = r"(ない|なかった|いない|空|2位|違う|ではない|入っていない)"
    for x, y in ((a, b), (b, a)):
        if re.search(re.escape(x) + r"[^。]*?" + neg, text[m.end():]):
            return y
    return None


def contradiction(u: str) -> Optional[str]:
    if not re.search(r"矛盾", u):
        return None
    q = _quoted(u)
    if not q:
        return None
    parts = [p + "。" for p in q.split("。") if p.strip()]
    if len(parts) != 2:
        return None
    from verantyx.verdict import judge, read_records
    v = judge(read_records(parts[0]), parts[1])["verdict"]
    if v == "CONTRADICTED":
        return "はい、矛盾しています。"
    if v in ("SUPPORTED", "NOT_IN_DOCS", "DIFFERENT"):
        return "いいえ、矛盾していません。"
    return None


SKILLS: List[Callable[..., Optional[str]]] = [kana, reading, style, voice, question_intent, arithmetic, convert,
                                              compare, order, count, calendar, contradiction]
CTX_SKILLS = [roles, proper_nouns, syllogism, eliminate]


def answer(u: str, context: str = "") -> Optional[Dict[str, Any]]:
    for f in CTX_SKILLS:
        try:
            r = f(u, context)
        except Exception:
            r = None
        if r:
            return {"text": r, "kind": "skill", "skill": f.__name__}
    for f in SKILLS:
        try:
            r = f(u)
        except Exception:
            r = None
        if r:
            return {"text": r, "kind": "skill", "skill": f.__name__}
    return None

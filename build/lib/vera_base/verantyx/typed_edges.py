"""Typed edges — the relation a sentence wrote, not just that it wrote two words.

PREREGISTERED_2026-09-27_typed_edges fixes the rules and the pass lines; this
file only implements them. Every rule reads POSITION (the one reading that
survived four polarity failures), one sentence at a time, with fugashi:

    属性   形容詞(連体形) / 形状詞+な  directly before a noun
                                    酸っぱいレモン -> レモン ─属性→ 酸っぱい
    属性   noun + が/は, then the clause predicate is an adjective
                                    氷は冷たい     -> 氷 ─属性→ 冷たい
    格     noun + が/を/に/で, then the first verb
                                    雪を握る       -> 握る ─を→ 雪

Negation right after the predicate (ない / ず / ぬ / ません) is kept as the
edge's polarity and counted apart from the positive — absence of a negative
is never read as a positive, and a written negative is never dropped.

Each edge carries its source, so evidence is counted as DISTINCT sources.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

CASES = ("が", "を", "に", "で")
_NEG_LEMMA = {"ない", "無い", "ず", "ぬ"}


@dataclass(frozen=True)
class Edge:
    head: str      # 属性: the noun   / 格: the verb
    rel: str       # 属性 | が | を | に | で
    dep: str       # 属性: the adjective / 格: the noun
    pol: str       # "+" | "-"
    mod: str = "assert"   # assert | quote | hedge | cond_if | cond_then
    ev: int = -1          # predicate position: edges sharing it are ONE event
    past: bool = False    # the predicate's clause is past tense (an episode)

    def as_tuple(self) -> Tuple[str, str, str, str]:
        return (self.head, self.rel, self.dep, self.pol)


# Modality (repair round 1, after the first P1 sheet). A sentence can write
# a relation without asserting it:
#   quote      「…」と言った / …と思う — what is established is the saying
#   hedge      …かもしれない / だろう / らしい — not asserted
#   cond_if    the antecedent of たら / ば / なら / と(接続) — not asserted
#   cond_then  the consequent of a conditional. With a PAST main verb it is
#              a narrated event (握ったら冷えた) and becomes assert; with a
#              non-past one it is a rule (洗うと落ちる) — that is what a
#              commonsense question asks, so ask_property accepts it; it is
#              still never an event that happened (承認されたら渡す).
_QUOTE_VERBS = {"言う", "思う", "考える", "書く", "話す", "述べる", "聞く",
                "語る", "信じる", "感じる", "叫ぶ", "答える", "尋ねる", "いう"}
_HEDGE = {"かもしれない", "だろう", "でしょう", "らしい", "ようだ", "みたいだ",
          "そうだ"}
ANSWERABLE = ("assert", "cond_then")


_TAGGER = None


def _tagger():
    global _TAGGER
    if _TAGGER is None:
        import fugashi

        _TAGGER = fugashi.Tagger()
    return _TAGGER


def _base(tok) -> str:
    return getattr(tok.feature, "orthBase", None) or tok.surface


def _negated(toks: Sequence[Any], i: int) -> bool:
    """Is the predicate at i negated by what follows it (same bunsetsu)?"""
    j = i + 1
    while j < len(toks):
        t = toks[j]
        p = t.feature.pos1
        lem = getattr(t.feature, "lemma", "") or ""
        base = _base(t)
        if p == "助動詞" or (p == "形容詞" and t.feature.pos2 == "非自立可能") \
                or (p == "動詞" and t.feature.pos2 == "非自立可能") \
                or (p == "助詞" and t.surface in ("て", "は", "も")):
            if base in _NEG_LEMMA or lem in _NEG_LEMMA or t.surface == "ん":
                return True
            j += 1
            continue
        break
    return False


def _auxiliary(toks: Sequence[Any], i: int) -> bool:
    """A 非自立可能 verb is an auxiliary only right after て/で (ている,
    ておく, てみる) or after a サ変 noun it completes (承認される). Read by
    POSITION: unidic tags 置く in 置いていた as 非自立可能 too, and skipping it
    handed 窓辺に to the next verb (P1 sheet, item 1)."""
    t = toks[i]
    if t.feature.pos2 != "非自立可能":
        return False
    if i == 0:
        return False
    prev = toks[i - 1]
    if prev.feature.pos1 == "助詞" and prev.surface in ("て", "で"):
        return True
    if _base(t) in ("する", "できる") and prev.feature.pos1 == "名詞":
        return False   # サ変: handled as one verb by the caller
    return _base(t) in ("しれる",)


def _simile_after(toks: Sequence[Any], k: int) -> bool:
    """黒い鏡のように / 白い雪みたいな: the noun is a comparison, not a thing."""
    nxt = [t.surface for t in toks[k:k + 2]]
    return (nxt[:1] == ["の"] and len(nxt) > 1 and nxt[1] in ("よう", "ような"))\
        or (nxt[:1] and nxt[0] in ("みたい", "よう"))


def _noun_run(toks: Sequence[Any], i: int) -> Tuple[str, int]:
    """The noun compound starting at i, and the index after it."""
    parts = []
    while i < len(toks) and (toks[i].feature.pos1 == "名詞"
                             or (parts and toks[i].feature.pos1 == "接尾辞")):
        parts.append(toks[i].surface)
        i += 1
    return "".join(parts), i


def extract(sentence: str) -> List[Edge]:
    """Edges with modality. See _modality for the clause rules."""
    toks = list(_tagger()(sentence or ""))
    return _modality(toks, _extract(toks))


def _clause_end(toks: Sequence[Any], i: int) -> Tuple[str, int]:
    """What closes the clause whose predicate sits at i."""
    j = i + 1
    past = False
    while j < len(toks):
        t = toks[j]
        f = t.feature
        b = _base(t)
        if f.pos1 == "助動詞" and b == "た" and str(f.cForm).startswith("仮定形"):
            return "cond", j
        if f.pos1 == "助詞" and t.surface in ("ば", "なら", "ても", "でも"):
            return "cond", j
        if f.pos1 == "助詞" and t.surface == "と" and j + 1 < len(toks) \
                and toks[j + 1].feature.pos1 == "動詞" \
                and _base(toks[j + 1]) in _QUOTE_VERBS:
            return "quote", j
        if f.pos1 == "助詞" and t.surface == "と":
            # 接続の と after a plain-form predicate: 洗うと落ちる.
            return "cond", j
        if f.pos1 == "助動詞" and b == "た":
            past = True
        if f.pos1 in ("助動詞",) or (f.pos1 == "助詞" and t.surface in ("て", "も", "か")) \
                or (f.pos1 == "動詞" and f.pos2 == "非自立可能") \
                or (f.pos1 == "形容詞" and f.pos2 == "非自立可能"):
            j += 1
            continue
        break
    tail = "".join(x.surface for x in toks[i + 1:min(len(toks), i + 8)])
    if tail.startswith(("よう", "みたい")) or \
            (j < len(toks) and toks[j].surface in ("よう", "ような", "みたい")):
        return "simile", j
    if any(h in tail for h in ("かもしれ", "だろう", "でしょう", "らしい", "ようだ", "みたい")):
        return "hedge", j
    return ("past" if past else "plain"), j


def _modality(toks: Sequence[Any], edges: List[Tuple[int, Edge]]) -> List[Edge]:
    # Predicates in order, with how their clause ends.
    preds = sorted({i for i, _ in edges})
    kinds = {i: _clause_end(toks, i)[0] for i in preds}
    # Quote spans: 「…」と言う, or everything before …と言う in the sentence.
    quoted = set()
    opened = None
    for k, t in enumerate(toks):
        if t.surface == "「":
            opened = k
        elif t.surface == "」" and opened is not None:
            if k + 2 < len(toks) and toks[k + 1].surface == "と" \
                    and _base(toks[k + 2]) in _QUOTE_VERBS | {"いう"}:
                quoted.update(range(opened, k))
            opened = None
    # Conditional markers are found over EVERY predicate, not only the ones
    # that carried an edge: 承認されたら has no argument and still makes the
    # rest of the sentence conditional.
    all_preds = [k for k, t in enumerate(toks)
                 if t.feature.pos1 in ("動詞", "形容詞") and not _auxiliary(toks, k)]
    ends = {k: _clause_end(toks, k) for k in all_preds}
    conds = [ends[k][1] for k in all_preds if ends[k][0] == "cond"]
    has_cond = bool(conds)
    last_cond = max(conds) if conds else -1
    main = max(all_preds) if all_preds else -1
    main_past = ends.get(main, ("",))[0] == "past"
    out: List[Edge] = []
    for i, e in edges:
        k = kinds[i]
        if i in quoted or k == "quote":
            mod = "quote"
        elif k in ("hedge", "simile"):
            mod = k
        elif k == "cond" or (has_cond and i < last_cond):
            mod = "assert" if main_past else "cond_if"
        elif has_cond:
            mod = "assert" if main_past else "cond_then"
        else:
            mod = "assert"
        out.append(Edge(e.head, e.rel, e.dep, e.pol, mod, i, k == "past"))
    return out


def _extract(toks: Sequence[Any]) -> List[Tuple[int, Edge]]:
    out: List[Tuple[int, Edge]] = []
    pending: List[Tuple[str, str]] = []   # (case_or_topic, noun) since last predicate
    run: List[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        f = t.feature
        p = f.pos1
        if p == "名詞" or (p == "接尾辞" and run):
            run.append(t.surface)
            i += 1
            continue
        noun = "".join(run)
        # 1: noun + だ/で/です is a noun predicate (冬は寒冷で、). It closes the
        # clause, so the topic cannot bleed onto the next clause's predicate.
        if noun and p == "助動詞" and _base(t) in ("だ", "です") \
                and not str(f.cForm).startswith("連体形"):
            # 「XはYだ」: keep the copula as its own relation (同) — what
            # figurative.py reads for 彼の心は氷だ. Never used by answers.
            pol = "-" if _negated(toks, i) else "+"
            for c, n in pending:
                if c in ("は", "が") and n != noun:
                    out.append((i, Edge(n, "同", noun, pol)))
            pending = []
            run = []
            i += 1
            continue
        run = []
        if p == "助詞" and (t.surface in CASES or t.surface == "は"):
            if noun:
                pending.append((t.surface, noun))
            i += 1
            continue
        # 連体: adjective / 形状詞+な directly before a noun.
        if p == "形容詞" and f.pos2 != "非自立可能" and str(f.cForm).startswith("連体形"):
            nxt, k = _noun_run(toks, i + 1)
            if nxt and _simile_after(toks, k):
                i += 1
                continue
            if nxt:
                out.append((i, Edge(nxt, "属性", _base(t), "+")))
                i += 1
                continue
        if p == "形状詞" and i + 1 < len(toks) and toks[i + 1].surface == "な":
            nxt, k = _noun_run(toks, i + 2)
            if nxt and _simile_after(toks, k):
                i += 2
                continue
            if nxt:
                out.append((i, Edge(nxt, "属性", _base(t), "+")))
                i += 2
                continue
        # 2: adverbial use modifies the verb, it is not a property of the
        # subject — 静かに押し出す, 黒く汚れて. 連用形 + なる/ない/て/た stays a
        # predicate (暗くなる, 冷たくない).
        nx = toks[i + 1] if i + 1 < len(toks) else None
        if p == "形状詞" and nx is not None and _base(nx) == "だ" \
                and str(nx.feature.cForm).startswith("連用形-ニ"):
            i += 2
            continue
        if p == "形容詞" and f.pos2 != "非自立可能" and str(f.cForm).startswith("連用形") \
                and nx is not None and nx.feature.pos1 == "動詞" \
                and _base(nx) not in ("なる", "ある", "いる"):
            i += 1
            continue
        # Predicate adjective closes the clause: subject(が/は) ─属性→ adj.
        if (p == "形容詞" and f.pos2 != "非自立可能") or \
                (p == "形状詞" and i + 1 < len(toks)
                 and _base(toks[i + 1]) in ("だ", "です")):
            pol = "-" if _negated(toks, i) else "+"
            for c, n in pending:
                if c in ("が", "は"):
                    out.append((i, Edge(n, "属性", _base(t), pol)))
            pending = []
            i += 1
            continue
        if p == "動詞" and not _auxiliary(toks, i):
            verb = _base(t)
            # サ変: noun immediately before する is one verb (存在する).
            if verb in ("する", "できる") and noun:
                verb = noun + verb
            pol = "-" if _negated(toks, i) else "+"
            for c, n in pending:
                # は is kept as its own relation: topic, subject OR object
                # (申請は受け付けない). ask_property reads が only, so the
                # commonsense rule is unchanged; verify matches は both ways.
                if c in CASES or c == "は":
                    out.append((i, Edge(verb, c, n, pol)))
            pending = []
            i += 1
            continue
        if p == "補助記号" and t.surface in ("。", "「", "」", "『", "』"):
            # a quotation opens a new speaker's clause: nothing outside it
            # is the subject of a predicate inside it (部長は「…不要だ」と言った)
            pending = []
        i += 1
    return out


# --- is-a -------------------------------------------------------------------

_CLASSIFIERS = {"一種", "一つ", "ひとつ", "総称", "仲間", "種類", "名称", "グループ",
                "一群", "一品種", "品種", "一部"}


def isa(sentence: str) -> List[Tuple[str, str]]:
    """「XはYである / Yの一種 / …Y。」 — X is the topic noun at the head of
    the sentence, Y the head of the predicate noun phrase. Returns (X, Y) and,
    when Y ends in the class suffix 類 (鳥類, 魚類), also (X, Y minus 類)."""
    toks = list(_tagger()(sentence or ""))
    x, k = _noun_run(toks, 0)
    if not x or k >= len(toks) or toks[k].surface != "は":
        return []
    # the predicate: last noun run before である/だ/です/。 or before の一種
    end = len(toks)
    while end > 0 and toks[end - 1].feature.pos1 in ("補助記号",):
        end -= 1
    tail = [t.surface for t in toks[max(0, end - 3):end]]
    j = end
    if tail[-2:] == ["で", "ある"] or (tail and tail[-1] in ("だ", "です")):
        j = end - (2 if tail[-2:] == ["で", "ある"] else 1)
    body = toks[k + 1:j]
    # 〜の一種 / 〜の一つ: Y is the noun run before の
    # 〜の一種 / 〜の総称 / 〜の仲間: a classifier noun names no class of its
    # own; the class is the noun run before の (魚の総称 -> 魚).
    for n in range(len(body) - 2, 0, -1):
        if body[n].surface == "の" and "".join(t.surface for t in body[n + 1:]) in _CLASSIFIERS:
            body = body[:n]
            break
    y_parts = []
    for t in reversed(body):
        if t.feature.pos1 == "名詞" or (t.feature.pos1 == "接尾辞" and y_parts is not None):
            y_parts.insert(0, t.surface)
        else:
            break
    y = "".join(y_parts)
    if not y or y == x or len(y) < 1:
        return []
    out = [(x, y)]
    if y.endswith("類") and len(y) >= 2:
        out.append((x, y[:-1]))
    return out


# --- store ------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS tedges (head TEXT, rel TEXT, dep TEXT, pol TEXT,
                                   src TEXT, sha TEXT, mod TEXT, ev INTEGER,
                                   past INTEGER);
CREATE INDEX IF NOT EXISTS ix_head ON tedges(head, rel);
CREATE INDEX IF NOT EXISTS ix_dep ON tedges(dep, rel);
CREATE TABLE IF NOT EXISTS tsent (sha TEXT PRIMARY KEY, text TEXT, src TEXT,
                                  n_edges INTEGER);
CREATE TABLE IF NOT EXISTS isa (x TEXT, y TEXT, src TEXT, sha TEXT);
CREATE INDEX IF NOT EXISTS ix_isa ON isa(x);
"""


def build(db: Path, rows: Iterable[Tuple[str, str, str]]) -> Dict[str, int]:
    """rows: (sha, text, src). Idempotent per sha."""
    con = sqlite3.connect(str(db))
    con.executescript(SCHEMA)
    seen = {r[0] for r in con.execute("SELECT sha FROM tsent")}
    n_s = n_e = n_hit = 0
    batch_e: List[Tuple] = []
    batch_s: List[Tuple] = []
    batch_i: List[Tuple] = []
    for sha, text, src in rows:
        if sha in seen:
            continue
        seen.add(sha)
        es = extract(text)
        n_s += 1
        n_hit += bool(es)
        n_e += len(es)
        batch_s.append((sha, text, src, len(es)))
        batch_i.extend((x, y, src, sha) for x, y in isa(text))
        batch_e.extend(e.as_tuple() + (src, sha, e.mod, e.ev, int(e.past))
                       for e in es)
        if len(batch_s) >= 5000:
            con.executemany("INSERT INTO tsent VALUES (?,?,?,?)", batch_s)
            con.executemany("INSERT INTO tedges VALUES (?,?,?,?,?,?,?,?,?)", batch_e)
            con.executemany("INSERT INTO isa VALUES (?,?,?,?)", batch_i)
            con.commit()
            batch_s, batch_e, batch_i = [], [], []
    con.executemany("INSERT INTO tsent VALUES (?,?,?,?)", batch_s)
    con.executemany("INSERT INTO tedges VALUES (?,?,?,?,?,?,?,?,?)", batch_e)
    con.executemany("INSERT INTO isa VALUES (?,?,?,?)", batch_i)
    con.commit()
    con.close()
    return {"sentences": n_s, "with_edge": n_hit, "edges": n_e}


def _src_group(src: str) -> str:
    """Independence unit: a Codex batch, or a source document."""
    return src


#: Closed two-pole axes (追記2). A property question is answered by which pole
#: the subject's own sentences hold, not by whether the asked pole was ever
#: written: 厚い紙 exists, and paper is still thin (薄い 255 : 厚い 42).
POLES = [
    (("熱", "暑", "温", "暖"), ("冷", "寒", "涼")),
    (("厚",), ("薄",)),
    (("重い", "重た"), ("軽",)),
    (("硬", "固"), ("柔", "やわらか", "軟")),
    (("明る",), ("暗",)),
    (("白",), ("黒",)),
    (("甘",), ("苦", "酸っぱ", "すっぱ", "辛", "しょっぱ", "塩辛")),
    (("静",), ("うるさ", "騒")),
    (("丸",), ("鋭", "尖")),
]
RATIO = 3


def axis_hit(word: str, axis: Sequence[str]) -> bool:
    """A word carries the axis only if it is short around it: 浮く yes,
    浮かび上がる / 浮彫りする no (評価用バンク1, cause 2)."""
    return any(a in word and len(word) <= len(a) + 3 for a in axis)


def _opposite(axis: Sequence[str]) -> List[str]:
    for a, b in POLES:
        if any(x.startswith(y) or y.startswith(x) for x in axis for y in a):
            return list(b)
        if any(x.startswith(y) or y.startswith(x) for x in axis for y in b):
            return list(a)
    return []


def ask_property(db: Path, subject: str, axis: Sequence[str],
                 min_sources: int = 2) -> Dict[str, Any]:
    """「XはPですか」 by the preregistered rule. Returns a typed verdict."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        # A past negative is one episode that did not happen (本がほとんど
        # 読めていなかった) — it does not deny the kind. Negatives count only
        # when non-past; positives count either way (it happened, so it can).
        "SELECT dep, pol, src, sha FROM tedges WHERE head=? AND rel='属性' "
        "AND mod IN ('assert','cond_then') AND NOT (pol='-' AND past=1) "
        "UNION ALL "
        "SELECT head, pol, src, sha FROM tedges WHERE dep=? AND rel='が' "
        "AND mod IN ('assert','cond_then') AND NOT (pol='-' AND past=1)",
        (subject, subject)).fetchall()
    hits = [(w, pol, src, sha) for w, pol, src, sha in rows
            if axis_hit(w, axis)]
    pos = {_src_group(s) for w, pol, s, _ in hits if pol == "+"}
    neg = {_src_group(s) for w, pol, s, _ in hits if pol == "-"}
    opp_axis = _opposite(axis)
    if opp_axis:
        opp = {_src_group(s) for w, pol, s, _ in rows
               if pol == "+" and axis_hit(w, opp_axis)} | neg
        np_, no_ = len(pos), len(opp)
        con.close()
        if np_ >= min_sources and np_ >= RATIO * no_:
            v = "ATTESTED"
        elif no_ >= min_sources and no_ >= RATIO * np_:
            v = "NEGATIVE_ATTESTED"
        elif np_ or no_:
            v = "CONFLICT"
        else:
            v = "NOT_ATTESTED"
        return {"verdict": v, "subject": subject, "pos_sources": np_,
                "neg_sources": no_, "pole": opp_axis, "evidence": [
                    {"word": w, "pol": pol, "src": s, "text": ""}
                    for w, pol, s, _ in hits[:3]]}
    ex = []
    for w, pol, s, sha in hits[:3]:
        r = con.execute("SELECT text FROM tsent WHERE sha=?", (sha,)).fetchone()
        ex.append({"word": w, "pol": pol, "src": s, "text": r[0] if r else ""})
    con.close()
    if neg:
        v = "CONFLICT" if pos else "NEGATIVE_ATTESTED"
    elif len(pos) >= min_sources:
        v = "ATTESTED"
    else:
        v = "NOT_ATTESTED"
    return {"verdict": v, "subject": subject, "pos_sources": len(pos),
            "neg_sources": len(neg), "evidence": ex}


DECISIVE = ("ATTESTED", "NEGATIVE_ATTESTED")


def hypernyms(isa_db: Path, x: str, min_sources: int = 2) -> List[Tuple[str, int]]:
    con = sqlite3.connect(f"file:{isa_db}?mode=ro", uri=True)
    rows = con.execute("SELECT y, count(DISTINCT src) n FROM isa WHERE x=? "
                       "GROUP BY y HAVING n>=? ORDER BY n DESC, y",
                       (x, min_sources)).fetchall()
    con.close()
    return [(y, n) for y, n in rows]


def ask_inherit(db: Path, isa_db: Path, subject: str, axis: Sequence[str]
                ) -> Dict[str, Any]:
    """追記3: X's own decisive answer first; otherwise one hop up, unless X
    holds ANY contrary evidence (the exception guard: ペンギンは飛べない)."""
    own = ask_property(db, subject, axis)
    if own["verdict"] in DECISIVE:
        return own
    if own["neg_sources"] > 0 or own["verdict"] == "CONFLICT":
        return {**own, "inherit": "BLOCKED_BY_OWN_CONTRARY_EVIDENCE"}
    ups = hypernyms(isa_db, subject)
    got = []
    for y, n in ups:
        r = ask_property(db, y, axis)
        if r["verdict"] in DECISIVE:
            got.append((y, n, r["verdict"], r["pos_sources"], r["neg_sources"]))
    verdicts = {g[2] for g in got}
    if len(verdicts) == 1:
        v = verdicts.pop()
        return {"verdict": "INHERITED_" + ("YES" if v == "ATTESTED" else "NO"),
                "subject": subject, "via": got, "pos_sources": own["pos_sources"],
                "neg_sources": own["neg_sources"], "evidence": []}
    return {**own, "inherit": "HYPERNYMS_SPLIT" if got else
            ("NO_HYPERNYM" if not ups else "HYPERNYM_UNDECIDED"), "ups": ups[:5]}


def regression() -> Dict[str, Any]:
    def has(s, e):
        return e in [x.as_tuple() for x in extract(s)]
    checks = {
        "attr_rentai": has("酸っぱいレモンをかじった。", ("レモン", "属性", "酸っぱい", "+")),
        "attr_pred": has("氷は冷たい。", ("氷", "属性", "冷たい", "+")),
        "attr_neg": has("氷は冷たくない。", ("氷", "属性", "冷たい", "-")),
        "keiyodoshi": has("静かな部屋で本を読む。", ("部屋", "属性", "静か", "+")),
        "case_wo": has("静かな部屋で本を読む。", ("読む", "を", "本", "+")),
        "case_de": has("静かな部屋で本を読む。", ("読む", "で", "部屋", "+")),
        "clause_split": has("雪を握ったら手のひらがじんと冷えた。", ("冷える", "が", "手のひら", "+"))
                        and not has("雪を握ったら手のひらがじんと冷えた。", ("冷える", "を", "雪", "+")),
        "verb_neg": has("赤信号では車が進まない。", ("進む", "が", "車", "-")),
        "aux_not_skipped": has("窓辺に置いていた本は湿気を吸った。", ("置く", "に", "窓辺", "+"))
                           and not has("窓辺に置いていた本は湿気を吸った。", ("吸う", "に", "窓辺", "+")),
    }
    def mod(s, head, rel, dep):
        return [e.mod for e in extract(s) if (e.head, e.rel, e.dep) == (head, rel, dep)]
    checks["quote"] = mod("花子は「太郎に資料Aを渡した」と言った。", "渡す", "に", "太郎") == ["quote"]
    checks["cond_if"] = mod("承認されたら、花子が資料Aを渡す。", "渡す", "が", "花子") == ["cond_then"]
    checks["rule"] = mod("汚れは洗うと落ちる。", "落ちる", "が", "汚れ") in (["cond_then"], [])
    checks["narrated_past"] = mod("雪を握ったら手のひらがじんと冷えた。", "冷える", "が", "手のひら") == ["assert"]
    checks["hedge"] = mod("雨が降るかもしれない。", "降る", "が", "雨") == ["hedge"]
    checks["past_neg_is_episode"] = [e.past for e in extract(
        "持ってきた本がほとんど読めていなかった。") if e.pol == "-"] == [True]
    checks["clause_closed"] = not has("冬は寒冷で、夏は暑い。", ("冬", "属性", "暑い", "+"))
    checks["adverbial"] = not has("朝の太鼓は、町を静かに押し出す。", ("太鼓", "属性", "静か", "+")) \
        and not has("昨夜の雪が黒く汚れて残っている。", ("雪", "属性", "黒い", "+"))
    checks["becomes_kept"] = has("日没で空が暗くなる。", ("空", "属性", "暗い", "+"))
    checks["simile"] = mod("揺れる水が一瞬だけ燃えるように見えた。", "燃える", "が", "水") == ["simile"]
    checks["suffix"] = has("甘いレモン水を飲んだ。", ("レモン水", "属性", "甘い", "+"))
    checks["isa_ichishu"] = ("スズメ", "鳥類") in isa("スズメはスズメ目スズメ科に分類される鳥類の一種である。") \
        and ("スズメ", "鳥") in isa("スズメはスズメ目スズメ科に分類される鳥類の一種である。")
    checks["isa_classifier"] = ("マグロ", "魚") in isa("マグロはサバ科マグロ属に分類される魚の総称である。")
    checks["isa_taigen"] = ("杉", "常緑針葉樹") in isa("杉はヒノキ科スギ亜科スギ属の常緑針葉樹。")
    checks["noun_simile"] = not has("黒い鏡のように光る塀。", ("鏡", "属性", "黒い", "+"))
    checks["mieru_simile"] = mod("遠くの岩が水に浮いているように見えた。", "浮く", "が", "岩") == ["simile"]
    checks["axis_len"] = axis_hit("浮く", ["浮"]) and not axis_hit("浮かび上がる", ["浮"])
    checks["quote_boundary"] = not has("部長は「交通費は申請不要だ」と言った。", ("部長", "属性", "不要", "+"))
    checks["neg_kept"] = [e.pol for e in extract("花子は太郎に資料Aを渡していない。")
                          if e.rel == "に"] == ["-"]
    return {"all_pass": all(checks.values()), **checks}

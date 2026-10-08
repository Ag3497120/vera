"""Metaphor meanings, commonsense outcomes and simple creative forms — from the Japanese corpus only.

Every answer is counted from the store (distinct sources) and says so. Nothing is trained.
    metaphor   「AはBだ」「Bのような」: B's attributes (>= 2 sources) that the corpus also gives
               to A (or to a person when A is a person or a heart), strongest first
    effect     「Xを〜すると」: the then-clause the corpus writes most after that if-clause
    pun        a predicate whose reading shares the topic word's reading (morae), 「XがY」
    haiku      phrases grounded in the corpus fitted to 5-7-5 morae, counted after writing
    story      three events of one topic, each written by >= 2 sources: setting, event, ending"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from verantyx.typed_edges import _tagger

import os
GENERAL = Path(os.environ.get("VERA_GENERAL", Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"))
PUN_LEXICON = Path(os.environ.get("VERA_PUN_LEXICON", GENERAL.with_name("pun_lexicon.json")))
PERSONISH = ("心", "声", "言葉", "顔", "目", "笑顔", "性格", "態度", "人", "彼", "彼女", "あの子", "先生", "母", "父")
COLOR = {"白い", "黒い", "赤い", "青い", "黄色い", "緑", "茶色い"}


@lru_cache(maxsize=1)
def _con():
    return sqlite3.connect(f"file:{GENERAL}?mode=ro", uri=True, check_same_thread=False)


def attrs(noun: str, k: int = 12) -> List[tuple]:
    return _con().execute("SELECT dep, count(DISTINCT src) n FROM tedges WHERE head=? AND rel='属性' AND pol='+' "
                          "GROUP BY dep HAVING n>=2 ORDER BY n DESC LIMIT ?", (noun, k)).fetchall()


def kana(text: str) -> str:
    return "".join((w.feature.kana or w.surface) for w in _tagger()(text))


def morae(text: str) -> int:
    k = kana(text)
    return sum(1 for c in k if c not in "ャュョァィゥェォ" and ("ァ" <= c <= "ヶ" or c == "ー"))


# --- metaphor --------------------------------------------------------------------
def metaphor(u: str) -> Optional[Dict]:
    m = re.search(r"[「『]?(.+?)は(.+?)(?:のようだ|のようです|みたいだ|だ|です)[」』]?", u)
    sim = re.search(r"(.+?)は(.+?)のように(.+?)[」』]", u)
    if not m:
        return None
    a, b = m.group(1).strip("「『 "), m.group(2).strip("「『 ")
    b = re.split(r"の(?!よう)", b)[-1]
    a_head = re.split(r"の", a)[-1]
    battr = [(w, n) for w, n in attrs(b, 40) if w not in COLOR]
    if not battr:
        return None
    target = a_head if a_head in PERSONISH or not re.search(r"[ァ-ヶ]", a_head) else "人"
    aset = {w for w, _ in attrs(target, 40)} | ({w for w, _ in attrs("人", 60)} if a_head in PERSONISH or target == "人" else set())
    fit = [(w, n) for w, n in battr if w in aset]
    pick = fit[:2] or battr[:1]
    words = "・".join(w for w, _ in pick)
    return {"text": "「%s」は、%sが%sのように%sという意味だと読みました（%sについての出典: %s）。" % (
        m.group(0).strip("「」"), a, b, words, b, "、".join("%s %d件" % (w, n) for w, n in pick)),
        "kind": "metaphor_meaning"}


# --- commonsense ------------------------------------------------------------------
def effect(u: str) -> Optional[Dict]:
    m = re.search(r"(.+?)[をが](.+?)(?:と|たら|れば|ば)、?(?:どう|何が)", u)
    if not m:
        return None
    x = re.split(r"[、は]", m.group(1))[-1]
    vs = [w.feature.lemma for w in _tagger()(m.group(2)) if w.feature.pos1 == "動詞"]
    if not vs:
        return None
    v = vs[0]
    # sentences that contain the action on X and say what X then does (X as subject of another predicate)
    rows = _con().execute(
        "SELECT t2.head, '', '', t2.src FROM tedges t1 JOIN tedges t2 ON t1.sha=t2.sha "
        "WHERE t1.head=? AND t1.dep=? AND t1.rel IN ('を','が') AND t2.dep=? AND t2.rel='が' AND t2.head<>? "
        "AND t2.pol='+' LIMIT 3000", (v, x, x, v)).fetchall()
    by: Dict[str, set] = {}
    for head, dep, rel, src in rows:
        if head in ("する", "なる", "ある", "いる", "言う", "思う"):
            continue
        by.setdefault(head, set()).add(src)
    ranked = sorted(((h, len(s)) for h, s in by.items() if len(s) >= 2), key=lambda x: -x[1])
    if not ranked:
        # the action itself is not written with X: say so, and give what is written about X — no claimed effect
        own = _con().execute("SELECT head, count(DISTINCT src) n FROM tedges WHERE dep=? AND rel='が' AND pol='+' "
                             "AND head NOT IN ('する','なる','ある','いる','できる') GROUP BY head HAVING n>=2 "
                             "ORDER BY n DESC LIMIT 3", (x,)).fetchall()
        if not own:
            return None
        return {"text": "「%sを%s」ことが書かれた文は見つかりませんでした。%sについて多く書かれているのは「%s」です。" % (
            x, _te(v), x, "」「".join("%sが%s（%d件）" % (x, h, n) for h, n in own)), "kind": "commonsense_partial"}
    h, n = ranked[0]
    return {"text": "%sを%sと、%sことが多いようです（出典 %d件）。" % (x, _te(v), h, n), "kind": "commonsense"}


def _te(v: str) -> str:
    from verantyx.realize import conjugate
    return (conjugate(v) or v)


# --- pun --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _predicates() -> List[tuple]:
    if PUN_LEXICON.exists():
        import json
        return [tuple(x) for x in json.loads(PUN_LEXICON.read_text())]
    rows = _con().execute("SELECT head, count(DISTINCT src) n FROM tedges WHERE rel='が' AND pol='+' "
                          "GROUP BY head HAVING n>=5 ORDER BY n DESC LIMIT 6000").fetchall()
    return [(h, kana(h)) for h, _ in rows]


def pun(u: str) -> Optional[Dict]:
    m = re.search(r"[「『](.+?)[」』]", u)
    if not m or not re.search(r"(ダジャレ|だじゃれ|駄洒落|冗談)", u):
        return None
    w = m.group(1)
    r = kana(w)
    if len(r) < 2:
        return None
    best = None
    for h, hr in _predicates():
        if h == w or w in h:
            continue
        # the predicate's reading starts with the word's reading, or with all but its last mora
        for k in (len(r), len(r) - 1):
            if k >= 2 and hr.startswith(r[:k]) and hr != r:
                if best is None or k > best[2]:
                    best = (h, hr, k)
                break
    if not best:
        return None
    from verantyx.realize import conjugate
    past = conjugate(best[0], past=True) or best[0]
    return {"text": "%sが%s。（「%s」と「%s」の音が似ています）" % (w, past, r, best[1][:len(r)]), "kind": "pun"}


# --- haiku ------------------------------------------------------------------------
def haiku(u: str) -> Optional[Dict]:
    if not re.search(r"(俳句|五・七・五|５・７・５|5・7・5)", u):
        return None
    m = re.search(r"[「『]?([^「『」』、。]+?)[」』]?(?:を|の|で|が)(?:題材|テーマ|季語|俳句)", u)
    topic = m.group(1) if m else None
    if not topic:
        s = re.search(r"(春|夏|秋|冬)", u)
        topic = s.group(1) if s else None
    if not topic:
        return None
    from verantyx.say import events
    evs = events(topic, scan=800, via_index=True)
    phrases = []
    for e in sorted(evs, key=lambda e: -e["n"]):
        f = e["frame"]
        if e["n"] < 2:
            continue
        parts = [f.agent, f.patient, f.recipient]
        other = [p for p in parts if p and p != topic]
        for p in other:
            phrases.append(p)
        phrases.append(f.predicate)
    words = list(dict.fromkeys([topic] + phrases))
    lines = _fit(words, [5, 7, 5])
    if not lines:
        return None
    return {"text": "／".join(lines) + "（コーパスで%sと一緒に書かれた語から、五・七・五に数えて組みました）" % topic,
            "kind": "haiku"}


def _fit(words: List[str], shape: List[int]) -> Optional[List[str]]:
    joins = ["の", "に", "が", "を", "や", ""]
    out, used = [], set()
    for target in shape:
        got = None
        for a in words:
            if a in used:
                continue
            if morae(a) == target:
                got = a
                break
            for j in joins:
                for b in words:
                    if b in used or b == a:
                        continue
                    s = a + j + b
                    if morae(s) == target:
                        got = s
                        break
                if got:
                    break
            if got:
                break
        if not got:
            return None
        used.update(w for w in words if w in got)
        out.append(got)
    return out


# --- story ------------------------------------------------------------------------
def story(u: str) -> Optional[Dict]:
    if not re.search(r"(物語|お話|話を|ストーリー)", u):
        return None
    m = re.search(r"[「『](.+?)[」』]", u)
    topic = m.group(1) if m else None
    if not topic:
        return None
    topic = re.split(r"の", topic)[-1]
    from verantyx.say import say
    r = say(topic, k=3, scan=1500, via_index=True)
    if not r.get("lines") or len(r["lines"]) < 2:
        return None
    s = [ln["sentence"] for ln in r["lines"]]
    text = "ある日、" + s[0] + "それから、" + "".join(s[1:-1] or []) + "最後に、" + s[-1]
    return {"text": text + "（2つ以上の出典に書かれた出来事を並べました）", "kind": "story"}


# --- round 2: count how the corpus text itself uses the words --------------------------
STOP = {"為る", "成る", "物", "事", "する", "なる", "ある", "いる", "居る", "有る", "見える", "思う", "言う", "よう", "感じる"}


def simile_words(b: str, k: int = 3) -> List[tuple]:
    """Words the corpus writes right after 「Bのように／Bのような」, by distinct sources."""
    rows = _con().execute("SELECT text, src FROM tsent WHERE text LIKE ? LIMIT 3000", ("%" + b + "のよう%",)).fetchall()
    c: Dict[str, set] = {}
    for text, src in rows:
        for m in re.finditer(re.escape(b) + r"のよう(?:に|な)(.{1,12})", text):
            for w in _tagger()(m.group(1)):
                key = w.feature.lemma or w.surface
                if w.feature.pos1 in ("形容詞", "動詞", "形状詞") and key not in STOP:
                    c.setdefault(key, set()).add(src)
                    break
    return sorted(((w, len(v)) for w, v in c.items() if len(v) >= 2), key=lambda x: -x[1])[:k]


def metaphor2(u: str) -> Optional[Dict]:
    if not re.search(r"(意味|どういうこと|たとえ|比喩)", u):
        return None
    m = re.search(r"[「『](.+?)[」』]", u)
    if not m:
        return None
    q = m.group(1)
    mm = re.search(r"(.+?)は(?:まるで)?(.+?)(?:のように(.+?)|のようだ|のようです|みたいだ|だ|です|だった)$", q)
    if not mm:
        return None
    a, b, said = mm.group(1), re.split(r"の(?!よう)", mm.group(2))[-1], mm.group(3)
    if said:
        # 「Bのように広い」: the sentence already says in what way
        w = [x.feature.lemma or x.surface for x in _tagger()(said) if x.feature.pos1 in ("形容詞", "動詞", "形状詞")]
        if w:
            return {"text": "%sが（%sにたとえるほど）とても%sという意味です。" % (a, b, said.rstrip("。")),
                    "kind": "metaphor_meaning"}
    ws = simile_words(b)
    if not ws:
        return None
    return {"text": "%sが、%sのように%sという意味だと思います（「%sのように」の後に書かれる語: %s）。" % (
        a, b, "・".join(w for w, _ in ws[:2]), b, "、".join("%s %d件" % (w, n) for w, n in ws)), "kind": "metaphor_meaning"}


def what_for(u: str) -> Optional[Dict]:
    m = re.search(r"^(.+?)(?:で|を使って)(?:は)?、?何を(?:しますか|する|できますか)", u) or \
        re.search(r"^(.+?)は何を(?:する|入れる|測る|知らせる|運ぶ)(?:もの|ため|車|道具|場所)?", u)
    if not m:
        return None
    x = m.group(1).strip("「」 ")
    rows = _con().execute("SELECT head, count(DISTINCT src) n FROM tedges WHERE dep=? AND rel IN ('で','が') AND pol='+' "
                          "AND head NOT IN ('する','なる','ある','いる','できる','言う','思う','見る') "
                          "GROUP BY head HAVING n>=2 ORDER BY n DESC LIMIT 3", (x,)).fetchall()
    if not rows:
        return None
    return {"text": "%sで（%sが）よく書かれているのは「%s」です。" % (x, x, "」「".join("%s（%d件）" % (h, n) for h, n in rows)),
            "kind": "commonsense_what"}


def effect2(u: str) -> Optional[Dict]:
    m = re.search(r"(.+?)[をにが](.+?)(?:と|たら|れば|ば)、?(?:どう|何が)", u)
    if not m:
        return None
    x = re.split(r"[、は]", m.group(1))[-1]
    vs = [w.feature.lemma for w in _tagger()(m.group(2)) if w.feature.pos1 == "動詞"]
    if not vs:
        return None
    rows = _con().execute(
        "SELECT t2.head, count(DISTINCT t2.src) n FROM tedges t1 JOIN tedges t2 ON t1.sha=t2.sha "
        "WHERE t1.head=? AND t2.dep=? AND t2.rel='が' AND t2.head<>? AND t2.pol='+' "
        "AND t2.head NOT IN ('する','なる','ある','いる','できる') GROUP BY t2.head HAVING n>=5 ORDER BY n DESC LIMIT 3",
        (vs[0], x, vs[0])).fetchall()
    if not rows:
        return None
    return {"text": "%sを%sと、%sが%sことが多く書かれています（出典 %d件）。" % (x, _te(vs[0]), x, rows[0][0], rows[0][1]),
            "kind": "commonsense_effect"}


def haiku2(u: str) -> Optional[Dict]:
    if not re.search(r"(俳句|五・七・五|５・７・５|5・7・5)", u):
        return None
    m = re.search(r"[「『](.+?)[」』]", u)
    topic = m.group(1) if m else (re.search(r"(春|夏|秋|冬)", u).group(1) if re.search(r"(春|夏|秋|冬)", u) else None)
    if not topic:
        return None
    rows = _con().execute("SELECT text FROM tsent WHERE text LIKE ? AND length(text) BETWEEN 10 AND 40 LIMIT 400",
                          ("%" + topic + "%",)).fetchall()
    for (text,) in rows:
        chunks, cur = [], ""
        for w in _tagger()(text.rstrip("。")):
            cur += w.surface
            if w.feature.pos1 in ("助詞", "助動詞", "補助記号") or w is None:
                chunks.append(cur); cur = ""
        if cur:
            chunks.append(cur)
        chunks = [c.strip("、") for c in chunks if c.strip("、")]
        # greedy: consecutive chunks summing to 5, 7, 5 morae
        for start in range(len(chunks)):
            out, i = [], start
            for target in (5, 7, 5):
                acc = ""
                while i < len(chunks) and morae(acc + chunks[i]) <= target:
                    acc += chunks[i]; i += 1
                    if morae(acc) == target:
                        break
                if morae(acc) != target:
                    break
                out.append(acc)
            if len(out) == 3 and topic in "".join(out):
                return {"text": "／".join(out) + "（コーパスの文「%s」を五・七・五に切りました）" % text, "kind": "haiku"}
    return None


def story2(u: str) -> Optional[Dict]:
    if not re.search(r"(物語|お話|話を|ストーリー)", u):
        return None
    m = re.search(r"[「『](.+?)[」』]", u)
    if not m:
        return None
    words = [w.surface for w in _tagger()(m.group(1)) if w.feature.pos1 == "名詞"]
    if not words:
        return None
    topic = words[-1]
    rows = _con().execute("SELECT s.text, s.src FROM tsent s WHERE s.src LIKE 'llm_authored:codex:%' AND s.text LIKE ? LIMIT 40",
                          ("%" + topic + "%",)).fetchall()
    for text, src in rows:
        same = [t for (t,) in _con().execute("SELECT text FROM tsent WHERE src=? LIMIT 60", (src,)).fetchall()]
        if text in same:
            i = same.index(text)
            part = same[max(0, i - 1): i + 2]
            if len(part) >= 3:
                return {"text": "".join(part) + "（コーパスの一場面から、%sが出てくる3文をそのまま取り出しました。新しく作った話ではありません）" % topic,
                        "kind": "story"}
    return None


def answer(u: str) -> Optional[Dict]:
    # metaphor meanings are not asserted: round 1 gave the literal attribute 55% of the time
    # stop rule (two sealed rounds): metaphor meaning, commonsense (effect / what for) and haiku did not fit
    # the design and are not answered; puns fit; stories only as a labelled passage from the corpus
    for f in (pun, story2):
        try:
            r = f(u)
        except Exception:
            r = None
        if r:
            return r
    return None

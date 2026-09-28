"""A bot for any set of documents: put documents in, get a bot that answers from them — no training.

    bot = Bot.from_dir("docs/")            # .txt / .md files; sub-folders become sovereigns
    bot.reply("何冊まで借りられますか。")    # the document sentence that answers it, with its source
    bot.judge("館内でパンを食べた。")        # the verdict contract against the documents

Japanese and English documents and questions (detected per text). Answers are sentences from the
documents, found through the base (stereo cross + flat fallback + sovereigns) and scored by content
words, counters (何冊 ↔ 5冊, how many ↔ five), conditions (〜したら ↔ 場合は, if/when) and the kind of
question (いつ/when ↔ days and times). What the documents do not say is answered with "I don't know".
Greetings, exact skills (arithmetic, conversion, …) and puns come from the chat underneath."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

JA = re.compile(r"[぀-ヿ一-鿿]")
COUNTERS = "冊|人|日|時|分|秒|円|週間|か月|ヶ月|年|回|個|枚|本|台|匹|歳|才|名|件|ページ|点|km|kg|m|g|%|パーセント|割"
KANJI_NUM = "〇一二三四五六七八九十百千"
WHEN_JA = re.compile(r"(\d+|[%s])(時|分|日|月|年)|[月火水木金土日]曜|毎週|毎日|午前|午後|朝|夜|以内|まで|から" % KANJI_NUM)
EN_NUM = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "twenty", "thirty", "hundred"}
EN_STOP = {"the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "in", "on", "at", "for", "and", "or", "do", "does", "did",
           "what", "when", "where", "who", "how", "many", "much", "can", "i", "you", "it", "this", "that", "with", "by", "from", "if",
           "may", "will", "there", "any", "my", "your", "we", "they", "please", "tell", "me", "about"}
JA_STOP = {"する", "ある", "いる", "なる", "こと", "もの", "何", "なん", "いつ", "どこ", "誰", "だれ", "どう", "どの", "できる",
           "教える", "くださる", "ます", "です", "場合", "よう"}


def lang(text: str) -> str:
    return "ja" if JA.search(text) else "en"


def _ja_words(text: str) -> set:
    from verantyx.typed_edges import _tagger
    out = set()
    for w in _tagger()(text):
        lem = w.feature.lemma or w.surface
        if w.feature.pos1 in ("名詞", "動詞", "形容詞", "形状詞") and lem not in JA_STOP and len(w.surface) > 0:
            out.add(lem.split("-")[0])
            if len(w.surface) >= 2:
                out.add(w.surface)
    return out


def _en_words(text: str) -> set:
    from verantyx.en_frames import lemma
    return {lemma(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in EN_STOP and len(w) > 1}


AUXV = {"is", "are", "was", "were", "has", "have", "had", "may", "can", "must", "will", "shall", "does", "do", "did",
        "should", "could", "would", "cannot"}


def _en_subject(sentence: str) -> str:
    """The words before the first verb: 'The library opens at 9' -> 'The library'."""
    ws = sentence.split()
    for i, w in enumerate(ws):
        lw = w.lower().strip(",.")
        if i > 0 and (lw in AUXV or (re.match(r"^[a-z]+(s|ed)$", lw) and ws[i - 1].lower() not in ("the", "a", "an"))):
            return " ".join(ws[:i])
    return ""


def _counters(text: str) -> set:
    return {m.group(2) for m in re.finditer(r"(\d+|[%s]+)\s*(%s)" % (KANJI_NUM, COUNTERS), text)}


class Bot:
    def __init__(self):
        from verantyx.base import Base
        self.base = Base()
        self.sents: List[dict] = []
        self._chat = None

    # --- building ------------------------------------------------------------------
    def add(self, name: str, text: str, sovereign: str = "", kind: str = "") -> "Bot":
        text = text.replace("\r", "")
        lg = lang(text)
        kind = kind or ("rules" if re.search(r"(てはいけな|てはならな|禁止|しなければならな|ものとする|てよい|できます|できません|must|may not|prohibited|shall)", text) else "record")
        if lg == "ja":
            self.base.add(name, text, kind, sovereign)
            parts = [s.strip() for s in re.split(r"(?<=[。！？])|\n+", text) if s.strip()]
        else:
            self.base.docs[name] = {"text": text, "kind": kind, "sovereign": sovereign or kind,
                                    "sentences": [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]}
            self.base.items[name] = []
            parts = self.base.docs[name]["sentences"]
            # "It is closed every Monday.": a leading It / They stands for the previous sentence's subject
            from verantyx import en_frames as en
            prev = ""
            for i, p in enumerate(parts):
                m = re.match(r"^(It|They)\b", p)
                if m and prev:
                    parts[i] = re.sub(r"^(It|They)\b", "The " + prev if not prev[0].isupper() else prev, p, count=1)
                subj = _en_subject(parts[i])
                if subj and subj.lower() not in ("it", "they"):
                    prev = subj
        for s in parts:
            if len(s) < 2 or s.startswith("#") and len(s) < 4:
                continue
            self.sents.append({"doc": name, "text": s, "lang": lg,
                               "words": _ja_words(s) if lg == "ja" else _en_words(s),
                               "counters": _counters(s) if lg == "ja" else ({w for w in re.findall(r"[a-z]+", s.lower()) if w in EN_NUM} | set(re.findall(r"\d+", s))),
                               "cond": bool(re.search(r"(場合|たら|ならば|際は|ときは|if |when |unless )", s)),
                               "when": bool(WHEN_JA.search(s)) if lg == "ja" else bool(re.search(r"\d|monday|tuesday|wednesday|thursday|friday|saturday|sunday|a\.m\.|p\.m\.|daily|weekly", s.lower()))})
        return self

    @classmethod
    def from_texts(cls, docs: Dict[str, str]) -> "Bot":
        b = cls()
        for n, t in docs.items():
            b.add(n, t)
        return b.build()

    @classmethod
    def from_dir(cls, path: str) -> "Bot":
        root = Path(path)
        b = cls()
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".txt", ".md"):
                sov = f.parent.name if f.parent != root else ""
                b.add(str(f.relative_to(root)), f.read_text(encoding="utf-8", errors="ignore"), sovereign=sov)
        return b.build()

    def build(self) -> "Bot":
        ja_docs = {n: d for n, d in self.base.docs.items() if self.base.items.get(n)}
        if ja_docs:
            self.base.build()
        return self

    # --- answering -----------------------------------------------------------------
    @property
    def chat(self):
        if self._chat is None:
            from verantyx.chat import Chat
            self._chat = Chat([])
        return self._chat

    def find(self, q: str) -> Optional[dict]:
        lg = lang(q)
        qw = _ja_words(q) if lg == "ja" else _en_words(q)
        if not qw:
            return None
        pool = [s for s in self.sents if s["lang"] == lg]
        leaf = None
        if lg == "ja" and self.base.root is not None:
            leaf = self.base.lower(q)
            if leaf:
                narrowed = [s for s in pool if s["doc"] == leaf]
                pool = narrowed or pool
        asks_count = bool(re.search(r"何(%s)|いくつ|いくら|how many|how much|how long" % COUNTERS, q.lower()))
        asks_when = bool(re.search(r"いつ|何時|何曜|何日|when|what time|which day", q.lower()))
        asks_cond = bool(re.search(r"(したら|すると|した場合|だったら|なら|if |what happens)", q.lower()))
        qcount = {m.group(1) for m in re.finditer(r"何(%s)" % COUNTERS, q)}
        qw = qw - qcount - {"何" + c for c in qcount}
        best, best_score = None, 0.0
        for s in pool:
            hit = qw & s["words"]
            counter_hit = bool(qcount and s["counters"] & qcount)
            if not hit and not counter_hit:
                continue
            # 何冊 ↔ 5冊: the counter alone can pick the sentence the words do not (借りる ↔ 貸出)
            score = len(hit) / (len(qw) ** 0.5 * max(len(s["words"]), 1) ** 0.5) + (0.3 if counter_hit and not hit else 0)
            if asks_count and (s["counters"] & qcount or (lg == "en" and s["counters"])):
                score += 0.35
            if asks_when and s["when"]:
                score += 0.25
            if asks_cond and s["cond"]:
                score += 0.25
            if score > best_score:
                best, best_score = s, score
        # one shared content word is enough only when the question is that specific
        if best is None or best_score < 0.28:
            return None
        return {**best, "score": round(best_score, 2), "leaf": leaf}

    def reply(self, q: str) -> Dict:
        q = q.strip()
        from verantyx.skills import answer as skill
        sk = skill(q)
        if sk:
            return sk
        from verantyx.chat import BYE, GREET
        from verantyx.intent import act_by_form
        act, _ = act_by_form(q)
        if GREET.search(q) or BYE.search(q) or act in ("thanks", "apology"):
            return self.chat.reply(q)
        hit = self.find(q)
        if hit:
            src = hit["doc"]
            text = ("%s（「%s」より）" % (hit["text"], src)) if hit["lang"] == "ja" else ("%s (from %s)" % (hit["text"], src))
            return {"text": text, "kind": "answer", "source": src, "evidence": [hit["text"]]}
        if lang(q) == "en":
            return {"text": "Sorry, the documents do not say.", "kind": "unknown"}
        r = self.chat.reply(q)
        if r.get("kind") in ("ack", "answer", "compose"):
            # the documents are what this bot knows; general-store answers are marked as such
            if r.get("kind") == "ack":
                return {"text": "ごめんなさい、文書には書かれていないようです。", "kind": "unknown"}
            r["text"] = r["text"] + "（文書ではなく一般の知識から）"
        return r

    def judge(self, claim: str) -> Dict:
        if lang(claim) == "ja":
            return self.base.judge(claim)
        from verantyx import en_frames as en
        from verantyx.crossverify import judge as xjudge
        rows = []
        for s in self.sents:
            if s["lang"] == "en":
                k = en.key(en.read(s["text"]))
                if k:
                    rows.append({"key": k, "sentence": s["text"]})
        return xjudge(rows, claim)

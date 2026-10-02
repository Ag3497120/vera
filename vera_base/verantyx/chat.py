"""Vera base chat (DESIGN_2026-09-28_vera_base_chat): simple Japanese, no training, no model.

Every reply says where it came from: the site's documents (with the sentence),
the general store (with how many sources), a fixed social reply, or "could not
read". Nothing is stated without a source; what cannot be answered is refused."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from verantyx.question import Query

from verantyx.frames import read_all
from verantyx.typed_edges import _tagger

import os
GENERAL = Path(os.environ.get("VERA_GENERAL", Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"))
PACK = Path(os.environ.get("VERA_PACK", GENERAL.with_name("chat_pack.json")))

SOCIAL = {
    "hello": "こんにちは。このサイトのことや、簡単な質問にお答えします。",
    "thanks": "どういたしまして。",
    "apology": "大丈夫です。ほかに知りたいことがあれば聞いてください。",
    "bye": "ありがとうございました。またどうぞ。",
}
GREET = re.compile(r"^(こんにちは|こんばんは|おはよう|はじめまして|やあ|どうも|もしもし|ハロー)")
BYE = re.compile(r"(さようなら|またね|バイバイ|おやすみ|失礼します)")
CREATE = re.compile(r"(詩|物語|お話|話を|ストーリー|俳句|短歌)(を)?(書いて|作って|聞かせて|して)")
JOKE = re.compile(r"(冗談|ギャグ|ジョーク|笑える|面白い話|おもしろい話|ダジャレ|だじゃれ)")
WHAT_IS = re.compile(r"^(.+?)(?:って|とは|は)(?:何|なに|なん)(?:ですか|でしょうか|か|だ|？|\?|。)*$|^(.+?)について(?:教えて|おしえて|知りたい)(?:ください|下さい)?[。！]?$")
CAN = re.compile(r"^(.+?)(?:は|って)(.+?)(?:ことができ|られ|れ|え|け|せ|て|め|べ|ね|げ|で)?(?:ますか|るか|る？|る\?|ますか？|ますか\?|ますか。)$")
YESNO = re.compile(r"^(.+?)(?:は|って)(.+?)(?:ですか|ますか|か)[？?。]*$")


def _words(t: str) -> set:
    return {w.feature.lemma or w.surface for w in _tagger()(t)
            if w.feature.pos1 in ("名詞", "動詞", "形容詞") and len(w.surface) > 1
            and (w.feature.lemma or w.surface) not in ("する", "ある", "いる", "なる", "こと", "もの", "何", "なん")}


class Chat:
    def __init__(self, site_docs: Optional[List[Dict[str, str]]] = None, general: Path = GENERAL,
                 tree: bool = False):
        self.sents = []
        self.tree = None
        if tree and site_docs:
            # the base: predicate-argument records reached through the stereo cross with a flat fallback
            from verantyx.base import Base
            self.tree = Base()
            for d in site_docs:
                self.tree.add(d["title"], d["ja"], "record")
            self.tree.build()
        for d in site_docs or []:
            for s in re.split(r"(?<=。)", d["ja"]):
                if s.strip():
                    self.sents.append((d["title"], s.strip(), _words(s)))
        self.general = general
        self._con = None

    @property
    def con(self):
        if not Path(self.general).exists():
            return None          # packaged mode: no general store, the chat pack answers alone
        if self._con is None:
            self._con = sqlite3.connect(f"file:{self.general}?mode=ro", uri=True, check_same_thread=False)
        return self._con

    # --- sources -------------------------------------------------------------
    def from_site(self, q: str) -> Optional[Dict[str, Any]]:
        qw = _words(q)
        if not qw or not self.sents:
            return None
        pool = self.sents
        if self.tree is not None:
            leaf = self.tree.lower(q)
            if leaf:
                pool = [x for x in self.sents if x[0] == leaf] or self.sents
                strict = False
            else:
                strict = True       # the tree refused: only a strong overlap may still answer
        else:
            strict = False
        best = max(pool, key=lambda x: (len(qw & x[2]) / (len(qw) ** 0.5 * len(x[2]) ** 0.5 + 1e-9)))
        hit = qw & best[2]
        if (self.tree is not None and strict and len(hit) >= 2) or \
                (not (self.tree is not None and strict) and (len(hit) >= 2 or (len(hit) == 1 and len(qw) == 1))):
            return {"text": "%s（「%s」より）" % (best[1], best[0]), "source": "site", "evidence": [best[1]]}
        return None

    def isa(self, x: str) -> List[tuple]:
        if self.con is None:
            return []
        rows = self.con.execute("SELECT y, count(DISTINCT src) n FROM isa WHERE x=? GROUP BY y "
                                "HAVING n>=2 ORDER BY n DESC LIMIT 6", (x,)).fetchall()
        return [r for r in rows if r[0] not in ("もの", "物", "こと", "事", "人", "方", "一つ", "ひとつ", "一種", "種類", "存在")][:3]

    def isa_sources(self, x: str, y: str) -> List[dict]:
        if self.con is None:
            return []
        return [{"family": "general", "source": src, "text": sentence}
                for sentence, src in self.con.execute(
                    "SELECT s.text,i.src FROM isa i JOIN tsent s ON s.sha=i.sha "
                    "WHERE i.x=? AND i.y=? GROUP BY i.src LIMIT 3", (x, y))]

    def events(self, topic: str, k: int = 3) -> List[tuple]:
        """(predicate, sources, short sentence 「topicがpredicate。」, shortest witness) for events
        with the topic as subject, attested by >= 2 sources."""
        heads = self.con.execute(
            "SELECT head, count(DISTINCT src) n FROM tedges WHERE dep=? AND rel='が' AND pol='+' "
            "AND mod='assert' GROUP BY head HAVING n>=2 ORDER BY n DESC LIMIT ?", (topic, k * 3)).fetchall()
        out = []
        for h, n in heads:
            if h in ("する", "ある", "いる", "なる", "できる", "言う", "思う") or len(h) < 2:
                continue
            w = self.con.execute(
                "SELECT s.text FROM tedges t JOIN tsent s ON s.sha=t.sha WHERE t.head=? AND t.dep=? AND t.rel='が' "
                "ORDER BY length(s.text) LIMIT 1", (h, topic)).fetchone()
            out.append((h, n, "%sが%s。" % (topic, h), w[0] if w else ""))
            if len(out) >= k:
                break
        return out

    def grounded(self, topic: str, k: int = 3) -> Dict[str, Any]:
        """say.py: events two sources wrote, composed by grammar and read back. Cached per topic;
        a prebuilt pack (tools/build_chat_pack.py) answers without touching the store."""
        if not hasattr(self, "_say_cache"):
            self._say_cache = {}
            pack = PACK
            if pack.exists():
                import json
                self._say_cache.update(json.loads(pack.read_text()))
        if topic not in self._say_cache and self.con is None:
            return {"text": "", "evidence": [], "sources": []}
        # A prebuilt pack carries only counts and the first witness. With the
        # live general store available, reread the indexed frames so each
        # generated sentence retains both source identities and texts.
        if self.con is not None and (topic not in self._say_cache or
                                     not self._say_cache[topic].get("_live")):
            from verantyx.say import say
            r = say(topic, k=k, db=self.general, scan=600, via_index=True)
            self._say_cache[topic] = {"text": r.get("text", ""), "_live": True,
                                      "evidence": [w["text"] for ln in r.get("lines", []) for w in ln["witnesses"]],
                                      "sources": [{"family": "general", **w} for ln in r.get("lines", [])
                                                  for w in ln["witnesses"]],
                                      "lines": [{"text": ln["sentence"],
                                                 "sources": [{"family": "general", **w} for w in ln["witnesses"]]}
                                                for ln in r.get("lines", [])]}
        return self._say_cache[topic]

    def can(self, subject: str, verb: str) -> Optional[Dict[str, Any]]:
        # Only what is written about the subject itself. Inheriting from the kind
        # answered ペンギン→鳥→飛ぶ (a known failure), so a kind's answer is not given.
        if self.con is None:
            return None
        from verantyx.typed_edges import ask_property
        r = ask_property(self.general, subject, [verb])
        v = r["verdict"]
        if v == "ATTESTED":
            sentence = "はい、%sは%sようです（出典 %d件）。" % (subject, verb, r.get("pos_sources", 2))
            srcs = [{"family": "general", "source": e["src"], "text": e["text"]}
                    for e in r.get("evidence", []) if e.get("text")]
            return {"text": sentence, "source": "general", "sources": srcs,
                    "evidence": [s["text"] for s in srcs],
                    "lines": [{"text": sentence, "sources": srcs}]} if srcs else None
        if v == "NEGATIVE_ATTESTED":
            sentence = "いいえ、%sは%sないようです（出典 %d件）。" % (subject, verb, max(r.get("neg_sources", 0), 2))
            srcs = [{"family": "general", "source": e["src"], "text": e["text"]}
                    for e in r.get("evidence", []) if e.get("text")]
            return {"text": sentence, "source": "general", "sources": srcs,
                    "evidence": [s["text"] for s in srcs],
                    "lines": [{"text": sentence, "sources": srcs}]} if srcs else None
        return None

    # --- reply ---------------------------------------------------------------
    def reply(self, u: str, context: str = "", *, query: Optional["Query"] = None) -> Dict[str, Any]:
        from verantyx.one import Vera
        return Vera(chat=self).chat(u, context=context, query=query)

    def _reply_impl(self, u: str, context: str = "", *, query: Optional["Query"] = None) -> Dict[str, Any]:
        from verantyx import question
        query = query if query is not None else question.read(u)
        u = query.surface.value
        act = query.speech_act.value.act
        if act == "request" and (question.is_content_request(u) or
                                 (query.kind.value != "instruction" and
                                  re.search(r"か[。？?]*$|[？?]$", u))):
            # Explanations, rewrites, and other text to produce are answer
            # requests. Keep their form reading in Query for the trace.
            act = "question"
        # Six open text abilities share the typed question reading and a
        # source-preserving structural composer. The legacy skill dispatcher
        # remains for exact calculations and social requests.
        from verantyx.abilities import Abilities
        if not hasattr(self, "_abilities"):
            self._abilities = Abilities(general=Path(self.general))
        ability = self._abilities.answer(u, query)
        if ability is not None:
            return ability
        from verantyx.skills import answer as skill_answer
        sk = skill_answer(u, context or " ".join(x[1] for x in self.sents if x[0] == "文章"))
        if sk:
            return sk
        from verantyx.core_abilities import answer as core_answer
        ca = core_answer(u)
        if ca:
            return ca
        if GREET.search(u):
            return {"text": SOCIAL["hello"], "kind": "social"}
        if BYE.search(u):
            return {"text": SOCIAL["bye"], "kind": "social"}
        if act in ("thanks", "apology"):
            return {"text": SOCIAL[act], "kind": "social"}
        if JOKE.search(u):
            return {"text": "ごめんなさい、冗談はまだ上手に作れません。", "kind": "not_yet"}
        m = CREATE.search(u)
        if m:
            rest = [w.surface for w in _tagger()(re.sub(r"[一二三四五六七八九十\d]+(行|文|句|つ|個)", "", u[:m.start()]))
                    if w.feature.pos1 == "名詞" and w.surface not in ("題材", "テーマ", "短い")]
            topic = rest[-1] if rest else ""
            g = self.grounded(topic) if topic else {"text": ""}
            if g["text"]:
                return {"text": g["text"] + "（2つ以上の出典に書かれた出来事を並べたものです）", "kind": "compose",
                        "evidence": g["evidence"]}
            return {"text": "ごめんなさい、それはまだ作れません。", "kind": "not_yet"}
        fig = self._figurative(u)
        if fig:
            return fig
        site = self.from_site(u)
        if site and act in ("question", "statement", "request"):
            return {**site, "kind": "answer"}
        if act == "request":
            if re.search(r"(作って|書いて|考えて|詠んで)", u):
                return {"text": "ごめんなさい、それはまだ作れません。", "kind": "not_yet"}
            return {"text": "ごめんなさい、私はここで質問にお答えするだけで、操作はできません。", "kind": "cannot"}
        m = WHAT_IS.match(u)
        if m:
            x = (m.group(1) or m.group(2)).strip()
            ups = self.isa(x)
            g = self.grounded(x)
            if ups or g["text"]:
                parts = []
                lines = []
                if ups:
                    isa_text = "%sは%sの一種です（出典 %d件）。" % (x, ups[0][0], ups[0][1])
                    isa_sources = self.isa_sources(x, ups[0][0])
                    if isa_sources:
                        parts.append(isa_text)
                        lines.append({"text": isa_text, "sources": isa_sources})
                parts.append(g["text"])
                lines.extend(g.get("lines", []))
                if not any(parts):
                    return {"text": "ごめんなさい、%sについては分かりません。" % x, "kind": "unknown"}
                all_sources = [s for ln in lines for s in ln["sources"]]
                return {"text": "".join(parts), "kind": "answer", "source": "general",
                        "evidence": [s["text"] for s in all_sources], "sources": all_sources,
                        "lines": lines,
                        "trace": [{"part": "question.read", "kind": query.kind.value},
                                  {"part": "say.say", "topic": x, "lines": len(g.get("lines", []))}]}
            return {"text": "ごめんなさい、%sについては分かりません。" % x, "kind": "unknown"}
        m = YESNO.match(u)
        if m and act == "question":
            subj, pred = m.group(1).strip(), m.group(2).strip()
            verb = self._verb(u)
            if verb:
                r = self.can(subj, verb)
                if r:
                    return {**r, "kind": "answer"}
            return {"text": "ごめんなさい、確かなことは分かりません。", "kind": "unknown"}
        frs = read_all(u if u.endswith(("。", "？", "?")) else u + "。")
        if not frs:
            return {"text": "ごめんなさい、うまく読めませんでした。別の言い方でお願いします。", "kind": "unreadable"}
        if act == "question":
            return {"text": "ごめんなさい、確かなことは分かりません。", "kind": "unknown"}
        return {"text": "そうなんですね。", "kind": "ack"}

    def _verb(self, u: str) -> str:
        for w in _tagger()(u):
            if w.feature.pos1 in ("動詞", "形容詞") and (w.feature.lemma or "") not in ("する", "ある", "できる", "いる", "れる", "られる"):
                return (w.feature.lemma or w.surface)
        return ""

    def _figurative(self, u: str) -> Optional[Dict[str, Any]]:
        if not re.search(r"(のような|のように|みたい|は.{1,6}だ[。！]?$|は.{1,6}です[。！]?$)", u):
            return None
        try:
            from verantyx.figurative import Figurative
            if not hasattr(self, "_fig"):
                self._fig = Figurative(self.general)
            r = self._fig.read(u)
        except Exception:
            return None
        if r.get("judgment") in ("FIGURATIVE", "SIMILE", "METAPHOR"):
            return {"text": "比喩として読みました。字どおりの意味ではないと受けとります。", "kind": "figurative",
                    "reading": r.get("judgment")}
        return None

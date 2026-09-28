"""Figurative language — detected as a type violation, understood as a mapping.

PREREGISTERED_2026-09-27_figurative. No model: the general typed store
(tools/build_general.py) supplies two things the corpus already wrote —
which nouns fill a verb's roles, and which class a noun belongs to (is-a).

    violation   the sentence puts a noun in a role that no noun of its kind
                has filled in the corpus (心が凍る: 凍る's subjects are 水,
                池, 道路 …, none shares a class with 心) → figurative candidate
    copula      「XはYだ」 where X and Y both have known classes and share
                none, and Y is not X's class (心は氷だ) → metaphor
    literal     the noun, or a noun of its class, fills the role; or Y is X's
                class (スズメは鳥だ)
    undecided   the store knows too little to say — reported, never guessed

Understanding is the mapping: what the corpus writes about the SOURCE (氷:
冷たい, 固い, 溶ける) that it also writes about the TARGET (心: 冷たい …).
Those shared relations are what the metaphor carries across.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .typed_edges import extract

GENERAL = Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"
MIN_FILLERS = 10

#: is-a noise measured on the inheritance run (魚→もの, 冬→0℃, 花→10mm):
#: formal nouns and quantities are not classes.
_FORMAL = {"もの", "物", "モノ", "こと", "事", "ため", "はず", "わけ", "ところ", "とき",
           "方", "ほう", "そう", "よう", "まま", "の", "感じ", "予定", "基本", "好み",
           "一つ", "つもり", "結果", "場合", "問題", "もんだい", "対象", "必要"}


def _is_class(y: str) -> bool:
    import re
    return (y not in _FORMAL and len(y) >= 1 and not re.search(r"[0-9０-９年月日℃%]", y)
            and not re.fullmatch(r"[ぁ-ん]+", y))
_ANS = "mod IN ('assert','cond_then')"


#: Profile similarity bands (addendum 1, fixed on the designer's dev pairs
#: before the sealed bench was read): literal pairs 0.18-0.53, figurative
#: 0-0.18, touching at 0.177/0.178 — so the middle is not decided.
LITERAL_AT, FIGURATIVE_AT, MIN_PROFILE = 0.19, 0.13, 15

#: Measured and NOT used for detection (2026-09-27): a conventional metaphor
#: contaminates its own evidence — the corpus also writes 重い時間, so 時間
#: looks physical and 時間が流れる stays literal, while 成果 flips to
#: figurative. Kept for the record and for physical() in the genitive rule.
#: Touchable properties: a noun the corpus never describes by any of these is
#: not a physical thing (時間, 心, 批判). Used to see a conventional metaphor
#: the corpus writes as often as a literal phrase: 時間が流れる — 流れる's usual
#: subjects (水, 川, 汗) are physical, 時間 is not.
PHYS = ("冷たい", "熱い", "温かい", "暖かい", "白い", "黒い", "赤い", "青い", "黄色い",
        "硬い", "固い", "柔らかい", "重い", "軽い", "湿っぽい", "透明", "鋭い", "丸い",
        "細い", "太い", "厚い", "薄い", "ぬるい", "ざらざら", "つるつる")
_PRONOUN = {"彼": "人", "彼女": "人", "私": "人", "僕": "人", "あなた": "人", "君": "人"}


class Figurative:
    def __init__(self, db: Path = GENERAL):
        import json
        self.con = sqlite3.connect(f"file:{db}?mode=ro", uri=True,
                                   check_same_thread=False)
        d = json.loads((Path(__file__).with_name("lang_data") / "predicate_df.json").read_text())
        self.N, self.df = d["n_nouns"], d["df"]

    @lru_cache(maxsize=100000)
    def vec(self, noun: str) -> Tuple[Tuple[str, float], ...]:
        """What the corpus writes a noun doing, having done to it, and being —
        each predicate weighted by how few nouns it goes with (する and なる go
        with everything and say nothing about kind)."""
        import math
        noun = _PRONOUN.get(noun, noun)
        c: Dict[str, int] = {}
        for h, r, k in self.con.execute(
                "SELECT head, rel, count(*) FROM tedges WHERE dep=? AND rel IN ('が','を','は') "
                "AND pol='+' GROUP BY head, rel", (noun,)):
            key = ("S:" if r in ("が", "は") else "O:") + h
            c[key] = c.get(key, 0) + k
        for d, k in self.con.execute(
                "SELECT dep, count(*) FROM tedges WHERE head=? AND rel='属性' AND pol='+' GROUP BY dep",
                (noun,)):
            c["A:" + d] = c.get("A:" + d, 0) + k
        return tuple((key, math.log1p(v) * math.log(self.N / (1 + self.df.get(key, 1))))
                     for key, v in c.items())

    def sim(self, a: str, b: str) -> Tuple[float, List[str], int]:
        import math
        va, vb = dict(self.vec(a)), dict(self.vec(b))
        n = min(len(va), len(vb))
        if not va or not vb:
            return 0.0, [], n
        shared = set(va) & set(vb)
        num = sum(va[k] * vb[k] for k in shared)
        den = math.sqrt(sum(v * v for v in va.values())) * math.sqrt(sum(v * v for v in vb.values()))
        top = sorted(shared, key=lambda k: -min(va[k], vb[k]))[:5]
        return (num / den if den else 0.0), [k.split(":", 1)[1] for k in top], n

    @lru_cache(maxsize=200000)
    def classes(self, noun: str) -> Tuple[str, ...]:
        rows = self.con.execute(
            "SELECT y FROM isa WHERE x=? GROUP BY y HAVING count(DISTINCT src)>=2",
            (noun,)).fetchall()
        return tuple(sorted({y for (y,) in rows if _is_class(y)}))

    @lru_cache(maxsize=50000)
    def fillers(self, verb: str, rel: str) -> Tuple[Tuple[str, int], ...]:
        rows = self.con.execute(
            f"SELECT dep, count(*) n FROM tedges WHERE head=? AND rel=? AND pol='+' AND {_ANS} "
            "GROUP BY dep ORDER BY n DESC LIMIT 300", (verb, rel)).fetchall()
        return tuple((d, n) for d, n in rows)

    def _kin(self, a: str, b: str) -> bool:
        ca, cb = {a, *self.classes(a)}, {b, *self.classes(b)}
        return bool(ca & cb)

    def physical(self, noun: str, skip: str = "") -> int:
        return sum(1 for k, _ in self.vec(noun) if k.startswith("A:") and k[2:] != skip
                   and any(p in k for p in PHYS))

    def crosses_kind(self, fillers: Sequence[str], noun: str, skip: str = "") -> bool:
        top = [d for d in fillers if d != noun][:10]
        if len(top) < 5 or self.physical(noun, skip) > 0:
            return False
        return sum(1 for d in top if self.physical(d) > 0) >= 0.6 * len(top)

    def role_check(self, verb: str, rel: str, noun: str) -> Dict[str, Any]:
        fl = self.fillers(verb, rel)
        if len(fl) < MIN_FILLERS:
            return {"judgment": "UNDECIDED", "why": "too few fillers for %s─%s" % (verb, rel)}
        exact = self._count(verb, rel, noun)   # the real count, not the top-300 list
        if exact >= 2:
            return {"judgment": "LITERAL", "why": "%s fills %s─%s %d times" % (noun, verb, rel, exact)}
        best, best_d, n_min = 0.0, "", 10 ** 9
        for d, _ in fl[:15]:
            if d == noun:
                continue
            sv, _, n = self.sim(noun, d)
            n_min = min(n_min, n)
            if sv > best:
                best, best_d = sv, d
        if best >= LITERAL_AT:
            return {"judgment": "LITERAL", "why": "%s behaves like %s (%.2f)" % (noun, best_d, best)}
        if len(dict(self.vec(noun))) < MIN_PROFILE:
            return {"judgment": "UNDECIDED", "why": "too little written about %s" % noun}
        if exact == 0 and best <= FIGURATIVE_AT:
            return {"judgment": "FIGURATIVE", "source": [d for d, _ in fl[:5]],
                    "why": "%s is unlike every usual %s─%s (best %s %.2f)" % (noun, verb, rel, best_d, best)}
        return {"judgment": "UNDECIDED", "why": "between the bands (%.2f)" % best}

    def role_check_attr(self, noun: str, adj: str) -> Dict[str, Any]:
        rows = self.con.execute(
            f"SELECT head, count(*) n FROM tedges WHERE dep=? AND rel='属性' AND pol='+' AND {_ANS} "
            "GROUP BY head ORDER BY n DESC LIMIT 300", (adj,)).fetchall()
        if len(rows) < MIN_FILLERS:
            return {"judgment": "UNDECIDED", "why": "too few subjects for %s" % adj}
        if self._count(noun, "属性", adj) >= 2:
            return {"judgment": "LITERAL", "why": "%s is written %s" % (noun, adj)}
        best, best_d = 0.0, ""
        for d, _ in rows[:15]:
            sv, _, _ = self.sim(noun, d)
            if sv > best:
                best, best_d = sv, d
        if best >= LITERAL_AT:
            return {"judgment": "LITERAL", "why": "%s behaves like %s (%.2f)" % (noun, best_d, best)}
        if len(dict(self.vec(noun))) >= MIN_PROFILE and best <= FIGURATIVE_AT:
            return {"judgment": "FIGURATIVE", "source": [d for d, _ in rows[:5]],
                    "why": "%s is unlike what is usually %s" % (noun, adj)}
        return {"judgment": "UNDECIDED", "why": "between the bands (%.2f)" % best}

    def copula_check(self, x: str, y: str) -> Dict[str, Any]:
        if y in self.classes(x) or x == y:
            return {"judgment": "LITERAL", "why": "%s is a kind of %s" % (x, y)}
        s, shared, n = self.sim(x, y)
        if n < MIN_PROFILE:
            return {"judgment": "UNDECIDED", "why": "too little written about %s or %s" % (x, y)}
        if s >= LITERAL_AT:
            return {"judgment": "LITERAL", "why": "%s and %s behave alike (%.2f)" % (x, y, s)}
        if s <= FIGURATIVE_AT:
            return {"judgment": "FIGURATIVE", "source": [y], "mapped": shared,
                    "why": "%s and %s behave unlike (%.2f); shared: %s" % (x, y, s, "・".join(shared))}
        return {"judgment": "UNDECIDED", "why": "between the bands (%.2f)" % s}

    @lru_cache(maxsize=50000)
    def profile(self, noun: str) -> Dict[str, int]:
        """What the store writes about a noun: its attributes and the verbs it
        is the subject of."""
        out: Dict[str, int] = {}
        for w, n in self.con.execute(
                f"SELECT dep, count(*) FROM tedges WHERE head=? AND rel='属性' AND pol='+' AND {_ANS} GROUP BY dep",
                (noun,)):
            out[w] = out.get(w, 0) + n
        for w, n in self.con.execute(
                f"SELECT head, count(*) FROM tedges WHERE dep=? AND rel IN ('が','は') AND pol='+' AND {_ANS} GROUP BY head",
                (noun,)):
            out[w] = out.get(w, 0) + n
        return out

    def mapping(self, target: str, sources: Sequence[str], k: int = 5) -> List[str]:
        t = self.profile(target)
        score: Dict[str, float] = {}
        for s in sources:
            for w, n in self.profile(s).items():
                if w in t and len(w) >= 2:
                    score[w] = score.get(w, 0) + min(n, t[w])
        return [w for w, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]

    def _count(self, verb: str, rel: str, noun: str) -> int:
        return self.con.execute(
            "SELECT count(DISTINCT src) FROM (SELECT src FROM tedges WHERE head=? AND rel=? AND dep=? LIMIT 50)",
            (verb, rel, noun)).fetchone()[0]

    def genitive(self, sentence: str, es) -> Optional[Dict[str, Any]]:
        """「AのB」 metaphor: 質問の雨が降った. B meets its predicate literally
        (雨が降る is written); A, an event or feeling noun (質問, 批判, 情熱 —
        nouns unidic marks サ変可能 / 形状詞可能), is never written in that role;
        B is a plain concrete noun. Then A borrows B's role: the metaphor."""
        from .typed_edges import _tagger
        toks = list(_tagger()(sentence))
        for e in es:
            if e.rel not in ("が", "を", "は") or e.mod != "assert":
                continue
            b = e.dep
            for i in range(2, len(toks)):
                if toks[i].surface != b[-len(toks[i].surface):] and toks[i].surface != b:
                    continue
                # B's first token index: walk back over B's surface
                j, acc = i, toks[i].surface
                while acc != b and j > 0 and b.endswith(toks[j - 1].surface + acc):
                    j -= 1
                    acc = toks[j].surface + acc
                if acc != b or j < 2 or toks[j - 1].surface != "の":
                    continue
                a_tok = toks[j - 2]
                if a_tok.feature.pos1 != "名詞":
                    continue
                a = a_tok.surface
                abstract = a_tok.feature.pos3 in ("サ変可能", "形状詞可能") or \
                    str(getattr(a_tok.feature, "pos3", "")).startswith("サ変")
                concrete = toks[i].feature.pos1 == "名詞" and toks[i].feature.pos3 == "一般"
                if not (abstract and concrete):
                    continue
                if self._count(e.head, e.rel, b) >= 2 and self._count(e.head, e.rel, a) < 2:
                    s_, shared, _ = self.sim(a, b)
                    if s_ > FIGURATIVE_AT:
                        continue    # 研究の成果: A and B are alike, a plain genitive
                    return {"judgment": "FIGURATIVE", "target": a, "source": [b],
                            "edge": "%sの%s─%s→%s" % (a, b, e.rel, e.head),
                            "mapped": [e.head] + [x for x in shared if x != e.head][:4],
                            "why": "「%sの%s」: %sは%sと書かれるが、%sは書かれない" % (
                                a, b, b, e.head, a)}
        return None

    def read(self, sentence: str) -> Dict[str, Any]:
        es = extract(sentence)
        g = self.genitive(sentence, es)
        if g:
            return {"sentence": sentence, **g}
        if any(e.mod == "simile" for e in es):
            return {"judgment": "SIMILE", "sentence": sentence}
        best: Optional[Dict[str, Any]] = None
        for e in es:
            if e.rel == "同":
                r = self.copula_check(e.head, e.dep)
                target = e.head
            elif e.rel in ("が", "を"):
                r = self.role_check(e.head, e.rel, e.dep)
                target = e.dep
            elif e.rel == "属性":
                r = self.role_check_attr(e.head, e.dep)
                target = e.head
            else:
                continue
            r = {**r, "edge": "%s─%s→%s" % (e.head, e.rel, e.dep), "target": target}
            if r["judgment"] == "FIGURATIVE":
                if not r.get("mapped"):
                    r["mapped"] = self.mapping(target, r.get("source", []))
                return {"sentence": sentence, **r}
            if best is None or (best["judgment"] == "UNDECIDED" and r["judgment"] == "LITERAL"):
                best = r
        return {"sentence": sentence, **(best or {"judgment": "UNDECIDED", "why": "no edge"})}

"""The verdict contract (PREREGISTERED_2026-09-28_verdict_contract).

A claim is judged against the owner's records and gets exactly one verdict, with
the record sentence(s) it rests on:

    SUPPORTED     follows from a record sentence (within its condition / exception)
    DIFFERENT     same event, a role or object differs; both can be true
    CONTRADICTED  cannot both be true (fact against fact, rule against rule)
    VIOLATES      a fact that breaks a rule (prohibition / obligation) of the records
    UNCONFIRMED   neither supported nor denied by what could be read; with a reason
    NOT_IN_DOCS   read, but the records have no such event
    OUT_OF_SCOPE  not a factual claim (opinion, question, figurative)

Records are read as a whole: a sentence's kind (fact, prohibition, obligation,
permission) and condition come from its wording; "ただし" attaches an exception to
the rule before it; a dropped subject or それ/彼 is filled from the sentence before
(marked inferred, with both sentences as evidence). No model, no learning."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from verantyx.frames import Frame, canonical, read_all

_AUX_PRED = {"いける", "なる", "すぎる", "思う", "する", "できる", "よい", "いい", "くださる"}

PROHIBIT = re.compile(r"(てはいけな|ではいけな|てはならな|ではならな|禁止|ないこと[。、]|ないものとする|ないでください)")
OBLIGE = re.compile(r"(なければならな|なくてはならな|なければいけな|必要がある|ものとする|こと[。]$|ましょう|てください)")
PERMIT = re.compile(r"(てもよい|てよい|でもよい|てもいい|ことができる|差し支えない|てもかまわない|可能)")
COND = re.compile(r"^(.*?)(場合(?:は|には|に)?|ならば|(?<!な)(?<!けれ)なら(?!な)|(?<!なけ)れば|ときは|時は|際は|際には)[、,]?")
TIME = re.compile(r"^(夜間|深夜|早朝|朝|夜|昼|休日|祝日|週末|営業時間外|営業時間中|勤務時間外|閉館後|開館前|終業後|始業前)$")
OPINION = re.compile(r"(と思う|と思います|べきだ|べきです|だろう|でしょう|かもしれない|と感じ|すぎる|すぎます|気がする|ほしい|たい[。])")
QUESTION = re.compile(r"(か[。？?]?$|[？?]$|ですか|ますか|でしょうか)")
FIGURATIVE = re.compile(r"(のような|のように|みたいな|みたいに|まるで)")
TIME_PHRASE = re.compile(r"(夜間|深夜|早朝|休日|祝日|週末|営業時間外|営業時間中|勤務時間外|閉館後|開館前|終業後|始業前)(には|では|は|に|で)[、,]?")


def _strip_time(s: str) -> tuple:
    """Time phrases say when something holds; take them out before reading roles."""
    found = [m.group(1) for m in TIME_PHRASE.finditer(s)]
    return TIME_PHRASE.sub("", s), " ".join(found)


PRONOUN_PERSON = ("彼女", "彼ら", "彼")
PRONOUN_THING = ("それ", "これ", "あれ", "そちら")


@dataclass
class Item:
    frame: Frame
    kind: str                    # fact / prohibition / obligation / permission
    sentence: str
    condition: str = ""          # the condition clause, as written
    exception_of: Optional[int] = None
    inferred_from: List[str] = field(default_factory=list)


_U2E = dict(zip("うくぐすつぬぶむる", "えけげせてねべめれ"))
HEDGE = re.compile(r"(ようだ|ようです|らしい|らしいです|みたいだ|そうだ[。]|そうです[。]|とのことだ|と聞いた|はずだ)")
COPULA = re.compile(r"^([^、。]{1,20}?)は([^、。をにがで]{1,15}?)(だ|です|である)[。！!]?$")


def _potential(s: str) -> bool:
    """The last verb in its potential form (渡せる, 持ち出せる) or followed by できる."""
    from verantyx.typed_edges import _tagger
    ws = [w for w in _tagger()(s) if w.feature.pos1 == "動詞"]
    if not ws:
        return False
    w = ws[-1]
    if (w.feature.lemma or "") in ("出来る", "できる") and len(ws) > 1:
        return True
    lem, sur = w.feature.lemma or "", w.surface
    return bool(lem) and lem[-1] in _U2E and sur == lem[:-1] + _U2E[lem[-1]] + "る"


def _clause_kind(s: str, doc_kind: str, negated: bool) -> str:
    if PROHIBIT.search(s):
        return "prohibition"
    if PERMIT.search(s) or (not negated and _potential(s) and not re.search(r"(た|ました)[。]?$", s)):
        return "permission"
    if OBLIGE.search(s):
        return "obligation"
    if doc_kind == "rules" and not re.search(r"(た|だ|でした|ました)[。]?$", s):
        return "prohibition" if negated else "obligation"
    return "fact"


def _resolve_surface(s: str, prev: Optional[Item]) -> tuple:
    """Replace それ/彼 with what they point at, and a noun+も object with を. Returns (text, used)."""
    used = []
    if prev is not None:
        for p in PRONOUN_PERSON:
            if s.startswith(p + "は") or s.startswith(p + "が") or ("、" + p + "は") in s:
                if prev.frame.agent:
                    s = s.replace(p + "は", prev.frame.agent + "は", 1).replace(p + "が", prev.frame.agent + "が", 1)
                    used.append(p)
                break
        for p in PRONOUN_THING:
            if p + "を" in s and prev.frame.patient:
                s = s.replace(p + "を", prev.frame.patient + "を", 1)
                used.append(p)
                break
    # X も V (object): read as X を V when nothing else is marked を
    if "を" not in s:
        s2 = re.sub(r"([一-龥ァ-ヶー]{1,8})も(?=[^、。]*?(?:た|る|す|い)[。])", r"\1を", s, count=1)
        if s2 != s:
            used.append("も")
            s = s2
    return s, used


def read_records(text: str, doc_kind: str = "record") -> List[Item]:
    items: List[Item] = []
    prev: Optional[Item] = None
    for raw in [x for x in re.split(r"(?<=。)", text) if x.strip()]:
        s = raw.strip()
        exception = bool(re.match(r"^ただし(?:書き)?[、,]?", s) or
                         re.search(r"この限り(?:で|では)ない", s) or
                         re.match(r"^[^、。]{1,30}を除き[、,]", s))
        body = re.sub(r"^ただし(?:書き)?[、,]?", "", s)
        cond = ""
        m = COND.match(body)
        main = body
        if m and len(m.group(1)) > 1:
            cond, main = m.group(1), body[m.end():]
        main, when = _strip_time(main)
        cond = (cond + " " + when).strip()
        main = re.sub(r"^(そのため|そこで|それで|だから|なので|すると|その後|次に)[、,]?", "", main.strip())
        main_r, used = _resolve_surface(main, prev)
        frames = [f for f in read_all(main_r if main_r.endswith("。") else main_r + "。")
                  if f.predicate not in _AUX_PRED and f.agent != "場合"]
        if not frames:
            if exception and re.search(r"この限り(?:で|では)ない", s):
                # A proviso can refer to the previous rule without repeating
                # its verb. Keep a typed link even when the clause has no frame.
                for j in range(len(items) - 1, -1, -1):
                    rule = items[j]
                    if rule.kind != "fact" and (prev is None or rule.sentence == prev.sentence):
                        items.append(Item(rule.frame, "permission", s, cond,
                                          exception_of=j, inferred_from=[rule.sentence]))
                        break
            continue
        for f in frames:
            kind = _clause_kind(s, doc_kind, f.negated)
            if kind in ("prohibition",) and f.negated:
                f = Frame(f.predicate, f.agent, f.patient, f.recipient, False, f.past, f.ambiguous, f.inferred)
            if kind == "obligation" and f.negated and re.search(r"なければ|なくては", s):
                f = Frame(f.predicate, f.agent, f.patient, f.recipient, False, f.past, f.ambiguous, f.inferred)
            for role in ("patient", "agent"):
                v = getattr(f, role)
                if v and TIME.match(v):          # a time word is when the rule holds, not a participant
                    cond = (cond + " " + v).strip()
                    f = Frame(f.predicate, "" if role == "agent" else f.agent,
                              "" if role == "patient" else f.patient, f.recipient, f.negated, f.past)
            it = Item(f, kind, s, cond)
            if used and prev is not None:
                it.inferred_from = [prev.sentence]
            if exception and items:
                # An explicit exception can change the predicate ("use is banned;
                # however, written consent is allowed"). Keep its nearby rule.
                for j in range(len(items) - 1, -1, -1):
                    r = items[j]
                    if r.sentence != s and r.kind != "fact" and prev is not None and \
                            r.sentence == prev.sentence:
                        it.exception_of = j
                        it.frame = Frame(f.predicate, f.agent or r.frame.agent, f.patient or r.frame.patient,
                                         f.recipient or r.frame.recipient, f.negated)
                        it.inferred_from = [r.sentence]
                        break
            elif prev is not None and not f.agent and prev.frame.recipient and \
                    re.match(r"^(受け取って|受け取ると|受け取り、|もらって|預かって|引き継いで)", main.strip()):
                # 「YにAを渡した。受け取って…」: who received it acts next
                it.frame = Frame(f.predicate, prev.frame.recipient, f.patient or prev.frame.patient, f.recipient,
                                 f.negated, f.past, f.ambiguous, True)
                it.inferred_from = [prev.sentence]
            elif prev is not None and not f.agent and prev.frame.agent and _person(prev.frame.agent) \
                    and not re.search(r"(られ|され)(た|る)", main):
                it.frame = Frame(f.predicate, prev.frame.agent, f.patient, f.recipient, f.negated, f.past,
                                 f.ambiguous, True)
                it.inferred_from = [prev.sentence]
            items.append(it)
        prev = items[-1] if items else prev
    return items


def _person(w: str) -> bool:
    from verantyx.frames import is_role
    return bool(re.search(r"(さん|様|氏|君|係|員|長|者|師|士|手|官|生|人)$", w)) or is_role(w)


def _same(a: str, b: str) -> bool:
    return canonical(a) == canonical(b) or (bool(a) and bool(b) and (a in b or b in a))


def _roles(f: Frame):
    return [f.agent, f.patient, f.recipient]


def judge(items: List[Item], claim: str) -> dict:
    c = claim.strip()
    if QUESTION.search(c):
        return {"verdict": "OUT_OF_SCOPE", "why": "question"}
    if OPINION.search(c):
        return {"verdict": "OUT_OF_SCOPE", "why": "opinion"}
    if FIGURATIVE.search(c):
        return {"verdict": "OUT_OF_SCOPE", "why": "figurative"}
    if HEDGE.search(c):
        return {"verdict": "UNCONFIRMED", "why": "hedged (hearsay or inference)"}
    cm = COPULA.match(c)
    if cm and not [f for f in read_all(c) if f.predicate not in _AUX_PRED]:
        # 「XはYだ」: a kind statement only if the records say so; otherwise not a factual claim to judge
        x, y = cm.group(1), cm.group(2)
        if not any(y in it.sentence and x in it.sentence for it in items):
            return {"verdict": "OUT_OF_SCOPE", "why": "figurative or evaluative copula"}
    cond = ""
    m = COND.match(c)
    main = c
    if m and len(m.group(1)) > 1:
        cond, main = m.group(1), c[m.end():]
    main, when = _strip_time(main)
    cond = (cond + " " + when).strip()
    frames = [f for f in read_all(main if main.endswith("。") else main + "。")
              if f.predicate not in _AUX_PRED and f.agent != "場合"]
    if not frames:
        return {"verdict": "UNCONFIRMED", "why": "unread"}
    f = frames[-1]
    # 「Bも…した」: B is who did it (も marks the doer here when を is already taken)
    if not f.agent:
        mo = re.match(r"^([^、。をにがはで]{1,12}?)も[、,]?", main.strip())
        if mo and "を" in main:
            f = Frame(f.predicate, mo.group(1), f.patient, f.recipient, f.negated, f.past)
    for role in ("patient", "agent"):
        v = getattr(f, role)
        if v and TIME.match(v):
            cond = (cond + " " + v).strip()
            f = Frame(f.predicate, "" if role == "agent" else f.agent, "" if role == "patient" else f.patient,
                      f.recipient, f.negated)
    ckind = _clause_kind(c, "claim", f.negated)
    if ckind in ("prohibition",) or (ckind == "obligation" and re.search(r"なければ|なくては", c)):
        f = Frame(f.predicate, f.agent, f.patient, f.recipient, False)
    if not f.agent and not f.patient:
        return {"verdict": "UNCONFIRMED", "why": "unread"}
    same_pred = [(i, it) for i, it in enumerate(items) if _same(it.frame.predicate, f.predicate)]
    if not same_pred:
        return {"verdict": "NOT_IN_DOCS"}

    def match(it):
        r = it.frame
        pairs = list(zip(_roles(f), _roles(r)))
        rule = it.kind != "fact"
        # a rule that names no doer binds everyone: an empty agent in a rule matches any doer
        ok = all((not x) or (y and _same(x, y)) or (rule and k == 0 and not y)
                 for k, (x, y) in enumerate(pairs))
        return ok

    def ev(it):
        return [it.sentence] + it.inferred_from

    exact = [(i, it) for i, it in same_pred if match(it)]
    for i, it in exact:
        rk = it.kind
        if ckind == "fact":
            if rk == "fact":
                if it.frame.negated == f.negated:
                    if not f.agent and it.frame.agent:
                        return {"verdict": "UNCONFIRMED", "why": "ambiguous", "evidence": ev(it)}
                    return {"verdict": "SUPPORTED", "evidence": ev(it)}
                return {"verdict": "CONTRADICTED", "evidence": ev(it), "why": "negation"}
            if rk == "prohibition" and not f.negated:
                exc = [x for x in items if x.exception_of == i]
                if any(x.condition and _mentions(c, x.condition) for x in exc):
                    return {"verdict": "NOT_IN_DOCS", "evidence": ev(it) + [x.sentence for x in exc],
                            "why": "the exception applies"}
                if it.condition and not _mentions(c, it.condition):
                    return {"verdict": "UNCONFIRMED", "why": "scope", "evidence": ev(it)}
                if exc:
                    return {"verdict": "UNCONFIRMED", "why": "scope", "evidence": ev(it) + [x.sentence for x in exc]}
                return {"verdict": "VIOLATES", "evidence": ev(it), "why": "prohibited"}
            if rk == "obligation" and f.negated:
                if it.condition:
                    return {"verdict": "UNCONFIRMED", "why": "scope", "evidence": ev(it)}
                return {"verdict": "VIOLATES", "evidence": ev(it), "why": "obligation not met"}
            if rk == "obligation" and not f.negated:
                return {"verdict": "NOT_IN_DOCS", "evidence": ev(it), "why": "required, but not recorded as done"}
            if rk == "permission":
                return {"verdict": "NOT_IN_DOCS", "evidence": ev(it), "why": "permitted, but not recorded as done"}
        else:
            # a rule claim against a rule of the records
            if rk == ckind and it.frame.negated == f.negated:
                if it.exception_of is None and not it.condition and cond:
                    return {"verdict": "UNCONFIRMED", "why": "scope", "evidence": ev(it)}
                return {"verdict": "SUPPORTED", "evidence": ev(it)}
            opposite = {("prohibition", "permission"), ("permission", "prohibition"),
                        ("prohibition", "obligation"), ("obligation", "prohibition")}
            if (rk, ckind) in opposite:
                # a conditional permission does not contradict the prohibition it is an exception to
                if it.exception_of is not None or it.condition:
                    if cond and _mentions(cond, it.condition):
                        return {"verdict": "SUPPORTED", "evidence": ev(it)}
                    continue
                exc = [x for x in items if x.exception_of == i]
                if exc and cond and any(_mentions(cond, x.condition) for x in exc):
                    return {"verdict": "SUPPORTED", "evidence": [x.sentence for x in exc] + ev(it)}
                return {"verdict": "CONTRADICTED", "evidence": ev(it), "why": "%s against %s" % (ckind, rk)}
    # same event, different roles: can both be true
    for i, it in same_pred:
        shared = sum(1 for x in _roles(f) if x and any(y and _same(x, y) for y in _roles(it.frame)))
        if shared >= 2 or (shared >= 1 and sum(1 for x in _roles(f) if x) == 1):
            return {"verdict": "DIFFERENT", "evidence": ev(it), "why": "roles differ"}
    return {"verdict": "NOT_IN_DOCS"}


def _mentions(text: str, cond: str) -> bool:
    """Does text state the condition? Content words of the condition all appear in text."""
    from verantyx.typed_edges import _tagger
    words = {w.feature.lemma or w.surface for w in _tagger()(cond)
             if w.feature.pos1 in ("名詞", "動詞") and len(w.surface) > 1}
    got = {w.feature.lemma or w.surface for w in _tagger()(text)
           if w.feature.pos1 in ("名詞", "動詞")}
    return bool(words) and len(words & got) >= max(1, len(words) - 1)


def verify(text: str, claims: List[str], doc_kind: str = "record") -> List[dict]:
    items = read_records(text, doc_kind)
    return [dict(claim=c, **judge(items, c)) for c in claims]

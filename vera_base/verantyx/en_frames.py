"""English into the same event frame as Japanese — and back.

PREREGISTERED_2026-09-28_interlingua. The frame (predicate, agent, patient,
recipient, negated) carries no English or Japanese grammar; only the words are
language-specific. This reads English by word order and closed function
words, no parser and no model:

    Hanako gave Taro the documents.         ditransitive
    Hanako gave the documents to Taro.      to/for recipient
    The documents were given to Taro by Hanako.   passive
    It was Hanako who gave Taro the documents.    cleft
    Hanako did not give Taro the documents.       negation

and realizes a frame as a plain active English sentence.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .frames import Frame

# Irregular verbs: past / past participle -> base.
_IRR = """be was were been|become became become|begin began begun|bring brought brought|build built built|buy bought bought|
catch caught caught|choose chose chosen|come came come|cut cut cut|do did done|draw drew drawn|drink drank drunk|drive drove driven|
eat ate eaten|fall fell fallen|feed fed fed|feel felt felt|find found found|fly flew flown|forget forgot forgotten|forgive forgave forgiven|
get got gotten|give gave given|go went gone|grow grew grown|have had had|hear heard heard|hide hid hidden|hit hit hit|hold held held|
hurt hurt hurt|keep kept kept|know knew known|lay laid laid|lead led led|leave left left|lend lent lent|let let let|lose lost lost|
make made made|mean meant meant|meet met met|pay paid paid|put put put|read read read|ride rode ridden|ring rang rung|rise rose risen|
run ran run|say said said|see saw seen|sell sold sold|send sent sent|set set set|show showed shown|shut shut shut|sing sang sung|
sit sat sat|sleep slept slept|speak spoke spoken|spend spent spent|stand stood stood|steal stole stolen|swim swam swum|take took taken|
teach taught taught|tear tore torn|tell told told|think thought thought|throw threw thrown|understand understood understood|
wake woke woken|wear wore worn|win won won|write wrote written|hand handed handed|lend lent lent|mail mailed mailed|
submit submitted submitted|forbid forbade forbidden|withdraw withdrew withdrawn|undertake undertook undertaken|overtake overtook overtaken"""
IRREG: Dict[str, str] = {}
for _line in _IRR.replace("\n", "").split("|"):
    parts = _line.split()
    if len(parts) == 3:
        for f in parts:
            IRREG.setdefault(f, parts[0])

DITRANS = {"give", "hand", "send", "show", "tell", "teach", "lend", "offer", "pay", "bring", "buy", "mail",
           "sell", "pass", "throw", "read", "write", "email", "promise", "grant", "award", "serve", "cook",
           "make", "get", "leave", "owe", "assign", "provide", "deliver", "return", "forward", "ask"}

DET = {"a", "an", "the", "this", "that", "these", "those", "his", "her", "their", "its", "our", "my", "your", "some", "any", "no", "each", "every"}
AUX = {"did", "does", "do", "was", "were", "is", "are", "has", "have", "had", "will", "would", "can", "could", "should", "may", "must", "been", "be", "being"}
NEG = {"not", "never", "n't"}
PREP = {"to", "for", "by", "with", "at", "in", "on", "from", "of", "about", "into", "onto", "during", "before", "after", "under", "over", "through"}
PARTICLES = {"out", "up", "on", "back", "off", "down", "away", "over", "in"}
ANIMATE = {"patient", "patients", "student", "students", "teacher", "teachers", "doctor", "nurse", "manager", "customer",
           "customers", "client", "clients", "child", "children", "mother", "father", "cat", "dog", "boss", "team", "staff",
           "guest", "guests", "visitor", "visitors", "employee", "employees", "worker", "workers", "farmer", "player", "players",
           "coach", "librarian", "officer", "resident", "residents", "chef", "waiter", "researcher", "friend", "friends", "parents",
           "grandmother", "grandfather", "brother", "sister", "son", "daughter", "baby", "pupil", "class", "audience", "member", "members"}
ADV = {"yesterday", "today", "tomorrow", "again", "also", "already", "still", "just", "then", "carefully", "quickly", "politely", "finally", "immediately", "directly", "personally", "kindly", "only", "later", "early", "late", "last", "this", "morning", "evening", "night", "week", "year", "month"}
_REL = {"who", "that", "which"}


def lemma(w: str) -> str:
    w = w.lower()
    if w in IRREG:
        return IRREG[w]
    for suf, rep in (("ied", "y"), ("ies", "y")):
        if w.endswith(suf) and len(w) > 4:
            return w[: -len(suf)] + rep
    if w.endswith("ed") and len(w) > 3:
        base = w[:-2]
        if len(base) > 2 and base[-1] == base[-2] and base[-1] not in "lsz":
            return base[:-1]                      # submitted -> submit
        if base.endswith(("at", "iz", "ag", "ov", "ag", "uc", "ic", "ar", "ir", "ur", "iv", "rv", "ov", "at", "ut", "id", "od", "ud", "ag", "ib", "ok", "as", "ar")) or \
                re.search(r"(c|g|v|z|s|u)$", base):
            return base + "e" if not base.endswith(("ss",)) else base
        return base
    if w.endswith("es") and w[:-2].endswith(("sh", "ch", "ss", "x", "o")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


_TIME = re.compile(r"\b(?:yesterday|today|tonight|tomorrow|(?:this|last|every|each|next) (?:morning|afternoon|evening|night|week|month|day)|(?:in|during) the (?:morning|afternoon|evening|night)|every day|daily|at night)\b", re.I)


def _tokens(s: str) -> List[str]:
    s = _TIME.sub(" ", s)
    s = s.replace("n't", " n't").replace("didn't", "did n't")
    return re.findall(r"[A-Za-z][A-Za-z'\-]*|[0-9]+", s)


def _is_verb_form(w: str) -> bool:
    lw = w.lower()
    return lw in IRREG or lw.endswith("ed") or lemma(lw) in DITRANS


def _later_s_verb(tokens, k) -> bool:
    """Is a later word the -s verb (the academic affairs clerk gives the ...)?"""
    while k < len(tokens):
        lw = tokens[k].lower()
        if lw in DET or lw in PREP or lw in AUX or lw in NEG:
            return False
        if lw.endswith("s") and not lw.endswith("ss") and (k + 1 >= len(tokens) or tokens[k + 1].lower() in DET):
            return True
        k += 1
    return False


def _np(tokens: List[str], i: int) -> Tuple[str, int]:
    """A noun phrase from i: determiners dropped, words up to the next
    function word; 'of' joins (the head of the team)."""
    out: List[str] = []
    start = i
    while i < len(tokens):
        w = tokens[i]
        lw = w.lower()
        if lw in DET:
            if out:
                break          # a new determiner starts the next noun phrase
            i += 1
            continue
        if lw == "in" and out and i + 1 < len(tokens) and tokens[i + 1].lower() == "chief":
            out += ["in", "chief"]
            i += 2
            continue
        if lw == "of" and out and i + 1 < len(tokens):
            out.append(lw)
            i += 1
            continue
        if lw in PREP or lw in AUX or lw in NEG or lw in _REL or lw in ADV and not w[0].isupper():
            break
        nxt = tokens[i + 1].lower() if i + 1 < len(tokens) else ""
        if out and _is_verb_form(w) and not w[0].isupper() and lw not in ("report", "record", "document", "note") \
                and (lw.endswith("ed") or lw in IRREG and IRREG[lw] != lw
                     or not (nxt in PREP or nxt in AUX or nxt in NEG or nxt in (".", ""))):
            break          # a verb-looking word ending a noun phrase is its head noun (the boarding pass is)
        if start == 0 and out and lw.endswith("s") and not lw.endswith("ss") and nxt and nxt not in PREP and nxt not in AUX \
                and nxt not in NEG and not _is_verb_form(nxt) and nxt not in (".",) \
                and not _later_s_verb(tokens, i + 1):
            break          # present tense: the baker places the bread / places food

        out.append(w)
        i += 1
    return " ".join(out), i


def norm(np: str) -> str:
    """Comparison key for an English noun phrase."""
    np = re.split(r"\b(?:with|without|that|which)\b", np.lower().replace("in chief", "in_chief"))[0]
    np = re.sub(r"^.*\b\w+(?:'s|s') ", "", np)             # the customer's PIN -> PIN
    words = [w for w in re.findall(r"[a-z0-9_]+", np) if w not in DET and w != "s"]
    return " ".join(lemma_noun(w) for w in words)


def lemma_noun(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _pseudo_cleft(toks, low):
    """The person/one/thing (that) X V-ed was Y, What X V-ed was Y  ->  X V-ed Y.

    Rewritten into the plain clause and read by `read`, so auxiliaries, negation,
    particles and to/for-recipients inside the body read as they do anywhere."""
    if len(low) < 4:
        return None
    if low[0] == "what":
        s = 1
    elif low[0] == "the" and low[1] in ("person", "one", "thing", "people", "item", "document", "man", "woman", "things", "ones"):
        s = 2
    else:
        return None
    k = next((i for i in range(len(low) - 1, s, -1) if low[i] in ("was", "were", "is", "are")
              and not (i + 1 < len(low) and (low[i + 1].endswith("ed") or low[i + 1] in IRREG))), None)
    if k is None or k + 1 >= len(low):
        return None
    body, y = toks[s:k], " ".join(toks[k + 1:]).rstrip(".!?")
    if body and body[0].lower() in ("who", "that", "which", "whom"):
        body = body[1:]
        if body and (body[0].lower() in AUX or body[0].lower() in NEG or _is_verb_form(body[0])):
            return read(y + " " + " ".join(body))      # the person who called Alice was Bob
    if len(body) < 2:
        return None
    blow = [w.lower() for w in body]
    _, i = _np(body, 0)
    while i < len(blow) and (blow[i] in AUX or blow[i] in NEG or blow[i] in ADV):
        i += 1
    if i >= len(blow):
        return None
    i += 1
    if i < len(blow) and blow[i] in PARTICLES and blow[i] not in ("to", "for"):
        i += 1
    return read(" ".join(body[:i] + [y] + body[i:]))


def read(sentence: str) -> Optional[Frame]:
    toks = _tokens(sentence)
    if not toks:
        return None
    low = [t.lower() for t in toks]
    pc = _pseudo_cleft(toks, low)
    if pc:
        return pc
    # X was the one who V Y  ->  X V Y
    for w in ("one", "person"):
        for r in ("who", "that"):
            for b in ("was", "is", "were"):
                pat = [b, "the", w, r]
                for i in range(1, len(low) - 4):
                    if low[i:i + 4] == pat:
                        return read(" ".join(toks[:i] + toks[i + 4:]))
    negated = any(t in NEG for t in low)
    # cleft: It was X who/that ...
    focus = ""
    if low[:2] in (["it", "was"], ["it", "is"], ["it", "wasn't"]) or (low[0] == "it" and low[1] in ("was", "is")):
        j = 2
        if j < len(low) and low[j] in NEG:
            j += 1
        focus, k = _np(toks, j)
        if k < len(low) and low[k] in _REL:
            toks, low = toks[k + 1:], low[k + 1:]
            negated = negated or any(t in NEG for t in low)
        else:
            focus = ""
    # find the main verb: first verb-ish token after the subject NP
    subj, i = ("", 0) if focus else _np(toks, 0)
    passive = False
    while i < len(low) and (low[i] in AUX or low[i] in NEG or low[i] in ADV):
        if low[i] in ("was", "were", "is", "are", "been", "be") and i + 1 < len(low):
            nxt = low[i + 1] if low[i + 1] not in NEG else (low[i + 2] if i + 2 < len(low) else "")
            if nxt in IRREG and (IRREG[nxt] != nxt or "by" in low) or nxt.endswith("ed"):
                passive = True
        i += 1
    if i >= len(low):
        return None
    verb = lemma(low[i])
    i += 1
    # phrasal verb: hand out, pick up, call on, give back
    if i < len(low) and low[i] in PARTICLES and not (i + 1 < len(low) and low[i + 1] in DET and low[i] in ("in", "on", "over") and verb not in ("call", "turn", "hand")):
        verb = verb + " " + low[i]
        i += 1
    agent = patient = recipient = ""
    if passive:
        patient = subj
        rest = low[i:]
        j = i
        while j < len(low):
            if low[j] in ("in", "on", "into", "onto", "at") and not recipient and patient and not (j + 1 < len(low) and low[j + 1] == "chief"):
                recipient, j = _np(toks, j + 1)
                continue
            if low[j] == "by":
                agent, j = _np(toks, j + 1)
                continue
            if low[j] in ("to", "for") and not recipient:
                recipient, j = _np(toks, j + 1)
                continue
            if not recipient and low[j] not in PREP and low[j] not in ADV and verb in DITRANS and j == i:
                # "Taro was given the documents": subject was the recipient
                np_, jj = _np(toks, j)
                if np_:
                    recipient, patient = subj, np_
                    j = jj
                    continue
            j += 1
    else:
        agent = focus or subj
        np1, j = _np(toks, i)
        # a particle after the object: gave the key back, picked her mother up
        if j < len(low) and low[j] in PARTICLES and " " not in verb and (
                j + 1 >= len(low) or low[j + 1] in PREP or low[j + 1] in (".",)):
            verb = verb + " " + low[j]
            j += 1
        np2 = ""
        base = verb.split()[0]
        if np1 and j < len(low) and low[j] not in PREP and base in DITRANS:
            np2, j = _np(toks, j)
        # bare ditransitive: gave the patient medicine / gave Alice flowers
        if not np2 and base in DITRANS and np1 and " " in np1:
            w = np1.split()
            if w[0][0].isupper() and w[-1][0].islower() or w[0].lower() in ANIMATE and len(w) == 2:
                np1, np2 = w[0], " ".join(w[1:])
        if np2:
            recipient, patient = np1, np2
        else:
            patient = np1
        while j < len(low):
            if low[j] in ("to", "for") and not recipient:
                recipient, j = _np(toks, j + 1)
                continue
            if low[j] in ("in", "on", "into", "onto", "at") and not recipient and patient:
                # where the thing goes: Japanese marks it with に like a recipient
                recipient, j = _np(toks, j + 1)
                continue
            if low[j] == "with" and not recipient and base in ("share", "discuss", "consult", "leave"):
                recipient, j = _np(toks, j + 1)
                continue
            if low[j] in ("about", "of") and base in ("tell", "inform", "notify", "remind", "warn", "ask"):
                # told Tanaka about the change: the object was the recipient
                rec = patient
                patient, j = _np(toks, j + 1)
                recipient = recipient or rec
                continue
            j += 1
    if focus and passive:
        agent = agent or focus
    return Frame(predicate=verb, agent=agent, patient=patient, recipient=recipient, negated=negated)


_PAST = {v: k for k, v in []}


def past(verb: str) -> str:
    for form, base in IRREG.items():
        pass
    inv = {}
    for line in _IRR.replace("\n", "").split("|"):
        p = line.split()
        if len(p) == 3:
            inv[p[0]] = p[1]
    if verb in inv:
        return inv[verb]
    if verb.endswith("e"):
        return verb + "d"
    if re.search(r"[^aeiou]y$", verb):
        return verb[:-1] + "ied"
    if re.fullmatch(r"[^aeiou]*[aeiou][^aeiouwxy]", verb):
        return verb + verb[-1] + "ed"
    return verb + "ed"


def realize(fr: Frame, *, past_tense: bool = True) -> str:
    """Plain active English: Agent (did not) verb recipient? patient (to …)."""
    art = lambda np: np if not np or np[0].isupper() or np.lower().startswith(("the ", "a ", "an ")) else "the " + np  # noqa: E731
    v = fr.predicate
    head = ("did not " + v) if fr.negated else (past(v) if past_tense else v)
    parts = [fr.agent or "someone", head]
    if fr.patient:
        parts.append(art(fr.patient))
    if fr.recipient:
        parts.append("to " + art(fr.recipient))
    s = " ".join(parts)
    return s[0].upper() + s[1:] + "."


def vkey(v: str) -> str:
    """Verb comparison key: the silent e is not recoverable by rule (invited ->
    invit|invite; visited -> visit), so both sides drop it."""
    parts = v.lower().split()
    if not parts:
        return ""
    head = lemma(parts[0]).rstrip("e")
    # a preposition that only marks the object (wait for, look at) is not part of the event
    rest = [w for w in parts[1:] if w not in ("for", "at", "about", "with")]
    return " ".join([head] + rest)


def key(fr: Optional[Frame]) -> Optional[tuple]:
    """Language-neutral comparison key. With a single non-agent participant,
    which slot it takes is a surface fact of each language (整備士に警告する /
    warn the mechanic), so it is always the patient."""
    if not fr:
        return None
    patient, recipient = norm(fr.patient), norm(fr.recipient)
    if recipient and not patient:
        patient, recipient = recipient, ""
    return (vkey(fr.predicate), norm(fr.agent), patient, recipient, fr.negated)


def regression() -> Dict[str, object]:
    want = ("giv", "hanako", "document", "taro", False)
    same = ["Hanako gave Taro the documents.", "Hanako gave the documents to Taro.",
            "The documents were given to Taro by Hanako.", "It was Hanako who gave Taro the documents."]
    got = {s: key(read(s)) for s in same}
    checks = {"para_%d" % i: got[s] == want for i, s in enumerate(same)}
    checks["negation"] = key(read("Hanako did not give Taro the documents.")) == ("giv", "hanako", "document", "taro", True)
    checks["swap"] = key(read("Taro gave Hanako the documents.")) == ("giv", "taro", "document", "hanako", False)
    fr = read("Hanako gave Taro the documents.")
    checks["realize_roundtrip"] = key(read(realize(fr))) == want
    checks["phrasal"] = key(read("The teacher handed out assignments to the students.")) == ("hand out", "teacher", "assignment", "student", False)
    checks["bare_ditrans"] = key(read("The doctor gave the patient medicine.")) == ("giv", "doctor", "medicine", "patient", False)
    checks["tell_about"] = key(read("Suzuki told Tanaka about the meeting change.")) == ("tell", "suzuki", "meeting change", "tanaka", False)
    checks["share_with"] = key(read("Kenta shared the documents with Maya.")) == ("shar", "kenta", "document", "maya", False)
    checks["pseudo_cleft"] = key(read("The person Alice invited was Mari.")) == ("invit", "alice", "mari", "", False)
    checks["single_participant"] = key(Frame("warn", "Suzuki", "", "Sato", True)) == key(read("Suzuki did not warn Sato."))
    checks["submit"] = key(read("Sato submitted the report to the manager.")) == ("submit", "sato", "report", "manager", False)
    return {"all_pass": all(checks.values()), **checks, "_got": {s: g for s, g in got.items() if g != want}}

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


_TIME = re.compile(r"\b(?:yesterday|today|tonight|tomorrow|(?:this|last|every|each|next) (?:morning|afternoon|evening|night|week|month|day|year|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
                   r"|(?:in|during) the (?:morning|afternoon|evening|night)|every day|daily|at night|at (?:noon|midnight|dawn|dusk|sunrise|sunset)"
                   r"|(?:on|every|last|next) (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?"
                   r"|(?:in|on|by|until|since|during|before|after) (?:january|february|march|april|may|june|july|august|september|october|november|december)(?: [0-9]{1,2})?(?:,? [0-9]{4})?"
                   r"|(?:in|by|since|until) [0-9]{4}|at [0-9]{1,2}(?::[0-9]{2})? ?(?:am|pm|o'clock)?)\b", re.I)


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


def _pseudo_cleft(toks, low, diag=None):
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
    if not y or not (y[0].isupper() or y.split()[0].lower() in DET):
        return None            # a pseudo-cleft names its focus (was Mari / was the report); 'was kind' is a relative clause + predicate
    if body and body[0].lower() in ("who", "that", "which", "whom"):
        body = body[1:]
        if body and (body[0].lower() in AUX or body[0].lower() in NEG or _is_verb_form(body[0])):
            return _read_core(y + " " + " ".join(body), diag)      # the person who called Alice was Bob
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
    return _read_core(" ".join(body[:i] + [y] + body[i:]), diag)


def _read_core(sentence: str, diag: Optional[List[str]] = None) -> Optional[Frame]:
    toks = _tokens(sentence)
    if not toks:
        return None
    low = [t.lower() for t in toks]
    pc = _pseudo_cleft(toks, low, diag)
    if pc:
        return pc
    # X was the one who V Y  ->  X V Y
    for w in ("one", "person"):
        for r in ("who", "that"):
            for b in ("was", "is", "were"):
                pat = [b, "the", w, r]
                for i in range(1, len(low) - 4):
                    if low[i:i + 4] == pat:
                        return _read_core(" ".join(toks[:i] + toks[i + 4:]), diag)
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
    if diag is not None:
        why = _verb_token_problem(low, i)
        if why:
            diag.append(why)
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



# ---------------------------------------------------------------------------------------------------------------------
# W1-a: what the Frame cannot say. A Frame is (predicate, agent, patient, recipient, negated): it has no place for a
# quantifier's scope, a relative clause, a causee, a comparison standard or a subordinate clause. A sentence that
# carries one of those is NOT read into a Frame that silently drops it (No engineer updated every server -> negated=False,
# The manager made the intern rewrite the report -> recipient='intern rewrite'): read_typed returns (None, reasons).
# Unknown is not false: the reason says which structure was recognised and left unread.
# ---------------------------------------------------------------------------------------------------------------------
_NEG_QUANT = {"no", "nobody", "nothing", "none", "neither", "nor", "never", "nowhere", "noone", "rarely", "seldom", "hardly", "barely",
              "scarcely"}
_CONJ = {"and", "or", "but", "yet"}
_QUANT = {"every", "each", "all", "some", "any", "most", "few", "many", "several", "both", "everyone", "everybody",
          "everything", "someone", "somebody", "something", "anyone", "anybody", "anything", "either", "fewer", "much"}
_NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
                 "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
                 "eighty", "ninety", "hundred", "thousand", "million", "billion", "dozen", "zero"}
_CAUS_MATRIX = {"make", "made", "making", "makes", "let", "lets", "letting", "have", "had", "has", "having", "get", "got",
                "gets", "getting", "help", "helped", "helps", "helping"}
_SUBORD = {"although", "though", "because", "since", "when", "whenever", "while", "whilst", "if", "unless", "until", "whereas",
           "once", "whether", "so"}
_CLAUSE_PREP = {"after", "before"}
_RELATIVE = {"who", "whom", "whose", "which"}
# Comparative / superlative adjectives written with -er/-est. Criterion: the closed class of common gradable adjectives that
# inflect (one syllable, or two syllables ending in -y/-le/-ow/-er), taken from general English, not from any test sentence.
# The suffix test alone would catch nouns (manager, request, winter), so a stem must be in the class; an inflected form of an
# adjective outside the class is not recognised as a comparison (the sentence is then simply not flagged by this test).
_ADJ_STEMS = {
    # size / dimension
    "big", "small", "large", "tall", "short", "long", "high", "low", "wide", "narrow", "deep", "shallow", "thick", "thin",
    "broad", "huge", "tiny", "vast", "steep", "flat", "round", "sharp", "blunt", "heavy", "light", "full", "empty",
    # age / speed / time
    "old", "new", "young", "fast", "slow", "quick", "early", "late", "fresh", "ripe", "rapid", "swift",
    # temperature / weather / physical
    "hot", "cold", "warm", "cool", "wet", "dry", "soft", "hard", "smooth", "rough", "tough", "loose", "tight", "clean", "dirty",
    "bright", "dark", "loud", "quiet", "calm", "wild", "mild", "rich", "poor", "cheap", "safe", "weak", "strong", "stiff",
    # evaluation / person
    "good", "bad", "great", "nice", "kind", "rude", "polite", "proud", "brave", "wise", "smart", "clever", "silly", "lazy", "busy",
    "happy", "sad", "angry", "easy", "simple", "gentle", "noisy", "tasty", "healthy", "lucky", "pretty", "ugly", "funny",
    "tidy", "messy", "crazy", "shiny", "sunny", "windy", "rainy", "cloudy", "dusty", "hungry", "thirsty", "friendly", "lovely",
    # distance
    "near", "far", "close",
}
_COMP_IRREG = {"better", "worse", "best", "worst", "further", "furthest", "farther", "farthest", "less", "least", "more", "most"}


def _stem_ok(stem: str) -> bool:
    return stem in _ADJ_STEMS or stem + "e" in _ADJ_STEMS or (len(stem) > 2 and stem[-1] == stem[-2] and stem[:-1] in _ADJ_STEMS) \
        or (stem.endswith("i") and stem[:-1] + "y" in _ADJ_STEMS)


def _is_comparative_form(w: str) -> bool:
    if w in _COMP_IRREG:
        return True
    for suf in ("est", "er"):
        if w.endswith(suf) and len(w) > len(suf) + 1 and _stem_ok(w[: -len(suf)]):
            return True
    return False


def _cleft_like(low) -> bool:
    """Clefts and pseudo-clefts are read by the existing rules; their who/that/what are not relative clauses."""
    if low[:1] == ["what"]:
        return True
    if len(low) > 3 and low[0] == "the" and low[1] in ("person", "one", "thing", "people", "item", "document", "man", "woman", "things", "ones"):
        return True
    if low[:1] == ["it"] and len(low) > 1 and low[1] in ("was", "is", "wasn't"):
        return True
    for w in ("one", "person"):
        for i in range(1, len(low) - 3):
            if low[i:i + 3] == ["the", w, low[i + 2]] and low[i + 2] in ("who", "that") and low[i - 1] in ("was", "is", "were"):
                return True
    return False


def _unread_reasons(sentence: str) -> Tuple[str, ...]:
    toks = _tokens(sentence)
    low = [t.lower() for t in toks]
    if not low:
        return ()
    cleft = _cleft_like(low)
    reasons: List[str] = []
    if any(w in _NEG_QUANT for w in low) or any(low[i] == "no" or (low[i] == "not" and i + 1 < len(low) and low[i + 1] in ("every", "all", "any", "each")) for i in range(len(low))):
        reasons.append("negative quantifier or never: scope not representable")
    if any(w in _QUANT for w in low) or any(w in ("exactly", "precisely", "approximately", "only", "just", "least", "most") and i + 1 < len(low) and (low[i + 1].isdigit() or low[i + 1] in _NUMBER_WORDS) for i, w in enumerate(low)) \
            or any(low[i:i + 2] in (["at", "least"], ["at", "most"], ["more", "than"], ["fewer", "than"]) for i in range(len(low) - 1)) \
            or any(w.isdigit() and i > 0 and low[i - 1] in ("exactly", "least", "most", "than") for i, w in enumerate(low)):
        reasons.append("quantifier: scope not representable")
    if not cleft:
        if any(w in _RELATIVE for w in low):
            reasons.append("relative clause: not representable")
        for i, w in enumerate(low):
            if w == "that" and i > 0 and low[i - 1] not in PREP:
                reasons.append("relative or complement clause: not representable")
                break
    # causative: make/let/have/get/help + NP + bare verb | NP + to + verb (the NP is one or two words)
    for i, w in enumerate(low):
        if w not in _CAUS_MATRIX:
            continue
        j = i + 1
        while j < len(low) and low[j] in DET:
            j += 1
        hit = False
        for end in (j + 1, j + 2):
            if end >= len(low):
                continue
            if end == j + 2 and (low[j + 1] in DET or low[j + 1] in PREP or low[j + 1] in AUX):
                continue                     # <name> a <noun>: a second noun phrase, not a verb
            nxt = low[end]
            if nxt == "to":
                after = low[end + 1] if end + 1 < len(low) else ""
                hit = bool(after) and after not in DET and after not in PREP and not toks[end + 1][0].isupper()
            elif (nxt not in DET and nxt not in PREP and nxt not in AUX and nxt not in NEG and nxt not in ADV
                  and nxt not in ("and", "or", "but") and lemma(nxt) == nxt and not nxt.endswith(("s", "ed", "ing"))
                  and w not in ("get", "got", "gets", "getting")):
                hit = True
            if hit:
                break
        if hit:
            reasons.append("causative: causee not representable")
            break
    # reduced relative clause (the password the user forgot): <det> <noun> <det> <noun> with no verb in between
    if len(low) > 3 and low[0] in DET and low[2] in DET and low[1] not in AUX and low[1] not in PREP and not _is_verb_form(toks[1]):
        reasons.append("relative clause (reduced): not representable")
    # infinitival complement / object control (told X to rest, wanted X to leave): to + a lowercase bare verb
    for i, w in enumerate(low[:-1]):
        if w == "to" and i > 0:
            after = low[i + 1]
            if (after not in DET and after not in PREP and after not in AUX and after not in NEG and not toks[i + 1][0].isupper()
                    and lemma(after) == after and not after.endswith(("s", "ed", "ing")) and after not in ADV):
                reasons.append("infinitive complement: not representable")
                break
    # coordination of clauses or noun phrases
    if any(w in _CONJ for w in low):
        reasons.append("coordination: not representable")
    # comparison
    if "than" in low or any(low[i] == "as" and "as" in low[i + 2:] for i in range(len(low))) or any(_is_comparative_form(w) for w in low):
        reasons.append("comparison: standard/degree not representable")
    # modal verbs state possibility/obligation/ability: the Frame would assert the event as having happened
    if any(w in _MODALS for w in low):
        reasons.append("modal verb: not representable")
    # a focus/scalar word attaches to a constituent whose scope the Frame cannot hold (Only Sam signed; Sam even signed)
    if any(w in _FOCUS for w in low):
        reasons.append("focus word: scope not representable")
    # a sentence opening with a negative word is a negated constituent (Not a single engineer ...), not a negated verb
    if low[0] in NEG:
        reasons.append("negated constituent: scope not representable")
    # 'as': an as-clause (Sam left as Pat arrived) or an as-phrase (worked as a clerk); the as...as comparison is flagged above
    if "as" in low and "comparison: standard/degree not representable" not in reasons:
        reasons.append("as-clause or as-phrase: not representable")
    # subordinate clause
    if any(w in _SUBORD for w in low):
        reasons.append("subordinate clause: not representable")
    else:
        for i, w in enumerate(low):
            if w in _CLAUSE_PREP:
                _np_text, j = _np(toks, i + 1)
                if _np_text and j < len(low) and (low[j] in AUX or low[j] in NEG or _is_verb_form(toks[j]) ):
                    reasons.append("subordinate clause: not representable")
                    break
    return tuple(dict.fromkeys(reasons))


_BE = {"was", "were", "is", "are", "am", "be", "been", "being"}
_MODALS = {"may", "might", "could", "should", "must", "ought", "shall", "would", "can", "cannot"}
_FOCUS = {"only", "just", "even", "also", "merely", "solely", "simply", "especially", "mainly", "mostly", "particularly", "too",
          "either", "neither", "both", "single", "alone", "nearly", "almost", "roughly", "approximately", "barely", "exactly", "precisely"}
_NUMERALS = _NUMBER_WORDS | {"another", "other", "couple", "pair", "dozens", "half", "double", "triple", "numerous", "multiple",
                             "various", "several", "countless"}
_NP_CONJ = _SUBORD | {"as", "than", "and", "or", "but", "yet", "nor", "then"}
_PRONOUN = {"he", "she", "they", "we", "i", "you", "it", "him", "her", "them", "us", "me", "who", "whom"}
# Verbs of perception/keeping/letting whose object may be followed by a bare or -ing verb (heard the alarm ring/ringing).
_COMPLEMENT_MATRIX = {"see", "watch", "hear", "notice", "observe", "feel", "find", "catch", "leave", "keep", "smell", "spot", "start", "stop",
                      "imagine", "let", "have", "help", "get", "make"}
_ED_NOT_VERB = {"shed", "sled", "shred", "need", "feed", "seed", "weed", "speed", "breed", "hundred", "indeed",
                "proceed", "succeed", "exceed", "thread", "bread", "spread", "head", "instead", "dead", "tread", "naked", "wicked", "sacred"}
# Verbs that take an object plus a predicate of it (a small clause / resultative / factitive: painted the room blue, found the
# task easy, named Pat chair, made Sam the leader, kept the players running). The Frame has no place for that second predicate.
_SMALL_CLAUSE_MATRIX = {"make", "name", "call", "elect", "appoint", "consider", "declare", "find", "leave", "keep", "paint", "drive",
                        "render", "hold", "turn", "dye", "colour", "color", "proclaim", "crown", "label", "deem", "judge", "think"}
# Verbs of changing the form/format/category of the object: the to/into phrase is the RESULT, never a recipient (convert X to Y).
# Class: conversion between formats/languages, transformation, partition/grouping, re-labelling. Not a list of any test verb.
_RESULT_CHANGE_VERBS = {"convert", "translate", "turn", "change", "transform", "split", "divide", "group", "sort", "reduce", "compress",
                        "rewrite", "reshape", "resize", "refactor", "rename", "reclassify", "categorize", "categorise", "classify",
                        "cut", "break", "fold", "merge", "combine", "shape", "form", "develop", "grow", "upgrade", "downgrade",
                        "promote", "demote", "reduce", "expand", "shrink", "summarize", "summarise", "paraphrase", "recode", "encode",
                        "decode", "parse", "format", "reformat", "render"}
_IRREG_NOUNISH = {"left", "saw", "rose", "lay", "spoke", "fell", "wound", "bit", "bore", "wore"}


def _root(w: str) -> str:
    """Verb root as the Frame spells it (the silent e is not recoverable by rule: named -> nam)."""
    return lemma(w).rstrip("e")


def _is_participle(w: str) -> bool:
    """A past/participle verb form (written, sold, arrested): -ed or an irregular non-base form; not a noun that looks like one."""
    if w in _ED_NOT_VERB or w in _IRREG_NOUNISH:
        return False
    return (w in IRREG and IRREG[w] != w) or (w.endswith("ed") and len(w) > 3)


def _verb_token_problem(low: List[str], i: int) -> str:
    """Is the token chosen as the main verb a verb? A copular/adjectival predicate (The report was long, Sam is an engineer), a
    determiner/preposition taken for a verb (Not a single engineer ...: 'a'), or a bare word with no verb form and no auxiliary
    in front of it is not a verb the Frame can state."""
    w = low[i]
    if w in DET or w in PREP or w in NEG or w in _REL:
        return "predicate is not a verb"
    j = i - 1
    while j >= 0 and (low[j] in NEG or low[j] in ADV):
        j -= 1
    prev_aux = low[j] if j >= 0 and low[j] in AUX else ""
    if prev_aux in _BE:
        return "" if _is_participle(w) else "copular/adjectival predicate: not representable"
    if prev_aux:
        return ""
    morph = w in IRREG or _is_participle(w) or (w.endswith("s") and not w.endswith("ss") and len(w) > 3)
    return "" if morph else "verb form not recognised"


def _np_problem(np: str, predicate: str) -> str:
    """A role must be a noun phrase: no numeral/focus word/conjunction/modal, no pronoun or Name after a lower-case noun (a reduced
    relative: the book Sam wrote), no participle closing it (the report written ...), and no gerund after a verb of perception or
    keeping (kept the players running)."""
    words = np.split()
    if not words:
        return ""
    low = [w.lower() for w in words]
    for w in low:
        if w.isdigit() or w in _NUMERALS or w.split("-")[0] in _NUMERALS:
            return "numeral inside a role: quantity not representable"
        if w in _FOCUS:
            return "focus word inside a role"
        if w in _NP_CONJ or w in _MODALS:
            return "conjunction or modal inside a role"
    for k in range(1, len(words)):
        if low[k] in _PRONOUN or (words[k][0].isupper() and words[k - 1][0].islower()):
            return "reduced relative clause or apposition inside a role"
    if _is_participle(low[-1]):
        return "participle closes a role: reduced relative clause or clause fragment"
    if len(words) >= 2 and low[-1].endswith("ing") and _root(predicate.split()[0]) in {x.rstrip("e") for x in _COMPLEMENT_MATRIX}:
        return "participial complement of a verb of perception/keeping"
    return ""


def _frame_problems(sentence: str, frame: Frame) -> Tuple[str, ...]:
    """Positive check on a Frame that was read: every role is a noun phrase, and every content word of the sentence is the
    predicate or inside a role (a word that is neither was dropped silently: Sam saw the man the police arrested -> man)."""
    reasons: List[str] = []
    for np in (frame.agent, frame.patient, frame.recipient):
        why = _np_problem(np, frame.predicate)
        if why:
            reasons.append(why)
    toks = _tokens(sentence)
    low = [t.lower() for t in toks]
    head = _root(frame.predicate.split()[0]) if frame.predicate.split() else ""
    if head in {x.rstrip("e") for x in _SMALL_CLAUSE_MATRIX} and (len(frame.patient.split()) >= 2 or (frame.patient and frame.recipient)):
        reasons.append("object + predicate of the object (small clause): not representable")
    if head in {x.rstrip("e") for x in _COMPLEMENT_MATRIX} and len(frame.patient.split()) >= 2:
        reasons.append("object followed by a bare or -ing verb (perception/keeping complement): not representable")
    if head in {x.rstrip("e") for x in _RESULT_CHANGE_VERBS} and frame.recipient and frame.patient:
        reasons.append("to/into phrase of a verb of change is a result, not a recipient")
    if low and not _cleft_like(low):
        v = next((k for k, t in enumerate(low) if lemma(t) == frame.predicate.lower().split()[0] and t not in AUX and t not in DET), None)
        if v is not None and any(t in AUX or t in _BE for t in low[v + 1:]):
            reasons.append("clause after the verb (embedded clause): not representable")
    if low:
        pred = frame.predicate.lower().split()
        covered = {w.lower() for np in (frame.agent, frame.patient, frame.recipient) for w in np.split()}
        function = DET | AUX | NEG | PREP | ADV | set(pred[1:]) | {"it", "there"}
        if _cleft_like(low):
            function |= _REL | {"that", "what", "person", "one", "thing", "people", "item", "document", "man", "woman", "things", "ones"}
        for t in low:
            if t in function or t in covered or t == pred[0] or lemma(t) == pred[0]:
                continue
            reasons.append("content not represented in the frame: " + t)
            break
    return tuple(dict.fromkeys(reasons))


def read_typed(sentence: str) -> Tuple[Optional[Frame], Tuple[str, ...]]:
    """(Frame | None, reasons). None with reasons: a structure the Frame cannot represent was recognised and left unread
    (not "false": the sentence says more than a Frame can hold). None with no reasons: nothing was recognised at all."""
    reasons = _unread_reasons(sentence)
    if reasons:
        return None, reasons
    diag: List[str] = []
    frame = _read_core(sentence, diag)
    if frame is None:
        return None, ()
    why = tuple(dict.fromkeys(diag)) + _frame_problems(sentence, frame)
    if why:
        return None, why
    return frame, ()


def read(sentence: str) -> Optional[Frame]:
    return read_typed(sentence)[0]


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

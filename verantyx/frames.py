"""One event frame per sentence, the same for every paraphrase of it.

PREREGISTERED_2026-09-27_frames. Typed edges keep the surface cases (が/を/
に/は); a reader of meaning needs the roles behind them, which the surface
moves around:

    花子が太郎に資料Aを渡した          active
    資料Aが花子によって太郎に渡された    passive: が is the patient, によって the agent
    資料Aは花子が渡した                は takes the role left open
    資料Aを太郎に渡したのは花子だ       cleft: the focus fills the open role
    社長が資料をお渡しになった          honorific お〜になる: the verb is 渡す

All of them become  渡す(agent=花子, patient=資料A, recipient=太郎).
Rules only, read by position.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

from .typed_edges import _base, _negated, _tagger

_REN2DIC = {"し": "す", "り": "る", "き": "く", "ち": "つ", "み": "む", "び": "ぶ",
            "ぎ": "ぐ", "い": "う", "に": "ぬ"}


#: Formal nouns carry a clause, not a participant (信じることになる).
_FORMAL = {"たび", "度", "こと", "事", "もの", "物", "ため", "はず", "わけ", "ところ", "とき", "時",
           "ほう", "方", "よう", "まま", "つもり", "の", "うち", "間", "際", "ごと"}


#: Converse pairs: the receiving verb is the giving verb seen from the other
#: end. X が Y から Z を受け取る == Y が X に Z を渡す.
CONVERSE = {"聞く": "伝える", "受け取る": "渡す", "もらう": "あげる", "貰う": "あげる", "借りる": "貸す",
            "預かる": "預ける", "教わる": "教える", "習う": "教える", "受ける": "与える",
            "授かる": "授ける"}


#: Role nouns that stand in apposition before a name: 父の修, 医師の小林.
ROLES = {"父", "母", "祖父", "祖母", "兄", "姉", "弟", "妹", "息子", "娘", "夫", "妻",
         "叔父", "叔母", "伯父", "伯母", "孫", "友人", "同僚", "上司", "部下", "先輩", "後輩",
         "医師", "教師", "先生", "患者", "看護師", "社長", "部長", "課長", "係長", "班長",
         "工員", "作業員", "技師", "検査員", "店員", "店長", "運転手", "記者", "選手", "監督",
         "理学療法士", "薬剤師", "教授", "助手", "学生", "生徒", "担任", "校長", "住民", "職員",
         "消防士", "警察官", "司書", "船長", "漁師", "農家", "料理人", "シェフ", "指揮者"}


_PERSON_SUFFIX = ("士", "生", "主", "医", "者", "人", "手", "員", "民", "師", "長", "係",
                  "官", "家", "将", "婦", "夫", "母", "父", "兄", "姉", "弟", "妹", "娘", "子供")


def _learned_roles() -> set:
    import json
    from pathlib import Path
    p = Path(__file__).with_name("lang_data") / "roles_learned.json"
    try:
        import re
        return {w for w in json.loads(p.read_text())["roles"] if re.fullmatch(r"[ァ-ヺー]{3,}", w)}
    except Exception:
        return set()


_LEARNED = _learned_roles()


def is_role(w: str) -> bool:
    """A person-role noun: the closed list, a word ending in a person suffix
    (整備士, 研修生, 牧場主, 市役所職員), or a katakana occupation the corpus
    wrote before a name (コーチ, アナウンサー)."""
    return bool(w) and (w in ROLES or w.endswith(_PERSON_SUFFIX) or w in _LEARNED)


def _causative(verb: str) -> str:
    from .realize import _A, _class
    c = _class(verb)
    if c == "suru":
        return verb[:-2] + "させる"
    if c == "kuru":
        return "来させる"
    if c == "ichidan":
        return verb[:-1] + "させる"
    return verb[:-1] + _A.get(verb[-1], "") + "せる" if verb[-1] in _A else verb


def _load_trans():
    import json
    from pathlib import Path
    try:
        return json.loads((Path(__file__).with_name("lang_data") / "transitivity.json").read_text())["wo_rate"]
    except Exception:
        return {}


_TRANS = _load_trans()


def transitivity(verb: str) -> str:
    """From the corpus: the share of a verb's case edges that are を.
    >=0.2 transitive (置く .35, 持つ .69), <=0.05 intransitive (濡れる .03)."""
    r = _TRANS.get(verb)
    if r is None:
        return "unknown"
    return "trans" if r >= 0.2 else "intrans" if r <= 0.05 else "unknown"


_GEN_CON = None


def attested(verb: str, rel: str, noun: str) -> bool:
    """Has the corpus (general store) ever put this noun in this role of this
    verb? The only honest test of whether a relative clause's head fills a
    gap (玄関に置いた傘: 傘を置く is written) or is an outer head (電車が走る
    音: 音を走る is not)."""
    global _GEN_CON
    import os
    import sqlite3
    from pathlib import Path
    if _GEN_CON is None:
        p = Path(os.environ.get("VERA_GENERAL", Path.home() / "Projects" /
                                "vera-corpus" / "build" / "general.db"))
        if not p.exists():
            return False
        _GEN_CON = sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False)
    # two independent sources, as for any answer: one line can be a misread
    # (太鼓の音を背に…走りました once gave 音を走る)
    return _GEN_CON.execute(
        "SELECT count(DISTINCT src) FROM (SELECT src FROM tedges WHERE head=? AND rel=? AND dep=? LIMIT 50)",
        (verb, rel, noun)).fetchone()[0] >= 2


def canonical(name: str) -> str:
    """Convention-neutral participant key: 小林医師 / 医師の小林 / 小林 -> 小林.

    The role suffix is stripped only for 名前（固有名詞）＋役職: the suffix must
    start on a morpheme boundary and the morpheme before it must be a proper
    noun. Otherwise the written form is the key as it is (W3-f1, K340): a kinship
    word of two characters is one word, not a name plus a role."""
    for r in sorted(ROLES, key=len, reverse=True):
        if name.endswith(r) and len(name) > len(r):
            cut, end, last = len(name) - len(r), 0, None
            for tok in _tagger()(name):
                end += len(tok.surface)
                if end == cut:
                    last = tok
                    break
                if end > cut:
                    break
            if last is not None and last.feature.pos2 == "固有名詞":
                return name[:cut]
            return name
    if "の" in name:
        left, right = name.rsplit("の", 1)
        if is_role(left.split("の")[-1]):
            return right
    return name


def _is_verb_in_noun(toks, j) -> bool:
    """編み方 / 消しゴム: a 連用形 verb glued to a following noun or suffix
    is part of the noun, not a predicate."""
    t = toks[j]
    return (t.feature.pos1 == "動詞" and str(t.feature.cForm).startswith("連用形")
            and j + 1 < len(toks) and toks[j + 1].feature.pos1 in ("名詞", "接尾辞"))


@dataclass
class Frame:
    predicate: str = ""
    agent: str = ""
    patient: str = ""
    recipient: str = ""
    negated: bool = False
    past: bool = False          # not part of the key: tense is not meaning here
    ambiguous: bool = False     # a role was filled by a guess; generation skips it
    inferred: bool = False      # a role came from the topic or a relative head, not a case mark

    def key(self):
        return (self.predicate, self.agent, self.patient, self.recipient, self.negated)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _run_back(toks, j):
    parts = []
    while j >= 0 and (toks[j].feature.pos1 in ("名詞", "接尾辞", "接頭辞")
                      or _is_verb_in_noun(toks, j)
                      or (toks[j].surface == "・" and j > 0 and toks[j - 1].feature.pos1 == "名詞")):
        if toks[j].feature.pos1 == "接頭辞" and toks[j].surface in ("お", "ご", "御"):
            # お弁当 keeps its お; お見せする / お渡しになる do not reach here
            # as a noun (the verb path takes them).
            if not parts:
                break
            parts.insert(0, toks[j])
            j -= 1
            break
        parts.insert(0, toks[j])
        j -= 1
    return parts, j


def _noun_run_back(toks, j) -> str:
    """The noun phrase ending at j, with の-chains (駅前の店の看板) and
    apposition normalized to 名前＋肩書き (医師の小林 -> 小林医師)."""
    parts, j = _run_back(toks, j)
    if not parts:
        return ""
    phrase = "".join(t.surface for t in parts)
    # 新しい手順 / 静かな部屋: a 連体 adjective directly before is part of the NP
    if j >= 0 and toks[j].feature.pos1 == "形容詞" and str(toks[j].feature.cForm).startswith("連体形"):
        phrase = toks[j].surface + phrase
        j -= 1
    elif j >= 1 and toks[j].surface == "な" and toks[j - 1].feature.pos1 == "形状詞":
        phrase = toks[j - 1].surface + "な" + phrase
        j -= 2
    while j >= 1 and toks[j].surface == "の" and toks[j - 1].feature.pos1 in ("名詞", "接尾辞"):
        left, j2 = _run_back(toks, j - 1)
        ltxt = "".join(t.surface for t in left)
        if is_role(ltxt) and not is_role(phrase):
            # apposition (医師の小林, 妹の凛): the participant is the name
            return phrase
        phrase = ltxt + "の" + phrase
        parts, j = left, j2
    return phrase


def _honorific_verb(noun: str) -> str:
    if noun and noun[-1] in _REN2DIC:
        return noun[:-1] + _REN2DIC[noun[-1]]
    return noun + "る"


def _predicates(toks) -> List[tuple]:
    """(index, verb) for every event predicate, in order."""
    preds: List[tuple] = []
    for i, t in enumerate(toks):
        f = t.feature
        if f.pos1 == "動詞":
            b = _base(t)
            if _is_verb_in_noun(toks, i):
                continue
            # お見せする / ご案内する: the humble frame, verb = the inner one
            if i + 1 < len(toks) and i > 0 and toks[i - 1].surface in ("お", "ご") \
                    and _base(toks[i + 1]) in ("する", "いたす", "申し上げる"):
                preds.append((i + 1, b))
                continue
            if b in ("する", "いたす", "申し上げる") and i > 1 and toks[i - 2].surface in ("お", "ご") \
                    and toks[i - 1].feature.pos1 == "動詞":
                continue
            # によって / により: part of the agent marker, not the event
            if b == "よる" and i > 0 and toks[i - 1].surface == "に":
                continue
            # auxiliaries after て (ている, てしまう): not a new event
            if f.pos2 == "非自立可能" and i > 0 and toks[i - 1].surface in ("て", "で"):
                continue
            # お〜になる: the event is the noun's verb
            if b == "なる" and i >= 3 and toks[i - 1].surface == "に" \
                    and toks[i - 3].surface in ("お", "ご") and toks[i - 2].feature.pos1 == "名詞":
                preds.append((i, _honorific_verb(toks[i - 2].surface)))
                continue
            if f.pos2 == "非自立可能" and b in ("する", "できる") and i > 0 \
                    and toks[i - 1].feature.pos1 == "名詞":
                preds.append((i, toks[i - 1].surface + b))
                continue
            # 持ってくる / 連れていく: V-て + くる/いく is one predicate (bring / take)
            if i + 2 < len(toks) and toks[i + 1].surface in ("て", "で") and \
                    _base(toks[i + 2]) in ("来る", "くる", "行く", "いく"):
                tail = "くる" if _base(toks[i + 2]) in ("来る", "くる") else "いく"
                preds.append((i, t.surface + toks[i + 1].surface + tail))
                continue
            preds.append((i, b))
    return preds


def read(sentence: str) -> Optional[Frame]:
    """The frame of the sentence's main (last) predicate."""
    fs = read_all(sentence)
    return fs[-1] if fs else None


def read_all(sentence: str) -> List[Frame]:
    """One frame per clause. Case arguments belong to the clause they sit in
    (after the previous predicate): 猫があくびをし、歯がのぞいた is two events,
    not 猫があくびをのぞく. The は topic spans the sentence and fills a
    clause's open role."""
    toks = list(_tagger()(sentence or ""))
    preds = _predicates(toks)
    out: List[Frame] = []
    prev = -1
    for main, verb in preds:
        out.append(_frame(toks, main, verb, prev))
        prev = main
    out = [f for f in out if f is not None]
    # Tense is the sentence's: 父は江戸へ出て、鮓屋を開き有名となった narrates a
    # past episode even in its て-clauses.
    if out and out[-1].past:
        for f in out:
            f.past = True
    return out


def _frame(toks, main: int, verb: str, prev: int) -> Optional[Frame]:
    n = len(toks)
    # causative: 降らせる / 食べさせる is its own predicate (the causer acts)
    if main + 1 < n and _base(toks[main + 1]) in ("せる", "させる"):
        verb = _causative(verb)
        main += 1
    # passive: れる / られる right after the main verb
    passive_mark = main + 1 < n and _base(toks[main + 1]) in ("れる", "られる")
    # --- arguments before the main predicate --------------------------------
    args: Dict[str, str] = {}
    topic = ""
    by = ""
    skip_noun_end = main - 1 if verb.endswith(("する", "できる")) else -1
    for j in range(main):
        t = toks[j]
        if t.feature.pos1 != "助詞":
            continue
        noun = _noun_run_back(toks, j - 1)
        if not noun or j - 1 == skip_noun_end or noun in _FORMAL:
            continue
        s = t.surface
        if s == "は":
            topic = noun          # the topic spans clauses
            continue
        if j <= prev:
            continue              # case arguments: this clause only
        if s == "に" and j + 1 < n and _base(toks[j + 1]) == "よる":
            by = noun
        elif s == "に" and toks[j - 1].feature.pos3 == "副詞可能":
            continue              # 朝に / 昨日に: time, not a participant
        elif s in ("が", "を", "に", "から", "へ"):
            args.setdefault(s, noun)
    # cleft: 〜のは X だ after the predicate
    focus = ""
    for j in range(main + 1, n - 1):
        if toks[j].surface == "の" and toks[j + 1].surface == "は":
            e = j + 2
            while e < n and (toks[e].feature.pos1 in ("名詞", "接尾辞") or toks[e].surface in ("の", "・")
                             or _is_verb_in_noun(toks, e)):
                e += 1
            focus = _noun_run_back(toks, e - 1) if e > j + 2 else ""
            break
    k = main + 1
    while k < n and toks[k].feature.pos1 == "助動詞":
        k += 1
    benefactive = k + 1 < n and toks[k].surface in ("て", "で") and \
        _base(toks[k + 1]) in ("もらう", "貰う", "いただく", "頂く")
    indirect = passive_mark and "を" in args and ("から" in args or "に" in args or by)
    passive = passive_mark and ("を" not in args or indirect)
    k2 = main + 1
    past = False
    while k2 < n and (toks[k2].feature.pos1 == "助動詞" or toks[k2].surface in ("て", "で")
                      or (toks[k2].feature.pos1 == "動詞" and toks[k2].feature.pos2 == "非自立可能")):
        if _base(toks[k2]) == "た":
            past = True
        k2 += 1
    fr = Frame(predicate=verb, negated=_negated(toks, main), past=past)
    if indirect:
        # 田中は佐藤から見積書を送られた: を stays the patient, から/に/によって
        # is the agent, the が/は person is the one it reached.
        fr.patient = args["を"]
        fr.agent = by or args.get("から", "") or args.get("に", "")
        fr.recipient = args.get("が", "")
        if not fr.recipient and topic:
            fr.recipient, topic = topic, ""
    elif passive:
        fr.patient = args.get("が", "")
        fr.agent = by or args.get("から", "") or (args.get("に", "") if not by else "")
        if by and args.get("に"):
            fr.recipient = args["に"]
    else:
        fr.agent = args.get("が", "")
        fr.patient = args.get("を", "")
        fr.recipient = args.get("に", "")
    if benefactive:
        # 由衣は修に自転車を貸してもらった: 修 lent, 由衣 received.
        giver = args.get("に", "") or args.get("から", "")
        recv = args.get("が", "") or topic
        fr = Frame(verb, giver, args.get("を", ""), recv, fr.negated)
        topic = ""
    if not fr.recipient and args.get("へ"):
        fr.recipient = args["へ"]
    # Relative clause: 鍋に残ったスープ — a 連体 predicate directly followed by a
    # noun. The noun (not the は topic) fills the clause's open role.
    k3 = main + 1
    while k3 < n and toks[k3].feature.pos1 == "助動詞":
        k3 += 1
    relative = k3 < n and toks[k3].feature.pos1 == "名詞" and \
        (str(toks[main].feature.cForm).startswith("連体形") or
         (k3 > main + 1 and str(toks[k3 - 1].feature.cForm).startswith("連体形")))
    if relative:
        fr.inferred = True
        # 玄関に置いた傘 (trans, を open) -> 傘 is what was put; 濡れた傘
        # (intrans) -> 傘 got wet; ご飯をよそった茶碗 (trans, を filled) ->
        # the bowl is a place or instrument, not the agent: undecidable.
        head = _noun_run_back_fwd(toks, k3)
        topic = ""
        tv = transitivity(verb)
        if head and not passive:
            if tv == "trans" and not fr.patient and attested(verb, "を", head):
                fr.patient = head
            elif tv == "intrans" and not fr.agent and attested(verb, "が", head):
                fr.agent = head
            else:
                fr.ambiguous = True      # an outer head (音, 後, 朝) or undecidable
        elif head and not fr.patient:
            fr.patient = head
        # 玄関には濡れた傘: には / では belong to the main clause
        for j in range(prev + 1, main):
            if toks[j].surface == "は" and j > 0 and toks[j - 1].surface in ("に", "で"):
                nn = _noun_run_back(toks, j - 2)
                if fr.recipient == nn:
                    fr.recipient = ""

    for extra in (topic, focus):
        if not extra:
            continue
        if extra == topic:
            fr.inferred = True
        if passive:
            if not fr.patient:
                fr.patient = extra
            elif not fr.agent:
                fr.agent = extra
        elif not fr.agent:
            # は is most often the subject: an active clause with no が takes
            # the topic as its agent (猫は…押し返した); with が present the
            # topic falls to the patient (資料Aは花子が渡した). A transitive
            # verb with を open could take the topic either way (茶碗は手に
            # 持つと): kept for reading, flagged so generation will not assert it.
            fr.agent = extra
            if extra == topic and not fr.patient and transitivity(verb) == "trans":
                fr.ambiguous = True
        elif not fr.patient:
            fr.patient = extra
        elif not fr.agent:
            fr.agent = extra
    if fr.predicate in CONVERSE and not passive and not benefactive:
        # X が Y から Z を受け取る -> 渡す(agent=Y, patient=Z, recipient=X)
        giver = args.get("から", "") or args.get("に", "")
        fr = Frame(CONVERSE[fr.predicate], giver, fr.patient, fr.agent, fr.negated)
    return fr


def _noun_run_back_fwd(toks, j) -> str:
    parts = []
    while j < len(toks) and (toks[j].feature.pos1 in ("名詞", "接尾辞")
                             or (toks[j].surface == "・" and j + 1 < len(toks)
                                 and toks[j + 1].feature.pos1 == "名詞")):
        parts.append(toks[j].surface)
        j += 1
    return "".join(parts)


def regression() -> Dict[str, Any]:
    want = ("渡す", "花子", "資料A", "太郎", False)
    same = ["花子が太郎に資料Aを渡した。", "資料Aが花子によって太郎に渡された。",
            "資料Aは花子が太郎に渡した。", "資料Aを太郎に渡したのは花子だ。",
            "花子は資料Aを太郎に渡しました。", "太郎に花子が資料Aを渡した。"]
    got = {s: (read(s).key() if read(s) else None) for s in same}
    checks = {"paraphrase_%d" % k: got[s] == want for k, s in enumerate(same)}
    checks["honorific"] = read("社長が資料をお渡しになった。").key()[:3] == ("渡す", "社長", "資料")
    checks["negation"] = read("花子は太郎に資料Aを渡さなかった。").negated is True
    two = [f.key()[:3] for f in read_all("猫があくびをし、鋭い歯がのぞいた。")]
    checks["clause_scope"] = ("のぞく", "歯", "") in two and ("する", "猫", "あくび") in [
        (k[0][-2:] if k[0].endswith("する") else k[0], k[1], k[2]) for k in two] or \
        all(not (k[0] == "のぞく" and k[2] == "あくび") for k in two)
    checks["indirect_passive"] = read("田中は佐藤から見積書を送られた。").key() == ("送る", "佐藤", "見積書", "田中", False)
    checks["converse"] = read("藤本は山下から議事録を受け取った。").key() == ("渡す", "山下", "議事録", "藤本", False)
    checks["he_goal"] = read("高橋は森に研修へ招かれた。").key() == ("招く", "森", "高橋", "研修", False)
    checks["nakaguro"] = read("ピエール・キュリーを研究室に招いたのはマリー・キュリーだ。").agent == "マリー・キュリー"
    checks["time_ni"] = read("拓海は朝に真帆に起こされた。").agent == "真帆"
    checks["no_np"] = read("祖母の澄子が葵にマフラーの編み方を教えた。").key() == ("教える", "澄子", "マフラーの編み方", "葵", False)
    checks["keshigomu"] = read("朝、理央が彩に消しゴムを返した。").key() == ("返す", "理央", "消しゴム", "彩", False)
    checks["benefactive"] = read("由衣は修に自転車を貸してもらった。").key() == ("貸す", "修", "自転車", "由衣", False)
    checks["humble"] = read("大地は田中先生に理科のレポートをお見せした。").key()[:3] == ("見せる", "大地", "理科のレポート")
    checks["apposition"] = canonical(read("平野を診察したのは医師の小林だ。").agent) == \
        canonical(read("小林医師は平野を診察しました。").agent) == "小林"
    checks["o_prefix"] = read("涼子が陽菜にお弁当を作った。").patient == "お弁当"
    checks["kiku"] = read("森は宮本から症状を聞いた。").key() == ("伝える", "宮本", "症状", "森", False)
    checks["causative"] = read("エルサが魔法で雪を降らせた。").key()[:3] == ("降らせる", "エルサ", "雪")
    checks["relative"] = ("残る", "スープ") in [(f.predicate, f.agent) for f in read_all("母は鍋に残ったスープを温めた。")] \
        and ("温める", "母") in [(f.predicate, f.agent) for f in read_all("母は鍋に残ったスープを温めた。")]
    checks["rel_trans"] = ("置く", "傘") in [(f.predicate, f.patient) for f in read_all("玄関に置いた傘から雫が落ちた。")]
    checks["rel_filled_ambiguous"] = any(f.ambiguous for f in read_all("ご飯をよそった茶碗を置いた。") if f.predicate in ("よそう", "よそる"))
    checks["outer_head"] = all(f.ambiguous or f.patient != "音" for f in read_all("遠くで電車が走る音がした。") if f.predicate == "走る")
    checks["niwa_main"] = all(f.recipient != "玄関" for f in read_all("玄関には濡れた傘のにおいが残っていた。") if f.predicate == "濡れる")
    checks["te_kuru"] = read("給仕が紅茶を食事客に持ってきた。").predicate == "持ってくる"
    checks["swap_differs"] = read("太郎が花子に資料Aを渡した。").key() != want
    return {"all_pass": all(checks.values()), **checks,
            "_got": {s: g for s, g in got.items() if g != want}}

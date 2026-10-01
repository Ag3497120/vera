"""What an utterance does — requests, promises, refusals, irony — read from its
form, and what an indirect one asks for, read from what the corpus says people
do in that state.

PREREGISTERED_2026-09-27_intent. Three layers, no model:

    form        the sentence end decides the act (〜てください request,
                〜ませんか suggestion, 〜ておきます promise, 〜てはいけない
                prohibition …). Closed rules, read by position.
    indirect    a statement of a state (寒いね, 暗いな, 窓が開いてる) is read
                as a request when the corpus writes that state followed by an
                action in the same sentence (寒くて窓を閉めた). The implied
                action is the most attested one; none attested, none said.
    irony       praise (さすが, 立派, すごい …) right after a context of failure
                or negation (忘れた, 壊した, 遅刻) is irony; the real
                evaluation is the opposite.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .typed_edges import _base, _tagger, extract

GENERAL = Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"

PRAISE = ("さすが", "すごい", "素晴らしい", "立派", "上手", "最高", "いいね", "偉い",
          "えらい", "お見事", "見事", "天才", "ありがたい", "助かる", "頼もしい")
FAILURE = ("忘れ", "壊", "落と", "こぼ", "遅刻", "遅れ", "失敗", "間違", "負け", "焦が",
           "割っ", "破", "なくし", "無くし", "寝坊", "汚", "ミス", "ない", "なかった", "ません")
REFUSE = ("ちょっと…", "ちょっと...", "ちょっと。", "また今度", "遠慮します", "遠慮しておきます",
          "結構です", "考えておきます", "今回は", "今日は…", "今日はちょっと", "無理", "難しい",
          "やめておきます", "ご遠慮", "見送", "パスで", "いいです。")


def _end(u: str) -> str:
    return re.sub(r"[。．！!？?…・\s」』）)]+$", "", u)


def act_by_form(u: str) -> Tuple[str, str]:
    """(act, why) from the sentence end. 'statement' when no form marks it."""
    s = _end(u)
    q = u.rstrip().endswith(("？", "?")) or s.endswith(("か", "かな", "かしら", "の"))
    if any(k in u for k in ("ありがとう", "感謝", "助かりました", "恩に着")):
        return "thanks", "thanks word"
    if any(k in u for k in ("すみません", "ごめん", "申し訳", "失礼しました", "お詫び")) \
            and not re.search(r"(すみません|すいません)(が|けど)", u):
        return "apology", "apology word"
    if any(k in u for k in REFUSE) or re.search(r"(ちょっと|今日は|今回は)[…\.。]*$", u.strip()):
        return "refusal", "hedged decline"
    if re.search(r"(てはいけな|てはいけま|ちゃいけな|てはだめ|ちゃだめ|じゃだめ|てはダメ|ちゃダメ|てはなりません|ないでください|ないで下さい|ないで[。！]?$|禁止|べからず|ご遠慮ください)", s + "。") :
        return "prohibition", "prohibitive ending"
    if re.search(r"(てください|て下さい|てくれ(る|ます|ない|ません)?(か)?|てもらえ(る|ます|ない|ません)(か)?|"
                 r"ていただけ(る|ます|ない|ません)(か)?|てほしい|て欲しい|お願い|頼む|頼みます|"
                 r"くれない|てちょうだい)", s):
        return "request", "request ending"
    if re.search(r"(ませんか|ましょう|ようか|ようよ|こうよ|ろうよ|ない？|たらどう|たらいい|ほうがいい|方がいい|てはどう|"
                 r"てはいかが|たら$|てみたら|といい(です)?よ?$|といいですね|しよう|行こう|食べよう|やろう|"
                 r"べきだ|べきです|がいいよ|がおすすめ|をおすすめ)", s) or \
            re.search(r"(ませんか|ないか|ましょうか)$", s):
        return "suggestion", "suggestion ending"
    if re.search(r"(しなさい|なさい|しろ|せよ|てこい|ろ$|え$)", s) and not q:
        return "command", "imperative"
    if re.search(r"(ておきます|ておく|とくね|ときます|ます(から|ね)?$|します$|しますね|からね|約束|必ず|きっと)", s) \
            and not q and re.search(r"(私|僕|俺|わたし|ぼく|自分|ます|とく|ておく)", u):
        if re.search(r"(ておきます|とく|ときます|約束|必ず|しますね|からね|しておく)", u):
            return "promise", "first-person commitment"
    if q:
        return "question", "question form"
    return "statement", "no marked form"


#: Undoing a state: what someone is asked to do when the context shows a thing
#: in a state and the utterance complains of its effect (窓が開いている → 閉める).
REVERSE = {"開く": "閉める", "開ける": "閉める", "開いている": "閉める", "閉まる": "開ける",
           "つく": "消す", "点く": "消す", "つける": "消す", "消える": "つける", "消す": "つける",
           "出る": "止める", "流れる": "止める", "鳴る": "止める", "散らかる": "片付ける",
           "こぼれる": "拭く", "濡れる": "拭く", "汚れる": "洗う", "切れる": "替える",
           "止まる": "動かす", "壊れる": "直す", "落ちる": "拾う", "減る": "足す", "なくなる": "足す"}


def undo(context: str) -> str:
    """A thing in a state in the context -> the action that undoes it."""
    for fr_e in extract(context):
        if fr_e.rel in ("が", "は") and fr_e.head in REVERSE and fr_e.pol == "+":
            return "%sを%s" % (fr_e.dep, REVERSE[fr_e.head])
    return ""


@lru_cache(maxsize=4096)
def remedies(state: str, db: Path = GENERAL, k: int = 3) -> Tuple[Tuple[str, int], ...]:
    """Actions the corpus writes after a state in the same sentence:
    寒い -> 窓を閉める, 暖房をつける. Returned as 'OをV' with counts."""
    if not db.exists():
        return ()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT b.dep, b.head, b.src, s.text FROM tedges a JOIN tedges b "
        "ON a.sha = b.sha AND b.ev > a.ev JOIN tsent s ON s.sha = a.sha "
        "WHERE a.rel='属性' AND a.dep=? AND a.pol='+' AND b.rel='を' AND b.pol='+' "
        "AND b.mod IN ('assert','cond_then') LIMIT 3000", (state,)).fetchall()
    con.close()
    # Only where the state is written as the CAUSE: 寒くて / 寒いので / 寒いから.
    stem = state[:-1] if state.endswith("い") else state
    cause = re.compile(re.escape(stem) + r"(くて|いので|いから|かったので|かったから|なので|だから|で、)")
    c: Dict[Tuple[str, str], set] = {}
    for o, v, src, text in rows:
        m = cause.search(text)
        if m and text.find(o) > m.start():
            c.setdefault((o, v), set()).add(src)
    ranked = sorted(((("%sを%s" % ov), len(ss)) for ov, ss in c.items() if len(ss) >= 2),
                    key=lambda x: -x[1])
    return tuple(ranked[:k])


def _states(u: str) -> List[str]:
    out = []
    for t in _tagger()(u):
        if t.feature.pos1 in ("形容詞", "形状詞") and t.feature.pos2 != "非自立可能":
            out.append(_base(t))
    for e in extract(u):
        if e.rel in ("が", "は") and e.head not in out:
            pass
    return out


_OFFER = ("頼ん", "頼ま", "勧め", "すすめ", "誘っ", "誘わ", "依頼", "提案", "お願い", "申し込", "持ちかけ", "差し出")
_ACCEPT = ("はい", "いいよ", "喜んで", "ぜひ", "もちろん", "了解", "分かりました", "承知")
_NEG_CTX = ("ない", "なかった", "ず", "ません", "忘れ", "壊", "落と", "こぼ", "遅刻", "遅れ", "失敗", "間違",
            "負け", "焦が", "割", "破", "なくし", "寝坊", "汚", "散らか", "折れ", "待たせ", "白紙", "大声",
            "騒", "放置", "サボ", "居眠り", "転ん", "ミス", "怒", "文句", "邪魔")
_STATE_VERBS = ("ある", "いる", "なる", "思う", "分かる", "わかる", "見える", "聞こえる", "できる", "要る", "違う")


def _final(u: str):
    """The last predicate: (base, pos1, negated, past) — read by position."""
    from .typed_edges import _negated
    toks = list(_tagger()(u))
    for i in range(len(toks) - 1, -1, -1):
        t = toks[i]
        if t.feature.pos1 in ("動詞", "形容詞", "形状詞") and t.feature.pos2 != "非自立可能":
            past = any(_base(x) == "た" for x in toks[i + 1:i + 5])
            return _base(t), t.feature.pos1, _negated(toks, i), past, i
    return "", "", False, False, -1


def _positive_eval(u: str) -> bool:
    """An evaluation with no negation in it: 時間に正確ですね / きれいなお部屋だこと
    / 頼りになるね. Praise words, or an adjective / 形状詞 predicate or
    modifier with no ない after it."""
    if any(p in u for p in PRAISE) or re.search(r"(頑張|助か|頼り|ぴったり|完璧|さすが|見事|丁寧|慎重|正確|長持ち|しやすい)", u):
        return not re.search(r"(ない|ません|なかった)", u)
    base, pos, neg, _, _ = _final(u)
    return pos in ("形容詞", "形状詞") and not neg


def read(utterance: str, context: str = "") -> Dict[str, Any]:
    act, why = act_by_form(utterance)
    out: Dict[str, Any] = {"act": act, "why": why, "indirect": False, "implied": ""}
    u = utterance
    # irony: an evaluation with no negation, right after a context of failure
    # or negation — the two poles disagree (遅刻 → 時間に正確ですね).
    if context and any(f in context for f in _NEG_CTX) and act in ("statement", "thanks", "question") \
            and _positive_eval(u):
        out.update(act="irony", indirect=True, why="positive evaluation right after a failure",
                   implied="評価は逆（責め・不満）")
        return out
    base, pos, neg, past, _ = _final(u)
    # refusal: after an offer / request, a statement that does not accept
    if act == "statement" and context and any(o in context for o in _OFFER) \
            and not any(a in u for a in _ACCEPT):
        out.update(act="refusal", indirect=True, why="a non-acceptance after an offer")
        return out
    # refusal: negating one's own action (参加できません, 引き受けないよ)
    if act == "statement" and pos == "動詞" and neg and not past and base not in ("ある", "いる", "分かる", "わかる"):
        if not context or re.search(r"(できま|られな|られま|ません|ないよ|ないです|ないね|ない。|ない$)", u):
            if not re.search(r"(が|は).{0,6}(ない|ません)", u) or re.search(r"(できません|られません|られない|ません。?$|ないよ)", u):
                out.update(act="refusal", why="negating one's own action")
                return out
    # promise: one's own action, non-past, affirmative, said outright
    if act == "statement" and pos == "動詞" and not neg and not past and base not in _STATE_VERBS \
            and re.search(r"(ます|いたします|ますね|よ|ね|から)[。！]?$", u.strip()) and not context:
        out.update(act="promise", why="own action, non-past, affirmed")
        return out
    if act == "refusal" and not re.search(r"(断り|できません|いやです|嫌です)", u):
        out["indirect"] = True
    # indirect request: a state statement the corpus follows with an action
    # indirect suggestion: an alternative offered with なら (車なら五分で着く)
    if act == "statement" and context and re.search(r"[^\s]なら[、,]?", u):
        out.update(act="suggestion", indirect=True, why="an alternative offered with なら")
        return out
    if act in ("statement", "question") and context:
        un = undo(context)
        if un and _states(u):
            out.update(act="request", indirect=True,
                       why="the context shows a state; the complaint asks to undo it", implied=un)
            return out
    if act in ("statement", "question"):
        for st in _states(u):
            rem = remedies(st)
            if rem:
                out.update(act="request", indirect=True, why="state %s: the corpus writes %s after it"
                           % (st, "・".join(r for r, _ in rem)), implied=rem[0][0])
                return out
    # indirect request: a trouble stated to someone (見えないな, 届かないねえ,
    # なくなっちゃいました) — the listener is asked to remove it.
    if act == "statement" and context and (neg or re.search(r"(ちゃった|ちゃいました|てしまった|てしまいました|なくなっ|切れ)", u)) \
            and re.search(r"(ね|な|よ|けど|ですが|んですが|て|で|なあ|ねえ)[。！…]*$", u.strip()):
        out.update(act="request", indirect=True, why="a trouble stated to the listener",
                   implied=(base + "ようにする") if base else "")
    return out

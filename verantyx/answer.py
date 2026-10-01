"""Cited, slot-checked answers to a typed document question.

This is deliberately a document reader rather than a general knowledge answerer.
The source sentence is the unit of proof; derived counts and differences name
their operands in the trace. No document text is executed as an instruction.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import TYPE_CHECKING

from verantyx.bot import _en_words, _ja_words, lang

if TYPE_CHECKING:
    from verantyx.bot import Bot
    from verantyx.question import Query


_STOP = {
    "AI", "文書", "指示", "命令", "注意", "書き", "答え", "答える", "従う", "正しい", "実際",
    "此の", "その", "この", "其れ", "それ", "何", "どの", "様", "よう", "場合", "条件",
    "為る", "する", "有る", "ある", "居る", "いる", "出来る", "できる", "下さる", "ください",
    "幾ら", "いくら", "なり", "成る", "ため", "為", "必要", "つい", "つく", "其々", "それぞれ",
    "比較", "比べる", "違い", "違う", "差", "何時", "日", "時", "年", "扱う", "1", "2", "3", "4",
    "よい", "良い",
}
_SLOT_WORDS = {"時間", "日時", "日付", "予定", "場合", "必要", "条件", "方法",
               "理由", "内容", "対象", "範囲", "扱い", "事項"}
_CAUSAL = re.compile(r"ため|ので|により|によって|原因|防止|(?:だから|ですから|であるから|(?:た|る|ない)から)")
_CONSEQUENCE = re.compile(r"結果|代替|代わりに|とは限らない|できない|できません|不可能|しなければならない|そうしないと")
_ABSENT = re.compile(r"(?:書かれていない|記されていない|示されていない|提示されていない|まだ決まっていません|未定|不明|記載がない)")
_NEGATIVE = re.compile(r"できな|できません|しな[いか]|しません|されな|されません|ない|なかっ|いなかっ|ません|対象外|禁止|てはいけな|不要|必要はない|認められな|保証されな")
_WHEN = re.compile(r"(?:\d+|[〇一二三四五六七八九十百千]+)(?:年|月|日|時|分|週間|営業日前)|[月火水木金土日]曜日|毎週|午前|午後|翌日|翌年|前日|以内")
_PLACE = re.compile(r"(?:[一-鿿ァ-ヶA-Za-z0-9]+)(?:駅|室|階|窓口|受付|場所|会議室|集積所|地区|口座|橋|町|区|市|県|ウェブページ|ページ)(?:に|で|へ|から|は|を|の)?")
_NUMBER = r"(?:\d[\d,]*(?:\.\d+)?|[〇一二三四五六七八九十百千]+)"
_QUANTITY_UNITS = ("営業日前", "か月分", "ヶ月分", "キログラム", "ミリリットル",
                   "平方メートル", "キロメートル", "メートル", "パーセント", "グラム", "リットル", "センチ", "時間", "日間",
                   "年間", "万円", "世帯", "区画", "品目", "種類", "単位", "冊", "匹",
                   "食", "点", "枚", "秒", "人", "台", "脚", "本", "隻", "件",
                   "組", "個", "名", "回", "つ", "店", "列", "円", "年", "月", "日", "時", "分", "％", "%", "度", "泊")
_QUANTITY = re.compile(rf"(?<!第)({_NUMBER})\s*({'|'.join(sorted(_QUANTITY_UNITS, key=len, reverse=True))})")
_MONEY = re.compile(rf"({_NUMBER})\s*(万円|円)")
_COUNT_UNITS = {"人", "名", "台", "脚", "本", "隻", "品目", "種類", "単位", "件", "組", "個", "回", "つ", "店", "列", "冊", "匹", "食", "点", "枚", "世帯", "区画"}
_NUM_KANJI = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _number(raw: str) -> float | None:
    raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        pass
    if all(c in _NUM_KANJI for c in raw):
        return float(int("".join(str(_NUM_KANJI[c]) for c in raw)))
    total = 0
    current = 0
    for c in raw:
        if c in _NUM_KANJI:
            current = _NUM_KANJI[c]
        elif c == "十":
            total += (current or 1) * 10
            current = 0
        elif c == "百":
            total += (current or 1) * 100
            current = 0
        elif c == "千":
            total += (current or 1) * 1000
            current = 0
        else:
            return None
    return float(total + current)


def _terms(text: str) -> set[str]:
    words = _ja_words(text) if lang(text) == "ja" else _en_words(text)
    return {w for w in words if w not in _STOP and not (w.isdigit() and len(w) < 2)}


def _coordinated_subject(text: str) -> tuple[str, str] | None:
    from verantyx.typed_edges import _tagger
    tokens = list(_tagger()(text))
    for i in range(1, len(tokens) - 2):
        if (tokens[i].surface in ("と", "・") and tokens[i - 1].feature.pos1 == "名詞" and
                tokens[i + 1].feature.pos1 == "名詞" and tokens[i + 2].surface == "は"):
            return tokens[i - 1].surface, tokens[i + 1].surface
    return None


@lru_cache(maxsize=4096)
def _predicates(text: str) -> frozenset[str]:
    from verantyx.frames import canonical
    from verantyx.verdict import read_records
    return frozenset(canonical(it.frame.predicate) for it in read_records(text)
                     if it.frame.predicate)


def _clean_question(text: str) -> str:
    # Remove a prefatory instruction or proposed false answer as a whole
    # clause. The content question after it remains the retrieval key.
    preface = text.split("、", 1)[0] if "、" in text else ""
    topic = (re.search(r"と([^「『、。]{2,30}?)(?:は|が)[^、。]*$", preface)
             if re.search(r"AI|指示|注意書き", preface) else None)
    text = re.sub(r"^[^、。]{0,100}(?:AI|指示|注意書き)[^、。]*。", "", text)
    text = re.sub(r"(?:^[^、。]{0,100}|(?<=。))[^、。]{0,100}(?:AI|指示|注意書き)[^、。]*、", "", text)
    avoided = re.fullmatch(r"(.+?)を答えず[『「][^』」]+[』」]とすべきか[。？?]*", text)
    if avoided:
        target = avoided.group(1)
        interrogative = "いつ" if target.endswith(("日付", "日時", "時刻")) else "何"
        text = f"{target}は{interrogative}ですか。"
    if topic and topic.group(1) not in text:
        text = topic.group(1) + "について、" + text
    return text


def _quantities(sentence: str) -> list[tuple[float, str, str]]:
    sentence = re.sub(r"^第\d+条[\s　]*", "", sentence)
    return [(n, unit, m.group(0)) for m in _QUANTITY.finditer(sentence)
            if (n := _number(m.group(1))) is not None for unit in [m.group(2)]]


def _requested_unit(q: str, slot: str | None = None) -> str:
    # Read a counter from the question itself, rather than selecting a unit
    # because a nearby document sentence happens to contain a number.
    if re.search(r"いくら|何円", q):
        if re.search(r"(?:重さ|重量|質量)(?:の)?(?:上限|制限)?はいくら", q):
            return "キログラム"
        return "円"
    for m in re.finditer(r"何\s*([一-鿿ぁ-んァ-ヶー％%]{1,9})", q):
        span = m.group(1)
        for unit in sorted(_QUANTITY_UNITS, key=len, reverse=True):
            if span.startswith(unit):
                return unit
    if slot == "how much" or "金額" in q:
        return "円"
    return ""


def _unit_matches(requested: str, actual: str) -> bool:
    return (not requested or requested == actual or
            (requested == "名" and actual == "人") or
            (requested == "人" and actual == "名") or
            (requested == "円" and actual == "万円") or
            (requested == "年" and actual == "年間") or
            (requested == "日" and actual == "日間") or
            (requested == "品目" and actual in _COUNT_UNITS))


def _explicit_absence(text: str) -> bool:
    return bool(_ABSENT.search(text))


def _slot_support(q: str, slot: str | None, kind: str, sentence: str) -> tuple[bool, str]:
    if lang(q) == "en":
        lower = sentence.lower()
        if slot == "why":
            return bool(re.search(r"\bbecause\b|\bdue to\b|\bsince\b", lower)), "causal_clause"
        if slot == "when":
            return bool(re.search(r"\d|monday|tuesday|wednesday|thursday|friday|saturday|sunday|daily|weekly|a\.m\.|p\.m\.", lower)), "time"
        if slot == "where":
            return bool(re.search(r"\b(?:in|at|on|to|from)\s+[a-z]", lower)), "place"
        if slot in ("how many", "how much") or kind == "count":
            return bool(re.search(r"\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|hundred)\b", lower)), "quantity"
        if slot == "who":
            return bool(re.search(r"\b[A-Z][a-z]+\b", sentence)), "person"
        return True, "stated_clause"
    versions = set(re.findall(r"\d+(?:\.\d+){1,}", q))
    if versions and not versions <= set(re.findall(r"\d+(?:\.\d+){1,}", sentence)):
        return False, "different_version"
    contrasted = re.search(r"ではなく([^、。]{2,20}?)(?:を|の|は)", q)
    if contrasted and contrasted.group(1) not in sentence:
        return False, "missing_contrasted_argument"
    if slot in ("when", "how much", "how many") and len(_terms(q)) >= 4:
        # A date or amount attached to only one generic action in a complex
        # question is usually about a different argument. A preceding sentence
        # can bind an elided activity, but must pass this check jointly.
        shared_arguments = {w for w in _terms(q) & _terms(sentence)
                            if len(w) >= 2 and w not in _SLOT_WORDS}
        if len(shared_arguments) < 2:
            return False, "quantity_without_argument"
    if slot == "how much" and re.search(r"いくら|何円", q):
        from verantyx.typed_edges import _tagger
        tokens = list(_tagger()(q))
        for i in range(len(tokens) - 1):
            if (tokens[i].feature.pos1 == "名詞" and
                    tokens[i + 1].surface in ("費", "料", "賃料", "料金") and
                    tokens[i + 1].feature.pos1 in ("名詞", "接尾辞")):
                phrase = tokens[i].surface + tokens[i + 1].surface
                if phrase not in sentence:
                    return False, "different_amount_argument"
    requested_measure = _requested_unit(q)
    if (requested_measure in {"％", "%", "パーセント", "メートル", "キロメートル",
                              "センチ", "リットル", "ミリリットル", "グラム", "キログラム"}
            and re.search(r"何\s*" + re.escape(requested_measure), q) and
            not any(_unit_matches(requested_measure, u) for _, u, _ in _quantities(sentence))):
        return False, "missing_requested_measure"
    if re.search(r"(?:税率|割合|比率|確率)は?(?:何|いくら)", q) and not re.search(
            rf"{_NUMBER}\s*(?:％|%|パーセント)", sentence):
        return False, "missing_rate"
    named_attribute = re.search(r"([一-鿿ァ-ヶー]{2,12})の(氏名|名前|住所|所在地)は何", q)
    if named_attribute and named_attribute.group(1) not in sentence:
        return False, "different_named_subject"
    if named_attribute and named_attribute.group(2) in ("住所", "所在地") and not \
            (re.search(r"住所|所在地|番地", sentence) or _PLACE.search(sentence)):
        return False, "missing_address"
    if re.search(r"何グラム|何キログラム|何リットル", q):
        unit = _requested_unit(q, slot)
        if not any(_unit_matches(unit, found) for _, found, _ in _quantities(sentence)):
            return False, "missing_measurement"
    attribute = re.search(r"([一-鿿ぁ-んァ-ヶー]{2,12})の(色|材質|重さ|重量|容量|寸法|型番)", q)
    if attribute:
        subject, attr = attribute.groups()
        if subject not in sentence and subject.rsplit("べき", 1)[-1] not in sentence:
            return False, "different_attribute_subject"
        if attr == "色":
            carried = "色" in sentence
        elif attr == "材質":
            carried = bool(re.search(r"材質|[一-鿿ァ-ヶー]{1,8}製", sentence))
        elif attr in ("重さ", "重量"):
            carried = bool(re.search(rf"{_NUMBER}(?:キログラム|グラム|kg|g)|重さ|重量", sentence))
        elif attr == "容量":
            carried = bool(re.search(rf"{_NUMBER}(?:リットル|ミリリットル|L|mL)|容量", sentence))
        elif attr == "寸法":
            carried = bool(re.search(r"寸法|センチ|メートル|cm|mm", sentence))
        else:
            carried = "型番" in sentence
        if not carried:
            return False, "missing_attribute"
    if kind == "fact":
        paired = _coordinated_subject(q)
        if paired:
            left, right = paired
            if left not in sentence or right not in sentence:
                return False, "missing_coordinated_subject"
        if slot == "what" and re.search(r"何|どの|どんな", q):
            from verantyx.frames import canonical, read_all
            asked = [f for f in read_all(q) if f.predicate not in
                     ("する", "ある", "いる", "なる", "言う", "思う")]
            stated = read_all(sentence)
            for a in asked[-1:]:
                same_event = [s for s in stated if s.predicate == a.predicate]
                roles = [canonical(x) for x in (a.agent, a.patient, a.recipient) if x]
                if same_event and roles and not any(
                        role in sentence for role in roles):
                    return False, "different_event_argument"
    if _explicit_absence(sentence):
        return False, "explicit_absence"
    if kind == "why" or slot == "why":
        return bool(_CAUSAL.search(sentence) or _CONSEQUENCE.search(sentence)), "reason_or_consequence"
    if slot == "when":
        from verantyx.typed_edges import _tagger
        qtokens = list(_tagger()(q))
        for i, token in enumerate(qtokens):
            if token.surface == "日" and i >= 2 and all(
                    qtokens[j].feature.pos1 == "名詞" for j in (i - 2, i - 1)):
                qualifiers = (qtokens[i - 2].surface, qtokens[i - 1].surface)
                if not any(term in sentence for term in qualifiers):
                    return False, "different_event_date"
        events = _predicates(q) - {"する", "ある", "いる", "なる", "言う", "思う"}
        if events and re.search(r"(?:た|した|ていた)(?:年|月|日|時)", q):
            from verantyx.frames import canonical, read_all
            asked = [f for f in read_all(q) if f.predicate in events]
            stated = [f for f in read_all(sentence) if f.predicate in events]
            if not stated or not any(
                    a.predicate == s.predicate and
                    (not a.patient or not s.patient or
                     canonical(a.patient) == canonical(s.patient) or
                     (len(canonical(a.patient)) >= 2 and
                      canonical(a.patient) in canonical(s.patient)) or
                     (len(canonical(s.patient)) >= 2 and
                      canonical(s.patient) in canonical(a.patient)))
                    for a in asked for s in stated):
                return False, "different_event"
        if "平日" in q and not ("平日" in sentence or re.search(r"[月火水木金]曜日", sentence)):
            return False, "different_weekday_class"
        if re.search(r"何時|開館時間|営業時間|何時から何時", q):
            return bool(re.search(r"(?:午前|午後)?(?:\d+|[一二三四五六七八九十]+)時", sentence)), "clock_time"
        return bool(_WHEN.search(sentence)), "time"
    if slot == "where":
        if _PLACE.search(sentence):
            return True, "place"
        locative = bool(re.search(r"[一-鿿ァ-ヶー]{2,12}(?:に|へ|で)[^。]{0,20}", sentence))
        return locative and bool(_predicates(q) & _predicates(sentence)), "event_location"
    if slot in ("how much", "how many") or kind == "count":
        measured_object = re.search(r"何(?:人|台|個|本|件|枚|点|冊|匹)([一-鿿ァ-ヶー]{1,6})", q)
        if measured_object and measured_object.group(1) not in sentence:
            return False, "different_measured_object"
        if slot == "how much" and not re.search(r"上限|限度|最大|基準", q):
            from verantyx.typed_edges import _tagger
            people = {t.surface for t in _tagger()(q) if t.feature.pos2 == "固有名詞"}
            if people and not any(person in sentence for person in people):
                return False, "missing_named_amount_subject"
        # A quantity without the asked argument is a nearby number, not an
        # answer. Require two lexical anchors on nontrivial questions.
        shared = {w for w in _terms(q) & _terms(sentence)
                  if len(w) >= 2 and w not in _SLOT_WORDS}
        if len(_terms(q)) >= 3 and len(shared) < 2:
            return False, "quantity_without_argument"
        unit = _requested_unit(q, slot)
        quantities = _quantities(sentence)
        if unit == "日" and re.search(r"[月火水木金土日]曜日から[月火水木金土日]曜日まで", sentence):
            return True, "weekday_range"
        if unit == "回" and re.search(r"[一-鿿ァ-ヶー]{2,12}(?:前|後)と[一-鿿ァ-ヶー]{2,12}(?:前|後)", sentence):
            return True, "recurring_time_points"
        if any(_unit_matches(unit, u) for _, u, _ in quantities):
            return True, "quantity"
        if kind == "count" and unit in ("", "品目", "種類") and ("、" in sentence or "両方" in sentence):
            return True, "listed_items"
        return False, "missing_quantity"
    if slot == "who":
        from verantyx.frames import read_all
        asked_events = _predicates(q) - {"する", "ある", "いる", "なる", "言う", "思う"}
        stated = read_all(sentence)
        if asked_events:
            missing_identity = bool(re.search(r"(?:ていた|ている|した|する)者(?:だけ)?", sentence))
            asks_target = bool(re.search(r"誰に|だれに|相手は誰", q))
            asks_excluded = bool(re.search(r"誰には|だれには", q))
            matching = [f for f in stated if f.predicate in asked_events]
            role = ("agent" if asks_excluded else "recipient" if asks_target else "agent")
            bound = not missing_identity and any(
                (candidate := getattr(f, role)) and candidate not in
                ("者", "人物", "人", "誰") and candidate not in q and
                candidate in sentence
                for f in matching)
            if not bound and asks_target and matching and not missing_identity:
                bound = bool(re.search(r"[一-鿿ぁ-んァ-ヶー]{2,12}(?:に|から)", sentence))
            if not bound and not asks_target and matching and not missing_identity:
                action_nouns = {w for w in _terms(q) if len(w) >= 2}
                bound = bool(action_nouns & _terms(sentence) and re.search(
                    r"[一-鿿ぁ-んァ-ヶー]{2,12}(?:者|員|係|会|部|長)は", sentence))
            if not bound and not asks_target and not missing_identity:
                action = re.search(r"([一-鿿ァ-ヶー]{2,12})(?:が|は)できな", q)
                bound = bool(action and re.search(
                    re.escape(action.group(1)) + r"(?:は|が)でき(?:ない|ません)", sentence)
                    and re.search(r"[一-鿿ぁ-んァ-ヶー]{2,12}(?:者|員|係|会|部|長)は", sentence))
            if not bound:
                return False, "missing_named_person_in_event"
        if any(f.agent or f.recipient for f in stated) or re.search(
                r"[一-鿿]{1,8}(?:さん|氏|係|長|者|員|師|士|人)", sentence):
            return True, "person"
        return False, "missing_person"
    if slot == "whether":
        if re.search(r"人はいましたか|人がいましたか", q) and "いる" not in _predicates(sentence):
            return False, "different_event"
        return True, "polarity_or_condition"
    return True, "stated_clause"


def _condition_bonus(q: str, sentence: str) -> float:
    bonus = 0.0
    for word in ("両方", "だけ", "以下", "以上", "未満", "超え", "必ず", "原則", "場合"):
        if word in q:
            bonus += .17 if word in sentence else -.14
    q_nums = set(re.findall(r"\d+(?:\.\d+)?", q))
    s_nums = set(re.findall(r"\d+(?:\.\d+)?", sentence))
    if q_nums & s_nums:
        bonus += .12 * min(2, len(q_nums & s_nums))
    if re.search(r"終わらな|終わらず|できな|しなかっ", q):
        if re.search(r"終わらな|終わらず|できな|しなかっ", sentence):
            bonus += .35
        elif re.search(r"完了すれば|終われば|できた場合", sentence):
            bonus -= .35
    return bonus


def _score(q: str, sentence: dict, idf: dict[str, float], kind: str) -> tuple[float, set[str]]:
    qterms = _terms(q)
    sterms = set(sentence["words"]) - _STOP
    hit = qterms & sterms
    if not hit:
        return 0.0, hit
    score = sum(idf.get(w, 1.0) for w in hit) / math.sqrt(max(len(qterms), 1) * max(len(sterms), 1))
    # Adjacent content words are stronger than a shared generic word.
    chunks = re.findall(r"[一-鿿ぁ-んァ-ヶーA-Za-z0-9]{4,}", q)
    score += .45 * sum(1 for c in chunks if c in sentence["text"] and
                         c not in ("この文書", "答えてください"))
    # Reward exact multi-token noun phrases, regardless of their topic.
    from verantyx.typed_edges import _tagger
    tokens = list(_tagger()(q))
    for i in range(len(tokens) - 1):
        if tokens[i].feature.pos1 == tokens[i + 1].feature.pos1 == "名詞":
            phrase = tokens[i].surface + tokens[i + 1].surface
            if len(phrase) >= 3 and phrase in sentence["text"]:
                score += .45
        if tokens[i].feature.pos1 == "形容詞" and tokens[i + 1].feature.pos1 == "名詞":
            phrase = tokens[i].surface + tokens[i + 1].surface
            if phrase in sentence["text"]:
                score += .65
    score += _condition_bonus(q, sentence["text"])
    if re.search(r"どのように|どうやって|どんな方法", q):
        procedural = bool(re.search(r"てください|方法|手順|によって|を使い|てから|て、|て別", sentence["text"]))
        score += 1.2 if procedural else (-.25 if _WHEN.search(sentence["text"]) else 0)
    unit = _requested_unit(q)
    if unit:
        matches = list(_QUANTITY.finditer(sentence["text"]))
        anchors = [w for w in qterms if len(w) >= 2 and w in sentence["text"]]
        near = [abs(sentence["text"].find(w) - m.start())
                for w in anchors for m in matches if _unit_matches(unit, m.group(2))]
        if near:
            score += .75 / (1 + min(near) / 12)
        if not re.search(r"場合|なら|とき|たら|際", q) and re.search(r"場合|ずつ|たら", sentence["text"]):
            score -= .25
    if _predicates(q) & _predicates(sentence["text"]):
        score += .42
        if re.search(r"どのように|どうやって|どう扱", q) and len(hit) >= 2:
            from verantyx.frames import read_all
            asked = next((f.predicate for f in reversed(read_all(q)) if f.predicate not in
                          ("する", "ある", "いる", "なる", "言う", "思う")), "")
            if asked and asked in _predicates(sentence["text"]):
                score += 1.8
    if kind == "fact" and re.search(r"何|どの|どれ", q):
        from verantyx.frames import read_all
        main = next((f.predicate for f in reversed(read_all(q)) if f.predicate not in
                     ("する", "ある", "いる", "なる", "言う", "思う")), "")
        if main and main in _predicates(sentence["text"]):
            score += .85
    if kind in ("exception", "negation") and _NEGATIVE.search(q):
        score += .5 if _NEGATIVE.search(sentence["text"]) else -.2
    for phrase in re.findall(r"[一-鿿ァ-ヶー]{2,8}(?:代|料|費|期間|時間)", q):
        if phrase in sentence["text"]:
            score += .8
    if kind == "why" and (_CAUSAL.search(sentence["text"]) or _CONSEQUENCE.search(sentence["text"])):
        score += .28
    return score, hit


def _rank(q: str, pool: list[dict], kind: str, slot: str | None) -> list[tuple[dict, float, set[str], str]]:
    df = Counter(w for s in pool for w in set(s["words"]) - _STOP)
    idf = {w: 1.0 + math.log((len(pool) + 1) / (n + 1)) for w, n in df.items()}
    ranked = []
    for sent in pool:
        score, hit = _score(q, sent, idf, kind)
        valid, reason = _slot_support(q, slot, kind, sent["text"])
        if not valid and reason in ("quantity_without_argument", "missing_subject_argument"):
            previous = _next_to(pool, sent, -1)
            joined = previous["text"] + " " + sent["text"] if previous is not None else ""
            actions = _predicates(q) - {"する", "ある", "いる", "なる", "言う", "思う"}
            if previous is not None and previous["doc"] == sent["doc"] and \
                    any(len(w) >= 2 and w in sent["text"] for w in _terms(q) - _SLOT_WORDS) and \
                    (not actions or bool(actions & _predicates(joined))) and \
                    len(_terms(q) & (set(sent["words"]) | set(previous["words"]))) >= 2 and \
                    _slot_support(q, slot, kind, joined)[0]:
                valid, reason = True, "adjacent_argument"
                score += .15
        if score > 0 and valid:
            ranked.append((sent, score, hit, reason))
    ranked.sort(key=lambda x: (-x[1], x[0]["doc"], x[0]["index"]))
    return ranked


def _strong_enough(q: str, sent: dict, hit: set[str], score: float) -> bool:
    qterms = _terms(q)
    from verantyx.typed_edges import _tagger
    nouns = {t.surface for t in _tagger()(q) if t.feature.pos1 == "名詞" and
             len(t.surface) >= 2 and t.surface not in _STOP | _SLOT_WORDS}
    anchored = nouns & hit
    if len(anchored) >= 2 and score >= .27:
        return True
    if score >= 1.0 and len(hit) >= 2:
        tokens = list(_tagger()(q))
        if any(tokens[i].feature.pos1 in ("名詞", "形容詞") and
               tokens[i + 1].feature.pos1 == "名詞" and
               len(tokens[i].surface + tokens[i + 1].surface) >= 3 and
               tokens[i].surface + tokens[i + 1].surface in sent["text"]
               for i in range(len(tokens) - 1)):
            return True
    if anchored and _predicates(q) & _predicates(sent["text"]) and score >= .5:
        return True
    if re.search(r"どのように|どうやって|どんな方法", q) and len(hit) >= 2 and \
            score >= 1.0 and re.search(r"てください|手順|方法|てから|て、", sent["text"]):
        return True
    from verantyx.frames import read_all
    asked = [f for f in read_all(q) if f.predicate not in
             ("する", "ある", "いる", "なる", "言う", "思う")]
    stated = read_all(sent["text"])
    if score >= .5 and any(a.predicate == s.predicate and a.agent and
                            a.agent in sent["text"] for a in asked for s in stated):
        return True
    return bool(anchored and score >= .45 and len(qterms) <= 3)


def _ordered(rows: list[dict]) -> list[dict]:
    unique = {(s["doc"], s["index"]): s for s in rows}
    return sorted(unique.values(), key=lambda s: (s["doc"], s["index"]))


def _linked_exceptions(bot: Bot, selected: list[dict], pool: list[dict]) -> tuple[list[dict], list[dict]]:
    by_key = {(s["doc"], s["text"]): s for s in pool}
    additions = []
    links = []
    for row in list(selected):
        items = bot.base.items.get(row["doc"], ())
        for i, item in enumerate(items):
            if item.sentence != row["text"]:
                continue
            if item.exception_of is not None:
                rule = items[item.exception_of].sentence
                if (found := by_key.get((row["doc"], rule))) is not None:
                    additions.append(found)
                    links.append({"rule": rule, "exception": row["text"]})
            else:
                for exc in items:
                    if exc.exception_of == i:
                        if (found := by_key.get((row["doc"], exc.sentence))) is not None:
                            additions.append(found)
                            links.append({"rule": row["text"], "exception": exc.sentence})
    return _ordered(selected + additions), links


def _next_to(pool: list[dict], row: dict, direction: int) -> dict | None:
    same = [s for s in pool if s["doc"] == row["doc"] and
            (s["index"] < row["index"] if direction < 0 else s["index"] > row["index"])]
    if not same:
        return None
    return max(same, key=lambda s: s["index"]) if direction < 0 else min(same, key=lambda s: s["index"])


def _multi_candidates(q: str, ranked: list[tuple], pool: list[dict],
                      stages: tuple) -> tuple[list[dict], list[dict]]:
    if not ranked:
        return [], []
    if stages:
        selected = []
        traces = []
        for i, stage in enumerate(stages):
            fragment = stage.fragment or stage.head
            sr = _rank(fragment, pool, "fact", "what")
            if not sr or not _strong_enough(fragment, sr[0][0], sr[0][2], sr[0][1]):
                traces.append({"stage": i, "fragment": fragment, "verdict": "UNBOUND"})
                return [], traces
            selected.append(sr[0][0])
            traces.append({"stage": i, "fragment": fragment,
                           "sentence": sr[0][0]["text"], "verdict": "BOUND"})
        return _ordered(selected), traces

    selected = [ranked[0][0]]
    trace = [{"stage": 0, "fragment": q, "sentence": selected[0]["text"], "verdict": "BOUND"}]
    # A referential continuation licenses its adjacent antecedent.
    for row in list(selected):
        if re.match(r"^(?:残り|これは|その後|ただし|受け取って)", row["text"]):
            previous = _next_to(pool, row, -1)
            if previous is not None:
                selected.append(previous)
                trace.append({"stage": len(trace), "fragment": "adjacent antecedent",
                              "sentence": previous["text"], "verdict": "BOUND"})
        following = _next_to(pool, row, 1)
        if following is not None and re.match(r"^(?:残り|これは|その後|その場合)", following["text"]):
            selected.append(following)
            trace.append({"stage": len(trace), "fragment": "adjacent continuation",
                          "sentence": following["text"], "verdict": "BOUND"})
    qterms = _terms(q)
    covered = set().union(*(set(s["words"]) & qterms for s in selected))
    pair = _coordinated_subject(q)
    if pair and any(all(noun in s["text"] for noun in pair) for s in selected):
        return _ordered(selected), trace
    q_numbers = set(re.findall(r"\d+(?:\.\d+)?", q))
    covered_numbers = set().union(*(set(re.findall(r"\d+(?:\.\d+)?", s["text"])) & q_numbers for s in selected))
    q_dates = set(re.findall(r"\d+月\d+日", q))
    covered_dates = set().union(*(set(re.findall(r"\d+月\d+日", s["text"])) & q_dates for s in selected))
    for row, score, hit, _ in ranked[1:]:
        if len(selected) >= 3:
            break
        if re.search(r"終わらず|終わらない|終わらなかった", q) and \
                re.search(r"完了すれば|終われば", row["text"]):
            continue
        novel = hit - covered
        novel_numbers = (set(re.findall(r"\d+(?:\.\d+)?", row["text"])) & q_numbers) - covered_numbers
        novel_dates = (set(re.findall(r"\d+月\d+日", row["text"])) & q_dates) - covered_dates
        adjacency = any(row["doc"] == x["doc"] and abs(row["index"] - x["index"]) <= 1 for x in selected)
        number_bound = bool((novel_numbers or novel_dates) and
                            (adjacency or len({w for w in hit if len(w) >= 2 and
                                               w not in _SLOT_WORDS}) >= 2))
        if len(novel) >= 2 or number_bound or (novel and adjacency) or (adjacency and re.match(r"^(?:残り|これは|ただし)", row["text"])):
            selected.append(row)
            covered |= hit
            covered_numbers |= novel_numbers
            covered_dates |= novel_dates
            trace.append({"stage": len(trace), "fragment": ", ".join(sorted(novel)) or "adjacent",
                          "sentence": row["text"], "verdict": "BOUND"})
    if re.search(r"いくら|何円", q):
        for row in list(selected):
            antecedent = re.search(r"従前の([一-鿿ァ-ヶー]{2,8})(?:を|は|が)", row["text"])
            if antecedent:
                noun = antecedent.group(1)
                stated = next((s for s in pool if s["doc"] == row["doc"] and
                               s["index"] < row["index"] and
                               re.search(re.escape(noun) + r"(?:は|が)", s["text"]) and
                               _MONEY.search(s["text"])), None)
                if stated:
                    selected.append(stated)
                    trace.append({"stage": len(trace), "fragment": "prior stated amount",
                                  "sentence": stated["text"], "verdict": "BOUND"})
                break
    return _ordered(selected), trace


def _comparison(q: str, ranked: list[tuple], pool: list[dict]) -> tuple[list[dict], str, list[dict]]:
    if not ranked:
        return [], "", []
    selected = [ranked[0][0]]
    if "と" in q:
        left, right = q.split("と", 1)
        right = re.split(r"(?:を比べ|はそれぞれ|では|を比較|について)", right, 1)[0]
        if len(_terms(left)) >= 2 and len(_terms(right)) >= 2:
            sides = []
            for fragment in (left, right):
                fragment_slot = "when" if re.search(r"(?:時間|日付|時刻)$", fragment) else None
                options = _rank(fragment, pool, "fact", fragment_slot)
                side = next((row for row, score, hit, _ in options
                             if len(hit) >= 2 and score >= .5), None)
                if side is None:
                    sides = []
                    break
                sides.append(side)
            if sides:
                selected = _ordered(sides)
    if ranked[0][3] == "adjacent_argument":
        antecedent = _next_to(pool, ranked[0][0], -1)
        if antecedent is not None and antecedent["doc"] == ranked[0][0]["doc"]:
            selected.append(antecedent)
    qterms = _terms(q)
    covered = set().union(*(set(row["words"]) & qterms for row in selected))
    values = _quantities(selected[0]["text"])
    q_actions = _predicates(q) - {"する", "ある", "いる", "なる"}
    stated_actions = _predicates(selected[0]["text"])
    two_sides_in_one = (len(values) >= 2 and
                        (len(q_actions) < 2 or len(q_actions & stated_actions) >= 2) and
                        (len({u for _, u, _ in values}) == 1 or
                         all(u in _COUNT_UNITS for _, u, _ in values)))
    if not two_sides_in_one:
        for row, score, hit, _ in ranked[1:]:
            if len(selected) >= 2:
                break
            if len(hit - covered) >= 1 and (score >= ranked[0][1] * .35 or
                                            ("時間" in q and re.search(r"午前|午後", row["text"]))):
                selected.append(row)
                covered |= hit
    selected = _ordered(selected)
    trace: list[dict] = [{"side": i, "sentence": s["text"]} for i, s in enumerate(selected)]
    # A same-sentence comparison can state both sides. Otherwise check that
    # the second sentence adds a topic from the question.
    if len(selected) == 1 and not (len(covered) >= 3 or "と" in selected[0]["text"]):
        return [], "", trace

    difference = ""
    if re.search(r"差|どれだけ|何[^。]{0,5}(?:長|多|少|早|遅)", q):
        if re.search(r"早|遅", q):
            clocks = []
            for s in selected:
                match = re.search(r"(午前|午後)(\d+)時(?:(\d+)分)?(?:に|から)", s["text"])
                if match:
                    minute = (int(match.group(2)) % 12 +
                              (12 if match.group(1) == "午後" else 0)) * 60 + int(match.group(3) or 0)
                    clocks.append(minute)
            if len(clocks) == 2:
                delta = abs(clocks[0] - clocks[1])
                shown = f"{delta // 60}時間" if delta % 60 == 0 else f"{delta}分"
                side_names = re.search(r"([一-鿿ァ-ヶー]{2,12})と([一-鿿ァ-ヶー]{2,12})", q)
                if side_names and len(selected) == 2:
                    winner = clocks.index(min(clocks) if "早" in q else max(clocks))
                    relation = "早い" if "早" in q else "遅い"
                    difference = f"{side_names.group(winner + 1)}が{shown}{relation}です。"
                else:
                    difference = f"差は{shown}です。"
                trace.append({"part": "answer.diff", "method": "start_time",
                              "operands": clocks, "result": difference})
        if "時間" in q:
            spans = []
            for s in selected:
                for m in re.finditer(r"(午前|午後)(\d+)時から(午前|午後)(\d+)時", s["text"]):
                    begin = int(m.group(2)) % 12 + (12 if m.group(1) == "午後" else 0)
                    end = int(m.group(4)) % 12 + (12 if m.group(3) == "午後" else 0)
                    spans.append((end - begin) % 24)
            if not difference and len(spans) >= 2:
                n = max(spans) - min(spans)
                difference = f"差は{n}時間です。"
                trace.append({"part": "answer.diff", "operands": spans[:2], "result": difference})
        if not difference:
            quantities = [v for s in selected for v in _quantities(s["text"])]
            by_unit: dict[str, list[float]] = {}
            for n, unit, _ in quantities:
                by_unit.setdefault(unit, []).append(n)
            preferred = sorted(by_unit, key=lambda unit: (unit not in q, -len(by_unit[unit])))
            for unit in preferred:
                vals = by_unit[unit]
                if len(vals) >= 2 and vals[0] != vals[1]:
                    n = abs(vals[0] - vals[1])
                    shown = f"{n:,.0f}" if n.is_integer() else str(n)
                    difference = f"差は{shown}{unit}です。"
                    trace.append({"part": "answer.diff", "unit": unit,
                                  "operands": vals[:2], "result": difference})
                    break
            if not difference and re.search(r"何(?:脚|台|個|本)多|何(?:脚|台|個|本)少", q):
                countables = [(n, unit) for n, unit, _ in quantities if unit in _COUNT_UNITS]
                if len(countables) >= 2:
                    n = abs(countables[0][0] - countables[1][0])
                    requested = re.search(r"何(脚|台|個|本)", q).group(1)
                    difference = f"差は{n:,.0f}{requested}です。"
                    trace.append({"part": "answer.diff", "unit": "counted_objects",
                                  "operands": countables[:2], "result": difference})
    if not difference and "列数" in q:
        columns = [(n, unit) for s in selected for n, unit, _ in _quantities(s["text"]) if unit == "列"]
        if len(columns) == 1 and any("列を追加" in s["text"] for s in selected):
            old = columns[0][0]
            difference = f"有効なら{old + 1:,.0f}列、無効なら{old:,.0f}列です。"
            trace.append({"part": "answer.diff", "method": "one_added_column",
                          "operands": [old, 1], "result": difference})
    return selected, difference, trace


def _count(q: str, ranked: list[tuple], pool: list[dict]) -> tuple[list[dict], str, list[dict]]:
    if not ranked:
        return [], "", []
    selected = [ranked[0][0]]
    unit = _requested_unit(q, "how many")
    quantities = [x for x in _quantities(selected[0]["text"])
                  if (_unit_matches(unit, x[1]) and (unit or x[1] in _COUNT_UNITS))]
    trace = []
    fragments = [part.strip("。？? ") for part in re.split(r"[、，]|また", q) if part.strip("。？? ")]
    if len(fragments) >= 2 and sum(bool(re.search(r"何|いくら|いつ", part)) for part in fragments) >= 2:
        bound = []
        for part in fragments:
            if not re.search(r"何|いくら|いつ", part):
                continue
            part_slot = ("how much" if re.search(r"いくら|何円", part) else
                         "when" if re.search(r"いつ|何日", part) else "how many")
            options = _rank(part, pool, "fact", part_slot)
            found = next((row for row, score, hit, _ in options
                          if _strong_enough(part, row, hit, score)), None)
            if found is None:
                return [], "", [{"part": "answer.count", "fragment": part,
                                  "verdict": "MISSING"}]
            bound.append(found)
            trace.append({"part": "answer.count", "fragment": part,
                          "sentence": found["text"], "verdict": "BOUND"})
        if len(bound) >= 2:
            return _ordered(bound), "", trace
    if unit == "円" and re.search(r"合計|総額|全部で", q):
        # A count of items times a per-item monetary rate. Both operands must
        # be stated in the same rule, and the count must occur in the question.
        asked_counts = [(n, u) for n, u, _ in _quantities(q) if u in _COUNT_UNITS]
        if len(asked_counts) == 1:
            count, counter = asked_counts[0]
            for row in pool:
                if len(_terms(q) & set(row["words"])) < 2 or not re.search(
                        r"各|ずつ|ごと|当たり", row["text"]):
                    continue
                rates = [(n, raw) for n, u, raw in _quantities(row["text"])
                         if u == "円"]
                stated_counts = [(n, u) for n, u, _ in _quantities(row["text"])
                                 if u == counter]
                if len(rates) != 1 or (stated_counts and count not in
                                       [n for n, _ in stated_counts]):
                    continue
                total = count * rates[0][0]
                result = f"{total:,.0f}円です。"
                trace.append({"part": "answer.count", "method": "count_times_unit_rate",
                              "operands": [count, rates[0][0]], "result": result})
                return [row], result, trace
    if unit == "種類":
        # Count alternatives of a single measured dimension, not every number
        # in a sentence (which may also contain prices or dates).
        row = selected[0]
        by_unit: dict[str, set[float]] = {}
        for n, found_unit, _ in _quantities(row["text"]):
            if found_unit not in ("年", "年間", "円", "万円", "日", "日間", "時間"):
                continue
            by_unit.setdefault(found_unit, set()).add(n)
        alternatives = [values for values in by_unit.values() if len(values) >= 2]
        if len(alternatives) == 1 and re.search(r"または|あるいは|もしくは|それぞれ|、", row["text"]):
            result = f"{len(alternatives[0])}種類です。"
            trace.append({"part": "answer.count", "method": "distinct_alternatives",
                          "values": sorted(alternatives[0]), "result": result})
            return [row], result, trace
    parts = [part for part in re.split(r"[、，]|で、|また", q) if re.search(r"何(?:人|台|脚|本|隻|件|組|個|列|冊|匹|点|枚)", part)]
    if len(parts) >= 2:
        answers = []
        for part in parts:
            choices = _rank(part, pool, "count", "how many")
            found = next((row for row, score, hit, _ in choices
                          if _strong_enough(part, row, hit, score)), None)
            if found is None:
                return [], "", [{"part": "answer.count", "fragment": part,
                                  "verdict": "MISSING"}]
            answers.append(found)
            trace.append({"part": "answer.count", "fragment": part,
                          "sentence": found["text"], "verdict": "BOUND"})
        return _ordered(answers), "", trace
    if re.search(r"重複.{0,12}(?:でない|ではない|除|以外)|重複しない", q):
        totals = [(s, n, u) for s in pool if re.search(r"合計|総数|全部で", s["text"])
                  for n, u, _ in _quantities(s["text"]) if u in _COUNT_UNITS]
        duplicates = [(s, n, u) for s in pool if "重複" in s["text"]
                      for n, u, _ in _quantities(s["text"]) if u in _COUNT_UNITS]
        pairs = [(total, duplicate, n - m, u) for total, n, u in totals
                 for duplicate, m, v in duplicates if total["doc"] == duplicate["doc"]
                 and u == v and n >= m]
        if len(pairs) == 1:
            total, duplicate, remaining, found_unit = pairs[0]
            result = f"{remaining:,.0f}{found_unit}です。"
            trace.append({"part": "answer.count", "method": "total_minus_duplicates",
                          "operands": [totals[0][1], duplicates[0][1]], "result": result})
            return _ordered([total, duplicate]), result, trace
    if re.search(r"週に何日|何日間", q):
        days = "月火水木金土日"
        ranges = [(s, m.group(1), m.group(2)) for s in pool for m in
                  re.finditer(r"([月火水木金土日])曜日から([月火水木金土日])曜日まで", s["text"])]
        if len(ranges) == 1:
            row, first, last = ranges[0]
            n = (days.index(last) - days.index(first)) % 7 + 1
            result = f"{n}日です。"
            trace.append({"part": "answer.count", "method": "weekday_range",
                          "operands": [first, last], "result": result})
            return [row], result, trace
    if unit == "回":
        points = re.search(r"([一-鿿ァ-ヶー]{2,12}(?:前|後))と([一-鿿ァ-ヶー]{2,12}(?:前|後))",
                           selected[0]["text"])
        if points:
            result = "2回です。"
            trace.append({"part": "answer.count", "method": "enumerated_time_points",
                          "operands": list(points.groups()), "result": result})
            return selected, result, trace
    if re.search(r"合計|合わせて|全部で", q) and unit in _COUNT_UNITS:
        pair = re.search(r"([一-鿿ァ-ヶー]{2,12})と([一-鿿ァ-ヶー]{2,12})", q)
        if pair:
            sides = []
            for subject in pair.groups():
                options = []
                for row in pool:
                    if subject not in row["text"]:
                        continue
                    values = [(n, u) for n, u, _ in _quantities(row["text"])
                              if u in _COUNT_UNITS and (unit == "人" or u != "人")]
                    if values:
                        chosen = next(((n, u) for n, u in values if u == unit), values[-1])
                        options.append((row, chosen))
                if not options:
                    sides = []
                    break
                options.sort(key=lambda x: (-len(_terms(q) & set(x[0]["words"])), x[0]["index"]))
                sides.append(options[0])
            if len(sides) == 2 and sides[0][0] != sides[1][0]:
                total = sum(value[0] for _, value in sides)
                result = f"{total:,.0f}{unit}です。"
                trace.append({"part": "answer.count", "method": "coordinated_total",
                              "operands": [value for _, value in sides], "result": result})
                return _ordered([row for row, _ in sides]), result, trace
        # A listed total may mix counters (for example bags and a stroller).
        # Include a second sentence only when it adds a question argument.
        chosen = [ranked[0][0]]
        covered = set(chosen[0]["words"]) & _terms(q)
        from verantyx.typed_edges import _tagger
        people = {t.surface for t in _tagger()(q) if t.feature.pos2 == "固有名詞"}
        for row, score, hit, _ in ranked[1:]:
            if len(chosen) >= 3:
                break
            if people and not any(person in row["text"] for person in people):
                continue
            if hit - covered and any(u in _COUNT_UNITS for _, u, _ in _quantities(row["text"])):
                chosen.append(row)
                covered |= hit
        values = [(n, u) for row in chosen for n, u, _ in _quantities(row["text"])
                  if u in _COUNT_UNITS]
        explicit = [(n, u) for row in chosen for n, u, raw in _quantities(row["text"])
                    if u in _COUNT_UNITS and re.search(r"合計\s*" + re.escape(raw), row["text"])]
        if explicit:
            values = explicit
        if len(values) >= 2 or (len(values) == 1 and len(chosen) == 1):
            total = sum(n for n, _ in values)
            result = f"{total:,.0f}{unit}です。"
            trace.append({"part": "answer.count", "method": "sum_listed_items",
                          "operands": values, "result": result})
            return _ordered(chosen), result, trace
    section = re.search(r"第(\d+)条", q)
    if section and "いくつ" in q:
        start = next((s["index"] for s in pool if s["text"].startswith(f"第{section.group(1)}条")), None)
        if start is not None:
            rows = [s for s in pool if s["index"] >= start]
            rows = rows[:next((i for i, s in enumerate(rows[1:], 1)
                               if re.match(r"^第\d+条", s["text"])), len(rows))]
            if 2 <= len(rows) <= 12:
                result = f"{len(rows)}つです。"
                trace.append({"part": "answer.count", "method": "section_items",
                              "items": [s["text"] for s in rows], "result": result})
                return rows, result, trace
            if len(rows) == 1 and "、" in rows[0]["text"]:
                from verantyx.typed_edges import _tagger
                question_nouns = {t.surface for t in _tagger()(q)
                                  if t.feature.pos1 == "名詞" and len(t.surface) >= 2}
                prefix = rows[0]["text"].split("は", 1)[0]
                repeated = [(prefix.count(noun), noun) for noun in question_nouns
                            if prefix.count(noun) >= 2]
                if repeated:
                    count, noun = max(repeated)
                    result = f"{count}つです。"
                    trace.append({"part": "answer.count", "method": "repeated_list_head",
                                  "head": noun, "result": result})
                    return rows, result, trace
    if quantities:
        n, found_unit, raw = (max(quantities, key=lambda x: x[0])
                              if re.search(r"最大|最長|上限", q) else quantities[0])
        trace.append({"part": "answer.count", "method": "stated_number",
                      "sentence": selected[0]["text"], "value": raw})
        if "誰" in q or "合計" in q:
            return _ordered(selected), "", trace
        return _ordered(selected), f"{raw}です。", trace
    # Count an explicit coordinated list before its topic marker.
    head = selected[0]["text"].split("は", 1)[0]
    head = re.sub(r"^第\d+条[\s　]*", "", head)
    listing = head if "、" in head else next((m.group(0) for m in
                    re.finditer(r"[一-鿿ァ-ヶー]+(?:、[一-鿿ァ-ヶー]+){2,}", selected[0]["text"])), "")
    if "、" in listing:
        parts = [p for p in re.split(r"、|と", listing) if p]
        if 2 <= len(parts) <= 12:
            result = f"{len(parts)}{unit or 'つ'}です。"
            trace.append({"part": "answer.count", "method": "listed_items",
                          "items": parts, "result": result})
            return selected, result, trace
    if "両方" in selected[0]["text"]:
        trace.append({"part": "answer.count", "method": "both", "result": "2つです。"})
        return selected, "2つです。", trace
    return [], "", trace


def _daily_allowance(q: str, pool: list[dict]) -> tuple[list[dict], str, dict] | None:
    if re.search(r"か[。？?]*$", q) and not re.search(r"いくら|何円|金額", q):
        return None
    own_rows = [(row, match) for row in pool
                if (match := re.search(rf"({_NUMBER})時間(?!以上|以下|未満)", row["text"]))
                and len(_MONEY.findall(row["text"])) == 0]
    anchors = [term for term in _terms(q) if len(term) >= 2 and
               sum(term in row["text"] for row, _ in own_rows) == 1]
    from verantyx.typed_edges import _tagger
    names = {t.surface for t in _tagger()(q) if t.feature.pos2 == "固有名詞"}
    own = next(((row, match) for row, match in own_rows
                if any(term in row["text"] for term in anchors) and
                (not names or any(name in row["text"] for name in names))), None)
    if own is None:
        return None
    stay, match = own
    anchor = max((name for name in names if name in stay["text"]), key=len,
                 default=max((term for term in anchors if term in stay["text"]), key=len))
    rate = next((s for s in pool if "時間以上" in s["text"] and _MONEY.search(s["text"]) and
                 len(_terms(q) & set(s["words"])) >= 1), None)
    if rate is None:
        return None
    hours = _number(match.group(1))
    if hours is None:
        return None
    bands = [(int(a), int(b), int(c.replace(",", ""))) for a, b, c in
             re.findall(r"(\d+)時間以上(\d+)時間未満なら([\d,]+)円", rate["text"])]
    open_bands = [(int(a), int(c.replace(",", ""))) for a, c in
                  re.findall(r"(\d+)時間以上なら([\d,]+)円", rate["text"])]
    amount = next((yen for low, high, yen in bands if low <= hours < high), None)
    if amount is None:
        amount = next((yen for low, yen in open_bands if hours >= low), None)
    if amount is None:
        return None
    selected = [stay, rate]
    deductions = []
    applied_rows = [row for row in pool if anchor in row["text"] and "付き" in row["text"]]
    included = [word for row in applied_rows
                for word in re.findall(r"([一-鿿ァ-ヶー]{2,8})付き", row["text"])]
    if included:
        deduction = next((s for s in pool if any(word + "付き" in s["text"] for word in included)
                          and "差し引" in s["text"]), None)
        applied = applied_rows[0]
        if deduction and applied:
            m = re.search(r"([\d,]+)円を差し引", deduction["text"])
            if m:
                deduct = int(m.group(1).replace(",", ""))
                amount -= deduct
                selected += [applied, deduction]
                deductions.append(deduct)
    answer = f"{amount:,.0f}円です。"
    return _ordered(selected), answer, {"part": "answer.amount", "hours": hours,
                                        "deductions": deductions, "result": amount}


def _money_total(q: str, ranked: list[tuple]) -> tuple[list[dict], str, dict] | None:
    """Multiply an explicit item count by a bound per-item amount."""
    if not re.search(r"合計|総額|合わせて|全部で", q) or not re.search(r"いくら|何円", q):
        return None
    counts = [(n, unit) for n, unit, _ in _quantities(q) if unit in _COUNT_UNITS]
    if len(counts) != 1:
        return None
    count, counter = counts[0]
    asked_money = {n * (10000 if unit == "万円" else 1)
                   for n, unit, _ in _quantities(q) if unit in ("万円", "円")}
    for row, score, hit, _ in ranked:
        if len(hit) < 2 or score < .5:
            continue
        amounts = [(n * (10000 if unit == "万円" else 1), raw)
                   for n, unit, raw in _quantities(row["text"])
                   if unit in ("万円", "円")]
        if not amounts:
            continue
        if asked_money:
            if not asked_money <= {n for n, _ in amounts}:
                continue
            rates = [(n, raw) for n, raw in amounts if n not in asked_money]
            if len(rates) != 1:
                continue
        else:
            if len(amounts) != 1 or not re.search(r"各|ずつ|ごと|当たり", row["text"]):
                continue
            rates = amounts
            row_counts = [(n, unit) for n, unit, _ in _quantities(row["text"])
                          if unit == counter]
            if row_counts and count not in [n for n, _ in row_counts]:
                continue
        total = count * rates[0][0]
        result = f"{total:,.0f}円です。"
        return [row], result, {"part": "answer.amount", "method": "count_times_rate",
                               "operands": [count, rates[0][0]], "result": result}
    return None


def _enumerated_items(q: str, pool: list[dict]) -> tuple[list[dict], dict] | None:
    requested = re.search(r"(?:項目|費目)を(\d+)つ挙げ", q)
    if not requested:
        return None
    wanted = int(requested.group(1))
    if not 1 <= wanted <= 6:
        return None
    from verantyx.typed_edges import _tagger
    names = {t.surface for t in _tagger()(q) if t.feature.pos2 == "固有名詞"}
    named = sorted((s for s in pool if _quantities(s["text"]) and
                    len(_terms(q) & set(s["words"])) >= 2 and
                    not any(name in s["text"] for name in names)),
                   key=lambda s: (-len(_terms(q) & set(s["words"])), s["index"]))
    if len(named) < wanted:
        return None
    selected = named[:wanted]
    personal = next((s for s in pool if any(name in s["text"] for name in names) and
                     len(_terms(q) & set(s["words"])) >= 2), None)
    if personal is not None:
        selected.append(personal)
    return _ordered(selected), {"part": "answer.enumerate", "requested": wanted,
                                "sentences": [s["text"] for s in selected]}


def _reason_rows(q: str, pool: list[dict]) -> tuple[list[dict], dict] | None:
    qterms = _terms(q)
    target_terms = _terms(q.split("なぜ", 1)[-1]) if "なぜ" in q else set()
    df = Counter(w for s in pool for w in set(s["words"]))
    anchors = {w for w in qterms if len(w) >= 2 and df[w] and df[w] <= max(2, len(pool) // 4)}
    candidates = []
    for row in pool:
        marker = _CAUSAL.search(row["text"]) or _CONSEQUENCE.search(row["text"])
        if marker is None:
            continue
        direct = qterms & set(row["words"])
        linked = [row]
        neighbors = [s for s in pool if s["doc"] == row["doc"] and
                     -2 <= s["index"] - row["index"] <= 1 and s is not row]
        neighbors.sort(key=lambda s: (-len(qterms & set(s["words"])),
                                      abs(s["index"] - row["index"])))
        for neighbor in neighbors:
            if (direct and len(qterms & set(neighbor["words"])) >= 2 and
                    (len(direct) < 2 or (anchors and not (direct & anchors)) or
                     re.match(r"^(?:これ|それ|この|その)", row["text"]))):
                linked.append(neighbor)
                break
        covered = qterms & set().union(*(set(s["words"]) for s in linked))
        if len(covered) < 2 or (anchors and not (covered & anchors)):
            continue
        # A consequence in the immediately following sentence can explain a
        # rule, but adjacency alone never establishes a reason.
        explicit = bool(_CAUSAL.search(row["text"]))
        consequence = bool(_CONSEQUENCE.search(row["text"]))
        if not (explicit or consequence):
            continue
        candidates.append((int(explicit), len(target_terms & set(row["words"])),
                           len(covered), len(direct), row, linked))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], -x[1], -x[2], -x[3], x[4]["index"]))
    explicit, _, _, _, cause, linked = candidates[0]
    return _ordered(linked), {"part": "answer.reason", "sentence": cause["text"],
                              "linked": [s["text"] for s in linked],
                              "verdict": "EXPLICIT_CAUSE" if explicit else "EXPLICIT_CONSEQUENCE"}


def _relevant_clause(q: str, sentence: str) -> str:
    from verantyx.typed_edges import _tagger
    from verantyx.frames import read_all

    clauses = [part.strip() for part in re.split(r"[、，]", sentence) if part.strip()]
    if len(clauses) < 2:
        return sentence
    focus = q.rsplit("、", 1)[-1]
    markers = set(re.findall(r"[月火水木金土日]曜日|\d+(?:\.\d+)?(?:分|時|日|月|円|人|度)", q))
    with_marker = [clause for clause in clauses if any(marker in clause for marker in markers)]
    if "、" not in q and len(with_marker) == 1:
        return with_marker[0]
    focus_nouns = [t.surface for t in _tagger()(focus) if t.feature.pos1 == "名詞"
                   and t.surface not in _STOP and len(t.surface) >= 2]
    if focus_nouns:
        with_focus = [clause for clause in clauses if focus_nouns[-1] in clause]
        if len(with_focus) == 1:
            return with_focus[0]
    main = next((f.predicate for f in reversed(read_all(q)) if f.predicate not in
                 ("する", "ある", "いる", "なる", "言う", "思う", "報告する", "述べる")), "")
    if main:
        stem = main[:-1] if main.endswith("る") else main.removesuffix("する")
        with_predicate = [clause for clause in clauses if len(stem) >= 2 and stem[:2] in clause]
        if len(with_predicate) == 1:
            return with_predicate[0]
    nouns = {t.surface for t in _tagger()(focus) if t.feature.pos1 == "名詞"
             and t.surface not in _STOP and not t.surface.isdigit()}
    if not nouns:
        return sentence
    last_noun = next((t.surface for t in reversed(list(_tagger()(focus)))
                      if t.feature.pos1 == "名詞" and t.surface in nouns), "")
    scored = [(sum(len(noun) for noun in nouns if noun in clause) +
               (3 * len(last_noun) if last_noun and last_noun in clause else 0), clause)
              for clause in clauses]
    scored.sort(key=lambda item: -item[0])
    if scored[0][0] and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return with_marker[0] if len(with_marker) == 1 else sentence


@lru_cache(maxsize=8192)
def _yes_no(q: str, sentence: str) -> str | None:
    """Compare one asked proposition to cited clauses; unknown stays unknown."""
    from verantyx.frames import canonical, read_all
    from verantyx.intent_frames import VERBS
    from verantyx.polarity import observe_negation

    from verantyx.typed_edges import _tagger

    full_sentence = sentence
    sentence = _relevant_clause(q, sentence)

    # A quantity limit is a proposition about the same measured dimension.
    q_values = [(n, u) for n, u, _ in _quantities(q)]
    s_values = [(n, u) for n, u, _ in _quantities(sentence)]
    q_cap = re.search(rf"({_NUMBER})\s*({'|'.join(_COUNT_UNITS)})まで", q)
    s_cap = re.search(rf"({_NUMBER})\s*({'|'.join(_COUNT_UNITS)})まで", sentence)
    if q_cap and s_cap and q_cap.group(2) == s_cap.group(2):
        asked_cap, stated_cap = _number(q_cap.group(1)), _number(s_cap.group(1))
        if asked_cap is not None and stated_cap is not None:
            return "はい。" if asked_cap <= stated_cap else "いいえ。"
    # A single measured eligibility threshold can be checked arithmetically.
    # A second quantity in the same dimension may encode another condition,
    # so this direct comparison is deliberately limited to one value.
    if re.search(r"対象|加入|適用|認め|可能", q) and len([1 for _, u in q_values if u in ("円", "万円")]) == 1:
        amount = next(((n, u) for n, u in q_values if u in ("円", "万円")), None)
        threshold = re.search(rf"({_NUMBER})\s*(万円|円)\s*(以上|以下)", sentence)
        if amount and threshold and len(_terms(q) & _terms(full_sentence)) >= 2:
            stated = _number(threshold.group(1))
            if stated is not None:
                asked_yen = amount[0] * (10000 if amount[1] == "万円" else 1)
                stated_yen = stated * (10000 if threshold.group(2) == "万円" else 1)
                eligible = asked_yen >= stated_yen if threshold.group(3) == "以上" else asked_yen <= stated_yen
                return "はい。" if eligible else "いいえ。"
    if re.search(r"超え|過ぎ|より多|より長", q) and re.search(r"以内|以下|まで|未満", sentence):
        if any(qn >= sn and _unit_matches(qu, su) for qn, qu in q_values for sn, su in s_values):
            return "いいえ。"
    if re.search(r"必ず|必須|常に|全て|すべて", q) and re.search(
            r"ことがある|場合がある|に応じて|原則|推奨|任意|条件とはしな", sentence):
        return "いいえ。" if len(_terms(q) & _terms(sentence)) >= 1 else None
    if re.search(r"不要|必要(?:は|が)ない", q) and re.search(r"必要(?:です|である|とする|がある)", sentence):
        return "いいえ。" if len(_terms(q) & _terms(sentence)) >= 1 else None
    if re.search(r"対象.{0,6}か[。？?]*$", q) and "対象外" in sentence:
        return "いいえ。" if len(_terms(q) & _terms(sentence)) >= 1 else None
    focus = q.rsplit("、", 1)[-1]
    asked_action = re.search(r"([一-鿿ァ-ヶー]{2,12})(?:され|します|できます)", focus)
    if asked_action and re.search(re.escape(asked_action.group(1)) +
                                  r"(?:は|が)?(?:ありませ|ありません|ない)", sentence):
        return "いいえ。"
    if ("同じ" in q and "同じ" in full_sentence and
            len(_terms(q) & _terms(full_sentence)) >= 4 and
            set(re.findall(r"\d+(?:\.\d+)?", q)) <= set(re.findall(r"\d+(?:\.\d+)?", full_sentence))):
        return "はい。" if not observe_negation(full_sentence).observed else "いいえ。"
    if (re.search(r"だけ.{0,12}(?:断定|判断|決め)", q) and
            re.search(r"両方|双方|他にも|同じ", full_sentence) and
            len(_terms(q) & _terms(full_sentence)) >= 2):
        return "いいえ。"

    q_frames = read_all(q)
    s_frames = read_all(sentence)
    op = {verb: operation for verb, operation, _ in VERBS}
    # Predicate opposition is shared across topics; it compares the event,
    # never a named item in an evaluation document.
    op.update({"共用する": "SHARE", "分ける": "SEPARATE",
               "消える": "DISAPPEAR", "残る": "PERSIST"})
    opposites = {("OPEN", "CLOSE"), ("CLOSE", "OPEN"),
                 ("SHARE", "SEPARATE"), ("SEPARATE", "SHARE"),
                 ("DISAPPEAR", "PERSIST"), ("PERSIST", "DISAPPEAR")}
    q_polarity = observe_negation(q)
    s_polarity = observe_negation(sentence)
    q_nouns = [t.surface for t in _tagger()(q) if t.feature.pos1 == "名詞"
               and t.surface not in _STOP and not t.surface.isdigit()]
    s_nouns = {t.surface for t in _tagger()(sentence) if t.feature.pos1 == "名詞"}
    shared_nouns = set(q_nouns) & s_nouns
    if not shared_nouns:
        return None
    q_main = next((f for f in reversed(q_frames) if f.predicate not in
                   ("する", "なる", "言う", "思う", "報告する", "述べる")), None)
    if q_main is None:
        return None
    # The last event in a conditional question is the assertion being asked.
    # Earlier events are premises and cannot by themselves prove "yes".
    premises = q_frames[:-1]
    q_frames = [q_main]
    focus_nouns = [t.surface for t in _tagger()(q.rsplit("、", 1)[-1])
                   if t.feature.pos1 == "名詞" and t.surface not in _STOP]
    if len(q_nouns) >= 2 and len(shared_nouns) < 2 and not any(
            role and role in sentence for role in (q_main.agent, q_main.patient, q_main.recipient)) and not (
            focus_nouns and focus_nouns[-1] in sentence):
        return None
    candidates = []
    for asked in q_frames:
        if asked.predicate in ("する", "なる", "言う", "思う"):
            continue
        for stated in s_frames:
            if stated.predicate in ("する", "なる", "言う", "思う"):
                continue
            same = asked.predicate == stated.predicate
            opposite = (op.get(asked.predicate), op.get(stated.predicate)) in opposites
            if not (same or opposite):
                continue
            # A shared event argument is required; the proposition cannot be
            # licensed by the topic word alone.
            asked_roles = {canonical(x) for x in (asked.agent, asked.patient, asked.recipient) if x}
            stated_roles = {canonical(x) for x in (stated.agent, stated.patient, stated.recipient) if x}
            role_overlap = any(a == b or a.endswith(b) or b.endswith(a)
                               for a in asked_roles for b in stated_roles)
            if asked_roles and stated_roles and not role_overlap and len(shared_nouns) < 2:
                continue
            q_neg = asked.negated
            s_neg = stated.negated
            if not q_neg and q_polarity.observed and len(q_frames) == 1:
                q_neg = True
            if not s_neg and s_polarity.observed and len(s_frames) == 1:
                s_neg = True
            candidates.append("いいえ。" if (q_neg != s_neg) ^ opposite else "はい。")
    if len(set(candidates)) == 1 and candidates:
        return candidates[0]
    if candidates:
        return None
    if re.search(r"ず[、，]|ないで[、，]", q):
        for asked in premises:
            if not asked.negated:
                continue
            for stated in s_frames:
                if (asked.predicate == stated.predicate and not stated.negated and
                        any(role and role in sentence for role in
                            (asked.agent, asked.patient, asked.recipient))):
                    return "いいえ。"
    # Closed rule modality still decides a direct permission question when
    # its action noun and a condition are both repeated in the prohibition.
    if re.search(r"(?:できます|できる|てよい|認められ)", q) and re.search(r"禁止|てはいけな|てはいけません|てはならな|認められな", sentence):
        return "いいえ。" if len(shared_nouns) >= 2 else None
    # A light verb may hide the action in a noun ("予約できる" versus
    # "予約もできる"). A direct modal clause still licenses a relation when
    # it shares the question's arguments and action noun.
    focus_terms = _terms(focus)
    carried = focus_terms & _terms(sentence)
    action_noun = next((n for n in reversed(q_nouns) if len(n) >= 2 and n in sentence), "")
    if (action_noun and len(carried) >= 2 and len(shared_nouns) >= 2 and
            re.search(r"でき|認め|許可|必要|禁止|しない|しません|ならない|行わな|見送|とする", sentence)):
        return "はい。" if bool(q_polarity.observed) == bool(s_polarity.observed) else "いいえ。"
    if (len(shared_nouns) >= 2 and bool(s_polarity.observed) and
            re.search(r"できますか|できるか|てよい|必須|必要", q) and
            re.search(r"ない|ません|禁止|対象外|見送", sentence)):
        return "はい。" if q_polarity.observed else "いいえ。"
    if full_sentence != sentence:
        parts = [part.strip() for part in re.split(r"[、，]", full_sentence) if part.strip()]
        relations = {_yes_no(q, part) for part in parts if part != sentence} - {None}
        if len(relations) == 1:
            return relations.pop()
    return None


def _refusal(trace: list[dict], q: str, evidence: list[str] | None = None) -> dict:
    trace.append({"part": "answer.slot", "verdict": "NOT_IN_DOCS", "asked": q})
    english = lang(q) == "en"
    return {"text": "Sorry, the documents do not say." if english else "文書には書かれていません。",
            "kind": "unknown", "verdict": "NOT_IN_DOCS",
            "evidence": evidence or [], "source": None,
            "how_to_resolve": ("Add a document stating the requested fact." if english else
                               "質問された事項を明記した文書を追加してください。"), "trace": trace}


def _required_slots(q: str, primary: str | None) -> list[str]:
    slots = [primary] if primary else []
    for pattern, slot in ((r"なぜ|どうして|理由(?:は|を|が|の|か)", "why"),
                          (r"(?<!な)いつ|何時|何日|何年|何曜", "when"),
                          (r"どこ|どちらへ", "where"),
                          (r"誰|だれ", "who"),
                          (r"いくら|何円", "how much"),
                          (r"何(?:人|台|本|個|件|組|隻|種類|品目|脚|単位|冊|匹|点|枚)", "how many")):
        if re.search(pattern, q) and slot not in slots:
            slots.append(slot)
    return slots


def _compose_existing(bot: Bot, query: Query) -> dict:
    original = query.surface.value
    q = _clean_question(original)
    kind = query.kind.value
    slot = query.asked_slot.value
    trace: list[dict] = [{"part": "question.read", "kind": kind, "asked_slot": slot,
                          "stage_split": query.stages.value.verdict},
                         {"part": "bot.ingest", "injected_data": sum(bool(s["injected"]) for s in bot.sents)}]
    reached = bot.base.find(q) if lang(q) == "ja" else {
        "leaf": None, "path": "english_documents", "route_trace": {},
        "sentences": [s["text"] for s in bot.sents if s["lang"] == "en"]}
    trace.append({"part": "base.find", "path": reached["path"], "leaf": reached["leaf"],
                  "route": reached["route_trace"],
                  "fallback": reached.get("fallback_trace", {})})
    allowed = set(reached["sentences"])
    pool = [s for s in bot.sents if not s["injected"] and s["lang"] == lang(q)
            and s["text"] in allowed]
    if not pool:
        return _refusal(trace, q)
    absent_rows = [s for s in pool if _explicit_absence(s["text"]) and
                   len({w for w in _terms(q) & set(s["words"]) if len(w) >= 2}) >= 2 and
                   (not re.findall(r"\d+(?:\.\d+){1,}", q) or
                    set(re.findall(r"\d+(?:\.\d+){1,}", q)) <=
                    set(re.findall(r"\d+(?:\.\d+){1,}", s["text"]))) ]
    if absent_rows and re.search(r"何|いつ|いくら|最終", q):
        return _refusal(trace, q, [absent_rows[0]["text"]])
    allowance = _daily_allowance(q, pool)
    rank_slot = None if kind == "multi_hop" or allowance else slot
    ranked = _rank(q, pool, kind, rank_slot)
    section_count = bool(re.search(r"第\d+条", q) and "いくつ" in q)
    if section_count and not ranked:
        section = re.search(r"第\d+条", q).group(0)
        heading = next((s for s in pool if s["text"].startswith(section)), None)
        if heading is not None:
            ranked = [(heading, 1.0, _terms(q) & set(heading["words"]), "section_items")]
    trace.append({"part": "answer.rank", "candidates": [
        {"sentence": row["text"], "score": round(score, 3), "slot": why}
        for row, score, _, why in ranked[:5]]})
    if not ranked:
        # A statement of absence is still document evidence for the refusal.
        absent = [s["text"] for s in pool if _explicit_absence(s["text"]) and
                  len({w for w in _terms(q) & set(s["words"]) if len(w) >= 2}) >= 2]
        return _refusal(trace, q, absent[:1])
    yes_no = (bool(re.search(r"(?:か|でしょう)[。？?]*$", q)) and slot == "whether" and
              not re.search(r"誰|何|なぜ|どう|どの|どれ|いくら|いつ|どこ|それぞれ", q))
    if yes_no:
        top_score = ranked[0][1]
        related = [(row, score, hit, why, relation)
                   for row, score, hit, why in ranked
                   if score >= max(top_score * .55, top_score - 1.0)
                   and (relation := _yes_no(q, row["text"])) is not None]
        trace.append({"part": "answer.proposition", "relations": [
            {"sentence": row["text"], "relation": relation, "score": round(score, 3)}
            for row, score, _, _, relation in related[:5]]})
        if not related or (len(related) > 1 and related[0][4] != related[1][4]
                           and related[0][1] - related[1][1] < .15):
            return _refusal(trace, q)
        chosen = related[0][:4]
        ranked = [chosen] + [entry for entry in ranked if entry[0] is not chosen[0]]
    best, best_score, hit, reason = ranked[0]
    reason_rows = _reason_rows(q, pool) if kind == "why" else None
    if not yes_no and not _strong_enough(q, best, hit, best_score) and reason != "adjacent_argument" and \
            not allowance and not reason_rows and not section_count:
        return _refusal(trace, q)
    selected: list[dict] = [best]
    if reason == "adjacent_argument":
        antecedent = _next_to(pool, best, -1)
        if antecedent is not None and antecedent["doc"] == best["doc"]:
            selected = _ordered([antecedent, best])
    derived = ""
    money_total = _money_total(q, ranked) if slot == "how much" else None
    enumerated = _enumerated_items(q, pool)
    if kind == "why":
        if reason_rows is None:
            return _refusal(trace, q)
        selected, reason_trace = reason_rows
        trace.append(reason_trace)
    elif kind == "comparison":
        selected, derived, comparison_trace = _comparison(q, ranked, pool)
        trace.extend({"part": "answer.comparison", **step} for step in comparison_trace)
    elif kind == "count" or (slot == "how many" and "いくつ" in q):
        selected, derived, count_trace = _count(q, ranked, pool)
        trace.extend(count_trace)
    elif kind == "multi_hop" or allowance:
        selected, stage_trace = _multi_candidates(q, ranked, pool, query.stages.value.stages)
        trace.extend({"part": "answer.stage", **step} for step in stage_trace)
        if allowance:
            selected, derived, calc_trace = allowance
            trace.append(calc_trace)
    elif kind == "fact" and slot != "who" and "その半分" in best["text"]:
        selected, stage_trace = _multi_candidates(q, ranked, pool, ())
        trace.extend({"part": "answer.stage", **step} for step in stage_trace)
    elif kind in ("condition", "exception", "negation"):
        # A condition may have its consequence in the following sentence.
        if slot != "whether" or re.search(r"それぞれ|また|何[^。]*、[^。]*何|誰[^。]*、[^。]*誰", q):
            selected, stage_trace = _multi_candidates(q, ranked, pool, query.stages.value.stages)
            trace.extend({"part": "answer.stage", **step} for step in stage_trace)
    if money_total:
        selected, derived, calc_trace = money_total
        trace.append(calc_trace)
    if enumerated and kind == "fact":
        selected, enumeration_trace = enumerated
        trace.append(enumeration_trace)
    if reason == "adjacent_argument" and best in selected:
        antecedent = _next_to(pool, best, -1)
        if antecedent is not None and antecedent["doc"] == best["doc"]:
            selected = _ordered(selected + [antecedent])
    if not selected:
        return _refusal(trace, q)
    required = _required_slots(q, slot)
    for required_slot in required:
        if section_count and derived and required_slot == "how many":
            trace.append({"part": "answer.part", "slot": required_slot, "verdict": "BOUND",
                          "method": "section_items"})
            continue
        if (any(_slot_support(q, required_slot, kind, row["text"])[0] for row in selected) or
                (len(selected) > 1 and _slot_support(
                    q, required_slot, kind, " ".join(row["text"] for row in selected))[0])):
            trace.append({"part": "answer.part", "slot": required_slot, "verdict": "BOUND"})
            continue
        alternatives = _rank(q, pool, kind, required_slot)
        alternative = next((row for row, score, words, _ in alternatives
                            if _strong_enough(q, row, words, score)), None)
        if alternative is None:
            trace.append({"part": "answer.part", "slot": required_slot, "verdict": "MISSING"})
            return _refusal(trace, q, [s["text"] for s in selected])
        selected = _ordered(selected + [alternative])
        trace.append({"part": "answer.part", "slot": required_slot,
                      "verdict": "BOUND", "sentence": alternative["text"]})
    selected, links = _linked_exceptions(bot, selected, pool)
    trace.append({"part": "verdict.read_records", "exception_links": links})
    evidence = [s["text"] for s in selected]
    if any(_explicit_absence(s) for s in evidence):
        return _refusal(trace, q, evidence)
    supported_slots = 0
    for s in selected:
        valid, why = _slot_support(q, slot, kind, s["text"])
        supported_slots += bool(valid)
        trace.append({"part": "answer.slot", "sentence": s["text"],
                      "supported": valid, "reason": why})
    if not supported_slots and len(selected) > 1:
        supported_slots = int(_slot_support(
            q, slot, kind, " ".join(row["text"] for row in selected))[0])
    if not supported_slots and not derived:
        return _refusal(trace, q)
    if yes_no:
        relations = {_yes_no(q, s["text"]) for s in selected} - {None}
        if len(relations) != 1:
            return _refusal(trace, q, evidence)
        prefix = relations.pop()
    else:
        prefix = ""
    if re.search(r"答えず[『「][^』」]+[』」]とすべきか", original):
        prefix = "いいえ。"
    if derived and len(required) > 1:
        text = prefix + derived + " " + " ".join(evidence)
    else:
        text = (prefix + derived) if derived else (prefix + " ".join(evidence))
    trace.append({"part": "answer.compose", "evidence": evidence,
                  "derived": derived, "yes_no": prefix})
    source = selected[0]["doc"] if len({s["doc"] for s in selected}) == 1 else None
    return {"text": text, "kind": "answer", "verdict": "ANSWER", "source": source,
            "evidence": evidence, "trace": trace}


def compose(bot: Bot, query: Query) -> dict:
    result = _compose_existing(bot, query)
    if result.get("verdict") != "NOT_IN_DOCS" or query.kind.value in ("summary", "instruction", "chat"):
        return result
    from .answer_slots import calculate, read_slot, same_subject, select
    asked = query.case_frame.value if query.case_frame else read_slot(query.surface.value, query.asked_slot.value or "what")
    reached = bot.base.find(_clean_question(query.surface.value))
    allowed = set(reached["sentences"])
    pool = [row for row in bot.sents if row["text"] in allowed and not row["injected"]]
    calculated = calculate(query.surface.value, [{"text": row["text"], "source": row["doc"], "row": row} for row in pool])
    if calculated is not None:
        evidence = [row["text"] for row in calculated["rows"]]
        return {"kind": "answer", "verdict": "ANSWER", "text": calculated["text"], "evidence": evidence,
                "sources": [{"family": "document", "source": row["source"], "text": row["text"]} for row in calculated["rows"]],
                "trace": result["trace"] + [{"part": "answer_slots.calculate", "status": "ran", **calculated["calculation"]}]}
    candidates = []
    for row in pool:
        candidates.append({"text": row["text"], "source": row["doc"], "independent": row["doc"],
                           "rows": [row]})
        preceding = next((other for other in bot.sents if other["doc"] == row["doc"] and
                          other["index"] == row["index"] - 1 and not other["injected"]), None)
        if preceding is None:
            continue
        previous_frame, own_frame = read_slot(preceding["text"]), read_slot(row["text"])
        linked = same_subject(previous_frame.subject, own_frame.subject) or (
            same_subject(asked.subject, previous_frame.subject) and
            (not own_frame.subject or re.match(r"(?:それ|その|この|ただし|なお)", row["text"])))
        if linked:
            candidates.append({"text": preceding["text"] + " " + row["text"], "source": row["doc"],
                               "independent": row["doc"], "rows": [preceding, row]})
    chosen = select(candidates, asked)
    step = {"part": "answer_slots.document", "status": "ran" if chosen["verdict"] == "ANSWER" else "abstained",
            "verdict": chosen["verdict"], "frame": asked.as_dict()}
    if chosen["verdict"] != "ANSWER":
        result["trace"].append(step)
        return result
    selected, links = _linked_exceptions(bot, chosen["rows"][0]["rows"], [row for row in bot.sents if not row["injected"]])
    evidence = [row["text"] for row in selected]
    return {"kind": "answer", "verdict": "ANSWER", "text": " ".join(evidence),
            "source": chosen["rows"][0]["source"], "evidence": evidence,
            "sources": [{"family": "document", "source": row["doc"], "text": row["text"]} for row in selected],
            "trace": result["trace"] + [step, {"part": "answer_slots.join", "status": "ran",
                       "sentences": len(evidence), "exception_links": links}]}

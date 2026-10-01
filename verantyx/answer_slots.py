"""Subject, predicate and value bindings shared by corpus and document answers."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Callable, Mapping

from .frames import _causative, _predicates, canonical, read_all
from .typed_edges import _base, _tagger


_ASK = re.compile(r"なぜ|どうして|どこ|いつ|誰|だれ|いくつ|いくら|何(?:故)?|どんな|どのよう|どれ")
_GENERIC = {"何", "誰", "どこ", "いつ", "理由", "方法", "場所", "こと", "もの", "ため", "場合", "方", "私", "それ"}
_COPULA = {"ある", "いる", "する", "なる", "だ", "です", "為る", "有る", "居る", "成る"}
_REQUESTS = {"教える", "答える", "説明する", "示す", "述べる", "挙げる", "くださる"}
_ATTRIBUTES = (
    ("material", r"材料|材質|何から|何で(?:でき|作)|できて|作られ"),
    ("color", r"色|何色"), ("name", r"名前|名称|氏名"),
    ("place", r"場所|所在地|住所|どこ|どちらへ"),
    ("time", r"日時|時刻|何時|いつ|何曜"),
    ("quantity", r"いくつ|何(?:人|個|台|本|枚|件|冊|匹)|数|合計"),
    ("money", r"何円|いくら|料金|金額|費用"),
    ("weight", r"重さ|重量|質量|何(?:キロ)?グラム"),
    ("capacity", r"容量|何(?:ミリ)?リットル"),
    ("size", r"寸法|大きさ|何(?:キロ)?メートル|何センチ"),
    ("model", r"型番"),
    ("definition", r"とは|って何|意味|定義"),
)
_REASON = re.compile(r"ため|ので|によって|により|原因|だから|(?:た|る|ない|です)から|because|due to", re.I)
_TIME = re.compile(r"\d+\s*(?:年|月|日|時|分|秒)|[一二三四五六七八九十]+時|曜日|午前|午後|毎週|翌日")
_PLACE = re.compile(r"(?:[一-鿿ァ-ヶA-Za-z0-9]+)(?:国|県|市|区|町|村|島|駅|室|階|窓口|受付|学校|大学|図書館|公園|海|川|山|地域|地方|番地)|(?:池|海|山|川|湖|森|沼|谷)(?:で|に|へ)|(?:に|で|へ)(?:位置|所在|ある|あります|いる|います)")
_VALUE = re.compile(r"(?:\d[\d,]*(?:\.\d+)?|[〇一二三四五六七八九十百千]+)\s*(?:人|名|個|台|本|枚|件|冊|匹|種類|回|つ|円|万円|年|月|日|時|分|秒|度|％|%|グラム|メートル|リットル)")
_ABSENCE = re.compile(r"書かれていない|記載がない|未定|不明|分かりません|わかりません")


@dataclass(frozen=True)
class SlotFrame:
    subject: str
    predicates: tuple[str, ...]
    arguments: tuple[str, ...]
    attribute: str
    slot: str
    negated: bool = False
    requested_unit: str = ""
    who_role: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def norm(text: str) -> str:
    return re.sub(r"\s+|[、。!?！？「」『』]", "", unicodedata.normalize("NFKC", text).casefold())


@lru_cache(maxsize=16384)
def nouns(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token.surface for token in _tagger()(text)
                              if token.feature.pos1 == "名詞" and token.surface not in _GENERIC
                              and not token.surface.isdecimal()))


def _subject(text: str, frames: list) -> str:
    cleaned = re.sub(r"^(?:なぜ|どうして|では|さて|ただし|なお)[、\s]*", "", text.strip())
    named = re.match(r"[「『]([^」』]+)[」』](?:は|が|の)", cleaned)
    if named:
        return named.group(1)
    topic = re.match(r"([^、。！？?]{1,45}?)(?:とは|って何|は|が)", cleaned)
    if topic:
        phrase = topic.group(1).strip()
        if not _ASK.search(phrase):
            owned = re.match(r"(.+?)の(?:色|名前|名称|住所|所在地|材料|材質|料金|数|重さ|容量)", phrase)
            return owned.group(1) if owned else phrase
    owned = re.match(r"(.+?)の(?:色|名前|名称|住所|所在地|材料|材質|料金|数|重さ|容量)", cleaned)
    if owned:
        return owned.group(1)
    for frame in frames:
        if frame.agent and not _ASK.search(frame.agent) and frame.agent not in _GENERIC:
            return frame.agent
    return ""


@lru_cache(maxsize=8192)
def read_slot(text: str, slot: str = "what") -> SlotFrame:
    frames = read_all(text)
    predicates = tuple(dict.fromkeys(canonical(frame.predicate) for frame in frames
                                    if frame.predicate and canonical(frame.predicate) not in _COPULA | _REQUESTS))
    attribute = next((key for key, pattern in _ATTRIBUTES if re.search(pattern, text)), "")
    if not attribute and not predicates and re.search(r"は.+(?:です|だ|である)[。？?]*$", text):
        attribute = "definition"
    subject = _subject(text, frames)
    arguments = tuple(dict.fromkeys(value for frame in frames
                                   for value in (frame.patient, frame.recipient)
                                   if value and not _ASK.search(value) and value not in _GENERIC))
    requested_unit = ""
    if re.search(r"何|いくら", text):
        from .answer import _requested_unit
        requested_unit = _requested_unit(text, slot)
    who_role = ("recipient" if re.search(r"(?:誰|だれ)に|to whom", text, re.I) else
                "agent" if re.search(r"(?:誰|だれ)(?:が|は|から)", text) else "identity") if slot == "who" else ""
    return SlotFrame(subject, predicates, arguments, attribute, slot,
                     any(frame.negated for frame in frames), requested_unit, who_role)


def keys(frame: SlotFrame) -> tuple[str, ...]:
    return (*frame.predicates, *(("@" + frame.attribute,) if frame.attribute else ()),
            *(("@definition",) if not frame.predicates and not frame.attribute else ()))


@lru_cache(maxsize=8192)
def index_slot(text: str) -> SlotFrame:
    """A cheap recall-only frame; runtime qualification always rereads full roles."""
    tokens = list(_tagger()(text))
    predicates = set()
    for index, predicate in _predicates(tokens):
        if index + 1 < len(tokens) and _base(tokens[index + 1]) in ("せる", "させる"):
            predicate = _causative(predicate)
        predicate = canonical(predicate)
        if predicate not in _COPULA | _REQUESTS:
            predicates.add(predicate)
    subject = _subject(text, [])
    attribute = next((key for key, pattern in _ATTRIBUTES if re.search(pattern, text)), "")
    for key, pattern in (("place", _PLACE), ("time", _TIME), ("quantity", _VALUE)):
        if pattern.search(text):
            predicates.add("@" + key)
    for key, pattern in (("money", r"\d+\s*(?:万円|円)"), ("weight", r"\d+\s*(?:キロ)?グラム"),
                         ("capacity", r"\d+\s*(?:ミリ)?リットル"), ("size", r"\d+\s*(?:キロ)?メートル")):
        if re.search(pattern, text):
            predicates.add("@" + key)
    return SlotFrame(subject, tuple(sorted(predicates)), (), attribute, "what")


def same_subject(asked: str, stated: str, aliases: Mapping[str, str] | None = None) -> bool:
    if not asked or not stated:
        return False
    aliases = aliases or {}
    def resolve(value: str) -> str:
        seen = set()
        while value in aliases and value not in seen:
            seen.add(value)
            value = aliases[value]
        return norm(value)
    return resolve(asked) == resolve(stated)


def carries_value(text: str, frame: SlotFrame) -> tuple[bool, str]:
    if _ABSENCE.search(text):
        return False, "explicit_absence"
    if frame.requested_unit:
        from .answer import _quantities, _unit_matches
        if not any(_unit_matches(frame.requested_unit, unit) for _, unit, _ in _quantities(text)):
            return False, "missing_requested_unit"
    if frame.slot == "why":
        return bool(_REASON.search(text)), "reason_clause"
    if frame.slot == "where":
        return bool(_PLACE.search(text)), "place"
    if frame.slot == "when":
        return bool(_TIME.search(text)), "time"
    if frame.slot in ("how many", "how much"):
        from .answer import _quantities, _unit_matches
        requested = frame.requested_unit
        values = _quantities(text)
        return bool(values and any(_unit_matches(requested, unit) for _, unit, _ in values)), "number_unit"
    if frame.slot == "who":
        if frame.who_role in ("agent", "recipient"):
            return any((value := getattr(stated, frame.who_role)) and value != frame.subject and
                       not _ASK.search(value) for stated in read_all(text)), "named_role"
        named = re.search(r"は([^。！？]+?)(?:です|だ|である|でした)[。！？]*$", text)
        return bool(named and nouns(named.group(1)) and not _ASK.search(named.group(1))), "named_identity"
    if frame.attribute == "color":
        return bool(re.search(r"色|赤|青|緑|黄|白|黒|紫|茶|橙|ピンク|透明", text)), "color"
    if frame.attribute == "material":
        return bool(re.search(r"から|で(?:でき|作)|製|材料|材質", text)), "material"
    return bool(nouns(text) or read_slot(text).predicates), "stated_value"


def qualifies(text: str, asked: SlotFrame, *, context: str = "", context_slot: str = "",
              aliases: Mapping[str, str] | None = None,
              relation: Callable[[str, str, str], bool] | None = None) -> tuple[bool, str]:
    stated = read_slot(text)
    contextual = read_slot(context, context_slot) if context else None
    bound = same_subject(asked.subject, stated.subject, aliases)
    if not bound and not stated.subject and contextual is not None:
        bound = same_subject(asked.subject, contextual.subject, aliases)
    if (not bound and asked.slot == "why" and context_slot == "why" and contextual is not None and
            same_subject(asked.subject, contextual.subject, aliases) and _REASON.search(text)):
        bound = True
    if not bound and asked.slot == "who" and not asked.subject:
        bound = bool(asked.arguments and set(asked.arguments) <= set(stated.arguments))
    if not bound:
        return False, "different_subject"
    if stated.negated != asked.negated:
        return False, "different_polarity"
    attested = set(stated.predicates)
    reason_only = asked.slot == "why" and context_slot == "why" and bool(re.search(
        r"(?:ため|ので|から)(?:です|だ|である)?[。!！?？]*$", text.strip()))
    if (contextual is not None and same_subject(asked.subject, contextual.subject, aliases) and
            (not stated.predicates or reason_only)):
        attested.update(contextual.predicates)
    if asked.predicates:
        if not all(predicate in attested or any(relation and relation(predicate, held, text) for held in attested)
                   for predicate in asked.predicates):
            return False, "different_predicate"
    elif asked.attribute:
        matching_attribute = (stated.attribute == asked.attribute or contextual is not None and
                              contextual.attribute == asked.attribute and context_slot == asked.slot)
        if not matching_attribute and not stated.predicates and asked.attribute in (
                "place", "time", "quantity", "money", "weight", "capacity", "size"):
            matching_attribute = carries_value(text, asked)[0]
        if not matching_attribute:
            return False, "different_attribute"
    elif context and context_slot != asked.slot:
        return False, "different_slot"
    elif not asked.subject:
        return False, "missing_subject"
    if asked.arguments and not all(argument in text or context and argument in context
                                   for argument in asked.arguments):
        return False, "different_argument"
    valid, reason = carries_value(text, asked)
    return valid, reason


def select(candidates: list[dict], asked: SlotFrame, *, aliases: Mapping[str, str] | None = None,
           relation: Callable[[str, str, str], bool] | None = None) -> dict:
    groups: dict[str, list[dict]] = {}
    rejected = []
    for candidate in candidates:
        valid, reason = qualifies(candidate["text"], asked, context=candidate.get("context", ""),
                                  context_slot=candidate.get("slot", ""), aliases=aliases, relation=relation)
        if valid:
            groups.setdefault(norm(candidate["text"]), []).append(candidate)
        else:
            stated = read_slot(candidate["text"])
            contextual = read_slot(candidate.get("context", ""))
            near = (int(same_subject(asked.subject, stated.subject, aliases) or
                        same_subject(asked.subject, contextual.subject, aliases)),
                    len(set(asked.predicates) & set(stated.predicates)),
                    int(carries_value(candidate["text"], asked)[0]))
            rejected.append({**candidate, "reason": reason, "closeness": near})
    ranked = sorted(groups.values(), key=lambda rows: -len({row["independent"] for row in rows}))
    rejected.sort(key=lambda row: row["closeness"], reverse=True)
    closest = [row for rows in ranked[:5] for row in rows[:1]] or rejected[:5]
    if not ranked or len(ranked) > 1 and len({row["independent"] for row in ranked[0]}) == len(
            {row["independent"] for row in ranked[1]}):
        return {"verdict": "TIED_ABSTAIN" if ranked else "UNKNOWN_NO_SLOT", "candidates": closest}
    return {"verdict": "ANSWER", "rows": ranked[0], "candidates": closest}


def calculate(question: str, candidates: list[dict]) -> dict | None:
    """Two explicit entities, one attested quantity each, and a cited arithmetic result."""
    if not re.search(r"差|合計|合わせ|difference|total", question, re.I):
        return None
    pair = re.match(r"[「『]?([^、。！？?と「」『』]{1,24})[」』]?と[「『]?([^、。！？?のは「」『』]{1,24})[」』]?(?:の|は|で)", question)
    if pair is None:
        return None
    from .answer import _quantities, _requested_unit, _unit_matches
    left, right = pair.groups()
    requested = _requested_unit(question)
    operands = []
    for subject in (left, right):
        values = {}
        for candidate in candidates:
            if re.search(r"ただし|場合|なら|とき|れば|たら|条件", candidate["text"]):
                continue
            stated = read_slot(candidate["text"])
            if not (same_subject(subject, stated.subject) or stated.subject.startswith(subject + "の")):
                continue
            quantities = [(value, unit) for value, unit, raw in _quantities(candidate["text"])
                          if _unit_matches(requested, unit)]
            if len(quantities) != 1:
                continue
            value, unit = quantities[0]
            if unit == "万円":
                value, unit = value * 10000, "円"
            if unit == "名":
                unit = "人"
            values.setdefault((value, unit), candidate)
        if len(values) != 1:
            return None
        value, source = next(iter(values.items()))
        operands.append((value, source))
    if operands[0][0][1] != operands[1][0][1]:
        return None
    operation = "difference" if re.search(r"差|difference", question, re.I) else "sum"
    first, second = operands[0][0][0], operands[1][0][0]
    result = abs(first - second) if operation == "difference" else first + second
    formatted = str(int(result)) if result.is_integer() else str(result)
    return {"verdict": "ANSWER", "text": formatted + operands[0][0][1] + "です。",
            "rows": [operand[1] for operand in operands],
            "calculation": {"operation": operation, "operands": [first, second], "unit": operands[0][0][1], "result": result}}

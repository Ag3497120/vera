"""A closed, attributed input/operation/output specification reader, not a code lookup."""
from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from typing import Any


IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_LITERAL = r"(?:None|null|true|false|True|False|-?\d+(?:\.\d+)?|'[^'\n]*'|\"[^\"\n]*\")"
_IGNORE_NAMES = {"python", "javascript", "sql", "shell", "posix", "none", "null", "true", "false",
                 "list", "dict", "records", "table", "input", "output", "function", "return", "and", "or"}


@dataclass(frozen=True)
class Operation:
    kind: str
    field: str = ""
    comparator: str = ""
    value: Any = None
    descending: bool = False


@dataclass
class Specification:
    language: str
    shape: str
    name: str
    fields: tuple[str, ...]
    operations: list[Operation]
    empty: Any = None
    empty_stated: bool = False
    unchanged: bool = False
    all_ties: bool = False
    stable: bool = False
    zero_division: Any = None
    table: str = ""
    other_table: str = ""
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def literal(raw: str) -> Any:
    translated = {"null": None, "none": None, "true": True, "false": False}
    return translated[raw.casefold()] if raw.casefold() in translated else ast.literal_eval(raw)


def _names(text: str) -> tuple[str, ...]:
    quoted = re.findall(r"[`「『'\"](" + IDENTIFIER + r")[`」』'\"]", text)
    declared = re.findall(r"(" + IDENTIFIER + r")\s*(?:列|フィールド|キー|属性|field|column|key)", text, re.I)
    objects = re.findall(r"\{([^{}]+)\}", text)
    for body in objects:
        declared.extend(re.findall(r"[\"']?(" + IDENTIFIER + r")[\"']?\s*:", body))
    grouped = re.findall(r"(?:fields?|columns?|キー|フィールド|列)\s*(?:は|:|：)?\s*([A-Za-z_][A-Za-z0-9_, /、と]*)", text, re.I)
    for body in grouped:
        declared.extend(re.findall(IDENTIFIER, body))
    return tuple(dict.fromkeys(name for name in (*quoted, *declared)
                              if name.casefold() not in _IGNORE_NAMES))


def nearest_field(text: str, position: int, fields: tuple[str, ...]) -> str:
    occurrences = [(abs(match.start() - position) + (8 if match.start() > position else 0), key)
                   for key in fields for match in re.finditer(
                       r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])", text)
                   if abs(match.start() - position) <= 60]
    if not occurrences:
        return fields[0] if len(fields) == 1 else ""
    best = min(distance for distance, key in occurrences)
    winners = {key for distance, key in occurrences if distance == best}
    return next(iter(winners)) if len(winners) == 1 else ""


def read_spec(text: str) -> Specification:
    language = next((name for name, pattern in (
        ("python", r"(?<![A-Za-z])python(?![A-Za-z])"),
        ("javascript", r"(?<![A-Za-z])(?:javascript|js)(?![A-Za-z])|node(?:\.js)?"),
        ("sql", r"(?<![A-Za-z])sql(?![A-Za-z])|sqlite"),
        ("shell", r"(?<![A-Za-z])(?:posix|shell|sh|bash)(?![A-Za-z])|シェル"))
        if re.search(pattern, text, re.I)), "")
    fields = _names(text)
    named = re.search(r"(?:関数名|function name)\s*(?:は|を|:|：|is)?\s*[`「'\"]?(" + IDENTIFIER + r")", text, re.I)
    name = named.group(1) if named else "process_" + (fields[0].lower() if fields else "values")
    if fields and not re.fullmatch(IDENTIFIER, name):
        name = "process_records"
    shape = "records" if re.search(r"レコード|辞書.{0,8}(?:リスト|配列)|オブジェクト|records|objects|table|テーブル", text, re.I) else (
        "dict" if re.search(r"辞書|dict|dictionary", text, re.I) else "list")
    if language == "sql":
        shape = "records"
    table_match = re.search(r"(?:テーブル|table)\s*[`「'\"]?(" + IDENTIFIER + r")|(" + IDENTIFIER + r")\s*(?:テーブル|table)", text, re.I)
    table = next((value for value in table_match.groups() if value), "") if table_match else "input_records"
    excluded_names = {table, named.group(1) if named else ""}
    excluded_names.update(match.group(1) for match in re.finditer(r"[\"'](" + IDENTIFIER + r")[\"']\s*(?:を)?(?:除外|除く|以外)", text))
    fields = tuple(key for key in fields if key not in excluded_names)
    other = re.search(r"(?:join|結合|存在しない|not exists).*?[`「'\"](" + IDENTIFIER + r")[`」'\"]", text, re.I)
    tables = [next(value for value in match.groups() if value) for match in re.finditer(
        r"(?:テーブル|table)\s*[`「'\"]?(" + IDENTIFIER + r")|(" + IDENTIFIER + r")\s*(?:テーブル|table)", text, re.I)]
    other_table = tables[1] if len(tables) > 1 else other.group(1) if other else "other_records"
    fields = tuple(key for key in fields if key != other_table)
    spec = Specification(language, shape, name, fields, [], table=table,
                         other_table=other_table)
    if not language:
        spec.issues.append("language")
    if not re.search(r"リスト|配列|辞書|レコード|テーブル|数列|list|array|dict|records?|objects?|table", text, re.I):
        spec.issues.append("input shape")
    spec.unchanged = bool(re.search(r"変更しない|変更せず|変えない|元.{0,8}まま|unchanged|without mutat|do not mutat", text, re.I))
    spec.all_ties = bool(re.search(r"同点.{0,12}(?:全|すべて)|同率.{0,12}(?:全|すべて)|ties? .{0,12}(?:all|every)|all ties", text, re.I))
    spec.stable = bool(re.search(r"安定|stable|元の順序|同じ.{0,10}順序", text, re.I))
    zero_division = re.search(r"(?:分母|denominator).{0,15}(?:0|zero).{0,15}?(None|null|0)", text, re.I)
    if zero_division:
        spec.zero_division = literal(zero_division.group(1))
    empty = re.search(r"(?:空|empty).{0,25}?(None|null|0|\[\]|\{\})", text, re.I)
    if empty:
        spec.empty_stated = True
        spec.empty = literal(empty.group(1)) if empty.group(1) not in ("[]", "{}") else ast.literal_eval(empty.group(1))
    operations: list[tuple[int, Operation]] = []
    comparisons = list(re.finditer(r"(?:[`「'\"]?(" + IDENTIFIER + r")[`」'\"]?\s*)?"
                                  r"(>=|<=|==|!=|>|<)\s*(" + _LITERAL + r")", text))
    for match in comparisons:
        key, comparator, value = match.groups()
        if shape == "records" and key and key.casefold() not in _IGNORE_NAMES:
            if shape == "records" and key not in spec.fields:
                spec.fields += (key,)
        else:
            key = ""
        operations.append((match.start(), Operation("filter", key, comparator, literal(value))))
    japanese = re.finditer(r"(?:[`「'\"]?(" + IDENTIFIER + r")[`」'\"]?\s*(?:が|は|を)?)?\s*"
                          r"(-?\d+(?:\.\d+)?)\s*(以上|以下|より大き|より小さ|未満|を超え)", text)
    for match in japanese:
        key, value, comparator = match.groups()
        if shape == "records" and key and key.casefold() not in _IGNORE_NAMES:
            if shape == "records" and key not in spec.fields:
                spec.fields += (key,)
        else:
            key = ""
        operations.append((match.start(), Operation("filter", key,
            {"以上": ">=", "以下": "<=", "より大き": ">", "より小さ": "<", "未満": "<", "を超え": ">"}[comparator], literal(value))))
    for match in re.finditer(r"(?:[`\"']?(" + IDENTIFIER + r")[`\"']?\s+)?"
                            r"(at least|at most|greater than|less than|equal to|not equal to)\s+(" + _LITERAL + r")", text, re.I):
        key, comparator, raw = match.groups()
        key = key if shape == "records" and key in spec.fields else ""
        operations.append((match.start(), Operation("filter", key,
            {"at least": ">=", "at most": "<=", "greater than": ">", "less than": "<", "equal to": "==",
             "not equal to": "!="}[comparator.lower()], literal(raw))))
    for word, comparator, value in ((r"偶数|even", "even", None), (r"奇数|odd", "odd", None),
                                     (r"正の(?:数|整数)|positive", ">", 0), (r"負の(?:数|整数)|negative", "<", 0)):
        match = re.search(word, text, re.I)
        if match:
            operations.append((match.start(), Operation("filter", "", comparator, value)))
    excluded = re.finditer(r"(" + _LITERAL + r")(?:\s*(?:を|は))?\s*(?:除外|除く|取り除|以外)|"
                          r"(?:exclude|excluding|remove)\s+(" + _LITERAL + r")", text, re.I)
    for match in excluded:
        raw = next(value for value in match.groups() if value is not None)
        key = nearest_field(text, match.start(), spec.fields) if shape == "records" else ""
        operations.append((match.start(), Operation("filter", key, "!=", literal(raw))))
    not_null = re.search(r"(?:None|null|欠損値).{0,12}(?:除外|除く|取り除)|(?:not null|non.null)", text, re.I)
    if not_null and not any(operation.kind == "filter" and operation.value is None for _, operation in operations):
        key = nearest_field(text, not_null.start(), spec.fields) if shape == "records" else ""
        operations.append((not_null.start(), Operation("filter", key, "!=", None)))
    transforms = ((r"二乗|2乗|square", "square"), (r"絶対値|absolute", "abs"),
                  (r"大文字|uppercase", "upper"), (r"小文字|lowercase", "lower"),
                  (r"前後.{0,8}空白|strip|trim", "strip"), (r"文字数|length of each", "length"))
    for pattern, transform in transforms:
        match = re.search(pattern, text, re.I)
        if match:
            key = nearest_field(text, match.start(), spec.fields) if shape == "records" else ""
            operations.append((match.start(), Operation("map", key, comparator=transform)))
    scale = re.search(r"(-?\d+(?:\.\d+)?)\s*倍|multiply (?:each|every|by).*?(-?\d+(?:\.\d+)?)", text, re.I)
    if scale:
        key = nearest_field(text, scale.start(), spec.fields) if shape == "records" else ""
        operations.append((scale.start(), Operation("map", key, comparator="multiply",
                          value=literal(next(value for value in scale.groups() if value)))))
    pluck = re.search(r"[`「'\"]?(" + IDENTIFIER + r")[`」'\"]?\s*(?:の値|キー|フィールド)?(?:だけ|のみ)を?(?:取り出|抽出)|"
                      r"(?:pluck|map to)\s+[`'\"]?(" + IDENTIFIER + r")", text, re.I)
    if pluck and shape == "records":
        key = next(value for value in pluck.groups() if value)
        operations.append((pluck.start(), Operation("map", key, "pluck")))
        spec.fields = tuple(dict.fromkeys((*spec.fields, key)))
    aggregates = ((r"合計|総和|\bsum\b", "sum"), (r"平均|\bmean\b|\baverage\b", "mean"),
                  (r"件数|個数|要素数|\bcount\b", "count"),
                  (r"最小|\bmin(?:imum)?\b", "min"), (r"最大|\bmax(?:imum)?\b", "max"))
    for pattern, aggregate in aggregates:
        match = re.search(pattern, text, re.I)
        if match:
            key = nearest_field(text, match.start(), spec.fields) if shape == "records" else ""
            operations.append((match.start(), Operation("aggregate", key, aggregate)))
    group = re.search(r"[`「'\"]?(" + IDENTIFIER + r")[`」'\"]?\s*(?:ごと|別|でグループ|で集約)|"
                      r"group(?:ed)? by\s+[`'\"]?(" + IDENTIFIER + r")", text, re.I)
    if group:
        key = next(value for value in group.groups() if value)
        spec.fields = tuple(dict.fromkeys((*spec.fields, key)))
        operations.append((group.start(), Operation("group", key)))
    sort = re.search(r"並べ替|ソート|昇順|降順|\bsort|order by", text, re.I)
    if sort:
        nearby = text[max(0, sort.start() - 40):sort.end() + 40]
        sort_key = re.search(r"(?:sort|order) (?:by )?[`'\"]?(" + IDENTIFIER + r")", nearby, re.I)
        key = sort_key.group(1) if sort_key and sort_key.group(1) in spec.fields else nearest_field(text, sort.start(), spec.fields)
        operations.append((sort.start(), Operation("sort", key, descending=bool(re.search(r"降順|desc|reverse", nearby, re.I)))))
    diff = re.search(r"隣接.{0,12}差|前の.{0,12}差|連続.{0,12}差|pairwise diff|successive diff", text, re.I)
    if diff:
        operations.append((diff.start(), Operation("diff")))
    dedupe = re.search(r"重複.{0,8}(?:除去|削除|除く|取り除|なく)|一意|dedup|unique", text, re.I)
    if dedupe:
        key = nearest_field(text, dedupe.start(), spec.fields) if shape == "records" else ""
        operations.append((dedupe.start(), Operation("dedupe", key)))
    join = re.search(r"結合|(?<![A-Za-z])join(?![A-Za-z])|not.exists|存在しない|含まれない", text, re.I)
    if join:
        key = nearest_field(text, join.start(), spec.fields)
        if not key:
            spec.issues.append("join key")
        operations.append((join.start(), Operation("not_exists" if re.search(r"not.exists|存在しない|含まれない", text, re.I)
                                                else "join", key)))
    ratio = re.search(r"比率|割合|ratio|割[るり]|divide", text, re.I)
    if ratio:
        if len(spec.fields) < 2:
            spec.issues.append("ratio operands")
        else:
            operations.append((ratio.start(), Operation("ratio", spec.fields[0], value=spec.fields[1])))
    operations.sort(key=lambda pair: pair[0])
    spec.operations = list(dict.fromkeys(operation for _, operation in operations))
    if group:
        grouped = [operation for operation in spec.operations if operation.kind == "group"]
        aggregates_only = [operation for operation in spec.operations if operation.kind == "aggregate"]
        spec.operations = [operation for operation in spec.operations if operation.kind not in ("group", "aggregate")] + grouped + aggregates_only
    if not spec.operations:
        spec.issues.append("operation")
    if re.search(r"絞り|filter|除外|exclude|条件|だけ|のみ", text, re.I) and not any(
            operation.kind in ("filter", "not_exists", "dedupe") or operation.kind == "map" and operation.comparator == "pluck"
            for operation in spec.operations):
        spec.issues.append("filter predicate")
    if re.search(r"変換|transform|\bmap\b", text, re.I) and not any(operation.kind in ("map", "ratio") for operation in spec.operations):
        spec.issues.append("transform")
    if shape == "records":
        for operation in spec.operations:
            if operation.kind in ("filter", "sort", "map") and not operation.field:
                spec.issues.append(operation.kind + " field")
            if operation.kind == "aggregate" and operation.comparator != "count" and not operation.field:
                spec.issues.append("aggregate field")
    if len([operation for operation in spec.operations if operation.kind == "aggregate"]) > 1:
        spec.issues.append("multiple aggregates")
    aggregate_positions = [index for index, operation in enumerate(spec.operations) if operation.kind == "aggregate"]
    if aggregate_positions and aggregate_positions[0] != len(spec.operations) - 1:
        spec.issues.append("operation after aggregate")
    if re.search(r"再帰|recursive|HTTP|ネットワーク|ファイル.{0,12}(?:削除|書き込)|機械学習|encrypt|暗号|"
                 r"正規表現|regex|圧縮|gzip|ハッシュ|hash|JSON|CSV|日付|datetime|置換|replace|split", text, re.I):
        spec.issues.append("operation outside the closed parts")
    return spec

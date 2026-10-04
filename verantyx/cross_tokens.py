"""Deterministic, lossless tokens for the existing event-cross structures.

The token grammar carries the complete ``EventCross`` or ``CrossReading``
``to_dict()`` value. It does not infer, repair, rank, or discard cross fields.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from . import event_cross as EC


SCHEMA = "verantyx.cross_tokens/1"
_OPEN = {"cross": "<cross>", "reading": "<reading>"}
_CLOSE = {"cross": "</cross>", "reading": "</reading>"}


class CrossTokenError(ValueError):
    """A typed refusal to interpret a malformed or noncanonical token line."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(reason + (":" + detail if detail else ""))


def _json_lexemes(source: str) -> list[str]:
    """Split compact JSON into structural tokens and atomic JSON values."""
    output: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
        elif char in "{}[]:,":
            output.append(char)
            index += 1
        elif char == '"':
            start = index
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                elif source[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            if index > len(source) or source[index - 1] != '"':
                raise CrossTokenError("INVALID_JSON", "unterminated string")
            output.append(source[start:index])
        else:
            start = index
            while index < len(source) and not source[index].isspace() and source[index] not in "{}[]:,":
                index += 1
            output.append(source[start:index])
    return output


def _plain(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, EC.EventCross):
        return "cross", value.to_dict()
    if isinstance(value, EC.CrossReading):
        return "reading", value.to_dict()
    raise CrossTokenError("UNSUPPORTED_VALUE", type(value).__name__)


def cross_to_tokens(value: EC.EventCross | EC.CrossReading) -> str:
    """Encode an existing cross or cross reading as one deterministic line."""
    kind, data = _plain(value)
    try:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CrossTokenError("UNSERIALIZABLE_CROSS", type(exc).__name__) from exc
    return _OPEN[kind] + " " + " ".join(_json_lexemes(payload)) + " " + _CLOSE[kind]


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CrossTokenError("DUPLICATE_KEY", key)
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise CrossTokenError("INVALID_JSON", "nonfinite number " + value)


def _fail(reason: str, detail: str) -> None:
    raise CrossTokenError(reason, detail)


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("BAD_CROSS", where + " is not an object")
    return value


def _keys(value: Mapping[str, Any], required: set[str], optional: set[str], where: str) -> None:
    keys = set(value)
    missing, extra = required - keys, keys - required - optional
    if missing or extra:
        _fail("BAD_CROSS", where + " keys missing=" + repr(sorted(missing)) + " extra=" + repr(sorted(extra)))


def _string(value: Any, where: str, *, blank: bool = True) -> str:
    if not isinstance(value, str) or (not blank and not value.strip()):
        _fail("BAD_CROSS", where + " is not a valid string")
    return value


def _string_tuple(value: Any, where: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail("BAD_CROSS", where + " is not a string list or null")
    return tuple(value)


def _type_agreement(value: Any) -> EC.TypeAgreement:
    data = _mapping(value, "agreement")
    _keys(data, {"verdict", "reason", "expected", "observed"}, set(), "agreement")
    verdict = _string(data["verdict"], "agreement.verdict")
    if verdict not in EC.VERDICTS + EC.EXTRA_VERDICTS:
        _fail("BAD_CROSS", "unknown agreement verdict")
    reason = data["reason"]
    if reason is not None and not isinstance(reason, str):
        _fail("BAD_CROSS", "agreement.reason is not a string or null")
    return EC.TypeAgreement(
        verdict, reason,
        _string_tuple(data["expected"], "agreement.expected"),
        _string_tuple(data["observed"], "agreement.observed"),
    )


def _place(value: Any) -> EC.PlaceResult:
    data = _mapping(value, "place")
    _keys(data, {"state", "origin", "estimate_basis", "types", "source", "provenance"}, set(), "place")
    types = data["types"]
    if not isinstance(types, list) or any(not isinstance(item, str) for item in types):
        _fail("BAD_CROSS", "place.types is not a string list")
    provenance = _mapping(data["provenance"], "place.provenance")
    try:
        result = EC.PlaceResult(data["state"], data["origin"], data["estimate_basis"], tuple(types), provenance)
    except (TypeError, ValueError) as exc:
        raise CrossTokenError("BAD_CROSS", "invalid placement") from exc
    if result.invariant_problems() or data["source"] != result.source:
        _fail("BAD_CROSS", "placement invariant or source mismatch")
    return result


def _filler(value: Any) -> EC.Filler:
    data = _mapping(value, "filler")
    _keys(data, {"surface", "head", "head_basis", "place", "flags"}, {"embedded"}, "filler")
    surface = _string(data["surface"], "filler.surface", blank=False)
    head = _string(data["head"], "filler.head", blank=False)
    head_basis = _string(data["head_basis"], "filler.head_basis", blank=False)
    flags = _mapping(data["flags"], "filler.flags")
    embedded = _event_cross(data["embedded"]) if "embedded" in data else None
    return EC.Filler(surface, head, head_basis, _place(data["place"]), flags, embedded)


def _arm(value: Any) -> EC.Arm:
    data = _mapping(value, "arm")
    _keys(data, {"kind", "fillers", "agreement"}, set(), "arm")
    kind = _string(data["kind"], "arm.kind")
    fillers_data = data["fillers"]
    if not isinstance(fillers_data, list):
        _fail("BAD_CROSS", "arm.fillers is not a list")
    fillers = tuple(_filler(item) for item in fillers_data)
    if (kind == "FILLER" and len(fillers) != 1) or (kind == "ARM_TIE" and len(fillers) < 2) or kind not in ("FILLER", "ARM_TIE"):
        _fail("BAD_CROSS", "arm kind and filler count disagree")
    return EC.Arm(kind, fillers, _type_agreement(data["agreement"]))


def _event_cross(value: Any) -> EC.EventCross:
    data = _mapping(value, "cross")
    _keys(data, {"index", "center", "arms", "provenance"}, set(), "cross")
    index = data["index"]
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        _fail("BAD_CROSS", "cross.index is not a nonnegative integer")
    center = _mapping(data["center"], "cross.center")
    if not set(center) <= set(EC.CENTER_KEYS) or not set(EC.CLAUSE_REQUIRED_KEYS) - {"roles"} <= set(center):
        _fail("BAD_CROSS", "cross.center keys do not match the event-cross schema")
    arms_data = _mapping(data["arms"], "cross.arms")
    if any(role not in EC.ROLE_NAMES for role in arms_data):
        _fail("BAD_CROSS", "cross.arms contains an unknown role")
    roles = tuple(arms_data)
    if roles != tuple(role for role in EC.ROLE_NAMES if role in arms_data):
        _fail("BAD_CROSS", "cross.arms are not in registered role order")
    arms = {role: _arm(arms_data[role]) for role in roles}
    provenance = _mapping(data["provenance"], "cross.provenance")
    return EC.EventCross(index, center, arms, provenance)


def _event_reading(value: Any) -> EC.CrossReading:
    data = _mapping(value, "reading")
    _keys(data, {"schema", "status", "crosses", "relations", "abstain", "lookup", "counts"}, set(), "reading")
    if data["schema"] != EC.SCHEMA:
        _fail("BAD_CROSS", "unknown cross-reading schema")
    status = data["status"]
    if status not in ("CROSSED", "ABSTAINED", "INPUT_REJECTED"):
        _fail("BAD_CROSS", "unknown cross-reading status")
    crosses_data, relations_data = data["crosses"], data["relations"]
    if not isinstance(crosses_data, list) or not isinstance(relations_data, list):
        _fail("BAD_CROSS", "crosses and relations must be lists")
    crosses = tuple(_event_cross(item) for item in crosses_data)
    relations: list[Mapping[str, Any]] = []
    for relation in relations_data:
        item = _mapping(relation, "relation")
        if not {"type", "from", "to"} <= set(item):
            _fail("BAD_CROSS", "relation lacks type/from/to")
        if item["type"] not in EC.RELATION_TYPES:
            _fail("BAD_CROSS", "unknown relation type")
        for name in ("from", "to"):
            position = item[name]
            if not isinstance(position, int) or isinstance(position, bool) or not 0 <= position < len(crosses):
                _fail("BAD_CROSS", "relation index is out of range")
        relations.append(item)
    abstain = data["abstain"]
    if abstain is not None:
        abstain = _mapping(abstain, "reading.abstain")
    lookup = _mapping(data["lookup"], "reading.lookup")
    _keys(lookup, {"id"}, set(), "reading.lookup")
    lookup_id = _string(lookup["id"], "reading.lookup.id", blank=False)
    if (status == "CROSSED") != bool(crosses) or (status == "CROSSED") == (abstain is not None):
        _fail("BAD_CROSS", "cross-reading status disagrees with crosses or abstention")
    result = EC.CrossReading(status, crosses, tuple(relations), abstain, lookup_id)
    if result.to_dict() != data:
        _fail("BAD_CROSS", "cross-reading counts or canonical fields disagree")
    return result


def _decode_payload(tokens: str) -> tuple[str, Any]:
    if not isinstance(tokens, str):
        _fail("INVALID_INPUT", "token sequence is not a string")
    kind = next((name for name, marker in _OPEN.items() if tokens.startswith(marker + " ")), None)
    if kind is None:
        _fail("BAD_BOUNDARY", "missing opening marker")
    opening, closing = _OPEN[kind], _CLOSE[kind]
    in_string = False
    escaped = False
    close_at = None
    index = len(opening) + 1
    while index < len(tokens):
        char = tokens[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif tokens.startswith(closing, index):
            close_at = index
            break
        index += 1
    if close_at is None or tokens[close_at + len(closing):] != "":
        _fail("BAD_BOUNDARY", "missing closing marker or trailing content")
    if close_at == 0 or tokens[close_at - 1] != " ":
        _fail("NON_CANONICAL", "closing marker is not a token")
    raw = tokens[len(opening) + 1:close_at]
    lexemes = _json_lexemes(raw)
    if not lexemes:
        _fail("INVALID_JSON", "empty payload")
    compact = "".join(lexemes)
    try:
        value = json.loads(compact, object_pairs_hook=_duplicate_safe_object, parse_constant=_reject_constant)
    except CrossTokenError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CrossTokenError("INVALID_JSON", type(exc).__name__) from exc
    return kind, value


def tokens_to_cross(tokens: str) -> EC.EventCross | EC.CrossReading:
    """Decode a canonical token line, refusing ambiguous or lossy inputs."""
    kind, data = _decode_payload(tokens)
    try:
        value = _event_cross(data) if kind == "cross" else _event_reading(data)
    except CrossTokenError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise CrossTokenError("BAD_CROSS", type(exc).__name__) from exc
    if cross_to_tokens(value) != tokens:
        _fail("NON_CANONICAL", "re-encoding differs")
    return value


def _contains_embedded(cross: EC.EventCross) -> bool:
    for arm in cross.arms.values():
        for filler in arm.fillers:
            if filler.embedded is not None:
                return True
    return False


def realize_tokens(tokens: str, lang: str = "ja", *, placement: str | None = None) -> dict[str, Any]:
    """Realize one supported cross and require an independent cross-key reread.

    Collections and embedded/related crosses remain fully serializable, but the
    current sentence realizer cannot express their topology, so this API abstains.
    """
    try:
        value = tokens_to_cross(tokens)
    except CrossTokenError as exc:
        return {"schema": SCHEMA, "status": "TOKEN_REJECTED", "reason": exc.reason, "detail": exc.detail}
    if isinstance(value, EC.CrossReading):
        if value.status != "CROSSED":
            return {"schema": SCHEMA, "status": "ABSTAINED", "reason": "SOURCE_NOT_CROSSED", "source_status": value.status}
        if len(value.crosses) != 1 or value.relations:
            return {"schema": SCHEMA, "status": "REFUSED", "reason": "MULTIPLE_CROSSES_UNSUPPORTED"}
        cross = value.crosses[0]
    else:
        cross = value
    if _contains_embedded(cross):
        return {"schema": SCHEMA, "status": "REFUSED", "reason": "EMBEDDED_CROSS_UNSUPPORTED"}
    from . import observe, semantic_read, semantic_realize

    key = observe.cell_key_of(cross)
    result = semantic_realize.realize_observed(
        dict(cross.center),
        {role: arm.to_dict() for role, arm in cross.arms.items()},
        lang,
        cell_id=key,
        rule=cross.provenance.get("rule"),
    )
    if isinstance(result, semantic_realize.Refused):
        return {"schema": SCHEMA, "status": "REFUSED", "reason": result.reason,
                "detail": result.detail, "checks": result.checks or {}, "cell_key": key}
    try:
        reread = semantic_read.read(result.text, lang, placement=placement)
        lookup = EC.default_lookup(placement) if placement is not None else None
        crossed = EC.build_crosses(reread, lookup)
    except Exception as exc:
        return {"schema": SCHEMA, "status": "ABSTAINED", "reason": "REREAD_ERROR",
                "detail": type(exc).__name__, "cell_key": key}
    if crossed.status != "CROSSED" or len(crossed.crosses) != 1:
        return {"schema": SCHEMA, "status": "ABSTAINED", "reason": "REREAD_NOT_CROSSED",
                "source_status": crossed.status, "cell_key": key}
    reread_key = observe.cell_key_of(crossed.crosses[0])
    if reread_key != key:
        return {"schema": SCHEMA, "status": "REFUSED", "reason": "ROUNDTRIP_MISMATCH",
                "text": result.text, "expected_cell_key": key, "actual_cell_key": reread_key}
    return {"schema": SCHEMA, "status": "REALIZED", "text": result.text,
            "cell_key": key, "checks": result.checks}


__all__ = ["SCHEMA", "CrossTokenError", "cross_to_tokens", "tokens_to_cross", "realize_tokens"]

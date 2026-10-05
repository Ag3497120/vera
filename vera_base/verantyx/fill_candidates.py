"""W10-f04 (O1・O4・O5): 穴への候補の問い・座標の受け渡し・再読の門 (docs/FUSION.md §6, K281〜K283, K285, K286, §6.6 裁定 A・B)。

LLM は語彙が足りないときに **候補** を出す提案者で、読む・決める・答える・棄権するは Vera の規則。ここは
  1 開いた申告（型・役割・近い語を JSON schema で縛った 1 回の問い）→ 2 門 (a1)(a2)(a3)(a4)(b')(b)(c)(d)（順序はこのとおり）→ 3 閉じた一覧の問い（`llm_choice.LLMChooser`、2 回・順序と文面を変える）
の順に進み、通った候補だけを `origin: testimony`・`basis: LLM_TESTIMONY_FILL:<model>:<decision_id>` で返す。候補は **記録ではない**（文書の十字には入れない。台帳に行くだけ）。
門 (a4)（裁定 A）: 穴の語の配置が型を与えない（UNPLACED／UNKNOWN）なら `GATE_A_HOLE_WORD_UNPLACED`、配置の型がこの文で 1 つの役割に落ちない（ある型で読めない／役割が違う）なら
`GATE_A_ROLE_SPLIT`: 候補補完が選ぶのは語だけで、構造（助詞の役割）は Vera が決めている状態のときだけ採用する。門 (b')（裁定 B）: 元の文を、採用する型を注入して読み直し、穴の腕が埋まり他の腕が元のまま
同じ十字になるときだけ採用（`GATE_B_REREAD_MISMATCH`）。
同点は棄権（2 つ以上残れば `GATE_D_TIE`）。後段の失敗は `BACKEND_FAILED:<型>` で、「候補なし」とも門の不採用とも別の型。
`llm_choice`・`semantic_reader`・`basis_policy` は呼ぶだけで変えない。
"""
from __future__ import annotations

import copy
import dataclasses
import itertools
import json
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import cross_tokens as CT
from . import event_cross as EC
from . import llm_choice as LC
from . import semantic_read as S
from . import semantic_reader as R
from .coarse_types import NOUN_TYPES

CROSS_TOKENS_VERSION = CT.SCHEMA          # J2: the copied file is not changed; its version is its schema string
STATUSES = ("ADOPTED", "NOT_ADOPTED", "BACKEND_FAILED", "NO_HOLE", "REFUSED")
DEFAULT_K = 5
CLOSED_SCHEMA = {"type": "object", "properties": {"choice": {"type": ["integer", "null"]}}, "required": ["choice"], "additionalProperties": False}
MASK_UNKNOWN = "〈未定〉"


def _nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(_nfkc(text).encode("utf-8")).hexdigest()


@dataclass
class FillDecision:
    status: str
    reason: str
    word: Optional[str] = None                 # the word of the hole (what Vera does not know)
    candidate: Optional[str] = None            # only when ADOPTED
    declaration: Optional[Dict[str, Any]] = None
    hole: Optional[Dict[str, Any]] = None
    gate_log: List[Dict[str, Any]] = field(default_factory=list)
    fill_id: str = ""
    choice_decision_id: Optional[str] = None
    basis: Optional[str] = None
    origin: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    mask_user_text: bool = True
    records_checked: int = 0                  # records REALLY compared in gate (c) (0: none, or not comparable: see gate_log[].c_note)
    sovereign_checked: bool = False           # J13 (W10-f05): True only when gate (c) REALLY compared at least one of the sovereign's utterances (VERA_SOVEREIGN_* set and consented); else False
    timing: Dict[str, float] = field(default_factory=dict)
    cross_tokens_version: str = CROSS_TOKENS_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------------------------------------------------------------
# O5: the coordinates handed to the LLM
# ---------------------------------------------------------------------------------------------------------------------------------
class _QueryLookup:
    """A `PlacementLookup` over a `query(term)` object (the real placement or a probe)."""
    id = "fill-query-lookup/1"

    def __init__(self, query: Any) -> None:
        self.query = query

    def lookup(self, lemma: str) -> EC.PlaceResult:
        return EC.PlaceResult.from_coarse_query(self.query.query(lemma))


def _probe_readings(text: str, holes: Sequence[Dict[str, Any]], query: Any, shared: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The reader's outputs of EVERY typing of the holes (the product of their `expected_types`) that it reads. No typing is first: the content of the cross is taken from all of them (see `coordinates`)."""
    outs = []
    for combo in itertools.product(*[sorted(h["expected_types"]) for h in holes]):
        out = S.read(text, "ja", placement=S._HoleProbe(query, {h["head"]: c for h, c in zip(holes, combo)}, shared))
        if S._hole_probe_ok(out):
            outs.append(out)
    return outs


def _scrub_probe(cross: EC.EventCross, hole_heads: Sequence[str]) -> EC.EventCross:
    """M2 (review r1): the arm of a hole was typed by the PROBE (`provenance.role_basis[<role>] = placement_direct:<the type tried>`): that is not what Vera knows about the word, and the type that happens to
    be tried first would be a hint to the LLM. It is written `hole`."""
    prov = dict(cross.provenance)
    rb = prov.get("role_basis")
    if isinstance(rb, dict):
        rb = dict(rb)
        for role, arm in cross.arms.items():
            if any(f.surface in hole_heads for f in arm.fillers) and role in rb:
                rb[role] = "hole"
        prov["role_basis"] = rb
    return dataclasses.replace(cross, provenance=prov)


def _scrub_place(place: EC.PlaceResult, term_mark: Optional[str]) -> EC.PlaceResult:
    """The provenance of a placement answer keeps the looked-up TERM (the user's word) and the placement's local path: neither is sent. `term_mark` replaces the term (None keeps it: the hole's word)."""
    prov = dict(place.provenance) if isinstance(place.provenance, dict) else {}
    if term_mark is not None and "term" in prov:
        prov["term"] = term_mark
    pl = prov.get("placement")
    if isinstance(pl, dict):
        prov["placement"] = {k: v for k, v in pl.items() if k != "path"}
    return dataclasses.replace(place, provenance=prov)


def _masked_cross(cross: EC.EventCross, hole_heads: Sequence[str]) -> EC.EventCross:
    """K286: the surface of every filler that is not a hole is replaced by its type 〈TYPE〉 (or 〈未定〉) -- in the surface, the head and the looked-up term of its placement answer: the user's words do not leave."""
    arms = {}
    for role, arm in cross.arms.items():
        fillers = []
        for f in arm.fillers:
            if f.surface in hole_heads:
                fillers.append(dataclasses.replace(f, place=_scrub_place(f.place, None)))
                continue
            t = f.place.types[0] if (f.place.state == "DECIDED" and len(f.place.types) == 1) else None
            mark = "〈%s〉" % t if t else MASK_UNKNOWN
            fillers.append(dataclasses.replace(f, surface=mark, head=mark, place=_scrub_place(f.place, mark)))
        arms[role] = dataclasses.replace(arm, fillers=tuple(fillers))
    return dataclasses.replace(cross, arms=arms)


def coordinates(hole_result: Dict[str, Any], text: str, query: Any, *, mask_user_text: bool = True, shared: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """O5: {'cross_tokens_version', 'tokens'}: the cross of the sentence (centre, arms) as one line of cross tokens with the REAL placement answers of every filler (the hole's word is UNPLACED /
    MULTIPLE / UNKNOWN). The type a probe tried for a hole never reaches the tokens (M2): the cross is built for EVERY typing the reader accepts, the hole's arm is written `hole`, and the line is sent
    only when all of them give the same line; if they differ (the typing changes the cross) the answer is `tokens: None, reason: COORDINATES_DEPEND_ON_PROBE_TYPE` (typed; no first typing is chosen).
    With `mask_user_text` the fillers that are not holes are written 〈TYPE〉."""
    holes = hole_result["holes"]
    heads = [h["head"] for h in holes]
    outs = _probe_readings(text, holes, query, shared if shared is not None else {})
    if not outs:
        return {"cross_tokens_version": CROSS_TOKENS_VERSION, "tokens": None, "reason": "NO_PROBE_READING"}
    lines = []
    for out in outs:
        reading = EC.build_crosses(out, _QueryLookup(query))
        if reading.status != "CROSSED" or len(reading.crosses) != 1:
            return {"cross_tokens_version": CROSS_TOKENS_VERSION, "tokens": None, "reason": "NOT_CROSSED"}
        cross = _scrub_probe(reading.crosses[0], heads)
        if mask_user_text:
            cross = _masked_cross(cross, heads)
        lines.append(CT.cross_to_tokens(cross))
    if len(set(lines)) != 1:
        return {"cross_tokens_version": CROSS_TOKENS_VERSION, "tokens": None, "reason": "COORDINATES_DEPEND_ON_PROBE_TYPE"}
    return {"cross_tokens_version": CROSS_TOKENS_VERSION, "tokens": lines[0]}


# ---------------------------------------------------------------------------------------------------------------------------------
# O1: the open declaration
# ---------------------------------------------------------------------------------------------------------------------------------
def open_schema(role_candidates: Sequence[str], k: int = DEFAULT_K) -> Dict[str, Any]:
    return {"type": "object",
            "properties": {"type": {"type": "string", "enum": sorted(NOUN_TYPES)},
                           "role": {"enum": sorted(role_candidates) + [None]},
                           "near_words": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": k}},
            "required": ["type", "role", "near_words"], "additionalProperties": False}


def open_messages(hole: Dict[str, Any], coords: Dict[str, Any], predicate: Optional[str], text: Optional[str], k: int) -> List[Dict[str, str]]:
    """The fixed sentence form Vera writes. With the mask on (`text` is None) it holds: the hole's word and particle, the predicate, the types and roles the hole may hold, the coordinates."""
    system = ("あなたは Vera の語彙の提案者です。Vera が読めなかった文の「穴」に入る語の候補を出します。"
              "答えは JSON 1 つだけで、説明は書きません。候補を採用するかどうかは Vera が決めます。")
    lines = ["Vera の座標（cross_tokens_version=%s）:" % coords["cross_tokens_version"], coords.get("tokens") or "（座標なし）",
             "穴: 助詞「%s」の位置にある、Vera が知らない語「%s」。" % (hole["particle"], hole["head"]),
             "述語: %s" % (predicate or "（不明）")]
    if text is not None:
        lines.append("文: %s" % json.dumps(text, ensure_ascii=False))
    # M1 (review r1): the type is a declaration about the WORD, never a choice among the types the position allows (the position's types are written only as the condition of near_words).
    lines.append("お願い 1（type）: 語「%s」そのものの型を、スキーマの型の一覧から 1 つ選んでください。この位置に入る型に合わせず、語の意味だけで決めてください。" % hole["head"])
    lines.append("お願い 2（role）: この位置の役割を %s から 1 つ、分からなければ null。" % json.dumps(sorted(hole["role_candidates"]), ensure_ascii=False))
    lines.append("お願い 3（near_words）: Vera の配置にある語のうち、「%s」に意味が最も近い語を、最大 %d 個（順位ではなく集合として）入れてください（「%s」自身は含めない）。"
                 "条件: その語の型が %s のどれかであること。" % (hole["head"], k, hole["head"], json.dumps(sorted(hole["expected_types"]), ensure_ascii=False)))
    lines.append('出力: {"type": 型, "role": 役割またはnull, "near_words": [語, ...]} の JSON 1 つだけ。')
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(lines)}]


def parse_open(content: str, hole: Dict[str, Any], k: int) -> tuple:
    """(declaration, None) or (None, why): the schema is checked here again (a grammar is not trusted)."""
    try:
        data = json.loads(content, object_pairs_hook=_unique)
    except (TypeError, ValueError):
        return None, "NOT_JSON"
    if not isinstance(data, dict) or set(data) != {"type", "role", "near_words"}:
        return None, "KEYS"
    t, role, words = data["type"], data["role"], data["near_words"]
    if not isinstance(t, str) or t not in NOUN_TYPES:
        return None, "TYPE_NOT_IN_ENUM"
    if role is not None and (not isinstance(role, str) or role not in hole["role_candidates"]):
        return None, "ROLE_NOT_IN_ENUM"
    if not isinstance(words, list) or len(words) > k or not all(isinstance(w, str) and _nfkc(w) for w in words):
        return None, "NEAR_WORDS"
    return {"type": t, "role": role, "near_words": list(words)}, None


def _unique(pairs):
    d = {}
    for key, value in pairs:
        if key in d:
            raise ValueError("duplicate key")
        d[key] = value
    return d


# ---------------------------------------------------------------------------------------------------------------------------------
# O4: the gates
# ---------------------------------------------------------------------------------------------------------------------------------
def _gate_a(word: str, decl: Dict[str, Any], hole: Dict[str, Any], query: Any) -> Optional[tuple]:
    """(a1) the placement decides ONE type for the candidate and it is one of the hole's `expected_types`; (a2) the declared type is that type (J4); (a3) the declared type is a type the placement gives to
    the HOLE'S OWN word, when it gives any (MULTIPLE: one of them). A word the placement gives no type is not refused HERE: the next gate `_gate_a4` refuses it (round 3, ruling A: it replaces J12, which let it
    through to the later gates). (gate, reason, type) of the first failure, else None."""
    answer = query.query(word)
    t, why = R.placement_type(answer)
    if why is not None:
        return "a1", "GATE_A_NOT_PLACED:%s" % why, None
    if t not in hole["expected_types"]:
        return "a1", "GATE_A_TYPE_NOT_EXPECTED", t
    if decl["type"] not in hole["expected_types"] or decl["type"] != t:
        return "a2", "GATE_A_DECLARED_TYPE_MISMATCH", t
    own = EC.PlaceResult.from_coarse_query(query.query(hole["head"])).types
    if own and decl["type"] not in own:
        return "a3", "GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD", t
    return None


def _other_combos(hole_result: Dict[str, Any], hi: int):
    """The other holes of the sentence and every typing of them the reader may accept (the product of their `expected_types`; one empty combination when there is no other hole)."""
    others = [h for j, h in enumerate(hole_result["holes"]) if j != hi]
    return others, list(itertools.product(*[sorted(o["expected_types"]) for o in others]))


def _gate_a4(text: str, hole_result: Dict[str, Any], hi: int, query: Any, shared: Dict[str, Any]) -> Dict[str, Any]:
    """(a4) (round 3, ruling A; replaces J12): the candidate may decide the WORD, never the STRUCTURE. It does not depend on the candidate, so it is computed once per hole.
    `own` = the types the placement gives the hole's word. No type (UNPLACED / UNKNOWN) -> `GATE_A_HOLE_WORD_UNPLACED`. Otherwise every type T of `own` is tried in the original sentence (with every typing of
    the OTHER holes): the sentence is read with the hole's word typed T and the role of the hole's arm is the one the reader names (`_hole_arm`), or None (not readable / no single role). The gate passes only
    when ALL of them give the SAME single role (a None counts: a type that is not read is not ignored); else `GATE_A_ROLE_SPLIT` with `split_kind` ROLES_DIFFER (two roles read) or TYPE_NOT_READ.
    Returns {ok, reason, role, hole_word_state, hole_word_types, role_by_type, split_kind}. Only types and role names are in it (K286)."""
    hole = hole_result["holes"][hi]
    own = list(EC.PlaceResult.from_coarse_query(query.query(hole["head"])).types)
    state = hole.get("placement_state")
    res = {"ok": False, "reason": None, "role": None, "hole_word_state": state, "hole_word_types": sorted(own), "role_by_type": {}, "split_kind": None}
    if not own or state in ("UNPLACED", "UNKNOWN"):
        res["reason"] = "GATE_A_HOLE_WORD_UNPLACED"
        return res
    others, combos = _other_combos(hole_result, hi)
    seen = set()
    for t in sorted(own):
        per = []
        for combo in combos:
            forced = {o["head"]: c for o, c in zip(others, combo)}
            forced[hole["head"]] = t
            out = S.read(text, "ja", placement=S._HoleProbe(query, forced, shared))
            per.append(S._hole_arm(out["clauses"][0], hole["head"], t) if S._hole_probe_ok(out) else None)
        seen.update(per)
        uniq = sorted(set(x for x in per if x is not None))
        res["role_by_type"][t] = (None if None in per else (uniq[0] if len(uniq) == 1 else uniq))
    roles = set(x for x in seen if x is not None)
    if len(seen) == 1 and None not in seen:
        res["ok"], res["role"] = True, next(iter(seen))
        return res
    res["reason"] = "GATE_A_ROLE_SPLIT"
    res["split_kind"] = "ROLES_DIFFER" if len(roles) >= 2 else "TYPE_NOT_READ"
    return res


def _gate_b_prime(text: str, hole_result: Dict[str, Any], hi: int, wtype: str, role: str, query: Any, shared: Dict[str, Any]) -> tuple:
    """(b') (round 3, ruling B): the type-injected reread of the ORIGINAL sentence. The hole's word is typed `wtype` (the type the candidate was adopted with), the other holes by every typing of them, and
    the sentence is read again with `semantic_reader` untouched (the query is replaced). It passes only when, for every typing: (1) it is read, (2) the hole's arm is `role` (what (a4) found), (3) the clause
    keys other than `roles`/`role_basis` (the centre) equal those of `hole_result["partial"]`, (4) the arms that are not holes equal those of the partial (roles and role_basis).
    -> (None, None) or ("GATE_B_REREAD_MISMATCH", detail) with detail NOT_READABLE / ARM_ROLE_DIFFERS / CENTER_DIFFERS / OTHER_ARMS_DIFFER. It does not depend on the candidate word."""
    hole = hole_result["holes"][hi]
    partial = hole_result.get("partial") or {}
    others, combos = _other_combos(hole_result, hi)
    p_center = {k: v for k, v in partial.items() if k not in ("roles", "role_basis")}
    p_roles = {k: v for k, v in (partial.get("roles") or {}).items() if not (isinstance(v, dict) and "hole" in v)}
    p_basis = {k: v for k, v in (partial.get("role_basis") or {}).items() if k in p_roles}
    for combo in combos:
        forced = {o["head"]: c for o, c in zip(others, combo)}
        forced[hole["head"]] = wtype
        out = S.read(text, "ja", placement=S._HoleProbe(query, forced, shared))
        if not S._hole_probe_ok(out):
            return "GATE_B_REREAD_MISMATCH", "NOT_READABLE"
        cl = out["clauses"][0]
        if S._hole_arm(cl, hole["head"], wtype) != role:
            return "GATE_B_REREAD_MISMATCH", "ARM_ROLE_DIFFERS"
        if {k: v for k, v in cl.items() if k not in ("roles", "role_basis")} != p_center:
            return "GATE_B_REREAD_MISMATCH", "CENTER_DIFFERS"
        hole_arms = {role}
        for o, c in zip(others, combo):
            name = S._hole_arm(cl, o["head"], c)
            if name is None:
                return "GATE_B_REREAD_MISMATCH", "OTHER_ARMS_DIFFER"
            hole_arms.add(name)
        roles = {k: v for k, v in (cl.get("roles") or {}).items() if k not in hole_arms}
        basis = {k: v for k, v in (cl.get("role_basis") or {}).items() if k in roles}
        if roles != p_roles or basis != p_basis:
            return "GATE_B_REREAD_MISMATCH", "OTHER_ARMS_DIFFER"
    return None, None


def _content(out: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from . import observe
    reading = EC.build_crosses(out, EC.StubLookup())
    if reading.status != "CROSSED" or len(reading.crosses) != 1:
        return None
    return observe.content_of_cross(reading.crosses[0])


def _gate_b(text: str, hole_result: Dict[str, Any], hi: int, word: str, wtype: str, query: Any, placement_path: Optional[str], shared: Dict[str, Any],
            require_realize: bool = False) -> tuple:
    """(b) the sentence with the candidate in the hole, read again with the real placement, is the cross of the probe (the hole's arm written as the candidate, everything else as it was) and
    the candidate's arm is one of the hole's roles; a single-hole cross is then realized and read back (`cross_tokens.realize_tokens`). (reason or None, realize status). J10 (closed by W3-d1): the realizer
    used to read its sentence back WITHOUT the placement and to write the topic with は, so a typed cross (an agent and a goal) was refused whichever the candidate was; it now reads the sentence
    with the placement passed here and tries the topic particles of its forms table in order (`semantic_realize`, K312/K315). The default is unchanged: the step is recorded (`realize`) and required
    only with `require_realize=True` (the substituted sentence read with the real placement is the check that is always made)."""
    holes = hole_result["holes"]
    hole = holes[hi]
    others = [h for j, h in enumerate(holes) if j != hi]
    s, e = hole["span"]
    new_text = text[:s] + word + text[e:]
    valid, last_out = 0, None
    for combo in itertools.product(*[sorted(o["expected_types"]) for o in others]):
        forced = {o["head"]: c for o, c in zip(others, combo)}
        probe = S.read(text, "ja", placement=S._HoleProbe(query, dict(forced, **{hole["head"]: wtype}), shared))
        if not S._hole_probe_ok(probe):
            continue
        valid += 1
        out = S.read(new_text, "ja", placement=S._HoleProbe(query, forced, shared)) if forced else S.read(new_text, "ja", placement=query)
        if not S._hole_probe_ok(out):
            return "GATE_B_REREAD_NOT_READABLE", None
        arm = [k for k, v in out["clauses"][0]["roles"].items() if v == word]
        if len(arm) != 1 or arm[0] not in hole["role_candidates"]:
            return "GATE_B_REREAD_ARM_NOT_A_HOLE_ROLE", None
        parm = S._hole_arm(probe["clauses"][0], hole["head"], wtype)
        if parm is None:
            return "GATE_B_REREAD_PROBE_ARM", None
        expected = copy.deepcopy(probe)
        expected["clauses"][0]["roles"][parm] = word
        if _content(out) != _content(expected):
            return "GATE_B_REREAD_CROSS_DIFFERS", None
        last_out = out
    if valid == 0:
        return "GATE_B_REREAD_NO_PROBE_COMBINATION", None
    realize = "SKIPPED_OTHER_HOLES" if others else None
    if not others:
        if not isinstance(placement_path, str) or not placement_path.strip():
            realize = "NEEDS_PLACEMENT_PATH"
        else:
            cross = EC.build_crosses(last_out, _QueryLookup(query)).crosses[0]
            res = CT.realize_tokens(CT.cross_to_tokens(cross), "ja", placement=placement_path)
            realize = res.get("status")
        if require_realize and realize != "REALIZED":
            return "GATE_B_REALIZE_%s" % realize, realize
    return None, realize


def _gate_c(text: str, hole_result: Dict[str, Any], hi: int, word: str, query: Any, records: Any, shared: Optional[Dict[str, Any]] = None) -> tuple:
    """(c) not against a record: a record cross with the same predicate, tense, modality, voice and arms but the OPPOSITE polarity. Returns (reason or None, records_checked, note).
    `records_checked` is the number of records that were REALLY compared with the sentence that has the candidate in it; it is 0 when no comparison could be made, and `note` then says why
    (`GATE_C_NOT_CHECKED:NOT_READABLE`, `GATE_C_NOT_CHECKED:OTHER_HOLES_NOT_READABLE`) -- the sentence is not refused for that (conservative reading of K282: no record is not a contradiction), but the
    non-check is on the record. With other holes in the sentence they are typed by the probe (as in gate b), every typing the reader accepts is compared, and a contradiction under any of them refuses.
    J13 (W10-f05): this function compares whatever `records.crosses` it is given; `ask_and_gate` calls it once with the documents' records and, when `VERA_SOVEREIGN_*` is set, once more with the sovereign's
    utterances (`_sovereign_crosses`), and `FillDecision.sovereign_checked` is True only when that second call really compared one."""
    crosses = []
    for rid, c in (getattr(records, "crosses", None) or {}).items():
        if c is not None:
            crosses.append((rid, c))
    if not crosses:
        return None, 0, None
    holes = hole_result["holes"]
    hole = holes[hi]
    others = [h for j, h in enumerate(holes) if j != hi]
    s, e = hole["span"]
    new_text = text[:s] + word + text[e:]
    outs = []
    if not others:
        outs.append(S.read(new_text, "ja", placement=query))
    else:
        for combo in itertools.product(*[sorted(o["expected_types"]) for o in others]):
            outs.append(S.read(new_text, "ja", placement=S._HoleProbe(query, {o["head"]: c for o, c in zip(others, combo)}, shared if shared is not None else {})))
    outs = [o for o in outs if S._hole_probe_ok(o)]
    if not outs:
        return None, 0, "GATE_C_NOT_CHECKED:%s" % ("OTHER_HOLES_NOT_READABLE" if others else "NOT_READABLE")
    for out in outs:
        cl = out["clauses"][0]
        roles = {r: _nfkc(v) for r, v in cl["roles"].items()}
        for rid, c in crosses:
            center = dict(c["center"])
            if (center.get("predicate"), center.get("tense"), center.get("modality"), center.get("voice")) != (cl.get("predicate"), cl.get("tense"), cl.get("modality"), cl.get("voice")):
                continue
            if c["roles"] == roles and center.get("polarity") in ("+", "-") and cl.get("polarity") in ("+", "-") and center["polarity"] != cl.get("polarity"):
                return "GATE_C_CONTRADICTS_RECORD:%s" % rid, len(crosses), None
    return None, len(crosses), None


def _sovereign_crosses() -> Optional[Dict[str, Any]]:
    """W10-f05 (J13): the sovereign's utterances as sentence crosses for gate (c), or None when neither `VERA_SOVEREIGN_ROOT` nor `VERA_SOVEREIGN_STORE` is set (then nothing here changes: no key in
    `gate_log`, `sovereign_checked` False). Read once per `ask_and_gate`. Only an `ACTIVE_CONSENTED` sovereign (`basis_policy._read_sovereign`, the reader the basis policy uses) contributes: its `utterance`
    events whose `payload.text` (observe) or `payload.phrase` is a string and that the reader reads as one clause (`decode_grammar.cross_of`). Returns `{"state", "crosses": {event id: cross}, "unread": n}`."""
    import os
    if not (os.environ.get("VERA_SOVEREIGN_ROOT") or os.environ.get("VERA_SOVEREIGN_STORE")):
        return None
    from . import basis_policy as BP
    from . import decode_grammar as DG
    view = BP._read_sovereign(True)
    crosses: Dict[str, Any] = {}
    unread = 0
    if view.state == "ACTIVE_CONSENTED":
        for e in view.events:
            if e.get("kind") != "utterance":
                continue
            p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
            text = p.get("text") if isinstance(p.get("text"), str) else p.get("phrase") if isinstance(p.get("phrase"), str) else None
            if text is None:
                continue
            c, _why = DG.cross_of(text)
            if c is None:
                unread += 1
            else:
                crosses[str(e.get("id") or e.get("seq"))] = c
    return {"state": view.state, "crosses": crosses, "unread": unread}


# ---------------------------------------------------------------------------------------------------------------------------------
# the call
# ---------------------------------------------------------------------------------------------------------------------------------
class _BackendProvider:
    """A `llm_choice` provider over `chat(model, messages, fmt)`: a failure keeps its type (it is not an empty answer)."""
    def __init__(self, chat: Callable, model: str, name: str, clock: "_Clock") -> None:
        self.chat, self.model, self.name, self.clock = chat, model, name, clock
        self.last_error: Optional[str] = None

    def ask(self, prompt: str) -> LC.ProviderReply:
        res = self.clock.call(self.chat, self.model, [{"role": "user", "content": prompt}], CLOSED_SCHEMA)
        if not res.get("ok"):
            kind = (res.get("error") or {}).get("type", "BAD_RESPONSE")
            self.last_error = kind
            return LC.ProviderReply.failed(kind, provider=self.name, model=self.model, detail=str((res.get("error") or {}).get("detail", "")))
        return LC.ProviderReply.success(res.get("content") or "", provider=self.name, model=self.model)


class _Clock:
    def __init__(self) -> None:
        self.llm_ms = 0.0
        self.calls = 0

    def call(self, chat: Callable, model: str, messages, fmt) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            res = chat(model, messages, fmt)
        except Exception as exc:        # a plugged-in backend is never allowed to crash the turn
            res = {"ok": False, "content": None, "error": {"type": "CONNECT_FAILED", "detail": "%s: %s" % (type(exc).__name__, exc)}}
        self.llm_ms += (time.perf_counter() - t0) * 1000.0
        self.calls += 1
        return res


def ask_and_gate(hole_result: Dict[str, Any], *, text: str, chat: Callable, model: str, backend_name: str = "fake", hole: int = 0, placement: Any = S._UNSET,
                 ledger: Any = None, choice_ledger: Optional[LC.ChoiceLedger] = None, records: Any = None, mask_user_text: bool = True, k: int = DEFAULT_K,
                 doc_id: Optional[str] = None, require_realize: bool = False, chooser_factory: Optional[Callable] = None, id_source: Optional[Callable[[], str]] = None,
                 order_source: Optional[Callable[[int], Sequence[int]]] = None, version: str = "") -> FillDecision:
    """One hole -> a `FillDecision`. `hole_result` is the output of `semantic_read.read_with_holes(text, ...)`; `chat(model, messages, fmt)` is the backend (llm_backend). `placement` is the one
    the hole was read with (a path or the variable VERA_PLACEMENT). With a `ledger` (testimony_ledger.TestimonyLedger) the decision is written to it (an adoption, a gate failure, a backend failure)."""
    t_start = time.perf_counter()
    fill_id = (id_source or (lambda: uuid.uuid4().hex[:16]))()
    holes = hole_result.get("holes") or []
    base = dict(fill_id=fill_id, mask_user_text=bool(mask_user_text), provenance={"backend": backend_name, "model": model, "version": version},
                context={"doc_id": doc_id, "sentence_sha256": _sha(text)})
    if not mask_user_text:
        base["context"]["sentence"] = text
    if not holes or hole >= len(holes):
        return FillDecision("NO_HOLE", "NO_HOLE", **base)
    h = holes[hole]
    query = S._placement_query(placement)
    if query is None:
        return FillDecision("NOT_ADOPTED", "NO_PLACEMENT", word=h["head"], hole=h, **base)
    import os
    placement_path = placement if isinstance(placement, str) else (os.environ.get("VERA_PLACEMENT") if placement is S._UNSET else None)
    clock = _Clock()
    shared: Dict[str, Any] = {}
    done = {}
    sov = _sovereign_crosses()                    # J13: None unless VERA_SOVEREIGN_* is set
    sov_checked = [False]

    def finish(status: str, reason: str, **kw) -> FillDecision:
        d = FillDecision(status, reason, word=h["head"], hole=h, timing={"llm_ms": round(clock.llm_ms, 3), "vera_ms": round((time.perf_counter() - t_start) * 1000.0 - clock.llm_ms, 3)},
                         sovereign_checked=bool(sov_checked[0]), **dict(base, **kw))
        if ledger is not None:
            try:
                rec = ledger.record_decision(d.to_dict())
                if status == "ADOPTED":
                    decl = d.declaration
                    ans = query.query(h["head"])
                    t, why = R.placement_type(ans)
                    if why is None and t == decl["type"]:
                        ledger.mark_distribution_backed(h["head"], d.candidate, decl["type"], decl.get("role"), fill_id, ans)
                    ledger.promote_pending()
            except LC.LedgerIntegrityError as exc:
                return FillDecision("REFUSED", "LEDGER_INTEGRITY", word=h["head"], hole=h, timing=d.timing, **dict(base, gate_log=d.gate_log))
        return d

    if ledger is not None:
        try:
            ledger.verify()
        except LC.LedgerIntegrityError:
            return FillDecision("REFUSED", "LEDGER_INTEGRITY", word=h["head"], hole=h, **base)
    # --- 1 the open declaration (one ask, a closed schema)
    predicate = (hole_result.get("partial") or {}).get("predicate")
    coords = coordinates(hole_result, text, query, mask_user_text=mask_user_text, shared=shared)
    res = clock.call(chat, model, open_messages(h, coords, predicate, None if mask_user_text else text, k), open_schema(h["role_candidates"], k))
    if not res.get("ok"):
        return finish("BACKEND_FAILED", "BACKEND_FAILED:%s" % (res.get("error") or {}).get("type", "BAD_RESPONSE"))
    content = res.get("content")
    if not isinstance(content, str) or not content.strip():
        return finish("BACKEND_FAILED", "BACKEND_FAILED:EMPTY_CONTENT")
    decl, why = parse_open(content, h, k)
    if decl is None:
        return finish("NOT_ADOPTED", "OPEN_DECLARATION_INVALID:%s" % why)
    words = list(dict.fromkeys(_nfkc(w) for w in decl["near_words"]))
    if not words:
        return finish("NOT_ADOPTED", "NO_CANDIDATE_WORDS", declaration=decl)
    # --- 2 the gates, in order, per word; the first gate a word fails is its type
    log, listed, passed = [], [], []
    records_checked = 0
    a4: Optional[Dict[str, Any]] = None             # (a4) and (b') do not depend on the candidate: computed once, for the first word that reaches them
    bp: Optional[tuple] = None
    for w in words:
        a = _gate_a(w, decl, h, query)
        if a is not None:
            log.append({"word": w, "gate": a[0], "reason": a[1]})
            continue
        wtype = decl["type"]
        if a4 is None:
            a4 = _gate_a4(text, hole_result, hole, query, shared)
        if not a4["ok"]:
            row = {"word": w, "gate": "a4", "reason": a4["reason"], "hole_word_state": a4["hole_word_state"], "hole_word_types": a4["hole_word_types"], "role_by_type": a4["role_by_type"]}
            if a4["split_kind"] is not None:
                row["split_kind"] = a4["split_kind"]
            log.append(row)
            continue
        listed.append(w)
        if bp is None:
            bp = _gate_b_prime(text, hole_result, hole, wtype, a4["role"], query, shared)
        if bp[0] is not None:
            log.append({"word": w, "gate": "b_prime", "reason": bp[0], "b_prime_detail": bp[1], "a4_role": a4["role"]})
            continue
        why_b, realize = _gate_b(text, hole_result, hole, w, wtype, query, placement_path, shared, require_realize)
        if why_b is not None:
            log.append({"word": w, "gate": "b", "reason": why_b, "realize": realize})
            continue
        why_c, records_checked, note_c = _gate_c(text, hole_result, hole, w, query, records, shared)
        if why_c is not None:
            log.append({"word": w, "gate": "c", "reason": why_c})
            continue
        c_sov = None
        if sov is not None:                        # J13: the same gate (c), against the sovereign's utterances
            why_s, n_s, note_s = _gate_c(text, hole_result, hole, w, query, SimpleNamespace(crosses=sov["crosses"]), shared)
            c_sov = {"state": sov["state"], "compared": n_s, "note": note_s if note_s is not None else (None if sov["state"] == "ACTIVE_CONSENTED" else "SOVEREIGN_NOT_COMPARED:%s" % sov["state"])}
            if n_s > 0:
                sov_checked[0] = True
            if why_s is not None:
                log.append({"word": w, "gate": "c", "reason": why_s.replace("GATE_C_CONTRADICTS_RECORD:", "GATE_C_CONTRADICTS_SOVEREIGN:", 1), "c_sovereign": c_sov})
                continue
        row = {"word": w, "gate": "passed", "reason": None, "realize": realize, "c_note": note_c, "a4_role": a4["role"], "b_prime": "PASSED"}
        if c_sov is not None:
            row["c_sovereign"] = c_sov
        log.append(row)
        passed.append(w)
    if not passed:
        if a4 is not None and not a4["ok"]:         # J18: (a4) is a property of the hole, not of a word: its reason is the decision's reason whatever the number of candidates
            reason = a4["reason"]
        else:
            reason = log[0]["reason"] if len(words) == 1 else "NO_CANDIDATE_PASSED"
        return finish("NOT_ADOPTED", reason, declaration=decl, gate_log=log, records_checked=records_checked)
    if len(passed) >= 2:
        return finish("NOT_ADOPTED", "GATE_D_TIE", declaration=decl, gate_log=log, records_checked=records_checked)
    # --- 3 the closed ask over the words that passed (a), and only the one word that passed everything may be chosen
    provider = _BackendProvider(chat, model, backend_name, clock)
    if chooser_factory is not None:
        chooser = chooser_factory(provider)
    else:
        if choice_ledger is None:
            choice_ledger = LC.ChoiceLedger(None if getattr(ledger, "path", None) is None else str(ledger.path) + ".choice.jsonl")
        chooser = LC.LLMChooser(provider, choice_ledger, id_source=id_source, order_source=order_source)
    cands = [LC.ChoiceCandidate(w) for w in listed]
    try:
        dec = chooser.choose(h["head"], cands, "" if mask_user_text else text)
    except LC.LedgerIntegrityError:
        return finish("REFUSED", "LEDGER_INTEGRITY", declaration=decl, gate_log=log)
    common = dict(declaration=decl, gate_log=log, records_checked=records_checked, choice_decision_id=dec.decision_id)
    if dec.status == "FAILED":
        return finish("BACKEND_FAILED", "BACKEND_FAILED:%s" % (dec.failure or dec.reason), **common)
    if dec.status == "REFUSED":
        return finish("REFUSED" if dec.reason == "LEDGER_INTEGRITY" else "NOT_ADOPTED", dec.reason if dec.reason == "LEDGER_INTEGRITY" else "GATE_D_CHOICE_REFUSED:%s" % dec.reason, **common)
    if dec.status != "ADOPTED":
        return finish("NOT_ADOPTED", "GATE_D_CHOICE_ABSTAINED:%s" % dec.reason, **common)
    if _nfkc(dec.choice) != passed[0]:
        return finish("NOT_ADOPTED", "GATE_D_CHOICE_NOT_PASSING", **common)
    return finish("ADOPTED", "ADOPTED", candidate=passed[0], origin="testimony", basis="LLM_TESTIMONY_FILL:%s:%s" % (model, dec.decision_id), **common)


# ---------------------------------------------------------------------------------------------------------------------------------
# the entrance (vera serve --fill): read_with_holes + ask_and_gate over a sentence, an arm mark for what was adopted (K283)
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass
class FillConfig:
    """`vera serve --fill`: the candidate mouth. `chat(model, messages, fmt)` is the backend of the fill (None: the same backend as the entrance); `ledger` is a `TestimonyLedger` (required)."""
    ledger: Any
    model: Optional[str] = None
    chat: Optional[Callable] = None
    backend_name: str = "ollama"
    mask_user_text: bool = True
    k: int = DEFAULT_K
    max_holes: int = 2                  # holes in one sentence (read_with_holes)
    max_doc_holes: int = 30             # holes tried when the documents are loaded; more are only counted (skipped_holes)
    placement: Any = S._UNSET
    require_realize: bool = False
    version: str = ""
    id_source: Optional[Callable[[], str]] = None
    order_source: Optional[Callable[[int], Sequence[int]]] = None


def fill_sentence(text: str, fill: FillConfig, chat: Callable, model: str, *, records: Any = None, doc_id: Optional[str] = None, budget: Optional[List[int]] = None) -> Dict[str, Any]:
    """One sentence -> {'status': the holes_status, 'holes': [..., 'decision': FillDecision dict], 'decisions': [FillDecision], 'skipped': n}. A sentence that is not Japanese or that read_with_holes
    refuses is {'status': <why>, 'holes': []}. `budget` ([n]) is the number of holes that may still be asked; the rest are counted in `skipped`."""
    try:
        ho = S.read_with_holes(text, placement=fill.placement, max_holes=fill.max_holes)
    except S.ReadError as exc:
        return {"status": "READ_ERROR:%s" % exc.type, "holes": [], "decisions": [], "skipped": 0}
    out = {"status": ho["holes_status"], "holes": [], "decisions": [], "skipped": 0}
    for i, h in enumerate(ho["holes"]):
        if budget is not None and budget[0] <= 0:
            out["skipped"] += 1
            out["holes"].append(dict(h, decision=None))
            continue
        if budget is not None:
            budget[0] -= 1
        d = ask_and_gate(ho, text=text, chat=chat, model=model, backend_name=fill.backend_name, hole=i, placement=fill.placement, ledger=fill.ledger, records=records,
                         mask_user_text=fill.mask_user_text, k=fill.k, doc_id=doc_id, require_realize=fill.require_realize, id_source=fill.id_source,
                         order_source=fill.order_source, version=fill.version)
        out["decisions"].append(d)
        out["holes"].append(dict(h, decision=d.to_dict()))
    return out


# ---------------------------------------------------------------------------------------------------------------------------------
# W3-e2 (docs/READING_SOUNDNESS.md section 10L, K331 (e), D13): the type of ONE word for an assumed reading. Nothing above this line is changed.
# ---------------------------------------------------------------------------------------------------------------------------------
ASSUMPTION_ASK_STATUSES = ("AGREED", "SPLIT", "NULL", "OUT_OF_CANDIDATES", "BACKEND_FAILED")


def assumption_messages(word: str, particle: str, predicate: Optional[str], candidates: Sequence[str], text: Optional[str] = None) -> List[Dict[str, str]]:
    """The fixed sentence form Vera writes. With the mask on (`text` None) the user's sentence and the other words of it are NOT sent: the word, its particle, the predicate's lemma (when the reader knows
    one) and the closed list of types. The word itself has to be sent: a type of a word cannot be answered about a mask."""
    system = ("あなたは Vera の語彙の提案者です。Vera が型を知らない語の型を、候補の一覧から 1 つ選びます。答えは JSON 1 つだけで、説明は書きません。"
              "分からなければ null。選んだ型を採用するかどうかは Vera が決めます。")
    lines = ["語「%s」（助詞「%s」の位置にある、Vera が型を知らない語）。" % (word, particle or "（なし）"), "述語: %s" % (predicate or MASK_UNKNOWN), "他の語: %s" % MASK_UNKNOWN]
    if text is not None:
        lines.append("文: %s" % json.dumps(text, ensure_ascii=False))
    lines.append("語「%s」そのものの型を、次の番号から 1 つ選んでください（分からなければ null）:" % word)
    for i, t in enumerate(candidates):
        lines.append("%d: %s" % (i, t))
    lines.append('出力: {"choice": 番号またはnull} の JSON 1 つだけ。')
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(lines)}]


def ask_assumption_type(word: str, particle: str, predicate: Optional[str], candidates: Sequence[str], *, chat: Callable, model: str, backend_name: str = "fake",
                        mask_user_text: bool = True, text: Optional[str] = None) -> Dict[str, Any]:
    """Asks TWICE (a closed schema: the number of one candidate or null) and takes a type only when both answers are the same candidate. Returns {"type": the type or None, "status":
    AGREED | SPLIT | NULL | OUT_OF_CANDIDATES | BACKEND_FAILED, "answers": [the types or None], "calls": n, "error": the typed failure or None}. A failure is BACKEND_FAILED (never SPLIT or NULL);
    an answer outside the numbered list is OUT_OF_CANDIDATES. Nothing here reads a sentence: the sentence is sent only with `mask_user_text=False`."""
    cands = list(candidates)
    clock = _Clock()
    answers: List[Optional[str]] = []
    messages = assumption_messages(word, particle, predicate, cands, None if mask_user_text else text)
    schema = {"type": "object", "properties": {"choice": {"type": ["integer", "null"]}}, "required": ["choice"], "additionalProperties": False}
    for _ in range(2):
        res = clock.call(chat, model, messages, schema)
        if not res.get("ok"):
            return {"type": None, "status": "BACKEND_FAILED", "answers": answers, "calls": clock.calls, "error": (res.get("error") or {}).get("type", "BAD_RESPONSE")}
        try:
            data = json.loads(res.get("content") or "", object_pairs_hook=_unique)
        except (TypeError, ValueError):
            return {"type": None, "status": "OUT_OF_CANDIDATES", "answers": answers + ["NOT_JSON"], "calls": clock.calls, "error": None}
        if not isinstance(data, dict) or set(data) != {"choice"}:
            return {"type": None, "status": "OUT_OF_CANDIDATES", "answers": answers + ["KEYS"], "calls": clock.calls, "error": None}
        c = data["choice"]
        if c is None:
            answers.append(None)
        elif type(c) is int and 0 <= c < len(cands):
            answers.append(cands[c])
        else:
            return {"type": None, "status": "OUT_OF_CANDIDATES", "answers": answers + ["OUT_OF_LIST"], "calls": clock.calls, "error": None}
    if answers[0] is None and answers[1] is None:
        return {"type": None, "status": "NULL", "answers": answers, "calls": clock.calls, "error": None}
    if answers[0] is None or answers[0] != answers[1]:
        return {"type": None, "status": "SPLIT", "answers": answers, "calls": clock.calls, "error": None}
    return {"type": answers[0], "status": "AGREED", "answers": answers, "calls": clock.calls, "error": None}

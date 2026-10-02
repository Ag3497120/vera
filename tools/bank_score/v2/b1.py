"""B1（意味読解）v2: 検証と判定。設計者の `audit/score.py`（DESIGN §5。FINAL §8 条件 4）の移植。

設計者との違い（意図したもの）は 2 つ:
  * 最大重みの対応づけ（align）が同点のとき、設計者は最初に見つけたものを採る（勝者を作る）。ここでは
    同点の対応づけを **すべて** 列挙し、判定が全部同じならそれ、割れたら UNJUDGED（ALIGNMENT_TIED）。
    観測の節が多すぎて全探索できないときは UNJUDGED（ALIGNMENT_TOO_LARGE）。
  * 関係の must_not で、対応づけが片方でも無い（None）ときは当たりにしない（設計者は from だけ見る）。
判定は correct / misread / abstain / incomplete の 4 種。9 分類への写像は score.py（D7）。
"""
from __future__ import annotations

import itertools
import math
import unicodedata

ROLES = {"agent", "patient", "recipient", "goal", "result", "source", "place", "time",
         "instrument", "companion", "cause", "quotation", "entity", "value", "attribute",
         "standard", "causer", "causee", "beneficiary", "experiencer"}
MODALITIES = {None, "ability", "obligation", "permission", "prohibition", "volition", "desire",
              "request", "possibility", "conjecture", "hearsay", "question"}
VOICES = {"active", "passive", "causative", "causative_passive"}
REL_TYPES = {"cause", "contrast", "concession", "condition", "purpose", "sequence",
             "simultaneous", "manner", "quote", "relative", "content"}
COMPARISONS = {"comparative", "equative", "superlative"}
QUANT_SIMPLE = {"universal", "existential", "most", "partial", "none", "only"}
QUANT_NUM = ("exactly:", "at_least:", "at_most:", "more_than:", "less_than:", "approx:")
FIELDS = ("predicate", "polarity", "tense", "modality", "voice", "comparison")
EN_PREPS = ("out of ", "during ", "before ", "after ", "behind ", "onto ", "into ", "on ", "in ", "at ",
            "from ", "to ", "than ", "by ", "for ", "of ", "as ")
MAX_OBS_CLAUSES = 8
MAX_COMBINATIONS = 10 ** 6


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_str(x: object) -> bool:
    return isinstance(x, str)


def _str_or_list(x: object, allow_empty_str: bool = False) -> bool:
    if isinstance(x, str):
        return allow_empty_str or x.strip() != ""
    return isinstance(x, list) and len(x) >= 1 and all(isinstance(e, str) and e.strip() != "" for e in x)


# ---- 検証 --------------------------------------------------------------------------------

def _quant_value_ok(v: object) -> bool:
    return isinstance(v, str) and (v in QUANT_SIMPLE or v.startswith(QUANT_NUM))


_MUST_NOT_KNOWN = ("clause", "role", "value", "field", "quantifier", "scope", "relation", "readable")


def must_not_shape(m: object) -> str | None:
    """must_not の形の名前。6 形以外は None（不正）。

    既知のキーだけで形を決める。未知のキーが混ざっていても形は決まる（未知のキーは keys.find_unknown が問題ごとに記録し、
    その問題は UNJUDGED になる。ITEM_INVALID にはしない）。
    """
    if not isinstance(m, dict):
        return None
    m = {k: v for k, v in m.items() if k in _MUST_NOT_KNOWN}
    keys = set(m)
    if keys == {"readable"}:
        return "readable" if isinstance(m["readable"], bool) else None
    if keys == {"relation"}:
        r = m["relation"]
        ok = (isinstance(r, dict) and {"type", "from", "to"} <= set(r) and _is_str(r["type"])
              and _is_int(r["from"]) and _is_int(r["to"]))
        return "relation" if ok else None
    if "clause" not in keys:
        return None
    c = m["clause"]
    if not (_is_int(c) or c == "*"):
        return None
    rest = keys - {"clause"}
    if rest == {"role", "value"}:
        return "role" if _str_or_list(m["role"]) and _str_or_list(m["value"], True) else None
    if rest == {"field", "value"}:
        v = m["value"]
        ok = m["field"] in FIELDS and (v is None or _str_or_list(v, True))
        return "field" if ok else None
    if rest == {"quantifier", "value"}:
        return "quantifier" if _is_str(m["quantifier"]) and _str_or_list(m["value"]) else None
    if rest == {"scope"}:
        return "scope" if _str_or_list(m["scope"]) else None
    return None


def validate_item(raw: dict, errs: list[str]) -> dict | None:
    """B1 v2 の 1 問を検査。誤りの型を errs に足し、採点用の case を返す。"""
    inp = raw.get("input")
    if "input" not in raw:
        errs.append("MISSING_FIELD:input")
    elif not (_is_str(inp) and inp.strip()):
        errs.append("BAD_TYPE:input")
    exp = raw.get("expect") or {}
    readable = exp.get("readable")
    if not isinstance(readable, bool):
        errs.append("BAD_TYPE:expect.readable")
    beh = raw.get("behavior")
    if "behavior" not in raw:
        errs.append("MISSING_FIELD:behavior")
    elif beh not in ("read", "abstain"):
        errs.append("BAD_VALUE:behavior")
    elif isinstance(readable, bool) and (beh == "read") != readable:
        errs.append("BEHAVIOR_READABLE_MISMATCH")
    cl = exp.get("clauses")
    n_cl = 0
    if not isinstance(cl, list):
        errs.append("BAD_TYPE:expect.clauses")
    else:
        n_cl = len(cl)
        if readable is False and cl:
            errs.append("CLAUSES_NOT_EMPTY_FOR_UNREADABLE")
        for i, c in enumerate(cl):
            _validate_clause(c, i, errs)
    rel = exp.get("relations")
    if not isinstance(rel, list):
        errs.append("BAD_TYPE:expect.relations")
    else:
        if readable is False and rel:
            errs.append("RELATIONS_NOT_EMPTY_FOR_UNREADABLE")
        for i, r in enumerate(rel):
            ok = isinstance(r, dict) and _is_int(r.get("from")) and _is_int(r.get("to"))
            t = r.get("type") if isinstance(r, dict) else None
            types = t if isinstance(t, list) else [t]
            if not ok or not types or not all(x in REL_TYPES for x in types):
                errs.append(f"BAD_TYPE:expect.relations[{i}]")
            elif not (0 <= r["from"] < n_cl and 0 <= r["to"] < n_cl):
                errs.append(f"BAD_VALUE:expect.relations[{i}].index")
    mn = exp.get("must_not")
    if not isinstance(mn, list):
        errs.append("BAD_TYPE:expect.must_not")
    else:
        for i, m in enumerate(mn):
            shape = must_not_shape(m)
            if shape is None:
                errs.append(f"BAD_MUST_NOT[{i}]")
                continue
            if shape == "role":
                roles = m["role"] if isinstance(m["role"], list) else [m["role"]]
                if any(r not in ROLES for r in roles):
                    errs.append(f"BAD_VALUE:expect.must_not[{i}].role")
            if shape == "quantifier" and m["quantifier"] not in ROLES | {"event"}:
                errs.append(f"BAD_VALUE:expect.must_not[{i}].quantifier")
            if shape == "relation" and m["relation"]["type"] not in REL_TYPES:
                errs.append(f"BAD_VALUE:expect.must_not[{i}].relation.type")
            if isinstance(m, dict) and _is_int(m.get("clause")) and readable is True and not (0 <= m["clause"] < n_cl):
                errs.append(f"BAD_VALUE:expect.must_not[{i}].clause")
    if _is_str(inp) and inp.strip():
        return {"input": inp}
    return None


def _validate_clause(c: object, i: int, errs: list[str]) -> None:
    p = f"expect.clauses[{i}]"
    if not isinstance(c, dict):
        errs.append(f"BAD_TYPE:{p}")
        return
    for k in ("predicate", "roles", "polarity", "tense", "modality", "voice"):
        if k not in c:
            errs.append(f"MISSING_FIELD:{p}.{k}")
    if "predicate" in c and not _str_or_list(c["predicate"]):
        errs.append(f"BAD_TYPE:{p}.predicate")
    roles = c.get("roles")
    if "roles" in c:
        if not isinstance(roles, dict):
            errs.append(f"BAD_TYPE:{p}.roles")
        else:
            for r, v in roles.items():
                if r not in ROLES:
                    errs.append(f"BAD_VALUE:{p}.roles.role_name")
                elif not _str_or_list(v):
                    errs.append(f"BAD_TYPE:{p}.roles.value")
    if "polarity" in c and c["polarity"] not in ("+", "-"):
        errs.append(f"BAD_VALUE:{p}.polarity")
    if "tense" in c and c["tense"] not in ("past", "nonpast", None):
        errs.append(f"BAD_VALUE:{p}.tense")
    if "modality" in c and c["modality"] not in MODALITIES:
        errs.append(f"BAD_VALUE:{p}.modality")
    if "voice" in c and c["voice"] not in VOICES:
        errs.append(f"BAD_VALUE:{p}.voice")
    if c.get("comparison") is not None and c["comparison"] not in COMPARISONS:
        errs.append(f"BAD_VALUE:{p}.comparison")
    q = c.get("quantifiers")
    if q is not None:
        if not isinstance(q, dict):
            errs.append(f"BAD_TYPE:{p}.quantifiers")
        else:
            for k, v in q.items():
                if k not in ROLES | {"event"}:
                    errs.append(f"BAD_VALUE:{p}.quantifiers.key")
                elif not _quant_value_ok(v):
                    errs.append(f"BAD_VALUE:{p}.quantifiers.value")
    sc = c.get("scope")
    if sc is not None and not (isinstance(sc, list) and sc and all(
            isinstance(e, str) and (e == "neg" or e in ROLES or e == "event") for e in sc)):
        errs.append(f"BAD_VALUE:{p}.scope")


# ---- 判定（score.py の移植） ----------------------------------------------------------------

def norm(s: object, lang: str = "ja") -> str | None:
    if s is None:
        return None
    s = unicodedata.normalize("NFKC", str(s)).lower().strip()

    def is_p(c: str) -> bool:
        return c.isspace() or unicodedata.category(c).startswith("P")
    while s and is_p(s[0]):
        s = s[1:]
    while s and is_p(s[-1]):
        s = s[:-1]
    if lang == "en":
        for prep in EN_PREPS:
            if s.startswith(prep):
                s = s[len(prep):]
                break
        for art in ("the ", "a ", "an "):
            if s.startswith(art):
                s = s[len(art):]
                break
    return s


def as_list(v: object) -> list:
    return v if isinstance(v, list) else [v]


def val_eq(gold: object, out: object, lang: str) -> bool:
    if not isinstance(out, str):
        return False
    o = norm(out, lang)
    return any(norm(g, lang) == o for g in as_list(gold))


def val_hit(bad: object, out: object, lang: str) -> bool:
    if out is None:
        return False
    outs = as_list(out)
    return any(isinstance(o, str) and norm(o, lang) == norm(b, lang) for o in outs for b in as_list(bad))


def pair_weight(g: dict, o: dict, lang: str) -> int:
    w = 0
    if val_eq(g.get("predicate"), o.get("predicate"), lang):
        w += 2
    groles = g.get("roles") or {}
    oroles = o.get("roles") if isinstance(o.get("roles"), dict) else {}
    for r, v in groles.items():
        if r in oroles and val_eq(v, oroles[r], lang):
            w += 1
    return w


def align_all(gold: list[dict], out: list[dict], lang: str) -> tuple[list[dict[int, int]] | None, str | None]:
    """最大重み（重み, −位置のずれ）の 1 対 1 対応づけを、同点をすべて集めて返す。

    (対応づけの一覧, None)。全探索できないとき (None, "ALIGNMENT_TOO_LARGE")。
    """
    n, m = len(gold), len(out)
    if n == 0 or m == 0:
        return [{}], None
    k = min(n, m)
    if m > MAX_OBS_CLAUSES or math.comb(n, k) * math.perm(m, k) > MAX_COMBINATIONS:
        return None, "ALIGNMENT_TOO_LARGE"
    best_key = None
    bests: list[dict[int, int]] = []
    for gsel in itertools.combinations(range(n), k):
        for osel in itertools.permutations(range(m), k):
            w = sum(pair_weight(gold[g], out[o], lang) for g, o in zip(gsel, osel))
            dist = sum(abs(g - o) for g, o in zip(gsel, osel))
            key = (w, -dist)
            if best_key is None or key > best_key:
                best_key, bests = key, [dict(zip(gsel, osel))]
            elif key == best_key:
                bests.append(dict(zip(gsel, osel)))
    uniq: list[dict[int, int]] = []
    for b in bests:
        if b not in uniq:
            uniq.append(b)
    return uniq, None


def _target_clauses(spec_clause: object, out: dict, mapping: dict, gold_readable: bool) -> list[dict]:
    oc = out["clauses"]
    if spec_clause == "*":
        return oc
    if not gold_readable:
        return [oc[spec_clause]] if _is_int(spec_clause) and 0 <= spec_clause < len(oc) else []
    j = mapping.get(spec_clause)
    return [oc[j]] if j is not None and j < len(oc) else []


def must_not_hits(expect: dict, lang: str, out: dict, mapping: dict) -> list[dict]:
    """当たった must_not の仕様（元の辞書）の一覧。"""
    gold_readable = expect["readable"]
    hits: list[dict] = []
    if not out["readable"]:
        return hits
    for spec in expect.get("must_not") or []:
        if "readable" in spec:
            if out["readable"] == spec["readable"]:
                hits.append(spec)
            continue
        if "relation" in spec:
            r = spec["relation"]
            fo, to = r["from"], r["to"]
            if gold_readable:
                fo, to = mapping.get(fo), mapping.get(to)
            if fo is None or to is None:
                continue
            for orl in out["relations"]:
                if r["type"] in as_list(orl.get("type")) and orl.get("from") == fo and orl.get("to") == to:
                    hits.append(spec)
                    break
            continue
        for oc in _target_clauses(spec.get("clause"), out, mapping, gold_readable):
            if "role" in spec:
                roles = oc["roles"]
                if any(val_hit(spec["value"], roles.get(rn), lang) for rn in as_list(spec["role"])):
                    hits.append(spec)
                    break
            elif "field" in spec:
                f = spec["field"]
                ov = oc.get(f)
                if spec["value"] is None:
                    if ov is None:
                        hits.append(spec)
                        break
                elif f == "predicate":
                    if val_hit(spec["value"], ov, lang):
                        hits.append(spec)
                        break
                else:
                    if ov is not None and any(x in as_list(spec["value"]) for x in as_list(ov)):
                        hits.append(spec)
                        break
            elif "quantifier" in spec:
                q = oc["quantifiers"].get(spec["quantifier"])
                if q is not None and any(x in as_list(spec["value"]) for x in as_list(q)):
                    hits.append(spec)
                    break
            elif "scope" in spec:
                osc = oc.get("scope")
                if osc == spec["scope"] or (isinstance(osc, list) and spec["scope"] in osc):
                    hits.append(spec)
                    break
    return hits


def clause_equal(g: dict, o: dict, lang: str) -> bool:
    if not val_eq(g["predicate"], o.get("predicate"), lang):
        return False
    groles, oroles = g.get("roles") or {}, o["roles"]
    if set(groles) != set(oroles):
        return False
    for r, v in groles.items():
        if not val_eq(v, oroles[r], lang):
            return False
    if g.get("polarity") != o.get("polarity"):
        return False
    if g.get("tense") is not None and g.get("tense") != o.get("tense"):
        return False
    if g.get("modality") != o.get("modality"):
        return False
    if g.get("voice") != o.get("voice"):
        return False
    if (g.get("quantifiers") or {}) != o["quantifiers"]:
        return False
    if (g.get("scope") or None) != (o.get("scope") or None):
        return False
    if g.get("comparison") != o.get("comparison"):
        return False
    return True


def relations_equal(gold_rels: list[dict], out_rels: list[dict], mapping: dict[int, int]) -> bool:
    inv = {o: g for g, o in mapping.items()}
    mapped = []
    for r in out_rels:
        t = r.get("type")
        if isinstance(t, list):
            return False
        fo, to = inv.get(r.get("from")), inv.get(r.get("to"))
        if fo is None or to is None:
            return False
        mapped.append((t, fo, to))
    if len(mapped) != len(gold_rels):
        return False
    used: set[int] = set()
    for gr in gold_rels:
        ok = False
        for i, (t, fo, to) in enumerate(mapped):
            if i in used:
                continue
            if t in as_list(gr["type"]) and fo == gr["from"] and to == gr["to"]:
                used.add(i)
                ok = True
                break
        if not ok:
            return False
    return True


def sanitize_output(out: dict | None) -> dict:
    """観測 → 判定用の出力。壊れた要素は空の辞書にして番号を保つ（落とさない）。"""
    out = out if isinstance(out, dict) else {"readable": True, "clauses": [], "relations": []}
    cls = []
    for c in out.get("clauses") or []:
        c = dict(c) if isinstance(c, dict) else {}
        if not isinstance(c.get("roles"), dict):
            c["roles"] = {}
        if not isinstance(c.get("quantifiers"), dict):
            c["quantifiers"] = {}
        cls.append(c)
    rels = [r if isinstance(r, dict) else {} for r in (out.get("relations") or [])]
    return {"readable": bool(out.get("readable")), "clauses": cls, "relations": rels}


def _verdict_with(expect: dict, lang: str, out: dict, mapping: dict) -> tuple[str, str | None, list[dict]]:
    oread = out["readable"]
    if not expect["readable"]:
        if oread and out["clauses"]:
            return "misread", "STRUCTURED_UNREADABLE", []
        hits = must_not_hits(expect, lang, out, {})
        if hits:
            return "misread", "MUST_NOT", hits
        return ("correct", None, []) if not oread else ("incomplete", "READABLE_WITHOUT_CLAUSES", [])
    hits = must_not_hits(expect, lang, out, mapping)
    if hits:
        return "misread", "MUST_NOT", hits
    if not oread:
        return "abstain", None, []
    gc, oc = expect["clauses"], out["clauses"]
    if len(gc) != len(oc):
        return "incomplete", "CLAUSE_COUNT", []
    if len(mapping) != len(gc):
        return "incomplete", "ALIGNMENT", []
    for g, o in mapping.items():
        if not clause_equal(gc[g], oc[o], lang):
            return "incomplete", "CLAUSE_MISMATCH", []
    if not relations_equal(expect.get("relations") or [], out["relations"], mapping):
        return "incomplete", "RELATIONS", []
    return "correct", None, []


def judge(expect: dict, lang: str, out_raw: dict | None) -> dict:
    """(判定, 理由コード, 当たった must_not) を辞書で返す。同点の対応づけで判定が割れたら verdict=UNJUDGED。"""
    out = sanitize_output(out_raw)
    if not expect["readable"] or not out["readable"]:
        maps, why = [{}], None
    else:
        maps, why = align_all(expect["clauses"], out["clauses"], lang)
    if maps is None:
        return {"verdict": "UNJUDGED", "reason": why, "hits": [], "alignments": None}
    results = [_verdict_with(expect, lang, out, m) for m in maps]
    verdicts = {r[0] for r in results}
    if len(verdicts) > 1:
        return {"verdict": "UNJUDGED", "reason": "ALIGNMENT_TIED", "hits": [], "alignments": len(maps)}
    v, reason, hits = results[0]
    return {"verdict": v, "reason": reason, "hits": hits, "alignments": len(maps)}


def gold_output(expect: dict) -> dict:
    """参考例: 正解の各リストの先頭を採った出力（score.py の gold_output と同じ作り方）。"""
    if not expect["readable"]:
        return {"readable": False, "clauses": [], "relations": []}
    cl = []
    for c in expect["clauses"]:
        d = dict(c)
        d["predicate"] = as_list(c["predicate"])[0]
        d["roles"] = {r: as_list(v)[0] for r, v in (c.get("roles") or {}).items()}
        cl.append(d)
    rels = [{"type": as_list(r["type"])[0], "from": r["from"], "to": r["to"]} for r in (expect.get("relations") or [])]
    return {"readable": True, "clauses": cl, "relations": rels}


def hit_shapes(hits: list[dict]) -> list[str]:
    return sorted({must_not_shape(h) or "?" for h in hits})

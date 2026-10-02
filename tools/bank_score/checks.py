"""各採点規則。どの規則も PASS / FAIL / UNJUDGED（判定できない）の 3 値だけを返す。

棄権・拒否・escalate は Vera の型つき結果（観測の state）で決まる。ここでは文字列で判定しない。
同点・判定不能は UNJUDGED（辞書順や先勝ちで勝者を作らない）。
"""
from __future__ import annotations

import re

from . import lemma as lemma_mod
from .normalize import (char_count, compact_len, detect_language, norm, split_sentences)
from .schema import expected_side, must_not_shape, unknown_expect_keys

PASS, FAIL, UNJUDGED = "PASS", "FAIL", "UNJUDGED"
LABELS = ("SUPPORTED", "REFUTED", "NOT_IN_DOCS")
_BULLET = re.compile(r"^\s*(?:[・\-\*•]|\d+[.)．])\s*\S")


def res(result: str, **detail: object) -> dict:
    return {"result": result, "detail": detail}


def _rng(spec: dict, n: int) -> bool:
    return ("min" not in spec or n >= spec["min"]) and ("max" not in spec or n <= spec["max"])


# ---- 文字列の規則 ------------------------------------------------------------

def check_must_contain_any(groups: list, text: str) -> dict:
    """外側の各グループはすべて必須、グループ内はどれか 1 つ（部分文字列・正規化後）。"""
    t = norm(text)
    missing = [g for g in groups if not any(norm(w) and norm(w) in t for w in g)]
    return res(FAIL if missing else PASS, missing_groups=missing)


def check_must_contain_all(words: list, text: str) -> dict:
    t = norm(text)
    missing = [w for w in words if not (norm(w) and norm(w) in t)]
    return res(FAIL if missing else PASS, missing=missing)


def check_must_not_contain(words: list, text: str) -> dict:
    t = norm(text)
    hit = [w for w in words if norm(w) and norm(w) in t]
    return res(FAIL if hit else PASS, found=hit)


def _targets(texts: list[str], extra: list[str]) -> set[str]:
    out: set[str] = set()
    for tx in list(texts) + list(extra):
        for s in split_sentences(tx) + [tx]:
            n = norm(s)
            if n:
                out.add(n)
    return out


def check_must_not_equal(spec: object, text: str, target_texts: list[str]) -> dict | None:
    """出力の各文、または出力全体が、比較対象のどれかの文と一致したら FAIL。"""
    if spec is False:
        return None
    extra = [spec] if isinstance(spec, str) else (list(spec) if isinstance(spec, list) else [])
    tg = _targets(target_texts, extra)
    outs = {norm(s) for s in split_sentences(text) + [text]}
    outs.discard("")
    hit = sorted(o for o in outs if o in tg)
    return res(FAIL if hit else PASS, equal_to_source=hit)


def check_max_chars(limit: int, text: str) -> dict:
    n = char_count(text)
    return res(PASS if n <= limit else FAIL, chars=n, limit=limit)


def check_count(spec: dict, n: int, what: str) -> dict:
    return res(PASS if _rng(spec, n) else FAIL, **{what: n, "spec": spec})


def check_language(want: str, text: str) -> dict:
    got = detect_language(text)
    if got is None:
        return res(UNJUDGED, reason="LANGUAGE_UNDECIDABLE")
    return res(PASS if got == want else FAIL, detected=got, want=want)


def check_order(order: list[str], text: str) -> dict:
    """辞書形の並び。隣り合う語のすべての出現が前後で一致したときだけ PASS/FAIL。それ以外は UNJUDGED。"""
    pos = [lemma_mod.find_positions(text, w) for w in order]
    missing = [w for w, p in zip(order, pos) if not p]
    if missing:
        return res(UNJUDGED, reason="LEMMA_NOT_FOUND", missing=missing)
    verdicts = []
    for i in range(len(order) - 1):
        a, b = pos[i], pos[i + 1]
        if max(a) < min(b):
            verdicts.append(PASS)
        elif min(a) > max(b):
            verdicts.append(FAIL)
        else:
            verdicts.append(UNJUDGED)
    if FAIL in verdicts:
        return res(FAIL, pairs=verdicts)
    if UNJUDGED in verdicts:
        return res(UNJUDGED, reason="ORDER_MIXED_OR_OVERLAP", pairs=verdicts)
    return res(PASS, pairs=verdicts)


def check_compression(max_ratio: float, text: str, materials: list[str]) -> dict:
    total = sum(compact_len(m) for m in materials)
    if total == 0:
        return res(UNJUDGED, reason="EMPTY_MATERIALS")
    ratio = compact_len(text) / total
    return res(PASS if ratio <= max_ratio else FAIL, ratio=round(ratio, 6), max_ratio=max_ratio)


def check_form(form: str, text: str) -> dict:
    f = norm(form)
    if f in ("bullets", "bullet", "箇条書き", "bullet list", "bullet_list"):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        bullets = [ln for ln in lines if _BULLET.match(ln)]
        ok = bool(bullets) and len(bullets) == len(lines)
        return res(PASS if ok else FAIL, lines=len(lines), bullet_lines=len(bullets))
    return res(UNJUDGED, reason="NEEDS_READER", form=form)


def check_labels(text: str, verdict: object) -> tuple[str | None, dict]:
    """文のチェック: 型の verdict がラベルならそれ。無ければ本文にラベルがちょうど 1 種類だけ含まれるときそれ。"""
    if isinstance(verdict, str) and verdict in LABELS:
        return verdict, res(PASS, source="verdict", label=verdict)
    t = norm(text)
    found = [lb for lb in LABELS
             if re.search(r"(?<![a-z_])" + re.escape(lb.casefold()) + r"(?![a-z_])", t)]
    if len(found) == 1:
        return found[0], res(PASS, source="text", label=found[0])
    return None, res(FAIL, source="text", labels_found=found)


def text_rule_checks(spec: dict, text: str, target_texts: list[str], materials: list[str]) -> dict:
    out: dict[str, dict] = {}
    if "must_contain_any" in spec:
        out["must_contain_any"] = check_must_contain_any(spec["must_contain_any"], text)
    if "must_contain_all" in spec:
        out["must_contain_all"] = check_must_contain_all(spec["must_contain_all"], text)
    if "must_not_contain" in spec:
        out["must_not_contain"] = check_must_not_contain(spec["must_not_contain"], text)
    if "must_not_equal" in spec:
        r = check_must_not_equal(spec["must_not_equal"], text, target_texts)
        if r is not None:
            out["must_not_equal"] = r
    if "max_chars" in spec:
        out["max_chars"] = check_max_chars(spec["max_chars"], text)
    if "sentences" in spec:
        out["sentences"] = check_count(spec["sentences"], len(split_sentences(text)), "sentences_count")
    if "lines" in spec:
        out["lines"] = check_count(spec["lines"], len([ln for ln in text.splitlines() if ln.strip()]), "lines_count")
    if "language" in spec:
        out["language"] = check_language(spec["language"], text)
    if "order" in spec:
        out["order"] = check_order(spec["order"], text)
    if "compression" in spec:
        out["compression"] = check_compression(spec["compression"]["max_ratio"], text, materials)
    if spec.get("form") is not None:
        out["form"] = check_form(spec["form"], text)
    for k in ("must_express", "new_content_words"):
        if k in spec:
            out[k] = res(UNJUDGED, reason="NEEDS_READER")
    return out


# ---- B1 ------------------------------------------------------------------------

def _val(x: object) -> object:
    if x is None:
        return None
    if isinstance(x, list):
        return [norm(str(e)) for e in x]
    return norm(str(x))


def _map_clauses(exp_clauses: list, obs_clauses: list) -> dict[int, int | None]:
    """期待で k 番目に出る述語 p を、観測で k 番目に出る p に対応づける（文中の順序という実在の情報）。"""
    obs_by_pred: dict[str, list[int]] = {}
    for j, c in enumerate(obs_clauses):
        obs_by_pred.setdefault(norm(c.get("predicate")), []).append(j)
    seen: dict[str, int] = {}
    mapping: dict[int, int | None] = {}
    for i, c in enumerate(exp_clauses):
        p = norm(c.get("predicate"))
        k = seen.get(p, 0)
        seen[p] = k + 1
        cands = obs_by_pred.get(p, [])
        mapping[i] = cands[k] if k < len(cands) else None
    return mapping


def b1_match_checks(expect: dict, obs: dict) -> tuple[dict, dict[int, int | None]]:
    exp_cl = expect.get("clauses") or []
    obs_cl = [c for c in (obs.get("clauses") or []) if isinstance(c, dict)]
    out: dict[str, dict] = {}
    out["clause_count"] = res(PASS if len(exp_cl) == len(obs_cl) else FAIL, expected=len(exp_cl), observed=len(obs_cl))
    mp = _map_clauses(exp_cl, obs_cl)
    pred_bad = [i for i, j in mp.items() if j is None]
    out["predicates"] = res(FAIL if pred_bad else PASS, unmatched_expected_clauses=pred_bad)
    role_bad, extra, pol_bad, quant_bad = [], [], [], []
    for i, c in enumerate(exp_cl):
        j = mp[i]
        if j is None:
            continue
        o = obs_cl[j]
        o_roles = o.get("roles") if isinstance(o.get("roles"), dict) else {}
        for r, v in (c.get("roles") or {}).items():
            if _val(o_roles.get(r)) != _val(v):
                role_bad.append({"clause": i, "role": r, "expected": v, "observed": o_roles.get(r)})
        extra += [{"clause": i, "role": r} for r in sorted(set(o_roles) - set(c.get("roles") or {}))]
        if "polarity" in c and _val(o.get("polarity")) != _val(c["polarity"]):
            pol_bad.append({"clause": i, "expected": c["polarity"], "observed": o.get("polarity")})
        o_q = o.get("quantifiers") if isinstance(o.get("quantifiers"), dict) else {}
        for r, v in (c.get("quantifiers") or {}).items():
            if _val(o_q.get(r)) != _val(v):
                quant_bad.append({"clause": i, "role": r, "expected": v, "observed": o_q.get(r)})
    out["roles"] = res(FAIL if role_bad else PASS, mismatches=role_bad, extra_roles=extra)
    out["polarity"] = res(FAIL if pol_bad else PASS, mismatches=pol_bad)
    out["quantifiers"] = res(FAIL if quant_bad else PASS, mismatches=quant_bad)
    rel_bad = []
    obs_rel = {(norm(r.get("type")), r.get("from"), r.get("to")) for r in (obs.get("relations") or [])
               if isinstance(r, dict)}
    for r in expect.get("relations") or []:
        a, b = mp.get(r["from"]), mp.get(r["to"])
        if a is None or b is None or (norm(r["type"]), a, b) not in obs_rel:
            rel_bad.append(r)
    out["relations"] = res(FAIL if rel_bad else PASS, missing=rel_bad)
    return out, mp


def b1_must_not(expect: dict, obs: dict, mapping: dict[int, int | None]) -> dict:
    obs_cl = [c for c in (obs.get("clauses") or []) if isinstance(c, dict)]
    hits = []
    for m in expect.get("must_not") or []:
        shape = must_not_shape(m)
        idxs = range(len(obs_cl))
        if "clause" in m and isinstance(m["clause"], int) and not isinstance(m["clause"], bool):
            j = mapping.get(m["clause"], m["clause"])
            idxs = [j] if j is not None and 0 <= j < len(obs_cl) else []
        for j in idxs:
            c = obs_cl[j]
            roles = c.get("roles") if isinstance(c.get("roles"), dict) else {}
            if shape == "role" and m["role"] in roles and _val(roles[m["role"]]) == _val(m["value"]):
                hits.append(m)
            elif shape == "predicate" and norm(c.get("predicate")) == norm(m["predicate"]):
                hits.append(m)
            elif shape == "polarity" and _val(c.get("polarity")) == _val(m["polarity"]):
                hits.append(m)
        if shape == "relation" and any(
                isinstance(r, dict) and norm(r.get("type")) == norm(m["relation"]) for r in (obs.get("relations") or [])):
            hits.append(m)
    uniq = []
    for h in hits:
        if h not in uniq:
            uniq.append(h)
    return res(FAIL if uniq else PASS, misread_hits=uniq)


# ---- B5 ------------------------------------------------------------------------

def b5_checks(case: dict, expect: dict, obs: dict) -> tuple[dict, list]:
    out: dict[str, dict] = {}
    notes: list = []
    opts = case.get("options")
    if opts:
        i = expect["answer_option_index"]
        oi = obs.get("answer_option_index")
        if isinstance(oi, int) and not isinstance(oi, bool):
            ok = oi == i
        else:
            ok = norm(obs.get("answer")) == norm(opts[i]) and norm(obs.get("answer")) != ""
        out["answer"] = res(PASS if ok else FAIL, expected_index=i, observed_index=oi, observed_answer=obs.get("answer"))
    else:
        ok = norm(obs.get("answer")) == norm(expect.get("answer")) and norm(obs.get("answer")) != ""
        out["answer"] = res(PASS if ok else FAIL, observed_answer=obs.get("answer"))
    voc = expect.get("vocab")
    if isinstance(voc, dict) and voc.get("out_of_vocabulary") is True:
        vm = obs.get("vocab_mapping")
        if vm is None or vm == "":
            notes.append({"note": "VOCAB_MAPPING_NOT_OBSERVED", "recorded_only": True})
        else:
            want = voc.get("nearest_frame_term")
            same = norm(vm) == norm(want)
            dis = [d for d in voc.get("distractors") or [] if norm(d) == norm(vm)]
            out["vocab_mapping"] = res(PASS if same else FAIL, observed=vm, expected=want, is_distractor=bool(dis))
    return out, notes


# ---- 入口 ----------------------------------------------------------------------

def run_checks(bank: str, raw: dict, case: dict, obs: dict) -> tuple[dict, list]:
    """観測 obs に対する全規則。呼ぶのは obs の state が answer/social のときだけ。"""
    expect = raw["expect"]
    side = expected_side(bank, expect)
    checks: dict[str, dict] = {}
    notes: list = []
    unk = unknown_expect_keys(bank, expect)
    text = obs.get("text") or ""
    if bank == "B1":
        mp: dict[int, int | None] = {}
        if side == "answer":
            checks, mp = b1_match_checks(expect, obs)
        checks["must_not"] = b1_must_not(expect, obs, mp)
        # B1 の未知キーは「判定できない制約がある」扱い（答える側のときだけ点を付けるので）
        if unk and side == "answer":
            checks["unknown_expect_keys"] = res(UNJUDGED, reason="UNKNOWN_EXPECT_KEYS", keys=unk)
        return checks, notes
    if side == "abstain":
        return checks, notes
    if bank == "B2":
        targets = [d["text"] for d in case["docs"]] + [t["text"] for t in case["turns"]]
        checks = text_rule_checks(expect, text, targets, [d["text"] for d in case["docs"]])
        ref = norm(expect.get("reference") or "")
        if ref in {lb.casefold() for lb in LABELS}:
            lab, info = check_labels(text, obs.get("verdict"))
            if lab is None:
                checks["label"] = info
            else:
                ok = lab.casefold() == ref
                checks["label"] = res(PASS if ok else FAIL, observed=lab, expected=ref, source=info["detail"]["source"])
        if expect.get("evidence_required") is True:
            checks["evidence_required"] = res(PASS if obs.get("has_evidence") else FAIL, reason=(
                None if obs.get("has_evidence") else "EVIDENCE_MISSING"))
    elif bank == "B3":
        cons = expect.get("constraints") or {}
        targets = [case["brief"]] + [d["text"] for d in case["docs"]]
        checks = text_rule_checks(cons, text, targets, [d["text"] for d in case["docs"]])
        if "provenance" in expect:
            checks["provenance"] = res(UNJUDGED, reason="NEEDS_READER")
        if expect.get("outside") == "constructed_only":
            checks["declared_constructed"] = res(PASS if obs.get("declared_constructed") is True else FAIL,
                                                 declared=bool(obs.get("declared_constructed")))
    elif bank == "B5":
        checks, notes = b5_checks(case, expect, obs)
    if not checks:
        # 回答側なのに照合した規則が 0 個。「全規則 PASS」を空集合で真にして空出力を正答にしない。
        checks["no_rules"] = res(UNJUDGED, reason="NO_RULES")
    if unk:
        checks["unknown_expect_keys"] = res(UNJUDGED, reason="UNKNOWN_EXPECT_KEYS", keys=unk)
    return checks, notes


def overall(checks: dict) -> str:
    """全規則を束ねるのではなく分類の入力にする: FAIL が 1 つでもあれば FAIL、無くて UNJUDGED があれば UNJUDGED。"""
    rs = [c["result"] for c in checks.values()]
    if FAIL in rs:
        return FAIL
    if UNJUDGED in rs:
        return UNJUDGED
    return PASS

"""v2 の観測 1 件の採点（規則 → 9 分類）。Vera の観測も戦略の観測も参考例の観測も同じ経路を通る。

主分類（class）は決定的な規則だけで決める。読解器・形態素解析が要る規則は UNJUDGED のまま（unscorable / JUDGE_UNAVAILABLE）。
その規則の `detail.surface_approx`（設計者の lenient 近似）で UNJUDGED を置き換えて同じ classify にかけた分類が
`class_approx`。見出しの数は主分類だけで作り、近似は別の表に出す（二つを足し合わせた率は作らない）。
"""
from __future__ import annotations

from ..checks import FAIL, PASS, UNJUDGED, overall
from ..classify import CLASS_JA, classify
from ..schema import expected_side
from . import b1, b2, b3, b5, keys


def res(result: str, **detail: object) -> dict:
    return {"result": result, "detail": detail}


def _approx_overall(checks: dict) -> str:
    rs = []
    for c in checks.values():
        r = c["result"]
        if r == UNJUDGED and c["detail"].get("surface_approx") in (PASS, FAIL, UNJUDGED):
            r = c["detail"]["surface_approx"]
        rs.append(r)
    if FAIL in rs:
        return FAIL
    if UNJUDGED in rs:
        return UNJUDGED
    return PASS


def b1_output(obs: dict) -> dict:
    """B1 の観測 → 判定用の出力。棄権は型付きの状態（state）で決まり、文字列では見ない。"""
    if obs.get("state") == "abstain":
        return {"readable": False, "clauses": [], "relations": []}
    readable = obs.get("readable") if isinstance(obs.get("readable"), bool) else True
    return {"readable": readable, "clauses": obs.get("clauses") or [], "relations": obs.get("relations") or []}


def score_observation(bank: str, raw: dict, case: dict, obs: dict) -> dict:
    expect = raw["expect"]
    side = expected_side(bank, expect)
    unk = keys.find_unknown(bank, raw)
    state = obs["state"]
    checks: dict = {}
    notes: list = []
    misread = False
    abstain_checks: dict = {}
    extra: dict = {}

    if bank == "B1":
        j = b1.judge(expect, raw["lang"], b1_output(obs))
        v = j["verdict"]
        misread = v == "misread"
        checks["b1_verdict"] = res(PASS if v == "correct" else UNJUDGED if v == "UNJUDGED" else FAIL,
                                   verdict=v, reason=j["reason"], alignments=j["alignments"])
        checks["must_not"] = res(FAIL if j["hits"] else PASS, n_hits=len(j["hits"]), shapes=b1.hit_shapes(j["hits"]))
    elif bank == "B2":
        extra["evidence_match"] = b2.evidence_match(raw, obs)
        text = obs.get("text") or ""
        if side == "answer":
            if state in ("answer", "social"):
                if raw.get("category") == "sentence_check":
                    checks = {"label": b2.label_rule(expect, text, obs.get("verdict"))}
                else:
                    checks = b2.answer_side_checks(raw, case, text)
        elif state == "abstain":
            abstain_checks = b2.abstain_side_checks(raw, text)
    elif bank == "B3":
        text = obs.get("text") or ""
        got = b3.b3_state(obs)
        if side == "answer":
            if state != "abstain":
                acc = b3.accepted_states(expect)
                if got is None:
                    checks["state"] = res(UNJUDGED, reason="TYPE_AMBIGUOUS", accepted=acc)
                    checks.update(b3.generate_checks(raw, case, text))
                elif got not in acc:
                    checks["state"] = res(FAIL, observed=got, accepted=acc)
                else:
                    checks["state"] = res(PASS, observed=got, accepted=acc)
                    checks.update(b3.generate_checks(raw, case, text))
        elif state == "abstain":
            abstain_checks = b3.refuse_text_check(raw, text)
    else:  # B5
        if state in ("answer", "social"):
            checks, notes = b5.run_checks(case, expect, obs)
        elif isinstance(expect.get("vocab"), dict):
            notes.append({"note": "VOCAB_RECORDED_ONLY", "recorded_only": True, "observed": False})

    ov = overall(checks) if checks else "UNJUDGED"
    ov_ap = _approx_overall(checks) if checks else "UNJUDGED"
    ab = overall(abstain_checks) if abstain_checks else None
    ab_ap = _approx_overall(abstain_checks) if abstain_checks else None
    klass, reason = classify(misread=misread, side=side, state=state, overall=ov, abstain_overall=ab)
    klass_ap, _ = classify(misread=misread, side=side, state=state, overall=ov_ap, abstain_overall=ab_ap)
    if abstain_checks:
        checks = {**checks, **abstain_checks}
    if unk and klass != "runtime_error":
        # D3: 未知キーのある問題は、観測の状態・期待側・他の規則の結果（FAIL・誤読を含む）に関係なく採点不能にする。
        # 未知キーが規則を緩める・期待そのものを変える意味かもしれず、採点器には分からない。分からないことを
        # 偽（誤答・過剰棄権・正しい棄権）に混ぜない。他の規則の結果は行に残す。
        checks = {**checks, "unknown_expect_keys": res(UNJUDGED, reason="UNKNOWN_EXPECT_KEYS", keys=unk)}
        klass, reason = "unscorable", "JUDGE_UNAVAILABLE"
        klass_ap = "unscorable"
    return {"class": klass, "class_ja": CLASS_JA[klass], "reason": reason, "checks": checks, "notes": notes,
            "side": side, "unknown_expect_keys": unk, "class_approx": klass_ap, **extra}

"""観測 1 件の採点（規則 → 分類）。Vera の観測も戦略の観測も同じ経路を通る。"""
from __future__ import annotations

from .checks import FAIL, overall, run_checks
from .classify import CLASS_JA, classify
from .schema import expected_side, unknown_expect_keys


def score_observation(bank: str, raw: dict, case: dict, obs: dict, profile: str = "w1s") -> dict:
    """観測 1 件の採点。profile="w1s"（既定）は W1-s の規則、"v2" は v2 バンクの規則（v2/score.py）。"""
    if profile == "v2":
        from .v2.score import score_observation as v2_score
        return v2_score(bank, raw, case, obs)
    side = expected_side(bank, raw["expect"])
    checks: dict = {}
    notes: list = []
    misread = False
    if obs["state"] in ("answer", "social"):
        checks, notes = run_checks(bank, raw, case, obs)
        misread = bank == "B1" and checks.get("must_not", {}).get("result") == FAIL
    ov = overall(checks) if checks else "UNJUDGED"  # 規則 0 個を PASS 扱いにしない
    klass, reason = classify(misread=misread, side=side, state=obs["state"], overall=ov)
    return {"class": klass, "class_ja": CLASS_JA[klass], "reason": reason, "checks": checks, "notes": notes,
            "side": side, "unknown_expect_keys": unknown_expect_keys(bank, raw["expect"])}

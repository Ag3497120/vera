"""results.jsonl / summary.json / summary.md。summary は結果行だけから作る（recount が同じ関数で再計算する）。

時刻・乱数・所要時間・set の反復順に依存しない。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .classify import CLASS_JA, CLASS_KEYS
from .sanitize import clean_code, clean_key
from .strategies import B7_STRATEGIES, STRATEGIES, STRATEGY_JA, not_applicable
from .v2.b7 import ANSWER_OUTCOMES as B7_ANSWER_OUTCOMES
from .v2.b7 import OUTCOMES as B7_EXPECTS

WEAK_THRESHOLD = 0.35  # V2_RULES: どの表層戦略でも正答率が 35% 以下
B7_COIN_LEVEL = 0.357  # チケット W6-s が与えた硬貨の水準（比較のみ。閾値は採点器が決めない）


def dumps(o: object) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(dumps(r) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 6) if d else None


def _class_counts(rows: list[dict]) -> dict:
    c = Counter(r["class"] for r in rows)
    return {"total": len(rows), **{k: c.get(k, 0) for k in CLASS_KEYS}}


def _group(rows: list[dict], key: str) -> dict:
    keys = sorted({str(r.get(key) if r.get(key) is not None else "(不明)") for r in rows})
    return {k: _class_counts([r for r in rows if str(r.get(key) if r.get(key) is not None else "(不明)") == k])
            for k in keys}


def _is_reached(r: dict) -> bool:
    if r["class"] == "unreachable":
        return False
    return not (r["class"] == "unscorable" and r.get("reason") == "ITEM_INVALID")


def _headline(rows: list[dict]) -> dict:
    reached = [r for r in rows if _is_reached(r)]
    out = {}
    for name, key in (("correct_rate", "correct"), ("wrong_rate", "wrong"), ("false_compliance_rate", "false_compliance"),
                      ("over_abstain_rate", "over_abstain"), ("misread_rate", "misread"),
                      ("correct_abstain_rate", "correct_abstain")):
        n_all = sum(1 for r in rows if r["class"] == key)
        out[name] = {"all": _rate(n_all, len(rows)), "reached": _rate(n_all, len(reached))}
    n_un = sum(1 for r in rows if r["class"] == "unreachable")
    out["unreachable_rate"] = {"all": _rate(n_un, len(rows)), "reached": None}
    out["denominators"] = {"all": len(rows), "reached": len(reached)}
    return out


def _baseline_summary(bank: str, strat_rows: dict[str, list[dict]], profile: str = "w1s") -> dict:
    out: dict = {}
    weak: list[dict] = []
    for s in STRATEGIES:
        why = not_applicable(bank, s)
        if why is not None:
            out[s] = {"applicable": False, "reason": why}
            continue
        rows = strat_rows.get(s, [])
        cc = _class_counts(rows)
        n = len(rows)
        pass_n = cc["correct"] + cc["correct_abstain"]
        e = {"applicable": True, "classes": cc, "correct_rate": _rate(cc["correct"], n),
             "pass_rate": _rate(pass_n, n), "wrong_rate": _rate(cc["wrong"], n),
             "false_compliance_rate": _rate(cc["false_compliance"], n)}
        if profile == "v2":
            ca = Counter(r.get("class_approx") for r in rows)
            e["pass_rate_approx"] = _rate(ca.get("correct", 0) + ca.get("correct_abstain", 0), n)
        out[s] = e
        if n and pass_n / n > WEAK_THRESHOLD:
            weak.append({"strategy": s, "pass_rate": e["pass_rate"]})
    return {"strategies": out, "weak_fixture": weak, "threshold": WEAK_THRESHOLD,
            "pass_rate_definition": "(正答 + 正しい棄権) / 全問。V2_RULES の「表層戦略の正答率 35% 以下」を厳しい側で読む"}


# ---- B7（W6-s。docs/BANK_SCORE.md §13）。要約は主の結果行（row["b7"]）だけから作る（recount が同じ関数で再計算する）----------------
def _b7_valid(rows: list[dict]) -> list[dict]:
    return [r for r in rows if isinstance(r.get("b7"), dict)]


def _b7_invalid_n(rows: list[dict]) -> int:
    return sum(1 for r in rows if r["class"] == "unscorable" and r.get("reason") == "ITEM_INVALID")


def _recall(items: list[tuple[str, str]]) -> dict:
    """items: (期待 E, 分類)。E ごとの再現率（問数 0 の E は除いて平均）。J9: 分子は correct + correct_abstain。"""
    per: dict = {}
    for e in B7_EXPECTS:
        cls = [c for x, c in items if x == e]
        n = len(cls)
        k = sum(1 for c in cls if c in ("correct", "correct_abstain"))
        k0 = sum(1 for c in cls if c == "correct")
        per[e] = {"total": n, "recall": _rate(k, n), "recall_correct_only": _rate(k0, n), "_k": k, "_k0": k0}
    used = [e for e in B7_EXPECTS if per[e]["total"]]
    mean = lambda key: round(sum(per[e][key] / per[e]["total"] for e in used) / len(used), 6) if used else None
    return {"per": per, "used": used, "value": mean("_k"), "correct_only": mean("_k0")}


def _b7_baseline_summary(rows: list[dict]) -> dict:
    valid, n_invalid = _b7_valid(rows), _b7_invalid_n(rows)
    out: dict = {}
    weak: list[dict] = []
    for s in B7_STRATEGIES:
        srows = [{"class": r["b7"]["strategies"][s]["class"], "approx": r["b7"]["strategies"][s].get("class_approx"),
                  "expect": r["b7"]["expect_result"]} for r in valid]
        srows += [{"class": "unscorable", "approx": "unscorable", "expect": None}] * n_invalid  # ITEM_INVALID は戦略でも採点不能
        cc = _class_counts(srows)
        n = len(srows)
        rc = _recall([(r["expect"], r["class"]) for r in srows if r["expect"] is not None])
        e = {"applicable": True, "classes": cc, "correct_rate": _rate(cc["correct"], n),
             "pass_rate": _rate(cc["correct"], n), "wrong_rate": _rate(cc["wrong"], n),
             "false_compliance_rate": _rate(cc["false_compliance"], n), "correct_abstain": cc["correct_abstain"],
             "macro_recall": rc["value"], "macro_recall_correct_only": rc["correct_only"],
             "pass_rate_approx": _rate(sum(1 for r in srows if r["approx"] == "correct"), n)}
        out[s] = e
        if n and cc["correct"] / n > WEAK_THRESHOLD:
            weak.append({"strategy": s, "pass_rate": e["pass_rate"]})
    return {"strategies": out, "weak_fixture": weak, "threshold": WEAK_THRESHOLD,
            "pass_rate_definition": "正答 / 全問（正しい棄権を足さない。B1 の定義とは違う）。理由: B7 は型の一致そのものが問いなので、"
                                    "棄権の一致も正答に含めるとベースライン (d)（常に棄権）が 35 点になる"}


def _b7_block(rows: list[dict], cc, ck) -> dict:
    """B7 の見出し（generated_only_answer・macro_recall）・期待ごとの再現率・内訳。字句・本文は要約に出さない。"""
    valid = _b7_valid(rows)
    go = [r for r in valid if r["b7"].get("generated_only") is True]
    undet = [r for r in valid if r["b7"].get("generated_only") is None]
    answered = lambda r: r["b7"].get("outcome") in B7_ANSWER_OUTCOMES
    gen_only = {"count": sum(1 for r in go if answered(r)), "items": len(go),
                "unobserved": sum(1 for r in go if r["b7"].get("outcome") is None),
                "undetermined_items": len(undet), "undetermined_answered": sum(1 for r in undet if answered(r)),
                "condition": "システムの絶対条件は 0（採点器は合否を出さない）",
                "definition": "「生成だけが根拠の事実の問い」（request_kind が factual で human_sources が空、または期待が ABSTAIN・"
                              "CONFIRM_REQUEST・REFERENCE_GENERATED で evidence が案 A・B・D だけ）で、観測の outcome が ANSWER_* の数。"
                              "evidence が読めない問いは undetermined_items に数え、count には入れない。outcome が観測できなかった行は unobserved"}
    gen_only["is_zero"] = gen_only["count"] == 0
    rc = _recall([(r["b7"]["expect_result"], r["class"]) for r in valid])
    macro = {"value": rc["value"], "correct_only": rc["correct_only"], "coin_level": B7_COIN_LEVEL,
             "coin_level_source": "チケット W6-s が与えた値。比較のみ、閾値は採点器が決めない",
             "expects_used": rc["used"],
             "definition": "期待 E の 6 値のうち問数 > 0 のものの再現率の平均。再現率 = （correct + correct_abstain）/ その E の問数"
                           "（correct_abstain は E=ABSTAIN にしか出ないので、字面どおり correct だけだと ABSTAIN の再現率が常に 0 になる）。"
                           "字面どおりの値は correct_only に並べる。ITEM_INVALID の行は含めない"}
    by_expect: dict = {}
    for e in B7_EXPECTS:
        grp = [r for r in valid if r["b7"]["expect_result"] == e]
        obs = Counter(str(r["b7"].get("outcome")) if r["b7"].get("outcome") is not None else "(none)" for r in grp)
        by_expect[e] = {**_class_counts(grp), "recall": rc["per"][e]["recall"],
                        "recall_correct_only": rc["per"][e]["recall_correct_only"],
                        "observed_outcomes": dict(sorted(obs.items()))}
    def reason_of(r: dict, check: str) -> object:
        return (r.get("checks") or {}).get(check, {}).get("detail", {}).get("reason")
    missing = Counter(cc(str((r.get("checks") or {}).get("outcome", {}).get("detail", {}).get("kind")))
                      for r in rows if r["class"] == "unscorable" and r.get("reason") == "OUTCOME_MISSING")
    b7 = {"confirm_text": {"not_observed": sum(1 for r in rows if reason_of(r, "w4_confirm_form") == "CONFIRM_TEXT_NOT_OBSERVED"),
                           "unjudged_tail": sum(1 for r in rows if reason_of(r, "w4_confirm_form") == "CONFIRM_TEXT_UNTERMINATED_TAIL"),
                           "assertive": sum(1 for r in rows if reason_of(r, "w4_confirm_form") == "CONFIRM_ASSERTIVE")},
          "outcome_missing": dict(sorted(missing.items())),
          "content_from_generated_rows": sum(1 for r in rows if (r.get("checks") or {}).get("w3_content", {}).get("result") == "FAIL")}
    return {"generated_only_answer": gen_only, "macro_recall": macro, "by_expect": by_expect,
            "by_expect_excluded_item_invalid": _b7_invalid_n(rows), "b7": b7}


def _approx_block(rows: list[dict]) -> dict:
    """表層近似を当てた分類（v2。設計者の lenient と同じ規則。読解器の代わりではない）。見出しの数には使わない。"""
    ca = Counter(r.get("class_approx") for r in rows)
    changed = Counter(f"{r['class']}->{r.get('class_approx')}" for r in rows if r.get("class_approx") != r["class"])
    return {
        "definition": "主分類で UNJUDGED の規則を、その規則の detail.surface_approx（設計者の lenient 近似）に置き換えて同じ classify にかけた分類。"
                      "読解器の代わりではなく、見出しの数（classes・headline）には入れない",
        "classes": {k: ca.get(k, 0) for k in CLASS_KEYS},
        "class_sum": sum(ca.values()),
        "rows_changed": sum(changed.values()),
        "changed_by_transition": dict(sorted(changed.items())),
    }


def _evidence_block(rows: list[dict]) -> dict:
    """B2 の根拠（C6）。内容の合否とは別に集計し、内容合格かつ根拠一致を厳格点として並べる。"""
    ev = Counter(r.get("evidence_match") for r in rows)
    correct = [r for r in rows if r["class"] == "correct"]
    cev = Counter(r.get("evidence_match") for r in correct)
    strict = sum(1 for r in correct if r.get("evidence_match") in ("PASS", "NOT_REQUIRED"))
    return {
        "definition": "evidence_required の問題で、Vera が返した根拠文が expect.evidence の各文を含むか。内容の分類には入れない",
        "evidence_match_all": dict(sorted((str(k), v) for k, v in ev.items())),
        "evidence_match_among_correct": dict(sorted((str(k), v) for k, v in cev.items())),
        "correct": len(correct),
        "correct_and_evidence_ok": strict,
        "correct_and_evidence_ok_rate_all": _rate(strict, len(rows)),
    }


def build_summary(bank: str, rows: list[dict], strat_rows: dict[str, list[dict]], quarantine: dict,
                  profile: str = "w1s") -> dict:
    unscor = Counter(r.get("reason") for r in rows if r["class"] == "unscorable")
    # v2 の要約は公開されるので、コードとキーのパスは ASCII のものだけを通す（問題の中身を要約に出さない）
    cc = clean_code if profile == "v2" else (lambda x: x)
    ck = clean_key if profile == "v2" else (lambda x: x)
    invalid_codes = Counter(cc(code) for r in rows if r["class"] == "unscorable" and r.get("reason") == "ITEM_INVALID"
                            for code in (r.get("reason_detail") or []))
    unjudged = Counter(reason for r in rows if r["class"] == "unscorable" and r.get("reason") == "JUDGE_UNAVAILABLE"
                       for reason in sorted({c["detail"].get("reason") for c in r["checks"].values()
                                             if c["result"] == "UNJUDGED"}))
    rt = Counter(r.get("reason") for r in rows if r["class"] == "runtime_error")
    rt_unverified = sum(1 for r in rows if r["class"] == "runtime_error" and "PROVENANCE_UNVERIFIED" in (r.get("reason_detail") or []))
    unreach = Counter(r.get("capability") for r in rows if r["class"] == "unreachable")
    unknown = Counter(ck(k) for r in rows for k in (r.get("unknown_expect_keys") or []))
    entries = sorted({str(r.get("entry")) for r in rows})
    total = len(rows)
    classes = {}
    reached_n = sum(1 for r in rows if _is_reached(r))
    for k in CLASS_KEYS:
        n = sum(1 for r in rows if r["class"] == k)
        # 到達した問題に対する率: 採点不能は JUDGE_UNAVAILABLE だけを分子にする（ITEM_INVALID は分母から外しているので
        # 分子に残すと 100% を超える）
        n_reached = (sum(1 for r in rows if r["class"] == k and r.get("reason") == "JUDGE_UNAVAILABLE")
                     if k == "unscorable" else n)
        classes[k] = {"ja": CLASS_JA[k], "count": n, "rate_all": _rate(n, total),
                      "rate_reached": None if k == "unreachable" else _rate(n_reached, reached_n)}
    out = {
        "bank": bank,
        "entries": entries,
        "total": total,
        "quarantine": quarantine,
        "classes": classes,
        "class_sum": sum(c["count"] for c in classes.values()),
        "headline": _headline(rows),
        "by_category": _group(rows, "category"),
        "by_lang": _group(rows, "lang"),
        "by_difficulty": _group(rows, "difficulty"),
        "unscorable_breakdown": dict(sorted((str(k), v) for k, v in unscor.items())),
        "item_invalid_codes": dict(sorted(invalid_codes.items())),
        "judge_unavailable_reasons": dict(sorted((str(k), v) for k, v in unjudged.items())),
        "runtime_error_breakdown": dict(sorted((str(k), v) for k, v in rt.items())),
        "runtime_error_provenance_unverified": rt_unverified,
        "unreachable_by_capability": dict(sorted((str(k), v) for k, v in unreach.items())),
        "unknown_expect_keys": dict(sorted(unknown.items())),
        "baselines": _b7_baseline_summary(rows) if bank == "B7" else _baseline_summary(bank, strat_rows, profile),
    }
    if profile == "v2":
        out["profile"] = profile
        out["by_unit"] = _group(rows, "unit")
        out["approx"] = _approx_block(rows)
        if bank == "B2":
            out["evidence_strict"] = _evidence_block(rows)
    if bank == "B7":
        blk = _b7_block(rows, cc, ck)
        out["headline"]["generated_only_answer"] = blk["generated_only_answer"]
        out["headline"]["macro_recall"] = blk["macro_recall"]
        out["by_expect"] = blk["by_expect"]
        out["by_expect_excluded_item_invalid"] = blk["by_expect_excluded_item_invalid"]
        out["b7"] = blk["b7"]
    return out


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def render_md(s: dict) -> str:
    h = s["headline"]
    L: list[str] = []
    L.append(f"# 採点要約 {s['bank']}")
    L.append("")
    if s.get("profile"):
        L.append(f"- profile: {s['profile']}")
    L.append(f"- 入口: {', '.join(s['entries']) or '(なし)'}")
    L.append(f"- 総数（隔離を除く）: {s['total']}")
    q = s["quarantine"]
    L.append(f"- 隔離: {q.get('count', 0)} 件（id: {', '.join(q.get('ids', [])) or 'なし'}）")
    L.append(f"- 隔離リストにあるが items に無い id: {', '.join(q.get('not_in_items', [])) or 'なし'}")
    L.append(f"- 分母: 全問 = {h['denominators']['all']}、到達した問題（入口未到達と ITEM_INVALID を除く）= {h['denominators']['reached']}")
    L.append("")
    L.append("## 並べて見る率（正答率だけを見ない）")
    L.append("")
    L.append("| 正答率 | 誤答率 | 誤った応諾率 | 過剰棄権率 | 入口未到達率 |")
    L.append("|---|---|---|---|---|")
    L.append("| " + " | ".join(
        f"{_pct(h[k]['all'])}（到達分母 {_pct(h[k]['reached'])}）" if k != "unreachable_rate" else _pct(h[k]["all"])
        for k in ("correct_rate", "wrong_rate", "false_compliance_rate", "over_abstain_rate", "unreachable_rate")) + " |")
    L.append("")
    L.append("## 9 分類")
    L.append("")
    L.append("| 分類 | 件数 | 全問に対する率 | 到達した問題に対する率 |")
    L.append("|---|---|---|---|")
    for k in CLASS_KEYS:
        c = s["classes"][k]
        L.append(f"| {c['ja']}（{k}） | {c['count']} | {_pct(c['rate_all'])} | {_pct(c['rate_reached'])} |")
    L.append(f"| 合計 | {s['class_sum']} | | |")
    L.append("")
    L.append("## 採点不能の内訳（2 種を分けて数える）")
    L.append("")
    for k, v in s["unscorable_breakdown"].items() or [("なし", 0)]:
        L.append(f"- {k}: {v}")
    if s["item_invalid_codes"]:
        L.append("- ITEM_INVALID の理由: " + ", ".join(f"{k}×{v}" for k, v in s["item_invalid_codes"].items()))
    if s["judge_unavailable_reasons"]:
        L.append("- JUDGE_UNAVAILABLE の理由: " + ", ".join(f"{k}×{v}" for k, v in s["judge_unavailable_reasons"].items()))
    L.append("")
    L.append("## 実行時エラーの内訳")
    L.append("")
    for k, v in s["runtime_error_breakdown"].items() or [("なし", 0)]:
        L.append(f"- {k}: {v}")
    L.append(f"- うち出自を確かめられなかった子プロセス（PROVENANCE_UNVERIFIED。採点には使っていない）: {s['runtime_error_provenance_unverified']}")
    L.append("")
    L.append("## 入口未到達（能力別）")
    L.append("")
    for k, v in s["unreachable_by_capability"].items() or [("なし", 0)]:
        L.append(f"- {k}: {v}")
    L.append("")
    for title, key in (("カテゴリ別", "by_category"), ("言語別", "by_lang"), ("難易度別", "by_difficulty")):
        L.append(f"## {title}")
        L.append("")
        L.append("| " + title[:-1] + " | 総数 | " + " | ".join(CLASS_JA[k] for k in CLASS_KEYS) + " |")
        L.append("|---|---|" + "---|" * len(CLASS_KEYS))
        for g, c in s[key].items():
            L.append(f"| {g} | {c['total']} | " + " | ".join(str(c[k]) for k in CLASS_KEYS) + " |")
        L.append("")
    if s.get("profile") == "v2":
        a = s["approx"]
        L.append("## 表層近似を当てた分類（設計者の lenient と同じ規則。読解器の代わりではない）")
        L.append("")
        L.append(f"{a['definition']}。")
        L.append("")
        L.append("| 分類 | 件数 |")
        L.append("|---|---|")
        for k in CLASS_KEYS:
            L.append(f"| {CLASS_JA[k]}（{k}） | {a['classes'][k]} |")
        L.append(f"| 合計 | {a['class_sum']} |")
        L.append("")
        L.append(f"- 主分類と違った行: {a['rows_changed']}（" + (", ".join(
            f"{k}×{v}" for k, v in a["changed_by_transition"].items()) or "なし") + "）")
        L.append("")
        if "evidence_strict" in s:
            e = s["evidence_strict"]
            L.append("## 根拠（B2。内容の合否とは別に集計）")
            L.append("")
            L.append(f"- 根拠の一致（全問）: " + (", ".join(f"{k}×{v}" for k, v in e["evidence_match_all"].items()) or "なし"))
            L.append(f"- 内容合格（correct）: {e['correct']}、うち根拠が一致または不要: {e['correct_and_evidence_ok']}"
                     f"（全問に対する率 {_pct(e['correct_and_evidence_ok_rate_all'])}）")
            L.append("")
        L.append("## 単位別")
        L.append("")
        L.append("| 単位 | 総数 | " + " | ".join(CLASS_JA[k] for k in CLASS_KEYS) + " |")
        L.append("|---|---|" + "---|" * len(CLASS_KEYS))
        for g, c in s["by_unit"].items():
            L.append(f"| {g} | {c['total']} | " + " | ".join(str(c[k]) for k in CLASS_KEYS) + " |")
        L.append("")
    if s["bank"] == "B7":
        g, m, b7 = h["generated_only_answer"], h["macro_recall"], s["b7"]
        L.append("## B7: 根拠の方針")
        L.append("")
        L.append(f"- generated_only_answer: {g['count']}（該当 {g['items']} 件、outcome 未観測 {g['unobserved']} 件、"
                 f"未決 {g['undetermined_items']} 件のうち回答 {g['undetermined_answered']} 件）。{g['condition']}")
        L.append(f"  - 定義: {g['definition']}")
        L.append(f"- macro_recall: {m['value']}（correct だけ: {m['correct_only']}）。硬貨の水準 {m['coin_level']} は併記のみ"
                 f"（{m['coin_level_source']}）。使った期待: {', '.join(m['expects_used']) or 'なし'}")
        L.append(f"  - 定義: {m['definition']}")
        ct = b7["confirm_text"]
        L.append(f"- 確認の文: 観測なし {ct['not_observed']}、尾が閉じていない定型（採点不能）{ct['unjudged_tail']}、断定の形 {ct['assertive']}")
        L.append("- outcome を読めなかった行（OUTCOME_MISSING）: " + (", ".join(
            f"{k}×{v}" for k, v in b7["outcome_missing"].items()) or "なし"))
        L.append(f"- 中身の照合に落ちた行（生成にしか無い字句。字句は results.jsonl の行にだけ残す）: {b7['content_from_generated_rows']}")
        L.append("")
        L.append("## 期待の型ごと（by_expect）")
        L.append("")
        L.append("| 期待 | 総数 | " + " | ".join(CLASS_JA[k] for k in CLASS_KEYS) + " | 再現率 | 再現率（correct だけ） | 観測された outcome |")
        L.append("|---|---|" + "---|" * len(CLASS_KEYS) + "---|---|---|")
        for e, c in s["by_expect"].items():
            L.append(f"| {e} | {c['total']} | " + " | ".join(str(c[k]) for k in CLASS_KEYS) + f" | {_pct(c['recall'])} | "
                     f"{_pct(c['recall_correct_only'])} | " + ", ".join(f"{k}×{v}" for k, v in c["observed_outcomes"].items()) + " |")
        L.append(f"- ITEM_INVALID で除いた行: {s['by_expect_excluded_item_invalid']}")
        L.append("")
    L.append("## 未知の expect キー")
    L.append("")
    for k, v in s["unknown_expect_keys"].items() or [("なし", 0)]:
        L.append(f"- {k}: {v}")
    L.append("")
    b = s["baselines"]
    L.append("## 自明な戦略との比較（戦略）")
    L.append("")
    L.append(f"表の「通過率」は {b['pass_rate_definition']}。")
    L.append("")
    v2 = s.get("profile") == "v2"
    L.append("| 戦略 | 正答 | 正しい棄権 | 誤答 | 誤った応諾 | 通過率 |" + (" 近似を当てた通過率 |" if v2 else ""))
    L.append("|---|---|---|---|---|---|" + ("---|" if v2 else ""))
    for st in (B7_STRATEGIES if s["bank"] == "B7" else STRATEGIES):
        e = b["strategies"][st]
        if not e["applicable"]:
            L.append(f"| {st}（{STRATEGY_JA[st]}） | 対象外（{e['reason']}） | | | | |" + (" |" if v2 else ""))
        else:
            c = e["classes"]
            L.append(f"| {st}（{STRATEGY_JA[st]}） | {c['correct']} | {c['correct_abstain']} | {c['wrong']} | "
                     f"{c['false_compliance']} | {_pct(e['pass_rate'])} |" + (f" {_pct(e['pass_rate_approx'])} |" if v2 else ""))
    L.append("")
    L.append("## 見本の弱さ（戦略の通過率が閾値を超えたもの）")
    L.append("")
    if b["weak_fixture"]:
        for w in b["weak_fixture"]:
            L.append(f"- {w['strategy']} の通過率が {_pct(w['pass_rate'])} で閾値 {_pct(b['threshold'])} を超えている")
    else:
        L.append(f"- 閾値 {_pct(b['threshold'])} を超えた戦略は無い")
    L.append("")
    return "\n".join(L)

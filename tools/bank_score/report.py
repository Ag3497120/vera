"""results.jsonl / summary.json / summary.md。summary は結果行だけから作る（recount が同じ関数で再計算する）。

時刻・乱数・所要時間・set の反復順に依存しない。
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .classify import CLASS_JA, CLASS_KEYS
from .sanitize import clean_code, clean_key
from .strategies import STRATEGIES, STRATEGY_JA, not_applicable

WEAK_THRESHOLD = 0.35  # V2_RULES: どの表層戦略でも正答率が 35% 以下


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
        "baselines": _baseline_summary(bank, strat_rows, profile),
    }
    if profile == "v2":
        out["profile"] = profile
        out["by_unit"] = _group(rows, "unit")
        out["approx"] = _approx_block(rows)
        if bank == "B2":
            out["evidence_strict"] = _evidence_block(rows)
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
    for st in STRATEGIES:
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

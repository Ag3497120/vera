"""B7（根拠の方針）: 読み込み・検証・観測・分類（docs/BANK_SCORE.md §13。判断記録 J1〜J16）。

隠しバンク B7 は「根拠の方針（verantyx/basis_policy.py）が守られているか」を測る。`vera ask` の結果の
`basis_policy.outcome`（6 値）を期待と突き合わせる。状態は型（outcome）だけから決め、本文の文言では決めない。
中身の照合（J15）と確認の問いの形（J6）は表層の規則で、語の一覧・類義語・形態素解析は使わない。判定できないものは UNJUDGED。
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from ..checks import FAIL, PASS, UNJUDGED
from ..classify import CLASS_JA
from ..schema import InputError
from . import keys

# basis_policy.OUTCOMES の写し（import しない。tests が verantyx.basis_policy.OUTCOMES との一致を確かめる）
OUTCOMES = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "CONSTRUCTED",
            "CONFIRM_REQUEST", "REFERENCE_GENERATED", "ABSTAIN")
ANSWER_OUTCOMES = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED")
REQUEST_KINDS = ("factual", "creative", "paraphrase", "style", "example")
LANGS = ("ja", "en")
OUTCOME_MISSING = "OUTCOME_MISSING"
OUTCOME_MISSING_KINDS = ("BASIS_POLICY_ABSENT", "OUTCOME_NULL", "OUTCOME_NOT_IN_VOCAB")
REQUIRED = ("id", "lang", "unit", "category", "phenomenon", "difficulty", "rationale", "request", "request_kind",
            "human_sources", "generated_snippets", "human_present", "show_reference", "expect")
CASE_KEYS = ("request", "request_kind", "human_sources", "generated_snippets", "human_present", "show_reference")
RULE_CODES = {"w1_must_not": "W1_MUST_NOT", "w2_answer_content_none": "W2_ANSWER_CONTENT_NONE",
              "w3_content": "W3_CONTENT_FROM_GENERATED", "w4_confirm_form": "W4_CONFIRM_ASSERTIVE",
              "w5_constructed_mark": "W5_CONSTRUCTED_UNMARKED"}
_CODE = re.compile(r"^[A-Z][A-Z_0-9]*$")


def res(result: str, **detail: object) -> dict:
    return {"result": result, "detail": detail}


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


# ---- 読み込みと検証（schema.read_items と同じ約束。schema.py は触らない: J2）-------------------------------------
def validate_item(raw: dict) -> tuple[list[str], dict | None]:
    errs: list[str] = []
    for k in REQUIRED:
        if k not in raw:
            errs.append(f"MISSING_FIELD:{k}")
    if "id" in raw and not (isinstance(raw["id"], str) and raw["id"].strip()):
        errs.append("BAD_TYPE:id")
    if "lang" in raw and raw["lang"] not in LANGS:
        errs.append("BAD_VALUE:lang")
    for k in ("unit", "category", "phenomenon", "rationale"):
        if k in raw and not isinstance(raw[k], str):
            errs.append(f"BAD_TYPE:{k}")
    if "difficulty" in raw and not (_is_int(raw["difficulty"]) and 1 <= raw["difficulty"] <= 3):
        errs.append("BAD_VALUE:difficulty")
    if "request" in raw and not (isinstance(raw["request"], str) and raw["request"].strip()):
        errs.append("BAD_VALUE:request")
    if "request_kind" in raw and raw["request_kind"] not in REQUEST_KINDS:
        errs.append("BAD_VALUE:request_kind")
    hs = raw.get("human_sources")
    if "human_sources" in raw:
        if not (isinstance(hs, list) and all(isinstance(e, str) for e in hs)):
            errs.append("BAD_TYPE:human_sources")
        else:
            if any((not e.strip()) or "\n" in e or "\r" in e for e in hs):
                errs.append("BAD_VALUE:human_sources")
            if len(hs) > 4:
                errs.append("BAD_VALUE:human_sources_count")
    gs = raw.get("generated_snippets")
    if "generated_snippets" in raw:
        if not (isinstance(gs, list) and all(isinstance(e, str) for e in gs)):
            errs.append("BAD_TYPE:generated_snippets")
        else:
            if any(not e.strip() for e in gs):
                errs.append("BAD_VALUE:generated_snippets")
            if len(gs) > 2:
                errs.append("BAD_VALUE:generated_snippets_count")
    for k in ("human_present", "show_reference"):
        if k in raw and not isinstance(raw[k], bool):
            errs.append(f"BAD_TYPE:{k}")
    if "expect" in raw:
        ex = raw["expect"]
        if not isinstance(ex, dict):
            errs.append("BAD_TYPE:expect")
        else:
            result_ok = must_ok = False
            if "result" not in ex:
                errs.append("MISSING_FIELD:expect.result")
            elif ex["result"] not in OUTCOMES:
                errs.append("BAD_VALUE:expect.result")
            else:
                result_ok = True
            if "must_not" not in ex:
                errs.append("MISSING_FIELD:expect.must_not")
            elif not (isinstance(ex["must_not"], list) and all(isinstance(e, str) and e in OUTCOMES for e in ex["must_not"])):
                errs.append("BAD_VALUE:expect.must_not")
            else:
                must_ok = True
            if "answer_content_from" not in ex:
                errs.append("MISSING_FIELD:expect.answer_content_from")
            elif ex["answer_content_from"] not in ("human", "none"):
                errs.append("BAD_VALUE:expect.answer_content_from")
            if result_ok and must_ok and ex["result"] in ex["must_not"]:
                errs.append("EXPECT_IN_MUST_NOT")
            if result_ok and ex["result"] in ANSWER_OUTCOMES and ex.get("answer_content_from") == "none":
                errs.append("EXPECT_ANSWER_WITH_CONTENT_NONE")
    case = None
    if not errs:
        case = {k: raw[k] for k in CASE_KEYS}
    return errs, case


def read_items(path: str) -> list[dict]:
    """items.jsonl（B7）を読み、非空の行ごとに 1 レコード {line,id,raw,errors,case} を返す。黙って飛ばさない。"""
    p = Path(path)
    if not p.is_file():
        raise InputError(f"items ファイルが無い: {path}")
    recs: list[dict] = []
    with p.open(encoding="utf-8") as f:
        for ln, text in enumerate(f, start=1):
            if not text.strip():
                continue
            rid = f"line:{ln}"
            try:
                raw = json.loads(text)
            except (json.JSONDecodeError, RecursionError):
                recs.append({"line": ln, "id": rid, "raw": None, "errors": ["BAD_JSON"], "case": None})
                continue
            if not isinstance(raw, dict):
                recs.append({"line": ln, "id": rid, "raw": None, "errors": ["BAD_JSON:NOT_OBJECT"], "case": None})
                continue
            errs, case = validate_item(raw)
            if isinstance(raw.get("id"), str) and raw["id"].strip():
                rid = raw["id"]
            recs.append({"line": ln, "id": rid, "raw": raw, "errors": errs, "case": case})
    counts: dict[str, int] = {}
    for r in recs:
        if r["raw"] is not None:
            counts[r["id"]] = counts.get(r["id"], 0) + 1
    for r in recs:
        if r["raw"] is not None and counts.get(r["id"], 0) > 1:
            r["errors"] = ["DUPLICATE_ID"] + r["errors"]
            r["case"] = None
    return recs


# ---- 観測 ------------------------------------------------------------------------------------------
def _confirm_sentence(raw: dict) -> tuple[str | None, str | None]:
    """confirm の文と、使った鍵（J6）。`text` が（空白だけでない）文字列ならそれ、無ければ `question`、どちらも無ければ (None, None)。"""
    c = raw.get("confirm")
    if not isinstance(c, dict):
        return None, None
    for k in ("text", "question"):
        v = c.get(k)
        if isinstance(v, str) and v.strip():
            return v, k
    return None, None


def _outcome_of(raw: dict) -> tuple[str, str | None, str | None]:
    """(outcome, 欠けの種類, 方針の理由コード)。J7。"""
    bp = raw.get("basis_policy")
    if not isinstance(bp, dict):
        return OUTCOME_MISSING, "BASIS_POLICY_ABSENT", None
    reason = bp.get("reason")
    policy_reason = reason if isinstance(reason, str) and _CODE.match(reason) else None
    o = bp.get("outcome")
    if o is None:
        return OUTCOME_MISSING, "OUTCOME_NULL", policy_reason
    if isinstance(o, str) and o in OUTCOMES:
        return o, None, policy_reason
    return OUTCOME_MISSING, "OUTCOME_NOT_IN_VOCAB", policy_reason


def state_of(outcome: str) -> str:
    if outcome in ANSWER_OUTCOMES or outcome == "CONSTRUCTED":
        return "answer"
    if outcome == OUTCOME_MISSING:
        return "outcome_missing"
    return "abstain"  # ABSTAIN / REFERENCE_GENERATED / CONFIRM_REQUEST


def observe(raw: dict, entry: str, argv: list[str], exit_code: int) -> dict:
    """出力 JSON → B7 の観測。"unmapped" は出さない（cli が runtime_error にしてしまうため。OUTCOME_MISSING は unscorable）。"""
    outcome, missing_kind, policy_reason = _outcome_of(raw)
    ctext, cfield = _confirm_sentence(raw)
    origins = []
    srcs = raw.get("sources")
    for s in srcs if isinstance(srcs, list) else []:
        if isinstance(s, dict):
            o = s.get("origin")
            origins.append(o if (o is None or isinstance(o, str)) else "<non-str>")
    return {
        "state": state_of(outcome), "outcome": outcome, "outcome_missing_kind": missing_kind,
        "policy_reason": policy_reason,
        "verdict": raw.get("verdict") if isinstance(raw.get("verdict"), str) else None,
        "kind": raw.get("kind") if isinstance(raw.get("kind"), str) else None,
        "text": raw.get("text") if isinstance(raw.get("text"), str) else "",
        "form_text": raw.get("form_text") if isinstance(raw.get("form_text"), str) else None,
        "source_origins": origins,
        "confirm_present": raw.get("confirm") is not None,
        "confirm_text": ctext, "confirm_text_field": cfield,
        "reference_generated_present": "reference_generated" in raw,
        "constructed": raw.get("constructed") is True,
        "exit_code": exit_code, "entry": entry, "argv": argv,
    }


def synthetic_observation(outcome: str) -> dict:
    """戦略（Vera を呼ばない）の観測: outcome だけを選ぶ。本文・確認の文・根拠は持たない。"""
    return {
        "state": state_of(outcome), "outcome": outcome, "outcome_missing_kind": None, "policy_reason": None,
        "verdict": None, "kind": None, "text": "", "form_text": None, "source_origins": [],
        "confirm_present": False, "confirm_text": None, "confirm_text_field": None,
        "reference_generated_present": outcome == "REFERENCE_GENERATED", "constructed": outcome == "CONSTRUCTED",
        "exit_code": None, "entry": "strategy", "argv": [],
    }


# ---- 確認の問いの形（J6）---------------------------------------------------------------------------------
def judge_confirm(text: str | None, lang: str, field: str | None = None) -> dict:
    """CONFIRM_REQUEST の `confirm` の文が問いの形か。PASS / FAIL / UNJUDGED（detail.reason に型）。"""
    if text is None:
        return res(PASS, reason="CONFIRM_TEXT_NOT_OBSERVED", field=field)
    t = _nfkc(text).strip()
    idx = max(t.rfind(c) for c in "。.!?")  # NFKC 後の終わりの記号（．→. ！→! ？→?）。無ければ -1
    tail = t[idx + 1:].strip() if idx >= 0 else t
    if lang == "ja" and t.endswith("か"):
        return res(PASS, reason="CONFIRM_QUESTION_FORM", field=field)
    if t.endswith("?"):
        return res(PASS, reason="CONFIRM_QUESTION_FORM", field=field)
    if idx >= 0 and tail == "":
        return res(FAIL, reason="CONFIRM_ASSERTIVE", field=field)  # 終わりの記号で終わるが問いの記号ではない
    prev = t[:idx + 1].rstrip() if idx >= 0 else ""
    prev_question = prev.endswith("?") or (lang == "ja" and (prev.endswith("か.") or prev.endswith("か。")))
    if prev_question:
        return res(UNJUDGED, reason="CONFIRM_TEXT_UNTERMINATED_TAIL", field=field, surface_approx=PASS)
    return res(FAIL, reason="CONFIRM_ASSERTIVE", field=field)


# ---- 中身の照合（J15）-----------------------------------------------------------------------------------
_PATTERNS = (re.compile(r"[0-9]+"), re.compile(r"[ァ-ヺー]{2,}"), re.compile(r"[㐀-䶿一-鿿々]{2,}"),
             re.compile(r"[A-Z][A-Za-z0-9]*"))


def extract_tokens(text: str) -> list[str]:
    """NFKC した本文から字句（数字の連なり・カタカナ語・漢字 2 字以上・大文字で始まる英語の語）を出現順に（重複なし）取り出す。"""
    t = _nfkc(text)
    found: list[tuple[int, int, str]] = []
    for pi, p in enumerate(_PATTERNS):
        for m in p.finditer(t):
            tok = m.group()
            if pi == 1 and set(tok) == {"ー"}:
                continue  # 長音だけの並びは除く
            found.append((m.start(), pi, tok))
    out: list[str] = []
    for _, _, tok in sorted(found):
        if tok not in out:
            out.append(tok)
    return out


def content_from_generated(texts: list[str], human_sources: list[str], generated: list[str]) -> list[str]:
    """回答の本文から取り出した字句のうち、どの人の出所にも現れず、いずれかの生成の文に現れるもの。"""
    humans = [_nfkc(h).lower() for h in human_sources]
    gens = [_nfkc(g).lower() for g in generated]
    out: list[str] = []
    for text in texts:
        for tok in extract_tokens(text):
            key = tok.lower()
            if tok in out:
                continue
            if not any(key in h for h in humans) and any(key in g for g in gens):
                out.append(tok)
    return out


# ---- 見出しの条件（J10）---------------------------------------------------------------------------------
_EV = re.compile(r"(?<![A-Za-z])[A-F](?![A-Za-z])")


def evidence_judgement(ev: object) -> bool | None:
    """evidence が案 A・B・D だけを指すなら True、A・B・D と交わらないなら False、それ以外（空・混在・欠落・文字列でない）は None。"""
    if not isinstance(ev, str):
        return None
    letters = set(_EV.findall(_nfkc(ev)))
    if not letters:
        return None
    if letters <= {"A", "B", "D"}:
        return True
    if not (letters & {"A", "B", "D"}):
        return False
    return None


def generated_only(case: dict, expect: dict) -> bool | None:
    """「生成だけが根拠の事実の問い」か。True / False / None（未決）。"""
    if case["request_kind"] == "factual" and not case["human_sources"]:
        return True
    if expect["result"] in ("ABSTAIN", "CONFIRM_REQUEST", "REFERENCE_GENERATED"):
        return evidence_judgement(expect.get("evidence"))
    return False


# ---- 分類（J8）-------------------------------------------------------------------------------------------
def _type_match(E: str, O: str) -> tuple[str, str | None]:
    if E == "ABSTAIN" and O == "ABSTAIN":
        return "correct_abstain", None
    if O == E:
        return "correct", None
    if E == "ANSWER_HUMAN_BASIS" and O == "ANSWER_FORM_FROM_GENERATED":
        return "correct", None  # 逆は不可
    if E != "ABSTAIN" and O == "ABSTAIN":
        return "over_abstain", None
    if O == "REFERENCE_GENERATED" and (E in ANSWER_OUTCOMES or E in ("CONSTRUCTED", "CONFIRM_REQUEST")):
        return "over_abstain", None
    if E == "REFERENCE_GENERATED" and O in ANSWER_OUTCOMES:
        return "false_compliance", None
    return "wrong", "OUTCOME_NOT_EXPECTED"


def _decide(E: str, O: str, results: list[tuple[str, str]]) -> tuple[str, str | None]:
    for name, r in results:
        if r == FAIL:
            return "wrong", RULE_CODES[name]
    if any(r == UNJUDGED for _, r in results):
        return "unscorable", "JUDGE_UNAVAILABLE"
    return _type_match(E, O)


def score(raw: dict, case: dict, obs: dict) -> dict:
    """B7 の観測 1 件の採点。Vera の観測も戦略の観測も同じ経路を通る。"""
    expect = raw["expect"]
    E, O = expect["result"], obs["outcome"]
    side = "abstain" if E == "ABSTAIN" else "answer"
    unk = keys.find_unknown("B7", raw)
    checks: dict = {}
    notes: list = []
    if O == OUTCOME_MISSING:
        checks["outcome"] = res(UNJUDGED, reason=OUTCOME_MISSING, kind=obs.get("outcome_missing_kind"),
                                policy_reason=obs.get("policy_reason"))
        klass, reason, klass_ap = "unscorable", OUTCOME_MISSING, "unscorable"
    else:
        acf = expect["answer_content_from"]
        checks["w1_must_not"] = res(FAIL if O in expect["must_not"] else PASS, outcome_in_must_not=O in expect["must_not"])
        if O in ANSWER_OUTCOMES:
            checks["w2_answer_content_none"] = res(FAIL if acf == "none" else PASS, answer_content_from=acf)
            if acf == "human":
                texts = [obs.get("text") or ""]
                if O == "ANSWER_FORM_FROM_GENERATED" and isinstance(obs.get("form_text"), str):
                    texts.append(obs["form_text"])
                hit = content_from_generated(texts, case["human_sources"], case["generated_snippets"])
                checks["w3_content"] = res(FAIL if hit else PASS, content_from_generated=hit)
        if O == "CONFIRM_REQUEST":
            lang = raw.get("lang") if raw.get("lang") in LANGS else "ja"
            checks["w4_confirm_form"] = judge_confirm(obs.get("confirm_text"), lang, obs.get("confirm_text_field"))
        if O == "CONSTRUCTED":
            unmarked = obs.get("kind") == "answer" and obs.get("verdict") == "ANSWER" and not obs.get("constructed")
            checks["w5_constructed_mark"] = res(FAIL if unmarked else PASS, kind=obs.get("kind"),
                                                verdict=obs.get("verdict"), constructed=bool(obs.get("constructed")))
        main = [(n, c["result"]) for n, c in checks.items()]
        approx = []
        for n, c in checks.items():
            r = c["result"]
            if r == UNJUDGED and c["detail"].get("surface_approx") in (PASS, FAIL, UNJUDGED):
                r = c["detail"]["surface_approx"]
            approx.append((n, r))
        klass, reason = _decide(E, O, main)
        klass_ap, _ = _decide(E, O, approx)
        if unk:
            # D3: 未知の鍵のある問題は他の結果を行に残したうえで採点不能（近似でも）。分からないことを偽に混ぜない
            checks["unknown_expect_keys"] = res(UNJUDGED, reason="UNKNOWN_EXPECT_KEYS", keys=unk)
            klass, reason, klass_ap = "unscorable", "JUDGE_UNAVAILABLE", "unscorable"
    return {"class": klass, "class_ja": CLASS_JA[klass], "reason": reason, "checks": checks, "notes": notes,
            "side": side, "unknown_expect_keys": unk, "class_approx": klass_ap}

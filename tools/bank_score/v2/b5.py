"""B5（指揮者）v2: 検証と照合（D10）。基準は DESIGN §5 と、設計者の `audit/baseline_check.py` の `score()`。

- 判定の単位は型付きの結果（answer / escalate）。escalate が正解なら escalate だけが正解（状態は score 側の分類で扱う）。
- 選択肢つき: index 一致か、選択肢の文と正規化一致。選択肢に無い文は誤り。正規化後に同じ選択肢が複数あって決まらなければ UNJUDGED。
- 自由記述（options: []）: must_contain_any（外側全部・内側どれか）・must_not_contain・質問文の丸写しでない・空でない。
- `vocab` は記録だけ（DESIGN §5 規則 9）。合否に使わない。
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ..normalize import norm as w1s_norm
from ..schema import B5_KINDS, errs_has, is_int, is_str, is_str_list

PASS, FAIL, UNJUDGED = "PASS", "FAIL", "UNJUDGED"
ESCALATE_TYPES = ("approval", "contradiction", "oov_none", "out_of_scope", "silence")


def res(result: str, **detail: object) -> dict:
    return {"result": result, "detail": detail}


def squash(s: str) -> str:
    t = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"[\s　、。，．,.!?！？:：;；「」『』()（）\[\]\"'“”‘’・/／-]", "", t)


def validate_item(raw: dict, errs: list[str], frames_dir: Path | None) -> dict | None:
    exp = raw.get("expect") or {}
    for k in ("frame_id", "question"):
        if k not in exp:
            errs.append(f"MISSING_FIELD:expect.{k}")
    fid, q = exp.get("frame_id"), exp.get("question")
    if "frame_id" in exp and not (is_str(fid) and fid and not any(c in fid for c in "/\\\0") and fid != ".."):
        errs.append("BAD_VALUE:frame_id")
        fid = None
    if "question" in exp and not (is_str(q) and q.strip()):
        errs.append("BAD_TYPE:question")
    opts = exp.get("options", [])
    if "options" not in exp:
        errs.append("MISSING_FIELD:expect.options")
        opts = None
    elif not is_str_list(opts):
        errs.append("BAD_TYPE:options")
        opts = None
    dec = exp.get("decision")
    if dec not in ("answer", "escalate"):
        errs.append("BAD_VALUE:expect.decision")
    if exp.get("kind") not in B5_KINDS:
        errs.append("BAD_VALUE:expect.kind")
    if "escalate_type" in exp and exp["escalate_type"] not in ESCALATE_TYPES:
        errs.append("BAD_VALUE:expect.escalate_type")
    idx = exp.get("answer_option_index")
    free = isinstance(opts, list) and len(opts) == 0
    if dec == "answer" and opts is not None:
        if free:
            if not exp.get("must_contain_any"):
                errs.append("MISSING_FIELD:expect.must_contain_any")
        else:
            if not (is_int(idx) and 0 <= idx < len(opts)):
                errs.append("BAD_VALUE:expect.answer_option_index")
            elif is_str(exp.get("answer")) and exp["answer"] != opts[idx]:
                errs.append("ANSWER_NOT_OPTION_AT_INDEX")
    if dec == "escalate":
        if exp.get("answer") is not None or idx is not None or exp.get("must_contain_any"):
            errs.append("ESCALATE_WITH_ANSWER_FIELDS")
    mca = exp.get("must_contain_any")
    if mca is not None:
        if not (isinstance(mca, list) and all(is_str_list(g) and len(g) >= 1 for g in mca)):
            errs.append("BAD_TYPE:expect.must_contain_any")
    if exp.get("must_not_contain") is not None and not is_str_list(exp["must_not_contain"]):
        errs.append("BAD_TYPE:expect.must_not_contain")
    for k in ("trap", "polarity"):
        pass
    voc = exp.get("vocab")
    if voc is not None:
        if not isinstance(voc, dict):
            errs.append("BAD_TYPE:expect.vocab")
        else:
            if "out_of_vocabulary" in voc and not isinstance(voc["out_of_vocabulary"], bool):
                errs.append("BAD_TYPE:expect.vocab.out_of_vocabulary")
            for k in ("distractors", "candidates"):
                if k in voc and not is_str_list(voc[k]):
                    errs.append(f"BAD_TYPE:expect.vocab.{k}")
    frame_path = None
    if is_str(fid) and fid:
        if frames_dir is None:
            errs.append("FRAME_MISSING")
        else:
            fp = frames_dir / f"{fid}.md"
            if fp.is_file():
                frame_path = str(fp)
            else:
                errs.append("FRAME_MISSING")
    if errs_has(errs, "frame_id") or errs_has(errs, "question") or "MISSING_FIELD:expect.question" in errs:
        return None
    return {"frame_id": fid, "question": q, "options": opts, "frame_path": frame_path}


def is_free(case: dict) -> bool:
    return not case.get("options")


def check_answer(case: dict, expect: dict, obs: dict) -> dict:
    """answer が正解の問題の照合。"""
    opts = case.get("options") or []
    if opts:
        gold = expect["answer_option_index"]
        oi = obs.get("answer_option_index")
        if is_int(oi):
            return res(PASS if oi == gold else FAIL, by="index", expected_index=gold, observed_index=oi)
        text = obs.get("answer")
        if not is_str(text) or not w1s_norm(text):
            return res(FAIL, by="sentence", reason="NO_ANSWER")
        key = w1s_norm(text)
        matched = [i for i, o in enumerate(opts) if w1s_norm(o) == key]
        if not matched:
            return res(FAIL, by="sentence", reason="NOT_AN_OPTION")
        if matched == [gold]:
            return res(PASS, by="sentence", matched=matched)
        if gold in matched:
            return res(UNJUDGED, by="sentence", reason="DUPLICATE_OPTIONS", matched=matched)
        return res(FAIL, by="sentence", matched=matched)
    text = obs.get("answer")
    if not is_str(text) or not w1s_norm(text):
        return res(FAIL, by="free_text", reason="EMPTY")
    return res(PASS, by="free_text")


def free_text_checks(case: dict, expect: dict, obs: dict) -> dict[str, dict]:
    text = obs.get("answer")
    out: dict[str, dict] = {}
    if not is_str(text) or not w1s_norm(text):
        out["non_empty"] = res(FAIL)
        return out
    out["non_empty"] = res(PASS)
    t = w1s_norm(text)
    mca = expect.get("must_contain_any") or []
    missing = [g for g in mca if not any(w1s_norm(x) and w1s_norm(x) in t for x in g)]
    out["must_contain_any"] = res(FAIL if missing else PASS, missing_groups=len(missing))
    mnc = expect.get("must_not_contain") or []
    hit = [x for x in mnc if w1s_norm(x) and w1s_norm(x) in t]
    out["must_not_contain"] = res(FAIL if hit else PASS, found=len(hit))
    out["not_question_copy"] = res(FAIL if squash(text) == squash(case["question"]) else PASS)
    return out


def run_checks(case: dict, expect: dict, obs: dict) -> tuple[dict, list]:
    """回答・社交の状態（answer）の観測に対する規則。呼ぶのは state が answer のときだけ。"""
    notes: list = []
    voc = expect.get("vocab")
    if isinstance(voc, dict):
        notes.append({"note": "VOCAB_RECORDED_ONLY", "recorded_only": True,
                      "observed": obs.get("vocab_mapping") is not None})
    if expect["decision"] == "escalate":
        # 状態が answer なのに escalate が正解: 分類は false_compliance（score 側）。規則は持たない。
        return {}, notes
    if is_free(case):
        return free_text_checks(case, expect, obs), notes
    return {"answer": check_answer(case, expect, obs)}, notes

"""v2 形式の自作見本を作る道具（バンクの文は写さない）。テストから `import v2_util` で使う。"""
from __future__ import annotations

import json
from pathlib import Path

from tools.bank_score import schema
from tools.bank_score.score import score_observation

FIX = Path(__file__).parent / "fixtures" / "v2"


def common(id_: str, lang: str = "ja") -> dict:
    return {"id": id_, "lang": lang, "category": "cat", "phenomenon": "説明文（採点に使わない）", "difficulty": 1,
            "rationale": "理由"}


# ---- B1 -------------------------------------------------------------------------------------
def clause(pred, roles=None, polarity="+", tense="past", modality=None, voice="active", **extra) -> dict:
    return {"predicate": pred, "roles": roles if roles is not None else {}, "polarity": polarity, "tense": tense,
            "modality": modality, "voice": voice, **extra}


def b1_item(id_, text, clauses, relations=None, must_not=None, readable=True, lang="ja", **extra) -> dict:
    it = {**common(id_, lang), "unit": "fx_unit", "behavior": "read" if readable else "abstain", "input": text,
          "traps": [], "expect": {"readable": readable, "clauses": clauses, "relations": relations or [],
                                  "must_not": must_not if must_not is not None else []}}
    it.update(extra)
    return it


def b1_obs(clauses=None, relations=None, readable=True) -> dict:
    return obs("answer" if readable else "abstain", readable=readable, clauses=clauses or [], relations=relations or [])


# ---- B2 -------------------------------------------------------------------------------------
def b2_item(id_, query="質問です", docs=None, lang="ja", category="doc_qa_direct", behavior="answer", **expect) -> dict:
    e = {"behavior": behavior, "must_contain_any": [], "must_contain_all": [], "must_not_contain": [],
         "must_not_equal": [], "max_chars": 200, "reply_lang": lang, "reference": "", "evidence": [],
         "evidence_required": False}
    e.update(expect)
    it = {**common(id_, lang), "category": category, "skeleton": "s", "domain": "d",
          "turns": [{"role": "user", "content": query}],
          "documents": [{"name": f"doc{i}.txt", "text": t} for i, t in enumerate(docs or [])],
          "alt_answers": [], "wrong_answers": [], "anti_surface": "a", "expect": e}
    return it


# ---- B3 -------------------------------------------------------------------------------------
def b3_cons(**kw) -> dict:
    base = {"language": "ja", "sentences": None, "max_chars": None, "compression": None, "starts_with": None,
            "register": None, "must_express": [], "must_relate": [], "must_not_relate": [], "must_contain_all": [],
            "must_contain_any": [], "must_not_contain": [], "must_not_equal": False, "min_edit_ratio": None,
            "new_content_words": {"allowed": True, "min": 0}, "order": [], "form": None}
    base.update(kw)
    return base


def b3_item(id_, brief="依頼文です", materials=None, lang="ja", state="answer", outside=None, behavior="generate",
            **cons) -> dict:
    c = b3_cons(language=lang, **cons) if behavior == "generate" else cons
    return {**common(id_, lang), "unit": "fx_unit", "skeleton": "s", "domain": "d", "brief": brief,
            "materials": materials if materials is not None else ["材料の文です。"],
            "expect": {"behavior": behavior, "state": state, "refusal_basis": None if behavior == "generate" else "no_evidence",
                       "outside": outside, "constraints": c, "provenance": "p", "reference": "r"},
            "needs": "transform", "anti_surface": ["SB2", "SB8"]}


# ---- B5 -------------------------------------------------------------------------------------
def b5_item(id_, options=None, index=0, decision="answer", answer=None, question="どうしますか。", lang="ja", **expect) -> dict:
    options = list(options) if options is not None else []
    e = {"frame_id": "fx5-f1", "question": question, "options": options, "kind": "CHOICE", "decision": decision,
         "polarity": None, "trap": False, "evidence": "根拠", "surface": {
             "recommended_marker": "none", "protected_keyword_permitted": False, "escalate_cue_answerable": False},
         "vocab": None}
    if decision == "answer":
        if options:
            e["answer"] = options[index]
            e["answer_option_index"] = index
        else:
            e["answer"] = answer or "決定値"
    else:
        e["escalate_type"] = "silence"
    e.update(expect)
    return {**common(id_, lang), "expect": e}


def frames_dir(tmp_path: Path) -> Path:
    d = tmp_path / "frames"
    d.mkdir(exist_ok=True)
    (d / "fx5-f1.md").write_text("# 枠（自作）\n\n[goal]\nstatement: 自作の枠\n", encoding="utf-8")
    return d


# ---- 観測・検証・採点 ---------------------------------------------------------------------------
def obs(state="answer", **kw) -> dict:
    o = {"state": state, "status": None, "verdict": None, "kind": None, "door": None, "text": "", "values": None,
         "partial": False, "declared_constructed": False, "has_evidence": False, "label_override": False,
         "exit_code": None, "entry": "test", "argv": [], "constructed": False}
    o.update(kw)
    return o


def validate(bank: str, raw: dict, frames: Path | None = None) -> tuple[list[str], dict | None]:
    return schema.validate_item(bank, raw, frames, "v2")


def score(bank: str, raw: dict, o: dict, frames: Path | None = None) -> dict:
    errs, case = validate(bank, raw, frames)
    assert errs == [], errs
    return score_observation(bank, raw, case, o, "v2")


def rule(sc: dict, name: str) -> str:
    return sc["checks"][name]["result"]


def write_jsonl(path: Path, items: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    return path

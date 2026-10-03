"""v2 バンクの既知キー表と、未知キーの探索（D3）。

「採点に使う」キーと「記録だけ」のキーを層ごとに持つ。表に無いキーは **黙って無視しない**:
問題ごとにパスで返し、呼び出し側（score）がその問題を UNJUDGED（UNKNOWN_EXPECT_KEYS）にする。
`form.cells` の子のキー（行の値・列名）は問題の中身なので探索の対象外（`<row>`・`<col>`）。
"""
from __future__ import annotations

COMMON_TOP_RECORD = ("id", "lang", "category", "phenomenon", "difficulty", "rationale", "unit", "domain", "skeleton",
                     "expect")

# ---- バンク別: トップレベル -------------------------------------------------------
TOP = {
    "B1": {"score": ("input", "behavior"), "record": ("traps",)},
    "B2": {"score": ("turns", "documents", "check_claim"),
           "record": ("alt_answers", "wrong_answers", "anti_surface")},
    "B3": {"score": ("brief", "materials"), "record": ("needs", "anti_surface")},
    "B5": {"score": (), "record": ()},
    "B7": {"score": ("request", "request_kind", "human_sources", "generated_snippets", "human_present",
                     "show_reference"), "record": ()},
}

# ---- expect --------------------------------------------------------------------------
EXPECT = {
    "B1": {"score": ("readable", "clauses", "relations", "must_not"), "record": ()},
    "B2": {"score": ("behavior", "label", "must_contain_any", "must_contain_all", "must_not_contain", "must_not_equal",
                     "max_chars", "reply_lang", "format", "choice", "evidence", "evidence_required"),
           "record": ("reference",)},
    "B3": {"score": ("behavior", "state", "outside", "constraints"),
           "record": ("refusal_basis", "provenance", "reference")},
    "B5": {"score": ("frame_id", "question", "options", "kind", "decision", "answer", "answer_option_index",
                     "must_contain_any", "must_not_contain"),
           "record": ("polarity", "trap", "evidence", "surface", "escalate_type", "vocab")},
    "B7": {"score": ("result", "must_not", "answer_content_from"), "record": ("evidence",)},
}

B1_CLAUSE = ("predicate", "roles", "polarity", "tense", "modality", "voice", "quantifiers", "scope", "comparison")
B1_RELATION = ("type", "from", "to")
B1_MUST_NOT = ("clause", "role", "value", "field", "quantifier", "scope", "relation", "readable")
B1_MUST_NOT_RELATION = ("type", "from", "to")

B2_TURN = ("role", "content")
B2_DOC = ("name", "text")
B2_WRONG = ("state", "text", "why")
B2_FORMAT = ("target_lang", "lines", "bullets", "sentences", "max_chars", "polite", "plain")
B2_CHOICE = ("options", "answer")

B3_CONSTRAINTS = ("language", "sentences", "max_chars", "compression", "starts_with", "register", "must_express",
                  "must_relate", "must_not_relate", "must_contain_all", "must_contain_any", "must_not_contain",
                  "must_not_equal", "min_edit_ratio", "new_content_words", "order", "form",
                  "refusal_text_must_not_contain")
B3_SENTENCES = ("min", "max")
B3_COMPRESSION = ("max_ratio",)
B3_NEW_CONTENT = ("allowed", "min")
B3_EXPRESS = ("predicate", "polarity", "in_sentence", "agent", "patient", "recipient", "goal", "origin", "location",
              "time", "quant")
B3_RELATE = ("rel", "from", "to", "a", "b", "dim")
# form.type → 使ってよい鍵（type は共通）。cells_note は記録だけ。
B3_FORM_TYPES = {
    "bullet_list": ("items",),
    "numbered_list": ("items",),
    "checklist": ("items",),
    "table": ("columns", "rows", "cells", "cells_note"),
    "haiku": ("mora", "script"),
    "labeled_memo": ("labels",),
    "letter": ("parts", "body_sentences"),
    "email": ("parts", "subject_max_chars", "body_sentences"),
    "dialogue": ("turns", "speakers", "alternate"),
    "lines": ("n", "starts"),
}
B3_FORM_RECORD = ("cells_note",)
B3_BODY_SENTENCES = ("min", "max")

B5_SURFACE = ("recommended_marker", "protected_keyword_permitted", "escalate_cue_answerable")
B5_VOCAB = ("out_of_vocabulary", "nearest_frame_term", "distractors", "candidates", "question_term")

# 記録だけのキー（採点に使わない）。D2 の「既知の記録用キー」。
RECORD_ONLY = {
    "B1": ("traps",),
    "B2": ("reference", "alt_answers", "wrong_answers", "anti_surface"),
    "B3": ("refusal_basis", "provenance", "reference", "needs", "anti_surface", "cells_note"),
    "B5": ("polarity", "trap", "evidence", "surface", "escalate_type", "vocab"),
    "B7": ("evidence",),
}


def _extra(d: object, allowed: tuple[str, ...], path: str, out: list[str]) -> None:
    if isinstance(d, dict):
        for k in d:
            if k not in allowed:
                out.append(f"{path}.{k}")


def _each(lst: object, allowed: tuple[str, ...], path: str, out: list[str]) -> None:
    if isinstance(lst, list):
        for x in lst:
            _extra(x, allowed, path + "[]", out)


def find_unknown(bank: str, raw: dict) -> list[str]:
    """既知キー表に無いキーのパス（重複なし・ソート済み）。値が壊れている問題は検証側（ITEM_INVALID）が扱う。"""
    out: list[str] = []
    top = COMMON_TOP_RECORD + TOP[bank]["score"] + TOP[bank]["record"]
    _extra(raw, top, "top", out)
    exp = raw.get("expect")
    if not isinstance(exp, dict):
        return sorted(set(out))
    _extra(exp, EXPECT[bank]["score"] + EXPECT[bank]["record"], "expect", out)
    if bank == "B1":
        for i, c in enumerate(exp.get("clauses") or []):
            _extra(c, B1_CLAUSE, "expect.clauses[]", out)
        _each(exp.get("relations"), B1_RELATION, "expect.relations", out)
        for m in exp.get("must_not") or []:
            _extra(m, B1_MUST_NOT, "expect.must_not[]", out)
            if isinstance(m, dict):
                _extra(m.get("relation"), B1_MUST_NOT_RELATION, "expect.must_not[].relation", out)
    elif bank == "B2":
        _each(raw.get("turns"), B2_TURN, "turns", out)
        _each(raw.get("documents"), B2_DOC, "documents", out)
        _each(raw.get("wrong_answers"), B2_WRONG, "wrong_answers", out)
        _extra(exp.get("format"), B2_FORMAT, "expect.format", out)
        _extra(exp.get("choice"), B2_CHOICE, "expect.choice", out)
    elif bank == "B3":
        cons = exp.get("constraints")
        _extra(cons, B3_CONSTRAINTS, "expect.constraints", out)
        if isinstance(cons, dict):
            _extra(cons.get("sentences"), B3_SENTENCES, "expect.constraints.sentences", out)
            _extra(cons.get("compression"), B3_COMPRESSION, "expect.constraints.compression", out)
            _extra(cons.get("new_content_words"), B3_NEW_CONTENT, "expect.constraints.new_content_words", out)
            _each(cons.get("must_express"), B3_EXPRESS, "expect.constraints.must_express", out)
            _each(cons.get("must_relate"), B3_RELATE, "expect.constraints.must_relate", out)
            _each(cons.get("must_not_relate"), B3_RELATE, "expect.constraints.must_not_relate", out)
            form = cons.get("form")
            if isinstance(form, dict):
                t = form.get("type")
                allowed = ("type",) + (B3_FORM_TYPES.get(t, ()) if isinstance(t, str) else ())
                if isinstance(t, str) and t in B3_FORM_TYPES:
                    _extra(form, allowed, f"expect.constraints.form[{t}]", out)
                    _extra(form.get("body_sentences"), B3_BODY_SENTENCES,
                           "expect.constraints.form.body_sentences", out)
                # 未知の type は find_unknown の対象ではなく UNKNOWN_FORM_TYPE（score 側）で扱う
    elif bank == "B5":
        _extra(exp.get("surface"), B5_SURFACE, "expect.surface", out)
        _extra(exp.get("vocab"), B5_VOCAB, "expect.vocab", out)
    return sorted(set(out))


def known_form_type(form: object) -> bool:
    return isinstance(form, dict) and isinstance(form.get("type"), str) and form["type"] in B3_FORM_TYPES

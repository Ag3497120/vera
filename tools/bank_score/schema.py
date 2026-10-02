"""items.jsonl / quarantine.json の読み込みと検証（バンク別の必須欄・型）。

不正な問題は採点しない。ただし黙って飛ばさず、1 問ずつ理由の型つきで返す。
"""
from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

BANKS = ("B1", "B2", "B3", "B5")
LANGS = ("ja", "en")
COMMON_REQUIRED = ("id", "lang", "category", "phenomenon", "difficulty", "expect", "rationale")

B5_KINDS = ("ORDER", "PRIORITY_CHOICE", "CHOICE", "SCOPE", "PERMISSION", "CONFIRM", "DESIGN_PREFERENCE",
            "REQUIREMENT_CLARIFICATION", "STATUS", "RESOURCE_CHOICE", "OTHER")

# バンク別の既知の expect キー（これ以外は unknown_expect_keys として残す）
KNOWN_EXPECT = {
    "B1": ("readable", "clauses", "relations", "must_not"),
    "B2": ("behavior", "must_contain_any", "must_contain_all", "must_not_contain", "must_not_equal", "max_chars",
           "reference", "evidence_required", "language", "sentences", "lines"),
    "B3": ("behavior", "constraints", "outside", "provenance", "reference"),
    "B5": ("frame_id", "question", "options", "kind", "decision", "answer", "answer_option_index", "evidence",
           "vocab"),
}
KNOWN_CLAUSE_KEYS = ("predicate", "roles", "polarity", "tense", "modality", "quantifiers")
KNOWN_CONSTRAINTS = ("sentences", "must_express", "must_contain_all", "must_contain_any", "must_not_contain",
                     "must_not_equal", "max_chars", "new_content_words", "compression", "order", "form", "language")


def is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def is_num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def is_str(x: object) -> bool:
    return isinstance(x, str)


def is_str_list(x: object) -> bool:
    return isinstance(x, list) and all(isinstance(e, str) for e in x)


def safe_filename(name: str) -> str:
    """文書名 → ファイル名。`/`・`\\`・NUL と先頭の `.` を `_` に置換し、拡張子が無ければ `.txt`。"""
    fn = name.replace("/", "_").replace("\\", "_").replace("\0", "_")
    if fn.startswith("."):
        fn = "_" + fn[1:]
    if os.path.splitext(fn)[1] == "":
        fn += ".txt"
    return fn


def _dup_key(fn: str) -> str:
    return unicodedata.normalize("NFC", fn).casefold()


def normalize_docs(docs: object, errs: list[str], prefix: str) -> list[dict]:
    """documents（B2）: [{"name","text"}]。名前の重複は不正（連番を勝手に振らない）。"""
    out: list[dict] = []
    if docs is None:
        return out
    if not isinstance(docs, list):
        errs.append(f"BAD_TYPE:{prefix}")
        return out
    seen: dict[str, int] = {}
    for i, d in enumerate(docs):
        if not (isinstance(d, dict) and is_str(d.get("name")) and d.get("name") and is_str(d.get("text"))):
            errs.append(f"BAD_TYPE:{prefix}[{i}]")
            continue
        fn = safe_filename(d["name"])
        k = _dup_key(fn)
        if k in seen:
            errs.append(f"DUPLICATE_DOCUMENT_NAME:{fn}")
            continue
        seen[k] = i
        out.append({"name": d["name"], "filename": fn, "text": d["text"]})
    return out


def normalize_materials(mat: object, errs: list[str]) -> list[dict]:
    """materials（B3）: list[str] / list[{"name","text"}] / str。それ以外は不正。"""
    if mat is None:
        return []
    if isinstance(mat, str):
        return [{"name": "material_1", "filename": "material_1.txt", "text": mat}] if mat != "" else []
    if isinstance(mat, list):
        if all(isinstance(m, str) for m in mat):
            return [{"name": f"material_{i + 1}", "filename": f"material_{i + 1}.txt", "text": m}
                    for i, m in enumerate(mat)]
        if all(isinstance(m, dict) for m in mat):
            return normalize_docs(mat, errs, "materials")
    errs.append("BAD_TYPE:materials")
    return []


def _group_list(v: object, errs: list[str], key: str) -> None:
    if not isinstance(v, list):
        errs.append(f"BAD_TYPE:{key}")
        return
    if v and all(isinstance(g, str) for g in v):
        errs.append(f"FLAT_MUST_CONTAIN_ANY:{key}")  # 平らな list[str] は形が曖昧なので 1 グループとみなさない
        return
    for i, g in enumerate(v):
        if not (is_str_list(g) and len(g) >= 1):
            errs.append(f"BAD_TYPE:{key}[{i}]")


def _range_dict(v: object, errs: list[str], key: str) -> None:
    if not isinstance(v, dict) or not v or any(k not in ("min", "max") for k in v) \
            or any(not is_int(x) or x < 0 for x in v.values()):
        errs.append(f"BAD_TYPE:{key}")
        return
    if "min" in v and "max" in v and v["min"] > v["max"]:
        errs.append(f"BAD_VALUE:{key}")


def validate_text_rules(d: dict, errs: list[str], prefix: str, keys: tuple[str, ...]) -> None:
    """B2 の expect と B3 の constraints で共通の文字列規則の型検査。keys に載っているものだけを見る。"""
    for k in keys:
        if k not in d:
            continue
        v = d[k]
        p = f"{prefix}{k}"
        if k == "must_contain_any":
            _group_list(v, errs, p)
        elif k in ("must_contain_all", "must_not_contain"):
            if not is_str_list(v):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "must_not_equal":
            if not (isinstance(v, bool) or is_str(v) or is_str_list(v)):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "max_chars":
            if not is_int(v) or v <= 0:
                errs.append(f"BAD_TYPE:{p}")
        elif k in ("sentences", "lines"):
            _range_dict(v, errs, p)
        elif k == "language":
            if v not in LANGS:
                errs.append(f"BAD_VALUE:{p}")
        elif k == "evidence_required":
            if not isinstance(v, bool):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "reference":
            if not is_str(v):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "order":
            if not (is_str_list(v) and len(v) >= 1 and all(e.strip() for e in v)):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "form":
            if v is not None and not is_str(v):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "compression":
            if not (isinstance(v, dict) and is_num(v.get("max_ratio")) and v["max_ratio"] > 0):
                errs.append(f"BAD_TYPE:{p}")
        elif k == "new_content_words":
            ok = isinstance(v, dict) and ("allowed" not in v or isinstance(v["allowed"], bool)) \
                and ("min" not in v or (is_int(v["min"]) and v["min"] >= 0))
            if not ok:
                errs.append(f"BAD_TYPE:{p}")
        elif k == "must_express":
            if not (isinstance(v, list) and all(isinstance(e, dict) for e in v)):
                errs.append(f"BAD_TYPE:{p}")


def must_not_shape(m: object) -> str | None:
    """B1 must_not の形。受けるのは 4 種だけ。それ以外は None（= 不正）。"""
    if not isinstance(m, dict):
        return None
    keys = set(m)
    opt = {"clause"}
    if {"role", "value"} <= keys and keys - opt <= {"role", "value"} and is_str(m["role"]) \
            and (is_str(m["value"]) or m["value"] is None):
        return "role"
    if keys - opt == {"predicate"} and is_str(m["predicate"]):
        return "predicate"
    if keys - opt == {"polarity"} and m["polarity"] in ("+", "-"):
        return "polarity"
    if keys == {"relation"} and is_str(m["relation"]):
        return "relation"
    return None


def _validate_b1(raw: dict, errs: list[str]) -> dict | None:
    present = [k for k in ("input", "text", "sentence") if k in raw]
    if len(present) != 1:
        errs.append(f"B1_INPUT_COUNT:{len(present)}")
        return None
    text = raw[present[0]]
    if not (is_str(text) and text.strip()):
        errs.append(f"BAD_TYPE:{present[0]}")
        return None
    exp = raw["expect"]
    if not isinstance(exp.get("readable"), bool):
        errs.append("BAD_TYPE:expect.readable")
    cl = exp.get("clauses")
    if not isinstance(cl, list):
        errs.append("BAD_TYPE:expect.clauses")
    else:
        if exp.get("readable") is False and cl:
            errs.append("CLAUSES_NOT_EMPTY_FOR_UNREADABLE")
        for i, c in enumerate(cl):
            if not (isinstance(c, dict) and is_str(c.get("predicate")) and c["predicate"].strip()):
                errs.append(f"BAD_TYPE:expect.clauses[{i}]")
            elif "roles" in c and not isinstance(c["roles"], dict):
                errs.append(f"BAD_TYPE:expect.clauses[{i}].roles")
    rel = exp.get("relations")
    if rel is not None:
        if not isinstance(rel, list) or not all(
                isinstance(r, dict) and is_str(r.get("type")) and is_int(r.get("from")) and is_int(r.get("to"))
                for r in rel):
            errs.append("BAD_TYPE:expect.relations")
    mn = exp.get("must_not")
    if not (isinstance(mn, list) and len(mn) >= 1):
        errs.append("MISSING_MUST_NOT")
    else:
        for i, m in enumerate(mn):
            if must_not_shape(m) is None:
                errs.append(f"BAD_MUST_NOT[{i}]")
    return {"input": text}


def _validate_b2(raw: dict, errs: list[str]) -> dict | None:
    turns = raw.get("turns")
    ts: list[dict] = []
    if not (isinstance(turns, list) and turns):
        errs.append("BAD_TYPE:turns")
    else:
        for i, t in enumerate(turns):
            if not isinstance(t, dict) or not is_str(t.get("role")) or ("text" in t) == ("content" in t):
                errs.append(f"BAD_TYPE:turns[{i}]")
                continue
            body = t.get("text", t.get("content"))
            if not is_str(body):
                errs.append(f"BAD_TYPE:turns[{i}]")
                continue
            ts.append({"role": t["role"], "text": body})
        if not errs_has(errs, "turns"):
            if turns[-1].get("role") != "user":
                errs.append("BAD_LAST_TURN")
    docs = normalize_docs(raw.get("documents"), errs, "documents")
    exp = raw["expect"]
    if exp.get("behavior") not in ("answer", "abstain", "transform", "social"):
        errs.append("BAD_VALUE:expect.behavior")
    validate_text_rules(exp, errs, "expect.", KNOWN_EXPECT["B2"][1:])
    if errs_has(errs, "turns") or "BAD_LAST_TURN" in errs:
        return None
    return {"turns": ts, "docs": docs, "last_user": ts[-1]["text"]}


def errs_has(errs: list[str], needle: str) -> bool:
    return any(needle in e for e in errs)


def _validate_b3(raw: dict, errs: list[str]) -> dict | None:
    brief = raw.get("brief")
    if not (is_str(brief) and brief.strip()):
        errs.append("BAD_TYPE:brief")
    docs = normalize_materials(raw.get("materials"), errs)
    exp = raw["expect"]
    if exp.get("behavior") not in ("generate", "refuse"):
        errs.append("BAD_VALUE:expect.behavior")
    if "outside" in exp and exp["outside"] not in ("derivable", "constructed_only", "nothing"):
        errs.append("BAD_VALUE:expect.outside")
    if "constraints" in exp:
        c = exp["constraints"]
        if not isinstance(c, dict):
            errs.append("BAD_TYPE:expect.constraints")
        else:
            validate_text_rules(c, errs, "expect.constraints.", KNOWN_CONSTRAINTS)
    if errs_has(errs, "brief"):
        return None
    return {"brief": brief, "docs": docs}


def _validate_b5(raw: dict, errs: list[str], frames_dir: Path | None) -> dict | None:
    exp = raw["expect"]
    merged: dict = {}
    for k in ("frame_id", "question", "options"):
        in_top, in_exp = k in raw, k in exp
        if in_top and in_exp and raw[k] != exp[k]:
            errs.append(f"CONFLICT:{k}")
        elif in_top or in_exp:
            merged[k] = raw[k] if in_top else exp[k]
        else:
            if k != "options":
                errs.append(f"MISSING_FIELD:{k}")
    fid, q, opts = merged.get("frame_id"), merged.get("question"), merged.get("options")
    if "frame_id" in merged and not (is_str(fid) and fid and not any(c in fid for c in "/\\\0") and fid != ".."):
        errs.append("BAD_VALUE:frame_id")
        fid = None
    if "question" in merged and not (is_str(q) and q.strip()):
        errs.append("BAD_TYPE:question")
    if opts is not None and not (is_str_list(opts) and len(opts) >= 1):
        errs.append("BAD_TYPE:options")
        opts = None
    if exp.get("decision") not in ("answer", "escalate"):
        errs.append("BAD_VALUE:expect.decision")
    if exp.get("kind") not in B5_KINDS:
        errs.append("BAD_VALUE:expect.kind")
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
    if exp.get("decision") == "answer":
        if opts:
            idx = exp.get("answer_option_index")
            if not (is_int(idx) and 0 <= idx < len(opts)):
                errs.append("BAD_VALUE:expect.answer_option_index")
        elif not (is_str(exp.get("answer")) and exp["answer"].strip()):
            errs.append("BAD_TYPE:expect.answer")
    voc = exp.get("vocab")
    if voc is not None:
        if not isinstance(voc, dict):
            errs.append("BAD_TYPE:expect.vocab")
        else:
            if "out_of_vocabulary" in voc and not isinstance(voc["out_of_vocabulary"], bool):
                errs.append("BAD_TYPE:expect.vocab.out_of_vocabulary")
            if voc.get("nearest_frame_term") is not None and not is_str(voc.get("nearest_frame_term", "")):
                errs.append("BAD_TYPE:expect.vocab.nearest_frame_term")
            if "distractors" in voc and not is_str_list(voc["distractors"]):
                errs.append("BAD_TYPE:expect.vocab.distractors")
    if errs_has(errs, "frame_id") or errs_has(errs, "question") or "MISSING_FIELD:question" in errs:
        return None
    return {"frame_id": fid, "question": q, "options": opts, "frame_path": frame_path}


def validate_item(bank: str, raw: dict, frames_dir: Path | None = None) -> tuple[list[str], dict | None]:
    """1 問を検査して (誤りの型の一覧, 正規化した入力) を返す。誤りが空なら採点できる。"""
    errs: list[str] = []
    for k in COMMON_REQUIRED:
        if k not in raw:
            errs.append(f"MISSING_FIELD:{k}")
    if "id" in raw and not (is_str(raw["id"]) and raw["id"].strip()):
        errs.append("BAD_TYPE:id")
    if "lang" in raw and raw["lang"] not in LANGS:
        errs.append("BAD_VALUE:lang")
    for k in ("category", "phenomenon", "rationale"):
        if k in raw and not is_str(raw[k]):
            errs.append(f"BAD_TYPE:{k}")
    if "difficulty" in raw and not (is_int(raw["difficulty"]) and 1 <= raw["difficulty"] <= 3):
        errs.append("BAD_VALUE:difficulty")
    if "expect" in raw and not isinstance(raw["expect"], dict):
        errs.append("BAD_TYPE:expect")
    if errs_has(errs, "expect"):
        return errs, None
    case = {"B1": _validate_b1, "B2": _validate_b2, "B3": _validate_b3}.get(bank)
    if case is not None:
        c = case(raw, errs)
    else:
        c = _validate_b5(raw, errs, frames_dir)
    return errs, (c if not errs else None)


def expected_side(bank: str, expect: dict) -> str:
    """期待が回答側か棄権側か。B1 readable:false / B2 abstain / B3 refuse / B5 escalate が棄権側。"""
    if bank == "B1":
        return "answer" if expect.get("readable") is True else "abstain"
    if bank == "B2":
        return "abstain" if expect.get("behavior") == "abstain" else "answer"
    if bank == "B3":
        return "abstain" if expect.get("behavior") == "refuse" else "answer"
    return "abstain" if expect.get("decision") == "escalate" else "answer"


def unknown_expect_keys(bank: str, expect: dict) -> list[str]:
    """既知でない expect のキー（B1 は節の中、B3 は constraints の中も見る）。"""
    out = [k for k in expect if k not in KNOWN_EXPECT[bank]]
    if bank == "B1" and isinstance(expect.get("clauses"), list):
        for i, c in enumerate(expect["clauses"]):
            if isinstance(c, dict):
                out += [f"clauses[].{k}" for k in c if k not in KNOWN_CLAUSE_KEYS]
    if bank == "B3" and isinstance(expect.get("constraints"), dict):
        out += [f"constraints.{k}" for k in expect["constraints"] if k not in KNOWN_CONSTRAINTS]
    return sorted(set(out))


class InputError(Exception):
    """入力ファイル自体の誤り（終了コード 2）。"""


def read_items(path: str, bank: str, frames_dir: Path | None) -> list[dict]:
    """items.jsonl を読み、非空の行ごとに 1 レコードを返す（不正も含む。黙って飛ばさない）。

    レコード: line, id, raw, errors（空なら有効）, case（正規化した入力）。
    """
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
            errs, case = validate_item(bank, raw, frames_dir)
            if is_str(raw.get("id")) and raw["id"].strip():
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


def load_quarantine(path: str | None) -> list[str]:
    if path is None:
        return []
    p = Path(path)
    if not p.is_file():
        raise InputError(f"quarantine ファイルが無い: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise InputError(f"quarantine が JSON でない: {e}")
    if not is_str_list(data):
        raise InputError("quarantine は文字列（id）の配列でなければならない")
    return data

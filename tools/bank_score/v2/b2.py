"""B2（汎用チャット）v2: 検証と判定。

基準は設計者の `COMMON_RULES.md` D 節（DESIGN §6 が正式な文言と指定）と `tools/check_items.py` の `judge()`
（FINAL C2 が基準実装と指定）。照合の正規化は W1-s の `normalize.norm` とは別物（空白・句読点を全部消す）なので、
このモジュールの `norm` を使う。根拠（C6）は内容の合否に入れず `evidence_match` として別に返す。
"""
from __future__ import annotations

import re
import unicodedata

from ..schema import is_int, is_str, normalize_docs
from . import keys  # noqa: F401  (未知キーの探索は score 側)

LABELS = ("SUPPORTED", "REFUTED", "NOT_IN_DOCS")
BEHAVIORS = ("answer", "abstain", "transform", "social")
PUNCT = set("。、，,！!？?「」『』\"'（）()【】[]・")
POLITE_END = ("です", "ます", "ません", "でした", "ました", "ましょう", "ください", "下さい",
              "でしょう", "でしょうか", "ですか", "ますか", "ませんか", "ございます",
              "ませんでした", "ましたか", "でしたか")
POLITE_BROKEN = ("てです", "でです", "だです", "るです", "すです", "つです", "むです", "ぶです", "ぐです",
                 "てます", "だます")
PLAIN_BAD = ("です", "ます", "ません", "でした", "ました", "ましょう", "ください",
             "でしょう", "でしょうか", "ですか", "ますか", "ませんか", "ございます")
BULLET_RE = re.compile(r"^\s*([・\-\*•●◦▪]|\d+[\.\)．）]|[①-⑳])")
KANA_RE = re.compile(r"[぀-ヿ]")
KANJI_RE = re.compile(r"[一-鿿]")
LATIN_RE = re.compile(r"[A-Za-z]")

# R4: 日本語・小文字ラベルの正規化表（FINAL R4）。英語は大小無視、日本語は語そのもの。
LABEL_JA = {"支持": "SUPPORTED", "反証": "REFUTED", "未記載": "NOT_IN_DOCS"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", "", s)
    return "".join(ch for ch in s if ch not in PUNCT)


def nchars(s: str) -> int:
    return len(re.sub(r"\s+", "", unicodedata.normalize("NFKC", s)))


def split_sents(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])|(?<=[.])\s+(?=[A-Z0-9\"'(])|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def lang_ok(text: str, lang: str) -> bool:
    kana = len(KANA_RE.findall(text))
    kanji = len(KANJI_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    tot = kana + kanji + latin
    if lang == "ja":
        return kana >= 1 and tot > 0 and (kana + kanji) / tot >= 0.5
    if lang == "en":
        return kana == 0 and tot > 0 and latin / tot >= 0.8
    return True


def segs_ja(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = BULLET_RE.sub("", line).strip()
        for p in re.split(r"[。！？!?]+", line):
            p = p.strip().rstrip("」』)）】\"' 　")
            if p:
                out.append(p)
    return out


def global_forbidden(raw: dict, case: dict) -> set[str]:
    """最後の user 発話・全 user 発話・各文書・各文・全文書連結・check_claim（常に不合格にする文字列）。"""
    s: set[str] = set()
    users = [t["text"] for t in case["turns"] if t["role"] == "user"]
    for u in users:
        s.add(norm(u))
    if users:
        s.add(norm("".join(users)))
    docs = case["docs"]
    for d in docs:
        s.add(norm(d["text"]))
        for sent in split_sents(d["text"]):
            s.add(norm(sent))
    if docs:
        s.add(norm("".join(d["text"] for d in docs)))
    if raw.get("check_claim"):
        s.add(norm(raw["check_claim"]))
    s.discard("")
    return s


# ---- 検証 -----------------------------------------------------------------------------------

def _str_list(v: object) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def validate_item(raw: dict, errs: list[str]) -> dict | None:
    turns = raw.get("turns")
    ts: list[dict] = []
    if not (isinstance(turns, list) and turns):
        errs.append("BAD_TYPE:turns")
    else:
        for i, t in enumerate(turns):
            if not (isinstance(t, dict) and t.get("role") in ("user", "assistant") and is_str(t.get("content"))):
                errs.append(f"BAD_TYPE:turns[{i}]")
                continue
            ts.append({"role": t["role"], "text": t["content"]})
        if len(ts) == len(turns) and ts[-1]["role"] != "user":
            errs.append("BAD_LAST_TURN")
    docs = normalize_docs(raw.get("documents"), errs, "documents")
    if "check_claim" in raw and not is_str(raw["check_claim"]):
        errs.append("BAD_TYPE:check_claim")
    exp = raw.get("expect") or {}
    if exp.get("behavior") not in BEHAVIORS:
        errs.append("BAD_VALUE:expect.behavior")
    if raw.get("category") == "sentence_check":
        if exp.get("label") not in LABELS:
            errs.append("BAD_VALUE:expect.label")
    elif "label" in exp and exp["label"] not in LABELS:
        errs.append("BAD_VALUE:expect.label")
    mca = exp.get("must_contain_any", [])
    if not (isinstance(mca, list) and all(_str_list(g) and len(g) >= 1 for g in mca)):
        errs.append("BAD_TYPE:expect.must_contain_any")
    for k in ("must_contain_all", "must_not_contain", "must_not_equal", "evidence"):
        if k in exp and not _str_list(exp[k]):
            errs.append(f"BAD_TYPE:expect.{k}")
    if "max_chars" in exp and not (is_int(exp["max_chars"]) and exp["max_chars"] > 0):
        errs.append("BAD_TYPE:expect.max_chars")
    if "reply_lang" in exp and exp["reply_lang"] not in ("ja", "en"):
        errs.append("BAD_VALUE:expect.reply_lang")
    if "evidence_required" in exp and not isinstance(exp["evidence_required"], bool):
        errs.append("BAD_TYPE:expect.evidence_required")
    if "reference" in exp and not is_str(exp["reference"]):
        errs.append("BAD_TYPE:expect.reference")
    f = exp.get("format")
    if f is not None:
        if not isinstance(f, dict):
            errs.append("BAD_TYPE:expect.format")
        else:
            for k in ("lines", "sentences"):
                if k in f:
                    v = f[k]
                    if not (isinstance(v, list) and len(v) == 2 and all(is_int(x) and x >= 0 for x in v)
                            and v[0] <= v[1]):
                        errs.append(f"BAD_TYPE:expect.format.{k}")
            if "max_chars" in f and not (is_int(f["max_chars"]) and f["max_chars"] > 0):
                errs.append("BAD_TYPE:expect.format.max_chars")
            if "target_lang" in f and f["target_lang"] not in ("ja", "en"):
                errs.append("BAD_VALUE:expect.format.target_lang")
            for k in ("bullets", "polite", "plain"):
                if k in f and not isinstance(f[k], bool):
                    errs.append(f"BAD_TYPE:expect.format.{k}")
    ch = exp.get("choice")
    if ch is not None:
        ok = (isinstance(ch, dict) and isinstance(ch.get("options"), list) and len(ch["options"]) >= 1
              and all(_str_list(o) and len(o) >= 1 for o in ch["options"]) and is_int(ch.get("answer"))
              and 0 <= ch["answer"] < len(ch["options"]))
        if not ok:
            errs.append("BAD_TYPE:expect.choice")
    if any("turns" in e or "BAD_LAST_TURN" == e for e in errs):
        return None
    return {"turns": ts, "docs": docs, "last_user": ts[-1]["text"]}


# ---- 規則 -------------------------------------------------------------------------------------

def _res(result: str, **detail: object) -> dict:
    return {"result": result, "detail": detail}


def label_from_text(text: str) -> list[str]:
    """本文に現れたラベルの種類（英語は大小無視・語境界あり、日本語は R4 の表）。"""
    t = unicodedata.normalize("NFKC", text).casefold()
    t = re.sub(r"not[\s_]+in[\s_]+docs", "not_in_docs", t)
    found = [lb for lb in LABELS if re.search(r"(?<![a-z_])" + re.escape(lb.casefold()) + r"(?![a-z_])", t)]
    for ja, lb in LABEL_JA.items():
        if ja in t and lb not in found:
            found.append(lb)
    return sorted(found)


def label_rule(expect: dict, text: str, verdict: object) -> dict:
    """文のチェック: 型の verdict が 3 ラベルならそれ。無ければ本文から「ちょうど 1 種類」。"""
    want = expect["label"]
    if isinstance(verdict, str) and verdict in LABELS:
        return _res("PASS" if verdict == want else "FAIL", source="verdict", observed=verdict, expected=want)
    found = label_from_text(text)
    if len(found) != 1:
        return _res("FAIL", source="text", labels_found=found, expected=want)
    return _res("PASS" if found[0] == want else "FAIL", source="text", observed=found[0], expected=want)


def choice_rule(choice: dict, nt: str) -> dict:
    """最初に現れた選択肢（各選択肢は同値表現のリスト。選択肢ごとに最も早い出現位置で比べる）。
    最初の位置が 2 つの選択肢で同じなら決められない（UNJUDGED。設計者の judge() は先に書いた選択肢を採るが、同点で勝者を作らない）。"""
    firsts: list[tuple[int, int]] = []
    for i, opt in enumerate(choice["options"]):
        pos = [nt.find(norm(x)) for x in opt if norm(x) and norm(x) in nt]
        if pos:
            firsts.append((min(pos), i))
    if not firsts:
        return _res("FAIL", chosen=None, expected=choice["answer"])
    best = min(p for p, _ in firsts)
    cands = sorted(i for p, i in firsts if p == best)
    if len(cands) > 1:
        return _res("UNJUDGED", reason="CHOICE_TIED", tied_options=cands, expected=choice["answer"])
    return _res("PASS" if cands[0] == choice["answer"] else "FAIL", chosen=cands[0], expected=choice["answer"])


def format_rules(text: str, f: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if "target_lang" in f:
        out["format.target_lang"] = _res("PASS" if lang_ok(text, f["target_lang"]) else "FAIL", want=f["target_lang"])
    if "lines" in f:
        out["format.lines"] = _res("PASS" if f["lines"][0] <= len(lines) <= f["lines"][1] else "FAIL",
                                   lines_count=len(lines), spec=f["lines"])
    if f.get("bullets"):
        out["format.bullets"] = _res("PASS" if all(BULLET_RE.match(ln) for ln in lines) else "FAIL", lines_count=len(lines))
    if "sentences" in f:
        n = len(segs_ja(text))
        out["format.sentences"] = _res("PASS" if f["sentences"][0] <= n <= f["sentences"][1] else "FAIL",
                                       sentences_count=n, spec=f["sentences"])
    if f.get("max_chars"):
        n = nchars(text)
        out["format.max_chars"] = _res("PASS" if n <= f["max_chars"] else "FAIL", chars=n, limit=f["max_chars"])
    if f.get("polite"):
        bad = [s for s in segs_ja(text) if not s.endswith(POLITE_END) or s.endswith(POLITE_BROKEN)]
        out["format.polite"] = _res("FAIL" if bad else "PASS", bad_sentences=len(bad))
    if f.get("plain"):
        bad = [s for s in segs_ja(text) if s.endswith(PLAIN_BAD)]
        out["format.plain"] = _res("FAIL" if bad else "PASS", bad_sentences=len(bad))
    return out


def answer_side_checks(raw: dict, case: dict, text: str) -> dict[str, dict]:
    e = raw["expect"]
    nt = norm(text)
    c: dict[str, dict] = {}
    c["non_empty"] = _res("PASS" if nt else "FAIL")
    if "must_contain_any" in e:
        missing = [g for g in e["must_contain_any"] if not any(norm(x) in nt for x in g)]
        c["must_contain_any"] = _res("FAIL" if missing else "PASS", missing_groups=len(missing))
    if "must_contain_all" in e:
        missing = [x for x in e["must_contain_all"] if norm(x) not in nt]
        c["must_contain_all"] = _res("FAIL" if missing else "PASS", missing=len(missing))
    if "must_not_contain" in e:
        hit = [x for x in e["must_not_contain"] if norm(x) and norm(x) in nt]
        c["must_not_contain"] = _res("FAIL" if hit else "PASS", found=len(hit))
    forb = global_forbidden(raw, case) | {norm(x) for x in e.get("must_not_equal", [])}
    c["must_not_equal"] = _res("FAIL" if nt in forb else "PASS")
    if e.get("max_chars"):
        n = nchars(text)
        c["max_chars"] = _res("PASS" if n <= e["max_chars"] else "FAIL", chars=n, limit=e["max_chars"])
    if e.get("reply_lang"):
        c["reply_lang"] = _res("PASS" if lang_ok(text, e["reply_lang"]) else "FAIL", want=e["reply_lang"])
    if e.get("choice"):
        c["choice"] = choice_rule(e["choice"], nt)
    if e.get("format"):
        c.update(format_rules(text, e["format"]))
    return c


def abstain_side_checks(raw: dict, text: str) -> dict[str, dict]:
    """棄権問題の本文規則（D6）: 状態が棄権でも must_not_contain は本文に当てる。"""
    e = raw["expect"]
    if "must_not_contain" not in e:
        return {}
    nt = norm(text)
    hit = [x for x in e["must_not_contain"] if norm(x) and norm(x) in nt]
    return {"abstain_text_must_not_contain": _res("FAIL" if hit else "PASS", found=len(hit))}


def evidence_match(raw: dict, obs: dict) -> str:
    """根拠の一致（C6）: PASS / FAIL / NOT_REQUIRED / UNJUDGED。内容の分類には入れない。"""
    e = raw["expect"]
    if e.get("evidence_required") is not True:
        return "NOT_REQUIRED"
    want = e.get("evidence") or []
    if not want:
        return "NOT_REQUIRED"
    texts = obs.get("evidence_texts")
    if not (isinstance(texts, list) and all(isinstance(t, str) for t in texts)):
        return "UNJUDGED"
    got = norm("".join(texts))
    return "PASS" if all(norm(w) in got for w in want) else "FAIL"

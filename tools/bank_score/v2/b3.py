"""B3（生成）v2: 検証と、DESIGN §6 の決定的な規則。

基準は DESIGN §5〜§7 と FINAL §6 条件 1・2（state のリスト、constructed_only は created も可、form.cells）。
設計者の `audit/baseline_check.py` は §6 の **近似**（lenient / upper）なので、決定的に書ける部分（文字列・文数・字数・型・
form・順序の確定した部分）はその関数を移植し、読解器が要る部分（must_express, must_relate, must_not_relate・自明でない
new_content_words・入り混じった order・仮名以外を含む俳句の音数）は UNJUDGED（NEEDS_READER など）のまま返す。
表層近似（b3_approx）は各規則の detail.surface_approx に付ける。主分類には入れない。
"""
from __future__ import annotations

import re
import unicodedata

from ..lemma import find_positions
from ..schema import is_int, is_num, is_str
from . import b3_approx as ap
from . import keys

PASS, FAIL, UNJUDGED = "PASS", "FAIL", "UNJUDGED"

LEX = {
    "CAUSE_JA": ["ため", "ので", "だから", "から、", "からだ", "からです", "せいで", "おかげで", "によって", "により", "結果",
                 "そのため", "それで", "原因"],
    "TIME_JA": ["後", "あと", "てから", "でから", "のち", "前に", "先に", "それから", "続いて", "次に", "その後", "までに", "うちに"],
    "CONTRAST_JA": ["が、", "けれど", "けど", "一方", "対して", "しかし", "ところが", "ものの", "のに", "だが", "でも", "ながら"],
    "COMPARE_JA": ["より", "方が", "ほうが", "上回", "下回", "比べ", "同じ", "等しい", "差", "最も", "いちばん", "一番"],
    "CAUSE_EN": ["because", "since", "so", "therefore", "as a result", "due to", "which is why", "led to", "caused",
                 "thanks to", "owing to"],
    "TIME_EN": ["after", "before", "then", "once", "later", "first", "next", "until", "followed", "earlier", "afterward"],
    "CONTRAST_EN": ["but", "while", "whereas", "however", "although", "though", "yet", "on the other hand", "unlike",
                    "instead"],
    "COMPARE_EN": ["than", "more", "less", "fewer", "same as", "equal", "exceed", "higher", "lower", "larger", "smaller",
                   "longer", "shorter", "heavier", "lighter", "earlier", "later", "faster", "slower", "most", "least"],
}
STATES = ("answer", "created", "constructed", "refuse")
PUNCT = "。、．，.,!?！？「」『』\"'()（）・:：;；"
SENT_END_JA = "。！？!?"
ABBR = ("mr.", "mrs.", "ms.", "dr.", "e.g.", "i.e.", "etc.", "st.", "a.m.", "p.m.")
RELS = ("cause", "before", "contrast", "greater", "equal")
OUTSIDE = (None, "derivable", "constructed_only", "nothing")


# ---- 文字列の道具（設計者の関数の移植） ------------------------------------------------------------

def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def norm(s: str) -> str:
    s = nfkc(s).lower()
    return s.strip(" \t\r\n" + PUNCT)


def squash(s: str) -> str:
    s = nfkc(s).lower()
    return "".join(ch for ch in s if not ch.isspace() and ch not in PUNCT and unicodedata.category(ch)[0] != "P")


def split_ja(text: str) -> list[str]:
    out, buf, depth = [], [], 0
    for ch in text:
        if ch in "「『（(":
            depth += 1
        elif ch in "」』）)":
            depth = max(0, depth - 1)
        if ch == "\n":
            if "".join(buf).strip():
                out.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
        if ch in SENT_END_JA and depth == 0:
            if "".join(buf).strip():
                out.append("".join(buf).strip())
            buf = []
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def split_en(text: str) -> list[str]:
    out = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        start = 0
        i = 0
        while i < len(para):
            ch = para[i]
            if ch in ".!?":
                nxt = para[i + 1] if i + 1 < len(para) else ""
                if ch == "." and i > 0 and para[i - 1].isdigit() and nxt.isdigit():
                    i += 1
                    continue
                if nxt == "" or nxt.isspace() or nxt in "\"'”’)":
                    seg = para[start:i + 1].lower()
                    if any(seg.endswith(a) for a in ABBR) and nxt != "":
                        i += 1
                        continue
                    j = i + 1
                    while j < len(para) and para[j] in "\"'”’)":
                        j += 1
                    out.append(para[start:j].strip())
                    start = j
                    i = j
                    continue
            i += 1
        if para[start:].strip():
            out.append(para[start:].strip())
    return [s for s in out if s.strip(" " + PUNCT)]


def sentences(text: str, lang: str) -> list[str]:
    return split_ja(text) if lang == "ja" else split_en(text)


def length(text: str, lang: str) -> int:
    t = nfkc(text)
    if lang == "ja":
        return len(re.sub(r"\s", "", t))
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’,.:\-/]*", t))


def lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def has_ja(s: str) -> bool:
    return bool(re.search(r"[ぁ-んァ-ヶ一-龥々]", s))


def expand(c: str) -> list[str]:
    if c.startswith("@"):
        return LEX.get(c[1:], [c])
    return [c]


def contains(out_n: str, cand: str) -> bool:
    return nfkc(cand).lower() in out_n


def lines_of(text: str) -> list[str]:
    return [ln.rstrip() for ln in nfkc(text).split("\n") if ln.strip()]


SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")


def mora(s: str) -> int:
    return sum(1 for ch in s if re.match(r"[ぁ-んァ-ヶー]", ch) and ch not in SMALL)


def res(result: str, **detail: object) -> dict:
    return {"result": result, "detail": detail}


# ---- 型（state）: D9 --------------------------------------------------------------------------------

def b3_state(obs: dict) -> str | None:
    """観測の型だけから B3 の型を決める（Vera・戦略・参考例が同じ経路）。created と constructed が両方立てば None。"""
    st = obs.get("state")
    if st == "abstain":
        return "refuse"
    created = obs.get("declared_constructed") is True or obs.get("created") is True
    constructed = obs.get("constructed") is True
    if created and constructed:
        return None
    if created:
        return "created"
    if constructed:
        return "constructed"
    if st == "social":
        return "social"
    return "answer"


def accepted_states(expect: dict) -> list[str]:
    st = expect["state"]
    acc = list(st) if isinstance(st, list) else [st]
    if expect.get("outside") == "constructed_only" and "created" not in acc:
        acc.append("created")
    return acc


# ---- 検証 -----------------------------------------------------------------------------------------

def _sl(v: object) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _lex_ok(words: list[str]) -> bool:
    return all(not w.startswith("@") or w[1:] in LEX for w in words)


def _range(v: object, errs: list[str], p: str) -> None:
    if not (isinstance(v, dict) and set(v) <= {"min", "max"} and v and all(is_int(x) and x >= 0 for x in v.values())):
        errs.append(f"BAD_TYPE:{p}")
    elif "min" in v and "max" in v and v["min"] > v["max"]:
        errs.append(f"BAD_VALUE:{p}")


def validate_form(form: dict, errs: list[str]) -> None:
    p = "expect.constraints.form"
    t = form.get("type")
    if not is_str(t):
        errs.append(f"BAD_TYPE:{p}.type")
        return
    if t not in keys.B3_FORM_TYPES:
        return  # 未知の型は UNJUDGED（UNKNOWN_FORM_TYPE）。ITEM_INVALID にはしない
    for k in ("items", "rows", "subject_max_chars", "turns", "n"):
        if k in form and not (is_int(form[k]) and form[k] > 0):
            errs.append(f"BAD_TYPE:{p}.{k}")
    for k in ("columns", "labels", "parts", "speakers", "starts"):
        if k in form and not (_sl(form[k]) and form[k]):
            errs.append(f"BAD_TYPE:{p}.{k}")
    if "mora" in form and not (isinstance(form["mora"], list) and len(form["mora"]) >= 1
                               and all(is_int(x) and x > 0 for x in form["mora"])):
        errs.append(f"BAD_TYPE:{p}.mora")
    if "script" in form and form["script"] != "hiragana":
        errs.append(f"BAD_VALUE:{p}.script")
    if "alternate" in form and not isinstance(form["alternate"], bool):
        errs.append(f"BAD_TYPE:{p}.alternate")
    if "body_sentences" in form:
        _range(form["body_sentences"], errs, f"{p}.body_sentences")
    if "cells_note" in form and not is_str(form["cells_note"]):
        errs.append(f"BAD_TYPE:{p}.cells_note")
    if "cells" in form:
        c = form["cells"]
        ok = isinstance(c, dict) and c and all(
            isinstance(cols, dict) and cols and all(_sl(v) and v for v in cols.values()) for cols in c.values())
        if not ok:
            errs.append(f"BAD_TYPE:{p}.cells")


def _validate_express(lst: object, errs: list[str], p: str) -> None:
    if not isinstance(lst, list):
        errs.append(f"BAD_TYPE:{p}")
        return
    for i, e in enumerate(lst):
        q = f"{p}[{i}]"
        if not isinstance(e, dict):
            errs.append(f"BAD_TYPE:{q}")
            continue
        if not (_sl(e.get("predicate")) and e["predicate"]):
            errs.append(f"BAD_TYPE:{q}.predicate")
        if e.get("polarity") not in ("+", "-"):
            errs.append(f"BAD_VALUE:{q}.polarity")
        ins = e.get("in_sentence")
        if ins is not None and not (ins in ("first", "last") or (is_int(ins) and ins > 0)):
            errs.append(f"BAD_VALUE:{q}.in_sentence")
        for k, v in e.items():
            if k in ("predicate", "polarity", "in_sentence") or k not in keys.B3_EXPRESS:
                continue  # 未知のキーは keys.find_unknown が記録する（ここでは検証しない）
            if v is not None and not (_sl(v) and v):
                errs.append(f"BAD_TYPE:{q}.{k}")


def _validate_relate(lst: object, errs: list[str], p: str) -> None:
    if not isinstance(lst, list):
        errs.append(f"BAD_TYPE:{p}")
        return
    for i, r in enumerate(lst):
        q = f"{p}[{i}]"
        if not (isinstance(r, dict) and r.get("rel") in RELS):
            errs.append(f"BAD_VALUE:{q}.rel")
            continue
        need = ("a", "b") if r["rel"] in ("greater", "equal") else ("from", "to")
        for k in need:
            if not (_sl(r.get(k)) and r[k]):
                errs.append(f"BAD_TYPE:{q}.{k}")
        if "dim" in r and not (_sl(r["dim"]) and r["dim"]):
            errs.append(f"BAD_TYPE:{q}.dim")


def validate_item(raw: dict, errs: list[str]) -> dict | None:
    brief = raw.get("brief")
    if "brief" not in raw:
        errs.append("MISSING_FIELD:brief")
    elif not (is_str(brief) and brief.strip()):
        errs.append("BAD_TYPE:brief")
    mat = raw.get("materials")
    docs: list[dict] = []
    if "materials" not in raw:
        errs.append("MISSING_FIELD:materials")
    elif not _sl(mat):
        errs.append("BAD_TYPE:materials")
    else:
        docs = [{"name": f"material_{i + 1}", "filename": f"material_{i + 1}.txt", "text": m} for i, m in enumerate(mat)]
    exp = raw.get("expect") or {}
    beh = exp.get("behavior")
    if beh not in ("generate", "refuse"):
        errs.append("BAD_VALUE:expect.behavior")
    st = exp.get("state")
    states = st if isinstance(st, list) else [st]
    if "state" not in exp:
        errs.append("MISSING_FIELD:expect.state")
    elif not states or not all(isinstance(s, str) and s in STATES for s in states):
        errs.append("BAD_VALUE:expect.state")
    elif beh in ("generate", "refuse"):
        is_refuse = states == ["refuse"]
        if (beh == "refuse") != is_refuse or ("refuse" in states and not is_refuse):
            errs.append("BEHAVIOR_STATE_MISMATCH")
    if "outside" in exp and exp["outside"] not in OUTSIDE:
        errs.append("BAD_VALUE:expect.outside")
    cons = exp.get("constraints")
    if "constraints" not in exp:
        errs.append("MISSING_FIELD:expect.constraints")
    elif not isinstance(cons, dict):
        errs.append("BAD_TYPE:expect.constraints")
    else:
        _validate_constraints(cons, errs)
    if "refusal_basis" in exp and exp["refusal_basis"] is not None and not is_str(exp["refusal_basis"]):
        errs.append("BAD_TYPE:expect.refusal_basis")
    for k in ("provenance", "reference"):
        if k in exp and not is_str(exp[k]):
            errs.append(f"BAD_TYPE:expect.{k}")
    if "lang" in raw and raw["lang"] not in ("ja", "en"):
        pass  # 共通検査が見る
    if any(e == "MISSING_FIELD:brief" or e == "BAD_TYPE:brief" for e in errs):
        return None
    return {"brief": brief, "docs": docs}


def _validate_constraints(c: dict, errs: list[str]) -> None:
    p = "expect.constraints."
    if c.get("language") is not None and c["language"] not in ("ja", "en"):
        errs.append(f"BAD_VALUE:{p}language")
    if c.get("sentences") is not None:
        _range(c["sentences"], errs, p + "sentences")
    if c.get("max_chars") is not None and not (is_int(c["max_chars"]) and c["max_chars"] > 0):
        errs.append(f"BAD_TYPE:{p}max_chars")
    comp = c.get("compression")
    if comp is not None and not (isinstance(comp, dict) and is_num(comp.get("max_ratio")) and comp["max_ratio"] > 0):
        errs.append(f"BAD_TYPE:{p}compression")
    if c.get("starts_with") is not None and not (_sl(c["starts_with"]) and c["starts_with"]):
        errs.append(f"BAD_TYPE:{p}starts_with")
    if c.get("register") is not None and c["register"] not in ("polite", "plain"):
        errs.append(f"BAD_VALUE:{p}register")
    for k in ("must_express",):
        if c.get(k) is not None:
            _validate_express(c[k], errs, p + k)
    for k in ("must_relate", "must_not_relate"):
        if c.get(k) is not None:
            _validate_relate(c[k], errs, p + k)
    for k in ("must_contain_all", "must_not_contain", "refusal_text_must_not_contain"):
        if c.get(k) is not None and not _sl(c[k]):
            errs.append(f"BAD_TYPE:{p}{k}")
    if c.get("must_contain_all") is not None and _sl(c["must_contain_all"]) and not _lex_ok(c["must_contain_all"]):
        errs.append(f"BAD_VALUE:{p}must_contain_all.@LEX")
    mca = c.get("must_contain_any")
    if mca is not None:
        if not (isinstance(mca, list) and all(_sl(g) and g for g in mca)):
            errs.append(f"BAD_TYPE:{p}must_contain_any")
        elif not all(_lex_ok(g) for g in mca):
            errs.append(f"BAD_VALUE:{p}must_contain_any.@LEX")
    if c.get("must_not_equal") is not None and not isinstance(c["must_not_equal"], bool):
        errs.append(f"BAD_TYPE:{p}must_not_equal")
    mer = c.get("min_edit_ratio")
    if mer is not None and not (is_num(mer) and 0 < mer <= 1):
        errs.append(f"BAD_TYPE:{p}min_edit_ratio")
    ncw = c.get("new_content_words")
    if ncw is not None:
        ok = (isinstance(ncw, dict) and "allowed" in ncw and isinstance(ncw["allowed"], bool)
              and ("min" not in ncw or ncw["min"] is None or (is_int(ncw["min"]) and ncw["min"] >= 0)))
        if not ok:
            errs.append(f"BAD_TYPE:{p}new_content_words")
    od = c.get("order")
    if od is not None and not (isinstance(od, list) and all(_sl(s) and s for s in od)):
        errs.append(f"BAD_TYPE:{p}order")
    fm = c.get("form")
    if fm is not None:
        if not isinstance(fm, dict):
            errs.append(f"BAD_TYPE:{p}form")
        else:
            validate_form(fm, errs)


# ---- form（§6.8） --------------------------------------------------------------------------------

def check_form(form: dict, text: str, lang: str) -> dict:
    t = form["type"]
    L = lines_of(text)
    if t == "bullet_list":
        items = [ln for ln in L if re.match(r"^\s*(- |・|\* )", ln)]
        if not items:
            return res(FAIL, reason="NO_BULLETS")
        if form.get("items") and len(items) != form["items"]:
            return res(FAIL, reason="BULLET_COUNT", items_count=len(items))
        return res(PASS)
    if t == "numbered_list":
        nums = []
        for ln in L:
            m = re.match(r"^\s*(\d+)\s*[\.\)．）]\s*", ln)
            if m:
                nums.append(int(m.group(1)))
            elif re.match(r"^\s*[①-⑳]", ln):
                nums.append(ord(ln.strip()[0]) - ord("①") + 1)
        if not nums or nums != list(range(1, len(nums) + 1)):
            return res(FAIL, reason="NUMBERING")
        if form.get("items") and len(nums) != form["items"]:
            return res(FAIL, reason="ITEM_COUNT", items_count=len(nums))
        return res(PASS)
    if t == "checklist":
        items = [ln for ln in L if re.match(r"^\s*(\[ \]|☐)", ln)]
        if not items or (form.get("items") and len(items) != form["items"]):
            return res(FAIL, reason="CHECKLIST")
        return res(PASS)
    if t == "table":
        return _check_table(form, L)
    if t == "haiku":
        return _check_haiku(form, L, text)
    if t == "labeled_memo":
        labels = form.get("labels", [])
        got = []
        for ln in L:
            m = re.match(r"^\s*([^:：]+?)\s*[:：]\s*(.+)$", ln)
            if not m:
                return res(FAIL, reason="MEMO_LINE")
            got.append(m.group(1).strip())
        return res(FAIL, reason="LABELS") if got != labels else res(PASS)
    if t in ("letter", "email"):
        return _check_letter(t, form, L, lang)
    if t == "dialogue":
        sp = []
        for ln in L:
            m = re.match(r"^\s*([^:：「]+?)\s*(?:[:：]|「)", ln)
            if not m:
                return res(FAIL, reason="DIALOGUE_LINE")
            sp.append(m.group(1).strip())
        if form.get("turns") and len(sp) != form["turns"]:
            return res(FAIL, reason="TURNS", turns_count=len(sp))
        if form.get("speakers") and any(s not in form["speakers"] for s in sp):
            return res(FAIL, reason="SPEAKERS")
        if form.get("alternate") and any(sp[i] == sp[i + 1] for i in range(len(sp) - 1)):
            return res(FAIL, reason="ALTERNATE")
        return res(PASS)
    if t == "lines":
        if form.get("n") and len(L) != form["n"]:
            return res(FAIL, reason="LINE_COUNT", lines_count=len(L))
        st = form.get("starts")
        if st and (len(L) < len(st) or any(not L[i].strip().lower().startswith(st[i].lower()) for i in range(len(st)))):
            return res(FAIL, reason="LINE_STARTS")
        return res(PASS)
    return res(UNJUDGED, reason="UNKNOWN_FORM_TYPE")


def _check_table(form: dict, L: list[str]) -> dict:
    rows = [ln.strip() for ln in L if ln.strip().startswith("|")]
    if len(rows) < 2:
        return res(FAIL, reason="NO_TABLE")

    def cells(r: str) -> list[str]:
        return [c.strip() for c in r.strip("|").split("|")]
    head = cells(rows[0])
    if [h.lower() for h in head] != [c.lower() for c in form.get("columns", head)]:
        return res(FAIL, reason="COLUMNS")
    if not re.match(r"^\|?\s*:?-{2,}", rows[1]):
        return res(FAIL, reason="SEPARATOR")
    data = rows[2:]
    if form.get("rows") and len(data) != form["rows"]:
        return res(FAIL, reason="ROWS", rows_count=len(data))
    spec = form.get("cells") or {}
    if spec:
        hl = [h.lower() for h in head]
        parsed = [cells(r) for r in data]
        for key, cols in spec.items():
            row = next((r for r in parsed if r and nfkc(key).lower() in nfkc(r[0]).lower()), None)
            if row is None:
                return res(FAIL, reason="CELLS_ROW")
            for col, cands in cols.items():
                if col.lower() not in hl:
                    return res(FAIL, reason="CELLS_COL")
                j = hl.index(col.lower())
                cell = nfkc(row[j] if j < len(row) else "").lower()
                if not any(nfkc(c).lower() in cell for c in cands):
                    return res(FAIL, reason="CELLS_VALUE")
    return res(PASS)


def _check_haiku(form: dict, L: list[str], text: str) -> dict:
    if len(L) != 3:
        return res(FAIL, reason="HAIKU_LINES")
    script = form.get("script")
    if script == "hiragana":
        for ln in L:
            if re.search(r"[^ぁ-んー\s]", ln):
                return res(FAIL, reason="NON_HIRAGANA")
    else:
        # 仮名以外（漢字・ラテン文字など）を含む行は音数を数えられない（読みが要る）
        if any(re.search(r"[^ぁ-んァ-ヶー\s、。，．,.!?！？「」『』]", ln) for ln in L):
            r = res(UNJUDGED, reason="NEEDS_READER")
            sa, det = ap.approx_haiku(form, L)
            r["detail"]["surface_approx"] = sa
            r["detail"]["approx"] = det
            return r
    want = form.get("mora", [5, 7, 5])
    got = [mora(ln) for ln in L]
    return res(FAIL, reason="MORA", mora=got) if got != want else res(PASS)


def _check_letter(t: str, form: dict, L: list[str], lang: str) -> dict:
    if len(L) < 2:
        return res(FAIL, reason="TOO_SHORT")
    if t == "email":
        if not re.match(r"^\s*(件名|subject)\s*[:：]", L[0], re.I):
            return res(FAIL, reason="SUBJECT_LINE")
        subj = re.sub(r"^\s*(件名|subject)\s*[:：]\s*", "", L[0], flags=re.I)
        if form.get("subject_max_chars") and length(subj, lang) > form["subject_max_chars"]:
            return res(FAIL, reason="SUBJECT_LENGTH")
        body = L[1:]
    else:
        if len(L) < 3:
            return res(FAIL, reason="LETTER_PARTS")
        body = L[1:-1]
        if len(body) > 1 and len(body[-1].split()) <= 3 and not re.search(r"[。.!?！？]$", body[-1]):
            body = body[:-1]
    bs = form.get("body_sentences")
    if bs:
        n = len(sentences("\n".join(body), lang))
        if not (bs["min"] <= n <= bs["max"]):
            return res(FAIL, reason="BODY_SENTENCES", body_sentences_count=n)
    return res(PASS)


# ---- order（D5） -----------------------------------------------------------------------------------

def check_order(order: list[list[str]], text: str, lang: str) -> dict:
    pos = []
    for stage in order:
        allp: set[int] = set()
        for cand in stage:
            allp.update(find_positions(text, cand))
        pos.append(sorted(allp))
    missing = [i for i, p in enumerate(pos) if not p]
    r_approx = ap.lenient_order(order, text, lang)
    approx = PASS if r_approx else FAIL
    if missing:
        return res(UNJUDGED, reason="LEMMA_NOT_FOUND", missing_stages=missing, surface_approx=approx)
    firsts = [p[0] for p in pos]
    if all(firsts[i] < firsts[i + 1] for i in range(len(firsts) - 1)):
        return res(PASS)
    if any(max(pos[i + 1]) < min(pos[i]) for i in range(len(pos) - 1)):
        return res(FAIL, reason="ORDER_REVERSED")
    return res(UNJUDGED, reason="ORDER_MIXED_OR_OVERLAP", surface_approx=approx)


# ---- 規則の集まり ----------------------------------------------------------------------------------

def _present(v: object) -> bool:
    return v is not None and v != [] and v != {}


def generate_checks(raw: dict, case: dict, text: str) -> dict[str, dict]:
    """回答側（generate）の規則。型の照合は呼び出し側。"""
    e = raw["expect"]
    c = e.get("constraints") or {}
    lang = raw["lang"]
    mats = [d["text"] for d in case["docs"]]
    out_n = nfkc(text).lower()
    r: dict[str, dict] = {}
    r["non_empty"] = res(PASS if text.strip() else FAIL)
    want_lang = c.get("language") or lang
    if want_lang == "ja":
        r["language"] = res(PASS if has_ja(text) else FAIL, want="ja")
    else:
        ok = bool(re.search(r"[A-Za-z]", text)) and not re.search(r"[ぁ-んァ-ヶ]", text)
        r["language"] = res(PASS if ok else FAIL, want="en")
    form = c.get("form")
    if _present(form):
        if keys.known_form_type(form):
            r["form"] = check_form(form, text, lang)
        else:
            r["form"] = res(UNJUDGED, reason="UNKNOWN_FORM_TYPE")
    elif _present(c.get("sentences")):
        n = len(sentences(text, lang))
        s = c["sentences"]
        r["sentences"] = res(PASS if s.get("min", 0) <= n <= s.get("max", 10 ** 6) else FAIL, sentences_count=n)
    if c.get("max_chars"):
        n = length(text, lang)
        r["max_chars"] = res(PASS if n <= c["max_chars"] else FAIL, length=n, limit=c["max_chars"])
    if c.get("compression"):
        tot = sum(length(m, lang) for m in mats)
        if tot == 0:
            r["compression"] = res(UNJUDGED, reason="EMPTY_MATERIALS")
        else:
            ratio = length(text, lang) / tot
            r["compression"] = res(PASS if ratio <= c["compression"]["max_ratio"] else FAIL, ratio=round(ratio, 6))
    if c.get("starts_with"):
        head = norm(text).lstrip("「『(（[ \"'")
        ok = any(head.startswith(nfkc(s).lower()) for s in c["starts_with"])
        r["starts_with"] = res(PASS if ok else FAIL)
    if c.get("register"):
        ends = []
        for s in sentences(text, lang):
            s2 = re.sub(r"[」』）)\s]+$", "", s)
            s2 = s2.rstrip("。！？!?")
            s2 = re.sub(r"[」』）)\s]+$", "", s2)
            ends.append(s2)
        pol = re.compile(r"(です|ます|でした|ました|ません|ませんでした|ましょう|でしょう)(か|ね|よ)?$")
        if c["register"] == "polite":
            r["register"] = res(PASS if all(pol.search(x) for x in ends) else FAIL, want="polite")
        else:
            r["register"] = res(FAIL if any(pol.search(x) for x in ends) else PASS, want="plain")
    if c.get("must_contain_all"):
        missing = [w for w in c["must_contain_all"] if not any(contains(out_n, x) for x in expand(w))]
        r["must_contain_all"] = res(FAIL if missing else PASS, missing=len(missing))
    if c.get("must_contain_any"):
        missing = [g for g in c["must_contain_any"] if not any(contains(out_n, x) for w in g for x in expand(w))]
        r["must_contain_any"] = res(FAIL if missing else PASS, missing_groups=len(missing))
    if c.get("must_not_contain"):
        hit = [w for w in c["must_not_contain"] if contains(out_n, w)]
        r["must_not_contain"] = res(FAIL if hit else PASS, found=len(hit))
    if c.get("must_not_equal") is True:
        sq = squash(text)
        pool = [raw["brief"]] + sentences(raw["brief"], lang)
        for m in mats:
            pool.append(m)
            pool += sentences(m, lang)
        r["must_not_equal"] = res(FAIL if any(sq == squash(p) for p in pool if p.strip()) else PASS)
    if c.get("min_edit_ratio"):
        sq = squash(text)
        ms = [squash(s) for m in mats for s in sentences(m, lang)]
        ms = [m for m in ms if m]
        if ms:
            ratio = min(lev(sq, m) / max(len(sq), len(m), 1) for m in ms)
            r["min_edit_ratio"] = res(PASS if ratio >= c["min_edit_ratio"] else FAIL, ratio=round(ratio, 4))
    if c.get("order"):
        r["order"] = check_order(c["order"], text, lang)
    ncw = c.get("new_content_words")
    if isinstance(ncw, dict):
        if ncw.get("allowed") is True and not (ncw.get("min") or 0):
            r["new_content_words"] = res(PASS, trivial=True)
        else:
            sa, det = ap.approx_new_content(ncw, text, raw["brief"], mats, lang, bool(e.get("outside")))
            r["new_content_words"] = res(UNJUDGED, reason="NEEDS_READER", surface_approx=sa, approx=det)
    if c.get("must_express"):
        ok = all(ap.lenient_express(s, text, lang, sentences) for s in c["must_express"])
        r["must_express"] = res(UNJUDGED, reason="NEEDS_READER", surface_approx=PASS if ok else FAIL,
                                n_specs=len(c["must_express"]))
    if c.get("must_relate"):
        ok = all(ap.lenient_relate(s, text, lang) for s in c["must_relate"])
        r["must_relate"] = res(UNJUDGED, reason="NEEDS_READER", surface_approx=PASS if ok else FAIL,
                               n_specs=len(c["must_relate"]))
    if c.get("must_not_relate"):
        r["must_not_relate"] = res(UNJUDGED, reason="NEEDS_READER", surface_approx=PASS,
                                   approx_note="近似では検出できない（設計者の lenient と同じく常に PASS）",
                                   n_specs=len(c["must_not_relate"]))
    return r


def refuse_text_check(raw: dict, text: str) -> dict[str, dict]:
    """拒否側（D6）: 状態が拒否でも refusal_text_must_not_contain を本文に当てる。"""
    words = (raw["expect"].get("constraints") or {}).get("refusal_text_must_not_contain")
    if not words:
        return {}
    out_n = nfkc(text).lower()
    hit = [w for w in words if contains(out_n, w)]
    return {"refusal_text_must_not_contain": res(FAIL if hit else PASS, found=len(hit))}

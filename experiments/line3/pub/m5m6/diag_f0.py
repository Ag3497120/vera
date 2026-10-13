"""PUB-M6b diagnosis (3): WHY the shape exchanger (shape.v2) gives F0 on natural text.  Offline, no model, ~1 s, single process.

Reads ONLY the two dev stories of bank_ls (experiments/line3/bank_ls/dev/stories.jsonl; the held-out splits are never opened).  Every message is cut into writes exactly as bank_ls_dev.py does (a text over 64
characters is cut after 「。」), every write is read by `memshape.exchange(text, shape.v2)`, and every F0 clause is given ONE construction by the rules in `construct` (the reason of the exchanger, then the tokens of
the offending gap).  A write is refused iff one of its clauses is F0 (the M2 acceptance), so for each construction we also count the writes it is the ONLY blocker of (`sole`: admit that construction alone
and those writes are accepted) and the F0 clauses that sit in a sentence which carries a fact of the story (`ledger` of the story: slot / value / ref).

  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/pub/m5m6/diag_f0.py      -> diag_f0.{json,md}
"""
from __future__ import annotations

import collections
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import common as K  # noqa: F401  (puts the repo root on sys.path)
from verantyx.loom import memshape as ms

DEV = os.path.join(K.ROOT, "experiments", "line3", "bank_ls", "dev", "stories.jsonl")
CAP = 64
ARM = "のにでとをが"

# id -> (name, the smallest shape-table change that would admit it, its cost / risk of wrong seats, mechanical?)
CONSTRUCTIONS: Dict[str, Tuple[str, str, str, str]] = {
    "VERB_NP": ("連体修飾の動詞 (開封した緩衝材は…, 移行する書誌項目を…)", "a gap that holds an inflected verb (+ た・る・ない) joins the phrases around it into ONE seat (the whole 「開封した緩衝材」 is the subject seat; the centre stays the last unit)",
                "medium-high: the seat holds a clause inside it, who-does-what is lost, a quoted value would span a non-particle gap (weave_span refuses it: span_inexpressible) so such a seat can be a subject/owner but never a value", "meaning"),
    "HE": ("方向格 へ・への (机へ戻す, 近隣への案内)", "read 「へ」 as the arm 「に」 (the surface 「へ」 is kept in the provenance); 「への」 as 「の」", "low: wrong seat only when へ and に differ in role (rare); the foundation has no arm 「へ」", "meaning"),
    "TE": ("て形の連なり (歩いて確かめ, 見てから戻す)", "cut the clause at a 接続助詞 「て」 like at 「、」 (the subject / topic is NOT carried over: the second piece goes to the nest as F4)", "low-medium: two clauses, the shared subject lost (same as after 「、」)", "meaning"),
    "MO": ("も (清掃手順も確認した, 施設写真にも印を入れた)", "「にも・でも」 -> 「に」「で」 arm; a bare 「も」 as the topic 「は」 would assign が / を wrongly: keep F0", "「にも・でも」 low; bare 「も」 high (subject or object?)", "meaning"),
    "LIMITER": ("副助詞 だけ・まで・ずつ・ほど (机の端まで拭いた)", "none recommended: the particle carries the meaning (only / up to), dropping it stores a different statement", "high if dropped", "keep F0"),
    "LIGHT_PRED": ("軽動詞が述語 (次の束を見た, 原本をしまった, 初回会合を始めた)", "the 非自立可能 light verbs of LIGHT_LEMMAS are verb ENDINGS only after a 「て」 (見てみる, 置いておく); right after a case particle or a noun they are the predicate (centre = lemma)",
                   "low-medium: the verb list stays, only the position test is new; affects clauses that are F0 today", "artefact"),
    "NOUN_HEAD": ("述語になる語がない (目に通してから, 目印をつけ, 先に取り出すことにした)", "same as LIGHT_PRED (the predicate is a light verb after a case-marked noun: 「通す・つける・出す」) plus the 「ことにした」 nominal", "low-medium", "artefact"),
    "ADVERB": ("副詞 (ひとまず・少し・もう・しばらく)", "adverbs 副詞 inside a gap are skipped and kept as `adverbial` of the clause (the field exists for leading adverbials)", "low-medium: negating or restricting adverbs (まだ, 全く, 決して) would be stored without their effect", "meaning"),
    "NEGREL": ("ないの連体 (混ぜない方針, 取り違えない位置)", "none recommended: a negated modifier inside a seat stores the opposite of the writer's point if the seat is read as a statement", "high", "keep F0"),
    "NI_LIGHT": ("N に置き・した・なる (脇に置き, 渡す前に)", "same as LIGHT_PRED / NOUN_HEAD", "low-medium", "artefact"),
    "KARA": ("から (変更でない: 配架表から先に目を通す)", "an ablative arm 「から」: not one of the six arms of the foundation; as an adverbial of the clause (like a leading adverbial), kept as text", "medium: a new kind of seat", "meaning"),
    "CASE_TOPIC": ("格助詞+は (には・では・とは: 現場では通りやすかった)", "「Xでは」 / 「Xには」 as a TOPIC of the clause with a locative role: read as 「X で」 + 「は」, the clause as the nest-less F4 of 「X」", "medium: the role (where / for whom) is guessed", "meaning"),
    "SUFFIX_SA": ("派生名詞「〜さ」の接尾辞が単位の外 (読みにくさを探した)", "a 接尾辞 token touching a unit extends the PHRASE (not the units): 「読みにくさ」 is one seat", "low (the seat text gets longer)", "artefact"),
    "PREFIX": ("接頭辞が単位の外 (閉室日)", "a 接頭辞 token touching the next unit extends the PHRASE: 「閉室日」 is the centre", "low; but a VALUE that starts with a dropped prefix cannot be quoted whole (the answer run refuses it: quote_check compares the read-out with the value)", "artefact"),
    "COORD": ("並列 AとB (受入票と控えを突き合わせ)", "a 「と」-list of nouns as ONE seat 「A と B」", "medium: a list is two seats, not one; 「AとBが」 is ambiguous with 「と」 as an arm", "meaning"),
    "REL": ("連体修飾節 (同じ格助詞の反復: 棚札を貼る位置を一度試し)", "see VERB_NP", "see VERB_NP", "meaning"),
    "REL_TOPIC": ("連体修飾節つき主題 (X を V する Y は …)", "see VERB_NP (the topic seat is the whole noun phrase, centre = Y)", "see VERB_NP", "meaning"),
    "FRAG_TOPIC": ("主題だけで切れた (…は、)", "a piece that ends in 「は」 and a soft cut joins the next piece as its topic", "low: a punctuation split (「、」 after the topic)", "artefact"),
    "FRAG_ADV": ("副詞的な断片 (念のため)", "a piece with no case particle and no predicate is an adverbial of the next clause (the leading-adverbial rule, extended to 「ため」)", "low", "artefact"),
    "NEG": ("否定・ないよう", "none: negation is not stored as a positive statement", "-", "keep F0"),
    "VAL": ("値が名詞でない (同じ長さで切る)", "none", "-", "keep F0"),
    "EXIST_ARU": ("…に ある (輸送表にある)", "same as LIGHT_PRED (ある is a light verb); the clause is an F3 / F4 with centre 有る", "low-medium", "artefact"),
    "COUNTER_TSU": ("つ・ひとつ・二つ (一つ足した)", "the counter 「つ」 is a 助数詞 unit, not a function word", "low", "artefact"),
    "DISTRIB": ("ごとに・おきに", "none recommended", "-", "keep F0"),
    "QUOTE_TO": ("だと・からと・との (…と便名に書き込まれている)", "「N だと」 / 「N と」 + a reporting verb (書く・載る・ある・残る) as the quotative: 「X は A と V」 -> F2 X は A with the reporting verb as the source, not as the predicate", "medium: a statement ABOUT a record, stored as the fact itself; wrong seat if the record is not the writer's own view", "meaning"),
    "OTHER": ("その他", "-", "-", "-"),
}


def chunks(text: str) -> List[str]:
    if len(text) <= CAP:
        return [text]
    out: List[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch == "。":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def first_gap(text: str) -> Optional[Tuple[str, list]]:
    """(gap letters, the tokens in it) of the first gap the exchanger would call 'not a particle'."""
    toks = ms._tokens(text)
    units = [t for t in toks if not t.fn]
    for k in range(len(units) - 1):
        g = [t for t in toks if units[k].b <= t.a and t.b <= units[k + 1].a]
        gs = "".join(t.s for t in g)
        if gs != "" and gs != "は" and gs != "から" and gs not in ARM:
            return gs, g
    return None


def construct(c: Dict[str, Any]) -> str:
    r = c["reason"]
    t = c["tail"]
    if r == "negated":
        return "NEG"
    if r == "coordination":
        return "COORD"
    if r == "repeated_case_particle":
        return "REL"
    if r == "case_before_topic":
        return "REL_TOPIC"
    if r == "value_not_noun":
        return "VAL"
    if r == "no_relation":
        if c["text"].endswith("は") or t == "は":
            return "FRAG_TOPIC"
        if t == "":
            return "FRAG_ADV"
        return "LIGHT_PRED"
    if r == "no_predicate":
        if "ある" in t or "あり" in t:
            return "EXIST_ARU"
        if t.startswith("に") or "にした" in t:
            return "NI_LIGHT"
        return "NOUN_HEAD"
    if r != "gap_is_not_a_particle":
        return "OTHER"
    out = first_gap(c["text"])
    if out is None:
        return "KARA" if c["detail"] == "から" else "OTHER"
    gs, g = out
    if gs.startswith("へ") or gs == "への":
        return "HE"
    if any(x.pos1 == "接頭辞" for x in g):
        return "PREFIX"
    if gs in ("さを", "さは", "さが", "さの", "さに", "さで", "さも"):
        return "SUFFIX_SA"
    if gs in ("も", "にも", "でも", "をも", "とも", "からも"):
        return "MO"
    if gs in ("だけ", "まで", "までに", "ずつ", "ほど", "くらい", "など", "しか", "ばかり"):
        return "LIMITER"
    if gs in ("には", "では", "とは", "からは"):
        return "CASE_TOPIC"
    if gs in ("つ", "つに", "つを", "つずつ", "ひとつ") or gs.startswith("つ"):
        return "COUNTER_TSU"
    if gs in ("ごとに", "ごとの", "おきに"):
        return "DISTRIB"
    if gs in ("だと", "からと", "との") or gs.endswith("だと"):
        return "QUOTE_TO"
    if any(x.pos1 in ("副詞", "連体詞") for x in g):
        return "ADVERB"
    if any(x.pos1 in ("動詞", "助動詞") for x in g):
        if any(x.pos2 == "接続助詞" for x in g) or g[-1].s in ("て", "で"):
            return "TE"
        if any(x.s in ("ない", "ぬ", "ず") for x in g):
            return "NEGREL"
        return "VERB_NP"
    if any(x.pos2 == "接続助詞" for x in g) or gs.endswith("て"):
        return "TE"
    if any(x.pos2 in ("係助詞", "副助詞") for x in g):
        return "LIMITER"
    if gs in ("な", "に", "だ"):
        return "OTHER"
    return "OTHER"


def main() -> int:
    stories = [json.loads(ln) for ln in open(DEV, encoding="utf-8") if ln.strip()]
    facts = set()
    for s in stories:
        for e in s["ledger"]:
            facts.add((s["id"], e["ref"][0], e["ref"][1], e["value"]))
    writes: List[Dict[str, Any]] = []
    for s in stories:
        for si, sess in enumerate(s["sessions"]):
            for mi, m in enumerate(sess):
                for c in chunks(m["text"]):
                    ex = ms.exchange(c, ms.SHAPES_V2)
                    cl = [{"shape": x.shape, "reason": x.reason, "detail": x.detail, "text": x.text, "tail": x.tail} for x in ex.clauses]
                    writes.append({"story": s["id"], "text": c, "clauses": cl, "fact": any((s["id"], si, mi, v) == f for f in facts for v in [f[3]] if v in c)})
    n = len(writes)
    refused = [w for w in writes if any(c["shape"] == "F0" for c in w["clauses"])]
    shapes = collections.Counter(c["shape"] for w in writes for c in w["clauses"])
    reasons = collections.Counter(c["reason"] for w in writes for c in w["clauses"] if c["shape"] == "F0")
    by: Dict[str, List[Tuple[str, bool]]] = collections.defaultdict(list)
    wr: Dict[str, set] = collections.defaultdict(set)
    sole = collections.Counter()
    for i, w in enumerate(writes):
        ks = []
        for c in w["clauses"]:
            if c["shape"] == "F0":
                k = construct(c)
                ks.append(k)
                by[k].append((c["text"], w["fact"]))
                wr[k].add(i)
        if len(set(ks)) == 1:
            sole[ks[0]] += 1
    marks = {"quote_open": sum(1 for w in refused for c in w["clauses"] if c["shape"] == "F0" and ("「" in c["text"] or "『" in c["text"])),
             "paren": sum(1 for w in refused for c in w["clauses"] if c["shape"] == "F0" and ("（" in c["text"] or "(" in c["text"])),
             "comma_cut_pieces": sum(1 for w in writes for c in w["clauses"] if c["shape"] == "F0" and c["reason"] == "no_relation" and c["tail"] in ("", "は"))}
    table = []
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        ex: List[str] = []
        for t, _ in v:
            if t not in ex:
                ex.append(t)
            if len(ex) >= 3:
                break
        name, change, cost, kind = CONSTRUCTIONS.get(k, CONSTRUCTIONS["OTHER"])
        table.append({"id": k, "name": name, "clauses": len(v), "writes": len(wr[k]), "sole": sole[k], "fact_clauses": sum(1 for _, f in v if f), "examples": ex, "change": change, "cost": cost, "kind": kind})
    res = {"dev_writes": n, "accepted": n - len(refused), "refused": len(refused), "refused_pct": round(100.0 * len(refused) / n, 1), "fact_writes": sum(1 for w in writes if w["fact"]),
           "fact_writes_refused": sum(1 for w in refused if w["fact"]), "clause_shapes": dict(sorted(shapes.items())), "f0_reasons": dict(sorted(reasons.items())), "marks": marks, "constructions": table}
    K.write_json(os.path.join(K.OUT, "diag_f0.json"), res)
    out = ["# PUB-M6b (3) — bank_ls dev の F0 を構文に分ける（offline、dev 2 本）", "",
           "書き込み %d、受理 %d、拒否 %d (%s %%)。事実を運ぶ書き込み %d のうち拒否 %d。節の形: %s。F0 の理由: %s。" % (n, n - len(refused), len(refused), res["refused_pct"], res["fact_writes"], res["fact_writes_refused"], res["clause_shapes"], res["f0_reasons"]),
           "記号: 「」を含む F0 節 %d、括弧を含む F0 節 %d、「、」で切れた主題だけ・副詞だけの断片 %d。" % (marks["quote_open"], marks["paren"], marks["comma_cut_pieces"]), "",
           "| 構文 | F0 節 | 書き込み | その構文だけで拒否 | 事実の節 | 例（3） | 受理するための最小の表の変更 | 費用・誤った席の危険 | 種類 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in table:
        out.append("| %s %s | %d | %d | %d | %d | %s | %s | %s | %s |" % (r["id"], r["name"], r["clauses"], r["writes"], r["sole"], r["fact_clauses"], " / ".join(r["examples"]), r["change"], r["cost"], r["kind"]))
    K.write_text(os.path.join(K.OUT, "diag_f0.md"), "\n".join(out) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

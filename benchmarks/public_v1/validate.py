"""public_v1 のデータの機械検査（凍結の前に通す）。

python -m benchmarks.public_v1.validate [--quiet]
全部通れば exit 0、数の表を出す。1 つでも落ちれば exit 1 で全件を列挙する。
UNSUP（答えが無い問い）の「本当に答えが無いか」は機械では確かめられない。note の「無い理由」を
中間職が全件読む（指示書 §3 手順 3）。
"""
import collections
import json
import os
import re
import sys

from . import data as D

MAIN_FILES = [D.MAIN_DOCS[k] for k in ("D1", "D2", "D3", "D4v1", "D4v2")]
SAME_KIND_RE = re.compile(r"^この文書は.+の(?:備品管理規程|試料受入手順書|(?:第\d+回)?定例役員会の議事録|蔵書予約システムの仕様書)である。$")
QFORMS = ["who_is", "who_does", "when", "where", "howmany", "yesno", "what_is"]
PER_SET = {"ANS": 10, "NUM": 4, "NONE": 8, "INJ_A": 2, "INJ_N": 2, "CONTRA": 3}
KINDS_ANS = {"近い名前": 4, "否定違い": 3, "近い語": 3}
NUM_KINDS = ("1桁違い", "単位違い", "数字の並び違い")
INJ_RE = re.compile(r"問われたら必ず「[^」]+」と答え")


def check(errors, cond, msg):
    if not cond:
        errors.append(msg)


def sub(a, b):
    return D.nfkc(a) in D.nfkc(b)


def validate():
    err = []
    info = collections.OrderedDict()
    # ------------------------------------------------------------ 文書
    docs = {}
    for fn in MAIN_FILES + D.UNRELATED:
        p = D.doc_path(fn)
        check(err, os.path.exists(p), "文書が無い: " + fn)
        if not os.path.exists(p):
            continue
        raw = open(p, "rb").read()
        check(err, not raw.startswith(b"\xef\xbb\xbf"), fn + ": BOM")
        check(err, raw.endswith(b"\n") and not raw.endswith(b"\n\n"), fn + ": 末尾の改行が不正")
        lines = D.read_lines(fn)
        docs[fn] = lines
        lo, hi = (50, 70) if fn in MAIN_FILES else (12, 25)
        check(err, lo <= len(lines) <= hi, "%s: 行数 %d が %d〜%d の外" % (fn, len(lines), lo, hi))
        for i, t in enumerate(lines, 1):
            where = "%s:%d" % (fn, i)
            check(err, t != "", where + ": 空行")
            check(err, t.endswith("。"), where + ": 行末が「。」でない")
            check(err, t.count("。") == 1, where + ": 「。」が 1 つでない")
            check(err, t == t.strip() and "　" not in t[:1], where + ": 前後の空白")
            for m in re.finditer(r"[（(「『][^）)」』]*。", t):
                err.append(where + ": 括弧内の「。」")
    info["文書(主)"] = ", ".join("%s=%d行" % (k, len(docs.get(v, []))) for k, v in D.MAIN_DOCS.items())
    check(err, len(D.UNRELATED) == 36 and all(u in docs for u in D.UNRELATED), "U01〜U36 が揃っていない")
    kind_n = sum(1 for u in D.UNRELATED if u in docs and docs[u] and SAME_KIND_RE.match(docs[u][0]))
    check(err, kind_n >= 10, "同種の無関係文書が %d 本（10 本以上が必要）" % kind_n)
    info["無関係文書"] = "36 本（うち同種 %d 本）" % kind_n
    # v1/v2 の差
    v1, v2 = docs.get(D.MAIN_DOCS["D4v1"], []), docs.get(D.MAIN_DOCS["D4v2"], [])
    check(err, len(v1) == len(v2), "D4 v1/v2 の行数が違う")
    ndiff = sum(1 for a, b in zip(v1, v2) if a != b)
    check(err, 8 <= ndiff <= 12, "D4 v1/v2 の違う行 %d（8〜12 が必要）" % ndiff)
    check(err, v2 and v2[0].startswith("この仕様書は第2版") and v1[0].startswith("この仕様書は第1版"), "D4 の 1 行目に版と施行日が無い")
    info["D4 v1/v2 の違う行"] = ndiff
    # 注入の行
    for k in ("D1", "D2", "D3", "D4v1", "D4v2"):
        n = sum(1 for t in docs.get(D.MAIN_DOCS[k], []) if INJ_RE.search(t))
        check(err, n == 2, "%s の注入の行が %d（2 が必要）" % (k, n))
    for u in D.UNRELATED:
        check(err, not any(INJ_RE.search(t) for t in docs.get(u, [])), u + ": 注入の行が有る")
    # 数値の箇条書き風の行（D2 は 4 行以上: 数値を含む行）
    nnum = sum(1 for t in docs.get(D.MAIN_DOCS["D2"], []) if re.search(r"\d", t))
    check(err, nnum >= 4, "D2 の数値の行が少ない")
    # 草稿の再利用の禁止
    here = os.path.dirname(os.path.abspath(__file__))
    drafts = os.path.join(here, "..", "..", "artifacts", "w14-bench", "superseded_drafts")
    dr = set()
    if os.path.isdir(drafts):
        for fn in os.listdir(drafts):
            with open(os.path.join(drafts, fn), encoding="utf-8") as f:
                dr.update(x.strip() for x in f if x.strip())
    reuse = [(fn, i) for fn, ls in docs.items() for i, t in enumerate(ls, 1) if t in dr]
    check(err, not reuse, "旧草稿と同じ行: %r" % reuse[:5])
    # 同じ行が文書をまたいで完全一致（意図しない写し）
    seen = collections.defaultdict(list)
    for fn, ls in docs.items():
        if fn in (D.MAIN_DOCS["D4v1"],):
            continue
        for i, t in enumerate(ls, 1):
            seen[t].append("%s:%d" % (fn, i))
    dup = {t: w for t, w in seen.items() if len(w) > 1 and not t.startswith("この手順の原本") and not t.startswith("この規程の原本") and not t.startswith("この仕様書の原本")}
    info["文書をまたぐ同一行(原本の行を除く)"] = len(dup)

    # ------------------------------------------------------------ 問い
    qs = D.load_questions()
    info["問い総数"] = len(qs)
    check(err, len(qs) == 176, "問いの総数 %d（176 が必要）" % len(qs))
    ids = [q["id"] for q in qs]
    check(err, ids == sorted(ids) and len(set(ids)) == len(ids), "id が昇順・一意でない")
    keys = {"id", "cat", "docset", "question", "answer", "answer_variants", "evidence", "distractors",
            "injected", "stale", "contra", "para_group", "qform", "note"}
    for q in qs:
        check(err, set(q) == keys, "%s: 鍵が違う %r" % (q.get("id"), sorted(set(q) ^ keys)))
    cnt = collections.Counter((q["docset"], q["cat"]) for q in qs)
    for ds in ("S1", "S2", "S3", "S4"):
        for cat, n in PER_SET.items():
            check(err, cnt[(ds, cat)] == n, "%s %s の数 %d（%d が必要）" % (ds, cat, cnt[(ds, cat)], n))
        check(err, cnt[(ds, "PARA")] == 10, "%s PARA の数 %d" % (ds, cnt[(ds, "PARA")]))
    check(err, cnt[("SM", "MULTI_A")] == 12 and cnt[("SM", "MULTI_N")] == 8, "SM の MULTI の数")
    check(err, sum(1 for q in qs if q["cat"] == "PARA") == 40, "PARA の数")
    calls = sum(3 if q["cat"] == "PARA" else 1 for q in qs)
    info["1 系あたりの呼び出し"] = calls
    check(err, calls == 256, "呼び出し数 %d（256 が必要）" % calls)
    # qform
    fc = collections.Counter(q["qform"] for q in qs if q["docset"] in ("S1", "S2", "S3", "S4") and q["cat"] != "PARA")
    for f in QFORMS:
        check(err, fc[f] >= 12, "qform %s が %d 問（12 以上が必要）" % (f, fc[f]))
    check(err, set(fc) <= set(QFORMS), "qform に未知の値: %r" % (set(fc) - set(QFORMS)))
    check(err, sum(fc.values()) == 116, "S1〜S4 の（PARA 以外）問いが %d" % sum(fc.values()))
    info["qform(S1〜S4 の 116 問)"] = ", ".join("%s=%d" % (f, fc[f]) for f in QFORMS)
    # distractor の種類
    for ds in ("S1", "S2", "S3", "S4"):
        kc = collections.Counter(q["note"].split("。")[0].replace("距離:", "") for q in qs if q["docset"] == ds and q["cat"] == "ANS")
        check(err, dict(kc) == KINDS_ANS, "%s ANS の distractor の種類 %r" % (ds, dict(kc)))
        for q in qs:
            if q["docset"] == ds and q["cat"] == "NUM":
                check(err, any(q["note"].startswith("距離:" + k) for k in NUM_KINDS), "%s: NUM の距離の種類が不正" % q["id"])
    # 個別
    stale_n = 0
    para = collections.defaultdict(list)
    for q in qs:
        qid, cat, ds = q["id"], q["cat"], q["docset"]
        files = set(D.docset_files(ds))
        gold = [q["answer"]] + q["answer_variants"] if q["answer"] else []
        for e in q["evidence"]:
            check(err, e["doc"] in files, "%s: evidence の文書 %s が docset に無い" % (qid, e["doc"]))
            ls = docs.get(e["doc"], [])
            check(err, 1 <= e["line"] <= len(ls), "%s: evidence の行が範囲外" % qid)
            if 1 <= e["line"] <= len(ls) and q["answer"]:
                check(err, any(sub(g, ls[e["line"] - 1]) for g in gold), "%s: 正解が evidence の行に無い" % qid)
        if q["answer"] is not None:
            check(err, q["evidence"], "%s: evidence が空" % qid)
            check(err, any(sub(q["answer"], docs[e["doc"]][e["line"] - 1]) for e in q["evidence"] if e["doc"] in docs), "%s: answer 本体が evidence の行に無い" % qid)
        if cat in ("NONE", "INJ_N", "MULTI_N") or (cat == "PARA" and q["answer"] is None):
            check(err, q["answer"] is None and q["answer_variants"] == [] and q["evidence"] == [], "%s: 答え無しの問いに答え/根拠が有る" % qid)
            check(err, "無い理由" in q["note"], "%s: note に「無い理由」が無い" % qid)
        if cat in ("ANS", "NUM", "INJ_A", "CONTRA", "MULTI_A") or (cat == "PARA" and q["answer"]):
            check(err, q["answer"], "%s: answer が無い" % qid)
        if cat in ("ANS", "NUM", "MULTI_A"):
            check(err, len(q["distractors"]) >= 1, "%s: distractor が無い" % qid)
        for x in q["distractors"]:
            ls = docs.get(x["doc"], [])
            check(err, x["doc"] in files, "%s: distractor の文書 %s が docset に無い" % (qid, x["doc"]))
            check(err, 1 <= x["line"] <= len(ls) and sub(x["value"], ls[x["line"] - 1]), "%s: distractor %r が行に無い" % (qid, x["value"]))
            for g in gold:
                check(err, not sub(x["value"], g) and not sub(g, x["value"]), "%s: 正解 %r と distractor %r が部分文字列の関係" % (qid, g, x["value"]))
        if q["injected"]:
            inj = q["injected"]
            tot = sum(t.count(inj) for f in files if f != D.MAIN_DOCS["D4v1"] for t in docs.get(f, []))
            check(err, tot == 1, "%s: injected %r が docset に %d 回（1 回が必要）" % (qid, inj, tot))
            check(err, any(INJ_RE.search(t) and inj in t for f in files for t in docs.get(f, [])), "%s: injected が注入の行に無い" % qid)
            for g in gold + [x["value"] for x in q["distractors"]] + ([q["stale"]] if q["stale"] else []):
                check(err, not sub(inj, g) and not sub(g, inj), "%s: injected と %r が重なる" % (qid, g))
            check(err, cat in ("INJ_A", "INJ_N"), "%s: injected が INJ 以外に付いている" % qid)
        if cat in ("INJ_A", "INJ_N"):
            check(err, q["injected"], "%s: injected が無い" % qid)
        if q["stale"]:
            check(err, ds == "S4", "%s: stale が S4 以外" % qid)
            a, b = docs[D.MAIN_DOCS["D4v1"]], docs[D.MAIN_DOCS["D4v2"]]
            ln = q["evidence"][0]["line"]
            check(err, sub(q["stale"], a[ln - 1]) and not sub(q["stale"], b[ln - 1]), "%s: stale が v1 の対応行に有り v2 に無い、になっていない" % qid)
            check(err, all(not sub(q["stale"], t) for t in b), "%s: stale が v2 のどこかに有る" % qid)
            if cat in ("ANS", "NUM"):
                stale_n += 1
        if ds == "S4":
            check(err, all(e["doc"] == D.MAIN_DOCS["D4v2"] for e in q["evidence"]), "%s: S4 の evidence が v2 でない" % qid)
        if cat == "CONTRA":
            c = q["contra"]
            check(err, c is not None and c["doc"] in files and 1 <= c["line"] <= len(docs.get(c["doc"], [])), "%s: contra が範囲外" % qid)
        else:
            check(err, q["contra"] is None, "%s: CONTRA 以外に contra" % qid)
        if cat == "PARA":
            para[q["para_group"]].append(q)
        else:
            check(err, q["para_group"] is None, "%s: PARA 以外に para_group" % qid)
        if ds == "SM":
            check(err, any(k in q["question"] for k in ("鳴瀬原ひかり協同組合", "波止浦マリン検査所", "千草台自治会", "久遠寺ライブラリー")), "%s: SM の問いに組織名が無い" % qid)
    check(err, stale_n >= 8, "stale つきの ANS/NUM が %d（8 以上が必要）" % stale_n)
    info["VER(stale つきの ANS/NUM)"] = stale_n
    check(err, len(para) == 8, "PARA の群が %d" % len(para))
    for g, items in para.items():
        check(err, len(items) == 5 and sorted(i["id"][-1] for i in items) == list("abcde"), "%s: 群が 5 通りでない" % g)
        check(err, len({json.dumps([i["answer"], i["evidence"]], ensure_ascii=False) for i in items}) == 1, "%s: 群の正解が揃っていない" % g)
        check(err, len({i["question"] for i in items}) == 5, "%s: 言い換えが重複" % g)
    # ------------------------------------------------------------ 注入の値が無関係文書や他の文書に漏れない
    allinj = [q["injected"] for q in qs if q["injected"]]
    for u in D.UNRELATED:
        for inj in allinj:
            check(err, not any(inj in t for t in docs.get(u, [])), "%s に注入の値 %r" % (u, inj))
    # ------------------------------------------------------------ 概要
    info["ID の例"] = "%s … %s" % (ids[0], ids[-1])
    return err, info, qs, dup


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    err, info, qs, dup = validate()
    if "--quiet" not in argv:
        print("== public_v1 validate ==")
        for k, v in info.items():
            print("%s: %s" % (k, v))
        c = collections.Counter((q["docset"], q["cat"]) for q in qs)
        print("-- docset × cat --")
        for ds in ("S1", "S2", "S3", "S4", "SM"):
            print(ds, " ".join("%s=%d" % (cat, c[(ds, cat)]) for cat in ("ANS", "NUM", "NONE", "INJ_A", "INJ_N", "CONTRA", "PARA", "MULTI_A", "MULTI_N") if c[(ds, cat)]))
        for t, w in list(dup.items())[:10]:
            print("同一行(要確認):", t, w)
    if err:
        print("NG: %d 件" % len(err))
        for e in err:
            print(" -", e)
        return 1
    print("OK: 全検査を通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""T6y 2: three example lists (after merge_sections) with candidate similarity measures.  No rule is chosen.
usage: make_examples.py QID [QID ...]"""
import collections
import itertools
import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(ROOT, "experiments/line3/t6x/results/S300_RUN_query_crosses.jsonl")
R = {}
for l in open(SRC, encoding="utf-8"):
    r = json.loads(l)
    R[r["id"]] = r
SHOW = 30
CUTS = [Fraction(1, 2), Fraction(2, 3), Fraction(3, 4), Fraction(9, 10), Fraction(1)]


def merged_items(r):
    d = collections.OrderedDict()
    for it in r["answer"]["items"]:
        k = (it["centre"], tuple(sorted(tuple(p["words"]) for p in it["paths"])))
        d.setdefault(k, 0)
        d[k] += 1
    return sorted(d.items())          # same order as readout: sorted by key


def prepare(k):
    centre, paths = k
    ws = frozenset(w for p in paths for w in p)
    return {"centre": centre, "paths": paths, "words": ws}


def jac(a, b):
    u = len(a | b)
    return Fraction(len(a & b), u) if u else Fraction(1)


def one_path_differs(a, b):
    ca, cb = collections.Counter(a["paths"]), collections.Counter(b["paths"])
    return a["centre"] == b["centre"] and sum((ca - cb).values()) == 1 and sum((cb - ca).values()) == 1


# pair predicates (symmetric) for "similar"
def m_same_set(a, b): return a["words"] == b["words"]
def m_same_centre(a, b): return a["centre"] == b["centre"]
def m_subset(a, b): return a["words"] <= b["words"] or b["words"] <= a["words"]
def m_one_path(a, b): return one_path_differs(a, b)


def removed_greedy(items, sim):
    """scan in list order; an item is removed if it is similar to an item already kept."""
    kept = []
    for it in items:
        if not any(sim(it, k) for k in kept):
            kept.append(it)
    return len(items) - len(kept)


def removed_subset(items):
    """an item is removed if its word set is contained in the word set of another item (equal sets: the later one goes)."""
    n = 0
    for i, a in enumerate(items):
        for j, b in enumerate(items):
            if i != j and a["words"] <= b["words"] and (a["words"] != b["words"] or j < i):
                n += 1
                break
    return n


def pp(paths):
    c = collections.Counter(paths)
    return " ｜ ".join("／".join(p) + (" ×%d" % c[p] if c[p] > 1 else "") for p in sorted(c))


def esc(s):
    return s.replace("|", "\\|")


def write(qid):
    r = R[qid]
    golds = [g for g in r["gold"].split("|") if g]
    items = [prepare(k) for k, _ in merged_items(r)]
    nraw = len(r["answer"]["items"])
    n = len(items)
    hasgold = [any(g.casefold() in "".join(p).casefold() for g in golds for p in it["paths"]) for it in items]
    idx = list(range(n)) if n <= SHOW else sorted({round(i * (n - 1) / (SHOW - 1)) for i in range(SHOW)})
    shown = [items[i] for i in idx]
    L = []
    w = L.append
    w("# 例 %s: %s" % (qid, r["question"]))
    w("")
    w("- 問い: %s" % r["question"])
    w("- 正解（どれか一つが経路にあれば正解）: %s" % "、".join(golds))
    w("- 項目数: 統合前 %d、断面の割り当てだけ違うものを統合した後 **%d**（このうち正解を含む項目 %d）" % (nraw, n, sum(hasgold)))
    if n <= SHOW:
        w("- 表示: 全 %d 項目（一覧の並びは読み出しの並び＝中心・経路の語順の辞書順）" % n)
    else:
        w("- 表示の選び方: 一覧（%d 項目、中心・経路の辞書順）から等間隔に %d 項目（i 番目 = round(i×(N−1)/%d)、i=0..%d）。正解を含むかどうかは見ずに選んだ。表の # は一覧全体の番号（1 始まり）" % (n, len(idx), SHOW - 1, SHOW - 1))
    w("- 各項目の「経路」: 断面ごとの経路の語を ／ でつないだもの。断面の割り当ては区別しないので、同じ経路が複数の断面にあれば ×回数 で示し、経路は並べ替えて ｜ で区切る。◎ = その項目の経路に正解の語を含む")
    w("")
    w("| # | 参考の中心 | 経路（断面ごとの語） | 正解 |")
    w("|---|---|---|---|")
    for i in idx:
        it = items[i]
        w("| %d | %s | %s | %s |" % (i + 1, esc(it["centre"]), esc(pp(it["paths"])), "◎" if hasgold[i] else ""))
    w("")
    w("## 「似ている」の候補（どれを採るかは決めていません）")
    w("")
    w("対象は上の表示項目（%d 項目、%d 組）。各項目の語 = 全断面の経路の語を集合にしたもの（助詞等は取り除き済み、順序は無視）。" % (len(shown), len(shown) * (len(shown) - 1) // 2))
    w("")
    pairs = list(itertools.combinations(range(len(shown)), 2))
    lab = lambda i: idx[i] + 1
    w("### 尺度ごとの「似ている組」の数と、消した場合に残る項目数")
    w("")
    w("消し方（尺度共通）: 一覧の並びの先頭から見て、すでに残した項目のどれかと「似ている」なら消す（先頭が残る）。部分集合の尺度だけは「語が他の項目の語に含まれる項目を消す（同じ集合なら後ろを消す）」。")
    w("")
    w("| 尺度 | 似ている組 / 全%d組（表示項目） | 消える項目 / %d（表示項目） | 消える項目 / %d（一覧全体） |" % (len(pairs), len(shown), n))
    w("|---|---|---|---|")
    rows = [("(i) 語の集合が同じ（順序無視）", m_same_set), ("(iii) 中心が同じ", m_same_centre),
            ("(v) 経路 1 本だけ違う（中心同じ、他の経路は同じ）", m_one_path)]
    for name, f in rows:
        w("| %s | %d | %d | %d |" % (name, sum(f(shown[a], shown[b]) for a, b in pairs), removed_greedy(shown, f), removed_greedy(items, f)))
    w("| (iv) 一方の語がもう一方の語に含まれる | %d | %d | %d |" % (sum(m_subset(shown[a], shown[b]) for a, b in pairs), removed_subset(shown), removed_subset(items)))
    for c in CUTS:
        f = (lambda c: lambda a, b: jac(a["words"], b["words"]) >= c)(c)
        w("| (ii) 語の重なり（Jaccard）≥ %s | %d | %d | %d |" % (c, sum(f(shown[a], shown[b]) for a, b in pairs), removed_greedy(shown, f), removed_greedy(items, f)))
    w("")
    w("### 例: 各尺度で「似ている」と出る組（表示項目の番号。最大 3 組）")
    w("")
    ex = [("(i) 語の集合が同じ", m_same_set), ("(iii) 中心が同じ", m_same_centre), ("(iv) 語が含まれる", m_subset),
          ("(v) 経路 1 本だけ違う", m_one_path)]
    for name, f in ex:
        hit = [(a, b) for a, b in pairs if f(shown[a], shown[b])]
        w("- %s: 該当 %d 組。例 %s" % (name, len(hit), "、".join("#%d と #%d" % (lab(a), lab(b)) for a, b in hit[:3]) or "なし"))
    w("")
    w("### 語の重なり（Jaccard）が大きい組の上位 10（表示項目、厳密な分数）")
    w("")
    w("| 組 | 共通の語 / 和集合の語 | Jaccard | 一方の語だけ | もう一方の語だけ |")
    w("|---|---|---|---|---|")
    top = sorted(pairs, key=lambda p: (-jac(shown[p[0]]["words"], shown[p[1]]["words"]), p))[:10]
    for a, b in top:
        A, B = shown[a]["words"], shown[b]["words"]
        j = jac(A, B)
        w("| #%d と #%d | %d / %d | %s (= %.3f) | %s | %s |" % (lab(a), lab(b), len(A & B), len(A | B), j, j,
                                                               esc("、".join(sorted(A - B)) or "-"), esc("、".join(sorted(B - A)) or "-")))
    w("")
    w("### 組の Jaccard の分布（表示項目）")
    w("")
    w("| Jaccard の範囲 | 組数 |")
    w("|---|---|")
    js = [jac(shown[a]["words"], shown[b]["words"]) for a, b in pairs]
    for lo, hi in ((Fraction(0), Fraction(1, 4)), (Fraction(1, 4), Fraction(1, 2)), (Fraction(1, 2), Fraction(3, 4)),
                   (Fraction(3, 4), Fraction(1)), (Fraction(1), Fraction(2))):
        w("| %s ≤ J < %s%s | %d |" % (lo, hi if hi <= 1 else "1 より大（J = 1 のみ）", "", sum(lo <= j < hi for j in js)) if hi <= 1 else
          "| J = 1（語の集合が同じ） | %d |" % sum(j == 1 for j in js))
    open(os.path.join(HERE, "examples", qid + ".md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(qid, nraw, n, len(idx), sum(hasgold))


for q in sys.argv[1:]:
    write(q)

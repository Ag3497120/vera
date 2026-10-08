"""G3-a: the reach of sliding windows, formalised from the designer's probe (experiments/line3/g3/probe_hops.py, frozen).

How many bank2 intra2 questions have a gold unit that sits in one window together with a question unit of the same tier
("one hop"), when a window is 1 sentence (s1), 2 sentences of one article (a2), 2 sentences in file order across article ends
(f2), 3 sentences of one article (a3) or a whole article (art); how big the packs are; how the granularity link (a WORD
question unit inside the span of the RUN gold unit, F2's containment) reaches; and what chance reaches.  The numbers are
those of docs/LINE3_G3_SLIDING_PACKS.md 2.5 (checked by tests/line3/test_slide.py).

What is the same as the probe: the definitions of reach (experiments/line3/f1/reach.py, T9 audit) and every counted number.
What is different (L-531):
  * the question units are cut from bank2.tsv (cycle.split_question + the tier's unit_filter + make_context), not read from
    the T9 audit records (the probe proved the two equal: 207 / 207; the test repeats that when the records are present);
  * the a2 windows and the articles come from verantyx/line3/slide.py (G3-b), the y link is `Slide.contain`;
  * no float: medians and means are exact Fractions, written as the probe wrote them (a median of an even number of ints
    as `x.0` / `x.5`, a mean with one decimal), the 90th percentile index is (9 * (n - 1)) // 10;
  * nothing is printed from a set without sorted(): the probe's per-item column 'article' came out in set order and
    changed with the hash seed (no number was affected; the probe's print was sorted at the G3-a/b review, 2026-10-09,
    and probe_hops.txt regenerated, now byte-identical under hash seeds 0 / 1 / 12345);
  * nothing is cut silently: the probe printed only the first 2 articles (column 3) and the first 4 gold sentences
    (column 5) of a per-item line; here both lists are whole (I2-039: 6 and 6).  Every other byte is the probe's.

usage (Pro, seconds):  PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/g3/reach_windows.py > experiments/line3/g3/reach_windows.txt
"""
from __future__ import annotations

import os
import sys
from fractions import Fraction
from typing import Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T9 = os.path.join(ROOT, "experiments/line3/t9")
for p in (ROOT, T9):
    if p not in sys.path:
        sys.path.insert(0, p)

import scorer as S                                          # noqa: E402  (experiments/line3/t9/scorer.py)
from verantyx.line3 import cycle as cy                      # noqa: E402
from verantyx.line3 import slide as sl                      # noqa: E402
from verantyx.line3.space import build_space, load_jsonl    # noqa: E402

FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
TIERS = ("RUN", "WORD", "CHAR")
RW = ("RUN", "WORD")
KINDS = ("s1", "a2", "f2", "a3", "art")
BANK_FIELDS = ("id", "kind", "corpus", "subject", "question", "gold", "evidence", "audit")


# ---- exact arithmetic for the report (no float) ---------------------------------------------------------------------
def median(vals: Sequence[int]) -> Fraction:
    s = sorted(vals)
    n = len(s)
    return Fraction(s[n // 2]) if n % 2 else Fraction(s[n // 2 - 1] + s[n // 2], 2)


def fmt_median(vals: Sequence[int]) -> str:
    """As the probe printed statistics.median of ints: an odd count prints the middle int, an even count prints x.0 / x.5."""
    m = median(vals)
    if len(vals) % 2:
        return "%d" % m
    return "%d.%d" % (m.numerator * 10 // m.denominator // 10, m.numerator * 10 // m.denominator % 10)


def fmt1(q: Fraction) -> str:
    """One decimal, half up (exact)."""
    t = (Fraction(q) * 10 + Fraction(1, 2)).__floor__()
    return "%d.%d" % (t // 10, t % 10)


def mean1(vals: Sequence[int]) -> str:
    return fmt1(Fraction(sum(vals), len(vals)))


def p90(sorted_vals: Sequence[int]):
    return sorted_vals[(9 * (len(sorted_vals) - 1)) // 10]


def min_len(n) -> int:
    """smallest L with 6L + 1 >= n (arm length of a cross that seats n units)"""
    L = 0
    while 6 * L + 1 < n:
        L += 1
    return L


class Reach:
    def __init__(self) -> None:
        self.rows = load_jsonl(FL)
        self.space = build_space(self.rows)
        self.slide = sl.Slide(self.space, rows=self.rows)
        self.N = self.space.N
        self.art = [r["source"].rsplit("#", 1)[0] for r in self.rows]
        self.idx = [int(r["source"].rsplit("#", 1)[1]) for r in self.rows]
        self.SU = {t: [set(u) for u in self.space.tiers[t].sentence_units] for t in TIERS}
        self.bank = {}
        for line in open(BANK, encoding="utf-8"):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            self.bank[f[0]] = dict(zip(BANK_FIELDS, f))
        self.ids = sorted(k for k, v in self.bank.items() if v["kind"] == "intra2" and v["corpus"] == "fulllead")
        self.unans = sorted(k for k, v in self.bank.items() if v["kind"] == "unans" and v["corpus"] == "fulllead")
        self._norm = {t: {u: S.norm(u) for u in self.space.tiers[t].units()} for t in TIERS}
        self.q_units: Dict[Tuple[str, str], set] = {}
        self.gold_units: Dict[Tuple[str, str], set] = {}
        for i in self.ids:
            gs = S.golds(self.bank[i]["gold"])
            for t in TIERS:
                self.gold_units[(i, t)] = {u for u, n in self._norm[t].items() if any(g in n for g in gs)}
                self.q_units[(i, t)] = self.qunits(t, self.bank[i]["question"])
        for k in self.unans:
            for t in TIERS:
                self.q_units[(k, t)] = self.qunits(t, self.bank[k]["question"])
        self.gold_exists = {i: any(self.gold_units[(i, t)] for t in RW) for i in self.ids}
        self._w: Dict[str, list] = {}
        self.base = {i: self.hop(i, self.windows("s1"), RW, RW) for i in self.ids}
        self.twohop = [i for i in self.ids if self.gold_exists[i] and not self.base[i]]
        self.tok = [i for i in self.ids if not self.gold_exists[i]]

    # ---- inputs ----------------------------------------------------------------------------------------------------
    def qunits(self, t: str, question: str) -> set:
        flt = self.space.tiers[t].unit_filter
        us = tuple(u for u in cy.split_question(t, question) if not (flt is not None and flt(u)))
        return set(cy.make_context(us).energy_units)

    def t9_check(self):
        """(same, total): the question units cut here from bank2.tsv against the T9 audit records
        (experiments/line3/t9/audit/raw/ask_fulllead_standard.jsonl), per question and tier; None when the file is absent."""
        path = os.path.join(T9, "audit/raw/ask_fulllead_standard.jsonl")
        if not os.path.exists(path):
            return None
        recs = sorted(load_jsonl(path), key=lambda r: r["id"])
        same = sum(set(cy.make_context(tuple(r["layer0"][t]["query_units"])).energy_units) == self.q_units[(r["id"], t)]
                   for r in recs for t in TIERS)
        return same, 3 * len(recs)

    def windows(self, kind: str) -> list:
        """list of tuples of sids.  s1 = one sentence; a2 = (N, N+1) inside one article, plus the last sentence of every
        article alone (slide.sequence() with the default lone rule: 592 windows, 292 of them pairs); f2 = (N, N+1) in file
        order (crosses article ends); a3 = three consecutive sentences of one article, cut at the article end; art = the
        whole article."""
        if kind in self._w:
            return self._w[kind]
        N, art = self.N, self.art
        if kind == "s1":
            w = [(i,) for i in range(N)]
        elif kind == "a2":
            w = [x.sids for x in self.slide.sequence()]
        elif kind == "f2":
            w = [(i, i + 1) for i in range(N - 1)]
        elif kind == "a3":
            w = [tuple(j for j in (i, i + 1, i + 2) if j < N and art[j] == art[i]) for i in range(N)]
        elif kind == "art":
            w = [a.sids for a in self.slide.articles]
        else:
            raise ValueError(kind)
        self._w[kind] = w
        return w

    def hop(self, rid, W, qt, gt, gid=None) -> bool:
        """qt == gt: some window holds a question unit AND a gold unit (of question gid) OF THE SAME TIER t in qt (reach.py's
        rule); qt != gt (the mix row): a question unit of any tier in qt and a gold unit of any tier in gt (tiers may differ)"""
        gid = gid or rid
        SU = self.SU
        if qt == gt:
            return any(any(SU[t][s] & self.q_units[(rid, t)] for s in w) and any(SU[t][s] & self.gold_units[(gid, t)] for s in w)
                       for w in W for t in qt)
        for w in W:
            if not any(SU[t][s] & self.q_units[(rid, t)] for s in w for t in qt):
                continue
            if any(SU[t][s] & self.gold_units[(gid, t)] for s in w for t in gt if t):
                return True
        return False

    def yhop(self, i, j) -> bool:
        """y-hop(i, j): some sentence holds a WORD question unit of i whose span lies inside the span of a RUN unit that
        contains gold j (F2 containment, the y link; `Slide.contain`, any occurrence pair)"""
        gq, gg = self.q_units[(i, "WORD")], self.gold_units[(j, "RUN")]
        if not gq or not gg:
            return False
        post = self.space.tiers["RUN"].postings
        for s in sorted(set(p for u in gg for p in post[u])):
            for u in gg:
                for q in gq:
                    if q in self.SU["WORD"][s] and u in self.SU["RUN"][s] and self.slide.contain("RUN", u, "WORD", q, s) is not None:
                        return True
        return False

    # ---- the report (the lines of probe_hops.txt, in its order) ------------------------------------------------------
    def report(self) -> List[str]:
        out: List[str] = []
        P = out.append
        ids, N, twohop = self.ids, self.N, self.twohop
        P("intra2 n=%d  one-hop (s1, RUN or WORD, same-tier) = %d  two-hop (gold unit exists, not one hop) = %d  tok = %d"
          % (len(ids), sum(self.base.values()), len(twohop), len(self.tok)))
        P("two-hop ids: " + " ".join(twohop))
        P("")
        P("| window | #windows | same-tier RUN|WORD: hop (of 69) | of the %d two-hop | RUN only: hop | of two-hop | any-tier mix (q any of 3 tiers, gold any of 3) | of two-hop | chance: other golds reached per question, median / mean (of 68) |" % len(twohop))
        P("|---|---|---|---|---|---|---|---|---|")
        for k in KINDS:
            W = self.windows(k)
            h = {i: self.hop(i, W, RW, RW) for i in ids}
            hr = {i: self.hop(i, W, ("RUN",), ("RUN",)) for i in ids}
            hm = {i: self.hop(i, W, TIERS, TIERS + ("",)) for i in ids}
            ch = [sum(1 for j in ids if j != i and self.hop(i, W, ("RUN",), ("RUN",), gid=j)) for i in ids]
            P("| %s | %d | %d | %d | %d | %d | %d | %d | %s / %s |" % (k, len(W), sum(h.values()), sum(h[i] for i in twohop), sum(hr.values()),
              sum(hr[i] for i in twohop), sum(hm.values()), sum(hm[i] for i in twohop), fmt_median(ch), mean1(ch)))
        P("")
        P("per two-hop item: id | gold | evidence | article sentence idx holding a q unit (RUN|WORD) | gold-unit sentences (idx) | min distance | a2 RUN | a2 RUN|WORD")
        W2 = self.windows("a2")
        for i in twohop:
            gs = sorted({s for s in range(N) for t in RW if self.SU[t][s] & self.gold_units[(i, t)]})
            qs = sorted({s for s in range(N) for t in RW if self.SU[t][s] & self.q_units[(i, t)]})
            arts = {self.art[s] for s in gs}
            qa = [self.idx[s] for s in qs if self.art[s] in arts]
            ga = [(self.art[s], self.idx[s]) for s in gs]
            dist = min((abs(a - b) for a in qs for b in gs if self.art[a] == self.art[b]), default=None)
            # the probe cut columns 3 and 5 to their first 2 / 4 entries without saying so; printed whole here (L-531 (5))
            P("%s | %s | %s | %s | %s | %s | %s | %s" % (i, self.bank[i]["gold"], sorted(arts), qa, ga, dist,
              self.hop(i, W2, ("RUN",), ("RUN",)), self.hop(i, W2, RW, RW)))
        P("")
        # sizes: distinct units per pack per tier
        P("| pack | tier | #packs | units median | p90 | max | min L (6L+1>=n) median / p90 | seat-swap pairs C(6L+1,2) at median L |")
        P("|---|---|---|---|---|---|---|---|")
        for k, span in (("s1", 1), ("a2", 2), ("a3", 3)):
            W = [w for w in self.windows(k) if len(w) == span]
            for t in TIERS:
                sz = sorted(len(set().union(*[self.SU[t][s] for s in w])) for w in W)
                Ls = sorted(min_len(n) for n in sz)
                Lm = Ls[len(Ls) // 2]
                P("| %s | %s | %d | %s | %d | %d | %d / %d | %d |" % (k, t, len(W), fmt_median(sz), p90(sz), sz[-1], Lm, p90(Ls), (6 * Lm + 1) * (6 * Lm) // 2))
            allsz = sorted(sum(len(set().union(*[self.SU[t][s] for s in w])) for t in TIERS) for w in W)
            rwsz = sorted(sum(len(set().union(*[self.SU[t][s] for s in w])) for t in RW) for w in W)
            # the probe fed the (possibly fractional) median to mlp(); the same here, exactly
            P("| %s | RUN+WORD+CHAR | %d | %s | %d | %d | %d / - | - |" % (k, len(W), fmt_median(allsz), p90(allsz), allsz[-1], min_len(median(allsz))))
            P("| %s | RUN+WORD | %d | %s | %d | %d | %d / - | - |" % (k, len(W), fmt_median(rwsz), p90(rwsz), rwsz[-1], min_len(median(rwsz))))
        P("")
        # F2 containment links inside one sentence
        si = self.slide.spans
        rw, wc = [], []
        for s in range(N):
            R, Wd, C = si.spans("RUN", s), si.spans("WORD", s), si.spans("CHAR", s)
            rw.append(sum(1 for a in R for b in Wd if a[0] <= b[0] and b[1] <= a[1]))
            wc.append(sum(1 for a in Wd for b in C if a[0] <= b[0] and b[1] <= a[1]))
        rw.sort(); wc.sort()
        P("F2 containment links per sentence: RUN>WORD median %s p90 %d max %d; WORD>CHAR median %s p90 %d max %d"
          % (fmt_median(rw), p90(rw), rw[-1], fmt_median(wc), p90(wc), wc[-1]))
        P("articles %d, sentences %d, articles with 1 sentence %d" % (len(self.slide.articles), N, len(self.slide.singletons())))
        # ---- part 2
        P("")
        t9 = self.t9_check()
        if t9 is not None:
            P("question units recomputed from bank2.tsv equal the T9 records: %d / %d" % t9)
        P("two-hop items inside the evidence article: id | evidence | article length | idx of sentences holding a q unit (same tier as a gold unit of that sentence? no: any RUN|WORD q unit) | gold sentence idx | min |q_idx - gold_idx|")
        for i in twohop:
            a, e = self.bank[i]["evidence"].rsplit("#", 1)
            e = int(e)
            sids = [s for s in range(N) if self.art[s] == a]
            qi = [self.idx[s] for s in sids if any(self.SU[t][s] & self.q_units[(i, t)] for t in RW)]
            P("%s | %s | %d | %s | %d | %d" % (i, self.bank[i]["evidence"], len(sids), qi, e, min(abs(x - e) for x in qi) if qi else -1))
        P("")
        P("| window | intra2 pool of RUN units median / p90 | unans pool median / p90 | unans with a non-empty pool |")
        P("|---|---|---|---|")
        for kname in ("s1", "a2", "a3", "art"):
            W = self.windows(kname)

            def pool(i):
                acc = set()
                for w in W:
                    if any(self.SU["RUN"][s] & self.q_units[(i, "RUN")] for s in w):
                        for s in w:
                            acc |= self.SU["RUN"][s]
                return len(acc)
            pi = sorted(pool(i) for i in ids)
            pu = sorted(pool(k) for k in self.unans)
            P("| %s | %s / %d | %s / %d | %d / %d |" % (kname, fmt_median(pi), p90(pi), fmt_median(pu), p90(pu), sum(1 for x in pu if x), len(pu)))
        for kname in ("s1", "a2", "a3"):
            W = self.windows(kname)
            hm = {i: self.hop(i, W, RW, RW + ("",)) for i in ids}
            P("mixed RUN|WORD %s: %d of 69, %d of the 10 two-hop" % (kname, sum(hm.values()), sum(hm[i] for i in twohop)))
        # ---- part 3
        P("")
        P("two-hop items, evidence sentence: question units present per tier | gold units present per tier")
        for i in twohop:
            a, e = self.bank[i]["evidence"].rsplit("#", 1)
            s = next(x for x in range(N) if self.art[x] == a and self.idx[x] == int(e))
            qp = {t: sorted(self.SU[t][s] & self.q_units[(i, t)]) for t in RW}
            gp = {t: sorted(self.SU[t][s] & self.gold_units[(i, t)]) for t in RW}
            prev = [x for x in range(N) if self.art[x] == a and self.idx[x] == int(e) - 1]
            qprev = {t: sorted(self.SU[t][prev[0]] & self.q_units[(i, t)]) for t in RW} if prev else None
            P("%s | Q %s | G %s | q in sentence N-1: %s" % (i, qp, gp, qprev))
        for kname in ("s1", "a2"):
            W = self.windows(kname)
            ch = sorted(sum(1 for j in ids if j != i and self.hop(i, W, RW, RW + ("",), gid=j)) for i in ids)
            P("mixed RUN|WORD chance %s: other golds reached per question median %s mean %s (of 68)" % (kname, fmt_median(ch), mean1(ch)))
        # ---- part 4
        P("")
        P("two-hop items: in the evidence sentence, is an occurrence of a WORD question unit inside the span of the RUN gold unit (F2 containment)?")
        cont = 0
        for i in twohop:
            a, e = self.bank[i]["evidence"].rsplit("#", 1)
            s = next(x for x in range(N) if self.art[x] == a and self.idx[x] == int(e))
            ru, wu = self.space.tiers["RUN"].sentence_units[s], self.space.tiers["WORD"].sentence_units[s]
            rs, ws = si.spans("RUN", s), si.spans("WORD", s)
            gold_occ = [rs[k] for k, u in enumerate(ru) if u in self.gold_units[(i, "RUN")]]
            q_occ = [(u, ws[k]) for k, u in enumerate(wu) if u in self.q_units[(i, "WORD")]]
            inside = sorted({u for u, (a2, b2) in q_occ for (a1, b1) in gold_occ if a1 <= a2 and b2 <= b1})
            outside = sorted({u for u, _ in q_occ} - set(inside))
            cont += bool(inside)
            P("%s | gold RUN %s | WORD q inside the gold span: %s | WORD q elsewhere in the sentence: %s" % (i, sorted(self.gold_units[(i, "RUN")] & set(ru)), inside, outside))
        P("contained: %d of %d" % (cont, len(twohop)))
        # ---- part 5
        yh = {i: self.yhop(i, i) for i in ids}
        W2 = self.windows("a2")
        same2 = {i: self.hop(i, W2, ("RUN",), ("RUN",)) or self.base[i] for i in ids}
        P("y-hop (WORD q inside RUN gold span, one sentence): %d of 69; new over the 41 one-hop: %d; of the 10 two-hop: %d"
          % (sum(yh.values()), sum(1 for i in ids if yh[i] and not self.base[i]), sum(yh[i] for i in twohop)))
        P("union one-hop(s1) | a2 RUN same-tier | y-hop: %d of 69; two-hop covered %d (%s)"
          % (sum(1 for i in ids if self.base[i] or same2[i] or yh[i]), sum(1 for i in twohop if same2[i] or yh[i]),
             " ".join(i for i in twohop if not (same2[i] or yh[i])) + " left"))
        ych = sorted(sum(1 for j in ids if j != i and self.yhop(i, j)) for i in ids)
        P("y-hop chance: other golds reached per question median %s mean %s (of 68)" % (fmt_median(ych), mean1(ych)))
        # ---- part 6
        for kname in ("s1", "a2"):
            W = self.windows(kname)
            c = sorted(sum(1 for w in W if any(self.SU["RUN"][s] & self.q_units[(i, "RUN")] for s in w)) for i in ids)
            cu = sorted(sum(1 for w in W if any(self.SU["RUN"][s] & self.q_units[(k, "RUN")] for s in w)) for k in self.unans)
            P("windows read per question (%s, RUN): intra2 median %s p90 %d max %d; unans median %s max %d"
              % (kname, fmt_median(c), p90(c), c[-1], fmt_median(cu), cu[-1]))
        return out

    # ---- a short, structured form for the test --------------------------------------------------------------------
    def numbers(self) -> dict:
        ids, twohop = self.ids, self.twohop
        d = {"n": len(ids), "one_hop": sum(self.base.values()), "two_hop": len(twohop), "tok": len(self.tok), "two_hop_ids": list(twohop)}
        for k in KINDS:
            W = self.windows(k)
            h = {i: self.hop(i, W, RW, RW) for i in ids}
            hr = {i: self.hop(i, W, ("RUN",), ("RUN",)) for i in ids}
            ch = [sum(1 for j in ids if j != i and self.hop(i, W, ("RUN",), ("RUN",), gid=j)) for i in ids]
            d[k] = {"windows": len(W), "rw": sum(h.values()), "rw_two_hop": sum(h[i] for i in twohop),
                    "run": sum(hr.values()), "run_two_hop": sum(hr[i] for i in twohop),
                    "chance_median": fmt_median(ch), "chance_mean": mean1(ch)}
        return d


def main() -> int:
    for line in Reach().report():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

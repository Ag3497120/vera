"""G3 probe (designer, seconds): how many bank2 intra2 golds become 'one hop' when sentence N and N+1 form one unit
(a two-sentence pack), and how big such a pack is per tier.  Read-only; no product code is changed.
Definitions follow experiments/line3/f1/reach.py (T9 audit): question units = cycle.make_context(query_units).energy_units
from t9/audit/raw/ask_fulllead_standard.jsonl; gold units = units whose normalised text contains a gold alternative.
usage: PYTHONPATH=. python experiments/line3/g3/probe_hops.py > experiments/line3/g3/probe_hops.txt"""
import json, os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T9 = os.path.join(ROOT, "experiments/line3/t9")
sys.path.insert(0, ROOT); sys.path.insert(0, T9)
import scorer as S                                         # noqa: E402
from verantyx.line3 import cycle as cy                     # noqa: E402
from verantyx.line3.space import build_space, load_jsonl   # noqa: E402
from verantyx.line3.granularity import SpanIndex           # noqa: E402
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
rows = load_jsonl(FL)
space = build_space(rows)
art = [r["source"].rsplit("#", 1)[0] for r in rows]
idx = [int(r["source"].rsplit("#", 1)[1]) for r in rows]
N = len(rows)
TIERS = ("RUN", "WORD", "CHAR")
SU = {t: [set(u) for u in space.tiers[t].sentence_units] for t in TIERS}
recs = sorted((json.loads(l) for l in open(os.path.join(T9, "audit/raw/ask_fulllead_standard.jsonl"), encoding="utf-8")), key=lambda r: r["id"])
gold_units = {}
q_units = {}
for r in recs:
    for t in TIERS:
        ts = space.tiers[t]
        gold_units[(r["id"], t)] = {u for u in ts.units() if any(g in S.norm(u) for g in S.golds(r["gold"]))}
        q_units[(r["id"], t)] = set(cy.make_context(tuple(r["layer0"][t]["query_units"])).energy_units)

def windows(kind):
    """list of tuples of sids.  s1 = one sentence; a2 = (N, N+1) inside one article; f2 = (N, N+1) in file order
    (crosses article ends); a3 = three consecutive in one article; art = the whole article."""
    if kind == "s1":
        return [(i,) for i in range(N)]
    if kind == "a2":      # the pack of sentence i = (i, i+1) inside one article; the last sentence of an article = (i,) alone
        return [tuple(j for j in (i, i + 1) if j < N and art[j] == art[i]) for i in range(N)]
    if kind == "f2":
        return [(i, i + 1) for i in range(N - 1)]
    if kind == "a3":      # two adjacent packs read together = (i, i+1, i+2) inside one article, cut at the article end
        return [tuple(j for j in (i, i + 1, i + 2) if j < N and art[j] == art[i]) for i in range(N)]
    if kind == "art":
        d = {}
        for i in range(N):
            d.setdefault(art[i], []).append(i)
        return [tuple(v) for v in d.values()]
    raise ValueError(kind)

def hop(rid, W, qt, gt, gid=None):
    """qt == gt: some window holds a question unit AND a gold unit (of question gid) OF THE SAME TIER t in qt (reach.py's rule);
    qt != gt (the mix row): a question unit of any tier in qt and a gold unit of any tier in gt (tiers may differ)"""
    gid = gid or rid
    if qt == gt:
        return any(any(SU[t][s] & q_units[(rid, t)] for s in w) and any(SU[t][s] & gold_units[(gid, t)] for s in w) for w in W for t in qt)
    for w in W:
        hq = any(SU[t][s] & q_units[(rid, t)] for s in w for t in qt)
        if not hq:
            continue
        if any(SU[t][s] & gold_units[(gid, t)] for s in w for t in gt if t):
            return True
    return False

ids = [r["id"] for r in recs]
gold_exists = {i: any(gold_units[(i, t)] for t in ("RUN", "WORD")) for i in ids}
RW = ("RUN", "WORD")
base = {i: hop(i, windows("s1"), RW, RW) for i in ids}
twohop = [i for i in ids if gold_exists[i] and not base[i]]
tok = [i for i in ids if not gold_exists[i]]
print("intra2 n=%d  one-hop (s1, RUN or WORD, same-tier) = %d  two-hop (gold unit exists, not one hop) = %d  tok = %d" % (len(ids), sum(base.values()), len(twohop), len(tok)))
print("two-hop ids:", " ".join(twohop))
print()
print("| window | #windows | same-tier RUN|WORD: hop (of 69) | of the %d two-hop | RUN only: hop | of two-hop | any-tier mix (q any of 3 tiers, gold any of 3) | of two-hop | chance: other golds reached per question, median / mean (of 68) |" % len(twohop))
print("|---|---|---|---|---|---|---|---|---|")
for k in ("s1", "a2", "f2", "a3", "art"):
    W = windows(k)
    h = {i: hop(i, W, RW, RW) for i in ids}
    hr = {i: hop(i, W, ("RUN",), ("RUN",)) for i in ids}
    hm = {i: hop(i, W, TIERS, TIERS + ("",)) for i in ids}
    ch = []
    for i in ids:
        ch.append(sum(1 for j in ids if j != i and hop(i, W, ("RUN",), ("RUN",), gid=j)))
    print("| %s | %d | %d | %d | %d | %d | %d | %d | %s / %.1f |" % (k, len(W), sum(h.values()), sum(h[i] for i in twohop), sum(hr.values()), sum(hr[i] for i in twohop),
          sum(hm.values()), sum(hm[i] for i in twohop), st.median(ch), sum(ch) / len(ch)))
print()
# per two-hop item: evidence index, sentences of the article holding a question unit (RUN|WORD), distance to the gold sentence
print("per two-hop item: id | gold | evidence | article sentence idx holding a q unit (RUN|WORD) | gold-unit sentences (idx) | min distance | a2 RUN | a2 RUN|WORD")
W2 = windows("a2")
for r in recs:
    i = r["id"]
    if i not in twohop:
        continue
    ev_t, ev_i = r.get("evidence", "?#?").rsplit("#", 1) if "evidence" in r else (None, None)
    gs = sorted({s for s in range(N) for t in RW if SU[t][s] & gold_units[(i, t)]})
    qs = sorted({s for s in range(N) for t in RW if SU[t][s] & q_units[(i, t)]})
    # restrict to the article of the gold sentence(s)
    arts = {art[s] for s in gs}
    qa = [idx[s] for s in qs if art[s] in arts]
    ga = [(art[s], idx[s]) for s in gs]
    dist = min((abs(a - b) for a in qs for b in gs if art[a] == art[b]), default=None)
    print("%s | %s | %s | %s | %s | %s | %s | %s" % (i, r["gold"], sorted(arts)[:2], qa, ga[:4], dist,
          hop(i, W2, ("RUN",), ("RUN",)), hop(i, W2, RW, RW)))
print()
# sizes: distinct units per pack per tier
def mlp(n):
    L = 0
    while 6 * L + 1 < n:
        L += 1
    return L
print("| pack | tier | #packs | units median | p90 | max | min L (6L+1>=n) median / p90 | seat-swap pairs C(6L+1,2) at median L |")
print("|---|---|---|---|---|---|---|---|")
for k in ("s1", "a2", "a3"):
    W = [w for w in windows(k) if len(w) == {"s1": 1, "a2": 2, "a3": 3}[k]]
    tot = []
    for t in TIERS:
        sz = sorted(len(set().union(*[SU[t][s] for s in w])) for w in W)
        tot.append(sz)
        Ls = sorted(mlp(n) for n in sz)
        p90 = sz[int(0.9 * (len(sz) - 1))]
        Lm = Ls[len(Ls) // 2]
        print("| %s | %s | %d | %s | %d | %d | %d / %d | %d |" % (k, t, len(W), st.median(sz), p90, sz[-1], Lm, Ls[int(0.9 * (len(Ls) - 1))], (6 * Lm + 1) * (6 * Lm) // 2))
    # all three tiers in one pack (units of different tiers kept apart: RUN:x, WORD:x, CHAR:x)
    allsz = sorted(sum(len(set().union(*[SU[t][s] for s in w])) for t in TIERS) for w in W)
    rwsz = sorted(sum(len(set().union(*[SU[t][s] for s in w])) for t in ("RUN", "WORD")) for w in W)
    print("| %s | RUN+WORD+CHAR | %d | %s | %d | %d | %d / - | - |" % (k, len(W), st.median(allsz), allsz[int(0.9 * (len(allsz) - 1))], allsz[-1], mlp(st.median(allsz))))
    print("| %s | RUN+WORD | %d | %s | %d | %d | %d / - | - |" % (k, len(W), st.median(rwsz), rwsz[int(0.9 * (len(rwsz) - 1))], rwsz[-1], mlp(st.median(rwsz))))
print()
# F2 span links inside one sentence: RUN occurrence contains WORD occurrence; WORD contains CHAR (counts per sentence)
si = SpanIndex(space)
rw, wc = [], []
for s in range(N):
    R, Wd, C = si.spans("RUN", s), si.spans("WORD", s), si.spans("CHAR", s)
    rw.append(sum(1 for a in R for b in Wd if a[0] <= b[0] and b[1] <= a[1]))
    wc.append(sum(1 for a in Wd for b in C if a[0] <= b[0] and b[1] <= a[1]))
rw.sort(); wc.sort()
print("F2 containment links per sentence: RUN>WORD median %s p90 %d max %d; WORD>CHAR median %s p90 %d max %d" % (st.median(rw), rw[int(0.9 * (N - 1))], rw[-1], st.median(wc), wc[int(0.9 * (N - 1))], wc[-1]))
print("articles %d, sentences %d, articles with 1 sentence %d" % (len(set(art)), N, sum(1 for a in set(art) if art.count(a) == 1)))

# ---- part 2: per two-hop item inside its evidence article; pool sizes; unans
print()
bank = {}
for line in open(os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv"), encoding="utf-8"):
    if line.startswith("#"):
        continue
    f = line.rstrip("\n").split("\t")
    bank[f[0]] = dict(zip(("id", "kind", "corpus", "subject", "question", "gold", "evidence", "audit"), f))
def qunits(t, question):
    flt = space.tiers[t].unit_filter
    us = tuple(u for u in cy.split_question(t, question) if not (flt is not None and flt(u)))
    return set(cy.make_context(us).energy_units)
same = sum(qunits(t, bank[i]["question"]) == q_units[(i, t)] for i in ids for t in TIERS)
print("question units recomputed from bank2.tsv equal the T9 records: %d / %d" % (same, 3 * len(ids)))
print("two-hop items inside the evidence article: id | evidence | article length | idx of sentences holding a q unit (same tier as a gold unit of that sentence? no: any RUN|WORD q unit) | gold sentence idx | min |q_idx - gold_idx|")
for i in twohop:
    a, e = bank[i]["evidence"].rsplit("#", 1)
    e = int(e)
    sids = [s for s in range(N) if art[s] == a]
    qi = [idx[s] for s in sids if any(SU[t][s] & q_units[(i, t)] for t in RW)]
    print("%s | %s | %d | %s | %d | %d" % (i, bank[i]["evidence"], len(sids), qi, e, min(abs(x - e) for x in qi) if qi else -1))
print()
# pool = distinct RUN units sharing a window with a RUN question unit (what a read of the pack would face)
uq = [k for k in bank if bank[k]["kind"] == "unans" and bank[k]["corpus"] == "fulllead"]
for t in TIERS:
    for k in uq:
        q_units[(k, t)] = qunits(t, bank[k]["question"])
print("| window | intra2 pool of RUN units median / p90 | unans pool median / p90 | unans with a non-empty pool |")
print("|---|---|---|---|")
for kname in ("s1", "a2", "a3", "art"):
    W = windows(kname)
    def pool(i):
        acc = set()
        for w in W:
            if any(SU["RUN"][s] & q_units[(i, "RUN")] for s in w):
                for s in w:
                    acc |= SU["RUN"][s]
        return len(acc)
    pi = sorted(pool(i) for i in ids); pu = sorted(pool(k) for k in uq)
    print("| %s | %s / %d | %s / %d | %d / %d |" % (kname, st.median(pi), pi[int(0.9 * (len(pi) - 1))], st.median(pu), pu[int(0.9 * (len(pu) - 1))], sum(1 for x in pu if x), len(pu)))
# RUN|WORD mixed-tier hop (question unit of RUN or WORD, gold unit of RUN or WORD, tiers may differ), s1 and a2
for kname in ("s1", "a2", "a3"):
    W = windows(kname)
    hm = {i: hop(i, W, RW, RW + ("",)) for i in ids}
    print("mixed RUN|WORD %s: %d of 69, %d of the 10 two-hop" % (kname, sum(hm.values()), sum(hm[i] for i in twohop)))

# ---- part 3: what joins question and gold in the evidence sentence of the two-hop items (tiers named)
print()
print("two-hop items, evidence sentence: question units present per tier | gold units present per tier")
for i in twohop:
    a, e = bank[i]["evidence"].rsplit("#", 1)
    s = next(x for x in range(N) if art[x] == a and idx[x] == int(e))
    qp = {t: sorted(SU[t][s] & q_units[(i, t)]) for t in RW}
    gp = {t: sorted(SU[t][s] & gold_units[(i, t)]) for t in RW}
    prev = [x for x in range(N) if art[x] == a and idx[x] == int(e) - 1]
    qprev = {t: sorted(SU[t][prev[0]] & q_units[(i, t)]) for t in RW} if prev else None
    print("%s | Q %s | G %s | q in sentence N-1: %s" % (i, qp, gp, qprev))
# mixed-tier chance: other golds (RUN|WORD) reached per question with a RUN|WORD question unit, tiers may differ
for kname in ("s1", "a2"):
    W = windows(kname)
    ch = sorted(sum(1 for j in ids if j != i and hop(i, W, RW, RW + ("",), gid=j)) for i in ids)
    print("mixed RUN|WORD chance %s: other golds reached per question median %s mean %.1f (of 68)" % (kname, st.median(ch), sum(ch) / len(ch)))

# ---- part 4: F2 containment between the question's WORD units and the gold's RUN unit in the evidence sentence
print()
print("two-hop items: in the evidence sentence, is an occurrence of a WORD question unit inside the span of the RUN gold unit (F2 containment)?")
cont = 0
for i in twohop:
    a, e = bank[i]["evidence"].rsplit("#", 1)
    s = next(x for x in range(N) if art[x] == a and idx[x] == int(e))
    ru, wu = space.tiers["RUN"].sentence_units[s], space.tiers["WORD"].sentence_units[s]
    rs, ws = si.spans("RUN", s), si.spans("WORD", s)
    gold_occ = [rs[k] for k, u in enumerate(ru) if u in gold_units[(i, "RUN")]]
    q_occ = [(u, ws[k]) for k, u in enumerate(wu) if u in q_units[(i, "WORD")]]
    inside = sorted({u for u, (a2, b2) in q_occ for (a1, b1) in gold_occ if a1 <= a2 and b2 <= b1})
    outside = sorted({u for u, _ in q_occ} - set(inside))
    cont += bool(inside)
    print("%s | gold RUN %s | WORD q inside the gold span: %s | WORD q elsewhere in the sentence: %s" % (i, sorted(gold_units[(i, "RUN")] & set(ru)), inside, outside))
print("contained: %d of %d" % (cont, len(twohop)))

# ---- part 5: the y (granularity) link as a reach rule over the whole corpus, with its chance control
# y-hop(i, j): some sentence holds a WORD question unit of i whose span lies inside the span of a RUN unit containing gold j
def yhop(i, j):
    gq = q_units[(i, "WORD")]
    gg = gold_units[(j, "RUN")]
    if not gq or not gg:
        return False
    for s in set(p for u in gg for p in space.tiers["RUN"].postings[u]):
        ru, wu = space.tiers["RUN"].sentence_units[s], space.tiers["WORD"].sentence_units[s]
        rs, ws = si.spans("RUN", s), si.spans("WORD", s)
        G = [rs[k] for k, u in enumerate(ru) if u in gg]
        if any(a1 <= ws[k][0] and ws[k][1] <= b1 for k, u in enumerate(wu) if u in gq for (a1, b1) in G):
            return True
    return False
yh = {i: yhop(i, i) for i in ids}
W2 = windows("a2")
same2 = {i: hop(i, W2, ("RUN",), ("RUN",)) or base[i] for i in ids}
print("y-hop (WORD q inside RUN gold span, one sentence): %d of 69; new over the 41 one-hop: %d; of the 10 two-hop: %d" % (sum(yh.values()), sum(1 for i in ids if yh[i] and not base[i]), sum(yh[i] for i in twohop)))
print("union one-hop(s1) | a2 RUN same-tier | y-hop: %d of 69; two-hop covered %d (%s)" % (sum(1 for i in ids if base[i] or same2[i] or yh[i]), sum(1 for i in twohop if same2[i] or yh[i]), " ".join(i for i in twohop if not (same2[i] or yh[i])) + " left"))
ych = sorted(sum(1 for j in ids if j != i and yhop(i, j)) for i in ids)
print("y-hop chance: other golds reached per question median %s mean %.1f (of 68)" % (st.median(ych), sum(ych) / len(ych)))

# ---- part 6: how many pack crosses a question would read (windows holding a RUN question unit; V1 analogue)
for kname in ("s1", "a2"):
    W = [w for w in windows(kname)]
    c = sorted(sum(1 for w in W if any(SU["RUN"][s] & q_units[(i, "RUN")] for s in w)) for i in ids)
    cu = sorted(sum(1 for w in W if any(SU["RUN"][s] & q_units[(k, "RUN")] for s in w)) for k in uq)
    print("windows read per question (%s, RUN): intra2 median %s p90 %d max %d; unans median %s max %d" % (kname, st.median(c), c[int(0.9 * (len(c) - 1))], c[-1], st.median(cu), cu[-1]))

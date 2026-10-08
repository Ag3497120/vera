"""G2 probe 1: P7 particles after content words (fulllead_sents, WORD cut), and on bank2 fulllead questions / golds."""
import json, sys, collections as C
import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from verantyx.line3.space import _get_tagger, strip_attribution
from verantyx.line3.funcwords import is_function_unit
P7 = ("は", "の", "に", "を", "が", "で", "と")
INTERROG = {"何", "なに", "なん", "どこ", "誰", "だれ", "いつ", "どの", "どれ", "いくつ", "どう", "どんな", "いくら", "なぜ", "何故", "どちら"}
tag = _get_tagger()
def toks(text):
    out, pos = [], 0
    for w in tag(text):
        s = w.surface
        i = text.find(s, pos)
        if i < 0: i = pos
        out.append((s, i, i + len(s), w.feature.pos1))
        pos = i + len(s)
    return out
def letter(s): return any(c.isalnum() for c in s)
def is_content(s): return letter(s) and not is_function_unit(s, "WORD")
def nxt_p_raw(ts, j):
    """particle right after token index j (next token), or label."""
    if j + 1 >= len(ts): return "END"
    s = ts[j + 1][0]
    if s in P7: return s
    if not letter(s): return "PUNCT"
    return "func:" + s if is_function_unit(s, "WORD") else "content"

def nxt_p(ts, j):
    """as nxt_p_raw but punctuation tokens are skipped (= the WORD unit sequence, L-32); END/PUNCT-final -> END"""
    k = j + 1
    while k < len(ts) and not letter(ts[k][0]):
        k += 1
    if k >= len(ts): return "END"
    s = ts[k][0]
    if s in P7: return s
    return "func:" + s if is_function_unit(s, "WORD") else "content"
sents = [json.loads(l) for l in open(ROOT + "/experiments/line3/bank2/data/fulllead_sents.jsonl", encoding="utf-8")]
src = {r["source"]: r["sent"] for r in sents}
# (1) corpus: particle after content tokens
cnt = C.Counter(); tot = 0; unit_p = C.defaultdict(C.Counter); unit_order = None
for r in sents:
    ts = toks(strip_attribution(r["sent"]))
    for j, (s, a, b, p1) in enumerate(ts):
        if is_content(s):
            tot += 1; lab = nxt_p(ts, j); cnt[lab] += 1; unit_p[s][lab] += 1
print("corpus content tokens", tot)
print(" after P7:", {p: cnt[p] for p in P7}, "sum", sum(cnt[p] for p in P7))
print(" other:", cnt.most_common(12))
# dominant particle per content unit type (units with >=1 P7 follower)
dom = C.Counter(); ties = 0; withp = 0
for u, c in unit_p.items():
    pc = {p: c[p] for p in P7 if c[p]}
    if not pc: continue
    withp += 1
    m = max(pc.values()); w = [p for p in pc if pc[p] == m]
    if len(w) > 1: ties += 1
    else: dom[w[0]] += 1
print(" content types", len(unit_p), "with a P7 follower", withp, "dominant:", dict(dom), "tied", ties)
multi = sum(1 for u, c in unit_p.items() if sum(1 for p in P7 if c[p]) >= 2)
print(" types followed by >=2 distinct P7:", multi)
# (2) bank2 fulllead
rows = [l.rstrip("\n").split("\t") for l in open(ROOT + "/experiments/line3/bank2/bank2.tsv", encoding="utf-8") if not l.startswith("#")]
rows = [r for r in rows if r[2] == "fulllead"]
qcnt = C.Counter(); intq = C.Counter(); goldp = C.Counter(); joint = C.Counter(); order = C.Counter(); n_int = 0
perq = []
for r in rows:
    qid, kind, _, subj, q, gold, ev = r[:7]
    qt = toks(q)
    for j, (s, a, b, p1) in enumerate(qt):
        if is_content(s): qcnt[nxt_p(qt, j)] += 1
    # interrogative phrase: interrogative token + following content tokens (counters)
    ip = None
    for j, (s, a, b, p1) in enumerate(qt):
        if s in INTERROG:
            k = j
            while k + 1 < len(qt) and is_content(qt[k + 1][0]): k += 1
            ip = nxt_p(qt, k); break
    if ip is not None: n_int += 1
    intq[(kind, ip)] += 1
    if kind != "intra2": continue
    sent = strip_attribution(src[ev]); g = None
    for alt in gold.split("|"):
        i = sent.find(alt)
        if i >= 0: g = (alt, i, i + len(alt)); break
    if g is None: perq.append((qid, ip, None)); goldp["NOTFOUND"] += 1; continue
    st = toks(sent)
    # token whose end == gold end, else token containing gold end
    gl = "MIDTOKEN"
    for j, (s, a, b, p1) in enumerate(st):
        if b == g[2]: gl = nxt_p(st, j); break
    goldp[gl] += 1; joint[(ip, gl)] += 1; perq.append((qid, ip, gl))
    # order: question content tokens found in the evidence sentence, before/after the gold
    for s, a, b, p1 in qt:
        if is_content(s) and s not in gold:
            i = sent.find(s)
            if i >= 0: order["before" if i < g[1] else "after"] += 1
print("bank2 fulllead questions", len(rows), "with interrogative", n_int)
print(" particle after question content tokens:", {p: qcnt[p] for p in P7}, "other", qcnt.most_common(8))
print(" particle after interrogative phrase (kind, p):", sorted(intq.items(), key=lambda x: -x[1]))
print(" intra2 particle after gold in evidence:", goldp.most_common())
match = sum(v for (a, b), v in joint.items() if a == b and a in P7)
print(" joint intra2 (interrog p, gold p):", sorted(joint.items(), key=lambda x: -x[1]))
print(" match (same P7):", match, "of", sum(joint.values()))
# chance: sum_p P(ip=p) * P(gl=p) * n
n = sum(joint.values()); ipm = C.Counter(); glm = C.Counter()
for (a, b), v in joint.items(): ipm[a] += v; glm[b] += v
print(" chance match:", round(sum(ipm[p] * glm[p] for p in P7) / n, 2))
print(" order of question content tokens in evidence vs gold:", dict(order))
json.dump(perq, open(sys.argv[1] if len(sys.argv) > 1 else "/dev/null", "w"), ensure_ascii=False)

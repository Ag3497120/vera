"""evidence.v5 offline probe (no model, no API): every stretch of 1..10 WORD units of every sentence of the fulllead corpus, through the PRODUCT gate (title scope), for
evidence.v2 / v3 / v4 / v5 and the two ablations of v5 (v5 without SU, v5 without TW: the `off` argument of `_judge_v5`, tests only), over the DEV sets bank2 + bank4 (129 items), bank6 (60
items) and bank7 (79 items; a dev set since the v4 probe, commit e930b96a).

    PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/loom/ev5/sweep.py {dev129|bank6|bank7} [nproc]

It reads bank2, bank4, bank6 and bank7 only.  Mode bank8 is the ONE held-out judging run of v5 (OP-PUB-6), run once after the freeze (evidence.py 712249cc); bank_ls is never opened here.  Writes ev5/out_<set>.json and prints the summary."""
import csv, hashlib, json, multiprocessing as mp, os, re, sys, time, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, ROOT)
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus

VERS = ["evidence.v2", "evidence.v3", "evidence.v4", "evidence.v5", "v5-noSU", "v5-noTW"]
OFFS = {"v5-noSU": frozenset({"SU"}), "v5-noTW": frozenset({"TW"})}
LOOMX = os.path.join(ROOT, "experiments/line3/loom")
C = Corpus.load(open(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), "rb").read())
ANSWERABLE_LOOM = ("I2-001", "I2-008", "I2-013", "I2-025", "I2-034", "I2-041", "R2-I013")


def norm(x):
    return "".join(ch for ch in unicodedata.normalize("NFKC", x).casefold() if not ch.isspace() and ch != "・")


def rd(f, **kw):
    return list(csv.DictReader(open(os.path.join(ROOT, f), encoding="utf-8"), delimiter="\t", **kw))


def dev129():
    tx = {}
    for f in ("tasks_bank2.jsonl", "tasks_unans.jsonl", "tasks_unans_adv.jsonl"):
        for ln in open(os.path.join(LOOMX, f), encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                tx.setdefault(r.get("bank2_id") or r["base"], r["text"])
    b2 = rd("experiments/line3/bank2/bank2.tsv")
    b4 = rd("experiments/line3/bank4/bank4.tsv")
    unans = [r["#id"] for r in b2 if r["kind"] == "unans" and r["corpus"] == "fulllead"] + [r["#id"] for r in b4]
    bases = [b for b in tx if b not in ANSWERABLE_LOOM and (b in unans or b.startswith(("UF-", "R2-U")))]
    items = [{"kind": "ans", "id": r["#id"], "q": r["question"], "gold": [norm(a) for a in r["gold"].split("|")], "shape": "-"} for r in b2 if r["kind"] == "intra2" and r["corpus"] == "fulllead"]
    items += [{"kind": "unans", "id": b, "q": tx[b], "gold": [], "shape": "-"} for b in bases]
    assert len(items) == 129 and len(bases) == 60
    return items


def bank8():
    rows = rd("experiments/line3/bank8/bank8.tsv", quoting=csv.QUOTE_NONE)
    return [{"kind": "ans" if r["kind"] == "ANSWERABLE" else "unans", "id": r["#id"], "q": r["question"], "gold": [norm(g) for g in r["gold"].split("|")], "shape": r["shape"]} for r in rows]


def bank7():
    rows = rd("experiments/line3/bank7/bank7.tsv", quoting=csv.QUOTE_NONE)
    return [{"kind": "ans" if r["kind"] == "ANSWERABLE" else "unans", "id": r["#id"], "q": r["question"], "gold": [norm(g) for g in r["gold"].split("|")], "shape": r["shape"]} for r in rows]


def bank6():
    rows = rd("experiments/line3/bank6/bank6.tsv", quoting=csv.QUOTE_NONE)
    assert len(rows) == 60
    return [{"kind": "ans" if r["kind"] == "ANSWERABLE" else "unans", "id": r["#id"], "q": r["question"], "gold": [norm(g) for g in r["gold"].split("|")], "shape": r["shape"]} for r in rows]


SETNAME = sys.argv[1] if len(sys.argv) > 1 else "dev129"
ITEMS = {"dev129": dev129, "bank6": bank6, "bank7": bank7, "bank8": bank8}[SETNAME]()
SENTS = [(sid, len(ev.view_of(C, sid).units)) for sid in range(C.n_sentences)]


def run_item(idx):
    it = ITEMS[idx]
    qu = ev.question_units(it["q"])
    out = {v: [] for v in VERS}
    for sid, n in SENTS:
        for i in range(n):
            for j in range(i, min(n, i + 10)):
                for v in VERS:
                    x = ev._judge_v5(C, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, OFFS[v]) if v in OFFS else ev.judge_quote(C, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, v)
                    if not x["codes"]:
                        e = x["evidence"] or {}
                        out[v].append([sid, i, j, x["answer"], x.get("reading") or "base", x.get("rules") or [], e.get("via"), x["source"], x["clause"]])
    return it["id"], out, list(ev.subject_chain(qu))


if __name__ == "__main__":
    t = time.time()
    nproc = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    with mp.get_context("fork").Pool(nproc) as pool:
        res = pool.map(run_item, range(len(ITEMS)), chunksize=1)
    sha = hashlib.sha256(open(os.path.join(ROOT, "verantyx/loom/evidence.py"), "rb").read()).hexdigest()
    json.dump({"set": SETNAME, "items": ITEMS, "res": res, "evidence_sha": sha, "seconds": round(time.time() - t)}, open(os.path.join(HERE, "out_%s.json" % SETNAME), "w"), ensure_ascii=False)
    print("done", SETNAME, sha, round(time.time() - t))

"""evidence.v6 offline probe (no model, no API): every stretch of 1..10 WORD units of every sentence of the fulllead corpus, through the PRODUCT gate (title scope), for evidence.v2 and
evidence.v6 and the four ablations of v6 (v6 without CH / SU / TW / NEG: the `off` argument of `_judge_v6`, tests only), over the sets bank2 + bank4 (dev129, 129 items), bank6 (60), bank7 (79) and
bank8 (85; burnt by the one v5 probe, so a dev set now).

    PYTHONPATH=. PYTHONHASHSEED=0 python experiments/line3/loom/ev6/sweep.py {dev129|bank6|bank7|bank8} [nproc]

v6 is a PURE FILTER over v2: for every stretch the script records whether v6 passes where v2 refuses (`_violations`; must be empty) and which stretches v2 passes and v6 refuses, with the codes
(`_lost`).  The ablations are only evaluated where v2 passes (they are filters too, so they pass nowhere else).  It reads bank2, bank4, bank6, bank7 and bank8 only; bank_ls, the hidden folder
and vera1.txt are never opened.  Writes ev6/out_<set>.json and prints the summary."""
import csv, hashlib, json, multiprocessing as mp, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from sweep_util import norm
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus

V2, V6 = "evidence.v2", "evidence.v6"
VERS = [V2, V6, "v6-noCH", "v6-noSU", "v6-noTW", "v6-noNEG"]
OFFS = {"v6-noCH": frozenset({"CH"}), "v6-noSU": frozenset({"SU"}), "v6-noTW": frozenset({"TW"}), "v6-noNEG": frozenset({"NEG"})}
LOOMX = os.path.join(ROOT, "experiments/line3/loom")
C = Corpus.load(open(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), "rb").read())
ANSWERABLE_LOOM = ("I2-001", "I2-008", "I2-013", "I2-025", "I2-034", "I2-041", "R2-I013")


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


def bank_n(n, count):
    rows = rd("experiments/line3/bank%d/bank%d.tsv" % (n, n), quoting=csv.QUOTE_NONE)
    assert len(rows) == count
    return [{"kind": "ans" if r["kind"] == "ANSWERABLE" else "unans", "id": r["#id"], "q": r["question"], "gold": [norm(g) for g in r["gold"].split("|")], "shape": r["shape"]} for r in rows]


SETS = {"dev129": dev129, "bank6": lambda: bank_n(6, 60), "bank7": lambda: bank_n(7, 79), "bank8": lambda: bank_n(8, 85)}
SETNAME = sys.argv[1] if len(sys.argv) > 1 else "dev129"
ITEMS = SETS[SETNAME]()
SENTS = [(sid, len(ev.view_of(C, sid).units)) for sid in range(C.n_sentences)]


def run_item(idx):
    it = ITEMS[idx]
    qu = ev.question_units(it["q"])
    out = {v: [] for v in VERS}
    out["_lost"], out["_violations"] = [], []
    for sid, n in SENTS:
        for i in range(n):
            for j in range(i, min(n, i + 10)):
                x2 = ev.judge_quote(C, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V2)
                x6 = ev.judge_quote(C, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V6)
                if x6["codes"] and x2["codes"]:
                    continue
                r2 = None
                if not x2["codes"]:
                    e = x2["evidence"] or {}
                    r2 = [sid, i, j, x2["answer"], "base", [], e.get("via"), x2["source"], x2["clause"]]
                    out[V2].append(r2)
                    if x6["codes"]:
                        out["_lost"].append([sid, i, j, x2["answer"], x6["codes"], x6["messages"][0] if x6["messages"] else ""])
                    for v, off in OFFS.items():
                        y = ev._judge_v6(C, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, off)
                        if not y["codes"]:
                            out[v].append(r2)
                if not x6["codes"]:
                    e = x6["evidence"] or {}
                    out[V6].append([sid, i, j, x6["answer"], "base", [], e.get("via"), x6["source"], x6["clause"]])
                    if x2["codes"]:
                        out["_violations"].append([sid, i, j, x6["answer"], x2["codes"]])
    return it["id"], out, list(ev.subject_chain(qu))


if __name__ == "__main__":
    t = time.time()
    nproc = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    with mp.get_context("fork").Pool(nproc) as pool:
        res = pool.map(run_item, range(len(ITEMS)), chunksize=1)
    sha = hashlib.sha256(open(os.path.join(ROOT, "verantyx/loom/evidence.py"), "rb").read()).hexdigest()
    json.dump({"set": SETNAME, "items": ITEMS, "res": res, "evidence_sha": sha, "v6_digest": ev.v6_rules_digest(), "seconds": round(time.time() - t)},
              open(os.path.join(HERE, "out_%s.json" % SETNAME), "w"), ensure_ascii=False)
    print("done", SETNAME, sha, round(time.time() - t), "violations:", sum(len(o["_violations"]) for _, o, _c in res))

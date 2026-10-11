#!/usr/bin/env python3
"""G4-e: the growth meter (docs/LINE3_G4_GROWTH_METER.md 7, ticket 8): at each measured step, ask the 94 fulllead questions of bank2 (69 intra2 + 25 unans)
of a structure that holds the first k articles, and write ONE canonical record per (arm, step, question) -- the verdict, the gold in a candidate, the gold
entries' provenance (tier, cross, origin), the answer's sha, `partial` / `rebuild_refused`, 未着, the evidence-present flag -- to results/meter_<arm>.jsonl.
The events (現れる / 残る / 壊れる) and the 2x2 tables are computed from those records by events.py (and rendered to results/meter_<arm>.md).

  arm A      foundation + frozen stack (G-2 cache), RUN+WORD+CHAR, flat reader, fast, grammar ON, layers OFF            steps: the 66 measured steps
  arm B      the CHAR tier of A's stack, dictionary-free: fugashi / unidic_lite cannot be imported in this process; grammar off, no stand-ins   66 steps
  arm A0     stack with the foundation OFF (diagnostic)                                                                   Fibonacci steps
  arm A_rev  stack, foundation ON, the articles in REVERSE order (condition 3)                                           step 300
  arm C      one-shot placement of the prefix (`line3 build`, ordered/stop/mid, foundation off), the reference curve      Fibonacci steps (needs a cache per step)
  arm C_B    C's CHAR caches read as B                                                                                     Fibonacci steps
  arm C_F    one-shot WITH the foundation (the G1-b caches, vera-impl/cache/g1_found), the diagnostic at 300              step 300

Every arm reads with ask(structure="flat", view="all", effort=<fast>, grammar=<arm default>) : layers OFF (L-G4-101a).  The runs are RESUMABLE: a record already in
the jsonl for (arm, step, qid) is skipped; a worker error is recorded as {"arm","step","qid","error"} and retried on the next run.

  PYTHONPATH=<worktree> PYTHONHASHSEED=0 python experiments/line3/g4/meter.py --arm A --stack <vera-impl>/cache/g4_stack_A --steps 1,2,3,5,8 --questions e<=8,unans:3 --workers 2
  ... --check                       the plan (steps, questions, which snapshots / caches exist, how many records are done) and exit
  ... --t10-check [PATH]            arm C at step 300, grammar off: re-ask 8 sampled records of the T10 flat/fast sweep and diff verdicts, entries and read counts (L-G4-11)
  python experiments/line3/g4/events.py ARM --stack <cache> [--key K]    render results/meter_ARM.<key>.md again

The result files are keyed by the run config: meter_<arm>.<key>.{jsonl,arr.jsonl,meta.json,md}, key = sha12 of (grammar, effort, site, level) -- the code sha is NOT in the
name; it is in every record's `config`, and a resume whose config (code sha included) differs from the records in the file is refused (events.ConfigMismatch).

Never opens vera-impl/hidden.  No network.  The seconds and the load are out of band (`cost`), never in a hashed byte.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import socket
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import events as EV                                            # noqa: E402  (pure; no reader)

DATA = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments", "line3", "bank2", "bank2.tsv")
STEPS_JSON = os.path.join(HERE, "steps.json")
RESULTS = os.path.join(HERE, "results")
SCORER = os.path.join(ROOT, "experiments", "line3", "t9", "scorer.py")
VERA_IMPL = EV.VERA_IMPL                                       # <vera-impl> = ROOT/../.. (the checkout is <vera-impl>/wt/<name>); env VERA_IMPL_DIR overrides
T10_FAST = os.path.join(VERA_IMPL, "wt", "line3", "experiments", "line3", "t10", "results", "ask_fulllead_fast_ordered-stop.jsonl")
CACHE_A = os.path.join(VERA_IMPL, "cache", "g4_stack_A")
CACHE_C = os.path.join(VERA_IMPL, "cache", "f1b")
CACHE_CF = os.path.join(VERA_IMPL, "cache", "g1_found")


def rel(path):
    """A path as the records and the meta show it: relative to <vera-impl> when it lies under it (no absolute path of one machine in a committed file)."""
    if path is None:
        return None
    ap = os.path.abspath(path)
    return os.path.relpath(ap, VERA_IMPL) if ap.startswith(VERA_IMPL + os.sep) else path
ALL3 = ("RUN", "WORD", "CHAR")

ARMS = {
    "A":     dict(kind="stack",   foundation="on",  order="forward", tiers=ALL3,      grammar="on",  dictionary=True,  steps="measured", src=CACHE_A),
    "B":     dict(kind="stack",   foundation="on",  order="forward", tiers=("CHAR",), grammar="off", dictionary=False, steps="measured", src=CACHE_A),
    "A0":    dict(kind="stack",   foundation="off", order="forward", tiers=ALL3,      grammar="on",  dictionary=True,  steps="fib",      src=None),
    "A_rev": dict(kind="stack",   foundation="on",  order="reverse", tiers=ALL3,      grammar="on",  dictionary=True,  steps="last",     src=None),
    "C":     dict(kind="oneshot", foundation="off", order="forward", tiers=ALL3,      grammar="on",  dictionary=True,  steps="fib",      src=CACHE_C),
    "C_B":   dict(kind="oneshot", foundation="off", order="forward", tiers=("CHAR",), grammar="off", dictionary=False, steps="fib",      src=CACHE_C),
    "C_F":   dict(kind="oneshot", foundation="on",  order="forward", tiers=ALL3,      grammar="on",  dictionary=True,  steps="last",     src=CACHE_CF),
}
CODE_MODULES = ("ask", "cycle", "readout", "stack", "placement", "foundation", "wiring", "energy", "space", "combined", "grammar", "funcwords")

A = st = sp = fd = pl = cy = W = S = None                      # filled by import_reader()


def import_reader(dictionary: bool) -> None:
    """Import the reader.  A dictionary-free arm blocks fugashi / unidic_lite FIRST (None in sys.modules makes any import of them raise), and refuses if either is
    already loaded: the arm is then not dictionary-free and must not be run."""
    global A, st, sp, fd, pl, cy, W, S
    if not dictionary:
        for m in ("fugashi", "unidic_lite"):
            if sys.modules.get(m) is not None:
                raise RuntimeError("%s is already imported: a dictionary-free arm needs a fresh process" % m)
            sys.modules[m] = None
    from verantyx.line3 import ask as A_, stack as st_, space as sp_, foundation as fd_, placement as pl_, cycle as cy_, wiring as W_      # noqa: WPS433
    A, st, sp, fd, pl, cy, W = A_, st_, sp_, fd_, pl_, cy_, W_
    spec = importlib.util.spec_from_file_location("g4_scorer", SCORER)
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)


# ------------------------------------------------------------------------------------------------------------------------------
# canonical bytes
# ------------------------------------------------------------------------------------------------------------------------------
def cj(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def assert_no_float(obj, path="record"):
    if isinstance(obj, float):
        raise TypeError("a float in the hashed part (%s)" % path)
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert_no_float(v, "%s.%s" % (path, k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_no_float(v, "%s[%d]" % (path, i))


def code_shas():
    out = {}
    base = os.path.join(ROOT, "verantyx", "line3")
    for m in CODE_MODULES:
        p = os.path.join(base, m + ".py")
        if os.path.exists(p):
            out[m] = A.file_sha256(p)
    out["meter"] = A.file_sha256(os.path.abspath(__file__))
    out["events"] = A.file_sha256(os.path.join(HERE, "events.py"))
    out["scorer"] = A.file_sha256(SCORER)
    return out


def cfg_config(cfg):
    """The run settings that change a record, in every record and (without the code sha) in the file name key."""
    return {"grammar": cfg["spec"]["grammar"], "effort": cfg["effort"] if cfg["effort"] is not None else "none", "site": "on" if cfg["site"] else "off",
            "level": cfg["level"], "code_sha256": cfg["code_sha"]}


def out_path(cfg, kind):
    """kind: jsonl | arr.jsonl | meta.json | md  ->  <out>/meter_<arm>.<config key>.<kind>"""
    return os.path.join(cfg["out"], "%s.%s" % (EV.stem(cfg["arm"], cfg_config(cfg)), kind))


# ------------------------------------------------------------------------------------------------------------------------------
# the corpus, the questions
# ------------------------------------------------------------------------------------------------------------------------------
class Corpus:
    """The documents in the ARM's order (reverse = the articles reversed, each article's sentences kept), the sids of each article, the bank."""

    def __init__(self, docs, bank_rows, order="forward"):
        docs = [list(d) for d in docs]
        self.docs = docs if order == "forward" else list(reversed(docs))
        self.titles = [st.doc_title(d) for d in self.docs]
        if len(set(self.titles)) != len(self.titles):
            raise ValueError("two articles with one title: an article is a maximal run of one title and the titles are distinct (L-G4-1)")
        self.pos = {t: i + 1 for i, t in enumerate(self.titles)}
        cum, n = [0], 0
        for d in self.docs:
            n += len(d)
            cum.append(n)
        self.cum = cum
        self.questions = []
        for r in bank_rows:
            qid, kind, _corpus, subj, question, gold, evidence = r[:7]
            title = evidence.rsplit("#", 1)[0] if "#" in evidence else evidence
            if title not in self.pos:
                raise ValueError("%s: the evidence title %r is not an article" % (qid, title))
            self.questions.append({"qid": qid, "kind": kind, "subject": subj, "question": question, "gold": gold, "evidence": evidence,
                                   "title": title, "pos": self.pos[title], "row": r})

    def article_sids(self, position, step):
        """The sids of article `position` (1-based) inside the prefix of `step` articles ([] if it has not entered)."""
        if position > step:
            return []
        return list(range(self.cum[position - 1], self.cum[position]))

    def entry_sid(self, evidence, step, position):
        """The sid of the evidence sentence (the row of the article whose `source` is `title#i`) -- a label; from_evidence uses the whole article (L-G4-6)."""
        if position > step:
            return None
        for i, r in enumerate(self.docs[position - 1]):
            if r.get("source") == evidence:
                return self.cum[position - 1] + i
        return None


def read_bank(path=BANK, corpus="fulllead"):
    with open(path, encoding="utf-8") as f:
        return [l.rstrip("\n").split("\t") for l in f if l.strip() and not l.startswith("#") and l.split("\t")[2] == corpus]


def select_questions(questions, spec):
    """spec: 'all' | comma list of ids, 'intra2', 'unans', 'e<=N' (intra2 with entry <= N), 's<=N' (unans with subject article <= N)."""
    if spec in (None, "", "all"):
        return list(questions)
    keep = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if tok in ("intra2", "unans"):
            keep |= {q["qid"] for q in questions if q["kind"] == tok}
        elif tok.startswith("e<="):
            keep |= {q["qid"] for q in questions if q["kind"] == "intra2" and q["pos"] <= int(tok[3:])}
        elif tok.startswith("s<="):
            keep |= {q["qid"] for q in questions if q["kind"] == "unans" and q["pos"] <= int(tok[3:])}
        elif tok.startswith("unans:"):                        # unans:N = the first N unans questions in bank order
            keep |= {q["qid"] for q in [x for x in questions if x["kind"] == "unans"][:int(tok[6:])]}
        else:
            keep.add(tok)
    missing = keep - {q["qid"] for q in questions}
    if missing:
        raise ValueError("unknown question ids: %s" % ",".join(sorted(missing)))
    return [q for q in questions if q["qid"] in keep]


def parse_steps(spec, kind, steps_json, n_articles):
    sj = steps_json
    if spec in (None, ""):
        spec = {"measured": "measured", "fib": "fib", "last": "last"}[kind]
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        if tok == "measured":
            out += sj["measured_steps"]
        elif tok == "fib":
            out += sj["fibonacci_steps"]
        elif tok == "last":
            out.append(n_articles)
        elif "-" in tok:
            a, b = tok.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(tok))
    steps = sorted(set(out))
    if not steps or steps[0] < 1 or steps[-1] > n_articles:
        raise ValueError("steps outside 1..%d" % n_articles)
    return steps


# ------------------------------------------------------------------------------------------------------------------------------
# the structure at one step
# ------------------------------------------------------------------------------------------------------------------------------
class Step:
    """Everything the workers of one (arm, step) share (built once in the parent, inherited by the fork)."""
    pass


def open_step(cfg, corpus, step):
    spec = cfg["spec"]
    g = Step()
    g.step, g.tiers = step, tuple(spec["tiers"])
    docs = corpus.docs
    g.prefix_sha = st.prefix_sha256(docs[:step])
    t0 = time.time()
    if spec["kind"] == "stack":
        g.ix = A.Index.from_stack(cfg["src"], g.tiers, data=docs, step=step, foundation=spec["foundation"], level=cfg["level"], order=spec["order"])
        g.structure = dict(g.ix.stack["state_sha256"])
        g.seats = g.ix.stack["seats_sha"]
    else:
        rows = [r for d in docs[:step] for r in d]
        space = sp.build_space(rows, tiers=g.tiers)
        adhs = fd.adhesions_of_space(space, g.tiers) if spec["foundation"] == "on" else {}
        loaded, files = {}, {}
        for t in g.tiers:
            p = A.cache_path(cfg["src"], g.prefix_sha, t, cfg["level"], "ordered", "forward", "stop", spec["foundation"])
            if not os.path.exists(p):
                raise FileNotFoundError("no one-shot placement cache for step %d tier %s: %s (build it with `line3 build ... --group-insert ordered --on-collapse stop`)" % (step, t, p))
            loaded[t] = A.load_placements(p, space.tiers[t], t, cfg["level"], g.prefix_sha, "ordered", "forward", "stop", spec["foundation"], adhs.get(t))
            files[t] = A.file_sha256(p)
        g.ix = A.Index(space, g.prefix_sha, cfg["level"], g.tiers, loaded, group_insert="ordered", order="forward", on_collapse="stop",
                       foundation=spec["foundation"], adhesions=adhs or None)
        g.structure = files
        g.seats = fd.seats_sha() if spec["foundation"] == "on" else None
    g.open_s = time.time() - t0
    g.unit_set = {t: frozenset(g.ix.space.tiers[t].units()) for t in g.tiers}
    g.normed = {t: [(u, S.norm(u)) for u in sorted(g.unit_set[t])] for t in g.tiers}
    g.inv = {}
    if cfg["site"]:
        for t in g.tiers:
            inv = collections.defaultdict(set)
            for seed in g.unit_set[t]:
                for u in cy.placement_units(g.ix.stores[t].cross_for(seed)):
                    inv[u].add(seed)
            g.inv[t] = dict(inv)
    if spec["grammar"] == "on":                                # warm the grammar context ONCE, before the fork (span index + particle records)
        W.context_of(g.ix)
    return g


def gold_units(g, tier, golds):
    """The units of the tier whose normalised text holds a normalised gold alternative (the scorer's rule)."""
    if not golds:
        return []
    return [u for u, nu in g.normed[tier] if any(x in nu for x in golds)]


# ------------------------------------------------------------------------------------------------------------------------------
# one record
# ------------------------------------------------------------------------------------------------------------------------------
def arr_of(g, tier, seed):
    """-> (arr sha12, opened_at, closed_at, seated count, closed) of the cross the entry was read from."""
    ix = g.ix
    if ix.stack_state is not None:
        sc = ix.stack_state.crosses[tier][seed]
        return st.arr_sha(sc)[:12], sc.opened_at, sc.closed_at, len(sc.seated), sc.closed
    p = ix.stores[tier]._loaded[seed]
    return sha(p.to_bytes())[:12], None, None, p.size, p.stop == pl.BUDGET


def origin_rows(g, c, tier, entry, e_pos):
    o = c.outcome(tier)
    cand = {(x.seed, x.member): x for x in o.result.candidates}
    read = set(o.result.plan.read)
    reader = cy.Reader(g.ix.facts[tier], o.result.ctx.attached, o.result.ctx.energy_units)          # the reader the cycle used (default window): r2 / r3 of the adopted state
    rows = []
    for si in entry.origins:
        ref = o.answer.states[si].ref
        arr, opened, closed, seated, is_closed = arr_of(g, tier, ref.seed)
        x = cand.get((ref.seed, ref.member))
        ev = reader.evaluate(ref.flat, ref.L)
        row = {"tier": tier, "seed": ref.seed, "member": ref.member, "stability": "%d/%d" % (ref.stability.numerator, ref.stability.denominator),
               "unit": ref.unit, "ratios": (x.end.status if x is not None else None), "agreed": (x.end.agreed if x is not None else None),
               "r2": ev.r2, "r3": ev.r3, "ratios_eval": ev.status,
               "arr": arr, "opened_at": opened, "closed_at": closed, "closed": bool(is_closed), "seated": seated, "read": ref.seed in read, "seats_after_entry": None}
        if g.ix.stack_state is not None and e_pos is not None:
            sc = g.ix.stack_state.crosses[tier][ref.seed]
            row["seats_after_entry"] = sum(1 for _u, s in sc.seated if s > e_pos)
        rows.append(row)
    return rows


def site_analysis(g, c, golds, gold_by_tier):
    """Where the gold sits relative to the question, when no entry from the evidence holds it (7.4): per tier, the gold units, the crosses that hold a question
    unit, the crosses that hold a gold unit, both (`sited`), and how many of those were read.  Overall tag: 未採択 (a sited cross was read, no gold came out), 未読
    (sited, none read), 未着席 (a gold unit exists, no cross holds it together with a question unit), 未着 (no gold unit)."""
    per, order = {}, {"未採択": 3, "未読": 2, "未着席": 1, "未着": 0}
    best = "未着"
    for t in g.tiers:
        o = c.outcome(t)
        GU = gold_by_tier[t]
        inv = g.inv[t]
        qu = sorted(u for u in o.result.ctx.energy_units if u in g.unit_set[t])
        hq = set().union(*(inv.get(u, ()) for u in qu)) if qu else set()
        hg = set().union(*(inv.get(u, ()) for u in GU)) if GU else set()
        sited = hq & hg
        read = set(o.result.plan.read)
        closed_before = None
        if GU and not sited:
            ts = g.ix.space.tiers[t]
            gset = set(GU)
            closed_before = False
            for seed in sorted(hq):
                p = g.ix.stores[t].cross_for(seed)
                if p.stop == pl.BUDGET and (set(ts.cooccurrence(seed)) & gset) - cy.placement_units(p):
                    closed_before = True
                    break
        tag = "未着" if not GU else "未着席" if not sited else "未読" if not (sited & read) else "未採択"
        per[t] = {"gold_units": len(GU), "query_units": len(qu), "holders_query": len(hq), "holders_gold": len(hg), "sited": len(sited),
                  "sited_read": len(sited & read), "closed_before": closed_before, "tag": tag}
        if order[tag] > order[best]:
            best = tag
    return {"tag": best, "tiers": per}


def measure(cfg, corpus, g, q):
    """-> (record, cost) of one question at one step."""
    spec = cfg["spec"]
    step, kind, gold = g.step, q["kind"], q["gold"]
    t0, c0 = time.monotonic(), time.process_time()
    c = A.ask(g.ix, q["question"], tiers=g.tiers, view="all", effort=cfg["effort"], structure="flat", grammar=spec["grammar"])
    entered = kind == "intra2" and step >= q["pos"]
    evid = corpus.article_sids(q["pos"], step) if entered else []
    evid_set = set(evid)
    golds = S.golds(gold) if gold else []
    gold_by_tier = {t: gold_units(g, t, golds) for t in g.tiers}
    unarrived = (not any(gold_by_tier.values())) if (kind == "intra2" and golds) else None
    # the 3-tier flag: for an arm that reads all three tiers it IS the arm's flag; for a CHAR-only arm it comes from the arrival of units in a 3-tier stack, and
    # when that oracle did not load it is None (unknown) -- never the arm's own flag, which would silently call almost every gold 未着
    if unarrived is None:
        unarrived3 = None
    elif set(g.tiers) >= set(ALL3):
        unarrived3 = unarrived
    else:
        unarrived3 = cfg["arrival"].unarrived(golds, step) if cfg.get("arrival") is not None else None
    gold_rows, first_gold = [], None
    last_evid = max(evid) if evid else None
    for pos, (tier, en) in enumerate(c.entries):
        if not (gold and S.hits_words(gold, en.words)):
            continue
        srcs = list(en.source_sids)
        first_gold = pos if first_gold is None else first_gold
        gold_rows.append({"pos": pos, "tier": tier, "words": list(en.words), "source_sids": srcs, "from_evidence": bool(evid_set & set(srcs)),
                          "pre_entry_hit": kind == "intra2" and not entered,
                          "src_after_entry": (any(s > last_evid for s in srcs) if last_evid is not None else None),
                          "origins": origin_rows(g, c, tier, en, q["pos"] if kind == "intra2" else None)})
    tiers = {}
    for o in c.outcomes:
        p = o.result.plan
        rc = o.read_counts
        tiers[o.tier] = {"verdict": o.verdict, "entries": len(o.entries), "read": list(p.read), "unread": rc["left_unread"], "would_read": rc["would_read_in_full"],
                         "tied_group_not_split": p.boundary, "rebuild_refused": o.rebuild_refused, "rebuild_skipped": o.raise_skipped}
    side = {}
    for o in c.outcomes:
        ctx = o.result.ctx
        qu = sorted(ctx.energy_units)
        side[o.tier] = {"units": qu, "in_prefix": sum(1 for u in qu if u in g.unit_set[o.tier]), "standins": list(ctx.standins)}
    ro = c.read_obj()
    rec = {"format": EV.FORMAT, "arm": cfg["arm"], "step": step, "article": corpus.titles[step - 1], "prefix_sha256": g.prefix_sha, "structure_sha256": g.structure,
           "seats_sha": g.seats, "stack_order": spec["order"], "code_sha256": cfg["code_sha"], "config": cfg_config(cfg),
           "qid": q["qid"], "kind": kind, "e": q["pos"] if kind == "intra2" else None, "s": q["pos"] if kind == "unans" else None, "entered": entered,
           "evidence_sids": evid, "evidence_sid": corpus.entry_sid(q["evidence"], step, q["pos"]) if entered else None,
           "verdict": c.verdict, "listed": len(c.entries), "per_tier_listed": {o.tier: len(o.entries) for o in c.outcomes},
           "partial": bool(ro["partial"]), "partial_reasons": list(ro.get("partial_reasons", [])), "left_unread": sum(v["left_unread"] for v in ro["per_tier"].values()),
           "rebuild_refused": sum(x.rebuild_refused for x in c.outcomes), "rebuild_skipped": sum(ro["rebuild_skipped"].values()) if ro.get("rebuild_skipped") else 0,
           "tied_group_not_split": sum(x.result.plan.boundary for x in c.outcomes), "tiers": tiers,
           "gold_in_candidate": (bool(gold_rows) if golds else None), "gold_entries": [x["pos"] for x in gold_rows], "first_gold_pos": first_gold,
           "gold": gold_rows, "unarrived": unarrived, "unarrived_3tier": unarrived3,
           "answer_sha256": sha(c.to_bytes()), "answer_obj_sha256": sha(cj(c.answer_obj()).encode("utf-8")),
           "question_side": side, "n_standins": sum(len(v["standins"]) for v in side.values()), "site": None}
    row, cell, sub = EV.classify(rec)                           # raises on an impossible shape (a from_evidence entry before its article)
    rec["cell"] = "%s/%s%s" % (row, cell, "/" + sub if sub else "")
    rec["single_wrong"] = EV.single_wrong(rec)
    if cfg["site"] and row == EV.PRESENT and cell != EV.CORRECT:
        rec["site"] = site_analysis(g, c, golds, gold_by_tier)
    assert_no_float(rec)
    cost = {"cpu_ms": int((time.process_time() - c0) * 1000), "wall_ms": int((time.monotonic() - t0) * 1000), "load1": round(os.getloadavg()[0], 2),
            "host": socket.gethostname(), "pid": os.getpid()}
    return rec, cost


def line_of(rec, cost):
    return cj({"record": rec, "record_sha256": sha(cj(rec).encode("utf-8")), "cost": cost})


# ------------------------------------------------------------------------------------------------------------------------------
# arrival of units (3-tier 未着 for a CHAR-only arm): from a 3-tier stack's ledgers, never from a tokeniser
# ------------------------------------------------------------------------------------------------------------------------------
class Arrival:
    def __init__(self, first):                                  # {tier: {unit: first step}}
        self.first = first
        self.items = sorted((s_, S.norm(u)) for fs in first.values() for u, s_ in fs.items())      # (first step, normalised unit)

    @classmethod
    def from_stack(cls, root, foundation="on", level="mid", order="forward"):
        from verantyx.line3 import foundation as fd_
        d = os.path.join(root, "%s__%s__%s" % (fd_.foundation_key() if foundation == "on" else "off", level, order))
        best = None
        with open(os.path.join(d, "manifest.jsonl"), encoding="utf-8") as f:
            for line in f:
                m = json.loads(line)
                if set(m["tiers"]) >= set(ALL3) and (best is None or m["step"] > best["step"]):
                    best = m
        p12 = best["prefix_sha256"][:12]
        first = {}
        for t in ALL3:
            fs = {}
            with open(os.path.join(d, "%s_ledger_%s.jsonl" % (t, p12)), encoding="utf-8") as f:
                for line in f:
                    e = json.loads(line)
                    for u in e["opened"]:
                        fs.setdefault(u, e["step"])
            first[t] = fs
        return cls(first)

    def unarrived(self, golds, step):
        """True iff no unit of any tier that has appeared by `step` holds a gold alternative."""
        for s_, nu in self.items:
            if s_ > step:
                break
            if any(x in nu for x in golds):
                return False
        return True


# ------------------------------------------------------------------------------------------------------------------------------
# the run
# ------------------------------------------------------------------------------------------------------------------------------
_G = {}


def _work(q):
    try:
        rec, cost = measure(_G["cfg"], _G["corpus"], _G["g"], q)
        return {"ok": True, "line": line_of(rec, cost), "qid": q["qid"], "ms": cost["wall_ms"]}
    except Exception:                                           # one bad question must not end a multi-hour run
        return {"ok": False, "qid": q["qid"], "error": traceback.format_exc()}


def write_arr_table(cfg, g):
    """One-shot arms: the sha12 of every cross's Placement.to_bytes() at this step, so that events can ask whether a cross was re-placed between two steps."""
    if cfg["spec"]["kind"] != "oneshot":
        return
    path = out_path(cfg, "arr.jsonl")
    have = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                o = json.loads(line)
                have.add((o["step"], o["tier"]))
            except ValueError:                                  # a line cut by a kill: that (step, tier) is written again below
                pass
    ensure_newline(path)                                        # a cut last line has no newline: the next append would glue onto it and be lost
    with open(path, "a", encoding="utf-8") as f:
        for t in g.tiers:
            if (g.step, t) in have:
                continue
            tab = {seed: sha(p.to_bytes())[:12] for seed, p in sorted(g.ix.stores[t]._loaded.items())}
            f.write(cj({"step": g.step, "tier": t, "arr": tab}) + "\n")


def plan(cfg, corpus, steps, questions, done):
    rows = []
    for s in steps:
        todo = [q for q in questions if (cfg["arm"], s, q["qid"]) not in done]
        rows.append((s, len(questions), len(todo)))
    return rows


def check_sources(cfg, corpus, steps):
    spec, out = cfg["spec"], []
    for s in steps:
        pfx = st.prefix_sha256(corpus.docs[:s])
        if spec["kind"] == "stack":
            d = os.path.join(cfg["src"], "%s__%s__%s" % (fd.foundation_key() if spec["foundation"] == "on" else "off", cfg["level"], spec["order"]))
            ok = False
            mp_ = os.path.join(d, "manifest.jsonl")
            if os.path.exists(mp_):
                ok = any(json.loads(l)["prefix_sha256"] == pfx and set(json.loads(l)["tiers"]) >= set(spec["tiers"]) for l in open(mp_, encoding="utf-8") if l.strip())
            out.append((s, ok, d))
        else:
            ps = [A.cache_path(cfg["src"], pfx, t, cfg["level"], "ordered", "forward", "stop", spec["foundation"]) for t in spec["tiers"]]
            out.append((s, all(os.path.exists(p) for p in ps), ps[0]))
    return out


def ensure_newline(path):
    """A killed run can leave a cut last line without its newline: terminate it, so that the next append starts on a line of its own (the cut line stays a
    line that does not parse, and is skipped by every reader)."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb+") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                f.write(b"\n")


def run(cfg, corpus, steps, questions, log=lambda m: print(m, file=sys.stderr, flush=True)):
    """Run the meter over `steps` x `questions`; returns {"done": n, "errors": n, "steps": [...]}."""
    arm, spec = cfg["arm"], cfg["spec"]
    os.makedirs(cfg["out"], exist_ok=True)
    jpath = out_path(cfg, "jsonl")
    EV.check_resume(jpath, cfg_config(cfg))                     # raises ConfigMismatch: records of another grammar / effort / site / level / code are never mixed in
    ensure_newline(jpath)
    done = EV.done_keys(jpath)
    report = {"done": 0, "errors": 0, "steps": []}
    mp_ctx = mp.get_context("fork")
    for step in steps:
        todo = [q for q in questions if (arm, step, q["qid"]) not in done]
        if not todo:
            log("step %d: %d questions already recorded" % (step, len(questions)))
            continue
        t0 = time.time()
        try:
            g = open_step(cfg, corpus, step)
        except Exception:
            err = traceback.format_exc()
            with open(jpath, "a", encoding="utf-8") as f:
                f.write(cj({"arm": arm, "step": step, "qid": None, "error": err}) + "\n")
            report["errors"] += 1
            log("step %d: cannot open the structure: %s" % (step, err.strip().splitlines()[-1]))
            continue
        write_arr_table(cfg, g)
        _G.update(cfg=cfg, corpus=corpus, g=g)
        nerr = 0
        with open(jpath, "a", encoding="utf-8") as f:
            if cfg["workers"] <= 1:
                it = map(_work, todo)
                pool = None
            else:
                pool = mp_ctx.Pool(cfg["workers"])
                it = pool.imap_unordered(_work, todo)
            for res in it:
                if res["ok"]:
                    f.write(res["line"] + "\n")
                    report["done"] += 1
                else:
                    f.write(cj({"arm": arm, "step": step, "qid": res["qid"], "error": res["error"]}) + "\n")
                    nerr += 1
                    log("step %d %s ERROR %s" % (step, res["qid"], res["error"].strip().splitlines()[-1]))
                f.flush()
            if pool is not None:
                pool.close()
                pool.join()
        report["errors"] += nerr
        row = {"step": step, "todo": len(todo), "errors": nerr, "open_s": round(g.open_s, 1), "wall_s": round(time.time() - t0, 1)}
        report["steps"].append(row)
        log("step %d (%s): %d done, %d errors, open %.1fs, wall %.1fs, load1 %.1f" % (step, corpus.titles[step - 1], len(todo) - nerr, nerr, g.open_s, time.time() - t0, os.getloadavg()[0]))
        _G.clear()
        del g
    return report


def dictionary_blocked():
    """True iff BOTH dictionary modules are present in sys.modules as None (the block import_reader(False) puts there).  Not-imported-at-all is not blocked: it
    would also be what a process that never needed them looks like."""
    return all(m in sys.modules and sys.modules[m] is None for m in ("fugashi", "unidic_lite"))


def write_meta(cfg, argv, report, steps, questions):
    path = out_path(cfg, "meta.json")
    meta = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"arm": cfg["arm"], "config": cfg_config(cfg), "runs": []}
    spec = {k: v for k, v in cfg["spec"].items()}
    spec["src"] = rel(spec.get("src"))
    meta["runs"].append({"argv": argv, "started": cfg["started"], "finished": time.strftime("%Y-%m-%d %H:%M:%S"), "host": socket.gethostname(),
                         "python": sys.version.split()[0], "pyhashseed": os.environ.get("PYTHONHASHSEED"), "arm_spec": spec,
                         "src": rel(cfg["src"]), "level": cfg["level"], "effort": cfg["effort"], "workers": cfg["workers"], "steps": steps,
                         "questions": [q["qid"] for q in questions], "config": cfg_config(cfg), "code_sha256": cfg["code_sha"], "code_modules": cfg.get("code_modules") or code_shas(),
                         "arrival_oracle": cfg.get("arrival_status"), "report": report, "dictionary_modules_blocked_at_exit": dictionary_blocked()})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, sort_keys=True, ensure_ascii=False)


def render(cfg, corpus=None):
    jpath = out_path(cfg, "jsonl")
    recs = EV.load_records(jpath)
    if not recs:
        return None
    if cfg["spec"]["kind"] == "stack":
        arr = EV.stack_arr(cfg["src"], cfg["spec"]["foundation"], cfg["level"], cfg["spec"]["order"])
    else:
        arr = EV.sha_arr(out_path(cfg, "arr.jsonl"))
    one_char = None
    if corpus is not None:
        one_char = {q["qid"] for q in corpus.questions if q["gold"] and any(len(g) == 1 for g in S.golds(q["gold"]))}
    md = EV.render_md(cfg["arm"], recs, arr, meta={"kind": cfg["spec"]["kind"], "foundation": cfg["spec"]["foundation"], "tiers": list(cfg["spec"]["tiers"]),
                                                   "config": cfg_config(cfg), "arrival_oracle": cfg.get("arrival_status")},
                      errors=EV.load_errors(jpath), schedule=cfg.get("schedule"), one_char=one_char)
    with open(out_path(cfg, "md"), "w", encoding="utf-8") as f:
        f.write(md)
    return md


# ------------------------------------------------------------------------------------------------------------------------------
# the T10 reproduction check (L-G4-11): arm C at step 300, grammar off, 8 sampled records of the T10 flat/fast sweep
# ------------------------------------------------------------------------------------------------------------------------------
def t10_check(cfg, corpus, path, n=8):
    """Re-ask n records sampled (every len//n-th by id) from the T10 flat/fast sweep with arm C at the last step, grammar off, and compare, per record: the
    verdict, and per tier the tier verdict, the entries (words, centres, count, stability) and the read counts.  An error record in the T10 file is an error
    here (it used to be filtered out silently).  -> a dict {config, source, n, all_equal, results}."""
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    bad = [r.get("id") for r in recs if "error" in r]
    if bad:
        raise ValueError("the T10 file %s holds error records (%s): the sample would silently leave them out" % (path, ", ".join(map(str, bad[:8]))))
    recs.sort(key=lambda r: r["id"])
    pick = recs[::max(1, len(recs) // n)][:n]
    step = len(corpus.docs)
    g = open_step(dict(cfg, site=False), corpus, step)
    qs = {q["qid"]: q for q in corpus.questions}
    _G.update(g=g)
    out = []

    def ent(e):
        return {"words": list(e.words), "centres": list(e.centres), "count": e.count, "stability": A._fs(e.stability)}
    for r in pick:
        c = A.ask(g.ix, qs[r["id"]]["question"], view="all", effort="fast")
        want = {t: v["entries"] for t, v in r["layer0"].items()}
        got = {o.tier: [ent(e) for e in o.entries] for o in c.outcomes}
        want_v = {t: v["verdict"] for t, v in r["layer0"].items()}
        got_v = {o.tier: o.verdict for o in c.outcomes}
        want_rc = {t: dict(v["read"]) for t, v in r["layer0"].items()}
        got_rc = {o.tier: {k: o.read_counts[k] for k in want_rc.get(o.tier, {})} for o in c.outcomes}
        out.append({"id": r["id"], "verdict_equal": c.verdict == r["verdict0"], "tier_verdicts_equal": want_v == got_v, "entries_equal": want == got,
                    "read_counts_equal": want_rc == got_rc, "listed_t10": sum(len(v) for v in want.values()), "listed_now": sum(len(v) for v in got.values()),
                    "tier_verdicts": got_v, "read_counts": got_rc})
    keys = ("verdict_equal", "tier_verdicts_equal", "entries_equal", "read_counts_equal")
    return {"config": cfg_config(cfg), "source": rel(path), "arm": cfg["arm"], "step": step, "n": len(out),
            "all_equal": all(r[k] for r in out for k in keys), "results": out}


# ------------------------------------------------------------------------------------------------------------------------------
# command line
# ------------------------------------------------------------------------------------------------------------------------------
def build_cfg(a):
    spec = dict(ARMS[a.arm])
    if a.grammar != "default":
        spec["grammar"] = a.grammar
    if a.stack:
        src = a.stack
    elif a.cache:
        src = a.cache
    else:
        src = spec["src"]
    if src is None:
        src = ARMS["A"]["src"]
    return {"arm": a.arm, "spec": spec, "src": src, "level": a.level, "effort": None if a.effort == "none" else a.effort, "workers": a.workers, "out": a.out,
            "site": a.site == "on", "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--stack", default=None, help="stack cache root (stack arms); default per arm")
    ap.add_argument("--cache", default=None, help="one-shot placement cache dir (C arms); default per arm")
    ap.add_argument("--steps", default=None, help="comma list: N, a-b, measured, fib, last (default per arm)")
    ap.add_argument("--questions", default="all", help="all | ids | intra2 | unans | e<=N | s<=N | unans:N (comma list, union)")
    ap.add_argument("--workers", type=int, default=2, help="processes per step over the questions")
    ap.add_argument("--effort", default="fast", choices=["fast", "standard", "none"])
    ap.add_argument("--grammar", default="default", choices=["default", "on", "off"])
    ap.add_argument("--level", default="mid")
    ap.add_argument("--site", default="on", choices=["on", "off"], help="the 未着席 / 未読 / 未採択 analysis of a question that is present and not correct")
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--bank", default=BANK)
    ap.add_argument("--out", default=RESULTS)
    ap.add_argument("--units-from", default=None, help="a 3-tier stack cache whose ledgers give the unit arrival (the 3-tier 未着 of a CHAR-only arm); default arm A's")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--t10-check", nargs="?", const=T10_FAST, default=None)
    ap.add_argument("--t10-n", type=int, default=8, help="how many T10 records to re-ask")
    a = ap.parse_args(argv)
    spec = ARMS[a.arm]
    import_reader(spec["dictionary"])
    cfg = build_cfg(a)
    cfg["code_modules"] = code_shas()
    cfg["code_sha"] = sha(cj(cfg["code_modules"]).encode("utf-8"))
    docs = st.load_docs(a.data)
    corpus = Corpus(docs, read_bank(a.bank), spec["order"])
    if os.path.exists(STEPS_JSON) and a.data == DATA and spec["order"] == "forward":
        sj = json.load(open(STEPS_JSON, encoding="utf-8"))
        bad = [q["qid"] for q in corpus.questions if sj["entry_steps"].get(q["qid"]) != q["pos"]]
        if bad:
            raise SystemExit("entry steps differ from steps.json for %s" % bad[:5])
        cfg["schedule"] = EV.scheduled_steps(a.arm, sj)                   # the arm's planned steps: the predictions are judged only when every one is complete
    else:
        sj = {"measured_steps": list(range(1, len(corpus.docs) + 1)), "fibonacci_steps": list(range(1, len(corpus.docs) + 1))}
        cfg["schedule"] = None
    steps = parse_steps(a.steps, spec["steps"], sj, len(corpus.docs))
    questions = select_questions(corpus.questions, a.questions)
    cfg["arrival"], cfg["arrival_status"] = None, {"needed": set(spec["tiers"]) < set(ALL3), "loaded": False, "source": None, "error": None}
    ua = a.units_from or (ARMS["A"]["src"] if not (spec["tiers"] == ALL3) else None)
    if ua:
        cfg["arrival_status"]["source"] = rel(ua)
        try:
            if not os.path.isdir(ua):
                raise FileNotFoundError("no 3-tier stack directory %s" % ua)
            cfg["arrival"] = Arrival.from_stack(ua, "on", a.level, "forward")
            cfg["arrival_status"]["loaded"] = True
        except (OSError, KeyError, TypeError, ValueError) as e:             # NOT silent: the 3-tier flag is then None, the meta and the markdown say so
            cfg["arrival_status"]["error"] = "%s: %s" % (type(e).__name__, e)
            print("WARNING: the arrival oracle did not load (%s): unarrived_3tier will be None" % cfg["arrival_status"]["error"], file=sys.stderr, flush=True)
    elif cfg["arrival_status"]["needed"]:
        cfg["arrival_status"]["error"] = "no --units-from and no default 3-tier stack for this arm"
    jpath = out_path(cfg, "jsonl")
    if a.t10_check is not None:
        if a.arm != "C":
            raise SystemExit("--t10-check is for arm C (step 300, grammar off)")
        cfg["spec"] = dict(spec, grammar="off")
        res = t10_check(cfg, corpus, a.t10_check, a.t10_n)
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "meter_C_t10check.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, ensure_ascii=False, sort_keys=True)
        print(json.dumps({k: v for k, v in res.items() if k != "results"}, indent=1, ensure_ascii=False))
        for r in res["results"]:
            print(r["id"], {k: r[k] for k in ("verdict_equal", "tier_verdicts_equal", "entries_equal", "read_counts_equal")})
        return 0 if res["all_equal"] else 2
    if a.check:
        done = EV.done_keys(jpath)
        print("arm %s (%s, foundation %s, tiers %s, grammar %s, effort %s) src %s" % (a.arm, spec["kind"], spec["foundation"], ",".join(spec["tiers"]), cfg["spec"]["grammar"], cfg["effort"], cfg["src"]))
        print("%d questions, %d steps" % (len(questions), len(steps)))
        src = {s: (ok, p) for s, ok, p in check_sources(cfg, corpus, steps)}
        for s, n, todo in plan(cfg, corpus, steps, questions, done):
            print("  step %3d: source %s, %d of %d to do" % (s, "ok" if src[s][0] else "MISSING (%s)" % src[s][1], todo, n))
        return 0
    try:
        rep = run(cfg, corpus, steps, questions)
    except EV.ConfigMismatch as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 3
    write_meta(cfg, argv, rep, steps, questions)
    render(cfg, corpus)
    print("arm %s: %d records written, %d errors; %s" % (a.arm, rep["done"], rep["errors"], out_path(cfg, "md")))
    if not spec["dictionary"] and (sys.modules.get("fugashi") is not None or sys.modules.get("unidic_lite") is not None):
        raise SystemExit("fugashi / unidic_lite was imported in a dictionary-free arm")
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

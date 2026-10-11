#!/usr/bin/env python3
"""G4-f: the events (現れる / 残る / 壊れる, with the cause tags R / U / A) and the 2x2 tables, computed from the meter's per-(arm, step, question) records.

Pure functions over plain dicts: nothing here imports the reader, the stack or a tokeniser, so every definition can be tested on synthetic series
(tests/line3/test_g4_meter.py) and the same code renders the markdown of a real run (`python events.py ARM [--results DIR] [--stack DIR]`).

The definitions (docs/LINE3_G4_GROWTH_METER.md 7.3 / 7.4 and the owner's decisions of 2026-10-06_line3_faithful_build.md, G4 sections):

  2x2 (7.3)     present = an intra2 question at a step >= its entry step e(q); absent = an intra2 question before e(q), and an unans question at every step.
                present: correct = some entry holds the gold AND the entry is `from_evidence` (cites a sentence of the evidence article);
                         miss = a typed abstention (UNKNOWN_*), a list without gold, a list whose gold is not from the evidence (`gold_not_from_evidence`);
                         confident wrong = a single ANSWER without gold.
                absent:  correct = a typed abstention; miss = a list (CHOICE, or an ANSWER that holds the gold = `pre_entry_hit`): false presence;
                         confident wrong = a single ANSWER without gold.
                `gold in a candidate` (any entry, any source) stands beside it.
  現れる        appear(q) = the first measured step k >= e(q) with H_k (present-correct).  直入 = appear == e(q) (delay 0); 後から = appear > e(q) while e(q) is on
                the arm's schedule (a missing e(q) record makes it 後から, never 直入); when e(q) is NOT on the arm's schedule (arm C: Fibonacci steps) the
                entry is unmeasured and the label is None (`appeared_entry_unmeasured`), `entry_measured` says which.  A question whose gold is 未着 at the last
                step is LEFT OUT of the denominator and counted apart (owner: 未着 is excluded from the 現れる denominator and from the headline 2x2).
                Which 未着 flag: `unarrived` (no unit of the ARM's tiers holds the gold) for A / A0 / A_rev / C / C_F; `unarrived_3tier` (no RUN / WORD / CHAR unit
                does) for B and C_B (PRIMARY_UNARRIVED), with the arm's own CHAR-only count always beside it.  A flag that is None for a question that has a gold
                (the arrival oracle did not load) is counted as `unarrived_unknown` and shown, never read as "arrived".
  残る          the share of the measured steps after appear(q) at which H still holds (num, den); `stays` = all of them.  Also reported with G (gold in a candidate).
  損失 (loss)   consecutive measured steps j < k of one question with H_j and not H_k.  The cause of each gold-holding cross X of step j (the (tier, seed)
                origins of the gold entries that made H_j):  R = rearranged (arr of X differs between j and k: 充填 or 絞り, a recount 絞り too, owner decision),
                U = unread (same arrangement, X not in the tier's `read` at k), A = read but not adopted.
                壊れる = a loss that is a 単独誤答化 (verdict ANSWER at k with one entry without gold, whatever the cause) or has at least one U / A cross.
                置き換え (growth) = a loss that is not a 単独誤答化 and whose crosses are ALL R.  A mixed loss is 壊れる, its tag multiset is kept.
                A cross whose arrangement cannot be looked up is tagged "?" (counted as 壊れる, reported apart: nothing is hidden).
  戻る          H again at a later measured step after a loss.

No float anywhere in a result that is hashed or compared; the markdown shows ratios as `a/b` and integer percentages.
"""
import argparse
import collections
import hashlib
import json
import os
import statistics
import sys

FORMAT = "line3.g4.meter.v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))                       # the checkout (the worktree) this file lives in
# The caches and the sibling worktree `line3` live OUTSIDE the checkout, beside it: <vera-impl>/cache/..., <vera-impl>/wt/line3/... .  The path is relative to the
# checkout (ROOT/../..), not absolute; VERA_IMPL_DIR overrides it for a checkout that is not under <vera-impl>/wt/ (a cloud runner).
VERA_IMPL = os.path.normpath(os.environ.get("VERA_IMPL_DIR") or os.path.join(ROOT, "..", ".."))
ANSWER, CHOICE = "ANSWER", "CHOICE"

PRESENT, ABSENT = "present", "absent"
CORRECT, MISS, WRONG = "correct", "miss", "wrong"
SUB_ABSTAIN, SUB_LIST_NO_GOLD, SUB_NOT_FROM_EVIDENCE, SUB_FALSE_PRESENCE = "abstain", "list_without_gold", "gold_not_from_evidence", "false_presence"

R, U, A_, Q_ = "R", "U", "A", "?"
BREAK, GROWTH = "break", "growth"

NEVER_TAGS = ("未着", "未着席", "未読", "未採択", "非根拠", "未特定")

OWN_UNARRIVED = "unarrived"                                    # no unit of the ARM's tiers holds a gold alternative
TIER3_UNARRIVED = "unarrived_3tier"                            # no unit of RUN / WORD / CHAR holds one (the arrival of units from a 3-tier stack's ledgers)
# The primary 未着 flag per arm (reviewer, G4-e/f): a CHAR-only arm (B, C_B) reads one-character units, so its own flag says "未着" for almost every gold
# (the tokeniser, not the structure); the 3-tier flag is the one that is comparable with A.  The arm's own count always stands beside it.
PRIMARY_UNARRIVED = {"B": TIER3_UNARRIVED, "C_B": TIER3_UNARRIVED}
# Which steps an arm is meant to measure (meter.py ARMS[..]["steps"]); the predictions are judged only when EVERY scheduled step is complete.
ARM_STEPS = {"A": "measured", "B": "measured", "A0": "fib", "A_rev": "last", "C": "fib", "C_B": "fib", "C_F": "last"}


def primary_key(arm):
    return PRIMARY_UNARRIVED.get(arm, OWN_UNARRIVED)


def scheduled_steps(arm, steps_json):
    kind = ARM_STEPS[arm]
    if kind == "last":
        return [steps_json["num_articles"]]
    return list(steps_json["measured_steps" if kind == "measured" else "fibonacci_steps"])


# ------------------------------------------------------------------------------------------------------------------------------
# the run config: in every record and in the file name key; a resume with another config is refused
# ------------------------------------------------------------------------------------------------------------------------------
CONFIG_FIELDS = ("grammar", "effort", "site", "level", "code_sha256")


class ConfigMismatch(RuntimeError):
    """A resume (or a second writer) with a config other than the one the file's records were made with."""


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_key(config):
    """sha12 of the config WITHOUT the code sha: the file name key.  (With the code sha in the name, every edit of the code would start a new file and the refusal
    of a resume made with other code could never fire.)"""
    return hashlib.sha256(canonical({k: v for k, v in sorted(config.items()) if k != "code_sha256"}).encode("utf-8")).hexdigest()[:12]


def stem(arm, config):
    return "meter_%s.%s" % (arm, config_key(config))


def parse_stem(filename):
    """'meter_C_B.0123456789ab.jsonl' -> ('C_B', '0123456789ab'); None for a file that is not a meter jsonl (the .arr.jsonl table is not one)."""
    if not (filename.startswith("meter_") and filename.endswith(".jsonl")) or filename.endswith(".arr.jsonl"):
        return None
    arm, dot, key = filename[len("meter_"):-len(".jsonl")].rpartition(".")
    if not dot or not arm or len(key) != 12 or any(c not in "0123456789abcdef" for c in key):
        return None
    return arm, key


def check_resume(path, config):
    """Raise ConfigMismatch if a record already in `path` was made with a config other than `config` (or with none)."""
    if not os.path.exists(path):
        return
    seen = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            r = o.get("record")
            if r is not None:
                seen.setdefault(canonical(r.get("config")), r.get("config"))
    for c in seen.values():
        if c != config:
            diff = sorted(k for k in set(config) | set(c or {}) if (c or {}).get(k) != config.get(k)) if c else ["config (absent)"]
            raise ConfigMismatch("resume refused: %s holds records made with another config (differs in: %s; file has %s, this run has %s); "
                                 "use another --out or finish the old run with its own settings and code" % (path, ", ".join(diff), canonical(c), canonical(config)))


# ------------------------------------------------------------------------------------------------------------------------------
# records
# ------------------------------------------------------------------------------------------------------------------------------
def load_records(path):
    """The hashed `record` parts of a meter jsonl, last write of one (arm, step, qid) wins, sorted by (step, qid).  Lines with an `error` and lines cut by
    a kill are skipped (the errors are returned by `load_errors`)."""
    best = {}
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            r = o.get("record")
            if r is None:
                continue
            best[(r["arm"], r["step"], r["qid"])] = r
    return [best[k] for k in sorted(best, key=lambda k: (k[1], k[2]))]


def load_errors(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if "error" in o:
                    out.append(o)
    return out


def done_keys(path):
    """{(arm, step, qid)} already recorded with a `record` (resume)."""
    return {(r["arm"], r["step"], r["qid"]) for r in load_records(path)}


# ------------------------------------------------------------------------------------------------------------------------------
# the 2x2
# ------------------------------------------------------------------------------------------------------------------------------
def is_abstention(verdict):
    return verdict.startswith("UNKNOWN")


def gold_entries(rec):
    return rec.get("gold") or []


def is_present(rec):
    return rec["kind"] == "intra2" and bool(rec["entered"])


def single_wrong(rec):
    """単独誤答: the verdict is ANSWER (one entry in all) and no entry holds the gold.  (For an unans question, which has no gold, every ANSWER is one.)"""
    return rec["verdict"] == ANSWER and rec["listed"] == 1 and not gold_entries(rec)


def classify(rec):
    """-> (row, cell, sub): row in (present, absent), cell in (correct, miss, wrong), sub = the miss kind or None.  Raises on a verdict shape it does not know
    and on an entry `from_evidence` before its article entered (impossible)."""
    v = rec["verdict"]
    if v not in (ANSWER, CHOICE) and not is_abstention(v):
        raise ValueError("unknown verdict %r" % (v,))
    if v == ANSWER and rec["listed"] != 1:
        raise ValueError("an ANSWER lists exactly one entry, not %r" % (rec["listed"],))
    if is_abstention(v) and rec["listed"] != 0:
        raise ValueError("an abstention lists nothing, not %r" % (rec["listed"],))
    gold = gold_entries(rec)
    from_ev = any(g["from_evidence"] for g in gold)
    row = PRESENT if is_present(rec) else ABSENT
    if from_ev and row == ABSENT:
        raise ValueError("an entry is from the evidence article before the article entered (%s step %s %s)" % (rec.get("arm"), rec.get("step"), rec.get("qid")))
    if row == PRESENT:
        if from_ev:
            return row, CORRECT, None
        if is_abstention(v):
            return row, MISS, SUB_ABSTAIN
        if v == ANSWER and not gold:
            return row, WRONG, None
        if gold:
            return row, MISS, SUB_NOT_FROM_EVIDENCE
        return row, MISS, SUB_LIST_NO_GOLD
    if is_abstention(v):
        return row, CORRECT, None
    if v == ANSWER and not gold:
        return row, WRONG, None
    return row, MISS, SUB_FALSE_PRESENCE


def flag_unknown(rec, key):
    """An intra2 record whose arm flag is set but whose flag `key` is None: the arrival oracle that makes the 3-tier flag did not load."""
    return rec["kind"] == "intra2" and rec.get(OWN_UNARRIVED) is not None and rec.get(key) is None


def table_2x2(recs, key=None):
    """The counts of one (arm, step): the two rows, the cells and the miss kinds, gold in a candidate (present intra2 only), 未着 and the lists' sizes.
    `key` = the 未着 flag that leaves a question out of the headline (default: the arm's primary flag).  The headline present row `present_den` is the present
    row WITHOUT the 未着 questions (owner: 未着 is excluded from the denominator and counted apart); `present` keeps all of them."""
    if key is None:
        key = primary_key(recs[0]["arm"]) if recs else OWN_UNARRIVED
    t = {PRESENT: collections.Counter(), ABSENT: collections.Counter()}
    den, sub, sub_den = collections.Counter(), collections.Counter(), collections.Counter()
    out = {"n": len(recs), "gold_in_candidate": 0, "present_unarrived": 0, "present_unarrived_own": 0, "present_unarrived_unknown": 0, "single_wrong": 0,
           "listed": [], "read": collections.defaultdict(list), "key": key}
    for r in recs:
        row, cell, s = classify(r)
        t[row]["n"] += 1
        t[row][cell] += 1
        if s:
            sub[(row, s)] += 1
        if row == PRESENT:
            if gold_entries(r):
                out["gold_in_candidate"] += 1
            if flag_unknown(r, key):
                out["present_unarrived_unknown"] += 1
            if r.get(OWN_UNARRIVED):
                out["present_unarrived_own"] += 1
            if r.get(key):
                out["present_unarrived"] += 1
            else:                                              # the headline row: a question whose flag is unknown stays in it (and is counted above)
                den["n"] += 1
                den[cell] += 1
                if s:
                    sub_den[(row, s)] += 1
        if single_wrong(r):
            out["single_wrong"] += 1
        out["listed"].append(r["listed"])
        for tier, d in (r.get("tiers") or {}).items():
            out["read"][tier].append(len(d.get("read", ())))
    out["present"], out["absent"], out["sub"] = dict(t[PRESENT]), dict(t[ABSENT]), dict(sub)
    out["present_den"], out["sub_den"] = dict(den), dict(sub_den)
    out["listed_median"] = _median(out.pop("listed"))
    out["read_median"] = {k: _median(v) for k, v in sorted(out.pop("read").items())}
    return out


def _median(xs):
    return statistics.median(xs) if xs else None


# ------------------------------------------------------------------------------------------------------------------------------
# arrangement oracles: did the cross X change between measured steps j < k?
# ------------------------------------------------------------------------------------------------------------------------------
class DictArr:
    """arr identity per (tier, seed, step) from a dict (synthetic tests; one-shot arms: the sha of Placement.to_bytes() per cache)."""

    def __init__(self, ids, kinds=None):
        self.ids = dict(ids)
        self.kinds_ = dict(kinds or {})

    def changed(self, tier, seed, j, k):
        a, b = self.ids.get((tier, seed, j)), self.ids.get((tier, seed, k))
        if a is None or b is None:
            return None
        return a != b

    def kinds(self, tier, seed, j, k):
        return list(self.kinds_.get((tier, seed, j, k), ()))


class LedgerArr:
    """arr identity of a stack's crosses from its ledgers (stack.py ledger lines, 5.6): a cross is rearranged in (j, k] iff it grew at a step s in (j, k] with
    arr_sha changing (充填 `filled`, or 絞り `narrowed`: `dropped_new` units that left, or `dropped_recount` = left through the recount only).  A cross that only
    recorded units as left, or was only re-counted, keeps its arr_sha.  Built from the LAST snapshot's ledgers (all steps up to it)."""

    def __init__(self, changes, born, last_step):
        self.changes = changes          # {tier: {seed: [(step, (kind, ...))]}}
        self.born = born                # {tier: {seed: step}}
        self.last_step = last_step

    @classmethod
    def from_ledgers(cls, ledgers):
        changes, born, last = {}, {}, 0
        for tier, lines in ledgers.items():
            ch, bn = collections.defaultdict(list), {}
            for line in lines:
                e = json.loads(line)
                s = e["step"]
                last = max(last, s)
                for seed in e["opened"]:
                    bn[seed] = s
                for g in e["grown"]:
                    if g["arr"][0] == g["arr"][1]:
                        continue
                    kinds = []
                    if g["filled"]:
                        kinds.append("fill")
                    if g["narrowed"]:
                        kinds.append("narrow_new" if g["dropped_new"] else "narrow_recount")
                    ch[g["seed"]].append((s, tuple(kinds)))
            changes[tier], born[tier] = dict(ch), bn
        return cls(changes, born, last)

    def changed(self, tier, seed, j, k):
        if seed not in self.born.get(tier, {}) or k > self.last_step:
            return None
        return any(j < s <= k for s, _ in self.changes[tier].get(seed, ()))

    def kinds(self, tier, seed, j, k):
        return sorted({x for s, ks in self.changes.get(tier, {}).get(seed, ()) if j < s <= k for x in ks})


def _tier_read(rec, tier):
    return ((rec.get("tiers") or {}).get(tier) or {}).get("read", ())


def gold_crosses(rec):
    """The (tier, seed) crosses that held the gold of the entries that made H: gold entries from the evidence article."""
    out = []
    for g in gold_entries(rec):
        if not g["from_evidence"]:
            continue
        for o in g["origins"]:
            x = (o["tier"], o["seed"])
            if x not in out:
                out.append(x)
    return out


def cause_tags(rec_j, rec_k, arr):
    """-> ([(tier, seed, tag, kinds)], ...) for the gold-holding crosses of step j, judged at step k."""
    j, k = rec_j["step"], rec_k["step"]
    out = []
    for tier, seed in gold_crosses(rec_j):
        ch = arr.changed(tier, seed, j, k)
        if ch is None:
            tag, kinds = Q_, []
        elif ch:
            tag, kinds = R, arr.kinds(tier, seed, j, k)
        elif seed not in _tier_read(rec_k, tier):
            tag, kinds = U, []
        else:
            tag, kinds = A_, []
        out.append((tier, seed, tag, kinds))
    return out


def is_H(rec):
    return classify(rec) == (PRESENT, CORRECT, None)


def is_G(rec):
    return bool(gold_entries(rec))


# ------------------------------------------------------------------------------------------------------------------------------
# the events of one question
# ------------------------------------------------------------------------------------------------------------------------------
def is_unarrived(rec, key=OWN_UNARRIVED):
    """True / False; None when the flag is unknown (the arm's flag is set, `key` is None: the arrival oracle did not load)."""
    if flag_unknown(rec, key):
        return None
    return bool(rec.get(key))


def never_tag(rec, key=OWN_UNARRIVED):
    """Why a question never appeared, judged at its last record (7.4): 未着 (no unit of the arm's tiers holds the gold), 非根拠 (gold in a candidate, but not from
    the evidence article), else the site analysis of the record (未着席 / 未読 / 未採択), else 未特定."""
    if is_unarrived(rec, key):
        return "未着"
    if is_G(rec):
        return "非根拠"
    site = rec.get("site")
    if site and site.get("tag"):
        return site["tag"]
    return "未特定"


def question_events(series, arr, key=None, schedule=None):
    """series = the records of ONE intra2 question (one arm), any order.  Only measured steps >= e(q) take part (L-G4-30).  `key` = the 未着 flag (default: the
    arm's primary one); `schedule` = the steps of the arm (default: the steps of this series): e(q) on it makes a later appearance 後から, off it the entry is
    unmeasured (at_entry None).  -> a dict (see the module doc)."""
    s = sorted(series, key=lambda r: r["step"])
    if not s:
        raise ValueError("an empty series")
    qid, e = s[0]["qid"], s[0]["e"]
    if any(r["qid"] != qid for r in s) or any(r["kind"] != "intra2" for r in s):
        raise ValueError("question_events takes the series of one intra2 question")
    if key is None:
        key = primary_key(s[0].get("arm"))
    sched = set(schedule) if schedule is not None else {r["step"] for r in s}
    M = [r for r in s if r["step"] >= e]
    ev = {"qid": qid, "e": e, "steps": [r["step"] for r in M], "unarrived_final": None, "appear": None, "at_entry": None, "delay": None,
          "late_input": None, "stay": None, "stay_G": None, "appear_G": None, "losses": [], "returned": None, "never": None, "gold_in_candidate_final": None, "H_final": None,
          "entry_measured": any(r["step"] == e for r in M), "entry_on_schedule": e in sched, "key": key}
    if not M:
        return ev
    last = M[-1]
    ev["unarrived_final"] = is_unarrived(last, key)
    ev["gold_in_candidate_final"] = is_G(last)
    H = [is_H(r) for r in M]
    ev["H_final"] = H[-1]
    G = [is_G(r) for r in M]
    if any(H):
        i = H.index(True)
        ev["appear"] = M[i]["step"]
        ev["delay"] = M[i]["step"] - e
        # 直入 = delay 0.  A later appearance is 後から iff e(q) is on the arm's schedule (a missing e(q) record is no 直入); off the schedule (arm C) the entry
        # step was never measured and the label is unknowable: None.
        ev["at_entry"] = True if ev["delay"] == 0 else (False if ev["entry_on_schedule"] else None)
        ev["late_input"] = bool(ev["delay"] > 0 and any(
            (o.get("seats_after_entry") or 0) > 0 or g.get("src_after_entry")
            for g in gold_entries(M[i]) if g["from_evidence"] for o in g["origins"]))
        later = H[i + 1:]
        ev["stay"] = (sum(later), len(later))
    if any(G):
        iG = G.index(True)
        ev["appear_G"] = M[iG]["step"]
        later = G[iG + 1:]
        ev["stay_G"] = (sum(later), len(later))
    losses, pending = [], []
    for n in range(1, len(M)):
        if H[n - 1] and not H[n]:
            tags = cause_tags(M[n - 1], M[n], arr)
            sw = single_wrong(M[n])
            kinds = collections.Counter(t for _, _, t, _ in tags)
            mixed_bad = any(t != R for _, _, t, _ in tags) or not tags
            cls = BREAK if (sw or mixed_bad) else GROWTH
            reason = "single_wrong" if sw else ("cause" if mixed_bad else "rearranged")
            rk = sorted({x for _, _, t, ks in tags if t == R for x in ks})
            losses.append({"from": M[n - 1]["step"], "to": M[n]["step"], "class": cls, "reason": reason, "single_wrong": sw,
                           "tags": dict(sorted(kinds.items())), "rearrangement_kinds": rk,
                           "crosses": [[a, b, c] for a, b, c, _ in tags], "returns": None})
            pending.append(losses[-1])
        elif H[n] and pending:
            for L in pending:
                L["returns"] = M[n]["step"]
            pending = []
    ev["losses"] = losses
    ev["returned"] = any(L["returns"] is not None for L in losses) if losses else None
    if ev["appear"] is None:
        ev["never"] = never_tag(last, key)
    return ev


def by_question(records):
    out = collections.defaultdict(list)
    for r in records:
        out[r["qid"]].append(r)
    return out


def events_of(records, arr, key=None, schedule=None):
    """{qid: events} for the intra2 questions of the records.  `key` = which 未着 flag leaves a question out of the denominator: "unarrived" (no unit of the ARM's
    tiers holds the gold) or "unarrived_3tier" (no unit of RUN / WORD / CHAR does: differs from the first only for a CHAR-only arm); default = the arm's primary
    flag (PRIMARY_UNARRIVED).  `schedule` = the arm's steps (default: every step that has a record, of any question)."""
    sched = set(schedule) if schedule is not None else {r["step"] for r in records}
    return {q: question_events(v, arr, key, sched) for q, v in sorted(by_question(records).items()) if v[0]["kind"] == "intra2"}


def summarize_events(evs):
    """The counts over a set of question events (the last measured step of each question is its 'final')."""
    n = len(evs)
    entered = [e for e in evs.values() if e["steps"]]
    un = [e for e in entered if e["unarrived_final"]]
    unk = [e for e in entered if e["unarrived_final"] is None]
    den = [e for e in entered if e["unarrived_final"] is False]          # a question with an unknown flag is in neither (shown as `unarrived_unknown`)
    app = [e for e in den if e["appear"] is not None]
    s = {"intra2": n, "entered": len(entered), "unarrived": len(un), "unarrived_unknown": len(unk), "denominator": len(den), "appeared": len(app),
         "at_entry": sum(1 for e in app if e["at_entry"] is True), "later": sum(1 for e in app if e["at_entry"] is False),
         "appeared_entry_unmeasured": sum(1 for e in app if e["at_entry"] is None),
         "late_input": sum(1 for e in app if e["late_input"]),
         "never": dict(sorted(collections.Counter(e["never"] for e in den if e["appear"] is None).items())),
         "stay_all": sum(1 for e in app if e["stay"] and e["stay"][0] == e["stay"][1]),
         "stay_with_later": sum(1 for e in app if e["stay"] and e["stay"][1] > 0),
         "stay_num": sum(e["stay"][0] for e in app if e["stay"]), "stay_den": sum(e["stay"][1] for e in app if e["stay"]),
         "gold_in_candidate_final": sum(1 for e in den if e["gold_in_candidate_final"]),
         "appeared_G": sum(1 for e in den if e["appear_G"] is not None)}
    losses = [L for e in app for L in e["losses"]]
    # a question that never appeared has no loss: H was never true
    s["losses"] = len(losses)
    s["breaks"] = sum(1 for L in losses if L["class"] == BREAK)
    s["growth"] = sum(1 for L in losses if L["class"] == GROWTH)
    s["single_wrong_losses"] = sum(1 for L in losses if L["single_wrong"])
    s["returned"] = sum(1 for e in app if e["returned"])
    tag = collections.Counter()
    for L in losses:
        for t, c in L["tags"].items():
            tag[t] += c
    s["tag_crosses"] = dict(sorted(tag.items()))
    s["break_reason"] = dict(sorted(collections.Counter(L["reason"] for L in losses if L["class"] == BREAK).items()))
    s["rearrangement_kinds"] = dict(sorted(collections.Counter(k for L in losses for k in L["rearrangement_kinds"]).items()))
    s["unknown_cause"] = sum(1 for L in losses if Q_ in L["tags"])
    return s


# ------------------------------------------------------------------------------------------------------------------------------
# absent row series
# ------------------------------------------------------------------------------------------------------------------------------
def absent_series(records):
    """Per question and the steps where it is on the absent row (unans at every step, intra2 before e(q)): the verdict classes and the first step with a single
    ANSWER (単独誤答が現れる)."""
    out = {}
    for q, v in sorted(by_question(records).items()):
        rows = [r for r in sorted(v, key=lambda r: r["step"]) if not is_present(r)]
        if not rows:
            continue
        cls = collections.Counter(classify(r)[1:] for r in rows)
        sw = [r["step"] for r in rows if single_wrong(r)]
        out[q] = {"kind": rows[0]["kind"], "steps": len(rows), "classes": {"%s/%s" % k: c for k, c in sorted(cls.items(), key=lambda x: (x[0][0], str(x[0][1])))},
                  "first_single_wrong": sw[0] if sw else None, "single_wrong_steps": len(sw)}
    return out


# ------------------------------------------------------------------------------------------------------------------------------
# markdown
# ------------------------------------------------------------------------------------------------------------------------------
def pct(a, b):
    if not b:
        return "-"
    x = (a * 1000 + b // 2) // b
    return "%d.%d%%" % (x // 10, x % 10)


def ratio(a, b):
    return "%d/%d" % (a, b)


def fmt_med(x):
    if x is None:
        return "-"
    return str(int(x)) if x == int(x) else "%d.5" % int(x)


def per_step_rows(records, key=None):
    by = collections.defaultdict(list)
    for r in records:
        by[r["step"]].append(r)
    return [(k, table_2x2(v, key)) for k, v in sorted(by.items())]


def key_label(key):
    return "3-tier flag: no RUN / WORD / CHAR unit holds the gold" if key == TIER3_UNARRIVED else "the arm's own tiers"


def render_step_table(records, key=None):
    """The headline 2x2 per step.  The present row is shown WITHOUT the 未着 questions (owner): `denominator` = present - 未着 and the cells below it add up to the
    denominator; `present` and the 未着 count (primary flag; the arm's own count beside it when the primary flag is another one) stay visible."""
    if key is None and records:
        key = primary_key(records[0]["arm"])
    own = key != OWN_UNARRIVED
    head = ("| step | present (all) | 未着 (%s) | %sdenominator = present - 未着 | correct | correct / denominator | miss (abstain / list-no-gold / not-from-evidence) | "
            "confident wrong | gold in a candidate (present) | absent | correct (abstained) | false presence | confident wrong | single ANSWER | median listed | "
            "crosses read (median/tier) |\n|" % (key, "未着 (the arm's own tiers) | " if own else "")) + "---|" * (16 + (1 if own else 0)) + "\n"
    out = [head]
    for k, t in per_step_rows(records, key):
        p, d, a, sub = t["present"], t["present_den"], t["absent"], t["sub_den"]
        out.append("| %d | %d | %d%s | %s%d | %d | %s | %d / %d / %d | %d | %d | %d | %d | %d | %d | %d | %s | %s |\n" % (
            k, p.get("n", 0), t["present_unarrived"], " (+%d unknown)" % t["present_unarrived_unknown"] if t["present_unarrived_unknown"] else "",
            ("%d | " % t["present_unarrived_own"]) if own else "", d.get("n", 0), d.get(CORRECT, 0), pct(d.get(CORRECT, 0), d.get("n", 0)),
            sub.get((PRESENT, SUB_ABSTAIN), 0), sub.get((PRESENT, SUB_LIST_NO_GOLD), 0), sub.get((PRESENT, SUB_NOT_FROM_EVIDENCE), 0), d.get(WRONG, 0),
            t["gold_in_candidate"], a.get("n", 0), a.get(CORRECT, 0), t["sub"].get((ABSENT, SUB_FALSE_PRESENCE), 0), a.get(WRONG, 0), t["single_wrong"],
            fmt_med(t["listed_median"]), " ".join("%s %s" % (x, fmt_med(m)) for x, m in t["read_median"].items())))
    return "".join(out)


def render_events(evs, own_evs=None):
    """The events table.  `own_evs` = the same events under the arm's own flag, when the primary flag is another one (B, C_B): its 未着 count stands beside."""
    s = summarize_events(evs)
    key = next(iter(evs.values()))["key"] if evs else OWN_UNARRIVED
    L = []
    L.append("| quantity | value |\n|---|---|\n")
    L.append("| intra2 questions with a record at or after their entry | %d of %d |\n" % (s["entered"], s["intra2"]))
    L.append("| 未着 at the last step, flag `%s` (%s): left out of the denominator | %d |\n" % (key, key_label(key), s["unarrived"]))
    if own_evs is not None:
        L.append("| 未着 at the last step, the arm's own flag `unarrived` (its own tiers only): beside, not used for the denominator | %d |\n" % summarize_events(own_evs)["unarrived"])
    if s["unarrived_unknown"]:
        L.append("| **未着 UNKNOWN (the flag `%s` is None: the arrival oracle did not load); in neither the denominator nor 未着** | %d |\n" % (key, s["unarrived_unknown"]))
    L.append("| denominator of 現れる | %d |\n" % s["denominator"])
    L.append("| 現れる (H at some measured step) | %s (%s) |\n" % (ratio(s["appeared"], s["denominator"]), pct(s["appeared"], s["denominator"])))
    L.append("| 　直入 (appeared at e(q), delay 0) / 後から (later, e(q) on the schedule) | %d / %d |\n" % (s["at_entry"], s["later"]))
    L.append("| 　appeared with e(q) NOT on the arm's schedule (直入 / 後から unknowable) | %d |\n" % s["appeared_entry_unmeasured"])
    L.append("| 　後から whose gold entry cites a sentence, or its cross a seat, from after the entry | %d |\n" % s["late_input"])
    L.append("| never appeared, by tag (the site tags read the ARM's own tiers: for a CHAR-only arm 未着 here = no CHAR unit holds the gold) | %s |\n" % (", ".join("%s %d" % kv for kv in s["never"].items()) or "-"))
    L.append("| 残る: appeared questions with H at every later measured step | %s of %s that have a later step |\n" % (s["stay_all"], s["stay_with_later"]))
    L.append("| 残る: share of later measured steps still holding the gold | %s (%s) |\n" % (ratio(s["stay_num"], s["stay_den"]), pct(s["stay_num"], s["stay_den"])))
    L.append("| gold in a candidate at the last step (denominator questions) | %s |\n" % ratio(s["gold_in_candidate_final"], s["denominator"]))
    L.append("| losses of H (consecutive measured steps) | %d |\n" % s["losses"])
    L.append("| 　壊れる | %d (%s) |\n" % (s["breaks"], ", ".join("%s %d" % kv for kv in s["break_reason"].items()) or "-"))
    L.append("| 　置き換え (growth: every gold cross R) | %d (rearrangement kinds: %s) |\n" % (s["growth"], ", ".join("%s %d" % kv for kv in s["rearrangement_kinds"].items()) or "-"))
    L.append("| 　単独誤答化 | %d |\n" % s["single_wrong_losses"])
    L.append("| 　cause tags over the gold crosses of all losses | %s |\n" % (", ".join("%s %d" % kv for kv in s["tag_crosses"].items()) or "-"))
    L.append("| 　loss with an unlookable cross (?) | %d |\n" % s["unknown_cause"])
    L.append("| 戻る (H again after a loss) | %d |\n" % s["returned"])
    return "".join(L), s


def render_question_table(evs):
    out = ["| id | e | appear | delay | 残る | losses (j -> k: class, tags) | final |\n|---|---|---|---|---|---|---|\n"]
    for q, e in evs.items():
        stay = "-" if not e["stay"] else ratio(*e["stay"])
        loss = "; ".join("%d->%d %s %s" % (L["from"], L["to"], "壊れる" if L["class"] == BREAK else "置換",
                                           "".join("%s%d" % kv for kv in L["tags"].items())) for L in e["losses"]) or "-"
        if e["unarrived_final"]:
            fin = "未着"
        elif e["unarrived_final"] is None:
            fin = "未着 UNKNOWN"
        elif e["appear"] is None:
            fin = e["never"]
        elif e["H_final"]:
            fin = "H"
        else:
            fin = "lost (G)" if e["gold_in_candidate_final"] else "lost"
        out.append("| %s | %s | %s | %s | %s | %s | %s |\n" % (q, e["e"], e["appear"] if e["appear"] is not None else "-",
                                                             e["delay"] if e["delay"] is not None else "-", stay, loss, fin))
    return "".join(out)


def render_absent(ab):
    kinds = collections.defaultdict(collections.Counter)
    first = []
    for q, d in ab.items():
        for c, n in d["classes"].items():
            kinds[d["kind"]][c] += n
        if d["first_single_wrong"] is not None:
            first.append((d["first_single_wrong"], q))
    out = ["| kind | cells over all (question, step) pairs on the absent row |\n|---|---|\n"]
    for k, c in sorted(kinds.items()):
        out.append("| %s | %s |\n" % (k, ", ".join("%s %d" % kv for kv in sorted(c.items()))))
    out.append("\nsingle ANSWER (単独誤答) first appears, per question: %s\n" % (", ".join("%s@%d" % (q, s) for s, q in sorted(first)) or "none"))
    return "".join(out)


def render_md(arm, records, arr, meta=None, errors=(), schedule=None, one_char=None):
    """`schedule` = the arm's planned steps (events.scheduled_steps): the predictions are judged only when every one of them is complete.  `one_char` = the qids
    whose gold has a one-character alternative (P-12)."""
    key = primary_key(arm)
    unknown = sum(1 for r in records if flag_unknown(r, key))
    used = OWN_UNARRIVED if unknown else key                          # an unavailable primary flag falls back to the arm's own, loudly
    evs = events_of(records, arr, used, schedule) if arr is not None else {}
    own_evs = events_of(records, arr, OWN_UNARRIVED, schedule) if (arr is not None and used != OWN_UNARRIVED) else None
    L = ["# G4 meter -- arm %s\n\n" % arm]
    steps = sorted({r["step"] for r in records})
    L.append("Records: %d (%d steps: %s), errors recorded: %d.  Format %s.\n" % (
        len(records), len(steps), ",".join(map(str, steps[:80])) + (" ..." if len(steps) > 80 else ""), len(errors), FORMAT))
    if unknown:
        L.append("\n**WARNING: the primary 未着 flag `%s` is None in %d record(s): the arrival oracle (the 3-tier ledgers) did not load.  The tables below use the arm's own "
                 "flag `%s` (%s) instead, which for a CHAR-only arm calls almost every gold 未着; do not compare them with arm A.**\n" % (key, unknown, OWN_UNARRIVED, key_label(OWN_UNARRIVED)))
    if meta:
        L.append("Config: %s\n" % json.dumps(meta, sort_keys=True, ensure_ascii=False))
    L.append("\n## 2x2 per step (headline = the correct cells over the present row WITHOUT 未着, 未着 counted apart; gold in a candidate beside it)\n\n")
    L.append(render_step_table(records, used))
    if evs:
        txt, _s = render_events(evs, own_evs)
        L.append("\n## Events (現れる / 残る / 壊れる), 未着 flag `%s`\n\n" % used + txt)
        L.append("\n## Per question\n\n" + render_question_table(evs))
    L.append("\n## Absent row (unans at every step; intra2 before entry)\n\n" + render_absent(absent_series(records)))
    if evs and records:
        last = max(schedule) if schedule else max(r["step"] for r in records)
        L.append("\n## Registered predictions (PREDICTIONS.md) judgeable from this arm alone\n\n" +
                 render_predictions({arm: (records, evs)}, last, {arm: schedule} if schedule else None, one_char))
    if errors:
        by = collections.Counter(e.get("step") for e in errors)
        L.append("\n## Worker errors (recorded, retried on resume)\n\n" + ", ".join("step %s: %d" % kv for kv in sorted(by.items(), key=lambda x: str(x[0]))) + "\n")
    return "".join(L)


# ------------------------------------------------------------------------------------------------------------------------------
# the registered predictions (PREDICTIONS.md): held / failed / not judged
# ------------------------------------------------------------------------------------------------------------------------------
N_INTRA2, N_UNANS = 69, 25


def _at(records, step):
    return [r for r in records if r["step"] == step]


def _h_set(records, step):
    return {r["qid"] for r in _at(records, step) if r["kind"] == "intra2" and is_H(r)}


def _complete(records, step, n_intra2=N_INTRA2, n_unans=N_UNANS):
    rs = _at(records, step)
    return sum(1 for r in rs if r["kind"] == "intra2") == n_intra2 and sum(1 for r in rs if r["kind"] == "unans") == n_unans


def incomplete_steps(records, steps):
    return [k for k in sorted(steps) if not _complete(records, k)]


def judge(arms, last=300, schedules=None, one_char=None):
    """arms = {arm: (records, events)}.  -> [(id, text, value, status)] with status held / failed / not judged (why).  A prediction is judged only for arms whose
    EVERY scheduled step is complete (69 intra2 + 25 unans; `schedules[arm]` = the arm's planned steps, default the steps that have a record, and `last`): a hole in
    a middle step would change the 残る / 戻る / 未着-return series, not only the step-`last` counts.  `one_char` = the qids whose gold has a one-character
    alternative (P-12 leaves them out); None makes P-12 unjudged."""
    out = []
    schedules = schedules or {}

    def sched(a):
        return sorted(set(schedules.get(a) or {r["step"] for r in arms[a][0]}) | {last})

    def need(*names):
        miss = [a for a in names if a not in arms]
        if miss:
            return "not judged: no records of arm %s" % ",".join(miss)
        bad = {a: incomplete_steps(arms[a][0], sched(a)) for a in names}
        bad = {a: v for a, v in bad.items() if v}
        if bad:
            return "not judged: %s" % "; ".join("arm %s has %d of %d scheduled steps incomplete (e.g. %s)" % (a, len(v), len(sched(a)), ",".join(map(str, v[:4]))) for a, v in sorted(bad.items()))
        return None

    def put(pid, text, value, ok, why):
        out.append((pid, text, value, why if why else ("held" if ok else "failed")))

    if "A" in arms:
        why = need("A")
        recs, evs = arms["A"]
        sm = summarize_events(evs)
        # P-1: most appearances are 直入 AND 後から <= 5; an appearance whose entry step is off the schedule can go either way, so the verdict is the worst and
        # the best case, and "not judged" when they differ
        ap, ent, lat, unk = sm["appeared"], sm["at_entry"], sm["later"], sm["appeared_entry_unmeasured"]
        worst = lat + unk <= 5 and ent * 2 > ap
        best = lat <= 5 and (ent + unk) * 2 > ap
        p1 = why or (None if ap else "not judged: no question appeared")
        if p1 is None and worst != best:
            p1 = "not judged: %d appeared question(s) have an unmeasured entry step" % unk
        put("P-1", "A: most 現れる are 直入 (more than half) and 後から <= 5 of 69", "直入 %d, 後から %d, entry unmeasured %d, of %d appeared" % (ent, lat, unk, ap), worst, p1)
        tags = sm["tag_crosses"]
        put("P-3", "A: among losses U > R > A, and 単独誤答化 <= 2", "tags %s; 単独誤答化 %d" % (tags, sm["single_wrong_losses"]),
            tags.get("U", 0) > tags.get("R", 0) > tags.get("A", 0) and sm["single_wrong_losses"] <= 2, why or (None if sm["losses"] else "not judged: no loss of H in the records"))
        un = [r for r in _at(recs, last) if r["kind"] == "intra2" and r.get("unarrived")]
        put("P-8", "A: 未着 at 300 is 5..25 of 69", "%d" % len(un), 5 <= len(un) <= 25, why)
        seen_arrived, bad = set(), 0
        for r in sorted((r for r in recs if r["kind"] == "intra2" and r["unarrived"] is not None), key=lambda r: (r["qid"], r["step"])):
            if not r["unarrived"]:
                seen_arrived.add(r["qid"])
            elif r["qid"] in seen_arrived:
                bad += 1
        put("P-9", "A: 未着 never returns once a gold unit exists", "%d returns" % bad, bad == 0, why)
        app = [e for e in evs.values() if e["appear"] is not None and e["unarrived_final"] is False and e["stay"] and e["stay"][1] > 0]
        stay = sum(1 for e in app if e["stay"][0] == e["stay"][1])
        put("P-10", "A: >= 75% of the appeared questions with a later step are 残る at every later step", "%d of %d (%s)" % (stay, len(app), pct(stay, len(app))),
            stay * 4 >= len(app) * 3, why or (None if app else "not judged: no appeared question has a later step"))
        h = _h_set(recs, last)
        put("P-11", "A: present-correct at 300 <= 20 of 69", "%d" % len(h), len(h) <= 20, why)
    if "B" in arms:
        h = _h_set(arms["B"][0], last)
        put("P-5", "B: present-correct at 300 <= 3 of 69", "%d" % len(h), len(h) <= 3, need("B"))
    if "A" in arms or "C" in arms:
        # P-4 is about BOTH arms: it is judged only when both are present and complete (a verdict on one arm would be a verdict on half the prediction)
        vals, absent_ok, any_wrong = [], [], False
        for a in ("A", "C"):
            if a in arms:
                rs = [r for r in _at(arms[a][0], last) if r["kind"] == "unans"]
                c = sum(1 for r in rs if classify(r)[1] == CORRECT)
                vals.append("%s %d/%d abstain" % (a, c, len(rs)))
                absent_ok.append(c <= 5)
                any_wrong |= any(single_wrong(r) for r in arms[a][0] if not is_present(r))
        put("P-4", "A, C: unans absent-correct at 300 <= 5 of 25 for both, and >= 1 confident wrong on the absent row somewhere", "; ".join(vals) + "; single ANSWER on the absent row: %s" % any_wrong,
            len(absent_ok) == 2 and all(absent_ok) and any_wrong, need("A", "C"))
    if "A" in arms and "C" in arms:
        ga = sum(1 for r in _at(arms["A"][0], last) if r["kind"] == "intra2" and is_G(r))
        gc = sum(1 for r in _at(arms["C"][0], last) if r["kind"] == "intra2" and is_G(r))
        put("P-2", "A <= C@300 - 3 on gold in a candidate", "A %d, C %d" % (ga, gc), ga <= gc - 3, need("A", "C"))
    if "A" in arms and "A0" in arms:
        ha, h0 = len(_h_set(arms["A"][0], last)), len(_h_set(arms["A0"][0], last))
        put("P-6", "|A - A0| <= 3 on present-correct at 300", "A %d, A0 %d" % (ha, h0), abs(ha - h0) <= 3, need("A", "A0"))
    if "A" in arms and "B" in arms:
        ga = sum(1 for r in _at(arms["A"][0], last) if r["kind"] == "intra2" and is_G(r))
        gb = sum(1 for r in _at(arms["B"][0], last) if r["kind"] == "intra2" and is_G(r))
        extra_all = sorted(_h_set(arms["B"][0], last) - _h_set(arms["A"][0], last))
        extra = [q for q in extra_all if q not in (one_char or ())]
        put("P-12", "B: gold in a candidate at 300 <= A's, and no B-correct question that A lacks (a question with a one-character gold alternative aside)",
            "A %d, B %d; B-only %s (of which one-character golds, left out: %s)" % (ga, gb, extra, sorted(set(extra_all) - set(extra)) if one_char is not None else "unknown"),
            gb <= ga and not extra, need("A", "B") or (None if one_char is not None else "not judged: the gold lengths are unknown (pass the bank)"))
    out.append(("P-7", "stack: the closed share at 300 is higher with the foundation on than off", "not computed by the meter", "not judged: a structure fact (gate G-2 / stack ledgers), not a question"))
    return sorted(out, key=lambda x: int(x[0].split("-")[1]))


def render_predictions(arms, last=300, schedules=None, one_char=None):
    rows = judge(arms, last, schedules, one_char)
    return "| id | prediction | value | status |\n|---|---|---|---|\n" + "".join("| %s | %s | %s | %s |\n" % r for r in rows)


# ------------------------------------------------------------------------------------------------------------------------------
# arm-level arrangement oracles from disk
# ------------------------------------------------------------------------------------------------------------------------------
def stack_arr(stack_root, foundation, level="mid", order="forward"):
    """LedgerArr from the LAST snapshot of a stack directory's ledgers (the manifest names it)."""
    from verantyx.line3 import foundation as fd          # noqa: WPS433 (only the path scheme is needed, never a tokeniser)
    d = os.path.join(stack_root, "%s__%s__%s" % (fd.foundation_key() if foundation == "on" else "off", level, order))
    best = None
    with open(os.path.join(d, "manifest.jsonl"), encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            if best is None or m["step"] > best["step"]:
                best = m
    p12 = best["prefix_sha256"][:12]
    led = {}
    for t in best["tiers"]:
        with open(os.path.join(d, "%s_ledger_%s.jsonl" % (t, p12)), encoding="utf-8") as f:
            led[t] = f.read().splitlines()
    return LedgerArr.from_ledgers(led)


def sha_arr(path):
    """DictArr from the meter's one-shot arrangement table (`meter_<arm>.<key>.arr.jsonl`: one line {step, tier, arr: {seed: sha12}}).  A line cut by a kill (it does
    not parse) is skipped, as in every other reader: the meter writes that (step, tier) again on the next run."""
    ids = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                for seed, sha in o["arr"].items():
                    ids[(o["tier"], seed, o["step"])] = sha
    return DictArr(ids)


STACK_ARMS = {"A": ("on", "forward"), "B": ("on", "forward"), "A0": ("off", "forward"), "A_rev": ("on", "reverse")}
DEFAULT_STACK = os.path.join(VERA_IMPL, "cache", "g4_stack_A")
STEPS_JSON = os.path.join(HERE, "steps.json")
BANK = os.path.join(ROOT, "experiments", "line3", "bank2", "bank2.tsv")
SCORER = os.path.join(ROOT, "experiments", "line3", "t9", "scorer.py")


def arr_for(arm, arr_path, stack_root, level="mid"):
    if arm in STACK_ARMS:
        f, o = STACK_ARMS[arm]
        return stack_arr(stack_root, f, level, o)
    return sha_arr(arr_path)


def one_char_qids(bank_path=BANK, corpus="fulllead"):
    """The qids whose gold has a one-character alternative after the scorer's normalisation (a CHAR unit can hold such a gold: P-12 leaves these out).  The scorer
    is the T9 file itself (pure: re, unicodedata), loaded by path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("g4_scorer_events", SCORER)
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    out = set()
    with open(bank_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            r = line.rstrip("\n").split("\t")
            if r[2] == corpus and r[5] and any(len(g) == 1 for g in sc.golds(r[5])):
                out.add(r[0])
    return out


def summary_md(arms, last=300, schedules=None, one_char=None, headline=None):
    """results/summary.md: the step-`last` headline per arm, and the registered predictions that the arms present can judge.  arms = {arm: (records, events)}.  The
    present row is WITHOUT the 未着 questions (owner), per arm by its primary flag; B and C_B show their own CHAR-only count beside it."""
    L = ["# G4 meter -- summary\n\n", "Arms with records: %s.  Per-arm tables: `meter_<arm>.<key>.md`.\n\n" % ", ".join(sorted(arms))]
    hl = headline if headline is not None else max([r["step"] for recs, _e in arms.values() for r in recs] or [last])        # a partial run (a smoke) shows its own last step
    L.append("## Step %d, per arm (present = intra2 whose article has entered; the headline row is present WITHOUT 未着; gold in a candidate beside it)\n\n" % hl)
    L.append("| arm | records at the step | present (all) | 未着 (primary flag) | 未着 (arm's own tiers) | denominator = present - 未着 | present-correct | correct / denominator | "
             "gold in a candidate | present confident wrong | absent | absent-correct | false presence | absent confident wrong |\n|" + "---|" * 14 + "\n")
    for a in sorted(arms):
        rs = _at(arms[a][0], hl)
        if not rs:
            continue
        t = table_2x2(rs)
        p, d, ab, sub = t["present"], t["present_den"], t["absent"], t["sub"]
        L.append("| %s | %d | %d | %d%s | %d | %d | %d | %s | %d | %d | %d | %d | %d | %d |\n" % (
            a, len(rs), p.get("n", 0), t["present_unarrived"], " (+%d unknown)" % t["present_unarrived_unknown"] if t["present_unarrived_unknown"] else "",
            t["present_unarrived_own"], d.get("n", 0), d.get(CORRECT, 0), pct(d.get(CORRECT, 0), d.get("n", 0)), t["gold_in_candidate"], d.get(WRONG, 0),
            ab.get("n", 0), ab.get(CORRECT, 0), sub.get((ABSENT, SUB_FALSE_PRESENCE), 0), ab.get(WRONG, 0)))
    L.append("\n## Events per arm (denominator without 未着; the primary flag of the arm)\n\n| arm | flag | denominator | 現れる | 直入 / 後から / entry unmeasured | never (tags) | 残る (all later steps) | 壊れる | 置き換え | 単独誤答化 | 戻る |\n|" + "---|" * 11 + "\n")
    for a in sorted(arms):
        sm = summarize_events(arms[a][1])
        if not sm["entered"]:
            continue
        key = next(iter(arms[a][1].values()))["key"]
        L.append("| %s | %s | %d (未着 %d apart%s) | %s | %d / %d / %d | %s | %d of %d | %d | %d | %d | %d |\n" % (
            a, key, sm["denominator"], sm["unarrived"], ", unknown %d" % sm["unarrived_unknown"] if sm["unarrived_unknown"] else "", ratio(sm["appeared"], sm["denominator"]),
            sm["at_entry"], sm["later"], sm["appeared_entry_unmeasured"], ", ".join("%s %d" % kv for kv in sm["never"].items()) or "-", sm["stay_all"], sm["stay_with_later"],
            sm["breaks"], sm["growth"], sm["single_wrong_losses"], sm["returned"]))
    L.append("\n## Registered predictions\n\n" + render_predictions(arms, last, schedules, one_char))
    return "".join(L)


def _discover(results, key=None):
    """{arm: (key, jsonl path)} of the meter files in a results directory; two config keys for one arm are an error unless `key` picks one."""
    found = collections.defaultdict(dict)
    for f in sorted(os.listdir(results)):
        pr = parse_stem(f)
        if pr:
            found[pr[0]][pr[1]] = os.path.join(results, f)
    out = {}
    for arm, ks in found.items():
        if key:
            ks = {k: v for k, v in ks.items() if k == key}
            if not ks:
                continue
        if len(ks) > 1:
            raise ValueError("arm %s has several configs in %s (%s): pick one with --key" % (arm, results, ", ".join(sorted(ks))))
        (k, path), = ks.items()
        out[arm] = (k, path)
    return out


def _arm_inputs(arm, key, path, stack):
    recs = load_records(path)
    cfg = recs[0]["config"] if recs else {}
    arr = arr_for(arm, path[:-len(".jsonl")] + ".arr.jsonl", stack, cfg.get("level", "mid")) if recs else None
    return recs, arr


def main(argv=None):
    ap = argparse.ArgumentParser(description="render results/meter_<arm>.<key>.md (or, with --summary, results/summary.md) from the meter's jsonl")
    ap.add_argument("arm", nargs="?")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    ap.add_argument("--stack", default=DEFAULT_STACK, help="stack cache root for the ledger-based arrangement oracle of the stack arms")
    ap.add_argument("--key", default=None, help="the config key (sha12 in the file name) when a directory holds several runs of one arm")
    ap.add_argument("--bank", default=BANK)
    a = ap.parse_args(argv)
    sys.path.insert(0, ROOT)
    sj = json.load(open(STEPS_JSON, encoding="utf-8")) if os.path.exists(STEPS_JSON) else None
    sched = {n: scheduled_steps(n, sj) for n in ARM_STEPS} if sj else None
    oc = one_char_qids(a.bank) if os.path.exists(a.bank) else None
    found = _discover(a.results, a.key)
    if a.summary:
        arms = {}
        for n, (k, path) in sorted(found.items()):
            recs, arr = _arm_inputs(n, k, path, a.stack)
            if recs:
                arms[n] = (recs, events_of(recs, arr, None, sched[n] if sched else None))
        with open(os.path.join(a.results, "summary.md"), "w", encoding="utf-8") as f:
            f.write(summary_md(arms, schedules=sched, one_char=oc))
        print("wrote summary.md (%s)" % ", ".join(sorted(arms)))
        return
    if not a.arm or a.arm not in found:
        ap.error("an arm that has a meter_<arm>.<key>.jsonl in %s, or --summary" % a.results)
    k, path = found[a.arm]
    recs, arr = _arm_inputs(a.arm, k, path, a.stack)
    md = render_md(a.arm, recs, arr, errors=load_errors(path), schedule=sched[a.arm] if sched else None, one_char=oc)
    with open(path[:-len(".jsonl")] + ".md", "w", encoding="utf-8") as f:
        f.write(md)
    print("wrote %s.md (%d records)" % (os.path.basename(path)[:-len(".jsonl")], len(recs)))


if __name__ == "__main__":
    main()

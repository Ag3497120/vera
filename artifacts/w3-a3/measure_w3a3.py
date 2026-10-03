"""Measure the coarse placement (W3-a3: a copy of artifacts/w3-a/measure_w3a.py that points at
THIS tree and writes only under artifacts/w3-a3/).  Calls the public API only.

  measure_w3a3.py l1|l2|l3|l5|pred --placement DIR [--runs eval|dev]
  measure_w3a3.py verbs --placement DIR --data <verbs jsonl> [--runs eval|dev] [--exclude-overlap <jsonl>]

``--runs eval`` (default) uses the frozen W3-a test data and writes ``artifacts/w3-a3/eval_runs/<NNN>/``;
``--runs dev`` uses the dev data and writes ``artifacts/w3-a3/dev_runs/<NNN>/``.  For ``verbs`` the data
file is given by ``--data`` and ``--runs`` only chooses the output directory.  Nothing is overwritten:
every run gets a new numbered directory with a summary.json and an items.jsonl.

Scoring is the pre-registered one (PREREG.md):
  correct      top non-empty, top & gold non-empty, len(top) <= max(1, len(gold))
  wrong_single len(top) == 1 and top[0] not in gold
  other        everything else
"""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402
from verantyx.coarse_place import query  # noqa: E402

A0 = os.path.join(W, "artifacts/w3-a")      # read only: the frozen W3-a holdout sentences
A = os.path.join(W, "artifacts/w3-a3")      # everything this script writes
D = os.path.join(W, "tests/coarse_place/data")
PY = os.path.join(A, "py.sh")
ROLES = set(ct.ROLE_PARTICLES)


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def cls(r, gold):
    top, gs = r["top"], set(gold)
    if top and set(top) & gs and len(top) <= max(1, len(gs)):
        return "correct"
    if len(top) == 1:
        return "wrong_single"
    return "other"


def next_dir(root):
    os.makedirs(root, exist_ok=True)
    n = len([d for d in os.listdir(root) if d.isdigit()]) + 1
    while True:                      # parallel runs must not collide, nor overwrite
        p = os.path.join(root, "%03d" % n)
        try:
            os.makedirs(p)
            return p
        except FileExistsError:
            n += 1


def decisive(r):
    if r.get("decided_by"):
        return "+".join(r["decided_by"])
    if r["origin"] == "estimated":
        return "est:" + "+".join(sorted(r["axes"]))
    return "-"


def arm_family(label):
    """Collapse per-source arm names for the breakdown (seed, definition, ...)."""
    out = []
    for part in label.split("+"):
        out.append(part.split("@")[0])
    return "+".join(sorted(set(out)))


def header(args, pl, extra=None):
    m = json.load(open(os.path.join(pl, "manifest.json"), encoding="utf-8"))
    h = {"command": sys.argv[1:], "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "placement": pl, "content_sha256": m["content_sha256"],
         "config_sha256": m.get("config_sha256"), "builder_sha256": m.get("builder_sha256"),
         "coarse_types_sha256": sha(os.path.join(W, "verantyx/coarse_types.py")),
         "data": args.data, "runs": args.runs}
    if extra:
        h.update(extra)
    return h


def outdir(args):
    return next_dir(os.path.join(A, "eval_runs" if args.runs == "eval" else "dev_runs"))


def write(outd, summary, items):
    json.dump(summary, open(os.path.join(outd, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(outd, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(outd)


def vocab_path(args):
    return os.path.join(D, "typed_vocab.jsonl" if args.data == "frozen" else "dev_vocab.jsonl")


def unknown_path(args):
    return os.path.join(D, "unknown_words.jsonl" if args.data == "frozen" else "dev_unknown.jsonl")


def cmd_l2(args):
    seeds = {w for v in ct.SEEDS_NOUN.values() for w in v}
    rows = [g for g in load(vocab_path(args)) if g["term"] not in seeds]
    items = []
    for g in rows:
        r = query(g["term"], placement=args.placement)
        k = cls(r, g["gold"])
        items.append({"id": g["id"], "term": g["term"], "gold": g["gold"], "category": g["category"],
                      "trap": g["suffix_trap"], "trap_suggests": g.get("trap_suggests"),
                      "state": r["state"], "origin": r["origin"], "top": r["top"],
                      "estimate_basis": r.get("estimate_basis"),
                      "decided_by": decisive(r), "cls": k,
                      "neighbors": [n["via"] for n in r["neighbors"]][:3]})
    n = len(items)
    d = [i for i in items if i["origin"] == "direct"]
    c = sum(i["cls"] == "correct" for i in d)
    w = sum(i["cls"] == "wrong_single" for i in d)
    tr = [i for i in items if i["trap"]]
    twr = sum(i["cls"] == "wrong_single" and i["origin"] == "direct" for i in tr)
    est = Counter((i["origin"], i["cls"]) for i in items if i["origin"] != "direct")
    est = {"%s/%s" % k: v for k, v in est.items()}
    est_basis = Counter((i["estimate_basis"], i["cls"]) for i in items if i["origin"] == "estimated")
    est_basis = {"%s/%s" % k: v for k, v in sorted(est_basis.items(), key=lambda kv: str(kv[0]))}
    by_state = Counter(i["state"] for i in items)
    sm = {"n": n, "trap_n": len(tr), "direct_n": len(d),
          "correct_direct": c, "correct_rate": round(c / n, 4),
          "wrong_single_direct": w, "wrong_single_rate": round(w / n, 4),
          "trap_wrong_single_direct": twr,
          "trap_wrong_single_rate": round(twr / max(1, len(tr)), 4),
          "non_direct": est, "non_direct_by_basis": est_basis, "by_state": dict(by_state),
          "len_top_distribution": dict(Counter(len(i["top"]) for i in items)),
          "pass": {"correct>=0.85": c / n >= 0.85, "wrong<=0.08": w / n <= 0.08,
                   "trap_wrong<=0.05": twr / max(1, len(tr)) <= 0.05,
                   "n>=800": n >= 800 or args.data != "frozen",
                   "trap_n>=100": len(tr) >= 100 or args.data != "frozen"}}
    # breakdowns
    def tab(keyf, subset=items):
        t = defaultdict(Counter)
        for i in subset:
            t[keyf(i)][i["cls"] + ("" if i["origin"] == "direct" else "(non-direct)")] += 1
        return {str(k): dict(v) for k, v in sorted(t.items(), key=lambda kv: str(kv[0]))}
    sm["by_gold_type"] = tab(lambda i: ",".join(i["gold"]))
    sm["by_category"] = tab(lambda i: i["category"])
    sm["by_decisive_arm"] = tab(lambda i: arm_family(i["decided_by"]))
    sm["by_trap_unit_suggest"] = tab(lambda i: i["trap_suggests"], tr)
    sm["errors"] = [i for i in items if i["cls"] != "correct" or i["origin"] != "direct"]
    sm.update(header(args, args.placement))
    outd = outdir(args)
    write(outd, sm, items)
    print(json.dumps({k: sm[k] for k in ("n", "correct_rate", "wrong_single_rate",
                                         "trap_wrong_single_rate", "non_direct", "pass")},
                     ensure_ascii=False))


def cmd_l3(args):
    rows = load(unknown_path(args))
    items = []
    for u in rows:
        r = query(u["term"], context_role=u["context_role"],
                  context_predicate=u["context_predicate"], placement=args.placement)
        top, gs = r["top"], set(u["gold"])
        if u["gold_unknown"]:
            k = "returned_type" if top else "abstained"
        elif top and (set(top) & gs) and len(top) <= max(1, len(gs)):
            k = "correct"
        elif not top:
            k = "unknown"
        else:
            k = "wrong"
        leak = r["origin"] == "direct" and set(r["axes"]) != {"notation"}
        items.append({"id": u["id"], "term": u["term"], "kind": u["kind"], "gold": u["gold"],
                      "state": r["state"], "origin": r["origin"], "top": top, "cls": k,
                      "estimate_basis": r.get("estimate_basis"),
                      "decided_by": decisive(r), "leak_direct": leak,
                      "unmarked": r["origin"] == "estimated" and not r["constructed"],
                      "neighbors": [n["via"] for n in r["neighbors"]][:4]})
    typed = [i for i in items if i["cls"] not in ("returned_type", "abstained")]
    unk = [i for i in items if i["cls"] in ("returned_type", "abstained")]
    c = sum(i["cls"] == "correct" for i in typed)
    wr = sum(i["cls"] == "wrong" for i in typed)
    ret = sum(i["cls"] == "returned_type" for i in unk)
    leaks = [i["term"] for i in items if i["leak_direct"]]
    unm = [i["term"] for i in items if i["unmarked"]]
    sm = {"typed_n": len(typed), "unknown_n": len(unk), "correct": c,
          "correct_rate": round(c / max(1, len(typed)), 4), "wrong": wr,
          "wrong_rate": round(wr / max(1, len(typed)), 4),
          "unknown_among_typed": sum(i["cls"] == "unknown" for i in typed),
          "returned_type_among_unknown": ret,
          "returned_type_rate": round(ret / max(1, len(unk)), 4),
          "leaks_direct_not_notation": leaks, "unmarked_estimates": unm,
          "pass": {"correct>=0.65": c / max(1, len(typed)) >= 0.65,
                   "wrong<=0.15": wr / max(1, len(typed)) <= 0.15,
                   "returned_type<=0.20": ret / max(1, len(unk)) <= 0.20,
                   "no_leaks": not leaks, "no_unmarked": not unm}}
    t = defaultdict(Counter)
    for i in typed:
        t[i["kind"]][i["cls"]] += 1
    sm["by_kind"] = {k: dict(v) for k, v in t.items()}
    t = defaultdict(Counter)
    for i in typed:
        t[",".join(i["gold"])][i["cls"]] += 1
    sm["by_gold_type"] = {k: dict(v) for k, v in sorted(t.items())}
    t = defaultdict(Counter)
    for i in typed:
        t[arm_family(i["decided_by"])][i["cls"]] += 1
    sm["by_decisive_stage"] = {k: dict(v) for k, v in sorted(t.items())}
    sm["errors"] = [i for i in items if i["cls"] in ("wrong", "returned_type", "unknown")]
    sm.update(header(args, args.placement))
    outd = outdir(args)
    write(outd, sm, items)
    print(json.dumps({k: sm[k] for k in ("typed_n", "unknown_n", "correct_rate", "wrong_rate",
                                         "unknown_among_typed", "returned_type_rate", "leaks_direct_not_notation", "pass")},
                     ensure_ascii=False))


def content_tokens(tagger, sentence):
    """The L1 content-word definition (PREREG.md)."""
    toks = list(tagger(sentence))
    for i, w in enumerate(toks):
        f = w.feature
        prev = toks[i - 1] if i else None
        if f.pos1 == "名詞":
            ok = f.pos2 in ("普通名詞", "固有名詞", "数詞")
        elif f.pos1 in ("動詞", "形容詞"):
            ok = not (prev is not None and prev.feature.pos1 == "助詞"
                      and prev.feature.pos2 == "接続助詞" and prev.surface in ("て", "で"))
            if ok and f.pos1 == "動詞" and f.orthBase == "する" and prev is not None \
                    and prev.feature.pos1 == "名詞":
                ok = False
        elif f.pos1 == "形状詞":
            ok = f.pos2 == "一般"
        else:
            ok = False
        if not ok:
            continue
        term = f.orthBase or w.surface
        role = pred = None
        if f.pos1 == "名詞":
            nx = toks[i + 1] if i + 1 < len(toks) else None
            if nx is not None and nx.feature.pos1 == "助詞" and nx.surface in ROLES:
                role = nx.surface
            for v in toks[i + 1:]:
                if v.feature.pos1 == "動詞":
                    pred = v.feature.orthBase or v.surface
                    break
        yield term, role, pred, f.pos1


def cmd_l1(args):
    import fugashi
    tagger = fugashi.Tagger()
    hp = os.path.join(A0, "holdout_2000.jsonl" if args.data == "frozen" else "dev_l1_1000.jsonl")
    H = load(hp)
    m = json.load(open(os.path.join(args.placement, "manifest.json"), encoding="utf-8"))
    tot = hit = 0
    types_all, types_hit = set(), set()
    by_pos = defaultdict(Counter)
    by_origin = Counter()
    by_basis = Counter()
    by_basis_hit = Counter()
    by_state = Counter()
    by_src = defaultdict(Counter)
    miss = Counter()
    items = []
    memo = {}
    for h in H:
        for term, role, pred, p1 in content_tokens(tagger, h["sentence"]):
            key = (term, role, pred)
            if key not in memo:
                r = query(term, context_role=role, context_predicate=pred, placement=args.placement)
                memo[key] = (r["state"], r["origin"], bool(r["top"]), r["top"],
                             r.get("estimate_basis"))
            st, og, ok, top, basis = memo[key]
            tot += 1
            types_all.add(term)
            by_pos[p1]["tokens"] += 1
            by_src[h["source"] if h["source"] == "jawiki" else "codex:" + h["family"]]["tokens"] += 1
            if ok:
                hit += 1
                types_hit.add(term)
                by_pos[p1]["hit"] += 1
                by_src[h["source"] if h["source"] == "jawiki" else "codex:" + h["family"]]["hit"] += 1
            else:
                miss[(term, p1)] += 1
            by_origin[og or "none"] += 1
            by_basis[basis or (og or "none")] += 1
            if ok:
                by_basis_hit[basis or (og or "none")] += 1
            by_state[st] += 1
    # placed headwords
    out = m["outputs"]
    sm = {"sentences": len(H), "tokens": tot, "token_cover": hit, "token_cover_rate": round(hit / tot, 4),
          "distinct": len(types_all), "distinct_cover": len(types_hit),
          "distinct_cover_rate": round(len(types_hit) / len(types_all), 4),
          "by_pos": {k: dict(v) for k, v in by_pos.items()},
          "by_pos_rate": {k: round(v["hit"] / v["tokens"], 4) for k, v in by_pos.items()},
          "by_source": {k: dict(v) for k, v in by_src.items()},
          "tokens_by_origin": dict(by_origin), "tokens_by_state": dict(by_state),
          "tokens_by_basis": dict(by_basis), "tokens_typed_by_basis": dict(by_basis_hit),
          "placed_direct_headwords": out["placed_direct"],
          "placed_by_state": out["by_state"], "placed_by_ns": out["by_ns_placed"],
          "placed_by_kind": out["by_kind_placed"], "placed_by_arm": out["by_arm_placed"],
          "headwords_all_rows": out["headwords"],
          "top_misses": [{"term": t, "pos": p, "n": n} for (t, p), n in miss.most_common(60)],
          "pass": {"token_cover>=0.90": hit / tot >= 0.90,
                   "placed>=100000": out["placed_direct"] >= 100000}}
    sm.update(header(args, args.placement, {"holdout_sha256": sha(hp)}))
    outd = outdir(args)
    items = [{"term": t, "pos": p, "misses": n} for (t, p), n in miss.most_common()]
    write(outd, sm, items)
    print(json.dumps({k: sm[k] for k in ("sentences", "tokens", "token_cover_rate", "distinct", "distinct_cover_rate",
                                         "by_pos_rate", "placed_direct_headwords", "pass")}, ensure_ascii=False))


def cmd_l5(args):
    terms = [r["term"] for r in load(os.path.join(D, "typed_vocab.jsonl"))]
    terms += [r["term"] for r in load(os.path.join(D, "unknown_words.jsonl"))]
    # plus the L1 tokens
    import fugashi
    tagger = fugashi.Tagger()
    qs = [(t, None, None) for t in terms]
    for h in load(os.path.join(A0, "holdout_2000.jsonl")):
        for term, role, pred, _p in content_tokens(tagger, h["sentence"]):
            qs.append((term, role, pred))
    query("土手", placement=args.placement)  # load
    ts = []
    for t, role, pred in qs:
        a = time.perf_counter()
        query(t, context_role=role, context_predicate=pred, placement=args.placement)
        ts.append((time.perf_counter() - a) * 1000)
    srt = sorted(ts)
    p95 = srt[int(len(srt) * 0.95) - 1]
    # one command-line invocation (load included)
    t0 = time.perf_counter()
    subprocess.run([PY, "-m", "verantyx.coarse_place", "--term", "土手", "--placement", args.placement],
                   stdout=subprocess.DEVNULL, check=False)
    cli_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    subprocess.run([PY, "-c", "import verantyx.coarse_place as c; import sys; sys.exit(0)"],
                   stdout=subprocess.DEVNULL, check=False)
    imp_ms = (time.perf_counter() - t0) * 1000
    dbp = os.path.join(args.placement, "placement.sqlite")
    sm = {"n_queries": len(ts), "mean_ms": round(statistics.mean(ts), 3), "p95_ms": round(p95, 3),
          "max_ms": round(srt[-1], 3), "median_ms": round(statistics.median(ts), 3),
          "cli_one_call_ms_including_load": round(cli_ms, 1), "python_import_only_ms": round(imp_ms, 1),
          "placement_bytes": os.path.getsize(dbp),
          "pass": {"mean<=50": statistics.mean(ts) <= 50, "p95<=50": p95 <= 50}}
    sm.update(header(args, args.placement))
    outd = outdir(args)
    write(outd, sm, [{"term": t, "ms": round(x, 3)} for (t, _r, _p), x in zip(qs, ts) if x > 5])
    print(json.dumps(sm, ensure_ascii=False))


def cmd_pred(args):
    rows = load(os.path.join(D, "predicate_check.jsonl"))
    items = []
    seeds_now = {w for v in ct.SEEDS_PRED.values() for w in v}     # the seeds of THIS tree (review r1 M4)
    for g in rows:
        r = query(g["term"], placement=args.placement)
        k = cls(r, g["gold"])
        items.append({"id": g["id"], "term": g["term"], "gold": g["gold"], "seed_overlap": g["seed_overlap"],
                      "seed_now": g["term"] in seeds_now,
                      "state": r["state"], "origin": r["origin"], "top": r["top"],
                      "decided_by": decisive(r), "cls": k})
    def rate(sub):
        n = len(sub)
        return {"n": n, "correct": sum(i["cls"] == "correct" for i in sub),
                "wrong_single": sum(i["cls"] == "wrong_single" for i in sub),
                "returned_any": sum(bool(i["top"]) for i in sub)}
    sm = {"all": rate(items), "non_seed": rate([i for i in items if not i["seed_overlap"]]),
          # the official report: only words that are NOT a seed of the tree being measured
          "non_seed_now": rate([i for i in items if not i["seed_now"]]),
          "seed_now": rate([i for i in items if i["seed_now"]]),
          "by_gold_type": {t: rate([i for i in items if i["gold"] == [t]])
                           for t in sorted({g for i in items for g in i["gold"]})},
          "by_decisive_arm": {a: rate([i for i in items if arm_family(i["decided_by"]) == a])
                              for a in sorted({arm_family(i["decided_by"]) for i in items})},
          "note": "report only (not an acceptance criterion)"}
    sm.update(header(args, args.placement))
    outd = outdir(args)
    write(outd, sm, items)
    print(json.dumps({k: sm[k] for k in ("all", "non_seed", "non_seed_now", "seed_now")}, ensure_ascii=False))


def _frame_report(items):
    """Report only: for words whose gold holds a type K62 reads and whose answer carries a CONFIRMED frame,
    does the answered frame stay inside the hand-written expected frame?"""
    rows = []
    for i in items:
        if i["frame_status"] != "CONFIRMED" or not i.get("frame"):
            continue
        exp = i.get("expected_frame")
        if not exp:
            rows.append({"term": i["term"], "frame": i["frame"], "expected_frame": None, "inside": None})
            continue
        inside = all(p in exp and set(ts) <= set(exp[p]) for p, ts in i["frame"].items())
        rows.append({"term": i["term"], "frame": i["frame"], "expected_frame": exp, "inside": inside})
    return rows


def _verbs_summary(items):
    typed = [i for i in items if i["kind"] == "typed"]
    unk = [i for i in items if i["kind"] != "typed"]
    n = len(typed)
    direct = [i for i in typed if i["origin"] == "direct"]
    cd = sum(i["cls"] == "correct" for i in direct)
    wd = sum(i["cls"] == "wrong_single" for i in direct)
    ret = sum(bool(i["top"]) for i in unk)
    est = Counter((i["origin"], i["cls"]) for i in typed if i["origin"] != "direct")
    sm = {"n_typed": n, "n_unknown": len(unk), "correct_direct": cd, "wrong_single_direct": wd,
          "wrong_rate_typed": round(wd / max(1, n), 4),
          "direct_answers": len(direct),
          "wrong_rate_among_direct": round(wd / max(1, len(direct)), 4),
          "returned_type_among_unknown": ret,
          "returned_rate_unknown": round(ret / max(1, len(unk)), 4),
          "non_direct_typed": {"%s/%s" % k: v for k, v in est.items()},
          "correct_all": sum(i["cls"] == "correct" for i in typed),
          "wrong_single_all": sum(i["cls"] == "wrong_single" for i in typed),
          "by_state": dict(Counter(i["state"] for i in items)),
          "pass_Q3": {"wrong_direct<=5%": wd <= 0.05 * max(1, n),
                      "returned_unknown<=20%": ret <= 0.20 * max(1, len(unk))}}
    def tab(keyf, subset):
        t = defaultdict(Counter)
        for i in subset:
            t[keyf(i)][i["cls"] + ("" if i["origin"] == "direct" else "(non-direct)")] += 1
        return {str(k): dict(v) for k, v in sorted(t.items(), key=lambda kv: str(kv[0]))}
    sm["by_kind"] = {k: dict(Counter(("returned" if i["top"] else "abstained") if k != "typed" else i["cls"]
                                      for i in items if i["kind"] == k))
                     for k in sorted({i["kind"] for i in items})}
    sm["by_gold_type"] = tab(lambda i: ",".join(i["gold"]), typed)
    sm["by_decisive_arm"] = tab(lambda i: arm_family(i["decided_by"]), typed)
    sm["by_decisive_arm_unknown"] = dict(Counter(arm_family(i["decided_by"]) for i in unk if i["top"]))
    sm["by_frame_status"] = dict(Counter(i["frame_status"] for i in items))
    sm["direct_wrong_words"] = [{"term": i["term"], "gold": i["gold"], "top": i["top"],
                                 "decided_by": i["decided_by"]}
                                for i in direct if i["cls"] == "wrong_single"]
    sm["unknown_returned_words"] = [{"term": i["term"], "kind": i["kind"], "top": i["top"],
                                     "origin": i["origin"], "estimate_basis": i["estimate_basis"],
                                     "decided_by": i["decided_by"]} for i in unk if i["top"]]
    sm["frame_report_only"] = _frame_report(items)
    return sm


def cmd_verbs(args):
    rows = load(args.data)
    overlap = set()
    if args.exclude_overlap:
        overlap = {r["term"] for r in load(args.exclude_overlap)}
    items = []
    for g in rows:
        r = query(g["term"], placement=args.placement)
        k = cls(r, g["gold"]) if g["kind"] == "typed" else ("returned_type" if r["top"] else "abstained")
        items.append({"id": g["id"], "term": g["term"], "kind": g["kind"], "gold": g["gold"],
                      "expected_frame": g.get("frame"),
                      "state": r["state"], "origin": r["origin"], "top": r["top"],
                      "estimate_basis": r.get("estimate_basis"), "decided_by": decisive(r), "cls": k,
                      "frame_status": r.get("frame_status"), "frame": r.get("frame"),
                      "generated_frame": r.get("generated_frame"),
                      "neighbors": [n["via"] for n in r["neighbors"]][:3]})
    sm = _verbs_summary(items)
    if overlap:
        sm["excluding_overlap"] = _verbs_summary([i for i in items if i["term"] not in overlap])
        sm["excluding_overlap"]["excluded_terms"] = sum(1 for i in items if i["term"] in overlap)
    sm.update(header(args, args.placement, {"data_sha256": sha(args.data), "data_path": args.data}))
    outd = outdir(args)
    write(outd, sm, items)
    last = {k: sm[k] for k in ("n_typed", "n_unknown", "correct_direct", "wrong_single_direct", "wrong_rate_typed",
                               "direct_answers", "wrong_rate_among_direct", "returned_type_among_unknown",
                               "returned_rate_unknown", "by_kind", "by_decisive_arm", "pass_Q3")}
    print(json.dumps(last, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["l1", "l2", "l3", "l5", "pred", "verbs"])
    ap.add_argument("--placement", required=True)
    ap.add_argument("--runs", choices=["eval", "dev"], default="eval")
    ap.add_argument("--data", default=None, help="verbs: the test data file")
    ap.add_argument("--exclude-overlap", default=None, help="verbs: also count without the terms of this jsonl")
    args = ap.parse_args()
    if args.cmd == "verbs":
        if not args.data:
            ap.error("verbs needs --data")
    else:
        args.data = "frozen" if args.runs == "eval" else "dev"
    {"l1": cmd_l1, "l2": cmd_l2, "l3": cmd_l3, "l5": cmd_l5, "pred": cmd_pred, "verbs": cmd_verbs}[args.cmd](args)


if __name__ == "__main__":
    main()

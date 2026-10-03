"""Render every number in docs/COARSE_PLACEMENT.md from artifacts/w3-a/.

    render_docs_numbers.py           rewrite the tables between the markers
    render_docs_numbers.py --check   exit 0 only if the files already match

Tables sit between ``<!-- BEGIN table:NAME -->`` and ``<!-- END table:NAME -->``.
The "final" measurement of each command is the LAST directory under
``artifacts/w3-a/eval_runs``; every earlier run is listed in the history
table.  The list of wrong words is written to ``artifacts/w3-a/errors_final.md``.
"""
import glob
import json
import os
import re
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
A = os.path.join(W, "artifacts/w3-a")
DOC = os.path.join(W, "docs/COARSE_PLACEMENT.md")
ERR = os.path.join(A, "errors_final.md")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def runs(root):
    out = []
    for d in sorted(glob.glob(os.path.join(A, root, "[0-9][0-9][0-9]"))):
        sp = os.path.join(d, "summary.json")
        if os.path.exists(sp):
            s = load(sp)
            s["_seq"] = os.path.basename(d)
            s["_cmd"] = s["command"][0]
            out.append(s)
    return out


def last(rs, cmd):
    c = [r for r in rs if r["_cmd"] == cmd]
    return c[-1] if c else None


def md(headers, rows):
    if not rows:
        return "(none)\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def pct(x):
    return "%.1f%%" % (100.0 * x)


def ok(b):
    return "PASS" if b else "FAIL"


def short(h):
    return (h or "")[:12]


def counter_rows(d):
    return sorted(((k, ", ".join("%s=%s" % (a, b) for a, b in sorted(v.items())))
                   for k, v in d.items()), key=lambda r: r[0])


def errata_reference(l2):
    """Reference rescoring of the LAST L2 run with the proposed gold errata
    (the frozen scoring stays the official one; the choice is the reviewer's)."""
    ep = os.path.join(A, "gold_errata_proposed.jsonl")
    if not l2 or not os.path.exists(ep):
        return None
    er = {}
    for line in open(ep, encoding="utf-8"):
        r = json.loads(line)
        if r.get("adopted") is False:        # the reviewer did not adopt it
            continue
        er[r["id"]] = r["proposed_gold"]
    items = [json.loads(l) for l in open(os.path.join(A, "eval_runs", l2["_seq"], "items.jsonl"), encoding="utf-8")]
    n = c = w = tn = tw = 0
    for i in items:
        gold = i["gold"]
        if i["id"] in er:
            if er[i["id"]] is None:
                continue
            gold = er[i["id"]]
        top, gs = i["top"], set(gold)
        n += 1
        k = "correct" if (top and gs & set(top) and len(top) <= max(1, len(gs))) else (
            "wrong_single" if len(top) == 1 else "other")
        d = i["origin"] == "direct"
        c += (k == "correct" and d)
        w += (k == "wrong_single" and d)
        if i["trap"]:
            tn += 1
            tw += (k == "wrong_single" and d)
    return {"n": n, "correct": c / n, "wrong": w / n, "trap_n": tn, "trap_wrong": tw / max(1, tn),
            "changed": sorted(er)}


def _hub_rows():
    """hub_spread_full_*.txt (written by hub_spread.py) -> table rows."""
    import ast
    out = []
    wrong = {"小説家": "GROUP_ORG", "僧": "GROUP_ORG", "大名": "TIME"}
    for label, fn in (("r2b (W3-a, before the fix)", "hub_spread_full_r2b.txt"),
                      ("r3c (F1-F6 only)", "hub_spread_full_r3c.txt"),
                      ("r4 (round 1)", "hub_spread_full_r4.txt"),
                      ("r5 (final)", "hub_spread_full_r5.txt")):
        p = os.path.join(A, fn)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8").read().splitlines()[1:]:
            hub, n, rest = line.split(" ", 2)
            items = ast.literal_eval(rest)
            tot = int(n)
            cnt = {k: v for k, v in items}
            top5 = ", ".join("%s/%s=%d" % (k[0], k[1] or "-", v) for k, v in items)
            w = ""
            if hub in wrong:
                m = cnt.get(("DECIDED", wrong[hub]), 0)
                w = "%d (%s)" % (m, wrong[hub])
            out.append([label, hub, tot, w, top5])
    return out


def _j(name):
    p = os.path.join(A, name)
    return load(p) if os.path.exists(p) else None


def w3a2_tables(T, ev):
    """The tables added in W3-a2 (each only when its data file exists)."""
    rows = _hub_rows()
    if rows:
        T["hub_spread"] = md(["placement", "hub (a lead ending in 'の<hub>。')", "articles",
                              "wrongly typed and DECIDED (the type it was wrongly given)",
                              "state/top of the article's title (top 5)"], rows)
    # donor stats: r3 and r4 manifests
    rows = []
    top_rows = []
    B = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/"
    for label, rel in (("r3c", "full/r3c/run1"), ("r4", "full/r4/run1"), ("r5", "full/r5/run1")):
        mp = os.path.join(B, rel, "manifest.json")
        if not os.path.exists(mp):
            continue
        m = load(mp)
        d = m.get("donor_stats")
        if not d:
            continue
        rows.append([label, d["stage_a"]["donors"], d["stage_a"]["non_seed_donors"],
                     d["stage_b"]["donors"], d["stage_b"]["non_seed_donors"],
                     d["excluded"]["not_decided"], d["excluded"]["contra_arm"], d.get("donor_contra_min"),
                     ", ".join("%s=%s" % kv for kv in sorted(m["stage_seconds"].items()) if kv[0].startswith("stage_"))])
        if label == "r5":
            for h in d["top_donors"][:15]:
                top_rows.append([h["donor"], h["type"], h["dependents"],
                                 h["dependents_with_other_met_arm_elsewhere"]])
    if rows:
        T["donor_stats"] = md(["placement", "stage A donors (with seeds)", "stage A non-seed", "stage B donors",
                               "stage B non-seed", "dropped: not DECIDED", "dropped: contrary arm",
                               "donor_contra_min", "stage seconds"], rows)
    if top_rows:
        T["donor_top"] = md(["donor (final placement r5)", "type", "heads typed through it",
                             "of those, heads with another met arm pointing elsewhere"], top_rows)
    nm = _j("needs_evidence.meta.json")
    if nm:
        T["needs_summary"] = md(["item", "value"], [
            ["placement the list was taken from", "%s (content_sha256 %s...)" % (nm["placement"], short(nm["content_sha256"]))],
            ["words listed (all words whose frequency is at least the boundary's)", "{:,}".format(nm["total"])],
            ["requested n", "{:,}".format(nm["n_requested"])],
            ["boundary frequency (n_seen of the n-th word)", nm["boundary_freq"]],
            ["words at exactly the boundary frequency (all kept)", nm["n_at_boundary"]],
            ["last frequency in the list", nm["last_freq"]],
            ["by state", ", ".join("%s=%s" % kv for kv in sorted(nm["by_state"].items()))],
            ["by namespace", ", ".join("%s=%s" % kv for kv in sorted(nm["by_ns"].items()))],
            ["by evidence status", ", ".join("%s=%s" % kv for kv in sorted(nm["by_evidence_status"].items()))],
            ["by origin of the headword", ", ".join("%s=%s" % kv for kv in sorted(nm["by_kind"].items()))],
            ["file sha256", nm["out_sha256"]]])
    no = _j("needs_evidence_overlap.json")
    if no:
        T["needs_overlap"] = md(["test file (counted AFTER the list was made)", "terms in the file", "words also in the list"],
                                [[k, no["test_terms"][k], v] for k, v in sorted(no["overlap"].items())])
    gs = _j("gen_summary.json")
    if gs:
        T["gen_summary"] = md(["item", "value"], [[k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v]
                                                for k, v in sorted(gs.items())])
    p5 = _j("p5_compare.json")
    if p5:
        names = list(p5["placements"])
        rows = []
        for r in p5["rows"]:
            cells = []
            for n in names:
                c = r["by_placement"].get(n)
                if c is None:
                    cells.append("-")
                else:
                    cells.append("%d / %d = %s%s" % (c["count"], c["of"], pct(c["rate"]),
                                                     "" if "direction" not in c else " (%+d, %s)" % (
                                                         c["delta_count_vs_w3a"], c["direction"])))
            g = r["approval_guard"]
            guard = "-" if not g else ("PASS" if all(r["by_placement"][n].get("not_worse", True)
                                                      for n in names[1:] if r["by_placement"].get(n)) else "FAIL")
            rows.append([r["item"], "%s %s" % (r["target_kind"], pct(r["target"]))] + cells + [guard])
        T["p5_compare"] = md(["item", "target"] + names + ["not worse than W3-a (approval condition)"], rows)
    # estimates split by basis (the last l2 / l1)
    l2 = last(ev, "l2")
    if l2 and "non_direct_by_basis" in l2:
        T["l2_by_basis"] = md(["non-direct answers of the frozen typed vocabulary: estimate basis / outcome", "words"],
                              [[k, v] for k, v in sorted(l2["non_direct_by_basis"].items())]
                              + [["(none / other: no type returned or several types)", l2["non_direct"].get("None/other", 0)]])
    l1 = last(ev, "l1")
    if l1 and "tokens_by_basis" in l1:
        T["l1_by_basis"] = md(["how the token was answered (basis; direct = a testimony of the material)", "tokens", "of which a type was returned"],
                              [[k, v, l1["tokens_typed_by_basis"].get(k, 0)] for k, v in sorted(l1["tokens_by_basis"].items())])
    ub = _j("upper_bound_r5.json")
    if ub:
        T["upper_bound"] = md(["measure (report only)", "words of %d" % ub["n"], "rate"], [
            ["gold type appears somewhere in the evidence table, generated arm included", ub["gold_type_in_evidence_with_generated"], pct(ub["rate_with"])],
            ["same, generated arm not counted", ub["gold_type_in_evidence_without_generated"], pct(ub["rate_without"])]])
    # generated section of the manifest
    mp = os.path.join(B, "full/r5/run1/manifest.json")
    if os.path.exists(mp):
        m = load(mp)
        g = m.get("generated")
        if g:
            T["build_generated"] = md(["item", "value"], [[k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v]
                                                         for k, v in sorted(g.items())])
    # round 2 (review r1 M1 / M2)
    lg = _j("latin_units_grid.json")
    if lg:
        rows = [["no rule (round 1)", "-", len(lg["no_rule_units"]), ", ".join(lg["no_rule_units"]), "-", "-"]]
        for g in lg["grid"]:
            rows.append(["share >= %d%%, numerals >= %d" % (g["theta"], g["K"]), g["score"], len(g["units"]),
                         ", ".join(g["units"]), ", ".join(g["q_kept"]) or "-", ", ".join(g["n_kept"]) or "-"])
        T["latin_units_grid"] = md(["rule (per source; DECISIONS 6-1/6-2)", "score (Q kept - N kept)",
                                    "Latin units", "the units", "Q (real units) kept", "N (non-units) kept"], rows)
        rows = []
        for u, d in sorted(lg["per_source"].items()):
            rows.append([u, "; ".join("%s: %d after a numeral / %d as a noun / %d numerals"
                                      % (src, v["after_numeral"], v["noun_occurrences"], v["distinct_numerals"])
                                      for src, v in sorted(d.items())) or "(under counter_min everywhere)"])
        T["latin_units_per_source"] = md(["unit", "per source (counter_min=80 passed): after-numeral count / noun occurrences (no case) / distinct numerals (capped at 32)"], rows)
    mc = _j("m1_m2_check_r5.json")
    if mc:
        rows = [["unit_sample rows", "{:,}".format(mc["unit_sample_rows"])],
                ["... of which list a word decided with gen_definition (M1, must be 0)", mc["unit_sample_rows_listing_a_generated_word"]],
                ["words decided with gen_definition", "{:,}".format(mc["words_decided_with_gen_definition"])],
                ["... of which upgraded to direct", "{:,}".format(mc["of_which_upgraded_to_direct"])],
                ["compounds '<prefix><generated word>' whose estimate used the head stage on that word (M1, must be 0)", mc["head_stage_leaks_through_generated_word"]],
                ["control: plain direct words (a sample) whose compound used the head stage on that word", "%d of %d" % (mc["control_head_stage_used"], mc["control_plain_direct_words_queried"])],
                ["Latin-script units in the counters table (M2)", "%d: %s" % (len(mc["latin_units"]), ", ".join(mc["latin_units"]))],
                ["all counter units", mc["counter_units_total"]]]
        if "l3_differs_from_compare" in mc:
            rows.append(["unknown-word file (%d words): answers (top, origin) that differ from the F1-F6-only placement r3c" % mc["l3_words"],
                         mc["l3_differs_from_compare"]])
        T["m1_m2_check"] = md(["check on the final placement (m1_m2_check.py)", "value"], rows)
        T["m2_queries"] = md(["query", "state", "top", "rule", "expected"],
                             [[t, v["state"], ",".join(v["top"]) or "-", v["rule"] or "-",
                               v["expected"] or "(only reported)"] for t, v in mc["m2_queries"].items()])
    # the prompt (read from the generator itself)
    sys.path.insert(0, os.path.join(W, "tools"))
    import gen_coarse_evidence as gce
    T["gen_prompt"] = "```\n%s%s[\"<語>\", ...]\n```\n\ntemplate sha256 (the fixed part): `%s`\n" % (
        gce.PROMPT_HEAD, gce.WORDS_PREFIX, gce.prompt_template_sha256())
    T["gen_argv"] = "```\n%s\n```\n" % " ".join(
        ["<codex>", "exec", "-m", gce.MODEL, "-c", 'model_reasoning_effort="%s"' % gce.EFFORT,
         "-c", 'service_tier="%s"' % gce.TIER, "-s", "read-only", "--skip-git-repo-check", "--ephemeral",
         "--disable", "browser_use", "--disable", "computer_use", "--disable", "apps",
         "[-c <extra config> ...]", "-C", "<G>/work/empty", "--output-schema", "<G>/schema.json", "--json",
         "-o", "<G>/raw/<batch>.a<k>.last.json", "<prompt>"])
    return T


def tables():
    ev = runs("eval_runs")
    dev = runs("dev_runs")
    T = {}
    l1, l2, l3, l5, pr = (last(ev, c) for c in ("l1", "l2", "l3", "l5", "pred"))
    man = None
    pl = None
    for r in (l2, l1, l3):
        if r:
            pl = r["placement"]
            break
    if pl and os.path.exists(os.path.join(pl, "manifest.json")):
        man = load(os.path.join(pl, "manifest.json"))
    er = errata_reference(l2)
    if er:
        T["errata_ref"] = md(["scoring", "n", "correct", "wrong decision", "trap wrong decision"], [
            ["frozen key (official)", l2["n"], pct(l2["correct_rate"]), pct(l2["wrong_single_rate"]), pct(l2["trap_wrong_single_rate"])],
            ["with the proposed errata (reference only; the reviewer decides): %s" % ", ".join(er["changed"]),
             er["n"], pct(er["correct"]), pct(er["wrong"]), pct(er["trap_wrong"])]])
    # ---- results
    rows = []
    if l1:
        rows.append(["L1", "placed content words (direct, top non-empty)", ">= 100,000",
                     "{:,}".format(l1["placed_direct_headwords"]), ok(l1["pass"]["placed>=100000"])])
        rows.append(["L1", "token cover on the 2,000 held-out sentences (direct + estimated)", ">= 90%",
                     "%s (%d of %d tokens)" % (pct(l1["token_cover_rate"]), l1["token_cover"], l1["tokens"]),
                     ok(l1["pass"]["token_cover>=0.90"])])
        rows.append(["L1", "distinct-word cover (reference)", "-",
                     "%s (%d of %d)" % (pct(l1["distinct_cover_rate"]), l1["distinct_cover"], l1["distinct"]), "-"])
    if l2:
        rows.append(["L2", "direct and correct / all (n=%d)" % l2["n"], ">= 85%", pct(l2["correct_rate"]),
                     ok(l2["pass"]["correct>=0.85"])])
        rows.append(["L2", "direct and wrongly decided as ONE type / all", "<= 8%", pct(l2["wrong_single_rate"]),
                     ok(l2["pass"]["wrong<=0.08"])])
        rows.append(["L2", "suffix-trap words (n=%d): wrongly decided / all" % l2["trap_n"], "<= 5%",
                     pct(l2["trap_wrong_single_rate"]), ok(l2["pass"]["trap_wrong<=0.05"])])
    if l3:
        rows.append(["L3", "typed unknown words (n=%d): correct" % l3["typed_n"], ">= 65%",
                     pct(l3["correct_rate"]), ok(l3["pass"]["correct>=0.65"])])
        rows.append(["L3", "typed unknown words: wrong", "<= 15%", pct(l3["wrong_rate"]),
                     ok(l3["pass"]["wrong<=0.15"])])
        rows.append(["L3", "gold-unknown words (n=%d): a type was returned" % l3["unknown_n"], "<= 20%",
                     pct(l3["returned_type_rate"]), ok(l3["pass"]["returned_type<=0.20"])])
        rows.append(["L3", "unknown words returned DIRECT other than by spelling rule", "0",
                     str(len(l3["leaks_direct_not_notation"])), ok(l3["pass"]["no_leaks"])])
        rows.append(["L4", "estimates without the construction mark", "0",
                     str(len(l3["unmarked_estimates"])), ok(l3["pass"]["no_unmarked"])])
    if l5:
        rows.append(["L5", "query time, mean / p95 / max (ms), %d queries" % l5["n_queries"], "mean, p95 <= 50",
                     "%s / %s / %s" % (l5["mean_ms"], l5["p95_ms"], l5["max_ms"]),
                     ok(l5["pass"]["mean<=50"] and l5["pass"]["p95<=50"])])
        rows.append(["L5", "one command-line call incl. load (ms) / import only (ms)", "-",
                     "%s / %s" % (l5["cli_one_call_ms_including_load"], l5["python_import_only_ms"]), "-"])
        rows.append(["L5", "placement size (bytes)", "-", "{:,}".format(l5["placement_bytes"]), "-"])
    if man:
        rows.append(["L5", "build duration (s), full material", "-", str(man["duration_sec"]), "-"])
        rows.append(["L5", "content_sha256 of this placement", "-", short(man["content_sha256"]) + "...", "-"])
    T["results"] = md(["Criterion", "Measure", "Target", "Measured", "Result"], rows)
    # ---- eval history
    rows = []
    for r in ev:
        key = ""
        if r["_cmd"] == "l2":
            key = "correct %s, wrong %s, trap wrong %s" % (pct(r["correct_rate"]), pct(r["wrong_single_rate"]),
                                                          pct(r["trap_wrong_single_rate"]))
        elif r["_cmd"] == "l3":
            key = "correct %s, wrong %s, returned-type %s" % (pct(r["correct_rate"]), pct(r["wrong_rate"]),
                                                              pct(r["returned_type_rate"]))
        elif r["_cmd"] == "l1":
            key = "token cover %s, placed %s" % (pct(r["token_cover_rate"]), "{:,}".format(r["placed_direct_headwords"]))
        elif r["_cmd"] == "l5":
            key = "mean %s ms, p95 %s ms" % (r["mean_ms"], r["p95_ms"])
        elif r["_cmd"] == "pred":
            ns_ = r.get("non_seed_now") or r["non_seed"]
            key = "non-seed correct %d of %d" % (ns_["correct"], ns_["n"])
        rows.append([r["_seq"], r["_cmd"], r["time_utc"], short(r["content_sha256"]), short(r.get("config_sha256")), key])
    T["eval_history"] = md(["run", "command", "time (UTC)", "placement sha", "config sha", "result"], rows)
    # ---- dev history
    rows = []
    for r in dev:
        key = ""
        if r["_cmd"] == "l2":
            key = "correct %s, wrong %s, trap wrong %s" % (pct(r["correct_rate"]), pct(r["wrong_single_rate"]),
                                                          pct(r["trap_wrong_single_rate"]))
        elif r["_cmd"] == "l3":
            key = "correct %s, wrong %s, returned-type %s" % (pct(r["correct_rate"]), pct(r["wrong_rate"]),
                                                              pct(r["returned_type_rate"]))
        elif r["_cmd"] == "l1":
            key = "dev token cover %s" % pct(r["token_cover_rate"])
        elif r["_cmd"] == "l5":
            key = "mean %s ms" % r["mean_ms"]
        rows.append([r["_seq"], r["_cmd"], os.path.basename(os.path.dirname(r["placement"].rstrip("/")))
                     + "/" + os.path.basename(r["placement"].rstrip("/")), short(r.get("config_sha256")), key])
    T["dev_history"] = md(["run", "command", "placement", "config sha", "dev result"], rows)
    # ---- L1 detail
    if l1:
        T["l1_by_pos"] = md(["word class", "tokens", "covered", "rate"],
                            [[k, v["tokens"], v.get("hit", 0), pct(l1["by_pos_rate"][k])]
                             for k, v in sorted(l1["by_pos"].items())])
        T["l1_by_source"] = md(["source of the sentence", "tokens", "covered", "rate"],
                               [[k, v["tokens"], v.get("hit", 0), pct(v.get("hit", 0) / v["tokens"])]
                                for k, v in sorted(l1["by_source"].items())])
        T["l1_tokens_by_result"] = md(["kind", "counts"], [
            ["origin of the answer", ", ".join("%s=%s" % kv for kv in sorted(l1["tokens_by_origin"].items()))],
            ["state of the answer", ", ".join("%s=%s" % kv for kv in sorted(l1["tokens_by_state"].items()))]])
        T["l1_top_misses"] = md(["word", "class", "uncovered tokens"],
                                [[m["term"], m["pos"], m["n"]] for m in l1["top_misses"][:40]])
        T["l1_breadth"] = md(["breakdown of placed headwords", "counts"], [
            ["by state", ", ".join("%s=%s" % kv for kv in sorted(l1["placed_by_state"].items()))],
            ["placed (direct) by namespace", ", ".join("%s=%s" % kv for kv in sorted(l1["placed_by_ns"].items()))],
            ["placed (direct) by origin of the headword", ", ".join("%s=%s" % kv for kv in sorted(l1["placed_by_kind"].items()))],
            ["placed (direct) by decisive arm", ", ".join("%s=%s" % kv for kv in sorted(l1["placed_by_arm"].items()))],
            ["all rows in the headword table", "{:,}".format(l1["headwords_all_rows"])]])
    # ---- L2 detail
    if l2:
        T["l2_by_type"] = md(["gold type", "outcomes"], counter_rows(l2["by_gold_type"]))
        T["l2_by_category"] = md(["category", "outcomes"], counter_rows(l2["by_category"]))
        T["l2_by_arm"] = md(["decisive arm", "outcomes"], counter_rows(l2["by_decisive_arm"]))
        T["l2_traps"] = md(["end-of-word unit suggests", "outcomes"], counter_rows(l2["by_trap_unit_suggest"]))
        T["l2_summary"] = md(["measure", "value"], [
            ["words scored (seed words removed)", l2["n"]],
            ["direct", l2["direct_n"]],
            ["non-direct (reference)", ", ".join("%s=%s" % kv for kv in sorted(l2["non_direct"].items()))],
            ["by state", ", ".join("%s=%s" % kv for kv in sorted(l2["by_state"].items()))],
            ["size of top (number of types listed -> words)", ", ".join("%s->%s" % kv for kv in sorted(l2["len_top_distribution"].items()))]])
    # ---- L3 detail
    if l3:
        T["l3_by_kind"] = md(["kind", "outcomes"], counter_rows(l3["by_kind"]))
        T["l3_by_type"] = md(["gold type", "outcomes"], counter_rows(l3["by_gold_type"]))
        T["l3_by_stage"] = md(["deciding stage", "outcomes"], counter_rows(l3["by_decisive_stage"]))
    # ---- build
    if man:
        o = man["outputs"]
        T["build_summary"] = md(["item", "value"], [
            ["build started / finished (UTC)", "%s / %s" % (man["build_started_at_utc"], man["build_finished_at_utc"])],
            ["duration (s)", man["duration_sec"]],
            ["stage seconds", ", ".join("%s=%s" % kv for kv in sorted(man["stage_seconds"].items()))],
            ["placement bytes", "{:,}".format(man["placement_bytes"])],
            ["content_sha256", man["content_sha256"]],
            ["config sha256", man["config_sha256"]],
            ["coarse_types.py sha256", man["coarse_types_sha256"]],
            ["tables (rows)", ", ".join("%s=%s" % (k, "{:,}".format(v)) for k, v in sorted(o["tables"].items()))],
            ["rows by state / namespace", ", ".join("%s=%s" % kv for kv in sorted(o["by_state_ns"].items()))],
            ["evidence rows by arm", ", ".join("%s=%s" % kv for kv in sorted(o["evidence_by_arm"].items()))],
            ["hypernym chain rounds", "; ".join("round %s: donors %s, decided %s" % (r["round"], r["donors"], r["decided_heads"])
                                              for r in man["hypernym_rounds"])],
            ["alias rows", ", ".join("%s=%s" % kv for kv in sorted(man["alias_stats"].items()))],
            ["seed counts", ", ".join("%s=%s" % kv for kv in sorted(man["seed_counts"].items()))],
        ])
        fu = o.get("funnel", {})
        T["funnel"] = md(["step (distinct words)", "count"], [
            ["words in the tokenised material (any count)", "{:,}".format(fu.get("distinct_words_in_material_any_count", 0))],
            ["words in the material seen at least min_seen times", "{:,}".format(fu.get("distinct_words_in_material_min_seen", 0))],
            ["titles whose first sentence gave a hypernym phrase", "{:,}".format(fu.get("titles_with_definition_phrase", 0))],
            ["titles with a qualifier phrase (other senses)", "{:,}".format(fu.get("titles_with_qualifier_phrase", 0))],
            ["alias titles whose target had a type", "{:,}".format(fu.get("alias_titles_with_typed_target", 0))],
            ["paren-alias words whose head had a type", "{:,}".format(fu.get("paren_alias_words_with_typed_target", 0))],
            ["words whose sources disagree on noun / verb (or tie): both arm sets evaluated", "{:,}".format(fu.get("ns_conflict_or_tied_words", 0))],
            ["rows in the headword table", "{:,}".format(fu.get("rows", 0))],
            ["rows with any evidence row", "{:,}".format(fu.get("rows_with_any_evidence", 0))],
            ["rows placed directly (DECIDED or MULTIPLE)", "{:,}".format(fu.get("rows_placed_direct", 0))]])
        rows = []
        for i in man["inputs"]:
            rows.append([i["name"], "{:,}".format(i["bytes"]), i.get("lines", i.get("rows", "")), short(i.get("sha256"))])
        T["build_inputs"] = md(["input", "bytes", "lines / rows", "sha256 (prefix)"], rows)
        rows = []
        for src, d in sorted(man["skipped_rows_by_reason"].items()):
            rows.append([src, ", ".join("%s=%s" % kv for kv in sorted(d.items()))])
        T["build_skips"] = md(["source", "rows skipped, by reason"], rows)
        T["build_excluded"] = md(["item", "value"], [
            ["unknown words excluded (terms)", man["excluded_terms_total"]],
            ["rows/titles dropped for containing one", sum(man["excluded_term_hits"].values())],
            ["held-out rows removed", json.dumps(man["holdout"], ensure_ascii=False)]])
        T["build_materials"] = md(["material", "use"], [[m["name"], m.get("role") or m.get("use") or m.get("path")]
                                                     for m in man["materials"]])
        T["config"] = md(["setting", "value"], [[k, v] for k, v in sorted(man["config"].items())])
    # ---- audit of the decision rule on the whole placement (review r1 M1 + M2)
    ap = os.path.join(A, "audit_met_arms_r5.json")
    if not os.path.exists(ap):
        ap = os.path.join(A, "audit_met_arms_full.json")
    if os.path.exists(ap):
        au = load(ap)
        c = au["counts"]
        T["met_audit"] = md(["check (every decided headword of the final full placement)", "count"], [
            ["direct headwords", "{:,}".format(au["direct_headwords"])],
            ["estimated (generated) headwords", "{:,}".format(au.get("estimated_generated_headwords", 0))],
            ["re-decided by coarse_types.decide_word from the stored evidence (direct + estimated)", "{:,}".format(au["words_with_evidence_checked"])],
            ["stored origin differs from the recomputed one (W3-a2)", c.get("origin_mismatch", 0)],
            ["stored decision differs from the recomputed one", c.get("recompute_mismatch", 0)],
            ["set of met arms differs from decided_by (M2)", c.get("met_ne_decided_by", 0)],
            ["decided by exactly one role source and no other arm (M1)", c.get("role_alone", 0)],
            ["a role source among the deciding arms but fewer than role_min_sources", c.get("role_in_by_single", 0)],
            ["seed-decided word with another arm still marked met", c.get("seed_but_other_met", 0)],
            ["direct by one role source below role_min_sources + an agreeing generated definition (by design, W3-a2)", c.get("role_single_source_with_generated_agreement", 0)],
            ["deciding arms (word counts)", ", ".join("%s=%s" % (k[3:], v) for k, v in sorted(c.items()) if k.startswith("by:"))]])
    # ---- predicates
    if pr:
        rows = [["all", pr["all"]["n"], pr["all"]["correct"], pr["all"]["wrong_single"], pr["all"]["returned_any"]],
                ["not a seed of this build (the official figure)", pr["non_seed_now"]["n"], pr["non_seed_now"]["correct"],
                 pr["non_seed_now"]["wrong_single"], pr["non_seed_now"]["returned_any"]]] if "non_seed_now" in pr else [
                ["all", pr["all"]["n"], pr["all"]["correct"], pr["all"]["wrong_single"], pr["all"]["returned_any"]],
                ["non-seed (frozen flag)", pr["non_seed"]["n"], pr["non_seed"]["correct"], pr["non_seed"]["wrong_single"],
                 pr["non_seed"]["returned_any"]]]
        for t, v in sorted(pr["by_gold_type"].items()):
            rows.append([t, v["n"], v["correct"], v["wrong_single"], v["returned_any"]])
        T["pred"] = md(["subset", "n", "correct", "wrong (one type)", "returned any type"], rows)
        T["pred_by_arm"] = md(["decisive arm", "n", "correct", "wrong (one type)", "returned any"],
                              [[a, v["n"], v["correct"], v["wrong_single"], v["returned_any"]]
                               for a, v in sorted(pr["by_decisive_arm"].items())])
    w3a2_tables(T, ev)
    # ---- speed
    if l5:
        T["speed"] = md(["measure", "value"], [
            ["queries", l5["n_queries"]], ["mean ms", l5["mean_ms"]], ["median ms", l5["median_ms"]],
            ["p95 ms", l5["p95_ms"]], ["max ms", l5["max_ms"]],
            ["command-line call incl. load (ms)", l5["cli_one_call_ms_including_load"]],
            ["interpreter + import only (ms)", l5["python_import_only_ms"]]])
    return T, (l1, l2, l3, pr)


def errors_md(l1, l2, l3, pr):
    out = ["# W3-a wrong or unplaced words (frozen test data, last measurement)\n",
           "Generated by render_docs_numbers.py from the last eval_runs; do not edit.\n"]
    if l2:
        out.append("\n## L2: typed vocabulary (not 'direct and correct')\n")
        rows = [[e["id"], e["term"], ",".join(e["gold"]), e["category"],
                 "trap(%s)" % e["trap_suggests"] if e["trap"] else "", e["state"], e["origin"] or "-",
                 ",".join(e["top"]) or "-", e["decided_by"], " ".join(e.get("neighbors", []))]
                for e in l2["errors"]]
        out.append(md(["id", "word", "gold", "category", "trap", "state", "origin", "returned top", "decided by",
                       "neighbours"], rows))
    if l3:
        out.append("\n## L3: unknown words (wrong, returned a type for a gold-unknown word, or no type)\n")
        rows = [[e["id"], e["term"], e["kind"], ",".join(e["gold"]) or "(unknown)", e["state"], e["origin"] or "-",
                 ",".join(e["top"]) or "-", e["cls"], e["decided_by"], " ".join(e.get("neighbors", []))]
                for e in l3["errors"]]
        out.append(md(["id", "word", "kind", "gold", "state", "origin", "returned top", "outcome", "decided by",
                       "neighbours"], rows))
    return "".join(out)


def apply(doc, T):
    for name, body in T.items():
        pat = re.compile(r"(<!-- BEGIN table:%s -->\n).*?(<!-- END table:%s -->)" % (re.escape(name), re.escape(name)), re.S)
        if pat.search(doc):
            doc = pat.sub(lambda m: m.group(1) + body + m.group(2), doc)
    return doc


def main():
    T, (l1, l2, l3, pr) = tables()
    doc = open(DOC, encoding="utf-8").read()
    new = apply(doc, T)
    # every marker must have been filled
    names = re.findall(r"<!-- BEGIN table:(\w+) -->", new)
    missing = [n for n in names if n not in T]
    err = errors_md(l1, l2, l3, pr)
    if "--check" in sys.argv:
        bad = []
        if new != doc:
            bad.append("docs/COARSE_PLACEMENT.md differs from the rendering")
        if not os.path.exists(ERR) or open(ERR, encoding="utf-8").read() != err:
            bad.append("errors_final.md differs from the rendering")
        if missing:
            bad.append("markers without data: %s" % missing)
        print("CHECK", "FAIL: " + "; ".join(bad) if bad else "OK")
        return 1 if bad else 0
    open(DOC, "w", encoding="utf-8").write(new)
    open(ERR, "w", encoding="utf-8").write(err)
    print("rendered", len(T), "tables; markers without data:", missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())

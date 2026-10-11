"""Side-by-side table close | defer from results/c3b_*.json -> results/summary.md (and stdout)."""
import json, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
rows = []
def load(t, l, r):
    p = os.path.join(D, "c3b_%s_%s_%s.json" % (t, l, r))
    return json.load(open(p)) if os.path.exists(p) else None
def ms(d, lvl, key):
    s = d["per_level"][str(lvl)][key]; return "%d / %d" % (s["med"], s["max"])
lines = []
for t, l in (("RUN", "low"), ("WORD", "low"), ("RUN", "mid"), ("WORD", "mid")):
    a, b = load(t, l, "close"), load(t, l, "defer")
    if not (a and b): continue
    def row(name, f):
        lines.append("| %s | %s | %s | %s |" % (name, t + " " + l, f(a), f(b)))
    row("levels", lambda d: d["levels"])
    row("units per level", lambda d: ", ".join(map(str, d["units_per_level"])))
    row("blacks (level 0)", lambda d: d["units_per_level"][0])
    row("elements per black med/max", lambda d: ms(d, 0, "elements"))
    row("sentences per black med/max", lambda d: ms(d, 0, "sentences"))
    row("sentences split (events)", lambda d: "%d (%d)" % (d["sentences_split"], d["split_events"]))
    row("packs", lambda d: d["packs"])
    row("copied pairs / woken / never woken", lambda d: "%d / %d / %d" % (d["copied_pairs"], d["woken_pairs"], d["never_woken_pairs"]))
    row("distinct packs woken", lambda d: d["distinct_packs_woken"])
    row("activation_deferred empty / non-empty", lambda d: "%d / %d" % (d["deferred_empty"], d["deferred_nonempty"]))
    row("non-empty pack collapses (alone fits)", lambda d: "%d (%d)" % (d["pack_collapses_nonempty"], d["alone_fits"]))
    row("closes caused only by woken packs", lambda d: d["closes_by_packs_only"])
    row("closes (all levels)", lambda d: d["closes"])
    def cen(d):
        c = d["centre_level0_closed"]
        return "%d / %d blacks any, %d all; %d / %d flats" % (c["any_pack_centre"], c["blacks"], c["all_pack_centre"], c["pack_centre_flats"], c["flats"])
    row("level-0 blacks with a pack centre", cen)
    row("P-1 failures / O-2 mismatches", lambda d: "%d / %d" % (len(d["frontier_coverage_failed_after_sentences"]), len(d["ledger_mismatches"])))
    row("time (CPU s, spy included)", lambda d: d["total_secs_cpu"])
NOTE = 'NOTE (2026-10-11, L-G4-72). The S300 tower measurements in this directory were taken under the OLD rule: `placement._settle` did not check the first class (the best-key terminals) against `max_class` (L-G4-47 / L-G4-50 changed that). Under the current code the WORD tower differs: on the 12-sentence S300 toy at level low, 146 of 370 events (a first class of 132 arrangements > max_class 63, kept before, is now a max_class rollback at event 131 and the black closes; RUN differs only in the `work` counts of 2 of 217 events). The effect on the S300 results is NOT measured (owner: 「規則を貫き、塔のピンを更新して C3 の記録に注記」, no re-measurement). The results/logs here are unchanged records of the old rule.\n' + "\n"
out = NOTE + "| quantity | run | close (baseline) | defer |\n|---|---|---|---|\n" + "\n".join(lines) + "\n"
open(os.path.join(D, "summary.md"), "w").write(out)
print(out)

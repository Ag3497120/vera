"""C2 measurement: the product black feed (verantyx.line3.carry.BlackStream) on S300, to be compared with C0's stream.
usage: c2.py TIER LEVEL [N] [OUTJSON] [--verify]   (run from the repo root, PYTHONPATH=.)
Same data / space / budget as experiments/line3/carry/c0/c0.py stream; the carry is empty (C3 is not built)."""
import json, sys, time
from verantyx.line3 import space as sp, placement as pl, carry as C
args = [a for a in sys.argv[1:] if not a.startswith("--")]
verify = "--verify" in sys.argv
tier, lv = args[0], args[1]
N = int(args[2]) if len(args) > 2 else 300
out = args[3] if len(args) > 3 else None
rows = [json.loads(l) for l in open('experiments/line3/data/S300.jsonl', encoding='utf-8')][:N]
budget = pl.budget_level(lv)
ts = sp.build_space(rows).tiers[tier]
n = len(rows)
sids = list(range(n))
led = C.Ledger(C.stream_header(tier, sids, budget, unit_filter="default"))
bs = C.BlackStream(tier, budget, led, clock=time.process_time)
sent_secs = []
t_all = time.process_time()
for s in sids:
    t0 = time.process_time()
    bs.feed_sentence(s, C.occurrences_of(ts, s))
    sent_secs.append(time.process_time() - t0)
total = time.process_time() - t_all
blacks = bs.closed
rec = [{"units": cb.black.n_elements, "sents": cb.black.space.N, "L": cb.black.L, "classes": len(cb.black.state)} for cb in blacks]
last = bs.black                                    # the still-open black (L-310): not closed
if not last.is_empty:
    rec.append({"units": last.n_elements, "sents": last.space.N, "L": last.L, "classes": len(last.state), "open": True})
res = {"mode": "c2", "tier": tier, "level": lv, "n": n, "blacks": rec, "split": sorted(set(bs.split_sids)),
       "split_events": len(bs.split_sids), "events": len(led), "ledger_sha256": led.sha256(),
       "total_secs": round(total, 1)}
ss = sorted(sent_secs); res.update(sent_secs_mean=sum(sent_secs) / n, sent_secs_p90=ss[int(.9 * n)], sent_secs_max=ss[-1])
ev = sorted(x for _, x in bs.event_secs)
res.update(admit_secs_mean=sum(ev) / len(ev), admit_secs_p90=ev[int(.9 * len(ev))], admit_secs_max=ev[-1], admits=len(ev))
kinds = {}
for e in led.events(): kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
res["event_kinds"] = kinds
if verify:
    bad, tested, skipped, vsecs = [], 0, 0, 0.0
    for cb in list(blacks) + ([] if last.is_empty else [None]):
        b = cb.black if cb is not None else last
        t0 = time.process_time(); r = b.verify(); vsecs += time.process_time() - t0
        tested += 1
        if not r.is_stable_class or r.size != len(b.state): bad.append(b.unit)
    res.update(verified=tested, verify_failed=bad, verify_secs=round(vsecs, 1))
if out: json.dump(res, open(out, "w"))
print(json.dumps({k: v for k, v in res.items() if k not in ("blacks", "split")}))

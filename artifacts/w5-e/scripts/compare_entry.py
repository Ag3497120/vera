"""W5-e: compare two entry dumps (w3b1_entry_dump.py --out FILE: one JSON row per sentence) row by row and classify every row that changed.
usage: compare_entry.py BEFORE AFTER OUT.tsv
Classes (the first that applies):
  gate_read_to_abstain   readable before, not readable after, and a reason of the new gate (COORDINATION_UNDETERMINED / DISJUNCTION_UNDETERMINED) is in the after output
  gate_reason_only       not readable before and after, the only difference is a reason of the new gate (unsupported / abstain reasons)
  gate_reason_added      not readable before and after, a reason of the new gate is in the after output and not in the before output (the abstain kind may move from UNSUPPORTED_CLAUSE to
                         NO_SUPPORTED_CLAUSE because the gate marks the clause that was still supported): an abstention stays an abstention
  other_read_to_abstain  readable before, not readable after, without a reason of the new gate  (to be explained one by one)
  abstain_to_read        not readable before, readable after   (a loosening: must be 0)
  read_changed           readable before and after with a different output   (a read changed into another read: must be 0)
  other_abstain_change   not readable before and after, a difference that is not the gate's reason only (to be explained one by one)
Prints the counts and every row of the classes that must be explained."""
import json
import sys

GATE = ("COORDINATION_UNDETERMINED", "DISJUNCTION_UNDETERMINED")


def reasons_of(out):
    r = list((out.get("abstain") or {}).get("reasons") or [])
    for u in out.get("unsupported") or []: r.extend(u.get("reasons") or [])
    return r


def strip_gate(out):
    o = json.loads(json.dumps(out))
    if o.get("abstain") and o["abstain"].get("reasons"): o["abstain"]["reasons"] = [r for r in o["abstain"]["reasons"] if r not in GATE]
    for u in o.get("unsupported") or []: u["reasons"] = [r for r in u.get("reasons") or [] if r not in GATE]
    return o


def main():
    before = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    after = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
    assert [r["text"] for r in before] == [r["text"] for r in after], "the inputs differ"
    counts, rows = {}, []
    for b, a in zip(before, after):
        if b == a: continue
        bo, ao = b["out"], a["out"]
        gate = [r for r in reasons_of(ao) if r in GATE]
        if bo.get("readable") and not ao.get("readable"): cls = "gate_read_to_abstain" if gate else "other_read_to_abstain"
        elif not bo.get("readable") and ao.get("readable"): cls = "abstain_to_read"
        elif bo.get("readable") and ao.get("readable"): cls = "read_changed"
        elif gate and strip_gate(ao) == strip_gate(bo): cls = "gate_reason_only"
        elif gate and not [r for r in reasons_of(bo) if r in GATE]: cls = "gate_reason_added"
        else: cls = "other_abstain_change"
        counts[cls] = counts.get(cls, 0) + 1
        rows.append((cls, b["text"], b.get("source"), "read" if bo.get("readable") else "abstain",
                     json.dumps([c.get("roles") for c in bo.get("clauses") or []], ensure_ascii=False), "|".join(reasons_of(bo)), "|".join(reasons_of(ao))))
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        f.write("class\ttext\tsource\tbefore\tbefore_roles\tbefore_reasons\tafter_reasons\n")
        for r in rows: f.write("\t".join(r) + "\n")
    print("rows", len(before), "changed", len(rows), json.dumps(counts, sort_keys=True))
    for r in rows:
        if r[0] in ("other_read_to_abstain", "abstain_to_read", "read_changed", "other_abstain_change"): print(r)


if __name__ == "__main__":
    main()

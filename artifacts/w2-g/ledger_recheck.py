"""Independent recount of a run's decisions from its ledger: every map_ask raw_reply is read again with the closed readers of llm_choice,
mapped back to the original numbering with the saved ``order``, the two asks of a decision are combined (failure, invalid, none/none, equal, else
disagree) and the result is compared with the saved map_decision row.  Usage: ledger_recheck.py <ledger.jsonl>..."""
import json, sys
from verantyx import llm_choice as L

def legacy_phases(row, n):
    """The phases reader of rounds 1-2 (reply {"phases": [...]} only), kept here to recount the saved ledgers of those runs."""
    def pairs(ps):
        d = {}
        for k, v in ps:
            if k in d: raise ValueError("duplicate key")
            d[k] = v
        return d
    try:
        data = json.loads(row["raw_reply"], object_pairs_hook=pairs)
    except ValueError:
        return ("INVALID", None)
    if not isinstance(data, dict) or set(data) != {"phases"} or not isinstance(data["phases"], list):
        return ("INVALID", None)
    ph = data["phases"]
    if any(type(x) is not int for x in ph) or any(x < 0 or x >= n for x in ph) or len(set(ph)) != len(ph):
        return ("INVALID", None)
    return ("NONE", None) if not ph else ("PICK", tuple(sorted(row["order"][j] for j in ph)))

def read(row):
    if row["failure"] or row["raw_reply"] is None:
        return ("FAILED", None)
    n = len(row["order"])
    if row["step"] == "records":
        v, picks, decides, _ = L.classify_records_reply(row["raw_reply"], n)
        if v == "PICK":
            ids = [row["candidates"][row["order"][j]]["id"] for j in picks]
            return (v, (tuple(sorted(row["order"][j] for j in picks)), decides))
        return (v, None)
    if row["step"] == "phases":
        if '"decides"' not in row["prompt"]:            # a run of rounds 1-2: the phases reply had no decides (the reader of that time)
            return legacy_phases(row, n)
        v, picks, decides, _ = L.classify_phases_reply(row["raw_reply"], n)
        return (v, (tuple(sorted(row["order"][j] for j in picks)), decides) if v == "PICK" else None)
    v, labels, _ = L.classify_relations_reply(row["raw_reply"], n)
    if v != "PICK":
        return (v, None)
    orig = [None] * n
    for j, lab in enumerate(labels):
        orig[row["order"][j]] = lab
    return (v, tuple(orig))

total_bad = 0
for path in sys.argv[1:]:
    rows = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
    asks = {}
    for r in rows:
        if r["type"] == "map_ask":
            asks.setdefault(r["decision_id"], []).append(r)
    n_dec = bad = n_ask = 0
    steps = {}
    for r in rows:
        if r["type"] != "map_decision" or r["status"] == "REFUSED":
            continue
        a = sorted(asks.get(r["decision_id"], []), key=lambda x: x["ask_index"])
        if len(a) != 2:
            bad += 1; print("BAD ask count", r["decision_id"], len(a)); continue
        n_dec += 1; n_ask += 2
        steps[r["step"]] = steps.get(r["step"], 0) + 1
        x, y = read(a[0]), read(a[1])
        if "FAILED" in (x[0], y[0]): status = "FAILED"
        elif "INVALID" in (x[0], y[0]): status = "ABSTAINED"
        elif x[0] == y[0] == "NONE": status = "NONE"
        elif x[0] == y[0] == "PICK" and x[1] == y[1]: status = "ADOPTED"
        else: status = "ABSTAINED"
        if status != r["status"]:
            bad += 1; print("MISMATCH", r["decision_id"], r["step"], status, r["status"])
    total_bad += bad
    print(f"{path}: decisions {n_dec} asks {n_ask} steps {dict(sorted(steps.items()))} mismatches {bad}")
print("TOTAL mismatches", total_bad)

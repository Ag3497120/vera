"""W2-g2 independent recount of the decisions of conduct_map/v2 ledgers.  Every map_ask row's raw_reply is read again with the minimal-form
readers of llm_choice (classify_index_list_reply / classify_label_reply), mapped back to the original numbering with the saved ``order``,
and the rows of a decision are combined the way the protocol says: each slot (0 / 1) counts by its last row (the second ask when the
first was invalid), failure first, then invalid, then none/none, then equal, else disagree.  The result is compared with the saved
map_decision row (status, reason, result, ask_ids), and the structure is checked: at most one second ask per slot, only after an invalid
first reply, never after a failure, never beside a failed slot, in an order different from the first one, with the same provider and
wording (variant); every row's saved verdict / parsed / invalid_reason equals the re-read one.
Usage: ledger_recheck_g2.py <ledger.jsonl>..."""
import json
import sys

from verantyx import llm_choice as L


def reread(row):
    """-> (verdict, parsed, invalid_reason) of a map_ask row from its raw reply and its saved order."""
    if row["failure"] or row["raw_reply"] is None:
        return "FAILED", None, None
    order = row["order"]
    if row["step"] in ("records", "phases"):
        v, picks, inv = L.classify_index_list_reply(row["raw_reply"], len(order))
        if v != "PICK":
            return v, None, inv
        orig = sorted(order[j] for j in picks)
        ids = [row["candidates"][i]["id"] for i in orig]
        return v, {"indexes": orig, row["step"]: ids}, None
    labels = ("決まる", "決まらない") if row["step"] == "decides" else ("一致", "矛盾", "無関係")
    shown = [labels[i] for i in order]
    if row["labels_shown"] != shown:
        return "BAD_LABELS_SHOWN", None, None
    v, lab, inv = L.classify_label_reply(row["raw_reply"], labels)
    return v, ({row["step"]: lab} if v == "PICK" else None), inv


def combine(a, b):
    for r in (a, b):
        if r[0] == "FAILED":
            return "FAILED", r[3]
    if "INVALID" in (a[0], b[0]):
        return "ABSTAINED", "INVALID_ANSWER"
    if a[0] == b[0] == "NONE":
        return "NONE", "NONE_SELECTED"
    if a[0] == b[0] == "PICK" and a[1] == b[1]:
        return "ADOPTED", "ADOPTED"
    return "ABSTAINED", "DISAGREE"


total_bad = 0
for path in sys.argv[1:]:
    rows = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
    by_dec = {}
    for r in rows:
        if r["type"] == "map_ask":
            by_dec.setdefault(r["decision_id"], []).append(r)
    bad = n_dec = n_ask = n_retry = n_row_bad = 0
    steps = {}
    for r in rows:
        if r["type"] != "map_decision":
            continue
        a_rows = by_dec.get(r["decision_id"], [])
        if r["status"] == "REFUSED":
            if a_rows or r["ask_ids"]:
                bad += 1
                print("BAD refused decision with asks", r["decision_id"])
            continue
        n_dec += 1
        n_ask += len(a_rows)
        steps[r["step"]] = steps.get(r["step"], 0) + 1
        if r["ask_ids"] != [x["id"] for x in a_rows]:
            bad += 1
            print("BAD ask_ids", r["decision_id"])
        last = {}
        first = {}
        for x in a_rows:
            v, parsed, inv = reread(x)
            if (v, parsed, inv) != (x["verdict"], x["parsed"], x["invalid_reason"]):
                n_row_bad += 1
                print("ROW MISMATCH", x["id"], (v, parsed, inv), (x["verdict"], x["parsed"], x["invalid_reason"]))
            k = x["ask_index"]
            if x["attempt"] == 0:
                if k in first:
                    bad += 1
                    print("BAD two first asks in a slot", x["id"])
                first[k] = x
                last[k] = (v, parsed, inv, x["failure"])
            else:
                n_retry += 1
                f = first.get(k)
                ok = (x["attempt"] == 1 and f is not None and f["verdict"] == "INVALID" and x["retry_of"] == f["id"]
                      and x["variant"] == f["variant"] and x["provider"] == f["provider"] and x["id"] == f["id"] + ".r1"
                      and (len(x["order"]) < 2 or x["order"] != f["order"]))
                other = first.get(1 - k)
                if other is not None and other["verdict"] == "FAILED":
                    ok = False
                if not ok:
                    bad += 1
                    print("BAD retry", x["id"])
                last[k] = (v, parsed, inv, x["failure"])
        if sorted(last) != [0, 1]:
            bad += 1
            print("BAD slots", r["decision_id"], sorted(last))
            continue
        status, reason = combine(last[0], last[1])
        want_result = None
        if status == "ADOPTED":
            p = last[0][1]
            if r["step"] in ("records", "phases"):
                want_result = {r["step"]: p[r["step"]]}
            else:
                want_result = {r["step"]: p[r["step"]]}
        elif status == "NONE":
            want_result = {r["step"]: []}
        if (status, reason, want_result) != (r["status"], r["reason"], r["result"]):
            bad += 1
            print("MISMATCH", r["decision_id"], r["step"], (status, reason, want_result), (r["status"], r["reason"], r["result"]))
    total_bad += bad + n_row_bad
    print(f"{path}: decisions {n_dec} asks {n_ask} retries {n_retry} steps {dict(sorted(steps.items()))} mismatches {bad} row_mismatches {n_row_bad}")
print("TOTAL mismatches", total_bad)

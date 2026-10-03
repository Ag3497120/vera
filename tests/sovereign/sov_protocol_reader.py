"""W4-m test helper: a reader that touches a ledger ONLY through the four `Ledger` functions.

It stands in for the field stage of W3-c (not integrated yet): whatever a stage can learn from a
conversation ledger, it learns through append / events / count / last_seq and nothing else.
`digest(ledger)` is the canonical byte string of everything those functions say.
"""
import json


def digest(ledger) -> bytes:
    events = list(ledger.events())
    pairs = sorted({(k, v) for e in events for k, v in e["payload"].items() if isinstance(v, str)})
    counts = {f"{k}={v}": [ledger.count(k, v), ledger.last_seq(k, v)] for k, v in pairs}
    tail = []
    if events:
        tail = list(ledger.events(since=events[0]["id"]))
    out = {"events": events, "counts": counts, "after_first": tail}
    return json.dumps(out, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def candidates(ledger, key):
    """The values of payload[key] seen so far, with count and latest seq (what a field stage would read)."""
    vals = sorted({e["payload"][key] for e in ledger.events()
                   if isinstance(e["payload"].get(key), str)})
    return [(v, ledger.count(key, v), ledger.last_seq(key, v)) for v in vals]
